"""ui/dialogs/contact.py sözleşmeleri (Faz 4B-2B)."""

import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from ui.dialogs import contact as ui_contact  # noqa: E402


def test_contact_groups_dialog_delegates_and_saves(monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_contact, "show_contact_groups",
        lambda parent, contacts, groups, on_save:
            captured.append((parent, contacts, groups, on_save)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win._contacts = {"a@b.c": "Ali"}
    monkeypatch.setattr(xmpp, "_load_config",
                        lambda: {"contact_groups": {"İş": ["a@b.c"]}})
    saved = {}
    monkeypatch.setattr(xmpp, "_save_config",
                        lambda cfg: saved.update(cfg))

    xmpp.MainWindow._contact_groups_dialog(win)

    parent, contacts, groups, on_save = captured[0]
    assert (parent, contacts) == ("ROOT", {"a@b.c": "Ali"})
    assert groups == {"İş": ["a@b.c"]}

    # Apply (ve WM_DELETE) yolu: kalıcı yazım owner'da, tek çağrı ile
    groups["Yeni"] = ["x@y.z"]
    on_save(groups)
    assert saved["contact_groups"] == {"İş": ["a@b.c"], "Yeni": ["x@y.z"]}


def test_contact_groups_icerikleri_ui_modulunde():
    assert "Kişi Grupları" in inspect.getsource(ui_contact.show_contact_groups)
    assert "Kişi Grupları" not in inspect.getsource(
        xmpp.MainWindow._contact_groups_dialog)


def test_contact_modulu_domain_cagrisi_yapmaz():
    src = inspect.getsource(ui_contact)
    for token in ("self.bot", "_db_", "_save_config",
                  "send_presence_subscription", "run_coroutine_threadsafe"):
        assert token not in src, f"domain sızıntısı: {token}"


# ── Search users (4B-2B) ────────────────────────────────────────────────────

def test_search_users_dialog_wires_refs_and_callbacks(monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_contact, "show_search_users",
        lambda parent, default_server, on_search, on_start_chat:
            captured.append((parent, default_server, on_search, on_start_chat))
            or ("DLG", "LIST", []))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "me@example.com"

    xmpp.MainWindow._search_users_dialog(win)

    parent, srv, on_search, on_start = captured[0]
    assert (parent, srv) == ("ROOT", "example.com")
    assert (win._search_dlg_ref, win._search_list_ref) == ("DLG", "LIST")
    assert win._search_jids_ref == []

    calls = []
    win.bot = types.SimpleNamespace(
        search_users=lambda s, q: calls.append((s, q)))
    on_search("example.com", "ali")
    assert calls == [("example.com", "ali")]


def test_start_chat_from_search_updates_contacts_and_loads():
    win = object.__new__(xmpp.MainWindow)
    win._contacts = {}
    calls = []
    win._refresh_contacts = lambda: calls.append("refresh")
    win._hide_members = lambda: calls.append("hide")
    win._load_chat = lambda j: calls.append(("load", j))

    xmpp.MainWindow._start_chat_from_search(win, "new@x")

    assert win._contacts == {"new@x": "new@x"}
    assert calls == ["refresh", "hide", ("load", "new@x")]


def test_start_chat_from_search_existing_contact_no_refresh():
    win = object.__new__(xmpp.MainWindow)
    win._contacts = {"new@x": "New"}
    calls = []
    win._refresh_contacts = lambda: calls.append("refresh")
    win._hide_members = lambda: calls.append("hide")
    win._load_chat = lambda j: calls.append(("load", j))

    xmpp.MainWindow._start_chat_from_search(win, "new@x")

    assert calls == ["hide", ("load", "new@x")]


def test_handle_search_results_renders_with_refs():
    win = object.__new__(xmpp.MainWindow)

    class _L:
        def __init__(self):
            self.rows = []

        def delete(self, *a):
            self.rows.clear()

        def insert(self, *a):
            self.rows.append(a[-1])

    win._search_list_ref = _L()
    win._search_jids_ref = []

    xmpp.MainWindow._handle(win, "search_results",
                            {"items": [{"jid": "a@x", "name": "Ali"}]})
    assert win._search_jids_ref == ["a@x"]
    assert "Ali" in win._search_list_ref.rows[0]

    # Hata/boş sonuç index hizası için None ekler (mevcut semantik)
    xmpp.MainWindow._handle(win, "search_results",
                            {"items": [], "error": "boom"})
    assert win._search_jids_ref == [None]


def test_search_users_icerikleri_ui_modulunde():
    assert "Kullanıcı Ara" in inspect.getsource(ui_contact.show_search_users)
    assert "Kullanıcı Ara" not in inspect.getsource(
        xmpp.MainWindow._search_users_dialog)


# ── Add contact (4B-2B.1) ───────────────────────────────────────────────────

def test_validate_jid_mesajlari_birebir():
    assert ui_contact.validate_jid("") == (None, "Lütfen bir JID girin.")
    assert ui_contact.validate_jid("   ") == (None, "Lütfen bir JID girin.")
    assert ui_contact.validate_jid("abc") == (
        None, "Geçersiz JID — @ işareti olmalı (ör: ali@sunucu.tld)")
    assert ui_contact.validate_jid("  a@b.c  ") == ("a@b.c", "")


def test_add_contact_dialog_delegates_and_wires(monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_contact, "show_add_contact",
        lambda parent, contacts, presence, srv, on_open, on_sub, on_search,
               on_refs: captured.append(dict(
                   parent=parent, contacts=contacts, presence=presence, srv=srv,
                   on_open=on_open, on_sub=on_sub, on_search=on_search,
                   on_refs=on_refs)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "me@example.com"
    win._contacts = {}
    win.presence = {"a@x": "chat"}
    bot_add, bot_srv = [], []
    win.bot = types.SimpleNamespace(
        add_contact=lambda j: bot_add.append(j),
        search_users=lambda s, q: bot_srv.append((s, q)))
    events = []
    win._refresh_contacts = lambda: events.append("refresh")
    win._hide_members = lambda: events.append("hide")
    win._load_chat = lambda j: events.append(("load", j))

    xmpp.MainWindow._add_contact_dialog(win)

    c = captured[0]
    assert (c["parent"], c["srv"]) == ("ROOT", "example.com")
    assert c["contacts"] is win._contacts and c["presence"] is win.presence

    # open_chat: kişi değilse ekle + refresh + hide + load (birebir sıra)
    c["on_open"]("new@x")
    assert win._contacts["new@x"] == "new@x"
    assert events == ["refresh", "hide", ("load", "new@x")]

    # subscribe: open + bot.add_contact (tek çağrı)
    c["on_sub"]("sub@x")
    assert bot_add == ["sub@x"]
    assert events[-2:] == ["hide", ("load", "sub@x")]

    # search request delegation
    c["on_search"]("example.com", "ali")
    assert bot_srv == [("example.com", "ali")]

    # search refs: _handle("search_results") kontratı; _search_dlg_ref'e dokunulmaz
    c["on_refs"]("DLG", "LIST", ["j1"])
    assert (win._search_list_ref, win._search_jids_ref) == ("LIST", ["j1"])
    assert not hasattr(win, "_search_dlg_ref")


def test_open_chat_from_add_existing_contact_no_refresh():
    win = object.__new__(xmpp.MainWindow)
    win._contacts = {"a@x": "Ali"}
    events = []
    win._refresh_contacts = lambda: events.append("refresh")
    win._hide_members = lambda: events.append("hide")
    win._load_chat = lambda j: events.append(("load", j))

    xmpp.MainWindow._open_chat_from_add(win, "a@x")
    assert events == ["hide", ("load", "a@x")]


def test_add_contact_icerikleri_ui_modulunde_ve_wrapper_ince():
    assert "JID Gir" in inspect.getsource(ui_contact.show_add_contact)
    src_old = inspect.getsource(xmpp.MainWindow._add_contact_dialog)
    assert "JID Gir" not in src_old
    assert "kullanici@sunucu.tld" not in src_old
    assert len(src_old.splitlines()) < 30
