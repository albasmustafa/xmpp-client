"""Mesaj eylem dialogları (Faz 4A): düzenleme girdisi, iletme hedefi seçimi.

UI yalnızca kullanıcı girdisini/ hedefini toplar; XMPP gönderimi
çağıranda (MainWindow sarmalayıcısında) kalır.
"""
import tkinter as tk
from tkinter import simpledialog, ttk

from ui.dialogs.simple import _app


def ask_edit_message(parent, title, prompt, initial):
    """Mesaj düzenleme girdisi (MainWindow._edit_message_dialog).

    Dönüş: yeni metin veya iptalde None.
    """
    return simpledialog.askstring(
        title, prompt, initialvalue=initial, parent=parent)


def show_forward(parent, contacts, rooms, body, sender, on_forward):
    """İletme hedefi seçme diyaloğu (MainWindow._forward_dialog).

    `contacts`: {jid: isim}; `rooms`: oda jid listesi.
    `on_forward(to, mtype)` seçim onaylanınca çağrılır.
    """
    A = _app()
    pop = tk.Toplevel(parent)
    pop.title("Mesajı İlet")
    pop.configure(bg=A.BG_CARD)
    pop.geometry("320x400")
    pop.transient(parent)
    pop.attributes("-topmost", True)

    tk.Label(pop, text="İletilecek kişi/oda seçin:",
             fg=A.FG, bg=A.BG_CARD, font=(A.FONT, 10, "bold")).pack(
                 padx=16, pady=(16, 8), anchor="w")

    # Önizleme
    prev = tk.Frame(pop, bg=A.BG_HOVER, padx=12, pady=6)
    prev.pack(fill="x", padx=16, pady=(0, 8))
    tk.Label(prev, text=f"{sender}:", fg=A.ACCENT, bg=A.BG_HOVER,
             font=(A.FONT, 8, "bold")).pack(anchor="w")
    tk.Label(prev, text=body[:120] + ("…" if len(body) > 120 else ""),
             fg=A.FG_DIM, bg=A.BG_HOVER, font=(A.FONT, 8),
             wraplength=280).pack(anchor="w")

    lb = tk.Listbox(pop, bg=A.BG_PANEL, fg=A.FG, selectbackground=A.SEL_BG,
                    selectforeground=A.SEL_FG, font=(A.FONT, 9),
                    relief="flat", highlightthickness=0)
    lb.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    targets = []
    for jid in sorted(contacts.keys()):
        targets.append(jid)
        name = contacts[jid] or jid
        lb.insert("end", f"  {name}")
    for jid in sorted(rooms):
        targets.append(jid)
        lb.insert("end", f"  🏠 {jid}")

    def do_forward():
        sel = lb.curselection()
        if not sel:
            return
        to = targets[sel[0]]
        mtype = "groupchat" if to in rooms else "chat"
        on_forward(to, mtype)
        pop.destroy()

    ttk.Button(pop, text="İlet", command=do_forward).pack(
        padx=16, pady=(0, 16))
