"""Tests for local trusted correction records."""

import json

import numpy as np
import pytest

from voiceflow.history import TranscriptionHistory, default_learning_dir
from voiceflow.segmentation import TARGET_SAMPLE_RATE, encode_wav


def test_record_and_correct_builds_training_manifest(tmp_path):
    history = TranscriptionHistory(tmp_path)
    wav_bytes = encode_wav(np.zeros(TARGET_SAMPLE_RATE, dtype=np.float32))

    created = history.record(wav_bytes, "сырой текст", "GigaAM test")
    corrected = history.correct_last("Исправленный текст.")

    assert created["raw_text"] == "сырой текст"
    assert corrected["corrected_text"] == "Исправленный текст."
    assert history.last_record()["engine"] == "GigaAM test"
    assert "Исправленный текст." in history.manifest_path.read_text(encoding="utf-8")
    metadata = json.loads(next(tmp_path.glob("records/*/*/record.json")).read_text(encoding="utf-8"))
    assert metadata["corrected_at"]


def test_correct_last_rejects_empty_history(tmp_path):
    with pytest.raises(LookupError):
        TranscriptionHistory(tmp_path).correct_last("текст")


def test_correct_last_rejects_empty_text(tmp_path):
    history = TranscriptionHistory(tmp_path)
    history.record(
        encode_wav(np.zeros(TARGET_SAMPLE_RATE, dtype=np.float32)),
        "текст",
        "test",
    )

    with pytest.raises(ValueError):
        history.correct_last("   ")


def test_default_learning_dir_uses_rechtype_for_new_install(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_learning_dir() == tmp_path / "RechType" / "learning"


def test_default_learning_dir_keeps_existing_voiceflow_history(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy = tmp_path / "VoiceFlow Local" / "learning"
    legacy.mkdir(parents=True)

    assert default_learning_dir() == legacy
