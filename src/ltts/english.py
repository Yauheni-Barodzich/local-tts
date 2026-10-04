"""Английские вставки -> русская запись: espeak-ng (en-us) даёт IPA, IPA мапим на кириллицу.

Русские модели английский не знают: silero глотает латиницу, piper получает чужие фонемы, rhvoice читает по буквам.
«Claude Code» -> «кл+од к+од», «API» -> «эйпи+ай», «GitHub» -> «г+итхаб».
"""

import re
import threading
from pathlib import Path

# espeak-ng — глобальное состояние в одном процессе; piper тоже им пользуется, поэтому лок общий
ESPEAK_LOCK = threading.RLock()
_ready = False

# многосимвольные токены — первыми
_TOKENS = [
    "tʃ", "dʒ", "eɪ", "aɪ", "ɔɪ", "aʊ", "oʊ", "əʊ", "ɪə", "eə", "ʊə",
    "iː", "uː", "ɑː", "ɔː", "ɜː", "ɚ", "ɝ",
]  # fmt: skip
_CONS = {
    "p": "п", "b": "б", "t": "т", "d": "д", "k": "к", "ɡ": "г", "g": "г", "f": "ф", "v": "в",
    "θ": "т", "ð": "з", "s": "с", "z": "з", "ʃ": "ш", "ʒ": "ж", "tʃ": "ч", "dʒ": "дж", "h": "х",
    "m": "м", "n": "н", "l": "л", "ɹ": "р", "r": "р", "ɾ": "т", "w": "в", "x": "х", "ç": "х",
}  # fmt: skip
# гласная -> (после согласной, в начале слова/после гласной)
_VOW = {
    "ɪ": ("и", "и"), "iː": ("и", "и"), "i": ("и", "и"), "ᵻ": ("и", "и"),
    "ɛ": ("е", "э"), "e": ("е", "э"), "æ": ("э", "э"),
    "ʌ": ("а", "а"), "ɑː": ("а", "а"), "ɑ": ("а", "а"), "a": ("а", "а"),
    "ɒ": ("о", "о"), "ɔː": ("о", "о"), "ɔ": ("о", "о"), "o": ("о", "о"),
    "ʊ": ("у", "у"), "uː": ("у", "у"), "u": ("у", "у"),
    "ə": ("о", "о"), "ɐ": ("а", "а"), "ɜː": ("ёр", "ёр"), "ɚ": ("ер", "эр"), "ɝ": ("ёр", "ёр"),
    "eɪ": ("ей", "эй"), "aɪ": ("ай", "ай"), "ɔɪ": ("ой", "ой"), "aʊ": ("ау", "ау"),
    "oʊ": ("о", "о"), "əʊ": ("о", "о"), "ɪə": ("иа", "иа"), "eə": ("эа", "эа"), "ʊə": ("уа", "уа"),
}  # fmt: skip
# j + гласная -> йотированная
_IOT = {"u": "ю", "uː": "ю", "ʊ": "ю", "ʊə": "юа", "a": "я", "ɑː": "я", "æ": "я", "ʌ": "я",
        "ɛ": "е", "e": "е", "ə": "е", "ɚ": "ер", "ɔ": "ё", "ɔː": "ё", "o": "ё", "oʊ": "ё", "ɜː": "ёр"}  # fmt: skip
_SKIP = set("ˌːʲʔ̃ ̩()-")

_LATIN_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")

# устоявшиеся русские написания: espeak читает по-американски (Docker -> «дакер»), а у нас говорят «докер».
# «+» — ударение.
BUILTIN_DICT = {
    "docker": "д+окер", "github": "г+итхаб", "gitlab": "г+итлаб", "google": "г+угл", "youtube": "ют+уб",
    "iphone": "айф+он", "windows": "в+индоус", "apple": "+эпл", "whatsapp": "вотс+ап", "openai": "опенэй+ай",
    "kubernetes": "кубер+нетис", "linux": "л+инукс", "macos": "мак+оэс", "ios": "айо+эс", "android": "андр+оид",
    "telegram": "телегр+ам", "python": "п+айтон", "javascript": "джаваскр+ипт", "typescript": "тайпскр+ипт",
    "react": "ри+акт", "node": "н+од", "postgres": "постгр+эс", "nginx": "энджин+икс", "json": "дж+ейсон",
    "the": "зэ", "hello": "хэл+оу", "ok": "ок+ей", "okay": "ок+ей", "chatgpt": "чатджипит+и", "gpt": "джипит+и",
    "claude": "кл+од", "anthropic": "антр+опик", "wi": "вай", "fi": "фай", "wifi": "вайф+ай", "email": "имэйл",
    "e": "и", "mail": "м+эйл", "online": "онл+айн", "offline": "офл+айн", "startup": "ст+артап", "feature": "ф+ича",
}  # fmt: skip


