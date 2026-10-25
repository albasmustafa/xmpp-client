"""HTTP dosya yükleme ve OOB transfer yardımcıları.

Faz 2: XMPPBot TransferMixin (XEP-0363). Jingle (XEP-0234) yönetimi
bilinçli olarak jingle_ft.py + xmpp.py'de bırakılmıştır.
Event adları ve gui_q payload'ları birebir korunmuştur.

OMEMO'lu sohbette dosya AES-256-GCM ile şifrelenip yüklenir (XEP-0454):
sunucu yalnız şifreli veriyi ve rastgele bir adı görür; çözme anahtarı
taşıyan `aesgcm://` bağlantısı yalnız OMEMO'lu gövdede gider (OOB yok).
"""
import asyncio
import io
import os

from xmppcore import aesgcm as _aesgcm
from xmppcore.helpers import _get_xep
from xmppcore.i18n import tr as _tr


def _encrypt_file(filepath):
    with open(filepath, "rb") as f:
        return _aesgcm.encrypt(f.read())


class TransferMixin:
    """HTTP Upload (XEP-0363) ile dosya yükleme/gönderme."""

    # ── HTTP File Upload (XEP-0363) ──────────────────────────────────────────
    def upload_file(self, filepath, callback, encrypt=False):
        asyncio.run_coroutine_threadsafe(
            self._upload_file(filepath, callback, encrypt), self.loop)

    async def _upload_file(self, filepath, callback, encrypt=False):
        try:
            if encrypt:
                if not self._omemo_file_ready():
                    return
                url = await self._upload_encrypted(filepath)
            else:
                upload = _get_xep(self, "xep_0363")
                url = await upload.upload_file(filepath, timeout=60)
            self.gui_q.put(("file_uploaded", {"url": str(url), "path": filepath,
                             "cb": callback, "encrypted": bool(encrypt)}))
        except Exception as e:
            self.gui_q.put(("error", _tr("Dosya yükleme hatası: {}").format(e)))

    def send_file(self, to, filepath, mtype="chat", encryption="none"):
        """Dosyayı HTTP Upload ile yükleyip gönder: düz → OOB mesaj,
        "omemo" → şifreli yükleme + aesgcm:// bağlantısı OMEMO'lu gövdede."""
        asyncio.run_coroutine_threadsafe(
            self._send_file_impl(to, filepath, mtype, encryption), self.loop)

    async def _send_file_impl(self, to, filepath, mtype, encryption="none"):
        try:
            fname = os.path.basename(filepath)
            if encryption == "omemo":
                if not self._omemo_file_ready():
                    return
                url = await self._upload_encrypted(filepath)
                self.gui_q.put(("sys_msg",
                                _tr("🔒 Dosya şifreli yüklendi: {}").format(fname)))
                # Gönderim sonucu (hata dahil) _send_omemo'nun kendi olaylarıdır
                await self._send_omemo(to, url, mtype)
                return
            upload = _get_xep(self, "xep_0363")
            url = await upload.upload_file(filepath, timeout=60)
            url = str(url)
            msg = self.make_message(mto=to, mbody=url, mtype=mtype)
            msg["oob"]["url"] = url
            msg.send()
            self.gui_q.put(("sys_msg", _tr("✓ Dosya gönderildi: {}").format(fname)))
        except Exception as e:
            self.gui_q.put(("error", _tr("Dosya gönderme hatası: {}").format(e)))

    # ── Şifreli yükleme (XEP-0454) ───────────────────────────────────────────
    def _omemo_file_ready(self):
        """Şifreli dosya için OMEMO hazır mı? Değilse dosya hiç yüklenmez:
        şifresiz yüklemeye düşmek sohbetin şifreleme seçimini çiğner."""
        if not self._omemo_enabled():
            self.gui_q.put(("error",
                _tr("OMEMO kütüphanesi yüklü değil (slixmpp-omemo) — dosya "
                    "gönderilmedi.")))
            return False
        if not self.omemo_ready:
            self.gui_q.put(("error",
                _tr("OMEMO henüz hazır değil — dosya gönderilmedi; birkaç "
                    "saniye sonra tekrar deneyin.")))
            return False
        return True

    async def _upload_encrypted(self, filepath):
        """Dosyayı şifreleyip yükle; `aesgcm://…#<iv><anahtar>` döner."""
        blob, key, iv = await asyncio.to_thread(_encrypt_file, filepath)
        upload = _get_xep(self, "xep_0363")
        url = await upload.upload_file(
            _aesgcm.upload_name(filepath), size=len(blob),
            content_type="application/octet-stream",
            input_file=io.BytesIO(blob), timeout=60)
        return _aesgcm.to_url(str(url), key, iv)
