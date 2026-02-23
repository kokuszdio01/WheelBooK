"""
ui_components.py
----------------
UI komponensek: InfoCard, DataRow, SearchFilterBar, ReminderPopup, BackupPanel, SettingsPanel
"""

import os
import customtkinter as ctk
from tkinter import messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# Segédfüggvények
# =============================================================================

def format_amount(amount) -> str:
    try:
        val = float(str(amount).replace(' ', '').replace('Ft', ''))
        return f"{val:,.0f}".replace(",", " ") + " Ft"
    except (ValueError, TypeError):
        return str(amount)


def get_category_icon(category: str) -> str:
    return {"Tankolás": "⛽", "Karbantartás": "🔧"}.get(category, "📦")


def bind_widget_tree(widget, event, callback):
    """Rekurzívan bekötik az eseményt a widgetre és minden gyermekére."""
    widget.bind(event, callback)
    for child in widget.winfo_children():
        bind_widget_tree(child, event, callback)


# =============================================================================
# InfoCard – jármű kártya
# =============================================================================

class InfoCard(ctk.CTkFrame):
    # Márka ikonok emoji alapon
    BRAND_ICONS = {
        "Audi": "🔵", "BMW": "🔵", "Mercedes": "⭐", "Volkswagen": "🟡",
        "Opel": "⚡", "Ford": "🔵", "Toyota": "🔴", "Honda": "🔴",
        "Suzuki": "🟣", "Skoda": "🟢", "Seat": "🟠", "Renault": "🟡",
        "Peugeot": "🦁", "Citroen": "🟣", "Fiat": "🔴", "Hyundai": "🔵",
        "Kia": "🔴", "Mazda": "🔴", "Nissan": "🔴", "Volvo": "🔵",
    }

    def __init__(self, parent, car_data, select_cb, edit_cb, delete_cb, active=False):
        cid, marka, tipus, ev, km, vin, rsz, muszaki, intervallum, ikon = car_data
        mode = ctk.get_appearance_mode()
        is_dark = mode == "Dark"

        if is_dark:
            bg = "#1e293b" if not active else "#1e3a5f"
            border = "#334155" if not active else "#3b82f6"
        else:
            bg = "#ffffff" if not active else "#eff6ff"
            border = "#e2e8f0" if not active else "#3b82f6"

        super().__init__(parent, fg_color=bg, corner_radius=15,
                         border_width=2, border_color=border, width=220, height=155)
        self.pack_propagate(False)
        bind_widget_tree(self, "<Button-1>", lambda e: select_cb(cid))

        # Ikon megjelenítése
        display_ikon = ikon if ikon else self.BRAND_ICONS.get(marka, "🚗")
        ctk.CTkLabel(self, text=display_ikon, font=("Arial", 28)).pack(pady=(8, 0))
        ctk.CTkLabel(self, text=f"{marka} {tipus}", font=("Arial", 13, "bold")).pack(pady=(2, 0))
        ctk.CTkLabel(self, text=rsz if rsz else "---", font=("Arial", 11), text_color="gray").pack()
        km_str = f"{km:,} km".replace(",", " ") if km else "--- km"
        ctk.CTkLabel(self, text=km_str, font=("Arial", 11), text_color="#3b82f6").pack()

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(side="bottom", pady=5)
        ctk.CTkButton(btn_f, text="📝", width=30, height=25,
                      fg_color="#f1f5f9", text_color="black",
                      command=lambda: edit_cb(cid)).pack(side="left", padx=2)
        ctk.CTkButton(btn_f, text="🗑", width=30, height=25,
                      fg_color="#f1f5f9", text_color="red",
                      command=lambda: delete_cb(cid)).pack(side="left", padx=2)


# =============================================================================
# DataRow – bejegyzés sor
# =============================================================================

