"""PHASE 6A — F1 regression: /clear kalıcı (SQLite) geçmişi de silmeli.

F1 (Phase 5 Octet değerlendirmesi, bağımsız doğrulama CONFIRMED P1):
/clear lambda'sı bellek-içi temizlik yapıp _load_chat ile yeniden yükleme
tetikliyor; ancak canonical DB temizliği (_db_clear_chat) çağrılmıyor.
Sonuç: MAM arşivi ve/veya restart sonrası "silinen" geçmiş geri geliyor.

Bu test fix ÖNCESİ FAIL etmelidir: /clear _db_clear_chat'i hiç çağırmadığı
için DB satırları yerinde kalır ve reopen okuması (login history yolu)
silinen mesajları geri getirir.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from test_history_window_bounds import _win  # noqa: E402

import xmpp  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Gerçek SQLite dosyası tmp altında (2j kalıbı — string-form patch).

    _db_conn tekil bağlantı önbelleğidir: önceki testlerden kalan bağlantı
    farklı bir DB dosyasına işaret edebileceğinden reset-ZORUNLUDUR.
    """
    db_path = tmp_path / "f1.db"
    monkeypatch.setattr(xmpp, "_DB_PATH", str(db_path))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def _seed_db(jid, mids):
    for i, mid in enumerate(mids):
        xmpp._db_store_msg(jid, "Ayşe", f"kalıcı-{i}", False,
                           f"10:0{i}", "them", mid=mid)


def test_f1_slash_clear_deletes_persistent_history(tmp_db):
    """F1: /clear sonrası reopen okuması (DB) boş dönmeli."""
    # 1) Kalıcı geçmiş: a@x için iki mesaj gerçek SQLite'a yazıldı
    _seed_db("a@x", ["m1", "m2"])
    assert len(xmpp._db_load_msgs("a@x")) == 2

    # 2) Açık sohbet + GERÇEK /clear sürüşü (2F-B1 kalıbı)
    w = _win([], jid="a@x")
    xmpp.MainWindow._load_chat(w, "a@x")
    assert "a@x" in w.chats
    xmpp.MainWindow._handle_bot_command(w, "/clear")

    # 3) Bellek temizliği (mevcut davranış korunmalı)
    assert "a@x" not in w.chats

    # 4) F1 çekirdek iddiası: reopen/repopülasyon okuması TEMİZ dönmeli.
    #    Fix öncesi: lambda _db_clear_chat çağırmadığı için 2 satır geri gelir.
    assert xmpp._db_load_msgs("a@x") == []


def test_f1_slash_clear_is_jid_isolated(tmp_db):
    """F1 tamamlayıcı: /clear yalnız aktif JID'in kalıcı geçmişini silmeli."""
    _seed_db("a@x", ["m1"])
    _seed_db("b@x", ["n1", "n2"])

    w = _win([], jid="a@x")
    xmpp.MainWindow._load_chat(w, "a@x")
    xmpp.MainWindow._handle_bot_command(w, "/clear")

    assert xmpp._db_load_msgs("a@x") == []
    assert len(xmpp._db_load_msgs("b@x")) == 2  # diğer JID dokunulmaz


def test_f1_slash_clear_without_chat_entry_is_safe(tmp_db):
    """/clear, chats'te girişi olmayan aktif JID'de çökmemeli (canonical
    guard: _clear_active_history False döner; lambda'nın koşullu no-op'u
    ile aynı gözlemlenebilir davranış)."""
    w = _win([], jid="ghost@x")
    xmpp.MainWindow._load_chat(w, "ghost@x")
    w.chats.pop("ghost@x")  # giriş yok senaryosu
    xmpp.MainWindow._handle_bot_command(w, "/clear")  # exception YOK
    assert "ghost@x" not in w.chats
