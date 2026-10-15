"""Yanıt bekleyen sorular (yerel, modelsiz sezgi).

Tk/ağ/DB YOKTUR. Girdi, storage'ın `_db_unanswered` satırlarıdır: her
sohbette benim son mesajımdan SONRA gelen mesajlar. Bunlardan soru
olanlar sohbet başına tek kayıtta toplanır. Soru tespiti deterministiktir
(soru işareti, Türkçe soru eki, soru sözcüğüyle başlama); gövde yalnız
yerelde işlenir, hiçbir modele gitmez.
"""
import re
from datetime import date, datetime, timedelta

from .ai import message_text
from .storage import STORED_AT_FMT

DISMISS_KEY = "dismissed_questions"
DISMISS_CAP = 300

_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
_QMARK_RE = re.compile(r"[?？¿]")
# mı/mi/mu/mü ve çekimli biçimleri (misin, mıyız, mudur, müydü…) ayrı
# sözcük olarak. Ünlü uyumu zorlanmaz; ek tek başına neredeyse her zaman
# soru belirtir.
_PARTICLE_RE = re.compile(
    r"(?<!\w)m[ıiuü](?:y[ıiuü]m|s[ıiuü]n(?:[ıiuü]z)?|y[ıiuü]z|d[ıiuü]r|"
    r"yd[ıiuü](?:m|n|k|n[ıiuü]z)?|ym[ıiuü]ş)?(?!\w)", re.IGNORECASE)
_LEADING_RE = re.compile(
    r"^(?:ne zaman|nerede|nereye|nereden|neden|niye|niçin|nasıl|kim|kime|"
    r"kimin|kimi|hangi|hangisi|kaç|acaba|"
    r"who|what|when|where|why|how|which|can you|could you|would you|"
    r"will you|do you|did you|are you|is it|is there|should i)\b",
    re.IGNORECASE)


def _plain(body: str) -> str:
    """Alıntı satırları, kod ve bağlantılar çıkarılmış metin."""
    text = message_text(body or "")
    if not text:
        return ""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    text = _CODE_RE.sub(" ", "\n".join(lines))
    return _URL_RE.sub(" ", text).strip()


def is_question(body: str) -> bool:
    text = _plain(body)
    if not text:
        return False
    if _QMARK_RE.search(text) or _PARTICLE_RE.search(text):
        return True
    return bool(_LEADING_RE.match(text))


def parse_stored_at(value):
    try:
        return datetime.strptime(str(value or ""), STORED_AT_FMT)
    except ValueError:
        return None


def snippet(body: str, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", _plain(body))
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def find_pending(rows, *, dismissed=(), skip_jids=()):
    """Sohbet başına yanıt bekleyen soru kaydı.

    rows: [(id, jid, sender, body, stored_at, mid, encrypted)], id artan.
    Dönüş: [{"jid", "key", "sender", "text", "count", "since",
    "encrypted"}] — en uzun bekleyen önce; tarihi bilinmeyenler sonda.
    `key` sohbetin EN YENİ sorusuna bağlıdır: yok sayılan sohbete yeni soru
    gelirse kayıt yeniden görünür.
    """
    dismissed = set(dismissed)
    skip = set(skip_jids)
    by_jid: dict = {}
    for msg_id, jid, sender, body, stored_at, _mid, encrypted in rows:
        if jid in skip or not is_question(body):
            continue
        by_jid.setdefault(jid, []).append(
            (msg_id, sender, body, parse_stored_at(stored_at),
             bool(encrypted)))
    out = []
    for jid, qs in by_jid.items():
        last = qs[-1]
        key = f"{jid}#{last[0]}"
        if key in dismissed:
            continue
        times = [q[3] for q in qs if q[3] is not None]
        out.append({
            "jid": jid, "key": key, "sender": last[1] or "",
            "text": snippet(last[2]), "count": len(qs),
            "since": min(times) if times else None,
            "encrypted": any(q[4] for q in qs),
        })
    out.sort(key=lambda e: (e["since"] is None, e["since"] or datetime.min,
                            e["jid"]))
    return out


def format_age(since, now) -> str:
    if since is None:
        return "tarihi bilinmiyor"
    secs = max(0, int((now - since).total_seconds()))
    if secs < 60:
        return "az önce"
    if secs < 3600:
        return f"{secs // 60} dakika önce"
    if secs < 86400:
        return f"{secs // 3600} saat önce"
    days = (now.date() - since.date()).days
    return "dün" if days <= 1 else f"{days} gün önce"


def waiting_longer_than(entries, now, seconds) -> list:
    """Belirtilen süreden uzun bekleyen kayıtlar (tarihsizler hariç)."""
    return [e for e in entries if e["since"] is not None
            and (now - e["since"]).total_seconds() >= seconds]


def dismiss(stored, key) -> list:
    """Yok sayılanlar listesine ekle; en eski kayıtlar tavanda düşer."""
    items = [k for k in (stored if isinstance(stored, list) else [])
             if isinstance(k, str) and k != key]
    items.append(key)
    return items[-DISMISS_CAP:]


def reminder_item(entry, label: str, today: date) -> dict:
    """"Yarın 09:00'da hatırlat" için görev öğesi (ai.validate_actions
    biçimi; MainWindow mevcut hatırlatıcı yoluna verir)."""
    return {"kind": "task", "title": f"Yanıtla: {label} — {entry['text']}",
            "date": (today + timedelta(days=1)).isoformat(), "time": "09:00",
            "location": "", "notes": entry["text"]}
