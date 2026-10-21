"""Патчи pywebview/WebView2: chroma-key фон окна ltts-avatar + drag."""

from __future__ import annotations

import os
from typing import Any

from .avatar_win32 import (
    CHROMA_HEX,
    CHROMA_RGB,
    clear_dwm_backdrop,
    inject_page_chroma_background,
    set_webview2_chroma_background,
    tune_avatar_form,
)

_patched = False


def ensure_webview2_chroma_env() -> None:
    """AARRGGBB opaque chroma для WebView2 environment (до первого runtime)."""
    r, g, b = CHROMA_RGB
    env = f"FF{r:02X}{g:02X}{b:02X}"
    os.environ["WEBVIEW2_DEFAULT_BACKGROUND_COLOR"] = env


def apply_avatar_webview_patches() -> None:
    global _patched
    if _patched:
        return
    _patched = True
    ensure_webview2_chroma_env()
    _patch_browser_form_theme()
    _patch_edge_webview_ready()
    _patch_edge_navigation_completed()


def _is_avatar_window(window: Any) -> bool:
    return getattr(window, "title", "") == "ltts-avatar"


def _patch_browser_form_theme() -> None:
    try:
        from webview.platforms import winforms
    except ImportError:
        return

    BrowserForm = winforms.BrowserView.BrowserForm
    original = BrowserForm.update_title_bar_theme

    def update_title_bar_theme(self: Any) -> None:
        if _is_avatar_window(self.pywebview_window):
            try:
                from .avatar_win32 import _hwnd

                hwnd = _hwnd(self)
                if hwnd:
                    clear_dwm_backdrop(hwnd)
            except Exception:
                pass
            return
        original(self)

    BrowserForm.update_title_bar_theme = update_title_bar_theme  # type: ignore[method-assign]


def _patch_edge_webview_ready() -> None:
    try:
        from webview.platforms import edgechromium
    except ImportError:
        return

    EdgeChrome = edgechromium.EdgeChrome
    original = EdgeChrome.on_webview_ready

    def on_webview_ready(self: Any, sender: Any, args: Any) -> None:
        if args.IsSuccess and _is_avatar_window(self.pywebview_window):
            set_webview2_chroma_background(self.webview)
        original(self, sender, args)
        if args.IsSuccess and _is_avatar_window(self.pywebview_window):
            inject_page_chroma_background(self.webview)
            tune_avatar_form(self.form, transparency=True)

    EdgeChrome.on_webview_ready = on_webview_ready  # type: ignore[method-assign]


def _patch_edge_navigation_completed() -> None:
    try:
        from webview.platforms import edgechromium
    except ImportError:
        return

    EdgeChrome = edgechromium.EdgeChrome
    original = EdgeChrome.on_navigation_completed

    def on_navigation_completed(self: Any, sender: Any, args: Any) -> None:
        original(self, sender, args)
        if _is_avatar_window(self.pywebview_window):
            set_webview2_chroma_background(self.webview)
            inject_page_chroma_background(self.webview)

    EdgeChrome.on_navigation_completed = on_navigation_completed  # type: ignore[method-assign]


def bind_avatar_before_show(window: Any) -> None:
    def _on_before_show() -> None:
        form = getattr(window, "native", None)
        if form is None or not _is_avatar_window(window):
            return
        try:
            from .avatar_win32 import _hwnd

            hwnd = _hwnd(form)
            if hwnd:
                clear_dwm_backdrop(hwnd)
        except Exception:
            pass

    window.events.before_show += _on_before_show
