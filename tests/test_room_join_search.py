"""Oda (kanal) girişi ve oda araması regresyonları.

B1 — Oda servisi `"conference." + domain` diye tahmin ediliyordu (yax.im'de
     yok; gerçek servis chat.yax.im). XEP-0030 ile keşfedilmeli.
B2 — Arama `GET /rooms?q=` ile yapılıyordu; sunucu q'yu yok sayıp alakasız
     liste döndürüyor. Doğru uç nokta `POST /api/1.0/search` (keywords ≥3 harf).
B3 — Büyük harf/boşluk/`xmpp:` önekli oda adresi normalize edilmiyordu:
     slixmpp olayları küçük harfli JID ile tetiklediğinden katılım 30 sn
     sonra "yanıt vermedi" diye düşüyordu. Ham PresenceError metni de
     anlaşılmıyordu.
B4 — Keşif sonuç/hata bildirimi sys balonu olarak gidiyordu; açık sohbet
     yokken görünmüyordu.
B5 — Sonuçlar yalnız kullanıcı sayısına göre sıralanıyordu: sunucu kelimeyi
     açıklamada da eşlediği için açıklamasına yüzlerce anahtar kelime dolduran
     kalabalık odalar ("Indonesia, Jawa, … Linux, Python, …") aramayla ilgisiz
     olduğu hâlde en üste çıkıyordu. Sonuçlar alaka düzeyine göre sıralanmalı,
     yalnız şişirilmiş açıklamada geçen eşleşmeler en sona düşmeli.
"""
import asyncio
import contextlib
import io
import json
import os
import sys
import types
import urllib.error

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp import Presence  # noqa: E402
from slixmpp.exceptions import PresenceError  # noqa: E402
from slixmpp.plugins.xep_0030.stanza import DiscoInfo, DiscoItems  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import helpers  # noqa: E402
from xmppcore import muc as muc_mod  # noqa: E402


class _Events:
    """slixmpp event_handler/event çifti (kayıt + elle tetikleme)."""

    def __init__(self):
        self.handlers = {}

    @contextlib.contextmanager
    def event_handler(self, name, fn):
        self.handlers.setdefault(name, []).append(fn)
        try:
            yield
        finally:
            self.handlers[name].remove(fn)

    def fire(self, name, arg):
        for fn in list(self.handlers.get(name, [])):
            fn(arg)

    def active(self):
        return {k: v for k, v in self.handlers.items() if v}


def _bot():
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.my_nicks = {}
    bot.gui_q = types.SimpleNamespace(items=[])
    bot.gui_q.put = bot.gui_q.items.append
    bot.events = _Events()
    bot.event_handler = bot.events.event_handler
    return bot


# ── B3) Oda adresi normalizasyonu ───────────────────────────────────────────
@pytest.mark.parametrize("raw,default,expected", [
    ("xmpp:Linux@Chat.Yax.im?join", "", "linux@chat.yax.im"),
    ("  Oda@Conference.Example.ORG  ", "", "oda@conference.example.org"),
    ("oda@x.org/nick", "", "oda@x.org"),
    ("linux", "chat.yax.im", "linux@chat.yax.im"),
])
def test_normalize_room_jid(raw, default, expected):
    assert helpers._normalize_room_jid(raw, default) == expected


@pytest.mark.parametrize("raw,default", [
    ("", "chat.yax.im"), ("   ", "x.org"), ("linux", ""),
    ("a b@x.org", ""), ("@x.org", ""),
])
def test_normalize_room_jid_rejects_invalid(raw, default):
    with pytest.raises(ValueError):
        helpers._normalize_room_jid(raw, default)


class _X45:
    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    async def join_muc_wait(self, room, nick, **kw):
        self.calls.append((room, nick, kw))
        if self.exc:
            raise self.exc
        return (None, None, [], [])


def test_join_uses_normalized_room(monkeypatch):
    bot, x45 = _bot(), _X45()
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, "Linux@Chat.Yax.im ", "ben"))
    assert x45.calls[0][0] == "linux@chat.yax.im"
    assert bot.gui_q.items == [("room_joined", "linux@chat.yax.im")]
    assert bot.my_nicks == {"linux@chat.yax.im": "ben"}


def test_join_invalid_room_reports_error_without_network(monkeypatch):
    bot, x45 = _bot(), _X45()
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, "geçersiz oda", "ben"))
    assert x45.calls == []
    kind, text = bot.gui_q.items[0]
    assert kind == "error" and "Geçersiz oda adresi" in text


