"""XMPP bağlantısı için proxy tüneli: SOCKS5, SOCKS4a, HTTP CONNECT.

slixmpp'de proxy desteği yok. Tünel engellemeyen soket çağrılarıyla
(`loop.sock_*`, döngü thread'inde) kurulur; bağlı soket
`loop.create_connection(sock=...)`'e verilir, TLS onun üstünde açılır.
Hedef ad proxy'de çözülür (SOCKS5 ATYP=3, SOCKS4a): Tor'da yerel DNS
sızmaz. Kimlik doğrulamalı proxy desteklenmez (anlaşılır hata verilir).
Yalnız XMPP akışını kapsar; HTTP istekleri (dosya, önizleme…) kapsam dışı.
"""
import asyncio
import socket

from xmppcore.i18n import N_
from xmppcore.i18n import tr as _tr

PROXY_TYPES = ("socks5", "socks4", "http")

_SOCKS5_REPLIES = {
    1: N_("genel sunucu hatası"), 2: N_("kural seti izin vermedi"),
    3: N_("ağa ulaşılamıyor"), 4: N_("sunucuya ulaşılamıyor"),
    5: N_("bağlantı reddedildi"), 6: N_("zaman aşımı (TTL)"),
    7: N_("komut desteklenmiyor"), 8: N_("adres türü desteklenmiyor"),
}


class ProxyError(OSError):
    """Tünel kurulamadı (slixmpp bunu bağlantı hatası olarak işler)."""


def proxy_settings(cfg: dict):
    """Config'teki "proxy" kaydı geçerliyse {type, host, port}, değilse None."""
    p = cfg.get("proxy") or {}
    if not isinstance(p, dict) or p.get("type") not in PROXY_TYPES:
        return None
    host = str(p.get("host") or "").strip()
    try:
        port = int(p.get("port") or 0)
    except (TypeError, ValueError):
        return None
    if not host or not 0 < port < 65536:
        return None
    return {"type": p["type"], "host": host, "port": port}


def proxy_from_form(ptype: str, host: str, port_text: str) -> dict:
    """Proxy penceresi girdisi → config kaydı; geçersizse ValueError."""
    if ptype not in PROXY_TYPES:
        return {"type": "none", "host": "", "port": 0}
    host = (host or "").strip()
    if not host:
        raise ValueError(_tr("Proxy adresi girin (Tor için 127.0.0.1)."))
    try:
        port = int((port_text or "").strip())
    except ValueError:
        raise ValueError(_tr("Geçerli bir port girin (1–65535).")) from None
    if not 0 < port < 65536:
        raise ValueError(_tr("Geçerli bir port girin (1–65535)."))
    return {"type": ptype, "host": host, "port": port}


async def _recv_exact(loop, sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = await loop.sock_recv(sock, n - len(buf))
        if not chunk:
            raise ProxyError(_tr("Proxy bağlantıyı beklenmedik şekilde kapattı"))
        buf += chunk
    return buf


def _host_bytes(host: str) -> bytes:
    name = host.encode("idna")
    if not 0 < len(name) < 256:
        raise ProxyError(_tr("Geçersiz hedef adı: {!r}").format(host))
    return name


async def _socks5(loop, sock, host: str, port: int):
    await loop.sock_sendall(sock, b"\x05\x01\x00")          # yalnız "kimliksiz"
    ver, method = await _recv_exact(loop, sock, 2)
    if ver != 5:
        raise ProxyError(_tr("SOCKS5 değil: proxy türünü kontrol edin"))
    if method != 0:
        raise ProxyError(_tr("SOCKS5 proxy kimlik doğrulama istiyor (desteklenmiyor)"))
    name = _host_bytes(host)
    await loop.sock_sendall(sock, b"\x05\x01\x00\x03" + bytes([len(name)])
                            + name + port.to_bytes(2, "big"))
    _ver, rep, _rsv, atyp = await _recv_exact(loop, sock, 4)
    if rep != 0:
        reason = _SOCKS5_REPLIES.get(rep)
        reason = _tr(reason) if reason else _tr("hata kodu {}").format(rep)
        raise ProxyError(_tr("SOCKS5: {}").format(reason))
    if atyp == 1:
        await _recv_exact(loop, sock, 4 + 2)
    elif atyp == 4:
        await _recv_exact(loop, sock, 16 + 2)
    elif atyp == 3:
        (length,) = await _recv_exact(loop, sock, 1)
        await _recv_exact(loop, sock, length + 2)
    else:
        raise ProxyError(_tr("SOCKS5: geçersiz proxy yanıtı"))


async def _socks4a(loop, sock, host: str, port: int):
    # SOCKS4a: IP 0.0.0.1 + ad → ad proxy'de çözülür
    await loop.sock_sendall(sock, b"\x04\x01" + port.to_bytes(2, "big")
                            + b"\x00\x00\x00\x01\x00" + _host_bytes(host) + b"\x00")
    resp = await _recv_exact(loop, sock, 8)
    if resp[1] != 0x5A:
        raise ProxyError(_tr("SOCKS4: istek reddedildi (kod {})").format(resp[1]))


async def _http_connect(loop, sock, host: str, port: int):
    target = f"{host}:{port}"
    await loop.sock_sendall(
        sock, f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode("ascii"))
    head = b""
    while not head.endswith(b"\r\n\r\n"):       # tek tek: başlıktan fazlasını okuma
        head += await _recv_exact(loop, sock, 1)
        if len(head) > 8192:
            raise ProxyError(_tr("HTTP proxy yanıtı çok uzun"))
    status = head.split(b"\r\n", 1)[0].decode("latin-1").strip()
    parts = status.split(None, 2)
    if len(parts) < 2 or not parts[0].startswith("HTTP/") or parts[1] != "200":
        raise ProxyError(_tr("HTTP proxy reddetti: {}").format(status))


_HANDSHAKES = {"socks5": _socks5, "socks4": _socks4a, "http": _http_connect}


async def open_tunnel(loop, proxy: dict, host: str, port: int,
                      timeout: float = 30) -> socket.socket:
    """`proxy` üzerinden host:port'a tünel kur; bağlı (engellemeyen) soket."""
    async def _open():
        infos = await loop.getaddrinfo(proxy["host"], proxy["port"],
                                       type=socket.SOCK_STREAM)
        last = None
        for family, stype, proto, _canon, addr in infos:
            sock = socket.socket(family, stype, proto)
            sock.setblocking(False)
            try:
                await loop.sock_connect(sock, addr)
            except OSError as e:
                sock.close()
                last = e
                continue
            try:
                await _HANDSHAKES[proxy["type"]](loop, sock, host, port)
            except BaseException:
                sock.close()
                raise
            return sock
        raise ProxyError(_tr("Proxy'ye bağlanılamadı ({}:{}): {}")
                         .format(proxy['host'], proxy['port'], last))
    try:
        return await asyncio.wait_for(_open(), timeout)
    except asyncio.TimeoutError as e:
        raise ProxyError(_tr("Proxy zaman aşımı")) from e
