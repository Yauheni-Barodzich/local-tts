import json
import tempfile
from pathlib import Path

from ltts.pronunciation import Lexicon, load_lexicon, invalidate_cache


def test_apply_word_and_phrase():
    lex = Lexicon(
        words={"замок": "з+амок"},
        phrases=[("московский метро", "моск+овский метр+о")],
    )
    assert lex.apply_ru("У замок.") == "У з+амок."
    assert "моск+овский" in lex.apply_ru("В московский метро едут все.")


def test_load_from_dir(tmp_path, monkeypatch):
    d = tmp_path / "pronunciation"
    d.mkdir(parents=True)
    (d / "a.json").write_text(json.dumps({"words": {"тест": "т+ест"}}), encoding="utf-8")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"pronunciation": {"enabled": True}}), encoding="utf-8")
    monkeypatch.setattr("ltts.paths.HOME", tmp_path)
    monkeypatch.setattr("ltts.paths.PRONUNCIATION", d)
    monkeypatch.setattr("ltts.paths.CONFIG", cfg)
    monkeypatch.setattr("ltts.pronunciation.CONFIG", cfg)
    monkeypatch.setattr("ltts.pronunciation.PRONUNCIATION", d)
    invalidate_cache()
    lex = load_lexicon(force=True)
    assert lex.words.get("тест") == "т+ест"


if __name__ == "__main__":
    test_apply_word_and_phrase()
    print("ok")
