# -*- coding: utf-8 -*-
"""
WheelBooK v9.3 – PyQt6
Autó nyilvántartó program – teljes UI átírás PyQt6-ra.
"""

import sys
import os
import sqlite3
import csv
import shutil
import logging
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QScrollArea, QLineEdit, QComboBox,
    QDialog, QFormLayout, QMessageBox, QFileDialog, QSizePolicy,
    QStackedWidget, QGridLayout, QTextEdit, QDateEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QSplitter, QToolButton, QMenu,
)
from PyQt6.QtCore import Qt, QSize, QDate, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette, QCursor

try:
    from updater import start_update_check, check_update_manual, CURRENT_VERSION
except ImportError:
    def start_update_check(w, silent=True): pass
    def check_update_manual(w): pass
    CURRENT_VERSION = "9.3"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

import zipfile
import json
import threading
from pathlib import Path
try:
    import matplotlib
    matplotlib.use("QtAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False
logger = logging.getLogger(__name__)

# ── Útvonalak ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    EXE_DIR  = os.path.dirname(sys.executable)
    DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", "WheelBooK")
else:
    EXE_DIR  = BASE_DIR
    DATA_DIR = os.path.join(BASE_DIR, "adatok")

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH     = os.path.join(DATA_DIR, "auto_naplo.db")
UPLOAD_DIR  = os.path.join(DATA_DIR, "csatolmanyok")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
BACKUP_DIR  = os.path.join(DATA_DIR, "backups")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── Adatbázis ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS autok (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marka TEXT NOT NULL,
                tipus TEXT NOT NULL,
                evjarat TEXT,
                km_allas INTEGER DEFAULT 0,
                vin TEXT,
                rendszam TEXT,
                muszaki_lejarat TEXT,
                olaj_intervallum INTEGER DEFAULT 10000
            );
            CREATE TABLE IF NOT EXISTS szerviz_adatok (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auto_id INTEGER NOT NULL,
                datum TEXT NOT NULL,
                kategoria TEXT NOT NULL,
                osszeg REAL DEFAULT 0,
                km_allas INTEGER,
                mennyiseg_liter REAL,
                egysegar_ft_l REAL,
                benzinkut TEXT,
                megjegyzes TEXT,
                kep_utvonal TEXT DEFAULT '',
                FOREIGN KEY (auto_id) REFERENCES autok(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS kategoriak (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nev TEXT NOT NULL UNIQUE,
                ikon TEXT DEFAULT '📦',
                szin TEXT DEFAULT '#64748b',
                alap INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS biztositas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auto_id INTEGER NOT NULL,
                datum TEXT NOT NULL,
                osszeg REAL DEFAULT 0,
                biztosito TEXT,
                kezdete TEXT,
                vege TEXT,
                megjegyzes TEXT,
                kep_utvonal TEXT DEFAULT '',
                FOREIGN KEY (auto_id) REFERENCES autok(id) ON DELETE CASCADE
            );
        """)
        # Alapkategóriák
        existing = conn.execute("SELECT COUNT(*) FROM kategoriak").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO kategoriak (nev, ikon, szin, alap) VALUES (?,?,?,?)",
                [("Tankolás","⛽","#3b82f6",1),
                 ("Karbantartás","🔧","#10b981",1),
                 ("Egyéb","📦","#f97316",1),
                 ("Biztosítás","🛡️","#8b5cf6",1)]
            )

# ══════════════════════════════════════════════════════════════════════════════
# QSS Stíluslapok
# ══════════════════════════════════════════════════════════════════════════════
DARK_QSS = """
QMainWindow, QDialog { background: #0f172a; }
QWidget { background: transparent; color: #e2e8f0; font-family: 'Segoe UI'; font-size: 13px; }

/* Topbar */
#topbar { background: #1e293b; border-bottom: 1px solid #334155; }
#logo   { color: #f97316; font-size: 20px; font-weight: 900; background: transparent; }

/* Topbar gombok */
#tb_btn {
    background: #334155; color: #cbd5e1;
    border: none; border-radius: 7px;
    padding: 6px 14px; font-size: 12px; font-weight: 600;
}
#tb_btn:hover { background: #475569; color: white; }

/* Chip sáv */
#chipbar { background: #0f172a; border-bottom: 1px solid #1e293b; }

/* Jármű chip */
#car_chip {
    background: #1e293b; border: 2px solid #334155;
    border-radius: 10px; padding: 8px 14px;
}
#car_chip:hover { border-color: #3b82f6; }

#car_chip_active {
    background: #1e3a5f; border: 2px solid #3b82f6;
    border-radius: 10px; padding: 8px 14px;
}

/* Új jármű chip */
#chip_add {
    background: transparent; border: 2px dashed #334155;
    border-radius: 10px; color: #475569;
    font-size: 13px; font-weight: 600;
}
#chip_add:hover { border-color: #f97316; color: #f97316; }

/* Tab sáv */
#tabbar { background: #1e293b; border-bottom: 2px solid #334155; }

#tab_btn {
    background: transparent; border: none;
    color: #64748b; font-size: 13px; font-weight: 600;
    padding: 12px 20px; border-bottom: 3px solid transparent;
}
#tab_btn:hover { color: #e2e8f0; background: #0f172a; }

#tab_btn_active {
    background: transparent; border: none;
    color: #3b82f6; font-size: 13px; font-weight: 700;
    padding: 12px 20px; border-bottom: 3px solid #3b82f6;
}

/* Toolbar */
#toolbar { background: #0f172a; border-bottom: 1px solid #1e293b; }

#btn_green {
    background: #16a34a; color: white;
    border: none; border-radius: 8px;
    padding: 8px 16px; font-size: 13px; font-weight: 700;
}
#btn_green:hover { background: #15803d; }

#btn_gray {
    background: #1e293b; color: #94a3b8;
    border: 1px solid #334155; border-radius: 8px;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
}
#btn_gray:hover { background: #334155; color: #e2e8f0; }

#btn_red {
    background: #450a0a; color: #f87171;
    border: 1px solid #7f1d1d; border-radius: 8px;
    padding: 7px 14px; font-size: 13px;
}
#btn_red:hover { background: #7f1d1d; }

#btn_filter {
    background: #1e293b; color: #94a3b8;
    border: 1px solid #334155; border-radius: 8px;
    padding: 7px 14px; font-size: 13px;
}
#btn_filter:hover { background: #334155; }

#sort_combo {
    background: #1e293b; color: #3b82f6;
    border: 1px solid #3b82f6; border-radius: 7px;
    padding: 6px 10px; font-size: 12px; font-weight: 600;
}
#sort_combo::drop-down { border: none; width: 20px; }
#sort_combo QAbstractItemView { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; }

#search_box {
    background: #1e293b; color: #e2e8f0;
    border: 1px solid #334155; border-radius: 8px;
    padding: 7px 12px; font-size: 13px;
}
#search_box:focus { border-color: #3b82f6; }

/* Bejegyzés sorok */
#entry_row {
    background: #1e293b; border: 1px solid #334155;
    border-radius: 10px;
}
#entry_row:hover { border-color: #475569; }

#entry_date { color: #e2e8f0; font-size: 13px; font-weight: 700; }
#entry_km   { color: #64748b; font-size: 12px; }
#entry_sub  { color: #94a3b8; font-size: 12px; }
#entry_amt  { color: #f1f5f9; font-size: 14px; font-weight: 800; }

#e_btn {
    background: transparent; border: 1px solid #334155;
    border-radius: 7px; color: #64748b;
    font-size: 13px; padding: 4px;
    min-width: 30px; max-width: 30px;
    min-height: 30px; max-height: 30px;
}
#e_btn:hover { background: #334155; color: #e2e8f0; }
#e_btn_del:hover { border-color: #ef4444; color: #ef4444; background: #450a0a; }

/* Scrollbar */
QScrollBar:vertical { background: #0f172a; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal { background: #0f172a; height: 8px; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #334155; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* Popup dialógusok */
QDialog { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
QLabel  { color: #94a3b8; font-size: 12px; }
QLineEdit, QDoubleSpinBox, QSpinBox, QDateEdit, QTextEdit, QComboBox {
    background: #0f172a; color: #e2e8f0;
    border: 1.5px solid #334155; border-radius: 8px;
    padding: 8px 12px; font-size: 13px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus,
QDateEdit:focus, QTextEdit:focus, QComboBox:focus { border-color: #3b82f6; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; selection-background-color: #1e3a5f; }
QSpinBox { padding-right: 20px; }
QDoubleSpinBox { padding-right: 20px; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: #475569; border: none; border-radius: 3px;
    width: 18px; height: 14px;
}
QSpinBox::up-button { subcontrol-position: top right; subcontrol-origin: border; top: 2px; right: 2px; border-radius: 3px 3px 0 0; }
QSpinBox::down-button { subcontrol-position: bottom right; subcontrol-origin: border; bottom: 2px; right: 2px; border-radius: 0 0 3px 3px; }
QDoubleSpinBox::up-button { subcontrol-position: top right; subcontrol-origin: border; top: 2px; right: 2px; border-radius: 3px 3px 0 0; }
QDoubleSpinBox::down-button { subcontrol-position: bottom right; subcontrol-origin: border; bottom: 2px; right: 2px; border-radius: 0 0 3px 3px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: #64748b; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: none; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid #e2e8f0; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: none; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #e2e8f0; }
QDateEdit::up-button, QDateEdit::down-button { background: #334155; border: none; }
QDateEdit::drop-down { background: #475569; border: none; width: 24px; border-radius: 0 6px 6px 0; }

#popup_title { color: #f1f5f9; font-size: 16px; font-weight: 700; }
#save_btn {
    background: #f97316; color: white;
    border: none; border-radius: 8px;
    padding: 10px; font-size: 14px; font-weight: 700;
}
#save_btn:hover { background: #ea580c; }
#cancel_btn {
    background: #334155; color: #94a3b8;
    border: none; border-radius: 8px;
    padding: 10px; font-size: 13px;
}
#cancel_btn:hover { background: #475569; color: #e2e8f0; }

/* Üres állapot */
#empty_label { color: #475569; font-size: 14px; }

/* Bejegyzés sor chip-edit gombok */
#chip_edit_btn {
    background: #334155; border: none; border-radius: 4px;
    color: #94a3b8; font-size: 11px;
    min-width: 22px; max-width: 22px;
    min-height: 22px; max-height: 22px;
}
#chip_edit_btn:hover { background: #475569; color: white; }
#chip_del_btn {
    background: #450a0a; border: none; border-radius: 4px;
    color: #f87171; font-size: 11px;
    min-width: 22px; max-width: 22px;
    min-height: 22px; max-height: 22px;
}
#chip_del_btn:hover { background: #7f1d1d; }

/* Chip neve/rsz/km labelek */
#chip_name { color: #f1f5f9; font-size: 14px; font-weight: 800; background: transparent; }
#chip_rsz  { color: #64748b; font-size: 11px; background: transparent; }
#chip_km   { color: #3b82f6; font-size: 12px; font-weight: 700; background: transparent; }

/* Content area */
#content_area { background: #0f172a; }

/* Scroll area */
QScrollArea { border: none; background: #0f172a; }
QScrollArea > QWidget > QWidget { background: #0f172a; }
"""

LIGHT_QSS = """
QMainWindow, QDialog { background: #f8fafc; }
QWidget { background: transparent; color: #0f172a; font-family: 'Segoe UI'; font-size: 13px; }

#topbar { background: #ffffff; border-bottom: 1px solid #e2e8f0; }
#logo   { color: #f97316; font-size: 20px; font-weight: 900; background: transparent; }

#tb_btn {
    background: #f1f5f9; color: #374151;
    border: 1px solid #e2e8f0; border-radius: 7px;
    padding: 6px 14px; font-size: 12px; font-weight: 600;
}
#tb_btn:hover { background: #e2e8f0; }

#chipbar { background: #f8fafc; border-bottom: 1px solid #e2e8f0; }

#car_chip {
    background: #ffffff; border: 2px solid #e2e8f0;
    border-radius: 10px; padding: 8px 14px;
}
#car_chip:hover { border-color: #3b82f6; }

#car_chip_active {
    background: #eff6ff; border: 2px solid #3b82f6;
    border-radius: 10px; padding: 8px 14px;
}

#chip_add {
    background: transparent; border: 2px dashed #e2e8f0;
    border-radius: 10px; color: #94a3b8;
    font-size: 13px; font-weight: 600;
}
#chip_add:hover { border-color: #f97316; color: #f97316; }

#tabbar { background: #ffffff; border-bottom: 2px solid #e2e8f0; }

#tab_btn {
    background: transparent; border: none;
    color: #94a3b8; font-size: 13px; font-weight: 600;
    padding: 12px 20px; border-bottom: 3px solid transparent;
}
#tab_btn:hover { color: #374151; }

#tab_btn_active {
    background: transparent; border: none;
    color: #3b82f6; font-size: 13px; font-weight: 700;
    padding: 12px 20px; border-bottom: 3px solid #3b82f6;
}

#toolbar { background: #f8fafc; border-bottom: 1px solid #f1f5f9; }

#btn_green {
    background: #22c55e; color: white;
    border: none; border-radius: 8px;
    padding: 8px 16px; font-size: 13px; font-weight: 700;
}
#btn_green:hover { background: #16a34a; }

#btn_gray {
    background: #f1f5f9; color: #374151;
    border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
}
#btn_gray:hover { background: #e2e8f0; }

