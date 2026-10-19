"""HTTP: веб-морда, свой API и OpenAI-совместимый /v1/audio/speech."""

import json
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import __version__
from .audio import ALL_FORMATS, MIME
from .core import ENGINES, all_voices, default_voice, doctor, download, engine_voice, out_keep_limit, render, verify_models
from .engines.base import EngineError, ModelError
from .mcp_http import MCP_MOUNT_PATH, create_app_lifespan, mcp_http_enabled, register_mcp_http
from .paths import DEFAULT_HOST, DEFAULT_PORT, OUT
from .web_assets import HTML_NO_CACHE
from .text import LANGS, detect_lang

app = FastAPI(title="ltts", version=__version__, lifespan=create_app_lifespan())


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


class SettingsPatch(BaseModel):
    default_voices: dict[str, str] | None = None
    sample_rate: int | None = None
    out_keep: int | None = Field(None, ge=0, le=1000)
    pronunciation: dict | None = None
    avatar: dict | None = None


class AvatarConfigPatch(BaseModel):
    enabled: bool | None = None
    size: int | None = Field(None, ge=80, le=400)
    mode: str | None = None


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


def _html_page(name: str) -> HTMLResponse:
    body = (files("ltts") / "web" / name).read_text(encoding="utf-8")
    return HTMLResponse(body, headers=HTML_NO_CACHE)


@app.get("/", response_class=HTMLResponse)
def index():
    return _html_page("index.html")


@app.get("/favicon.ico")
def favicon_ico():
    path = files("ltts") / "web" / "favicon.ico"
    return FileResponse(path, media_type="image/x-icon")


@app.get("/favicon.svg")
def favicon_svg():
    path = files("ltts") / "web" / "favicon.svg"
    return FileResponse(path, media_type="image/svg+xml")


@app.get("/favicon.png")
def favicon_png():
    path = files("ltts") / "web" / "favicon.png"
    return FileResponse(path, media_type="image/png")


@app.get("/common.js")
def common_js():
    path = files("ltts") / "web" / "common.js"
    return FileResponse(path, media_type="application/javascript")


@app.get("/health")
def health():
    body = {"ok": True, "app": "ltts", "version": __version__}
    if mcp_http_enabled() and getattr(app.state, "ltts_mcp_http", False):
        body["mcp_http"] = MCP_MOUNT_PATH
    return body


@app.get("/api/status")
def status():
    from .desktop_setup import setup_status

    info = doctor()
    info["desktop_setup"] = setup_status()
    return info


@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    return _html_page("settings.html")


@app.get("/setup", response_class=HTMLResponse)
def setup_page():
    return _html_page("setup.html")


@app.get("/avatar", response_class=HTMLResponse)
def avatar_page():
    return _html_page("avatar.html")


@app.get("/avatar-rig", response_class=HTMLResponse)
def avatar_rig_page():
    return _html_page("avatar-rig.html")


@app.get("/assets/{name}")
def package_asset(name: str):
    if name not in ("app.png", "tray.png", "logo.svg", "avatar-default.png"):
        raise ApiError(404, "не найдено")
    path = files("ltts") / "assets" / name
    if not path.is_file():
        raise ApiError(404, "не найдено")
    mt = "image/png" if name.endswith(".png") else "image/svg+xml"
    return FileResponse(path, media_type=mt)


@app.get("/api/avatar/config")
def api_avatar_config():
    from .avatar_config import avatar_public_config

    return avatar_public_config()


@app.get("/api/avatar/playback")
def api_avatar_playback():
    from .playback_hub import get_playback_hub

    hub = get_playback_hub()
    if hub is None:
        return {"playing": False, "level": 0.0, "viseme": "closed", "elapsed": 0, "duration": 0, "schedule": []}
    return hub.state.snapshot()


class PlaybackIn(BaseModel):
    delta: int | None = None
    level: float | None = None
    text: str | None = None
    duration: float | None = None


@app.post("/api/playback")
def api_playback(body: PlaybackIn):
    from .playback_hub import get_playback_hub

    hub = get_playback_hub()
    if hub is None:
        return {"ok": False, "playing": False}
    if body.delta is not None:
        if hub.playback_delta(int(body.delta)):
            hub.avatar.sync_playing(hub.state.refcount > 0)
    if body.level is not None:
        hub.playback_level(float(body.level))
    if body.text is not None and body.duration is not None:
        hub.playback_speech(str(body.text), float(body.duration))
    return {"ok": True, "playing": hub.state.refcount > 0}


@app.get("/api/avatar/image")
def api_avatar_image():
    from .avatar_config import AVATAR_IMAGE
    from .app_icon import default_avatar_image_path

    if AVATAR_IMAGE.is_file():
        return FileResponse(AVATAR_IMAGE, media_type="image/png")
    return FileResponse(default_avatar_image_path(), media_type="image/png")


@app.get("/api/avatar/rig/manifest")
def api_avatar_rig_manifest():
    from .avatar_rig import rig_manifest

    m = rig_manifest()
    if not m:
        raise ApiError(404, "риг не настроен")
    return m


