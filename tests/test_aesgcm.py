"""OMEMO medya paylaşımı: aesgcm:// bağlantıları (XEP-0454).

Kanıt: Conversations, Monocles, Monal, Siskin OMEMO açıkken fotoğraf, sesli
mesaj ve dosyaları AES-256-GCM ile şifreleyip `aesgcm://…#<iv><anahtar>`
bağlantısıyla gönderir. Uygulama yalnız https:// tanıyordu: telefondan gelen
her şifreli medya açılamayan uzun bir bağlantı olarak görünüyordu.
"""
import inspect
import os

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from test_media_cache import (
    _FakeResp,
    _Holder,
    _make_mw,
    _tiny_png,
    _wait_inflight_cleared,
    _wire_image_ui,
)

import xmpp
from xmppcore import aesgcm

KEY = bytes(range(32))
IV12 = bytes(range(100, 112))
IV16 = bytes(range(100, 116))


def _url(path="upload.example.org/abc/foto.jpg", iv=IV12, key=KEY):
    return f"aesgcm://{path}#{(iv + key).hex()}"


def _encrypt(data, iv=IV12, key=KEY):
    return AESGCM(key).encrypt(iv, data, None)      # etiket sonda (XEP-0454)


# ── Ayrıştırma ve çözme ──────────────────────────────────────────────────────

@pytest.mark.parametrize("iv", [IV12, IV16], ids=["iv12", "iv16-eski"])
def test_parse_splits_https_url_key_and_iv(iv):
    https, key, got_iv = aesgcm.parse(_url(iv=iv))
    assert https == "https://upload.example.org/abc/foto.jpg"
    assert key == KEY and got_iv == iv


def test_parse_keeps_port_query_and_encoding():
    https, _key, _iv = aesgcm.parse(_url("up.example:5443/a/b%20c.jpg?x=1"))
    assert https == "https://up.example:5443/a/b%20c.jpg?x=1"


@pytest.mark.parametrize("url", [
    "https://upload.example.org/foto.jpg",
    "aesgcm://upload.example.org/foto.jpg",                 # parça yok
    "aesgcm://upload.example.org/foto.jpg#abcd",             # kısa
    "aesgcm://upload.example.org/foto.jpg#" + "zz" * 44,     # onaltılık değil
    "", None,
])
def test_parse_rejects_invalid(url):
    assert aesgcm.parse(url) is None


def test_decrypt_roundtrip_and_tamper_detection():
    data = "gizli fotoğraf baytları".encode()
    assert aesgcm.decrypt(_encrypt(data), KEY, IV12) == data
    tampered = bytearray(_encrypt(data))
    tampered[0] ^= 1
    with pytest.raises(InvalidTag):           # bozuk veri çöp olarak gösterilmez
        aesgcm.decrypt(bytes(tampered), KEY, IV12)


def test_file_name_is_decoded_and_safe():
    assert aesgcm.file_name(_url("h/a/rapor%20son.pdf")) == "rapor son.pdf"
    assert aesgcm.file_name(_url("h/a/..%2F..%2Fetc%2Fpasswd")) == "passwd"
    assert aesgcm.file_name(_url("h/")) == "dosya"


# ── İndirme: https üzerinden indir, çöz ──────────────────────────────────────

def test_fetch_url_bytes_downloads_over_https_and_decrypts(monkeypatch):
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append((req.full_url, timeout))
        return _FakeResp(_encrypt(b"PNGDATA"))

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    assert xmpp._fetch_url_bytes(_url(), 1024, timeout=7) == b"PNGDATA"
    assert seen == [("https://upload.example.org/abc/foto.jpg", 7)]


def test_fetch_url_bytes_plain_https_unchanged(monkeypatch):
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"duz"))
    assert xmpp._fetch_url_bytes("https://h/a.png", 1024) == b"duz"


def test_media_workers_use_shared_fetch():
    for fn in (xmpp.MainWindow._image_fetch_worker,
               xmpp.MainWindow._audio_fetch_worker,
               xmpp.MainWindow._show_image_fullscreen):
        assert "_fetch_url_bytes(" in inspect.getsource(fn), fn.__name__


def test_encrypted_photo_from_phone_is_shown_inline(monkeypatch):
    mw = _make_mw()
    _wire_image_ui(monkeypatch, mw)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(_encrypt(_tiny_png())))
    holder = _Holder()
    url = _url()
    assert mw._request_image(url, holder, "#fff") is True
    _wait_inflight_cleared(mw, ("image", url))
    assert holder.placed == ["photo"] and holder.errors == []


