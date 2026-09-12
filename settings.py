"""Сохранение настроек в %APPDATA%\\WhisperTyping."""

from __future__ import annotations

import json
import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

from compat import user_data_dir

APP_NAME = "F1WhisperTyping"
APP_VERSION = "2.0"
APP_UPDATED = "12.09.2026 08:51"

HOTKEY_OPTIONS = [
    ("f1", "F1", 0x70, 0),
    ("f2", "F2", 0x71, 0),
    ("f3", "F3", 0x72, 0),
    ("f4", "F4", 0x73, 0),
    ("f5", "F5", 0x74, 0),
    ("f6", "F6", 0x75, 0),
    ("f7", "F7", 0x76, 0),
    ("f8", "F8", 0x77, 0),
    ("f9", "F9", 0x78, 0),
    ("f10", "F10", 0x79, 0),
    ("f11", "F11", 0x7A, 0),
    ("f12", "F12", 0x7B, 0),
    ("ctrl_space", "Ctrl+Пробел", 0x20, 0x0002),
    ("ctrl_f8", "Ctrl+F8", 0x77, 0x0002),
    ("pause", "Pause", 0x13, 0),
    ("scroll_lock", "Scroll Lock", 0x91, 0),
    ("insert", "Insert", 0x2D, 0),
    ("rctrl", "Правый Ctrl", 0xA3, 0),
]

HOTKEY_LABELS = {hid: label for hid, label, _vk, _mods in HOTKEY_OPTIONS}
HOTKEY_VK = {hid: vk for hid, _label, vk, _mods in HOTKEY_OPTIONS}
HOTKEY_MODS = {hid: mods for hid, _label, _vk, mods in HOTKEY_OPTIONS}

# Шаблонный каталог. Новая модель = ещё один словарь ниже.
# engine: faster-whisper (CTranslate2) или onnx-asr (GigaAM Сбера и др.).
MODEL_CATALOG = [
    {
        "id": "large-v3-turbo",
        "group": "Whisper",
        "label": "turbo",
        "hint": "быстро и точно, рекомендуется",
        "engine": "faster-whisper",
        "source": "large-v3-turbo",
        "repo": "Systran/faster-whisper-large-v3-turbo",
        "hf_folders": [
            "models--Systran--faster-whisper-large-v3-turbo",
            "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
            "models--dropbox-dash--faster-whisper-large-v3-turbo",
        ],
        "cache_glob": "model.bin",
        "size_bytes": 2_000_000_000,
        "size_label": "~1.6 ГБ",
        "recommended": True,
    },
    {
        "id": "small",
        "group": "Whisper",
        "label": "small",
        "hint": "легче, менее точно",
        "engine": "faster-whisper",
        "source": "small",
        "repo": "Systran/faster-whisper-small",
        "hf_folders": ["models--Systran--faster-whisper-small"],
        "cache_glob": "model.bin",
        "size_bytes": 800_000_000,
        "size_label": "~500 МБ",
    },
    {
        "id": "base",
        "group": "Whisper",
        "label": "base",
        "hint": "самая быстрая Whisper",
        "engine": "faster-whisper",
        "source": "base",
        "repo": "Systran/faster-whisper-base",
        "hf_folders": ["models--Systran--faster-whisper-base"],
        "cache_glob": "model.bin",
        "size_bytes": 300_000_000,
        "size_label": "~150 МБ",
    },
    {
        "id": "medium",
        "group": "Whisper",
        "label": "medium",
        "hint": "точнее small, медленнее",
        "engine": "faster-whisper",
        "source": "medium",
        "repo": "Systran/faster-whisper-medium",
        "hf_folders": ["models--Systran--faster-whisper-medium"],
        "cache_glob": "model.bin",
        "size_bytes": 2_000_000_000,
        "size_label": "~1.5 ГБ",
    },
    {
        "id": "large-v3",
        "group": "Whisper",
        "label": "large-v3",
        "hint": "максимум качества, на CPU очень медленно",
        "engine": "faster-whisper",
        "source": "large-v3",
        "repo": "Systran/faster-whisper-large-v3",
        "hf_folders": ["models--Systran--faster-whisper-large-v3"],
        "cache_glob": "model.bin",
        "size_bytes": 4_000_000_000,
        "size_label": "~3 ГБ",
    },
    {
        "id": "gigaam-v3-e2e-rnnt",
        "group": "Сбер",
        "label": "GigaAM v3 RNN-T",
        "hint": "лучший русский, с пунктуацией",
        "engine": "onnx-asr",
        "source": "gigaam-v3-e2e-rnnt",
        "repo": "istupakov/gigaam-v3-onnx",
        "hf_folders": ["models--istupakov--gigaam-v3-onnx"],
        "allow_patterns": [
            "config.json",
            "v3_e2e_rnnt.yaml",
            "v3_e2e_rnnt_vocab.txt",
            "v3_e2e_rnnt_encoder.int8.onnx",
            "v3_e2e_rnnt_decoder.int8.onnx",
            "v3_e2e_rnnt_joint.int8.onnx",
        ],
        "cache_glob": "*e2e_rnnt_encoder*.onnx",
        "quantization": "int8",
        "size_bytes": 400_000_000,
        "size_label": "~250 МБ",
        "recommended": True,
    },
    {
        "id": "gigaam-v3-e2e-ctc",
        "group": "Сбер",
        "label": "GigaAM v3 CTC",
        "hint": "быстрее RNN-T, тоже русский",
        "engine": "onnx-asr",
        "source": "gigaam-v3-e2e-ctc",
        "repo": "istupakov/gigaam-v3-onnx",
        "hf_folders": ["models--istupakov--gigaam-v3-onnx"],
        "allow_patterns": [
            "config.json",
            "v3_e2e_ctc.yaml",
            "v3_e2e_ctc_vocab.txt",
            "v3_e2e_ctc.int8.onnx",
        ],
        "cache_glob": "*e2e_ctc.int8.onnx",
        "quantization": "int8",
        "size_bytes": 400_000_000,
        "size_label": "~250 МБ",
    },
]

