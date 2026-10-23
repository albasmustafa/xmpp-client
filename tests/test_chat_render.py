"""FAZ 4C-2A: ui/chat/render.py contract + _append orchestrator parity."""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fake_selectable  # noqa: E402

import ui.chat.render as render_mod  # noqa: E402
import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _W:
    instances = []

    def __init__(self, master=None, **kw):
        self.master = master
        self.kw = dict(kw)
        self.binds = {}
        self.children = []
        self.pack_calls = []
        self.grid_calls = []
        if master is not None and isinstance(master, _W):
            master.children.append(self)
        _W.instances.append(self)

    def pack(self, *a, **k):
        self.pack_calls.append((a, k))

    def grid(self, *a, **k):
        self.grid_calls.append((a, k))

    def place(self, *a, **k):
        pass

    def configure(self, *a, **k):
        pass

    def config(self, *a, **k):
        pass

    def columnconfigure(self, *a, **k):
        pass

    def rowconfigure(self, *a, **k):
        pass

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def winfo_children(self):
        return list(self.children)

    def create_oval(self, *a, **k):
        pass

    def create_text(self, *a, **k):
        pass

    def create_rectangle(self, *a, **k):
        pass

    def create_window(self, *a, **k):
        return "cw1"

    def delete(self, *a):
        pass

    def itemconfig(self, *a, **k):
        pass

    def after(self, *a, **k):
        return "af1"

    def bbox(self, *a):
        return (0, 0, 10, 10)

    def yview_moveto(self, *a):
        pass

    def yview(self, *a):
        pass

    def set(self, *a):
        pass

    def winfo_exists(self):
        return True


def _window(monkeypatch, active="a@b"):
    monkeypatch.setattr(render_mod, "tk", types.SimpleNamespace(
        Frame=_W, Label=_W, Canvas=_W, StringVar=_W, Toplevel=_W))
    fake_selectable.install(monkeypatch, _W)
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w.msg_frame = _W()
    w._bubble_widgets = []
    w._avatars = {}
    w._photo_refs = []
    w._reactions = {}
    w._reply_map = {}
    w._last_date_label = ""
    w._prune_photo_refs = lambda: None
    w._bind_scroll_widget = _Capture()
    w._scroll_bottom = _Capture()
    w._render_reactions = _Capture()
    w._jump_to_message = _Capture()
    w._set_reply = _Capture()
    w._attach_file_card = lambda *a: None
    w._bind_message_menu = lambda *a, **k: None
    w._avatars_calls = []
    monkeypatch.setattr(xmpp, "_avatar",
                        lambda *a, **k: (w._avatars_calls.append(a), _W())[1])
    xmpp.MainWindow._last_sender = None
    return w


def _labels(text=None):
    out = [x for x in _W.instances if "text" in x.kw]
    if text is not None:
        out = [x for x in out if x.kw["text"] == text]
    return out


# ── A) outgoing text row contract ───────────────────────────────────────────
def test_outgoing_text_row_contract(monkeypatch):
    w = _window(monkeypatch)
    xmpp.MainWindow._append(w, "benden", "me", mid="m1", time_str="10:30")

    rows = [x for x in w._bubble_widgets if getattr(x, "_mid", None) == "m1"]
    assert len(rows) == 1
    row = rows[0]
    assert (row._is_me, row._body, row._tag, row._sender) == \
        (True, "benden", "me", "")
    assert row._reply_to is None
    assert row._retracted is False and row._edited is False
    assert row._bubble.winfo_exists()
    assert row._body_text.kw["text"] == "benden"     # seçilebilir gövde
    assert _labels("10:30") and _labels(" ✓")
    # bookkeeping sırası: tarih ayırıcı önce, sonra row
    assert w._bubble_widgets[-1] is row
    assert len(w._scroll_bottom.calls) == 1


# ── B/C) incoming + MUC sender presentation ─────────────────────────────────
def test_incoming_and_muc_sender_presentation(monkeypatch):
    w = _window(monkeypatch)
    xmpp.MainWindow._append(w, "merhaba", "them", sender="Ali")
    row1 = [x for x in w._bubble_widgets if getattr(x, "_tag", "") == "them"][-1]
    assert (row1._is_me, row1._mid, row1._sender) == (False, "", "Ali")
    assert len(w._avatars_calls) == 1
    assert _labels("Ali")  # MUC/1:1 sender label

    # Aynı gönderici → avatar ve sender label tekrarı yok
    xmpp.MainWindow._append(w, "ikinci", "them", sender="Ali")
    assert len(w._avatars_calls) == 1
    assert len(_labels("Ali")) == 1


