"""jingle_ft çekirdek birim testleri (ağsız)."""

import asyncio
import base64
import hashlib
import os
import queue
import sys
from unittest.mock import AsyncMock
from xml.etree import ElementTree as StdET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp import Iq  # noqa: E402
from slixmpp.xmlstream import tostring  # noqa: E402

import jingle_ft  # noqa: E402


def _make_initiate():
    jingle_ft.register_stanza_plugins()
    iq = Iq()
    iq["type"] = "set"
    iq["to"] = "kisi@example.com/phone"
    j = iq["jingle"]
    j["action"] = "session-initiate"
    j["sid"] = "jsid-1"
    j["initiator"] = "ben@example.com/laptop"

    content = jingle_ft.Content()
    content["creator"] = "initiator"
    content["name"] = "file"

    f = jingle_ft.File()
    f["name"] = "rapor.pdf"
    f["size"] = 12345
    f["media-type"] = "application/pdf"
    f["desc"] = "aylık rapor"
    jingle_ft.set_file_hash(f, b"\x00" * 32)

    t = jingle_ft.TransportIBB()
    t["sid"] = "ibb-1"
    t["block_size"] = 4096
    t["stanza"] = "iq"

    desc = jingle_ft.Description()
    desc["file"] = f
    content["description"] = desc
    content["senders"] = "initiator"
    content["transport_ibb"] = t
    j["content"] = content
    return iq


def test_initiate_roundtrip():
    iq = _make_initiate()
    xml = tostring(iq.xml)
    assert "urn:xmpp:jingle:1" in xml
    assert "action=\"session-initiate\"" in xml
    assert "rapor.pdf" in xml
    assert "urn:xmpp:jingle:transports:ibb:1" in xml
    assert "urn:xmpp:hashes:2" in xml
    assert "urn:xmpp:jingle:apps:file-transfer:5" in xml

    parsed = Iq(xml=StdET.fromstring(xml))
    j = parsed["jingle"]
    assert j["action"] == "session-initiate"
    assert j["sid"] == "jsid-1"
    content = j["content"]
    assert content["creator"] == "initiator"
    assert content["senders"] == "initiator"
    f = content["description"]["file"]
    assert f["name"] == "rapor.pdf"
    assert f["size"] == 12345
    assert f["media-type"] == "application/pdf"
    algo, digest = jingle_ft.get_file_hash(f)
    assert algo == "sha-256"
    t = content["transport_ibb"]
    assert t["sid"] == "ibb-1"
    assert t["block_size"] == 4096
    assert t["stanza"] == "iq"


def test_reason_roundtrip():
    jingle_ft.register_stanza_plugins()
    for tag in ("success", "cancel", "decline", "failed"):
        reason = jingle_ft.Reason()
        reason[tag] = True
        reason["text"] = "sebep"
        parsed = jingle_ft.Reason(xml=StdET.fromstring(tostring(reason.xml)))
        assert parsed[tag] is True
        assert parsed["text"] == "sebep"


def test_sanitize_filename():
    assert jingle_ft.sanitize_filename("rapor.pdf") == "rapor.pdf"
    assert jingle_ft.sanitize_filename("../../etc/passwd") == "passwd"
    assert jingle_ft.sanitize_filename("a\\b\\c.txt") == "c.txt"
    assert jingle_ft.sanitize_filename("") == ""
    assert jingle_ft.sanitize_filename("..") == ""
    assert jingle_ft.sanitize_filename(".") == ""
    assert jingle_ft.sanitize_filename("x\x00y.txt") == "xy.txt"


def test_unique_download_path(tmp_path):
    first = jingle_ft.unique_download_path(str(tmp_path), "rapor.pdf")
    assert first == str(tmp_path / "rapor.pdf")
    (tmp_path / "rapor.pdf").write_bytes(b"x")
    second = jingle_ft.unique_download_path(str(tmp_path), "rapor.pdf")
    assert second == str(tmp_path / "rapor (1).pdf")
    (tmp_path / "rapor (1).pdf").write_bytes(b"x")
    third = jingle_ft.unique_download_path(str(tmp_path), "rapor.pdf")
    assert third == str(tmp_path / "rapor (2).pdf")


