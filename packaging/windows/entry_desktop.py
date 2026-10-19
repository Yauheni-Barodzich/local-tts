"""Точка входа PyInstaller: ltts-desktop.exe (без консоли)."""

from ltts.desktop import run_desktop

if __name__ == "__main__":
    raise SystemExit(run_desktop())
