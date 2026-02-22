import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "font_size": 14,
    "card_bg": "#ffffff",
    "accent_color": "#3b82f6",
    "header_bg": "#1e293b",
    "appearance_mode": "light",
    "auto_backup": True,
    "backup_keep_days": 30,
    "reminder_days_before": 30,
    "oil_warning_km": 1000,
    "default_oil_interval": 10000,
}

class ConfigManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.settings.update(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Konfigurációs fájl sérült, alapértelmezett beállítások betöltve: {e}")
            except OSError as e:
                logger.error(f"Konfigurációs fájl olvasási hiba: {e}")

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Konfigurációs fájl mentési hiba: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()

    def reset(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.save()
