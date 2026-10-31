"""Headless web oturumu: MainWindow'nun Tk'siz karşılığı.

`WebSession`, `xmpp.start()` ile aynı thread modelini kullanır (XMPPBot ayrı
asyncio döngüsünde, olaylar gui_q ile). MainWindow'nun `_handle`/`_store`
davranışının olayla ilgili kısmını birebir uygular: durum güncellemesi +
SQLite kaydı + WebSocket olayı. Pencere/balon işleri tarayıcıdadır; burada
yalnız sunucu tarafı davranışlar (okundu bildirimi, otomatik oda katılımı,
kayıt, OMEMO mod takibi) yaşar.
"""
import asyncio
import queue
import threading
import time
from datetime import datetime

from xmppcore import sensitive as _sensitive
from xmppcore import storage as _storage
from xmppcore.ai import RETRACTED_BODY
from xmppcore.config import _load_config, _save_config
from xmppcore.constants import _log
from xmppcore.helpers import _new_msg_id
from xmppcore.i18n import tr as _tr


def _safe_put(q, ev):
    """Kanal doluysa en eski olayı düşürüp yenisini yaz (yavaş istemcide
    köprü thread'i ve diğer istemciler etkilenmez)."""
    try:
        q.put_nowait(ev)
    except asyncio.QueueFull:
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            pass


