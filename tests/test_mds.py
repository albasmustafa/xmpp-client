"""XEP-0490 (MDS): okundu bilgisinin aynı hesabın cihazları arasında eşitlenmesi.

Telefonda okunan sohbet (oda dahil, okundu bilgisi kapalı olsa da) masaüstünde
ve web'de okunmamış kalmasın; masaüstünde/web'de okunan telefonda da okunsun.
Önceden: yalnız 1:1'de, telefon okundu işareti gönderirse (XEP-0333 carbon) ve
masaüstü o an açıksa düzeliyordu; masaüstünde sohbet açılınca telefona hiçbir
şey gitmiyordu.
"""
import os
import queue
import sys
import types
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _win  # noqa: E402
from test_webapp import session  # noqa: E402,F401  (fixture)

import xmpp  # noqa: E402
from xmppcore import mds  # noqa: E402

ME = "ben@example.com"
ALI = "ali@x.im"
ROOM = "oda@chat.x"
SID = "{urn:xmpp:sid:0}"


def _xml(*sids, origin=None):
    el = ET.Element("message")
    for sid, by in sids:
        ET.SubElement(el, SID + "stanza-id", id=sid, by=by)
    if origin:
        ET.SubElement(el, SID + "origin-id", id=origin)
    return el


# ── Saf mantık ──────────────────────────────────────────────────────────────
def test_server_stanza_id_picks_archive_owner():
    x = _xml(("oda-1", ROOM), ("ben-1", ME))
    assert mds.server_stanza_id(x, ME) == "ben-1"
    assert mds.server_stanza_id(x, ROOM.upper()) == "oda-1"   # JID büyük/küçük
    assert mds.server_stanza_id(x, "baska@x") == ""
    assert mds.server_stanza_id(None, ME) == ""


def _rs(*unread, seen=()):
    rs = mds.ReadSync()
    for m in seen:
        rs.note_incoming(ALI, m, unread=False)
    for m in unread:
        rs.note_incoming(ALI, m, unread=True)
    return rs


def test_apply_counts_messages_after_displayed_one():
    rs = _rs("m1", "m2", "m3")
    rs.note_ids(ALI, "m2", "s2")              # sunucu stanza-id'si ≠ origin-id
    assert rs.apply(ALI, "s2", current=3) == 1
    assert rs.apply(ALI, "s2", current=1) is None      # değişiklik yok


def test_apply_matches_mid_that_is_the_stanza_id():
    rs = _rs("s1", "s2")                      # origin-id yoksa mid = stanza-id
    assert rs.apply(ALI, "s2", current=2) == 0


def test_apply_older_known_message_keeps_unread():
    rs = _rs("m1", seen=("m0",))
    rs.note_ids(ALI, "m0", "s0")
    assert rs.apply(ALI, "s0", current=1) is None


def test_apply_unknown_sid_means_all_read():
    rs = _rs("m1", "m2")
    assert rs.apply(ALI, "bilinmeyen", current=2) == 0
    assert rs.apply(ALI, "bilinmeyen", current=0) is None


def test_publish_waits_for_sid_and_never_repeats():
    rs = mds.ReadSync()
    assert rs.publish_sid(ALI, "m1") == ""            # sid henüz yok: bekler
    assert rs.note_ids(ALI, "m1", "s1") is True       # bekleyen yayın hazır
    assert rs.publish_sid(ALI, "m1") == "s1"
    assert rs.publish_sid(ALI, "m1") == ""            # aynısı tekrar gitmez
    rs.note_ids(ALI, "m2", "s2")
    rs.apply(ALI, "s2", current=0)                    # başka cihaz zaten yazdı
    assert rs.publish_sid(ALI, "m2") == ""


def test_sid_map_is_bounded():
    rs = mds.ReadSync(max_ids=3)
    for i in range(5):
        rs.note_ids(ALI, f"m{i}", f"s{i}")
    assert rs.publish_sid(ALI, "m0") == ""            # en eskiler düştü
    assert rs.publish_sid(ALI, "m4") == "s4"


# ── Bot tarafı ──────────────────────────────────────────────────────────────
class _J:
    def __init__(self, bare):
        self.bare = bare


class _Msg(dict):
    """slixmpp Message'ın gözlemcinin dokunduğu yüzeyi."""

    def __init__(self, mtype, frm, xml, origin=None, mid="r1"):
        super().__init__(type=mtype, id=mid)
        self["from"] = _J(frm)
        self["origin_id"] = {"id": origin or ""}
        self["stanza_id"] = {"id": ""}
        self.xml = xml


