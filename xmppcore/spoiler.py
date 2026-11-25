"""XEP-0382 spoiler mesajları (Tk'sız, ağsız).

Spoiler, gövdesi tıklanana kadar gizli gösterilen mesajdır; isteğe bağlı
uyarı metni (`<spoiler xmlns='urn:xmpp:spoiler:0'>uyarı</spoiler>`) gizliyken
görünür. Yalnız şifresiz (düz) mesajlarda gönderilir ve okunur: OMEMO/PGP
yollarına dokunulmaz (CLAUDE.md kural 1); şifreli mesajdaki işaret yok sayılır.

Olay sözleşmesi: "msg"/"own_msg" yüküne "spoiler" anahtarı YALNIZ mesaj
spoiler'sa eklenir (değer uyarı metni, uyarısızsa ""). Saklama: DB
`messages.spoiler` (NULL = spoiler değil).
"""
import xml.etree.ElementTree as ET

from xmppcore.i18n import tr as _tr

NS = "urn:xmpp:spoiler:0"
TAG = "{%s}spoiler" % NS
HINT_MAX = 200


def clean_hint(hint):
    """None → None (spoiler değil); metin → tek satır, sınırlı."""
    if hint is None:
        return None
    return " ".join(str(hint).split())[:HINT_MAX]


def hint_of(xml):
    """Stanza XML'indeki spoiler uyarısı: yoksa None, uyarısızsa ""."""
    if xml is None:
        return None
    el = xml.find(TAG)
    if el is None:
        return None
    return clean_hint(el.text or "")


def mark(data: dict, xml) -> dict:
    """Olay yüküne spoiler'ı yalnız varsa ekle; yükü döndürür."""
    hint = hint_of(xml)
    if hint is not None:
        data["spoiler"] = hint
    return data


def add(msg, hint):
    """Giden düz mesaja spoiler öğesi ekle (uyarı boşsa boş öğe)."""
    hint = clean_hint(hint)
    if hint is None:
        return msg
    el = ET.SubElement(msg.xml, TAG)
    if hint:
        el.text = hint
    return msg


def label(hint):
    """Bildirimde ve gizli gövdenin yerinde gösterilen metin."""
    return _tr("🙈 Gizli içerik: {}").format(hint) if hint else _tr("🙈 Gizli içerik")


def cover(hint):
    """Balondaki örtü: tıklayınca asıl metin açılır."""
    return _tr("{} — göstermek için tıklayın").format(label(hint))
