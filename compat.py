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


_WIN_EXE_NAMES = ("FreeScribe-AI.exe", "F1WhisperTyping.exe", "WhisperTyping.exe")

_splash_root = None
_splash_lock = None


def _reap_stale_windows_processes() -> None:
    """Завершить зависшие копии exe после краша (mutex уже снят)."""
    if not IS_WIN:
        return
    import subprocess

    me = os.getpid()
    for image in _WIN_EXE_NAMES:
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                creationflags=0x08000000,
                text=True,
                errors="replace",
            )
        except (OSError, subprocess.SubprocessError):
            continue
        for line in out.strip().splitlines():
            if image.lower() not in line.lower():
                continue
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[1])
            except ValueError:
                continue
            if pid == me:
                continue
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                creationflags=0x08000000,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def ensure_single_instance() -> bool:
    if IS_WIN:
        import ctypes

        global _mutex_handle
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        _mutex_handle = kernel32.CreateMutexW(None, True, "Local\\FreeScribe-AI")
        if kernel32.GetLastError() == 183:
            return False
        _reap_stale_windows_processes()
        return True


def startup_splash_begin() -> None:
    """Окно «Запуск…» пока onefile распаковывается и грузятся DLL (без консоли)."""
    global _splash_root, _splash_lock
    if not IS_WIN or not getattr(sys, "frozen", False):
        return
    if _splash_root is not None:
        return
    import threading

    _splash_lock = threading.Lock()
    log_path = user_data_dir() / "app.log"

    def _thread() -> None:
        global _splash_root
        try:
            import tkinter as tk

            root = tk.Tk()
            root.title(APP_TITLE)
            root.resizable(False, False)
            root.attributes("-topmost", True)
            tk.Label(
                root,
                text=(
                    f"{APP_TITLE} запускается…\n\n"
                    "Иконка появится у часов (▲ в трее).\n"
                    "Первый запуск после скачивания может занять 1–2 минуты.\n\n"
                    f"Если зависло — смотрите:\n{log_path}"
                ),
                justify="left",
                padx=16,
                pady=12,
            ).pack()
            root.update_idletasks()
            root.geometry(f"+{max(40, root.winfo_screenwidth() // 2 - 220)}+80")
            with _splash_lock:
                _splash_root = root
            root.mainloop()
        except Exception:
            _splash_root = None

    threading.Thread(target=_thread, name="startup-splash", daemon=True).start()


def startup_splash_end() -> None:
    global _splash_root
    root = _splash_root
    if root is None:
        return

    def _close() -> None:
        global _splash_root
        try:
            root.destroy()
        except Exception:
            pass
        _splash_root = None

    try:
        root.after(0, _close)
    except Exception:
        _close()
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


def clean_exit_path(pid: int | None = None) -> Path:
    suffix = str(pid if pid is not None else os.getpid())
    return user_data_dir() / f"clean_exit.{suffix}.flag"


def mark_clean_exit() -> None:
    try:
        clean_exit_path().write_text("1", encoding="utf-8")
    except OSError:
        pass


def app_launch_command() -> str:
    """Команда для автозапуска (ярлык в Run / LaunchAgents)."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    root = Path(__file__).resolve().parent
    if IS_WIN:
        bat = root / "start.bat"
        if bat.is_file():
            return f'"{bat}"'
        return f'py -3.13 "{root / "main.py"}"'
    return f'"{sys.executable}" "{root / "main.py"}"'


def is_run_at_startup() -> bool:
    if IS_WIN:
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            ) as key:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(str(value or "").strip())
        except OSError:
            return False
    if IS_MAC:
        return _mac_launch_agent_path().is_file()
    return False


def set_run_at_startup(enabled: bool) -> None:
    if IS_WIN:
        import winreg

        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except OSError:
                    pass
        return
    if IS_MAC:
        agent = _mac_launch_agent_path()
        if enabled:
            exe = sys.executable if not getattr(sys, "frozen", False) else sys.executable
            script = Path(__file__).resolve().parent / "main.py"
            program = [exe, str(script)] if not getattr(sys, "frozen", False) else [str(Path(sys.executable).resolve())]
            plist = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict>\n'
                f"<key>Label</key><string>by.freescribe.ai</string>\n"
                "<key>ProgramArguments</key><array>\n"
                + "".join(f"<string>{p}</string>\n" for p in program)
                + "</array>\n"
                "<key>RunAtLoad</key><true/>\n"
                "</dict></plist>\n"
            )
            agent.parent.mkdir(parents=True, exist_ok=True)
            agent.write_text(plist, encoding="utf-8")
        elif agent.is_file():
            agent.unlink()


def _mac_launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "by.freescribe.ai.plist"


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
