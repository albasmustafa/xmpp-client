"""Relogin / hesap değişimi ve tema-menü lifecycle sözleşmeleri.

Faz 4B runtime kapanışı: RUNTIME-3 (relogin) ve RUNTIME-1 (tema girişi).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


class _Root:
    def __init__(self):
        self.after_calls = []

    def after(self, ms, cb):
        self.after_calls.append(ms)
        return "id1"


class _Q:
    def __init__(self, items):
        self.items = list(items)

    def get_nowait(self):
        if not self.items:
            raise xmpp.queue.Empty
        return self.items.pop(0)


# ── RUNTIME-3: relogin sırasında kuyruk boşaltma ────────────────────────────

def test_poll_stops_draining_after_quit():
    """_handle içinde _quit (auth_failed/relogin) olursa kalan olaylar
    işlenmemeli; yıkılmış Tk'ya çizim (TclError) oluşmamalı."""
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    win.gui_q = _Q([("auth_failed", "x"), ("disconnected", None)])
    handled = []

    def _h(kind, data):
        handled.append(kind)
        if kind == "auth_failed":
            win._closing = True  # _quit etkisi

    win._handle = _h
    win.root = _Root()

    xmpp.MainWindow._poll(win)

    assert handled == ["auth_failed"]
    assert win.root.after_calls == []  # kapanışta yeniden planlanmaz


def test_switch_and_relogin_sets_flag_then_quits():
    win = object.__new__(xmpp.MainWindow)
    order = []
    win._quit = lambda: order.append("quit")

    xmpp.MainWindow._switch_and_relogin(win)

    assert win._relogin is True
    assert order == ["quit"]


def test_main_relogin_loops_to_login(monkeypatch):
    """start() True dönerse main yeni LoginWindow açar; False'ta çıkar."""
    logins = []

    class _LW:
        def __init__(self, cb):
            logins.append(1)
            cb("a@b", "pw", 5222, "")

    seq = iter([True, False])
    monkeypatch.setattr(xmpp, "LoginWindow", _LW)
    monkeypatch.setattr(xmpp, "start", lambda *a: next(seq))
    monkeypatch.setattr(xmpp, "_check_pin_lock", lambda: True)
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})  # otomatik giriş yok

    xmpp.main()

    assert len(logins) == 2


# ── RUNTIME-1: tema seçici girişi ───────────────────────────────────────────

def test_sidebar_menu_has_theme_entry():
    spec = xmpp._sidebar_menu_spec(has_active_chat=False)
    keys = [item[2] for item in spec if item[0] == "item"]
    assert "theme" in keys
    labels = [item[1] for item in spec if item[0] == "item"]
    assert any(xmpp._t("theme") in lbl for lbl in labels)


def test_theme_picker_bound_in_actions():
    import inspect
    src = inspect.getsource(xmpp.MainWindow._sidebar_menu)
    assert '"theme":' in src and "_show_theme_picker" in src
