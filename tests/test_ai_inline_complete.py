"""Satır içi öneri (yazarken devam önerisi).

Kanıtlar:
- İstem/temizlik: yalnız devam metni; taslak tekrarı, tırnak, düşünme
  bloğu ve fazla uzunluk ayıklanır; boş/… öneri yok sayılır.
- `max_tokens` Ollama'da num_predict, Claude'da max_tokens olur ve kısa
  yanıta kesilme notu EKLENMEZ; verilmezse sağlayıcıya hiç iletilmez.
- Tetikleme: ayar açık + sözcük bitmiş (boşluk) + imleç sonda + "/" komutu
  değil; her tuş öneriyi gizler ve zamanlayıcıyı yeniler.
- İstek yalnız yerel (Ollama) sağlayıcıyla yapılır; bulutta hiç gitmez.
  Geç gelen ya da taslak/sohbet değişmiş yanıt atılır; aynı anda tek istek.
- Tab kabul eder (öneri yoksa normal Tab), Esc gizler; sohbet değişince
  ve ayar kapanınca öneri kaybolur. Panel yeniden kurulursa çubuk yeni
  girişe bağlanır.
"""
import inspect
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_chat_media import _MW  # noqa: E402
from test_history_window_bounds import _Cap  # noqa: E402

import xmpp  # noqa: E402
from ui.chat import suggest as suggest_mod  # noqa: E402
from xmppcore import ai  # noqa: E402


# ── 1) İstem ve temizlik ────────────────────────────────────────────────────
def test_completion_request_contains_draft_and_rules():
    system, user = ai.completion_request("Ali: selam", "yarın gel")
    assert "at most 8 words" in system and ai._DATA_RULE in system
    assert user.endswith("<draft>yarın gel</draft>")


@pytest.mark.parametrize("draft,raw,expected", [
    ("Yarın ", "saat 10'da gelirim", "saat 10'da gelirim"),
    ("Yarın ", "\"saat 10'da\"", "saat 10'da"),
    ("Yarın ", "Yarın saat 10'da", "saat 10'da"),
    ("Yarın ", "<think>x</think>saat 10'da\nikinci satır", "saat 10'da"),
    ("Yarın ", "", ""),
    ("Yarın ", "…", ""),
    ("Yarın ", "çok " * 40, ("çok " * 40)[:80].rsplit(" ", 1)[0]),
])
def test_clean_completion(draft, raw, expected):
    assert ai.clean_completion(draft, raw) == expected


def test_max_tokens_plumbing(monkeypatch):
    s = ai.load_settings({})
    sent = {}

    def fake_request(settings, path, payload, timeout):
        sent.update(payload)
        return {"message": {"content": "devam"}, "done_reason": "length"}
    monkeypatch.setattr(ai, "_ollama_request", fake_request)
    assert ai.ollama_chat(s, "sys", "u", max_tokens=24) == "devam"
    assert sent["options"]["num_predict"] == 24
    sent.clear()
    assert ai.TRUNCATED_NOTE in ai.ollama_chat(s, "sys", "u")
    assert "num_predict" not in sent["options"]
    kw = ai.claude_request_kwargs(dict(s, claude_model="claude-opus-5-5"),
                                  "sys", "u", max_tokens=24)
    assert kw["max_tokens"] == 24
    assert ai.claude_request_kwargs(s, "s", "u")["max_tokens"] == \
        ai._CLAUDE_MAX_TOKENS


def test_chat_omits_max_tokens_when_unset(monkeypatch):
    seen = []
    monkeypatch.setattr(ai, "ollama_chat", lambda *a, **k: seen.append(k)
                        or "x")
    ai.chat(ai.load_settings({}), "s", "u")
    ai.chat(ai.load_settings({}), "s", "u", max_tokens=5)
    assert "max_tokens" not in seen[0] and seen[1]["max_tokens"] == 5


# ── 2) MainWindow ───────────────────────────────────────────────────────────
class _Bar:
    def __init__(self):
        self.text, self.shown = "", []

    @property
    def visible(self):
        return bool(self.text)

    def show(self, draft, text):
        self.text = text
        self.shown.append((draft, text))

    def hide(self):
        self.text = ""


