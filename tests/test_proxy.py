"""Proxy / SOCKS ayarı gerçekten uygulanır (önceden kaydedilip yok sayılıyordu).

Tüneller 127.0.0.1'de çalışan sahte proxy sunucularıyla uçtan uca sınanır:
el sıkışma → tünel → veri yankısı. Dış ağ kullanılmaz.
"""
import asyncio
import types

import pytest

import xmpp
from xmppcore import proxy as proxy_mod

TARGET = ("xmpp.example", 5222)


# ── Ayar doğrulama ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("cfg, expected", [
    ({}, None),
    ({"proxy": {"type": "none", "host": "127.0.0.1", "port": 9050}}, None),
    ({"proxy": {"type": "socks5", "host": "", "port": 9050}}, None),
    ({"proxy": {"type": "socks5", "host": "127.0.0.1", "port": 0}}, None),
    ({"proxy": {"type": "socks5", "host": "127.0.0.1", "port": "x"}}, None),
    ({"proxy": {"type": "socks5", "host": " 127.0.0.1 ", "port": "9050"}},
     {"type": "socks5", "host": "127.0.0.1", "port": 9050}),
])
def test_proxy_settings(cfg, expected):
    assert proxy_mod.proxy_settings(cfg) == expected


# ── Sahte proxy sunucuları ───────────────────────────────────────────────────

async def _echo(reader, writer):
    data = await reader.read(100)
    writer.write(data)
    await writer.drain()


def _socks5_server(seen, rep=0, method=0):
    async def handle(reader, writer):
        greet = await reader.readexactly(3)
        seen.append(greet)
        writer.write(bytes([5, method]))
        await writer.drain()
        if method != 0:
            writer.close()
            return
        head = await reader.readexactly(5)              # VER CMD RSV ATYP LEN
        name = await reader.readexactly(head[4])
        port = int.from_bytes(await reader.readexactly(2), "big")
        seen.append((head[3], name.decode(), port))
        writer.write(bytes([5, rep, 0, 1, 127, 0, 0, 1, 0, 0]))
        await writer.drain()
        if rep == 0:
            await _echo(reader, writer)
        writer.close()
    return handle


def _socks4_server(seen, ok=True):
    async def handle(reader, writer):
        head = await reader.readexactly(8)
        rest = await reader.readuntil(b"\x00")               # userid
        host = (await reader.readuntil(b"\x00"))[:-1]
        seen.append((head[:2], int.from_bytes(head[2:4], "big"),
                     head[4:8], rest, host.decode()))
        writer.write(bytes([0, 0x5A if ok else 0x5B]) + b"\x00" * 6)
        await writer.drain()
        if ok:
            await _echo(reader, writer)
        writer.close()
    return handle


def _http_server(seen, status=b"200 Connection established"):
    async def handle(reader, writer):
        req = await reader.readuntil(b"\r\n\r\n")
        seen.append(req.decode())
        writer.write(b"HTTP/1.1 " + status + b"\r\nProxy-Agent: test\r\n\r\n")
        await writer.drain()
        if status.startswith(b"200"):
            await _echo(reader, writer)
        writer.close()
    return handle


def _through(handler, ptype):
    """Sahte proxy'yi başlat, tünel kur, içinden yankı al."""
    async def main():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        loop = asyncio.get_running_loop()
        try:
            sock = await proxy_mod.open_tunnel(
                loop, {"type": ptype, "host": "127.0.0.1", "port": port},
                *TARGET, timeout=5)
            try:
                await loop.sock_sendall(sock, b"<stream>")
                return await loop.sock_recv(sock, 100)
            finally:
                sock.close()
        finally:
            server.close()
            await server.wait_closed()
    return asyncio.run(main())


def test_socks5_tunnel_resolves_name_at_proxy():
    seen = []
    assert _through(_socks5_server(seen), "socks5") == b"<stream>"
    assert seen[0] == b"\x05\x01\x00"                     # kimlik doğrulamasız
    assert seen[1] == (3, "xmpp.example", 5222)           # ATYP=3: DNS proxy'de


def test_socks5_refusal_is_reported():
    with pytest.raises(proxy_mod.ProxyError, match="reddedildi"):
        _through(_socks5_server([], rep=5), "socks5")


def test_socks5_auth_required_is_reported():
    with pytest.raises(proxy_mod.ProxyError, match="kimlik"):
        _through(_socks5_server([], method=0xFF), "socks5")


def test_socks4a_tunnel():
    seen = []
    assert _through(_socks4_server(seen), "socks4") == b"<stream>"
    ver_cmd, port, ip, userid, host = seen[0]
    assert ver_cmd == b"\x04\x01" and port == 5222
    assert ip == b"\x00\x00\x00\x01" and host == "xmpp.example"   # SOCKS4a


def test_socks4_refusal_is_reported():
    with pytest.raises(proxy_mod.ProxyError, match="SOCKS4"):
        _through(_socks4_server([], ok=False), "socks4")


