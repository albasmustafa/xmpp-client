"""⭐ Yıldızlı Mesajlar penceresi (MainWindow._starred_dialog).

Durumsuz görünüm: satırlar ve eylemler parametreyle gelir; DB/bot/ağ yok.
Tema çağrı anında `xmpp`'den okunur (`_app()`).
"""
import tkinter as tk
from tkinter import ttk


def _app():
    import xmpp as _app_mod
    return _app_mod


def _tr(text):
    """Arayüz metnini seçili dile çevir (`xmpp._tr`)."""
    return _app()._tr(text)


def show_starred(parent, rows, *, on_open, on_unstar):
    """rows: [(satır metni, anahtar)] — yeniden eskiye. Çift tık / Enter /
    "Aç" `on_open(anahtar)` çağırıp kartı kapatır; "☆ Yıldızı Kaldır"
    `on_unstar(anahtar)` çağırıp satırı listeden düşürür."""
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title(_tr("⭐ Yıldızlı Mesajlar"))
    dlg.configure(bg=A.BG_CARD)
    dlg.transient(parent)
    A._make_popover(dlg)

    tk.Label(dlg, text=_tr("⭐ Yıldızlı Mesajlar"), font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 8))
    if not rows:
        tk.Label(dlg, text=_tr("Henüz yıldızlı mesaj yok"), font=(A.FONT, 9),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(padx=24, pady=(0, 20))
        return dlg

    keys = [key for _text, key in rows]
    box = tk.Frame(dlg, bg=A.BG_CARD)
    box.pack(fill="both", expand=True, padx=16)
    lb = tk.Listbox(box, bg=A.BG_PANEL, fg=A.FG, selectbackground=A.SEL_BG,
                    selectforeground=A.SEL_FG, font=(A.FONT, 9), width=72,
                    height=min(14, max(4, len(rows))), relief="flat",
                    highlightthickness=0, activestyle="none")
    bar = ttk.Scrollbar(box, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=bar.set)
    lb.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    for text, _key in rows:
        lb.insert("end", text)
    lb.selection_set(0)

    def _chosen():
        sel = lb.curselection()
        return sel[0] if sel else None

    def _open(_e=None):
        i = _chosen()
        if i is None:
            return
        dlg.destroy()
        on_open(keys[i])

    def _unstar():
        i = _chosen()
        if i is None:
            return
        on_unstar(keys.pop(i))
        lb.delete(i)
        if keys:
            lb.selection_set(min(i, len(keys) - 1))

    lb.bind("<Double-Button-1>", _open)
    lb.bind("<Return>", _open)
    btns = tk.Frame(dlg, bg=A.BG_CARD)
    btns.pack(fill="x", padx=16, pady=(8, 14))
    ttk.Button(btns, text=_tr("Aç"), command=_open).pack(side="right")
    ttk.Button(btns, text=_tr("☆ Yıldızı Kaldır"), command=_unstar).pack(
        side="right", padx=(0, 8))
    lb.focus_set()
    return dlg
