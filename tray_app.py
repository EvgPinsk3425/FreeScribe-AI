"""Системный трей и управление приложением."""

from __future__ import annotations

import ctypes
import logging
import sys
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pystray
from PIL import Image, ImageDraw

from audio_recorder import AudioRecorder, SAMPLE_RATE, list_capture_devices, mic_rdp_warning
from hotkey import HotkeyManager
from injector import capture_target, inject_text
from overlay import RecordOverlay
from settings import (
    APP_TITLE,
    HOTKEY_OPTIONS,
    MODEL_CATALOG,
    best_cached_model,
    cached_models,
    disk_free,
    format_hotkey,
    get_model,
    hotkey_label,
    is_model_cached,
    load_settings,
    save_settings,
    spec_from_preset,
)
COLOR_IDLE = (70, 130, 220, 255)
COLOR_RECORD = (200, 60, 60, 255)
COLOR_PAUSE = (140, 140, 140, 255)
logger = logging.getLogger("whisper_typing")
_ICON_CACHE: dict[tuple, Image.Image] = {}
_JUNK_PHRASES = (
    "продолжение следует",
    "субтитры создавал",
    "dimatorzok",
    "thanks for watching",
    "subscribe to",
)
# После усиления (mic_gain) — ниже считаем «микрофон не слышит».
_MIN_AUDIO_PEAK = 0.003


def _is_junk_transcript(text: str) -> bool:
    low = (text or "").lower()
    return any(token in low for token in _JUNK_PHRASES)


def _audio_peak(audio: np.ndarray) -> float:
    if audio is None or not len(audio):
        return 0.0
    return float(np.max(np.abs(audio)))
_WM_APP = 0x8000
_user32 = ctypes.WinDLL("user32")
_user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
_user32.PostMessageW.restype = ctypes.c_int


