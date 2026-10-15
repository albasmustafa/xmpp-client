"""Kullanıcının yazdığı oda/kişi adreslerinde anlaşılmaz "geçersiz" hataları.

- Oda Oluştur'da yazılan ad doğrudan JID yerel kısmı yapılıyordu: "Şifreli
  Oda" (boşluk), "Ali'nin odası" (kesme) → "Geçersiz oda adresi"; "İstanbul"
  görünmez birleşik nokta taşıyan bir adrese dönüşüyordu.
- Adres başkasına ait bir odaya denk gelirse o odaya katılıp kalınıyordu.
- Kişi ekleme/davet/engelleme JID'i doğrulamıyor ve küçültmüyordu.
"""
import asyncio
import types

import pytest
from test_room_join_search import _bot
from test_room_kind import _form, _open_create, _tk_root, _walk

import xmpp
from ui.dialogs import contact as ui_contact
from xmppcore import helpers
from xmppcore import muc as muc_mod

# ── Oda adı → adres ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, slug", [
    ("Şifreli Oda", "sifreli-oda"),
    ("OMEMO Oda", "omemo-oda"),
    ("İstanbul", "istanbul"),
    ("Ali'nin odası", "ali-nin-odasi"),
    ("  çay & kahve  ", "cay-kahve"),
    ("oda_1.test", "oda_1.test"),
    ("ĞÜŞÖÇ ığüşöç", "gusoc-igusoc"),
    ("!!!", ""),
    ("Проект", ""),
])
def test_room_slug(name, slug):
    assert helpers._room_slug(name) == slug


def test_room_address_from_display_name():
    assert helpers._room_address("Şifreli Oda", "chat.yax.im") == (
        "sifreli-oda@chat.yax.im", "Şifreli Oda")


def test_room_address_accepts_full_address():
    assert helpers._room_address(" Proje@Chat.Yax.im ", "chat.yax.im") == (
        "proje@chat.yax.im", "")


@pytest.mark.parametrize("name, needle", [
    ("!!!", "harf ya da rakam"),
    ("", "Oda adı"),
    ("a b@chat.yax.im", "boşluk"),
])
def test_room_address_rejects_with_reason(name, needle):
    with pytest.raises(ValueError, match=needle):
        helpers._room_address(name, "chat.yax.im")


def test_invalid_room_error_explains_and_suggests():
    with pytest.raises(ValueError) as e:
        helpers._normalize_room_jid("Şifreli Oda", "chat.yax.im")
    msg = str(e.value)
    assert "Geçersiz oda adresi" in msg
    assert "boşluk" in msg
    assert "sifreli-oda" in msg


# ── Kişi JID'i ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, jid", [
    ("Ali@Yax.IM", "ali@yax.im"),
    ("  xmpp:ali@yax.im?message ", "ali@yax.im"),
    ("ali@yax.im/telefon", "ali@yax.im"),
])
def test_normalize_user_jid(raw, jid):
    assert helpers._normalize_user_jid(raw) == jid


@pytest.mark.parametrize("raw, needle", [
    ("", "Lütfen bir JID girin."),
    ("abc", "@ işareti olmalı"),
    ("ali veli@yax.im", "boşluk"),
    ("ali'@yax.im", "kullanılamaz"),
    ("ali@", "Geçersiz JID"),
])
def test_normalize_user_jid_rejects_with_reason(raw, needle):
    with pytest.raises(ValueError, match=needle):
        helpers._normalize_user_jid(raw)


def test_add_contact_validation_normalizes():
    assert ui_contact.validate_jid("Ali@Yax.im") == ("ali@yax.im", "")
    jid, err = ui_contact.validate_jid("ali veli@yax.im")
    assert jid is None and "boşluk" in err


# ── XMPPBot: oluşturma ───────────────────────────────────────────────────────

class _X45:
    """Oda servisi taklidi: disco#info + katılım + oda formu."""

    def __init__(self, bot, exists=False, codes=(), affiliation="owner"):
        self.bot, self.exists = bot, exists
        self.codes, self.affiliation = set(codes), affiliation
        self.joined, self.left, self.submitted = [], [], []

    async def get_info(self, jid=None, **kw):
        if not self.exists:
            raise RuntimeError("item-not-found")
        return object()

    async def join_muc_wait(self, room, nick, **kw):
        self.joined.append(room)
        self.bot.events.fire(f"muc::{room}::self-presence", {
            "muc": {"status_codes": self.codes,
                    "affiliation": self.affiliation},
            "type": "available"})

    def leave_muc(self, room, nick):
        self.left.append(room)

    async def get_room_config(self, room):
        f = _form()
        f.add_field(var="muc#roomconfig_roomname", ftype="text-single",
                    value="")
        return f

    async def set_room_config(self, room, form):
        self.submitted.append(form)


def _create(monkeypatch, name="", **kw):
    bot = _bot()
    x45 = _X45(bot, **kw)
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, n: x45)
    asyncio.run(xmpp.XMPPBot._join(
        bot, "sifreli-oda@chat.yax.im", "ben", "encrypted", name))
    return bot, x45


def test_create_sets_display_name(monkeypatch):
    bot, x45 = _create(monkeypatch, name="Şifreli Oda", codes={110, 201})
    vals = x45.submitted[0].get_values()
    assert vals["muc#roomconfig_roomname"] == "Şifreli Oda"
    assert bot.gui_q.items[-1][0] == "room_created"


