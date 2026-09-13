"""Платформа: Windows и macOS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
APP_NAME = "FreeScribe-AI"
APP_TITLE = "FreeScribe-AI"
_LEGACY_APP_NAMES = ("F1WhisperTyping",)


def user_data_dir() -> Path:
    if os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
        root = base / APP_NAME
        if not root.is_dir():
            for legacy in _LEGACY_APP_NAMES:
                old = base / legacy
                if old.is_dir() and (old / "settings.json").is_file():
                    try:
                        root.mkdir(parents=True, exist_ok=True)
                        for name in ("settings.json", "app.log"):
                            src = old / name
                            dst = root / name
                            if src.is_file() and not dst.is_file():
                                dst.write_bytes(src.read_bytes())
                    except OSError:
                        pass
                    break
    elif IS_MAC:
        root = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        root = Path.home() / ".config" / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def show_message(text: str, error: bool = False) -> None:
    title = APP_TITLE
    if IS_WIN:
        import ctypes

        flags = 0x00000010 if error else 0x00000040
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
        return
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        if error:
            messagebox.showerror(title, text)
        else:
            messagebox.showinfo(title, text)
        root.destroy()
    except Exception:
        print(f"{title}: {text}", file=sys.stderr)


def ensure_single_instance() -> bool:
    if IS_WIN:
        import ctypes

        global _mutex_handle
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        _mutex_handle = kernel32.CreateMutexW(None, True, "Local\\FreeScribe-AI")
        return kernel32.GetLastError() != 183
    lock_path = user_data_dir() / "instance.lock"
    handle = open(lock_path, "a+b")
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    except ImportError:
        handle.close()
        return True
    _posix_lock_handle = handle  # noqa: F841 — keep lock for process lifetime
    globals()["_posix_lock_handle"] = handle
    return True


_mutex_handle = None


def missing_module_hint(missing: str) -> str:
    if IS_WIN:
        return (
            f"Не найден пакет Python: {missing}\n\n"
            "Запустите start.bat или в консоли:\npy -3.13 main.py"
        )
    return (
        f"Не найден пакет Python: {missing}\n\n"
        "В Терминале, в папке проекта:\n"
        "python3 -m pip install -r requirements.txt\n"
        "python3 main.py\n\n"
        "На Mac разрешите микрофон и Универсальный доступ (Accessibility)."
    )
