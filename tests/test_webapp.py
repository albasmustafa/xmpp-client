"""Web köprüsü ve sunucu (webapp/) sözleşmeleri — ağ ve Tk YOK.

Kanıtlar:
- Olay izdüşümü: msg/own_msg/typing/presence/düzeltme/geri çekme/tepki/
  muc_presence olayları oturum durumuna ve çıkış olaylarına doğru dönüşür;
  aktif sohbette okundu bildirimi (displayed marker) gönderilir.
- Giden komutlar: send (hassas veri uyarısı → force ile gönderim), reply,
  react, correct, retract, join_room (config'e kayıt) bot'a iletilir.
- REST: login doğrulaması, history sayfalama (before_id), ayarlar GET/POST
  (claude_api_key dışarı sızmaz).
"""
import asyncio
import os
import queue
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402  (facade: _DB_PATH, _db_conn)
from webapp import bridge as wb  # noqa: E402
from webapp import server as srv  # noqa: E402


class FakeLoop:
    def call_soon_threadsafe(self, fn, *a):
        fn(*a)


class FakeBot:
    def __init__(self):
        self.calls = []
        self.my_nicks = {}
        self.muc_service = "chat.example.com"

    def __getattr__(self, name):
        if name.startswith("send_") or name in ("retract_message",
                                                "join_room", "leave_room",
                                                "discover_rooms",
                                                "set_presence",
                                                "approve_subscribe",
                                                "fetch_mam"):
            def _rec(*a, **kw):
                self.calls.append((name, a, kw))
            return _rec
        raise AttributeError(name)


CFG: dict = {}


@pytest.fixture()
def session(monkeypatch, tmp_path):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "web.db"))
    xmpp._db_conn = None
    CFG.clear()
    monkeypatch.setattr(wb, "_load_config", lambda: CFG)
    monkeypatch.setattr(wb, "_save_config", lambda c: None)

    s = object.__new__(wb.WebSession)
    s._app = xmpp
    s.jid, s.password = "ben@example.com", "pw"
    s.server, s.port = "", 5222
    s.gui_q = queue.Queue()
    s.bot = FakeBot()
    s._closing = False
    s._auth_failed = False
    s.sinks = []
    s._sinks_lock = threading.Lock()
    s.contacts = {}
    s.presence = {}
    s.unread = {}
    s.rooms = set()
    s.members = {}
    s.subjects = {}
    s.enc_modes = {}
    s.typing = {}
    s.chats = {}
    s.bookmarks = []
    s.rooms_found = []
    s.active = ""
    s._mam_gen = {}
    s._mam_intent = {}
    s._mam_oldest = {}
    s._mam_has_more = {}
    s._send_read_receipts = True
    s._send_typing = True
    s._leak_guard = True
    s._reactions_cache = {}
    s.sink = queue.Queue()
    s.add_sink(FakeLoop(), s.sink)
    yield s
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
        xmpp._db_conn = None


# ── Olay izdüşümü ───────────────────────────────────────────────────────────
def test_connected_builds_roster_and_rejoins_rooms(session, monkeypatch):
    CFG["rooms"] = {"oda@chat.x": {"nick": "ben"}}
    session._apply("connected", {"ali@x.im": "Ali"})
    assert session.contacts == {"ali@x.im": "Ali"}
    assert ("join_room", ("oda@chat.x", "ben"), {}) in session.bot.calls
    ev = session.sink.get_nowait()
    assert ev == {"ev": "connected",
                  "data": {"roster": {"ali@x.im": "Ali"},
                           "jid": "ben@example.com"}}


