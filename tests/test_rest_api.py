"""REST API için gerçek loopback HTTP istekleri ve lifecycle regresyonları."""
import asyncio
import http.client
import json
import queue
import socket
import threading
import time
import types
from contextlib import contextmanager

import pytest
from slixmpp import Message

import xmpp


def _window():
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    win.gui_q = queue.Queue()
    win.jid = "qa@example.com"
    win.rooms = []
    win._contacts = {}
    win.presence = {}
    win._last_ping_ms = None
    win.sent = []
    win.bot = types.SimpleNamespace(
        is_connected=lambda: True,
        send_chat=lambda to, body: win.sent.append((to, body)),
        send_gc=lambda to, body: win.sent.append((to, body)))
    win._safe_after = lambda *args: None
    win._show_toast = lambda *args: None
    win.generated_tokens = []

    def token():
        win._api_token = f"test-token-{len(win.generated_tokens) + 1}"
        win.generated_tokens.append(win._api_token)
        return win._api_token

    win._generate_api_token = token
    return win


@pytest.fixture()
def api(monkeypatch):
    win = _window()
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"webhooks": [
        {"key": "known-key", "target": "peer@example.com", "enabled": True}]})
    monkeypatch.setattr(xmpp, "_API_REQUEST_TIMEOUT", 0.1, raising=False)
    win._start_rest_api(0)
    deadline = time.monotonic() + 5
    try:
        while getattr(win, "_api_server", None) is None:
            if getattr(win, "_api_error", None):
                pytest.fail(win._api_error)
            assert time.monotonic() < deadline, "REST API başlamadı"
            time.sleep(0.005)
        yield win
    finally:
        win._stop_api_server()


def _post(win, body=b"{}", *, path="/api/send", headers=None):
    host, port = win._api_server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=1)
    auth = {"Authorization": f"Bearer {win._api_token}"}
    auth.update(headers or {})
    try:
        conn.request("POST", path, body=body, headers=auth)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    except (http.client.RemoteDisconnected, TimeoutError, ConnectionResetError) as exc:
        return None, str(exc)
    finally:
        conn.close()


def test_normal_send_remains_available_after_invalid_request(api):
    assert _post(api, b"not-json")[0] == 400
    status, payload = _post(api, b'{"to":"peer@example.com","message":"merhaba"}')

    assert status == 200
    assert payload == {"status": "sent"}
    assert api.sent == [("peer@example.com", "merhaba")]


@pytest.mark.parametrize("body", [b"[]", b"null", b'"message"', b"42"])
def test_non_object_json_returns_bad_request(api, body):
    assert _post(api, body)[0] == 400
    assert api.sent == []


@pytest.mark.parametrize("body", [
    b'{"to":42,"message":"hi"}',
    b'{"to":"peer@example.com","message":["hi"]}',
    b'{"to":"   ","message":"hi"}',
    b'{"to":"peer@example.com","message":"   "}',
])
def test_invalid_send_fields_are_not_forwarded(api, body):
    assert _post(api, body)[0] == 400
    assert api.sent == []


@pytest.mark.parametrize("length,status", [("invalid", 400), ("-1", 400), ("1048577", 413)])
def test_invalid_content_length_returns_http_error(api, length, status):
    assert _post(api, headers={"Content-Length": length})[0] == status


def test_incomplete_body_times_out_with_http_error(api):
    assert _post(api, headers={"Content-Length": "200"})[0] == 408


def test_missing_bot_returns_service_unavailable(api):
    api.bot = None
    assert _post(api, b'{"to":"peer@example.com","message":"hi"}')[0] == 503


def test_failed_send_returns_service_unavailable(api):
    def failed_send(to, message):
        raise RuntimeError("Event loop is closed")

    api.bot.send_chat = failed_send
    assert _post(api, b'{"to":"peer@example.com","message":"hi"}')[0] == 503
    assert api.gui_q.empty()


def test_webhook_non_object_json_returns_bad_request(api):
    assert _post(api, b"[]", path="/api/webhook/known-key")[0] == 400
    assert api.sent == []


def test_webhook_plaintext_fallback_is_preserved(api):
    status, payload = _post(api, "selam dünya".encode(), path="/api/webhook/known-key")

    assert status == 200
    assert payload == {"status": "delivered", "to": "peer@example.com"}
    assert api.sent == [("peer@example.com", "🔔 [webhook] selam dünya")]


def test_second_start_does_not_rotate_running_api_token(api):
    token = api._api_token
    api._start_rest_api(api._api_server.server_address[1])

    assert api.generated_tokens == [token]


def test_stop_clears_server_state_and_releases_port(api):
    address = api._api_server.server_address
    api._stop_api_server()

    assert getattr(api, "_api_server", None) is None
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(address)


def test_stop_before_startup_finishes_prevents_server_publication(monkeypatch):
    win = _window()
    workers = []
    calls = []

    class Thread:
        def __init__(self, target, **kwargs):
            workers.append(target)

        def start(self):
            pass

    class Server:
        server_address = ("127.0.0.1", 8099)

        def __init__(self, *args):
            pass

        def serve_forever(self):
            calls.append("serve")

        def server_close(self):
            calls.append("close")

    monkeypatch.setattr(xmpp.threading, "Thread", Thread)
    monkeypatch.setattr(xmpp.http.server, "HTTPServer", Server)
    win._start_rest_api()
    win._stop_api_server()
    workers[0]()

    assert calls == ["close"]
    assert getattr(win, "_api_server", None) is None


