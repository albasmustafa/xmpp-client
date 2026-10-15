"""Beni hatırla / otomatik giriş regresyonları.

e62c2ead ile giriş ekranının kayıtlı bilgileri okuması ve otomatik giriş
kayboldu: bilgiler config'e yazılıyor ama hiç geri okunmuyordu; hesap
değişimi de (`_switch_account` → relogin) boş giriş ekranına düşüyordu.
"""
import os
import sys
import tkinter as tk
import types

import pytest
from cryptography.fernet import Fernet

import xmpp


@pytest.fixture()
def key(monkeypatch):
    k = Fernet.generate_key()
    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: k)
    return k


def _saved_cfg():
    cfg = {"theme": "koyu"}
    xmpp._store_login(cfg, True, "ben@example.com", "gizli", 5223, "gw.example")
    return cfg


# ── config yardımcıları ──────────────────────────────────────────────────────

def test_store_login_encrypts_and_saved_login_reads_back(key):
    cfg = _saved_cfg()
    assert cfg["remember"] is True
    assert cfg["pw"].startswith("fernet:") and "gizli" not in cfg["pw"]
    assert xmpp._saved_login(cfg) == ("ben@example.com", "gizli", 5223, "gw.example")


def test_store_login_disabled_wipes_credentials(key):
    cfg = _saved_cfg()
    xmpp._store_login(cfg, False)
    assert cfg["remember"] is False
    assert not {"jid", "pw", "server", "port"} & cfg.keys()
    assert cfg["theme"] == "koyu"
    assert xmpp._saved_login(cfg) is None


@pytest.mark.parametrize("patch", [
    {"remember": False},
    {"jid": ""},
    {"pw": ""},
    {"pw": "fernet:bozuk"},
])
def test_saved_login_none_without_usable_credentials(key, patch):
    cfg = _saved_cfg()
    cfg.update(patch)
    assert xmpp._saved_login(cfg) is None


def test_saved_login_defaults_bad_port(key):
    cfg = _saved_cfg()
    cfg["port"] = "abc"
    assert xmpp._saved_login(cfg)[2] == 5222


# ── main(): otomatik giriş akışı ─────────────────────────────────────────────

def _run_main(monkeypatch, cfg, start_results):
    forms, starts = [], []

    class _LW:
        def __init__(self, cb):
            forms.append(1)
            cb("form@example.com", "pw", 5222, "")

    seq = iter(start_results)

    def _start(*args):
        starts.append(args)
        return next(seq)

    monkeypatch.setattr(xmpp, "LoginWindow", _LW)
    monkeypatch.setattr(xmpp, "start", _start)
    monkeypatch.setattr(xmpp, "_check_pin_lock", lambda: True)
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    xmpp.main()
    return forms, starts


def test_main_auto_logs_in_with_saved_credentials(monkeypatch, key):
    forms, starts = _run_main(monkeypatch, _saved_cfg(), [False])
    assert forms == []
    assert starts == [("ben@example.com", "gizli", 5223, "gw.example")]


def test_main_shows_form_without_saved_credentials(monkeypatch):
    forms, starts = _run_main(monkeypatch, {"remember": False}, [False])
    assert forms == [1]
    assert starts == [("form@example.com", "pw", 5222, "")]


def test_main_shows_form_after_auth_failure(monkeypatch, key):
    """Şifre sunucuda değiştiyse otomatik giriş döngüye girmemeli."""
    forms, starts = _run_main(monkeypatch, _saved_cfg(), [True, False])
    assert forms == [1]
    assert starts[0][0] == "ben@example.com"
    assert starts[1][0] == "form@example.com"


def test_main_auto_logs_in_after_account_switch(monkeypatch, key):
    forms, starts = _run_main(monkeypatch, _saved_cfg(), ["auto", False])
    assert forms == []
    assert len(starts) == 2


def test_switch_and_relogin_requests_auto_login():
    win = object.__new__(xmpp.MainWindow)
    win._quit = lambda: None
    xmpp.MainWindow._switch_and_relogin(win)
    assert win._relogin is True
    assert win._relogin_auto is True


