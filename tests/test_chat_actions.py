"""FAZ 4C-5A: ui/chat/actions.py contract + MainWindow capability/callback parity."""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui.chat.actions as actions_mod  # noqa: E402
import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _FakeMenu:
    def __init__(self, parent=None, **kw):
        self.parent = parent
        self.kw = kw
        self.items = []
        self.popup = None
        self.released = 0

    def add_command(self, label=None, command=None, **k):
        self.items.append(("cmd", label, command))

    def add_separator(self):
        self.items.append(("sep", None, None))

    def add_cascade(self, label=None, menu=None, **k):
        self.items.append(("cascade", label, menu))

    def tk_popup(self, x, y):
        self.popup = (x, y)

    def grab_release(self):
        self.released += 1


class _W:
    def __init__(self, master=None, **kw):
        self.master = master
        self.kw = dict(kw)
        self.binds = {}
        self.children = []
        self.destroyed = False
        self.exists = True
        self.placed = None
        self.lifted = 0
        if master is not None and isinstance(master, _W):
            master.children.append(self)

    def pack(self, *a, **k):
        self.kw.setdefault("_pack", (a, k))

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        self.destroyed = True
        if isinstance(self.master, _W) and self in self.master.children:
            self.master.children.remove(self)

    def config(self, **k):
        self.kw.update(k)

    def winfo_exists(self):
        return self.exists

    def update_idletasks(self):
        pass

    def winfo_reqwidth(self):
        return 100

    def winfo_reqheight(self):
        return 20

    def winfo_x(self):
        return 10

    def winfo_y(self):
        return 50

    def winfo_width(self):
        return 200

    def place(self, **k):
        self.placed = k

    def lift(self):
        self.lifted += 1


class _Anchor:
    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 200

    def winfo_height(self):
        return 12


def _patch_tk(monkeypatch):
    menus = []

    class _Menu(_FakeMenu):
        def __init__(self, parent=None, **kw):
            super().__init__(parent, **kw)
            menus.append(self)

    monkeypatch.setattr(actions_mod, "tk", types.SimpleNamespace(
        Menu=_Menu, Frame=_W, Label=_W))
    return menus


def _theme():
    th = dict(xmpp._chat_theme())
    th.setdefault("SEL_BG", "sb")
    th.setdefault("SEL_FG", "sf")
    return th


CB_KEYS = ("on_copy", "on_jump", "on_edit", "on_delete", "on_reply",
           "on_forward", "on_pin", "on_react", "on_more_emoji",
           "on_reactions_details")


def _cm(monkeypatch, caps, mine=(), has_reactions=False):
    menus = _patch_tk(monkeypatch)
    cb = {k: _Capture() for k in CB_KEYS}
    actions_mod.show_context_menu(
        "ROOT", 7, 9, theme=_theme(), t=lambda k: k.upper(), caps=caps,
        mine=set(mine), has_reactions=has_reactions, callbacks=cb)
    return menus[0], cb


def _labels(menu):
    return [it[1] for it in menu.items if it[0] == "cmd"]


def _cmd(menu, label):
    for it in menu.items:
        if it[0] == "cmd" and it[1] == label:
            return it[2]
    raise AssertionError(f"komut yok: {label}")


ALL_ON = {"copy": True, "jump": True, "edit": True, "delete": True,
          "reply": True, "forward": True, "pin": True, "react": True}


# ── 1-3) context menu capabilities ──────────────────────────────────────────
def test_context_menu_incoming_caps(monkeypatch):
    caps = dict(ALL_ON, edit=False, delete=False)
    menu, _ = _cm(monkeypatch, caps)
    labels = _labels(menu)
    assert "📋 COPY" in labels and "↩ REPLY" in labels
    assert "↪ FORWARD" in labels and "📌 PIN" in labels
    assert "✏ EDIT" not in labels and "🗑 DELETE" not in labels
    assert any(it[0] == "cascade" and it[1] == "😊 REACT" for it in menu.items)
    assert menu.popup == (7, 9)


