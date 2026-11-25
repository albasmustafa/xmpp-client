"""Web oturum süresi ve ⚙ → Tüm oturumları kapat.

Önceden token, sunucu çalıştıkça sonsuza dek geçerliydi (CLAUDE.md'de kabul
edilmiş kalıntı risk). Şimdi: 7 gün kullanılmayan oturum, her durumda 30 günü
dolduran oturum kapanır; açık WebSocket kullanım sayılır.
"""
import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_webapp import session  # noqa: E402,F401  (fixture)

from webapp import server as srv  # noqa: E402

DAY = 24 * 3600


class _Sess:
    def __init__(self):
        self.sinks = []
        self.stopped = False
        self.events = []
        self.dead = False

    def stop(self):
        self.stopped = True

    def _broadcast(self, ev):
        self.events.append(ev)


@pytest.fixture()
def stores(monkeypatch):
    monkeypatch.setattr(srv, "_TOKENS", {})
    monkeypatch.setattr(srv, "_TOKEN_TIMES", {})
    monkeypatch.setattr(srv, "_WS_TICKETS", {})


def test_ttl_constants_match_settings_text():
    assert srv._IDLE_TTL == 7 * DAY and srv._MAX_TTL == 30 * DAY
    html = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert "7 gün sonra, her oturum en geç 30 gün sonra" in html


def test_idle_expiry_unless_a_tab_is_connected(stores):
    s, now = _Sess(), time.time()
    srv._touch("t", now - 8 * DAY)
    assert srv._expired("t", s, now)
    s.sinks = [object()]                    # açık sekme: kullanımda
    assert not srv._expired("t", s, now)


def test_absolute_expiry_even_with_open_tab(stores):
    s, now = _Sess(), time.time()
    s.sinks = [object()]
    srv._TOKEN_TIMES["t"] = [now - 31 * DAY, now]
    assert srv._expired("t", s, now)


def test_token_without_times_stays_valid(stores):
    assert not srv._expired("eski", _Sess())


def test_revoke_stops_session_tells_tabs_and_drops_tickets(stores):
    s = _Sess()
    srv._TOKENS["a"] = s
    srv._TOKEN_TIMES["a"] = [1.0, 1.0]
    srv._WS_TICKETS["bilet"] = ("a", 0.0)
    srv._revoke("a")
    assert s.stopped and s.events == [{"ev": "logged_out", "data": {}}]
    assert srv._TOKENS == srv._TOKEN_TIMES == srv._WS_TICKETS == {}


def test_sweep_revokes_only_expired(stores):
    old, fresh, now = _Sess(), _Sess(), time.time()
    srv._TOKENS.update(o=old, f=fresh)
    srv._TOKEN_TIMES.update(o=[now - 9 * DAY, now - 8 * DAY], f=[now, now])
    srv._sweep_tokens(now)
    assert old.stopped and not fresh.stopped and list(srv._TOKENS) == ["f"]


def _run(coro_fn):
    from aiohttp.test_utils import TestClient, TestServer

    async def go():
        client = TestClient(TestServer(srv.make_app()))
        await client.start_server()
        try:
            await coro_fn(client)
        finally:
            await client.close()
    asyncio.run(go())


def test_expired_token_gets_401_and_fresh_one_is_refreshed(stores):
    old, fresh, now = _Sess(), _Sess(), time.time()
    srv._TOKENS.update(o=old, f=fresh)
    srv._TOKEN_TIMES.update(o=[now - 2 * DAY, now - 8 * DAY], f=[now - 5, now - 5])

    async def go(client):
        r = await client.post("/api/ws-ticket", headers={"X-Auth-Token": "o"})
        assert r.status == 401
        r = await client.post("/api/ws-ticket", headers={"X-Auth-Token": "f"})
        assert r.status == 200
    _run(go)
    assert old.stopped and "o" not in srv._TOKENS
    assert srv._TOKEN_TIMES["f"][1] > now - 1          # son kullanım tazelendi


def test_logout_all_revokes_every_token(stores):
    a, b = _Sess(), _Sess()
    srv._TOKENS.update(a=a, b=b)

    async def go(client):
        r = await client.post("/api/logout-all", json={})
        assert r.status == 401                          # token şart
        r = await client.post("/api/logout-all", json={},
                              headers={"X-Auth-Token": "a"})
        assert r.status == 200
    _run(go)
    assert a.stopped and b.stopped and srv._TOKENS == {}
    assert a.events == b.events == [{"ev": "logged_out", "data": {}}]


def test_open_tab_receives_logged_out_and_socket_closes(stores, session):  # noqa: F811
    srv._TOKENS["t"] = session
    session._uploads = set()                # fikstürde yok; stop() geziyor

    async def go(client):
        r = await client.post("/api/ws-ticket", headers={"X-Auth-Token": "t"})
        ticket = (await r.json())["ticket"]
        ws = await client.ws_connect("/ws", params={"ticket": ticket})
        assert (await ws.receive_json())["ev"] == "hello"
        srv._revoke("t")
        assert (await ws.receive_json()) == {"ev": "logged_out", "data": {}}
        msg = await ws.receive()
        assert msg.type.name in ("CLOSE", "CLOSED", "CLOSING")
    _run(go)
    assert "t" not in srv._TOKENS


def test_web_ui_wiring():
    js = (srv.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "logged_out() {" in js and '"/api/logout-all"' in js
    html = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="s-logout-all"' in html
