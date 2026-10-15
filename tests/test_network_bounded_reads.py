"""Security Hotfix 1 — sınırlı ağ okuması regression testleri.

Kapsam:
- `_read_bounded` helper sözleşmesi (limit altı/eşit/üstü, Content-Length
  erken red, bozuk/eksik başlıkta bounded-read fallback),
- doğrulanmış sınırsız `resp.read()` call-site'larının limit davranışı
  (inline/fullscreen image, audio, GIF thumb, oda arama JSON, Tenor JSON),
- `_fetch_url_preview` mevcut 16 KB cap'inin korunumu.

Testler gerçek Tk ve gerçek ağ gerektirmez: `urlopen` monkeypatch edilir,
GUI teslimi `_safe_after`'ın worker-thread kuyruk yolu üzerinden boşaltılır.
MainWindow `object.__new__` ile Tk'sız kurulur (mevcut test geleneği).
"""
import io
import json
import os
import queue
import threading
import time

import pytest

import xmpp

# ══════════════════════════════════════════════════════════════════════════
# Yardımcılar
# ══════════════════════════════════════════════════════════════════════════

class FakeResponse:
    """urlopen sözleşmesini taklit eden yanıt.

    read(n) gerçek HTTP gibi EN FAZLA n byte döndürür; okunan adet ve
    boyutlar test assertions'ı için kaydedilir.
    """

    def __init__(self, payload=b"", headers=None):
        self._payload = payload
        self._pos = 0
        self.headers = dict(headers or {})
        self.read_calls = []

    def read(self, n=-1):
        self.read_calls.append(n)
        if n is None or n < 0:
            n = len(self._payload) - self._pos
        chunk = self._payload[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _tiny_png() -> bytes:
    """Geçerli 2x2 PNG üret (PIL ile; sabit byte gömmeye gerek yok)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (200, 10, 10)).save(buf, format="PNG")
    return buf.getvalue()


def _make_mw():
    """Tk'sız MainWindow iskeleti (yalnız bu turun ihtiyaçları)."""
    mw = object.__new__(xmpp.MainWindow)
    mw._closing = False
    mw.gui_q = queue.Queue()
    mw._photo_refs = []
    mw._temp_files = []
    mw.root = type("R", (), {"after": lambda self, ms, fn, *a: None})()
    return mw


def _drain(mw):
    """_safe_after kuyruğundaki __ui__ olaylarını çalıştır."""
    ran = []
    while True:
        try:
            kind, data = mw.gui_q.get_nowait()
        except queue.Empty:
            return ran
        assert kind == "__ui__", f"beklenmeyen olay: {kind}"
        fn, args = data
        fn(*args)
        ran.append(fn)


def _drain_wait(mw, timeout=5.0):
    """Worker thread olaylarını bekle; süre dolarsa gelenleri döndür."""
    deadline = time.time() + timeout
    ran = []
    while time.time() < deadline:
        ran.extend(_drain(mw))
        if ran:
            time.sleep(0.02)
            ran.extend(_drain(mw))  # zincirleme teslimler için
            return ran
        time.sleep(0.01)
    return ran


def _run_bg(fn, *args):
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()
    t.join(30)
    assert not t.is_alive(), "worker thread askıda kaldı"


class _Holder:
    """winfo_exists() True dönen sahte widget."""

    def winfo_exists(self):
        return True


class _Label:
    def config(self, *a, **k):
        pass


# ══════════════════════════════════════════════════════════════════════════
# _read_bounded helper sözleşmesi
# ══════════════════════════════════════════════════════════════════════════

def test_below_limit_success():
    resp = FakeResponse(b"x" * 100)
    assert xmpp._read_bounded(resp, 1000) == b"x" * 100
    assert resp.read_calls == [1001]  # enforcement read(max+1)


def test_exact_limit_success():
    resp = FakeResponse(b"y" * 1024)
    assert xmpp._read_bounded(resp, 1024) == b"y" * 1024


def test_limit_plus_one_raises_and_is_bounded():
    resp = FakeResponse(b"z" * 1025)
    with pytest.raises(ValueError, match="exceeds size limit"):
        xmpp._read_bounded(resp, 1024)
    # Sınırsız akışta bile soketten en fazla max+1 byte çekilmiş olmalı
    assert resp.read_calls == [1025]


def test_content_length_over_limit_early_reject():
    resp = FakeResponse(b"", headers={"Content-Length": str(10 * 1024 * 1024)})
    with pytest.raises(ValueError, match="exceeds size limit"):
        xmpp._read_bounded(resp, 1024)
    assert resp.read_calls == []  # hiç okumadan reddedildi


def test_content_length_equal_limit_ok():
    resp = FakeResponse(b"a" * 1024, headers={"Content-Length": "1024"})
    assert xmpp._read_bounded(resp, 1024) == b"a" * 1024


def test_invalid_content_length_falls_back_to_bounded_read():
    resp = FakeResponse(b"b" * 512, headers={"Content-Length": "abc"})
    assert xmpp._read_bounded(resp, 1024) == b"b" * 512


def test_missing_content_length_still_bounded():
    resp = FakeResponse(b"c" * 1025)
    with pytest.raises(ValueError, match="exceeds size limit"):
        xmpp._read_bounded(resp, 1024)


# ══════════════════════════════════════════════════════════════════════════
# Call-site davranışları
# ══════════════════════════════════════════════════════════════════════════

def test_inline_image_oversized_no_placement(monkeypatch):
    mw = _make_mw()
    placed, errors = [], []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(b"\xff" * (xmpp._NET_IMG_MAX + 1)))
    monkeypatch.setattr(xmpp._media_ui, "image_error",
                        lambda holder, theme: errors.append(holder))
    mw._place_image = lambda holder, img, bg, url: placed.append(url)

    # Hotfix 2B: istek cache/single-flight girişinden geçer
    assert mw._request_image("http://evil/huge.png", _Holder(), "#fff") is True
    ran = _drain_wait(mw)
    assert placed == []                      # resim yerleştirilmedi
    assert errors and ran                    # mevcut error yolu çalıştı
    assert mw._media_inflight == {}          # in-flight temizlendi
    assert ("image", "http://evil/huge.png") not in mw._media_cache  # zehirsiz