MODEL_OPTIONS = [
    (item["id"], f"{item['label']} — {item['hint']}")
    for item in MODEL_CATALOG
]

DEFAULTS = {
    "hotkey": "ctrl_f8",
    "hotkey_spec": None,
    "hotkey_mode": "toggle",
    "model": "large-v3-turbo",
    "groq_api_key": "",
    "groq_proxy": "",
    "mic_device": "",
    "mic_gain": 1.5,
}

MOD_ALT = 0x0001
MOD_CTRL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1

_MODIFIER_VKS = {
    VK_SHIFT,
    VK_CONTROL,
    VK_MENU,
    VK_LWIN,
    VK_RWIN,
    VK_LSHIFT,
    VK_RSHIFT,
    VK_LCONTROL,
    VK_RCONTROL,
    VK_LMENU,
    VK_RMENU,
}

_VK_NAMES = {
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x13: "Pause",
    0x14: "Caps Lock",
    0x1B: "Esc",
    0x20: "Пробел",
    0x21: "Page Up",
    0x22: "Page Down",
    0x23: "End",
    0x24: "Home",
    0x25: "Влево",
    0x26: "Вверх",
    0x27: "Вправо",
    0x28: "Вниз",
    0x2C: "Print Screen",
    0x2D: "Insert",
    0x2E: "Delete",
    0x5D: "Menu",
    0x90: "Num Lock",
    0x91: "Scroll Lock",
    VK_LCONTROL: "Левый Ctrl",
    VK_RCONTROL: "Правый Ctrl",
    VK_LSHIFT: "Левый Shift",
    VK_RSHIFT: "Правый Shift",
    VK_LMENU: "Левый Alt",
    VK_RMENU: "Правый Alt",
    VK_LWIN: "Win",
    VK_RWIN: "Правый Win",
}
for _i in range(1, 25):
    _VK_NAMES[0x6F + _i] = f"F{_i}"
for _i in range(10):
    _VK_NAMES[0x30 + _i] = str(_i)
    _VK_NAMES[0x60 + _i] = f"Num {_i}"
for _i in range(26):
    _VK_NAMES[0x41 + _i] = chr(ord("A") + _i)


def vk_name(vk: int, extended: bool = False) -> str:
    if vk == VK_CONTROL and extended:
        return "Правый Ctrl"
    if vk == VK_CONTROL:
        return "Ctrl"
    return _VK_NAMES.get(int(vk), f"VK_{int(vk):02X}")


