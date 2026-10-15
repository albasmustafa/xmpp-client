"""Metni sesli okuma — yerel TTS motorları (Tk/ağ YOK).

Motorlar ("auto" bu sırayla dener): piper (doğal sinir ağı sesi; .onnx
ses modeli gerekir), espeak-ng, espeak, spd-say (speech-dispatcher).
Bu modül yalnız motoru seçer ve çalıştırılacak adımları üretir; süreç
yönetimi (başlatma/durdurma/geçici dosya) MainWindow'dadır.

Güvenlik: komutlar liste olarak üretilir (kabuk yok) ve metin argüman
yerine stdin'den verilir — "-" ile başlayan bir mesaj seçenek sayılmaz.
"""
import os
import re
import shutil
from collections import namedtuple

from .ai import AISetupError

Step = namedtuple("Step", ("argv", "stdin"))

MAX_CHARS = 1500
_PLAYERS = (("pw-play", ()), ("paplay", ()), ("aplay", ("-q",)),
            ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "quiet")))
_AUTO_ORDER = ("piper", "espeak-ng", "espeak", "spd-say")

INSTALL_HINT = (
    "Sesli okuma için yerel bir ses motoru gerekli. Örneğin:\n"
    "  sudo pacman -S espeak-ng\n"
    "Daha doğal ses için Piper: piper-tts kurun ve ✨ → AI Ayarları'nda "
    "Türkçe bir ses modelinin (.onnx) yolunu girin.")

_URL_RE = re.compile(r"(?:https?|aesgcm)://\S+|www\.\S+", re.IGNORECASE)
_MARKUP_RE = re.compile(r"```.*?```|[*_~`#>|]+", re.DOTALL)
_SENTENCE_END_RE = re.compile(r"[.!?…](?=\s)")


def clean_for_speech(text: str) -> str:
    """Bağlantı/biçim işaretlerini ayıkla, uzun metni cümle sınırında kes."""
    text = _URL_RE.sub(" bağlantı ", text or "")
    text = _MARKUP_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= MAX_CHARS:
        return text
    head = text[:MAX_CHARS]
    ends = [m.end() for m in _SENTENCE_END_RE.finditer(head)]
    cut = ends[-1] if ends and ends[-1] > MAX_CHARS // 2 else MAX_CHARS
    return head[:cut].rstrip() + " …"


def _player(which):
    for name, args in _PLAYERS:
        path = which(name)
        if path:
            return [path, *args]
    return None


def _available(engine, settings, which):
    if engine == "piper":
        voice = settings.get("tts_voice", "")
        return bool(which("piper") and voice and os.path.isfile(voice)
                    and _player(which))
    return bool(which(engine))


def pick_engine(settings, which=None) -> str:
    """Kullanılacak motor; yoksa AISetupError (kurulum ipucuyla)."""
    which = which or shutil.which
    pref = settings.get("tts_engine", "auto")
    order = _AUTO_ORDER if pref == "auto" else (pref,)
    for engine in order:
        if _available(engine, settings, which):
            return engine
    if pref == "piper":
        raise AISetupError(
            "Piper için `piper` komutu, bir ses modeli (.onnx) ve bir ses "
            "çalar (pw-play/paplay/aplay) gerekli.\n\n" + INSTALL_HINT)
    if pref != "auto":
        raise AISetupError(f"Seçili ses motoru bulunamadı: {pref}\n\n"
                           + INSTALL_HINT)
    raise AISetupError(INSTALL_HINT)


def plan_speech(text: str, settings, wav_path: str, which=None) -> list:
    """Çalıştırılacak adımlar: [Step(argv, stdin_metni | None)]."""
    which = which or shutil.which
    text = clean_for_speech(text)
    if not text:
        raise AISetupError("Okunacak metin yok.")
    engine = pick_engine(settings, which)
    lang = settings.get("tts_lang") or "tr"
    if engine == "piper":
        return [Step([which("piper"), "-m", settings["tts_voice"],
                      "-f", wav_path], text),
                Step([*_player(which), wav_path], None)]
    if engine in ("espeak-ng", "espeak"):
        return [Step([which(engine), "-v", lang, "-s", "165", "--stdin"],
                     text)]
    # spd-say metni argüman olarak alır: "--" seçenek ayrıştırmayı bitirir.
    return [Step([which("spd-say"), "-w", "-l", lang, "--", text], None)]


def describe_engines(settings, which=None) -> str:
    """AI Ayarları testinde gösterilecek tek satırlık durum."""
    try:
        engine = pick_engine(settings, which)
    except AISetupError:
        return ("ℹ Sesli okuma motoru yok (isteğe bağlı): sudo pacman -S "
                "espeak-ng")
    return f"✓ Sesli okuma: {engine}"
