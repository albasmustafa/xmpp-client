"""Bildirim kontrolü: sessize alma, odada yalnız adım geçince, Meşgul susar.

Kanıt (2026-11-23 kod okuması): oda mesajları da 1:1 mesajlarla aynı "msg"
olayından geçiyordu (xmppcore/muc.py → MainWindow._handle); açık olmayan her
oda mesajı masaüstü bildirimi + ses + toast çıkarıyordu, Meşgul durumu ve
sohbet başına sessize alma yoktu. Web köprüsü de her mesajı bildiriyordu.

Sözleşme:
- Kurallar `xmppcore/notify_policy` içindedir (Tk'sız, ağsız); masaüstü ve web
  aynı config anahtarlarını (`muted_chats`, `room_notify_all`) kullanır.
- Politika yalnız dikkat çeken yan etkileri keser: okunmamış sayacı artar.
"""
import json
import time
import types

import pytest
from test_ai_agent import _FakeWin
from test_webapp import CFG, session  # noqa: F401  (fixture)

import xmpp
from ui import sidebar as ui_sidebar
from xmppcore import config as xcfg
from xmppcore import notify_policy as np

NOW = 1_800_000_000.0
ALI, ROOM = "ali@x.org", "oda@conf.x.org"


# ── Çekirdek kurallar ───────────────────────────────────────────────────────
def test_mute_durations_expire():
    cfg = {}
    np.set_mute(cfg, ALI, "1h", now=NOW)
    assert cfg["muted_chats"] == {ALI: NOW + 3600}
    assert np.is_muted(cfg, ALI, now=NOW + 3599)
    assert not np.is_muted(cfg, ALI, now=NOW + 3601)
    np.set_mute(cfg, ALI, "8h", now=NOW)
    assert np.muted_until(cfg, ALI, now=NOW) == NOW + 8 * 3600
    np.set_mute(cfg, ALI, "1d", now=NOW)
    assert np.muted_until(cfg, ALI, now=NOW) == NOW + 86400


def test_mute_forever_and_unmute():
    cfg = {}
    np.set_mute(cfg, ALI, "forever", now=NOW)
    assert np.muted_until(cfg, ALI, now=NOW + 10**9) == np.MUTE_FOREVER
    np.set_mute(cfg, ALI, None, now=NOW)
    assert np.muted_until(cfg, ALI, now=NOW) is None
    assert cfg["muted_chats"] == {}


def test_expired_entries_are_pruned_on_write_and_snapshot():
    cfg = {"muted_chats": {"eski@x": NOW - 1, "kalici@x": 0}}
    assert np.snapshot(cfg, now=NOW)["muted"] == {"kalici@x": 0}
    np.set_mute(cfg, ALI, "1h", now=NOW)
    assert set(cfg["muted_chats"]) == {"kalici@x", ALI}


@pytest.mark.parametrize("raw", [None, [], "x", {ALI: "yarın"}, {ALI: True},
                                 {ALI: None}])
def test_malformed_config_never_mutes_or_crashes(raw):
    cfg = {"muted_chats": raw, "room_notify_all": "bozuk"}
    assert not np.is_muted(cfg, ALI, now=NOW)
    assert np.should_notify(cfg, ALI, "selam", is_room=False, now=NOW)
    assert np.snapshot(cfg, now=NOW) == {"muted": {}, "room_all": []}


@pytest.mark.parametrize("body", ["albas selam", "@albas bakar mısın",
                                  "ALBAS: naber", "Albas'a sor", "hey, albas!"])
def test_mentions_whole_word(body):
    assert np.mentions(body, "albas")


@pytest.mark.parametrize("body", ["albasmustafa geldi", "kalbas", "", "selam"])
def test_mentions_rejects_partial_words(body):
    assert not np.mentions(body, "albas")


def test_mentions_turkish_letters_and_regex_chars():
    assert np.mentions("ilker gel", "İlker")
    assert np.mentions("ILKER gel", "ılker")
    assert np.mentions("a.b neredesin", "a.b")
    assert not np.mentions("axb neredesin", "a.b")
    assert not np.mentions("herhangi", "")


def _ok(cfg=None, body="selam", **kw):
    kw.setdefault("is_room", False)
    return np.should_notify(cfg or {}, kw.pop("jid", ALI), body, now=NOW, **kw)


def test_should_notify_direct_chats():
    assert _ok()
    assert not _ok({"muted_chats": {ALI: 0}})
    assert not _ok(my_show="dnd")
    assert _ok(my_show="away")


def test_should_notify_rooms_default_to_mentions_and_replies():
    room = {"jid": ROOM, "is_room": True, "my_nick": "albas"}
    assert not _ok(body="herkese selam", **room)
    assert _ok(body="albas sen ne dersin", **room)
    assert _ok(body="katılıyorum", reply_sender="Ben", **room)
    assert _ok(body="katılıyorum", reply_sender="albas", **room)
    assert not _ok(body="katılıyorum", reply_sender="veli", **room)
    assert not _ok(body="albas", my_show="dnd", **room)


