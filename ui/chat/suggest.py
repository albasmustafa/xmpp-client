"""Satır içi öneri çubuğu (yazarken AI devam önerisi).

Giriş satırının hemen altında ince bir satır: "✨ …taslak<öneri>   Tab ↹
kabul · Esc kapat". Giriş satırının `grid` düzeninde ayrı bir satırdır;
giriş alanının `pack` sırasına (yanıt/sabit çubukları) dokunmaz.
Durumsuz sunum: öneri metni ve görünürlük MainWindow'dan gelir;
model/thread/after YOKTUR.
"""
import tkinter as tk


class SuggestionBar:
    def __init__(self, parent, theme, *, row=1, columnspan=8,
                 on_accept=None):
        self._bar = tk.Frame(parent, bg=theme["BG_CARD"])
        self._grid = {"row": row, "column": 0, "columnspan": columnspan,
                      "sticky": "ew", "pady": (6, 0)}
        self._text = ""
        self._lbl = tk.Label(self._bar, text="", fg=theme["FG_DIM"],
                             bg=theme["BG_CARD"],
                             font=(theme["FONT"], 9, "italic"), anchor="w",
                             cursor="hand2")
        self._lbl.pack(side="left", fill="x", expand=True)
        tk.Label(self._bar, text="Tab ↹ kabul · Esc kapat",
                 fg=theme["FG_DIM"], bg=theme["BG_CARD"],
                 font=(theme["FONT"], 7)).pack(side="right")
        if on_accept is not None:
            self._lbl.bind("<Button-1>", lambda _e: on_accept())

    @property
    def text(self) -> str:
        return self._text

    @property
    def visible(self) -> bool:
        return bool(self._text)

    def show(self, draft, suggestion):
        """Taslağın son kısmı + öneri (uzun taslak baştan kısaltılır)."""
        self._text = suggestion
        tail = draft[-40:]
        if len(draft) > 40:
            tail = "…" + tail
        self._lbl.config(text=f"✨ {tail}{suggestion}")
        self._bar.grid(**self._grid)

    def hide(self):
        if self._text:
            self._text = ""
            self._bar.grid_remove()
