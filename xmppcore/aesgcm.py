"""OMEMO medya paylaşımı: aesgcm:// bağlantıları (XEP-0454).

Conversations, Monocles, Monal, Siskin ve Gajim OMEMO açıkken dosyayı
AES-256-GCM ile şifreleyip HTTP Upload'a yükler; bağlantı şifreli mesaj
gövdesinde `aesgcm://sunucu/yol/dosya.jpg#<iv><anahtar>` biçiminde gelir.
Parça onaltılıktır: 12 baytlık IV + 32 baytlık anahtar (88 hane); eski
istemciler 16 baytlık IV kullanır (96 hane). GCM doğrulama etiketi (16 bayt)
şifreli verinin sonundadır. Gönderimde (OMEMO'lu sohbet) her dosyaya yeni
anahtar ve 12 baytlık IV üretilir. Tk'sız; ağ işi çağıranda yapılır.
"""
import os
import re
import secrets
from urllib.parse import unquote, urlsplit, urlunsplit

# Mesaj gövdesindeki aesgcm bağlantısı (parça zorunlu)
URL_RE = re.compile(r'(aesgcm://[^\s<>"#]+#(?:[0-9a-fA-F]{96}|[0-9a-fA-F]{88}))'
                    r'(?![0-9a-fA-F])')
_FRAGMENT_RE = re.compile(r"^(?:[0-9a-fA-F]{88}|[0-9a-fA-F]{96})$")
_KEY_LEN = 32
_IV_LEN = 12
_EXT_RE = re.compile(r"\.[a-z0-9]{1,8}")


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


def encrypt(data: bytes) -> tuple[bytes, bytes, bytes]:
    """Gönderim için şifrele → (şifreli veri + etiket, anahtar, IV)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = AESGCM.generate_key(bit_length=256)
    iv = os.urandom(_IV_LEN)
    return AESGCM(key).encrypt(iv, data, None), key, iv


def to_url(https_url: str, key: bytes, iv: bytes) -> str:
    """Yükleme bağlantısı (https) → `aesgcm://…#<iv><anahtar>`. Alıcı
    bağlantıyı https olarak indirir; başka şema kabul edilmez."""
    parts = urlsplit(str(https_url))
    if parts.scheme.lower() != "https" or not parts.netloc:
        raise ValueError("aesgcm bağlantısı yalnız https yüklemeden kurulur")
    return urlunsplit(("aesgcm", parts.netloc, parts.path, parts.query,
                       (iv + key).hex()))


def upload_name(path) -> str:
    """Sunucuya giden ad: rastgele + özgün uzantı. Asıl dosya adı sunucuya
    gitmez; alıcı istemciler türü (görsel, ses…) uzantıdan tanır."""
    ext = os.path.splitext(os.path.basename(str(path)))[1].lower()
    return secrets.token_hex(8) + (ext if _EXT_RE.fullmatch(ext) else "")


def file_name(url) -> str:
    """Bağlantıdaki dosya adı (kaydetmeye güvenli; yol parçası içermez)."""
    path = unquote(urlsplit(url).path)
    name = os.path.basename(path.replace("\\", "/")).strip()
    return name if name not in ("", ".", "..") else "dosya"