def test_room_all_and_mute_override():
    cfg = np.set_room_all({}, ROOM, True)
    room = {"jid": ROOM, "is_room": True, "my_nick": "albas"}
    assert _ok(cfg, body="herkese selam", **room)
    np.set_mute(cfg, ROOM, "forever", now=NOW)
    assert not _ok(cfg, body="albas acil", **room)
    np.set_room_all(cfg, ROOM, False)
    assert cfg["room_notify_all"] == []


def test_end_text_same_day_and_other_day():
    today = time.mktime((2026, 11, 23, 9, 0, 0, 0, 0, -1))
    assert np.end_text(today + 3600, now=today) == "10:00"
    assert np.end_text(today + 86400, now=today) == "24.11 09:00"
    assert np.end_text(np.MUTE_FOREVER, now=today) == ""


# ── Önbellekli config okuma (her gelen mesajda dosya ayrıştırılmaz) ───────────
def test_cached_config_reloads_only_when_file_changes(monkeypatch, tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(path))
    first = xcfg._load_config_cached()
    assert first == {"a": 1}
    assert xcfg._load_config_cached() is first           # değişmedi: aynı nesne
    xcfg._save_config({"a": 1, "muted_chats": {ALI: 0}})  # web/masaüstü yazdı
    assert np.is_muted(xcfg._load_config_cached(), ALI)
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(tmp_path / "yok.json"))
    assert xcfg._load_config_cached() == {}


# ── Masaüstü: gelen mesaj yolu ───────────────────────────────────────────────
def _desktop(monkeypatch, tmp_path, cfg=None):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(cfg or {}), encoding="utf-8")
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(path))
    alerts = []
    monkeypatch.setattr(xmpp, "_desktop_notify",
                        lambda title, body, **k: alerts.append(("notify", title)))
    w = object.__new__(xmpp.MainWindow)
    w.active = "baska@x.org"
    w.jid = "albas@x.org"
    w.chats = {}
    w.rooms = [ROOM]
    w.my_nick = {ROOM: "albas"}
    w._contacts = {ALI: "Ali"}
    w._chat_tabs = {}
    w._chat_enc_modes = {}
    w._unread_counts = {}
    w._ai_assistant_win = _FakeWin()
    w._ai_drafts = None
    w._resolve_reply = lambda reply, frm: reply
    w._remember_mid = lambda jid, mid: None
    w._is_live_duplicate = lambda *a: False
    w._store = lambda *a, **k: None
    w._ai_away_note_message = lambda jid: None
    w._note_inactive_live = lambda jid: None
    w._refresh_contacts = lambda: None
    w._ai_assistant_refresh = lambda: None
    w._show_toast = lambda title, msg, **k: alerts.append(("toast", title))
    w._play_notification_sound = lambda: alerts.append(("sound", ""))
    w._notify_enabled = w._sound_enabled = True
    w.root = types.SimpleNamespace(title=lambda *a: None)
    monkeypatch.setattr(xmpp.threading, "Thread",
                        lambda target, daemon=None: types.SimpleNamespace(
                            start=target))
    return w, alerts


def _incoming(w, frm, body, nick="Veli", reply=None):
    xmpp.MainWindow._handle(w, "msg", {"from": frm, "nick": nick, "body": body,
                                       "mid": f"m-{body}", "reply": reply})


def test_desktop_direct_message_alerts(monkeypatch, tmp_path):
    w, alerts = _desktop(monkeypatch, tmp_path)
    _incoming(w, ALI, "selam")
    assert [kind for kind, _ in alerts] == ["notify", "sound", "toast"]
    assert w._unread_counts[ALI] == 1


def test_desktop_muted_chat_counts_but_stays_silent(monkeypatch, tmp_path):
    w, alerts = _desktop(monkeypatch, tmp_path, {"muted_chats": {ALI: 0}})
    _incoming(w, ALI, "selam")
    assert alerts == []
    assert w._unread_counts[ALI] == 1


def test_desktop_room_alerts_only_on_mention(monkeypatch, tmp_path):
    w, alerts = _desktop(monkeypatch, tmp_path)
    _incoming(w, ROOM, "herkese günaydın")
    assert alerts == [] and w._unread_counts[ROOM] == 1
    _incoming(w, ROOM, "albas sen gelecek misin?")
    assert [kind for kind, _ in alerts] == ["notify", "sound", "toast"]


def test_desktop_dnd_silences_everything(monkeypatch, tmp_path):
    w, alerts = _desktop(monkeypatch, tmp_path)
    w._my_show = "dnd"
    _incoming(w, ALI, "selam")
    _incoming(w, ROOM, "albas acil")
    assert alerts == []


