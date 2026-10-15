"""MAM arşiv akışı ve plugin yükleme sözleşmeleri (refactor regression ağı).

Refactor sırasında MAM sayfalama payload'ı (bot → gui_q → _handle) ve
plugin yükleme/çalıştırma davranışı (importlib, plugin_init çağrısı,
hata yutma) değişmemelidir.
"""

import asyncio
import os
import sys
import types
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp import JID  # noqa: E402

import xmpp  # noqa: E402


class _Q:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def _bot_stub():
    bot = object.__new__(xmpp.XMPPBot)
    bot.gui_q = _Q()
    bot._run_out_filters = None
    return bot


class _FakeStanza:
    def __init__(self, body="", frm="", mid=None, xml=None):
        self._body = body
        self._frm = frm
        self._mid = mid
        self.xml = xml if xml is not None else ET.Element("message")

    def get(self, key, default=""):
        return self._body if key == "body" else default

    def __getitem__(self, key):
        if key == "from":
            return JID(self._frm)
        if key == "id":
            return self._mid
        raise KeyError(key)


class _Mam:
    def __init__(self, results=None, error=None):
        self._results = results or []
        self.error = error
        self.captured = {}

    def retrieve(self, **kw):
        self.captured.update(kw)
        if kw.get("iterator"):
            return _Pages(self)
        return self._result()

    async def _result(self):
        if self.error:
            raise self.error
        return {"mam": {"results": self._results}}


class _Pages:
    """slixmpp RSM ResultIterator taklidi (reverse=True → boş <before/>)."""

    def __init__(self, mam):
        self._mam = mam

    async def next(self):
        if self._mam.error:
            raise self._mam.error
        if not self._mam._results:
            raise StopAsyncIteration
        return {"mam": {"results": self._mam._results}}


def _mam_result(stanza, stamp):
    return {"mam_result": {"forwarded": {
        "stanza": stanza, "delay": {"stamp": stamp}}}}


# ── Bot tarafı: _fetch_mam (xmpp.py:2726-2760) ──────────────────────────────

def test_fetch_mam_duz_metin_mesajlari_ve_rsm(monkeypatch):
    """[2N] Düz metin arşiv kayıtları from/body/ts/is_me/mid alanlarıyla
    'mam_results' olayına dönüşür; ham stanza id non-empty ise raw_id
    eklenir (archive_id fake'te yok → anahtar eklenmez); before verilmezse
    son sayfa RSM yineleyicisiyle (reverse) istenir: slixmpp rsm sözlüğündeki
    before=True'yu "<before>True</before>" olarak yazar → item-not-found."""
    bot = _bot_stub()
    bot.boundjid = JID("ben@example.com/kaynak")
    mam = _Mam(results=[
        _mam_result(_FakeStanza(body="merhaba", frm="ali@example.com",
                                mid="a1"), "2026-09-14T10:00:00Z"),
        _mam_result(_FakeStanza(body="benden", frm="ben@example.com",
                                mid="b1"), "2026-09-14T10:01:00Z"),
    ])
    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: mam if name == "xep_0313" else None)

    asyncio.run(xmpp.XMPPBot._fetch_mam(bot, "ali@example.com"))

    assert mam.captured["with_jid"] == "ali@example.com"
    assert mam.captured["rsm"] == {"max": 50}
    assert mam.captured["iterator"] is True and mam.captured["reverse"] is True
    kind, data = bot.gui_q.items[0]
    assert kind == "mam_results"
    assert data["jid"] == "ali@example.com"
    assert data["messages"] == [
        {"from": "ali@example.com", "body": "merhaba", "ts":
         "2026-09-14T10:00:00Z", "is_me": False, "mid": "a1",
         "raw_id": "a1"},
        {"from": "ben@example.com", "body": "benden", "ts":
         "2026-09-14T10:01:00Z", "is_me": True, "mid": "b1",
         "raw_id": "b1"},
    ]


def test_fetch_mam_hatasi_bos_liste_ve_error_yayar(monkeypatch):
    """Mevcut davranış: arşiv hatası çökertmez; boş messages + error alanı
    ile 'mam_results' yayılır."""
    bot = _bot_stub()
    mam = _Mam(error=RuntimeError("arşiv yok"))
    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: mam if name == "xep_0313" else None)

    asyncio.run(xmpp.XMPPBot._fetch_mam(bot, "ali@example.com"))

    kind, data = bot.gui_q.items[0]
    assert kind == "mam_results"
    assert data["jid"] == "ali@example.com"
    assert data["messages"] == []
    assert data["error"] == "arşiv yok"


# ── GUI tarafı: _load_mam_history (xmpp.py:7472-7475) ───────────────────────

