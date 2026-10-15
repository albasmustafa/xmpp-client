"""Yanıt bekleyen sorular (xmppcore/questions + storage + MainWindow + görünüm).

Kanıtlar:
- Soru tespiti: soru işareti, Türkçe soru eki, soru sözcüğüyle başlama;
  bağlantı içindeki "?", alıntı satırı, kod, silinmiş/ses yer tutucusu
  soru sayılmaz.
- find_pending: sohbet başına tek kayıt (en yeni soru metni, en eski
  sorunun zamanı, soru sayısı); en uzun bekleyen önce, tarihsizler sonda;
  yok sayılan anahtar yeni soru gelene kadar gizli; odalar hariç.
- Depolama: her satıra tam tarih (stored_at) yazılır; eski şemaya sütun
  eklenir; `_db_unanswered` yalnız benim son mesajımdan sonraki gelen
  (sistem olmayan) satırları döndürür ve tarama penceresiyle sınırlıdır.
- MainWindow: pencere girişleri etiket/yaş ile beslenir; odalar (katılınan
  ve kayıtlı) ile yok sayılanlar elenir; hatırlatma mevcut hatırlatıcı
  yolundan yarın 09:00'a kurulur; yok sayma config'e yazılır; bağlantı
  bildirimi oturumda bir kez ve yalnız 1 saatten eski sorular için çıkar.
- Görünüm: kartlar, sohbete git / hatırlat / yok say geri çağrıları.
"""
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ai_dialog_view import _W, _find, fake_tk  # noqa: E402,F401
from test_history_window_bounds import _Cap  # noqa: E402

import ui.dialogs.ai as ui_ai  # noqa: E402
import xmpp  # noqa: E402
from xmppcore import ai, questions  # noqa: E402

FMT = questions.STORED_AT_FMT


def _r(i, jid, body, at="2026-10-08T10:00:00", sender="Ali", enc=0):
    return (i, jid, sender, body, at, f"m{i}", enc)


# ── 1) Soru tespiti ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("Toplantı saat kaçta?", True),
    ("Yarın geliyor musun", True),
    ("Bunu sen mi yaptın", True),
    ("hazır mısınız", True),
    ("ne zaman buluşuyoruz", True),
    ("How are you doing", True),
    ("tamam görüşürüz", False),
    ("mimar sinan camii", False),
    ("https://x.com/a?b=1", False),
    ("> naber?\ntamam", False),
    ("`a?b` kodu çalıştı", False),
    (ai.RETRACTED_BODY, False),
    (ai.VOICE_PLACEHOLDER, False),
    ("bak https://x/y.ogg", False),
])
def test_is_question(text, expected):
    assert questions.is_question(text) is expected


# ── 2) find_pending ─────────────────────────────────────────────────────────
def test_find_pending_groups_per_chat_and_sorts_oldest_first():
    rows = [
        _r(1, "a@x", "naber?", "2026-10-08T10:00:00"),
        _r(2, "a@x", "tamam"),
        _r(3, "a@x", "yarın geliyor musun", "2026-10-09T09:00:00"),
        _r(4, "b@x", "saat kaç?", "2026-10-07T08:00:00", enc=1),
        _r(5, "c@x", "selam"),
        _r(6, "d@x", "nerede?", ""),
    ]
    out = questions.find_pending(rows)
    assert [e["jid"] for e in out] == ["b@x", "a@x", "d@x"]
    a = out[1]
    assert (a["count"], a["key"], a["text"]) == (
        2, "a@x#3", "yarın geliyor musun")
    assert a["since"] == datetime(2026, 10, 8, 10, 0)
    assert out[0]["encrypted"] is True and a["encrypted"] is False
    assert out[2]["since"] is None


def test_dismissed_hidden_until_new_question_and_rooms_skipped():
    rows = [_r(1, "a@x", "naber?"), _r(2, "oda@c", "kim geliyor?")]
    out = questions.find_pending(rows, dismissed=["a@x#1"],
                                 skip_jids={"oda@c"})
    assert out == []
    rows.append(_r(3, "a@x", "orada mısın?"))
    out = questions.find_pending(rows, dismissed=["a@x#1"],
                                 skip_jids={"oda@c"})
    assert [e["key"] for e in out] == ["a@x#3"]


def test_format_age():
    now = datetime(2026, 10, 10, 12, 0)
    cases = [(None, "tarihi bilinmiyor"),
             (now - timedelta(seconds=30), "az önce"),
             (now - timedelta(minutes=5), "5 dakika önce"),
             (now - timedelta(hours=3), "3 saat önce"),
             (datetime(2026, 10, 9, 8, 0), "dün"),
             (datetime(2026, 10, 7, 13, 0), "3 gün önce")]
    for since, expected in cases:
        assert questions.format_age(since, now) == expected


def test_dismiss_list_dedupes_and_caps():
    stored = [f"k{i}" for i in range(questions.DISMISS_CAP)]
    out = questions.dismiss(stored + ["x"], "k0")
    assert len(out) == questions.DISMISS_CAP and out[-1] == "k0"
    assert out.count("k0") == 1
    assert questions.dismiss("bozuk", "y") == ["y"]


