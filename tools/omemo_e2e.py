#!/usr/bin/env python3
"""İki XMPP hesabı arasında OMEMO uçtan uca testi.

Kullanım:
    XMPP_A_JID=a@sunucu XMPP_A_PW=... \
    XMPP_B_JID=b@sunucu XMPP_B_PW=... \
    .venv-xmpp/bin/python tools/omemo_e2e.py [sunucu] [port]

Her iki hesap da aynı sunucuda olmalı. Sertifika doğrulaması açıktır;
kendinden imzalı yerel test sunucusunda XMPP_E2E_INSECURE=1 ile kapatılır
(gerçek hesaplarla herkese açık sunucuda KAPATMAYIN: şifreler araya girene
açık kalır). Gerçek hesabın OMEMO kimliğine dokunmamak için
XMPP_CLIENT_HOME=<boş geçici dizin> önerilir (betik yeni cihaz yayımlar).
Test:
1. İki istemci bağlanır, OMEMO'nun hazır olması beklenir.
2. Karşılıklı abonelik kurulur.
3. A, B'ye OMEMO şifreli mesaj gönderir (uygulamanın kendi kod yoluyla).
4. B mesajı çözebilirse test geçer.
5. A, B'ye şifreli dosya gönderir (aesgcm://, XEP-0454; sunucuda HTTP
   Upload gerekir); B indirip çözdüğü dosya kaynakla aynıysa test geçer.
"""

import asyncio
import hashlib
import os
import queue
import ssl
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slixmpp import JID  # noqa: E402

import xmpp  # noqa: E402

TIMEOUT = 60


