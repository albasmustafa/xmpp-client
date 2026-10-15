"""RESOURCE HARDENING 2J.a: kalıcı mesaj mutasyonu (jid, mid) kapsamlı.

Kanıt: mid gönderici-kontrollü ve sohbetler arası benzersiz DEĞİLDİR; eski
mid-only UPDATE, başka bir sohbetin aynı-mid satırını da değiştirebiliyordu
(bellek mutasyonu JID-kapsamlı olduğu için runtime/DB ayrışması doğardı).
Artık kalıcı mutasyon jid+mid ile kapsamlıdır; şema değişikliği yoktur.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import xmpp  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "test_2ja.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def _seed_duplicate_mid():
    """A ve B sohbetlerinde AYNI mid 'X' ile kalıcı satırlar aç."""
    xmpp._db_store_msg("a@x", "Zeynep", "A gövdesi", False, "10:00", "them",
                       mid="X")
    xmpp._db_store_msg("b@x", "Ayşe", "B gövdesi", False, "10:01", "them",
                       mid="X")


def _body(jid):
    rows = xmpp._db_load_msgs(jid)
    assert len(rows) == 1
    return rows[0][1]


# ── 1) Düzeltme kapsamı ──────────────────────────────────────────────────────
def test_db_correction_scoped_to_jid(tmp_db):
    """Düzeltme A'ya uygulanır: A satırı değişir, B'nin aynı-mid satırı korunur."""
    _seed_duplicate_mid()
    xmpp._db_update_msg_body("a@x", "X", "A düzeltildi")
    assert _body("a@x") == "A düzeltildi"
    assert _body("b@x") == "B gövdesi"


# ── 2) Geri çekme kapsamı ────────────────────────────────────────────────────
def test_db_retraction_scoped_to_jid(tmp_db):
    """Geri çekme yalnız hedef sohbetin satırını değiştirir."""
    _seed_duplicate_mid()
    xmpp._db_update_msg_body("a@x", "X", "🚫 Bu mesaj silindi")
    assert _body("a@x") == "🚫 Bu mesaj silindi"
    assert _body("b@x") == "B gövdesi"


# ── 3) Yanıt üstverisi kapsamı ───────────────────────────────────────────────
def test_db_reply_update_scoped_to_jid(tmp_db):
    """Yanıt (alıntı) alanları yalnız hedef sohbetin satırına yazılır."""
    _seed_duplicate_mid()
    xmpp._db_update_msg_reply("a@x", "X", "mid-0", "Ali", "alıntı")
    ra = xmpp._db_load_msgs("a@x")[0]
    rb = xmpp._db_load_msgs("b@x")[0]
    assert (ra[9], ra[10], ra[11]) == ("mid-0", "Ali", "alıntı")
    assert (rb[9], rb[10], rb[11]) == ("", "", "")


# ── 4-5) Üretim çağırıcı yolları (gerçek mutasyon metodları) ─────────────────
def test_production_correction_scopes_db_to_chat(tmp_db):
    """Gerçek _apply_local_correction yolu: DB mutasyonu frm ile kapsamlı.

    active != frm seçilir; UI yaması yalnız aktif sohbeti dokunduğundan
    bu test yalnız bellek+DB mutasyon yolunu sürer (UI orkestrasyonu
    test_chat_identity.py kapsamındadır).
    """
    _seed_duplicate_mid()
    w = object.__new__(xmpp.MainWindow)
    w.chats = {}
    w.active = "b@x"
    xmpp.MainWindow._apply_local_correction(w, "a@x", "X", "A düzeltildi")
    assert _body("a@x") == "A düzeltildi"
    assert _body("b@x") == "B gövdesi"


def test_production_retraction_scopes_db_to_chat(tmp_db):
    """Gerçek _apply_local_retraction yolu: DB mutasyonu frm ile kapsamlı."""
    _seed_duplicate_mid()
    w = object.__new__(xmpp.MainWindow)
    w.chats = {}
    w.active = "b@x"
    xmpp.MainWindow._apply_local_retraction(w, "a@x", "X")
    assert _body("a@x") == "🚫 Bu mesaj silindi"
    assert _body("b@x") == "B gövdesi"
