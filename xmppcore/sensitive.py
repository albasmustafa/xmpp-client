"""Göndermeden önce hassas veri taraması (yerel, modelsiz).

Tk/ağ/DB YOKTUR. Şifresiz sohbete gidecek taslakta parola, IBAN, kart
numarası, T.C. kimlik no, API anahtarı ya da özel anahtar gibi bilgileri
deterministik kurallarla bulur. Yanlış pozitifi azaltmak için sayısal
kimlikler sağlama algoritmasıyla (Luhn, mod-97, TCKN) doğrulanır.
Bulgular yalnız MASKELİ örnekle döner; ham değer hiçbir yere yazılmaz.
"""
import re
from collections import namedtuple

from xmppcore.i18n import N_
from xmppcore.i18n import tr as _tr

Finding = namedtuple("Finding", ("kind", "label", "sample"))

MAX_FINDINGS = 6

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----")

# Sıra önemlidir: önce eşleşen aralık sonrakilerce yeniden sayılmaz
# (ör. sk-ant- anahtarı ayrıca "OpenAI" olarak raporlanmaz).
_TOKEN_PATTERNS = (
    (N_("Anthropic API anahtarı"), r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    (N_("OpenAI API anahtarı"),
     r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{32,}"),
    (N_("GitHub belirteci"),
     r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"),
    (N_("AWS erişim anahtarı"), r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    (N_("Google API anahtarı"), r"\bAIza[0-9A-Za-z_\-]{35}"),
    (N_("Slack belirteci"), r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    (N_("Stripe gizli anahtarı"), r"\b[sr]k_live_[A-Za-z0-9]{16,}"),
    (N_("Oturum belirteci (JWT)"),
     r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
)
_TOKEN_RES = tuple((label, re.compile(p)) for label, p in _TOKEN_PATTERNS)

# "şifre: x", "parolam = x", "password is x" — anahtar kelime + ayraç şart;
# "şifremi unuttum" gibi düz cümleler eşleşmez.
_PASSWORD_RE = re.compile(
    r"(?<!\w)(?:şifre(?:m|miz|niz|si)?|parola(?:m|mız|nız|sı)?|password|"
    r"passwd|pwd|pin(?:\s*kod(?:u|um))?)\s*(?:[:=]|\bis\b)\s*(\S{3,})",
    re.IGNORECASE)

_CARD_RE = re.compile(r"(?<![\d.,])(?:\d[ -]?){12,18}\d(?![\d.,]\d|\d)")
_TCKN_RE = re.compile(r"(?<![\d.,])[1-9]\d{10}(?![\d.,]\d|\d)")
_IBAN_HEAD_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2})\d{2}")

# Ülke → IBAN uzunluğu (bilinmeyen ülke kodu taranmaz: rastgele dizide
# mod-97 tutma olasılığı 1/97'dir, uzunluk denetimi bunu bastırır).
_IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16,
    "BG": 22, "BH": 22, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28,
    "CZ": 24, "DE": 22, "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24,
    "FI": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18,
    "GR": 27, "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23,
    "IS": 26, "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MD": 24, "ME": 22,
    "MK": 19, "MR": 27, "MT": 31, "MU": 30, "NL": 18, "NO": 15, "PK": 24,
    "PL": 28, "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22, "SA": 24,
    "SC": 31, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "ST": 25, "SV": 28,
    "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20,
}

_CARD_PREFIXES = ("2", "3", "4", "5", "6", "9792")


# ── Sağlama algoritmaları ───────────────────────────────────────────────────
def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def iban_ok(iban: str) -> bool:
    s = iban.replace(" ", "").upper()
    if _IBAN_LENGTHS.get(s[:2]) != len(s) or not s.isalnum():
        return False
    moved = s[4:] + s[:4]
    try:
        return int("".join(str(int(ch, 36)) for ch in moved)) % 97 == 1
    except ValueError:
        return False


def tckn_ok(num: str) -> bool:
    if len(num) != 11 or not num.isdigit() or num[0] == "0":
        return False
    d = [int(c) for c in num]
    if (sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


# ── Maskeleme ───────────────────────────────────────────────────────────────
def _mask_tail(value: str, keep: int = 4) -> str:
    return "•••• " + value[-keep:] if len(value) > keep else "••••"


def _mask_token(value: str) -> str:
    return value[:6] + "…" if len(value) > 10 else "••••"


# ── Tarama ──────────────────────────────────────────────────────────────────
def _iban_matches(text):
    """(başlangıç, bitiş, sıkıştırılmış IBAN) — tekli boşluklu yazım da."""
    for m in _IBAN_HEAD_RE.finditer(text):
        want = _IBAN_LENGTHS.get(m.group(1).upper())
        if not want:
            continue
        chars, i = [], m.start()
        while i < len(text) and len(chars) < want:
            ch = text[i]
            if ch.isascii() and ch.isalnum():
                chars.append(ch)
            elif not (ch == " " and chars and i + 1 < len(text)
                      and text[i + 1].isascii() and text[i + 1].isalnum()):
                break
            i += 1
        if len(chars) != want:
            continue
        if i < len(text) and text[i].isascii() and text[i].isalnum():
            continue                    # daha uzun bir dizinin parçası
        iban = "".join(chars).upper()
        if iban_ok(iban):
            yield m.start(), i, iban


def scan(text: str) -> list:
    """Taslaktaki hassas bilgiler: [Finding] (en fazla MAX_FINDINGS)."""
    text = text or ""
    found, spans, seen = [], [], set()

    def _free(start, end):
        return all(end <= s or start >= e for s, e in spans)

    def _add(start, end, kind, label, sample):
        if not _free(start, end):
            return
        spans.append((start, end))
        if (kind, sample) not in seen:
            seen.add((kind, sample))
            found.append(Finding(kind, label, sample))

    for m in _PRIVATE_KEY_RE.finditer(text):
        _add(m.start(), m.end(), "private_key", _tr("Özel anahtar (private key)"),
             "-----BEGIN … PRIVATE KEY-----")
    for label, rx in _TOKEN_RES:
        for m in rx.finditer(text):
            _add(m.start(), m.end(), "token", _tr(label), _mask_token(m.group(0)))
    for start, end, iban in _iban_matches(text):
        _add(start, end, "iban", "IBAN", f"{iban[:4]} {_mask_tail(iban)}")
    for m in _PASSWORD_RE.finditer(text):
        value = m.group(1)
        _add(m.start(1), m.end(1), "password", _tr("Parola / PIN"),
             value[0] + "•••")
    for m in _CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if (13 <= len(digits) <= 19 and digits.startswith(_CARD_PREFIXES)
                and len(set(digits)) > 1 and luhn_ok(digits)):
            _add(m.start(), m.end(), "card", _tr("Kart numarası"),
                 _mask_tail(digits))
    for m in _TCKN_RE.finditer(text):
        if tckn_ok(m.group(0)):
            _add(m.start(), m.end(), "tckn", _tr("T.C. kimlik no"),
                 _mask_tail(m.group(0), 2))
    return found[:MAX_FINDINGS]


def warning_text(findings, *, room: bool = False) -> str:
    """Onay penceresi metni (maskeli örneklerle)."""
    lines = [f"• {f.label}: {f.sample}" for f in findings]
    where = (_tr("Bu grup sohbetine şifresiz gönderilecek mesaj")
             if room else _tr("Bu mesaj şifresiz gönderilecek ve"))
    return (_tr("{} şu hassas bilgileri içeriyor gibi görünüyor:\n\n").format(where)
            + "\n".join(lines)
            + _tr("\n\nŞifresiz mesajları sunucu yöneticileri görebilir ve "
                  "sunucu arşivinde (MAM) saklanabilir. Göndermeden önce 🔒 "
                  "ile şifrelemeyi açabilirsiniz.\n\nYine de gönderilsin mi?"))
