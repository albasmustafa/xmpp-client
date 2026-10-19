"""Aynı hesap birden çok cihazda (ör. telefonda Monocles/Conversations/Monal).

Kanıtlar (gerçek slixmpp stanza'ları, Conversations biçimli XML):
- Carbons (XEP-0280) etkinleştiriliyordu ama carbon_sent/carbon_received
  olayları dinlenmiyordu: telefondan gönderilen mesajlar ve telefona gelen
  kopyalar masaüstünde hiç görünmüyordu.
- Presence çıplak JID'de "son gelen kazanır"dı: kişinin bir cihazı çevrimdışı
  olunca diğer cihazı (telefonu) açık olsa da kişi çevrimdışı görünüyordu.
- Odada kendi takma adımızla gelen her mesaj "yankı" sayılıp atılıyordu:
  aynı hesapla, aynı takma adla odadaki telefonun mesajları kayboluyordu.
"""
import asyncio
import types
import xml.etree.ElementTree as ET

import pytest
from slixmpp import JID, Message

import xmpp
from xmppcore import messages as messages_mod

OWN = "ben@example.com"


class _Q:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


@pytest.fixture(scope="module")
def real_bot():
    # Gerçek bot kendi döngüsünde kurulur ve sonunda kapanır; OMEMO gereken
    # testler sahte bir xep_0384 takar (üçüncü taraf eklenti kurulmaz).
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    saved, xmpp.HAS_OMEMO = xmpp.HAS_OMEMO, False
    try:
        bot = xmpp.XMPPBot(f"{OWN}/masaustu", "parola", _Q())
    finally:
        xmpp.HAS_OMEMO = saved
    yield bot
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()
    asyncio.set_event_loop(None)
    bot._run_out_filters = None          # XMLStream.__del__ gürültüsü


@pytest.fixture()
def bot(real_bot):
    real_bot.gui_q = _Q()
    real_bot.my_nicks = {}
    real_bot._sent_ids.clear()
    return real_bot


def _stanza(bot, xml):
    # Gelen stanza'lar slixmpp'de recv=True ile kurulur (otomatik id yok)
    return Message(bot, ET.fromstring(xml), recv=True)


def _carbon(direction, inner, outer_from=OWN):
    return (f"<message xmlns='jabber:client' from='{outer_from}' "
            f"to='{OWN}/masaustu' type='chat'>"
            f"<{direction} xmlns='urn:xmpp:carbons:2'>"
            f"<forwarded xmlns='urn:xmpp:forward:0'>{inner}</forwarded>"
            f"</{direction}></message>")


SENT_FROM_PHONE = (
    f"<message xmlns='jabber:client' from='{OWN}/monocles.Ab12' "
    "to='ayse@example.org' type='chat' id='m-1'>"
    "<body>Telefondan selam</body>"
    "<origin-id xmlns='urn:xmpp:sid:0' id='o-1'/>"
    "<request xmlns='urn:xmpp:receipts'/>"
    "<markable xmlns='urn:xmpp:chat-markers:0'/></message>")

RECEIVED_ON_PHONE = (
    "<message xmlns='jabber:client' from='ayse@example.org/monal' "
    f"to='{OWN}/monocles.Ab12' type='chat' id='m-2'>"
    "<body>Telefonuna yazdım</body>"
    "<origin-id xmlns='urn:xmpp:sid:0' id='o-2'/></message>")


# ── Carbons ──────────────────────────────────────────────────────────────────

def test_carbon_events_are_registered():
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None          # XMLStream.__del__ gürültüsü
    registered = {}
    bot.add_event_handler = lambda ev, fn: registered.setdefault(ev, fn.__name__)
    xmpp.XMPPBot._register_handlers(bot)
    assert registered["carbon_sent"] == "_on_carbon_sent"
    assert registered["carbon_received"] == "_on_carbon_received"


def test_message_sent_from_phone_appears_as_own_message(bot):
    msg = _stanza(bot, _carbon("sent", SENT_FROM_PHONE))
    bot.plugin["xep_0280"]._handle_carbon_sent(msg)      # slixmpp yolu
    assert bot.gui_q.items == [("own_msg", {
        "to": "ayse@example.org", "body": "Telefondan selam", "oob": "",
        "encrypted": False, "mid": "o-1", "reply": None})]


