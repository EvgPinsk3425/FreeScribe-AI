"""Локальный SOCKS5 через userspace WireGuard/WARP — без MSI и без системного VPN."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("whisper_typing")

SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 40000
SOCKS_URL = f"socks5://{SOCKS_HOST}:{SOCKS_PORT}"


def socks_url() -> str:
    return SOCKS_URL


def port_open(host: str = SOCKS_HOST, port: int = SOCKS_PORT) -> bool:
    sock = socket.socket()
    sock.settimeout(0.3)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _search_dirs() -> list[Path]:
    dirs: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "F1WhisperTyping" / "warp-socks")
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent / "warp-socks")
        dirs.append(Path(sys.executable).resolve().parent.parent / "warp-socks")
    else:
        dirs.append(Path(__file__).resolve().parent / "warp-socks")
    return dirs


def find_wireproxy() -> tuple[Path, Path] | None:
    for folder in _search_dirs():
        exe = folder / "wireproxy.exe"
        conf = folder / "wireproxy.conf"
        if exe.is_file() and conf.is_file():
            return exe, conf
    return None


def ensure_local_socks() -> str:
    """Запускает wireproxy при необходимости. Возвращает URL или пустую строку."""
    if sys.platform != "win32":
        return ""
    if port_open():
        logger.info("socks already listening %s", SOCKS_URL)
        return SOCKS_URL
    found = find_wireproxy()
    if not found:
        logger.warning("wireproxy.exe not found")
        return ""
    exe, conf = found
    try:
        subprocess.Popen(
            [str(exe), "-c", str(conf)],
            cwd=str(exe.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        logger.exception("start wireproxy")
        return ""
    for _ in range(20):
        time.sleep(0.25)
        if port_open():
            logger.info("wireproxy started %s", SOCKS_URL)
            return SOCKS_URL
    logger.error("wireproxy did not open port %s", SOCKS_PORT)
    return ""
