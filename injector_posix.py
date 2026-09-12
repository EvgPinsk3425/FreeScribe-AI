"""Вставка текста на macOS: буфер + Cmd+V."""

from __future__ import annotations

import logging
import time

import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger("whisper_typing")
_keyboard = Controller()


def capture_target() -> tuple[int, int]:
    return 0, 0


def inject_text(text: str, hwnd: int = 0, focus: int = 0) -> None:
    if not text:
        return
    previous = ""
    try:
        previous = pyperclip.paste()
    except Exception:
        logger.exception("clipboard read")
    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        _keyboard.press(Key.cmd)
        _keyboard.press("v")
        _keyboard.release("v")
        _keyboard.release(Key.cmd)
        time.sleep(0.15)
        logger.info("pasted chars=%s", len(text))
    finally:
        try:
            if previous:
                pyperclip.copy(previous)
        except Exception:
            logger.exception("clipboard restore")
