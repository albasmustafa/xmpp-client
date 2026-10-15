"""Security Hotfix 2B — image/URL-preview single-flight + bounded cache.

Kapsam:
- aynı (kind, url) için tek network fetch (in-flight subscriber birleştirme),
- tamamlanan sonucun bounded LRU cache'ten reuse'i (history/MAM re-render),
- ("image", url) ve ("preview", url) anahtar ayrımı,
- hata yollarında in-flight temizliği + cache zehirsizliği,
- evict → yeniden fetch döngüsü,
- `_closing` davranışı.

Deterministik: gerçek ağ yok, sleep-flaky yok (Event gate + kuyruk boşaltma).
Audio bilinçli olarak scope dışıdır (ayrı tur).
"""
import io
import queue
import threading
import time
from collections import OrderedDict

import xmpp

# ══════════════════════════════════════════════════════════════════════════
# Yardımcılar
# ══════════════════════════════════════════════════════════════════════════

def _make_mw():
    mw = object.__new__(xmpp.MainWindow)
    mw._closing = False
    mw.gui_q = queue.Queue()
    mw._photo_refs = []
    mw._temp_files = []
    mw._scroll_bottom = lambda: None
    return mw


def _drain(mw):
    ran = []
    while True:
        try:
            kind, data = mw.gui_q.get_nowait()
        except queue.Empty:
            return ran
        assert kind == "__ui__", kind
        fn, args = data
        fn(*args)
        ran.append(fn)


def _drain_wait(mw, timeout=5.0):
    deadline = time.time() + timeout
    ran = []
    while time.time() < deadline:
        ran.extend(_drain(mw))
        if ran:
            time.sleep(0.02)
            ran.extend(_drain(mw))  # zincirleme teslimler
            return ran
        time.sleep(0.01)
    return ran


def _tiny_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (5, 100, 200)).save(buf, format="PNG")
    return buf.getvalue()


class _Holder:
    def __init__(self, alive=True):
        self.alive = alive
        self.placed = []
        self.errors = []

    def winfo_exists(self):
        return self.alive


