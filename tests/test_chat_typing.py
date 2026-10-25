"""FAZ 4C-4B: typing timer/lifecycle contract testleri (T1/T2 + presentation)."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Root:
    def __init__(self):
        self._seq = 0
        self.pending = {}
        self.cancelled = []

    def after(self, ms, fn=None):
        self._seq += 1
        self.pending[self._seq] = (ms, fn)
        return self._seq

    def after_cancel(self, aid):
        self.cancelled.append(aid)
        self.pending.pop(aid, None)

    def fire(self, aid):
        _ms, fn = self.pending.pop(aid)
        fn()


def _typing_window(active="a@b", rooms=()):
    w = object.__new__(xmpp.MainWindow)
    w.root = _Root()
    w.active = active
    w.rooms = list(rooms)
    w._typing_send_id = None
    w._send_typing_notif = True
    w.bot = types.SimpleNamespace(send_chatstate=_Capture())
    return w


# ── T1: paused hedefi timer kurulduğu sohbet olmalı ─────────────────────────
def test_t1_paused_targets_same_chat_when_unchanged():
    w = _typing_window()
    xmpp.MainWindow._on_typing_key(w)
    assert w.bot.send_chatstate.calls[0][0] == ("a@b", "composing", "chat")
    aid = w._typing_send_id
    assert w.root.pending[aid][0] == 3000
    w.root.fire(aid)
    assert w.bot.send_chatstate.calls[-1][0] == ("a@b", "paused", "chat")
    assert w._typing_send_id is None


def test_t1_paused_targets_original_after_switch():
    w = _typing_window()
    xmpp.MainWindow._on_typing_key(w)
    aid = w._typing_send_id
    w.active = "c@d"                      # kullanıcı başka sohbete geçti
    w.root.fire(aid)
    sent = [c[0] for c in w.bot.send_chatstate.calls]
    assert sent == [("a@b", "composing", "chat"), ("a@b", "paused", "chat")]
    assert ("c@d", "paused", "chat") not in sent


def test_t1_repeated_key_cancels_previous_timer():
    w = _typing_window()
    xmpp.MainWindow._on_typing_key(w)
    old = w._typing_send_id
    xmpp.MainWindow._on_typing_key(w)
    assert old in w.root.cancelled
    assert len(w.root.pending) == 1 and w._typing_send_id != old


def test_t1_groupchat_mtype_captured():
    w = _typing_window(active="oda@conf", rooms=["oda@conf"])
    xmpp.MainWindow._on_typing_key(w)
    aid = w._typing_send_id
    w.active = "baska@x"
    w.root.fire(aid)
    assert w.bot.send_chatstate.calls[-1][0] == ("oda@conf", "paused",
                                                 "groupchat")


def test_t1_send_message_cancels_paused_timer():
    w = _typing_window()
    w.root = _Root()
    w.msg_var = types.SimpleNamespace(get=lambda: "merhaba", set=lambda v: None)
    w._composer = types.SimpleNamespace(get_text=lambda: "merhaba",
                                        clear_text=lambda: None,
                                        consume_reply=lambda: None)
    w._encryption_mode = types.SimpleNamespace(get=lambda: "none")
    w._store = _Capture()
    w._append = _Capture()
    w._chat_tabs = {}
    w._send_typing_notif = True
    w._disappearing_ttl = {}
    w._bubble_widgets = []
    w.bot = types.SimpleNamespace(send_chat=_Capture(), send_gc=_Capture(),
                                  send_reply=_Capture(),
                                  send_chatstate=_Capture())
    w._typing_send_id = 77
    xmpp.MainWindow._send_message(w)
    assert 77 in w.root.cancelled and w._typing_send_id is None


def test_t1_quit_cancels_paused_timer(monkeypatch):
    w = _typing_window()
    w.root = _QuitRoot()
    w._closing = False
    w._tray_icon = None
    w._temp_files = []
    w.active = None
    w._after_ids = set()
    for attr in ("_poll_id", "_idle_check_id", "_ping_loop_id",
                 "_conn_timeout_id", "_auto_theme_id",
                 "_typing_anim_id", "_typing_send_id"):
        setattr(w, attr, None)
    w._typing_send_id = "pause1"
    w.bot = None
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: None)
    monkeypatch.setattr(xmpp, "_cleanup_temp_files", lambda files: None)

    xmpp.MainWindow._quit(w)

    assert "pause1" in w.root.cancelled
    assert w._typing_send_id is None
    assert w.bot is None or not getattr(w.bot, "send_chatstate", None)


class _QuitRoot:
    class _Tk:
        def setvar(self, k, v):
            pass

        def splitlist(self, s):
            return s

        def call(self, *a):
            return ()

    def __init__(self):
        self.tk = _QuitRoot._Tk()
        self.cancelled = []

    def after_cancel(self, aid):
        self.cancelled.append(aid)

    def winfo_geometry(self):
        return "800x600+0+0"

    def state(self):
        return "normal"

    def destroy(self):
        pass


# ── T2: conversation switch'te stale remote typing ──────────────────────────
class _Widget:
    def __init__(self):
        self.kw = {}
        self.text = None

    def config(self, **k):
        self.kw.update(k)
        if "text" in k:
            self.text = k["text"]

    def pack(self, **k):
        pass

    def pack_forget(self):
        pass

    def grid(self, **k):
        pass

    def grid_remove(self):
        pass

    def delete(self, *a):
        pass

    def create_oval(self, *a, **k):
        pass

    def create_text(self, *a, **k):
        pass

    def create_image(self, *a, **k):
        pass


def _load_window(typing=(), active=""):
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w._typing = set(typing)
    w.jid = "ben@example.com"
    w.rooms = []
    w.bot = None
    w._unread_counts = {}
    w._refresh_contacts = lambda: None
    w.root = _Root()
    w.root.title = lambda *a: None
    w.chat_title = _Widget()
    w._chat_subject = _Widget()
    w._room_subjects = {}
    w._hdr_avatar = _Widget()
    w._avatars = {}
    w._empty_state = _Widget()
    w._chat_area = _Widget()
    w._input_area = _Widget()
    w._clear_chat = lambda: None
    w.chats = {}
    w._reply_map = {}
    w._append = _Capture()
    w._load_mam_history = lambda: None
    w._chat_shell = types.SimpleNamespace(show_chat=lambda: None)
    w._chat_enc_modes = {}
    w._encryption_mode = types.SimpleNamespace(set=lambda v: None)
    w._update_enc_btn = lambda silent=False: None
    w._composer = types.SimpleNamespace(cancel_reply=lambda: None)
    w._update_pin_bar = lambda: None
    w._last_date_label = ""
    w._chat_wallpaper = None
    w.typing_label = _Widget()
    w._typing_anim_id = None
    w._typing_dots = 0
    w._after_ids = set()
    return w


def test_t2_handler_active_and_inactive_stop_events():
    w = _typing_window()
    w._typing = set()
    starts, stops = _Capture(), _Capture()
    w._start_typing_anim = starts
    w._stop_typing_anim = stops
    w.typing_label = _Widget()

    xmpp.MainWindow._handle(w, "typing", {"jid": "a@b", "active": True})
    assert w._typing == {"a@b"} and len(starts.calls) == 1

    # aktif olmayan JID'in stop'u aktif indicator'ı kapatmaz
    xmpp.MainWindow._handle(w, "typing", {"jid": "x@y", "active": False})
    assert len(starts.calls) == 2 and stops.calls == []


def test_t2_switch_clears_foreign_indicator():
    w = _load_window(typing=("a@b",), active="a@b")
    xmpp.MainWindow._refresh_typing_indicator(w)
    anim = w._typing_anim_id
    assert anim is not None and w.typing_label.text.startswith("✎")

    xmpp.MainWindow._load_chat(w, "c@d")

    assert w.active == "c@d"
    assert anim in w.root.cancelled
    assert w._typing_anim_id is None
    assert w.typing_label.text == ""


def test_t2_switch_shows_indicator_for_new_active():
    w = _load_window(typing=("a@b", "c@d"), active="a@b")
    xmpp.MainWindow._refresh_typing_indicator(w)

    xmpp.MainWindow._load_chat(w, "c@d")

    assert w._typing_anim_id is not None
    assert w.typing_label.text.startswith("✎")


def test_t2_refresh_start_when_active_in_set():
    w = _load_window(typing=("a@b",), active="a@b")
    xmpp.MainWindow._refresh_typing_indicator(w)
    assert w._typing_anim_id is not None

    w.active = "z@z"
    xmpp.MainWindow._refresh_typing_indicator(w)
    assert w._typing_anim_id is None and w.typing_label.text == ""


def test_t2_quit_cancels_typing_anim(monkeypatch):
    w = _typing_window()
    w.root = _QuitRoot()
    w._closing = False
    w._tray_icon = None
    w._temp_files = []
    w.active = None
    w._after_ids = set()
    for attr in ("_poll_id", "_idle_check_id", "_ping_loop_id",
                 "_conn_timeout_id", "_auto_theme_id",
                 "_typing_anim_id", "_typing_send_id"):
        setattr(w, attr, None)
    w._typing_anim_id = "anim1"
    w.bot = None
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: None)
    monkeypatch.setattr(xmpp, "_cleanup_temp_files", lambda files: None)

    xmpp.MainWindow._quit(w)

    assert "anim1" in w.root.cancelled and w._typing_anim_id is None


# ── 4C-4B extraction: presentation boundary ─────────────────────────────────
def test_typing_presentation_primitives():
    import ui.chat.typing as typing_mod
    lbl = _Widget()
    typing_mod.show_typing(lbl, lambda k: "yazıyor", 2)
    assert lbl.text == "✎ yazıyor.."
    typing_mod.hide_typing(lbl)
    assert lbl.text == ""


def test_animate_uses_presentation_cycle_and_closing_guard():
    import ui.chat.typing as typing_mod
    assert typing_mod is xmpp._typing_ui
    w = _typing_window()
    w.typing_label = _Widget()
    w._typing_dots = 0
    w._typing_anim_id = None
    w._closing = False

    xmpp.MainWindow._animate_typing(w)
    assert w.typing_label.text == f"✎ {'yazıyor'}."
    aid = w._typing_anim_id
    assert w.root.pending[aid][0] == 500
    w.root.fire(aid)
    assert w.typing_label.text.endswith("..")

    w._closing = True
    w.typing_label.text = None
    xmpp.MainWindow._animate_typing(w)
    assert w.typing_label.text is None  # _closing'de hiç yazmaz


def test_stop_uses_hide_presentation():
    w = _typing_window()
    w.typing_label = _Widget()
    w.typing_label.text = "✎ x"
    w._typing_anim_id = 5
    xmpp.MainWindow._stop_typing_anim(w)
    assert 5 in w.root.cancelled
    assert w.typing_label.text == "" and w._typing_anim_id is None


def test_typing_module_has_no_domain_or_timer():
    import inspect

    import ui.chat.typing as typing_mod
    src = inspect.getsource(typing_mod)
    for token in ("_after(", "root.after", "threading.", "self.active",
                  "asyncio", "import xmpp", "sqlite", "gui_q"):
        assert token not in src, token