def test_room_name_field_missing_is_not_an_error():
    missing = muc_mod._apply_room_preset(_form(), "encrypted", "Şifreli Oda")
    assert missing == []


def test_create_never_joins_existing_room(monkeypatch):
    """Adres doluysa yabancı odaya hiç girilmez (takma ad/presence sızmaz)."""
    bot, x45 = _create(monkeypatch, exists=True)
    assert x45.joined == []
    assert bot.gui_q.items == [("room_taken", {
        "room": "sifreli-oda@chat.yax.im", "kind": "encrypted"})]


def test_create_leaves_room_owned_by_someone_else(monkeypatch):
    """disco yanıt vermediyse (yarış/sunucu) katılım sonrası sahiplik denetlenir."""
    bot, x45 = _create(monkeypatch, codes={110}, affiliation="none")
    assert x45.left == ["sifreli-oda@chat.yax.im"]
    kinds = [k for k, _d in bot.gui_q.items]
    assert "room_taken" in kinds and "room_left" in kinds
    assert x45.submitted == []


def test_create_existing_own_room_stays(monkeypatch):
    bot, x45 = _create(monkeypatch, codes={110}, affiliation="owner")
    assert x45.left == [] and x45.submitted == []
    assert bot.gui_q.items[-1][0] == "room_exists"


def test_join_invalid_room_message_has_single_prefix(monkeypatch):
    bot = _bot()
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, n: None)
    asyncio.run(xmpp.XMPPBot._join(bot, "geçersiz oda", "ben"))
    kind, text = bot.gui_q.items[0]
    assert kind == "error" and text.count("Geçersiz oda adresi") == 1


# ── MainWindow ───────────────────────────────────────────────────────────────

def _win(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    w.jid = "ben@yax.im"
    w.my_nick = {}
    w.errors = []
    monkeypatch.setattr(xmpp.messagebox, "showerror",
                        lambda title, msg, **kw: w.errors.append(msg))
    monkeypatch.setattr(xmpp.messagebox, "showwarning",
                        lambda title, msg, **kw: w.errors.append(msg))
    return w


def test_create_request_passes_display_name(monkeypatch):
    w = _win(monkeypatch)
    calls = []
    w.bot = types.SimpleNamespace(muc_service="chat.yax.im",
                                  create_room=lambda *a: calls.append(a))
    xmpp.MainWindow._create_room_requested(
        w, "sifreli-oda@chat.yax.im", "ben", "encrypted", "Şifreli Oda")
    assert calls == [("sifreli-oda@chat.yax.im", "ben", "encrypted",
                      "Şifreli Oda")]


def test_room_taken_warns_to_pick_another_name(monkeypatch):
    w = _win(monkeypatch)
    xmpp.MainWindow._handle(w, "room_taken", {
        "room": "sifreli-oda@chat.yax.im", "kind": "encrypted"})
    assert w.errors and "başka bir ad" in w.errors[0]


@pytest.mark.parametrize("raw, expected", [
    ("Ali@B.C", [("oda@conf", "ali@b.c", "gel")]),
    ("ali veli@b.c", []),
])
def test_invite_dialog_validates_jid(monkeypatch, raw, expected):
    from ui.dialogs import rooms as ui_rooms
    monkeypatch.setattr(ui_rooms, "ask_invite", lambda parent, room: (raw, "gel"))
    w = _win(monkeypatch)
    calls = []
    w.bot = types.SimpleNamespace(invite_to_room=lambda *a: calls.append(a))
    xmpp.MainWindow._invite_to_room_dialog(w, "oda@conf")
    assert calls == expected
    assert bool(w.errors) == (not expected)


def test_jid_input_helper_used_by_block_and_admin_invite():
    import inspect
    for meth in ("_blocking_dialog", "_room_admin_dialog"):
        src = inspect.getsource(getattr(xmpp.MainWindow, meth))
        assert "self._jid_or_warn(" in src, meth


# ── Görünüm: Oda Oluştur ─────────────────────────────────────────────────────

def _labels(dlg):
    return [str(w.cget("text")) for w in _walk(dlg) if w.winfo_class() == "Label"]


def test_create_dialog_previews_address_and_sends_name(monkeypatch, tk_root):
    dlg, radios, button, created = _open_create(monkeypatch, tk_root, True)
    entry = next(w for w in _walk(dlg) if isinstance(w, xmpp.PlaceholderEntry))
    entry.delete(0, "end")
    entry.insert(0, "Şifreli Oda")
    dlg.update_idletasks()
    assert any("sifreli-oda@conf.example.com" in t for t in _labels(dlg))
    radios["encrypted"].invoke()
    button.invoke()
    assert created == [("sifreli-oda@conf.example.com", "ben", "encrypted",
                        "Şifreli Oda")]


def test_create_dialog_stays_open_on_unusable_name(monkeypatch, tk_root):
    dlg, radios, button, created = _open_create(monkeypatch, tk_root, True)
    entry = next(w for w in _walk(dlg) if isinstance(w, xmpp.PlaceholderEntry))
    entry.delete(0, "end")
    entry.insert(0, "!!!")
    button.invoke()
    assert created == []
    assert dlg.winfo_exists()
    assert any("harf ya da rakam" in t for t in _labels(dlg))


@pytest.fixture()
def tk_root():
    yield from _tk_root()
