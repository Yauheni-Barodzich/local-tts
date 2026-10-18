#!/usr/bin/env python3
"""Конвертация словарей ударений (RUAccent / Supertonic JSON) в JSONL для ltts pronunciation.

Примеры:
  python scripts/ruaccent_to_lexicon.py -i accents.json.gz -o ru.jsonl
  python scripts/ruaccent_to_lexicon.py -i russian_accents_compact.json --omographs omographs.json.gz -o ru.jsonl
  copy ru.jsonl %LOCALAPPDATA%\\ltts\\pronunciation\\
  ltts lexicon --reload
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

COMBINING_ACUTE = "\u0301"
CYR_VOWELS = set("аеёиоуыэюя")
CYR_WORD = re.compile(r"^[а-яё]+(?:[''-][а-яё]+)*$", re.IGNORECASE)


def _open_text(path: Path):
    if path.suffix.lower() == ".gz" or path.name.endswith(".json.gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def load_mapping(path: Path) -> dict[str, str]:
    with _open_text(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit(f"ожидается JSON-объект key→value, получено {type(data).__name__}")
    return {str(k): str(v) for k, v in data.items()}


def load_homographs(path: Path | None) -> set[str]:
    if not path:
        return set()
    with _open_text(path) as f:
        data = json.load(f)
    out: set[str] = set()
    if isinstance(data, dict):
        for k, v in data.items():
            out.add(str(k).lower())
            if isinstance(v, list):
                for item in v:
                    out.add(str(item).lower())
            elif isinstance(v, str):
                out.add(v.lower())
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                out.add(item.lower())
            elif isinstance(item, dict):
                for key in ("word", "lemma", "form"):
                    if key in item:
                        out.add(str(item[key]).lower().replace("ё", "е"))
    return {w.replace("ё", "е") for w in out}


def acute_to_plus(text: str) -> str:
    """U+0301 после гласной → «+» перед гласной (формат Silero)."""
    result: list[str] = []
    chars = list(unicodedata.normalize("NFD", text))
    i = 0
    while i < len(chars):
        ch = chars[i]
        if i + 1 < len(chars) and chars[i + 1] == COMBINING_ACUTE and ch.lower() in CYR_VOWELS:
            result.append("+")
            result.append(ch)
            i += 2
            continue
        if ch != COMBINING_ACUTE:
            result.append(ch)
        i += 1
    return unicodedata.normalize("NFC", "".join(result))


def ruaccent_plus_normalize(text: str) -> str:
    """Уже с «+» (RUAccent): оставить как есть, убрать лишние пробелы."""
    return text.strip()


def detect_and_convert(value: str, mode: str) -> str:
    if mode == "acute":
        return acute_to_plus(value)
    if mode == "plus":
        return ruaccent_plus_normalize(value)
    if COMBINING_ACUTE in unicodedata.normalize("NFD", value):
        return acute_to_plus(value)
    if "+" in value:
        return ruaccent_plus_normalize(value)
    return value


def syllable_count(word: str) -> int:
    return sum(1 for c in word.lower() if c in CYR_VOWELS)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RUAccent/Supertonic JSON → ltts pronunciation JSONL")
    p.add_argument("-i", "--input", type=Path, required=True, help="accents.json или .json.gz")
    p.add_argument("-o", "--output", type=Path, required=True, help="выходной .jsonl")
    p.add_argument("--omographs", type=Path, help="omographs.json(.gz) — эти слова пропустить")
    p.add_argument("--max-len", type=int, default=9, help="макс. длина слова (0 = без лимита)")
    p.add_argument("--min-syllables", type=int, default=2, help="мин. число слогов (1 = не отсеивать односложные)")
    p.add_argument(
        "--format",
        choices=("auto", "plus", "acute"),
        default="auto",
        help="plus: RUAccent (+ перед гласной); acute: Supertonic (комбинируемый acute)",
    )
    p.add_argument("--no-skip-unchanged", action="store_true", help="писать строки даже без «+»")
    args = p.parse_args(argv)

    if not args.input.is_file():
        raise SystemExit(f"нет файла: {args.input}")

    print(f"читаю {args.input}…", file=sys.stderr)
    mapping = load_mapping(args.input)
    homographs = load_homographs(args.omographs)
    if homographs:
        print(f"омографов для пропуска: {len(homographs)}", file=sys.stderr)

    max_len = args.max_len if args.max_len > 0 else 10_000
    args.output.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    skipped_hom = skipped_filter = 0
    with args.output.open("w", encoding="utf-8") as out:
        for key, raw_val in mapping.items():
            word = key.strip().lower().replace("ё", "е")
            if not word or not CYR_WORD.match(word):
                skipped_filter += 1
                continue
            if word in homographs:
                skipped_hom += 1
                continue
            if len(word) > max_len:
                skipped_filter += 1
                continue
            if syllable_count(word) < args.min_syllables:
                skipped_filter += 1
                continue
            speak = detect_and_convert(raw_val, args.format).lower().replace("ё", "е")
            if not args.no_skip_unchanged and "+" not in speak and speak == word:
                skipped_filter += 1
                continue
            out.write(json.dumps({"k": word, "v": speak, "t": "word"}, ensure_ascii=False) + "\n")
            n += 1

    print(
        f"готово: {n} записей → {args.output}\n"
        f"  пропущено омографов: {skipped_hom}, прочих фильтров: {skipped_filter}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