class DataRow(ctk.CTkFrame):
    def __init__(self, parent, entry_id, date, amount, km, category,
                 delete_callback, edit_callback, copy_callback=None,
                 liter="", ar_l="", kut="", note="", image_path=""):

        mode = ctk.get_appearance_mode()
        row_bg = "#1e293b" if mode == "Dark" else "white"

        super().__init__(parent, fg_color=row_bg, corner_radius=12,
                         border_width=1, border_color="#334155" if mode == "Dark" else "#e2e8f0")
        self.pack(fill="x", pady=6, padx=10)

        main_cont = ctk.CTkFrame(self, fg_color="transparent")
        main_cont.pack(fill="x", padx=15, pady=10)

        top_row = ctk.CTkFrame(main_cont, fg_color="transparent")
        top_row.pack(fill="x")

        icon = get_category_icon(category)
        info_str = f"{icon} {date}"
        if km:
            info_str += f"    {km} km"

        ctk.CTkLabel(top_row, text=info_str, font=("Arial", 13, "bold")).pack(side="left")

        btn_f = ctk.CTkFrame(top_row, fg_color="transparent")
        btn_f.pack(side="right")

        ctk.CTkLabel(btn_f, text=format_amount(amount),
                     font=("Arial", 15, "bold")).pack(side="left", padx=20)

        if image_path:
            full_path = os.path.join(BASE_DIR, image_path)
            ctk.CTkButton(btn_f, text="📷", width=30, height=30,
                          fg_color="#f1f5f9", text_color="#10b981",
                          command=lambda p=full_path: self._open_file(p)).pack(side="left", padx=2)

        ctk.CTkButton(btn_f, text="📝", width=30, height=30,
                      fg_color="#f1f5f9", text_color="#3b82f6",
                      command=lambda: edit_callback(entry_id)).pack(side="left", padx=2)
        if copy_callback:
            ctk.CTkButton(btn_f, text="📋", width=30, height=30,
                          fg_color="#f1f5f9", text_color="#8b5cf6",
                          command=lambda: copy_callback(entry_id)).pack(side="left", padx=2)
        ctk.CTkButton(btn_f, text="🗑", width=30, height=30,
                      fg_color="#f1f5f9", text_color="#ef4444",
                      command=lambda: delete_callback(entry_id)).pack(side="left", padx=2)

        details = []
        if category == "Tankolás" and liter:
            details.append(f"{liter} L")
            if ar_l:
                details.append(f"({ar_l} Ft/L)")
        if kut:
            details.append(f"📍 {kut}")
        if note:
            details.append(f"💬 {note}")

        if details:
            bottom_row = ctk.CTkFrame(main_cont, fg_color="transparent")
            bottom_row.pack(fill="x", pady=(5, 0))
            ctk.CTkLabel(bottom_row, text="  |  ".join(details),
                         font=("Arial", 11), text_color="#64748b").pack(side="left", padx=(25, 0))

    @staticmethod
    def _open_file(path: str):
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning("Hiba", f"A fájl nem található:\n{path}")


# =============================================================================
# SearchFilterBar – keresés és szűrés sáv
# =============================================================================

