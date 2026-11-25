"""--lan: yerel ağda güvenilir HTTPS (telefona PWA kurulumu).

Telefon tarayıcısı servis çalışanını yalnız güvenilen sertifikayla kaydeder;
kendinden imzalı sertifikanın uyarısını geçmek yetmez. Yerel kök sertifika
(CA) telefona bir kez kurulur; CA ad kısıtlıdır (çalınsa bile başka site için
geçerli sertifika imzalayamaz).
"""
import asyncio
import os
import ssl
import stat
import sys
import types

import pytest
from cryptography import x509

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp import lan_tls  # noqa: E402
from webapp import server as srv  # noqa: E402


def _load(path):
    with open(path, "rb") as f:
        return x509.load_pem_x509_certificate(f.read())


def test_certs_created_private_and_chained(tmp_path):
    d = tmp_path / "web-tls"
    tls = lan_tls.ensure_certs(str(d), ["192.168.1.23"], hostname="dizustu")
    assert tls["issued"]
    assert stat.S_IMODE(os.stat(d).st_mode) == 0o700
    for key in ("ca-key.pem", "server-key.pem"):
        assert stat.S_IMODE(os.stat(d / key).st_mode) == 0o600
    ca, cert = _load(tls["ca"]), _load(tls["cert"])
    cert.verify_directly_issued_by(ca)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert {str(a) for a in san.get_values_for_type(x509.IPAddress)} == {
        "192.168.1.23", "127.0.0.1"}
    assert set(san.get_values_for_type(x509.DNSName)) == {
        "dizustu", "dizustu.local", "localhost"}
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    nc = ca.extensions.get_extension_for_class(x509.NameConstraints).value
    assert x509.DNSName("dizustu") in nc.permitted_subtrees


def test_reuse_and_reissue_keep_the_same_ca(tmp_path):
    d = str(tmp_path)
    first = lan_tls.ensure_certs(d, ["192.168.1.23"], hostname="h")
    ca_before = _load(first["ca"]).serial_number
    assert not lan_tls.ensure_certs(d, ["192.168.1.23"], hostname="h")["issued"]
    moved = lan_tls.ensure_certs(d, ["10.0.0.7"], hostname="h")   # IP değişti
    assert moved["issued"] and _load(moved["ca"]).serial_number == ca_before


def test_near_expiry_server_cert_is_renewed(tmp_path):
    d = str(tmp_path)
    lan_tls.ensure_certs(d, ["192.168.1.23"], hostname="h", days=10)
    assert lan_tls.ensure_certs(d, ["192.168.1.23"], hostname="h")["issued"]


def _serve_and_fetch(tls_paths, ca_path, server_hostname, path="/ca.crt"):
    """Uygulamayı gerçek TLS ile 127.0.0.1'de çalıştır; kök sertifikaya güvenen
    bir istemciyle bağlan. Döner: (durum, gövde) ya da istisna."""
    from aiohttp import ClientSession, TCPConnector, web

    async def go():
        app = srv.make_app(public_hosts=["127.0.0.1"], ca_path=ca_path)
        sctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        sctx.load_cert_chain(tls_paths["cert"], tls_paths["key"])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=sctx)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        cctx = ssl.create_default_context(cafile=ca_path)
        try:
            async with ClientSession(connector=TCPConnector(ssl=cctx)) as http:
                async with http.get(f"https://127.0.0.1:{port}{path}",
                                    server_hostname=server_hostname) as r:
                    return r.status, await r.read()
        finally:
            await runner.cleanup()
    return asyncio.run(go())


def test_real_tls_handshake_and_ca_download(tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "_TOKENS", {})
    tls = lan_tls.ensure_certs(str(tmp_path), [], hostname="h")
    status, body = _serve_and_fetch(tls, tls["ca"], "127.0.0.1")
    assert status == 200
    with open(tls["ca"], "rb") as f:
        assert body == f.read()


def test_name_constraints_block_foreign_sites(tmp_path):
    """Kök anahtarı çalınsa bile başka site (ör. bir banka) için imzalanan
    sertifika reddedilir: ad kısıtı OpenSSL'de de uygulanır."""
    tls = lan_tls.ensure_certs(str(tmp_path), [], hostname="h")
    from cryptography.hazmat.primitives import serialization
    with open(tmp_path / "ca-key.pem", "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), None)
    evil, evil_key = lan_tls._make_server(_load(tls["ca"]), ca_key, "bank.example",
                                          ["bank.example"], ["127.0.0.1"], 30)
    (tmp_path / "evil.pem").write_bytes(
        evil.public_bytes(serialization.Encoding.PEM))
    (tmp_path / "evil-key.pem").write_bytes(lan_tls._key_pem(evil_key))
    with pytest.raises(Exception) as err:
        _serve_and_fetch({"cert": str(tmp_path / "evil.pem"),
                          "key": str(tmp_path / "evil-key.pem")},
                         tls["ca"], "bank.example")
    assert "permitted subtree violation" in str(err.value)


def test_ca_route_only_in_lan_mode():
    paths = {r.resource.canonical for r in srv.make_app().router.routes()}
    assert "/ca.crt" not in paths


def test_apply_lan_switches_to_secure_lan_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("XMPP_CLIENT_HOME", str(tmp_path))
    monkeypatch.setattr(lan_tls, "lan_addresses", lambda: ["192.168.1.23"])
    args = types.SimpleNamespace(host="127.0.0.1", cert=None, key=None,
                                 insecure=False, public_host=[])
    ca = srv._apply_lan(args)
    assert args.host == "0.0.0.0" and not args.insecure
    assert args.public_host[0] == "192.168.1.23"
    assert os.path.isfile(args.cert) and os.path.isfile(ca)
    assert ca.startswith(str(tmp_path / "web-tls"))


def test_apply_lan_refuses_insecure_mix(monkeypatch):
    args = types.SimpleNamespace(host="127.0.0.1", cert=None, key=None,
                                 insecure=True, public_host=[])
    with pytest.raises(SystemExit):
        srv._apply_lan(args)


def test_lan_addresses_are_private():
    import ipaddress
    for ip in lan_tls.lan_addresses():
        addr = ipaddress.ip_address(ip)
        assert addr.is_private and not addr.is_loopback
