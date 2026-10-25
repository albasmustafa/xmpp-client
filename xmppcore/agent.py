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

from xmppcore.i18n import N_
from xmppcore.i18n import tr as _tr

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
    "set_status": "Change the user's presence. status = online (çevrimiçi, "
                  "müsait) | away (uzakta) | dnd (meşgul, rahatsız "
                  "etmeyin) | xa (uzun süre uzakta).",
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
STATUS_LABELS = {"online": N_("Çevrimiçi"), "away": N_("Uzakta"),
                 "dnd": N_("Meşgul"), "xa": N_("Uzun süre uzakta")}

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


def normalize_plan(data, request: str = "") -> dict:
    """Model çıktısını plana çevir. `request`: kullanıcının yazdığı metin;
    durum değişikliğinde oradaki durum sözü modelin seçiminden önce gelir."""
    if not isinstance(data, dict):
        raise AIError(_tr("Model beklenen biçimde yanıt vermedi; tekrar deneyin."))
    plan = {key: _clip(data.get(key), _LIMITS.get(key, 40))
            for key in _FIELDS}
    if plan["action"] not in ACTIONS:
        plan["action"] = "answer"
    if plan["status"] not in STATUS_LABELS:
        plan["status"] = ""
    if plan["action"] == "set_status":
        plan["status"] = status_hint(request) or plan["status"]
    plan["target"] = strip_suffix(plan["target"])
    return plan


def parse_plan(text: str, request: str = "") -> dict:
    return normalize_plan(_loads_json(text), request)


# ── Durum sözleri (yerel) ───────────────────────────────────────────────────
# Küçük yerel model "meşgul"ü away/xa planlayabiliyor: kullanıcının yazdığı
# durum sözü kesin eşlenir. (fold'lanmış söz, durum, ek alabilir mi); uzun
# ifade önce ("uzun süre uzakta" "uzakta"dan önce)
_STATUS_WORDS = (
    ("uzun sureli uzakta", "xa", True), ("uzun sure uzakta", "xa", True),
    ("extended away", "xa", False),
    ("rahatsiz etme", "dnd", True), ("do not disturb", "dnd", False),
    ("mesgul", "dnd", True), ("busy", "dnd", False), ("dnd", "dnd", False),
    ("uzakta", "away", True), ("away", "away", False), ("afk", "away", False),
    ("cevrimici", "online", True), ("musait", "online", True),
    ("online", "online", False), ("available", "online", False),
)
_STATUS_RES = tuple(
    (re.compile(r"(?<![a-z0-9])" + re.escape(word)
                + ("" if suffix else r"(?![a-z0-9])")), show)
    for word, show, suffix in _STATUS_WORDS)
_NEGATION_RE = re.compile(
    r"(?<![a-z0-9])(?:degil|not(?![a-z0-9])|yapma(?:yin|yiniz)?(?![a-z0-9]))"
    r"|n't")
# Durumdan çıkış ("meşgulden çıkar", "uzaktan dön", "modundan çık"): hangi
# duruma geçileceği belli değil — karar modelin (onay kartı yine gelir)
_LEAVE_RE = re.compile(r"(?<![a-z0-9])(?:mesgul|uzak|cevrimici|musait|mod)"
                       r"[a-z]*(?:den|dan|ten|tan)(?![a-z0-9])")


def status_hint(text: str) -> str | None:
    """Metindeki durum sözü → durum ("meşgulüm" → dnd) ya da None.

    Olumsuzsa ("meşgul değilim", "meşgul yapma"), durumdan çıkışsa
    ("meşgulden çıkar") ya da birden çok farklı durum geçiyorsa None: karar
    modele kalır.
    """
    rest, found = fold(text), set()
    if _LEAVE_RE.search(rest):
        return None
    for rx, show in _STATUS_RES:
        rest, hits = rx.subn(" ", rest)
        if hits:
            found.add(show)
    if len(found) != 1 or _NEGATION_RE.search(rest):
        return None
    return found.pop()


