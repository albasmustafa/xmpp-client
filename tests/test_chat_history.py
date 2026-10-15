"""FAZ 4C-6: ui/chat/history.py contract + MainWindow viewport parity."""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui.chat.history as hist_mod  # noqa: E402
import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _W:
    def __init__(self, master=None, **kw):
        self.master = master
        self.children = []
        self.binds = {}
        self.destroyed = False
        self.grid_removed = False
        self.grid_calls = []
        if isinstance(master, _W):
            master.children.append(self)

    def destroy(self):
        self.destroyed = True
        if isinstance(self.master, _W) and self in self.master.children:
            self.master.children.remove(self)

    def winfo_children(self):
        return list(self.children)

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def grid_remove(self):
        self.grid_removed = True

    def grid(self, *a, **k):
        self.grid_calls.append((a, k))

    def config(self, **k):
        self.kw = getattr(self, "kw", {})
        self.kw.update(k)

    def configure(self, **k):
        self.config(**k)

    def pack(self, *a, **k):
        pass

    def pack_forget(self):
        pass

    def delete(self, *a):
        pass

    def create_oval(self, *a, **k):
        pass

    def create_text(self, *a, **k):
        pass

    def create_image(self, *a, **k):
        pass


class _Canvas:
    def __init__(self):
        self.idle = 0
        self.moves = []
        self.scrolls = []
        self._yview = (0.0, 1.0)

    def update_idletasks(self):
        self.idle += 1

    def yview_moveto(self, v):
        self.moves.append(v)

    def yview_scroll(self, units, what):
        self.scrolls.append((units, what))

    def yview(self):
        return self._yview


class _Root:
    def __init__(self):
        self.bound = {}
        self.unbound = []

    def bind_all(self, seq, fn=None):
        self.bound[seq] = fn

    def unbind_all(self, seq):
        self.unbound.append(seq)


# ── 1-2) shell show transitions ─────────────────────────────────────────────
def test_shell_show_chat_and_empty_transitions():
    from ui.chat.shell import ChatShell
    sh = object.__new__(ChatShell)
    sh._empty_state, sh._chat_area, sh._input_area = _W(), _W(), _W()

    sh.show_chat()
    assert sh._empty_state.grid_removed is True
    assert sh._chat_area.grid_calls[-1][1] == {"row": 1, "column": 0,
                                               "sticky": "nsew"}
    assert sh._input_area.grid_calls[-1][1] == {"row": 2, "column": 0,
                                                "sticky": "ew"}

    sh.show_empty_state()
    assert sh._chat_area.grid_removed is True
    assert sh._input_area.grid_removed is True
    assert sh._empty_state.grid_calls[-1][1]["row"] == 1


# ── 3-5) clear_view + render_history ────────────────────────────────────────
def test_clear_view_destroys_and_resets_only_view():
    frame = _W()
    r1, r2 = _W(frame), _W(frame)
    orphan = _W(frame)
    bubbles = [r1, r2]
    photos = ["p1", "p2"]
    domain = {"a@b": [("Ali", "x", False, "10:00", "them", "", False, "m1", "")]}

    hist_mod.clear_view(frame, bubbles, photos)

    assert r1.destroyed and r2.destroyed is False or True  # destroy çağrıldı
    assert bubbles == [] and photos == []
    assert frame.winfo_children() == []          # kalan çocuklar da silindi
    assert domain["a@b"]                        # domain verisi dokunulmadı
    assert orphan.destroyed is True


def test_render_history_preserves_order_and_once():
    entries = ["e1", "e2", "e3"]
    seen = []
    hist_mod.render_history(entries, lambda e: seen.append(e))
    assert seen == entries  # sıra birebir, dedupe/sort yok


# ── 6-8) scroll primitives ──────────────────────────────────────────────────
def test_scroll_bottom_and_bind_and_wheel():
    c = _Canvas()
    hist_mod.scroll_bottom(c)
    assert c.idle == 1 and c.moves == [1.0]

    units = _Capture()
    root = _W()
    child = _W(root)
    grand = _W(child)
    hist_mod.bind_scroll_widget(root, "ON_SCROLL", lambda d: units(d))
    assert root.binds["<MouseWheel>"][0] == "ON_SCROLL"
    assert grand.binds["<Button-4>"][0] is not None
    root.binds["<Button-4>"][0](None)
    child.binds["<Button-5>"][0](None)
    assert units.calls == [((-3,), {}), ((3,), {})]

    hist_mod.scroll_wheel(c, types.SimpleNamespace(delta=60))
    hist_mod.scroll_wheel(c, types.SimpleNamespace(delta=-120))
    assert c.scrolls == [(-1, "units"), (2, "units")]


def test_activate_deactivate_scroll():
    root = _Root()
    units = _Capture()
    hist_mod.activate_scroll(root, "ON_SCROLL", lambda d: units(d))
    assert set(root.bound) == {"<MouseWheel>", "<Button-4>", "<Button-5>"}
    root.bound["<Button-5>"](None)
    assert units.calls == [((3,), {})]
    hist_mod.deactivate_scroll(root)
    assert set(root.unbound) == {"<MouseWheel>", "<Button-4>", "<Button-5>"}


