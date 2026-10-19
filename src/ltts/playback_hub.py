"""Состояние воспроизведения: трей, API аватара, окно у трея."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .avatar_window import AvatarWindowController
from .tray import _load_icon_image
from .viseme import schedule_from_text, viseme_at

_IDLE_TITLE = "ltts — локальный TTS"
_PLAY_TITLE = "ltts — воспроизведение…"
_FRAME_INTERVAL = 0.12


@dataclass
class PlaybackState:
    refcount: int = 0
    level: float = 0.0
    speech_text: str = ""
    speech_duration: float = 0.0
    speech_started: float = 0.0
    viseme_schedule: list[dict[str, float]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def delta(self, n: int) -> bool:
        with self.lock:
            prev = self.refcount > 0
            self.refcount = max(0, self.refcount + n)
            if self.refcount == 0:
                self.level = 0.0
                self.viseme_schedule = []
            now = self.refcount > 0
            return prev != now

    def set_level(self, level: float) -> None:
        with self.lock:
            if self.refcount > 0:
                self.level = max(0.0, min(1.0, float(level)))

    def start_speech(self, text: str, duration: float) -> None:
        with self.lock:
            self.speech_text = text
            self.speech_duration = max(0.0, float(duration))
            self.speech_started = time.monotonic()
            self.viseme_schedule = schedule_from_text(text, self.speech_duration)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            playing = self.refcount > 0
            elapsed = time.monotonic() - self.speech_started if playing and self.speech_started else 0.0
            viseme = viseme_at(self.viseme_schedule, elapsed) if playing else "closed"
            return {
                "playing": playing,
                "level": self.level if playing else 0.0,
                "viseme": viseme,
                "elapsed": round(elapsed, 3),
                "duration": self.speech_duration,
                "schedule": list(self.viseme_schedule),
            }


# --- tray frames (from tray_playback) ---

def _draw_tray_frame(size: int, bar_heights: tuple[float, ...], dot_scale: float) -> object:
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
        d.rounded_rectangle((x, base_y - bh, x + bar_w, base_y), radius=max(1, bar_w / 2), fill=fg)
        x += bar_w + gap
    cx, cy = size * 0.82, size * 0.18
    rad = size * 0.09 * dot_scale
    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=dot, outline=fg, width=max(1, size // 18))
    return img


_FRAME_SPECS: tuple[tuple[tuple[float, ...], float], ...] = (
    ((0.35, 0.55, 0.95, 0.5, 0.75, 0.35), 1.0),
    ((0.5, 0.75, 0.55, 0.9, 0.45, 0.6), 1.15),
    ((0.75, 0.45, 0.7, 0.55, 1.0, 0.5), 0.95),
    ((0.55, 0.9, 0.4, 0.8, 0.6, 0.85), 1.2),
    ((0.4, 0.65, 0.85, 0.45, 0.7, 1.0), 1.05),
    ((0.6, 0.5, 0.65, 0.95, 0.5, 0.7), 0.9),
)


def load_tray_animation_frames(size: int = 64) -> tuple[object, list[object]]:
    from PIL import Image

    try:
        idle = _load_icon_image().resize((size, size), Image.Resampling.LANCZOS)
    except OSError:
        idle = _draw_tray_frame(size, _FRAME_SPECS[0][0], 1.0)
    frames = [_draw_tray_frame(size, bars, dot) for bars, dot in _FRAME_SPECS]
    return idle, frames


_hub: PlaybackHub | None = None


def set_playback_hub(hub: PlaybackHub | None) -> None:
    global _hub
    _hub = hub


def get_playback_hub() -> PlaybackHub | None:
    return _hub


class PlaybackHub:
    """Трей-анимация + окно аватара."""

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
        self.avatar = AvatarWindowController()

    @property
    def state(self) -> PlaybackState:
        return self._state

    def playback_delta(self, delta: int) -> bool:
        if self._state.delta(int(delta)):
            self._cmds.put("sync")
            return True
        return False

    def playback_level(self, level: float) -> None:
        self._state.set_level(level)

    def playback_speech(self, text: str, duration: float) -> None:
        self._state.start_speech(text, duration)

    def attach_tray(self, icon) -> None:
        self._icon = icon
        self._idle, self._frames = load_tray_animation_frames()
        icon.visible = True
        self._stop.clear()
        self._pump = threading.Thread(target=self._run_pump, name="ltts-playback-pump", daemon=True)
        self._pump.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._cmds.put(None)
        self.avatar.shutdown()
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
                self._icon.title = _IDLE_TITLE
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
                self._icon.title = _IDLE_TITLE
                if self._idle is not None:
                    self._icon.icon = self._idle
                self._frame_idx = 0
        except Exception:
            pass


class DesktopJsApi:
    def __init__(self, hub: PlaybackHub, app_url: Callable[[], str] | None = None) -> None:
        self._hub = hub
        self._app_url = app_url

    def desktop_app_url(self) -> str:
        if self._app_url:
            return self._app_url() or ""
        return ""

    def playback_delta(self, delta: int) -> None:
        hub = self._hub
        if hub.playback_delta(delta):
            hub.avatar.sync_playing(hub._state.refcount > 0)

    def playback_level(self, level: float) -> None:
        self._hub.playback_level(level)

    def playback_speech(self, text: str, duration: float) -> None:
        self._hub.playback_speech(text, duration)