def test_message_received_on_phone_appears_on_desktop(bot):
    msg = _stanza(bot, _carbon("received", RECEIVED_ON_PHONE))
    bot.plugin["xep_0280"]._handle_carbon_received(msg)
    (kind, data), = bot.gui_q.items
    assert kind == "msg"
    assert (data["from"], data["body"], data["mid"]) == (
        "ayse@example.org", "Telefonuna yazdım", "o-2")


@pytest.mark.parametrize("direction, inner", [
    ("sent", SENT_FROM_PHONE), ("received", RECEIVED_ON_PHONE)])
def test_spoofed_carbon_from_other_account_is_ignored(bot, direction, inner):
    msg = _stanza(bot, _carbon(direction, inner, outer_from="mallory@evil.example"))
    handler = getattr(bot.plugin["xep_0280"], f"_handle_carbon_{direction}")
    handler(msg)
    assert bot.gui_q.items == []


def test_sent_carbon_to_room_or_self_is_ignored(bot):
    bot.my_nicks = {"oda@conf.example.com": "ben"}
    for to in ("oda@conf.example.com/ali", OWN):
        inner = SENT_FROM_PHONE.replace("to='ayse@example.org'", f"to='{to}'")
        xmpp.XMPPBot._on_carbon_sent(bot, _stanza(bot, _carbon("sent", inner)))
    assert bot.gui_q.items == []


class _FakeOmemo:
    def is_encrypted(self, msg):
        found = msg.xml.find("{eu.siacs.conversations.axolotl}encrypted")
        return {"eu.siacs.conversations.axolotl"} if found is not None else set()

    async def decrypt_message(self, msg):
        return {"body": "şifreli telefondan"}, None


def test_omemo_message_sent_from_phone_is_decrypted_as_own(bot, monkeypatch):
    spawned = []
    monkeypatch.setattr(messages_mod, "_spawn_task",
                        lambda owner, coro: spawned.append(coro))
    monkeypatch.setitem(bot.plugin._plugins, "xep_0384", _FakeOmemo())
    monkeypatch.setattr(xmpp, "HAS_OMEMO", True)
    inner = SENT_FROM_PHONE.replace(
        "<body>Telefondan selam</body>",
        "<body>I sent you an OMEMO encrypted message</body>"
        "<encrypted xmlns='eu.siacs.conversations.axolotl'><header sid='1'/>"
        "</encrypted><store xmlns='urn:xmpp:hints'/>")
    xmpp.XMPPBot._on_carbon_sent(bot, _stanza(bot, _carbon("sent", inner)))
    assert bot.gui_q.items == [] and len(spawned) == 1
    asyncio.run(spawned[0])
    (kind, data), = bot.gui_q.items
    assert kind == "own_msg"
    assert data["to"] == "ayse@example.org"
    assert data["body"] == "şifreli telefondan"
    assert data["encrypted"] == "omemo"


# ── Odada aynı takma adla ikinci oturum ─────────────────────────────────────

ROOM = "oda@conf.example.com"


def _gc(bot, nick, body="selam oda", mid="m-9", origin="o-9", delay=False):
    extra = ("<delay xmlns='urn:xmpp:delay' stamp='2026-10-15T10:00:00Z'/>"
             if delay else "")
    oid = f"<origin-id xmlns='urn:xmpp:sid:0' id='{origin}'/>" if origin else ""
    mid_attr = f" id='{mid}'" if mid else ""
    return _stanza(bot, (
        f"<message xmlns='jabber:client' from='{ROOM}/{nick}' "
        f"to='{OWN}/masaustu' type='groupchat'{mid_attr}>"
        f"<body>{body}</body>{oid}{extra}</message>"))


def test_own_nick_message_from_phone_is_shown_as_own(bot):
    bot.my_nicks = {ROOM: "tuskun"}
    xmpp.XMPPBot._on_gc_message(bot, _gc(bot, "tuskun", "telefondan odaya"))
    (kind, data), = bot.gui_q.items
    assert kind == "own_msg"
    assert (data["to"], data["body"], data["mid"]) == (
        ROOM, "telefondan odaya", "o-9")


def test_reflection_of_our_own_message_is_still_dropped(bot):
    bot.my_nicks = {ROOM: "tuskun"}
    out = bot.make_message(mto=ROOM, mbody="masaüstünden", mtype="groupchat")
    out["id"] = "m-9"
    xmpp._add_origin_id(out, "o-9")
    bot._remember_sent_id(out)          # giden filtre
    xmpp.XMPPBot._on_gc_message(bot, _gc(bot, "tuskun", "masaüstünden"))
    assert bot.gui_q.items == []


