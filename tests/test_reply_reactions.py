"""Yanıt (XEP-0461), tepki (XEP-0444) ve mesaj kimliği yardımcıları testleri."""

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp import Message  # noqa: E402
from slixmpp.plugins.xep_0428.stanza import register_plugins as fb_register
from slixmpp.plugins.xep_0461.stanza import register_plugins as reply_register

import xmpp  # noqa: E402

fb_register()
reply_register()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "test_rr.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


class _Cell:
    def __init__(self, store):
        self.store = store

    def __getitem__(self, key):
        return self.store.get(key)

    def __setitem__(self, key, value):
        self.store[key] = value


class _FakeStanza:
    """slixmpp mesajı gibi davranan asgari sahte nesne."""

    def __init__(self, origin=None, stanza_id=None, mid="", missing=False):
        self.data = {"origin_id": {"id": origin}, "stanza_id": {"id": stanza_id},
                     "id": mid}
        self.missing = missing

    def __getitem__(self, key):
        if self.missing or key not in self.data:
            raise KeyError(key)
        if key == "origin_id":
            return _Cell(self.data["origin_id"])
        if key == "stanza_id":
            return _Cell(self.data["stanza_id"])
        return self.data[key]


# ── Kimlik çözümleme ─────────────────────────────────────────────────────
def test_stanza_msg_id_origin_oncelikli():
    stanza = _FakeStanza(origin="o-1", stanza_id="s-1", mid="m-1")
    assert xmpp._stanza_msg_id(stanza) == "o-1"


def test_stanza_msg_id_stanza_id_ikincil():
    stanza = _FakeStanza(origin=None, stanza_id="s-1", mid="m-1")
    assert xmpp._stanza_msg_id(stanza) == "s-1"


def test_stanza_msg_id_son_care_stanza_id():
    stanza = _FakeStanza(origin=None, stanza_id=None, mid="m-1")
    assert xmpp._stanza_msg_id(stanza) == "m-1"


def test_stanza_msg_id_eksik_alanlar_bos():
    assert xmpp._stanza_msg_id(_FakeStanza(missing=True)) == ""


def test_new_msg_id_uuid_bicimi():
    value = xmpp._new_msg_id()
    assert str(uuid.UUID(value)) == value


def test_add_origin_id_verilen_degeri_kullanir():
    class Msg:
        def __init__(self):
            self.data = {"origin_id": {"id": None}, "id": "server-7"}

        def __getitem__(self, key):
            return _Cell(self.data[key])

    msg = Msg()
    assert xmpp._add_origin_id(msg, "sabit-id") == "sabit-id"
    assert msg.data["origin_id"]["id"] == "sabit-id"
    # İkinci çağrı aynı kimliği döndürür (idempotent)
    assert xmpp._add_origin_id(msg, "başka") == "sabit-id"


def test_add_origin_id_otomatik_uretir():
    class Msg:
        def __init__(self):
            self.data = {"origin_id": {"id": None}, "id": ""}

        def __getitem__(self, key):
            return _Cell(self.data[key])

    msg = Msg()
    value = xmpp._add_origin_id(msg)
    assert str(uuid.UUID(value)) == value


# ── Yanıt yardımcıları ───────────────────────────────────────────────────
def test_reply_preview_kisaltir_ve_satir_birler():
    assert xmpp._reply_preview("  çok   satırlı\n metin ") == "çok satırlı metin"
    uzun = "a" * 200
    out = xmpp._reply_preview(uzun, limit=20)
    assert out.endswith("…") and len(out) == 21


def test_strip_fallback_govdeden_alintiyi_cikarir():
    msg = Message()
    msg["body"] = "cevabım"
    msg["reply"]["id"] = "orijinal-1"
    msg["reply"].add_quoted_fallback("alıntı metni", "Ali")
    assert "alıntı metni" in msg["body"]
    assert xmpp._strip_quoted_fallback(msg, msg["body"]) == "cevabım"


def test_strip_fallback_yanit_yoksa_dokunmaz():
    msg = Message()
    msg["body"] = "düz mesaj"
    assert xmpp._strip_quoted_fallback(msg, msg["body"]) == "düz mesaj"


