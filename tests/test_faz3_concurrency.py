"""Faz 3 concurrency/lifecycle regression ağları.

Kapsam: P0-1 (SQLite çapraz-thread), P0-2 (webhook/API _store kuyruk
bypass), P1-1 (reconnect/retry yabancı thread loop erişimi), P1-2
(GUI thread'inden senkron send), P1-6a (ses kareleri yarışı).
"""

import asyncio
import inspect
import os
import re
import sys
import threading
import time
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


class _Q:
    def __init__(self, items=None):
        self.items = list(items or [])

    def put(self, item):
        self.items.append(item)


class _FakeLoop:
    def __init__(self):
        self.soon = []

    def call_soon_threadsafe(self, cb, *a):
        self.soon.append((cb, a))


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


# ── P0-1: SQLite çapraz-thread ───────────────────────────────────────────────

def test_db_cross_thread_stress_writes_all_persist(tmp_db):
    """8 çalışan thread'den eşzamanlı yazım; hiçbir kayıp/yutma olmamalı."""
    def _worker(i):
        for k in range(25):
            xmpp._db_store_msg("a@b.c", f"t{i}", f"m{i}-{k}", False,
                               "10:00", "them")

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = xmpp._db_load_msgs("a@b.c")
    assert len(rows) == 200
    assert all(r[1].startswith("m") for r in rows)


# ── P0-2: webhook/API _store kuyruk bypass ──────────────────────────────────

def test_api_store_event_calls_store_with_mapped_args():
    win = object.__new__(xmpp.MainWindow)
    calls = []

    def _store(*a, **k):
        calls.append((a, k))

    win._store = _store
    win._handle("api_store", {"target": "a@b.c", "body": "selam",
                              "tag": "them", "sender": "🔔 bot"})
    assert len(calls) == 1
    a, k = calls[0]
    assert a[0] == "a@b.c" and a[1] == "selam"
    assert k["tag"] == "them" and k["sender"] == "🔔 bot"


def test_api_store_event_is_me_passthrough():
    win = object.__new__(xmpp.MainWindow)
    calls = []
    win._store = lambda *a, **k: calls.append((a, k))
    win._handle("api_store", {"target": "a@b.c", "body": "x",
                              "tag": "me", "sender": "API", "is_me": True})
    assert calls[0][1]["is_me"] is True


def test_webhook_api_direct_store_call_removed():
    with open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "xmpp.py"), encoding="utf-8") as f:
        src = f.read()
    assert "main_win._store(" not in src


# ── P1-1: reconnect / retry thread-safety ───────────────────────────────────

def test_reconnect_schedules_connect_on_loop(monkeypatch):
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = _Q()
    bot.omemo_ready = False
    bot._connected_ok = False
    bot._auth_failed = False
    bot._reconnect_delay = 2
    fake = _FakeLoop()
    bot.loop = fake
    scheduled = []

    class _T:
        def __init__(self, target=None, **k):
            self.target = target

        def start(self):
            scheduled.append(self.target)

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    monkeypatch.setattr(xmpp.time, "sleep", lambda s: None)
    xmpp.XMPPBot._on_disconnect(bot, None)
    assert len(scheduled) == 1
    scheduled[0]()
    assert len(fake.soon) == 1
    cb, args = fake.soon[0]
    assert cb == bot.connect and args == ()


def test_reconnect_dedupe_guard(monkeypatch):
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = _Q()
    bot._connected_ok = False
    bot._auth_failed = False
    bot._reconnect_delay = 2
    fake = _FakeLoop()
    bot.loop = fake
    scheduled = []

    class _T:
        def __init__(self, target=None, **k):
            self.target = target

        def start(self):
            scheduled.append(self.target)

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    monkeypatch.setattr(xmpp.time, "sleep", lambda s: None)
    xmpp.XMPPBot._on_disconnect(bot, None)
    xmpp.XMPPBot._on_disconnect(bot, None)
    assert len(scheduled) == 1
    scheduled[0]()
    assert len(fake.soon) == 1
    xmpp.XMPPBot._on_disconnect(bot, None)
    assert len(scheduled) == 2