def test_reflection_matched_by_stanza_id_when_origin_id_dropped(bot):
    """OMEMO şifreleme origin-id'yi siler; yansıma `id` ile tanınır."""
    bot.my_nicks = {ROOM: "tuskun"}
    out = bot.make_message(mto=ROOM, mtype="groupchat")
    out["id"] = "m-9"
    bot._remember_sent_id(out)
    xmpp.XMPPBot._on_gc_message(bot, _gc(bot, "tuskun", origin=None))
    assert bot.gui_q.items == []


@pytest.mark.parametrize("kw", [{"delay": True}, {"mid": "", "origin": None}])
def test_own_nick_history_or_unidentified_message_is_dropped(bot, kw):
    bot.my_nicks = {ROOM: "tuskun"}
    xmpp.XMPPBot._on_gc_message(bot, _gc(bot, "tuskun", **kw))
    assert bot.gui_q.items == []


def test_outgoing_filter_is_installed(real_bot):
    filters = real_bot._XMLStream__filters["out"]
    assert real_bot._remember_sent_id in filters


def test_sent_id_memory_is_bounded(bot):
    for i in range(2000):
        out = bot.make_message(mto=ROOM, mtype="groupchat")
        out["id"] = f"id-{i}"
        bot._remember_sent_id(out)
    assert len(bot._sent_ids) <= 1000
    assert "id-1999" in bot._sent_ids


def test_omemo_room_message_from_phone_is_own(bot, monkeypatch):
    bot.my_nicks = {ROOM: "tuskun"}
    monkeypatch.setitem(bot.plugin._plugins, "xep_0384", _FakeOmemo())
    msg = _gc(bot, "tuskun", origin=None)
    asyncio.run(bot._decrypt_and_deliver(msg, "groupchat"))
    (kind, data), = bot.gui_q.items
    assert kind == "own_msg" and data["to"] == ROOM
    assert data["encrypted"] == "omemo"


# ── Çok kaynaklı presence ────────────────────────────────────────────────────

def _presence_bot(resources):
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = _Q()
    bot.client_roster = {"ayse@example.org": types.SimpleNamespace(
        resources=resources)}
    return bot


class _Pres(dict):
    def __init__(self, frm, ptype, show=""):
        super().__init__(type=ptype, show=show)
        self["from"] = JID(frm)


def test_contact_stays_online_while_phone_is_connected():
    """Bilgisayardaki istemci kapandı, telefondaki Monocles açık."""
    bot = _presence_bot({"monocles": {"show": "", "priority": 0}})
    xmpp.XMPPBot._on_presence(bot, _Pres("ayse@example.org/gajim", "unavailable"))
    assert bot.gui_q.items == [("presence", {
        "jid": "ayse@example.org", "ptype": "available", "pshow": ""})]


def test_contact_goes_offline_when_last_device_leaves():
    bot = _presence_bot({})
    xmpp.XMPPBot._on_presence(bot, _Pres("ayse@example.org/monocles", "unavailable"))
    assert bot.gui_q.items == [("presence", {
        "jid": "ayse@example.org", "ptype": "unavailable", "pshow": ""})]


def test_most_available_device_wins():
    bot = _presence_bot({"telefon": {"show": "away"}, "masaustu": {"show": "chat"},
                         "tablet": {"show": "dnd"}})
    xmpp.XMPPBot._on_presence(bot, _Pres("ayse@example.org/telefon", "away", "away"))
    assert bot.gui_q.items[0][1]["pshow"] == "chat"


# ── GUI: başka cihazımızdan gelen kendi mesajımız ────────────────────────────

def _own_win(active="ayse@example.org"):
    win = object.__new__(xmpp.MainWindow)
    win.active = active
    win.chats = {}
    win._chat_tabs = {}
    win._unread_counts = {"ayse@example.org": 3}
    calls = []
    win._store = lambda *a, **k: calls.append(("store", a, k))
    win._deliver_live = lambda target, fn: calls.append(("live", target)) or "append"
    win._append = lambda *a, **k: calls.append(("append", a, k))
    win._remember_mid = lambda jid, mid: None
    win._resolve_reply = lambda reply, frm: reply
    win._refresh_contacts = lambda: calls.append(("refresh",))
    return win, calls


OWN_PAYLOAD = {"to": "ayse@example.org", "body": "Telefondan selam", "oob": "",
               "encrypted": False, "mid": "o-1", "reply": None}


