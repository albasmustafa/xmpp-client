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

Bağlam: asistan açık sohbeti bilir. Hedef yazılmazsa ya da "bu sohbet"
denirse o sohbet kullanılır (`is_context_ref`); sohbetin adı modele gitmez,
model yalnız boş hedef döndürür. Sık komutlar (`quick_intent`) ve hızlı
eylem düğmeleri (`quick_actions`) modele plan sordurmadan çalışır.
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
    "summarize_unread": "Summarize only the unread messages of a chat. "
                        "Needs target.",
    "extract_tasks": "Extract tasks and events from a chat. Needs target.",
    "suggest_replies": "Suggest short replies the user could send in a "
                       "chat. Needs target.",
    "missed": "Summarize all unread messages (what did I miss).",
    "ask_history": "Search the user's past messages and answer a question "
                   "about them. text = the question.",
    "pending_questions": "Show questions the user has not answered yet.",
    "drafts": "Show the reply drafts prepared while the user was away.",
}
CONFIRM_ACTIONS = frozenset({"send_message", "remind", "join_room",
                             "set_status"})
TARGET_ACTIONS = frozenset({"open_chat", "draft_message", "send_message",
                            "summarize_chat", "summarize_unread",
                            "extract_tasks", "suggest_replies"})
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


def system_prompt(now: datetime, lang: str, has_context: bool = False) -> str:
    actions = "\n".join(f"- {name}: {desc}" for name, desc in ACTIONS.items())
    context = (
        "- A chat is open in the client now. If the user means that chat "
        "(\"this chat\", \"bunu\", \"burası\") or names nobody for an "
        "action that needs a target, leave target empty; the client uses "
        "the open chat.\n" if has_context else "")
    return (
        "You are the built-in assistant of an XMPP chat client. Turn the "
        "user's request into exactly ONE action and answer as JSON.\n"
        f"Actions:\n{actions}\n\n"
        "Rules:\n"
        "- target: the contact or room name EXACTLY as the user wrote it, "
        "without grammatical suffixes (\"Ahmet'e\" → \"Ahmet\"). Never "
        "invent addresses; the client resolves names itself.\n"
        f"{context}"
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


def check_plan(plan: dict, now: datetime,
               has_context: bool = False) -> str | None:
    """Eksik/geçersiz alan için kullanıcıya gösterilecek açıklama ya da None.
    `has_context`: açık sohbet var; boş hedef / "bu sohbet" ona gider."""
    action = plan["action"]
    if action in TARGET_ACTIONS and is_context_ref(plan["target"]) and (
            not has_context):
        return ("Hangi kişi ya da oda için? Adını yazın ya da önce "
                "sohbeti açın.")
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
# Açık sohbeti gösteren hedefler (fold'lanmış; bkz. is_context_ref)
_CONTEXT_REFS = frozenset({
    "bu", "bunu", "buna", "bunun", "burasi", "burayi", "buraya", "burada",
    "bu sohbet", "bu sohbeti", "bu sohbete", "bu sohbetin", "bu sohbette",
    "bu kisi", "bu kisiye", "bu kisiyle", "bu kisinin", "bu oda",
    "bu odayi", "bu odaya", "bu odanin", "acik sohbet", "sohbet",
    "this", "this chat", "here", "current chat", "the open chat"})


def strip_suffix(name: str) -> str:
    """"Ahmet'e" → "Ahmet" (Türkçe hâl eki kesme işaretinden sonra)."""
    return _SUFFIX_RE.sub("", (name or "").strip()).strip()


def fold(value: str) -> str:
    """Büyük/küçük harf ve Türkçe karakter duyarsız karşılaştırma anahtarı."""
    text = str(value or "").replace("İ", "i").replace("I", "ı").casefold()
    text = unicodedata.normalize("NFKD", text.replace("ı", "i"))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).strip()


def is_context_ref(target: str) -> bool:
    """Hedef boş ya da açık sohbeti gösteriyor mu ("bu sohbet", "bunu")?"""
    key = " ".join(fold(strip_suffix(target)).split())
    return not key or key in _CONTEXT_REFS


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


# ── Modelsiz kısa yollar ────────────────────────────────────────────────────
# Sık komutlar plan için modele gitmez (yerel küçük modelde iki bekleme
# yerine bir). Yalnız TAM ifade eşleşir; ad ya da ayrıntı içeren her istek
# modele gider.
_QUICK_PHRASES = {
    "missed": ("neler kacirdim", "ne kacirdim", "neleri kacirdim",
               "kacirdiklarim", "kacirdiklarimi ozetle", "what did i miss"),
    "summarize_chat": ("ozetle", "ozet", "ozet cikar", "sohbeti ozetle",
                       "bu sohbeti ozetle", "summarize"),
    "summarize_unread": ("okunmamislari ozetle", "okunmamis ozeti",
                         "okunmamislarin ozeti"),
    "extract_tasks": ("gorevleri cikar", "gorevler", "etkinlikleri cikar",
                      "gorev ve etkinlikleri cikar"),
    "suggest_replies": ("yanit oner", "cevap oner", "ne yazayim",
                        "ne cevap vereyim", "suggest a reply"),
    "pending_questions": ("sorular", "bekleyen sorular",
                          "yanit bekleyen sorular", "cevap bekleyen sorular"),
    "drafts": ("taslaklar", "yanit taslaklari"),
}
_QUICK_INDEX = {phrase: action for action, phrases in _QUICK_PHRASES.items()
                for phrase in phrases}
# "Geçmişe sor: <soru>" → doğrudan ask_history (soru olduğu gibi)
HISTORY_PREFIX = "Geçmişe sor: "
_HISTORY_RE = re.compile(r"^\s*(?:geçmişe|gecmise|geçmiş|gecmis)\s*"
                         r"(?:sor)?\s*[:：]\s*(.*)$",
                         re.IGNORECASE | re.DOTALL)


def quick_intent(text: str) -> dict | None:
    """Model gerektirmeyen komutun planı ya da None (→ model)."""
    m = _HISTORY_RE.match(text or "")
    if m:
        return normalize_plan({"action": "ask_history",
                               "text": m.group(1).strip()})
    key = " ".join(fold(text).strip(" ?!.…").split())
    action = _QUICK_INDEX.get(key)
    return normalize_plan({"action": action}) if action else None


def quick_actions(chat: str = "", unread: int = 0, missed: int = 0,
                  drafts: int = 0) -> list[tuple[str, str]]:
    """Asistanın hızlı eylem düğmeleri: [(etiket, eylem)].

    `chat`: açık sohbetin etiketi ("" = yok) · `unread`: o sohbette açılışta
    okunmamış sayısı · `missed`: tüm okunmamışlar · `drafts`: hazır taslak.
    "ask_history" düğmesi soru kutusunu açar (soruyu kullanıcı yazar).
    """
    items = []
    if chat:
        if unread:
            items.append((f"📝 Okunmamışları özetle ({unread})",
                          "summarize_unread"))
        items += [("📝 Sohbeti özetle", "summarize_chat"),
                  ("💡 Yanıt öner", "suggest_replies"),
                  ("📅 Görevleri çıkar", "extract_tasks")]
    items.append(("📥 Neler kaçırdım?" + (f" ({missed})" if missed else ""),
                  "missed"))
    items.append(("❓ Bekleyen sorular", "pending_questions"))
    if drafts:
        items.append((f"📝 Taslaklar ({drafts})", "drafts"))
    items.append(("💬 Geçmişe sor…", "ask_history"))
    return items