# ── D) reply preview + on_jump exactly once ─────────────────────────────────
def test_reply_preview_jump_callback(monkeypatch):
    w = _window(monkeypatch)
    xmpp.MainWindow._append(w, "yanit", "them", sender="Ali", mid="m2",
                            reply_to={"id": "m1", "sender": "Bob",
                                      "body": "eski mesaj"})
    assert _labels("↪ Bob") and _labels("eski mesaj")
    quote = [x for x in _W.instances
             if x.kw.get("cursor") == "hand2"
             and "<Button-1>" in x.binds and x.kw.get("padx") == 1][0]
    quote.binds["<Button-1>"][0](None)
    assert w._jump_to_message.calls == [(("m1",), {})]


# ── E) system message ───────────────────────────────────────────────────────
def test_system_message_row(monkeypatch):
    w = _window(monkeypatch)
    xmpp.MainWindow._append(w, "Ali katıldı", "sys")
    rows = [x for x in w._bubble_widgets if x.kw.get("bg") == xmpp.BG_CHAT]
    assert rows, "system divider yok"
    assert _labels("Ali katıldı")
    assert len(w._bubble_widgets) == 1
    assert xmpp.MainWindow._last_sender is None


# ── F/G) edited/retracted default contract ──────────────────────────────────
def test_initial_flags_false_and_identity_contract(monkeypatch):
    w = _window(monkeypatch)
    xmpp.MainWindow._append(w, "x", "them", sender="Ali", mid="m9",
                            reply_to={"id": "m1", "sender": "B", "body": "y"})
    row = w._bubble_widgets[-1]
    for attr in ("_mid", "_is_me", "_body", "_tag", "_sender", "_reply_to",
                 "_retracted", "_edited", "_bubble", "_msg_index"):
        assert hasattr(row, attr), attr
    assert row._retracted is False and row._edited is False


# ── H/I) date separator + theme inputs ──────────────────────────────────────
def test_date_separator_and_theme_inputs(monkeypatch):
    w = _window(monkeypatch)
    xmpp.MainWindow._append(w, "ilk", "them", sender="Ali",
                            time_str="2026-09-25T10:00:00Z")
    seps = [x for x in w._bubble_widgets if not hasattr(x, "_tag")]
    assert len(seps) == 1
    assert any("2026" in str(x.kw.get("text")) for x in _labels())
    # Aynı gün ikinci mesaj → duplicate yok
    xmpp.MainWindow._append(w, "ikinci", "them", sender="Ali",
                            time_str="2026-09-25T11:00:00Z")
    seps2 = [x for x in w._bubble_widgets if not hasattr(x, "_tag")]
    assert len(seps2) == 1
    # Tema değerleri gerçek global'lerden gelir
    bubbles = [x for x in _W.instances if x.kw.get("bg") == xmpp.BG_THEM]
    assert bubbles


# ── J) no domain leak ───────────────────────────────────────────────────────
def test_render_has_no_domain_dependencies():
    src = inspect.getsource(render_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot", "run_coroutine_threadsafe",
                  "sqlite", "urlopen(", "threading.", "gui_q",
                  "subprocess", "_safe_after", "import xmpp"):
        assert token not in src, token


# ── K) orchestrator parity: sıra ve contract ────────────────────────────────
def test_append_orchestration_parity(monkeypatch):
    w = _window(monkeypatch)
    xmpp.MainWindow._append(w, "bir", "them", sender="Ali")
    xmpp.MainWindow._append(w, "iki", "them", sender="Ali", mid="m2",
                            reply_to={"id": "m1", "sender": "Ali", "body": "bir"})
    xmpp.MainWindow._append(w, "sistem", "sys")

    kinds = []
    for x in w._bubble_widgets:
        if hasattr(x, "_msg_index"):
            kinds.append("row")
        else:
            kinds.append("other")
    assert kinds == ["other", "row", "row", "other"]  # sep, row1, row2, sys
    assert w._bubble_widgets[1]._mid == ""
    assert w._bubble_widgets[2]._mid == "m2"
    assert len(w._bind_scroll_widget.calls) == 4
    assert len(w._scroll_bottom.calls) == 3  # sep scroll çağırmaz


# ── 4C-2B: render_base_message assembly ─────────────────────────────────────
def _patch_render_tk(monkeypatch):
    monkeypatch.setattr(render_mod, "tk", types.SimpleNamespace(
        Frame=_W, Label=_W, Canvas=_W, StringVar=_W, Toplevel=_W))


