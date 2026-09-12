"""Глобальные горячие клавиши: Windows-хук или pynput на macOS."""

from __future__ import annotations

from compat import IS_WIN

if IS_WIN:
    from hotkey_win import HotkeyManager
else:
    from hotkey_posix import HotkeyManager

__all__ = ["HotkeyManager"]
