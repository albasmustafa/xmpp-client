# Jingle Dosya Transferi (XEP-0166 + 0234 + 0261) Tasarım Belgesi

## Özet

Mevcut XMPP istemcisine (xmpp.py) P2P dosya transferi eklenir: Jingle (XEP-0166)
oturum katmanı, dosya tanımı XEP-0234 ve IBB transportu XEP-0261. Gönderim ve
alım desteklenir. Mevcut HTTP Upload (XEP-0363) yolu korunur; kullanıcı gönderim
yöntemini seçer.

Hedef uyumluluk: Conversations (Android), Gajim/Dino (masaüstü) ve kendi
uygulamamız. IBB transportunun Conversations'da desteklendiği doğrulandı
(`urn:xmpp:jingle:transports:ibb:1` disco listesinde ve kendi model paketi var).

> **Not:** Jingle ile yapılan P2P transfer OMEMO uçtan uca şifrelemesi
> kapsamında **değildir** (XEP-0261 §5.1). Dosya TLS üzerinden P2P gider;
> sunucuya yüklenmez ama E2E değildir. Bu, gönderim menüsünde ve gelen teklif
> penceresinde bilgi notu olarak gösterilir.

## Kapsam

**Dahil:**
- 1:1 sohbetlerde gönderim ve alım
- IBB transportu (XEP-0261), SHA-256 hash doğrulama (XEP-0300)
- Gelen teklifte kabul/red, ilerleme göstergesi, iptal, hata yönetimi
- Yetenek keşfi (disco) ve destek yoksa HTTP Upload'a yönlendirme
- İndirme klasörü ve otomatik kabul ayarları

