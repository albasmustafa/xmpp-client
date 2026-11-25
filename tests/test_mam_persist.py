"""Sunucu arşivinden (MAM) gelen geçmiş masaüstünde de veritabanına yazılır.

Önceden masaüstü arşiv geçmişini yalnız bellekte tutuyordu: bu mesajlar
yıldızlanamıyor, aranamıyor, AI tarafından görülemiyordu. Yazma tek işlemde
(tek commit) yapılır: satır başına commit bu makinenin HDD'sinde ~120 ms
sürüyor, 50 mesajlık sayfa web köprüsünde ~6 sn bekletiyordu.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _win  # noqa: E402
from test_webapp import session  # noqa: E402,F401  (fixture)

import xmpp  # noqa: E402
from xmppcore import format as fmt  # noqa: E402
from xmppcore import storage as st  # noqa: E402

ALI = "ali@x.im"


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


class _CommitCounter:
    """Gerçek bağlantıyı sarar; commit sayısını tutar."""

    def __init__(self, conn):
        self._conn = conn
        self.commits = 0

    def commit(self):
        self.commits += 1
        return self._conn.commit()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _count_commits(monkeypatch):
    real = st._get_db()
    counter = _CommitCounter(real)
    monkeypatch.setattr(st, "_get_db", lambda: counter)
    return counter


def _rows(*mids, spoiler=None):
    return [("ali", f"gövde {m}", False, "10:00", m, "2026-11-25T10:00:00",
             spoiler) for m in mids]


# ── Depolama ────────────────────────────────────────────────────────────────
def test_store_archived_one_commit_and_skips_known(db, monkeypatch):
    st._db_store_msg(ALI, "ali", "canlı", False, "09:00", "them", mid="m1")
    counter = _count_commits(monkeypatch)
    flags = st._db_store_archived(ALI, _rows("m1", "m2", "m2", "m3"))
    assert flags == [False, True, False, True]     # m1 vardı, m2 sayfada iki kez
    assert counter.commits == 1
    assert [r[1] for r in st._db_load_msgs(ALI)] == ["canlı", "gövde m2",
                                                     "gövde m3"]


def test_store_archived_keeps_time_and_spoiler(db):
    st._db_store_archived(ALI, _rows("s1", spoiler="film"))
    assert st._db_load_spoilers(ALI) == {"s1": "film"}
    conn = st._get_db()
    stored_at, tag = conn.execute(
        "SELECT stored_at, tag FROM messages WHERE mid='s1'").fetchone()
    assert stored_at == "2026-11-25T10:00:00" and tag == "them"


def test_store_archived_without_mid(db):
    rows = _rows("")
    assert st._db_store_archived(ALI, rows) == [True]           # web: gösterir
    assert st._db_store_archived(ALI, rows, skip_without_mid=True) == [False]


def test_mam_times_shared_helper():
    hm, stored_at = fmt._mam_times("2026-11-25T07:00:00Z")
    assert len(hm) == 5 and stored_at.startswith("2026-11-25T")
    assert fmt._mam_times("")[1] is None


# ── Masaüstü ────────────────────────────────────────────────────────────────
def _page(*mids):
    return [{"from": ALI, "body": f"arşiv {m}", "ts": "2026-11-25T07:00:00Z",
             "is_me": False, "mid": m} for m in mids]


def test_desktop_mam_page_is_persisted_and_starrable(db, monkeypatch):
    w = _win([], jid=ALI)
    counter = _count_commits(monkeypatch)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": ALI, "token": 0, "messages": _page("A1", "A2")})
    assert counter.commits == 1                   # sayfa başına tek commit
    assert [r[1] for r in st._db_load_msgs(ALI)] == ["arşiv A1", "arşiv A2"]
    assert st._db_set_starred(ALI, "A1") is True  # önceden: "yerel geçmişte yok"


def test_desktop_mam_does_not_duplicate_live_rows(db):
    st._db_store_msg(ALI, "ali", "canlı", False, "09:00", "them", mid="L1")
    w = _win([], jid=ALI)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": ALI, "token": 0, "messages": _page("L1", "N1")})
    assert [r[1] for r in st._db_load_msgs(ALI)] == ["canlı", "arşiv N1"]
    assert [e[1] for e in w.chats[ALI]] == ["arşiv L1", "arşiv N1"]   # bellek aynı


def test_desktop_mam_skips_rows_without_id(db):
    w = _win([], jid=ALI)
    page = _page("")
    for _ in range(2):                            # her açılışta yeniden yüklenir
        w.chats[ALI] = []
        xmpp.MainWindow._handle(w, "mam_results",
                                {"jid": ALI, "token": 0, "messages": page})
    assert st._db_load_msgs(ALI) == []


# ── Web köprüsü ─────────────────────────────────────────────────────────────
def test_web_mam_page_single_commit(session, monkeypatch):  # noqa: F811
    counter = _count_commits(monkeypatch)
    session._apply("mam_results", {"jid": ALI, "messages": _page("W1", "W2", "W3")})
    assert counter.commits == 1
    assert [r[1] for r in st._db_load_msgs(ALI)] == ["arşiv W1", "arşiv W2",
                                                     "arşiv W3"]
