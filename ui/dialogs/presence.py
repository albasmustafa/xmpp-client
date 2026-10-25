"""Presence ile ilgili basit dialoglar (Faz 4A): durum mesajı, konum paylaşımı.

MainWindow state'i yok; XMPPBot çağrıları callback ile yapılır.
Tema/widget yardımcıları canlı `xmpp` modülünden okunur.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from ui.dialogs.simple import _app


def _tr(text):
    """Arayüz metnini seçili dile çevir (`xmpp._tr`)."""
    return _app()._tr(text)


def status_choices():
    """(yayınlanan show, etiket): Durum Mesajı ve Ayarlar "chat" yayınlar;
    etiketler durum menüsünün sözlüğüdür (STATUS_OPTIONS, "chat" = Çevrimiçi)."""
    labels = {show: label for label, show in _app()._status_options()}
    return [("chat", labels["online"]), ("away", labels["away"]),
            ("dnd", labels["dnd"]), ("xa", labels["xa"])]


def show_status(parent, on_apply, text="", show="chat"):
    """Durum mesajı + görünürlük seçimi (MainWindow._status_dialog).

    `text`/`show`: mevcut durum; pencere onunla açılır (yalnız yazıyı
    değiştirmek Meşgul'ü Çevrimiçi'ne çevirmesin)."""
    A = _app()
    pop = tk.Toplevel(parent)
    pop.title(_tr("Durum Mesajı"))
    pop.configure(bg=A.BG_CARD)
    pop.geometry("340x200")
    pop.transient(parent)
    A._make_popover(pop, form=True)

    tk.Label(pop, text=_tr("Durum Mesajı"), fg=A.FG, bg=A.BG_CARD,
             font=(A.FONT, 12, "bold")).pack(padx=16, pady=(16, 8), anchor="w")

    status_var = tk.StringVar(value=text)
    status_entry = A.PlaceholderEntry(pop, placeholder=_tr("Durum yazın..."),
                                      textvariable=status_var,
                                      font=(A.FONT, 10), style="Modern.TEntry")
    status_entry.pack(fill="x", padx=16, pady=(0, 12))

    show_var = tk.StringVar(value=show)
    sf = tk.Frame(pop, bg=A.BG_CARD)
    sf.pack(fill="x", padx=16)
    # 2×2: yan yana dört seçenek 340 px'e sığmıyordu ("Uzun süre uzakta"
    # kesiliyordu). Adlar durum menüsüyle aynı (STATUS_OPTIONS)
    for i, (val, txt) in enumerate(status_choices()):
        tk.Radiobutton(sf, text=txt, variable=show_var, value=val,
                       bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 8)).grid(
                           row=i // 2, column=i % 2, sticky="w", padx=(0, 12))

    def _apply():
        # get_value: boş alanda ipucu ("Durum yazın...") değer değildir
        on_apply(status_entry.get_value(), show_var.get())
        pop.destroy()

    ttk.Button(pop, text=_tr("Uygula"), command=_apply).pack(
        padx=16, pady=(12, 16))


def show_location(parent, on_publish, on_stop):
    """Konum paylaşım formu (MainWindow._location_dialog).

    Koordinat doğrulaması burada; ağ çağrıları callback'lerle yapılır.
    """
    A = _app()
    pop = tk.Toplevel(parent)
    pop.title(_tr("Konum Paylaş"))
    pop.configure(bg=A.BG_CARD)
    pop.geometry("320x240")
    pop.transient(parent)
    A._make_popover(pop, form=True)

    tk.Label(pop, text=_tr("Konum Paylaş"), fg=A.FG, bg=A.BG_CARD,
             font=(A.FONT, 12, "bold")).pack(padx=16, pady=(16, 8), anchor="w")

    fields = {}
    for label, key, ph in [("Enlem:", "lat", "41.0082"),
                           ("Boylam:", "lon", "28.9784"),
                           (_tr("Açıklama:"), "desc", _tr("İstanbul"))]:
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
            messagebox.showerror(_tr("Hata"), _tr("Geçersiz koordinatlar"), parent=pop)

    def _stop():
        on_stop()
        pop.destroy()

    btn_f = tk.Frame(pop, bg=A.BG_CARD)
    btn_f.pack(pady=(12, 16))
    ttk.Button(btn_f, text=_tr("Paylaş"), command=_send).pack(side="left", padx=4)
    ttk.Button(btn_f, text=_tr("Durdur"), command=_stop).pack(side="left", padx=4)
