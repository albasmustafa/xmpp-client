"""Saf biçimleme/parse yardımcıları (Faz 1 yaprak modülü)."""
import re
import unicodedata


def _fill_search_form(fields: dict, query: str) -> str | None:
    """XEP-0055 formunda sorguyu en uygun alana yerleştir.

    Öncelik: nick → first → last → q → ilk görünür alan.
    Doldurulan alanın adını, hiç alan yoksa None döndürür.
    """
    for preferred in ("nick", "first", "last", "q", "fn", "email"):
        field = fields.get(preferred)
        if field is not None and field.get("type") != "hidden":
            field["value"] = query
            return preferred
    for name, field in fields.items():
        if field.get("type") != "hidden":
            field["value"] = query
            return name
    return None



def _bookmark_add(bookmarks: list, jid: str, name: str = "",
                  nick: str = "", autojoin: bool = True) -> dict:
    """Yer imi ekle; aynı JID varsa güncelle (tekilleştirme)."""
    for bm in bookmarks:
        if bm.get("jid") == jid:
            if name:
                bm["name"] = name
            if nick:
                bm["nick"] = nick
            bm["autojoin"] = autojoin
            return bm
    bm = {"jid": jid, "name": name or jid.split("@")[0],
          "nick": nick, "autojoin": autojoin}
    bookmarks.append(bm)
    return bm



