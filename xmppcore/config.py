"""Config ve şifre yardımcıları (Faz 1 yaprak modülü).

Yamalanabilir tekil durum (_CONFIG_PATH, _get_fernet_key) facade
uzayında (xmpp.py) yaşadığından çağrı sırasında erişilir;
test sözleşmesi (monkeypatch hedefleri) değişmez.
"""
import base64
import hashlib
import json
import os
import tempfile

from .constants import _log, _user_home


def _load_config() -> dict:
    try:
        import xmpp as _app
        with open(_app._CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            _log.warning("Ayar dosyası JSON nesnesi içermiyor: %s", _app._CONFIG_PATH)
            return {}
        return cfg
    except FileNotFoundError:
        return {}
    except Exception:
        _log.warning("Ayar dosyası okunamadı: %s", _app._CONFIG_PATH, exc_info=True)
        return {}


def _save_config(cfg: dict):
    tmp_path = None
    try:
        import xmpp as _app
        path = os.path.abspath(_app._CONFIG_PATH)
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=os.path.dirname(path),
                prefix=".xmpp-config-", delete=False) as f:
            tmp_path = f.name
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    except Exception:
        _log.error("Ayar dosyası yazılamadı: %s", _app._CONFIG_PATH, exc_info=True)
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                _log.warning("Geçici ayar dosyası silinemedi: %s", tmp_path, exc_info=True)


def _key_path() -> str:
    return os.path.join(_user_home(), ".xmpp_client.key")


def _get_fernet_key() -> bytes:
    """Makine-bazlı Fernet anahtarı üret/oku."""
    key_path = _key_path()
    if os.path.isfile(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
    except ImportError:
        seed = (os.getlogin() + str(os.getuid())).encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    old_umask = os.umask(0o077)
    try:
        with open(key_path, "wb") as f:
            f.write(key)
    finally:
        os.umask(old_umask)
    _log.info("Yeni şifreleme anahtarı oluşturuldu: %s", key_path)
    return key


def _encode_pw(pw: str) -> str:
    """Fernet ile şifrele, fallback olarak base64."""
    try:
        from cryptography.fernet import Fernet

        import xmpp as _app
        f = Fernet(_app._get_fernet_key())
        return "fernet:" + f.encrypt(pw.encode("utf-8")).decode("ascii")
    except ImportError:
        _log.warning("cryptography modülü yok, base64 obfuscation kullanılıyor")
        return base64.b64encode(pw.encode("utf-8")).decode("ascii")
    except Exception:
        # Anahtar dosyası bozuk/okunamaz ise parola kaydı çökmemeli (B6)
        _log.warning("Fernet şifreleme başarısız, base64 obfuscation "
                     "kullanılıyor", exc_info=True)
        return base64.b64encode(pw.encode("utf-8")).decode("ascii")


def _decode_pw(encoded: str) -> str:
    try:
        if encoded.startswith("fernet:"):
            from cryptography.fernet import Fernet

            import xmpp as _app
            f = Fernet(_app._get_fernet_key())
            return f.decrypt(encoded[7:].encode("ascii")).decode("utf-8")
        return base64.b64decode(encoded.encode("ascii")).decode("utf-8")
    except Exception:
        _log.error("Şifre çözülemedi", exc_info=True)
        return ""


def _verify_pin(stored: str, entered: str) -> bool:
    """PIN doğrula: şifreli kayıt ve eski düz metin kaydını destekler."""
    if not isinstance(stored, str) or not isinstance(entered, str) or not stored or not entered:
        return False
    if stored.startswith("fernet:"):
        return _decode_pw(stored) == entered
    if stored == entered:  # eski düz metin kaydı (geriye dönük uyum)
        return True
    return _decode_pw(stored) == entered


def _account_password(acc: dict) -> str:
    """Hesap kaydındaki parolayı çöz (eski düz metin kayıtlarını da destekler)."""
    pw = acc.get("password", "")
    if not pw:
        return ""
    return _decode_pw(pw) or pw


def _store_login(cfg: dict, remember: bool, jid: str = "", pw: str = "",
                 port: int = 5222, server: str = "",
                 auto_login: bool = True) -> None:
    """Şifremi hatırla: giriş bilgilerini cfg'ye şifreli yaz ya da sil.
    `auto_login`: açılışta formu atlayıp bu bilgilerle bağlan."""
    if remember and jid and pw:
        cfg["jid"] = jid
        cfg["pw"] = _encode_pw(pw)
        cfg["server"] = server
        cfg["port"] = port
        cfg["remember"] = True
        cfg["auto_login"] = bool(auto_login)
    else:
        for k in ("jid", "pw", "server", "port"):
            cfg.pop(k, None)
        cfg["remember"] = False
        cfg["auto_login"] = False


def _auto_login_enabled(cfg: dict) -> bool:
    """Açılışta form atlanıp kayıtlı bilgilerle mi bağlanılsın? Eski
    kayıtlarda anahtar yoksa "Beni hatırla" otomatik giriş demekti → açık."""
    return bool(cfg.get("remember")) and bool(cfg.get("auto_login", True))


def _saved_login(cfg: dict):
    """Hatırlanan giriş → (jid, pw, port, server); kullanılamıyorsa None."""
    if not cfg.get("remember"):
        return None
    jid = cfg.get("jid") or ""
    pw = _decode_pw(cfg.get("pw") or "")
    if not jid or not pw:
        return None
    try:
        port = int(cfg.get("port") or 5222)
    except (TypeError, ValueError):
        port = 5222
    return jid, pw, port, cfg.get("server") or ""
