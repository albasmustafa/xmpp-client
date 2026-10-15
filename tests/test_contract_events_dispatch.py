"""GUI kuyruğu, XMPP olay dağıtımı ve gelen mesaj ayrıştırma sözleşmeleri.

Refactor regression ağı: Faz 2'de (bot mixin'leri) ve Faz 3'te (UI)
olay kayıt tablosu, gui_q tüketim sözleşmesi ve gelen mesaj
payload'larının değişmemesi gerekir. Testler Tk penceresi açmadan
object.__new__ ve sahte stanza'larla çalışır.
"""

import asyncio
import os
import sys
import types
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp.plugins.base import PluginManager  # noqa: E402

import xmpp  # noqa: E402


class _Q:
    def __init__(self, items=None):
        self.items = list(items or [])

    def put(self, item):
        self.items.append(item)

    def get_nowait(self):
        if not self.items:
            raise xmpp.queue.Empty
        return self.items.pop(0)


def _bot_stub():
    bot = object.__new__(xmpp.XMPPBot)
    bot.gui_q = _Q()
    bot._run_out_filters = None  # XMLStream.__del__ gürültüsünü sustur
    # [2Q] Gerçek PluginManager: _get_xep artık desteklenen .plugin yolunu
    # kullanır; deprecated obj[name] yolu (DeprecationWarning) yerine.
    bot.plugin = PluginManager(bot)
    # [2P-BUG B] _on_message artık yutulan OMEMO denetim hatalarını loglar
    bot.log = types.SimpleNamespace(warning=lambda *a, **k: None)
    return bot


class _Cell:
    def __init__(self, value):
        self.value = value

    def __getitem__(self, key):
        return self.value


class _FakeMsg:
    """slixmpp mesajı gibi davranan asgari sahte nesne."""

    def __init__(self, body="", frm="ali@example.com/kaynak", mtype="chat",
                 origin=None, stanza_id=None, mid="", xml=None):
        self._data = {"type": mtype, "body": body, "id": mid,
                      "origin_id": {"id": origin},
                      "stanza_id": {"id": stanza_id}}
        self._from = frm
        self.xml = xml if xml is not None else ET.Element("message")

    def __getitem__(self, key):
        if key == "from":
            from slixmpp import JID
            return JID(self._from)
        if key in ("origin_id", "stanza_id"):
            return _Cell(self._data[key]["id"])
        if key == "reply":
            raise KeyError(key)
        if key == "oob":
            raise KeyError(key)
        return self._data[key]


# ── GUI kuyruğu: _poll sözleşmesi (xmpp.py:11530-11549) ─────────────────────

class _Root:
    def __init__(self):
        self.after_calls = []

    def after(self, ms, cb):
        self.after_calls.append((ms, cb))
        return f"id{len(self.after_calls)}"


def test_poll_kuyrugu_sirayla_tuketir_ve_yeniden_planlar():
    """Mevcut davranış: _poll tüm olayları get_nowait ile boşaltır,
    _handle'a sırayla verir ve 100 ms sonra kendini yeniden planlar."""
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    win.gui_q = _Q([("a", 1), ("b", 2), ("c", 3)])
    handled = []
    win._handle = lambda kind, data: handled.append((kind, data))
    root = _Root()
    win.root = root

    xmpp.MainWindow._poll(win)

    assert handled == [("a", 1), ("b", 2), ("c", 3)]
    assert [ms for ms, _ in root.after_calls] == [100]
    assert win._poll_id == "id1"


def test_poll_bos_kuyrukta_da_yeniden_planlar():
    """Mevcut davranış: boş kuyruk istisna sızdırmaz, zincir devam eder."""
    win = object.__new__(xmpp.MainWindow)
    win._closing = False
    win.gui_q = _Q()
    win._handle = lambda kind, data: None
    root = _Root()
    win.root = root

    xmpp.MainWindow._poll(win)

    assert [ms for ms, _ in root.after_calls] == [100]


def test_poll_kapanista_yeniden_planlamaz():
    """Mevcut davranış: _closing True iken _poll hiç iş yapmaz ve
    yeni after zinciri kurmaz."""
    win = object.__new__(xmpp.MainWindow)
    win._closing = True
    win.gui_q = _Q([("a", 1)])
    win._handle = lambda kind, data: (_ for _ in ()).throw(
        AssertionError("kapanışta _handle çağrılmamalı"))
    root = _Root()
    win.root = root

    xmpp.MainWindow._poll(win)

    assert root.after_calls == []
    assert win._poll_id is None


