"""Sunucu seçimi ve kapanışta yeniden bağlantı regresyonları."""
import asyncio
import queue
import types

import pytest

import xmpp


def _bot():
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = queue.Queue()
    return bot


def test_reconnect_preserves_custom_server(monkeypatch):
    addresses = []

    def connect(self, host=None, port=None):
        addresses.append((host, port))
        self.custom_address = (host, port) if host and port else None

    monkeypatch.setattr(xmpp.ClientXMPP, "connect", connect)
    bot = _bot()
    bot.connect(host="gateway.example", port=5275)
    bot.connect()

    assert addresses == [("gateway.example", 5275), ("gateway.example", 5275)]


def test_start_honors_nondefault_port_without_server(monkeypatch):
    addresses = []

    class Bot:
        default_domain = "example.com"

        def __init__(self, jid, password, gui_q):
            pass

        def connect(self, host=None, port=None):
            addresses.append((host, port))
            self.loop.call_soon(self.loop.stop)

    monkeypatch.setattr(xmpp, "XMPPBot", Bot)
    monkeypatch.setattr(xmpp, "MainWindow", lambda *a: types.SimpleNamespace(_relogin=False))

    assert xmpp.start("qa@example.com", "dummy", port=5275) is False
    assert addresses == [("example.com", 5275)]


@pytest.mark.parametrize("flag", ["_closing", "_auth_failed"])
def test_delayed_reconnect_rechecks_stop_flags(monkeypatch, flag):
    bot = _bot()
    queued = []
    workers = []
    bot.loop = types.SimpleNamespace(call_soon_threadsafe=lambda cb: queued.append(cb))

    class Thread:
        def __init__(self, target, **kwargs):
            workers.append(target)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", Thread)
    monkeypatch.setattr(xmpp.time, "sleep", lambda seconds: None)
    bot._on_disconnect(None)
    setattr(bot, flag, True)
    workers[0]()

    assert queued == []


def test_disconnect_during_shutdown_does_not_start_worker(monkeypatch):
    bot = _bot()
    bot._closing = True
    workers = []

    class Thread:
        def __init__(self, **kwargs):
            workers.append(kwargs)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", Thread)

    bot._on_disconnect(None)

    assert workers == []


def test_quit_sends_unavailable_and_disconnects_before_stopping_loop(monkeypatch):
    loop = asyncio.new_event_loop()
    bot = _bot()
    bot.loop = loop
    calls = []
    bot.is_connected = lambda: True
    bot.send_presence = lambda **kwargs: calls.append(("presence", kwargs))
    bot.cancel_connection_attempt = lambda: calls.append(("cancel", None))
    bot.abort = lambda: calls.append(("abort", None))

    def disconnect(**kwargs):
        calls.append(("disconnect", kwargs))
        future = loop.create_future()

        def finished():
            calls.append(("disconnected", None))
            future.set_result(None)

        loop.call_soon(finished)
        return future

    bot.disconnect = disconnect
    win = object.__new__(xmpp.MainWindow)
    win.bot = bot
    win._tray_icon = None
    win.active = None
    win._temp_files = []
    win._stop_voice_playback = lambda: None
    win.root = types.SimpleNamespace(destroy=lambda: None)
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: None)
    monkeypatch.setattr(xmpp.threading, "Thread", lambda **kwargs: types.SimpleNamespace(
        start=lambda: None))

    try:
        win._quit()
        loop.run_forever()
        assert ("presence", {"ptype": "unavailable"}) in calls
        assert ("disconnect", {"wait": 1}) in calls
        assert calls.index(("disconnected", None)) < calls.index(("abort", None))
        assert bot._closing is True
    finally:
        xmpp._shutdown_loop(loop)


def test_shutdown_loop_finalizes_async_generators():
    loop = asyncio.new_event_loop()
    finalized = []

    async def stream():
        try:
            yield "message"
        finally:
            finalized.append(True)

    iterator = stream()

    async def first_message():
        return await iterator.__anext__()

    try:
        assert loop.run_until_complete(first_message()) == "message"
        xmpp._shutdown_loop(loop)
        assert finalized == [True]
    finally:
        if not loop.is_closed():
            xmpp._shutdown_loop(loop)
        asyncio.run(iterator.aclose())


def test_conn_timeout_id_hazir_ilk_poll_oncesi():
    """Hızlı sunucuda 'connected' ilk _poll'da işlenir: _conn_timeout_id o
    anda tanımlı olmalı ve bağlıysa zaman aşımı kurulmamalı."""
    import inspect

    src = inspect.getsource(xmpp.MainWindow.__init__)
    assert src.index("self._conn_timeout_id = None") < src.index("self._poll()")
    assert 'if not getattr(self.bot, "_connected_ok", False):' in src
