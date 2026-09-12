"""Regression tests for file-transcription workers and window state."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


# The tests exercise widgets without opening a desktop window.  Set this before
# importing PyQt so the module remains usable on headless test runners as well.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import voiceflow.main as main_module  # noqa: E402
from voiceflow.main import (  # noqa: E402
    DOWNLOAD_DISK_MARGIN_BYTES,
    FileRecognitionWorker,
    RechTypeApp,
    _file_model_download_fits,
)
from voiceflow.window import TranscriptionWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


@pytest.fixture
def transcription_window(qapp):
    window = TranscriptionWindow()
    yield window
    window.hide()
    window.deleteLater()
    qapp.processEvents()


def test_file_worker_decodes_then_recognizes_and_emits_engine(monkeypatch):
    normalized_wav = b"normalized wav bytes"
    decoded_paths: list[str] = []

    def fake_media_to_wav_bytes(media_path: str) -> bytes:
        decoded_paths.append(media_path)
        return normalized_wav

    monkeypatch.setattr("voiceflow.main.media_to_wav_bytes", fake_media_to_wav_bytes)
    recognizer = Mock(engine_name="GigaAM test", last_fallback_reason=None)
    recognizer.recognize.return_value = "Распознанный текст."
    worker = FileRecognitionWorker("C:/media/пример видео.mp4", recognizer)
    results: list[tuple[str, str, object]] = []
    errors: list[str] = []
    worker.text_ready.connect(
        lambda text, engine, fallback: results.append((text, engine, fallback))
    )
    worker.error_occurred.connect(errors.append)

    # Calling run directly keeps the test deterministic while exercising the
    # exact pipeline that QThread invokes on its worker thread.
    worker.run()

    assert decoded_paths == ["C:/media/пример видео.mp4"]
    recognizer.recognize.assert_called_once_with(normalized_wav)
    assert results == [("Распознанный текст.", "GigaAM test", None)]
    assert errors == []


def test_file_worker_reports_decode_error_without_calling_recognizer(monkeypatch):
    def fail_decode(_media_path: str) -> bytes:
        raise ValueError("В выбранном файле нет аудиодорожки")

    monkeypatch.setattr("voiceflow.main.media_to_wav_bytes", fail_decode)
    recognizer = Mock(engine_name="unused")
    worker = FileRecognitionWorker("C:/media/silent.mp4", recognizer)
    results: list[tuple[str, str, object]] = []
    errors: list[str] = []
    worker.text_ready.connect(
        lambda text, engine, fallback: results.append((text, engine, fallback))
    )
    worker.error_occurred.connect(errors.append)

    worker.run()

    recognizer.recognize.assert_not_called()
    assert results == []
    assert errors == ["В выбранном файле нет аудиодорожки"]


def test_file_worker_reports_recognition_error(monkeypatch):
    monkeypatch.setattr(
        "voiceflow.main.media_to_wav_bytes",
        lambda _media_path: b"normalized wav bytes",
    )
    recognizer = Mock(engine_name="GigaAM test")
    recognizer.recognize.side_effect = RuntimeError("model unavailable")
    worker = FileRecognitionWorker("C:/media/audio.mp3", recognizer)
    results: list[tuple[str, str, object]] = []
    errors: list[str] = []
    worker.text_ready.connect(
        lambda text, engine, fallback: results.append((text, engine, fallback))
    )
    worker.error_occurred.connect(errors.append)

    worker.run()

    assert results == []
    assert errors == ["model unavailable"]


def test_file_transcription_uses_the_model_selected_in_the_window(monkeypatch):
    selected_recognizer = Mock()
    create_file_recognizer = Mock(return_value=selected_recognizer)
    monkeypatch.setattr(
        main_module,
        "create_file_recognizer",
        create_file_recognizer,
        raising=False,
    )
    worker = Mock()
    worker_type = Mock(return_value=worker)
    monkeypatch.setattr(main_module, "FileRecognitionWorker", worker_type)
    save_config = Mock()
    monkeypatch.setattr(main_module, "save_config", save_config)
    app = Mock(
        _recording=False,
        _processing=False,
        config={"max_segment_seconds": 20.0},
    )

    RechTypeApp._start_file_transcription(
        app,
        "C:/media/interview.mp4",
        "multilingual_large_ctc",
    )

    create_file_recognizer.assert_called_once_with(
        app.config,
        "multilingual_large_ctc",
    )
    worker_type.assert_called_once_with(
        "C:/media/interview.mp4",
        selected_recognizer,
    )
    worker.start.assert_called_once_with()
    save_config.assert_called_once_with(app.config)


def test_download_preflight_counts_partial_checkpoint_as_reclaimable(
    monkeypatch, tmp_path
):
    checkpoint = tmp_path / "multilingual_large_ctc.ckpt"
    checkpoint.write_bytes(b"partial-checkpoint")
    primary = SimpleNamespace(
        model_dir=tmp_path,
        checkpoint_path=checkpoint,
    )
    download_bytes = 100
    free_without_partial = DOWNLOAD_DISK_MARGIN_BYTES + download_bytes - 1
    monkeypatch.setattr(
        main_module.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=free_without_partial),
    )

    assert _file_model_download_fits(primary, download_bytes) is True
    checkpoint.unlink()
    assert _file_model_download_fits(primary, download_bytes) is False


class _LocalUrl:
    def __init__(self, path: Path):
        self._path = path

    def isLocalFile(self) -> bool:  # noqa: N802 - mirrors the Qt API
        return True

    def toLocalFile(self) -> str:  # noqa: N802 - mirrors the Qt API
        return str(self._path)


class _MimeData:
    def __init__(self, path: Path):
        self._urls = [_LocalUrl(path)]

    def hasUrls(self) -> bool:  # noqa: N802 - mirrors the Qt API
        return True

    def urls(self):
        return self._urls


class _DropEvent:
    def __init__(self, path: Path):
        self._mime_data = _MimeData(path)
        self.accepted = False
        self.ignored = False

    def mimeData(self):  # noqa: N802 - mirrors the Qt API
        return self._mime_data

    def acceptProposedAction(self) -> None:  # noqa: N802 - mirrors the Qt API
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def test_busy_window_ignores_dropped_replacement_file(
    transcription_window, tmp_path
):
    original = tmp_path / "original.mp3"
    replacement = tmp_path / "replacement.mp4"
    original.write_bytes(b"audio")
    replacement.write_bytes(b"video")
    transcription_window.select_file(original)
    transcription_window.set_busy(True, "Распознавание…")
    event = _DropEvent(replacement)

    transcription_window.dropEvent(event)

    assert transcription_window._selected_path == original
    assert transcription_window.path_edit.text() == str(original)
    assert event.ignored is True
    assert event.accepted is False


def test_selecting_new_file_clears_result_from_previous_file(
    transcription_window, tmp_path
):
    original = tmp_path / "original.wav"
    replacement = tmp_path / "replacement.mp4"
    original.write_bytes(b"audio")
    replacement.write_bytes(b"video")
    transcription_window.select_file(original)
    transcription_window.set_result("Текст первого файла", "test")
    assert transcription_window.copy_button.isEnabled()
    assert transcription_window.save_button.isEnabled()

    transcription_window.select_file(replacement)

    assert transcription_window.result_edit.toPlainText() == ""
    assert not transcription_window.copy_button.isEnabled()
    assert not transcription_window.save_button.isEnabled()


def test_model_selector_lists_supported_models_and_defaults_to_large(
    transcription_window,
):
    model_ids = {
        transcription_window.model_combo.itemData(index)
        for index in range(transcription_window.model_combo.count())
    }

    assert {
        "multilingual_large_ctc",
        "v3_e2e_rnnt",
    }.issubset(model_ids)
    assert transcription_window.model_combo.currentData() == "multilingual_large_ctc"


def test_model_selector_honours_constructor_default(qapp):
    window = TranscriptionWindow(default_model="v3_e2e_rnnt")
    try:
        assert window.model_combo.currentData() == "v3_e2e_rnnt"
    finally:
        window.hide()
        window.deleteLater()
        qapp.processEvents()


def test_transcription_request_includes_selected_model(
    transcription_window, tmp_path
):
    selected = tmp_path / "recording.wav"
    selected.write_bytes(b"audio")
    transcription_window.select_file(selected)
    model_index = transcription_window.model_combo.findData("v3_e2e_rnnt")
    assert model_index >= 0
    transcription_window.model_combo.setCurrentIndex(model_index)
    requested: list[tuple[str, str]] = []
    transcription_window.transcription_requested.connect(
        lambda path, model_id: requested.append((path, model_id))
    )

    transcription_window._request_transcription()

    assert requested == [(str(selected), "v3_e2e_rnnt")]


def test_model_selector_is_disabled_while_transcription_is_busy(
    transcription_window,
):
    assert transcription_window.model_combo.isEnabled()

    transcription_window.set_busy(True, "Распознавание…")
    assert not transcription_window.model_combo.isEnabled()

    transcription_window.set_busy(False)
    assert transcription_window.model_combo.isEnabled()


def test_deleted_selected_file_cannot_be_transcribed(
    transcription_window, tmp_path, monkeypatch
):
    selected = tmp_path / "deleted.mp3"
    selected.write_bytes(b"audio")
    transcription_window.select_file(selected)
    assert transcription_window.transcribe_button.isEnabled()

    selected.unlink()
    transcription_window.set_busy(False)

    assert not transcription_window.transcribe_button.isEnabled()
    errors: list[str] = []
    requested: list[tuple[str, str]] = []
    monkeypatch.setattr(transcription_window, "show_error", errors.append)
    transcription_window.transcription_requested.connect(
        lambda path, model_id: requested.append((path, model_id))
    )
    transcription_window._request_transcription()
    assert requested == []
    assert errors == ["Выбранный файл больше не существует."]
