"""Bozuk ayarlar ve başarısız kayıtta mevcut veriyi koruma regresyonları."""
import json

import pytest
from cryptography.fernet import Fernet

import xmpp


@pytest.mark.parametrize("payload", [[], None, "settings", 37])
def test_non_object_config_is_rejected(tmp_path, monkeypatch, payload):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(path))

    assert xmpp._load_config() == {}


def test_failed_config_save_preserves_previous_settings(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    original = {"jid": "qa@example.com", "rooms": {"room@conference.example": {}}}
    path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(path))

    xmpp._save_config({"jid": "other@example.com", "invalid": object()})

    assert json.loads(path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.iterdir()) == [path]


def test_encrypted_pin_token_cannot_be_used_as_the_pin(monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: key)
    stored = xmpp._encode_pw("1234")

    assert xmpp._verify_pin(stored, stored) is False
    assert xmpp._verify_pin(stored, "1234") is True
