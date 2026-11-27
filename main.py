"""
FreeScribe-AI — офлайн голосовой набор для Windows и macOS.

Windows: start.bat или FreeScribe-AI.exe
macOS:   ./start.command  или python3 main.py
"""

import atexit
import faulthandler
import logging
import os
import sys
import threading


class _NullStream:
    """Подмена stdout/stderr в PyInstaller windowed — иначе tqdm/logging падают с None.write."""

    def write(self, _s: object = "") -> int:
        return 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise OSError("no fileno")


def _bootstrap_runtime() -> None:
    """Сборка без консоли: tqdm/huggingface не должны писать в None stdout."""
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TQDM_DISABLE", "1")
    if getattr(sys, "frozen", False):
        _sink = _NullStream()
        sys.stdout = sys.stderr = _sink
        sys.__stdout__ = sys.__stderr__ = _sink
    try:
        from huggingface_hub.utils.tqdm import disable_progress_bars

        disable_progress_bars()
    except Exception:
        pass
    try:
        import huggingface_hub
        import huggingface_hub._snapshot_download as _snapshot_mod
        from huggingface_hub.utils import tqdm as hf_tqdm

        _orig_snapshot = _snapshot_mod.snapshot_download

        def _snapshot_download(*args, **kwargs):
            kwargs.setdefault("tqdm_class", hf_tqdm)
            return _orig_snapshot(*args, **kwargs)

        _snapshot_mod.snapshot_download = _snapshot_download
        huggingface_hub.snapshot_download = _snapshot_download
    except Exception:
        pass


_bootstrap_runtime()
from multiprocessing import freeze_support
from pathlib import Path

from compat import (
    APP_TITLE,
    clean_exit_path,
    ensure_single_instance,
    mark_clean_exit,
    missing_module_hint,
    show_message,
    startup_splash_begin,
    user_data_dir,
)

_fault_file = None


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
    if not handlers:
        handlers = [logging.NullHandler()]
    logging.basicConfig(
        level=logging.INFO,
        format=format_str,
        handlers=handlers,
        force=True,
    )


def _enable_crash_dump(log: logging.Logger) -> None:
    global _fault_file
    try:
        _fault_file = open(user_data_dir() / "crash.log", "a", encoding="utf-8")
        faulthandler.enable(file=_fault_file, all_threads=True)
    except OSError:
        try:
            faulthandler.enable(file=open(os.devnull, "w", encoding="utf-8"), all_threads=True)
        except OSError:
            pass

    def _excepthook(exc_type, exc, tb):
        log.error("uncaught exception", exc_info=(exc_type, exc, tb))
        show_message(str(exc), error=True)

    sys.excepthook = _excepthook

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        log.error(
            "thread exception name=%s",
            getattr(args.thread, "name", None),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_hook
    atexit.register(lambda: log.info("process atexit"))


def _run_app() -> None:
    _setup_logging()
    log = logging.getLogger("whisper_typing")
    log.info(
        "start frozen=%s cwd=%s platform=%s supervised=%s",
        getattr(sys, "frozen", False),
        os.getcwd(),
        sys.platform,
        os.environ.get("FREESCRIBE_SUPERVISED", ""),
    )
    _enable_crash_dump(log)

    if not ensure_single_instance():
        log.info("already running")
        mark_clean_exit()
        show_message(
            f"{APP_TITLE} уже запущена.\n\n"
            "Иконка — в трее (стрелка ▲ возле часов) или в переполнении.\n\n"
            "Если иконки нет — в Диспетчере задач завершите\n"
            "FreeScribe-AI.exe или F1WhisperTyping.exe\n"
            f"и запустите снова.\n\nЛог: {user_data_dir() / 'app.log'}"
        )
        return

    startup_splash_begin()
    log.info("importing app")
    try:
        from tray_app import WhisperTrayApp
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        log.exception("missing module")
        mark_clean_exit()
        show_message(missing_module_hint(str(missing)), error=True)
        return

    log.info("imports done")
    try:
        app = WhisperTrayApp()
        log.info("tray app created")
        app.run()
        log.info("tray run returned")
        mark_clean_exit()
    except Exception as exc:
        log.exception("fatal")
        show_message(f"Не удалось запустить:\n{exc}", error=True)
        raise


def _supervise() -> None:
    """Перезапуск после нативного краша (оверлей/хук). В onefile-exe не порождаем второй распаковщик."""
    if os.environ.get("FREESCRIBE_SUPERVISED") == "1" or getattr(sys, "frozen", False):
        _run_app()
        return
    import subprocess
    import time

    _setup_logging()
    log = logging.getLogger("whisper_typing")
    script = str(Path(__file__).resolve())
    args = [sys.executable, script, *sys.argv[1:]]
    env = os.environ.copy()
    env["FREESCRIBE_SUPERVISED"] = "1"
    crashes: list[float] = []
    while True:
        proc = subprocess.Popen(args, env=env, cwd=str(Path(script).parent))
        code = proc.wait()
        flag = clean_exit_path(proc.pid)
        clean = flag.is_file()
        if clean:
            try:
                flag.unlink()
            except OSError:
                pass
        if clean or code == 0:
            log.info("child exit code=%s clean=%s", code, clean)
            return
        now = time.time()
        crashes = [t for t in crashes if now - t < 90]
        crashes.append(now)
        log.error("child died code=%s, restart", code)
        if len(crashes) >= 5:
            show_message(
                "FreeScribe-AI несколько раз аварийно закрылась.\nСмотрите crash.log в папке настроек.",
                error=True,
            )
            return
        time.sleep(2)


def main() -> None:
    _supervise()


if __name__ == "__main__":
    freeze_support()
    main()