def test_unique_download_path_sanitizes(tmp_path):
    path = jingle_ft.unique_download_path(str(tmp_path), "../../etc/passwd")
    assert os.path.dirname(path) == str(tmp_path)
    assert os.path.basename(path) == "passwd"


def test_unique_download_path_empty_name(tmp_path):
    path = jingle_ft.unique_download_path(str(tmp_path), "..")
    assert os.path.basename(path) == "dosya"


def test_format_helpers():
    assert jingle_ft.format_size(0) == "0 B"
    assert jingle_ft.format_size(1024) == "1.0 KB"
    assert jingle_ft.format_size(1536) == "1.5 KB"
    assert jingle_ft.format_size(5 * 1024 ** 2) == "5.0 MB"
    assert jingle_ft.format_speed(2048) == "2.0 KB/s"
    assert jingle_ft.format_eta(0) == "00:00"
    assert jingle_ft.format_eta(83) == "01:23"
    assert jingle_ft.format_eta(3723) == "01:02:03"


def test_guess_media_type(tmp_path):
    p = tmp_path / "belge.pdf"
    p.write_bytes(b"x")
    assert jingle_ft.guess_media_type(str(p)) == "application/pdf"
    assert jingle_ft.guess_media_type(str(tmp_path / "bilinmeyen")) == \
        "application/octet-stream"


class _FakeStream:
    """Test için sahte IBB akışı."""
    def __init__(self, incoming=b""):
        self.sent = bytearray()
        self.closed = False
        self.recv_queue = asyncio.Queue()
        for i in range(0, len(incoming), 4096):
            self.recv_queue.put_nowait(incoming[i:i + 4096])

    async def send(self, data, timeout=None):
        self.sent.extend(data)
        return len(data)

    async def close(self):
        self.closed = True


def test_parse_offer():
    iq = _make_initiate()
    offer = jingle_ft.parse_offer(iq)
    assert offer["sid"] == "jsid-1"
    assert offer["name"] == "rapor.pdf"
    assert offer["size"] == 12345
    assert offer["mime"] == "application/pdf"
    assert offer["desc"] == "aylık rapor"
    assert offer["hash_algo"] == "sha-256"
    assert offer["ibb_sid"] == "ibb-1"
    assert offer["block_size"] == 4096


def test_send_stream(tmp_path):
    src = tmp_path / "veri.bin"
    payload = bytes(range(256)) * 100  # 25600 bayt
    src.write_bytes(payload)

    session = jingle_ft.FTSession(
        sid="s1", peer="p@x/y", initiator=True,
        size=len(payload), block_size=4096, filepath=str(src))
    stream = _FakeStream()
    progress = []
    digest = asyncio.run(jingle_ft.send_stream(
        session, stream, str(src), lambda d, t: progress.append((d, t))))

    assert bytes(stream.sent) == payload
    assert digest == base64.b64encode(hashlib.sha256(payload).digest()).decode()
    assert progress[-1] == (len(payload), len(payload))


def test_recv_stream(tmp_path):
    payload = bytes(range(256)) * 100
    session = jingle_ft.FTSession(
        sid="s2", peer="p@x/y", initiator=False,
        size=len(payload), block_size=4096, filepath="")
    stream = _FakeStream(incoming=payload)
    part = tmp_path / "hedef.bin.part"
    progress = []
    digest = asyncio.run(jingle_ft.recv_stream(
        session, stream, str(part), lambda d, t: progress.append((d, t))))

    assert part.read_bytes() == payload
    assert digest == base64.b64encode(hashlib.sha256(payload).digest()).decode()
    assert progress[-1] == (len(payload), len(payload))


