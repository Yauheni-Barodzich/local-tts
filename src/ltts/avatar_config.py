"""Настройки и пути персонажа у трея."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import load_config, save_config
from .paths import HOME

AVATAR_DIR = HOME / "avatar"
AVATAR_IMAGE = HOME / "avatar.png"
AVATAR_RIG_JSON = AVATAR_DIR / "rig.json"
DEFAULT_SIZE = 160
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DEFAULT_CHROMA_HEX = "#010102"
DEFAULT_CHROMA_TOLERANCE = 16


def default_layout() -> dict[str, Any]:
    return {
        "fit": "cover",
        "scale": 1.0,
        "offset_x": 0,
        "offset_y": 0,
        "chroma_enabled": False,
        "chroma_color": DEFAULT_CHROMA_HEX,
        "chroma_tolerance": DEFAULT_CHROMA_TOLERANCE,
    }


def _normalize_hex_color(raw: Any) -> str:
    s = str(raw or DEFAULT_CHROMA_HEX).strip()
    if not s.startswith("#"):
        s = "#" + s
    if len(s) == 4:
        s = "#" + "".join(c * 2 for c in s[1:])
    if len(s) != 7:
        return DEFAULT_CHROMA_HEX
    try:
        int(s[1:], 16)
    except ValueError:
        return DEFAULT_CHROMA_HEX
    return s.lower()


def parse_chroma_rgb(hex_color: str) -> tuple[int, int, int]:
    h = _normalize_hex_color(hex_color)
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def effective_page_chroma_hex(layout: dict[str, Any] | None = None) -> str:
    """Фон WebView/страницы — всегда служебный, не цвет ключа из картинки."""
    return DEFAULT_CHROMA_HEX


def chroma_key_rgb(layout: dict[str, Any] | None = None) -> tuple[int, int, int]:
    if layout is None:
        layout = avatar_config().get("layout") or {}
    return parse_chroma_rgb(_normalize_hex_color(layout.get("chroma_color")))


def chroma_from_layout(layout: dict[str, Any] | None = None) -> dict[str, Any]:
    """Параметры вырезки окна Win32 (фон страницы + опционально ключ из layout)."""
    if layout is None:
        layout = avatar_config().get("layout") or {}
    enabled = bool(layout.get("chroma_enabled"))
    page_rgb = parse_chroma_rgb(DEFAULT_CHROMA_HEX)
    try:
        tol = int(layout.get("chroma_tolerance", DEFAULT_CHROMA_TOLERANCE))
    except (TypeError, ValueError):
        tol = DEFAULT_CHROMA_TOLERANCE
    tol = max(0, min(64, tol))
    key_rgb = chroma_key_rgb(layout)
    if not enabled:
        return {
            "enabled": False,
            "hex": DEFAULT_CHROMA_HEX,
            "rgb": page_rgb,
            "key_rgb": key_rgb,
            "tolerance": DEFAULT_CHROMA_TOLERANCE,
        }
    return {
        "enabled": True,
        "hex": DEFAULT_CHROMA_HEX,
        "rgb": page_rgb,
        "key_rgb": key_rgb,
        "tolerance": tol,
    }


def normalize_layout(raw: Any) -> dict[str, Any]:
    base = default_layout()
    if not isinstance(raw, dict):
        return base
    fit = str(raw.get("fit", base["fit"])).lower()
    if fit not in ("contain", "cover"):
        fit = base["fit"]
    try:
        scale = float(raw.get("scale", base["scale"]))
    except (TypeError, ValueError):
        scale = base["scale"]
    scale = max(0.25, min(3.0, scale))
    try:
        offset_x = int(raw.get("offset_x", base["offset_x"]))
        offset_y = int(raw.get("offset_y", base["offset_y"]))
    except (TypeError, ValueError):
        offset_x, offset_y = base["offset_x"], base["offset_y"]
    offset_x = max(-200, min(200, offset_x))
    offset_y = max(-200, min(200, offset_y))
    chroma_enabled = bool(raw.get("chroma_enabled", base["chroma_enabled"]))
    chroma_color = _normalize_hex_color(raw.get("chroma_color", base["chroma_color"]))
    try:
        chroma_tolerance = int(raw.get("chroma_tolerance", base["chroma_tolerance"]))
    except (TypeError, ValueError):
        chroma_tolerance = base["chroma_tolerance"]
    chroma_tolerance = max(0, min(64, chroma_tolerance))
    return {
        "fit": fit,
        "scale": scale,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "chroma_enabled": chroma_enabled,
        "chroma_color": chroma_color,
        "chroma_tolerance": chroma_tolerance,
    }


def default_avatar_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "size": DEFAULT_SIZE,
        "mode": "auto",  # auto | image | rig
        "layout": default_layout(),
    }


def avatar_config() -> dict[str, Any]:
    cfg = load_config()
    av = cfg.get("avatar")
    if not isinstance(av, dict):
        av = {}
    out = {**default_avatar_config(), **av}
    out["enabled"] = bool(out.get("enabled", True))
    out["size"] = max(80, min(400, int(out.get("size", DEFAULT_SIZE))))
    out["layout"] = normalize_layout(out.get("layout"))
    return out


def save_avatar_config(patch: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    av = cfg.setdefault("avatar", default_avatar_config())
    if not isinstance(av, dict):
        av = default_avatar_config()
        cfg["avatar"] = av
    if "enabled" in patch:
        av["enabled"] = bool(patch["enabled"])
    if "size" in patch and patch["size"] is not None:
        av["size"] = max(80, min(400, int(patch["size"])))
    if "mode" in patch and patch["mode"]:
        av["mode"] = str(patch["mode"])
    if "layout" in patch:
        cur = av.get("layout") if isinstance(av.get("layout"), dict) else {}
        merged = {**cur, **patch["layout"]} if isinstance(patch["layout"], dict) else patch["layout"]
        av["layout"] = normalize_layout(merged)
    save_config(cfg)
    return avatar_config()


def rig_active() -> bool:
    return AVATAR_RIG_JSON.is_file() and (AVATAR_DIR / "base.png").is_file()


def effective_mode() -> str:
    av = avatar_config()
    mode = av.get("mode", "auto")
    if mode == "rig":
        return "rig" if rig_active() else "image"
    if mode == "image":
        return "image"
    if rig_active():
        return "rig"
    if AVATAR_IMAGE.is_file():
        return "image"
    return "bundled"


def avatar_public_config() -> dict[str, Any]:
    av = avatar_config()
    mode = effective_mode()
    return {
        **av,
        "mode": mode,
        "has_image": AVATAR_IMAGE.is_file(),
        "has_rig": rig_active(),
        "rig_url": "/api/avatar/rig/manifest" if rig_active() else None,
        "image_url": "/api/avatar/image" if AVATAR_IMAGE.is_file() or mode == "bundled" else None,
        "bundled_url": "/assets/avatar-default.png",
    }
