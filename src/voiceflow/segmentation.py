"""Local WAV conversion and speech-aware segmentation for short-form ASR models."""

from __future__ import annotations

import io
import wave

import numpy as np


TARGET_SAMPLE_RATE = 16_000


def decode_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode 16-bit PCM WAV bytes into mono float32 samples."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        raw = wav.readframes(wav.getnframes())

    if sample_width != 2:
        raise ValueError(f"Поддерживается только 16-битный PCM WAV, получено: {sample_width * 8} бит")

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    if sample_rate != TARGET_SAMPLE_RATE and len(samples):
        old_points = np.arange(len(samples), dtype=np.float64)
        new_length = round(len(samples) * TARGET_SAMPLE_RATE / sample_rate)
        new_points = np.linspace(0, len(samples) - 1, new_length)
        samples = np.interp(new_points, old_points, samples).astype(np.float32)
        sample_rate = TARGET_SAMPLE_RATE

    return samples, sample_rate


def encode_wav(samples: np.ndarray, sample_rate: int = TARGET_SAMPLE_RATE) -> bytes:
    """Encode mono float samples as a 16-bit PCM WAV."""
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _frame_rms(samples: np.ndarray, frame_samples: int) -> np.ndarray:
    frame_count = (len(samples) + frame_samples - 1) // frame_samples
    padded = np.pad(samples, (0, frame_count * frame_samples - len(samples)))
    frames = padded.reshape(frame_count, frame_samples)
    return np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)


def speech_ranges(
    samples: np.ndarray,
    sample_rate: int = TARGET_SAMPLE_RATE,
    max_segment_seconds: float = 20.0,
) -> list[tuple[int, int]]:
    """Return speech-containing sample ranges that never exceed the ASR limit."""
    if len(samples) == 0:
        return []

    frame_ms = 30
    frame_samples = sample_rate * frame_ms // 1000
    rms = _frame_rms(samples, frame_samples)
    if float(rms.max()) < 0.0008:
        return []

    noise = float(np.percentile(rms, 20))
    speech_peak = float(np.percentile(rms, 90))
    threshold = max(0.0015, noise * 2.2, speech_peak * 0.10)
    active_indexes = np.flatnonzero(rms >= threshold)

    if not len(active_indexes):
        active_indexes = np.arange(len(rms))

    max_gap_frames = round(0.65 * 1000 / frame_ms)
    min_speech_frames = round(0.25 * 1000 / frame_ms)
    pad_frames = round(0.22 * 1000 / frame_ms)
    regions: list[tuple[int, int]] = []
    start = previous = int(active_indexes[0])
    for frame_index in map(int, active_indexes[1:]):
        if frame_index - previous > max_gap_frames:
            if previous - start + 1 >= min_speech_frames:
                regions.append((max(0, start - pad_frames), min(len(rms), previous + 1 + pad_frames)))
            start = frame_index
        previous = frame_index
    if previous - start + 1 >= min_speech_frames:
        regions.append((max(0, start - pad_frames), min(len(rms), previous + 1 + pad_frames)))

    max_frames = max(1, round(max_segment_seconds * 1000 / frame_ms))
    preferred_frames = max(1, round((max_segment_seconds - 2.0) * 1000 / frame_ms))
    search_frames = round(3.0 * 1000 / frame_ms)
    split_regions: list[tuple[int, int]] = []
    for region_start, region_end in regions:
        cursor = region_start
        while region_end - cursor > max_frames:
            target = cursor + preferred_frames
            search_start = max(cursor + max_frames // 2, target - search_frames)
            search_end = min(region_end, cursor + max_frames, target + search_frames)
            split_at = search_start + int(np.argmin(rms[search_start:search_end]))
            if split_at <= cursor:
                split_at = cursor + max_frames
            split_regions.append((cursor, split_at))
            cursor = split_at
        if region_end > cursor:
            split_regions.append((cursor, region_end))

    sample_regions = [
        (start * frame_samples, min(len(samples), end * frame_samples))
        for start, end in split_regions
        if end > start
    ]

    # Preserve context by packing neighboring utterances and their silence gap.
    max_samples = round(max_segment_seconds * sample_rate)
    packed: list[tuple[int, int]] = []
    for start, end in sample_regions:
        if packed and end - packed[-1][0] <= max_samples:
            packed[-1] = (packed[-1][0], end)
        else:
            packed.append((start, end))

    return [(start, end) for start, end in packed if end - start >= sample_rate // 4]


def split_wav(wav_bytes: bytes, max_segment_seconds: float = 20.0) -> list[bytes]:
    """Split one recording into model-ready WAV byte strings."""
    samples, sample_rate = decode_wav(wav_bytes)
    return [
        encode_wav(samples[start:end], sample_rate)
        for start, end in speech_ranges(samples, sample_rate, max_segment_seconds)
    ]