def test_inline_image_normal_places(monkeypatch):
    mw = _make_mw()
    placed = []
    png = _tiny_png()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(png))
    mw._place_image = lambda holder, img, bg, url: placed.append(url)

    assert mw._request_image("http://ok/ok.png", _Holder(), "#fff") is True
    _drain_wait(mw)
    assert placed == ["http://ok/ok.png"]    # normal resim regreyonu yok
    assert len(mw._media_cache) == 1         # sonuç cache'e girdi


def test_fullscreen_oversized_no_photo_placement(monkeypatch):
    mw = _make_mw()
    photos, errors = [], []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(b"\xff" * (xmpp._NET_IMG_FULL_MAX + 1)))
    monkeypatch.setattr(xmpp._media_ui, "fullscreen_window",
                        lambda root, theme, on_open: (object(), _Holder()))
    monkeypatch.setattr(xmpp._media_ui, "image_error",
                        lambda holder, theme: errors.append(holder))
    monkeypatch.setattr(xmpp._media_ui, "place_photo",
                        lambda w, photo: photos.append(photo))

    _run_bg(mw._show_image_fullscreen, object(), "http://evil/full.png")
    _drain_wait(mw)
    assert photos == [] and mw._photo_refs == []
    assert errors                            # error etiketi yolu korundu


def test_fullscreen_normal_places_photo(monkeypatch):
    mw = _make_mw()
    photos = []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(_tiny_png()))
    monkeypatch.setattr(xmpp._media_ui, "fullscreen_window",
                        lambda root, theme, on_open: (object(), _Holder()))
    monkeypatch.setattr(xmpp._media_ui, "place_photo",
                        lambda w, photo: photos.append(photo))
    monkeypatch.setattr(xmpp.ImageTk, "PhotoImage", lambda img: ("photo", img))

    _run_bg(mw._show_image_fullscreen, object(), "http://ok/full.png")
    _drain_wait(mw)
    assert len(photos) == 1 and len(mw._photo_refs) == 1  # GC koruması yerinde


def test_audio_oversized_fallback_no_tempfile(monkeypatch):
    mw = _make_mw()
    fallbacks, placed, temps = [], [], []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(b"\xff" * (xmpp._NET_AUDIO_MAX + 1)))
    mw._place_audio = lambda holder, path, bg, url: placed.append(path)
    mw._place_audio_fallback = lambda holder, url, bg: fallbacks.append(url)
    mw._remember_temp = lambda path: temps.append(path)

    # Hotfix 2C: istek audio single-flight girişinden geçer
    holder = _Holder()  # üretimde widget ağacı gibi güçlü sahip
    assert mw._request_audio("http://evil/huge.ogg", holder, "#fff") is True
    _drain_wait(mw)
    assert fallbacks and not placed          # mevcut fallback yolu
    assert temps == []                       # tempfile hiç oluşturulmadı/yazılmadı
    assert mw._audio_inflight == {}          # in-flight temizlendi


