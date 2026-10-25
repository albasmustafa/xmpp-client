# CLAUDE.md

Proje klasörü: `/run/media/albas/albas/xmpp-istemcisi/`. Git deposu diskin köküdür
(`/run/media/albas/albas`) ve **birden çok proje** barındırır (hesapdeepseek, csalbas,
oyunlar…); bu kurallar yalnız bu klasördeki **xmpp.py projesi** içindir.

## xmpp.py — Tkinter + slixmpp XMPP istemcisi (Türkçe arayüz)

Dosyalar: `xmpp.py` (facade, ~12,8K satır) · `xmppcore/` (config, storage, i18n, theme, helpers,
XMPPBot mixin'leri, `ai.py`) · `ui/` (durumsuz Tk görünüm katmanı: `chat/`, `dialogs/`,
`sidebar.py`…) · `jingle_ft.py` (P2P dosya aktarımı) · `xmpp_mcp.py` (MCP sunucusu) ·
`webapp/` (tarayıcı arayüzü: headless köprü + aiohttp sunucusu; aşağıda) ·
`tests/` · `tools/` (uçtan uca betikler) · `docs/` (tasarım belgeleri) · `xmpp-client.sh`
(başlatıcı) · `xmpp-web.sh` (web başlatıcısı) · `_arsiv/` (eski yedekler; git dışı).

> Dikkat: Klasör Ekim 2026'da diskin kökünden buraya taşındı (taşıma commit'i `90f32f8f`).
> Depo başka projelerin commit edilmemiş değişikliklerini de barındırır: commit atarken
> yalnız bu klasörü seç (`git add -- xmpp-istemcisi/`); diğer projelere dokunma.

### Çalıştırma ve test
```bash
./xmpp-client.sh                                   # uygulama (.venv-xmpp içindeki Python)
cd /run/media/albas/albas/xmpp-istemcisi && \
  .venv-xmpp/bin/python -m pytest tests/ -q        # ~1920 test, ~60 sn, ağ kullanmaz
```
Paket kurulumu: `.venv-xmpp/bin/python -m pip install <paket>`. "Test geçti" demek için testi
gerçekten çalıştır.

### Mimari
- **Thread modeli:** Tk ana thread'i tüm widget işlerini yapar. XMPP ayrı asyncio döngüsünde
  koşar ve GUI'ye yalnız `gui_q` üzerinden olay yollar. Worker thread'leri Tk'ya asla doğrudan
  dokunmaz: `self._safe_after(0, fn, *args)` kullanır. GUI'den asyncio'ya geçiş
  `run_coroutine_threadsafe` iledir. Bu model değiştirilmez.
- **MainWindow** tek sınıflık facade'dır (UI + durum); **XMPPBot** mixin'lerden oluşur.
  Dispatcher: `_handle(kind, data)`.
