"""Горячие клавиши через pynput (macOS / Linux)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from pynput import keyboard

from settings import format_hotkey, sanitize_hotkey_spec, spec_from_preset

logger = logging.getLogger("whisper_typing")

_PRESET_KEYS = {
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
    "ctrl_space": keyboard.Key.space,
    "ctrl_f8": keyboard.Key.f8,
    "pause": getattr(keyboard.Key, "pause", keyboard.Key.f8),
    "scroll_lock": getattr(keyboard.Key, "scroll_lock", keyboard.Key.f8),
    "insert": getattr(keyboard.Key, "insert", keyboard.Key.f8),
    "rctrl": keyboard.Key.ctrl_r,
}

_CTRL = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
_ALT = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}
_SHIFT = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}
_CMD = {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r}


def _key_name(key) -> str:
    name = getattr(key, "name", None)
    if name:
        return str(name).lower()
    char = getattr(key, "char", None)
    if char:
        return str(char).lower()
    return str(key).replace("'", "").lower()


class HotkeyManager:
    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        hotkey_id: str = "ctrl_f8",
        hold_mode: bool = False,
        on_registered: Callable[[str], None] | None = None,
        spec: dict | None = None,
    ):
        self._on_press = on_press
        self._on_release = on_release
        self._on_registered = on_registered
        self._spec = sanitize_hotkey_spec(spec or spec_from_preset(hotkey_id))
        self._hotkey_id = self._spec.get("id") or "custom"
        self._hold_mode = hold_mode
        self._key_held = False
        self._last_fire = 0.0
        self._mods = {"ctrl": False, "alt": False, "shift": False, "win": False}
        self._listener: keyboard.Listener | None = None

    def attach(self, icon=None) -> None:
        self.stop()
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)
        self._listener.start()
        logger.info("pynput hotkey ok spec=%s", format_hotkey(self._spec))
        if self._on_registered:
            try:
                self._on_registered(self._hotkey_id)
            except Exception:
                logger.exception("on_registered")

    def set_hotkey(self, hotkey_id: str | dict, spec: dict | None = None) -> None:
        if isinstance(hotkey_id, dict):
            self._spec = sanitize_hotkey_spec(hotkey_id)
        elif spec is not None:
            self._spec = sanitize_hotkey_spec(spec)
        else:
            self._spec = spec_from_preset(hotkey_id)
        self._hotkey_id = self._spec.get("id") or "custom"
        self._key_held = False
        logger.info("hotkey now %s", format_hotkey(self._spec))

    def set_hold_mode(self, hold: bool) -> None:
        self._hold_mode = hold

    def start(self, icon=None) -> None:
        self.attach(icon)

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener:
            try:
                listener.stop()
            except Exception:
                logger.exception("pynput stop")
        self._key_held = False

    def _update_mod(self, key, down: bool) -> None:
        if key in _CTRL:
            self._mods["ctrl"] = down
        elif key in _ALT:
            self._mods["alt"] = down
        elif key in _SHIFT:
            self._mods["shift"] = down
        elif key in _CMD:
            self._mods["win"] = down

    def _is_trigger(self, key) -> bool:
        hid = self._spec.get("id") or ""
        want = _PRESET_KEYS.get(hid)
        if want is not None:
            return key == want
        keysym = str(self._spec.get("keysym") or "").lower()
        if keysym:
            return _key_name(key) == keysym or _key_name(key) == keysym.replace("_l", "").replace("_r", "")
        return False

    def _combo(self, key) -> bool:
        if not self._is_trigger(key):
            return False
        hid = self._spec.get("id") or ""
        if hid == "rctrl":
            return True
        if hid in _PRESET_KEYS and hid.startswith("ctrl_"):
            return self._mods["ctrl"]
        return (
            self._mods["ctrl"] == bool(self._spec.get("ctrl"))
            and self._mods["alt"] == bool(self._spec.get("alt"))
            and self._mods["shift"] == bool(self._spec.get("shift"))
            and self._mods["win"] == bool(self._spec.get("win"))
        )

    def _press(self, key) -> None:
        self._update_mod(key, True)
        if not self._combo(key):
            return
        now = time.monotonic()
        if self._hold_mode:
            if not self._key_held:
                self._key_held = True
                logger.info("hotkey down spec=%s", format_hotkey(self._spec))
                threading.Thread(target=self._on_press, daemon=True).start()
            return
        if (now - self._last_fire) < 0.28:
            return
        self._last_fire = now
        self._key_held = True
        logger.info("hotkey down spec=%s", format_hotkey(self._spec))
        threading.Thread(target=self._on_press, daemon=True).start()

    def _release(self, key) -> None:
        was = self._key_held and self._is_trigger(key)
        self._update_mod(key, False)
        if not was:
            return
        self._key_held = False
        logger.info("hotkey up spec=%s", format_hotkey(self._spec))
        if self._hold_mode:
            threading.Thread(target=self._on_release, daemon=True).start()
