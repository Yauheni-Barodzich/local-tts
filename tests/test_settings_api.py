import json

import pytest
from fastapi.testclient import TestClient

from ltts.paths import CONFIG
from ltts.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("ltts.paths.HOME", tmp_path)
    monkeypatch.setattr("ltts.paths.CONFIG", tmp_path / "config.json")
    monkeypatch.setattr("ltts.paths.MODELS", tmp_path / "models")
    monkeypatch.setattr("ltts.paths.OUT", tmp_path / "out")
    monkeypatch.setattr("ltts.paths.PRONUNCIATION", tmp_path / "pronunciation")
    monkeypatch.setattr("ltts.core.CONFIG", tmp_path / "config.json")
    monkeypatch.setattr("ltts.pronunciation.PRONUNCIATION", tmp_path / "pronunciation")
    return TestClient(app)


def test_get_settings(client, tmp_path):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert data["paths"]["home"] == str(tmp_path)
    assert "effective" in data


def test_patch_sample_rate_and_out_keep(client):
    r = client.patch("/api/settings", json={"sample_rate": 48000, "out_keep": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["config"]["sample_rate"] == 48000
    assert data["config"]["out_keep"] == 50
    assert CONFIG.read_text(encoding="utf-8")


def test_patch_invalid_sample_rate(client):
    r = client.patch("/api/settings", json={"sample_rate": 12345})
    assert r.status_code == 400


def test_lexicon_reload(client):
    r = client.post("/api/lexicon/reload")
    assert r.status_code == 200
    assert r.json()["ok"] is True
