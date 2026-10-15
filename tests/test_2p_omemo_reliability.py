"""RESOURCE HARDENING 2P — BUG B: OMEMO çözme güvenilirliği.

Kanıt: `_decrypt_and_deliver` bir decrypt hatasında mesajı TAMAMEN
kaybediyordu (yalnız sys_msg; oturum/bundle hazır-değil geçici hatası da
kalıcı sayılıyordu) ve `_on_message`'da OMEMO kontrolü etrafında yutulan
`except: pass` vardı. [2P] ile: transiyan oturum/bundle hatalarında
SINIRLI yeniden deneme (3 deneme, artan bounded backoff, asyncio — Tk
bloklamaz), aynı stanza için tek çözüm görevi (pending set — çift
plaintext yok), kalıcı hatalar tek explicit sys_msg, yutulan except
log'a observable.
"""
import asyncio
import os
import queue
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


class _FakeFrom:
    def __init__(self, bare="a@x", user="Ali"):
        self.bare = bare
        self.user = user


class _FakeMsg:
    """slixmpp Message benzeri minimal sahte (decrypt yolu)."""

    def __init__(self, body="çözülen metin", mid=""):
        self._frm = _FakeFrom()
        self._mid = mid
        self._origin = {"id": mid}   # [2P] pending set gerçek stanza-id kullansın

    def __getitem__(self, key):
        if key == "from":
            return self._frm
        if key == "type":
            return "chat"
        if key == "origin_id":
            return self._origin
        if key == "reply":
            raise KeyError("reply")
        if key == "body":
            return ""
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key == "origin_id":
            self._origin = value

    @property
    def xml(self):
        return _FakeXml()              # helpers fallback: mid = ""


class _FakeXml:
    """slixmpp xml benzeri minimal sahte (find sadece)."""

    def __init__(self, omemo=False, pgp=False):
        self._omemo = omemo
        self._pgp = pgp

    def find(self, ns):
        if ns == "{eu.siacs.conversations.axolotl}encrypted":
            return object() if self._omemo else None
        if ns == "{jabber:x:encrypted}x":
            return object() if self._pgp else None
        return None


class _FakePlain:
    """decrypt_message dönüşü: plaintext_msg["body"]."""

    def __init__(self, body):
        self._body = body

    def __getitem__(self, key):
        if key == "body":
            return self._body
        raise KeyError(key)


class _DecryptXep:
    """[2P] Senaryolu decrypt mock'u: başarısızlık sırası deterministik."""

    def __init__(self, script):
        self.script = list(script)     # her eleman: Exception | ("ok", body)
        self.calls = 0

    async def decrypt_message(self, msg):
        self.calls += 1
        await asyncio.sleep(0.01)                  # eşzamanlılık penceresi
        step = self.script.pop(0) if self.script else ("ok", "varsayılan")
        if isinstance(step, Exception):
            raise step
        return _FakePlain(step[1]), None


def _bot(xep):
    from slixmpp import JID
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = queue.Queue()
    bot.my_nicks = {}
    bot.rooms = []
    bot.boundjid = JID("ben@example.com/kaynak")
    monkey = {"xep": xep}
    return bot, monkey


def _drain(bot):
    msgs, sys_msgs = [], []
    while not bot.gui_q.empty():
        kind, data = bot.gui_q.get()
        if kind == "msg":
            msgs.append(data)
        elif kind == "sys_msg":
            sys_msgs.append(data)
    return msgs, sys_msgs


def _run_decrypt(bot, msg, mtype="chat"):
    async def main():
        await xmpp.XMPPBot._decrypt_and_deliver(bot, msg, mtype)
    asyncio.run(main())


# ── B1) hazır oturum: tek çözüm, tek teslim ──────────────────────────────────
def test_ready_session_decrypts_once(monkeypatch):
    xep = _DecryptXep([("ok", "merhaba")])
    bot, monkey = _bot(xep)
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: xep)
    _run_decrypt(bot, _FakeMsg())
    msgs, sys_msgs = _drain(bot)
    assert len(msgs) == 1 and msgs[0]["body"] == "merhaba"
    assert sys_msgs == []
    assert xep.calls == 1


# ── B3) beş hızlı şifreli mesaj: hiçbiri düşmez/ezilmez ──────────────────────
def test_five_rapid_encrypted_all_delivered(monkeypatch):
    script = [("ok", f"metin {i}") for i in range(5)]
    xep = _DecryptXep(script)
    bot, _ = _bot(xep)
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: xep)
    for i in range(5):
        _run_decrypt(bot, _FakeMsg(mid=f"m{i}"))
    msgs, sys_msgs = _drain(bot)
    assert [m["body"] for m in msgs] == [f"metin {i}" for i in range(5)]
    assert sys_msgs == []


# ── B4) ZORUNLU: oturum hazır değilken ilk mesaj → sınırlı retry → teslim ────
def test_transient_session_failure_bounded_retry_then_deliver(monkeypatch):
    """Pre-fix: ilk 'No session' hatasında mesaj KAYBOLUYORDU (yalnız
    sys_msg). Post-fix: 3 denemeye kadar sınırlı retry → mesaj teslim."""
    xep = _DecryptXep([RuntimeError("No session found for device"),
                       ("ok", "gecikmeli çözüldü")])
    bot, _ = _bot(xep)
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: xep)
    _run_decrypt(bot, _FakeMsg())
    msgs, sys_msgs = _drain(bot)
    assert xep.calls == 2                          # sınırlı: 1 retry
    assert len(msgs) == 1 and msgs[0]["body"] == "gecikmeli çözüldü"
    assert sys_msgs == []                          # hata çözüldü: sessiz


