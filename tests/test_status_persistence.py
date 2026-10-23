"""Durum yeniden bağlanınca ve otomatik uzaktayken tutarlı kalmalı.

Kanıt (kod incelemesi, 2026-10-23):
- B2: "connected" kenar çubuğunu "● Çevrimiçi"ye çekiyor ama `_my_show`
  eski kalıyordu (uzakta sanılıp yanıt taslağı üretiliyordu); durum
  menüsünden seçilen durum kaydedilmediğinden yeniden bağlanınca kayboluyordu.
- B3: otomatik uzakta elle seçilmiş Meşgul'ü eziyordu; dönüşte durum
  Çevrimiçi oluyor ve `set_presence("online")` boş durum metniyle gidip
  durum mesajını siliyordu.
"""
import types

import pytest

import xmpp


class _Cap:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))


@pytest.fixture()
def w(monkeypatch):
    store = {}
    monkeypatch.setattr(xmpp, "_load_config", lambda: dict(store))
    monkeypatch.setattr(xmpp, "_save_config",
                        lambda c: (store.clear(), store.update(c)))
    win = object.__new__(xmpp.MainWindow)
    win.store = store
    win.labels = []
    win._status_label = types.SimpleNamespace(
        config=lambda **kw: win.labels.append(kw["text"]))
    win.status_var = types.SimpleNamespace(set=lambda v: None)
    win.bot = types.SimpleNamespace(set_presence=_Cap(),
                                    set_status_message=_Cap())
    win._ai_away_returned = _Cap()
    win._status_text = "Toplantıda"
    win._my_show = "online"
    win._is_idle = False
    win._idle_after_min = 5
    win._last_activity_ts = 0
    win._after = lambda *a: None
    return win


@pytest.mark.parametrize("show, saved", [
    ("dnd", "dnd"), ("away", "away"), ("xa", "xa"), ("online", "chat")])
def test_menu_status_is_saved(w, show, saved):
    label, color = xmpp.MainWindow._ai_status_option(show)
    xmpp.MainWindow._set_status(w, label, show, color)
    assert w._status_show == saved
    assert w.store["presence_show"] == saved
    assert w.store.get("status_text", "Toplantıda") == "Toplantıda"


def test_menu_status_survives_reconnect(w):
    label, color = xmpp.MainWindow._ai_status_option("away")
    xmpp.MainWindow._set_status(w, label, "away", color)
    w.labels.clear()
    xmpp.MainWindow._restore_status_prefs(w)
    assert w.bot.set_status_message.calls[-1][0] == ("Toplantıda", "away")
    assert w.labels[-1] == "● Uzakta" and w._my_show == "away"


def test_reconnect_resyncs_stale_my_show(w):
    w._my_show = "away"                 # eski oturumdan kalan
    w._status_text, w._status_show = "", "chat"
    xmpp.MainWindow._restore_status_prefs(w)
    assert w._my_show == "online"
    assert w.labels[-1] == "● Çevrimiçi"
    assert not xmpp.MainWindow._ai_is_away(w)


def test_auto_away_keeps_status_text_and_returns(w):
    xmpp.MainWindow._check_idle(w)
    assert w.bot.set_presence.calls == [(("away",), {"status": "Toplantıda"})]
    assert w.labels[-1] == "● Uzakta (oto)"
    xmpp.MainWindow._reset_activity(w)
    assert w.bot.set_presence.calls[-1] == (("online",),
                                            {"status": "Toplantıda"})
    assert w.labels[-1] == "● Çevrimiçi"


def test_auto_away_does_not_override_manual_dnd(w):
    w._my_show = "dnd"
    xmpp.MainWindow._check_idle(w)
    assert w.bot.set_presence.calls == []
    assert w.labels == []
    assert w._is_idle                    # taslaklar için yine "uzakta"
    xmpp.MainWindow._reset_activity(w)
    assert w.bot.set_presence.calls == [] and w.labels == []
    assert w._my_show == "dnd"


def test_manual_choice_while_auto_away_is_not_reset(w):
    xmpp.MainWindow._check_idle(w)
    label, color = xmpp.MainWindow._ai_status_option("dnd")
    xmpp.MainWindow._set_status(w, label, "dnd", color)
    n = len(w.bot.set_presence.calls)
    xmpp.MainWindow._reset_activity(w)
    assert len(w.bot.set_presence.calls) == n   # dnd ezilmez
    assert w._my_show == "dnd"
