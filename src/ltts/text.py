import re

from num2words import num2words

_NUM = re.compile(r"(?<![\w])(\d+(?:[.,]\d+)?)(\s*%)?")
_SENT = re.compile(r"(?<=[.!?…;])\s+|\n+")


_CYR = re.compile(r"[А-Яа-яЁё]")
_LAT = re.compile(r"[A-Za-z]")
LANGS = ("ru", "en")


def detect_lang(text: str) -> str:
    """ru, если есть хоть немного кириллицы (английские слова в русской фразе — норм), иначе en при латинице."""
    cyr, lat = len(_CYR.findall(text)), len(_LAT.findall(text))
    return "en" if lat and cyr * 10 < lat else "ru"


def numbers_to_words(text: str, lang: str = "ru") -> str:
    """«В 2026 году 3,5%» -> «В две тысячи двадцать шесть году три целых пять десятых процентов».
    Падежи не согласуются, но лучше, чем молча проглоченные цифры."""
    if lang == "en":
        text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 1,000 -> 1000

    def repl(m: re.Match) -> str:
        raw = m.group(1)
        raw = raw.replace(",", ".") if lang == "ru" else raw
        try:
            words = num2words(float(raw) if "." in raw else int(raw), lang=lang)
        except Exception:
            return m.group(0)
        return words + ((" процентов" if lang == "ru" else " percent") if m.group(2) else "")

    return _NUM.sub(repl, text)


_LAT2 = {"sh": "ш", "ch": "ч", "zh": "ж", "th": "т", "ph": "ф", "kh": "х", "ts": "ц", "ya": "я", "yu": "ю",
         "yo": "ё", "ee": "и", "oo": "у", "ck": "к", "qu": "кв", "wh": "в"}  # fmt: skip
_LAT1 = {"a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х", "i": "и", "j": "дж",
         "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т",
         "u": "у", "v": "в", "w": "в", "x": "кс", "y": "и", "z": "з"}  # fmt: skip
_LATWORD = re.compile(r"[A-Za-z]+")


def latin_to_cyrillic(text: str) -> str:
    """Грубая транслитерация латиницы: silero её иначе просто проглатывает (world -> ворлд)."""

    def word(m: re.Match) -> str:
        w, out, i = m.group(0).lower(), [], 0
        while i < len(w):
            if w[i : i + 2] in _LAT2:
                out.append(_LAT2[w[i : i + 2]])
                i += 2
            else:
                out.append(_LAT1[w[i]])
                i += 1
        return "".join(out)

    return _LATWORD.sub(word, text)


def chunks(text: str, limit: int) -> list[str]:
    """Режет текст по предложениям в куски не длиннее limit символов."""
    out: list[str] = []
    cur = ""
    for sent in filter(None, (s.strip() for s in _SENT.split(text))):
        while len(sent) > limit:  # длинное предложение режем по запятым/пробелам
            cut = max(sent.rfind(",", 0, limit), sent.rfind(" ", 0, limit))
            cut = cut if cut > 0 else limit
            if cur:
                out.append(cur)
                cur = ""
            out.append(sent[: cut + 1].strip())
            sent = sent[cut + 1 :].strip()
        if cur and len(cur) + 1 + len(sent) > limit:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out
