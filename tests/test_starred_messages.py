"""⭐ Yıldızlı mesajlar: DB bayrağı (messages.starred), masaüstü sağ tık
menüsü ve liste penceresi, web komutları (star / starred).

Sözleşme: yıldız (jid, mid) kapsamlıdır; geçmiş silinince yıldız da gider;
geri çekilmiş mesaj listelenmez; masaüstü ve web aynı DB'yi kullanır.
"""
import os
import sqlite3
import sys
import tkinter as tk
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_chat_actions import _labels, _patch_tk, _theme  # noqa: E402
from test_webapp import session  # noqa: E402,F401  (fixture)

import xmpp  # noqa: E402
from ui.chat import actions as actions_mod  # noqa: E402
from ui.dialogs import starred as ui_starred  # noqa: E402
from xmppcore import storage as st  # noqa: E402
from xmppcore.ai import RETRACTED_BODY  # noqa: E402

ALI, ROOM = "ali@x.im", "oda@conf.x.im"


@pytest.fixture()
def db(monkeypatch, tmp_path):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "m.db"))
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    xmpp._db_conn = None
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    xmpp._db_conn = None


def _msg(jid, body, mid, *, me=False, at="2026-11-24T10:00:00"):
    st._db_store_msg(jid, "Ben" if me else "ali", body, me, at[11:16],
                     "me" if me else "them", mid=mid, stored_at=at)


# ── DB ──────────────────────────────────────────────────────────────────────


def test_star_is_chat_scoped_listed_newest_first(db):
    _msg(ALI, "eski", "m1", at="2026-11-20T09:00:00")
    _msg(ALI, "yeni", "m2", me=True, at="2026-11-24T18:30:00")
    _msg(ROOM, "aynı mid başka sohbet", "m1")
    assert st._db_set_starred(ALI, "m1") and st._db_set_starred(ALI, "m2")
    assert st._db_is_starred(ALI, "m1") and not st._db_is_starred(ROOM, "m1")
    rows = st._db_load_starred()
    assert [(r[0], r[2], r[6]) for r in rows] == [(ALI, "yeni", "m2"),
                                                  (ALI, "eski", "m1")]
    assert st._db_set_starred(ALI, "m2", False)
    assert [r[6] for r in st._db_load_starred()] == ["m1"]


def test_unknown_or_empty_message_cannot_be_starred(db):
    assert st._db_set_starred(ALI, "yok") is False
    assert st._db_set_starred("", "m1") is False
    assert st._db_set_starred(ALI, "") is False
    assert st._db_is_starred(ALI, "") is False


def test_edit_keeps_star_retract_hides_clear_removes(db):
    _msg(ALI, "ilk", "m1")
    _msg(ALI, "iki", "m2")
    st._db_set_starred(ALI, "m1")
    st._db_set_starred(ALI, "m2")
    st._db_update_msg_body(ALI, "m1", "düzeltildi")
    st._db_update_msg_body(ALI, "m2", RETRACTED_BODY)
    rows = st._db_load_starred(skip_bodies=(RETRACTED_BODY,))
    assert [(r[2], r[6]) for r in rows] == [("düzeltildi", "m1")]
    st._db_clear_chat(ALI)
    assert st._db_load_starred() == []


def test_duplicate_rows_listed_once(db):
    _msg(ALI, "kopya", "m1")
    _msg(ALI, "kopya", "m1")
    st._db_set_starred(ALI, "m1")
    assert len(st._db_load_starred()) == 1


def test_old_database_gets_starred_column(tmp_path, monkeypatch):
    path = tmp_path / "eski.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "jid TEXT NOT NULL, sender TEXT, body TEXT, is_me INTEGER, "
                "timestamp TEXT, tag TEXT)")
    con.execute("INSERT INTO messages (jid, sender, body, is_me, timestamp, "
                "tag) VALUES ('a@x', 'a', 'eski', 0, '10:00', 'them')")
    con.commit()
    con.close()
    monkeypatch.setattr(xmpp, "_DB_PATH", str(path))
    conn = st._init_db()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
        assert "starred" in cols
        assert conn.execute("SELECT starred FROM messages").fetchone() == (0,)
    finally:
        conn.close()


# ── Masaüstü: sağ tık menüsü ────────────────────────────────────────────────


