"""
Mobile dashboard user preferences — lightweight JSON file store.
Preference file: /home/ubuntu/mobile_prefs.json
"""
import json
import os

PREFS_PATH = "/home/ubuntu/mobile_prefs.json"

DEFAULTS = {
    "pressure_watch_alerts": True,
    "pulse_telegram_alerts":    True,
    "rift_telegram_alerts":     True,
}

def get_preference(key: str, default=None):
    try:
        if os.path.exists(PREFS_PATH):
            with open(PREFS_PATH, encoding="utf-8") as f:
                prefs = json.load(f)
            return prefs.get(key, DEFAULTS.get(key, default))
        return DEFAULTS.get(key, default)
    except Exception:
        return DEFAULTS.get(key, default)


def set_preference(key: str, value) -> bool:
    try:
        prefs = dict(DEFAULTS)
        if os.path.exists(PREFS_PATH):
            with open(PREFS_PATH, encoding="utf-8") as f:
                prefs.update(json.load(f))
        prefs[key] = value
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
        return True
    except Exception:
        return False


def get_all_preferences() -> dict:
    try:
        base = dict(DEFAULTS)
        if os.path.exists(PREFS_PATH):
            with open(PREFS_PATH, encoding="utf-8") as f:
                base.update(json.load(f))
        return base
    except Exception:
        return dict(DEFAULTS)
