"""RESOURCE HARDENING 2P — BUG A: hızlı ardışık gönderim güvenilirliği.

Kanıt (yarış modeli): `_send_omemo` eşzamanlı çağrıldığında (hızlı ardışık
5 gönderim) slixmpp-omemo SessionManager'ı eşzamanlı encrypt_prepare'de
yarışır; üretim kodu hata alan mesajı TAMAMEN düşürüyor (wire'a gitmiyor,
sent_mid yok). Testin yarış modeli: mock encrypt_message, aktif eşzamanlı
çağrı > 1 iken deterministik EncryptionPrepareException benzeri hata
fırlatır. Pre-fix: bazıları/harbisi düşer → FAIL. Post-fix ([2P] asyncio.Lock
ile sıra korunarak serileştirme — drop değil): 5/5 gönderilir, 5 benzersiz
mid, 5 sent_mid.
"""
import asyncio
import os
import queue
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2i_ttl_expiry import _Row  # noqa: E402
from test_history_window_bounds import _Cap, _win  # noqa: E402

import xmpp  # noqa: E402


def _o_w(texts):
    """[2P] Composer'dan 5 hızlı gönderimi süren Tk'sız pencere çifti."""
    it = iter(texts)
    w = _win(jid="a@b")
    w.active = "a@b"
    w._msg_ids = {}
    w._notify_enabled = False
    w._sound_enabled = False
    w._show_toast = lambda *a, **k: None
    w._send_read_receipts = False
    w._send_typing_notif = False
    w._typing_send_id = None
    w._disappearing_ttl = {}
    w._ttl_deadlines = {}
    w._reply_map = {}
    w._encryption_mode = types.SimpleNamespace(
        get=lambda: "none", set=lambda v: None)
    w._bubble_widgets = []
    w._composer = types.SimpleNamespace(
        get_text=lambda: next(it), clear_text=lambda: None,
        consume_reply=lambda: None, cancel_reply=lambda: None)

    def _fake_clear():
        w._bubble_widgets.clear()

    w._clear_chat = _fake_clear

    def _fake_append(body, tag, sender="", is_me=False, time_str=None,
                     oob="", encrypted=False, mid="", reply_to=None,
                     local_path=""):
        r = _Row(mid, body)
        w._bubble_widgets.append(r)
        return r

    w._append = _fake_append
    w.bot = types.SimpleNamespace(send_chat=_Cap(), send_gc=_Cap(),
                                  send_reply=_Cap())
    return w


def _summary(w, jid="a@b"):
    return [(e[7], e[1], bool(e[2])) for e in w.chats.get(jid, [])]


# ── A1) plain chat: 5 hızlı gönderim → 5/5, benzersiz mid/body ───────────────
def test_plain_rapid_sends_all_delivered():
    w = _o_w([f"mesaj {i}" for i in range(1, 6)])
    for _ in range(5):
        xmpp.MainWindow._send_message(w)
    sent = w.bot.send_chat.calls
    assert len(sent) == 5                              # 5/5 wire çağrısı
    assert [c[0][1] for c in sent] == [f"mesaj {i}" for i in range(1, 6)]
    mids = [c[1]["mid"] for c in sent]
    assert len(set(mids)) == 5                         # 5 benzersiz mid
    assert len(_summary(w)) == 5                       # 5 optimistik satır
    assert _summary(w) == [(m, f"mesaj {i}", True)
                           for i, m in enumerate(mids, 1)]


# ── A3) reply gönderimi hızlı akışta kimliğini korur ─────────────────────────
def test_reply_send_keeps_identity(monkeypatch):
    w = _o_w(["yanıt gövde"])
    w._composer = types.SimpleNamespace(
        get_text=lambda: "yanıt gövde", clear_text=lambda: None,
        consume_reply=lambda: {"mid": "hedef-mid", "sender": "Ali",
                               "body": "alıntı"},
        cancel_reply=lambda: None)
    xmpp.MainWindow._send_message(w)
    calls = w.bot.send_reply.calls
    assert len(calls) == 1
    to, body, rid, rbody = calls[0][0][:4]
    assert (to, body, rid) == ("a@b", "yanıt gövde", "hedef-mid")
    mid = calls[0][1]["mid"]
    assert isinstance(mid, str) and mid                # origin-id benzersiz


