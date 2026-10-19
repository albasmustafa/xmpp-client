"""aiohttp web sunucusu: REST + WebSocket + statik dosyalar.

Tek hesaplı kişisel kullanım içindir: varsayılan yalnız 127.0.0.1'e bağlanır.
Her giriş bir WebSession (headless XMPPBot) ve rastgele bir token üretir;
token yalnız `X-Auth-Token` başlığıyla taşınır (URL'de token yok — günlük/
vekil sızıntısı kapalıdır). WebSocket, tek kullanımlık kısa ömürlü bilet
ile açılır (tarayıcı WS'de başlık gönderemez).

Saldırı yüzeyi savunmaları (pentest 2026-10):
  • Origin/Host middleware'i: yerel döngü dışı Host ya da yabancı Origin
    (tarayıcı-CSRF / DNS rebinding) 403 ile reddedilir. `--insecure`
    verilirse (LAN'a açık çalışma) bu denetimler atlanır — bilinçli taviz.
  • /api/login `X-Requested-With` başlığı ister (basit istek CSRF'i kapıdır)
    ve dakikada 10 denemeyle sınırlıdır.
  • REST `/api/draft` (masaüstü) ayrıdır; bkz. xmpp.py.

Çalıştırma:  .venv-xmpp/bin/python -m webapp.server [--host H] [--port P]
"""
import argparse
import asyncio
import collections
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web

from webapp import aiapi
from webapp.bridge import WebSession

STATIC_DIR = Path(__file__).parent / "static"
_TOKENS: dict[str, WebSession] = {}
_WS_TICKETS: dict[str, float] = {}          # bilet → son kullanma (monotonic)
_TICKET_TTL = 30.0

_MAX_BODY = 1 * 1024 * 1024
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})
_CSRF_HEADER = "X-Requested-With"
_CSRF_VALUE = "xmpp-web"
APP_INSECURE = web.AppKey("insecure", bool)
APP_LOGIN_RATE = web.AppKey("login_rate", object)   # değer: _LoginRate
_SETTINGS_GENERAL = ("notifications", "sounds", "send_read_receipts",
                     "send_typing", "auto_rejoin", "theme", "remote_previews")


def _json(data, status: int = 200) -> web.Response:
    return web.json_response(data, status=status)


def _err(message: str, status: int) -> web.Response:
    return _json({"error": message}, status=status)


def _session(request) -> WebSession:
    token = request.headers.get("X-Auth-Token") or ""
    session = _TOKENS.get(token)
    if session is None:
        raise web.HTTPUnauthorized(text="Geçersiz oturum.")
    return session


async def _body(request) -> dict:
    try:
        data = await request.content.read(_MAX_BODY + 1)
        obj = json.loads(data or b"{}")
    except Exception:
        raise web.HTTPBadRequest(text="Geçersiz JSON gövde.")
    if not isinstance(obj, dict):
        raise web.HTTPBadRequest(text="Geçersiz JSON gövde.")
    return obj


# ── Origin/Host savunma katmanı ─────────────────────────────────────────────
def _host_of(value: str) -> str:
    """Host/Origin netloc'unun makine kısmı ("127.0.0.1:8420" → "127.0.0.1")."""
    value = (value or "").strip()
    if value.startswith("["):                 # "[::1]:8420"
        return value.split("]", 1)[0] + "]"
    return value.rsplit(":", 1)[0] if ":" in value else value


@web.middleware
async def _origin_guard(request, handler):
    """Tarayıcı-CSRF ve DNS rebinding kapısı: yerel olmayan Host ya da
    yabancı Origin reddedilir. curl benzeri istemciler Origin göndermez →
    geçer; tarayıcılar aynı-kaynak istekte kendi Origin'ini yollar → geçer."""
    if not request.app[APP_INSECURE]:
        if _host_of(request.headers.get("Host", "127.0.0.1")) \
                not in _LOCAL_HOSTS:
            return _err("Geçersiz Host.", 403)
        origin = request.headers.get("Origin")
        if origin and _host_of(urlsplit(origin).netloc) not in _LOCAL_HOSTS:
            return _err("Geçersiz Origin.", 403)
    return await handler(request)


