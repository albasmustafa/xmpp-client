"""💬 Hazır yanıtlar: çekirdek (xmppcore/canned), masaüstü ✨ menüsü ve
düzenleyici, web komutları (get_canned / set_canned).

Sözleşme: seçilen yanıt giriş kutusuna eklenir, kendiliğinden gönderilmez;
masaüstü ve web aynı config listesini ("canned_replies") kullanır.
"""
import os
import sys
import tkinter as tk

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_webapp import CFG, session  # noqa: E402,F401  (fixture)

import xmpp  # noqa: E402
from xmppcore import canned  # noqa: E402

# ── Çekirdek ────────────────────────────────────────────────────────────────


def test_normalize_one_line_dedupe_and_limits():
    items = ["  Merhaba,\n nasılsın? ", "", 7, None, "Merhaba, nasılsın?",
             "x" * 900]
    out = canned.normalize(items)
    assert out == ["Merhaba, nasılsın?", "x" * canned.MAX_LEN]
    many = [f"yanıt {i}" for i in range(canned.MAX_ITEMS + 10)]
    assert len(canned.normalize(many)) == canned.MAX_ITEMS
    for bad in (None, "metin", {"a": 1}, 3):
        assert canned.normalize(bad) == []


def test_editor_round_trip_one_reply_per_line():
    text = "Toplantı 15:00'te\n\n   \nTeşekkürler!\r\nToplantı 15:00'te\n"
    items = canned.parse_editor(text)
    assert items == ["Toplantı 15:00'te", "Teşekkürler!"]
    assert canned.parse_editor(canned.editor_text(items)) == items
    assert canned.parse_editor(None) == []


def test_load_and_set_items_use_shared_config_key():
    cfg = {"canned_replies": ["a", "a", " b "], "diğer": 1}
    assert canned.load(cfg) == ["a", "b"]
    assert canned.load({}) == [] and canned.load(None) == []
    assert canned.set_items(cfg, ["c"]) is cfg
    assert cfg == {"canned_replies": ["c"], "diğer": 1}


def test_label_shortens_long_replies():
    assert canned.label("kısa") == "kısa"
    long = "Bu çok uzun bir hazır yanıt " * 5
    lab = canned.label(long, width=20)
    assert len(lab) <= 20 and lab.endswith("…")


@pytest.mark.parametrize("current,expected", [
    ("", "Selam"), ("Merhaba", " Selam"), ("Merhaba ", "Selam"),
])
def test_joined_never_glues_to_a_word(current, expected):
    assert canned.joined(current, "Selam") == expected


# ── Masaüstü ────────────────────────────────────────────────────────────────


class _Menu:
    made = []

    def __init__(self, parent=None, **k):
        self.entries = []
        _Menu.made.append(self)

    def add_command(self, **k):
        self.entries.append(("cmd", k.get("label"), k.get("command"),
                             k.get("state")))

    def add_cascade(self, **k):
        self.entries.append(("cascade", k.get("label"), k.get("menu")))

    def add_separator(self):
        self.entries.append(("sep",))

    def tk_popup(self, x, y):
        pass

    def labels(self):
        return [e[1] if e[0] != "sep" else "---" for e in self.entries]


def _win(monkeypatch, items):
    _Menu.made = []
    monkeypatch.setattr(xmpp.tk, "Menu", _Menu)
    monkeypatch.setattr(xmpp, "_load_config_cached",
                        lambda: {"canned_replies": items})
    w = object.__new__(xmpp.MainWindow)
    w.root = None
    w.active = "ali@x"
    return w


def test_canned_menu_inserts_choice_and_offers_editor(monkeypatch):
    w = _win(monkeypatch, ["Toplantı 15:00'te", "Teşekkürler!"])
    inserted, opened = [], []
    w._canned_insert = inserted.append
    w._canned_dialog = lambda: opened.append(True)
    sub = xmpp.MainWindow._canned_menu(w, None)
    assert sub.labels() == ["Toplantı 15:00'te", "Teşekkürler!", "---",
                            "✏ Düzenle…"]
    sub.entries[1][2]()
    assert inserted == ["Teşekkürler!"]      # eklenir, gönderilmez
    sub.entries[-1][2]()
    assert opened == [True]


