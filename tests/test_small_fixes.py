"""Ufak tefek hatalar (2026-10-14 taraması) — her biri için regresyon testi."""
import asyncio
import io
import types

import pytest
from slixmpp import Message
from test_room_join_search import _bot

import xmpp
from xmppcore import messages as messages_mod
from xmppcore import muc as muc_mod


class _Cap:
    def __init__(self, ret=None):
        self.calls, self.ret = [], ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret


# ── OMEMO denetimi başarısız olunca mesaj kaybolmamalı ───────────────────────
# `self.log` botta yok: except bloğu AttributeError ile çöküp mesajı düşürüyordu.

def _omemo_broken_bot(monkeypatch, mod):
    bot = _bot()
    bot._omemo_enabled = lambda: True

    def _boom(self, name):
        raise RuntimeError("omemo bozuk")
    monkeypatch.setattr(mod, "_get_xep", _boom)
    return bot


def test_chat_message_survives_failed_omemo_check(monkeypatch):
    bot = _omemo_broken_bot(monkeypatch, messages_mod)
    msg = Message()
    msg["type"], msg["from"], msg["body"] = "chat", "ali@example.com/tel", "selam"
    xmpp.XMPPBot._on_message(bot, msg)
    kind, data = bot.gui_q.items[-1]
    assert kind == "msg" and data["body"] == "selam"


def test_room_message_survives_failed_omemo_check(monkeypatch):
    bot = _omemo_broken_bot(monkeypatch, muc_mod)
    msg = Message()
    msg["type"], msg["from"], msg["body"] = "groupchat", "oda@conf.x/veli", "selam"
    xmpp.XMPPBot._on_gc_message(bot, msg)
    kind, data = bot.gui_q.items[-1]
    assert kind == "msg" and data["nick"] == "veli"


# ── /komutlar ────────────────────────────────────────────────────────────────

def _cmd_win(monkeypatch, active="oda@conf.x"):
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    w.jid = "ben@example.com"
    w.active = active
    w.rooms = ["oda@conf.x"]
    w.my_nick = {"oda@conf.x": "benim"}
    w.msgs = []
    w._append = lambda text, tag="sys", *a, **k: w.msgs.append(text)
    w.bot = types.SimpleNamespace(
        muc_service="conf.x", leave_room=_Cap(), join_room=_Cap(),
        invite_to_room=_Cap(), ban_user=_Cap(), send_correction=_Cap(),
        set_status_message=_Cap())
    w.errors = []
    monkeypatch.setattr(xmpp.messagebox, "showerror",
                        lambda t, m, **k: w.errors.append(m))
    return w


def test_leave_command_passes_nick(monkeypatch):
    """/leave botun leave_room(room, nick) imzasını karşılamıyordu (TypeError)."""
    w = _cmd_win(monkeypatch)
    xmpp.MainWindow._handle_bot_command(w, "/leave")
    assert w.bot.leave_room.calls == [(("oda@conf.x", "benim"), {})]


def test_join_command_normalizes_room(monkeypatch):
    w = _cmd_win(monkeypatch)
    xmpp.MainWindow._handle_bot_command(w, "/join Linux@Conf.X")
    assert w.bot.join_room.calls == [(("linux@conf.x", "ben"), {})]
    assert "linux@conf.x" in w.my_nick and "Linux@Conf.X" not in w.my_nick


@pytest.mark.parametrize("cmd, attr", [("/invite", "invite_to_room"),
                                       ("/ban", "ban_user")])
def test_invite_and_ban_validate_jid(monkeypatch, cmd, attr):
    w = _cmd_win(monkeypatch)
    xmpp.MainWindow._handle_bot_command(w, f"{cmd} ali veli@x.org")
    assert getattr(w.bot, attr).calls == [] and w.errors
    xmpp.MainWindow._handle_bot_command(w, f"{cmd} Ali@X.org")
    assert getattr(w.bot, attr).calls[0][0][:2] == ("oda@conf.x", "ali@x.org")


