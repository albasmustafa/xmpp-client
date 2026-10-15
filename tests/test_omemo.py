"""OMEMO gönderim/alım yolları için ağsız (mock'lu) testler."""

import asyncio
import os
import queue
import sys

from slixmpp import JID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


class _Queue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


class _FakeStanza:
    def __init__(self):
        self.eme = {}
        self.sent = False

    def __setitem__(self, key, value):
        if key == "eme":
            self.eme = value
        else:
            setattr(self, key, value)

    def __getitem__(self, key):
        if key == "eme":
            return self.eme
        return getattr(self, key)

    def set_to(self, to):
        self.to = to

    def set_from(self, frm):
        self.frm = frm

    def send(self):
        self.sent = True


class _FakeEme:
    mechanisms = {"eu.siacs.conversations.axolotl": "Legacy OMEMO"}


class _FakeOmemoXep:
    def __init__(self, result=None, error=None, namespaces=None):
        self.result = result
        self.error = error
        self.namespaces = (namespaces if namespaces is not None
                           else {"eu.siacs.conversations.axolotl"})
        self.calls = []

    async def refresh_device_lists(self, recipients, force_download=False):
        self.refresh_calls = getattr(self, "refresh_calls", 0) + 1

    async def encrypt_message(self, stanza, recipients, identifier=None):
        self.calls.append((stanza, set(recipients)))
        if self.error:
            raise self.error
        return self.result, frozenset()

    def is_encrypted(self, stanza):
        return set(self.namespaces)


class _FakeBot:
    def __init__(self, xep):
        self._xep = xep
        self.boundjid = JID("ben@example.com/kaynak")
        self.gui_q = _Queue()
        self.rooms = []                    # [2P] _send_omemo recipients yolu
        self.my_nicks = {}
        self.sent_plain = []
        self.made_messages = []
        # [2P-BUG A] üretim _send_omemo wrapper'ı _send_omemo_locked'i
        # çağırır; gerçek üretim gövdesini bu çifte bağla (bypass yok).
        from types import MethodType
        self._send_omemo_locked = MethodType(
            xmpp.XMPPBot._send_omemo_locked, self)

    def __getitem__(self, name):
        if name == "xep_0384":
            return self._xep
        if name == "xep_0380":
            return _FakeEme()
        raise KeyError(name)

    def make_message(self, mto=None, mtype=None, mbody=None):
        st = _FakeStanza()
        st.to = mto
        st.type = mtype
        st.body = mbody
        self.made_messages.append(st)
        return st

    def send_message(self, mto=None, mbody=None, mtype=None):
        self.sent_plain.append((mto, mbody, mtype))


class _FakeXml:
    def find(self, tag):
        return None


class _FakeMsg:
    def __init__(self, body="", mtype="chat"):
        self._data = {"type": mtype, "body": body, "id": "mid1"}
        self.xml = _FakeXml()

    def __getitem__(self, key):
        if key == "from":
            return JID("ali@example.com/kaynak")
        return self._data[key]


def test_send_omemo_success():
    enc = _FakeStanza()
    xep = _FakeOmemoXep(result=enc)
    bot = _FakeBot(xep)

    asyncio.run(xmpp.XMPPBot._send_omemo(
        bot, "ali@example.com", "merhaba", "chat"))

    assert enc.sent
    assert enc.eme["namespace"] == "eu.siacs.conversations.axolotl"
    assert enc.eme["name"] == "Legacy OMEMO"
    assert bot.sent_plain == []
    assert len(xep.calls) == 1


def test_send_omemo_none_falls_back_to_plaintext():
    xep = _FakeOmemoXep(result=None)
    bot = _FakeBot(xep)

    asyncio.run(xmpp.XMPPBot._send_omemo(
        bot, "ali@example.com", "merhaba", "chat"))

    assert bot.sent_plain == []
    # ilk stanza şifreleme denemesi, ikincisi düz metin yedeği
    assert len(bot.made_messages) == 2
    assert not bot.made_messages[0].sent
    assert bot.made_messages[-1].sent
    assert any(kind == "error" for kind, _ in bot.gui_q.items)


def test_send_omemo_error_reports():
    xep = _FakeOmemoXep(error=RuntimeError("bundle alınamadı: device yok"))
    bot = _FakeBot(xep)

    asyncio.run(xmpp.XMPPBot._send_omemo(
        bot, "ali@example.com", "merhaba", "chat"))

    assert bot.sent_plain == []
    assert any(kind == "error" for kind, _ in bot.gui_q.items)


def test_on_message_routes_omemo(monkeypatch):
    calls = []

    async def _fake_decrypt(self, msg, mtype):
        calls.append((msg, mtype))

    monkeypatch.setattr(xmpp.XMPPBot, "_decrypt_and_deliver", _fake_decrypt)
    monkeypatch.setattr(
        xmpp.XMPPBot, "__getitem__",
        lambda self, name: self._xep if name == "xep_0384" else None)

    async def _run():
        bot = xmpp.XMPPBot("test@example.com", "pw", queue.Queue())
        bot._xep = _FakeOmemoXep()
        bot.plugin = None  # _get_xep, __getitem__ yamasına düşsün
        bot.gui_q = _Queue()
        xmpp.XMPPBot._on_message(bot, _FakeMsg(body="gizli"))
        await asyncio.sleep(0)
        return bot

    bot = asyncio.run(_run())
    assert calls and calls[0][1] == "chat"
    assert bot.gui_q.items == []


def test_on_message_plain_not_routed(monkeypatch):
    calls = []

    async def _fake_decrypt(self, msg, mtype):
        calls.append((msg, mtype))

    monkeypatch.setattr(xmpp.XMPPBot, "_decrypt_and_deliver", _fake_decrypt)
    monkeypatch.setattr(
        xmpp.XMPPBot, "__getitem__",
        lambda self, name: self._xep if name == "xep_0384" else None)

    async def _run():
        bot = xmpp.XMPPBot("test@example.com", "pw", queue.Queue())
        bot._xep = _FakeOmemoXep(namespaces=set())
        bot.plugin = None  # _get_xep, __getitem__ yamasına düşsün
        bot.gui_q = _Queue()
        xmpp.XMPPBot._on_message(bot, _FakeMsg(body="açık mesaj"))
        await asyncio.sleep(0)
        return bot

    bot = asyncio.run(_run())
    assert calls == []
    assert len(bot.gui_q.items) == 1
    kind, data = bot.gui_q.items[0]
    assert kind == "msg"
    assert data["body"] == "açık mesaj"