class SearchFilterBar(ctk.CTkFrame):
    """
    Keresés és szűrés sáv egy fülhöz.
    on_change(filters) – callback, filters dict:
        {"search": str, "date_from": str, "date_to": str,
         "amount_min": float|None, "amount_max": float|None, "sort": str}
    """

    SORT_OPTIONS = ["Dátum (újabb)", "Dátum (régebbi)", "Összeg (nagyobb)", "Összeg (kisebb)", "KM állás"]

    def __init__(self, parent, on_change_callback, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.on_change = on_change_callback
        self._build()

    def _build(self):
        # 1. sor: Keresés + Rendezés
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 4))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._notify)
        ctk.CTkLabel(row1, text="🔍", font=("Arial", 14)).pack(side="left", padx=(0, 4))
        ctk.CTkEntry(row1, textvariable=self.search_var,
                     placeholder_text="Keresés (megjegyzés, helyszín...)",
                     width=240).pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row1, text="Rendezés:").pack(side="left", padx=(0, 4))
        self.sort_var = ctk.StringVar(value=self.SORT_OPTIONS[0])
        ctk.CTkOptionMenu(row1, variable=self.sort_var,
                          values=self.SORT_OPTIONS,
                          command=lambda _: self._notify(), width=180).pack(side="left")

        # Szűrő megjelenítő gomb
        self.filter_visible = False
        self.toggle_btn = ctk.CTkButton(row1, text="▾ Szűrők", width=90,
                                         fg_color="#64748b",
                                         command=self._toggle_filters)
        self.toggle_btn.pack(side="left", padx=10)

        # Törlés gomb
        ctk.CTkButton(row1, text="✕ Törlés", width=80,
                      fg_color="#ef4444", command=self.reset).pack(side="left")

        # 2. sor: Részletes szűrők (alapból rejtett)
        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")

        ctk.CTkLabel(self.filter_frame, text="Dátumtól:").pack(side="left", padx=(0, 4))
        self.date_from = ctk.CTkEntry(self.filter_frame, placeholder_text="ÉÉÉÉ.HH.NN", width=110)
        self.date_from.pack(side="left", padx=(0, 10))
        self.date_from.bind("<KeyRelease>", lambda e: self._notify())

        ctk.CTkLabel(self.filter_frame, text="Dátumig:").pack(side="left", padx=(0, 4))
        self.date_to = ctk.CTkEntry(self.filter_frame, placeholder_text="ÉÉÉÉ.HH.NN", width=110)
        self.date_to.pack(side="left", padx=(0, 15))
        self.date_to.bind("<KeyRelease>", lambda e: self._notify())

        ctk.CTkLabel(self.filter_frame, text="Min Ft:").pack(side="left", padx=(0, 4))
        self.amount_min = ctk.CTkEntry(self.filter_frame, placeholder_text="0", width=80)
        self.amount_min.pack(side="left", padx=(0, 10))
        self.amount_min.bind("<KeyRelease>", lambda e: self._notify())

        ctk.CTkLabel(self.filter_frame, text="Max Ft:").pack(side="left", padx=(0, 4))
        self.amount_max = ctk.CTkEntry(self.filter_frame, placeholder_text="∞", width=80)
        self.amount_max.pack(side="left")
        self.amount_max.bind("<KeyRelease>", lambda e: self._notify())

    def _toggle_filters(self):
        self.filter_visible = not self.filter_visible
        if self.filter_visible:
            self.filter_frame.pack(fill="x", pady=(4, 0))
            self.toggle_btn.configure(text="▴ Szűrők")
        else:
            self.filter_frame.pack_forget()
            self.toggle_btn.configure(text="▾ Szűrők")

    def _notify(self, *_):
        self.on_change(self.get_filters())

    def get_filters(self) -> dict:
        def safe_float(widget):
            try:
                return float(widget.get().replace(" ", ""))
            except (ValueError, AttributeError):
                return None

        return {
            "search": self.search_var.get().strip().lower(),
            "date_from": self.date_from.get().strip(),
            "date_to": self.date_to.get().strip(),
            "amount_min": safe_float(self.amount_min),
            "amount_max": safe_float(self.amount_max),
            "sort": self.sort_var.get(),
        }

    def reset(self):
        self.search_var.set("")
        self.date_from.delete(0, "end")
        self.date_to.delete(0, "end")
        self.amount_min.delete(0, "end")
        self.amount_max.delete(0, "end")
        self.sort_var.set(self.SORT_OPTIONS[0])
        self._notify()

    def apply_filters(self, rows: list[tuple]) -> list[tuple]:
        """
        Szűri és rendezi az adatbázisból kapott sorokat.
        rows: [(id, datum, osszeg, km_allas, kategoria, liter, ar_l, kut, megj, kep), ...]
        """
        f = self.get_filters()
        result = list(rows)

        # Szöveges keresés (megjegyzés + helyszín)
        if f["search"]:
            result = [r for r in result if
                      f["search"] in str(r[8] or "").lower() or
                      f["search"] in str(r[7] or "").lower()]

        # Dátum szűrő
        if f["date_from"]:
            result = [r for r in result if str(r[1]) >= f["date_from"]]
        if f["date_to"]:
            result = [r for r in result if str(r[1]) <= f["date_to"]]

        # Összeg szűrő
        if f["amount_min"] is not None:
            result = [r for r in result if (r[2] or 0) >= f["amount_min"]]
        if f["amount_max"] is not None:
            result = [r for r in result if (r[2] or 0) <= f["amount_max"]]

        # Rendezés
        sort = f["sort"]
        if sort == "Dátum (újabb)":
            result.sort(key=lambda r: r[1] or "", reverse=True)
        elif sort == "Dátum (régebbi)":
            result.sort(key=lambda r: r[1] or "")
        elif sort == "Összeg (nagyobb)":
            result.sort(key=lambda r: r[2] or 0, reverse=True)
        elif sort == "Összeg (kisebb)":
            result.sort(key=lambda r: r[2] or 0)
        elif sort == "KM állás":
            result.sort(key=lambda r: r[3] or 0, reverse=True)

        return result


