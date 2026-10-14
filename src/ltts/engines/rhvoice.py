import os
import subprocess
import tempfile
from importlib.resources import files
from pathlib import Path

from ..audio import read_wav
from ..paths import HOME, IS_WINDOWS
from .base import Engine, EngineError, Voice, fetch_github_tree

LANGS = {"ru": "Russian", "en": "English"}
# голос -> (язык, репозиторий RHVoice/..., пол); пол уточняется из voice.info после скачивания
CATALOG = {
    **{v: ("ru", f"{v}-rus", g) for v, g in {
        "aleksandr": "male", "aleksandr-hq": "male", "anna": "female", "arina": "female", "artemiy": "male",
        "dasha": "female", "elena": "female", "evgeniy": "male", "irina": "female", "lyudmila": "female",
        "michal": "male", "mikhail": "male", "pavel": "male", "ryhor": "male", "seva": "male",
        "tatiana": "female", "timofey": "male", "umka": "", "victoria": "female", "vitaliy": "male",
        "vitaliy-ng": "male", "vsevolod": "male", "yuriy": "male",
    }.items()},
    **{v: ("en", repo, g) for v, (repo, g) in {
        "slt": ("slt-eng", "female"), "clb": ("clb-eng", "female"), "lyubov": ("lyubov-eng", "female"),
        "bdl": ("bdl-eng", "male"), "alan": ("alan-eng", "male"), "ksp": ("ksp-eng", "male"),
        "evgeniy-eng": ("evgeniy-eng", "male"), "dasha-eng": ("dasha-eng", "female"),
    }.items()},
}  # fmt: skip


class RHVoice(Engine):
    name = "rhvoice"
    title = "RHVoice"

    def __init__(self) -> None:
        super().__init__()
        self.prefix = HOME / "rhvoice"
        self.bin = self.prefix / "bin" / "RHVoice-test"
        self.data = self.prefix / "data"
        self.config = self.prefix / "config"

    def status(self):
        if IS_WINDOWS:
            return False, "RHVoice на Windows пока не поддерживается (нет готовых сборок) — используй Silero или Piper"
        if not self.bin.exists():
            return False, "RHVoice не собран — соберётся сам при первом использовании голоса (1–3 мин) или `ltts setup`"
        if not any((self.data / "languages" / lang).exists() for lang in LANGS.values()):
            return False, "нет языковых данных — `ltts download rhvoice:anna` (или rhvoice:slt для английского)"
        return True, ""

    def installable(self):
        """Собрать сможем: есть git, компилятор и cmake (или brew, чтобы его поставить)."""
        import shutil

        has = shutil.which
        if IS_WINDOWS:
            return False
        return self.bin.exists() or bool(has("git") and has("c++") and (has("cmake") or has("brew")))

    def _info(self, voice: str) -> dict:
        info = self.data / "voices" / voice / "voice.info"
        if not info.exists():
            return {}
        return dict(line.split("=", 1) for line in info.read_text(encoding="utf-8").splitlines() if "=" in line)

    def _installed(self, voice: str) -> bool:
        lang = CATALOG[voice][0]
        return bool(self._info(voice)) and self.bin.exists() and (self.data / "languages" / LANGS[lang]).exists()

    def voices(self):
        out = []
        for v, (lang, _, gender) in CATALOG.items():
            info = self._info(v)
            out.append(Voice(self.name, v, info.get("gender", gender), self._installed(v), lang))
        return out

    def reset(self, voice):
        import shutil

        if voice in CATALOG:
            shutil.rmtree(self.data / "voices" / voice, ignore_errors=True)

    def download(self, voice):
        if IS_WINDOWS:
            raise EngineError(self.status()[1])
        if voice not in CATALOG:
            raise EngineError(f"у rhvoice нет голоса {voice!r}, есть: {', '.join(CATALOG)}")
        lang, repo, _ = CATALOG[voice]
        language = LANGS[lang]
        fetch_github_tree(f"RHVoice/{language}", self.data / "languages" / language, f"rhvoice:{language}")
        fetch_github_tree(f"RHVoice/{repo}", self.data / "voices" / voice, f"rhvoice:{voice}")
        self.config.mkdir(parents=True, exist_ok=True)
        (self.config / "RHVoice.conf").touch()
        if not self.bin.exists():
            build(bin_only=True)

    def synth(self, text, voice, speed=1.0):
        ok, why = self.status()
        if not ok:
            raise EngineError(why)
        if voice not in CATALOG or not self._installed(voice):
            raise EngineError(f"голос rhvoice:{voice} не скачан — `ltts download rhvoice:{voice}`")
        profile = self._info(voice).get("name", voice)  # -p ждёт имя из voice.info (Evgeniy-Eng и т.п.)
        env = {**os.environ, "RHVOICE_DATA_PATH": str(self.data), "RHVOICE_CONFIG_PATH": str(self.config)}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            proc = subprocess.run(
                [str(self.bin), "-p", profile, "-r", str(round(speed * 100)), "-o", str(out)],
                input=text.encode(),
                env=env,
                capture_output=True,
            )
            if proc.returncode or not out.exists():
                raise EngineError(f"RHVoice упал ({proc.returncode}): {proc.stderr.decode(errors='replace')[-300:]}")
            return read_wav(out.read_bytes())


def build(voices: list[str] | None = None, bin_only: bool = False) -> None:
    """Собирает RHVoice из исходников скриптом из пакета (bin_only — без скачивания голосов)."""
    script = files("ltts") / "scripts" / "build-rhvoice.sh"
    env = {**os.environ, "LTTS_HOME": str(HOME)}
    if bin_only:
        env["LTTS_RHVOICE_BIN_ONLY"] = "1"
    proc = subprocess.run(["bash", str(script), *(voices or [])], env=env)
    if proc.returncode:
        raise EngineError("сборка RHVoice не удалась, лог выше")
