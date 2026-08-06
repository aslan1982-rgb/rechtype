"""Tests for speech-aware long-recording segmentation."""

import numpy as np

from voiceflow.segmentation import TARGET_SAMPLE_RATE, decode_wav, encode_wav, split_wav


def test_silent_audio_produces_no_segments():
    wav_bytes = encode_wav(np.zeros(TARGET_SAMPLE_RATE * 3, dtype=np.float32))

    assert split_wav(wav_bytes) == []


def test_long_speech_is_split_below_model_limit():
    seconds = 48
    samples = np.zeros(TARGET_SAMPLE_RATE * seconds, dtype=np.float32)
    timeline = np.arange(len(samples), dtype=np.float32) / TARGET_SAMPLE_RATE
    tone = 0.12 * np.sin(2 * np.pi * 220 * timeline)
    for start, end in [(1, 9), (10, 34), (36, 47)]:
        samples[start * TARGET_SAMPLE_RATE : end * TARGET_SAMPLE_RATE] = tone[
            start * TARGET_SAMPLE_RATE : end * TARGET_SAMPLE_RATE
        ]

    segments = split_wav(encode_wav(samples), max_segment_seconds=20.0)

    assert len(segments) >= 3
    durations = [len(decode_wav(segment)[0]) / TARGET_SAMPLE_RATE for segment in segments]
    assert all(0.25 <= duration <= 20.0 for duration in durations)


def test_encode_decode_round_trip():
    source = np.linspace(-0.5, 0.5, TARGET_SAMPLE_RATE, dtype=np.float32)

    decoded, sample_rate = decode_wav(encode_wav(source))

    assert sample_rate == TARGET_SAMPLE_RATE
    assert len(decoded) == len(source)
    assert np.allclose(decoded, source, atol=2 / 32768)
