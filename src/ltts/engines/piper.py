import json

import numpy as np

from ..audio import Audio
from ..english import ESPEAK_LOCK
from ..paths import MODELS
from .base import Engine, EngineError, ModelError, Voice, ensure_valid, fetch, invalidate

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
# имя -> (локаль, качество, пол)
CATALOG = {
    "irina": ("ru_RU", "medium", "female"),
    "denis": ("ru_RU", "medium", "male"),
    "dmitri": ("ru_RU", "medium", "male"),
    "ruslan": ("ru_RU", "medium", "male"),
    "lessac": ("en_US", "medium", "female"),
    "amy": ("en_US", "medium", "female"),
    "ryan": ("en_US", "medium", "male"),
    "joe": ("en_US", "medium", "male"),
    "cori": ("en_GB", "medium", "female"),
    "alan": ("en_GB", "medium", "male"),
}


def _onnx_ok(path) -> bool:
    """Проверка старых файлов без маркера: обрезанный onnx не загрузится."""
    import onnxruntime

    onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return True


class Piper(Engine):
    name = "piper"
    title = "Piper (VITS/ONNX)"

    def __init__(self) -> None:
        super().__init__()
        self.lock = ESPEAK_LOCK  # espeak-ng в процессе один, делим его с английской транслитерацией
        self.dir = MODELS / "piper"
        self._loaded: dict = {}

    def _model(self, voice: str):
        locale, quality, _ = CATALOG[voice]
        return self.dir / f"{locale}-{voice}-{quality}.onnx"

    def status(self):
        try:
            import piper  # noqa: F401
        except ImportError as e:
            return False, f"пакет piper-tts не установлен: {e}"
        return True, ""

    def _ok(self, voice: str) -> bool:
        m = self._model(voice)
        cfg_ok = ensure_valid(m.with_suffix(".onnx.json"), lambda p: json.loads(p.read_text())["audio"]["sample_rate"])
        return cfg_ok and ensure_valid(m, _onnx_ok)

    def voices(self):
        return [Voice(self.name, v, gender, self._ok(v), locale[:2]) for v, (locale, _, gender) in CATALOG.items()]

    def reset(self, voice):
        self._loaded.pop(voice, None)
        m = self._model(voice)
        invalidate(m, m.with_suffix(".onnx.json"))

    def download(self, voice):
        if voice not in CATALOG:
            raise EngineError(f"у piper нет голоса {voice!r}, есть: {', '.join(CATALOG)}")
        locale, quality, _ = CATALOG[voice]
        model = self._model(voice)
        base = f"{HF}/{locale[:2]}/{locale}/{voice}/{quality}/{model.name}"
        fetch(base + ".json", model.with_suffix(".onnx.json"))
        fetch(base, model, f"piper:{voice}")

    def synth(self, text, voice, speed=1.0):
        from piper import PiperVoice, SynthesisConfig

        if not self.is_installed(voice):
            raise EngineError(f"голос piper:{voice} не скачан — `ltts download piper:{voice}`")
        with self.lock:
            if voice not in self._loaded:
                try:
                    self._loaded[voice] = PiperVoice.load(self._model(voice))
                except Exception as e:
                    self.reset(voice)
                    raise ModelError(f"модель piper:{voice} повреждена и удалена ({e}); следующий вызов скачает её заново") from e
            pv = self._loaded[voice]
            cfg = SynthesisConfig(length_scale=1.0 / max(speed, 0.1))
            chunks = [c.audio_float_array for c in pv.synthesize(text, syn_config=cfg)]
        if not chunks:
            raise EngineError("piper вернул пустое аудио")
        rate = json.loads(self._model(voice).with_suffix(".onnx.json").read_text())["audio"]["sample_rate"]
        return Audio(np.concatenate(chunks).astype(np.float32), rate)