def test_context_menu_outgoing_and_order(monkeypatch):
    menu, _ = _cm(monkeypatch, dict(ALL_ON), mine=("👍",))
    kinds = [it[0] for it in menu.items]
    assert kinds == ["cmd", "cmd", "cmd", "cmd", "cmd", "cmd", "cmd",
                     "sep", "cascade"]
    assert _labels(menu)[:7] == ["📋 COPY", "↪ Alıntılanan mesaja git",
                                 "✏ EDIT", "🗑 DELETE", "↩ REPLY",
                                 "↪ FORWARD", "📌 PIN"]
    react = menu.items[-1][2]
    assert react.items[0][1] == "👍  ✓"
    assert react.items[1][1] == "❤"


def test_context_menu_retracted_empty(monkeypatch):
    caps = {k: False for k in ALL_ON}
    menu, _ = _cm(monkeypatch, caps)
    assert menu.items == []
    assert menu.popup == (7, 9)


# ── 4-8) callback exactly-once ──────────────────────────────────────────────
def test_context_menu_callbacks_exactly_once(monkeypatch):
    menu, cb = _cm(monkeypatch, dict(ALL_ON))
    _cmd(menu, "📋 COPY")()
    _cmd(menu, "↪ Alıntılanan mesaja git")()
    _cmd(menu, "✏ EDIT")()
    _cmd(menu, "🗑 DELETE")()
    _cmd(menu, "↩ REPLY")()
    _cmd(menu, "↪ FORWARD")()
    _cmd(menu, "📌 PIN")()
    for key in ("on_copy", "on_jump", "on_edit", "on_delete", "on_reply",
                "on_forward", "on_pin"):
        assert len(cb[key].calls) == 1, key


def test_context_menu_react_and_details(monkeypatch):
    menu, cb = _cm(monkeypatch, dict(ALL_ON), mine=("❤",), has_reactions=True)
    react = menu.items[-1][2]
    _cmd(react, "❤  ✓")()
    _cmd(react, "😀 Daha fazla emoji…")()
    _cmd(react, "👥 Tepkileri gör…")()
    assert cb["on_react"].calls == [(("❤",), {})]
    assert len(cb["on_more_emoji"].calls) == 1
    assert len(cb["on_reactions_details"].calls) == 1


# ── 9) quick reaction popup ─────────────────────────────────────────────────
def test_quick_reaction_popup(monkeypatch):
    menus = _patch_tk(monkeypatch)
    reacts, more = _Capture(), _Capture()
    actions_mod.show_quick_reaction_menu(
        "ROOT", _Anchor(), theme=_theme(), mine={"🔥"},
        on_react=reacts, on_more=more)
    menu = menus[0]
    labels = _labels(menu)
    assert labels[0] == "👍" and labels[6] == "🔥  ✓"
    assert len([lb for lb in labels if lb.endswith("✓")]) == 1
    _cmd(menu, "🔥  ✓")()
    _cmd(menu, "😀 Daha fazla emoji…")()
    assert reacts.calls == [(("🔥",), {})]
    assert len(more.calls) == 1
    assert menu.popup == (100, 212)
    assert menu.released == 0       # grab kalır: dışarı tıklayınca kapanır


def test_hover_ai_menu_keeps_grab(monkeypatch):
    menus = _patch_tk(monkeypatch)
    cb = {"on_" + key: _Capture() for key, _l in actions_mod.AI_MESSAGE_ITEMS}
    actions_mod.show_ai_message_menu(
        "ROOT", _Anchor(), theme=_theme(), items={"ai_translate"},
        callbacks=cb)
    menu = menus[0]
    assert _labels(menu) == ["🌐 Çevir"]
    assert menu.popup == (100, 212)
    assert menu.released == 0


# ── 10-12) hover action bar ─────────────────────────────────────────────────
def test_action_bar_construction_binds(monkeypatch):
    _patch_tk(monkeypatch)
    entered, left, wheel, units = _Capture(), _Capture(), _Capture(), _Capture()
    bar = actions_mod.create_action_bar(
        _W(), _theme(), on_enter=entered, on_leave=left, on_wheel=wheel,
        on_scroll_units=units)
    bar.binds["<Enter>"][0](None)
    bar.binds["<Leave>"][0](None)
    bar.binds["<MouseWheel>"][0](None)
    bar.binds["<Button-4>"][0](None)
    bar.binds["<Button-5>"][0](None)
    assert len(entered.calls) == 1 and len(left.calls) == 1
    assert len(wheel.calls) == 1
    assert units.calls == [((-3,), {}), ((3,), {})]