# =============================================================================
# ReminderPopup – indításkori figyelmeztetés
# =============================================================================

class ReminderPopup(ctk.CTkToplevel):
    def __init__(self, parent, reminders: list[dict]):
        super().__init__(parent)
        self.title("🔔 Szerviz emlékeztetők")
        self.geometry("520x400")
        self.attributes("-topmost", True)
        self.grab_set()
        self.resizable(False, False)

        ctk.CTkLabel(self, text="Szerviz emlékeztetők",
                     font=("Arial", 18, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self, text=f"{len(reminders)} aktív figyelmeztetés",
                     text_color="gray").pack()

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        for r in reminders:
            color = "#fff1f2" if r["sulyossag"] == "danger" else "#fffbeb"
            border = "#f43f5e" if r["sulyossag"] == "danger" else "#f59e0b"

            card = ctk.CTkFrame(scroll, fg_color=color, border_width=1,
                                border_color=border, corner_radius=10)
            card.pack(fill="x", pady=5)

            ctk.CTkLabel(card, text=r["uzenet"],
                         font=("Arial", 12), wraplength=440).pack(anchor="w", padx=15, pady=5)
            ctk.CTkLabel(card, text=f"🚗 {r['auto']}",
                         font=("Arial", 11), text_color="gray").pack(anchor="w", padx=15, pady=(0, 8))

        ctk.CTkButton(self, text="Értettem", fg_color="#3b82f6",
                      command=self.destroy).pack(pady=15)


# =============================================================================
# BackupPanel – backup kezelő ablak
# =============================================================================

class BackupPanel(ctk.CTkToplevel):
    def __init__(self, parent, backup_manager, restart_callback=None):
        super().__init__(parent)
        self.bm = backup_manager
        self.restart_cb = restart_callback
        self.title("💾 Adatmentés kezelő")
        self.geometry("580x520")
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()

    def _build(self):
        from tkinter import filedialog

        ctk.CTkLabel(self, text="Adatmentés kezelő",
                     font=("Arial", 18, "bold")).pack(pady=(20, 5))

        # Gombok
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(btn_frame, text="📦 ZIP Export (teljes)",
                      fg_color="#10b981", width=180,
                      command=self._export_zip).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="📂 ZIP Visszaállítás",
                      fg_color="#f97316", width=180,
                      command=self._import_zip).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🔄 Azonnali Backup",
                      fg_color="#3b82f6", width=160,
                      command=self._manual_backup).pack(side="left", padx=5)

        # Backup lista
        ctk.CTkLabel(self, text="Automatikus backupok:",
                     font=("Arial", 13, "bold")).pack(anchor="w", padx=20, pady=(10, 5))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", height=250)
        self.list_frame.pack(fill="both", expand=True, padx=20)

        self._refresh_list()

        ctk.CTkButton(self, text="Bezárás", fg_color="#64748b",
                      command=self.destroy).pack(pady=15)

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        backups = self.bm.list_backups()
        if not backups:
            ctk.CTkLabel(self.list_frame, text="Nincs backup.", text_color="gray").pack()
            return

        for b in backups:
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"📁 {b['date']}  ({b['size_kb']} KB)",
                         font=("Arial", 12)).pack(side="left")
            ctk.CTkButton(row, text="Visszaállítás", width=110,
                          fg_color="#f97316",
                          command=lambda p=b["path"]: self._restore_db(p)).pack(side="right")

    def _export_zip(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=f"WheelBooK_backup_{__import__('datetime').datetime.now().strftime('%Y%m%d')}.zip",
            filetypes=[("ZIP fájl", "*.zip")]
        )
        if path:
            ok = self.bm.export_zip(path)
            if ok:
                messagebox.showinfo("Siker", "ZIP export sikeres!", parent=self)
            else:
                messagebox.showerror("Hiba", "ZIP export sikertelen!", parent=self)

    def _import_zip(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("ZIP fájl", "*.zip")])
        if path:
            ok, msg = self.bm.import_zip(path)
            if ok:
                messagebox.showinfo("Siker", msg, parent=self)
                if self.restart_cb:
                    self.destroy()
                    self.restart_cb()
            else:
                messagebox.showerror("Hiba", msg, parent=self)

    def _manual_backup(self):
        import shutil
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{self.bm.backup_dir}/manual_{ts}.db"
        try:
            shutil.copy2(self.bm.db_path, dest)
            messagebox.showinfo("Siker", f"Backup elkészült:\n{dest}", parent=self)
            self._refresh_list()
        except Exception as e:
            messagebox.showerror("Hiba", str(e), parent=self)

    def _restore_db(self, path):
        if messagebox.askyesno("Visszaállítás",
                               "Biztosan visszaállítod ezt a backupot?\n"
                               "A jelenlegi adatok felülíródnak!",
                               parent=self):
            ok, msg = self.bm.restore_from_db_backup(path)
            if ok:
                messagebox.showinfo("Siker", msg, parent=self)
                if self.restart_cb:
                    self.destroy()
                    self.restart_cb()
            else:
                messagebox.showerror("Hiba", msg, parent=self)


