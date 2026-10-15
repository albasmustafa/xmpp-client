"""☰ kenar çubuğu menü yapısının (saf veri) birim testleri."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


def _items(spec):
    return [item for item in spec if item[0] == "item"]


def _keys(spec):
    return [item[2] for item in _items(spec)]


def test_sidebar_spec_all_actions_present():
    """Eski araç çubuğu işlevleri + tema seçici menüde eksiksiz yer almalı."""
    keys = _keys(xmpp._sidebar_menu_spec(has_active_chat=True))
    assert keys == [
        "search_users", "groups",
        "discover_rooms", "bookmarks",
        "gif", "msg_search", "log", "rest_api",
        "reconnect", "theme", "settings",
    ]


def test_sidebar_spec_gif_requires_active_chat():
    """Sticker/GIF yalnızca aktif sohbet varken menüye girer."""
    assert "gif" not in _keys(xmpp._sidebar_menu_spec(has_active_chat=False))


def test_sidebar_spec_sections_in_order():
    """Bölüm başlıkları Kişiler → Odalar → Gelişmiş sırasında olmalı."""
    sections = [item[1] for item in xmpp._sidebar_menu_spec(has_active_chat=False)
                if item[0] == "section"]
    assert sections == [xmpp._t("contacts"), xmpp._t("rooms"), xmpp._t("advanced")]


def test_sidebar_spec_no_empty_labels_and_settings_last():
    spec = xmpp._sidebar_menu_spec(has_active_chat=True)
    for kind, *rest in spec:
        if kind == "item":
            assert rest[0].strip()
            assert rest[1]
    assert _items(spec)[-1][2] == "settings"


def test_sidebar_spec_language_switch(monkeypatch):
    """Dil değişince bölüm başlıkları da değişmeli."""
    monkeypatch.setattr(xmpp, "_current_lang", "en")
    sections = [item[1] for item in xmpp._sidebar_menu_spec(has_active_chat=False)
                if item[0] == "section"]
    assert sections == [xmpp._t("contacts"), xmpp._t("rooms"), xmpp._t("advanced")]
