"""Oda oluştururken tür seçimi: şifreli (OMEMO) ya da normal oda.

OMEMO odada üyelerin gerçek JID'lerine ihtiyaç duyar; anonim odada gönderim
düz metne düşer. Şifreli oda bu yüzden anonim olmayan + yalnız üyelere açık
kurulur. Yapılandırma, sunucunun odayı gerçekten yeni oluşturduğunu bildiren
201 durum koduna bağlıdır (eskiden sabit 2 sn gecikmeyle körlemesine
gönderiliyordu; var olan odada sahibi değilsek hata veriyordu).
"""
import asyncio
import types

import pytest
from slixmpp.plugins.xep_0004.stanza import Form
from test_room_join_search import _bot

import xmpp
from xmppcore import muc as muc_mod

WHOIS = "muc#roomconfig_whois"
MEMBERS = "muc#roomconfig_membersonly"
PUBLIC = "muc#roomconfig_publicroom"
PERSIST = "muc#roomconfig_persistentroom"


def _form(whois_options=("moderators", "anyone"), drop=()):
    f = Form()
    f.add_field(var="FORM_TYPE", ftype="hidden",
                value="http://jabber.org/protocol/muc#roomconfig")
    for var in (MEMBERS, PUBLIC, PERSIST):
        if var not in drop:
            f.add_field(var=var, ftype="boolean", value=False)
    if WHOIS not in drop:
        w = f.add_field(var=WHOIS, ftype="list-single", value="moderators")
        for opt in whois_options:
            w.add_option(label=opt, value=opt)
    return f


# ── Hazır ayarlar (Tk'sız çekirdek) ──────────────────────────────────────────

def test_encrypted_preset_makes_room_private_and_non_anonymous():
    form = _form()
    missing = muc_mod._apply_room_preset(form, "encrypted")
    vals = form.get_values()
    assert missing == []
    assert vals[WHOIS] == "anyone"
    assert vals[MEMBERS] is True
    assert vals[PUBLIC] is False
    assert vals[PERSIST] is True
    assert muc_mod._room_kind_ok("encrypted", missing)


def test_normal_preset_makes_room_public_and_open():
    form = _form()
    missing = muc_mod._apply_room_preset(form, "normal")
    vals = form.get_values()
    assert missing == []
    assert vals[PUBLIC] is True
    assert vals[MEMBERS] is False
    assert vals[WHOIS] == "moderators"


@pytest.mark.parametrize("form", [
    _form(drop=(WHOIS,)),
    _form(whois_options=("moderators",)),   # sunucu "anyone" sunmuyor
    _form(drop=(MEMBERS,)),
])
def test_encrypted_preset_reports_missing_omemo_requirements(form):
    missing = muc_mod._apply_room_preset(form, "encrypted")
    assert missing
    assert not muc_mod._room_kind_ok("encrypted", missing)


def test_normal_room_ok_even_if_server_lacks_fields():
    missing = muc_mod._apply_room_preset(_form(drop=(PUBLIC,)), "normal")
    assert missing == [PUBLIC]
    assert muc_mod._room_kind_ok("normal", missing)


# ── XMPPBot: katıl → 201 ise yapılandır ──────────────────────────────────────

class _X45:
    def __init__(self, bot, codes=(), form=None, form_error=None,
                 affiliation="owner"):
        self.bot, self.codes = bot, set(codes)
        self.form, self.form_error = form, form_error
        self.affiliation = affiliation
        self.submitted = []

    async def get_info(self, jid=None, **kw):
        raise RuntimeError("item-not-found")   # adres boş: oluşturulabilir

    async def join_muc_wait(self, room, nick, **kw):
        if self.codes:
            self.bot.events.fire(f"muc::{room}::self-presence",
                                 {"muc": {"status_codes": self.codes,
                                          "affiliation": self.affiliation},
                                  "type": "available"})
        return None

    async def get_room_config(self, room):
        if self.form_error:
            raise self.form_error
        return self.form

    async def set_room_config(self, room, form):
        self.submitted.append((str(room), form))

    async def cancel_config(self, room):
        raise AssertionError("cancel_config yeni odayı yok eder (§10.1.3)")


def _run_create(monkeypatch, kind, **x45_kw):
    bot = _bot()
    x45 = _X45(bot, **x45_kw)
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, "Gizli@Conf.Example.com", "ben", kind))
    return bot, x45


def test_create_encrypted_room_configures_when_server_created_it(monkeypatch):
    bot, x45 = _run_create(monkeypatch, "encrypted",
                           codes={110, 201}, form=_form())
    assert [r for r, _f in x45.submitted] == ["gizli@conf.example.com"]
    assert x45.submitted[0][1].get_values()[WHOIS] == "anyone"
    assert bot.gui_q.items == [
        ("room_joined", "gizli@conf.example.com"),
        ("room_created", {"room": "gizli@conf.example.com",
                          "kind": "encrypted", "missing": []}),
    ]