class _LoginRate:
    """/api/login için kayan pencere sayacı (tek istemcili yüzey: global)."""

    def __init__(self, max_events: int = 10, window: float = 60.0):
        self.max_events = max_events
        self.window = window
        self._events: collections.deque = collections.deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self._events and now - self._events[0] > self.window:
            self._events.popleft()
        if len(self._events) >= self.max_events:
            return False
        self._events.append(now)
        return True


# ── Giriş / oturum ──────────────────────────────────────────────────────────
async def handle_prefill(request) -> web.Response:
    from xmppcore.config import _saved_login
    saved = _saved_login(_load_cfg())
    if not saved:
        return _json({"jid": "", "port": 5222, "server": ""})
    jid, _pw, port, server = saved
    return _json({"jid": jid, "port": port, "server": server})


def _load_cfg() -> dict:
    from xmppcore.config import _load_config
    return _load_config()


def _save_cfg(cfg: dict) -> None:
    from xmppcore.config import _save_config
    _save_config(cfg)


async def handle_login(request) -> web.Response:
    from xmppcore.config import _store_login
    if request.headers.get(_CSRF_HEADER) != _CSRF_VALUE:
        # Tarayıcı "basit istek"iyle (text/plain JSON) oturum açma/CDRF kapısı.
        return _err("Eksik güvenlik başlığı.", 403)
    if not request.app[APP_LOGIN_RATE].allow():
        return _err("Çok fazla giriş denemesi — bir dakika sonra tekrar "
                    "deneyin.", 429)
    body = await _body(request)
    jid = (body.get("jid") or "").strip()
    password = body.get("password") or ""
    server = (body.get("server") or "").strip()
    try:
        port = int(body.get("port") or 5222)
    except (TypeError, ValueError):
        port = 5222
    if "@" not in jid or not password:
        return _err("JID (ad@sunucu) ve parola zorunlu.", 400)
    # Açık oturum: force yoksa engelle, varsa kapat. Eski oturum yalnız
    # güvenlik başlığı ve hız sınırını geçen istekle kapanır; yeni oturumun
    # kimliği XMPP'de doğrulanana kadar eskisi zaten durur (bkz. WebSession).
    alive = [(t, s) for t, s in _TOKENS.items() if not s.dead]
    if alive and not body.get("force"):
        return _json({"error": "Zaten açık bir oturum var.",
                      "connected_as": alive[0][1].jid,
                      "conflict": True}, 409)
    for token, old in alive:
        old.stop()
        _TOKENS.pop(token, None)
    session = WebSession(jid, password, server, port)
    session.start()
    token = secrets.token_urlsafe(24)
    _TOKENS[token] = session
    _store_login(_load_cfg(), bool(body.get("remember")), jid, password,
                 port, server)
    return _json({"token": token, "jid": jid})


async def handle_logout(request) -> web.Response:
    await _body(request)
    token = request.headers.get("X-Auth-Token") or ""
    session = _TOKENS.pop(token, None)
    if session is not None:
        session.stop()
    return _json({"ok": True})


# ── WebSocket bileti ────────────────────────────────────────────────────────
async def handle_ws_ticket(request) -> web.Response:
    """Tek kullanımlık, 30 sn ömürlü WS bileti üret (X-Auth-Token şart).

    Bilet, üreten oturumun token'ıyla eşlenir: tarayıcı WebSocket'te başlık
    gönderemediğinden kimlik biletle taşınır; bilet sızsa bile tek istekte
    yanar."""
    session = _session(request)
    now = time.monotonic()
    for t in [t for t, exp in _WS_TICKETS.items() if exp[1] < now]:
        _WS_TICKETS.pop(t, None)
    ticket = secrets.token_urlsafe(24)
    _WS_TICKETS[ticket] = (token_for(session), now + _TICKET_TTL)
    return _json({"ticket": ticket})


def token_for(session: WebSession) -> str:
    """Oturumun token'ı (ticket eşlemesi için)."""
    for token, s in _TOKENS.items():
        if s is session:
            return token
    raise web.HTTPUnauthorized(text="Geçersiz oturum.")


