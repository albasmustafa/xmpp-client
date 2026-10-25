"""İngilizce arayüz kataloğu: Türkçe metin (anahtar) → İngilizce.

`{}` yer tutucuları şablonla aynı kalmalı (`tests/test_i18n_catalog.py`
denetler). Kaynak dosyaya göre gruplu; yeni metin eklerken buraya da ekleyin.
"""

EN = {
    # ── jingle_ft.py ──
    "Veri zaman aşımı":
        "Data timed out",
    "Beyan edilen boyut aşıldı":
        "Declared size exceeded",
    "Dosya 2 GiB sınırını aşıyor":
        "File exceeds the 2 GiB limit",
    "Kabul zaman aşımı":
        "Accept timed out",
    "Teklif gönderilemedi: {}":
        "Could not send offer: {}",
    "Hash uyuşmadı":
        "Hash mismatch",
    "Hash uyuşmazlığı":
        "Hash mismatch",
    "Reddedildi":
        "Declined",
    "İptal edildi":
        "Cancelled",
    "Yeni teklif":
        "New offer",
    "Yeni teklif geldi":
        "A new offer arrived",
    "Karşı taraf kapattı: {}":
        "The other side closed: {}",
    "sebep yok":
        "no reason",
    # ── ui/chat/actions.py ──
    "↪ Alıntılanan mesaja git":
        "↪ Go to quoted message",
    "👥 Tepkileri gör…":
        "👥 View reactions…",
    "✨ AI":
        "✨ AI",
    "🌐 Çevir":
        "🌐 Translate",
    "🎙 Sesi yazıya dök":
        "🎙 Transcribe audio",
    "🖼 Görseli açıkla":
        "🖼 Describe image",
    "❓ Görsele soru sor…":
        "❓ Ask about image…",
    "🔊 Sesli oku":
        "🔊 Read aloud",
    "😀 Daha fazla emoji…":
        "😀 More emoji…",
    # ── ui/chat/audio.py ──
    "🎤 Yükleniyor…":
        "🎤 Loading…",
    "🎤 Ses Mesajı":
        "🎤 Voice Message",
    "🎤 Ses: {}…":
        "🎤 Audio: {}…",
    # ── ui/chat/history.py ──
    "⬆ Daha eski":
        "⬆ Older",
    "↓ En yeni":
        "↓ Newest",
    "↓ Yeni mesajlar ({})":
        "↓ New messages ({})",
    # ── ui/chat/media.py ──
    "📷 Yükleniyor…":
        "📷 Loading…",
    "⚠ Resim yüklenemedi":
        "⚠ Image could not be loaded",
    "ESC ile kapat":
        "Close with ESC",
    # ── ui/chat/suggest.py ──
    "Tab ↹ kabul · Esc kapat":
        "Tab ↹ accept · Esc close",
    # ── ui/dialogs/ai.py ──
    "Takip sorusu sorun…":
        "Ask a follow-up question…",
    "⏳ Hazırlanıyor…":
        "⏳ Preparing…",
    "Sor ↵":
        "Ask ↵",
    "✓ Hazır":
        "✓ Ready",
    "✍ Yazılıyor…":
        "✍ Writing…",
    "⏳ Yanıt hazırlanıyor…":
        "⏳ Preparing reply…",
    "Seçince giriş kutusuna yerleştirilir:":
        "Picking one puts it in the input box:",
    "Anlamsal Arama":
        "Semantic Search",
    "🧠  Anlamla Ara":
        "🧠  Search by Meaning",
    "Örn: \"geçen ay konuşulan fiyat\", \"buluşma yeri\"":
        "E.g. \"the price we discussed last month\", \"meeting place\"",
    "Ne arıyorsunuz?":
        "What are you looking for?",
    "📅 Etkinlik":
        "📅 Event",
    "✅ Görev":
        "✅ Task",
    "Tarih ve saatler sohbetten tahmin edildi; kaydetmeden önce kontrol edin (YYYY-AA-GG, SS:DD).":
        "Dates and times were guessed from the chat; check them before saving (YYYY-MM-DD, HH:MM).",
    "📅 .ics olarak kaydet":
        "📅 Save as .ics",
    "⏰ Hatırlatıcı kur":
        "⏰ Set reminder",
    "✓ {} öğe bulundu — seçip kaydedin ya da hatırlatıcı kurun.":
        "✓ {} items found — select and save them or set a reminder.",
    "Bu sohbette görev ya da etkinlik bulunamadı.":
        "No tasks or events found in this chat.",
    "Tarih":
        "Date",
    "Saat":
        "Time",
    "Bitiş":
        "End",
    "Yer":
        "Place",
    "Önce en az bir öğe seçin.":
        "Select at least one item first.",
    "📋 Panoya kopyalandı":
        "📋 Copied to clipboard",
    "💬 Sohbete git":
        "💬 Go to chat",
    "⏰ Yarın 09:00 hatırlat":
        "⏰ Remind tomorrow 09:00",
    "✓ Yok say":
        "✓ Dismiss",
    "{} sohbette yanıt bekleyen soru var.":
        "{} chats have unanswered questions.",
    "Yanıt bekleyen soru yok. 🎉":
        "No unanswered questions. 🎉",
    "Yanıt Bekleyen Sorular":
        "Unanswered Questions",
    "❓  Yanıt Bekleyen Sorular":
        "❓  Unanswered Questions",
    "Son mesajınızdan sonra size sorulan ve henüz yanıtlamadığınız sorular. Tespit bilgisayarınızda yapılır; hiçbir içerik dışarı gönderilmez.":
        "Questions you were asked after your last message and haven't answered yet. Detection runs on your computer; no content is sent anywhere.",
    "⏳ Taranıyor…":
        "⏳ Scanning…",
    "↩ Takip sorusu":
        "↩ Follow-up question",
    "✓ Giriş kutusuna kondu — kontrol edip siz gönderin.":
        "✓ Put in the input box — check it and send it yourself.",
    "✓ Bir öneri seçin":
        "✓ Pick a suggestion",
    "Asistan":
        "Assistant",
    "✨  Asistan":
        "✨  Assistant",
    "Bir komut yazın ya da soru sorun…":
        "Type a command or ask a question…",
    "↩ Takip sorusu: {} — {}  (Esc: komut)":
        "↩ Follow-up: {} — {}  (Esc: command)",
    "{}  ·  sırada: {}":
        "{}  ·  queued: {}",
    "sırada: {}":
        "queued: {}",
    "Örnekler — tıklayın ya da kendiniz yazın:":
        "Examples — click one or type your own:",
    "✗ Vazgeç":
        "✗ Cancel",
    "Vazgeçildi.":
        "Cancelled.",
    "Yanıt Taslakları":
        "Reply Drafts",
    "📝  Yanıt Taslakları":
        "📝  Reply Drafts",
    "Taslaklar asla kendiliğinden gönderilmez: “Kullan” metni sohbetin giriş kutusuna koyar, düzenleyip siz gönderirsiniz.":
        "Drafts are never sent on their own: “Use” puts the text in the chat's input box, you edit and send it yourself.",
    "{} sohbet için taslak var.":
        "Drafts are ready for {} chats.",
    "Bekleyen taslak yok.":
        "No pending drafts.",
    "{} yeni mesaj":
        "{} new messages",
    "⏳ Taslak hazırlanıyor…":
        "⏳ Preparing draft…",
    "🔒 Şifreli sohbet: taslak için içerik buluta (Claude) gönderilmeli.":
        "🔒 Encrypted chat: the content must be sent to the cloud (Claude) for a draft.",
    "➡ Kullan":
        "➡ Use",
    "☁ Onayla ve hazırla":
        "☁ Approve and prepare",
    "🔄 Yeniden üret":
        "🔄 Regenerate",
    "✓ Kaldır":
        "✓ Remove",
    "Kapalı":
        "Off",
    "🖥 Yerel — Ollama (önerilen; veri bilgisayarda kalır)":
        "🖥 Local — Ollama (recommended; data stays on your computer)",
    "☁ Claude — bulut (Anthropic API)":
        "☁ Claude — cloud (Anthropic API)",
    "AI Ayarları":
        "AI Settings",
    "✨ AI Asistanı":
        "✨ AI Assistant",
    "Şifreli sohbetler varsayılan olarak yalnız yerel modelle işlenir. Ses→metin ve anlamsal arama her zaman yereldir.":
        "Encrypted chats are processed only by the local model by default. Speech-to-text and semantic search are always local.",
    "🤖 Model":
        "🤖 Model",
    "SAĞLAYICI":
        "PROVIDER",
    "YEREL MODEL (OLLAMA)":
        "LOCAL MODEL (OLLAMA)",
    "Adres":
        "Address",
    "Sohbet modeli":
        "Chat model",
    "Görsel modeli":
        "Vision model",
    "Gömme modeli":
        "Embedding model",
    "Model sıcak":
        "Keep model warm",
    "Ekran kartı":
        "Graphics card",
    "Kurulum: ollama pull {}  ·  ollama pull {}\nModel, bu süre boyunca bellekte tutulur; boşta geçen isteklerde yeniden yükleme beklemesi olmaz (5 dk = Ollama varsayılanı). Ekran kartı \"off\": sohbet modeli yalnız CPU'da (zayıf ekran kartında daha hızlı).":
        "Setup: ollama pull {}  ·  ollama pull {}\nThe model is kept in memory for this long, so requests after idle time don't wait for a reload (5 min = Ollama default). Graphics card \"off\": the chat model runs on the CPU only (faster with a weak graphics card).",
    "☁ Claude":
        "☁ Claude",
    "CLAUDE (BULUT)":
        "CLAUDE (CLOUD)",
    "Model":
        "Model",
    "API anahtarı":
        "API key",
    "Kayıtlı anahtar var — değiştirmek için yazın.":
        "A key is saved — type to change it.",
    "Boş bırakılırsa ANTHROPIC_API_KEY ortam değişkeni kullanılır.":
        "If left empty, the ANTHROPIC_API_KEY environment variable is used.",
    "Kayıtlı anahtarı sil":
        "Delete saved key",
    "Şifreli sohbetlerde de her seferinde sormadan Claude'u kullan (önerilmez)":
        "Use Claude in encrypted chats too without asking each time (not recommended)",
    "✨ Özellikler":
        "✨ Features",
    "GENEL":
        "GENERAL",
    "Çeviri/yanıt dili":
        "Translation/reply language",
    "Şifresiz gönderimde parola/IBAN/kart gibi hassas bilgi uyarısı (yerel)":
        "Warn about sensitive data like passwords/IBAN/cards when sending unencrypted (local)",
    "ASİSTAN":
        "ASSISTANT",
    "Yazarken satır içi öneri — Tab ile kabul et (yalnız yerel Ollama modeliyle çalışır)":
        "Inline suggestions while typing — accept with Tab (works only with a local Ollama model)",
    "Uzaktayken gelen mesajlara yanıt taslağı hazırla (asla gönderilmez; dönüşte gözden geçirirsiniz)":
        "Prepare reply drafts for messages received while away (never sent; you review them when you return)",
    "🎙 Ses":
        "🎙 Voice",
    "SES → METİN":
        "SPEECH → TEXT",
    "Whisper modeli":
        "Whisper model",
    "Gelen sesli mesajları otomatik yazıya dök (yerel, faster-whisper)":
        "Automatically transcribe incoming voice messages (local, faster-whisper)",
    "SESLİ OKUMA":
        "READ ALOUD",
    "Motor":
        "Engine",
    "Piper ses modeli":
        "Piper voice model",
    "Okuma dili":
        "Reading language",
    "Motor yoksa: sudo pacman -S espeak-ng · Piper için .onnx ses modelinin tam yolunu girin (ör. tr_TR-dfki-medium.onnx).":
        "No engine: sudo pacman -S espeak-ng · For Piper, enter the full path of the .onnx voice model (e.g. tr_TR-dfki-medium.onnx).",
    "🔌 MCP":
        "🔌 MCP",
    "CLAUDE CODE / DESKTOP":
        "CLAUDE CODE / DESKTOP",
    "MCP erişimi: harici AI araçları sohbet geçmişini okuyabilir ve taslak bırakabilir (mesaj gönderemez)":
        "MCP access: external AI tools can read chat history and leave drafts (they cannot send messages)",
    "MCP'ye şifreli mesajların içeriğini de göster (önerilmez)":
        "Also show the content of encrypted messages to MCP (not recommended)",
    "Kayıt komutu (taslak için REST API de açık olmalı):":
        "Registration command (the REST API must also be on for drafts):",
    "📋 MCP komutu panoya kopyalandı.":
        "📋 MCP command copied to clipboard.",
    "⏳ Test ediliyor…":
        "⏳ Testing…",
    "🔌 Bağlantıyı Test Et":
        "🔌 Test Connection",
    # ── ui/dialogs/chat_actions.py ──
    "Mesajı İlet":
        "Forward Message",
    "İletilecek kişi/oda seçin:":
        "Select recipient:",
    # ── ui/dialogs/chat_options.py ──
    "Kaybolan Mesajlar":
        "Disappearing Messages",
    "Mesajlar belirli süre sonra\notomatik silinir.":
        "Messages are deleted automatically\nafter a set time.",
    "30sn":
        "30s",
    "5dk":
        "5m",
    "1sa":
        "1h",
    "1gün":
        "1d",
    "Uygula":
        "Apply",
    "Geçmişi Sil":
        "Delete History",
    "🗑 Mesaj Geçmişini Sil":
        "🗑 Delete Message History",
    "Toplam: {} mesaj, {} sohbet":
        "Total: {} messages, {} chats",
    "Silindi":
        "Deleted",
    "Bu sohbetin geçmişi silindi":
        "This chat's history was deleted",
    "Tüm Geçmişi Sil":
        "Delete All History",
    "Tüm sohbet geçmişi silinecek. Emin misiniz?":
        "All chat history will be deleted. Are you sure?",
    "🗑 Bu Sohbeti Sil":
        "🗑 Delete This Chat",
    "⚠ Tüm Geçmişi Sil":
        "⚠ Delete All History",
    # ── ui/dialogs/contact.py ──
    "Kişi Grupları":
        "Contact Groups",
    "🏷 Kişi Grupları":
        "🏷 Contact Groups",
    "Henüz grup yok":
        "No groups yet",
    "Grup Ekle":
        "Add Group",
    "Grup adı:":
        "Group name:",
    "Bilgi":
        "Info",
    "Önce bir grup oluşturun":
        "Create a group first",
    "Gruba Ekle":
        "Add to Group",
    "Grup:":
        "Group:",
    "Ekle":
        "Add",
    "+ Yeni Grup":
        "+ New Group",
    "+ Kişi Ekle":
        "+ Add Contact",
    "Yeni Sohbet":
        "New Chat",
    "  JID Gir  ":
        "  Enter JID  ",
    "Bir XMPP adresi girerek doğrudan sohbet\nbaşlatabilir veya abonelik isteği gönderebilirsiniz.":
        "Enter an XMPP address to start a chat\ndirectly or send a subscription request.",
    "JID (XMPP Adresi)":
        "JID (XMPP Address)",
    "  Sohbet Başlat  ":
        "  Start Chat  ",
    "  Kişi Olarak Ekle  ":
        "  Add as Contact  ",
    "  Kişiler  ":
        "  Contacts  ",
    "Mevcut kişilerinizden birini seçerek\nsohbet başlatabilirsiniz.":
        "Pick one of your existing contacts\nto start a chat.",
    "Filtrele...":
        "Filter...",
    "  Kullanıcı Ara  ":
        "  Search Users  ",
    "Sunucuda kullanıcı arayın (XEP-0055).\nTüm sunucular bu özelliği desteklemeyebilir.":
        "Search for users on the server (XEP-0055).\nNot every server supports this.",
    "Sunucu:":
        "Server:",
    "Arama:":
        "Search:",
    "İsim veya JID...":
        "Name or JID...",
    "  Aranıyor…":
        "  Searching…",
    "  Ara  ":
        "  Search  ",
    "🔍  Kullanıcı Ara":
        "🔍  Search Users",
    "Sunucuda kullanıcı arayın (XEP-0055)":
        "Search for users on the server (XEP-0055)",
    "Ara":
        "Search",
    "Sohbet Başlat":
        "Start Chat",
    # ── ui/dialogs/presence.py ──
    "Durum Mesajı":
        "Status Message",
    "Durum yazın...":
        "Type a status...",
    "Konum Paylaş":
        "Share Location",
    "Açıklama:":
        "Description:",
    "İstanbul":
        "Istanbul",
    "Geçersiz koordinatlar":
        "Invalid coordinates",
    "Paylaş":
        "Share",
    "Durdur":
        "Stop",
    # ── ui/dialogs/rooms.py ──
    "Davet Gönder":
        "Send Invitation",
    "{} odasına davet edilecek JID:":
        "JID to invite to {}:",
    "Ortak Gruplar":
        "Groups in Common",
    "🏠 {} ile Ortak Gruplar":
        "🏠 Groups in Common with {}",
    "  Ortak grup bulunamadı":
        "  No groups in common",
    "Bir konferans sunucusu keşfedin veya doğrudan katılın":
        "Discover a conference server or join directly",
    "🌐  KONFERANS SUNUCUSU":
        "🌐  CONFERENCE SERVER",
    "Odaları Keşfet":
        "Discover Rooms",
    "🚪  ODA JID (doğrudan katıl)":
        "🚪  ROOM JID (join directly)",
    "👤  TAKMA AD":
        "👤  NICKNAME",
    "Katıl":
        "Join",
    "Yeni bir sohbet odası oluşturun":
        "Create a new chat room",
    "🏠  ODA ADI":
        "🏠  ROOM NAME",
    "Adres: …@{}":
        "Address: …@{}",
    "Adres: {}":
        "Address: {}",
    "🛡  ODA TÜRÜ":
        "🛡  ROOM TYPE",
    "🌐  Normal oda":
        "🌐  Normal room",
    "Adresi bilen herkes katılabilir, mesajlar şifresizdir.":
        "Anyone who knows the address can join; messages are not encrypted.",
    "🔒  Şifreli oda (OMEMO)":
        "🔒  Encrypted room (OMEMO)",
    "Yalnız davet ettikleriniz katılır, mesajlar uçtan uca şifrelenir.":
        "Only people you invite can join; messages are end-to-end encrypted.",
    "OMEMO kütüphanesi (slixmpp-omemo) yüklü değil.":
        "The OMEMO library (slixmpp-omemo) is not installed.",
    "Oluştur ve Katıl":
        "Create and Join",
    "📑  Yer İmleri":
        "📑  Bookmarks",
    "Mevcut Odayı Ekle":
        "Add Current Room",
    "🗑 Sil":
        "🗑 Delete",
    "Oda Ayarları — {}":
        "Room Settings — {}",
    "Oda Yönetimi — {}":
        "Room Management — {}",
    "  Üyeler  ":
        "  Members  ",
    "  Ayarlar  ":
        "  Settings  ",
    "Oda Konusu:":
        "Room Topic:",
    "Konuyu Güncelle":
        "Update Topic",
    "  Davet  ":
        "  Invite  ",
    "Davet edilecek JID:":
        "JID to invite:",
    "{} davet edildi":
        "{} invited",
    "📨 Davet Gönder":
        "📨 Send Invitation",
    "İsim A→Z":
        "Name A→Z",
    "İsim Z→A":
        "Name Z→A",
    "Adres A→Z":
        "Address A→Z",
    "Adres Z→A":
        "Address Z→A",
    "Keşfedilen Odalar":
        "Discovered Rooms",
    "Oda ara (isim veya adres)...":
        "Search rooms (name or address)...",
    "  (Eşleşen oda bulunamadı)":
        "  (No matching rooms found)",
    "{}/{} oda":
        "{}/{} rooms",
    "Seçilen Odaya Katıl":
        "Join Selected Room",
    "  Genel Ara  ":
        "  Public Search  ",
    "Oda adı veya konu ara...":
        "Search room name or topic...",
    "Aranıyor…":
        "Searching…",
    "  (Sonuç bulunamadı)":
        "  (No results found)",
    "Yer imine eklendi":
        "Added to bookmarks",
    "Yer İmine Ekle":
        "Add Bookmark",
    "  Popüler Sunucular  ":
        "  Popular Servers  ",
    "Bir sunucu seçip 'Keşfet' ile odaları listeleyin.":
        "Pick a server and use 'Discover' to list its rooms.",
    "Seçili Sunucudan Keşfet":
        "Discover from Selected Server",
    "Sunucu adresi":
        "Server address",
    "  Keşfet  ":
        "  Discover  ",
    # ── ui/dialogs/settings.py ──
    "  Hesap  ":
        "  Account  ",
    "PROFİL":
        "PROFILE",
    "Sunucu: {}":
        "Server: {}",
    "Profil Fotoğrafı Seç":
        "Choose Profile Photo",
    "*.png *.jpg *.jpeg *.gif *.webp *.bmp":
        "*.png *.jpg *.jpeg *.gif *.webp *.bmp",
    "Tüm":
        "All",
    "Fotoğraf yüklenemedi: {}":
        "Photo could not be loaded: {}",
    "Fotoğraf Değiştir":
        "Change Photo",
    "Kaldır":
        "Remove",
    "DURUM MESAJI":
        "STATUS MESSAGE",
    "GİRİŞ":
        "LOGIN",
    "Açılışta otomatik giriş (formu atla)":
        "Log in automatically at startup (skip the form)",
    "ÇOKLU HESAP":
        "MULTIPLE ACCOUNTS",
    "⇄ Geçiş":
        "⇄ Switch",
    "Ek hesap yok":
        "No other accounts",
    "Hesap Ekle":
        "Add Account",
    "Şifre:":
        "Password:",
    "+ Hesap Ekle":
        "+ Add Account",
    "  Görünüm  ":
        "  Appearance  ",
    "TEMA":
        "THEME",
    "YAZI TİPİ":
        "FONT",
    "Yazı tipi:":
        "Font:",
    "Boyut:":
        "Size:",
    "ÖNİZLEME":
        "PREVIEW",
    "Merhaba! Bu bir önizleme mesajıdır. 🎉":
        "Hello! This is a preview message. 🎉",
    "DİL":
        "LANGUAGE",
    "DÜZEN":
        "LAYOUT",
    "📐 Kompakt mod (mesaj balonları daha sıkışık)":
        "📐 Compact mode (tighter message bubbles)",
    "SOHBET ARKA PLANI":
        "CHAT BACKGROUND",
    "(varsayılan)":
        "(default)",
    "Mevcut: {}":
        "Current: {}",
    "🖼 Arka Plan Değiştir…":
        "🖼 Change Background…",
    "  Bildirimler  ":
        "  Notifications  ",
    "BİLDİRİMLER":
        "NOTIFICATIONS",
    "Masaüstü bildirimleri göster":
        "Show desktop notifications",
    "Bildirim sesleri çal":
        "Play notification sounds",
    "🔊 Sesi Test Et":
        "🔊 Test Sound",
    "SİSTEM TEPSİSİ":
        "SYSTEM TRAY",
    "⚫ pystray yüklü değil":
        "⚫ pystray is not installed",
    "Tepsi ikonu: {}":
        "Tray icon: {}",
    "Yüklemek için: pip install pystray":
        "To install: pip install pystray",
    "GİZLİLİK":
        "PRIVACY",
    "Okundu bilgisi gönder (XEP-0333)":
        "Send read receipts (XEP-0333)",
    "Yazıyor bildirimi gönder (XEP-0085)":
        "Send typing notifications (XEP-0085)",
    "KAYBOLAN MESAJLAR":
        "DISAPPEARING MESSAGES",
    "Varsayılan süre (tüm yeni sohbetler için):":
        "Default duration (for all new chats):",
    "30 sn":
        "30 s",
    "5 dk":
        "5 min",
    "1 gün":
        "1 day",
    "ENGELLİ KİŞİLER":
        "BLOCKED CONTACTS",
    "🚫 Engelli kişileri yönet...":
        "🚫 Manage blocked contacts...",
    "İndirme klasörü":
        "Download folder",
    "Gelen dosyaları otomatik kabul et":
        "Automatically accept incoming files",
    "IBB blok boyutu":
        "IBB block size",
    "Büyük dosya uyarı eşiği (MB)":
        "Large file warning threshold (MB)",
    "  Şifreleme  ":
        "  Encryption  ",
    "OMEMO (XEP-0384)":
        "OMEMO (XEP-0384)",
    "Hazır":
        "Ready",
    "Yüklü değil":
        "Not installed",
    "Başlatılmadı":
        "Not started",
    "Cihaz bilgileri yükleniyor…":
        "Loading device information…",
    "Bu Cihaz  (ID: {})":
        "This Device  (ID: {})",
    "Diğer Cihazlar ({})":
        "Other Devices ({})",
    "Başka cihaz bulunamadı":
        "No other devices found",
    "OpenPGP (XEP-0027)":
        "OpenPGP (XEP-0027)",
    "GPG bulunamadı":
        "GPG not found",
    "🔑 OpenPGP":
        "🔑 OpenPGP",
    "Anahtar: {} adet":
        "Keys: {}",
    "PGP ANAHTAR EŞLEŞTİRME":
        "PGP KEY MAPPING",
    "JID → GPG Key ID eşleştirmesi":
        "JID → GPG Key ID mapping",
    "Key ID":
        "Key ID",
    "+ Eşleştirme Ekle":
        "+ Add Mapping",
    "OMEMO QR DOĞRULAMA":
        "OMEMO QR VERIFICATION",
    "🔐 QR Kod ile Parmak İzi Doğrula…":
        "🔐 Verify Fingerprint with QR Code…",
    "🟢 qrcode kütüphanesi yüklü":
        "🟢 qrcode library installed",
    "⚫ QR için: pip install qrcode[pil]":
        "⚫ For QR: pip install qrcode[pil]",
    "VARSAYILAN ŞİFRELEME":
        "DEFAULT ENCRYPTION",
    "🔓 Kapalı":
        "🔓 Off",
    "  Bağlantı  ":
        "  Connection  ",
    "BAĞLANTI AYARLARI":
        "CONNECTION SETTINGS",
    "Odalara otomatik yeniden katıl":
        "Rejoin rooms automatically",
    "OTOMATİK UZAKTA":
        "AUTO AWAY",
    "İşlem yapılmadığında otomatik uzakta durumuna geç:":
        "Switch to away automatically when idle:",
    "3 dk":
        "3 min",
    "BAĞLANTI KALİTESİ":
        "CONNECTION QUALITY",
    "📶 Bağlantı yok":
        "📶 No connection",
    "📶 Henüz ölçülmedi":
        "📶 Not measured yet",
    "KAYITLI ODALAR":
        "SAVED ROOMS",
    "Kayıtlı oda yok":
        "No saved rooms",
    "BAĞLANTI DURUMU":
        "CONNECTION STATUS",
    "Bağlı":
        "Connected",
    "Bağlı değil":
        "Not connected",
    "Hesap: {}":
        "Account: {}",
    "Kişiler: {}  •  Aktif Odalar: {}":
        "Contacts: {}  •  Active Rooms: {}",
    "PROXY / ANONİM BAĞLANTI":
        "PROXY / ANONYMOUS CONNECTION",
    "Yapılandırılmamış":
        "Not configured",
    "Tür: {}":
        "Type: {}",
    "🔧 Proxy Ayarları…":
        "🔧 Proxy Settings…",
    "OTOMATİK TEMA GEÇİŞİ":
        "AUTOMATIC THEME SWITCHING",
    "⚫ Kapalı":
        "⚫ Off",
    "🌓 Otomatik Tema Ayarları…":
        "🌓 Automatic Theme Settings…",
    "GÜVENLİK":
        "SECURITY",
    "🔑 Uygulama Kilidi (PIN)…":
        "🔑 App Lock (PIN)…",
    "🗑 Mesaj Geçmişini Sil…":
        "🗑 Delete Message History…",
    "  Hakkında  ":
        "  About  ",
    "deneme.py — Modern Tkinter XMPP İstemcisi":
        "deneme.py — Modern Tkinter XMPP Client",
    "KÜTÜPHANELER":
        "LIBRARIES",
    "VERİ":
        "DATA",
    "📤 Sohbetleri Dışa Aktar":
        "📤 Export Chats",
    "📋 Ayarları Kopyala":
        "📋 Copy Settings",
    "✓ Kopyalandı":
        "✓ Copied",
    "💾 Yedekleme / Geri Yükleme…":
        "💾 Backup / Restore…",
    "KLAVYE KISAYOLLARI":
        "KEYBOARD SHORTCUTS",
    "⌨ Kısayolları Göster…":
        "⌨ Show Shortcuts…",
    "Hızlı Geçiş":
        "Quick Switch",
    "Ctrl+F":
        "Ctrl+F",
    "Sohbette Ara":
        "Search in Chat",
    "Ctrl+K":
        "Ctrl+K",
    "Ctrl+N":
        "Ctrl+N",
    "Ctrl+B":
        "Ctrl+B",
    "Yedekleme":
        "Backup",
    "  Kaydet ve Kapat  ":
        "  Save and Close  ",
    # ── ui/dialogs/simple.py ──
    "Klavye Kısayolları":
        "Keyboard Shortcuts",
    "Hızlı Geçiş (kişi/oda)":
        "Quick Switch (contact/room)",
    "Ctrl+R":
        "Ctrl+R",
    "Son mesaja yanıtla":
        "Reply to the last message",
    "Ctrl+Shift+E":
        "Ctrl+Shift+E",
    "Son mesajımı düzenle":
        "Edit my last message",
    "Ctrl+Shift+D":
        "Ctrl+Shift+D",
    "Son mesajımı sil":
        "Delete my last message",
    "Ctrl+Shift+M":
        "Ctrl+Shift+M",
    "✨ Neler kaçırdım? (AI özeti)":
        "✨ What did I miss? (AI summary)",
    "Ctrl+Shift+H":
        "Ctrl+Shift+H",
    "✨ Geçmişe sor (AI)":
        "✨ Ask history (AI)",
    "Ctrl+Shift+S":
        "Ctrl+Shift+S",
    "✨ Sesle yaz (dikte)":
        "✨ Voice typing (dictation)",
    "Üzerine gel":
        "Hover",
    "Eylem butonları (yanıtla/tepki/… )":
        "Action buttons (reply/react/… )",
    "Çift tık":
        "Double-click",
    "Mesajı yanıtla (alıntı)":
        "Reply to message (quote)",
    "Tepkiye tıkla":
        "Click a reaction",
    "Tepkini ekle / kaldır":
        "Add / remove your reaction",
    "Ctrl+,":
        "Ctrl+,",
    "Ctrl+?":
        "Ctrl+?",
    "Bu menü":
        "This menu",
    "Escape":
        "Escape",
    "Aramayı kapat":
        "Close search",
    "Enter":
        "Enter",
    "Mesaj gönder":
        "Send message",
    "Ctrl+V":
        "Ctrl+V",
    "Yapıştır (resim/metin)":
        "Paste (image/text)",
    "Tepkiler":
        "Reactions",
    "😊 Tepkiler":
        "😊 Reactions",
    "(tepki yok)":
        "(no reactions)",
    # ── ui/profile.py ──
    "📖 Hikaye / Durum Paylaş":
        "📖 Share Story / Status",
    "METİN DURUMU":
        "TEXT STATUS",
    "RUHSAL DURUM":
        "MOOD",
    "😊 Mutlu":
        "😊 Happy",
    "😔 Üzgün":
        "😔 Sad",
    "😡 Kızgın":
        "😡 Angry",
    "😴 Uykulu":
        "😴 Sleepy",
    "🤔 Düşünceli":
        "🤔 Thoughtful",
    "🎉 Heyecanlı":
        "🎉 Excited",
    "FOTOĞRAF":
        "PHOTO",
    "Seçilmedi":
        "None selected",
    "*.png *.jpg *.jpeg":
        "*.png *.jpg *.jpeg",
    "📷 Fotoğraf Seç":
        "📷 Choose Photo",
    "📤 Yayınla":
        "📤 Publish",
    "Profil Fotoğrafı":
        "Profile Photo",
    "Fotoğrafınızı değiştirin veya kaldırın":
        "Change or remove your photo",
    "✓ Güncellendi":
        "✓ Updated",
    "⚠ Yayınlanamadı — eski fotoğraf korundu":
        "⚠ Could not publish — the old photo was kept",
    "Pillow Gerekli":
        "Pillow Required",
    "Fotoğraf desteği için Pillow gerekli:\npip install Pillow":
        "Photo support requires Pillow:\npip install Pillow",
    "Fotoğraf Seç":
        "Choose Photo",
    "Resim Dosyaları":
        "Image Files",
    "Tüm Dosyalar":
        "All Files",
    "✓ Kaldırıldı":
        "✓ Removed",
    "📷  Fotoğraf Seç":
        "📷  Choose Photo",
    # ── ui/rooms.py ──
    "  📝 Konu Değiştir":
        "  📝 Change Topic",
    "  📨 Davet Gönder":
        "  📨 Send Invitation",
    "  ⚙ Oda Ayarları":
        "  ⚙ Room Settings",
    "  🚪 Odayı Terk Et":
        "  🚪 Leave Room",
    "  💣 Odayı Sil":
        "  💣 Delete Room",
    "  Yetki: {}":
        "  Affiliation: {}",
    "  Rol: {}":
        "  Role: {}",
    "  💬 Özel Mesaj":
        "  💬 Private Message",
    "  👢 At (Kick)":
        "  👢 Kick",
    "  🔇 Sustur":
        "  🔇 Mute",
    "  🔊 Konuşmaya İzin Ver":
        "  🔊 Allow to Speak",
    "  ⚔ Moderatör Yap":
        "  ⚔ Make Moderator",
    "  ⚔ Moderatörlüğü Al":
        "  ⚔ Revoke Moderator",
    "  🚫 Yasakla (Ban)":
        "  🚫 Ban",
    "  🛡 Yönetici Yap":
        "  🛡 Make Admin",
    "  👤 Üye Yap":
        "  👤 Make Member",
    "  ↓ Yetkiyi Kaldır":
        "  ↓ Remove Affiliation",
    # ── ui/sidebar.py ──
    "⚡ {} (Ctrl+K)":
        "⚡ {} (Ctrl+K)",
    "↑/↓ seç · Enter aç · Esc kapat":
        "↑/↓ select · Enter open · Esc close",
    "Eşleşen sohbet bulunamadı":
        "No matching chats",
    "  Sohbet Başlat":
        "  Start Chat",
    "📌 Sabitlemeyi Kaldır":
        "📌 Unpin",
    "📌 Sohbeti Sabitle":
        "📌 Pin Chat",
    "🏠 Ortak Gruplar":
        "🏠 Groups in Common",
    "  Kişiyi Kaldır":
        "  Remove Contact",
    "KATILIMCILAR — {}":
        "PARTICIPANTS — {}",
    "Çevrimdışı":
        "Offline",
    "Ortak grup: {}":
        "Groups in common: {}",
    # ── xmpp.py ──
    "özel":
        "private",
    "⚠ Değişiklikler kaybolacak — kapatmak için yine dışarı tıkla":
        "⚠ Changes will be lost — click outside again to close",
    "KİŞİLER":
        "CONTACTS",
    "Kullanıcı Ara":
        "Search Users",
    "ODALAR":
        "ROOMS",
    "GELİŞMİŞ":
        "ADVANCED",
    "Sticker/GIF":
        "Sticker/GIF",
    "Mesaj Ara":
        "Search Messages",
    "Log":
        "Log",
    "REST API":
        "REST API",
    "Yeniden Bağlan":
        "Reconnect",
    "Ayarlar":
        "Settings",
    "⏱ Kaybolan Mesajlar":
        "⏱ Disappearing Messages",
    "📜 Daha Eski Mesajları Yükle (MAM)":
        "📜 Load Older Messages (MAM)",
    "⏰ Mesaj Zamanla":
        "⏰ Schedule Message",
    "📤 Sohbeti Dışa Aktar":
        "📤 Export Chat",
    "🗑 Geçmişi Sil":
        "🗑 Delete History",
    "🔧 Oda Yönetimi":
        "🔧 Room Management",
    "👤 Profil":
        "👤 Profile",
    "🔎 Mesaj Ara":
        "🔎 Search Messages",
    "📌 Sabitlenmiş Mesajlar":
        "📌 Pinned Messages",
    "💬 Sohbet":
        "💬 Chat",
    "📤 Paylaşım":
        "📤 Sharing",
    "📍 Konum Paylaş":
        "📍 Share Location",
    "📖 Hikaye Paylaş":
        "📖 Share Story",
    "📢 Toplu Mesaj":
        "📢 Broadcast Message",
    "🔒 Güvenlik":
        "🔒 Security",
    "🔒 OMEMO Parmak İzleri":
        "🔒 OMEMO Fingerprints",
    "🔐 OMEMO QR Doğrulama":
        "🔐 OMEMO QR Verification",
    "🚫 Engelli Kişiler":
        "🚫 Blocked Contacts",
    "🪟 Görünüm":
        "🪟 View",
    "📺 Yeni Sekmede Aç":
        "📺 Open in New Tab",
    "📺 Bölünmüş Ekran":
        "📺 Split Screen",
    "🖼 Arka Plan Değiştir":
        "🖼 Change Background",
    "📐 Rahat Moda Geç":
        "📐 Switch to Comfortable Mode",
    "📐 Kompakt Moda Geç":
        "📐 Switch to Compact Mode",
    "⚙ Diğer":
        "⚙ More",
    "💬 Durum Mesajı":
        "💬 Status Message",
    "💾 Yedekleme / Geri Yükleme":
        "💾 Backup / Restore",
    "⌨ Klavye Kısayolları":
        "⌨ Keyboard Shortcuts",
    "Yüzler":
        "Faces",
    "El":
        "Hands",
    "Kalp":
        "Hearts",
    "Nesne":
        "Objects",
    "Yiyecek":
        "Food",
    "Doğa":
        "Nature",
    "Bugün":
        "Today",
    "⚠ OMEMO plugin kaydı başarısız: {}":
        "⚠ OMEMO plugin registration failed: {}",
    "⚠ OMEMO başlatma zaman aşımına uğradı. Sunucu PEP/PubSub desteklemeyebilir.":
        "⚠ OMEMO startup timed out. The server may not support PEP/PubSub.",
    "⚠ OMEMO başlatma hatası: {}":
        "⚠ OMEMO startup error: {}",
    "🔐 OMEMO şifreleme hazır":
        "🔐 OMEMO encryption ready",
    "⚠ OMEMO çözme hatası: {}":
        "⚠ OMEMO decryption error: {}",
    "⚠ PGP mesajı çözülemedi (anahtar eksik?)":
        "⚠ PGP message could not be decrypted (missing key?)",
    "⚠ PGP çözme hatası: {}":
        "⚠ PGP decryption error: {}",
    "🔑 PGP anahtar ayarlandı (config)":
        "🔑 PGP key set (config)",
    "🔑 PGP anahtar otomatik eşleştirildi: {}":
        "🔑 PGP key matched automatically: {}",
    "🔑 PGP: tek secret key kullanılıyor: {}":
        "🔑 PGP: using the only secret key: {}",
    "Sunucuya bağlandı, oturum açılıyor…":
        "Connected to the server, logging in…",
    "Giriş başarısız: JID veya şifre yanlış.":
        "Login failed: wrong JID or password.",
    "⟳ {}s sonra yeniden bağlanılıyor…":
        "⟳ Reconnecting in {}s…",
    "PGP: {} için GPG anahtarı bulunamadı. Ayarlar → Şifreleme'den anahtar eşleştirin.":
        "PGP: no GPG key found for {}. Map a key in Settings → Encryption.",
    "PGP şifreleme başarısız: {}":
        "PGP encryption failed: {}",
    "PGP: Şifreli veri çıkarılamadı":
        "PGP: encrypted data could not be extracted",
    "PGP gönderme hatası: {}":
        "PGP send error: {}",
    "OMEMO: Oda üyelerinin JID'leri alınamadı (oda anonim olabilir). Şifreli dosya bağlantısı şifresiz GÖNDERİLMEDİ.":
        "OMEMO: could not get the room members' JIDs (the room may be anonymous). The encrypted file link was NOT sent unencrypted.",
    "OMEMO: Oda üyelerinin JID'leri alınamadı (oda anonim olabilir). Düz metin gönderiliyor.":
        "OMEMO: could not get the room members' JIDs (the room may be anonymous). Sending plain text.",
    "OMEMO: Alıcının cihaz bilgileri alınamadı.\nKarşı tarafın OMEMO destekli bir istemci kullanması gerekiyor.\nDetay: {}":
        "OMEMO: could not get the recipient's device information.\nThe other side needs a client with OMEMO support.\nDetails: {}",
    "OMEMO şifreleme hatası: {}":
        "OMEMO encryption error: {}",
    "⚠ OMEMO uyarı: {}":
        "⚠ OMEMO warning: {}",
    "OMEMO şifreleme başarısız — şifreli dosya bağlantısı şifresiz GÖNDERİLMEDİ.":
        "OMEMO encryption failed — the encrypted file link was NOT sent unencrypted.",
    "OMEMO şifreleme başarısız — düz metin gönderiliyor":
        "OMEMO encryption failed — sending plain text",
    "✓ Profil fotoğrafı güncellendi":
        "✓ Profile photo updated",
    "⚠ Avatar yayınlanamadı: {}":
        "⚠ Avatar could not be published: {}",
    "İstek gönderildi → {}":
        "Request sent → {}",
    "Kişi eklenemedi: {}":
        "Contact could not be added: {}",
    "✓ Kişi kaldırıldı: {}":
        "✓ Contact removed: {}",
    "Kişi kaldırılamadı: {}":
        "Contact could not be removed: {}",
    "Engelleme hatası: {}":
        "Blocking error: {}",
    "✓ {} engeli kaldırıldı":
        "✓ {} unblocked",
    "Engel kaldırma hatası: {}":
        "Unblocking error: {}",
    "Engel listesi hatası: {}":
        "Block list error: {}",
    "📍 Konum paylaşıldı":
        "📍 Location shared",
    "Konum paylaşma hatası: {}":
        "Location sharing error: {}",
    "Ruh hâli paylaşılamadı: {}":
        "Mood could not be shared: {}",
    "📍 Konum paylaşımı durduruldu":
        "📍 Location sharing stopped",
    "Konum durdurma hatası: {}":
        "Error stopping location: {}",
    "XMPP Giriş":
        "XMPP Login",
    "XMPP Connect":
        "XMPP Connect",
    "Hesabınıza giriş yapın":
        "Log in to your account",
    "JID":
        "JID",
    "Şifre":
        "Password",
    "Gelişmiş":
        "Advanced",
    "Otomatik giriş":
        "Automatic login",
    "Şifremi hatırla":
        "Remember my password",
    "Sunucu (boş = SRV)":
        "Server (empty = SRV)",
    "Port":
        "Port",
    "SRV otomatik  •  OMEMO & PGP destekli":
        "SRV automatic  •  OMEMO & PGP supported",
    "Bağlan":
        "Connect",
    "Eksik Bilgi":
        "Missing Information",
    "JID ve şifre gerekli.":
        "JID and password are required.",
    "Geçersiz JID":
        "Invalid JID",
    "JID formatı: kullanıcı@sunucu.tld":
        "JID format: user@server.tld",
    "XMPP — {}":
        "XMPP — {}",
    "Kişi veya oda ara...":
        "Search contacts or rooms...",
    "Kişi Ekle":
        "Add Contact",
    "Gruplar":
        "Groups",
    "Komut ver ya da soru sor · Ctrl+Shift+K":
        "Give a command or ask a question · Ctrl+Shift+K",
    "Oda Keşfet":
        "Discover Rooms",
    "Yer İmleri":
        "Bookmarks",
    "Odaya Katıl":
        "Join Room",
    "Ana Menü":
        "Main Menu",
    "＋  Yeni Sohbet":
        "＋  New Chat",
    "✓ Bağlantı":
        "✓ Connection",
    "Zaten bağlısınız":
        "You are already connected",
    "Bağlantı":
        "Connection",
    "Deneme başlatılamadı: {}":
        "Could not start an attempt: {}",
    "⟳ Yeniden bağlanılıyor…":
        "⟳ Reconnecting…",
    "Bağlanıyor…":
        "Connecting…",
    "KATILIMCILAR":
        "PARTICIPANTS",
    "🔒 Şifreli dosya (OMEMO)":
        "🔒 Encrypted file (OMEMO)",
    "⬇ İndir ve aç":
        "⬇ Download and open",
    "📂 Klasörde göster":
        "📂 Show in folder",
    "Alıntılanan mesaja git":
        "Go to quoted message",
    "Yanıtla":
        "Reply",
    "Tepki ekle":
        "Add reaction",
    "Tepkileri gör":
        "View reactions",
    "AI: çevir / yazıya dök / açıkla":
        "AI: translate / transcribe / describe",
    "Kopyala":
        "Copy",
    "İlet":
        "Forward",
    "Sabitle":
        "Pin",
    "Düzenle":
        "Edit",
    "Sil":
        "Delete",
    "⚠ Şifreli dosya açılamadı":
        "⚠ Encrypted file could not be opened",
    "📥 Şifreli dosya":
        "📥 Encrypted file",
    "Aç":
        "Open",
    "Klasörü Aç":
        "Open Folder",
    "🔗 {n} görsel bağlantısı daha":
        "🔗 {n} more image links",
    "🎤 {n} ses bağlantısı daha":
        "🎤 {n} more audio links",
    "Görsel bağlantıları":
        "Image links",
    "Ses bağlantıları":
        "Audio links",
    "{} — {} bağlantı":
        "{} — {} links",
    "Sayfa {}/{}":
        "Page {}/{}",
    "◀ Önceki":
        "◀ Previous",
    "Sonraki ▶":
        "Next ▶",
    "🔗 Tarayıcıda Aç":
        "🔗 Open in Browser",
    "↪ Alıntılanan mesaj uygulamada bulunamadı":
        "↪ The quoted message was not found in the app",
    "Mesajı Düzenle":
        "Edit Message",
    "Yeni metin:":
        "New text:",
    "Mesajı Sil":
        "Delete Message",
    "Bu mesajı silmek istediğinizden emin misiniz?":
        "Are you sure you want to delete this message?",
    "↩ Bu mesaj yanıtlanamıyor (kimlik yok)":
        "↩ This message can't be replied to (no ID)",
    "Bu mesaj şifreli içerik taşıyor ama seçtiğiniz sohbet şifresiz: içerik (şifreli dosyanın anahtarı dahil) sunucuya açık metin gider. Yine de iletilsin mi?":
        "This message carries encrypted content, but the chosen chat is unencrypted: the content (including the key of an encrypted file) reaches the server in plain text. Forward anyway?",
    "Sabitlenmiş Mesajlar":
        "Pinned Messages",
    "Şifreli Sohbet":
        "Encrypted Chat",
    "{}\n\nYalnız bu istek için içerik Claude'a (bulut) gönderilsin mi?\nHayır derseniz hiçbir şey gönderilmez.":
        "{}\n\nSend the content to Claude (cloud) for this request only?\nIf you say No, nothing is sent.",
    "{}\n\nAI Ayarları açılsın mı?":
        "{}\n\nOpen AI Settings?",
    "Beklenmeyen hata: {}":
        "Unexpected error: {}",
    "{}\n\n{} kaynağın {} tanesi şifreli.\n\nEvet: şifreli içerik de yalnız bu istek için Claude'a (bulut) gönderilsin.\nHayır: şifreli içerik çıkarılsın, yalnız kalanı gönderilsin.\nİptal: hiçbir şey gönderilmesin.":
        "{}\n\n{} of {} sources are encrypted.\n\nYes: send the encrypted content to Claude (cloud) too, for this request only.\nNo: leave the encrypted content out and send only the rest.\nCancel: send nothing.",
    "✨ Asistan…":
        "✨ Assistant…",
    "📬 Okunmamışları özetle ({})":
        "📬 Summarize unread ({})",
    "📝 Sohbeti özetle":
        "📝 Summarize chat",
    "📅 Görev ve etkinlikleri çıkar":
        "📅 Extract tasks and events",
    "💬 Bu sohbet":
        "💬 This chat",
    "❓ Yanıt bekleyen sorular":
        "❓ Unanswered questions",
    "✍ Yanıt taslakları":
        "✍ Reply drafts",
    "🔎 Geçmişe sor…":
        "🔎 Ask history…",
    "🧠 Anlamsal arama…":
        "🧠 Semantic search…",
    "🗂 Tüm sohbetler":
        "🗂 All chats",
    "⚙ AI Ayarları…":
        "⚙ AI Settings…",
    "💡 Yanıt öner":
        "💡 Suggest a reply",
    "✨ Asistan (bu sohbet)…":
        "✨ Assistant (this chat)…",
    "⏹ Dikteyi bitir":
        "⏹ Stop dictation",
    "🎙 Sesle yaz (dikte)":
        "🎙 Voice typing (dictation)",
    "⏹ Sesli okumayı durdur":
        "⏹ Stop reading aloud",
    "✍ Taslağı düzenle":
        "✍ Edit draft",
    "↶ AI değişikliğini geri al":
        "↶ Undo AI change",
    "🌐 Çeviri":
        "🌐 Translation",
    "Örn: Bu ifade ne anlama geliyor?":
        "E.g.: What does this expression mean?",
    "🎙 Ses kaydının metni":
        "🎙 Voice recording transcript",
    "🖥 Yerel (faster-whisper) · {}":
        "🖥 Local (faster-whisper) · {}",
    "Yazıya dökülüyor… (ilk kullanımda model indirilir)":
        "Transcribing… (the model is downloaded on first use)",
    "🎙 Otomatik ses→metin durdu":
        "🎙 Automatic speech-to-text stopped",
    "faster-whisper/model yok — AI Ayarları → Test Et":
        "faster-whisper/model missing — AI Settings → Test",
    "Görsel çok büyük.":
        "The image is too large.",
    "Görsele Soru Sor":
        "Ask About Image",
    "Görsel hakkında ne sormak istiyorsunuz?":
        "What do you want to ask about the image?",
    "🖼 Görsel açıklaması":
        "🖼 Image description",
    "Örn: Arka planda ne yazıyor?":
        "E.g.: What is written in the background?",
    "Özet":
        "Summary",
    "Özetlenecek mesaj yok.":
        "No messages to summarize.",
    "📝 {} — okunmamış {} mesajın özeti":
        "📝 {} — summary of {} unread messages",
    "📝 {} — sohbet özeti":
        "📝 {} — chat summary",
    "{} · son {} mesaj":
        "{} · last {} messages",
    "Örn: Benden ne isteniyor? Saat kaçta buluşuyoruz?":
        "E.g.: What am I being asked? What time are we meeting?",
    "Neler kaçırdım?":
        "What did I miss?",
    "Okunmamış mesaj yok — her şey okunmuş. 🎉":
        "No unread messages — everything has been read. 🎉",
    "Okunmamışlar arasında özetlenecek metin mesajı yok.":
        "There are no text messages to summarize among the unread ones.",
    "📥 Neler kaçırdım?":
        "📥 What did I miss?",
    "{} · {} sohbet, {} okunmamış mesaj":
        "{} · {} chats, {} unread messages",
    "Örn: Bana kim soru sordu?":
        "E.g.: Who asked me a question?",
    "Sohbete git":
        "Go to chat",
    "Ali'ye yarın 10'da toplantı olduğunu yaz":
        "Tell Ali we have a meeting tomorrow at 10",
    "Yarın 09:00'da faturayı ödemeyi hatırlat":
        "Remind me to pay the bill tomorrow at 09:00",
    "Geçmişe sor: Ali'nin verdiği adres neydi?":
        "Ask history: What address did Ali give?",
    "Ayşe ile sohbeti özetle":
        "Summarize the chat with Ayşe",
    "Durumumu meşgul yap":
        "Set my status to busy",
    "💬 Bağlam: {} — \"bu sohbet\" ya da ad yazmadan verilen komutlar bu sohbete":
        "💬 Context: {} — commands that say \"this chat\" or name no one go to this chat",
    "Açık sohbet yok — komutlarda kişi ya da oda adını yazın":
        "No open chat — name the contact or room in your commands",
    "{} · kişi listeniz modele gönderilmez; gönderme ve değişiklikler onayınızla yapılır":
        "{} · your contact list is not sent to the model; sending and changes need your approval",
    "Düşünüyor…":
        "Thinking…",
    "“{}” adında bir kişi ya da oda bulunamadı.":
        "No contact or room named “{}” was found.",
    "“{}” birden çok kişiyle eşleşti":
        "“{}” matched more than one contact",
    "✓ Onayla":
        "✓ Approve",
    "✗ İptal":
        "✗ Cancel",
    "✓ Seçildi":
        "✓ Selected",
    "✓ {} sohbeti açıldı.":
        "✓ Opened the chat with {}.",
    "✓ Taslak giriş kutusuna kondu — kontrol edip siz gönderin.":
        "✓ The draft is in the input box — check it and send it yourself.",
    "⚠ Oda adresi geçersiz.":
        "⚠ The room address is invalid.",
    "✓ {} odasına katılma isteği gönderildi.":
        "✓ Join request sent to {}.",
    "✓ Durum: {}":
        "✓ Status: {}",
    "✓ İlgili pencere açıldı.":
        "✓ The related window was opened.",
    "⚠ Bu eylem desteklenmiyor.":
        "⚠ This action is not supported.",
    "⚠ Sunucuya bağlı değilsiniz.":
        "⚠ You are not connected to the server.",
    "⚠ “/” ile başlayan metin komut sayılır; gönderilmedi.":
        "⚠ Text starting with “/” counts as a command; it was not sent.",
    "✓ {} kişisine gönderildi.":
        "✓ Sent to {}.",
    "Gönderilmedi (uyarıda vazgeçildi).":
        "Not sent (cancelled at the warning).",
    "Sohbette metin mesajı yok.":
        "There are no text messages in the chat.",
    "Model öneri üretemedi.":
        "The model could not produce suggestions.",
    "📝 Taslak alınamadı":
        "📝 Draft could not be made",
    "Taslak kutusu dolu — önce birkaçını kaldırın":
        "The draft box is full — remove a few first",
    "📝 Yeni yanıt taslağı":
        "📝 New reply draft",
    "{}: {} — Ctrl+Shift+R":
        "{}: {} — Ctrl+Shift+R",
    "📝 Uzaktayken gelenler":
        "📝 While you were away",
    "{} sohbet için yanıt taslağı — Ctrl+Shift+R":
        "Reply drafts for {} chats — Ctrl+Shift+R",
    "🌙 Uzaktayken":
        "🌙 While away",
    "🔊 Sesli okuma":
        "🔊 Read aloud",
    "🔊 Sesli okuma başarısız":
        "🔊 Reading aloud failed",
    "{} çalışmadı":
        "{} did not work",
    "⚠ Hassas bilgi":
        "⚠ Sensitive information",
    "Tespit bu bilgisayarda yapılır; hiçbir içerik dışarı gönderilmez.":
        "Detection runs on this computer; no content is sent anywhere.",
    "Taranıyor…":
        "Scanning…",
    "{} sohbette soru yanıt bekliyor — Ctrl+Shift+Q":
        "Questions are waiting for a reply in {} chats — Ctrl+Shift+Q",
    "Görevler ve Etkinlikler":
        "Tasks and Events",
    "Bu sohbette henüz mesaj yok.":
        "There are no messages in this chat yet.",
    "📅 {} — görevler ve etkinlikler":
        "📅 {} — tasks and events",
    "Sohbet inceleniyor…":
        "Reviewing the chat…",
    "Kaydedilecek öğe yok.":
        "Nothing to save.",
    "Takvim dosyasını kaydet":
        "Save calendar file",
    "Tüm dosyalar":
        "All files",
    "⚠ Dosya yazılamadı: {}":
        "⚠ File could not be written: {}",
    "✓ {} öğe kaydedildi: {} — takvim uygulamanızla açabilirsiniz.":
        "✓ {} items saved: {} — you can open it with your calendar app.",
    "Hatırlatıcı için seçili öğelerde ileri bir tarih ve saat olmalı.":
        "Selected items need a future date and time for a reminder.",
    "⏰ {} hatırlatıcı kuruldu.":
        "⏰ {} reminders set.",
    " {} öğede ileri tarih/saat olmadığı için kurulmadı.":
        " {} items were skipped because they have no future date/time.",
    "  — zamanı geçti":
        "  — time has passed",
    "⏰ Hatırlatıcı":
        "⏰ Reminder",
    "Yanıt Öner":
        "Suggest a Reply",
    "💡 Yanıt önerileri":
        "💡 Reply suggestions",
    "AI Asistanı":
        "AI Assistant",
    "Önce giriş kutusuna bir mesaj yazın.":
        "Type a message in the input box first.",
    "Sesle Yaz":
        "Voice Typing",
    "Mikrofon için PyAudio gerekli:\n  .venv-xmpp/bin/python -m pip install pyaudio":
        "The microphone needs PyAudio:\n  .venv-xmpp/bin/python -m pip install pyaudio",
    "Ses→metin için faster-whisper gerekli (yerel çalışır):\n  .venv-xmpp/bin/python -m pip install faster-whisper":
        "Speech-to-text needs faster-whisper (runs locally):\n  .venv-xmpp/bin/python -m pip install faster-whisper",
    "Uygulama kapanıyor.":
        "The app is closing.",
    "Konuşma algılanmadı.":
        "No speech detected.",
    "🎙 Dikte":
        "🎙 Dictation",
    "✍ Taslağa koy":
        "✍ Put in draft",
    "✓ Sohbet değiştiği için burada gösteriliyor":
        "✓ Shown here because the chat changed",
    "🖥 Yerel gömme · {} — mesajlar bilgisayardan çıkmaz":
        "🖥 Local embedding · {} — messages never leave your computer",
    "⏳ İndeksleme zaten sürüyor…":
        "⏳ Indexing is already running…",
    "⏳ Mesajlar indeksleniyor: {}/{} (arama şimdiden çalışır)":
        "⏳ Indexing messages: {}/{} (search already works)",
    "✓ {} yeni mesaj indekslendi.":
        "✓ {} new messages indexed.",
    "✓ İndeks güncel.":
        "✓ The index is up to date.",
    "⏳ İndeks kontrol ediliyor…":
        "⏳ Checking the index…",
    "İptal edildi.":
        "Cancelled.",
    "Gömmeler veritabanına yazılamadı.":
        "Embeddings could not be written to the database.",
    "⏳ Aranıyor…":
        "⏳ Searching…",
    "{} sonuç — açmak için çift tıklayın":
        "{} results — double-click to open",
    "Eşleşen mesaj bulunamadı.":
        "No matching messages found.",
    "🔎 Geçmişe sor":
        "🔎 Ask history",
    "{} · arama yerel ({})":
        "{} · local search ({})",
    "Örn: Ali'nin verdiği adres neydi?":
        "E.g.: What address did Ali give?",
    "Sorunuzu aşağıya yazın: ilgili mesajlar bu bilgisayarda bulunur, yanıt kaynaklarıyla gelir.":
        "Type your question below: related messages are found on this computer, and the answer comes with its sources.",
    "İlgili mesajlar aranıyor…":
        "Looking for related messages…",
    "Mesajlar indeksleniyor: {}/{}…":
        "Indexing messages: {}/{}…",
    "Bu soruyla ilgili bir mesaj bulunamadı. Farklı kelimelerle sormayı deneyin.":
        "No message related to this question was found. Try asking with different words.",
    "Eşleşme yok":
        "No matches",
    "Gönderilmedi.":
        "Not sent.",
    "İptal edildi — hiçbir şey gönderilmedi.":
        "Cancelled — nothing was sent.",
    "Eşleşen mesajlar gönderilebilecek metin içermiyor (yalnız medya ya da şifreli içerik).":
        "The matching messages contain no text that can be sent (only media or encrypted content).",
    "Kaynaklar":
        "Sources",
    "İlgili mesajlar":
        "Related messages",
    "Yanıt hazırlanıyor…":
        "Preparing the answer…",
    "AI kapalı — test edilecek sağlayıcı yok.":
        "AI is off — no provider to test.",
    "✓ Ollama çalışıyor; modeller hazır.":
        "✓ Ollama is running; the models are ready.",
    "✗ Ollama çalışıyor ama eksik model var: ":
        "✗ Ollama is running but models are missing: ",
    "✓ Claude erişilebilir ({}).":
        "✓ Claude is reachable ({}).",
    "✓ faster-whisper kurulu (ses→metin).":
        "✓ faster-whisper is installed (speech-to-text).",
    "✗ Ses→metin için: .venv-xmpp/bin/python -m pip install faster-whisper":
        "✗ For speech-to-text: .venv-xmpp/bin/python -m pip install faster-whisper",
    "✓ MCP erişimi açık; REST API çalışıyor (taslak bırakılabilir).":
        "✓ MCP access is on; the REST API is running (drafts can be left).",
    "ℹ MCP erişimi açık; taslak bırakmak için REST API'yi de açın.":
        "ℹ MCP access is on; turn on the REST API too to leave drafts.",
    "Engelli Kişiler":
        "Blocked Contacts",
    "Engelle":
        "Block",
    "JID:":
        "JID:",
    "Engeli Kaldır":
        "Unblock",
    "Yeni Engelle":
        "Block New",
    "Profil — {}":
        "Profile — {}",
    "vCard bilgileri yükleniyor…":
        "Loading vCard information…",
    "vCard bulunamadı":
        "vCard not found",
    "Ad":
        "Name",
    "Takma Ad":
        "Nickname",
    "E-posta":
        "Email",
    "Web":
        "Web",
    "Doğum":
        "Birthday",
    "vCard boş":
        "vCard is empty",
    "Mesaj Gönder":
        "Send Message",
    "OMEMO Parmak İzleri — {}":
        "OMEMO Fingerprints — {}",
    "OMEMO Parmak İzleri":
        "OMEMO Fingerprints",
    "Bilgi alınamadı":
        "Could not get information",
    "Hata: {}":
        "Error: {}",
    "Cihaz bulunamadı":
        "No device found",
    "Cihaz: {}  ({})":
        "Device: {}  ({})",
    "Dışa Aktar":
        "Export",
    "Sohbet geçmişi boş.":
        "The chat history is empty.",
    "Sohbet Dışa Aktar":
        "Export Chat",
    "Tümü":
        "All",
    "Okunmamış":
        "Unread",
    "Sabitlenmiş":
        "Pinned",
    "Metin":
        "Text",
    "Sohbet: {}\n":
        "Chat: {}\n",
    "Dışa aktarma: {}\n":
        "Export: {}\n",
    "Sohbet başarıyla dışa aktarıldı:\n{}":
        "Chat exported successfully:\n{}",
    "Hata":
        "Error",
    "Dışa aktarma hatası: {}":
        "Export error: {}",
    "Ses Mesajı":
        "Voice Message",
    "PyAudio yüklü değil.\npip install pyaudio":
        "PyAudio is not installed.\npip install pyaudio",
    "✕ İptal":
        "✕ Cancel",
    "✍ Yazıya dök":
        "✍ Transcribe",
    "▶ Gönder":
        "▶ Send",
    "Ses kaydı hatası: {}":
        "Recording error: {}",
    "Ses mesajı gönderilemedi: {}":
        "Voice message could not be sent: {}",
    "XMPP — {}{}":
        "XMPP — {}{}",
    "Kick":
        "Kick",
    "{} atılsın mı?\nSebep (opsiyonel):":
        "Kick {}?\nReason (optional):",
    "Ban":
        "Ban",
    "{} yasaklansın mı?\nSebep (opsiyonel):":
        "Ban {}?\nReason (optional):",
    "{} için JID girin:":
        "Enter a JID for {}:",
    "Yetki Değiştir":
        "Change Affiliation",
    "Kişiyi Kaldır":
        "Remove Contact",
    "{} kaldırılsın mı?":
        "Remove {}?",
    "Oda Konusu":
        "Room Topic",
    "Yeni konu:":
        "New topic:",
    "Davet":
        "Invite",
    "Odayı Sil":
        "Delete Room",
    "{} kalıcı olarak silinecek.\nEmin misiniz?":
        "{} will be deleted permanently.\nAre you sure?",
    "Sebep (opsiyonel):":
        "Reason (optional):",
    "{}🔓  Şifreleme Kapalı":
        "{}🔓  Encryption Off",
    "  (kütüphane yüklü değil)":
        "  (library not installed)",
    "  (başlatılıyor…)":
        "  (starting…)",
    "  (GPG anahtarı yok)":
        "  (no GPG key)",
    "🔒 OMEMO":
        "🔒 OMEMO",
    "🔒 OMEMO şifreleme açıldı":
        "🔒 OMEMO encryption turned on",
    "🔑 PGP":
        "🔑 PGP",
    "🔑 OpenPGP şifreleme açıldı":
        "🔑 OpenPGP encryption turned on",
    "🔓 Şifreleme kapatıldı":
        "🔓 Encryption turned off",
    "Tepki seç":
        "Pick a reaction",
    "Emoji":
        "Emoji",
    "☁  Sunucuya Yükle (HTTP)":
        "☁  Upload to Server (HTTP)",
    "⚡  P2P Gönder (Jingle)":
        "⚡  Send P2P (Jingle)",
    "Dosya Seç":
        "Choose File",
    "Dosya Transferi":
        "File Transfer",
    "Bu sohbet OpenPGP ile şifreli, ama OpenPGP dosya şifreleyemez: dosya sunucuya şifresiz yüklenir, bağlantıyı gören herkes açabilir. Yine de gönderilsin mi?":
        "This chat uses OpenPGP, but OpenPGP cannot encrypt files: the file is uploaded unencrypted and anyone with the link can open it. Send anyway?",
    "{} Yükleniyor: {}…":
        "{} Uploading: {}…",
    "Bu sohbet şifreli, ama P2P aktarım (Jingle/IBB) uçtan uca şifreli değil: dosya sunucu üzerinden şifresiz geçer. Yine de P2P ile gönderilsin mi?":
        "This chat is encrypted, but P2P transfer (Jingle/IBB) is not end-to-end encrypted: the file passes through the server unencrypted. Send via P2P anyway?",
    "Şifreli göndermek için 📎 → Sunucuya Yükle'yi kullanın (OMEMO'lu sohbette dosya şifrelenir).":
        "To send it encrypted, use 📎 → Upload to Server (files are encrypted in OMEMO chats).",
    "{mb} MB üzeri dosyalarda P2P yavaş olabilir. Devam edilsin mi?":
        "P2P may be slow for files over {mb} MB. Continue?",
    "Kişi çevrimdışı görünüyor; P2P başarısız olabilir.":
        "Contact appears offline; P2P may fail.",
    "otomatik kabul edildi":
        "accepted automatically",
    "Gelen Dosya Teklifi":
        "Incoming File Offer",
    "sha-256: {}…":
        "sha-256: {}…",
    "P2P — uçtan uca şifreli değil":
        "P2P — not end-to-end encrypted",
    "Kabul Et ve Kaydet":
        "Accept and Save",
    "Dosya teklifi yanıtsız kaldı":
        "File offer timed out",
    "Reddet":
        "Decline",
    "bilinmeyen hata":
        "unknown error",
    "❌ Dosya transferi: {}":
        "❌ File transfer: {}",
    "P2P başarısız oldu. Dosya sunucuya yüklenerek gönderilsin mi?":
        "P2P failed. Send the file via server upload?",
    "Dosya gönderildi":
        "File sent",
    "Dosya alındı":
        "File received",
    "İptal":
        "Cancel",
    "Mesaj Arama":
        "Message Search",
    "🔍  Mesajlarda Ara":
        "🔍  Search Messages",
    "Aranacak metin...":
        "Text to search...",
    "Tema":
        "Theme",
    "Tema uygulandı. Bazı öğeler yeniden başlatmada yenilenir.":
        "Theme applied. Some elements refresh after a restart.",
    "En az {} harfli bir kelime girin":
        "Enter a word of at least {} letters",
    "Oda Oluştur":
        "Create Room",
    "{} adresinde zaten bir oda var.\n\nLütfen başka bir ad seçin. Oda sizinse odalar bölümündeki + (Odaya Katıl) düğmesiyle girebilirsiniz.":
        "There is already a room at {}.\n\nPlease choose another name. If the room is yours, you can enter it with the + (Join Room) button in the rooms section.",
    "⚠ Sunucu şifreli oda ayarlarını (yalnız üyeler / gerçek JID'ler) desteklemiyor; OMEMO bu odada çalışmaz. Oda normal ayarlarla açıldı.":
        "⚠ The server doesn't support encrypted room settings (members only / real JIDs); OMEMO won't work in this room. The room was opened with normal settings.",
    "🌐 Oda hazır: adresi bilen herkes katılabilir.":
        "🌐 Room ready: anyone who knows the address can join.",
    "🔒 Şifreli oda hazır: mesajlar OMEMO ile şifrelenir; yalnız davet ettikleriniz katılabilir (odaya sağ tık → 📨 Davet Gönder).":
        "🔒 Encrypted room ready: messages are encrypted with OMEMO; only people you invite can join (right-click the room → 📨 Send Invitation).",
    "Hesap":
        "Account",
    "Sunucu":
        "Server",
    "🟢 Aktif":
        "🟢 Active",
    "🔴 Pasif":
        "🔴 Inactive",
    "⚫ Pasif":
        "⚫ Inactive",
    "PyAudio":
        "PyAudio",
    "🟢 Yüklü":
        "🟢 Installed",
    "⚫ Yok":
        "⚫ None",
    "Kişi Sayısı":
        "Contact Count",
    "Aktif Odalar":
        "Active Rooms",
    "Ayar Dosyası":
        "Settings File",
    "OMEMO Veri":
        "OMEMO Data",
    "Fotoğraf yayınlanamadı; eski fotoğraf korundu.":
        "The photo could not be published; the old photo was kept.",
    "🌐 Dil":
        "🌐 Language",
    "Yeni dil uygulama yeniden başlatılınca geçerli olur.":
        "The new language takes effect when the app is restarted.",
    "● Uzakta (oto)":
        "● Away (auto)",
    "Göster":
        "Show",
    "Çıkış":
        "Quit",
    "XMPP İstemci":
        "XMPP Client",
    "📶 {}ms":
        "📶 {}ms",
    "{} sonuç":
        "{} results",
    "GIF / Sticker":
        "GIF / Sticker",
    "🎭 GIF Ara":
        "🎭 Search GIFs",
    "💡 Üstteki kutuya yazıp Enter'a basın (ilk aramada Tenor API anahtarı sorulur)":
        "💡 Type in the box above and press Enter (the first search asks for a Tenor API key)",
    "GIF Araması":
        "GIF Search",
    "Tenor API anahtarı (Google Cloud Console → Tenor API):":
        "Tenor API key (Google Cloud Console → Tenor API):",
    "⚠ GIF araması için Tenor API anahtarı gerekli":
        "⚠ GIF search needs a Tenor API key",
    "Sonuç bulunamadı":
        "No results found",
    "{} GIF — tıklayınca gönderilir":
        "{} GIFs — click to send",
    "Yedekleme / Geri Yükleme":
        "Backup / Restore",
    "💾 Sohbet Yedekleme":
        "💾 Chat Backup",
    "Yedek Kaydet":
        "Save Backup",
    "Yedek":
        "Backup",
    "Yedeklendi: {}":
        "Backed up: {}",
    "Yedek Yükle":
        "Load Backup",
    "Geri yüklendi: {} sohbet":
        "Restored: {} chats",
    "📤 Yedekle (JSON)":
        "📤 Back Up (JSON)",
    "📥 Geri Yükle":
        "📥 Restore",
    "OMEMO QR Doğrulama":
        "OMEMO QR Verification",
    "🔐 OMEMO Parmak İzi":
        "🔐 OMEMO Fingerprint",
    "Yükleniyor…":
        "Loading…",
    "(OMEMO hazır değil)":
        "(OMEMO not ready)",
    "QR için: pip install qrcode":
        "For QR: pip install qrcode",
    "Kopyalandı":
        "Copied",
    "Parmak izi panoya kopyalandı":
        "Fingerprint copied to clipboard",
    "📋 Kopyala":
        "📋 Copy",
    "Sohbet Arka Planı":
        "Chat Background",
    "🖼 Sohbet Arka Planı":
        "🖼 Chat Background",
    "Resim":
        "Image",
    "*.png *.jpg *.jpeg *.gif *.bmp":
        "*.png *.jpg *.jpeg *.gif *.bmp",
    "Arka Plan Seç":
        "Choose Background",
    "Arka Plan Rengi":
        "Background Color",
    "🖼 Resim Seç":
        "🖼 Choose Image",
    "🎨 Renk Seç":
        "🎨 Choose Color",
    "↩ Varsayılana Dön":
        "↩ Back to Default",
    "↩ Yanıtlanacak mesaj yok":
        "↩ No message to reply to",
    "✏ Düzenlenecek mesajım yok":
        "✏ No message of mine to edit",
    "🗑 Silinecek mesajım yok":
        "🗑 No message of mine to delete",
    "Mesaj Zamanla":
        "Schedule Message",
    "Mesaj:":
        "Message:",
    "Kaç dakika sonra gönderilsin:":
        "Send after how many minutes:",
    "30 dk":
        "30 min",
    "1 saat":
        "1 hour",
    "Özel (dk):":
        "Custom (min):",
    "⏰ Zamanla":
        "⏰ Schedule",
    "⏰ Zamanlanmış mesaj ({} dk sonra): {}":
        "⏰ Scheduled message (in {} min): {}",
    "Toplu Mesaj":
        "Broadcast Message",
    "📢 Toplu Mesaj Gönder":
        "📢 Send Broadcast Message",
    "Alıcıları seçin:":
        "Choose recipients:",
    "0 kişi seçildi":
        "0 contacts selected",
    "{} kişi seçildi":
        "{} contacts selected",
    "{} kişiye gönderildi":
        "Sent to {} contacts",
    "📨 Gönder":
        "📨 Send",
    "Otomatik Tema Geçişi":
        "Automatic Theme Switching",
    "🌓 Otomatik Tema Geçişi":
        "🌓 Automatic Theme Switching",
    "Otomatik tema geçişini etkinleştir":
        "Turn on automatic theme switching",
    "Gündüz teması:":
        "Day theme:",
    "Gece teması:":
        "Night theme:",
    "Gündüz başlangıç saati:":
        "Day starts at:",
    "Gece başlangıç saati:":
        "Night starts at:",
    "Kaydet":
        "Save",
    "Uygulama Kilidi":
        "App Lock",
    "Mevcut PIN ayarlanmış ✓":
        "A PIN is set ✓",
    "PIN Doğrula":
        "Verify PIN",
    "Mevcut PIN:":
        "Current PIN:",
    "PIN kaldırıldı":
        "PIN removed",
    "🗑 PIN'i Kaldır":
        "🗑 Remove PIN",
    "Yeni PIN belirleyin:":
        "Set a new PIN:",
    "Tekrar girin:":
        "Enter it again:",
    "PIN en az 4 karakter olmalı":
        "The PIN must be at least 4 characters",
    "PIN'ler eşleşmiyor":
        "The PINs don't match",
    "PIN":
        "PIN",
    "PIN ayarlandı ✓":
        "PIN set ✓",
    "🔒 PIN Ayarla":
        "🔒 Set PIN",
    "Proxy Ayarları":
        "Proxy Settings",
    "🔒 Proxy / SOCKS Ayarları":
        "🔒 Proxy / SOCKS Settings",
    "Proxy türü:":
        "Proxy type:",
    "Yok":
        "None",
    "Adres:":
        "Address:",
    "Port:":
        "Port:",
    "💡 Tor için: SOCKS5, 127.0.0.1:9050":
        "💡 For Tor: SOCKS5, 127.0.0.1:9050",
    "Yalnız XMPP bağlantısı proxy'den geçer; dosya yükleme/indirme, bağlantı önizlemesi, GIF ve AI istekleri geçmez. Kimlik doğrulamalı proxy desteklenmez.":
        "Only the XMPP connection goes through the proxy; file uploads/downloads, link previews, GIF and AI requests don't. Proxies with authentication are not supported.",
    "Proxy":
        "Proxy",
    "Ayarlar kaydedildi.\nBir sonraki bağlantıda uygulanır (ör. uygulamayı yeniden başlatınca).":
        "Settings saved.\nThey apply on the next connection (e.g. after restarting the app).",
    "Kullanılabilir komutlar:\n/help — Bu yardım\n/clear — Sohbet geçmişini temizle\n/nick <isim> — Oda takma adını değiştir\n/topic <konu> — Oda konusunu değiştir\n/invite <jid> — Odaya davet et\n/kick <nick> — Odadan at\n/ban <jid> — Yasakla\n/join <oda> — Odaya katıl\n/leave — Odadan ayrıl\n/status <mesaj> — Durum mesajı değiştir\n/ping — Sunucu ping\n/time — Şu anki saat\n/broadcast — Toplu mesaj\n/schedule — Mesaj zamanla\n/reply <metin> — Son gelen mesaja yanıt ver\n/react <emoji> — Son gelen mesaja tepki ekle\n/edit <metin> — Son mesajımı düzenle\n/del — Son mesajımı sil":
        "Available commands:\n/help — This help\n/clear — Clear chat history\n/nick <name> — Change your room nickname\n/topic <topic> — Change the room topic\n/invite <jid> — Invite to the room\n/kick <nick> — Kick from the room\n/ban <jid> — Ban\n/join <room> — Join a room\n/leave — Leave the room\n/status <message> — Change the status message\n/ping — Ping the server\n/time — Current time\n/broadcast — Broadcast message\n/schedule — Schedule a message\n/reply <text> — Reply to the last incoming message\n/react <emoji> — React to the last incoming message\n/edit <text> — Edit my last message\n/del — Delete my last message",
    "📶 Son ping: {}ms":
        "📶 Last ping: {}ms",
    "Takma ad değiştirildi: {}":
        "Nickname changed: {}",
    "Konu değiştirildi: {}":
        "Topic changed: {}",
    "Davet gönderildi: {}":
        "Invitation sent: {}",
    "Kullanıcı atıldı: {}":
        "User kicked: {}",
    "Yasakla":
        "Ban",
    "Kullanıcı yasaklanıyor: {}":
        "Banning user: {}",
    "Odaya katılınıyor: {}":
        "Joining room: {}",
    "Odadan ayrılınıyor: {}":
        "Leaving room: {}",
    "Durum güncellendi: {}":
        "Status updated: {}",
    "😊 Tepki verilecek mesaj yok":
        "😊 No message to react to",
    "Bilinmeyen komut: {}\n/help yazarak yardım alabilirsiniz":
        "Unknown command: {}\nType /help for help",
    "Sohbet — {}":
        "Chat — {}",
    "Bölünmüş Ekran":
        "Split Screen",
    "En az 2 sohbet gerekli":
        "At least 2 chats are needed",
    "Bölünmüş Ekran — İkinci sohbet seçin":
        "Split Screen — Choose the second chat",
    "✓ Bağlandı":
        "✓ Connected",
    "✓ Bağlantı Kuruldu":
        "✓ Connection Established",
    "Sunucuya bağlanıldı":
        "Connected to the server",
    "XMPP — {}{}  {}  {}":
        "XMPP — {}{}  {}  {}",
    "Mesaj — {}":
        "Message — {}",
    "Yeni mesaj":
        "New message",
    "  Arama hatası: {}":
        "  Search error: {}",
    "  Sonuç bulunamadı":
        "  No results found",
    "✓ {} odasına katıldı":
        "✓ Joined {}",
    "ℹ {} zaten vardı: mevcut odaya katıldınız, ayarları değiştirilmedi.":
        "ℹ {} already existed: you joined the existing room; its settings were not changed.",
    "Bir kişi veya oda seçin":
        "Choose a contact or room",
    "📌 Konu: {}":
        "📌 Topic: {}",
    "MUC Daveti":
        "MUC Invitation",
    "{} odasına davet edildiniz.\nSebep: {}\n\nKabul et?":
        "You were invited to {}.\nReason: {}\n\nAccept?",
    "Arkadaşlık İsteği":
        "Contact Request",
    "{} sizi takip etmek istiyor.\nKabul et?":
        "{} wants to follow you.\nAccept?",
    "Oda Keşfi":
        "Room Discovery",
    "Giriş Hatası":
        "Login Error",
    "⚠ Bağlantı kesildi":
        "⚠ Disconnected",
    "⚠ Bağlanılamadı":
        "⚠ Could not connect",
    "⚠ Bağlantı başarısız{}: {}":
        "⚠ Connection failed{}: {}",
    "Bağlantı kesildi":
        "Disconnected",
    "📊 Anket Oluştur":
        "📊 Create Poll",
    "Soru:":
        "Question:",
    "Seçenekler (her satır bir seçenek):":
        "Options (one per line):",
    "Evet\nHayır\nKararsızım":
        "Yes\nNo\nUndecided",
    "Anket":
        "Poll",
    "Soru ve en az 2 seçenek gerekli":
        "A question and at least 2 options are required",
    "\n💡 Oy vermek için ilgili emoji ile tepki ekleyin":
        "\n💡 React with the matching emoji to vote",
    "📊 Anketi Gönder":
        "📊 Send Poll",
    "Hikaye":
        "Story",
    "Fotoğraf okunamadı: {}":
        "The photo could not be read: {}",
    "📖 Hikaye":
        "📖 Story",
    "Durum yayınlandı":
        "Status published",
    "📋 XMPP Log Görüntüleyici":
        "📋 XMPP Log Viewer",
    "📋 XMPP XML Trafik Logu":
        "📋 XMPP XML Traffic Log",
    "── XMPP Debug Log ──\n":
        "── XMPP Debug Log ──\n",
    "Hesap: {}\n":
        "Account: {}\n",
    "Bağlı: {}\n\n":
        "Connected: {}\n\n",
    "→ SENT:\n{}\n\n":
        "→ SENT:\n{}\n\n",
    "← RECV:\n{}\n\n":
        "← RECV:\n{}\n\n",
    "⚠ Filter eklenemedi\n":
        "⚠ Filter could not be added\n",
    "🗑 Temizle":
        "🗑 Clear",
    "📤 Dışa Aktar":
        "📤 Export",
    "Sunucu başlatılamadı (port {}):\n{}":
        "The server could not be started (port {}):\n{}",
    "🌐 REST API":
        "🌐 REST API",
    "🔴 Hata: {}":
        "🔴 Error: {}",
    "🟢 Çalışıyor":
        "🟢 Running",
    "⚫ Durduruldu":
        "⚫ Stopped",
    "Token:":
        "Token:",
    "⏳ Başlatılıyor…":
        "⏳ Starting…",
    "⏳ Durduruluyor…":
        "⏳ Stopping…",
    "▶ Başlat":
        "▶ Start",
    "⏹ Durdur":
        "⏹ Stop",
    "API Endpoints:":
        "API Endpoints:",
    "Bağlantı durumu":
        "Connection status",
    "Kişi listesi":
        "Contact list",
    "Oda listesi":
        "Room list",
    "Mesaj geçmişi":
        "Message history",
    "Mesaj gönder {to, message}":
        "Send message {to, message}",
    "Bağlantı Kurulamadı":
        "Could Not Connect",
    "20 saniye içinde sunucuya bağlanılamadı.\n\nSunucu: {}:{}{}\nSon hata: {}\n\nArka planda yeniden bağlanma denemeleri sürüyor.\nDenemeye devam edilsin mi?\n(\"Hayır\" → giriş ekranına dönülür)":
        "Could not connect to the server within 20 seconds.\n\nServer: {}:{}{}\nLast error: {}\n\nReconnect attempts continue in the background.\nKeep trying?\n(\"No\" → back to the login screen)",
    "Kapat":
        "Close",
    "Ne yapmak istiyorsun?":
        "What do you want to do?",
    "  Gizle (Tepsiye)  ":
        "  Hide (to Tray)  ",
    "  Uygulamadan Cik  ":
        "  Quit the App  ",
    "  Iptal  ":
        "  Cancel  ",
    "🔁 Hesap Değişimi":
        "🔁 Switch Account",
    "{} hesabına geçiliyor…":
        "Switching to {}…",
    "Hesap değiştirilemedi: {}":
        "Could not switch account: {}",
    "XMPP bağlantı thread'i durdu: {}":
        "XMPP connection thread stopped: {}",
    "Bağlanıyor… {}":
        "Connecting… {}",
    "🔑 Uygulama Kilidi":
        "🔑 App Lock",
    "🔑 PIN Girin":
        "🔑 Enter PIN",
    "Yanlış PIN":
        "Wrong PIN",
    "Giriş":
        "Log In",
    # ── xmppcore/aesgcm.py ──
    "aesgcm bağlantısı yalnız https yüklemeden kurulur":
        "An aesgcm link is only made from an https upload",
    # ── xmppcore/agent.py ──
    "Çevrimiçi":
        "Online",
    "Uzakta":
        "Away",
    "Meşgul":
        "Busy",
    "Uzun süre uzakta":
        "Extended away",
    "Model beklenen biçimde yanıt vermedi; tekrar deneyin.":
        "The model did not reply in the expected format; try again.",
    "Hangi kişi ya da oda için? Adını yazın ya da önce sohbeti açın.":
        "For which contact or room? Type the name or open the chat first.",
    "Hangi odaya katılmak istiyorsunuz?":
        "Which room do you want to join?",
    "Ne sormak istiyorsunuz?":
        "What do you want to ask?",
    "Mesaj ya da hatırlatıcı metni eksik.":
        "The message or reminder text is missing.",
    "Hangi durum? (çevrimiçi, uzakta, meşgul)":
        "Which status? (online, away, busy)",
    "Hatırlatıcı için tarih ve saat gerekli (ör. yarın 10:00).":
        "A reminder needs a date and time (e.g. tomorrow 10:00).",
    "Hatırlatıcı zamanı geçmişte kalıyor.":
        "The reminder time is in the past.",
    "📨 Mesaj gönderilsin mi?":
        "📨 Send the message?",
    "Alıcı: {}\n“{}”":
        "To: {}\n“{}”",
    "⏰ Hatırlatıcı kurulsun mu?":
        "⏰ Set the reminder?",
    "🚪 Odaya katılınsın mı?":
        "🚪 Join the room?",
    "● Durum değiştirilsin mi?":
        "● Change the status?",
    "Geçmişe sor: ":
        "Ask history: ",
    "📬 Okunmamışları özetle":
        "📬 Summarize unread",
    "📅 Görevleri çıkar":
        "📅 Extract tasks",
    "❓ Bekleyen sorular":
        "❓ Unanswered questions",
    "✍ Taslaklar":
        "✍ Drafts",
    # ── xmppcore/ai.py ──
    "🚫 Bu mesaj silindi":
        "🚫 This message was deleted",
    "🎤 Ses mesajı":
        "🎤 Voice message",
    "(Konuşma algılanmadı)":
        "(No speech detected)",
    "[…yanıt uzunluk sınırına takıldı ve kesildi]":
        "[…the reply hit the length limit and was cut off]",
    "AI asistanı kapalı. ⚙ AI Ayarları'ndan bir sağlayıcı seçin.":
        "The AI assistant is off. Choose a provider in ⚙ AI Settings.",
    "Bu sohbet şifreli. Şifreli içerik izniniz olmadan buluta (Claude) gönderilmez.":
        "This chat is encrypted. Encrypted content is not sent to the cloud (Claude) without your permission.",
    "☁ Claude (bulut) · {}":
        "☁ Claude (cloud) · {}",
    "🖥 Yerel (Ollama) · {}":
        "🖥 Local (Ollama) · {}",
    "AI kapalı":
        "AI off",
    "Yanıt boyut sınırını aştı.":
        "The reply exceeded the size limit.",
    "Geçersiz adres: {!r} (http/https olmalı)":
        "Invalid address: {!r} (must be http/https)",
    "Ollama'da '{}' modeli yok. Terminalde kurun:\n  ollama pull {}":
        "Ollama doesn't have the '{}' model. Install it in a terminal:\n  ollama pull {}",
    "Ollama hatası ({}): {}":
        "Ollama error ({}): {}",
    "Ollama'ya ulaşılamadı ({}).\nOllama çalışıyor mu? Terminalde: ollama serve":
        "Could not reach Ollama ({}).\nIs Ollama running? In a terminal: ollama serve",
    "Yerel model zamanında yanıt vermedi.":
        "The local model did not reply in time.",
    "Ollama'dan geçersiz yanıt alındı.":
        "Invalid reply from Ollama.",
    "Ollama yanıtı yarıda kesildi.":
        "The Ollama reply was cut off.",
    "Ollama hatası: {}":
        "Ollama error: {}",
    "Model yanıtı uzunluk sınırına takıldı; daha kısa bir sohbet aralığıyla tekrar deneyin.":
        "The model's reply hit the length limit; try again with a shorter part of the chat.",
    "Yerel model boş yanıt döndürdü.":
        "The local model returned an empty reply.",
    "Gömme modeli beklenmeyen yanıt döndürdü.":
        "The embedding model returned an unexpected reply.",
    "Claude için 'anthropic' paketi kurulu değil:\n  .venv-xmpp/bin/python -m pip install anthropic":
        "The 'anthropic' package is not installed for Claude:\n  .venv-xmpp/bin/python -m pip install anthropic",
    "Claude API anahtarı geçersiz ya da eksik (⚙ AI Ayarları).":
        "The Claude API key is invalid or missing (⚙ AI Settings).",
    "Bu API anahtarının bu modele erişim izni yok.":
        "This API key has no access to this model.",
    "Claude modeli bulunamadı: {}":
        "Claude model not found: {}",
    "Claude hız sınırına takıldı; biraz sonra tekrar deneyin.":
        "Claude rate limit reached; try again a little later.",
    "Claude isteği kabul etmedi: {}":
        "Claude did not accept the request: {}",
    "Claude sunucu hatası ({}); daha sonra tekrar deneyin.":
        "Claude server error ({}); try again later.",
    "Claude'a bağlanılamadı (internet bağlantısı?).":
        "Could not connect to Claude (internet connection?).",
    "Claude hatası: {}":
        "Claude error: {}",
    "Claude bu isteği güvenlik nedeniyle yanıtlamadı.":
        "Claude did not answer this request for safety reasons.",
    "Claude boş yanıt döndürdü.":
        "Claude returned an empty reply.",
    "✍ Yazımı düzelt":
        "✍ Fix spelling",
    "🎩 Resmîleştir":
        "🎩 Make formal",
    "😊 Samimileştir":
        "😊 Make friendly",
    "✂ Kısalt":
        "✂ Shorten",
    "🌐 İngilizceye çevir":
        "🌐 Translate to English",
    "Bilinmeyen düzenleme modu: {}":
        "Unknown edit mode: {}",
    "Model geçerli JSON döndürmedi; tekrar deneyin.":
        "The model did not return valid JSON; try again.",
    "Başlığı boş bir öğe var.":
        "An item has an empty title.",
    "“{}”: tarih YYYY-AA-GG biçiminde olmalı.":
        "“{}”: the date must be in YYYY-MM-DD format.",
    "“{}”: saat SS:DD biçiminde olmalı.":
        "“{}”: the time must be in HH:MM format.",
    "“{}”: bitiş saati SS:DD biçiminde olmalı.":
        "“{}”: the end time must be in HH:MM format.",
    "“{}”: saat verildiyse tarih de gerekli.":
        "“{}”: a time needs a date too.",
    "Sohbetten: “{}”":
        "From the chat: “{}”",
    "Görsel biçimi tanınmadı.":
        "Image format not recognized.",
    "Görsel açılamadı.":
        "The image could not be opened.",
    "Medya indirilemedi.":
        "The media could not be downloaded.",
    "Ses→metin için faster-whisper gerekli (yerel çalışır):\n  .venv-xmpp/bin/python -m pip install faster-whisper \"av<19\"":
        "Speech-to-text needs faster-whisper (runs locally):\n  .venv-xmpp/bin/python -m pip install faster-whisper \"av<19\"",
    "Whisper modeli yüklenemedi ({}): {}":
        "The Whisper model could not be loaded ({}): {}",
    "Ses çözücü (PyAV) faster-whisper ile uyumsuz. Düzeltmek için:\n  .venv-xmpp/bin/python -m pip install \"av<19\"":
        "The audio decoder (PyAV) is incompatible with faster-whisper. To fix it:\n  .venv-xmpp/bin/python -m pip install \"av<19\"",
    "Ses yazıya dökülemedi: {}":
        "The audio could not be transcribed: {}",
    # ── xmppcore/archive.py ──
    "🔒 Şifreli mesaj (arşivde çözülemedi)":
        "🔒 Encrypted message (could not be decrypted in the archive)",
    # ── xmppcore/format.py ──
    "[İletildi — {}]\n{}":
        "[Forwarded — {}]\n{}",
    # ── xmppcore/helpers.py ──
    "Oda adresi boş":
        "The room address is empty",
    "Geçersiz oda adresi: {!r} — oda adında {}":
        "Invalid room address: {!r} — in the room name, {}",
    " (ör. {})":
        " (e.g. {})",
    "Oda adresinde sunucu yok: {!r}":
        "The room address has no server: {!r}",
    "Geçersiz oda adresi: {!r}":
        "Invalid room address: {!r}",
    "boşluk kullanılamaz":
        "spaces are not allowed",
    "şu karakterler kullanılamaz: ":
        "these characters are not allowed: ",
    "Oda adı girin.":
        "Enter a room name.",
    "Oda adından adres üretilemedi; harf ya da rakam kullanın (ör. proje-ekibi).":
        "Could not make an address from the room name; use letters or digits (e.g. project-team).",
    "Lütfen bir JID girin.":
        "Please enter a JID.",
    "Geçersiz JID — @ işareti olmalı (ör: ali@sunucu.tld)":
        "Invalid JID — it must contain @ (e.g. ali@server.tld)",
    "Geçersiz JID — {}: {!r}":
        "Invalid JID — {}: {!r}",
    "Geçersiz JID: {!r}":
        "Invalid JID: {!r}",
    # ── xmppcore/i18n.py (KEYS) ──
    "Mesaj yazın...":
        "Type a message...",
    "Tepki Ekle":
        "Add Reaction",
    "Bir sohbet seçin":
        "Select a chat",
    "Bir kişi veya oda seçerek konuşmaya başlayın":
        "Select a contact or room to start chatting",
    "Sohbete Başlayın":
        "Start a Conversation",
    "yazıyor":
        "typing",
    # ── xmppcore/messages.py ──
    "⚠ OMEMO mesajı alındı ancak OMEMO hazır değil — çözülemedi":
        "⚠ An OMEMO message arrived but OMEMO is not ready — it could not be decrypted",
    "OMEMO kütüphanesi yüklü değil (slixmpp-omemo).":
        "The OMEMO library is not installed (slixmpp-omemo).",
    "OMEMO henüz hazır değil — lütfen birkaç saniye bekleyin.":
        "OMEMO is not ready yet — please wait a few seconds.",
    "Mesaj gönderilemedi: {}":
        "Message could not be sent: {}",
    "Düzenleme hatası: {}":
        "Edit error: {}",
    "Silme hatası: {}":
        "Delete error: {}",
    "Tepki hatası: {}":
        "Reaction error: {}",
    "Yanıt hatası: {}":
        "Reply error: {}",
    "İletme hatası: {}":
        "Forwarding error: {}",
    # ── xmppcore/muc.py ──
    "Bu takma ad odada kullanılıyor; başka bir takma ad deneyin.":
        "This nickname is in use in the room; try another nickname.",
    "Oda parola istiyor.":
        "The room requires a password.",
    "Bu odaya girişiniz yasaklanmış.":
        "You are banned from this room.",
    "Oda yalnız üyelere açık.":
        "The room is members-only.",
    "Oda bulunamadı (adres yanlış ya da oda kilitli olabilir).":
        "Room not found (the address may be wrong or the room locked).",
    "Oda sunucusu bulunamadı (adresi kontrol edin).":
        "Room server not found (check the address).",
    "Oda dolu ya da şu an kullanılamıyor.":
        "The room is full or unavailable right now.",
    "Bu sunucuda yeni oda oluşturma izniniz yok.":
        "You are not allowed to create rooms on this server.",
    "Geçersiz oda adresi ya da takma ad.":
        "Invalid room address or nickname.",
    "Oda sunucusuna ulaşılamadı (zaman aşımı).":
        "Could not reach the room server (timeout).",
    "Oda taşınmış ya da kaldırılmış.":
        "The room was moved or removed.",
    "Oda mesajı gönderilemedi: {}":
        "Room message could not be sent: {}",
    "'{}' sunucusunda oda bulunamadi.":
        "No rooms found on the '{}' server.",
    "Sunucu bulunamadi (DNS hatasi)":
        "Server not found (DNS error)",
    "Sunucu kesfetme desteklemiyor":
        "The server does not support discovery",
    "Sunucu yanit vermedi (zaman asimi)":
        "The server did not respond (timeout)",
    "Erisim reddedildi":
        "Access denied",
    "⚠ '{}': {}. Genel Ara sekmesini deneyin.":
        "⚠ '{}': {}. Try the Public Search tab.",
    "Oda katılım hatası: {} {} sn içinde yanıt vermedi; oda sunucusu kapalı ya da adres yanlış olabilir.":
        "Room join error: {} did not respond within {} s; the room server may be down or the address wrong.",
    "{} odasına katılınamadı: {}":
        "Could not join {}: {}",
    "Oda katılım hatası: {}":
        "Room join error: {}",
    "Oda ayrılma hatası: {}":
        "Error leaving the room: {}",
    "Konu değiştirme hatası: {}":
        "Topic change error: {}",
    "✓ {} odadan atıldı.":
        "✓ {} was kicked from the room.",
    "Kick hatası: {}":
        "Kick error: {}",
    "✓ {} yasaklandı.":
        "✓ {} was banned.",
    "Ban hatası: {}":
        "Ban error: {}",
    "Rol değiştirme hatası: {}":
        "Role change error: {}",
    "Yetki değiştirme hatası: {}":
        "Affiliation change error: {}",
    "✓ Takma adın değişti: {}":
        "✓ Your nickname changed: {}",
    "Takma ad değiştirilemedi: {}":
        "Nickname could not be changed: {}",
    "✓ {} davet edildi → {}":
        "✓ {} invited → {}",
    "Davet hatası: {}":
        "Invitation error: {}",
    "Oda ayarları alınamadı: {}":
        "Room settings could not be fetched: {}",
    "✓ {} ayarları güncellendi.":
        "✓ {} settings updated.",
    "Oda ayar kaydetme hatası: {}":
        "Error saving room settings: {}",
    "✓ {} odası silindi.":
        "✓ Room {} deleted.",
    "Oda silme hatası: {}":
        "Room delete error: {}",
    "ℹ {} adresinde oda yoktu; sunucunun varsayılan ayarlarıyla yeni bir oda oluşturuldu.":
        "ℹ There was no room at {}; a new room was created with the server's default settings.",
    "Yeni oda kullanıma açılamadı: {}":
        "The new room could not be opened for use: {}",
    "Oda yapılandırılamadı (sahibi olarak ⋮ → Oda Yönetimi'ni kullanın): {}":
        "The room could not be configured (as the owner, use ⋮ → Room Management): {}",
    "✓ Yer imleri kaydedildi":
        "✓ Bookmarks saved",
    "Yer imi kaydetme hatası: {}":
        "Error saving bookmark: {}",
    # ── xmppcore/presence.py ──
    "✓ {} isteği kabul etti":
        "✓ {} accepted the request",
    "✗ {} sizi kaldırdı":
        "✗ {} removed you",
    # ── xmppcore/proxy.py ──
    "genel sunucu hatası":
        "general server failure",
    "kural seti izin vermedi":
        "not allowed by ruleset",
    "ağa ulaşılamıyor":
        "network unreachable",
    "sunucuya ulaşılamıyor":
        "host unreachable",
    "bağlantı reddedildi":
        "connection refused",
    "zaman aşımı (TTL)":
        "timeout (TTL)",
    "komut desteklenmiyor":
        "command not supported",
    "adres türü desteklenmiyor":
        "address type not supported",
    "Proxy adresi girin (Tor için 127.0.0.1).":
        "Enter a proxy address (127.0.0.1 for Tor).",
    "Geçerli bir port girin (1–65535).":
        "Enter a valid port (1–65535).",
    "Proxy bağlantıyı beklenmedik şekilde kapattı":
        "The proxy closed the connection unexpectedly",
    "Geçersiz hedef adı: {!r}":
        "Invalid target name: {!r}",
    "SOCKS5 değil: proxy türünü kontrol edin":
        "Not SOCKS5: check the proxy type",
    "SOCKS5 proxy kimlik doğrulama istiyor (desteklenmiyor)":
        "The SOCKS5 proxy requires authentication (not supported)",
    "hata kodu {}":
        "error code {}",
    "SOCKS5: {}":
        "SOCKS5: {}",
    "SOCKS5: geçersiz proxy yanıtı":
        "SOCKS5: invalid proxy reply",
    "SOCKS4: istek reddedildi (kod {})":
        "SOCKS4: request rejected (code {})",
    "HTTP proxy yanıtı çok uzun":
        "HTTP proxy reply is too long",
    "HTTP proxy reddetti: {}":
        "HTTP proxy refused: {}",
    "Proxy'ye bağlanılamadı ({}:{}): {}":
        "Could not connect to the proxy ({}:{}): {}",
    "Proxy zaman aşımı":
        "Proxy timeout",
    # ── xmppcore/questions.py ──
    "az önce":
        "just now",
    "{} dakika önce":
        "{} minutes ago",
    "{} saat önce":
        "{} hours ago",
    "dün":
        "yesterday",
    "{} gün önce":
        "{} days ago",
    "Yanıtla: {} — {}":
        "Reply: {} — {}",
    # ── xmppcore/sensitive.py ──
    "Anthropic API anahtarı":
        "Anthropic API key",
    "OpenAI API anahtarı":
        "OpenAI API key",
    "GitHub belirteci":
        "GitHub token",
    "AWS erişim anahtarı":
        "AWS access key",
    "Google API anahtarı":
        "Google API key",
    "Slack belirteci":
        "Slack token",
    "Stripe gizli anahtarı":
        "Stripe secret key",
    "Oturum belirteci (JWT)":
        "Session token (JWT)",
    "Özel anahtar (private key)":
        "Private key",
    "Parola / PIN":
        "Password / PIN",
    "Kart numarası":
        "Card number",
    "T.C. kimlik no":
        "Turkish ID number",
    "Bu grup sohbetine şifresiz gönderilecek mesaj":
        "The message to be sent unencrypted to this group chat",
    "Bu mesaj şifresiz gönderilecek ve":
        "This message will be sent unencrypted and",
    "{} şu hassas bilgileri içeriyor gibi görünüyor:\n\n":
        "{} seems to contain this sensitive information:\n\n",
    "\n\nŞifresiz mesajları sunucu yöneticileri görebilir ve sunucu arşivinde (MAM) saklanabilir. Göndermeden önce 🔒 ile şifrelemeyi açabilirsiniz.\n\nYine de gönderilsin mi?":
        "\n\nServer admins can see unencrypted messages, and they may be kept in the server archive (MAM). You can turn on encryption with 🔒 before sending.\n\nSend anyway?",
    # ── xmppcore/transfers.py ──
    "Dosya yükleme hatası: {}":
        "File upload error: {}",
    "🔒 Dosya şifreli yüklendi: {}":
        "🔒 File uploaded encrypted: {}",
    "✓ Dosya gönderildi: {}":
        "✓ File sent: {}",
    "Dosya gönderme hatası: {}":
        "File send error: {}",
    "OMEMO kütüphanesi yüklü değil (slixmpp-omemo) — dosya gönderilmedi.":
        "The OMEMO library is not installed (slixmpp-omemo) — the file was not sent.",
    "OMEMO henüz hazır değil — dosya gönderilmedi; birkaç saniye sonra tekrar deneyin.":
        "OMEMO is not ready yet — the file was not sent; try again in a few seconds.",
    # ── xmppcore/tts.py ──
    "Sesli okuma için yerel bir ses motoru gerekli. Örneğin:\n  sudo pacman -S espeak-ng\nDaha doğal ses için Piper: piper-tts kurun ve ✨ → AI Ayarları'nda Türkçe bir ses modelinin (.onnx) yolunu girin.":
        "Reading aloud needs a local voice engine. For example:\n  sudo pacman -S espeak-ng\nFor a more natural voice, install piper-tts and enter the path of a voice model (.onnx) in ✨ → AI Settings.",
    "Piper için `piper` komutu, bir ses modeli (.onnx) ve bir ses çalar (pw-play/paplay/aplay) gerekli.\n\n":
        "Piper needs the `piper` command, a voice model (.onnx) and an audio player (pw-play/paplay/aplay).\n\n",
    "Seçili ses motoru bulunamadı: {}\n\n":
        "The selected voice engine was not found: {}\n\n",
    "Okunacak metin yok.":
        "There is no text to read.",
    "ℹ Sesli okuma motoru yok (isteğe bağlı): sudo pacman -S espeak-ng":
        "ℹ No read-aloud engine (optional): sudo pacman -S espeak-ng",
    "✓ Sesli okuma: {}":
        "✓ Read aloud: {}",
    # ── süreler, örnek adresler, tema adları ──
    "1 dk":
        "1 min",
    "10 dk":
        "10 min",
    "15 dk":
        "15 min",
    "kullanici@sunucu.tld":
        "user@server.tld",
    "oda@conference.sunucu.tld":
        "room@conference.server.tld",
    "yeni-oda":
        "new-room",
    "muc.sunucu.tld":
        "muc.server.tld",
    "Koyu":
        "Dark",
    "Açık":
        "Light",
    "Gece mavisi":
        "Night blue",
}