def test_msg_stores_unreads_and_marks_displayed_when_active(session):
    session._apply("connected", {"ali@x.im": "Ali"})
    session.sink.get_nowait()
    data = {"from": "ali@x.im", "nick": "ali", "body": "selam",
            "type": "chat", "oob": "", "encrypted": False, "mid": "m1",
            "reply": None}
    session._apply("msg", data)
    assert session.unread["ali@x.im"] == 1
    ev = session.sink.get_nowait()
    assert ev["ev"] == "msg" and ev["data"]["is_unread"] is True
    assert ("send_marker",) != ()  # bot çağrısı beklenmez
    assert all(name != "send_marker" for name, _a, _k in session.bot.calls)

    session.command("open_chat", {"jid": "ali@x.im"})
    data2 = {**data, "mid": "m2", "body": "nasılsın"}
    session._apply("msg", data2)
    assert ("send_marker", ("ali@x.im", "m2", "displayed"), {}) \
        in session.bot.calls
    assert session.unread.get("ali@x.im", 0) == 0


def test_correction_and_retract_update_db(session):
    from xmppcore import storage as st
    from xmppcore.ai import RETRACTED_BODY
    session._apply("connected", {"ali@x.im": "Ali"})
    session.sink.get_nowait()
    session._apply("msg", {"from": "ali@x.im", "nick": "ali", "body": "eskı",
                           "mid": "m9", "encrypted": False})
    session._apply("msg_correction", {"from": "ali@x.im", "orig_id": "m9",
                                      "body": "yeni", "nick": "ali"})
    rows = st._db_load_msgs("ali@x.im")
    assert rows[-1][1] == "yeni"
    session._apply("msg_retract", {"from": "ali@x.im",
                                   "retracted_id": "m9"})
    rows = st._db_load_msgs("ali@x.im")
    assert rows[-1][1] == RETRACTED_BODY


def test_reactions_replaced_per_sender(session):
    from xmppcore import storage as st
    jid = "ali@x.im"
    session._apply("msg", {"from": jid, "nick": "ali", "body": "x",
                           "mid": "r1", "encrypted": False})
    session._apply("msg_reactions", {"from": jid, "nick": "ayse",
                                     "target_id": "r1",
                                     "emojis": ["👍", "🎉"]})
    assert st._db_load_reactions(jid)["r1"]["👍"] == ["ayse"]
    session._apply("msg_reactions", {"from": jid, "nick": "ayse",
                                     "target_id": "r1", "emojis": []})
    assert st._db_load_reactions(jid).get("r1", {}) == {}


def test_muc_events_track_members_and_rooms(session):
    session._apply("muc_presence", {"room": "oda@chat.x", "nick": "ali",
                                    "online": True, "role": "participant",
                                    "affil": "member", "show": ""})
    assert session.members["oda@chat.x"]["ali"]["role"] == "participant"
    session._apply("room_joined", "oda@chat.x")
    assert "oda@chat.x" in session.rooms
    assert CFG["rooms"]["oda@chat.x"]["nick"] == "ben"
    session._apply("muc_presence", {"room": "oda@chat.x", "nick": "ali",
                                    "online": False, "role": "",
                                    "affil": "", "show": ""})
    assert "ali" not in session.members["oda@chat.x"]
    session._apply("room_left", "oda@chat.x")
    assert "oda@chat.x" not in session.rooms
    assert "oda@chat.x" not in CFG.get("rooms", {})


# ── Giden komutlar ──────────────────────────────────────────────────────────
def test_send_plain_stores_and_broadcasts(session):
    res = session.command("send", {"to": "ali@x.im", "body": "merhaba"})
    assert res["ok"] is True and res["mid"]
    assert ("send_chat", ("ali@x.im", "merhaba"),
            {"encryption": "none", "mid": res["mid"]}) in session.bot.calls
    ev = session.sink.get_nowait()
    while ev["ev"] != "own_sent":
        ev = session.sink.get_nowait()
    assert ev["data"]["mid"] == res["mid"]
    from xmppcore import storage as st
    rows = st._db_load_msgs("ali@x.im")
    assert rows[-1][2] is True and rows[-1][1] == "merhaba"


def test_send_leak_guard_blocks_until_force(session):
    body = "IBAN: TR330006100519786457841326"
    res = session.command("send", {"to": "ali@x.im", "body": body})
    assert res.get("leak") is True and res["findings"]
    n_before = len(session.bot.calls)
    res2 = session.command("send", {"to": "ali@x.im", "body": body,
                                    "force": True})
    assert res2["ok"] is True
    assert len(session.bot.calls) == n_before + 2  # send_chat + chatstate


