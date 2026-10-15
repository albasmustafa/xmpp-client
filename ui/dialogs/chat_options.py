"""Sohbet seçenekleri dialogları (Faz 4A): kaybolan mesajlar, geçmiş silme.

Kurallar (ui/dialogs/simple.py ile aynı):
- MainWindow state'ine doğrudan erişim yok; veri/eylemler parametre ve
  callback ile gelir.
- Tema/yardımcı semboller çağrı anında `xmpp`'den okunur (`_app()`),
  böylece canlı tema korunur ve döngüsel import oluşmaz.
- Public davranış (başlık, boyut, metinler, onay akışı) taşınmadan önceki
  haliyle birebir aynıdır.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from ui.dialogs.simple import _app


def show_disappearing(parent, current_ttl, on_apply):
    """Kaybolan mesaj TTL seçimi (MainWindow._disappearing_dialog).

    `on_apply(ttl)` uygulama anında çağrılır; hedef sohbetin seçimi
    çağırana aittir (orijinalde `self.active` uygulama anında okunur).
    """
    A = _app()
    pop = tk.Toplevel(parent)
    pop.title("Kaybolan Mesajlar")
    pop.configure(bg=A.BG_CARD)
    pop.geometry("300x200")
    pop.transient(parent)

    tk.Label(pop, text="Kaybolan Mesajlar", fg=A.FG, bg=A.BG_CARD,
             font=(A.FONT, 12, "bold")).pack(padx=16, pady=(16, 8), anchor="w")
    tk.Label(pop, text="Mesajlar belirli süre sonra\notomatik silinir.",
             fg=A.FG_DIM, bg=A.BG_CARD, font=(A.FONT, 8)).pack(
                 padx=16, anchor="w")

    ttl_var = tk.IntVar(value=current_ttl)
    sf = tk.Frame(pop, bg=A.BG_CARD)
    sf.pack(fill="x", padx=16, pady=12)
    for val, txt in [(0, "Kapalı"), (30, "30sn"), (300, "5dk"),
                     (3600, "1sa"), (86400, "1gün")]:
        tk.Radiobutton(sf, text=txt, variable=ttl_var, value=val,
                       bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 9)).pack(
                           side="left", padx=(0, 6))

    def _apply():
        on_apply(ttl_var.get())
        pop.destroy()

    ttk.Button(pop, text="Uygula",
               command=_apply).pack(padx=16, pady=(0, 16))


def show_clear_history(parent, total, chats, has_active,
                       on_clear_active, on_clear_all):
    """Mesaj geçmişi silme penceresi (MainWindow._clear_history_dialog).

    `on_clear_active()` True dönerse bilgi kutusu gösterilir;
    `on_clear_all()` yalnızca kullanıcı onayından sonra çağrılır.
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Geçmişi Sil")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("340x220")
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    tk.Label(dlg, text="🗑 Mesaj Geçmişini Sil", font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 12))

    tk.Label(dlg, text=f"Toplam: {total} mesaj, {chats} sohbet",
             font=(A.FONT, 9), fg=A.FG_DIM, bg=A.BG_CARD).pack(padx=16)

    def _clear_active():
        if on_clear_active():
            messagebox.showinfo("Silindi", "Bu sohbetin geçmişi silindi",
                                parent=dlg)

    def _clear_all():
        if messagebox.askyesno("Tüm Geçmişi Sil",
                               "Tüm sohbet geçmişi silinecek. Emin misiniz?",
                               parent=dlg):
            on_clear_all()
            dlg.destroy()

    btn_f = tk.Frame(dlg, bg=A.BG_CARD, padx=16)
    btn_f.pack(fill="x", pady=12)
    if has_active:
        ttk.Button(btn_f, text="🗑 Bu Sohbeti Sil",
                   command=_clear_active).pack(fill="x", ipady=4, pady=4)
    ttk.Button(btn_f, text="⚠ Tüm Geçmişi Sil",
               command=_clear_all).pack(fill="x", ipady=4)
