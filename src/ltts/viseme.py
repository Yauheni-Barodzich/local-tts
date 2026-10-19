"""Эвристика viseme по тексту (без фонем от движка)."""

from __future__ import annotations

import re

# Preston Blair–style упрощение
_VISEME_CHARS: dict[str, str] = {
    "а": "A",
    "я": "A",
    "о": "O",
    "у": "U",
    "ю": "U",
    "ы": "I",
    "и": "I",
    "е": "E",
    "э": "E",
    "ё": "O",
    "a": "A",
    "o": "O",
    "u": "U",
    "i": "I",
    "e": "E",
    "y": "I",
    "ä": "E",
    "ö": "O",
    "ü": "U",
}
_MBP = set("бпмБПМbmpMBP")
_CLOSED = set(" .,!?;:-—…\n\t")


def _char_viseme(ch: str) -> str:
    if ch in _CLOSED:
        return "closed"
    low = ch.lower()
    if low in _VISEME_CHARS:
        return _VISEME_CHARS[low]
    if low in _MBP or ch in _MBP:
        return "MBP"
    if low.isalpha():
        return "E"
    return "closed"


def schedule_from_text(text: str, duration: float) -> list[dict[str, float]]:
    """Список {t: секунда от начала, v: имя viseme}."""
    if duration <= 0:
        return []
    tokens = [c for c in text if not c.isspace() or c == " "]
    if not tokens:
        tokens = list(text) or [" "]
    visemes = [_char_viseme(c) for c in tokens]
    # схлопнуть подряд одинаковые
    collapsed: list[str] = []
    for v in visemes:
        if not collapsed or collapsed[-1] != v:
            collapsed.append(v)
    if not collapsed:
        collapsed = ["closed"]
    n = len(collapsed)
    step = duration / n
    return [{"t": round(i * step, 4), "v": collapsed[i]} for i in range(n)]


def viseme_at(schedule: list[dict], elapsed: float, default: str = "closed") -> str:
    if not schedule:
        return default
    cur = default
    for item in schedule:
        if elapsed >= item["t"]:
            cur = item["v"]
    return cur