# =============================================================================
# SettingsPanel – beállítások ablak
# =============================================================================

class SettingsPanel(ctk.CTkToplevel):
    def __init__(self, parent, config_manager, on_appearance_change=None):
        super().__init__(parent)
        self.config = config_manager
        self.on_appearance_change = on_appearance_change
        self.title("⚙️ Beállítások")
        self.geometry("420x500")
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Beállítások",
                     font=("Arial", 18, "bold")).pack(pady=(20, 15))

        # Megjelenés / Sötét mód
        section = self._section("🎨 Megjelenés")
        mode_frame = ctk.CTkFrame(section, fg_color="transparent")
        mode_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(mode_frame, text="Téma:").pack(side="left", padx=(0, 10))
        self.mode_var = ctk.StringVar(value=self.config.get("appearance_mode", "light").capitalize())
        ctk.CTkSegmentedButton(mode_frame, values=["Light", "Dark", "System"],
                               variable=self.mode_var,
                               command=self._on_mode_change).pack(side="left")

        # Emlékeztetők
        section2 = self._section("🔔 Emlékeztetők")

        self._labeled_entry(section2, "Műszaki lejárat előtti figyelmeztetés (nap):",
                            "reminder_days_before", default=30)
        self._labeled_entry(section2, "Olajcsere figyelmeztetés (km-rel előtte):",
                            "oil_warning_km", default=1000)

        # Backup
        section3 = self._section("💾 Backup")

        backup_row = ctk.CTkFrame(section3, fg_color="transparent")
        backup_row.pack(fill="x", pady=5)
        ctk.CTkLabel(backup_row, text="Automatikus napi backup:").pack(side="left")
        self.auto_backup_var = ctk.BooleanVar(value=self.config.get("auto_backup", True))
        ctk.CTkSwitch(backup_row, variable=self.auto_backup_var, text="").pack(side="right")

        self._labeled_entry(section3, "Backup megőrzési idő (nap):",
                            "backup_keep_days", default=30)

        # Olajcsere alapértelmezett intervallum
        section4 = self._section("🔧 Szerviz")
        self._labeled_entry(section4, "Alapértelmezett olajcsere periódus (km):",
                            "default_oil_interval", default=10000)

        # Gombok
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=20)
        ctk.CTkButton(btn_f, text="💾 Mentés", fg_color="#10b981",
                      command=self._save).pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="↩ Alapértelmezett", fg_color="#64748b",
                      command=self._reset).pack(side="left", padx=10)

    def _section(self, title: str) -> ctk.CTkFrame:
        ctk.CTkLabel(self, text=title, font=("Arial", 13, "bold")).pack(anchor="w", padx=20, pady=(10, 2))
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20)
        return frame

    def _labeled_entry(self, parent, label: str, key: str, default):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=label, wraplength=260, justify="left").pack(side="left")
        e = ctk.CTkEntry(row, width=80)
        e.pack(side="right")
        e.insert(0, str(self.config.get(key, default)))
        setattr(self, f"entry_{key}", e)

    def _on_mode_change(self, value):
        mode = value.lower()
        ctk.set_appearance_mode(mode)
        self.config.set("appearance_mode", mode)
        if self.on_appearance_change:
            self.on_appearance_change(mode)

    def _save(self):
        def safe_int(key, default):
            try:
                return int(getattr(self, f"entry_{key}").get())
            except (ValueError, AttributeError):
                return default

        self.config.set("reminder_days_before", safe_int("reminder_days_before", 30))
        self.config.set("oil_warning_km", safe_int("oil_warning_km", 1000))
        self.config.set("backup_keep_days", safe_int("backup_keep_days", 30))
        self.config.set("default_oil_interval", safe_int("default_oil_interval", 10000))
        self.config.set("auto_backup", self.auto_backup_var.get())
        self.config.set("appearance_mode", self.mode_var.get().lower())
        messagebox.showinfo("Mentve", "Beállítások elmentve!", parent=self)
        self.destroy()

    def _reset(self):
        if messagebox.askyesno("Visszaállítás", "Visszaállítod az alapbeállításokat?", parent=self):
            self.config.reset()
            self.destroy()


