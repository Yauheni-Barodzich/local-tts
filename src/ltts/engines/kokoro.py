"""Kokoro-82M через MLX: лучший по качеству/скорости английский (№1 open-weight в TTS Arena), 28 голосов."""

from ..audio import Audio
from .base import Engine, EngineError, Voice
from .mlx_common import MLX_LOCK, fetch_repo, fix_espeak_path, load, mlx_status, quiet_stdout, repo_ok, reset_repo, to_numpy

REPO = "mlx-community/Kokoro-82M-bf16"
# af/am — американский английский, bf/bm — британский; f/m — пол
VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "af_nova", "af_alloy", "af_aoede", "af_jessica",
    "af_kore", "af_river", "am_michael", "am_adam", "am_eric", "am_fenrir", "am_liam", "am_onyx", "am_puck",
    "am_echo", "bf_emma", "bf_isabella", "bf_alice", "bf_lily", "bm_george", "bm_lewis", "bm_daniel", "bm_fable",
]  # fmt: skip


class Kokoro(Engine):
    name = "kokoro"
    title = "Kokoro 82M (MLX)"

    def __init__(self) -> None:
        super().__init__()
        self.lock = MLX_LOCK
        self._espeak_fixed = False

    def status(self):
        return mlx_status()

    def voices(self):
        ok = repo_ok(REPO)
        return [
            Voice(self.name, v, "female" if v[1] == "f" else "male", ok, "en", "UK" if v[0] == "b" else "US")
            for v in VOICES
        ]

    def download(self, voice):
        if voice not in VOICES:
            raise EngineError(f"у kokoro нет голоса {voice!r}, есть: {', '.join(VOICES)}")
        if not repo_ok(REPO):
            fetch_repo(REPO)

    def reset(self, voice):
        reset_repo(REPO)

    def synth(self, text, voice, speed=1.0):
        if voice not in VOICES:
            raise EngineError(f"у kokoro нет голоса {voice!r}")
        with self.lock, quiet_stdout():
            if not self._espeak_fixed:
                fix_espeak_path()
                self._espeak_fixed = True
            model = load(REPO)
            samples, rate = to_numpy(model.generate(text=text, voice=voice, speed=speed, lang_code=voice[0]))
        return Audio(samples, rate or 24000)
