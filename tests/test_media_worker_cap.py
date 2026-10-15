"""Security Hotfix 2A — bounded media worker concurrency regression testleri.

Kapsam:
- `_dispatch_media_worker` sözleşmesi (cap, non-blocking acquire, slot
  iadesi, start-failure slot leak'i, `_closing` guard),
- saturasyon degrade yolları (`_saturate_image_holder`,
  `_saturate_audio_holder`),
- normal image/audio/URL-preview yollarının dispatcher üzerinden
  çalışmaya devam etmesi,
- DeepSeek AMP-1 probe'u senaryosu: 42 URL'lik fan-out cap'i aşamaz.

Testler gerçek ağ ve sleep-tabanlı flaky senkronizasyon kullanmaz;
deterministic Event/gate + manuel semaphore dolumu ile çalışır.
MainWindow `object.__new__` ile Tk'sız kurulur (mevcut test geleneği).
"""
import queue
import threading
import time

import xmpp

CAP = xmpp._MEDIA_WORKER_CAP


# ══════════════════════════════════════════════════════════════════════════
# Yardımcılar
# ══════════════════════════════════════════════════════════════════════════

def _make_mw(cap=None):
    mw = object.__new__(xmpp.MainWindow)
    mw._closing = False
    mw.gui_q = queue.Queue()
    mw._photo_refs = []
    mw._temp_files = []
    if cap is not None:
        mw._media_slots = threading.BoundedSemaphore(cap)
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
            ran.extend(_drain(mw))
            return ran
        time.sleep(0.01)
    return ran


def _run_bg(fn, *args):
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()
    t.join(30)
    assert not t.is_alive(), "worker thread askıda kaldı"


def _tiny_png():
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (10, 200, 10)).save(buf, format="PNG")
    return buf.getvalue()


class _Holder:
    def winfo_exists(self):
        return True


class _FakeLabel:
    """config/bind kaydeden sahte placeholder etiketi."""

    def __init__(self):
        self.configs = []
        self.binds = {}

    def config(self, *a, **k):
        self.configs.append(k)

    def bind(self, seq, fn, add=False):
        self.binds[seq] = self.binds.get(seq, []) + [fn]