# ── Tepki yardımcıları ───────────────────────────────────────────────────
def test_toggle_reaction_set_ekler_ve_cikarir():
    assert xmpp._toggle_reaction_set(None, "👍") == {"👍"}
    assert xmpp._toggle_reaction_set({"👍"}, "👍") == set()
    assert xmpp._toggle_reaction_set({"👍"}, "❤") == {"👍", "❤"}
    assert xmpp._toggle_reaction_set({"👍", "❤"}, "👍") == {"❤"}


def test_reaction_tooltip():
    assert xmpp._reaction_tooltip(["Ali"]) == "Ali"
    assert xmpp._reaction_tooltip(["Ali", "Ayşe"]) == "Ali, Ayşe"
    assert xmpp._reaction_tooltip(["a", "b", "c", "d", "e", "f"]).endswith("+2")
    assert xmpp._reaction_tooltip([]) == ""


# ── Veritabanı: yanıt alanları ───────────────────────────────────────────
def test_db_yanit_alanlari_kaydedilir_ve_okunur(tmp_db):
    xmpp._db_store_msg("ali@example.org", "Ben", "cevap", True, "10:00", "me",
                       mid="mid-1", reply_id="mid-0", reply_sender="Ali",
                       reply_body="orijinal metin")
    rows = xmpp._db_load_msgs("ali@example.org")
    assert len(rows) == 1
    row = rows[0]
    assert row[7] == ""            # local_path (geriye dönük konum)
    assert row[8] == "mid-1"       # mid
    assert row[9] == "mid-0"       # reply_id
    assert row[10] == "Ali"        # reply_sender
    assert row[11] == "orijinal metin"


def test_db_update_msg_reply(tmp_db):
    xmpp._db_store_msg("ali@example.org", "Ben", "selam", True, "10:00", "me",
                       mid="mid-9")
    xmpp._db_update_msg_reply("ali@example.org", "mid-9", "mid-1", "Ayşe",
                              "alıntı")
    row = xmpp._db_load_msgs("ali@example.org")[0]
    assert (row[9], row[10], row[11]) == ("mid-1", "Ayşe", "alıntı")


# ── Veritabanı: tepkiler ─────────────────────────────────────────────────
def test_db_tepki_ekle_yukle_sil(tmp_db):
    jid = "oda@conf.example.org"
    xmpp._db_save_reaction(jid, "mid-1", "👍", "Ali", True)
    xmpp._db_save_reaction(jid, "mid-1", "👍", "Ben", True)
    xmpp._db_save_reaction(jid, "mid-1", "❤", "Ayşe", True)
    loaded = xmpp._db_load_reactions(jid)
    assert set(loaded["mid-1"]["👍"]) == {"Ali", "Ben"}
    assert loaded["mid-1"]["❤"] == ["Ayşe"]

    xmpp._db_save_reaction(jid, "mid-1", "❤", "Ayşe", False)
    assert "❤" not in xmpp._db_load_reactions(jid)["mid-1"]

    xmpp._db_clear_my_reactions(jid, "mid-1")
    assert xmpp._db_load_reactions(jid)["mid-1"]["👍"] == ["Ali"]


def test_db_clear_reactions_mid_ve_temizlik(tmp_db):
    jid = "ali@example.org"
    xmpp._db_save_reaction(jid, "mid-1", "👍", "Ali", True)
    xmpp._db_save_reaction(jid, "mid-2", "❤", "Ali", True)
    xmpp._db_clear_reactions_mid(jid, "mid-1")
    loaded = xmpp._db_load_reactions(jid)
    assert "mid-1" not in loaded and "mid-2" in loaded

    xmpp._db_clear_chat(jid)
    assert xmpp._db_load_reactions(jid) == {}


def test_db_ayni_tepki_tekrar_eklenmez(tmp_db):
    jid = "ali@example.org"
    xmpp._db_save_reaction(jid, "mid-1", "👍", "Ali", True)
    xmpp._db_save_reaction(jid, "mid-1", "👍", "Ali", True)
    assert xmpp._db_load_reactions(jid)["mid-1"]["👍"] == ["Ali"]


