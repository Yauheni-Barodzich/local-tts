"""Запуск uvicorn: в foreground (CLI serve) и в фоне (desktop)."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .client import server_alive


@dataclass
class ServerHandle:
    """Сервер, запущенный этим процессом."""

    thread: threading.Thread
    server: object
    host: str
    port: int

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


def ensure_port_available(host: str, port: int) -> None:
    with socket.socket() as sock:
        try:
            sock.bind((host, port))
        except OSError:
            raise RuntimeError(
                f"порт {port} занят другим процессом — `ltts serve --port <другой>` и LTTS_URL для клиентов"
            ) from None


def wait_server(url: str, seconds: float = 120, poll: float = 0.4) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if server_alive(url, timeout=0.5):
            return True
        time.sleep(poll)
    return server_alive(url, timeout=1)


def start_server_background(
    host: str,
    port: int,
    log_level: str = "warning",
    on_loaded: Callable[[], None] | None = None,
    *,
    wait: bool = True,
) -> ServerHandle | None:
    """Фоновый сервер. None — уже отвечает /health (чужой или свой экземпляр)."""
    url = f"http://{host}:{port}"
    if server_alive(url, timeout=1):
        return None
    ensure_port_available(host, port)
    import uvicorn

    from .server import app

    if on_loaded:
        on_loaded()
    config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
    server = uvicorn.Server(config)

    def _run() -> None:
        server.run()

    thread = threading.Thread(target=_run, name="ltts-uvicorn", daemon=True)
    thread.start()
    if wait:
        if not wait_server(url):
            stop_server(ServerHandle(thread=thread, server=server, host=host, port=port))
            raise RuntimeError(f"сервер не запустился за отведённое время: {url}")
    return ServerHandle(thread=thread, server=server, host=host, port=port)


def stop_server(handle: ServerHandle | None, join_timeout: float = 25) -> None:
    if not handle:
        return
    handle.server.should_exit = True
    handle.thread.join(timeout=join_timeout)


def run_server_foreground(host: str, port: int, log_level: str = "info") -> int:
    """Блокирующий serve для `ltts serve`. 0 — уже был запущен."""
    url = f"http://{host}:{port}"
    if server_alive(url, timeout=1):
        return 0
    ensure_port_available(host, port)
    import uvicorn

    from .server import app

    uvicorn.run(app, host=host, port=port, log_level=log_level)
    return 0