# ── XMPP olay dağıtım tablosu (xmpp.py:1701-1727) ───────────────────────────

def _expected_handlers(with_omemo=True):
    table = {
        "session_start": "_on_start",
        "message": "_on_message",
        "groupchat_message": "_on_gc_message",
        "changed_status": "_on_presence",
        "failed_auth": "_on_auth_fail",
        "disconnected": "_on_disconnect",
        "chatstate_composing": "_on_typing_start",
        "chatstate_paused": "_on_typing_stop",
        "chatstate_active": "_on_typing_stop",
        "chatstate_gone": "_on_typing_stop",
        "chatstate_inactive": "_on_typing_stop",
        "groupchat_invite": "_on_muc_invite",
        "groupchat_direct_invite": "_on_muc_invite",
        "groupchat_presence": "_on_muc_presence",
        "groupchat_subject": "_on_muc_subject",
        "presence_subscribe": "_on_subscribe_req",
        "presence_subscribed": "_on_subscribed",
        "presence_unsubscribed": "_on_unsubscribed",
        "connected": "_on_tcp_connected",
        "connection_failed": "_on_conn_fail",
        "encrypted_message": "_on_pgp_message",
        "marker_displayed": "_on_marker_displayed",
        "message_correction": "_on_message_correction",
        "message_retract": "_on_message_retract",
        "reactions": "_on_reactions",
        "carbon_sent": "_on_carbon_sent",          # XEP-0280: diğer cihazlar
        "carbon_received": "_on_carbon_received",
    }
    if with_omemo:
        table["omemo_initialized"] = "_on_omemo_ready"
    return table


def test_register_handlers_tam_dagitim_tablosu(monkeypatch):
    """Mevcut davranış: olay adı → metot eşlemesi aynen korunmalı
    (Faz 2 mixin ayrımında tablo kayması olmamalı)."""
    monkeypatch.setattr(xmpp, "HAS_OMEMO", True)
    bot = _bot_stub()
    registered = []
    bot.add_event_handler = lambda event, handler: registered.append(
        (event, handler.__name__))
    xmpp.XMPPBot._register_handlers(bot)
    assert dict(registered) == _expected_handlers(with_omemo=True)
    assert len(registered) == 28


def test_register_handlers_omemo_yoksa_kayit_etmez(monkeypatch):
    """Mevcut davranış: OMEMO yoksa omemo_initialized handler'ı kaydedilmez."""
    monkeypatch.setattr(xmpp, "HAS_OMEMO", False)
    bot = _bot_stub()
    registered = []
    bot.add_event_handler = lambda event, handler: registered.append(
        (event, handler.__name__))
    xmpp.XMPPBot._register_handlers(bot)
    assert dict(registered) == _expected_handlers(with_omemo=False)
    assert "omemo_initialized" not in dict(registered)


# ── Gelen mesaj ayrıştırma (xmpp.py:1804-1832) ──────────────────────────────

def test_on_message_chat_payload():
    """Mevcut davranış: chat mesajı gui_q'ya ('msg', sözlük) olarak
    iletilir; from bare JID, nick user, mid origin-id öncelikli."""
    bot = _bot_stub()
    msg = _FakeMsg(body="merhaba", origin="o-1", stanza_id="s-1", mid="m-1")
    xmpp.XMPPBot._on_message(bot, msg)
    assert bot.gui_q.items == [("msg", {
        "from": "ali@example.com",
        "nick": "ali",
        "body": "merhaba",
        "type": "chat",
        "oob": "",
        "encrypted": False,
        "mid": "o-1",
        "reply": None,
    })]


def test_on_message_chat_olmayan_tipleri_yok_sayar():
    """Mevcut davranış: yalnızca 'chat' ve 'normal' tipleri işlenir."""
    bot = _bot_stub()
    for mtype in ("groupchat", "error", "headline"):
        xmpp.XMPPBot._on_message(bot, _FakeMsg(body="x", mtype=mtype))
    assert bot.gui_q.items == []


