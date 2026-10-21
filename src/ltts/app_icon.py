"""Пути к иконкам приложения (desktop, трей, установщик)."""

from __future__ import annotations

from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"


def app_ico() -> Path:
    for name in ("app.ico", "tray.ico"):
        p = _ASSETS / name
        if p.is_file():
            return p
    raise FileNotFoundError("app.ico not found in ltts/assets")


def tray_image_path() -> Path:
    for name in ("app.png", "tray.png", "app.ico", "tray.ico"):
        p = _ASSETS / name
        if p.is_file():
            return p
    raise FileNotFoundError("tray icon not found in ltts/assets")


def default_avatar_image_path() -> Path:
    p = _ASSETS / "avatar-default.png"
    if p.is_file():
        return p
    return tray_image_path()


def load_tray_icon_image():
    from PIL import Image

    with tray_image_path().open("rb") as f:
        img = Image.open(f)
        img.load()
        return img.convert("RGBA")