# ── B7) kalıcı kriptografik hata: explicit failure, retry sonsuz değil ───────
def test_permanent_failure_surfaces_once(monkeypatch):
    xep = _DecryptXep([RuntimeError("Device is not trusted for encryption")])
    bot, _ = _bot(xep)
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: xep)
    _run_decrypt(bot, _FakeMsg())
    msgs, sys_msgs = _drain(bot)
    assert xep.calls == 1                          # kalıcı: retry YOK
    assert len(sys_msgs) == 1
    assert "OMEMO çözme hatası" in sys_msgs[0]
    assert msgs == []                              # plaintext/ciphertext karışık DEĞİL


# ── B2/B3-extension) üç transient hatadan sonra da sınırlı kalır ────────────
def test_all_transient_attempts_exhausted_surfaces_once(monkeypatch):
    xep = _DecryptXep([RuntimeError("No session")] * 5)
    bot, _ = _bot(xep)
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: xep)
    _run_decrypt(bot, _FakeMsg())
    msgs, sys_msgs = _drain(bot)
    assert xep.calls == 3                          # üst sınır 3 (sonsuz değil)
    assert len(sys_msgs) == 1 and msgs == []


# ── B8) aynı stanza: çift plaintext üretimi imkânsız ─────────────────────────
def test_same_stanza_never_delivers_duplicate_plaintext(monkeypatch):
    xep = _DecryptXep([("ok", "tek çözüm")])
    bot, _ = _bot(xep)
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: xep)
    msg = _FakeMsg(mid="ayni-stanza")

    async def main():
        # gerçek duplicate senaryosu: iki event görevi EŞZAMANLI çözüyor
        await asyncio.gather(
            xmpp.XMPPBot._decrypt_and_deliver(bot, msg, "chat"),
            xmpp.XMPPBot._decrypt_and_deliver(bot, msg, "chat"))

    asyncio.run(main())
    msgs, _sys = _drain(bot)
    assert len(msgs) == 1                          # çift plaintext YOK
    assert msgs[0]["body"] == "tek çözüm"


# ── yutulan except: `_on_message` OMEMO kontrolü hatası log'a düşer ──────────
def test_on_message_swallowed_exception_becomes_observable(monkeypatch):
    calls = []
    # Gerçek botta `log` özniteliği YOK: modül loglayıcısı dinlenir (eski sahte
    # `win.log` AttributeError hatasını gizliyordu)
    import xmppcore.messages as _msgs_log
    monkeypatch.setattr(_msgs_log._log, "warning",
                        lambda msg, *a, **k: calls.append(msg))
    win = types.SimpleNamespace()
    win._omemo_enabled = lambda: True

    class _RaisingXep:
        def is_encrypted(self, msg):
            raise RuntimeError("plugin pasifik değil")
    # _on_message _get_xep'i KENDİ modülünden import eder (xmppcore.messages)
    import xmppcore.messages as _msgs
    monkeypatch.setattr(_msgs, "_get_xep",
                        lambda self, name: _RaisingXep())
    msg = _FakeMsg()
    xmpp.XMPPBot._on_message(win, msg)
    assert calls                                   # yutulmadı: log observable


# ── ek) OMEMO hazır değilken şifreli mesaj: sessiz kayıp YOK ─────────────────
def test_omemo_disabled_encrypted_message_is_observable(monkeypatch):
    bot, _ = _bot(_DecryptXep([]))
    bot._omemo_enabled = lambda: False
    msg = _FakeMsg()                   # body yok; xml OMEMO encrypted içerir
    # _FakeMsg.xml'i OMEMO'lu xml'e bağla
    type(msg).xml = property(
        lambda self: _FakeXml(omemo=True))
    xmpp.XMPPBot._on_message(bot, msg)
    msgs, sys_msgs = _drain(bot)
    assert msgs == []                  # plaintext üretilmedi
    assert len(sys_msgs) == 1          # sessiz kayıp yerine observable


# ── ek2) yutulan except artık sys_msg değil log'a düşer (onu da test et) ─────
def test_on_message_swallowed_exception_uses_log_warning(monkeypatch):
    calls = []
    # Gerçek botta `log` özniteliği YOK: modül loglayıcısı dinlenir (eski sahte
    # `win.log` AttributeError hatasını gizliyordu)
    import xmppcore.messages as _msgs_log
    monkeypatch.setattr(_msgs_log._log, "warning",
                        lambda msg, *a, **k: calls.append(msg))
    win = types.SimpleNamespace()
    win._omemo_enabled = lambda: True

    class _RaisingXep:
        def is_encrypted(self, msg):
            raise RuntimeError("plugin pasifik değil")
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: _RaisingXep())
    msg = _FakeMsg()
    xmpp.XMPPBot._on_message(win, msg)
    assert calls and "OMEMO" in str(calls[0])
