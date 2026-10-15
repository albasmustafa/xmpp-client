"""Oda keşfi gerçek slixmpp disco#items yanıtını ayrıştırır."""

import asyncio
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp.plugins.xep_0030.stanza import DiscoItems  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import muc as muc_mod  # noqa: E402


def _bot(items):
    disco = DiscoItems()
    for jid, name in items:
        disco.add_item(jid, name=name)

    class _X30:
        async def get_items(self, jid=None, timeout=None):
            return {"disco_items": disco}

    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = types.SimpleNamespace(items=[])
    bot.gui_q.put = bot.gui_q.items.append
    return bot, _X30()


def test_discover_rooms_parses_disco_tuples(monkeypatch):
    bot, x30 = _bot([("a@conf.example.com", "A Odası"), ("b@conf.example.com", None)])
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x30)
    asyncio.run(xmpp.XMPPBot._discover_rooms(bot, "conf.example.com"))
    kind, rooms = bot.gui_q.items[0]
    assert kind == "rooms_discovered"
    assert sorted(rooms) == [("a@conf.example.com", "A Odası"), ("b@conf.example.com", "")]


def test_discover_rooms_empty_reports_not_found(monkeypatch):
    bot, x30 = _bot([])
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x30)
    asyncio.run(xmpp.XMPPBot._discover_rooms(bot, "conf.example.com"))
    kind, text = bot.gui_q.items[0]
    # Ayrı olay türü: açık sohbet yokken de görünür bildirim (bkz.
    # test_room_join_search.py B4); sys balonu boş ekranda görünmüyordu.
    assert kind == "rooms_discover_failed" and "bulunamadi" in text
