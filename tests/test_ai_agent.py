"""AI ajanı / ✨ Asistan (xmppcore/agent + MainWindow + AssistantWindow).

Kanıtlar:
- Plan: bilinmeyen eylem "answer"a düşer, alanlar kırpılır, hâl eki
  ayıklanır; eksik/geçersiz alan kullanıcıya açıklanır, eylem yapılmaz;
  şema tüm alanları zorunlu tutar (yapılandırılmış çıktı).
- Hedef YEREL çözülür (Türkçe harf/ek duyarsız, yazım hatası toleranslı);
  eşit puanlı adaylar belirsizdir → kullanıcı seçer; kişi listesi modele
  hiç gönderilmez.
- Gönderme/hatırlatıcı/odaya katılma/durum her zaman onay kartı ister;
  diğerleri mevcut pencereleri açar. Gönderim normal giriş kutusu yolundan
  geçer; kullanıcının sohbeti ve yarım taslağı geri yüklenir; "/" komutu
  ve bağlantısız durum reddedilir.
- Pencere kapandıysa gelen plan YÜRÜTÜLMEZ; "Temizle" sırasında gelen
  yanıt atılır ve pencere meşgul kalmaz.
- Görünüm: örnek tıklaması gönderir, meşgulken gönderim yok, kart
  düğmeleri bir kez çalışır, hata kartı kilitlemez.
- Bağlam: hedef yazılmazsa ya da "bu sohbet" denirse açık sohbet kullanılır
  (adı modele gitmez); açık sohbet yoksa ad istenir. Sık komutlar ve hızlı
  eylem düğmeleri modele plan sordurmadan çalışır.
"""
import inspect
import json
import os
import sys
import types
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ai_dialog_view import _W, _find, fake_tk  # noqa: E402,F401
from test_history_window_bounds import _Cap  # noqa: E402

import ui.dialogs.ai as ui_ai  # noqa: E402
import xmpp  # noqa: E402
from xmppcore import agent, ai  # noqa: E402

NOW = datetime(2026, 10, 10, 12, 0)
TARGETS = [("ahmet.yilmaz@x.org", "Ahmet Yılmaz"),
           ("ahmet.kaya@x.org", "Ahmet Kaya"), ("ayse@x.org", "Ayşe"),
           ("isil@x.org", "IŞIL"), ("proje@conf.x.org", "proje")]


def _plan(**kw):
    base = {"action": "answer", "reply": "", "target": "", "text": "",
            "date": "", "time": "", "status": ""}
    base.update(kw)
    return base


# ── 1) Plan ─────────────────────────────────────────────────────────────────
def test_normalize_plan_defaults_and_clipping():
    p = agent.normalize_plan({"action": "rm_rf", "target": "Ali'ye",
                              "status": "invisible", "text": "x" * 9000})
    assert p["action"] == "answer" and p["target"] == "Ali"
    assert p["status"] == "" and len(p["text"]) == 4000
    assert set(p) == set(agent.PLAN_SCHEMA["properties"])
    with pytest.raises(ai.AIError):
        agent.normalize_plan(["liste"])


def test_parse_plan_accepts_fenced_json():
    raw = "```json\n" + json.dumps(_plan(action="missed")) + "\n```"
    assert agent.parse_plan(raw)["action"] == "missed"


def test_schema_is_strict_and_complete():
    sch = agent.PLAN_SCHEMA
    assert sch["additionalProperties"] is False
    assert set(sch["required"]) == set(sch["properties"])
    assert set(sch["properties"]["action"]["enum"]) == set(agent.ACTIONS)


@pytest.mark.parametrize("plan,needle", [
    (_plan(action="send_message", text="selam"), "Hangi kişi"),
    (_plan(action="send_message", target="Ali"), "metni eksik"),
    (_plan(action="ask_history"), "Ne sormak"),
    (_plan(action="join_room"), "Hangi odaya"),
    (_plan(action="set_status", status=""), "Hangi durum"),
    (_plan(action="remind", text="x", date="2026-10-11"), "tarih ve saat"),
    (_plan(action="remind", text="x", date="2026-10-09", time="10:00"),
     "geçmişte"),
])
def test_check_plan_explains_problems(plan, needle):
    assert needle in agent.check_plan(plan, NOW)


def test_check_plan_accepts_valid():
    assert agent.check_plan(_plan(action="remind", text="x",
                                  date="2026-10-11", time="10:00"), NOW) is None
    assert agent.check_plan(_plan(action="missed"), NOW) is None


def test_system_prompt_has_date_and_actions():
    text = agent.system_prompt(NOW, "Türkçe")
    assert "2026-10-10 (Saturday)" in text and "12:00" in text
    assert all(name in text for name in agent.ACTIONS)
    assert "Never invent addresses" in text and "Türkçe" in text
    assert agent.user_prompt("selam") == "<request>\nselam\n</request>"


# ── 2) Yerel hedef çözümleme ────────────────────────────────────────────────
@pytest.mark.parametrize("name,expected", [
    ("ayşe", ["ayse@x.org"]),
    ("AYŞE'ye", ["ayse@x.org"]),
    ("Işıl", ["isil@x.org"]),
    ("ISIL", ["isil@x.org"]),
    ("ahmet.kaya@x.org", ["ahmet.kaya@x.org"]),
    ("Yılmaz", ["ahmet.yilmaz@x.org"]),
    ("aysee", ["ayse@x.org"]),
    ("Ahmet'e", ["ahmet.kaya@x.org", "ahmet.yilmaz@x.org"]),
    ("Mehmet", []),
    ("", []),
])
def test_resolve_target(name, expected):
    assert [j for j, _l in agent.resolve_target(name, TARGETS)] == expected


