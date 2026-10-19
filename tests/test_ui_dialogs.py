"""ui/dialogs extraction sözleşmeleri (Faz 4A).

MainWindow metotları artık ince delegasyon sarmalayıcısıdır; içerik
ui modülünde yaşar ve MainWindow state'i parametre olarak geçirilir.
"""

import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from ui.dialogs import chat_actions as ui_chat_actions  # noqa: E402
from ui.dialogs import chat_options as ui_chat_options  # noqa: E402
from ui.dialogs import presence as ui_presence  # noqa: E402
from ui.dialogs import rooms as ui_rooms  # noqa: E402
from ui.dialogs import simple as ui_simple  # noqa: E402


def test_shortcuts_dialog_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(ui_simple, "show_shortcuts",
                        lambda parent: calls.append(parent))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    xmpp.MainWindow._shortcuts_dialog(win)
    assert calls == ["ROOT"]


def test_reaction_details_dialog_passes_data(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ui_simple, "show_reaction_details",
        lambda parent, reactions, emoji=None:
            calls.append((parent, reactions, emoji)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.active = "a@b"                          # [2M] tepki anahtarı (jid, mid)
    win._reactions = {("a@b", "m1"): {"👍": ["Ali"]}}

    xmpp.MainWindow._reaction_details_dialog(win, "m1")
    xmpp.MainWindow._reaction_details_dialog(win, "m1", "👍")

    assert calls == [
        ("ROOT", {"👍": ["Ali"]}, None),
        ("ROOT", {"👍": ["Ali"]}, "👍"),
    ]


def test_dialog_icerikleri_ui_modulunde():
    assert "Ctrl+F" in inspect.getsource(ui_simple.show_shortcuts)
    assert "Ctrl+F" not in inspect.getsource(xmpp.MainWindow._shortcuts_dialog)
    assert "😊 Tepkiler" in inspect.getsource(ui_simple.show_reaction_details)
    assert "😊 Tepkiler" not in inspect.getsource(
        xmpp.MainWindow._reaction_details_dialog)


# ── 4A dilim-2: chat options (kaybolan mesajlar / geçmiş silme) ─────────────

def test_disappearing_dialog_delegates_and_applies(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ui_chat_options, "show_disappearing",
        lambda parent, ttl, on_apply: calls.append((parent, ttl, on_apply)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.active = "a@b.c"
    win._disappearing_ttl = {"a@b.c": 300}

    xmpp.MainWindow._disappearing_dialog(win)

    parent, ttl, on_apply = calls[0]
    assert (parent, ttl) == ("ROOT", 300)
    # Orijinal davranış: hedef sohbet uygulama anında okunur
    win.active = "x@y.z"
    on_apply(60)
    assert win._disappearing_ttl == {"a@b.c": 300, "x@y.z": 60}


def test_disappearing_dialog_noop_without_active(monkeypatch):
    calls = []
    monkeypatch.setattr(ui_chat_options, "show_disappearing",
                        lambda *a, **k: calls.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.active = None

    xmpp.MainWindow._disappearing_dialog(win)
    assert calls == []


def test_clear_history_dialog_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ui_chat_options, "show_clear_history",
        lambda parent, total, chats, has_active, ca, call_all:
            calls.append((parent, total, chats, has_active, ca, call_all)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.chats = {"a@b.c": [1, 2], "x@y.z": [3]}
    win.active = "a@b.c"
    active_calls, all_calls = [], []
    win._clear_active_history = lambda: active_calls.append(1) or True
    win._clear_all_history = lambda: all_calls.append(1) or True

    xmpp.MainWindow._clear_history_dialog(win)

    parent, total, chats, has_active, ca, call_all = calls[0]
    assert (parent, total, chats, has_active) == ("ROOT", 3, 2, True)
    assert ca() is True and active_calls == [1] and all_calls == []
    assert call_all() is True and all_calls == [1]


def test_chat_options_icerikleri_ui_modulunde():
    assert "Kaybolan Mesajlar" in inspect.getsource(
        ui_chat_options.show_disappearing)
    assert "Kaybolan Mesajlar" not in inspect.getsource(
        xmpp.MainWindow._disappearing_dialog)
    assert "Tüm Geçmişi Sil" in inspect.getsource(
        ui_chat_options.show_clear_history)
    assert "Tüm Geçmişi Sil" not in inspect.getsource(
        xmpp.MainWindow._clear_history_dialog)


# ── 4A dilim-3: mesaj eylemi + oda dialogları ───────────────────────────────

def test_edit_message_dialog_delegates_and_sends(monkeypatch):
    monkeypatch.setattr(
        ui_chat_actions, "ask_edit_message",
        lambda parent, title, prompt, initial:
            ("yeni" if parent == "ROOT" else None))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.active = "a@b.c"
    win._bubble_widgets = []
    win.chats = {"a@b.c": []}
    monkeypatch.setattr(xmpp, "_db_update_msg_body", lambda *a: None)
    sent = []
    win.bot = types.SimpleNamespace(
        send_correction=lambda to, body, mid, mtype:
            sent.append((to, body, mid, mtype)))

    xmpp.MainWindow._edit_message_dialog(win, "m1", "eski", "chat")

    assert sent == [("a@b.c", "yeni", "m1", "chat")]


def test_edit_message_dialog_unchanged_no_send(monkeypatch):
    monkeypatch.setattr(ui_chat_actions, "ask_edit_message",
                        lambda *a: "eski")
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.active = "a@b.c"
    sent = []
    win.bot = types.SimpleNamespace(
        send_correction=lambda *a: sent.append(a))

    xmpp.MainWindow._edit_message_dialog(win, "m1", "eski", "chat")
    assert sent == []


def test_invite_dialog_delegates(monkeypatch):
    monkeypatch.setattr(ui_rooms, "ask_invite",
                        lambda parent, room: ("ali@b.c", "gel"))
    calls = []
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.bot = types.SimpleNamespace(
        invite_to_room=lambda *a: calls.append(a))

    xmpp.MainWindow._invite_to_room_dialog(win, "oda@conf")
    assert calls == [("oda@conf", "ali@b.c", "gel")]


def test_invite_dialog_cancel_noop(monkeypatch):
    monkeypatch.setattr(ui_rooms, "ask_invite", lambda *a: None)
    calls = []
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.bot = types.SimpleNamespace(
        invite_to_room=lambda *a: calls.append(a))

    xmpp.MainWindow._invite_to_room_dialog(win, "oda@conf")
    assert calls == []


def test_common_groups_dialog_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ui_rooms, "show_common_groups",
        lambda parent, name, jid, rooms, members:
            calls.append((parent, name, jid, rooms, members)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win._contacts = {"ali@b.c": "Ali"}
    win.rooms = ["r@conf"]
    win.room_members = {"r@conf": {"ali": {}}}

    xmpp.MainWindow._common_groups_dialog(win, "ali@b.c")

    assert calls == [("ROOT", "Ali", "ali@b.c", ["r@conf"],
                      {"r@conf": {"ali": {}}})]


def test_dilim3_icerikleri_ui_modulunde():
    assert "Davet Gönder" in inspect.getsource(ui_rooms.ask_invite)
    assert "Davet Gönder" not in inspect.getsource(
        xmpp.MainWindow._invite_to_room_dialog)
    assert "Ortak Gruplar" in inspect.getsource(ui_rooms.show_common_groups)
    assert "Ortak Gruplar" not in inspect.getsource(
        xmpp.MainWindow._common_groups_dialog)


# ── 4A dilim-4: presence (durum/konum) + forward ────────────────────────────

def test_status_dialog_delegates_and_applies(monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_presence, "show_status",
        lambda parent, on_apply: captured.append((parent, on_apply)))
    saved = {}
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda c: saved.update(c))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    calls = []
    win.bot = types.SimpleNamespace(
        set_status_message=lambda t, s: calls.append((t, s)))

    xmpp.MainWindow._status_dialog(win)

    parent, on_apply = captured[0]
    assert parent == "ROOT"
    on_apply("merhaba", "dnd")
    assert calls == [("merhaba", "dnd")]
    assert saved["status_text"] == "merhaba"   # yeniden bağlanınca da geçerli


def test_status_dialog_bot_none_noop(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_presence, "show_status",
                        lambda p, cb: captured.append(cb))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.bot = None
    xmpp.MainWindow._status_dialog(win)
    captured[0]("x", "away")  # bot yokken sessiz kalmalı


def test_location_dialog_delegates(monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_presence, "show_location",
        lambda parent, pub, stop: captured.append((parent, pub, stop)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    calls = []
    win.bot = types.SimpleNamespace(
        publish_location=lambda *a: calls.append(("pub",) + a),
        stop_location=lambda: calls.append(("stop",)))

    xmpp.MainWindow._location_dialog(win)

    parent, pub, stop = captured[0]
    assert parent == "ROOT"
    pub(41.0, 29.0, "İst")
    stop()
    assert calls == [("pub", 41.0, 29.0, "İst"), ("stop",)]


def test_forward_dialog_delegates(monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_chat_actions, "show_forward",
        lambda parent, contacts, rooms, body, sender, on_forward:
            captured.append((parent, dict(contacts), list(rooms), body,
                             sender, on_forward)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win._contacts = {"a@b.c": "Ali"}
    win.rooms = ["r@conf"]
    calls = []
    # Gönderim (hedefin şifrelemesi, yerel kayıt) _forward_to'dadır:
    # test_forward_encryption.py
    win._forward_to = lambda *a: calls.append(a)

    xmpp.MainWindow._forward_dialog(win, "gövde", "Ali")

    parent, contacts, rooms, body, sender, on_forward = captured[0]
    assert (parent, contacts, rooms, body, sender) == (
        "ROOT", {"a@b.c": "Ali"}, ["r@conf"], "gövde", "Ali")
    on_forward("a@b.c", "chat")
    assert calls == [("a@b.c", "chat", "Ali", "gövde", False)]


def test_dilim4_icerikleri_ui_modulunde():
    assert "Durum Mesajı" in inspect.getsource(ui_presence.show_status)
    assert "Durum Mesajı" not in inspect.getsource(
        xmpp.MainWindow._status_dialog)
    assert "Konum Paylaş" in inspect.getsource(ui_presence.show_location)
    assert "Konum Paylaş" not in inspect.getsource(
        xmpp.MainWindow._location_dialog)
    assert "Mesajı İlet" in inspect.getsource(ui_chat_actions.show_forward)
    assert "Mesajı İlet" not in inspect.getsource(
        xmpp.MainWindow._forward_dialog)
