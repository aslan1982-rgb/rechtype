"""Модуль конфигурации приложения."""

import json
from pathlib import Path

APP_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "hotkey": "ctrl+space",
    "microphone_index": None,
    "sample_rate": 16000,
    "channels": 1,
    "theme": "dark",
    "language": "ru",
    "recognizer": "gigaam",
    "gigaam_model": "v3_e2e_rnnt",
    "gigaam_model_dir": None,
    "max_segment_seconds": 20.0,
    "auto_startup": False,
}


def load_config():
    """Загрузить конфиг из файла."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Сохранить конфиг в файл."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
