"""Клонированные голоса: clone:<имя> — OmniVoice (быстро, 24 кГц), clonehq:<имя> — VoxCPM2 (48 кГц, медленнее)."""

from .. import clones
from ..audio import Audio
from ..text import detect_lang
from .base import Engine, EngineError, Voice
from .mlx_common import MLX_LOCK, fetch_repo, load, mlx_status, quiet_stdout, repo_ok, reset_repo, to_numpy

LANG_NAMES = {"ru": "Russian", "en": "English"}


def _natural_duration(text: str) -> float:
    """Та же оценка, что OmniVoice делает сам при duration_s=None (25 токенов/с, запас 15%)."""
    from mlx_audio.tts.models.omnivoice.duration import RuleDurationEstimator

    return RuleDurationEstimator().estimate_duration(text, "Nice to meet you.", 25) * 1.15 / 25


class CloneEngine(Engine):
    def __init__(self, name: str, repo: str, title: str, hq: bool) -> None:
        super().__init__()
        self.lock = MLX_LOCK
        self.name, self.repo, self.title, self.hq = name, repo, title, hq

    def status(self):
        return mlx_status()

    def voices(self):
        ok = repo_ok(self.repo)
        note = "48 кГц, медленнее; нужен текст образца" if self.hq else "OmniVoice"
        return [
            Voice(self.name, c.slug, c.gender, ok and (bool(c.text) or not self.hq), "any", note)
            for c in clones.all_clones()
        ]

    def has_voice(self, voice):
        return clones.get(voice) is not None

    def is_installed(self, voice):
        c = clones.get(voice)
        return bool(c) and repo_ok(self.repo) and (bool(c.text) or not self.hq)

    def download(self, voice):
        c = clones.get(voice)
        if not c:
            raise EngineError(f"нет клонированного голоса {voice!r} — `ltts clone add {voice} образец.wav`")
        if self.hq and not c.text:
            raise EngineError(f"для HQ нужен текст образца: `ltts clone add {voice} образец.wav --text \"…\" --force`")
        if not repo_ok(self.repo):
            fetch_repo(self.repo)

    def reset(self, voice):
        reset_repo(self.repo)

    def synth(self, text, voice, speed=1.0):
        c = clones.get(voice)
        if not c:
            raise EngineError(f"нет клонированного голоса {voice!r}")
        with self.lock, quiet_stdout():
            model = load(self.repo)
            if self.hq:  # VoxCPM2: без текста образца похожесть падает до ~0.75, поэтому текст обязателен
                gen = model.generate(text=text, ref_audio=str(c.ref), ref_text=c.text)
            else:
                kw = {"language": LANG_NAMES.get(detect_lang(text), "English"), "ref_audio": str(c.ref)}
                if c.text:
                    kw["ref_text"] = c.text
                if abs(speed - 1.0) > 0.01:  # скорость у OmniVoice — через целевую длительность
                    kw["duration_s"] = max(0.5, _natural_duration(text) / speed)
                gen = model.generate(text=text, **kw)
            samples, rate = to_numpy(gen)
        return Audio(samples, rate or model.sample_rate)


def make_engines() -> list[CloneEngine]:
    return [
        CloneEngine("clone", "mlx-community/OmniVoice-bf16", "Клоны · OmniVoice (MLX)", hq=False),
        CloneEngine("clonehq", "mlx-community/VoxCPM2-8bit", "Клоны HQ · VoxCPM2 48 кГц (MLX)", hq=True),
    ]