def _bot():
    q = queue.Queue()
    bot = types.SimpleNamespace(boundjid=_J(ME), gui_q=q)
    bot.items = lambda: [q.get_nowait() for _ in range(q.qsize())]
    return bot


def test_observe_chat_uses_own_archive_stanza_id():
    bot = _bot()
    x = _xml(("yabanci", "baska@x"), ("ben-7", ME), origin="o-7")
    xmpp.XMPPBot._mds_observe(bot, _Msg("chat", ALI, x, origin="o-7"))
    assert bot.items() == [("msg_ids", {"jid": ALI, "mid": "o-7", "sid": "ben-7"})]


def test_observe_groupchat_uses_room_stanza_id_and_skips_without_one():
    bot = _bot()
    xmpp.XMPPBot._mds_observe(bot, _Msg("groupchat", ROOM, _xml(("oda-3", ROOM))))
    xmpp.XMPPBot._mds_observe(bot, _Msg("chat", ALI, _xml()))       # stanza-id yok
    xmpp.XMPPBot._mds_observe(bot, _Msg("headline", ALI, _xml(("h", ME))))
    assert bot.items() == [("msg_ids", {"jid": ROOM, "mid": "r1", "sid": "oda-3"})]


def test_observe_carbon_reads_inner_message():
    bot = _bot()
    bot._mds_observe = lambda m: xmpp.XMPPBot._mds_observe(bot, m)
    inner = _Msg("chat", ALI, _xml(("ben-9", ME)), origin="o-9")
    xmpp.XMPPBot._mds_observe_carbon(bot, {"carbon_received": inner})
    assert bot.items() == [("msg_ids", {"jid": ALI, "mid": "o-9", "sid": "ben-9"})]


def _event(frm, chat, sid):
    item = {"id": chat, "displayed": {"stanza_id": {"id": sid}}}
    return {"from": _J(frm), "pubsub_event": {"items": {"item": item}}}


def test_pep_publish_only_from_own_account():
    bot = _bot()
    xmpp.XMPPBot._on_mds_publish(bot, _event(ME, ROOM, "oda-3"))
    xmpp.XMPPBot._on_mds_publish(bot, _event("kotu@x", ALI, "s"))   # başkası
    assert bot.items() == [("mds_displayed", {"jid": ROOM, "sid": "oda-3"})]


def test_mds_flag_publishes_with_archive_owner():
    from slixmpp.plugins.xep_0490 import stanza as mds_stanza
    mds_stanza.register_plugin()
    stored = []
    bot = _bot()
    bot._dispatch_loop = lambda fn: fn()
    bot.plugin = {
        "xep_0490": types.SimpleNamespace(stanza=mds_stanza),
        "xep_0223": types.SimpleNamespace(
            store=lambda st, node=None, id=None: stored.append((st, node, id))),
    }
    xmpp.XMPPBot.mds_flag(bot, ALI, "ben-7")
    xmpp.XMPPBot.mds_flag(bot, ROOM, "oda-3", room=True)
    (d1, node1, id1), (d2, _n2, id2) = stored
    assert node1 == mds.NS and id1 == ALI and id2 == ROOM
    assert (d1["stanza_id"]["id"], d1["stanza_id"]["by"]) == ("ben-7", ME)
    assert (d2["stanza_id"]["id"], d2["stanza_id"]["by"]) == ("oda-3", ROOM)


# ── Masaüstü ────────────────────────────────────────────────────────────────
class _BotRec:
    def __init__(self):
        self.calls = []

    def mds_flag(self, *a, **k):
        self.calls.append(("mds_flag", a, k))

    def send_marker(self, *a, **k):
        self.calls.append(("send_marker", a, k))

    def fetch_mam(self, *a, **k):
        pass


def _desk(unread=None, history=None, jid=ALI):
    w = _win(history or [], jid=jid, active="")
    w.bot = _BotRec()
    w._unread_counts = dict(unread or {})
    refreshed = []
    w._refresh_contacts = lambda: refreshed.append(1)
    w._ai_assistant_refresh = lambda: None
    w._send_read_receipts = True
    w.refreshed = refreshed
    return w


