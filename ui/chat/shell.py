"""ChatView statik shell/layout kurulumu (Faz 4C-1).

Yalnız Tk widget construction + layout + callback wiring. Domain/bot/storage/
network/thread YOKTUR. Tema değerleri construction anında input olarak alınır
(import-time snapshot yok; çağıran canlı değerleri geçirir).
"""
import tkinter as tk
from tkinter import ttk


class ChatShell:
    """Sohbet panelinin widget graph'ını kurar ve sahiplenir.

    Geçici compatibility: MainWindow eski attribute adlarına (LEGACY_REFS)
    aynı widget nesneleriyle alias bağlar; duplicate state yoktur.
    """

    LEGACY_REFS = (
        "_chat_panel", "_hdr_avatar", "chat_title", "_chat_subject",
        "typing_label", "_enc_badge", "_empty_state", "_chat_area",
        "chat_canvas", "msg_frame", "_canvas_win", "_input_area",
        "_reply_bar", "_reply_lbl", "_pin_bar", "_pin_lbl",
        "_encryption_mode", "_inp_border", "msg_var", "_msg_entry",
        "_emoji_btn", "_gif_btn", "_file_btn", "_mic_btn", "_enc_btn",
        "_send_c",
    )

    def __init__(self, parent, t, theme, callbacks, entry_cls,
                 add_tooltip=None):
        self.t = t
        self.th = theme
        self.cb = callbacks
        self.entry_cls = entry_cls
        self._add_tooltip = add_tooltip or (lambda w, s: None)
        self._build(parent)

    # ── Widget graph ────────────────────────────────────────────────────────
    def _build(self, parent):
        th = self.th
        t = self.t

        self._chat_panel = tk.Frame(parent, bg=th["BG_CHAT"])
        self._chat_panel.grid(row=0, column=1, sticky="nsew")
        self._chat_panel.columnconfigure(0, weight=1)
        self._chat_panel.rowconfigure(1, weight=1)
        panel = self._chat_panel

        # ── Üst başlık çubuğu (gradient arka plan) ──
        hdr = tk.Frame(panel, bg=th["BG_CARD"], padx=22, pady=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(1, weight=1)
        hdr.configure(height=66)
        hdr.grid_propagate(False)
        grad_line = tk.Canvas(panel, height=3, bg=th["BG_CHAT"],
                              highlightthickness=0)
        grad_line.grid(row=0, column=0, sticky="sew")

        def _draw_hdr_line(e):
            grad_line.delete("all")
            w = e.width
            grad_line.create_rectangle(w * 0.1, 0, w * 0.9, 1,
                                       fill=th["ACCENT2"], outline="")
            grad_line.create_rectangle(w * 0.25, 1, w * 0.75, 2,
                                       fill=th["ACCENT"], outline="")
            grad_line.create_rectangle(0, 2, w, 3, fill=th["BORDER"],
                                       outline="")

        grad_line.bind("<Configure>", _draw_hdr_line)

        # Avatar: çift halkalı (büyütülmüş + glow)
        self._hdr_avatar = tk.Canvas(hdr, width=46, height=46,
                                     bg=th["BG_CARD"], highlightthickness=0)
        self._hdr_avatar.grid(row=0, column=0, rowspan=2, padx=(0, 16),
                              pady=10)
        self._hdr_avatar.create_oval(0, 0, 46, 46, fill="",
                                     outline=th["ACCENT2"], width=2)
        self._hdr_avatar.create_oval(4, 4, 42, 42, fill=th["BG_HOVER"],
                                     outline="")
        self._hdr_avatar.create_text(23, 23, text="?",
                                     fill=th["FG_DIM"],
                                     font=(th["FONT"], 14, "bold"))

        title_frame = tk.Frame(hdr, bg=th["BG_CARD"])
        title_frame.grid(row=0, column=1, rowspan=2, sticky="nsw",
                         pady=(6, 0))

        self.chat_title = tk.Label(title_frame, text=t("select_chat"),
                                   font=(th["FONT"], 13, "bold"),
                                   fg=th["FG"], bg=th["BG_CARD"], anchor="w")
        self.chat_title.pack(anchor="w")

        self._chat_subject = tk.Label(title_frame, text="",
                                      font=(th["FONT"], 8), fg=th["FG_DIM"],
                                      bg=th["BG_CARD"], anchor="w")

        self.typing_label = tk.Label(title_frame, text="",
                                     font=(th["FONT"], 8), fg=th["ACCENT"],
                                     bg=th["BG_CARD"])
        self.typing_label.pack(anchor="w")

        self._enc_badge = tk.Label(hdr, text="", font=(th["FONT"], 8),
                                   fg=th["ACCENT_G"], bg=th["BG_CARD"])
        self._enc_badge.grid(row=0, column=2, rowspan=2, padx=(8, 0))

        more_btn = tk.Label(hdr, text="⋮", font=(th["FONT"], 14),
                            fg=th["FG_DIM"], bg=th["BG_CARD"], cursor="hand2")
        more_btn.grid(row=0, column=3, rowspan=2, padx=(8, 0))
        more_btn.bind("<Button-1>", self.cb["on_header_menu"])
        more_btn.bind("<Enter>", lambda _: more_btn.config(fg=th["FG"]))
        more_btn.bind("<Leave>", lambda _: more_btn.config(fg=th["FG_DIM"]))

        # ── Boş durum ekranı ──
        self._empty_state = tk.Frame(panel, bg=th["BG_CHAT"])
        self._empty_state.grid(row=1, column=0, sticky="nsew")

        inner = tk.Frame(self._empty_state, bg=th["BG_CHAT"])
        inner.place(relx=0.5, rely=0.4, anchor="center")

        deco = tk.Canvas(inner, width=90, height=90,
                         bg=th["BG_CHAT"], highlightthickness=0)
        deco.pack(pady=(0, 20))
        deco.create_oval(2, 2, 88, 88, fill=th["BG_CARD"],
                         outline=th["BORDER"], width=1)
        deco.create_oval(12, 12, 78, 78, fill=th["BG_THEM"], outline="")
        deco.create_text(45, 43, text="💬", fill=th["ACCENT"],
                         font=(th["FONT"], 24))

        tk.Label(inner, text=t("start_conversation"),
                 font=(th["FONT"], 18, "bold"), fg=th["FG"],
                 bg=th["BG_CHAT"]).pack()
        tk.Label(inner, text=t("select_contact"),
                 font=(th["FONT"], 10), fg=th["FG_DIM"],
                 bg=th["BG_CHAT"]).pack(pady=(8, 32))

        btn_frame = tk.Frame(inner, bg=th["BG_CHAT"])
        btn_frame.pack()
        for txt, cmd in [(t("start_chat"), self.cb["on_add_contact"]),
                         (t("join_room"), self.cb["on_join_room"]),
                         (t("discover_rooms"),
                          self.cb["on_discover_rooms"])]:
            ttk.Button(btn_frame, text=f"  {txt}  ",
                       command=cmd).pack(side="left", padx=6)

        # ── Canvas mesaj alanı ──
        chat_area = tk.Frame(panel, bg=th["BG_CHAT"])
        chat_area.grid(row=1, column=0, sticky="nsew")
        self._chat_area = chat_area
        chat_area.grid_remove()
        chat_area.columnconfigure(0, weight=1)
        chat_area.rowconfigure(0, weight=1)

        self.chat_canvas = tk.Canvas(chat_area, bg=th["BG_CHAT"],
                                     highlightthickness=0, bd=0)
        vsb = self._vsb = ttk.Scrollbar(chat_area, orient="vertical",
                                        command=self.chat_canvas.yview)
        # Takip: kullanıcı en alttayken yeni içerik görünümü alta indirir;
        # yukarı kaydırınca kapanır, en alta dönünce açılır (_on_yscroll)
        self.following = True
        self._scroll_region = None
        self._msg_frame_size = None
        self.chat_canvas.configure(yscrollcommand=self._on_yscroll)
        self.chat_canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.msg_frame = tk.Frame(self.chat_canvas, bg=th["BG_CHAT"])
        self._canvas_win = self.chat_canvas.create_window(
            (0, 0), window=self.msg_frame, anchor="nw")

        self.msg_frame.bind("<Configure>", self._on_msg_frame_configure)
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)
        self.chat_canvas.bind("<Enter>", self.cb["on_canvas_enter"])
        self.chat_canvas.bind("<Leave>", self._on_canvas_leave)

        # ── Giriş çubuğu ──
        inp_wrap = tk.Frame(panel, bg=th["BG_CARD"])
        inp_wrap.grid(row=2, column=0, sticky="ew")
        self._input_area = inp_wrap
        inp_wrap.grid_remove()

        tk.Frame(inp_wrap, bg=th["BORDER"], height=1).pack(side="top",
                                                           fill="x")

        # Yanıt çubuğu (gizli başlar)
        self._reply_bar = tk.Frame(inp_wrap, bg=th["BG_HOVER"], padx=16,
                                   pady=6)
        self._reply_lbl = tk.Label(self._reply_bar, text="", fg=th["ACCENT"],
                                   bg=th["BG_HOVER"], font=(th["FONT"], 8),
                                   anchor="w", wraplength=400)
        self._reply_lbl.pack(side="left", fill="x", expand=True)
        reply_close = tk.Label(self._reply_bar, text="✕", fg=th["FG_DIM"],
                               bg=th["BG_HOVER"], font=(th["FONT"], 10),
                               cursor="hand2")
        reply_close.pack(side="right", padx=(8, 0))
        reply_close.bind("<Button-1>", lambda _: self.cb["on_cancel_reply"]())

        # Sabitlenmiş mesaj çubuğu (gizli başlar)
        self._pin_bar = tk.Frame(inp_wrap, bg="#1a1a2e", padx=16, pady=4)
        self._pin_lbl = tk.Label(self._pin_bar, text="", fg=th["FG_DIM"],
                                 bg="#1a1a2e", font=(th["FONT"], 7),
                                 anchor="w", wraplength=400)
        self._pin_lbl.pack(side="left", fill="x", expand=True)
        pin_show = tk.Label(self._pin_bar, text="📌", fg=th["ACCENT"],
                            bg="#1a1a2e", font=(th["FONT"], 10),
                            cursor="hand2")
        pin_show.pack(side="right")
        pin_show.bind("<Button-1>", lambda _: self.cb["on_show_pinned"]())

        inf = tk.Frame(inp_wrap, bg=th["BG_CARD"], padx=18, pady=14)
        inf.pack(fill="x")

        self._encryption_mode = tk.StringVar(value="none")

        # Rounded input sarmalayıcı
        self._inp_border = tk.Frame(inf, bg=th["BORDER"], padx=1, pady=1)
        inp_border = self._inp_border
        inp_border.grid(row=0, column=0, sticky="ew")
        inp_inner = tk.Frame(inp_border, bg=th["BG_HOVER"])
        inp_inner.pack(fill="x")
        inp_inner.columnconfigure(0, weight=1)

        self.msg_var = tk.StringVar()
        msg_entry = self.entry_cls(inp_inner,
                                   placeholder=t("message_placeholder"),
                                   textvariable=self.msg_var,
                                   font=(th["FONT"], 11),
                                   style="Modern.TEntry")
        msg_entry.grid(row=0, column=0, sticky="ew", ipady=10, padx=(10, 0))
        msg_entry.bind("<Return>", self.cb["on_send"])
        msg_entry.bind("<Control-v>", self.cb["on_paste"])
        msg_entry.bind("<KeyRelease>", self.cb["on_typing"])
        self._msg_entry = msg_entry
        inf.columnconfigure(0, weight=1)

        # AI asistanı butonu (isteğe bağlı callback; giriş kutusunun içinde)
        self._ai_btn = None
        on_ai = self.cb.get("on_ai")
        if on_ai is not None:
            self._ai_btn = tk.Label(
                inp_inner, text="✨", font=(th["FONT"], 12),
                bg=th["BG_HOVER"], fg=th["FG_DIM"], cursor="hand2", padx=6)
            self._ai_btn.grid(row=0, column=1, padx=(4, 6))
            self._ai_btn.bind("<Button-1>", on_ai)
            self._ai_btn.bind("<Enter>",
                              lambda _: self._ai_btn.config(fg=th["ACCENT"]))
            self._ai_btn.bind("<Leave>",
                              lambda _: self._ai_btn.config(fg=th["FG_DIM"]))
            self._add_tooltip(self._ai_btn, t("ai_assistant"))

        # Emoji butonu
        self._emoji_btn = tk.Label(
            inf, text="😊", font=(th["FONT"], 14), bg=th["BG_CARD"],
            fg=th["FG_DIM"], cursor="hand2", padx=4)
        self._emoji_btn.grid(row=0, column=1, padx=(8, 0))
        self._emoji_btn.bind("<Button-1>", lambda _: self.cb["on_emoji"]())
        self._emoji_btn.bind("<Enter>",
                             lambda _: self._emoji_btn.config(fg=th["ACCENT"]))
        self._emoji_btn.bind("<Leave>",
                             lambda _: self._emoji_btn.config(fg=th["FG_DIM"]))

        # Sticker/GIF butonu
        self._gif_btn = tk.Label(
            inf, text="🎭", font=(th["FONT"], 14), bg=th["BG_CARD"],
            fg=th["FG_DIM"], cursor="hand2", padx=4)
        self._gif_btn.grid(row=0, column=2, padx=(6, 0))
        self._gif_btn.bind("<Button-1>", lambda _: self.cb["on_gif"]())
        self._gif_btn.bind("<Enter>",
                           lambda _: self._gif_btn.config(fg=th["ACCENT"]))
        self._gif_btn.bind("<Leave>",
                           lambda _: self._gif_btn.config(fg=th["FG_DIM"]))
        self._add_tooltip(self._gif_btn, t("sticker_gif"))

        # Dosya gönder butonu
        self._file_btn = tk.Label(
            inf, text="📎", font=(th["FONT"], 14), bg=th["BG_CARD"],
            fg=th["FG_DIM"], cursor="hand2", padx=4)
        self._file_btn.grid(row=0, column=3, padx=(6, 0))
        self._file_btn.bind("<Button-1>", lambda _: self.cb["on_file"]())
        self._file_btn.bind("<Enter>",
                            lambda _: self._file_btn.config(fg=th["ACCENT"]))
        self._file_btn.bind("<Leave>",
                            lambda _: self._file_btn.config(fg=th["FG_DIM"]))

        # Ses mesajı butonu
        self._mic_btn = tk.Label(
            inf, text="🎤", font=(th["FONT"], 14), bg=th["BG_CARD"],
            fg=th["FG_DIM"], cursor="hand2", padx=4)
        self._mic_btn.grid(row=0, column=4, padx=(6, 0))
        self._mic_btn.bind("<Button-1>", lambda _: self.cb["on_voice"]())
        self._mic_btn.bind("<Enter>",
                           lambda _: self._mic_btn.config(fg=th["RED"]))
        self._mic_btn.bind("<Leave>",
                           lambda _: self._mic_btn.config(fg=th["FG_DIM"]))

        # Şifreleme butonu
        self._enc_btn = tk.Label(
            inf, text="🔓", font=(th["FONT"], 14), bg=th["BG_CARD"],
            fg=th["FG_DIM"], cursor="hand2", padx=4)
        self._enc_btn.grid(row=0, column=5, padx=(6, 0))
        self._enc_btn.bind("<Button-1>", self.cb["on_encryption"])
        self._enc_btn.bind("<Enter>",
                           lambda _: self._enc_btn.config(fg=th["ACCENT_G"]))
        self._enc_btn.bind("<Leave>",
                           lambda _: self._enc_btn.config(fg=th["FG_DIM"]))

        # Gönder butonu — yuvarlak Canvas (büyütülmüş)
        self._send_c = tk.Canvas(inf, width=44, height=44,
                                 bg=th["BG_CARD"], highlightthickness=0,
                                 cursor="hand2")
        self._send_c.grid(row=0, column=6, padx=(8, 0))
        self._draw_send()
        self._send_c.bind("<Button-1>", self.cb["on_send"])
        self._send_c.bind("<Enter>", lambda _: self._draw_send(hover=True))
        self._send_c.bind("<Leave>", lambda _: self._draw_send(hover=False))

    # ── Shell davranışları (saf görsel) ─────────────────────────────────────
    def _draw_send(self, hover=False):
        th = self.th
        c = self._send_c
        c.delete("all")
        color = th["ACCENT"] if hover else th["ACCENT2"]
        if hover:
            c.create_oval(0, 0, 44, 44, fill="", outline=th["GLOW"], width=3)
        c.create_oval(3, 3, 41, 41, fill=color, outline="")
        c.create_text(22, 22, text="▶", fill=th["FG_ME"],
                      font=(th["FONT"], 14, "bold"))

    def _on_msg_frame_configure(self, event):
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        # <Configure> konum değişiminde de gelir: tekerlek çerçeveyi yalnız
        # TAŞIR. Yalnız boyut değişince (içerik) alta in; yoksa kaydırma
        # 10 ms sonra geri alınır ve tekerlek çalışmaz.
        size = (event.width, event.height)
        if size == self._msg_frame_size:
            return
        self._msg_frame_size = size
        if self.following:          # yukarıda okuyan kullanıcı çekilmez
            self.chat_canvas.after(10,
                                   lambda: self.chat_canvas.yview_moveto(1.0))

    def _on_yscroll(self, first, last):
        """Kaydırma çubuğu + takip kararı. Bölge aynıyken görünüm değiştiyse
        kaydıran kullanıcıdır (ya da bilinçli bir moveto): en alttaysa takip
        sürer. Bölge değiştiyse içerik büyümüştür; karar değişmez."""
        self._vsb.set(first, last)
        region = self.chat_canvas.cget("scrollregion")
        if region == self._scroll_region:
            self.following = float(last) >= 0.999
        else:
            self._scroll_region = region

    def follow_bottom(self):
        """Takibi aç (sohbet açma, gönderme, "↓ En yeni")."""
        self.following = True

    def _on_canvas_leave(self, event):
        # Tuvalden içindeki mesaj alanına geçmek de <Leave> verir (X:
        # NotifyInferior); imleç hâlâ sohbetteyse tekerlek açık kalır
        if not self._pointer_in_chat(event):
            self.cb["on_canvas_leave"](event)

    def _pointer_in_chat(self, event) -> bool:
        try:
            w = self.chat_canvas.winfo_containing(event.x_root, event.y_root)
        except Exception:           # Tk'nın kendi pencereleri (menü vb.)
            return False
        while w is not None:
            if w is self.chat_canvas:
                return True
            w = getattr(w, "master", None)
        return False

    def _on_canvas_configure(self, event):
        self.chat_canvas.itemconfig(self._canvas_win, width=event.width)

    def show_empty_state(self):
        self._chat_area.grid_remove()
        self._input_area.grid_remove()
        self._empty_state.grid(row=1, column=0, sticky="nsew")

    def show_chat(self):
        """Sohbet görünümünü göster (empty → chat geçişi)."""
        self._empty_state.grid_remove()
        self._chat_area.grid(row=1, column=0, sticky="nsew")
        self._input_area.grid(row=2, column=0, sticky="ew")
