"""ui/sidebar.py render/sıralama sözleşmeleri (Faz 4B-1)."""

import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from ui import sidebar as ui_sidebar  # noqa: E402


class _List:
    def __init__(self):
        self.rows = []
        self.colors = []
        self.selected = None

    def delete(self, *a):
        self.rows.clear()
        self.selected = None

    def insert(self, _idx, text):
        self.rows.append(text)

    def itemconfig(self, *a, **k):
        self.colors.append(k.get("fg"))

    def curselection(self):
        return () if self.selected is None else (self.selected,)

    def selection_set(self, index):
        self.selected = index

    def activate(self, index):
        pass


def test_ordered_contact_jids_pinned_online_offline():
    contacts = {"b@x": "B", "a@x": "A", "c@x": "C", "d@x": "D"}
    presence = {"b@x": "unavailable", "c@x": "available", "d@x": "away"}
    out = ui_sidebar.ordered_contact_jids(contacts, presence, ["b@x"])
    assert out == ["b@x", "c@x", "d@x", "a@x"]


def test_ordered_contact_jids_query_filters_jid_and_name():
    contacts = {"ali@x": "Ali Veli", "ayse@x": "Ayşe"}
    assert ui_sidebar.ordered_contact_jids(contacts, {}, [], "ali@") == ["ali@x"]
    assert ui_sidebar.ordered_contact_jids(contacts, {}, [], "veli") == ["ali@x"]
    assert ui_sidebar.ordered_contact_jids(contacts, {}, [], "yok") == []


def test_render_contacts_text_pin_unread_color():
    lst = _List()
    ui_sidebar.render_contacts(
        lst, {"a@x": "Ali", "b@x": ""},
        {"a@x": "available", "b@x": "unavailable"},
        ["a@x"], {"a@x": 3}, ["a@x", "b@x"])
    assert lst.rows[0] == "  ● 📌 Ali (3)"
    assert lst.rows[1] == "  ● b@x"
    assert lst.colors[0] == xmpp.PRESENCE_COLOR["available"]
    assert lst.colors[1] == xmpp.PRESENCE_COLOR["unavailable"]


def test_filtered_rooms_and_render_rooms():
    assert ui_sidebar.filtered_rooms(["a@conf", "b@conf"], "a") == ["a@conf"]
    assert ui_sidebar.filtered_rooms(["a@conf"], "") == ["a@conf"]
    lst = _List()
    ui_sidebar.render_rooms(lst, ["oda@conf"])
    assert lst.rows == ["  💬  oda"]


def test_refresh_contacts_delegates_and_preserves_jids():
    win = object.__new__(xmpp.MainWindow)
    win.contact_list = _List()
    win._contacts = {"a@x": "Ali"}
    win.presence = {"a@x": "available"}
    win._pinned_chats = []
    win._unread_counts = {"a@x": 1}

    xmpp.MainWindow._refresh_contacts(win)

    assert win._contact_jids == ["a@x"]
    assert win.contact_list.rows == ["  ● Ali (1)"]


def test_filter_sidebar_matches_old_behavior():
    win = object.__new__(xmpp.MainWindow)
    win._contacts = {"ali@x": "Ali", "ayse@x": "Ayşe"}
    win.presence = {"ali@x": "available", "ayse@x": "dnd"}
    win._pinned_chats = []
    win._unread_counts = {}
    win.rooms = ["oda@conf", "sohbet@conf"]
    win._sidebar_search = None

    def _run(query):
        win.contact_list = _List()
        win.room_list = _List()
        win._sidebar_search_var = type("V", (), {"get": lambda self: query})()
        xmpp.MainWindow._filter_sidebar(win)

    # Kişi filtresi (eski davranış: odalar da aynı sorguyla süzülür)
    _run("ay")
    assert win._contact_jids == ["ayse@x"]
    assert win._room_jids == []
    assert win.contact_list.rows == ["  ● Ayşe"]
    assert win.room_list.rows == []

    # Oda filtresi
    _run("oda")
    assert win._contact_jids == []
    assert win._room_jids == ["oda@conf"]
    assert win.contact_list.rows == []
    assert win.room_list.rows == ["  💬  oda"]

    # Boş sorgu: hepsi görünür
    _run("")
    assert win._contact_jids == ["ali@x", "ayse@x"]
    assert win._room_jids == ["oda@conf", "sohbet@conf"]