# ── Geçmiş / ayarlar ────────────────────────────────────────────────────────
async def handle_history(request) -> web.Response:
    session = _session(request)
    jid = request.query.get("jid", "")
    if not jid:
        return _err("jid zorunlu.", 400)
    try:
        limit = min(int(request.query.get("limit") or 60), 300)
        before = None
        if request.query.get("before_id"):
            # İmleç: (stored_at, id) — MAM sonrası id sırası zaman sırası
            # değildir; boş stored_at en eski sayılır (storage ile aynı).
            before = (request.query.get("before_stored_at") or "",
                      int(request.query.get("before_id")))
    except ValueError:
        return _err("Sayısal parametre hatalı.", 400)
    return _json(session.history(jid, before=before, limit=limit))


def _ai_public(values: dict) -> dict:
    out = {k: v for k, v in values.items() if k != "claude_api_key"}
    out["has_api_key"] = bool(values.get("claude_api_key"))
    return out


async def handle_settings_get(request) -> web.Response:
    _session(request)
    from xmppcore.ai import KEEP_ALIVE_CHOICES, TTS_ENGINES, WHISPER_MODELS, load_settings
    from xmppcore.theme import _THEMES
    cfg = _load_cfg()
    general = {k: cfg.get(k, d) for k, d in
               (("notifications", True), ("sounds", True),
                ("send_read_receipts", True), ("send_typing", True),
                ("auto_rejoin", True), ("theme", "koyu"),
                ("remote_previews", True))}
    return _json({
        "general": general,
        "ai": _ai_public(load_settings(cfg)),
        "themes": sorted(_THEMES),
        "theme_colors": _THEMES,
        "choices": {"whisper_models": list(WHISPER_MODELS),
                    "tts_engines": list(TTS_ENGINES),
                    "keep_alive": list(KEEP_ALIVE_CHOICES)},
    })


async def handle_settings_post(request) -> web.Response:
    _session(request)
    from xmppcore.ai import api_key, merge_settings
    body = await _body(request)
    cfg = _load_cfg()
    general = body.get("general")
    if isinstance(general, dict):
        for key in _SETTINGS_GENERAL:
            if key in general:
                cfg[key] = general[key]
    ai_new = body.get("ai")
    if isinstance(ai_new, dict):
        merge_settings(cfg, ai_new, body.get("api_key"))
    _save_cfg(cfg)
    from xmppcore.ai import load_settings
    for session in list(_TOKENS.values()):
        try:
            session.command("refresh_settings", {})
        except Exception:
            # Ayar kaydı, yarım/kapanan bir oturum yüzünden başarısız olmaz.
            pass
    return _json({"ok": True, "ai": _ai_public(load_settings(cfg)),
                  "api_key_set": bool(api_key(load_settings(cfg)))})


# ── AI uçları ───────────────────────────────────────────────────────────────
async def handle_ai(request) -> web.Response:
    session = _session(request)
    action = request.match_info["action"]
    body = await _body(request)
    allow = bool(body.get("allow_cloud"))
    contacts = dict(session.contacts)          # kişi adları (etiketleme)
    try:
        if action == "summary":
            out = await asyncio.to_thread(
                aiapi.summary, body.get("jid", ""),
                int(body.get("unread") or 0), allow, contacts)
        elif action == "translate":
            text = (body.get("text") or "").strip()
            if not text:
                return _err("Çevrilecek metin boş.", 400)
            out = await asyncio.to_thread(aiapi.translate, text, allow)
        elif action == "digest":
            out = await asyncio.to_thread(aiapi.digest, dict(session.unread),
                                          allow, contacts)
        elif action == "ask":
            q = (body.get("question") or "").strip()
            if not q:
                return _err("Soru boş.", 400)
            out = await asyncio.to_thread(aiapi.ask_history, q,
                                          body.get("previous") or "", allow,
                                          contacts)
        elif action == "assistant":
            out = await asyncio.to_thread(aiapi.assistant,
                                          body.get("history") or [], allow)
        else:
            return _err("Bilinmeyen AI eylemi.", 404)
    except aiapi.AIPrivacyError as e:
        return _json({"error": str(e), "privacy": True}, 403)
    except ValueError as e:
        return _err(f"Geçersiz parametre: {e}", 400)
    except Exception as e:
        from xmppcore.ai import AIError
        if isinstance(e, AIError):
            return _err(str(e), 502)
        raise
    return _json(out)


