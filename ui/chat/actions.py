"""Mesaj action/context/hover sunum primitifleri (Faz 4C-5A).

Stateless, GUI-only. Domain/bot/DB/reaction state/active JID/timer YOKTUR.
Capability ve callback'ler MainWindow tarafından hazırlanır; bu modül yalnız
menü/action-bar popup görünümünü üretir.
"""
import tkinter as tk

# Arayüz metni çevirisi: xmpp içe aktarılınca `xmpp._tr` takılır
# (ui/chat yalnız tkinter/collections içe aktarır)
_tr = str
N_ = str        # modül düzeyindeki metin işareti (kullanım yerinde _tr)


MENU_REACTIONS = ("👍", "❤", "😂", "😮", "😢", "👎")
QUICK_REACTIONS = ("👍", "❤", "😂", "😮", "😢", "👎", "🔥", "🎉")


def create_action_bar(parent, theme, *, on_enter, on_leave, on_wheel,
                      on_scroll_units):
    """Hover action bar frame'i + mevcut bind semantiği."""
    bar = tk.Frame(parent, bg=theme["BG_CARD"], highlightthickness=1,
                   highlightbackground=theme["BORDER"], padx=5, pady=3)
    bar.bind("<Enter>", lambda e: on_enter(), "+")
    bar.bind("<Leave>", lambda e: on_leave(), "+")
    bar.bind("<MouseWheel>", on_wheel)
    bar.bind("<Button-4>", lambda _: on_scroll_units(-3))
    bar.bind("<Button-5>", lambda _: on_scroll_units(3))
    return bar


def action_button(parent, theme, icon, tip, command, *, danger, add_tooltip,
                  on_after):
    """Tek ikon buton: hover renkleri + tooltip + command→on_after."""
    normal_fg = theme["RED"] if danger else theme["FG"]
    hover_fg = theme["RED"] if danger else theme["ACCENT"]
    lbl = tk.Label(parent, text=icon, font=(theme["FONT"], 11),
                   bg=theme["BG_CARD"], fg=normal_fg, padx=6, pady=1,
                   cursor="hand2")
    lbl.pack(side="left", padx=1)
    lbl.bind("<Enter>", lambda e, w=lbl:
             w.config(bg=theme["BG_HOVER"], fg=hover_fg), "+")
    lbl.bind("<Leave>", lambda e, w=lbl:
             w.config(bg=theme["BG_CARD"], fg=normal_fg), "+")
    lbl.bind("<Button-1>", lambda e: (command(), on_after()))
    add_tooltip(lbl, tip)
    return lbl


def populate_action_bar(bar, theme, specs, *, add_tooltip, on_after):
    """Eski butonları temizle, verilen (icon, tip, command, danger) sırasını kur."""
    for child in bar.winfo_children():
        child.destroy()
    for icon, tip, command, danger in specs:
        action_button(bar, theme, icon, tip, command, danger=danger,
                      add_tooltip=add_tooltip, on_after=on_after)


def position_action_bar(row, bar):
    """Row'un üstüne hizala (mevcut geometri semantiği)."""
    try:
        if not row.winfo_exists():
            return False
        bar.update_idletasks()
        bw = max(44, bar.winfo_reqwidth())
        bh = max(18, bar.winfo_reqheight())
        rx, ry = row.winfo_x(), row.winfo_y()
        rw = row.winfo_width()
        x = (rx + rw - bw - 6) if getattr(row, "_is_me", False) else (rx + 44)
        y = ry - bh + 2
        bar.place(x=max(0, x), y=max(0, y))
        bar.lift()
        return True
    except Exception:
        return False


