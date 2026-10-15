"""Resource Hardening 2C follow-up — quit vs geç worker tempfile yarışı.

Doğrulanmış blocker: `_audio_fetch_worker` ağ/ffmpeg içinde blokelidirken
`_quit` çalışırsa, temizlik anlık görüntüsünden SONRA worker'ın
oluşturduğu/tescil ettiği tempfile yetim kalıyordu.

Bu test dosyası yeni sahiplik sözleşmesini kanıtlar:
- `_remember_temp(path) → bool`: temizlik geçtiyse tescil REDDEDİLİR,
- reddedilen tescilde worker yeni artefaktı kendisi siler ve durur,
- temizlikten ÖNCE gelen tesciller temizlik anlık görüntüsüne dahildir.

Deterministik: gerçek ağ/ffmpeg yok; Event gate + kuyruk boşaltma.
"""
import os
import queue
import subprocess
import tempfile
import threading
import time
import types

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


def _spy_named_tempfile(monkeypatch):
    """NamedTemporaryFile çağrılarını kaydet (gerçek dosya da oluşturulur)."""
    created = []
    real = tempfile.NamedTemporaryFile

    def spy(*a, **k):
        f = real(*a, **k)
        created.append(f.name)
        return f

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy)
    return created


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


def _wait_worker_done(mw, url, timeout=5.0):
    """Worker in-flight kaydını çözene dek bekle; sonra kuyruğu boşalt."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if url not in mw._audio_inflight:
            _drain(mw)
            return True
        time.sleep(0.005)
    _drain(mw)
    return False


# ══════════════════════════════════════════════════════════════════════════
# Blocker 1: WAV geç worker — temizlik tescilden ÖNCE biterse
# ══════════════════════════════════════════════════════════════════════════

def test_wav_late_worker_after_cleanup_leaves_no_file(monkeypatch):
    mw = _make_mw()
    net = _GatedUrlopen(b"WAVEFAKE")
    monkeypatch.setattr(xmpp.urllib.request, "urlopen", net)
    created = _spy_named_tempfile(monkeypatch)
    h = _Holder()
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    mw._place_audio_fallback = lambda holder, url, bg: holder.errors.append("fb")

    assert mw._request_audio("http://x/late.wav", h, "#fff") is True
    assert net.entered.wait(5)                 # worker ağda bloke
    # _quit sırası: _closing=True → temizlik (worker henüz tescil etmedi)
    mw._closing = True
    mw._cleanup_temp_registry()
    assert mw._temp_cleanup_done is True
    assert mw._temp_files == []

    net.gate.set()                             # worker serbest
    assert _wait_worker_done(mw, "http://x/late.wav")
    _drain(mw)
    # worker yeni tempfile oluşturdu ama tescil reddedildi → kendisi sildi
    assert len(created) == 1
    assert not os.path.exists(created[0])      # diskte yetim yok
    assert h.placed == []                      # bayat UI mutasyonu yok
    assert h.errors == []
    assert mw._audio_inflight == {}            # in-flight yapışık kalmadı
    assert mw._temp_files == []                # registry temiz


# ══════════════════════════════════════════════════════════════════════════
# Blocker 2: non-WAV geç worker — temizlik ffmpeg SIRASINDA geçerse
# ══════════════════════════════════════════════════════════════════════════

def test_nonwav_late_worker_after_cleanup_no_orphans(monkeypatch):
    mw = _make_mw()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"oggdata"))
    created = _spy_named_tempfile(monkeypatch)
    conv_gate = threading.Event()
    conv_entered = threading.Event()

    def fake_run(cmd, capture_output=None, timeout=None):
        conv_entered.set()
        conv_gate.wait(10)
        with open(cmd[-1], "wb") as f:
            f.write(b"RIFFconverted")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    h = _Holder()
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    mw._place_audio_fallback = lambda holder, url, bg: holder.errors.append("fb")

    assert mw._request_audio("http://x/v.ogg", h, "#fff") is True
    assert conv_entered.wait(5)
    # worker original tescilledi ve ffmpeg içinde bloke; temizlik ŞİMDİ:
    mw._closing = True
    mw._cleanup_temp_registry()
    original = created[0]
    assert not os.path.exists(original)        # original temizlikte silindi
    assert mw._temp_files == []

    conv_gate.set()                            # ffmpeg "tamamlanır"
    assert _wait_worker_done(mw, "http://x/v.ogg")
    _drain(mw)
    converted = original + ".wav"              # çıktı worker tarafından yazılır
    # temizlik geçti: dönüştürülen tescil reddedildi → worker kendisi sildi
    assert not os.path.exists(converted)
    assert converted not in mw._temp_files
    assert mw._temp_files == []                # registry gerçeği yansıtıyor
    assert mw._audio_inflight == {}            # in-flight yapışmadı
    assert h.placed == [] and h.errors == []   # kapanışta UI yok


# ══════════════════════════════════════════════════════════════════════════
# Tescil ↔ temizlik araya girme sözleşmesi (birim)
# ══════════════════════════════════════════════════════════════════════════

def test_remember_temp_ownership_contract():
    mw = _make_mw()
    # kapanış yok: normal tescil
    assert mw._remember_temp("/p/a") is True
    assert "/p/a" in mw._temp_files
    # kapanış VAR ama temizlik henüz yapılmadı → kabul (temizlik sahiplenir)
    mw._closing = True
    assert mw._remember_temp("/p/b") is True
    assert "/p/b" in mw._temp_files
    # temizlik: snapshot hepsini alır, kaydı boşaltır, bayrak kalkar
    mw._cleanup_temp_registry()
    assert mw._temp_files == []
    assert mw._temp_cleanup_done is True
    # temizlik sonrası tescil: RED — çağıran kendi artefaktından sorumlu
    assert mw._remember_temp("/p/c") is False
    assert "/p/c" not in mw._temp_files
    # forget: boş kayıtta no-op
    mw._forget_temp("/p/a")
    assert mw._temp_files == []


def test_cleanup_registry_deletes_registered_files_from_disk(tmp_path):
    mw = _make_mw()
    f1 = tmp_path / "a.wav"
    f2 = tmp_path / "b.wav"
    f1.write_bytes(b"1")
    f2.write_bytes(b"2")
    assert mw._remember_temp(str(f1)) is True
    assert mw._remember_temp(str(f2)) is True
    mw._closing = True
    mw._cleanup_temp_registry()
    assert not f1.exists() and not f2.exists()   # diskten gerçekten silindi
    assert mw._temp_files == []


def test_wav_file_registered_before_cleanup_is_deleted_by_cleanup(
        monkeypatch, tmp_path):
    """Tescil temizlikten ÖNCEyse: temizlik sahiptir; worker dosyayı
    kullanmaz ve dosya temizlikte silinir."""
    mw = _make_mw()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"WAVEFAKE"))
    created = _spy_named_tempfile(monkeypatch)
    h = _Holder()
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)

    assert mw._request_audio("http://x/ok.wav", h, "#fff") is True
    _wait_worker_done(mw, "http://x/ok.wav")
    wav = created[0]
    assert os.path.exists(wav) and wav in mw._temp_files   # normal yol
    mw._closing = True
    mw._cleanup_temp_registry()
    assert not os.path.exists(wav)             # temizlik sahiplendi ve sildi
    assert mw._temp_files == []


# ══════════════════════════════════════════════════════════════════════════
# Kapanış sınır durumları
# ══════════════════════════════════════════════════════════════════════════

def test_closing_before_creation_starts_nothing(monkeypatch):
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResp(b"WAVEFAKE")

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", fake_urlopen)
    mw._closing = True
    # istek girişi: yeni fetch başlatmaz
    assert mw._request_audio("http://x/z.wav", _Holder(), "#fff") is False
    # doğrudan worker çağrısı da dosya oluşturmadan çıkar
    mw._audio_fetch_worker("http://x/z.wav")
    assert calls["n"] == 0 and created == []
    assert getattr(mw, "_audio_inflight", {}) == {}


def test_closing_after_converted_registration_cleanup_still_owns(
        monkeypatch, tmp_path):
    """Dönüştürülen WAV tescil edildikten SONRA kapanış: temizlik onu siler
    (normal tamamlanmış akışta original zaten unutulmuştu)."""
    mw = _make_mw()
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"oggdata"))

    def fake_run(cmd, capture_output=None, timeout=None):
        with open(cmd[-1], "wb") as f:
            f.write(b"RIFFconverted")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    registered = []
    orig_remember = mw._remember_temp

    def spy_remember(path):
        registered.append(path)
        return orig_remember(path)

    mw._remember_temp = spy_remember
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h = _Holder()

    assert mw._request_audio("http://x/v4.ogg", h, "#fff") is True
    _wait_worker_done(mw, "http://x/v4.ogg")
    original, converted = registered
    assert not os.path.exists(original)        # normal 2C davranışı korunur
    assert converted in mw._temp_files and os.path.exists(converted)

    mw._closing = True
    mw._cleanup_temp_registry()
    assert not os.path.exists(converted)       # temizlik sahipliği sürüyor
    assert mw._temp_files == []
    assert h.placed == [converted]             # tamamlanan yerleşim geri alınmaz


# ══════════════════════════════════════════════════════════════════════════
# Kapanış olmadan normal 2C davranışı değişmedi
# ══════════════════════════════════════════════════════════════════════════

def test_normal_wav_path_still_works(monkeypatch):
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"WAVEFAKE"))
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h = _Holder()

    assert mw._request_audio("http://x/ok2.wav", h, "#fff") is True
    _wait_worker_done(mw, "http://x/ok2.wav")
    _drain(mw)
    assert len(created) == 1 and os.path.exists(created[0])
    assert created[0] in mw._temp_files        # tescilli
    assert h.placed == [created[0]]


def test_normal_conversion_still_works(monkeypatch):
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)
    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"oggdata"))

    def fake_run(cmd, capture_output=None, timeout=None):
        with open(cmd[-1], "wb") as f:
            f.write(b"RIFFconverted")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    mw._place_audio = lambda holder, path, bg, url: holder.placed.append(path)
    h = _Holder()

    assert mw._request_audio("http://x/ok.ogg", h, "#fff") is True
    _wait_worker_done(mw, "http://x/ok.ogg")
    _drain(mw)
    original = created[0]
    converted = original + ".wav"
    assert os.path.exists(converted) and converted in mw._temp_files
    assert not os.path.exists(original) and original not in mw._temp_files
    assert h.placed == [converted]
    os.unlink(converted)
