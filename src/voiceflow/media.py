"""Decode audio tracks from local audio and video files for offline ASR."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import av
import numpy as np

from voiceflow.segmentation import TARGET_SAMPLE_RATE


SUPPORTED_MEDIA_EXTENSIONS = (
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".mpg",
    ".mpeg",
    ".ts",
)

MEDIA_FILE_FILTER = (
    "Аудио и видео ("
    + " ".join(f"*{extension}" for extension in SUPPORTED_MEDIA_EXTENSIONS)
    + ");;Все файлы (*)"
)


def _resampled_frame_bytes(frame) -> bytes:
    """Return one mono packed signed-16 frame as little-endian bytes."""
    samples = np.asarray(frame.to_ndarray())
    if not samples.size:
        return b""
    return samples.astype("<i2", copy=False).reshape(-1).tobytes()


def media_to_wav_bytes(media_path: str | Path) -> bytes:
    """Decode a file's first audio stream to 16 kHz mono 16-bit PCM WAV.

    PyAV wheels ship with FFmpeg libraries, so this works offline without a
    separately installed ``ffmpeg.exe`` and supports ordinary audio as well as
    audio tracks embedded in video containers.
    """
    path = Path(media_path)
    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден: {path}")

    output = io.BytesIO()
    pcm_byte_count = 0
    try:
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(TARGET_SAMPLE_RATE)
            with av.open(str(path)) as container:
                audio_stream = next(
                    (stream for stream in container.streams if stream.type == "audio"),
                    None,
                )
                if audio_stream is None:
                    raise ValueError("В выбранном файле нет аудиодорожки")

                resampler = av.AudioResampler(
                    format="s16",
                    layout="mono",
                    rate=TARGET_SAMPLE_RATE,
                )
                for frame in container.decode(audio_stream):
                    for converted in resampler.resample(frame):
                        chunk = _resampled_frame_bytes(converted)
                        if chunk:
                            wav.writeframesraw(chunk)
                            pcm_byte_count += len(chunk)
                for converted in resampler.resample(None):
                    chunk = _resampled_frame_bytes(converted)
                    if chunk:
                        wav.writeframesraw(chunk)
                        pcm_byte_count += len(chunk)
    except (ValueError, FileNotFoundError):
        raise
    except Exception as error:
        raise ValueError(f"Не удалось прочитать аудио или видео: {error}") from error

    if not pcm_byte_count:
        raise ValueError("Аудиодорожка пуста или не поддерживается")
    return output.getvalue()
