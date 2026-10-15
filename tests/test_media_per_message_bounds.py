"""Resource Hardening 2E — mesaj başına zengin medya tavanları.

Kapsam:
- tek mesajda zengin görsel ≤ 6, zengin ses ≤ 3, önizleme ≤ 2,
- kota benzersiz URL'ye uygulanır (aynı URL tekrarı slot yemez),
- fazlası mevcut hafif bağlantı görünümüne gider (_request_* çağrılmaz),
- kota mesaj başınadır (history re-render'da paylaşılan bütçe yok),
- cache hit kota'yı bypass etmez; 2A/2B/2C değişmezleri korunur.

Deterministik: gerçek ağ yok; `_request_*` kayıt edici veya sahte
dispatcher ile çalışır.
"""
import os
import sys
import types
from collections import OrderedDict
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_chat_media import _append_window, _Capture  # noqa: E402

import xmpp  # noqa: E402

# ══════════════════════════════════════════════════════════════════════════
# Yardımcılar
# ══════════════════════════════════════════════════════════════════════════

class _FakeW:
    """tk.Frame/Label yerine geçen sahte widget (önizleme bloğu)."""

    def __init__(self, master=None, **kw):
        pass

    def pack(self, *a, **k):
        pass

    def bind(self, *a, **k):
        pass


def _bounds_mw(monkeypatch):
    """_append_window + medya sayaçları (zengin/istek/önizleme/taşan)."""
    mw = _append_window(monkeypatch)
    c = {"rich_img": [], "link_img": [], "rich_audio": [], "fb_audio": [],
         "req_img": [], "req_audio": [], "preview": [], "overflow": []}

    holders = []

    def fake_placeholder(parent, theme, bg):
        holder = SimpleNamespace(
            configs=[],
            config=lambda **k: holder.configs.append(k),
            bind=lambda *a, **k: None)
        holders.append(holder)
        c["rich_img"].append(bg)
        return holder

    mw._image_holders = holders
    monkeypatch.setattr(xmpp._media_ui, "image_placeholder", fake_placeholder)
    monkeypatch.setattr(xmpp._media_ui, "image_link",
                        lambda parent, theme, url, bg, cb:
                        c["link_img"].append(url))
    monkeypatch.setattr(xmpp._audio_ui, "audio_placeholder",
                        lambda parent, theme, bg: c["rich_audio"].append(bg))
    monkeypatch.setattr(xmpp._audio_ui, "fallback_link",
                        lambda parent, theme, bg, url, cb:
                        c["fb_audio"].append(url))
    mw._request_image = lambda url, holder, bg: c["req_img"].append(url)
    mw._request_audio = lambda url, holder, bg: c["req_audio"].append(url)
    mw._request_url_preview = lambda url, container: c["preview"].append(url)
    mw._add_media_overflow_control = (
        lambda bubble, kind, urls, bg:
        c["overflow"].append((kind, list(urls))))
    return mw, c


def _imgs(n, base="http://x/i"):
    return " ".join(f"{base}{i}.png" for i in range(n))


def _auds(n, base="http://x/a"):
    return " ".join(f"{base}{i}.ogg" for i in range(n))


# ══════════════════════════════════════════════════════════════════════════
# 1-2: 1000 benzersiz URL
# ══════════════════════════════════════════════════════════════════════════