def test_edit_command_persists_correction(monkeypatch):
    """/edit balonu değiştirip DB'yi atlıyordu; yeniden başlatınca eski metin."""
    w = _cmd_win(monkeypatch, active="ali@x.org")
    w._last_message_row = lambda mine: types.SimpleNamespace(_mid="m1")
    applied = []
    w._apply_local_correction = lambda jid, mid, body: applied.append(
        (jid, mid, body))
    xmpp.MainWindow._handle_bot_command(w, "/edit yeni metin")
    assert w.bot.send_correction.calls[0][0][:3] == ("ali@x.org", "yeni metin", "m1")
    assert applied == [("ali@x.org", "m1", "yeni metin")]


# ── Durum mesajı ─────────────────────────────────────────────────────────────

def _status_win(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    w.bot = types.SimpleNamespace(set_status_message=_Cap(), set_presence=_Cap())
    w.status_var = types.SimpleNamespace(set=lambda v: None)
    w._status_label = types.SimpleNamespace(config=lambda **k: None)
    store = {}
    monkeypatch.setattr(xmpp, "_load_config", lambda: dict(store))
    monkeypatch.setattr(xmpp, "_save_config",
                        lambda c: (store.clear(), store.update(c)))
    return w, store


def test_publish_status_persists_and_remembers(monkeypatch):
    """⋮ → Durum Mesajı ve /status kaydedilmiyordu: yeniden bağlanınca
    Ayarlar'daki eski metin geri yayınlanıyordu."""
    w, store = _status_win(monkeypatch)
    xmpp.MainWindow._publish_status(w, "Toplantıda", "dnd")
    assert w.bot.set_status_message.calls == [(("Toplantıda", "dnd"), {})]
    assert store["status_text"] == "Toplantıda" and store["presence_show"] == "dnd"
    assert w._status_text == "Toplantıda"


def test_status_command_uses_publish(monkeypatch):
    w = _cmd_win(monkeypatch)
    seen = []
    w._publish_status = lambda text, show="chat": seen.append((text, show))
    xmpp.MainWindow._handle_bot_command(w, "/status Kahve molası")
    assert seen == [("Kahve molası", "chat")]


def test_status_menu_keeps_status_text(monkeypatch):
    """Durum menüsünden seçim durum mesajını siliyordu (metinsiz presence)."""
    w, _ = _status_win(monkeypatch)
    w._status_text = "Toplantıda"
    xmpp.MainWindow._set_status(w, "Uzakta", "away", "#abc")
    assert w.bot.set_presence.calls == [(("away",), {"status": "Toplantıda"})]


# ── Zamanlanmış mesaj ────────────────────────────────────────────────────────

def _sched_win(enc="omemo", leak_ok=True):
    w = object.__new__(xmpp.MainWindow)
    w.active, w.rooms, w.chats = "ali@x.org", [], {}
    timers = []
    w.root = types.SimpleNamespace(after=lambda ms, cb: timers.append((ms, cb)))
    w._after = lambda ms, cb: timers.append((ms, cb))
    mode = {"v": enc}
    w._encryption_mode = types.SimpleNamespace(get=lambda: mode["v"])
    w._leak_guard_ok = lambda target, body, enc_mode, parent=None: leak_ok
    w.msgs = []
    w._append = lambda text, tag="sys", *a, **k: w.msgs.append(text)
    w._store = lambda *a, **k: None
    w._deliver_live = lambda *a, **k: None
    w.bot = types.SimpleNamespace(send_chat=_Cap(), send_gc=_Cap())
    return w, timers, mode


def test_scheduled_message_keeps_encryption_of_its_chat():
    """Şifreleme gönderim anındaki AÇIK sohbetten okunuyordu: OMEMO sohbette
    zamanlanan mesaj, o an şifresiz sohbet açıksa düz metin gidiyordu."""
    w, timers, mode = _sched_win("omemo")
    assert xmpp.MainWindow._schedule_send(w, "ali@x.org", "gizli plan", 5)
    assert timers[0][0] == 5 * 60 * 1000
    w.active, mode["v"] = "veli@x.org", "none"     # başka sohbete geçildi
    timers[0][1]()
    assert w.bot.send_chat.calls[0][1]["encryption"] == "omemo"


def test_scheduled_message_respects_leak_guard():
    w, timers, _ = _sched_win("none", leak_ok=False)
    assert not xmpp.MainWindow._schedule_send(w, "ali@x.org", "TR33 0006 …", 5)
    assert timers == []


@pytest.mark.parametrize("body, shown", [("kısa", "kısa"),
                                         ("x" * 50, "x" * 40 + "…")])
def test_scheduled_notice_truncates_only_long_text(body, shown):
    w, _, _ = _sched_win("none")
    xmpp.MainWindow._schedule_send(w, "ali@x.org", body, 1)
    assert w.msgs[-1].endswith(shown)


# ── Odaya Katıl: var olmayan adres kilitli oda bırakmamalı ───────────────────

class _X45:
    def __init__(self, bot, codes):
        self.bot, self.codes, self.submitted = bot, set(codes), []

    async def join_muc_wait(self, room, nick, **kw):
        self.bot.events.fire(f"muc::{room}::self-presence", {
            "muc": {"status_codes": self.codes, "affiliation": "owner"},
            "type": "available"})

    async def set_room_config(self, room, form):
        self.submitted.append(form)


def test_plain_join_unlocks_room_the_server_just_created(monkeypatch):
    """Sunucu yeni (kilitli) oda açtıysa anında oda gönderilmeli; yoksa kimse
    giremez ve Prosody odayı birkaç dakika sonra siler."""
    bot = _bot()
    x45 = _X45(bot, {110, 201})
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, n: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, "yeni@conf.x", "ben"))
    assert len(x45.submitted) == 1 and x45.submitted[0].get_fields() == {}
    kinds = [k for k, _d in bot.gui_q.items]
    assert kinds[0] == "room_joined" and "sys_msg" in kinds


