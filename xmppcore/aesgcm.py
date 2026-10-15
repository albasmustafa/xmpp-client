"""OMEMO medya paylaşımı: aesgcm:// bağlantıları (XEP-0454).

Conversations, Monocles, Monal, Siskin ve Gajim OMEMO açıkken dosyayı
AES-256-GCM ile şifreleyip HTTP Upload'a yükler; bağlantı şifreli mesaj
gövdesinde `aesgcm://sunucu/yol/dosya.jpg#<iv><anahtar>` biçiminde gelir.
Parça onaltılıktır: 12 baytlık IV + 32 baytlık anahtar (88 hane); eski
istemciler 16 baytlık IV kullanır (96 hane). GCM doğrulama etiketi (16 bayt)
şifreli verinin sonundadır. Tk'sız; ağ işi çağıranda yapılır.
"""
import os
import re
from urllib.parse import unquote, urlsplit, urlunsplit

# Mesaj gövdesindeki aesgcm bağlantısı (parça zorunlu)
URL_RE = re.compile(r'(aesgcm://[^\s<>"#]+#(?:[0-9a-fA-F]{96}|[0-9a-fA-F]{88}))'
                    r'(?![0-9a-fA-F])')
_FRAGMENT_RE = re.compile(r"^(?:[0-9a-fA-F]{88}|[0-9a-fA-F]{96})$")
_KEY_LEN = 32


def parse(url):
    """aesgcm URL → (https_url, key, iv); geçersizse None."""
    if not url or not str(url).lower().startswith("aesgcm://"):
        return None
    parts = urlsplit(url)
    if not parts.netloc or not _FRAGMENT_RE.match(parts.fragment):
        return None
    raw = bytes.fromhex(parts.fragment)
    iv, key = raw[:-_KEY_LEN], raw[-_KEY_LEN:]
    https = urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))
    return https, key, iv


def decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """Şifreli içeriği çöz; anahtar/veri bozuksa InvalidTag yükselir."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key).decrypt(iv, data, None)


def file_name(url) -> str:
    """Bağlantıdaki dosya adı (kaydetmeye güvenli; yol parçası içermez)."""
    path = unquote(urlsplit(url).path)
    name = os.path.basename(path.replace("\\", "/")).strip()
    return name if name not in ("", ".", "..") else "dosya"