def _create_icon(color=COLOR_IDLE, size: int = 64) -> Image.Image:
    cached = _ICON_CACHE.get(color)
    if cached is not None:
        return cached
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((1, 1, size - 2, size - 2), fill=color)

    white = (255, 255, 255, 255)
    body = (size * 0.35, size * 0.18, size * 0.65, size * 0.58)
    draw.rounded_rectangle(body, radius=size // 8, fill=white)

    arc_box = (size * 0.28, size * 0.50, size * 0.72, size * 0.84)
    draw.arc(arc_box, start=0, end=180, fill=white, width=max(3, size // 14))

    stem = (size * 0.46, size * 0.78, size * 0.54, size * 0.90)
    draw.rectangle(stem, fill=white)

    base = (size * 0.32, size * 0.88, size * 0.68, size * 0.94)
    draw.rounded_rectangle(base, radius=2, fill=white)

    _ICON_CACHE[color] = image
    return image


class WhisperTrayApp:
    def __init__(self):
        self.settings = load_settings()
        from compat import is_run_at_startup

        self.settings["run_at_startup"] = is_run_at_startup()
        requested = self.settings["model"]
        if requested == "large-v3":
            requested = "large-v3-turbo"
            self.settings["model"] = requested
            save_settings(self.settings)
        self._wanted_model = requested
        startup_model = best_cached_model(requested)
        self._fallback_notice = None
        if startup_model != requested:
            logger.warning("model %s not ready, starting with %s", requested, startup_model)
            self._fallback_notice = (
                f"Сначала {startup_model}. Скачиваю {requested} — она точнее и быстрее на CPU."
            )

        self.recorder = AudioRecorder()
        self._configure_recorder()
        from transcriber import Transcriber

        self.transcriber = Transcriber(startup_model, autoload=False)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._paste_hwnd = 0
        self._paste_focus = 0

        self.active = True
        self.recording = False
        self._state_lock = threading.Lock()

        self._hook = HotkeyManager(
            self._on_hotkey_press,
            self._on_hotkey_release,
            hotkey_id=self.settings["hotkey"],
            hold_mode=self.settings["hotkey_mode"] == "hold",
            spec=self.settings.get("hotkey_spec"),
        )
        self._user_quit = False
        self._record_timer: threading.Timer | None = None
        self._ui_q: queue.Queue = queue.Queue()
        self._overlay = RecordOverlay()
        self._mic_rdp_warned = False
        self._icon = self._make_icon()

    def _on_tray_thread(self, fn) -> None:
        hwnd = getattr(self._icon, "_hwnd", None)
        if hwnd:
            self._ui_q.put(fn)
            _user32.PostMessageW(hwnd, _WM_APP, 0, 0)
            return
        fn()

    def _drain_ui(self, _wparam=0, _lparam=0):
        while True:
            try:
                fn = self._ui_q.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                logger.exception("tray ui")
        return 0

    def _make_icon(self) -> pystray.Icon:
        return pystray.Icon(
            "freescribe_ai",
            _create_icon(),
            "FreeScribe-AI",
            menu=self._build_menu(),
        )

    def _hotkey_label(self) -> str:
        return hotkey_label(self.settings)

    def _tooltip(self) -> str:
        label = self._hotkey_label()
        if self.settings["hotkey_mode"] == "hold":
            hint = f"Удерживайте {label}"
        else:
            hint = f"{label} — старт/стоп"
        if self.recording:
            return f"FreeScribe-AI — идёт запись ({hint})"
        if not self.active:
            return "FreeScribe-AI — пауза"
        return f"FreeScribe-AI — {hint}"

    def _status_label(self, _item=None) -> str:
        if self.recording:
            return "Статус: Запись..."
        if getattr(self.transcriber, "error", None):
            return "Статус: Ошибка модели"
        if not getattr(self.transcriber, "ready", False):
            if (self.settings.get("groq_api_key") or "").strip():
                return "Статус: Работает (Groq)" if self.active else "Статус: Пауза"
            return "Статус: Загрузка модели..."
        return "Статус: Работает" if self.active else "Статус: Пауза"

    def _model_label(self, model_id: str) -> str:
        spec = get_model(model_id)
        downloaded = "на диске" if model_id in cached_models() else "не на диске"
        mark = " • текущая" if model_id == self.transcriber.model_size else ""
        return f"{spec['label']} ({downloaded}){mark}"

    def _record_label(self, _item=None) -> str:
        if self.recording:
            return f"Стоп записи ({self._hotkey_label()})"
        return f"Начать запись ({self._hotkey_label()})"

    def _hotkey_action(self, hid: str):
        def action(_icon=None, _item=None):
            self._set_hotkey(hid)

        return action

    def _hotkey_checked(self, hid: str):
        def checked(_item=None):
            return self.settings["hotkey"] == hid

        return checked

    def _model_action(self, mid: str):
        def action(_icon=None, _item=None):
            self._set_model(mid)

        return action

    def _model_checked(self, mid: str):
        def checked(_item=None):
            return self.transcriber.model_size == mid

        return checked

    def _model_text(self, mid: str):
        def text(_item=None):
            return self._model_label(mid)

        return text

    def _build_menu(self) -> pystray.Menu:
        current = hotkey_label(self.settings)
        hotkey_items = [
            pystray.MenuItem(f"Сейчас: {current}", lambda *_: None, enabled=False),
        ]
        hotkey_items += [
            pystray.MenuItem(
                label,
                self._hotkey_action(hid),
                checked=self._hotkey_checked(hid),
                radio=True,
            )
            for hid, label, *_rest in HOTKEY_OPTIONS
        ]
        groups: dict[str, list] = {}
        for spec in MODEL_CATALOG:
            groups.setdefault(spec["group"], []).append(spec)
        model_groups = []
        for group, items in groups.items():
            child = [
                pystray.MenuItem(
                    self._model_text(item["id"]),
                    self._model_action(item["id"]),
                    checked=self._model_checked(item["id"]),
                    radio=True,
                )
                for item in items
            ]
            model_groups.append(pystray.MenuItem(group, pystray.Menu(*child)))
        return pystray.Menu(
            pystray.MenuItem(self._status_label, self._toggle_active),
            pystray.MenuItem(
                self._record_label,
                self._toggle_recording,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Горячая клавиша", pystray.Menu(*hotkey_items)),
            pystray.MenuItem(
                "Режим",
                pystray.Menu(
                    pystray.MenuItem(
                        "Нажать — старт/стоп",
                        lambda _icon, _item: self._set_mode("toggle"),
                        checked=lambda _item: self.settings["hotkey_mode"] == "toggle",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Удерживать клавишу",
                        lambda _icon, _item: self._set_mode("hold"),
                        checked=lambda _item: self.settings["hotkey_mode"] == "hold",
                        radio=True,
                    ),
                ),
            ),
            pystray.MenuItem("Модель", pystray.Menu(*model_groups)),
            pystray.MenuItem("Настройки...", self._open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._quit),
        )

    def _set_icon_color(self) -> None:
        def apply() -> None:
            if self.recording:
                color = COLOR_RECORD
            elif self.active:
                color = COLOR_IDLE
            else:
                color = COLOR_PAUSE
            try:
                self._icon.icon = _create_icon(color)
                self._icon.title = self._tooltip()
            except Exception:
                logger.exception("tray icon update")

        self._on_tray_thread(apply)

    def _refresh_menu(self) -> None:
        self._icon.menu = self._build_menu()
        self._set_icon_color()

    def _persist(self) -> None:
        save_settings(self.settings)
        self._refresh_menu()

    def _clear_recording_ui(self) -> None:
        try:
            self._overlay.hide()
        except Exception:
            logger.exception("overlay hide")
        self._set_icon_color()

    def _toggle_active(self, _icon=None, _item=None) -> None:
        with self._state_lock:
            self.active = not self.active
            if not self.active and self.recording:
                self.recording = False
        if not self.active:
            self._cancel_record_limit()
            try:
                self.recorder.stop()
            except Exception:
                logger.exception("stop recorder on pause")
            self._clear_recording_ui()
        self._refresh_menu()

    def _set_hotkey(self, hotkey_id: str) -> None:
        spec = spec_from_preset(hotkey_id)
        self.settings["hotkey"] = hotkey_id
        self.settings["hotkey_spec"] = spec
        self._hook.set_hotkey(spec)
        self._persist()
        logger.info("hotkey set to %s", format_hotkey(spec))

    def _set_mode(self, mode: str) -> None:
        self.settings["hotkey_mode"] = mode
        self._hook.set_hold_mode(mode == "hold")
        self._persist()

    def _set_model(self, model_size: str) -> None:
        spec = get_model(model_size)
        label = spec.get("label") or model_size
        if not is_model_cached(model_size):
            free = disk_free()
            needed = spec.get("size_bytes", 1_000_000_000)
            if free < needed:
                free_gb = free / (1024 ** 3)
                self._notify(
                    f"Недостаточно места ({free_gb:.1f} ГБ свободно) для {label}",
                    "Модель",
                )
                return

        self.settings["model"] = model_size
        save_settings(self.settings)

        def load():
            self._notify("Загрузка модели " + label, "FreeScribe-AI")
            self.transcriber.set_model_size(model_size)
            self._refresh_menu()
            if self.transcriber.error:
                self._notify(self.transcriber.error, "Ошибка модели")
            else:
                self._notify("Модель " + label + " готова", "FreeScribe-AI")

        threading.Thread(target=load, daemon=True).start()
        self._refresh_menu()

    def _open_settings(self, _icon=None, _item=None) -> None:
        from settings_ui import open_settings_window

        snapshot = dict(self.settings)

        def apply_saved(data: dict) -> None:
            self.settings.update(data)
            spec = data.get("hotkey_spec") or spec_from_preset(self.settings.get("hotkey") or "ctrl_f8")
            self.settings["hotkey_spec"] = spec
            self._hook.set_hotkey(spec)
            self._hook.set_hold_mode(self.settings["hotkey_mode"] == "hold")
            self._configure_recorder()
            save_settings(self.settings)
            if data.get("model") and data["model"] != self.transcriber.model_size:
                self._set_model(data["model"])
            else:
                self._refresh_menu()

        open_settings_window(snapshot, apply_saved, on_quit=self._quit)

    def _configure_recorder(self) -> None:
        self.recorder.configure(
            self.settings.get("mic_device") or "",
            self.settings.get("mic_gain") or 1.5,
            self.settings.get("mic_device_name") or "",
        )

    def _notify(self, message: str, title: str = APP_TITLE) -> None:
        text = (message or "").strip() or title
        logger.info("notify: %s | %s", title, text[:160])
        if not self.settings.get("show_toasts", True):
            return

        def apply() -> None:
            icon = getattr(self, "_icon", None)
            if icon is None:
                return
            try:
                icon.notify(text[:240], title)
            except Exception:
                logger.exception("tray notify")

        self._on_tray_thread(apply)

    def _record_beep(self, kind: str) -> None:
        mode = self.settings.get("record_beep_mode") or "both"
        if mode == "start" and kind != "start":
            return
        if mode == "stop" and kind != "stop":
            return
        if mode not in ("start", "stop", "both"):
            return

        def play() -> None:
            try:
                import sys

                if sys.platform == "win32":
                    import winsound

                    # Beep() часто ломается в RDP («Failed to beep») — тогда системный звук.
                    try:
                        if kind == "start":
                            winsound.Beep(980, 70)
                        else:
                            winsound.Beep(620, 90)
                        return
                    except RuntimeError:
                        alias = "SystemAsterisk" if kind == "start" else "SystemExclamation"
                        winsound.PlaySound(alias, winsound.SND_ALIAS | winsound.SND_ASYNC)
                else:
                    print("\a", end="", flush=True)
            except Exception:
                logger.debug("record beep unavailable", exc_info=True)

        threading.Thread(target=play, daemon=True).start()

    def _toggle_recording(self, _icon=None, _item=None) -> None:
        with self._state_lock:
            recording = self.recording
        if recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _on_hotkey_press(self) -> None:
        if not self.active:
            return
        if self.settings["hotkey_mode"] == "hold":
            self._start_recording()
        else:
            self._toggle_recording()

    def _on_hotkey_release(self) -> None:
        if not self.active:
            return
        if self.settings["hotkey_mode"] == "hold":
            self._stop_recording()

    def _start_recording(self) -> None:
        with self._state_lock:
            if not self.active or self.recording:
                return
            self.recording = True
        logger.info("recording start")
        self._paste_hwnd, self._paste_focus = capture_target()
        try:
            self._overlay.show()
        except Exception:
            logger.exception("overlay show")
        self._set_icon_color()
        self._record_beep("start")
        self._arm_record_limit()
        try:
            self._configure_recorder()
            self.recorder.start()
            warn = mic_rdp_warning(list_capture_devices())
            if warn and not self._mic_rdp_warned:
                self._mic_rdp_warned = True
                self._notify(warn, "Микрофон RDP")
        except Exception as exc:
            logger.exception("microphone")
            with self._state_lock:
                self.recording = False
            self._cancel_record_limit()
            self._clear_recording_ui()
            self._refresh_menu()
            self._notify(str(exc), "Микрофон")

    def _arm_record_limit(self) -> None:
        self._cancel_record_limit()
        limit = int(self.settings.get("max_record_sec") or 300)
        timer = threading.Timer(limit, self._on_record_limit)
        timer.daemon = True
        self._record_timer = timer
        timer.start()
        logger.info("record limit %ss", limit)

    def _cancel_record_limit(self) -> None:
        timer = self._record_timer
        self._record_timer = None
        if timer is not None:
            timer.cancel()

    def _on_record_limit(self) -> None:
        with self._state_lock:
            if not self.recording:
                return
        limit = int(self.settings.get("max_record_sec") or 300)
        minutes = max(1, round(limit / 60))
        logger.info("record auto-stop after %ss", limit)
        self._notify(
            f"Запись остановлена: лимит {minutes} мин. Нажмите клавишу, если это было зря.",
            "FreeScribe-AI",
        )
        self._stop_recording()

    def _stop_recording(self) -> None:
        self._cancel_record_limit()
        with self._state_lock:
            if not self.recording:
                return
            self.recording = False
        logger.info("recording stop")
        try:
            self._overlay.hide()
        except Exception:
            logger.exception("overlay hide")
        self._set_icon_color()
        self._record_beep("stop")
        audio = self.recorder.stop()
        if audio is None or len(audio) == 0:
            logger.info("recording empty")
            self._notify(
                "Микрофон не записал звук. Настройки → Микрофон → «Слушать» и проверьте полоску.",
                "Запись",
            )
            return
        self._notify("Распознаю речь…", "FreeScribe-AI")
        self.executor.submit(self._transcribe_and_inject, audio, self._paste_hwnd, self._paste_focus)

    def _inject_on_ui_thread(self, text: str, hwnd: int, focus: int) -> None:
        """Вставка с потока иконки трея — иначе OpenClipboard/SendInput часто ломаются в RDP."""
        for _ in range(20):
            if getattr(self._icon, "_hwnd", None):
                break
            time.sleep(0.02)
        done = threading.Event()
        err: list[BaseException] = []

        def work() -> None:
            try:
                owner = int(getattr(self._icon, "_hwnd", 0) or 0)
                inject_text(text, hwnd, focus, clipboard_owner=owner)
            except BaseException as exc:
                err.append(exc)
            finally:
                done.set()

        self._on_tray_thread(work)
        if not done.wait(timeout=30.0):
            raise RuntimeError("Вставка текста: таймаут (трей не отвечает)")
        if err:
            raise err[0]

    def _transcribe_and_inject(self, audio, hwnd: int = 0, focus: int = 0) -> None:
        try:
            pipeline_t0 = time.perf_counter()
            peak = _audio_peak(audio)
            if peak < _MIN_AUDIO_PEAK:
                logger.info("recording too quiet peak=%.5f", peak)
                self._notify(
                    "Микрофон почти не слышит речь (тишина в записи). "
                    "Настройки → Микрофон: выберите «Удалённое аудио» / нужное устройство, "
                    "нажмите «Слушать» и проверьте полоску уровня.",
                    "Запись",
                )
                return

            groq_key = (self.settings.get("groq_api_key") or "").strip()
            text = ""
            if groq_key:
                try:
                    from transcriber import transcribe_groq

                    text = transcribe_groq(
                        audio,
                        SAMPLE_RATE,
                        groq_key,
                        self.settings.get("groq_proxy") or "",
                    )
                    if _is_junk_transcript(text):
                        logger.info("groq junk, fallback local: %s", (text or "")[:80])
                        text = ""
                except Exception as exc:
                    logger.exception("groq failed, fallback local")
                    self._notify(f"{exc} Распознаю локально…", "Groq")
            if not text:
                if not self.transcriber.ready:
                    self._notify("Модель ещё загружается, подождите", "FreeScribe-AI")
                    if not self.transcriber.wait_until_ready(120.0):
                        if self.transcriber.error:
                            raise RuntimeError(self.transcriber.error)
                        raise RuntimeError("Модель не успела загрузиться")
                t_tr = time.perf_counter()
                text = self.transcriber.transcribe(audio, SAMPLE_RATE)
                logger.info("transcribe phase %.2fs", time.perf_counter() - t_tr)
            if text and _is_junk_transcript(text):
                logger.info("drop junk transcript: %s", text[:80])
                text = ""
            if text:
                t_inj = time.perf_counter()
                self._inject_on_ui_thread(text, hwnd, focus)
                logger.info(
                    "injected: %s (inject %.2fs, pipeline %.2fs)",
                    text[:80],
                    time.perf_counter() - t_inj,
                    time.perf_counter() - pipeline_t0,
                )
                self._notify(text, "Распознано")
            else:
                self._notify("Не удалось разобрать речь", "FreeScribe-AI")
        except Exception as exc:
            logger.exception("transcribe")
            self._notify(str(exc), "Ошибка распознавания")

    def _quit(self, _icon=None, _item=None) -> None:
        self._user_quit = True
        self._cancel_record_limit()
        try:
            from compat import mark_clean_exit

            mark_clean_exit()
        except Exception:
            logger.exception("clean exit flag")
        try:
            self._hook.stop()
        except Exception:
            logger.exception("hook stop")
        self.recorder.close()
        self.executor.shutdown(wait=False)
        try:
            self._overlay.hide()
            self._overlay.close()
        except Exception:
            logger.exception("overlay close")
        try:
            self._icon.stop()
        except Exception:
            logger.exception("icon stop")

    def _load_startup_model(self) -> None:
        self.transcriber.load_model(local_only=True)
        if self.transcriber.ready:
            self._refresh_menu()
            self._notify(f"Готово. Модель {self.transcriber.model_size}", "FreeScribe-AI")
            if self._wanted_model != self.transcriber.model_size and disk_free() > 2_000_000_000:
                self._notify(f"Скачиваю {self._wanted_model}…", "FreeScribe-AI")
                self._set_model(self._wanted_model)
            return
        fallback = best_cached_model("small")
        if is_model_cached(fallback) and fallback != self.transcriber.model_size:
            logger.warning("startup model failed, fallback %s", fallback)
            self.transcriber.model_size = fallback
            self.settings["model"] = fallback
            save_settings(self.settings)
            self.transcriber.load_model(local_only=True)
            self._refresh_menu()
            if self.transcriber.ready:
                self._notify(f"Готово. Модель {self.transcriber.model_size}", "FreeScribe-AI")
                return
        target = self._wanted_model
        spec = get_model(target)
        if disk_free() < spec.get("size_bytes", 800_000_000):
            target = "small"
            spec = get_model(target)
        self._notify(
            f"Первый запуск: скачиваю {spec['label']} ({spec['size_label']}). Не закрывайте программу.",
            "FreeScribe-AI",
        )
        self.transcriber.model_size = target
        self.settings["model"] = target
        save_settings(self.settings)
        self.transcriber.load_model(local_only=False)
        self._refresh_menu()
        if self.transcriber.ready:
            self._notify(f"Готово. Модель {spec['label']}", "FreeScribe-AI")
        else:
            err = self.transcriber.error or "Модель не загрузилась. Откройте Настройки → Модели и нажмите «Скачать»."
            self._notify(err, "Ошибка модели")
            try:
                from compat import show_message

                show_message(err, error=True)
            except Exception:
                logger.exception("model error dialog")

    def run(self) -> None:
        first = True
        while not self._user_quit:
            logger.info("starting tray")
            icon = self._icon

            def setup(icon_obj, load_model=first):
                icon_obj.visible = True
                icon_obj._message_handlers[_WM_APP] = self._drain_ui
                try:
                    from compat import startup_splash_end

                    startup_splash_end()
                except Exception:
                    logger.exception("startup splash end")
                try:
                    self._hook.attach(icon_obj)
                except Exception as exc:
                    logger.exception("hook start")
                    self._notify(
                        f"Хоткей недоступен: {exc}. Запись из меню трея.",
                        "FreeScribe-AI",
                    )
                if load_model:
                    if self._fallback_notice:
                        self._notify(self._fallback_notice, "FreeScribe-AI")

                    def _startup_background() -> None:
                        try:
                            from socks_proxy import ensure_local_socks

                            socks = ensure_local_socks()
                            if socks and not (self.settings.get("groq_proxy") or "").strip():
                                self.settings["groq_proxy"] = socks
                                save_settings(self.settings)
                        except Exception:
                            logger.exception("socks autostart")
                        groq_key = (self.settings.get("groq_api_key") or "").strip()
                        if groq_key:
                            try:
                                from transcriber import warmup_groq

                                warmup_groq(groq_key, self.settings.get("groq_proxy") or "")
                            except Exception:
                                logger.exception("groq warmup")
                        self._load_startup_model()

                    threading.Thread(target=_startup_background, daemon=True).start()

                def keep_visible() -> None:
                    while not self._user_quit:
                        time.sleep(25)
                        try:
                            def restore() -> None:
                                if not icon_obj.visible:
                                    return
                                # NIM_ADD после RDP/explorer: MODIFY не возвращает иконку.
                                show = getattr(icon_obj, "_show", None)
                                if show:
                                    show()
                                else:
                                    icon_obj._update_icon()

                            self._on_tray_thread(restore)
                        except Exception:
                            logger.exception("tray keep-alive")

                threading.Thread(target=keep_visible, daemon=True, name="tray-keep").start()

            try:
                icon.run(setup=setup)
            except Exception:
                logger.exception("tray loop crash")
            logger.warning("tray loop ended user_quit=%s", self._user_quit)
            if self._user_quit:
                break
            if getattr(sys, "frozen", False):
                logger.error("tray died unexpectedly — exit (exe, no auto-restart)")
                break
            try:
                self._hook.stop()
            except Exception:
                logger.exception("hook stop after tray")
            try:
                self._overlay.close()
            except Exception:
                logger.exception("overlay close before tray restart")
            time.sleep(1)
            first = False
            self._icon = self._make_icon()
            self._overlay = RecordOverlay()