# ── MainWindow: yanıt çözümleme ve bellek sınırı ─────────────────────────
def _window(**attrs):
    win = object.__new__(xmpp.MainWindow)
    win.chats = attrs.get("chats", {})
    win._reply_map = attrs.get("reply_map", {})
    win.jid = attrs.get("jid", "ben@example.org")
    win.rooms = attrs.get("rooms", [])
    win.my_nick = attrs.get("my_nick", {})
    return win


def test_resolve_reply_yerel_gecmisten_bulur():
    win = _window(chats={"ali@example.org": [
        ("Ali", "orijinal metin", False, "10:00", "them", "", False, "m1", "")]})
    info = xmpp.MainWindow._resolve_reply(
        win, {"id": "m1", "sender": "", "body": "önizleme"}, "ali@example.org")
    assert info["sender"] == "Ali"
    assert info["body"] == "orijinal metin"


def test_resolve_reply_kendi_mesajim_ben_olur():
    win = _window(chats={"ali@example.org": [
        ("Ben", "benim mesajım", True, "10:00", "me", "", False, "m2", "")]})
    info = xmpp.MainWindow._resolve_reply(
        win, {"id": "m2", "sender": "", "body": ""}, "ali@example.org")
    assert info["sender"] == "Ben"


def test_resolve_reply_onbellekten_okur():
    # [2M] cache fallback (frm, rid) kapsamlıdır
    win = _window(reply_map={("ali@example.org", "m5"):
                             {"id": "r5", "sender": "Veli",
                              "body": "önbellek metni"}})
    info = xmpp.MainWindow._resolve_reply(
        win, {"id": "m5", "sender": "", "body": ""}, "ali@example.org")
    assert info["sender"] == "Veli"
    assert info["body"] == "önbellek metni"


def test_remember_reply_kapasitesi():
    win = _window()
    for i in range(850):
        xmpp.MainWindow._remember_reply(
            win, "ali@example.org", f"m{i}",
            {"id": f"r{i}", "sender": "A", "body": "b"})
    assert len(win._reply_map) <= 800


def _reaction_window(rooms=None):
    import types
    win = object.__new__(xmpp.MainWindow)
    win.active = (rooms or ["ali@example.org"])[0]
    win.rooms = rooms or []
    win.jid = "ben@example.org"
    win.my_nick = {}
    win._reactions = {}
    win._my_reactions = {}
    win._bubble_widgets = []
    win._reply_map = {}
    win._persist_my_reactions = lambda *a, **k: None
    win._render_reactions = lambda *a, **k: None
    win._scroll_bottom = lambda *a, **k: None
    sent = []
    win.bot = types.SimpleNamespace(
        send_reaction=lambda to, mid, emojis, mtype: sent.append(
            (to, mid, emojis, mtype)))
    return win, sent


def test_toggle_reaction_tam_kume_gonderir_ve_optimistik_gunceller():
    win, sent = _reaction_window()
    jid = "ali@example.org"              # [2M] tepki anahtarı (jid, mid)
    xmpp.MainWindow._toggle_reaction(win, "m1", "👍")
    assert sent == [("ali@example.org", "m1", ["👍"], "chat")]
    assert win._reactions[(jid, "m1")]["👍"] == ["Ben"]
    assert win._my_reactions[(jid, "m1")] == {"👍"}

    xmpp.MainWindow._toggle_reaction(win, "m1", "❤")
    assert set(sent[-1][2]) == {"👍", "❤"}
    assert set(win._reactions[(jid, "m1")].keys()) == {"👍", "❤"}

    xmpp.MainWindow._toggle_reaction(win, "m1", "👍")
    assert sent[-1][2] == ["❤"]

    xmpp.MainWindow._toggle_reaction(win, "m1", "❤")
    assert sent[-1][2] == []             # tümü geri çekildi
    assert (jid, "m1") not in win._reactions
    assert (jid, "m1") not in win._my_reactions


def test_toggle_reaction_mucda_groupchat_tipi_kullanir():
    win, sent = _reaction_window(rooms=["oda@conf.example.org"])
    xmpp.MainWindow._toggle_reaction(win, "m9", "😮")
    assert sent == [("oda@conf.example.org", "m9", ["😮"], "groupchat")]
