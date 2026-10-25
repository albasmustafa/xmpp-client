"""Arayüz dili (Faz 1 yaprak modülü).

Gettext tarzı: Türkçe arayüz metninin kendisi anahtardır. `tr(metin)` seçili
dilin kataloğundaki (`xmppcore/locale_<kod>.py`, `CATALOG`) karşılığı, yoksa
İngilizcesini (`locale_en.EN`), o da yoksa metnin kendisini döndürür;
Türkçede metin aynen döner. Kataloglar ilk kullanımda yüklenir. Değişken
içeren metinler şablonla çevrilir: `tr("{} mesaj").format(n)` — şablon
kataloğun anahtarıdır.

Modül düzeyindeki sabitler (menü listeleri, durum adları) içe aktarılırken
değil kullanıldıkları yerde çevrilir: dil, ayarlar okunduktan sonra seçilir.
"""
import importlib

from xmppcore.locale_en import EN

# Kod → dilin kendi adı (Ayarlar'daki seçici bu sırayla gösterir)
LANGUAGES = {
    "tr": "Türkçe", "en": "English", "de": "Deutsch", "fr": "Français",
    "es": "Español", "it": "Italiano", "pt": "Português", "nl": "Nederlands",
    "pl": "Polski", "ru": "Русский", "uk": "Українська", "zh": "简体中文",
    "ja": "日本語", "ko": "한국어",
}
# AI yanıt dili (modele İngilizce adla verilir); Türkçe arayüzün eski
# varsayılanı "Türkçe" korunur
AI_LANGUAGE_NAMES = {
    "tr": "Türkçe", "en": "English", "de": "German", "fr": "French",
    "es": "Spanish", "it": "Italian", "pt": "Portuguese", "nl": "Dutch",
    "pl": "Polish", "ru": "Russian", "uk": "Ukrainian",
    "zh": "Simplified Chinese", "ja": "Japanese", "ko": "Korean",
}
DEFAULT_LANGUAGE = "tr"

_lang = DEFAULT_LANGUAGE
_catalogs = {"en": EN}


def catalog(lang) -> dict:
    """`lang` kataloğu (ilk kullanımda içe aktarılır; Türkçe için boş)."""
    if lang == DEFAULT_LANGUAGE or lang not in LANGUAGES:
        return {}
    cat = _catalogs.get(lang)
    if cat is None:
        cat = importlib.import_module(f"xmppcore.locale_{lang}").CATALOG
        _catalogs[lang] = cat
    return cat


def set_language(lang) -> str:
    """Arayüz dilini seç; bilinmeyen değer Türkçeye düşer."""
    global _lang
    _lang = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    return _lang


def language() -> str:
    return _lang


def N_(text):
    """Modül düzeyindeki görüntü metnini işaretle (çevirmez): değer
    kullanıldığı yerde `tr()` ile çevrilir; katalog denetimi bu işareti okur."""
    return text


def tr(text):
    """Arayüz metnini seçili dile çevir (eksikse İngilizce, o da yoksa aynen)."""
    return tr_in(_lang, text)


def tr_in(lang, text):
    """Metni seçili dilden bağımsız olarak `lang` dilinde ver."""
    if lang == DEFAULT_LANGUAGE or not text:
        return text
    found = catalog(lang).get(text)
    return found if found is not None else EN.get(text, text)


# Anahtarlı eski çağrılar (`t("copy")`): ui/chat görünümleri çevirmeni
# parametre olarak alır (yalnız tkinter/collections sözleşmesi).
KEYS = {
    "ai_assistant": "AI Asistanı",
    "copy": "Kopyala",
    "delete": "Sil",
    "discover_rooms": "Oda Keşfet",
    "edit": "Düzenle",
    "forward": "İlet",
    "join_room": "Odaya Katıl",
    "message_placeholder": "Mesaj yazın...",
    "pin": "Sabitle",
    "react": "Tepki Ekle",
    "reply": "Yanıtla",
    "select_chat": "Bir sohbet seçin",
    "select_contact": "Bir kişi veya oda seçerek konuşmaya başlayın",
    "start_chat": "Sohbet Başlat",
    "start_conversation": "Sohbete Başlayın",
    "sticker_gif": "Sticker/GIF",
    "typing": "yazıyor",
    "filter_all": "Tümü",
    "filter_unread": "Okunmamış",
    "filter_pinned": "Sabitlenmiş",
}


def t(key: str) -> str:
    """Anahtarlı çeviri: anahtar → Türkçe metin → seçili dil."""
    return tr(KEYS.get(key, key))