def test_sidebar_formatting_in_ui_module():
    assert "  ● " in inspect.getsource(ui_sidebar.render_contacts)
    assert "  ● " not in inspect.getsource(xmpp.MainWindow._refresh_contacts)
    assert "  💬  " in inspect.getsource(ui_sidebar.render_rooms)
    assert "  💬  " not in inspect.getsource(xmpp.MainWindow._filter_sidebar)


# ── 4B-2A: avatar presentation ──────────────────────────────────────────────

def test_update_sidebar_avatar_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ui_sidebar, "update_sidebar_avatar",
        lambda canvas, jid, data, refs=None:
            calls.append((canvas, jid, data, refs)))
    win = object.__new__(xmpp.MainWindow)
    win._sidebar_avatar = "CANVAS"
    win.jid = "me@x"
    win._avatars = {"me@x": b"img"}
    win._photo_refs = ["REF"]

    xmpp.MainWindow._update_sidebar_avatar(win)

    assert calls == [("CANVAS", "me@x", b"img", ["REF"])]


def test_update_sidebar_avatar_missing_widget_noop(monkeypatch):
    calls = []
    monkeypatch.setattr(ui_sidebar, "update_sidebar_avatar",
                        lambda *a, **k: calls.append(a))
    win = object.__new__(xmpp.MainWindow)
    xmpp.MainWindow._update_sidebar_avatar(win)
    assert calls == []


class _Canvas:
    def __init__(self):
        self.ovals = []
        self.texts = []
        self.deleted = 0

    def delete(self, *a):
        self.deleted += 1

    def create_oval(self, *a, **k):
        self.ovals.append(k)

    def create_text(self, *a, **k):
        self.texts.append(k)


def test_update_sidebar_avatar_fallback_letter(monkeypatch):
    monkeypatch.setattr(xmpp, "HAS_PIL", False)
    c = _Canvas()
    ui_sidebar.update_sidebar_avatar(c, "ali@x", b"data", [])
    assert c.deleted == 1
    assert c.texts and c.texts[0]["text"] == "A"
    assert c.ovals and c.ovals[-1]["fill"] == xmpp.ONLINE


def test_update_sidebar_avatar_none_data_fallback(monkeypatch):
    c = _Canvas()
    ui_sidebar.update_sidebar_avatar(c, "", None, [])
    assert c.deleted == 1
    assert c.texts[0]["text"] == "?"


# ── 4B-2B: contact context menu ─────────────────────────────────────────────

