"""Yol sabitleri ve kayıt altyapısı (Faz 1 yaprak modülü)."""
import logging
import logging.handlers
import os

# Ev dizinindeki tek satırlık dosya: başka diske taşınmış profilin klasörü
_HOME_POINTER = ".xmpp_client_home"


def _user_home() -> str:
    """Kullanıcı dosyalarının (ayar, DB, log, anahtar, OMEMO, avatar) kökü.

    Sıra: XMPP_CLIENT_HOME (testler bunu tests/conftest.py ile geçici dizine
    ayarlar; gerçek dosyalara dokunulmaz) → ev dizinindeki
    `.xmpp_client_home` dosyasının gösterdiği klasör (taşınmış profil; betik,
    masaüstü kısayolu, doğrudan python — her başlatma aynı yeri bulur) → ev
    dizini. Gösterilen klasör yoksa (ör. disk takılı değil) boş profille
    açılmaz — yeni OMEMO kimliği ve boş ayar demekti —, açıklamayla durur.
    """
    env = os.environ.get("XMPP_CLIENT_HOME")
    if env:
        return env
    home = os.path.expanduser("~")
    pointer = os.path.join(home, _HOME_POINTER)
    try:
        with open(pointer, encoding="utf-8") as f:
            target = os.path.expanduser(f.read().strip())
    except FileNotFoundError:
        return home
    if not os.path.isabs(target) or not os.path.isdir(target):
        raise SystemExit(
            f"XMPP istemcisi: veri klasörü bulunamadı: {target or '(boş)'}\n"
            f"{pointer} bu klasörü gösteriyor. Disk takılı değilse takıp "
            "yeniden açın; profili ev dizinine geri taşıdıysanız bu dosyayı "
            "silin.")
    return target


# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_PATH = os.path.join(_user_home(), ".xmpp_client.log")
_log = logging.getLogger("xmpp_client")
_log.setLevel(logging.DEBUG)

_log_fh = logging.handlers.RotatingFileHandler(
    _LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
_log_fh.setLevel(logging.DEBUG)
_log_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"))
_log.addHandler(_log_fh)

_log_ch = logging.StreamHandler()
_log_ch.setLevel(logging.WARNING)
_log_ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
_log.addHandler(_log_ch)

_log.info("XMPP istemcisi başlatılıyor")

# ── Ayar dosyası (şifre + oda hafızası) ─────────────────────────────────────
_CONFIG_PATH = os.path.join(_user_home(), ".xmpp_client.json")
_DB_PATH = os.path.join(_user_home(), ".xmpp_client_messages.db")
_AVATAR_DIR = os.path.join(_user_home(), ".xmpp_avatars")
os.makedirs(_AVATAR_DIR, exist_ok=True)

# Taşınmış profilde ses→metin modeli (faster-whisper, Hugging Face önbelleği)
# de profille durur; evdeki profilde HF'nin kendi yeri, kullanıcının
# HF_HOME'u her durumda korunur. faster_whisper geç (ilk kullanımda) yüklenir.
if os.path.abspath(_user_home()) != os.path.abspath(os.path.expanduser("~")):
    os.environ.setdefault("HF_HOME",
                          os.path.join(_user_home(), ".cache", "huggingface"))

