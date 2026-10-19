from ltts.desktop_setup import (
    DESKTOP_SETUP_VERSION,
    desktop_setup_complete,
    mark_desktop_setup_complete,
    minimal_desktop_downloads,
    needs_desktop_setup,
)


def test_minimal_downloads():
    assert minimal_desktop_downloads() == ["silero:kseniya"]


def test_setup_flags(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr("ltts.desktop_setup.HOME", tmp_path)
    monkeypatch.setattr("ltts.paths.HOME", tmp_path)
    monkeypatch.setattr("ltts.paths.CONFIG", cfg)
    monkeypatch.setattr("ltts.core.CONFIG", cfg)
    assert needs_desktop_setup()
    mark_desktop_setup_complete()
    assert desktop_setup_complete()
    assert not needs_desktop_setup()
    text = cfg.read_text(encoding="utf-8")
    assert str(DESKTOP_SETUP_VERSION) in text
