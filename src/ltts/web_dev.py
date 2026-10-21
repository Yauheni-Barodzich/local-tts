"""Dev: HTML/JS из клона + live-reload в браузере (LTTS_WEB_DEV)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_ENV = "LTTS_WEB_DEV"
_ROOT_ENV = "LTTS_WEB_ROOT"
_WATCH_SUFFIXES = {".html", ".js", ".css", ".svg"}

_RELOAD_SNIPPET = """
<script>
(function () {
  let rev = "";
  setInterval(function () {
    fetch("/api/dev/web-rev", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.rev) return;
        if (rev && j.rev !== rev) location.reload();
        rev = j.rev;
      })
      .catch(function () {});
  }, 900);
})();
</script>
"""


def web_dev_enabled() -> bool:
    v = os.environ.get(_ENV, "").strip().lower()
    return v in ("1", "true", "yes", "on")


def web_root() -> Path | None:
    raw = os.environ.get(_ROOT_ENV, "").strip()
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p.resolve()
    if web_dev_enabled():
        here = Path(__file__).resolve().parent / "web"
        if here.is_dir():
            return here
    return None


def _safe_web_path(name: str) -> Path | None:
    root = web_root()
    if root is None or not name or "/" in name or "\\" in name or ".." in name:
        return None
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


def read_dev_html(name: str) -> str | None:
    if not web_dev_enabled():
        return None
    path = _safe_web_path(name)
    if path is None or path.suffix.lower() != ".html":
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def read_dev_static(name: str) -> Path | None:
    if not web_dev_enabled():
        return None
    return _safe_web_path(name)


def inject_live_reload(html: str) -> str:
    if not web_dev_enabled() or _RELOAD_SNIPPET.strip() in html:
        return html
    m = re.search(r"</body\s*>", html, re.I)
    if m:
        i = m.start()
        return html[:i] + _RELOAD_SNIPPET + html[i:]
    return html + _RELOAD_SNIPPET


def web_static_rev() -> str:
    root = web_root()
    if root is None:
        return "0"
    best = 0
    try:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in _WATCH_SUFFIXES:
                best = max(best, p.stat().st_mtime_ns)
    except OSError:
        pass
    return str(best)
