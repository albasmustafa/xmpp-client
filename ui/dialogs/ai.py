"""AI asistanı pencereleri: sonuç/sohbet, anlamsal arama, eylemler, ayarlar.

Kurallar (ui/dialogs/simple.py ile aynı):
- MainWindow state'ine doğrudan erişim yok; veri/eylemler parametre ve
  callback ile gelir. Ağ/model/thread YOKTUR — sonuçlar MainWindow'dan
  GUI thread'inde `set_*` / `append_text` çağrılarıyla gelir.
- Tema/yardımcı semboller çağrı anında `xmpp`'den okunur (`_app()`).
- Pencere sonuç gelmeden kapatılabilir: tüm `set_*` metotları `alive()`
  kontrolüyle sessizce yok sayılır; kapanış `on_close` ile bildirilir
  (MainWindow süren akışı iptal eder).
"""
import tkinter as tk
from tkinter import ttk

from ui.dialogs.simple import _app


def _alive(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def _link_button(parent, text, command, *, fg=None, bg=None):
    A = _app()
    bg = bg or A.BG_CARD
    lbl = tk.Label(parent, text=text, font=(A.FONT, 9), fg=fg or A.ACCENT,
                   bg=bg, cursor="hand2", padx=8, pady=4)
    lbl.bind("<Button-1>", lambda _e: command())
    lbl.bind("<Enter>", lambda _e: lbl.config(bg=A.BG_HOVER))
    lbl.bind("<Leave>", lambda _e: lbl.config(bg=bg))
    return lbl


class ResultWindow:
    """AI sonuç penceresi; isteğe bağlı akış, takip soruları ve kaynaklar.

    `actions`: [(etiket, fn(metin))] — son yanıt metniyle çağrılır.
    `on_ask(soru)`: verilirse altta soru kutusu çıkar. MainWindow soruyu
    kabul ederse `begin_question` çağırır; kutu yanıt (`set_answer`) ya da
    hata (`set_error`) gelene dek kilitlidir. Kutu ilk yanıttan sonra açılır
    (`ask_ready=True` → baştan açık; ör. geçmişe sor).
    `on_close()`: pencere kapanınca/yok edilince bir kez çağrılır.
    Akış: `append_text` parçaları geçerli yanıtın sonuna ekler; `set_text`
    / `set_answer` kesin metinle değiştirir; `set_error` kısmi yanıtı (ve
    yanıtlanamayan takip sorusunu) siler, soruyu kutuya geri koyar.
    """

    def __init__(self, parent, title, subtitle="", actions=(), *,
                 on_ask=None, on_close=None,
                 ask_hint="Takip sorusu sorun…", ask_ready=False):
        A = _app()
        self._text_value = ""
        self._actions = list(actions)
        self._on_ask = on_ask
        self._on_close = on_close
        self._ask_ready = bool(ask_ready)
        self._ask_enabled = False
        self._ask_entry = None
        self._ask_var = None
        self._partial = False        # akışla gelmiş, kesinleşmemiş yanıt
        self._pending_q = None       # yanıtı beklenen takip sorusu
        self._turns = 0              # kesinleşen yanıt sayısı
        self.top = top = tk.Toplevel(parent)
        top.title(title)
        top.configure(bg=A.BG_CARD)
        top.geometry("560x580" if on_ask else "500x440")
        top.transient(parent)
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Destroy>", self._on_destroy, add="+")

        head = tk.Frame(top, bg=A.BG_CARD, padx=16, pady=12)
        head.pack(fill="x")
        tk.Label(head, text=title, font=(A.FONT, 11, "bold"), fg=A.FG,
                 bg=A.BG_CARD, anchor="w").pack(anchor="w")
        if subtitle:
            tk.Label(head, text=subtitle, font=(A.FONT, 8), fg=A.FG_DIM,
                     bg=A.BG_CARD, anchor="w").pack(anchor="w")
        self._status = tk.Label(head, text="⏳ Hazırlanıyor…",
                                font=(A.FONT, 8), fg=A.ACCENT, bg=A.BG_CARD,
                                anchor="w", justify="left", wraplength=440)
        self._status.pack(anchor="w", pady=(4, 0))

        self._choices = tk.Frame(top, bg=A.BG_CARD, padx=16)
        self._choices.pack(fill="x")

        # Butonlar önce (alttan) yerleşir: metin alanı taşsa da görünür kalır.
        btns = tk.Frame(top, bg=A.BG_CARD, padx=12, pady=8)
        btns.pack(side="bottom", fill="x")

        if on_ask is not None:
            ask = tk.Frame(top, bg=A.BG_CARD)
            ask.pack(side="bottom", fill="x", padx=16, pady=(8, 0))
            box = tk.Frame(ask, bg=A.BORDER, padx=1, pady=1)
            box.pack(side="left", fill="x", expand=True)
            self._ask_var = tk.StringVar()
            self._ask_entry = A.PlaceholderEntry(
                box, placeholder=ask_hint, textvariable=self._ask_var,
                font=(A.FONT, 10), style="Modern.TEntry")
            self._ask_entry.pack(fill="x", ipady=6, padx=2, pady=2)
            self._ask_entry.bind("<Return>", self._submit)
            _link_button(ask, "Sor ↵", self._submit).pack(side="left",
                                                          padx=(6, 0))
            self._set_ask_enabled(self._ask_ready)

        # Kaynak/bağlantı listesi: set_sources ile doldurulup yerleşir.
        self._sources = tk.Frame(top, bg=A.BG_CARD)

        body = self._body = tk.Frame(top, bg=A.BORDER, padx=1, pady=1)
        body.pack(fill="both", expand=True, padx=16, pady=(4, 0))
        self._text = tk.Text(body, wrap="word", bg=A.BG_PANEL, fg=A.FG,
                             insertbackground=A.FG, relief="flat",
                             font=(A.FONT, 10), padx=10, pady=8,
                             highlightthickness=0, height=8)
        sb = ttk.Scrollbar(body, orient="vertical", command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        self._text.pack(side="left", fill="both", expand=True)
        self._text.tag_configure("q", font=(A.FONT, 10, "bold"),
                                 foreground=A.ACCENT)
        # "qstart": geçerli takip sorusunun başı; "answer": geçerli yanıtın
        # başı. Sol yerçekimi: sona eklenen metin işaretin arkasında kalır.
        for mark in ("qstart", "answer"):
            self._text.mark_set(mark, "1.0")
            self._text.mark_gravity(mark, "left")

        self._action_btns = []
        _link_button(btns, "📋 Kopyala", self._copy).pack(side="left")
        for label, fn in self._actions:
            b = _link_button(btns, label,
                             lambda f=fn: f(self._text_value)
                             if self._text_value else None)
            b.pack(side="left")
            self._action_btns.append(b)
        _link_button(btns, "Kapat", self.close,
                     fg=A.FG_DIM).pack(side="right")

    # ── durum ───────────────────────────────────────────────────────────────
    def alive(self) -> bool:
        return _alive(self.top)

    def close(self):
        self._notify_close()
        if self.alive():
            self.top.destroy()

    def _on_destroy(self, event):
        if event.widget is self.top:
            self._notify_close()

    def _notify_close(self):
        cb, self._on_close = self._on_close, None
        if cb is not None:
            cb()

    def set_busy(self, message):
        if self.alive():
            A = _app()
            self._status.config(text=f"⏳ {message}", fg=A.ACCENT)

    def set_status(self, message, error=False):
        if self.alive():
            A = _app()
            self._status.config(text=message, fg=A.RED if error else A.ACCENT)

    def _edit(self, fn):
        self._text.configure(state="normal")
        try:
            fn(self._text)
        finally:
            self._text.configure(state="disabled")

    def _finish(self, text, status):
        A = _app()
        self._text_value = text
        self._partial = False
        self._pending_q = None
        self._turns += 1
        self._status.config(text=status or "✓ Hazır", fg=A.ACCENT_G)
        self._set_ask_enabled(self._on_ask is not None)

    def set_text(self, text, status=""):
        """Tüm içeriği değiştir (tek sonuç / ilk yanıtın kesin metni)."""
        if not self.alive():
            return

        def _do(t):
            t.delete("1.0", "end")
            t.insert("1.0", text)
            t.mark_set("qstart", "1.0")
            t.mark_set("answer", "1.0")
        self._edit(_do)
        self._turns = 0
        self._finish(text, status)

    def append_text(self, chunk):
        """Akış parçasını geçerli yanıtın sonuna ekle."""
        if not self.alive() or not chunk:
            return
        follow = self._text.yview()[1] >= 0.999
        self._edit(lambda t: t.insert("end", chunk))
        if follow:
            self._text.see("end")
        if not self._partial:
            self._partial = True
            A = _app()
            self._status.config(text="✍ Yazılıyor…", fg=A.ACCENT)

    def begin_question(self, question):
        """Kabul edilen takip sorusunu göster; yanıt bölgesini aç."""
        if not self.alive():
            return
        A = _app()
        if self._ask_var is not None:
            self._ask_var.set("")

        def _do(t):
            t.mark_set("qstart", "end-1c")
            if t.get("1.0", "end-1c").strip():
                t.insert("end", "\n\n")
            t.insert("end", f"❓ {question}\n", "q")
            t.insert("end", "\n")
            t.mark_set("answer", "end-1c")
        self._edit(_do)
        self._text.see("end")
        self._pending_q = question
        self._partial = False
        self._set_ask_enabled(False)
        self._status.config(text="⏳ Yanıt hazırlanıyor…", fg=A.ACCENT)

    def set_answer(self, text, status=""):
        """Geçerli (takip) yanıtının kesin metni: akış parçalarının yerine."""
        if not self.alive():
            return
        streamed = self._partial

        def _do(t):
            t.delete("answer", "end")
            t.insert("end", text)
        self._edit(_do)
        if not streamed:
            self._text.see("answer")
        self._finish(text, status)

    def set_error(self, message):
        if not self.alive():
            return
        A = _app()
        question = self._pending_q
        if question is not None:
            # Yanıtlanamayan soru iz bırakmaz; yeniden sormak için kutuya döner.
            self._edit(lambda t: t.delete("qstart", "end"))
            entry = self._ask_entry
            if entry is not None and not entry.get_value():
                if getattr(entry, "_showing_ph", False):
                    entry._showing_ph = False
                    entry.configure(foreground=A.FG)
                self._ask_var.set(question)
        elif self._partial:
            # Kısmi (ör. reddedilen) yanıt geçerli sayılmaz.
            self._edit(lambda t: t.delete("answer", "end"))
        self._pending_q = None
        self._partial = False
        self._status.config(text=f"⚠ {message}", fg=A.RED)
        self._set_ask_enabled(self._on_ask is not None
                              and (self._turns > 0 or self._ask_ready))

    # ── takip sorusu kutusu ─────────────────────────────────────────────────
    def _set_ask_enabled(self, enabled):
        if self._ask_entry is None:
            return
        self._ask_enabled = bool(enabled)
        try:
            self._ask_entry.state(["!disabled"] if enabled else ["disabled"])
        except Exception:
            pass

    def _submit(self, _event=None):
        if (self._ask_enabled and self._on_ask is not None and self.alive()):
            question = self._ask_entry.get_value().strip()
            if question:
                self._on_ask(question)
        return "break"

    def focus_ask(self):
        if self._ask_entry is not None and self.alive():
            try:
                self.top.after(50, self._ask_entry.focus_force)
            except Exception:
                pass

    def set_sources(self, items, on_pick, title="Kaynaklar"):
        """Tıklanabilir bağlantılar: items [(etiket, payload)] → on_pick."""
        if not self.alive():
            return
        A = _app()
        for child in self._sources.winfo_children():
            child.destroy()
        if not items:
            self._sources.pack_forget()
            return
        tk.Label(self._sources, text=title, font=(A.FONT, 7, "bold"),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
        for label, payload in list(items)[:12]:
            lbl = tk.Label(self._sources, text=label, font=(A.FONT, 8),
                           fg=A.ACCENT, bg=A.BG_CARD, anchor="w",
                           justify="left", wraplength=500, cursor="hand2")
            lbl.pack(fill="x")
            lbl.bind("<Button-1>", lambda _e, p=payload: on_pick(p))
            lbl.bind("<Enter>", lambda _e, w=lbl: w.config(bg=A.BG_HOVER))
            lbl.bind("<Leave>", lambda _e, w=lbl: w.config(bg=A.BG_CARD))
        self._sources.pack(side="bottom", fill="x", padx=16, pady=(6, 0),
                           before=self._body)

    def set_choices(self, items, on_pick, hint="Seçince giriş kutusuna "
                                               "yerleştirilir:"):
        """Seçilebilir öneriler (yanıt önerisi). Seçim pencereyi kapatır."""
        if not self.alive():
            return
        A = _app()
        for child in self._choices.winfo_children():
            child.destroy()
        tk.Label(self._choices, text=hint, font=(A.FONT, 8), fg=A.FG_DIM,
                 bg=A.BG_CARD, anchor="w").pack(anchor="w", pady=(0, 4))
        for item in items:
            card = tk.Label(self._choices, text=item, font=(A.FONT, 10),
                            fg=A.FG, bg=A.BG_HOVER, anchor="w",
                            justify="left", wraplength=420, padx=10, pady=6,
                            cursor="hand2")
            card.pack(fill="x", pady=2)

            def _pick(_e, s=item):
                on_pick(s)
                self.close()
            card.bind("<Button-1>", _pick)
        self.set_text("\n".join(items), status="✓ Bir öneri seçin")

    def _copy(self):
        if not self.alive():
            return
        # Takip soruları olduysa tüm konuşma, yoksa yalnız sonuç kopyalanır.
        value = (self._text.get("1.0", "end-1c") if self._turns > 1
                 else self._text_value)
        if value:
            self.top.clipboard_clear()
            self.top.clipboard_append(value)
            self._status.config(text="📋 Panoya kopyalandı")


class SemanticSearchWindow:
    """Anlamla arama: sorgu → (MainWindow) → sonuç listesi."""

    def __init__(self, parent, subtitle, on_search, on_open):
        A = _app()
        self._payloads = []
        self.top = top = tk.Toplevel(parent)
        top.title("Anlamsal Arama")
        top.configure(bg=A.BG_CARD)
        top.geometry("560x460")
        top.transient(parent)

        head = tk.Frame(top, bg=A.BG_CARD, padx=16, pady=12)
        head.pack(fill="x")
        tk.Label(head, text="🧠  Anlamla Ara", font=(A.FONT, 11, "bold"),
                 fg=A.FG, bg=A.BG_CARD).pack(anchor="w")
        tk.Label(head, text=subtitle, font=(A.FONT, 8), fg=A.FG_DIM,
                 bg=A.BG_CARD).pack(anchor="w")
        tk.Label(head, text="Örn: \"geçen ay konuşulan fiyat\", "
                            "\"buluşma yeri\"", font=(A.FONT, 8),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")

        self._query = tk.StringVar()
        sb = tk.Frame(head, bg=A.BORDER, padx=1, pady=1)
        sb.pack(fill="x", pady=(8, 0))
        entry = A.PlaceholderEntry(sb, placeholder="Ne arıyorsunuz?",
                                   textvariable=self._query,
                                   font=(A.FONT, 10), style="Modern.TEntry")
        entry.pack(fill="x", ipady=7, padx=2, pady=2)
        self._status = tk.Label(head, text="", font=(A.FONT, 8),
                                fg=A.ACCENT, bg=A.BG_CARD, anchor="w",
                                justify="left", wraplength=520)
        self._status.pack(anchor="w", pady=(6, 0))

        frame = tk.Frame(top, bg=A.BG_CARD)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._list = tk.Listbox(frame, bg=A.BG_PANEL, fg=A.FG,
                                selectbackground=A.SEL_BG,
                                selectforeground=A.SEL_FG, font=(A.FONT, 9),
                                relief="flat", highlightthickness=0,
                                activestyle="none")
        self._list.pack(fill="both", expand=True)

        def _search(_e=None):
            q = self._query.get().strip()
            if len(q) >= 2:
                on_search(q)

        def _open(_e=None):
            sel = self._list.curselection()
            if sel and sel[0] < len(self._payloads):
                on_open(self._payloads[sel[0]])

        entry.bind("<Return>", _search)
        self._list.bind("<Double-1>", _open)
        self._list.bind("<Return>", _open)
        try:
            top.after(50, entry.focus_force)
        except Exception:
            pass

    def alive(self) -> bool:
        return _alive(self.top)

    def close(self):
        if self.alive():
            self.top.destroy()

    def set_status(self, message, error=False):
        if self.alive():
            A = _app()
            self._status.config(text=message, fg=A.RED if error else A.ACCENT)

    def set_results(self, results):
        """results: [(satır etiketi, payload)]"""
        if not self.alive():
            return
        self._list.delete(0, "end")
        self._payloads = []
        for label, payload in results:
            self._list.insert("end", label)
            self._payloads.append(payload)


_KIND_LABELS = (("event", "📅 Etkinlik"), ("task", "✅ Görev"))


def format_action_line(item) -> str:
    """Panoya kopyalama için tek satırlık özet (saf; test edilebilir)."""
    kind = dict(_KIND_LABELS).get(item.get("kind"), "✅ Görev")
    when = " ".join(p for p in (item.get("date", ""), item.get("time", ""))
                    if p)
    if when and item.get("end_time"):
        when += f"–{item['end_time']}"
    parts = [f"{kind}: {item.get('title', '')}"]
    if when:
        parts.append(when)
    if item.get("location"):
        parts.append(f"@ {item['location']}")
    return " · ".join(parts)


class ActionsWindow:
    """Sohbetten çıkarılan görev/etkinlikleri gözden geçir ve dışa aktar.

    Her öğe düzenlenebilir (tür, başlık, tarih, saat, bitiş, yer) ve
    seçilebilir. `on_export(öğeler)` / `on_remind(öğeler)` MainWindow'da
    doğrulayıp kaydeder; dönüş (başarılı mı, mesaj) ya da None (iptal).
    """

    def __init__(self, parent, title, subtitle, on_export, on_remind, *,
                 on_close=None):
        A = _app()
        self._on_export = on_export
        self._on_remind = on_remind
        self._on_close = on_close
        self._rows = []
        self.top = top = tk.Toplevel(parent)
        top.title("Görevler ve Etkinlikler")
        top.configure(bg=A.BG_CARD)
        top.geometry("680x600")
        top.transient(parent)
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Destroy>", self._on_destroy, add="+")

        head = tk.Frame(top, bg=A.BG_CARD, padx=16, pady=12)
        head.pack(fill="x")
        tk.Label(head, text=title, font=(A.FONT, 11, "bold"), fg=A.FG,
                 bg=A.BG_CARD, anchor="w").pack(anchor="w")
        if subtitle:
            tk.Label(head, text=subtitle, font=(A.FONT, 8), fg=A.FG_DIM,
                     bg=A.BG_CARD, anchor="w").pack(anchor="w")
        tk.Label(head, text="Tarih ve saatler sohbetten tahmin edildi; "
                            "kaydetmeden önce kontrol edin (YYYY-AA-GG, "
                            "SS:DD).",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD, anchor="w",
                 justify="left", wraplength=640).pack(anchor="w")
        self._status = tk.Label(head, text="⏳ Hazırlanıyor…",
                                font=(A.FONT, 8), fg=A.ACCENT, bg=A.BG_CARD,
                                anchor="w", justify="left", wraplength=640)
        self._status.pack(anchor="w", pady=(4, 0))

        btns = tk.Frame(top, bg=A.BG_CARD, padx=12, pady=8)
        btns.pack(side="bottom", fill="x")
        self._btns = [
            _link_button(btns, "📅 .ics olarak kaydet",
                         lambda: self._run(self._on_export)),
            _link_button(btns, "⏰ Hatırlatıcı kur",
                         lambda: self._run(self._on_remind)),
            _link_button(btns, "📋 Kopyala", self._copy),
        ]
        for b in self._btns:
            b.pack(side="left")
        _link_button(btns, "Kapat", self.close,
                     fg=A.FG_DIM).pack(side="right")

        wrap = tk.Frame(top, bg=A.BORDER, padx=1, pady=1)
        wrap.pack(fill="both", expand=True, padx=16, pady=(4, 0))
        self._canvas = tk.Canvas(wrap, bg=A.BG_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical",
                           command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._list = tk.Frame(self._canvas, bg=A.BG_PANEL)
        self._win_id = self._canvas.create_window((0, 0), window=self._list,
                                                  anchor="nw")
        self._list.bind("<Configure>", lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win_id, width=e.width))
        self._bind_wheel(self._canvas)
        self._bind_wheel(self._list)

    # ── yaşam döngüsü ───────────────────────────────────────────────────────
    def alive(self) -> bool:
        return _alive(self.top)

    def close(self):
        self._notify_close()
        if self.alive():
            self.top.destroy()

    def _on_destroy(self, event):
        if event.widget is self.top:
            self._notify_close()

    def _notify_close(self):
        cb, self._on_close = self._on_close, None
        if cb is not None:
            cb()

    def _bind_wheel(self, widget):
        """Tekerlek listeyi kaydırır (alt widget'lar dahil; açılır kutunun
        değeri tekerlekle yanlışlıkla değişmez)."""
        def _wheel(event):
            step = -1 if (getattr(event, "num", 0) == 4
                          or getattr(event, "delta", 0) > 0) else 1
            self._canvas.yview_scroll(step, "units")
            return "break"
        stack = [widget]
        while stack:
            w = stack.pop()
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                w.bind(seq, _wheel)
            stack.extend(w.winfo_children())

    # ── durum ───────────────────────────────────────────────────────────────
    def set_busy(self, message):
        if self.alive():
            A = _app()
            self._status.config(text=f"⏳ {message}", fg=A.ACCENT)

    def set_status(self, message, ok=True):
        if self.alive():
            A = _app()
            self._status.config(text=message,
                                fg=A.ACCENT_G if ok else A.RED)

    def set_error(self, message):
        self.set_status(f"⚠ {message}", ok=False)

    def set_items(self, items):
        if not self.alive():
            return
        for child in self._list.winfo_children():
            child.destroy()
        self._rows = []
        for item in items:
            self._add_row(item)
        if items:
            self.set_status(f"✓ {len(items)} öğe bulundu — seçip "
                            "kaydedin ya da hatırlatıcı kurun.")
        else:
            self.set_status("Bu sohbette görev ya da etkinlik bulunamadı.")

    def _add_row(self, item):
        A = _app()
        card = tk.Frame(self._list, bg=A.BG_CARD, padx=10, pady=8)
        card.pack(fill="x", padx=6, pady=4)
        vars_ = {k: tk.StringVar(value=item.get(k, ""))
                 for k in ("title", "date", "time", "end_time", "location")}
        checked = tk.BooleanVar(value=True)
        kind = tk.StringVar(value=dict(_KIND_LABELS).get(item.get("kind"),
                                                         "✅ Görev"))
        line1 = tk.Frame(card, bg=A.BG_CARD)
        line1.pack(fill="x")
        tk.Checkbutton(line1, variable=checked, bg=A.BG_CARD,
                       activebackground=A.BG_CARD,
                       selectcolor=A.BG_HOVER).pack(side="left")
        ttk.Combobox(line1, textvariable=kind, state="readonly", width=10,
                     values=[label for _k, label in _KIND_LABELS]
                     ).pack(side="left", padx=(0, 6))
        ttk.Entry(line1, textvariable=vars_["title"],
                  style="Modern.TEntry").pack(side="left", fill="x",
                                              expand=True)
        line2 = tk.Frame(card, bg=A.BG_CARD)
        line2.pack(fill="x", pady=(6, 0))
        for label, key, width in (("Tarih", "date", 11), ("Saat", "time", 6),
                                  ("Bitiş", "end_time", 6)):
            tk.Label(line2, text=label, font=(A.FONT, 8), fg=A.FG_DIM,
                     bg=A.BG_CARD).pack(side="left", padx=(0, 3))
            ttk.Entry(line2, textvariable=vars_[key], width=width,
                      style="Modern.TEntry").pack(side="left", padx=(0, 8))
        tk.Label(line2, text="Yer", font=(A.FONT, 8), fg=A.FG_DIM,
                 bg=A.BG_CARD).pack(side="left", padx=(0, 3))
        ttk.Entry(line2, textvariable=vars_["location"],
                  style="Modern.TEntry").pack(side="left", fill="x",
                                              expand=True)
        extra = " · ".join(p for p in (
            item.get("notes", ""),
            f"“{item['quote']}”" if item.get("quote") else "") if p)
        if extra:
            tk.Label(card, text=extra, font=(A.FONT, 8), fg=A.FG_DIM,
                     bg=A.BG_CARD, anchor="w", justify="left",
                     wraplength=600).pack(fill="x", pady=(6, 0))
        self._bind_wheel(card)
        self._rows.append((checked, kind, vars_, item))

    def selected_items(self) -> list:
        kinds = {label: key for key, label in _KIND_LABELS}
        out = []
        for checked, kind, vars_, item in self._rows:
            if not checked.get():
                continue
            out.append({
                "kind": kinds.get(kind.get(), "task"),
                "title": vars_["title"].get().strip(),
                "date": vars_["date"].get().strip(),
                "time": vars_["time"].get().strip(),
                "end_time": vars_["end_time"].get().strip(),
                "location": vars_["location"].get().strip(),
                "notes": item.get("notes", ""),
                "quote": item.get("quote", ""),
            })
        return out

    def _run(self, callback):
        if not self.alive():
            return
        items = self.selected_items()
        if not items:
            self.set_status("Önce en az bir öğe seçin.", ok=False)
            return
        result = callback(items)
        if result is not None and self.alive():
            ok, message = result
            self.set_status(message, ok=ok)

    def _copy(self):
        items = self.selected_items()
        if not items or not self.alive():
            return
        self.top.clipboard_clear()
        self.top.clipboard_append(
            "\n".join(format_action_line(i) for i in items))
        self.set_status("📋 Panoya kopyalandı")


class PendingQuestionsWindow:
    """Yanıt bekleyen sorular: sohbet başına bir kart.

    Girişler MainWindow'da biçimlenir: {"jid", "key", "label", "age",
    "text", "count", "encrypted"}. `on_open(giriş)`, `on_dismiss(giriş)`;
    `on_remind(giriş)` → (başarılı mı, mesaj) | None. Yok sayılan kart
    listeden kalkar.
    """

    def __init__(self, parent, on_open, on_remind, on_dismiss):
        A = _app()
        self._on_open = on_open
        self._on_remind = on_remind
        self._on_dismiss = on_dismiss
        self._cards = {}
        self.top = top = tk.Toplevel(parent)
        top.title("Yanıt Bekleyen Sorular")
        top.configure(bg=A.BG_CARD)
        top.geometry("580x520")
        top.transient(parent)

        head = tk.Frame(top, bg=A.BG_CARD, padx=16, pady=12)
        head.pack(fill="x")
        tk.Label(head, text="❓  Yanıt Bekleyen Sorular",
                 font=(A.FONT, 11, "bold"), fg=A.FG, bg=A.BG_CARD,
                 anchor="w").pack(anchor="w")
        tk.Label(head, text="Son mesajınızdan sonra size sorulan ve henüz "
                            "yanıtlamadığınız sorular. Tespit bilgisayarınızda "
                            "yapılır; hiçbir içerik dışarı gönderilmez.",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD, anchor="w",
                 justify="left", wraplength=540).pack(anchor="w")
        self._status = tk.Label(head, text="⏳ Taranıyor…", font=(A.FONT, 8),
                                fg=A.ACCENT, bg=A.BG_CARD, anchor="w",
                                justify="left", wraplength=540)
        self._status.pack(anchor="w", pady=(4, 0))

        btns = tk.Frame(top, bg=A.BG_CARD, padx=12, pady=8)
        btns.pack(side="bottom", fill="x")
        _link_button(btns, "Kapat", self.close,
                     fg=A.FG_DIM).pack(side="right")

        wrap = tk.Frame(top, bg=A.BORDER, padx=1, pady=1)
        wrap.pack(fill="both", expand=True, padx=16, pady=(4, 0))
        self._canvas = tk.Canvas(wrap, bg=A.BG_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical",
                           command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._list = tk.Frame(self._canvas, bg=A.BG_PANEL)
        self._win_id = self._canvas.create_window((0, 0), window=self._list,
                                                  anchor="nw")
        self._list.bind("<Configure>", lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win_id, width=e.width))
        self._bind_wheel(self._canvas)
        self._bind_wheel(self._list)

    def alive(self) -> bool:
        return _alive(self.top)

    def close(self):
        if self.alive():
            self.top.destroy()

    def _bind_wheel(self, widget):
        def _wheel(event):
            step = -1 if (getattr(event, "num", 0) == 4
                          or getattr(event, "delta", 0) > 0) else 1
            self._canvas.yview_scroll(step, "units")
            return "break"
        stack = [widget]
        while stack:
            w = stack.pop()
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                w.bind(seq, _wheel)
            stack.extend(w.winfo_children())

    def set_status(self, message, ok=True):
        if self.alive():
            A = _app()
            self._status.config(text=message,
                                fg=A.ACCENT_G if ok else A.RED)

    def set_error(self, message):
        self.set_status(f"⚠ {message}", ok=False)

    def set_entries(self, entries):
        if not self.alive():
            return
        for child in self._list.winfo_children():
            child.destroy()
        self._cards = {}
        for entry in entries:
            self._add_card(entry)
        self._show_count()

    def _show_count(self):
        n = len(self._cards)
        self.set_status(f"{n} sohbette yanıt bekleyen soru var." if n else
                        "Yanıt bekleyen soru yok. 🎉")

    def _add_card(self, entry):
        A = _app()
        card = tk.Frame(self._list, bg=A.BG_CARD, padx=10, pady=8)
        card.pack(fill="x", padx=6, pady=4)
        meta = [entry["label"], entry["age"]]
        if entry.get("count", 1) > 1:
            meta.append(f"{entry['count']} soru")
        tk.Label(card, text=("🔒 " if entry.get("encrypted") else "👤 ")
                 + "  ·  ".join(meta), font=(A.FONT, 9, "bold"),
                 fg=A.ACCENT, bg=A.BG_CARD, anchor="w").pack(fill="x")
        tk.Label(card, text=entry["text"], font=(A.FONT, 10), fg=A.FG,
                 bg=A.BG_CARD, anchor="w", justify="left",
                 wraplength=500).pack(fill="x", pady=(2, 4))
        row = tk.Frame(card, bg=A.BG_CARD)
        row.pack(fill="x")
        _link_button(row, "💬 Sohbete git",
                     lambda: self._on_open(entry), bg=A.BG_CARD
                     ).pack(side="left")
        _link_button(row, "⏰ Yarın 09:00 hatırlat",
                     lambda: self._remind(entry), bg=A.BG_CARD
                     ).pack(side="left")
        _link_button(row, "✓ Yok say", lambda: self._dismiss(entry),
                     fg=A.FG_DIM, bg=A.BG_CARD).pack(side="right")
        self._bind_wheel(card)
        self._cards[entry["key"]] = card

    def _remind(self, entry):
        result = self._on_remind(entry)
        if result is not None and self.alive():
            ok, message = result
            self.set_status(message, ok=ok)

    def _dismiss(self, entry):
        self._on_dismiss(entry)
        card = self._cards.pop(entry["key"], None)
        if card is not None and self.alive():
            card.destroy()
            self._show_count()


class _ScrollList:
    """Kaydırılabilir dikey liste (Canvas + iç Frame); tekerlek alt
    widget'larda da çalışır."""

    def __init__(self, parent, bg):
        A = _app()
        wrap = tk.Frame(parent, bg=A.BORDER, padx=1, pady=1)
        self.wrap = wrap
        self.canvas = tk.Canvas(wrap, bg=bg, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win_id = self.canvas.create_window((0, 0), window=self.inner,
                                                 anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self._win_id, width=e.width))
        self.bind_wheel(self.canvas)
        self.bind_wheel(self.inner)

    def bind_wheel(self, widget):
        def _wheel(event):
            step = -1 if (getattr(event, "num", 0) == 4
                          or getattr(event, "delta", 0) > 0) else 1
            self.canvas.yview_scroll(step, "units")
            return "break"
        stack = [widget]
        while stack:
            w = stack.pop()
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                w.bind(seq, _wheel)
            stack.extend(w.winfo_children())

    def scroll_end(self):
        try:
            self.canvas.update_idletasks()
            self.canvas.yview_moveto(1.0)
        except Exception:
            pass

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()


class _Card:
    """Onay kartı: düğmeler bir kez çalışır, sonra sonuç satırına dönüşür."""

    def __init__(self, frame, buttons_row, result_label):
        self.frame = frame
        self._row = buttons_row
        self._result = result_label
        self.done = False

    def resolve(self, message, ok=True):
        if not _alive(self.frame):
            return
        A = _app()
        self.done = True
        for child in self._row.winfo_children():
            child.destroy()
        self._result.config(text=message, fg=A.ACCENT_G if ok else A.RED)


class AssistantWindow:
    """✨ Asistan: doğal dil komutları ve sohbet (ajan) penceresi.

    Kullanıcı metni `on_submit(metin)` ile MainWindow'a gider; yanıtlar
    `add_reply`, onay isteyen eylemler `add_card`, belirsiz hedefler
    `add_choices` ile gelir. Meşgulken yeni gönderim kabul edilmez.
    `on_speak(metin)` verilirse yanıtların yanında 🔊 çıkar.
    """

    def __init__(self, parent, subtitle, on_submit, *, on_clear=None,
                 on_close=None, on_speak=None, examples=()):
        A = _app()
        self._on_submit = on_submit
        self._on_close = on_close
        self._on_speak = on_speak
        self._busy = False
        self.top = top = tk.Toplevel(parent)
        top.title("Asistan")
        top.configure(bg=A.BG_CARD)
        top.geometry("560x660")
        top.transient(parent)
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Destroy>", self._on_destroy, add="+")

        head = tk.Frame(top, bg=A.BG_CARD, padx=16, pady=12)
        head.pack(fill="x")
        title_row = tk.Frame(head, bg=A.BG_CARD)
        title_row.pack(fill="x")
        tk.Label(title_row, text="✨  Asistan", font=(A.FONT, 12, "bold"),
                 fg=A.FG, bg=A.BG_CARD).pack(side="left")
        if on_clear is not None:
            _link_button(title_row, "🗑 Temizle", on_clear,
                         fg=A.FG_DIM).pack(side="right")
        self._subtitle = tk.Label(head, text=subtitle, font=(A.FONT, 8),
                                  fg=A.FG_DIM, bg=A.BG_CARD, anchor="w",
                                  justify="left", wraplength=520)
        self._subtitle.pack(anchor="w", fill="x")

        bottom = tk.Frame(top, bg=A.BG_CARD, padx=16, pady=10)
        bottom.pack(side="bottom", fill="x")
        self._status = tk.Label(bottom, text="", font=(A.FONT, 8),
                                fg=A.ACCENT, bg=A.BG_CARD, anchor="w")
        self._status.pack(fill="x")
        row = tk.Frame(bottom, bg=A.BORDER, padx=1, pady=1)
        row.pack(fill="x", pady=(4, 0))
        self._var = tk.StringVar()
        self._entry = A.PlaceholderEntry(
            row, placeholder="Bir komut yazın ya da soru sorun…",
            textvariable=self._var, font=(A.FONT, 10),
            style="Modern.TEntry")
        self._entry.pack(side="left", fill="x", expand=True, ipady=7,
                         padx=2, pady=2)
        self._send_btn = _link_button(row, "➤", self._submit,
                                      bg=A.BG_CARD)
        self._send_btn.pack(side="right")
        self._entry.bind("<Return>", lambda _e: self._submit() or "break")

        self._list = _ScrollList(top, A.BG_PANEL)
        self._list.wrap.pack(fill="both", expand=True, padx=16)
        self._examples = tuple(examples)
        self._show_examples()
        self.focus()

    # ── yaşam döngüsü ───────────────────────────────────────────────────────
    def alive(self) -> bool:
        return _alive(self.top)

    def close(self):
        self._notify_close()
        if self.alive():
            self.top.destroy()

    def _on_destroy(self, event):
        if event.widget is self.top:
            self._notify_close()

    def _notify_close(self):
        cb, self._on_close = self._on_close, None
        if cb is not None:
            cb()

    def focus(self):
        try:
            self.top.lift()
            self._entry.focus_force()
        except Exception:
            pass

    def set_subtitle(self, text):
        if self.alive():
            self._subtitle.config(text=text)

    # ── giriş ───────────────────────────────────────────────────────────────
    def _text(self) -> str:
        get = getattr(self._entry, "get_value", None)
        return (get() if get else self._var.get()).strip()

    def _submit(self):
        if not self.alive() or self._busy:
            return
        text = self._text()
        if not text:
            return
        self._var.set("")
        self._on_submit(text)

    def submit_text(self, text):
        """Örnek komut ya da dışarıdan verilen metni gönder (giriş kutusunu
        atlar: yer tutucu gösterilirken değişkene yazmak metni boş sayar)."""
        text = (text or "").strip()
        if self.alive() and not self._busy and text:
            self._on_submit(text)

    def set_busy(self, message=None):
        if not self.alive():
            return
        A = _app()
        self._busy = bool(message)
        self._status.config(text=f"⏳ {message}" if message else "",
                            fg=A.ACCENT)
        try:
            self._entry.state(["disabled"] if message else ["!disabled"])
            if not message:
                self._entry.focus_set()
        except Exception:
            pass

    # ── mesajlar ────────────────────────────────────────────────────────────
    def _show_examples(self):
        if not self._examples:
            return
        A = _app()
        box = tk.Frame(self._list.inner, bg=A.BG_PANEL, padx=10, pady=10)
        box.pack(fill="x")
        tk.Label(box, text="Örnekler — tıklayın ya da kendiniz yazın:",
                 font=(A.FONT, 8, "bold"), fg=A.FG_DIM, bg=A.BG_PANEL,
                 anchor="w").pack(fill="x")
        for ex in self._examples:
            _link_button(box, f"› {ex}", lambda e=ex: self.submit_text(e),
                         bg=A.BG_PANEL).pack(anchor="w")
        self._examples_box = box
        self._list.bind_wheel(box)

    def _drop_examples(self):
        box = getattr(self, "_examples_box", None)
        if box is not None:
            box.destroy()
            self._examples_box = None

    def _bubble(self, text, *, mine, fg=None):
        A = _app()
        self._drop_examples()
        outer = tk.Frame(self._list.inner, bg=A.BG_PANEL)
        outer.pack(fill="x", padx=8, pady=4)
        bg = A.BG_ME if mine else A.BG_THEM
        bubble = tk.Frame(outer, bg=bg, padx=12, pady=8)
        bubble.pack(side="right" if mine else "left",
                    padx=(60, 0) if mine else (0, 60))
        tk.Label(bubble, text=text, font=(A.FONT, 10),
                 fg=fg or (A.FG_ME if mine else A.FG), bg=bg,
                 wraplength=380, justify="left", anchor="w").pack(anchor="w")
        return outer, bubble

    def add_user(self, text):
        if self.alive():
            self._bubble(text, mine=True)
            self._finish()

    def add_reply(self, text):
        if not self.alive():
            return
        A = _app()
        _outer, bubble = self._bubble(text, mine=False)
        if self._on_speak is not None:
            _link_button(bubble, "🔊", lambda t=text: self._on_speak(t),
                         bg=A.BG_THEM).pack(anchor="e")
        self._finish()

    def add_note(self, text, error=False):
        if not self.alive():
            return
        A = _app()
        self._drop_examples()
        tk.Label(self._list.inner, text=text, font=(A.FONT, 8),
                 fg=A.RED if error else A.FG_DIM, bg=A.BG_PANEL,
                 wraplength=480, justify="left", anchor="w").pack(
            fill="x", padx=12, pady=(2, 4))
        self._finish()

    def add_card(self, title, detail, buttons):
        """buttons: [(etiket, fn)] — fn() → (mesaj, başarılı) | None."""
        if not self.alive():
            return None
        A = _app()
        self._drop_examples()
        frame = tk.Frame(self._list.inner, bg=A.BORDER, padx=1, pady=1)
        frame.pack(fill="x", padx=8, pady=6)
        inner = tk.Frame(frame, bg=A.BG_CARD, padx=12, pady=10)
        inner.pack(fill="x")
        tk.Label(inner, text=title, font=(A.FONT, 10, "bold"), fg=A.FG,
                 bg=A.BG_CARD, anchor="w").pack(fill="x")
        tk.Label(inner, text=detail, font=(A.FONT, 9), fg=A.FG,
                 bg=A.BG_CARD, wraplength=460, justify="left",
                 anchor="w").pack(fill="x", pady=(4, 6))
        row = tk.Frame(inner, bg=A.BG_CARD)
        row.pack(fill="x")
        result = tk.Label(inner, text="", font=(A.FONT, 8), fg=A.ACCENT,
                          bg=A.BG_CARD, anchor="w", justify="left",
                          wraplength=460)
        result.pack(fill="x")
        card = _Card(frame, row, result)

        def _run(fn):
            if card.done:
                return
            card.done = True            # çift tıklama iki kez çalıştırmaz
            try:
                outcome = fn()
            except Exception as e:
                card.resolve(f"⚠ {e}", ok=False)
                raise
            card.resolve(*(outcome or ("✓ Tamam", True)))
        for label, fn in buttons:
            _link_button(row, label, lambda f=fn: _run(f),
                         bg=A.BG_CARD).pack(side="left")
        self._list.bind_wheel(frame)
        self._finish()
        return card

    def add_choices(self, prompt, options, on_pick):
        """Belirsiz hedef: options [(etiket, değer)] → on_pick(değer)."""
        buttons = [(f"› {label}", lambda v=value: on_pick(v))
                   for label, value in options]
        buttons.append(("✗ Vazgeç", lambda: ("Vazgeçildi.", False)))
        return self.add_card("❔ " + prompt, "Hangisini kastettiniz?",
                             buttons)

    def clear(self):
        if self.alive():
            self._list.clear()
            self._show_examples()

    def _finish(self):
        self._list.bind_wheel(self._list.inner)
        self._list.scroll_end()


class DraftsWindow:
    """Yanıt taslakları: uzaktayken hazırlananlar ve harici (MCP) taslaklar.

    Girişler MainWindow'da biçimlenir: {"jid", "label", "source", "count",
    "last", "options", "state" (ready|pending|blocked|error), "error"}.
    Geri çağrılar girişle çağrılır: on_use(giriş, metin) — metni giriş
    kutusuna koyar (asla göndermez), on_regen, on_consent, on_dismiss.
    """

    def __init__(self, parent, on_use, on_regen, on_consent, on_dismiss):
        A = _app()
        self._cb = {"use": on_use, "regen": on_regen, "consent": on_consent,
                    "dismiss": on_dismiss}
        self.top = top = tk.Toplevel(parent)
        top.title("Yanıt Taslakları")
        top.configure(bg=A.BG_CARD)
        top.geometry("600x560")
        top.transient(parent)
        head = tk.Frame(top, bg=A.BG_CARD, padx=16, pady=12)
        head.pack(fill="x")
        tk.Label(head, text="📝  Yanıt Taslakları", font=(A.FONT, 11, "bold"),
                 fg=A.FG, bg=A.BG_CARD, anchor="w").pack(anchor="w")
        tk.Label(head, text="Taslaklar asla kendiliğinden gönderilmez: "
                            "“Kullan” metni sohbetin giriş kutusuna koyar, "
                            "düzenleyip siz gönderirsiniz.",
                 font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD, anchor="w",
                 justify="left", wraplength=560).pack(anchor="w")
        self._status = tk.Label(head, text="", font=(A.FONT, 8),
                                fg=A.ACCENT, bg=A.BG_CARD, anchor="w")
        self._status.pack(anchor="w", pady=(4, 0))
        btns = tk.Frame(top, bg=A.BG_CARD, padx=12, pady=8)
        btns.pack(side="bottom", fill="x")
        _link_button(btns, "Kapat", self.close, fg=A.FG_DIM).pack(
            side="right")
        self._list = _ScrollList(top, A.BG_PANEL)
        self._list.wrap.pack(fill="both", expand=True, padx=16, pady=(4, 0))

    def alive(self) -> bool:
        return _alive(self.top)

    def close(self):
        if self.alive():
            self.top.destroy()

    def set_entries(self, entries):
        if not self.alive():
            return
        self._list.clear()
        for entry in entries:
            self._add_card(entry)
        n = len(entries)
        self._status.config(text=f"{n} sohbet için taslak var." if n else
                            "Bekleyen taslak yok.")

    def _add_card(self, entry):
        A = _app()
        cb = self._cb
        card = tk.Frame(self._list.inner, bg=A.BG_CARD, padx=10, pady=8)
        card.pack(fill="x", padx=6, pady=4)
        meta = [entry["label"]]
        if entry.get("count"):
            meta.append(f"{entry['count']} yeni mesaj")
        if entry.get("source"):
            meta.append(entry["source"])
        tk.Label(card, text="👤 " + "  ·  ".join(meta),
                 font=(A.FONT, 9, "bold"), fg=A.ACCENT, bg=A.BG_CARD,
                 anchor="w").pack(fill="x")
        if entry.get("last"):
            tk.Label(card, text=f"“{entry['last']}”", font=(A.FONT, 9),
                     fg=A.FG_DIM, bg=A.BG_CARD, anchor="w", justify="left",
                     wraplength=520).pack(fill="x", pady=(2, 4))
        state = entry.get("state", "ready")
        if state == "pending":
            tk.Label(card, text="⏳ Taslak hazırlanıyor…", font=(A.FONT, 9),
                     fg=A.ACCENT, bg=A.BG_CARD, anchor="w").pack(fill="x")
        elif state == "blocked":
            tk.Label(card, text="🔒 Şifreli sohbet: taslak için içerik "
                                "buluta (Claude) gönderilmeli.",
                     font=(A.FONT, 9), fg=A.FG_DIM, bg=A.BG_CARD,
                     anchor="w", justify="left", wraplength=520).pack(
                fill="x")
        elif state == "error":
            tk.Label(card, text=f"⚠ {entry.get('error', '')}",
                     font=(A.FONT, 9), fg=A.RED, bg=A.BG_CARD, anchor="w",
                     justify="left", wraplength=520).pack(fill="x")
        for text in entry.get("options", ()):
            row = tk.Frame(card, bg=A.BG_HOVER, padx=8, pady=4)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=text, font=(A.FONT, 10), fg=A.FG,
                     bg=A.BG_HOVER, anchor="w", justify="left",
                     wraplength=440).pack(side="left", fill="x", expand=True)
            _link_button(row, "➡ Kullan",
                         lambda t=text: cb["use"](entry, t),
                         bg=A.BG_HOVER).pack(side="right")
        actions = tk.Frame(card, bg=A.BG_CARD)
        actions.pack(fill="x", pady=(4, 0))
        if state == "blocked":
            _link_button(actions, "☁ Onayla ve hazırla",
                         lambda: cb["consent"](entry),
                         bg=A.BG_CARD).pack(side="left")
        elif state in ("ready", "error") and entry.get("regen", True):
            _link_button(actions, "🔄 Yeniden üret",
                         lambda: cb["regen"](entry),
                         bg=A.BG_CARD).pack(side="left")
        _link_button(actions, "✓ Kaldır", lambda: cb["dismiss"](entry),
                     fg=A.FG_DIM, bg=A.BG_CARD).pack(side="right")
        self._list.bind_wheel(card)


_PROVIDER_CHOICES = (
    ("off", "Kapalı"),
    ("ollama", "🖥 Yerel — Ollama (önerilen; veri bilgisayarda kalır)"),
    ("claude", "☁ Claude — bulut (Anthropic API)"),
)
_CLAUDE_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")


def show_settings(parent, settings, has_key, whisper_models, on_save,
                  on_test, *, tts_engines=("auto",), mcp_command=""):
    """AI ayarları penceresi: sekmeler (Model, Claude, Özellikler, Ses, MCP);
    durum satırı ve düğmeler sabit altta. Pencere içeriğe göre boyutlanır
    (en uzun sekme küçük ekranlara da sığacak kadar kısa tutulur).

    `on_save(values, api_key)`: api_key None → kayıtlı anahtar korunur,
    "" → silinir. `on_test(values, api_key, report)`: bağlantı testi;
    `report(mesaj, ok)` sonucu GUI thread'inde gösterir. `mcp_command`:
    MCP sunucusunu kaydetme komutu (kopyalanabilir).
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("AI Ayarları")
    dlg.configure(bg=A.BG_CARD)
    dlg.minsize(560, 0)
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    head = tk.Frame(dlg, bg=A.BG_CARD, padx=18, pady=12)
    head.pack(fill="x")
    tk.Label(head, text="✨ AI Asistanı", font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(anchor="w")
    tk.Label(head, text="Şifreli sohbetler varsayılan olarak yalnız yerel "
                        "modelle işlenir. Ses→metin ve anlamsal arama her "
                        "zaman yereldir.",
             font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD, justify="left",
             wraplength=510).pack(anchor="w", pady=(2, 0))

    btns = tk.Frame(dlg, bg=A.BG_CARD, padx=18, pady=10)
    btns.pack(fill="x", side="bottom")
    status = tk.Label(dlg, text="", font=(A.FONT, 8), fg=A.ACCENT,
                      bg=A.BG_CARD, justify="left", wraplength=510,
                      anchor="w")
    status.pack(fill="x", side="bottom", padx=18)

    tabs = ttk.Notebook(dlg)
    tabs.pack(fill="both", expand=True, padx=12)

    def _page(title):
        page = tk.Frame(tabs, bg=A.BG_CARD, padx=14, pady=8)
        tabs.add(page, text=title)
        return page

    def _section(page, title):
        tk.Label(page, text=title, font=(A.FONT, 7, "bold"), fg=A.FG_DIM,
                 bg=A.BG_CARD).pack(anchor="w", pady=(8, 4))

    def _row(page, label, var, show=None, values=None):
        f = tk.Frame(page, bg=A.BG_CARD)
        f.pack(fill="x", pady=2)
        tk.Label(f, text=label, font=(A.FONT, 9), fg=A.FG, bg=A.BG_CARD,
                 width=16, anchor="w").pack(side="left")
        if values is not None:
            w = ttk.Combobox(f, textvariable=var, values=list(values))
        else:
            w = ttk.Entry(f, textvariable=var, show=show or "",
                          style="Modern.TEntry")
        w.pack(side="left", fill="x", expand=True, ipady=2)
        return w

    def _hint(page, text):
        tk.Label(page, text=text, font=(A.FONT, 8), fg=A.FG_DIM,
                 bg=A.BG_CARD, justify="left", wraplength=490,
                 anchor="w").pack(anchor="w", fill="x")

    chk_kw = dict(bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                  activebackground=A.BG_CARD, activeforeground=A.FG,
                  font=(A.FONT, 9), anchor="w", justify="left",
                  wraplength=490)

    def _check(page, text, key):
        var = tk.BooleanVar(value=settings[key])
        tk.Checkbutton(page, text=text, variable=var, **chk_kw).pack(
            anchor="w")
        return var

    # ── 1) Model ────────────────────────────────────────────────────────────
    page = _page("🤖 Model")
    _section(page, "SAĞLAYICI")
    provider = tk.StringVar(value=settings["provider"])
    for value, text in _PROVIDER_CHOICES:
        tk.Radiobutton(page, text=text, variable=provider, value=value,
                       **chk_kw).pack(anchor="w")
    _section(page, "YEREL MODEL (OLLAMA)")
    v_url = tk.StringVar(value=settings["ollama_url"])
    v_model = tk.StringVar(value=settings["ollama_model"])
    v_vision = tk.StringVar(value=settings["ollama_vision_model"])
    v_embed = tk.StringVar(value=settings["embed_model"])
    _row(page, "Adres", v_url)
    _row(page, "Sohbet modeli", v_model)
    _row(page, "Görsel modeli", v_vision)
    _row(page, "Gömme modeli", v_embed)
    _hint(page, f"Kurulum: ollama pull {settings['ollama_model']}  ·  "
                f"ollama pull {settings['embed_model']}")

    # ── 2) Claude ───────────────────────────────────────────────────────────
    page = _page("☁ Claude")
    _section(page, "CLAUDE (BULUT)")
    v_cmodel = tk.StringVar(value=settings["claude_model"])
    v_key = tk.StringVar(value="")
    _row(page, "Model", v_cmodel, values=_CLAUDE_MODELS)
    _row(page, "API anahtarı", v_key, show="•")
    _hint(page, "Kayıtlı anahtar var — değiştirmek için yazın." if has_key
          else "Boş bırakılırsa ANTHROPIC_API_KEY ortam değişkeni kullanılır.")
    v_delkey = tk.BooleanVar(value=False)
    if has_key:
        tk.Checkbutton(page, text="Kayıtlı anahtarı sil", variable=v_delkey,
                       **chk_kw).pack(anchor="w")
    v_cloud_enc = _check(page, "Şifreli sohbetlerde de her seferinde "
                               "sormadan Claude'u kullan (önerilmez)",
                         "cloud_for_encrypted")

    # ── 3) Özellikler ───────────────────────────────────────────────────────
    page = _page("✨ Özellikler")
    _section(page, "GENEL")
    v_lang = tk.StringVar(value=settings["target_language"])
    _row(page, "Çeviri/yanıt dili", v_lang)
    v_guard = _check(page, "Şifresiz gönderimde parola/IBAN/kart gibi hassas "
                           "bilgi uyarısı (yerel)", "leak_guard")
    _section(page, "ASİSTAN")
    v_inline = _check(page, "Yazarken satır içi öneri — Tab ile kabul et "
                            "(yalnız yerel Ollama modeliyle çalışır)",
                      "inline_complete")
    v_away = _check(page, "Uzaktayken gelen mesajlara yanıt taslağı hazırla "
                          "(asla gönderilmez; dönüşte gözden geçirirsiniz)",
                    "away_drafts")

    # ── 4) Ses ──────────────────────────────────────────────────────────────
    page = _page("🎙 Ses")
    _section(page, "SES → METİN")
    v_whisper = tk.StringVar(value=settings["whisper_model"])
    _row(page, "Whisper modeli", v_whisper, values=whisper_models)
    v_auto_stt = _check(page, "Gelen sesli mesajları otomatik yazıya dök "
                              "(yerel, faster-whisper)", "auto_transcribe")
    _section(page, "SESLİ OKUMA")
    v_tts = tk.StringVar(value=settings["tts_engine"])
    v_voice = tk.StringVar(value=settings["tts_voice"])
    v_tts_lang = tk.StringVar(value=settings["tts_lang"])
    _row(page, "Motor", v_tts, values=tts_engines)
    _row(page, "Piper ses modeli", v_voice)
    _row(page, "Okuma dili", v_tts_lang)
    _hint(page, "Motor yoksa: sudo pacman -S espeak-ng · Piper için .onnx "
                "ses modelinin tam yolunu girin (ör. tr_TR-dfki-medium.onnx).")

    # ── 5) MCP ──────────────────────────────────────────────────────────────
    page = _page("🔌 MCP")
    _section(page, "CLAUDE CODE / DESKTOP")
    v_mcp = _check(page, "MCP erişimi: harici AI araçları sohbet geçmişini "
                         "okuyabilir ve taslak bırakabilir (mesaj gönderemez)",
                   "mcp_enabled")
    v_mcp_enc = _check(page, "MCP'ye şifreli mesajların içeriğini de göster "
                             "(önerilmez)", "mcp_include_encrypted")
    if mcp_command:
        _hint(page, "Kayıt komutu (taslak için REST API de açık olmalı):")
        cmd_f = tk.Frame(page, bg=A.BG_CARD)
        cmd_f.pack(fill="x", pady=(2, 0))
        tk.Label(cmd_f, text=mcp_command, font=("Courier", 8), fg=A.FG,
                 bg=A.BG_HOVER, justify="left", wraplength=420, anchor="w",
                 padx=6, pady=4).pack(side="left", fill="x", expand=True)

        def _copy_cmd():
            dlg.clipboard_clear()
            dlg.clipboard_append(mcp_command)
            status.config(text="📋 MCP komutu panoya kopyalandı.",
                          fg=A.ACCENT_G)
        _link_button(cmd_f, "📋", _copy_cmd).pack(side="right")

    def _values():
        return {
            "provider": provider.get(),
            "ollama_url": v_url.get().strip(),
            "ollama_model": v_model.get().strip(),
            "ollama_vision_model": v_vision.get().strip(),
            "embed_model": v_embed.get().strip(),
            "claude_model": v_cmodel.get().strip(),
            "cloud_for_encrypted": bool(v_cloud_enc.get()),
            "target_language": v_lang.get().strip(),
            "whisper_model": v_whisper.get().strip(),
            "auto_transcribe": bool(v_auto_stt.get()),
            "leak_guard": bool(v_guard.get()),
            "inline_complete": bool(v_inline.get()),
            "away_drafts": bool(v_away.get()),
            "tts_engine": v_tts.get().strip(),
            "tts_voice": v_voice.get().strip(),
            "tts_lang": v_tts_lang.get().strip(),
            "mcp_enabled": bool(v_mcp.get()),
            "mcp_include_encrypted": bool(v_mcp_enc.get()),
        }

    def _key():
        if v_delkey.get():
            return ""
        typed = v_key.get().strip()
        return typed or None

    def _report(message, ok):
        if _alive(dlg):
            status.config(text=message, fg=A.ACCENT_G if ok else A.RED)

    def _test():
        status.config(text="⏳ Test ediliyor…", fg=A.ACCENT)
        on_test(_values(), _key(), _report)

    def _save():
        on_save(_values(), _key())
        dlg.destroy()

    ttk.Button(btns, text="🔌 Bağlantıyı Test Et",
               command=_test).pack(side="left")
    ttk.Button(btns, text="İptal", command=dlg.destroy).pack(side="right")
    ttk.Button(btns, text="Kaydet", command=_save).pack(side="right",
                                                        padx=(0, 6))
    return dlg
