"""Словарь произношения для препроцессинга текста перед TTS (Silero: «+», замены слов/фраз).

Большие базы хранятся вне config.json — каталог LTTS_HOME/pronunciation (или пути из config).
Файлы *.json / *.jsonl, вложенные папки; поздние файлы по имени перекрывают ранние.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import CONFIG, PRONUNCIATION


def _load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}

# русские слова; латиница обрабатывается в english.py
_CYR_WORD = re.compile(r"[А-Яа-яЁё]+(?:[''-][А-Яа-яЁё]+)*")

_CACHE: Lexicon | None = None
_CACHE_KEY: tuple | None = None


@dataclass
class Lexicon:
    words: dict[str, str] = field(default_factory=dict)  # lower -> speak form
    phrases: list[tuple[str, str]] = field(default_factory=list)  # (lower phrase, speak), longest first
    english: dict[str, str] = field(default_factory=dict)  # lower latin -> speak
    files: list[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "dir": str(_lexicon_dirs()[0]) if _lexicon_dirs() else str(PRONUNCIATION),
            "files": len(self.files),
            "words": len(self.words),
            "phrases": len(self.phrases),
            "english": len(self.english),
        }

    def apply_ru(self, text: str) -> str:
        if not self.enabled or (not self.words and not self.phrases):
            return text
        for key, speak in self.phrases:
            if key not in text.lower():
                continue
            text = re.sub(re.escape(key), speak, text, flags=re.IGNORECASE)
        if not self.words:
            return text

        def word(m: re.Match) -> str:
            w = m.group(0)
            return self.words.get(w.lower(), w)

        return _CYR_WORD.sub(word, text)

    def english_dict(self) -> dict[str, str]:
        return dict(self.english) if self.enabled else {}


def _lexicon_dirs() -> list[Path]:
    cfg = _load_config().get("pronunciation") or {}
    dirs: list[Path] = []
    for raw in cfg.get("paths") or []:
        p = Path(os.path.expandvars(str(raw))).expanduser()
        if p.is_dir():
            dirs.append(p)
    default = PRONUNCIATION
    if default.is_dir() or not dirs:
        dirs.append(default)
    # unique, order preserved
    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        r = d.resolve()
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _enabled() -> bool:
    if os.environ.get("LTTS_PRONUNCIATION", "").lower() in ("0", "false", "no", "off"):
        return False
    cfg = _load_config().get("pronunciation") or {}
    return cfg.get("enabled", True)


def _collect_files(dirs: list[Path]) -> list[Path]:
    cfg = _load_config().get("pronunciation") or {}
    explicit = cfg.get("include")
    files: list[Path] = []
    if explicit:
        for d in dirs:
            for pattern in explicit:
                files.extend(sorted(d.glob(pattern)))
    else:
        for d in dirs:
            if not d.is_dir():
                continue
            files.extend(sorted(d.rglob("*.json")))
            files.extend(sorted(d.rglob("*.jsonl")))
    # стабильный порядок: имя файла; дубликаты убираем, последний wins при merge
    uniq: dict[Path, None] = {}
    for f in files:
        if f.is_file() and f.name not in ("config.json",):
            uniq[f.resolve()] = None
    return sorted(uniq.keys(), key=lambda p: str(p).lower())


def _merge_entry(lex: Lexicon, key: str, val: str, kind: str, phrase_acc: dict[str, str]) -> None:
    key = key.strip()
    val = val.strip()
    if not key or not val:
        return
    kind = (kind or "word").lower()
    if kind in ("phrase", "phrases"):
        lex.words.pop(key.lower(), None)
        phrase_acc[key.lower()] = val
    elif kind in ("english", "en", "latin"):
        lex.english[key.lower()] = val
    else:
        lex.words[key.lower()] = val


def _load_json(path: Path, lex: Lexicon, phrase_acc: dict[str, str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "words" in data or "phrases" in data or "english" in data:
            for k, v in (data.get("words") or {}).items():
                _merge_entry(lex, str(k), str(v), "word", phrase_acc)
            for k, v in (data.get("phrases") or {}).items():
                _merge_entry(lex, str(k), str(v), "phrase", phrase_acc)
            for k, v in (data.get("english") or {}).items():
                _merge_entry(lex, str(k), str(v), "english", phrase_acc)
        else:
            for k, v in data.items():
                if k.startswith("_") or k in ("words", "phrases", "english"):
                    continue
                _merge_entry(lex, str(k), str(v), "word", phrase_acc)
    lex.files.append(str(path))


def _load_jsonl(path: Path, lex: Lexicon, phrase_acc: dict[str, str]) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        if "k" in row and "v" in row:
            _merge_entry(lex, row["k"], row["v"], row.get("t") or row.get("type") or "word", phrase_acc)
        elif "word" in row and "speak" in row:
            kind = "english" if row.get("lang") == "en" else (row.get("t") or row.get("type") or "word")
            _merge_entry(lex, row["word"], row["speak"], kind, phrase_acc)
    lex.files.append(str(path))


def load_lexicon(*, force: bool = False) -> Lexicon:
    global _CACHE, _CACHE_KEY
    enabled = _enabled()
    dirs = _lexicon_dirs()
    files = _collect_files(dirs) if enabled else []
    key = (enabled, tuple(str(d) for d in dirs), tuple(str(f) for f in files), tuple(f.stat().st_mtime_ns for f in files))
    if not force and _CACHE is not None and _CACHE_KEY == key:
        return _CACHE

    lex = Lexicon(enabled=enabled)
    phrase_acc: dict[str, str] = {}
    if enabled:
        for path in files:
            try:
                if path.suffix.lower() == ".jsonl":
                    _load_jsonl(path, lex, phrase_acc)
                else:
                    _load_json(path, lex, phrase_acc)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        lex.phrases = sorted(phrase_acc.items(), key=lambda p: len(p[0]), reverse=True)
    _CACHE = lex
    _CACHE_KEY = key
    return lex


def get_lexicon() -> Lexicon:
    return load_lexicon()


def prepare_silero_ru(text: str) -> str:
    """Цифры и латиница — снаружи; здесь словарь + english."""
    from .english import english_to_cyrillic

    lex = get_lexicon()
    text = lex.apply_ru(text)
    return english_to_cyrillic(text, stress=True, user_dict=lex.english_dict())


def invalidate_cache() -> None:
    global _CACHE, _CACHE_KEY
    _CACHE = _CACHE_KEY = None
