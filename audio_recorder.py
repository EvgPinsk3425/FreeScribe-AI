"""Захват микрофона: waveIn (RDP «Удалённое аудио») и sounddevice."""

from __future__ import annotations

import logging
import threading
import time

import numpy as np
import sounddevice as sd

from compat import IS_WIN

SAMPLE_RATE = 16000
CHANNELS = 1
logger = logging.getLogger("whisper_typing")

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    WHDR_DONE = 0x00000001
    WAVE_FORMAT_PCM = 1
    CALLBACK_EVENT = 0x00050000
    MAXPNAMELEN = 32
    winmm = ctypes.WinDLL("winmm")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    HWAVEIN = ctypes.c_void_p
else:
    WHDR_DONE = 0
    WAVE_FORMAT_PCM = 1
    CALLBACK_EVENT = 0
    MAXPNAMELEN = 32
    winmm = None
    kernel32 = None
    HWAVEIN = None


if IS_WIN:
    class WAVEFORMATEX(ctypes.Structure):
        _fields_ = [
            ("wFormatTag", wintypes.WORD),
            ("nChannels", wintypes.WORD),
            ("nSamplesPerSec", wintypes.DWORD),
            ("nAvgBytesPerSec", wintypes.DWORD),
            ("nBlockAlign", wintypes.WORD),
            ("wBitsPerSample", wintypes.WORD),
            ("cbSize", wintypes.WORD),
        ]

    class WAVEHDR(ctypes.Structure):
        _fields_ = [
            ("lpData", ctypes.c_void_p),
            ("dwBufferLength", wintypes.DWORD),
            ("dwBytesRecorded", wintypes.DWORD),
            ("dwUser", ctypes.c_void_p),
            ("dwFlags", wintypes.DWORD),
            ("dwLoops", wintypes.DWORD),
            ("lpNext", ctypes.c_void_p),
            ("reserved", ctypes.c_void_p),
        ]

    class WAVEINCAPSW(ctypes.Structure):
        _fields_ = [
            ("wMid", wintypes.WORD),
            ("wPid", wintypes.WORD),
            ("vDriverVersion", wintypes.DWORD),
            ("szPname", wintypes.WCHAR * MAXPNAMELEN),
            ("dwFormats", wintypes.DWORD),
            ("wChannels", wintypes.WORD),
            ("wReserved1", wintypes.WORD),
        ]

    winmm.waveInGetNumDevs.restype = wintypes.UINT
    winmm.waveInGetDevCapsW.argtypes = [ctypes.c_uint, ctypes.POINTER(WAVEINCAPSW), wintypes.UINT]
    winmm.waveInGetDevCapsW.restype = wintypes.UINT
    winmm.waveInOpen.argtypes = [
        ctypes.POINTER(HWAVEIN),
        wintypes.UINT,
        ctypes.POINTER(WAVEFORMATEX),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    winmm.waveInOpen.restype = wintypes.UINT
    winmm.waveInPrepareHeader.argtypes = [HWAVEIN, ctypes.POINTER(WAVEHDR), wintypes.UINT]
    winmm.waveInAddBuffer.argtypes = [HWAVEIN, ctypes.POINTER(WAVEHDR), wintypes.UINT]
    winmm.waveInUnprepareHeader.argtypes = [HWAVEIN, ctypes.POINTER(WAVEHDR), wintypes.UINT]
    winmm.waveInStart.argtypes = [HWAVEIN]
    winmm.waveInStop.argtypes = [HWAVEIN]
    winmm.waveInReset.argtypes = [HWAVEIN]
    winmm.waveInClose.argtypes = [HWAVEIN]
    kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    kernel32.ResetEvent.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


def _refresh_portaudio() -> None:
    try:
        sd._terminate()
    except Exception:
        pass
    try:
        sd._initialize()
    except Exception:
        logger.exception("portaudio init")


def _hostapi_name(index: int) -> str:
    try:
        return str(sd.query_hostapis()[index]["name"])
    except Exception:
        return str(index)


def _wavein_devices() -> list[dict]:
    if not IS_WIN or winmm is None:
        return []
    found = []
    count = int(winmm.waveInGetNumDevs())
    for index in range(count):
        caps = WAVEINCAPSW()
        if winmm.waveInGetDevCapsW(index, ctypes.byref(caps), ctypes.sizeof(caps)):
            continue
        name = str(caps.szPname).strip() or f"waveIn {index}"
        found.append(
            {
                "id": f"wavein:{index}",
                "name": name,
                "label": f"{name}  —  RDP / MME",
                "backend": "wavein",
                "index": index,
                "channels": int(caps.wChannels or 1),
                "rate": 16000,
                "hostapi": "waveIn",
            }
        )
    return found


def _sounddevice_inputs() -> list[dict]:
    try:
        devices = list(sd.query_devices())
    except Exception:
        logger.exception("query_devices")
        return []
    found = []
    for i, item in enumerate(devices):
        try:
            channels = int(item["max_input_channels"])
        except Exception:
            continue
        if channels <= 0:
            continue
        name = str(item["name"])
        api = _hostapi_name(int(item.get("hostapi") or 0))
        found.append(
            {
                "id": f"sd:{i}",
                "name": name,
                "label": f"{name}  —  {api}",
                "backend": "sounddevice",
                "index": i,
                "channels": channels,
                "rate": int(item.get("default_samplerate") or 44100),
                "hostapi": api,
            }
        )
    return found


def list_capture_devices() -> list[dict]:
    devices = _wavein_devices() + _sounddevice_inputs()

    def _rank(item: dict) -> tuple:
        name = item["name"].lower()
        if any(token in name for token in ("удален", "remote")):
            group = 0
        elif item["backend"] == "wavein":
            group = 1
        elif any(token in name for token in ("mixed", "stereo mix", "loopback")):
            group = 3
        else:
            group = 2
        return (group, item["backend"] != "wavein", item["index"])

    devices.sort(key=_rank)
    return devices


def _resample_mono(audio: np.ndarray, src_rate: int) -> np.ndarray:
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32, copy=False).flatten()
    if src_rate == SAMPLE_RATE or audio.size == 0:
        return audio
    n_out = max(1, int(round(audio.size * SAMPLE_RATE / float(src_rate))))
    old_x = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
    new_x = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(new_x, old_x, audio).astype(np.float32)