#btn_red {
    background: #fee2e2; color: #dc2626;
    border: 1px solid #fecaca; border-radius: 8px;
    padding: 7px 14px; font-size: 13px;
}
#btn_red:hover { background: #fecaca; }

#btn_filter {
    background: #f1f5f9; color: #374151;
    border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 7px 14px; font-size: 13px;
}
#btn_filter:hover { background: #e2e8f0; }

#sort_combo {
    background: #eff6ff; color: #3b82f6;
    border: 1px solid #3b82f6; border-radius: 7px;
    padding: 6px 10px; font-size: 12px; font-weight: 600;
}
#sort_combo::drop-down { border: none; width: 20px; }

#search_box {
    background: #ffffff; color: #0f172a;
    border: 1.5px solid #e2e8f0; border-radius: 8px;
    padding: 7px 12px; font-size: 13px;
}
#search_box:focus { border-color: #3b82f6; }

#entry_row {
    background: #ffffff; border: 1px solid #f1f5f9;
    border-radius: 10px;
}
#entry_row:hover { border-color: #e2e8f0; }

#entry_date { color: #1e293b; font-size: 13px; font-weight: 700; }
#entry_km   { color: #94a3b8; font-size: 12px; }
#entry_sub  { color: #64748b; font-size: 12px; }
#entry_amt  { color: #0f172a; font-size: 14px; font-weight: 800; }

#e_btn {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 7px; color: #94a3b8;
    font-size: 13px; padding: 4px;
    min-width: 30px; max-width: 30px;
    min-height: 30px; max-height: 30px;
}
#e_btn:hover { background: #e2e8f0; color: #374151; }
#e_btn_del:hover { border-color: #ef4444; color: #ef4444; background: #fee2e2; }

