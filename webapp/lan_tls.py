"""Yerel ağda HTTPS: telefon web arayüzünü uygulama (PWA) olarak kurabilsin.

Telefon tarayıcısı servis çalışanını (PWA) yalnız GÜVENİLEN bir sertifikayla
kaydeder; kendinden imzalı sertifikanın uyarısını geçmek yetmez. Bu modül
profilde (`<veri klasörü>/web-tls/`) küçük bir yerel kök sertifika (CA) ve onun
imzaladığı bir sunucu sertifikası üretir. Kök sertifika telefona BİR KEZ kurulur;
yerel IP değişince yalnız sunucu sertifikası yeniden üretilir.

Kök sertifikanın anahtarı çalınırsa başka siteler için sertifika imzalanamasın
diye CA ad kısıtlıdır (RFC 5280 Name Constraints): yalnız özel IPv4 aralıkları,
127.0.0.0/8, `localhost`, `.local` ve bu bilgisayarın adı.
"""
import datetime as _dt
import ipaddress
import os
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CA_CERT, CA_KEY = "ca.pem", "ca-key.pem"
SERVER_CERT, SERVER_KEY = "server.pem", "server-key.pem"
_PRIVATE_NETS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")
_CA_DAYS = 3650
_SERVER_DAYS = 397             # tarayıcıların sunucu sertifikası üst sınırı
_RENEW_BEFORE = _dt.timedelta(days=30)


def lan_addresses() -> list:
    """Bu bilgisayarın yerel ağ IPv4 adresleri (ilk: varsayılan çıkış). UDP
    "bağlantısı" paket göndermez; yalnız çıkış arayüzünü seçtirir."""
    found = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))         # TEST-NET-1: yönlendirilmez
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    out = []
    for ip in found:
        addr = ipaddress.ip_address(ip)
        if addr.is_private and not addr.is_loopback and ip not in out:
            out.append(ip)
    return out


def _now():
    return _dt.datetime.now(_dt.timezone.utc)


def _write_private(path, data: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(path, 0o600)


def _new_key():
    return ec.generate_private_key(ec.SECP256R1())


def _key_pem(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def _make_ca(hostname: str):
    key = _new_key()
    name = x509.Name([x509.NameAttribute(
        NameOID.COMMON_NAME, f"xmpp-istemcisi yerel CA ({hostname})")])
    permitted = [x509.IPAddress(ipaddress.ip_network(n)) for n in _PRIVATE_NETS]
    permitted += [x509.DNSName("localhost"), x509.DNSName("local"),
                  x509.DNSName(hostname)]
    now = _now()
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - _dt.timedelta(minutes=5))
            .not_valid_after(now + _dt.timedelta(days=_CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=False, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.NameConstraints(permitted_subtrees=permitted,
                                                excluded_subtrees=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                           critical=False)
            .sign(key, hashes.SHA256()))
    return cert, key


def _make_server(ca_cert, ca_key, hostname: str, dns_names, ips, days: int):
    key = _new_key()
    alt = [x509.DNSName(n) for n in dns_names]
    alt += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
    now = _now()
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - _dt.timedelta(minutes=5))
            .not_valid_after(now + _dt.timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                           critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    return cert, key


def _covers(cert, dns_names, ips) -> bool:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False
    have_dns = set(san.get_values_for_type(x509.DNSName))
    have_ip = {str(a) for a in san.get_values_for_type(x509.IPAddress)}
    return set(dns_names) <= have_dns and set(ips) <= have_ip


def ensure_certs(directory, ips, hostname=None, days=_SERVER_DAYS) -> dict:
    """Kök ve sunucu sertifikalarını hazırla; gerekirse üret.

    Kök sertifika bir kez üretilir (telefona bir kez kurulur). Sunucu
    sertifikası yoksa, süresi 30 günden az kaldıysa ya da istenen ad/IP'leri
    kapsamıyorsa yeniden üretilir. Döner: {"cert", "key", "ca", "issued"}.
    """
    hostname = (hostname or socket.gethostname() or "localhost").lower()
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    p = {k: os.path.join(directory, v) for k, v in (
        ("ca", CA_CERT), ("ca_key", CA_KEY), ("cert", SERVER_CERT),
        ("key", SERVER_KEY))}
    if os.path.isfile(p["ca"]) and os.path.isfile(p["ca_key"]):
        with open(p["ca"], "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
        with open(p["ca_key"], "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), None)
    else:
        ca_cert, ca_key = _make_ca(hostname)
        _write_private(p["ca_key"], _key_pem(ca_key))
        with open(p["ca"], "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    dns_names = sorted({hostname, f"{hostname}.local", "localhost"})
    want_ips = sorted(set(ips) | {"127.0.0.1"})
    issued = True
    if os.path.isfile(p["cert"]) and os.path.isfile(p["key"]):
        with open(p["cert"], "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        fresh = cert.not_valid_after_utc - _now() > _RENEW_BEFORE
        same_ca = cert.issuer == ca_cert.subject
        issued = not (fresh and same_ca and _covers(cert, dns_names, want_ips))
    if issued:
        cert, key = _make_server(ca_cert, ca_key, hostname, dns_names, want_ips, days)
        _write_private(p["key"], _key_pem(key))
        with open(p["cert"], "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
    return {"cert": p["cert"], "key": p["key"], "ca": p["ca"], "issued": issued,
            "hostname": hostname, "dns": dns_names, "ips": want_ips}
