"""Regression tests for file-transcription workers and window state."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock

import pytest


# The tests exercise widgets without opening a desktop window.  Set this before
# importing PyQt so the module remains usable on headless test runners as well.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from voiceflow.main import FileRecognitionWorker  # noqa: E402
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
    recognizer = Mock(engine_name="GigaAM test")
    recognizer.recognize.return_value = "Распознанный текст."
    worker = FileRecognitionWorker("C:/media/пример видео.mp4", recognizer)
    results: list[tuple[str, str]] = []
    errors: list[str] = []
    worker.text_ready.connect(lambda text, engine: results.append((text, engine)))
    worker.error_occurred.connect(errors.append)

    # Calling run directly keeps the test deterministic while exercising the
    # exact pipeline that QThread invokes on its worker thread.
    worker.run()

    assert decoded_paths == ["C:/media/пример видео.mp4"]
    recognizer.recognize.assert_called_once_with(normalized_wav)
    assert results == [("Распознанный текст.", "GigaAM test")]
    assert errors == []


def test_file_worker_reports_decode_error_without_calling_recognizer(monkeypatch):
    def fail_decode(_media_path: str) -> bytes:
        raise ValueError("В выбранном файле нет аудиодорожки")

    monkeypatch.setattr("voiceflow.main.media_to_wav_bytes", fail_decode)
    recognizer = Mock(engine_name="unused")
    worker = FileRecognitionWorker("C:/media/silent.mp4", recognizer)
    results: list[tuple[str, str]] = []
    errors: list[str] = []
    worker.text_ready.connect(lambda text, engine: results.append((text, engine)))
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
    results: list[tuple[str, str]] = []
    errors: list[str] = []
    worker.text_ready.connect(lambda text, engine: results.append((text, engine)))
    worker.error_occurred.connect(errors.append)

    worker.run()

    assert results == []
    assert errors == ["model unavailable"]


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
    requested: list[str] = []
    monkeypatch.setattr(transcription_window, "show_error", errors.append)
    transcription_window.transcription_requested.connect(requested.append)
    transcription_window._request_transcription()
    assert requested == []
    assert errors == ["Выбранный файл больше не существует."]
