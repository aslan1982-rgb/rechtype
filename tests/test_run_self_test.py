"""Tests for packaged command-line smoke checks."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import run as run_module
import voiceflow.media as media_module
import voiceflow.recognizer as recognizer_module


def test_media_self_test_fails_when_selected_model_falls_back(
    monkeypatch, tmp_path
):
    recognizer = Mock(
        primary=SimpleNamespace(engine_name="GigaAM Multilingual Large 600M"),
        engine_name="Vosk small ru",
        last_fallback_reason="large unavailable",
    )
    recognizer.recognize.return_value = "Резервный текст."
    monkeypatch.setattr(
        recognizer_module, "create_file_recognizer", lambda *_args: recognizer
    )
    monkeypatch.setattr(media_module, "media_to_wav_bytes", lambda _path: b"wav")
    report_path = tmp_path / "report.json"

    exit_code = run_module.run_media_self_test(
        tmp_path / "audio.mp3",
        report_path,
        "multilingual_large_ctc",
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["ok"] is False
    assert report["requested_engine"] == "GigaAM Multilingual Large 600M"
    assert report["engine"] == "Vosk small ru"
    assert report["fallback_reason"] == "large unavailable"


def test_media_self_test_reports_invalid_model_in_json(monkeypatch, tmp_path):
    monkeypatch.setattr(
        recognizer_module,
        "create_file_recognizer",
        Mock(side_effect=ValueError("unknown model")),
    )
    report_path = tmp_path / "invalid-model.json"

    exit_code = run_module.run_media_self_test(
        tmp_path / "audio.mp3",
        report_path,
        "invalid",
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["ok"] is False
    assert report["requested_engine"] == "invalid"
    assert report["error"] == "unknown model"