def test_retry_connection_schedules_on_loop(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot._connected_ok = False
    fake = _FakeLoop()
    bot.loop = fake
    cancels = []
    bot.cancel_connection_attempt = lambda: cancels.append(1)
    win.bot = bot
    win._show_toast = lambda *a, **k: None
    win._append = lambda *a, **k: None
    win._status_label = types.SimpleNamespace(config=lambda **k: None)
    monkeypatch.setattr(xmpp.messagebox, "showerror", lambda *a, **k: None)
    xmpp.MainWindow._retry_connection(win, None)
    assert cancels == []
    assert [cb for cb, _ in fake.soon] == [bot.cancel_connection_attempt,
                                           bot.connect]


# ── P1-2: GUI thread'inden senkron send ─────────────────────────────────────

_SYNC_SENDS = [
    ("send_chatstate", ("a@b.c", "composing")),
    ("send_marker", ("a@b.c", "m1")),
    ("send_reaction", ("a@b.c", "m1", {"👍"})),
    ("forward_message", ("a@b.c", "x@y", "gövde")),
    ("set_presence", ("dnd", "meşgul")),
    ("approve_subscribe", ("a@b.c", True)),
    ("set_room_subject", ("r@conf", "konu")),
    ("invite_to_room", ("r@conf", "a@b.c")),
    ("set_status_message", ("durum",)),
]


@pytest.mark.parametrize("name,args", _SYNC_SENDS)
def test_sync_sends_scheduled_on_loop(name, args):
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = _Q()
    fake = _FakeLoop()
    bot.loop = fake

    def _yasak(*a, **k):
        raise AssertionError("çağıran thread'de send yolu çalıştı")

    bot.make_message = _yasak
    bot.send_presence = _yasak
    bot.send_presence_subscription = _yasak
    getattr(xmpp.XMPPBot, name)(bot, *args)
    assert len(fake.soon) == 1, name


def test_sync_send_falls_back_direct_when_loop_yok():
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = _Q()
    assert not hasattr(bot, "loop")
    xmpp.XMPPBot.send_chatstate(bot, "a@b.c", "composing")
    assert bot.gui_q.items == []


def test_ping_loop_schedules_ping_on_loop(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    fake = _FakeLoop()
    bot.loop = fake
    bot.is_connected = lambda: True
    pings = []
    bot.plugin = {"xep_0199": types.SimpleNamespace(
        send_ping=lambda *a, **k: pings.append((a, k)))}
    bot.boundjid = types.SimpleNamespace(domain="example.com")
    win.bot = bot
    win._closing = False
    win._after = lambda *a, **k: None
    win._update_ping_label = lambda: None
    xmpp.MainWindow._ping_loop(win)
    assert pings == []
    assert len(fake.soon) == 1


# ── P1-6a: ses kareleri yarışı ──────────────────────────────────────────────

def test_voice_frames_join_is_locked_snapshot():
    win = object.__new__(xmpp.MainWindow)
    win._voice_lock = threading.Lock()
    win._voice_frames = []
    stop = threading.Event()

    def _worker():
        while not stop.is_set():
            with win._voice_lock:
                win._voice_frames.append(b"x" * 10)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    total = 0
    for _ in range(50):
        total += len(win._join_voice_frames())
        time.sleep(0.001)
    stop.set()
    t.join(timeout=2)
    final = len(win._join_voice_frames())
    assert (total + final) % 10 == 0
    assert final % 10 == 0


# ── P1-1b: _dispatch_loop loop thread'inde yeniden planlamamalı ─────────────

def test_dispatch_loop_runs_directly_on_loop_thread(monkeypatch):
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    fake = _FakeLoop()
    bot.loop = fake
    ran = []
    monkeypatch.setattr(xmpp.asyncio, "get_running_loop", lambda: fake)
    bot._dispatch_loop(lambda: ran.append(1))
    assert ran == [1]          # aynı loop thread'inde doğrudan çalıştı
    assert fake.soon == []     # gereksiz yeniden planlama yok


# ── P1-3: worker → Tk köprüsü (kuyruk tabanlı) ──────────────────────────────

class _RootAfter:
    def __init__(self):
        self.calls = []

    def after(self, ms, cb, *a):
        self.calls.append((ms, cb, a))
        return "id1"


def test_safe_after_main_thread_uses_root_after():
    win = object.__new__(xmpp.MainWindow)
    win.gui_q = _Q()
    root = _RootAfter()
    win.root = root

    win._safe_after(0, lambda: None)

    assert len(root.calls) == 1
    assert win.gui_q.items == []


def test_safe_after_worker_thread_uses_gui_q():
    win = object.__new__(xmpp.MainWindow)
    win.gui_q = _Q()
    win.root = _RootAfter()
    seen = []

    def _worker():
        win._safe_after(0, seen.append, 42)

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    assert seen == []  # worker thread'inde Tk çağrılmadı
    assert win.root.calls == []
    kind, data = win.gui_q.items[0]
    assert kind == "__ui__"
    fn, args = data
    assert callable(fn) and args == (42,)


def test_handle_ui_event_runs_callable():
    win = object.__new__(xmpp.MainWindow)
    called = []
    win._handle("__ui__", (called.append, (7,)))
    assert called == [7]


_WORKER_NO_TK = [
    (xmpp.MainWindow._image_fetch_worker,
     ("self.root.after(", "ImageTk.PhotoImage"), "_safe_after"),
    (xmpp.MainWindow._audio_fetch_worker, ("self.root.after(",
                                           "ImageTk.PhotoImage"),
     "_safe_after"),
    (xmpp.MainWindow._preview_fetch_worker, ("self.root.after(",
                                             "ImageTk.PhotoImage"),
     "_safe_after"),
    (xmpp.MainWindow._load_gif_thumb, ("self.root.after(",), "_safe_after"),
    (xmpp.MainWindow._show_image_fullscreen, ("top.after(",), "_safe_after"),
    (xmpp.MainWindow._start_recording, ("self.root.after(",), "_safe_after"),
    (xmpp.MainWindow._stop_recording, ("self.root.after(", "_process_audio"),
     "_finalize_recording"),
    (xmpp.MainWindow._show_voice_waveform,
     ("self.root.after(", "struct.unpack"), "_safe_after"),
    (xmpp.MainWindow._gif_search, ("self.root.after(",), "_safe_after"),
    (xmpp.MainWindow._start_rest_api, ("self.root.after(",), "_safe_after"),
    # GUI-thread odak `dlg.after(50, ...)` meşru; worker fetch yolu _safe_after
    (xmpp.MainWindow._search_rooms_dialog, (), None),
    (xmpp.MainWindow._search_rooms_requested,
     ("dlg.after(", "self.root.after(", "status_lbl.config("), "_safe_after"),
    # XMPP filter'ları (log izleme) loop thread'inde çalışır
    (xmpp.MainWindow._log_viewer_dialog, ("dlg.after(", "self.root.after("),
     "_safe_after"),
]


@pytest.mark.parametrize("fn,forbidden,required", _WORKER_NO_TK,
                         ids=[f.__name__ for f, _, _ in _WORKER_NO_TK])
def test_worker_fonksiyonlari_dogrudan_tk_cagirmaz(fn, forbidden, required):
    src = inspect.getsource(fn)
    for token in forbidden:
        assert token not in src, f"{fn.__name__} içinde yasaklı: {token}"
    if required is not None:
        assert required in src, f"{fn.__name__} {required} kullanmıyor"


def test_player_state_locked():
    src = inspect.getsource(xmpp.MainWindow._show_voice_waveform)
    assert "state_lock" in src, "oynatıcı state kilitsiz görünüyor"


def test_playback_generation_guard():
    """Eski playback thread cleanup'ı yeni oturumun state'ini ezmemeli.

    Faz 4-0A: pause → yeniden ▶ yarışında eski thread'in cleanup'ı
    yeni thread'in playing/stop state'ini sıfırlamamalı (generation).
    """
    src = inspect.getsource(xmpp.MainWindow._show_voice_waveform)
    assert '"gen"' in src, "playback generation sayacı yok"
    assert "my_gen" in src, "thread kendi generation değerini taşımıyor"
    assert "!= my_gen" in src, "cleanup generation kontrolü yok"


def test_waveform_renkleri_tk_uyumlu():
    """Tk 8.6 `#RRGGBBAA` (8 haneli RGBA) kabul etmez.

    Runtime hatası: `invalid color name "#6366f180"` — dalga formu
    çiziminde 6 haneli renk kullanılmalı.
    """
    src = inspect.getsource(xmpp.MainWindow._show_voice_waveform)
    bad = re.findall(r"#[0-9a-fA-F]{8}\b", src)
    assert bad == [], f"Tk uyumsuz 8 haneli renk(ler): {bad}"


def test_recording_ready_hedefi_sabit_tutar():
    win = object.__new__(xmpp.MainWindow)
    win.active = "baska@b.c"          # işlem sırasında sohbet değişti
    win.rooms = []
    win._chat_enc_modes = {}
    win._temp_files = []
    calls = []
    win.bot = types.SimpleNamespace(
        send_file=lambda to, path, mtype, encryption="none": calls.append(
            (to, path, mtype)))
    win._show_sent_voice = lambda path, target=None: calls.append(
        ("show", target))

    win._on_recording_ready("/tmp/x.wav", "hedef@b.c")

    assert calls[0] == ("hedef@b.c", "/tmp/x.wav", "chat")
    assert calls[1] == ("show", "hedef@b.c")


def test_show_sent_voice_hedef_degistiyse_cizmez():
    win = object.__new__(xmpp.MainWindow)
    win.active = "b@c.d"
    calls = []
    win._store = lambda *a, **k: calls.append((a, k))

    win._show_sent_voice("/tmp/x.wav", "a@b.c")  # Tk'ya dokunmadan dönmeli

    assert calls and calls[0][0][0] == "a@b.c"


# ── P2-2: kapanış sırası / lifecycle ────────────────────────────────────────

class _CaptureThread:
    started = []

    def __init__(self, target=None, daemon=None, args=()):
        self.target = target
        self.args = args

    def start(self):
        _CaptureThread.started.append((self.target, self.args))


def test_quit_stops_api_server(monkeypatch):
    _CaptureThread.started = []
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    win._tray_icon = None
    win._temp_files = []
    win.active = None
    win._after_ids = set()
    for attr in ("_poll_id", "_idle_check_id", "_ping_loop_id",
                 "_conn_timeout_id", "_auto_theme_id",
                 "_typing_anim_id", "_typing_send_id"):
        setattr(win, attr, None)
    calls = []

    class _Tk:
        def setvar(self, k, v):
            pass

        def splitlist(self, s):
            return s

        def call(self, *a):
            return ""

    class _Root:
        tk = _Tk()

        def after_cancel(self, i):
            pass

        def winfo_geometry(self):
            return "800x600+0+0"

        def state(self):
            return "normal"

        def destroy(self):
            calls.append("destroy")

    win.root = _Root()
    win.bot = None
    win._api_server = types.SimpleNamespace(
        shutdown=lambda: calls.append("shutdown"),
        server_close=lambda: calls.append("server_close"))
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: None)
    monkeypatch.setattr(xmpp, "_cleanup_temp_files", lambda files: None)
    monkeypatch.setattr(xmpp.threading, "Thread", _CaptureThread)

    xmpp.MainWindow._quit(win)

    assert "destroy" in calls
    api_targets = [t for t, _ in _CaptureThread.started
                   if getattr(t, "__name__", "") == "_stop_api_server"]
    assert len(api_targets) == 1
    api_targets[0]()
    assert "shutdown" in calls
    assert "server_close" in calls


def test_shutdown_loop_cancels_pending_tasks():
    loop = asyncio.new_event_loop()
    task = loop.create_task(asyncio.sleep(30))
    loop.run_until_complete(asyncio.sleep(0))  # görev başlasın

    xmpp._shutdown_loop(loop)

    assert loop.is_closed()
    assert task.cancelled()
