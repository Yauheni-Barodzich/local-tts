"""Общее для MLX-движков (Apple Silicon): проверка платформы, загрузка моделей с HF с маркером целостности, кэш."""

import contextlib
import json
import os
import platform
import shutil
import sys
import threading
from pathlib import Path

from ..paths import HOME, MODELS
from .base import EngineError, ModelError

APPLE_SILICON = sys.platform == "darwin" and platform.machine() == "arm64"
MLX_DIR = MODELS / "mlx"
# MLX/Metal в одном процессе — один общий лок на все MLX-модели (GPU всё равно один)
MLX_LOCK = threading.RLock()
_models: dict = {}


def mlx_status() -> tuple[bool, str]:
    if not APPLE_SILICON:
        return False, "только для Mac на Apple Silicon (MLX)"
    try:
        import mlx_audio  # noqa: F401
    except ImportError as e:
        return False, f"не установлен mlx-audio: {e} — переустанови ltts"
    return True, ""


def _repo_dir(repo: str) -> Path:
    return MLX_DIR / repo.replace("/", "--")


def _marker(d: Path) -> Path:
    return d / ".ltts-complete"


def repo_ok(repo: str) -> bool:
    """Скачан полностью: маркер есть и размеры всех файлов совпадают."""
    d = _repo_dir(repo)
    try:
        files = json.loads(_marker(d).read_text())
    except (FileNotFoundError, ValueError):
        return False
    return all((d / f).exists() and (d / f).stat().st_size == size for f, size in files.items())


def fetch_repo(repo: str) -> Path:
    from huggingface_hub import snapshot_download

    d = _repo_dir(repo)
    _marker(d).unlink(missing_ok=True)
    try:
        with quiet_stdout():
            snapshot_download(repo, local_dir=d)
    except Exception as e:
        raise EngineError(f"не удалось скачать {repo}: {e}") from e
    files = {
        str(p.relative_to(d)): p.stat().st_size
        for p in d.rglob("*")
        if p.is_file() and ".cache" not in p.parts and p.name != _marker(d).name
    }
    _marker(d).write_text(json.dumps(files))
    return d


def reset_repo(repo: str) -> None:
    with MLX_LOCK:
        _models.pop(repo, None)
    shutil.rmtree(_repo_dir(repo), ignore_errors=True)


def load(repo: str):
    """Загружает (и кэширует) MLX-модель; битую — удаляет и сообщает ModelError."""
    with MLX_LOCK:
        if repo not in _models:
            from mlx_audio.tts.utils import load_model

            try:
                _models[repo] = load_model(str(_repo_dir(repo)))
            except Exception as e:
                reset_repo(repo)
                raise ModelError(f"модель {repo} не загрузилась и удалена ({e}); следующий вызов скачает её заново") from e
        return _models[repo]


def fix_espeak_path() -> None:
    """espeak-ng обрезает путь к данным примерно до 160 символов и молча падает (exit) на длинном пути
    (например, в uv tool в длинном домашнем каталоге). Если путь длинный — кладём копию данных в LTTS_HOME."""
    import espeakng_loader
    import misaki.espeak  # noqa: F401  — при импорте выставляет свой (длинный) путь, поэтому сначала он
    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    src_data, src_lib = Path(espeakng_loader.get_data_path()), Path(espeakng_loader.get_library_path())
    if len(str(src_data.resolve())) < 140:
        return
    dst = HOME / "espeak"
    if not (dst / "espeak-ng-data" / "phontab").exists():
        tmp = dst.with_name("espeak.tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(src_data, tmp / "espeak-ng-data")
        shutil.copy2(src_lib, tmp / src_lib.name)
        shutil.rmtree(dst, ignore_errors=True)
        tmp.rename(dst)
    if len(str(dst.resolve())) >= 140:
        raise EngineError(f"путь {dst} слишком длинный для espeak-ng — задай короткий LTTS_HOME")
    EspeakWrapper.set_library(str(dst / src_lib.name))
    EspeakWrapper.set_data_path(str(dst / "espeak-ng-data"))


@contextlib.contextmanager
def quiet_stdout():
    """mlx-audio печатает служебное в stdout — это ломает --json и `-o -`. Уводим в stderr."""
    with contextlib.redirect_stdout(sys.stderr):
        yield


def to_numpy(results) -> tuple:
    """Склеивает чанки генератора mlx-audio в float32 numpy и возвращает (samples, sample_rate)."""
    import numpy as np

    chunks, rate = [], None
    for r in results:
        chunks.append(np.asarray(r.audio, dtype=np.float32).reshape(-1))
        rate = getattr(r, "sample_rate", None) or rate
    if not chunks:
        raise EngineError("модель вернула пустое аудио")
    return np.concatenate(chunks), rate


os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
