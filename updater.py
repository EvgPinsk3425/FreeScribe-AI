"""Проверка и установка обновлений с GitHub Releases."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from settings import APP_VERSION

logger = logging.getLogger("whisper_typing")

GITHUB_REPO = "EvgPinsk3425/FreeScribe-AI"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ASSET_NAME = "FreeScribe-AI.exe"


def _parse_version(raw: str) -> tuple[int, ...]:
    text = (raw or "").strip().lstrip("vV")
    parts = re.findall(r"\d+", text)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def version_newer(remote: str, local: str = APP_VERSION) -> bool:
    a = _parse_version(remote)
    b = _parse_version(local)
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


def _opener(proxy: str = ""):
    proxy = (proxy or "").strip()
    if not proxy:
        return urllib.request.build_opener()
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )


def fetch_latest_release(proxy: str = "") -> dict | None:
    """Возвращает {tag, name, url, notes} или None."""
    req = urllib.request.Request(
        API_LATEST,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"FreeScribe-AI/{APP_VERSION}",
        },
    )
    try:
        with _opener(proxy).open(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("github latest failed: %s", exc)
        return None
    if not isinstance(data, dict):
        return None
    tag = str(data.get("tag_name") or "")
    assets = data.get("assets") or []
    url = ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("name") or "") == ASSET_NAME:
            url = str(asset.get("browser_download_url") or "")
            break
    return {
        "tag": tag,
        "name": str(data.get("name") or tag),
        "url": url,
        "notes": str(data.get("body") or "")[:500],
    }


def check_for_update(proxy: str = "") -> dict | None:
    """Если на GitHub новее — словарь релиза, иначе None."""
    info = fetch_latest_release(proxy)
    if not info or not info.get("tag"):
        return None
    if not version_newer(info["tag"], APP_VERSION):
        return None
    return info


def install_exe_update(download_url: str, proxy: str = "", on_before_quit=None) -> str:
    """Скачивает exe и планирует замену текущего файла после выхода. Возвращает сообщение."""
    if not getattr(sys, "frozen", False):
        return (
            "Обновление exe доступно только для собранной программы.\n"
            f"Скачайте вручную: https://github.com/{GITHUB_REPO}/releases"
        )
    if not download_url:
        return f"В релизе нет файла {ASSET_NAME}."

    target = Path(sys.executable).resolve()
    tmp = Path(tempfile.gettempdir()) / f"FreeScribe-AI-update-{os.getpid()}.exe"
    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": f"FreeScribe-AI/{APP_VERSION}"},
    )
    try:
        with _opener(proxy).open(req, timeout=120) as resp, open(tmp, "wb") as out:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.exception("download update")
        return f"Не удалось скачать обновление:\n{exc}"

    if tmp.stat().st_size < 1_000_000:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return "Скачанный файл слишком маленький — обновление отменено."

    bat = Path(tempfile.gettempdir()) / f"FreeScribe-AI-apply-{os.getpid()}.bat"
    pid = os.getpid()
    bat.write_text(
        "\r\n".join(
            [
                "@echo off",
                "chcp 65001 >nul",
                f":wait",
                f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul',
                "if not errorlevel 1 (",
                "  timeout /t 1 /nobreak >nul",
                "  goto wait",
                ")",
                f'copy /Y "{tmp}" "{target}"',
                f'start "" "{target}"',
                f'del "{tmp}" >nul 2>&1',
                f'del "%~f0" >nul 2>&1',
                "",
            ]
        ),
        encoding="utf-8",
    )
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=creation,
        close_fds=True,
    )
    if on_before_quit:
        try:
            on_before_quit()
        except Exception:
            logger.exception("quit after update")
    return "ok"
