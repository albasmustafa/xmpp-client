"""⋮ sohbet başlığı menüsü: sadeleştirme hiçbir komutu kaybetmez.

Kanıtlar:
- Eski düz menüdeki her komut (24 + ✨ AI alt menüsü) yeni gruplu yapıda
  aynı etiketle ve aynı hedef metoda bağlı olarak durur; fazlası yoktur.
  (Sesli arama medya akışı olmadığı için kaldırıldı: test_removed_features.)
- Üst düzey kısa kalır (sık kullanılanlar + konu başlıklı alt menüler).
- Oda yönetimi yalnız odada, kompakt mod etiketi duruma göre görünür.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _Cap  # noqa: E402

import xmpp  # noqa: E402

# Eski (sadeleştirme öncesi) menünün etiket → hedef metot eşlemesi.
OLD_MENU = {
    "👤 Profil": "_profile_card",
    "🔒 OMEMO Parmak İzleri": "_omemo_fingerprint_dialog",
    "📌 Sabitlenmiş Mesajlar": "_show_pinned",
    "🔎 Mesaj Ara": "_search_messages_dialog",
    "⏱ Kaybolan Mesajlar": "_disappearing_dialog",
    "📜 Daha Eski Mesajları Yükle (MAM)": "_load_older_mam",
    "📤 Sohbeti Dışa Aktar": "_export_chat",
    "📍 Konum Paylaş": "_location_dialog",
    "💬 Durum Mesajı": "_status_dialog",
    "🚫 Engelli Kişiler": "_blocking_dialog",
    "🖼 Arka Plan Değiştir": "_wallpaper_dialog",
    "🔐 OMEMO QR Doğrulama": "_omemo_qr_dialog",
    "💾 Yedekleme / Geri Yükleme": "_backup_dialog",
    "📐 Kompakt Moda Geç": "_toggle_compact_mode",
    "⌨ Klavye Kısayolları": "_shortcuts_dialog",
    "⏰ Mesaj Zamanla": "_schedule_message_dialog",
    "📢 Toplu Mesaj": "_broadcast_dialog",
    "🗑 Geçmişi Sil": "_clear_history_dialog",
    "🔧 Oda Yönetimi": "_room_admin_dialog",
    "📺 Yeni Sekmede Aç": "_open_chat_tab",
    "📺 Bölünmüş Ekran": "_split_view_dialog",
    "🖥 Ekran Paylaş": "_screen_share_dialog",
    "📊 Anket Oluştur": "_poll_dialog",
    "📖 Hikaye Paylaş": "_story_dialog",
}


class _Menu:
    def __init__(self, *a, **k):
        self.items = []

    def add_command(self, label=None, command=None, **k):
        self.items.append(("cmd", label, command))

    def add_cascade(self, label=None, menu=None, **k):
        self.items.append(("sub", label, menu))

    def add_separator(self):
        self.items.append(("sep", None, None))

    def tk_popup(self, x, y):
        pass


def _build(monkeypatch, *, room=False, compact=False):
    created = []

    def factory(*a, **k):
        created.append(_Menu())
        return created[-1]
    monkeypatch.setattr(xmpp.tk, "Menu", factory)
    w = object.__new__(xmpp.MainWindow)
    w.active = "oda@conf.x" if room else "ali@x"
    w.rooms = {"oda@conf.x": {}} if room else {}
    w._compact_mode = compact
    w.root = None
    ai_menu = _Menu()
    w._ai_build_chat_menu = lambda parent: ai_menu
    for method in set(OLD_MENU.values()):
        setattr(w, method, _Cap())
    xmpp.MainWindow._chat_header_menu(w, types.SimpleNamespace(
        x_root=0, y_root=0))
    return w, created[0], ai_menu         # ilk kurulan: ana menü


def _commands(menu):
    for kind, label, target in menu.items:
        if kind == "cmd":
            yield label, target
        elif kind == "sub" and isinstance(target, _Menu):
            yield from _commands(target)


def test_every_old_command_still_reachable(monkeypatch):
    w, menu, ai_menu = _build(monkeypatch, room=True)
    found = dict(_commands(menu))
    assert set(found) == set(OLD_MENU)            # eksik de fazla da yok
    for label, cmd in found.items():
        cmd()
        target = getattr(w, OLD_MENU[label])
        assert len(target.calls) >= 1, label
    assert w._profile_card.calls[0] == (("oda@conf.x",), {})
    assert w._omemo_fingerprint_dialog.calls[0] == (("oda@conf.x",), {})
    assert any(kind == "sub" and target is ai_menu
               for kind, _l, target in menu.items)


def test_top_level_is_short_and_grouped(monkeypatch):
    _w, menu, _ai = _build(monkeypatch)
    top = [label for kind, label, _t in menu.items if kind != "sep"]
    assert top == ["👤 Profil", "🔎 Mesaj Ara", "📌 Sabitlenmiş Mesajlar",
                   f"✨ {xmpp._t('ai_assistant')}", "💬 Sohbet",
                   "📤 Paylaşım", "🔒 Güvenlik", "🪟 Görünüm",
                   "⚙ Diğer"]


def test_room_admin_and_compact_label(monkeypatch):
    _w, menu, _ai = _build(monkeypatch, room=False, compact=True)
    labels = dict(_commands(menu))
    assert "🔧 Oda Yönetimi" not in labels
    assert "📐 Rahat Moda Geç" in labels and "📐 Kompakt Moda Geç" not in \
        labels


def test_no_active_chat_no_menu(monkeypatch):
    monkeypatch.setattr(xmpp.tk, "Menu", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("menü kurulmamalı")))
    w = object.__new__(xmpp.MainWindow)
    w.active = None
    assert xmpp.MainWindow._chat_header_menu(w) is None
