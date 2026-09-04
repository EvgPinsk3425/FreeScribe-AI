"""Глобальные горячие клавиши: низкоуровневый хук на отдельном потоке."""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes
from typing import Callable

from settings import (
    VK_CONTROL,
    VK_LCONTROL,
    VK_LMENU,
    VK_LSHIFT,
    VK_LWIN,
    VK_MENU,
    VK_RCONTROL,
    VK_RMENU,
    VK_RSHIFT,
    VK_RWIN,
    VK_SHIFT,
    format_hotkey,
    is_modifier_vk,
    sanitize_hotkey_spec,
    spec_from_preset,
)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WH_KEYBOARD_LL = 13
HC_ACTION = 0
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
LRESULT = ctypes.c_ssize_t

logger = logging.getLogger("whisper_typing")


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LowLevelKeyboardProc,
    ctypes.c_void_p,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class HotkeyManager:
    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        hotkey_id: str = "ctrl_f8",
        hold_mode: bool = False,
        on_registered: Callable[[str], None] | None = None,
        spec: dict | None = None,
    ):
        self._on_press = on_press
        self._on_release = on_release
        self._on_registered = on_registered
        self._spec = sanitize_hotkey_spec(spec or spec_from_preset(hotkey_id))
        self._hotkey_id = self._spec.get("id") or "custom"
        self._hold_mode = hold_mode
        self._hook = None
        self._hook_proc = LowLevelKeyboardProc(self._ll_proc)
        self._key_held = False
        self._held_since = 0.0
        self._last_fire = 0.0
        self._mods = {"ctrl": False, "alt": False, "shift": False, "win": False}
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()

    def attach(self, icon=None) -> None:
        self._start_hook_thread()
        logger.info("hotkey attach spec=%s", format_hotkey(self._spec))

    def set_hotkey(self, hotkey_id: str | dict, spec: dict | None = None) -> None:
        if isinstance(hotkey_id, dict):
            self._spec = sanitize_hotkey_spec(hotkey_id)
        elif spec is not None:
            self._spec = sanitize_hotkey_spec(spec)
        else:
            self._spec = spec_from_preset(hotkey_id)
        self._hotkey_id = self._spec.get("id") or "custom"
        self._key_held = False
        self._last_fire = 0.0
        logger.info("hotkey now %s", format_hotkey(self._spec))

    def set_hold_mode(self, hold: bool) -> None:
        self._hold_mode = hold

    def start(self, icon=None) -> None:
        self.attach(icon)

    def stop(self) -> None:
        tid = self._thread_id
        if tid:
            user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._uninstall_hook()
        self._thread = None
        self._thread_id = 0

    def _start_hook_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._hook_loop, name="hotkey-hook", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=2.0):
            raise RuntimeError("поток горячих клавиш не запустился")

    def _hook_loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        dummy = MSG()
        user32.PeekMessageW(ctypes.byref(dummy), None, 0, 0, 0)
        if not self._install_hook():
            self._ready.set()
            return
        logger.info("keyboard hook ok spec=%s thread=%s", format_hotkey(self._spec), self._thread_id)
        self._ready.set()
        if self._on_registered:
            try:
                self._on_registered(self._hotkey_id)
            except Exception:
                logger.exception("on_registered")
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        self._uninstall_hook()

    def _install_hook(self) -> bool:
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
        if not self._hook:
            logger.error("SetWindowsHookEx failed err=%s", ctypes.get_last_error())
            return False
        return True

    def _uninstall_hook(self) -> None:
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
        self._key_held = False

    def _update_mods(self, vk: int, is_down: bool) -> None:
        if vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
            self._mods["ctrl"] = is_down
        elif vk in (VK_MENU, VK_LMENU, VK_RMENU):
            self._mods["alt"] = is_down
        elif vk in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT):
            self._mods["shift"] = is_down
        elif vk in (VK_LWIN, VK_RWIN):
            self._mods["win"] = is_down

    def _is_trigger_vk(self, vk: int, extended: bool) -> bool:
        want = int(self._spec["vk"])
        if is_modifier_vk(want):
            if want == VK_RCONTROL or self._spec.get("extended"):
                return vk == VK_RCONTROL or (vk == VK_CONTROL and extended)
            if want == VK_LCONTROL:
                return vk == VK_LCONTROL or (vk == VK_CONTROL and not extended)
            return vk == want or vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL)
        return vk == want

    def _mod_is_down(self, name: str, *vks: int) -> bool:
        if self._mods.get(name):
            return True
        return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in vks)

    def _combo_down(self, vk: int, extended: bool) -> bool:
        if not self._is_trigger_vk(vk, extended):
            return False
        if is_modifier_vk(int(self._spec["vk"])):
            return True
        ctrl = self._mod_is_down("ctrl", VK_CONTROL, VK_LCONTROL, VK_RCONTROL)
        alt = self._mod_is_down("alt", VK_MENU, VK_LMENU, VK_RMENU)
        shift = self._mod_is_down("shift", VK_SHIFT, VK_LSHIFT, VK_RSHIFT)
        win = self._mod_is_down("win", VK_LWIN, VK_RWIN)
        return (
            ctrl == bool(self._spec.get("ctrl"))
            and alt == bool(self._spec.get("alt"))
            and shift == bool(self._spec.get("shift"))
            and win == bool(self._spec.get("win"))
        )

    def _ll_proc(self, nCode, wParam, lParam):
        try:
            if nCode == HC_ACTION:
                info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.flags & LLKHF_INJECTED:
                    return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
                is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)
                is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                if is_down or is_up:
                    self._update_mods(info.vkCode, is_down)
                now = time.monotonic()
                if self._key_held and (now - self._held_since) > 0.8:
                    self._key_held = False
                if is_down and self._combo_down(info.vkCode, bool(info.flags & LLKHF_EXTENDED)):
                    if self._hold_mode:
                        if not self._key_held:
                            self._key_held = True
                            self._held_since = now
                            logger.info("hotkey down spec=%s vk=0x%X", format_hotkey(self._spec), info.vkCode)
                            threading.Thread(target=self._on_press, daemon=True).start()
                    elif (now - self._last_fire) >= 0.28:
                        self._last_fire = now
                        self._key_held = True
                        self._held_since = now
                        logger.info("hotkey down spec=%s vk=0x%X", format_hotkey(self._spec), info.vkCode)
                        threading.Thread(target=self._on_press, daemon=True).start()
                    return 1
                if is_up and self._is_trigger_vk(info.vkCode, bool(info.flags & LLKHF_EXTENDED)):
                    was_held = self._key_held
                    self._key_held = False
                    if was_held:
                        logger.info("hotkey up spec=%s", format_hotkey(self._spec))
                        if self._hold_mode:
                            threading.Thread(target=self._on_release, daemon=True).start()
                    if was_held or (now - self._last_fire) < 0.5:
                        return 1
        except Exception:
            logger.exception("ll hook")
        return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