def test_recv_stream_size_overflow(tmp_path):
    session = jingle_ft.FTSession(
        sid="s3", peer="p@x/y", initiator=False, size=10, block_size=4096)
    stream = _FakeStream(incoming=b"x" * 4096)

    async def _run():
        with pytest.raises(ValueError):
            await jingle_ft.recv_stream(session, stream, str(tmp_path / "a.part"),
                                        lambda d, t: None)
    asyncio.run(_run())


class _FakeXMPP:
    def __init__(self, gui_q):
        self.gui_q = gui_q
        self.boundjid = type("J", (), {"full": "ben@example.com/laptop"})()
        self.plugin = {}
        self.sent = []

    def Iq(self):  # noqa: N802 - slixmpp API'si
        from slixmpp import Iq as RealIq
        iq = RealIq()
        iq.stream = None
        self.sent.append(iq)
        return iq


def test_is_capable_caches():
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)

    disco = AsyncMock()

    class _Info:
        def __getitem__(self, key):
            return {"features": ["urn:xmpp:jingle:1",
                                 "urn:xmpp:jingle:transports:ibb:1"]}
    disco.get_info = AsyncMock(return_value=_Info())
    xmpp.plugin["xep_0030"] = disco

    ok1 = asyncio.run(mgr.is_capable("kisi@example.com"))
    ok2 = asyncio.run(mgr.is_capable("kisi@example.com/phone"))
    assert ok1 is True and ok2 is True
    assert disco.get_info.await_count == 1  # bare JID önbelleği


def test_send_flow_emits_progress_and_done(tmp_path):
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    payload = b"merhaba dunya" * 1000
    src = tmp_path / "selam.txt"
    src.write_bytes(payload)
    stream = _FakeStream()
    xmpp.plugin["xep_0047"] = type(
        "P", (), {"open_stream": staticmethod(AsyncMock(return_value=stream))})()

    async def _run():
        mgr._terminate = AsyncMock()
        async def fake_send_iq(iq, timeout=None):
            if iq["jingle"]["action"] == "session-initiate":
                sid = iq["jingle"]["sid"]
                mgr.sessions[sid].accept_future.set_result(True)
        mgr._send_iq = fake_send_iq
        await mgr.start_send("kisi@example.com/phone", str(src))

    asyncio.run(_run())

    events = [q.get_nowait() for _ in range(q.qsize())]
    kinds = [k for k, _ in events]
    assert "ft_progress" in kinds
    assert "ft_done" in kinds
    assert bytes(stream.sent) == payload
    ok = [d for k, d in events if k == "ft_progress"][-1]
    assert ok["done"] == len(payload) == ok["total"]


def test_start_send_respects_block_size(tmp_path):
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    src = tmp_path / "b.bin"
    src.write_bytes(b"x" * 100)
    seen = {}

    async def _run():
        mgr._terminate = AsyncMock()

        async def fake_send_iq(iq, timeout=None):
            if iq["jingle"]["action"] == "session-initiate":
                sid = iq["jingle"]["sid"]
                seen["block"] = iq["jingle"]["content"]["transport_ibb"]["block_size"]
                mgr.sessions[sid].accept_future.set_result(True)
        mgr._send_iq = fake_send_iq
        stream = _FakeStream()
        xmpp.plugin["xep_0047"] = type(
            "P", (), {"open_stream": staticmethod(AsyncMock(return_value=stream))})()
        await mgr.start_send("kisi@example.com/phone", str(src), block_size=8192)

    asyncio.run(_run())
    assert seen["block"] == 8192


def test_handle_initiate_emits_offer_and_pending():
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    iq = _make_initiate()
    iq["id"] = "iq-1"
    iq["from"] = "kisi@example.com/phone"
    asyncio.run(mgr.handle_jingle_iq(iq))

    assert "jsid-1" in mgr.sessions
    assert mgr.sessions["jsid-1"].state == "pending"
    events = [q.get_nowait() for _ in range(q.qsize())]
    assert events[0][0] == "ft_offer"
    offer = events[0][1]
    assert offer["name"] == "rapor.pdf"
    assert offer["size"] == 12345
    assert offer["peer"] == "kisi@example.com/phone"


