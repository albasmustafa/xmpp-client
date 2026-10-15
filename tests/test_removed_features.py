"""Kaldırılan özellikler; geri gelirse bu testler yakalar.

- Sesli arama: medya akışı yoktu. ⋮ → Sesli Arama karşıya "Sesli arama
  daveti (deneysel)" metni gönderip sahte bir süre sayıyordu; başlıktaki 📞
  düğmesi yalnız "gelecek sürümlerde eklenecek" kutusu açıyordu.
- Ekran paylaşımı: gerçek paylaşım değildi. 5 sn'de bir ekran görüntüsünü
  HTTP Upload ile ayrı sohbet mesajı olarak yüklüyordu ve hedefi her karede
  `self.active`'ten okuduğu için sohbet değişince görüntüler başka kişiye
  gidiyordu.
- Eklenti sistemi ve webhook alıcısı: hiç kullanılmamıştı; eklenti sistemi
  seçilen herhangi bir .py dosyasını açılışta çalıştırıyordu.
"""
import inspect

import pytest

import xmpp
from ui.chat import shell as ui_shell


def _keys(spec):
    out = []
    for item in spec:
        if item[0] == "item":
            out.append(item[2])
        elif item[0] == "menu":
            out += _keys(item[2])
    return out


@pytest.mark.parametrize("is_room", [False, True])
def test_header_menu_has_no_call_command(is_room):
    spec = xmpp._chat_header_menu_spec(is_room=is_room, compact=False)
    assert "call" not in _keys(spec)
    labels = [item[1] for item in spec if item[0] == "menu"]
    assert "📤 Paylaşım" in labels                 # alt menü adı içeriğine uysun
    assert not any("Arama" in lbl for lbl in labels)


@pytest.mark.parametrize("name", ["_jingle_call_dialog", "_voip_call",
                                  "_check_gstreamer"])
def test_call_methods_removed(name):
    assert not hasattr(xmpp.MainWindow, name)


@pytest.mark.parametrize("is_room", [False, True])
def test_header_menu_has_no_screen_share(is_room):
    spec = xmpp._chat_header_menu_spec(is_room=is_room, compact=False)
    assert "screen_share" not in _keys(spec)


@pytest.mark.parametrize("name", [
    "_screen_share_dialog",
    "_plugin_manager_dialog", "_execute_plugin", "_load_enabled_plugins",
    "_webhook_dialog"])
def test_removed_feature_methods_gone(name):
    assert not hasattr(xmpp.MainWindow, name)


def test_sidebar_menu_has_no_plugins():
    keys = [item[2] for item in xmpp._sidebar_menu_spec(has_active_chat=True)
            if item[0] == "item"]
    assert "plugins" not in keys


def test_rest_api_has_no_webhook_route():
    assert "/api/webhook/" not in inspect.getsource(xmpp.MainWindow)


def test_chat_header_has_no_call_button():
    src = inspect.getsource(ui_shell)
    assert "on_voip" not in src and "📞" not in src