def test_desktop_remote_read_lowers_unread():
    w = _desk({ALI: 3})
    rs = w._readsync()
    for m in ("m1", "m2", "m3"):
        rs.note_incoming(ALI, m, unread=True)
    xmpp.MainWindow._handle(w, "msg_ids", {"jid": ALI, "mid": "m2", "sid": "s2"})
    xmpp.MainWindow._handle(w, "mds_displayed", {"jid": ALI, "sid": "s2"})
    assert w._unread_counts == {ALI: 1} and w.refreshed
    xmpp.MainWindow._handle(w, "mds_displayed", {"jid": ALI, "sid": "yeni"})
    assert w._unread_counts == {}                     # en yeniyi gördü: hepsi


def _entry(sender, body, is_me, mid):
    return (sender, body, is_me, "10:00", "me" if is_me else "them", "",
            False, mid, "", "")


def test_desktop_opening_chat_publishes_read_and_marker():
    hist = [_entry("ali", "selam", False, "m1"),
            _entry("Ben", "naber", True, "o-me")]
    w = _desk({ALI: 1}, hist)
    w._readsync().note_ids(ALI, "m1", "s1")
    xmpp.MainWindow._load_chat(w, ALI)
    assert ("mds_flag", (ALI, "s1"), {"room": False}) in w.bot.calls
    assert ("send_marker", (ALI, "m1", "displayed"), {}) in w.bot.calls


def test_desktop_opening_room_publishes_without_marker():
    w = _desk({ROOM: 2}, [_entry("ayse", "selam", False, "r9")], jid=ROOM)
    w.rooms = [ROOM]
    w._readsync().note_ids(ROOM, "r9", "oda-9")
    xmpp.MainWindow._load_chat(w, ROOM)
    assert w.bot.calls == [("mds_flag", (ROOM, "oda-9"), {"room": True})]


def test_desktop_open_without_unread_publishes_nothing():
    w = _desk({}, [_entry("ali", "selam", False, "m1")])
    w._readsync().note_ids(ALI, "m1", "s1")
    xmpp.MainWindow._load_chat(w, ALI)                # ör. açılışta son sohbet
    assert w.bot.calls == []


def test_desktop_late_stanza_id_triggers_pending_publish():
    w = _desk()
    xmpp.MainWindow._mds_publish(w, ALI, "m5")        # stanza-id henüz yok
    assert w.bot.calls == []
    xmpp.MainWindow._handle(w, "msg_ids", {"jid": ALI, "mid": "m5", "sid": "s5"})
    assert w.bot.calls == [("mds_flag", (ALI, "s5"), {"room": False})]


# ── Web köprüsü ─────────────────────────────────────────────────────────────
def _flags(session):  # noqa: F811
    calls = []
    session.bot.mds_flag = lambda *a, **k: calls.append((a, k))
    return calls


def test_web_live_message_in_open_chat_publishes(session):  # noqa: F811
    calls = _flags(session)
    session.active = ALI
    session._apply("msg_ids", {"jid": ALI, "mid": "w1", "sid": "s-w1"})
    session._apply("msg", {"from": ALI, "nick": "ali", "body": "x", "mid": "w1",
                           "encrypted": False})
    assert calls == [((ALI, "s-w1"), {"room": False})]


def test_web_remote_read_updates_browser(session):  # noqa: F811
    _flags(session)
    for mid in ("w1", "w2"):
        session._apply("msg", {"from": ALI, "nick": "ali", "body": mid,
                               "mid": mid, "encrypted": False})
    while not session.sink.empty():
        session.sink.get_nowait()
    session._apply("msg_ids", {"jid": ALI, "mid": "w1", "sid": "s1"})
    session._apply("mds_displayed", {"jid": ALI, "sid": "s1"})
    assert session.unread == {ALI: 1}
    assert session.sink.get_nowait() == {
        "ev": "unread_update", "data": {"counts": {ALI: 1}, "total": 1}}
    session._apply("mds_displayed", {"jid": ALI, "sid": "baska"})
    assert session.unread == {}
    assert session.sink.get_nowait() == {"ev": "read_elsewhere",
                                         "data": {"jid": ALI}}


def test_web_mark_displayed_publishes_even_without_receipts(session):  # noqa: F811
    calls = _flags(session)
    session._send_read_receipts = False
    session._apply("msg_ids", {"jid": ALI, "mid": "w3", "sid": "s3"})
    assert session.command("mark_displayed", {"to": ALI, "mid": "w3"})["ok"]
    assert calls == [((ALI, "s3"), {"room": False})]
    assert not [c for c in session.bot.calls if c[0] == "send_marker"]


@pytest.mark.parametrize("name", ["xep_0490"])
def test_plugin_registered(name):
    import inspect
    assert f'"{name}"' in inspect.getsource(xmpp.XMPPBot._register_xeps)
