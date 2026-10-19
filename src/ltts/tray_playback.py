"""Состояние воспроизведения и анимация иконки трея (Windows desktop)."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field

from .tray import _load_icon_image

_IDLE_TITLE = "ltts — локальный TTS"
_PLAY_TITLE = "ltts — воспроизведение…"
_FRAME_INTERVAL = 0.12


def _draw_tray_frame(size: int, bar_heights: tuple[float, ...], dot_scale: float) -> "object":
    from PIL import Image, ImageDraw

    bg = (15, 23, 42, 255)
    fg = (248, 250, 252, 255)
    dot = (220, 38, 38, 255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = max(2, size // 9)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=bg)

    n = len(bar_heights)
    pad_x = size * 0.22
    inner_w = size - 2 * pad_x
    bar_w = max(1, inner_w / (n * 2.2))
    gap = bar_w * 1.2
    max_h = size * 0.42
    base_y = size * 0.72
    x = pad_x
    for h in bar_heights:
        bh = max(size * 0.06, h * max_h)
        d.rounded_rectangle(
            (x, base_y - bh, x + bar_w, base_y),
            radius=max(1, bar_w / 2),
            fill=fg,
        )
        x += bar_w + gap

    cx, cy = size * 0.82, size * 0.18
    rad = size * 0.09 * dot_scale
    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=dot, outline=fg, width=max(1, size // 18))
    return img


# Высоты столбиков по кадрам (0..1), красная точка пульсирует
_FRAME_SPECS: tuple[tuple[tuple[float, ...], float], ...] = (
    ((0.35, 0.55, 0.95, 0.5, 0.75, 0.35), 1.0),
    ((0.5, 0.75, 0.55, 0.9, 0.45, 0.6), 1.15),
    ((0.75, 0.45, 0.7, 0.55, 1.0, 0.5), 0.95),
    ((0.55, 0.9, 0.4, 0.8, 0.6, 0.85), 1.2),
    ((0.4, 0.65, 0.85, 0.45, 0.7, 1.0), 1.05),
    ((0.6, 0.5, 0.65, 0.95, 0.5, 0.7), 0.9),
)


def load_tray_animation_frames(size: int = 64) -> tuple[object, list[object]]:
    """Статичная иконка и кадры анимации (PIL.Image)."""
    from PIL import Image

    try:
        idle = _load_icon_image().resize((size, size), Image.Resampling.LANCZOS)
    except OSError:
        idle = _draw_tray_frame(size, _FRAME_SPECS[0][0], 1.0)
    frames = [_draw_tray_frame(size, bars, dot) for bars, dot in _FRAME_SPECS]
    return idle, frames


@dataclass
class PlaybackState:
    refcount: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def delta(self, n: int) -> bool:
        """Изменить счётчик; True если перешли idle↔playing."""
        with self.lock:
            prev = self.refcount > 0
            self.refcount = max(0, self.refcount + n)
            now = self.refcount > 0
            return prev != now


class TrayPlaybackAnimator:
    """Обновляет pystray.Icon по сигналам из WebView (refcount воспроизведения)."""

    def __init__(self) -> None:
        self._state = PlaybackState()
        self._cmds: queue.Queue[str | None] = queue.Queue()
        self._pump: threading.Thread | None = None
        self._icon = None
        self._idle = None
        self._frames: list = []
        self._frame_idx = 0
        self._playing = False
        self._stop = threading.Event()
        self._idle_title = _IDLE_TITLE

    def playback_delta(self, delta: int) -> None:
        if self._state.delta(int(delta)):
            self._cmds.put("sync")

    def attach(self, icon) -> None:
        """Вызывать из pystray setup (после создания Icon)."""
        self._icon = icon
        self._idle, self._frames = load_tray_animation_frames()
        icon.visible = True
        self._stop.clear()
        self._pump = threading.Thread(target=self._run_pump, name="ltts-tray-anim", daemon=True)
        self._pump.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._cmds.put(None)
        if self._pump:
            self._pump.join(timeout=2)

    def _run_pump(self) -> None:
        while not self._stop.is_set():
            deadline = time.monotonic() + _FRAME_INTERVAL
            try:
                while True:
                    cmd = self._cmds.get_nowait()
                    if cmd is None:
                        return
                    if cmd == "sync":
                        self._apply_playing(self._state.refcount > 0)
            except queue.Empty:
                pass

            if self._playing and self._icon and self._frames:
                self._frame_idx = (self._frame_idx + 1) % len(self._frames)
                try:
                    self._icon.icon = self._frames[self._frame_idx]
                except Exception:
                    pass

            wait = deadline - time.monotonic()
            if wait > 0:
                time.sleep(wait)

        if self._icon and self._idle is not None:
            try:
                self._icon.icon = self._idle
                self._icon.title = self._idle_title
            except Exception:
                pass

    def _apply_playing(self, on: bool) -> None:
        self._playing = on
        if not self._icon:
            return
        try:
            if on:
                self._icon.title = _PLAY_TITLE
                if self._frames:
                    self._icon.icon = self._frames[0]
            else:
                self._icon.title = self._idle_title
                if self._idle is not None:
                    self._icon.icon = self._idle
                self._frame_idx = 0
        except Exception:
            pass


class DesktopJsApi:
    """API для pywebview: window.pywebview.api.playback_delta(n)."""

    def __init__(self, animator: TrayPlaybackAnimator) -> None:
        self._animator = animator

    def playback_delta(self, delta: int) -> None:
        self._animator.playback_delta(delta)
