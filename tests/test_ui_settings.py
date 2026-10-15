"""Ayarlar penceresi ui/dialogs/settings'e taşındı: davranış korunur.

- Görünüm durumsuzdur: bot, config yazımı, thread, DB yoktur.
- Bağlantılar MainWindow'daki alt pencereleri açar; "Kaydet ve Kapat"
  toplanan değerleri _settings_apply ile config'e yazar ve canlı uygular.
"""
import inspect
import os
import sys
import tkinter as tk
from unittest import mock

import pytest

import xmpp
from ui.dialogs import settings as ui_settings


def test_settings_view_has_no_domain_dependencies():
    src = inspect.getsource(ui_settings)
    for token in ("self.", "_db_", "_save_config", "_load_config", "threading",
                  "gui_q", "_safe_after", "run_coroutine_threadsafe",
                  "slixmpp", "sqlite", "publish_avatar"):
        assert token not in src, f"domain sızıntısı: {token}"


def test_settings_dialog_is_thin_delegation():
    src = inspect.getsource(xmpp.MainWindow._settings_dialog)
    assert "_ui_settings.show_settings(" in src
    assert len(src.splitlines()) < 10


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


@pytest.fixture()
def settings(monkeypatch):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    root = tk.Tk()
    root.withdraw()
    xmpp._apply_theme()
    saved = []
    monkeypatch.setattr(xmpp, "_load_config", lambda: {
        "sounds": False, "default_encryption": "omemo",
        "status_text": "Toplantıda", "pgp_keymap": {"ali@x": "ABCD1234"}})
    monkeypatch.setattr(xmpp, "_save_config", saved.append)
    monkeypatch.setattr(xmpp, "_safe_grab_set", lambda *a, **k: None)
    monkeypatch.setattr(xmpp, "_apply_color_theme", lambda name: None)
    monkeypatch.setattr(xmpp, "_current_lang", "tr")

    class _W(xmpp.MainWindow):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            m = mock.MagicMock(name=name)
            object.__setattr__(self, name, m)   # aynı sahte geri dönsün
            return m

    w = object.__new__(_W)
    w.root, w.jid = root, "ben@example.com"
    w._avatars, w._photo_refs = {}, []
    w._last_ping_ms, w._compact_mode = 0, False
    w._contacts, w.rooms = {"ali@x": "Ali"}, {}
    w.bot = mock.MagicMock(omemo_ready=False)
    w.bot.pgp_available.return_value = True
    w.bot.pgp_list_keys.return_value = [{"keyid": "ABCD1234", "uids": ["Ali"]}]
    w.bot.is_connected.return_value = True
    w._settings_dialog()
    top = next(c for c in root.winfo_children() if isinstance(c, tk.Toplevel))
    top.update_idletasks()
    yield w, top, saved
    root.destroy()


LINKS = [
    ("🖼 Arka Plan Değiştir…", "wallpaper", "_wallpaper_dialog"),
    ("🚫 Engelli kişileri yönet...", "blocking", "_blocking_dialog"),
    ("🔐 QR Kod ile Parmak İzi Doğrula…", "omemo_qr", "_omemo_qr_dialog"),
    ("🔧 Proxy Ayarları…", "proxy", "_proxy_dialog"),
    ("🌓 Otomatik Tema Ayarları…", "auto_theme", "_auto_theme_dialog"),
    ("🔑 Uygulama Kilidi (PIN)…", "pin_lock", "_pin_lock_dialog"),
    ("🗑 Mesaj Geçmişini Sil…", "clear_history", "_clear_history_dialog"),
    ("📤 Sohbetleri Dışa Aktar", "export_chat", "_export_chat"),
    ("💾 Yedekleme / Geri Yükleme…", "backup", "_backup_dialog"),
    ("⌨ Kısayolları Göster…", "shortcuts", "_shortcuts_dialog"),
]


@pytest.mark.parametrize("text, _key, _method", LINKS)
def test_links_exist_and_are_bound(settings, text, _key, _method):
    # Gizli kök altında pencere çizilmez; Tk çizilmemiş widget'a fare olayı
    # iletmez. Bu yüzden bağlama burada, yönlendirme aşağıda ayrı denetlenir.
    _w, top, _saved = settings
    lbl = next(x for x in _walk(top)
               if isinstance(x, tk.Label) and x.cget("text") == text)
    assert lbl.bind("<Button-1>")


@pytest.mark.parametrize("_text, key, method", LINKS)
def test_actions_route_to_owner_dialogs(settings, _text, key, method):
    w, _top, _saved = settings
    target = mock.MagicMock()
    setattr(w, method, target)          # gerçek alt pencere açılmasın
    w._settings_actions()[key]()
    assert target.call_count == 1


def test_save_writes_config_and_applies_live(settings):
    w, top, saved = settings
    save = next(x for x in _walk(top) if x.winfo_class() == "TButton"
                and x.cget("text").strip() == "Kaydet ve Kapat")
    save.invoke()
    assert len(saved) == 1
    cfg = saved[0]
    # Açılış değerleri pencereden geçip geri yazılır
    assert cfg["sounds"] is False and w._sound_enabled is False
    assert cfg["default_encryption"] == "omemo"
    assert w._default_encryption == "omemo"
    # PGP eşleştirmesi pencereden okunur ve bota iletilir
    assert cfg["pgp_keymap"] == {"ali@x": "ABCD1234"}
    assert cfg["ft_block_size"] == 4096 and cfg["ft_warn_mb"] == 50
    assert cfg["status_text"] == "Toplantıda"
    w.bot.set_status_message.assert_called_once_with("Toplantıda", "chat")
    assert not top.winfo_exists()


def test_omemo_device_info_goes_through_safe_after(settings, monkeypatch):
    """OMEMO hazırsa cihaz bilgisi bot'tan istenir, yanıt GUI'ye
    _safe_after ile döner (görünüm thread'e dokunmaz)."""
    w, top, _saved = settings
    top.destroy()
    w.bot.omemo_ready = True
    monkeypatch.setattr(xmpp, "HAS_OMEMO", True)
    w._safe_after = mock.MagicMock()
    w._settings_dialog()
    (callback,), _kw = w.bot.omemo_device_info.call_args
    callback({"device_id": 7, "fingerprint": "aa bb", "other_devices": []})
    args = w._safe_after.call_args[0]
    assert args[0] == 0 and args[2]["device_id"] == 7
