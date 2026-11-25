# XMPP İstemcisi

[![CI](https://github.com/albasmustafa/xmpp-client/actions/workflows/ci.yml/badge.svg)](https://github.com/albasmustafa/xmpp-client/actions/workflows/ci.yml)

Tkinter + [slixmpp](https://codeberg.org/poezio/slixmpp) ile yazılmış masaüstü XMPP (Jabber)
istemcisi. Aynı çekirdeği kullanan bir **tarayıcı arayüzü** ve isteğe bağlı, **yerelde
çalışan bir AI asistanı** da içerir. Arayüz Türkçe yazıldı; 14 dilde kullanılabilir.

> **English:** A desktop XMPP client (Tkinter + slixmpp) with OMEMO/OpenPGP encryption,
> multi-device sync (carbons, MAM), group chats, file transfer, a local-first AI assistant
> (Ollama) and a browser UI that runs on the same core. The UI is written in Turkish and
> translated into 13 more languages (English, German, French, Spanish, Italian, Portuguese,
> Dutch, Polish, Russian, Ukrainian, Chinese, Japanese, Korean).

## Öne çıkanlar

**Mesajlaşma**
- Birebir sohbet ve odalar (MUC): yanıtlama, düzeltme, geri çekme, tepkiler, okundu ve
  yazıyor bilgisi, iletme, kaybolan mesajlar.
- ⭐ Yıldızlı mesajlar, 💬 hazır yanıtlar, 🙈 gizli içerik (spoiler), sürükle-bırak ve
  yapıştırmayla dosya gönderme, sesli mesaj.
- 🔔 Bildirim kontrolü: sohbeti 1 saat / 8 saat / 1 gün / sürekli sessize alma; odada
  yalnız adınız geçince ya da size yanıt verilince bildirim; "Meşgul" durumunda sessizlik.
- Oda keşfi ve genel oda araması (search.jabber.network), yer imleri.

**Güvenlik**
- OMEMO ve OpenPGP uçtan uca şifreleme; OMEMO sohbetinde dosyalar da şifrelenir
  (`aesgcm://`). Şifreleme yapılamazsa dosya düz olarak yüklenmez.
- Hassas veri uyarısı: şifresiz sohbete parola, IBAN, kart numarası, T.C. kimlik no ya da
  API anahtarı gibi bir bilgi gidecekse önce sorulur (yerel tarama, model kullanılmaz).
- Kayıtlı parola şifrelenir; ayar, log ve OMEMO dosyaları yalnız sahibinin okuyabileceği
  izinlerle (0600) yazılır.
- SOCKS5 / SOCKS4a / HTTP CONNECT proxy desteği (proxy varken yerel DNS sorgusu yapılmaz).

**Çoklu cihaz**
- Aynı hesap telefonda da açıksa (Conversations, Monocles, Monal…) giden mesajlar, düzeltmeler,
  geri çekmeler ve tepkiler iki tarafta da görünür (Message Carbons).
- Okundu bilgisi eşitleme (XEP-0490): telefonda okuduğunuz sohbet (odalar dahil, okundu
  bilgisi kapalı olsa da) bilgisayarda okunmamış görünmez; bilgisayarda okuduğunuz da
  telefonda okunmuş sayılır.
- Sunucu arşivinden (MAM) geçmiş: birebir sohbetlerde ve odalarda.

**AI asistanı (isteğe bağlı)**
- Varsayılan olarak bilgisayarınızda çalışır ([Ollama](https://ollama.com)); bulut sağlayıcı
  (Claude) isteğe bağlıdır. Şifreli sohbetlerin içeriği izin vermediğiniz sürece buluta gitmez.
- Sohbet ve okunmamış özeti, mesaj çevirisi, yanıt önerisi, geçmişte soru sorma,
  sesli mesajı yazıya dökme (faster-whisper), sesli okuma, görsel açıklama.
- ✨ Asistan: "Ali'ye yarın 10'da geleceğimi yaz" gibi istekleri onayınızla uygular.
- MCP sunucusu (`xmpp_mcp.py`): başka AI araçları geçmişi salt okunur sorgulayabilir;
  taslak bırakabilir ama mesaj gönderemez.

**Tarayıcı arayüzü**
- `./xmpp-web.sh` ile http://127.0.0.1:8420/ adresinde açılır; masaüstü uygulamasıyla aynı
  anda çalışabilir. Tarayıcıdan uygulama olarak kurulabilir (PWA).
- Varsayılan olarak yalnız bu bilgisayardan erişilir. Oturum anahtarı yalnız istek
  başlığında taşınır, WebSocket tek kullanımlık biletle açılır; yabancı Origin ve DNS
  rebinding istekleri reddedilir.

## Kurulum (Linux)

Gerekenler: Python 3 ve Tkinter (dağıtımınızda genellikle `python3-tk` ya da `tk` paketi),
mikrofon için PortAudio (`portaudio` / `portaudio19-dev`).

```bash
git clone https://github.com/albasmustafa/xmpp-client.git
cd xmpp-client
python3 -m venv .venv-xmpp
.venv-xmpp/bin/python -m pip install -r requirements.txt
```

İsteğe bağlı parçalar:

```bash
# Yerel AI modelleri (Ollama kurulu olmalı)
ollama pull gemma4:e2b-it-qat
ollama pull bge-m3

# Sesli mesajı yazıya dökme (~300 MB indirme)
.venv-xmpp/bin/python -m pip install "faster-whisper>=1.1" "av<19"
```

## Çalıştırma

```bash
./xmpp-client.sh        # masaüstü uygulaması
./xmpp-web.sh           # tarayıcı arayüzü → http://127.0.0.1:8420/
```

Web sunucusu seçenekleri: `--port 8420`, `--cert` / `--key` (HTTPS). Başka bir cihazdan
erişim için `--host` vermek ayrıca `--insecure` ister; bu kipte güvenlik denetimleri
kapanır ve trafik düz HTTP'dir, yalnız güvendiğiniz bir ağda kullanın.

## Verileriniz nerede?

Ayarlar, mesaj geçmişi (SQLite), log, OMEMO anahtarları ve avatarlar tek bir veri klasöründe
tutulur. Klasör şu sırayla seçilir:

1. `XMPP_CLIENT_HOME` ortam değişkeni,
2. ev dizinindeki `.xmpp_client_home` dosyasında yazan yol (profili başka bir diske
   taşımak için; klasör bulunamazsa uygulama boş profille açılmaz, durur),
3. ev dizini (`~`).

Mesaj geçmişi yerel veritabanında şifrelenmeden durur; disk şifrelemesi (LUKS vb.) önerilir.

## Geliştirme

```bash
.venv-xmpp/bin/python -m pip install -r requirements-dev.txt
.venv-xmpp/bin/python -m pytest tests/ -q     # ~2400 test; ağ kullanmaz
.venv-xmpp/bin/ruff check .
```

GitHub'da her push ve pull request'te aynı denetimler çalışır (`.github/workflows/ci.yml`; Tk testleri sanal ekranda).

Mimari ve geliştirme kuralları [CLAUDE.md](CLAUDE.md) dosyasındadır. Kısaca:

| Yol | İçerik |
|---|---|
| `xmpp.py` | Uygulama: `MainWindow` (arayüz + durum) ve `XMPPBot` |
| `xmppcore/` | Tk'siz çekirdek: ayar, depolama, şifreleme, MAM, odalar, AI, çeviriler |
| `ui/` | Durumsuz Tk görünüm katmanı (sohbet, diyaloglar, kenar çubuğu) |
| `webapp/` | Tarayıcı arayüzü: aiohttp sunucusu, köprü ve derlemesiz JS önyüz |
| `jingle_ft.py` | Eşler arası dosya aktarımı (Jingle) |
| `xmpp_mcp.py` | MCP sunucusu |
| `tools/` | Gerçek sunucuda uçtan uca denetimler (OMEMO, dosya aktarımı, telefon) |
| `tests/` | pytest testleri |

Yeni arayüz metni Türkçe yazılır ve `_tr()` ile sarılır; çevirileri `xmppcore/locale_*.py`
dosyalarındadır. Masaüstünde dil değişikliği yeniden başlatınca geçerli olur.

## Desteklenen XEP'ler (seçme)

| Alan | XEP |
|---|---|
| Şifreleme | OMEMO (0384), OpenPGP (0027), şifreli medya `aesgcm://` (0454), açık şifreleme işareti (0380) |
| Mesaj | Düzeltme (0308), geri çekme (0424), tepkiler (0444), yanıtlar (0461), spoiler (0382), okundu (0333), teslim bildirimi (0184), yazıyor (0085) |
| Çoklu cihaz ve geçmiş | Message Carbons (0280), okundu eşitleme (0490), MAM (0313), Stream Management (0198), Client State Indication (0352) |
| Odalar | MUC (0045), yer imleri (0048, 0402), doğrudan davet (0249), MUC self-ping (0410) |
| Dosya | HTTP File Upload (0363), Jingle File Transfer (0234), IBB (0047), SOCKS5 (0065), OOB (0066) |
| Kişiler | Engelleme (0191), avatar (0084, 0153), vCard (0054, 0292), takma ad (0172) |

## Lisans

[GPL-3.0-or-later](LICENSE): GNU Genel Kamu Lisansı'nın 3. sürümü ya da (isteğinize göre)
daha sonraki bir sürümü. Kodu değiştirip dağıtan, kaynağını da aynı lisansla paylaşır.
OMEMO için kullanılan `slixmpp-omemo` ve `oldmemo` kitaplıkları AGPL-3.0 lisanslıdır.
