"""
updater.py – WheelBooK automatikus frissítő
--------------------------------------------
GitHub-alapú fél-automatikus frissítés.

Beállítás:
  1. Hozz létre egy GitHub repót (pl. felhasználonev/wheelbook)
  2. Töltsd fel a .py fájlokat és a version.txt-t
  3. Az alábbi GITHUB_USER és GITHUB_REPO változókat írd át

GitHub repó struktúra:
  /version.txt          ← csak a verziószám, pl: 9.2
  /main.py
  /ui_components.py
  /database.py
  /config.py
  /backup_manager.py
  /reminder_manager.py
  /updater.py
  /CHANGELOG.md
"""

import os
import sys
import shutil
import zipfile
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

# ── BEÁLLÍTÁS ──────────────────────────────────────────────────────────────────
GITHUB_USER = "FELHASZNÁLÓNÉV"       # ← írd át a saját GitHub felhasználónevedre
GITHUB_REPO = "wheelbook"            # ← írd át a repó nevére
CURRENT_VERSION = "9.1"              # ← ezt mindig frissítsd új verzió kiadásakor
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main"
ZIP_URL  = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/main.zip"

# Ezek a fájlok frissülnek (az adatbázis és a config NEM)
UPDATABLE_FILES = [
    "main.py",
    "ui_components.py",
    "database.py",
    "config.py",
    "backup_manager.py",
    "reminder_manager.py",
    "updater.py",
    "CHANGELOG.md",
]


class UpdateChecker:
    def __init__(self, base_dir: str, on_update_available_callback):
        """
        base_dir: az exe könyvtára (sys.executable mappája)
        on_update_available_callback(latest_version, changelog): UI szálon hívandó
        """
        self.base_dir = base_dir
        self.on_update_available = on_update_available_callback

    def check_async(self):
        """Háttérszálon ellenőrzi a verziót – nem blokkolja az UI-t."""
        t = threading.Thread(target=self._check, daemon=True)
        t.start()

    def _check(self):
        try:
            latest = self._fetch_latest_version()
            if latest and self._is_newer(latest, CURRENT_VERSION):
                changelog = self._fetch_changelog_snippet(latest)
                # Visszaad az UI szálra (a hívó felelős a tkinter after()-rel)
                self.on_update_available(latest, changelog)
        except Exception as e:
            logger.warning(f"Frissítés ellenőrzés sikertelen: {e}")

    def _fetch_latest_version(self) -> str | None:
        url = f"{BASE_URL}/version.txt"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.read().decode("utf-8").strip()
        except urllib.error.URLError as e:
            logger.info(f"Verzió lekérés sikertelen (nincs net?): {e}")
            return None

    def _fetch_changelog_snippet(self, version: str) -> str:
        """Lekéri a CHANGELOG.md-ből az adott verzió szekciót."""
        url = f"{BASE_URL}/CHANGELOG.md"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                content = r.read().decode("utf-8")
            # Csak az első (legújabb) blokkot adjuk vissza
            blocks = content.split("\n## ")
            if len(blocks) > 1:
                lines = blocks[1].splitlines()
                # Max 10 sor
                return "\n".join(lines[:10])
        except Exception:
            pass
        return f"v{version} – újdonságok a CHANGELOG.md-ben"

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        """Összehasonlítja a verziókat (pl. '9.2' > '9.1')."""
        try:
            def to_tuple(v):
                return tuple(int(x) for x in v.strip().split("."))
            return to_tuple(latest) > to_tuple(current)
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Letöltés és telepítés
    # ------------------------------------------------------------------

    def download_and_install(self, progress_callback=None) -> tuple[bool, str]:
        """
        Letölti a ZIP-et, kicsomagolja az UPDATABLE_FILES fájlokat.
        Visszatér: (sikeres: bool, üzenet: str)
        progress_callback(pct: int) – opcionális, 0-100
        """
        tmp_zip = os.path.join(self.base_dir, "_update_tmp.zip")
        tmp_dir = os.path.join(self.base_dir, "_update_tmp_dir")

        # Backup mappa: telepített módban Dokumentumok/WheelBooK/backups
        import sys
        if getattr(sys, 'frozen', False):
            data_dir = os.path.join(os.path.expanduser("~"), "Documents", "WheelBooK")
        else:
            data_dir = os.path.join(self.base_dir, "adatok")
        backup_root = os.path.join(data_dir, "backups")

        try:
            # 1. Biztonsági mentés az aktuális fájlokról
            backup_dir = os.path.join(backup_root,
                                      f"pre_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(backup_dir, exist_ok=True)
            for fname in UPDATABLE_FILES:
                src = os.path.join(self.base_dir, fname)
                if os.path.exists(src):
                    shutil.copy2(src, backup_dir)
            logger.info(f"Frissítés előtti backup: {backup_dir}")

            if progress_callback:
                progress_callback(10)

            # 2. ZIP letöltése
            logger.info(f"Letöltés: {ZIP_URL}")
            urllib.request.urlretrieve(ZIP_URL, tmp_zip)

            if progress_callback:
                progress_callback(50)

            # 3. Kicsomagolás
            repo_prefix = f"{GITHUB_REPO}-main/"
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                for fname in UPDATABLE_FILES:
                    zip_path = f"{repo_prefix}{fname}"
                    if zip_path in zf.namelist():
                        dest = os.path.join(self.base_dir, fname)
                        with zf.open(zip_path) as src_f, open(dest, "wb") as dst_f:
                            dst_f.write(src_f.read())
                        logger.info(f"  Frissítve: {fname}")
                    else:
                        logger.warning(f"  Nem található a ZIP-ben: {fname}")

            if progress_callback:
                progress_callback(90)

            return True, "Frissítés sikeres! Zárd be és nyisd meg újra az alkalmazást."

        except urllib.error.URLError as e:
            return False, f"Letöltési hiba (nincs internetkapcsolat?):\n{e}"
        except zipfile.BadZipFile:
            return False, "Sérült letöltött fájl. Próbáld újra."
        except Exception as e:
            return False, f"Váratlan hiba a frissítés során:\n{e}"
        finally:
            # Temp fájlok takarítása
            for path in [tmp_zip, tmp_dir]:
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except OSError:
                    pass
            if progress_callback:
                progress_callback(100)