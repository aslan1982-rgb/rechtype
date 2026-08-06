"""Модуль записи аудио с микрофона."""

import io
import wave
import threading
import numpy as np
import pyaudio


class AudioRecorder:
    """Потоковая запись аудио с микрофона."""

    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1024

    def __init__(self, microphone_index=None):
        self.audio = pyaudio.PyAudio()
        self.microphone_index = microphone_index
        self.stream = None
        self.frames = []
        self.is_recording = False
        self._thread = None

    def list_microphones(self):
        """Вернуть список доступных микрофонов."""
        devices = []
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append((i, info["name"]))
        return devices

    def start(self):
        """Начать запись."""
        if self.is_recording:
            return
        self.frames = []
        self.is_recording = True
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=self.microphone_index,
            frames_per_buffer=self.CHUNK,
        )
        self._thread = threading.Thread(
            target=self._record,
            name="RechTypeAudioRecorder",
            daemon=True,
        )
        self._thread.start()

    def _record(self):
        """Внутренний цикл записи."""
        # Vosk accepts streaming audio of arbitrary duration. Keep collecting
        # frames until the user explicitly toggles recording off.
        while self.is_recording:
            try:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                self.frames.append(data)
            except Exception:
                break

    def get_audio_level(self):
        """Получить текущий уровень громкости (0.0 - 1.0)."""
        if not self.frames:
            return 0.0
        last_frame = self.frames[-1]
        audio_data = np.frombuffer(last_frame, dtype=np.int16)
        if len(audio_data) == 0:
            return 0.0
        rms = np.sqrt(np.mean(audio_data.astype(np.float64) ** 2))
        level = min(rms / 32768.0 * 8, 1.0)
        return level

    def stop(self):
        """Остановить запись и вернуть audio bytes."""
        self.is_recording = False
        if self._thread:
            self._thread.join(timeout=1)
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(self.frames))
        return buffer.getvalue()

    def close(self):
        """Освободить ресурсы."""
        self.audio.terminate()
