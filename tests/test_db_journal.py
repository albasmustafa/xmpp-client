"""Mesaj DB'si WAL + synchronous=NORMAL ile açılır.

Kanıt (2026-11-28, albas HDD, ext4, sqlite 3.54): eski kipte (journal
DELETE + synchronous FULL) her commit ~56-67 ms sürüyordu; canlı mesaj,
yıldız ve tepki kaydı GUI thread'inde bu kadar donduruyordu. WAL +
NORMAL'da commit ~0,03 ms. NORMAL yalnız WAL'da güvenlidir (uygulama
çökünce veri kaybolmaz; elektrik kesilirse son işlemler geri alınabilir,
DB bozulmaz). WAL kurulamazsa SQLite varsayılanı (FULL) kalır.

Salt okunur okuyucular (tools/phone_check.py, MCP sunucusu) yazıcı açıkken
WAL'daki satırları da görmeli. Ağ ve Tk yok.
"""
import importlib.util
import logging
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import storage as st  # noqa: E402
from xmppcore.mcp_server import MCPServer  # noqa: E402

SYNC_NORMAL, SYNC_FULL = 1, 2


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "msgs.db")
    monkeypatch.setattr(xmpp, "_DB_PATH", path)
    if xmpp._db_conn is not None:      # önceki testin bağlantısı sızmasın
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield path
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def _pragma(conn, name):
    return conn.execute(f"PRAGMA {name}").fetchone()[0]


def test_new_db_opens_in_wal_with_normal_sync(db_path):
    conn = st._get_db()
    assert _pragma(conn, "journal_mode") == "wal"
    assert _pragma(conn, "synchronous") == SYNC_NORMAL


def test_old_delete_mode_db_is_converted_and_rows_survive(db_path):
    old = sqlite3.connect(db_path)
    assert _pragma(old, "journal_mode") == "delete"
    old.close()
    st._db_store_msg("ali@x.im", "ali", "eski", False, "10:00", "them", mid="m1")
    xmpp._db_conn.close()
    xmpp._db_conn = None

    conn = st._get_db()                 # yeniden açılış (uygulama yeniden başladı)
    assert _pragma(conn, "journal_mode") == "wal"
    assert [r[1] for r in st._db_load_msgs("ali@x.im")] == ["eski"]
    # WAL kalıcıdır: başka bir bağlantı da WAL görür
    other = sqlite3.connect(db_path)
    try:
        assert _pragma(other, "journal_mode") == "wal"
    finally:
        other.close()


def test_without_wal_sync_stays_full(monkeypatch):
    """WAL kurulamayan DB'de (burada bellek içi) NORMAL'a geçilmez: rollback
    journal'da NORMAL elektrik kesintisinde DB'yi bozabilir."""
    monkeypatch.setattr(xmpp, "_DB_PATH", ":memory:")
    monkeypatch.setattr(xmpp, "_db_conn", None)
    conn = st._init_db()
    try:
        assert _pragma(conn, "journal_mode") == "memory"
        assert _pragma(conn, "synchronous") == SYNC_FULL
    finally:
        conn.close()


class _BusyConn:
    """journal_mode isteğinde kilitli DB gibi davranır."""

    def __init__(self):
        self.calls = []

    def execute(self, sql):
        self.calls.append(sql)
        raise sqlite3.OperationalError("database is locked")


def test_journal_error_is_logged_not_raised(caplog):
    """Dönüşüm kilide takılırsa uygulama yine açılır (eski kiple); bir
    sonraki açılış yeniden dener."""
    conn = _BusyConn()
    with caplog.at_level(logging.WARNING, logger=st._log.name):
        st._set_journal(conn)
    assert conn.calls == ["PRAGMA journal_mode=WAL"]   # NORMAL'a geçilmedi
    assert "WAL" in caplog.text


def test_phone_check_ro_reader_sees_rows_while_app_is_open(db_path):
    spec = importlib.util.spec_from_file_location(
        "phone_check", os.path.join(os.path.dirname(__file__), "..", "tools",
                                    "phone_check.py"))
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    st._db_store_msg("ali@x.im", "ali", "bir", False, "10:00", "them")
    ro = pc.connect(db_path)
    try:
        assert pc.last_id(ro) == 1
        st._db_store_msg("ali@x.im", "ali", "iki", False, "10:01", "them")
        assert pc.last_id(ro) == 2      # yalnız WAL'da duran satır da görünür
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("DELETE FROM messages")
    finally:
        ro.close()


def test_mcp_ro_reader_sees_rows_while_app_is_open(db_path, tmp_path):
    st._db_store_msg("ali@x.im", "ali", "merhaba", False, "10:00", "them")
    srv = MCPServer(db_path, str(tmp_path / "cfg.json"))
    conn = srv._connect()
    try:
        assert conn.execute("SELECT body FROM messages").fetchall() == [("merhaba",)]
    finally:
        conn.close()