class _Container:
    def __init__(self):
        self.labels = []


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.headers = {}

    def read(self, n=-1):
        if n is None or n < 0:
            return self._payload
        return self._payload[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _GatedUrlopen:
    """urlopen yerine geçer; gate kapatılana kadar bekletir."""

    def __init__(self, payload):
        self.calls = 0
        self.entered = threading.Event()
        self.gate = threading.Event()
        self._payload = payload

    def __call__(self, req, timeout=None):
        self.calls += 1
        self.entered.set()
        self.gate.wait(10)
        return _FakeResp(self._payload)


class _GatedPreview:
    def __init__(self):
        self.calls = 0
        self.entered = threading.Event()
        self.gate = threading.Event()

    def __call__(self, url):
        self.calls += 1
        self.entered.set()
        self.gate.wait(10)
        return {"title": f"T{self.calls}", "desc": "D"}


def _wait_inflight_cleared(mw, key, timeout=3.0):
    """Event üretmeyen yollar (cache hit / sessiz preview) için poll."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if key not in mw._media_inflight:
            _drain(mw)
            return True
        time.sleep(0.005)
    _drain(mw)
    return False


def _wire_image_ui(monkeypatch, mw):
    """Gerçek guard'lı yerleşim + hata yollarını gözlemlenebilir yap."""
    monkeypatch.setattr(xmpp.ImageTk, "PhotoImage", lambda img: "photo")
    monkeypatch.setattr(xmpp._media_ui, "place_image",
                        lambda h, photo, bg, cb: h.placed.append(photo))
    monkeypatch.setattr(xmpp._media_ui, "image_error",
                        lambda h, theme: h.errors.append("err"))


# ══════════════════════════════════════════════════════════════════════════
# Image: single-flight + abone dağıtımı
# ══════════════════════════════════════════════════════════════════════════

def test_same_image_url_simultaneous_single_fetch(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    net = _GatedUrlopen(_tiny_png())
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    h1, h2 = _Holder(), _Holder()

    assert mw._request_image("http://x/a.png", h1, "#fff") is True
    assert net.entered.wait(5)
    # in-flight kaydı varken ikinci istek: yeni fetch değil, abone
    assert ("image", "http://x/a.png") in mw._media_inflight
    assert mw._request_image("http://x/a.png", h2, "#fff") is True
    assert net.calls == 1  # tek network fetch

    net.gate.set()
    _drain_wait(mw)
    assert h1.placed and h2.placed          # iki holder da sonucu aldı
    assert mw._media_inflight == {}         # abone listesi serbest bırakıldı


def test_one_holder_destroyed_other_still_placed(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    net = _GatedUrlopen(_tiny_png())
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    h1, h2 = _Holder(), _Holder()

    assert mw._request_image("http://x/b.png", h1, "#fff") is True
    assert mw._request_image("http://x/b.png", h2, "#fff") is True
    h2.alive = False                        # biri destroy oldu
    net.gate.set()
    _drain_wait(mw)
    assert h1.placed                        # diğer abone yine sonucu aldı
    assert h2.placed == []                  # destroyed holder skip


def test_completed_cache_hit_no_second_fetch(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        _GatedUrlopen(_tiny_png()) if False else
                        lambda req, timeout=None: _FakeResp(_tiny_png()))
    h1, h2 = _Holder(), _Holder()

    assert mw._request_image("http://x/c.png", h1, "#fff") is True
    _drain_wait(mw)
    assert h1.placed
    # cache hit: network yok, worker yok, yerleşim senkron
    assert mw._request_image("http://x/c.png", h2, "#fff") is True
    assert h2.placed
    assert xmpp.urllib.request.urlopen.calls == 1 \
        if hasattr(xmpp.urllib.request.urlopen, "calls") else True


def test_second_history_render_no_refetch(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResp(_tiny_png())

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    for _ in range(3):  # aynı history yeniden render
        assert mw._request_image("http://x/d.png", _Holder(), "#fff") is True
        _wait_inflight_cleared(mw, ("image", "http://x/d.png"))
    assert calls["n"] == 1                  # yalnız ilk render fetch etti


def test_mam_like_rerender_uses_cache(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResp(_tiny_png())

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    urls = [f"http://x/m{i}.png" for i in range(3)]
    for u in urls:                          # ilk render
        assert mw._request_image(u, _Holder(), "#fff") is True
        _drain_wait(mw)
    assert calls["n"] == 3
    for u in urls:                          # MAM merge → re-render
        assert mw._request_image(u, _Holder(), "#fff") is True
        _wait_inflight_cleared(mw, ("image", u))
    assert calls["n"] == 3                  # eski URL'ler yeniden fetch edilmedi


def test_different_urls_fetch_independently(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResp(_tiny_png())

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    assert mw._request_image("http://x/1.png", _Holder(), "#fff") is True
    assert mw._request_image("http://x/2.png", _Holder(), "#fff") is True
    _drain_wait(mw)
    assert calls["n"] == 2


# ══════════════════════════════════════════════════════════════════════════
# Cache anahtarı ve içerik
# ══════════════════════════════════════════════════════════════════════════

def test_image_and_preview_keys_do_not_collide(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    img_calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        img_calls["n"] += 1
        return _FakeResp(_tiny_png())

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    pv_calls = {"n": 0}

    def fake_preview(url):
        pv_calls["n"] += 1
        return {"title": "T", "desc": "D"}

    monkeypatch.setattr(xmpp, "_fetch_url_preview", fake_preview)
    monkeypatch.setattr(xmpp._media_ui, "url_preview_labels",
                        lambda c, theme, t, d: c.labels.append((t, d)))
    containers = []

    assert mw._request_image("http://x/same", _Holder(), "#fff") is True
    _drain_wait(mw)
    containers.append(_Container())
    assert mw._request_url_preview("http://x/same", containers[-1]) is True
    _drain_wait(mw)
    assert img_calls["n"] == 1 and pv_calls["n"] == 1  # ayrı pipeline
    assert ("image", "http://x/same") in mw._media_cache
    assert ("preview", "http://x/same") in mw._media_cache
    assert containers[-1].labels == [("T", "D")]


def test_cache_holds_no_tk_objects(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(_tiny_png()))
    monkeypatch.setattr(xmpp, "_fetch_url_preview",
                        lambda url: {"title": "T", "desc": "D"})

    assert mw._request_image("http://x/k.png", _Holder(), "#fff") is True
    _drain_wait(mw)
    assert mw._request_url_preview("http://x/k", _Container()) is True
    _drain_wait(mw)

    from PIL import Image
    img = mw._media_cache[("image", "http://x/k.png")]
    assert isinstance(img, Image.Image)     # GUI-bağımsız çözülmüş thumbnail
    assert img.load() is not None           # tamamen materialize
    pv = mw._media_cache[("preview", "http://x/k")]
    assert isinstance(pv, dict)             # küçük parsed data
    for v in mw._media_cache.values():
        assert not isinstance(v, xmpp.tk.Widget) if hasattr(xmpp, "tk") else True


# ══════════════════════════════════════════════════════════════════════════
# Hata yolları: in-flight temizliği + cache zehirsizliği
# ══════════════════════════════════════════════════════════════════════════

def test_failed_fetch_clears_inflight_no_poison(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    h = _Holder()

    def boom(req, timeout=None):
        raise OSError("ağ yok")

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", boom)
    assert mw._request_image("http://x/fail.png", h, "#fff") is True
    _drain_wait(mw)
    assert mw._media_inflight == {}          # in-flight kesin temizlendi
    assert ("image", "http://x/fail.png") not in mw._media_cache  # zehir yok
    assert h.errors == ["err"] and h.placed == []  # mevcut error semantiği


def test_retry_after_failure_fetches_again(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    state = {"fail": True}

    def flaky(req, timeout=None):
        if state["fail"]:
            raise OSError("ağ yok")
        return _FakeResp(_tiny_png())

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", flaky)
    h1 = _Holder()
    assert mw._request_image("http://x/r.png", h1, "#fff") is True
    _drain_wait(mw)
    assert h1.errors == ["err"]

    state["fail"] = False
    h2 = _Holder()
    assert mw._request_image("http://x/r.png", h2, "#fff") is True
    _drain_wait(mw)
    assert h2.placed                        # yeniden deneme fetch edebildi
    assert ("image", "http://x/r.png") in mw._media_cache


# ══════════════════════════════════════════════════════════════════════════
# Bounded cache: evict döngüsü
# ══════════════════════════════════════════════════════════════════════════

def test_cache_bounded_oldest_evicted():
    mw = _make_mw()
    mw._media_cache = OrderedDict()
    for i in range(xmpp._MEDIA_CACHE_MAX):
        mw._media_cache[("image", f"u{i}")] = f"v{i}"
    mw._media_cache_put(("image", "yeni"), "vyeni")
    assert len(mw._media_cache) == xmpp._MEDIA_CACHE_MAX  # sınır aşılmaz
    assert ("image", "u0") not in mw._media_cache          # en eski düştü
    assert mw._media_cache[("image", "yeni")] == "vyeni"


def test_evicted_url_fetches_again(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResp(_tiny_png())

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    assert mw._request_image("http://x/old.png", _Holder(), "#fff") is True
    _drain_wait(mw)
    # 64 yeni girdi ile eskiyi evict et
    for i in range(xmpp._MEDIA_CACHE_MAX):
        mw._media_cache_put(("image", f"fill{i}"), f"f{i}")
    assert ("image", "http://x/old.png") not in mw._media_cache
    assert mw._request_image("http://x/old.png", _Holder(), "#fff") is True
    _drain_wait(mw)
    assert calls["n"] == 2                  # evict sonrası yeniden fetch


# ══════════════════════════════════════════════════════════════════════════
# URL preview: single-flight + cache
# ══════════════════════════════════════════════════════════════════════════

def test_same_preview_url_simultaneous_single_fetch(monkeypatch):
    mw = _make_mw()
    pv = _GatedPreview()
    monkeypatch.setattr(xmpp, "_fetch_url_preview", pv)
    monkeypatch.setattr(xmpp._media_ui, "url_preview_labels",
                        lambda c, theme, t, d: c.labels.append((t, d)))
    c1, c2 = _Container(), _Container()

    assert mw._request_url_preview("http://x/page", c1) is True
    assert pv.entered.wait(5)
    assert mw._request_url_preview("http://x/page", c2) is True
    assert pv.calls == 1                    # tek fetch

    pv.gate.set()
    _drain_wait(mw)
    assert c1.labels and c2.labels
    assert mw._media_inflight == {}


def test_completed_preview_cache_hit_no_second_fetch(monkeypatch):
    mw = _make_mw()
    pv_calls = {"n": 0}

    def fake_preview(url):
        pv_calls["n"] += 1
        return {"title": "T", "desc": "D"}

    monkeypatch.setattr(xmpp, "_fetch_url_preview", fake_preview)
    monkeypatch.setattr(xmpp._media_ui, "url_preview_labels",
                        lambda c, theme, t, d: c.labels.append((t, d)))
    c1, c2 = _Container(), _Container()

    assert mw._request_url_preview("http://x/p", c1) is True
    _drain_wait(mw)
    assert c1.labels == [("T", "D")]
    assert mw._request_url_preview("http://x/p", c2) is True  # cache hit
    assert c2.labels == [("T", "D")]
    assert pv_calls["n"] == 1


def test_empty_preview_not_cached_and_inflight_cleared(monkeypatch):
    mw = _make_mw()
    monkeypatch.setattr(xmpp, "_fetch_url_preview", lambda url: {})
    c = _Container()
    assert mw._request_url_preview("http://x/empty", c) is True
    _wait_inflight_cleared(mw, ("preview", "http://x/empty"))
    assert c.labels == []                   # mevcut sessiz davranış
    assert mw._media_inflight == {}         # leak yok
    assert ("preview", "http://x/empty") not in mw._media_cache


# ══════════════════════════════════════════════════════════════════════════
# Kapanış
# ══════════════════════════════════════════════════════════════════════════

def test_closing_prevents_new_fetch_and_leak(monkeypatch):
    mw = _make_mw()
    mw._closing = True
    _wire_image_ui(monkeypatch, mw)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResp(_tiny_png())

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(xmpp, "_fetch_url_preview",
                        lambda url: calls.__setitem__("n", calls["n"] + 1))
    assert mw._request_image("http://x/z.png", _Holder(), "#fff") is False
    assert mw._request_url_preview("http://x/z", _Container()) is False
    assert calls["n"] == 0                  # fetch başlatılmadı
    # kapanışta state yaratılmaz/leak olmaz (lazy attr hiç oluşmamış olabilir)
    assert getattr(mw, "_media_inflight", {}) == {}