def test_populate_action_bar_order_danger_and_replace(monkeypatch):
    _patch_tk(monkeypatch)
    bar = _W()
    tips, after = _Capture(), _Capture()
    cmds = _Capture(), _Capture()
    specs = [("↩", "Yanıtla", cmds[0], False),
             ("🗑", "Sil", cmds[1], True)]
    actions_mod.populate_action_bar(bar, _theme(), specs,
                                    add_tooltip=tips, on_after=after)
    btns = bar.winfo_children()
    assert [b.kw["text"] for b in btns] == ["↩", "🗑"]
    assert btns[0].kw["fg"] == xmpp.FG and btns[1].kw["fg"] == xmpp.RED
    assert len(tips.calls) == 2 and tips.calls[0][0] == (btns[0], "Yanıtla")
    btns[0].binds["<Button-1>"][0](None)
    assert len(cmds[0].calls) == 1 and len(after.calls) == 1

    actions_mod.populate_action_bar(bar, _theme(),
                                    [("📋", "Kopyala", _Capture(), False)],
                                    add_tooltip=tips, on_after=after)
    assert btns[0].destroyed is True and btns[1].destroyed is True
    assert len(bar.winfo_children()) == 1


def test_position_action_bar_geometry_and_missing_row(monkeypatch):
    _patch_tk(monkeypatch)
    bar = _W()
    row = _W()
    row._is_me = True
    assert actions_mod.position_action_bar(row, bar) is True
    assert bar.placed == {"x": 104, "y": 32} and bar.lifted == 1
    row._is_me = False
    actions_mod.position_action_bar(row, bar)
    assert bar.placed == {"x": 54, "y": 32}

    row.exists = False
    assert actions_mod.position_action_bar(row, bar) is False


# ── 13) no domain leak ──────────────────────────────────────────────────────
def test_actions_has_no_domain_dependencies():
    src = inspect.getsource(actions_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot",
                  "run_coroutine_threadsafe", "sqlite", "_db_", "urlopen(",
                  "threading.", "gui_q", "subprocess", "_safe_after",
                  "import xmpp", "asyncio", ".after("):
        assert token not in src, token


# ── 14-16) MainWindow integration ───────────────────────────────────────────
def _mw(row):
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.bot = object()
    w.rooms = []
    w._my_reactions = {("a@b", "m1"): {"👍"}}   # [2M] (jid, mid) kapsamlı
    w._reactions = {("a@b", "m1"): {"👍": ["Ben"]}}
    w.root = types.SimpleNamespace(clipboard_clear=lambda: None,
                                   clipboard_append=_Capture())
    for name in ("_jump_to_message", "_edit_message_dialog", "_retract_message",
                 "_set_reply", "_forward_dialog", "_pin_message",
                 "_toggle_reaction", "_show_emoji_picker",
                 "_reaction_details_dialog"):
        setattr(w, name, _Capture())
    return w


def _row(is_me=False, mid="m1", body="gövde", retracted=False, reply=None):
    return types.SimpleNamespace(_body=body, _is_me=is_me, _mid=mid,
                                 _sender="Ali", _retracted=retracted,
                                 _reply_to=reply)


def _spy_context(monkeypatch, w, row):
    captured = {}

    def spy(parent, x, y, **kw):
        captured.update(kw, parent=parent, x=x, y=y, row=row)
    monkeypatch.setattr(xmpp._actions_ui, "show_context_menu", spy)
    event = types.SimpleNamespace(x_root=3, y_root=4)
    xmpp.MainWindow._message_context_menu(w, event, row)
    return captured


