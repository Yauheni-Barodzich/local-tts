"""Один экземпляр desktop/tray (Windows)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .paths import HOME

DESKTOP_PID = HOME / "desktop.pid"
TRAY_PID = HOME / "tray.pid"

_DESKTOP_CMD = re.compile(r"ltts(\.cli)?\s+desktop|ltts-desktop|entry_desktop", re.I)


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


def _process_command_line(pid: int) -> str:
    if os.name != "nt":
        return ""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' -EA 0).CommandLine",
            ],
            capture_output=True,
            text=True,
            creationflags=flags,
            timeout=8,
        )
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def is_desktop_process(pid: int) -> bool:
    if not _process_alive(pid):
        return False
    cmd = _process_command_line(pid)
    if cmd and not _DESKTOP_CMD.search(cmd):
        return False
    if not cmd:
        from .client import server_alive

        return server_alive(timeout=0.5)
    return True


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
    if path == DESKTOP_PID and not is_desktop_process(pid):
        path.unlink(missing_ok=True)
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


def focus_desktop_window(title: str = "ltts") -> bool:
    """Вывести окно ltts на передний план (повторный запуск)."""
    if os.name != "nt":
        return False
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True
