"""MAM mesaj arşivi (Faz 2: XMPPBot ArchiveMixin, XEP-0313).

Event adı ('mam_results') ve payload formatı taşınmadan önceki haliyle
birebir aynıdır.
"""
import asyncio

from xmppcore.helpers import _get_xep, _stanza_is_encrypted, _stanza_msg_id


class ArchiveMixin:
    """MAM arşiv çekme (sayfalama dahil)."""

    # ── MAM — Mesaj Arşivi (XEP-0313) ───────────────────────────────────────
    def fetch_mam(self, jid, max_msgs=50, before=None, token=None):
        asyncio.run_coroutine_threadsafe(
            self._fetch_mam(jid, max_msgs, before, token), self.loop)

    async def _fetch_mam(self, jid, max_msgs=50, before=None, token=None):
        """MAM arşivini çek. before verilirse o stanza id'sinden öncesini getirir.

        token: istek sahibinin (GUI) generation değeri; sonuçla geri yankılanır.
        """
        try:
            mam = _get_xep(self, "xep_0313")
            # Oda arşivi odanın kendisinde tutulur (jid=oda; takma adımız
            # my_nicks'te odaya katılınca yazılır); 1:1 arşiv kendi
            # hesabımızdadır ve with= ile süzülür.
            is_room = jid in (getattr(self, "my_nicks", None) or {})
            if is_room:
                target = {"jid": jid}
            else:
                target = {"with_jid": jid}
            if before:
                results = await mam.retrieve(
                    **target, rsm={"max": max_msgs, "before": before}, timeout=15)
            else:
                # Son sayfa = boş <before/>. slixmpp rsm sözlüğündeki değerleri
                # str() ile yazar: before=True "<before>True</before>" olur ve
                # sunucu item-not-found döner. Boş <before/> yalnız RSM
                # yineleyicisinde (reverse=True) doğru kodlanır.
                pages = mam.retrieve(**target, rsm={"max": max_msgs},
                                     iterator=True, reverse=True)
                try:
                    results = await asyncio.wait_for(pages.next(), 15)
                except StopAsyncIteration:
                    results = {"mam": {"results": []}}
            messages = []
            for msg in results["mam"]["results"]:
                fwd = msg["mam_result"]["forwarded"]
                m = fwd["stanza"]
                delay = fwd.get("delay", {})
                ts = str(delay.get("stamp", "")) if delay else ""
                body = m.get("body", "")
                if not body:
                    if _stanza_is_encrypted(getattr(m, "xml", None)):
                        body = "🔒 Şifreli mesaj (arşivde çözülemedi)"
                    else:
                        continue
                frm = str(m["from"].bare) if hasattr(m["from"], "bare") else str(m["from"])
                try:
                    resource = str(m["from"].resource or "")
                except Exception:
                    resource = ""
                # 1:1'de yön: gönderen bizim bare JID'imiz. Odada yön:
                # resource (takma ad) bizim takma adımız mı — MAM'daki
                # forwarded stanza from=oda/takma-ad gelir.
                if is_room:
                    is_me = (bool(resource)
                             and resource == self.my_nicks.get(jid, ""))
                else:
                    is_me = frm == str(self.boundjid.bare)
                # [2N] ÜÇ AYRI kimlik (birbirine karıştırılmaz):
                # logical_mid: _stanza_msg_id (origin-id → stanza-id → id) —
                #   self.chats[*][7]'ye depolanan kanonik kimlik (tepkiler,
                #   yanıtlar, Policy C ile uyumlu);
                # raw_id: ham stanza id — sunucu MAM'a stanza-id eklediğinde
                #   live/mid karışmasını kapatmak için YALNIZ dedupe sırasında
                #   kullanılan geçici korelasyon alias'ı;
                # archive_id: MAM/RSM taşıma üstverisi — YALNIZ imleç
                #   (_mam_oldest/before=) olarak kullanılır; asla mesaj
                #   kimliği/dedupe alias'ı değildir.
                logical_mid = _stanza_msg_id(m)
                try:
                    raw_id = str(m["id"] or "")
                except Exception:
                    raw_id = ""
                try:
                    archive_id = str(msg["mam_result"]["id"] or "")
                except Exception:
                    archive_id = ""
                item = {
                    "from": frm,
                    "body": body,
                    "ts": ts,
                    "is_me": is_me,
                    "mid": logical_mid,
                }
                # Odada gönderenin adı resource'tadır; boş anahtar eklenmez.
                if resource:
                    item["nick"] = resource
                # Uyumluluk: mevcut exact-payload testleri boş anahtarların
                # yokluğunu varsaydığından yalnız boş OLmayan alanlar eklenir.
                if raw_id:
                    item["raw_id"] = raw_id
                if archive_id:
                    item["archive_id"] = archive_id
                messages.append(item)
            self.gui_q.put(("mam_results", {"jid": jid, "messages": messages,
                                            "token": token}))
        except Exception as e:
            self.gui_q.put(("mam_results", {"jid": jid, "messages": [],
                             "error": str(e), "token": token}))
