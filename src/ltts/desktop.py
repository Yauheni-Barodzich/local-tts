"""Windows: трей + встроенный сервер; браузер для UI; опционально одно окно аватара."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from .instance_lock import DESKTOP_PID, clear_pid, instance_running, write_pid
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


def _avatar_webview_enabled() -> bool:
    try:
        from .avatar_config import avatar_config

        return bool(avatar_config().get("enabled", True))
    except Exception:
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

    base = f"http://{host}:{port}"
    if instance_running(DESKTOP_PID):
        webbrowser.open(f"{base}/")
        print("ltts уже запущен — открыт интерфейс в браузере", file=sys.stderr)
        return 0

    _configure_stdio()

    try:
        import pystray
        from pystray import MenuItem as item
    except ImportError:
        print(f"ltts desktop: нужны pystray и Pillow.\n  {_desktop_install_hint()}", file=sys.stderr)
        return 1

    use_avatar_webview = _avatar_webview_enabled()
    if use_avatar_webview:
        try:
            import webview
        except ImportError:
            print(f"ltts desktop: для аватара нужен pywebview (extra desktop).\n  {_desktop_install_hint()}", file=sys.stderr)
            use_avatar_webview = False

    from .tray import _load_icon_image
    from .playback_hub import PlaybackHub, set_playback_hub

    playback_hub = PlaybackHub()
    set_playback_hub(playback_hub)
    server_handle: ServerHandle | None = None
    owned_server = False
    avatar_window = None
    icon_ref: list[pystray.Icon] = []
    shutting_down = threading.Event()
    server_ready = threading.Event()
    boot_lock = threading.Lock()
    boot_started = False
    bust = ""

    def page_url() -> str:
        from .desktop_setup import desktop_setup_complete
        from .web_assets import web_ui_query

        b = bust or web_ui_query()
        if desktop_setup_complete():
            return f"{base}/?{b}"
        return f"{base}/setup?{b}"

    def settings_url() -> str:
        from .web_assets import web_ui_query

        return f"{base}/settings?{web_ui_query()}"

    def _wait_server(seconds: float = 120) -> bool:
        return server_ready.wait(seconds)

    def _attach_avatar() -> None:
        from .avatar_config import avatar_config

        cfg = avatar_config()
        if not cfg.get("enabled", True):
            playback_hub.avatar.configure(f"{base}/avatar?{bust}", enabled=False, size=160)
            return
        playback_hub.avatar.configure(
            f"{base}/avatar?{bust}&always=1",
            enabled=True,
            size=int(cfg.get("size", 160)),
        )
        _log("bootstrap: аватар настроен")

    def _bootstrap_server() -> None:
        nonlocal server_handle, owned_server, bust
        _log("bootstrap: старт")
        try:
            from .web_assets import web_ui_query

            bust = web_ui_query()
            _log("bootstrap: uvicorn…")
            server_handle = start_server_background(host, port, log_level="warning", wait=True)
            owned_server = server_handle is not None
            _log("bootstrap: сервер готов")

            from .desktop_setup import needs_desktop_setup, start_minimal_setup_async

            if needs_desktop_setup():
                start_minimal_setup_async()

            _attach_avatar()
            server_ready.set()
            playback_hub.avatar.prime()
            if playback_hub.state.refcount > 0:
                playback_hub.avatar.sync_playing(True)
            _log("bootstrap: готово")
        except Exception as e:
            _log(f"bootstrap_server: {e!r}")
            server_ready.set()

    def _start_server_boot() -> None:
        nonlocal boot_started
        with boot_lock:
            if boot_started or shutting_down.is_set():
                return
            boot_started = True
        threading.Thread(target=_bootstrap_server, name="ltts-server-boot", daemon=True).start()

    def open_ui(_icon=None, _item=None) -> None:
        _start_server_boot()
        if _wait_server(120):
            webbrowser.open(page_url())

    def open_settings(_icon=None, _item=None) -> None:
        _start_server_boot()
        if _wait_server(120):
            webbrowser.open(settings_url())

    def stop_owned_server() -> None:
        nonlocal server_handle, owned_server
        if owned_server and server_handle:
            stop_server(server_handle)
            server_handle = None
            owned_server = False

    def quit_app(_icon=None, _item=None) -> None:
        shutting_down.set()
        playback_hub.shutdown()
        set_playback_hub(None)
        stop_owned_server()
        if icon_ref:
            try:
                icon_ref[0].stop()
            except Exception:
                pass

    def run_tray() -> None:
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except ImportError:
            pass
        try:
            image = _load_icon_image()
            menu = pystray.Menu(
                item("Открыть интерфейс", open_ui, default=True),
                item("Настройки", open_settings),
                pystray.Menu.SEPARATOR,
                item("Выход", quit_app),
            )
            tray_icon = pystray.Icon("ltts", image, "ltts — локальный TTS", menu)

            def _tray_setup(icon) -> None:
                playback_hub.attach_tray(icon)

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

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ltts.local.desktop")
        except Exception:
            pass

    try:
        from .app_icon import app_ico

        icon_path = str(app_ico())
    except (OSError, FileNotFoundError):
        icon_path = None

    try:
        write_pid(DESKTOP_PID)

        if use_avatar_webview:
            from .avatar_config import avatar_config

            from .avatar_window import AVATAR_ALWAYS_VISIBLE, corner_xy

            cfg = avatar_config()
            av_size = int(cfg.get("size", 160))
            av_h = av_size
            if AVATAR_ALWAYS_VISIBLE:
                ax, ay = corner_xy(av_size, av_h)
            else:
                ax, ay = -24000, -24000
            avatar_window = webview.create_window(
                "ltts-avatar",
                html="<!DOCTYPE html><html><body style='margin:0;background:transparent'></body></html>",
                width=av_size,
                height=av_h,
                x=ax,
                y=ay,
                hidden=not AVATAR_ALWAYS_VISIBLE,
                frameless=True,
                transparent=True,
                background_color="#FFFFFF",
                on_top=True,
                easy_drag=True,
                focus=False,
                resizable=False,
                shadow=False,
            )
            playback_hub.avatar.attach_window(avatar_window)
            bust_q = ""
            playback_hub.avatar.configure(
                f"{base}/avatar?{bust_q}always=1",
                enabled=bool(cfg.get("enabled", True)),
                size=av_size,
            )
            _start_server_boot()
            tray_thread = threading.Thread(target=run_tray, name="ltts-tray", daemon=True)
            tray_thread.start()
            webview.start(gui="edgechromium", icon=icon_path)
            tray_thread.join(timeout=3)
        else:
            _start_server_boot()
            run_tray()
    except Exception as e:
        _log(f"desktop error: {e!r}")
        print(f"ltts desktop: {e}", file=sys.stderr)
        quit_app()
        return 1
    finally:
        clear_pid(DESKTOP_PID)
        stop_owned_server()
        shutting_down.set()
        playback_hub.shutdown()
        set_playback_hub(None)
        if icon_ref:
            try:
                icon_ref[0].stop()
            except Exception:
                pass
    return 0