async def _wait_for(predicate, timeout=TIMEOUT, interval=0.25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return False


def _drain(q):
    items = []
    while True:
        try:
            items.append(q.get_nowait())
        except queue.Empty:
            return items


def _insecure_requested(env=None) -> bool:
    return (os.environ if env is None else env).get(
        "XMPP_E2E_INSECURE") == "1"


def _apply_tls(bots, insecure):
    """Sertifika doğrulamasını yalnız açıkça istenirse kapat."""
    if not insecure:
        return
    print("UYARI: TLS sertifika doğrulaması kapalı (XMPP_E2E_INSECURE=1)")
    for bot in bots:
        bot.ssl_context.check_hostname = False
        bot.ssl_context.verify_mode = ssl.CERT_NONE


async def run(server, port):
    jid_a = os.environ["XMPP_A_JID"]
    pw_a = os.environ["XMPP_A_PW"]
    jid_b = os.environ["XMPP_B_JID"]
    pw_b = os.environ["XMPP_B_PW"]

    qa, qb = queue.Queue(), queue.Queue()
    bot_a = xmpp.XMPPBot(jid_a, pw_a, qa)
    bot_b = xmpp.XMPPBot(jid_b, pw_b, qb)
    bot_a.loop = asyncio.get_running_loop()
    bot_b.loop = asyncio.get_running_loop()

    # Kendinden imzalı yerel test sunucusu: XMPP_E2E_INSECURE=1
    _apply_tls((bot_a, bot_b), _insecure_requested())

    ok = False
    try:
        if server:
            bot_a.connect(host=server, port=port)
            bot_b.connect(host=server, port=port)
        else:
            bot_a.connect()
            bot_b.connect()

        ready = await _wait_for(
            lambda: bot_a.omemo_ready and bot_b.omemo_ready)
        if not ready:
            print(f"HATA: OMEMO hazır olmadı "
                  f"(A={bot_a.omemo_ready}, B={bot_b.omemo_ready})")
            print("A kuyruğu:", _drain(qa)[-5:])
            print("B kuyruğu:", _drain(qb)[-5:])
            return 1
        print("✓ Her iki istemcide OMEMO hazır")

        bare_a, bare_b = JID(jid_a).bare, JID(jid_b).bare
        bot_a.send_presence(pto=bare_b, ptype="subscribe")
        bot_b.send_presence(pto=bare_a, ptype="subscribed")
        bot_b.send_presence(pto=bare_a, ptype="subscribe")
        bot_a.send_presence(pto=bare_b, ptype="subscribed")
        await asyncio.sleep(2)

        # Cihaz listelerini tazele
        try:
            await bot_a["xep_0384"].refresh_device_lists({JID(bare_b)})
            await bot_b["xep_0384"].refresh_device_lists({JID(bare_a)})
        except Exception as e:
            print(f"Uyarı: cihaz listesi tazeleme: {e}")

        await _wait_for(lambda: False, timeout=1)

        test_body = f"OMEMO e2e testi {int(time.time())}"
        await bot_a._send_chat(bare_b, test_body, encryption="omemo")
        print("→ A, B'ye OMEMO mesajı gönderdi")

        found = []

        def _check():
            for kind, data in _drain(qb):
                if kind == "msg" and data.get("body") == test_body:
                    found.append(data)
                    return True
                if kind == "error":
                    print("B hata:", data)
            return False

        decrypted = await _wait_for(_check)
        if not decrypted:
            print("HATA: B mesajı çözemedi")
            print("A kuyruğu:", _drain(qa)[-8:])
            print("B kuyruğu:", _drain(qb)[-8:])
        else:
            data = found[0]
            print(f"✓ B mesajı çözdü: {data['body']!r} "
                  f"(encrypted={data.get('encrypted')})")

            # Ters yön: B → A
            test_body2 = f"OMEMO ters yön {int(time.time())}"
            await bot_b._send_chat(bare_a, test_body2, encryption="omemo")
            print("→ B, A'ya OMEMO mesajı gönderdi")

            found2 = []

            def _check_a():
                for kind, data in _drain(qa):
                    if kind == "msg" and data.get("body") == test_body2:
                        found2.append(data)
                        return True
                    if kind == "error":
                        print("A hata:", data)
                return False

            if await _wait_for(_check_a):
                print(f"✓ A mesajı çözdü: {found2[0]['body']!r}")
                ok = await _encrypted_file_step(bot_a, qb, bare_b)
            else:
                print("HATA: A mesajı çözemedi")
                print("A kuyruğu:", _drain(qa)[-8:])
                print("B kuyruğu:", _drain(qb)[-8:])
    finally:
        for bot in (bot_a, bot_b):
            try:
                bot.disconnect()
            except Exception:
                pass
        await asyncio.sleep(1)

    print("SONUÇ:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


async def _encrypted_file_step(bot_a, qb, bare_b):
    """A → B şifreli dosya; B bağlantıyı indirip çözer, özetler eşleşmeli."""
    data = os.urandom(64 * 1024)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(data)
    try:
        await bot_a._send_file_impl(bare_b, f.name, "chat",
                                    encryption="omemo")
        print("→ A, B'ye şifreli dosya gönderdi")
        links = []

        def _check():
            for kind, item in _drain(qb):
                body = item.get("body", "") if kind == "msg" else ""
                if body.startswith("aesgcm://"):
                    links.append(body)
                    return True
                if kind == "error":
                    print("B hata:", item)
            return False

        if not await _wait_for(_check):
            print("HATA: B şifreli dosya bağlantısını almadı")
            return False
        got = await asyncio.to_thread(xmpp._fetch_url_bytes, links[0],
                                      len(data) + 1024, 60)
        if hashlib.sha256(got).digest() != hashlib.sha256(data).digest():
            print("HATA: çözülen dosya kaynakla aynı değil")
            return False
        print(f"✓ B şifreli dosyayı indirip çözdü ({len(got)} bayt, "
              "sha-256 eşleşti)")
        return True
    except Exception as e:
        print(f"HATA: şifreli dosya adımı: {e}")
        return False
    finally:
        os.unlink(f.name)


def main():
    server = sys.argv[1] if len(sys.argv) > 1 else ""
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5222
    for var in ("XMPP_A_JID", "XMPP_A_PW", "XMPP_B_JID", "XMPP_B_PW"):
        if not os.environ.get(var):
            print(f"HATA: {var} ortam değişkeni gerekli")
            return 2
    return asyncio.run(run(server, port))


if __name__ == "__main__":
    sys.exit(main())
