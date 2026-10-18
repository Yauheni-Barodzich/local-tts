import os
from pathlib import Path

IS_WINDOWS = os.name == "nt"


def _default_home() -> Path:
    if IS_WINDOWS:  # C:\Users\<you>\AppData\Local\ltts
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ltts"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ltts"


HOME = Path(os.environ.get("LTTS_HOME") or _default_home()).expanduser()
MODELS = HOME / "models"
OUT = HOME / "out"
CONFIG = HOME / "config.json"
PRONUNCIATION = HOME / "pronunciation"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("LTTS_PORT", "8765"))
