# -*- coding: utf-8 -*-
"""
main.py – WheelBooK
Autó nyilvántartó program.
Funkciók: Tankolás, Karbantartás, Egyéb, Statisztika,
          Sötét mód, Keresés/Szűrés, Backup, Emlékeztetők
"""

import customtkinter as ctk
import sqlite3
import sys
import os
import csv
import shutil
import logging
from tkinter import filedialog, messagebox
from updater import UpdateChecker, CURRENT_VERSION
from ui_components import (InfoCard, DataRow, SearchFilterBar, ReminderPopup,
                           BackupPanel, SettingsPanel, ChangelogPopup,
                           CategoryManagerPanel, UpdatePopup)
from database import init_db
from config import ConfigManager
from backup_manager import BackupManager
from reminder_manager import ReminderManager
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use("TkAgg")
import warnings
warnings.filterwarnings("ignore", message=".*categorical units.*")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# PyInstaller frozen exe esetén Program Files-ba nincs írási jog
# Ezért az adatok a Dokumentumok/WheelBooK mappába kerülnek
if getattr(sys, 'frozen', False):
    # Telepített mód: Dokumentumok/WheelBooK
    EXE_DIR = os.path.dirname(sys.executable)
    DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", "WheelBooK")
else:
    # Fejlesztői mód: a .py fájl melletti adatok mappa
    EXE_DIR = BASE_DIR
    DATA_DIR = os.path.join(BASE_DIR, "adatok")

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "auto_naplo.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "csatolmanyok")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
CHANGELOG_PATH = os.path.join(EXE_DIR, "CHANGELOG.md")

