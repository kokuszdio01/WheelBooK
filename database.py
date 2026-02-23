import sqlite3
import logging

logger = logging.getLogger(__name__)

# Alapértelmezett kategóriák
DEFAULT_KATEGORIAK = [
    ("Tankolás",       "⛽", "#3b82f6", 1),
    ("Karbantartás",   "🔧", "#10b981", 1),
    ("Egyéb",          "📦", "#f97316", 1),
    ("Biztosítás",     "🛡️", "#8b5cf6", 1),
]

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute("""
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
        )
    """)

    cursor.execute("""
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
            FOREIGN KEY (auto_id) REFERENCES autok (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kategoriak (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nev TEXT NOT NULL UNIQUE,
            ikon TEXT DEFAULT '📦',
            szin TEXT DEFAULT '#64748b',
            alap INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
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
            FOREIGN KEY (auto_id) REFERENCES autok (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_szerviz_auto_id ON szerviz_adatok (auto_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_szerviz_datum ON szerviz_adatok (datum)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_biztositas_auto_id ON biztositas (auto_id)")

    conn.commit()
    _migrate_db(cursor, conn)

    # Alapértelmezett kategóriák feltöltése ha még üres
    existing = cursor.execute("SELECT COUNT(*) FROM kategoriak").fetchone()[0]
    if existing == 0:
        cursor.executemany(
            "INSERT INTO kategoriak (nev, ikon, szin, alap) VALUES (?,?,?,?)",
            DEFAULT_KATEGORIAK
        )
        conn.commit()
    else:
        # Biztosítás hozzáadása ha még nincs (meglévő adatbázisnál)
        biz = cursor.execute(
            "SELECT id FROM kategoriak WHERE nev='Biztosítás'"
        ).fetchone()
        if not biz:
            cursor.execute(
                "INSERT INTO kategoriak (nev, ikon, szin, alap) VALUES (?,?,?,?)",
                ("Biztosítás", "🛡️", "#8b5cf6", 1)
            )
            conn.commit()

    conn.close()

def _migrate_db(cursor, conn):
    try:
        cursor.execute("SELECT kep_utvonal FROM szerviz_adatok LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migráció: kep_utvonal oszlop hozzáadása...")
        cursor.execute("ALTER TABLE szerviz_adatok ADD COLUMN kep_utvonal TEXT DEFAULT ''")
        conn.commit()

    try:
        cursor.execute("SELECT ikon FROM autok LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migráció: ikon oszlop hozzáadása az autok táblához...")
        cursor.execute("ALTER TABLE autok ADD COLUMN ikon TEXT DEFAULT '🚗'")
        conn.commit()