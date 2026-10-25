"""Stanza kimliği ve şifreleme yardımcıları (Faz 2 altyapısı).

xmpp.py'den taşınan yaprak yardımcılar; bot mixin'leri ile GUI kodu
tarafından ortak kullanılır. Davranış birebir korunmuştur.
"""
import asyncio
import re
import unicodedata
import uuid

from slixmpp.plugins.base import PluginNotFound

from xmppcore.i18n import tr as _tr

# JID yerel kısmında (kullanıcı/oda adı) yasak karakterler (RFC 7622 §3.3.1)
_LOCALPART_FORBIDDEN = "\"&'/:<>@"
_TR_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")


def _spawn_task(owner, coro):
    """Arka plan coroutine'ini başlat ve bitene kadar referansını tut.

    ``asyncio.ensure_future`` sonucu saklanmazsa event loop görevi yalnızca
    zayıf referansla tutar; GC görevi iş ortasında toplayabilir (ör. çözülen
    OMEMO mesajı sessizce düşer). Görev ``owner._bg_tasks`` kümesinde
    tutulur ve bitince kendini çıkarır.
    """
    task = asyncio.ensure_future(coro)
    tasks = getattr(owner, "_bg_tasks", None)
    if tasks is None:
        tasks = set()
        try:
            owner._bg_tasks = tasks
        except AttributeError:
            return task
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return task


def _normalize_room_jid(text: str, default_server: str = "") -> str:
    """Kullanıcının yazdığı/yapıştırdığı oda adresini bare, normalize JID'e çevir.

    slixmpp MUC olaylarını normalize (küçük harfli) JID ile tetikler; ham
    girdiyle katılım beklenirse olay hiç eşleşmez ve zaman aşımına düşer.
    Kabul edilenler: `xmpp:oda@sunucu?join` bağlantısı, kaynaklı JID
    (`oda@sunucu/nick` → resource atılır) ve yalnız oda adı (`default_server`
    eklenir). Geçersiz girdi → ValueError.
    """
    from slixmpp import JID
    from slixmpp.jid import InvalidJID

    s = (text or "").strip()
    if s.lower().startswith("xmpp:"):
        s = s[5:]
    s = s.split("?", 1)[0].strip()
    if not s:
        raise ValueError(_tr("Oda adresi boş"))
    local = s.split("/", 1)[0].rsplit("@", 1)[0] if "@" in s else s
    problem = _localpart_problem(local)
    if problem:
        hint = _room_slug(local)
        raise ValueError(_tr("Geçersiz oda adresi: {!r} — oda adında {}")
                         .format(text.strip(), problem) + (_tr(" (ör. {})")
                                                           .format(hint) if hint else ""))
    if "@" not in s:
        server = (default_server or "").strip()
        if not server:
            raise ValueError(_tr("Oda adresinde sunucu yok: {!r}").format(text))
        s = f"{s}@{server}"
    try:
        jid = JID(s)
    except InvalidJID as e:
        raise ValueError(_tr("Geçersiz oda adresi: {!r}").format(text)) from e
    if not jid.user or not jid.domain:
        raise ValueError(_tr("Geçersiz oda adresi: {!r}").format(text))
    return jid.bare


