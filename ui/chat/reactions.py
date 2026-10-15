"""Reaction chip presentation helpers (Faz 4C-3B).

Stateless, GUI-only: yalnız rendered row üzerinde görsel çip üretir/temizler.
Reaction state/DB/bot/identity lookup YOK; snapshot veriler caller'dan gelir.
"""
import tkinter as tk

FRAME_TAG = "_reactions_frame"


def _clear_previous(row):
    for child in row.winfo_children():
        if getattr(child, "_tag", "") == FRAME_TAG:
            child.destroy()
            return True
    return False


def render_reactions(row, reactions, mine, *, theme, on_toggle, on_details,
                     on_reply, on_add, tooltip_fn, add_tooltip):
    """Tepki çiplerini yeniden çiz. Erken çıkışlarda None, aksi halde frame.

    Mevcut semantik: önce eski çip frame'i temizlenir; retracted satırda
    yeni çip üretilmez; reactions boş ve mid yoksa hiçbir şey yapılmaz.
    """
    _clear_previous(row)
    if getattr(row, "_retracted", False):
        return None
    mid = getattr(row, "_mid", "")
    if not reactions and not mid:
        return None
    is_me = getattr(row, "_is_me", False)
    rf = tk.Frame(row, bg=theme["BG_CHAT"])
    rf._tag = FRAME_TAG
    if is_me:
        rf.pack(anchor="e", padx=(60, 6), pady=(0, 2))
    else:
        rf.pack(anchor="w", padx=(46, 60), pady=(0, 2))
    for emoji, senders in sorted(reactions.items(),
                                 key=lambda kv: (-len(kv[1]), kv[0])):
        count = len(senders)
        tip = tooltip_fn(senders)
        is_mine = emoji in mine
        base_text = f"{emoji} {count}" if count > 1 else emoji
        lbl = tk.Label(rf, text=base_text, font=(theme["FONT"], 9),
                       fg=(theme["FG_ME"] if is_mine else theme["FG"]),
                       bg=(theme["ACCENT2"] if is_mine else theme["BG_HOVER"]),
                       padx=6, pady=1, cursor="hand2")
        lbl.pack(side="left", padx=(0, 3))
        if mid:
            lbl.bind("<Button-1>",
                     lambda e, em=emoji: on_toggle(em))
            lbl.bind("<Button-3>",
                     lambda e, em=emoji: on_details(em))
        if tip:
            lbl.bind("<Enter>", lambda e, t=tip, bt=base_text, w=lbl:
                     w.config(text=f"{bt}  {t[:34]}"))
            lbl.bind("<Leave>", lambda e, bt=base_text, w=lbl:
                     w.config(text=bt))
    if mid:
        reply_chip = tk.Label(rf, text="↩", font=(theme["FONT"], 9),
                              fg=theme["FG_DIM"], bg=theme["BG_CHAT"],
                              padx=4, pady=1, cursor="hand2")
        reply_chip.pack(side="left", padx=(0, 3))
        reply_chip.bind("<Enter>",
                        lambda e, w=reply_chip: w.config(fg=theme["ACCENT"]))
        reply_chip.bind("<Leave>",
                        lambda e, w=reply_chip: w.config(fg=theme["FG_DIM"]))
        reply_chip.bind("<Button-1>", lambda e: on_reply())
        add_tooltip(reply_chip, "Yanıtla")
        plus = tk.Label(rf, text="＋", font=(theme["FONT"], 9),
                        fg=theme["FG_DIM"], bg=theme["BG_CHAT"],
                        padx=4, pady=1, cursor="hand2")
        plus.pack(side="left", padx=(0, 3))
        plus.bind("<Enter>",
                  lambda e, w=plus: w.config(fg=theme["ACCENT"]))
        plus.bind("<Leave>",
                  lambda e, w=plus: w.config(fg=theme["FG_DIM"]))
        plus.bind("<Button-1>", lambda e: on_add())
        add_tooltip(plus, "Tepki ekle")
    return rf
