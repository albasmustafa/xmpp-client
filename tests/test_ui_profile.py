"""ui/profile.py sözleşmeleri (Faz 4B-4)."""

import inspect
import os
import sys
import types

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
