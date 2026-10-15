"""Profile/presence presentation (Faz 4B-4).

Kurallar:
- Presence publish, XEP-0107 mood, avatar publish, toast: owner'da (callback).
- UI yalnız menü/form/geçici state ve kullanıcı seçimini taşır.
- Tema/STATUS_OPTIONS canlı `xmpp`'den okunur (tek mapping kaynağı korunur).
"""
import os
import tkinter as tk
from tkinter import ttk

from ui.dialogs.simple import _app


def show_status_menu(parent, on_select, x_root, y_root):
    """Durum menüsü (MainWindow._show_status_menu).

    `on_select(label, show, color)` — gerçek presence yayını owner'da
    (`_set_status`). Mevcut STATUS_OPTIONS ve renk eşlemesi birebir.
    """
    A = _app()
    menu = tk.Menu(parent, tearoff=0,
                   bg=A.BG_CARD, fg=A.FG, activebackground=A.ACCENT2,
                   activeforeground=A.FG_ME, borderwidth=1,
                   relief="flat", font=(A.FONT, 9))
    colors = {"Online": A.ONLINE, "Away": A.AWAY,
              "Meşgul": A.RED, "Uzakta": A.RED}
    for label, show in A.STATUS_OPTIONS:
        c = colors.get(label, A.FG)
        menu.add_command(
            label=f"  ●  {label}",
            command=lambda lbl=label, s=show, cl=c: on_select(lbl, s, cl),
            foreground=c)
    menu.tk_popup(x_root, y_root)


def show_story_dialog(parent, on_publish):
    """Hikaye / Durum Paylaş penceresi (MainWindow._story_dialog).

    UI metin/mood/fotoğrafı toplar; boş doğrulaması yerel kalır; yayınlama
    `on_publish(text, mood, photo_path)` ile owner'da yapılır.
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("📖 Hikaye Paylaş")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("380x340")
    dlg.transient(parent)

    tk.Label(dlg, text="📖 Hikaye / Durum Paylaş", font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 8))

    # Metin durumu
    tk.Label(dlg, text="METİN DURUMU", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", padx=16, pady=(8, 4))
    story_var = tk.StringVar()
    ttk.Entry(dlg, textvariable=story_var, font=(A.FONT, 10)).pack(
        fill="x", padx=16, ipady=5)

    # Mood
    tk.Label(dlg, text="RUHSAL DURUM", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", padx=16, pady=(12, 4))
    mood_var = tk.StringVar(value="")
    mood_f = tk.Frame(dlg, bg=A.BG_CARD)
    mood_f.pack(fill="x", padx=16)
    moods = [("😊 Mutlu", "happy"), ("😔 Üzgün", "sad"), ("😡 Kızgın", "angry"),
             ("😴 Uykulu", "sleepy"), ("🤔 Düşünceli", "thoughtful"),
             ("🎉 Heyecanlı", "excited")]
    col = 0
    for txt, val in moods:
        tk.Radiobutton(mood_f, text=txt, variable=mood_var, value=val,
                       bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 8)).grid(
                           row=col // 3, column=col % 3, sticky="w", padx=(0, 8))
        col += 1

    # Fotoğraflı durum
    tk.Label(dlg, text="FOTOĞRAF", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", padx=16, pady=(12, 4))
    photo_path = [None]
    photo_lbl = tk.Label(dlg, text="Seçilmedi", font=(A.FONT, 8),
                         fg=A.FG_DIM, bg=A.BG_CARD)
    photo_lbl.pack(anchor="w", padx=16)

    def _pick():
        from tkinter import filedialog
        p = filedialog.askopenfilename(parent=dlg,
            filetypes=[("Resim", "*.png *.jpg *.jpeg")])
        if p:
            photo_path[0] = p
            photo_lbl.config(text=os.path.basename(p))

    tk.Label(dlg, text="📷 Fotoğraf Seç", font=(A.FONT, 8), fg=A.ACCENT,
             bg=A.BG_CARD, cursor="hand2").pack(anchor="w", padx=16)
    dlg.winfo_children()[-1].bind("<Button-1>", lambda _: _pick())

    def _publish():
        text = story_var.get().strip()
        mood = mood_var.get()
        if not text and not mood and not photo_path[0]:
            return
        on_publish(text, mood, photo_path[0])
        dlg.destroy()

    ttk.Button(dlg, text="📤 Yayınla", command=_publish).pack(
        padx=16, pady=12, fill="x", ipady=4)
