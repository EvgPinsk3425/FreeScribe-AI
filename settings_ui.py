"""Окно настроек на tkinter."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
import ctypes

from compat import IS_WIN
from settings import (
    APP_TITLE,
    APP_UPDATED,
    APP_VERSION,
    MODEL_CATALOG,
    VK_CONTROL,
    VK_LCONTROL,
    VK_MENU,
    VK_RCONTROL,
    VK_RMENU,
    VK_RSHIFT,
    VK_RWIN,
    VK_SHIFT,
    VK_LWIN,
    download_model,
    format_hotkey,
    is_model_cached,
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
    root = tk.Tk()
    root.title(f"{APP_TITLE} — Настройки  {APP_VERSION}")
    root.resizable(True, True)
    root.attributes("-topmost", True)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    pad = {"padx": 12, "pady": 6}
    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(0, weight=0)

    header = ttk.Frame(frame)
    header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))
    ttk.Label(header, text=APP_TITLE, font=("", 11, "bold")).pack(side="left")
    ttk.Label(header, text=f"{APP_VERSION}  ·  {APP_UPDATED}").pack(side="right")

    spec = sanitize_hotkey_spec(current.get("hotkey_spec") or current.get("hotkey") or "ctrl_f8")
    hotkey_holder = {"spec": spec}
    capturing = {"on": False, "mod_only": None}

    ttk.Label(frame, text="Горячая клавиша").grid(row=1, column=0, sticky="w", **pad)
    hotkey_row = ttk.Frame(frame)
    hotkey_row.grid(row=1, column=1, sticky="ew", **pad)
    hotkey_var = tk.StringVar(value=format_hotkey(spec))
    ttk.Label(hotkey_row, textvariable=hotkey_var, width=22).pack(side="left")
    capture_btn = ttk.Button(hotkey_row, text="Задать…")
    capture_btn.pack(side="left", padx=(8, 0))

    ttk.Label(frame, text="Режим").grid(row=2, column=0, sticky="w", **pad)
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
    mode_combo.grid(row=2, column=1, sticky="ew", **pad)

    signals = ttk.LabelFrame(frame, text="Сигналы")
    signals.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=6)
    toast_var = tk.BooleanVar(value=bool(current.get("show_toasts", True)))
    beep_var = tk.BooleanVar(value=bool(current.get("record_beeps", True)))
    ttk.Checkbutton(
        signals,
        text="Всплывающие подсказки у иконки",
        variable=toast_var,
    ).pack(anchor="w", padx=10, pady=(8, 2))
    ttk.Checkbutton(
        signals,
        text="Звук при старте и окончании записи",
        variable=beep_var,
    ).pack(anchor="w", padx=10, pady=(2, 8))

    models_box = ttk.LabelFrame(frame, text="Модели")
    models_box.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=12, pady=6)
    frame.rowconfigure(4, weight=1)
    models_box.columnconfigure(0, weight=1)

    tree = ttk.Treeview(
        models_box,
        columns=("size", "status"),
        show="tree headings",
        height=8,
        selectmode="browse",
    )
    tree.heading("#0", text="Модель")
    tree.heading("size", text="Размер")
    tree.heading("status", text="Статус")
    tree.column("#0", width=320, minwidth=220)
    tree.column("size", width=80, stretch=False)
    tree.column("status", width=160, stretch=False)
    tree.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
    models_box.rowconfigure(0, weight=1)
    scroll = ttk.Scrollbar(models_box, orient="vertical", command=tree.yview)
    scroll.grid(row=0, column=1, sticky="ns", pady=(8, 4))
    tree.configure(yscrollcommand=scroll.set)

    current_model = current.get("model", "large-v3-turbo")
    selected_model = {"id": current_model}

    def _status_for(mid: str) -> str:
        cached = is_model_cached(mid)
        if mid == selected_model["id"] and mid == current_model:
            return "скачана · текущая" if cached else "текущая · скачается"
        if mid == selected_model["id"]:
            return "скачана · выбрана" if cached else "выбрана · скачается"
        return "скачана" if cached else "не скачана"

    def _refresh_status() -> None:
        for spec in MODEL_CATALOG:
            if tree.exists(spec["id"]):
                tree.item(spec["id"], values=(spec["size_label"], _status_for(spec["id"])))

    def _fill_tree() -> None:
        tree.delete(*tree.get_children())
        groups: dict[str, str] = {}
        for spec in MODEL_CATALOG:
            group = spec["group"]
            if group not in groups:
                gid = f"group:{group}"
                tree.insert("", "end", iid=gid, text=group, open=True)
                groups[group] = gid
            star = " ★" if spec.get("recommended") else ""
            tree.insert(
                groups[group],
                "end",
                iid=spec["id"],
                text=f"{spec['label']}{star} — {spec['hint']}",
                values=(spec["size_label"], _status_for(spec["id"])),
            )

    def _select_model(mid: str) -> None:
        if mid not in {item["id"] for item in MODEL_CATALOG}:
            return
        selected_model["id"] = mid
        _refresh_status()
        tree.see(mid)
        tree.selection_set(mid)
        tree.focus(mid)

    def on_tree_select(_event=None) -> None:
        iid = tree.focus()
        if iid not in {item["id"] for item in MODEL_CATALOG}:
            return
        if selected_model["id"] == iid:
            return
        selected_model["id"] = iid
        _refresh_status()

    any_cached = any(is_model_cached(item["id"]) for item in MODEL_CATALOG)
    model_status = tk.StringVar(
        value=(
            "Скачайте модель и нажмите «Сохранить», чтобы включить её."
            if any_cached
            else "Первый запуск: выберите модель (turbo или GigaAM Сбера) и нажмите «Скачать». "
            "GigaAM меньше (~250 МБ) и лучше на русском."
        )
    )
    models_btns = ttk.Frame(models_box)
    models_btns.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
    download_btn = ttk.Button(models_btns, text="Скачать выбранную")
    download_btn.pack(side="left")
    ttk.Label(models_btns, textvariable=model_status, wraplength=420).pack(side="left", padx=(10, 0))

    downloading = {"on": False}

    def download_clicked() -> None:
        mid = selected_model["id"]
        spec = next((item for item in MODEL_CATALOG if item["id"] == mid), None)
        if spec is None or downloading["on"]:
            return
        if is_model_cached(mid):
            model_status.set(f"{spec['label']} уже скачана")
            return
        downloading["on"] = True
        download_btn.configure(state="disabled")
        model_status.set(f"Скачиваю {spec['label']} ({spec['size_label']})…")

        def work() -> None:
            try:
                download_model(mid)
            except Exception as exc:
                msg = str(exc)
                root.after(0, lambda m=msg: _download_done(False, m))
                return
            root.after(0, lambda: _download_done(True, ""))

        threading.Thread(target=work, daemon=True).start()

    def _download_done(ok: bool, error: str) -> None:
        downloading["on"] = False
        download_btn.configure(state="normal")
        spec = next((item for item in MODEL_CATALOG if item["id"] == selected_model["id"]), None)
        label = spec["label"] if spec else selected_model["id"]
        if ok:
            model_status.set(f"{label} скачана. Нажмите «Сохранить», чтобы включить.")
        else:
            model_status.set(f"Не удалось скачать {label}: {error}")
        _refresh_status()
        if selected_model["id"] in {item["id"] for item in MODEL_CATALOG}:
            tree.selection_set(selected_model["id"])
            tree.focus(selected_model["id"])

    download_btn.configure(command=download_clicked)
    tree.bind("<<TreeviewSelect>>", on_tree_select)
    _fill_tree()
    _select_model(current_model)

    from audio_recorder import AudioRecorder, list_capture_devices

    ttk.Label(frame, text="Микрофон").grid(row=5, column=0, sticky="w", **pad)
    mic_devices = list_capture_devices()
    mic_labels = ["Авто — сначала RDP «Удалённое аудио»"] + [item["label"] for item in mic_devices]
    mic_ids = [""] + [item["id"] for item in mic_devices]
    saved_mic = current.get("mic_device") or ""
    mic_index = mic_ids.index(saved_mic) if saved_mic in mic_ids else 0
    mic_var = tk.StringVar(value=mic_labels[mic_index])
    mic_combo = ttk.Combobox(
        frame,
        state="readonly",
        values=mic_labels,
        textvariable=mic_var,
        width=42,
    )
    mic_combo.grid(row=5, column=1, sticky="ew", **pad)
    groq_status = tk.StringVar(value="")

    ttk.Label(frame, text="Проверка").grid(row=6, column=0, sticky="w", **pad)
    mic_row = ttk.Frame(frame)
    mic_row.grid(row=6, column=1, sticky="ew", **pad)
    level_canvas = tk.Canvas(mic_row, width=220, height=16, highlightthickness=1, highlightbackground="#888")
    level_canvas.pack(side="left")
    mic_check_btn = ttk.Button(mic_row, text="Слушать")
    mic_check_btn.pack(side="left", padx=(8, 0))
    mic_level_text = tk.StringVar(value="0%")
    ttk.Label(mic_row, textvariable=mic_level_text, width=5).pack(side="left", padx=(6, 0))

    ttk.Label(frame, text="Громкость").grid(row=7, column=0, sticky="w", **pad)
    gain_row = ttk.Frame(frame)
    gain_row.grid(row=7, column=1, sticky="ew", **pad)
    try:
        saved_gain = float(current.get("mic_gain") or 1.5)
    except (TypeError, ValueError):
        saved_gain = 1.5
    gain_var = tk.DoubleVar(value=saved_gain)
    gain_label = tk.StringVar(value=f"{saved_gain:.1f}×")

    def _selected_mic_id() -> str:
        try:
            return mic_ids[mic_labels.index(mic_var.get())]
        except ValueError:
            return ""

    monitor = {"rec": None, "on": False}

    def _draw_level(value: float) -> None:
        level_canvas.delete("all")
        width = max(0, min(218, int(218 * value)))
        color = "#2e7d32" if value < 0.7 else ("#f9a825" if value < 0.9 else "#c62828")
        if width:
            level_canvas.create_rectangle(1, 1, 1 + width, 15, fill=color, outline="")
        mic_level_text.set(f"{int(value * 100)}%")

    def stop_monitor() -> None:
        rec = monitor["rec"]
        monitor["rec"] = None
        monitor["on"] = False
        if rec is not None:
            try:
                rec.close()
            except Exception:
                pass
        mic_check_btn.configure(text="Слушать")
        _draw_level(0.0)

    def tick_monitor() -> None:
        if not monitor["on"]:
            return
        rec = monitor["rec"]
        if rec is not None:
            rec.gain = max(0.2, min(8.0, float(gain_var.get())))
            _draw_level(rec.current_level())
        root.after(50, tick_monitor)

    def start_monitor() -> None:
        stop_monitor()
        rec = AudioRecorder()
        rec.configure(_selected_mic_id(), float(gain_var.get()))
        try:
            rec.start_monitor()
        except Exception as exc:
            groq_status.set(f"Микрофон: {exc}")
            return
        monitor["rec"] = rec
        monitor["on"] = True
        mic_check_btn.configure(text="Стоп")
        tick_monitor()

    def toggle_monitor() -> None:
        if monitor["on"]:
            stop_monitor()
        else:
            start_monitor()

    def on_mic_change(_event=None) -> None:
        if monitor["on"]:
            start_monitor()

    def on_gain(_value=None) -> None:
        gain_label.set(f"{float(gain_var.get()):.1f}×")

    gain_scale = ttk.Scale(gain_row, from_=0.4, to=4.0, variable=gain_var, command=on_gain)
    gain_scale.pack(side="left", fill="x", expand=True)
    ttk.Label(gain_row, textvariable=gain_label, width=5).pack(side="left", padx=(8, 0))
    mic_check_btn.configure(command=toggle_monitor)
    mic_combo.bind("<<ComboboxSelected>>", on_mic_change)

    ttk.Label(frame, text="Groq API-ключ").grid(row=8, column=0, sticky="w", **pad)
    groq_var = tk.StringVar(value=current.get("groq_api_key") or "")
    groq_entry = ttk.Entry(frame, textvariable=groq_var, width=36, show="*")
    groq_entry.grid(row=8, column=1, sticky="ew", **pad)

    ttk.Label(frame, text="Прокси Groq").grid(row=9, column=0, sticky="w", **pad)
    proxy_var = tk.StringVar(value=current.get("groq_proxy") or "")
    proxy_entry = ttk.Entry(frame, textvariable=proxy_var, width=36)
    proxy_entry.grid(row=9, column=1, sticky="ew", **pad)

    groq_row = ttk.Frame(frame)
    groq_row.grid(row=10, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 6))
    test_btn = ttk.Button(groq_row, text="Проверить Groq")
    test_btn.pack(side="left")
    ttk.Label(groq_row, textvariable=groq_status, wraplength=360).pack(side="left", padx=(10, 0))

    hint = (
        "Модели: выберите Whisper или GigaAM Сбера, при необходимости нажмите «Скачать», "
        "затем «Сохранить».\n"
        "Микрофон RDP: выберите «Удалённое аудио», нажмите «Слушать» и говорите — "
        "полоска должна прыгать. «Задать…» — клавиша, Esc отменяет."
    )
    ttk.Label(frame, text=hint, justify="left", wraplength=520).grid(
        row=11, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 10)
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

    def _pressed_mods(event=None) -> dict:
        if IS_WIN:
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
        state = int(getattr(event, "state", 0) or 0)
        return {
            "ctrl": bool(state & 0x4),
            "alt": bool(state & 0x10),
            "shift": bool(state & 0x1),
            "win": bool(state & 0x8),
        }

    _MOD_KEYSYMS = {
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
        "Meta_L",
        "Meta_R",
        "Super_L",
        "Super_R",
        "Command",
        "Option_L",
        "Option_R",
    }

    def on_key_press(event) -> str:
        if not capturing["on"]:
            return ""
        if (event.keysym or "") == "Escape" or int(event.keycode or 0) == 0x1B:
            stop_capture()
            return "break"
        if not IS_WIN:
            keysym = str(event.keysym or "")
            if keysym in _MOD_KEYSYMS:
                capturing["mod_only"] = keysym
                return "break"
            mods = _pressed_mods(event)
            apply_spec(
                {
                    "id": "custom",
                    "vk": 0,
                    "keysym": keysym,
                    "ctrl": mods["ctrl"],
                    "alt": mods["alt"],
                    "shift": mods["shift"],
                    "win": mods["win"],
                    "extended": False,
                    "label": "",
                }
            )
            return "break"
        vk = int(event.keycode or 0)
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
        if (event.keysym or "") == "Escape" or int(event.keycode or 0) == 0x1B:
            stop_capture()
            return "break"
        if not IS_WIN:
            if capturing["mod_only"] is None or str(event.keysym or "") != capturing["mod_only"]:
                return "break"
            apply_spec(
                {
                    "id": "custom",
                    "vk": 0,
                    "keysym": str(event.keysym or ""),
                    "ctrl": False,
                    "alt": False,
                    "shift": False,
                    "win": False,
                    "extended": False,
                    "label": "",
                }
            )
            return "break"
        vk = int(event.keycode or 0)
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
        stop_monitor()
        mode_id = "hold" if mode_var.get() == mode_labels["hold"] else "toggle"
        model_id = selected_model["id"]
        spec_now = sanitize_hotkey_spec(hotkey_holder["spec"])
        on_save(
            {
                "hotkey": spec_now.get("id") or "custom",
                "hotkey_spec": spec_now,
                "hotkey_mode": mode_id,
                "model": model_id,
                "groq_api_key": groq_var.get().strip(),
                "groq_proxy": proxy_var.get().strip(),
                "mic_device": _selected_mic_id(),
                "mic_gain": max(0.2, min(8.0, float(gain_var.get()))),
                "show_toasts": bool(toast_var.get()),
                "record_beeps": bool(beep_var.get()),
            }
        )
        root.destroy()

    def close_window() -> None:
        stop_capture()
        stop_monitor()
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=12, column=0, columnspan=2, sticky="e", padx=12, pady=(4, 8))
    ttk.Button(buttons, text="Отмена", command=close_window).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="Сохранить", command=save).pack(side="right")

    root.protocol("WM_DELETE_WINDOW", close_window)
    root.minsize(580, 720)
    root.update_idletasks()
    width, height = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 3
    root.geometry(f"+{x}+{y}")
    root.mainloop()
