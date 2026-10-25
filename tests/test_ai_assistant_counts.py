"""Asistanın hızlı eylem çipleri okunmamış/taslak değişince tazelenmeli.

Kanıt (gerçek uygulamada duman testi, 2026-10-23): asistan açıkken
- Ali (3) ve Bob (3) okunmamışken Ali açılınca çip "📥 Neler kaçırdım? (6)"
  kaldı: `_load_chat` asistanı sayaç sıfırlanmadan ÖNCE tazeliyordu;
- Bob'dan yeni mesaj gelince sayı değişmedi; Bob telefonda okununca da "(6)"
  kaldı, tıklayınca "Okunmamış mesaj yok" dedi (yanlış düğme);
- Bob için yanıt taslağı hazırlanınca "✍ Taslaklar" çipi hiç çıkmadı (eksik
  düğme): çipler yalnız asistan açılırken ve sohbet değişince kuruluyordu.
"""
import types

from test_ai_agent import _FakeWin
from test_history_window_bounds import _win

import xmpp
from xmppcore import agent

ALI, BOB = "ali@x.org", "bob@x.org"


def _groups(win):
    return dict(win._ai_assistant_win.quick[1])


def _missed_label(win):
    every = _groups(win)[agent.QUICK_GROUP_ALL]
    return next(lbl for lbl, key in every if key == "missed")


def _keys(win):
    return [key for _t, items in win._ai_assistant_win.quick[1]
            for _l, key in items]


def _assistant(w):
    w._contacts = {ALI: "Ali", BOB: "Bob"}
    w._ai_assistant_win = _FakeWin()
    w._ai_drafts = None
    return w


def test_opening_chat_does_not_count_it_as_missed():
    w = _assistant(_win(jid=ALI, active=""))
    w._unread_counts = {ALI: 3, BOB: 3}
    xmpp.MainWindow._load_chat(w, ALI)
    assert _missed_label(w) == f"{agent.ACTION_LABELS['missed']} (3)"
    assert (agent.ACTION_LABELS["summarize_unread"] + " (3)",
            "summarize_unread") in _groups(w)[agent.QUICK_GROUP_CHAT]


def _msg_win():
    w = _assistant(object.__new__(xmpp.MainWindow))
    w.active = ALI
    w.jid = "ben@x.org"
    w.chats = {}
    w.rooms = []
    w._chat_tabs = {}
    w._chat_enc_modes = {}
    w._unread_counts = {BOB: 1}
    w._resolve_reply = lambda reply, frm: reply
    w._remember_mid = lambda jid, mid: None
    w._is_live_duplicate = lambda *a: False
    w._store = lambda *a, **k: None
    w._deliver_live = lambda *a: None
    w._ai_away_note_message = lambda jid: None
    w._note_inactive_live = lambda jid: None
    w._refresh_contacts = lambda: None
    w._show_toast = lambda *a: None
    w._notify_enabled = w._sound_enabled = False
    w.root = types.SimpleNamespace(title=lambda *a: None)
    xmpp.MainWindow._ai_assistant_refresh(w)
    return w


def test_incoming_message_updates_missed_count():
    w = _msg_win()
    xmpp.MainWindow._handle(w, "msg", {"from": BOB, "nick": "Bob",
                                       "body": "Selam", "mid": "m-1"})
    assert w._unread_counts[BOB] == 2
    assert _missed_label(w).endswith("(2)")


def test_read_on_phone_updates_missed_count():
    w = _msg_win()
    xmpp.MainWindow._handle(w, "read_elsewhere", BOB)
    assert _missed_label(w) == agent.ACTION_LABELS["missed"]


def test_own_message_from_phone_updates_missed_count():
    w = _msg_win()
    xmpp.MainWindow._handle(w, "own_msg", {
        "to": BOB, "body": "Telefondan", "oob": "", "encrypted": False,
        "mid": "o-1", "reply": None})
    assert _missed_label(w) == agent.ACTION_LABELS["missed"]


def test_ready_draft_adds_drafts_chip():
    w = _msg_win()
    assert "drafts" not in _keys(w)
    entry = xmpp.MainWindow._ai_draft_entry(w, BOB)
    entry.update(options=["Tamam"], state="ready")
    xmpp.MainWindow._ai_drafts_refresh(w)
    assert "drafts" in _keys(w)


def test_unchanged_counts_do_not_rebuild_chips():
    w = _msg_win()
    calls = []
    w._ai_assistant_win.set_quick_actions = lambda *a: calls.append(a)
    xmpp.MainWindow._ai_assistant_refresh(w)
    xmpp.MainWindow._ai_assistant_refresh(w)
    assert len(calls) <= 1


# "📬 Okunmamışları özetle (n)" açılıştaki sayıyı tutar; kullanıcı o sohbete
# yanıt verince (masaüstünden ya da telefondan) okunmamışlara yetişmiş
# sayılır. Kanıt (kod incelemesi, 2026-10-25): sayı sohbet yeniden açılana
# dek hep "(n)" kalıyordu — yanıttan sonra da ⋮ menüsünde ve çipte.
def _unread_chip(win):
    return [lbl for lbl, key in _groups(win)[agent.QUICK_GROUP_CHAT]
            if key == "summarize_unread"]


def test_reply_from_desktop_clears_unread_summary_count():
    from test_2p_consecutive_send import _o_w
    w = _assistant(_o_w(["Tamam, bakarım"]))
    w.active = ALI
    w._ai_unread_at_open = {ALI: 3}
    w._ai_agent_context = lambda: ALI
    xmpp.MainWindow._ai_assistant_refresh(w)
    assert _unread_chip(w)
    xmpp.MainWindow._send_message(w)
    assert w._ai_unread_at_open[ALI] == 0
    assert not _unread_chip(w)


def test_reply_from_phone_clears_unread_summary_count():
    w = _msg_win()
    w._ai_unread_at_open = {ALI: 3}
    w._ai_agent_context = lambda: ALI
    xmpp.MainWindow._ai_assistant_refresh(w)
    assert _unread_chip(w)
    xmpp.MainWindow._handle(w, "own_msg", {
        "to": ALI, "body": "Telefondan", "oob": "", "encrypted": False,
        "mid": "o-2", "reply": None})
    assert w._ai_unread_at_open[ALI] == 0
    assert not _unread_chip(w)


def test_bot_command_keeps_unread_summary_count():
    from test_2p_consecutive_send import _o_w
    w = _o_w(["/help"])
    w.active = ALI
    w._ai_unread_at_open = {ALI: 3}
    w._handle_bot_command = lambda body: None
    xmpp.MainWindow._send_message(w)
    assert w._ai_unread_at_open[ALI] == 3
