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


def default_avatar_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "size": DEFAULT_SIZE,
        "mode": "auto",  # auto | image | rig
    }


def avatar_config() -> dict[str, Any]:
    cfg = load_config()
    av = cfg.get("avatar")
    if not isinstance(av, dict):
        av = {}
    out = {**default_avatar_config(), **av}
    out["enabled"] = bool(out.get("enabled", True))
    out["size"] = max(80, min(400, int(out.get("size", DEFAULT_SIZE))))
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
