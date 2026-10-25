"""Audio/voice sunum primitifleri (Faz 4C-5B2).

GUI-only presentation. Playback engine, kilit, generation, ses backend'i
ve ağ MainWindow'da kalır. Bu modül thread/after/worker üretmez.
"""
import tkinter as tk

# Arayüz metni çevirisi: xmpp içe aktarılınca `xmpp._tr` takılır
# (ui/chat yalnız tkinter/collections içe aktarır)
_tr = str



def audio_placeholder(parent, theme, bg):
    """İndirilme placeholder'ı (frame + başlık)."""
    holder = tk.Frame(parent, bg=bg)
    holder.pack(anchor="w", pady=(4, 2))
    tk.Label(holder, text=_tr("🎤 Yükleniyor…"), fg=theme["FG_DIM"], bg=bg,
             font=(theme["FONT"], 8)).pack(anchor="w")
    return holder


def start_player(holder, theme, bg):
    """Placeholder'ı oynatıcı başlığıyla değiştir (eski içerik temizlenir)."""
    for w in holder.winfo_children():
        w.destroy()
    tk.Label(holder, text=_tr("🎤 Ses Mesajı"), fg=theme["FG_DIM"], bg=bg,
             font=(theme["FONT"], 8, "bold")).pack(anchor="w")


def fallback_link(holder, theme, bg, url, on_open):
    """Ses yüklenemedi — tıklanabilir link."""
    for w in holder.winfo_children():
        w.destroy()
    lnk = tk.Label(holder, text=_tr("🎤 Ses: {}…").format(url[:50]), fg=theme["ACCENT"],
                   bg=bg, font=(theme["FONT"], 8), cursor="hand2")
    lnk.pack(anchor="w")
    lnk.bind("<Button-1>", lambda _e: on_open())
    return lnk


def sent_voice_bubble(parent, theme):
    """Gönderilen ses balonu: (row, bubble) — başlık eklenmiş halde."""
    row = tk.Frame(parent, bg=theme["BG_CHAT"])
    row.pack(fill="x", padx=18, pady=(8, 0))
    bubble = tk.Frame(row, bg=theme["BG_ME"], padx=14, pady=8)
    bubble.pack(side="right", anchor="e", padx=(60, 0))
    tk.Label(bubble, text=_tr("🎤 Ses Mesajı"), fg=theme["FG_ME"],
             bg=theme["BG_ME"], font=(theme["FONT"], 8, "bold")).pack(
        anchor="w")
    return row, bubble


def finish_voice_bubble(bubble, theme, ts):
    """Balona zaman damgası + gönderildi işareti ekle (waveform sonrası)."""
    ts_f = tk.Frame(bubble, bg=theme["BG_ME"])
    ts_f.pack(anchor="e", pady=(3, 0))
    tk.Label(ts_f, text=ts, fg="#c8c0ff", bg=theme["BG_ME"],
             font=(theme["FONT"], 7)).pack(side="left")
    tk.Label(ts_f, text=" ✓", fg=theme["FG_DIM"], bg=theme["BG_ME"],
             font=(theme["FONT"], 6)).pack(side="left")


TRANSCRIPT_MAX_CHARS = 600


def transcript_note(bubble, theme, bg, text, *, is_me, text_factory,
                    before=None):
    """Ses kaydının yazıya dökümü — balonda, meta satırından (saat) önce;
    mesaj metni gibi sol tıkla seçilir (`text_factory`: MainWindow'un
    seçilebilir metin kurucusu; bu modül yalnız tkinter kullanır).

    Uzun metin kırpılır; tamamı ✨ → "Metne dök" penceresindedir.
    """
    box = text_factory(
        bubble, "", fg=("#c8c0ff" if is_me else theme["FG_DIM"]), bg=bg,
        font=(theme["FONT"], 9, "italic"), wrap=420, sel_bg=theme["SEL_BG"],
        sel_fg=theme["SEL_FG"])
    set_transcript(box, text)
    pack_kw = {"anchor": "w", "pady": (4, 0)}
    if before is not None:
        pack_kw["before"] = before
    box.pack(**pack_kw)
    return box


def set_transcript(box, text):
    text = " ".join((text or "").split())
    if len(text) > TRANSCRIPT_MAX_CHARS:
        text = text[:TRANSCRIPT_MAX_CHARS - 1].rstrip() + "…"
    box.set_content(f"📝 {text}")


def set_play_icon(play_btn, playing):
    play_btn.config(text="⏸" if playing else "▶")


def set_duration(dur_lbl, duration):
    dur_lbl.config(text=f"{int(duration) // 60}:{int(duration) % 60:02d}")


def draw_waveform(canvas, bars, width, height, progress, accent_color, theme,
                  is_me):
    """Dalga formu çizimi + ilerleme vurgusu (saf sunum)."""
    canvas.delete("all")
    if not bars:
        canvas.create_text(width // 2, height // 2, text="🎵",
                           fill=theme["FG_DIM"])
        return
    max_val = max(1, max(bars))
    bar_w = 3
    gap = 1
    total_bars = len(bars)
    progress_bar = int(progress * total_bars)
    for i, v in enumerate(bars):
        h = max(2, int((v / max_val) * (height - 4)))
        x = i * (bar_w + gap)
        y = height // 2 - h // 2
        color = accent_color if i <= progress_bar else (
            theme["FG_DIM"] if not is_me else "#6366f1")
        canvas.create_rectangle(x, y, x + bar_w, y + h, fill=color,
                                outline="")
    if progress > 0:
        px = int(progress * total_bars * (bar_w + gap))
        canvas.create_line(px, 0, px, height, fill=accent_color, width=1)
