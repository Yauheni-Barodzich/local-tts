"""Позиция и show/hide окна аватара (pywebview, Windows)."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Any

from .avatar_config import avatar_config

_OFFSCREEN = -24000


def _work_area() -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


def corner_xy(width: int, height: int, margin: int = 12) -> tuple[int, int]:
    left, top, right, bottom = _work_area()
    x = right - width - margin
    y = bottom - height - margin
    return max(left, x), max(top, y)


class AvatarWindowController:
    """Show/hide только с потока pywebview API (JS → playback_delta)."""

    def __init__(self) -> None:
        self._win: Any = None
        self._lock = threading.Lock()
        self._visible = False
        self._page_url: str | None = None
        self._page_loaded = False

    def set_page_url(self, url: str) -> None:
        self._page_url = url

    def attach(self, window: Any) -> None:
        self._win = window
        try:
            window.move(_OFFSCREEN, _OFFSCREEN)
        except Exception:
            pass

    def sync_playing(self, on: bool) -> None:
        """Вызывать из DesktopJsApi (поток WebView), не из потока трея."""
        if on:
            self._show()
        else:
            self._hide()

    def _show(self) -> None:
        from .avatar_config import avatar_config as ac

        if not ac()["enabled"]:
            return
        win = self._win
        if win is None or self._visible:
            return
        try:
            if self._page_url and not self._page_loaded:
                win.load_url(self._page_url)
                self._page_loaded = True
            size = avatar_config()["size"]
            h = int(size * 1.15)
            x, y = corner_xy(size, h)
            win.resize(size, h)
            win.move(x, y)
            win.show()
            self._visible = True
        except Exception:
            pass

    def _hide(self) -> None:
        win = self._win
        if win is None or not self._visible:
            return
        try:
            win.hide()
            win.move(_OFFSCREEN, _OFFSCREEN)
            self._visible = False
        except Exception:
            pass

    def shutdown(self) -> None:
        win = self._win
        if win:
            try:
                win.destroy()
            except Exception:
                pass
        self._win = None
        self._visible = False