def test_plain_join_existing_room_sends_no_config(monkeypatch):
    bot = _bot()
    x45 = _X45(bot, {110})
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, n: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, "eski@conf.x", "ben"))
    assert x45.submitted == []


# ── Hesap değiştirme ─────────────────────────────────────────────────────────

def test_switch_account_drops_previous_server(monkeypatch):
    """Önceki hesabın özel sunucu/portu kalıyor, yeni hesap oraya bağlanıyordu."""
    w = object.__new__(xmpp.MainWindow)
    saved = {}
    monkeypatch.setattr(xmpp, "_load_config", lambda: {
        "jid": "eski@a.org", "server": "gw.a.org", "port": 5223})
    monkeypatch.setattr(xmpp, "_save_config", lambda c: saved.update(c))
    monkeypatch.setattr(xmpp, "_encode_pw", lambda pw: f"enc:{pw}")
    w.root = types.SimpleNamespace(after=lambda ms, cb: None)
    w._after = lambda ms, cb: None
    w._show_toast = lambda *a, **k: None
    xmpp.MainWindow._switch_account(w, {"jid": "yeni@b.org", "password": "pw"})
    assert saved["jid"] == "yeni@b.org"
    assert "server" not in saved and "port" not in saved


# ── Giriş ekranı: yer tutucu metin JID olarak gönderilmemeli ─────────────────

def test_login_ignores_placeholder_text(monkeypatch):
    warned, logins = [], []
    monkeypatch.setattr(xmpp.messagebox, "showwarning",
                        lambda t, m, **k: warned.append(m))
    lw = object.__new__(xmpp.LoginWindow)
    var = lambda v: types.SimpleNamespace(get=lambda: v)  # noqa: E731
    lw.jid_var, lw.pw_var = var("kullanici@sunucu.tld"), var("gizli")
    lw.srv_var, lw.port_var, lw.remember_var = var(""), var("5222"), var(False)
    lw.auto_login_var = var(False)
    lw._jid_entry = types.SimpleNamespace(_showing_ph=True)
    lw.root = types.SimpleNamespace(destroy=lambda: None)
    lw.on_login = lambda *a: logins.append(a)
    xmpp.LoginWindow._connect(lw)
    assert logins == [] and warned


# ── GIF araması: anahtar girilebilmeli ───────────────────────────────────────
# Panel "Ayarlar → GIF API anahtarı" diyordu ama böyle bir ayar yoktu.

