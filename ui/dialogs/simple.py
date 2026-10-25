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


def _tr(text):
    """Arayüz metnini seçili dile çevir (`xmpp._tr`)."""
    return _app()._tr(text)


def show_shortcuts(parent):
    """Klavye kısayolları listesi penceresi (MainWindow._shortcuts_dialog)."""
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title(_tr("Klavye Kısayolları"))
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("400x560")
    dlg.transient(parent)
    A._make_popover(dlg)

    tk.Label(dlg, text=_tr("⌨ Klavye Kısayolları"), font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 12))

    shortcuts = [
        (_tr("Ctrl+F"), _tr("Sohbette Ara")),
        (_tr("Ctrl+K"), _tr("Hızlı Geçiş (kişi/oda)")),
        (_tr("Ctrl+N"), _tr("Yeni Sohbet")),
        ("Ctrl+E", "Emoji Paneli"),
        (_tr("Ctrl+R"), _tr("Son mesaja yanıtla")),
        (_tr("Ctrl+Shift+E"), _tr("Son mesajımı düzenle")),
        (_tr("Ctrl+Shift+D"), _tr("Son mesajımı sil")),
        (_tr("Ctrl+Shift+M"), _tr("✨ Neler kaçırdım? (AI özeti)")),
        (_tr("Ctrl+Shift+H"), _tr("✨ Geçmişe sor (AI)")),
        (_tr("Ctrl+Shift+S"), _tr("✨ Sesle yaz (dikte)")),
        (_tr("Üzerine gel"), _tr("Eylem butonları (yanıtla/tepki/… )")),
        (_tr("Çift tık"), _tr("Mesajı yanıtla (alıntı)")),
        (_tr("Tepkiye tıkla"), _tr("Tepkini ekle / kaldır")),
        (_tr("Ctrl+B"), _tr("Yedekleme")),
        (_tr("Ctrl+,"), _tr("Ayarlar")),
        (_tr("Ctrl+?"), _tr("Bu menü")),
        (_tr("Escape"), _tr("Aramayı kapat")),
        (_tr("Enter"), _tr("Mesaj gönder")),
        (_tr("Ctrl+V"), _tr("Yapıştır (resim/metin)")),
    ]

    for key, desc in shortcuts:
        row = tk.Frame(dlg, bg=A.BG_CARD, padx=16)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=key, font=("Courier", 10, "bold"),
                 fg=A.ACCENT, bg=A.BG_CARD, width=12,
                 anchor="w").pack(side="left")
        tk.Label(row, text=desc, font=(A.FONT, 9),
                 fg=A.FG, bg=A.BG_CARD).pack(side="left", padx=(8, 0))

    ttk.Button(dlg, text=_tr("Kapat"),
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
    dlg.title(_tr("Tepkiler"))
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("300x340")
    dlg.transient(parent)
    A._make_popover(dlg)
    tk.Label(dlg, text=_tr("😊 Tepkiler"), font=(A.FONT, 11, "bold"),
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
        tk.Label(dlg, text=_tr("(tepki yok)"), fg=A.FG_DIM, bg=A.BG_CARD
                 ).pack(padx=16, pady=6)
    ttk.Button(dlg, text=_tr("Kapat"), command=dlg.destroy).pack(pady=14)