# ── Mesaj gövdesinde tanıma ──────────────────────────────────────────────────

def test_image_and_audio_regexes_capture_full_aesgcm_link():
    img, voice = _url(), _url("h/ses/kayit.m4a")
    body = f"{img} ve {voice}"
    assert [m.group(1) for m in xmpp._IMG_URL_RE.finditer(body)] == [img]
    assert [m.group(1) for m in xmpp._AUDIO_URL_RE.finditer(body)] == [voice]


def test_https_detection_is_unchanged():
    body = "bak https://h/a.png?x=1 ve https://h/s.ogg"
    assert [m.group(1) for m in xmpp._IMG_URL_RE.finditer(body)] == [
        "https://h/a.png?x=1"]
    assert [m.group(1) for m in xmpp._AUDIO_URL_RE.finditer(body)] == [
        "https://h/s.ogg"]


def test_non_media_aesgcm_links_become_file_cards():
    doc, img = _url("h/a/rapor.pdf"), _url()
    body = f"{doc}\n{img}"
    assert xmpp._aesgcm_file_urls(body, exclude={img}) == [doc]
    assert xmpp._aesgcm_file_urls("aesgcm://h/a.pdf", exclude=set()) == []


# ── Şifreli dosyayı indir, çöz, kaydet ve aç ─────────────────────────────────

def _file_mw(monkeypatch, tmp_path):
    mw = _make_mw()
    mw._download_dir = str(tmp_path)
    mw._show_toast = lambda *a, **k: None
    opened = []
    monkeypatch.setattr(xmpp, "_safe_open_url", opened.append)
    mw._safe_after = lambda ms, fn, *a: fn(*a)
    return mw, opened


@pytest.mark.parametrize("reveal", [False, True])
def test_encrypted_file_is_saved_decrypted_and_opened(monkeypatch, tmp_path, reveal):
    mw, opened = _file_mw(monkeypatch, tmp_path)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(_encrypt(b"%PDF-1.7")))
    (tmp_path / "rapor.pdf").write_bytes(b"eski")       # üzerine yazılmaz
    xmpp.MainWindow._aesgcm_file_worker(mw, _url("h/a/rapor.pdf"), reveal)
    saved = tmp_path / "rapor (1).pdf"
    assert saved.read_bytes() == b"%PDF-1.7"
    assert (tmp_path / "rapor.pdf").read_bytes() == b"eski"
    assert opened == [str(tmp_path) if reveal else str(saved)]


def test_encrypted_file_bad_key_saves_nothing(monkeypatch, tmp_path):
    mw, opened = _file_mw(monkeypatch, tmp_path)
    toasts = []
    mw._show_toast = lambda title, msg, **k: toasts.append(title)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"bozuk veri" * 4))
    xmpp.MainWindow._aesgcm_file_worker(mw, _url("h/a/rapor.pdf"), False)
    assert os.listdir(tmp_path) == [] and opened == []
    assert toasts and "açılamadı" in toasts[0]


# ── AI özellikleri: şifreli medya indirilir, anahtar asla metne girmez ──────

def test_ai_text_never_contains_aesgcm_key():
    from xmppcore import ai
    body = (f"bak {_url()} şu da {_url('h/ses/kayit.m4a')} "
            f"ve {_url('h/a/rapor.pdf')}")
    text = ai.strip_media_urls(body)
    assert (IV12 + KEY).hex() not in text and "aesgcm" not in text
    assert text == "bak [görsel] şu da [ses mesajı] ve [dosya]"
    assert ai.message_text(_url()) == ""          # yalnız medya: metin değil


def test_ai_fetch_url_decrypts_aesgcm(monkeypatch):
    from xmppcore import ai
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append(req.full_url)
        return _FakeResp(_encrypt(b"OGGDATA"))

    monkeypatch.setattr(ai.urllib.request, "urlopen", fake_urlopen)
    assert ai.fetch_url(_url("h/ses/kayit.ogg"), 1024) == b"OGGDATA"
    assert seen == ["https://h/ses/kayit.ogg"]


def test_ai_fetch_url_bad_key_is_ai_error(monkeypatch):
    from xmppcore import ai
    monkeypatch.setattr(ai.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"bozuk" * 8))
    with pytest.raises(ai.AIError):
        ai.fetch_url(_url(), 1024)


def test_speech_never_reads_aesgcm_key():
    from xmppcore import tts
    text = tts.clean_for_speech(f"fotoğraf geldi {_url()}")
    assert (IV12 + KEY).hex() not in text and "bağlantı" in text
