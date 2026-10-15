"""A fazı hata düzeltmeleri için regresyon testleri.

Her test, düzeltilecek davranışın gerçek kod üzerinde çalışmasını doğrular.
GUI nesneleri ``object.__new__`` ile kurulur; yalnızca test edilen yolun
ihtiyaç duyduğu alanlar atanır.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter.filedialog as fd  # noqa: E402

from slixmpp.plugins.base import PluginManager  # noqa: E402

import xmpp  # noqa: E402


class _Q:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def _bot_stub():
    bot = object.__new__(xmpp.XMPPBot)
    bot.gui_q = _Q()
    bot._connected_ok = False
    bot.omemo_ready = False
    bot._run_out_filters = None  # XMLStream.__del__ gürültüsünü sustur
    # [2Q] Gerçek PluginManager: _get_xep artık desteklenen .plugin yolunu
    # kullanır; deprecated obj[name] yolu (DeprecationWarning) yerine.
    bot.plugin = PluginManager(bot)
    return bot


# ── A1: yanlış şifrede sonsuz yeniden bağlanma ──────────────────────────────

def test_auth_fail_sets_flag(monkeypatch):
    bot = _bot_stub()
    bot.disconnect = lambda: None
    xmpp.XMPPBot._on_auth_fail(bot, None)
    assert getattr(bot, "_auth_failed", False) is True


def test_disconnect_after_auth_fail_does_not_reconnect(monkeypatch):
    bot = _bot_stub()
    bot._auth_failed = True
    started = []

    class _T:
        def __init__(self, *a, **k):
            started.append(a)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    xmpp.XMPPBot._on_disconnect(bot, None)
    assert started == []
    assert not any("yeniden bağlan" in str(m)
                   for _, m in bot.gui_q.items)


# ── A2: kick İptal'de uygulanmamalı ─────────────────────────────────────────

def test_kick_member_cancel_does_not_kick(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    calls = []
    win.bot = type("B", (), {
        "kick_user": lambda self, room, nick, reason: calls.append(
            (room, nick, reason))})()
    win.root = None
    monkeypatch.setattr(xmpp.simpledialog, "askstring",
                        lambda *a, **k: None)
    xmpp.MainWindow._kick_member(win, "oda@conf", "ahmet")
    assert calls == []


def test_kick_member_with_reason_kicks(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    calls = []
    win.bot = type("B", (), {
        "kick_user": lambda self, room, nick, reason: calls.append(
            (room, nick, reason))})()
    win.root = None
    monkeypatch.setattr(xmpp.simpledialog, "askstring",
                        lambda *a, **k: "spam")
    xmpp.MainWindow._kick_member(win, "oda@conf", "ahmet")
    assert calls == [("oda@conf", "ahmet", "spam")]


# ── A3: dışa aktarma alan sırası ────────────────────────────────────────────

def test_export_chat_json_field_order(tmp_path, monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.active = "ali@example.com"
    win.chats = {"ali@example.com": [
        ("Ali", "merhaba", False, "12:00", "them", "", False)]}
    win.root = None
    target = tmp_path / "chat.json"
    monkeypatch.setattr(xmpp.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(fd, "asksaveasfilename",
                        lambda *a, **k: str(target))
    xmpp.MainWindow._export_chat(win)
    data = json.loads(target.read_text("utf-8"))
    assert data[0]["sender"] == "Ali"
    assert data[0]["body"] == "merhaba"
    assert data[0]["time"] == "12:00"
    assert data[0]["tag"] == "them"


def test_export_chat_txt_field_order(tmp_path, monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.active = "ali@example.com"
    win.chats = {"ali@example.com": [
        ("Ali", "merhaba", False, "12:00", "them", "", False)]}
    win.root = None
    target = tmp_path / "chat.txt"
    monkeypatch.setattr(xmpp.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(fd, "asksaveasfilename",
                        lambda *a, **k: str(target))
    xmpp.MainWindow._export_chat(win)
    body = target.read_text("utf-8")
    assert "[12:00] Ali: merhaba" in body


# ── A4: filtreli oda listesinde doğru odayı açma ────────────────────────────

def test_on_room_select_uses_filtered_mapping(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.rooms = ["a@conf", "b@conf", "c@conf"]
    win._room_jids = ["c@conf"]

    class _List:
        def curselection(self):
            return (0,)

    win.room_list = _List()
    loaded = []
    win._load_chat = lambda r: loaded.append(r)
    win._show_members = lambda r: None
    win._hide_members = lambda: None
    xmpp.MainWindow._on_room_select(win, None)
    assert loaded == ["c@conf"]


# ── A5: MUC davetinde oda JID'si ────────────────────────────────────────────

def _invite_stanza(xml):
    from slixmpp import Message
    from slixmpp.xmlstream import ET
    return Message(xml=ET.fromstring(xml))


def test_muc_invite_direct_xep0249_uses_room_jid():
    bot = _bot_stub()
    inv = _invite_stanza(
        "<message xmlns='jabber:client' from='davetci@example.com/kaynak'>"
        "<x xmlns='jabber:x:conference' jid='oda@conf.example.com' reason='gel'/>"
        "</message>")
    xmpp.XMPPBot._on_muc_invite(bot, inv)
    kind, data = bot.gui_q.items[0]
    assert kind == "muc_invite"
    assert data["room"] == "oda@conf.example.com"
    assert data["reason"] == "gel"


def test_muc_invite_mediated_xep0045_uses_from_and_reason():
    # Bu uygulamanın kendi gönderdiği biçim: oda → davetli (from = oda)
    bot = _bot_stub()
    inv = _invite_stanza(
        "<message xmlns='jabber:client' from='oda@conf.example.com'>"
        "<x xmlns='http://jabber.org/protocol/muc#user'>"
        "<invite from='davetci@example.com/kaynak'><reason>katıl</reason></invite>"
        "</x></message>")
    xmpp.XMPPBot._on_muc_invite(bot, inv)
    _, data = bot.gui_q.items[0]
    assert data["room"] == "oda@conf.example.com"
    assert data["reason"] == "katıl"


# ── A6: _poll tek istisnada durmamalı ───────────────────────────────────────

def test_poll_reschedules_after_handler_exception():
    win = object.__new__(xmpp.MainWindow)

    class _Q:
        def __init__(self):
            self.items = [("boom", None)]

        def get_nowait(self):
            if self.items:
                return self.items.pop(0)
            raise xmpp.queue.Empty

    win.gui_q = _Q()

    def _boom(kind, data):
        raise RuntimeError("işleyici çöktü")

    win._handle = _boom
    scheduled = []
    win.root = type("R", (), {
        "after": lambda self, ms, cb: scheduled.append(ms)})()
    xmpp.MainWindow._poll(win)
    assert scheduled == [100]


# ── A7: retract geçmişe ve DB'ye yansımalı ──────────────────────────────────

def test_msg_retract_updates_history_and_db(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.active = "ali@example.com"
    win.chats = {"ali@example.com": [
        ("Ali", "merhaba", False, "12:00", "them", "", False, "mid1")]}
    win._bubble_widgets = []
    win._update_bubble_text = lambda *a, **k: None
    db_calls = []
    monkeypatch.setattr(xmpp, "_db_update_msg_body",
                        lambda jid, mid, body: db_calls.append((jid, mid, body)),
                        raising=False)
    xmpp.MainWindow._handle(win, "msg_retract",
                            {"from": "ali@example.com", "retracted_id": "mid1"})
    assert win.chats["ali@example.com"][0][1] == "🚫 Bu mesaj silindi"
    # [2J.a] kalıcı mutasyon (jid, mid) kapsamlı
    assert db_calls == [("ali@example.com", "mid1", "🚫 Bu mesaj silindi")]


def test_store_keeps_mid(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "m.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    try:
        win = object.__new__(xmpp.MainWindow)
        win.chats = {}
        xmpp.MainWindow._store(win, "a@b.c", "merhaba", tag="them",
                               sender="Ali", mid="m1")
        assert win.chats["a@b.c"][0][7] == "m1"
        rows = xmpp._db_load_msgs("a@b.c")
        assert rows and rows[0][5] == ""
    finally:
        if xmpp._db_conn is not None:
            xmpp._db_conn.close()
        monkeypatch.setattr(xmpp, "_db_conn", None)


# ── A8: Geçmişi Sil DB'yi de temizlemeli ────────────────────────────────────

def test_clear_active_history_clears_db(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.active = "a@b.c"
    win.chats = {"a@b.c": [("A", "x", False, "1", "them", "", False)]}
    cleared = []
    monkeypatch.setattr(xmpp, "_db_clear_chat",
                        lambda jid: cleared.append(jid))
    win._load_chat = lambda t: None
    assert xmpp.MainWindow._clear_active_history(win) is True
    assert win.chats == {}
    assert cleared == ["a@b.c"]


def test_clear_all_history_clears_db(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.active = "a@b.c"
    win.chats = {"a@b.c": [("A", "x", False, "1", "them", "", False)],
                 "d@e.f": [("B", "y", False, "1", "them", "", False)]}
    cleared = []
    monkeypatch.setattr(xmpp, "_db_clear_all", lambda: cleared.append("all"))
    win._load_chat = lambda t: None
    assert xmpp.MainWindow._clear_all_history(win) is True
    assert win.chats == {}
    assert cleared == ["all"]


# ── A9: nick değişiminde my_nicks güncellenmeli ─────────────────────────────

def test_change_nick_updates_my_nicks(monkeypatch):
    bot = _bot_stub()
    bot.my_nicks = {"oda@conf": "eski"}
    bot.loop = object()
    muc_calls = []

    class _Muc:
        async def set_self_nick(self, room, nick):
            muc_calls.append((room, nick))

    # [2Q] eski __getitem__ yaması yerine gerçek manager kaydı
    monkeypatch.setitem(bot.plugin._plugins, "xep_0045", _Muc())
    submitted = []
    monkeypatch.setattr(xmpp.asyncio, "run_coroutine_threadsafe",
                        lambda coro, loop: submitted.append(coro))
    xmpp.XMPPBot.change_nick(bot, "oda@conf", "yeni")
    assert len(submitted) == 1
    asyncio.run(submitted[0])
    assert bot.my_nicks["oda@conf"] == "yeni"
    assert muc_calls and str(muc_calls[0][0]) == "oda@conf"


# ── A11: yanıt fallback gövdesi ─────────────────────────────────────────────

def _reply_stanza(monkeypatch, bot):
    made = []

    class _Msg:
        def __init__(self):
            self.xml = xmpp.ET.Element("message")

        def send(self):
            made[-1].sent = True

    def _make(**kw):
        made.append(_Msg())
        return made[-1]

    bot.make_message = _make
    submitted = []
    monkeypatch.setattr(xmpp.asyncio, "run_coroutine_threadsafe",
                        lambda coro, loop: submitted.append(coro))
    return made, submitted


def test_send_reply_plaintext_includes_quote(monkeypatch):
    bot = _bot_stub()
    bot.loop = object()
    made, submitted = _reply_stanza(monkeypatch, bot)
    xmpp.XMPPBot.send_reply(bot, "ali@example.com", "cevap", "m1",
                            "orijinal metin", "chat", "none")
    asyncio.run(submitted[0])
    xml = made[0].xml
    reply = xml.find("{urn:xmpp:reply:0}reply")
    fallback = xml.find("{urn:xmpp:fallback:0}fallback")
    assert reply is not None and reply.get("id") == "m1"
    assert fallback is not None
    qbody = fallback.find("body")
    assert qbody is not None and qbody.text == "orijinal metin"


def test_send_reply_omemo_passes_quote(monkeypatch):
    bot = _bot_stub()
    bot.omemo_ready = True
    calls = []

    async def _fake_omemo(to, body, mtype, reply_id=None, reply_body=None,
                          mid=None, reply_to_jid=None):
        calls.append((to, body, mtype, reply_id, reply_body))

    bot._send_omemo = _fake_omemo
    monkeypatch.setattr(xmpp, "HAS_OMEMO", True)
    asyncio.run(xmpp.XMPPBot._send_reply(
        bot, "ali@example.com", "cevap", "m1", "orijinal", "chat", "omemo"))
    assert calls == [("ali@example.com", "cevap", "chat", "m1", "orijinal")]


# ── A12: tepki geri çekme ───────────────────────────────────────────────────

def test_on_reactions_empty_is_forwarded():
    from slixmpp import JID

    class _Rx:
        def __getitem__(self, key):
            return "m1" if key == "id" else ""

        def get_values(self, all_chars=True):
            return []

    class _Msg:
        def __getitem__(self, key):
            if key == "reactions":
                return _Rx()
            if key == "from":
                return JID("ali@example.com/kaynak")
            raise KeyError(key)

    bot = _bot_stub()
    xmpp.XMPPBot._on_reactions(bot, _Msg())
    assert bot.gui_q.items == [
        ("msg_reactions", {"from": "ali@example.com", "nick": "kaynak",
                           "target_id": "m1", "emojis": []})]


def test_handle_reactions_removal():
    win = object.__new__(xmpp.MainWindow)
    win.active = None
    win._reactions = {("oda@conf", "m1"): {"👍": ["Ali", "Veli"], "❤": ["Ali"]}}
    win._bubble_widgets = []
    win._render_reactions = lambda *a, **k: None
    xmpp.MainWindow._handle(win, "msg_reactions", {
        "from": "oda@conf", "nick": "Ali", "target_id": "m1", "emojis": []})
    # [2M] (jid, mid) kapsamlı
    assert win._reactions[("oda@conf", "m1")] == {"👍": ["Veli"]}


# ── A14: geçici dosya temizliği ─────────────────────────────────────────────

def test_cleanup_temp_files(tmp_path):
    a = tmp_path / "a.wav"
    b = tmp_path / "b.jpg"
    a.write_text("x")
    b.write_text("y")
    xmpp._cleanup_temp_files([str(a), str(b), str(tmp_path / "yok.bin")])
    assert not a.exists() and not b.exists()


def test_remember_temp_file():
    win = object.__new__(xmpp.MainWindow)
    win._temp_files = []
    xmpp.MainWindow._remember_temp(win, "/tmp/x.wav")
    xmpp.MainWindow._remember_temp(win, "/tmp/x.wav")
    assert win._temp_files == ["/tmp/x.wav"]


# ── A15: sınırsız büyüyen depolara sınır ────────────────────────────────────

def test_remember_mid_caps_list():
    win = object.__new__(xmpp.MainWindow)
    win._msg_ids = {}
    for i in range(600):
        xmpp.MainWindow._remember_mid(win, "a@b.c", f"m{i}")
    assert len(win._msg_ids["a@b.c"]) == 500
    assert win._msg_ids["a@b.c"][-1] == "m599"


def test_reactions_store_caps_size():
    win = object.__new__(xmpp.MainWindow)
    win.active = None
    win._reactions = {}
    win._bubble_widgets = []
    win._render_reactions = lambda *a, **k: None
    for i in range(600):
        xmpp.MainWindow._handle(win, "msg_reactions", {
            "from": "x@y", "nick": "N", "target_id": f"m{i}",
            "emojis": ["👍"]})
    assert len(win._reactions) <= 500


def test_prune_photo_refs():
    win = object.__new__(xmpp.MainWindow)
    win._photo_refs = list(range(1000))
    xmpp.MainWindow._prune_photo_refs(win)
    assert len(win._photo_refs) == 400
    assert win._photo_refs[-1] == 999


# ── A16: balon metni güncellemesi doğru Label'ı hedeflemeli ─────────────────

def test_update_bubble_text_uses_body_label():
    class _Lbl:
        def __init__(self):
            self.kw = {}

        def winfo_exists(self):
            return True

        def config(self, **kw):
            self.kw.update(kw)

    win = object.__new__(xmpp.MainWindow)
    row = type("Row", (), {})()
    lbl = _Lbl()
    row._body_label = lbl
    xmpp.MainWindow._update_bubble_text(win, row, "yeni metin", edited=True)
    assert lbl.kw.get("text") == "yeni metin  ✏"


def test_update_bubble_text_retracted_style():
    class _Lbl:
        def __init__(self):
            self.kw = {}

        def winfo_exists(self):
            return True

        def config(self, **kw):
            self.kw.update(kw)

    win = object.__new__(xmpp.MainWindow)
    row = type("Row", (), {})()
    lbl = _Lbl()
    row._body_label = lbl
    xmpp.MainWindow._update_bubble_text(win, row, "silindi", retracted=True)
    assert lbl.kw.get("fg") == xmpp.FG_DIM
    assert "italic" in str(lbl.kw.get("font"))


# ── A17: tema listesi ve canlı yenileme eşlemesi ────────────────────────────

def test_theme_choices_lists_all_themes():
    assert len(xmpp._theme_choices()) == 10
    assert set(xmpp._theme_choices()) == set(xmpp._THEMES.keys())


def test_apply_color_theme_builds_remap():
    xmpp._apply_color_theme("koyu")
    xmpp._apply_color_theme("dracula")
    assert xmpp._COLOR_REMAP.get("#06060c") == "#282a36"
    xmpp._apply_color_theme("koyu")  # diğer testleri etkilememesi için geri al


# ── A18: otomatik tema zinciri yönetimi ─────────────────────────────────────

def test_auto_theme_chain_keeps_running_when_disabled(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    after_calls = []
    cancel_calls = []

    class _Root:
        def after(self, ms, cb):
            after_calls.append(ms)
            return f"id{len(after_calls)}"

        def after_cancel(self, i):
            cancel_calls.append(i)

    win.root = _Root()
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"auto_theme": False})
    xmpp.MainWindow._auto_theme_check(win)
    assert after_calls == [600000]
    xmpp.MainWindow._auto_theme_check(win)
    assert after_calls == [600000, 600000]
    assert cancel_calls == ["id1"]


# ── A19: kişi ekleme/kaldırma ───────────────────────────────────────────────

def test_add_contact_no_double_subscribe():
    bot = _bot_stub()
    calls = []

    class _Roster:
        def subscribe(self, jid):
            calls.append(("roster.subscribe", jid))

    bot.client_roster = _Roster()
    bot.send_presence_subscription = lambda **kw: calls.append(("presence", kw))
    asyncio.run(xmpp.XMPPBot._add_contact(bot, "ali@example.com"))
    assert calls == [("roster.subscribe", "ali@example.com")]


def test_remove_contact_uses_roster_remove():
    bot = _bot_stub()
    calls = []

    class _Roster:
        def remove(self, jid):
            calls.append(jid)

    bot.client_roster = _Roster()
    asyncio.run(xmpp.XMPPBot._remove_contact(bot, "ali@example.com"))
    assert calls == ["ali@example.com"]
    assert ("contact_removed", "ali@example.com") in bot.gui_q.items


# ── A21: callback tutarlılıkları ────────────────────────────────────────────

def test_get_blocked_list_passes_callback(monkeypatch):
    bot = _bot_stub()

    class _Xep:
        async def get_blocked(self):
            return {"blocklist": {"items": ["a@b.c"]}}

    # [2Q] eski __getitem__ yaması yerine gerçek manager kaydı
    monkeypatch.setitem(bot.plugin._plugins, "xep_0191", _Xep())
    cb = lambda items: None  # noqa: E731
    asyncio.run(xmpp.XMPPBot._get_blocked_list(bot, cb))
    kind, data = bot.gui_q.items[0]
    assert kind == "blocked_list"
    assert data["items"] == ["a@b.c"]
    assert data["cb"] is cb


def test_handle_blocked_list_invokes_callback():
    win = object.__new__(xmpp.MainWindow)
    called = []
    xmpp.MainWindow._handle(win, "blocked_list",
                            {"items": ["x@y"], "cb": called.append})
    assert called == [["x@y"]]


def test_vcard_error_includes_callback(monkeypatch):
    bot = _bot_stub()

    class _Xep:
        async def get_vcard(self, jid, timeout=10):
            raise RuntimeError("yok")

    # [2Q] eski __getitem__ yaması yerine gerçek manager kaydı
    monkeypatch.setitem(bot.plugin._plugins, "xep_0054", _Xep())
    cb = lambda data: None  # noqa: E731
    asyncio.run(xmpp.XMPPBot._get_vcard(bot, "a@b.c", cb))
    kind, data = bot.gui_q.items[0]
    assert kind == "vcard"
    assert data["cb"] is cb
    assert data["info"] is None


def test_stop_location_reports(monkeypatch):
    bot = _bot_stub()

    class _Xep:
        async def stop(self):
            pass

    # [2Q] eski __getitem__ yaması yerine gerçek manager kaydı
    monkeypatch.setitem(bot.plugin._plugins, "xep_0080", _Xep())
    asyncio.run(xmpp.XMPPBot._stop_location(bot))
    assert any("konum" in str(m).lower() for _, m in bot.gui_q.items)


# ── A24: PIN doğrulama ──────────────────────────────────────────────────────

def test_verify_pin_roundtrip_and_legacy(monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: key)
    enc = xmpp._encode_pw("1234")
    assert xmpp._verify_pin(enc, "1234") is True
    assert xmpp._verify_pin(enc, "9999") is False
    assert xmpp._verify_pin("1234", "1234") is True   # eski düz metin kaydı
    assert xmpp._verify_pin("", "1234") is False


# ── A25: OOB URL None güvenliği ─────────────────────────────────────────────

def test_extract_oob_none_returns_empty():
    class _Msg:
        def __getitem__(self, key):
            return {"url": None}

    assert xmpp.XMPPBot._extract_oob(_Msg()) == ""


# ── A10: MUC düz mesajında sent_mid üretilmeli ──────────────────────────────

def test_send_gc_emits_sent_mid():
    bot = _bot_stub()
    sent = {}

    class _Msg:
        def __getitem__(self, key):
            return "mid-42" if key == "id" else None

        def send(self):
            sent["ok"] = True

    bot.make_message = lambda **kw: _Msg()
    asyncio.run(xmpp.XMPPBot._send_gc(bot, "oda@conf", "selam"))
    assert sent.get("ok") is True
    assert ("sent_mid", {"to": "oda@conf", "mid": "mid-42"}) in bot.gui_q.items


def test_muc_invite_prosody_mediated_with_legacy_conference_x():
    # Prosody aracılı davete jabber:x:conference da ekler (sebep metin olarak)
    bot = _bot_stub()
    inv = _invite_stanza(
        "<message xmlns='jabber:client' from='oda@conf.example.com'>"
        "<x xmlns='http://jabber.org/protocol/muc#user'>"
        "<invite from='oda@conf.example.com/ali'><reason>gel</reason></invite></x>"
        "<x xmlns='jabber:x:conference' jid='oda@conf.example.com'>gel</x>"
        "</message>")
    xmpp.XMPPBot._on_muc_invite(bot, inv)
    _, data = bot.gui_q.items[0]
    assert data == {"room": "oda@conf.example.com", "reason": "gel"}


def test_muc_invite_unrelated_message_ignored():
    bot = _bot_stub()
    xmpp.XMPPBot._on_muc_invite(bot, _invite_stanza(
        "<message xmlns='jabber:client' from='a@example.com'><body>x</body></message>"))
    assert bot.gui_q.items == []
