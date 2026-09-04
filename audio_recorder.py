"""Захват аудио с микрофона в оперативную память через sounddevice."""

import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1


class AudioRecorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._buffers: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording = False
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}")
        if self._recording:
            with self._lock:
                self._buffers.append(indata.copy())

    def start(self) -> None:
        with self._lock:
            self._buffers.clear()
            self._recording = True

        if self._stream is None:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )

        if not self._stream.active:
            self._stream.start()

    def stop(self) -> np.ndarray | None:
        self._recording = False

        with self._lock:
            if not self._buffers:
                return None
            audio = np.concatenate(self._buffers, axis=0)
            self._buffers.clear()

        return audio.flatten()

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
