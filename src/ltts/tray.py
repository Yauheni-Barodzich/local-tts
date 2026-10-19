"""Windows: иконка в трее — supervises `ltts serve` в дочерннем процессе."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser

from pathlib import Path

from .client import server_alive
from .paths import DEFAULT_HOST, DEFAULT_PORT

_TRAY_PID = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ltts" / "tray.pid"

def _tray_install_hint() -> str:
    lines = [
        'uv tool install --force "ПУТЬ\\К\\local-tts[tray]"',
        'uv pip install "ltts[tray]"',
        'pip install "ltts[tray]"',
    ]
    return "\n  ".join(lines)


def _serve_cmd(host: str, port: int) -> list[str]:
    ltts = shutil.which("ltts")
    if ltts:
        return [ltts, "serve", "--host", host, "--port", str(port)]
    return [sys.executable, "-m", "ltts.cli", "serve", "--host", host, "--port", str(port)]


def _load_icon_image():
    from PIL import Image

    from .app_icon import tray_image_path

    with tray_image_path().open("rb") as f:
        img = Image.open(f)
        img.load()
        return img.convert("RGBA")


def _tray_log(msg: str) -> None:
    try:
        _TRAY_PID.parent.mkdir(parents=True, exist_ok=True)
        with (_TRAY_PID.parent / "tray.log").open("a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except OSError:
        pass


def _tray_already_running() -> bool:
    if not _TRAY_PID.is_file():
        return False
    try:
        pid = int(_TRAY_PID.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            _clear_tray_pid()
            return False
        code = ctypes.c_ulong()
        alive = False
        if ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)):
            alive = code.value == STILL_ACTIVE
        ctypes.windll.kernel32.CloseHandle(h)
        if not alive:
            _clear_tray_pid()
        return alive
    _clear_tray_pid()
    return False


def _write_tray_pid() -> None:
    _TRAY_PID.parent.mkdir(parents=True, exist_ok=True)
    _TRAY_PID.write_text(str(os.getpid()), encoding="utf-8")


def _clear_tray_pid() -> None:
    _TRAY_PID.unlink(missing_ok=True)


def run_tray(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    if os.name != "nt":
        print("ltts tray: только Windows", file=sys.stderr)
        return 1
    if _tray_already_running():
        print("ltts tray: уже запущен (см. иконку у часов)", file=sys.stderr)
        return 0
    if not sys.stderr or not getattr(sys.stderr, "isatty", lambda: False)():
        # pythonw: ошибки в tray.log
        log_path = _TRAY_PID.parent / "tray.log"
        try:
            sys.stderr = open(log_path, "a", encoding="utf-8")
        except OSError:
            pass
    try:
        import pystray
        from pystray import MenuItem as item
    except ImportError:
        print(f"ltts tray: нужны pystray и Pillow (extra tray).\n  {_tray_install_hint()}", file=sys.stderr)
        return 1
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print(f"ltts tray: нужен Pillow (extra tray).\n  {_tray_install_hint()}", file=sys.stderr)
        return 1

    url = f"http://{host}:{port}"
    proc: subprocess.Popen | None = None
    owned = False
    icon_ref: list[pystray.Icon] = []

    def stop_serve(_icon=None, _item=None) -> None:
        nonlocal proc, owned
        if not owned or not proc or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        proc = None
        owned = False

    def start_serve() -> None:
        nonlocal proc, owned
        if server_alive(url, timeout=0.5):
            return
        if proc and proc.poll() is None:
            return
        proc = subprocess.Popen(_serve_cmd(host, port))
        owned = True

    def wait_server(seconds: float = 90) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if server_alive(url, timeout=0.5):
                return True
            if owned and proc and proc.poll() is not None:
                return False
            time.sleep(0.4)
        return server_alive(url, timeout=1)

    def open_ui(_icon=None, _item=None) -> None:
        if not server_alive(url, timeout=0.5):
            start_serve()
            if not wait_server(120):
                print("ltts tray: сервер не запустился", file=sys.stderr)
                return
        webbrowser.open(url)

    def quit_app(_icon=None, _item=None) -> None:
        stop_serve()
        if icon_ref:
            icon_ref[0].stop()

    start_serve()
    if owned and not wait_server(120):
        print("ltts tray: не дождался ответа сервера", file=sys.stderr)
        stop_serve()
        return 1

    try:
        image = _load_icon_image()
    except Exception as e:
        print(f"ltts tray: иконка: {e}", file=sys.stderr)
        stop_serve()
        return 1

    menu = pystray.Menu(
        item("Открыть интерфейс", open_ui, default=True),
        item("Остановить сервер", stop_serve),
        pystray.Menu.SEPARATOR,
        item("Выход", quit_app),
    )
    icon = pystray.Icon("ltts", image, "ltts — локальный TTS", menu)
    icon_ref.append(icon)

    try:
        _write_tray_pid()
        icon.run()
    except Exception as e:
        _tray_log(f"tray error: {e!r}")
        print(f"ltts tray: {e}", file=sys.stderr)
        return 1
    finally:
        _clear_tray_pid()
        stop_serve()
    return 0
