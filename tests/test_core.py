"""xmpp.py çekirdek (ağsız) fonksiyonları için birim testleri."""

import os
import sys

import pytest
from cryptography.fernet import Fernet

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


@pytest.fixture()
def fernet_key(monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setattr(xmpp, "_get_fernet_key", lambda: key)
    return key


def test_encode_decode_pw(fernet_key):
    enc = xmpp._encode_pw("s3cret!üöç")
    assert enc.startswith("fernet:")
    assert xmpp._decode_pw(enc) == "s3cret!üöç"


def test_decode_pw_invalid_returns_empty():
    assert xmpp._decode_pw("bozuk-veri!!") == ""


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(tmp_path / "cfg.json"))
    xmpp._save_config({"a": 1, "türkçe": "ğüş"})
    assert xmpp._load_config() == {"a": 1, "türkçe": "ğüş"}


def test_load_config_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_CONFIG_PATH", str(tmp_path / "yok.json"))
    assert xmpp._load_config() == {}


def test_db_store_load(tmp_db):
    xmpp._db_store_msg("a@b.c", "Ali", "merhaba", False,
                       "2026-09-14 12:00", "them")
    xmpp._db_store_msg("a@b.c", "Ben", "selam", True,
                       "2026-09-14 12:01", "me")
    msgs = xmpp._db_load_msgs("a@b.c")
    assert [m[1] for m in msgs] == ["merhaba", "selam"]
    assert msgs[0][2] is False
    assert msgs[1][2] is True


def test_db_search(tmp_db):
    xmpp._db_store_msg("a@b.c", "Ali", "toplantı yarın", False,
                       "2026-09-14 12:00", "them")
    xmpp._db_store_msg("a@b.c", "Ali", "başka bir şey", False,
                       "2026-09-14 12:01", "them")
    rows = xmpp._db_search_msgs("toplantı")
    assert len(rows) == 1
    assert rows[0][2] == "toplantı yarın"


def test_db_clear_chat(tmp_db):
    xmpp._db_store_msg("a@b.c", "Ali", "merhaba", False,
                       "2026-09-14 12:00", "them")
    xmpp._db_store_msg("x@y.z", "Veli", "selam", False,
                       "2026-09-14 12:01", "them")
    xmpp._db_clear_chat("a@b.c")
    assert xmpp._db_load_msgs("a@b.c") == []
    assert len(xmpp._db_load_msgs("x@y.z")) == 1


def test_apply_color_theme():
    xmpp._apply_color_theme("dracula")
    assert xmpp.BG == "#282a36"
    xmpp._apply_color_theme("koyu")
    assert xmpp.BG == "#06060c"


def test_format_markdown():
    f = xmpp.MainWindow._format_markdown
    assert f("düz metin") == [("düz metin", None)]
    parts = f("**kalın** ve _italik_ ve `kod`")
    assert ("kalın", "bold") in parts
    assert ("italik", "italic") in parts
    assert ("kod", "code") in parts


def test_url_regexes():
    assert xmpp._IMG_URL_RE.findall("bak https://x.com/a.png?size=2 son") == [
        "https://x.com/a.png?size=2"]
    assert xmpp._AUDIO_URL_RE.findall("https://x.com/ses.ogg") == [
        "https://x.com/ses.ogg"]


def test_avatar_cache_path():
    assert xmpp._avatar_cache_path("a@b.c").endswith("a_at_b_c")


def test_process_audio_empty():
    assert xmpp.MainWindow._process_audio(b"") == b""


def test_db_local_path_roundtrip(tmp_db):
    xmpp._db_store_msg("a@b.c", "Ali", "dosya.pdf", False,
                       "2026-09-14 12:00", "them", local_path="/tmp/dosya.pdf")
    msgs = xmpp._db_load_msgs("a@b.c")
    assert msgs[0][1] == "dosya.pdf"
    assert msgs[0][7] == "/tmp/dosya.pdf"


def test_db_migrates_old_schema(tmp_path, monkeypatch):
    import sqlite3
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.execute("""CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, jid TEXT NOT NULL, sender TEXT,
        body TEXT, is_me INTEGER, timestamp TEXT, tag TEXT,
        oob TEXT DEFAULT '', encrypted INTEGER DEFAULT 0, mid TEXT DEFAULT '')""")
    conn.execute("INSERT INTO messages (jid, sender, body, is_me, timestamp, tag) "
                 "VALUES ('a@b.c','Ali','eski',0,'2026-01-01 10:00','them')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(xmpp, "_DB_PATH", str(old))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    msgs = xmpp._db_load_msgs("a@b.c")
    assert msgs[0][1] == "eski"
    assert msgs[0][7] == ""
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def test_init_db_idempotent_and_has_local_path(tmp_db):
    conn = xmpp._get_db()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()}
    assert "local_path" in cols
    xmpp._db_conn.close()
    xmpp._db_conn = None
    cols2 = {r[1] for r in xmpp._get_db().execute(
        "PRAGMA table_info(messages)").fetchall()}
    assert "local_path" in cols2