def test_block_size_clamped():
    assert jingle_ft.clamp_block_size(-1) == jingle_ft.DEFAULT_BLOCK_SIZE
    assert jingle_ft.clamp_block_size(0) == jingle_ft.DEFAULT_BLOCK_SIZE
    assert jingle_ft.clamp_block_size(1024 * 1024) == jingle_ft.MAX_BLOCK_SIZE
    assert jingle_ft.clamp_block_size(2048) == 2048


def test_initiate_negative_block_size_clamped():
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    iq = _make_initiate()
    iq["from"] = "kisi@example.com/phone"
    iq["jingle"]["content"]["transport_ibb"]["block_size"] = -1
    asyncio.run(mgr.handle_jingle_iq(iq))
    assert mgr.sessions[iq["jingle"]["sid"]].block_size == jingle_ft.DEFAULT_BLOCK_SIZE


def test_handle_initiate_rejects_missing_size():
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    iq = _make_initiate()
    iq["from"] = "kisi@example.com/phone"
    iq["jingle"]["content"]["description"]["file"]["size"] = 0
    from slixmpp.exceptions import XMPPError
    try:
        asyncio.run(mgr.handle_jingle_iq(iq))
        assert False, "XMPPError bekleniyordu"
    except XMPPError:
        pass


def test_handle_unknown_sid_raises():
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    iq = _make_initiate()
    iq["jingle"]["action"] = "session-accept"
    iq["jingle"]["sid"] = "yok"
    from slixmpp.exceptions import XMPPError
    try:
        asyncio.run(mgr.handle_jingle_iq(iq))
        assert False, "XMPPError bekleniyordu"
    except XMPPError:
        pass


def test_accept_transfers_and_verifies(tmp_path):
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    payload = b"dosya icerigi" * 500

    iq = _make_initiate()
    iq["from"] = "kisi@example.com/phone"
    iq["jingle"]["content"]["description"]["file"]["size"] = len(payload)
    jingle_ft.set_file_hash(iq["jingle"]["content"]["description"]["file"],
                            hashlib.sha256(payload).digest())
    asyncio.run(mgr.handle_jingle_iq(iq))
    sid = iq["jingle"]["sid"]

    stream = _FakeStream(incoming=payload)

    async def _run():
        mgr._send_iq = AsyncMock(return_value=None)
        mgr._terminate = AsyncMock()
        preauth = {"called": False}
        xmpp.plugin["xep_0047"] = type("P", (), {
            "api": {"preauthorize_sid": lambda *a: preauth.update(called=True)},
        })()
        target = tmp_path / "indirilen.bin"

        async def fake_wait(ibb_sid, peer, timeout):
            return stream
        mgr._wait_stream = fake_wait
        await mgr.accept(sid, str(target))
        assert preauth["called"]
        assert target.read_bytes() == payload
        # geçici dosya kalmamalı
        assert not (tmp_path / "indirilen.bin.part").exists()
    asyncio.run(_run())
    events = [q.get_nowait() for _ in range(q.qsize())]
    assert any(k == "ft_done" for k, _ in events)


