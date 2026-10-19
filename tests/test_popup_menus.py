"""Açılır menüler dışarı tıklayınca kapanmalı.

Kanıt: X11'de `tk_popup` beklemeden döner ve menünün dışarı tıklamayı
görmesini sağlayan global grab'i kurar (tk/menu.tcl ::tk_popup). Hemen
ardından `grab_release()` çağrılınca grab kalkıyor, menü bir öğe seçilene dek
açık kalıyordu (gerçek Tk: `grab_current()` None). Bu dosya MainWindow
menülerini sınar ve deseni kod tabanında yasaklar.
"""
import glob
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Menu:
    made = []

    def __init__(self, *a, **k):
        self.calls = []
        _Menu.made.append(self)

    def add_command(self, **k):
        pass

    def add_separator(self):
        pass

    def tk_popup(self, x, y):
        self.calls.append("popup")

    def grab_release(self):
        self.calls.append("release")


def _menus(monkeypatch):
    _Menu.made = []
    monkeypatch.setattr(xmpp.tk, "Menu", _Menu)
    return _Menu.made


def test_sidebar_menu_keeps_grab(monkeypatch):
    made = _menus(monkeypatch)
    w = object.__new__(xmpp.MainWindow)
    w.active = "ali@x"
    w.root = None
    xmpp.MainWindow._sidebar_menu(w, types.SimpleNamespace(x_root=1,
                                                           y_root=2))
    assert [m.calls for m in made] == [["popup"]]


def test_send_file_menu_keeps_grab(monkeypatch):
    made = _menus(monkeypatch)
    w = object.__new__(xmpp.MainWindow)
    w.active = "ali@x"
    w.rooms = {}
    w.root = types.SimpleNamespace(winfo_pointerx=lambda: 1,
                                   winfo_pointery=lambda: 2)
    xmpp.MainWindow._send_file(w)
    assert [m.calls for m in made] == [["popup"]]


def test_no_grab_release_after_popup_anywhere():
    files = [os.path.join(ROOT, "xmpp.py")] + glob.glob(
        os.path.join(ROOT, "ui", "**", "*.py"), recursive=True)
    offenders = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                code = line.split("#", 1)[0]
                if re.search(r"\.grab_release\(", code):
                    offenders.append(f"{os.path.relpath(path, ROOT)}:{n}")
    assert offenders == []