def test_contact_context_menu_delegates_and_routes(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_sidebar, "show_contact_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win._contact_jids = ["a@x", "b@x"]
    win._pinned_chats = ["a@x"]

    class _L:
        sel = None

        def nearest(self, y):
            return 1

        def selection_set(self, i):
            self.sel = i

    win.contact_list = _L()
    calls = []
    win._load_chat = lambda j: calls.append(("chat", j))
    win._toggle_pin_chat = lambda j: calls.append(("pin", j))
    win._common_groups_dialog = lambda j: calls.append(("groups", j))
    win._remove_contact = lambda j: calls.append(("remove", j))
    ev = types.SimpleNamespace(y=5, x_root=10, y_root=20)

    xmpp.MainWindow._contact_context_menu(win, ev)

    (root, jid, pinned, cb_chat, cb_pin, cb_groups, cb_rem,
     xr, yr) = captured[0]
    assert (root, jid, pinned, xr, yr) == ("ROOT", "b@x", False, 10, 20)
    cb_chat()
    cb_pin()
    cb_groups()
    cb_rem()
    assert calls == [("chat", "b@x"), ("pin", "b@x"),
                     ("groups", "b@x"), ("remove", "b@x")]
    assert win.contact_list.sel == 1


def test_contact_context_menu_out_of_range_noop(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_sidebar, "show_contact_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win._contact_jids = []

    class _L:
        def nearest(self, y):
            return 0

        def selection_set(self, i):
            raise AssertionError("seçim yapılmamalı")

    win.contact_list = _L()
    ev = types.SimpleNamespace(y=1, x_root=0, y_root=0)
    xmpp.MainWindow._contact_context_menu(win, ev)
    assert captured == []


def test_sidebar_modulu_domain_cagrisi_yapmaz():
    src = inspect.getsource(ui_sidebar)
    for token in ("self.bot", "_db_", "send_presence_subscription",
                  "run_coroutine_threadsafe", "remove_contact("):
        assert token not in src, f"domain sızıntısı: {token}"


# ── 4B-2B: hover kartı sunumu ───────────────────────────────────────────────

def test_show_contact_card_delegates_and_tracks_popup(monkeypatch):
    calls = []

    class _OldPop:
        destroyed = False

        def destroy(self):
            self.destroyed = True

    class _Pop:
        def __init__(self):
            self.binds = []

        def bind(self, *a):
            self.binds.append(a)

    class _Root:
        def __init__(self):
            self.afters = []

        def after(self, ms, cb):
            self.afters.append((ms, cb))
            return "id"

    old, new_pop = _OldPop(), _Pop()
    monkeypatch.setattr(
        ui_sidebar, "show_contact_card",
        lambda parent, jid, name, pshow, av, refs, common, x, y:
            calls.append((parent, jid, name, pshow, av, refs, common, x, y))
            or new_pop)
    win = object.__new__(xmpp.MainWindow)
    win.root = _Root()
    win._contact_card_pop = old
    win._contacts = {"a@x": "Ali"}
    win.presence = {"a@x": "available"}
    win._avatars = {"a@x": b"img"}
    win._photo_refs = ["REF"]
    win.rooms = ["r@conf"]
    win.room_members = {"r@conf": {"ali": {}}}
    ev = types.SimpleNamespace(x_root=100, y_root=200)

    xmpp.MainWindow._show_contact_card(win, ev, "a@x")

    assert old.destroyed is True
    parent, jid, name, pshow, av, refs, common, x, y = calls[0]
    assert parent is win.root
    assert (jid, name, pshow, av, refs, common, x, y) == (
        "a@x", "Ali", "available", b"img", ["REF"], 1, 100, 200)
    assert win._contact_card_pop is new_pop
    assert new_pop.binds and new_pop.binds[0][0] == "<Leave>"
    assert win.root.afters and win.root.afters[0][0] == 3000


def test_contact_card_icerikleri_ui_modulunde():
    assert "Ortak grup" in inspect.getsource(ui_sidebar.show_contact_card)
    assert "Ortak grup" not in inspect.getsource(
        xmpp.MainWindow._show_contact_card)


# ── 4B final shell: member panel render ─────────────────────────────────────

class _MList:
    def __init__(self):
        self.rows = []
        self.colors = []

    def delete(self, *a):
        self.rows.clear()

    def insert(self, *a):
        self.rows.append(a[-1])

    def itemconfig(self, *a, **k):
        self.colors.append(k.get("fg"))


class _MLabel:
    def __init__(self):
        self.kw = {}

    def config(self, **k):
        self.kw.update(k)


def test_render_members_groups_order_and_map():
    members = {
        "ali": {"affil": "owner", "role": "moderator", "show": "dnd"},
        "veli": {"affil": "admin", "role": "participant", "show": "away"},
        "ayse": {"affil": "member", "role": "moderator", "show": "chat"},
        "can": {"affil": "none", "role": "participant", "show": ""},
    }
    lb, lbl = _MList(), _MLabel()

    idx_map = ui_sidebar.render_members(lb, lbl, members)

    assert lbl.kw["text"] == "KATILIMCILAR — 4"
    assert [r.strip() for r in lb.rows] == [
        "─ SAHİPLER ─", "● 👑 ali",
        "─ YÖNETİCİLER ─", "● 🛡 veli",
        "─ MODERATÖRLER ─", "● ⚔ ayse",
        "● can",
    ]
    assert idx_map == {1: "ali", 3: "veli", 5: "ayse", 6: "can"}
    assert lb.colors == [xmpp.FG_DIM, xmpp.RED, xmpp.FG_DIM, xmpp.AWAY,
                         xmpp.FG_DIM, xmpp.ONLINE, xmpp.ONLINE]


def test_render_members_empty_state():
    lb, lbl = _MList(), _MLabel()
    assert ui_sidebar.render_members(lb, lbl, {}) == {}
    assert lbl.kw["text"] == "KATILIMCILAR"
    assert lb.rows == []


def test_refresh_members_delegates_and_stores_map(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ui_sidebar, "render_members",
        lambda lst, lbl, mbrs: calls.append((lst, lbl, mbrs)) or {"x": "y"})
    win = object.__new__(xmpp.MainWindow)
    win.members_list = "LB"
    win._members_label = "LBL"
    win.room_members = {"r@conf": {"ali": {}}}

    xmpp.MainWindow._refresh_members(win, "r@conf")

    assert calls == [("LB", "LBL", {"ali": {}})]
    assert win._member_index_map == {"x": "y"}
