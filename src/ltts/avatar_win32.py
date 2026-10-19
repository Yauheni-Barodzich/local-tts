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


def tune_avatar_form(form: Any, owner: Any = None) -> None:
    try:
        form.ShowInTaskbar = False
    except Exception:
        pass
    if owner is not None:
        try:
            form.Owner = owner
        except Exception:
            pass
    hwnd = _hwnd(form)
    if hwnd:
        exclude_from_taskbar(hwnd)


def set_main_taskbar_visible(form: Any, visible: bool) -> None:
    try:
        form.ShowInTaskbar = bool(visible)
    except Exception:
        pass
