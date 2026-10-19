"""Окно аватара: создаётся в bootstrap (не UI), показ — из daemon-потока через pywebview."""

from __future__ import annotations

import logging
import threading
from typing import Any

from .avatar_win32 import tune_avatar_form

_LOG = logging.getLogger(__name__)
_OFFSCREEN = -24000
_ui_lock = threading.Lock()


def corner_xy(width: int, height: int, margin: int = 12) -> tuple[int, int]:
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    x = rect.right - width - margin
    y = rect.bottom - height - margin
    return max(rect.left, x), max(rect.top, y)


class AvatarWindowController:
    def __init__(self) -> None:
        self._win: Any = None
        self._visible = False
        self._page_url: str | None = None
        self._page_loaded = False
        self._owner_native: Any = None
        self._enabled = False
        self._size = 160

    def configure(self, page_url: str, *, enabled: bool, size: int) -> None:
        self._page_url = page_url
        self._enabled = bool(enabled)
        self._size = int(size)

    def attach_window(self, window: Any) -> None:
        self._win = window
        self._tune()

    def set_owner_native(self, owner: Any) -> None:
        self._owner_native = owner
        self._tune()

    def attach(self, window: Any) -> None:
        """Устаревший путь: окно уже создано."""
        self.attach_window(window)

    def sync_playing(self, on: bool) -> None:
        if not self._enabled or self._win is None:
            return
        fn = self._show_worker if on else self._hide_worker
        threading.Thread(target=fn, name="ltts-avatar-ui", daemon=True).start()

    def _tune(self) -> None:
        native = getattr(self._win, "native", None) if self._win else None
        if native:
            tune_avatar_form(native, self._owner_native)

    def _show_worker(self) -> None:
        with _ui_lock:
            if self._visible or not self._win:
                return
            win = self._win
            try:
                if self._page_url and not self._page_loaded:
                    win.load_url(self._page_url)
                    self._page_loaded = True
                size = self._size
                h = int(size * 1.15)
                x, y = corner_xy(size, h)
                win.resize(size, h)
                win.move(x, y)
                win.show()
                self._visible = True
            except Exception as e:
                _LOG.warning("avatar show: %s", e)

    def _hide_worker(self) -> None:
        with _ui_lock:
            win = self._win
            if win is None or not self._visible:
                return
            try:
                win.hide()
                win.move(_OFFSCREEN, _OFFSCREEN)
                self._visible = False
            except Exception as e:
                _LOG.warning("avatar hide: %s", e)

    def shutdown(self) -> None:
        win = self._win
        self._win = None
        self._visible = False
        if win is None:
            return

        def _destroy() -> None:
            try:
                win.destroy()
            except Exception:
                pass

        threading.Thread(target=_destroy, name="ltts-avatar-close", daemon=True).start()
