"""Тесты для модуля распознавания речи."""

import pytest
import io
import sys
import types
import wave
from unittest.mock import Mock, patch, MagicMock
import json
import numpy as np
from voiceflow.recognizer import (
    GigaAMRecognizer,
    QualityRecognizer,
    VoskRecognizer,
    _install_gigaam_wav_loader,
)


class TestVoskRecognizer:
    """Тесты VoskRecognizer."""

    def test_init_default_path(self):
        """Тест создания с дефолтным путём."""
        rec = VoskRecognizer()
        assert rec.model_path is not None
        assert rec._loaded is False

    def test_init_custom_path(self):
        """Тест создания с кастомным путём."""
        rec = VoskRecognizer(model_path="/tmp/test-model")
        assert str(rec.model_path).replace("\\", "/") == "/tmp/test-model"

    def test_post_process_empty(self):
        """Пост-обработка пустого текста."""
        rec = VoskRecognizer()
        assert rec._post_process("") == ""

    def test_post_process_capitalization(self):
        """Пост-обработка заглавной буквы."""
        rec = VoskRecognizer()
        result = rec._post_process("привет мир")
        assert result == "Привет мир."

    def test_post_process_punctuation_preserved(self):
        """Пост-обработка сохраняет существующую пунктуацию."""
        rec = VoskRecognizer()
        result = rec._post_process("привет мир!")
        assert result == "Привет мир!"

    def test_post_process_already_capitalized(self):
        """Пост-обработка уже заглавной буквы."""
        rec = VoskRecognizer()
        result = rec._post_process("Привет")
        assert result == "Привет."

    def test_load_model_missing(self):
        """Ошибка при отсутствии модели."""
        rec = VoskRecognizer(model_path="/nonexistent/path")
        with pytest.raises(FileNotFoundError):
            rec.load_model()

    @patch('voiceflow.recognizer.vosk')
    def test_recognize(self, mock_vosk):
        """Тест распознавания."""
        # Мокаем модель
        mock_model = Mock()
        mock_vosk.Model.return_value = mock_model

        # Мокаем recognizer
        mock_rec = Mock()
        mock_vosk.KaldiRecognizer.return_value = mock_rec
        mock_rec.AcceptWaveform.return_value = True
        mock_rec.Result.return_value = json.dumps({"text": ""})
        mock_rec.FinalResult.return_value = json.dumps({"text": "привет мир"})

        rec = VoskRecognizer(model_path="/tmp/test")
        rec.model = mock_model
        rec._loaded = True

        # Создаём тестовый WAV
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b'\x00' * 32000)

        wav_bytes = buffer.getvalue()
        result = rec.recognize(wav_bytes)

        assert "Привет мир" in result
        mock_rec.AcceptWaveform.assert_called()
        mock_rec.FinalResult.assert_called_once()


class TestGigaAMRecognizer:
    def test_embedded_wav_loader_avoids_external_ffmpeg(self, monkeypatch, tmp_path):
        package = types.ModuleType("gigaam")
        package.__path__ = []
        preprocess = types.ModuleType("gigaam.preprocess")
        model = types.ModuleType("gigaam.model")
        monkeypatch.setitem(sys.modules, "gigaam", package)
        monkeypatch.setitem(sys.modules, "gigaam.preprocess", preprocess)
        monkeypatch.setitem(sys.modules, "gigaam.model", model)

        fake_torch = Mock()
        fake_torch.from_numpy.side_effect = lambda samples: samples

        audio_path = tmp_path / "sample.wav"
        with wave.open(str(audio_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16_000)
            wav_file.writeframes(np.array([0, 16_384, -16_384], dtype="<i2").tobytes())

        _install_gigaam_wav_loader(package, fake_torch)
        samples = model.load_audio(str(audio_path))

        assert preprocess.load_audio is model.load_audio
        assert samples.dtype == np.float32
        assert samples.tolist() == pytest.approx([0.0, 0.5, -0.5])
        fake_torch.from_numpy.assert_called_once()

    def test_joins_segment_results(self, monkeypatch):
        class Result:
            def __init__(self, text):
                self.text = text

        class Model:
            calls = 0

            def transcribe(self, _path):
                self.calls += 1
                return Result("первая часть" if self.calls == 1 else "Вторая часть!")

        monkeypatch.setattr("voiceflow.recognizer.split_wav", lambda *_args: [b"one", b"two"])
        recognizer = GigaAMRecognizer()
        recognizer.model = Model()
        recognizer._loaded = True

        assert recognizer.recognize(b"wav") == "Первая часть Вторая часть!"

    def test_post_process_removes_spaces_before_punctuation(self):
        assert GigaAMRecognizer._post_process(" привет  , мир ") == "Привет, мир."


def test_quality_recognizer_falls_back_after_primary_error():
    primary = Mock(engine_name="GigaAM")
    primary.recognize.side_effect = RuntimeError("model unavailable")
    fallback = Mock(engine_name="Vosk")
    fallback.recognize.return_value = "Резервный текст."
    recognizer = QualityRecognizer(primary, fallback)

    assert recognizer.recognize(b"wav") == "Резервный текст."
    assert recognizer.last_engine == "Vosk"
    assert recognizer.last_fallback_reason == "model unavailable"
