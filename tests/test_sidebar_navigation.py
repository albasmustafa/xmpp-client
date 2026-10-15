"""Günlük sohbet kullanımı: Unicode arama, filtreler ve hızlı geçiş."""
import types

import pytest

import xmpp
from ui import sidebar


@pytest.mark.parametrize("query", ["ayse", "AYŞE", "AySe", "Ays\u0327e"])
def test_contact_search_handles_turkish_and_unicode_equivalents(query):
    contacts = {"user1@example.com": "Ayşe Yılmaz", "ali@example.com": "Ali Veli"}

    assert sidebar.ordered_contact_jids(contacts, {}, [], query) == ["user1@example.com"]


@pytest.mark.parametrize("query,expected", [
    ("yilmaz example", ["ayse@example.com"]),
    ("isik example.net", ["light@example.net"]),
    ("GÜNGÖR IŞIK", ["light@example.net"]),
    ("ali yilmaz", []),
])
def test_contact_search_matches_all_words_across_name_and_jid(query, expected):
    contacts = {
        "ayse@example.com": "Ayşe Yılmaz",
        "light@example.net": "IŞIK Güngör",
        "ali@example.com": "Ali Veli",
    }

    assert sidebar.ordered_contact_jids(contacts, {}, [], query) == expected


@pytest.mark.parametrize("view,expected", [
    ("all", ["c@x", "b@x", "a@x"]),
    ("unread", ["b@x"]),
    ("pinned", ["c@x"]),
])
def test_contact_filters_use_unread_counts_and_pins(view, expected):
    contacts = {"a@x": "Ada", "b@x": "Bora", "c@x": "Cem"}

    assert sidebar.ordered_contact_jids(
        contacts, {"b@x": "available"}, ["c@x"],
        unread_counts={"b@x": 3}, view=view) == expected


def test_query_and_unread_filter_are_applied_together():
    contacts = {"ayse@x": "Ayşe", "ali@x": "Ali", "other@x": "Ayşe Yılmaz"}

    assert sidebar.ordered_contact_jids(
        contacts, {}, [], "ayse", unread_counts={"ayse@x": 2, "ali@x": 1},
        view="unread") == ["ayse@x"]


def test_chat_presence_is_sorted_as_online():
    assert sidebar.ordered_contact_jids(
        {"a@x": "Offline", "b@x": "Ready to chat"}, {"b@x": "chat"}, []) == ["b@x", "a@x"]


def test_room_search_handles_turkish_and_multiple_words():
    rooms = ["geliştirme@conference.example", "genel@conference.example"]

    assert sidebar.filtered_rooms(rooms, "GELISTIRME conference") == [
        "geliştirme@conference.example"]


@pytest.mark.parametrize("view,expected", [
    ("all", ["dev@conf", "genel@conf"]),
    ("unread", ["genel@conf"]),
    ("pinned", ["dev@conf"]),
])
def test_room_filters_use_unread_counts_and_pins(view, expected):
    assert sidebar.filtered_rooms(
        ["dev@conf", "genel@conf"], pinned=["dev@conf"],
        unread_counts={"genel@conf": 2}, view=view) == expected


def test_room_labels_include_unread_badges_and_pin_icons():
    class List:
        def __init__(self):
            self.rows = []

        def delete(self, *args):
            self.rows.clear()

        def insert(self, index, label):
            self.rows.append(label)

    widget = List()
    sidebar.render_rooms(widget, ["dev@conf", "genel@conf"],
                         pinned=["dev@conf"], unread_counts={"genel@conf": 2})

    assert widget.rows == ["  💬  📌 dev", "  💬  genel (2)"]


def test_quick_switch_prioritizes_pins_then_unread_and_formats_badges():
    targets = sidebar.quick_switch_targets(
        {"a@x": "Ada", "b@x": "Bora", "c@x": "Cem"},
        ["genel@conf", "dev@conf"], ["c@x", "dev@conf"],
        {"b@x": 3, "genel@conf": 1})

    assert targets == [
        ("c@x", "📌 👤 Cem", False),
        ("dev@conf", "📌 🏠 dev", True),
        ("b@x", "👤 Bora (3)", False),
        ("genel@conf", "🏠 genel (1)", True),
        ("a@x", "👤 Ada", False),
    ]


def test_quick_switch_uses_the_same_turkish_multiword_search():
    targets = sidebar.quick_switch_targets(
        {"ayse@example.com": "Ayşe Yılmaz", "ali@example.com": "Ali"},
        ["geliştirme@conference.example"], query="YILMAZ example")

    assert targets == [("ayse@example.com", "👤 Ayşe Yılmaz", False)]