QScrollBar:vertical { background: #f1f5f9; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QDialog { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; }
QLabel  { color: #64748b; font-size: 12px; }
QLineEdit, QDoubleSpinBox, QSpinBox, QDateEdit, QTextEdit, QComboBox {
    background: #f8fafc; color: #0f172a;
    border: 1.5px solid #e2e8f0; border-radius: 8px;
    padding: 8px 12px; font-size: 13px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus,
QDateEdit:focus, QTextEdit:focus, QComboBox:focus { border-color: #3b82f6; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #ffffff; color: #0f172a; border: 1px solid #e2e8f0; selection-background-color: #eff6ff; }
QSpinBox { padding-right: 20px; }
QDoubleSpinBox { padding-right: 20px; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: #e2e8f0; border: none;
    width: 18px; height: 14px;
}
QSpinBox::up-button { subcontrol-position: top right; subcontrol-origin: border; top: 2px; right: 2px; border-radius: 3px 3px 0 0; }
QSpinBox::down-button { subcontrol-position: bottom right; subcontrol-origin: border; bottom: 2px; right: 2px; border-radius: 0 0 3px 3px; }
QDoubleSpinBox::up-button { subcontrol-position: top right; subcontrol-origin: border; top: 2px; right: 2px; border-radius: 3px 3px 0 0; }
QDoubleSpinBox::down-button { subcontrol-position: bottom right; subcontrol-origin: border; bottom: 2px; right: 2px; border-radius: 0 0 3px 3px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: #cbd5e1; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: none; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid #374151; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: none; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #374151; }
QDateEdit::drop-down { background: #e2e8f0; border: none; width: 24px; border-radius: 0 6px 6px 0; }

#popup_title { color: #0f172a; font-size: 16px; font-weight: 700; }
#save_btn {
    background: #f97316; color: white;
    border: none; border-radius: 8px;
    padding: 10px; font-size: 14px; font-weight: 700;
}
#save_btn:hover { background: #ea580c; }
#cancel_btn {
    background: #f1f5f9; color: #374151;
    border: none; border-radius: 8px;
    padding: 10px; font-size: 13px;
}
#cancel_btn:hover { background: #e2e8f0; }

#empty_label { color: #cbd5e1; font-size: 14px; }

#chip_edit_btn {
    background: #f1f5f9; border: none; border-radius: 4px;
    color: #64748b; font-size: 11px;
    min-width: 22px; max-width: 22px;
    min-height: 22px; max-height: 22px;
}
#chip_edit_btn:hover { background: #e2e8f0; color: #374151; }
#chip_del_btn {
    background: #fee2e2; border: none; border-radius: 4px;
    color: #dc2626; font-size: 11px;
    min-width: 22px; max-width: 22px;
    min-height: 22px; max-height: 22px;
}
#chip_del_btn:hover { background: #fecaca; }

#chip_name { color: #0f172a; font-size: 14px; font-weight: 800; background: transparent; }
#chip_rsz  { color: #94a3b8; font-size: 11px; background: transparent; }
#chip_km   { color: #3b82f6; font-size: 12px; font-weight: 700; background: transparent; }

#content_area { background: #f8fafc; }

QScrollArea { border: none; background: #f8fafc; }
QScrollArea > QWidget > QWidget { background: #f8fafc; }
"""

# ══════════════════════════════════════════════════════════════════════════════
# Jármű Popup
# ══════════════════════════════════════════════════════════════════════════════
class CarDialog(QDialog):
    def __init__(self, parent=None, car_id=None):
        super().__init__(parent)
        self.car_id = car_id
        self.setWindowTitle("Jármű szerkesztése" if car_id else "Új jármű")
        self.setFixedWidth(420)
        self.setModal(True)
        self._build()
        if car_id:
            self._load()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title = QLabel("Jármű szerkesztése" if self.car_id else "Új jármű")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.f_marka   = QLineEdit(); self.f_marka.setPlaceholderText("pl. Seat")
        self.f_tipus   = QLineEdit(); self.f_tipus.setPlaceholderText("pl. Ibiza")
        self.f_rsz     = QLineEdit(); self.f_rsz.setPlaceholderText("pl. SWY-130")
        self.f_evjarat = QLineEdit(); self.f_evjarat.setPlaceholderText("pl. 2018")
        self.f_km      = QSpinBox();  self.f_km.setRange(0, 9_999_999); self.f_km.setSuffix(" km")
        self.f_muszaki = QLineEdit(); self.f_muszaki.setPlaceholderText("ÉÉÉÉ.HH.NN")
        self.f_olaj    = QSpinBox();  self.f_olaj.setRange(1000, 99_999); self.f_olaj.setSuffix(" km"); self.f_olaj.setValue(10000)

        for lbl, w in [
            ("Márka *",    self.f_marka),
            ("Típus *",    self.f_tipus),
            ("Rendszám",   self.f_rsz),
            ("Évjárat",    self.f_evjarat),
            ("Aktuális KM",self.f_km),
            ("Műszaki lejárata", self.f_muszaki),
            ("Olajcsere periódus", self.f_olaj),
        ]:
            lbl_w = QLabel(lbl)
            form.addRow(lbl_w, w)

        lay.addLayout(form)
        lay.addSpacing(6)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Mégse"); cancel.setObjectName("cancel_btn")
        save   = QPushButton("Mentés"); save.setObjectName("save_btn")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def _load(self):
        with get_db() as conn:
            r = conn.execute(
                "SELECT marka,tipus,rendszam,evjarat,km_allas,muszaki_lejarat,olaj_intervallum "
                "FROM autok WHERE id=?", (self.car_id,)
            ).fetchone()
        if r:
            self.f_marka.setText(r["marka"] or "")
            self.f_tipus.setText(r["tipus"] or "")
            self.f_rsz.setText(r["rendszam"] or "")
            self.f_evjarat.setText(str(r["evjarat"] or ""))
            self.f_km.setValue(int(r["km_allas"] or 0))
            self.f_muszaki.setText(r["muszaki_lejarat"] or "")
            self.f_olaj.setValue(int(r["olaj_intervallum"] or 10000))

    def _save(self):
        marka = self.f_marka.text().strip()
        tipus = self.f_tipus.text().strip()
        if not marka or not tipus:
            QMessageBox.warning(self, "Hiányzó adat", "Márka és Típus megadása kötelező!")
            return
        vals = (marka, tipus, self.f_rsz.text().strip(),
                self.f_evjarat.text().strip(), self.f_km.value(),
                self.f_muszaki.text().strip(), self.f_olaj.value())
        with get_db() as conn:
            if self.car_id:
                conn.execute(
                    "UPDATE autok SET marka=?,tipus=?,rendszam=?,evjarat=?,km_allas=?,muszaki_lejarat=?,olaj_intervallum=? WHERE id=?",
                    (*vals, self.car_id)
                )
            else:
                conn.execute(
                    "INSERT INTO autok (marka,tipus,rendszam,evjarat,km_allas,muszaki_lejarat,olaj_intervallum) VALUES (?,?,?,?,?,?,?)",
                    vals
                )
        self.accept()

# ══════════════════════════════════════════════════════════════════════════════
# Bejegyzés Popup
# ══════════════════════════════════════════════════════════════════════════════
class EntryDialog(QDialog):
    def __init__(self, parent=None, auto_id=None, kategoria="Tankolás", entry_id=None, prefill=None):
        super().__init__(parent)
        self.auto_id   = auto_id
        self.kategoria = kategoria
        self.entry_id  = entry_id
        self.setWindowTitle("Bejegyzés szerkesztése" if entry_id else "Új bejegyzés")
        self.setFixedWidth(440)
        self.setModal(True)
        self._build()
        if entry_id:
            self._load()
        elif prefill:
            self._prefill(prefill)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        title = QLabel(f"{'✏️ Szerkesztés' if self.entry_id else '➕ Új bejegyzés'} – {self.kategoria}")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.f_datum = QLineEdit()
        self.f_datum.setPlaceholderText("ÉÉÉÉ.HH.NN")
        self.f_datum.setText(datetime.today().strftime("%Y.%m.%d"))

        self.f_km    = QSpinBox(); self.f_km.setRange(0, 9_999_999); self.f_km.setSuffix(" km")
        self.f_osszeg= QDoubleSpinBox(); self.f_osszeg.setRange(0, 99_999_999); self.f_osszeg.setSuffix(" Ft"); self.f_osszeg.setDecimals(0)
        self.f_megj  = QLineEdit(); self.f_megj.setPlaceholderText("Megjegyzés...")

        form.addRow(QLabel("Dátum *"), self.f_datum)
        form.addRow(QLabel("KM állás"), self.f_km)
        form.addRow(QLabel("Összeg (Ft)"), self.f_osszeg)

        # Tankolás extra mezők
        self.fuel_widgets = []
        if self.kategoria == "Tankolás":
            self.f_liter = QDoubleSpinBox(); self.f_liter.setRange(0,999); self.f_liter.setSuffix(" L"); self.f_liter.setDecimals(2)
            self.f_arl   = QDoubleSpinBox(); self.f_arl.setRange(0,9999); self.f_arl.setSuffix(" Ft/L"); self.f_arl.setDecimals(1)
            self.f_kut   = QLineEdit(); self.f_kut.setPlaceholderText("pl. MOL Kecskemét")
            form.addRow(QLabel("Mennyiség"), self.f_liter)
            form.addRow(QLabel("Egységár"), self.f_arl)
            form.addRow(QLabel("Benzinkút"), self.f_kut)
            self.fuel_widgets = [self.f_liter, self.f_arl, self.f_kut]

            # Auto összeg számítás
            self.f_liter.valueChanged.connect(self._calc_total)
            self.f_arl.valueChanged.connect(self._calc_total)

        form.addRow(QLabel("Megjegyzés"), self.f_megj)
        lay.addLayout(form)
        lay.addSpacing(6)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Mégse"); cancel.setObjectName("cancel_btn")
        save   = QPushButton("Mentés"); save.setObjectName("save_btn")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def _calc_total(self):
        if hasattr(self, "f_liter") and hasattr(self, "f_arl"):
            total = self.f_liter.value() * self.f_arl.value()
            if total > 0:
                self.f_osszeg.setValue(round(total))

    def _load(self):
        with get_db() as conn:
            r = conn.execute(
                "SELECT datum,osszeg,km_allas,mennyiseg_liter,egysegar_ft_l,benzinkut,megjegyzes "
                "FROM szerviz_adatok WHERE id=?", (self.entry_id,)
            ).fetchone()
        if r:
            self.f_datum.setText(r["datum"] or "")
            self.f_osszeg.setValue(float(r["osszeg"] or 0))
            self.f_km.setValue(int(r["km_allas"] or 0))
            self.f_megj.setText(r["megjegyzes"] or "")
            if self.kategoria == "Tankolás":
                self.f_liter.setValue(float(r["mennyiseg_liter"] or 0))
                self.f_arl.setValue(float(r["egysegar_ft_l"] or 0))
                self.f_kut.setText(r["benzinkut"] or "")

    def _prefill(self, d):
        if "datum" in d:    self.f_datum.setText(d["datum"])
        if "km_allas" in d: self.f_km.setValue(int(d["km_allas"]))
        if "osszeg" in d:   self.f_osszeg.setValue(float(d["osszeg"]))

    def _save(self):
        datum = self.f_datum.text().strip()
        if not datum:
            QMessageBox.warning(self, "Hiányzó adat", "A dátum megadása kötelező!")
            return
        liter = getattr(self, "f_liter", None)
        arl   = getattr(self, "f_arl", None)
        kut   = getattr(self, "f_kut", None)
        vals = (
            datum,
            self.f_osszeg.value(),
            self.f_km.value(),
            self.kategoria,
            liter.value() if liter else None,
            arl.value()   if arl   else None,
            kut.text().strip() if kut else None,
            self.f_megj.text().strip(),
        )
        with get_db() as conn:
            if self.entry_id:
                conn.execute(
                    "UPDATE szerviz_adatok SET datum=?,osszeg=?,km_allas=?,kategoria=?,"
                    "mennyiseg_liter=?,egysegar_ft_l=?,benzinkut=?,megjegyzes=? WHERE id=?",
                    (*vals, self.entry_id)
                )
            else:
                conn.execute(
                    "INSERT INTO szerviz_adatok "
                    "(datum,osszeg,km_allas,kategoria,mennyiseg_liter,egysegar_ft_l,benzinkut,megjegyzes,auto_id)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (*vals, self.auto_id)
                )
        self.accept()

# ══════════════════════════════════════════════════════════════════════════════
# Bejegyzés sor widget
# ══════════════════════════════════════════════════════════════════════════════
class EntryRow(QFrame):
    edit_requested   = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    copy_requested   = pyqtSignal(int)

    def __init__(self, row_data, kategoria, parent=None):
        super().__init__(parent)
        self.row_data  = row_data
        self.entry_id  = row_data["id"]
        self.kategoria = kategoria
        self.setObjectName("entry_row")
        self._build()

    def _build(self):
        r = self.row_data
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 11, 14, 11)
        lay.setSpacing(0)

        # Ikon
        ikon_map = {"Tankolás": "⛽", "Karbantartás": "🔧", "Biztosítás": "🛡️", "Egyéb": "📦"}
        ikon = QLabel(ikon_map.get(self.kategoria, "📦"))
        ikon.setFixedWidth(24)
        ikon.setObjectName("entry_sub")
        lay.addWidget(ikon)
        lay.addSpacing(10)

        # Dátum
        date_lbl = QLabel(r["datum"] or "")
        date_lbl.setObjectName("entry_date")
        date_lbl.setFixedWidth(88)
        lay.addWidget(date_lbl)

        # KM
        km_str = f'{r["km_allas"]:,} km'.replace(",", " ") if r["km_allas"] else "—"
        km_lbl = QLabel(km_str)
        km_lbl.setObjectName("entry_km")
        km_lbl.setFixedWidth(88)
        lay.addWidget(km_lbl)

        # Részletek
        parts = []
        if r["mennyiseg_liter"]: parts.append(f'{r["mennyiseg_liter"]:.2f} L')
        if r["egysegar_ft_l"]:   parts.append(f'{r["egysegar_ft_l"]:.1f} Ft/L')
        if r["benzinkut"]:       parts.append(f'📍 {r["benzinkut"]}')
        if r["megjegyzes"] and not parts: parts.append(r["megjegyzes"])
        sub_lbl = QLabel("  ·  ".join(parts) if parts else (r["megjegyzes"] or ""))
        sub_lbl.setObjectName("entry_sub")
        lay.addWidget(sub_lbl, stretch=1)

        # Összeg
        amt = f'{int(r["osszeg"]):,} Ft'.replace(",", " ") if r["osszeg"] else "—"
        amt_lbl = QLabel(amt)
        amt_lbl.setObjectName("entry_amt")
        amt_lbl.setFixedWidth(90)
        amt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(amt_lbl)
        lay.addSpacing(14)

        # Gombok
        for txt, obj, sig in [
            ("📋", "e_btn", self.copy_requested),
            ("✏️", "e_btn", self.edit_requested),
            ("🗑️", "e_btn_del", self.delete_requested),
        ]:
            btn = QPushButton(txt)
            btn.setObjectName(obj)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda _, s=sig: s.emit(self.entry_id))
            lay.addWidget(btn)
            lay.addSpacing(3)

# ══════════════════════════════════════════════════════════════════════════════
# Tab tartalom (bejegyzés lista)
# ══════════════════════════════════════════════════════════════════════════════
class TabContent(QWidget):
    def __init__(self, auto_id_getter, kategoria, parent=None):
        super().__init__(parent)
        self.auto_id_getter = auto_id_getter
        self.kategoria = kategoria
        self._search_text = ""
        self._sort = "datum DESC"
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Toolbar
        toolbar = QFrame(); toolbar.setObjectName("toolbar"); toolbar.setFixedHeight(54)
        tb_lay = QHBoxLayout(toolbar); tb_lay.setContentsMargins(16, 0, 16, 0); tb_lay.setSpacing(8)

        self.btn_new = QPushButton("➕  Új bejegyzés"); self.btn_new.setObjectName("btn_green")
        self.btn_csv = QPushButton("📥  Import CSV"); self.btn_csv.setObjectName("btn_gray")

        self.sort_cb = QComboBox(); self.sort_cb.setObjectName("sort_combo")
        self.sort_cb.addItems(["📅 Dátum (újabb)", "📅 Dátum (régebbi)", "💰 Összeg (nagy→kis)", "🛣️ KM (nagy→kis)"])
        self.sort_cb.currentIndexChanged.connect(self._on_sort_change)

        self.search = QLineEdit(); self.search.setObjectName("search_box")
        self.search.setPlaceholderText("🔍  Keresés..."); self.search.setFixedWidth(200)
        self.search.textChanged.connect(self._on_search)

        self.btn_clear = QPushButton("🗑️  Törlés"); self.btn_clear.setObjectName("btn_red")
        self.btn_clear.clicked.connect(lambda: self.search.clear())

        tb_lay.addWidget(self.btn_new)
        tb_lay.addWidget(self.btn_csv)
        tb_lay.addWidget(self.sort_cb)
        tb_lay.addStretch()
        tb_lay.addWidget(self.search)
        tb_lay.addWidget(self.btn_clear)
        lay.addWidget(toolbar)

        # Scroll area bejegyzéseknek
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("content_area")
        self.list_widget = QWidget(); self.list_widget.setObjectName("content_area")
        self.list_lay = QVBoxLayout(self.list_widget)
        self.list_lay.setContentsMargins(16, 10, 16, 16)
        self.list_lay.setSpacing(7)
        self.list_lay.addStretch()
        self.scroll.setWidget(self.list_widget)
        lay.addWidget(self.scroll)

        self.btn_new.clicked.connect(self._new_entry)
        self.btn_csv.clicked.connect(self._import_csv)

    def _sort_key(self):
        idx = self.sort_cb.currentIndex()
        return ["datum DESC","datum ASC","osszeg DESC","km_allas DESC"][idx]

    def _on_sort_change(self): self.refresh()
    def _on_search(self, txt): self._search_text = txt; self.refresh()

    def refresh(self):
        auto_id = self.auto_id_getter()
        # Töröljük a régi sorokat (a stretch előtti elemeket)
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not auto_id:
            return

        sort = self._sort_key()
        q = f"""SELECT id,datum,osszeg,km_allas,kategoria,
                       mennyiseg_liter,egysegar_ft_l,benzinkut,megjegyzes,kep_utvonal
                FROM szerviz_adatok
                WHERE auto_id=? AND kategoria=?
                ORDER BY {sort}"""
        with get_db() as conn:
            rows = conn.execute(q, (auto_id, self.kategoria)).fetchall()

        txt = self._search_text.lower()
        if txt:
            rows = [r for r in rows if txt in (r["datum"] or "").lower()
                    or txt in (r["megjegyzes"] or "").lower()
                    or txt in (r["benzinkut"] or "").lower()]

        if not rows:
            lbl = QLabel("Nincs bejegyzés ebben a kategóriában.")
            lbl.setObjectName("empty_label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_lay.insertWidget(0, lbl)
            return

        for r in rows:
            row_w = EntryRow(r, self.kategoria)
            row_w.edit_requested.connect(self._edit_entry)
            row_w.delete_requested.connect(self._delete_entry)
            row_w.copy_requested.connect(self._copy_entry)
            self.list_lay.insertWidget(self.list_lay.count()-1, row_w)

    def _new_entry(self):
        dlg = EntryDialog(self, auto_id=self.auto_id_getter(), kategoria=self.kategoria)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _edit_entry(self, eid):
        dlg = EntryDialog(self, auto_id=self.auto_id_getter(), kategoria=self.kategoria, entry_id=eid)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _copy_entry(self, eid):
        with get_db() as conn:
            r = conn.execute("SELECT * FROM szerviz_adatok WHERE id=?", (eid,)).fetchone()
        if r:
            prefill = {"datum": datetime.today().strftime("%Y.%m.%d"),
                       "km_allas": r["km_allas"], "osszeg": r["osszeg"]}
            dlg = EntryDialog(self, auto_id=self.auto_id_getter(), kategoria=self.kategoria, prefill=prefill)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.refresh()

    def _delete_entry(self, eid):
        ret = QMessageBox.question(self, "Törlés", "Biztosan törlöd ezt a bejegyzést?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            with get_db() as conn:
                conn.execute("DELETE FROM szerviz_adatok WHERE id=?", (eid,))
            self.refresh()

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV importálása", "", "CSV fájlok (*.csv)")
        if not path:
            return
        auto_id = self.auto_id_getter()
        if not auto_id:
            QMessageBox.warning(self, "Hiba", "Nincs kiválasztott jármű!")
            return

        # Megkérdezzük: törölje-e a meglévőket és írja felül?
        ret = QMessageBox.question(
            self, "Import mód",
            "Töröld a meglévő bejegyzéseket ebből a kategóriából,\n"
            "és importáld újra? (Ajánlott újraimportálásnál)\n\n"
            "Igen = Felülír (töröl + újraimportál)\n"
            "Nem = Hozzáfűz (meglévők megmaradnak)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        if ret == QMessageBox.StandardButton.Cancel:
            return

        count = 0
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows_data = list(reader)

            with get_db() as conn:
                if ret == QMessageBox.StandardButton.Yes:
                    conn.execute(
                        "DELETE FROM szerviz_adatok WHERE auto_id=? AND kategoria=?",
                        (auto_id, self.kategoria)
                    )

                for row in rows_data:
                    datum     = row.get("datum", "").strip()
                    osszeg    = float(row.get("osszeg", 0) or 0)
                    km        = int(float(row.get("km_allas", 0) or 0))
                    megj      = row.get("megjegyzes", "").strip()
                    liter_s   = row.get("mennyiseg_liter", "").strip()
                    arl_s     = row.get("egysegar_ft_l", "").strip()
                    benzinkut = row.get("benzinkut", "").strip() or None
                    liter     = float(liter_s) if liter_s else None
                    arl       = float(arl_s)   if arl_s   else None
                    conn.execute(
                        "INSERT INTO szerviz_adatok "
                        "(auto_id,datum,osszeg,km_allas,kategoria,"
                        "mennyiseg_liter,egysegar_ft_l,benzinkut,megjegyzes) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (auto_id, datum, osszeg, km, self.kategoria,
                         liter, arl, benzinkut, megj)
                    )
                    count += 1

            QMessageBox.information(self, "✅ Kész", f"{count} bejegyzés importálva!")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Import hiba:\n{e}")

# ══════════════════════════════════════════════════════════════════════════════
# Főablak
# ══════════════════════════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Beállítások")
        self.setFixedWidth(400)
        self.setModal(True)
        self.cfg = load_config()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title = QLabel("⚙️ Beállítások")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        # Sötét mód
        self.dark_cb = QCheckBox("Sötét mód")
        self.dark_cb.setChecked(self.cfg.get("dark_mode", True))
        self.dark_cb.setStyleSheet("color: #e2e8f0; font-size: 13px;")
        form.addRow(QLabel("Megjelenés:"), self.dark_cb)

        # Olajcsere intervallum
        self.olaj_spin = QSpinBox()
        self.olaj_spin.setRange(1000, 50000)
        self.olaj_spin.setSingleStep(1000)
        self.olaj_spin.setSuffix(" km")
        self.olaj_spin.setValue(self.cfg.get("default_oil_interval", 10000))
        form.addRow(QLabel("Alapértelmezett olajcsere:"), self.olaj_spin)

        # Műszaki figyelmeztetés
        self.muszaki_spin = QSpinBox()
        self.muszaki_spin.setRange(7, 90)
        self.muszaki_spin.setSuffix(" nap")
        self.muszaki_spin.setValue(self.cfg.get("muszaki_warning_days", 30))
        form.addRow(QLabel("Műszaki figyelmeztetés:"), self.muszaki_spin)

        # Biztosítás figyelmeztetés
        self.biz_spin = QSpinBox()
        self.biz_spin.setRange(7, 90)
        self.biz_spin.setSuffix(" nap")
        self.biz_spin.setValue(self.cfg.get("biztositas_warning_days", 30))
        form.addRow(QLabel("Biztosítás figyelmeztetés:"), self.biz_spin)

        lay.addLayout(form)
        lay.addSpacing(6)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Mégse"); cancel.setObjectName("cancel_btn")
        save   = QPushButton("Mentés"); save.setObjectName("save_btn")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def _save(self):
        self.cfg["dark_mode"] = self.dark_cb.isChecked()
        self.cfg["default_oil_interval"] = self.olaj_spin.value()
        self.cfg["muszaki_warning_days"] = self.muszaki_spin.value()
        self.cfg["biztositas_warning_days"] = self.biz_spin.value()
        save_config(self.cfg)
        self.accept()

    def get_dark_mode(self):
        return self.dark_cb.isChecked()


# ══════════════════════════════════════════════════════════════════════════════
# Backup dialog
# ══════════════════════════════════════════════════════════════════════════════
class BackupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💾 Backup")
        self.setFixedWidth(480)
        self.setMinimumHeight(360)
        self.setModal(True)
        self._build()
        self._list_backups()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        title = QLabel("💾 Backup kezelő")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        btn_row = QHBoxLayout()
        btn_create = QPushButton("➕ Backup létrehozása"); btn_create.setObjectName("btn_green")
        btn_import = QPushButton("📥 Importálás ZIP-ből"); btn_import.setObjectName("btn_gray")
        btn_create.clicked.connect(self._create_backup)
        btn_import.clicked.connect(self._import_backup)
        btn_row.addWidget(btn_create)
        btn_row.addWidget(btn_import)
        lay.addLayout(btn_row)

        self.list_widget = QWidget()
        self.list_lay = QVBoxLayout(self.list_widget)
        self.list_lay.setContentsMargins(0,0,0,0)
        self.list_lay.setSpacing(6)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(self.list_widget)
        lay.addWidget(scroll)

        close_btn = QPushButton("Bezárás"); close_btn.setObjectName("cancel_btn")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

    def _list_backups(self):
        for i in reversed(range(self.list_lay.count())):
            w = self.list_lay.itemAt(i).widget()
            if w: w.deleteLater()

        backups = sorted(Path(BACKUP_DIR).glob("*.zip"), reverse=True)
        if not backups:
            lbl = QLabel("Nincs mentett backup.")
            lbl.setObjectName("empty_label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_lay.addWidget(lbl)
            return

        for bp in backups:
            row = QFrame(); row.setObjectName("entry_row")
            r_lay = QHBoxLayout(row); r_lay.setContentsMargins(12,8,12,8)
            size_kb = bp.stat().st_size // 1024
            lbl = QLabel(f"📦 {bp.name}  ({size_kb} KB)")
            lbl.setObjectName("entry_sub")
            r_lay.addWidget(lbl, stretch=1)
            restore_btn = QPushButton("♻️ Visszaállítás"); restore_btn.setObjectName("btn_gray")
            restore_btn.clicked.connect(lambda _, p=bp: self._restore(p))
            del_btn = QPushButton("🗑️"); del_btn.setObjectName("e_btn_del"); del_btn.setFixedSize(30,30)
            del_btn.clicked.connect(lambda _, p=bp: self._delete_backup(p))
            r_lay.addWidget(restore_btn)
            r_lay.addWidget(del_btn)
            self.list_lay.addWidget(row)

    def _create_backup(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(BACKUP_DIR, f"wheelbook_backup_{ts}.zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(DB_PATH, "auto_naplo.db")
                if os.path.exists(CONFIG_PATH):
                    zf.write(CONFIG_PATH, "config.json")
            QMessageBox.information(self, "✅ Kész", f"Backup létrehozva:\n{os.path.basename(zip_path)}")
            self._list_backups()
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Backup hiba:\n{e}")

    def _import_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Backup importálása", "", "ZIP fájlok (*.zip)")
        if not path:
            return
        ret = QMessageBox.question(self, "Visszaállítás",
                                   "Ez felülírja az aktuális adatbázist!\nBiztosan folytatod?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._do_restore(path)

    def _restore(self, zip_path):
        ret = QMessageBox.question(self, "Visszaállítás",
                                   f"Visszaállítod ezt a backupot?\n{zip_path.name}\n\nAz aktuális adatok felülíródnak!",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self._do_restore(str(zip_path))

    def _do_restore(self, zip_path):
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                if "auto_naplo.db" in zf.namelist():
                    zf.extract("auto_naplo.db", DATA_DIR)
                if "config.json" in zf.namelist():
                    zf.extract("config.json", DATA_DIR)
            QMessageBox.information(self, "✅ Kész", "Adatok visszaállítva!\nIndítsd újra az alkalmazást.")
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"Visszaállítási hiba:\n{e}")

    def _delete_backup(self, zip_path):
        ret = QMessageBox.question(self, "Törlés", f"Törlöd ezt a backupot?\n{zip_path.name}",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            zip_path.unlink()
            self._list_backups()


# ══════════════════════════════════════════════════════════════════════════════
# Kategória kezelő
# ══════════════════════════════════════════════════════════════════════════════
class CategoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📂 Kategóriák")
        self.setFixedWidth(440)
        self.setMinimumHeight(400)
        self.setModal(True)
        self._build()
        self._load()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        title = QLabel("📂 Kategória kezelő")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        # Új kategória sor
        add_row = QHBoxLayout()
        self.new_name = QLineEdit(); self.new_name.setPlaceholderText("Új kategória neve, pl. Parkolás")
        self.new_icon = QLineEdit(); self.new_icon.setPlaceholderText("🅿️"); self.new_icon.setFixedWidth(60)
        add_btn = QPushButton("➕ Hozzáadás"); add_btn.setObjectName("btn_green")
        add_btn.clicked.connect(self._add_cat)
        add_row.addWidget(self.new_name)
        add_row.addWidget(self.new_icon)
        add_row.addWidget(add_btn)
        lay.addLayout(add_row)

        # Lista
        self.list_widget = QWidget()
        is_dark_dlg = load_config().get("dark_mode", True)
        dlg_bg = "#0f172a" if is_dark_dlg else "#f8fafc"
        self.list_widget.setStyleSheet(f"background: {dlg_bg};")
        self.list_lay = QVBoxLayout(self.list_widget)
        self.list_lay.setContentsMargins(0,0,0,0)
        self.list_lay.setSpacing(5)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background: {dlg_bg}; border: none; }}")
        scroll.setWidget(self.list_widget)
        lay.addWidget(scroll)

        close_btn = QPushButton("Bezárás"); close_btn.setObjectName("save_btn")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

    def _load(self):
        for i in reversed(range(self.list_lay.count())):
            w = self.list_lay.itemAt(i).widget()
            if w: w.deleteLater()

        with get_db() as conn:
            cats = conn.execute("SELECT id,nev,ikon,alap FROM kategoriak ORDER BY alap DESC, id").fetchall()

        for cat in cats:
            row = QFrame(); row.setObjectName("entry_row")
            r_lay = QHBoxLayout(row); r_lay.setContentsMargins(12,6,12,6); r_lay.setSpacing(8)

            lbl = QLabel(f'{cat["ikon"]}  {cat["nev"]}')
            lbl.setObjectName("entry_date")
            r_lay.addWidget(lbl, stretch=1)

            if cat["alap"]:
                base_lbl = QLabel("alap")
                is_dark_cat = load_config().get("dark_mode", True)
                badge_bg  = "#1e293b" if is_dark_cat else "#e2e8f0"
                badge_col = "#64748b" if is_dark_cat else "#475569"
                base_lbl.setStyleSheet(f"color: {badge_col}; font-size: 11px; padding: 2px 6px; background: {badge_bg}; border-radius: 4px;")
                r_lay.addWidget(base_lbl)
            else:
                del_btn = QPushButton("🗑️"); del_btn.setObjectName("e_btn_del"); del_btn.setFixedSize(30,30)
                del_btn.clicked.connect(lambda _, cid=cat["id"]: self._del_cat(cid))
                r_lay.addWidget(del_btn)

            self.list_lay.addWidget(row)

    def _add_cat(self):
        name = self.new_name.text().strip()
        icon = self.new_icon.text().strip() or "📦"
        if not name:
            QMessageBox.warning(self, "Hiba", "Add meg a kategória nevét!")
            return
        try:
            with get_db() as conn:
                conn.execute("INSERT INTO kategoriak (nev,ikon,alap) VALUES (?,?,0)", (name, icon))
            self.new_name.clear(); self.new_icon.clear()
            self._load()
        except Exception as e:
            QMessageBox.warning(self, "Hiba", f"Már létezik ilyen nevű kategória!\n{e}")

    def _del_cat(self, cid):
        ret = QMessageBox.question(self, "Törlés", "Biztosan törlöd ezt a kategóriát?\n(A bejegyzések megmaradnak.)",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            with get_db() as conn:
                conn.execute("DELETE FROM kategoriak WHERE id=? AND alap=0", (cid,))
            self._load()


# ══════════════════════════════════════════════════════════════════════════════
# Biztosítás tab
# ══════════════════════════════════════════════════════════════════════════════
class BiztositasDialog(QDialog):
    def __init__(self, parent=None, auto_id=None, entry_id=None):
        super().__init__(parent)
        self.auto_id  = auto_id
        self.entry_id = entry_id
        self.setWindowTitle("Biztosítás szerkesztése" if entry_id else "Új biztosítás")
        self.setFixedWidth(420)
        self.setModal(True)
        self._build()
        if entry_id:
            self._load()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24,20,24,20)
        lay.setSpacing(12)

        title = QLabel("🛡️ Biztosítás")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        form = QFormLayout(); form.setSpacing(8)
        self.f_biztosito = QLineEdit(); self.f_biztosito.setPlaceholderText("pl. Allianz")
        self.f_datum     = QLineEdit(); self.f_datum.setText(datetime.today().strftime("%Y.%m.%d"))
        self.f_kezdete   = QLineEdit(); self.f_kezdete.setPlaceholderText("ÉÉÉÉ.HH.NN")
        self.f_vege      = QLineEdit(); self.f_vege.setPlaceholderText("ÉÉÉÉ.HH.NN")
        self.f_osszeg    = QDoubleSpinBox(); self.f_osszeg.setRange(0,99_999_999); self.f_osszeg.setSuffix(" Ft"); self.f_osszeg.setDecimals(0)
        self.f_megj      = QLineEdit(); self.f_megj.setPlaceholderText("Megjegyzés...")

        for lbl, w in [("Biztosító",self.f_biztosito),("Dátum",self.f_datum),
                        ("Kezdete",self.f_kezdete),("Vége",self.f_vege),
                        ("Összeg",self.f_osszeg),("Megjegyzés",self.f_megj)]:
            form.addRow(QLabel(lbl), w)
        lay.addLayout(form)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Mégse"); cancel.setObjectName("cancel_btn")
        save   = QPushButton("Mentés"); save.setObjectName("save_btn")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel); btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def _load(self):
        with get_db() as conn:
            r = conn.execute("SELECT * FROM biztositas WHERE id=?", (self.entry_id,)).fetchone()
        if r:
            self.f_biztosito.setText(r["biztosito"] or "")
            self.f_datum.setText(r["datum"] or "")
            self.f_kezdete.setText(r["kezdete"] or "")
            self.f_vege.setText(r["vege"] or "")
            self.f_osszeg.setValue(float(r["osszeg"] or 0))
            self.f_megj.setText(r["megjegyzes"] or "")

    def _save(self):
        vals = (self.f_datum.text().strip(), self.f_biztosito.text().strip(),
                self.f_kezdete.text().strip(), self.f_vege.text().strip(),
                self.f_osszeg.value(), self.f_megj.text().strip())
        with get_db() as conn:
            if self.entry_id:
                conn.execute("UPDATE biztositas SET datum=?,biztosito=?,kezdete=?,vege=?,osszeg=?,megjegyzes=? WHERE id=?",
                             (*vals, self.entry_id))
            else:
                conn.execute("INSERT INTO biztositas (datum,biztosito,kezdete,vege,osszeg,megjegyzes,auto_id) VALUES (?,?,?,?,?,?,?)",
                             (*vals, self.auto_id))
        self.accept()


class BiztositasTab(QWidget):
    def __init__(self, auto_id_getter, parent=None):
        super().__init__(parent)
        self.auto_id_getter = auto_id_getter
        self.setObjectName("content_area")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        toolbar = QFrame(); toolbar.setObjectName("toolbar"); toolbar.setFixedHeight(54)
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(16,0,16,0); tb.setSpacing(8)
        btn_new = QPushButton("➕  Új biztosítás"); btn_new.setObjectName("btn_green")
        btn_new.clicked.connect(self._new)
        tb.addWidget(btn_new); tb.addStretch()
        lay.addWidget(toolbar)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.list_w = QWidget(); self.list_w.setObjectName("content_area")
        self.list_lay = QVBoxLayout(self.list_w)
        self.list_lay.setContentsMargins(16,10,16,16); self.list_lay.setSpacing(7)
        self.list_lay.addStretch()
        self.scroll.setWidget(self.list_w)
        lay.addWidget(self.scroll)

    def refresh(self):
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        auto_id = self.auto_id_getter()
        if not auto_id:
            return

        with get_db() as conn:
            rows = conn.execute("SELECT * FROM biztositas WHERE auto_id=? ORDER BY vege DESC", (auto_id,)).fetchall()

        if not rows:
            lbl = QLabel("Nincs biztosítási bejegyzés.")
            lbl.setObjectName("empty_label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_lay.insertWidget(0, lbl)
            return

        today = datetime.today().strftime("%Y.%m.%d")
        for r in rows:
            row_w = QFrame(); row_w.setObjectName("entry_row")
            r_lay = QHBoxLayout(row_w); r_lay.setContentsMargins(14,11,14,11); r_lay.setSpacing(12)

            # Lejárt-e?
            expired = r["vege"] and r["vege"] < today
            color = "#ef4444" if expired else "#22c55e"
            dot = QLabel("●"); dot.setStyleSheet(f"color: {color}; font-size: 16px;")
            r_lay.addWidget(dot)

            info = QLabel(f"{r['biztosito'] or '—'}  ·  {r['kezdete'] or '?'} → {r['vege'] or '?'}")
            info.setObjectName("entry_date")
            r_lay.addWidget(info, stretch=1)

            amt = f"{int(r['osszeg']):,} Ft".replace(",", " ") if r["osszeg"] else "—"
            amt_lbl = QLabel(amt); amt_lbl.setObjectName("entry_amt")
            r_lay.addWidget(amt_lbl)

            edit_btn = QPushButton("✏️"); edit_btn.setObjectName("e_btn"); edit_btn.setFixedSize(30,30)
            del_btn  = QPushButton("🗑️"); del_btn.setObjectName("e_btn_del"); del_btn.setFixedSize(30,30)
            edit_btn.clicked.connect(lambda _, rid=r["id"]: self._edit(rid))
            del_btn.clicked.connect(lambda _, rid=r["id"]: self._delete(rid))
            r_lay.addWidget(edit_btn); r_lay.addWidget(del_btn)

            self.list_lay.insertWidget(self.list_lay.count()-1, row_w)

    def _new(self):
        dlg = BiztositasDialog(self, auto_id=self.auto_id_getter())
        if dlg.exec() == QDialog.DialogCode.Accepted: self.refresh()

    def _edit(self, rid):
        dlg = BiztositasDialog(self, auto_id=self.auto_id_getter(), entry_id=rid)
        if dlg.exec() == QDialog.DialogCode.Accepted: self.refresh()

    def _delete(self, rid):
        ret = QMessageBox.question(self, "Törlés", "Biztosan törlöd?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            with get_db() as conn:
                conn.execute("DELETE FROM biztositas WHERE id=?", (rid,))
            self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# Statisztika tab
# ══════════════════════════════════════════════════════════════════════════════
class StatTab(QWidget):
    def __init__(self, auto_id_getter, parent=None):
        super().__init__(parent)
        self.auto_id_getter = auto_id_getter
        self.setObjectName("content_area")
        self._build()

    def _build(self):
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(20,16,20,16)
        self.lay.setSpacing(16)

    def refresh(self):
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        auto_id = self.auto_id_getter()
        if not auto_id:
            lbl = QLabel("Nincs kiválasztott jármű.")
            lbl.setObjectName("empty_label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lay.addWidget(lbl)
            return

        with get_db() as conn:
            tankolas = conn.execute("""
                SELECT SUM(osszeg) as total_ft,
                       SUM(mennyiseg_liter) as total_liter,
                       COUNT(*) as db,
                       AVG(egysegar_ft_l) as avg_ar
                FROM szerviz_adatok WHERE auto_id=? AND kategoria='Tankolás'
            """, (auto_id,)).fetchone()

            karbantartas = conn.execute("""
                SELECT SUM(osszeg) as total, COUNT(*) as db
                FROM szerviz_adatok WHERE auto_id=? AND kategoria='Karbantartás'
            """, (auto_id,)).fetchone()

            egyeb = conn.execute("""
                SELECT SUM(osszeg) as total, COUNT(*) as db
                FROM szerviz_adatok WHERE auto_id=? AND kategoria NOT IN ('Tankolás','Karbantartás','Biztosítás')
            """, (auto_id,)).fetchone()

            km_range = conn.execute("""
                SELECT MIN(km_allas) as min_km, MAX(km_allas) as max_km
                FROM szerviz_adatok WHERE auto_id=? AND km_allas > 0
            """, (auto_id,)).fetchone()

            # Átlagfogyasztás: km különbség és össz liter alapján
            fogyasztas_rows = conn.execute("""
                SELECT km_allas, mennyiseg_liter
                FROM szerviz_adatok
                WHERE auto_id=? AND kategoria='Tankolás'
                AND km_allas > 0 AND mennyiseg_liter > 0
                ORDER BY km_allas
            """, (auto_id,)).fetchall()

            monthly = conn.execute("""
                SELECT substr(datum,1,7) as honap,
                       SUM(osszeg) as total,
                       SUM(mennyiseg_liter) as liter
                FROM szerviz_adatok
                WHERE auto_id=? AND kategoria='Tankolás'
                AND datum >= date('now','-12 months')
                GROUP BY honap ORDER BY honap
            """, (auto_id,)).fetchall()

        # Átlagfogyasztás számítás (L/100km)
        avg_fogyasztas = 0.0
        if len(fogyasztas_rows) >= 2:
            km_min = fogyasztas_rows[0]["km_allas"]
            km_max = fogyasztas_rows[-1]["km_allas"]
            total_liter_fog = sum(r["mennyiseg_liter"] for r in fogyasztas_rows[1:])
            km_kulonbseg = km_max - km_min
            if km_kulonbseg > 0:
                avg_fogyasztas = (total_liter_fog / km_kulonbseg) * 100

        # ── Kártyák ──────────────────────────────────────────────────────────
        def stat_card(title, value, sub="", color="#3b82f6"):
            frame = QFrame(); frame.setObjectName("entry_row")
            frame.setFixedHeight(95)
            lay = QVBoxLayout(frame); lay.setContentsMargins(16,10,16,10); lay.setSpacing(3)
            t = QLabel(title); t.setObjectName("entry_sub"); lay.addWidget(t)
            v = QLabel(value)
            v.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 800; background: transparent;")
            lay.addWidget(v)
            if sub:
                s = QLabel(sub); s.setObjectName("entry_km"); lay.addWidget(s)
            return frame

        total_ft   = int(tankolas["total_ft"] or 0)
        total_lit  = float(tankolas["total_liter"] or 0)
        avg_ar     = float(tankolas["avg_ar"] or 0)
        karb_total = int(karbantartas["total"] or 0)
        km_diff    = (km_range["max_km"] or 0) - (km_range["min_km"] or 0) if km_range["min_km"] else 0
        egyeb_db   = int(egyeb["db"] or 0)
        egyeb_total= int(egyeb["total"] or 0)

        row1 = QHBoxLayout(); row1.setSpacing(12)
        row1.addWidget(stat_card("⛽ Összes tankolás",
            f"{total_ft:,} Ft".replace(",", " "),
            f"{total_lit:.1f} L  ·  {tankolas['db']} alkalom", "#3b82f6"))
        row1.addWidget(stat_card("🔥 Átlagfogyasztás",
            f"{avg_fogyasztas:.1f} L/100km" if avg_fogyasztas else "—",
            "km-alapú számítás", "#ef4444"))
        row1.addWidget(stat_card("💰 Átlagos üzemanyagár",
            f"{avg_ar:.1f} Ft/L" if avg_ar else "—",
            "", "#f97316"))
        row1.addWidget(stat_card("🛣️ Megtett km",
            f"{km_diff:,} km".replace(",", " ") if km_diff else "—",
            "adatok alapján", "#8b5cf6"))
        self.lay.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(12)
        row2.addWidget(stat_card("🔧 Karbantartás",
            f"{karb_total:,} Ft".replace(",", " "),
            f"{karbantartas['db']} bejegyzés", "#10b981"))
        row2.addWidget(stat_card("📦 Egyéb kiadások",
            f"{egyeb_total:,} Ft".replace(",", " "),
            f"{egyeb_db} bejegyzés", "#f97316"))
        összes = total_ft + karb_total + egyeb_total
        row2.addWidget(stat_card("💵 Összes kiadás",
            f"{összes:,} Ft".replace(",", " "),
            "tankolás + karbantartás + egyéb", "#22c55e"))
        km_ft = összes / km_diff if km_diff > 0 else 0
        row2.addWidget(stat_card("📊 Ft / km",
            f"{km_ft:.1f} Ft/km" if km_ft else "—",
            "összes kiadás / megtett km", "#64748b"))
        self.lay.addLayout(row2)

        # ── Grafikonok ────────────────────────────────────────────────────────
        if HAS_MPL and monthly:
            import numpy as np
            honapok = [r["honap"] for r in monthly]
            ossz    = [r["total"] or 0 for r in monthly]
            literek = [r["liter"] or 0 for r in monthly]

            # Havi átlagfogyasztás – minden tankolás km-e és litere alapján,
            # az előző tankolás km-étől számítva (fill-up módszer)
            all_tankolas = conn.execute("""
                SELECT datum, km_allas, mennyiseg_liter,
                       substr(datum,1,7) as honap
                FROM szerviz_adatok
                WHERE auto_id=? AND kategoria='Tankolás'
                AND km_allas > 0 AND mennyiseg_liter > 0
                ORDER BY km_allas ASC
            """, (auto_id,)).fetchall()

            # Fill-up módszer: minden tankolásnál km_diff = jelenlegi - előző km
            fog_per_tankolas = []
            for i in range(1, len(all_tankolas)):
                prev = all_tankolas[i-1]
                curr = all_tankolas[i]
                km_diff_t = curr["km_allas"] - prev["km_allas"]
                if km_diff_t > 0 and curr["mennyiseg_liter"]:
                    fog = (curr["mennyiseg_liter"] / km_diff_t) * 100
                    if 2.0 < fog < 30.0:  # szűrjük az irreális értékeket
                        fog_per_tankolas.append((curr["honap"], fog))

            # Havi átlagolás
            from collections import defaultdict
            havi_fog = defaultdict(list)
            for honap, fog in fog_per_tankolas:
                havi_fog[honap].append(fog)

            # Csak az utolsó 12 hónap
            fog_honapok = sorted(havi_fog.keys())[-12:]
            fog_ertekek = [sum(havi_fog[h])/len(havi_fog[h]) for h in fog_honapok]

            is_dark = load_config().get("dark_mode", True)
            bg  = "#1e293b" if is_dark else "#f8fafc"
            fg  = "#e2e8f0" if is_dark else "#1e293b"
            gc  = "#334155" if is_dark else "#e2e8f0"

            # ── Grafikon 1+2: Ft és Liter oszlopok ───────────────────────────
            fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.2), dpi=90)
            fig1.patch.set_facecolor(bg)

            for ax, adatok, cim, szin, fmt in [
                (ax1, ossz,    "Havi tankolási költség",  "#3b82f6",
                 lambda x: f"{int(x):,}".replace(",", " ") + " Ft"),
                (ax2, literek, "Havi tankolási mennyiség","#10b981",
                 lambda x: f"{x:.1f} L"),
            ]:
                ax.set_facecolor(bg)
                bars = ax.bar(honapok, adatok, color=szin, alpha=0.85, width=0.6, zorder=3)
                ax.set_title(cim, color=fg, fontsize=10, pad=8)
                ax.tick_params(colors=fg, labelsize=8)
                for spine in ax.spines.values(): spine.set_color(gc)
                ax.yaxis.grid(True, color=gc, alpha=0.4, zorder=0)
                ax.set_axisbelow(True)
                plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
                ax.yaxis.set_tick_params(labelcolor=fg)
                # Értékek az oszlopok tetejére
                for bar, v in zip(bars, adatok):
                    if v > 0:
                        ax.text(bar.get_x() + bar.get_width()/2,
                                bar.get_height() + max(adatok)*0.01,
                                fmt(v),
                                ha="center", va="bottom",
                                fontsize=7, color=fg, fontweight="bold")
            fig1.patch.set_facecolor(bg)
            plt.tight_layout(pad=1.5)
            canvas1 = FigureCanvas(fig1)
            canvas1.setFixedHeight(270)
            self.lay.addWidget(canvas1)
            plt.close(fig1)

            # ── Grafikon 3: Átlagfogyasztás vonal diagram ─────────────────────
            # Egyedi tankolások alapján: minden egymást követő pár ad egy pontot
            # Numerikus x tengellyel hogy a köztes hónapok is látszanak
            if len(fog_per_tankolas) >= 2:
                fig2, ax3 = plt.subplots(figsize=(11, 2.8), dpi=90)
                fig2.patch.set_facecolor(bg)
                ax3.set_facecolor(bg)

                # Numerikus index az x tengelyen (minden tankolás egy pont)
                all_tank_sorted = conn.execute("""
                    SELECT datum, km_allas, mennyiseg_liter,
                           substr(datum,1,7) as honap
                    FROM szerviz_adatok
                    WHERE auto_id=? AND kategoria='Tankolás'
                    AND km_allas > 0 AND mennyiseg_liter > 0
                    AND datum >= date('now','-12 months')
                    ORDER BY km_allas ASC
                """, (auto_id,)).fetchall()

                # Fill-up fogyasztás minden tankoláshoz
                x_vals, y_vals, x_labels = [], [], []
                for i in range(1, len(all_tank_sorted)):
                    prev = all_tank_sorted[i-1]
                    curr = all_tank_sorted[i]
                    km_d = curr["km_allas"] - prev["km_allas"]
                    if km_d > 0 and curr["mennyiseg_liter"]:
                        fog = (curr["mennyiseg_liter"] / km_d) * 100
                        if 2.0 < fog < 30.0:
                            x_vals.append(i)
                            y_vals.append(fog)
                            x_labels.append(curr["datum"])

                if len(y_vals) >= 2:
                    avg_line = sum(y_vals) / len(y_vals)

                    # Vonal + pontok
                    ax3.plot(x_vals, y_vals, color="#ef4444", linewidth=2.0,
                             marker="o", markersize=7, markerfacecolor="#ef4444",
                             markeredgecolor=bg, markeredgewidth=1.5, zorder=4)
                    ax3.axhline(avg_line, color="#f97316", linewidth=1.5,
                                linestyle="--", alpha=0.8, zorder=3,
                                label=f"Átlag: {avg_line:.1f} L/100km")
                    ax3.fill_between(x_vals, y_vals, avg_line,
                                     where=[v >= avg_line for v in y_vals],
                                     alpha=0.15, color="#ef4444", zorder=2,
                                     interpolate=True)
                    ax3.fill_between(x_vals, y_vals, avg_line,
                                     where=[v < avg_line for v in y_vals],
                                     alpha=0.15, color="#22c55e", zorder=2,
                                     interpolate=True)

                    # Értékek minden pont fölé/alá
                    for xi, yi, lbl_t in zip(x_vals, y_vals, x_labels):
                        offset = 10 if yi >= avg_line else -16
                        ax3.annotate(f"{yi:.1f}",
                                     xy=(xi, yi),
                                     xytext=(0, offset),
                                     textcoords="offset points",
                                     ha="center", fontsize=7.5,
                                     color=fg, fontweight="bold")

                    # X tengely: dátum feliratok
                    ax3.set_xticks(x_vals)
                    ax3.set_xticklabels(x_labels, rotation=40, ha="right", fontsize=7)
                    ax3.set_xlim(x_vals[0] - 0.5, x_vals[-1] + 0.5)

                    ax3.set_title("Fogyasztás tankolásról tankolásra (L/100km)",
                                  color=fg, fontsize=10, pad=8)
                    ax3.set_ylabel("L/100km", color=fg, fontsize=9)
                    ax3.tick_params(colors=fg, labelsize=7)
                    for spine in ax3.spines.values(): spine.set_color(gc)
                    ax3.yaxis.grid(True, color=gc, alpha=0.4, zorder=0)
                    ax3.set_axisbelow(True)
                    ax3.legend(facecolor=bg, edgecolor=gc, labelcolor=fg, fontsize=9)
                    y_min = max(0, min(y_vals) - 1)
                    y_max = max(y_vals) + 1.5
                    ax3.set_ylim(y_min, y_max)
                    plt.tight_layout(pad=1.5)

                    canvas2 = FigureCanvas(fig2)
                    canvas2.setFixedHeight(240)
                    self.lay.addWidget(canvas2)
                plt.close(fig2)
        else:
            lbl = QLabel("📊 Grafikon: pip install matplotlib")
            lbl.setObjectName("empty_label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lay.addWidget(lbl)

        self.lay.addStretch()


# ══════════════════════════════════════════════════════════════════════════════
# Éves összesítő tab
# ══════════════════════════════════════════════════════════════════════════════
class YearlyTab(QWidget):
    def __init__(self, auto_id_getter, parent=None):
        super().__init__(parent)
        self.auto_id_getter = auto_id_getter
        self.setObjectName("content_area")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        toolbar = QFrame(); toolbar.setObjectName("toolbar"); toolbar.setFixedHeight(54)
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(16,0,16,0)
        self.year_cb = QComboBox(); self.year_cb.setObjectName("sort_combo")
        self.year_cb.setFixedWidth(120)
        cur_year = datetime.today().year
        for y in range(cur_year, cur_year - 6, -1):
            self.year_cb.addItem(str(y))
        self.year_cb.currentIndexChanged.connect(self.refresh)
        tb.addWidget(QLabel("Év:")); tb.addWidget(self.year_cb); tb.addStretch()
        lay.addWidget(toolbar)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.content = QWidget(); self.content.setObjectName("content_area")
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(16,12,16,16); self.content_lay.setSpacing(10)
        self.scroll.setWidget(self.content)
        lay.addWidget(self.scroll)

    def refresh(self):
        while self.content_lay.count():
            item = self.content_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        auto_id = self.auto_id_getter()
        if not auto_id:
            return

        ev = self.year_cb.currentText()

        with get_db() as conn:
            rows = conn.execute("""
                SELECT substr(datum,1,7) as honap,
                       SUM(CASE WHEN kategoria='Tankolás' THEN osszeg ELSE 0 END) as tankolos,
                       SUM(CASE WHEN kategoria='Karbantartás' THEN osszeg ELSE 0 END) as karbantartas,
                       SUM(CASE WHEN kategoria NOT IN ('Tankolás','Karbantartás') THEN osszeg ELSE 0 END) as egyeb,
                       SUM(osszeg) as total
                FROM szerviz_adatok
                WHERE auto_id=? AND datum LIKE ?
                GROUP BY honap ORDER BY honap
            """, (auto_id, f"{ev}.%")).fetchall()

        if not rows:
            lbl = QLabel(f"Nincs adat {ev}-re.")
            lbl.setObjectName("empty_label")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_lay.addWidget(lbl)
            return

        # Fejléc
        header = QFrame(); header.setObjectName("entry_row")
        h_lay = QHBoxLayout(header); h_lay.setContentsMargins(14,8,14,8)
        for txt, w in [("Hónap",100),("⛽ Tankolás",130),("🔧 Karbantartás",140),("📦 Egyéb",110),("💰 Összesen",120)]:
            lbl = QLabel(txt); lbl.setObjectName("entry_km"); lbl.setFixedWidth(w)
            h_lay.addWidget(lbl)
        self.content_lay.addWidget(header)

        ev_total = [0, 0, 0, 0]
        for r in rows:
            row_w = QFrame(); row_w.setObjectName("entry_row")
            r_lay = QHBoxLayout(row_w); r_lay.setContentsMargins(14,10,14,10)

            vals = [r["tankolos"] or 0, r["karbantartas"] or 0, r["egyeb"] or 0, r["total"] or 0]
            for i, v in enumerate(vals): ev_total[i] += v

            honap_lbl = QLabel(r["honap"]); honap_lbl.setObjectName("entry_date"); honap_lbl.setFixedWidth(100)
            r_lay.addWidget(honap_lbl)
            is_dark_mode = load_config().get("dark_mode", True)
            total_color = "#ffffff" if is_dark_mode else "#0f172a"
            col_cfg = [
                ("#3b82f6", 130, "400"),
                ("#10b981", 140, "400"),
                ("#f97316", 110, "400"),
                (total_color, 130, "800"),
            ]
            for i, (v, (c, w, fw)) in enumerate(zip(vals, col_cfg)):
                lbl = QLabel(f"{int(v):,} Ft".replace(",", " ") if v else "—")
                lbl.setStyleSheet(f"color: {c}; font-weight: {fw}; font-size: {'14px' if i==3 else '13px'}; background: transparent;")
                lbl.setFixedWidth(w)
                r_lay.addWidget(lbl)
            self.content_lay.addWidget(row_w)

        # Összesítő sor
        total_w = QFrame(); total_w.setObjectName("entry_row")
        total_w.setStyleSheet("QFrame#entry_row { border: 2px solid #3b82f6; }")
        t_lay = QHBoxLayout(total_w); t_lay.setContentsMargins(14,12,14,12); t_lay.setSpacing(0)

        total_lbl = QLabel(f"📅 {ev} összesen")
        total_lbl.setObjectName("entry_date")
        total_lbl.setFixedWidth(110)
        t_lay.addWidget(total_lbl)

        col_data = [
            (ev_total[0], "#3b82f6", 130),
            (ev_total[1], "#10b981", 140),
            (ev_total[2], "#f97316", 110),
            (ev_total[3], "#22c55e", 130),
        ]
        for v, c, w in col_data:
            lbl = QLabel(f"{int(v):,} Ft".replace(",", " "))
            lbl.setStyleSheet(f"color: {c}; font-weight: 800; font-size: 13px; background: transparent;")
            lbl.setFixedWidth(w)
            t_lay.addWidget(lbl)

        self.content_lay.addWidget(total_w)

        # Éves grafikon
        if HAS_MPL and rows:
            is_dark = load_config().get("dark_mode", True)
            bg = "#1e293b" if is_dark else "#f8fafc"
            fg = "#e2e8f0" if is_dark else "#1e293b"
            grid_color = "#334155" if is_dark else "#e2e8f0"

            honapok  = [r["honap"][-2:] + ". hó" for r in rows]
            tankolas_v = [r["tankolos"] or 0 for r in rows]
            karb_v     = [r["karbantartas"] or 0 for r in rows]
            egyeb_v    = [r["egyeb"] or 0 for r in rows]

            x = range(len(honapok))
            fig, ax = plt.subplots(figsize=(10, 3.0), dpi=90)
            fig.patch.set_facecolor(bg)
            ax.set_facecolor(bg)
            w = 0.28
            import numpy as np
            xi = np.arange(len(honapok))
            ax.bar(xi - w, tankolas_v, width=w, color="#3b82f6", alpha=0.85, label="⛽ Tankolás", zorder=3)
            ax.bar(xi,     karb_v,     width=w, color="#10b981", alpha=0.85, label="🔧 Karbantartás", zorder=3)
            ax.bar(xi + w, egyeb_v,    width=w, color="#f97316", alpha=0.85, label="📦 Egyéb", zorder=3)
            ax.set_xticks(xi); ax.set_xticklabels(honapok, rotation=30, ha="right", fontsize=8)
            ax.tick_params(colors=fg, labelsize=8)
            ax.set_title(f"{ev} – havi kiadások kategóriánként", color=fg, fontsize=10, pad=8)
            ax.yaxis.grid(True, color=grid_color, alpha=0.5, zorder=0); ax.set_axisbelow(True)
            for spine in ax.spines.values(): spine.set_color(grid_color)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", " ")))
            ax.legend(facecolor=bg, edgecolor=grid_color, labelcolor=fg, fontsize=8)
            plt.tight_layout(pad=1.2)

            canvas = FigureCanvas(fig)
            canvas.setFixedHeight(240)
            self.content_lay.addWidget(canvas)
            plt.close(fig)

        self.content_lay.addStretch()


# ══════════════════════════════════════════════════════════════════════════════
# PDF Export
# ══════════════════════════════════════════════════════════════════════════════
class PdfExportDialog(QDialog):
    def __init__(self, parent=None, auto_id=None):
        super().__init__(parent)
        self.auto_id = auto_id
        self.setWindowTitle("📄 PDF Export")
        self.setFixedWidth(400)
        self.setModal(True)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24,20,24,20)
        lay.setSpacing(14)

        title = QLabel("📄 PDF Export")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        form = QFormLayout(); form.setSpacing(10)

        self.cat_cb = QComboBox()
        self.cat_cb.addItems(["Összes", "Tankolás", "Karbantartás", "Biztosítás", "Egyéb"])
        form.addRow(QLabel("Kategória:"), self.cat_cb)

        self.ev_from = QLineEdit(); self.ev_from.setPlaceholderText("pl. 2025.01.01")
        self.ev_to   = QLineEdit(); self.ev_to.setPlaceholderText("pl. 2025.12.31")
        form.addRow(QLabel("Dátumtól:"), self.ev_from)
        form.addRow(QLabel("Dátumig:"), self.ev_to)
        lay.addLayout(form)

        if not HAS_FPDF:
            warn = QLabel("⚠️ PDF exporthoz szükséges: pip install fpdf2")
            warn.setStyleSheet("color: #f59e0b; font-size: 12px;")
            lay.addWidget(warn)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Mégse"); cancel.setObjectName("cancel_btn")
        export = QPushButton("📄 Exportálás"); export.setObjectName("save_btn")
        cancel.clicked.connect(self.reject)
        export.clicked.connect(self._export)
        btn_row.addWidget(cancel); btn_row.addWidget(export)
        lay.addLayout(btn_row)

    def _export(self):
        if not self.auto_id:
            QMessageBox.warning(self, "Hiba", "Nincs kiválasztott jármű!")
            return
        if not HAS_FPDF:
            QMessageBox.warning(self, "Hiba", "Telepítsd az fpdf2 csomagot:\npip install fpdf2")
            return

        path, _ = QFileDialog.getSaveFileName(self, "PDF mentése", "wheelbook_export.pdf", "PDF (*.pdf)")
        if not path:
            return

        kat = self.cat_cb.currentText()
        datum_tol = self.ev_from.text().strip()
        datum_ig  = self.ev_to.text().strip()

        with get_db() as conn:
            auto = conn.execute("SELECT marka,tipus,rendszam FROM autok WHERE id=?", (self.auto_id,)).fetchone()
            q = "SELECT datum,osszeg,km_allas,kategoria,megjegyzes,benzinkut,mennyiseg_liter,egysegar_ft_l FROM szerviz_adatok WHERE auto_id=?"
            params = [self.auto_id]
            if kat != "Összes":
                q += " AND kategoria=?"; params.append(kat)
            if datum_tol:
                q += " AND datum >= ?"; params.append(datum_tol)
            if datum_ig:
                q += " AND datum <= ?"; params.append(datum_ig)
            q += " ORDER BY datum DESC"
            rows = conn.execute(q, params).fetchall()

        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            # Fejléc
            pdf.set_font("Helvetica", "B", 20)
            pdf.cell(0, 12, "WheelBooK", ln=True, align="C")
            pdf.set_font("Helvetica", "", 12)
            car_str = f"{auto['marka']} {auto['tipus']}"
            if auto["rendszam"]: car_str += f" ({auto['rendszam']})"
            pdf.cell(0, 8, car_str, ln=True, align="C")
            pdf.cell(0, 6, f"Exportálva: {datetime.today().strftime('%Y.%m.%d')}", ln=True, align="C")
            pdf.ln(8)

            # Táblázat fejléc
            pdf.set_fill_color(30, 41, 59)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(28, 9, "Dátum", border=1, fill=True)
            pdf.cell(30, 9, "Kategória", border=1, fill=True)
            pdf.cell(28, 9, "KM állás", border=1, fill=True)
            pdf.cell(35, 9, "Összeg", border=1, fill=True)
            pdf.cell(69, 9, "Megjegyzés", border=1, fill=True, ln=True)

            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 9)
            total = 0
            for i, r in enumerate(rows):
                fill = i % 2 == 0
                if fill: pdf.set_fill_color(240, 248, 255)
                else: pdf.set_fill_color(255, 255, 255)
                pdf.cell(28, 8, r["datum"] or "", border=1, fill=True)
                pdf.cell(30, 8, r["kategoria"] or "", border=1, fill=True)
                km_str = f"{r['km_allas']:,}".replace(",", " ") if r["km_allas"] else ""
                pdf.cell(28, 8, km_str, border=1, fill=True)
                amt = f"{int(r['osszeg']):,} Ft".replace(",", " ") if r["osszeg"] else ""
                pdf.cell(35, 8, amt, border=1, fill=True)
                megj = r["benzinkut"] or r["megjegyzes"] or ""
                pdf.cell(69, 8, megj[:40], border=1, fill=True, ln=True)
                total += r["osszeg"] or 0

            # Összesítő
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, f"Összesen: {int(total):,} Ft".replace(",", " "), ln=True, align="R")

            pdf.output(path)
            QMessageBox.information(self, "✅ Kész", f"PDF exportálva:\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hiba", f"PDF hiba:\n{e}")

# ══════════════════════════════════════════════════════════════════════════════
# Emlékeztető dialog
# ══════════════════════════════════════════════════════════════════════════════
class ReminderDialog(QDialog):
    def __init__(self, parent=None, warnings=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ Figyelmeztetések")
        self.setFixedWidth(500)
        self.setModal(True)
        self._build(warnings or [])

    def _build(self, warnings):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        title = QLabel("⚠️ Figyelmeztetések")
        title.setObjectName("popup_title")
        lay.addWidget(title)

        sub = QLabel("Az alábbi elemek figyelmet igényelnek:")
        sub.setObjectName("entry_sub")
        lay.addWidget(sub)

        for w in warnings:
            row = QFrame()
            row.setObjectName("entry_row")
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(14, 10, 14, 10)

            # Szín az emoji alapján
            if "lejárt" in w or "esedékes" in w:
                row.setStyleSheet("QFrame#entry_row { border: 1px solid #ef4444; }")
                dot = QLabel("🔴")
            else:
                row.setStyleSheet("QFrame#entry_row { border: 1px solid #f59e0b; }")
                dot = QLabel("🟡")

            dot.setFixedWidth(24)
            r_lay.addWidget(dot)

            lbl = QLabel()
            lbl.setText(w)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setWordWrap(True)
            lbl.setObjectName("entry_date")
            r_lay.addWidget(lbl, stretch=1)
            lay.addWidget(row)

        lay.addSpacing(4)
        ok_btn = QPushButton("Rendben, köszönöm!")
        ok_btn.setObjectName("save_btn")
        ok_btn.clicked.connect(self.accept)
        lay.addWidget(ok_btn)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_car_id = None
        cfg = load_config()
        self.dark_mode = cfg.get("dark_mode", True)
        self.setWindowTitle(f"WheelBooK v{CURRENT_VERSION} – Dokumentum Kezelő")
        self.resize(1200, 820)
        self._apply_theme()
        self._build_ui()
        self.refresh_cars()
        # Induláskor emlékeztetők ellenőrzése (kis késleltetéssel)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(800, self._check_reminders)
        # Frissítés ellenőrzés 3 mp késleltetéssel
        QTimer.singleShot(3000, lambda: start_update_check(self))

    def _check_reminders(self):
        """Induláskor ellenőrzi az olajcsere és biztosítás lejáratát."""
        cfg = load_config()
        warning_days_muszaki  = cfg.get("muszaki_warning_days", 30)
        warning_days_biz      = cfg.get("biztositas_warning_days", 30)
        warning_days_olaj     = cfg.get("olaj_warning_days", 1000)  # km
        today = datetime.today().strftime("%Y.%m.%d")
        today_dt = datetime.today()

        warnings = []

        with get_db() as conn:
            cars = conn.execute(
                "SELECT id, marka, tipus, km_allas, muszaki_lejarat, olaj_intervallum FROM autok"
            ).fetchall()

            for car in cars:
                name = f"{car['marka']} {car['tipus']}"

                # Műszaki lejárat
                if car["muszaki_lejarat"]:
                    try:
                        muszaki_dt = datetime.strptime(car["muszaki_lejarat"], "%Y.%m.%d")
                        days_left = (muszaki_dt - today_dt).days
                        if days_left < 0:
                            warnings.append(f"🚗 <b>{name}</b> – Műszaki vizsga <b>lejárt</b> "
                                          f"({car['muszaki_lejarat']})!")
                        elif days_left <= warning_days_muszaki:
                            warnings.append(f"🚗 <b>{name}</b> – Műszaki vizsga lejár "
                                          f"<b>{days_left} nap múlva</b> ({car['muszaki_lejarat']})")
                    except ValueError:
                        pass

                # Olajcsere (km alapján)
                if car["km_allas"] and car["olaj_intervallum"]:
                    last_oil = conn.execute("""
                        SELECT MAX(km_allas) as km FROM szerviz_adatok
                        WHERE auto_id=? AND (megjegyzes LIKE '%olaj%' OR kategoria='Karbantartás')
                        AND km_allas > 0
                    """, (car["id"],)).fetchone()
                    last_oil_km = last_oil["km"] if last_oil and last_oil["km"] else 0
                    if last_oil_km > 0:
                        km_until_oil = (last_oil_km + car["olaj_intervallum"]) - car["km_allas"]
                        if km_until_oil <= 0:
                            warnings.append(f"🔧 <b>{name}</b> – Olajcsere <b>esedékes!</b> "
                                          f"(+{abs(km_until_oil):,} km-rel késve)".replace(",", " "))
                        elif km_until_oil <= warning_days_olaj:
                            warnings.append(f"🔧 <b>{name}</b> – Olajcsere "
                                          f"<b>{km_until_oil:,} km-en belül</b>".replace(",", " "))

                # Biztosítás lejárat
                biz = conn.execute("""
                    SELECT vege, biztosito FROM biztositas
                    WHERE auto_id=? AND vege IS NOT NULL AND vege != ''
                    ORDER BY vege DESC LIMIT 1
                """, (car["id"],)).fetchone()
                if biz and biz["vege"]:
                    try:
                        biz_dt = datetime.strptime(biz["vege"], "%Y.%m.%d")
                        days_left = (biz_dt - today_dt).days
                        biztosito = biz["biztosito"] or "Biztosítás"
                        if days_left < 0:
                            warnings.append(f"🛡️ <b>{name}</b> – {biztosito} biztosítás "
                                          f"<b>lejárt</b> ({biz['vege']})!")
                        elif days_left <= warning_days_biz:
                            warnings.append(f"🛡️ <b>{name}</b> – {biztosito} biztosítás lejár "
                                          f"<b>{days_left} nap múlva</b> ({biz['vege']})")
                    except ValueError:
                        pass

        if warnings:
            dlg = ReminderDialog(self, warnings)
            dlg.exec()

    def _apply_theme(self):
        self.setStyleSheet(DARK_QSS if self.dark_mode else LIGHT_QSS)
        bg = "#0f172a" if self.dark_mode else "#f8fafc"
        self.setStyleSheet((DARK_QSS if self.dark_mode else LIGHT_QSS) +
                           f"QMainWindow {{ background: {bg}; }}")

    def _build_ui(self):
        central = QWidget(); central.setObjectName("content_area")
        self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Topbar ────────────────────────────────────────────────────────────
        topbar = QFrame(); topbar.setObjectName("topbar"); topbar.setFixedHeight(52)
        tb = QHBoxLayout(topbar); tb.setContentsMargins(16, 0, 16, 0); tb.setSpacing(8)

        logo = QLabel("WheelBooK"); logo.setObjectName("logo")
        tb.addWidget(logo)
        tb.addStretch()

        for txt, fn in [
            ("📄 PDF Export",  self._pdf_export),
            ("📂 Kategóriák",  self._categories),
            ("💾 Backup",      self._backup),
            ("🔄 Frissítés",   self._check_update),
            ("⚙️ Beállítások", self._settings),
        ]:
            btn = QPushButton(txt); btn.setObjectName("tb_btn")
            btn.clicked.connect(fn)
            tb.addWidget(btn)

        root.addWidget(topbar)

        # Topbar szeparátor
        sep1 = QFrame(); sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background: #334155;" if self.dark_mode else "background: #e2e8f0;")
        sep1.setFixedHeight(1)
        root.addWidget(sep1)

        # ── Chip sáv ──────────────────────────────────────────────────────────
        chipbar = QFrame(); chipbar.setObjectName("chipbar"); chipbar.setFixedHeight(92)
        self.chip_lay = QHBoxLayout(chipbar)
        self.chip_lay.setContentsMargins(16, 10, 16, 10)
        self.chip_lay.setSpacing(10)
        self.chip_lay.addStretch()
        root.addWidget(chipbar)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: #1e293b;" if self.dark_mode else "background: #e2e8f0;")
        sep2.setFixedHeight(1)
        root.addWidget(sep2)

        # ── Tab sáv ───────────────────────────────────────────────────────────
        self.tabbar = QFrame(); self.tabbar.setObjectName("tabbar"); self.tabbar.setFixedHeight(48)
        self.tab_btn_lay = QHBoxLayout(self.tabbar)
        self.tab_btn_lay.setContentsMargins(16, 0, 0, 0)
        self.tab_btn_lay.setSpacing(0)
        self.tab_btn_lay.addStretch()
        root.addWidget(self.tabbar)

        # ── Tab tartalom (stack) ───────────────────────────────────────────────
        self.stack = QStackedWidget(); self.stack.setObjectName("content_area")
        root.addWidget(self.stack)

        self._tab_buttons = []
        self._build_tabs()

    def _build_tabs(self):
        # Töröljük a régi füleket
        for btn in self._tab_buttons:
            btn.deleteLater()
        self._tab_buttons.clear()
        while self.stack.count():
            self.stack.removeWidget(self.stack.widget(0))

        # Tab definíciók
        with get_db() as conn:
            custom = conn.execute(
                "SELECT nev,ikon FROM kategoriak WHERE alap=0 ORDER BY id"
            ).fetchall()

        tabs = [
            ("⛽  Tankolások",    "Tankolás"),
            ("🔧  Karbantartás",  "Karbantartás"),
            ("🛡️  Biztosítás",    "__biz__"),
            ("📦  Egyéb",         "Egyéb"),
        ]
        for r in custom:
            if r["nev"] != "Biztosítás":
                tabs.append((f'{r["ikon"]}  {r["nev"]}', r["nev"]))
        tabs += [
            ("📊  Statisztika",    "__stat__"),
            ("📅  Éves összesítő", "__eves__"),
        ]

        # Tab gombok + tartalom
        for i, (label, kat) in enumerate(tabs):
            # Gomb
            btn = QPushButton(label)
            btn.setObjectName("tab_btn")
            btn.setCheckable(False)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            self.tab_btn_lay.insertWidget(self.tab_btn_lay.count()-1, btn)
            self._tab_buttons.append(btn)

            # Tartalom
            if kat == "__biz__":
                w = self._make_biz_tab()
            elif kat == "__stat__":
                w = StatTab(lambda: self.selected_car_id)
            elif kat == "__eves__":
                w = YearlyTab(lambda: self.selected_car_id)
            else:
                w = TabContent(lambda: self.selected_car_id, kat)
            self.stack.addWidget(w)

        self._switch_tab(0)

    def _switch_tab(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_buttons):
            btn.setObjectName("tab_btn_active" if i == idx else "tab_btn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        # Frissítjük az aktuális tab tartalmát
        w = self.stack.currentWidget()
        if hasattr(w, 'refresh'):
            w.refresh()

    def _make_placeholder(self, text):
        w = QWidget(); w.setObjectName("content_area")
        lay = QVBoxLayout(w)
        lbl = QLabel(text); lbl.setObjectName("empty_label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)
        return w

    def _make_biz_tab(self):
        return BiztositasTab(lambda: self.selected_car_id)

    # ── Jármű chip-ek ─────────────────────────────────────────────────────────
    def refresh_cars(self):
        # Töröljük a régi chip-eket (stretch kivételével)
        while self.chip_lay.count() > 1:
            item = self.chip_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        with get_db() as conn:
            cars = conn.execute(
                "SELECT id,marka,tipus,rendszam,km_allas FROM autok ORDER BY id"
            ).fetchall()

        if not self.selected_car_id and cars:
            self.selected_car_id = cars[0]["id"]

        for car in cars:
            cid = car["id"]
            active = (cid == self.selected_car_id)
            chip = self._make_chip(car, active)
            self.chip_lay.insertWidget(self.chip_lay.count()-1, chip)

        # + Új jármű chip
        add_chip = QPushButton("➕  Új jármű"); add_chip.setObjectName("chip_add")
        add_chip.setFixedSize(110, 72)
        add_chip.clicked.connect(lambda: self._new_car())
        self.chip_lay.insertWidget(self.chip_lay.count()-1, add_chip)

        self._refresh_current_tab()

    def _make_chip(self, car, active):
        cid    = car["id"]
        is_dark = self.dark_mode

        # Egyedi QFrame subclass hover kezeléssel
        class ChipFrame(QFrame):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setMouseTracking(True)
            def enterEvent(self, e):
                edit_btn.setVisible(True)
                del_btn.setVisible(True)
            def leaveEvent(self, e):
                edit_btn.setVisible(False)
                del_btn.setVisible(False)
            def mousePressEvent(self, e):
                pass  # kezeljük lentebb

        chip = ChipFrame()
        chip.setObjectName("car_chip_active" if active else "car_chip")
        chip.setFixedHeight(72)
        chip.setMinimumWidth(130)
        chip.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        chip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Fő layout – jobb oldalt helyet hagyunk a gomboknak
        main_lay = QVBoxLayout(chip)
        main_lay.setContentsMargins(10, 7, 54, 7)
        main_lay.setSpacing(1)

        name_lbl = QLabel(f"{car['marka']} {car['tipus']}")
        name_lbl.setObjectName("chip_name")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        name_lbl.adjustSize()
        main_lay.addWidget(name_lbl)

        rsz_lbl = QLabel(car["rendszam"] or "—")
        rsz_lbl.setObjectName("chip_rsz")
        main_lay.addWidget(rsz_lbl)

        km_str = f'{car["km_allas"]:,} km'.replace(",", " ") if car["km_allas"] else "— km"
        km_lbl = QLabel(km_str)
        km_lbl.setObjectName("chip_km")
        main_lay.addWidget(km_lbl)

        # Gombok – mindig a jobb felső sarokba pozicionálva resizeEvent-tel
        btn_bg  = "#334155" if is_dark else "#e2e8f0"
        del_bg  = "#450a0a" if is_dark else "#fee2e2"
        btn_col = "#e2e8f0" if is_dark else "#374151"
        del_col = "#f87171" if is_dark else "#dc2626"

        edit_btn = QPushButton("✏️", chip)
        edit_btn.setFixedSize(22, 22)
        edit_btn.setStyleSheet(f"""
            QPushButton {{ background: {btn_bg}; border: none; border-radius: 4px;
                           color: {btn_col}; font-size: 11px; }}
            QPushButton:hover {{ background: #475569; color: white; }}
        """)
        edit_btn.clicked.connect(lambda checked=False, c=cid: self._edit_car(c))
        edit_btn.setVisible(False)

        del_btn = QPushButton("🗑️", chip)
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet(f"""
            QPushButton {{ background: {del_bg}; border: none; border-radius: 4px;
                           color: {del_col}; font-size: 11px; }}
            QPushButton:hover {{ background: #7f1d1d; color: #fca5a5; }}
        """)
        del_btn.clicked.connect(lambda checked=False, c=cid: self._delete_car(c))
        del_btn.setVisible(False)

        # Gombok pozícionálása mindig a jobb felső sarokba
        def reposition_btns(e=None):
            w = chip.width()
            edit_btn.move(w - 48, 5)
            del_btn.move(w - 24, 5)
        chip.resizeEvent = lambda e: reposition_btns()
        chip.showEvent   = lambda e: reposition_btns()

        # Kattintás kiválasztja
        chip.mousePressEvent = lambda e, c=cid: self._select_car(c)
        for child in [name_lbl, rsz_lbl, km_lbl]:
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        return chip

    def _select_car(self, cid):
        self.selected_car_id = cid
        self.refresh_cars()

    def _new_car(self):
        dlg = CarDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Utolsó beillesztett autó kiválasztása
            with get_db() as conn:
                r = conn.execute("SELECT id FROM autok ORDER BY id DESC LIMIT 1").fetchone()
            if r:
                self.selected_car_id = r["id"]
            self.refresh_cars()

    def _edit_car(self, cid):
        dlg = CarDialog(self, car_id=cid)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_cars()

    def _delete_car(self, cid):
        ret = QMessageBox.question(self, "Jármű törlése",
                                   "Biztosan törlöd ezt a járművet és összes bejegyzését?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            with get_db() as conn:
                conn.execute("DELETE FROM autok WHERE id=?", (cid,))
            if self.selected_car_id == cid:
                self.selected_car_id = None
            self.refresh_cars()

    def _refresh_current_tab(self):
        w = self.stack.currentWidget()
        if hasattr(w, 'refresh'):
            w.refresh()

    # ── Topbar akciók ─────────────────────────────────────────────────────────
    def _pdf_export(self):
        dlg = PdfExportDialog(self, self.selected_car_id)
        dlg.exec()

    def _categories(self):
        dlg = CategoryDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._build_tabs()
            self._refresh_current_tab()

    def _backup(self):
        dlg = BackupDialog(self)
        dlg.exec()

    def _check_update(self):
        check_update_manual(self)

    def _settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_mode = dlg.get_dark_mode()
            if new_mode != self.dark_mode:
                self.dark_mode = new_mode
                self._apply_theme()
                self.refresh_cars()
                self._build_tabs()

# ══════════════════════════════════════════════════════════════════════════════
# Indítás
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

# ══════════════════════════════════════════════════════════════════════════════
# Beállítások dialog
# ══════════════════════════════════════════════════════════════════════════════