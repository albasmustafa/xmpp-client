"""Security Hotfix 2C — audio single-flight + tempfile sahipliği.

Kapsam:
- aynı audio URL için tek worker/fetch/tempfile/ffmpeg (in-flight abonelik),
- weakref aboneler: GC/destroy edilen holder diğer aboneleri etkilemez,
- 2A dispatcher sözleşmesi (tek slot, saturasyon, start-failure),
- ffmpeg başarı/hata tempfile sahipliği (dönüştürülen WAV tescilli,
  original gereksizse silinir, kısmi artefakt birakılmaz),
- `_closing` davranışı, aynı mesaj içi dedupe korunumu,
- AMP-2 kalıntısı: tamamlanan audio cache'i YOKTUR (re-render yeniden
  fetch eder) — bilinçli olarak böyle belgelenir.

Deterministik: gerçek ağ/ffmpeg yok, flaky sleep yok.
"""
import gc
import os
import queue
import subprocess
import threading
import time
import types
import weakref

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


class _Holder:
    def __init__(self, alive=True):
        self.alive = alive
        self.placed = []
        self.errors = []

    def winfo_exists(self):
        return self.alive


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


def _wait_inflight_cleared(mw, url, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if url not in mw._audio_inflight:
            _drain(mw)
            return True
        time.sleep(0.005)
    _drain(mw)
    return False


def _spy_temp_registry(mw):
    """_remember_temp çağrılarını kaydet, gerçek tescili de yap."""
    registered = []
    orig = mw._remember_temp

    def spy(path):
        registered.append(path)
        return orig(path)   # 2C+: boolean sahiplik sözleşmesi korunur

    mw._remember_temp = spy
    return registered


def _fake_ffmpeg(monkeypatch, *, succeed=True, create_partial=False):
    """subprocess.run'ı sahte ffmpeg ile değiştir (gerçek ffmpeg yok)."""
    calls = {"n": 0}

    def fake_run(cmd, capture_output=None, timeout=None):
        calls["n"] += 1
        out = cmd[-1]
        if succeed or create_partial:
            with open(out, "wb") as f:
                f.write(b"RIFFfake-converted" if succeed else b"partial")
        return types.SimpleNamespace(returncode=0 if succeed else 1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


# ══════════════════════════════════════════════════════════════════════════
# Single-flight + abone dağıtımı
# ══════════════════════════════════════════════════════════════════════════

def test_same_audio_url_simultaneous_single_fetch(monkeypatch):
    mw = _make_mw()
    net = _GatedUrlopen(b"WAVEFAKE")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h1, h2 = _Holder(), _Holder()

    assert mw._request_audio("http://x/a.wav", h1, "#fff") is True
    assert net.entered.wait(5)
    assert "http://x/a.wav" in mw._audio_inflight
    assert mw._request_audio("http://x/a.wav", h2, "#fff") is True
    assert net.calls == 1                      # tek fetch

    net.gate.set()
    _drain_wait(mw)
    assert len(h1.placed) == 1 and len(h2.placed) == 1
    assert h1.placed[0] == h2.placed[0]        # aynı oynatılabilir yol
    assert mw._audio_inflight == {}            # kayıt çözüldü


def test_second_subscriber_consumes_no_extra_slot(monkeypatch):
    mw = _make_mw()
    mw._media_slots = threading.BoundedSemaphore(1)  # tek slot
    net = _GatedUrlopen(b"WAVEFAKE")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h1, h2 = _Holder(), _Holder()

    assert mw._request_audio("http://x/b.wav", h1, "#fff") is True
    assert net.entered.wait(5)                 # slot worker'da
    assert mw._request_audio("http://x/b.wav", h2, "#fff") is True
    net.gate.set()
    _drain_wait(mw)
    # Slot hiç iade edilmediği halde iki abone de yerleşti → ekstra slot
    # talebi olmadığını kanıtlar (deneseydi saturasyon fallback'e düşerdi).
    assert h1.placed and h2.placed
    assert all(not h.errors for h in (h1, h2))


def test_holder_gc_while_inflight_does_not_leak_or_break(monkeypatch):
    mw = _make_mw()
    net = _GatedUrlopen(b"WAVEFAKE")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h1, h2 = _Holder(), _Holder()

    assert mw._request_audio("http://x/c.wav", h1, "#fff") is True
    assert mw._request_audio("http://x/c.wav", h2, "#fff") is True
    wr = weakref.ref(h1)
    del h1
    gc.collect()
    assert wr() is None                        # weakref holder'ı tutmuyor
    net.gate.set()
    _drain_wait(mw)
    assert h2.placed                           # hayatta kalan etkilenmedi


def test_destroyed_holder_skipped_other_succeeds(monkeypatch):
    mw = _make_mw()
    net = _GatedUrlopen(b"WAVEFAKE")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h1, h2 = _Holder(), _Holder(alive=False)

    assert mw._request_audio("http://x/d.wav", h1, "#fff") is True
    assert mw._request_audio("http://x/d.wav", h2, "#fff") is True
    net.gate.set()
    _drain_wait(mw)
    assert h1.placed and h2.placed == []       # destroyed skip, diğer başarılı


# ══════════════════════════════════════════════════════════════════════════
# Hata / retry / saturasyon / start-failure / closing
# ══════════════════════════════════════════════════════════════════════════

def test_network_failure_clears_inflight_and_allows_retry(monkeypatch):
    mw = _make_mw()
    state = {"fail": True}

    def flaky(req, timeout=None):
        if state["fail"]:
            raise OSError("ağ yok")
        return _FakeResp(b"WAVEFAKE")

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(xmpp._audio_ui, "fallback_link",
                        lambda holder, theme, bg, url, cb:
                        holder.errors.append("err"))
    h1 = _Holder()
    assert mw._request_audio("http://x/f.wav", h1, "#fff") is True
    _drain_wait(mw)
    assert mw._audio_inflight == {}            # in-flight temiz
    assert h1.errors == ["err"] and h1.placed == []  # mevcut fallback

    state["fail"] = False
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h2 = _Holder()
    assert mw._request_audio("http://x/f.wav", h2, "#fff") is True  # retry
    _drain_wait(mw)
    assert h2.placed


def test_dispatcher_saturation_clears_inflight_and_falls_back(monkeypatch):
    mw = _make_mw()
    mw._media_slots = threading.BoundedSemaphore(1)
    assert mw._media_slots.acquire(blocking=False)  # slotu işgal et
    fallbacks = []
    monkeypatch.setattr(xmpp._audio_ui, "fallback_link",
                        lambda holder, theme, bg, url, cb: fallbacks.append(url))
    h = _Holder()
    assert mw._request_audio("http://x/s.wav", h, "#fff") is False
    assert "http://x/s.wav" not in mw._audio_inflight  # in-flight temiz
    assert fallbacks == ["http://x/s.wav"]              # mevcut degrade


def test_thread_start_failure_clears_inflight_no_slot_leak(monkeypatch):
    mw = _make_mw()
    degraded = []

    class _Broken:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("start patladı")

    monkeypatch.setattr(xmpp.threading, "Thread", _Broken)
    assert mw._request_audio("http://x/t.wav", _Holder(), "#fff") is False
    assert degraded == []  # on_saturated çağrılır (aşağıda) — önce temizlik:
    # slot sızmadı:
    assert mw._media_slots.acquire(blocking=False)
    mw._media_slots.release()
    assert mw._audio_inflight == {}


def test_thread_start_failure_runs_degrade(monkeypatch):
    mw = _make_mw()
    fallbacks = []
    monkeypatch.setattr(xmpp._audio_ui, "fallback_link",
                        lambda holder, theme, bg, url, cb: fallbacks.append(url))

    class _Broken:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("start patladı")

    monkeypatch.setattr(xmpp.threading, "Thread", _Broken)
    mw._request_audio("http://x/t2.wav", _Holder(), "#fff")
    assert fallbacks == ["http://x/t2.wav"]


def test_closing_prevents_new_audio_fetch(monkeypatch):
    mw = _make_mw()
    mw._closing = True
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResp(b"WAVEFAKE")

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    assert mw._request_audio("http://x/z.wav", _Holder(), "#fff") is False
    assert calls["n"] == 0
    assert getattr(mw, "_audio_inflight", {}) == {}


def test_completion_after_closing_no_stale_ui_clean_ownership(monkeypatch):
    mw = _make_mw()
    net = _GatedUrlopen(b"WAVEFAKE")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    registered = _spy_temp_registry(mw)
    h = _Holder()

    assert mw._request_audio("http://x/late.wav", h, "#fff") is True
    assert net.entered.wait(5)
    mw._closing = True                         # fetch uçuştayken kapanış
    net.gate.set()
    assert _wait_inflight_cleared(mw, "http://x/late.wav")  # worker bitti
    time.sleep(0.05)
    _drain(mw)                                 # olay gelmemeli (kapanış)
    assert h.placed == []                      # bayat UI mutasyonu yok
    assert "http://x/late.wav" not in mw._audio_inflight  # kayıt çözüldü
    assert len(registered) == 1 and os.path.exists(registered[0])
    assert registered[0] in mw._temp_files     # sahiplik temiz


# ══════════════════════════════════════════════════════════════════════════
# Tempfile sahipliği (ffmpeg başarı/hata)
# ══════════════════════════════════════════════════════════════════════════

def test_ffmpeg_success_converted_registered_original_removed(monkeypatch):
    mw = _make_mw()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"oggdata"))
    registered = _spy_temp_registry(mw)
    _fake_ffmpeg(monkeypatch, succeed=True)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h = _Holder()

    assert mw._request_audio("http://x/v.ogg", h, "#fff") is True
    _drain_wait(mw)
    assert len(registered) == 2                # original + dönüştürülen
    original, converted = registered
    assert converted.endswith(".wav")
    assert converted in mw._temp_files         # çıktı tescilli (test 7)
    assert original not in mw._temp_files      # kayıt gerçeği yansıtıyor
    assert not os.path.exists(original)        # original silindi (test 8)
    assert os.path.exists(converted)           # oynatılabilir artefakt duruyor
    assert h.placed == [converted]             # aboneye dönüştürülen gitti
    os.unlink(converted)


