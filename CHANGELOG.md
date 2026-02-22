# WheelBooK – Változásnapló

## v9.1 – 2026.02.21
### Újdonságok
- 📋 **Bejegyzés másolása** – minden bejegyzésnél megjelent egy 📋 gomb, ami az adatokat előtölti az új bejegyzés popupba (dátum és km üresen marad)
- 🏷️ **Kategóriák testreszabása** – a Beállítások panelen saját kategóriák vehetők fel, szerkeszthetők és törölhetők; az új bejegyzés popupban dropdown választóból lehet kiválasztani
- 📝 **Verziókövetés** – ez az ablak! Indításkor egyszer megjelenik ha új verzió érhető el

### Javítások
- Bejegyzés mentésekor az autó km állása most visszafelé is helyesen szinkronizálódik törlés/módosítás esetén
- Dátum automata formázás: `20260221` → `2026.02.21`
- Tankológép: Liter × Ft/L automatikusan számítja az összeget

---

## v9.0 – 2026.02.15
### Újdonságok
- 🌙 Sötét mód támogatás
- 🔍 Keresés és szűrés minden fülön (dátum, összeg, rendezés)
- 💾 Automatikus napi backup + ZIP export/import
- 🔔 Szerviz emlékeztetők indításkor + Windows értesítések
- ✅ Olajcsere "elvégezve" gomb a statisztika oldalon
- ⚙️ Beállítások panel
- 📅 Éves összesítő fül havi km előrejelzéssel

### Javítások
- `kep_utvonal` mező hozzáadva az adatbázishoz (régi verziókból automatikus migráció)
- Csatolt képek törlése bejegyzés törlésekor
- Modális popupok (grab_set)

---

## v8.7 – eredeti verzió
- Alapfunkciók: Tankolás, Karbantartás, Egyéb nyilvántartás
- PDF export
- Statisztika grafikonokkal
- CSV import
