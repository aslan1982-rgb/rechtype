"""Тесты для модуля распознавания речи."""

import pytest
import io
import socket
import sys
import types
import wave
from unittest.mock import Mock, patch, MagicMock
import json
import numpy as np
import voiceflow.recognizer as recognizer_module
from voiceflow.recognizer import (
    FILE_MODEL_SPECS,
    GigaAMRecognizer,
    QualityRecognizer,
    VoskRecognizer,
    _install_gigaam_wav_loader,
    create_file_recognizer,
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

    def test_segment_length_is_clamped_below_gigaam_limit(self):
        recognizer = GigaAMRecognizer(max_segment_seconds=37.5)
        assert recognizer.max_segment_seconds == 24.0

    def test_non_positive_segment_length_is_rejected(self):
        for value in (0, float("nan"), float("inf")):
            with pytest.raises(ValueError):
                GigaAMRecognizer(max_segment_seconds=value)

    def test_nonbundled_large_model_uses_local_app_data_cache(
        self, monkeypatch, tmp_path
    ):
        local_app_data = tmp_path / "local-app-data"
        monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
        monkeypatch.setattr(
            recognizer_module,
            "_runtime_root",
            lambda: tmp_path / "empty-runtime",
        )
        monkeypatch.setattr(
            recognizer_module.sys,
            "executable",
            str(tmp_path / "empty-app" / "RechType.exe"),
        )

        recognizer = GigaAMRecognizer(
            model_name="multilingual_large_ctc",
            allow_download=True,
        )

        assert recognizer.model_dir == (
            local_app_data / "RechType" / "models" / "gigaam"
        )

    def test_first_use_download_is_allowed_without_existing_checkpoint(
        self, monkeypatch, tmp_path
    ):
        package = types.ModuleType("gigaam")
        package.__path__ = []
        package.load_model = Mock(return_value=object())
        preprocess = types.ModuleType("gigaam.preprocess")
        model = types.ModuleType("gigaam.model")
        monkeypatch.setitem(sys.modules, "gigaam", package)
        monkeypatch.setitem(sys.modules, "gigaam.preprocess", preprocess)
        monkeypatch.setitem(sys.modules, "gigaam.model", model)

        fake_torch = types.ModuleType("torch")
        fake_torch.from_numpy = Mock()
        fake_torch.set_num_threads = Mock()
        fake_torch.set_num_interop_threads = Mock()
        monkeypatch.setitem(sys.modules, "torch", fake_torch)

        model_dir = tmp_path / "download-cache"
        recognizer = GigaAMRecognizer(
            model_name="multilingual_large_ctc",
            model_dir=model_dir,
            allow_download=True,
        )

        recognizer.load_model()

        package.load_model.assert_called_once_with(
            "multilingual_large_ctc",
            device="cpu",
            fp16_encoder=False,
            use_flash=False,
            download_root=str(model_dir),
        )
        assert recognizer._loaded is True

    def test_incomplete_large_checkpoint_is_discarded_before_retry(
        self, monkeypatch, tmp_path
    ):
        model_dir = tmp_path / "download-cache"
        model_dir.mkdir()
        checkpoint = model_dir / "multilingual_large_ctc.ckpt"
        checkpoint.write_bytes(b"incomplete")

        package = types.ModuleType("gigaam")
        package.__path__ = []

        def fake_load_model(*_args, **_kwargs):
            assert not checkpoint.exists()
            return object()

        package.load_model = Mock(side_effect=fake_load_model)
        preprocess = types.ModuleType("gigaam.preprocess")
        model = types.ModuleType("gigaam.model")
        monkeypatch.setitem(sys.modules, "gigaam", package)
        monkeypatch.setitem(sys.modules, "gigaam.preprocess", preprocess)
        monkeypatch.setitem(sys.modules, "gigaam.model", model)

        fake_torch = types.ModuleType("torch")
        fake_torch.from_numpy = Mock()
        fake_torch.set_num_threads = Mock()
        fake_torch.set_num_interop_threads = Mock()
        monkeypatch.setitem(sys.modules, "torch", fake_torch)

        recognizer = GigaAMRecognizer(
            model_name="multilingual_large_ctc",
            model_dir=model_dir,
            allow_download=True,
        )
        assert recognizer.model_available is False

        recognizer.load_model()

        assert recognizer._loaded is True

    @pytest.mark.parametrize("retry_succeeds", [True, False])
    def test_checksum_retry_is_bounded_and_restores_socket_timeout(
        self, monkeypatch, tmp_path, retry_succeeds
    ):
        model_dir = tmp_path / "download-cache"
        model_dir.mkdir()
        checkpoint = model_dir / "multilingual_large_ctc.ckpt"
        checkpoint.write_bytes(b"corrupt but treated as the expected size")

        package = types.ModuleType("gigaam")
        package.__path__ = []
        calls = 0

        def fake_load_model(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            assert socket.getdefaulttimeout() == 60.0
            if calls == 1:
                raise AssertionError("model checksum mismatch")
            assert not checkpoint.exists()
            if retry_succeeds:
                return object()
            raise OSError("download failed")

        package.load_model = Mock(side_effect=fake_load_model)
        preprocess = types.ModuleType("gigaam.preprocess")
        model = types.ModuleType("gigaam.model")
        monkeypatch.setitem(sys.modules, "gigaam", package)
        monkeypatch.setitem(sys.modules, "gigaam.preprocess", preprocess)
        monkeypatch.setitem(sys.modules, "gigaam.model", model)

        fake_torch = types.ModuleType("torch")
        fake_torch.from_numpy = Mock()
        fake_torch.set_num_threads = Mock()
        fake_torch.set_num_interop_threads = Mock()
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setattr(
            GigaAMRecognizer,
            "model_available",
            property(lambda _self: True),
        )

        sentinel_timeout = 13.0
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(sentinel_timeout)
        try:
            recognizer = GigaAMRecognizer(
                model_name="multilingual_large_ctc",
                model_dir=model_dir,
                allow_download=True,
            )
            if retry_succeeds:
                recognizer.load_model()
                assert recognizer._loaded is True
            else:
                with pytest.raises(OSError, match="download failed"):
                    recognizer.load_model()
            assert socket.getdefaulttimeout() == sentinel_timeout
        finally:
            socket.setdefaulttimeout(original_timeout)


def test_file_model_specs_expose_both_selectable_models():
    assert {
        "multilingual_large_ctc",
        "v3_e2e_rnnt",
    }.issubset(FILE_MODEL_SPECS)


@pytest.mark.parametrize(
    ("model_id", "allows_download"),
    [("multilingual_large_ctc", True), ("v3_e2e_rnnt", False)],
)
def test_create_file_recognizer_selects_model_and_configures_download_policy(
    model_id, allows_download, tmp_path
):
    config = {
        "model_path": str(tmp_path / "vosk"),
        "max_segment_seconds": 37.5,
    }

    recognizer = create_file_recognizer(config, model_id)

    assert isinstance(recognizer, QualityRecognizer)
    assert isinstance(recognizer.primary, GigaAMRecognizer)
    assert recognizer.primary.model_name == model_id
    assert recognizer.primary.allow_download is allows_download
    assert recognizer.primary.max_segment_seconds == 24.0
    assert recognizer.fallback.model_path == tmp_path / "vosk"


def test_create_file_recognizer_rejects_unknown_model():
    with pytest.raises(ValueError):
        create_file_recognizer({}, "not-a-real-model")


def test_quality_recognizer_falls_back_after_primary_error():
    primary = Mock(engine_name="GigaAM")
    primary.recognize.side_effect = RuntimeError("model unavailable")
    fallback = Mock(engine_name="Vosk")
    fallback.recognize.return_value = "Резервный текст."
    recognizer = QualityRecognizer(primary, fallback)

    assert recognizer.recognize(b"wav") == "Резервный текст."
    assert recognizer.last_engine == "Vosk"
    assert recognizer.last_fallback_reason == "model unavailable"
