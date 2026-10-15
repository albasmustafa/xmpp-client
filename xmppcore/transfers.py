"""HTTP dosya yükleme ve OOB transfer yardımcıları.

Faz 2: XMPPBot TransferMixin (XEP-0363). Jingle (XEP-0234) yönetimi
bilinçli olarak jingle_ft.py + xmpp.py'de bırakılmıştır.
Event adları ve gui_q payload'ları birebir korunmuştur.
"""
import asyncio
import os

from xmppcore.helpers import _get_xep


class TransferMixin:
    """HTTP Upload (XEP-0363) ile dosya yükleme/gönderme."""

    # ── HTTP File Upload (XEP-0363) ──────────────────────────────────────────
    def upload_file(self, filepath, callback):
        asyncio.run_coroutine_threadsafe(
            self._upload_file(filepath, callback), self.loop)

    async def _upload_file(self, filepath, callback):
        try:
            upload = _get_xep(self, "xep_0363")
            url = await upload.upload_file(filepath, timeout=60)
            self.gui_q.put(("file_uploaded", {"url": str(url), "path": filepath,
                             "cb": callback}))
        except Exception as e:
            self.gui_q.put(("error", f"Dosya yükleme hatası: {e}"))

    def send_file(self, to, filepath, mtype="chat"):
        """Dosyayı HTTP Upload ile yükleyip OOB mesaj olarak gönder."""
        asyncio.run_coroutine_threadsafe(
            self._send_file_impl(to, filepath, mtype), self.loop)

    async def _send_file_impl(self, to, filepath, mtype):
        try:
            upload = _get_xep(self, "xep_0363")
            url = await upload.upload_file(filepath, timeout=60)
            url = str(url)
            msg = self.make_message(mto=to, mbody=url, mtype=mtype)
            msg["oob"]["url"] = url
            msg.send()
            fname = os.path.basename(filepath)
            self.gui_q.put(("sys_msg", f"✓ Dosya gönderildi: {fname}"))
        except Exception as e:
            self.gui_q.put(("error", f"Dosya gönderme hatası: {e}"))