@pytest.mark.parametrize("attrs, expected", [
    ({"_relogin": True, "_relogin_auto": True}, "auto"),
    ({"_relogin": True}, True),
    ({"_relogin": False, "_relogin_auto": True}, False),
])
def test_start_reports_auto_relogin(monkeypatch, attrs, expected):
    class Bot:
        default_domain = "example.com"

        def __init__(self, jid, password, gui_q):
            pass

        def connect(self, host=None, port=None):
            self.loop.call_soon(self.loop.stop)

    monkeypatch.setattr(xmpp, "XMPPBot", Bot)
    monkeypatch.setattr(xmpp, "MainWindow",
                        lambda *a: types.SimpleNamespace(**attrs))
    assert xmpp.start("qa@example.com", "dummy") == expected


# ── Ayarlar → Bağlantı: otomatik giriş anahtarı ──────────────────────────────

def _settings_win(custom_address=None):
    win = object.__new__(xmpp.MainWindow)
    win.jid = "ben@example.com"
    win.bot = types.SimpleNamespace(password="gizli",
                                    custom_address=custom_address)
    return win


def test_settings_enable_auto_login_stores_session_credentials(key):
    cfg = {"remember": False}
    xmpp.MainWindow._apply_auto_login(
        _settings_win(("gw.example", 5223)), cfg, True)
    assert xmpp._saved_login(cfg) == ("ben@example.com", "gizli", 5223, "gw.example")


def test_settings_enable_auto_login_default_server(key):
    cfg = {}
    xmpp.MainWindow._apply_auto_login(_settings_win(), cfg, True)
    assert xmpp._saved_login(cfg) == ("ben@example.com", "gizli", 5222, "")


def test_settings_disable_auto_login_forgets_password(key):
    cfg = _saved_cfg()
    xmpp.MainWindow._apply_auto_login(_settings_win(), cfg, False)
    assert "pw" not in cfg and cfg["remember"] is False


def test_settings_unchanged_auto_login_keeps_saved_values(key):
    """Açık kalan anahtar kayıtlı sunucu/portu oturum değerleriyle ezmemeli."""
    cfg = _saved_cfg()
    before = dict(cfg)
    xmpp.MainWindow._apply_auto_login(_settings_win(), cfg, True)
    assert cfg == before


# ── LoginWindow ──────────────────────────────────────────────────────────────

def test_connect_saves_credentials_when_remember_checked(monkeypatch, key):
    saved, logins = {}, []
    lw = object.__new__(xmpp.LoginWindow)
    var = lambda v: types.SimpleNamespace(get=lambda: v)  # noqa: E731
    lw.jid_var, lw.pw_var = var("ben@example.com"), var("gizli")
    lw.srv_var, lw.port_var, lw.remember_var = var(""), var("5222"), var(True)
    lw.root = types.SimpleNamespace(destroy=lambda: None)
    lw.on_login = lambda *a: logins.append(a)
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: saved.update(cfg))

    xmpp.LoginWindow._connect(lw)

    assert xmpp._saved_login(saved) == ("ben@example.com", "gizli", 5222, "")
    assert logins == [("ben@example.com", "gizli", 5222, "")]


@pytest.fixture()
def tk_root():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    root = tk.Tk()
    root.withdraw()
    xmpp._apply_theme()
    yield root
    root.destroy()


def _build_form(monkeypatch, root, cfg):
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    lw = object.__new__(xmpp.LoginWindow)
    lw.root = root
    lw._build()
    return lw


def test_login_form_prefills_saved_credentials(monkeypatch, key, tk_root):
    lw = _build_form(monkeypatch, tk_root, _saved_cfg())
    assert lw.jid_var.get() == "ben@example.com"
    assert lw.pw_var.get() == "gizli"
    assert lw.srv_var.get() == "gw.example"
    assert lw.port_var.get() == "5223"
    assert lw.remember_var.get() is True


def test_login_form_remember_checked_by_default(monkeypatch, tk_root):
    # Eski sürüm kutuyu boş açıp "remember": False yazıyordu; bu bir tercih değil
    lw = _build_form(monkeypatch, tk_root, {"remember": False})
    assert lw.pw_var.get() == ""
    assert lw.remember_var.get() is True