- **ui/** modülleri durumsuzdur: veri/callback parametreyle gelir, tema çağrı anında
  `_app()` (= `import xmpp`) ile okunur. Ağ, DB ve thread YOKTUR (testler bunu kaynak
  taramasıyla zorlar, ör. `test_actions_has_no_domain_dependencies`).
- **Sohbet girişi 10'lu tuple:** `(sender, body, is_me, ts, tag, oob, encrypted, mid,
  local_path, inst_uid)`. `mid` = wire kimliği; `inst_uid` yalnız bellekte tutulur (TTL ve yanıt
  sahipliği), SQLite'a yazılmaz.
- **Kalıcılık:** `xmppcore/storage.py` (tek bağlantı `_db_conn`, işlemler `_db_lock` altında).
  Mesaj gövdesi değişiklikleri ve silmeler yalnız buradan yapılır.
- Ayar: `.xmpp_client.json` · DB: `.xmpp_client_messages.db` · Log: `.xmpp_client.log` ·
  anahtar, `.xmpp_omemo/`, `.xmpp_avatars/` — hepsi veri kökünde (`constants._user_home`):
  `XMPP_CLIENT_HOME` → ev dizinindeki `.xmpp_client_home` dosyasının gösterdiği klasör
  (taşınmış profil; her başlatma yolu aynı yeri bulur, klasör yoksa boş profille açılmaz,
  durur) → `~`. Taşınmış profilde Hugging Face önbelleği (faster-whisper modeli) de oraya
  gider (`HF_HOME`). Bu makinede profil `/run/media/albas/albas/xmpp-veri` (disk deposunun
  `.git/info/exclude`'unda; şifre/anahtar içerir). Giriş: `remember` (şifreyi hatırla, form dolu
  gelir) + `auto_login` (formu atla; anahtar yoksa eski davranış: açık) → `_auto_login_enabled`.
- **Çoklu cihaz** (aynı hesap telefonda Monocles/Conversations/Monal ile de açık): carbons
  (`_on_carbon_sent/_received`, messages.py) ve odada aynı takma adlı oturum
  (`_muc_own_message`; giden filtre `_remember_sent_id` → `_sent_ids`) kendi mesajımızı
  `own_msg` olayıyla verir; presence tüm kaynaklardan birleştirilir (presence.py). Düzeltme/
  geri çekme mesajları `_on_message`'a girmez (kendi olayları var; OMEMO'lu ve PGP'li düzeltme çözülüp
  `msg_correction` olur). Telefonda yapılan düzeltme/geri çekme/tepki (carbon_sent) aynı
  olaylarla `from`=karşı taraf ve gönderen `"Ben"` olarak gelir (`own_to`). Tepki olayı
  gönderenin TAM kümesidir (XEP-0444): kümede olmayan eski tepkisi kalkar.
  Telefona gelen PGP kopyası (carbon_received) `_on_pgp_message`'a bota bağlı yeni
  `Message` olarak verilir: `encrypted_message` iç stanza için tetiklenmez ve iç stanza'nın
  stream'i olmadığından `msg["encrypted"]` çözemez.
  Testler: `test_multi_device.py`, `test_mobile_edits.py`.
- **Şifreli medya** `aesgcm://` (XEP-0454, mobil istemciler OMEMO'da kullanır):
  `xmppcore/aesgcm.py` + `_fetch_url_bytes`; çözme anahtarı AI metnine, sesli okumaya ve
  bildirimlere girmez (`test_aesgcm.py`). **Gönderim:** sohbet OMEMO'daysa
  (`_file_encryption` → `_chat_encryption`) 📎, sürükle-bırak, yapıştırma ve sesli mesaj
  dosyası şifrelenip rastgele adla (uzantı korunur) yüklenir (`transfers.py:_upload_encrypted`);
  bağlantı yalnız OMEMO'lu gövdede gider, OOB'ye yazılmaz. OMEMO hazır değilse dosya
  yüklenmez (düz yüklemeye düşmez); `_send_omemo` şifreleyemezse metni düz gönderir ama
  gövde aesgcm:// anahtarı taşıyorsa göndermez. PGP dosya şifreleyemez: PGP sohbetinde
  dosya şifresiz yüklenmeden önce onay sorulur (`_confirm_plain_file`)
  (`test_omemo_file_send.py`; gerçek sunucuda `tools/omemo_e2e.py` 5. adım —
  TLS doğrulaması açık, yalnız kendinden imzalı yerel sunucuda
  `XMPP_E2E_INSECURE=1`; `test_tools_e2e_tls.py`).
- **İletme ve P2P:** iletilen mesaj (`_forward_to` → `forward_message`) hedef sohbetin
  şifrelemesiyle gider, hedef sohbete kendi mesajımız olarak yazılır (mid = origin-id).
  Şifreli içerik ya da aesgcm:// anahtarı şifresiz sohbete onaysız gitmez; hassas veri
  uyarısı geçerlidir. P2P (Jingle/IBB) uçtan uca şifreli değildir: şifreli sohbette dosya
  seçilmeden önce uyarılır (`test_forward_encryption.py`).
- **Oda arama** (Oda Keşfet → Genel Ara; `_search_rooms_requested`): search.jabber.network
  `POST /search` kelimeyi açıklamada da eşler. `_parse_room_search(veri, kelimeler)` sonucu
  alakaya göre dizer (`format._room_relevance`: adres/ad tam > adda kelime > kelime başı >
  kelime içi > açıklama); açıklaması anahtar kelime yığını olan (`_is_stuffed`: URL'ler hariç
  ≥40 kısa liste öğesi) odanın yalnız oradaki eşleşmesi en sona düşer, atılmaz
  (`test_room_join_search.py` B5).
- **Proxy:** `xmppcore/proxy.py` SOCKS5/SOCKS4a/HTTP CONNECT tüneli kurar; XMPPBot
  `_attempt_connection`/`get_dns_records`'u ezer (proxy varken yerel DNS yok). Yalnız XMPP
  akışını kapsar; HTTP istekleri (dosya, önizleme, GIF, AI) proxy'den geçmez.

### Geliştirme kuralları
1. OMEMO/PGP davranışına dokunma.
2. MainWindow tek facade sınıf kalır (mixin'lere/modüllere bölünmez); yeni kod mevcut
   desenleri izler (ince MainWindow metodu + durumsuz `ui/` görünümü + Tk'sız `xmppcore/`
   mantığı). Büyük pencereler bu desenle `ui/`'a taşınabilir: görünüm veri (`cfg`, `state`)
   ve callback (`actions`, `on_save`) alır; bot/config/thread işleri MainWindow'da kalır.
   Örnek: `_settings_dialog` → `ui/dialogs/settings.py` (+ `_settings_state`,
   `_settings_actions`, `_settings_apply`). Taşımada davranış birebir korunur.
3. Hata düzeltmesinden önce deterministik bir regresyon testi yaz. Kapsam dışı "fırsatçı"
   düzeltme yapma; böyle bir şey görürsen raporla.
4. Bulguları `Claim → Evidence → Verdict (P0–P3)` biçiminde raporla.
5. Kontrat testlerini bozma: `ChatShell.LEGACY_REFS` (26 öğe), sağ tık menüsü öğe sırası,
   `_sidebar_menu_spec` anahtar listesi, ui modüllerinin bağımlılık taraması,
   `_chat_header_menu_spec` (⋮ menüsü; `tests/test_chat_header_menu.py` eski 24 komutun
   hepsinin erişilebilir kaldığını denetler — yeni komut eklerken bu listeyi de güncelle).
6. Arayüz sade kalır: yeni komutlar düz listeye değil ilgili alt menüye girer; ekran
   ölçeği 1,5 (≈1280×720 mantıksal) — pencereler ~690 px yüksekliği aşmamalı.
7. **Açılır kartlar:** kullanıcının açtığı her pencere `_make_popover(win)` ile açılır:
   uygulamada dışarı tıklama ya da Esc kapatır (Tk yerel grab'i; kapanınca grab önceki
   tutana döner), gizli başlayıp açanın ortasına yerleşir (konumsuz Toplevel Hyprland'de
   ekranın sol üst köşesinde açılıyordu), transient yapılır (değilse Hyprland döşer).
   İçerik kesilmez: gösterilmeden önce `_fit_content` en küçük boyutu içeriğin istediği
   boyuta çeker (ekranı aşmadan) — koddaki `geometry("WxH")` piksel boyutları büyük yazılı
   ekranda 21 pencerede seçenekleri/alt düğmeleri kesiyordu; artık yalnız en küçük boyut.
   `-topmost` ve `_safe_grab_set` kullanılmaz. Yazı/seçim içeren formlar (Durum Mesajı,
   Ayarlar, oda/kişi pencereleri…) `form=True` ile: değişiklik yoksa dışarı tıklama
   kapatır; varsa ilk tıklama "Değişiklikler kaybolacak…" şeridini gösterir, şerit
   görünürken (4 sn) ikinci tıklama kapatır — tek yanlış tıklama yazılanı silmez.
   Kapanışta iş yapan pencere `close=` verir (ör. Kişi Grupları kaydeder). Kart OLMAYANLAR
   (asistan pencereleri, log, sohbet sekmesi, gelen dosya teklifi, bildirim) gerekçesiyle
   `tests/test_popovers.py` WINDOWS'tadır; `Toplevel(` açan her işlev PLAIN / FORMS /
   WINDOWS'tan birinde olmalı (tarama testi). İpucu balonu (`_add_tooltip`) önde duran
   `Tooltip` bağlama etiketiyle tıklamada kapanır; kişi hover kartı tıklamada kapanır ve
   tıklanan satırda fare kıpırdadıkça yeniden açılmaz.
8. **Seçilebilir yazılar:** mesaj gövdesi, sesli mesaj dökümü ve asistan yanıtları/sonuç
   kartı `ui/selectable.py` ile kurulur (Label metni seçilemez): kapalı Text, yalnız
   fareyle seçim bağlamaları (`SelectableText` etiketi; tekerlek sohbeti kaydırır, metin
   kendi içinde kaymaz). Tk 8.6.16'nın `tk::TextButton1`'i kapalı Text'e de odak verip
   giriş kutusunu boşa düşürüyordu: odak satırı çıkarılmış kopyası kullanılır. Boyut
   içeriğe göre piksel (`count -ypixels`; emoji/kod kesilmez). Ctrl+C: ana pencere ve
   asistan `<<Copy>>` → `copy_selection`; sağ tık "Kopyala" seçim varsa yalnız seçimi
   alır. ui/chat modülleri onu içe aktarmaz (yalnız tkinter/collections sözleşmesi):
   `text_factory` MainWindow'dan gelir, kutu `set_content`/`set_bg` taşır. Yazı tipi
   ayarı (`set_family`) ve tema yenilemesi (etiket/seçim renkleri) kutuları korur. Sahte
   Tk testleri `tests/fake_selectable.py` kullanır.

### Test desenleri
- DB: `monkeypatch.setattr(xmpp, "_DB_PATH", tmp)` + `xmpp._db_conn = None` (teardown'da
  `close()`). Örnek: `tests/test_contract_config_storage.py`.
- Yalıtım: `tests/conftest.py` `XMPP_CLIENT_HOME`'u geçici dizine ayarlar; ayar/DB/log/
  anahtar/OMEMO yolları buradan türetilir (`xmppcore.constants._user_home`), test oturumu
  gerçek profile dokunmaz (`tests/test_user_data_isolation.py`). Duman/e2e betiklerine de
  `XMPP_CLIENT_HOME=<boş dizin>` verin (OMEMO eskiden hep `~/.xmpp_omemo`'ya yazıyordu).
- Tk'sız pencere çifti: `object.__new__(xmpp.MainWindow)` + gereken öznitelikler;
  `_load_chat` için hazır `_win()` → `tests/test_history_window_bounds.py`.
- Testler arası import serbest (`from test_history_window_bounds import _win`).
- Sahte MainWindow (`MagicMock` dönen `__getattr__`) ile pencere testinde gerçek metotlar
  çalışabilir ve diske yazabilir (ör. `_export_chat` çalışma dizinine dosya bırakır); tetiklenen
  hedef metotları örnek üzerinde `MagicMock` ile değiştir. Gizli kök altındaki pencere çizilmez;
  Tk çizilmemiş widget'a fare olayı iletmez (`ttk.Button.invoke` çalışır).
- Kaldırılan özellikler (sesli arama, ekran paylaşımı, eklenti sistemi, webhook) geri
  gelmemeli: `tests/test_removed_features.py`.

### AI asistanı (`xmppcore/ai.py`, `ui/dialogs/ai.py`, MainWindow `_ai_*`)
- **Özellikler:** sohbet ve okunmamış özeti, ses→metin (faster-whisper), mesaj çevirisi,
  taslak düzeltme/resmîleştirme/kısaltma + yanıt önerisi, anlamsal arama (gömme), görsel
  açıklama ve görsele soru sorma; "Neler kaçırdım?" (tüm okunmamışların özeti), geçmişe
  sor (RAG: yerel gömmeyle bul, kaynaklı yanıt), görev/etkinlik çıkarma (.ics + kalıcı
  hatırlatıcı, config `"ai_reminders"`), sesle yazma (dikte → giriş kutusu).
- **Modelsiz yerel yardımcılar:** sesli mesaj dökümü balonda (`_ai_inline_transcript`;
  `"auto_transcribe"` açıksa gelen sesler tek worker'lı kuyrukta, en yeni önce yazıya
  dökülür; faster-whisper yoksa `AISetupError` ile oturumluk kapanır) · şifresiz
  gönderimde hassas veri uyarısı (`xmppcore/sensitive.py`, `_leak_guard_ok`; IBAN/kart/
  TCKN sağlamalı, bulgular maskeli; `"leak_guard"`) · yanıt bekleyen sorular
  (`xmppcore/questions.py`, `_ai_pending_questions`; yok sayılanlar config
  `"dismissed_questions"`; bağlanınca 1 saatten eski soru varsa tek toast).
- **Ajan / ✨ Asistan** (`xmppcore/agent.py`, `ui/dialogs/ai.py:AssistantWindow`,
  MainWindow `_ai_agent_*`; kenar çubuğunda kişi görünümlü giriş, Ctrl+Shift+K): doğal dil →
  tek eylem (yapılandırılmış JSON, `PLAN_SCHEMA`). Hedef YEREL çözülür (`resolve_target`;
  kişi listesi modele gitmez). `CONFIRM_ACTIONS` (gönder, hatırlatıcı, odaya katıl, durum)
  her zaman kartla onaylanır; gönderim `_ai_agent_send` → normal `_send_message` yolu
  (hassas veri uyarısı dahil), kullanıcının sohbeti/taslağı geri yüklenir. Asistan XMPP
  kişisi DEĞİLDİR: `self.active`/roster/stanza yollarına girmez — böyle kalmalı.
  **Bağlam:** ana penceredeki açık sohbet (`_ai_agent_context`); hedef boşsa ya da
  "bu sohbet" denirse (`is_context_ref`) o kullanılır, adı modele gitmez. **Modelsiz kısa
  yollar:** tam eşleşen sık komutlar (`quick_intent`, "Geçmişe sor: …" öneki ve "Durumumu
  meşgul yap" gibi durum komutları dahil) ve üstteki hızlı eylem çipleri
  (`quick_action_groups` → `_ai_agent_quick`) plan için modele gitmez. **Durum sözü
  yereldir:** küçük model "meşgul"ü away/xa, "uzaktayım"ı xa planlıyordu; `status_hint`
  kullanıcının yazdığı sözü (meşgul/rahatsız etme → dnd, uzakta → away, uzun süre uzakta
  → xa, çevrimiçi/müsait → online; olumsuz ya da çok anlamlıysa model) modelin seçiminden
  önce koyar (`parse_plan(…, request=metin)`). Durum menüsü (`STATUS_OPTIONS`) aynı
  sözlüğü `STATUS_LABELS`'tan alır ("Uzakta" = away); Durum Mesajı penceresi
  (`presence.status_choices`, 2×2), Ayarlar ve web arayüzü de aynı adları kullanır ("chat" =
  Çevrimiçi; `test_status_vocabulary.py`). Durum Mesajı penceresi mevcut durumla (`_my_show`,
  `_status_text`) açılır; pencere, /status ve Ayarlar yayını `_show_my_status` ile kenar
  çubuğuna ve `_my_show`'a yansır (`test_status_dialog_state.py`). Menü seçimi de
  `presence_show` olarak kaydedilir; bağlanınca `_restore_status_prefs` kenar çubuğunu ve
  `_my_show`'u her zaman eşitler. Otomatik uzakta yalnız Çevrimiçi'yken devreye girer
  (`_auto_away`; elle Meşgul/Uzakta ezilmez) ve durum mesajını korur; boştayken yeniden
  bağlanınca kayıtlı Çevrimiçi yerine otomatik uzakta yeniden yayınlanır
  (`test_status_persistence.py`). Durum adlarının tek kaynağı `STATUS_LABELS`'tır; i18n'de
  ikinci bir durum sözlüğü tutulmaz. `status_hint` durumdan çıkışı ("meşgulden çıkar") ve
  olumsuz emri ("meşgul yapma") modele bırakır (`test_status_hint_direction.py`). `_ai_assistant_refresh` çipleri bağlam/okunmamış/
  taslak sayısıyla tazeler: `_load_chat` (sayaç sıfırlandıktan SONRA), gelen mesaj,
  `own_msg`/`read_elsewhere` ve `_ai_drafts_refresh` çağırır; çipler değişmediyse yeniden
  kurulmaz (`test_ai_assistant_counts.py`). "📬 Okunmamışları özetle (n)" açılıştaki sayıyı
  (`_ai_unread_at_open`) tutar; o sohbete masaüstünden ya da telefondan yanıt verilince
  `_ai_caught_up` sıfırlar (bot komutu sıfırlamaz). Çipler ⋮ menüsü gibi "💬 Bu sohbet" / "🗂 Tüm sohbetler"
  gruplu, simgeleri ayrı (`ACTION_LABELS`) ve pencere genişliğine göre satır kırar
  (`_flow`, place); bağlam/alt başlık/durum satırları da genişlikte kırılır. Meşgulken
  tıklanan eylem sıraya girer (durum satırında "sırada: …"), meşguliyet bitince
  `after_idle` ile çalışır; "Temizle" sırayı boşaltır; meşgulken durum satırı geçen
  saniyeyi sayar. **Ön yükleme:** asistan açılınca Ollama modeli arka planda belleğe
  alınır (`_ai_warm_model` → `ai.ollama_warm`, boş /api/chat; `num_ctx` gerçek istekle
  aynı olmalı, yoksa model yeniden yüklenir). **Sonuçlar asistanın içinde:** asistandan istenen özet,
  neler kaçırdım, yanıt önerisi, bekleyen sorular ve geçmişe sor `inline=True` ile
  `InlineResult` kartına akar (`_ai_open_window`/`_ai_result_window`/`_ai_notice`;
  asistan kapalıysa eski pencereler). Kart ResultWindow arayüzünü taşır; takip sorusu
  asistanın giriş kutusundan gelir (`set_followup`, Esc/✗ komut kipi). Asistan kapanınca
  ya da "Temizle"de kartların akışı iptal edilir. Görev çıkarma ve taslaklar düzenlenebilir
  liste olduğundan kendi penceresinde kalır. Testler: `tests/test_ai_assistant_inline.py`.
- **Yanıt taslakları** (`_ai_drafts`, Ctrl+Shift+R): uzaktayken (`_is_idle` ya da elle
  away/xa) gelen 1:1 mesajlara gecikmeli yanıt önerisi + harici (MCP/REST `/api/draft`)
  taslaklar. Asla gönderilmez; şifreli+bulut+izinsiz → "onay bekliyor" (arka planda soru yok).
- **Satır içi öneri** (`ui/chat/suggest.py`, `_ai_complete_*`): sözcük sonunda duraksayınca
  kısa devam (`max_tokens`); yalnız Ollama; Tab kabul, Esc gizle. Çubuk giriş satırının
  `grid` satırı 1'dedir — giriş alanının `pack` sırasına (yanıt/sabit çubukları) koyma.
- **Sesli okuma** (`xmppcore/tts.py`, `_ai_speak_*`): piper/espeak-ng/espeak/spd-say;
  komutlar kabuksuz, metin stdin'den; tek okuma (nesil sayacı), `_quit` durdurur.
- **MCP sunucusu** (`xmpp_mcp.py` → `xmppcore/mcp_server.py`, stdio JSON-RPC): DB'yi salt
  okunur açar; `ai.mcp_enabled` kapalıyken her araç reddedilir; şifreli gövdeler
  `mcp_include_encrypted` olmadan gizli ve aramada eşleşmez; yazma yok, `draft_reply`
  yalnız REST `/api/draft` ile taslak kutusuna düşer (port config `"api_port"`).
- **Akış ve takip soruları:** özet/çeviri/görsel/neler-kaçırdım/geçmişe-sor pencereleri yanıtı
  akışla yazar (`chat(on_delta=…)` → `StreamSink` → `_safe_after`) ve takip sorusu kabul
  eder (`Conversation`, `_ai_turn`, `_ai_followup`). Pencere kapanınca `cancel` olayı
  akışı keser (`AICancelled`, `_ai_submit` sessizce yutar). Asistan turları geçmişe yalnız
  METİN olarak döner (düşünme blokları saklanmaz); Claude'da üst düzey `cache_control`.
- **Giriş noktaları — ✨ Asistan tek merkez:** kenar çubuğundaki asistan girişi,
  Ctrl+Shift+K ve giriş kutusundaki ✨ menüsünün ilk öğesi asistanı açar. ⋮ başlık
  menüsü → ✨ AI Asistanı öğeleri ve kısayollar Ctrl+Shift+M (neler kaçırdım),
  Ctrl+Shift+H (geçmişe sor), Ctrl+Shift+Q (yanıt bekleyen sorular) asistanı açıp sonucu
  onun içinde gösterir (`_ai_assistant_run(eylem, jid)` → `_ai_agent_quick`; etiketler
  `agent.ACTION_LABELS`). Giriş kutusu ✨ menüsünde yalnız yazma araçları kalır (yanıt
  öner — öneriler asistanda, dikte Ctrl+Shift+S, taslağı düzenle, geri al). Görev
  çıkarma, taslaklar (Ctrl+Shift+R) ve anlamsal arama kendi penceresindedir; mesaj
  başına araçlar (çeviri, ses→metin, görsel, sesli okuma) sağ tık / hover ✨ menüsünde
  ve ayrı pencerededir.
- **Sağlayıcı:** varsayılan yerel Ollama (`gemma4:e2b-it-qat` metin+görsel, gömme `bge-m3`;
  2026-10-20 ölçümü, i7-7500U/15 GB: sıcak özet 63 sn — gemma3:4b 93 sn, gemma4:e4b 161 sn).
  İstekler `think: false` gönderir (Gemma 4 düşünme tokenları dakikalar sürer). Yükleme
  seçenekleri `_ollama_load_options` (num_ctx; `"ollama_gpu": "off"` → `num_gpu: 0`, zayıf
  ekran kartında CPU daha hızlı) ön yükleme ve gerçek istekte aynıdır. İsteğe bağlı Claude
  (`anthropic` SDK, varsayılan `claude-opus-5-5`, sunucu tarafı `fallbacks: "default"`).
  Ayarlar config'te `"ai"` anahtarında; API anahtarı `_encode_pw` ile şifreli saklanır.
  İstem kuralları gerçek e2b ölçümünden gelir (`test_ai_prompt_quality.py`): özetler
  kullanıcıya "siz" der ve istek yönünü korur (`_PERSON_RULE`), "neler kaçırdım" bekleyenleri
  önce listeler, görev çıkarma her toplantıyı alır, öneriler bekleyen soruyu yanıtlar.
- **Gizlilik sözleşmesi:** şifreli sohbet içeriği buluta, `cloud_for_encrypted` kapalıyken
  yalnız istek başına alınan açık onayla gider (`ensure_allowed` → `AIPrivacyError` →
  `_ai_gate`); takip soruları da ayrı istektir, her biri yeniden sorulur. Çok sohbetli
  istekler (neler kaçırdım, geçmişe sor) `_ai_gate_mixed` ile üç yollu sorar: hepsi / şifreli
  içerik çıkarılsın / hiçbiri. Gömme ve ses→metin her zaman yereldir. Sohbet içeriği
  prompt'a etiket içinde **veri** olarak girer.
- **DB:** `ai_embeddings` (msg_id → vektör) ve `ai_cache` (ses metni, görsel açıklaması).
  `messages.timestamp` yalnız "SS:DD" tutar; tam kayıt tarihi `messages.stored_at`'tadır
  (eski satırlarda boş).
  Düzeltme/geri çekme gömmeyi düşürür; geçmiş silme türetilmiş veriyi de siler.
- **Model kurulumu:** `ollama pull gemma4:e2b-it-qat && ollama pull bge-m3`; ses→metin için
  `.venv-xmpp/bin/python -m pip install faster-whisper "av<19"` — faster-whisper 1.2.1 (en
  yenisi) PyAV 19'da kaldırılan `metadata_errors`'u geçiriyor; PyAV 19 ile her ses
  çözümü düşer (uygulama bunu düzeltme komutuyla `AISetupError` olarak bildirir).
  `tests/test_ai_core.py::test_installed_speech_stack_decodes_audio` kurulu ikiliyi denetler.
- Testler: `tests/test_ai_core.py`, `tests/test_ai_storage.py`, `tests/test_ai_mainwindow.py`,
  `tests/test_ai_stream_core.py` (Tk'sız çekirdek), `tests/test_ai_assistant_flows.py`
  (MainWindow akışları), `tests/test_ai_dialog_view.py` (sahte tk ile görünüm),
  `tests/test_ai_inline_transcript.py`, `tests/test_ai_privacy_guard.py`,
  `tests/test_ai_questions.py`, `tests/test_ai_agent.py`, `tests/test_ai_drafts.py`,
  `tests/test_ai_inline_complete.py`, `tests/test_ai_tts.py`, `tests/test_ai_settings_view.py`,
  `tests/test_mcp_server.py` (gerçek stdio süreci dahil).

### Tarayıcı arayüzü (`webapp/`, `./xmpp-web.sh` → http://127.0.0.1:8420/)
- **Mimari:** masaüstüyle aynı XMPPBot çekirdeği, Tk'siz. `bridge.py:WebSession`
  `xmpp.start()` ile aynı thread modelini kurar (bot ayrı asyncio döngüsünde, olaylar
  `gui_q` ile); `_apply`, MainWindow `_handle`/`_store`'un Tk'siz karşılığıdır — davranış
  farkları burada notlanır (TTL/kaybolan mesaj, ayrı sohbet penceresi, dikte/taslak gibi
  masaüstü-özel kısımlar yok). Durum + SQLite yazımı köprüde, pencere işleri tarayıcıdadır.
- **MAM (XEP-0313) — iki istemcide de geçmiş:** masaüstü `_load_chat`'ta yerel geçmiş
  boşsa arşivin son sayfasını çeker (`_load_mam_history`; **odalar dahil** — oda arşivi
  odanın kendisinden `jid=`, 1:1 `with=` ile; `ArchiveMixin` yönü odada takma adla
  (resource) belirler, `nick` alanı resource'tan gelir). "Daha eski" `_load_older_mam`
  archive_id imleciyle sayfalar. Köprü: `open_chat`'ta DB boşsa `initial`, "daha eski
  MAM" `load_older_mam` komutu; `mam_results` tek-kuşak token + niyet ([2F-Blocker]
  aynen) ile tüketilir, **DB'ye yazılır** (masaüstü bellek-only'dir — bilinçli fark:
  web geçmişi DB'den okur; `stored_at` gerçek MAM zamanıdır). `/api/history`
  stored_at+id sıralı ve (stored_at, id) imleçli sayfalanır.
- **Sunucu:** `server.py` (aiohttp; yeni bağımlılık YOK — aiohttp zaten requirements'ta).
  Tek hesaplı, varsayılan 127.0.0.1:8420. REST: `/api/login|logout|prefill|history|settings`,
  `/api/ai/{summary|translate|digest|ask|assistant}` (aiapi.py; `AIPrivacyError` → 403,
  izin tarayıcıdaki onay kutusuyla istek başına verilir). WS `/ws?ticket=`: hello snapshot +
  olay akışı (gui_q izdüşümü) + komut (`send`, `typing`, `mark_displayed`, `correct`,
  `retract`, `react`, `join_room`, `set_enc`, `load_older_mam`… → `WebSession.command`).
- **Güvenlik modeli (pentest 2026-10 düzeltmeleri):** token yalnız `X-Auth-Token`
  başlığında taşınır (URL'de yok); WS tek kullanımlık 30 sn'lik bilet ile açılır
  (`POST /api/ws-ticket`, bilet token'a eşlenir). `_origin_guard` middleware'i yerel
  döngü dışı Host (DNS rebinding) ve yabancı Origin (tarayıcı-CSRF) istekleri 403'ler;
  `/api/login` ayrıca `X-Requested-With: xmpp-web` başlığı ister (basit istek CSRF'i
  kapalı) ve dakikada 10 denemeyle sınırlıdır. Loopback dışı `--host` yalnız
  `--insecure` ile açılır (denetimler atlanır, düz metin HTTP). Uzak görsel
  önizlemeleri `remote_previews` ayarıyla kapatılabilir. Bilinen kalıntı riskler
  (kabul edilmiş): Fernet anahtarı şifreli parolanın yanındadır (ev LUKS altında),
  oturum token'larının ömrü sınırsızdır (yerel yüzey).
- **Frontend:** `webapp/static/` (vanilla JS, derlemesiz). Tema renkleri `xmppcore/theme`
  paletinden CSS değişkeni olarak gelir (`/api/settings` → `theme_colors`).
- **Ölçek:** web köprüsü aynı `~/.xmpp_client.json` ve mesaj DB'sini paylaşır; masaüstüyle
  aynı anda çalışabilir (çoklu cihaz yolu: carbons + aynı OMEMO deposu). `storage.py`'ye
  web için eklenen `_db_load_msgs_full` salt-okunurdur; gövde mutasyonları hâlâ yalnız
  `storage.py`'dendir.
- Testler: `tests/test_webapp.py` (sahte bot + sahte döngüyle `_apply`/`command` ve
  aiohttp TestClient ile REST/WS; ağ ve Tk yok).