def test_own_message_is_stored_as_mine_and_clears_unread():
    win, calls = _own_win()
    xmpp.MainWindow._handle(win, "own_msg", dict(OWN_PAYLOAD))
    (_, args, kw), = [c for c in calls if c[0] == "store"]
    assert args == ("ayse@example.org", "Telefondan selam")
    assert kw["is_me"] is True and kw["tag"] == "me" and kw["sender"] == "Ben"
    assert kw["mid"] == "o-1"
    assert ("live", "ayse@example.org") in calls
    # Telefondan yanıt verildiyse sohbet masaüstünde okunmamış kalmaz
    assert "ayse@example.org" not in win._unread_counts


def test_own_message_for_inactive_chat_is_stored_without_rendering():
    win, calls = _own_win(active="baska@example.org")
    xmpp.MainWindow._handle(win, "own_msg", dict(OWN_PAYLOAD))
    assert [c[0] for c in calls if c[0] in ("store", "live")] == ["store"]


def test_duplicate_own_message_is_suppressed():
    win, calls = _own_win()
    win.chats = {"ayse@example.org": [
        ("Ben", "Telefondan selam", True, "10:00", "me", "", False, "o-1", "")]}
    xmpp.MainWindow._handle(win, "own_msg", dict(OWN_PAYLOAD))
    assert not [c for c in calls if c[0] in ("store", "live")]


# ── Carbon içindeki düzeltme/geri çekme/tepki ve okundu işareti ──────────────

def _inner(frm, to, extra, body="", mid="m-5"):
    b = f"<body>{body}</body>" if body else ""
    return (f"<message xmlns='jabber:client' from='{frm}' to='{to}' "
            f"type='chat' id='{mid}'>{b}{extra}</message>")


CONTACT, PHONE = "ayse@example.org/monal", f"{OWN}/monocles.Ab12"


@pytest.mark.parametrize("extra, body, kind", [
    ("<replace xmlns='urn:xmpp:message-correct:0' id='o-2'/>", "düzeltildi",
     "msg_correction"),
    ("<retract xmlns='urn:xmpp:message-retract:1' id='o-2'/>",
     "This person attempted to retract a previous message", "msg_retract"),
    ("<reactions xmlns='urn:xmpp:reactions:0' id='o-2'><reaction>👍</reaction>"
     "</reactions>", "", "msg_reactions"),
])
def test_received_carbon_meta_goes_to_its_handler(bot, extra, body, kind):
    inner = _inner(CONTACT, PHONE, extra, body)
    xmpp.XMPPBot._on_carbon_received(bot, _stanza(bot, _carbon("received", inner)))
    assert [k for k, _ in bot.gui_q.items] == [kind]   # yeni mesaj DEĞİL


@pytest.mark.parametrize("extra, body, event", [
    ("<replace xmlns='urn:xmpp:message-correct:0' id='o-1'/>", "düzeltildi",
     ("msg_correction", {"from": "ayse@example.org", "orig_id": "o-1",
                         "body": "düzeltildi", "nick": "Ben"})),
    ("<retract xmlns='urn:xmpp:message-retract:1' id='o-1'/>", "geri çekildi",
     ("msg_retract", {"from": "ayse@example.org", "retracted_id": "o-1"})),
    ("<reactions xmlns='urn:xmpp:reactions:0' id='o-1'><reaction>👍</reaction>"
     "</reactions>", "",
     ("msg_reactions", {"from": "ayse@example.org", "nick": "Ben",
                        "target_id": "o-1", "emojis": ["👍"]})),
])
def test_edit_retract_react_on_phone_applies_to_contact_chat(bot, extra, body,
                                                             event):
    """Telefonda yapılan düzeltme/geri çekme/tepki yeni mesaj değildir;
    karşı tarafın sohbetindeki kendi mesajımıza (from=kişi) uygulanır.
    Önce sessizce atılıyordu: masaüstünde eski metin/tepki kalıyordu."""
    inner = _inner(PHONE, "ayse@example.org", extra, body)
    msg = _stanza(bot, _carbon("sent", inner))
    bot.plugin["xep_0280"]._handle_carbon_sent(msg)      # slixmpp yolu
    assert bot.gui_q.items == [event]


def test_reactions_withdrawn_on_phone_send_empty_set(bot):
    inner = _inner(PHONE, "ayse@example.org",
                   "<reactions xmlns='urn:xmpp:reactions:0' id='o-1'/>")
    xmpp.XMPPBot._on_carbon_sent(bot, _stanza(bot, _carbon("sent", inner)))
    assert bot.gui_q.items == [("msg_reactions", {
        "from": "ayse@example.org", "nick": "Ben", "target_id": "o-1",
        "emojis": []})]