def test_describe_and_reminder_item():
    t, d = agent.describe(_plan(action="send_message", text="selam"),
                          "Ali", "ali@x")
    assert t.startswith("📨") and d == "Alıcı: Ali (ali@x)\n“selam”"
    t, d = agent.describe(_plan(action="remind", text="fatura",
                                date="2026-10-11", time="9:05"), "", "")
    assert d == "11.10.2026 09:05 — fatura"
    assert agent.describe(_plan(action="set_status", status="dnd"),
                          "Meşgul")[1] == "Meşgul"
    valid, errors = ai.validate_actions([agent.reminder_item(
        _plan(text="fatura", date="2026-10-11", time="09:00"))])
    assert errors == [] and valid[0]["title"] == "fatura"


# ── 3) MainWindow akışları ──────────────────────────────────────────────────
class _FakeWin:
    def __init__(self):
        self.events, self.cards, self.choices = [], [], []
        self.alive_flag = True
        self.busy = None

    def alive(self):
        return self.alive_flag

    def add_user(self, t):
        self.events.append(("user", t))

    def add_reply(self, t):
        self.events.append(("reply", t))

    def add_note(self, t, error=False):
        self.events.append(("error" if error else "note", t))

    def add_card(self, title, detail, buttons):
        self.cards.append((title, detail, dict(buttons)))

    def add_choices(self, prompt, options, on_pick):
        self.choices.append((prompt, options, on_pick))

    def set_busy(self, m):
        self.busy = m

    def set_subtitle(self, t):
        pass

    def set_quick_actions(self, context, groups):
        self.quick = (context, list(groups))

    def prefill(self, t):
        self.events.append(("prefill", t))

    def clear(self):
        self.events.clear()

    def focus(self):
        self.events.append(("focus", None))


