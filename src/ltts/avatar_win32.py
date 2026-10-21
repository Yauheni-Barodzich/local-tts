"""Win32: окно аватара без кнопки на панели задач."""

from __future__ import annotations

import ctypes
from typing import Any

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000


def _hwnd(form: Any) -> int | None:
    try:
        return int(form.Handle.ToInt32())
    except Exception:
        return None


def exclude_from_taskbar(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)


def _core_webview2_ready(form: Any) -> bool:
    wv = getattr(form, "webview", None)
    return wv is not None and wv.CoreWebView2 is not None


def _set_webview2_transparent_bg(wv: Any) -> None:
    try:
        from System.Drawing import Color

        wv.DefaultBackgroundColor = Color.Transparent
        core = wv.CoreWebView2
        if core is None:
            return
        try:
            from Microsoft.Web.WebView2.Core import CoreWebView2Color

            c = CoreWebView2Color()
            c.A = 0
            c.R = 0
            c.G = 0
            c.B = 0
            core.DefaultBackgroundColor = c
        except Exception:
            core.DefaultBackgroundColor = Color.FromArgb(0, 0, 0, 0)
    except Exception:
        pass


def enable_avatar_transparency(form: Any) -> None:
    """Прозрачность после CoreWebView2. Без WS_EX_LAYERED — иначе клики проходят сквозь окно."""
    if not _core_webview2_ready(form):
        return
    wv = form.webview
    _set_webview2_transparent_bg(wv)
    try:
        from System.Drawing import Color

        form.AllowTransparency = True
        form.BackColor = Color.Transparent
    except Exception:
        pass


def tune_avatar_form(form: Any, owner: Any = None, *, transparency: bool = True) -> None:
    try:
        form.ShowInTaskbar = False
    except Exception:
        pass
    if owner is not None:
        try:
            form.Owner = owner
        except Exception:
            pass
    if transparency:
        enable_avatar_transparency(form)
    hwnd = _hwnd(form)
    if hwnd:
        exclude_from_taskbar(hwnd)


def set_main_taskbar_visible(form: Any, visible: bool) -> None:
    try:
        form.ShowInTaskbar = bool(visible)
    except Exception:
        pass