def _to_int(value, default: int = 0) -> int:
    """Güvenli int dönüşümü (bozuk API verisi çökertmesin)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Açıklamasında bu kadar çok kısa liste öğesi (≤3 sözcük) olan oda anahtar
# kelime doldurmuştur ("Indonesia, Jawa, … Linux, Python, …"); yalnız orada
# geçen eşleşme aramayla ilgili sayılmaz. Gerçek veride doldurulmuş
# açıklamalar 60+ öğe, düzyazı/konu listeleri en çok ~26 öğe.
_STUFFED_MIN_PARTS = 40
_DESCR_URL_RE = re.compile(r"\S+://\S+|\S*\w\.\w+/\S*|#\S+|\bxmpp:\S+")
_DESCR_SEP_RE = re.compile(r"::|[,;/|•·\n]")
_WORD_RE = re.compile(r"\w+")


def _is_stuffed(descr: str) -> bool:
    """Açıklama anahtar kelime yığını mı (URL'ler sayılmaz)."""
    descr = _DESCR_URL_RE.sub(" ", descr)
    short = sum(1 for p in _DESCR_SEP_RE.split(descr)
                if p.strip() and len(p.split()) <= 3)
    return short >= _STUFFED_MIN_PARTS


def _search_fold(value) -> str:
    """Büyük/küçük harf ve Türkçe aksan farkını yok say (İ/ı/ş… → i/i/s…)."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = text.replace("ı", "i")
    return "".join(c for c in text if not unicodedata.combining(c))


def _room_relevance(item: dict, keywords) -> tuple:
    """Oda arama sonucunun alakası: (en zayıf kelimenin puanı, toplam).

    Her kelime nerede geçtiğine göre puanlanır: adres/ad tam eşleşme 100,
    adda/adreste tam kelime 60, kelime başı 40, kelime içi 25, açıklamada
    kelime 15, açıklamada parça ya da sunucu adında 8, yerelde hiç bulunamazsa
    5 (sunucu başka biçimde eşlemiştir). Yalnız şişirilmiş açıklamada geçerse
    1: en sona düşer ama atılmaz (o konuyu arayan yine bulsun).
    """
    local, _, domain = str(item.get("address") or "").partition("@")
    local, domain = _search_fold(local), _search_fold(domain)
    name = _search_fold(item.get("name"))
    descr_raw = str(item.get("description") or "")
    descr = _search_fold(descr_raw)
    stuffed = _is_stuffed(descr_raw)
    title_words = _WORD_RE.findall(local) + _WORD_RE.findall(name)
    descr_words = _WORD_RE.findall(descr)
    scores = []
    for kw in keywords:
        kw = _search_fold(kw).strip()
        if not kw:
            continue
        if kw == local or kw == name.strip():
            score = 100
        elif kw in title_words:
            score = 60
        elif any(w.startswith(kw) for w in title_words):
            score = 40
        elif kw in local or kw in name:
            score = 25
        elif not stuffed and kw in descr_words:
            score = 15
        elif (not stuffed and kw in descr) or kw in domain:
            score = 8
        elif kw in descr:
            score = 1
        else:
            score = 5
        scores.append(score)
    return (min(scores), sum(scores)) if scores else (5, 5)


def _parse_room_search(payload: dict, keywords=None) -> list:
    """search.jabber.network yanıtını oda listesine çevir.

    `POST /search` yanıtı `{"result": {"items": [...]}}`; eski `GET /rooms`
    biçimi `{"items": [...]}` de kabul edilir. Adresi olmayan kayıtlar
    atılır. `keywords` verilirse sonuçlar alaka düzeyine göre sıralanır
    (`_room_relevance`; yalnız şişirilmiş açıklamada eşleşenler en sonda);
    eşit alakada (ya da kelime yoksa) kullanıcı sayısına göre azalan,
    eşitlikte ada göre artan sıralanır.
    """
    payload = payload if isinstance(payload, dict) else {}
    result = payload.get("result")
    raw = (result.get("items", []) if isinstance(result, dict)
           else payload.get("items", []))
    if not isinstance(raw, list):
        raw = []
    items = [i for i in raw if isinstance(i, dict) and i.get("address")]
    rel = {}
    if keywords:
        rel = {id(i): _room_relevance(i, keywords) for i in items}
    items.sort(key=lambda i: (tuple(-x for x in rel.get(id(i), ())),
                              -_to_int(i.get("nusers")),
                              str(i.get("name") or i.get("address")).lower()))
    return items



def _room_result_line(item: dict) -> str:
    """Oda arama sonucunun liste satırı."""
    addr = item.get("address", "")
    name = item.get("name") or addr
    nusers = _to_int(item.get("nusers"))
    lang = item.get("language", "") or ""
    prefix = f"[{lang}] " if lang else ""
    return f"  {prefix}{name}   👤{nusers}   —   {addr}"



_GEOM_RE = re.compile(r"^(\d+)x(\d+)(?:([+-]\d+)([+-]\d+))?$")


def _parse_geometry(geom, screen_w: int, screen_h: int) -> str:
    """Kayıtlı pencere geometrisini doğrula ve ekrana sığdır.

    Bozuk/eksik değerde "" döner; geçerliyse ``WxH`` veya ``WxH+X+Y``.
    Konum ekran dışına taşarsa görünür alana kırpılır.
    """
    m = _GEOM_RE.match(str(geom or "").strip())
    if not m:
        return ""
    w, h = int(m.group(1)), int(m.group(2))
    if w < 400 or h < 300:
        return ""
    screen_w = max(400, int(screen_w))
    screen_h = max(300, int(screen_h))
    w = min(w, screen_w)
    h = min(h, screen_h)
    out = f"{w}x{h}"
    if m.group(3) is not None:
        x, y = int(m.group(3)), int(m.group(4))
        x = min(max(x, 0), max(0, screen_w - w))
        y = min(max(y, 0), max(0, screen_h - h))
        out += f"+{x}+{y}"
    return out


def _parse_tenor_results(payload: dict) -> list:
    """Tenor API yanıtından {preview, url} listesi çıkar."""
    out = []
    for item in (payload or {}).get("results", []):
        fmts = item.get("media_formats", {}) or {}
        preview = (fmts.get("tinygif") or {}).get("url", "")
        full = (fmts.get("gif") or {}).get("url", "")
        url = full or preview
        if url:
            out.append({"preview": preview or url, "url": url})
    return out


def _reply_preview(text: str, limit: int = 140) -> str:
    """Yanıt kartı için tek satırlık kısa önizleme."""
    if not text:
        return ""
    flat = " ".join(str(text).split())
    return flat[:limit] + ("…" if len(flat) > limit else "")


def _forward_body(orig_from: str, orig_body: str) -> str:
    """İletilen mesajın gövdesi (gönderilen ve yerelde saklanan aynı metin)."""
    return f"[İletildi — {orig_from}]\n{orig_body}"


def _toggle_reaction_set(current, emoji: str) -> set:
    """Tepki kümesinde emoji'yi aç/kapat (XEP-0444 tam küme gönderilir)."""
    result = set(current or ())
    if emoji in result:
        result.discard(emoji)
    else:
        result.add(emoji)
    return result


def _reaction_tooltip(senders) -> str:
    """Tepki baloncuğu için 'kim tepki verdi' ipucu."""
    names = [str(x) for x in (senders or []) if str(x)]
    if not names:
        return ""
    if len(names) <= 4:
        return ", ".join(names)
    return ", ".join(names[:4]) + f" +{len(names) - 4}"