# ── A4) file_uploaded (URL mesaj) aynı gönderim makinesini kullanır ──────────
def test_file_uploaded_rapid_keeps_five_distinct(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w([])
    w._deliver_live = lambda target, fn: (fn(), "append")[1]
    for i in range(5):
        xmpp.MainWindow._handle(w, "file_uploaded",
                                {"url": f"https://x/y{i}.bin", "path": f"p{i}",
                                 "cb": "a@b"})   # üretim: cb = hedef sohbet
    rows = _summary(w)
    assert len(rows) == 5
    assert [b for _m, b, _me in rows] == [f"https://x/y{i}.bin"
                                          for i in range(5)]
    mids = [m for m, _b, _me in rows]
    assert len(set(mids)) == 5                         # 5 benzersiz mid


# ── A2) OMEMO hızlı ardışık: yarış modeli → sıra korunarak serileştirme ──────
class _FakeMsg:
    """slixmpp Message benzeri minimal sahte (origin-id/eme + send)."""

    def __init__(self, tag="plain"):
        self._origin = {"id": ""}
        self._data = {"body": "", "eme": {}}
        self.sent = False
        self.tag = tag

    def __getitem__(self, key):
        if key == "origin_id":
            return self._origin
        return self._data[key]

    def __setitem__(self, key, value):
        if key == "origin_id":
            self._origin = value
        else:
            self._data[key] = value

    def set_to(self, to):
        pass

    def set_from(self, frm):
        pass

    def send(self):
        self.sent = True


class _ConcurrencyRaceXep:
    """[2P] Yarış modeli: eşzamanlı encrypt_prepare deterministik hata verir.

    Gerçek slixmpp-omemo davranışını modeller: aynı SessionManager'a
    eşzamanlı encrypt_message → hazırlık yarışı → hata.
    """

    def __init__(self, bot):
        self.bot = bot
        self.encrypt_calls = 0
        self.refresh_calls = 0
        self.active = 0

    async def refresh_device_lists(self, recipients, force_download=False):
        self.refresh_calls += 1
        await asyncio.sleep(0)                         # yarış penceresi

    async def encrypt_message(self, stanza, recipients):
        self.encrypt_calls += 1
        self.active += 1
        try:
            await asyncio.sleep(0.02)                  # gerçek yarış penceresi
            if self.active > 1:                        # eşzamanlılık = yarış
                raise RuntimeError("EncryptionPrepareException: session race")
            return _FakeMsg(tag="encrypted"), []
        finally:
            self.active -= 1

    def is_encrypted(self, msg):
        return {"urn:xmpp:omemo:2"}


def _race_bot():
    """[2P] _send_omemo üretim yolunu süren bot çifti + mock xep."""
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    from slixmpp import JID
    bot.boundjid = JID("ben@example.com/kaynak")
    bot.gui_q = queue.Queue()
    bot.rooms = []
    bot.my_nicks = {}
    bot._omemo_enabled = lambda: True
    bot.omemo_ready = True
    bot.make_message = lambda **k: _FakeMsg()
    xep = _ConcurrencyRaceXep(bot)
    bot._mock_xep = xep
    return bot, xep


def test_omemo_rapid_sends_no_message_lost(monkeypatch):
    """[2P-A2] 5 hızlı OMEMO gönderim: 5/5 encrypt → 5/5 wire + sent_mid.

    Pre-fix: yarış modeli eşzamanlı encrypt'leri düşürür → FAIL.
    Post-fix: [2P] lock sıra KORUYARAK serileştirir → 5/5.
    """
    bot, xep = _race_bot()
    monkeypatch.setattr(xmpp, "_get_xep", lambda self, name: xep)

    async def main():
        tasks = [asyncio.ensure_future(
            xmpp.XMPPBot._send_omemo(bot, "ali@example.com", f"mesaj {i}",
                                     "chat", mid=f"mid-{i}"))
            for i in range(1, 6)]
        await asyncio.gather(*tasks)

    asyncio.run(main())

    sent_mids = []
    while not bot.gui_q.empty():
        kind, data = bot.gui_q.get()
        if kind == "sent_mid":
            sent_mids.append(data["mid"])
    assert xep.encrypt_calls == 5                       # 5/5 encrypt denemesi
    assert sorted(sent_mids) == sorted(f"mid-{i}" for i in range(1, 6))
    assert len(sent_mids) == 5                          # SIFIR kayıp
    errors = []
    while not bot.gui_q.empty():
        kind, data = bot.gui_q.get()
        if kind == "error":
            errors.append(data)
    assert errors == []                                 # yarış hatası sıfır
