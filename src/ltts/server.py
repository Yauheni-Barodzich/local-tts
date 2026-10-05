"""HTTP: веб-морда, свой API и OpenAI-совместимый /v1/audio/speech."""

import json
from importlib.resources import files
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import __version__
from .audio import ALL_FORMATS, MIME
from .core import ENGINES, all_voices, default_voice, doctor, download, engine_voice, render
from .engines.base import EngineError, ModelError
from .text import LANGS, detect_lang

app = FastAPI(title="ltts", version=__version__)


# ---------- ошибки: всегда JSON. /v1/* — в формате OpenAI {"error": {...}}, /api/* — ещё и "detail" ----------


class ApiError(Exception):
    def __init__(self, status: int, message: str, type_: str = "invalid_request_error", code: str | None = None):
        super().__init__(message)
        self.status, self.message, self.type, self.code = status, message, type_, code


def _error_body(request: Request, err: ApiError) -> dict:
    body = {"error": {"message": err.message, "type": err.type, "param": None, "code": err.code}}
    if not request.url.path.startswith("/v1/"):
        body["detail"] = err.message
    return body


@app.exception_handler(ApiError)
async def _api_error(request: Request, err: ApiError):
    return JSONResponse(_error_body(request, err), status_code=err.status)


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, err: RequestValidationError):
    msg = "; ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in err.errors())
    status = 400 if request.url.path.startswith("/v1/") else 422  # OpenAI отвечает 400
    return JSONResponse(_error_body(request, ApiError(status, msg)), status_code=status)


@app.exception_handler(Exception)
async def _unexpected(request: Request, err: Exception):
    api = ApiError(500, f"{type(err).__name__}: {err}", "server_error", "internal_error")
    return JSONResponse(_error_body(request, api), status_code=500)


def _api_error_from(e: Exception) -> ApiError:
    if isinstance(e, ModelError):
        return ApiError(503, str(e), "server_error", "model_unavailable")
    return ApiError(400, str(e), "invalid_request_error", "invalid_value")

# голоса OpenAI -> наши (мужские/женские по смыслу, остальное — голос по умолчанию)
OPENAI_VOICES = {
    "alloy": "female", "ash": "male", "ballad": "male", "coral": "female", "echo": "male",
    "fable": "male", "nova": "female", "onyx": "male", "sage": "female", "shimmer": "female",
    "verse": "male", "marin": "female", "cedar": "male",
}  # fmt: skip


class SynthReq(BaseModel):
    text: str
    voice: str | None = None
    speed: float = 1.0
    format: str = "wav"
    lang: str | None = None  # ru|en|auto
    rate: int | None = None  # частота на выходе: 48000, 24000, …; None — родная частота движка


class OpenAISpeechReq(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str | None = None
    speed: float = Field(1.0, ge=0.25, le=4.0)
    response_format: str = "mp3"
    instructions: str | None = None  # не поддерживается, игнорируем
    sample_rate: int | None = None  # расширение ltts: частота на выходе


def _audio_response(text: str, voice, speed: float, fmt: str, lang=None, rate=None) -> Response:
    fmt = (fmt or "").lower()
    if fmt not in ALL_FORMATS:
        raise ApiError(400, f"формат {fmt!r} не поддерживается, есть: {', '.join(ALL_FORMATS)}", code="unsupported_format")
    try:
        data, meta = render(text, voice, speed, lang, fmt, rate)
    except (EngineError, ValueError) as e:
        raise _api_error_from(e) from e
    return Response(data, media_type=MIME[fmt], headers={"X-LTTS-Meta": json.dumps(meta)})


@app.get("/", response_class=HTMLResponse)
def index():
    return (files("ltts") / "web" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"ok": True, "app": "ltts", "version": __version__}


@app.get("/api/status")
def status():
    return doctor()


@app.get("/api/voices")
def voices():
    defaults = {lang: default_voice(lang) for lang in LANGS}
    return {"default": defaults["ru"], "defaults": defaults, "voices": [v.to_dict() for v in all_voices()]}


@app.post("/api/synth")
def synth(req: SynthReq):
    return _audio_response(req.text, req.voice, req.speed, req.format, req.lang, req.rate)


@app.post("/api/download")
def api_download(body: dict):
    if "voice" not in body:
        raise ApiError(400, "нужно поле voice")
    try:
        return download(body["voice"], bool(body.get("force"))).to_dict()
    except EngineError as e:
        raise _api_error_from(e) from e


# ---------- клонированные голоса ----------


@app.get("/api/clones")
def api_clones():
    from . import clones

    return {"clones": [{"voice": f"clone:{c.slug}", **c.to_dict()} for c in clones.all_clones()]}


@app.post("/api/clones")
async def api_clone_add(
    name: Annotated[str, Form()],
    audio: Annotated[UploadFile, File()],
    text: Annotated[str, Form()] = "",
    gender: Annotated[str, Form()] = "",
    overwrite: Annotated[bool, Form()] = False,
):
    from . import clones

    data = await audio.read()
    if len(data) > 25 * 1024 * 1024:
        raise ApiError(413, "файл больше 25 МБ — нужен короткий образец 8–20 с", code="too_large")
    try:
        c = clones.add(name, data, text, gender, overwrite)
    except EngineError as e:
        raise _api_error_from(e) from e
    return {"voice": f"clone:{c.slug}", **c.to_dict()}


@app.get("/api/clones/{slug}/sample")
def api_clone_sample(slug: str):
    from . import clones

    c = clones.get(slug)
    if not c:
        raise ApiError(404, f"нет голоса {slug!r}", code="not_found")
    return Response(c.ref.read_bytes(), media_type="audio/wav")


@app.delete("/api/clones/{slug}")
def api_clone_delete(slug: str):
    from . import clones

    try:
        clones.remove(slug)
    except EngineError as e:
        raise ApiError(404, str(e), code="not_found") from e
    return {"ok": True}


# ---------- OpenAI-совместимое API ----------


def _openai_voice(model: str, voice: str | None, lang: str) -> str | None:
    model = (model or "").lower()
    voice = (voice or "").lower() or None
    if voice in OPENAI_VOICES:  # nova -> женский голос движка (model или движка голоса по умолчанию) для языка текста
        engine = ENGINES.get(model) or ENGINES[default_voice(lang).split(":")[0]]
        name = engine_voice(engine, lang, OPENAI_VOICES[voice])
        return f"{engine.name}:{name}" if name else engine.name
    if voice is None and model in ENGINES:
        return model
    if voice and ":" not in voice and model in ENGINES:
        return f"{model}:{voice}"
    return voice


@app.post("/v1/audio/speech")
def openai_speech(req: OpenAISpeechReq):
    lang = detect_lang(req.input)
    voice = _openai_voice(req.model, req.voice, lang)
    return _audio_response(req.input, voice, req.speed, req.response_format, None, req.sample_rate)


@app.get("/v1/models")
def openai_models():
    ids = ["tts-1", "tts-1-hd", *ENGINES]
    return {"object": "list", "data": [{"id": i, "object": "model", "owned_by": "ltts"} for i in ids]}


@app.get("/v1/audio/voices")
def openai_voices():
    return {"voices": [v.id for v in all_voices()]}
