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


def run_media_self_test(media_path: Path, report_path: Path) -> int:
    """Decode and recognize an audio/video file in the packaged application."""
    from voiceflow.config import DEFAULT_CONFIG
    from voiceflow.media import media_to_wav_bytes
    from voiceflow.recognizer import create_recognizer

    started = time.perf_counter()
    recognizer = create_recognizer(DEFAULT_CONFIG.copy())
    try:
        wav_bytes = media_to_wav_bytes(media_path)
        text = recognizer.recognize(wav_bytes)
        report = {
            "ok": True,
            "engine": recognizer.engine_name,
            "fallback_reason": getattr(recognizer, "last_fallback_reason", None),
            "elapsed_seconds": time.perf_counter() - started,
            "decoded_wav_bytes": len(wav_bytes),
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
    if "--self-test" in sys.argv:
        option_index = sys.argv.index("--self-test")
        if len(sys.argv) <= option_index + 2:
            raise SystemExit("--self-test requires INPUT.wav and REPORT.json")
        raise SystemExit(
            run_self_test(
                Path(sys.argv[option_index + 1]),
                Path(sys.argv[option_index + 2]),
            )
        )
    if "--media-self-test" in sys.argv:
        option_index = sys.argv.index("--media-self-test")
        if len(sys.argv) <= option_index + 2:
            raise SystemExit("--media-self-test requires INPUT and REPORT.json")
        raise SystemExit(
            run_media_self_test(
                Path(sys.argv[option_index + 1]),
                Path(sys.argv[option_index + 2]),
            )
        )
    raise SystemExit(main())