def test_audio_normal_roundtrip(monkeypatch):
    mw = _make_mw()
    placed = []
    payload = b"WAVEFAKE" * 100
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(payload))
    mw._place_audio = lambda holder, path, bg, url: placed.append(path)

    holder = _Holder()
    assert mw._request_audio("http://ok/ok.wav", holder, "#fff") is True
    _drain_wait(mw)
    assert len(placed) == 1
    with open(placed[0], "rb") as f:
        assert f.read() == payload           # içerik bozulmadan yazıldı
    assert placed[0] in mw._temp_files       # cleanup kaydı tutuluyor
    os.unlink(placed[0])


def test_gif_thumb_oversized_no_photo_ref(monkeypatch):
    mw = _make_mw()
    photos = []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(b"\xff" * (xmpp._NET_GIF_THUMB_MAX + 1)))
    monkeypatch.setattr(xmpp._media_ui, "place_photo",
                        lambda w, photo: photos.append(photo))

    _run_bg(mw._load_gif_thumb, "http://tenor/huge.gif", _Holder())
    time.sleep(0.2)                          # worker biter; olay üretmemeli
    _drain(mw)
    assert photos == [] and mw._photo_refs == []  # gereksiz ref büyümez


def test_gif_thumb_normal_places(monkeypatch):
    mw = _make_mw()
    photos = []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(_tiny_png()))
    monkeypatch.setattr(xmpp._media_ui, "place_photo",
                        lambda w, photo: photos.append(photo))
    monkeypatch.setattr(xmpp.ImageTk, "PhotoImage", lambda img: ("photo", img))

    _run_bg(mw._load_gif_thumb, "http://tenor/ok.gif", _Holder())
    _drain_wait(mw)
    assert len(photos) == 1 and len(mw._photo_refs) == 1


def test_rooms_json_oversized_error_path(monkeypatch):
    mw = _make_mw()
    done, err = [], []
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(b"{" * (xmpp._NET_JSON_MAX + 1)))
    mw._search_rooms_requested("test", lambda items: done.append(items),
                               lambda msg: err.append(msg))
    ran = _drain_wait(mw)
    assert done == [] and err                # mevcut on_error yolu
    assert ran


def test_rooms_json_normal_done(monkeypatch):
    mw = _make_mw()
    done, err = [], []
    payload = json.dumps({"items": [
        {"address": "room@conf", "name": "Oda", "nusers": 3},
        {"name": "adresisiz"},                   # filtrelenir
    ]}).encode()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(payload))
    mw._search_rooms_requested("oda", lambda items: done.append(items),
                               lambda msg: err.append(msg))
    _drain_wait(mw)
    assert err == [] and len(done) == 1 and len(done[0]) == 1


def test_gif_search_oversized_error_status(monkeypatch):
    mw = _make_mw()
    shown, status = [], []

    class _Status:
        def config(self, *a, **k):
            status.append(k.get("text", ""))

    class _Grid:
        def winfo_children(self):
            return []

    monkeypatch.setattr(xmpp, "_load_config", lambda: {"gif_api_key": "K"})
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(b"{" * (xmpp._NET_JSON_MAX + 1)))
    mw._show_gif_results = lambda results, grid, lbl: shown.append(results)
    mw._gif_search("cats", _Grid(), _Status())
    _drain_wait(mw)
    assert shown == [] and any(t.startswith("Hata:") for t in status)


def test_gif_search_normal_parses(monkeypatch):
    mw = _make_mw()
    shown, status = [], []

    class _Status:
        def config(self, *a, **k):
            status.append(k.get("text", ""))

    class _Grid:
        def winfo_children(self):
            return []

    payload = json.dumps({"results": [
        {"media_formats": {"tinygif": {"url": "http://t/tiny.gif"},
                           "gif": {"url": "http://t/full.gif"}}}]}).encode()
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"gif_api_key": "K"})
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(payload))
    mw._show_gif_results = lambda results, grid, lbl: shown.append(results)
    mw._gif_search("cats", _Grid(), _Status())
    _drain_wait(mw)
    assert len(shown) == 1 and shown[0][0]["url"] == "http://t/full.gif"
    assert not any(t.startswith("Hata:") for t in status)


def test_url_preview_16k_cap_preserved(monkeypatch):
    read_caps = []

    class _Resp(FakeResponse):
        def read(self, n=-1):
            read_caps.append(n)
            return super().read(n)

    html = (b"<html><head><title>Beni gor</title>"
            b"<meta name='description' content='aciklama'>"
            + b"<!-- filler -->" * 2000 + b"</head></html>")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp(html, {"Content-Type": "text/html"}))
    info = xmpp._fetch_url_preview("http://ok/page.html")
    assert read_caps == [16384]              # mevcut 16 KB cap değişmedi
    assert info["title"] == "Beni gor" and info["desc"] == "aciklama"