def check_plan(plan: dict, now: datetime,
               has_context: bool = False) -> str | None:
    """Eksik/geçersiz alan için kullanıcıya gösterilecek açıklama ya da None.
    `has_context`: açık sohbet var; boş hedef / "bu sohbet" ona gider."""
    action = plan["action"]
    if action in TARGET_ACTIONS and is_context_ref(plan["target"]) and (
            not has_context):
        return (_tr("Hangi kişi ya da oda için? Adını yazın ya da önce "
                    "sohbeti açın."))
    if action == "join_room" and not plan["target"]:
        return _tr("Hangi odaya katılmak istiyorsunuz?")
    if action in TEXT_ACTIONS and not plan["text"]:
        return (_tr("Ne sormak istiyorsunuz?") if action == "ask_history"
                else _tr("Mesaj ya da hatırlatıcı metni eksik."))
    if action == "set_status" and plan["status"] not in STATUS_LABELS:
        return _tr("Hangi durum? (çevrimiçi, uzakta, meşgul)")
    if action == "remind":
        d, t = parse_date(plan["date"]), parse_time(plan["time"])
        if not d or not t:
            return _tr("Hatırlatıcı için tarih ve saat gerekli (ör. yarın 10:00).")
        if datetime.combine(d, t) <= now:
            return _tr("Hatırlatıcı zamanı geçmişte kalıyor.")
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
        return _tr("📨 Mesaj gönderilsin mi?"), _tr("Alıcı: {}\n“{}”").format(who, plan['text'])
    if action == "remind":
        d, t = parse_date(plan["date"]), parse_time(plan["time"])
        when = (f"{d:%d.%m.%Y} {t:%H:%M}" if d and t
                else f"{plan['date']} {plan['time']}")
        extra = f" · {who}" if who else ""
        return _tr("⏰ Hatırlatıcı kurulsun mu?"), f"{when} — {plan['text']}{extra}"
    if action == "join_room":
        return _tr("🚪 Odaya katılınsın mı?"), who
    if action == "set_status":
        return (_tr("● Durum değiştirilsin mi?"),
                label or _tr(STATUS_LABELS.get(plan["status"], plan["status"])))
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
               "kacirdiklarim", "kacirdiklarimi ozetle", "what did i miss",
               "what have i missed"),
    "summarize_chat": ("ozetle", "ozet", "ozet cikar", "sohbeti ozetle",
                       "bu sohbeti ozetle", "summarize", "summarize this chat",
                       "summarize the chat"),
    "summarize_unread": ("okunmamislari ozetle", "okunmamis ozeti",
                         "okunmamislarin ozeti", "summarize unread"),
    "extract_tasks": ("gorevleri cikar", "gorevler", "etkinlikleri cikar",
                      "gorev ve etkinlikleri cikar", "extract tasks"),
    "suggest_replies": ("yanit oner", "cevap oner", "ne yazayim",
                        "ne cevap vereyim", "suggest a reply",
                        "suggest replies"),
    "pending_questions": ("sorular", "bekleyen sorular",
                          "yanit bekleyen sorular", "cevap bekleyen sorular",
                          "pending questions", "unanswered questions"),
    "drafts": ("taslaklar", "yanit taslaklari", "drafts", "reply drafts"),
}
_QUICK_INDEX = {phrase: action for action, phrases in _QUICK_PHRASES.items()
                for phrase in phrases}
# "Geçmişe sor: <soru>" (İngilizce arayüzde "Ask history: <soru>") →
# doğrudan ask_history (soru olduğu gibi)
HISTORY_PREFIX = N_("Geçmişe sor: ")
_HISTORY_RE = re.compile(r"^\s*(?:(?:geçmişe|gecmise|geçmiş|gecmis)\s*(?:sor)?"
                         r"|ask\s+(?:the\s+)?history)\s*[:：]\s*(.*)$",
                         re.IGNORECASE | re.DOTALL)
# "Durumumu meşgul yap", "meşgule geç", "durum: uzakta" (fold'lanmış,
# noktalamasız). Fiilsiz yalnız "durum…" ile başlayınca; soru ("durumu
# meşgul mü"), olumsuz ve ad içeren istekler modele gider.
_STATUS_KW = "|".join(re.escape(word) for word, _s, _x in _STATUS_WORDS)
_STATUS_VERB = (r"(?:olarak\s+)?(?:yap|ol|ayarla|isaretle|gec"
                r"|moduna\s+(?:al|gec|gecir))")