def test_load_mam_history_sadece_gecmisi_olmayan_1e1_sohbette_ister():
    """Mevcut davranış: yerel geçmiş yoksa ve oda değilse MAM istenir
    (generation token'ı istekle birlikte geçirilir)."""
    win = object.__new__(xmpp.MainWindow)
    calls = []
    win.bot = types.SimpleNamespace(
        fetch_mam=lambda jid, n, **kw: calls.append((jid, n, kw.get("token"))))

    win.active, win.rooms, win.chats = "a@b.c", [], {}
    xmpp.MainWindow._load_mam_history(win)
    assert calls == [("a@b.c", 50, 0)]

    win.chats = {"a@b.c": [("Ali", "var", False, "1", "them")]}
    xmpp.MainWindow._load_mam_history(win)
    assert len(calls) == 1  # geçmiş varsa istenmez

    win.active, win.rooms, win.chats = "r@conf", ["r@conf"], {}
    xmpp.MainWindow._load_mam_history(win)
    assert len(calls) == 1  # odalar için MAM istenmez


# ── GUI tarafı: _handle("mam_results") (xmpp.py:11665-11691) ────────────────

def test_handle_mam_results_birlestirir_ve_tekiller():
    """[2N] MAM sonuçları yerel geçmişin önüne eklenir; dedupe imza
    (kimlik-alias, body, yön) temellidir: aynı mid + AYNI body + aynı yön
    → duplicate; aynı mid + FARKLI body → ikisi de korunur (alias tek
    başına duplikasyon kanıtı değildir). En eski imleç güncellenir."""
    win = object.__new__(xmpp.MainWindow)
    win.chats = {"ali@example.com": [
        ("Ali", "eski", False, "09:00", "them", "", False, "m1", "")]}
    win.active = "ali@example.com"
    win.rooms = []
    win._mam_oldest = {}
    win._mam_has_more = {}
    loaded = []
    win._load_chat = lambda jid: loaded.append(jid)

    xmpp.MainWindow._handle(win, "mam_results", {
        "jid": "ali@example.com",
        "messages": [
            # birebir duplicate: aynı mid + aynı body + aynı yön
            {"from": "ali@example.com", "body": "eski", "is_me": False,
             "ts": "2026-09-14T09:59:00Z", "mid": "m1"},
            # aynı mid + FARKLI body → [2N] korunur (satır içinde iki
            # düzeltme olabilir; wire belirsizliğini sessizce silme)
            {"from": "ali@example.com", "body": "m1 tekrar", "is_me": False,
             "ts": "2026-09-14T10:00:00Z", "mid": "m1"},
            {"from": "ali@example.com", "body": "yeni", "is_me": False,
             "ts": "2026-09-14T10:01:00Z", "mid": "m2"},
        ],
    })

    hist = win.chats["ali@example.com"]
    assert len(hist) == 3
    # [2J.b] taze MAM girişi 10'luk: index 0..7 aynı, 8 local_path"",
    # 9 dahili örnek UID (benzersiz, wire'a gitmez)
    # [2N] fresh page sırasını korur: m1-tekrar kabul, m2 kabul → öne
    # eklenir; m1 "eski" birebir duplicate düştü
    assert hist[0][:8] == ("ali", "m1 tekrar", False, "10:00", "them",
                           "", False, "m1")
    assert hist[0][8] == "" and hist[0][9] is not None
    assert hist[1][:8] == ("ali", "yeni", False, "10:01", "them",
                           "", False, "m2")
    assert hist[2][1] == "eski"
    assert win._mam_oldest["ali@example.com"] == "m1"
    assert win._mam_has_more["ali@example.com"] is False
    assert loaded == ["ali@example.com"]  # aktif sohbet yeniden çizilir


def test_handle_mam_results_bos_liste_devam_etmez():
    """Mevcut davranış: boş MAM sayfası 'daha eski yok' demektir."""
    win = object.__new__(xmpp.MainWindow)
    win.chats = {}
    win.active = None
    win.rooms = []
    win._mam_oldest = {}
    win._mam_has_more = {"ali@example.com": True}

    xmpp.MainWindow._handle(win, "mam_results",
                            {"jid": "ali@example.com", "messages": []})

    assert win._mam_has_more["ali@example.com"] is False
    assert win.chats == {}


# ── Plugin yükleme (xmpp.py:12579-12591) ────────────────────────────────────

def _plugin_win():
    win = object.__new__(xmpp.MainWindow)
    win._loaded_plugins = {}
    win.bot = object()
    toasts = []
    win._show_toast = lambda title, msg, **k: toasts.append((title, msg))
    return win, toasts


