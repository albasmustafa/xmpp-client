"""Ayarlar penceresi (MainWindow._settings_dialog).

Durumsuz görünüm: config anlık görüntüsü (`cfg`), çalışma zamanı bilgisi
(`state`) ve yan etkiler (`actions`) parametreyle gelir. Bot, config yazımı,
thread ve DB işleri owner'da (MainWindow) kalır; "Kaydet ve Kapat" toplanan
değerleri `on_save(values)` ile owner'a verir, ardından pencere kapanır.
Tema/widget yardımcıları canlı `xmpp` modülünden okunur.

state anahtarları:
  jid, avatar_data, photo_refs (owner'ın listesi), compact_mode, wallpaper,
  current_lang, tray_active, has_omemo, omemo_ok, pgp_ok, pgp_keys,
  has_qrcode, ping_ms, connected, contacts_count, rooms_count,
  about [(etiket, değer)], libs [metin]
actions anahtarları:
  set_photo(path, parent) → bytes, remove_photo(), refresh_sidebar_avatar(),
  switch_account(acc), encode_pw(pw) → str, wallpaper(), test_sound(),
  blocking(), omemo_device_info(cb), pgp_entries(entries), omemo_qr(),
  proxy(), auto_theme(), pin_lock(), clear_history(), export_chat(),
  config_json() → str, backup(), shortcuts()
"""
import io
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ui.dialogs.simple import _app

# Tema seçim kartlarının önizleme renkleri (arka plan, yazı)
THEME_SWATCHES = {
    "koyu": ("#12101e", "#e8edf5"),
    "acik": ("#f5f5f7", "#2d3436"),
    "gece-mavisi": ("#0a1628", "#dfe6e9"),
    "amoled": ("#000000", "#ffffff"),
    "midnight": ("#0f0e17", "#fffffe"),
    "dracula": ("#282a36", "#f8f8f2"),
    "nord": ("#2e3440", "#eceff4"),
    "gruvbox": ("#282828", "#ebdbb2"),
    "solarized": ("#002b36", "#fdf6e3"),
    "monokai": ("#272822", "#f8f8f2"),
}

FONT_FAMILIES = ["Cantarell", "Noto Sans", "DejaVu Sans", "Ubuntu",
                 "Segoe UI", "Helvetica", "Arial", "monospace"]