@pytest.fixture()
def gif_cfg(monkeypatch):
    from cryptography.fernet import Fernet
    k = Fernet.generate_key()
    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: k)
    store = {}
    monkeypatch.setattr(xmpp, "_load_config", lambda: dict(store))
    monkeypatch.setattr(xmpp, "_save_config",
                        lambda c: (store.clear(), store.update(c)))
    return store


def test_gif_key_asked_once_and_stored_encrypted(monkeypatch, gif_cfg):
    asked = []
    monkeypatch.setattr(xmpp.simpledialog, "askstring",
                        lambda *a, **k: asked.append(1) or "  abc123  ")
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    assert xmpp.MainWindow._gif_api_key(w) == "abc123"
    assert gif_cfg["gif_api_key"].startswith("fernet:")
    assert xmpp.MainWindow._gif_api_key(w) == "abc123"
    assert asked == [1]


def test_gif_key_cancel_returns_none(monkeypatch, gif_cfg):
    monkeypatch.setattr(xmpp.simpledialog, "askstring", lambda *a, **k: None)
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    assert xmpp.MainWindow._gif_api_key(w) is None
    assert "gif_api_key" not in gif_cfg


def test_gif_key_plain_legacy_value_still_works(gif_cfg):
    gif_cfg["gif_api_key"] = "elle-yazilmis"
    w = object.__new__(xmpp.MainWindow)
    assert xmpp.MainWindow._gif_api_key(w) == "elle-yazilmis"


def test_gif_panel_hint_names_no_missing_setting():
    import inspect
    assert "Ayarlar → GIF" not in inspect.getsource(xmpp.MainWindow._show_gif_panel)


# ── 📖 Hikaye Paylaş ─────────────────────────────────────────────────────────

def _png(tmp_path, size=(640, 480)):
    from PIL import Image
    p = tmp_path / "foto.png"
    Image.new("RGB", size, (200, 30, 30)).save(p)
    return p


def _story_win(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.jid = "ben@example.com"
    w._avatars = {}
    calls = []
    w.bot = types.SimpleNamespace(
        set_status_message=lambda t, s: calls.append(("status", t, s)),
        publish_mood=lambda m, t: calls.append(("mood", m, t)),
        publish_avatar=lambda d, m, cb=None: calls.append(("avatar", m, d)))
    w._publish_status = lambda t, s: calls.append(("status", t, s))
    w._show_toast = lambda *a: calls.append(("toast",) + a)
    w._update_sidebar_avatar = lambda: calls.append(("sidebar",))
    monkeypatch.setattr(xmpp, "_save_avatar_cache",
                        lambda jid, data: calls.append(("cache", jid)))
    return w, calls


def test_story_mood_goes_through_bot_thread(monkeypatch):
    """Ruh hâli Tk thread'inden doğrudan eklentiye gidiyor, hata yutuluyordu."""
    w, calls = _story_win(monkeypatch)
    xmpp.MainWindow._publish_story(w, "selam", "happy", None)
    assert ("mood", "happy", "selam") in calls


def test_story_photo_becomes_proper_avatar(monkeypatch, tmp_path):
    """Ham dosya 'image/jpeg' diye (PNG bile olsa) ve küçültülmeden
    yollanıyor, yerel profil resmi güncellenmiyordu."""
    from PIL import Image
    w, calls = _story_win(monkeypatch)
    xmpp.MainWindow._publish_story(w, "", "", str(_png(tmp_path)))
    _k, mime, data = next(c for c in calls if c[0] == "avatar")
    assert mime == "image/png"
    assert Image.open(io.BytesIO(data)).size == (256, 256)
    assert w._avatars["ben@example.com"] == data
    assert ("cache", "ben@example.com") in calls and ("sidebar",) in calls


def test_bot_publish_mood_is_dispatched_to_loop(monkeypatch):
    bot = _bot()
    bot.loop = object()
    sent = []
    monkeypatch.setattr(xmpp.asyncio, "run_coroutine_threadsafe",
                        lambda coro, loop: (sent.append(coro), coro.close()))
    xmpp.XMPPBot.publish_mood(bot, "happy", "selam")
    assert len(sent) == 1
