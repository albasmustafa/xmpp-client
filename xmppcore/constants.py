"""Yol sabitleri ve kayıt altyapısı (Faz 1 yaprak modülü)."""
import logging
import logging.handlers
import os


def _user_home() -> str:
    """Kullanıcı dosyalarının kökü: XMPP_CLIENT_HOME (testler, taşınabilir
    profil) ya da ev dizini. Testler bunu tests/conftest.py ile geçici
    dizine yönlendirir; gerçek ayar/DB/log dosyalarına dokunulmaz."""
    return os.environ.get("XMPP_CLIENT_HOME") or os.path.expanduser("~")


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