def show_settings(parent, cfg, state, actions, on_save):
    """Ayarlar penceresini kur; Toplevel'ı döndür."""
    A = _app()
    jid = state["jid"]
    dlg = tk.Toplevel(parent)
    dlg.title("Ayarlar")
    dlg.configure(bg=A.SHADOW)
    dlg.geometry("560x640")
    dlg.transient(parent)
    A._safe_grab_set(dlg)
    dlg.resizable(False, True)

    shadow = tk.Frame(dlg, bg=A.SHADOW, padx=3, pady=3)
    shadow.pack(fill="both", expand=True, padx=14, pady=14)
    outer = tk.Frame(shadow, bg=A.BG_CARD)
    outer.pack(fill="both", expand=True)

    nb = ttk.Notebook(outer)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    def _scroll_tab(title):
        """Uzun sekme: dikey kaydırmalı iç çerçeve (pencere 640 px'e
        sığmayan içerik görünmez kalıyordu)."""
        holder = tk.Frame(nb, bg=A.BG_CARD)
        nb.add(holder, text=title)
        cv = tk.Canvas(holder, bg=A.BG_CARD, highlightthickness=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=A.BG_CARD, padx=20, pady=16)
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>",   # iç çerçeve sekme genişliğini doldursun
                lambda e: cv.itemconfigure(win_id, width=e.width))
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        inner.bind("<Configure>",
                   lambda _: cv.configure(scrollregion=cv.bbox("all")))
        for w in (cv, inner):
            w.bind("<Button-4>", lambda _: cv.yview_scroll(-3, "units"))
            w.bind("<Button-5>", lambda _: cv.yview_scroll(3, "units"))
        return inner

    chk_kw = dict(bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                  activebackground=A.BG_CARD, activeforeground=A.FG,
                  font=(A.FONT, 9))

    def _section(parent, title):
        tk.Frame(parent, bg=A.BORDER, height=1).pack(fill="x", pady=(12, 8))
        tk.Label(parent, text=title, font=(A.FONT, 7, "bold"),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(0, 6))

    def _link(parent, text, action, fg=None, **pack):
        """Tıklanabilir bağlantı etiketi (alt pencere açar)."""
        lbl = tk.Label(parent, text=text, font=(A.FONT, 9),
                       fg=fg or A.ACCENT, bg=A.BG_CARD, cursor="hand2")
        lbl.pack(anchor="w", **pack)
        lbl.bind("<Button-1>", lambda _: action())
        return lbl

    # ═══════════════════════════════════════════════════════════════════
    # SEKME 1 — HESAP & PROFİL
    # ═══════════════════════════════════════════════════════════════════
    t_account = tk.Frame(nb, bg=A.BG_CARD, padx=20, pady=16)
    nb.add(t_account, text="  Hesap  ")

    # — Scrollable container —
    ac_canvas = tk.Canvas(t_account, bg=A.BG_CARD, highlightthickness=0)
    ac_scroll = ttk.Scrollbar(t_account, orient="vertical",
                              command=ac_canvas.yview)
    ac_inner = tk.Frame(ac_canvas, bg=A.BG_CARD)
    ac_canvas.create_window((0, 0), window=ac_inner, anchor="nw")
    ac_canvas.configure(yscrollcommand=ac_scroll.set)
    ac_scroll.pack(side="right", fill="y")
    ac_canvas.pack(side="left", fill="both", expand=True)
    ac_inner.bind("<Configure>",
                  lambda _: ac_canvas.configure(scrollregion=ac_canvas.bbox("all")))
    ac_canvas.bind("<Button-4>",
                   lambda _: ac_canvas.yview_scroll(-3, "units"))
    ac_canvas.bind("<Button-5>",
                   lambda _: ac_canvas.yview_scroll(3, "units"))
    t1 = ac_inner  # alias

    # ── Profil fotoğrafı ──
    tk.Label(t1, text="PROFİL", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(0, 6))

    profile_f = tk.Frame(t1, bg=A.BG_HOVER, padx=14, pady=10)
    profile_f.pack(fill="x")
    photo_refs = state["photo_refs"]
    av_preview = A._avatar(profile_f, 56, jid[0], A.ACCENT2, A.BG_HOVER,
                           photo_data=state["avatar_data"], _photo_refs=photo_refs)
    av_preview.pack(side="left")

    prof_info = tk.Frame(profile_f, bg=A.BG_HOVER)
    prof_info.pack(side="left", padx=(12, 0), fill="y")
    tk.Label(prof_info, text=jid, font=(A.FONT, 10, "bold"),
             fg=A.FG, bg=A.BG_HOVER).pack(anchor="w")
    server = jid.split("@")[1] if "@" in jid else "—"
    tk.Label(prof_info, text=f"Sunucu: {server}", font=(A.FONT, 8),
             fg=A.FG_DIM, bg=A.BG_HOVER).pack(anchor="w")

    def _pick_photo():
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=dlg, title="Profil Fotoğrafı Seç",
            filetypes=[("Resim", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                       ("Tüm", "*.*")])
        if not path:
            return
        try:
            photo_bytes = actions["set_photo"](path, dlg)
            av_preview.delete("all")
            pi = A.Image.open(io.BytesIO(photo_bytes)).resize(
                (54, 54), A.Image.LANCZOS)
            from PIL import ImageDraw
            mask = A.Image.new("L", (54, 54), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 54, 54), fill=255)
            pi.putalpha(mask)
            pho = A.ImageTk.PhotoImage(pi)
            av_preview.create_image(28, 28, image=pho)
            av_preview._photo = pho
            photo_refs.append(pho)
            actions["refresh_sidebar_avatar"]()
        except Exception as e:
            messagebox.showerror("Hata", f"Fotoğraf yüklenemedi: {e}",
                                 parent=dlg)

    def _remove_photo():
        try:
            actions["remove_photo"]()
            av_preview.delete("all")
            av_preview.create_oval(1, 1, 55, 55, fill=A.ACCENT2, outline="")
            av_preview.create_text(28, 28, text=jid[0].upper(),
                                   fill=A.FG_ME, font=(A.FONT, 18, "bold"))
            actions["refresh_sidebar_avatar"]()
        except Exception:
            pass

    btn_f2 = tk.Frame(prof_info, bg=A.BG_HOVER)
    btn_f2.pack(anchor="w", pady=(6, 0))
    for txt, clr, cmd in [("Fotoğraf Değiştir", A.ACCENT, _pick_photo),
                          ("Kaldır", A.RED, _remove_photo)]:
        b = tk.Label(btn_f2, text=txt, font=(A.FONT, 8), fg=clr,
                     bg=A.BG_HOVER, cursor="hand2", padx=6)
        b.pack(side="left")
        b.bind("<Button-1>", lambda _, c=cmd: c())
        b.bind("<Enter>", lambda e: e.widget.config(fg=A.FG))
        b.bind("<Leave>", lambda e, c=clr: e.widget.config(fg=c))

    # ── Durum Mesajı ──
    _section(t1, "DURUM MESAJI")
    status_f = tk.Frame(t1, bg=A.BG_CARD)
    status_f.pack(fill="x")
    status_var = tk.StringVar(value=cfg.get("status_text", ""))
    A.PlaceholderEntry(status_f, placeholder="Durum yazın...",
                       textvariable=status_var,
                       font=(A.FONT, 9), style="Modern.TEntry").pack(
                           fill="x", ipady=4)

    show_var = tk.StringVar(value=cfg.get("presence_show", "chat"))
    show_f = tk.Frame(t1, bg=A.BG_CARD)
    show_f.pack(fill="x", pady=(6, 0))
    for val, txt, dot in [("chat", "Müsait", "🟢"), ("away", "Uzakta", "🟡"),
                          ("dnd", "Meşgul", "🔴"), ("xa", "Uzun Süre Uzakta", "🟠")]:
        tk.Radiobutton(show_f, text=f"{dot} {txt}", variable=show_var,
                       value=val, bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 8)).pack(
                           side="left", padx=(0, 10))

    # ── Giriş ──
    _section(t1, "GİRİŞ")
    auto_login_var = tk.BooleanVar(value=bool(cfg.get("remember")))
    tk.Checkbutton(t1, text="Açılışta otomatik giriş (şifreyi hatırla)",
                   variable=auto_login_var, **chk_kw).pack(anchor="w")

    # ── Çoklu Hesap ──
    _section(t1, "ÇOKLU HESAP")
    accounts = cfg.get("accounts", [])
    acc_list_f = tk.Frame(t1, bg=A.BG_CARD)
    acc_list_f.pack(fill="x")

    def _refresh_acc_list():
        for w in acc_list_f.winfo_children():
            w.destroy()
        for i, acc in enumerate(accounts):
            af = tk.Frame(acc_list_f, bg=A.BG_HOVER, padx=10, pady=5)
            af.pack(fill="x", pady=2)
            tk.Label(af, text=f"● {acc['jid']}", font=(A.FONT, 9),
                     fg=A.FG, bg=A.BG_HOVER).pack(side="left")
            rm = tk.Label(af, text="✕", font=(A.FONT, 9), fg=A.RED,
                          bg=A.BG_HOVER, cursor="hand2")
            rm.pack(side="right")
            rm.bind("<Button-1>", lambda _, idx=i: (
                accounts.pop(idx), _refresh_acc_list()))
            sw = tk.Label(af, text="⇄ Geçiş", font=(A.FONT, 8), fg=A.ACCENT,
                          bg=A.BG_HOVER, cursor="hand2")
            sw.pack(side="right", padx=(0, 8))
            sw.bind("<Button-1>",
                    lambda _, a=acc: actions["switch_account"](a))
        if not accounts:
            tk.Label(acc_list_f, text="Ek hesap yok",
                     font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")

    _refresh_acc_list()

    def _add_account():
        new_jid = simpledialog.askstring("Hesap Ekle", "JID:", parent=dlg)
        if not new_jid:
            return
        pw = simpledialog.askstring("Hesap Ekle", "Şifre:",
                                    parent=dlg, show="*")
        if not pw:
            return
        accounts.append({"jid": new_jid, "password": actions["encode_pw"](pw)})
        _refresh_acc_list()

    add_acc = tk.Label(t1, text="+ Hesap Ekle", font=(A.FONT, 8),
                       fg=A.ACCENT, bg=A.BG_CARD, cursor="hand2")
    add_acc.pack(anchor="w", pady=(6, 0))
    add_acc.bind("<Button-1>", lambda _: _add_account())

    # ═══════════════════════════════════════════════════════════════════
    # SEKME 2 — GÖRÜNÜM
    # ═══════════════════════════════════════════════════════════════════
    t_appear = _scroll_tab("  Görünüm  ")

    # ── Tema ──
    tk.Label(t_appear, text="TEMA", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(0, 6))

    theme_var = tk.StringVar(value=cfg.get("theme", "koyu"))
    theme_f = tk.Frame(t_appear, bg=A.BG_CARD)
    theme_f.pack(fill="x")
    col = 0
    for tname, (bg_c, fg_c) in THEME_SWATCHES.items():
        card = tk.Frame(theme_f, bg=A.BORDER, padx=1, pady=1)
        card.grid(row=col // 4, column=col % 4, padx=3, pady=3, sticky="ew")
        theme_f.columnconfigure(col % 4, weight=1)
        inner = tk.Frame(card, bg=bg_c, padx=8, pady=6)
        inner.pack(fill="x")
        rb = tk.Radiobutton(inner, text=tname.capitalize(),
                            variable=theme_var, value=tname,
                            bg=bg_c, fg=fg_c, selectcolor=bg_c,
                            activebackground=bg_c, activeforeground=fg_c,
                            font=(A.FONT, 7), anchor="w")
        rb.pack(fill="x")
        col += 1

    # ── Yazı Tipi ──
    _section(t_appear, "YAZI TİPİ")
    font_var = tk.IntVar(value=cfg.get("font_size", 10))
    font_family_var = tk.StringVar(value=cfg.get("font_family", A.FONT))

    ff_f = tk.Frame(t_appear, bg=A.BG_CARD)
    ff_f.pack(fill="x")
    tk.Label(ff_f, text="Yazı tipi:", font=(A.FONT, 9),
             fg=A.FG, bg=A.BG_CARD).pack(side="left")
    font_combo = ttk.Combobox(ff_f, textvariable=font_family_var,
                              values=FONT_FAMILIES, state="readonly",
                              width=14, font=(A.FONT, 9))
    font_combo.pack(side="left", padx=(8, 0))

    # Font boyutu slider
    fs_f = tk.Frame(t_appear, bg=A.BG_CARD)
    fs_f.pack(fill="x", pady=(8, 0))
    tk.Label(fs_f, text="Boyut:", font=(A.FONT, 9),
             fg=A.FG, bg=A.BG_CARD).pack(side="left")
    fs_lbl = tk.Label(fs_f, text=str(font_var.get()), font=(A.FONT, 9, "bold"),
                      fg=A.ACCENT, bg=A.BG_CARD, width=3)
    fs_lbl.pack(side="right")
    font_scale = tk.Scale(fs_f, from_=8, to=18, orient="horizontal",
                          variable=font_var, showvalue=False,
                          bg=A.BG_CARD, fg=A.FG, troughcolor=A.BG_HOVER,
                          highlightthickness=0, length=200,
                          activebackground=A.ACCENT,
                          command=lambda v: fs_lbl.config(text=v))
    font_scale.pack(side="left", padx=(8, 0), fill="x", expand=True)

    # Önizleme
    _section(t_appear, "ÖNİZLEME")
    preview_f = tk.Frame(t_appear, bg=A.BG_HOVER, padx=14, pady=10)
    preview_f.pack(fill="x")
    preview_lbl = tk.Label(preview_f,
                           text="Merhaba! Bu bir önizleme mesajıdır. 🎉",
                           fg=A.FG, bg=A.BG_HOVER, font=(A.FONT, 10))
    preview_lbl.pack(anchor="w")

    def _update_preview(*_):
        try:
            fam = font_family_var.get()
            sz = font_var.get()
            preview_lbl.config(font=(fam, sz))
        except Exception:
            pass
    font_var.trace_add("write", _update_preview)
    font_family_var.trace_add("write", _update_preview)

    # ── Dil ──
    _section(t_appear, "DİL")
    lang_f = tk.Frame(t_appear, bg=A.BG_CARD)
    lang_f.pack(fill="x")
    lang_var = tk.StringVar(value=cfg.get("language", state["current_lang"]))
    for val, txt, flag in [("tr", "Türkçe", "🇹🇷"), ("en", "English", "🇬🇧")]:
        tk.Radiobutton(lang_f, text=f"{flag}  {txt}", variable=lang_var,
                       value=val, bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 9)).pack(
                           side="left", padx=(0, 16))

    # ── Kompakt Mod ──
    _section(t_appear, "DÜZEN")
    compact_var = tk.BooleanVar(value=state["compact_mode"])
    tk.Checkbutton(t_appear, text="📐 Kompakt mod (mesaj balonları daha sıkışık)",
                   variable=compact_var, **chk_kw).pack(anchor="w")

    # ── Sohbet Arka Planı ──
    _section(t_appear, "SOHBET ARKA PLANI")
    wp_f = tk.Frame(t_appear, bg=A.BG_CARD)
    wp_f.pack(fill="x")
    current_wp = state["wallpaper"] or "(varsayılan)"
    wp_display = current_wp if len(current_wp) < 40 else "…" + current_wp[-37:]
    tk.Label(wp_f, text=f"Mevcut: {wp_display}",
             font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
    _link(wp_f, "🖼 Arka Plan Değiştir…", actions["wallpaper"], pady=(4, 0))

    # ═══════════════════════════════════════════════════════════════════
    # SEKME 3 — BİLDİRİMLER & GİZLİLİK
    # ═══════════════════════════════════════════════════════════════════
    t_notif = tk.Frame(nb, bg=A.BG_CARD, padx=20, pady=16)
    nb.add(t_notif, text="  Bildirimler  ")

    # ── Bildirimler ──
    tk.Label(t_notif, text="BİLDİRİMLER", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(0, 6))

    notify_var = tk.BooleanVar(value=cfg.get("notifications", True))
    tk.Checkbutton(t_notif, text="Masaüstü bildirimleri göster",
                   variable=notify_var, **chk_kw).pack(anchor="w")

    sound_var = tk.BooleanVar(value=cfg.get("sounds", True))
    tk.Checkbutton(t_notif, text="Bildirim sesleri çal",
                   variable=sound_var, **chk_kw).pack(anchor="w", pady=(4, 0))

    sound_test = tk.Label(t_notif, text="🔊 Sesi Test Et", font=(A.FONT, 8),
                          fg=A.ACCENT, bg=A.BG_CARD, cursor="hand2")
    sound_test.pack(anchor="w", padx=(24, 0), pady=(2, 0))
    sound_test.bind("<Button-1>", lambda _: actions["test_sound"]())

    # ── Sistem Tepsisi ──
    _section(t_notif, "SİSTEM TEPSİSİ")
    tray_status = "🟢 Aktif" if state["tray_active"] else "⚫ pystray yüklü değil"
    tk.Label(t_notif, text=f"Tepsi ikonu: {tray_status}",
             font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
    if not state["tray_active"]:
        tk.Label(t_notif, text="Yüklemek için: pip install pystray",
                 font=(A.FONT, 7), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(2, 0))

    # ── Gizlilik ──
    _section(t_notif, "GİZLİLİK")

    read_receipt_var = tk.BooleanVar(
        value=cfg.get("send_read_receipts", True))
    tk.Checkbutton(t_notif, text="Okundu bilgisi gönder (XEP-0333)",
                   variable=read_receipt_var, **chk_kw).pack(anchor="w")

    typing_var = tk.BooleanVar(
        value=cfg.get("send_typing", True))
    tk.Checkbutton(t_notif, text="Yazıyor bildirimi gönder (XEP-0085)",
                   variable=typing_var, **chk_kw).pack(anchor="w", pady=(4, 0))

    # ── Kaybolan Mesajlar ──
    _section(t_notif, "KAYBOLAN MESAJLAR")
    tk.Label(t_notif, text="Varsayılan süre (tüm yeni sohbetler için):",
             font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(
                 anchor="w", pady=(0, 4))

    disappear_var = tk.IntVar(value=cfg.get("default_disappear", 0))
    dis_f = tk.Frame(t_notif, bg=A.BG_CARD)
    dis_f.pack(fill="x")
    for val, txt in [(0, "Kapalı"), (30, "30 sn"), (300, "5 dk"),
                     (3600, "1 saat"), (86400, "1 gün")]:
        tk.Radiobutton(dis_f, text=txt, variable=disappear_var,
                       value=val, bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 8)).pack(
                           side="left", padx=(0, 8))

    # ── Engelli Kişiler ──
    _section(t_notif, "ENGELLİ KİŞİLER")
    _link(t_notif, "🚫 Engelli kişileri yönet...", actions["blocking"])

    # ── Dosya Transferi ──
    t_ft = tk.Frame(nb, bg=A.BG_CARD, padx=16, pady=12)
    nb.add(t_ft, text=A._t("ft_title"))
    _section(t_ft, A._t("ft_title"))

    tk.Label(t_ft, text=A._t("ft_download_dir"), font=(A.FONT, 8),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
    dl_var = tk.StringVar(value=cfg.get(
        "download_dir", os.path.expanduser("~/Downloads")))
    dl_row = tk.Frame(t_ft, bg=A.BG_CARD)
    dl_row.pack(fill="x", pady=(2, 0))
    ttk.Entry(dl_row, textvariable=dl_var, font=(A.FONT, 9)).pack(
        side="left", fill="x", expand=True, ipady=4)

    def _pick_dir():
        from tkinter import filedialog
        chosen = filedialog.askdirectory(initialdir=dl_var.get() or ".",
                                         parent=dlg)
        if chosen:
            dl_var.set(chosen)

    ttk.Button(dl_row, text="…", width=3, style="Small.TButton",
               command=_pick_dir).pack(side="left", padx=(6, 0))

    auto_var = tk.BooleanVar(value=bool(cfg.get("ft_auto_accept", False)))
    tk.Checkbutton(t_ft, text=A._t("ft_auto_accept"), variable=auto_var,
                   **chk_kw).pack(anchor="w", pady=(10, 0))

    tk.Label(t_ft, text=A._t("ft_block_size"), font=(A.FONT, 8),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(10, 2))
    bs_var = tk.StringVar(value=str(cfg.get("ft_block_size", 4096)))
    ttk.Combobox(t_ft, textvariable=bs_var, values=("4096", "8192"),
                 state="readonly", width=8).pack(anchor="w")

    tk.Label(t_ft, text=A._t("ft_warn_mb"), font=(A.FONT, 8),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(10, 2))
    warn_var = tk.StringVar(value=str(cfg.get("ft_warn_mb", 50)))
    ttk.Entry(t_ft, textvariable=warn_var, width=8).pack(anchor="w")

    # ═══════════════════════════════════════════════════════════════════
    # SEKME 4 — ŞİFRELEME
    # ═══════════════════════════════════════════════════════════════════
    t2 = tk.Frame(nb, bg=A.BG_CARD, padx=20, pady=16)
    nb.add(t2, text="  Şifreleme  ")

    # — Scrollable —
    enc_canvas = tk.Canvas(t2, bg=A.BG_CARD, highlightthickness=0)
    enc_scroll = ttk.Scrollbar(t2, orient="vertical",
                               command=enc_canvas.yview)
    enc_inner = tk.Frame(enc_canvas, bg=A.BG_CARD)
    enc_canvas.create_window((0, 0), window=enc_inner, anchor="nw")
    enc_canvas.configure(yscrollcommand=enc_scroll.set)
    enc_scroll.pack(side="right", fill="y")
    enc_canvas.pack(side="left", fill="both", expand=True)
    enc_inner.bind("<Configure>",
                   lambda _: enc_canvas.configure(scrollregion=enc_canvas.bbox("all")))
    enc_canvas.bind("<Button-4>",
                    lambda _: enc_canvas.yview_scroll(-3, "units"))
    enc_canvas.bind("<Button-5>",
                    lambda _: enc_canvas.yview_scroll(3, "units"))
    t2i = enc_inner  # alias

    tk.Label(t2i, text="OMEMO (XEP-0384)", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(0, 6))

    # OMEMO durumu
    omemo_f = tk.Frame(t2i, bg=A.BG_HOVER, padx=14, pady=10)
    omemo_f.pack(fill="x")
    omemo_ok = state["omemo_ok"]
    status_row = tk.Frame(omemo_f, bg=A.BG_HOVER)
    status_row.pack(fill="x")
    omemo_status = "Hazır" if omemo_ok else (
        "Yüklü değil" if not state["has_omemo"] else "Başlatılmadı")
    omemo_color = A.ACCENT_G if omemo_ok else A.RED
    dot = "🟢" if omemo_ok else "🔴"
    tk.Label(status_row, text="🔒 OMEMO", font=(A.FONT, 10, "bold"),
             fg=A.FG, bg=A.BG_HOVER).pack(side="left")
    tk.Label(status_row, text=f"  {dot} {omemo_status}",
             font=(A.FONT, 9), fg=omemo_color, bg=A.BG_HOVER).pack(side="left")

    # OMEMO cihaz bilgileri
    omemo_info_f = tk.Frame(t2i, bg=A.BG_CARD)
    omemo_info_f.pack(fill="x", pady=(8, 0))

    if omemo_ok:
        tk.Label(omemo_info_f, text="Cihaz bilgileri yükleniyor…",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")

        def _show_omemo_info(info):
            if not dlg.winfo_exists():
                return
            for w in omemo_info_f.winfo_children():
                w.destroy()
            if info is None or "error" in (info or {}):
                err = (info or {}).get("error", "Bilgi alınamadı")
                tk.Label(omemo_info_f, text=f"Hata: {err}",
                         font=(A.FONT, 8), fg=A.RED, bg=A.BG_CARD).pack(anchor="w")
                return
            dev_f = tk.Frame(omemo_info_f, bg=A.BG_HOVER, padx=12, pady=8)
            dev_f.pack(fill="x", pady=(0, 4))
            tk.Label(dev_f, text=f"Bu Cihaz  (ID: {info['device_id']})",
                     font=(A.FONT, 9, "bold"),
                     fg=A.ACCENT, bg=A.BG_HOVER).pack(anchor="w")
            fp_var = tk.StringVar(value=info["fingerprint"])
            fp_e = ttk.Entry(dev_f, textvariable=fp_var,
                             font=(A.FONT, 7), state="readonly",
                             style="Modern.TEntry")
            fp_e.pack(fill="x", pady=(4, 0))
            # Kopyala butonu
            copy_b = tk.Label(dev_f, text="📋 Kopyala", font=(A.FONT, 7),
                              fg=A.ACCENT, bg=A.BG_HOVER, cursor="hand2")
            copy_b.pack(anchor="w", pady=(2, 0))
            copy_b.bind("<Button-1>", lambda _: (
                dlg.clipboard_clear(),
                dlg.clipboard_append(info["fingerprint"]),
                copy_b.config(text="✓ Kopyalandı")))

            others = info.get("other_devices", [])
            if others:
                tk.Label(omemo_info_f,
                         text=f"Diğer Cihazlar ({len(others)})",
                         font=(A.FONT, 9, "bold"),
                         fg=A.FG, bg=A.BG_CARD).pack(anchor="w", pady=(8, 4))
                for dev in others:
                    df = tk.Frame(omemo_info_f, bg=A.BG_HOVER,
                                  padx=12, pady=6)
                    df.pack(fill="x", pady=(0, 3))
                    active = "aktif" if dev["active"] else "pasif"
                    ac = A.ACCENT_G if dev["active"] else A.FG_DIM
                    tk.Label(df, text=f"Cihaz: {dev['device_id']}  ({active})",
                             font=(A.FONT, 8, "bold"), fg=ac,
                             bg=A.BG_HOVER).pack(anchor="w")
                    dv = tk.StringVar(value=dev["fingerprint"])
                    de = ttk.Entry(df, textvariable=dv, font=(A.FONT, 7),
                                   state="readonly", style="Modern.TEntry")
                    de.pack(fill="x", pady=(2, 0))
            else:
                tk.Label(omemo_info_f,
                         text="Başka cihaz bulunamadı",
                         font=(A.FONT, 8), fg=A.FG_DIM,
                         bg=A.BG_CARD).pack(anchor="w", pady=(4, 0))

        actions["omemo_device_info"](_show_omemo_info)

    # PGP durumu
    _section(t2i, "OpenPGP (XEP-0027)")
    pgp_f = tk.Frame(t2i, bg=A.BG_HOVER, padx=14, pady=10)
    pgp_f.pack(fill="x")
    pgp_ok = state["pgp_ok"]
    pgp_row = tk.Frame(pgp_f, bg=A.BG_HOVER)
    pgp_row.pack(fill="x")
    pgp_status = "Hazır" if pgp_ok else "GPG bulunamadı"
    pgp_color = A.ACCENT_G if pgp_ok else A.FG_DIM
    pgp_dot = "🟢" if pgp_ok else "⚫"
    tk.Label(pgp_row, text="🔑 OpenPGP", font=(A.FONT, 10, "bold"),
             fg=A.FG, bg=A.BG_HOVER).pack(side="left")
    tk.Label(pgp_row, text=f"  {pgp_dot} {pgp_status}",
             font=(A.FONT, 9), fg=pgp_color, bg=A.BG_HOVER).pack(side="left")

    keys = state["pgp_keys"]   # owner'da okunamadıysa None
    if pgp_ok and keys:
        try:
            tk.Label(pgp_f, text=f"Anahtar: {len(keys)} adet",
                     font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_HOVER).pack(
                         anchor="w", pady=(4, 0))
            for k in keys[:5]:
                uids = ", ".join(k.get("uids", [])[:2]) or "—"
                tk.Label(pgp_f, text=f"  {k['keyid']}  {uids}",
                         font=(A.FONT, 7), fg=A.FG_DIM,
                         bg=A.BG_HOVER).pack(anchor="w")
        except Exception:
            pass

    # PGP Anahtar Eşleştirme
    if pgp_ok:
        _section(t2i, "PGP ANAHTAR EŞLEŞTİRME")
        tk.Label(t2i, text="JID → GPG Key ID eşleştirmesi",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(
                     anchor="w", pady=(0, 6))

        pgp_map_f = tk.Frame(t2i, bg=A.BG_CARD)
        pgp_map_f.pack(fill="x")

        saved_pgp = cfg.get("pgp_keymap", {})
        pgp_entries = []

        def _add_pgp_row(jid_val="", keyid_val=""):
            row = tk.Frame(pgp_map_f, bg=A.BG_CARD)
            row.pack(fill="x", pady=2)
            jv = tk.StringVar(value=jid_val)
            kv = tk.StringVar(value=keyid_val)
            jb = tk.Frame(row, bg=A.BORDER, padx=1, pady=1)
            jb.pack(side="left", fill="x", expand=True)
            ttk.Entry(jb, textvariable=jv, font=(A.FONT, 8),
                      width=24, style="Modern.TEntry").pack(
                          fill="x", ipady=3, padx=1, pady=1)
            kb = tk.Frame(row, bg=A.BORDER, padx=1, pady=1)
            kb.pack(side="left", padx=(4, 0))
            ttk.Entry(kb, textvariable=kv, font=(A.FONT, 8),
                      width=12, style="Modern.TEntry").pack(
                          fill="x", ipady=3, padx=1, pady=1)
            rm = tk.Label(row, text="✕", font=(A.FONT, 9), fg=A.RED,
                          bg=A.BG_CARD, cursor="hand2")
            rm.pack(side="left", padx=(4, 0))
            rm.bind("<Button-1>", lambda _: (
                row.destroy(), pgp_entries.remove((jv, kv))))
            pgp_entries.append((jv, kv))

        hdr = tk.Frame(pgp_map_f, bg=A.BG_CARD)
        hdr.pack(fill="x")
        tk.Label(hdr, text="JID", font=(A.FONT, 7, "bold"),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(side="left")
        tk.Label(hdr, text="Key ID", font=(A.FONT, 7, "bold"),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(side="right", padx=(0, 24))

        for jid_key, kid in saved_pgp.items():
            _add_pgp_row(jid_key, kid)

        add_b = tk.Label(pgp_map_f, text="+ Eşleştirme Ekle",
                         font=(A.FONT, 8), fg=A.ACCENT, bg=A.BG_CARD,
                         cursor="hand2")
        add_b.pack(anchor="w", pady=(4, 0))
        add_b.bind("<Button-1>", lambda _: _add_pgp_row())
        actions["pgp_entries"](pgp_entries)

    # QR Doğrulama
    _section(t2i, "OMEMO QR DOĞRULAMA")
    _link(t2i, "🔐 QR Kod ile Parmak İzi Doğrula…", actions["omemo_qr"])
    if state["has_qrcode"]:
        tk.Label(t2i, text="🟢 qrcode kütüphanesi yüklü",
                 font=(A.FONT, 7), fg=A.ACCENT_G, bg=A.BG_CARD).pack(anchor="w", pady=(2, 0))
    else:
        tk.Label(t2i, text="⚫ QR için: pip install qrcode[pil]",
                 font=(A.FONT, 7), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(2, 0))

    # Varsayılan şifreleme
    _section(t2i, "VARSAYILAN ŞİFRELEME")
    default_enc_var = tk.StringVar(
        value=cfg.get("default_encryption", "none"))
    enc_opts = [("🔓 Kapalı", "none"), ("🔒 OMEMO", "omemo"),
                ("🔑 OpenPGP", "pgp")]
    for label, val in enc_opts:
        tk.Radiobutton(t2i, text=label, variable=default_enc_var,
                       value=val, bg=A.BG_CARD, fg=A.FG,
                       selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, activeforeground=A.FG,
                       font=(A.FONT, 9)).pack(anchor="w")

    # ═══════════════════════════════════════════════════════════════════
    # SEKME 5 — BAĞLANTI
    # ═══════════════════════════════════════════════════════════════════
    t_conn = _scroll_tab("  Bağlantı  ")

    tk.Label(t_conn, text="BAĞLANTI AYARLARI", font=(A.FONT, 7, "bold"),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(0, 6))

    auto_rejoin_var = tk.BooleanVar(value=cfg.get("auto_rejoin", True))
    tk.Checkbutton(t_conn, text="Odalara otomatik yeniden katıl",
                   variable=auto_rejoin_var, **chk_kw).pack(anchor="w")

    # ── Otomatik Uzakta ──
    _section(t_conn, "OTOMATİK UZAKTA")
    tk.Label(t_conn, text="İşlem yapılmadığında otomatik uzakta durumuna geç:",
             font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", pady=(0, 4))
    idle_var = tk.IntVar(value=cfg.get("idle_after_min", 5))
    idle_f = tk.Frame(t_conn, bg=A.BG_CARD)
    idle_f.pack(fill="x")
    for val, txt in [(0, "Kapalı"), (3, "3 dk"), (5, "5 dk"),
                     (10, "10 dk"), (15, "15 dk"), (30, "30 dk")]:
        tk.Radiobutton(idle_f, text=txt, variable=idle_var,
                       value=val, bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, font=(A.FONT, 8)).pack(
                           side="left", padx=(0, 6))

    # ── Bağlantı Kalitesi ──
    _section(t_conn, "BAĞLANTI KALİTESİ")
    ping_ms = state["ping_ms"]
    if ping_ms < 0:
        ping_txt = "📶 Bağlantı yok"
        ping_c = A.RED
    elif ping_ms == 0:
        ping_txt = "📶 Henüz ölçülmedi"
        ping_c = A.FG_DIM
    else:
        ping_txt = f"📶 Gecikme: {ping_ms} ms"
        ping_c = A.ONLINE if ping_ms < 100 else (A.AWAY if ping_ms < 300 else A.RED)
    tk.Label(t_conn, text=ping_txt, font=(A.FONT, 9, "bold"),
             fg=ping_c, bg=A.BG_CARD).pack(anchor="w")

    # Kayıtlı odalar
    _section(t_conn, "KAYITLI ODALAR")
    saved_rooms = cfg.get("rooms", {})
    rooms_f = tk.Frame(t_conn, bg=A.BG_CARD)
    rooms_f.pack(fill="x")

    if saved_rooms:
        for room_jid, room_cfg in list(saved_rooms.items()):
            rf = tk.Frame(rooms_f, bg=A.BG_HOVER, padx=10, pady=5)
            rf.pack(fill="x", pady=2)
            nick = room_cfg.get("nick", "?") if isinstance(room_cfg, dict) else "?"
            tk.Label(rf, text=f"🏠 {room_jid}", font=(A.FONT, 8),
                     fg=A.FG, bg=A.BG_HOVER).pack(side="left")
            tk.Label(rf, text=nick, font=(A.FONT, 7),
                     fg=A.FG_DIM, bg=A.BG_HOVER).pack(side="right")
    else:
        tk.Label(rooms_f, text="Kayıtlı oda yok",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")

    # Bağlantı durumu
    _section(t_conn, "BAĞLANTI DURUMU")
    conn_f = tk.Frame(t_conn, bg=A.BG_HOVER, padx=14, pady=10)
    conn_f.pack(fill="x")
    connected = state["connected"]
    conn_dot = "🟢" if connected else "🔴"
    conn_text = "Bağlı" if connected else "Bağlı değil"
    tk.Label(conn_f, text=f"{conn_dot}  {conn_text}",
             font=(A.FONT, 10, "bold"), fg=A.FG, bg=A.BG_HOVER).pack(
                 anchor="w")
    if connected:
        tk.Label(conn_f, text=f"Hesap: {jid}",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_HOVER).pack(anchor="w")
        tk.Label(conn_f, text=f"Kişiler: {state['contacts_count']}  •  "
                              f"Aktif Odalar: {state['rooms_count']}",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_HOVER).pack(anchor="w")

    # ── Proxy / SOCKS ──
    _section(t_conn, "PROXY / ANONİM BAĞLANTI")
    proxy_cfg = cfg.get("proxy", {})
    proxy_type = proxy_cfg.get("type", "none")
    proxy_txt = f"Tür: {proxy_type}" if proxy_type != "none" else "Yapılandırılmamış"
    tk.Label(t_conn, text=f"🔒 {proxy_txt}", font=(A.FONT, 8),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
    _link(t_conn, "🔧 Proxy Ayarları…", actions["proxy"], pady=(4, 0))

    # ── Otomatik Tema Geçişi ──
    _section(t_conn, "OTOMATİK TEMA GEÇİŞİ")
    auto_theme = cfg.get("auto_theme", False)
    at_txt = "🟢 Aktif" if auto_theme else "⚫ Kapalı"
    tk.Label(t_conn, text=f"🌓 {at_txt}", font=(A.FONT, 8),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
    _link(t_conn, "🌓 Otomatik Tema Ayarları…", actions["auto_theme"], pady=(4, 0))

    # ── Güvenlik ──
    _section(t_conn, "GÜVENLİK")
    _link(t_conn, "🔑 Uygulama Kilidi (PIN)…", actions["pin_lock"])
    _link(t_conn, "🗑 Mesaj Geçmişini Sil…", actions["clear_history"],
          fg=A.RED, pady=(4, 0))

    # ═══════════════════════════════════════════════════════════════════
    # SEKME 6 — HAKKINDA
    # ═══════════════════════════════════════════════════════════════════
    t3 = _scroll_tab("  Hakkında  ")

    # Logo / başlık
    logo_c = tk.Canvas(t3, width=64, height=64, bg=A.BG_CARD,
                       highlightthickness=0)
    logo_c.pack(pady=(0, 8))
    logo_c.create_oval(2, 2, 62, 62, fill=A.ACCENT2, outline=A.ACCENT, width=2)
    logo_c.create_text(32, 32, text="X", fill=A.FG_ME,
                       font=(A.FONT, 22, "bold"))

    tk.Label(t3, text="XMPP İstemci", font=(A.FONT, 16, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack()
    tk.Label(t3, text="deneme.py — Modern Tkinter XMPP İstemcisi",
             font=(A.FONT, 9), fg=A.FG_DIM, bg=A.BG_CARD).pack(pady=(2, 16))

    # Bilgi kartları
    info_f = tk.Frame(t3, bg=A.BG_CARD)
    info_f.pack(fill="x")
    for lbl, val in state["about"]:
        row = tk.Frame(info_f, bg=A.BG_CARD)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=f"{lbl}:", font=(A.FONT, 8, "bold"),
                 fg=A.FG_DIM, bg=A.BG_CARD, width=14, anchor="e").pack(
                     side="left")
        tk.Label(row, text=val, font=(A.FONT, 8),
                 fg=A.FG, bg=A.BG_CARD).pack(side="left", padx=(8, 0))

    _section(t3, "KÜTÜPHANELER")
    lib_f = tk.Frame(t3, bg=A.BG_CARD)
    lib_f.pack(fill="x")
    col = 0
    for lib_txt in state["libs"]:
        tk.Label(lib_f, text=lib_txt, font=(A.FONT, 8),
                 fg=A.FG_DIM, bg=A.BG_CARD, anchor="w").grid(
                     row=col // 2, column=col % 2, sticky="w", padx=(0, 20))
        col += 1

    # Dışa aktarma
    _section(t3, "VERİ")
    export_f = tk.Frame(t3, bg=A.BG_CARD)
    export_f.pack(fill="x")
    _link(export_f, "📤 Sohbetleri Dışa Aktar", actions["export_chat"])

    exp_cfg = tk.Label(export_f, text="📋 Ayarları Kopyala",
                       font=(A.FONT, 9), fg=A.ACCENT, bg=A.BG_CARD,
                       cursor="hand2")
    exp_cfg.pack(anchor="w", pady=(4, 0))
    exp_cfg.bind("<Button-1>", lambda _: (
        dlg.clipboard_clear(),
        dlg.clipboard_append(actions["config_json"]()),
        exp_cfg.config(text="✓ Kopyalandı")))

    _link(export_f, "💾 Yedekleme / Geri Yükleme…", actions["backup"], pady=(4, 0))

    # Kısayollar
    _section(t3, "KLAVYE KISAYOLLARI")
    _link(t3, "⌨ Kısayolları Göster…", actions["shortcuts"])

    shortcuts_info = tk.Frame(t3, bg=A.BG_CARD)
    shortcuts_info.pack(fill="x", pady=(4, 0))
    for key, desc in [("Ctrl+F", "Sohbette Ara"), ("Ctrl+K", "Hızlı Geçiş"),
                      ("Ctrl+N", "Yeni Sohbet"), ("Ctrl+B", "Yedekleme")]:
        row = tk.Frame(shortcuts_info, bg=A.BG_CARD)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=key, font=("Courier", 7, "bold"),
                 fg=A.ACCENT, bg=A.BG_CARD, width=8, anchor="w").pack(side="left")
        tk.Label(row, text=desc, font=(A.FONT, 7),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(side="left", padx=(4, 0))

    # ═══════════════════════════════════════════════════════════════════
    # KAYDET BUTONU
    # ═══════════════════════════════════════════════════════════════════
    btn_f = tk.Frame(outer, bg=A.BG_CARD, padx=12, pady=10)
    btn_f.pack(fill="x")
    tk.Frame(btn_f, bg=A.BORDER, height=1).pack(fill="x", pady=(0, 10))

    def _save():
        on_save({
            "notifications": notify_var.get(),
            "sounds": sound_var.get(),
            "status_text": status_var.get(),
            "presence_show": show_var.get(),
            "accounts": accounts,
            "auto_login": auto_login_var.get(),
            "theme": theme_var.get(),
            "font_size": font_var.get(),
            "font_family": font_family_var.get(),
            "language": lang_var.get(),
            "send_read_receipts": read_receipt_var.get(),
            "send_typing": typing_var.get(),
            "default_disappear": disappear_var.get(),
            "auto_rejoin": auto_rejoin_var.get(),
            "idle_after_min": idle_var.get(),
            "compact_mode": compact_var.get(),
            "default_encryption": default_enc_var.get(),
            # Dosya transferi: ham giriş; doğrulama owner'da
            "download_dir": dl_var.get(),
            "ft_auto_accept": auto_var.get(),
            "ft_block_size": bs_var.get(),
            "ft_warn_mb": warn_var.get(),
        })
        dlg.destroy()

    save_btn = ttk.Button(btn_f, text="  Kaydet ve Kapat  ",
                          command=_save)
    save_btn.pack(fill="x", ipady=6)

    # İptal butonu
    cancel_btn = tk.Label(btn_f, text="İptal", font=(A.FONT, 8),
                          fg=A.FG_DIM, bg=A.BG_CARD, cursor="hand2")
    cancel_btn.pack(pady=(6, 0))
    cancel_btn.bind("<Button-1>", lambda _: dlg.destroy())

    dlg.lift()
    return dlg