def test_canned_menu_empty_list_shows_disabled_hint(monkeypatch):
    w = _win(monkeypatch, [])
    sub = xmpp.MainWindow._canned_menu(w, None)
    assert sub.entries[0][1] == "Henüz hazır yanıt yok"
    assert sub.entries[0][3] == "disabled"
    assert sub.labels()[-1] == "✏ Düzenle…"


def test_composer_menu_has_canned_cascade_after_suggest(monkeypatch):
    w = _win(monkeypatch, ["Selam"])
    w._ai_speaking = lambda: False
    xmpp.MainWindow._ai_composer_menu(w, type("E", (), {"x_root": 1,
                                                       "y_root": 2})())
    top = _Menu.made[0]
    labels = top.labels()
    assert labels.index("💬 Hazır yanıtlar") == labels.index("💡 Yanıt öner") + 1


@pytest.mark.parametrize("current,expected", [
    ("", "Selam"), ("Merhaba", "Merhaba Selam"), ("Merhaba ", "Merhaba Selam"),
])
def test_canned_insert_appends_without_sending(current, expected):
    w = object.__new__(xmpp.MainWindow)
    box = {"text": current}
    sent = []
    w._ai_composer_text = lambda: box["text"]
    w._ai_set_composer_text = lambda t: box.update(text=t)
    w._send_message = lambda *a: sent.append(a)
    xmpp.MainWindow._canned_insert(w, "Selam")
    assert box["text"] == expected and sent == []


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("ekran yok")
    r.withdraw()
    yield r
    r.destroy()


def _walk(w):
    yield w
    for child in w.winfo_children():
        yield from _walk(child)


def test_canned_dialog_saves_one_reply_per_line(root, monkeypatch):
    saved, toasts = {}, []
    monkeypatch.setattr(xmpp, "_load_config",
                        lambda: {"canned_replies": ["Eski yanıt"], "a": 1})
    monkeypatch.setattr(xmpp, "_save_config", saved.update)
    w = object.__new__(xmpp.MainWindow)
    w.root = root
    w._show_toast = lambda *a: toasts.append(a)
    dlg = xmpp.MainWindow._canned_dialog(w)   # gösterilmeden (idle yok)
    box = next(x for x in _walk(dlg) if x.winfo_class() == "Text")
    assert box.get("1.0", "end-1c") == "Eski yanıt"
    box.delete("1.0", "end")
    box.insert("1.0", "Merhaba\n\n  Toplantı   15:00'te \nMerhaba")
    save = next(x for x in _walk(dlg) if x.winfo_class() == "TButton"
                and str(x.cget("text")) == "Kaydet")
    save.invoke()
    assert saved == {"canned_replies": ["Merhaba", "Toplantı 15:00'te"],
                     "a": 1}
    assert toasts == [("💬 Hazır yanıtlar", "Kaydedilen yanıt: 2")]
    assert not dlg.winfo_exists()


# ── Web ─────────────────────────────────────────────────────────────────────


def test_web_get_and_set_canned(session):  # noqa: F811
    CFG["canned_replies"] = ["Selam"]
    assert session.command("get_canned", {}) == {"ok": True,
                                                 "items": ["Selam"]}
    r = session.command("set_canned", {"text": "Bir\n\nİki\nBir"})
    assert r == {"ok": True, "items": ["Bir", "İki"]}
    assert CFG["canned_replies"] == ["Bir", "İki"]
    assert session.command("get_canned", {})["items"] == ["Bir", "İki"]


@pytest.mark.parametrize("args", [{}, {"text": None}, {"text": ["a"]}])
def test_web_set_canned_rejects_non_text(session, args):  # noqa: F811
    CFG["canned_replies"] = ["Selam"]
    assert session.command("set_canned", args)["ok"] is False
    assert CFG["canned_replies"] == ["Selam"]


def test_web_canned_ui_wiring():
    from webapp import server as srv
    js = (srv.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for el in ('id="btn-canned"', 'id="canned-menu"', 'id="dlg-canned"',
               'id="canned-text"', 'id="canned-save"'):
        assert el in html
    insert = js.split("function insertCanned(", 1)[1].split("\nfunction ", 1)[0]
    assert "wsSend(" not in insert            # eklemek göndermek değildir
    assert 'wsSend("get_canned"' in js and 'wsSend("set_canned"' in js