def _wait_slot(mw, timeout=5.0):
    """Bir slotun serbest kalmasını bekle; geldi mi döndür."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mw._media_slots.acquire(blocking=False):
            return True
        time.sleep(0.01)
    return False


# ══════════════════════════════════════════════════════════════════════════
# Dispatcher sözleşmesi
# ══════════════════════════════════════════════════════════════════════════

def test_concurrency_never_exceeds_cap():
    mw = _make_mw(cap=4)
    lock = threading.Lock()
    state = {"n": 0, "max": 0}
    all_entered = threading.Event()
    all_done = threading.Event()

    def body():
        with lock:
            state["n"] += 1
            state["max"] = max(state["max"], state["n"])
            if state["n"] == 4:
                all_entered.set()
        all_entered.wait(10)
        with lock:
            state["n"] -= 1
            if state["n"] == 0:
                all_done.set()

    for _ in range(4):
        assert mw._dispatch_media_worker(body) is True
    assert all_entered.wait(5)
    assert all_done.wait(5)
    with lock:
        assert state["max"] == 4  # cap'i hiç aşmadı


def test_no_extra_worker_when_full():
    mw = _make_mw(cap=2)
    started, degraded = [], []
    # İki slotu manuel doldur → üretimde koşan worker'ları temsil eder
    assert mw._media_slots.acquire(blocking=False)
    assert mw._media_slots.acquire(blocking=False)

    assert mw._dispatch_media_worker(lambda: started.append(1),
                                     on_saturated=lambda: degraded.append(1)
                                     ) is False
    assert started == []          # ekstra worker BAŞLAMADI
    assert degraded == [1]        # degrade adımı çağrıldı
    mw._media_slots.release()
    mw._media_slots.release()


def test_gui_thread_never_blocks_on_full_slots():
    mw = _make_mw(cap=1)
    assert mw._media_slots.acquire(blocking=False)  # tek slotu işgal et
    degraded = []
    result = {}

    def call():
        result["r"] = mw._dispatch_media_worker(
            lambda: None, on_saturated=lambda: degraded.append(1))

    t = threading.Thread(target=call, daemon=True)
    t.start()
    t.join(3)
    assert not t.is_alive(), "dispatcher GUI thread'ini blokladı"
    assert result.get("r") is False and degraded == [1]


def test_slot_returned_after_worker_completes():
    mw = _make_mw(cap=1)
    done = threading.Event()
    assert mw._dispatch_media_worker(done.set) is True
    assert done.wait(5)
    assert _wait_slot(mw), "worker bitmesine rağmen slot geri gelmedi"
    mw._media_slots.release()
    assert mw._dispatch_media_worker(lambda: None) is True


def test_slot_returned_after_worker_exception():
    mw = _make_mw(cap=1)

    def boom():
        raise RuntimeError("worker patladı")

    assert mw._dispatch_media_worker(boom) is True
    assert _wait_slot(mw), "worker exception sonrası slot geri gelmedi"
    mw._media_slots.release()


def test_no_slot_leak_when_thread_start_fails(monkeypatch):
    mw = _make_mw(cap=1)
    degraded = []

    class _Broken:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("start patladı")

    monkeypatch.setattr(xmpp.threading, "Thread", _Broken)
    assert mw._dispatch_media_worker(
        lambda: None, on_saturated=lambda: degraded.append(1)) is False
    assert degraded == [1]
    assert _wait_slot(mw), "Thread.start patladı ama slot sızdı"
    mw._media_slots.release()


def test_no_worker_when_closing():
    mw = _make_mw(cap=2)
    mw._closing = True
    started = []
    assert mw._dispatch_media_worker(lambda: started.append(1)) is False
    assert started == []
    # acquire bile yapılmadı: iki slot da yerinde
    assert mw._media_slots.acquire(blocking=False)
    mw._media_slots.release()


# ══════════════════════════════════════════════════════════════════════════
# Saturasyon degrade yolları
# ══════════════════════════════════════════════════════════════════════════

def test_saturated_image_holder_converts_to_link():
    mw = _make_mw()
    holder = _FakeLabel()
    mw._saturate_image_holder(holder, "http://x/big.png")
    assert holder.configs and holder.configs[0]["text"].startswith("🔗")
    assert holder.binds.get("<Button-1>")  # tıklanabilir bağlantı


def test_saturated_audio_holder_uses_fallback_link(monkeypatch):
    mw = _make_mw()
    calls = []
    monkeypatch.setattr(xmpp._audio_ui, "fallback_link",
                        lambda *a, **k: calls.append(a))
    mw._saturate_audio_holder(_FakeLabel(), "http://x/a.ogg", "#fff")
    assert len(calls) == 1


def test_dispatch_degrades_without_popup_on_saturation():
    mw = _make_mw(cap=1)
    assert mw._media_slots.acquire(blocking=False)
    degraded = []
    # on_saturated verilmediğinde sessizce False dönmeli (popup spam yok)
    assert mw._dispatch_media_worker(lambda: None) is False
    assert mw._dispatch_media_worker(
        lambda: None, on_saturated=lambda: degraded.append(1)) is False
    assert degraded == [1]
    mw._media_slots.release()


# ══════════════════════════════════════════════════════════════════════════
# Normal yollar dispatcher üzerinden çalışmaya devam eder
# ══════════════════════════════════════════════════════════════════════════

def test_normal_image_path_still_places(monkeypatch):
    mw = _make_mw()
    placed = []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(_tiny_png()))
    mw._place_image = lambda holder, img, bg, url: placed.append(url)

    assert mw._request_image("http://ok/a.png", _Holder(), "#fff") is True
    _drain_wait(mw)
    assert placed == ["http://ok/a.png"]


def test_normal_audio_path_still_places(monkeypatch):
    mw = _make_mw()
    placed = []
    payload = b"WAVEFAKE" * 50
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(payload))
    mw._place_audio = lambda holder, path, bg, url: placed.append(path)

    holder = _Holder()
    assert mw._request_audio("http://ok/a.wav", holder, "#fff") is True
    _drain_wait(mw)
    assert len(placed) == 1
    with open(placed[0], "rb") as f:
        assert f.read() == payload
    import os
    os.unlink(placed[0])


def test_normal_preview_path_still_runs(monkeypatch):
    mw = _make_mw()
    labels = []
    monkeypatch.setattr(xmpp, "_fetch_url_preview",
                        lambda url: {"title": "T", "desc": "D"})
    monkeypatch.setattr(xmpp._media_ui, "url_preview_labels",
                        lambda c, theme, title, desc: labels.append(title))
    mw._scroll_bottom = lambda: None

    assert mw._request_url_preview("http://ok/x", object()) is True
    _drain_wait(mw)
    assert labels == ["T"]


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


# ══════════════════════════════════════════════════════════════════════════
# AMP-1 probe senaryosu: 42 URL fan-out
# ══════════════════════════════════════════════════════════════════════════

def test_many_urls_fanout_never_exceeds_cap():
    mw = _make_mw()  # varsayılan cap
    release = threading.Event()
    lock = threading.Lock()
    state = {"n": 0, "max": 0}

    def body():
        with lock:
            state["n"] += 1
            state["max"] = max(state["max"], state["n"])
        release.wait(10)
        with lock:
            state["n"] -= 1

    started = degraded = 0
    for _ in range(42):  # 30 image + 10 audio + 2 preview denklemi
        if mw._dispatch_media_worker(body):
            started += 1
        else:
            degraded += 1
    assert started == CAP
    assert degraded == 42 - CAP

    release.set()
    deadline = time.time() + 10
    while time.time() < deadline:
        with lock:
            if state["n"] == 0:
                break
        time.sleep(0.01)
    with lock:
        assert state["n"] == 0
        assert state["max"] == CAP  # hiç cap aşımı olmadı

    # Tüm slotlar geri geldi
    for _ in range(CAP):
        assert mw._media_slots.acquire(blocking=False)
    for _ in range(CAP):
        mw._media_slots.release()