def test_bound_canceled_startup_is_closed_before_restart(monkeypatch):
    win = _window()
    bound = threading.Event()
    release = threading.Event()
    servers = []
    workers = []
    real_server = xmpp.http.server.HTTPServer
    real_thread = threading.Thread

    def server(*args):
        instance = real_server(*args)
        servers.append(instance)
        bound.set()
        assert release.wait(2)
        return instance

    def thread(*args, **kwargs):
        instance = real_thread(*args, **kwargs)
        workers.append(instance)
        return instance

    monkeypatch.setattr(xmpp.http.server, "HTTPServer", server)
    monkeypatch.setattr(xmpp.threading, "Thread", thread)
    try:
        win._start_rest_api(0)
        assert bound.wait(1)
        port = servers[0].server_address[1]
        win._stop_api_server()
        win._start_rest_api(port)
        assert len(win.generated_tokens) == 1  # Port henüz eski worker'ın sahipliğinde.
        release.set()
        workers[0].join(timeout=2)
        assert not workers[0].is_alive()
        assert getattr(win, "_api_server", None) is None
        monkeypatch.setattr(xmpp.http.server, "HTTPServer", real_server)
        win._start_rest_api(port)
        deadline = time.monotonic() + 2
        while getattr(win, "_api_server", None) is None:
            assert time.monotonic() < deadline
            time.sleep(0.005)
        assert win._api_error is None
        assert win._api_server.server_address[1] == port
    finally:
        release.set()
        deadline = time.monotonic() + 2
        while (getattr(win, "_api_server", None) is None
               and any(worker.is_alive() for worker in workers)
               and time.monotonic() < deadline):
            time.sleep(0.005)
        win._stop_api_server()
        for worker in workers:
            worker.join(timeout=2)
        for instance in servers:
            instance.server_close()


def test_trickling_body_has_absolute_deadline_and_cannot_hold_shutdown(api, monkeypatch):
    accepted = threading.Event()
    handler = api._api_server.RequestHandlerClass
    real_setup = handler.setup

    def setup(self):
        real_setup(self)
        accepted.set()

    monkeypatch.setattr(handler, "setup", setup)
    host, port = api._api_server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=1)
    conn.putrequest("POST", "/api/send")
    conn.putheader("Authorization", f"Bearer {api._api_token}")
    conn.putheader("Content-Length", "1000")
    conn.endheaders()
    conn.send(b"x")
    assert accepted.wait(1)
    done = threading.Event()
    stopped = threading.Event()

    def trickle():
        while not done.wait(0.02):
            try:
                conn.send(b"x")
            except OSError:
                break

    def stop_api():
        api._stop_api_server()
        stopped.set()

    sender = threading.Thread(target=trickle, daemon=True)
    stopper = threading.Thread(target=stop_api, daemon=True)
    sender.start()
    stopper.start()
    try:
        try:
            response = conn.getresponse()
            status = response.status
            response.read()
        except TimeoutError:
            status = None
        assert status == 408
        assert stopped.wait(1)
    finally:
        done.set()
        sender.join(timeout=1)
        conn.close()
        stopper.join(timeout=2)


@contextmanager
def _async_bot(api):
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    loop.call_soon(ready.set)
    worker = threading.Thread(target=loop.run_forever, daemon=True)
    worker.start()
    assert ready.wait(1)
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.loop = loop
    bot.gui_q = api.gui_q
    api.bot = bot
    try:
        yield bot
    finally:
        loop.call_soon_threadsafe(loop.stop)
        worker.join(timeout=2)
        xmpp._shutdown_loop(loop)


@pytest.mark.parametrize("groupchat", [False, True])
def test_real_async_send_failure_is_not_reported_or_stored_as_success(api, groupchat):
    with _async_bot(api) as bot:
        if groupchat:
            api.rooms = ["peer@example.com"]

        def failed_message(**kwargs):
            raise RuntimeError("stanza oluşturulamadı")

        bot.make_message = failed_message
        assert _post(api, b'{"to":"peer@example.com","message":"hi"}')[0] == 503
        kinds = [kind for kind, _data in list(api.gui_q.queue)]
        assert "error" in kinds
        assert "api_store" not in kinds


def test_real_async_send_success_returns_http_success(api):
    with _async_bot(api) as bot:
        sent = []

        def message(**kwargs):
            stanza = Message()
            stanza["body"] = kwargs["mbody"]
            stanza.send = lambda: sent.append(stanza["body"])
            return stanza

        bot.make_message = message
        assert _post(api, b'{"to":"peer@example.com","message":"hi"}')[0] == 200
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), bot.loop).result(timeout=1)
        assert sent == ["hi"]
        assert "api_store" in [kind for kind, _data in list(api.gui_q.queue)]


def test_async_send_timeout_does_not_create_history_record(api, monkeypatch):
    monkeypatch.setattr(xmpp, "_API_SEND_TIMEOUT", 0.1, raising=False)
    with _async_bot(api) as bot:
        bot._send_chat = lambda *args: asyncio.sleep(10)
        assert _post(api, b'{"to":"peer@example.com","message":"hi"}')[0] == 503
        assert "api_store" not in [kind for kind, _data in list(api.gui_q.queue)]


@pytest.mark.parametrize("groupchat", [False, True])
def test_closed_xmpp_loop_returns_error_without_leaking_coroutine(api, groupchat):
    loop = asyncio.new_event_loop()
    loop.close()
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.loop = loop
    bot.gui_q = api.gui_q
    api.bot = bot
    if groupchat:
        api.rooms = ["peer@example.com"]

    assert _post(api, b'{"to":"peer@example.com","message":"hi"}')[0] == 503
    assert api.gui_q.empty()