@pytest.mark.parametrize("cond,needle", [
    ("conflict", "takma ad"),
    ("not-authorized", "parola"),
    ("forbidden", "yasak"),
    ("registration-required", "üye"),
    ("item-not-found", "bulunamadı"),
])
def test_join_presence_error_is_readable(monkeypatch, cond, needle):
    err = PresenceError({"error": {"condition": cond, "text": "",
                                   "type": "cancel"}})
    bot, x45 = _bot(), _X45(exc=err)
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, "oda@chat.yax.im", "ben"))
    kind, text = bot.gui_q.items[0]
    assert kind == "error" and needle in text and "oda@chat.yax.im" in text


def _mw():
    w = object.__new__(xmpp.MainWindow)
    w.jid = "ben@yax.im"
    w.root = "ROOT"
    w.my_nick = {}
    joins = []
    w.bot = types.SimpleNamespace(muc_service="chat.yax.im",
                                  join_room=lambda r, n: joins.append((r, n)),
                                  configure_instant_room=lambda r: None)
    return w, joins


def test_mainwindow_join_paths_normalize(monkeypatch):
    w, joins = _mw()
    xmpp.MainWindow._join_room_requested(w, "Linux@Chat.Yax.im", "ben")
    xmpp.MainWindow._join_searched_room(w, "xmpp:Prosody@Conference.Prosody.im?join", "ben")
    xmpp.MainWindow._join_room_requested(w, "kahve", "ben")
    assert joins == [("linux@chat.yax.im", "ben"),
                     ("prosody@conference.prosody.im", "ben"),
                     ("kahve@chat.yax.im", "ben")]
    assert set(w.my_nick) == {r for r, _n in joins}


def test_mainwindow_join_invalid_shows_error(monkeypatch):
    w, joins = _mw()
    shown = []
    monkeypatch.setattr(xmpp.messagebox, "showerror",
                        lambda *a, **k: shown.append(a))
    xmpp.MainWindow._join_room_requested(w, "boşluklu oda adı", "ben")
    assert joins == [] and shown and w.my_nick == {}


# ── B1) Oda servisi keşfi ───────────────────────────────────────────────────
def _info(*identities):
    info = DiscoInfo()
    for cat, typ in identities:
        info.add_identity(cat, typ)
    return info


class _X30:
    def __init__(self, results=None, exc=None):
        self.results = results or []
        self.exc = exc

    async def get_info_from_domain(self, domain=None, timeout=None, **kw):
        if self.exc:
            raise self.exc
        return self.results


def test_find_muc_service_picks_conference_identity(monkeypatch):
    bot = _bot()
    x30 = _X30([
        {"from": "yax.im", "disco_info": _info(("server", "im"))},
        {"from": "upload.yax.im", "disco_info": _info(("store", "file"))},
        {"from": "chat.yax.im", "disco_info": _info(("conference", "text"))},
    ])
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x30)
    asyncio.run(xmpp.XMPPBot._find_muc_service(bot))
    assert bot.muc_service == "chat.yax.im"


def test_find_muc_service_none_or_error_keeps_empty(monkeypatch):
    for x30 in (_X30([{"from": "yax.im",
                       "disco_info": _info(("server", "im"))}]),
                _X30(exc=RuntimeError("timeout"))):
        bot = _bot()
        monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name, x=x30: x)
        asyncio.run(xmpp.XMPPBot._find_muc_service(bot))
        assert bot.muc_service == ""


def test_dialogs_default_to_discovered_service(monkeypatch):
    from ui.dialogs import rooms as ui_rooms
    seen = {}
    monkeypatch.setattr(ui_rooms, "show_join_room",
                        lambda parent, conf, nick, on_disc, on_join:
                        seen.update(join=conf))
    monkeypatch.setattr(ui_rooms, "show_create_room",
                        lambda parent, conf, nick, on_create:
                        seen.update(create=conf))
    monkeypatch.setattr(ui_rooms, "show_room_search",
                        lambda *a, **kw: seen.update(search=kw["own_conf"]))
    w, _ = _mw()
    xmpp.MainWindow._join_room_dialog(w)
    xmpp.MainWindow._create_room_dialog(w)
    xmpp.MainWindow._search_rooms_dialog(w)
    assert seen == {"join": "chat.yax.im", "create": "chat.yax.im",
                    "search": "chat.yax.im"}
    w.bot.muc_service = ""                    # keşif bitmedi/başarısız
    xmpp.MainWindow._join_room_dialog(w)
    assert seen["join"] == "conference.yax.im"


