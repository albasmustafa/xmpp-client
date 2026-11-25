"""Kenar çubuğunda sağ tık → 🔔 Bildirimler (sessize alma) alt menüsü.

Sessize alma önce yalnız açık sohbetin ⋮ menüsündeydi; kişi ve oda
listesindeki sağ tık menüleri aynı alt menüyü (`_notify_menu_spec`) ve aynı
anahtar → komut eşlemesini (`_notify_actions`) kullanır.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from ui import rooms as ui_rooms  # noqa: E402
from ui import sidebar as ui_sidebar  # noqa: E402


class _Menu:
    made = []

    def __init__(self, parent=None, **k):
        self.parent = parent
        self.entries = []
        _Menu.made.append(self)

    def add_command(self, **k):
        self.entries.append(("cmd", k.get("label"), k.get("command")))

    def add_separator(self):
        self.entries.append(("sep",))

    def add_cascade(self, **k):
        self.entries.append(("cascade", k.get("label"), k.get("menu")))

    def tk_popup(self, x, y):
        pass

    def labels(self):
        return [e[1] if e[0] != "sep" else "---" for e in self.entries]

    def invoke(self, label):
        for e in self.entries:
            if e[0] == "cmd" and e[1] == label:
                return e[2]()
        raise AssertionError(f"öğe yok: {label}")


def _fake_menus(monkeypatch):
    _Menu.made = []
    monkeypatch.setattr(ui_sidebar.tk, "Menu", _Menu)
    return _Menu.made


def _noop():
    pass


def _cascade(menu):
    found = [e for e in menu.entries if e[0] == "cascade"]
    assert len(found) == 1, menu.labels()
    assert found[0][1] == "🔔 Bildirimler"
    return found[0][2]


def test_contact_menu_has_notify_submenu_after_pin(monkeypatch):
    made = _fake_menus(monkeypatch)
    picked = []
    ui_sidebar.show_contact_menu(
        None, "a@x", False, _noop, _noop, _noop, _noop, 1, 2,
        notify_items=xmpp._notify_menu_spec(is_room=False),
        on_notify=picked.append)
    top = made[0]
    labels = top.labels()
    assert labels.index("🔔 Bildirimler") == labels.index("📌 Sohbeti Sabitle") + 1
    sub = _cascade(top)
    assert sub.labels() == ["🔕 1 Saat Sessize Al", "🔕 8 Saat Sessize Al",
                            "🔕 1 Gün Sessize Al", "🔕 Süresiz Sessize Al"]
    sub.invoke("🔕 8 Saat Sessize Al")
    assert picked == ["mute_8h"]


def test_contact_menu_without_notify_args_has_no_submenu(monkeypatch):
    made = _fake_menus(monkeypatch)
    ui_sidebar.show_contact_menu(None, "a@x", True, _noop, _noop, _noop,
                                 _noop, 1, 2)
    assert not [e for e in made[0].entries if e[0] == "cascade"]


def test_room_menu_notify_submenu_has_room_options(monkeypatch):
    made = _fake_menus(monkeypatch)
    picked = []
    ui_rooms.show_room_menu(
        None, "r@conf", "", False, False, _noop, _noop, _noop, _noop, _noop,
        1, 2, False, _noop,
        notify_items=xmpp._notify_menu_spec(is_room=True, muted_until=0),
        on_notify=picked.append)
    top = made[0]
    labels = top.labels()
    i = labels.index("🔔 Bildirimler")
    assert labels[i + 1] == "---"          # oda komutlarından ayrı
    sub = _cascade(top)
    assert sub.labels()[0] == "🔔 Sesi Aç (süresiz)"
    assert sub.labels()[-1] == "🔔 Her Mesajda Bildir"
    sub.invoke("🔔 Sesi Aç (süresiz)")
    sub.invoke("🔔 Her Mesajda Bildir")
    assert picked == ["unmute", "room_all"]


def test_room_menu_notify_without_pin_still_separated(monkeypatch):
    made = _fake_menus(monkeypatch)
    ui_rooms.show_room_menu(
        None, "r@conf", "", False, False, _noop, _noop, _noop, _noop, _noop,
        1, 2, notify_items=xmpp._notify_menu_spec(is_room=True),
        on_notify=lambda k: None)
    labels = made[0].labels()
    assert labels[labels.index("🔔 Bildirimler") + 1] == "---"


class _L:
    sel = None

    def nearest(self, y):
        return 0

    def selection_set(self, i):
        self.sel = i


def _ev():
    return types.SimpleNamespace(y=1, x_root=5, y_root=6)


def _cfg(monkeypatch, cfg):
    monkeypatch.setattr(xmpp, "_load_config_cached", lambda: cfg)


def test_contact_context_menu_routes_mute_choices(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_sidebar, "show_contact_menu",
                        lambda *a, **k: captured.append(k))
    _cfg(monkeypatch, {"muted_chats": {"b@x": 0}})
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win._contact_jids = ["b@x"]
    win._pinned_chats = []
    win.contact_list = _L()
    calls = []
    win._set_chat_mute = lambda j, c: calls.append(("mute", j, c))
    win._set_room_notify_all = lambda j, on: calls.append(("room", j, on))

    xmpp.MainWindow._contact_context_menu(win, _ev())

    kw = captured[0]
    keys = [it[2] for it in kw["notify_items"] if it[0] == "item"]
    # süresiz sessizde önce "Sesi Aç"; 1:1 sohbette oda seçenekleri yok
    assert keys == ["unmute", "mute_1h", "mute_8h", "mute_1d", "mute_forever"]
    for key in ("mute_1h", "mute_1d", "mute_forever", "unmute"):
        kw["on_notify"](key)
    assert calls == [("mute", "b@x", "1h"), ("mute", "b@x", "1d"),
                     ("mute", "b@x", "forever"), ("mute", "b@x", None)]


def test_room_context_menu_routes_room_choices(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_room_menu",
                        lambda *a, **k: captured.append(k))
    _cfg(monkeypatch, {"room_notify_all": ["r@conf"]})
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@x"
    win._room_jids = ["r@conf"]
    win.my_nick = {}
    win.room_members = {}
    win._room_subjects = {}
    win.room_list = _L()
    calls = []
    win._set_chat_mute = lambda j, c: calls.append(("mute", j, c))
    win._set_room_notify_all = lambda j, on: calls.append(("room", j, on))

    xmpp.MainWindow._room_context_menu(win, _ev())

    kw = captured[0]
    keys = [it[2] for it in kw["notify_items"] if it[0] == "item"]
    assert keys[-1] == "room_mention"     # odada zaten her mesaj bildiriliyor
    kw["on_notify"]("room_mention")
    kw["on_notify"]("mute_8h")
    assert calls == [("room", "r@conf", False), ("mute", "r@conf", "8h")]


def test_header_menu_and_sidebar_share_notify_actions():
    win = object.__new__(xmpp.MainWindow)
    keys = set(xmpp.MainWindow._notify_actions(win, "a@x"))
    spec = xmpp._notify_menu_spec(is_room=True, muted_until=0)
    spec += xmpp._notify_menu_spec(is_room=True, room_all=True)
    used = {it[2] for it in spec if it[0] == "item"}
    assert used <= keys