def is_modifier_vk(vk: int) -> bool:
    return int(vk) in _MODIFIER_VKS


def spec_from_preset(hotkey_id: str) -> dict:
    if hotkey_id not in HOTKEY_VK:
        hotkey_id = DEFAULTS["hotkey"]
    vk = HOTKEY_VK[hotkey_id]
    mods = HOTKEY_MODS.get(hotkey_id, 0)
    spec = {
        "id": hotkey_id,
        "vk": vk,
        "ctrl": bool(mods & MOD_CTRL),
        "alt": bool(mods & MOD_ALT),
        "shift": bool(mods & MOD_SHIFT),
        "win": bool(mods & MOD_WIN),
        "extended": hotkey_id == "rctrl",
        "label": HOTKEY_LABELS[hotkey_id],
    }
    return spec


def sanitize_hotkey_spec(raw) -> dict:
    if isinstance(raw, str):
        return spec_from_preset(raw)
    if isinstance(raw, dict) and raw.get("keysym") and "vk" not in raw:
        raw = dict(raw)
        raw["vk"] = 0
    if not isinstance(raw, dict) or "vk" not in raw:
        return spec_from_preset(DEFAULTS["hotkey"])
    try:
        vk = int(raw["vk"])
    except (TypeError, ValueError):
        return spec_from_preset(DEFAULTS["hotkey"])
    spec = {
        "id": raw.get("id") if raw.get("id") in HOTKEY_VK else "custom",
        "vk": vk,
        "keysym": str(raw.get("keysym") or ""),
        "ctrl": bool(raw.get("ctrl")),
        "alt": bool(raw.get("alt")),
        "shift": bool(raw.get("shift")),
        "win": bool(raw.get("win")),
        "extended": bool(raw.get("extended")),
        "label": str(raw.get("label") or ""),
    }
    if vk and is_modifier_vk(vk):
        spec["ctrl"] = False
        spec["alt"] = False
        spec["shift"] = False
        spec["win"] = False
    spec["label"] = spec["label"] or format_hotkey(spec)
    return spec


def format_hotkey(spec: dict) -> str:
    vk = int(spec.get("vk") or 0)
    parts = []
    if spec.get("ctrl") and not (vk and is_modifier_vk(vk)):
        parts.append("Ctrl")
    if spec.get("alt") and vk not in (VK_MENU, VK_LMENU, VK_RMENU):
        parts.append("Alt")
    if spec.get("shift") and vk not in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT):
        parts.append("Shift")
    if spec.get("win") and vk not in (VK_LWIN, VK_RWIN):
        parts.append("Cmd" if sys.platform == "darwin" else "Win")
    if spec.get("keysym"):
        parts.append(str(spec["keysym"]))
    else:
        parts.append(vk_name(vk, bool(spec.get("extended"))))
    return "+".join(parts)


def hotkey_label(data: dict) -> str:
    spec = data.get("hotkey_spec")
    if isinstance(spec, dict) and (spec.get("vk") or spec.get("keysym")):
        return spec.get("label") or format_hotkey(spec)
    hid = data.get("hotkey")
    return HOTKEY_LABELS.get(hid, format_hotkey(spec_from_preset(DEFAULTS["hotkey"])))


def app_dir() -> Path:
    return user_data_dir()


def disk_free() -> int:
    try:
        return shutil.disk_usage(_hub_dir()).free
    except OSError:
        return shutil.disk_usage(Path.home()).free


def settings_path() -> Path:
    return app_dir() / "settings.json"


def log_path() -> Path:
    return app_dir() / "app.log"


