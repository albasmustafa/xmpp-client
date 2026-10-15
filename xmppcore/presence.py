"""Presence ve abonelik olayları (Faz 2: XMPPBot PresenceMixin).

Bu modül yalnızca XMPPBot'a karışan (mixin) metotları içerir; state
XMPPBot örneğinde kalır. Event adları, gui_q payload'ları ve iş mantığı
xmpp.py'deki taşınmadan önceki haliyle birebir aynıdır.
"""


class PresenceMixin:
    """Presence, durum bildirimi ve abonelik istekleri."""

    # ── Presence ──────────────────────────────────────────────────────────────
    def _on_presence(self, presence):
        self.gui_q.put(("presence", {
            "jid":   str(presence["from"].bare),
            "ptype": presence["type"],
            "pshow": presence.get("show", ""),
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
