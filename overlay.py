"""Плашка записи поверх окон — не путать с системным индикатором микрофона Windows."""

from __future__ import annotations

import ctypes
import logging
import os
import threading
from ctypes import wintypes

from compat import IS_WIN

logger = logging.getLogger("whisper_typing")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
WM_PAINT = 0x000F
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_NCHITTEST = 0x0084
WM_APP_SHOW = 0x8001
WM_APP_HIDE = 0x8002
HTTRANSPARENT = -1
DT_CENTER = 0x0001
DT_VCENTER = 0x0004
DT_SINGLELINE = 0x0020
LWA_ALPHA = 0x02
TRANSPARENT = 1
ERROR_CLASS_ALREADY_EXISTS = 1410

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", wintypes.BYTE * 32),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = wintypes.HDC
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.RECT), wintypes.UINT]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT), wintypes.BOOL]
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

_TEXT = "FreeScribe-AI  ·  запись"
_WIDTH = 280
_HEIGHT = 36
_CLASS_BASE = "FreeScribeRecordOverlay"


class RecordOverlay:
    def __init__(self) -> None:
        self._hwnd = 0
        self._proc = None
        self._brush = None
        class_name = f"{_CLASS_BASE}_{os.getpid()}"
        self._class_name = ctypes.create_unicode_buffer(class_name)
        self._title = ctypes.create_unicode_buffer("FreeScribe-AI")
        self._ready = threading.Event()
        self._visible = False
        self._gui_lock = threading.Lock()
        if not IS_WIN:
            return
        threading.Thread(target=self._thread, name="record-overlay", daemon=True).start()
        self._ready.wait(timeout=2.0)

    def show(self) -> None:
        if not IS_WIN:
            return
        with self._gui_lock:
            hwnd = self._hwnd
        if not hwnd:
            return
        self._visible = True
        user32.PostMessageW(hwnd, WM_APP_SHOW, 0, 0)

    def hide(self) -> None:
        if not IS_WIN:
            return
        with self._gui_lock:
            hwnd = self._hwnd
        if not hwnd:
            return
        self._visible = False
        user32.PostMessageW(hwnd, WM_APP_HIDE, 0, 0)

    def close(self) -> None:
        with self._gui_lock:
            hwnd = self._hwnd
        if hwnd:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    def _layout_show(self) -> None:
        sw = user32.GetSystemMetrics(0)
        x = max(0, (sw - _WIDTH) // 2)
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, 12, _WIDTH, _HEIGHT, SWP_NOACTIVATE | SWP_SHOWWINDOW)
        user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
        user32.InvalidateRect(self._hwnd, None, True)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            rect = wintypes.RECT(0, 0, _WIDTH, _HEIGHT)
            gdi32.SetBkMode(hdc, TRANSPARENT)
            gdi32.SetTextColor(hdc, 0x00FFFFFF)
            user32.DrawTextW(hdc, _TEXT, -1, ctypes.byref(rect), DT_CENTER | DT_VCENTER | DT_SINGLELINE)
            user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        if msg == WM_APP_SHOW:
            self._layout_show()
            return 0
        if msg == WM_APP_HIDE:
            user32.ShowWindow(hwnd, SW_HIDE)
            return 0
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            with self._gui_lock:
                self._hwnd = 0
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _thread(self) -> None:
        try:
            self._proc = WNDPROC(self._wndproc)
            self._brush = gdi32.CreateSolidBrush(0x003C3CDC)
            inst = kernel32.GetModuleHandleW(None)
            cls = WNDCLASSW()
            cls.lpfnWndProc = ctypes.cast(self._proc, ctypes.c_void_p)
            cls.hInstance = inst
            cls.hbrBackground = self._brush
            cls.lpszClassName = ctypes.cast(self._class_name, wintypes.LPCWSTR)
            atom = user32.RegisterClassW(ctypes.byref(cls))
            if not atom:
                err = ctypes.get_last_error()
                if err != ERROR_CLASS_ALREADY_EXISTS:
                    logger.error("overlay RegisterClassW failed err=%s", err)
                    return
            hwnd = user32.CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED,
                self._class_name,
                self._title,
                WS_POPUP,
                0,
                0,
                _WIDTH,
                _HEIGHT,
                None,
                None,
                inst,
                None,
            )
            if not hwnd:
                logger.error("overlay CreateWindowExW failed err=%s", ctypes.get_last_error())
                return
            with self._gui_lock:
                self._hwnd = hwnd
            user32.SetLayeredWindowAttributes(hwnd, 0, 230, LWA_ALPHA)
            logger.info("record overlay hwnd=%s", hwnd)
            self._ready.set()
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            logger.exception("record overlay")
        finally:
            with self._gui_lock:
                self._hwnd = 0
            self._ready.set()
            if self._brush:
                gdi32.DeleteObject(self._brush)
                self._brush = None