def _tokenize(ipa: str) -> list[str]:
    out, i = [], 0
    while i < len(ipa):
        for t in _TOKENS:
            if ipa.startswith(t, i):
                out.append(t)
                i += len(t)
                break
        else:
            out.append(ipa[i])
            i += 1
    return out


def ipa_to_cyrillic(ipa: str, stress: bool = True) -> str:
    words = []
    for word in ipa.split():
        toks = [t for t in _tokenize(word) if t not in _SKIP]
        res: list[str] = []
        prev_vowel = True  # начало слова ведёт себя как «после гласной»
        pending = stressed = False
        i = 0
        while i < len(toks):
            t = toks[i]
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            if t == "j" and nxt == "ˈ" and i + 2 < len(toks) and toks[i + 2] in _IOT:  # pjˈuː -> пь+ю
                pending = not stressed
                del toks[i + 1]
                nxt = toks[i + 1]
            if t == "ˈ":
                pending = not stressed  # одно ударение на слово (CamelCase даёт два)
            elif t == "j" and nxt in _IOT:
                if not prev_vowel:
                    res.append("ь")
                res.append(("+" if pending and stress else "") + _IOT[nxt])
                stressed |= pending
                pending, prev_vowel = False, True
                i += 1
            elif t == "j":
                res.append("й")
                prev_vowel = False
            elif t in _VOW:
                if t == "ɜː" and res and res[-1] == "в":  # world, word, work -> ворлд
                    v = "ор"
                else:
                    v = _VOW[t][1 if prev_vowel else 0]
                if t == "ə" and i == len(toks) - 1:  # конечный шва: java -> джава
                    v = "а"
                if t == "ə" and nxt == "l" and i + 2 == len(toks):  # apple, google -> эпл, гугл
                    v = ""
                res.append(("+" if pending and stress else "") + v)
                stressed |= pending
                pending, prev_vowel = False, True
            elif t == "ŋ":
                res.append("н" if nxt in ("k", "ɡ", "g") else "нг")
                prev_vowel = False
            elif t in _CONS:
                res.append(_CONS[t])
                prev_vowel = False
            i += 1
        words.append("".join(res))
    return " ".join(w for w in words if w)


def _espeak():
    global _ready
    from piper import espeakbridge

    if not _ready:
        import piper

        espeakbridge.initialize(str(Path(piper.__file__).parent / "espeak-ng-data"))
        _ready = True
    return espeakbridge


def english_to_cyrillic(text: str, stress: bool = True, user_dict: dict | None = None) -> str:
    """Заменяет латинские слова на русскую запись английского произношения.
    stress=True оставляет «+» перед ударной гласной (понимает silero), иначе убирает."""
    if not re.search(r"[A-Za-z]", text):
        return text
    words = {**BUILTIN_DICT, **{k.lower(): v for k, v in (user_dict or {}).items()}}
    try:
        with ESPEAK_LOCK:
            bridge = _espeak()
            bridge.set_voice("en-us")

            def repl(m: re.Match) -> str:
                word = m.group(0).replace("’", "'")
                if word.lower() in words:
                    out = words[word.lower()]
                else:
                    ipa = " ".join(p for p, _, _ in bridge.get_phonemes(word))
                    out = ipa_to_cyrillic(re.sub(r"\([^)]*\)", "", ipa), True).replace(" ", "") or word
                return out if stress else out.replace("+", "")

            return _LATIN_WORD.sub(repl, text)
    except Exception:
        from .text import latin_to_cyrillic  # espeak недоступен — грубая побуквенная транслитерация

        return latin_to_cyrillic(text)
