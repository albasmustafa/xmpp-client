"""Durum sözlüğü her yerde aynı olmalı; Durum Mesajı penceresi seçenekleri kesmemeli.

Kanıt: Durum Mesajı penceresi (340 px) dört seçeneği yan yana diziyordu;
"Uzun Süre Uzakta" sağdan kesiliyordu. Aynı durumlar yerine göre farklı
adlanıyordu: menü Çevrimiçi/Meşgul (`agent.STATUS_LABELS`), Durum Mesajı
penceresi Müsait/Rahatsız Etmeyin, Ayarlar Müsait, web arayüzü
"Çok uzakta"/"Rahatsız etmeyin".
"""
import os
import re
import sys
import tkinter as tk
from pathlib import Path

import pytest

import xmpp
from ui.dialogs import presence as ui_presence
from xmppcore.agent import STATUS_LABELS

ROOT = Path(__file__).resolve().parent.parent
# Durum Mesajı / Ayarlar "chat" yayınlar; menü ve web "online" der: aynı ad
SHOW_ORDER = [("chat", "online"), ("away", "away"), ("dnd", "dnd"), ("xa", "xa")]
DIALOG_WIDTH = 340      # presence.show_status içindeki geometry


@pytest.fixture()
def root():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    r = tk.Tk()
    r.withdraw()
    xmpp._apply_theme()
    yield r
    r.destroy()


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def _radios(top):
    return [w for w in _walk(top) if isinstance(w, tk.Radiobutton)]


def test_status_dialog_uses_menu_vocabulary(root):
    ui_presence.show_status(root, lambda *a: None)
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    got = [(r.cget("value"), r.cget("text")) for r in _radios(top)]
    assert got == [(val, STATUS_LABELS[key]) for val, key in SHOW_ORDER]


def test_status_dialog_options_fit_its_width(root):
    ui_presence.show_status(root, lambda *a: None)
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    top.update_idletasks()
    assert len(_radios(top)) == 4
    # Yan yana dört seçenek 426 px istiyordu: _fit_content pencereyi
    # genişletmeden (kesmeden) sığmalı
    assert top.winfo_reqwidth() <= DIALOG_WIDTH, top.winfo_reqwidth()


def test_settings_presence_radios_use_menu_vocabulary():
    src = (ROOT / "ui/dialogs/settings.py").read_text(encoding="utf-8")
    assert "Müsait" not in src and "Uzun Süre Uzakta" not in src
    assert "STATUS_OPTIONS" in src


def test_web_presence_select_uses_menu_vocabulary():
    html = (ROOT / "webapp/static/index.html").read_text(encoding="utf-8")
    sel = re.search(r'<select id="presence-select".*?</select>', html, re.S)
    opts = re.findall(r'<option value="(\w+)">([^<]+)</option>', sel.group(0))
    assert dict(opts) == STATUS_LABELS


def test_web_chat_subtitle_uses_menu_vocabulary():
    js = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    m = re.search(r"const awayTxt = \{(.*?)\};", js, re.S)
    pairs = dict(re.findall(r'(\w+): _t\("([^"]+)"\)', m.group(1)))
    assert pairs == {"away": STATUS_LABELS["away"].lower(),
                     "xa": STATUS_LABELS["xa"].lower(),
                     "dnd": STATUS_LABELS["dnd"].lower(),
                     "chat": STATUS_LABELS["online"].lower()}


def test_i18n_has_no_second_status_vocabulary():
    """Kanıt (2026-10-23 incelemesi): i18n'de hiçbir yerden okunmayan
    `available`/`dnd_status`/`xa_status` duruyordu; İngilizcesi
    "Available"/"Extended Away" ile menü sözlüğünden ayrışıyordu. Durum
    adlarının tek kaynağı `STATUS_LABELS`'tır."""
    from xmppcore.i18n import KEYS
    assert not {"available", "dnd_status", "xa_status"} & set(KEYS)
    for key, show in (("online", "online"), ("away", "away"), ("busy", "dnd")):
        assert KEYS.get(key, STATUS_LABELS[show]) == STATUS_LABELS[show]