def test_http_connect_tunnel():
    seen = []
    assert _through(_http_server(seen), "http") == b"<stream>"
    assert seen[0].startswith("CONNECT xmpp.example:5222 HTTP/1.1\r\n")


def test_http_connect_refusal_is_reported():
    with pytest.raises(proxy_mod.ProxyError, match="407"):
        _through(_http_server([], b"407 Proxy Authentication Required"), "http")


def test_unreachable_proxy_is_reported():
    async def main():
        loop = asyncio.get_running_loop()
        await proxy_mod.open_tunnel(
            loop, {"type": "socks5", "host": "127.0.0.1", "port": 1}, *TARGET,
            timeout=5)
    with pytest.raises(proxy_mod.ProxyError, match="bağlanılamadı"):
        asyncio.run(main())


# ── XMPPBot entegrasyonu ─────────────────────────────────────────────────────

PROXY = {"type": "socks5", "host": "127.0.0.1", "port": 9050}


def _bot(monkeypatch, proxy):
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None          # XMLStream.__del__ bunu bekler
    bot.default_port = 5222
    monkeypatch.setattr(xmpp.XMPPBot, "_current_proxy", lambda self: proxy)
    return bot


def test_proxy_skips_local_dns(monkeypatch):
    """Tor'da SRV/DNS sorgusu yerel çözücüye sızmamalı: ad proxy'de çözülür."""
    async def _no_dns(self, domain, port=None):
        raise AssertionError("yerel DNS sorgusu yapıldı")
    monkeypatch.setattr(xmpp.ClientXMPP, "get_dns_records", _no_dns)
    bot = _bot(monkeypatch, PROXY)
    recs = asyncio.run(xmpp.XMPPBot.get_dns_records(bot, "yax.im"))
    assert recs == [("", "yax.im", "yax.im", 5222)]


def test_no_proxy_keeps_dns(monkeypatch):
    async def _dns(self, domain, port=None):
        return [("", domain, "1.2.3.4", 5222)]
    monkeypatch.setattr(xmpp.ClientXMPP, "get_dns_records", _dns)
    bot = _bot(monkeypatch, None)
    recs = asyncio.run(xmpp.XMPPBot.get_dns_records(bot, "yax.im"))
    assert recs[0][2] == "1.2.3.4"


def _attempt_bot(monkeypatch, tunnel):
    bot = _bot(monkeypatch, PROXY)
    bot._current_connection_attempt = object()
    bot._connect_loop_wait = 1
    bot.get_ssl_context = lambda: "SSL"
    bot.events = []
    bot.event = lambda name, data=None: bot.events.append((name, data))
    created = []

    async def _create(factory, **kw):
        created.append(kw)
    bot.loop = types.SimpleNamespace(create_connection=_create)
    monkeypatch.setattr(xmpp, "_open_proxy_tunnel", tunnel)
    return bot, created


def test_connection_goes_through_tunnel(monkeypatch):
    async def _tunnel(loop, proxy, host, port, **kw):
        assert (proxy, host, port) == (PROXY, "yax.im", 5223)
        return "SOKET"
    bot, created = _attempt_bot(monkeypatch, _tunnel)
    ok = asyncio.run(xmpp.XMPPBot._attempt_connection(
        bot, "yax.im", 5223, True, "yax.im"))
    assert ok is True and bot._connect_loop_wait == 0
    assert created == [{"sock": "SOKET", "ssl": "SSL", "server_hostname": "yax.im"}]


def test_proxy_failure_is_a_connection_failure(monkeypatch):
    async def _tunnel(*a, **kw):
        raise proxy_mod.ProxyError("SOCKS5: bağlantı reddedildi")
    bot, created = _attempt_bot(monkeypatch, _tunnel)
    ok = asyncio.run(xmpp.XMPPBot._attempt_connection(
        bot, "yax.im", 5222, False, None))
    assert ok is False and created == []
    assert bot.events[-1][0] == "connection_failed"


def test_proxy_dialog_explains_scope():
    import inspect
    src = inspect.getsource(xmpp.MainWindow._proxy_dialog)
    assert "Yalnız XMPP bağlantısı" in src


@pytest.mark.parametrize("ptype, host, port, expected", [
    ("none", "", "", {"type": "none", "host": "", "port": 0}),
    ("socks5", " 127.0.0.1 ", "9050",
     {"type": "socks5", "host": "127.0.0.1", "port": 9050}),
])
def test_proxy_form_accepts_valid(ptype, host, port, expected):
    assert proxy_mod.proxy_from_form(ptype, host, port) == expected


@pytest.mark.parametrize("host, port", [("127.0.0.1", "abc"), ("", "9050"),
                                        ("127.0.0.1", "70000")])
def test_proxy_form_rejects_invalid(host, port):
    """Port alanına sayı dışı bir şey yazınca Kaydet çöküyordu (int())."""
    with pytest.raises(ValueError, match="port|adres"):
        proxy_mod.proxy_from_form("socks5", host, port)