def test_ffmpeg_failure_no_orphan_converted_original_kept(monkeypatch):
    mw = _make_mw()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"oggdata"))
    registered = _spy_temp_registry(mw)
    _fake_ffmpeg(monkeypatch, succeed=False, create_partial=True)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h = _Holder()

    assert mw._request_audio("http://x/v2.ogg", h, "#fff") is True
    _drain_wait(mw)
    assert len(registered) == 1                # yalnız original tescilli
    original = registered[0]
    assert original in mw._temp_files and os.path.exists(original)
    assert h.placed == [original]              # mevcut davranış: original yerleşir
    partial = original + ".wav"
    assert not os.path.exists(partial)         # kısmi artefakt orphan bırakılmadı


def test_ffmpeg_exception_no_orphan_original_kept(monkeypatch):
    mw = _make_mw()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"oggdata"))
    registered = _spy_temp_registry(mw)

    def boom(cmd, capture_output=None, timeout=None):
        raise RuntimeError("ffmpeg yok")

    monkeypatch.setattr(subprocess, "run", boom)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h = _Holder()
    assert mw._request_audio("http://x/v3.ogg", h, "#fff") is True
    _drain_wait(mw)
    assert len(registered) == 1 and os.path.exists(registered[0])
    assert registered[0] in mw._temp_files
    assert not os.path.exists(registered[0] + ".wav")
    assert h.placed == [registered[0]]