@app.get("/api/avatar/rig/{filename}")
def api_avatar_rig_file(filename: str):
    from .avatar_config import AVATAR_DIR

    if filename not in (
        "base.png",
        "mouth_closed.png",
        "mouth_A.png",
        "mouth_E.png",
        "mouth_I.png",
        "mouth_O.png",
        "mouth_U.png",
        "mouth_MBP.png",
    ):
        raise ApiError(400, "недопустимый файл")
    path = AVATAR_DIR / filename
    if not path.is_file():
        raise ApiError(404, "не найдено")
    return FileResponse(path, media_type="image/png")


@app.post("/api/avatar/upload")
async def api_avatar_upload(request: Request):
    from .avatar_config import AVATAR_IMAGE, MAX_UPLOAD_BYTES

    form = await request.form()
    upload = form.get("file")
    if upload is None:
        raise ApiError(400, "нужно поле file")
    data = await upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(400, f"файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ")
    if not data[:8]:
        raise ApiError(400, "пустой файл")
    AVATAR_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    AVATAR_IMAGE.write_bytes(data)
    from .avatar_config import save_avatar_config

    save_avatar_config({"mode": "image"})
    return {"ok": True, "path": str(AVATAR_IMAGE)}


@app.post("/api/avatar/rig")
async def api_avatar_rig_save(request: Request):
    import json

    from .avatar_config import AVATAR_DIR, MAX_UPLOAD_BYTES, save_avatar_config
    from .avatar_rig import build_rig_from_upload

    form = await request.form()
    upload = form.get("file")
    spec_raw = form.get("spec")
    if upload is None or spec_raw is None:
        raise ApiError(400, "нужны file и spec (JSON)")
    data = await upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(400, "файл слишком большой")
    try:
        spec = json.loads(spec_raw if isinstance(spec_raw, str) else spec_raw.decode())
    except (json.JSONDecodeError, AttributeError) as e:
        raise ApiError(400, "spec: невалидный JSON") from e
    tmp = AVATAR_DIR / "_upload_source.png"
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    try:
        meta = build_rig_from_upload(tmp, spec)
    finally:
        tmp.unlink(missing_ok=True)
    save_avatar_config({"mode": "rig"})
    return {"ok": True, "rig": meta}


@app.get("/api/settings")
def api_settings_get():
    from .settings_api import settings_snapshot

    return settings_snapshot()


@app.patch("/api/settings")
def api_settings_patch(body: SettingsPatch):
    from .settings_api import apply_settings

    patch = body.model_dump(exclude_unset=True)
    try:
        return apply_settings(patch)
    except ValueError as e:
        raise ApiError(400, str(e)) from e
    except EngineError as e:
        raise _api_error_from(e) from e


@app.post("/api/doctor/verify")
def api_doctor_verify():
    return verify_models()


@app.post("/api/lexicon/reload")
def api_lexicon_reload():
    from .pronunciation import load_lexicon

    lex = load_lexicon(force=True)
    return {"ok": True, "stats": lex.stats}


@app.post("/api/setup/minimal")
def api_setup_minimal():
    from .desktop_setup import desktop_setup_complete, setup_status, start_minimal_setup_async

    if not desktop_setup_complete():
        start_minimal_setup_async()
    return setup_status()


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


def _out_root() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    return OUT.resolve()


def _resolve_out_file(name: str) -> Path:
    if not name or name != Path(name).name or name in {".", ".."}:
        raise ApiError(400, "недопустимое имя файла")
    root = _out_root()
    path = (OUT / name).resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise ApiError(400, "недопустимое имя файла") from e
    if not path.is_file():
        raise ApiError(404, "файл не найден")
    return path


@app.get("/api/out")
def list_out(limit: int = Query(200, ge=1, le=500)):
    """Файлы из LTTS_HOME/out (ltts say без -o, MCP и т.д.). Веб-синтез сюда не пишет."""
    OUT.mkdir(parents=True, exist_ok=True)
    entries = sorted((p for p in OUT.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    files = []
    for p in entries[:limit]:
        st = p.stat()
        files.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime})
    return {"dir": str(OUT.resolve()), "keep": out_keep_limit(), "files": files}


@app.get("/api/out/file/{name}")
def get_out_file(name: str):
    path = _resolve_out_file(name)
    ext = path.suffix.lstrip(".").lower()
    return FileResponse(path, media_type=MIME.get(ext, "application/octet-stream"), filename=path.name)


@app.delete("/api/out/file/{name}")
def delete_out_file(name: str):
    path = _resolve_out_file(name)
    path.unlink()
    return {"ok": True, "name": name}


@app.delete("/api/out")
def delete_all_out():
    """Удалить все файлы в LTTS_HOME/out (не подкаталоги)."""
    root = _out_root()
    deleted = 0
    for p in OUT.iterdir():
        if not p.is_file():
            continue
        try:
            p.resolve().relative_to(root)
        except ValueError:
            continue
        p.unlink()
        deleted += 1
    return {"ok": True, "deleted": deleted}


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


register_mcp_http(app)
