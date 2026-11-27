"""Вставка текста в активное поле через буфер и WM_PASTE / Ctrl+V."""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
WM_PASTE = 0x0302
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
VK_CONTROL = 0x11
VK_V = 0x56
SW_RESTORE = 9

logger = logging.getLogger("whisper_typing")


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT(ctypes.Structure):
    class _UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]


user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetFocus.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t


def capture_target() -> tuple[int, int]:
    hwnd = user32.GetForegroundWindow() or 0
    focus = 0
    if hwnd:
        pid = wintypes.DWORD()
        tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        my_tid = kernel32.GetCurrentThreadId()
        attached = False
        if tid and tid != my_tid:
            attached = bool(user32.AttachThreadInput(my_tid, tid, True))
        try:
            focus = user32.GetFocus() or 0
        finally:
            if attached:
                user32.AttachThreadInput(my_tid, tid, False)
    logger.info("capture target hwnd=%s focus=%s", hwnd, focus)
    return hwnd, focus


def _open_clipboard(owner: int = 0, retries: int = 40) -> bool:
    hwnd = owner or None
    for attempt in range(retries):
        if user32.OpenClipboard(hwnd):
            return True
        err = ctypes.get_last_error()
        if attempt and attempt % 8 == 0:
            logger.debug("OpenClipboard retry err=%s owner=%s", err, owner)
        time.sleep(0.05)
    logger.warning("OpenClipboard failed err=%s owner=%s", ctypes.get_last_error(), owner)
    return False


def _clipboard_get(owner: int = 0) -> str:
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return ""
    if not _open_clipboard(owner):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _clipboard_set_win32(text: str, owner: int = 0) -> None:
    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise RuntimeError("GlobalAlloc failed")
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        raise RuntimeError("GlobalLock failed")
    try:
        ctypes.memmove(ptr, data, len(data))
    finally:
        kernel32.GlobalUnlock(handle)
    if not _open_clipboard(owner):
        kernel32.GlobalFree(handle)
        raise RuntimeError("OpenClipboard failed")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("SetClipboardData failed")
        handle = None
    finally:
        user32.CloseClipboard()


def _clipboard_set(text: str, owner: int = 0) -> None:
    try:
        import pyperclip

        pyperclip.copy(text)
        if _clipboard_get(owner) == text:
            return
    except Exception:
        logger.debug("pyperclip.copy", exc_info=True)
    _clipboard_set_win32(text, owner)


def _restore_focus(hwnd: int, focus: int) -> int:
    target = focus or hwnd
    if hwnd:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        pid = wintypes.DWORD()
        tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        my_tid = kernel32.GetCurrentThreadId()
        attached = False
        if tid and tid != my_tid:
            attached = bool(user32.AttachThreadInput(my_tid, tid, True))
        try:
            user32.SetForegroundWindow(hwnd)
            if focus:
                user32.SetFocus(focus)
            time.sleep(0.08)
        finally:
            if attached:
                user32.AttachThreadInput(my_tid, tid, False)
    return target


def _send_ctrl_v() -> None:
    def key(vk: int, up: bool = False) -> INPUT:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
        return inp

    events = (INPUT * 5)(
        key(VK_CONTROL, True),
        key(VK_CONTROL),
        key(VK_V),
        key(VK_V, True),
        key(VK_CONTROL, True),
    )
    sent = user32.SendInput(5, events, ctypes.sizeof(INPUT))
    if sent != 5:
        logger.warning("SendInput ctrl+v sent=%s err=%s", sent, ctypes.get_last_error())


def _paste_to_target(target: int) -> bool:
    if not target:
        return False
    try:
        user32.SendMessageW(target, WM_PASTE, 0, 0)
        return True
    except Exception:
        logger.debug("WM_PASTE", exc_info=True)
    return False


def inject_text(
    text: str,
    hwnd: int = 0,
    focus: int = 0,
    *,
    clipboard_owner: int = 0,
) -> None:
    if not text:
        return
    owner = clipboard_owner or 0
    try:
        _clipboard_set(text, owner)
        got = _clipboard_get(owner)
        logger.info("clipboard keep ok=%s chars=%s", got == text, len(got))
        if got != text:
            _clipboard_set_win32(text, owner)
            got = _clipboard_get(owner)
            logger.info("clipboard retry ok=%s chars=%s", got == text, len(got))
        if got != text:
            raise RuntimeError("Текст не попал в буфер обмена (занят другой программой?)")
    except Exception:
        logger.exception("clipboard set")
        raise
    if not hwnd:
        hwnd, focus = capture_target()
    now_hwnd, now_focus = capture_target()
    use_hwnd = now_hwnd or hwnd
    use_focus = now_focus or focus
    target = _restore_focus(use_hwnd, use_focus)
    paste_hwnd = use_focus or target or use_hwnd
    logger.info(
        "paste to hwnd=%s focus=%s owner=%s keep_clipboard=1",
        use_hwnd,
        paste_hwnd,
        owner,
    )
    time.sleep(0.08)
    if _paste_to_target(paste_hwnd):
        time.sleep(0.12)
        return
    _send_ctrl_v()
    time.sleep(0.2)
