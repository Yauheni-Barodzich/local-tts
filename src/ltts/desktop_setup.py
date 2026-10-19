"""Первый запуск desktop: минимальная загрузка голосов и состояние для API."""

from __future__ import annotations

import threading
from typing import Any

from .core import download, load_config, save_config
from .paths import HOME

DESKTOP_SETUP_VERSION = 1
MINIMAL_DESKTOP_DOWNLOADS = ["silero:kseniya"]

_lock = threading.Lock()
_state: dict[str, Any] = {
    "state": "idle",  # idle | pending | running | done | error
    "current": "",
    "error": None,
    "voices": MINIMAL_DESKTOP_DOWNLOADS,
}


def minimal_desktop_downloads() -> list[str]:
    return list(MINIMAL_DESKTOP_DOWNLOADS)


def desktop_setup_complete() -> bool:
    cfg = load_config()
    if cfg.get("desktop_setup_version", 0) >= DESKTOP_SETUP_VERSION:
        return True
    marker = HOME / ".desktop-setup-done"
    return marker.is_file()


def mark_desktop_setup_complete() -> None:
    cfg = load_config()
    cfg["desktop_setup_version"] = DESKTOP_SETUP_VERSION
    save_config(cfg)
    try:
        (HOME / ".desktop-setup-done").write_text(str(DESKTOP_SETUP_VERSION), encoding="utf-8")
    except OSError:
        pass


def needs_desktop_setup() -> bool:
    return not desktop_setup_complete()


def setup_status() -> dict[str, Any]:
    with _lock:
        out = dict(_state)
    out["needed"] = needs_desktop_setup()
    out["complete"] = desktop_setup_complete()
    out["version"] = DESKTOP_SETUP_VERSION
    return out


def _set_state(**kwargs: Any) -> None:
    with _lock:
        _state.update(kwargs)


def run_minimal_setup() -> None:
    """Синхронная загрузка дефолтного голоса."""
    if desktop_setup_complete():
        _set_state(state="done", current="", error=None)
        return
    _set_state(state="running", error=None)
    try:
        for vid in minimal_desktop_downloads():
            _set_state(current=vid)
            download(vid)
        mark_desktop_setup_complete()
        _set_state(state="done", current="", error=None)
    except Exception as e:
        _set_state(state="error", error=str(e))
        raise


def start_minimal_setup_async() -> bool:
    """Запуск в фоне. False — уже идёт или не нужен."""
    if desktop_setup_complete():
        _set_state(state="done")
        return False
    with _lock:
        if _state["state"] == "running":
            return False
        _state["state"] = "running"
        _state["error"] = None

    def worker() -> None:
        try:
            run_minimal_setup()
        except Exception:
            pass

    threading.Thread(target=worker, name="ltts-desktop-setup", daemon=True).start()
    return True
