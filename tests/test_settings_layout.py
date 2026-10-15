"""Ayarlar penceresi (560×640, ölçek 1,5 → ~720 px ekran) sekmeleri sığmalı.

Ölçüm: not defterinde içerik için ~555 px kalıyor. Bağlantı (781) ve Hakkında
(759) sekmelerinin altı (PIN, Mesaj Geçmişini Sil…) hiç görünmüyordu;
Görünüm (586) alttan kırpılıyordu. Bütçeyi aşan sekme kaydırılabilir olmalı.
"""
import os
import sys
import tkinter as tk
from unittest import mock

import pytest

import xmpp

BUDGET = 540   # ~555 px görünür alan − pay


@pytest.fixture()
def settings_top(monkeypatch):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    root = tk.Tk()
    root.withdraw()
    xmpp._apply_theme()
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_safe_grab_set", lambda *a, **k: None)

    class _W(xmpp.MainWindow):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return mock.MagicMock(name=name)

    w = object.__new__(_W)
    w.root, w.jid = root, "ben@example.com"
    w._avatars, w._photo_refs = {}, []
    w._last_ping_ms, w._compact_mode = 0, False
    w.bot = mock.MagicMock(password="x", custom_address=None, omemo_ready=False)
    w._settings_dialog()
    top = next(c for c in root.winfo_children() if isinstance(c, tk.Toplevel))
    top.withdraw()
    top.update_idletasks()
    yield top
    root.destroy()


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def test_every_settings_tab_fits_or_scrolls(settings_top):
    nb = next(x for x in _walk(settings_top) if x.winfo_class() == "TNotebook")
    too_tall = []
    for tab_id in nb.tabs():
        frame = nb.nametowidget(tab_id)
        scrolls = any(isinstance(x, tk.Canvas) for x in _walk(frame))
        if frame.winfo_reqheight() > BUDGET and not scrolls:
            too_tall.append((nb.tab(tab_id, "text").strip(),
                             frame.winfo_reqheight()))
    assert too_tall == []
