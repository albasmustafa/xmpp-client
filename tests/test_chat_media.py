"""FAZ 4C-5B1: media presentation + stale-holder guard regression testleri."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fake_selectable  # noqa: E402

import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Holder:
    """Destroyed/live holder simülasyonu."""

    def __init__(self, alive=True):
        self.alive = alive
        self.configs = []
        self.image = None
        self.cursor = None
        self.binds = {}

    def winfo_exists(self):
        return self.alive

    def config(self, **k):
        if not self.alive:
            raise AssertionError("destroyed holder'a config çağrıldı")
        self.configs.append(k)

    def bind(self, seq, fn=None):
        self.binds[seq] = fn


# ── M1: late image callback / destroyed holder ──────────────────────────────
def test_place_image_skips_destroyed_holder(monkeypatch):
    monkeypatch.setattr(xmpp, "_photo_refs", [], raising=False)
    w = object.__new__(xmpp.MainWindow)
    w._photo_refs = []
    w._scroll_bottom = _Capture()
    w._show_image_fullscreen = lambda *a: None
    made = _Capture()
    monkeypatch.setattr(xmpp, "ImageTk", types.SimpleNamespace(
        PhotoImage=lambda img: made(img)))

    dead = _Holder(alive=False)
    xmpp.MainWindow._place_image(w, dead, object(), "BG", "http://x")

    assert made.calls == []          # PhotoImage dahi üretilmedi
    assert w._photo_refs == []       # gereksiz ref yok
    assert w._scroll_bottom.calls == []


def test_place_image_live_holder_places_and_retains(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w._photo_refs = []
    w._scroll_bottom = _Capture()
    w._show_image_fullscreen = _Capture()
    monkeypatch.setattr(xmpp, "ImageTk", types.SimpleNamespace(
        PhotoImage=lambda img: f"photo:{img}"))

    live = _Holder()
    xmpp.MainWindow._place_image(w, live, "IMG", "BG", "http://x")

    assert live.image == "photo:IMG"
    assert w._photo_refs == ["photo:IMG"]
    assert live.configs[0] == {"image": "photo:IMG", "text": "", "bg": "BG"}
    assert live.cursor if False else live.configs[-1] == {"cursor": "hand2"}
    assert "<Button-1>" in live.binds
    assert len(w._scroll_bottom.calls) == 1


def test_image_download_error_late_callback_skips_destroyed_holder(monkeypatch):
    scheduled = []

    def fake_safe_after(ms, fn, *a):
        scheduled.append((fn, a))

    monkeypatch.setattr(xmpp, "_safe_after", fake_safe_after, raising=False)
    w = object.__new__(xmpp.MainWindow)
    w._safe_after = fake_safe_after

    # indirme hatası → hata callback'i schedule edilir
    def boom(*a, **k):
        raise OSError("ağ yok")

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", boom)
    dead = _Holder(alive=False)
    # Hotfix 2B: worker artık abone listesiyle çalışır; dead holder
    # abone olarak kayıtlıyken fetch patlar → hata dağıtımı onu atlamalı
    w._media_inflight = {("image", "http://x"): {"subs": [(dead, "BG")]}}
    xmpp.MainWindow._image_fetch_worker(w, "http://x")

    assert scheduled, "hata callback'i schedule edilmedi"
    assert ("image", "http://x") not in w._media_inflight  # in-flight temiz
    fn, fargs = scheduled[-1]
    fn(*fargs)  # geç gelen hata UI'ı (url, subs)
    assert dead.configs == []


# ── M2: fullscreen Toplevel kapanınca geç callback ──────────────────────────
class _Lbl:
    def __init__(self, alive=True, text=""):
        self.alive = alive
        self.text = text
        self.configs = []

    def pack(self, **k):
        pass

    def bind(self, seq, fn=None):
        pass

    def config(self, **k):
        if not self.alive:
            raise AssertionError("destroyed fullscreen label'a config")
        self.configs.append(k)

    def winfo_exists(self):
        return self.alive


class _Top:
    def __init__(self):
        self.binds = {}

    def pack(self, *a, **k):
        pass

    def title(self, *a):
        pass

    def configure(self, **k):
        pass

    def transient(self, *a):
        pass

    def geometry(self, *a):
        pass

    def bind(self, seq, fn=None):
        self.binds[seq] = fn

    def focus_set(self):
        pass

    def destroy(self):
        pass


def test_fullscreen_error_late_callback_skips_destroyed_label(monkeypatch):
    labels = []

    def fake_label(parent, **kw):
        lb = _Lbl()
        labels.append((lb, kw))
        return lb

    monkeypatch.setattr(xmpp.tk, "Toplevel", lambda *a, **k: _Top())
    monkeypatch.setattr(xmpp.tk, "Label", fake_label)
    monkeypatch.setattr(xmpp.tk, "Frame", lambda *a, **k: _Top())
    monkeypatch.setattr(xmpp, "_make_popover", lambda *a, **k: None)

    scheduled = []

    def fake_safe_after(ms, fn, *a):
        scheduled.append((fn, a))

    threads = []

    class _T:
        def __init__(self, target=None, daemon=None):
            threads.append(target)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    w = object.__new__(xmpp.MainWindow)
    w._safe_after = fake_safe_after
    w._photo_refs = []
    w.root = object()

    xmpp.MainWindow._show_image_fullscreen(w, None, "http://x")

    # worker'ı çalıştır → hata yolu schedule eder
    threads[-1]()
    assert scheduled, "fullscreen hata callback'i yok"
    load_lbl = [lb for lb, kw in labels
                if str(kw.get("text", "")).startswith("📷")][0]
    load_lbl.alive = False  # kullanıcı pencereyi kapattı
    fn, _args = scheduled[-1]
    fn()
    assert load_lbl.configs == []


# ── Presentation primitives ─────────────────────────────────────────────────
import ui.chat.media as media_mod  # noqa: E402


class _MW:
    def __init__(self, master=None, **kw):
        self.master = master
        self.kw = dict(kw)
        self.children = []
        self.binds = {}
        if isinstance(master, _MW):
            master.children.append(self)

    def pack(self, *a, **k):
        self.kw.setdefault("_pack", (a, k))

    def grid(self, *a, **k):
        pass

    def config(self, **k):
        self.kw.update(k)

    def configure(self, **k):
        self.kw.update(k)

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def winfo_children(self):
        return list(self.children)

    def winfo_exists(self):
        return True

    def columnconfigure(self, *a, **k):
        pass

    def rowconfigure(self, *a, **k):
        pass

    def place(self, *a, **k):
        pass

    def delete(self, *a):
        pass

    def title(self, *a):
        pass

    def transient(self, *a):
        pass

    def geometry(self, *a):
        pass

    def focus_set(self):
        pass


def _patch_media_tk(monkeypatch):
    monkeypatch.setattr(media_mod, "tk", types.SimpleNamespace(
        Frame=_MW, Label=_MW, Toplevel=_MW))


def _theme():
    th = dict(xmpp._chat_theme())
    th.setdefault("BG", xmpp.BG)
    return th


def test_image_placeholder_presentation(monkeypatch):
    _patch_media_tk(monkeypatch)
    parent = _MW()
    lbl = media_mod.image_placeholder(parent, _theme(), "BUBBLE")
    assert lbl.kw["text"] == "📷 Yükleniyor…"
    assert lbl.kw["fg"] == xmpp.FG_DIM and lbl.kw["bg"] == "BUBBLE"
    assert lbl.kw["_pack"][1]["pady"] == (4, 2)
    assert parent.children == [lbl]


def test_place_image_and_error_and_photo(monkeypatch):
    _patch_media_tk(monkeypatch)
    holder = _MW()
    full = _Capture()
    media_mod.place_image(holder, "PHOTO", "BG", lambda e: full(e))
    assert holder.kw["image"] == "PHOTO" and holder.kw["bg"] == "BG"
    assert holder.image == "PHOTO" and holder.kw["cursor"] == "hand2"
    holder.binds["<Button-1>"][0](None)
    assert len(full.calls) == 1

    media_mod.image_error(holder, _theme())
    assert holder.kw["text"] == "⚠ Resim yüklenemedi"
    assert holder.kw["fg"] == xmpp.RED

    lbl = _MW()
    media_mod.place_photo(lbl, "P2")
    assert lbl.image == "P2" and lbl.kw["text"] == ""


def test_image_link_open_once(monkeypatch):
    _patch_media_tk(monkeypatch)
    opened = _Capture()
    lnk = media_mod.image_link(_MW(), _theme(), "http://x/a.jpg", "BG",
                               lambda: opened())
    assert lnk.kw["text"] == "🔗 http://x/a.jpg"
    lnk.binds["<Button-1>"][0](None)
    assert len(opened.calls) == 1


def test_file_card_presentation_and_callbacks(monkeypatch):
    _patch_media_tk(monkeypatch)
    opened, folder = _Capture(), _Capture()
    card = media_mod.file_card(_MW(), _theme(), "rapor.pdf", "12 KB",
                               "Aç", "Klasörü Aç", opened, folder)
    texts = [c.kw.get("text") for c in card.winfo_children() if c.kw.get("text")]
    assert texts == ["📎  rapor.pdf", "12 KB"]
    btns = card.winfo_children()[-1].winfo_children()
    assert [b.kw["text"] for b in btns] == ["Aç", "Klasörü Aç"]
    btns[0].binds["<Button-1>"][0](None)
    btns[1].binds["<Button-1>"][0](None)
    assert len(opened.calls) == 1 and len(folder.calls) == 1

    # size boşsa ikinci label yok
    card2 = media_mod.file_card(_MW(), _theme(), "x", "", "A", "B",
                                opened, folder)
    assert len(card2.winfo_children()) == 2


def test_url_preview_labels(monkeypatch):
    _patch_media_tk(monkeypatch)
    c = _MW()
    media_mod.url_preview_labels(c, _theme(), "Başlık", "A" * 200)
    assert c.children[0].kw["text"] == "Başlık"
    assert len(c.children[1].kw["text"]) == 150


def test_fullscreen_window_presentation(monkeypatch):
    _patch_media_tk(monkeypatch)
    opened = _Capture()
    root = _MW()
    top, lbl = media_mod.fullscreen_window(root, _theme(), lambda: opened())
    assert lbl.kw["text"] == "📷 Yükleniyor…"
    assert top.kw["bg"] == xmpp.BG
    bar = top.winfo_children()[0]
    link = bar.winfo_children()[1]
    link.binds["<Button-1>"][0](None)
    assert len(opened.calls) == 1
    esc = top.binds["<Escape>"][0]
    assert callable(esc)


# ── _append integration + ordering (BODY → MEDIA → META) ────────────────────
def _append_window(monkeypatch):
    _patch_media_tk(monkeypatch)
    monkeypatch.setattr(xmpp._render, "tk", types.SimpleNamespace(
        Frame=_MW, Label=_MW, Canvas=_MW, StringVar=_MW, Toplevel=_MW))
    fake_selectable.install(monkeypatch, _MW)   # seçilebilir gövde
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.msg_frame = _MW()
    w._bubble_widgets = []
    w._avatars = {}
    w._photo_refs = []
    w._reactions = {}
    w._reply_map = {}
    w._last_date_label = ""
    w._prune_photo_refs = lambda: None
    w._bind_scroll_widget = _Capture()
    w._scroll_bottom = _Capture()
    w._render_reactions = _Capture()
    w._jump_to_message = _Capture()
    w._set_reply = _Capture()
    w._attach_file_card = lambda *a: None
    w._bind_message_menu = lambda *a, **k: None
    monkeypatch.setattr(xmpp, "_avatar", lambda *a, **k: _MW())
    xmpp.MainWindow._last_sender = None
    return w


def test_append_media_ordering_and_worker_ownership(monkeypatch):
    w = _append_window(monkeypatch)
    order = []
    orig_ph = media_mod.image_placeholder

    def spy_ph(parent, theme, bg):
        order.append("media")
        return orig_ph(parent, theme, bg)

    monkeypatch.setattr(xmpp._media_ui, "image_placeholder", spy_ph)
    orig_meta = xmpp._render.render_meta_row

    def spy_meta(*a, **k):
        order.append("meta")
        return orig_meta(*a, **k)

    monkeypatch.setattr(xmpp._render, "render_meta_row", spy_meta)
    threads = []

    class _T:
        def __init__(self, target=None, args=(), daemon=None):
            threads.append((target, args))

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _T)

    # Hotfix 2A/2B: worker bounded dispatcher üzerinden spawn ediliyor;
    # runner closure'ı, _append anındaki hedefi (kayıt için instance attr)
    # argümanlarıyla çağırır.
    seen = []
    w._image_fetch_worker = lambda *a: seen.append(a)

    xmpp.MainWindow._append(w, "bak http://x/a.jpg", "them", sender="Ali")

    assert order == ["media", "meta"]
    assert threads  # dispatcher üzerinden tek worker spawn
    threads[0][0]()  # runner → worker'ı argümanlarıyla çalıştır
    assert seen and seen[0][0] == "http://x/a.jpg"


def test_append_image_link_branch_without_pil(monkeypatch):
    w = _append_window(monkeypatch)
    links = _Capture()
    monkeypatch.setattr(xmpp, "HAS_PIL", False)
    monkeypatch.setattr(xmpp._media_ui, "image_link",
                        lambda *a, **k: links(a))
    xmpp.MainWindow._append(w, "bak http://x/a.jpg", "them", sender="Ali")
    assert len(links.calls) == 1


# ── No-domain-leak + GUI-only ImageTk contract ──────────────────────────────
def test_media_module_no_domain_and_no_imagetk():
    import inspect
    src = inspect.getsource(media_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot",
                  "run_coroutine_threadsafe", "sqlite", "_db_", "urlopen(",
                  "threading", "gui_q", "subprocess", "_safe_after",
                  "import xmpp", "asyncio", "ImageTk", ".after("):
        assert token not in src, token