def load_settings() -> dict:
    data = dict(DEFAULTS)
    path = settings_path()
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    if data.get("hotkey_mode") not in ("toggle", "hold"):
        data["hotkey_mode"] = DEFAULTS["hotkey_mode"]
    if isinstance(data.get("hotkey_spec"), dict) and "vk" in data["hotkey_spec"]:
        data["hotkey_spec"] = sanitize_hotkey_spec(data["hotkey_spec"])
        data["hotkey"] = data["hotkey_spec"].get("id") or "custom"
    elif isinstance(data.get("hotkey"), dict):
        data["hotkey_spec"] = sanitize_hotkey_spec(data["hotkey"])
        data["hotkey"] = data["hotkey_spec"].get("id") or "custom"
    elif data.get("hotkey") in HOTKEY_VK:
        data["hotkey_spec"] = spec_from_preset(data["hotkey"])
    else:
        data["hotkey"] = DEFAULTS["hotkey"]
        data["hotkey_spec"] = spec_from_preset(data["hotkey"])
    known_models = {item["id"] for item in MODEL_CATALOG}
    if data.get("model") not in known_models:
        data["model"] = DEFAULTS["model"]
    if not isinstance(data.get("groq_api_key"), str):
        data["groq_api_key"] = ""
    if not isinstance(data.get("groq_proxy"), str):
        data["groq_proxy"] = ""
    if not isinstance(data.get("mic_device"), str):
        data["mic_device"] = ""
    try:
        data["mic_gain"] = max(0.2, min(8.0, float(data.get("mic_gain") or DEFAULTS["mic_gain"])))
    except (TypeError, ValueError):
        data["mic_gain"] = DEFAULTS["mic_gain"]
    return data


def save_settings(data: dict) -> None:
    merged = dict(DEFAULTS)
    merged.update(data)
    settings_path().write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _hub_dir() -> Path:
    return Path.home() / ".cache" / "huggingface" / "hub"


def get_model(model_id: str) -> dict:
    for item in MODEL_CATALOG:
        if item["id"] == model_id:
            return item
    return next(item for item in MODEL_CATALOG if item["id"] == DEFAULTS["model"])


def is_model_cached(model_id: str) -> bool:
    spec = next((item for item in MODEL_CATALOG if item["id"] == model_id), None)
    if spec is None:
        return False
    pattern = spec.get("cache_glob") or "model.bin"
    min_size = 10_000_000
    for name in spec.get("hf_folders") or []:
        folder = _hub_dir() / name
        if not folder.is_dir():
            continue
        if any(folder.rglob("*.incomplete")):
            continue
        matches = list(folder.rglob(pattern))
        if any(path.stat().st_size > min_size for path in matches):
            return True
    return False


def cached_models() -> set[str]:
    return {item["id"] for item in MODEL_CATALOG if is_model_cached(item["id"])}


def best_cached_model(preferred: str) -> str:
    cached = cached_models()
    if preferred in cached:
        return preferred
    for item in MODEL_CATALOG:
        if item["id"] in cached:
            return item["id"]
    return "small"


_PROXY_ENV = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


@contextmanager
def huggingface_network():
    """Hugging Face через рабочий SOCKS, а не через мёртвый системный HTTP-прокси."""
    keys = _PROXY_ENV + ("HF_HUB_DISABLE_XET",)
    old = {key: os.environ.get(key) for key in keys}
    try:
        proxy = ""
        try:
            from socks_proxy import ensure_local_socks

            proxy = ensure_local_socks() or ""
        except Exception:
            proxy = ""
        if proxy.startswith("socks5://"):
            proxy = "socks5h://" + proxy[len("socks5://") :]
        if proxy:
            for key in _PROXY_ENV:
                os.environ[key] = proxy
        else:
            for key in _PROXY_ENV:
                os.environ.pop(key, None)
        os.environ["HF_HUB_DISABLE_XET"] = "1"
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def download_model(model_id: str) -> None:
    spec = get_model(model_id)
    repo = spec.get("repo")
    if not repo:
        raise RuntimeError(f"Для модели {model_id} не указан репозиторий")
    from huggingface_hub import snapshot_download

    kwargs = {"repo_id": repo}
    patterns = spec.get("allow_patterns")
    if patterns:
        kwargs["allow_patterns"] = patterns
    try:
        with huggingface_network():
            snapshot_download(**kwargs)
    except Exception as exc:
        text = str(exc)
        if "10061" in text or "ConnectError" in text:
            raise RuntimeError(
                "Нет связи с Hugging Face. Нужен локальный SOCKS 127.0.0.1:40000 "
                "(WARP proxy / wireproxy). Сейчас прокси не отвечает."
            ) from exc
        raise RuntimeError(text[:400]) from exc
