"""MUC (çoklu kullanıcı sohbeti) işlemleri (Faz 2: XMPPBot MucMixin).

XEP'ler: 0045 (MUC), 0249 (davet), 0048 (yer imleri). Event adları ve
gui_q payload'ları taşınmadan önceki haliyle birebir aynıdır.
"""
import asyncio

from slixmpp.exceptions import PresenceError

from xmppcore.constants import _log
from xmppcore.helpers import (
    _CORRECTION,
    _RETRACTS,
    _add_origin_id,
    _get_xep,
    _has_child,
    _normalize_room_jid,
    _spawn_task,
    _stanza_msg_id,
    _strip_quoted_fallback,
)

# Oda katılım hatası koşulu → kullanıcıya gösterilen açıklama (XEP-0045 §7.2)
_JOIN_ERRORS = {
    "conflict": "Bu takma ad odada kullanılıyor; başka bir takma ad deneyin.",
    "not-authorized": "Oda parola istiyor.",
    "forbidden": "Bu odaya girişiniz yasaklanmış.",
    "registration-required": "Oda yalnız üyelere açık.",
    "item-not-found": "Oda bulunamadı (adres yanlış ya da oda kilitli olabilir).",
    "remote-server-not-found": "Oda sunucusu bulunamadı (adresi kontrol edin).",
    "service-unavailable": "Oda dolu ya da şu an kullanılamıyor.",
    "not-allowed": "Bu sunucuda yeni oda oluşturma izniniz yok.",
    "jid-malformed": "Geçersiz oda adresi ya da takma ad.",
    "remote-server-timeout": "Oda sunucusuna ulaşılamadı (zaman aşımı).",
    "gone": "Oda taşınmış ya da kaldırılmış.",
    "redirect": "Oda taşınmış ya da kaldırılmış.",
}

# Oda türü → muc#roomconfig alanları (XEP-0045 §10.2). OMEMO odada üyelerin
# gerçek JID'lerini ister (anonim odada gönderim düz metne düşer): şifreli
# oda anonim olmayan (whois=anyone), yalnız üyelere açık ve gizli kurulur.
ROOM_PRESETS = {
    "normal": {
        "muc#roomconfig_persistentroom": True,
        "muc#roomconfig_publicroom": True,
        "muc#roomconfig_membersonly": False,
        "muc#roomconfig_whois": "moderators",
    },
    "encrypted": {
        "muc#roomconfig_persistentroom": True,
        "muc#roomconfig_publicroom": False,
        "muc#roomconfig_membersonly": True,
        "muc#roomconfig_whois": "anyone",
    },
}
_OMEMO_ROOM_FIELDS = ("muc#roomconfig_membersonly", "muc#roomconfig_whois")


def _apply_room_preset(form, kind, name="") -> list:
    """Türün ayarlarını oda formuna yaz; sunucunun sunmadığı alanları döndür.

    `name` oda başlığıdır (adres "sifreli-oda", başlık "Şifreli Oda");
    sunucu başlık alanı sunmuyorsa sorun sayılmaz."""
    missing = []
    fields = form.get_fields()
    if name and "muc#roomconfig_roomname" in fields:
        fields["muc#roomconfig_roomname"]["value"] = name
    for var, value in ROOM_PRESETS[kind].items():
        field = fields.get(var)
        if field is None:
            missing.append(var)
            continue
        if field["type"] == "list-single":
            options = {o["value"] for o in field.get_options()}
            if options and value not in options:
                missing.append(var)
                continue
        field["value"] = value
    return missing


def _room_kind_ok(kind, missing) -> bool:
    """Şifreli oda yalnız OMEMO'nun şart koştuğu alanlar uygulandıysa geçerli."""
    return kind != "encrypted" or not set(_OMEMO_ROOM_FIELDS) & set(missing)


def _status_codes(presence) -> set:
    try:
        return set(presence["muc"]["status_codes"])
    except Exception:
        return set()


def _affiliation(presence) -> str:
    try:
        return presence["muc"]["affiliation"] or ""
    except Exception:
        return ""


