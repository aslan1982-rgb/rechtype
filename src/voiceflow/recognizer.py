"""Offline speech recognition engines used by RechType."""

from __future__ import annotations

import io
import importlib
import json
import os
import re
import sys
import tempfile
import wave
from pathlib import Path

import vosk

from voiceflow.segmentation import decode_wav, split_wav


def _install_gigaam_wav_loader(gigaam_module, torch_module) -> None:
    """Make GigaAM read our PCM WAV segments without an external ffmpeg binary."""

    def load_local_wav(audio_path: str, sample_rate: int = 16_000):
        samples, decoded_rate = decode_wav(Path(audio_path).read_bytes())
        if decoded_rate != sample_rate:
            raise ValueError(
                f"GigaAM requested {sample_rate} Hz audio, decoded {decoded_rate} Hz"
            )
        return torch_module.from_numpy(samples.copy())

    package_name = gigaam_module.__name__
    for module_name in ("preprocess", "model"):
        module = importlib.import_module(f"{package_name}.{module_name}")
        module.load_audio = load_local_wav


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def _find_vosk_model_path() -> Path:
    root = _runtime_root()
    candidates = [
        root / "models" / "vosk-model-small-ru-0.22",
        Path(sys.executable).parent / "models" / "vosk-model-small-ru-0.22",
    ]
    return next((path for path in candidates if path.exists()), candidates[0])


def _find_gigaam_model_dir() -> Path:
    root = _runtime_root()
    candidates = [
        root / "models" / "gigaam",
        Path(sys.executable).parent / "models" / "gigaam",
    ]
    return next((path for path in candidates if path.exists()), candidates[0])


class VoskRecognizer:
    """Small and fast offline recognizer kept as the reliable fallback."""

    engine_name = "Vosk small ru"

    def __init__(self, model_path=None):
        self.model_path = Path(model_path) if model_path else _find_vosk_model_path()
        self.model = None
        self._loaded = False

    def load_model(self):
        if self._loaded:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(f"Модель Vosk не найдена: {self.model_path}")

        print(f"[RechType] Загрузка резервной модели Vosk из {self.model_path}...")
        self.model = vosk.Model(str(self.model_path))
        self._loaded = True

    def recognize(self, wav_bytes: bytes) -> str:
        if not self._loaded:
            self.load_model()

        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            raw_data = wav.readframes(wav.getnframes())

        if channels == 2:
            import array

            samples = array.array("h", raw_data)
            mono = [(samples[index] + samples[index + 1]) // 2 for index in range(0, len(samples), 2)]
            raw_data = array.array("h", mono).tobytes()

        recognizer = vosk.KaldiRecognizer(self.model, sample_rate)
        recognizer.SetWords(False)
        texts: list[str] = []
        for start in range(0, len(raw_data), 4096):
            if recognizer.AcceptWaveform(raw_data[start : start + 4096]):
                text = json.loads(recognizer.Result()).get("text", "")
                if text:
                    texts.append(text)
        final_text = json.loads(recognizer.FinalResult()).get("text", "")
        if final_text:
            texts.append(final_text)
        return self._post_process(" ".join(texts))

    @staticmethod
    def _post_process(text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        text = text[0].upper() + text[1:]
        if text[-1] not in ".!?":
            text += "."
        return text


class GigaAMRecognizer:
    """High-quality Russian recognizer with local long-audio segmentation."""

    def __init__(
        self,
        model_name: str = "v3_e2e_rnnt",
        model_dir: str | Path | None = None,
        max_segment_seconds: float = 20.0,
    ):
        self.model_name = model_name
        self.model_dir = Path(model_dir) if model_dir else _find_gigaam_model_dir()
        self.max_segment_seconds = max_segment_seconds
        self.model = None
        self._loaded = False

    @property
    def engine_name(self) -> str:
        return f"GigaAM {self.model_name}"

    def load_model(self):
        if self._loaded:
            return

        checkpoint = self.model_dir / f"{self.model_name}.ckpt"
        if not checkpoint.exists():
            raise FileNotFoundError(f"Модель GigaAM не найдена: {checkpoint}")
        if "e2e" in self.model_name:
            tokenizer = self.model_dir / f"{self.model_name}_tokenizer.model"
            if not tokenizer.exists():
                raise FileNotFoundError(f"Токенизатор GigaAM не найден: {tokenizer}")

        import gigaam
        import torch

        # GigaAM's stock loader launches the external `ffmpeg` command even for
        # ordinary PCM WAV files. Portable RechType builds must work on a clean
        # Windows installation, so route its loader through our in-process WAV
        # decoder before constructing the model.
        _install_gigaam_wav_loader(gigaam, torch)

        thread_count = max(1, min(8, (os.cpu_count() or 2) // 2))
        torch.set_num_threads(thread_count)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            # PyTorch allows setting this only before inter-op work starts.
            pass

        print(f"[RechType] Загрузка качественной модели {self.model_name} из {self.model_dir}...")
        self.model = gigaam.load_model(
            self.model_name,
            device="cpu",
            fp16_encoder=False,
            use_flash=False,
            download_root=str(self.model_dir),
        )
        self._loaded = True
        print("[RechType] GigaAM загружена.")

    def recognize(self, wav_bytes: bytes) -> str:
        if not self._loaded:
            self.load_model()

        segments = split_wav(wav_bytes, self.max_segment_seconds)
        if not segments:
            return ""

        texts: list[str] = []
        with tempfile.TemporaryDirectory(prefix="voiceflow-asr-") as temp_dir:
            for index, segment in enumerate(segments):
                segment_path = Path(temp_dir) / f"segment-{index:03d}.wav"
                segment_path.write_bytes(segment)
                result = self.model.transcribe(str(segment_path))
                text = (result.text if hasattr(result, "text") else str(result)).strip()
                if text:
                    texts.append(text)
        return self._post_process(" ".join(texts))

    @staticmethod
    def _post_process(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        if not text:
            return ""
        text = text[0].upper() + text[1:]
        if text[-1] not in ".!?":
            text += "."
        return text


class QualityRecognizer:
    """Use GigaAM first and automatically fall back to Vosk on any local failure."""

    def __init__(self, primary: GigaAMRecognizer, fallback: VoskRecognizer):
        self.primary = primary
        self.fallback = fallback
        self.last_engine = primary.engine_name
        self.last_fallback_reason: str | None = None

    @property
    def engine_name(self) -> str:
        return self.last_engine

    def recognize(self, wav_bytes: bytes) -> str:
        self.last_fallback_reason = None
        try:
            text = self.primary.recognize(wav_bytes)
            self.last_engine = self.primary.engine_name
            return text
        except Exception as error:
            self.last_fallback_reason = str(error)
            print(f"[RechType] GigaAM недоступна, используется Vosk: {error}")
            text = self.fallback.recognize(wav_bytes)
            self.last_engine = self.fallback.engine_name
            return text


def create_recognizer(config: dict):
    """Create the configured recognizer without loading large models eagerly."""
    fallback = VoskRecognizer(model_path=config.get("model_path"))
    if config.get("recognizer", "gigaam") == "vosk":
        return fallback
    primary = GigaAMRecognizer(
        model_name=config.get("gigaam_model", "v3_e2e_rnnt"),
        model_dir=config.get("gigaam_model_dir"),
        max_segment_seconds=float(config.get("max_segment_seconds", 20.0)),
    )
    return QualityRecognizer(primary, fallback)