def test_parse_room_search_filters_and_sorts():
    payload = {"items": [
        {"address": "b@conf", "name": "Beta", "nusers": 10},
        {"address": "a@conf", "name": "alfa", "nusers": 50},
        {"name": "adressiz", "nusers": 99},
        "bozuk",
        {"address": "c@conf", "name": "Gama", "nusers": "12"},
    ]}
    items = xmpp._parse_room_search(payload)
    assert [i["address"] for i in items] == ["a@conf", "c@conf", "b@conf"]


def test_parse_room_search_tolerates_bad_payload():
    assert xmpp._parse_room_search(None) == []
    assert xmpp._parse_room_search({}) == []
    assert xmpp._parse_room_search({"items": "bozuk"}) == []


def test_room_result_line():
    line = xmpp._room_result_line(
        {"address": "a@conf", "name": "Alfa", "nusers": 5, "language": "tr"})
    assert "[tr]" in line and "Alfa" in line and "👤5" in line
    assert "a@conf" in line


def test_room_result_details():
    d = xmpp._room_result_details({
        "address": "a@conf", "nusers": 5, "language": "en",
        "is_public": False, "description": "deneme odası"})
    assert "👤 5" in d and "🌐 en" in d
    assert "özel" in d and "deneme odası" in d
    # Boş alanlarda adrese düşer
    assert xmpp._room_result_details({"address": "a@conf"}) == "a@conf"


def test_parse_geometry_valid():
    assert xmpp._parse_geometry("800x600+10+20", 1920, 1080) == "800x600+10+20"
    assert xmpp._parse_geometry("800x600", 1920, 1080) == "800x600"
    assert xmpp._parse_geometry(" 1024x768-5-5 ", 1920, 1080) == "1024x768+0+0"


def test_parse_geometry_clamps_and_rejects():
    # Ekran dışı konum görünür alana kırpılır
    assert xmpp._parse_geometry("800x600+5000+5000", 1920, 1080) == \
        "800x600+1120+480"
    # Ekrandan büyük boyut küçültülür
    assert xmpp._parse_geometry("3000x2000", 1920, 1080) == "1920x1080"
    # Bozuk / çok küçük / boş değerler reddedilir
    assert xmpp._parse_geometry("", 1920, 1080) == ""
    assert xmpp._parse_geometry(None, 1920, 1080) == ""
    assert xmpp._parse_geometry("bozuk", 1920, 1080) == ""
    assert xmpp._parse_geometry("100x100+0+0", 1920, 1080) == ""


class _FakeDialog:
    def __init__(self, exists=True, viewable=False):
        self.exists = exists
        self.viewable = viewable
        self.grabs = 0
        self.afters = []

    def winfo_exists(self):
        return self.exists

    def winfo_viewable(self):
        return self.viewable

    def grab_set(self):
        self.grabs += 1

    def after(self, ms, cb, *args):
        self.afters.append((ms, cb, args))
        return f"a{len(self.afters)}"


def test_safe_grab_set_retries_until_viewable():
    dlg = _FakeDialog()
    xmpp._safe_grab_set(dlg, retries=3, delay_ms=1)
    assert dlg.grabs == 0 and len(dlg.afters) == 1

    dlg.viewable = True
    _, cb, args = dlg.afters.pop(0)
    cb(*args)
    assert dlg.grabs == 1


def test_safe_grab_set_gives_up_and_handles_destroyed():
    dlg = _FakeDialog()
    xmpp._safe_grab_set(dlg, retries=2, delay_ms=1)
    # Görünür olmayınca zincir tükenir, hata yok
    for _ in range(3):
        if dlg.afters:
            _, cb, args = dlg.afters.pop(0)
            cb(*args)
    assert dlg.grabs == 0

    gone = _FakeDialog(exists=False)
    xmpp._safe_grab_set(gone)
    assert gone.grabs == 0 and gone.afters == []


def test_prefer_ipv4_filters_and_sorts():
    recs = [
        ("xmpp-client", "h", "2a12::1", 5222),
        ("xmpp-client", "h", "1.2.3.4", 5222),
        ("xmpp-client", "h", "2001:db8::2", 5222),
    ]
    out = xmpp._prefer_ipv4(recs, ipv6_ok=False)
    assert [r[2] for r in out] == ["1.2.3.4"]
    out2 = xmpp._prefer_ipv4(recs, ipv6_ok=True)
    assert out2[0][2] == "1.2.3.4"
    assert {r[2] for r in out2} == {"1.2.3.4", "2a12::1", "2001:db8::2"}


def test_prefer_ipv4_keeps_ipv6_when_only_record():
    recs = [("xmpp-client", "h", "2001:db8::2", 5222)]
    assert xmpp._prefer_ipv4(recs, ipv6_ok=False) == recs