@pytest.fixture()
def aw(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = None
    w.jid = "me@x.org"
    w.active = None
    w._contacts = {j: n for j, n in TARGETS if "conf" not in j}
    w.rooms = {"proje@conf.x.org": {}}
    w.bot = types.SimpleNamespace(muc_service="conf.x.org")
    w._ai_assistant_win = _FakeWin()
    w._ai_warmed = []
    monkeypatch.setattr(xmpp._ai, "ollama_warm", w._ai_warmed.append)
    cfg = {"ai": {"provider": "ollama"}}
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    w.cfg = cfg
    replies, calls = [], []

    def fake_chat(settings, system, user, **kw):
        calls.append((system, user, kw))
        return json.dumps(replies.pop(0))
    monkeypatch.setattr(xmpp._ai, "chat", fake_chat)

    def submit(job, done, err):
        try:
            result = job()
        except ai.AIError as e:
            err(e)
            return
        done(result)
    w._ai_submit = submit
    w.replies, w.calls = replies, calls
    return w


def _say(w, text, plan):
    w.replies.append(plan)
    xmpp.MainWindow._ai_agent_submit(w, text)
    return w._ai_assistant_win


def test_answer_turn_and_history(aw):
    win = _say(aw, "merhaba", _plan(reply="Merhaba! Nasıl yardım edeyim?"))
    assert win.events == [("user", "merhaba"),
                          ("reply", "Merhaba! Nasıl yardım edeyim?")]
    assert win.busy is None
    system, user, kw = aw.calls[0]
    assert kw["schema"] is agent.PLAN_SCHEMA and kw["history"] == []
    assert "Ayşe" not in system + user           # kişi listesi gitmez
    _say(aw, "teşekkürler", _plan(reply="Rica ederim"))
    hist = aw.calls[1][2]["history"]
    assert hist[0] == ("user", "<request>\nmerhaba\n</request>")
    assert json.loads(hist[1][1])["reply"].startswith("Merhaba")
    assert aw._ai_agent_log[-1] == ("assistant", "Rica ederim")


def test_ai_off_is_reported(aw):
    aw.cfg["ai"]["provider"] = "off"
    xmpp.MainWindow._ai_agent_submit(aw, "neler kaçırdım")
    assert aw._ai_assistant_win.events[-1][0] == "error"
    assert aw.calls == []


def test_model_error_clears_busy(aw, monkeypatch):
    def boom(*a, **k):
        raise ai.AIError("Yerel model boş yanıt döndürdü.")
    monkeypatch.setattr(xmpp._ai, "chat", boom)
    xmpp.MainWindow._ai_agent_submit(aw, "x")
    win = aw._ai_assistant_win
    assert win.busy is None and win.events[-1] == (
        "error", "⚠ Yerel model boş yanıt döndürdü.")


def test_send_message_needs_confirmation(aw):
    aw._ai_agent_send = _Cap()
    win = _say(aw, "Ayşe'ye selam yaz", _plan(
        action="send_message", target="Ayşe", text="Selam!",
        reply="Ayşe'ye gönderiyorum."))
    (title, detail, buttons), = win.cards
    assert title == "📨 Mesaj gönderilsin mi?"
    assert detail == "Alıcı: Ayşe (ayse@x.org)\n“Selam!”"
    assert aw._ai_agent_send.calls == []         # onaysız gönderim yok
    assert buttons["✗ İptal"]() == ("İptal edildi.", False)
    buttons["✓ Onayla"]()
    assert aw._ai_agent_send.calls == [(("ayse@x.org", "Selam!"), {})]


def test_ambiguous_target_offers_choices(aw):
    win = _say(aw, "Ahmet'e yaz", _plan(action="send_message",
                                        target="Ahmet", text="Naber"))
    (prompt, options, pick), = win.choices
    assert [v for _l, v in options] == ["ahmet.kaya@x.org",
                                        "ahmet.yilmaz@x.org"]
    assert win.cards == []
    assert pick("ahmet.kaya@x.org") == ("✓ Seçildi", True)
    assert "ahmet.kaya@x.org" in win.cards[0][1]


def test_unknown_target_and_missing_field(aw):
    win = _say(aw, "Mehmet'i aç", _plan(action="open_chat", target="Mehmet"))
    assert win.events[-1] == ("error", "“Mehmet” adında bir kişi ya da oda "
                                       "bulunamadı.")
    win = _say(aw, "yaz", _plan(action="send_message", target="Ayşe"))
    assert win.events[-1] == ("reply", "Mesaj ya da hatırlatıcı metni eksik.")
    assert win.cards == []


INLINE = {"inline": True}


@pytest.mark.parametrize("plan,method,args,kwargs", [
    (_plan(action="open_chat", target="Işıl"), "_ai_open_chat",
     ("isil@x.org",), {}),
    (_plan(action="summarize_chat", target="ayse"), "_ai_summarize",
     ("ayse@x.org",), INLINE),
    (_plan(action="summarize_unread", target="ayse"), "_ai_summarize",
     ("ayse@x.org",), dict(INLINE, unread_only=True)),
    (_plan(action="suggest_replies", target="ayse"), "_ai_suggest_replies",
     ("ayse@x.org",), INLINE),
    (_plan(action="extract_tasks", target="proje"), "_ai_extract_actions",
     ("proje@conf.x.org",), {}),
    (_plan(action="missed"), "_ai_digest", (), INLINE),
    (_plan(action="pending_questions"), "_ai_pending_questions", (), INLINE),
    (_plan(action="drafts"), "_ai_drafts_window", (), {}),
    (_plan(action="ask_history", text="Adres neydi?"), "_ai_ask_history",
     ("Adres neydi?",), INLINE),
])
def test_safe_actions_run_immediately(aw, plan, method, args, kwargs):
    setattr(aw, method, _Cap())
    win = _say(aw, "komut", plan)
    assert getattr(aw, method).calls == [(args, kwargs)]
    assert win.cards == []
    # Sonucu asistanın içinde açılanlar ayrıca "pencere açıldı" notu düşmez
    assert (win.events[-1][0] == "note") is not kwargs.get("inline", False)


def test_remind_confirm_uses_reminder_path(aw):
    tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
    aw._ai_add_reminders = lambda items, jid: (
        aw.__dict__.setdefault("rem", []).append((items, jid)),
        (True, "⏰ 1 hatırlatıcı kuruldu."))[1]
    win = _say(aw, "yarın 9'da Ayşe'yi aramayı hatırlat", _plan(
        action="remind", text="Ayşe'yi ara", date=tomorrow, time="09:00",
        target="Ayşe"))
    (title, detail, buttons), = win.cards
    assert title.startswith("⏰") and "Ayşe (ayse@x.org)" in detail
    assert buttons["✓ Onayla"]() == ("⏰ 1 hatırlatıcı kuruldu.", True)
    (items, jid), = aw.rem
    assert jid == "ayse@x.org" and items[0]["time"] == "09:00"


def test_join_room_prefers_known_room_then_normalizes(aw):
    aw._join_room_normalized = lambda room, nick: (
        aw.__dict__.setdefault("joined", []).append((room, nick)), room)[1]
    win = _say(aw, "proje odasına katıl",
               _plan(action="join_room", target="proje"))
    assert win.cards[0][1] == "proje@conf.x.org"
    assert win.cards[0][2]["✓ Onayla"]()[1] is True
    assert aw.joined == [("proje@conf.x.org", "me")]
    win = _say(aw, "Yeni odasına katıl",
               _plan(action="join_room", target="Yeni"))
    assert win.cards[-1][1] == "yeni@conf.x.org"


def test_set_status_uses_app_labels(aw):
    aw._set_status = _Cap()
    win = _say(aw, "meşgul yap", _plan(action="set_status", status="dnd"))
    assert win.cards[0][1] == "Meşgul"
    win.cards[0][2]["✓ Onayla"]()
    assert aw._set_status.calls == [(("Meşgul", "dnd", xmpp.RED), {})]
    aw.bot = None
    assert xmpp.MainWindow._ai_agent_execute(
        aw, _plan(action="set_status", status="away"), "")[1] is False


def test_closed_window_executes_nothing(aw):
    aw._ai_open_chat = _Cap()
    win = aw._ai_assistant_win
    aw.replies.append(_plan(action="open_chat", target="Ayşe",
                            reply="Açıyorum"))

    def submit(job, done, err):
        result = job()
        win.alive_flag = False                    # yanıt gelmeden kapandı
        done(result)
    aw._ai_submit = submit
    xmpp.MainWindow._ai_agent_submit(aw, "Ayşe'yi aç")
    assert aw._ai_open_chat.calls == []
    assert aw._ai_agent_log[-1] == ("assistant", "Açıyorum")


def test_clear_during_flight_drops_reply_and_unblocks(aw):
    aw.replies.append(_plan(reply="geç yanıt"))
    win = aw._ai_assistant_win

    def submit(job, done, err):
        result = job()
        xmpp.MainWindow._ai_assistant_clear(aw)
        done(result)
    aw._ai_submit = submit
    xmpp.MainWindow._ai_agent_submit(aw, "x")
    assert win.busy is None
    assert ("reply", "geç yanıt") not in win.events
    assert aw._ai_agent_conv is None


# ── 4) Gönderim (normal giriş kutusu yolu) ──────────────────────────────────
@pytest.fixture()
def sender(aw):
    st = {"text": "yarım taslak", "sent": [], "allow": True}
    aw.active = "ayse@x.org"
    aw._ai_composer_text = lambda: st["text"]

    def set_text(t):
        st["text"] = t
    aw._ai_set_composer_text = set_text
    aw._composer = types.SimpleNamespace(clear_text=lambda: set_text(""))

    def offer(jid, text):
        aw.active = jid
        st["text"] = text
    aw._ai_offer_text = offer

    def send():
        if st["allow"]:                           # hassas veri uyarısı geçti
            st["sent"].append((aw.active, st["text"]))
            st["text"] = ""
    aw._send_message = send

    def open_chat(jid):
        aw.active = jid
    aw._ai_open_chat = open_chat
    aw.st = st
    return aw


def test_send_restores_chat_and_draft(sender):
    msg, ok = xmpp.MainWindow._ai_agent_send(sender, "ali@x", "Selam")
    assert ok and sender.st["sent"] == [("ali@x", "Selam")]
    assert sender.active == "ayse@x.org"
    assert sender.st["text"] == "yarım taslak"


def test_declined_send_reports_and_cleans(sender):
    sender.st.update(allow=False, text="")
    msg, ok = xmpp.MainWindow._ai_agent_send(sender, "ali@x", "şifre: 1234")
    assert not ok and "Gönderilmedi" in msg
    assert sender.st["sent"] == [] and sender.st["text"] == ""


def test_send_rejects_commands_and_offline(sender):
    assert xmpp.MainWindow._ai_agent_send(sender, "ali@x", "/clear")[1] is \
        False
    sender.bot = None
    assert xmpp.MainWindow._ai_agent_send(sender, "ali@x", "x")[1] is False
    assert sender.st["sent"] == []


# ── 5) Pencere açma, kenar çubuğu, kısayol ──────────────────────────────────
def test_open_reuses_window_and_replays_log(aw, monkeypatch):
    xmpp.MainWindow._ai_assistant_open(aw)
    assert aw._ai_assistant_win.events == [("focus", None)]
    created = []

    class _Win(_FakeWin):
        def __init__(self, parent, subtitle, on_submit, **kw):
            super().__init__()
            self.kw = kw
            created.append(self)
    monkeypatch.setattr(xmpp._ui_ai, "AssistantWindow", _Win)
    aw._ai_assistant_win.alive_flag = False
    aw._ai_agent_log = [("user", "a"), ("assistant", "b")]
    assert xmpp.MainWindow._ai_assistant_open(aw) == "break"
    assert created[0].events == [("user", "a"), ("reply", "b")]
    assert created[0].kw["on_speak"] == aw._ai_speak_text


def test_open_warms_local_model_in_background(aw, monkeypatch):
    """Asistan açılınca model arka planda belleğe yüklenir (ilk isteğin
    yükleme beklemesi — HDD'de dakikayı bulur — kullanıcıya düşmesin)."""
    started = []

    class _T:
        def __init__(self, target=None, args=(), daemon=None):
            self.target, self.args, self.daemon = target, args, daemon
            self.alive = True
            started.append(self)

        def start(self):
            self.target(*self.args)

        def is_alive(self):
            return self.alive
    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    monkeypatch.setattr(xmpp._ui_ai, "AssistantWindow",
                        lambda *a, **kw: _FakeWin())
    aw._ai_assistant_win.alive_flag = False
    xmpp.MainWindow._ai_assistant_open(aw)
    assert len(started) == 1 and started[0].daemon
    assert [s["provider"] for s in aw._ai_warmed] == ["ollama"]
    xmpp.MainWindow._ai_assistant_open(aw)            # açık pencere: yok
    aw._ai_assistant_win.alive_flag = False
    xmpp.MainWindow._ai_assistant_open(aw)            # önceki hâlâ sürüyor
    assert len(started) == 1
    started[0].alive = False
    aw._ai_assistant_win.alive_flag = False
    xmpp.MainWindow._ai_assistant_open(aw)
    assert len(started) == 2
    aw.cfg["ai"]["provider"] = "claude"               # bulutta yükleme yok
    started[1].alive = False
    aw._ai_assistant_win.alive_flag = False
    xmpp.MainWindow._ai_assistant_open(aw)
    assert len(started) == 2


def test_sidebar_entry_and_shortcuts_wired():
    sidebar_src = inspect.getsource(xmpp.MainWindow._build_sidebar)
    assert "build_assistant_entry" in sidebar_src
    assert "row=4" in sidebar_src[sidebar_src.index("build_assistant_entry"):]
    keys = inspect.getsource(xmpp.MainWindow._bind_shortcuts)
    assert '"<Control-Shift-K>", self._ai_assistant_open' in keys
    assert '"<Control-Shift-R>"' in keys


# ── 6) Görünüm (sahte tk) ───────────────────────────────────────────────────
@pytest.mark.usefixtures("fake_tk")
def test_assistant_view_examples_busy_and_cards():
    sent = []
    win = ui_ai.AssistantWindow(_W(), "alt", sent.append,
                                examples=("Neler kaçırdım?",))
    _find(win.top, "› Neler kaçırdım?").click()
    assert sent == ["Neler kaçırdım?"]
    win.set_busy("Düşünüyor…")
    win.submit_text("ikinci")
    assert sent == ["Neler kaçırdım?"]          # meşgulken gönderim yok
    win.set_busy(None)
    runs = []
    card = win.add_card("Başlık", "Ayrıntı", [
        ("✓ Onayla", lambda: runs.append(1) or ("✓ Gönderildi", True))])
    btn = _find(win.top, "✓ Onayla")
    btn.click()
    btn.click()                                  # çift tıklama
    assert runs == [1] and card.done
    assert card._result.kw["text"] == "✓ Gönderildi"


@pytest.mark.usefixtures("fake_tk")
def test_assistant_view_choice_cancel_and_failing_button():
    win = ui_ai.AssistantWindow(_W(), "alt", lambda t: None)
    card = win.add_choices("Belirsiz", [("A", "a")], lambda v: None)
    _find(win.top, "✗ Vazgeç").click()
    assert card._result.kw["text"] == "Vazgeçildi."

    def boom():
        raise RuntimeError("bozuk")
    card = win.add_card("T", "D", [("Çalıştır", boom)])
    with pytest.raises(RuntimeError):
        _find(win.top, "Çalıştır").click()
    assert card.done and card._result.kw["text"] == "⚠ bozuk"


# ── 7) Bağlam, modelsiz kısa yollar, hızlı eylemler ─────────────────────────
@pytest.mark.parametrize("text,action,qtext", [
    ("Neler kaçırdım?", "missed", ""),
    ("NE KAÇIRDIM", "missed", ""),
    ("özetle.", "summarize_chat", ""),
    ("okunmamışları özetle", "summarize_unread", ""),
    ("Yanıt öner", "suggest_replies", ""),
    ("görevleri çıkar", "extract_tasks", ""),
    ("bekleyen sorular", "pending_questions", ""),
    ("Taslaklar", "drafts", ""),
    ("Geçmişe sor: Ali'nin adresi neydi?", "ask_history",
     "Ali'nin adresi neydi?"),
    ("geçmiş:  toplantı ne zaman", "ask_history", "toplantı ne zaman"),
    ("Geçmişe sor:", "ask_history", ""),
])
def test_quick_intent_matches_exact_commands(text, action, qtext):
    plan = agent.quick_intent(text)
    assert (plan["action"], plan["text"], plan["target"]) == (action, qtext,
                                                              "")


@pytest.mark.parametrize("text", [
    "Ayşe ile sohbeti özetle", "Ali'ye yanıt öner", "özetle ve gönder",
    "merhaba", "", "sorular nerede kaldı"])
def test_quick_intent_leaves_detailed_requests_to_model(text):
    assert agent.quick_intent(text) is None


# "Durumumu meşgul yap" (2026-10-21): yerel model "meşgul"ü away (gemma4
# e2b) ya da xa (gemma3) planlıyordu; durum menüsü de "Uzakta"yı xa'ya
# bağlıyordu. Durum sözü kullanıcının metninden yerelde okunur.
@pytest.mark.parametrize("text,status", [
    ("Durumumu meşgul yap", "dnd"), ("MEŞGULÜM", "dnd"),
    ("rahatsız etmeyin moduna al", "dnd"),
    ("toplantıdayım, beni rahatsız etmesinler", "dnd"),
    ("set my status to do not disturb", "dnd"),
    ("uzaktayım", "away"), ("Uzun süre uzakta olacağım", "xa"),
    ("çevrimiçi ol", "online"), ("ÇEVRİMİÇİ", "online"),
    ("müsaitim artık", "online"),
    ("meşgul değilim", None), ("I'm not busy", None),
    ("uzakta ya da meşgul", None), ("Ali'ye selam yaz", None), ("", None),
])
def test_status_hint_reads_status_words(text, status):
    assert agent.status_hint(text) == status


@pytest.mark.parametrize("text,status", [
    ("Durumumu meşgul yap", "dnd"), ("meşgul ol", "dnd"),
    ("Meşgule geç.", "dnd"), ("rahatsız etmeyin moduna al", "dnd"),
    ("durum: uzakta", "away"), ("beni uzakta olarak işaretle", "away"),
    ("Uzun süre uzakta yap", "xa"), ("Çevrimiçi ol!", "online"),
])
def test_quick_intent_sets_status_without_model(text, status):
    plan = agent.quick_intent(text)
    assert (plan["action"], plan["status"]) == ("set_status", status)


@pytest.mark.parametrize("text", [
    "meşgulüm", "Ali'nin durumu meşgul mü?", "Ali'ye meşgul olduğumu yaz",
    "meşgul değilim", "durumumu değiştir", "meşgul olmak istiyorum"])
def test_quick_intent_leaves_unclear_status_to_model(text):
    assert agent.quick_intent(text) is None


def test_model_status_yields_to_users_word():
    raw = json.dumps(_plan(action="set_status", status="away"))
    assert agent.parse_plan(raw, request="Beni meşgul göster")[
        "status"] == "dnd"
    assert agent.parse_plan(raw)["status"] == "away"     # istek yok: model
    assert agent.parse_plan(raw, request="durumu değiştir")[
        "status"] == "away"
    msg = json.dumps(_plan(action="send_message", target="Ali",
                           text="Meşgulüm"))
    assert agent.parse_plan(msg, request="Ali'ye meşgul olduğumu yaz")[
        "status"] == ""


def test_set_status_description_names_turkish_words():
    desc = agent.ACTIONS["set_status"]
    for word in ("çevrimiçi", "uzakta", "meşgul", "rahatsız etmeyin",
                 "uzun süre uzakta"):
        assert word in desc


def test_status_command_through_model_uses_users_word(aw):
    win = _say(aw, "Toplantıdayım, beni meşgul göster",
               _plan(action="set_status", status="away"))
    assert win.cards[0][1] == "Meşgul"


def test_status_command_needs_no_model(aw):
    win = _say(aw, "Durumumu meşgul yap", _plan(reply="kullanılmamalı"))
    assert aw.calls == [] and win.cards[0][1] == "Meşgul"


def test_status_labels_share_one_vocabulary():
    assert xmpp.STATUS_OPTIONS == [(label, show) for show, label
                                   in agent.STATUS_LABELS.items()]
    assert dict(xmpp.STATUS_OPTIONS)["Uzakta"] == "away"
    assert xmpp.MainWindow._ai_status_option("xa")[0] == "Uzun süre uzakta"


@pytest.mark.parametrize("target,expected", [
    ("", True), ("bu sohbet", True), ("Bu Sohbet'e", True),
    ("bu kişiyle", True), ("BURASI", True), ("this chat", True),
    ("Ayşe", False), ("bu ayşe", False)])
def test_is_context_ref(target, expected):
    assert agent.is_context_ref(target) is expected


def test_check_plan_uses_open_chat_as_target():
    plan = _plan(action="summarize_chat")
    assert "önce sohbeti açın" in agent.check_plan(plan, NOW)
    assert agent.check_plan(plan, NOW, has_context=True) is None
    plan = _plan(action="send_message", target="bu sohbet", text="selam")
    assert agent.check_plan(plan, NOW, has_context=True) is None
    assert "Hangi kişi" in agent.check_plan(plan, NOW)


def test_system_prompt_mentions_open_chat_only_when_present():
    assert "A chat is open" not in agent.system_prompt(NOW, "Türkçe")
    assert "leave target empty" in agent.system_prompt(
        NOW, "Türkçe", has_context=True)


def test_quick_actions_follow_context():
    assert [k for _l, k in agent.quick_actions()] == [
        "missed", "pending_questions", "ask_history"]
    items = agent.quick_actions("Ayşe", unread=3, missed=7, drafts=2)
    assert items == [
        ("📬 Okunmamışları özetle (3)", "summarize_unread"),
        ("📝 Sohbeti özetle", "summarize_chat"),
        ("💡 Yanıt öner", "suggest_replies"),
        ("📅 Görevleri çıkar", "extract_tasks"),
        ("📥 Neler kaçırdım? (7)", "missed"),
        ("❓ Bekleyen sorular", "pending_questions"),
        ("✍ Taslaklar (2)", "drafts"),
        ("🔎 Geçmişe sor…", "ask_history")]
    assert all(k in agent.ACTIONS for _l, k in items)


def test_quick_action_groups_split_this_chat_from_all_chats():
    groups = agent.quick_action_groups("Ayşe", unread=3, missed=7, drafts=2)
    assert [t for t, _i in groups] == ["💬 Bu sohbet", "🗂 Tüm sohbetler"]
    assert [k for _l, k in groups[0][1]] == [
        "summarize_unread", "summarize_chat", "suggest_replies",
        "extract_tasks"]
    assert [i for _t, items in groups for i in items] == agent.quick_actions(
        "Ayşe", 3, 7, 2)
    # Açık sohbet yoksa yalnız genel grup
    assert [t for t, _i in agent.quick_action_groups()] == ["🗂 Tüm sohbetler"]


def test_action_icons_are_distinct():
    icons = [lbl.split()[0] for lbl in agent.ACTION_LABELS.values()]
    assert len(icons) == len(set(icons))


@pytest.mark.parametrize("target", ["", "bu sohbet"])
def test_open_chat_is_the_default_target(aw, target):
    aw.active = "ayse@x.org"
    aw._ai_summarize = _Cap()
    _say(aw, "bunu özetler misin", _plan(action="summarize_chat",
                                         target=target))
    assert aw._ai_summarize.calls == [(("ayse@x.org",), INLINE)]
    system = aw.calls[0][0]
    assert "A chat is open" in system and "Ayşe" not in system


def test_named_target_still_wins_over_open_chat(aw):
    aw.active = "ayse@x.org"
    aw._ai_summarize = _Cap()
    _say(aw, "Işıl ile sohbeti özetle", _plan(action="summarize_chat",
                                              target="Işıl"))
    assert aw._ai_summarize.calls == [(("isil@x.org",), INLINE)]


def test_without_open_chat_target_is_asked(aw):
    aw._ai_summarize = _Cap()
    win = _say(aw, "özetler misin", _plan(action="summarize_chat"))
    assert aw._ai_summarize.calls == []
    assert "önce sohbeti açın" in win.events[-1][1]


@pytest.mark.parametrize("text,method,args,kwargs", [
    ("Neler kaçırdım?", "_ai_digest", (), INLINE),
    ("özetle", "_ai_summarize", ("ayse@x.org",), INLINE),
    ("okunmamışları özetle", "_ai_summarize", ("ayse@x.org",),
     dict(INLINE, unread_only=True)),
    ("yanıt öner", "_ai_suggest_replies", ("ayse@x.org",), INLINE),
    ("taslaklar", "_ai_drafts_window", (), {}),
    ("Geçmişe sor: adres neydi?", "_ai_ask_history", ("adres neydi?",),
     INLINE),
])
def test_quick_commands_skip_the_model(aw, text, method, args, kwargs):
    aw.active = "ayse@x.org"
    setattr(aw, method, _Cap())
    xmpp.MainWindow._ai_agent_submit(aw, text)
    assert aw.calls == []                        # plan için model yok
    assert getattr(aw, method).calls == [(args, kwargs)]
    user, answer = aw._ai_agent_conv.turns[-2:]
    assert user == ("user", agent.user_prompt(text))
    assert json.loads(answer[1])["action"] == agent.quick_intent(
        text)["action"]


def test_quick_button_runs_without_model_and_history_opens_card(aw):
    aw.active = "ayse@x.org"
    aw._ai_summarize = _Cap()
    xmpp.MainWindow._ai_agent_quick(aw, "summarize_unread",
                                    "📬 Okunmamışları özetle (3)")
    win = aw._ai_assistant_win
    assert aw.calls == [] and win.events[0] == (
        "user", "📬 Okunmamışları özetle (3)")
    assert aw._ai_summarize.calls == [(("ayse@x.org",),
                                       dict(INLINE, unread_only=True))]
    aw._ai_ask_history = _Cap()
    n = len(win.events)
    xmpp.MainWindow._ai_agent_quick(aw, "ask_history", "🔎 Geçmişe sor…")
    assert aw._ai_ask_history.calls == [((), INLINE)]
    assert len(win.events) == n                  # kart başlığı yeter


def test_menu_and_shortcut_entry_runs_inside_assistant(aw):
    aw._ai_assistant_open = _Cap()
    aw._ai_summarize = _Cap()
    aw._ai_digest = _Cap()
    assert xmpp.MainWindow._ai_assistant_run(
        aw, "summarize_chat", "isil@x.org") == "break"
    assert aw._ai_summarize.calls == [(("isil@x.org",), INLINE)]
    xmpp.MainWindow._ai_assistant_run(aw, "missed")
    assert aw._ai_digest.calls == [((), INLINE)]
    assert len(aw._ai_assistant_open.calls) == 2
    assert aw._ai_assistant_win.events[0] == ("user", "📝 Sohbeti özetle")
    assert set(agent.ACTION_LABELS) <= set(agent.ACTIONS)


def test_refresh_shows_context_and_counts(aw):
    aw.active = "ayse@x.org"
    aw._ai_unread_at_open = {"ayse@x.org": 2}
    aw._unread_counts = {"isil@x.org": 4, "proje@conf.x.org": 0}
    xmpp.MainWindow._ai_assistant_refresh(aw)
    context, groups = aw._ai_assistant_win.quick
    assert context.startswith("💬 Bağlam: Ayşe")
    assert groups == agent.quick_action_groups("Ayşe", 2, 4, 0)
    aw.active = None
    xmpp.MainWindow._ai_assistant_refresh(aw)
    assert aw._ai_assistant_win.quick[0].startswith("Açık sohbet yok")
    aw._ai_assistant_win.alive_flag = False      # kapalı pencere: dokunma
    aw._ai_assistant_win.quick = None
    xmpp.MainWindow._ai_assistant_refresh(aw)
    assert aw._ai_assistant_win.quick is None


def test_switching_chat_refreshes_assistant_context():
    src = inspect.getsource(xmpp.MainWindow._load_chat)
    assert "self._ai_assistant_refresh()" in src


def _chips(win):
    """Görünümdeki çip etiketleri, sırayla."""
    out = []

    def walk(w):
        if w.kw.get("cursor") == "hand2" and w.binds.get("<Button-1>"):
            out.append(w)
        for c in w.winfo_children():
            walk(c)
    walk(win._quick)
    return out


@pytest.mark.usefixtures("fake_tk")
def test_assistant_view_quick_actions_and_prefill():
    picked = []
    win = ui_ai.AssistantWindow(_W(), "alt", lambda t: None,
                                on_quick=lambda k, lbl: picked.append(k))
    win.set_quick_actions("💬 Bağlam: Ayşe", agent.quick_action_groups("Ayşe"))
    assert _find(win.top, "💬 Bağlam: Ayşe") is not None
    assert _find(win.top, "💬 Bu sohbet") is not None      # iki grup başlığı
    assert _find(win.top, "🗂 Tüm sohbetler") is not None
    old = list(win._quick.winfo_children())
    _find(win.top, "💡 Yanıt öner").click()
    assert picked == ["suggest_replies"]
    win.set_quick_actions("Açık sohbet yok", agent.quick_action_groups())
    assert all(w.destroyed for w in old)                 # eski düğmeler gitti
    assert [c.kw["text"] for c in _chips(win)] == [
        lbl for lbl, _k in agent.quick_actions()]
    live = [w.kw.get("text") for w in win._quick.winfo_children()]
    assert "🗂 Tüm sohbetler" not in live                # tek grup: başlık yok
    win._entry._showing_ph = True
    win.prefill(agent.HISTORY_PREFIX)
    assert win._text() == agent.HISTORY_PREFIX.strip()
    assert win._entry._showing_ph is False


@pytest.mark.usefixtures("fake_tk")
def test_quick_chips_wrap_to_window_width():
    """Sabit "satırda 3 düğme" dar pencerede sağdan kesiliyordu."""
    win = ui_ai.AssistantWindow(_W(), "alt", lambda t: None,
                                on_quick=lambda k, lbl: None)
    win.set_quick_actions("bağlam", agent.quick_action_groups(
        "Ayşe", unread=4, missed=9, drafts=2))
    for width in (520, 300):
        for box in win._quick_boxes:
            box.width = width
            for fn in box.binds["<Configure>"]:
                fn(types.SimpleNamespace(width=width))
            chips = [c for c in box.winfo_children()]
            assert chips and all(c.placed is not None for c in chips)
            for c in chips:                  # çip = 1 px kenarlı etiket
                w = c.winfo_children()[0].winfo_reqwidth() + 2
                assert c.placed["x"] == 0 or c.placed["x"] + w <= width
            rows = {c.placed["y"] for c in chips}
            assert box.kw["height"] == max(rows) + 24 + 2
    # dar pencerede daha çok satır
    box = win._quick_boxes[0]
    assert len({c.placed["y"] for c in box.winfo_children()}) >= 2
    # bağlam satırı ve alt başlık da pencere genişliğinde kırılır
    for fn in win._quick.binds["<Configure>"]:
        fn(types.SimpleNamespace(width=300))
    assert win._context_lbl.kw["wraplength"] <= 300
    head = next(
        w for w in win.top.children if win._subtitle in w.children)
    for fn in head.binds["<Configure>"]:
        fn(types.SimpleNamespace(width=300))
    assert win._subtitle.kw["wraplength"] <= 300
    bottom = next(w for w in win.top.children if win._status in w.children)
    for fn in bottom.binds["<Configure>"]:
        fn(types.SimpleNamespace(width=300))
    assert win._status.kw["wraplength"] <= 300


@pytest.mark.usefixtures("fake_tk")
def test_quick_click_while_busy_is_queued_and_runs_after():
    """Meşgulken tıklama sessizce yok sayılıyordu; şimdi sıraya girer."""
    picked = []
    win = ui_ai.AssistantWindow(_W(), "alt", lambda t: None,
                                on_quick=lambda k, lbl: picked.append(k))
    win.set_quick_actions("bağlam", agent.quick_action_groups("Ayşe"))
    win.set_busy("Düşünüyor…")
    _find(win.top, "📥 Neler kaçırdım?").click()
    _find(win.top, "📥 Neler kaçırdım?").click()         # aynısı bir kez
    _find(win.top, "📝 Sohbeti özetle").click()
    assert picked == []
    status = win._status.kw["text"]
    assert "Düşünüyor" in status and "sırada" in status
    assert "Neler kaçırdım?" in status and "Sohbeti özetle" in status
    win.set_busy(None)
    assert picked == []                  # bitiş geri çağrısı önce tamamlansın
    win.top.run_idle()
    assert picked == ["missed", "summarize_chat"]
    assert "sırada" not in win._status.kw["text"]


@pytest.mark.usefixtures("fake_tk")
def test_queue_waits_if_assistant_becomes_busy_again():
    picked = []
    win = ui_ai.AssistantWindow(_W(), "alt", lambda t: None,
                                on_quick=lambda k, lbl: (
                                    picked.append(k),
                                    win.set_busy("Yazıya dökülüyor…")))
    win.set_quick_actions("bağlam", agent.quick_action_groups("Ayşe"))
    win.set_busy("Düşünüyor…")
    _find(win.top, "📥 Neler kaçırdım?").click()
    _find(win.top, "❓ Bekleyen sorular").click()
    win.set_busy(None)
    win.top.run_idle()
    assert picked == ["missed"]          # ilki yine meşgul etti: ikinci bekler
    win.set_busy(None)
    win.top.run_idle()
    assert picked == ["missed", "pending_questions"]


@pytest.mark.usefixtures("fake_tk")
def test_clear_drops_queued_actions():
    picked = []
    win = ui_ai.AssistantWindow(_W(), "alt", lambda t: None,
                                on_quick=lambda k, lbl: picked.append(k))
    win.set_quick_actions("bağlam", agent.quick_action_groups("Ayşe"))
    win.set_busy("Düşünüyor…")
    _find(win.top, "📥 Neler kaçırdım?").click()
    win.clear()
    win.set_busy(None)
    win.top.run_idle()
    assert picked == []


@pytest.mark.usefixtures("fake_tk")
def test_busy_status_shows_elapsed_seconds(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(ui_ai.time, "monotonic", lambda: now[0])
    win = ui_ai.AssistantWindow(_W(), "alt", lambda t: None)
    win.set_busy("Düşünüyor…")
    assert win._status.kw["text"] == "⏳ Düşünüyor…"
    now[0] = 112.4
    fn, a = win.top.timers[-1]
    fn(*a)
    assert win._status.kw["text"] == "⏳ Düşünüyor… 12 sn"
    win.set_busy(None)
    assert win._status.kw["text"] == ""
    n = len(win.top.timers)
    fn(*a)                               # eski zamanlayıcı: yazmaz, kurmaz
    assert win._status.kw["text"] == "" and len(win.top.timers) == n