os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class WheelBooK(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager(CONFIG_PATH)
        init_db(DB_PATH)

        # Managerek inicializálása
        self.backup_manager = BackupManager(
            DATA_DIR, DB_PATH,
            backup_keep_days=self.config_manager.get("backup_keep_days", 30)
        )
        self.reminder_manager = ReminderManager(DB_PATH, self.config_manager)
        self.update_checker = UpdateChecker(EXE_DIR, self._on_update_available)

        self.selected_car_id = None
        self.temp_image_path = None
        self._open_popups = set()  # Dupla kattintás védelem
        self._stats_cache_key = None  # Statisztika cache

        # Sötét mód betöltése
        mode = self.config_manager.get("appearance_mode", "light")
        ctk.set_appearance_mode(mode)

        self.title(f"WheelBooK v{CURRENT_VERSION} - Dokumentum Kezelő")
        self.geometry("1200x950")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.configure(fg_color="#f8fafc")

        self.setup_ui()
        self.refresh_cars()

        # Indítás utáni feladatok (rövid késleltetéssel, hogy az UI betöltődjön)
        self.after(800, self._startup_tasks)

    def _startup_tasks(self):
        """Indítás utáni háttérfeladatok: backup + emlékeztetők."""
        # Automatikus backup
        if self.config_manager.get("auto_backup", True):
            self.backup_manager.run_auto_backup()

        # Emlékeztetők ellenőrzése
        reminders = self.reminder_manager.check_all()
        if reminders:
            self.reminder_manager.notify_reminders(reminders)
            ReminderPopup(self, reminders)

        # Changelog megjelenítése ha új verzió
        self.after(200, lambda: ChangelogPopup(self, self.config_manager, CHANGELOG_PATH))

        # Frissítés keresése a háttérben (3mp késleltetéssel, hogy az UI betöltődjön)
        self.after(3000, self.update_checker.check_async)

    def on_closing(self):
        plt.close('all')
        self.quit()
        self.destroy()

    def _on_appearance_change(self, mode: str):
        """Sötét/Világos mód váltásakor frissíti az UI-t."""
        ctk.set_appearance_mode(mode)
        self.configure(fg_color="#1a1a2e" if mode == "dark" else "#f8fafc")
        self.refresh_cars()

    # =========================================================================
    # UI Felépítés
    # =========================================================================

    def setup_ui(self):
        # Fejléc
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=20)
        ctk.CTkLabel(header, text="WheelBooK", font=("Arial", 26, "bold")).pack(side="left")

        # Fejléc gombok (jobbra)
        ctk.CTkButton(header, text="⚙️ Beállítások", fg_color="#64748b", width=130,
                      command=self._open_settings).pack(side="right", padx=5)
        ctk.CTkButton(header, text="🏷️ Kategóriák", fg_color="#64748b", width=120,
                      command=self._open_categories).pack(side="right", padx=5)
        ctk.CTkButton(header, text="💾 Backup", fg_color="#64748b", width=110,
                      command=self._open_backup).pack(side="right", padx=5)
        ctk.CTkButton(header, text="📄 PDF Export", fg_color="#64748b", width=120,
                      command=self.export_to_pdf).pack(side="right", padx=5)
        ctk.CTkButton(header, text="+ Új Jármű", fg_color="#f97316", width=120,
                      command=self.open_car_popup).pack(side="right", padx=5)

        # Jármű lista
        ctk.CTkLabel(self, text="Járművek", font=("Arial", 18, "bold")).pack(anchor="w", padx=30)
        self.car_list_container = ctk.CTkFrame(self, fg_color="transparent")
        self.car_list_container.pack(fill="x", padx=30, pady=(5, 10))

        # Fő tab tartó keret (ebbe kerül a dinamikus tabview)
        self.tab_container = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_container.pack(fill="both", expand=True, padx=20, pady=10)

        self._build_tabs()

    def _build_tabs(self):
        """Felépíti a tab rendszert – az egyedi kategóriákkal együtt. Újrahívható."""
        # Előző tabview törlése
        for w in self.tab_container.winfo_children():
            w.destroy()

        self.tab_lists = {}    # kat -> scrollframe
        self.tab_filters = {}  # kat -> filterbar

        self.tabs = ctk.CTkTabview(self.tab_container,
                                   segmented_button_selected_color="#3b82f6")
        self.tabs.pack(fill="both", expand=True)

        # Alap fülek (Biztosítás saját fület kap)
        for tab_name, kat, import_fn in [
            ("⛽ Tankolások",  "Tankolás",    self.import_fuel),
            ("🔧 Karbantartás","Karbantartás", self.import_maintenance),
            ("📦 Egyéb",       "Egyéb",        self.import_other),
        ]:
            tab = self.tabs.add(tab_name)
            self._setup_tab_content(tab, kat, import_fn)

        # Biztosítás fix fül
        tab_biz = self.tabs.add("🛡️ Biztosítás")
        self._setup_biztositas_tab(tab_biz)

        # Egyedi kategória fülek (Biztosítás kihagyva – már van saját füle)
        with get_db() as conn:
            custom_cats = conn.execute(
                "SELECT nev, ikon FROM kategoriak WHERE alap=0 ORDER BY id ASC"
            ).fetchall()

        for nev, ikon in custom_cats:
            if nev == "Biztosítás":
                continue
            tab_label = f"{ikon} {nev}"
            tab = self.tabs.add(tab_label)
            self._setup_tab_content(tab, nev, None)

        # Statisztika + Éves fülek
        tab_stat = self.tabs.add("📊 Statisztika")
        self.stat_scroll = ctk.CTkScrollableFrame(tab_stat, fg_color="transparent")
        self.stat_scroll.pack(fill="both", expand=True)

        tab_eves = self.tabs.add("📅 Éves összesítő")
        self.eves_scroll = ctk.CTkScrollableFrame(tab_eves, fg_color="transparent")
        self.eves_scroll.pack(fill="both", expand=True)

    def _setup_biztositas_tab(self, tab):
        """Biztosítás fül felépítése."""
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(bar, text="+ Új biztosítás", fg_color="#8b5cf6",
                      command=self.open_biztositas_popup).pack(side="left", padx=5)

        self.biz_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.biz_scroll.pack(fill="both", expand=True)

    def _refresh_biztositas_tab(self):
        if not hasattr(self, "biz_scroll"):
            return
        for w in self.biz_scroll.winfo_children():
            w.destroy()

        if not self.selected_car_id:
            return

        with get_db() as conn:
            rows = conn.execute("""
                SELECT id, datum, biztosito, kezdete, vege, osszeg, megjegyzes, kep_utvonal
                FROM biztositas WHERE auto_id=? ORDER BY vege DESC
            """, (self.selected_car_id,)).fetchall()

        if not rows:
            ctk.CTkLabel(self.biz_scroll, text="Nincs biztosítási bejegyzés.",
                         text_color="gray", font=("Arial", 13)).pack(pady=30)
            return

        today = datetime.now().date()
        for row in rows:
            rid, datum, biztosito, kezdete, vege, osszeg, megj, kep = row

            # Lejárat státusz
            try:
                vege_date = datetime.strptime(vege, "%Y.%m.%d").date()
                napok = (vege_date - today).days
                if napok < 0:
                    statuscolor = "#ef4444"
                    status = f"⚠️ Lejárt {abs(napok)} napja"
                elif napok <= 30:
                    statuscolor = "#f97316"
                    status = f"⚠️ {napok} nap múlva jár le"
                else:
                    statuscolor = "#10b981"
                    status = f"✅ Érvényes ({napok} nap)"
            except Exception:
                statuscolor = "#64748b"
                status = "Ismeretlen lejárat"

            card = ctk.CTkFrame(self.biz_scroll, fg_color="white",
                                corner_radius=10, border_width=1, border_color="#e2e8f0")
            card.pack(fill="x", padx=10, pady=5)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 4))

            ctk.CTkLabel(top, text=f"🛡️ {biztosito or 'Ismeretlen biztosító'}",
                         font=("Arial", 14, "bold")).pack(side="left")
            ctk.CTkLabel(top, text=f"{osszeg:,.0f} Ft".replace(",", " "),
                         font=("Arial", 14, "bold"),
                         text_color="#8b5cf6").pack(side="right")

            mid = ctk.CTkFrame(card, fg_color="transparent")
            mid.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(mid, text=f"📅 {kezdete or '?'} → {vege or '?'}",
                         font=("Arial", 12)).pack(side="left")
            ctk.CTkLabel(mid, text=status, font=("Arial", 11),
                         text_color=statuscolor).pack(side="right")

            if megj:
                ctk.CTkLabel(card, text=f"💬 {megj}", font=("Arial", 11),
                             text_color="gray").pack(anchor="w", padx=12, pady=(0, 4))

            btn_f = ctk.CTkFrame(card, fg_color="transparent")
            btn_f.pack(anchor="e", padx=12, pady=(0, 8))

            if kep:
                full_path = os.path.join(UPLOAD_DIR, os.path.basename(kep))
                ctk.CTkButton(btn_f, text="📷", width=30, height=28,
                              fg_color="#f1f5f9", text_color="#10b981",
                              command=lambda p=full_path: self._open_file(p)).pack(side="left", padx=2)

            ctk.CTkButton(btn_f, text="📝", width=30, height=28,
                          fg_color="#f1f5f9", text_color="#3b82f6",
                          command=lambda i=rid: self._edit_biztositas(i)).pack(side="left", padx=2)
            ctk.CTkButton(btn_f, text="🗑", width=30, height=28,
                          fg_color="#f1f5f9", text_color="#ef4444",
                          command=lambda i=rid: self._delete_biztositas(i)).pack(side="left", padx=2)

    def _edit_biztositas(self, eid: int):
        with get_db() as conn:
            r = conn.execute(
                "SELECT datum, osszeg, biztosito, kezdete, vege, megjegyzes FROM biztositas WHERE id=?",
                (eid,)
            ).fetchone()
        if not r:
            return
        prefill = {"datum": r[0], "osszeg": r[1], "biztosito": r[2],
                   "kezdete": r[3], "vege": r[4], "megj": r[5]}
        self.open_biztositas_popup(eid=eid, prefill=prefill)

    def _delete_biztositas(self, eid: int):
        if not messagebox.askyesno("Törlés", "Biztosan törlöd ezt a biztosítási bejegyzést?"):
            return
        with get_db() as conn:
            conn.execute("DELETE FROM biztositas WHERE id=?", (eid,))
        self.refresh_data()

    def _setup_tab_content(self, tab, kat: str, import_cmd):
        """Egy fül tartalmának felépítése (lista + szűrő + gombok)."""
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(bar, text=f"+ Új bejegyzés", fg_color="#10b981",
                      command=lambda k=kat: self.open_entry_popup(k)).pack(side="left", padx=5)
        if import_cmd:
            ctk.CTkButton(bar, text="📂 Import CSV", fg_color="#64748b",
                          command=import_cmd).pack(side="left", padx=5)

        filter_bar = SearchFilterBar(
            tab, on_change_callback=lambda f, k=kat: self._refresh_tab(k))
        filter_bar.pack(fill="x", padx=10, pady=(0, 5))

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self.tab_lists[kat] = scroll
        self.tab_filters[kat] = filter_bar

    def _on_filter_change(self, kat: str, filters: dict):
        self._refresh_tab(kat)

    def _open_settings(self):
        SettingsPanel(self, self.config_manager, on_appearance_change=self._on_appearance_change)

    def _open_categories(self):
        CategoryManagerPanel(self, DB_PATH, on_change_callback=self._rebuild_tabs_and_refresh)

    def _open_backup(self):
        BackupPanel(self, self.backup_manager, restart_callback=self._restart)

    def _restart(self):
        """Backup visszaállítás után újraindítás szükséges."""
        messagebox.showinfo(
            "Újraindítás szükséges",
            "A visszaállítás sikeres!\n\nKérd zárd be és nyisd meg újra a WheelBooK-ot\na változások érvénybe lépéséhez."
        )
        self.on_closing()

    def _on_update_available(self, latest_version: str, changelog: str):
        """Háttérszálból hívódik – tkinter after()-rel vissza a UI szálra."""
        self.after(0, lambda: UpdatePopup(
            self, latest_version, changelog,
            install_callback=self._do_install
        ))

    def _do_install(self):
        """Letölti és telepíti a frissítést, majd értesíti a felhasználót."""
        # Haladásjelző popup
        prog = ctk.CTkToplevel(self)
        prog.title("Frissítés folyamatban...")
        prog.geometry("360x140")
        prog.attributes("-topmost", True)
        prog.grab_set()
        prog.resizable(False, False)
        ctk.CTkLabel(prog, text="⬇️  Frissítés letöltése...",
                     font=("Arial", 14, "bold")).pack(pady=(25, 10))
        bar = ctk.CTkProgressBar(prog, width=300)
        bar.pack()
        bar.set(0)
        prog.update()

        def run():
            def progress(pct):
                self.after(0, lambda p=pct: bar.set(p / 100))
            ok, msg = self.update_checker.download_and_install(progress_callback=progress)
            self.after(0, lambda: _done(ok, msg))

        def _done(ok: bool, msg: str):
            prog.destroy()
            if ok:
                messagebox.showinfo(
                    "✅ Frissítés kész",
                    f"{msg}\n\nZárd be és nyisd meg újra a WheelBooK-ot!"
                )
            else:
                messagebox.showerror("❌ Frissítési hiba", msg)

        import threading
        threading.Thread(target=run, daemon=True).start()

    def _rebuild_tabs_and_refresh(self):
        """Kategória változáskor újraépíti a tabokat és frissíti az adatokat."""
        self._build_tabs()
        self.refresh_data()

    # =========================================================================
    # Adatok frissítése
    # =========================================================================

    def refresh_cars(self):
        for w in self.car_list_container.winfo_children():
            w.destroy()

        with get_db() as conn:
            cars = conn.execute(
                "SELECT id, marka, tipus, evjarat, km_allas, vin, rendszam, muszaki_lejarat, olaj_intervallum, COALESCE(ikon,'🚗') FROM autok"
            ).fetchall()

        if not self.selected_car_id and cars:
            self.selected_car_id = cars[0][0]

        for c in cars:
            InfoCard(self.car_list_container, c,
                     self.select_car, self.open_car_popup, self.delete_car,
                     active=(c[0] == self.selected_car_id)).pack(side="left", padx=10)

        self.refresh_data()

    def select_car(self, cid):
        self.selected_car_id = cid
        self.refresh_cars()

    def refresh_data(self):
        if not self.selected_car_id:
            return
        for kat in list(self.tab_lists.keys()):
            self._refresh_tab(kat)
        self._refresh_biztositas_tab()
        self.update_statistics()
        self.update_yearly_stats()

    def _refresh_tab(self, kat: str):
        if not self.selected_car_id:
            return
        if kat not in self.tab_lists:
            return

        lst = self.tab_lists[kat]
        fbar = self.tab_filters[kat]

        for w in lst.winfo_children():
            w.destroy()

        with get_db() as conn:
            data = conn.execute("""
                SELECT id, datum, osszeg, km_allas, kategoria,
                       mennyiseg_liter, egysegar_ft_l, benzinkut, megjegyzes, kep_utvonal
                FROM szerviz_adatok
                WHERE auto_id=? AND kategoria=?
                ORDER BY datum DESC
            """, (self.selected_car_id, kat)).fetchall()

        data = fbar.apply_filters(data)

        if not data:
            ctk.CTkLabel(lst, text="Nincs megjeleníthető bejegyzés.",
                         text_color="gray", font=("Arial", 13)).pack(pady=30)
        else:
            for r in data:
                DataRow(lst, r[0], r[1], r[2], r[3], r[4],
                        self.delete_entry, self.open_edit_popup,
                        copy_callback=self.copy_entry,
                        liter=r[5], ar_l=r[6], kut=r[7], note=r[8],
                        image_path=r[9] or "")

    # =========================================================================
    # Statisztika
    # =========================================================================

    def update_statistics(self):
        for w in self.stat_scroll.winfo_children():
            w.destroy()
        plt.close('all')
        if not self.selected_car_id:
            return

        with get_db() as conn:
            c = conn.cursor()
            car = c.execute(
                "SELECT km_allas, muszaki_lejarat, olaj_intervallum FROM autok WHERE id=?",
                (self.selected_car_id,)
            ).fetchone()
            curr_km = car[0] or 0
            vizsga = car[1] or "---"
            intervallum = car[2] or 10000

            last_oil = c.execute("""
                SELECT km_allas FROM szerviz_adatok
                WHERE auto_id=? AND kategoria='Karbantartás'
                AND (megjegyzes LIKE '%olaj%' OR megjegyzes LIKE '%Oil%' OR megjegyzes LIKE '%OLAJ%')
                ORDER BY km_allas DESC LIMIT 1
            """, (self.selected_car_id,)).fetchone()

            t_data = c.execute("""
                SELECT datum, osszeg, mennyiseg_liter, km_allas FROM szerviz_adatok
                WHERE auto_id=? AND kategoria='Tankolás' ORDER BY km_allas ASC
            """, (self.selected_car_id,)).fetchall()

            szerv = c.execute("""
                SELECT SUM(osszeg), COUNT(id) FROM szerviz_adatok
                WHERE auto_id=? AND kategoria='Karbantartás'
            """, (self.selected_car_id,)).fetchone()

            egyeb = c.execute("""
                SELECT SUM(osszeg), COUNT(id) FROM szerviz_adatok
                WHERE auto_id=? AND kategoria='Egyéb'
            """, (self.selected_car_id,)).fetchone()

        # Emlékeztetők panel
        reminders = self.reminder_manager.check_all()
        car_reminders = [r for r in reminders if r["auto"] in
                         self._get_car_name(self.selected_car_id)]

        rem_f = ctk.CTkFrame(self.stat_scroll, fg_color="#fff1f2",
                              border_width=1, border_color="#f43f5e")
        rem_f.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkLabel(rem_f, text="🔔 Szerviz emlékeztetők",
                     font=("Arial", 14, "bold"), text_color="#e11d48").pack(anchor="w", padx=15, pady=5)

        # Olajcsere sor
        oil_row = ctk.CTkFrame(rem_f, fg_color="transparent")
        oil_row.pack(fill="x", padx=25, pady=(0, 5))

        oil_txt = "Nincs adat az utolsó olajcseréről."
        oil_clr = "#64748b"
        show_oil_btn = False
        if last_oil:
            diff = curr_km - last_oil[0]
            rem_km = intervallum - diff
            if rem_km <= 0:
                oil_txt = f"🔴 OLAJCSERE ESEDÉKES! ({diff} km telt el, {abs(rem_km)} km-rel túllépve)"
                oil_clr = "#e11d48"
                show_oil_btn = True
            elif rem_km <= self.config_manager.get("oil_warning_km", 1000):
                oil_txt = f"🟡 Olajcsere közelgő: még {rem_km} km ({diff} km telt el)"
                oil_clr = "#f59e0b"
                show_oil_btn = True
            else:
                oil_txt = f"✅ Olajcsere: {diff} km telt el. Még {rem_km} km van hátra."
        else:
            show_oil_btn = True  # Ha nincs adat, szintén fel lehet venni

        ctk.CTkLabel(oil_row, text=f"• {oil_txt}", text_color=oil_clr).pack(side="left")

        if show_oil_btn:
            ctk.CTkButton(
                oil_row, text="✅ Olajcsere elvégezve",
                width=180, height=28,
                fg_color="#10b981", hover_color="#059669",
                font=("Arial", 12),
                command=lambda km=curr_km: self._mark_oil_change_done(km)
            ).pack(side="right", padx=(10, 0))

        # Műszaki vizsga sor
        ctk.CTkLabel(rem_f, text=f"• Műszaki vizsga lejárata: {vizsga}").pack(anchor="w", padx=25, pady=(0, 5))

        # Biztosítási emlékeztető
        with get_db() as conn:
            biz_row = conn.execute("""
                SELECT biztosito, vege FROM biztositas
                WHERE auto_id=? AND vege IS NOT NULL
                ORDER BY vege DESC LIMIT 1
            """, (self.selected_car_id,)).fetchone()

        if biz_row:
            biztosito, vege_str = biz_row
            try:
                vege_date = datetime.strptime(vege_str, "%Y.%m.%d").date()
                napok = (vege_date - datetime.now().date()).days
                if napok < 0:
                    biz_txt = f"🔴 BIZTOSÍTÁS LEJÁRT! ({abs(napok)} napja) – {biztosito or ''}"
                    biz_clr = "#e11d48"
                elif napok <= 30:
                    biz_txt = f"🟡 Biztosítás hamarosan lejár: {napok} nap múlva ({vege_str}) – {biztosito or ''}"
                    biz_clr = "#f59e0b"
                else:
                    biz_txt = f"✅ Biztosítás érvényes: {vege_str}-ig ({napok} nap) – {biztosito or ''}"
                    biz_clr = "#10b981"
            except Exception:
                biz_txt = f"• Biztosítás lejárata: {vege_str}"
                biz_clr = "#64748b"
        else:
            biz_txt = "Nincs biztosítási adat rögzítve."
            biz_clr = "#64748b"

        ctk.CTkLabel(rem_f, text=f"• {biz_txt}",
                     text_color=biz_clr).pack(anchor="w", padx=25, pady=(0, 10))

        # Statisztika kártyák
        tank_sum = sum(r[1] for r in t_data)
        liter_sum = sum(r[2] for r in t_data if r[2])
        full_sum = tank_sum + (szerv[0] or 0) + (egyeb[0] or 0)

        avg_cons = 0
        cons_hist = []
        if len(t_data) > 1:
            for i in range(1, len(t_data)):
                d = t_data[i][3] - t_data[i - 1][3]
                if d > 0 and t_data[i][2]:
                    cons_hist.append((t_data[i][0], (t_data[i][2] / d) * 100))
            dist = t_data[-1][3] - t_data[0][3]
            if dist > 0:
                avg_cons = (sum(r[2] for r in t_data[1:] if r[2]) / dist) * 100

        card_f = ctk.CTkFrame(self.stat_scroll, fg_color="transparent")
        card_f.pack(fill="x", padx=10)
        card_f.grid_columnconfigure((0, 1, 2), weight=1)

        st_list = [
            ("Összköltség", f"{full_sum:,.0f} Ft".replace(',', ' '), "Összesen"),
            ("Tankolás", f"{tank_sum:,.0f} Ft".replace(',', ' '), f"{len(t_data)} alkalom"),
            ("Karbantartás", f"{(szerv[0] or 0):,.0f} Ft".replace(',', ' '), f"{szerv[1]} tétel"),
            ("Egyéb", f"{(egyeb[0] or 0):,.0f} Ft".replace(',', ' '), f"{egyeb[1]} tétel"),
            ("Fogyasztás", f"{avg_cons:.2f} L/100", "Átlag"),
            ("Üzemanyag", f"{liter_sum:.1f} L", "Összesen"),
        ]
        for i, (t, v, d) in enumerate(st_list):
            card = ctk.CTkFrame(card_f, fg_color="white", corner_radius=12,
                                border_width=1, border_color="#e2e8f0")
            card.grid(row=i // 3, column=i % 3, padx=10, pady=10, sticky="nsew")
            ctk.CTkLabel(card, text=t, font=("Arial", 11)).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=v, font=("Arial", 16, "bold")).pack()
            ctk.CTkLabel(card, text=d, font=("Arial", 10), text_color="gray").pack(pady=(0, 10))

        if t_data:
            self.plot_graph("Költség alakulása", [r[0] for r in t_data], [r[1] for r in t_data], "#3b82f6")
            if cons_hist:
                self.plot_graph("Fogyasztás alakulása",
                                [r[0] for r in cons_hist], [r[1] for r in cons_hist], "#10b981")

    def _mark_oil_change_done(self, curr_km: int):
        """
        Mini popup az olajcsere rögzítéséhez.
        Karbantartás bejegyzést hoz létre 'olaj' kulcsszóval,
        ettől kezdve a periódus újraindul.
        """
        pop = ctk.CTkToplevel(self)
        pop.title("Olajcsere rögzítése")
        pop.geometry("380x320")
        pop.attributes("-topmost", True)
        pop.grab_set()
        pop.resizable(False, False)

        ctk.CTkLabel(pop, text="Olajcsere elvégezve",
                     font=("Arial", 16, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(pop, text="Ellenőrizd vagy módosítsd az adatokat:",
                     text_color="gray").pack()

        form = ctk.CTkFrame(pop, fg_color="transparent")
        form.pack(pady=15, padx=30, fill="x")

        ctk.CTkLabel(form, text="Dátum:").grid(row=0, column=0, sticky="w", pady=5)
        e_datum = ctk.CTkEntry(form, width=200)
        e_datum.insert(0, datetime.now().strftime("%Y.%m.%d"))
        e_datum.grid(row=0, column=1, padx=10, pady=5)

        ctk.CTkLabel(form, text="KM állás:").grid(row=1, column=0, sticky="w", pady=5)
        e_km = ctk.CTkEntry(form, width=200)
        e_km.insert(0, str(curr_km) if curr_km else "")
        e_km.grid(row=1, column=1, padx=10, pady=5)

        ctk.CTkLabel(form, text="Összeg (Ft):").grid(row=2, column=0, sticky="w", pady=5)
        e_osszeg = ctk.CTkEntry(form, width=200, placeholder_text="opcionális")
        e_osszeg.grid(row=2, column=1, padx=10, pady=5)

        ctk.CTkLabel(form, text="Megjegyzés:").grid(row=3, column=0, sticky="w", pady=5)
        e_megj = ctk.CTkEntry(form, width=200)
        e_megj.insert(0, "Olajcsere elvégezve")
        e_megj.grid(row=3, column=1, padx=10, pady=5)

        def confirm():
            try:
                km_val = int(e_km.get()) if e_km.get().strip() else None
                osszeg_val = float(e_osszeg.get().replace(" ", "")) if e_osszeg.get().strip() else 0.0
                datum_val = e_datum.get().strip()
                megj_val = e_megj.get().strip() or "Olajcsere elvégezve"

                with get_db() as conn:
                    conn.execute("""
                        INSERT INTO szerviz_adatok
                        (auto_id, datum, km_allas, osszeg, megjegyzes, kategoria, kep_utvonal)
                        VALUES (?,?,?,?,?, 'Karbantartás', '')
                    """, (self.selected_car_id, datum_val, km_val, osszeg_val, megj_val))
                    if km_val:
                        conn.execute("""
                            UPDATE autok SET km_allas = ?
                            WHERE id = ? AND (km_allas IS NULL OR km_allas < ?)
                        """, (km_val, self.selected_car_id, km_val))

                pop.destroy()
                self.refresh_data()
                self.tabs.set("🔧 Karbantartás")
            except ValueError as e:
                messagebox.showerror("Hiba", f"Érvénytelen adat:\n{e}", parent=pop)

        btn_f = ctk.CTkFrame(pop, fg_color="transparent")
        btn_f.pack(pady=10)
        ctk.CTkButton(btn_f, text="Rögzítés", fg_color="#10b981",
                      command=confirm).pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="Mégsem", fg_color="#64748b",
                      command=pop.destroy).pack(side="left", padx=10)

    def update_yearly_stats(self):
        """Éves összesítő fül frissítése: évenként bontva költségek + havi km előrejelzés."""
        for w in self.eves_scroll.winfo_children():
            w.destroy()
        if not self.selected_car_id:
            return

        with get_db() as conn:
            # Összes bejegyzés évek szerint csoportosítva
            rows = conn.execute("""
                SELECT substr(datum, 1, 4) as ev,
                       kategoria,
                       SUM(osszeg) as osszeg,
                       COUNT(id) as db
                FROM szerviz_adatok
                WHERE auto_id=?
                GROUP BY ev, kategoria
                ORDER BY ev DESC
            """, (self.selected_car_id,)).fetchall()

            # Havi km adatok az előrejelzéshez
            km_rows = conn.execute("""
                SELECT datum, km_allas FROM szerviz_adatok
                WHERE auto_id=? AND km_allas IS NOT NULL
                ORDER BY datum ASC
            """, (self.selected_car_id,)).fetchall()

        if not rows:
            ctk.CTkLabel(self.eves_scroll, text="Még nincs elegendő adat.",
                         text_color="gray", font=("Arial", 13)).pack(pady=30)
            return

        # Éves adatok összegyűjtése
        from collections import defaultdict
        ev_data = defaultdict(lambda: {"Tankolás": 0, "Karbantartás": 0, "Egyéb": 0, "db": 0})
        for ev, kat, osszeg, db in rows:
            ev_data[ev][kat] += osszeg or 0
            ev_data[ev]["db"] += db

        # Cím
        ctk.CTkLabel(self.eves_scroll, text="Éves összesítő",
                     font=("Arial", 16, "bold")).pack(anchor="w", padx=15, pady=(10, 5))

        # Éves kártyák
        for ev in sorted(ev_data.keys(), reverse=True):
            d = ev_data[ev]
            total = d["Tankolás"] + d["Karbantartás"] + d["Egyéb"]

            ev_frame = ctk.CTkFrame(self.eves_scroll, fg_color="white",
                                    corner_radius=12, border_width=1, border_color="#e2e8f0")
            ev_frame.pack(fill="x", padx=15, pady=6)

            # Fejléc sor
            header = ctk.CTkFrame(ev_frame, fg_color="#3b82f6", corner_radius=8)
            header.pack(fill="x", padx=8, pady=8)
            ctk.CTkLabel(header, text=f"  {ev}  –  Összesen: {total:,.0f} Ft".replace(",", " "),
                         font=("Arial", 13, "bold"), text_color="white").pack(side="left", padx=10, pady=5)
            ctk.CTkLabel(header, text=f"{d['db']} bejegyzés  ",
                         font=("Arial", 11), text_color="#bfdbfe").pack(side="right", pady=5)

            # Bontás sor
            bont = ctk.CTkFrame(ev_frame, fg_color="transparent")
            bont.pack(fill="x", padx=15, pady=(0, 10))
            bont.grid_columnconfigure((0, 1, 2), weight=1)

            for col, (label, key, color) in enumerate([
                ("⛽ Tankolás", "Tankolás", "#3b82f6"),
                ("🔧 Karbantartás", "Karbantartás", "#10b981"),
                ("📦 Egyéb", "Egyéb", "#f97316"),
            ]):
                cell = ctk.CTkFrame(bont, fg_color="#f8fafc", corner_radius=8)
                cell.grid(row=0, column=col, padx=5, pady=5, sticky="ew")
                ctk.CTkLabel(cell, text=label, font=("Arial", 10),
                             text_color="gray").pack(pady=(6, 0))
                ctk.CTkLabel(cell, text=f"{d[key]:,.0f} Ft".replace(",", " "),
                             font=("Arial", 13, "bold"), text_color=color).pack(pady=(0, 6))

        # Havi km előrejelzés
        if len(km_rows) >= 2:
            ctk.CTkLabel(self.eves_scroll, text="Havi átlag és előrejelzés",
                         font=("Arial", 16, "bold")).pack(anchor="w", padx=15, pady=(20, 5))

            try:
                from datetime import datetime as dt
                elso_datum = dt.strptime(km_rows[0][0][:10].replace(".", "-"), "%Y-%m-%d")
                utolso_datum = dt.strptime(km_rows[-1][0][:10].replace(".", "-"), "%Y-%m-%d")
                elso_km = km_rows[0][1]
                utolso_km = km_rows[-1][1]

                napok = (utolso_datum - elso_datum).days
                ossz_km = utolso_km - elso_km

                if napok > 0 and ossz_km > 0:
                    havi_km = (ossz_km / napok) * 30
                    eves_km = havi_km * 12

                    pred_frame = ctk.CTkFrame(self.eves_scroll, fg_color="white",
                                              corner_radius=12, border_width=1, border_color="#e2e8f0")
                    pred_frame.pack(fill="x", padx=15, pady=6)
                    pred_frame.grid_columnconfigure((0, 1, 2), weight=1)

                    for col, (label, value, sub) in enumerate([
                        ("Havi átlag", f"{havi_km:,.0f} km".replace(",", " "), f"{napok} nap alapján"),
                        ("Éves előrejelzés", f"{eves_km:,.0f} km".replace(",", " "), "becsült"),
                        ("Összes mért", f"{ossz_km:,.0f} km".replace(",", " "), f"{km_rows[0][0]} óta"),
                    ]):
                        cell = ctk.CTkFrame(pred_frame, fg_color="transparent")
                        cell.grid(row=0, column=col, padx=10, pady=15, sticky="ew")
                        ctk.CTkLabel(cell, text=label, font=("Arial", 11),
                                     text_color="gray").pack()
                        ctk.CTkLabel(cell, text=value,
                                     font=("Arial", 15, "bold")).pack()
                        ctk.CTkLabel(cell, text=sub, font=("Arial", 10),
                                     text_color="gray").pack()

                    # Következő szerviz előrejelzés
                    with get_db() as conn:
                        car = conn.execute(
                            "SELECT km_allas, olaj_intervallum FROM autok WHERE id=?",
                            (self.selected_car_id,)
                        ).fetchone()
                        last_oil = conn.execute("""
                            SELECT km_allas FROM szerviz_adatok
                            WHERE auto_id=? AND kategoria='Karbantartás'
                            AND (megjegyzes LIKE '%olaj%' OR megjegyzes LIKE '%OLAJ%')
                            ORDER BY km_allas DESC LIMIT 1
                        """, (self.selected_car_id,)).fetchone()

                    if car and last_oil and havi_km > 0:
                        curr_km = car[0] or 0
                        intervallum = car[1] or 10000
                        hatra = intervallum - (curr_km - last_oil[0])
                        if hatra > 0:
                            honapok = hatra / havi_km
                            import math
                            ho = int(math.floor(honapok))
                            nap = int((honapok - ho) * 30)
                            elore = ctk.CTkFrame(self.eves_scroll, fg_color="#f0fdf4",
                                                 corner_radius=10, border_width=1,
                                                 border_color="#86efac")
                            elore.pack(fill="x", padx=15, pady=6)
                            ctk.CTkLabel(elore,
                                         text=f"🔧 Következő olajcsere várható: kb. {ho} hónap {nap} nap múlva  ({hatra:,.0f} km hátra)".replace(",", " "),
                                         font=("Arial", 12)).pack(padx=15, pady=10)
            except Exception as e:
                logger.warning(f"Előrejelzés hiba: {e}")

    def _get_car_name(self, cid) -> str:
        with get_db() as conn:
            r = conn.execute("SELECT marka, tipus FROM autok WHERE id=?", (cid,)).fetchone()
        return f"{r[0]} {r[1]}" if r else ""

    def plot_graph(self, title, x, y, color):
        fig, ax = plt.subplots(figsize=(10, 2.5), dpi=90)
        mode = self.config_manager.get("appearance_mode", "light")
        bg = "#1a1a2e" if mode == "dark" else "#f8fafc"
        fig.patch.set_facecolor(bg)
        ax.set_facecolor(bg)
        ax.plot(x, y, marker='o', color=color, linewidth=2)
        ax.set_title(title, fontsize=10, fontweight='bold',
                     color="white" if mode == "dark" else "black")
        ax.tick_params(colors="white" if mode == "dark" else "black")
        plt.xticks(rotation=20, fontsize=8)
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.stat_scroll)
        canvas.get_tk_widget().pack(pady=10, fill="x")

    # =========================================================================
    # PDF Export
    # =========================================================================

    def export_to_pdf(self):
        if not self.selected_car_id:
            messagebox.showwarning("Hiba", "Nincs kiválasztott jármű!")
            return

        with get_db() as conn:
            car = conn.execute(
                "SELECT marka, tipus, rendszam, vin, evjarat, km_allas FROM autok WHERE id=?",
                (self.selected_car_id,)
            ).fetchone()
            records = conn.execute("""
                SELECT datum, kategoria, osszeg, km_allas, megjegyzes
                FROM szerviz_adatok WHERE auto_id=? ORDER BY datum DESC
            """, (self.selected_car_id,)).fetchall()
            total = conn.execute(
                "SELECT SUM(osszeg) FROM szerviz_adatok WHERE auto_id=?",
                (self.selected_car_id,)
            ).fetchone()[0] or 0

        pdf = FPDF()
        font_path = "C:\\Windows\\Fonts\\arial.ttf"
        font_path_bold = "C:\\Windows\\Fonts\\arialbd.ttf"
        if os.path.exists(font_path):
            pdf.add_font("MagyarArial", "", font_path)
            pdf.add_font("MagyarArial", "B", font_path_bold)
            base_font = "MagyarArial"
        else:
            base_font = "Helvetica"

        pdf.add_page()
        pdf.set_font(base_font, "B", 16)
        pdf.cell(0, 10, f"WheelBooK - Jármű Napló: {car[0]} {car[1]}",
                 align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font(base_font, "", 10)
        pdf.cell(0, 10, f"Generálva: {datetime.now().strftime('%Y.%m.%d %H:%M')}",
                 align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(5)

        pdf.set_fill_color(245, 245, 245)
        pdf.set_font(base_font, "B", 12)
        pdf.cell(0, 10, " Jármű Adatok", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font(base_font, "", 11)
        pdf.cell(95, 8, f" Rendszám: {car[2]}", border='B')
        pdf.cell(95, 8, f" Alvázszám: {car[3] or '---'}", border='B',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        car_km = car[5] if car[5] is not None else 0
        pdf.cell(95, 8, f" Évjárat: {car[4]}", border='B')
        pdf.cell(95, 8, f" Futásteljesítmény: {car_km:,} km".replace(',', ' '), border='B',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 8, f" Összes ráfordítás: {total:,.0f} Ft".replace(',', ' '), border='B',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(10)

        pdf.set_font(base_font, "B", 10)
        pdf.set_fill_color(59, 130, 246)
        pdf.set_text_color(255, 255, 255)
        for header, width in [("Dátum", 30), ("Kategória", 35), ("KM állás", 30),
                               ("Összeg", 35), ("Megjegyzés", 60)]:
            is_last = header == "Megjegyzés"
            pdf.cell(width, 10, header, border=1, align='C', fill=True,
                     new_x=XPos.LMARGIN if is_last else XPos.RIGHT,
                     new_y=YPos.NEXT if is_last else YPos.TOP)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font(base_font, "", 9)
        for i, r in enumerate(records):
            pdf.set_fill_color(248, 250, 252) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            datum, kat = str(r[0]), str(r[1])
            osszeg_val, km_val, megj = r[2] or 0, r[3] or 0, str(r[4] or "")
            amt_str = f"{int(osszeg_val):,} Ft".replace(",", " ")
            km_str = f"{int(km_val):,} km".replace(',', ' ')
            note_short = megj[:35] + "..." if len(megj) > 35 else megj

            pdf.cell(30, 8, datum, border=1, align='C', fill=True)
            pdf.cell(35, 8, kat, border=1, align='C', fill=True)
            pdf.cell(30, 8, km_str, border=1, align='R', fill=True)
            pdf.cell(35, 8, amt_str, border=1, align='R', fill=True)
            pdf.cell(60, 8, note_short, border=1, align='L', fill=True,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"WheelBooK_{car[2]}.pdf",
            filetypes=[("PDF fájl", "*.pdf")]
        )
        if file_path:
            try:
                pdf.output(file_path)
                messagebox.showinfo("Siker", "A PDF exportálása sikeres volt!")
            except Exception as e:
                messagebox.showerror("Hiba", f"PDF mentési hiba:\n{e}")

    # =========================================================================
    # Jármű popup
    # =========================================================================

    def open_car_popup(self, cid=None):
        # Ikon választó opciók
        IKON_LISTA = [
            "🚗", "🚙", "🏎️", "🚕", "🚐", "🚌", "🚑", "🚒",
            "🛻", "🚚", "🏍️", "🛵", "⚡", "🔋",
        ]

        pop = ctk.CTkToplevel(self)
        pop.title("Jármű szerkesztése" if cid else "Új jármű")
        pop.geometry("420x700")
        pop.attributes("-topmost", True)
        pop.grab_set()

        keys   = ["marka", "tipus", "rendszam", "evjarat", "km_allas",
                  "muszaki_lejarat", "olaj_intervallum"]
        labels = ["Márka", "Típus", "Rendszám", "Évjárat", "Aktuális KM",
                  "Műszaki lejárata (ÉÉÉÉ.HH.NN)", "Olajcsere periódus (km)"]
        entries = {}

        for i, k in enumerate(keys):
            ctk.CTkLabel(pop, text=labels[i]).pack()
            e = ctk.CTkEntry(pop, width=280)
            e.pack(pady=(0, 3))
            entries[k] = e

        # Ikon választó
        ctk.CTkLabel(pop, text="Jármű ikon").pack(pady=(8, 2))
        ikon_var = ctk.StringVar(value="🚗")

        ikon_frame = ctk.CTkFrame(pop, fg_color="transparent")
        ikon_frame.pack()
        ikon_buttons = {}

        def select_ikon(ikon):
            ikon_var.set(ikon)
            for ico, btn in ikon_buttons.items():
                btn.configure(fg_color="#3b82f6" if ico == ikon else "#f1f5f9",
                              text_color="white"   if ico == ikon else "black")

        for idx, ikon in enumerate(IKON_LISTA):
            btn = ctk.CTkButton(ikon_frame, text=ikon, width=42, height=42,
                                fg_color="#f1f5f9", text_color="black",
                                font=("Arial", 20),
                                command=lambda ic=ikon: select_ikon(ic))
            btn.grid(row=idx // 7, column=idx % 7, padx=3, pady=3)
            ikon_buttons[ikon] = btn

        if cid:
            with get_db() as conn:
                r = conn.execute(
                    "SELECT marka, tipus, rendszam, evjarat, km_allas, muszaki_lejarat, olaj_intervallum, COALESCE(ikon,'🚗') FROM autok WHERE id=?",
                    (cid,)
                ).fetchone()
            for i, k in enumerate(keys):
                entries[k].insert(0, str(r[i]) if r[i] is not None else "")
            select_ikon(r[7])
        else:
            entries["olaj_intervallum"].insert(0,
                str(self.config_manager.get("default_oil_interval", 10000)))
            select_ikon("🚗")

        def save():
            v = [entries[k].get().strip() for k in keys]
            if not v[0] or not v[1]:
                messagebox.showwarning("Hiányzó adat", "Márka és Típus megadása kötelező!", parent=pop)
                return
            try:
                with get_db() as conn:
                    if cid:
                        conn.execute(
                            "UPDATE autok SET marka=?, tipus=?, rendszam=?, evjarat=?, km_allas=?, muszaki_lejarat=?, olaj_intervallum=?, ikon=? WHERE id=?",
                            (*v, ikon_var.get(), cid)
                        )
                    else:
                        conn.execute(
                            "INSERT INTO autok (marka, tipus, rendszam, evjarat, km_allas, muszaki_lejarat, olaj_intervallum, ikon) VALUES (?,?,?,?,?,?,?,?)",
                            (*v, ikon_var.get())
                        )
                self.refresh_cars()
                pop.destroy()
            except Exception as e:
                messagebox.showerror("Hiba", f"Mentési hiba:\n{e}", parent=pop)

        ctk.CTkButton(pop, text="Mentés", command=save, fg_color="#f97316").pack(pady=15)

    # =========================================================================
    # Bejegyzés popup – Új (kategória szerint eltérő mezők)
    # =========================================================================

    def open_entry_popup(self, kat, prefill: dict = None):
        """Új bejegyzés popup – kategória szerint eltérő mezőkkel."""
        if not self.selected_car_id:
            messagebox.showwarning("Hiba", "Először válassz ki egy járművet!")
            return

        # Biztosítás saját popupot kap
        if kat == "Biztosítás":
            self.open_biztositas_popup(prefill=prefill)
            return

        self.temp_image_path = None
        pop = ctk.CTkToplevel(self)
        pop.title(f"Új {kat}")
        pop.attributes("-topmost", True)
        pop.grab_set()

        def _field(label, val=""):
            ctk.CTkLabel(pop, text=label).pack()
            e = ctk.CTkEntry(pop, width=280)
            e.pack(pady=(0, 4))
            if val:
                e.insert(0, str(val))
            return e

        def _auto_fmt(event, entry):
            val = entry.get().replace(".", "").replace("-", "").strip()
            if len(val) == 8 and val.isdigit():
                entry.delete(0, "end")
                entry.insert(0, f"{val[:4]}.{val[4:6]}.{val[6:]}")

        e_datum = _field("Dátum (ÉÉÉÉ.HH.NN)",
                         prefill.get("datum", datetime.now().strftime("%Y.%m.%d")) if prefill
                         else datetime.now().strftime("%Y.%m.%d"))
        e_datum.bind("<FocusOut>", lambda e: _auto_fmt(e, e_datum))
        e_datum.bind("<Return>",   lambda e: _auto_fmt(e, e_datum))

        # KM csak Tankolásnál és Karbantartásnál
        e_km = None
        if kat in ("Tankolás", "Karbantartás"):
            e_km = _field("KM állás")

        # Liter + Ft/L csak Tankolásnál
        e_liter = e_ar = None
        if kat == "Tankolás":
            e_liter = _field("Liter", prefill.get("liter", "") if prefill else "")
            e_ar    = _field("Ft/L",  prefill.get("ar_l",  "") if prefill else "")

        e_sum = _field("Összeg (Ft)", prefill.get("osszeg", "") if prefill else "")

        # Helyszín Tankolásnál és Karbantartásnál
        e_hely = None
        if kat in ("Tankolás", "Karbantartás"):
            e_hely = _field("Helyszín", prefill.get("hely", "") if prefill else "")

        # Tankológép
        if kat == "Tankolás" and e_liter and e_ar:
            def _auto_calc(*_):
                try:
                    l  = float(e_liter.get().replace(",", ".").replace(" ", ""))
                    ar = float(e_ar.get().replace(",",   ".").replace(" ", ""))
                    e_sum.delete(0, "end")
                    e_sum.insert(0, str(round(l * ar)))
                except ValueError:
                    pass
            e_liter.bind("<KeyRelease>", _auto_calc)
            e_ar.bind("<KeyRelease>",    _auto_calc)
            ctk.CTkLabel(pop, text="💡 Liter × Ft/L = Összeg (automatikus)",
                         font=("Arial", 10), text_color="#64748b").pack()

        ctk.CTkLabel(pop, text="Megjegyzés").pack()
        txt = ctk.CTkTextbox(pop, width=280, height=60)
        txt.pack(pady=(0, 4))
        if prefill and prefill.get("megj"):
            txt.insert("1.0", str(prefill["megj"]))

        lbl_img = ctk.CTkLabel(pop, text="Nincs kép csatolva", text_color="gray")
        lbl_img.pack(pady=2)

        def attach():
            f = filedialog.askopenfilename(
                filetypes=[("Képek és PDF", "*.jpg *.png *.jpeg *.pdf")], parent=pop)
            if f:
                self.temp_image_path = f
                lbl_img.configure(text=f"Csatolva: {os.path.basename(f)}",
                                  text_color="#10b981")

        ctk.CTkButton(pop, text="📷 Kép/Számla csatolása", fg_color="#64748b",
                      command=attach).pack(pady=4)

        def save():
            final_img = self._copy_attachment(self.temp_image_path) if self.temp_image_path else ""
            try:
                def tf(e): v = e.get().strip().replace(" ","") if e else ""; return float(v) if v else None
                def ti(e): v = e.get().strip().replace(" ","") if e else ""; return int(float(v)) if v else None
                def ts(e): v = e.get().strip() if e else ""; return v or None

                datum = e_datum.get().strip()
                if not datum:
                    messagebox.showwarning("Hiba", "A dátum megadása kötelező!", parent=pop)
                    return
                osszeg = tf(e_sum)
                if osszeg is None:
                    messagebox.showwarning("Hiba", "Az összeg megadása kötelező!", parent=pop)
                    return

                with get_db() as conn:
                    conn.execute("""
                        INSERT INTO szerviz_adatok
                        (auto_id, datum, km_allas, mennyiseg_liter, egysegar_ft_l,
                         osszeg, benzinkut, megjegyzes, kategoria, kep_utvonal)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        self.selected_car_id, datum,
                        ti(e_km), tf(e_liter), tf(e_ar), osszeg,
                        ts(e_hely),
                        txt.get("1.0", "end-1c").strip() or None,
                        kat, final_img
                    ))
                    self._sync_car_km(conn, self.selected_car_id)

                self.refresh_data()
                pop.destroy()
            except Exception as ex:
                messagebox.showerror("Hiba", f"Mentési hiba:\n{ex}", parent=pop)

        ctk.CTkButton(pop, text="Mentés", fg_color="#10b981",
                      command=save).pack(pady=10)

        # Ablak mérete a tartalom alapján
        pop.update_idletasks()
        pop.geometry(f"380x{min(pop.winfo_reqheight() + 30, 700)}")

    # =========================================================================
    # Biztosítás popup
    # =========================================================================

    def open_biztositas_popup(self, eid=None, prefill: dict = None):
        """Biztosítás bejegyzés popup – saját mezőkkel."""
        if not self.selected_car_id:
            messagebox.showwarning("Hiba", "Először válassz ki egy járművet!")
            return

        self.temp_image_path = None
        pop = ctk.CTkToplevel(self)
        pop.title("Biztosítás szerkesztése" if eid else "Új biztosítás")
        pop.geometry("400x580")
        pop.attributes("-topmost", True)
        pop.grab_set()

        def _field(label, val=""):
            ctk.CTkLabel(pop, text=label).pack()
            e = ctk.CTkEntry(pop, width=280)
            e.pack(pady=(0, 4))
            if val:
                e.insert(0, str(val))
            return e

        def _auto_fmt(event, entry):
            val = entry.get().replace(".", "").replace("-", "").strip()
            if len(val) == 8 and val.isdigit():
                entry.delete(0, "end")
                entry.insert(0, f"{val[:4]}.{val[4:6]}.{val[6:]}")

        today = datetime.now().strftime("%Y.%m.%d")
        p = prefill or {}

        e_datum     = _field("Felvitel dátuma", p.get("datum", today))
        e_biztosito = _field("Biztosító neve",  p.get("biztosito", ""))
        e_kezdete   = _field("Biztosítás kezdete (ÉÉÉÉ.HH.NN)", p.get("kezdete", ""))
        e_vege      = _field("Biztosítás vége (ÉÉÉÉ.HH.NN)",    p.get("vege", ""))
        e_osszeg    = _field("Összeg (Ft)",      p.get("osszeg", ""))

        for e in [e_datum, e_kezdete, e_vege]:
            e.bind("<FocusOut>", lambda ev, en=e: _auto_fmt(ev, en))
            e.bind("<Return>",   lambda ev, en=e: _auto_fmt(ev, en))

        ctk.CTkLabel(pop, text="Megjegyzés").pack()
        txt = ctk.CTkTextbox(pop, width=280, height=60)
        txt.pack(pady=(0, 4))
        if p.get("megj"):
            txt.insert("1.0", str(p["megj"]))

        lbl_img = ctk.CTkLabel(pop, text="Nincs kép csatolva", text_color="gray")
        lbl_img.pack(pady=2)

        def attach():
            f = filedialog.askopenfilename(
                filetypes=[("Képek és PDF", "*.jpg *.png *.jpeg *.pdf")], parent=pop)
            if f:
                self.temp_image_path = f
                lbl_img.configure(text=f"Csatolva: {os.path.basename(f)}",
                                  text_color="#10b981")

        ctk.CTkButton(pop, text="📷 Kötvény csatolása", fg_color="#64748b",
                      command=attach).pack(pady=4)

        def save():
            final_img = self._copy_attachment(self.temp_image_path) if self.temp_image_path else ""
            try:
                datum     = e_datum.get().strip()
                biztosito = e_biztosito.get().strip() or None
                kezdete   = e_kezdete.get().strip() or None
                vege      = e_vege.get().strip() or None
                megj      = txt.get("1.0", "end-1c").strip() or None
                v_osszeg  = e_osszeg.get().strip().replace(" ", "")
                osszeg    = float(v_osszeg) if v_osszeg else 0.0

                if not datum:
                    messagebox.showwarning("Hiba", "A dátum megadása kötelező!", parent=pop)
                    return
                if not vege:
                    messagebox.showwarning("Hiba", "A lejárat dátuma kötelező!", parent=pop)
                    return

                with get_db() as conn:
                    if eid:
                        conn.execute("""
                            UPDATE biztositas SET datum=?, osszeg=?, biztosito=?,
                            kezdete=?, vege=?, megjegyzes=?, kep_utvonal=?
                            WHERE id=?
                        """, (datum, osszeg, biztosito, kezdete, vege, megj, final_img, eid))
                    else:
                        conn.execute("""
                            INSERT INTO biztositas
                            (auto_id, datum, osszeg, biztosito, kezdete, vege, megjegyzes, kep_utvonal)
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (self.selected_car_id, datum, osszeg,
                              biztosito, kezdete, vege, megj, final_img))

                self.refresh_data()
                pop.destroy()
            except Exception as ex:
                messagebox.showerror("Hiba", f"Mentési hiba:\n{ex}", parent=pop)

        ctk.CTkButton(pop, text="Mentés", fg_color="#8b5cf6",
                      command=save).pack(pady=10)

    # =========================================================================
    # Bejegyzés popup – Szerkesztés
    # =========================================================================

    def open_edit_popup(self, eid):
        self.temp_image_path = None

        with get_db() as conn:
            r = conn.execute("""
                SELECT datum, km_allas, mennyiseg_liter, egysegar_ft_l,
                       osszeg, benzinkut, megjegyzes, kategoria, kep_utvonal
                FROM szerviz_adatok WHERE id=?
            """, (eid,)).fetchone()

        if not r:
            messagebox.showerror("Hiba", "A bejegyzés nem található!")
            return

        kat, current_img = r[7], r[8] or ""
        pop = ctk.CTkToplevel(self)
        pop.title("Bejegyzés módosítása")
        pop.geometry("400x750")
        pop.attributes("-topmost", True)
        pop.grab_set()

        fields = [("Dátum", "d", r[0]), ("KM állás", "km", r[1])]
        if kat == "Tankolás":
            fields += [("Liter", "l", r[2]), ("Ft/L", "ar", r[3])]
        fields.append(("Összeg", "sum", r[4]))
        if kat != "Egyéb":
            fields.append(("Helyszín", "p", r[5]))

        entries = {}
        for label, key, val in fields:
            ctk.CTkLabel(pop, text=label).pack()
            e = ctk.CTkEntry(pop, width=280)
            e.pack()
            e.insert(0, str(val) if val is not None else "")
            entries[key] = e

        ctk.CTkLabel(pop, text="Megjegyzés").pack()
        txt = ctk.CTkTextbox(pop, width=280, height=80)
        txt.pack()
        txt.insert("1.0", r[6] or "")

        lbl_img = ctk.CTkLabel(pop,
                                text="Van csatolt kép" if current_img else "Nincs kép",
                                text_color="#10b981" if current_img else "gray")
        lbl_img.pack(pady=5)

        # Kép kezelő gombok
        img_btn_f = ctk.CTkFrame(pop, fg_color="transparent")
        img_btn_f.pack()

        def attach():
            f = filedialog.askopenfilename(
                filetypes=[("Képek és PDF", "*.jpg *.png *.jpeg *.pdf")], parent=pop)
            if f:
                self.temp_image_path = f
                lbl_img.configure(text=f"Új kép: {os.path.basename(f)}", text_color="#3b82f6")

        def delete_image():
            if messagebox.askyesno("Kép törlése", "Biztosan törlöd a csatolt képet?", parent=pop):
                nonlocal current_img
                self._delete_attachment_file(current_img)
                current_img = ""
                self.temp_image_path = None
                lbl_img.configure(text="Nincs kép", text_color="gray")

        ctk.CTkButton(img_btn_f, text="📷 Kép módosítása", fg_color="#64748b",
                      command=attach).pack(side="left", padx=5)
        if current_img:
            ctk.CTkButton(img_btn_f, text="🗑 Kép törlése", fg_color="#ef4444",
                          command=delete_image).pack(side="left", padx=5)

        def update():
            final_img_path = self._copy_attachment(self.temp_image_path) if self.temp_image_path else current_img
            try:
                def to_float(key):
                    v = entries[key].get().strip().replace(" ", "") if key in entries else ""
                    return float(v) if v else None

                def to_int(key):
                    v = entries[key].get().strip().replace(" ", "") if key in entries else ""
                    return int(float(v)) if v else None

                def to_str(key):
                    v = entries[key].get().strip() if key in entries else ""
                    return v if v else None

                uj_km = to_int("km")

                with get_db() as conn:
                    conn.execute("""
                        UPDATE szerviz_adatok
                        SET datum=?, km_allas=?, mennyiseg_liter=?,
                            egysegar_ft_l=?, osszeg=?, benzinkut=?, megjegyzes=?, kep_utvonal=?
                        WHERE id=?
                    """, (
                        entries["d"].get().strip(),
                        uj_km,
                        to_float("l"),
                        to_float("ar"),
                        to_float("sum"),
                        to_str("p"),
                        txt.get("1.0", "end-1c").strip() or None,
                        final_img_path, eid
                    ))
                    # Km szinkronizálás: módosítás esetén is mindig a max km kerül az autóhoz
                    self._sync_car_km(conn, self.selected_car_id)

                self.refresh_data()
                pop.destroy()
            except Exception as e:
                messagebox.showerror("Hiba", f"Frissítési hiba:\n{e}", parent=pop)

        ctk.CTkButton(pop, text="Frissítés", fg_color="#3b82f6", command=update).pack(pady=20)

    # =========================================================================
    # Bejegyzés másolása
    # =========================================================================

    def copy_entry(self, eid: int):
        """Megnyitja az új bejegyzés popupot az adott bejegyzés adataival előtöltve."""
        with get_db() as conn:
            r = conn.execute("""
                SELECT datum, km_allas, mennyiseg_liter, egysegar_ft_l,
                       osszeg, benzinkut, megjegyzes, kategoria
                FROM szerviz_adatok WHERE id=?
            """, (eid,)).fetchone()
        if not r:
            return

        prefill = {
            "kat":   r[7],
            "datum": datetime.now().strftime("%Y.%m.%d"),  # Dátum = mai nap
            # km szándékosan üres
            "liter": r[2],
            "ar_l":  r[3],
            "osszeg": r[4],
            "hely":  r[5],
            "megj":  r[6],
        }
        self.open_entry_popup(r[7], prefill=prefill)

    # =========================================================================
    # Törlés
    # =========================================================================

    def _sync_car_km(self, conn, car_id: int):
        """
        Szinkronizálja az autó km állását a bejegyzések maximuma alapján.
        Törlés vagy módosítás után hívandó.
        """
        result = conn.execute("""
            SELECT MAX(km_allas) FROM szerviz_adatok
            WHERE auto_id=? AND km_allas IS NOT NULL
        """, (car_id,)).fetchone()
        max_km = result[0] if result and result[0] is not None else None
        if max_km is not None:
            conn.execute("UPDATE autok SET km_allas=? WHERE id=?", (max_km, car_id))

    def delete_entry(self, eid):
        if messagebox.askyesno("Törlés megerősítése", "Biztosan törölni szeretnéd ezt a bejegyzést?"):
            with get_db() as conn:
                # Csatolt kép útvonalának lekérése törlés előtt
                row = conn.execute("SELECT kep_utvonal FROM szerviz_adatok WHERE id=?", (eid,)).fetchone()
                if row and row[0]:
                    self._delete_attachment_file(row[0])
                conn.execute("DELETE FROM szerviz_adatok WHERE id=?", (eid,))
                self._sync_car_km(conn, self.selected_car_id)
            self.refresh_data()

    def delete_car(self, cid):
        if messagebox.askyesno("Törlés megerősítése",
                               "Biztosan törlöd a járművet?\nEzzel MINDEN kapcsolódó bejegyzés is törlődik!"):
            with get_db() as conn:
                conn.execute("DELETE FROM autok WHERE id=?", (cid,))
                conn.execute("DELETE FROM szerviz_adatok WHERE auto_id=?", (cid,))
            self.selected_car_id = None
            self.refresh_cars()

    # =========================================================================
    # CSV Import
    # =========================================================================

    def _import_csv(self, process_row_fn):
        if not self.selected_car_id:
            messagebox.showwarning("Hiba", "Először válassz ki egy járművet!")
            return
        f = filedialog.askopenfilename(filetypes=[("CSV fájl", "*.csv")])
        if not f:
            return
        count = errors = 0
        try:
            with get_db() as conn, open(f, 'r', encoding='utf-8') as file:
                reader = csv.reader(file, quotechar='"')
                next(reader, None)
                for row in reader:
                    try:
                        process_row_fn(conn, row)
                        count += 1
                    except (ValueError, IndexError) as e:
                        logger.warning(f"CSV sor hiba: {e} | {row}")
                        errors += 1
            self.refresh_data()
            msg = f"{count} sor sikeresen importálva."
            if errors:
                msg += f"\n{errors} sor kihagyva (hibás formátum)."
            messagebox.showinfo("Import eredmény", msg)
        except Exception as e:
            messagebox.showerror("Import hiba", f"A CSV fájl nem olvasható:\n{e}")

    def import_fuel(self):
        def process(conn, row):
            if len(row) < 5: raise ValueError("Túl kevés oszlop")
            c = row[4].replace(" ", "").replace("Ft", "")
            conn.execute("""INSERT INTO szerviz_adatok
                (auto_id, datum, km_allas, mennyiseg_liter, egysegar_ft_l, osszeg, benzinkut, kategoria)
                VALUES (?,?,?,?,?,?,?, 'Tankolás')""",
                (self.selected_car_id, row[0], int(float(row[1])),
                 float(row[2]), float(row[3]), float(c), row[6] if len(row) > 6 else ""))
        self._import_csv(process)

    def import_maintenance(self):
        def process(conn, row):
            if len(row) < 5: raise ValueError("Túl kevés oszlop")
            c = row[4].replace(" ", "").replace("Ft", "")
            note = f"[{row[2]}] {row[3]} | {row[6] if len(row) > 6 else ''}"
            conn.execute("""INSERT INTO szerviz_adatok
                (auto_id, datum, km_allas, osszeg, benzinkut, megjegyzes, kategoria)
                VALUES (?,?,?,?,?,?, 'Karbantartás')""",
                (self.selected_car_id, row[0], int(float(row[1])), float(c), row[5], note))
        self._import_csv(process)

    def import_other(self):
        def process(conn, row):
            if len(row) < 4: raise ValueError("Túl kevés oszlop")
            c = row[3].replace(" ", "").replace("Ft", "")
            note = f"[{row[1]}] {row[2]} | {row[4] if len(row) > 4 else ''}"
            conn.execute("""INSERT INTO szerviz_adatok
                (auto_id, datum, osszeg, megjegyzes, kategoria)
                VALUES (?,?,?,?, 'Egyéb')""",
                (self.selected_car_id, row[0], float(c), note))
        self._import_csv(process)

    # =========================================================================
    # Segédfüggvények
    # =========================================================================

    def _copy_attachment(self, src_path: str) -> str:
        ext = os.path.splitext(src_path)[1]
        fname = f"img_{int(datetime.now().timestamp())}{ext}"
        rel_path = os.path.join("csatolmanyok", fname)
        shutil.copy(src_path, os.path.join(BASE_DIR, rel_path))
        return rel_path

    def _delete_attachment_file(self, rel_path: str):
        """Fizikailag törli a csatolt fájlt a csatolmányok mappából."""
        if not rel_path:
            return
        full_path = os.path.join(BASE_DIR, rel_path)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info(f"Csatolmány törölve: {full_path}")
        except OSError as e:
            logger.warning(f"Csatolmány törlési hiba: {e}")


if __name__ == "__main__":
    app = WheelBooK()
    app.mainloop()