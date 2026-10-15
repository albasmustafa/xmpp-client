"""Ayarlar penceresindeki bozuk/ölü seçenekler.

- Bildirim, ses, dil, yazı tipi, durum mesajı ve varsayılan şifreleme
  config'e yazılıyor ama açılışta okunmuyordu (yeniden başlatınca kayıp).
- Kaydet, AÇIK sohbetin şifrelemesini varsayılana çeviriyordu (tema
  değiştirmek bile OMEMO sohbeti sessizce şifresize düşürüyordu).
- "Kaybolan mesajlar varsayılan süresi" hiç okunmuyordu.
- Karbon / MAM / akış yönetimi anahtarları hiçbir şeye bağlı değildi.
"""
import inspect
import types

import pytest

import xmpp
from ui.dialogs import settings as ui_settings


def _w():
    return object.__new__(xmpp.MainWindow)


# ── Açılışta okunan tercihler ────────────────────────────────────────────────

def test_saved_prefs_are_loaded_at_startup(monkeypatch):
    monkeypatch.setattr(xmpp, "_current_lang", "tr")
    w = _w()
    xmpp.MainWindow._load_saved_prefs(w, {
        "notifications": False, "sounds": False,
        "default_encryption": "omemo", "default_disappear": 300,
        "encrypted_rooms": ["gizli@conf"], "language": "en"})
    assert w._notify_enabled is False
    assert w._sound_enabled is False
    assert w._default_encryption == "omemo"
    assert w._default_disappear == 300
    assert w._encrypted_rooms == {"gizli@conf"}
    assert xmpp._current_lang == "en"


def test_saved_prefs_defaults(monkeypatch):
    monkeypatch.setattr(xmpp, "_current_lang", "tr")
    w = _w()
    xmpp.MainWindow._load_saved_prefs(
        w, {"language": "xx", "default_disappear": "abc"})
    assert w._notify_enabled is True and w._sound_enabled is True
    assert w._default_encryption == "none"
    assert w._default_disappear == 0
    assert w._encrypted_rooms == set()
    assert xmpp._current_lang == "tr"


@pytest.mark.parametrize("cfg, expected", [
    ({}, []),
    ({"font_size": 12}, [(None, 12)]),
    ({"font_family": "Inter", "font_size": 11}, [("Inter", 11)]),
])
def test_font_prefs_restored_only_when_saved(cfg, expected):
    w = _w()
    calls = []
    w._apply_font_settings = lambda family=None, size=None: calls.append(
        (family, size))
    xmpp.MainWindow._restore_font_prefs(w, cfg)
    assert calls == expected


def _status_win(monkeypatch, cfg):
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    w = _w()
    sent, labels = [], []
    w.bot = types.SimpleNamespace(
        set_status_message=lambda text, show: sent.append((text, show)))
    w._status_label = types.SimpleNamespace(
        config=lambda **kw: labels.append(kw["text"]))
    w.status_var = types.SimpleNamespace(set=lambda v: None)
    return w, sent, labels


def test_status_message_restored_on_connect(monkeypatch):
    w, sent, labels = _status_win(
        monkeypatch, {"status_text": "Toplantıda", "presence_show": "dnd"})
    xmpp.MainWindow._restore_status_prefs(w)
    assert sent == [("Toplantıda", "dnd")]
    assert labels == ["● Meşgul"]
    assert w._my_show == "dnd"


def test_status_text_only_keeps_online_label(monkeypatch):
    w, sent, labels = _status_win(monkeypatch, {"status_text": "Buradayım"})
    xmpp.MainWindow._restore_status_prefs(w)
    assert sent == [("Buradayım", "chat")]
    assert labels == []


def test_no_saved_status_sends_nothing(monkeypatch):
    w, sent, labels = _status_win(monkeypatch, {"presence_show": "chat"})
    xmpp.MainWindow._restore_status_prefs(w)
    assert sent == [] and labels == []


def test_connected_handler_restores_status():
    src = inspect.getsource(xmpp.MainWindow._handle)
    assert "self._restore_status_prefs()" in src


# ── Kaydet: açık sohbetin şifrelemesine dokunmaz ─────────────────────────────

