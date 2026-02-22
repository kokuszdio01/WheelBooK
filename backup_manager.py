"""
backup_manager.py
-----------------
Automatikus és manuális biztonsági mentés kezelése.
- Napi automatikus backup az adatbázisról
- ZIP export (adatbázis + csatolmányok)
- ZIP import (visszaállítás)
- Régi backupok automatikus törlése
"""

import os
import shutil
import zipfile
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BackupManager:
    def __init__(self, base_dir: str, db_path: str, backup_keep_days: int = 30):
        self.base_dir = base_dir
        self.db_path = db_path
        self.backup_keep_days = backup_keep_days
        self.backup_dir = os.path.join(base_dir, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Automatikus napi backup
    # ------------------------------------------------------------------

    def run_auto_backup(self) -> bool:
        """
        Csak akkor készít backupot, ha ma még nem volt.
        Visszatér: True ha készült backup, False ha már volt ma.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_backup = os.path.join(self.backup_dir, f"auto_{today_str}.db")

        if os.path.exists(today_backup):
            logger.info("Napi backup már létezik, kihagyva.")
            return False

        try:
            shutil.copy2(self.db_path, today_backup)
            logger.info(f"Automatikus backup elkészült: {today_backup}")
            self._cleanup_old_backups()
            return True
        except Exception as e:
            logger.error(f"Automatikus backup hiba: {e}")
            return False

    def _cleanup_old_backups(self):
        """Törli a megadott napnál régebbi automatikus backupokat."""
        cutoff = datetime.now() - timedelta(days=self.backup_keep_days)
        for fname in os.listdir(self.backup_dir):
            if not fname.startswith("auto_") or not fname.endswith(".db"):
                continue
            fpath = os.path.join(self.backup_dir, fname)
            try:
                date_str = fname.replace("auto_", "").replace(".db", "")
                fdate = datetime.strptime(date_str, "%Y-%m-%d")
                if fdate < cutoff:
                    os.remove(fpath)
                    logger.info(f"Régi backup törölve: {fname}")
            except (ValueError, OSError):
                continue

    # ------------------------------------------------------------------
    # ZIP export
    # ------------------------------------------------------------------

    def export_zip(self, dest_path: str) -> bool:
        """
        Teljes ZIP exportálás: adatbázis + csatolmányok mappa.
        dest_path: a kívánt ZIP fájl elérési útja
        """
        upload_dir = os.path.join(self.base_dir, "csatolmanyok")
        try:
            with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Adatbázis
                zf.write(self.db_path, arcname="auto_naplo.db")

                # Csatolmányok
                if os.path.exists(upload_dir):
                    for fname in os.listdir(upload_dir):
                        fpath = os.path.join(upload_dir, fname)
                        if os.path.isfile(fpath):
                            zf.write(fpath, arcname=os.path.join("csatolmanyok", fname))

                # Metaadat
                meta = f"WheelBooK backup\nDátum: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                zf.writestr("backup_info.txt", meta)

            logger.info(f"ZIP export sikeres: {dest_path}")
            return True
        except Exception as e:
            logger.error(f"ZIP export hiba: {e}")
            return False

    # ------------------------------------------------------------------
    # ZIP import (visszaállítás)
    # ------------------------------------------------------------------

    def import_zip(self, zip_path: str) -> tuple[bool, str]:
        """
        ZIP visszaállítás. Előtte biztonsági mentést készít a jelenlegi állapotról.
        Visszatér: (sikeres: bool, üzenet: str)
        """
        # Előzetes biztonsági mentés
        pre_backup = os.path.join(
            self.backup_dir,
            f"pre_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        try:
            shutil.copy2(self.db_path, pre_backup)
        except Exception as e:
            return False, f"Nem sikerült előzetes mentést készíteni:\n{e}"

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()

                if "auto_naplo.db" not in names:
                    return False, "A ZIP fájl nem tartalmaz érvényes WheelBooK adatbázist!"

                # Adatbázis visszaállítása
                with zf.open("auto_naplo.db") as src, open(self.db_path, "wb") as dst:
                    dst.write(src.read())

                # Csatolmányok visszaállítása
                upload_dir = os.path.join(self.base_dir, "csatolmanyok")
                os.makedirs(upload_dir, exist_ok=True)
                for name in names:
                    if name.startswith("csatolmanyok/") and not name.endswith("/"):
                        fname = os.path.basename(name)
                        dest = os.path.join(upload_dir, fname)
                        with zf.open(name) as src, open(dest, "wb") as dst:
                            dst.write(src.read())

            logger.info(f"ZIP visszaállítás sikeres: {zip_path}")
            return True, "Visszaállítás sikeres! Az alkalmazás újraindítása szükséges."

        except zipfile.BadZipFile:
            # Visszaállítjuk az eredeti DB-t
            shutil.copy2(pre_backup, self.db_path)
            return False, "Sérült vagy érvénytelen ZIP fájl!"
        except Exception as e:
            shutil.copy2(pre_backup, self.db_path)
            return False, f"Visszaállítási hiba:\n{e}"

    # ------------------------------------------------------------------
    # Backup lista
    # ------------------------------------------------------------------

    def list_backups(self) -> list[dict]:
        """Visszaadja az elérhető automatikus backupok listáját."""
        backups = []
        for fname in sorted(os.listdir(self.backup_dir), reverse=True):
            if fname.startswith("auto_") and fname.endswith(".db"):
                fpath = os.path.join(self.backup_dir, fname)
                size_kb = os.path.getsize(fpath) // 1024
                date_str = fname.replace("auto_", "").replace(".db", "")
                backups.append({
                    "filename": fname,
                    "path": fpath,
                    "date": date_str,
                    "size_kb": size_kb,
                })
        return backups

    def restore_from_db_backup(self, backup_path: str) -> tuple[bool, str]:
        """Visszaállítás egy adott .db backup fájlból."""
        pre = os.path.join(
            self.backup_dir,
            f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        try:
            shutil.copy2(self.db_path, pre)
            shutil.copy2(backup_path, self.db_path)
            return True, "Visszaállítás sikeres! Az alkalmazás újraindítása szükséges."
        except Exception as e:
            return False, f"Visszaállítási hiba:\n{e}"
