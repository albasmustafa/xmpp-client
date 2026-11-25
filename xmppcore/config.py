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


_CACHE: dict = {"key": None, "cfg": {}}


def _load_config_cached() -> dict:
    """Sık okuyan yerler için (ör. her gelen mesajda bildirim kararı): dosya
    değişmediyse son okunanı döndürür. Masaüstü ve web aynı dosyayı yazdığı
    için anahtar yol + mtime + boyuttur. Dönen sözlük paylaşılır, DEĞİŞTİRME:
    yazmak için `_load_config` → `_save_config`."""
    import xmpp as _app
    path = _app._CONFIG_PATH
    try:
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
    except OSError:
        key = (path, None, None)
    if _CACHE["key"] != key:
        _CACHE["cfg"] = _load_config()
        _CACHE["key"] = key
    return _CACHE["cfg"]


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


# ── Parola şifreleme anahtarı: sistem anahtarlığı (Secret Service) ──────────
# Kayıtlı parola Fernet ile şifrelenir. Anahtar eskiden yanındaki dosyadaydı
# (.xmpp_client.key): ikisini okuyabilen parolayı da okurdu. Anahtarlık varsa
# (GNOME Keyring, KWallet…) anahtar orada tutulur, kilidi masaüstü girişiyle
# açılır; eski dosya anahtarlığa taşınıp silinir. Anahtarlık yoksa eski
# davranış. Profilin anahtarlıktaki öge adı profilde durur (.xmpp_client.keyring,
# gizli değil): profil taşınsa da aynı bilgisayarda bulunur. Başka bilgisayarda
# anahtarlıkta öge olmadığından kayıtlı parola yeniden girilir.
_KEYRING_SERVICE = "xmpp-istemcisi"
_KEYRING_CACHE: dict = {}        # öge adı → anahtar (her şifre çözmede D-Bus'a gitmesin)


def _keyring():
    """Kullanılabilir anahtarlık modülü ya da None (XMPP_NO_KEYRING=1 kapatır:
    testler ve CI gerçek anahtarlığa dokunmaz)."""
    if os.environ.get("XMPP_NO_KEYRING"):
        return None
    try:
        import keyring
        if getattr(keyring.get_keyring(), "priority", 0) <= 0:
            return None             # yalnız "fail"/"null" arka uç var
        return keyring
    except Exception:
        return None


def _keyring_item_path() -> str:
    return os.path.join(_user_home(), ".xmpp_client.keyring")


def _keyring_item_name() -> str:
    """Bu profilin anahtarlıktaki öge adı (ilk kez üretilip profile yazılır)."""
    path = _keyring_item_path()
    try:
        with open(path, encoding="utf-8") as f:
            name = f.read().strip()
        if name:
            return name
    except OSError:
        pass
    import uuid
    name = f"fernet-key-{uuid.uuid4().hex}"
    old_umask = os.umask(0o077)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(name + "\n")
    finally:
        os.umask(old_umask)
    return name


def _keyring_put(kr, name: str, key: bytes) -> bool:
    """Anahtarı anahtarlığa yaz ve geri okuyarak doğrula."""
    try:
        kr.set_password(_KEYRING_SERVICE, name, key.decode("ascii"))
        return kr.get_password(_KEYRING_SERVICE, name) == key.decode("ascii")
    except Exception:
        _log.warning("Şifreleme anahtarı anahtarlığa yazılamadı", exc_info=True)
        return False


def _new_fernet_key() -> bytes:
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key()
    except ImportError:
        seed = (os.getlogin() + str(os.getuid())).encode()
        return base64.urlsafe_b64encode(hashlib.sha256(seed).digest())


def _get_fernet_key() -> bytes:
    """Parola şifreleme anahtarını oku/üret: önce anahtarlık, yoksa dosya."""
    key_path = _key_path()
    kr = _keyring()
    name = ""
    if kr is not None:
        name = _keyring_item_name()
        if name in _KEYRING_CACHE:
            return _KEYRING_CACHE[name]
        try:
            stored = kr.get_password(_KEYRING_SERVICE, name)
        except Exception:
            _log.warning("Anahtarlık okunamadı; dosyadaki anahtar kullanılıyor",
                         exc_info=True)
            stored, kr = None, None
        if stored:
            key = stored.encode("ascii")
            _KEYRING_CACHE[name] = key
            _retire_key_file(key_path, key)
            return key
    if os.path.isfile(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
        if kr is not None and _keyring_put(kr, name, key):
            _KEYRING_CACHE[name] = key
            _retire_key_file(key_path, key)
            _log.info("Şifreleme anahtarı sistem anahtarlığına taşındı")
        return key
    key = _new_fernet_key()
    if kr is not None and _keyring_put(kr, name, key):
        _KEYRING_CACHE[name] = key
        _log.info("Yeni şifreleme anahtarı sistem anahtarlığında oluşturuldu")
        return key
    old_umask = os.umask(0o077)
    try:
        with open(key_path, "wb") as f:
            f.write(key)
    finally:
        os.umask(old_umask)
    _log.info("Yeni şifreleme anahtarı oluşturuldu: %s", key_path)
    return key


def _retire_key_file(key_path: str, key: bytes) -> None:
    """Anahtarlıktakiyle AYNI anahtarı taşıyan eski dosyayı sil; farklıysa
    (başka bir anahtar) dokunma — veri kaybı olmasın."""
    try:
        if not os.path.isfile(key_path):
            return
        with open(key_path, "rb") as f:
            if f.read() != key:
                _log.warning("Anahtar dosyası anahtarlıktakinden farklı; "
                             "silinmedi: %s", key_path)
                return
        os.remove(key_path)
    except OSError:
        _log.warning("Eski anahtar dosyası silinemedi: %s", key_path,
                     exc_info=True)


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
