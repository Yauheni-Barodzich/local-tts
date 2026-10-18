import re
import zipfile
from xml.sax.saxutils import escape

from ..audio import Audio
from ..paths import MODELS
from ..text import chunks, numbers_to_words
from .base import Engine, EngineError, ModelError, Voice, ensure_valid, fetch_urls, invalidate

# models.silero.ai иногда отдаёт просроченный SSL; fetch_urls + fallback в base._urlopen
SILERO_BASE = "https://models.silero.ai/models/tts"

# язык -> (модель, {голос: пол}); у английской модели 118 безымянных дикторов,
# в каталоге — по три явно мужских/женских (отобраны по высоте голоса), остальные en_N тоже работают
MODELS_BY_LANG = {
    "ru": ("ru/v5_5_ru", {"kseniya": "female", "xenia": "female", "baya": "female", "aidar": "male", "eugene": "male"}),
    "en": ("en/v3_en", {"en_0": "female", "en_14": "female", "en_99": "female",
                        "en_2": "male", "en_13": "male", "en_79": "male"}),
    "de": ("de/v3_de", {"eva_k": "female", "hokuspokus": "female", "bernd_ungerer": "male",
                        "friedrich": "male", "karlsson": "male"}),
}  # fmt: skip
EN_ANY = re.compile(r"en_(\d+)$")
RATE = 48000
CHUNK = 800  # silero не любит длинные куски


class Silero(Engine):
    name = "silero"
    title = "Silero TTS (v5_5_ru, v3_en, v3_de)"

    def __init__(self) -> None:
        super().__init__()
        self._models: dict = {}

    def _lang(self, voice: str) -> str:
        for lang in ("ru", "de"):
            if voice in MODELS_BY_LANG[lang][1]:
                return lang
        m = EN_ANY.match(voice)
        if m and int(m.group(1)) <= 117:
            return "en"
        raise EngineError(f"у silero нет голоса {voice!r} — смотри `ltts voices -e silero`")

    def _path(self, lang: str):
        return MODELS / "silero" / (MODELS_BY_LANG[lang][0].split("/")[1] + ".pt")

    def status(self):
        try:
            import torch  # noqa: F401
        except ImportError as e:
            return False, f"нужен torch: {e}"
        return True, ""

    def _ok(self, lang: str) -> bool:
        # torch.package — это zip: оборванный файл без центрального каталога сразу видно
        return ensure_valid(self._path(lang), zipfile.is_zipfile)

    def voices(self):
        out = []
        for lang, (_, speakers) in MODELS_BY_LANG.items():
            ok = self._ok(lang)
            out += [Voice(self.name, s, g, ok, lang) for s, g in speakers.items()]
        return out

    def has_voice(self, voice):
        try:
            self._lang(voice)
            return True
        except EngineError:
            return False

    def is_installed(self, voice):
        return self.has_voice(voice) and self._ok(self._lang(voice))

    def reset(self, voice):
        lang = self._lang(voice)
        self._models.pop(lang, None)
        invalidate(self._path(lang))

    def download(self, voice):
        lang = self._lang(voice)
        if not self._ok(lang):
            model = MODELS_BY_LANG[lang][0]
            fetch_urls([f"{SILERO_BASE}/{model}.pt"], self._path(lang), f"silero:{model}")

    def _load(self, lang: str):
        if lang not in self._models:
            import warnings

            import torch

            path = self._path(lang)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model = torch.package.PackageImporter(str(path)).load_pickle("tts_models", "model")
            except Exception as e:
                invalidate(path)
                raise ModelError(f"модель silero {path.name} повреждена и удалена ({e}); следующий вызов скачает её заново") from e
            model.to(torch.device("cpu"))
            self._models[lang] = model
        return self._models[lang]

    def synth(self, text, voice, speed=1.0):
        lang = self._lang(voice)
        if not self._ok(lang):
            raise EngineError(f"модель silero ({lang}) не скачана — `ltts download silero:{voice}`")
        # silero молча глотает цифры, а русская модель — ещё и латиницу
        text = numbers_to_words(text, lang)
        if lang == "ru":
            from ..pronunciation import prepare_silero_ru

            text = prepare_silero_ru(text)
        rate = f"{round(speed * 100)}%"
        parts = []
        with self.lock:
            model = self._load(lang)
            for piece in chunks(text, CHUNK):
                ssml = f'<speak><prosody rate="{rate}">{escape(piece)}</prosody></speak>'
                try:
                    wav = model.apply_tts(ssml_text=ssml, speaker=voice, sample_rate=RATE)
                except Exception as e:
                    raise EngineError(f"silero не смог озвучить кусок {piece[:40]!r}: {e}") from e
                parts.append(Audio(wav.numpy(), RATE))
        if not parts:
            raise EngineError("пустой текст")
        return Audio.concat(parts)
