"""Hazır yanıtlar (Tk'sız, ağsız): sık yazılan metinler tek tıkla eklenir.

Config "canned_replies": [metin, …] — masaüstü (giriş kutusundaki ✨ →
💬 Hazır yanıtlar) ve web (giriş kutusundaki 💬 düğmesi) aynı listeyi
kullanır. Her yanıt tek satırdır (masaüstü giriş kutusu tek satırlıdır).
Seçilen yanıt giriş kutusuna eklenir, kendiliğinden GÖNDERİLMEZ.
Düzenleyicide her satır bir yanıttır.
"""

KEY = "canned_replies"
MAX_ITEMS = 50
MAX_LEN = 500


def normalize(items) -> list:
    """Liste olmayanı boş say; her öğeyi tek satıra indir (boşluklar
    sadeleşir), boşları ve tekrarları at, uzunluk ve sayı sınırını uygula."""
    if not isinstance(items, list):
        return []
    out, seen = [], set()
    for raw in items:
        if not isinstance(raw, str):
            continue
        text = " ".join(raw.split())[:MAX_LEN].rstrip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= MAX_ITEMS:
            break
    return out


def load(cfg) -> list:
    return normalize((cfg or {}).get(KEY))


def set_items(cfg, items) -> dict:
    """`cfg`'yi yerinde günceller ve döndürür."""
    cfg[KEY] = normalize(items)
    return cfg


def parse_editor(text) -> list:
    """Düzenleyici metni → liste (her boş olmayan satır bir yanıt)."""
    return normalize(str(text or "").splitlines())


def editor_text(items) -> str:
    return "\n".join(normalize(items))


def label(text, width=48) -> str:
    """Menü etiketi: uzun yanıt "…" ile kısalır."""
    text = " ".join(str(text or "").split())
    if len(text) <= width:
        return text
    return text[:width - 1].rstrip() + "…"


def joined(current, text) -> str:
    """Giriş kutusundaki metnin sonuna eklenecek parça: yarım kalmış bir
    sözcüğe yapışmasın diye gerekirse araya boşluk girer."""
    if current and not current[-1].isspace():
        return " " + text
    return text
