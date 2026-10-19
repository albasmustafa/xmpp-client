"""Mobil istemcilerden (Conversations/Monocles/Monal) düzenleme ve geri çekme.

Kanıt (slixmpp'nin gerçek gelen-stanza yolu, `_spawn_event`): düzenlenen
mesaj hem orijinali güncelliyor hem de YENİ mesaj olarak ekleniyordu;
geri çekmenin yedek gövdesi ("This person attempted to retract…") yeni mesaj
olarak düşüyordu. OMEMO'lu düzenlemede düzeltme, çözülmemiş yedek metni
("I sent you an OMEMO encrypted message") orijinalin yerine yazıyordu.
"""
import asyncio

import pytest
import test_multi_device as _md
from test_multi_device import OWN, ROOM, _FakeOmemo

import xmpp
from xmppcore import messages as messages_mod

# Gerçek bot fikstürleri test_multi_device ile ortak
real_bot = _md.real_bot
bot = _md.bot

CONTACT = "ayse@example.org/monal"
RETRACT_FALLBACK = ("This person attempted to retract a previous message, "
                    "but it's unsupported by your client.")


def _msg(extra, body, frm=CONTACT, mtype="chat", mid="x-1"):
    return (f"<message xmlns='jabber:client' from='{frm}' to='{OWN}/masaustu' "
            f"type='{mtype}' id='{mid}'><body>{body}</body>{extra}</message>")


def _feed(bot, xml):
    import xml.etree.ElementTree as ET
    bot._spawn_event(ET.fromstring(xml))        # gerçek eşleştirme + olaylar


def _kinds(bot):
    return [k for k, _ in bot.gui_q.items]


CORRECTION = "<replace xmlns='urn:xmpp:message-correct:0' id='o-2'/>"
RETRACT = ("<retract xmlns='urn:xmpp:message-retract:1' id='o-2'/>"
           "<fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:message-retract:1'/>"
           "<store xmlns='urn:xmpp:hints'/>")


@pytest.mark.parametrize("mtype, frm", [
    ("chat", CONTACT), ("groupchat", f"{ROOM}/ayse")])
def test_correction_updates_original_without_new_message(bot, mtype, frm):
    bot.my_nicks = {ROOM: "tuskun"}
    _feed(bot, _msg(CORRECTION, "düzeltilmiş metin", frm, mtype))
    assert _kinds(bot) == ["msg_correction"]
    data = bot.gui_q.items[0][1]
    assert (data["orig_id"], data["body"]) == ("o-2", "düzeltilmiş metin")


@pytest.mark.parametrize("mtype, frm", [
    ("chat", CONTACT), ("groupchat", f"{ROOM}/ayse")])
def test_retraction_fallback_is_not_shown_as_message(bot, mtype, frm):
    bot.my_nicks = {ROOM: "tuskun"}
    _feed(bot, _msg(RETRACT, RETRACT_FALLBACK, frm, mtype))
    assert _kinds(bot) == ["msg_retract"]


def test_plain_message_still_arrives(bot):
    _feed(bot, _msg("", "normal mesaj"))
    assert _kinds(bot) == ["msg"]


def test_omemo_correction_is_decrypted_then_applied(bot, monkeypatch):
    spawned = []
    monkeypatch.setattr(messages_mod, "_spawn_task",
                        lambda owner, coro: spawned.append(coro))
    monkeypatch.setitem(bot.plugin._plugins, "xep_0384", _FakeOmemo())
    monkeypatch.setattr(xmpp, "HAS_OMEMO", True)
    _feed(bot, _msg(
        CORRECTION + "<encrypted xmlns='eu.siacs.conversations.axolotl'>"
        "<header sid='1'/></encrypted><store xmlns='urn:xmpp:hints'/>",
        "I sent you an OMEMO encrypted message"))
    # Yedek metin düzeltme olarak uygulanmaz; çözme görevi başlar
    assert _kinds(bot) == [] and len(spawned) == 1
    asyncio.run(spawned[0])
    assert bot.gui_q.items == [("msg_correction", {
        "from": "ayse@example.org", "orig_id": "o-2",
        "body": "şifreli telefondan", "nick": "monal"})]


class _FakePgp:
    def __init__(self, text="pgp düzeltilmiş"):
        self.text = text

    def decrypt(self, data, jid=None):
        return self.text


PGP_X = "<x xmlns='jabber:x:encrypted'>-----ARMOR-----</x>"


@pytest.mark.parametrize("mtype, frm, nick", [
    ("chat", CONTACT, "monal"), ("groupchat", f"{ROOM}/ayse", "ayse")])
def test_pgp_correction_is_decrypted_then_applied(bot, monkeypatch,
                                                  mtype, frm, nick):
    # Kanıt: düzeltme yedek gövdeyi ("This message is encrypted") orijinalin
    # yerine yazıyor, çözülen metin ise YENİ mesaj olarak düşüyordu
    bot.my_nicks = {ROOM: "tuskun"}
    monkeypatch.setitem(bot.plugin._plugins, "xep_0027", _FakePgp())
    _feed(bot, _msg(CORRECTION + PGP_X, "This message is encrypted",
                    frm, mtype))
    assert bot.gui_q.items == [("msg_correction", {
        "from": frm.split("/")[0], "orig_id": "o-2",
        "body": "pgp düzeltilmiş", "nick": nick})]


def test_pgp_message_without_correction_still_arrives(bot, monkeypatch):
    monkeypatch.setitem(bot.plugin._plugins, "xep_0027", _FakePgp())
    _feed(bot, _msg(PGP_X, "This message is encrypted"))
    assert _kinds(bot) == ["msg"]
    assert bot.gui_q.items[0][1]["encrypted"] == "pgp"


def _received_carbon(extra, body="This message is encrypted"):
    # Telefona (aynı hesabın başka cihazına) gelen mesajın kopyası
    inner = (f"<message xmlns='jabber:client' from='{CONTACT}' "
             f"to='{OWN}/telefon' type='chat' id='c-1'>"
             f"<body>{body}</body>{extra}</message>")
    return _md._carbon("received", inner)


def test_pgp_received_carbon_is_decrypted(bot, monkeypatch):
    # Kanıt: telefona gelen PGP mesajının kopyası hiç olay üretmiyordu
    # (encrypted_message olayı carbon içindeki stanza için tetiklenmez)
    monkeypatch.setitem(bot.plugin._plugins, "xep_0027",
                        _FakePgp("telefona gelen pgp"))
    _feed(bot, _received_carbon(PGP_X))
    assert _kinds(bot) == ["msg"]
    data = bot.gui_q.items[0][1]
    assert (data["from"], data["body"], data["encrypted"], data["mid"]) == (
        "ayse@example.org", "telefona gelen pgp", "pgp", "c-1")


def test_pgp_received_carbon_correction_is_applied(bot, monkeypatch):
    monkeypatch.setitem(bot.plugin._plugins, "xep_0027", _FakePgp())
    _feed(bot, _received_carbon(CORRECTION + PGP_X))
    assert bot.gui_q.items == [("msg_correction", {
        "from": "ayse@example.org", "orig_id": "o-2",
        "body": "pgp düzeltilmiş", "nick": "monal"})]
