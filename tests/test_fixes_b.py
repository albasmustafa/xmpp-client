"""B fazı özellik tamamlama testleri (saf mantık katmanı)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import slixmpp  # noqa: E402

import xmpp  # noqa: E402


class _Q:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def _bot_stub():
    bot = object.__new__(xmpp.XMPPBot)
    bot.gui_q = _Q()
    bot._run_out_filters = None
    return bot


# ── B33: XEP-0055 arama formu alan eşlemesi ─────────────────────────────────

def test_fill_search_form_prefers_nick():
    fields = {
        "nick": {"type": "text-single", "value": ""},
        "first": {"type": "text-single", "value": ""},
        "hidden_x": {"type": "hidden", "value": "s"},
    }
    chosen = xmpp._fill_search_form(fields, "ahmet")
    assert chosen == "nick"
    assert fields["nick"]["value"] == "ahmet"
    assert fields["first"]["value"] == ""


def test_fill_search_form_skips_hidden_nick():
    fields = {
        "nick": {"type": "hidden", "value": ""},
        "last": {"type": "text-single", "value": ""},
    }
    assert xmpp._fill_search_form(fields, "yılmaz") == "last"
    assert fields["last"]["value"] == "yılmaz"


def test_fill_search_form_fallback_first_visible():
    fields = {"custom": {"type": "text-single", "value": ""},
              "h": {"type": "hidden", "value": ""}}
    assert xmpp._fill_search_form(fields, "x") == "custom"
    assert fields["custom"]["value"] == "x"


# ── B35: oda oluşturma — instant room ───────────────────────────────────────

def test_configure_instant_room():
    """Form alınamayan yeni oda anında oda (boş submit) ile açılır.

    Oda türü yapılandırması (test_room_kind.py) formu bulamazsa bu yola
    düşer; cancel_config yeni odayı yok eder (XEP-0045 §10.1.3)."""
    bot = _bot_stub()
    calls = []

    class _Muc:
        async def get_room_config(self, room):
            raise RuntimeError("feature-not-implemented")

        async def cancel_config(self, room):
            raise AssertionError("cancel_config odayı yok eder")

        async def set_room_config(self, room, form):
            calls.append((str(room), len(form["fields"])))

    asyncio.run(xmpp.XMPPBot._setup_new_room(
        bot, _Muc(), "oda@conf.example.com", "normal"))
    assert calls == [("oda@conf.example.com", 0)]


# ── B37: yer imi ekleme — tekilleştirme ─────────────────────────────────────

def test_bookmark_add_dedupes():
    bookmarks = [{"jid": "a@conf", "name": "A", "nick": "ali",
                  "autojoin": False}]
    xmpp._bookmark_add(bookmarks, "a@conf", name="Yeni", nick="ahmet",
                       autojoin=True)
    assert len(bookmarks) == 1
    assert bookmarks[0]["name"] == "Yeni"
    assert bookmarks[0]["nick"] == "ahmet"
    assert bookmarks[0]["autojoin"] is True


def test_bookmark_add_appends_new():
    bookmarks = []
    bm = xmpp._bookmark_add(bookmarks, "b@conf", nick="veli")
    assert bm in bookmarks
    assert bm["name"] == "b"
    assert bm["autojoin"] is True


def test_get_bookmarks_with_callback_emits_update_not_dialog():
    """Callback verilince 'bookmarks' diyaloğu değil, 'bookmarks_update' yayılır."""
    bot = _bot_stub()

    class _BM:
        async def get_bookmarks(self):
            return {"private": {"bookmarks": {"conferences": [
                {"jid": "a@conf", "name": "A", "nick": "ali",
                 "autojoin": True}]}}}

    bot.plugin = {"xep_0048": _BM()}
    seen = []
    asyncio.run(bot._get_bookmarks(seen.append))

    kinds = [k for k, _ in bot.gui_q.items]
    assert kinds == ["bookmarks_update"]
    data = bot.gui_q.items[0][1]
    assert data["bookmarks"][0]["jid"] == "a@conf"
    assert data["cb"].__self__ is seen


def _connected_stub(monkeypatch, last_chat):
    win = object.__new__(xmpp.MainWindow)
    calls = []
    win._conn_timeout_id = None
    win._contacts = {}
    win._refresh_contacts = lambda: None
    win._append = lambda *a, **k: None
    win._load_pgp_keymap = lambda: None
    win._rejoin_saved_rooms = lambda: None
    win._fetch_avatars = lambda: None
    win._load_chat = lambda t: calls.append(t)
    monkeypatch.setattr(xmpp, "_load_config",
                        lambda: {"last_chat": last_chat})
    return win, calls


def test_connected_restores_last_chat(monkeypatch):
    """Bağlanınca kayıtlı son 1:1 sohbet geri açılmalı."""
    win, calls = _connected_stub(monkeypatch, "ali@example.com")
    xmpp.MainWindow._handle(win, "connected",
                            {"ali@example.com": {"name": "Ali"}})
    assert calls == ["ali@example.com"]


def test_connected_ignores_unknown_last_chat(monkeypatch):
    """Kişi listesinde olmayan son sohbet açılmamalı."""
    win, calls = _connected_stub(monkeypatch, "yok@example.com")
    xmpp.MainWindow._handle(win, "connected",
                            {"ali@example.com": {"name": "Ali"}})
    assert calls == []


def test_after_tracks_and_skips_when_closing():
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    scheduled = []

    class _Root:
        def after(self, ms, cb):
            scheduled.append(ms)
            return f"id{len(scheduled)}"

    win.root = _Root()
    aid = xmpp.MainWindow._after(win, 100, lambda: None)
    assert aid == "id1"
    assert win._after_ids == {"id1"}
    # Kapanışta yeni zincir kurulmaz
    win._closing = True
    assert xmpp.MainWindow._after(win, 100, lambda: None) is None
    assert len(scheduled) == 1


def test_after_runs_and_unregisters():
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    callbacks = []

    class _Root:
        def after(self, ms, cb):
            callbacks.append(cb)
            return "id1"

    win.root = _Root()
    ran = []
    xmpp.MainWindow._after(win, 50, lambda: ran.append(1))
    callbacks[0]()
    assert ran == [1]
    assert win._after_ids == set()


def test_quit_cancels_all_afters_and_is_idempotent(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    win._tray_icon = None
    win._temp_files = []
    win.active = None
    win._after_ids = set()
    for attr in ("_poll_id", "_idle_check_id", "_ping_loop_id",
                 "_conn_timeout_id", "_auto_theme_id",
                 "_typing_anim_id", "_typing_send_id"):
        setattr(win, attr, None)
    win._poll_id = "poll1"
    calls = {"cancel": [], "destroy": 0, "setvar": []}

    class _Tk:
        def setvar(self, k, v):
            calls["setvar"].append((k, v))

        def splitlist(self, s):
            return s

        def call(self, *a):
            if a[:2] == ("after", "info"):
                return ("a1", "a2")
            if a[:2] == ("after", "cancel"):
                calls["cancel"].append(a[2])
            return ""

    class _Root:
        tk = _Tk()

        def after_cancel(self, i):
            calls["cancel"].append(i)

        def winfo_geometry(self):
            return "800x600+0+0"

        def state(self):
            return "normal"

        def destroy(self):
            calls["destroy"] += 1

    win.root = _Root()
    win.bot = None
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: None)
    monkeypatch.setattr(xmpp, "_cleanup_temp_files", lambda files: None)

    xmpp.MainWindow._quit(win)
    assert win._closing is True
    assert ("xmpp_closing", 1) in calls["setvar"]
    assert "poll1" in calls["cancel"]
    assert "a1" in calls["cancel"] and "a2" in calls["cancel"]
    assert calls["destroy"] == 1
    xmpp.MainWindow._quit(win)  # ikinci çağrı no-op
    assert calls["destroy"] == 1


def test_conn_timeout_offers_retry(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.root = None
    win._last_conn_error = "[Errno 111] Connection refused"
    win.bot = object.__new__(xmpp.XMPPBot)
    win.bot._connected_ok = False
    win.bot._run_out_filters = None
    cancelled = []
    win.bot.cancel_connection_attempt = lambda: cancelled.append(1)
    quit_calls = []
    win._quit = lambda: quit_calls.append(1)

    # "Evet" → denemeye devam, çıkış yok
    monkeypatch.setattr(xmpp.messagebox, "askyesno", lambda *a, **k: True)
    xmpp.MainWindow._conn_timeout(win)
    assert quit_calls == [] and cancelled == []

    # "Hayır" → bağlantı iptal + giriş ekranı
    monkeypatch.setattr(xmpp.messagebox, "askyesno", lambda *a, **k: False)
    xmpp.MainWindow._conn_timeout(win)
    assert quit_calls == [1] and cancelled == [1]
    assert win._relogin is True


def test_conn_failed_updates_state_and_throttles_toast():
    win = object.__new__(xmpp.MainWindow)
    appends = []
    toasts = []
    win._append = lambda body, tag="them", **k: appends.append((body, tag))
    win._show_toast = lambda title, msg, **k: toasts.append((title, msg))
    win._status_label = type("L", (), {
        "config": lambda self, **k: None})()
    win._last_conn_error = ""
    win._last_conn_toast_ts = 0.0
    data = {"error": "[Errno 111] Connection refused",
            "domain": "anche.no", "port": 5222, "address": ""}

    xmpp.MainWindow._handle(win, "conn_failed", data)
    assert win._last_conn_error == "[Errno 111] Connection refused"
    assert any("Connection refused" in b for b, _ in appends)
    assert len(toasts) == 1

    # Aynı hata 30 sn içinde tekrar toast üretmez
    xmpp.MainWindow._handle(win, "conn_failed", data)
    assert len(toasts) == 1


def test_on_conn_fail_emits_rich_event():
    bot = _bot_stub()
    bot.default_domain = "anche.no"
    bot.default_port = 5222
    bot.custom_address = None
    xmpp.XMPPBot._on_conn_fail(
        bot, OSError("[Errno 111] Connection refused"))
    kind, data = bot.gui_q.items[-1]
    assert kind == "conn_failed"
    assert data["domain"] == "anche.no" and data["port"] == 5222
    assert "Connection refused" in data["error"]


def test_get_dns_records_prefers_ipv4_when_no_ipv6(monkeypatch):
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None

    async def fake_records(self, domain, port=None):
        return [("xmpp-client", "h", "2001:db8::1", 5222),
                ("xmpp-client", "h", "1.1.1.1", 5222)]

    monkeypatch.setattr(slixmpp.xmlstream.xmlstream.XMLStream,
                        "get_dns_records", fake_records)
    monkeypatch.setattr(xmpp, "_ipv6_available", lambda: False)
    out = asyncio.run(xmpp.XMPPBot.get_dns_records(bot, "anche.no"))
    assert [r[2] for r in out] == ["1.1.1.1"]


def test_retry_connection_schedules_on_loop():
    win = object.__new__(xmpp.MainWindow)
    calls = []

    class _Loop:
        def call_soon_threadsafe(self, fn):
            calls.append(fn)

    class _Bot:
        _connected_ok = False
        loop = _Loop()

        def connect(self):
            calls.append("connect")

        def cancel_connection_attempt(self):
            calls.append("cancel")

    win.bot = _Bot()
    win.root = None
    win._last_conn_error = "eski hata"
    win._append = lambda body, tag="them", **k: None
    win._status_label = type("L", (), {
        "config": lambda self, **k: None})()

    xmpp.MainWindow._retry_connection(win)
    assert win._last_conn_error == ""
    # P1-1: cancel_connection_attempt da loop'a planlanmalı (doğrudan değil)
    assert len(calls) == 2 and all(callable(c) for c in calls)
    calls[0]()  # loop thread'inde cancel çalışmalı
    assert "cancel" in calls
    calls[1]()  # loop thread'inde connect çalışmalı
    assert "connect" in calls


def test_auth_failed_uses_quit(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.root = None
    win._conn_timeout_id = None
    win._relogin = False
    quit_calls = []
    win._quit = lambda: quit_calls.append(1)
    monkeypatch.setattr(xmpp.messagebox, "showerror", lambda *a, **k: None)
    xmpp.MainWindow._handle(win, "auth_failed", "şifre yanlış")
    assert quit_calls == [1]
    assert win._relogin is True


# ── B38: kişi grupları kaydı ────────────────────────────────────────────────

def test_save_contact_groups_writes_config(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    saved = {}
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"x": 1})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: saved.update(cfg))
    xmpp.MainWindow._save_contact_groups(win, {"İş": ["a@b.c"]})
    assert saved["contact_groups"] == {"İş": ["a@b.c"]}
    assert saved["x"] == 1


# ── B28: Tenor GIF sonuç ayrıştırma ─────────────────────────────────────────

def test_parse_tenor_results():
    payload = {"results": [
        {"media_formats": {"tinygif": {"url": "https://t/1.gif"},
                           "gif": {"url": "https://t/1full.gif"}}},
        {"media_formats": {}},
        {"media_formats": {"gif": {"url": "https://t/2full.gif"}}},
    ]}
    out = xmpp._parse_tenor_results(payload)
    assert out[0]["preview"] == "https://t/1.gif"
    assert out[0]["url"] == "https://t/1full.gif"
    assert out[1]["url"] == "https://t/2full.gif"
    assert len(out) == 2


# ── B31: hesap parolası çözme ───────────────────────────────────────────────

def test_account_password_decodes_encoded(monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: key)
    enc = xmpp._encode_pw("gizli")
    assert xmpp._account_password({"password": enc}) == "gizli"


def test_account_password_keeps_legacy_plain():
    assert xmpp._account_password({"password": "duzparola"}) == "duzparola"
    assert xmpp._account_password({}) == ""


def test_switch_account_writes_config(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    saved = {}
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"theme": "koyu"})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: saved.update(cfg))
    monkeypatch.setattr(xmpp, "_encode_pw", lambda pw: f"enc:{pw}")
    after_calls = []
    win.root = type("R", (), {
        "after": lambda self, ms, cb: after_calls.append((ms, cb))})()
    win._show_toast = lambda *a, **k: None
    xmpp.MainWindow._switch_account(
        win, {"jid": "yeni@example.com", "password": "pw"})
    assert saved["jid"] == "yeni@example.com"
    assert saved["pw"] == "enc:pw"
    assert saved["remember"] is True
    assert after_calls and after_calls[0][0] == 800


# ── B32: MAM sayfalama + şifreli arşiv ──────────────────────────────────────

def test_stanza_is_encrypted_omemo():
    el = xmpp.ET.fromstring(
        "<message xmlns='jabber:client'>"
        "<encrypted xmlns='eu.siacs.conversations.axolotl'/></message>")
    assert xmpp._stanza_is_encrypted(el) is True


def test_stanza_is_encrypted_pgp():
    el = xmpp.ET.fromstring(
        "<message xmlns='jabber:client'>"
        "<x xmlns='jabber:x:encrypted'>hmm</x></message>")
    assert xmpp._stanza_is_encrypted(el) is True


def test_stanza_is_encrypted_plain():
    el = xmpp.ET.fromstring(
        "<message xmlns='jabber:client'><body>selam</body></message>")
    assert xmpp._stanza_is_encrypted(el) is False


def test_fetch_mam_pagination_and_placeholder(monkeypatch):
    bot = _bot_stub()
    from slixmpp import JID
    bot.boundjid = JID("ben@example.com/kaynak")
    captured = {}

    class _Mam:
        async def retrieve(self, **kw):
            captured.update(kw)
            return {"mam": {"results": [
                {"mam_result": {"forwarded": {
                    "stanza": _FakeStanza(
                        body="", frm="ali@example.com",
                        xml=xmpp.ET.fromstring(
                            "<message xmlns='jabber:client'>"
                            "<encrypted xmlns='eu.siacs.conversations.axolotl'/>"
                            "</message>")),
                    "delay": {"stamp": "2026-01-01T10:00:00Z"}}}}]}}

    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: _Mam() if name == "xep_0313" else None)
    asyncio.run(xmpp.XMPPBot._fetch_mam(bot, "ali@example.com",
                                        before="mid-42"))
    assert captured["rsm"] == {"max": 50, "before": "mid-42"}
    _, data = bot.gui_q.items[0]
    assert data["messages"][0]["body"] == "🔒 Şifreli mesaj (arşivde çözülemedi)"


class _FakeStanza:
    def __init__(self, body="", frm="", xml=None):
        self._body = body
        self._from = frm
        self.xml = xml if xml is not None else xmpp.ET.Element("message")

    def get(self, key, default=""):
        return self._body if key == "body" else default

    def __getitem__(self, key):
        if key == "from":
            from slixmpp import JID
            return JID(self._from)
        raise KeyError(key)


# ── Crash: sidebar arama kutusu hazır olmadan _filter_sidebar ───────────────

def test_filter_sidebar_without_search_widget_does_not_crash():
    """PlaceholderEntry kurulurken trace tetiklenirse çökmemeli."""
    win = object.__new__(xmpp.MainWindow)

    class _Var:
        def get(self):
            return ""

    class _List:
        def curselection(self):
            return ()

        def delete(self, *a):
            pass

        def insert(self, *a):
            pass

        def itemconfig(self, *a, **k):
            pass

    win._sidebar_search_var = _Var()
    win._contacts = {}
    win._contact_jids = []
    win._pinned_chats = []
    win.presence = {}
    win.rooms = []
    win._room_jids = []
    win.contact_list = _List()
    win.room_list = _List()
    xmpp.MainWindow._filter_sidebar(win)  # istisna fırlatmamalı


def test_sidebar_trace_registered_after_widget():
    """trace_add, PlaceholderEntry atandıktan SONRA çağrılmalı (kaynak kontrolü)."""
    import inspect
    src = inspect.getsource(xmpp.MainWindow._build_sidebar)
    assign = src.index("self._sidebar_search = PlaceholderEntry")
    trace = src.index('self._sidebar_search_var.trace_add')
    assert trace > assign, "trace, widget atamasından önce kaydediliyor"


# ── Deprecation: plugin erişimi (self.plugin yeni API) ──────────────────────

def test_get_xep_prefers_plugin_manager():
    class _O:
        plugin = {"xep_0045": "muc-plugin"}

        def __getitem__(self, name):
            raise AssertionError("eski API kullanılmamalı")

    assert xmpp._get_xep(_O(), "xep_0045") == "muc-plugin"


def test_get_xep_falls_back_to_getitem():
    calls = []

    class _O:
        def __getitem__(self, name):
            calls.append(name)
            return f"eski:{name}"

    assert xmpp._get_xep(_O(), "xep_0027") == "eski:xep_0027"
    assert calls == ["xep_0027"]


# ── B39: avatar başarısızlığında geri alma ──────────────────────────────────

def test_restore_avatar_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_AVATAR_DIR", str(tmp_path))
    win = object.__new__(xmpp.MainWindow)
    win.avatars_updates = []
    win._avatars = {}
    win._update_sidebar_avatar = lambda: win.avatars_updates.append(True)

    # Eski veri varsa geri yazılır
    win._avatars["a@b.c"] = b"yeni"
    xmpp.MainWindow._restore_avatar(win, "a@b.c", b"eski")
    assert win._avatars["a@b.c"] == b"eski"
    assert xmpp._load_avatar_cache("a@b.c") == b"eski"

    # Eski veri yoksa önbellek temizlenir
    win._avatars["a@b.c"] = b"yeni"
    xmpp._save_avatar_cache("a@b.c", b"yeni")
    xmpp.MainWindow._restore_avatar(win, "a@b.c", None)
    assert "a@b.c" not in win._avatars
    assert xmpp._load_avatar_cache("a@b.c") is None
    assert win.avatars_updates == [True, True]
