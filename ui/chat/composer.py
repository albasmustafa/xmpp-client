"""Composer + reply presentation boundary (Faz 4C-4A).

Mevcut ChatShell widget ref'lerini kullanır (duplicate widget/StringVar yok).
Reply transient UI state'inin tek sahibi bu view'dir. Domain/bot/storage/
network/thread/after YOKTUR.
"""


class ComposerView:
    """Reply bar sunumu + entry text primitifleri (mevcut semantik)."""

    def __init__(self, msg_var, msg_entry, reply_bar, reply_lbl):
        self._var = msg_var
        self._entry = msg_entry
        self._bar = reply_bar
        self._lbl = reply_lbl
        self._reply_to = None

    # ── Entry text primitifleri ─────────────────────────────────────────────
    def get_text(self):
        return self._var.get()

    def clear_text(self):
        self._var.set("")

    def insert_text(self, text):
        """Mevcut davranış: metnin sonuna ekler (cursor insert değil)."""
        self._var.set(self._var.get() + text)

    def focus(self):
        try:
            self._entry.focus_set()
        except Exception:
            pass

    # ── Reply transient UI state ────────────────────────────────────────────
    def has_reply(self):
        return bool(self._reply_to)

    def get_reply(self):
        return self._reply_to

    def set_reply(self, reply):
        """reply: {"mid","body","sender","to"} — shape aynen korunur."""
        self._reply_to = reply
        sender = reply.get("sender", "")
        body = reply.get("body", "")
        preview = body[:80] + ("…" if len(body) > 80 else "")
        self._lbl.config(text=f"↩ {sender}: {preview}")
        self._bar.pack(side="top", fill="x",
                       before=self._bar.master.winfo_children()[-1])

    def cancel_reply(self):
        """Idempotent: iki kez çağrılsa da state None + bar gizli."""
        self._reply_to = None
        self._bar.pack_forget()

    def consume_reply(self):
        """Reply'ı döndür ve yan etkisi olmadan temizle (yoksa None)."""
        reply = self._reply_to
        if reply:
            self.cancel_reply()
        return reply
