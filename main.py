"""
F1 Whisper Typing — офлайн голосовой набор для Windows и macOS.

Windows: start.bat или F1WhisperTyping.exe
macOS:   ./start.command  или  python3 main.py
"""

import logging
import os
import sys
from multiprocessing import freeze_support
from pathlib import Path

from compat import ensure_single_instance, missing_module_hint, show_message, user_data_dir


def _setup_logging() -> None:
    format_str = "%(asctime)s %(levelname)s %(message)s"
    handlers = []
    try:
        folder = user_data_dir()
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


def main() -> None:
    _setup_logging()
    log = logging.getLogger("whisper_typing")
    log.info(
        "start frozen=%s cwd=%s platform=%s",
        getattr(sys, "frozen", False),
        os.getcwd(),
        sys.platform,
    )

    def _excepthook(exc_type, exc, tb):
        log.error("uncaught exception", exc_info=(exc_type, exc, tb))
        show_message(str(exc), error=True)

    sys.excepthook = _excepthook

    if not ensure_single_instance():
        log.info("already running")
        show_message("Программа уже запущена.\nИконка — в трее (Windows) или в строке меню (Mac).")
        return

    log.info("importing app")
    try:
        from tray_app import WhisperTrayApp
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        log.exception("missing module")
        show_message(missing_module_hint(str(missing)), error=True)
        return

    log.info("imports done")
    try:
        app = WhisperTrayApp()
        log.info("tray app created")
        app.run()
    except Exception as exc:
        log.exception("fatal")
        show_message(f"Не удалось запустить:\n{exc}", error=True)
        raise


if __name__ == "__main__":
    freeze_support()
    main()
