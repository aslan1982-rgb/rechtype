"""Модуль конфигурации приложения."""

import json
import os
from pathlib import Path

APP_DIR = Path(__file__).parent.parent.parent
LOCAL_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", APP_DIR)) / "RechType"
CONFIG_PATH = LOCAL_DATA_DIR / "config.json"
LEGACY_CONFIG_PATH = APP_DIR / "config.json"

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
    "file_gigaam_model": "multilingual_large_ctc",
    "gigaam_file_model_dir": None,
    "max_segment_seconds": 20.0,
    "auto_startup": False,
}


def load_config():
    """Загрузить конфиг из файла."""
    for path in (CONFIG_PATH, LEGACY_CONFIG_PATH):
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
        except (json.JSONDecodeError, IOError):
            continue
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Сохранить конфиг в файл."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = CONFIG_PATH.with_suffix(".json.tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    temporary_path.replace(CONFIG_PATH)