def test_send_reply_and_muc_routing(session):
    session._apply("room_joined", "oda@chat.x")
    session.sink.get_nowait()
    session.command("send", {"to": "oda@chat.x", "body": "selam oda"})
    assert ("send_gc",) == (session.bot.calls[-2][0],)
    assert ("send_chatstate", ("oda@chat.x", "active", "groupchat"), {}) \
        in session.bot.calls
    session.command("send", {"to": "ali@x.im", "body": "yanıt",
                             "reply_to": {"id": "m1", "sender": "Ali",
                                          "body": "önceki"}})
    reply_calls = [c for c in session.bot.calls if c[0] == "send_reply"]
    assert reply_calls and reply_calls[-1][1] == \
        ("ali@x.im", "yanıt", "m1", "önceki", "chat", "none")


def test_react_correct_retract_commands(session):
    from xmppcore import storage as st
    session._apply("msg", {"from": "ali@x.im", "nick": "ali", "body": "x",
                           "mid": "q1", "encrypted": False})
    res = session.command("react", {"to": "ali@x.im", "mid": "q1",
                                    "emojis": ["👍"]})
    assert res["ok"] is True
    assert ("send_reaction", ("ali@x.im", "q1", {"👍"}, "chat"), {}) \
        in session.bot.calls
    assert st._db_load_reactions("ali@x.im")["q1"]["👍"] == ["Ben"]

    res = session.command("correct", {"to": "ali@x.im", "mid": "q1",
                                      "body": "düzeltilmiş"})
    assert ("send_correction", ("ali@x.im", "düzeltilmiş", "q1", "chat"), {}) \
        in session.bot.calls
    assert st._db_load_msgs("ali@x.im")[-1][1] == "düzeltilmiş"

    res = session.command("retract", {"to": "ali@x.im", "mid": "q1"})
    assert res["ok"] is True
    assert ("retract_message", ("ali@x.im", "q1", "chat"), {}) \
        in session.bot.calls


def test_omemo_auto_enables_on_incoming(session):
    session._apply("msg", {"from": "ali@x.im", "nick": "ali", "body": "gizli",
                           "mid": "e1", "encrypted": "omemo"})
    assert session.enc_modes["ali@x.im"] == "omemo"
    session.command("set_enc", {"jid": "ali@x.im", "mode": "none"})
    assert session.enc_modes["ali@x.im"] == "none"


# ── MAM (oda/1:1 arşiv geçmişi) ─────────────────────────────────────────────
def test_open_chat_empty_history_triggers_mam(session):
    session._apply("connected", {"ali@x.im": "Ali"})
    session.sink.get_nowait()
    session.command("open_chat", {"jid": "ali@x.im"})
    calls = [c for c in session.bot.calls if c[0] == "fetch_mam"]
    assert calls and calls[0][1][0] == "ali@x.im"
    assert session._mam_intent["ali@x.im"]["intent"] == "initial"
    # İkinci open_chat: niyet beklemede → ikinci istek gitmez (E kuralı)
    session.command("open_chat", {"jid": "ali@x.im"})
    assert len([c for c in session.bot.calls
                if c[0] == "fetch_mam"]) == 1


def test_open_chat_with_history_skips_mam(session):
    from xmppcore import storage as st
    st._db_store_msg("ali@x.im", "ali", "eski", False, "10:00", "them")
    session.command("open_chat", {"jid": "ali@x.im"})
    assert not [c for c in session.bot.calls if c[0] == "fetch_mam"]


