"""Синтез через запущенный `ltts serve` (модели тёплые) с откатом на локальный синтез."""

import json
import os
import sys
import urllib.error
import urllib.request

from .paths import DEFAULT_HOST, DEFAULT_PORT

DEFAULT_TIMEOUT = float(os.environ.get("LTTS_TIMEOUT", "120"))


class ServerError(RuntimeError):
    """Сервер ответил ошибкой (4xx/5xx) — это ответ по существу, откатываться на local смысла нет."""


def server_url() -> str:
    return os.environ.get("LTTS_URL", f"http://{DEFAULT_HOST}:{DEFAULT_PORT}").rstrip("/")


def server_alive(url: str | None = None, timeout: float = 0.3) -> bool:
    try:
        with urllib.request.urlopen((url or server_url()) + "/health", timeout=timeout) as r:
            return r.status == 200 and json.loads(r.read()).get("app") == "ltts"
    except Exception:
        return False


def synth_via_server(text, voice, speed, fmt, lang=None, rate=None, timeout: float = DEFAULT_TIMEOUT) -> tuple[bytes, dict]:
    body = json.dumps({"text": text, "voice": voice, "speed": speed, "format": fmt, "lang": lang, "rate": rate}).encode()
    req = urllib.request.Request(server_url() + "/api/synth", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), json.loads(r.headers.get("X-LTTS-Meta", "{}"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read() or b"{}")
            msg = err.get("error", {}).get("message") or err.get("detail") or str(e)
        except ValueError:
            msg = str(e)
        raise ServerError(msg) from e


def synth_auto(text, voice=None, speed=1.0, fmt="wav", lang=None, rate=None, local=False, timeout=DEFAULT_TIMEOUT):
    """Через сервер, если он жив; при таймауте/обрыве — локально (fallback в метаданных). Ошибки сервера пробрасываются."""
    fallback = None
    if not local and server_alive():
        try:
            data, meta = synth_via_server(text, voice, speed, fmt, lang, rate, timeout)
            meta["via"] = "server"
            return data, meta
        except ServerError:
            raise
        except Exception as e:  # таймаут, сервер упал посреди запроса
            fallback = f"сервер не ответил за {timeout:g} с ({type(e).__name__}) — синтез локально"
            print(f"ltts: {fallback}", file=sys.stderr)
    from .core import render

    data, meta = render(text, voice, speed, lang, fmt, rate)
    meta["via"] = "local"
    if fallback:
        meta["fallback"] = fallback
    return data, meta
