"""MCP Streamable HTTP на том же порту, что веб-сервер (desktop / ltts serve)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

MCP_MOUNT_PATH = "/mcp"


def mcp_http_enabled() -> bool:
    return os.environ.get("LTTS_MCP_HTTP", "1").strip().lower() not in ("0", "false", "no", "off")


def mcp_http_url(host: str, port: int) -> str:
    return f"http://{host}:{port}{MCP_MOUNT_PATH}"


_mcp_manager_started = False
_mcp_manager_cm = None


def create_app_lifespan():
    """Lifespan FastAPI: один session manager на процесс (повторный run() у MCP SDK запрещён)."""
    if not mcp_http_enabled():

        @asynccontextmanager
        async def _noop(_app):
            yield

        return _noop

    from .mcp_server import mcp

    @asynccontextmanager
    async def _mcp_lifespan(_app):
        global _mcp_manager_started, _mcp_manager_cm
        if not _mcp_manager_started:
            _mcp_manager_cm = mcp.session_manager.run()
            await _mcp_manager_cm.__aenter__()
            _mcp_manager_started = True
        yield
        # Намеренно не выходим из session manager: uvicorn/TestClient могут
        # перезапускать lifespan, а SDK не позволяет run() второй раз.

    return _mcp_lifespan


def register_mcp_http(app: FastAPI) -> bool:
    """Смонтировать /mcp. Вызвать один раз после создания app."""
    if not mcp_http_enabled():
        return False
    if getattr(app.state, "ltts_mcp_http", False):
        return True
    from .mcp_server import mcp

    sub = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        host="127.0.0.1",
    )
    app.mount(MCP_MOUNT_PATH, sub)
    app.state.ltts_mcp_http = True
    return True
