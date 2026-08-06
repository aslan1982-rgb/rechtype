"""Тесты для модуля записи аудио."""

import pytest
import io
import wave
from unittest.mock import Mock, patch, MagicMock

from voiceflow.audio import AudioRecorder


class TestAudioRecorder:
    """Тесты AudioRecorder."""

    def test_init(self):
        """Тест создания экземпляра."""
        recorder = AudioRecorder()
        assert recorder.microphone_index is None
        assert recorder.is_recording is False
        assert recorder.frames == []

    def test_init_with_index(self):
        """Тест создания с указанным микрофоном."""
        recorder = AudioRecorder(microphone_index=2)
        assert recorder.microphone_index == 2

    def test_list_microphones(self):
        """Тест получения списка микрофонов."""
        recorder = AudioRecorder()
        mics = recorder.list_microphones()
        # Должен вернуть список (может быть пустым в CI)
        assert isinstance(mics, list)
        recorder.close()

    def test_get_audio_level_empty(self):
        """Уровень звука без записи = 0."""
        recorder = AudioRecorder()
        assert recorder.get_audio_level() == 0.0
        recorder.close()

    def test_get_audio_level_with_data(self):
        """Уровень звука с данными."""
        recorder = AudioRecorder()
        # Симулируем фрейм с данными
        recorder.frames = [b'\x00\x01' * 512]
        level = recorder.get_audio_level()
        assert 0.0 <= level <= 1.0
        recorder.close()

    def test_start_stop(self):
        """Тест начала и остановки записи."""
        recorder = AudioRecorder()

        # Мокаем PyAudio
        with patch.object(recorder, 'audio') as mock_audio:
            mock_stream = Mock()
            mock_audio.open.return_value = mock_stream
            mock_audio.get_sample_size.return_value = 2  # 16-bit = 2 bytes
            def fake_blocking_read(*_args, **_kwargs):
                # Real PyAudio reads block for the buffer duration.
                import time
                time.sleep(0.001)
                return b'\x00' * 1024

            mock_stream.read.side_effect = fake_blocking_read

            recorder.start()
            assert recorder.is_recording is True

            # Даём время на запуск потока
            import time
            time.sleep(0.1)

            wav_bytes = recorder.stop()
            assert recorder.is_recording is False
            assert isinstance(wav_bytes, bytes)
            assert len(wav_bytes) > 0

    def test_close(self):
        """Тест закрытия ресурсов."""
        recorder = AudioRecorder()
        recorder.close()
        # Должно выполниться без ошибок

    def test_recording_continues_past_old_25_second_boundary(self):
        """Запись останавливается только пользователем, а не старым лимитом."""
        recorder = object.__new__(AudioRecorder)
        recorder.frames = []
        recorder.is_recording = True

        class FakeStream:
            calls = 0

            def read(self, _chunk_size, exception_on_overflow=False):
                assert exception_on_overflow is False
                self.calls += 1
                if self.calls >= 5000:
                    recorder.is_recording = False
                return b"\x00\x00" * AudioRecorder.CHUNK

        recorder.stream = FakeStream()
        recorder._record()

        # The removed implementation stopped at 390 chunks (~24.96 seconds).
        assert len(recorder.frames) == 5000
        assert len(recorder.frames) * AudioRecorder.CHUNK / AudioRecorder.RATE == 320.0
