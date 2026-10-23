"""tools/omemo_e2e.py: sertifika doğrulaması varsayılan olarak açık kalmalı.

Betik test sunucusu için doğrulamayı HER ZAMAN kapatıyordu (CERT_NONE);
gerçek hesaplarla herkese açık sunucuda çalıştırılınca şifreler araya
girene (MITM) açık kalırdı. Kapatma yalnız XMPP_E2E_INSECURE=1 ile.
"""
import importlib.util
import inspect
import os
import ssl
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), "tools", "omemo_e2e.py")


def _tool():
    spec = importlib.util.spec_from_file_location("omemo_e2e", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bot():
    return types.SimpleNamespace(ssl_context=ssl.create_default_context())


def test_tls_verification_stays_on_by_default():
    tool = _tool()
    bot = _bot()
    tool._apply_tls([bot], insecure=False)
    assert bot.ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert bot.ssl_context.check_hostname is True


def test_tls_verification_off_only_on_request():
    tool = _tool()
    bot = _bot()
    tool._apply_tls([bot], insecure=True)
    assert bot.ssl_context.verify_mode == ssl.CERT_NONE
    assert tool._insecure_requested({"XMPP_E2E_INSECURE": "1"}) is True
    assert tool._insecure_requested({}) is False
    assert tool._insecure_requested({"XMPP_E2E_INSECURE": "0"}) is False


def test_run_does_not_disable_verification_unconditionally():
    src = inspect.getsource(_tool().run)
    assert "CERT_NONE" not in src and "_apply_tls(" in src