# =============================================================================
# ChangelogPopup – verziókövetés ablak
# =============================================================================

class ChangelogPopup(ctk.CTkToplevel):
    """
    Indításkor egyszer megjelenő újdonságok ablak.
    Csak akkor nyílik meg ha az utolsó látott verzió != aktuális verzió.
    """
    CURRENT_VERSION = "9.1"

    def __init__(self, parent, config_manager, changelog_path: str, force=False):
        last_seen = config_manager.get("last_seen_version", "")
        if not force and last_seen == self.CURRENT_VERSION:
            return  # Már látta ezt a verziót

        super().__init__(parent)
        self.config = config_manager
        self.title(f"🆕 WheelBooK v{self.CURRENT_VERSION} – Újdonságok")
        self.geometry("560x480")
        self.attributes("-topmost", True)
        self.grab_set()
        self.resizable(False, True)
        self._build(changelog_path)

        # Mentjük hogy látta
        config_manager.set("last_seen_version", self.CURRENT_VERSION)

    def _build(self, changelog_path: str):
        ctk.CTkLabel(self, text=f"Újdonságok – v{self.CURRENT_VERSION}",
                     font=("Arial", 18, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self, text="Ezek kerültek be az új verzióba:",
                     text_color="gray").pack()

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        try:
            with open(changelog_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Csak az első (legújabb) verzió blokkját mutatjuk
            blocks = content.split("\n## ")
            first_block = blocks[1] if len(blocks) > 1 else content

            for line in first_block.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("###"):
                    ctk.CTkLabel(scroll, text=line.replace("###", "").strip(),
                                 font=("Arial", 13, "bold"),
                                 text_color="#3b82f6").pack(anchor="w", pady=(8, 2))
                elif line.startswith("-"):
                    card = ctk.CTkFrame(scroll, fg_color="#f8fafc",
                                        corner_radius=8, border_width=1,
                                        border_color="#e2e8f0")
                    card.pack(fill="x", pady=2)
                    ctk.CTkLabel(card, text=line, font=("Arial", 12),
                                 wraplength=480, justify="left").pack(
                        anchor="w", padx=12, pady=6)
        except FileNotFoundError:
            ctk.CTkLabel(scroll, text="Changelog fájl nem található.",
                         text_color="gray").pack()

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=15)
        ctk.CTkButton(btn_f, text="👍 Rendben", fg_color="#3b82f6",
                      width=140, command=self.destroy).pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="📄 Teljes changelog", fg_color="#64748b",
                      width=160,
                      command=lambda: self._show_full(changelog_path)).pack(side="left", padx=10)

    def _show_full(self, path):
        try:
            os.startfile(path)
        except Exception:
            pass


# =============================================================================
# CategoryManagerPanel – kategória kezelő
# =============================================================================

