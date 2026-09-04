"""Окно настроек на tkinter."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
import ctypes

from settings import (
    MODEL_OPTIONS,
    VK_CONTROL,
    VK_LCONTROL,
    VK_MENU,
    VK_RCONTROL,
    VK_RMENU,
    VK_RSHIFT,
    VK_RWIN,
    VK_SHIFT,
    VK_LWIN,
    cached_models,
    format_hotkey,
    is_modifier_vk,
    sanitize_hotkey_spec,
)

_open_lock = threading.Lock()
_window_open = False


def open_settings_window(current: dict, on_save) -> None:
    global _window_open
    with _open_lock:
        if _window_open:
            return
        _window_open = True

    def run() -> None:
        global _window_open
        try:
            _show_window(current, on_save)
        finally:
            with _open_lock:
                _window_open = False

    threading.Thread(target=run, daemon=True).start()


def _show_window(current: dict, on_save) -> None:
    downloaded = cached_models()
    root = tk.Tk()
    root.title("Whisper Typing — Настройки")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    pad = {"padx": 12, "pady": 6}
    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")

    spec = sanitize_hotkey_spec(current.get("hotkey_spec") or current.get("hotkey") or "ctrl_f8")
    hotkey_holder = {"spec": spec}
    capturing = {"on": False, "mod_only": None}

    ttk.Label(frame, text="Горячая клавиша").grid(row=0, column=0, sticky="w", **pad)
    hotkey_row = ttk.Frame(frame)
    hotkey_row.grid(row=0, column=1, sticky="ew", **pad)
    hotkey_var = tk.StringVar(value=format_hotkey(spec))
    ttk.Label(hotkey_row, textvariable=hotkey_var, width=22).pack(side="left")
    capture_btn = ttk.Button(hotkey_row, text="Задать…")
    capture_btn.pack(side="left", padx=(8, 0))

    ttk.Label(frame, text="Режим").grid(row=1, column=0, sticky="w", **pad)
    mode_labels = {
        "toggle": "Нажать — старт/стоп",
        "hold": "Удерживать клавишу",
    }
    mode_var = tk.StringVar(value=mode_labels.get(current.get("hotkey_mode", "toggle"), mode_labels["toggle"]))
    mode_combo = ttk.Combobox(
        frame,
        state="readonly",
        values=list(mode_labels.values()),
        textvariable=mode_var,
        width=28,
    )
    mode_combo.grid(row=1, column=1, sticky="ew", **pad)

    ttk.Label(frame, text="Локальная модель").grid(row=2, column=0, sticky="w", **pad)
    model_values = []
    for mid, label in MODEL_OPTIONS:
        mark = " (скачана)" if mid in downloaded else " (скачается при выборе)"
        model_values.append(label + mark)
    current_model = current.get("model", "large-v3-turbo")
    model_index = next((i for i, item in enumerate(MODEL_OPTIONS) if item[0] == current_model), 0)
    model_var = tk.StringVar(value=model_values[model_index])
    model_combo = ttk.Combobox(
        frame,
        state="readonly",
        values=model_values,
        textvariable=model_var,
        width=36,
    )
    model_combo.grid(row=2, column=1, sticky="ew", **pad)

    ttk.Label(frame, text="Groq API-ключ").grid(row=3, column=0, sticky="w", **pad)
    groq_var = tk.StringVar(value=current.get("groq_api_key") or "")
    groq_entry = ttk.Entry(frame, textvariable=groq_var, width=36, show="*")
    groq_entry.grid(row=3, column=1, sticky="ew", **pad)

    ttk.Label(frame, text="Прокси Groq").grid(row=4, column=0, sticky="w", **pad)
    proxy_var = tk.StringVar(value=current.get("groq_proxy") or "")
    proxy_entry = ttk.Entry(frame, textvariable=proxy_var, width=36)
    proxy_entry.grid(row=4, column=1, sticky="ew", **pad)

    groq_status = tk.StringVar(value="")
    groq_row = ttk.Frame(frame)
    groq_row.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 6))
    test_btn = ttk.Button(groq_row, text="Проверить Groq")
    test_btn.pack(side="left")
    ttk.Label(groq_row, textvariable=groq_status, wraplength=360).pack(side="left", padx=(10, 0))

    hint = (
        "«Задать…» — затем клавиша или Ctrl/Shift + клавиша. Esc отменяет.\n"
        "Groq из Беларуси даёт 403. Нужен локальный SOCKS5, без системного VPN:\n"
        "warp-cli mode proxy  или  v2rayN (локальный SOCKS, не «системный прокси»).\n"
        "В поле прокси: socks5://127.0.0.1:40000  (WARP)  или  socks5://127.0.0.1:10808 (v2rayN)"
    )
    ttk.Label(frame, text=hint, justify="left").grid(
        row=6, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 10)
    )

    def stop_capture() -> None:
        capturing["on"] = False
        capturing["mod_only"] = None
        capture_btn.configure(text="Задать…")
        try:
            root.grab_release()
        except tk.TclError:
            pass
        root.unbind_all("<KeyPress>")
        root.unbind_all("<KeyRelease>")

    def apply_spec(new_spec: dict) -> None:
        hotkey_holder["spec"] = sanitize_hotkey_spec(new_spec)
        hotkey_var.set(format_hotkey(hotkey_holder["spec"]))
        stop_capture()

    def _pressed_mods() -> dict:
        # Tk на Windows путает NumLock с Alt (бит 0x8). Берём реальное состояние клавиш.
        user32 = ctypes.windll.user32
        return {
            "ctrl": bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000),
            "alt": bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000),
            "shift": bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000),
            "win": bool(
                (user32.GetAsyncKeyState(VK_LWIN) & 0x8000)
                or (user32.GetAsyncKeyState(VK_RWIN) & 0x8000)
            ),
        }

    def on_key_press(event) -> str:
        if not capturing["on"]:
            return ""
        vk = int(event.keycode or 0)
        if vk == 0x1B:
            stop_capture()
            return "break"
        if is_modifier_vk(vk):
            capturing["mod_only"] = vk
            return "break"
        mods = _pressed_mods()
        apply_spec(
            {
                "id": "custom",
                "vk": vk,
                "ctrl": mods["ctrl"],
                "alt": mods["alt"],
                "shift": mods["shift"],
                "win": mods["win"],
                "extended": False,
                "label": "",
            }
        )
        return "break"

    def on_key_release(event) -> str:
        if not capturing["on"]:
            return ""
        vk = int(event.keycode or 0)
        if vk == 0x1B:
            stop_capture()
            return "break"
        if capturing["mod_only"] is None or vk != capturing["mod_only"]:
            return "break"
        extended = vk in (VK_RCONTROL, VK_RMENU, VK_RSHIFT, VK_RWIN) or vk == VK_CONTROL
        apply_spec(
            {
                "id": "custom" if vk not in (VK_RCONTROL,) else "rctrl",
                "vk": vk if vk != VK_CONTROL else (VK_RCONTROL if extended else VK_LCONTROL),
                "ctrl": False,
                "alt": False,
                "shift": False,
                "win": False,
                "extended": vk in (VK_RCONTROL, VK_CONTROL) and extended,
                "label": "",
            }
        )
        return "break"

    def start_capture() -> None:
        capturing["on"] = True
        capturing["mod_only"] = None
        capture_btn.configure(text="Нажмите клавишу… Esc отмена")
        capture_btn.focus_set()
        root.grab_set()
        root.bind_all("<KeyPress>", on_key_press)
        root.bind_all("<KeyRelease>", on_key_release)
        root.focus_force()

    capture_btn.configure(command=start_capture)

    def test_groq_clicked() -> None:
        groq_status.set("Проверяю…")

        def work() -> None:
            from transcriber import test_groq

            result = test_groq(groq_var.get(), proxy_var.get())
            root.after(0, lambda: groq_status.set(result))

        threading.Thread(target=work, daemon=True).start()

    test_btn.configure(command=test_groq_clicked)

    def save() -> None:
        stop_capture()
        mode_id = "hold" if mode_var.get() == mode_labels["hold"] else "toggle"
        model_id = MODEL_OPTIONS[model_values.index(model_var.get())][0]
        spec_now = sanitize_hotkey_spec(hotkey_holder["spec"])
        on_save(
            {
                "hotkey": spec_now.get("id") or "custom",
                "hotkey_spec": spec_now,
                "hotkey_mode": mode_id,
                "model": model_id,
                "groq_api_key": groq_var.get().strip(),
                "groq_proxy": proxy_var.get().strip(),
            }
        )
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=7, column=0, columnspan=2, sticky="e", padx=12, pady=(4, 8))
    ttk.Button(buttons, text="Отмена", command=lambda: (stop_capture(), root.destroy())).pack(
        side="right", padx=(8, 0)
    )
    ttk.Button(buttons, text="Сохранить", command=save).pack(side="right")

    root.protocol("WM_DELETE_WINDOW", lambda: (stop_capture(), root.destroy()))
    root.update_idletasks()
    width, height = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 3
    root.geometry(f"+{x}+{y}")
    root.mainloop()
