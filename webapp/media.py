"""Web arayüzü için medya: şifreli dosyayı açma, yükleme, ses dökümü.

- Şifreli medya (OMEMO, `aesgcm://`, XEP-0454) tarayıcıda çözülemez: anahtar
  bağlantının parçasıdır ve tarayıcı bu şemayı tanımaz. Sunucu dosyayı
  indirip çözer (ya da masaüstünün indirdiği yerel kopyayı okur) ve
  oturum başlığıyla gelen isteğe döndürür; tarayıcı blob URL'si gösterir.
  Düz `https` medya bu yoldan geçmez (tarayıcı kendisi yükler).
- Tarayıcı kaydı (MediaRecorder) çoğunlukla WebM/Opus üretir; telefon
  istemcileri Ogg/Opus'u daha iyi tanır. Ses yeniden kodlanmadan Ogg
  kabına aktarılır (PyAV); olmazsa özgün dosya gönderilir.
- Satır içi sunulan türler görsel/ses/video ile sınırlıdır; SVG ve diğer
  her şey indirme olarak döner (aynı kökende betik çalışmasın).
"""
import mimetypes
import os
import re
import tempfile
from urllib.parse import urlsplit

from xmppcore import aesgcm
from xmppcore import storage as _storage
from xmppcore.constants import _log
from xmppcore.i18n import tr as _tr

MEDIA_MAX = 32 * 1024 * 1024
UPLOAD_MAX = 25 * 1024 * 1024
_INLINE_TYPES = re.compile(r"^(?:image/(?:png|jpeg|gif|webp|avif|bmp)|"
                           r"audio/[\w.+-]+|video/(?:mp4|webm|ogg))$")
_AUDIO_EXT = re.compile(r"\.(?:wav|ogg|opus|mp3|m4a|flac|aac|webm)$", re.I)
_SAFE_NAME = re.compile(r"[^\w.-]+")
# Tarayıcının bildirdiği kayıt türü → dosya uzantısı
_UPLOAD_EXT = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
               "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav"}


def media_url(body: str, oob: str) -> str:
    """Satırın medya bağlantısı: aesgcm (oob ya da gövdede) ya da https oob."""
    for cand in (oob, (body or "").strip()):
        if cand and aesgcm.parse(cand):
            return cand
    if oob and oob.lower().startswith(("http://", "https://")):
        return oob
    return ""


def find(jid: str, row_id=None, mid: str = ""):
    """(url, yerel yol) ya da medya yoksa None."""
    row = _storage._db_media_row(jid, row_id=row_id, mid=mid)
    if row is None:
        return None
    body, oob, local_path, _enc = row
    url = media_url(body, oob)
    if not url and not local_path:
        return None
    return url, local_path


def file_name(url: str, local_path: str = "") -> str:
    if local_path:
        return os.path.basename(local_path)
    if aesgcm.parse(url):
        return aesgcm.file_name(url)
    return os.path.basename(urlsplit(url).path) or "dosya"


def content_type(name: str) -> tuple[str, bool]:
    """(MIME türü, satır içi mi). Bilinmeyen/tehlikeli tür → indirme."""
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if name.lower().endswith((".opus", ".ogg")):
        ctype = "audio/ogg"
    elif name.lower().endswith(".m4a"):
        ctype = "audio/mp4"
    if _INLINE_TYPES.match(ctype):
        return ctype, True
    return "application/octet-stream", False


def load(url: str, local_path: str = "") -> bytes:
    """Medya baytları (worker thread): yerel kopya, yoksa indir + çöz."""
    if local_path and os.path.isfile(local_path):
        if os.path.getsize(local_path) > MEDIA_MAX:
            raise ValueError("too large")
        with open(local_path, "rb") as f:
            return f.read()
    from xmppcore.ai import fetch_url
    return fetch_url(url, MEDIA_MAX)


def is_audio(name: str) -> bool:
    return bool(_AUDIO_EXT.search(name or ""))


