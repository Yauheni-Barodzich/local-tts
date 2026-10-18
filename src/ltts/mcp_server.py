"""MCP-сервер (stdio): инструменты speak / list_voices для агентов."""

from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .cli import play
from .client import synth_auto
from .core import ENGINE_NAMES, all_voices, default_voice, ordered, out_path
from .text import LANGS

mcp = MCPServer(
    "ltts",
    instructions=(
        "Локальный синтез речи на русском, английском и немецком (Silero, Piper, RHVoice). "
        "Язык определяется по тексту, голос подбирается того же движка и пола. "
        "speak сохраняет аудиофайл и возвращает путь; play=true — сразу проиграть на этом компьютере. "
        "Голос задаётся как engine:voice (silero:kseniya, piper:denis, rhvoice:anna); list_voices покажет все."
    ),
)


@mcp.tool()
def speak(
    text: str,
    voice: str | None = None,
    speed: float = 1.0,
    play_audio: bool = False,
    output_path: str | None = None,
    format: str = "wav",
    lang: str = "auto",
    sample_rate: int | None = None,
) -> dict:
    """Озвучить текст. Возвращает путь к файлу и метаданные (длительность, голос).

    voice: engine:voice, просто имя голоса или имя движка; пусто — голос по умолчанию.
    speed: 0.25–4.0. format: wav|mp3|ogg|opus|flac. play_audio: проиграть через динамики.
    lang: auto|ru|en|de — auto сам определит язык и подберёт голос под него.
    sample_rate: частота на выходе (например 48000), чтобы склеивать файлы разных движков; пусто — родная.
    """
    try:
        data, meta = synth_auto(text, voice, speed, format, lang, sample_rate)
    except Exception as e:  # ToolError — чтобы агент увидел причину, а не «Error executing tool»
        raise ToolError(str(e)) from e
    path = Path(output_path).expanduser().resolve() if output_path else out_path(format)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if play_audio:
        play(path)
    return ordered({**meta, "ok": True, "path": str(path)})


@mcp.tool()
def list_voices(engine: str | None = None, lang: str | None = None, installed_only: bool = False) -> dict:
    """Список голосов. engine: silero|piper|rhvoice, lang: ru|en|de. Нескачанные голоса скачаются при первом speak."""
    try:
        voices = [v.to_dict() for v in all_voices(engine, lang) if v.installed or not installed_only]
    except KeyError:
        raise ToolError(f"engine должен быть одним из: {', '.join(ENGINE_NAMES)}") from None
    return {"defaults": {lg: default_voice(lg) for lg in LANGS}, "voices": voices}


def run() -> None:
    mcp.run()
