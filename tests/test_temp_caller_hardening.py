"""Resource Hardening 2D — tempfile sahipliği çağıran sertleştirmesi.

Kapsam:
- Kayıt (recording) finalize: sahiplik üreticide — tescil reddedilirse
  producer dosyayı siler, gönderim/UI planlanmaz; kapanış callback'i
  baskılarsa temizlik sahiplenir.
- Bildirim sesi: WAV tescilli; tescil reddi → sil + oynatıcı yok;
  gecikmeli temizlik ↔ quit temizliği iki yönlü zararsız.

Deterministik: gerçek ağ/oynatıcı yok; Event/gate + kaydedilen thread
gövdeleri ile çalışır.
"""
import os
import queue
import subprocess
import tempfile
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
    mw.rooms = []
    mw.active = "t@b.c"
    mw._VOICE_CHANNELS = 1
    mw._VOICE_RATE = 44100
    mw.bot = types.SimpleNamespace(
        send_file=lambda to, path, mtype: mw.bot.calls.append(
            ("send", to, path, mtype)))
    mw.bot.calls = []
    mw._show_sent_voice = lambda path, target=None: mw.bot.calls.append(
        ("show", target))
    mw._safe_calls = []
    mw.root = types.SimpleNamespace()          # messagebox parent'ı için

    def fake_safe_after(ms, fn, *args):
        mw._safe_calls.append((fn, args))
        return None

    mw._safe_after = fake_safe_after
    return mw


def _spy_named_tempfile(monkeypatch):
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


def _run_callback(mw):
    """_safe_after ile planlanan tek callback'i çalıştır."""
    assert len(mw._safe_calls) == 1, mw._safe_calls
    fn, args = mw._safe_calls[0]
    fn(*args)


# ══════════════════════════════════════════════════════════════════════════
# Kayıt (recording) finalize sahipliği
# ══════════════════════════════════════════════════════════════════════════

def test_finalize_registers_then_shutdown_cleanup_owns(monkeypatch):
    """Spec-1/2: finalize WAV yazar + tesciller; callback baskılanırsa
    (kapanış) temizlik dosyayı sahiplenir ve siler."""
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)

    mw._finalize_recording(b"\x00\x00" * 200, "t@b.c")
    assert len(mw._safe_calls) == 1            # callback planlandı
    wav = mw._safe_calls[0][1][0]
    assert wav == created[0]
    assert os.path.exists(wav) and wav in mw._temp_files

    # callback HİÇ çalıştırılmadan kapanış:
    mw._closing = True
    mw._cleanup_temp_registry()
    assert not os.path.exists(wav)             # yetim yok
    assert mw._temp_files == []
    assert mw.bot.calls == []                  # gönderim/show hiç çalışmadı


def test_normal_recording_path_unchanged(monkeypatch):
    """Spec-4: normal yol — tescil + callback kullanılabilir yol alır."""
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)
    mw._finalize_recording(b"\x00\x00" * 200, "t@b.c")
    _run_callback(mw)

    wav = created[0]
    assert mw.bot.calls[0] == ("send", "t@b.c", wav, "chat")
    assert ("show", "t@b.c") in mw.bot.calls
    assert os.path.exists(wav)
    assert mw._temp_files.count(wav) == 1      # çift tescil yok (spec-5)
    os.unlink(wav)


def test_cleanup_completed_before_registration_producer_deletes(monkeypatch):
    """Spec-3: temizlik zaten geçtiyse tescil reddedilir → producer dosyayı
    siler, callback planlamaz."""
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)
    mw._closing = True
    mw._cleanup_temp_registry()

    mw._finalize_recording(b"\x00\x00" * 200, "t@b.c")

    assert len(created) == 1
    assert not os.path.exists(created[0])      # producer sildi
    assert mw._safe_calls == []                # callback planlanmadı
    assert mw._temp_files == []                # kayda girdi yok
    assert mw.bot.calls == []


def test_finalize_write_failure_leaves_no_artifact(monkeypatch):
    """Spec-audit: WAV yazım hatası → oluşturulan tmp silinir, kayda
    girmemişse registry de temiz kalır, hata diyaloğu planlanır."""
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)

    def broken_wave_open(*a, **k):
        raise RuntimeError("disk yok")

    monkeypatch.setattr(xmpp.wave, "open", broken_wave_open)
    dialogs = []
    monkeypatch.setattr(xmpp.messagebox, "showerror",
                        lambda *a, **k: dialogs.append(a))

    mw._finalize_recording(b"\x00\x00" * 200, "t@b.c")

    assert all(not os.path.exists(p) for p in created)  # artefakt yok
    assert mw._temp_files == []                # kayda girmemiş (ret/temizlik yok)
    # kapanış YOK: kullanıcıya hata diyaloğu planlanır (mevcut davranış)
    assert len(mw._safe_calls) == 1
    fn, args = mw._safe_calls[0]
    fn(*args)                                  # diyalog çağrılabilir olmalı
    assert dialogs                             # showerror mesajı iletildi


def test_no_double_registration_after_callback(monkeypatch):
    mw = _make_mw()
    created = _spy_named_tempfile(monkeypatch)
    mw._finalize_recording(b"\x00\x00" * 200, "t@b.c")
    _run_callback(mw)
    _run_callback(mw)                          # idempotent çağrım bile olsa
    wav = created[0]
    assert mw._temp_files.count(wav) == 1      # tek sahiplik kaydı
    os.unlink(wav)


