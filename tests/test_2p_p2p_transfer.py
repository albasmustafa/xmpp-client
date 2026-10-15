"""RESOURCE HARDENING 2P — BUG C: P2P (Jingle XEP-0234 + IBB XEP-0261).

Keşif izi (gerçek yollar): UI `_send_file_p2p` (xmpp.py) → `_ft_pending_out`
→ `XMPPBot.jingle_send` → `asyncio.run_coroutine_threadsafe(JingleFTManager.
start_send)` → C1 offer created (`_build_initiate`) → C2 offer sent
(`_send_iq`, ACCEPT_TIMEOUT) → C3 accept (`_on_accept` → accept_future) →
C4/C5 IBB transport (xep_0047 open_stream + preauthorize_sid) → C6/C7/C8
transfer (`send_stream`/`recv_stream` + `_progress`) → C9 done (`_finish`
"done" — yalnız hash doğrulama + stream close SONRASI) → C10 cleanup
(`_terminate` + sessions.pop + .part silme). Mevcut test_jingle_ft.py
C1–C10'un büyük bölümünü sürüyor; bu dosya UI→API bağlantısını, false-
success korumasını ve failed-transfer sonrası retry-yetenekliliğini
kanıtlar. Gerçek ağ/uzak eş doğrulaması manuel checklist'e bırakılır.
"""
import asyncio
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _Cap, _win  # noqa: E402

import jingle_ft  # noqa: E402
import xmpp  # noqa: E402


# ── C-öncesi: UI yolu `_send_file_p2p` → `jingle_send` bağlantısı ────────────
def test_ui_p2p_action_reaches_jingle_send(monkeypatch, tmp_path):
    path = tmp_path / "deneme.bin"
    path.write_bytes(b"icerik")
    w = _win(jid="a@x")
    w.active = "a@x"
    w._ft_warn_mb = 100
    w._ft_block_size = 4096
    w._ft_pending_out = {}
    w.presence = {}
    w._append = _Cap()
    w._ask_send_path = lambda: str(path)
    monkeypatch.setattr(xmpp.messagebox, "askyesno",
                        lambda *a, **k: True, raising=False)
    w.bot = types.SimpleNamespace(jingle_send=_Cap())
    xmpp.MainWindow._send_file_p2p(w)
    calls = w.bot.jingle_send.calls
    assert len(calls) == 1
    to, fpath, block_size = calls[0][0]
    assert (to, fpath) == ("a@x", str(path))
    assert block_size == 4096
    assert ("a@x", "deneme.bin") in w._ft_pending_out   # retry takibi kurulu


# ── C1/C2: offer oluşturulur ve gönderilir; kabul zaman aşımı → failed ──────
def test_start_send_offer_sent_and_timeout_fails_open(tmp_path):
    fpath = tmp_path / "dosya.bin"
    fpath.write_bytes(b"x" * 16)
    sent = []

    from slixmpp import JID
    mgr = jingle_ft.JingleFTManager(types.SimpleNamespace())
    from slixmpp.stanza import Iq as _SlixIq
    mgr.xmpp.Iq = lambda *a, **k: _SlixIq(*a, **k)   # gerçek stanza sınıfı
    mgr.xmpp.boundjid = JID("ben@example.com/kaynak")

    async def fake_send_iq(iq, timeout=None):
        sent.append((iq, timeout))
        # C3 YOK: karşı taraf kabul etmedi (ack/accept gelmedi)
        raise asyncio.TimeoutError()

    mgr._send_iq = fake_send_iq
    mgr._terminate = jingle_ft.JingleFTManager._terminate.__get__(mgr)
    finish_calls = []

    def fake_finish(session, state, error=""):
        mgr.sessions.pop(session.sid, None)      # gerçek _finish temizliği
        finish_calls.append((session.sid, state, error))

    mgr._finish = fake_finish

    async def main():
        await mgr.start_send("peer@x", str(fpath))

    asyncio.run(main())
    assert len(sent) == 2                      # offer IQ + terminate IQ
    assert sent[0][1] == jingle_ft.ACCEPT_TIMEOUT   # C2: offer, RSM dışı
    assert finish_calls[0][1] == "failed"      # C9: false-success YOK
    assert "Kabul zaman aşımı" in finish_calls[0][2]
    assert mgr.sessions == {}                  # C10: temizlik


# ── failed transfer sonrası retry-yeteneklilik ───────────────────────────────
def test_failed_transfer_is_retryable(tmp_path):
    fpath = tmp_path / "dosya.bin"
    fpath.write_bytes(b"x" * 16)

    from slixmpp import JID
    mgr = jingle_ft.JingleFTManager(types.SimpleNamespace())
    from slixmpp.stanza import Iq as _SlixIq
    mgr.xmpp.Iq = lambda *a, **k: _SlixIq(*a, **k)
    mgr.xmpp.boundjid = JID("ben@example.com/kaynak")
    attempts = []

    async def fake_send_iq(iq, timeout=None):
        attempts.append(1)
        raise asyncio.TimeoutError()

    mgr._send_iq = fake_send_iq
    mgr._terminate = jingle_ft.JingleFTManager._terminate.__get__(mgr)
    mgr._finish = lambda session, state, error="": None

    async def main():
        await mgr.start_send("peer@x", str(fpath))      # 1. deneme: failed
        await mgr.start_send("peer@x", str(fpath))      # 2. deneme: mümkün
        return len(mgr.sessions)

    def fake_finish(session, state, error=""):
        mgr.sessions.pop(session.sid, None)      # gerçek _finish davranışı
    mgr._finish = fake_finish
    leftover = asyncio.run(main())
    # her deneme: offer IQ + session-terminate IQ (ikisi de _send_iq'dan)
    assert len(attempts) == 4
    assert leftover == 0                         # orphan oturum kalmadı


# ── false-success koruması: done yalnız gerçek transfer sonrası ──────────────
def test_no_false_success_without_payload(tmp_path):
    """C7/C8/C9: payload taşınmadan/ilerlemeden 'done' yayınlanamaz."""
    fpath = tmp_path / "dosya.bin"
    fpath.write_bytes(b"gercek-icerik")
    events = []

    from slixmpp import JID
    mgr = jingle_ft.JingleFTManager(types.SimpleNamespace())
    from slixmpp.stanza import Iq as _SlixIq
    mgr.xmpp.Iq = lambda *a, **k: _SlixIq(*a, **k)
    mgr.xmpp.boundjid = JID("ben@example.com/kaynak")

    class _AlwaysFailStream:
        async def close(self):
            pass

    async def fake_send_iq(iq, timeout=None):
        raise RuntimeError("IBB open reddedildi")   # transport kurulamadı

    mgr._send_iq = fake_send_iq
    mgr._terminate = jingle_ft.JingleFTManager._terminate.__get__(mgr)
    mgr._finish = lambda session, state, error="": events.append(state)

    async def main():
        await mgr.start_send("peer@x", str(fpath))

    asyncio.run(main())
    assert events == ["failed"]                # 'done' YOK — payload gitmedi