# ── B2) Gerçek arama uç noktası ─────────────────────────────────────────────
class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run_search(monkeypatch, query, opener):
    w = object.__new__(xmpp.MainWindow)
    w._safe_after = lambda ms, fn, *a: fn(*a)

    class _T:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    reqs = []

    def _open(req, timeout=None):
        reqs.append(req)
        return opener(req)

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", _open)
    done, errors = [], []
    xmpp.MainWindow._search_rooms_requested(w, query, done.append,
                                            errors.append)
    return reqs, done, errors


def test_search_posts_keywords_to_search_endpoint(monkeypatch):
    payload = {"query": {}, "result": {"more": False, "items": [
        {"address": "linux@chat.yax.im", "name": "Linux", "nusers": 4},
        {"address": "debian@x.org", "name": "Debian", "nusers": 9}]}}
    reqs, done, errors = _run_search(
        monkeypatch, "  linux  ab debian ",
        lambda req: _Resp(json.dumps(payload).encode()))
    req, = reqs
    assert req.full_url == "https://search.jabber.network/api/1.0/search"
    assert req.get_method() == "POST"
    body = json.loads(req.data)
    assert body["keywords"] == ["linux", "debian"]      # <3 harf elenir
    assert body["sinname"] and body["sindescr"] and body["sinaddr"]
    assert errors == []
    assert [i["address"] for i in done[0]] == ["debian@x.org",
                                               "linux@chat.yax.im"]


def test_search_short_query_errors_without_request(monkeypatch):
    reqs, done, errors = _run_search(monkeypatch, "ab c", lambda req: None)
    assert reqs == [] and done == []
    assert errors and "3 harf" in errors[0]


def test_search_http_400_is_friendly(monkeypatch):
    def _bad(req):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {},
                                     io.BytesIO(b"parse error"))
    _reqs, done, errors = _run_search(monkeypatch, "linux", _bad)
    assert done == [] and "3 harf" in errors[0]


def test_parse_room_search_accepts_result_shape():
    payload = {"result": {"items": [{"address": "a@c", "nusers": 1},
                                    {"name": "adressiz"}]}}
    assert [i["address"] for i in xmpp._parse_room_search(payload)] == ["a@c"]
    assert xmpp._parse_room_search({"result": "bozuk"}) == []


# ── B5) Alaka sıralaması ─────────────────────────────────────────────────────
_STUFFED = ", ".join(
    "Indonesia Indochat Jawa Sumatera Kalimantan Sulawesi Papua Bali Lombok "
    "Sumbawa Flores Sumba Timor Rote Maluku Halmahera Seram Ambon Batam "
    "Bintan Karimun Natuna Mentawai Madura Buru Ternate Jakarta Banten "
    "Tangerang Surabaya Bandung Semarang Jogja Solo Medan Padang Lampung "
    "Linux Python Java JavaScript Debian Android HTML CSS ubuntu".split())


def _search_payload():
    """search.jabber.network'ün "linux" için gerçek yanıtından kısaltılmış."""
    return {"query": {}, "result": {"more": True, "items": [
        {"address": "indonesia@conference.conversations.im",
         "name": "🇮🇩 INDONESIA 🇮🇩 Conversations", "description": _STUFFED,
         "nusers": 216},
        {"address": "floss@rooms.dismail.de", "name": "FLOSS",
         "description": "Linux, BSD, XMPP, ...", "nusers": 53},
        {"address": "angrytux@conference.trashserver.net",
         "name": "Linux & FLOSS", "description": "Linux & FLOSS",
         "nusers": 258},
        {"address": "linux@muc.loqi.im", "name": "Linux/Unix",
         "description": "Everything related to Linux", "nusers": 270},
        {"address": "mobile-linux@conference.conversations.im",
         "name": "Mobile Linux", "description": "", "nusers": 48},
        {"address": "furrylinux@chat.jabberfr.org", "name": "boykisser",
         "description": "", "nusers": 4},
    ]}}


def test_search_ranks_by_relevance_and_sinks_stuffed_descriptions():
    items = xmpp._parse_room_search(_search_payload(), ["linux"])
    addrs = [i["address"] for i in items]
    # Tam ad/adres > adda kelime > adres parçası > açıklama > yığın açıklama
    assert addrs == ["linux@muc.loqi.im",
                     "angrytux@conference.trashserver.net",
                     "mobile-linux@conference.conversations.im",
                     "furrylinux@chat.jabberfr.org",
                     "floss@rooms.dismail.de",
                     "indonesia@conference.conversations.im"]


def test_stuffed_room_still_found_for_its_own_topic():
    """Yığın açıklamalı oda, adında geçen konuyla aranınca yine en üstte."""
    items = xmpp._parse_room_search(_search_payload(), ["indonesia"])
    assert items[0]["address"] == "indonesia@conference.conversations.im"