def test_create_existing_room_leaves_its_config_alone(monkeypatch):
    """Kendi (owner) odamız: ayarlara dokunulmaz; başkasınınki
    test_jid_input.py'de (odadan çıkılır)."""
    bot, x45 = _run_create(monkeypatch, "encrypted", codes={110}, form=_form())
    assert x45.submitted == []
    assert bot.gui_q.items[-1] == (
        "room_exists", {"room": "gizli@conf.example.com", "kind": "encrypted"})


def test_create_room_without_form_falls_back_to_instant_room(monkeypatch):
    """Form alınamazsa oda kilitli kalmamalı: boş submit (anında oda)."""
    bot, x45 = _run_create(monkeypatch, "encrypted", codes={201},
                           form_error=RuntimeError("feature-not-implemented"))
    assert len(x45.submitted) == 1
    assert x45.submitted[0][1].get_fields() == {}
    kind, data = bot.gui_q.items[-1]
    assert kind == "room_created"
    assert not muc_mod._room_kind_ok("encrypted", data["missing"])


def test_plain_join_never_applies_a_preset(monkeypatch):
    """Düz katılım oda türü ayarı uygulamaz; sunucu odayı yeni açtıysa yalnız
    kilidini açar (anında oda, test_small_fixes.py)."""
    bot = _bot()
    x45 = _X45(bot, codes={201}, form=_form())
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, "oda@conf.example.com", "ben"))
    assert [f.get_fields() for _r, f in x45.submitted] == [{}]
    assert bot.gui_q.items[0] == ("room_joined", "oda@conf.example.com")


def test_create_room_dispatches_join_with_kind(monkeypatch):
    bot = _bot()
    bot.loop = object()
    seen = []

    async def _fake_join(room, nick, kind=None, name=""):
        seen.append((room, nick, kind, name))

    bot._join = _fake_join
    monkeypatch.setattr(muc_mod.asyncio, "run_coroutine_threadsafe",
                        lambda coro, loop: asyncio.run(coro))
    xmpp.XMPPBot.create_room(bot, "oda@conf", "ben", "encrypted", "Oda")
    assert seen == [("oda@conf", "ben", "encrypted", "Oda")]


# ── MainWindow ───────────────────────────────────────────────────────────────

def _mw(monkeypatch, cfg=None):
    w = object.__new__(xmpp.MainWindow)
    w.jid = "ben@example.com"
    w.root = types.SimpleNamespace(
        after=lambda *a: pytest.fail("sabit gecikmeli yapılandırma kalmamalı"))
    w.my_nick = {}
    w.rooms = []
    w.active = None
    w._chat_enc_modes = {}
    w._encrypted_rooms = set()
    w.msgs = []
    w._append = lambda text, tag="sys", *a, **k: w.msgs.append((tag, text))
    creates = []
    w.bot = types.SimpleNamespace(
        muc_service="conference.example.com",
        create_room=lambda r, n, k, name="": creates.append((r, n, k)),
        join_room=lambda r, n: pytest.fail("create_room kullanılmalı"))
    store = dict(cfg or {})
    monkeypatch.setattr(xmpp, "_load_config", lambda: dict(store))
    monkeypatch.setattr(xmpp, "_save_config",
                        lambda c: (store.clear(), store.update(c)))
    return w, creates, store


def test_create_room_dialog_passes_kind_to_bot(monkeypatch):
    from ui.dialogs import rooms as ui_rooms
    captured = []
    monkeypatch.setattr(ui_rooms, "show_create_room",
                        lambda parent, conf, nick, on_create:
                        captured.append(on_create))
    w, creates, _ = _mw(monkeypatch)
    xmpp.MainWindow._create_room_dialog(w)
    captured[0]("Gizli@Conference.Example.com", "ahmet", "encrypted")
    assert creates == [("gizli@conference.example.com", "ahmet", "encrypted")]
    assert w.my_nick == {"gizli@conference.example.com": "ahmet"}


def test_encrypted_room_created_turns_on_omemo_and_persists(monkeypatch):
    w, _, store = _mw(monkeypatch)
    xmpp.MainWindow._handle(w, "room_created", {
        "room": "gizli@conf", "kind": "encrypted", "missing": []})
    assert w._chat_enc_modes["gizli@conf"] == "omemo"
    assert "gizli@conf" in w._encrypted_rooms
    assert store["encrypted_rooms"] == ["gizli@conf"]
    assert any("OMEMO" in t for _tag, t in w.msgs)


def test_encrypted_room_unsupported_by_server_is_not_marked(monkeypatch):
    w, _, store = _mw(monkeypatch)
    xmpp.MainWindow._handle(w, "room_created", {
        "room": "gizli@conf", "kind": "encrypted", "missing": [WHOIS]})
    assert "gizli@conf" not in w._chat_enc_modes
    assert "encrypted_rooms" not in store
    assert any("⚠" in t for _tag, t in w.msgs)