def test_execute_plugin_plugin_init_bot_ve_gui_alir(tmp_path):
    """Mevcut davranış: plugin dosyası importlib ile yüklenir,
    plugin_init(self.bot, self) çağrılır ve modül kayıtlı kalır."""
    plugin = tmp_path / "p1.py"
    plugin.write_text(
        "def plugin_init(bot, gui):\n"
        "    gui.plugin_called = (bot, gui)\n",
        encoding="utf-8")
    win, toasts = _plugin_win()

    xmpp.MainWindow._execute_plugin(win, "p1", str(plugin))

    assert win.plugin_called == (win.bot, win)
    assert win._loaded_plugins["p1"].__name__ == "p1"
    assert toasts == [("🔌 Plugin", "p1 yüklendi")]


def test_execute_plugin_hatasi_kaydetmez_ve_bildirir(tmp_path):
    """Mevcut davranış: plugin_init hatası yakalanır, modül kaydedilmez."""
    plugin = tmp_path / "p2.py"
    plugin.write_text(
        "def plugin_init(bot, gui):\n"
        "    raise RuntimeError('patladı')\n",
        encoding="utf-8")
    win, toasts = _plugin_win()

    xmpp.MainWindow._execute_plugin(win, "p2", str(plugin))

    assert win._loaded_plugins == {}
    assert toasts == [("⚠ Plugin", "p2: patladı")]


def test_execute_plugin_sozdizimi_hatasi_istisna_sizdirmaz(tmp_path):
    """Mevcut davranış: bozuk plugin dosyası uygulamayı çökertmez."""
    plugin = tmp_path / "p3.py"
    plugin.write_text("def (bozuk\n", encoding="utf-8")
    win, toasts = _plugin_win()

    xmpp.MainWindow._execute_plugin(win, "p3", str(plugin))

    assert win._loaded_plugins == {}
    assert toasts and toasts[0][0] == "⚠ Plugin"


# ── Başlangıçta etkin plugin'ler (xmpp.py:12625-12635) ──────────────────────

def test_load_enabled_plugins_sadece_var_olan_dosyalari_yukler(
        tmp_path, monkeypatch):
    """Mevcut davranış: DB'deki kayıtlardan yalnızca diskte var olan
    dosyalar yüklenir; kayıp yol atlanır."""
    plugin = tmp_path / "ok.py"
    plugin.write_text("def plugin_init(bot, gui): pass\n", encoding="utf-8")
    rows = [("ok", str(plugin)), ("yok", str(tmp_path / "yok.py"))]

    class _Cur:
        def fetchall(self):
            return rows

    class _Db:
        def execute(self, *args):
            return _Cur()

    monkeypatch.setattr(xmpp, "_get_db", lambda: _Db())
    calls = []
    monkeypatch.setattr(xmpp.MainWindow, "_execute_plugin",
                        lambda self, name, path: calls.append((name, path)))
    win = object.__new__(xmpp.MainWindow)

    xmpp.MainWindow._load_enabled_plugins(win)

    assert calls == [("ok", str(plugin))]


def test_load_enabled_plugins_db_hatasini_yutar(monkeypatch):
    """Mevcut davranış: plugin listesi okunamazsa başlangıç çökmez."""

    def _patlat():
        raise RuntimeError("db yok")

    monkeypatch.setattr(xmpp, "_get_db", _patlat)
    win = object.__new__(xmpp.MainWindow)
    assert xmpp.MainWindow._load_enabled_plugins(win) is None


def test_fetch_mam_bos_arsiv_bos_liste_doner(monkeypatch):
    """Yineleyici sonuç yokken StopAsyncIteration fırlatır; hata değildir."""
    bot = _bot_stub()
    bot.boundjid = JID("ben@example.com/kaynak")
    mam = _Mam(results=[])
    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: mam if name == "xep_0313" else None)

    asyncio.run(xmpp.XMPPBot._fetch_mam(bot, "ali@example.com"))

    kind, data = bot.gui_q.items[0]
    assert kind == "mam_results"
    assert data["messages"] == [] and "error" not in data


def test_fetch_mam_oda_arsivi_odanin_kendisinden_istenir(monkeypatch):
    """Katılınan oda için sorgu jid=oda ile gider (with= süzgeci değil)."""
    bot = _bot_stub()
    bot.boundjid = JID("ben@example.com/kaynak")
    bot.my_nicks = {"oda@conf.example.com": "ben"}
    mam = _Mam(results=[])
    monkeypatch.setattr(xmpp.XMPPBot, "__getitem__",
                        lambda self, name: mam if name == "xep_0313" else None)

    asyncio.run(xmpp.XMPPBot._fetch_mam(bot, "oda@conf.example.com"))

    assert mam.captured["jid"] == "oda@conf.example.com"
    assert "with_jid" not in mam.captured
