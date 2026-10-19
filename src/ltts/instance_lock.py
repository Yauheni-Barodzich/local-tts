"""Один экземпляр desktop/tray (Windows)."""

from __future__ import annotations

import os
from pathlib import Path

from .paths import HOME

DESKTOP_PID = HOME / "desktop.pid"
TRAY_PID = HOME / "tray.pid"


def _process_alive(pid: int) -> bool:
    if os.name != "nt":
        return False
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    alive = False
    if ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)):
        alive = code.value == STILL_ACTIVE
    ctypes.windll.kernel32.CloseHandle(h)
    return alive


def _read_pid(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def instance_running(path: Path) -> bool:
    pid = _read_pid(path)
    if pid is None:
        return False
    if not _process_alive(pid):
        path.unlink(missing_ok=True)
        return False
    return True


def write_pid(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")


def clear_pid(path: Path) -> None:
    path.unlink(missing_ok=True)