def test_mam_results_stored_broadcast_and_dedupe(session):
    from xmppcore import storage as st
    jid = "oda@chat.x"
    session.command("open_chat", {"jid": jid})
    token = session._mam_intent[jid]["token"]
    session._apply("mam_results", {
        "jid": jid, "token": token, "messages": [
            {"from": jid, "body": "eski 1", "is_me": False, "mid": "A1",
             "nick": "ayse", "ts": "2026-10-01T10:00:00Z",
             "archive_id": "arc-1"},
            {"from": jid, "body": "eski 2", "is_me": True, "mid": "A2",
             "nick": "ben", "ts": "2026-10-01T10:01:00Z",
             "archive_id": "arc-0"},
        ]})
    assert jid not in session._mam_intent          # niyet tüketildi
    assert session._mam_oldest[jid] == "arc-1"     # imleç ilk satırdan
    rows = st._db_load_msgs_full(jid)
    assert [r[2] for r in rows] == ["eski 1", "eski 2"]
    assert rows[0][4] == "13:00"                   # ISO damga yerel HH:MM
    assert rows[0][13] == "2026-10-01T13:00:00"    # stored_at gerçek tarih
    assert rows[1][3] is True and rows[1][1] == "Ben"
    # Bellek: prepend (kanonik sırada)
    assert session.chats[jid][0][7] == "A1"
    # Tarayıcıya haber
    evs = []
    while not session.sink.empty():
        evs.append(session.sink.get_nowait())
    assert any(e["ev"] == "mam_results" and e["data"]["count"] == 2
               for e in evs)
    # Aynı sayfa tekrar gelirse (farklı token'la bile) kopya yazılmaz
    session._apply("mam_results", {
        "jid": jid, "token": token, "messages": [
            {"from": jid, "body": "eski 1", "is_me": False, "mid": "A1",
             "nick": "ayse", "ts": "2026-10-01T10:00:00Z"}]})
    assert len(st._db_load_msgs_full(jid)) == 2


def test_stale_mam_result_is_dropped(session):
    session.command("open_chat", {"jid": "oda@chat.x"})
    session._mam_gen["oda@chat.x"] = 5      # istekten sonra generation arttı
    session._apply("mam_results", {
        "jid": "oda@chat.x", "token": 0, "messages": [
            {"from": "oda@chat.x", "body": "bayat", "is_me": False,
             "mid": "X1", "ts": ""}]})
    from xmppcore import storage as st
    assert st._db_load_msgs_full("oda@chat.x") == []
    assert "oda@chat.x" not in session._mam_intent


def test_load_older_mam_command_uses_cursor(session):
    jid = "oda@chat.x"
    session._mam_oldest[jid] = "arc-9"
    res = session.command("load_older_mam", {"jid": jid})
    assert res["ok"] is True
    calls = [c for c in session.bot.calls if c[0] == "fetch_mam"]
    assert calls and calls[-1][2].get("before") == "arc-9"
    assert session._mam_intent[jid]["intent"] == "older"


# ── REST ────────────────────────────────────────────────────────────────────
async def _client(monkeypatch, session=None):
    from aiohttp.test_utils import TestClient, TestServer
    if session is not None:
        monkeypatch.setattr(srv, "_TOKENS", {"tok": session})
    app = srv.make_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    return client


def test_history_endpoint_pagination(monkeypatch, session):
    from xmppcore import storage as st
    for i in range(30):
        st._db_store_msg("ali@x.im", "ali", f"m{i}", False, "10:00", "them")
    session._reactions_cache = {}

    async def go():
        client = await _client(monkeypatch, session)
        try:
            hdr = {"X-Auth-Token": "tok"}
            resp = await client.get("/api/history", headers=hdr, params={
                "jid": "ali@x.im", "limit": "10"})
            assert resp.status == 200
            data = await resp.json()
            assert len(data["messages"]) == 10
            assert data["messages"][0]["body"] == "m20"
            assert data["has_more"] is True
            first = data["messages"][0]
            resp = await client.get("/api/history", headers=hdr, params={
                "jid": "ali@x.im", "limit": "100",
                "before_id": str(first["id"]),
                "before_stored_at": first["stored_at"]})
            data2 = await resp.json()
            assert data2["messages"][0]["body"] == "m0"
            assert data2["has_more"] is False
            resp = await client.get("/api/history", headers=hdr)
            assert resp.status == 400
            resp = await client.get("/api/history", params={"jid": "x"})
            assert resp.status == 401
            # Sorgu dizesinde token artık tanınmaz (başlık zorunlu).
            resp = await client.get("/api/history",
                                    params={"token": "tok", "jid": "x"})
            assert resp.status == 401
        finally:
            await client.close()

    asyncio.run(go())