def test_context_menu_mw_caps_and_callbacks(monkeypatch):
    w = _mw(_row())
    row = _row(is_me=True, reply={"id": "m0", "sender": "B", "body": "eski"})
    cap = _spy_context(monkeypatch, w, row)
    assert (cap["x"], cap["y"]) == (3, 4)
    caps = cap["caps"]
    assert all(caps[k] for k in ("copy", "jump", "edit", "delete", "reply",
                                 "forward", "pin", "react"))
    assert cap["mine"] == {"👍"} and cap["has_reactions"] is True

    cb = cap["callbacks"]
    cb["on_reply"]()
    cb["on_react"]("❤")
    cb["on_edit"]()
    cb["on_delete"]()
    cb["on_forward"]()
    cb["on_pin"]()
    cb["on_jump"]()
    cb["on_more_emoji"]()
    cb["on_reactions_details"]()
    cb["on_copy"]()
    assert w._set_reply.calls == [(("m1", "gövde", "Ali"), {})]
    assert w._toggle_reaction.calls == [(("m1", "❤"), {})]
    assert w._edit_message_dialog.calls[0][0] == ("m1", "gövde", "chat")
    assert w._retract_message.calls[0][0] == ("m1", "chat")
    assert w._forward_dialog.calls == [(("gövde", "Ali"),
                                        {"encrypted": False})]
    assert w._pin_message.calls == [(("gövde", "Ali"), {})]
    assert w._jump_to_message.calls == [(("m0",), {})]
    assert w._show_emoji_picker.calls == [(("m1",), {})]
    assert w._reaction_details_dialog.calls == [(("m1",), {})]
    assert w.root.clipboard_append.calls == [(("gövde",), {})]


def test_context_menu_mw_incoming_and_retracted_caps(monkeypatch):
    w = _mw(_row())
    cap = _spy_context(monkeypatch, w, _row(is_me=False))
    assert cap["caps"]["edit"] is False and cap["caps"]["delete"] is False
    assert cap["caps"]["reply"] is True and cap["caps"]["react"] is True

    w2 = _mw(_row())
    cap2 = _spy_context(monkeypatch, w2, _row(retracted=True))
    assert not any(cap2["caps"].values())


def test_quick_reaction_popup_mw_delegation(monkeypatch):
    w = _mw(_row())
    captured = {}

    def spy(parent, anchor, **kw):
        captured.update(kw)
    monkeypatch.setattr(xmpp._actions_ui, "show_quick_reaction_menu", spy)
    xmpp.MainWindow._quick_reaction_popup(w, "ANCHOR", "m1")
    assert captured["mine"] == {"👍"}
    captured["on_react"]("🔥")
    captured["on_more"]()
    assert w._toggle_reaction.calls == [(("m1", "🔥"), {})]
    assert w._show_emoji_picker.calls == [(("m1",), {})]


# ── 17) hover timer ownership (MW'da kalır) ─────────────────────────────────
class _Root:
    def __init__(self):
        self.seq = 0
        self.pending = {}
        self.cancelled = []

    def after(self, ms, fn=None):
        self.seq += 1
        self.pending[self.seq] = (ms, fn)
        return self.seq

    def after_cancel(self, aid):
        self.cancelled.append(aid)
        self.pending.pop(aid, None)


def test_hover_timers_schedule_cancel_repeat():
    w = object.__new__(xmpp.MainWindow)
    w.root = _Root()
    w._actions_show_id = None
    w._actions_hide_id = None
    row = _row()

    xmpp.MainWindow._schedule_show_actions(w, row)
    first = w._actions_show_id
    assert w.root.pending[first][0] == 120
    assert w.root.pending[first][1] is not None

    xmpp.MainWindow._schedule_show_actions(w, row)  # tekrar enter
    assert first in w.root.cancelled and w._actions_show_id != first

    xmpp.MainWindow._schedule_hide_actions(w)
    hid = w._actions_hide_id
    assert w.root.pending[hid][0] == 260

    xmpp.MainWindow._cancel_show_actions(w)
    xmpp.MainWindow._cancel_hide_actions(w)
    assert w._actions_show_id is None and w._actions_hide_id is None
    assert set(w.root.pending) == set()


def test_show_actions_retracted_and_destroyed_row_benign():
    w = object.__new__(xmpp.MainWindow)
    w.root = _Root()
    called = []
    w._ensure_action_bar = lambda: called.append("bar")
    xmpp.MainWindow._show_actions(w, _row(retracted=True))
    assert called == []  # retracted → bar kurulmaz

    w._ensure_action_bar = lambda: _W()
    w._populate_action_bar = lambda bar, row: None
    w._actions_row = None
    xmpp.MainWindow._show_actions(w, _row())
    assert w._actions_row is None  # position False → satır atanmaz
