#!/usr/bin/env python3
"""İki XMPP hesabı arasında Jingle (IBB) dosya transferi uçtan uca testi.

Kullanım:
    XMPP_A_JID=a@sunucu XMPP_A_PW=... \
    XMPP_B_JID=b@sunucu XMPP_B_PW=... \
    .venv-xmpp/bin/python tools/ft_e2e.py [sunucu] [port]

Test akışı:
1. İki istemci bağlanır (A gönderen, B alan).
2. B, gelen teklifi otomatik kabul eder (indirme klasörü: geçici dizin).
3. A 1 MiB rastgele dosya gönderir.
4. B'nin indirdiği dosyanın sha-256'sı kaynakla karşılaştırılır.
"""

import asyncio
import hashlib
import os
import queue
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402

TIMEOUT = 180


class _AcceptBot:
    """B tarafı: ft_offer olayını görünce otomatik kabul eder."""

    def __init__(self, bot, gui_q, download_dir):
        self.bot = bot
        self.gui_q = gui_q
        self.download_dir = download_dir
        self.done = False
        self.error = ""

    async def run(self):
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline and not self.done:
            try:
                kind, data = self.gui_q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.2)
                continue
            if kind == "ft_offer":
                target = os.path.join(self.download_dir, data["name"])
                await self.bot.ft.accept(data["sid"], target)
            elif kind == "ft_done":
                self.done = True
            elif kind == "ft_error":
                self.error = str(data.get("error", ""))
                self.done = True
        if not self.done:
            self.error = "Zaman aşımı: ft_offer/transfer tamamlanmadı"


async def run(server, port):
    jid_a, pw_a = os.environ["XMPP_A_JID"], os.environ["XMPP_A_PW"]
    jid_b, pw_b = os.environ["XMPP_B_JID"], os.environ["XMPP_B_PW"]

    qa, qb = queue.Queue(), queue.Queue()
    bot_a = xmpp.XMPPBot(jid_a, pw_a, qa)
    bot_b = xmpp.XMPPBot(jid_b, pw_b, qb)
    bot_a.loop = asyncio.get_running_loop()
    bot_b.loop = asyncio.get_running_loop()

    a_started = asyncio.Event()
    b_started = asyncio.Event()
    bot_a.add_event_handler("session_start", lambda _: a_started.set())
    bot_b.add_event_handler("session_start", lambda _: b_started.set())

    if server:
        bot_a.connect(host=server, port=port)
        bot_b.connect(host=server, port=port)
    else:
        bot_a.connect()
        bot_b.connect()

    await asyncio.wait_for(a_started.wait(), 30)
    await asyncio.wait_for(b_started.wait(), 30)

    ok = False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            downloads = os.path.join(tmp, "downloads")
            os.makedirs(downloads, exist_ok=True)
            src = os.path.join(tmp, "veri.bin")
            payload = os.urandom(1024 * 1024)
            with open(src, "wb") as fh:
                fh.write(payload)
            src_hash = hashlib.sha256(payload).hexdigest()

            receiver = _AcceptBot(bot_b, qb, downloads)
            recv_task = asyncio.ensure_future(receiver.run())

            await bot_a.ft.start_send(bot_b.boundjid.full, src)
            await asyncio.wait_for(recv_task, TIMEOUT)

            target = os.path.join(downloads, "veri.bin")
            if not receiver.done or receiver.error:
                print("E2E HATA:", receiver.error or "transfer tamamlanmadı")
            elif not os.path.isfile(target):
                print("E2E HATA: indirilen dosya bulunamadı", target)
            else:
                with open(target, "rb") as fh:
                    got = hashlib.sha256(fh.read()).hexdigest()
                if got != src_hash:
                    print("E2E HATA: hash uyuşmadı", got, src_hash)
                else:
                    print("E2E BASARILI:", len(payload), "bayt")
                    ok = True
    finally:
        for bot in (bot_a, bot_b):
            try:
                bot.disconnect()
            except Exception:
                pass
        await asyncio.sleep(1)
    return ok


def main():
    server = sys.argv[1] if len(sys.argv) > 1 else ""
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5222
    ok = asyncio.run(run(server, port))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
