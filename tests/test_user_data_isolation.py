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
