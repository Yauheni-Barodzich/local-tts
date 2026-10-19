"""Окно аватара: pywebview сам маршалит show/load_url; native не трогаем вне UI."""

from __future__ import annotations

import logging
import threading
from typing import Any

from .avatar_win32 import exclude_from_taskbar, tune_avatar_form
from .webview_ui import run_on_ui

_LOG = logging.getLogger(__name__)
_OFFSCREEN = -24000
_ui_lock = threading.Lock()
# Пока тестируем: не убирать окно после озвучки, показать после prime.
AVATAR_ALWAYS_VISIBLE = True


def _alog(msg: str) -> None:
    _LOG.warning("%s", msg)
    try:
        from .paths import HOME

        with (HOME / "desktop.log").open("a", encoding="utf-8") as f:
            f.write(f"avatar: {msg}\n")
    except OSError:
        pass


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
        window.events.before_show += self._on_before_show

    def _on_before_show(self) -> None:
        self._tune_hwnd()

    def set_owner_native(self, owner: Any) -> None:
        self._owner_native = owner

    def attach(self, window: Any) -> None:
        self.attach_window(window)

    def prime(self) -> None:
        """Один load_url после старта GUI, не во время play."""
        win = self._win
        if not win or not self._enabled or not self._page_url or self._page_loaded:
            return
        if not win.events.shown.wait(60):
            _alog("prime: timeout shown")
            return
        try:
            win.load_url(self._page_url)
            self._page_loaded = True
            self._tune_hwnd()
            threading.Timer(0.35, self._tune_hwnd).start()
            _alog("prime: страница загружена")
            if AVATAR_ALWAYS_VISIBLE:
                threading.Thread(target=self._show_worker, name="ltts-avatar-ui", daemon=True).start()
        except Exception as e:
            _alog(f"prime: {e!r}")

    def sync_playing(self, on: bool) -> None:
        if not self._enabled:
            _alog("sync_playing: disabled")
            return
        if self._win is None:
            _alog("sync_playing: нет окна")
            return
        if not on and AVATAR_ALWAYS_VISIBLE:
            return
        target = self._show_worker if on else self._park_worker
        threading.Thread(target=target, name="ltts-avatar-ui", daemon=True).start()

    def _tune_hwnd(self) -> None:
        import ctypes

        win = self._win
        form = getattr(win, "native", None) if win else None

        def _on_ui() -> None:
            if form is not None:
                tune_avatar_form(form, self._owner_native)
            else:
                hwnd = ctypes.windll.user32.FindWindowW(None, "ltts-avatar")
                if hwnd:
                    exclude_from_taskbar(hwnd)

        if form is not None:
            run_on_ui(form, _on_ui, block=False)
        else:
            _on_ui()

    def _show_worker(self) -> None:
        win = self._win
        if not win:
            return
        if not win.events.shown.wait(60):
            _alog("show: timeout shown")
            return
        with _ui_lock:
            try:
                size = self._size
                h = size
                x, y = corner_xy(size, h)
                win.resize(size, h)
                win.move(x, y)
                win.show()
                self._tune_hwnd()
                self._visible = True
                _alog(f"show: {x},{y}")
            except Exception as e:
                _alog(f"show: {e!r}")

    def _park_worker(self) -> None:
        if AVATAR_ALWAYS_VISIBLE:
            return
        win = self._win
        if win is None:
            return
        if not win.events.shown.wait(5):
            return
        with _ui_lock:
            try:
                win.move(_OFFSCREEN, _OFFSCREEN)
                self._visible = False
                _alog("park: offscreen")
            except Exception as e:
                self._visible = False
                _alog(f"park: {e!r}")

    def shutdown(self) -> None:
        win = self._win
        self._win = None
        self._visible = False
        if win is None:
            return

        def _close() -> None:
            try:
                win.destroy()
            except Exception:
                pass

        threading.Thread(target=_close, name="ltts-avatar-close", daemon=True).start()
