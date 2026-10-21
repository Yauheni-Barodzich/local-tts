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

        transparent = Color.Transparent
        wv.DefaultBackgroundColor = transparent
        core = wv.CoreWebView2
        if core is not None:
            core.DefaultBackgroundColor = Color.FromArgb(0, 0, 0, 0)
    except Exception:
        pass


def apply_layered_colorkey(hwnd: int, *, rgb: int = 0xFFFFFF) -> None:
    """Белый фон окна → «дырка» без AllowTransparency (она уже поздно после Show)."""
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | 0x00080000)
    user32.SetLayeredWindowAttributes(hwnd, rgb, 0, 0x00000001)


def enable_avatar_transparency(form: Any) -> None:
    """Прозрачность после CoreWebView2; без AllowTransparency во время init."""
    if not _core_webview2_ready(form):
        return
    wv = form.webview
    _set_webview2_transparent_bg(wv)
    try:
        from System.Drawing import Color

        if not form.AllowTransparency:
            form.AllowTransparency = True
        form.BackColor = Color.Transparent
    except Exception:
        pass
    hwnd = _hwnd(form)
    if hwnd:
        apply_layered_colorkey(hwnd)


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
