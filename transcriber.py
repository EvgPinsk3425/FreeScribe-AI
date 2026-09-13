"""Офлайн-транскрибация через faster-whisper, опционально Groq."""

from __future__ import annotations

import io
import logging
import os
import socket
import threading
import time
import wave

import numpy as np
from faster_whisper import WhisperModel

from settings import get_model, huggingface_network, is_model_cached

DEFAULT_MODEL = "large-v3-turbo"
LANGUAGE = "ru"
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
logger = logging.getLogger("whisper_typing")


class GroqError(RuntimeError):
    pass


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _parse_proxy_host_port(proxy: str) -> tuple[str, int] | None:
    raw = (proxy or "").strip()
    if not raw:
        return None
    if "://" in raw:
        rest = raw.split("://", 1)[1]
    else:
        rest = raw
    rest = rest.split("@")[-1]
    rest = rest.strip("/").split("/")[0]
    if rest.startswith("[") and "]:" in rest:
        host, port_s = rest[1:].split("]:", 1)
    elif rest.count(":") == 1:
        host, port_s = rest.split(":")
    else:
        return None
    try:
        return host, int(port_s)
    except ValueError:
        return None


def normalize_proxy(proxy: str) -> str:
    raw = (proxy or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        parsed = _parse_proxy_host_port(raw)
        if parsed:
            _host, port = parsed
            if port in (40000, 1080, 10808, 1081, 9050):
                return f"socks5h://{raw}"
            return f"http://{raw}"
        return raw
    if raw.startswith("socks5://"):
        return "socks5h://" + raw[len("socks5://") :]
    return raw


def proxy_reachable(proxy: str) -> str:
    parsed = _parse_proxy_host_port(proxy)
    if not parsed:
        return ""
    host, port = parsed
    sock = socket.socket()
    sock.settimeout(0.4)
    try:
        err = sock.connect_ex((host, port))
    finally:
        sock.close()
    if err != 0:
        return f"Порт {host}:{port} закрыт — прокси не запущен. Для WARP: warp-cli mode proxy && warp-cli connect. Для v2rayN: локальный SOCKS, не системный прокси."
    return ""


def find_local_proxy() -> str:
    for url in (
        "socks5h://127.0.0.1:40000",
        "socks5h://127.0.0.1:10808",
        "socks5h://127.0.0.1:1080",
        "http://127.0.0.1:10809",
        "http://127.0.0.1:7890",
    ):
        if not proxy_reachable(url):
            return url
    return ""


def _groq_client(api_key: str, proxy: str = ""):
    import httpx

    kwargs = {
        "timeout": 30.0,
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "FreeScribe-AI/2.3",
        },
        "follow_redirects": True,
    }
    proxy = normalize_proxy(proxy)
    if proxy:
        if proxy.startswith("socks"):
            try:
                import socksio  # noqa: F401
            except ImportError as exc:
                raise GroqError(
                    "Для SOCKS5 установите пакет socksio (в сборке exe он уже должен быть)."
                ) from exc
        kwargs["proxy"] = proxy
    try:
        return httpx.Client(**kwargs)
    except TypeError:
        kwargs.pop("proxy", None)
        if proxy:
            kwargs["proxies"] = proxy
        return httpx.Client(**kwargs)


def groq_error_text(status: int, body: str) -> str:
    snippet = (body or "").replace("\n", " ").strip()[:240]
    if status == 401:
        return "Ключ Groq неверный или отозван. Создайте новый на console.groq.com"
    if status == 403:
        local = find_local_proxy()
        extra = f" Найден локальный прокси {local} — вставьте его в настройки." if local else (
            " HTTP-прокси недостаточен, если он тоже из Беларуси. Нужен SOCKS5: "
            "socks5://127.0.0.1:40000 (Cloudflare WARP proxy mode) или "
            "socks5://127.0.0.1:10808 (v2rayN). OpenRouter речь не распознаёт, только чат."
        )
        return "Groq отклонил запрос (403). С IP Беларуси API закрыт." + extra
    if status == 429:
        return "Groq: слишком много запросов. Подождите минуту и повторите."
    if snippet:
        return f"Groq ошибка {status}: {snippet}"
    return f"Groq ошибка {status}"


def test_groq(api_key: str, proxy: str = "") -> str:
    import httpx

    key = (api_key or "").strip()
    if not key:
        return "Сначала вставьте ключ Groq"
    if not key.startswith("gsk_"):
        return "Ключ должен начинаться с gsk_"
    proxy = normalize_proxy(proxy)
    if proxy:
        closed = proxy_reachable(proxy)
        if closed:
            return closed
    try:
        with _groq_client(key, proxy) as client:
            response = client.get(GROQ_MODELS_URL)
    except GroqError as exc:
        return str(exc)
    except httpx.ProxyError as exc:
        return f"Прокси не работает: {exc}. Для SOCKS нужен socks5://127.0.0.1:порт"
    except httpx.TimeoutException:
        return "Groq не отвечает (таймаут). Проверьте SOCKS5/VPN."
    except ImportError as exc:
        return str(exc)
    except Exception as exc:
        return f"Сеть: {exc}"
    if response.status_code == 200:
        via = f" через {proxy}" if proxy else ""
        return f"Groq работает{via}"
    logger.warning("groq test %s %s proxy=%s", response.status_code, response.text[:300], bool(proxy))
    return groq_error_text(response.status_code, response.text)


