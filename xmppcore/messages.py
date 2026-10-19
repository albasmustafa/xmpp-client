"""1:1 mesaj işleme ve mesaj gönderme (Faz 2: XMPPBot MessagesMixin).

XEP'ler: 0308 (düzeltme), 0424 (silme), 0444 (tepki), 0333/0085
(marker/chatstate), 0461 (yanıt), 0066 (OOB). OMEMO/PGP gönderim
metotları (_send_omemo/_send_pgp) ve _decrypt_and_deliver bilinçli olarak
xmpp.py'de bırakılmıştır; bu mixin onları self üzerinden çağırır.

Event adları ve gui_q payload'ları taşınmadan önceki haliyle birebir aynıdır.
"""
import asyncio
import xml.etree.ElementTree as ET

from xmppcore.constants import _log
from xmppcore.format import _forward_body, _reply_preview
from xmppcore.helpers import (
    _CORRECTION,
    _DISPLAYED,
    _OMEMO_TAGS,
    _REACTIONS,
    _RETRACTS,
    _add_origin_id,
    _get_xep,
    _has_child,
    _spawn_task,
    _stanza_msg_id,
    _strip_quoted_fallback,
)


class MessagesMixin:
    """1:1 mesaj alma/gönderme, düzeltme, silme, tepki ve yanıt işlemleri."""

    # ── Mesajlar ──────────────────────────────────────────────────────────────
    def _reply_info(self, msg) -> dict | None:
        """Gelen XEP-0461 yanıtını çöz: {id, to, sender, body(önizleme)}."""
        try:
            reply = msg["reply"]
            target = str(reply["id"] or "")
        except Exception:
            return None
        if not target:
            return None
        preview = ""
        try:
            preview = _reply_preview(reply.get_fallback_body())
        except Exception:
            pass
        to = ""
        try:
            to = str(reply["to"] or "")
        except Exception:
            pass
        if "/" in to:
            sender = to.split("/")[-1]
        elif to:
            sender = to.split("@")[0]
        else:
            sender = ""
        return {"id": target, "to": to, "sender": sender, "body": preview}

    def _on_message(self, msg):
        if msg["type"] not in ("chat", "normal"):
            return
        # PGP şifreli mi? → _on_pgp_message zaten işliyor, burada atla
        if msg.xml.find("{jabber:x:encrypted}x") is not None:
            return
        # Geri çekmenin kendi olayı var (message_retract); mobil istemcilerin
        # eklediği yedek gövde ("…attempted to retract…") mesaj değildir
        if _has_child(msg.xml, *_RETRACTS):
            return
        # Düz düzeltmeyi message_correction işler; şifreli düzeltme aşağıda
        # çözülür ve düzeltme olarak iletilir (_decrypt_and_deliver)
        is_correction = _has_child(msg.xml, _CORRECTION)
        # OMEMO şifreli mi kontrol et
        encrypted = False
        if self._omemo_enabled():
            try:
                xep = _get_xep(self, "xep_0384")
                if xep.is_encrypted(msg):
                    _spawn_task(self, self._decrypt_and_deliver(msg, "chat"))
                    return
            except Exception as e:
                # [2P-BUG B] Yutulan except yerine observable log: şifreli
                # mesaj sessizce düşmeyecek; hassas materyal sızdırılmaz.
                _log.warning("OMEMO şifreli-mesaj denetimi başarısız: %s", e)
        if is_correction:
            return
        if msg["body"]:
            oob = self._extract_oob(msg)
            self.gui_q.put(("msg", {
                "from": str(msg["from"].bare),
                "nick": str(msg["from"].user),
                "body": _strip_quoted_fallback(msg, msg["body"]),
                "type": "chat",
                "oob":  oob,
                "encrypted": encrypted,
                "mid": _stanza_msg_id(msg),
                "reply": self._reply_info(msg),
            }))
        else:
            # [2P-BUG B] Şifreli gövde işlenememişse sessiz kayıp yerine
            # observable bildirim (OMEMO hazır değilken gelen ilk mesajlar).
            try:
                if msg.xml.find(
                        "{eu.siacs.conversations.axolotl}encrypted") is not None:
                    self.gui_q.put(("sys_msg",
                        "⚠ OMEMO mesajı alındı ancak OMEMO hazır değil — "
                        "çözülemedi"))
            except Exception:
                pass

    # ── Carbons (XEP-0280): aynı hesabın diğer cihazları ──────────────────────
    # slixmpp, kopyanın kendi hesabımızdan geldiğini doğrulamadan olayı
    # tetiklemez (sahte carbon koruması: xep_0280._handle_carbon_*).
    def _on_carbon_received(self, msg):
        """Başka cihazımıza (ör. telefondaki Monocles) gelen mesajın kopyası:
        normal gelen mesaj gibi işlenir (OMEMO dahil)."""
        inner = msg["carbon_received"]
        if str(inner["from"].bare) in getattr(self, "my_nicks", {}):
            return          # oda özel mesajı (MUC PM): oda akışında değil
        # Düzeltme/geri çekme/tepki yeni mesaj değildir: kendi işleyicisine
        xml = inner.xml
        if _has_child(xml, _CORRECTION):
            self._on_message_correction(inner)
            if _has_child(xml, *_OMEMO_TAGS):
                self._on_message(inner)     # şifreli düzeltme: çözülüp uygulanır
        elif _has_child(xml, *_RETRACTS):
            self._on_message_retract(inner)
        elif _has_child(xml, _REACTIONS):
            self._on_reactions(inner)
        else:
            self._on_message(inner)

    def _on_carbon_sent(self, msg):
        """Başka cihazımızdan gönderilen mesajın kopyası: bizim mesajımız
        olarak gösterilir, böylece iki cihaz da aynı sohbeti görür."""
        inner = msg["carbon_sent"]
        if inner["type"] not in ("chat", "normal"):
            return
        to = str(inner["to"].bare)
        if (not to or to == str(self.boundjid.bare)
                or to in getattr(self, "my_nicks", {})):
            return
        xml = inner.xml
        if _has_child(xml, _DISPLAYED):
            # Telefonda okundu → masaüstünde de okunmamış kalmasın
            self.gui_q.put(("read_elsewhere", to))
            return
        # Telefondaki geri çekme/tepki/düzeltme yeni mesaj değildir: o kişinin
        # sohbetindeki kendi mesajımıza uygulanır (own_to=kişi)
        if _has_child(xml, *_RETRACTS):
            self._on_message_retract(inner, own_to=to)
            return
        if _has_child(xml, _REACTIONS):
            self._on_reactions(inner, own_to=to)
            return
        if xml.find("{jabber:x:encrypted}x") is not None:
            return          # PGP kopyası kendi anahtarımızla çözülemez
        if self._omemo_enabled():
            try:
                xep = _get_xep(self, "xep_0384")
                if xep.is_encrypted(inner):
                    # Şifreli düzeltme de buradan: çözülüp uygulanır
                    _spawn_task(self, self._decrypt_and_deliver(
                        inner, "chat", own_to=to))
                    return
            except Exception as e:
                _log.warning("OMEMO şifreli-mesaj denetimi başarısız: %s", e)
        if _has_child(xml, _CORRECTION):
            self._on_message_correction(inner, own_to=to)
            return
        if inner["body"]:
            self.gui_q.put(("own_msg", {
                "to": to,
                "body": _strip_quoted_fallback(inner, inner["body"]),
                "oob": self._extract_oob(inner),
                "encrypted": False,
                "mid": _stanza_msg_id(inner),
                "reply": self._reply_info(inner),
            }))

    @staticmethod
    def _extract_oob(msg):
        """XEP-0066 Out-of-Band URL çıkar. None değeri "" olur."""
        try:
            url = msg["oob"]["url"]
            return str(url) if url else ""
        except Exception:
            return ""

    # ── Yazıyor ───────────────────────────────────────────────────────────────
    def _on_typing_start(self, msg):
        self.gui_q.put(("typing", {"jid": str(msg["from"].bare), "active": True}))

    def _on_typing_stop(self, msg):
        self.gui_q.put(("typing", {"jid": str(msg["from"].bare), "active": False}))

    # ── Mesaj gönder (thread-safe) ────────────────────────────────────────────
    def send_chat(self, to, body, encryption="none", mid=None):
        coroutine = self._send_chat(to, body, encryption, mid)
        try:
            return asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        except Exception:
            coroutine.close()
            raise

    async def _send_chat(self, to, body, encryption="none", mid=None):
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
                await self._send_omemo(to, body, "chat", mid=mid)
            elif encryption == "pgp":
                self._send_pgp(to, body, "chat", mid)
            else:
                msg = self.make_message(mto=to, mbody=body, mtype="chat")
                sent_mid = _add_origin_id(msg, mid)
                msg.send()
                self.gui_q.put(("sent_mid", {"to": to, "mid": sent_mid}))
                return True
        except Exception as e:
            self.gui_q.put(("error", f"Mesaj gönderilemedi: {e}"))
            return False

    # ── Mesaj Düzenleme (XEP-0308) ───────────────────────────────────────────
    def send_correction(self, to, new_body, orig_id, mtype="chat"):
        asyncio.run_coroutine_threadsafe(
            self._send_correction(to, new_body, orig_id, mtype), self.loop)

    async def _send_correction(self, to, new_body, orig_id, mtype):
        try:
            correction = _get_xep(self, "xep_0308").build_correction(
                id_to_replace=orig_id, mto=to, mtype=mtype, mbody=new_body)
            correction.send()
        except Exception as e:
            self.gui_q.put(("error", f"Düzenleme hatası: {e}"))

    # ── Mesaj Silme (XEP-0424) ───────────────────────────────────────────────
    def retract_message(self, to, msg_id, mtype="chat"):
        asyncio.run_coroutine_threadsafe(
            self._retract_message(to, msg_id, mtype), self.loop)

    async def _retract_message(self, to, msg_id, mtype):
        try:
            _get_xep(self, "xep_0424").send_retraction(
                mto=to, id=msg_id, mtype=mtype)
        except Exception as e:
            self.gui_q.put(("error", f"Silme hatası: {e}"))

    # ── Tepkiler (XEP-0444) ─────────────────────────────────────────────────
    def send_reaction(self, to, msg_id, emojis, mtype="chat"):
        """Tam tepki kümesini gönder (boş küme = tümünü geri çek).

        slixmpp'nin send_reactions'ı mesaj tipini ayarlamadığı için
        özellikle MUC'da 'groupchat' tipini kendimiz kuruyoruz.
        """
        def _do():
            try:
                xep = _get_xep(self, "xep_0444")
                msg = self.make_message(mto=to, mtype=mtype)
                xep.set_reactions(msg, msg_id, emojis)
                msg.enable("store")
                msg.send()
            except Exception as e:
                self.gui_q.put(("error", f"Tepki hatası: {e}"))
        self._dispatch_loop(_do)

    # ── Chat Markers / Okundu (XEP-0333) ────────────────────────────────────
    def send_chatstate(self, to, state="composing", mtype="chat"):
        """Yazıyor / durdu bildirimi gönder (XEP-0085)."""
        def _do():
            try:
                msg = self.make_message(mto=to, mtype=mtype)
                msg["chat_state"] = state
                msg.send()
            except Exception:
                pass
        self._dispatch_loop(_do)

    def send_marker(self, to, msg_id, marker_type="displayed"):
        """marker_type: received, displayed, acknowledged"""
        def _do():
            try:
                xep = _get_xep(self, "xep_0333")
                xep.send_marker(mto=to, id=msg_id, marker=marker_type)
            except Exception:
                pass
        self._dispatch_loop(_do)

    def _on_marker_displayed(self, msg):
        """Karşı taraf mesajımızı okudu."""
        frm = str(msg["from"].bare)
        try:
            mid = msg["displayed"]["id"]
        except Exception:
            mid = ""
        if mid:
            self.gui_q.put(("marker_displayed", {"from": frm, "mid": mid}))

    def _on_message_correction(self, msg, own_to=None):
        """Gelen mesaj düzeltmesi (XEP-0308). OMEMO'lu düzeltmenin gövdesi
        yalnız yedek metindir: çözülünce _decrypt_and_deliver iletir.
        `own_to`: başka cihazımızda yapılmış düzeltme (carbon), o sohbete."""
        if _has_child(msg.xml, *_OMEMO_TAGS):
            return
        frm = own_to or str(msg["from"].bare)
        orig_id = ""
        try:
            orig_id = msg["replace"]["id"]
        except Exception:
            pass
        body = msg["body"] or ""
        if orig_id and body:
            self.gui_q.put(("msg_correction", {
                "from": frm,
                "orig_id": orig_id,
                "body": body,
                "nick": ("Ben" if own_to
                         else str(msg["from"].resource or msg["from"].user)),
            }))

    def _on_message_retract(self, msg, own_to=None):
        """Gelen mesaj silme (XEP-0424). `own_to`: bkz. düzeltme."""
        frm = own_to or str(msg["from"].bare)
        retracted_id = ""
        try:
            retracted_id = msg["retract"]["id"]
        except Exception:
            pass
        if retracted_id:
            self.gui_q.put(("msg_retract", {
                "from": frm,
                "retracted_id": retracted_id,
            }))

    def _on_reactions(self, msg, own_to=None):
        """Gelen tepkiler (XEP-0444). `own_to`: başka cihazımızdaki kendi
        tepkimiz; masaüstündeki kendi tepkilerimiz gibi "Ben" adıyla."""
        frm = own_to or str(msg["from"].bare)
        nick = "Ben" if own_to else str(msg["from"].resource or msg["from"].user)
        target_id = ""
        emojis = set()
        try:
            target_id = msg["reactions"]["id"]
            emojis = msg["reactions"].get_values(all_chars=True)
        except Exception:
            pass
        if target_id:
            # Boş küme = kullanıcının tüm tepkilerini geri çekmesi (XEP-0444)
            self.gui_q.put(("msg_reactions", {
                "from": frm,
                "nick": nick,
                "target_id": target_id,
                "emojis": list(emojis),
            }))

    # ── Yanıtlama (XEP-0461 Message Replies) ─────────────────────────────────
    def send_reply(self, to, body, reply_to_id, reply_to_body, mtype="chat",
                   encryption="none", mid=None, reply_to_jid=None):
        """Bir mesajı alıntılayarak yanıtla."""
        asyncio.run_coroutine_threadsafe(
            self._send_reply(to, body, reply_to_id, reply_to_body, mtype,
                             encryption, mid, reply_to_jid), self.loop)

    async def _send_reply(self, to, body, reply_to_id, reply_to_body, mtype,
                          encryption, mid=None, reply_to_jid=None):
        try:
            if encryption == "omemo" and self._omemo_enabled() and self.omemo_ready:
                await self._send_omemo(to, body, mtype,
                                       reply_id=reply_to_id,
                                       reply_body=reply_to_body, mid=mid,
                                       reply_to_jid=reply_to_jid)
                return
            quoted_jid = reply_to_jid or to
            msg = None
            try:
                xep = _get_xep(self, "xep_0461")
                msg = xep.make_reply(quoted_jid, reply_to_id,
                                     fallback=reply_to_body or None,
                                     quoted_nick=None,
                                     mto=to, mbody=body, mtype=mtype)
            except Exception:
                msg = None
            if msg is None:
                # XEP-0461 + XEP-0428 elle (eklenti yoksa)
                msg = self.make_message(mto=to, mbody=body, mtype=mtype)
                reply_el = ET.SubElement(msg.xml, "{urn:xmpp:reply:0}reply")
                reply_el.set("to", quoted_jid)
                reply_el.set("id", reply_to_id)
                fallback = ET.SubElement(msg.xml,
                                         "{urn:xmpp:fallback:0}fallback")
                fallback.set("for", "urn:xmpp:reply:0")
                if reply_to_body:
                    ET.SubElement(fallback, "body").text = reply_to_body[:200]
            sent_mid = _add_origin_id(msg, mid)
            msg.send()
            self.gui_q.put(("sent_mid", {"to": to, "mid": sent_mid}))
        except Exception as e:
            self.gui_q.put(("error", f"Yanıt hatası: {e}"))

    # ── Mesaj İletme ──────────────────────────────────────────────────────────
    def forward_message(self, to, orig_from, orig_body, mtype="chat",
                        encryption="none", mid=None):
        """Bir mesajı başka birine ilet. Şifreleme hedef sohbetinkidir:
        OMEMO/PGP'de normal şifreli gönderim yolu (send_chat/send_gc) kullanılır;
        düz iletim eskisi gibi loop'ta kurulur. `mid` yerel kayıtla aynı
        origin-id'dir (düzenleme/silme ve sent_mid eşlemesi)."""
        body = _forward_body(orig_from, orig_body)
        if encryption in ("omemo", "pgp"):
            send = self.send_gc if mtype == "groupchat" else self.send_chat
            send(to, body, encryption=encryption, mid=mid)
            return

        def _do():
            try:
                msg = self.make_message(mto=to, mbody=body, mtype=mtype)
                _add_origin_id(msg, mid)
                msg.send()
            except Exception as e:
                self.gui_q.put(("error", f"İletme hatası: {e}"))
        self._dispatch_loop(_do)