def test_prose_and_urls_are_not_keyword_stuffing():
    from xmppcore import format as _fmt
    """Virgüllü düzyazı ve URL eğik çizgileri yığın sayılmaz (gerçek veri)."""
    lounge = ("A friendly hangout for gamers, programmers, tinkerers and retro "
              "computing fans. Tell us what you are playing, show off what you "
              "are building, ask for help with code, swap stories about old "
              "consoles, DOS games and 8-bit machines, talk MUDs, roguelikes "
              "and indie games, or just kick back and chat, Linux too.")
    openwrt = ("matrix.org/legal/code-of-conduct https://forum.openwrt.org/x/y "
               "openwrt.org/bugs guides: openwrt.org/docs/guide-quick-start "
               "wireless mesh networking, free space radio, open source, "
               "Linux routers, wifi, WISP, https://matrix.to/#/#OpenWrt:m.org")
    assert not _fmt._is_stuffed(lounge)
    assert not _fmt._is_stuffed(openwrt)
    assert _fmt._is_stuffed(_STUFFED)


def test_search_relevance_is_case_and_turkish_insensitive():
    payload = {"result": {"items": [
        {"address": "sohbet@x.org", "name": "Genel", "nusers": 90,
         "description": "Türkçe GELİŞTİRİCİ sohbeti ve daha fazlası"},
        {"address": "gelistirici@x.org", "name": "Geliştirici", "nusers": 3},
    ]}}
    addrs = [i["address"] for i in
             xmpp._parse_room_search(payload, ["geliştirici"])]
    assert addrs == ["gelistirici@x.org", "sohbet@x.org"]


def test_search_keeps_server_match_we_cannot_explain():
    """Sunucu başka bir biçimde eşleştirdiyse (ör. kök bulma) sonuç atılmaz."""
    payload = {"result": {"items": [
        {"address": "a@x.org", "name": "Alfa", "nusers": 5},
        {"address": "linux@x.org", "name": "Linux", "nusers": 1}]}}
    addrs = [i["address"] for i in xmpp._parse_room_search(payload, ["linux"])]
    assert addrs == ["linux@x.org", "a@x.org"]


def test_search_multiple_keywords_need_all_strong():
    payload = {"result": {"items": [
        {"address": "debian@x.org", "name": "Debian",
         "description": "Linux dağıtımı", "nusers": 80},
        {"address": "linux-debian@x.org", "name": "Debian Linux",
         "nusers": 2}]}}
    addrs = [i["address"] for i in
             xmpp._parse_room_search(payload, ["linux", "debian"])]
    assert addrs == ["linux-debian@x.org", "debian@x.org"]


def test_search_worker_passes_keywords_for_ranking(monkeypatch):
    _reqs, done, errors = _run_search(
        monkeypatch, "linux",
        lambda req: _Resp(json.dumps(_search_payload()).encode()))
    assert errors == []
    addrs = [i["address"] for i in done[0]]
    assert addrs[0] == "linux@muc.loqi.im"
    assert addrs[-1] == "indonesia@conference.conversations.im"


# ── B4) Keşif bildirimi her zaman görünür ───────────────────────────────────
def _disco_bot(items=None, exc=None):
    disco = DiscoItems()
    for jid, name in items or []:
        disco.add_item(jid, name=name)

    class _X30i:
        async def get_items(self, jid=None, timeout=None):
            if exc:
                raise exc
            return {"disco_items": disco}
    return _bot(), _X30i()


def test_discover_failures_use_visible_event(monkeypatch):
    for kwargs in ({"items": []}, {"exc": RuntimeError("remote-server-not-found")}):
        bot, x30 = _disco_bot(**kwargs)
        monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name, x=x30: x)
        asyncio.run(xmpp.XMPPBot._discover_rooms(bot, "conference.yax.im"))
        kind, text = bot.gui_q.items[0]
        assert kind == "rooms_discover_failed" and "conference.yax.im" in text


