"""Image/GIF/sticker/file/URL-preview sunum primitifleri (Faz 4C-5B1).

GUI-only. Worker/network/decode MainWindow'da kalır. PhotoImage üretimi
bu modülde YAPILMAZ; MW GUI thread'inde üretip `place_photo`'ya verir.
"""
import tkinter as tk

# Arayüz metni çevirisi: xmpp içe aktarılınca `xmpp._tr` takılır
# (ui/chat yalnız tkinter/collections içe aktarır)
_tr = str



def image_placeholder(parent, theme, bg):
    """İndirilme placeholder'ı (mevcut metin/padding)."""
    lbl = tk.Label(parent, text=_tr("📷 Yükleniyor…"), fg=theme["FG_DIM"], bg=bg,
                   font=(theme["FONT"], 8))
    lbl.pack(anchor="w", pady=(4, 2))
    return lbl


def place_image(holder, photo, bg, on_fullscreen):
    """Canlı holder'a resmi yerleştir + tıklama bağla."""
    holder.config(image=photo, text="", bg=bg)
    holder.image = photo
    holder.config(cursor="hand2")
    holder.bind("<Button-1>", on_fullscreen)


def place_photo(widget, photo):
    """PhotoImage'i widget'a uygula (fullscreen/GIF-thumb ortak)."""
    widget.config(image=photo, text="")
    widget.image = photo


def image_error(holder, theme):
    """Resim yüklenemedi etiketi (mevcut metin/renk)."""
    holder.config(text=_tr("⚠ Resim yüklenemedi"), fg=theme["RED"])


def image_link(parent, theme, url, bg, on_open):
    """PIL yoksa gösterilen tıklanabilir link."""
    lnk = tk.Label(parent, text=f"🔗 {url}", fg=theme["ACCENT"], bg=bg,
                   font=(theme["FONT"], 8), cursor="hand2", wraplength=380)
    lnk.pack(anchor="w", pady=(4, 2))
    lnk.bind("<Button-1>", lambda _e: on_open())
    return lnk


def file_card(parent, theme, name, size_text, open_text, folder_text,
              on_open, on_open_folder):
    """Yerel dosya kartı (Aç / Klasörü Aç) — mevcut stil birebir."""
    card = tk.Frame(parent, bg=theme["BG_HOVER"], padx=10, pady=8)
    card.pack(fill="x", pady=(4, 0))
    tk.Label(card, text=f"📎  {name}", font=(theme["FONT"], 9, "bold"),
             fg=theme["FG"], bg=theme["BG_HOVER"], anchor="w",
             wraplength=280).pack(fill="x")
    if size_text:
        tk.Label(card, text=size_text, font=(theme["FONT"], 7),
                 fg=theme["FG_DIM"], bg=theme["BG_HOVER"],
                 anchor="w").pack(fill="x")
    btns = tk.Frame(card, bg=theme["BG_HOVER"])
    btns.pack(anchor="w", pady=(4, 0))
    for text, cmd in ((open_text, on_open), (folder_text, on_open_folder)):
        b = tk.Label(btns, text=text, font=(theme["FONT"], 8),
                     fg=theme["ACCENT"], bg=theme["BG_HOVER"],
                     cursor="hand2", padx=6)
        b.pack(side="left")
        b.bind("<Button-1>", lambda _e, c=cmd: c())
        b.bind("<Enter>", lambda e: e.widget.config(fg=theme["FG"]))
        b.bind("<Leave>", lambda e: e.widget.config(fg=theme["ACCENT"]))
    return card


def url_preview_labels(container, theme, title, desc):
    """URL önizleme başlık/açıklama etiketleri (mevcut stil)."""
    if title:
        tk.Label(container, text=title, fg=theme["FG"], bg=theme["BG_CARD"],
                 font=(theme["FONT"], 8, "bold"), wraplength=300,
                 anchor="w", justify="left").pack(anchor="w", pady=(2, 0))
    if desc:
        tk.Label(container, text=desc[:150], fg=theme["FG_DIM"],
                 bg=theme["BG_CARD"], font=(theme["FONT"], 7),
                 wraplength=300, anchor="w", justify="left").pack(anchor="w")


def fullscreen_window(root, theme, on_open_url):
    """Resim fullscreen penceresi (bar + yükleme label'ı + ESC)."""
    top = tk.Toplevel(root)
    top.title(_tr("Resim"))
    top.configure(bg=theme["BG"])
    top.transient(root)
    top.geometry("800x600")
    bar = tk.Frame(top, bg=theme["BG_CARD"])
    bar.pack(fill="x")
    tk.Label(bar, text=_tr("ESC ile kapat"), fg=theme["FG_DIM"],
             bg=theme["BG_CARD"], font=(theme["FONT"], 8)).pack(
        side="left", padx=12, pady=6)
    btn = tk.Label(bar, text=_tr("🔗 Tarayıcıda Aç"), fg=theme["ACCENT"],
                   bg=theme["BG_CARD"], font=(theme["FONT"], 9),
                   cursor="hand2")
    btn.pack(side="right", padx=12, pady=6)
    btn.bind("<Button-1>", lambda _e: on_open_url())
    lbl = tk.Label(top, text=_tr("📷 Yükleniyor…"), fg=theme["FG_DIM"],
                   bg=theme["BG"], font=(theme["FONT"], 10))
    lbl.pack(expand=True, padx=20, pady=20)
    top.bind("<Escape>", lambda _e: top.destroy())
    top.focus_set()
    return top, lbl
