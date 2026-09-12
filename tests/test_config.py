"""Tests for persistent user configuration."""

from __future__ import annotations

import json

import voiceflow.config as config_module


def test_config_is_saved_in_local_app_data(monkeypatch, tmp_path):
    config_path = tmp_path / "RechType" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(
        config_module,
        "LEGACY_CONFIG_PATH",
        tmp_path / "legacy" / "config.json",
    )

    config_module.save_config({"file_gigaam_model": "v3_e2e_rnnt"})

    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "file_gigaam_model": "v3_e2e_rnnt"
    }


def test_legacy_config_is_loaded_when_user_config_is_absent(monkeypatch, tmp_path):
    config_path = tmp_path / "RechType" / "config.json"
    legacy_path = tmp_path / "legacy" / "config.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        json.dumps({"hotkey": "alt+f2"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", legacy_path)

    loaded = config_module.load_config()

    assert loaded["hotkey"] == "alt+f2"
    assert loaded["file_gigaam_model"] == "multilingual_large_ctc"
