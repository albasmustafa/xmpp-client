"""Bildirim politikası (Tk'sız, ağsız): gelen mesaj dikkat çeksin mi?

Masaüstü (`MainWindow._handle` "msg") ve web köprüsü (`WebSession._apply`)
aynı kararı buradan alır. Politika yalnız dikkat çeken yan etkileri keser
(masaüstü bildirimi, ses, toast, tarayıcı bildirimi); okunmamış sayacı ve
kayıt her durumda aynı kalır.

Ayar anahtarları (config, masaüstü ve web ortak):
  "muted_chats":     {jid: bitiş (epoch sn)}; 0 = süresiz. Süresi geçen girdi
                     sessiz sayılmaz ve bir sonraki yazımda temizlenir.
  "room_notify_all": [oda jid'leri] — bu odalarda her mesaj bildirilir; öteki
                     odalarda yalnız takma adımız geçince ya da mesajımıza
                     yanıt verilince.
Meşgulken (dnd) hiçbir mesaj bildirilmez.
"""
import re
import time

MUTE_FOREVER = 0
# Seçenek anahtarı → süre (sn). Sıra menülerdeki sıradır.
MUTE_CHOICES = {"1h": 3600, "8h": 8 * 3600, "1d": 86400,
                "forever": MUTE_FOREVER}


def _now(now):
    return time.time() if now is None else now


def _mutes(cfg) -> dict:
    raw = (cfg or {}).get("muted_chats")
    return raw if isinstance(raw, dict) else {}


def _room_all(cfg) -> set:
    raw = (cfg or {}).get("room_notify_all")
    return {str(j) for j in raw} if isinstance(raw, list) else set()


def muted_until(cfg, jid, now=None):
    """None: sessiz değil · 0: süresiz sessiz · >0: o ana kadar sessiz."""
    until = _mutes(cfg).get(jid)
    if isinstance(until, bool) or not isinstance(until, (int, float)):
        return None
    if until == MUTE_FOREVER:
        return MUTE_FOREVER
    return until if until > _now(now) else None


def is_muted(cfg, jid, now=None) -> bool:
    return muted_until(cfg, jid, now) is not None


def room_notifies_all(cfg, room) -> bool:
    return room in _room_all(cfg)


def _fold(text: str) -> str:
    # Türkçe I/İ/ı/i her iki dilde de aynı harf sayılsın ("İlker" ↔ "ilker")
    for ch in "İIı":
        text = text.replace(ch, "i")
    return text.casefold()


def mentions(body, nick) -> bool:
    """Gövdede takma ad ayrı bir sözcük olarak geçiyor mu? ("@ali", "Ali:",
    "Ali'ye" evet; "alim" hayır)."""
    nick = (nick or "").strip()
    if not nick or not body:
        return False
    pattern = r"(?<!\w)" + re.escape(_fold(nick)) + r"(?!\w)"
    return re.search(pattern, _fold(body)) is not None


def should_notify(cfg, jid, body, *, is_room, my_nick="", my_show="online",
                  reply_sender="", now=None) -> bool:
    """Gelen mesaj bildirim/ses/toast çıkarsın mı?"""
    if my_show == "dnd" or is_muted(cfg, jid, now):
        return False
    if not is_room or room_notifies_all(cfg, jid):
        return True
    if reply_sender and reply_sender in {"Ben", my_nick}:
        return True
    return mentions(body, my_nick)


def _prune(mutes: dict, now) -> dict:
    return {j: u for j, u in mutes.items()
            if isinstance(u, (int, float)) and not isinstance(u, bool)
            and (u == MUTE_FOREVER or u > now)}


def set_mute(cfg, jid, choice, now=None) -> dict:
    """Sohbeti `choice` (MUTE_CHOICES anahtarı) kadar sessize al; None ya da
    bilinmeyen anahtar sesi açar. `cfg`'yi yerinde değiştirir ve döndürür."""
    now = _now(now)
    mutes = _prune(_mutes(cfg), now)
    if choice in MUTE_CHOICES:
        secs = MUTE_CHOICES[choice]
        mutes[jid] = MUTE_FOREVER if secs == MUTE_FOREVER else now + secs
    else:
        mutes.pop(jid, None)
    cfg["muted_chats"] = mutes
    return cfg


def set_room_all(cfg, room, on: bool) -> dict:
    """Odada her mesajda mı (on) yoksa yalnız adım geçince mi bildirilsin."""
    rooms = _room_all(cfg)
    if on:
        rooms.add(room)
    else:
        rooms.discard(room)
    cfg["room_notify_all"] = sorted(rooms)
    return cfg


def snapshot(cfg, now=None) -> dict:
    """Web istemcisine giden özet: {"muted": {jid: bitiş}, "room_all": [...]}."""
    return {"muted": _prune(_mutes(cfg), _now(now)),
            "room_all": sorted(_room_all(cfg))}


def end_text(until, now=None) -> str:
    """Sessizliğin bitişi: bugünse "18:30", değilse "24.11 18:30"; süresizse ""."""
    if not until:
        return ""
    end = time.localtime(until)
    today = time.localtime(_now(now))
    if end[:3] == today[:3]:
        return time.strftime("%H:%M", end)
    return time.strftime("%d.%m %H:%M", end)
