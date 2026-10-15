"""Resource Hardening 2Q — ``_get_xep`` slixmpp uyumluluk regresyonları.

Gerçek üretim yardımcısı (``xmpp._get_xep`` → ``xmppcore.helpers._get_xep``)
üzerinden, kurulu slixmpp'nin desteklenen ``PluginManager`` API'si ile eski
davranış sözleşmesinin korunmasını doğrular:
  A) kayıtlı eklenti desteklenen ``.plugin`` yolundan döner,
  B) kayıtsız eklenti eski sözleşmeyle ``False`` döner (istisna değil),
  B2) dict benzeri manager'da kayıtsız → eski ``obj[name]`` yolu,
  C) ``.plugin = None`` / ``.plugin``'siz sahteler → eski ``obj[name]`` yolu,
  D) desteklenen yolda DeprecationWarning ÜRETİLMEZ,
  E) gerçek XMPPBot'un üretim kayıtlı eklentisi çözümlenir.
"""

import asyncio
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp.plugins.base import BasePlugin, PluginManager  # noqa: E402

import xmpp  # noqa: E402


class _Q:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


class _FakeXep:
    """Kayıtlı eklenti gibi davranan asgari sahte."""


def _manager_bot():
    """Gerçek PluginManager taşıyan kısmi XMPPBot sahtesi."""
    bot = object.__new__(xmpp.XMPPBot)
    bot.gui_q = _Q()
    bot._run_out_filters = None  # XMLStream.__del__ gürültüsünü sustur
    bot.plugin = PluginManager(bot)
    return bot


# ── A: kayıtlı eklenti, desteklenen .plugin yolu ─────────────────────────────

def test_a_registered_plugin_returned_via_supported_manager(monkeypatch):
    bot = _manager_bot()
    fake = _FakeXep()
    monkeypatch.setitem(bot.plugin._plugins, "xep_0384", fake)
    assert xmpp._get_xep(bot, "xep_0384") is fake


# ── B: kayıtsız eklenti — eski ``False`` sözleşmesi ──────────────────────────

def test_b_missing_plugin_on_real_manager_returns_false(monkeypatch):
    bot = _manager_bot()
    result = xmpp._get_xep(bot, "xep_0384")
    assert result is False


def _partial_bot():
    """Plugin'siz kısmi XMPPBot sahtesi (GC gürültüsü susturulmuş)."""
    bot = object.__new__(xmpp.XMPPBot)
    bot.gui_q = _Q()
    bot._run_out_filters = None
    return bot


def test_b2_dict_manager_miss_falls_back_to_legacy_getitem(monkeypatch):
    bot = _partial_bot()
    bot.plugin = {}  # dict benzeri manager: kayıtsız → KeyError → eski yol
    sentinel = object()
    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: sentinel)
    assert xmpp._get_xep(bot, "xep_0384") is sentinel


# ── C: eski uyumlu sahteler ──────────────────────────────────────────────────

def test_c_plugin_none_double_uses_legacy_getitem(monkeypatch):
    bot = _partial_bot()
    bot.plugin = None  # test_omemo kalıbı: _get_xep bilinçli eski yola düşer
    sentinel = object()
    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: sentinel)
    assert xmpp._get_xep(bot, "xep_0384") is sentinel


def test_c2_stub_without_plugin_attr_uses_legacy_getitem(monkeypatch):
    bot = _partial_bot()  # .plugin hiç atanmadı
    sentinel = object()
    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: sentinel)
    assert xmpp._get_xep(bot, "xep_0384") is sentinel


# ── D: desteklenen yolda deprecation uyarısı yok ────────────────────────────

def test_d_no_deprecation_warning_on_supported_path(monkeypatch):
    bot = _manager_bot()
    fake = _FakeXep()
    monkeypatch.setitem(bot.plugin._plugins, "xep_0045", fake)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert xmpp._get_xep(bot, "xep_0045") is fake
        # Kayıtsız erişim de uyarısız False dönmeli (eski yola hiç inmez).
        assert xmpp._get_xep(bot, "xep_9999") is False


# ── E: gerçek XMPPBot üretim eklentileri ────────────────────────────────────

def test_e_real_bot_registered_plugin_resolves(monkeypatch):
    # HAS_OMEMO=False: slixmpp_omemo'nun kendi içindeki (üçüncü taraf)
    # deprecated erişimlerini devreye sokmadan gerçek bot kur.
    monkeypatch.setattr(xmpp, "HAS_OMEMO", False)

    async def probe():
        bot = xmpp.XMPPBot("qa@test.example", "dummy-pass", _Q())
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            xep = xmpp._get_xep(bot, "xep_0030")  # _register_xeps ile kayıtlı
        assert isinstance(xep, BasePlugin)
        # Kayıtsız XEP: gerçek bot üzerinde de eski False sözleşmesi geçerli.
        assert xmpp._get_xep(bot, "xep_9999") is False

    asyncio.run(probe())
