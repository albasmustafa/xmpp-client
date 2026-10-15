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


@pytest.mark.parametrize("plan,method,args", [
    (_plan(action="open_chat", target="Işıl"), "_ai_open_chat",
     ("isil@x.org",)),
    (_plan(action="summarize_chat", target="ayse"), "_ai_summarize",
     ("ayse@x.org",)),
    (_plan(action="extract_tasks", target="proje"), "_ai_extract_actions",
     ("proje@conf.x.org",)),
    (_plan(action="missed"), "_ai_digest", ()),
    (_plan(action="pending_questions"), "_ai_pending_questions", ()),
    (_plan(action="ask_history", text="Adres neydi?"), "_ai_ask_history",
     ("Adres neydi?",)),
])
def test_safe_actions_run_immediately(aw, plan, method, args):
    setattr(aw, method, _Cap())
    win = _say(aw, "komut", plan)
    assert getattr(aw, method).calls == [(args, {})]
    assert win.events[-1][0] == "note" and win.cards == []


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
