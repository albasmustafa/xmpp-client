"""Phase B2 — sent_mid pasif-sohbet reply kalıcılık çürütme/kilit testleri.

Conductor iş paketi iddiası (B2): "sent_mid pasif sohbette gelirken erken
return yüzünden _remember_reply ve _db_update_msg_reply çalışmaz; reply
ilişkisi kaybolur (sessiz veri kaybı)."

Gerçek veri akışı (bu testlerin kanıtladığı):
- Reply ilişkisi GÖNDERİM ANINDA yazılır: `_send_message` → `_store` →
  `_remember_reply(target, uid, reply_to)` (bellek) +
  `_db_store_msg(..., reply_id, ...)` (kalıcı DB).
- `sent_mid` pasif sohbet için erken dönerse yalnız REDUNDANT yeniden
  yazımlar atlanır — hiçbir bilgi kaybolmaz.

Bu testler davranışı KİLİTLER: sent_mid pasif sohbette geldiğinde
_reply_map girdisi ve DB satırı durmalıdır.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import xmpp

MID = "M1"
REPLY = {"id": "hedef-1", "sender": "Ayşe", "body": "alıntı gövde",
         "to": "a@x", "mid": "hedef-1"}


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "b2.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def _send_window(active="a@x"):
    """_send_message'ı uçtan uca sürebilen minimal pencere çifti."""
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w.rooms = []
    w.chats = {}
    w._msg_ids = {}
    w._reply_map = {}
    w._msg_inst_seq = 0
    w._disappearing_ttl = {}
    w._chat_tabs = {}
    w._bubble_widgets = []
    w._send_typing_notif = False
    w._typing_send_id = None
    w._encryption_mode = types.SimpleNamespace(get=lambda: "none")
    w.bot = types.SimpleNamespace(
        send_chat=lambda *a, **k: w.bot.sent_chat.append((a, k)),
        send_reply=lambda *a, **k: w.bot.sent_reply.append((a, k)),
        sent_chat=[], sent_reply=[])
    w._composer = types.SimpleNamespace(
        get_text=lambda: "gövde",
        clear_text=lambda: None,
        consume_reply=lambda: dict(REPLY))
    w.root = types.SimpleNamespace(after=lambda *a: None)
    w._deliver_live = lambda target, append_fn: "append"  # UI render stub
    return w


# 1. Gönderim anında kalıcılık (B2 çürütmesinin temeli) --------------------------


def test_send_persists_reply_to_db_and_reply_map(tmp_db):
    w = _send_window()
    sent = w._send_message()
    assert sent is None  # istisna yok
    # bellek-içi ilişki gönderim anında yazıldı:
    entries = w.chats["a@x"]
    assert len(entries) == 1
    mid = entries[0][7]               # üretilen gerçek mid
    uid = entries[0][9]
    assert w._reply_map[("a@x", uid)] == REPLY
    # kalıcı DB satırı reply alanlarıyla yazıldı:
    rows = xmpp._db_load_msgs("a@x")
    assert len(rows) == 1
    assert rows[0][8] == mid
    assert rows[0][9] == "hedef-1"    # reply_id
    assert rows[0][10] == "Ayşe"      # reply_sender
    # sent_mid henüz gelmedi — yine de kalıcılık TAMAM.


# 2. Pasif sohbette sent_mid: hiçbir kayıp yok ------------------------------------


def test_passive_sent_mid_preserves_association(tmp_db, monkeypatch):
    monkeypatch.setattr(xmpp, "_new_msg_id", lambda: MID)
    w = _send_window()
    w._send_message()
    w.active = "b@x"  # kullanıcı başka sohbete geçti
    # GERÇEK sent_mid işleme yolu (pasif sohbet):
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@x", "mid": MID})
    # ilişki korunur; hiçbir şey düşmez:
    uid = w.chats["a@x"][0][9]
    assert w._reply_map[("a@x", uid)] == REPLY
    assert w._msg_ids["a@x"] == [MID]


# 3. Restart/reopen: DB'den reply kalıcı -------------------------------------------


def test_reply_survives_reopen_from_db(tmp_db, monkeypatch):
    monkeypatch.setattr(xmpp, "_new_msg_id", lambda: MID)
    w = _send_window()
    w._send_message()
    w.active = "b@x"
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@x", "mid": MID})
    # yeni "oturum": aynı DB, taze pencere — reopen okuması reply'li döner
    _send_window(active="a@x")
    rows = xmpp._db_load_msgs("a@x")
    assert rows[0][9] == "hedef-1" and rows[0][10] == "Ayşe"