def test_image_1000_distinct_bounded(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    mw._append(_imgs(1000), "them", sender="A")
    assert len(c["rich_img"]) == xmpp._MAX_INLINE_IMAGES      # ≤6 zengin
    assert len(c["req_img"]) == xmpp._MAX_INLINE_IMAGES       # ≤6 istek
    # URL başına bağlantı widget'ı YOK; tek taşan denetim 994 URL taşır:
    assert len(c["link_img"]) == 0
    assert len(c["overflow"]) == 1
    kind, urls = c["overflow"][0]
    assert kind == "image" and len(urls) == 994
    assert urls[0] == "http://x/i6.png" and urls[-1] == "http://x/i999.png"
    assert c["req_img"] == [f"http://x/i{i}.png" for i in range(6)]


def test_audio_1000_distinct_bounded(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    mw._append(_auds(1000), "them", sender="A")
    assert len(c["rich_audio"]) == xmpp._MAX_INLINE_AUDIO     # ≤3 zengin
    assert len(c["req_audio"]) == xmpp._MAX_INLINE_AUDIO      # ≤3 istek
    # fallback_link bubble ile HİÇ çağrılmaz (2E regresyonu); taşma tek
    # denetimde 997 URL ile taşınır:
    assert len(c["fb_audio"]) == 0
    assert len(c["overflow"]) == 1
    kind, urls = c["overflow"][0]
    assert kind == "audio" and len(urls) == 997
    assert urls[0] == "http://x/a3.ogg" and urls[-1] == "http://x/a999.ogg"
    assert c["req_audio"] == [f"http://x/a{i}.ogg" for i in range(3)]


# ══════════════════════════════════════════════════════════════════════════
# 3-4: aynı URL tekrarı — mevcut dedupe korunur
# ══════════════════════════════════════════════════════════════════════════

def test_same_image_url_repeated_dedupe(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    mw._append(" ".join(["http://x/same.png"] * 1000), "them", sender="A")
    assert len(c["rich_img"]) == 1
    assert len(c["req_img"]) == 1
    assert len(c["link_img"]) == 0
    assert c["overflow"] == []                 # taşan yok → denetim yok


def test_same_audio_url_repeated_dedupe(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    mw._append(" ".join(["http://x/same.ogg"] * 1000), "them", sender="A")
    assert len(c["rich_audio"]) == 1
    assert len(c["req_audio"]) == 1
    assert len(c["fb_audio"]) == 0
    assert c["overflow"] == []


# ══════════════════════════════════════════════════════════════════════════
# 5: karışık mesaj — tüm URL'ler erişilebilir kalır
# ══════════════════════════════════════════════════════════════════════════

def test_mixed_message_bounded_and_accessible(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    imgs = [f"http://x/m{i}.png" for i in range(20)]
    auds = [f"http://x/m{i}.ogg" for i in range(20)]
    mw._append(" ".join(imgs + auds), "them", sender="A")
    assert len(c["rich_img"]) == 6
    assert len(c["rich_audio"]) == 3
    assert len(c["link_img"]) == 0 and len(c["fb_audio"]) == 0
    assert [(k, len(u)) for k, u in c["overflow"]] == [("image", 14),
                                                       ("audio", 17)]
    overflow_urls = set(c["overflow"][0][1]) | set(c["overflow"][1][1])
    assert overflow_urls == set(imgs[6:]) | set(auds[3:])  # hiçbiri gizlenmedi
    assert set(c["req_img"]) == set(imgs[:6])
    assert set(c["req_audio"]) == set(auds[:3])


# ══════════════════════════════════════════════════════════════════════════
# 6: önizleme tavanı aynen kalır
# ══════════════════════════════════════════════════════════════════════════

def test_preview_cap_remains_exactly_2(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    monkeypatch.setattr(xmpp.tk, "Frame", _FakeW)
    monkeypatch.setattr(xmpp.tk, "Label", _FakeW)
    mw._append("bak http://x/p1 http://x/p2 http://x/p3 http://x/p4 "
               "http://x/p5", "them", sender="A")
    assert len(c["preview"]) == 2              # mevcut [:2] davranışı


# ══════════════════════════════════════════════════════════════════════════
# 7-8: kota mesaj başınadır; history re-render paylaşılan bütçe paylaşmaz
# ══════════════════════════════════════════════════════════════════════════

def test_quota_is_per_message_fresh_budget(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    mw._append(_imgs(8, "http://x/m1-"), "them", sender="A")
    assert len(c["rich_img"]) == 6 and len(c["overflow"]) == 1
    mw._append(_imgs(8, "http://x/m2-"), "them", sender="A")
    assert len(c["rich_img"]) == 12            # yeni mesaj → yeni 6'lık bütçe
    assert len(c["overflow"]) == 2             # her mesajın kendi taşması


def test_history_rerender_each_message_bounded(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    msgs = [_imgs(10, f"http://x/h{i}-") for i in range(5)]
    for m in msgs:                             # history re-render benzeri
        mw._append(m, "them", sender="A")
    assert len(c["rich_img"]) == 5 * 6         # mesaj başına 6, global bütçe yok
    assert len(c["overflow"]) == 5             # mesaj başına tek taşan denetim
    for i in range(5):
        assert c["req_img"].count(f"http://x/h{i}-0.png") == 1


# ══════════════════════════════════════════════════════════════════════════
# 2E follow-up regresyon: taşma sesi bubble çocuklarını YOK ETMEMELİ
# (gerçek ui/chat/audio helper'ları sahte tk ile koşturulur)
# ══════════════════════════════════════════════════════════════════════════

class _ATK:
    """ui/chat/audio modülünün tk'sı yerine geçen çocuk-takipli sahte."""

    def __init__(self, master=None, **kw):
        self.kw = dict(kw)
        self.children = []
        self.destroyed = False
        if master is not None and hasattr(master, "children"):
            master.children.append(self)

    def pack(self, *a, **k):
        pass

    def config(self, **k):
        self.kw.update(k)

    def bind(self, *a, **k):
        pass

    def winfo_children(self):
        return [] if self.destroyed else list(self.children)

    def destroy(self):
        self.destroyed = True


class _XL:
    """xmpp.py'nin kendi tk.Label'ı yerine geçen kayıtçı."""

    def __init__(self, master=None, **kw):
        self.kw = dict(kw)
        if hasattr(master, "children"):
            master.children.append(self)

    def pack(self, *a, **k):
        pass

    def bind(self, *a, **k):
        pass


def test_mixed_overflow_preserves_bubble_children(monkeypatch):
    """Regresyon: eski taşma yolu `fallback_link(bubble, ...)` çağırıp
    bubble'ın TÜM çocuklarını yok ediyordu. Yeni taşma yolu tek denetim
    üretir; gövde, zengin görseller ve ilk 3 zengin ses korunur."""
    mw = _append_window(monkeypatch)
    monkeypatch.setattr(xmpp._audio_ui, "tk",
                        types.SimpleNamespace(Frame=_ATK, Label=_ATK))
    monkeypatch.setattr(xmpp.tk, "Frame", _XL)
    monkeypatch.setattr(xmpp.tk, "Label", _XL)
    fb_spy = _Capture()
    monkeypatch.setattr(xmpp._audio_ui, "fallback_link",
                        lambda *a, **k: fb_spy((a, k)))
    bubbles = []
    orig_render = xmpp._render.render_base_message

    def spy_render(*a, **k):
        view = orig_render(*a, **k)
        bubbles.append(view.bubble)
        return view

    monkeypatch.setattr(xmpp._render, "render_base_message", spy_render)

    # istek yollarını izole et: burada taşma RENDER davranışı test edilir
    # (saturasyon degrade'i ayrıca 2A testlerinde kapsanır)
    mw._request_image = lambda url, holder, bg: None
    mw._request_audio = lambda url, holder, bg: None

    body = "bak " + _imgs(8) + " " + _auds(5)
    mw._append(body, "them", sender="A")

    bubble = bubbles[0]
    kids = bubble.children
    body_lbls = [c for c in kids if getattr(c, "kw", {}).get("text") == "bak"]
    img_ph = [c for c in kids
              if getattr(c, "kw", {}).get("text") == "📷 Yükleniyor…"]
    audio_holders = [c for c in kids if isinstance(c, _ATK)]
    overflow_lbls = [c for c in kids
                     if "bağlantısı daha" in str(getattr(c, "kw", {})
                                                .get("text", ""))]

    assert body_lbls                           # gövde metni yaşıyor
    assert len(img_ph) == 6                    # zengin görseller yaşıyor
    assert len(audio_holders) == 3             # ilk 3 zengin ses yaşıyor
    assert all(not h.destroyed for h in audio_holders)
    assert all(len(h.children) == 1 for h in audio_holders)  # içleri dolu
    assert len(overflow_lbls) == 2             # görsel + ses taşma denetimi
    texts = [c.kw["text"] for c in overflow_lbls]
    assert "🔗 2 görsel bağlantısı daha" in texts
    assert "🎤 2 ses bağlantısı daha" in texts
    # taşma listeleri tam ve sıralı:
    img_ctl = next(c for c in overflow_lbls if c.kw["text"].startswith("🔗"))
    aud_ctl = next(c for c in overflow_lbls if c.kw["text"].startswith("🎤"))
    assert img_ctl._overflow_urls == [f"http://x/i{i}.png" for i in range(6, 8)]
    assert aud_ctl._overflow_urls == [f"http://x/a{i}.ogg" for i in range(3, 5)]
    assert len(fb_spy.calls) == 0              # yıkıcı helper hiç çağrılmadı


# ══════════════════════════════════════════════════════════════════════════
# 9-11: 2A/2B/2C değişmezleri
# ══════════════════════════════════════════════════════════════════════════

def test_worker_cap_invariant_unchanged():
    assert xmpp._MEDIA_WORKER_CAP == 6


def test_excess_links_do_not_touch_media_cache(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    mw._append(_imgs(50), "them", sender="A")
    assert getattr(mw, "_media_cache", None) in (None, OrderedDict())


def test_audio_singleflight_quota_independent(monkeypatch):
    """Tek mesajda 3 zengin ses sonrası ekstra istek yok; single-flight
    mimarisi (2C) değişmedi — `_request_audio` yalnız ilk 3 URL için çağrılır."""
    mw, c = _bounds_mw(monkeypatch)
    mw._append(_auds(10), "them", sender="A")
    assert len(c["req_audio"]) == 3
    assert getattr(mw, "_audio_inflight", {}) == {}  # kayıt çağrılmadı


# ══════════════════════════════════════════════════════════════════════════
# 12: cache hit kota'yı bypass etmez
# ══════════════════════════════════════════════════════════════════════════

def test_cached_image_url_still_limited_by_quota(monkeypatch):
    mw, c = _bounds_mw(monkeypatch)
    cached = "http://x/i8.png"
    mw._media_cache = OrderedDict([(("image", cached), "cached-img")])
    mw._append(_imgs(10), "them", sender="A")
    # ilk 6 zengin; cache'li 9. URL (i8) kota dışında → zengin DEĞİL,
    # taşan denetimin listesinde:
    assert cached not in c["req_img"]
    assert cached in c["overflow"][0][1]
    assert len(c["rich_img"]) == 6
    assert c["req_img"][0] == "http://x/i0.png"


# ══════════════════════════════════════════════════════════════════════════
# 13 + adversarial ölçek probu: N = 10/50/100/500/1000
# ══════════════════════════════════════════════════════════════════════════

def _scale_probe(monkeypatch, n, dispatch_result=True):
    """Gerçek `_request_image` + sahte dispatcher ile ölçüm."""
    mw = _append_window(monkeypatch)
    counts = {"rich": [], "links": [], "sat": [], "overflow": []}
    holders = []

    def fake_ph(parent, theme, bg):
        holder = SimpleNamespace(
            configs=[],
            config=lambda **k: holder.configs.append(k),
            bind=lambda *a, **k: None)
        holders.append(holder)
        counts["rich"].append(bg)
        return holder

    monkeypatch.setattr(xmpp._media_ui, "image_placeholder", fake_ph)
    monkeypatch.setattr(xmpp._media_ui, "image_link",
                        lambda *a, **k: counts["links"].append(1))
    monkeypatch.setattr(xmpp._media_ui, "image_link",
                        lambda parent, theme, url, bg, cb:
                        counts["links"].append(url))
    attempts = []
    started = []

    class _NoThread:
        def __init__(self, target=None, daemon=None):
            pass

        def start(self):
            started.append(1)

    monkeypatch.setattr(xmpp.threading, "Thread", _NoThread)

    def fake_dispatch(self, target, args=(), on_saturated=None):
        attempts.append(target)
        if not dispatch_result:
            counts["sat"].append(1)
            if on_saturated is not None:
                on_saturated()
            return False
        started.append(1)
        return True

    monkeypatch.setattr(xmpp.MainWindow, "_dispatch_media_worker",
                        fake_dispatch)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(
                            AssertionError("ağ çağrısı olmamalı")))
    mw._add_media_overflow_control = (
        lambda bubble, kind, urls, bg:
        counts["overflow"].append((kind, list(urls))))
    mw._append(_imgs(n), "them", sender="A")
    return counts, attempts, started, holders


@pytest.mark.parametrize("n", [10, 50, 100, 500, 1000])
def test_scale_probe_distinct_images_bounded(monkeypatch, n):
    counts, attempts, started, _holders = _scale_probe(monkeypatch, n)
    assert len(counts["rich"]) == min(6, n)    # zengin widget ≤ 6
    assert len(counts["links"]) == 0           # URL başına bağlantı üretimi yok
    assert len(attempts) == min(6, n)          # dispatcher denemesi ≤ 6
    assert len(started) == min(6, n)           # başlayan worker ≤ 6
    assert len(counts["sat"]) == 0             # slot müsait: saturasyon yok
    assert len(counts["overflow"]) == (1 if n > 6 else 0)
    if n > 6:
        assert len(counts["overflow"][0][1]) == n - 6   # tüm fazlalık listede


def test_saturation_path_only_for_rich_items(monkeypatch):
    """Slot yoksa yalnız zengin adaylar degrade edilir; fazlalıklar hiç
    dispatcher'a uğramaz (saturation callback gerekmez)."""
    counts, attempts, started, holders = _scale_probe(
        monkeypatch, 10, dispatch_result=False)
    assert len(attempts) == 6                  # yalnız zengin adaylar
    assert len(counts["sat"]) == 6             # 6 zengin aday degrade
    assert len(counts["links"]) == 0           # URL başına bağlantı üretimi yok
    assert len(counts["rich"]) == 6            # placeholder yine ≤ 6
    # 6 degrade placeholder bağlantı görünümüne çevrilmiş:
    assert all(h.configs and h.configs[0]["text"].startswith("🔗")
               for h in holders)
    # kota fazlası (4 URL) tek taşan denetimde:
    assert len(counts["overflow"]) == 1
    assert len(counts["overflow"][0][1]) == 4
