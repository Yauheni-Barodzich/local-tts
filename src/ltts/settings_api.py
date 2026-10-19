"""Снимок и применение настроек для веб-UI (/api/settings)."""

from __future__ import annotations

import os
from typing import Any

from . import __version__
from .core import (
    RATES,
    default_rate,
    default_voice,
    downloads_for_platform,
    load_config,
    out_keep_limit,
    resolve,
    save_config,
)
from . import paths
from .mcp_http import MCP_MOUNT_PATH, mcp_http_enabled, mcp_http_url
from .paths import DEFAULT_HOST, DEFAULT_PORT, IS_WINDOWS
from .text import LANGS
from .pronunciation import get_lexicon, load_lexicon


def _env_overrides() -> dict[str, str]:
    keys = (
        "LTTS_HOME",
        "LTTS_RATE",
        "LTTS_VOICE",
        "LTTS_VOICE_EN",
        "LTTS_VOICE_DE",
        "LTTS_OUT_KEEP",
        "LTTS_PRONUNCIATION",
        "LTTS_PORT",
        "LTTS_URL",
    )
    return {k: os.environ[k] for k in keys if os.environ.get(k)}


def settings_snapshot() -> dict[str, Any]:
    cfg = load_config()
    lex = get_lexicon()
    defaults = {lang: default_voice(lang) for lang in LANGS}
    pron_cfg = cfg.get("pronunciation") or {}
    return {
        "version": __version__,
        "platform": {"windows": IS_WINDOWS, "rhvoice": not IS_WINDOWS},
        "paths": {
            "home": str(paths.HOME),
            "models": str(paths.MODELS),
            "out": str(paths.OUT),
            "pronunciation": str(paths.PRONUNCIATION),
            "config": str(paths.CONFIG),
        },
        "config": cfg,
        "effective": {
            "default_voices": defaults,
            "sample_rate": default_rate(),
            "out_keep": out_keep_limit(),
        },
        "env_readonly": _env_overrides(),
        "pronunciation": {
            "enabled": lex.enabled,
            "stats": lex.stats,
            "dir": lex.stats.get("dir"),
            "paths": [str(p) for p in (pron_cfg.get("paths") or [])],
        },
        "recommended_downloads": downloads_for_platform(),
        "sample_rates": list(RATES),
        "integrations": {
            "mcp_stdio": "ltts mcp",
            "mcp_http": mcp_http_url(DEFAULT_HOST, DEFAULT_PORT) if mcp_http_enabled() else None,
            "mcp_http_path": MCP_MOUNT_PATH if mcp_http_enabled() else None,
        },
    }


def _validate_voice_id(voice_id: str, lang: str) -> str:
    voice_id = voice_id.strip().lower()
    resolve(voice_id, lang)
    return voice_id


def apply_settings(patch: dict[str, Any]) -> dict[str, Any]:
    if not patch:
        return settings_snapshot()
    cfg = load_config()

    if "default_voices" in patch and patch["default_voices"] is not None:
        dv = patch["default_voices"]
        if not isinstance(dv, dict):
            raise ValueError("default_voices должен быть объектом {ru, en, de}")
        voices = cfg.setdefault("default_voices", {})
        cfg.pop("default_voice", None)
        for lang in LANGS:
            if lang not in dv or dv[lang] is None:
                continue
            voices[lang] = _validate_voice_id(str(dv[lang]), lang)

    if "sample_rate" in patch:
        sr = patch["sample_rate"]
        if sr is None or sr == "":
            cfg.pop("sample_rate", None)
        else:
            rate = int(sr)
            if rate not in RATES:
                raise ValueError(f"sample_rate: одно из {', '.join(map(str, RATES))}")
            cfg["sample_rate"] = rate

    if "out_keep" in patch and patch["out_keep"] is not None:
        keep = int(patch["out_keep"])
        if keep < 0 or keep > 1000:
            raise ValueError("out_keep: от 0 до 1000")
        cfg["out_keep"] = keep

    if "pronunciation" in patch and isinstance(patch["pronunciation"], dict):
        pron = patch["pronunciation"]
        if "enabled" in pron:
            p = cfg.setdefault("pronunciation", {})
            p["enabled"] = bool(pron["enabled"])

    save_config(cfg)
    if "pronunciation" in patch:
        load_lexicon(force=True)
    return settings_snapshot()
