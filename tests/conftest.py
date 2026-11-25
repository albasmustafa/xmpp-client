"""Test oturumu gerçek kullanıcı dosyalarına (~/.xmpp_client.*) dokunmaz.

xmppcore.constants yolları içe aktarma anında hesaplar; pytest bu dosyayı
test modüllerinden (ve `import xmpp`'den) önce yükler. Alt süreçler
(ör. MCP sunucusu testleri) ortam değişkenini devralır.
"""
import os
import tempfile

os.environ["XMPP_CLIENT_HOME"] = tempfile.mkdtemp(prefix="xmpp-test-home-")
# Gerçek sistem anahtarlığına (GNOME Keyring…) dokunulmaz; anahtarlık testleri
# sahte arka uçla çalışır (test_keyring.py)
os.environ["XMPP_NO_KEYRING"] = "1"