def test_omemo_correction_on_phone_is_decrypted_into_contact_chat(
        bot, monkeypatch):
    spawned = []
    monkeypatch.setattr(messages_mod, "_spawn_task",
                        lambda owner, coro: spawned.append(coro))
    monkeypatch.setitem(bot.plugin._plugins, "xep_0384", _FakeOmemo())
    monkeypatch.setattr(xmpp, "HAS_OMEMO", True)
    inner = _inner(
        PHONE, "ayse@example.org",
        "<replace xmlns='urn:xmpp:message-correct:0' id='o-1'/>"
        "<encrypted xmlns='eu.siacs.conversations.axolotl'><header sid='1'/>"
        "</encrypted><store xmlns='urn:xmpp:hints'/>",
        body="I sent you an OMEMO encrypted message")
    xmpp.XMPPBot._on_carbon_sent(bot, _stanza(bot, _carbon("sent", inner)))
    # Yedek metin düzeltme olarak uygulanmaz; çözme görevi başlar
    assert bot.gui_q.items == [] and len(spawned) == 1
    asyncio.run(spawned[0])
    assert bot.gui_q.items == [("msg_correction", {
        "from": "ayse@example.org", "orig_id": "o-1",
        "body": "şifreli telefondan", "nick": "Ben"})]


def test_pgp_correction_on_phone_is_ignored(bot):
    """PGP kopyası kendi anahtarımızla çözülemez: yedek metin, düzeltme
    olarak orijinalin yerine yazılmamalı."""
    inner = _inner(PHONE, "ayse@example.org",
                   "<replace xmlns='urn:xmpp:message-correct:0' id='o-1'/>"
                   "<x xmlns='jabber:x:encrypted'>QUJD</x>",
                   body="This message is encrypted")
    xmpp.XMPPBot._on_carbon_sent(bot, _stanza(bot, _carbon("sent", inner)))
    assert bot.gui_q.items == []


# ── GUI: tepki kümesi değişince eskisi kalkar (XEP-0444 tam küme) ────────────

def _reaction_win(monkeypatch, store, mine=None):
    win = object.__new__(xmpp.MainWindow)
    win.jid, win.active, win.rooms, win.my_nick = OWN, None, [], {}
    win._reactions = store
    win._my_reactions = dict(mine or {})
    saved = []
    monkeypatch.setattr(xmpp, "_db_save_reaction",
                        lambda *a: saved.append(a))
    return win, saved


def test_changed_reaction_from_phone_replaces_old_one(monkeypatch):
    key = ("ayse@example.org", "o-1")
    win, saved = _reaction_win(monkeypatch, {key: {"👍": ["Ben"]}},
                               mine={key: {"👍"}})
    xmpp.MainWindow._handle(win, "msg_reactions", {
        "from": "ayse@example.org", "nick": "Ben", "target_id": "o-1",
        "emojis": ["❤️"]})
    assert win._reactions[key] == {"❤️": ["Ben"]}
    assert win._my_reactions[key] == {"❤️"}
    assert ("ayse@example.org", "o-1", "👍", "Ben", False) in saved
    assert ("ayse@example.org", "o-1", "❤️", "Ben", True) in saved


def test_changed_reaction_keeps_other_senders(monkeypatch):
    key = ("ayse@example.org", "o-1")
    win, _saved = _reaction_win(monkeypatch,
                                {key: {"👍": ["monal", "Ben"]}})
    xmpp.MainWindow._handle(win, "msg_reactions", {
        "from": "ayse@example.org", "nick": "monal", "target_id": "o-1",
        "emojis": ["😂"]})
    assert win._reactions[key] == {"👍": ["Ben"], "😂": ["monal"]}


def test_read_on_phone_clears_unread_on_desktop(bot):
    inner = _inner(PHONE, "ayse@example.org",
                   "<displayed xmlns='urn:xmpp:chat-markers:0' id='o-2'/>")
    xmpp.XMPPBot._on_carbon_sent(bot, _stanza(bot, _carbon("sent", inner)))
    assert bot.gui_q.items == [("read_elsewhere", "ayse@example.org")]


def test_read_elsewhere_clears_unread_badge():
    win, calls = _own_win()
    xmpp.MainWindow._handle(win, "read_elsewhere", "ayse@example.org")
    assert "ayse@example.org" not in win._unread_counts
    assert ("refresh",) in calls
