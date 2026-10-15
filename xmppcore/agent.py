"""AI ajanı: doğal dil komutunu tek bir istemci eylemine çevirir (Tk YOK).

Akış: kullanıcı metni → model (yapılandırılmış JSON, PLAN_SCHEMA) →
`parse_plan` → `check_plan` → hedef çözümleme `resolve_target` (YEREL:
kişi/oda listesi modele hiç gönderilmez; model yalnız kullanıcının yazdığı
adı döndürür) → onay kartı `describe` → MainWindow eylemi mevcut yollarla
yürütür (gönderim normal giriş kutusu yolundan, hatırlatıcı mevcut
hatırlatıcı yolundan geçer).

Güvenlik: CONFIRM_ACTIONS (mesaj gönderme, odaya katılma, durum değiştirme,
hatırlatıcı) her zaman kullanıcı onayı ister. Model bir JID uydursa bile
yalnız yerelde eşleşen hedefe işlem yapılır.
"""
import difflib
import re
import unicodedata
from datetime import datetime

from .ai import AIError, _loads_json, parse_date, parse_time

# Eylem → model için kısa açıklama (sistem isteminde listelenir).
ACTIONS = {
    "answer": "Only reply (chat, help, explanations). Do nothing else.",
    "open_chat": "Open the chat with a contact or room. Needs target.",
    "draft_message": "Put a message into the input box WITHOUT sending it. "
                     "Needs target and text.",
    "send_message": "Send a message to a contact or room (the user confirms "
                    "first). Needs target and text.",
    "remind": "Set a reminder. text = what to remind, date = YYYY-MM-DD, "
              "time = HH:MM; target = related contact (optional).",
    "join_room": "Join a group chat room. target = room name or address.",
    "set_status": "Change the user's presence. status = online | away | "
                  "dnd | xa.",
    "summarize_chat": "Summarize a chat. Needs target.",
    "extract_tasks": "Extract tasks and events from a chat. Needs target.",
    "missed": "Summarize all unread messages (what did I miss).",
    "ask_history": "Search the user's past messages and answer a question "
                   "about them. text = the question.",
    "pending_questions": "Show questions the user has not answered yet.",
}
CONFIRM_ACTIONS = frozenset({"send_message", "remind", "join_room",
                             "set_status"})
TARGET_ACTIONS = frozenset({"open_chat", "draft_message", "send_message",
                            "summarize_chat", "extract_tasks"})
TEXT_ACTIONS = frozenset({"draft_message", "send_message", "remind",
                          "ask_history"})
STATUS_LABELS = {"online": "Çevrimiçi", "away": "Uzakta",
                 "dnd": "Meşgul", "xa": "Uzun süre uzakta"}

_FIELDS = ("action", "reply", "target", "text", "date", "time", "status")
_LIMITS = {"reply": 2000, "target": 200, "text": 4000, "date": 20,
           "time": 10, "status": 10}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "reply": {"type": "string"},
        "target": {"type": "string"},
        "text": {"type": "string"},
        "date": {"type": "string"},
        "time": {"type": "string"},
        "status": {"type": "string", "enum": [*STATUS_LABELS, ""]},
    },
    "required": list(_FIELDS),
    "additionalProperties": False,
}

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday")


def system_prompt(now: datetime, lang: str) -> str:
    actions = "\n".join(f"- {name}: {desc}" for name, desc in ACTIONS.items())
    return (
        "You are the built-in assistant of an XMPP chat client. Turn the "
        "user's request into exactly ONE action and answer as JSON.\n"
        f"Actions:\n{actions}\n\n"
        "Rules:\n"
        "- target: the contact or room name EXACTLY as the user wrote it, "
        "without grammatical suffixes (\"Ahmet'e\" → \"Ahmet\"). Never "
        "invent addresses; the client resolves names itself.\n"
        "- text: for messages, the exact message to send, written as the "
        "user would write it to that person (not a description).\n"
        f"- Today is {now:%Y-%m-%d} ({_WEEKDAYS[now.weekday()]}), the time "
        f"is {now:%H:%M}. Resolve relative dates (tomorrow, next Monday) "
        "to YYYY-MM-DD and times to 24-hour HH:MM.\n"
        "- If the request is unclear or a required field is missing, use "
        "action \"answer\" and ask a short question.\n"
        "- Questions about what someone said or what was decided in past "
        "messages → ask_history.\n"
        "- Fill unused fields with an empty string.\n"
        f"- reply: one short sentence in {lang} telling the user what you "
        "will do (or your answer for \"answer\").")


def user_prompt(text: str) -> str:
    return f"<request>\n{text}\n</request>"


