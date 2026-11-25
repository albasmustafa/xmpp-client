"""Parola şifreleme anahtarı sistem anahtarlığında (Secret Service).

Önceden Fernet anahtarı şifreli parolanın yanındaki dosyadaydı
(.xmpp_client.key): ikisini okuyabilen parolayı da okurdu. Anahtarlık varsa
anahtar orada tutulur, eski dosya taşınıp silinir; yoksa eski davranış.
Gerçek anahtarlığa dokunulmaz: sahte arka uç.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from xmppcore import config as cfgmod  # noqa: E402


class _FakeKeyring:
    def __init__(self, fail_set=False):
        self.items = {}
        self.fail_set = fail_set

    def get_password(self, service, name):
        return self.items.get((service, name))

    def set_password(self, service, name, value):
        if self.fail_set:
            raise RuntimeError("kilitli")
        self.items[(service, name)] = value


@pytest.fixture()
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("XMPP_CLIENT_HOME", str(tmp_path))
    monkeypatch.setattr(cfgmod, "_KEYRING_CACHE", {})
    return tmp_path


def _use(monkeypatch, kr):
    monkeypatch.setattr(cfgmod, "_keyring", lambda: kr)


def test_new_key_goes_to_keyring_not_file(home, monkeypatch):
    kr = _FakeKeyring()
    _use(monkeypatch, kr)
    key = cfgmod._get_fernet_key()
    assert not (home / ".xmpp_client.key").exists()
    name = (home / ".xmpp_client.keyring").read_text().strip()
    assert kr.items[("xmpp-istemcisi", name)] == key.decode()
    assert cfgmod._get_fernet_key() == key          # aynı anahtar (önbellek/anahtarlık)


def test_existing_key_file_is_migrated_and_removed(home, monkeypatch):
    old = cfgmod._new_fernet_key()
    (home / ".xmpp_client.key").write_bytes(old)
    kr = _FakeKeyring()
    _use(monkeypatch, kr)
    assert cfgmod._get_fernet_key() == old          # parolalar çözülmeye devam eder
    assert not (home / ".xmpp_client.key").exists()
    assert list(kr.items.values()) == [old.decode()]


def test_saved_password_survives_migration(home, monkeypatch):
    _use(monkeypatch, None)                         # anahtarlıksız kayıt (eski)
    enc = cfgmod._encode_pw("gizli-parola")
    assert (home / ".xmpp_client.key").exists()
    _use(monkeypatch, _FakeKeyring())               # anahtarlık geldi: taşınır
    assert cfgmod._decode_pw(enc) == "gizli-parola"
    assert not (home / ".xmpp_client.key").exists()


def test_failed_keyring_write_keeps_file(home, monkeypatch):
    old = cfgmod._new_fernet_key()
    (home / ".xmpp_client.key").write_bytes(old)
    _use(monkeypatch, _FakeKeyring(fail_set=True))
    assert cfgmod._get_fernet_key() == old
    assert (home / ".xmpp_client.key").read_bytes() == old     # veri kaybı yok


def test_different_file_key_is_not_deleted(home, monkeypatch):
    kr = _FakeKeyring()
    _use(monkeypatch, kr)
    key = cfgmod._get_fernet_key()                  # anahtarlıkta
    other = cfgmod._new_fernet_key()
    (home / ".xmpp_client.key").write_bytes(other)  # ör. geri yüklenen eski dosya
    cfgmod._KEYRING_CACHE.clear()
    assert cfgmod._get_fernet_key() == key
    assert (home / ".xmpp_client.key").read_bytes() == other


def test_without_keyring_old_behavior(home, monkeypatch):
    _use(monkeypatch, None)
    key = cfgmod._get_fernet_key()
    assert (home / ".xmpp_client.key").read_bytes() == key
    assert not (home / ".xmpp_client.keyring").exists()


def test_env_switch_disables_keyring(monkeypatch):
    monkeypatch.setenv("XMPP_NO_KEYRING", "1")
    assert cfgmod._keyring() is None


def test_facade_still_patchable():
    assert xmpp._get_fernet_key is cfgmod._get_fernet_key
