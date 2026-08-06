#!/usr/bin/env python3
"""Точка входа для запуска RechType."""

import sys
import json
import time
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from voiceflow.main import main


def run_self_test(audio_path: Path, report_path: Path) -> int:
    """Exercise the packaged recognizer and write a machine-readable result."""
    from voiceflow.config import DEFAULT_CONFIG
    from voiceflow.recognizer import create_recognizer

    started = time.perf_counter()
    recognizer = create_recognizer(DEFAULT_CONFIG.copy())
    try:
        text = recognizer.recognize(audio_path.read_bytes())
        report = {
            "ok": True,
            "engine": recognizer.engine_name,
            "fallback_reason": getattr(recognizer, "last_fallback_reason", None),
            "elapsed_seconds": time.perf_counter() - started,
            "text": text,
        }
        exit_code = 0
    except Exception as error:
        report = {
            "ok": False,
            "engine": getattr(recognizer, "engine_name", "unknown"),
            "elapsed_seconds": time.perf_counter() - started,
            "error": str(error),
        }
        exit_code = 1
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return exit_code

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--self-test":
        raise SystemExit(run_self_test(Path(sys.argv[2]), Path(sys.argv[3])))
    main()
