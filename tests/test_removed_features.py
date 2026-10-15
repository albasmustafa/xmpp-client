"""Çalışmayan sesli arama kaldırıldı; geri gelirse bu testler yakalar.

Medya akışı yoktu: ⋮ → Sesli Arama karşıya "Sesli arama daveti (deneysel)"
metni gönderip sahte bir süre sayıyordu; başlıktaki 📞 düğmesi yalnız
"gelecek sürümlerde eklenecek" kutusu açıyordu.
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


def test_chat_header_has_no_call_button():
    src = inspect.getsource(ui_shell)
    assert "on_voip" not in src and "📞" not in src
