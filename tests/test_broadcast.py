"""Toplu mesaj: her alıcıya giden mesaj kimlikli (mid) gönderilip saklanır.

Kanıt: _broadcast_dialog send_chat'i mid'siz çağırıyor, kaydı da mid'siz
yazıyordu; bu mesajlar düzenlenemiyor, geri çekilemiyor ve sunucudan dönen
kimlikle eşleşmiyordu.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

import pytest

import xmpp


class _Bot:
    def __init__(self):
        self.sent = []

    def send_chat(self, to, body, encryption="none", mid=None):
        self.sent.append((to, body, encryption, mid))


@pytest.fixture()
def root(monkeypatch):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    r = tk.Tk()
    r.withdraw()
    xmpp._apply_theme()
    monkeypatch.setattr(xmpp, "_safe_grab_set", lambda *a, **k: None)
    monkeypatch.setattr(xmpp.messagebox, "showinfo", lambda *a, **k: None)
    yield r
    r.destroy()


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def test_broadcast_sends_and_stores_each_message_with_its_own_mid(root):
    win = object.__new__(xmpp.MainWindow)
    win.root, win.bot = root, _Bot()
    win._contacts = {"ali@x": "Ali", "ayse@x": "Ayşe"}
    win._encryption_mode = tk.StringVar(value="none")
    stored = []
    win._store = lambda target, body, **kw: stored.append((target, body, kw))
    win._broadcast_dialog()
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    next(e for e in _walk(top) if isinstance(e, ttk.Entry)).insert(0, "Toplantı")
    lb = next(w for w in _walk(top) if isinstance(w, tk.Listbox))
    lb.selection_set(0, 1)
    next(b for b in _walk(top) if isinstance(b, ttk.Button)).invoke()

    mids = [m for *_rest, m in win.bot.sent]
    assert all(mids) and len(set(mids)) == 2           # alıcı başına ayrı kimlik
    assert [(t, kw["mid"]) for t, _b, kw in stored] == [
        (to, mid) for to, _b, _e, mid in win.bot.sent]