class MucMixin:
    """Oda mesajları, oda yaşam döngüsü, yönetim ve yer imleri."""

    muc_service = ""   # XEP-0030 ile bulunan kendi oda sunucumuz (ör. chat.yax.im)
    _JOIN_TIMEOUT = 30          # sunucudan hiç yanıt gelmezse (sn)
    _JOIN_SUBJECT_GRACE = 5     # self-presence sonrası konu için ek süre (sn)

    def _on_gc_message(self, msg):
        # PGP şifreli mi? → _on_pgp_message zaten işliyor
        if msg.xml.find("{jabber:x:encrypted}x") is not None:
            return
        # Geri çekme ve düz düzeltmenin kendi olayları var (messages.py ile
        # aynı kural); şifreli düzeltme çözülünce düzeltme olarak iletilir
        if _has_child(msg.xml, *_RETRACTS):
            return
        is_correction = _has_child(msg.xml, _CORRECTION)
        if not msg["body"] and not self._omemo_enabled():
            return
        # OMEMO şifreli mi kontrol et
        if self._omemo_enabled():
            try:
                xep = _get_xep(self, "xep_0384")
                if xep.is_encrypted(msg):
                    _spawn_task(self, self._decrypt_and_deliver(msg, "groupchat"))
                    return
            except Exception as e:
                # Şifreli oda mesajı sessizce düşmesin (messages.py ile tutarlı)
                _log.warning("OMEMO şifreli-mesaj denetimi başarısız: %s", e)
        if not msg["body"] or is_correction:
            return
        sender = str(msg["from"].resource)
        room   = str(msg["from"].bare)
        own = self._muc_own_message(msg, room, sender)
        if own == "echo":
            return
        oob = self._extract_oob(msg)
        if own == "other":
            self.gui_q.put(("own_msg", {
                "to": room,
                "body": _strip_quoted_fallback(msg, msg["body"]),
                "oob": oob,
                "encrypted": False,
                "mid": _stanza_msg_id(msg),
                "reply": self._reply_info(msg),
            }))
            return
        self.gui_q.put(("msg", {
            "from": room,
            "nick": sender,
            "body": _strip_quoted_fallback(msg, msg["body"]),
            "type": "groupchat",
            "oob":  oob,
            "encrypted": False,
            "mid": _stanza_msg_id(msg),
            "reply": self._reply_info(msg),
        }))

    # ── Aynı hesabın odadaki diğer oturumları ─────────────────────────────────
    def _remember_sent_id(self, stanza):
        """Giden filtre: gönderilen mesajın `id` ve origin-id'sini hatırla.

        OMEMO şifreleme origin-id'yi siler ama `id`'yi korur; ikisi de
        tutulur. Bellek sınırlıdır (XMPPBot._sent_ids, deque)."""
        try:
            if stanza.name == "message" and stanza["type"] == "groupchat":
                for value in (stanza["id"], stanza["origin_id"]["id"]):
                    if value:
                        self._sent_ids.append(str(value))
        except Exception:
            pass
        return stanza

    def _muc_own_message(self, msg, room, sender):
        """Kendi takma adımızla gelen oda mesajını sınıflandır.

        None: başkasının mesajı. "echo": bu istemcinin yansıması, oda geçmişi
        ya da kimliksiz mesaj (eski davranış: atılır). "other": aynı hesabın
        aynı takma adla bağlı başka oturumu (ör. telefondaki Monocles) —
        kimliği var, biz göndermedik ve canlı (gecikmesiz)."""
        if sender != self.my_nicks.get(room, ""):
            return None
        ids = set()
        for get in (lambda: msg["origin_id"]["id"], lambda: msg["id"]):
            try:
                if get():
                    ids.add(str(get()))
            except Exception:
                pass
        sent = getattr(self, "_sent_ids", ())
        if (not ids or any(i in sent for i in ids)
                or msg.xml.find("{urn:xmpp:delay}delay") is not None):
            return "echo"
        return "other"

    # ── MUC presence ──────────────────────────────────────────────────────────
    def _on_muc_presence(self, presence):
        room  = str(presence["from"].bare)
        nick  = str(presence["from"].resource)
        ptype = presence["type"]
        # Role: moderator, participant, visitor, none
        # Affiliation: owner, admin, member, outcast, none
        try:
            role = presence["muc"]["role"] or ""
            affiliation = presence["muc"]["affiliation"] or ""
        except Exception:
            role, affiliation = "", ""
        show = presence.get("show", "") or ""
        self.gui_q.put(("muc_presence", {
            "room":   room,
            "nick":   nick,
            "online": ptype != "unavailable",
            "role":   role,
            "affil":  affiliation,
            "show":   show,
        }))

    def _on_muc_subject(self, msg):
        room = str(msg["from"].bare)
        subject = msg["subject"] or ""
        self.gui_q.put(("muc_subject", {"room": room, "subject": subject}))

    def _on_muc_invite(self, inv):
        """Oda daveti — iki biçim de desteklenir.

        XEP-0249 (doğrudan): oda JID'si <x xmlns='jabber:x:conference'
        jid='...' reason='...'/> içindedir, 'from' davet edendir.
        XEP-0045 (aracılı): mesaj odadan gelir ('from' = oda), sebep
        <x muc#user><invite><reason/></invite></x> içindedir.
        Not: inv["muc"]["jid"] aracılı davette KeyError değil '' döndürür.
        Prosody aracılı davete ayrıca jabber:x:conference ekler (sebep metin
        içeriğinde); bu yüzden önce aracılı biçime bakılır.
        """
        ns = "{http://jabber.org/protocol/muc#user}"
        mediated = inv.xml.find(f"{ns}x/{ns}invite")
        direct = inv.xml.find("{jabber:x:conference}x")
        if mediated is not None:
            room = str(inv["from"].bare)
            node = mediated.find(f"{ns}reason")
            reason = (node.text or "") if node is not None else ""
        elif direct is not None:
            room = direct.get("jid", "")
            reason = direct.get("reason") or (direct.text or "")
        else:
            return
        if not room:
            return
        self.gui_q.put(("muc_invite", {
            "room":   room,
            "reason": reason,
        }))

    # ── Oda mesajı gönder (thread-safe) ──────────────────────────────────────
    def send_gc(self, room, body, encryption="none", mid=None):
        coroutine = self._send_gc(room, body, encryption, mid)
        try:
            return asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        except Exception:
            coroutine.close()
            raise

    async def _send_gc(self, room, body, encryption="none", mid=None):
        try:
            if encryption == "omemo":
                if not self._omemo_enabled():
                    self.gui_q.put(("error",
                        "OMEMO kütüphanesi yüklü değil (slixmpp-omemo)."))
                    return False
                if not self.omemo_ready:
                    self.gui_q.put(("error",
                        "OMEMO henüz hazır değil — lütfen birkaç saniye bekleyin."))
                    return False
                await self._send_omemo(room, body, "groupchat", mid=mid)
            elif encryption == "pgp":
                self._send_pgp(room, body, "groupchat", mid)
            else:
                msg = self.make_message(mto=room, mbody=body, mtype="groupchat")
                sent_mid = _add_origin_id(msg, mid)
                msg.send()
                self.gui_q.put(("sent_mid", {"to": room, "mid": sent_mid}))
                return True
        except Exception as e:
            self.gui_q.put(("error", f"Oda mesajı gönderilemedi: {e}"))
            return False

    # ── Oda yönetimi ──────────────────────────────────────────────────────────
    def discover_rooms(self, server):
        asyncio.run_coroutine_threadsafe(self._discover_rooms(server), self.loop)

    async def _discover_rooms(self, server):
        try:
            result = await _get_xep(self, "xep_0030").get_items(jid=server,
                                                       timeout=10)
            # slixmpp disco öğeleri (jid, node, name) demetidir
            rooms = [(str(jid), name or "")
                     for jid, _node, name in result["disco_items"]["items"]]
            if rooms:
                self.gui_q.put(("rooms_discovered", rooms))
            else:
                # Ayrı olay: açık sohbet yokken de görünür (bkz. MainWindow._handle)
                self.gui_q.put(("rooms_discover_failed",
                    f"'{server}' sunucusunda oda bulunamadi."))
        except Exception as e:
            err = str(e)
            if "remote-server-not-found" in err or "NXDomain" in err:
                reason = "Sunucu bulunamadi (DNS hatasi)"
            elif "service-unavailable" in err:
                reason = "Sunucu kesfetme desteklemiyor"
            elif "timed out" in err.lower() or "timeout" in err.lower():
                reason = "Sunucu yanit vermedi (zaman asimi)"
            elif "not-allowed" in err or "forbidden" in err:
                reason = "Erisim reddedildi"
            else:
                reason = "Baglanti kurulamadi"
            self.gui_q.put(("rooms_discover_failed",
                f"⚠ '{server}': {reason}. "
                f"Genel Ara sekmesini deneyin."))

    async def _find_muc_service(self):
        """Kendi sunucumuzun oda servisini bul (XEP-0045 §6.1 / XEP-0030).

        Sunucunun disco#items öğelerinden `conference/text` kimliğini taşıyan
        ilki seçilir. Bulunamazsa `muc_service` boş kalır ve arayüz eski
        `conference.<domain>` tahminine düşer.
        """
        try:
            infos = await _get_xep(self, "xep_0030").get_info_from_domain(
                timeout=10)
        except Exception as e:
            _log.info("Oda servisi keşfedilemedi: %s", e)
            return
        for iq in infos or ():
            try:
                identities = iq["disco_info"].get_identities()
            except Exception:
                continue
            if any(cat == "conference" and typ == "text"
                   for cat, typ, *_rest in identities):
                self.muc_service = str(iq["from"])
                _log.info("Oda servisi: %s", self.muc_service)
                return

    def join_room(self, room, nick):
        asyncio.run_coroutine_threadsafe(self._join(room, nick), self.loop)

    def create_room(self, room, nick, kind, name=""):
        """Oda oluştur: katıl, sunucu odayı yeni açtıysa `kind`'a göre kur."""
        asyncio.run_coroutine_threadsafe(
            self._join(room, nick, kind, name), self.loop)

    async def _join(self, room, nick, kind=None, name=""):
        try:
            room = _normalize_room_jid(room, self.muc_service)
        except ValueError as e:
            self.gui_q.put(("error", str(e)))
            return
        try:
            muc = _get_xep(self, "xep_0045")
            # Oluşturma: adres doluysa yabancı odaya hiç girilmez
            if kind and await self._room_exists(room):
                self.gui_q.put(("room_taken", {"room": room, "kind": kind}))
                return
            seen = []
            with self.event_handler(f"muc::{room}::self-presence", seen.append):
                await self._await_room_join(muc, room, nick)
            self.my_nicks[room] = nick
            self.gui_q.put(("room_joined", room))
            codes = set().union(*map(_status_codes, seen))
            if not kind and 201 in codes:
                # Odaya Katıl'da yazılan adreste oda yoktu: sunucu yeni ve
                # KİLİTLİ bir oda açtı; yapılandırılmazsa kimse giremez
                await self._unlock_new_room(muc, room)
            if kind:
                owner = any(_affiliation(p) == "owner" for p in seen)
                if 201 in codes:
                    await self._setup_new_room(muc, room, kind, name)
                elif owner:
                    self.gui_q.put(("room_exists", {"room": room, "kind": kind}))
                else:
                    # disco yanıtsız kaldıysa (yarış/sunucu): başkasının odası
                    self.gui_q.put(("room_taken", {"room": room, "kind": kind}))
                    await self._leave(room, nick)
        except asyncio.TimeoutError:
            _log.warning("Oda katılımı başarısız: %s — yanıt yok", room)
            self.gui_q.put(("error",
                f"Oda katılım hatası: {room} {self._JOIN_TIMEOUT} sn içinde "
                "yanıt vermedi; oda sunucusu kapalı ya da adres yanlış "
                "olabilir."))
        except PresenceError as e:
            reason = _JOIN_ERRORS.get(e.condition) or e.text or e.condition
            _log.warning("Oda katılımı başarısız: %s — %s", room, e.condition)
            self.gui_q.put(("error", f"{room} odasına katılınamadı: {reason}"))
        except Exception as e:
            _log.warning("Oda katılımı başarısız: %s — %s", room, e,
                         exc_info=True)
            self.gui_q.put(("error", f"Oda katılım hatası: {e}"))

    async def _await_room_join(self, muc, room, nick):
        """Katılımı bekle; slixmpp `join_muc_wait`'in iki kör noktasını kapat.

        1) Hata yalnız MUC `<x/>` öğesi taşıyorsa tanınır. Oda sunucusu
           bulunamadığında kendi sunucumuzun geri yolladığı hata bu öğeyi
           içermez → genel `presence_error` olayı da dinlenir.
        2) Kendi presence'ımızdan sonra oda konusu zorunlu beklenir. Konu
           her zaman gelmez (zaten odadaysak yeniden gönderilmez) → self-
           presence geldiyse kısa ek süreden sonra katılmış sayılır.
        `join_muc_wait` slixmpp'nin oda kaydını tutmaya devam eder (join_muc
        deprecated; maxchars=9 eski "geçmiş isteme" ayarıdır).
        """
        loop = asyncio.get_running_loop()
        joined = loop.create_future()
        failed = loop.create_future()

        def _on_self(pr):
            if not joined.done():
                joined.set_result(pr)

        def _on_error(pr):
            if str(pr["from"].bare) == room and not failed.done():
                failed.set_result(pr)

        with self.event_handler(f"muc::{room}::self-presence", _on_self), \
                self.event_handler("presence_error", _on_error):
            task = asyncio.ensure_future(muc.join_muc_wait(
                room, nick, maxchars=9, timeout=self._JOIN_TIMEOUT))
            # İptal/yarış sonrası görev istisnası "never retrieved" olmasın
            task.add_done_callback(
                lambda t: t.cancelled() or t.exception())
            try:
                done, _ = await asyncio.wait(
                    {task, joined, failed}, timeout=self._JOIN_TIMEOUT,
                    return_when=asyncio.FIRST_COMPLETED)
                if failed in done:
                    raise PresenceError(failed.result())
                if task in done:
                    return task.result()
                if joined in done:
                    if joined.result()["type"] == "error":
                        raise PresenceError(joined.result())
                    finished, _ = await asyncio.wait(
                        {task, failed}, timeout=self._JOIN_SUBJECT_GRACE,
                        return_when=asyncio.FIRST_COMPLETED)
                    if failed in finished:
                        raise PresenceError(failed.result())
                    if task in finished:
                        return task.result()
                    _log.info("Oda konusu gelmedi, katılım kabul edildi: %s",
                              room)
                    return None
                raise asyncio.TimeoutError()
            finally:
                if not task.done():
                    task.cancel()

    def leave_room(self, room, nick):
        asyncio.run_coroutine_threadsafe(self._leave(room, nick), self.loop)

    async def _leave(self, room, nick):
        try:
            muc = _get_xep(self, "xep_0045")
            result = muc.leave_muc(room, nick)
            if asyncio.iscoroutine(result):
                await result
            self.my_nicks.pop(room, None)
            self.gui_q.put(("room_left", room))
        except Exception as e:
            self.gui_q.put(("error", f"Oda ayrılma hatası: {e}"))

    # ── MUC Yönetim ─────────────────────────────────────────────────────────
    def set_room_subject(self, room, subject):
        """Oda konusunu değiştir."""
        def _do():
            try:
                muc = _get_xep(self, "xep_0045")
                muc.set_subject(room, subject)
            except Exception as e:
                self.gui_q.put(("error", f"Konu değiştirme hatası: {e}"))
        self._dispatch_loop(_do)

    def kick_user(self, room, nick, reason=""):
        asyncio.run_coroutine_threadsafe(
            self._kick_user(room, nick, reason), self.loop)

    async def _kick_user(self, room, nick, reason=""):
        try:
            muc = _get_xep(self, "xep_0045")
            await muc.set_role(room, nick, "none", reason=reason)
            self.gui_q.put(("sys_msg", f"✓ {nick} odadan atıldı."))
        except Exception as e:
            self.gui_q.put(("error", f"Kick hatası: {e}"))

    def ban_user(self, room, jid, reason=""):
        asyncio.run_coroutine_threadsafe(
            self._ban_user(room, jid, reason), self.loop)

    async def _ban_user(self, room, jid, reason=""):
        try:
            muc = _get_xep(self, "xep_0045")
            await muc.set_affiliation(room, "outcast", jid=jid, reason=reason)
            self.gui_q.put(("sys_msg", f"✓ {jid} yasaklandı."))
        except Exception as e:
            self.gui_q.put(("error", f"Ban hatası: {e}"))

    def set_user_role(self, room, nick, role, reason=""):
        asyncio.run_coroutine_threadsafe(
            self._set_user_role(room, nick, role, reason), self.loop)

    async def _set_user_role(self, room, nick, role, reason=""):
        try:
            muc = _get_xep(self, "xep_0045")
            await muc.set_role(room, nick, role, reason=reason)
            self.gui_q.put(("sys_msg", f"✓ {nick} → {role}"))
        except Exception as e:
            self.gui_q.put(("error", f"Rol değiştirme hatası: {e}"))

    def set_user_affiliation(self, room, jid, affiliation, reason=""):
        asyncio.run_coroutine_threadsafe(
            self._set_user_affiliation(room, jid, affiliation, reason), self.loop)

    async def _set_user_affiliation(self, room, jid, affiliation, reason=""):
        try:
            muc = _get_xep(self, "xep_0045")
            await muc.set_affiliation(room, affiliation, jid=jid, reason=reason)
            self.gui_q.put(("sys_msg", f"✓ {jid} → {affiliation}"))
        except Exception as e:
            self.gui_q.put(("error", f"Yetki değiştirme hatası: {e}"))

    def change_nick(self, room, new_nick):
        async def _change():
            try:
                from slixmpp import JID
                muc = _get_xep(self, "xep_0045")
                await muc.set_self_nick(JID(room), new_nick)
                self.my_nicks[room] = new_nick
                self.gui_q.put(("sys_msg", f"✓ Takma adın değişti: {new_nick}"))
            except Exception as e:
                self.gui_q.put(("error", f"Takma ad değiştirilemedi: {e}"))
        asyncio.run_coroutine_threadsafe(_change(), self.loop)

    def invite_to_room(self, room, jid, reason=""):
        def _do():
            try:
                muc = _get_xep(self, "xep_0045")
                muc.invite(room, jid, reason=reason)
                self.gui_q.put(("sys_msg", f"✓ {jid} davet edildi → {room}"))
            except Exception as e:
                self.gui_q.put(("error", f"Davet hatası: {e}"))
        self._dispatch_loop(_do)

    def get_room_config(self, room, callback):
        asyncio.run_coroutine_threadsafe(
            self._get_room_config(room, callback), self.loop)

    async def _get_room_config(self, room, callback):
        try:
            muc = _get_xep(self, "xep_0045")
            form = await muc.get_room_config(room)
            self.gui_q.put(("room_config", {"room": room, "form": form, "cb": callback}))
        except Exception as e:
            self.gui_q.put(("error", f"Oda ayarları alınamadı: {e}"))

    def set_room_config(self, room, form):
        asyncio.run_coroutine_threadsafe(
            self._set_room_config(room, form), self.loop)

    async def _set_room_config(self, room, form):
        try:
            muc = _get_xep(self, "xep_0045")
            await muc.set_room_config(room, form)
            self.gui_q.put(("sys_msg", f"✓ {room} ayarları güncellendi."))
        except Exception as e:
            self.gui_q.put(("error", f"Oda ayar kaydetme hatası: {e}"))

    def destroy_room(self, room, reason=""):
        asyncio.run_coroutine_threadsafe(
            self._destroy_room(room, reason), self.loop)

    async def _destroy_room(self, room, reason=""):
        try:
            muc = _get_xep(self, "xep_0045")
            await muc.destroy(room, reason=reason)
            self.gui_q.put(("sys_msg", f"✓ {room} odası silindi."))
            self.gui_q.put(("room_left", room))
        except Exception as e:
            self.gui_q.put(("error", f"Oda silme hatası: {e}"))

    async def _room_exists(self, room):
        """Adreste oda var mı (disco#info; yoksa sunucu item-not-found döner).

        Belirsiz yanıtta False: katılım sonrası sahiplik denetimi yakalar."""
        try:
            await _get_xep(self, "xep_0030").get_info(jid=room, timeout=10)
            return True
        except Exception:
            return False

    async def _unlock_new_room(self, muc, room):
        """Sunucunun varsayılanlarıyla anında oda (boş submit, §10.1.2)."""
        from slixmpp.plugins.xep_0004.stanza import Form
        try:
            await muc.set_room_config(room, Form())
            self.gui_q.put(("sys_msg",
                f"ℹ {room} adresinde oda yoktu; sunucunun varsayılan "
                "ayarlarıyla yeni bir oda oluşturuldu."))
        except Exception as e:
            self.gui_q.put(("error", f"Yeni oda kullanıma açılamadı: {e}"))

    async def _setup_new_room(self, muc, room, kind, name=""):
        """Sunucunun yeni açtığı (201) odayı türüne göre yapılandır (§10.1).

        Form alınamazsa anında oda (boş submit, §10.1.2) gönderilir ki oda
        kilitli kalmasın; cancel_config yeni odayı YOK EDER (§10.1.3).
        """
        from slixmpp.plugins.xep_0004.stanza import Form
        try:
            form = await muc.get_room_config(room)
            missing = _apply_room_preset(form, kind, name)
        except Exception as e:
            _log.warning("Oda ayar formu alınamadı: %s — %s", room, e)
            form, missing = Form(), list(ROOM_PRESETS[kind])
        try:
            await muc.set_room_config(room, form)
        except Exception as e:
            self.gui_q.put(("error",
                f"Oda yapılandırılamadı (sahibi olarak ⋮ → Oda Yönetimi'ni "
                f"kullanın): {e}"))
            return
        self.gui_q.put(("room_created",
                        {"room": room, "kind": kind, "missing": missing}))

    # ── Yer İmleri (XEP-0048) ────────────────────────────────────────────────
    def get_bookmarks(self, callback):
        asyncio.run_coroutine_threadsafe(
            self._get_bookmarks(callback), self.loop)

    async def _get_bookmarks(self, callback):
        try:
            bm = _get_xep(self, "xep_0048")
            result = await bm.get_bookmarks()
            conferences = []
            for conf in result["private"]["bookmarks"]["conferences"]:
                conferences.append({
                    "jid": str(conf["jid"]),
                    "name": conf.get("name", ""),
                    "nick": conf.get("nick", ""),
                    "autojoin": conf.get("autojoin", False),
                })
            if callback is not None:
                self.gui_q.put(("bookmarks_update",
                                {"bookmarks": conferences, "cb": callback}))
            else:
                self.gui_q.put(("bookmarks", conferences))
        except Exception:
            if callback is not None:
                self.gui_q.put(("bookmarks_update",
                                {"bookmarks": [], "cb": callback}))
            else:
                self.gui_q.put(("bookmarks", []))

    def save_bookmarks(self, bookmarks):
        asyncio.run_coroutine_threadsafe(
            self._save_bookmarks(bookmarks), self.loop)

    async def _save_bookmarks(self, bookmarks):
        try:
            bm = _get_xep(self, "xep_0048")
            bm_stanza = bm.stanza.Bookmarks()
            for b in bookmarks:
                bm_stanza.add_conference(
                    b["jid"], nick=b.get("nick", ""),
                    name=b.get("name", ""),
                    autojoin=b.get("autojoin", False))
            await bm.set_bookmarks(bm_stanza)
            self.gui_q.put(("sys_msg", "✓ Yer imleri kaydedildi"))
        except Exception as e:
            self.gui_q.put(("error", f"Yer imi kaydetme hatası: {e}"))
