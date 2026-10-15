"""Config ve SQLite kalıcılık sözleşmeleri (refactor regression ağı).

Bu dosyadaki her test, refactor öncesi xmpp.py'nin mevcut davranışını
sabitler. Amaç: config/storage modülleri ayrıştırılırken (Faz 1) bu
davranışların aynen korunmasını garanti etmek.

Kapsam: config okuma/yazma hataları, SQLite mesaj DB'si (oob/şifreli
sütunları, limit/sıra, mid ile güncelleme, tümünü temizle, singleton
bağlantı) ve kritik yardımcı fonksiyonlar (_to_int, _extract_oob,
_iso_to_hm, _decode_pw bozuk Fernet).
"""

import os
import sys

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


# ── Config okuma/yazma ───────────────────────────────────────────────────────

def test_load_config_corrupt_json_returns_empty(tmp_path, monkeypatch):
    """Mevcut davranış (xmpp.py:100-108): bozuk JSON çökertmez, {} döner."""
    path = tmp_path / "bozuk.json"
    path.write_text("{bu json degil", encoding="utf-8")
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(path))
    assert xmpp._load_config() == {}


def test_load_config_utf8_values_survive(tmp_path, monkeypatch):
    """Mevcut davranış: _save_config ensure_ascii=False yazar (xmpp.py:111-116)."""
    path = tmp_path / "cfg.json"
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(path))
    cfg = {"jid": "ğüş@example.com", "list": [1, 2]}
    xmpp._save_config(cfg)
    assert xmpp._load_config() == cfg
    assert "ğüş" in path.read_text(encoding="utf-8")


def test_decode_pw_corrupt_fernet_returns_empty(monkeypatch):
    """Mevcut davranış (xmpp.py:349-358): fernet: önekli bozuk veri "" döner."""
    from cryptography.fernet import Fernet

    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: Fernet.generate_key())
    assert xmpp._decode_pw("fernet:bu-gecerli-degil") == ""


def test_get_fernet_key_cryptography_yoksa_hashlib_fallback(tmp_path,
                                                            monkeypatch):
    """Düzeltme (Faz 2 review, madde 16): cryptography yokken NameError
    değil, sha256 tabanlı anahtar üretilir ve 0600 ile yazılır."""
    import sys

    from xmppcore import config as xmpp_config

    monkeypatch.setenv("XMPP_CLIENT_HOME", str(tmp_path))
    monkeypatch.setitem(sys.modules, "cryptography", None)

    key = xmpp_config._get_fernet_key()

    assert len(key) == 44  # 32 bayt → urlsafe base64
    key_path = tmp_path / ".xmpp_client.key"
    assert key_path.is_file()
    assert (key_path.stat().st_mode & 0o777) == 0o600


# ── SQLite mesaj veritabanı ──────────────────────────────────────────────────

def test_db_oob_ve_encrypted_alanlari_geri_okunur(tmp_db):
    """Mevcut davranış (xmpp.py:179-191, 270-283): oob/encrypted sütunları
    _db_load_msgs demetinde 5. ve 6. sırada döner."""
    xmpp._db_store_msg("a@b.c", "Ali", "belge", False, "2026-09-14 12:00",
                       "them", oob="https://x/y.png", encrypted=True)
    row = xmpp._db_load_msgs("a@b.c")[0]
    assert row[5] == "https://x/y.png"
    assert row[6] is True


def test_db_limit_en_yeni_kayitlari_kronolojik_dondurur(tmp_db):
    """Mevcut davranış (xmpp.py:270-283): id DESC LIMIT + reverse → son N
    mesaj eskiden yeniye sıralanır."""
    for i in range(5):
        xmpp._db_store_msg("a@b.c", "Ali", f"m{i}", False,
                           f"2026-09-14 12:0{i}", "them")
    msgs = xmpp._db_load_msgs("a@b.c", limit=3)
    assert [m[1] for m in msgs] == ["m2", "m3", "m4"]


def test_db_update_msg_body_mid_ile_gunceller(tmp_db):
    """[2J.a] Düzeltme/silme (jid, mid) kapsamlı günceller; aynı sohbetin
    diğer satırlarına dokunmaz."""
    xmpp._db_store_msg("a@b.c", "Ben", "ilk", True, "10:00", "me", mid="mid-1")
    xmpp._db_store_msg("a@b.c", "Ben", "ikinci", True, "10:01", "me",
                       mid="mid-2")
    xmpp._db_update_msg_body("a@b.c", "mid-1", "düzeltildi")
    rows = xmpp._db_load_msgs("a@b.c")
    assert [r[1] for r in rows] == ["düzeltildi", "ikinci"]
    assert [r[8] for r in rows] == ["mid-1", "mid-2"]


def test_db_clear_all_mesaj_ve_tepkileri_siler(tmp_db):
    """Mevcut davranış (xmpp.py:306-313): _db_clear_all tüm jid'leri ve
    tepkileri temizler."""
    xmpp._db_store_msg("a@b.c", "Ali", "x", False, "10:00", "them")
    xmpp._db_store_msg("d@e.f", "Veli", "y", False, "10:01", "them")
    xmpp._db_save_reaction("a@b.c", "mid-1", "👍", "Ali", True)
    xmpp._db_clear_all()
    assert xmpp._db_load_msgs("a@b.c") == []
    assert xmpp._db_load_msgs("d@e.f") == []
    assert xmpp._db_load_reactions("a@b.c") == {}


def test_get_db_ayni_baglantiyi_dondurur(tmp_db):
    """Mevcut davranış (xmpp.py:171-177): _db_conn global singleton;
    ikinci çağrı yeni bağlantı açmaz."""
    first = xmpp._get_db()
    assert xmpp._get_db() is first


# ── Kritik yardımcı fonksiyonlar ─────────────────────────────────────────────

def test_to_int_guvenli_donusum():
    """Mevcut davranış (xmpp.py:405-410): bozuk API verisi çökertmez."""
    assert xmpp._to_int("12") == 12
    assert xmpp._to_int(12) == 12
    assert xmpp._to_int(None) == 0
    assert xmpp._to_int("x", 5) == 5
    assert xmpp._to_int(object(), 7) == 7


def test_extract_oob_url_ve_yokluk():
    """Mevcut davranış (xmpp.py:2011-2017): XEP-0066 URL'sini döndürür,
    alan yoksa boş string döner."""

    class _Var:
        def __getitem__(self, key):
            if key == "oob":
                return {"url": "https://x/y.png"}
            raise KeyError(key)

    class _Bos:
        def __getitem__(self, key):
            raise KeyError(key)

    assert xmpp.XMPPBot._extract_oob(_Var()) == "https://x/y.png"
    assert xmpp.XMPPBot._extract_oob(_Bos()) == ""


def test_iso_to_hm_formatlari():
    """Mevcut davranış (xmpp.py:7484-7493): ISO damgası HH:MM'e çevrilir;
    boş/bozuk değer çökertmez."""
    f = xmpp.MainWindow._iso_to_hm
    assert f("2026-09-14T10:30:00Z") == "10:30"
    assert f("2026-09-14T10:30:00+03:00") == "10:30"
    assert f("") == ""
    assert f("bozuk") == ""
