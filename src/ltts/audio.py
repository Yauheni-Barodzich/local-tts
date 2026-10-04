import io
import shutil
import subprocess
from dataclasses import dataclass

import numpy as np
import soundfile as sf
import soxr

# формат -> (container, subtype, допустимые частоты или None)
FORMATS = {
    "wav": ("WAV", "PCM_16", None),
    "flac": ("FLAC", "PCM_16", None),
    "mp3": ("MP3", "MPEG_LAYER_III", (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)),
    "ogg": ("OGG", "VORBIS", None),
    "opus": ("OGG", "OPUS", (8000, 12000, 16000, 24000, 48000)),
}
MIME = {
    "wav": "audio/wav",
    "flac": "audio/flac",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "opus": "audio/ogg",
    "aac": "audio/aac",
    "pcm": "audio/pcm",
}
ALL_FORMATS = tuple(MIME)


@dataclass
class Audio:
    samples: np.ndarray  # float32 mono [-1, 1]
    sample_rate: int

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate

    def resample(self, rate: int) -> "Audio":
        if rate == self.sample_rate:
            return self
        return Audio(soxr.resample(self.samples, self.sample_rate, rate).astype(np.float32), rate)

    @staticmethod
    def concat(parts: list["Audio"], pause: float = 0.12) -> "Audio":
        rate = parts[0].sample_rate
        gap = np.zeros(int(rate * pause), dtype=np.float32)
        chunks = []
        for i, p in enumerate(parts):
            if i:
                chunks.append(gap)
            chunks.append(p.resample(rate).samples)
        return Audio(np.concatenate(chunks), rate)

    def for_format(self, fmt: str, rate: int | None = None) -> "Audio":
        """Аудио с частотой, которую реально получит файл: rate (если задан) с поправкой на ограничения формата."""
        fmt = fmt.lower()
        if fmt == "pcm" and not rate:  # как у OpenAI: 24 кГц
            rate = 24000
        audio = self.resample(rate) if rate else self
        allowed = FORMATS.get(fmt, (None, None, None))[2]
        if allowed and audio.sample_rate not in allowed:  # mp3/opus умеют не любую частоту
            audio = audio.resample(min(allowed, key=lambda r: abs(r - audio.sample_rate)))
        return audio

    def encode(self, fmt: str) -> bytes:
        """Кодирует как есть; частоту готовит for_format."""
        fmt = fmt.lower()
        if fmt == "pcm":  # 16 бит, little-endian
            return (np.clip(self.samples, -1, 1) * 32767).astype("<i2").tobytes()
        if fmt == "aac":
            return _ffmpeg(self, "adts")
        if fmt not in FORMATS:
            raise ValueError(f"неизвестный формат {fmt!r}, доступны: {', '.join(ALL_FORMATS)}")
        container, subtype, _ = FORMATS[fmt]
        buf = io.BytesIO()
        sf.write(buf, self.samples, self.sample_rate, format=container, subtype=subtype)
        return buf.getvalue()


def _ffmpeg(audio: Audio, fmt: str) -> bytes:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise ValueError("для aac нужен ffmpeg в PATH (остальные форматы работают без него)")
    proc = subprocess.run(
        [exe, "-loglevel", "error", "-i", "pipe:0", "-f", fmt, "pipe:1"],
        input=audio.encode("wav"),
        capture_output=True,
        check=True,
    )
    return proc.stdout


def read_wav(data: bytes) -> Audio:
    samples, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    return Audio(samples, rate)