def test_normal_room_created_keeps_encryption_off(monkeypatch):
    w, _, store = _mw(monkeypatch)
    xmpp.MainWindow._handle(w, "room_created", {
        "room": "genel@conf", "kind": "normal", "missing": []})
    assert "genel@conf" not in w._chat_enc_modes
    assert "encrypted_rooms" not in store
    assert w.msgs


def test_room_exists_is_reported_without_marking(monkeypatch):
    w, _, store = _mw(monkeypatch)
    xmpp.MainWindow._handle(w, "room_exists", {
        "room": "gizli@conf", "kind": "encrypted"})
    assert "gizli@conf" not in w._chat_enc_modes
    assert "encrypted_rooms" not in store
    assert any("zaten" in t for _tag, t in w.msgs)


def test_encrypted_room_active_updates_lock_button(monkeypatch):
    w, _, _ = _mw(monkeypatch)
    w.active = "gizli@conf"
    modes = []
    w._encryption_mode = types.SimpleNamespace(set=modes.append)
    w._update_enc_btn = lambda silent=False: modes.append(("btn", silent))
    xmpp.MainWindow._handle(w, "room_created", {
        "room": "gizli@conf", "kind": "encrypted", "missing": []})
    assert modes == ["omemo", ("btn", True)]


# ── Sohbet açılınca şifreleme seçimi ─────────────────────────────────────────

@pytest.mark.parametrize("target, explicit, expected", [
    ("gizli@conf", None, "omemo"),        # şifreli oda
    ("genel@conf", None, "none"),         # normal oda: varsayılan OMEMO değil
    ("ali@example.com", None, "omemo"),   # 1:1: Ayarlar'daki varsayılan
    ("ali@example.com", "none", "none"),  # kullanıcının açık seçimi kazanır
    ("gizli@conf", "none", "none"),
])
def test_chat_encryption_default(target, explicit, expected):
    w = object.__new__(xmpp.MainWindow)
    w.rooms = ["gizli@conf", "genel@conf"]
    w._encrypted_rooms = {"gizli@conf"}
    w._default_encryption = "omemo"
    w._chat_enc_modes = {} if explicit is None else {target: explicit}
    assert xmpp.MainWindow._chat_encryption(w, target) == expected


# ── Görünüm: Oda Oluştur penceresi (gerçek Tk) ──────────────────────────────

def _tk_root():
    """Gerçek Tk kökü (ekran yoksa atla); test_jid_input.py de kullanır."""
    import os
    import sys
    import tkinter as tk
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    root = tk.Tk()
    root.withdraw()
    xmpp._apply_theme()
    yield root
    root.destroy()


@pytest.fixture()
def tk_root():
    yield from _tk_root()


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def _open_create(monkeypatch, root, has_omemo):
    from ui.dialogs import rooms as ui_rooms
    monkeypatch.setattr(xmpp, "HAS_OMEMO", has_omemo)
    dialogs, created = [], []
    root.wait_window = dialogs.append          # modal döngü bloklamasın
    ui_rooms.show_create_room(root, "conf.example.com", "ben",
                              lambda *a: created.append(a))
    dlg = dialogs[0]
    radios = {r.cget("value"): r for r in _walk(dlg)
              if r.winfo_class() == "Radiobutton"}
    entry = next(w for w in _walk(dlg) if isinstance(w, xmpp.PlaceholderEntry))
    entry._on_focus_in()
    entry.insert(0, "gizli")
    button = next(w for w in _walk(dlg) if w.winfo_class() == "TButton"
                  and "Oluştur" in str(w.cget("text")))
    return dlg, radios, button, created


def test_create_dialog_lets_user_pick_encrypted_room(monkeypatch, tk_root):
    dlg, radios, button, created = _open_create(monkeypatch, tk_root, True)
    assert set(radios) == {"encrypted", "normal"}
    assert "Şifreli" in radios["encrypted"].cget("text")
    radios["encrypted"].invoke()
    button.invoke()
    assert created == [("gizli@conf.example.com", "ben", "encrypted", "gizli")]


def test_create_dialog_defaults_to_normal_room(monkeypatch, tk_root):
    dlg, radios, button, created = _open_create(monkeypatch, tk_root, True)
    button.invoke()
    assert created == [("gizli@conf.example.com", "ben", "normal", "gizli")]


def test_create_dialog_disables_encrypted_without_omemo(monkeypatch, tk_root):
    dlg, radios, button, created = _open_create(monkeypatch, tk_root, False)
    assert str(radios["encrypted"].cget("state")) == "disabled"
    button.invoke()
    assert created[0][2] == "normal"
