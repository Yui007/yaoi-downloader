from __future__ import annotations

import json

from yaoi import config


def test_save_load_and_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"
    data = config.load_settings(path)
    data["custom"] = {"keep": 1}
    data["download"]["images_workers"] = 9
    config.save_settings(data, path)
    assert not (tmp_path / "settings.json.part").exists()
    loaded = config.load_settings(path)
    assert loaded["custom"] == {"keep": 1}
    assert loaded["download"]["images_workers"] == 9


def test_corrupt_file_is_quarantined(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = config.load_settings(path)
    assert loaded["version"] == 1
    assert (tmp_path / "settings.json.bad").exists()


def test_env_overrides(monkeypatch):
    settings = config.load_settings()
    monkeypatch.setenv("YAOI_DOWNLOAD_FORMAT", "pdf")
    assert config.resolve(settings, "download", "format") == "pdf"
    assert config.resolve(settings, "download", "format", "cbz") == "cbz"
