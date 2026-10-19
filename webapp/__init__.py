"""Tarayıcı arayüzü: XMPPBot çekirdeğini Tk'siz çalıştıran web köprüsü.

Modüller:
  bridge  — headless oturum: XMPPBot + gui_q → WebSocket olay izdüşümü
  aiapi   — Tk'siz AI uçları (özet, çeviri, neler kaçırdım, geçmişe sor)
  server  — aiohttp REST + WebSocket + statik dosya sunumu

Thread modeli (xmpp.py'ninkiyle aynı kurallar):
  • XMPP thread'i: WebSession._run_xmpp içinde ayrı asyncio döngüsü; olaylar
    yalnız gui_q ile köprüye gelir.
  • Köprü thread'i: gui_q'yu tarar, oturum durumunu günceller, olayları
    `loop.call_soon_threadsafe` ile aiohttp döngüsündeki kanallara yollar.
  • aiohttp thread'i: REST/WS; giden komutlar bot'un thread-safe
    metotlarına (send_chat, join_room…) gider — XMPP thread'ine doğrudan
    dokunulmaz.
"""
