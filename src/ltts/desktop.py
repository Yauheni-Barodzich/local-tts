"""Windows: трей + WebView2 + встроенный HTTP-сервер."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from .desktop_setup import desktop_setup_complete, needs_desktop_setup, start_minimal_setup_async
from .instance_lock import DESKTOP_PID, clear_pid, focus_desktop_window, instance_running, write_pid
from .paths import DEFAULT_HOST, DEFAULT_PORT
from .serve_runtime import ServerHandle, start_server_background, stop_server

_LOG = DESKTOP_PID.parent / "desktop.log"


def _desktop_install_hint() -> str:
    return 'uv pip install "ltts[desktop]"  или  uv tool install "ПУТЬ\\local-tts[desktop]"'


def _log(msg: str) -> None:
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with (_LOG.open("a", encoding="utf-8")) as f:
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
        if focus_desktop_window():
            print("ltts: окно выведено на передний план", file=sys.stderr)
        else:
            print(
                "ltts уже запущен — иконка у часов. Перезапуск: ltts-tray.bat force",
                file=sys.stderr,
            )
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
    from .tray_playback import DesktopJsApi, TrayPlaybackAnimator

    from .web_assets import web_ui_query

    base = f"http://{host}:{port}"
    bust = web_ui_query()
    url = f"{base}/?{bust}"
    tray_animator = TrayPlaybackAnimator()
    js_api = DesktopJsApi(tray_animator)
    server_handle: ServerHandle | None = None
    owned_server = False
    window = None
    icon_ref: list[pystray.Icon] = []
    shutting_down = threading.Event()

    try:
        server_handle = start_server_background(host, port, log_level="warning")
        owned_server = server_handle is not None
    except Exception as e:
        print(f"ltts desktop: {e}", file=sys.stderr)
        return 1

    if needs_desktop_setup():
        start_minimal_setup_async()
        initial = f"{base}/setup?{bust}"
    else:
        initial = url

    def page_url() -> str:
        if desktop_setup_complete():
            return url
        return f"{base}/setup?{bust}"

    def show_window() -> None:
        nonlocal window
        if window is None:
            return
        try:
            window.load_url(page_url())
            window.show()
            focus_desktop_window()
        except Exception as e:
            _log(f"show_window: {e!r}")
            try:
                webbrowser.open(page_url())
            except Exception:
                pass

    def stop_owned_server() -> None:
        nonlocal server_handle, owned_server
        if owned_server and server_handle:
            stop_server(server_handle)
            server_handle = None
            owned_server = False

    def quit_app(_icon=None, _item=None) -> None:
        shutting_down.set()
        tray_animator.shutdown()
        stop_owned_server()
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass
        if icon_ref:
            try:
                icon_ref[0].stop()
            except Exception:
                pass

    def on_closing():
        if window is not None and not shutting_down.is_set():
            try:
                window.hide()
            except Exception:
                pass
            return False
        return True

    def run_tray() -> None:
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except ImportError:
            pass
        try:
            image = _load_icon_image()
            menu = pystray.Menu(
                item("Открыть ltts", lambda *a: show_window(), default=True),
                pystray.Menu.SEPARATOR,
                item("Выход", quit_app),
            )
            tray_icon = pystray.Icon("ltts", image, "ltts — локальный TTS", menu)

            def _tray_setup(icon) -> None:
                tray_animator.attach(icon)

            icon_ref.append(tray_icon)
            tray_icon.run(setup=_tray_setup)
        except Exception as e:
            _log(f"tray error: {e!r}")
        finally:
            try:
                import pythoncom

                pythoncom.CoUninitialize()
            except Exception:
                pass

    tray_thread = threading.Thread(target=run_tray, name="ltts-tray", daemon=True)
    tray_thread.start()

    try:
        from .app_icon import app_ico

        icon_path = str(app_ico())
    except (OSError, FileNotFoundError):
        icon_path = None

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ltts.local.desktop")
        except Exception:
            pass

    try:
        write_pid(DESKTOP_PID)
        window = webview.create_window(
            "ltts",
            initial,
            width=1000,
            height=720,
            hidden=start_minimized,
            js_api=js_api,
        )
        window.events.closing += on_closing
        # pywebview — только главный поток
        webview.start(gui="edgechromium", icon=icon_path)
    except Exception as e:
        _log(f"webview error: {e!r}")
        print(f"ltts desktop: {e}", file=sys.stderr)
        quit_app()
        return 1
    finally:
        clear_pid(DESKTOP_PID)
        stop_owned_server()
        shutting_down.set()
        tray_animator.shutdown()
        if icon_ref:
            try:
                icon_ref[0].stop()
            except Exception:
                pass
        tray_thread.join(timeout=3)
    return 0