# ── WebSocket ───────────────────────────────────────────────────────────────
def _ws_command(session: WebSession, raw: str) -> dict:
    try:
        req = json.loads(raw)
        cmd = str(req.get("cmd") or "")
        result = session.command(cmd, req.get("args") or {})
    except Exception as e:
        req = {}
        result = {"ok": False, "error": str(e)}
    return {"ev": "ack", "data": {"req": req.get("req"), **result}}


async def handle_ws(request) -> web.WebSocketResponse:
    ticket = request.query.get("ticket", "")
    entry = _WS_TICKETS.pop(ticket, None)      # tek kullanım: önce düş
    if entry is None or entry[1] < time.monotonic():
        raise web.HTTPUnauthorized(text="Geçersiz WS bileti.")
    token, _exp = entry
    session = _TOKENS.get(token)
    if session is None:
        raise web.HTTPUnauthorized(text="Geçersiz oturum.")
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    sink: asyncio.Queue = asyncio.Queue(maxsize=1000)
    session.add_sink(asyncio.get_running_loop(), sink)
    try:
        await ws.send_json({"ev": "hello", "data": session.snapshot()})
        # Tek gönderici: alım ve pump görevleri sırayla yanıtlar.
        recv_task = asyncio.create_task(ws.receive())
        pump_task = asyncio.create_task(sink.get())
        try:
            while True:
                await asyncio.wait({recv_task, pump_task},
                                   return_when=asyncio.FIRST_COMPLETED)
                if recv_task.done():
                    msg = recv_task.result()
                    if msg.type != WSMsgType.TEXT:
                        break
                    await ws.send_json(_ws_command(session, msg.data))
                    recv_task = asyncio.create_task(ws.receive())
                if pump_task.done():
                    ev = pump_task.result()
                    if ws.closed:
                        break
                    await ws.send_json(ev)
                    pump_task = asyncio.create_task(sink.get())
        finally:
            recv_task.cancel()
            pump_task.cancel()
    finally:
        session.remove_sink(sink)
    return ws


# ── Statik ve uygulama ──────────────────────────────────────────────────────
async def handle_index(request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


def make_app(insecure: bool = False) -> web.Application:
    app = web.Application(client_max_size=_MAX_BODY,
                          middlewares=[_origin_guard])
    app[APP_INSECURE] = insecure
    app[APP_LOGIN_RATE] = _LoginRate()
    app.router.add_get("/", handle_index)
    app.router.add_get("/ws", handle_ws)
    app.router.add_post("/api/login", handle_login)
    app.router.add_post("/api/logout", handle_logout)
    app.router.add_post("/api/ws-ticket", handle_ws_ticket)
    app.router.add_get("/api/prefill", handle_prefill)
    app.router.add_get("/api/history", handle_history)
    app.router.add_get("/api/settings", handle_settings_get)
    app.router.add_post("/api/settings", handle_settings_post)
    app.router.add_post("/api/ai/{action}", handle_ai)
    app.router.add_static("/static/", STATIC_DIR)
    return app


def main():
    parser = argparse.ArgumentParser(
        description="xmpp.py — tarayıcı arayüzü")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument(
        "--insecure", action="store_true",
        help="Yerel döngü dışına aç: Host/Origin denetimi atlanır, trafik "
             "düz metin HTTP'de gider (yalnız güvenilir ağda).")
    args = parser.parse_args()
    insecure = args.insecure
    if _host_of(args.host) not in _LOCAL_HOSTS and not insecure:
        raise SystemExit(
            f"✗ --host {args.host} yerel döngü dışı. Ağa açmak için "
            "--insecure ekleyin (trafik şifrelenmez, düz HTTP'dir).")
    app = make_app(insecure=insecure)
    print(f"XMPP web arayüzü: http://{args.host}:{args.port}/"
          + ("  [GÜVENSİZ MOD — ağa açık]" if insecure else ""))
    try:
        web.run_app(app, host=args.host, port=args.port, print=None)
    except OSError as e:
        if e.errno == 98:       # EADDRINUSE: arayüz muhtemelen zaten açık
            print(f"✗ Port {args.port} kullanımda — arayüz zaten çalışıyor "
                  f"olabilir: http://{args.host}:{args.port}/\n"
                  f"  Yeniden başlatmak için: pkill -f webapp.server")
            raise SystemExit(1) from e
        raise


if __name__ == "__main__":
    main()
