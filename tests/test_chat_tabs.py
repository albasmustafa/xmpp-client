"""FAZ 4C closure V-3: sohbet sekmesi gönderimi hedefe özel şifreleme
modunu kullanmalı (aktif ana sohbetin modunu değil)."""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Var:
    def __init__(self, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class _W:
    def __init__(self, *a, **k):
        self.binds = {}
        self.kw = k

    def title(self, *a, **k):
        pass

    def configure(self, *a, **k):
        pass

    def geometry(self, *a, **k):
        pass

    def protocol(self, *a, **k):
        pass

    def pack(self, *a, **k):
        pass

    def grid(self, *a, **k):
        pass

    def bind(self, seq, fn=None, *a, **k):
        self.binds.setdefault(seq, []).append(fn)

    def create_window(self, *a, **k):
        pass

    def columnconfigure(self, *a, **k):
        pass

    def yview_scroll(self, *a, **k):
        pass

    def yview_moveto(self, *a, **k):
        pass

    def bbox(self, *a, **k):
        return (0, 0, 0, 0)

    def focus_set(self):
        pass


class _Entry(_W):
    pass


def _install_fake_tk(monkeypatch):
    entered = {}
    entries = []

    class _EntryCapture(_Entry):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            entries.append(self)

        def bind(self, seq, fn=None, *a, **k):
            super().bind(seq, fn, *a, **k)
            if seq == "<Return>":
                entered["send"] = fn

    fake_tk = types.SimpleNamespace(
        Toplevel=_W, Canvas=_W, Frame=_W, Label=_W, StringVar=_Var)
    fake_ttk = types.SimpleNamespace(Entry=_EntryCapture)
    monkeypatch.setattr(xmpp, "tk", fake_tk)
    monkeypatch.setattr(xmpp, "ttk", fake_ttk)
    return entered, entries


def _open_tab_window(active, target, main_mode, target_mode, rooms=()):
    w = object.__new__(xmpp.MainWindow)
    w.root = _W()
    w.active = active
    w.rooms = list(rooms)
    w.chats = {target: []}
    w._chat_tabs = {}
    w.bot = types.SimpleNamespace(send_chat=_Capture(), send_gc=_Capture())
    w._store = _Capture()
    w._encryption_mode = _Var(main_mode)
    w._chat_enc_modes = {active: main_mode, target: target_mode}
    return w


def _send_from_tab(w, entered, entries, body="merhaba"):
    var = entries[0].kw["textvariable"]
    var.set(body)
    entered["send"]()
    return var


def test_chat_tab_send_uses_target_encryption_mode(monkeypatch):
    """Ana sohbet B=OMEMO; A sekmesi none → A gönderimi none olmalı."""
    w = _open_tab_window(active="b@x", target="a@b",
                         main_mode="omemo", target_mode="none")
    entered, entries = _install_fake_tk(monkeypatch)

    xmpp.MainWindow._open_chat_tab(w, "a@b")
    assert "a@b" in w._chat_tabs

    var = _send_from_tab(w, entered, entries)

    assert w.bot.send_chat.calls == [(("a@b", "merhaba"),
                                      {"encryption": "none"})]
    assert w.bot.send_gc.calls == []
    assert w._store.calls[0][0] == ("a@b", "merhaba")
    assert var.get() == ""


def test_chat_tab_send_uses_target_mode_when_main_is_plain(monkeypatch):
    """Ana sohbet none; hedef sekme OMEMO → gönderim OMEMO olmalı."""
    w = _open_tab_window(active="b@x", target="a@b",
                         main_mode="none", target_mode="omemo")
    entered, entries = _install_fake_tk(monkeypatch)

    xmpp.MainWindow._open_chat_tab(w, "a@b")
    _send_from_tab(w, entered, entries)

    assert w.bot.send_chat.calls[0][1] == {"encryption": "omemo"}


def test_chat_tab_muc_send_uses_target_encryption_mode(monkeypatch):
    """MUC sekmesi de hedef odanın modunu kullanır."""
    w = _open_tab_window(active="b@x", target="oda@conf",
                         main_mode="omemo", target_mode="none",
                         rooms=["oda@conf"])
    entered, entries = _install_fake_tk(monkeypatch)

    xmpp.MainWindow._open_chat_tab(w, "oda@conf")
    _send_from_tab(w, entered, entries)

    assert w.bot.send_gc.calls == [(("oda@conf", "merhaba"),
                                    {"encryption": "none"})]
    assert w.bot.send_chat.calls == []


def test_chat_tab_send_defaults_to_none_without_stored_mode(monkeypatch):
    """Hedef için kayıtlı mod yoksa aktif modu sızdırmadan 'none' kullanılır."""
    w = _open_tab_window(active="b@x", target="a@b",
                         main_mode="pgp", target_mode="none")
    w._chat_enc_modes = {"b@x": "pgp"}          # a@b kaydı yok
    entered, entries = _install_fake_tk(monkeypatch)

    xmpp.MainWindow._open_chat_tab(w, "a@b")
    _send_from_tab(w, entered, entries)

    assert w.bot.send_chat.calls[0][1] == {"encryption": "none"}