def transcribe_groq(audio: np.ndarray, sample_rate: int, api_key: str, proxy: str = "") -> str:
    import httpx

    wav = _audio_to_wav_bytes(audio, sample_rate)
    started = time.perf_counter()
    proxy = normalize_proxy(proxy)
    if proxy:
        closed = proxy_reachable(proxy)
        if closed:
            raise GroqError(closed)
    try:
        with _groq_client(api_key, proxy) as client:
            response = client.post(
                GROQ_URL,
                files={"file": ("speech.wav", wav, "audio/wav")},
                data={
                    "model": "whisper-large-v3-turbo",
                    "language": LANGUAGE,
                    "response_format": "json",
                },
            )
    except httpx.ProxyError as exc:
        raise GroqError(f"Прокси не работает: {exc}") from exc
    except httpx.TimeoutException as exc:
        raise GroqError("Groq не отвечает (таймаут). Проверьте интернет или VPN.") from exc
    except Exception as exc:
        raise GroqError(f"Сеть Groq: {exc}") from exc
    if response.status_code != 200:
        logger.warning("groq http %s %s", response.status_code, response.text[:300])
        raise GroqError(groq_error_text(response.status_code, response.text))
    text = (response.json().get("text") or "").strip()
    logger.info("groq transcribe %.2fs: %s", time.perf_counter() - started, text[:80])
    return text


class Transcriber:
    def __init__(self, model_size: str = DEFAULT_MODEL, autoload: bool = True):
        self.model_size = model_size
        self._lock = threading.Lock()
        self._model = None
        self._engine = "faster-whisper"
        self.ready = False
        self.error: str | None = None
        if autoload:
            self.load_model()

    def load_model(self, local_only: bool = False) -> None:
        with self._lock:
            self.ready = False
            self.error = None
            self._model = None
            spec = get_model(self.model_size)
            engine = spec.get("engine") or "faster-whisper"
            self._engine = engine
            threads = min(8, max(4, os.cpu_count() or 4))
            logger.info(
                "loading model %s engine=%s local_only=%s threads=%s",
                self.model_size,
                engine,
                local_only,
                threads,
            )
            try:
                if engine == "onnx-asr":
                    self._model = self._load_onnx(spec, local_only)
                else:
                    self._model = WhisperModel(
                        spec.get("source") or self.model_size,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=threads,
                        num_workers=1,
                        local_files_only=local_only,
                    )
                self.ready = True
                logger.info("model %s ready", self.model_size)
            except Exception as exc:
                self._model = None
                self.error = str(exc)
                logger.exception("failed to load model %s", self.model_size)

    def _load_onnx(self, spec: dict, local_only: bool):
        try:
            import onnx_asr
        except ImportError as exc:
            raise RuntimeError(
                "Для модели Сбера нужен пакет onnx-asr. Установите: pip install \"onnx-asr[cpu,hub]\""
            ) from exc
        from huggingface_hub import snapshot_download

        path = None
        repo = spec.get("repo")
        if repo:
            kwargs = {"repo_id": repo, "local_files_only": local_only}
            patterns = spec.get("allow_patterns")
            if patterns:
                kwargs["allow_patterns"] = patterns
            try:
                if local_only:
                    path = snapshot_download(**kwargs)
                else:
                    with huggingface_network():
                        path = snapshot_download(**kwargs)
            except Exception:
                if local_only:
                    raise
                path = None
        name = spec.get("source") or self.model_size
        quant = spec.get("quantization") or "int8"
        if local_only:
            return onnx_asr.load_model(name, path, quantization=quant)
        with huggingface_network():
            return onnx_asr.load_model(name, path, quantization=quant)

    def set_model_size(self, model_size: str) -> None:
        spec = get_model(model_size)
        if spec["id"] != model_size:
            return
        if model_size == self.model_size and self.ready:
            return
        self.model_size = model_size
        self.load_model(local_only=is_model_cached(model_size))

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if audio is None or len(audio) == 0:
            return ""

        with self._lock:
            if self._model is None:
                raise RuntimeError(self.error or "Модель ещё загружается")
            started = time.perf_counter()
            duration = len(audio) / float(sample_rate or 16000)
            if self._engine == "onnx-asr":
                text = self._transcribe_onnx(audio, sample_rate)
            else:
                text = self._transcribe_whisper(audio, sample_rate, duration)
            logger.info(
                "local transcribe %.2fs model=%s engine=%s audio=%.1fs",
                time.perf_counter() - started,
                self.model_size,
                self._engine,
                duration,
            )
            return text

    def _transcribe_whisper(self, audio: np.ndarray, sample_rate: int, duration: float) -> str:
        use_vad = duration >= 8.0
        kwargs = {
            "language": LANGUAGE,
            "vad_filter": use_vad,
            "beam_size": 1,
            "temperature": 0.0,
            "condition_on_previous_text": False,
            "without_timestamps": True,
        }
        if use_vad:
            kwargs["vad_parameters"] = {
                "threshold": 0.35,
                "min_silence_duration_ms": 400,
                "speech_pad_ms": 250,
            }
        segments, _ = self._model.transcribe(audio, **kwargs)
        return "".join(segment.text for segment in segments).strip()

    def _transcribe_onnx(self, audio: np.ndarray, sample_rate: int) -> str:
        waveform = np.asarray(audio, dtype=np.float32).reshape(-1)
        max_samples = int(sample_rate * 20)
        hop = int(sample_rate * 19)
        parts = []
        start = 0
        while start < len(waveform):
            chunk = waveform[start : start + max_samples]
            if len(chunk) < sample_rate // 5:
                break
            result = self._model.recognize(chunk, sample_rate=int(sample_rate))
            text = _onnx_text(result)
            if text:
                parts.append(text)
            if start + max_samples >= len(waveform):
                break
            start += hop
        return " ".join(parts).strip()


def _onnx_text(result) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, (list, tuple)):
        return " ".join(_onnx_text(item) for item in result if item is not None).strip()
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()
    return str(result).strip()