def test_reminder_item_goes_through_existing_reminder_path():
    item = questions.reminder_item({"text": "saat kaç?"}, "Ali",
                                   date(2026, 10, 10))
    valid, errors = ai.validate_actions([item])
    assert errors == []
    assert (valid[0]["date"], valid[0]["time"]) == ("2026-10-11", "09:00")
    rem = ai.reminder_from_action(valid[0], "a@x",
                                  datetime(2026, 10, 10, 23, 0))
    assert rem["when"] == "2026-10-11T09:00"
    assert rem["title"].startswith("Yanıtla: Ali — saat kaç?")


# ── 3) Depolama ─────────────────────────────────────────────────────────────
@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "m.db"))
    xmpp._db_conn = None
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
        xmpp._db_conn = None


def test_store_writes_full_date(db):
    before = datetime.now().replace(microsecond=0)
    xmpp._db_store_msg("a@x", "Ali", "naber?", False, "10:00", "them")
    (stored,) = xmpp._get_db().execute(
        "SELECT stored_at FROM messages").fetchone()
    assert before <= datetime.strptime(stored, FMT) <= datetime.now()


def test_unanswered_only_after_my_last_message(db):
    store = xmpp._db_store_msg
    store("a@x", "Ali", "ilk soru?", False, "10:00", "them")
    store("a@x", "Ben", "cevap", True, "10:01", "me")
    store("a@x", "Ali", "ikinci soru?", False, "10:02", "them")
    store("a@x", "", "Ali çevrimdışı", False, "10:03", "sys")
    store("b@x", "Ayşe", "b sorusu?", False, "10:04", "them")
    store("c@x", "Ben", "sadece ben yazdım", True, "10:05", "me")
    rows = xmpp._db_unanswered()
    assert [(r[1], r[3]) for r in rows] == [("a@x", "ikinci soru?"),
                                            ("b@x", "b sorusu?")]
    assert all(datetime.strptime(r[4], FMT) for r in rows)


def test_unanswered_scan_window(db):
    for i in range(5):
        xmpp._db_store_msg("a@x", "Ali", f"s{i}?", False, "10:00", "them")
    assert [r[3] for r in xmpp._db_unanswered(scan_limit=2)] == ["s3?",
                                                                 "s4?"]


