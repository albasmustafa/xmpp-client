"""Oda MAM geçmişi (XEP-0313): odaya girince eski mesajlar gelsin.

Kanıtlar:
- `_load_mam_history`: boş geçmişli ODA için de arşiv isteği gider (eski kod
  yalnız 1:1'e izin veriyordu — kullanıcı şikâyeti: odada geçmiş yok).
- `_load_older_mam`: odada imleçle (archive_id) eski sayfa istenir.
- Bot `_fetch_mam`: oda arşivi odanın kendisinden (jid=) çekilir; is_me
  takma adla (resource) karşılaştırılır; gönderen adı resource'tan gelir.
- `mam_results` işlenince oda girişinde gönderen nick'tir (oda adı değil).
"""
import asyncio
import os
import queue
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _win  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import archive as arch  # noqa: E402

ROOM = "oda@chat.x"


def _recorder():
    calls = []

    def fetch_mam(*a, **k):
        calls.append((a, k))

    return types.SimpleNamespace(fetch_mam=fetch_mam), calls


def test_room_initial_mam_fetch():
    w = _win([], jid=ROOM)
    w.rooms = {ROOM}
    w.bot, calls = _recorder()
    w.active = ROOM
    xmpp.MainWindow._load_mam_history(w)
    assert calls, "boş geçmişli oda için MAM isteği gitmedi"
    assert calls[0][0][0] == ROOM


def test_room_older_mam_fetch():
    w = _win([], jid=ROOM)
    w.rooms = {ROOM}
    w.active = ROOM
    w._mam_oldest[ROOM] = "arc-1"
    w.bot, calls = _recorder()
    xmpp.MainWindow._load_older_mam(w)
    assert calls, "odada eski sayfa isteği gitmedi"
    a, k = calls[0]
    assert a[0] == ROOM and k.get("before") == "arc-1"


def test_room_mam_sender_is_nick():
    w = _win([], jid=ROOM)
    w.rooms = {ROOM}
    xmpp.MainWindow._handle(w, "mam_results", {
        "jid": ROOM, "token": 0, "messages": [
            {"from": ROOM, "body": "selam", "ts": "2026-10-15T10:00:00Z",
             "is_me": False, "mid": "M1", "nick": "ayse"},
            {"from": ROOM, "body": "ben de", "ts": "",
             "is_me": True, "mid": "M2", "nick": "ben"},
        ]})
    entries = w.chats[ROOM]
    assert entries[0][0] == "ayse"          # gönderen nick, oda adı değil
    assert entries[1][0] == "Ben"
    assert entries[1][2] is True


# ── Bot: oda arşivi hedefi, is_me ve nick ───────────────────────────────────
class _J:
    def __init__(self, bare, resource=""):
        self.bare, self.resource = bare, resource

    def __str__(self):
        return f"{self.bare}/{self.resource}" if self.resource else self.bare


class _Stanza(dict):
    """MAM forwarded stanza'sının bot kodunun dokunduğu yüzeyi."""

    def get(self, key, default=None):
        return dict.get(self, key, default)


def _mam_result(body, frm, mid="", raw_id="", ts="2026-10-15T10:00:00Z"):
    m = _Stanza({"from": frm, "body": body, "id": raw_id})
    msg = {
        "mam_result": {
            "forwarded": _Fwd(_Stanza(m), ts),
            "id": mid,
        },
    }
    return msg


class _Fwd(dict):
    def __init__(self, stanza, ts):
        super().__init__()
        self["stanza"] = stanza
        self._ts = ts

    def get(self, key, default=None):
        if key == "delay":
            return {"stamp": self._ts} if self._ts else {}
        return dict.get(self, key, default)


class _Pager:
    """slixmpp RSM yineleyicisi: her `next()` bir sayfa döndürür."""

    def __init__(self, results):
        self.results = results
        self.used = False

    async def next(self):
        if self.used:
            raise StopAsyncIteration
        self.used = True
        return {"mam": {"results": self.results}}


class _FakeMam:
    def __init__(self, results):
        self.results = results
        self.kw = None

    def retrieve(self, **kw):
        self.kw = kw
        if kw.get("iterator"):
            return _Pager(self.results)

        async def _one():
            return {"mam": {"results": self.results}}
        return _one()


def _bot_stub(room=True):
    return types.SimpleNamespace(
        my_nicks={ROOM: "ben"} if room else {},
        boundjid=types.SimpleNamespace(bare="ben@x.im"),
        gui_q=queue.Queue(),
    )


def test_bot_fetch_mam_room_targeting(monkeypatch):
    results = [_mam_result("merhaba", _J(ROOM, "ayse"), mid="S1",
                           raw_id="R1")]
    fake = _FakeMam(results)
    monkeypatch.setattr(arch, "_get_xep", lambda bot, name: fake)
    bot = _bot_stub(room=True)
    asyncio.run(arch.ArchiveMixin._fetch_mam(bot, ROOM, 50))
    kind, data = bot.gui_q.get_nowait()
    assert kind == "mam_results" and not data.get("error")
    msg = data["messages"][0]
    assert fake.kw.get("jid") == ROOM          # oda arşivi odadan çekilir
    assert "with_jid" not in fake.kw
    assert msg["is_me"] is False
    assert msg["nick"] == "ayse"


def test_bot_fetch_mam_room_own_message_is_me(monkeypatch):
    results = [_mam_result("benden", _J(ROOM, "ben"), mid="S2", raw_id="R2")]
    fake = _FakeMam(results)
    monkeypatch.setattr(arch, "_get_xep", lambda bot, name: fake)
    bot = _bot_stub(room=True)
    asyncio.run(arch.ArchiveMixin._fetch_mam(bot, ROOM, 50))
    kind, data = bot.gui_q.get_nowait()
    assert data["messages"][0]["is_me"] is True   # kendi takma adımız


def test_bot_fetch_mam_private_targets_with_jid(monkeypatch):
    fake = _FakeMam([])
    monkeypatch.setattr(arch, "_get_xep", lambda bot, name: fake)
    bot = _bot_stub(room=False)
    asyncio.run(arch.ArchiveMixin._fetch_mam(bot, "ali@x.im", 50))
    kind, data = bot.gui_q.get_nowait()
    assert fake.kw.get("with_jid") == "ali@x.im" and "jid" not in fake.kw
    assert data["messages"] == []