def _base(parent, **over):
    args = dict(is_me=False, sender="", same_sender=False, compact=False,
                reply_to=None, display_body="", formatter=xmpp.MainWindow._format_markdown,
                avatar_factory=lambda *a, **k: _W(), avatar_photo=None,
                photo_refs=[], on_jump=lambda m: None,
                text_factory=fake_selectable.make(_W).selectable_text)
    args.update(over)
    return render_mod.render_base_message(parent, xmpp._chat_theme(), **args)


def test_base_assembly_outgoing_return_contract(monkeypatch):
    _W.instances = []
    _patch_render_tk(monkeypatch)
    view = _base(_W(), is_me=True, display_body="benden")
    assert type(view)._fields == ("row", "bubble", "colors", "body_kind",
                                  "body_widget")
    assert view.colors["bubble_bg"] == xmpp.BG_ME
    assert view.colors["bubble_fg"] == xmpp.FG_ME
    assert view.body_kind == "text"
    assert view.body_widget.kw["text"] == "benden"
    assert view.row.kw["bg"] == xmpp.BG_CHAT
    # Meta satırı assembly dışında (medya sırası için)
    assert not _labels("10:30")


def test_base_assembly_incoming_and_room_sender(monkeypatch):
    _W.instances = []
    _patch_render_tk(monkeypatch)
    avatars = []
    view = _base(_W(), sender="Ali",
                 avatar_factory=lambda *a, **k: (avatars.append(a), _W())[1],
                 display_body="merhaba")
    assert view.colors["bubble_bg"] == xmpp.BG_THEM
    assert len(avatars) == 1
    assert _labels("Ali")
    assert view.body_kind == "text"


def test_base_assembly_reply_and_jump(monkeypatch):
    _W.instances = []
    _patch_render_tk(monkeypatch)
    jumps = []
    _base(_W(), sender="Ali", display_body="yanit",
          reply_to={"id": "m1", "sender": "Bob", "body": "eski"},
          on_jump=jumps.append)
    assert _labels("↪ Bob") and _labels("eski")
    quote = [x for x in _W.instances
             if x.kw.get("cursor") == "hand2" and "<Button-1>" in x.binds
             and x.kw.get("padx") == 1][0]
    quote.binds["<Button-1>"][0](None)
    assert jumps == ["m1"]


def test_base_assembly_theme_values(monkeypatch):
    _W.instances = []
    _patch_render_tk(monkeypatch)
    custom = dict(xmpp._chat_theme())
    custom.update({"BG_ME": "#111111", "BG_THEM": "#222222",
                   "FG_ME": "#333333", "FG": "#444444", "SHADOW": "#555555",
                   "BORDER": "#666666", "ACCENT": "#777777"})
    out = render_mod.render_base_message(
        _W(), custom, is_me=True, sender="", same_sender=False, compact=False,
        reply_to=None, display_body="x",
        formatter=xmpp.MainWindow._format_markdown,
        avatar_factory=lambda *a, **k: _W(), avatar_photo=None,
        photo_refs=[], on_jump=lambda m: None,
        text_factory=fake_selectable.make(_W).selectable_text)
    assert out.colors["bubble_bg"] == "#111111"
    assert any(x.kw.get("bg") == "#111111" for x in _W.instances)


def test_append_integration_uses_base_assembly_and_identity(monkeypatch):
    w = _window(monkeypatch)
    real = render_mod.render_base_message
    calls = []

    def spy(*a, **k):
        calls.append(k)
        return real(*a, **k)

    monkeypatch.setattr(xmpp._render, "render_base_message", spy)
    xmpp.MainWindow._append(w, "gövde", "them", sender="Ali", mid="m7",
                            time_str="10:30", encrypted=True,
                            reply_to={"id": "m1", "sender": "B", "body": "y"})

    assert len(calls) == 1
    k = calls[0]
    assert (k["is_me"], k["sender"], k["display_body"]) == \
        (False, "Ali", "gövde")
    assert k["on_jump"] and k["formatter"]
    assert k["text_factory"] is xmpp._selectable.selectable_text  # seçilebilir
    row = w._bubble_widgets[-1]
    # identity MainWindow'da
    assert (row._mid, row._is_me, row._body, row._tag, row._sender) == \
        ("m7", False, "gövde", "them", "Ali")
    assert row._reply_to["id"] == "m1"
    assert row._bubble is not None and row._msg_index == len(w._bubble_widgets) - 1
    # encrypted meta assembly sonrası (media hook sırası korunur)
    assert _labels("🔒") and _labels("10:30")
