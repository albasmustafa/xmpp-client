"""Durum Mesajı penceresi mevcut durumu korumalı; yayın kenar çubuğuna yansımalı.

Kanıt: pencere her açılışta "chat" seçili ve boş yazıyla açılıyordu. Meşgul'ken
yalnız yazıyı değiştirip Uygula'ya basmak durumu Çevrimiçi'ne çeviriyordu.
`_publish_status` (pencere, /status) ile Ayarlar'dan uygulanan durum yalnız
yayınlanıyordu: kenar çubuğu "● Çevrimiçi" demeye, `_my_show` (uzakta
taslakları, asistan) eski durumda kalmaya devam ediyordu.
"""
import os
import sys
import tkinter as tk
import types
from tkinter import ttk

import pytest

import xmpp
from ui.dialogs import presence as ui_presence


class _Var:
    def __init__(self):
        self.value = None

    def set(self, v):
        self.value = v


class _Label:
    def __init__(self):
        self.kw = {}

    def config(self, **kw):
        self.kw.update(kw)


def _win(monkeypatch, my_show="online", text=""):
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    w._my_show = my_show
    w._status_text = text
    w.status_var = _Var()
    w._status_label = _Label()
    w.returned = []
    w._ai_away_returned = lambda: w.returned.append(True)
    w.sent = []
    w.bot = types.SimpleNamespace(
        set_status_message=lambda t, s: w.sent.append((t, s)))
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda c: None)
    return w


@pytest.mark.parametrize("my_show, expected", [
    ("dnd", "dnd"), ("away", "away"), ("xa", "xa"), ("online", "chat")])
def test_dialog_opens_with_current_status(monkeypatch, my_show, expected):
    w = _win(monkeypatch, my_show, "Toplantıda")
    got = []
    monkeypatch.setattr(ui_presence, "show_status",
                        lambda parent, on_apply, **kw: got.append(kw))
    xmpp.MainWindow._status_dialog(w)
    assert got == [{"text": "Toplantıda", "show": expected}]


def test_publish_updates_sidebar_and_my_show(monkeypatch):
    w = _win(monkeypatch)
    xmpp.MainWindow._publish_status(w, "Toplantıda", "dnd")
    assert w.sent == [("Toplantıda", "dnd")]
    assert w._my_show == "dnd"
    assert w.status_var.value == "Meşgul"
    assert w._status_label.kw["text"] == "● Meşgul"


def test_publish_chat_shows_online_and_ends_away(monkeypatch):
    w = _win(monkeypatch, my_show="away")
    xmpp.MainWindow._publish_status(w, "", "chat")
    assert w._my_show == "online"
    assert w._status_label.kw["text"] == "● Çevrimiçi"
    assert w.returned == [True]            # uzaktan dönüş kancası


def test_settings_status_updates_sidebar(monkeypatch):
    src = __import__("inspect").getsource(xmpp.MainWindow)
    # Ayarlar'ın durum uygulaması da aynı yoldan geçer
    start = src.index("# Durum mesajını uygula")
    assert "_show_my_status(" in src[start:start + 600]


@pytest.fixture()
def root():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    r = tk.Tk()
    r.withdraw()
    xmpp._apply_theme()
    yield r
    r.destroy()


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def test_real_dialog_prefilled_apply_keeps_status(root):
    got = []
    ui_presence.show_status(root, lambda t, s: got.append((t, s)),
                            text="Toplantıda", show="dnd")
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    entry = next(w for w in _walk(top) if isinstance(w, xmpp.PlaceholderEntry))
    assert entry.get_value() == "Toplantıda"
    next(w for w in _walk(top) if isinstance(w, ttk.Button)
         and w.cget("text") == "Uygula").invoke()
    assert got == [("Toplantıda", "dnd")]
