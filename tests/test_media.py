"""Tests for decoding local audio/video files into model-ready WAV."""

import io
import wave

import numpy as np
import pytest
import av

from voiceflow.media import media_to_wav_bytes
from voiceflow.segmentation import TARGET_SAMPLE_RATE


def _write_stereo_wav(path, sample_rate: int = 8_000, duration: float = 0.25) -> None:
    points = np.arange(round(sample_rate * duration), dtype=np.float64)
    left = (np.sin(2 * np.pi * 220 * points / sample_rate) * 12_000).astype("<i2")
    right = (np.sin(2 * np.pi * 330 * points / sample_rate) * 8_000).astype("<i2")
    stereo = np.column_stack((left, right)).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(stereo)


def test_decodes_and_resamples_audio_file(tmp_path):
    source = tmp_path / "пример записи.wav"
    _write_stereo_wav(source)

    wav_bytes = media_to_wav_bytes(source)

    with wave.open(io.BytesIO(wav_bytes), "rb") as decoded:
        assert decoded.getnchannels() == 1
        assert decoded.getsampwidth() == 2
        assert decoded.getframerate() == TARGET_SAMPLE_RATE
        assert decoded.getnframes() == pytest.approx(TARGET_SAMPLE_RATE * 0.25, abs=32)
        assert decoded.readframes(decoded.getnframes())


def test_extracts_audio_track_from_video_container(tmp_path):
    source = tmp_path / "video-with-speech-track.mp4"
    with av.open(str(source), "w") as container:
        video_stream = container.add_stream("mpeg4", rate=5)
        video_stream.width = 64
        video_stream.height = 48
        video_stream.pix_fmt = "yuv420p"
        audio_stream = container.add_stream("aac", rate=44_100)
        audio_stream.layout = "mono"

        for index in range(5):
            image = np.full((48, 64, 3), index * 30, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(image, format="rgb24")
            frame.pts = index
            for packet in video_stream.encode(frame):
                container.mux(packet)
        for packet in video_stream.encode(None):
            container.mux(packet)

        points = np.arange(44_100, dtype=np.float64)
        samples = (np.sin(2 * np.pi * 440 * points / 44_100) * 10_000).astype("<i2")
        audio_frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1),
            format="s16",
            layout="mono",
        )
        audio_frame.sample_rate = 44_100
        for packet in audio_stream.encode(audio_frame):
            container.mux(packet)
        for packet in audio_stream.encode(None):
            container.mux(packet)

    wav_bytes = media_to_wav_bytes(source)

    with wave.open(io.BytesIO(wav_bytes), "rb") as decoded:
        assert decoded.getnchannels() == 1
        assert decoded.getsampwidth() == 2
        assert decoded.getframerate() == TARGET_SAMPLE_RATE
        assert decoded.getnframes() == pytest.approx(TARGET_SAMPLE_RATE, abs=1_000)


def test_rejects_file_without_audio_stream(tmp_path, monkeypatch):
    source = tmp_path / "silent-video.mp4"
    source.write_bytes(b"placeholder")

    class VideoStream:
        type = "video"

    class Container:
        streams = [VideoStream()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("voiceflow.media.av.open", lambda *_args, **_kwargs: Container())

    with pytest.raises(ValueError, match="нет аудиодорожки"):
        media_to_wav_bytes(source)


def test_rejects_empty_audio_track(tmp_path):
    source = tmp_path / "empty.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(TARGET_SAMPLE_RATE)

    with pytest.raises(ValueError, match="пуста"):
        media_to_wav_bytes(source)


def test_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="Файл не найден"):
        media_to_wav_bytes(tmp_path / "missing.mp3")