**Hariç (F4'e ertelenir):**
- SOCKS5 transportu (XEP-0260) ve otomatik transport seçimi
- MUC/oda sohbetlerinde Jingle (protokol gereği MUC'ta desteklenmez; HTTP kalır)
- E2E şifreli medya (XEP-0454)
- Çoklu içerik (aynı oturumda birden çok dosya)

## Mimari

Jingle mantığı ayrı modülde tutulur (test edilebilirlik ve dosya boyutu):
`jingle_ft.py`. `xmpp.py` yalnızca kayıt, bot API'si ve GUI içerir.

```
jingle_ft.py
├── NS_JINGLE, NS_FT, NS_IBB, NS_HASHES sabitleri
├── Jingle        (ElementBase)  urn:xmpp:jingle:1
│   └── Content   (ElementBase)
│       ├── File  (slixmpp xep_0234.stanza.File yeniden kullanılır)
│       └── TransportIBB (ElementBase) urn:xmpp:jingle:transports:ibb:1
├── Reason        (ElementBase)  session-terminate sebebi
├── FTSession     (dataclass)    oturum durumu
└── JingleFTManager
    ├── register_stanza_plugins(xmpp)
    ├── start_send(peer, filepath)        → sid döndürür
    ├── handle_session_initiate(iq)       → gui_q'ya "ft_offer"
    ├── accept(sid) / decline(sid) / cancel(sid)
    └── _run_sender(session) / _run_receiver(session)
```

### Stanza modelleri

```xml
<!-- session-initiate (gönderen) -->
<iq type='set' to='kisi@sunucu/kaynak'>
  <jingle xmlns='urn:xmpp:jingle:1' action='session-initiate'
          initiator='ben@sunucu/kaynak' sid='jingle-sid'>
    <content creator='initiator' name='file'>
      <description xmlns='urn:xmpp:jingle:apps:file-transfer:5'>
        <file><name>rapor.pdf</name><size>123456</size>
              <date>2026-09-19T00:00:00Z</date><media-type>application/pdf</media-type>
              <desc>...</desc>
              <hash xmlns='urn:xmpp:hashes:2' algo='sha-256'>BASE64</hash></file>
      </description>
      <transport xmlns='urn:xmpp:jingle:transports:ibb:1'
                 block-size='4096' sid='ibb-sid' stanza='iq'/>
    </content>
  </jingle>
</iq>

<!-- session-accept (alan) -->
<iq type='set'>
  <jingle action='session-accept' sid='jingle-sid'
          responder='kisi@sunucu/kaynak'>
    <content creator='initiator' name='file'>
      <description .../>
      <transport ... sid='ibb-sid' block-size='4096'/>  <!-- blok boyutu düşürülebilir -->
    </content>
  </jingle>
</iq>

<!-- session-terminate -->
<iq type='set'>
  <jingle action='session-terminate' sid='jingle-sid'>
    <reason><success/></reason>
  </jingle>
</iq>
```

Veri akışı **düz XEP-0047 elemanlarıdır** (`<open/>`, `<data/>`, `<close/>`,
`http://jabber.org/protocol/ibb`); slixmpp'in mevcut `xep_0047` eklentisi ve
`IBBytestream` sınıfı yeniden kullanılır (`open_stream`, `sendfile`, `gather`,
`read`, `close`).

### Akış

**Gönderen (initiator):**
1. `start_send(peer, path)`: dosya adı/boyut/mtime/media-type/sha-256 toplanır,
   `content` üretilir, yeni `sid`, `session-initiate` gönderilir.
2. `session-accept` beklenir (60 sn; timeout → terminate + hata olayı).
   Gelen transport'taki `block-size` ve `sid` esas alınır.
3. `xep_0047.open_stream(peer, sid=ibb_sid, block_size=...)` (stanza='iq').
4. Dosya blob halinde değil, parça parça okunur: `IBBytestream.sendfile()`
   döngüsü yerine ilerleme bildirimi için `send()` döngüsü (her parçada
   `("ft_progress", {sid, done, total, ...})`).
5. `close()` + `session-terminate(success)`.

**Alan (responder):**
1. `session-initiate` gelir → oturum `pending` olarak kaydedilir, GUI'ye
   `("ft_offer", {sid, peer, name, size, mime, desc, hash})` gönderilir.
2. GUI `accept(sid, save_path)` → `session-accept` gönderilir (istenirse daha
   küçük blok boyutuyla), ardından
   `xep_0047.api['preauthorize_sid'](ifrom, ibb_sid, jid)`.
3. `stream:<ibb_sid>:<peer>` eventiyle `IBBytestream` alınır; veriler
   `<hedef>.part` geçici dosyasına yazılır, ilerleme bildirilir.
4. Akış kapanınca: boyut ve SHA-256 doğrulanır; başarılıysa `.part` kalıcı
   hedefe taşınır, `session-terminate(success)`, GUI'ye `("ft_done", ...)`.
   Uyuşmazlıkta `.part` silinir, `session-terminate(failed)` + hata olayı.
5. `decline(sid)`: `session-terminate(decline)`.

### xmpp.py entegrasyonu

- `XMPPBot.__init__`: `self.ft = JingleFTManager(self)`; stanza kayıtları
  `JingleFTManager.register_stanza_plugins(self)` ile bir kez yapılır.
- `_register_handlers`: `iq@type=set/jingle` (CoroutineCallback) →
  `self.ft.handle_jingle_iq(iq)`; `session_bind`'te disco feature'ları eklenir:
  `urn:xmpp:jingle:1`, `urn:xmpp:jingle:apps:file-transfer:5`,
  `urn:xmpp:jingle:transports:ibb:1`.
- Bot API (GUI thread'inden çağrılır, `run_coroutine_threadsafe` ile):
  `jingle_send(to, path)`, `jingle_accept(sid, save_path)`,
  `jingle_decline(sid)`, `jingle_cancel(sid)`.
- gui_q olayları:
  `ft_offer`, `ft_progress`, `ft_done`, `ft_error`, `ft_state`
  (`state`: "waiting_accept" | "transferring" | "done" | "cancelled" | "failed").
- `ft_capable(jid)`: disco#info sonucu önbelleklenir; `urn:xmpp:jingle:1` ve
  `...transports:ibb:1` yoksa `False` → GUI HTTP önerir.

### GUI entegrasyonu (MainWindow)

- **Gönderim:** 📎 sol tık → iki seçenekli mini menü: "Sunucuya Yükle (HTTP)" /
  "P2P Gönder (Jingle)". Son seçim `config["file_send_mode"]` olarak hatırlanır;
  tekrar tıklamada varsayılan olarak ilk sıradadır. P2P seçilip karşı taraf
  desteklemiyorsa/çevrimdışıysa uyarı + HTTP'ye düşme teklifi.
- **Gelen teklif penceresi:** gönderen, dosya adı, boyut, SHA-256 (kısaltılmış),
  bilgi notu ("P2P — uçtan uca şifreli değil"); düğmeler: "Kabul Et ve Kaydet"
  (dosya seçici, varsayılan `~/Downloads`), "Reddet". 60 sn yanıtsız → otomatik
  red.
- **İlerleme penceresi:** dosya adı, progress bar, hız, kalan süre, "İptal".
  Gönderim ve alım için ortak bileşen; pencere kapanınca iptal edilir.
- **Sohbet balonu:** dosya mesajı isim + boyut gösterir; "Aç" / "Klasörü Aç".
  HTTP link baloncuğu mevcut davranışını korur.
- **Ayarlar:** indirme klasörü (`download_dir`, varsayılan `~/Downloads`),
  otomatik kabul (`ft_auto_accept`, varsayılan kapalı), IBB blok boyutu
  (`ft_block_size`, varsayılan 4096; en çok 8192), büyük dosya uyarısı
  (`ft_warn_mb`, varsayılan 50 — üzerinde HTTP önerilir).
- **i18n:** yeni anahtarlar tr/en olarak eklenir.

### Veritabanı

`messages` tablosuna `local_path TEXT DEFAULT ''` kolonu eklenir; mevcut
veritabanları için `ALTER TABLE` migration (`PRAGMA table_info` kontrolüyle).
Alınan/gönderilen Jingle dosyaları sohbet balonunda yerel yolla açılır.

## Güvenlik ve hata yönetimi

- Dosya adı temizlenir: dizin ayırıcıları ve `..` atılır, boş/`"."` isimler
  reddedilir; hedef her zaman ayarlanan klasör altında çözülür (path traversal
  koruması).
- Boyut sınırı: `size` beyanı zorunlu; IBB için `ft_warn_mb` üzeri uyarı;
  2 GiB üzeri reddedilir.
- Hash: alıcı SHA-256'yı stream halinde hesaplar ve karşılaştırır; uyuşmazsa
  dosya kalıcılaştırılmaz.
- Zaman aşımları: session-accept 60 sn, ilk veri 30 sn, veri arası 30 sn.
- İptal: her iki taraf da `session-terminate` gönderebilir; karşı taraf
  oturumu kapatır, geçici dosya silinir; tekrarlanan/geç gelen mesajlar
  yok sayılır (sid bilinmiyorsa IQ `item-not-found`).
- Aynı anda birden çok oturum desteklenir (jid başına tek aktif oturum;
  yeni teklif gelirse eski teklif reddedilir).

## Test stratejisi

1. **Birim testleri** (`tests/test_jingle_ft.py`):
   - Stanza üret/parse round-trip (jingle/content/file/transport/reason).
   - `_sanitize_filename` (path traversal, boş isim, unicode).
   - Hash hesaplama/karşılaştırma; `.part` → hedef taşıma davranışı (tmp_path).
   - Oturum durum makinesi: sahte stanza ile pending → accept → done,
     decline, timeout, çakışan sid.
   - İlerleme yüzdesi/ETA yardımcıları.
2. **Uçtan uca** (`tools/ft_e2e.py`): mevcut `tools/omemo_e2e.py` deseniyle iki
   `XMPPBot`, A dosya gönderir, B otomatik kabul eder (manager API),
   byte-eşitlik + sha-256 karşılaştırması. Ortam değişkenleriyle gerçek sunucu
   hesapları (`XMPP_A_JID` vb.) kullanılır.
3. **Manuel interop kontrol listesi:** Gajim (masaüstü), Conversations
   (Android) — karşılıklı gönder/al, red, iptal, büyük dosya, hash hatası
   simülasyonu.
4. **GUI smoke:** mevcut ekran görüntüsü betiği deseniyle teklif ve ilerleme
   pencerelerinin çizimi.
5. `ruff check` + `pytest tests` + `python -m py_compile xmpp.py jingle_ft.py`.

## Aşamalar

- **F1 — Çekirdek:** `jingle_ft.py` stanza katmanı + `JingleFTManager` IBB
  akışı + birim testleri + `tools/ft_e2e.py`. GUI yok; olaylar sys_msg ile.
- **F2 — GUI:** 📎 menüsü, teklif/ilerleme pencereleri, balon, ayarlar,
  DB migration, i18n.
- **F3 — Sertleştirme:** timeout/iptal/hata senaryoları, yetenek keşfi,
  otomatik kabul, interop testleri, büyük dosya uyarısı.
- **F4 — Opsiyonel:** SOCKS5 (XEP-0260) + otomatik transport seçimi.

## Riskler

| Risk | Olasılık | Etki | Önlem |
|------|----------|------|-------|
| Conversations IBB akış farkı | Orta | Yüksek | F1'de e2e + F3'te canlı test; gerekirse 0260'a geçiş |
| IBB yavaşlığı (4-8 KB/IQ) | Yüksek | Orta | Büyük dosya uyarısı + HTTP önerisi; F4 SOCKS5 |
| Stanza eklenti çakışması | Düşük | Orta | slixmpp xep_0234 yalnızca sınıf tanımlıyor (doğrulandı) |
| GUI donması | Düşük | Yüksek | Tüm I/O asyncio döngüsünde, GUI yalnız kuyruk tüketir |
| Kota/rate limit (sunucu) | Orta | Orta | Hata mesajı + HTTP'ye yönlendirme |

## Dosyalar

- **Yeni:** `jingle_ft.py`, `tests/test_jingle_ft.py`, `tools/ft_e2e.py`
- **Değişen:** `xmpp.py` (XEP kaydı, bot API, GUI, DB migration, i18n),
  isteğe bağlı olarak `README.md` (kullanım notu)
- **Değişmeyen:** `requirements.txt` (slixmpp 1.17 gerekli API'leri içeriyor)
