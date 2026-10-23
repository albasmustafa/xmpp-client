"""AI asistanı yeni akışları — MainWindow entegrasyonu (Tk'sız çiftlerle).

Kanıtlar:
- Akış: parçalar pencereye sırayla gelir, kesin metin sonra yazılır.
- Takip soruları aynı içeriği geçmişle (metin-only) ve önbellekle gönderir;
  şifreli+bulut sohbette HER takip sorusu ayrıca onay ister; başarısız tur
  geçmişe girmez; pencere kapanınca akış iptal edilir, hiçbir şey yazılmaz.
- "Neler kaçırdım?" okunmamış sohbetleri öncelik sırasıyla özetler; karışık
  şifreli içerikte üç yollu onay (hepsi / şifresizler / hiçbiri).
- Geçmişe sor: indeks güncellenir, eşleşme + komşular numaralı bağlam olur,
  atıflar kaynaklara çevrilir, takip sorusu önceki soruyla aranır.
- Eylemler: şemalı istek, .ics yazımı, doğrulama, kalıcı hatırlatıcılar.
- Dikte: kayıt modu, yerel yazıya dökme, taslağa ekleme, geçici dosya
  temizliği; ses mesajı yolu değişmez.
- Menüler ve kısayollar yeni girişleri içerir.
"""
import os
import sys
import threading
import time
import types
import wave
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ai_mainwindow import _Cap, _composer, _FakeWin, _mw, _row  # noqa: E402

import xmpp  # noqa: E402

AI = xmpp._ai


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "ai_flows.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


class _Win(_FakeWin):
    """Akış/takip sorusu destekli ResultWindow çifti."""

    def __init__(self, parent, title, subtitle="", actions=(), **kw):
        super().__init__(parent, title, subtitle, actions, **kw)
        self.actions = list(actions)
        self.appended, self.questions, self.answers = [], [], []
        self.errors = []
        self.sources = None
        self.focused = False
        self.closed = False

    def append_text(self, chunk):
        self.appended.append(chunk)

    def begin_question(self, q):
        self.questions.append(q)

    def set_answer(self, text, status=""):
        self.answers.append(text)
        self.text = text

    def set_error(self, msg):
        self.errors.append(msg)
        self.error = msg

    def set_sources(self, items, on_pick, title=""):
        self.sources = (list(items), on_pick, title)

    def focus_ask(self):
        self.focused = True

    def alive(self):
        return not self.closed

    # kullanıcı eylemleri
    def ask(self, q):
        self.kw["on_ask"](q)

    def close(self):
        self.closed = True
        self.kw["on_close"]()


