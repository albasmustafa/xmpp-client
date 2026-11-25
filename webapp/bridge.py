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

from webapp import media as _media
from xmppcore import canned as _canned
from xmppcore import mds as _mds
from xmppcore import notify_policy as _notify
from xmppcore import sensitive as _sensitive
from xmppcore import spoiler as _spoiler
from xmppcore import storage as _storage
from xmppcore.ai import RETRACTED_BODY, display_text
from xmppcore.config import _load_config, _load_config_cached, _save_config
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
        self._uploads: set[str] = set()           # gönderilmeyi bekleyen geçici dosyalar
        self.connected_at: float | None = None    # ilk "connected" anı
        self.my_show = "online"                   # bildirim kararı (dnd susar)
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
        for path in list(self._uploads):
            _media.discard_temp(path)
        self._uploads.clear()
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
            if not self.sinks:
                # Tarayıcı kapandı: "açık sohbet" yok — gelen mesajlar okundu
                # bildirilmesin, okunmamış sayılsın (sekme yeniden bağlanınca
                # open_chat ile geri gelir).
                self.active = ""

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
            self.connected_at = time.monotonic()    # sunucu zamanlayıcısı
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
            self._note_spoiler(frm, mid, data.get("spoiler"))
            unread_total = 0
            self._readsync().note_incoming(frm, mid, unread=self.active != frm)
            if self.active == frm:
                if mid and self.bot and self._send_read_receipts:
                    self.bot.send_marker(frm, mid, "displayed")
                self._mds_publish(frm, mid)          # diğer cihazlarımız (XEP-0490)
            else:
                self.unread[frm] = self.unread.get(frm, 0) + 1
                unread_total = sum(self.unread.values())
            self._broadcast({"ev": "msg", "data": {**data, "reply": reply,
                                                   "is_unread":
                                                       self.active != frm,
                                                   "unread_total":
                                                       unread_total,
                                                   "notify": self._should_notify(
                                                       frm, body, reply)}})

        elif kind == "own_msg":
            to, body = data["to"], data["body"]
            enc = bool(data.get("encrypted", False))
            reply = self._resolve_reply(data.get("reply"), to)
            self._store(to, body, tag="me", sender="Ben", is_me=True,
                        oob=data.get("oob", ""), encrypted=enc,
                        mid=data.get("mid", ""), reply_to=reply)
            self._note_spoiler(to, data.get("mid", ""), data.get("spoiler"))
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
            self._readsync().clear(data)
            self._broadcast({"ev": "read_elsewhere", "data": {"jid": data}})

        elif kind == "msg_ids":
            # XEP-0490: gelen mesajın sunucu stanza-id'si (okundu eşitleme)
            if self._readsync().note_ids(data["jid"], data["mid"], data["sid"]):
                self._mds_publish(data["jid"], data["mid"])

        elif kind == "mds_displayed":
            self._mds_apply(data["jid"], data["sid"])

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

        elif kind == "file_uploaded":
            self._file_uploaded(data)

        elif kind in ("sys_msg", "error", "disconnected", "conn_failed",
                      "ft_error"):
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
            self._note_spoiler(jid, mid, m.get("spoiler"))
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
            self._readsync().clear(self.active)
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
            if args.get("to") and args.get("mid"):
                self._mds_publish(args["to"], args["mid"])
            if bot and self._send_read_receipts and args.get("mid"):
                mtype = "groupchat" if args.get("to") in self.rooms \
                    else "chat"
                bot.send_marker(args["to"], args["mid"], "displayed")
                bot.send_chatstate(args["to"], "active", mtype)
            return {"ok": True}
        if cmd == "correct":
            if not bot:     # sessizce {"ok": True} dönmek düzeltmeyi kaybettiriyordu
                return {"ok": False, "error": _tr("Bağlı değil")}
            mtype = "groupchat" if args.get("to") in self.rooms else "chat"
            bot.send_correction(args["to"], args["body"], args["mid"], mtype)
            self._mutate_entry(args["to"], args["mid"], args["body"])
            _storage._db_update_msg_body(args["to"], args["mid"], args["body"])
            self._broadcast({"ev": "corrected",
                             "data": {"jid": args["to"], "mid": args["mid"],
                                      "body": args["body"]}})
            return {"ok": True}
        if cmd == "retract":
            to, mid = args.get("to"), args.get("mid")
            if not bot:
                return {"ok": False, "error": _tr("Bağlı değil")}
            if to and mid:
                mtype = "groupchat" if to in self.rooms else "chat"
                bot.retract_message(to, mid, mtype)
                if self._mutate_entry(to, mid, RETRACTED_BODY):
                    _storage._db_update_msg_body(to, mid, RETRACTED_BODY)
                    _storage._db_clear_reactions_mid(to, mid)
                self._broadcast({"ev": "corrected",
                                 "data": {"jid": to, "mid": mid,
                                          "body": RETRACTED_BODY}})
            return {"ok": True}
        if cmd == "send_file":
            return self._cmd_send_file(args)
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
            self.my_show = args.get("show", "online")
            if bot:
                bot.set_presence(self.my_show, args.get("status", ""))
            return {"ok": True}
        if cmd == "set_notify":
            return self._cmd_set_notify(args)
        if cmd == "star":
            return self._cmd_star(args)
        if cmd == "starred":
            return {"ok": True, "items": self._starred_items()}
        if cmd == "get_canned":
            return {"ok": True,
                    "items": _canned.load(_load_config_cached())}
        if cmd == "set_canned":
            return self._cmd_set_canned(args)
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

    # ── Bildirim kontrolü (masaüstüyle aynı kurallar: notify_policy) ────────
    def _should_notify(self, frm, body, reply=None) -> bool:
        """Tarayıcı bu mesaj için bildirim/ses çıkarsın mı? Masaüstündeki
        `MainWindow._should_notify` karşılığı; ayarlar ortak config'tedir."""
        is_room = frm in self.rooms
        nick = ((self.bot.my_nicks.get(frm) if self.bot else "")
                or self.nick_default()) if is_room else ""
        return _notify.should_notify(
            _load_config_cached(), frm, body, is_room=is_room, my_nick=nick,
            my_show=self.my_show,
            reply_sender=(reply or {}).get("sender", ""))

    def _cmd_set_notify(self, args) -> dict:
        """choice: MUTE_CHOICES anahtarı (sessize al), "unmute", "room_all"
        ya da "room_mention". Bütün sekmelere `notify_prefs` yayınlanır."""
        jid = (args.get("jid") or "").strip()
        choice = args.get("choice") or ""
        if "@" not in jid:
            return {"ok": False, "error": _tr("Geçersiz JID")}
        if not (choice in _notify.MUTE_CHOICES
                or choice in ("unmute", "room_all", "room_mention")):
            return {"ok": False,
                    "error": _tr("Geçersiz parametre: {}").format("choice")}
        cfg = _load_config()
        if choice in ("room_all", "room_mention"):
            _notify.set_room_all(cfg, jid, choice == "room_all")
        else:
            _notify.set_mute(cfg, jid, None if choice == "unmute" else choice)
        _save_config(cfg)
        prefs = _notify.snapshot(cfg)
        self._broadcast({"ev": "notify_prefs", "data": prefs})
        return {"ok": True, "prefs": prefs}

    # ── ⭐ Yıldızlı mesajlar (masaüstüyle ortak DB: messages.starred) ───────
    def _starred_items(self) -> list:
        """Yeniden eskiye; geri çekilmiş mesaj listelenmez."""
        items = []
        for (jid, sender, body, is_me, ts, stored_at, mid,
             enc) in _storage._db_load_starred(skip_bodies=(RETRACTED_BODY,)):
            chat = (self.contacts.get(jid)
                    or (jid.split("@")[0] if jid in self.rooms else jid))
            items.append({"jid": jid, "mid": mid, "chat": chat,
                          "sender": sender or "", "body": display_text(body or ""),
                          "is_me": bool(is_me), "ts": ts or "",
                          "stored_at": stored_at or "", "encrypted": bool(enc)})
        return items

    def _cmd_star(self, args) -> dict:
        """{jid, mid, on}: yıldızla / yıldızı kaldır; bütün sekmelere `star`."""
        jid = (args.get("jid") or "").strip()
        mid = (args.get("mid") or "").strip()
        if "@" not in jid or not mid:
            return {"ok": False,
                    "error": _tr("Geçersiz parametre: {}").format("mid")}
        on = bool(args.get("on", True))
        if not _storage._db_set_starred(jid, mid, on):
            return {"ok": False,
                    "error": _tr("Bu mesaj yerel geçmişte yok; yıldızlanamadı")}
        self._broadcast({"ev": "star", "data": {"jid": jid, "mid": mid,
                                                "on": on}})
        return {"ok": True, "on": on}

    # ── Okundu eşitleme (XEP-0490 MDS; kurallar xmppcore/mds) ────────────────
    def _readsync(self):
        return self.__dict__.setdefault("_rs", _mds.ReadSync())

    def _mds_publish(self, jid, mid):
        """Sohbeti `mid`'e kadar okuduk: aynı hesabın diğer cihazlarına bildir
        (özel PEP; karşı tarafa gitmez)."""
        sid = self._readsync().publish_sid(jid, mid)
        bot = self.bot
        if sid and bot is not None and hasattr(bot, "mds_flag"):
            bot.mds_flag(jid, sid, room=jid in self.rooms)

    def _mds_apply(self, jid, sid):
        """Başka cihaz sohbeti `sid`'e kadar okudu: sayacı düzelt, tarayıcıya
        bildir (0 → read_elsewhere; kalan varsa unread_update)."""
        count = self._readsync().apply(jid, sid, self.unread.get(jid, 0))
        if count is None:
            return
        if count:
            self.unread[jid] = count
            self._broadcast({"ev": "unread_update",
                             "data": {"counts": {jid: count},
                                      "total": sum(self.unread.values())}})
        else:
            self.unread.pop(jid, None)
            self._broadcast({"ev": "read_elsewhere", "data": {"jid": jid}})

    def _note_spoiler(self, jid, mid, hint):
        """XEP-0382: spoiler'ı DB'ye işle (satır `_store` ile az önce yazıldı)."""
        hint = _spoiler.clean_hint(hint)
        if hint is not None and mid:
            _storage._db_set_spoiler(jid, mid, hint)

    def _cmd_set_canned(self, args) -> dict:
        """💬 Hazır yanıtlar düzenleyicisi: her satır bir yanıt
        (masaüstüyle ortak config "canned_replies")."""
        text = args.get("text")
        if not isinstance(text, str):
            return {"ok": False,
                    "error": _tr("Geçersiz parametre: {}").format("text")}
        cfg = _load_config()
        _canned.set_items(cfg, _canned.parse_editor(text))
        _save_config(cfg)
        return {"ok": True, "items": cfg[_canned.KEY]}

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
        # XEP-0382: yalnız şifresiz sohbette (OMEMO/PGP yollarına dokunulmaz)
        spoiler = _spoiler.clean_hint(args.get("spoiler"))
        if spoiler is not None and enc != "none":
            return {"ok": False,
                    "error": _tr("Şifreli sohbette gizli içerik gönderilemez")}
        extra = {"spoiler": spoiler} if spoiler is not None else {}
        mid = _new_msg_id()
        self._store(to, body, tag="me", sender="Ben", is_me=True,
                    encrypted=enc != "none", mid=mid, reply_to=reply)
        self._note_spoiler(to, mid, spoiler)
        mtype = "groupchat" if to in self.rooms else "chat"
        if reply:
            self.bot.send_reply(to, body, reply["id"],
                                reply.get("body", ""), mtype, enc, mid=mid,
                                reply_to_jid=reply.get("to"), **extra)
        elif mtype == "groupchat":
            self.bot.send_gc(to, body, encryption=enc, mid=mid, **extra)
        else:
            self.bot.send_chat(to, body, encryption=enc, mid=mid, **extra)
        if self._send_typing:
            self.bot.send_chatstate(to, "active", mtype)
        entry = {"to": to, "body": body, "mid": mid, "enc": enc,
                 "reply": reply, "ts": datetime.now().strftime("%H:%M"),
                 **extra}
        self._broadcast({"ev": "own_sent", "data": entry})
        return {"ok": True, "mid": mid}

    def _cmd_send_file(self, args) -> dict:
        """Geçici dosyayı (webapp.media.write_temp) HTTP Upload ile gönder.

        OMEMO'lu sohbette şifreli yüklenir (aesgcm://); PGP gibi web'in
        bilmediği bir modda düz yüklemeye düşülmez. Dosya, yükleme bitince
        (file_uploaded) ya da on dakika sonra silinir.
        """
        to = (args.get("to") or "").strip()
        path = args.get("path") or ""
        if not to or not _media.is_own_temp(path):
            # Yalnız /api/upload'un yazdığı geçici dosya: WS komutu keyfi
            # yerel yol (ör. ~/.ssh/…) gönderemez.
            return {"ok": False, "error": _tr("Dosya bulunamadı.")}
        if self.bot is None:
            _media.discard_temp(path)
            return {"ok": False, "error": _tr("Bağlı değil")}
        enc = self.enc_modes.get(to, "none")
        if enc not in ("none", "omemo"):
            _media.discard_temp(path)
            return {"ok": False, "error": _tr(
                "Bu şifreleme modunda dosya web arayüzünden gönderilemez.")}
        self._uploads.add(path)
        timer = threading.Timer(600, self._forget_upload, args=(path,))
        timer.daemon = True
        timer.start()
        self.bot.upload_file(path, to, encrypt=enc == "omemo")
        return {"ok": True}

    def _forget_upload(self, path):
        self._uploads.discard(path)
        _media.discard_temp(path)

    def _file_uploaded(self, data):
        """Yükleme bitti: masaüstüyle aynı biçimde kaydet ve gönder.

        Şifreli dosyanın aesgcm:// bağlantısı yalnız OMEMO'lu gövdede gider
        (OOB'ye yazılmaz: anahtar taşır) — MainWindow._handle ile aynı.
        """
        path = data.get("path") or ""
        if path in self._uploads:
            self._forget_upload(path)
        target = data.get("cb") or ""
        url = data.get("url") or ""
        if not target or not url or self.bot is None:
            return
        encrypted = bool(data.get("encrypted"))
        enc = "omemo" if encrypted else "none"
        oob = "" if encrypted else url
        mid = _new_msg_id()
        self._store(target, url, tag="me", sender="Ben", is_me=True,
                    oob=oob, encrypted=encrypted, mid=mid)
        if target in self.rooms:
            self.bot.send_gc(target, url, encryption=enc, mid=mid)
        else:
            self.bot.send_chat(target, url, encryption=enc, mid=mid)
        self._broadcast({"ev": "own_sent", "data": {
            "to": target, "body": url, "mid": mid, "enc": enc, "oob": oob,
            "reply": None, "ts": datetime.now().strftime("%H:%M")}})

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
        # Odalar roster'da değildir: sayfa yenilenince listeden kaybolmasınlar
        names = dict(self.contacts)
        for room in sorted(self.rooms):
            names.setdefault(room, room.split("@")[0])
        for jid, name in names.items():
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
                "unread_total": sum(self.unread.values()),
                "notify_prefs": _notify.snapshot(_load_config_cached()),
                "starred": [[it["jid"], it["mid"]]
                            for it in self._starred_items()]}

    def history(self, jid: str, before: tuple | None = None,
                limit: int = 60) -> dict:
        rows = _storage._db_load_msgs_full(jid, limit=limit, before=before)
        reactions = self.reactions_map(jid)
        spoilers = _storage._db_load_spoilers(jid)
        msgs = [{"id": r[0], "sender": r[1] or jid, "body": r[2],
                 "is_me": r[3], "ts": r[4], "tag": r[5], "oob": r[6],
                 "encrypted": r[7], "mid": r[9],
                 "stored_at": r[13],
                 "reply": ({"id": r[10], "sender": r[11], "body": r[12]}
                           if r[10] else None),
                 "reactions": reactions.get(r[9], {}),
                 **({"spoiler": spoilers[r[9]]} if r[9] in spoilers else {})}
                for r in rows]
        return {"jid": jid, "messages": msgs,
                "has_more": len(msgs) == limit}
