"""Basit, durumsuz bilgi dialogları (Faz 4A).

Kurallar:
- MainWindow state'ine doğrudan erişim yok; gereken veri parametre gelir.
- Tema renkleri/yardımcı fonksiyonlar çağrı anında `xmpp` modülünden
  okunur (`_app()`), böylece canlı tema geçişleri çalışmaya devam eder ve
  döngüsel import oluşmaz.
- Public davranış (başlık, boyut, içerik, kapatma) xmpp.py'deki
  taşınmadan önceki haliyle birebir aynıdır.
"""
import tkinter as tk
from tkinter import ttk


def _app():
    """Canlı tema/sabitler için xmpp modülünü çağrı anında getir."""
    import xmpp as _app_mod
    return _app_mod


def show_shortcuts(parent):
    """Klavye kısayolları listesi penceresi (MainWindow._shortcuts_dialog)."""
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Klavye Kısayolları")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("400x560")
    dlg.transient(parent)

    tk.Label(dlg, text="⌨ Klavye Kısayolları", font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 12))

    shortcuts = [
        ("Ctrl+F", "Sohbette Ara"),
        ("Ctrl+K", "Hızlı Geçiş (kişi/oda)"),
        ("Ctrl+N", "Yeni Sohbet"),
        ("Ctrl+E", "Emoji Paneli"),
        ("Ctrl+R", "Son mesaja yanıtla"),
        ("Ctrl+Shift+E", "Son mesajımı düzenle"),
        ("Ctrl+Shift+D", "Son mesajımı sil"),
        ("Ctrl+Shift+M", "✨ Neler kaçırdım? (AI özeti)"),
        ("Ctrl+Shift+H", "✨ Geçmişe sor (AI)"),
        ("Ctrl+Shift+S", "✨ Sesle yaz (dikte)"),
        ("Üzerine gel", "Eylem butonları (yanıtla/tepki/… )"),
        ("Çift tık", "Mesajı yanıtla (alıntı)"),
        ("Tepkiye tıkla", "Tepkini ekle / kaldır"),
        ("Ctrl+B", "Yedekleme"),
        ("Ctrl+,", "Ayarlar"),
        ("Ctrl+?", "Bu menü"),
        ("Escape", "Aramayı kapat"),
        ("Enter", "Mesaj gönder"),
        ("Ctrl+V", "Yapıştır (resim/metin)"),
    ]

    for key, desc in shortcuts:
        row = tk.Frame(dlg, bg=A.BG_CARD, padx=16)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=key, font=("Courier", 10, "bold"),
                 fg=A.ACCENT, bg=A.BG_CARD, width=12,
                 anchor="w").pack(side="left")
        tk.Label(row, text=desc, font=(A.FONT, 9),
                 fg=A.FG, bg=A.BG_CARD).pack(side="left", padx=(8, 0))

    ttk.Button(dlg, text="Kapat",
               command=dlg.destroy).pack(pady=16)


def show_reaction_details(parent, reactions, emoji=None):
    """Tepki verenleri listeleyen pencere.

    `reactions`: {emoji: [sender, ...]} — MainWindow state'ine erişilmez,
    veri parametre olarak gelir (MainWindow._reaction_details_dialog).
    """
    if not reactions:
        return
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Tepkiler")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("300x340")
    dlg.transient(parent)
    A._safe_grab_set(dlg)
    tk.Label(dlg, text="😊 Tepkiler", font=(A.FONT, 11, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=14, pady=(14, 6), anchor="w")
    pairs = list(reactions.items()) if emoji is None else [
        (emoji, reactions.get(emoji, []))]
    shown = 0
    for em, senders in pairs:
        if not senders:
            continue
        tk.Label(dlg, text=f"{em}  ({len(senders)})",
                 font=(A.FONT, 11, "bold"), fg=A.ACCENT, bg=A.BG_CARD
                 ).pack(padx=16, pady=(8, 2), anchor="w")
        for sender in senders[:12]:
            tk.Label(dlg, text=f"• {sender}", font=(A.FONT, 9),
                     fg=A.FG, bg=A.BG_CARD).pack(padx=26, anchor="w")
        shown += 1
    if shown == 0:
        tk.Label(dlg, text="(tepki yok)", fg=A.FG_DIM, bg=A.BG_CARD
                 ).pack(padx=16, pady=6)
    ttk.Button(dlg, text="Kapat", command=dlg.destroy).pack(pady=14)