def test_on_message_pgp_sifreli_mesaji_atlar():
    """Mevcut davranış: jabber:x:encrypted içeren stanza _on_message
    tarafından işlenmez (PGP handler'ına bırakılır)."""
    bot = _bot_stub()
    xml = ET.fromstring(
        "<message xmlns='jabber:client'>"
        "<x xmlns='jabber:x:encrypted'>şifreli</x></message>")
    xmpp.XMPPBot._on_message(bot, _FakeMsg(body="görünmez", xml=xml))
    assert bot.gui_q.items == []


def test_on_gc_message_payload():
    """Mevcut davranış: MUC mesajı oda bare JID + kaynak nick ile
    'groupchat' tipinde iletilir."""
    bot = _bot_stub()
    bot.my_nicks = {"oda@conf.example.com": "ben"}
    msg = _FakeMsg(body="selam oda", frm="oda@conf.example.com/ahmet",
                   origin="gc-1")
    xmpp.XMPPBot._on_gc_message(bot, msg)
    kind, data = bot.gui_q.items[0]
    assert kind == "msg"
    assert data["from"] == "oda@conf.example.com"
    assert data["nick"] == "ahmet"
    assert data["type"] == "groupchat"
    assert data["encrypted"] is False
    assert data["mid"] == "gc-1"


def test_on_gc_message_kendi_nickini_yok_sayar():
    """Mevcut davranış: kendi nick'imizle gelen oda mesajı yankılanmaz."""
    bot = _bot_stub()
    bot.my_nicks = {"oda@conf.example.com": "ben"}
    msg = _FakeMsg(body="kendi mesajım", frm="oda@conf.example.com/ben")
    xmpp.XMPPBot._on_gc_message(bot, msg)
    assert bot.gui_q.items == []


def test_on_gc_message_bos_govde_omemo_yokken_yok_sayilir(monkeypatch):
    """Mevcut davranış: HAS_OMEMO False iken gövdesiz oda mesajı atlanır."""
    monkeypatch.setattr(xmpp, "HAS_OMEMO", False)
    bot = _bot_stub()
    bot.my_nicks = {}
    xmpp.XMPPBot._on_gc_message(bot, _FakeMsg(body="", frm="r@conf/x"))
    assert bot.gui_q.items == []


# ── Bağlantı kopma olayı (xmpp.py:2113-2128) ────────────────────────────────

def test_on_disconnect_olaylari_ve_geri_cekilme(monkeypatch):
    """Mevcut davranış: kopmada ('disconnected', None) + sys_msg yayılır,
    üstel geri çekilme ikiye katlanır, reconnect thread'i kurulur."""
    bot = _bot_stub()
    bot.omemo_ready = True
    bot._connected_ok = True
    bot._auth_failed = False
    bot._reconnect_delay = 2
    started = []

    class _Thread:
        def __init__(self, target=None, daemon=None):
            started.append(target)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _Thread)
    monkeypatch.setattr(xmpp.time, "sleep", lambda s: None)

    xmpp.XMPPBot._on_disconnect(bot, None)

    assert ("disconnected", None) in bot.gui_q.items
    assert any("yeniden bağlan" in str(m) for _, m in bot.gui_q.items)
    assert bot.omemo_ready is False
    assert bot._connected_ok is False
    assert bot._reconnect_delay == 4
    assert len(started) == 1 and callable(started[0])


# ── OMEMO bayrağı tek doğruluk kaynağı (Faz 2 review, madde 14) ─────────────

def test_send_omemo_kapaliyken_engellenir(monkeypatch):
    """Düzeltme: xmpp.HAS_OMEMO tek doğruluk kaynağıdır; False iken mixin'ler
    de omemo gönderimini engeller ve yama sapması oluşmaz."""
    bot = _bot_stub()
    bot.omemo_ready = True
    called = []

    async def _fake_omemo(*args, **kwargs):
        called.append(args)

    bot._send_omemo = _fake_omemo
    monkeypatch.setattr(xmpp, "HAS_OMEMO", False)

    asyncio.run(xmpp.XMPPBot._send_chat(bot, "ali@example.com", "x", "omemo"))
    assert called == []
    assert ("error", "OMEMO kütüphanesi yüklü değil (slixmpp-omemo).") \
        in bot.gui_q.items

    bot.gui_q.items.clear()
    asyncio.run(xmpp.XMPPBot._send_gc(bot, "oda@conf.example.com", "x",
                                      "omemo"))
    assert called == []
    assert ("error", "OMEMO kütüphanesi yüklü değil (slixmpp-omemo).") \
        in bot.gui_q.items
