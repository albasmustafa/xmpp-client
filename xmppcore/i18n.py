"""Arayüz dili (Faz 1 yaprak modülü).

Gettext tarzı: Türkçe arayüz metninin kendisi anahtardır. `tr(metin)` dil
İngilizceyken `locale_en.EN` kataloğundaki karşılığı, yoksa metnin kendisini
döndürür; Türkçede metin aynen döner. Değişken içeren metinler şablonla
çevrilir: `tr("{} mesaj").format(n)` — şablon kataloğun anahtarıdır.

Modül düzeyindeki sabitler (menü listeleri, durum adları) içe aktarılırken
değil kullanıldıkları yerde çevrilir: dil, ayarlar okunduktan sonra seçilir.
"""
from xmppcore.locale_en import EN

LANGUAGES = {"tr": "Türkçe", "en": "English"}
DEFAULT_LANGUAGE = "tr"

_lang = DEFAULT_LANGUAGE


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
    """Arayüz metnini seçili dile çevir (bilinmeyen metin aynen döner)."""
    if _lang == DEFAULT_LANGUAGE or not text:
        return text
    return EN.get(text, text)


def tr_in(lang, text):
    """Metni seçili dilden bağımsız olarak `lang` dilinde ver."""
    if lang != "en" or not text:
        return text
    return EN.get(text, text)


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
