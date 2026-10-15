"""AI türetilmiş veri (gömme + önbellek) kalıcılık sözleşmeleri.

Kanıtlar:
- Bekleyen indeks: sys/kısa/geri çekilmiş satırlar elenir, en yeni önce.
- Gömme yazımı mesaj hâlâ varsa yapılır (yetim satır oluşmaz).
- Arama okuması mesajlarla JOIN'lidir; model değişince yeniden bekler.
- Düzeltme/geri çekme gömmeyi düşürür; geçmiş silme türetilmiş veriyi de
  siler (sohbet bazında ve tümü).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from xmppcore import ai  # noqa: E402
from xmppcore import storage  # noqa: E402

SKIP = (ai.RETRACTED_BODY, ai.VOICE_PLACEHOLDER)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "ai_test.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def _ids(rows):
    return [r[0] for r in rows]


def _seed():
    xmpp._db_store_msg("a@b", "Ali", "yarın buluşalım mı", False, "10:00",
                       "them", mid="m1")
    xmpp._db_store_msg("a@b", "", "Ali katıldı", False, "10:01", "sys")
    xmpp._db_store_msg("a@b", "Ben", "x", True, "10:02", "me", mid="m2")
    xmpp._db_store_msg("a@b", "Ben", ai.RETRACTED_BODY, True, "10:03", "me",
                       mid="m3")
    xmpp._db_store_msg("c@d", "Can", "fatura 120 TL", False, "10:04", "them",
                       mid="m4")


def test_pending_filters_and_orders_newest_first(tmp_db):
    _seed()
    rows = storage._db_ai_pending("emb", 10, SKIP)
    assert [r[3] for r in rows] == ["fatura 120 TL", "yarın buluşalım mı"]
    assert storage._db_ai_pending_count("emb", SKIP) == 2


def test_store_and_read_chunk_joined(tmp_db):
    _seed()
    rows = storage._db_ai_pending("emb", 10, SKIP)
    storage._db_ai_store_embeddings(
        [(r[0], r[1], "emb", ai.pack_vec([1.0, 0.0])) for r in rows])
    assert storage._db_ai_pending("emb", 10, SKIP) == []
    chunk = storage._db_ai_embedding_chunk("emb", 0, 500)
    assert {(c[1], c[3], c[5]) for c in chunk} == {
        ("a@b", "yarın buluşalım mı", "m1"), ("c@d", "fatura 120 TL", "m4")}
    # parça okuma msg_id üzerinden ilerler
    first = storage._db_ai_embedding_chunk("emb", 0, 1)
    rest = storage._db_ai_embedding_chunk("emb", first[-1][0], 500)
    assert len(first) == 1 and len(rest) == 1
    # model değişti → tümü yeniden bekler, eski model okunmaz
    assert len(storage._db_ai_pending("emb2", 10, SKIP)) == 2
    assert storage._db_ai_embedding_chunk("emb2", 0, 500) == []


def test_store_skips_deleted_message(tmp_db):
    _seed()
    rows = storage._db_ai_pending("emb", 10, SKIP)
    xmpp._db_clear_chat("c@d")
    storage._db_ai_store_embeddings(
        [(r[0], r[1], "emb", b"v") for r in rows])
    chunk = storage._db_ai_embedding_chunk("emb", 0, 500)
    assert [c[1] for c in chunk] == ["a@b"]
    db = xmpp._get_db()
    assert db.execute("SELECT COUNT(*) FROM ai_embeddings").fetchone()[0] == 1


def test_edit_and_retract_drop_embedding(tmp_db):
    _seed()
    rows = storage._db_ai_pending("emb", 10, SKIP)
    storage._db_ai_store_embeddings([(r[0], r[1], "emb", b"v") for r in rows])
    xmpp._db_update_msg_body("a@b", "m1", "yarın değil, cuma")
    pending = storage._db_ai_pending("emb", 10, SKIP)
    assert [r[3] for r in pending] == ["yarın değil, cuma"]
    xmpp._db_update_msg_body("c@d", "m4", ai.RETRACTED_BODY)
    assert [c[1] for c in storage._db_ai_embedding_chunk("emb", 0, 500)] == []
    assert [r[3] for r in storage._db_ai_pending("emb", 10, SKIP)] == [
        "yarın değil, cuma"]


def test_clear_chat_and_all_remove_derived_data(tmp_db):
    _seed()
    rows = storage._db_ai_pending("emb", 10, SKIP)
    storage._db_ai_store_embeddings([(r[0], r[1], "emb", b"v") for r in rows])
    storage._db_ai_cache_set("stt:k1", "a@b", "metin a")
    storage._db_ai_cache_set("stt:k2", "c@d", "metin c")
    xmpp._db_clear_chat("a@b")
    assert storage._db_ai_cache_get("stt:k1") is None
    assert storage._db_ai_cache_get("stt:k2") == "metin c"
    assert [c[1] for c in storage._db_ai_embedding_chunk("emb", 0, 500)] == [
        "c@d"]
    xmpp._db_clear_all()
    assert storage._db_ai_cache_get("stt:k2") is None
    db = xmpp._get_db()
    assert db.execute("SELECT COUNT(*) FROM ai_embeddings").fetchone()[0] == 0