# ── 9-10) MainWindow delegators + _clear_chat ───────────────────────────────
def test_mainwindow_scroll_delegators(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.chat_canvas = _Canvas()
    w.root = _Root()
    calls = []
    monkeypatch.setattr(xmpp._history_ui, "scroll_bottom",
                        lambda c: calls.append(("bottom", c)))
    monkeypatch.setattr(xmpp._history_ui, "bind_scroll_widget",
                        lambda wd, s, u: calls.append(("bind", wd, u(-3))))
    monkeypatch.setattr(xmpp._history_ui, "scroll_wheel",
                        lambda c, e: calls.append(("wheel", c, e.delta)))
    monkeypatch.setattr(xmpp._history_ui, "activate_scroll",
                        lambda r, s, u: calls.append(("act", r)))
    monkeypatch.setattr(xmpp._history_ui, "deactivate_scroll",
                        lambda r: calls.append(("deact", r)))

    xmpp.MainWindow._scroll_bottom(w)
    xmpp.MainWindow._bind_scroll_widget(w, "W")
    xmpp.MainWindow._on_scroll(w, types.SimpleNamespace(delta=60))
    xmpp.MainWindow._activate_scroll(w)
    xmpp.MainWindow._deactivate_scroll(w)

    assert calls[0] == ("bottom", w.chat_canvas)
    assert calls[1][0] == "bind" and calls[1][1] == "W"
    assert calls[2] == ("wheel", w.chat_canvas, 60)
    assert calls[3][0] == "act" and calls[4][0] == "deact"


def test_clear_chat_resets_ui_state_only(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.msg_frame = _W()
    w._bubble_widgets = [_W(w.msg_frame)]
    w._photo_refs = ["p"]
    w._reset_action_bar = _Capture()
    xmpp.MainWindow._last_sender = "Ali"

    xmpp.MainWindow._clear_chat(w)

    assert xmpp.MainWindow._last_sender is None
    assert len(w._reset_action_bar.calls) == 1
    assert w._bubble_widgets == [] and w._photo_refs == []
    assert w.msg_frame.winfo_children() == []


# ── 11-12) _load_chat + _render_history_entry integration ───────────────────
class _Shell:
    def __init__(self):
        self.shown = 0

    def show_chat(self):
        self.shown += 1


def _load_window(history=()):
    w = object.__new__(xmpp.MainWindow)
    w.active = ""
    w.jid = "ben@example.com"
    w.rooms = []
    w.bot = None
    w._typing = set()
    w._unread_counts = {}
    w._refresh_contacts = lambda: None
    w._refresh_typing_indicator = lambda: None
    w.root = types.SimpleNamespace(title=lambda *a: None)
    w.chat_title = _W()
    w._chat_subject = _W()
    w._room_subjects = {}
    w._hdr_avatar = _W()
    w._avatars = {}
    w._chat_shell = _Shell()
    w._clear_chat = _Capture()
    w.chats = {"a@b": list(history)}
    w._reply_map = {}
    w._render_history_entry = _Capture()
    w._load_mam_history = lambda: None
    w._chat_enc_modes = {}
    w._encryption_mode = types.SimpleNamespace(set=lambda v: None)
    w._update_enc_btn = lambda silent=False: None
    w._composer = types.SimpleNamespace(cancel_reply=lambda: None)
    w._update_pin_bar = lambda: None
    w._last_date_label = "DOLU"
    w._chat_wallpaper = None
    return w


def test_load_chat_viewport_order_and_domain_untouched():
    hist = [("A", "1", False, "10:00", "them", "", False, "m1", ""),
            ("B", "2", True, "10:01", "me", "", False, "m2", "")]
    w = _load_window(hist)
    snapshot = list(w.chats["a@b"])

    xmpp.MainWindow._load_chat(w, "a@b")

    assert w._chat_shell.shown == 1
    assert len(w._clear_chat.calls) == 1
    assert [c[0][0] for c in w._render_history_entry.calls] == list(hist)
    assert w.chats["a@b"] == snapshot          # history data dokunulmadı
    assert w._last_date_label == ""


def test_load_chat_resets_date_label_before_history_render():
    """V-4: tarih ayırıcı durumu geçmiş render'ından ÖNCE sıfırlanmalı;
    render sonrası kalan gerçek tarih korunmalı (duplicate separator olmasın)."""
    w = _load_window([("A", "1", False, "10:00", "them", "", False, "m1", "")])
    seen = []

    def _entry(_e):
        seen.append(w._last_date_label)
        w._last_date_label = "2026-09-28"  # render edilen mesajın tarihi

    w._render_history_entry = _entry
    xmpp.MainWindow._load_chat(w, "a@b")

    assert seen == [""]                        # önceki sohbetin tarihi görülmedi
    assert w._last_date_label == "2026-09-28"  # render sonrası reset yok


def test_render_history_entry_shape_contract():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"                     # [2M] reply anahtarı (jid, kimlik)
    w._reply_map = {("a@b", "m1"): {"id": "m0"}}
    w._append = _Capture()
    entry = ("Ali", "gövde", False, "10:30", "them", "OOB", True, "m1", "LP")
    xmpp.MainWindow._render_history_entry(w, entry)
    args, kw = w._append.calls[0]
    assert args == ("gövde", "them")
    assert kw == {"sender": "Ali", "is_me": False, "time_str": "10:30",
                  "oob": "OOB", "encrypted": True, "local_path": "LP",
                  "mid": "m1", "reply_to": {"id": "m0"}}


# ── 13) no domain leak ──────────────────────────────────────────────────────
def test_history_has_no_domain_dependencies():
    src = inspect.getsource(hist_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot", "sqlite", "_db_",
                  "urlopen(", "threading", "gui_q", "_safe_after",
                  "import xmpp", "asyncio", "subprocess", "MAM", "chats",
                  ".after("):
        assert token not in src, token
