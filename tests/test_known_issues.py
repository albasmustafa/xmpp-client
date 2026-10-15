"""Çözülmüş bilinen hataların kalıcılık (regression) testleri.

Bu dosyadaki testler önceden bilinçli olarak kırmızıydı; ilgili düzeltmeler
yapıldıktan sonra yeşile döndüler ve artık geri gelmemelerini garanti eder.

- B1 (çözüldü, Faz 3): SQLite bağlantısı tek global ve check_same_thread'siz;
  REST/webhook thread'lerinden erişim sessizce yutuluyordu. Artık
  check_same_thread=False + _db_lock ile serileştiriliyor.
- B6 (çözüldü, Faz 4-0C): _encode_pw yalnızca ImportError yakalıyordu; bozuk
  anahtar dosyası ValueError fırlatıyordu. Artık base64 fallback'e düşüyor.
"""

import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "test_messages.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def test_b1_worker_thread_yazisi_kalici_olmali(tmp_db):
    """B1 (xmpp.py:179-191): _db_store_msg çalışan bir thread'den
    çağrıldığında (REST/webhook yolu) mesaj DB'ye yazılmalı.
    Bugün ProgrammingError yutuluyor ve mesaj kayboluyor."""
    xmpp._get_db()  # bağlantı ana thread'de sahiplenilir

    def _worker():
        xmpp._db_store_msg("t@t.t", "Ali", "işçi mesajı", False,
                           "10:00", "them")

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    rows = xmpp._db_load_msgs("t@t.t")
    assert rows, "B1: çapraz-thread _db_store_msg sessizce yutuldu"
    assert rows[0][1] == "işçi mesajı"


def test_b1_worker_thread_okumasi_veri_dondurmeli(tmp_db):
    """B1 (xmpp.py:270-283): REST API handler'ının yaptığı gibi çalışan
    thread'den _db_load_msgs çağrısı kayıtları döndürmeli. Bugün boş
    liste dönüyor (ProgrammingError yutuluyor)."""
    xmpp._db_store_msg("t@t.t", "Ali", "ana thread kaydı", False,
                       "10:00", "them")
    result = {}

    def _worker():
        result["rows"] = xmpp._db_load_msgs("t@t.t")

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    assert result["rows"], "B1: çapraz-thread _db_load_msgs boş döndü"


def test_b6_bozuk_anahtar_parola_kaydini_engellememeli(monkeypatch):
    """B6 (xmpp.py:338-346): ~/.xmpp_client.key bozuksa _encode_pw
    base64 fallback'e düşüp parolayı yazabilmeli. Bugün Fernet
    ValueError fırlatıyor ve çağıran akışı çökertiyor."""
    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: b"bozuk-anahtar")
    value = xmpp._encode_pw("parola")
    assert value, "B6: bozuk anahtarda _encode_pw istisna fırlattı"