class WebSession:
    """Tek hesaplı headless oturum. thread-safe: state güncellemeleri
    köprü thread'inde, komutlar aiohttp thread'inden gelir (bot metotları
    zaten run_coroutine_threadsafe ile güvenli; dict yazmaları atomik)."""

    def __init__(self, jid: str, password: str, server: str = "",
                 port: int = 5222):
        import xmpp as _app  # facade: XMPPBot + _shutdown_loop
        self._app = _app
        self.jid = jid
        self.password = password
        self.server = server
        self.port = port
        self.gui_q: queue.Queue = queue.Queue()
        self.bot = None
        self.thread: threading.Thread | None = None
        self._closing = False
        self._auth_failed = False
        self.sinks: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._sinks_lock = threading.Lock()
        # ── Oturum durumu (MainWindow karşılıkları) ──
        self.contacts: dict[str, str] = {}       # jid → görünen ad
        self.presence: dict[str, dict] = {}      # jid → {ptype, pshow}
        self.unread: dict[str, int] = {}
        self.rooms: set[str] = set()
        self.members: dict[str, dict] = {}       # room → {nick: {...}}
        self.subjects: dict[str, str] = {}
        self.enc_modes: dict[str, str] = {}      # jid → none|omemo
        self.typing: dict[str, bool] = {}
        self.chats: dict[str, list] = {}         # jid → [giriş demetleri]
        self._reactions_cache: dict[str, dict] = {}
        self.bookmarks: list = []
        self.rooms_found: list = []
        self.active = ""                          # tarayıcıdaki açık sohbet
        # ── MAM (XEP-0313) sayfalama durumu (MainWindow karşılıkları) ──
        self._mam_gen: dict[str, int] = {}        # jid → son token
        self._mam_intent: dict[str, dict] = {}    # jid → {"token", "intent"}
        self._mam_oldest: dict[str, str] = {}     # jid → archive imleci
        self._mam_has_more: dict[str, bool] = {}
        cfg = _load_config()
        self._send_read_receipts = bool(cfg.get("send_read_receipts", True))
        self._send_typing = bool(cfg.get("send_typing", True))
        self._leak_guard = bool((cfg.get("ai") or {}).get("leak_guard", True))

    # ── Yaşam döngüsü (xmpp.start() ile aynı model) ──────────────────────────
    def start(self):
        t = threading.Thread(target=self._run_xmpp, daemon=True,
                             name="web-xmpp")
        self.thread = t
        t.start()
        for _ in range(100):
            if self.bot is not None:
                break
            time.sleep(0.05)
        threading.Thread(target=self._poll_loop, daemon=True,
                         name="web-bridge").start()

    def _run_xmpp(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            bot = self._app.XMPPBot(self.jid, self.password, self.gui_q)
            bot.loop = loop
            self.bot = bot
            if self.server or self.port != 5222:
                bot.connect(host=self.server or bot.default_domain,
                            port=self.port)
            else:
                bot.connect()
            loop.run_forever()
        except Exception as e:
            _log.error("Web XMPP thread'i durdu", exc_info=True)
            try:
                self.gui_q.put(("error", _tr("XMPP bağlantı thread'i durdu: {}").format(e)))
            except Exception:
                pass
        finally:
            self._app._shutdown_loop(loop)

    def stop(self):
        """Bağlantıyı kapat (MainWindow._quit karşılığı)."""
        self._closing = True
        bot = self.bot
        if bot is not None and getattr(bot, "loop", None) is not None:
            try:
                if bot.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        bot._close_connection(), bot.loop)
            except RuntimeError:
                pass

    @property
    def dead(self) -> bool:
        """Yenisi başlatılmadan önce kapatılması gereken oturum mu?"""
        return self._auth_failed or (self._closing and self.bot is None)

    # ── WebSocket kanalları ──────────────────────────────────────────────────
    def add_sink(self, loop, q: asyncio.Queue):
        with self._sinks_lock:
            self.sinks.append((loop, q))

    def remove_sink(self, q: asyncio.Queue):
        with self._sinks_lock:
            self.sinks[:] = [(loop, sink)
                             for loop, sink in self.sinks if sink is not q]

    def _broadcast(self, ev: dict):
        with self._sinks_lock:
            sinks = list(self.sinks)
        for loop, q in sinks:
            try:
                loop.call_soon_threadsafe(_safe_put, q, dict(ev))
            except RuntimeError:
                pass

    # ── gui_q tüketimi (MainWindow._poll/_handle karşılığı) ─────────────────
    def _poll_loop(self):
        while not self._closing:
            try:
                kind, data = self.gui_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._apply(kind, data)
            except Exception:
                _log.error("Köprü olayı işlenemedi (kind=%s)", kind,
                           exc_info=True)

    def _apply(self, kind, data):
        """Olayı duruma uygula ve tarayıcıya izdüşür. MainWindow._handle'ın
        Tk'siz karşılığı; davranış farkları belgelenmiştir."""
        if kind == "connected":
            self.contacts = dict(data)
            self._rejoin_saved_rooms()
            self._broadcast({"ev": "connected",
                             "data": {"roster": data, "jid": self.jid}})

        elif kind == "msg":
            frm, nick, body = data["from"], data["nick"], data["body"]
            oob = data.get("oob", "")
            enc = data.get("encrypted", False)
            mid = data.get("mid", "")
            # Gelen OMEMO → bu sohbette OMEMO'yu otomatik aç (_handle ile aynı)
            if enc == "omemo" and self.enc_modes.get(frm) != "omemo":
                self.enc_modes[frm] = "omemo"
            reply = self._resolve_reply(data.get("reply"), frm)
            self._store(frm, body, tag="them", sender=nick, is_me=False,
                        oob=oob, encrypted=bool(enc), mid=mid, reply_to=reply)
            unread_total = 0
            if self.active == frm:
                if mid and self.bot and self._send_read_receipts:
                    self.bot.send_marker(frm, mid, "displayed")
            else:
                self.unread[frm] = self.unread.get(frm, 0) + 1
                unread_total = sum(self.unread.values())
            self._broadcast({"ev": "msg", "data": {**data, "reply": reply,
                                                   "is_unread":
                                                       self.active != frm,
                                                   "unread_total":
                                                       unread_total}})

        elif kind == "own_msg":
            to, body = data["to"], data["body"]
            enc = bool(data.get("encrypted", False))
            reply = self._resolve_reply(data.get("reply"), to)
            self._store(to, body, tag="me", sender="Ben", is_me=True,
                        oob=data.get("oob", ""), encrypted=enc,
                        mid=data.get("mid", ""), reply_to=reply)
            self._broadcast({"ev": "own_msg", "data": {**data,
                                                       "reply": reply}})

        elif kind == "typing":
            self.typing[data["jid"]] = bool(data.get("active"))
            self._broadcast({"ev": "typing", "data": data})

        elif kind == "presence":
            self.presence[data["jid"]] = {"ptype": data.get("ptype", ""),
                                          "pshow": data.get("pshow", "")}
            self._broadcast({"ev": "presence", "data": data})

        elif kind == "read_elsewhere":
            self.unread.pop(data, None)     # veri düz jid
            self._broadcast({"ev": "read_elsewhere", "data": {"jid": data}})

        elif kind == "marker_displayed":
            self._broadcast({"ev": "marker_displayed", "data": data})

        elif kind == "msg_correction":
            frm = data["from"]
            if self._mutate_entry(frm, data["orig_id"], data["body"]):
                _storage._db_update_msg_body(frm, data["orig_id"],
                                             data["body"])
            self._broadcast({"ev": "msg_correction", "data": data})

        elif kind == "msg_retract":
            frm = data["from"]
            if self._mutate_entry(frm, data["retracted_id"], RETRACTED_BODY):
                _storage._db_update_msg_body(frm, data["retracted_id"],
                                             RETRACTED_BODY)
                _storage._db_clear_reactions_mid(frm, data["retracted_id"])
            self._broadcast({"ev": "msg_retract", "data": data})

        elif kind == "msg_reactions":
            cur = self._apply_reactions(data)
            self._broadcast({"ev": "msg_reactions", "data": {**data,
                                                             "reactions": cur}})

        elif kind == "muc_presence":
            room, nick = data["room"], data["nick"]
            mem = self.members.setdefault(room, {})
            if data.get("online"):
                mem[nick] = {"role": data.get("role", ""),
                             "affil": data.get("affil", ""),
                             "show": data.get("show", "")}
            else:
                mem.pop(nick, None)
            self._broadcast({"ev": "muc_presence", "data": data})

        elif kind == "muc_subject":
            self.subjects[data["room"]] = data.get("subject", "")
            self._broadcast({"ev": "muc_subject", "data": data})

        elif kind == "room_joined":
            room = data if isinstance(data, str) else (data or {}).get("room",
                                                                       "")
            self.rooms.add(room)
            self._save_room(room)
            self._broadcast({"ev": "room_joined", "data": {"room": room}})

        elif kind == "room_left":
            room = data if isinstance(data, str) else data.get("room", "")
            self.rooms.discard(room)
            self.members.pop(room, None)
            self.subjects.pop(room, None)
            self._remove_room(room)
            self._broadcast({"ev": "room_left", "data": {"room": room}})

        elif kind == "bookmarks":
            self.bookmarks = list(data or [])
            self._broadcast({"ev": "bookmarks", "data": data})

        elif kind == "bookmarks_update":
            self._broadcast({"ev": "bookmarks_update", "data": data})

        elif kind == "rooms_discovered":
            self.rooms_found = list(data or [])
            self._broadcast({"ev": "rooms_discovered", "data": data})

        elif kind == "mam_results":
            self._apply_mam_results(data)

        elif kind in ("rooms_discover_failed", "room_taken", "room_exists",
                      "room_created", "muc_invite", "subscribe_req",
                      "search_results", "blocked_list"):
            self._broadcast({"ev": kind, "data": data})

        elif kind == "auth_failed":
            self._auth_failed = True
            self._broadcast({"ev": "auth_failed", "data": {}})

        elif kind in ("sys_msg", "error", "disconnected", "conn_failed",
                      "ft_error", "file_uploaded"):
            self._broadcast({"ev": kind, "data":
                             data if isinstance(data, str) else dict(data)})

        # vcard / omemo_fps / mam_results / room_config / api_* : geri çağrı
        # (cb) ya da masaüstü-özel taşırlar; web v1 kapsamı dışında.

    # ── Store ve bellek yardımcıları (_store karşılığı) ─────────────────────
    def _store(self, target, body, tag="them", sender="", is_me=None,
               oob="", encrypted=False, mid="", reply_to=None,
               stored_at=None):
        ts = datetime.now().strftime("%H:%M")
        if is_me is None:
            is_me = (tag == "me")
        self.chats.setdefault(target, []).append(
            (sender, body, is_me, ts, tag, oob, encrypted, mid))
        rep = reply_to or {}
        _storage._db_store_msg(target, sender, body, is_me, ts, tag, oob,
                               encrypted, mid, "", rep.get("id", ""),
                               rep.get("sender", ""), rep.get("body", ""),
                               stored_at=stored_at)

    # ── MAM (XEP-0313): oda/1:1 arşiv geçmişi ────────────────────────────────
    @staticmethod
    def _mam_times(ts: str) -> tuple[str, str | None]:
        """MAM damgasını (HH:MM, stored_at) ikilisine çevir."""
        if not ts:
            return datetime.now().strftime("%H:%M"), None
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            local = dt.astimezone()
            return (local.strftime("%H:%M"),
                    local.strftime("%Y-%m-%dT%H:%M:%S"))
        except Exception:
            return (ts[-8:-3] if len(ts) > 8 else ""), None

    def _mam_fetch(self, jid: str, intent: str, before: str | None = None):
        """Arşiv sayfası iste (MainWindow _load_mam_history/_load_older_mam
        karşılığı); niyet isteğin token'ına bağlanır. Tek uçuşta istek:
        niyet beklemedeysen yeni istek gönderilmez."""
        if self.bot is None or self._mam_intent.get(jid):
            return False
        gen = self._mam_gen.get(jid, 0)
        self._mam_intent[jid] = {"token": gen, "intent": intent}
        try:
            self.bot.fetch_mam(jid, 50, before=before, token=gen)
            return True
        except Exception:
            self._mam_intent.pop(jid, None)
            _log.warning("MAM isteği başlatılamadı (jid=%s)", jid,
                         exc_info=True)
            return False

    def _maybe_initial_mam(self, jid: str):
        """Yerel geçmiş boşsa (yeni oda/sohbet) arşivin son sayfasını çek."""
        if self.bot is None or not jid:
            return
        if self._mam_intent.get(jid):
            return
        if _storage._db_load_msgs_full(jid, limit=1):
            return
        self._mam_fetch(jid, "initial")

    def _apply_mam_results(self, data):
        """Sonuçları DB'ye yaz (web geçmişi DB'den okur), bellek geçmişinin
        önüne ekle ve tarayıcıya haber ver. Yeni gelenler MainWindow ile
        aynı imza dedupe'sinden geçer: (kimlik-alias, body, yön)."""
        jid = data.get("jid", "")
        # Bayat sonuç: token güncel kuşağa eşit değilse yok say; yalnız
        # KENDİ token'ına ait niyeti düşürebilir ([2F-Blocker] kuralı).
        token = data.get("token")
        if token is not None and token != self._mam_gen.get(jid, 0):
            if self._mam_intent.get(jid, {}).get("token") == token:
                self._mam_intent.pop(jid, None)
            return
        self._mam_intent.pop(jid, None)
        msgs = data.get("messages", [])
        first_cursor = (msgs[0].get("archive_id") or msgs[0].get("mid", "")
                        if msgs else "")
        if first_cursor:
            self._mam_oldest[jid] = first_cursor
        self._mam_has_more[jid] = len(msgs) >= 50 and bool(first_cursor)
        seen = {(e[7], e[1], bool(e[2]))
                for e in self.chats.get(jid, []) if e[7]}
        fresh_entries = []
        for m in msgs:
            mid = m.get("mid", "")
            raw_id = m.get("raw_id", "")
            body = m.get("body", "")
            direction = bool(m.get("is_me"))
            aliases = {a for a in (mid, raw_id) if a}
            if aliases and any((a, body, direction) in seen for a in aliases):
                continue
            if mid and _storage._db_mid_exists(jid, mid):
                for a in aliases:
                    seen.add((a, body, direction))
                continue
            hm, stored_at = self._mam_times(m.get("ts", ""))
            sender = ("Ben" if direction
                      else (m.get("nick") or m.get("from", jid).split("@")[0]))
            _storage._db_store_msg(jid, sender, body, direction, hm,
                                   "me" if direction else "them",
                                   "", False, mid, stored_at=stored_at)
            fresh_entries.append((sender, body, direction, hm,
                                  "me" if direction else "them", "", False,
                                  mid))
            for a in aliases:
                seen.add((a, body, direction))
        if fresh_entries:
            self.chats[jid] = fresh_entries + self.chats.get(jid, [])
        self._broadcast({"ev": "mam_results", "data": {
            "jid": jid, "count": len(fresh_entries),
            "has_more": self._mam_has_more.get(jid, False)}})

    def _mutate_entry(self, jid, mid, new_body) -> bool:
        hist = self.chats.get(jid, [])
        for i in range(len(hist) - 1, -1, -1):
            if hist[i][7] == mid:
                e = hist[i]
                hist[i] = (e[0], new_body, *e[2:7], e[7])
                return True
        return False

    def _apply_reactions(self, data) -> dict:
        """Gönderenin eski tepkilerini kaldırıp yenisini uygula; güncel
        {emoji: [sender]} haritasını döndürür."""
        jid, mid, nick = data["from"], data["target_id"], data.get("nick", "")
        emojis = set(data.get("emojis") or [])
        chat = self.reactions_map(jid)
        cur = chat.setdefault(mid, {})
        for emoji, senders in list(cur.items()):
            if nick in senders:
                _storage._db_save_reaction(jid, mid, emoji, nick, add=False)
                senders.remove(nick)
                if not senders:
                    del cur[emoji]
        for emoji in emojis:
            _storage._db_save_reaction(jid, mid, emoji, nick, add=True)
            cur.setdefault(emoji, []).append(nick)
        return cur

    def reactions_map(self, jid) -> dict:
        """{mid: {emoji: [sender]}} — DB'den yükle, canlı olaylarla tazele."""
        if jid not in self._reactions_cache:
            self._reactions_cache[jid] = _storage._db_load_reactions(jid)
        return self._reactions_cache[jid]

    def unread_snapshot(self) -> dict:
        return {"counts": dict(self.unread),
                "total": sum(self.unread.values())}

    def _resolve_reply(self, reply, peer) -> dict | None:
        if not reply or not reply.get("id"):
            return None
        return {"id": reply.get("id", ""), "to": reply.get("to", "") or peer,
                "sender": reply.get("sender", ""),
                "body": reply.get("body", "")}

    # ── Odalar ───────────────────────────────────────────────────────────────
    def _rejoin_saved_rooms(self):
        cfg = _load_config()
        if not cfg.get("auto_rejoin", True):
            return
        for room, info in (cfg.get("rooms") or {}).items():
            self.join_room(room, info.get("nick", self.nick_default()))

    def join_room(self, room, nick=None):
        room = (room or "").strip()
        if not room or "@" not in room or self.bot is None:
            return False
        nick = (nick or "").strip() or self.nick_default()
        self.bot.my_nicks[room] = nick
        self.bot.join_room(room, nick)
        return True

    def leave_room(self, room):
        if self.bot is None:
            return
        self.bot.leave_room(room, self.bot.my_nicks.get(room, ""))

    def discover_rooms(self):
        if self.bot is None:
            return False
        self.bot.discover_rooms(self.bot.muc_service
                                or self.jid.split("@")[-1])
        return True

    def nick_default(self) -> str:
        return self.jid.split("@")[0]

    def _save_room(self, room):
        if not room:
            return
        cfg = _load_config()
        cfg.setdefault("rooms", {})[room] = {
            "nick": (self.bot.my_nicks.get(room) if self.bot else "")
                    or self.nick_default()}
        _save_config(cfg)

    def _remove_room(self, room):
        cfg = _load_config()
        if room in (cfg.get("rooms") or {}):
            del cfg["rooms"][room]
            _save_config(cfg)

    # ── Komutlar (tarayıcı → bot; hepsi thread-safe) ─────────────────────────
    def command(self, cmd: str, args: dict) -> dict:
        """WS komutunu uygula; {"ok": bool, ...} döndürür."""
        if self._closing:
            return {"ok": False, "error": _tr("Oturum kapanıyor.")}
        bot = self.bot
        if cmd == "send":
            return self._cmd_send(args)
        if cmd == "typing":
            if bot and self._send_typing:
                mtype = "groupchat" if args.get("to") in self.rooms \
                    else "chat"
                bot.send_chatstate(args["to"],
                                   "composing" if args.get("active")
                                   else "active", mtype)
            return {"ok": True}
        if cmd == "open_chat":
            self.active = args.get("jid", "")
            self.unread.pop(self.active, None)
            self._broadcast({"ev": "unread_update",
                             "data": self.unread_snapshot()})
            self._maybe_initial_mam(self.active)
            return {"ok": True}
        if cmd == "load_older_mam":
            jid = args.get("jid", "")
            if not self._mam_has_more.get(jid, True):
                return {"ok": True, "has_more": False}
            ok = self._mam_fetch(jid, "older",
                                 self._mam_oldest.get(jid) or None)
            return {"ok": ok}
        if cmd == "mark_displayed":
            if bot and self._send_read_receipts and args.get("mid"):
                mtype = "groupchat" if args.get("to") in self.rooms \
                    else "chat"
                bot.send_marker(args["to"], args["mid"], "displayed")
                bot.send_chatstate(args["to"], "active", mtype)
            return {"ok": True}
        if cmd == "correct":
            if bot:
                mtype = "groupchat" if args.get("to") in self.rooms else "chat"
                bot.send_correction(args["to"], args["body"], args["mid"],
                                    mtype)
                self._mutate_entry(args["to"], args["mid"], args["body"])
                _storage._db_update_msg_body(args["to"], args["mid"],
                                             args["body"])
                self._broadcast({"ev": "corrected",
                                 "data": {"jid": args["to"],
                                          "mid": args["mid"],
                                          "body": args["body"]}})
            return {"ok": True}
        if cmd == "retract":
            to, mid = args.get("to"), args.get("mid")
            if bot and to and mid:
                mtype = "groupchat" if to in self.rooms else "chat"
                bot.retract_message(to, mid, mtype)
                if self._mutate_entry(to, mid, RETRACTED_BODY):
                    _storage._db_update_msg_body(to, mid, RETRACTED_BODY)
                    _storage._db_clear_reactions_mid(to, mid)
                self._broadcast({"ev": "corrected",
                                 "data": {"jid": to, "mid": mid,
                                          "body": RETRACTED_BODY}})
            return {"ok": True}
        if cmd == "react":
            return self._cmd_react(args)
        if cmd == "join_room":
            ok = self.join_room(args.get("room"), args.get("nick"))
            return {"ok": ok, "error": "" if ok else
                    _tr("Geçersiz oda adresi ya da bağlantı yok.")}
        if cmd == "leave_room":
            self.leave_room(args.get("room", ""))
            return {"ok": True}
        if cmd == "discover_rooms":
            return {"ok": self.discover_rooms()}
        if cmd == "set_presence":
            if bot:
                bot.set_presence(args.get("show", "online"),
                                 args.get("status", ""))
            return {"ok": True}
        if cmd == "approve_subscribe":
            if bot:
                bot.approve_subscribe(args.get("jid", ""),
                                      bool(args.get("approve", True)))
            return {"ok": True}
        if cmd == "set_enc":
            self.enc_modes[args.get("jid", "")] = \
                "omemo" if args.get("mode") == "omemo" else "none"
            return {"ok": True}
        if cmd == "refresh_settings":
            cfg = _load_config()
            self._send_read_receipts = bool(cfg.get("send_read_receipts",
                                                    True))
            self._send_typing = bool(cfg.get("send_typing", True))
            self._leak_guard = bool((cfg.get("ai") or {}).get("leak_guard",
                                                              True))
            return {"ok": True}
        return {"ok": False, "error": _tr("Bilinmeyen komut: {}").format(cmd)}

    def _cmd_send(self, args) -> dict:
        to = (args.get("to") or "").strip()
        body = (args.get("body") or "").strip()
        if not to or not body:
            return {"ok": False, "error": _tr("Boş mesaj.")}
        if self.bot is None:
            return {"ok": False, "error": _tr("Bağlı değil")}
        enc = args.get("enc") or self.enc_modes.get(to, "none")
        if not args.get("force") and enc == "none" and self._leak_guard:
            findings = _sensitive.scan(body)
            if findings:
                return {"ok": False, "leak": True, "findings": [
                    {"kind": f.kind, "label": f.label, "sample": f.sample}
                    for f in findings]}
        reply = args.get("reply_to") or None
        mid = _new_msg_id()
        self._store(to, body, tag="me", sender="Ben", is_me=True,
                    encrypted=enc != "none", mid=mid, reply_to=reply)
        mtype = "groupchat" if to in self.rooms else "chat"
        if reply:
            self.bot.send_reply(to, body, reply["id"],
                                reply.get("body", ""), mtype, enc, mid=mid,
                                reply_to_jid=reply.get("to"))
        elif mtype == "groupchat":
            self.bot.send_gc(to, body, encryption=enc, mid=mid)
        else:
            self.bot.send_chat(to, body, encryption=enc, mid=mid)
        if self._send_typing:
            self.bot.send_chatstate(to, "active", mtype)
        entry = {"to": to, "body": body, "mid": mid, "enc": enc,
                 "reply": reply, "ts": datetime.now().strftime("%H:%M")}
        self._broadcast({"ev": "own_sent", "data": entry})
        return {"ok": True, "mid": mid}

    def _cmd_react(self, args) -> dict:
        to, mid = args.get("to"), args.get("mid")
        emojis = set(args.get("emojis") or [])
        if not (self.bot and to and mid):
            return {"ok": False, "error": _tr("Eksik tepki hedefi.")}
        mtype = "groupchat" if to in self.rooms else "chat"
        self.bot.send_reaction(to, mid, emojis, mtype)
        # Kendi tepkilerim: eski kümemi sil, yenisini yaz (MainWindow ile aynı)
        cur = self.reactions_map(to).setdefault(mid, {})
        for emoji, senders in list(cur.items()):
            if "Ben" in senders:
                _storage._db_save_reaction(to, mid, emoji, "Ben", add=False)
                senders.remove("Ben")
                if not senders:
                    del cur[emoji]
        for emoji in emojis:
            _storage._db_save_reaction(to, mid, emoji, "Ben", add=True)
            cur.setdefault(emoji, []).append("Ben")
        self._broadcast({"ev": "msg_reactions",
                         "data": {"from": to, "nick": "Ben",
                                  "target_id": mid, "reactions": cur}})
        return {"ok": True}

    # ── Anlık görüntü (WS hello) ve geçmiş ───────────────────────────────────
    def snapshot(self) -> dict:
        contacts = []
        for jid, name in self.contacts.items():
            contacts.append({
                "jid": jid, "name": name,
                "presence": self.presence.get(jid, {}),
                "unread": self.unread.get(jid, 0),
                "room": jid in self.rooms,
                "members": self.members.get(jid, {}),
                "subject": self.subjects.get(jid, ""),
                "enc": self.enc_modes.get(jid, "none"),
                "typing": self.typing.get(jid, False),
            })
        return {"jid": self.jid, "contacts": contacts,
                "unread_total": sum(self.unread.values())}

    def history(self, jid: str, before: tuple | None = None,
                limit: int = 60) -> dict:
        rows = _storage._db_load_msgs_full(jid, limit=limit, before=before)
        reactions = self.reactions_map(jid)
        msgs = [{"id": r[0], "sender": r[1] or jid, "body": r[2],
                 "is_me": r[3], "ts": r[4], "tag": r[5], "oob": r[6],
                 "encrypted": r[7], "mid": r[9],
                 "stored_at": r[13],
                 "reply": ({"id": r[10], "sender": r[11], "body": r[12]}
                           if r[10] else None),
                 "reactions": reactions.get(r[9], {})} for r in rows]
        return {"jid": jid, "messages": msgs,
                "has_more": len(msgs) == limit}
