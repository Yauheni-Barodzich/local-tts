"""Windows: трей + WebView2 + встроенный HTTP-сервер."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from .desktop_setup import desktop_setup_complete, needs_desktop_setup, start_minimal_setup_async
from .instance_lock import DESKTOP_PID, clear_pid, instance_running, write_pid
from .paths import DEFAULT_HOST, DEFAULT_PORT
from .serve_runtime import ServerHandle, start_server_background, stop_server

_LOG = DESKTOP_PID.parent / "desktop.log"


def _desktop_install_hint() -> str:
    return 'uv pip install "ltts[desktop]"  или  uv tool install "ПУТЬ\\local-tts[desktop]"'


def _log(msg: str) -> None:
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with _LOG.open("a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except OSError:
        pass


def _configure_stdio() -> None:
    if not sys.stderr or not getattr(sys.stderr, "isatty", lambda: False)():
        try:
            sys.stderr = open(_LOG, "a", encoding="utf-8")
        except OSError:
            pass


def _has_console_window() -> bool:
    if os.name != "nt":
        return False
    import ctypes

    return bool(ctypes.windll.kernel32.GetConsoleWindow())


def _desktop_worker() -> bool:
    return os.environ.get("LTTS_DESKTOP_WORKER") == "1"


def _build_desktop_argv(host: str, port: int, start_minimized: bool, attach_console: bool) -> list[str]:
    args = ["desktop", "--host", host, "--port", str(port)]
    if start_minimized:
        args.append("--start-minimized")
    if attach_console:
        args.append("--attach-console")
    return args


def _respawn_detached(host: str, port: int, start_minimized: bool) -> bool:
    """Запуск без консоли (pythonw / CREATE_NO_WINDOW). True — текущий процесс можно завершить."""
    if os.name != "nt" or _desktop_worker() or not _has_console_window():
        return False

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    env = {**os.environ, "LTTS_DESKTOP_WORKER": "1"}
    cli_args = _build_desktop_argv(host, port, start_minimized, attach_console=False)

    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        cmd = [str(exe), *cli_args[1:]]
    elif exe.name.lower() == "pythonw.exe":
        return False
    else:
        pyw = exe.with_name("pythonw.exe")
        if pyw.is_file():
            cmd = [str(pyw), "-m", "ltts.cli", *cli_args[1:]]
        else:
            ltts = shutil.which("ltts")
            cmd = [ltts, *cli_args[1:]] if ltts else [str(exe), "-m", "ltts.cli", *cli_args[1:]]

    subprocess.Popen(cmd, creationflags=create_no_window, env=env, cwd=os.getcwd(), close_fds=True)
    return True


def run_desktop(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    start_minimized: bool = False,
    attach_console: bool = False,
) -> int:
    if os.name != "nt":
        print("ltts desktop: только Windows", file=sys.stderr)
        return 1
    if not attach_console and _respawn_detached(host, port, start_minimized):
        return 0
    if instance_running(DESKTOP_PID):
        print("ltts desktop: уже запущен (иконка у часов)", file=sys.stderr)
        return 0

    _configure_stdio()

    try:
        import webview
    except ImportError:
        print(f"ltts desktop: нужен pywebview (extra desktop).\n  {_desktop_install_hint()}", file=sys.stderr)
        return 1

    try:
        import pystray
        from pystray import MenuItem as item
    except ImportError:
        print(f"ltts desktop: нужны pystray и Pillow.\n  {_desktop_install_hint()}", file=sys.stderr)
        return 1

    from .tray import _load_icon_image

    url = f"http://{host}:{port}"
    server_handle: ServerHandle | None = None
    owned_server = False
    window = None
    icon_ref: list[pystray.Icon] = []
    lock = threading.Lock()

    try:
        server_handle = start_server_background(host, port, log_level="warning")
        owned_server = server_handle is not None
    except Exception as e:
        print(f"ltts desktop: {e}", file=sys.stderr)
        return 1

    if needs_desktop_setup():
        start_minimal_setup_async()
        initial = f"{url}/setup"
    else:
        initial = url

    def open_main(_icon=None, _item=None) -> None:
        with lock:
            w = window
        if w is None:
            return
        try:
            w.load_url(url if desktop_setup_complete() else f"{url}/setup")
            w.show()
        except Exception as e:
            _log(f"open_main: {e!r}")

    def stop_owned_server() -> None:
        nonlocal server_handle, owned_server
        if owned_server and server_handle:
            stop_server(server_handle)
            server_handle = None
            owned_server = False

    def quit_app(_icon=None, _item=None) -> None:
        stop_owned_server()
        with lock:
            w = window
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass
        if icon_ref:
            icon_ref[0].stop()

    def run_tray() -> None:
        try:
            image = _load_icon_image()
        except Exception as e:
            _log(f"tray icon: {e!r}")
            return
        menu = pystray.Menu(
            item("Открыть ltts", open_main, default=True),
            pystray.Menu.SEPARATOR,
            item("Выход", quit_app),
        )
        icon = pystray.Icon("ltts", image, "ltts — локальный TTS", menu)
        icon_ref.append(icon)
        icon.run()

    tray_thread = threading.Thread(target=run_tray, name="ltts-tray", daemon=True)
    tray_thread.start()

    def on_closing():
        with lock:
            w = window
        if w is not None:
            try:
                w.hide()
            except Exception:
                pass
        return False

    try:
        write_pid(DESKTOP_PID)
        window = webview.create_window(
            "ltts",
            initial,
            width=1000,
            height=720,
            hidden=start_minimized,
        )
        window.events.closing += on_closing
        try:
            from .app_icon import app_ico

            icon = str(app_ico())
        except (OSError, FileNotFoundError):
            icon = None
        if os.name == "nt":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ltts.local.desktop")
            except Exception:
                pass
        webview.start(gui="edgechromium", icon=icon)
    except Exception as e:
        _log(f"desktop error: {e!r}")
        print(f"ltts desktop: {e}", file=sys.stderr)
        quit_app()
        return 1
    finally:
        clear_pid(DESKTOP_PID)
        stop_owned_server()
    return 0