class _Chat:
    """_ai.chat çifti: yanıtı iki parça halinde on_delta'ya akıtır."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, settings, system, user, **kw):
        self.calls.append(types.SimpleNamespace(system=system, user=user,
                                                **kw))
        reply = self.replies.pop(0) if len(self.replies) > 1 \
            else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        if kw.get("on_delta") is not None:
            half = len(reply) // 2
            kw["on_delta"](reply[:half])
            kw["on_delta"](reply[half:])
        return reply


def _w(monkeypatch, **kw):
    w = _mw(monkeypatch, **kw)
    monkeypatch.setattr(xmpp._ui_ai, "ResultWindow", _Win)
    w._load_chat = _Cap()
    w._show_members = _Cap()
    w._hide_members = _Cap()
    return w


def _chat(monkeypatch, *replies):
    c = _Chat(*replies)
    monkeypatch.setattr(AI, "chat", c)
    return c


# ── 1) Akış + takip soruları ────────────────────────────────────────────────
def test_summary_streams_then_followup_sends_history_with_cache(monkeypatch):
    w = _w(monkeypatch)
    chat = _chat(monkeypatch, "Özet: yarın 14:00 buluşma.", "Saat 14:00.")
    xmpp.MainWindow._ai_summarize(w, "a@b")
    win = _FakeWin.instances[0]
    # ilk parça hemen, ikincisi toplanıp sonuçtan ÖNCE gelir
    assert len(win.appended) == 2
    assert "".join(win.appended) == "Özet: yarın 14:00 buluşma."
    assert win.text == "Özet: yarın 14:00 buluşma."
    first = chat.calls[0]
    assert first.history == [] and first.cache is True
    assert first.effort == "medium" and "follow-up" in first.system
    win.ask("Saat kaçta?")
    second = chat.calls[1]
    assert win.questions == ["Saat kaçta?"]
    assert second.user == "Saat kaçta?" and second.system == first.system
    assert second.history == [("user", first.user),
                              ("assistant", "Özet: yarın 14:00 buluşma.")]
    assert win.answers == ["Saat 14:00."]


def test_encrypted_cloud_followup_asks_consent_every_time(monkeypatch):
    w = _w(monkeypatch, settings={"provider": "claude"},
           enc={"a@b": "omemo"})
    chat = _chat(monkeypatch, "Özet", "Yanıt")
    asked = _Cap(ret=True)
    monkeypatch.setattr(xmpp.messagebox, "askyesno", asked)
    xmpp.MainWindow._ai_summarize(w, "a@b")
    win = _FakeWin.instances[0]
    win.ask("q1")
    assert len(asked.calls) == 2
    assert [c.allow_cloud for c in chat.calls] == [True, True]
    assert all(c.sensitive for c in chat.calls)
    asked.ret = False
    win.ask("q2")                       # reddedildi: hiçbir şey gitmez
    assert len(asked.calls) == 3 and len(chat.calls) == 2
    assert win.questions == ["q1"]


def test_failed_followup_is_not_committed(monkeypatch):
    w = _w(monkeypatch)
    chat = _chat(monkeypatch, "Özet", AI.AIError("bağlantı koptu"), "Yanıt")
    xmpp.MainWindow._ai_summarize(w, "a@b")
    win = _FakeWin.instances[0]
    win.ask("q1")
    assert win.errors == ["bağlantı koptu"]
    win.ask("q2")
    assert chat.calls[2].history == [("user", chat.calls[0].user),
                                     ("assistant", "Özet")]


def test_translate_window_supports_followups(monkeypatch):
    w = _w(monkeypatch)
    chat = _chat(monkeypatch, "Hello", "It is a greeting.")
    xmpp.MainWindow._ai_translate_row(w, _row("Merhaba"))
    win = _FakeWin.instances[0]
    assert win.text == "Hello" and chat.calls[0].effort == "low"
    win.ask("Ne anlama geliyor?")
    assert chat.calls[1].history[1] == ("assistant", "Hello")


def _drain(queue):
    for t in [t for t in threading.enumerate() if t.name == "ai-worker"]:
        t.join(5)
    while queue:
        fn, args = queue.pop(0)
        fn(*args)


def _real_submit(w):
    """Gerçek _ai_submit (thread) + kuyruğa alan _safe_after."""
    queue = []
    w._closing = False
    w._ai_submit = types.MethodType(xmpp.MainWindow._ai_submit, w)
    w._safe_after = lambda ms, fn, *a: queue.append((fn, a))
    return queue


def test_closing_window_cancels_stream_silently(monkeypatch):
    w = _w(monkeypatch)
    queue = _real_submit(w)
    raised = []

    def _chat_fn(settings, system, user, **kw):
        _FakeWin.instances[0].close()          # kullanıcı pencereyi kapattı
        try:
            kw["on_delta"]("parça")
        except AI.AICancelled as e:
            raised.append(e)
            raise
        return "yazılmamalı"
    monkeypatch.setattr(AI, "chat", _chat_fn)
    xmpp.MainWindow._ai_summarize(w, "a@b")
    _drain(queue)
    win = _FakeWin.instances[0]
    assert raised and win.appended == []
    assert win.text is None and win.errors == []


def test_real_submit_routes_results_errors_and_cancel():
    w = object.__new__(xmpp.MainWindow)
    queue = _real_submit(w)
    got = []
    w._ai_submit(lambda: 42, got.append, lambda e: got.append(("err", e)))
    w._ai_submit(lambda: (_ for _ in ()).throw(AI.AIError("x")),
                 got.append, lambda e: got.append(("err", str(e))))
    w._ai_submit(lambda: (_ for _ in ()).throw(AI.AICancelled("c")),
                 got.append, lambda e: got.append(("err", str(e))))
    _drain(queue)
    assert sorted(map(str, got)) == ["('err', 'x')", "42"]


def test_image_followup_sees_image_even_after_cached_answer(tmp_db,
                                                           monkeypatch):
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(buf, "PNG")
    w = _w(monkeypatch)
    fetches = []

    def _fetch(url, mx):
        fetches.append(url)
        return buf.getvalue()
    monkeypatch.setattr(AI, "fetch_url", _fetch)
    chat = _chat(monkeypatch, "Mavi kare.", "Mavi.")
    row = _row("https://x.org/p.png")
    xmpp.MainWindow._ai_describe_row(w, row)
    xmpp.MainWindow._ai_describe_row(w, row)        # önbellekten
    assert len(chat.calls) == 1
    cached_win = _FakeWin.instances[1]
    assert cached_win.text == "Mavi kare."
    cached_win.ask("Rengi ne?")
    follow = chat.calls[1]
    assert follow.images and follow.images[0][1] == "image/jpeg"
    assert follow.history == [("user", chat.calls[0].user),
                              ("assistant", "Mavi kare.")]
    assert len(fetches) == 2                         # pencere başına bir kez


# ── 2) "Neler kaçırdım?" ────────────────────────────────────────────────────
def _e(sender, body, enc=False, i=0):
    return (sender, body, False, f"09:{i:02d}", "them", "", enc, f"m{i}", "",
            i)


def _digest_w(monkeypatch, **kw):
    chats = {
        "ali@x": [_e("Ali", "Yarın 10'da toplantı var mı?")],
        "oda@conf": [_e("Can", f"mesaj {i}", i=i) for i in range(10)],
        "gizli@x": [_e("Ece", "şifre 1234", enc=True)],
    }
    w = _w(monkeypatch, chats=chats, **kw)
    w._unread_counts = {"ali@x": 1, "oda@conf": 3, "gizli@x": 1, "bos@x": 0}
    w._contacts = {"ali@x": "Ali Veli"}
    w.rooms = ["oda@conf"]
    return w


def test_digest_orders_by_unread_and_links_chats(monkeypatch):
    w = _digest_w(monkeypatch)
    chat = _chat(monkeypatch, "Ali soru sordu.")
    xmpp.MainWindow._ai_digest(w)
    (call,) = chat.calls
    user = call.user
    assert (user.index('name="oda" unread="3"')
            < user.index('name="Ali Veli" unread="1"')
            < user.index('name="gizli" unread="1"'))
    # 3 okunmamış + 5 bağlam = son 8 mesaj
    assert "mesaj 2" in user and "mesaj 9" in user and "mesaj 1" not in user
    assert call.sensitive is True and call.effort == "medium"
    win = _FakeWin.instances[0]
    assert "3 sohbet, 5 okunmamış" in win.subtitle
    items, on_pick, title = win.sources
    assert title == "Sohbete git"
    assert items == [("💬 oda (3)", "oda@conf"), ("💬 Ali Veli (1)", "ali@x"),
                     ("💬 gizli (1)", "gizli@x")]
    on_pick("oda@conf")
    assert w._show_members.calls == [(("oda@conf",), {})]
    assert w._load_chat.calls == [(("oda@conf",), {})]


@pytest.mark.parametrize("answer", [None, False, True])
def test_digest_mixed_encryption_three_way_consent(monkeypatch, answer):
    w = _digest_w(monkeypatch, settings={"provider": "claude"})
    chat = _chat(monkeypatch, "Özet")
    asked = _Cap(ret=answer)
    monkeypatch.setattr(xmpp.messagebox, "askyesnocancel", asked)
    xmpp.MainWindow._ai_digest(w)
    assert len(asked.calls) == 1
    if answer is None:
        assert chat.calls == [] and _FakeWin.instances == []
        return
    (call,) = chat.calls
    assert ("şifre 1234" in call.user) is answer
    assert call.allow_cloud is answer and call.sensitive is answer
    labels = [jid for _l, jid in _FakeWin.instances[0].sources[0]]
    assert ("gizli@x" in labels) is answer


def test_digest_without_unread_informs(monkeypatch):
    w = _w(monkeypatch)
    w._unread_counts = {"a@b": 0}
    chat = _chat(monkeypatch, "x")
    info = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "showinfo", info)
    xmpp.MainWindow._ai_digest(w)
    assert len(info.calls) == 1 and chat.calls == []


def test_open_chat_and_search_hit_set_members_panel(monkeypatch):
    """Regresyon: arama/RAG kaynağından odaya geçince üye paneli de
    güncellenir (eskiden yalnız _load_chat çağrılıyordu)."""
    w = _w(monkeypatch)
    w.rooms = ["oda@conf"]
    later = []
    w._safe_after = lambda ms, fn, *a: later.append((ms, fn, a))
    xmpp.MainWindow._ai_open_search_hit(w, ("oda@conf", "m9"))
    xmpp.MainWindow._ai_open_search_hit(w, ("ali@x", ""))
    assert w._show_members.calls == [(("oda@conf",), {})]
    assert len(w._hide_members.calls) == 1
    assert [c[0][0] for c in w._load_chat.calls] == ["oda@conf", "ali@x"]
    assert len(later) == 1 and later[0][0] == 200 and later[0][2] == ("m9",)


# ── 3) Geçmişe sor (RAG) ────────────────────────────────────────────────────
def _rag_embed(calls=None):
    def _embed(settings, texts):
        if calls is not None:
            calls.append(list(texts))
        out = []
        for t in texts:
            t = t.lower()
            if "hiç" in t:
                out.append([-1.0, -1.0, -1.0])
            elif "adres" in t:
                out.append([0.0, 1.0, 0.0])
            elif "fatura" in t:
                out.append([1.0, 0.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out
    return _embed


def _seed_rag(encrypted_secret=False):
    xmpp._db_store_msg("a@b", "Ali", "Merhaba nasılsın", False, "10:00",
                       "them", mid="m1")
    xmpp._db_store_msg("a@b", "Ali", "Yeni adresim Moda Caddesi 12", False,
                       "10:01", "them", mid="m2")
    xmpp._db_store_msg("a@b", "Ben", "Kapı kodu kaç?", True, "10:02", "me",
                       mid="m3")
    xmpp._db_store_msg("c@d", "Can", "Elektrik faturası 120 TL", False,
                       "11:00", "them", mid="m4")
    if encrypted_secret:
        xmpp._db_store_msg("g@x", "Ece", "Gizli adres: Bebek 5", False,
                           "12:00", "them", encrypted=True, mid="g1")


def _rag_w(monkeypatch, embed_calls=None, **kw):
    w = _w(monkeypatch, **kw)
    w._contacts = {"a@b": "Ali Veli"}
    monkeypatch.setattr(AI, "ollama_embed", _rag_embed(embed_calls))
    xmpp.MainWindow._ai_ask_history(w)
    return w, _FakeWin.instances[0]


def test_rag_answers_with_numbered_context_and_sources(tmp_db, monkeypatch):
    _seed_rag()
    embeds = []
    chat = _chat(monkeypatch, "Adres: Moda Caddesi 12 [2].",
                 "Kapı kodunu sormuşsunuz [3].")
    w, win = _rag_w(monkeypatch, embeds)
    assert win.kw["ask_ready"] is True and win.focused
    win.ask("Ali'nin adresi neydi?")
    assert w._ai_indexing is False
    first = chat.calls[0]
    assert first.user.startswith("<messages>\n[1] Ali Veli · 10:00 · Ali: "
                                 "Merhaba nasılsın\n[2] Ali Veli · 10:01")
    assert "[3] Ali Veli · 10:02 · Ben: Kapı kodu kaç?" in first.user
    assert "faturası" not in first.user
    assert first.user.endswith("Question: Ali'nin adresi neydi?")
    assert first.history == [] and first.cache is False
    assert win.answers == ["Adres: Moda Caddesi 12 [2]."]
    items, on_pick, title = win.sources
    assert title == "Kaynaklar"
    assert items == [("[2] Ali Veli · Ali (10:01): Yeni adresim Moda "
                      "Caddesi 12", ("a@b", "m2"))]
    # takip sorusu: önceki soruyla aranır, geçmiş atıfsız metindir
    win.ask("Peki kapı kodu?")
    assert "Ali'nin adresi neydi?\nPeki kapı kodu?" in embeds[-1][0]
    second = chat.calls[1]
    assert second.history == [("user", "Ali'nin adresi neydi?"),
                              ("assistant", "Adres: Moda Caddesi 12.")]
    assert win.questions == ["Ali'nin adresi neydi?", "Peki kapı kodu?"]


def test_rag_no_match_answers_without_model(tmp_db, monkeypatch):
    _seed_rag()
    chat = _chat(monkeypatch, "x")
    _w_, win = _rag_w(monkeypatch)
    win.sources = (["eski kaynak"], None, "Kaynaklar")
    win.ask("hiç konuşmadığımız şey")
    assert chat.calls == []
    assert "bulunamadı" in win.answers[0]
    assert win.sources[0] == []              # önceki turun kaynakları silindi


@pytest.mark.parametrize("answer", [None, False])
def test_rag_encrypted_hits_need_consent_on_cloud(tmp_db, monkeypatch,
                                                  answer):
    _seed_rag(encrypted_secret=True)
    chat = _chat(monkeypatch, "Moda [2].")
    asked = _Cap(ret=answer)
    monkeypatch.setattr(xmpp.messagebox, "askyesnocancel", asked)
    _w_, win = _rag_w(monkeypatch, settings={"provider": "claude"})
    win.ask("adres neydi")
    assert len(asked.calls) == 1
    if answer is None:
        assert chat.calls == [] and win.errors
        return
    (call,) = chat.calls
    assert "Bebek" not in call.user and "Moda" in call.user
    assert call.sensitive is False and call.allow_cloud is False


def test_rag_sensitive_history_requires_consent_for_next_turn(tmp_db,
                                                              monkeypatch):
    _seed_rag(encrypted_secret=True)
    chat = _chat(monkeypatch, "Bebek 5 [1].", "Fatura 120 TL [1].")
    monkeypatch.setattr(xmpp.messagebox, "askyesnocancel", _Cap(ret=True))
    asked = _Cap(ret=False)
    monkeypatch.setattr(xmpp.messagebox, "askyesno", asked)
    _w_, win = _rag_w(monkeypatch, settings={"provider": "claude"})
    win.ask("adres neydi")
    assert chat.calls[0].allow_cloud is True
    win.ask("fatura ne kadardı")         # yeni eşleşme şifresiz, geçmiş değil
    assert len(asked.calls) == 1 and len(chat.calls) == 1
    assert win.errors == ["Gönderilmedi."]


def test_rag_cancel_during_indexing_resets_flag(tmp_db, monkeypatch):
    _seed_rag()
    chat = _chat(monkeypatch, "x")
    w, win = _rag_w(monkeypatch)
    win.close()
    win.closed = False                     # kapanış olayı iletildi
    win.ask("adres")
    assert w._ai_indexing is False and chat.calls == []


def test_db_ai_context_returns_neighbours_in_chat_only(tmp_db):
    _seed_rag()
    rows = xmpp._db_ai_context([2, 4, 999], before=1, after=1)
    assert [(r[0], r[1]) for r in rows] == [(1, "a@b"), (2, "a@b"),
                                            (3, "a@b"), (4, "c@d")]
    assert rows[1][3] == "Yeni adresim Moda Caddesi 12" and rows[1][6] == "m2"
    assert xmpp._db_ai_context([]) == []


def test_index_pending_reports_progress_and_honours_cancel(tmp_db,
                                                          monkeypatch):
    _seed_rag()
    monkeypatch.setattr(AI, "ollama_embed", _rag_embed())
    w = _w(monkeypatch)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(AI.AICancelled):
        xmpp.MainWindow._ai_index_pending(w, w._ai_settings(), None, cancel)
    seen = []
    n = xmpp.MainWindow._ai_index_pending(
        w, w._ai_settings(), lambda d, t: seen.append((d, t)))
    assert n == 4 and seen == [(4, 4)]


# ── 4) Görev / etkinlik, .ics, hatırlatıcı ──────────────────────────────────
class _ActWin:
    instances = []

    def __init__(self, parent, title, subtitle, on_export, on_remind, **kw):
        self.title, self.subtitle = title, subtitle
        self.on_export, self.on_remind = on_export, on_remind
        self.items = self.error = self.busy = None
        _ActWin.instances.append(self)

    def set_busy(self, msg):
        self.busy = msg

    def set_items(self, items):
        self.items = items

    def set_error(self, msg):
        self.error = msg


_JSON = ('{"items": [{"kind": "event", "title": "Buluşma", "date": '
         '"2026-10-11", "time": "14:00", "end_time": "", "location": '
         '"Kafe", "notes": "", "quote": "yarın 14:00"}]}')


def test_extract_actions_uses_schema_and_lists_items(monkeypatch):
    w = _w(monkeypatch)
    _ActWin.instances = []
    monkeypatch.setattr(xmpp._ui_ai, "ActionsWindow", _ActWin)
    spy = _Cap(ret=_JSON)
    monkeypatch.setattr(AI, "chat", spy)
    xmpp.MainWindow._ai_extract_actions(w, "a@b")
    (args, kw), = spy.calls
    assert kw["schema"] is AI.ACTIONS_SCHEMA and kw["effort"] == "medium"
    assert "Today is" in args[2] and "Yarın 14:00" in args[2]
    item = _ActWin.instances[0].items[0]
    assert item["title"] == "Buluşma" and item["time"] == "14:00"
    spy.ret = "anlamsız"
    xmpp.MainWindow._ai_extract_actions(w, "a@b")
    assert _ActWin.instances[1].error and _ActWin.instances[1].items is None


def _item(**kw):
    base = {"kind": "event", "title": "Toplantı", "date": "2026-10-12",
            "time": "14:00", "end_time": "", "location": "", "notes": "",
            "quote": ""}
    base.update(kw)
    return base


def test_export_ics_writes_file_validates_and_handles_cancel(tmp_path,
                                                             monkeypatch):
    import tkinter.filedialog as fd
    w = _w(monkeypatch)
    target = tmp_path / "plan.ics"
    dialog = _Cap(ret=str(target))
    monkeypatch.setattr(fd, "asksaveasfilename", dialog)
    ok, msg = xmpp.MainWindow._ai_export_ics(w, [_item()], "Ali Veli")
    assert ok and "plan.ics" in msg
    assert dialog.calls[0][1]["initialfile"] == "Ali_Veli-gorevler.ics"
    data = target.read_bytes().decode("utf-8")
    assert "BEGIN:VEVENT\r\n" in data and "SUMMARY:Toplantı\r\n" in data
    ok, msg = xmpp.MainWindow._ai_export_ics(w, [_item(date="12/10")], "x")
    assert not ok and "YYYY-AA-GG" in msg and len(dialog.calls) == 1
    dialog.ret = ""
    assert xmpp.MainWindow._ai_export_ics(w, [_item()], "x") is None


def _cfg_store(monkeypatch, cfg):
    saved = []
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    monkeypatch.setattr(xmpp, "_save_config",
                        lambda c: saved.append(dict(c)))
    return saved


def test_add_reminders_persists_and_arms_once(monkeypatch):
    w = _w(monkeypatch)
    cfg = {"ai_reminders": "bozuk"}
    saved = _cfg_store(monkeypatch, cfg)
    w._after = _Cap(ret="after#1")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    ok, msg = xmpp.MainWindow._ai_add_reminders(
        w, [_item(date=tomorrow), _item(title="Saatsiz", time="")], "a@b")
    assert ok and "1 hatırlatıcı" in msg and "1 öğede" in msg
    (stored,) = saved[-1]["ai_reminders"]
    assert stored["title"] == "Toplantı" and stored["jid"] == "a@b"
    assert w._after.calls == [((1000, w._ai_check_reminders), {})]
    xmpp.MainWindow._ai_add_reminders(w, [_item(date=tomorrow)], "a@b")
    assert len(w._after.calls) == 1 and len(cfg["ai_reminders"]) == 2
    ok, msg = xmpp.MainWindow._ai_add_reminders(
        w, [_item(date="2000-01-01")], "a@b")
    assert not ok and "ileri bir" in msg


def test_check_reminders_fires_due_keeps_pending(monkeypatch):
    w = _w(monkeypatch)
    w._contacts = {"a@b": "Ali Veli"}
    now = datetime.now()
    fmt = "%Y-%m-%dT%H:%M"
    cfg = {"ai_reminders": [
        {"title": "Geç kaldı", "when": (now - timedelta(hours=1))
         .strftime(fmt), "jid": "a@b", "location": "Ofis"},
        {"title": "Sonra", "when": (now + timedelta(hours=1)).strftime(fmt)},
        {"title": "Bozuk", "when": "yarın"}]}
    saved = _cfg_store(monkeypatch, cfg)
    w._after = _Cap(ret="after#2")
    notes = _Cap()
    monkeypatch.setattr(xmpp, "_desktop_notify", notes)
    info = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "showinfo", info)
    xmpp.MainWindow._ai_check_reminders(w)
    assert [r["title"] for r in saved[-1]["ai_reminders"]] == ["Sonra"]
    assert notes.calls[0][0] == ("⏰ Hatırlatıcı", "Geç kaldı — Ofis")
    text = info.calls[0][0][1]
    assert "Geç kaldı — Ofis" in text and "(Ali Veli)" in text
    assert "zamanı geçti" in text
    assert w._after.calls == [((w._AI_REMINDER_POLL_MS,
                                w._ai_check_reminders), {})]
    assert w._ai_reminder_after == "after#2"


def test_check_reminders_idle_when_nothing_stored(monkeypatch):
    w = _w(monkeypatch)
    saved = _cfg_store(monkeypatch, {})
    w._after = _Cap()
    xmpp.MainWindow._ai_check_reminders(w)
    assert saved == [] and w._after.calls == []
    assert w._ai_reminder_after is None


# ── 5) Sesle yaz (dikte) ────────────────────────────────────────────────────
def test_dictate_guards(monkeypatch):
    import importlib.util
    w = _w(monkeypatch, settings={"provider": "off"})
    w._start_recording = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "askyesno", _Cap(ret=False))
    xmpp.MainWindow._ai_dictate(w)                    # AI kapalı
    w = _w(monkeypatch)
    w._start_recording = _Cap()
    warn = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "showwarning", warn)
    monkeypatch.setattr(xmpp, "_HAS_PYAUDIO", False)
    xmpp.MainWindow._ai_dictate(w)                    # mikrofon yok
    monkeypatch.setattr(xmpp, "_HAS_PYAUDIO", True)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    xmpp.MainWindow._ai_dictate(w)                    # whisper yok
    assert len(warn.calls) == 2 and w._start_recording.calls == []
    assert "pyaudio" in warn.calls[0][0][1]
    assert "faster-whisper" in warn.calls[1][0][1]
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    xmpp.MainWindow._ai_dictate(w)
    assert w._start_recording.calls == [((), {"mode": "dictate"})]


def test_dictate_second_press_stops_only_dictation(monkeypatch):
    w = _w(monkeypatch)
    w._stop_recording = _Cap()
    w._recording, w._rec_mode = True, "voice"
    xmpp.MainWindow._ai_dictate(w)
    assert w._stop_recording.calls == []
    w._rec_mode = "dictate"
    xmpp.MainWindow._ai_dictate(w)
    assert w._stop_recording.calls == [((), {"send": True})]


def test_mic_button_stops_dictation_even_offline(monkeypatch):
    """Regresyon: dikte sürerken ⏹ (mikrofon) butonu bağlantı olmasa da
    dikteyi bitirir; ses mesajı yolu bağlantı ister (değişmedi)."""
    w = _w(monkeypatch)
    w.bot = None
    w._stop_recording = _Cap()
    w._start_recording = _Cap()
    w._recording, w._rec_mode = True, "dictate"
    xmpp.MainWindow._toggle_voice(w)
    assert w._stop_recording.calls == [((), {"send": True})]
    w._recording, w._rec_mode = True, "voice"
    xmpp.MainWindow._toggle_voice(w)
    assert len(w._stop_recording.calls) == 1 and w._start_recording.calls == []


class _Widget:
    def __init__(self):
        self.cfg = {}

    def config(self, **kw):
        self.cfg.update(kw)

    def place_forget(self):
        pass

    def destroy(self):
        pass


def _recording_w(monkeypatch, mode):
    w = _w(monkeypatch)
    w._recording, w._rec_mode, w._rec_cancelled = True, mode, False
    w._rec_overlay, w._mic_btn = _Widget(), _Widget()
    w._voice_frames = [b"\x10\x27" * 4000]
    w._voice_lock = threading.Lock()
    w._rec_start_time = time.time() - 2
    w._ai_transcribe_dictation = _Cap()
    w._finalize_recording = _Cap()
    return w


def test_stop_recording_routes_dictation_and_keeps_voice_path(monkeypatch):
    w = _recording_w(monkeypatch, "dictate")
    xmpp.MainWindow._stop_recording(w, send=True)
    assert w._ai_transcribe_dictation.calls == [
        ((b"\x10\x27" * 4000, "a@b"), {})]
    assert w._finalize_recording.calls == [] and w._rec_mode == "voice"

    class _SyncThread:
        def __init__(self, target=None, args=(), daemon=None, **k):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)
    w = _recording_w(monkeypatch, "voice")
    monkeypatch.setattr(xmpp.threading, "Thread", _SyncThread)
    xmpp.MainWindow._stop_recording(w, send=True)
    monkeypatch.undo()
    assert w._ai_transcribe_dictation.calls == []
    assert len(w._finalize_recording.calls) == 1


def test_transcribe_dictation_appends_to_draft_and_cleans_temp(monkeypatch):
    w = _w(monkeypatch)
    _composer(w, "Selam")
    paths = []

    def _tr(path, model):
        paths.append(path)
        with wave.open(path, "rb") as wf:          # gerçek WAV yazılmış
            assert wf.getnchannels() == 1 and wf.getframerate() == 44100
        return " yarın görüşürüz "
    monkeypatch.setattr(AI, "transcribe_file", _tr)
    xmpp.MainWindow._ai_transcribe_dictation(w, b"\x10\x27" * 4000, "a@b")
    assert w.msg_var.get() == "Selam yarın görüşürüz"
    assert not os.path.exists(paths[0]) and w._temp_files == []


def test_transcribe_dictation_no_speech_and_chat_switch(monkeypatch):
    w = _w(monkeypatch)
    _composer(w, "Taslak")
    info = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "showinfo", info)
    monkeypatch.setattr(AI, "transcribe_file", lambda p, m: AI.NO_SPEECH)
    xmpp.MainWindow._ai_transcribe_dictation(w, b"\x10\x27" * 4000, "a@b")
    assert len(info.calls) == 1 and w.msg_var.get() == "Taslak"
    monkeypatch.setattr(AI, "transcribe_file", lambda p, m: "metin")
    w.active = "baska@x"
    xmpp.MainWindow._ai_transcribe_dictation(w, b"\x10\x27" * 4000, "a@b")
    win = _FakeWin.instances[-1]
    assert w.msg_var.get() == "Taslak" and win.text == "metin"
    (label, fn), = win.actions
    fn("metin")
    assert w._load_chat.calls == [(("a@b",), {})]


def test_transcribe_dictation_error_resets_busy(monkeypatch):
    w = _w(monkeypatch)
    _composer(w, "")
    btn = _Widget()
    w._chat_shell = types.SimpleNamespace(_ai_btn=btn)
    err = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "showerror", err)

    def _boom(p, m):
        raise AI.AIError("model yüklenemedi")
    monkeypatch.setattr(AI, "transcribe_file", _boom)
    xmpp.MainWindow._ai_transcribe_dictation(w, b"\x10\x27" * 4000, "a@b")
    assert err.calls[0][0][1] == "model yüklenemedi"
    assert btn.cfg["text"] == "✨" and w._temp_files == []


# ── 6) Menüler ve kısayollar ────────────────────────────────────────────────
class _Menu:
    def __init__(self):
        self.items = []

    def add_command(self, label=None, command=None, accelerator=None, **k):
        self.items.append((label, accelerator, command))

    def add_cascade(self, label=None, menu=None, **k):
        self.items.append((label, "▸", menu))

    def add_separator(self):
        self.items.append(("—", None, None))

    def tk_popup(self, x, y):
        pass

    def grab_release(self):
        pass


def _submenus(w):
    """_ai_new_menu yerine sahte menü üretici (oluşturulanlar listede)."""
    made = []

    def _new(parent):
        made.append(_Menu())
        return made[-1]
    w._ai_new_menu = _new
    return made


def _tree(menu):
    return [(lbl, acc, _tree(c) if acc == "▸" else None)
            for lbl, acc, c in menu.items]


def test_chat_menu_items_and_order(monkeypatch):
    w = _w(monkeypatch)
    _submenus(w)
    w._ai_unread_at_open = {"a@b": 2}
    w._ai_extract_actions = _Cap()
    w._ai_assistant_run = _Cap()
    menu = _Menu()
    xmpp.MainWindow._ai_fill_chat_items(w, menu, "a@b")
    assert _tree(menu) == [
        ("✨ Asistan…", "Ctrl+Shift+K", None),
        ("📬 Okunmamışları özetle (2)", None, None),
        ("💬 Bu sohbet", "▸", [
            ("📝 Sohbeti özetle", None, None),
            ("📅 Görev ve etkinlikleri çıkar", None, None)]),
        ("🗂 Tüm sohbetler", "▸", [
            ("📥 Neler kaçırdım?", "Ctrl+Shift+M", None),
            ("❓ Yanıt bekleyen sorular", "Ctrl+Shift+Q", None),
            ("✍ Yanıt taslakları", "Ctrl+Shift+R", None),
            ("🔎 Geçmişe sor…", "Ctrl+Shift+H", None),
            ("🧠 Anlamsal arama…", None, None)]),
        ("—", None, None),
        ("⚙ AI Ayarları…", None, None)]
    # Düzenlenebilir liste kendi penceresinde; sonuçlar asistanın içinde
    menu.items[2][2].items[1][2]()
    assert w._ai_extract_actions.calls == [(("a@b",), {})]
    menu.items[1][2]()
    menu.items[2][2].items[0][2]()
    every = menu.items[3][2].items
    for i in (0, 1, 3):         # neler kaçırdım, sorular, geçmişe sor
        every[i][2]()
    assert w._ai_assistant_run.calls == [
        (("summarize_unread", "a@b"), {}), (("summarize_chat", "a@b"), {}),
        (("missed",), {}), (("pending_questions",), {}),
        (("ask_history",), {})]


def test_chat_menu_hides_unread_item_without_unread(monkeypatch):
    w = _w(monkeypatch)
    _submenus(w)
    menu = _Menu()
    xmpp.MainWindow._ai_fill_chat_items(w, menu, "a@b")
    assert [lbl for lbl, _a, _c in menu.items[:2]] == ["✨ Asistan…",
                                                      "💬 Bu sohbet"]


def test_composer_menu_opens_assistant_and_offers_writing_tools(monkeypatch):
    w = _w(monkeypatch)
    made = _submenus(w)
    w._ai_assistant_open = _Cap()
    w._ai_assistant_run = _Cap()
    ev = types.SimpleNamespace(x_root=1, y_root=2)
    xmpp.MainWindow._ai_composer_menu(w, ev)
    main = made[0]
    labels = [lbl for lbl, _a, _c in main.items]
    assert labels == ["✨ Asistan (bu sohbet)…", "💡 Yanıt öner",
                      "🎙 Sesle yaz (dikte)", "✍ Taslağı düzenle", "—",
                      "⚙ AI Ayarları…"]
    rewrite = main.items[3][2]
    assert [lbl for lbl, _a, _c in rewrite.items] == [
        label for label, _i in xmpp._ai.REWRITE_MODES.values()]
    main.items[0][2]()
    main.items[1][2]()
    assert len(w._ai_assistant_open.calls) == 1
    assert w._ai_assistant_run.calls == [(("suggest_replies", "a@b"), {})]
    made.clear()
    w._recording, w._rec_mode = True, "dictate"
    xmpp.MainWindow._ai_composer_menu(w, ev)
    assert made[0].items[2][0] == "⏹ Dikteyi bitir"


def test_composer_menu_keeps_grab_so_outside_click_closes_it(monkeypatch):
    # Kanıt: X11'de tk_popup beklemeden döner ve menünün dışarı tıklamayı
    # görmesini sağlayan global grab'i kurar (tk/menu.tcl ::tk_popup). Hemen
    # ardından grab_release çağrılınca menü açık kalıyor, dışarı tıklayınca
    # kapanmıyordu (gerçek Tk: grab_current() None).
    w = _w(monkeypatch)
    _submenus(w)
    calls = []
    monkeypatch.setattr(_Menu, "tk_popup",
                        lambda self, x, y: calls.append("popup"))
    monkeypatch.setattr(_Menu, "grab_release",
                        lambda self: calls.append("release"))
    xmpp.MainWindow._ai_composer_menu(w, types.SimpleNamespace(
        x_root=1, y_root=2))
    assert calls == ["popup"]


def test_composer_menu_shows_undo_only_when_available(monkeypatch):
    w = _w(monkeypatch)
    made = _submenus(w)
    w._ai_undo = (w.active, "eski")
    xmpp.MainWindow._ai_composer_menu(w, types.SimpleNamespace(
        x_root=1, y_root=2))
    assert made[0].items[4][0] == "↶ AI değişikliğini geri al"


def test_shortcuts_route_ai_actions_into_assistant(monkeypatch):
    w = _w(monkeypatch)
    binds = {}
    w.root = types.SimpleNamespace(
        bind=lambda seq, fn: binds.__setitem__(seq, fn))
    w._msg_entry = None
    w._sidebar_search = None
    w._ai_dictate = _Cap()
    w._ai_assistant_run = _Cap()
    xmpp.MainWindow._bind_shortcuts(w)
    for seq in ("<Control-Shift-M>", "<Control-Shift-H>",
                "<Control-Shift-Q>", "<Control-Shift-S>"):
        binds[seq](None)
    assert w._ai_assistant_run.calls == [
        (("missed",), {}), (("ask_history",), {}),
        (("pending_questions",), {})]
    assert len(w._ai_dictate.calls) == 1
