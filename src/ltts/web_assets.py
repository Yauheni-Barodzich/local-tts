"""Версия статики веб-морды (cache-bust для WebView2 / браузера)."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import as_file, files


@lru_cache
def web_ui_rev() -> str:
    """Меняется при обновлении index.html в пакете."""
    ref = files("ltts") / "web" / "index.html"
    with as_file(ref) as path:
        return str(int(path.stat().st_mtime_ns))


def web_ui_query() -> str:
    return f"v={web_ui_rev()}"


HTML_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