# ── Yükleme ────────────────────────────────────────────────────────────────
def upload_suffix(name: str, ctype: str) -> str:
    ext = os.path.splitext(name or "")[1].lower()
    if re.fullmatch(r"\.[a-z0-9]{1,8}", ext):
        return ext
    return _UPLOAD_EXT.get((ctype or "").split(";")[0].strip().lower(), "")


def safe_upload_name(name: str, ctype: str) -> str:
    stem = _SAFE_NAME.sub("_", os.path.splitext(os.path.basename(name or ""))[0])
    return (stem.strip("_")[:60] or "dosya") + upload_suffix(name, ctype)


def remux_to_ogg(path: str) -> str:
    """WebM/Opus sesi yeniden kodlamadan Ogg'a aktar; olmazsa özgün yol.

    Yeni dosya oluşursa özgün dosya silinir (çağıranın tek dosyası kalır).
    """
    if not path.lower().endswith(".webm"):
        return path
    try:
        import av
    except ImportError:
        return path
    out_path = path[:-5] + ".ogg"
    try:
        with av.open(path) as src:
            audio = next((s for s in src.streams if s.type == "audio"), None)
            if audio is None or audio.codec_context.name != "opus":
                return path
            with av.open(out_path, "w", format="ogg") as dst:
                stream = dst.add_stream_from_template(audio)
                for packet in src.demux(audio):
                    if packet.dts is None:
                        continue
                    packet.stream = stream
                    dst.mux(packet)
    except Exception:
        _log.warning("WebM → Ogg aktarımı başarısız; özgün dosya gönderilir",
                     exc_info=True)
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return path
    try:
        os.unlink(path)
    except OSError:
        pass
    return out_path


def write_temp(data: bytes, name: str) -> str:
    """Yüklemeyi kendi geçici klasörüne yaz (ad sunucuya gider: güvenli ad)."""
    folder = tempfile.mkdtemp(prefix="xmpp-web-up-")
    path = os.path.join(folder, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def discard_temp(path: str) -> None:
    """write_temp dosyasını ve klasörünü sil (yalnız kendi önekimizdekiler)."""
    folder = os.path.dirname(path or "")
    if not os.path.basename(folder).startswith("xmpp-web-up-"):
        return
    for name in os.listdir(folder) if os.path.isdir(folder) else ():
        try:
            os.unlink(os.path.join(folder, name))
        except OSError:
            pass
    try:
        os.rmdir(folder)
    except OSError:
        pass


# ── Ses → metin ────────────────────────────────────────────────────────────
def transcribe(jid: str, row_id=None, mid: str = "") -> dict:
    """Satırdaki sesi yazıya dök (worker thread). Önbellek anahtarı
    masaüstüyle aynıdır ("stt:<model>:<bağlantı>"): iki taraf paylaşır."""
    from xmppcore import ai as _ai
    s = _ai.load_settings(_load_cfg())
    if s["provider"] == _ai.PROVIDER_OFF:
        raise _ai.AIError(_tr("AI kapalı"))
    found = find(jid, row_id=row_id, mid=mid)
    if not found:
        raise ValueError("no media")
    url, local_path = found
    ref = local_path if local_path and not url else url
    model = s["whisper_model"]
    key = _cache_key("stt", model, ref)
    cached = _storage._db_ai_cache_get(key)
    if cached:
        return {"text": _ai.display_text(cached), "cached": True}
    data = load(url, local_path)
    ext = os.path.splitext(file_name(url, local_path))[1] or ".audio"
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        text = _ai.transcribe_file(tmp.name, model)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    _storage._db_ai_cache_set(key, jid, text)
    return {"text": _ai.display_text(text), "cached": False}


def _cache_key(kind: str, model: str, source: str) -> str:
    """xmpp.MainWindow._ai_cache_key ile aynı biçim (önbellek ortak)."""
    import hashlib
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"{kind}:{model}:{digest}"


def _load_cfg() -> dict:
    from xmppcore.config import _load_config
    return _load_config()
