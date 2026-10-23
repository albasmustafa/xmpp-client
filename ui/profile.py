"""Profile/presence presentation (Faz 4B-4).

Kurallar:
- Presence publish, XEP-0107 mood, avatar publish, toast: owner'da (callback).
- UI yalnız menü/form/geçici state ve kullanıcı seçimini taşır.
- Tema/STATUS_OPTIONS canlı `xmpp`'den okunur (tek mapping kaynağı korunur).
"""
import io
import os
import tkinter as tk
from tkinter import messagebox, ttk

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
    # Renk duruma göre (etikete değil); MainWindow._ai_status_option ile aynı
    colors = {"online": A.ONLINE, "away": A.AWAY}
    for label, show in A.STATUS_OPTIONS:
        c = colors.get(show, A.RED)
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
    A._make_popover(dlg, form=True)

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


def show_avatar_dialog(parent, jid, avatar_data, photo_refs, *,
                       on_publish, on_forget, on_removed):
    """Profil fotoğrafı penceresi (MainWindow._change_avatar_dialog).

    Görsel seçimi, kırpma ve önizleme burada; kayıt ve yayın owner'da:
    `on_publish(photo_bytes, on_result)` (sonuç `on_result(ok)` ile döner),
    kaldırmada `on_forget()` → önizleme → `on_removed()`.
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Profil Fotoğrafı")
    dlg.configure(bg=A.SHADOW)
    dlg.resizable(False, False)
    dlg.transient(parent)
    A._make_popover(dlg)

    shadow = tk.Frame(dlg, bg=A.SHADOW, padx=3, pady=3)
    shadow.pack(padx=20, pady=20)
    card = tk.Frame(shadow, bg=A.BG_CARD, padx=28, pady=24)
    card.pack()

    tk.Label(card, text="Profil Fotoğrafı",
             font=(A.FONT, 14, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(anchor="w")
    tk.Label(card, text="Fotoğrafınızı değiştirin veya kaldırın",
             font=(A.FONT, 8), fg=A.FG_DIM,
             bg=A.BG_CARD).pack(anchor="w", pady=(2, 16))

    # Önizleme
    preview_f = tk.Frame(card, bg=A.BG_CARD)
    preview_f.pack(pady=(0, 16))
    preview = A._avatar(preview_f, 96, jid[0], A.ACCENT2, A.BG_CARD,
                        photo_data=avatar_data, _photo_refs=photo_refs)
    preview.pack()

    status_lbl = tk.Label(card, text="", font=(A.FONT, 8),
                          fg=A.ACCENT_G, bg=A.BG_CARD)
    status_lbl.pack(pady=(0, 8))

    def _on_result(ok):
        if dlg.winfo_exists():
            status_lbl.config(
                text="✓ Güncellendi" if ok else
                     "⚠ Yayınlanamadı — eski fotoğraf korundu",
                fg=A.ACCENT_G if ok else A.RED)

    def _pick():
        if not A.HAS_PIL:
            messagebox.showwarning("Pillow Gerekli",
                "Fotoğraf desteği için Pillow gerekli:\npip install Pillow",
                parent=dlg)
            return
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=dlg,
            title="Fotoğraf Seç",
            filetypes=[
                ("Resim Dosyaları", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                ("Tüm Dosyalar", "*.*"),
            ])
        if not path:
            return
        try:
            Image = A.Image
            img = Image.open(path)
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            # Kare kırp (ortadan)
            w, h = img.size
            s = min(w, h)
            left = (w - s) // 2
            top = (h - s) // 2
            img = img.crop((left, top, left + s, top + s))
            img = img.resize((256, 256), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            photo_bytes = buf.getvalue()

            status_lbl.config(text="Yükleniyor…", fg=A.ACCENT)

            # Önizlemeyi güncelle
            preview.delete("all")
            pi = img.resize((94, 94), Image.LANCZOS)
            from PIL import ImageDraw
            mask = Image.new("L", (94, 94), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 94, 94), fill=255)
            pi.putalpha(mask)
            pho = A.ImageTk.PhotoImage(pi)
            preview.create_image(48, 48, image=pho)
            preview._photo = pho
            photo_refs.append(pho)

            # Yayınla — hata olursa owner eski fotoğrafa döner
            on_publish(photo_bytes, _on_result)

        except Exception as e:
            status_lbl.config(text=f"Hata: {e}", fg=A.RED)

    def _remove():
        on_forget()
        preview.delete("all")
        preview.create_oval(2, 2, 94, 94, fill=A.ACCENT2, outline="")
        preview.create_text(48, 48, text=jid[0].upper(),
                            fill=A.FG_ME, font=(A.FONT, 32, "bold"))
        on_removed()
        status_lbl.config(text="✓ Kaldırıldı", fg=A.ACCENT_G)

    bf = tk.Frame(card, bg=A.BG_CARD)
    bf.pack(fill="x")
    ttk.Button(bf, text="📷  Fotoğraf Seç",
               command=_pick).pack(side="left", ipadx=8, ipady=3)
    if avatar_data:
        ttk.Button(bf, text="Kaldır", style="Ghost.TButton",
                   command=_remove).pack(side="right", ipadx=8, ipady=3)

    dlg.lift()
    return dlg