def test_quick_switch_deduplicates_rooms_that_are_also_in_the_roster():
    assert sidebar.quick_switch_targets(
        {"dev@conf": "Development"}, ["dev@conf", "dev@conf"]) == [
        ("dev@conf", "🏠 dev", True)]


def test_quick_switch_does_not_mutate_source_state():
    contacts = {"a@x": "Ada"}
    rooms = ["dev@conf"]
    pins = ["a@x"]
    unread = {"dev@conf": 2}

    sidebar.quick_switch_targets(contacts, rooms, pins, unread, query="dev")

    assert contacts == {"a@x": "Ada"}
    assert rooms == ["dev@conf"]
    assert pins == ["a@x"]
    assert unread == {"dev@conf": 2}


class _List:
    def __init__(self):
        self.rows = []
        self.selected = None

    def delete(self, *args):
        self.rows.clear()
        self.selected = None

    def insert(self, index, label):
        self.rows.append(label)

    def itemconfig(self, *args, **kwargs):
        pass

    def selection_set(self, index):
        self.selected = index

    def curselection(self):
        return () if self.selected is None else (self.selected,)

    def activate(self, index):
        pass


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _window(query="", view="all"):
    win = object.__new__(xmpp.MainWindow)
    win._contacts = {"a@x": "Ayşe", "b@x": "Bora"}
    win.presence = {"a@x": "available"}
    win._pinned_chats = ["b@x"]
    win._unread_counts = {"a@x": 2, "dev@conf": 3}
    win.rooms = ["dev@conf", "genel@conf"]
    win._sidebar_search_var = _Var(query)
    win._sidebar_filter_var = _Var(view)
    win._sidebar_search = types.SimpleNamespace(_showing_ph=False)
    win.contact_list = _List()
    win.room_list = _List()
    win.active = None
    return win


def test_presence_refresh_keeps_the_sidebar_query():
    win = _window("ayse")
    win._filter_sidebar()

    win._handle("presence", {"jid": "b@x", "pshow": "chat", "ptype": "available"})

    assert win._contact_jids == ["a@x"]
    assert win._sidebar_search_var.get() == "ayse"


def test_unread_view_filters_both_contacts_and_rooms():
    win = _window(view="unread")
    win._filter_sidebar()

    assert win._contact_jids == ["a@x"]
    assert win._room_jids == ["dev@conf"]
    assert win.room_list.rows == ["  💬  dev (3)"]


def test_pinned_view_filters_both_contacts_and_rooms():
    win = _window(view="pinned")
    win._pinned_chats.append("dev@conf")
    win._filter_sidebar()

    assert win._contact_jids == ["b@x"]
    assert win._room_jids == ["dev@conf"]


def test_unread_refresh_removes_read_chats_without_resetting_the_view():
    win = _window(view="unread")
    win._filter_sidebar()
    win._unread_counts["a@x"] = 0

    win._refresh_contacts()

    assert win._contact_jids == []
    assert win._room_jids == ["dev@conf"]
    assert win._sidebar_filter_var.get() == "unread"


def test_message_refresh_updates_room_badges():
    win = _window()
    win._filter_sidebar()
    win._unread_counts["dev@conf"] = 4

    win._refresh_contacts()

    assert win.room_list.rows == ["  💬  dev (4)", "  💬  genel"]


def test_refresh_preserves_active_chat_selection_by_jid():
    win = _window()
    win.active = "a@x"
    win._pinned_chats = []
    win._filter_sidebar()
    win.contact_list.selection_set(0)
    win._pinned_chats = ["b@x"]

    win._refresh_contacts()

    assert win.contact_list.selected is not None
    assert win._contact_jids[win.contact_list.selected] == "a@x"


def test_refresh_preserves_a_pending_user_selection_instead_of_overriding_it():
    win = _window()
    win.active = "a@x"
    win._filter_sidebar()
    win.contact_list.selected = win._contact_jids.index("b@x")

    win._refresh_contacts()

    assert win.contact_list.selected is not None
    assert win._contact_jids[win.contact_list.selected] == "b@x"


def test_joined_room_respects_the_active_unread_filter():
    win = _window(view="unread")
    win.room_members = {}
    win._load_chat = lambda room: None
    win._show_members = lambda room: None
    win._append = lambda *args, **kwargs: None
    win._save_room = lambda room: None

    win._handle("room_joined", "new@conf")

    assert "new@conf" in win.rooms
    assert win._room_jids == ["dev@conf"]
