"""
reminder_manager.py
-------------------
Szerviz emlékeztetők és Windows értesítések kezelése.
- Műszaki vizsga lejárat előtti figyelmeztetés
- Olajcsere közelgő figyelmeztetés
- Windows tálca push értesítések (plyer)
- Indításkori popup összefoglaló
"""

import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# plyer opcionális — ha nincs telepítve, csak popup lesz
try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    logger.info("plyer nincs telepítve – Windows értesítések nem elérhetők.")


class ReminderManager:
    def __init__(self, db_path: str, config_manager):
        self.db_path = db_path
        self.config = config_manager

    # ------------------------------------------------------------------
    # Fő ellenőrzés – indításkor hívandó
    # ------------------------------------------------------------------

    def check_all(self) -> list[dict]:
        """
        Ellenőrzi az összes járművet és visszaadja a figyelmeztetések listáját.
        Minden figyelmeztetés egy dict: {auto, tipus, uzenet, sulyossag}
        sulyossag: "warning" | "danger"
        """
        reminders = []
        conn = sqlite3.connect(self.db_path)
        try:
            cars = conn.execute(
                "SELECT id, marka, tipus, km_allas, muszaki_lejarat, olaj_intervallum FROM autok"
            ).fetchall()

            for car in cars:
                cid, marka, tipus, curr_km, muszaki, intervallum = car
                auto_str = f"{marka} {tipus}"
                curr_km = curr_km or 0
                intervallum = intervallum or 10000

                # Műszaki vizsga ellenőrzés
                muszaki_reminders = self._check_muszaki(auto_str, muszaki)
                reminders.extend(muszaki_reminders)

                # Olajcsere ellenőrzés
                olaj_reminder = self._check_olaj(conn, cid, auto_str, curr_km, intervallum)
                if olaj_reminder:
                    reminders.append(olaj_reminder)

        finally:
            conn.close()

        return reminders

    # ------------------------------------------------------------------
    # Műszaki vizsga ellenőrzés
    # ------------------------------------------------------------------

    def _check_muszaki(self, auto_str: str, muszaki_lejarat: str) -> list[dict]:
        if not muszaki_lejarat or muszaki_lejarat == "---":
            return []

        days_before = self.config.get("reminder_days_before", 30)
        results = []

        # Elfogadott formátumok: ÉÉÉÉ.HH.NN és ÉÉÉÉ-HH-NN (visszafelé kompatibilitás)
        for fmt in ("%Y.%m.%d", "%Y-%m-%d"):
            try:
                lejarat = datetime.strptime(muszaki_lejarat.strip(), fmt)
                break
            except ValueError:
                continue
        else:
            logger.warning(f"Érvénytelen dátumformátum: {muszaki_lejarat} (elfogadott: ÉÉÉÉ.HH.NN)")
            return results

        today = datetime.now()
        diff = (lejarat - today).days

        if diff < 0:
            results.append({
                "auto": auto_str,
                "tipus": "muszaki",
                "uzenet": f"⛔ LEJÁRT műszaki vizsga! ({abs(diff)} napja lejárt)",
                "sulyossag": "danger",
                "napok": diff,
            })
        elif diff <= days_before:
            results.append({
                "auto": auto_str,
                "tipus": "muszaki",
                "uzenet": f"⚠️ Műszaki vizsga {diff} nap múlva lejár ({muszaki_lejarat})",
                "sulyossag": "warning" if diff > 7 else "danger",
                "napok": diff,
            })

        return results

    # ------------------------------------------------------------------
    # Olajcsere ellenőrzés
    # ------------------------------------------------------------------

    def _check_olaj(self, conn, car_id: int, auto_str: str, curr_km: int, intervallum: int):
        warning_km = self.config.get("oil_warning_km", 1000)

        last_oil = conn.execute("""
            SELECT km_allas FROM szerviz_adatok
            WHERE auto_id=? AND kategoria='Karbantartás'
            AND (megjegyzes LIKE '%olaj%' OR megjegyzes LIKE '%Oil%'
                 OR megjegyzes LIKE '%OLAJ%')
            ORDER BY km_allas DESC LIMIT 1
        """, (car_id,)).fetchone()

        if not last_oil:
            return None

        diff = curr_km - last_oil[0]
        remaining = intervallum - diff

        if remaining <= 0:
            return {
                "auto": auto_str,
                "tipus": "olaj",
                "uzenet": f"🔴 OLAJCSERE ESEDÉKES! ({diff} km telt el, {abs(remaining)} km-rel túllépve)",
                "sulyossag": "danger",
                "remaining_km": remaining,
            }
        elif remaining <= warning_km:
            return {
                "auto": auto_str,
                "tipus": "olaj",
                "uzenet": f"🟡 Olajcsere közelgő: még {remaining} km ({diff} km telt el)",
                "sulyossag": "warning",
                "remaining_km": remaining,
            }

        return None

    # ------------------------------------------------------------------
    # Windows tálca értesítés (plyer)
    # ------------------------------------------------------------------

    def send_windows_notification(self, title: str, message: str):
        """Windows tálca push értesítés küldése (ha a plyer elérhető)."""
        if not PLYER_AVAILABLE:
            logger.info("plyer nem elérhető, értesítés kihagyva.")
            return False

        try:
            plyer_notification.notify(
                title=title,
                message=message,
                app_name="WheelBooK",
                timeout=8,
            )
            return True
        except Exception as e:
            logger.warning(f"Windows értesítés hiba: {e}")
            return False

    def notify_reminders(self, reminders: list[dict]):
        """
        Ha vannak emlékeztetők, Windows értesítést küld a legfontosabbról.
        """
        if not reminders:
            return

        dangers = [r for r in reminders if r["sulyossag"] == "danger"]
        target = dangers[0] if dangers else reminders[0]

        count = len(reminders)
        title = f"WheelBooK – {count} szerviz emlékeztető"
        message = target["uzenet"].replace("⛔", "").replace("⚠️", "").replace("🔴", "").replace("🟡", "").strip()

        self.send_windows_notification(title, message)

    # ------------------------------------------------------------------
    # Összefoglaló szöveg
    # ------------------------------------------------------------------

    @staticmethod
    def format_summary(reminders: list[dict]) -> str:
        if not reminders:
            return "✅ Minden rendben, nincs aktuális figyelmeztetés."

        lines = []
        for r in reminders:
            lines.append(f"  {r['uzenet']}  [{r['auto']}]")
        return "\n".join(lines)
