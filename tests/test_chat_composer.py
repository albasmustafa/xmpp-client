"""FAZ 4C-4A: ui/chat/composer.py contract + MainWindow send/escape parity."""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui.chat.composer as composer_mod  # noqa: E402
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


class _Entry:
    def __init__(self):
        self.focus_calls = 0

    def focus_set(self):
        self.focus_calls += 1


class _Bar:
    def __init__(self):
        self.packed = []
        self.unpacked = 0
        self.master = types.SimpleNamespace(
            winfo_children=lambda: ["header", self, "input"])

    def pack(self, **k):
        self.packed.append(k)

    def pack_forget(self):
        self.unpacked += 1


class _Lbl:
    def __init__(self):
        self.kw = {}

    def config(self, **k):
        self.kw.update(k)


def _composer(text=""):
    var, entry, bar, lbl = _Var(text), _Entry(), _Bar(), _Lbl()
    return composer_mod.ComposerView(var, entry, bar, lbl), var, entry, bar, lbl


# ── 1-2) construction + set_reply ───────────────────────────────────────────
def test_construction_and_set_reply_exact_target():
    c, var, entry, bar, lbl = _composer("yazı")
    assert c.get_text() == "yazı"
    reply = {"mid": "m1", "body": "eski", "sender": "Ali", "to": "a@b/Ali"}
    c.set_reply(reply)
    assert c.get_reply() is reply and c.has_reply() is True
    assert lbl.kw["text"] == "↩ Ali: eski"
    assert bar.packed[-1] == {"side": "top", "fill": "x", "before": "input"}


# ── 3-6) cancel/consume idempotency ─────────────────────────────────────────
def test_cancel_and_consume_semantics():
    c, *_ = _composer()
    reply = {"mid": "m1", "body": "b", "sender": "Ali", "to": ""}
    c.set_reply(reply)
    c.cancel_reply()
    assert c.has_reply() is False and c.get_reply() is None
    assert c._bar.unpacked == 1
    c.cancel_reply()  # idempotent
    assert c.has_reply() is False and c._bar.unpacked == 2

    c.set_reply(reply)
    got = c.consume_reply()
    assert got is reply and c.has_reply() is False
    assert c._bar.unpacked == 3
    assert c.consume_reply() is None  # boşta None


# ── 7) preview truncation parity ────────────────────────────────────────────
def test_reply_preview_truncation_parity():
    c, _, _, _, lbl = _composer()
    c.set_reply({"mid": "m", "body": "x" * 80, "sender": "A", "to": ""})
    assert lbl.kw["text"] == "↩ A: " + "x" * 80
    c.set_reply({"mid": "m", "body": "x" * 81, "sender": "A", "to": ""})
    assert lbl.kw["text"].endswith("…")


# ── 8-11) text primitives ───────────────────────────────────────────────────
def test_text_primitives_and_focus():
    c, var, entry, *_ = _composer("abc")
    c.insert_text("😊")
    assert var.get() == "abc😊"           # mevcut append semantiği
    assert c.get_text() == "abc😊"
    c.clear_text()
    assert var.get() == ""
    c.focus()
    assert entry.focus_calls == 1


# ── 12-14) _send_message integration ────────────────────────────────────────
def _mw(text="merhaba", reply=None):
    var, entry, bar, lbl = _Var(text), _Entry(), _Bar(), _Lbl()
    w = object.__new__(xmpp.MainWindow)
    w.msg_var = var
    w._composer = composer_mod.ComposerView(var, entry, bar, lbl)
    if reply:
        w._composer.set_reply(reply)
    w.active = "a@b"
    w.rooms = []
    w._encryption_mode = _Var("none")
    w._store = _Capture()
    w._append = _Capture()
    w._chat_tabs = {}
    w._send_typing_notif = False
    w._disappearing_ttl = {}
    w._bubble_widgets = []
    w._handle_bot_command = _Capture()
    w.bot = types.SimpleNamespace(
        send_chat=_Capture(), send_gc=_Capture(), send_reply=_Capture(),
        send_chatstate=_Capture())
    return w


def test_send_message_reply_capture_and_clear():
    reply = {"mid": "m1", "body": "eski", "sender": "Ali", "to": "a@b/Ali"}
    w = _mw(text="yanıt", reply=reply)
    xmpp.MainWindow._send_message(w)

    assert w.msg_var.get() == ""                      # clear_text
    assert w._composer.has_reply() is False           # consume
    assert w._store.calls[0][1]["reply_to"] is reply
    assert w._append.calls[0][1]["reply_to"] is reply
    args = w.bot.send_reply.calls[0][0]
    assert args[0] == "a@b" and args[2] == "m1" and args[3] == "eski"
    assert w.bot.send_reply.calls[0][1]["reply_to_jid"] == "a@b/Ali"


def test_send_message_empty_keeps_text_and_reply():
    reply = {"mid": "m1", "body": "eski", "sender": "Ali", "to": ""}
    w = _mw(text="   ", reply=reply)
    xmpp.MainWindow._send_message(w)
    assert w.msg_var.get() == "   "                   # boş gönderim text'i silmez
    assert w._composer.has_reply() is True            # reply korunur
    assert w._store.calls == [] and w._append.calls == []


def test_send_message_command_consumes_reply_preexisting_semantics():
    reply = {"mid": "m1", "body": "eski", "sender": "Ali", "to": ""}
    w = _mw(text="/status çalışıyor", reply=reply)
    xmpp.MainWindow._send_message(w)
    assert w._handle_bot_command.calls[0][0] == ("/status çalışıyor",)
    assert w._composer.has_reply() is False           # mevcut semantik
    assert w._store.calls == [] and w.bot.send_chat.calls == []


# ── 15) _on_escape parity ───────────────────────────────────────────────────
def test_on_escape_reply_cancel_and_fallthrough():
    reply = {"mid": "m1", "body": "b", "sender": "A", "to": ""}
    w = _mw(reply=reply)
    assert xmpp.MainWindow._on_escape(w) is None
    assert w._composer.has_reply() is False
    # reply yokken çökmez; ikinci çağrı da benign
    assert xmpp.MainWindow._on_escape(w) is None


# ── 16) rebuild → stale ref yok ─────────────────────────────────────────────
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
        _StubShell.calls.append(self)
        tag = f"shell{len(_StubShell.calls)}"
        for n in self.LEGACY_REFS:
            setattr(self, n, f"{tag}:{n}")

    def show_empty_state(self):
        pass


def test_rebuild_rebinds_composer_refs(monkeypatch):
    _StubShell.calls = []
    monkeypatch.setattr(xmpp, "_ChatShell", _StubShell)
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    xmpp.MainWindow._build_chat_panel(w)
    assert w._composer._var == "shell1:msg_var"
    xmpp.MainWindow._build_chat_panel(w)
    assert w._composer._var == "shell2:msg_var"
    assert w._composer._bar == "shell2:_reply_bar"
    assert w._composer._lbl == "shell2:_reply_lbl"


# ── 17) no domain leak ──────────────────────────────────────────────────────
def test_composer_has_no_domain_dependencies():
    src = inspect.getsource(composer_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot",
                  "run_coroutine_threadsafe", "sqlite", "_db_", "urlopen(",
                  "threading.", "gui_q", "subprocess", "_safe_after",
                  "import xmpp", "asyncio", ".after("):
        assert token not in src, token
