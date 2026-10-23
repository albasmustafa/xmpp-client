"""✨ Asistan tek merkez: AI sonuçları asistanın İÇİNDE (InlineResult).

Kanıtlar (gerçek AssistantWindow sahte tk ile + gerçek MainWindow akışları):
- Asistandan istenen özet / neler kaçırdım / yanıt önerisi / bekleyen
  sorular / geçmişe sor ayrı pencere açmaz; sonuç kart olarak akar.
- Takip sorusu asistanın giriş kutusundan gelir: "↩ Takip sorusu" kutuyu
  karta bağlar, soru+yanıt balon olarak eklenir; Esc/✗ komut kipine döner.
  Yanıt beklenirken yeni takip sorusu kabul edilmez; hata olursa soru
  kutuya geri döner, iz bırakmaz.
- Asistan kapanınca / "Temizle"de süren akışlar iptal edilir.
- Asistan kapalıyken aynı akışlar eskisi gibi ayrı pencere açar.
- Bilgi mesajları (okunmamış yok vb.) bilgi kutusu yerine asistan yanıtıdır.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ai_dialog_view import _W, _find, fake_tk  # noqa: E402,F401
from test_ai_mainwindow import _Cap, _chat_spy, _FakeWin, _mw  # noqa: E402

import ui.dialogs.ai as ui_ai  # noqa: E402
import xmpp  # noqa: E402

pytestmark = pytest.mark.usefixtures("fake_tk")


def _assistant(w=None, on_submit=None):
    win = ui_ai.AssistantWindow(_W(), "alt", on_submit or (lambda t: None))
    if w is not None:
        w._ai_assistant_win = win
    return win


def _type(win, text):
    win._entry._showing_ph = False
    win._var.set(text)
    win._submit()


def _bubbles(win):
    """Listedeki balon metinleri: [(benim mi, metin)] (canlı olanlar)."""
    out = []
    for outer in win._list.inner.winfo_children():
        for bubble in outer.winfo_children():
            pack = bubble.packed or {}
            if pack.get("side") in ("left", "right"):
                label = bubble.children[0]
                out.append((pack["side"] == "right", label.kw["text"]))
    return out


# ── Görünüm: InlineResult + takip kipi ──────────────────────────────────────
def test_result_streams_then_followup_goes_to_card_not_commands():
    asked, commands = [], []
    win = _assistant(on_submit=commands.append)
    res = win.add_result("📝 Ayşe — sohbet özeti", "yerel",
                         on_ask=asked.append, ask_hint="Örn: Ne zaman?")
    assert res._ask_btn.packed is None          # ilk yanıttan önce gizli
    res.append_text("Kısa ")
    res.append_text("özet")
    assert res._body.kw["text"] == "Kısa özet"
    assert res._status.kw["text"] == "✍ Yazılıyor…"
    res.set_text("Kısa özet.")
    assert res._status.kw["text"] == "✓ Hazır" and res._ask_btn.packed
    _type(win, "komut")
    assert commands == ["komut"] and asked == []
    _find(res.frame, "↩ Takip sorusu").click()
    assert win._followup is res and win._fu_bar.packed
    _type(win, "Saat kaçta?")
    assert asked == ["Saat kaçta?"] and commands == ["komut"]
    res.begin_question("Saat kaçta?")
    assert win._var.get() == ""
    res.append_text("14:")
    res.append_text("00")
    assert _bubbles(win)[-2:] == [(True, "Saat kaçta?"), (False, "14:00")]
    _type(win, "ikinci")                        # yanıt beklenirken kabul yok
    assert asked == ["Saat kaçta?"]
    res.set_answer("14:00'te.")
    assert _bubbles(win)[-1] == (False, "14:00'te.")
    win._entry.binds["<Escape>"][0](None)       # komut kipine dön
    assert win._followup is None and win._fu_bar.packed is None
    win._var.set("")
    _type(win, "yeni komut")
    assert commands == ["komut", "yeni komut"]
    res._copy()
    assert win.top.clip == "Kısa özet.\n\n❓ Saat kaçta?\n\n14:00'te."


def test_failed_followup_leaves_no_trace_and_restores_question():
    win = _assistant()
    res = win.add_result("Özet", on_ask=lambda q: None)
    res.set_text("Özet metni")
    n = len(win._list.inner.winfo_children())
    res.begin_question("Kim geliyor?")
    res.append_text("yarım")
    res.set_error("Model yanıt vermedi")
    assert len(win._list.inner.winfo_children()) == n   # balonlar silindi
    assert win._var.get() == "Kim geliyor?"
    assert res._status.kw["text"] == "⚠ Model yanıt vermedi"
    assert res._ask_enabled and res._body.kw["text"] == "Özet metni"
    res2 = win.add_result("Tek", on_ask=lambda q: None)
    res2.append_text("kısmi")
    res2.set_error("Reddedildi")
    assert res2._body.kw["text"] == "" and not res2._ask_enabled


def test_sources_stay_with_their_turn_and_echo_can_be_skipped():
    win = _assistant()
    res = win.add_result("💬 Geçmişe sor", on_ask=lambda q: None,
                         ask_ready=True)
    assert res._ask_enabled and res._ask_btn.packed
    res.skip_next_echo()
    res.begin_question("Adres neydi?")
    assert _bubbles(win) == [(False, "…")]      # soru yinelenmedi
    res.set_busy("İlgili mesajlar aranıyor…")
    assert _bubbles(win) == [(False, "⏳ İlgili mesajlar aranıyor…")]
    picked = []
    res.set_answer("Kızılay [1]")
    res.set_sources([("[1] Ali: Kızılay", ("a@b", "m1"))], picked.append)
    first = res._sources
    _find(first, "[1] Ali: Kızılay").click()
    assert picked == [("a@b", "m1")]
    res.begin_question("Ne zaman?")
    res.set_sources([], None)
    assert not first.destroyed                  # önceki turunki yerinde
    res.set_answer("Cuma")
    res.set_sources([("[2] Ali: Cuma", ("a@b", "m2"))], picked.append)
    assert res._sources is not first and not first.destroyed


def test_clear_and_close_cancel_running_results():
    closed = []
    win = _assistant()
    res = win.add_result("A", on_close=lambda: closed.append("A"))
    win.set_followup(res)
    win.clear()
    assert closed == ["A"] and not res.alive() and win._followup is None
    res.set_text("geç gelen")                   # ölü karta yazmak sessiz
    win.add_result("B", on_close=lambda: closed.append("B"))
    win.close()
    assert closed == ["A", "B"]


def test_choices_and_questions_inside_card():
    win = _assistant()
    res = win.add_result("💡 Yanıt önerileri")
    picked = []
    res.set_choices(["Olur", "Yarın"], picked.append)
    _find(res.frame, "Yarın").click()
    assert picked == ["Yarın"] and res.alive()
    assert res._status.kw["text"].startswith("✓ Giriş kutusuna kondu")
    res = win.add_result("❓ Yanıt bekleyen sorular")
    opened, dismissed = [], []
    entries = [{"jid": "a@b", "key": "k1", "label": "Ali", "age": "2 saat",
                "text": "Geliyor musun?"},
               {"jid": "c@d", "key": "k2", "label": "Can", "age": "1 gün",
                "text": "Dosya?", "count": 2}]
    res.set_questions(entries, opened.append,
                      lambda e: (True, "⏰ Hatırlatıcı kuruldu."),
                      dismissed.append)
    assert res._status.kw["text"] == "2 sohbette yanıt bekleyen soru var."
    cards = res._extra.winfo_children()
    _find(cards[0], "💬 Sohbete git").click()
    _find(cards[0], "⏰ Yarın 09:00 hatırlat").click()
    assert opened == [entries[0]]
    assert res._status.kw["text"] == "⏰ Hatırlatıcı kuruldu."
    _find(cards[1], "✓ Yok say").click()
    assert dismissed == [entries[1]] and cards[1].destroyed
    assert res._status.kw["text"] == "1 sohbette yanıt bekleyen soru var."


# ── MainWindow akışları asistanın içinde ────────────────────────────────────
def test_summary_and_followup_run_inside_assistant(monkeypatch):
    w = _mw(monkeypatch)
    win = _assistant(w)
    spy = _chat_spy(monkeypatch, reply="Yarın 14:00 buluşma.")
    xmpp.MainWindow._ai_summarize(w, "a@b", inline=True)
    assert _FakeWin.instances == []             # ayrı pencere yok
    res, = win._results
    assert res.title == "📝 a — sohbet özeti"
    assert res._body.kw["text"] == "Yarın 14:00 buluşma."
    res.focus_ask()
    spy.ret = "Kafede."
    _type(win, "Nerede?")
    assert len(spy.calls) == 2
    history = spy.calls[1][1]["history"]
    assert history[-1] == ("assistant", "Yarın 14:00 buluşma.")
    assert _bubbles(win)[-2:] == [(True, "Nerede?"), (False, "Kafede.")]


def test_without_assistant_flows_open_their_own_windows(monkeypatch):
    w = _mw(monkeypatch)
    w._ai_assistant_win = None
    _chat_spy(monkeypatch)
    xmpp.MainWindow._ai_summarize(w, "a@b", inline=True)
    assert len(_FakeWin.instances) == 1


def test_notices_become_assistant_replies(monkeypatch):
    w = _mw(monkeypatch)
    win = _assistant(w)
    w._unread_counts = {}
    shown = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "showinfo", shown)
    xmpp.MainWindow._ai_digest(w, inline=True)
    assert shown.calls == []
    assert _bubbles(win) == [(False, "Okunmamış mesaj yok — her şey "
                                     "okunmuş. 🎉")]
    assert w._ai_agent_log[-1][0] == "assistant"
    xmpp.MainWindow._ai_digest(w)               # pencere yolu değişmedi
    assert len(shown.calls) == 1


def test_suggestions_inline_fill_composer_and_keep_card(monkeypatch):
    w = _mw(monkeypatch)
    win = _assistant(w)
    w._ai_offer_text = _Cap()
    _chat_spy(monkeypatch, reply="1. Olur\n2. Saat kaçta?")
    xmpp.MainWindow._ai_suggest_replies(w, "a@b", inline=True)
    res, = win._results
    _find(res.frame, "Saat kaçta?").click()
    assert w._ai_offer_text.calls == [(("a@b", "Saat kaçta?"), {})]
    assert res.alive() and _FakeWin.instances == []


def test_pending_questions_inline(monkeypatch):
    w = _mw(monkeypatch)
    win = _assistant(w)
    w._ai_open_chat = _Cap()
    entry = {"jid": "a@b", "key": "k", "text": "Geliyor musun?",
             "since": datetime(2026, 10, 19, 10, 0)}
    w._questions_scan = lambda done, err=None: done([entry])
    xmpp.MainWindow._ai_pending_questions(w, inline=True)
    res, = win._results
    card, = res._extra.winfo_children()
    _find(card, "💬 Sohbete git").click()
    assert w._ai_open_chat.calls == [(("a@b",), {})]


def test_ask_history_inline_waits_for_question_in_followup_mode(monkeypatch):
    w = _mw(monkeypatch)
    win = _assistant(w)
    turns = _Cap()
    w._ai_rag_turn = turns
    xmpp.MainWindow._ai_ask_history(w, inline=True)
    res, = win._results
    assert win._followup is res and turns.calls == []
    _type(win, "Adres neydi?")
    assert turns.calls[0][0][2] == "Adres neydi?"
    xmpp.MainWindow._ai_ask_history(w, "Toplantı ne zaman?", inline=True)
    res2 = win._results[-1]
    assert res2._skip_echo and turns.calls[1][0][2] == "Toplantı ne zaman?"
