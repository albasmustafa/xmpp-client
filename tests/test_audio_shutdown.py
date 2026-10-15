"""FAZ 4C closure V-5: kayıt/oynatma kapanış lifecycle regression testleri.

- _quit aktif kaydı durdurmalı (mikrofon stream'i kapanabilsin)
- _quit aktif oynatıcılara stop sinyali göndermeli (pa_stream kapansın)
- cleanup istisnaları _quit'i durdurmamalı
- shutdown sonrası kuyruktaki GUI callback'leri mutation yapmamalı
"""

import os
import sys
import threading
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402

_RealThread = threading.Thread


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Tk:
    def setvar(self, *a, **k):
        pass

    def splitlist(self, s):
        return []

    def call(self, *a):
        return ()


class _Root:
    def __init__(self):
        self.tk = _Tk()
        self.destroyed = False
        self.cancelled = []

    def after_cancel(self, aid):
        self.cancelled.append(aid)

    def winfo_geometry(self):
        return "800x600+0+0"

    def state(self):
        return "normal"

    def destroy(self):
        self.destroyed = True


def _quit_window(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = _Root()
    w._closing = False
    w._relogin = False
    w._after_ids = set()
    for attr in ("_poll_id", "_idle_check_id", "_ping_loop_id",
                 "_conn_timeout_id", "_auto_theme_id",
                 "_typing_anim_id", "_typing_send_id"):
        setattr(w, attr, None)
    w._tray_icon = None
    w.bot = None
    w._temp_files = []
    w.active = None
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: None)
    monkeypatch.setattr(xmpp, "_cleanup_temp_files", lambda files: None)
    return w


# ── 1) kayıt açıkken _quit → stop request ───────────────────────────────────
def test_quit_stops_active_recording(monkeypatch):
    w = _quit_window(monkeypatch)
    w._recording = True
    w._stop_recording = _Capture()

    xmpp.MainWindow._quit(w)

    assert w._stop_recording.calls == [((), {"send": False})]
    assert w.root.destroyed is True


# ── 2) oynatma açıkken _quit → stop request + registry temizliği ────────────
def test_quit_requests_active_playback_stop(monkeypatch):
    w = _quit_window(monkeypatch)
    stop = _Capture()
    w._voice_players = {object(): stop}

    xmpp.MainWindow._quit(w)

    assert len(stop.calls) == 1
    assert w._voice_players == {}
    assert w.root.destroyed is True


def test_stop_voice_playback_idempotent(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    stop = _Capture()
    w._voice_players = {object(): stop}

    xmpp.MainWindow._stop_voice_playback(w)
    xmpp.MainWindow._stop_voice_playback(w)

    assert len(stop.calls) == 1


# ── 3) cleanup istisnası _quit'i durdurmaz ──────────────────────────────────
def test_quit_survives_audio_cleanup_exceptions(monkeypatch):
    w = _quit_window(monkeypatch)

    def _boom(**k):
        raise RuntimeError("boom")

    w._recording = True
    w._stop_recording = _boom
    w._voice_players = {object(): _boom}

    xmpp.MainWindow._quit(w)          # istisna dışarı sızmamalı

    assert w.root.destroyed is True


# ── 4) shutdown sonrası kuyruktaki GUI callback'i çalışmaz ──────────────────
class _StrictQ:
    def get_nowait(self):
        raise AssertionError("kapalıyken kuyruk okunmamalı")


def test_poll_skips_queued_ui_callbacks_after_shutdown():
    win = object.__new__(xmpp.MainWindow)
    win._closing = True
    win.gui_q = _StrictQ()
    win.root = types.SimpleNamespace(after=lambda *a: "id")

    xmpp.MainWindow._poll(win)        # AttributeError/AssertionError olmamalı


# ── 5) gerçek oynatıcı: stop isteği pa_stream'i kapatır ─────────────────────
class _W:
    def __init__(self, master=None, **kw):
        self.master = master
        self.kw = dict(kw)
        self.children = []
        self.binds = {}
        self.alive = True
        if isinstance(master, _W):
            master.children.append(self)

    def pack(self, *a, **k):
        pass

    def config(self, **k):
        self.kw.update(k)

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def winfo_exists(self):
        return self.alive

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        self.alive = False

    def delete(self, *a):
        pass

    def create_text(self, *a, **k):
        pass

    def create_rectangle(self, *a, **k):
        pass

    def create_line(self, *a, **k):
        pass


def _all_widgets(w):
    out = [w]
    for c in w.children:
        out.extend(_all_widgets(c))
    return out


def test_stop_voice_playback_closes_active_pyaudio_stream(monkeypatch):
    monkeypatch.setattr(xmpp, "_HAS_PYAUDIO", True)
    gate = threading.Event()

    class _Stream:
        def __init__(self):
            self.stopped = 0
            self.closed = 0
            self.stop_threads = set()

        def write(self, data):
            gate.set()
            time.sleep(0.02)          # ~bir ses parçasının çalma süresi

        def stop_stream(self):
            # Pa_StopStream, bloklu write ile eşzamanlı başka thread'den
            # çağrılırsa write takılır: yalnız oynatma thread'i çağırmalı.
            self.stopped += 1
            self.stop_threads.add(threading.get_ident())

        def close(self):
            self.closed += 1

    stream = _Stream()

    class _PA:
        def get_format_from_width(self, w):
            return 1

        def open(self, **k):
            return stream

        def terminate(self):
            pass

    class _Wave:
        def __init__(self):
            self._chunks = [b"\x00" * 2048] * 500

        def getsampwidth(self):
            return 2

        def getnchannels(self):
            return 1

        def getframerate(self):
            return 44100

        def getnframes(self):
            return 44100

        def readframes(self, n):
            return self._chunks.pop(0) if self._chunks else b""

        def close(self):
            pass

    started = []

    class _T:
        def __init__(self, target=None, daemon=None, args=()):
            self.target, self.args = target, args

        def start(self):
            started.append(self)

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    monkeypatch.setattr(xmpp, "pyaudio", types.SimpleNamespace(PyAudio=_PA))
    monkeypatch.setattr(xmpp.wave, "open", lambda path, mode: _Wave())
    monkeypatch.setattr(xmpp, "tk", types.SimpleNamespace(
        Frame=_W, Label=_W, Canvas=_W))

    w = object.__new__(xmpp.MainWindow)
    w._safe_after = lambda *a, **k: None
    w._load_waveform_bars = lambda path: (0.0, [])
    bubble = _W()

    xmpp.MainWindow._show_voice_waveform(w, bubble, "/tmp/x.wav", xmpp.BG_THEM)

    # Kayıt: kapanışta erişilebilmeli
    assert len(w._voice_players) == 1

    # ▶ butonunu bul ve oynatmayı başlat
    play_btn = next(
        wd for wd in _all_widgets(bubble)
        if wd.kw.get("text") == "▶" and "<Button-1>" in wd.binds)
    play_btn.binds["<Button-1>"][0]()

    play_thread = started[-1]
    t = _RealThread(target=play_thread.target, args=play_thread.args,
                    daemon=True)
    t.start()
    assert gate.wait(3.0), "oynatma başlamadı"

    # Kapanış yetkisi: stop isteği stream'i kapatmalı ve thread'i çözmeli
    xmpp.MainWindow._stop_voice_playback(w)
    t.join(3.0)
    assert not t.is_alive()
    assert stream.stopped >= 1 and stream.closed >= 1
    assert stream.stop_threads == {t.ident}
    assert w._voice_players == {}
