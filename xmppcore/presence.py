"""Presence ve abonelik olayları (Faz 2: XMPPBot PresenceMixin).

Bu modül yalnızca XMPPBot'a karışan (mixin) metotları içerir; state
XMPPBot örneğinde kalır. Event adları, gui_q payload'ları ve iş mantığı
xmpp.py'deki taşınmadan önceki haliyle birebir aynıdır.
"""


class PresenceMixin:
    """Presence, durum bildirimi ve abonelik istekleri."""

    # Birden çok cihazdan en "müsait" olanı gösterilir (küçük = daha müsait)
    _SHOW_RANK = {"chat": 0, "": 1, "away": 2, "xa": 3, "dnd": 4}

    # ── Presence ──────────────────────────────────────────────────────────────
    def _on_presence(self, presence):
        """Kişinin durumunu tüm cihazlarından (kaynaklarından) birleştir.

        slixmpp kaynak listesini olaydan önce günceller. Bir cihaz (ör.
        bilgisayardaki istemci) çevrimdışı olunca telefon (Monocles) hâlâ
        bağlıysa kişi çevrimiçi kalır; en müsait cihazın durumu gösterilir."""
        bare = str(presence["from"].bare)
        ptype, pshow = presence["type"], presence.get("show", "")
        try:
            resources = self.client_roster[bare].resources
        except Exception:
            resources = {}
        if resources:
            best = min(resources.values(),
                       key=lambda r: self._SHOW_RANK.get(r.get("show") or "", 1))
            ptype, pshow = "available", best.get("show") or ""
        self.gui_q.put(("presence", {
            "jid":   bare,
            "ptype": ptype,
            "pshow": pshow,
        }))

    # ── Subscription ──────────────────────────────────────────────────────────
    def _on_subscribe_req(self, presence):
        self.gui_q.put(("subscribe_req", str(presence["from"].bare)))

    def _on_subscribed(self, presence):
        self.gui_q.put(("sys_msg", f"✓ {presence['from'].bare} isteği kabul etti"))

    def _on_unsubscribed(self, presence):
        self.gui_q.put(("sys_msg", f"✗ {presence['from'].bare} sizi kaldırdı"))

    def set_presence(self, show, status=""):
        def _do():
            if show == "online":
                self.send_presence(pstatus=status)
            else:
                self.send_presence(pshow=show, pstatus=status)
        self._dispatch_loop(_do)

    def approve_subscribe(self, jid, approve: bool):
        ptype = "subscribed" if approve else "unsubscribed"
        self._dispatch_loop(
            lambda: self.send_presence_subscription(pto=jid, ptype=ptype))