def test_login_requires_jid_and_password(monkeypatch):
    monkeypatch.setattr(srv, "_TOKENS", {})

    class _StubSession:
        def __init__(self, jid, pw, server="", port=5222):
            self.jid, self._closing = jid, False

        def start(self):
            pass

    monkeypatch.setattr(srv, "WebSession", _StubSession)
    monkeypatch.setattr("xmppcore.config._store_login", lambda *a, **k: None)

    async def go():
        client = await _client(monkeypatch)
        try:
            resp = await client.post(
                "/api/login", json={"jid": "a@b", "password": ""},
                headers={"X-Requested-With": "xmpp-web"})
            assert resp.status == 400
            body = await resp.json()
            assert "zorunlu" in body["error"]
        finally:
            await client.close()

    asyncio.run(go())


def test_settings_roundtrip_hides_api_key(monkeypatch):
    monkeypatch.setattr(srv, "_TOKENS", {"tok": object.__new__(wb.WebSession)})

    async def go():
        client = await _client(monkeypatch)
        try:
            resp = await client.get("/api/settings",
                                    headers={"X-Auth-Token": "tok"})
            assert resp.status == 200
            data = await resp.json()
            assert "claude_api_key" not in data["ai"]
            assert "koyu" in data["themes"]
            assert data["theme_colors"]["koyu"]["BG"]
            assert data["choices"]["keep_alive"]

            resp = await client.post("/api/settings",
                                     headers={"X-Auth-Token": "tok"},
                                     json={"general": {"theme": "nord"},
                                           "ai": {"keep_alive": "1h"}})
            assert resp.status == 200
            saved = await resp.json()
            assert saved["ai"]["keep_alive"] == "1h"
        finally:
            await client.close()

    asyncio.run(go())


def test_ws_command_roundtrip(monkeypatch, session):
    """WS komutu ack ile döner; olaylar kanaldan akar."""
    from aiohttp.test_utils import TestClient, TestServer

    async def go():
        monkeypatch.setattr(srv, "_TOKENS", {"tok": session})
        server = TestServer(srv.make_app())
        client = TestClient(server)
        await client.start_server()
        try:
            tr = await client.post("/api/ws-ticket",
                                   headers={"X-Auth-Token": "tok"})
            assert tr.status == 200
            ws = await client.ws_connect(
                "/ws", params={"ticket": (await tr.json())["ticket"]})
            hello = await ws.receive_json()
            assert hello["ev"] == "hello"
            await ws.send_json({"cmd": "send",
                                "args": {"to": "ali@x.im", "body": "hey"},
                                "req": 7})
            # ack + own_sent yayını (sıra korunur)
            seen = []
            for _ in range(2):
                msg = await ws.receive_json(timeout=5)
                seen.append(msg["ev"])
            assert "ack" in seen and "own_sent" in seen
            await ws.close()
        finally:
            await client.close()

    asyncio.run(go())


# ── Güvenlik katmanı (pentest 2026-10 düzeltmeleri) ─────────────────────────
def test_origin_guard_rejects_foreign_host_and_origin(monkeypatch):
    monkeypatch.setattr(srv, "_TOKENS", {"tok": object.__new__(wb.WebSession)})

    async def go():
        client = await _client(monkeypatch)
        try:
            # Yabancı Host (DNS rebinding) → 403
            resp = await client.get("/", headers={"Host": "evil.example"})
            assert resp.status == 403
            # Yerel Host, yabancı Origin (tarayıcı-CSRF) → 403
            resp = await client.post(
                "/api/login", json={"jid": "a@b", "password": "x"},
                headers={"Origin": "https://evil.example",
                         "X-Requested-With": "xmpp-web"})
            assert resp.status == 403
            # Yerel Origin + CSRF başlığı →Guard geçer (sonraki adıma ilerler)
            resp = await client.post(
                "/api/login", json={"jid": "a@b", "password": ""},
                headers={"Origin": "http://127.0.0.1",
                         "X-Requested-With": "xmpp-web"})
            assert resp.status == 400        # guard'ı geçti, doğrulama 400
        finally:
            await client.close()

    asyncio.run(go())


