"""Вставка распознанного текста в активное окно."""

from __future__ import annotations

from compat import IS_WIN

if IS_WIN:
    from injector_win import capture_target, inject_text
else:
    from injector_posix import capture_target, inject_text

__all__ = ["capture_target", "inject_text"]