def _clip(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def normalize_plan(data) -> dict:
    if not isinstance(data, dict):
        raise AIError("Model beklenen biçimde yanıt vermedi; tekrar deneyin.")
    plan = {key: _clip(data.get(key), _LIMITS.get(key, 40))
            for key in _FIELDS}
    if plan["action"] not in ACTIONS:
        plan["action"] = "answer"
    if plan["status"] not in STATUS_LABELS:
        plan["status"] = ""
    plan["target"] = strip_suffix(plan["target"])
    return plan


def parse_plan(text: str) -> dict:
    return normalize_plan(_loads_json(text))


def check_plan(plan: dict, now: datetime) -> str | None:
    """Eksik/geçersiz alan için kullanıcıya gösterilecek açıklama ya da None."""
    action = plan["action"]
    if action in TARGET_ACTIONS and not plan["target"]:
        return "Hangi kişi ya da oda için? Adını da yazın."
    if action == "join_room" and not plan["target"]:
        return "Hangi odaya katılmak istiyorsunuz?"
    if action in TEXT_ACTIONS and not plan["text"]:
        return ("Ne sormak istiyorsunuz?" if action == "ask_history"
                else "Mesaj ya da hatırlatıcı metni eksik.")
    if action == "set_status" and plan["status"] not in STATUS_LABELS:
        return "Hangi durum? (çevrimiçi, uzakta, meşgul)"
    if action == "remind":
        d, t = parse_date(plan["date"]), parse_time(plan["time"])
        if not d or not t:
            return "Hatırlatıcı için tarih ve saat gerekli (ör. yarın 10:00)."
        if datetime.combine(d, t) <= now:
            return "Hatırlatıcı zamanı geçmişte kalıyor."
    return None


# ── Hedef çözümleme (yerel) ─────────────────────────────────────────────────
_SUFFIX_RE = re.compile(r"['’`´][^\s'’`´]*$")


def strip_suffix(name: str) -> str:
    """"Ahmet'e" → "Ahmet" (Türkçe hâl eki kesme işaretinden sonra)."""
    return _SUFFIX_RE.sub("", (name or "").strip()).strip()


def fold(value: str) -> str:
    """Büyük/küçük harf ve Türkçe karakter duyarsız karşılaştırma anahtarı."""
    text = str(value or "").replace("İ", "i").replace("I", "ı").casefold()
    text = unicodedata.normalize("NFKD", text.replace("ı", "i"))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).strip()


def _score(query: str, jid: str, label: str) -> int:
    j, lbl = fold(jid), fold(label)
    local = j.split("@")[0]
    if query == j:
        return 100
    if lbl and query == lbl:
        return 95
    if query == local:
        return 90
    words = lbl.split() + re.split(r"[._\-]", local)
    if any(w.startswith(query) for w in words if w):
        return 80
    if len(query) >= 3 and (query in lbl or query in j):
        return 70
    ratio = max(difflib.SequenceMatcher(None, query, lbl).ratio() if lbl
                else 0.0, difflib.SequenceMatcher(None, query, local).ratio())
    return int(60 * ratio) if ratio >= 0.75 else 0


def resolve_target(name: str, targets, limit: int = 5) -> list:
    """En iyi eşleşen hedefler: [(jid, etiket)].

    `targets`: [(jid, etiket)]. Boş liste → bulunamadı; tek öğe → kesin;
    birden çok → aynı puanda belirsiz (kullanıcı seçer).
    """
    query = fold(strip_suffix(name))
    if not query:
        return []
    scored = [(s, jid, label) for jid, label in targets
              if (s := _score(query, jid, label or ""))]
    if not scored:
        return []
    best = max(s for s, _j, _l in scored)
    hits = sorted(((jid, label) for s, jid, label in scored if s == best),
                  key=lambda h: (fold(h[1] or h[0]), h[0]))
    return hits[:limit]


# ── Onay kartı ve yürütme yardımcıları ──────────────────────────────────────
def describe(plan: dict, label: str = "", jid: str = "") -> tuple[str, str]:
    """Onay kartının (başlık, ayrıntı) metni."""
    action = plan["action"]
    who = f"{label} ({jid})" if label and jid and label != jid else (
        jid or label)
    if action == "send_message":
        return "📨 Mesaj gönderilsin mi?", f"Alıcı: {who}\n“{plan['text']}”"
    if action == "remind":
        d, t = parse_date(plan["date"]), parse_time(plan["time"])
        when = (f"{d:%d.%m.%Y} {t:%H:%M}" if d and t
                else f"{plan['date']} {plan['time']}")
        extra = f" · {who}" if who else ""
        return "⏰ Hatırlatıcı kurulsun mu?", f"{when} — {plan['text']}{extra}"
    if action == "join_room":
        return "🚪 Odaya katılınsın mı?", who
    if action == "set_status":
        return ("● Durum değiştirilsin mi?",
                label or STATUS_LABELS.get(plan["status"], plan["status"]))
    return "", ""


def reminder_item(plan: dict) -> dict:
    """Mevcut hatırlatıcı yolunun (ai.validate_actions) öğe biçimi."""
    return {"kind": "task", "title": plan["text"], "date": plan["date"],
            "time": plan["time"], "location": "", "notes": ""}