def test_set_chat_mute_saves_toasts_and_schedules_refresh(monkeypatch, tmp_path):
    w, alerts = _desktop(monkeypatch, tmp_path)
    afters, refreshed = [], []
    w.root = types.SimpleNamespace(after=lambda ms, fn: afters.append(ms))
    w._refresh_contacts = lambda: refreshed.append(1)
    xmpp.MainWindow._set_chat_mute(w, ALI, "1h")
    assert np.is_muted(xmpp._load_config(), ALI)
    assert alerts[-1] == ("toast", "🔕 Sessize alındı")
    assert afters and 3600_000 <= afters[0] <= 3602_000
    xmpp.MainWindow._set_chat_mute(w, ALI, None)
    assert not np.is_muted(xmpp._load_config(), ALI)
    assert alerts[-1] == ("toast", "🔔 Bildirimler açıldı")
    assert len(refreshed) == 2
    xmpp.MainWindow._set_room_notify_all(w, ROOM, True)
    assert xmpp._load_config()["room_notify_all"] == [ROOM]


def test_sidebar_rows_show_mute_icon():
    class _List:
        def __init__(self):
            self.rows = []

        def delete(self, *a):
            self.rows.clear()

        def insert(self, i, label):
            self.rows.append(label)

        def itemconfig(self, *a, **k):
            pass

    contacts = _List()
    ui_sidebar.render_contacts(contacts, {ALI: "Ali"}, {}, [], {ALI: 2}, [ALI],
                               muted={ALI})
    assert contacts.rows == ["  ● Ali 🔕 (2)"]
    rooms = _List()
    ui_sidebar.render_rooms(rooms, [ROOM], muted={ROOM})
    assert rooms.rows == ["  💬  oda 🔕"]


# ── ⋮ menüsü: 🔔 Bildirimler alt menüsü ──────────────────────────────────────
def _notify_items(**kw):
    spec = xmpp._chat_header_menu_spec(is_room=kw.pop("is_room", False),
                                       compact=False, notify=kw)
    chat = next(item[2] for item in spec if item[0] == "menu"
                and item[1] == "💬 Sohbet")
    sub = next(item[2] for item in chat if item[0] == "menu")
    return [(item[1], item[2]) for item in sub if item[0] == "item"]


def test_header_menu_notify_submenu_states():
    keys = [k for _l, k in _notify_items()]
    assert keys == ["mute_1h", "mute_8h", "mute_1d", "mute_forever"]
    assert _notify_items(muted_until=0)[0] == ("🔔 Sesi Aç (süresiz)", "unmute")
    label, key = _notify_items(muted_until=time.time() + 600)[0]
    assert key == "unmute" and label.startswith("🔔 Sesi Aç (bitiş ")
    assert _notify_items(is_room=True)[-1] == ("🔔 Her Mesajda Bildir", "room_all")
    assert _notify_items(is_room=True, room_all=True)[-1] == (
        "@ Yalnız Adım Geçince Bildir", "room_mention")


# ── Web köprüsü ──────────────────────────────────────────────────────────────
def _web_msg(s, frm, body, reply=None):
    s._apply("msg", {"from": frm, "nick": "veli", "body": body, "type": "chat",
                     "oob": "", "encrypted": False, "mid": f"m-{body}",
                     "reply": reply})
    return s.sink.get_nowait()["data"]


def test_web_msg_carries_notify_flag(session):  # noqa: F811
    session.rooms = {ROOM}
    session.bot.my_nicks[ROOM] = "albas"
    assert _web_msg(session, ALI, "selam")["notify"] is True
    assert _web_msg(session, ROOM, "herkese selam")["notify"] is False
    assert _web_msg(session, ROOM, "albas bak")["notify"] is True
    CFG["muted_chats"] = {ALI: 0}
    data = _web_msg(session, ALI, "yine selam")
    assert data["notify"] is False and data["is_unread"] is True


def test_web_dnd_presence_silences(session):  # noqa: F811
    session.command("set_presence", {"show": "dnd", "status": ""})
    assert _web_msg(session, ALI, "selam")["notify"] is False
    session.command("set_presence", {"show": "online", "status": ""})
    assert _web_msg(session, ALI, "selam 2")["notify"] is True


def test_web_set_notify_command_saves_and_broadcasts(session):  # noqa: F811
    r = session.command("set_notify", {"jid": ALI, "choice": "8h"})
    assert r["ok"] and ALI in r["prefs"]["muted"]
    assert np.is_muted(CFG, ALI)
    ev = session.sink.get_nowait()
    assert ev["ev"] == "notify_prefs" and ALI in ev["data"]["muted"]
    session.command("set_notify", {"jid": ROOM, "choice": "room_all"})
    assert CFG["room_notify_all"] == [ROOM]
    session.command("set_notify", {"jid": ALI, "choice": "unmute"})
    assert not np.is_muted(CFG, ALI)
    assert session.snapshot()["notify_prefs"] == {"muted": {},
                                                  "room_all": [ROOM]}


@pytest.mark.parametrize("args", [{"jid": "", "choice": "1h"},
                                  {"jid": ALI, "choice": "sonsuza"},
                                  {"jid": ALI}])
def test_web_set_notify_rejects_bad_input(session, args):  # noqa: F811
    assert session.command("set_notify", args)["ok"] is False
    assert "muted_chats" not in CFG and "room_notify_all" not in CFG
