"""Resource Hardening 2E follow-up — taşan medya görüntüleyici testleri.

`_open_media_overflow_viewer`: sayfa başına ≤30 satır, Previous/Next sınır
koruması, seçili URL'yi `_safe_open_url`'a iletme, `_closing` guard'ı.
Tüm tk widget'ları sahte; gerçek display gerekmez.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402

_created = []          # bu dosyanın sahte tk sınıflarının ürettikleri


class _FakeTop:
    def __init__(self, master=None, **kw):
        self.titles = []
        _created.append(self)

    def title(self, *a):
        self.titles.append(a)

    def configure(self, **k):
        pass

    def geometry(self, *a):
        pass

    def transient(self, *a):
        pass


class _FakeFrame:
    def __init__(self, master=None, **kw):
        pass

    def pack(self, *a, **k):
        pass


class _FakeListbox:
    def __init__(self, master=None, **kw):
        self.rows = []
        self.sel = []
        self.binds = {}
        _created.append(self)

    def insert(self, _i, text):
        self.rows.append(text)

    def delete(self, *a):
        self.rows.clear()

    def curselection(self):
        return self.sel

    def bind(self, seq, fn):
        self.binds[seq] = fn

    def pack(self, *a, **k):
        pass


class _FakeBtn:
    def __init__(self, master=None, **kw):
        self.kw = dict(kw)
        _created.append(self)

    def pack(self, *a, **k):
        pass


class _FakeLbl:
    def __init__(self, master=None, **kw):
        self.kw = dict(kw)
        _created.append(self)

    def pack(self, *a, **k):
        pass

    def config(self, **k):
        self.kw.update(k)


def _mw(closing=False):
    mw = object.__new__(xmpp.MainWindow)
    mw._closing = closing
    mw.root = object()
    return mw


def _patch_tk(monkeypatch):
    _created.clear()
    monkeypatch.setattr(xmpp.tk, "Toplevel", _FakeTop)
    monkeypatch.setattr(xmpp.tk, "Frame", _FakeFrame)
    monkeypatch.setattr(xmpp.tk, "Listbox", _FakeListbox)
    monkeypatch.setattr(xmpp.tk, "Button", _FakeBtn)
    monkeypatch.setattr(xmpp.tk, "Label", _FakeLbl)


def _viewer_widgets():
    tops = [w for w in _created if isinstance(w, _FakeTop)]
    lbs = [w for w in _created if isinstance(w, _FakeListbox)]
    btns = {}
    for w in _created:
        if isinstance(w, _FakeBtn):
            btns[w.kw.get("text", "")] = w
    infos = [w for w in _created if isinstance(w, _FakeLbl)
             and "Sayfa" in str(w.kw.get("text", ""))]
    return tops, lbs, btns, infos


# ══════════════════════════════════════════════════════════════════════════

def test_viewer_first_page_bounded(monkeypatch):
    _patch_tk(monkeypatch)
    urls = [f"http://x/u{i}" for i in range(100)]
    m = _mw()
    m._open_media_overflow_viewer("image", urls)
    tops, lbs, btns, infos = _viewer_widgets()
    assert len(tops) == 1
    assert len(lbs) == 1
    assert lbs[0].rows == urls[:30]            # sayfa başına ≤30
    assert infos[-1].kw["text"] == "Sayfa 1/4"


def test_next_pages_and_last_page_bound(monkeypatch):
    _patch_tk(monkeypatch)
    urls = [f"http://x/u{i}" for i in range(100)]
    _mw()._open_media_overflow_viewer("image", urls)
    _tops, lbs, btns, infos = _viewer_widgets()
    nxt = btns["Sonraki ▶"]
    nxt.kw["command"]()                        # sayfa 2
    assert lbs[0].rows == urls[30:60]
    nxt.kw["command"]()                        # sayfa 3
    nxt.kw["command"]()                        # sayfa 4 (son)
    assert lbs[0].rows == urls[90:100]         # 10 satır
    last_rows = list(lbs[0].rows)
    nxt.kw["command"]()                        # sonrası yok → aynı sayfa
    assert lbs[0].rows == last_rows
    assert infos[-1].kw["text"] == "Sayfa 4/4"


def test_previous_bound_at_first_page(monkeypatch):
    _patch_tk(monkeypatch)
    urls = [f"http://x/u{i}" for i in range(50)]
    _mw()._open_media_overflow_viewer("image", urls)
    _tops, lbs, btns, _infos = _viewer_widgets()
    btns["◀ Önceki"].kw["command"]()           # ilk sayfada geri → kalır
    assert lbs[0].rows == urls[:30]
    assert btns["◀ Önceki"].kw["command"] is not None


def test_open_action_uses_selected_url(monkeypatch):
    _patch_tk(monkeypatch)
    opened = []
    monkeypatch.setattr(xmpp, "_safe_open_url", lambda u: opened.append(u))
    urls = [f"http://x/u{i}" for i in range(100)]
    _mw()._open_media_overflow_viewer("image", urls)
    _tops, lbs, btns, _infos = _viewer_widgets()
    lbs[0].sel = [5]
    lbs[0].binds["<Double-Button-1>"](None)    # çift tık
    assert opened == [urls[5]]
    btns["🔗 Tarayıcıda Aç"].kw["command"]()   # açık buton
    assert opened[-1] == urls[5]


def test_selection_tracks_page_offset(monkeypatch):
    _patch_tk(monkeypatch)
    opened = []
    monkeypatch.setattr(xmpp, "_safe_open_url", lambda u: opened.append(u))
    urls = [f"http://x/u{i}" for i in range(100)]
    _mw()._open_media_overflow_viewer("image", urls)
    _tops, lbs, btns, _infos = _viewer_widgets()
    btns["Sonraki ▶"].kw["command"]()          # sayfa 2
    lbs[0].sel = [1]
    lbs[0].binds["<Double-Button-1>"](None)
    assert opened == [urls[30 + 1]]            # sayfa ofsetiyle doğru URL


def test_closing_suppresses_viewer(monkeypatch):
    _patch_tk(monkeypatch)
    m = _mw(closing=True)
    m._open_media_overflow_viewer("image", [f"http://x/u{i}" for i in range(5)])
    assert _created == []                      # görüntüleyici hiç kurulmadı


def test_1000_urls_pagination_bounded(monkeypatch):
    _patch_tk(monkeypatch)
    urls = [f"http://x/u{i}" for i in range(1000)]
    _mw()._open_media_overflow_viewer("image", urls)
    _tops, lbs, btns, infos = _viewer_widgets()
    assert len(lbs) == 1
    assert len(lbs[0].rows) == 30              # ilk sayfa ≤30
    nxt = btns["Sonraki ▶"]
    for _ in range(33):                        # son sayfaya kadar ilerle
        nxt.kw["command"]()
    assert infos[-1].kw["text"] == "Sayfa 34/34"
    assert len(lbs[0].rows) == 1000 - 33 * 30  # 10 satır
    assert lbs[0].rows[0] == "http://x/u990"   # sıra korunur
    # sayfa değişimleri birikmez: her show öncesi listbox temizlenir
    assert len(lbs[0].rows) <= 30