def test_accept_hash_mismatch_removes_part(tmp_path):
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    payload = b"yanlis hash" * 100

    iq = _make_initiate()
    iq["from"] = "kisi@example.com/phone"
    iq["jingle"]["content"]["description"]["file"]["size"] = len(payload)
    jingle_ft.set_file_hash(iq["jingle"]["content"]["description"]["file"],
                            hashlib.sha256(b"beklenen").digest())
    asyncio.run(mgr.handle_jingle_iq(iq))
    sid = iq["jingle"]["sid"]

    async def _run():
        mgr._send_iq = AsyncMock(return_value=None)
        mgr._terminate = AsyncMock()
        xmpp.plugin["xep_0047"] = type("P", (), {"api": {"preauthorize_sid": lambda *a: None}})()
        target = tmp_path / "bozuk.bin"

        async def fake_wait(ibb_sid, peer, timeout):
            return _FakeStream(incoming=payload)
        mgr._wait_stream = fake_wait
        await mgr.accept(sid, str(target))
        assert not target.exists()
        assert not (tmp_path / "bozuk.bin.part").exists()
    asyncio.run(_run())
    events = [q.get_nowait() for _ in range(q.qsize())]
    assert any(k == "ft_error" for k, _ in events)


def test_remote_success_terminate_does_not_cancel_transfer(tmp_path):
    """Karşı taraf success terminate gönderince yerel başarı bozulmamalı."""
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    payload = b"basarili transfer" * 100
    iq = _make_initiate()
    iq["from"] = "kisi@example.com/phone"
    iq["jingle"]["content"]["description"]["file"]["size"] = len(payload)
    jingle_ft.set_file_hash(iq["jingle"]["content"]["description"]["file"],
                            hashlib.sha256(payload).digest())
    asyncio.run(mgr.handle_jingle_iq(iq))
    sid = iq["jingle"]["sid"]

    async def _run():
        mgr._send_iq = AsyncMock(return_value=None)
        mgr._terminate = AsyncMock()
        xmpp.plugin["xep_0047"] = type(
            "P", (), {"api": {"preauthorize_sid": lambda *a: None}})()
        target = tmp_path / "tamam.bin"

        async def fake_wait(ibb_sid, peer, timeout):
            return _FakeStream(incoming=payload)
        mgr._wait_stream = fake_wait
        # Transfer sürerken karşı taraftan success terminate gelir
        term = jingle_ft.Iq()
        term["type"] = "set"
        term["from"] = "kisi@example.com/phone"
        term["jingle"]["action"] = "session-terminate"
        term["jingle"]["sid"] = sid
        r = jingle_ft.Reason()
        r["success"] = True
        term["jingle"]["reason"] = r
        await mgr.handle_jingle_iq(term)
        await mgr.accept(sid, str(target))
        assert target.read_bytes() == payload
    asyncio.run(_run())

    events = [q.get_nowait() for _ in range(q.qsize())]
    assert not any(k == "ft_error" for k, _ in events)
    assert any(k == "ft_done" for k, _ in events)


def test_remote_cancel_terminate_removes_part(tmp_path):
    """cancel terminate .part'ı siler ve ft_error yayar."""
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    iq = _make_initiate()
    iq["from"] = "kisi@example.com/phone"
    asyncio.run(mgr.handle_jingle_iq(iq))
    sid = iq["jingle"]["sid"]
    target = tmp_path / "yarim.bin"
    target.with_suffix(".bin.part").write_bytes(b"yarim")
    mgr.sessions[sid].filepath = str(target)
    mgr.sessions[sid].state = "transferring"

    term = jingle_ft.Iq()
    term["type"] = "set"
    term["from"] = "kisi@example.com/phone"
    term["jingle"]["action"] = "session-terminate"
    term["jingle"]["sid"] = sid
    r = jingle_ft.Reason()
    r["cancel"] = True
    term["jingle"]["reason"] = r
    asyncio.run(mgr.handle_jingle_iq(term))

    assert not (tmp_path / "yarim.bin.part").exists()
    events = [q.get_nowait() for _ in range(q.qsize())]
    assert any(k == "ft_error" for k, _ in events)


