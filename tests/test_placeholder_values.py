"""İpucu metinli alanlar (PlaceholderEntry) boşken ipucu değer sayılmamalı.

Kanıt: PlaceholderEntry ipucunu bağlı StringVar'a yazar; `var.get()` boş alanda
ipucunu döndürür. Durum alanı boşken kaydetmek kişilere "Durum yazın..."
yayınlıyordu; konum alanları boşken İstanbul (41.0082, 28.9784) paylaşılıyordu.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

import pytest

import xmpp
from ui.dialogs import presence as ui_presence


@pytest.fixture()
def root(monkeypatch):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    r = tk.Tk()
    r.withdraw()
    xmpp._apply_theme()
    errors = []
    monkeypatch.setattr(ui_presence.messagebox, "showerror",
                        lambda *a, **k: errors.append(a))
    r.errors = errors
    yield r
    r.destroy()


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def _button(top, text):
    return next(b for b in _walk(top)
                if isinstance(b, ttk.Button) and b.cget("text") == text)


def _top(root):
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]


def test_empty_status_dialog_publishes_empty_status(root):
    got = []
    ui_presence.show_status(root, lambda text, show: got.append((text, show)))
    _button(_top(root), "Uygula").invoke()
    assert got == [("", "chat")]


def test_empty_location_is_not_published_as_istanbul(root):
    got = []
    ui_presence.show_location(root, lambda *a: got.append(a), lambda: None)
    _button(_top(root), "Paylaş").invoke()
    assert got == [] and root.errors            # "Geçersiz koordinatlar"


def test_location_with_empty_description_sends_empty_text(root):
    got = []
    ui_presence.show_location(root, lambda *a: got.append(a), lambda: None)
    top = _top(root)
    entries = [e for e in _walk(top) if isinstance(e, xmpp.PlaceholderEntry)]
    for e, val in zip(entries[:2], ("39.92", "32.85")):
        e._on_focus_in()
        e.insert(0, val)
    _button(top, "Paylaş").invoke()
    assert got == [(39.92, 32.85, "")]