def show_context_menu(parent, x, y, *, theme, t, caps, mine, has_reactions,
                      callbacks):
    """Sağ tık menüsü. `caps` MainWindow'da hesaplanır; burada yalnız görünüm."""
    menu = tk.Menu(parent, tearoff=0, bg=theme["BG_CARD"], fg=theme["FG"],
                   activebackground=theme["SEL_BG"],
                   activeforeground=theme["SEL_FG"],
                   font=(theme["FONT"], 9))
    if caps.get("copy"):
        menu.add_command(label=f"📋 {t('copy')}",
                         command=callbacks["on_copy"])
    if caps.get("jump"):
        menu.add_command(label=_tr("↪ Alıntılanan mesaja git"),
                         command=callbacks["on_jump"])
    if caps.get("edit"):
        menu.add_command(label=f"✏ {t('edit')}",
                         command=callbacks["on_edit"])
        menu.add_command(label=f"🗑 {t('delete')}",
                         command=callbacks["on_delete"])
    if caps.get("reply"):
        menu.add_command(label=f"↩ {t('reply')}",
                         command=callbacks["on_reply"])
    if caps.get("forward"):
        menu.add_command(label=f"↪ {t('forward')}",
                         command=callbacks["on_forward"])
    if caps.get("pin"):
        menu.add_command(label=f"📌 {t('pin')}",
                         command=callbacks["on_pin"])
    if caps.get("react"):
        menu.add_separator()
        react_menu = tk.Menu(menu, tearoff=0, bg=theme["BG_CARD"],
                             fg=theme["FG"],
                             activebackground=theme["SEL_BG"],
                             activeforeground=theme["SEL_FG"],
                             font=(theme["FONT"], 12))
        for emoji in MENU_REACTIONS:
            mark = "  ✓" if emoji in mine else ""
            react_menu.add_command(
                label=f"{emoji}{mark}",
                command=lambda e=emoji: callbacks["on_react"](e))
        react_menu.add_separator()
        react_menu.add_command(label=_tr("😀 Daha fazla emoji…"),
                               command=callbacks["on_more_emoji"])
        if has_reactions:
            react_menu.add_command(label=_tr("👥 Tepkileri gör…"),
                                   command=callbacks["on_reactions_details"])
        menu.add_cascade(label=f"😊 {t('react')}", menu=react_menu)
    ai_items = [(key, label) for key, label in AI_MESSAGE_ITEMS
                if caps.get(key)]
    if ai_items:
        menu.add_separator()
        ai_menu = tk.Menu(menu, tearoff=0, bg=theme["BG_CARD"],
                          fg=theme["FG"], activebackground=theme["SEL_BG"],
                          activeforeground=theme["SEL_FG"],
                          font=(theme["FONT"], 9))
        for key, label in ai_items:
            ai_menu.add_command(label=_tr(label),
                                command=callbacks["on_" + key])
        menu.add_cascade(label=_tr("✨ AI"), menu=ai_menu)
    menu.tk_popup(x, y)


# Mesaj başına AI eylemleri: (capability/callback anahtarı, etiket)
AI_MESSAGE_ITEMS = (
    ("ai_translate", N_("🌐 Çevir")),
    ("ai_transcribe", N_("🎙 Sesi yazıya dök")),
    ("ai_describe", N_("🖼 Görseli açıkla")),
    ("ai_ask_image", N_("❓ Görsele soru sor…")),
    ("ai_speak", N_("🔊 Sesli oku")),
)


def show_ai_message_menu(parent, anchor, *, theme, items, callbacks):
    """Hover ✨ butonu: mesaj AI eylemleri (yalnız verilen anahtarlar)."""
    menu = tk.Menu(parent, tearoff=0, bg=theme["BG_CARD"], fg=theme["FG"],
                   activebackground=theme["SEL_BG"],
                   activeforeground=theme["SEL_FG"],
                   font=(theme["FONT"], 9))
    for key, label in AI_MESSAGE_ITEMS:
        if key in items:
            menu.add_command(label=_tr(label),
                             command=callbacks["on_" + key])
    # grab_release YOK: X11'de tk_popup dışarı tıklamayı yakalayan grab'i
    # kurup hemen döner; bırakılırsa menü açık kalır
    menu.tk_popup(anchor.winfo_rootx(),
                  anchor.winfo_rooty() + anchor.winfo_height())


def show_quick_reaction_menu(parent, anchor, *, theme, mine, on_react, on_more):
    """😊 butonu: hızlı tepki menüsü + tam seçici intent'i."""
    menu = tk.Menu(parent, tearoff=0, bg=theme["BG_CARD"], fg=theme["FG"],
                   activebackground=theme["SEL_BG"],
                   activeforeground=theme["SEL_FG"],
                   font=(theme["FONT"], 13))
    for emoji in QUICK_REACTIONS:
        mark = "  ✓" if emoji in mine else ""
        menu.add_command(label=f"{emoji}{mark}",
                         command=lambda e=emoji: on_react(e))
    menu.add_separator()
    menu.add_command(label=_tr("😀 Daha fazla emoji…"), command=on_more)
    # grab_release YOK: X11'de tk_popup dışarı tıklamayı yakalayan grab'i
    # kurup hemen döner; bırakılırsa menü açık kalır
    menu.tk_popup(anchor.winfo_rootx(),
                  anchor.winfo_rooty() + anchor.winfo_height())
