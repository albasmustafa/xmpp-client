"""FAZ 4C-1: ChatShell extraction contract testleri (headless fake Tk)."""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui.chat.shell as shell_mod  # noqa: E402
import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Var:
    def __init__(self, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class _W:
    instances = []

    def __init__(self, master=None, **kw):
        self.master = master
        self.kw = dict(kw)
        self.binds = {}
        self.grid_calls = []
        self.pack_calls = []
        self.place_calls = []
        self.items = []
        self.configs = []
        self.delete_count = 0
        self.grid_removed = False
        _W.instances.append(self)

    def pack(self, *a, **k):
        self.pack_calls.append((a, k))

    def grid(self, *a, **k):
        self.grid_calls.append((a, k))

    def place(self, *a, **k):
        self.place_calls.append((a, k))

    def grid_remove(self):
        self.grid_removed = True

    def grid_propagate(self, *a, **k):
        pass

    def columnconfigure(self, *a, **k):
        pass

    def rowconfigure(self, *a, **k):
        pass

    def configure(self, *a, **k):
        self.configs.append((a, k))

    def config(self, *a, **k):
        self.configure(*a, **k)

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def create_oval(self, *a, **k):
        self.items.append(("oval", k))

    def create_text(self, *a, **k):
        self.items.append(("text", k))

    def create_rectangle(self, *a, **k):
        self.items.append(("rect", k))

    def create_window(self, *a, **k):
        self.items.append(("window", k))
        return "cw1"

    def delete(self, *a):
        self.delete_count += 1

    def itemconfig(self, *a, **k):
        self.itemconfig_calls = getattr(self, "itemconfig_calls", [])
        self.itemconfig_calls.append((a, k))

    def after(self, ms, fn=None):
        self.after_calls = getattr(self, "after_calls", [])
        self.after_calls.append((ms, fn))
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


CALLBACK_KEYS = (
    "on_header_menu", "on_add_contact", "on_join_room",
    "on_discover_rooms", "on_cancel_reply", "on_show_pinned", "on_send",
    "on_paste", "on_typing", "on_emoji", "on_gif", "on_file", "on_voice",
    "on_encryption", "on_canvas_enter", "on_canvas_leave",
)


def _theme():
    return {k: f"C:{k}" for k in (
        "BG_CHAT", "BG_CARD", "BG_HOVER", "BG_THEM", "BORDER", "FG",
        "FG_DIM", "ACCENT", "ACCENT2", "ACCENT_G", "FG_ME", "GLOW",
        "RED", "FONT")}


def _make_shell(monkeypatch):
    _W.instances = []
    calls = {k: _Capture() for k in CALLBACK_KEYS}
    monkeypatch.setattr(shell_mod, "tk", types.SimpleNamespace(
        Frame=_W, Label=_W, Canvas=_W, StringVar=_Var))
    monkeypatch.setattr(shell_mod, "ttk", types.SimpleNamespace(
        Scrollbar=_W, Button=_W))
    tip = _Capture()
    sh = shell_mod.ChatShell(_W(), lambda s: "T:" + s, _theme(), calls,
                             entry_cls=_W, add_tooltip=tip)
    return sh, calls, tip


def _by_text(text):
    for w in _W.instances:
        if w.kw.get("text") == text:
            return w
    raise AssertionError(f"widget bulunamadı: {text}")


# ── A) construction ─────────────────────────────────────────────────────────
def test_shell_builds_required_widget_graph(monkeypatch):
    sh, calls, tip = _make_shell(monkeypatch)
    for name in shell_mod.ChatShell.LEGACY_REFS:
        assert hasattr(sh, name), name
    assert isinstance(sh._encryption_mode, _Var)
    assert isinstance(sh.msg_var, _Var)
    assert sh._canvas_win == "cw1"
    # tooltip yalnız GIF butonuna bağlandı
    assert len(tip.calls) == 1 and tip.calls[0][0][0] is sh._gif_btn


# ── B) callback wiring ──────────────────────────────────────────────────────
def test_shell_callback_wiring(monkeypatch):
    sh, calls, _ = _make_shell(monkeypatch)

    sh._msg_entry.binds["<Return>"][0](None)
    sh._msg_entry.binds["<Control-v>"][0](None)
    sh._msg_entry.binds["<KeyRelease>"][0](None)
    sh._send_c.binds["<Button-1>"][0](None)
    sh.chat_canvas.binds["<Enter>"][0](None)
    sh.chat_canvas.binds["<Leave>"][0](None)

    _by_text("😊").binds["<Button-1>"][0](None)
    _by_text("🎭").binds["<Button-1>"][0](None)
    _by_text("📎").binds["<Button-1>"][0](None)
    _by_text("🎤").binds["<Button-1>"][0](None)
    _by_text("🔓").binds["<Button-1>"][0](None)
    _by_text("⋮").binds["<Button-1>"][0](None)
    _by_text("✕").binds["<Button-1>"][0](None)
    _by_text("📌").binds["<Button-1>"][0](None)

    assert len(calls["on_send"].calls) == 2       # Return + send canvas
    assert len(calls["on_paste"].calls) == 1
    assert len(calls["on_typing"].calls) == 1
    assert len(calls["on_canvas_enter"].calls) == 1
    assert len(calls["on_canvas_leave"].calls) == 1
    for key in ("on_emoji", "on_gif", "on_file", "on_voice", "on_encryption",
                "on_header_menu", "on_cancel_reply",
                "on_show_pinned"):
        assert len(calls[key].calls) == 1, key

    # Boş durum butonları
    btns = [w for w in _W.instances
            if "command" in w.kw and "text" in w.kw]
    assert len(btns) == 3
    for b in btns:
        b.kw["command"]()
    for key in ("on_add_contact", "on_join_room", "on_discover_rooms"):
        assert len(calls[key].calls) == 1, key


# ── C) visual helpers ───────────────────────────────────────────────────────
def test_shell_visual_helpers(monkeypatch):
    sh, _, _ = _make_shell(monkeypatch)

    sh._draw_send()
    assert any(k.get("text") == "▶" for _, k in sh._send_c.items)
    n = len(sh._send_c.items)
    sh._draw_send(hover=True)
    assert len(sh._send_c.items) > n
    assert any(k.get("outline") == "C:GLOW"
               for _, k in sh._send_c.items if "outline" in k)

    sh._on_canvas_configure(types.SimpleNamespace(width=321))
    assert sh.chat_canvas.itemconfig_calls[-1][0] == ("cw1",)
    assert sh.chat_canvas.itemconfig_calls[-1][1]["width"] == 321
    assert getattr(sh.chat_canvas, "after_calls", []) == []
    sh._on_msg_frame_configure(None)
    assert sh.chat_canvas.after_calls[-1][0] == 10

    sh.show_empty_state()
    assert sh._chat_area.grid_removed is True
    assert sh._input_area.grid_removed is True
    assert sh._empty_state.grid_calls[-1][0] == ()
    assert sh._empty_state.grid_calls[-1][1]["row"] == 1


# ── D) no domain leak ───────────────────────────────────────────────────────
def test_shell_has_no_domain_dependencies():
    src = inspect.getsource(shell_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot", "run_coroutine_threadsafe",
                  "sqlite", "_db_", "urlopen", "threading.Thread", "gui_q"):
        assert token not in src, token
    assert "import xmpp" not in src


# ── E) MainWindow integration + rebuild ─────────────────────────────────────
class _StubShell:
    LEGACY_REFS = ("_chat_panel", "chat_canvas", "msg_frame", "_canvas_win",
                   "msg_var", "_msg_entry", "_send_c", "_reply_bar",
                   "_reply_lbl", "_pin_bar", "_pin_lbl", "chat_title",
                   "_chat_subject", "_hdr_avatar", "_empty_state",
                   "_chat_area", "_input_area", "_encryption_mode",
                   "_inp_border", "_emoji_btn", "_gif_btn", "_file_btn",
                   "_mic_btn", "_enc_btn", "typing_label", "_enc_badge")
    calls = []

    def __init__(self, parent, t, theme, callbacks, entry_cls,
                 add_tooltip=None):
        _StubShell.calls.append((parent, t, theme, callbacks, entry_cls,
                                 add_tooltip))
        tag = f"shell{len(_StubShell.calls)}"
        for n in self.LEGACY_REFS:
            setattr(self, n, f"{tag}:{n}")

    def show_empty_state(self):
        pass


def test_build_chat_panel_aliases_and_typing_state(monkeypatch):
    _StubShell.calls = []
    monkeypatch.setattr(xmpp, "_ChatShell", _StubShell)
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"

    xmpp.MainWindow._build_chat_panel(win)

    parent, t, theme, callbacks, entry_cls, tip = _StubShell.calls[0]
    assert parent == "ROOT"
    assert t is xmpp._t
    assert entry_cls is xmpp.PlaceholderEntry
    assert tip is xmpp._add_tooltip
    assert theme["BG_CARD"] is xmpp.BG_CARD
    for key in CALLBACK_KEYS:
        assert key in callbacks, key
    assert callbacks["on_send"] == win._send_message
    assert callbacks["on_typing"] == win._on_typing_key
    assert callbacks["on_discover_rooms"] == win._search_rooms_dialog
    # Alias'lar gerçek shell ref'lerine bağlı
    for n in _StubShell.LEGACY_REFS:
        assert getattr(win, n) == f"shell1:{n}", n
    assert (win._typing_dots, win._typing_anim_id,
            win._typing_send_id) == (0, None, None)


def test_build_chat_panel_rebuild_refreshes_aliases(monkeypatch):
    _StubShell.calls = []
    monkeypatch.setattr(xmpp, "_ChatShell", _StubShell)
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"

    xmpp.MainWindow._build_chat_panel(win)
    xmpp.MainWindow._build_chat_panel(win)

    assert win.chat_canvas == "shell2:chat_canvas"
    assert win.msg_frame == "shell2:msg_frame"


def test_removed_methods_gone_and_callsites_use_shell():
    assert not hasattr(xmpp.MainWindow, "_draw_send_btn")
    assert not hasattr(xmpp.MainWindow, "_show_empty_state")
    assert not hasattr(xmpp.MainWindow, "_on_canvas_configure")
    assert not hasattr(xmpp.MainWindow, "_on_msg_frame_configure")
    assert "self._chat_shell.show_empty_state()" in inspect.getsource(xmpp)
