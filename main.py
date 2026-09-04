"""
F1 Whisper Typing — офлайн голосовой набор текста для Windows.

Сборка: build.bat  →  dist\\F1WhisperTyping.exe
"""

import ctypes
import logging
import os
import sys
from multiprocessing import freeze_support
from pathlib import Path

MUTEX_NAME = "Local\\F1WhisperTyping"
_mutex_handle = None


def _setup_logging() -> None:
    format_str = "%(asctime)s %(levelname)s %(message)s"
    handlers = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        folder = Path(appdata) / "F1WhisperTyping"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(folder / "app.log", encoding="utf-8"))
        except OSError:
            pass
    if not getattr(sys, "frozen", False):
        try:
            handlers.append(
                logging.FileHandler(
                    Path(__file__).resolve().parent / "app.log",
                    encoding="utf-8",
                )
            )
        except OSError:
            pass
    logging.basicConfig(
        level=logging.INFO,
        format=format_str,
        handlers=handlers or None,
    )


def _message(text: str, error: bool = False) -> None:
    flags = 0x00000010 if error else 0x00000040
    ctypes.windll.user32.MessageBoxW(None, text, "F1 Whisper Typing", flags)


def _ensure_single_instance() -> bool:
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    _mutex_handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    return kernel32.GetLastError() != 183


def main() -> None:
    _setup_logging()
    log = logging.getLogger("whisper_typing")
    log.info(
        "start frozen=%s cwd=%s appdata=%s",
        getattr(sys, "frozen", False),
        os.getcwd(),
        os.environ.get("APPDATA"),
    )

    def _excepthook(exc_type, exc, tb):
        log.error("uncaught exception", exc_info=(exc_type, exc, tb))
        _message(str(exc), error=True)

    sys.excepthook = _excepthook

    if not _ensure_single_instance():
        log.info("already running")
        _message("Программа уже запущена.\nИконка в трее — возле часов, иногда в скрытых значках.")
        return

    log.info("importing app")
    from tray_app import WhisperTrayApp

    log.info("imports done")
    try:
        app = WhisperTrayApp()
        log.info("tray app created")
        app.run()
    except Exception as exc:
        log.exception("fatal")
        _message(f"Не удалось запустить:\n{exc}", error=True)
        raise


if __name__ == "__main__":
    freeze_support()
    main()
