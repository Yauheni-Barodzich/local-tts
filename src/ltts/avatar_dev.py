"""Dev: hot-reload avatar.html в webview + debug WebView2."""

from __future__ import annotations

import os
import threading
import time
from importlib.resources import as_file, files
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .webview_ui import run_on_ui

if TYPE_CHECKING:
    from .avatar_window import AvatarWindowController

_ENV = "LTTS_AVATAR_DEV"
_HTML_ENV = "LTTS_AVATAR_HTML"
_DEBUG_PORT_ENV = "LTTS_AVATAR_DEBUG_PORT"
_watch_stop: threading.Event | None = None
_default_debug_port = 9223


def prepare_pywebview_dev(*, log: Callable[[str], None] | None = None) -> int | None:
    """До create_window: DevTools без автo-open (иначе E_ABORT на прозрачном окне)."""
    import webview

    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    raw = os.environ.get(_DEBUG_PORT_ENV, "").strip()
    port: int | None = int(raw) if raw.isdigit() else None
    if port is not None:
        webview.settings["REMOTE_DEBUGGING_PORT"] = port
        if log:
            log(f"avatar-dev: remote debugging :{port} (edge://inspect)")
    elif log:
        log("avatar-dev: hot-reload avatar.html, DevTools — F12 или после загрузки")
    return port


def wait_core_webview2(window: Any, *, timeout: float = 25.0) -> bool:
    """shown у pywebview раньше CoreWebView2 — ждём перед load_url."""
    form = getattr(window, "native", None)
    if form is None:
        time.sleep(0.85)
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready = {"ok": False}

        def probe() -> None:
            wv = getattr(form, "webview", None)
            if wv is not None and wv.CoreWebView2 is not None:
                ready["ok"] = True

        run_on_ui(form, probe, block=True)
        if ready["ok"]:
            return True
        time.sleep(0.06)
    return False


def open_avatar_devtools(window: Any, *, log: Callable[[str], None] | None = None) -> bool:
    form = getattr(window, "native", None)
    if form is None:
        return False
    opened = {"ok": False}

    def _open() -> None:
        wv = getattr(form, "webview", None)
        if wv is None or wv.CoreWebView2 is None:
            return
        try:
            wv.CoreWebView2.OpenDevToolsWindow()
            opened["ok"] = True
        except Exception as e:
            if log:
                log(f"avatar-dev: OpenDevTools: {e!r}")

    run_on_ui(form, _open, block=True)
    if opened["ok"] and log:
        log("avatar-dev: окно DevTools открыто")
    return opened["ok"]


def schedule_avatar_devtools(
    window: Any,
    *,
    delay_s: float = 1.5,
    log: Callable[[str], None] | None = None,
) -> None:
    def _try() -> None:
        if open_avatar_devtools(window, log=log):
            return
        for wait in (0.8, 1.2):
            time.sleep(wait)
            if open_avatar_devtools(window, log=log):
                return
        if log:
            log("avatar-dev: DevTools не открылись — F12 или edge://inspect")

    threading.Timer(delay_s, _try).start()


def avatar_dev_enabled() -> bool:
    """True только если запуск через ltts-desktop-dev.bat (LTTS_AVATAR_DEV=1)."""
    v = os.environ.get(_ENV, "").strip().lower()
    return v in ("1", "true", "yes", "on")


def dev_avatar_html_body() -> str | None:
    if not avatar_dev_enabled():
        return None
    path = avatar_html_path()
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def avatar_html_path() -> Path | None:
    """Dev: LTTS_AVATAR_HTML или src в клоне; иначе файл из пакета ltts."""
    raw = os.environ.get(_HTML_ENV, "").strip()
    if raw:
        p = Path(raw)
        if p.is_file():
            return p
    if avatar_dev_enabled():
        here = Path(__file__).resolve().parent / "web" / "avatar.html"
        if here.is_file():
            return here
        cwd = Path.cwd() / "src" / "ltts" / "web" / "avatar.html"
        if cwd.is_file():
            return cwd
    ref = files("ltts") / "web" / "avatar.html"
    try:
        with as_file(ref) as path:
            return Path(path)
    except (TypeError, FileNotFoundError, OSError):
        return None


def bust_avatar_url(page_url: str) -> str:
    """Cache-bust для load_url после правок HTML."""
    parsed = urlparse(page_url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    q["_dev"] = str(int(time.time() * 1000))
    return urlunparse(parsed._replace(query=urlencode(q)))


def start_avatar_html_watch(
    controller: AvatarWindowController,
    *,
    poll_s: float = 0.45,
    log: Callable[[str], None] | None = None,
) -> threading.Event | None:
    """Следит за mtime avatar.html и перезагружает webview. None — не dev или нет файла."""
    global _watch_stop
    path = avatar_html_path()
    if path is None or not path.is_file():
        if log:
            log("avatar-dev: avatar.html не найден, watch выключен")
        return None

    stop = threading.Event()
    _watch_stop = stop

    def _loop() -> None:
        last_ns: int | None = None
        if log:
            log(f"avatar-dev: watch {path}")
        while not stop.wait(poll_s):
            try:
                ns = path.stat().st_mtime_ns
            except OSError:
                continue
            if last_ns is None:
                last_ns = ns
                continue
            if ns == last_ns:
                continue
            last_ns = ns
            base = controller.page_url
            if not base:
                continue
            url = bust_avatar_url(base)
            if log:
                log("avatar-dev: перезагрузка webview")
            controller.reload_page(url)

    threading.Thread(target=_loop, name="ltts-avatar-dev-watch", daemon=True).start()
    return stop


def stop_avatar_html_watch(stop: threading.Event | None) -> None:
    global _watch_stop
    if stop is not None:
        stop.set()
    if _watch_stop is stop:
        _watch_stop = None
