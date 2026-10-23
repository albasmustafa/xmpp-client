"""ui/dialogs/ai.py görünüm sözleşmeleri — sahte tk widget'larıyla.

Kanıtlar:
- Modül durumsuz görünümdür: ağ/DB/thread/model bağımlılığı yok.
- ResultWindow: akış parçaları yanıta eklenir, kesin metin yerine geçer;
  takip sorusu soru+yanıt bloğu açar; hata kısmi yanıtı ve yanıtlanamayan
  soruyu siler, soruyu kutuya geri koyar; soru kutusu yalnız boştayken açık.
- Kopyala: tek sonuçta yanıt, takip sonrası tüm konuşma.
- Kapanış (pencere, Destroy) `on_close`'u tek kez çağırır; sonra set_*
  çağrıları sessizdir.
- Kaynak bağlantıları tıklanınca payload'ı iletir.
- ActionsWindow: düzenlenen/seçilen öğeleri toplar, sonucu durumda gösterir.
"""
import inspect
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fake_selectable  # noqa: E402

import ui.dialogs.ai as ui_ai  # noqa: E402
import xmpp  # noqa: E402


# ── Sahte tk ────────────────────────────────────────────────────────────────
class _W:
    def __init__(self, master=None, **kw):
        self.kw = dict(kw)
        self.binds = {}
        self.children = []
        self.packed = None
        self.destroyed = False
        if isinstance(master, _W):
            master.children.append(self)

    def pack(self, **kw):
        self.packed = kw

    def pack_forget(self):
        self.packed = None

    def config(self, **kw):
        self.kw.update(kw)

    configure = config

    def bind(self, seq, fn, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def winfo_children(self):
        return [c for c in self.children if not c.destroyed]

    def destroy(self):
        self.destroyed = True

    def winfo_exists(self):
        return not self.destroyed

    def set(self, *a):              # Scrollbar.set
        pass

    def click(self):
        for fn in self.binds.get("<Button-1>", []):
            fn(types.SimpleNamespace(widget=self))

    # Akış yerleşimi (hızlı eylem çipleri): metin başına 8 px + kenar
    def place(self, **kw):
        self.placed = kw

    def winfo_reqwidth(self):
        return 8 * len(str(self.kw.get("text", ""))) + 18

    def winfo_reqheight(self):
        return 24

    def winfo_width(self):
        return getattr(self, "width", 1)


class _Top(_W):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.clip = None
        self.protocols = {}

    def title(self, *a):
        pass

    def geometry(self, *a):
        pass

    def minsize(self, *a):
        pass

    def transient(self, *a):
        pass

    def protocol(self, name, fn):
        self.protocols[name] = fn

    def after(self, ms, fn, *a):
        self.timers = getattr(self, "timers", [])
        self.timers.append((fn, a))
        return f"after#{len(self.timers)}"

    def after_cancel(self, ident):
        pass

    def after_idle(self, fn, *a):
        self.idle = getattr(self, "idle", [])
        self.idle.append((fn, a))

    def run_idle(self):
        while getattr(self, "idle", None):
            fn, a = self.idle.pop(0)
            fn(*a)

    def clipboard_clear(self):
        self.clip = ""

    def clipboard_append(self, text):
        self.clip += text

    def destroy(self):
        super().destroy()
        for fn in self.binds.get("<Destroy>", []):
            fn(types.SimpleNamespace(widget=self))


class _Text(_W):
    """Tek satırlık tampon; 'end' ve 'end-1c' = tampon sonu; işaretler
    Tk yerçekimi kuralına uyar (sol: tam işaret konumuna ekleme işareti
    yerinde bırakır)."""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.buf = ""
        self.marks, self.grav = {}, {}
        self.state = "normal"
        self.tagged = []
        self.seen = []

    def configure(self, **kw):
        if "state" in kw:
            self.state = kw["state"]
        super().configure(**kw)

    config = configure

    def _i(self, index):
        if index in ("end", "end-1c"):
            return len(self.buf)
        if index == "1.0":
            return 0
        return self.marks[index]

    def insert(self, index, text, *tags):
        assert self.state == "normal", "kilitli Text'e yazıldı"
        p = self._i(index)
        self.buf = self.buf[:p] + text + self.buf[p:]
        for m, pos in self.marks.items():
            if pos > p or (pos == p and self.grav.get(m) == "right"):
                self.marks[m] = pos + len(text)
        if tags:
            self.tagged.append((text, tags))

    def delete(self, a, b=None):
        assert self.state == "normal", "kilitli Text'ten silindi"
        pa, pb = self._i(a), (self._i(b) if b else self._i(a) + 1)
        if pb <= pa:
            return
        self.buf = self.buf[:pa] + self.buf[pb:]
        for m, pos in self.marks.items():
            if pos >= pb:
                self.marks[m] = pos - (pb - pa)
            elif pos > pa:
                self.marks[m] = pa

    def get(self, a, b):
        return self.buf[self._i(a):self._i(b)]

    def mark_set(self, m, index):
        self.marks[m] = self._i(index)

    def mark_gravity(self, m, g):
        self.grav[m] = g

    def tag_configure(self, *a, **k):
        pass

    def see(self, index):
        self.seen.append(index)

    def yview(self, *a):
        return (0.0, 1.0)


class _Var:
    def __init__(self, master=None, value=""):
        self.v = value

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


class _Entry(_W):
    def __init__(self, master=None, placeholder="", textvariable=None, **kw):
        super().__init__(master, **kw)
        self.var = textvariable or _Var()
        self._showing_ph = False
        self.states = []

    def get_value(self):
        return "" if self._showing_ph else self.var.get()

    def state(self, s):
        self.states.append(tuple(s))

    def focus_force(self):
        pass


class _Canvas(_W):
    def create_window(self, *a, **k):
        return 1

    def bbox(self, *a):
        return (0, 0, 1, 1)

    def itemconfig(self, *a, **k):
        pass

    def yview(self, *a):
        return (0.0, 1.0)

    def yview_scroll(self, *a):
        pass


@pytest.fixture()
def fake_tk(monkeypatch):
    monkeypatch.setattr(ui_ai, "tk", types.SimpleNamespace(
        Toplevel=_Top, Frame=_W, Label=_W, Text=_Text, StringVar=_Var,
        BooleanVar=_Var, Checkbutton=_W, Canvas=_Canvas))
    monkeypatch.setattr(ui_ai, "ttk", types.SimpleNamespace(
        Scrollbar=_W, Entry=_Entry, Combobox=_W, Button=_W))
    monkeypatch.setattr(xmpp, "PlaceholderEntry", _Entry)
    # Yanıt yazıları seçilebilir metin (ui.selectable): sahtesi _W üretir
    monkeypatch.setattr(ui_ai, "_selectable", fake_selectable.make(_W))


def _find(widget, text):
    if widget.kw.get("text") == text:
        return widget
    for c in widget.children:
        hit = _find(c, text)
        if hit is not None:
            return hit
    return None


def _entry(win):
    return win._ask_entry


def _submit(win, text):
    _entry(win).var.set(text)
    for fn in _entry(win).binds["<Return>"]:
        assert fn(None) == "break"


# ── 1) Bağımlılık taraması ──────────────────────────────────────────────────
def test_ai_dialogs_have_no_domain_dependencies():
    src = inspect.getsource(ui_ai)
    for token in ("slixmpp", "sqlite", "_db_", "urlopen(", "threading.",
                  "gui_q", "subprocess", "_safe_after", "asyncio",
                  "import anthropic", "ollama_chat(", "ollama_embed(",
                  "xmppcore", "run_coroutine"):
        assert token not in src, token


# ── 2) ResultWindow ─────────────────────────────────────────────────────────
def test_stream_then_final_text_then_followup_answer(fake_tk):
    asks, acted = [], []
    win = ui_ai.ResultWindow(_W(), "T", "alt", [("Eylem", acted.append)],
                             on_ask=asks.append)
    t = win._text
    assert _entry(win).states[-1] == ("disabled",)   # yanıt gelmeden kapalı
    win.append_text("Mer")
    win.append_text("haba")
    assert t.buf == "Merhaba" and "Yazılıyor" in win._status.kw["text"]
    win.set_text("Merhaba!")
    assert t.buf == "Merhaba!" and t.state == "disabled"
    assert _entry(win).states[-1] == ("!disabled",)
    _submit(win, "  Saat kaç?  ")
    assert asks == ["Saat kaç?"]
    win.begin_question("Saat kaç?")
    assert _entry(win).var.get() == "" and _entry(win).states[-1] == (
        "disabled",)
    _submit(win, "çift gönderim")                   # kilitliyken yok sayılır
    assert asks == ["Saat kaç?"]
    win.append_text("14")
    win.append_text(":0")
    assert t.buf == "Merhaba!\n\n❓ Saat kaç?\n\n14:0"
    win.set_answer("14:00")
    assert t.buf == "Merhaba!\n\n❓ Saat kaç?\n\n14:00"
    assert ("❓ Saat kaç?\n", ("q",)) in t.tagged
    _find(win.top, "Eylem").click()
    assert acted == ["14:00"]
    _find(win.top, "📋 Kopyala").click()
    assert win.top.clip == t.buf                     # takip sonrası: hepsi


def test_failed_followup_leaves_no_trace_and_restores_question(fake_tk):
    win = ui_ai.ResultWindow(_W(), "T", on_ask=lambda q: None)
    win.set_text("Özet")
    win.begin_question("Yer neresi?")
    win.append_text("kısmi yan")
    _entry(win).var.set("")
    win.set_error("bağlantı koptu")
    assert win._text.buf == "Özet"
    assert _entry(win).var.get() == "Yer neresi?"
    assert win._status.kw["text"] == "⚠ bağlantı koptu"
    assert _entry(win).states[-1] == ("!disabled",)
    # kullanıcı bu arada yeni bir şey yazdıysa ezilmez
    win.begin_question("q2")
    _entry(win).var.set("yeni soru")
    win.set_error("x")
    assert _entry(win).var.get() == "yeni soru"


def test_first_turn_error_discards_partial_and_keeps_ask_closed(fake_tk):
    win = ui_ai.ResultWindow(_W(), "T", on_ask=lambda q: None)
    win.append_text("reddedilen kısmi")
    win.set_error("Claude bu isteği güvenlik nedeniyle yanıtlamadı.")
    assert win._text.buf == ""
    assert _entry(win).states[-1] == ("disabled",)


def test_ask_ready_window_and_first_question_answer(fake_tk):
    asks = []
    win = ui_ai.ResultWindow(_W(), "Geçmişe sor", on_ask=asks.append,
                             ask_ready=True)
    assert _entry(win).states[-1] == ("!disabled",)
    win.begin_question("adres?")
    win.append_text("Moda")
    win.set_answer("Moda [1]")
    assert win._text.buf == "❓ adres?\n\nModa [1]"
    win.begin_question("kod?")
    win.set_error("yok")
    assert win._text.buf == "❓ adres?\n\nModa [1]"
    win2 = ui_ai.ResultWindow(_W(), "G", on_ask=asks.append, ask_ready=True)
    win2.begin_question("ilk")
    win2.set_error("hata")
    assert win2._text.buf == "" and _entry(win2).states[-1] == ("!disabled",)


def test_single_result_window_unchanged_without_ask(fake_tk):
    win = ui_ai.ResultWindow(_W(), "T")
    assert win._ask_entry is None
    win.set_text("Sonuç")
    _find(win.top, "📋 Kopyala").click()
    assert win.top.clip == "Sonuç"
    win.set_choices(["a", "b"], lambda s: None)
    assert win._text.buf == "a\nb"


def test_close_notifies_once_and_silences_updates(fake_tk):
    closed = []
    win = ui_ai.ResultWindow(_W(), "T", on_ask=lambda q: None,
                             on_close=lambda: closed.append(1))
    win.top.protocols["WM_DELETE_WINDOW"]()
    assert closed == [1] and not win.alive()
    win.top.destroy()
    win.append_text("geç")
    win.set_text("geç")
    win.set_error("geç")
    assert closed == [1] and win._text.buf == ""
    other = []
    win2 = ui_ai.ResultWindow(_W(), "T", on_close=lambda: other.append(1))
    win2.top.destroy()                     # üst pencere yok edildi
    assert other == [1]


def test_sources_are_clickable_and_clearable(fake_tk):
    picked = []
    win = ui_ai.ResultWindow(_W(), "T", on_ask=lambda q: None)
    win.set_sources([("[1] Ali", ("a@b", "m1")), ("[2] Can", ("c@d", ""))],
                    picked.append, title="Kaynaklar")
    assert win._sources.packed["before"] is win._body
    _find(win._sources, "[2] Can").click()
    assert picked == [("c@d", "")]
    assert _find(win._sources, "Kaynaklar") is not None
    win.set_sources([], picked.append)
    assert win._sources.packed is None and win._sources.winfo_children() == []


# ── 3) ActionsWindow ────────────────────────────────────────────────────────
def _items():
    return [{"kind": "event", "title": "Buluşma", "date": "2026-10-11",
             "time": "14:00", "end_time": "", "location": "Kafe",
             "notes": "not", "quote": "yarın 14"},
            {"kind": "task", "title": "Fatura", "date": "", "time": "",
             "end_time": "", "location": "", "notes": "", "quote": ""}]


def test_actions_window_collects_edited_selection(fake_tk):
    exported = []
    win = ui_ai.ActionsWindow(_W(), "📅 Ali", "alt",
                              lambda items: exported.append(items) or (
                                  True, "✓ kaydedildi"),
                              lambda items: None)
    win.set_items(_items())
    assert "2 öğe" in win._status.kw["text"]
    checked, kind, vars_, _item = win._rows[0]
    vars_["title"].set("  Buluşma (ofis) ")
    vars_["time"].set("15:00")
    kind.set("✅ Görev")
    win._rows[1][0].set(False)                     # ikinci öğe seçili değil
    _find(win.top, "📅 .ics olarak kaydet").click()
    assert exported == [[{"kind": "task", "title": "Buluşma (ofis)",
                          "date": "2026-10-11", "time": "15:00",
                          "end_time": "", "location": "Kafe", "notes": "not",
                          "quote": "yarın 14"}]]
    assert win._status.kw["text"] == "✓ kaydedildi"
    win._rows[0][0].set(False)
    _find(win.top, "⏰ Hatırlatıcı kur").click()
    assert "en az bir" in win._status.kw["text"]


def test_actions_window_copy_empty_and_close(fake_tk):
    closed = []
    win = ui_ai.ActionsWindow(_W(), "T", "", lambda i: None, lambda i: None,
                              on_close=lambda: closed.append(1))
    win.set_items([])
    assert "bulunamadı" in win._status.kw["text"]
    win.set_items(_items())
    _find(win.top, "📋 Kopyala").click()
    assert win.top.clip == ("📅 Etkinlik: Buluşma · 2026-10-11 14:00 · @ Kafe"
                            "\n✅ Görev: Fatura")
    win.close()
    win.close()
    assert closed == [1]


def test_format_action_line():
    assert ui_ai.format_action_line(
        {"kind": "event", "title": "T", "date": "2026-10-11",
         "time": "14:00", "end_time": "15:30", "location": ""}) == \
        "📅 Etkinlik: T · 2026-10-11 14:00–15:30"
    assert ui_ai.format_action_line({"kind": "?", "title": "X"}) == \
        "✅ Görev: X"
