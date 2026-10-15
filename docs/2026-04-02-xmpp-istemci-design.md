# GTK4 XMPP İstemcisi Tasarım Belgesi

## Genel Bakış
Gajim benzeri, tam teşekküllü, modern bir XMPP istemcisi. GTK4 + PyGObject ile sıfırdan yazılacak. slixmpp backend olarak kullanılacak.

## Mimari

### 3 Katmanlı Yapı
1. **Backend (slixmpp)**: XMPP bağlantısı, tüm XEP'ler, mesajlaşma, şifreleme
2. **Data (SQLite)**: Mesaj geçmişi, kişiler, ayarlar, anahtar depolama
3. **Frontend (GTK4)**: Modern UI, tepkisel arayüz, bildirim entegrasyonu

### Dosya Yapısı
Tek dosya: `xmppistemci.py` — tüm kod burada.

## Bağımlılıklar
- `PyGObject` (GTK4, GLib, GObject)
- `slixmpp` (XMPP protokolü)
- `Pillow` (avatar/görsel işleme)
- `cryptography` (şifreleme)
- opsiyonel: `pyaudio` (sesli mesaj)

## UI Düzeni
Gajim tarzı 3 panel:
- **Sol panel**: Kişiler, odalar, arama filtreleme
- **Orta panel**: Aktif sohbet (mesaj balonları, giriş alanı)
- **Sağ panel**: Katılımcılar, oda bilgisi, profil

### Tema
- Sistem teması takip edilir (koyu/açık)
- libadwaita renk şemaları
- Özel accent renk desteği

## Temel Özellikler

### Hesap Yönetimi
- Çoklu hesap desteği
- Hesap ekleme/silme/düzenleme
- Parola şifreleme (Fernet)
- Otomatik yeniden bağlanma

### Mesajlaşma
- Birebir sohbet
- Grup sohbeti (MUC)
- Mesaj gönderme/alma
- Mesaj düzenleme (XEP-0308)
- Mesaj silme/retraction (XEP-0424)
- Mesaj reaksiyonları (XEP-0444)
- Mesaj yanıtlama (XEP-0461)
- Mesaj sabitleme
- Yazıyor durumu (XEP-0085)
- Mesaj okundu bilgisi (XEP-0333)
- Mesaj karbonları (XEP-0280)
- İletme

### Şifreleme
- OMEMO (XEP-0384) — BTBV trust
- OpenPGP (XEP-0027)
- Şifreleme durumu göstergesi

### Dosya Transferi
- HTTP File Upload (XEP-0363)
- Jingle File Transfer (XEP-0234)
- In-Band Bytestreams (XEP-0047)
- SOCKS5 Bytestreams (XEP-0065)
- Görsel önizleme
- Sürükle-bırak dosya gönderme

### Sesli Mesaj
- PyAudio ile kayıt
- WAV/OGG formatında gönderim

### Bildirimler
- Masaüstü bildirimi (GLib notification)
- Ses bildirimi
- Sessiz mod

### Kişiler
- Roster yönetimi
- Avatar desteği (XEP-0084, XEP-0153)
- Durum bilgisi (online/away/busy/dnd)
- Mood, activity (XEP-0107, XEP-0108)
- Abonelik yönetimi
- Engelleme (XEP-0191)

### Grup Sohbet (MUC)
- Oda katılma/ayrılma
- Oda oluşturma
- Katılımcı listesi
- Oda konusu
- Davet gönderme/kabul
- Yer imleri (XEP-0402)
- Anonim ID (XEP-0421)

### Mesaj Arşivi
- MAM (XEP-0313) ile sunucu tarafı arşiv
- SQLite yerel arşiv
- Mesaj arama
- Sohbet dışa aktarma

### URL Önizleme
- HTML meta tag çekme
- Başlık, açıklama, görsel

### Konum Paylaşımı (XEP-0080)
- GPS konum gönderme/alma
- Harita linki oluşturma

### Eklenti Sistemi
- Basit Python eklenti yükleme
- Webhook entegrasyonu

### Çoklu Dil
- Türkçe / İngilizce

## XEP Listesi (Tam Destek)

### Temel & Keşif
- XEP-0004: Data Forms
- XEP-0030: Service Discovery
- XEP-0092: Software Version
- XEP-0115: Entity Capabilities
- XEP-0128: Service Discovery Extensions
- XEP-0199: XMPP Ping
- XEP-0202: Entity Time
- XEP-0203: Delayed Delivery

### Form & Kayıt
- XEP-0050: Ad-Hoc Commands
- XEP-0055: Jabber Search
- XEP-0077: In-Band Registration
- XEP-0122: Data Forms Validation

### Mesajlaşma
- XEP-0066: Out of Band Data
- XEP-0071: XHTML-IM
- XEP-0085: Chat State Notifications
- XEP-0184: Message Delivery Receipts
- XEP-0224: Attention
- XEP-0231: Bits of Binary
- XEP-0249: Direct MUC Invitations
- XEP-0280: Message Carbons
- XEP-0308: Last Message Correction
- XEP-0333: Chat Markers
- XEP-0334: Message Processing Hints
- XEP-0359: Unique and Stable Stanza IDs
- XEP-0422: Message Fastening
- XEP-0424: Message Retraction
- XEP-0444: Message Reactions
- XEP-0461: Message Replies

### Mesaj Arşivi
- XEP-0059: Result Set Management
- XEP-0297: Stanza Forwarding
- XEP-0313: Message Archive Management

### Şifreleme
- XEP-0027: Current Jabber OpenPGP Usage
- XEP-0380: Explicit Message Encryption
- XEP-0300: Cryptographic Hash Functions
- XEP-0384: OMEMO Encryption

### Kişiler & Profil
- XEP-0012: Last Activity
- XEP-0054: vcard-temp
- XEP-0084: User Avatar (PEP)
- XEP-0153: vCard-Based Avatars
- XEP-0172: User Nickname
- XEP-0191: Blocking Command
- XEP-0292: vCard4 Over XMPP

### Grup Sohbet (MUC)
- XEP-0045: Multi-User Chat
- XEP-0048: Bookmarks
- XEP-0402: PEP Native Bookmarks
- XEP-0410: MUC Self-Ping
- XEP-0421: Anonymous Unique Occupant IDs

### PubSub & PEP
- XEP-0060: Publish-Subscribe
- XEP-0163: Personal Eventing Protocol

### Durum / Konum / Aktivite
- XEP-0080: User Location
- XEP-0107: User Mood
- XEP-0108: User Activity
- XEP-0118: User Tune
- XEP-0256: Last Activity in Presence
- XEP-0319: Last User Interaction

### Dosya Transferi
- XEP-0047: In-Band Bytestreams
- XEP-0065: SOCKS5 Bytestreams
- XEP-0096: SI File Transfer
- XEP-0234: Jingle File Transfer
- XEP-0363: HTTP File Upload

### Bağlantı & Mobil
- XEP-0198: Stream Management
- XEP-0352: Client State Indication

## Veritabanı Şeması (SQLite)

### messages tablosu
- id, jid, sender, body, is_me, timestamp, tag, oob, encrypted, mid, edited, pinned, reactions

### contacts tablosu
- jid, name, avatar_hash, blocked, subscription

### rooms tablosu
- jid, nick, auto_join, bookmarked

### accounts tablosu
- id, jid, password_encrypted, enabled

### settings tablosu
- key, value

### plugins tablosu
- name, path, enabled

### webhooks tablosu
- id, name, url, events, enabled