_STATUS_CMD_RE = re.compile(
    rf"^(?:(?:benim\s+)?durum(?:um|umu|u)?\s+(?:{_STATUS_KW})[a-z]*"
    rf"(?:\s+{_STATUS_VERB})?"
    rf"|(?:beni\s+|kendimi\s+)?(?:{_STATUS_KW})[a-z]*\s+{_STATUS_VERB}"
    # İngilizce: "set my status to busy", "status busy", "make me away"
    rf"|(?:set\s+)?(?:my\s+)?status\s+(?:to\s+)?(?:{_STATUS_KW})"
    rf"|(?:set|make)\s+me\s+(?:{_STATUS_KW}))$")


def quick_intent(text: str) -> dict | None:
    """Model gerektirmeyen komutun planı ya da None (→ model)."""
    m = _HISTORY_RE.match(text or "")
    if m:
        return normalize_plan({"action": "ask_history",
                               "text": m.group(1).strip()})
    key = " ".join(fold(text).strip(" ?!.…").split())
    action = _QUICK_INDEX.get(key)
    if action:
        return normalize_plan({"action": action})
    words = " ".join(re.sub(r"[^\w\s]", " ", key).split())
    status = status_hint(words) if _STATUS_CMD_RE.match(words) else None
    if status:
        return normalize_plan({"action": "set_status", "status": status})
    return None


# Hızlı eylem / menü / kısayol etiketleri (asistanda komut balonu olur);
# simgeler birbirinden farklıdır (⋮ menüsü de aynılarını kullanır)
ACTION_LABELS = {
    "summarize_unread": N_("📬 Okunmamışları özetle"),
    "summarize_chat": N_("📝 Sohbeti özetle"),
    "suggest_replies": N_("💡 Yanıt öner"),
    "extract_tasks": N_("📅 Görevleri çıkar"),
    "missed": N_("📥 Neler kaçırdım?"),
    "pending_questions": N_("❓ Bekleyen sorular"),
    "drafts": N_("✍ Taslaklar"),
    "ask_history": N_("🔎 Geçmişe sor…"),
}
# Grup başlıkları ⋮ menüsündeki alt menülerle aynı
QUICK_GROUP_CHAT = N_("💬 Bu sohbet")
QUICK_GROUP_ALL = N_("🗂 Tüm sohbetler")


def quick_action_groups(chat: str = "", unread: int = 0, missed: int = 0,
                        drafts: int = 0) -> list[tuple[str, list]]:
    """Asistanın hızlı eylem düğmeleri, gruplu: [(başlık, [(etiket, eylem)])].

    `chat`: açık sohbetin etiketi ("" = yok; o zaman yalnız genel grup) ·
    `unread`: o sohbette açılışta okunmamış sayısı · `missed`: tüm
    okunmamışlar · `drafts`: hazır taslak. "ask_history" düğmesi soru
    kartını açar (soruyu kullanıcı yazar).
    """
    def item(key, count=0):
        label = _tr(ACTION_LABELS[key])
        return (f"{label} ({count})" if count else label, key)
    groups = []
    if chat:
        this = [item("summarize_unread", unread)] if unread else []
        this += [item("summarize_chat"), item("suggest_replies"),
                 item("extract_tasks")]
        groups.append((_tr(QUICK_GROUP_CHAT), this))
    every = [item("missed", missed), item("pending_questions")]
    if drafts:
        every.append(item("drafts", drafts))
    every.append(item("ask_history"))
    groups.append((_tr(QUICK_GROUP_ALL), every))
    return groups


def quick_actions(chat: str = "", unread: int = 0, missed: int = 0,
                  drafts: int = 0) -> list[tuple[str, str]]:
    """`quick_action_groups`'un düz listesi: [(etiket, eylem)]."""
    return [i for _title, items in quick_action_groups(
        chat, unread, missed, drafts) for i in items]
