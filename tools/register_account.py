#!/usr/bin/env python3
"""XMPP sunucusunda IBR (XEP-0077) ile test hesabı oluştur.

Kullanım:
    .venv-xmpp/bin/python tools/register_account.py SUNUCU KULLANICI ŞİFRE

Örnek:
    .venv-xmpp/bin/python tools/register_account.py trashserver.net deneme123 sifre123
"""

import asyncio
import sys

from slixmpp import ClientXMPP


class RegisterBot(ClientXMPP):
    def __init__(self, jid, password, timeout=25):
        super().__init__(jid, password)
        self.register_plugin("xep_0077")
        self.add_event_handler("register", self._on_register)
        self.add_event_handler("session_start", self._on_start)
        self.done = asyncio.get_running_loop().create_future()
        self.timeout = timeout

    async def _on_register(self, form):
        try:
            iq = self.Iq()
            iq["type"] = "set"
            iq["register"]["username"] = self.boundjid.user
            iq["register"]["password"] = self.password
            result = await iq.send(timeout=self.timeout)
            print("KAYIT BAŞARILI:", result["type"])
            self.done.set_result(True)
        except Exception as e:
            print("KAYIT HATASI:", e)
            self.done.set_exception(e)

    def _on_start(self, event):
        print("Oturum açıldı (kayıt sonrası):", self.boundjid)
        if not self.done.done():
            self.done.set_result(True)

    async def _run(self):
        self.connect()
        try:
            await asyncio.wait_for(self.done, timeout=self.timeout)
        except asyncio.TimeoutError:
            print("ZAMAN AŞIMI: sunucu IBR sunmuyor olabilir")
            return False
        except Exception:
            return False
        finally:
            self.disconnect()
        return True


async def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    server, user, password = sys.argv[1:4]
    jid = f"{user}@{server}"
    bot = RegisterBot(jid, password)
    ok = await bot._run()
    await asyncio.sleep(1)
    print("SONUÇ:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
