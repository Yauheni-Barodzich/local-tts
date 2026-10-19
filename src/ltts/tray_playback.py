"""Обратная совместимость: трей-анимация и JS API."""

from __future__ import annotations

from .playback_hub import (
    DesktopJsApi,
    PlaybackHub,
    PlaybackState,
    TrayPlaybackAnimator,
    load_tray_animation_frames,
)

# TrayPlaybackAnimator = alias
TrayPlaybackAnimator = PlaybackHub

__all__ = [
    "DesktopJsApi",
    "PlaybackHub",
    "PlaybackState",
    "TrayPlaybackAnimator",
    "load_tray_animation_frames",
]