def test_remote_decline_wakes_sender_without_timeout():
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)

    async def _run():
        mgr._terminate = AsyncMock()
        mgr._ack = lambda iq: None
        started = asyncio.Event()
        sid_box = {}

        async def fake_send_iq(iq, timeout=None):
            if iq["jingle"]["action"] == "session-initiate":
                sid_box["sid"] = iq["jingle"]["sid"]
                started.set()
        mgr._send_iq = fake_send_iq

        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "d.bin"
            src.write_bytes(b"veri" * 1000)
            task = asyncio.ensure_future(mgr.start_send("kisi@example.com/phone", str(src)))
            await asyncio.wait_for(started.wait(), 2)
            term = jingle_ft.Iq()
            term["type"] = "set"
            term["from"] = "kisi@example.com/phone"
            term["jingle"]["action"] = "session-terminate"
            term["jingle"]["sid"] = sid_box["sid"]
            r = jingle_ft.Reason()
            r["decline"] = True
            term["jingle"]["reason"] = r
            await mgr.handle_jingle_iq(term)
            # Zaman aşımına kalmadan dönmeli
            await asyncio.wait_for(task, 2)
    asyncio.run(_run())

    events = [q.get_nowait() for _ in range(q.qsize())]
    kinds = [k for k, _ in events]
    assert kinds.count("ft_error") == 1, kinds
    assert not any("zaman aşımı" in str(d.get("error", "")).lower()
                   for k, d in events if k == "ft_error")


def test_error_event_includes_peer_and_state():
    """ft_error olayı, GUI fallback yönlendirmesi için peer ve state taşır."""
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    mgr._terminate = AsyncMock()
    iq = _make_initiate()
    iq["from"] = "kisi@example.com/phone"
    asyncio.run(mgr.handle_jingle_iq(iq))
    asyncio.run(mgr.decline("jsid-1"))

    events = [q.get_nowait() for _ in range(q.qsize())]
    err = [d for k, d in events if k == "ft_error"]
    assert err and err[0]["peer"] == "kisi@example.com/phone"
    assert err[0]["state"] == "declined"


def test_replaced_offer_emits_cancelled_event():
    """Aynı kişiden yeni teklif gelince eskisi GUI'ye bildirilir."""
    q = queue.Queue()
    xmpp = _FakeXMPP(q)
    mgr = jingle_ft.JingleFTManager(xmpp, q)
    mgr._ack = lambda iq: None
    mgr._terminate = AsyncMock()
    iq1 = _make_initiate()
    iq1["from"] = "kisi@example.com/phone"
    asyncio.run(mgr.handle_jingle_iq(iq1))
    iq2 = _make_initiate()
    iq2["from"] = "kisi@example.com/phone"
    iq2["jingle"]["sid"] = "jsid-2"
    asyncio.run(mgr.handle_jingle_iq(iq2))

    events = [q.get_nowait() for _ in range(q.qsize())]
    kinds = [k for k, _ in events]
    assert kinds.count("ft_error") == 1
    assert any(k == "ft_offer" for k in kinds)
    assert "jsid-1" not in mgr.sessions and "jsid-2" in mgr.sessions


def test_bot_wires_jingle_manager(monkeypatch):
    """XMPPBot, yöneticiyi kurmalı ve jingle IQ handler'ını kaydetmeli."""
    import inspect

    import xmpp as app

    src = inspect.getsource(app.XMPPBot)
    assert "JingleFTManager" in src
    assert "iq@type=set/jingle" in src
    for meth in ("jingle_send", "jingle_accept", "jingle_decline", "jingle_cancel"):
        assert hasattr(app.XMPPBot, meth)


def test_session_bind_adds_jingle_features():
    import xmpp as app

    calls = []

    class _Disco:
        def add_feature(self, feat):
            calls.append(feat)

    class _Stub:
        plugin = {"xep_0030": _Disco()}

    app.XMPPBot._on_session_bind_jingle(_Stub(), "ben@example.com/laptop")
    assert set(calls) == {
        "urn:xmpp:jingle:1",
        "urn:xmpp:jingle:apps:file-transfer:5",
        "urn:xmpp:jingle:transports:ibb:1",
    }