def test_legacy_schema_gets_column_and_old_rows_have_no_date(tmp_path,
                                                             monkeypatch):
    path = str(tmp_path / "eski.db")
    conn = sqlite3.connect(path)
    # stored_at'tan önceki şema (diğer sütunlar mevcut göçlerle gelmişti)
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY "
                 "AUTOINCREMENT, jid TEXT NOT NULL, sender TEXT, body TEXT, "
                 "is_me INTEGER, timestamp TEXT, tag TEXT, oob TEXT DEFAULT "
                 "'', encrypted INTEGER DEFAULT 0, mid TEXT DEFAULT '', "
                 "local_path TEXT DEFAULT '', reply_id TEXT DEFAULT '', "
                 "reply_sender TEXT DEFAULT '', reply_body TEXT DEFAULT '')")
    conn.execute("INSERT INTO messages (jid, sender, body, is_me, timestamp, "
                 "tag) VALUES ('a@x', 'Ali', 'eski soru?', 0, '09:00', "
                 "'them')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(xmpp, "_DB_PATH", path)
    xmpp._db_conn = None
    try:
        rows = xmpp._db_unanswered()
        assert [(r[3], r[4]) for r in rows] == [("eski soru?", "")]
        assert questions.find_pending(rows)[0]["since"] is None
    finally:
        if xmpp._db_conn is not None:
            xmpp._db_conn.close()
            xmpp._db_conn = None


# ── 4) MainWindow akışları ──────────────────────────────────────────────────
def _qw(monkeypatch, rows, cfg=None):
    w = object.__new__(xmpp.MainWindow)
    w.root = None
    w.rooms = {"oda@c": {}}
    w._contacts = {"a@x": "Ali"}
    cfg = cfg if cfg is not None else {}
    saved = []
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    monkeypatch.setattr(xmpp, "_save_config", saved.append)
    monkeypatch.setattr(xmpp, "_db_unanswered", lambda: rows)
    w._ai_submit = lambda job, done, err: done(job())
    return w, saved


class _FakeWin:
    created = []

    def __init__(self, parent, on_open, on_remind, on_dismiss):
        self.cbs = (on_open, on_remind, on_dismiss)
        self.entries = None
        _FakeWin.created.append(self)

    def set_entries(self, entries):
        self.entries = entries

    def set_error(self, message):
        self.error = message


def test_pending_questions_window_flow(monkeypatch):
    two_h = (datetime.now() - timedelta(hours=2, minutes=1)).strftime(FMT)
    rows = [_r(1, "a@x", "naber?", two_h), _r(2, "oda@c", "kim?"),
            _r(3, "eski@c", "ne?"), _r(9, "z@x", "nasıl?")]
    cfg = {"rooms": {"eski@c": {}}, questions.DISMISS_KEY: ["z@x#9"]}
    w, saved = _qw(monkeypatch, rows, cfg)
    _FakeWin.created = []
    monkeypatch.setattr(xmpp._ui_ai, "PendingQuestionsWindow", _FakeWin)
    xmpp.MainWindow._ai_pending_questions(w)
    win = _FakeWin.created[0]
    assert [e["jid"] for e in win.entries] == ["a@x"]
    entry = win.entries[0]
    assert (entry["label"], entry["age"]) == ("Ali", "2 saat önce")

    w._ai_open_chat = _Cap()
    win.cbs[0](entry)
    assert w._ai_open_chat.calls == [(("a@x",), {})]

    reminders = []
    w._ai_add_reminders = lambda items, jid: (reminders.append(
        (items, jid)), (True, "ok"))[1]
    assert win.cbs[1](entry) == (True, "ok")
    (items, jid), = reminders
    assert jid == "a@x" and items[0]["time"] == "09:00"
    assert items[0]["date"] == (date.today() + timedelta(days=1)).isoformat()

    win.cbs[2](entry)
    assert saved[-1][questions.DISMISS_KEY] == ["z@x#9", "a@x#1"]


def test_remind_creates_real_reminder_record(monkeypatch):
    w, saved = _qw(monkeypatch, [])
    w._ai_arm_reminders = _Cap()
    ok, msg = xmpp.MainWindow._questions_remind(
        w, {"jid": "a@x", "label": "Ali", "text": "saat kaç?"})
    assert ok and "1 hatırlatıcı" in msg
    (rec,) = saved[-1][ai.REMINDER_KEY]
    assert rec["jid"] == "a@x" and rec["when"].endswith("T09:00")
    assert len(w._ai_arm_reminders.calls) == 1


def test_nudge_once_and_only_for_old_questions(monkeypatch):
    old = (datetime.now() - timedelta(hours=3)).strftime(FMT)
    fresh = (datetime.now() - timedelta(minutes=10)).strftime(FMT)
    rows = [_r(1, "a@x", "naber?", old), _r(2, "b@x", "geliyor musun", fresh)]
    w, _s = _qw(monkeypatch, rows)
    w._show_toast = _Cap()
    xmpp.MainWindow._questions_nudge(w)
    xmpp.MainWindow._questions_nudge(w)          # yeniden bağlanma
    assert len(w._show_toast.calls) == 1
    title, text = w._show_toast.calls[0][0]
    assert "1 sohbette" in text and "Ctrl+Shift+Q" in text
    assert len(text) <= 80                       # toast metni kırpılmaz


def test_nudge_silent_for_fresh_questions(monkeypatch):
    fresh = (datetime.now() - timedelta(minutes=10)).strftime(FMT)
    w, _s = _qw(monkeypatch, [_r(1, "a@x", "naber?", fresh)])
    w._show_toast = _Cap()
    xmpp.MainWindow._questions_nudge(w)
    assert w._show_toast.calls == []


# ── 5) Görünüm (sahte tk) ───────────────────────────────────────────────────
@pytest.mark.usefixtures("fake_tk")
def test_pending_window_cards_and_callbacks():
    opened, dismissed = [], []
    win = ui_ai.PendingQuestionsWindow(
        _W(), on_open=opened.append,
        on_remind=lambda e: (True, "⏰ 1 hatırlatıcı kuruldu."),
        on_dismiss=dismissed.append)
    entries = [
        dict(jid="a@x", key="a@x#1", label="Ali", age="2 saat önce",
             text="naber?", count=2, encrypted=False),
        dict(jid="b@x", key="b@x#5", label="Ayşe", age="dün",
             text="saat kaç?", count=1, encrypted=True)]
    win.set_entries(entries)
    assert "2 sohbette" in win._status.kw["text"]
    assert _find(win.top, "👤 Ali  ·  2 saat önce  ·  2 soru") is not None
    assert _find(win.top, "🔒 Ayşe  ·  dün") is not None

    card = win._cards["a@x#1"]
    _find(card, "💬 Sohbete git").click()
    assert opened == [entries[0]]
    _find(card, "⏰ Yarın 09:00 hatırlat").click()
    assert win._status.kw["text"] == "⏰ 1 hatırlatıcı kuruldu."
    _find(card, "✓ Yok say").click()
    assert dismissed == [entries[0]] and card.destroyed
    assert "a@x#1" not in win._cards
    assert "1 sohbette" in win._status.kw["text"]


@pytest.mark.usefixtures("fake_tk")
def test_pending_window_empty_state():
    win = ui_ai.PendingQuestionsWindow(_W(), on_open=None, on_remind=None,
                                       on_dismiss=None)
    win.set_entries([])
    assert "Yanıt bekleyen soru yok" in win._status.kw["text"]