def test_login_requires_csrf_header(monkeypatch):
    monkeypatch.setattr(srv, "_TOKENS", {})

    class _StubSession:
        def __init__(self, jid, pw, server="", port=5222):
            self.jid, self._closing = jid, False

        def start(self):
            pass

    monkeypatch.setattr(srv, "WebSession", _StubSession)
    monkeypatch.setattr("xmppcore.config._store_login", lambda *a, **k: None)

    async def go():
        client = await _client(monkeypatch)
        try:
            # Başlık yok → 403 (text/plain basit istek CSRF'i kapalı)
            resp = await client.post("/api/login", json={
                "jid": "a@b", "password": "x"})
            assert resp.status == 403
            resp = await client.post("/api/login", json={
                "jid": "a@b", "password": "x"},
                headers={"X-Requested-With": "xmpp-web"})
            assert resp.status == 200
        finally:
            await client.close()

    asyncio.run(go())


def test_login_rate_limited(monkeypatch):
    monkeypatch.setattr(srv, "_TOKENS", {})

    class _StubSession:
        def __init__(self, jid, pw, server="", port=5222):
            self.jid, self._closing = jid, False

        def start(self):
            pass

    monkeypatch.setattr(srv, "WebSession", _StubSession)
    monkeypatch.setattr("xmppcore.config._store_login", lambda *a, **k: None)

    async def go():
        client = await _client(monkeypatch)
        try:
            hdr = {"X-Requested-With": "xmpp-web"}
            codes = []
            for _ in range(12):
                resp = await client.post("/api/login", json={
                    "jid": "a@b", "password": "x"}, headers=hdr)
                codes.append(resp.status)
            assert codes.count(429) >= 1        # pencere sınırı devrede
        finally:
            await client.close()

    asyncio.run(go())


def test_ws_ticket_single_use(monkeypatch, session):
    from aiohttp.test_utils import TestClient, TestServer

    async def go():
        monkeypatch.setattr(srv, "_TOKENS", {"tok": session})
        server = TestServer(srv.make_app())
        client = TestClient(server)
        await client.start_server()
        try:
            tr = await client.post("/api/ws-ticket",
                                   headers={"X-Auth-Token": "tok"})
            ticket = (await tr.json())["ticket"]
            # İlk kullanım: bilet yanar, bağlantı kurulur.
            ws = await client.ws_connect("/ws",
                                         params={"ticket": ticket})
            hello = await ws.receive_json()
            assert hello["ev"] == "hello"
            await ws.close()
            # Aynı bilet ikinci kez: 401
            resp = await client.get("/api/history", headers={
                "X-Auth-Token": "tok"}, params={"jid": "x"})
            assert resp.status == 200             # token geçerli; bilet yanmış
            try:
                await client.ws_connect("/ws",
                                        params={"ticket": ticket})
                raised = False
            except Exception:
                raised = True
            assert raised, "tek kullanımlık bilet ikinci kez kabul edildi"
        finally:
            await client.close()

    asyncio.run(go())


def test_insecure_mode_skips_guard(monkeypatch):
    async def go():
        from aiohttp.test_utils import TestClient, TestServer
        app = srv.make_app(insecure=True)
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        try:
            resp = await client.get("/", headers={"Host": "evil.example"})
            assert resp.status == 200       # bilinçli taviz: denetim yok
        finally:
            await client.close()

    asyncio.run(go())
