"""Test paketi gerçek kullanıcı dosyalarına dokunmamalı.

Kanıt (2026-10-14): uygulama kapalıyken ~/.xmpp_client_messages.db tam test
çalıştırması sırasında değişti; ~/.xmpp_client.log her içe aktarmada
"XMPP istemcisi başlatılıyor" satırı topluyordu. Yollar XMPP_CLIENT_HOME ile
yönlendirilebilir; tests/conftest.py bunu geçici bir dizine ayarlar.
"""
import os
import pwd
import subprocess
import sys

import pytest

import xmpp
from xmppcore import config as xmpp_config
from xmppcore import constants

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir


@pytest.mark.parametrize("path", [
    constants._LOG_PATH, xmpp._CONFIG_PATH, xmpp._DB_PATH, xmpp._AVATAR_DIR,
])
def test_session_paths_are_not_in_real_home(path):
    assert not os.path.abspath(path).startswith(os.path.join(REAL_HOME, ".xmpp"))


def test_key_path_follows_data_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XMPP_CLIENT_HOME", str(tmp_path))
    assert xmpp_config._key_path() == str(tmp_path / ".xmpp_client.key")


def _paths_in_subprocess(env):
    code = ("import sys; sys.path.insert(0, %r); import xmppcore.constants as c;"
            "print(c._CONFIG_PATH); print(c._DB_PATH); print(c._LOG_PATH)" % ROOT)
    out = subprocess.run([sys.executable, "-c", code], env=env, check=True,
                         capture_output=True, text=True).stdout.split()
    return out


def test_data_home_env_redirects_all_files(tmp_path):
    env = dict(os.environ, XMPP_CLIENT_HOME=str(tmp_path), HOME=str(tmp_path / "ev"))
    for p in _paths_in_subprocess(env):
        assert p.startswith(str(tmp_path) + os.sep + ".xmpp_client")


def test_without_env_uses_home(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "XMPP_CLIENT_HOME"}
    env["HOME"] = str(tmp_path)
    for p in _paths_in_subprocess(env):
        assert p.startswith(str(tmp_path) + os.sep + ".xmpp_client")


# ── Başka diske taşınmış profil (2026-10-21, "her şeyi albas diskine taşı") ──
def test_omemo_keys_follow_data_home():
    """OMEMO deposu XMPP_CLIENT_HOME'u yok sayıp hep ~/.xmpp_omemo'yu
    kullanıyordu: profil taşınınca anahtar bulunamaz, yeni OMEMO kimliği
    yayımlanırdı; testler/duman betikleri de gerçek dizine yazıyordu."""
    omemo_dir = getattr(xmpp, "_OMEMO_DIR", None)
    if omemo_dir is None:
        pytest.skip("OMEMO kütüphaneleri kurulu değil")
    assert str(omemo_dir) == os.path.join(constants._user_home(),
                                          ".xmpp_omemo")
    assert not str(omemo_dir).startswith(os.path.join(REAL_HOME, ".xmpp"))


def _without_data_env(home):
    env = {k: v for k, v in os.environ.items()
           if k not in ("XMPP_CLIENT_HOME", "HF_HOME")}
    env["HOME"] = str(home)
    return env


def test_pointer_file_redirects_every_launch(tmp_path):
    """Ev dizinindeki `.xmpp_client_home` taşınmış profili gösterir: betik,
    masaüstü kısayolu ya da doğrudan `python xmpp.py` aynı yeri bulur."""
    home, data = tmp_path / "ev", tmp_path / "veri"
    home.mkdir()
    data.mkdir()
    (home / ".xmpp_client_home").write_text(f"{data}\n", encoding="utf-8")
    for p in _paths_in_subprocess(_without_data_env(home)):
        assert p.startswith(str(data) + os.sep + ".xmpp_client")
    assert sorted(os.listdir(home)) == [".xmpp_client_home"]


def test_env_wins_over_pointer_file(tmp_path):
    home, data, other = tmp_path / "ev", tmp_path / "veri", tmp_path / "test"
    for d in (home, data, other):
        d.mkdir()
    (home / ".xmpp_client_home").write_text(str(data), encoding="utf-8")
    env = dict(_without_data_env(home), XMPP_CLIENT_HOME=str(other))
    for p in _paths_in_subprocess(env):
        assert p.startswith(str(other) + os.sep)


@pytest.mark.parametrize("content", ["{missing}", "", "goreli/yol"])
def test_unusable_pointer_stops_instead_of_fresh_profile(tmp_path, content):
    """Gösterilen klasör yoksa (disk takılı değil) boş profille açılmak yeni
    OMEMO kimliği ve boş ayar demekti: açıklamayla durur, dosya yaratmaz."""
    home = tmp_path / "ev"
    home.mkdir()
    (home / ".xmpp_client_home").write_text(
        content.format(missing=tmp_path / "yok"), encoding="utf-8")
    code = ("import sys; sys.path.insert(0, %r); import xmppcore.constants"
            % ROOT)
    res = subprocess.run([sys.executable, "-c", code],
                         env=_without_data_env(home), capture_output=True,
                         text=True)
    assert res.returncode != 0
    assert "veri klasörü" in res.stderr and ".xmpp_client_home" in res.stderr
    assert sorted(os.listdir(home)) == [".xmpp_client_home"]
    assert not (tmp_path / "yok").exists()


def _hf_home(env):
    code = ("import os, sys; sys.path.insert(0, %r); import xmppcore.constants;"
            "print(os.environ.get('HF_HOME', '-'))" % ROOT)
    return subprocess.run([sys.executable, "-c", code], env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_speech_model_cache_moves_with_profile(tmp_path):
    """Ses→metin modeli (faster-whisper, ~460 MB) Hugging Face önbelleğine
    iner: taşınmış profilde profille durur; evdeki profilde HF'nin kendi
    yeri ve kullanıcının HF_HOME'u korunur."""
    home, data = tmp_path / "ev", tmp_path / "veri"
    home.mkdir()
    data.mkdir()
    assert _hf_home(_without_data_env(home)) == "-"
    (home / ".xmpp_client_home").write_text(str(data), encoding="utf-8")
    assert _hf_home(_without_data_env(home)) == str(
        data / ".cache" / "huggingface")
    env = dict(_without_data_env(home), HF_HOME=str(tmp_path / "hf"))
    assert _hf_home(env) == str(tmp_path / "hf")