class CategoryManagerPanel(ctk.CTkToplevel):
    """
    Kategóriák hozzáadása, szerkesztése, törlése.
    Az alap 3 kategória nem törölhető.
    """

    IKON_OPTIONS = ["⛽", "🔧", "📦", "🚗", "🛡️", "🅿️", "🛣️", "🔑", "💡", "🧰", "🪛", "💳", "📋"]
    SZIN_OPTIONS = {
        "Kék": "#3b82f6", "Zöld": "#10b981", "Narancs": "#f97316",
        "Piros": "#ef4444", "Lila": "#8b5cf6", "Sárga": "#f59e0b",
        "Szürke": "#64748b", "Türkiz": "#06b6d4",
    }

    def __init__(self, parent, db_path: str, on_change_callback=None):
        super().__init__(parent)
        self.db_path = db_path
        self.on_change = on_change_callback
        self.title("🏷️ Kategóriák kezelése")
        self.geometry("500x540")
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()

    def _get_db(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _build(self):
        ctk.CTkLabel(self, text="Kategóriák kezelése",
                     font=("Arial", 18, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self, text="Az alap 3 kategória nem törölhető.",
                     text_color="gray", font=("Arial", 11)).pack()

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", height=280)
        self.list_frame.pack(fill="x", padx=20, pady=10)
        self._refresh_list()

        # Új kategória hozzáadás
        ctk.CTkLabel(self, text="Új kategória hozzáadása:",
                     font=("Arial", 13, "bold")).pack(anchor="w", padx=20, pady=(5, 2))

        add_frame = ctk.CTkFrame(self, fg_color="transparent")
        add_frame.pack(fill="x", padx=20, pady=5)

        self.new_nev = ctk.CTkEntry(add_frame, placeholder_text="Név (pl. Parkolás)", width=150)
        self.new_nev.pack(side="left", padx=(0, 5))

        self.new_ikon_var = ctk.StringVar(value="📋")
        ctk.CTkOptionMenu(add_frame, variable=self.new_ikon_var,
                          values=self.IKON_OPTIONS, width=70).pack(side="left", padx=5)

        self.new_szin_var = ctk.StringVar(value="Szürke")
        ctk.CTkOptionMenu(add_frame, variable=self.new_szin_var,
                          values=list(self.SZIN_OPTIONS.keys()), width=100).pack(side="left", padx=5)

        ctk.CTkButton(add_frame, text="+ Hozzáad", fg_color="#10b981",
                      width=100, command=self._add_category).pack(side="left", padx=5)

        ctk.CTkButton(self, text="Bezárás", fg_color="#64748b",
                      command=self.destroy).pack(pady=15)

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        with self._get_db() as conn:
            cats = conn.execute(
                "SELECT id, nev, ikon, szin, alap FROM kategoriak ORDER BY alap DESC, id ASC"
            ).fetchall()

        for cid, nev, ikon, szin, alap in cats:
            row = ctk.CTkFrame(self.list_frame, fg_color="white",
                               corner_radius=8, border_width=1, border_color="#e2e8f0")
            row.pack(fill="x", pady=3)

            # Színes négyzet label-ként (megbízhatóbb mint CTkFrame)
            ctk.CTkLabel(row, text="●", font=("Arial", 16),
                         text_color=szin, width=20).pack(side="left", padx=(10, 4))
            ctk.CTkLabel(row, text=f"{ikon}  {nev}",
                         font=("Arial", 12)).pack(side="left", padx=4)

            if alap:
                ctk.CTkLabel(row, text="alap", font=("Arial", 10),
                             text_color="gray").pack(side="left", padx=4)
            else:
                ctk.CTkButton(row, text="🗑", width=30, height=28,
                              fg_color="#f1f5f9", text_color="#ef4444",
                              command=lambda c=cid, n=nev: self._delete_category(c, n)
                              ).pack(side="right", padx=8)

    def _add_category(self):
        nev = self.new_nev.get().strip()
        if not nev:
            messagebox.showwarning("Hiba", "Add meg a kategória nevét!", parent=self)
            return
        ikon = self.new_ikon_var.get()
        szin = self.SZIN_OPTIONS.get(self.new_szin_var.get(), "#64748b")
        try:
            with self._get_db() as conn:
                conn.execute(
                    "INSERT INTO kategoriak (nev, ikon, szin, alap) VALUES (?,?,?,0)",
                    (nev, ikon, szin)
                )
            self.new_nev.delete(0, "end")
            self._refresh_list()
            if self.on_change:
                self.on_change()
        except Exception as e:
            messagebox.showerror("Hiba", f"Már létezik ilyen nevű kategória!\n{e}", parent=self)

    def _delete_category(self, cid: int, nev: str):
        # Ellenőrzés: van-e bejegyzés ebben a kategóriában?
        with self._get_db() as conn:
            db_count = conn.execute(
                "SELECT COUNT(*) FROM szerviz_adatok WHERE kategoria=?", (nev,)
            ).fetchone()[0]

        if db_count > 0:
            if not messagebox.askyesno(
                "Figyelem",
                f"A '{nev}' kategóriában {db_count} bejegyzés van.\n"
                f"Törlés után ezek 'Egyéb' kategóriába kerülnek. Folytatod?",
                parent=self
            ):
                return
            with self._get_db() as conn:
                conn.execute("UPDATE szerviz_adatok SET kategoria='Egyéb' WHERE kategoria=?", (nev,))

        with self._get_db() as conn:
            conn.execute("DELETE FROM kategoriak WHERE id=?", (cid,))

        self._refresh_list()
        if self.on_change:
            self.on_change()


# =============================================================================
# UpdatePopup – frissítés értesítő ablak
# =============================================================================

class UpdatePopup(ctk.CTkToplevel):
    """
    Fél-automatikus frissítés popup.
    Megjelenik ha új verzió elérhető – megkérdezi a felhasználót.
    """

    def __init__(self, parent, latest_version: str, changelog: str, install_callback):
        super().__init__(parent)
        self.install_cb = install_callback
        self.title("🔄 Frissítés elérhető")
        self.geometry("480x400")
        self.attributes("-topmost", True)
        self.grab_set()
        self.resizable(False, False)
        self._build(latest_version, changelog)

    def _build(self, version: str, changelog: str):
        # Fejléc
        header = ctk.CTkFrame(self, fg_color="#3b82f6", corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text=f"🔄  Elérhető: WheelBooK v{version}",
                     font=("Arial", 16, "bold"),
                     text_color="white").pack(pady=15, padx=20, anchor="w")

        ctk.CTkLabel(self, text="Újdonságok ebben a verzióban:",
                     font=("Arial", 12, "bold")).pack(anchor="w", padx=20, pady=(15, 5))

        # Changelog szöveg
        scroll = ctk.CTkScrollableFrame(self, fg_color="#f8fafc",
                                         corner_radius=8, height=180)
        scroll.pack(fill="x", padx=20)

        for line in changelog.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("###"):
                ctk.CTkLabel(scroll, text=line.replace("###", "").strip(),
                             font=("Arial", 12, "bold"),
                             text_color="#3b82f6").pack(anchor="w", pady=(6, 2), padx=5)
            elif line.startswith("-"):
                ctk.CTkLabel(scroll, text=line,
                             font=("Arial", 11),
                             wraplength=400, justify="left").pack(anchor="w", padx=10, pady=2)
            else:
                ctk.CTkLabel(scroll, text=line,
                             font=("Arial", 11),
                             text_color="gray").pack(anchor="w", padx=5)

        ctk.CTkLabel(self,
                     text="⚠️  A frissítés előtt a program automatikusan biztonsági mentést készít.",
                     font=("Arial", 10), text_color="#64748b",
                     wraplength=440).pack(padx=20, pady=(10, 5))

        # Gombok
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(pady=15)

        ctk.CTkButton(btn_f, text="⬇️  Telepítés most", fg_color="#10b981",
                      width=160, font=("Arial", 13, "bold"),
                      command=self._install).pack(side="left", padx=10)
        ctk.CTkButton(btn_f, text="Később", fg_color="#64748b",
                      width=100, command=self.destroy).pack(side="left", padx=10)

    def _install(self):
        self.destroy()
        self.install_cb()