def test_handle_discover_failed_shows_dialog_even_without_chat(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = "ROOT"
    w.active = None
    shown = []
    monkeypatch.setattr(xmpp.messagebox, "showinfo",
                        lambda title, msg, **k: shown.append((title, msg)))
    xmpp.MainWindow._handle(w, "rooms_discover_failed", "oda bulunamadı")
    assert shown == [("Oda Keşfi", "oda bulunamadı")]


# ── J1/J2) Katılım beklemesi: hata presence'ı ve gelmeyen konu ──────────────
def _presence(frm, ptype=None, condition=None):
    p = Presence()
    p["from"] = frm
    if ptype:
        p["type"] = ptype
    if condition:
        p["error"]["condition"] = condition
    return p


class _X45Script:
    """join_muc_wait çifti: başlarken `script(bot)` çalışır, sonra bekler.

    `finish_after` verilirse o kadar saniye sonra normal biter (konu geldi);
    verilmezse hiç bitmez (konu hiç gelmedi / sunucu sessiz).
    """

    def __init__(self, bot, script=None, finish_after=None):
        self.bot = bot
        self.script = script
        self.finish_after = finish_after
        self.cancelled = False
        self.calls = []

    async def join_muc_wait(self, room, nick, **kw):
        self.calls.append((room, nick, kw))
        if self.script:
            asyncio.get_running_loop().call_soon(self.script, self.bot)
        try:
            if self.finish_after is not None:
                await asyncio.sleep(self.finish_after)
                return (None, None, [], [])
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


@pytest.fixture()
def fast_join(monkeypatch):
    monkeypatch.setattr(muc_mod.MucMixin, "_JOIN_TIMEOUT", 0.5)
    monkeypatch.setattr(muc_mod.MucMixin, "_JOIN_SUBJECT_GRACE", 0.05)


def _run_join(monkeypatch, bot, x45, room="oda@chat.yax.im"):
    monkeypatch.setattr(muc_mod, "_get_xep", lambda self, name: x45)
    asyncio.run(xmpp.XMPPBot._join(bot, room, "albas"))


def test_join_bounced_error_without_muc_element_fails_fast(monkeypatch,
                                                           fast_join):
    """J1: kendi sunucumuzun geri yolladığı hata (MUC <x/> yok) beklenmez."""
    def script(bot):
        # başka odanın hatası yok sayılmalı
        bot.events.fire("presence_error", _presence(
            "baska@chat.yax.im", "error", "forbidden"))
        bot.events.fire("presence_error", _presence(
            "oda@chat.yax.im", "error", "remote-server-not-found"))
    bot = _bot()
    x45 = _X45Script(bot, script)
    _run_join(monkeypatch, bot, x45)
    kind, text = bot.gui_q.items[0]
    assert kind == "error" and "Oda sunucusu bulunamadı" in text
    assert x45.cancelled and bot.my_nicks == {}
    assert bot.events.active() == {}             # dinleyiciler temizlendi


def test_join_succeeds_when_subject_never_arrives(monkeypatch, fast_join):
    """J2: self-presence geldi, konu gelmedi (ör. zaten odadaydık)."""
    def script(bot):
        bot.events.fire("muc::oda@chat.yax.im::self-presence",
                        _presence("oda@chat.yax.im/albas"))
    bot = _bot()
    x45 = _X45Script(bot, script)
    _run_join(monkeypatch, bot, x45, room="Oda@Chat.Yax.im")
    assert bot.gui_q.items == [("room_joined", "oda@chat.yax.im")]
    assert bot.my_nicks == {"oda@chat.yax.im": "albas"}
    assert x45.cancelled and bot.events.active() == {}


def test_join_normal_flow_with_subject_unchanged(monkeypatch, fast_join):
    def script(bot):
        bot.events.fire("muc::oda@chat.yax.im::self-presence",
                        _presence("oda@chat.yax.im/albas"))
    bot = _bot()
    x45 = _X45Script(bot, script, finish_after=0.01)
    _run_join(monkeypatch, bot, x45)
    assert bot.gui_q.items == [("room_joined", "oda@chat.yax.im")]
    assert not x45.cancelled


def test_join_no_answer_times_out_with_hint(monkeypatch, fast_join):
    bot = _bot()
    x45 = _X45Script(bot)
    _run_join(monkeypatch, bot, x45)
    kind, text = bot.gui_q.items[0]
    assert kind == "error" and "yanıt vermedi" in text
    assert "adres yanlış" in text and x45.cancelled
    assert bot.events.active() == {}


def test_join_failure_is_logged(monkeypatch, fast_join):
    logged = []
    monkeypatch.setattr(muc_mod._log, "warning",
                        lambda *a, **k: logged.append(a))
    def script(bot):
        bot.events.fire("presence_error", _presence(
            "oda@chat.yax.im", "error", "remote-server-timeout"))
    bot = _bot()
    _run_join(monkeypatch, bot, _X45Script(bot, script))
    assert "ulaşılamadı" in bot.gui_q.items[0][1]
    assert logged and "oda@chat.yax.im" in logged[0]
