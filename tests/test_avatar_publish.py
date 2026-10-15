"""Avatar yayını: XEP-0084 meta verisi serileştirilebilir olmalı ve akış biter."""

import asyncio
import io
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402
from slixmpp.plugins.xep_0084.stanza import MetaData  # noqa: E402

import xmpp  # noqa: E402


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (48, 32), (10, 20, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_publish_avatar_metadata_serilesir_ve_callback_true(monkeypatch):
    serialized = []

    class _X84:
        async def publish_avatar(self, data):
            return None

        def generate_id(self, data):
            return "abc123"

        async def publish_avatar_metadata(self, items):
            # Gerçek slixmpp akışı: MetaData.add_info + str() serileştirme.
            # int width/height burada TypeError atar (eski hata).
            md = MetaData()
            for i in items:
                md.add_info(i["id"], i["type"], i["bytes"],
                            height=i.get("height", ""), width=i.get("width", ""))
            serialized.append(str(md))

    class _X54:
        async def get_vcard(self, timeout=None):
            raise RuntimeError("vcard yok")

        def make_vcard(self):
            from slixmpp.plugins.xep_0054.stanza import VCardTemp
            return VCardTemp()

        async def publish_vcard(self, vcard):
            return None

    class _X153:
        async def set_avatar(self, avatar=None, mtype=None):
            return None

    plugins = {"xep_0084": _X84(), "xep_0054": _X54(), "xep_0153": _X153()}
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: plugins[name])
    monkeypatch.setattr(xmpp, "_save_avatar_cache", lambda *a: None)
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = types.SimpleNamespace(items=[], put=lambda it: bot.gui_q.items.append(it))
    bot.boundjid = types.SimpleNamespace(bare="ben@example.com")
    results = []

    asyncio.run(xmpp.XMPPBot._publish_avatar(bot, _png(), "image/png", results.append))

    assert results == [True]
    assert serialized and 'width="48"' in serialized[0] and 'height="32"' in serialized[0]
    assert ("sys_msg", "✓ Profil fotoğrafı güncellendi") in bot.gui_q.items
