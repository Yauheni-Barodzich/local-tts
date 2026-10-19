#!/usr/bin/env python3
"""Собрать app.ico / app.png из web/favicon.png для Windows desktop."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ltts" / "assets"
SOURCE = ROOT / "src" / "ltts" / "web" / "favicon.png"
ICO_SIZES = (256, 128, 64, 48, 32, 16)


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"нет {SOURCE}")
    base = Image.open(SOURCE).convert("RGBA")
    # чётче на больших размерах — из 48px исходника
    large = base.resize((256, 256), Image.Resampling.LANCZOS)
    large.save(SRC / "app.png", format="PNG")
    icons = [large.resize((s, s), Image.Resampling.LANCZOS) for s in ICO_SIZES]
    icons[0].save(SRC / "app.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    # трей: 64px достаточно
    large.resize((64, 64), Image.Resampling.LANCZOS).save(SRC / "tray.png", format="PNG")
    icons[3].save(SRC / "tray.ico", format="ICO", sizes=[(48, 48), (32, 32), (16, 16)])
    print(f"готово: {SRC / 'app.ico'}, app.png, tray.*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
