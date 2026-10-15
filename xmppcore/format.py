"""Saf biçimleme/parse yardımcıları (Faz 1 yaprak modülü)."""
import re


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


def _parse_room_search(payload: dict) -> list:
    """search.jabber.network yanıtını oda listesine çevir.

    `POST /search` yanıtı `{"result": {"items": [...]}}`; eski `GET /rooms`
    biçimi `{"items": [...]}` de kabul edilir. Adresi olmayan kayıtlar
    atılır; sonuçlar kullanıcı sayısına göre azalan, eşitlikte ada göre
    artan sıralanır.
    """
    payload = payload if isinstance(payload, dict) else {}
    result = payload.get("result")
    raw = (result.get("items", []) if isinstance(result, dict)
           else payload.get("items", []))
    if not isinstance(raw, list):
        raw = []
    items = [i for i in raw if isinstance(i, dict) and i.get("address")]
    items.sort(key=lambda i: (-_to_int(i.get("nusers")),
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
