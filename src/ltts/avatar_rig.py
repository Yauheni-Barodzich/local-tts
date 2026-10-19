"""Сборка рига персонажа из одного изображения и прямоугольников."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from .avatar_config import AVATAR_DIR, AVATAR_RIG_JSON

VISEME_NAMES = ("closed", "A", "E", "I", "O", "U", "MBP")


def _rect_norm_to_px(rect: dict, w: int, h: int) -> tuple[int, int, int, int]:
    """rect: x,y,w,h в 0..1."""
    x = int(rect["x"] * w)
    y = int(rect["y"] * h)
    rw = max(1, int(rect["w"] * w))
    rh = max(1, int(rect["h"] * h))
    return x, y, rw, rh


def build_rig_from_upload(
    source_path: Path,
    rig_spec: dict[str, Any],
) -> dict[str, Any]:
    """Сохраняет base.png и mouth_*.png в AVATAR_DIR."""
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(source_path).convert("RGBA")
    w, h = img.size
    mouth = rig_spec.get("mouth") or {"x": 0.35, "y": 0.55, "w": 0.3, "h": 0.12}
    mx, my, mw, mh = _rect_norm_to_px(mouth, w, h)

    base = img.copy()
    # Закрытый рот: залить область рта цветом кожи снизу (упрощение — размытие краёв mouth crop)
    mouth_crop = img.crop((mx, my, mx + mw, my + mh))
    base_draw = base.copy()
    # слегка затемнить зону рта на base
    overlay = Image.new("RGBA", (mw, mh), (0, 0, 0, 40))
    base_draw.paste(overlay, (mx, my), overlay)
    base_draw.save(AVATAR_DIR / "base.png", format="PNG")

    scales = {
        "closed": (1.0, 0.35),
        "A": (1.1, 0.85),
        "E": (1.05, 0.55),
        "I": (0.95, 0.45),
        "O": (1.15, 0.95),
        "U": (0.9, 0.5),
        "MBP": (1.0, 0.15),
    }
    for name, (sx, sy) in scales.items():
        layer = mouth_crop.resize((max(1, int(mw * sx)), max(1, int(mh * sy))), Image.Resampling.LANCZOS)
        out = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
        ox = (mw - layer.width) // 2
        oy = mh - layer.height
        out.paste(layer, (ox, max(0, oy)))
        out.save(AVATAR_DIR / f"mouth_{name}.png", format="PNG")

    meta = {
        "version": 1,
        "size": [w, h],
        "mouth": mouth,
        "eyes": rig_spec.get("eyes"),
        "face": rig_spec.get("face"),
        "visemes": list(VISEME_NAMES),
    }
    AVATAR_RIG_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def rig_manifest() -> dict[str, Any] | None:
    if not AVATAR_RIG_JSON.is_file():
        return None
    meta = json.loads(AVATAR_RIG_JSON.read_text(encoding="utf-8"))
    mouths = {}
    for v in VISEME_NAMES:
        p = AVATAR_DIR / f"mouth_{v}.png"
        if p.is_file():
            mouths[v] = f"/api/avatar/rig/mouth_{v}.png"
    return {
        **meta,
        "base": "/api/avatar/rig/base.png",
        "mouths": mouths,
    }