def _square_avatar_png(path, size: int = 256) -> bytes:
    """Görseli ortadan kare kırp, `size` px'e küçült, PNG bayt döndür
    (profil resmi biçimi; büyük ham dosyayı sunucular reddeder)."""
    import io

    from PIL import Image

    with Image.open(path) as img:
        img = img.convert("RGBA")
        w, h = img.size
        s = min(w, h)
        left, top = (w - s) // 2, (h - s) // 2
        img = img.crop((left, top, left + s, top + s)).resize(
            (size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    return buf.getvalue()


def _localpart_problem(local: str) -> str:
    """JID yerel kısmını geçersiz kılan sorunu Türkçe anlat ('' = sorun yok)."""
    if any(ch.isspace() for ch in local):
        return _tr("boşluk kullanılamaz")
    bad = sorted({ch for ch in local if ch in _LOCALPART_FORBIDDEN})
    if bad:
        return _tr("şu karakterler kullanılamaz: ") + " ".join(bad)
    return ""


def _room_slug(name: str) -> str:
    """Oda adından adres yerel kısmı üret: "Şifreli Oda" → "sifreli-oda".

    Türkçe harfler ASCII'ye çevrilir (İ küçültülünce birleşik nokta
    kalmasın), adres dışı karakterler tireye döner.
    """
    s = unicodedata.normalize("NFKD", (name or "").translate(_TR_ASCII))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-._")


def _room_address(name: str, server: str):
    """Oda Oluştur girdisi → (oda JID'i, görünen ad).

    '@' içeren girdi tam adres sayılır (görünen ad boş); düz ad adrese
    çevrilir ve kendisi oda başlığı olur. Kullanılamaz girdi → ValueError.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError(_tr("Oda adı girin."))
    if "@" in name:
        return _normalize_room_jid(name), ""
    slug = _room_slug(name)
    if not slug:
        raise ValueError(_tr("Oda adından adres üretilemedi; harf ya da rakam "
                             "kullanın (ör. proje-ekibi)."))
    return _normalize_room_jid(slug, server), name


def _normalize_user_jid(text: str) -> str:
    """Kullanıcının yazdığı kişi JID'ini bare, normalize biçime çevir.

    `xmpp:ali@sunucu?message` bağlantısı ve kaynaklı JID kabul edilir;
    büyük/küçük harf gelen mesajların anahtarıyla aynı biçime iner.
    Geçersiz girdi → anlaşılır Türkçe ValueError.
    """
    from slixmpp import JID
    from slixmpp.jid import InvalidJID

    s = (text or "").strip()
    if s.lower().startswith("xmpp:"):
        s = s[5:]
    s = s.split("?", 1)[0].strip()
    if not s:
        raise ValueError(_tr("Lütfen bir JID girin."))
    if "@" not in s:
        raise ValueError(_tr("Geçersiz JID — @ işareti olmalı (ör: ali@sunucu.tld)"))
    problem = _localpart_problem(s.split("/", 1)[0].rsplit("@", 1)[0])
    if not problem and any(ch.isspace() for ch in s.split("/", 1)[0]):
        problem = _tr("boşluk kullanılamaz")
    if problem:
        raise ValueError(_tr("Geçersiz JID — {}: {!r}").format(problem, s))
    try:
        jid = JID(s)
    except InvalidJID as e:
        raise ValueError(_tr("Geçersiz JID: {!r}").format(s)) from e
    if not jid.user or not jid.domain:
        raise ValueError(_tr("Geçersiz JID: {!r}").format(s))
    return jid.bare


def _get_xep(xmpp_obj, name: str):
    """XEP eklentisine eriş.

    Desteklenen API ``obj.plugin[name]`` (PluginManager); eski ``obj[name]``
    yolu DeprecationWarning üretir. Sözleşme:
      • kayıtlı eklenti → eklenti örneği,
      • gerçek PluginManager'da kayıtsız → ``False`` (eski API'nin
        eksik-eklenti davranışı; çağırıcılar falsy kontrolüyle atlar),
      • ``.plugin`` API'si olmayan eski nesneler / ``.plugin = None``
        sahteleri / dict benzeri manager'lar → eski ``obj[name]`` yolu
        (``__getitem__`` yaması kullanan test sahteleri burada çözülür).
    """
    plugin_mgr = getattr(xmpp_obj, "plugin", None)
    if plugin_mgr is None:
        return xmpp_obj[name]
    try:
        return plugin_mgr[name]
    except PluginNotFound:
        # Yalnızca gerçek PluginManager'ın "kayıtsız" cevabı: eski API'nin
        # döndürdüğü False'u uyarı ve log üretmeden döndür.
        return False
    except Exception:
        # PluginNotFound dışı hata = PluginManager olmayan (dict/sahte)
        # manager; eski erişim yolunu koru.
        return xmpp_obj[name]


# Mesaj üstverisi: düzeltme (XEP-0308), geri çekme (0424), tepki (0444),
# okundu işareti (0333) ve OMEMO yükü (eski + OMEMO 2)
_CORRECTION = "{urn:xmpp:message-correct:0}replace"
_RETRACTS = ("{urn:xmpp:message-retract:1}retract",
             "{urn:xmpp:message-retract:0}retract")
_REACTIONS = "{urn:xmpp:reactions:0}reactions"
_DISPLAYED = "{urn:xmpp:chat-markers:0}displayed"
_OMEMO_TAGS = ("{eu.siacs.conversations.axolotl}encrypted",
               "{urn:xmpp:omemo:2}encrypted")


def _has_child(xml, *tags) -> bool:
    """Stanza'nın doğrudan çocuklarından biri verilen etiketlerden biri mi?"""
    return xml is not None and any(xml.find(t) is not None for t in tags)


def _stanza_is_encrypted(xml) -> bool:
    """Stanza XML'inde OMEMO veya PGP şifreli yük var mı?"""
    if xml is None:
        return False
    ns = ("eu.siacs.conversations.axolotl", "urn:xmpp:omemo:2",
          "jabber:x:encrypted")
    try:
        for el in xml.iter():
            tag = str(getattr(el, "tag", ""))
            if any(f"{{{n}}}" in tag for n in ns):
                return True
    except Exception:
        pass
    return False


# ── Kimlik, yanıt ve tepki yardımcıları (XEP-0359/0461/0428/0444) ────────
def _new_msg_id() -> str:
    """Giden mesajlar için benzersiz origin-id üret."""
    return str(uuid.uuid4())


def _stanza_msg_id(stanza) -> str:
    """Mesajın kalıcı kimliği: origin-id → stanza-id → stanza id.

    Yanıt (XEP-0461) ve tepkiler (XEP-0444) bu kimliğe atıfta bulunur;
    bu yüzden gelen/giden tüm mesajlarda aynı sırayla okunmalıdır.
    """
    for attr in ("origin_id", "stanza_id"):
        try:
            value = stanza[attr]["id"]
            if value:
                return str(value)
        except Exception:
            continue
    try:
        return str(stanza["id"] or "")
    except Exception:
        return ""


def _add_origin_id(msg, value: str | None = None) -> str:
    """Giden mesaja XEP-0359 origin-id ekler ve kimliği döndürür."""
    try:
        existing = msg["origin_id"]["id"]
        if existing:
            return str(existing)
    except Exception:
        pass
    oid = value or _new_msg_id()
    try:
        msg["origin_id"]["id"] = oid
        return oid
    except Exception:
        try:
            return str(msg["id"] or oid)
        except Exception:
            return oid


def _strip_quoted_fallback(msg, body: str) -> str:
    """XEP-0428 alıntı önizlemesini gövdeden çıkarır (yanıtlarda)."""
    if not body:
        return body
    try:
        reply = msg["reply"]
        if reply is not None and reply["id"]:
            stripped = reply.strip_fallback_content()
            if stripped:
                return stripped
    except Exception:
        pass
    return body
