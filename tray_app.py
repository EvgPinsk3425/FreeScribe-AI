"""Системный трей и управление приложением."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pystray
from PIL import Image, ImageDraw

from audio_recorder import AudioRecorder, SAMPLE_RATE
from hotkey import HotkeyManager
from injector import capture_target, inject_text
from settings import (
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
from transcriber import Transcriber

COLOR_IDLE = (70, 130, 220, 255)
COLOR_RECORD = (200, 60, 60, 255)
COLOR_PAUSE = (140, 140, 140, 255)
logger = logging.getLogger("whisper_typing")


def _create_icon(color=COLOR_IDLE, size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    body = (size * 0.35, size * 0.2, size * 0.65, size * 0.62)
    draw.rounded_rectangle(body, radius=size // 8, fill=color)

    arc_box = (size * 0.28, size * 0.55, size * 0.72, size * 0.88)
    draw.arc(arc_box, start=0, end=180, fill=color, width=max(2, size // 16))

    stem = (size * 0.46, size * 0.82, size * 0.54, size * 0.94)
    draw.rectangle(stem, fill=color)

    base = (size * 0.32, size * 0.92, size * 0.68, size * 0.98)
    draw.rounded_rectangle(base, radius=2, fill=color)

    return image


class WhisperTrayApp:
    def __init__(self):
        self.settings = load_settings()
        from socks_proxy import ensure_local_socks

        socks = ensure_local_socks()
        if socks and not (self.settings.get("groq_proxy") or "").strip():
            self.settings["groq_proxy"] = socks
        save_settings(self.settings)
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
        self.recorder.configure(
            self.settings.get("mic_device") or "",
            self.settings.get("mic_gain") or 1.5,
        )
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
        self._icon = pystray.Icon(
            "f1_whisper_typing",
            _create_icon(),
            "F1 Whisper Typing",
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
            return f"Whisper Typing — идёт запись ({hint})"
        if not self.active:
            return "Whisper Typing — пауза"
        return f"Whisper Typing — {hint}"

    def _status_label(self, _item=None) -> str:
        if self.recording:
            return "Статус: Запись..."
        if getattr(self.transcriber, "error", None):
            return "Статус: Ошибка модели"
        if not getattr(self.transcriber, "ready", False):
            return "Статус: Загрузка модели..."
        return "Статус: Работает" if self.active else "Статус: Пауза"

    def _model_label(self, model_id: str) -> str:
        spec = get_model(model_id)
        downloaded = "скачана" if model_id in cached_models() else "скачается"
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
        if self.recording:
            color = COLOR_RECORD
        elif self.active:
            color = COLOR_IDLE
        else:
            color = COLOR_PAUSE
        self._icon.icon = _create_icon(color)

    def _refresh_menu(self) -> None:
        self._icon.menu = self._build_menu()
        self._set_icon_color()

    def _persist(self) -> None:
        save_settings(self.settings)
        self._refresh_menu()

    def _toggle_active(self, _icon=None, _item=None) -> None:
        with self._state_lock:
            self.active = not self.active
            if not self.active and self.recording:
                self.recording = False
        if not self.active:
            try:
                self.recorder.stop()
            except Exception:
                logger.exception("stop recorder on pause")
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
            self._notify("Загрузка модели " + label, "F1 Whisper Typing")
            self.transcriber.set_model_size(model_size)
            self._refresh_menu()
            if self.transcriber.error:
                self._notify(self.transcriber.error, "Ошибка модели")
            else:
                self._notify("Модель " + label + " готова", "F1 Whisper Typing")

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
            self.recorder.configure(
                self.settings.get("mic_device") or "",
                self.settings.get("mic_gain") or 1.5,
            )
            save_settings(self.settings)
            if data.get("model") and data["model"] != self.transcriber.model_size:
                self._set_model(data["model"])
            else:
                self._refresh_menu()

        open_settings_window(snapshot, apply_saved)

    def _notify(self, message: str, title: str = "Whisper Typing") -> None:
        text = (message or "").strip() or title
        logger.info("notify: %s | %s", title, text[:160])
        icon = getattr(self, "_icon", None)
        if icon is None:
            return
        try:
            icon.notify(text[:240], title)
        except Exception:
            logger.exception("tray notify")

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
        self._set_icon_color()
        try:
            self.recorder.configure(
                self.settings.get("mic_device") or "",
                self.settings.get("mic_gain") or 1.5,
            )
            self.recorder.start()
        except Exception as exc:
            logger.exception("microphone")
            with self._state_lock:
                self.recording = False
            self._refresh_menu()
            self._notify(str(exc), "Микрофон")

    def _stop_recording(self) -> None:
        with self._state_lock:
            if not self.recording:
                return
            self.recording = False
        logger.info("recording stop")
        self._set_icon_color()
        audio = self.recorder.stop()
        if audio is None or len(audio) == 0:
            logger.info("recording empty")
            self._notify(
                "Микрофон не записал звук. Настройки → Микрофон → «Слушать» и проверьте полоску.",
                "Запись",
            )
            return
        self._notify("Распознаю речь…", "F1 Whisper Typing")
        self.executor.submit(self._transcribe_and_inject, audio, self._paste_hwnd, self._paste_focus)

    def _transcribe_and_inject(self, audio, hwnd: int = 0, focus: int = 0) -> None:
        try:
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
                except Exception as exc:
                    logger.exception("groq failed, fallback local")
                    self._notify(f"{exc} Распознаю локально…", "Groq")
            if not text:
                if not self.transcriber.ready:
                    self._notify("Модель ещё загружается, подождите", "Whisper Typing")
                    for _ in range(120):
                        if self.transcriber.ready or self.transcriber.error:
                            break
                        time.sleep(1)
                    if self.transcriber.error:
                        raise RuntimeError(self.transcriber.error)
                    if not self.transcriber.ready:
                        raise RuntimeError("Модель не успела загрузиться")
                text = self.transcriber.transcribe(audio, SAMPLE_RATE)
            junk = (
                "продолжение следует",
                "субтитры создавал",
                "dimatorzok",
                "thanks for watching",
                "subscribe to",
            )
            if text and any(token in text.lower() for token in junk):
                logger.info("drop junk transcript: %s", text[:80])
                text = ""
            if text:
                inject_text(text, hwnd, focus)
                logger.info("injected: %s", text[:80])
                self._notify(text, "Распознано")
            else:
                self._notify("Не удалось разобрать речь", "Whisper Typing")
        except Exception as exc:
            logger.exception("transcribe")
            self._notify(str(exc), "Ошибка распознавания")

    def _quit(self, _icon=None, _item=None) -> None:
        try:
            self._hook.stop()
        except Exception:
            logger.exception("hook stop")
        self.recorder.close()
        self.executor.shutdown(wait=False)
        self._icon.stop()

    def _load_startup_model(self) -> None:
        self.transcriber.load_model(local_only=True)
        if self.transcriber.ready:
            self._refresh_menu()
            self._notify(f"Готово. Модель {self.transcriber.model_size}", "F1 Whisper Typing")
            if self._wanted_model != self.transcriber.model_size and disk_free() > 2_000_000_000:
                self._notify(f"Скачиваю {self._wanted_model}…", "F1 Whisper Typing")
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
                self._notify(f"Готово. Модель {self.transcriber.model_size}", "F1 Whisper Typing")
                return
        target = self._wanted_model
        spec = get_model(target)
        if disk_free() < spec.get("size_bytes", 800_000_000):
            target = "small"
            spec = get_model(target)
        self._notify(
            f"Первый запуск: скачиваю {spec['label']} ({spec['size_label']}). Не закрывайте программу.",
            "F1 Whisper Typing",
        )
        self.transcriber.model_size = target
        self.settings["model"] = target
        save_settings(self.settings)
        self.transcriber.load_model(local_only=False)
        self._refresh_menu()
        if self.transcriber.ready:
            self._notify(f"Готово. Модель {spec['label']}", "F1 Whisper Typing")
        else:
            err = self.transcriber.error or "Модель не загрузилась. Откройте Настройки → Модели и нажмите «Скачать»."
            self._notify(err, "Ошибка модели")
            try:
                from compat import show_message

                show_message(err, error=True)
            except Exception:
                logger.exception("model error dialog")

    def run(self) -> None:
        logger.info("starting tray")

        def setup(icon):
            icon.visible = True
            try:
                self._hook.attach(icon)
            except Exception as exc:
                logger.exception("hook start")
                self._notify(
                    f"Хоткей недоступен: {exc}. Запись из меню трея.",
                    "F1 Whisper Typing",
                )
            if self._fallback_notice:
                self._notify(self._fallback_notice, "F1 Whisper Typing")
            threading.Thread(target=self._load_startup_model, daemon=True).start()

        self._icon.run(setup=setup)
