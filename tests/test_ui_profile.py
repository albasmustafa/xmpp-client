"""ui/profile.py sözleşmeleri (Faz 4B-4)."""

import inspect
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from ui import profile as ui_profile  # noqa: E402


def test_status_menu_delegates_and_routes(monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_profile, "show_status_menu",
        lambda parent, on_select, x, y: captured.append((parent, on_select, x, y)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.status_var = types.SimpleNamespace(
        set=lambda v: captured.append(("var", v)))
    win._status_label = types.SimpleNamespace(
        config=lambda **k: captured.append(("lbl", k)))
    pres = []
    win.bot = types.SimpleNamespace(
        set_presence=lambda s, status="": pres.append(s))
    ev = types.SimpleNamespace(x_root=3, y_root=4)

    xmpp.MainWindow._show_status_menu(win, ev)

    parent, on_select, x, y = captured[0]
    assert (parent, x, y) == ("ROOT", 3, 4)
    on_select("Away", "away", "#abc")
    assert pres == ["away"]
    assert ("var", "Away") in captured
    assert ("lbl", {"text": "● Away", "fg": "#abc"}) in captured


def test_story_dialog_delegates_and_publishes(tmp_path, monkeypatch):
    captured = []
    monkeypatch.setattr(
        ui_profile, "show_story_dialog",
        lambda parent, on_publish: captured.append((parent, on_publish)))
    from PIL import Image
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@example.com"
    win._avatars = {}
    calls = []
    win.bot = types.SimpleNamespace(
        publish_mood=lambda m, t: calls.append(("mood", m, t)),
        publish_avatar=lambda d, m, cb=None: calls.append(("avatar", m)))
    win._publish_status = lambda t, s: calls.append(("status", t, s))
    win._show_toast = lambda *a: calls.append(("toast",) + a)
    win._update_sidebar_avatar = lambda: None
    monkeypatch.setattr(xmpp, "_save_avatar_cache", lambda jid, data: None)
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (40, 30)).save(photo, format="JPEG")

    xmpp.MainWindow._story_dialog(win)

    parent, on_publish = captured[0]
    assert parent == "ROOT"
    on_publish("selam", "happy", str(photo))
    assert ("status", "selam", "chat") in calls
    assert ("mood", "happy", "selam") in calls
    assert ("avatar", "image/png") in calls   # kare 256 px PNG
    assert calls[-1] == ("toast", "📖 Hikaye", "Durum yayınlandı")


def test_profile_icerikleri_ui_modulunde_ve_wrapper_ince():
    menu_src = inspect.getsource(ui_profile.show_status_menu)
    assert "STATUS_OPTIONS" in menu_src
    menu_wrap = inspect.getsource(xmpp.MainWindow._show_status_menu)
    assert "STATUS_OPTIONS" not in menu_wrap
    assert len(menu_wrap.splitlines()) < 12

    story_src = inspect.getsource(ui_profile.show_story_dialog)
    assert "Hikaye / Durum" in story_src
    story_wrap = inspect.getsource(xmpp.MainWindow._story_dialog)
    assert "Hikaye / Durum" not in story_wrap
    assert len(story_wrap.splitlines()) < 12


def test_profile_modulu_protocol_cagrisi_yapmaz():
    src = inspect.getsource(ui_profile)
    for token in ("self.bot", "set_status_message", "publish_mood",
                  "publish_avatar", "_db_", "run_coroutine_threadsafe"):
        assert token not in src, f"domain sızıntısı: {token}"


# ── Profil fotoğrafı penceresi: seçim/önizleme ui/profile'da, yayın owner'da ─

def test_change_avatar_dialog_delegates(monkeypatch):
    calls = []
    monkeypatch.setattr(ui_profile, "show_avatar_dialog",
                        lambda *a, **k: calls.append((a, k)))
    win = object.__new__(xmpp.MainWindow)
    win.root, win.jid = "ROOT", "ben@x"
    win._avatars, win._photo_refs = {"ben@x": b"png"}, ["REF"]
    xmpp.MainWindow._change_avatar_dialog(win)
    (args, kw), = calls
    assert args == ("ROOT", "ben@x", b"png", ["REF"])
    assert kw["on_publish"] == win._avatar_publish
    assert kw["on_forget"] == win._avatar_forget_local
    assert kw["on_removed"] == win._avatar_publish_removal


def _avatar_win(monkeypatch, tmp_path):
    win = object.__new__(xmpp.MainWindow)
    win.jid, win._avatars = "ben@x", {"ben@x": b"eski"}
    calls = []
    win._safe_after = lambda ms, fn, *a: fn(*a)
    win._update_sidebar_avatar = lambda: calls.append(("sidebar",))
    win._restore_avatar = lambda jid, data: calls.append(("restore", jid, data))
    published = []
    win.bot = types.SimpleNamespace(
        publish_avatar=lambda data, mime, cb=None: published.append((data, cb)))
    monkeypatch.setattr(xmpp, "_save_avatar_cache",
                        lambda jid, data: calls.append(("cache", jid, data)))
    monkeypatch.setattr(xmpp, "_avatar_cache_path",
                        lambda jid: str(tmp_path / "avatar.png"))
    return win, calls, published


@pytest.mark.parametrize("ok", [True, False])
def test_avatar_publish_reports_result_and_restores_on_failure(
        monkeypatch, tmp_path, ok):
    win, calls, published = _avatar_win(monkeypatch, tmp_path)
    results = []
    xmpp.MainWindow._avatar_publish(win, b"yeni", results.append)
    assert win._avatars["ben@x"] == b"yeni"
    assert calls == [("cache", "ben@x", b"yeni"), ("sidebar",)]
    (data, done), = published
    assert data == b"yeni"
    done(ok)                                    # sunucu yanıtı
    assert results == [ok]
    assert (("restore", "ben@x", b"eski") in calls) is (not ok)


def test_avatar_remove_clears_cache_then_publishes_empty(monkeypatch, tmp_path):
    win, calls, published = _avatar_win(monkeypatch, tmp_path)
    (tmp_path / "avatar.png").write_bytes(b"x")
    xmpp.MainWindow._avatar_forget_local(win)
    assert "ben@x" not in win._avatars
    assert not (tmp_path / "avatar.png").exists()
    xmpp.MainWindow._avatar_publish_removal(win)
    assert calls == [("sidebar",)] and published[0][0] == b""


def test_avatar_dialog_pick_crops_to_256_png(monkeypatch, tmp_path):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    import io
    import tkinter as tk
    from tkinter import filedialog, ttk

    from PIL import Image

    src = tmp_path / "genis.png"
    Image.new("RGB", (640, 480), "red").save(src)
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **k: str(src))
    monkeypatch.setattr(xmpp, "_safe_grab_set", lambda *a, **k: None)
    root = tk.Tk()
    root.withdraw()
    try:
        xmpp._apply_theme()
        sent = []
        dlg = ui_profile.show_avatar_dialog(
            root, "ben@x", None, [], on_publish=lambda b, cb: sent.append((b, cb)),
            on_forget=lambda: None, on_removed=lambda: None)

        def _walk(w):
            yield w
            for c in w.winfo_children():
                yield from _walk(c)
        btns = {b.cget("text"): b for b in _walk(dlg) if isinstance(b, ttk.Button)}
        assert "Kaldır" not in btns                 # fotoğraf yokken gizli
        btns["📷  Fotoğraf Seç"].invoke()
        (data, on_result), = sent
        assert Image.open(io.BytesIO(data)).size == (256, 256)
        on_result(False)
        status = [w.cget("text") for w in _walk(dlg) if isinstance(w, tk.Label)]
        assert "⚠ Yayınlanamadı — eski fotoğraf korundu" in status
    finally:
        root.destroy()
