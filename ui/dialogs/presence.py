"""Presence ile ilgili basit dialoglar (Faz 4A): durum mesajı, konum paylaşımı.

MainWindow state'i yok; XMPPBot çağrıları callback ile yapılır.
Tema/widget yardımcıları canlı `xmpp` modülünden okunur.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from ui.dialogs.simple import _app


def show_status(parent, on_apply):
    """Durum mesajı + görünürlük seçimi (MainWindow._status_dialog)."""
    A = _app()
    pop = tk.Toplevel(parent)
    pop.title("Durum Mesajı")
    pop.configure(bg=A.BG_CARD)
    pop.geometry("340x200")
    pop.transient(parent)

    tk.Label(pop, text="Durum Mesajı", fg=A.FG, bg=A.BG_CARD,
             font=(A.FONT, 12, "bold")).pack(padx=16, pady=(16, 8), anchor="w")

    status_var = tk.StringVar()
    status_entry = A.PlaceholderEntry(pop, placeholder="Durum yazın...",
                                      textvariable=status_var,
                                      font=(A.FONT, 10), style="Modern.TEntry")
    status_entry.pack(fill="x", padx=16, pady=(0, 12))

    show_var = tk.StringVar(value="chat")
    sf = tk.Frame(pop, bg=A.BG_CARD)
    sf.pack(fill="x", padx=16)
    for val, txt in [("chat", "Müsait"), ("away", "Uzakta"),
                     ("dnd", "Rahatsız Etmeyin"), ("xa", "Uzun Süre Uzakta")]:
        tk.Radiobutton(sf, text=txt, variable=show_var, value=val,
                       bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 8)).pack(
                           side="left", padx=(0, 8))

    def _apply():
        # get_value: boş alanda ipucu ("Durum yazın...") değer değildir
        on_apply(status_entry.get_value(), show_var.get())
        pop.destroy()

    ttk.Button(pop, text="Uygula", command=_apply).pack(
        padx=16, pady=(12, 16))


def show_location(parent, on_publish, on_stop):
    """Konum paylaşım formu (MainWindow._location_dialog).

    Koordinat doğrulaması burada; ağ çağrıları callback'lerle yapılır.
    """
    A = _app()
    pop = tk.Toplevel(parent)
    pop.title("Konum Paylaş")
    pop.configure(bg=A.BG_CARD)
    pop.geometry("320x240")
    pop.transient(parent)

    tk.Label(pop, text="Konum Paylaş", fg=A.FG, bg=A.BG_CARD,
             font=(A.FONT, 12, "bold")).pack(padx=16, pady=(16, 8), anchor="w")

    fields = {}
    for label, key, ph in [("Enlem:", "lat", "41.0082"),
                           ("Boylam:", "lon", "28.9784"),
                           ("Açıklama:", "desc", "İstanbul")]:
        f = tk.Frame(pop, bg=A.BG_CARD)
        f.pack(fill="x", padx=16, pady=2)
        tk.Label(f, text=label, fg=A.FG_DIM, bg=A.BG_CARD,
                 font=(A.FONT, 8), width=10, anchor="e").pack(side="left")
        v = tk.StringVar()
        e = A.PlaceholderEntry(f, placeholder=ph, textvariable=v,
                               font=(A.FONT, 9), style="Modern.TEntry")
        e.pack(side="left", fill="x", expand=True, padx=(8, 0))
        fields[key] = e     # get_value: boş alanda ipucu değer değildir

    def _send():
        try:
            lat = float(fields["lat"].get_value())
            lon = float(fields["lon"].get_value())
            desc = fields["desc"].get_value()
            on_publish(lat, lon, desc)
            pop.destroy()
        except ValueError:
            messagebox.showerror("Hata", "Geçersiz koordinatlar", parent=pop)

    def _stop():
        on_stop()
        pop.destroy()

    btn_f = tk.Frame(pop, bg=A.BG_CARD)
    btn_f.pack(pady=(12, 16))
    ttk.Button(btn_f, text="Paylaş", command=_send).pack(side="left", padx=4)
    ttk.Button(btn_f, text="Durdur", command=_stop).pack(side="left", padx=4)
