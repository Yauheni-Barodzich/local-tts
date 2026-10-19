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
