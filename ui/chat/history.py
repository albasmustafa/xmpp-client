"""History viewport / scroll sunum yardımcıları (Faz 4C-6).

GUI-only, stateless. Domain, arşiv, veritabanı ve sohbet veri modeli
bilmez; entry'leri caller'ın verdiği sırada render ettirir. Worker yoktur.
"""
import tkinter as tk


def clear_view(msg_frame, bubble_widgets, photo_refs):
    """Yalnız görünümü temizle (domain history'ye dokunmaz).

    Mevcut davranış birebir: bubble listesi + photo refs + msg_frame
    çocukları temizlenir; her destroy try/except ile korunur.
    """
    for w in bubble_widgets:
        try:
            w.destroy()
        except Exception:
            pass
    bubble_widgets.clear()
    photo_refs.clear()
    for w in msg_frame.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass


def render_history(entries, render_entry):
    """Entry'leri verilen sırada render et (sort/dedupe/merge YOK)."""
    for entry in entries:
        render_entry(entry)


def scroll_bottom(canvas):
    canvas.update_idletasks()
    canvas.yview_moveto(1.0)


def scroll_wheel(canvas, event):
    """MouseWheel delta → units (mevcut formül birebir)."""
    canvas.yview_scroll(int(-1 * event.delta / 60), "units")



def bind_scroll_widget(widget, on_scroll, on_units):
    """Tüm alt widget'larda scroll çalışsın (mevcut unit sayıları)."""
    widget.bind("<MouseWheel>", on_scroll)
    widget.bind("<Button-4>", lambda _: on_units(-3))
    widget.bind("<Button-5>", lambda _: on_units(3))
    for child in widget.winfo_children():
        bind_scroll_widget(child, on_scroll, on_units)


def activate_scroll(root, on_scroll, on_units):
    root.bind_all("<MouseWheel>", on_scroll)
    root.bind_all("<Button-4>", lambda _: on_units(-3))
    root.bind_all("<Button-5>", lambda _: on_units(3))


def deactivate_scroll(root):
    root.unbind_all("<MouseWheel>")
    root.unbind_all("<Button-4>")
    root.unbind_all("<Button-5>")


def build_history_nav(parent, th, on_older, on_latest):
    """[2F] Sabit gezinme çubuğu: ⬆ Daha eski | ↓ En yeni / Yeni mesajlar (N).

    Tek örnek kurulur; mesaj başına gezinme widget'ı YOKTUR. Çubuk,
    chat_area içinde canvas'ın altındaki 1. grid satırına yerleşir ve
    gizli başlar. Sağ kontrol hem "Latest" hem "New messages (N)" işlevini
    üstlenir (aynı callback).
    """
    bar = tk.Frame(parent, bg=th["BG_CHAT"], padx=10, pady=3)
    bar.grid(row=1, column=0, sticky="ew")
    bar.grid_remove()

    older = tk.Label(bar, text="⬆ Daha eski", font=(th["FONT"], 8, "bold"),
                     fg=th["ACCENT"], bg=th["BG_HOVER"], cursor="hand2",
                     padx=10, pady=2)
    older.pack(side="left")
    older.bind("<Button-1>", lambda _: on_older())
    older.bind("<Enter>", lambda _: older.config(fg=th["ACCENT_G"]))
    older.bind("<Leave>", lambda _: older.config(fg=th["ACCENT"]))

    latest = tk.Label(bar, text="↓ En yeni", font=(th["FONT"], 8, "bold"),
                      fg=th["ACCENT"], bg=th["BG_HOVER"], cursor="hand2",
                      padx=10, pady=2)
    latest.pack(side="right")
    latest.bind("<Button-1>", lambda _: on_latest())
    latest.bind("<Enter>", lambda _: latest.config(fg=th["ACCENT_G"]))
    latest.bind("<Leave>", lambda _: latest.config(fg=th["ACCENT"]))

    bar.nav_older = older
    bar.nav_latest = latest
    return bar


def update_history_nav(bar, show_older, show_latest, pending):
    """[2F] Çubuk senkronu: görünürlük + metin (widget sayısı sabittir).

    pending > 0 → sağ kontrol "↓ Yeni mesajlar (N)"; değilse "↓ En yeni".
    """
    if bar is None:
        return
    if show_older or show_latest:
        bar.grid()
    else:
        bar.grid_remove()
    older, latest = bar.nav_older, bar.nav_latest
    if show_older:
        older.pack(side="left")
    else:
        older.pack_forget()
    if show_latest:
        if pending > 0:
            latest.config(text=f"↓ Yeni mesajlar ({pending})")
        else:
            latest.config(text="↓ En yeni")
        latest.pack(side="right")
    else:
        latest.pack_forget()