def _menu(monkeypatch, *, star, starred=False):
    menus = _patch_tk(monkeypatch)
    calls = []
    cb = {k: (lambda *a, k=k: calls.append(k))
          for k in ("on_copy", "on_pin", "on_star")}
    actions_mod.show_context_menu(
        "ROOT", 1, 2, theme=_theme(), t=lambda k: k.upper(),
        caps={"copy": True, "pin": True, "star": star}, mine=set(),
        has_reactions=False, callbacks=cb, starred=starred)
    return menus[0], calls


def test_star_item_follows_pin_and_toggles_label(monkeypatch):
    menu, calls = _menu(monkeypatch, star=True)
    assert _labels(menu) == ["📋 COPY", "📌 PIN", "⭐ Yıldızla"]
    menu.items[-1][2]()
    assert calls == ["on_star"]
    menu, _ = _menu(monkeypatch, star=True, starred=True)
    assert _labels(menu)[-1] == "☆ Yıldızı Kaldır"
    menu, _ = _menu(monkeypatch, star=False)
    assert _labels(menu) == ["📋 COPY", "📌 PIN"]     # eski sıra aynen


def _row(**kw):
    base = dict(_body="Toplantı 15:00", _is_me=False, _mid="m1",
                _sender="ali", _retracted=False, _reply_to=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _ctx_win(monkeypatch, starred):
    captured = {}
    monkeypatch.setattr(xmpp._actions_ui, "show_context_menu",
                        lambda *a, **k: captured.update(k))
    monkeypatch.setattr(xmpp, "_db_is_starred", lambda j, m: starred)
    w = object.__new__(xmpp.MainWindow)
    w.root = None
    w.active = ALI
    w.rooms = {}
    w.bot = object()
    w._my_reactions = {}
    w._reactions = {}
    w._ai_message_items = lambda row: set()
    w._ai_message_callbacks = lambda row: {}
    toggles = []
    w._toggle_star = lambda *a: toggles.append(a)
    return w, captured, toggles


@pytest.mark.parametrize("starred", [False, True])
def test_context_menu_offers_star_toggle(monkeypatch, starred):
    w, kw, toggles = _ctx_win(monkeypatch, starred)
    ev = types.SimpleNamespace(x_root=1, y_root=2)
    xmpp.MainWindow._message_context_menu(w, ev, _row())
    assert kw["caps"]["star"] is True and kw["starred"] is starred
    kw["callbacks"]["on_star"]()
    assert toggles == [(ALI, "m1", not starred, "Toplantı 15:00")]


def test_context_menu_no_star_for_retracted_or_midless(monkeypatch):
    w, kw, _t = _ctx_win(monkeypatch, False)
    ev = types.SimpleNamespace(x_root=1, y_root=2)
    xmpp.MainWindow._message_context_menu(w, ev, _row(_retracted=True))
    assert kw["caps"]["star"] is False
    xmpp.MainWindow._message_context_menu(w, ev, _row(_mid=""))
    assert kw["caps"]["star"] is False


def test_toggle_star_reports_message_missing_from_db(db):
    w = object.__new__(xmpp.MainWindow)
    toasts = []
    w._show_toast = lambda *a: toasts.append(a)
    assert xmpp.MainWindow._toggle_star(w, ALI, "yok", True) is False
    assert "yıldızlanamadı" in toasts[-1][1]
    _msg(ALI, "kayıtlı", "m1")
    assert xmpp.MainWindow._toggle_star(w, ALI, "m1", True, "kayıtlı") is True
    assert st._db_is_starred(ALI, "m1")
    assert toasts[-1] == ("⭐ Yıldızlı Mesajlar", "kayıtlı")


# ── Masaüstü: liste penceresi ───────────────────────────────────────────────


def test_starred_rows_label_chat_time_and_sender(db):
    _msg(ALI, "yarın 15:00", "m1", at="2026-11-24T18:30:00")
    _msg(ALI, "tamam", "m2", me=True, at="2026-11-24T18:31:00")
    st._db_set_starred(ALI, "m1")
    st._db_set_starred(ALI, "m2")
    w = object.__new__(xmpp.MainWindow)
    w.rooms = {}
    w._contacts = {ALI: "Ali"}
    rows = xmpp.MainWindow._starred_rows(w)
    assert rows == [("Ali · 24.11.2026 18:31 — Ben: tamam", (ALI, "m2")),
                    ("Ali · 24.11.2026 18:30 — ali: yarın 15:00", (ALI, "m1"))]


def test_open_starred_switches_chat_then_jumps(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.active = ROOM
    loaded, scrolled, toasts = [], [], []
    w._load_chat = loaded.append
    w.root = types.SimpleNamespace(after_idle=lambda fn: fn())
    w._bubble_widgets = []
    found = {"m1": "ROW"}
    monkeypatch.setattr(xmpp._identity, "find_row_by_mid",
                        lambda widgets, mid: found.get(mid))
    w._scroll_to_row = scrolled.append
    w._flash_row = lambda row: None
    w._show_toast = lambda *a: toasts.append(a)
    xmpp.MainWindow._open_starred(w, ALI, "m1")
    assert loaded == [ALI] and scrolled == ["ROW"]
    xmpp.MainWindow._open_starred(w, ALI, "eski")
    assert toasts and "bulunamadı" in toasts[-1][1]


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("ekran yok")
    r.withdraw()
    yield r
    r.destroy()


def _walk(w):
    yield w
    for child in w.winfo_children():
        yield from _walk(child)


def test_starred_window_unstar_and_open(root):
    opened, unstarred = [], []
    rows = [("Ali · bugün — ali: bir", ("a@x", "m1")),
            ("Oda · dün — ben: iki", ("o@c", "m2"))]
    dlg = ui_starred.show_starred(root, rows, on_open=opened.append,
                                  on_unstar=unstarred.append)
    lb = next(x for x in _walk(dlg) if x.winfo_class() == "Listbox")
    assert lb.get(0, "end") == ("Ali · bugün — ali: bir", "Oda · dün — ben: iki")
    btn = {str(x.cget("text")): x for x in _walk(dlg)
           if x.winfo_class() == "TButton"}
    btn["☆ Yıldızı Kaldır"].invoke()                 # seçili: ilk satır
    assert unstarred == [("a@x", "m1")]
    assert lb.get(0, "end") == ("Oda · dün — ben: iki",)
    btn["Aç"].invoke()
    assert opened == [("o@c", "m2")] and not dlg.winfo_exists()


def test_starred_window_empty_state(root):
    dlg = ui_starred.show_starred(root, [], on_open=None, on_unstar=None)
    texts = [str(x.cget("text")) for x in _walk(dlg)
             if x.winfo_class() == "Label"]
    assert "Henüz yıldızlı mesaj yok" in texts
    dlg.destroy()


def test_header_menu_reaches_starred_dialog():
    keys = [it[2] for it in xmpp._chat_header_menu_spec(
        is_room=False, compact=False)[5][2] if it[0] == "item"]
    assert "starred" in keys


# ── Web ─────────────────────────────────────────────────────────────────────


def test_web_star_command_saves_and_broadcasts(session):  # noqa: F811
    _msg(ALI, "web yıldızı", "w1")
    r = session.command("star", {"jid": ALI, "mid": "w1", "on": True})
    assert r == {"ok": True, "on": True}
    assert st._db_is_starred(ALI, "w1")
    ev = session.sink.get_nowait()
    assert ev == {"ev": "star", "data": {"jid": ALI, "mid": "w1", "on": True}}
    assert session.snapshot()["starred"] == [[ALI, "w1"]]
    items = session.command("starred", {})["items"]
    assert [(i["jid"], i["mid"], i["body"]) for i in items] == [
        (ALI, "w1", "web yıldızı")]
    session.command("star", {"jid": ALI, "mid": "w1", "on": False})
    assert session.command("starred", {})["items"] == []


@pytest.mark.parametrize("args", [{"jid": ALI}, {"jid": "", "mid": "w1"},
                                  {"jid": ALI, "mid": "yok"}])
def test_web_star_rejects_bad_or_unknown(session, args):  # noqa: F811
    assert session.command("star", args)["ok"] is False


def test_web_star_ui_wiring():
    from webapp import server as srv
    js = (srv.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for el in ('id="btn-starred"', 'id="dlg-starred"', 'id="starred-list"',
               'id="starred-close"'):
        assert el in html
    assert 'data-act="star"' in js and 'wsSend("star"' in js
    assert "star(data)" in js                       # sekmeler arası eşitleme