def _settings_values(**over):
    """ui/dialogs/settings'in "Kaydet"te topladığı değerler."""
    v = {"notifications": True, "sounds": True, "status_text": "",
         "presence_show": "chat", "accounts": [], "auto_login": False,
         "theme": "koyu", "font_size": 10, "font_family": "Cantarell",
         "language": "tr", "send_read_receipts": True, "send_typing": True,
         "default_disappear": 0, "auto_rejoin": True, "idle_after_min": 5,
         "compact_mode": False, "default_encryption": "none",
         "download_dir": "/tmp/indir", "ft_auto_accept": False,
         "ft_block_size": "4096", "ft_warn_mb": "50"}
    v.update(over)
    return v


def _apply_settings(monkeypatch, values, w=None):
    saved = []
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", saved.append)
    monkeypatch.setattr(xmpp, "_apply_color_theme", lambda name: None)
    monkeypatch.setattr(xmpp, "_current_lang", "tr")
    w = w or _w()
    w.bot = None
    w._apply_auto_login = lambda cfg, on: None
    w._refresh_theme = lambda: None
    w._apply_font_settings = lambda **k: None
    xmpp.MainWindow._settings_apply(w, values)
    return w, saved[0]


def test_settings_save_does_not_change_open_chat_encryption(monkeypatch):
    w = _w()
    w._encryption_mode = types.SimpleNamespace(
        set=lambda v: pytest.fail("açık sohbetin şifrelemesi değişti"))
    w, cfg = _apply_settings(
        monkeypatch, _settings_values(default_encryption="omemo"), w)
    assert w._default_encryption == "omemo"
    assert cfg["default_encryption"] == "omemo"


def test_settings_save_applies_default_disappear_live(monkeypatch):
    w, cfg = _apply_settings(monkeypatch, _settings_values(default_disappear=300))
    assert w._default_disappear == 300 and cfg["default_disappear"] == 300


def test_settings_save_validates_file_transfer_fields(monkeypatch):
    w, cfg = _apply_settings(monkeypatch, _settings_values(
        download_dir="  ", ft_block_size="abc", ft_warn_mb="0"))
    assert cfg["ft_block_size"] == 4096 and cfg["ft_warn_mb"] == 1
    assert cfg["download_dir"].endswith("Downloads")
    assert w._ft_block_size == 4096 and w._ft_warn_mb == 1


def test_settings_sound_default_matches_runtime_default():
    src = inspect.getsource(ui_settings.show_settings)
    assert 'cfg.get("sounds", True)' in src


@pytest.mark.parametrize("key", ["carbons", "mam_enabled", "stream_management"])
def test_dead_protocol_toggles_removed(key):
    for fn in (ui_settings.show_settings, xmpp.MainWindow._settings_apply):
        assert f'"{key}"' not in inspect.getsource(fn)


# ── Kaybolan mesajlar: varsayılan süre ───────────────────────────────────────

@pytest.mark.parametrize("per_chat, default, expected", [
    ({}, 300, 300),                 # sohbete özel seçim yok → varsayılan
    ({"ali@x": 30}, 300, 30),       # sohbete özel seçim kazanır
    ({"ali@x": 0}, 300, 0),         # açıkça kapatılmışsa kapalı kalır
])
def test_chat_ttl_falls_back_to_default(per_chat, default, expected):
    w = _w()
    w._disappearing_ttl = per_chat
    w._default_disappear = default
    assert xmpp.MainWindow._chat_ttl(w, "ali@x") == expected


def test_chat_ttl_without_default_attribute_is_off():
    w = _w()
    w._disappearing_ttl = {}
    assert xmpp.MainWindow._chat_ttl(w, "ali@x") == 0


def test_disappearing_dialog_shows_effective_ttl(monkeypatch):
    seen = []
    monkeypatch.setattr(xmpp._ui_chat_options, "show_disappearing",
                        lambda root, ttl, cb: seen.append(ttl))
    w = _w()
    w.root, w.active = "ROOT", "ali@x"
    w._disappearing_ttl, w._default_disappear = {}, 3600
    xmpp.MainWindow._disappearing_dialog(w)
    assert seen == [3600]


@pytest.mark.parametrize("method", ["_send_message", "_handle"])
def test_send_and_receive_use_effective_ttl(method):
    src = inspect.getsource(getattr(xmpp.MainWindow, method))
    assert "_disappearing_ttl.get(" not in src
    assert "self._chat_ttl(" in src
