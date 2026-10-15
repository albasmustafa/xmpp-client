"""Yanıt taslakları: uzaktayken hazırlananlar + harici (MCP/REST) taslaklar.

Kanıtlar:
- Uzakta = otomatik boşta ya da elle "away"/"xa". Yalnız ayar açık,
  uzaktayken ve 1:1 sohbette gelen mesaj taslak planlar; art arda mesajlar
  tek gecikmeli üretime toplanır (zamanlayıcı yenilenir, kayıttan düşer).
- Üretim mevcut "yanıt öner" istemiyle yapılır, hiçbir şey GÖNDERİLMEZ.
  Şifreli sohbet + bulut + izin yok → "onay bekliyor": arka planda soru
  sorulmaz ve içerik gitmez; onay kapısından geçilince üretilir. Eski
  (yerine yenisi istenmiş) yanıtlar atılır.
- Kullanıcı o sohbete yazınca taslak düşer; dönüşte (boşta→aktif ya da
  elle durum) bir bildirim çıkar.
- Harici taslak yalnız kutuya eklenir (tavanlı), bildirim gösterir.
- Görünüm: "Kullan" metni giriş kutusuna verir; onay/yeniden üret/kaldır.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ai_dialog_view import _W, _find, fake_tk  # noqa: E402,F401
from test_history_window_bounds import _Cap  # noqa: E402

import ui.dialogs.ai as ui_ai  # noqa: E402
import xmpp  # noqa: E402
from xmppcore import ai  # noqa: E402

ENTRIES = [("Ali", "Yarın geliyor musun?", False, "10:00", "them"),
           ("Ben", "bakarım", True, "10:01", "me"),
           ("Ali", "Saat kaçta?", False, "10:02", "them")]


@pytest.fixture()
def dw(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = types.SimpleNamespace(after_cancel=lambda aid: None)
    w.rooms = {"oda@conf.x": {}}
    w._contacts = {"ali@x": "Ali"}
    w._chat_enc_modes = {}
    w._is_idle = True
    w._ai_away_on = True
    w.chats = {"ali@x": list(ENTRIES), "gizli@x": list(ENTRIES)}
    w._chat_enc_modes = {"gizli@x": "omemo"}
    timers = []
    w._after = lambda ms, fn, *a: (timers.append((ms, fn, a)),
                                   f"id{len(timers)}")[1]
    w._after_cancel = _Cap()
    w._show_toast = _Cap()
    cfg = {"ai": {"provider": "ollama"}}
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    chats = []

    def fake_chat(settings, system, user, **kw):
        chats.append((system, user, kw))
        return "Evet geliyorum\nSaat 10'da\nBiraz gecikeceğim"
    monkeypatch.setattr(xmpp._ai, "chat", fake_chat)
    w._ai_submit = lambda job, done, err: done(job())
    w.timers, w.chats_called, w.cfg = timers, chats, cfg
    return w


def test_away_detection(dw):
    assert xmpp.MainWindow._ai_is_away(dw)
    dw._is_idle = False
    assert not xmpp.MainWindow._ai_is_away(dw)
    for show, away in (("away", True), ("xa", True), ("dnd", False),
                       ("online", False)):
        dw._my_show = show
        assert xmpp.MainWindow._ai_is_away(dw) is away


def test_note_message_debounces_and_skips(dw):
    note = xmpp.MainWindow._ai_away_note_message
    note(dw, "ali@x")
    note(dw, "ali@x")
    assert [t[0] for t in dw.timers] == [xmpp.MainWindow._AWAY_DRAFT_DELAY_MS] * 2
    assert dw._after_cancel.calls[-1] == (("id1",), {})   # önceki iptal
    entry = dw._ai_drafts["ali@x"]
    assert entry["count"] == 2 and entry["state"] == "pending"
    note(dw, "oda@conf.x")                                  # oda
    dw._is_idle = False
    note(dw, "bob@x")                                       # uzakta değil
    dw._is_idle, dw._ai_away_on = True, False
    note(dw, "bob@x")                                       # ayar kapalı
    assert list(dw._ai_drafts) == ["ali@x"]
    assert dw.chats_called == []                            # henüz istek yok


def test_generate_produces_options_without_sending(dw):
    dw.bot = types.SimpleNamespace(send_chat=_Cap())
    xmpp.MainWindow._ai_away_note_message(dw, "ali@x")
    _ms, fn, args = dw.timers[-1]
    fn(*args)
    entry = dw._ai_drafts["ali@x"]
    assert entry["state"] == "ready"
    assert entry["options"] == ["Evet geliyorum", "Saat 10'da",
                                "Biraz gecikeceğim"]
    assert entry["last"] == "Saat kaçta?"
    system, user, kw = dw.chats_called[0]
    assert (system, user) == ai.suggest_request(ai.build_transcript(
        ENTRIES, max_chars=8000)[0])
    assert dw.bot.send_chat.calls == []                     # GÖNDERİM YOK


def test_encrypted_cloud_waits_for_consent(dw, monkeypatch):
    dw.cfg["ai"]["provider"] = "claude"
    xmpp.MainWindow._ai_away_note_message(dw, "gizli@x")
    xmpp.MainWindow._ai_draft_generate(dw, "gizli@x")
    assert dw._ai_drafts["gizli@x"]["state"] == "blocked"
    assert dw.chats_called == []                            # içerik gitmedi
    dw._ai_gate = lambda settings, sensitive: True          # kullanıcı onayı
    xmpp.MainWindow._ai_draft_consent(dw, {"jid": "gizli@x"})
    assert dw._ai_drafts["gizli@x"]["state"] == "ready"
    assert dw.chats_called[0][2]["allow_cloud"] is True
    dw._ai_drafts["gizli@x"]["state"] = "blocked"
    dw._ai_gate = lambda settings, sensitive: None          # vazgeçti
    xmpp.MainWindow._ai_draft_consent(dw, {"jid": "gizli@x"})
    assert len(dw.chats_called) == 1


def test_stale_generation_is_discarded(dw):
    xmpp.MainWindow._ai_away_note_message(dw, "ali@x")
    pending = []
    dw._ai_submit = lambda job, done, err: pending.append((job, done))
    xmpp.MainWindow._ai_draft_generate(dw, "ali@x")
    xmpp.MainWindow._ai_draft_generate(dw, "ali@x")         # yenisi istendi
    job, done = pending[0]
    done(["eski"])
    assert dw._ai_drafts["ali@x"]["options"] == []
    job2, done2 = pending[1]
    done2(job2())
    assert dw._ai_drafts["ali@x"]["options"][0] == "Evet geliyorum"


def test_errors_are_shown_on_entry(dw, monkeypatch):
    xmpp.MainWindow._ai_away_note_message(dw, "ali@x")
    dw.cfg["ai"]["provider"] = "off"
    xmpp.MainWindow._ai_draft_generate(dw, "ali@x")
    assert dw._ai_drafts["ali@x"]["state"] == "error"
    dw.cfg["ai"]["provider"] = "ollama"
    dw._ai_submit = lambda job, done, err: err(ai.AIError("Ollama kapalı"))
    xmpp.MainWindow._ai_draft_generate(dw, "ali@x")
    assert dw._ai_drafts["ali@x"]["error"] == "Ollama kapalı"


def test_my_reply_drops_draft(dw, monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    dw._next_msg_uid = lambda: "u1"
    dw._remember_reply = lambda *a: None
    xmpp.MainWindow._ai_away_note_message(dw, "ali@x")
    xmpp.MainWindow._store(dw, "ali@x", "geliyorum", tag="me", sender="Ben",
                           is_me=True)
    assert "ali@x" not in dw._ai_drafts
    assert dw._after_cancel.calls[-1] == (("id1",), {})


def test_returning_shows_toast(dw):
    xmpp.MainWindow._ai_away_note_message(dw, "ali@x")
    dw.bot = types.SimpleNamespace(set_presence=_Cap())
    dw._status_label = types.SimpleNamespace(config=lambda **k: None)
    dw._last_activity_ts = 0
    xmpp.MainWindow._reset_activity(dw)
    assert "1 sohbet" in dw._show_toast.calls[-1][0][1]
    dw.status_var = types.SimpleNamespace(set=lambda v: None)
    dw._my_show = "xa"
    xmpp.MainWindow._set_status(dw, "Online", "online", xmpp.ONLINE)
    assert len(dw._show_toast.calls) == 2 and dw._my_show == "online"
    xmpp.MainWindow._set_status(dw, "Meşgul", "dnd", xmpp.RED)
    assert len(dw._show_toast.calls) == 2           # uzaktan dönüş değil


def test_external_draft_added_and_capped(dw):
    dw._ai_is_idle = False
    for i in range(7):
        xmpp.MainWindow._ai_add_draft(dw, "can@x", [f"t{i}"], "🔌 MCP")
    entry = dw._ai_drafts["can@x"]
    assert entry["external"] == ["t2", "t3", "t4", "t5", "t6"]
    assert "🔌 MCP: can" in dw._show_toast.calls[-1][0][1]
    xmpp.MainWindow._ai_add_draft(dw, "gecersiz", ["x"], "🔌 MCP")
    xmpp.MainWindow._ai_add_draft(dw, "can@x", ["  "], "🔌 MCP")
    assert list(dw._ai_drafts) == ["can@x"]
    view, = xmpp.MainWindow._ai_drafts_view(dw)
    assert view["source"] == "🔌 MCP" and view["state"] == "ready"
    assert view["regen"] is False and view["options"][0] == "t2"


def test_drafts_cap(dw):
    for i in range(xmpp.MainWindow._DRAFTS_MAX + 2):
        xmpp.MainWindow._ai_add_draft(dw, f"k{i}@x", ["t"], "🔌 MCP")
    assert len(dw._ai_drafts) == xmpp.MainWindow._DRAFTS_MAX
    assert "dolu" in dw._show_toast.calls[-1][0][0] + \
        dw._show_toast.calls[-1][0][1]


def test_window_callbacks(dw, monkeypatch):
    created = []

    class _Win:
        def __init__(self, parent, **cb):
            self.cb = cb
            self.entries = None
            created.append(self)

        def alive(self):
            return True

        def set_entries(self, e):
            self.entries = e
    monkeypatch.setattr(xmpp._ui_ai, "DraftsWindow", _Win)
    xmpp.MainWindow._ai_add_draft(dw, "ali@x", ["Olur"], "🔌 MCP")
    xmpp.MainWindow._ai_drafts_window(dw)
    win = created[0]
    entry = win.entries[0]
    dw._ai_offer_text = _Cap()
    win.cb["on_use"](entry, "Olur")
    assert dw._ai_offer_text.calls == [(("ali@x", "Olur"), {})]
    win.cb["on_dismiss"](entry)
    assert dw._ai_drafts == {} and win.entries == []


# ── Görünüm (sahte tk) ──────────────────────────────────────────────────────
@pytest.mark.usefixtures("fake_tk")
def test_drafts_view_states_and_buttons():
    calls = []
    win = ui_ai.DraftsWindow(
        _W(), on_use=lambda e, t: calls.append(("use", t)),
        on_regen=lambda e: calls.append(("regen", e["jid"])),
        on_consent=lambda e: calls.append(("consent", e["jid"])),
        on_dismiss=lambda e: calls.append(("dismiss", e["jid"])))
    win.set_entries([
        {"jid": "a@x", "label": "Ali", "source": "🌙 Uzaktayken",
         "count": 2, "last": "Saat kaçta?", "options": ["Evet", "Hayır"],
         "state": "ready", "error": "", "regen": True},
        {"jid": "b@x", "label": "Veli", "source": "🌙 Uzaktayken",
         "count": 1, "last": "", "options": [], "state": "blocked",
         "error": "", "regen": True},
        {"jid": "c@x", "label": "Can", "source": "🔌 MCP", "count": 0,
         "last": "", "options": ["Taslak"], "state": "ready", "error": "",
         "regen": False}])
    assert win._status.kw["text"] == "3 sohbet için taslak var."
    assert _find(win.top, "👤 Ali  ·  2 yeni mesaj  ·  🌙 Uzaktayken")
    cards = win._list.inner.winfo_children()
    _find(cards[0], "➡ Kullan").click()
    _find(cards[0], "🔄 Yeniden üret").click()
    _find(cards[1], "☁ Onayla ve hazırla").click()
    assert _find(cards[2], "🔄 Yeniden üret") is None      # harici: yok
    _find(cards[2], "✓ Kaldır").click()
    assert calls == [("use", "Evet"), ("regen", "a@x"), ("consent", "b@x"),
                     ("dismiss", "c@x")]
    win.set_entries([])
    assert win._status.kw["text"] == "Bekleyen taslak yok."
