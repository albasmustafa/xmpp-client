"""FAZ 4C-5B2: audio/voice presentation + stale-callback regression testleri."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fake_selectable  # noqa: E402

import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Holder:
    def __init__(self, alive=True):
        self.alive = alive
        self.children = []
        self.labels = []

    def winfo_exists(self):
        return self.alive

    def winfo_children(self):
        if not self.alive:
            raise AssertionError("destroyed holder'da winfo_children")
        return list(self.children)


# ── A1/A2: destroyed audio holder guard ─────────────────────────────────────
def test_place_audio_skips_destroyed_holder(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w._show_voice_waveform = _Capture()
    w._scroll_bottom = _Capture()
    dead = _Holder(alive=False)

    xmpp.MainWindow._place_audio(w, dead, "/tmp/x.wav", "BG", "http://x")

    assert w._show_voice_waveform.calls == []
    assert w._scroll_bottom.calls == []


def test_place_audio_fallback_skips_destroyed_holder(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    dead = _Holder(alive=False)
    xmpp.MainWindow._place_audio_fallback(w, dead, "http://x", "BG")
    assert dead.labels == []


# ── A3: waveform late bars callback on destroyed widgets ────────────────────
class _W:
    def __init__(self, master=None, **kw):
        self.master = master
        self.kw = dict(kw)
        self.children = []
        self.binds = {}
        self.alive = True
        self.drawn = []
        if isinstance(master, _W):
            master.children.append(self)

    def pack(self, *a, **k):
        self.kw.setdefault("_pack", (a, k))

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def config(self, **k):
        if not self.alive:
            raise AssertionError("destroyed widget'a config")
        self.kw.update(k)

    def winfo_exists(self):
        return self.alive

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        self.alive = False
        if isinstance(self.master, _W) and self in self.master.children:
            self.master.children.remove(self)

    def grid(self, *a, **k):
        pass

    def columnconfigure(self, *a, **k):
        pass

    def rowconfigure(self, *a, **k):
        pass

    def place(self, *a, **k):
        pass

    def update_idletasks(self):
        pass

    def delete(self, *a):
        self.drawn.append(("delete", a))

    def create_text(self, *a, **k):
        self.drawn.append(("text", k))

    def create_rectangle(self, *a, **k):
        self.drawn.append(("rect", k))

    def create_line(self, *a, **k):
        self.drawn.append(("line", k))


def test_silent_waveform_draws_bars_without_division_by_zero():
    canvas = _W()
    xmpp._audio_ui.draw_waveform(
        canvas, [0, 0, 0], 12, 20, 0, "#ffffff", xmpp._chat_theme(), False)

    assert [kind for kind, _kwargs in canvas.drawn] == ["delete", "rect", "rect", "rect"]


def test_waveform_late_bars_callback_skips_destroyed_widgets(monkeypatch):
    monkeypatch.setattr(xmpp, "tk", types.SimpleNamespace(
        Frame=_W, Label=_W, Canvas=_W))
    scheduled = []

    def fake_safe_after(ms, fn, *a):
        scheduled.append((fn, a))

    threads = []

    class _T:
        def __init__(self, target=None, daemon=None):
            threads.append(target)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    w = object.__new__(xmpp.MainWindow)
    w._safe_after = fake_safe_after
    w._load_waveform_bars = lambda path: (2.0, [1, 2, 3])
    w._scroll_bottom = lambda: None

    bubble = _W()
    xmpp.MainWindow._show_voice_waveform(w, bubble, "/tmp/x.wav", xmpp.BG_THEM)

    # worker'ın schedule ettiği bars callback'ini al
    threads[-1]()
    assert scheduled, "bars callback schedule edilmedi"
    fn, args = scheduled[-1]

    for wdg in _all(bubble):
        wdg.alive = False
    fn(*args)  # geç gelen bars → destroyed widget'lara dokunmamalı


def _all(w):
    out = [w]
    for c in w.children:
        out.extend(_all(c))
    return out


# ── Presentation primitives ─────────────────────────────────────────────────
import ui.chat.audio as audio_mod  # noqa: E402


def _patch_audio_tk(monkeypatch):
    monkeypatch.setattr(audio_mod, "tk", types.SimpleNamespace(
        Frame=_W, Label=_W, Canvas=_W))


def _theme():
    return dict(xmpp._chat_theme())


def test_audio_placeholder_presentation(monkeypatch):
    _patch_audio_tk(monkeypatch)
    parent = _W()
    holder = audio_mod.audio_placeholder(parent, _theme(), "BG")
    assert holder.kw["bg"] == "BG"
    assert holder.children[0].kw["text"] == "🎤 Yükleniyor…"
    assert parent.children == [holder]


def test_start_player_clears_and_titles(monkeypatch):
    _patch_audio_tk(monkeypatch)
    holder = _W()
    old = _W(holder)
    audio_mod.start_player(holder, _theme(), "BG")
    assert old.alive is False
    assert [c.kw.get("text") for c in holder.children] == ["🎤 Ses Mesajı"]


def test_fallback_link_open_once(monkeypatch):
    _patch_audio_tk(monkeypatch)
    opened = _Capture()
    holder = _W()
    _W(holder)  # eski içerik
    lnk = audio_mod.fallback_link(holder, _theme(), "BG", "http://x/a.ogg",
                                  lambda: opened())
    assert lnk.kw["text"] == "🎤 Ses: http://x/a.ogg…"
    lnk.binds["<Button-1>"][0](None)
    assert len(opened.calls) == 1


def test_sent_voice_bubble_and_finish_order(monkeypatch):
    _patch_audio_tk(monkeypatch)
    row, bubble = audio_mod.sent_voice_bubble(_W(), _theme())
    assert row.kw["bg"] == xmpp.BG_CHAT and bubble.kw["bg"] == xmpp.BG_ME
    assert [c.kw.get("text") for c in bubble.children] == ["🎤 Ses Mesajı"]
    audio_mod.finish_voice_bubble(bubble, _theme(), "12:34")
    labels = [c.kw.get("text") for c in bubble.children[-1].children]
    assert labels == ["12:34", " ✓"]


def test_draw_waveform_empty_bars_and_progress(monkeypatch):
    _patch_audio_tk(monkeypatch)
    theme = _theme()
    canvas = _W()
    audio_mod.draw_waveform(canvas, [], 180, 32, 0.0, "ACC", theme, False)
    assert canvas.drawn[-1][0] == "text"  # 🎵
    assert canvas.drawn[-1][1]["text"] == "🎵"

    canvas2 = _W()
    audio_mod.draw_waveform(canvas2, [1, 2, 3], 180, 32, 0.5, "ACC",
                            theme, False)
    rects = [d for d in canvas2.drawn if d[0] == "rect"]
    lines = [d for d in canvas2.drawn if d[0] == "line"]
    assert len(rects) == 3 and len(lines) == 1
    assert rects[0][1]["fill"] == "ACC"       # progress içi vurgulu
    assert rects[2][1]["fill"] == xmpp.FG_DIM  # dışı idle


def test_set_play_icon_and_duration(monkeypatch):
    _patch_audio_tk(monkeypatch)
    btn, lbl = _W(), _W()
    audio_mod.set_play_icon(btn, True)
    assert btn.kw["text"] == "⏸"
    audio_mod.set_play_icon(btn, False)
    assert btn.kw["text"] == "▶"
    audio_mod.set_duration(lbl, 75)
    assert lbl.kw["text"] == "1:15"


# ── MainWindow integration ──────────────────────────────────────────────────
def test_show_sent_voice_integration_and_target_guard(monkeypatch):
    _patch_audio_tk(monkeypatch)
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w._store = _Capture()
    w.msg_frame = _W()
    w._bubble_widgets = []
    w._scroll_bottom = _Capture()
    w._show_voice_waveform = _Capture()

    xmpp.MainWindow._show_sent_voice(w, "/tmp/x.wav", target="a@b")
    assert w._store.calls[0][0][0] == "a@b"
    assert w._show_voice_waveform.calls[0][0][1] == "/tmp/x.wav"
    row = w._bubble_widgets[-1]
    assert row._is_me is True and row._body == "🎤 Ses mesajı"
    assert len(w._scroll_bottom.calls) == 1

    # hedef değişmişse yalnız store (mevcut semantik)
    w2 = object.__new__(xmpp.MainWindow)
    w2.active = "b@c"
    w2._store = _Capture()
    w2.msg_frame = _W()
    w2._bubble_widgets = []
    w2._scroll_bottom = _Capture()
    w2._show_voice_waveform = _Capture()
    xmpp.MainWindow._show_sent_voice(w2, "/tmp/x.wav", target="a@b")
    assert len(w2._store.calls) == 1 and w2._bubble_widgets == []
    assert w2._show_voice_waveform.calls == []


def test_append_audio_ordering_and_worker(monkeypatch):
    _patch_audio_tk(monkeypatch)
    monkeypatch.setattr(xmpp._render, "tk", types.SimpleNamespace(
        Frame=_W, Label=_W, Canvas=_W, StringVar=_W, Toplevel=_W))
    fake_selectable.install(monkeypatch, _W)   # seçilebilir gövde
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
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
    monkeypatch.setattr(xmpp, "_avatar", lambda *a, **k: _W())
    xmpp.MainWindow._last_sender = None

    order = []
    orig = audio_mod.audio_placeholder

    def spy(parent, theme, bg):
        order.append("audio")
        return orig(parent, theme, bg)

    monkeypatch.setattr(xmpp._audio_ui, "audio_placeholder", spy)
    orig_meta = xmpp._render.render_meta_row

    def spy_meta(*a, **k):
        order.append("meta")
        return orig_meta(*a, **k)

    monkeypatch.setattr(xmpp._render, "render_meta_row", spy_meta)
    threads = []

    class _T:
        def __init__(self, target=None, args=(), daemon=None):
            threads.append((target, args))

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _T)

    # Hotfix 2A/2C: bounded dispatcher runner'ı kayıtlı worker'ı çağırır
    seen = []
    w._audio_fetch_worker = lambda *a: seen.append(a)

    xmpp.MainWindow._append(w, "bak http://x/a.ogg", "them", sender="Ali")

    assert order == ["audio", "meta"]  # BODY → AUDIO → META
    assert threads  # dispatcher üzerinden spawn
    threads[0][0]()
    assert seen and seen[0][0] == "http://x/a.ogg"


# ── No-domain/engine leak ───────────────────────────────────────────────────
def test_audio_module_no_domain_or_engine():
    import inspect
    src = inspect.getsource(audio_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot", "sqlite", "_db_",
                  "urlopen(", "threading", "gui_q", "_safe_after",
                  "import xmpp", "asyncio", "subprocess", "pyaudio",
                  "PyAudio", "GStreamer", "state_lock", "_voice_lock",
                  "voice_lock", ".after("):
        assert token not in src, token