# ══════════════════════════════════════════════════════════════════════════
# Sözleşme korumaları
# ══════════════════════════════════════════════════════════════════════════

def test_same_message_audio_dedupe_intact(monkeypatch):
    mw = _make_mw()
    placeholders = []
    monkeypatch.setattr(xmpp._audio_ui, "audio_placeholder",
                        lambda parent, theme, bg:
                        (placeholders.append(1), _Holder())[1])
    monkeypatch.setattr(xmpp._render, "render_base_message",
                        lambda *a, **k: types.SimpleNamespace(
                            row=types.SimpleNamespace(
                                bind=lambda *a2, **k2: None,
                                winfo_children=lambda: []),
                            bubble=None, colors={"bubble_bg": "#fff"},
                            body_kind=None, body_widget=None))
    monkeypatch.setattr(xmpp._render, "render_meta_row", lambda *a, **k: None)
    monkeypatch.setattr(xmpp._render, "render_date_separator",
                        lambda *a, **k: None)
    targets = []

    class _T:
        def __init__(self, target=None, daemon=None):
            targets.append(target)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    mw.active = "a@b"
    mw.msg_frame = types.SimpleNamespace(winfo_children=lambda: [])
    mw._bubble_widgets = []
    mw._photo_refs = []
    mw._avatars = {}
    mw._last_date_label = ""
    mw._prune_photo_refs = lambda: None
    mw._bind_scroll_widget = lambda *a: None
    mw._bind_message_menu = lambda *a, **k: None
    xmpp.MainWindow._last_sender = None

    mw._append("dinle http://x/a.ogg ve http://x/a.ogg", "them", sender="Ali")
    assert len(placeholders) == 1              # aynı mesaj içi dedupe duruyor
    assert len(targets) == 1                   # tek worker


def test_no_audio_entry_in_completed_media_cache(monkeypatch):
    mw = _make_mw()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"WAVEFAKE"))
    h = _Holder()
    assert mw._request_audio("http://x/nocache.wav", h, "#fff") is True
    _drain_wait(mw)
    cache = getattr(mw, "_media_cache", {})
    assert ("audio", "http://x/nocache.wav") not in cache
    assert all(k[0] in ("image", "preview") for k in cache)


def test_audio_history_rerender_still_refetches_amp2_residual(monkeypatch):
    """AMP-2 kalıntısı BİLİNÇLİDİR: tamamlanan audio cache'i yoktur; aynı
    URL history yeniden render'ında yeniden fetch edilir."""
    mw = _make_mw()
    net = _GatedUrlopen(b"WAVEFAKE")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h1, h2 = _Holder(), _Holder()

    assert mw._request_audio("http://x/re.wav", h1, "#fff") is True
    net.gate.set()
    _drain_wait(mw)
    assert h1.placed
    # history re-render: aynı URL tekrar istenir → YENİDEN fetch edilir
    assert mw._request_audio("http://x/re.wav", h2, "#fff") is True
    assert net.calls == 2                      # cache yok (kasıtlı)
    net.gate.set()
    _drain_wait(mw)
    assert h2.placed
