"""Библиотека клонированных голосов: <LTTS_HOME>/voices/<slug>/{ref.wav, meta.json}."""

import io
import json
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .audio import Audio
from .engines.base import EngineError
from .paths import HOME

VOICES_DIR = HOME / "voices"
REF_RATE = 24000
MIN_SEC, MAX_SEC = 3.0, 20.0

_TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                     ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                      "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"], strict=True))  # fmt: skip


@dataclass
class Clone:
    slug: str
    name: str
    text: str = ""  # что сказано в образце: нужно для HQ (VoxCPM2), улучшает обычный клон
    gender: str = ""
    duration: float = 0.0
    created: str = ""

    @property
    def ref(self) -> Path:
        return VOICES_DIR / self.slug / "ref.wav"

    def to_dict(self) -> dict:
        return asdict(self)


def slugify(name: str) -> str:
    s = "".join(_TRANSLIT.get(c, c) for c in name.strip().lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:32]
    if not s:
        raise EngineError("имя голоса должно содержать буквы или цифры")
    return s


def _prepare(data: bytes) -> Audio:
    """Декодирует (wav/flac/ogg/mp3), моно, 24 кГц, обрезает тишину по краям, ограничивает длину, нормализует."""
    try:
        samples, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception as e:
        raise EngineError("не удалось прочитать аудио: формат не распознан — поддерживаются wav, mp3, flac, ogg") from e
    audio = Audio(samples.mean(axis=1), rate).resample(REF_RATE)
    x = audio.samples
    loud = np.flatnonzero(np.abs(x) > max(0.02, np.abs(x).max() * 0.05))
    if loud.size:
        pad = int(0.15 * REF_RATE)
        x = x[max(0, loud[0] - pad) : loud[-1] + pad]
    dur = len(x) / REF_RATE
    if dur < MIN_SEC:
        raise EngineError(f"образец слишком короткий ({dur:.1f} с) — нужно хотя бы {MIN_SEC:g} с речи, лучше 8–15 с")
    x = x[: int(MAX_SEC * REF_RATE)]
    peak = np.abs(x).max()
    if peak < 1e-3:
        raise EngineError("в образце тишина")
    return Audio((x / peak * 0.9).astype(np.float32), REF_RATE)


def add(name: str, data: bytes, text: str = "", gender: str = "", overwrite: bool = False) -> Clone:
    slug = slugify(name)
    if gender not in ("", "female", "male"):
        raise EngineError("gender: female, male или пусто")
    d = VOICES_DIR / slug
    if d.exists() and not overwrite:
        raise EngineError(f"голос {slug!r} уже есть — удали его или выбери другое имя")
    audio = _prepare(data)
    tmp = d.with_name(d.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    sf.write(tmp / "ref.wav", audio.samples, REF_RATE, subtype="PCM_16")
    clone = Clone(slug, name.strip(), text.strip(), gender, round(audio.duration, 2), time.strftime("%Y-%m-%dT%H:%M:%S"))
    (tmp / "meta.json").write_text(json.dumps(clone.to_dict(), ensure_ascii=False, indent=1))
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    return clone


def get(slug: str) -> Clone | None:
    try:
        meta = json.loads((VOICES_DIR / slug / "meta.json").read_text())
    except (FileNotFoundError, ValueError):
        return None
    c = Clone(**{k: v for k, v in meta.items() if k in Clone.__dataclass_fields__})
    return c if c.ref.exists() else None


def all_clones() -> list[Clone]:
    if not VOICES_DIR.exists():
        return []
    return sorted(filter(None, (get(p.name) for p in VOICES_DIR.iterdir() if p.is_dir() and not p.name.endswith(".tmp"))),
                  key=lambda c: c.created)


def remove(slug: str) -> None:
    if not get(slug):
        raise EngineError(f"нет клонированного голоса {slug!r}")
    shutil.rmtree(VOICES_DIR / slug)
