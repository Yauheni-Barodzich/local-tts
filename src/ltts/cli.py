"""ltts — локальный синтез речи. Дружит с агентами: --json, stdin, коды выхода, без интерактива."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .client import DEFAULT_TIMEOUT, server_alive, server_url, synth_auto
from .paths import DEFAULT_HOST, DEFAULT_PORT
from .text import LANGS

def _step(msg: str) -> None:
    print(f"  → {msg}", file=sys.stderr, flush=True)


EXAMPLES = """
примеры:
  ltts say "Привет, мир" --play
  echo "Текст из пайпа" | ltts say -v piper:denis -o out.mp3
  ltts say "Быстрее" -s 1.3 --json
  ltts say "Hello from local TTS"   # английский — сам выберет английский голос (Kokoro)
  ltts clone add me me.wav --text "что сказано в записи"
  ltts say "Hello, it's me" -v clone:me [--hq]
  ltts voices --installed
  ltts serve --open                 # веб-морда на http://127.0.0.1:8765
  claude mcp add ltts -- ltts mcp   # подключить как MCP-сервер
"""


def play(path: Path) -> None:
    """Проигрывает файл: afplay (macOS), winsound (Windows), paplay/pw-play/aplay/ffplay (Linux).
    Всё, кроме wav, сначала декодируется во временный wav — aplay/winsound не умеют mp3/ogg."""
    import tempfile

    if shutil.which("afplay"):  # macOS играет всё сам
        subprocess.run(["afplay", str(path)], check=False)
        return
    with tempfile.TemporaryDirectory() as tmp:
        wav = path
        if path.suffix.lower() != ".wav":
            import soundfile as sf

            data, rate = sf.read(str(path), dtype="float32")
            wav = Path(tmp) / "play.wav"
            sf.write(str(wav), data, rate, subtype="PCM_16")
        if os.name == "nt":
            import winsound

            winsound.PlaySound(str(wav), winsound.SND_FILENAME)
            return
        for cmd in (["paplay"], ["pw-play"], ["aplay", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
            if shutil.which(cmd[0]):
                subprocess.run([*cmd, str(wav)], check=False)
                return
    print("не нашёл чем проиграть (paplay/pw-play/aplay/ffplay)", file=sys.stderr)


def emit(args, data: dict, human: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(human)


# ---------- команды ----------


def cmd_say(args) -> int:
    from .audio import ALL_FORMATS

    text = " ".join(args.text) if args.text and args.text != ["-"] else sys.stdin.read()
    if not text.strip():
        raise RuntimeError("пустой текст: передай аргументом или через stdin")

    to_stdout = args.output == "-"
    fmt = (args.format or (Path(args.output).suffix.lstrip(".") if args.output and not to_stdout else "") or "wav").lower()
    if fmt not in ALL_FORMATS:
        raise RuntimeError(f"формат {fmt!r} не поддерживается, есть: {', '.join(ALL_FORMATS)}")
    if fmt == "aac" and not shutil.which("ffmpeg"):
        raise RuntimeError("для aac нужен ffmpeg в PATH; mp3/ogg/opus/flac/wav работают без него")

    voice = args.voice
    if args.hq:
        if not voice or not voice.startswith(("clone:", "clonehq:")):
            raise RuntimeError("--hq работает только с клонированными голосами: -v clone:<имя> --hq")
        voice = "clonehq:" + voice.split(":", 1)[1]
    _step("синтез речи")
    data, meta = synth_auto(text, voice, args.speed, fmt, args.lang, args.rate, args.local, args.timeout)
    _step("готово")

    if to_stdout:
        sys.stdout.buffer.write(data)
        sys.stdout.flush()
        return 0

    if args.output:
        path = Path(args.output).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        from .core import out_path

        path = out_path(fmt)
    path.write_bytes(data)
    from .core import ordered

    meta.update(ok=True, path=str(path), format=fmt, bytes=len(data))
    emit(args, ordered(meta), str(path))
    if args.play:
        play(path)
    return 0


def cmd_voices(args) -> int:
    from .core import all_voices, default_voice

    _step("каталог голосов")
    voices = all_voices(args.engine, args.lang, on_step=lambda n: _step(f"{n}: проверка…"))
    _step("готово")
    if args.installed:
        voices = [v for v in voices if v.installed]
    defaults = {lang: default_voice(lang) for lang in LANGS}
    if args.json:
        out = {"default": defaults["ru"], "defaults": defaults, "voices": [v.to_dict() for v in voices]}
        print(json.dumps(out, ensure_ascii=False))
        return 0
    for v in voices:
        mark = "●" if v.installed else "○"
        star = f" ← по умолчанию ({v.lang})" if defaults.get(v.lang) == v.id else ""
        print(f"{mark} {v.id:<22} {v.lang}  {v.gender:<7}{star}")
    sys.stdout.flush()
    print("\n● скачан  ○ скачается при первом использовании или через `ltts download`", file=sys.stderr)
    return 0


def cmd_download(args) -> int:
    from .core import ENGINES, download, downloads_for_platform

    ids = list(args.voices)
    if args.defaults or not ids:
        ids += downloads_for_platform()
    for e in args.all or []:
        ids += [v.id for v in ENGINES[e].voices()]
    results, failed = [], 0
    for vid in dict.fromkeys(ids):
        _step(f"скачивание {vid}")
        try:
            v = download(vid, args.force)
            results.append({"id": v.id, "ok": True})
            if not args.json:
                print(f"✓ {v.id}", file=sys.stderr)
        except Exception as e:
            failed += 1
            results.append({"id": vid, "ok": False, "error": str(e)})
            if not args.json:
                print(f"✗ {vid}: {e}", file=sys.stderr)
    if args.json:
        print(json.dumps({"ok": not failed, "results": results}, ensure_ascii=False))
    return 1 if failed else 0


def cmd_clone(args) -> int:
    from . import clones
    from .core import ENGINES

    if "clone" not in ENGINES:
        raise RuntimeError("клонирование голоса доступно только на Mac с Apple Silicon")

    if args.action in ("add", "rm") and not args.name:
        raise RuntimeError(f"ltts clone {args.action} <имя>" + (" <образец.wav>" if args.action == "add" else ""))
    if args.action == "add" and not args.audio:
        raise RuntimeError("укажи файл образца: ltts clone add <имя> <образец.wav>")

    if args.action == "add":
        data = sys.stdin.buffer.read() if args.audio == "-" else Path(args.audio).expanduser().read_bytes()
        c = clones.add(args.name, data, args.text or "", args.gender or "", overwrite=args.force)
        hint = "" if c.text else "  (без --text: обычный клон работает, для --hq нужен текст образца)"
        emit(args, {"ok": True, "voice": f"clone:{c.slug}", **c.to_dict()},
             f"✓ clone:{c.slug} — {c.duration:g} с образца{hint}")
    elif args.action == "list":
        items = clones.all_clones()
        if args.json:
            print(json.dumps({"clones": [{"voice": f"clone:{c.slug}", **c.to_dict()} for c in items]}, ensure_ascii=False))
        else:
            for c in items:
                print(f"clone:{c.slug:<20} {c.duration:>5.1f} с  {c.gender or '—':<7} {'текст есть' if c.text else 'без текста (нет HQ)'}")
            if not items:
                print("клонов пока нет — `ltts clone add <имя> <образец.wav> [--text …]`", file=sys.stderr)
    elif args.action == "rm":
        clones.remove(clones.slugify(args.name))
        emit(args, {"ok": True}, f"удалён {args.name}")
    return 0


def cmd_default(args) -> int:
    """Без аргумента — показать; с голосом — сделать его дефолтом для его языка."""
    from .core import default_voice, load_config, resolve, save_config, voice_info

    if args.voice:
        eng, name = resolve(args.voice)
        lang = voice_info(eng, name).lang
        cfg = load_config()
        cfg.pop("default_voice", None)
        cfg.setdefault("default_voices", {})[lang] = f"{eng.name}:{name}"
        save_config(cfg)
    defaults = {lang: default_voice(lang) for lang in LANGS}
    emit(args, {"default_voices": defaults}, "\n".join(f"{k}: {v}" for k, v in defaults.items()))
    return 0


def cmd_doctor(args) -> int:
    from .core import doctor, verify_models

    if args.verify:
        _step("проверка sha256 моделей…")
    checked = verify_models() if args.verify else None  # сначала проверка: битые удаляются и пропадают из статуса
    _step("состояние движков")
    info = doctor(on_step=lambda n: _step(f"{n}…"))
    if checked is not None:
        info["verify"] = checked
    info["server"] = {"url": server_url(), "running": server_alive()}
    info["ffmpeg"] = bool(shutil.which("ffmpeg"))
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"ltts {info['version']}  ·  данные: {info['home']}")
        print("голоса по умолчанию: " + ", ".join(f"{k} → {v}" for k, v in info["default_voices"].items()))
        for name, e in info["engines"].items():
            mark = "✓" if e["ok"] else "✗"
            voices = ", ".join(v.split(":")[1] for v in e["installed_voices"]) or "голосов нет"
            print(f"  {mark} {name:<8} {voices}")
            if e["hint"] and not e["ok"] and e["installable"]:
                print(f"      → {e['hint']}")
        srv = info["server"]
        print(f"сервер: {srv['url']} — {'запущен' if srv['running'] else 'не запущен (`ltts serve`)'}")
        print(f"ffmpeg: {'есть' if info['ffmpeg'] else 'нет (нужен только для aac)'}")
        if "verify" in info:
            v = info["verify"]
            bad = ", ".join(v["corrupt"]) or "нет"
            print(f"проверка sha256: {v['checked']} файлов, битых: {bad}" + (" (удалены, скачаются заново)" if v["corrupt"] else ""))
    return 0 if any(e["ok"] and e["installed_voices"] for e in info["engines"].values()) else 1


def cmd_serve(args) -> int:
    import socket
    import threading
    import webbrowser

    _step("подготовка HTTP-сервера")
    _step("загрузка веб-приложения (10–30 с, torch/FastAPI)")
    import uvicorn

    from .server import app

    _step("приложение загружено")

    url = f"http://{args.host}:{args.port}"
    if server_alive(url, timeout=1):
        _step(f"уже запущен: {url}")
        print(f"ltts уже запущен: {url} — переиспользуй его (CLI и MCP подхватят сами)", file=sys.stderr)
        if args.open:
            webbrowser.open(url)
        return 0
    _step(f"проверка порта {args.port}")
    with socket.socket() as sock:
        try:
            sock.bind((args.host, args.port))
        except OSError:
            raise RuntimeError(f"порт {args.port} занят другим процессом — `ltts serve --port <другой>` и LTTS_URL для клиентов") from None
    _step(f"слушаю {url}  (Ctrl+C — остановка)")
    print(f"ltts: {url}  (OpenAI API: {url}/v1/audio/speech)", file=sys.stderr)
    if args.open:
        _step("браузер откроется через 1 с")
        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_mcp(args) -> int:
    from .mcp_server import run

    run()
    return 0


def cmd_setup(args) -> int:
    """Первичная настройка: голоса по умолчанию + сборка RHVoice."""
    from .core import ENGINES, download, downloads_for_platform

    rhv = ENGINES.get("rhvoice")
    if rhv and args.rhvoice:
        from .engines.rhvoice import build

        if not rhv.bin.exists() and not rhv.installable():
            print(f"→ RHVoice пропускаю: {rhv.status()[1]}", file=sys.stderr)
        elif not rhv.bin.exists():
            print("→ собираю RHVoice (1–3 минуты)…", file=sys.stderr)
            try:
                build(["anna", "aleksandr"])
            except Exception as e:
                print(f"✗ RHVoice: {e}\n  остальные движки работают; повторить: `ltts setup --rhvoice`", file=sys.stderr)

    targets = [v for v in downloads_for_platform() if (not v.startswith("rhvoice:") or (rhv and rhv.bin.exists()))
               and ENGINES[v.split(":")[0]].installable()]
    _step(f"голосов к установке: {len(targets)}")
    for vid in targets:
        _step(f"скачивание {vid}")
        try:
            download(vid)
            print(f"✓ {vid}", file=sys.stderr)
        except Exception as e:
            print(f"✗ {vid}: {e}", file=sys.stderr)
    return cmd_doctor(argparse.Namespace(json=False, verify=False))


# ---------- парсер ----------


def build_parser() -> argparse.ArgumentParser:
    from . import __version__
    from .core import ENGINE_NAMES

    p = argparse.ArgumentParser(
        prog="ltts",
        description="Локальный синтез речи (русский, английский, немецкий): Silero, Piper, RHVoice, Kokoro, клоны.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"ltts {__version__} ({platform.system()})")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("say", help="озвучить текст (аргумент или stdin)")
    s.add_argument("text", nargs="*", help="текст; без него или '-' — читается stdin")
    s.add_argument("-v", "--voice", help="engine:voice, просто voice или просто engine (по умолчанию — см. `ltts default`)")
    s.add_argument("-s", "--speed", type=float, default=1.0, help="скорость 0.25–4.0 (по умолчанию 1.0)")
    s.add_argument("-o", "--output", help="файл (формат по расширению) или '-' для stdout")
    s.add_argument("-f", "--format", help="wav|mp3|ogg|opus|flac|aac|pcm")
    s.add_argument("-l", "--lang", choices=["auto", *LANGS], default="auto",
                   help="язык текста; auto (по умолчанию) — определить и подобрать голос того же движка и пола")
    s.add_argument("-p", "--play", action="store_true", help="проиграть после синтеза")
    s.add_argument("--json", action="store_true", help="метаданные в JSON")
    s.add_argument("--hq", action="store_true", help="для клонов: VoxCPM2, 48 кГц, медленнее (нужен текст образца)")
    s.add_argument("-r", "--rate", type=int, help="частота на выходе, Гц (48000, 24000, …); по умолчанию родная у движка или LTTS_RATE")
    s.add_argument("--local", action="store_true", help="не использовать запущенный сервер")
    s.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                   help=f"сколько ждать сервер, с (по умолчанию {DEFAULT_TIMEOUT:g}, LTTS_TIMEOUT); потом — локально")
    s.set_defaults(fn=cmd_say)

    s = sub.add_parser("voices", help="список голосов")
    s.add_argument("-e", "--engine", choices=ENGINE_NAMES)
    s.add_argument("-l", "--lang", choices=list(LANGS))
    s.add_argument("-i", "--installed", action="store_true", help="только скачанные")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_voices)

    s = sub.add_parser("download", help="скачать голоса (без аргументов — набор по умолчанию)")
    s.add_argument("voices", nargs="*", help="например silero:xenia piper:denis rhvoice:tatiana")
    s.add_argument("--defaults", action="store_true", help="добавить набор по умолчанию")
    s.add_argument("--all", action="append", choices=ENGINE_NAMES, help="все голоса движка")
    s.add_argument("--force", action="store_true", help="удалить и скачать заново")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_download)

    if "clone" in ENGINE_NAMES:
        s = sub.add_parser("clone", help="клонирование голоса: add / list / rm (Apple Silicon)")
        s.add_argument("action", choices=["add", "list", "rm"])
        s.add_argument("name", nargs="?", help="имя голоса (для add/rm)")
        s.add_argument("audio", nargs="?", help="образец речи 8–20 с: wav/mp3/flac/ogg или '-' для stdin")
        s.add_argument("--text", help="что сказано в образце (нужно для --hq, улучшает похожесть)")
        s.add_argument("--gender", choices=["female", "male"])
        s.add_argument("--force", action="store_true", help="перезаписать существующий")
        s.add_argument("--json", action="store_true")
        s.set_defaults(fn=cmd_clone)

    s = sub.add_parser("default", help="показать/задать голос по умолчанию (для языка этого голоса)")
    s.add_argument("voice", nargs="?")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_default)

    s = sub.add_parser("doctor", help="что установлено и что сломано")
    s.add_argument("--verify", action="store_true", help="сверить sha256 всех моделей, битые удалить")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("serve", help="веб-морда + HTTP API (в т.ч. OpenAI /v1/audio/speech)")
    s.add_argument("--host", default=DEFAULT_HOST)
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--open", action="store_true", help="открыть в браузере")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("mcp", help="MCP-сервер (stdio) для агентов")
    s.set_defaults(fn=cmd_mcp)

    s = sub.add_parser("setup", help="скачать голоса по умолчанию и (опц.) собрать RHVoice")
    s.add_argument("--rhvoice", action=argparse.BooleanOptionalAction, default=True, help="собрать RHVoice")
    s.set_defaults(fn=cmd_setup)
    return p


def main(argv=None) -> int:
    if os.name == "nt":  # на Windows пайпы по умолчанию в cp1251/cp866 — кириллица в JSON и stdin ломается
        for stream in (sys.stdout, sys.stderr, sys.stdin):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.cmd in ("voices", "doctor", "setup", "download", "say", "serve"):
        _step(f"команда {args.cmd}")
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            print(f"ltts: ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