@pytest.fixture()
def cw(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.active = "ali@x"
    w._ai_inline_on = True
    w._suggest_bar = _Bar()
    st = {"text": "Yarın "}
    w._ai_composer_text = lambda: st["text"]
    w._ai_set_composer_text = lambda t: st.update(text=t)
    w._msg_entry = types.SimpleNamespace(index=lambda i: len(st["text"]))
    timers = []
    w._after = lambda ms, fn, *a: (timers.append(fn), f"t{len(timers)}")[1]
    w._after_cancel = _Cap()
    w.chats = {"ali@x": [("Ali", "toplantı ne zaman?", False, "10:00",
                          "them")]}
    w._chat_enc_modes = {}
    cfg = {"ai": {"provider": "ollama", "inline_complete": True}}
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    calls = []

    def fake_chat(settings, system, user, **kw):
        calls.append(kw)
        return "saat 10'da"
    monkeypatch.setattr(xmpp._ai, "chat", fake_chat)
    w._ai_submit = lambda job, done, err: done(job())
    w.st, w.timers, w.calls, w.cfg = st, timers, calls, cfg
    return w


def _key(w, keysym="space"):
    xmpp.MainWindow._ai_complete_on_key(w, types.SimpleNamespace(
        keysym=keysym))


def test_pause_after_word_requests_and_shows(cw):
    _key(cw)
    assert len(cw.timers) == 1
    cw.timers[0]()
    assert cw.calls == [{"effort": "low",
                         "max_tokens": ai.COMPLETION_MAX_TOKENS}]
    assert cw._suggest_bar.shown == [("Yarın ", "saat 10'da")]


@pytest.mark.parametrize("setup", [
    lambda w: w.st.update(text="Yarın"),               # sözcük bitmedi
    lambda w: w.st.update(text="Ya "),                 # çok kısa
    lambda w: w.st.update(text="/nick yeni "),         # komut
    lambda w: setattr(w, "_ai_inline_on", False),      # ayar kapalı
    lambda w: setattr(w, "active", None),
    lambda w: setattr(w, "_msg_entry", types.SimpleNamespace(
        index=lambda i: 2)),                           # imleç ortada
])
def test_no_request_when_not_appropriate(cw, setup):
    setup(cw)
    _key(cw)
    assert cw.timers == []


def test_every_key_hides_and_reschedules(cw):
    cw._suggest_bar.text = "eski"
    cw.st["text"] = "Yarın a"                           # sözcük ortası
    _key(cw, "a")
    assert cw._suggest_bar.text == "" and cw._after_cancel.calls
    assert cw.timers == []
    cw.st["text"] = "Yarın "
    _key(cw, "Shift_L")
    assert cw.timers == []                              # değiştirici tuş
    _key(cw, "space")
    _key(cw, "space")
    assert len(cw.timers) == 2                          # yeniden planlandı
    assert cw._after_cancel.calls[-1] == (("t1",), {})


def test_cloud_provider_never_gets_draft(cw):
    cw.cfg["ai"]["provider"] = "claude"
    _key(cw)
    cw.timers[0]()
    assert cw.calls == [] and cw._suggest_bar.shown == []


def test_stale_results_are_dropped(cw):
    pending = []
    cw._ai_submit = lambda job, done, err: pending.append((job, done))
    _key(cw)
    cw.timers[0]()
    cw.st["text"] = "Yarın sabah "                      # yazmaya devam
    job, done = pending[0]
    done(job())
    assert cw._suggest_bar.shown == []
    assert cw._ai_complete_busy is False
    cw.timers[0]()                                       # yeni istek
    job, done = pending[1]
    cw.active = "veli@x"                                 # sohbet değişti
    done(job())
    assert cw._suggest_bar.shown == []


def test_single_request_in_flight(cw):
    pending = []
    cw._ai_submit = lambda job, done, err: pending.append(done)
    cw.timers.clear()
    xmpp.MainWindow._ai_complete_request(cw)
    xmpp.MainWindow._ai_complete_request(cw)
    assert len(pending) == 1
    pending[0]("")
    xmpp.MainWindow._ai_complete_request(cw)
    assert len(pending) == 2


def test_errors_release_busy(cw):
    cw._ai_submit = lambda job, done, err: err(ai.AIError("kapalı"))
    xmpp.MainWindow._ai_complete_request(cw)
    assert cw._ai_complete_busy is False


def test_tab_accept_and_escape(cw):
    assert xmpp.MainWindow._ai_complete_tab(cw) is None   # öneri yok
    cw._suggest_bar.text = "saat 10'da"
    assert xmpp.MainWindow._ai_complete_tab(cw) == "break"
    assert cw.st["text"] == "Yarın saat 10'da"
    assert not cw._suggest_bar.visible
    assert xmpp.MainWindow._ai_complete_escape(cw) is None
    cw._suggest_bar.text = "x"
    assert xmpp.MainWindow._ai_complete_escape(cw) == "break"
    assert cw.st["text"] == "Yarın saat 10'da"
    _key(cw, "Tab")                                       # Tab bırakma
    assert cw.timers == []


def test_flags_and_chat_switch_hide(cw, monkeypatch):
    cw._suggest_bar.text = "x"
    cw.cfg["ai"]["inline_complete"] = False
    xmpp.MainWindow._ai_refresh_flags(cw)
    assert cw._ai_inline_on is False and not cw._suggest_bar.visible
    cw.cfg["ai"].update(inline_complete=True, provider="claude")
    xmpp.MainWindow._ai_refresh_flags(cw)
    assert cw._ai_inline_on is False                      # yalnız yerel
    src = inspect.getsource(xmpp.MainWindow._load_chat)
    assert "self._ai_complete_hide()" in src.splitlines()[2]


def test_setup_binds_and_rebuild_rebinds(monkeypatch):
    made = []
    monkeypatch.setattr(xmpp, "_SuggestionBar", lambda parent, theme, **k:
                        made.append(parent) or _Bar())
    w = object.__new__(xmpp.MainWindow)

    class _Entry:
        def __init__(self):
            self.binds = {}

        def bind(self, seq, fn, add=None):
            self.binds[seq] = (fn, add)
    for i in range(2):
        w._msg_entry = _Entry()
        w._inp_border = types.SimpleNamespace(master=f"inf{i}")
        xmpp.MainWindow._ai_complete_setup(w)
        xmpp.MainWindow._ai_complete_setup(w)            # aynı giriş: tek
        assert w._msg_entry.binds["<KeyRelease>"][1] == "+"
        assert set(w._msg_entry.binds) == {"<KeyRelease>", "<Tab>",
                                           "<Escape>"}
    assert made == ["inf0", "inf1"]
    w._inp_border = "stub"                               # test çiftleri
    w._msg_entry = _Entry()
    xmpp.MainWindow._ai_complete_setup(w)
    assert made == ["inf0", "inf1"]


# ── 3) Görünüm ──────────────────────────────────────────────────────────────
class _GW(_MW):
    def grid(self, *a, **k):
        self.kw["_grid"] = k

    def grid_remove(self):
        self.kw["_grid"] = None


def test_suggestion_bar_grid_show_hide(monkeypatch):
    monkeypatch.setattr(suggest_mod, "tk", types.SimpleNamespace(
        Frame=_GW, Label=_GW))
    accepted = []
    bar = suggest_mod.SuggestionBar(_GW(), xmpp._chat_theme(),
                                    on_accept=lambda: accepted.append(1))
    bar.show("x" * 50 + " ", "devam")
    assert bar.visible and bar.text == "devam"
    assert bar._lbl.kw["text"] == "✨ …" + ("x" * 50 + " ")[-40:] + "devam"
    assert bar._bar.kw["_grid"]["row"] == 1
    bar._lbl.binds["<Button-1>"][0](None)
    assert accepted == [1]
    bar.hide()
    assert not bar.visible and bar._bar.kw["_grid"] is None


def test_suggest_has_no_domain_dependencies():
    src = inspect.getsource(suggest_mod)
    for token in ("slixmpp", "sqlite", "_db_", "urlopen(", "threading.",
                  "gui_q", "subprocess", "_safe_after", "asyncio",
                  "xmppcore", ".after(", "import xmpp"):
        assert token not in src, token