class _WaveInStream:
    def __init__(self, device_index: int, on_audio):
        self.device_index = device_index
        self.on_audio = on_audio
        self.rate = SAMPLE_RATE
        self.channels = 1
        self._handle = HWAVEIN()
        self._event = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._hdrs: list[WAVEHDR] = []
        self._bufs: list[ctypes.Array] = []

    def start(self) -> None:
        last: Exception | None = None
        for rate, channels in ((16000, 1), (16000, 2), (44100, 1), (44100, 2)):
            try:
                self._open(rate, channels)
                self.rate = rate
                self.channels = channels
                logger.info("waveIn open idx=%s rate=%s ch=%s", self.device_index, rate, channels)
                return
            except Exception as exc:
                last = exc
                self._close_handles()
        raise RuntimeError(f"waveIn: {last}")

    def _open(self, rate: int, channels: int) -> None:
        fmt = WAVEFORMATEX(
            WAVE_FORMAT_PCM,
            channels,
            rate,
            rate * channels * 2,
            channels * 2,
            16,
            0,
        )
        self._event = kernel32.CreateEventW(None, True, False, None)
        handle = HWAVEIN()
        err = winmm.waveInOpen(
            ctypes.byref(handle),
            self.device_index,
            ctypes.byref(fmt),
            self._event,
            None,
            CALLBACK_EVENT,
        )
        if err:
            raise RuntimeError(f"waveInOpen {err}")
        self._handle = handle
        nbytes = max(rate * channels * 2 // 5, 8192)
        self._hdrs = []
        self._bufs = []
        for _ in range(8):
            buf = (ctypes.c_char * nbytes)()
            hdr = WAVEHDR()
            hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
            hdr.dwBufferLength = nbytes
            if winmm.waveInPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR)):
                raise RuntimeError("waveInPrepareHeader")
            if winmm.waveInAddBuffer(handle, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR)):
                raise RuntimeError("waveInAddBuffer")
            self._bufs.append(buf)
            self._hdrs.append(hdr)
        if winmm.waveInStart(handle):
            raise RuntimeError("waveInStart")
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll, name="wavein", daemon=True)
        self._thread.start()

    def _collect(self, requeue: bool) -> None:
        handle = self._handle
        if not handle:
            return
        for hdr in self._hdrs:
            if not (hdr.dwFlags & WHDR_DONE):
                continue
            nbytes = int(hdr.dwBytesRecorded)
            if nbytes:
                raw = ctypes.string_at(hdr.lpData, nbytes)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if self.channels >= 2:
                    usable = samples.size - (samples.size % self.channels)
                    samples = samples[:usable].reshape(-1, self.channels).mean(axis=1)
                self.on_audio(samples, self.rate)
            hdr.dwBytesRecorded = 0
            hdr.dwFlags = 0x00000002
            if requeue:
                err = winmm.waveInAddBuffer(handle, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                if err:
                    logger.warning("waveInAddBuffer err=%s", err)

    def _poll(self) -> None:
        try:
            while not self._stop.is_set():
                kernel32.WaitForSingleObject(self._event, 50)
                if self._event:
                    kernel32.ResetEvent(self._event)
                self._collect(requeue=True)
        except Exception:
            logger.exception("waveIn poll")

    def stop(self) -> None:
        self._stop.set()
        self._collect(requeue=False)
        if self._handle:
            winmm.waveInStop(self._handle)
            self._collect(requeue=False)
            winmm.waveInReset(self._handle)
            self._collect(requeue=False)
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None
        if self._handle:
            for hdr in self._hdrs:
                winmm.waveInUnprepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
        self._close_handles()

    def _close_handles(self) -> None:
        if self._handle:
            winmm.waveInClose(self._handle)
            self._handle = HWAVEIN()
        if self._event:
            kernel32.CloseHandle(self._event)
            self._event = None
        self._hdrs = []
        self._bufs = []


class AudioRecorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_id = ""
        self.gain = 1.0
        self._buffers: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording = False
        self._monitor = False
        self._stream: sd.InputStream | None = None
        self._wave: _WaveInStream | None = None
        self._status = ""
        self._capture_rate = SAMPLE_RATE
        self._level = 0.0

    def configure(self, device_id: str = "", gain: float = 1.0) -> None:
        self.device_id = (device_id or "").strip()
        try:
            self.gain = max(0.2, min(8.0, float(gain)))
        except (TypeError, ValueError):
            self.gain = 1.0

    def current_level(self) -> float:
        return min(1.0, self._level * self.gain)

    def _on_chunk(self, samples: np.ndarray, rate: int) -> None:
        if samples.size == 0:
            return
        peak = float(np.max(np.abs(samples)))
        with self._lock:
            self._level = max(peak, self._level * 0.82)
            self._capture_rate = rate
            if self._recording:
                self._buffers.append(np.asarray(samples, dtype=np.float32))

    def _sd_callback(self, indata, frames, time_info, status):
        if status:
            self._status = str(status)
            logger.warning("audio callback status=%s", status)
        if not (self._recording or self._monitor):
            return
        data = np.asarray(indata, dtype=np.float32)
        if data.ndim > 1:
            data = data.mean(axis=1)
        self._on_chunk(data.flatten(), self._capture_rate)

    def _close_stream(self) -> None:
        wave = self._wave
        self._wave = None
        if wave:
            try:
                wave.stop()
            except Exception:
                logger.exception("waveIn stop")
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            if stream.active:
                stream.stop()
        except Exception:
            logger.exception("stream stop")
        try:
            stream.close()
        except Exception:
            logger.exception("stream close")

    def _pick_device(self) -> dict:
        devices = list_capture_devices()
        if not devices:
            _refresh_portaudio()
            devices = list_capture_devices()
        if not devices:
            raise RuntimeError(
                "Микрофон не найден. На Mac: Системные настройки → Конфиденциальность → Микрофон. "
                "На Windows: проверьте устройство и запись звука в RDP."
            )
        wanted = self.device_id
        if wanted:
            for item in devices:
                if item["id"] == wanted or item["name"] == wanted:
                    return item
        return devices[0]

    def _start_sounddevice(self, item: dict) -> None:
        last_error: Exception | None = None
        rates = []
        for rate in (SAMPLE_RATE, item.get("rate") or 44100, 48000, 44100):
            if rate and int(rate) not in rates:
                rates.append(int(rate))
        channels_opts = [1]
        if int(item.get("channels") or 1) >= 2:
            channels_opts.append(2)
        for rate in rates:
            for channels in channels_opts:
                try:
                    self._close_stream()
                    stream = sd.InputStream(
                        device=item["index"],
                        samplerate=rate,
                        channels=channels,
                        dtype="float32",
                        blocksize=1024,
                        latency="high",
                        callback=self._sd_callback,
                    )
                    stream.start()
                    if not stream.active:
                        stream.close()
                        continue
                    self._stream = stream
                    self._capture_rate = rate
                    logger.info(
                        "mic started sd name=%s idx=%s rate=%s ch=%s",
                        item["name"],
                        item["index"],
                        rate,
                        channels,
                    )
                    return
                except Exception as exc:
                    last_error = exc
                    logger.info(
                        "mic skip sd name=%s idx=%s rate=%s ch=%s err=%s",
                        item["name"],
                        item["index"],
                        rate,
                        channels,
                        exc,
                    )
                    self._close_stream()
        raise RuntimeError(f"sounddevice: {last_error}")

    def _open_selected(self) -> dict:
        item = self._pick_device()
        logger.info("mic pick id=%s name=%s backend=%s", item["id"], item["name"], item["backend"])
        if item["backend"] == "wavein":
            self._close_stream()
            wave = _WaveInStream(int(item["index"]), self._on_chunk)
            wave.start()
            self._wave = wave
            self._capture_rate = wave.rate
        else:
            self._start_sounddevice(item)
        return item

    def start(self) -> None:
        self._close_stream()
        self._status = ""
        self._level = 0.0
        with self._lock:
            self._buffers.clear()
            self._recording = True
            self._monitor = False
        try:
            item = self._open_selected()
            logger.info("mic record device=%s gain=%.2f", item["label"], self.gain)
        except Exception:
            self._recording = False
            raise

    def start_monitor(self) -> None:
        self._close_stream()
        self._status = ""
        self._level = 0.0
        with self._lock:
            self._buffers.clear()
            self._recording = False
            self._monitor = True
        self._open_selected()

    def stop(self) -> np.ndarray | None:
        self._recording = False
        self._monitor = False
        time.sleep(0.08)
        self._close_stream()
        with self._lock:
            chunks = len(self._buffers)
            if not self._buffers:
                logger.info("mic stop empty status=%s", self._status or "ok")
                return None
            audio = np.concatenate(self._buffers, axis=0)
            self._buffers.clear()
        audio = _resample_mono(audio, self._capture_rate)
        if self.gain != 1.0:
            audio = np.clip(audio * self.gain, -1.0, 1.0).astype(np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        logger.info(
            "mic stop chunks=%s samples=%s sec=%.2f peak=%.4f rate=%s gain=%.2f status=%s",
            chunks,
            int(audio.size),
            audio.size / float(SAMPLE_RATE),
            peak,
            self._capture_rate,
            self.gain,
            self._status or "ok",
        )
        return audio

    def close(self) -> None:
        self._recording = False
        self._monitor = False
        self._close_stream()