# ══════════════════════════════════════════════════════════════════════════
# Bildirim sesi sahipliği
# ══════════════════════════════════════════════════════════════════════════

def _notif_mw(monkeypatch, *, popen="ok"):
    """Bildirim testi iskeleti: Popen + Thread yakalayıcı."""
    mw = _make_mw()
    launched = []

    def fake_popen(cmd, stdout=None, stderr=None):
        launched.append(cmd)
        return types.SimpleNamespace(pid=1234, wait=lambda timeout=None: 0)

    if popen == "ok":
        monkeypatch.setattr(subprocess, "Popen", fake_popen)
    elif popen == "missing":
        def missing(*a, **k):
            raise FileNotFoundError("oynatıcı yok")
        monkeypatch.setattr(subprocess, "Popen", missing)
    targets = []

    class _T:
        def __init__(self, target=None, daemon=None):
            targets.append(target)

        def start(self):
            pass

    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    monkeypatch.setattr(xmpp.time, "sleep", lambda s: None)
    return mw, launched, targets


def test_notification_registered_before_player_launch(monkeypatch):
    """Spec-6: oynatıcı başlatılmadan WAV tescillenir."""
    mw, launched, _targets = _notif_mw(monkeypatch)
    mw._play_notification_sound()
    assert len(launched) == 1
    cmd = launched[0]
    assert cmd[0] == "paplay"
    path = cmd[1]
    assert path in mw._temp_files              # tescil oynatıcıdan önce
    assert os.path.exists(path)
    os.unlink(path)
    mw._forget_temp(path)


def test_notification_registration_rejected_no_player(monkeypatch):
    """Spec-7: geç kapanışta tescil reddedilir → dosya silinir, çalınmaz."""
    mw, launched, _targets = _notif_mw(monkeypatch)
    created = _spy_named_tempfile(monkeypatch)
    mw._closing = True
    mw._cleanup_temp_registry()

    mw._play_notification_sound()

    assert launched == []                      # oynatıcı başlatılmadı
    assert len(created) == 1
    assert not os.path.exists(created[0])      # producer sildi
    assert mw._temp_files == []


def test_delayed_notification_cleanup_removes_and_forgets(monkeypatch):
    """Spec-8: gecikmeli temizlik dosyayı siler + kaydı unutturur."""
    mw, launched, targets = _notif_mw(monkeypatch)
    mw._play_notification_sound()
    path = launched[0][1]
    assert os.path.exists(path) and path in mw._temp_files

    targets[0]()                               # gecikmeli temizlik gövdesi

    assert not os.path.exists(path)            # dosya silindi
    assert path not in mw._temp_files          # kayıt uzlaştırıldı


def test_quit_cleanup_before_delayed_cleanup_is_harmless(monkeypatch):
    """Spec-9: quit temizliği önce → gecikmeli temizlik no-op, kayıt tutarlı."""
    mw, launched, targets = _notif_mw(monkeypatch)
    mw._play_notification_sound()
    path = launched[0][1]
    assert path in mw._temp_files

    mw._closing = True
    mw._cleanup_temp_registry()                # quit: dosyayı siler, kaydı boşaltır
    assert not os.path.exists(path)
    assert mw._temp_files == []

    targets[0]()                               # geç gelen temizlik
    assert mw._temp_files == []                # çift silme/no-op zararsız
    assert mw._temp_cleanup_done is True


def test_delayed_cleanup_before_quit_is_harmless(monkeypatch):
    """Spec-10: gecikmeli temizlik önce → quit sonrası sahiplik zaten boş."""
    mw, launched, targets = _notif_mw(monkeypatch)
    mw._play_notification_sound()
    path = launched[0][1]
    targets[0]()
    assert path not in mw._temp_files and not os.path.exists(path)

    mw._closing = True
    mw._cleanup_temp_registry()
    assert mw._temp_files == []


def test_notification_without_player_still_registry_owned(monkeypatch):
    """Hiçbir oynatıcı yoksa: dosya tescilli kalır → kapanış temizliği siler
    (eski davranışta bu yol kalıcı yetim üretiyordu)."""
    mw, launched, _targets = _notif_mw(monkeypatch, popen="missing")
    created = _spy_named_tempfile(monkeypatch)
    mw._play_notification_sound()
    assert launched == []                      # üç oynatıcı da bulunamadı
    path = created[0]
    assert os.path.exists(path) and path in mw._temp_files
    mw._closing = True
    mw._cleanup_temp_registry()
    assert not os.path.exists(path)            # kapanış temizliği sildi
    assert mw._temp_files == []


def test_notification_write_failure_leaves_no_artifact(monkeypatch):
    mw, launched, _targets = _notif_mw(monkeypatch)
    created = _spy_named_tempfile(monkeypatch)

    def broken_wave_open(*a, **k):
        raise OSError("WAV yazılamadı")

    monkeypatch.setattr(xmpp.wave, "open", broken_wave_open)
    mw._play_notification_sound()

    assert created
    assert all(not os.path.exists(path) for path in created)
    assert mw._temp_files == []
    assert launched == []
