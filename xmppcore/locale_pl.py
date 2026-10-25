"""Polski arayüz kataloğu: Türkçe metin (anahtar) → Polski.

Eksik metin İngilizceye düşer (`xmppcore/i18n.py`); `{}` yer tutucuları
şablonla aynı kalmalı (`tests/test_i18n_catalog.py`).
"""

CATALOG = {
    "Veri zaman aşımı":
        "Przekroczono czas oczekiwania na dane",
    "Beyan edilen boyut aşıldı":
        "Przekroczono zadeklarowany rozmiar",
    "Dosya 2 GiB sınırını aşıyor":
        "Plik przekracza limit 2 GiB",
    "Kabul zaman aşımı":
        "Przekroczono czas na akceptację",
    "Teklif gönderilemedi: {}":
        "Nie udało się wysłać oferty: {}",
    "Hash uyuşmadı":
        "Niezgodny hash",
    "Hash uyuşmazlığı":
        "Niezgodność hasha",
    "Reddedildi":
        "Odrzucono",
    "İptal edildi":
        "Anulowano",
    "Yeni teklif":
        "Nowa oferta",
    "Yeni teklif geldi":
        "Nadeszła nowa oferta",
    "Karşı taraf kapattı: {}":
        "Druga strona zakończyła: {}",
    "sebep yok":
        "bez powodu",
    "↪ Alıntılanan mesaja git":
        "↪ Przejdź do cytowanej wiadomości",
    "👥 Tepkileri gör…":
        "👥 Zobacz reakcje…",
    "🌐 Çevir":
        "🌐 Przetłumacz",
    "🎙 Sesi yazıya dök":
        "🎙 Transkrybuj nagranie",
    "🖼 Görseli açıkla":
        "🖼 Opisz obraz",
    "❓ Görsele soru sor…":
        "❓ Zapytaj o obraz…",
    "🔊 Sesli oku":
        "🔊 Przeczytaj na głos",
    "😀 Daha fazla emoji…":
        "😀 Więcej emoji…",
    "🎤 Yükleniyor…":
        "🎤 Ładowanie…",
    "🎤 Ses Mesajı":
        "🎤 Wiadomość głosowa",
    "🎤 Ses: {}…":
        "🎤 Dźwięk: {}…",
    "⬆ Daha eski":
        "⬆ Starsze",
    "↓ En yeni":
        "↓ Najnowsze",
    "↓ Yeni mesajlar ({})":
        "↓ Nowe wiadomości ({})",
    "📷 Yükleniyor…":
        "📷 Ładowanie…",
    "⚠ Resim yüklenemedi":
        "⚠ Nie udało się wczytać obrazu",
    "ESC ile kapat":
        "Zamknij klawiszem ESC",
    "Tab ↹ kabul · Esc kapat":
        "Tab ↹ akceptuj · Esc zamknij",
    "Takip sorusu sorun…":
        "Zadaj pytanie uzupełniające…",
    "⏳ Hazırlanıyor…":
        "⏳ Przygotowywanie…",
    "Sor ↵":
        "Zapytaj ↵",
    "✓ Hazır":
        "✓ Gotowe",
    "✍ Yazılıyor…":
        "✍ Pisanie…",
    "⏳ Yanıt hazırlanıyor…":
        "⏳ Przygotowywanie odpowiedzi…",
    "Seçince giriş kutusuna yerleştirilir:":
        "Wybrana opcja trafi do pola wpisywania:",
    "Anlamsal Arama":
        "Wyszukiwanie semantyczne",
    "🧠  Anlamla Ara":
        "🧠  Szukaj według znaczenia",
    "Örn: \"geçen ay konuşulan fiyat\", \"buluşma yeri\"":
        "Np. \"cena, o której mówiliśmy w zeszłym miesiącu\", \"miejsce spotkania\"",
    "Ne arıyorsunuz?":
        "Czego szukasz?",
    "📅 Etkinlik":
        "📅 Wydarzenie",
    "✅ Görev":
        "✅ Zadanie",
    "Tarih ve saatler sohbetten tahmin edildi; kaydetmeden önce kontrol edin (YYYY-AA-GG, SS:DD).":
        "Daty i godziny odgadnięto z rozmowy; sprawdź je przed zapisaniem (RRRR-MM-DD, GG:MM).",
    "📅 .ics olarak kaydet":
        "📅 Zapisz jako .ics",
    "⏰ Hatırlatıcı kur":
        "⏰ Ustaw przypomnienie",
    "✓ {} öğe bulundu — seçip kaydedin ya da hatırlatıcı kurun.":
        "✓ Znalezione elementy: {} — zaznacz i zapisz albo ustaw przypomnienie.",
    "Bu sohbette görev ya da etkinlik bulunamadı.":
        "W tej rozmowie nie znaleziono zadań ani wydarzeń.",
    "Tarih":
        "Data",
    "Saat":
        "Godzina",
    "Bitiş":
        "Koniec",
    "Yer":
        "Miejsce",
    "Önce en az bir öğe seçin.":
        "Najpierw zaznacz co najmniej jeden element.",
    "📋 Panoya kopyalandı":
        "📋 Skopiowano do schowka",
    "💬 Sohbete git":
        "💬 Przejdź do rozmowy",
    "⏰ Yarın 09:00 hatırlat":
        "⏰ Przypomnij jutro o 09:00",
    "✓ Yok say":
        "✓ Odrzuć",
    "{} sohbette yanıt bekleyen soru var.":
        "Rozmowy z pytaniami bez odpowiedzi: {}.",
    "Yanıt bekleyen soru yok. 🎉":
        "Brak pytań bez odpowiedzi. 🎉",
    "Yanıt Bekleyen Sorular":
        "Pytania bez odpowiedzi",
    "❓  Yanıt Bekleyen Sorular":
        "❓  Pytania bez odpowiedzi",
    "Son mesajınızdan sonra size sorulan ve henüz yanıtlamadığınız sorular. Tespit bilgisayarınızda yapılır; hiçbir içerik dışarı gönderilmez.":
        "Pytania zadane Ci po Twojej ostatniej wiadomości, na które jeszcze nie odpowiedziano. Wykrywanie odbywa się na Twoim komputerze; żadna treść nie jest wysyłana.",
    "⏳ Taranıyor…":
        "⏳ Skanowanie…",
    "↩ Takip sorusu":
        "↩ Pytanie uzupełniające",
    "✓ Giriş kutusuna kondu — kontrol edip siz gönderin.":
        "✓ Wstawiono do pola wpisywania — sprawdź i wyślij samodzielnie.",
    "✓ Bir öneri seçin":
        "✓ Wybierz propozycję",
    "Asistan":
        "Asystent",
    "✨  Asistan":
        "✨  Asystent",
    "Bir komut yazın ya da soru sorun…":
        "Wpisz polecenie lub zadaj pytanie…",
    "↩ Takip sorusu: {} — {}  (Esc: komut)":
        "↩ Pytanie uzupełniające: {} — {}  (Esc: polecenie)",
    "{}  ·  sırada: {}":
        "{}  ·  w kolejce: {}",
    "sırada: {}":
        "w kolejce: {}",
    "Örnekler — tıklayın ya da kendiniz yazın:":
        "Przykłady — kliknij albo wpisz własne:",
    "✗ Vazgeç":
        "✗ Anuluj",
    "Vazgeçildi.":
        "Anulowano.",
    "Yanıt Taslakları":
        "Szkice odpowiedzi",
    "📝  Yanıt Taslakları":
        "📝  Szkice odpowiedzi",
    "Taslaklar asla kendiliğinden gönderilmez: “Kullan” metni sohbetin giriş kutusuna koyar, düzenleyip siz gönderirsiniz.":
        "Szkice nigdy nie są wysyłane same: „Użyj” wstawia tekst do pola rozmowy, a Ty go edytujesz i wysyłasz.",
    "{} sohbet için taslak var.":
        "Szkice gotowe dla rozmów: {}.",
    "Bekleyen taslak yok.":
        "Brak oczekujących szkiców.",
    "{} yeni mesaj":
        "Nowe wiadomości: {}",
    "⏳ Taslak hazırlanıyor…":
        "⏳ Przygotowywanie szkicu…",
    "🔒 Şifreli sohbet: taslak için içerik buluta (Claude) gönderilmeli.":
        "🔒 Rozmowa szyfrowana: aby powstał szkic, treść trzeba wysłać do chmury (Claude).",
    "➡ Kullan":
        "➡ Użyj",
    "☁ Onayla ve hazırla":
        "☁ Zatwierdź i przygotuj",
    "🔄 Yeniden üret":
        "🔄 Wygeneruj ponownie",
    "✓ Kaldır":
        "✓ Usuń",
    "Kapalı":
        "Wyłączone",
    "🖥 Yerel — Ollama (önerilen; veri bilgisayarda kalır)":
        "🖥 Lokalnie — Ollama (zalecane; dane zostają na Twoim komputerze)",
    "☁ Claude — bulut (Anthropic API)":
        "☁ Claude — chmura (API Anthropic)",
    "AI Ayarları":
        "Ustawienia AI",
    "✨ AI Asistanı":
        "✨ Asystent AI",
    "Şifreli sohbetler varsayılan olarak yalnız yerel modelle işlenir. Ses→metin ve anlamsal arama her zaman yereldir.":
        "Domyślnie rozmowy szyfrowane przetwarza tylko model lokalny. Zamiana mowy na tekst i wyszukiwanie semantyczne zawsze działają lokalnie.",
    "SAĞLAYICI":
        "DOSTAWCA",
    "YEREL MODEL (OLLAMA)":
        "MODEL LOKALNY (OLLAMA)",
    "Adres":
        "Adres",
    "Sohbet modeli":
        "Model rozmowy",
    "Görsel modeli":
        "Model obrazu",
    "Gömme modeli":
        "Model embeddingów",
    "Model sıcak":
        "Trzymaj model w pamięci",
    "Ekran kartı":
        "Karta graficzna",
    "Kurulum: ollama pull {}  ·  ollama pull {}\nModel, bu süre boyunca bellekte tutulur; boşta geçen isteklerde yeniden yükleme beklemesi olmaz (5 dk = Ollama varsayılanı). Ekran kartı \"off\": sohbet modeli yalnız CPU'da (zayıf ekran kartında daha hızlı).":
        "Instalacja: ollama pull {}  ·  ollama pull {}\nModel pozostaje w pamięci przez ten czas, więc żądania po przerwie nie czekają na ponowne wczytanie (5 min = domyślnie w Ollama). Karta graficzna \"off\": model rozmowy działa tylko na CPU (szybciej przy słabej karcie graficznej).",
    "CLAUDE (BULUT)":
        "CLAUDE (CHMURA)",
    "API anahtarı":
        "Klucz API",
    "Kayıtlı anahtar var — değiştirmek için yazın.":
        "Klucz jest zapisany — wpisz nowy, aby go zmienić.",
    "Boş bırakılırsa ANTHROPIC_API_KEY ortam değişkeni kullanılır.":
        "Jeśli pole jest puste, używana jest zmienna środowiskowa ANTHROPIC_API_KEY.",
    "Kayıtlı anahtarı sil":
        "Usuń zapisany klucz",
    "Şifreli sohbetlerde de her seferinde sormadan Claude'u kullan (önerilmez)":
        "Używaj Claude także w rozmowach szyfrowanych bez pytania za każdym razem (niezalecane)",
    "✨ Özellikler":
        "✨ Funkcje",
    "GENEL":
        "OGÓLNE",
    "Çeviri/yanıt dili":
        "Język tłumaczenia/odpowiedzi",
    "Şifresiz gönderimde parola/IBAN/kart gibi hassas bilgi uyarısı (yerel)":
        "Ostrzegaj o wrażliwych danych jak hasła/IBAN/karty przy wysyłaniu bez szyfrowania (lokalnie)",
    "ASİSTAN":
        "ASYSTENT",
    "Yazarken satır içi öneri — Tab ile kabul et (yalnız yerel Ollama modeliyle çalışır)":
        "Podpowiedzi podczas pisania — akceptuj klawiszem Tab (tylko z lokalnym modelem Ollama)",
    "Uzaktayken gelen mesajlara yanıt taslağı hazırla (asla gönderilmez; dönüşte gözden geçirirsiniz)":
        "Przygotowuj szkice odpowiedzi na wiadomości otrzymane podczas nieobecności (nigdy nie są wysyłane; przejrzysz je po powrocie)",
    "🎙 Ses":
        "🎙 Głos",
    "SES → METİN":
        "MOWA → TEKST",
    "Whisper modeli":
        "Model Whisper",
    "Gelen sesli mesajları otomatik yazıya dök (yerel, faster-whisper)":
        "Automatycznie transkrybuj przychodzące wiadomości głosowe (lokalnie, faster-whisper)",
    "SESLİ OKUMA":
        "CZYTANIE NA GŁOS",
    "Motor":
        "Silnik",
    "Piper ses modeli":
        "Model głosu Piper",
    "Okuma dili":
        "Język czytania",
    "Motor yoksa: sudo pacman -S espeak-ng · Piper için .onnx ses modelinin tam yolunu girin (ör. tr_TR-dfki-medium.onnx).":
        "Brak silnika: sudo pacman -S espeak-ng · Dla Piper podaj pełną ścieżkę modelu głosu .onnx (np. tr_TR-dfki-medium.onnx).",
    "MCP erişimi: harici AI araçları sohbet geçmişini okuyabilir ve taslak bırakabilir (mesaj gönderemez)":
        "Dostęp MCP: zewnętrzne narzędzia AI mogą czytać historię i zostawiać szkice (nie mogą wysyłać wiadomości)",
    "MCP'ye şifreli mesajların içeriğini de göster (önerilmez)":
        "Pokazuj MCP także treść wiadomości szyfrowanych (niezalecane)",
    "Kayıt komutu (taslak için REST API de açık olmalı):":
        "Polecenie rejestracji (do szkiców musi też działać REST API):",
    "📋 MCP komutu panoya kopyalandı.":
        "📋 Polecenie MCP skopiowano do schowka.",
    "⏳ Test ediliyor…":
        "⏳ Testowanie…",
    "🔌 Bağlantıyı Test Et":
        "🔌 Testuj połączenie",
    "Mesajı İlet":
        "Przekaż wiadomość",
    "İletilecek kişi/oda seçin:":
        "Wybierz odbiorcę:",
    "Kaybolan Mesajlar":
        "Znikające wiadomości",
    "Mesajlar belirli süre sonra\notomatik silinir.":
        "Wiadomości są usuwane automatycznie\npo ustalonym czasie.",
    "30sn":
        "30 s",
    "5dk":
        "5 min",
    "1sa":
        "1 godz.",
    "1gün":
        "1 d",
    "Uygula":
        "Zastosuj",
    "Geçmişi Sil":
        "Usuń historię",
    "🗑 Mesaj Geçmişini Sil":
        "🗑 Usuń historię wiadomości",
    "Toplam: {} mesaj, {} sohbet":
        "Łącznie wiadomości: {}, rozmów: {}",
    "Silindi":
        "Usunięto",
    "Bu sohbetin geçmişi silindi":
        "Historia tej rozmowy została usunięta",
    "Tüm Geçmişi Sil":
        "Usuń całą historię",
    "Tüm sohbet geçmişi silinecek. Emin misiniz?":
        "Cała historia rozmów zostanie usunięta. Na pewno?",
    "🗑 Bu Sohbeti Sil":
        "🗑 Usuń tę rozmowę",
    "⚠ Tüm Geçmişi Sil":
        "⚠ Usuń całą historię",
    "Kişi Grupları":
        "Grupy kontaktów",
    "🏷 Kişi Grupları":
        "🏷 Grupy kontaktów",
    "Henüz grup yok":
        "Nie ma jeszcze grup",
    "Grup Ekle":
        "Dodaj grupę",
    "Grup adı:":
        "Nazwa grupy:",
    "Bilgi":
        "Informacja",
    "Önce bir grup oluşturun":
        "Najpierw utwórz grupę",
    "Gruba Ekle":
        "Dodaj do grupy",
    "Grup:":
        "Grupa:",
    "Ekle":
        "Dodaj",
    "+ Yeni Grup":
        "+ Nowa grupa",
    "+ Kişi Ekle":
        "+ Dodaj kontakt",
    "Yeni Sohbet":
        "Nowa rozmowa",
    "  JID Gir  ":
        "  Wpisz JID  ",
    "Bir XMPP adresi girerek doğrudan sohbet\nbaşlatabilir veya abonelik isteği gönderebilirsiniz.":
        "Wpisz adres XMPP, aby od razu rozpocząć rozmowę\nlub wysłać prośbę o subskrypcję.",
    "JID (XMPP Adresi)":
        "JID (adres XMPP)",
    "  Sohbet Başlat  ":
        "  Rozpocznij rozmowę  ",
    "  Kişi Olarak Ekle  ":
        "  Dodaj jako kontakt  ",
    "  Kişiler  ":
        "  Kontakty  ",
    "Mevcut kişilerinizden birini seçerek\nsohbet başlatabilirsiniz.":
        "Wybierz jeden ze swoich kontaktów,\naby rozpocząć rozmowę.",
    "Filtrele...":
        "Filtruj...",
    "  Kullanıcı Ara  ":
        "  Szukaj użytkowników  ",
    "Sunucuda kullanıcı arayın (XEP-0055).\nTüm sunucular bu özelliği desteklemeyebilir.":
        "Szukaj użytkowników na serwerze (XEP-0055).\nNie każdy serwer to obsługuje.",
    "Sunucu:":
        "Serwer:",
    "Arama:":
        "Szukaj:",
    "İsim veya JID...":
        "Nazwa lub JID...",
    "  Aranıyor…":
        "  Wyszukiwanie…",
    "  Ara  ":
        "  Szukaj  ",
    "🔍  Kullanıcı Ara":
        "🔍  Szukaj użytkowników",
    "Sunucuda kullanıcı arayın (XEP-0055)":
        "Szukaj użytkowników na serwerze (XEP-0055)",
    "Ara":
        "Szukaj",
    "Sohbet Başlat":
        "Rozpocznij rozmowę",
    "Durum Mesajı":
        "Opis statusu",
    "Durum yazın...":
        "Wpisz status...",
    "Konum Paylaş":
        "Udostępnij lokalizację",
    "Açıklama:":
        "Opis:",
    "İstanbul":
        "Stambuł",
    "Geçersiz koordinatlar":
        "Nieprawidłowe współrzędne",
    "Paylaş":
        "Udostępnij",
    "Durdur":
        "Zatrzymaj",
    "Davet Gönder":
        "Wyślij zaproszenie",
    "{} odasına davet edilecek JID:":
        "JID do zaproszenia do {}:",
    "Ortak Gruplar":
        "Wspólne grupy",
    "🏠 {} ile Ortak Gruplar":
        "🏠 Wspólne grupy z {}",
    "  Ortak grup bulunamadı":
        "  Brak wspólnych grup",
    "Bir konferans sunucusu keşfedin veya doğrudan katılın":
        "Odkryj serwer konferencyjny lub dołącz bezpośrednio",
    "🌐  KONFERANS SUNUCUSU":
        "🌐  SERWER KONFERENCYJNY",
    "Odaları Keşfet":
        "Odkrywaj pokoje",
    "🚪  ODA JID (doğrudan katıl)":
        "🚪  JID POKOJU (dołącz bezpośrednio)",
    "👤  TAKMA AD":
        "👤  PSEUDONIM",
    "Katıl":
        "Dołącz",
    "Yeni bir sohbet odası oluşturun":
        "Utwórz nowy pokój rozmów",
    "🏠  ODA ADI":
        "🏠  NAZWA POKOJU",
    "Adres: …@{}":
        "Adres: …@{}",
    "Adres: {}":
        "Adres: {}",
    "🛡  ODA TÜRÜ":
        "🛡  TYP POKOJU",
    "🌐  Normal oda":
        "🌐  Zwykły pokój",
    "Adresi bilen herkes katılabilir, mesajlar şifresizdir.":
        "Każdy, kto zna adres, może dołączyć; wiadomości nie są szyfrowane.",
    "🔒  Şifreli oda (OMEMO)":
        "🔒  Pokój szyfrowany (OMEMO)",
    "Yalnız davet ettikleriniz katılır, mesajlar uçtan uca şifrelenir.":
        "Dołączyć mogą tylko zaproszone osoby; wiadomości są szyfrowane end-to-end.",
    "OMEMO kütüphanesi (slixmpp-omemo) yüklü değil.":
        "Biblioteka OMEMO (slixmpp-omemo) nie jest zainstalowana.",
    "Oluştur ve Katıl":
        "Utwórz i dołącz",
    "📑  Yer İmleri":
        "📑  Zakładki",
    "Mevcut Odayı Ekle":
        "Dodaj bieżący pokój",
    "🗑 Sil":
        "🗑 Usuń",
    "Oda Ayarları — {}":
        "Ustawienia pokoju — {}",
    "Oda Yönetimi — {}":
        "Zarządzanie pokojem — {}",
    "  Üyeler  ":
        "  Członkowie  ",
    "  Ayarlar  ":
        "  Ustawienia  ",
    "Oda Konusu:":
        "Temat pokoju:",
    "Konuyu Güncelle":
        "Zaktualizuj temat",
    "  Davet  ":
        "  Zaproś  ",
    "Davet edilecek JID:":
        "JID do zaproszenia:",
    "{} davet edildi":
        "Zaproszono: {}",
    "📨 Davet Gönder":
        "📨 Wyślij zaproszenie",
    "İsim A→Z":
        "Nazwa A→Z",
    "İsim Z→A":
        "Nazwa Z→A",
    "Adres A→Z":
        "Adres A→Z",
    "Adres Z→A":
        "Adres Z→A",
    "Keşfedilen Odalar":
        "Znalezione pokoje",
    "Oda ara (isim veya adres)...":
        "Szukaj pokoi (nazwa lub adres)...",
    "  (Eşleşen oda bulunamadı)":
        "  (Brak pasujących pokoi)",
    "{}/{} oda":
        "Pokoje: {}/{}",
    "Seçilen Odaya Katıl":
        "Dołącz do wybranego pokoju",
    "  Genel Ara  ":
        "  Wyszukiwanie publiczne  ",
    "Oda adı veya konu ara...":
        "Szukaj nazwy pokoju lub tematu...",
    "Aranıyor…":
        "Wyszukiwanie…",
    "  (Sonuç bulunamadı)":
        "  (Brak wyników)",
    "Yer imine eklendi":
        "Dodano do zakładek",
    "Yer İmine Ekle":
        "Dodaj zakładkę",
    "  Popüler Sunucular  ":
        "  Popularne serwery  ",
    "Bir sunucu seçip 'Keşfet' ile odaları listeleyin.":
        "Wybierz serwer i użyj „Odkryj”, aby wyświetlić jego pokoje.",
    "Seçili Sunucudan Keşfet":
        "Odkryj z wybranego serwera",
    "Sunucu adresi":
        "Adres serwera",
    "  Keşfet  ":
        "  Odkryj  ",
    "  Hesap  ":
        "  Konto  ",
    "PROFİL":
        "PROFIL",
    "Sunucu: {}":
        "Serwer: {}",
    "Profil Fotoğrafı Seç":
        "Wybierz zdjęcie profilowe",
    "Tüm":
        "Wszystkie",
    "Fotoğraf yüklenemedi: {}":
        "Nie udało się wczytać zdjęcia: {}",
    "Fotoğraf Değiştir":
        "Zmień zdjęcie",
    "Kaldır":
        "Usuń",
    "DURUM MESAJI":
        "OPIS STATUSU",
    "GİRİŞ":
        "LOGOWANIE",
    "Açılışta otomatik giriş (formu atla)":
        "Loguj automatycznie przy starcie (pomiń formularz)",
    "ÇOKLU HESAP":
        "WIELE KONT",
    "⇄ Geçiş":
        "⇄ Przełącz",
    "Ek hesap yok":
        "Brak innych kont",
    "Hesap Ekle":
        "Dodaj konto",
    "Şifre:":
        "Hasło:",
    "+ Hesap Ekle":
        "+ Dodaj konto",
    "  Görünüm  ":
        "  Wygląd  ",
    "TEMA":
        "MOTYW",
    "YAZI TİPİ":
        "CZCIONKA",
    "Yazı tipi:":
        "Czcionka:",
    "Boyut:":
        "Rozmiar:",
    "ÖNİZLEME":
        "PODGLĄD",
    "Merhaba! Bu bir önizleme mesajıdır. 🎉":
        "Cześć! To jest wiadomość podglądu. 🎉",
    "DİL":
        "JĘZYK",
    "DÜZEN":
        "UKŁAD",
    "📐 Kompakt mod (mesaj balonları daha sıkışık)":
        "📐 Tryb kompaktowy (ciaśniejsze dymki)",
    "SOHBET ARKA PLANI":
        "TŁO ROZMOWY",
    "(varsayılan)":
        "(domyślne)",
    "Mevcut: {}":
        "Bieżące: {}",
    "🖼 Arka Plan Değiştir…":
        "🖼 Zmień tło…",
    "  Bildirimler  ":
        "  Powiadomienia  ",
    "BİLDİRİMLER":
        "POWIADOMIENIA",
    "Masaüstü bildirimleri göster":
        "Pokazuj powiadomienia pulpitu",
    "Bildirim sesleri çal":
        "Odtwarzaj dźwięki powiadomień",
    "🔊 Sesi Test Et":
        "🔊 Testuj dźwięk",
    "SİSTEM TEPSİSİ":
        "ZASOBNIK SYSTEMOWY",
    "⚫ pystray yüklü değil":
        "⚫ pystray nie jest zainstalowany",
    "Tepsi ikonu: {}":
        "Ikona w zasobniku: {}",
    "Yüklemek için: pip install pystray":
        "Instalacja: pip install pystray",
    "GİZLİLİK":
        "PRYWATNOŚĆ",
    "Okundu bilgisi gönder (XEP-0333)":
        "Wysyłaj potwierdzenia odczytu (XEP-0333)",
    "Yazıyor bildirimi gönder (XEP-0085)":
        "Wysyłaj powiadomienia o pisaniu (XEP-0085)",
    "KAYBOLAN MESAJLAR":
        "ZNIKAJĄCE WIADOMOŚCI",
    "Varsayılan süre (tüm yeni sohbetler için):":
        "Domyślny czas (dla wszystkich nowych rozmów):",
    "30 sn":
        "30 s",
    "5 dk":
        "5 min",
    "1 gün":
        "1 dzień",
    "ENGELLİ KİŞİLER":
        "ZABLOKOWANE KONTAKTY",
    "🚫 Engelli kişileri yönet...":
        "🚫 Zarządzaj zablokowanymi kontaktami...",
    "İndirme klasörü":
        "Folder pobranych",
    "Gelen dosyaları otomatik kabul et":
        "Automatycznie akceptuj przychodzące pliki",
    "IBB blok boyutu":
        "Rozmiar bloku IBB",
    "Büyük dosya uyarı eşiği (MB)":
        "Próg ostrzeżenia dla dużych plików (MB)",
    "  Şifreleme  ":
        "  Szyfrowanie  ",
    "Hazır":
        "Gotowe",
    "Yüklü değil":
        "Niezainstalowane",
    "Başlatılmadı":
        "Nieuruchomione",
    "Cihaz bilgileri yükleniyor…":
        "Wczytywanie informacji o urządzeniu…",
    "Bu Cihaz  (ID: {})":
        "To urządzenie  (ID: {})",
    "Diğer Cihazlar ({})":
        "Inne urządzenia ({})",
    "Başka cihaz bulunamadı":
        "Nie znaleziono innych urządzeń",
    "GPG bulunamadı":
        "Nie znaleziono GPG",
    "Anahtar: {} adet":
        "Klucze: {}",
    "PGP ANAHTAR EŞLEŞTİRME":
        "PRZYPISANIE KLUCZY PGP",
    "JID → GPG Key ID eşleştirmesi":
        "Przypisanie JID → ID klucza GPG",
    "+ Eşleştirme Ekle":
        "+ Dodaj przypisanie",
    "OMEMO QR DOĞRULAMA":
        "WERYFIKACJA QR OMEMO",
    "🔐 QR Kod ile Parmak İzi Doğrula…":
        "🔐 Zweryfikuj odcisk kodem QR…",
    "🟢 qrcode kütüphanesi yüklü":
        "🟢 biblioteka qrcode zainstalowana",
    "⚫ QR için: pip install qrcode[pil]":
        "⚫ Dla QR: pip install qrcode[pil]",
    "VARSAYILAN ŞİFRELEME":
        "DOMYŚLNE SZYFROWANIE",
    "🔓 Kapalı":
        "🔓 Wyłączone",
    "  Bağlantı  ":
        "  Połączenie  ",
    "BAĞLANTI AYARLARI":
        "USTAWIENIA POŁĄCZENIA",
    "Odalara otomatik yeniden katıl":
        "Automatycznie wracaj do pokoi",
    "OTOMATİK UZAKTA":
        "AUTOMATYCZNA NIEOBECNOŚĆ",
    "İşlem yapılmadığında otomatik uzakta durumuna geç:":
        "Automatycznie ustaw „zaraz wracam” po bezczynności:",
    "3 dk":
        "3 min",
    "BAĞLANTI KALİTESİ":
        "JAKOŚĆ POŁĄCZENIA",
    "📶 Bağlantı yok":
        "📶 Brak połączenia",
    "📶 Henüz ölçülmedi":
        "📶 Jeszcze nie zmierzono",
    "KAYITLI ODALAR":
        "ZAPISANE POKOJE",
    "Kayıtlı oda yok":
        "Brak zapisanych pokoi",
    "BAĞLANTI DURUMU":
        "STAN POŁĄCZENIA",
    "Bağlı":
        "Połączono",
    "Bağlı değil":
        "Nie połączono",
    "Hesap: {}":
        "Konto: {}",
    "Kişiler: {}  •  Aktif Odalar: {}":
        "Kontakty: {}  •  Aktywne pokoje: {}",
    "PROXY / ANONİM BAĞLANTI":
        "PROXY / POŁĄCZENIE ANONIMOWE",
    "Yapılandırılmamış":
        "Nieskonfigurowane",
    "Tür: {}":
        "Typ: {}",
    "🔧 Proxy Ayarları…":
        "🔧 Ustawienia proxy…",
    "OTOMATİK TEMA GEÇİŞİ":
        "AUTOMATYCZNA ZMIANA MOTYWU",
    "⚫ Kapalı":
        "⚫ Wyłączone",
    "🌓 Otomatik Tema Ayarları…":
        "🌓 Ustawienia automatycznego motywu…",
    "GÜVENLİK":
        "BEZPIECZEŃSTWO",
    "🔑 Uygulama Kilidi (PIN)…":
        "🔑 Blokada aplikacji (PIN)…",
    "🗑 Mesaj Geçmişini Sil…":
        "🗑 Usuń historię wiadomości…",
    "  Hakkında  ":
        "  O programie  ",
    "deneme.py — Modern Tkinter XMPP İstemcisi":
        "deneme.py — Nowoczesny klient XMPP w Tkinter",
    "KÜTÜPHANELER":
        "BIBLIOTEKI",
    "VERİ":
        "DANE",
    "📤 Sohbetleri Dışa Aktar":
        "📤 Eksportuj rozmowy",
    "📋 Ayarları Kopyala":
        "📋 Kopiuj ustawienia",
    "✓ Kopyalandı":
        "✓ Skopiowano",
    "💾 Yedekleme / Geri Yükleme…":
        "💾 Kopia zapasowa / Przywracanie…",
    "KLAVYE KISAYOLLARI":
        "SKRÓTY KLAWISZOWE",
    "⌨ Kısayolları Göster…":
        "⌨ Pokaż skróty…",
    "Hızlı Geçiş":
        "Szybkie przełączanie",
    "Sohbette Ara":
        "Szukaj w rozmowie",
    "Yedekleme":
        "Kopia zapasowa",
    "  Kaydet ve Kapat  ":
        "  Zapisz i zamknij  ",
    "Klavye Kısayolları":
        "Skróty klawiszowe",
    "Hızlı Geçiş (kişi/oda)":
        "Szybkie przełączanie (kontakt/pokój)",
    "Son mesaja yanıtla":
        "Odpowiedz na ostatnią wiadomość",
    "Son mesajımı düzenle":
        "Edytuj moją ostatnią wiadomość",
    "Son mesajımı sil":
        "Usuń moją ostatnią wiadomość",
    "✨ Neler kaçırdım? (AI özeti)":
        "✨ Co mnie ominęło? (podsumowanie AI)",
    "✨ Geçmişe sor (AI)":
        "✨ Zapytaj historię (AI)",
    "✨ Sesle yaz (dikte)":
        "✨ Dyktowanie",
    "Üzerine gel":
        "Najechanie",
    "Eylem butonları (yanıtla/tepki/… )":
        "Przyciski akcji (odpowiedz/reaguj/… )",
    "Çift tık":
        "Dwuklik",
    "Mesajı yanıtla (alıntı)":
        "Odpowiedz na wiadomość (cytat)",
    "Tepkiye tıkla":
        "Kliknij reakcję",
    "Tepkini ekle / kaldır":
        "Dodaj / usuń swoją reakcję",
    "Bu menü":
        "To menu",
    "Aramayı kapat":
        "Zamknij wyszukiwanie",
    "Mesaj gönder":
        "Wyślij wiadomość",
    "Yapıştır (resim/metin)":
        "Wklej (obraz/tekst)",
    "Tepkiler":
        "Reakcje",
    "😊 Tepkiler":
        "😊 Reakcje",
    "(tepki yok)":
        "(brak reakcji)",
    "📖 Hikaye / Durum Paylaş":
        "📖 Udostępnij relację / status",
    "METİN DURUMU":
        "STATUS TEKSTOWY",
    "RUHSAL DURUM":
        "NASTRÓJ",
    "😊 Mutlu":
        "😊 Szczęśliwy",
    "😔 Üzgün":
        "😔 Smutny",
    "😡 Kızgın":
        "😡 Zły",
    "😴 Uykulu":
        "😴 Śpiący",
    "🤔 Düşünceli":
        "🤔 Zamyślony",
    "🎉 Heyecanlı":
        "🎉 Podekscytowany",
    "FOTOĞRAF":
        "ZDJĘCIE",
    "Seçilmedi":
        "Nic nie wybrano",
    "📷 Fotoğraf Seç":
        "📷 Wybierz zdjęcie",
    "📤 Yayınla":
        "📤 Opublikuj",
    "Profil Fotoğrafı":
        "Zdjęcie profilowe",
    "Fotoğrafınızı değiştirin veya kaldırın":
        "Zmień lub usuń swoje zdjęcie",
    "✓ Güncellendi":
        "✓ Zaktualizowano",
    "⚠ Yayınlanamadı — eski fotoğraf korundu":
        "⚠ Nie udało się opublikować — zachowano poprzednie zdjęcie",
    "Pillow Gerekli":
        "Wymagany Pillow",
    "Fotoğraf desteği için Pillow gerekli:\npip install Pillow":
        "Obsługa zdjęć wymaga biblioteki Pillow:\npip install Pillow",
    "Fotoğraf Seç":
        "Wybierz zdjęcie",
    "Resim Dosyaları":
        "Pliki obrazów",
    "Tüm Dosyalar":
        "Wszystkie pliki",
    "✓ Kaldırıldı":
        "✓ Usunięto",
    "📷  Fotoğraf Seç":
        "📷  Wybierz zdjęcie",
    "  📝 Konu Değiştir":
        "  📝 Zmień temat",
    "  📨 Davet Gönder":
        "  📨 Wyślij zaproszenie",
    "  ⚙ Oda Ayarları":
        "  ⚙ Ustawienia pokoju",
    "  🚪 Odayı Terk Et":
        "  🚪 Opuść pokój",
    "  💣 Odayı Sil":
        "  💣 Usuń pokój",
    "  Yetki: {}":
        "  Przynależność: {}",
    "  Rol: {}":
        "  Rola: {}",
    "  💬 Özel Mesaj":
        "  💬 Wiadomość prywatna",
    "  👢 At (Kick)":
        "  👢 Wyrzuć",
    "  🔇 Sustur":
        "  🔇 Wycisz",
    "  🔊 Konuşmaya İzin Ver":
        "  🔊 Pozwól mówić",
    "  ⚔ Moderatör Yap":
        "  ⚔ Nadaj moderatora",
    "  ⚔ Moderatörlüğü Al":
        "  ⚔ Odbierz moderatora",
    "  🚫 Yasakla (Ban)":
        "  🚫 Zbanuj",
    "  🛡 Yönetici Yap":
        "  🛡 Nadaj administratora",
    "  👤 Üye Yap":
        "  👤 Nadaj członkostwo",
    "  ↓ Yetkiyi Kaldır":
        "  ↓ Usuń przynależność",
    "↑/↓ seç · Enter aç · Esc kapat":
        "↑/↓ wybierz · Enter otwórz · Esc zamknij",
    "Eşleşen sohbet bulunamadı":
        "Brak pasujących rozmów",
    "  Sohbet Başlat":
        "  Rozpocznij rozmowę",
    "📌 Sabitlemeyi Kaldır":
        "📌 Odepnij",
    "📌 Sohbeti Sabitle":
        "📌 Przypnij rozmowę",
    "🏠 Ortak Gruplar":
        "🏠 Wspólne grupy",
    "  Kişiyi Kaldır":
        "  Usuń kontakt",
    "KATILIMCILAR — {}":
        "UCZESTNICY — {}",
    "Çevrimdışı":
        "Niedostępny",
    "Ortak grup: {}":
        "Wspólne grupy: {}",
    "özel":
        "prywatny",
    "⚠ Değişiklikler kaybolacak — kapatmak için yine dışarı tıkla":
        "⚠ Zmiany zostaną utracone — kliknij ponownie poza oknem, aby zamknąć",
    "KİŞİLER":
        "KONTAKTY",
    "Kullanıcı Ara":
        "Szukaj użytkowników",
    "ODALAR":
        "POKOJE",
    "GELİŞMİŞ":
        "ZAAWANSOWANE",
    "Mesaj Ara":
        "Szukaj wiadomości",
    "Yeniden Bağlan":
        "Połącz ponownie",
    "Ayarlar":
        "Ustawienia",
    "⏱ Kaybolan Mesajlar":
        "⏱ Znikające wiadomości",
    "📜 Daha Eski Mesajları Yükle (MAM)":
        "📜 Wczytaj starsze wiadomości (MAM)",
    "⏰ Mesaj Zamanla":
        "⏰ Zaplanuj wiadomość",
    "📤 Sohbeti Dışa Aktar":
        "📤 Eksportuj rozmowę",
    "🗑 Geçmişi Sil":
        "🗑 Usuń historię",
    "🔧 Oda Yönetimi":
        "🔧 Zarządzanie pokojem",
    "👤 Profil":
        "👤 Profil",
    "🔎 Mesaj Ara":
        "🔎 Szukaj wiadomości",
    "📌 Sabitlenmiş Mesajlar":
        "📌 Przypięte wiadomości",
    "💬 Sohbet":
        "💬 Rozmowa",
    "📤 Paylaşım":
        "📤 Udostępnianie",
    "📍 Konum Paylaş":
        "📍 Udostępnij lokalizację",
    "📖 Hikaye Paylaş":
        "📖 Udostępnij relację",
    "📢 Toplu Mesaj":
        "📢 Wiadomość zbiorcza",
    "🔒 Güvenlik":
        "🔒 Bezpieczeństwo",
    "🔒 OMEMO Parmak İzleri":
        "🔒 Odciski OMEMO",
    "🔐 OMEMO QR Doğrulama":
        "🔐 Weryfikacja QR OMEMO",
    "🚫 Engelli Kişiler":
        "🚫 Zablokowane kontakty",
    "🪟 Görünüm":
        "🪟 Widok",
    "📺 Yeni Sekmede Aç":
        "📺 Otwórz w nowej karcie",
    "📺 Bölünmüş Ekran":
        "📺 Podzielony ekran",
    "🖼 Arka Plan Değiştir":
        "🖼 Zmień tło",
    "📐 Rahat Moda Geç":
        "📐 Przełącz na tryb wygodny",
    "📐 Kompakt Moda Geç":
        "📐 Przełącz na tryb kompaktowy",
    "⚙ Diğer":
        "⚙ Więcej",
    "💬 Durum Mesajı":
        "💬 Opis statusu",
    "💾 Yedekleme / Geri Yükleme":
        "💾 Kopia zapasowa / Przywracanie",
    "⌨ Klavye Kısayolları":
        "⌨ Skróty klawiszowe",
    "Yüzler":
        "Twarze",
    "El":
        "Dłonie",
    "Kalp":
        "Serca",
    "Nesne":
        "Przedmioty",
    "Yiyecek":
        "Jedzenie",
    "Doğa":
        "Natura",
    "Bugün":
        "Dzisiaj",
    "⚠ OMEMO plugin kaydı başarısız: {}":
        "⚠ Rejestracja wtyczki OMEMO nie powiodła się: {}",
    "⚠ OMEMO başlatma zaman aşımına uğradı. Sunucu PEP/PubSub desteklemeyebilir.":
        "⚠ Przekroczono czas uruchamiania OMEMO. Serwer może nie obsługiwać PEP/PubSub.",
    "⚠ OMEMO başlatma hatası: {}":
        "⚠ Błąd uruchamiania OMEMO: {}",
    "🔐 OMEMO şifreleme hazır":
        "🔐 Szyfrowanie OMEMO gotowe",
    "⚠ OMEMO çözme hatası: {}":
        "⚠ Błąd odszyfrowania OMEMO: {}",
    "⚠ PGP mesajı çözülemedi (anahtar eksik?)":
        "⚠ Nie udało się odszyfrować wiadomości PGP (brak klucza?)",
    "⚠ PGP çözme hatası: {}":
        "⚠ Błąd odszyfrowania PGP: {}",
    "🔑 PGP anahtar ayarlandı (config)":
        "🔑 Ustawiono klucz PGP (konfiguracja)",
    "🔑 PGP anahtar otomatik eşleştirildi: {}":
        "🔑 Automatycznie przypisano klucz PGP: {}",
    "🔑 PGP: tek secret key kullanılıyor: {}":
        "🔑 PGP: używany jest jedyny klucz prywatny: {}",
    "Sunucuya bağlandı, oturum açılıyor…":
        "Połączono z serwerem, logowanie…",
    "Giriş başarısız: JID veya şifre yanlış.":
        "Logowanie nieudane: błędny JID lub hasło.",
    "⟳ {}s sonra yeniden bağlanılıyor…":
        "⟳ Ponowne łączenie za {} s…",
    "PGP: {} için GPG anahtarı bulunamadı. Ayarlar → Şifreleme'den anahtar eşleştirin.":
        "PGP: nie znaleziono klucza GPG dla {}. Przypisz klucz w Ustawienia → Szyfrowanie.",
    "PGP şifreleme başarısız: {}":
        "Szyfrowanie PGP nie powiodło się: {}",
    "PGP: Şifreli veri çıkarılamadı":
        "PGP: nie udało się wyodrębnić zaszyfrowanych danych",
    "PGP gönderme hatası: {}":
        "Błąd wysyłania PGP: {}",
    "OMEMO: Oda üyelerinin JID'leri alınamadı (oda anonim olabilir). Şifreli dosya bağlantısı şifresiz GÖNDERİLMEDİ.":
        "OMEMO: nie udało się pobrać JID-ów członków pokoju (pokój może być anonimowy). Link do zaszyfrowanego pliku NIE został wysłany bez szyfrowania.",
    "OMEMO: Oda üyelerinin JID'leri alınamadı (oda anonim olabilir). Düz metin gönderiliyor.":
        "OMEMO: nie udało się pobrać JID-ów członków pokoju (pokój może być anonimowy). Wysyłanie zwykłego tekstu.",
    "OMEMO: Alıcının cihaz bilgileri alınamadı.\nKarşı tarafın OMEMO destekli bir istemci kullanması gerekiyor.\nDetay: {}":
        "OMEMO: nie udało się pobrać informacji o urządzeniach odbiorcy.\nDruga strona potrzebuje klienta obsługującego OMEMO.\nSzczegóły: {}",
    "OMEMO şifreleme hatası: {}":
        "Błąd szyfrowania OMEMO: {}",
    "⚠ OMEMO uyarı: {}":
        "⚠ Ostrzeżenie OMEMO: {}",
    "OMEMO şifreleme başarısız — şifreli dosya bağlantısı şifresiz GÖNDERİLMEDİ.":
        "Szyfrowanie OMEMO nie powiodło się — link do zaszyfrowanego pliku NIE został wysłany bez szyfrowania.",
    "OMEMO şifreleme başarısız — düz metin gönderiliyor":
        "Szyfrowanie OMEMO nie powiodło się — wysyłanie zwykłego tekstu",
    "✓ Profil fotoğrafı güncellendi":
        "✓ Zaktualizowano zdjęcie profilowe",
    "⚠ Avatar yayınlanamadı: {}":
        "⚠ Nie udało się opublikować awatara: {}",
    "İstek gönderildi → {}":
        "Wysłano prośbę → {}",
    "Kişi eklenemedi: {}":
        "Nie udało się dodać kontaktu: {}",
    "✓ Kişi kaldırıldı: {}":
        "✓ Usunięto kontakt: {}",
    "Kişi kaldırılamadı: {}":
        "Nie udało się usunąć kontaktu: {}",
    "Engelleme hatası: {}":
        "Błąd blokowania: {}",
    "✓ {} engeli kaldırıldı":
        "✓ Odblokowano: {}",
    "Engel kaldırma hatası: {}":
        "Błąd odblokowania: {}",
    "Engel listesi hatası: {}":
        "Błąd listy blokowanych: {}",
    "📍 Konum paylaşıldı":
        "📍 Udostępniono lokalizację",
    "Konum paylaşma hatası: {}":
        "Błąd udostępniania lokalizacji: {}",
    "Ruh hâli paylaşılamadı: {}":
        "Nie udało się udostępnić nastroju: {}",
    "📍 Konum paylaşımı durduruldu":
        "📍 Zatrzymano udostępnianie lokalizacji",
    "Konum durdurma hatası: {}":
        "Błąd zatrzymywania lokalizacji: {}",
    "XMPP Giriş":
        "Logowanie XMPP",
    "Hesabınıza giriş yapın":
        "Zaloguj się na swoje konto",
    "Şifre":
        "Hasło",
    "Gelişmiş":
        "Zaawansowane",
    "Otomatik giriş":
        "Automatyczne logowanie",
    "Şifremi hatırla":
        "Zapamiętaj hasło",
    "Sunucu (boş = SRV)":
        "Serwer (puste = SRV)",
    "SRV otomatik  •  OMEMO & PGP destekli":
        "SRV automatycznie  •  Obsługa OMEMO i PGP",
    "Bağlan":
        "Połącz",
    "Eksik Bilgi":
        "Brakujące dane",
    "JID ve şifre gerekli.":
        "Wymagane są JID i hasło.",
    "Geçersiz JID":
        "Nieprawidłowy JID",
    "JID formatı: kullanıcı@sunucu.tld":
        "Format JID: uzytkownik@serwer.tld",
    "Kişi veya oda ara...":
        "Szukaj kontaktów lub pokoi...",
    "Kişi Ekle":
        "Dodaj kontakt",
    "Gruplar":
        "Grupy",
    "Komut ver ya da soru sor · Ctrl+Shift+K":
        "Wydaj polecenie lub zadaj pytanie · Ctrl+Shift+K",
    "Oda Keşfet":
        "Odkrywaj pokoje",
    "Yer İmleri":
        "Zakładki",
    "Odaya Katıl":
        "Dołącz do pokoju",
    "Ana Menü":
        "Menu główne",
    "＋  Yeni Sohbet":
        "＋  Nowa rozmowa",
    "✓ Bağlantı":
        "✓ Połączenie",
    "Zaten bağlısınız":
        "Już jesteś połączony",
    "Bağlantı":
        "Połączenie",
    "Deneme başlatılamadı: {}":
        "Nie udało się rozpocząć próby: {}",
    "⟳ Yeniden bağlanılıyor…":
        "⟳ Ponowne łączenie…",
    "Bağlanıyor…":
        "Łączenie…",
    "KATILIMCILAR":
        "UCZESTNICY",
    "🔒 Şifreli dosya (OMEMO)":
        "🔒 Zaszyfrowany plik (OMEMO)",
    "⬇ İndir ve aç":
        "⬇ Pobierz i otwórz",
    "📂 Klasörde göster":
        "📂 Pokaż w folderze",
    "Alıntılanan mesaja git":
        "Przejdź do cytowanej wiadomości",
    "Yanıtla":
        "Odpowiedz",
    "Tepki ekle":
        "Dodaj reakcję",
    "Tepkileri gör":
        "Zobacz reakcje",
    "AI: çevir / yazıya dök / açıkla":
        "AI: tłumacz / transkrybuj / opisz",
    "Kopyala":
        "Kopiuj",
    "İlet":
        "Przekaż",
    "Sabitle":
        "Przypnij",
    "Düzenle":
        "Edytuj",
    "Sil":
        "Usuń",
    "⚠ Şifreli dosya açılamadı":
        "⚠ Nie udało się otworzyć zaszyfrowanego pliku",
    "📥 Şifreli dosya":
        "📥 Zaszyfrowany plik",
    "Aç":
        "Otwórz",
    "Klasörü Aç":
        "Otwórz folder",
    "🔗 {n} görsel bağlantısı daha":
        "🔗 Więcej linków do obrazów: {n}",
    "🎤 {n} ses bağlantısı daha":
        "🎤 Więcej linków do dźwięku: {n}",
    "Görsel bağlantıları":
        "Linki do obrazów",
    "Ses bağlantıları":
        "Linki do dźwięku",
    "{} — {} bağlantı":
        "{} — linki: {}",
    "Sayfa {}/{}":
        "Strona {}/{}",
    "◀ Önceki":
        "◀ Poprzednia",
    "Sonraki ▶":
        "Następna ▶",
    "🔗 Tarayıcıda Aç":
        "🔗 Otwórz w przeglądarce",
    "↪ Alıntılanan mesaj uygulamada bulunamadı":
        "↪ Nie znaleziono cytowanej wiadomości w aplikacji",
    "Mesajı Düzenle":
        "Edytuj wiadomość",
    "Yeni metin:":
        "Nowy tekst:",
    "Mesajı Sil":
        "Usuń wiadomość",
    "Bu mesajı silmek istediğinizden emin misiniz?":
        "Czy na pewno usunąć tę wiadomość?",
    "↩ Bu mesaj yanıtlanamıyor (kimlik yok)":
        "↩ Nie można odpowiedzieć na tę wiadomość (brak ID)",
    "Bu mesaj şifreli içerik taşıyor ama seçtiğiniz sohbet şifresiz: içerik (şifreli dosyanın anahtarı dahil) sunucuya açık metin gider. Yine de iletilsin mi?":
        "Ta wiadomość zawiera zaszyfrowaną treść, a wybrana rozmowa nie jest szyfrowana: treść (łącznie z kluczem zaszyfrowanego pliku) trafi na serwer jako zwykły tekst. Mimo to przekazać?",
    "Sabitlenmiş Mesajlar":
        "Przypięte wiadomości",
    "Şifreli Sohbet":
        "Rozmowa szyfrowana",
    "{}\n\nYalnız bu istek için içerik Claude'a (bulut) gönderilsin mi?\nHayır derseniz hiçbir şey gönderilmez.":
        "{}\n\nWysłać treść do Claude (chmura) tylko dla tego żądania?\nJeśli wybierzesz Nie, nic nie zostanie wysłane.",
    "{}\n\nAI Ayarları açılsın mı?":
        "{}\n\nOtworzyć ustawienia AI?",
    "Beklenmeyen hata: {}":
        "Nieoczekiwany błąd: {}",
    "{}\n\n{} kaynağın {} tanesi şifreli.\n\nEvet: şifreli içerik de yalnız bu istek için Claude'a (bulut) gönderilsin.\nHayır: şifreli içerik çıkarılsın, yalnız kalanı gönderilsin.\nİptal: hiçbir şey gönderilmesin.":
        "{}\n\nŹródła: {}, w tym zaszyfrowane: {}.\n\nTak: wyślij do Claude (chmura) także zaszyfrowaną treść, tylko dla tego żądania.\nNie: pomiń zaszyfrowaną treść i wyślij resztę.\nAnuluj: nie wysyłaj niczego.",
    "✨ Asistan…":
        "✨ Asystent…",
    "📬 Okunmamışları özetle ({})":
        "📬 Podsumuj nieprzeczytane ({})",
    "📝 Sohbeti özetle":
        "📝 Podsumuj rozmowę",
    "📅 Görev ve etkinlikleri çıkar":
        "📅 Wyodrębnij zadania i wydarzenia",
    "💬 Bu sohbet":
        "💬 Ta rozmowa",
    "❓ Yanıt bekleyen sorular":
        "❓ Pytania bez odpowiedzi",
    "✍ Yanıt taslakları":
        "✍ Szkice odpowiedzi",
    "🔎 Geçmişe sor…":
        "🔎 Zapytaj historię…",
    "🧠 Anlamsal arama…":
        "🧠 Wyszukiwanie semantyczne…",
    "🗂 Tüm sohbetler":
        "🗂 Wszystkie rozmowy",
    "⚙ AI Ayarları…":
        "⚙ Ustawienia AI…",
    "💡 Yanıt öner":
        "💡 Zaproponuj odpowiedź",
    "✨ Asistan (bu sohbet)…":
        "✨ Asystent (ta rozmowa)…",
    "⏹ Dikteyi bitir":
        "⏹ Zakończ dyktowanie",
    "🎙 Sesle yaz (dikte)":
        "🎙 Dyktowanie",
    "⏹ Sesli okumayı durdur":
        "⏹ Zatrzymaj czytanie",
    "✍ Taslağı düzenle":
        "✍ Edytuj szkic",
    "↶ AI değişikliğini geri al":
        "↶ Cofnij zmianę AI",
    "🌐 Çeviri":
        "🌐 Tłumaczenie",
    "Örn: Bu ifade ne anlama geliyor?":
        "Np.: Co oznacza to wyrażenie?",
    "🎙 Ses kaydının metni":
        "🎙 Transkrypcja nagrania",
    "🖥 Yerel (faster-whisper) · {}":
        "🖥 Lokalnie (faster-whisper) · {}",
    "Yazıya dökülüyor… (ilk kullanımda model indirilir)":
        "Transkrypcja… (model jest pobierany przy pierwszym użyciu)",
    "🎙 Otomatik ses→metin durdu":
        "🎙 Automatyczna transkrypcja zatrzymana",
    "faster-whisper/model yok — AI Ayarları → Test Et":
        "Brak faster-whisper/modelu — Ustawienia AI → Testuj",
    "Görsel çok büyük.":
        "Obraz jest za duży.",
    "Görsele Soru Sor":
        "Zapytaj o obraz",
    "Görsel hakkında ne sormak istiyorsunuz?":
        "O co chcesz zapytać w sprawie obrazu?",
    "🖼 Görsel açıklaması":
        "🖼 Opis obrazu",
    "Örn: Arka planda ne yazıyor?":
        "Np.: Co jest napisane w tle?",
    "Özet":
        "Podsumowanie",
    "Özetlenecek mesaj yok.":
        "Brak wiadomości do podsumowania.",
    "📝 {} — okunmamış {} mesajın özeti":
        "📝 {} — podsumowanie nieprzeczytanych (liczba: {})",
    "📝 {} — sohbet özeti":
        "📝 {} — podsumowanie rozmowy",
    "{} · son {} mesaj":
        "{} · ostatnie wiadomości: {}",
    "Örn: Benden ne isteniyor? Saat kaçta buluşuyoruz?":
        "Np.: O co mnie proszą? O której się spotykamy?",
    "Neler kaçırdım?":
        "Co mnie ominęło?",
    "Okunmamış mesaj yok — her şey okunmuş. 🎉":
        "Brak nieprzeczytanych wiadomości — wszystko przeczytane. 🎉",
    "Okunmamışlar arasında özetlenecek metin mesajı yok.":
        "Wśród nieprzeczytanych nie ma wiadomości tekstowych do podsumowania.",
    "📥 Neler kaçırdım?":
        "📥 Co mnie ominęło?",
    "{} · {} sohbet, {} okunmamış mesaj":
        "{} · rozmowy: {}, nieprzeczytane: {}",
    "Örn: Bana kim soru sordu?":
        "Np.: Kto zadał mi pytanie?",
    "Sohbete git":
        "Przejdź do rozmowy",
    "Ali'ye yarın 10'da toplantı olduğunu yaz":
        "Napisz Alemu, że jutro o 10 mamy spotkanie",
    "Yarın 09:00'da faturayı ödemeyi hatırlat":
        "Przypomnij mi jutro o 09:00, żebym zapłacił rachunek",
    "Geçmişe sor: Ali'nin verdiği adres neydi?":
        "Zapytaj historię: Jaki adres podał Ali?",
    "Ayşe ile sohbeti özetle":
        "Podsumuj rozmowę z Ayşe",
    "Durumumu meşgul yap":
        "Ustaw mój status na zajęty",
    "💬 Bağlam: {} — \"bu sohbet\" ya da ad yazmadan verilen komutlar bu sohbete":
        "💬 Kontekst: {} — polecenia mówiące „ta rozmowa” lub bez nazwy trafiają do tej rozmowy",
    "Açık sohbet yok — komutlarda kişi ya da oda adını yazın":
        "Brak otwartej rozmowy — w poleceniach podaj kontakt lub pokój",
    "{} · kişi listeniz modele gönderilmez; gönderme ve değişiklikler onayınızla yapılır":
        "{} · Twoja lista kontaktów nie jest wysyłana do modelu; wysyłanie i zmiany wymagają Twojej zgody",
    "Düşünüyor…":
        "Myślę…",
    "“{}” adında bir kişi ya da oda bulunamadı.":
        "Nie znaleziono kontaktu ani pokoju o nazwie „{}”.",
    "“{}” birden çok kişiyle eşleşti":
        "„{}” pasuje do więcej niż jednego kontaktu",
    "✓ Onayla":
        "✓ Zatwierdź",
    "✗ İptal":
        "✗ Anuluj",
    "✓ Seçildi":
        "✓ Wybrano",
    "✓ {} sohbeti açıldı.":
        "✓ Otwarto rozmowę z {}.",
    "✓ Taslak giriş kutusuna kondu — kontrol edip siz gönderin.":
        "✓ Szkic jest w polu wpisywania — sprawdź i wyślij samodzielnie.",
    "⚠ Oda adresi geçersiz.":
        "⚠ Adres pokoju jest nieprawidłowy.",
    "✓ {} odasına katılma isteği gönderildi.":
        "✓ Wysłano prośbę o dołączenie do {}.",
    "✓ Durum: {}":
        "✓ Status: {}",
    "✓ İlgili pencere açıldı.":
        "✓ Otwarto odpowiednie okno.",
    "⚠ Bu eylem desteklenmiyor.":
        "⚠ Ta czynność nie jest obsługiwana.",
    "⚠ Sunucuya bağlı değilsiniz.":
        "⚠ Nie masz połączenia z serwerem.",
    "⚠ “/” ile başlayan metin komut sayılır; gönderilmedi.":
        "⚠ Tekst zaczynający się od „/” jest poleceniem; nie został wysłany.",
    "✓ {} kişisine gönderildi.":
        "✓ Wysłano do {}.",
    "Gönderilmedi (uyarıda vazgeçildi).":
        "Nie wysłano (anulowano przy ostrzeżeniu).",
    "Sohbette metin mesajı yok.":
        "W rozmowie nie ma wiadomości tekstowych.",
    "Model öneri üretemedi.":
        "Model nie zdołał zaproponować odpowiedzi.",
    "📝 Taslak alınamadı":
        "📝 Nie udało się przygotować szkicu",
    "Taslak kutusu dolu — önce birkaçını kaldırın":
        "Skrzynka szkiców jest pełna — najpierw usuń kilka",
    "📝 Yeni yanıt taslağı":
        "📝 Nowy szkic odpowiedzi",
    "📝 Uzaktayken gelenler":
        "📝 Podczas Twojej nieobecności",
    "{} sohbet için yanıt taslağı — Ctrl+Shift+R":
        "Szkice odpowiedzi dla rozmów: {} — Ctrl+Shift+R",
    "🌙 Uzaktayken":
        "🌙 Podczas nieobecności",
    "🔊 Sesli okuma":
        "🔊 Czytanie na głos",
    "🔊 Sesli okuma başarısız":
        "🔊 Czytanie na głos nie powiodło się",
    "{} çalışmadı":
        "{} nie zadziałało",
    "⚠ Hassas bilgi":
        "⚠ Dane wrażliwe",
    "Tespit bu bilgisayarda yapılır; hiçbir içerik dışarı gönderilmez.":
        "Wykrywanie odbywa się na tym komputerze; żadna treść nie jest wysyłana.",
    "Taranıyor…":
        "Skanowanie…",
    "{} sohbette soru yanıt bekliyor — Ctrl+Shift+Q":
        "Rozmowy z pytaniami czekającymi na odpowiedź: {} — Ctrl+Shift+Q",
    "Görevler ve Etkinlikler":
        "Zadania i wydarzenia",
    "Bu sohbette henüz mesaj yok.":
        "W tej rozmowie nie ma jeszcze wiadomości.",
    "📅 {} — görevler ve etkinlikler":
        "📅 {} — zadania i wydarzenia",
    "Sohbet inceleniyor…":
        "Przeglądanie rozmowy…",
    "Kaydedilecek öğe yok.":
        "Nie ma nic do zapisania.",
    "Takvim dosyasını kaydet":
        "Zapisz plik kalendarza",
    "Tüm dosyalar":
        "Wszystkie pliki",
    "⚠ Dosya yazılamadı: {}":
        "⚠ Nie udało się zapisać pliku: {}",
    "✓ {} öğe kaydedildi: {} — takvim uygulamanızla açabilirsiniz.":
        "✓ Zapisane elementy: {} — {} — możesz otworzyć plik w aplikacji kalendarza.",
    "Hatırlatıcı için seçili öğelerde ileri bir tarih ve saat olmalı.":
        "Do przypomnienia wybrane elementy muszą mieć przyszłą datę i godzinę.",
    "⏰ {} hatırlatıcı kuruldu.":
        "⏰ Ustawione przypomnienia: {}.",
    " {} öğede ileri tarih/saat olmadığı için kurulmadı.":
        " Pominięte elementy bez przyszłej daty/godziny: {}.",
    "  — zamanı geçti":
        "  — termin minął",
    "⏰ Hatırlatıcı":
        "⏰ Przypomnienie",
    "Yanıt Öner":
        "Zaproponuj odpowiedź",
    "💡 Yanıt önerileri":
        "💡 Propozycje odpowiedzi",
    "AI Asistanı":
        "Asystent AI",
    "Önce giriş kutusuna bir mesaj yazın.":
        "Najpierw wpisz wiadomość w pole wpisywania.",
    "Sesle Yaz":
        "Dyktowanie",
    "Mikrofon için PyAudio gerekli:\n  .venv-xmpp/bin/python -m pip install pyaudio":
        "Mikrofon wymaga PyAudio:\n  .venv-xmpp/bin/python -m pip install pyaudio",
    "Ses→metin için faster-whisper gerekli (yerel çalışır):\n  .venv-xmpp/bin/python -m pip install faster-whisper":
        "Zamiana mowy na tekst wymaga faster-whisper (działa lokalnie):\n  .venv-xmpp/bin/python -m pip install faster-whisper",
    "Uygulama kapanıyor.":
        "Aplikacja się zamyka.",
    "Konuşma algılanmadı.":
        "Nie wykryto mowy.",
    "🎙 Dikte":
        "🎙 Dyktowanie",
    "✍ Taslağa koy":
        "✍ Wstaw do szkicu",
    "✓ Sohbet değiştiği için burada gösteriliyor":
        "✓ Wyświetlono tutaj, bo zmieniła się rozmowa",
    "🖥 Yerel gömme · {} — mesajlar bilgisayardan çıkmaz":
        "🖥 Lokalne embeddingi · {} — wiadomości nigdy nie opuszczają Twojego komputera",
    "⏳ İndeksleme zaten sürüyor…":
        "⏳ Indeksowanie już trwa…",
    "⏳ Mesajlar indeksleniyor: {}/{} (arama şimdiden çalışır)":
        "⏳ Indeksowanie wiadomości: {}/{} (wyszukiwanie już działa)",
    "✓ {} yeni mesaj indekslendi.":
        "✓ Zindeksowano nowe wiadomości: {}.",
    "✓ İndeks güncel.":
        "✓ Indeks jest aktualny.",
    "⏳ İndeks kontrol ediliyor…":
        "⏳ Sprawdzanie indeksu…",
    "İptal edildi.":
        "Anulowano.",
    "Gömmeler veritabanına yazılamadı.":
        "Nie udało się zapisać embeddingów w bazie danych.",
    "⏳ Aranıyor…":
        "⏳ Wyszukiwanie…",
    "{} sonuç — açmak için çift tıklayın":
        "Wyniki: {} — kliknij dwukrotnie, aby otworzyć",
    "Eşleşen mesaj bulunamadı.":
        "Nie znaleziono pasujących wiadomości.",
    "🔎 Geçmişe sor":
        "🔎 Zapytaj historię",
    "{} · arama yerel ({})":
        "{} · wyszukiwanie lokalne ({})",
    "Örn: Ali'nin verdiği adres neydi?":
        "Np.: Jaki adres podał Ali?",
    "Sorunuzu aşağıya yazın: ilgili mesajlar bu bilgisayarda bulunur, yanıt kaynaklarıyla gelir.":
        "Wpisz pytanie poniżej: powiązane wiadomości są wyszukiwane na tym komputerze, a odpowiedź podaje źródła.",
    "İlgili mesajlar aranıyor…":
        "Szukanie powiązanych wiadomości…",
    "Mesajlar indeksleniyor: {}/{}…":
        "Indeksowanie wiadomości: {}/{}…",
    "Bu soruyla ilgili bir mesaj bulunamadı. Farklı kelimelerle sormayı deneyin.":
        "Nie znaleziono wiadomości związanych z tym pytaniem. Spróbuj innymi słowami.",
    "Eşleşme yok":
        "Brak dopasowań",
    "Gönderilmedi.":
        "Nie wysłano.",
    "İptal edildi — hiçbir şey gönderilmedi.":
        "Anulowano — nic nie wysłano.",
    "Eşleşen mesajlar gönderilebilecek metin içermiyor (yalnız medya ya da şifreli içerik).":
        "Znalezione wiadomości nie zawierają tekstu, który można wysłać (tylko media lub treść zaszyfrowana).",
    "Kaynaklar":
        "Źródła",
    "İlgili mesajlar":
        "Powiązane wiadomości",
    "Yanıt hazırlanıyor…":
        "Przygotowywanie odpowiedzi…",
    "AI kapalı — test edilecek sağlayıcı yok.":
        "AI jest wyłączone — brak dostawcy do przetestowania.",
    "✓ Ollama çalışıyor; modeller hazır.":
        "✓ Ollama działa; modele są gotowe.",
    "✗ Ollama çalışıyor ama eksik model var: ":
        "✗ Ollama działa, ale brakuje modeli: ",
    "✓ Claude erişilebilir ({}).":
        "✓ Claude jest dostępny ({}).",
    "✓ faster-whisper kurulu (ses→metin).":
        "✓ faster-whisper jest zainstalowany (mowa → tekst).",
    "✗ Ses→metin için: .venv-xmpp/bin/python -m pip install faster-whisper":
        "✗ Dla mowy → tekst: .venv-xmpp/bin/python -m pip install faster-whisper",
    "✓ MCP erişimi açık; REST API çalışıyor (taslak bırakılabilir).":
        "✓ Dostęp MCP jest włączony; REST API działa (można zostawiać szkice).",
    "ℹ MCP erişimi açık; taslak bırakmak için REST API'yi de açın.":
        "ℹ Dostęp MCP jest włączony; włącz też REST API, aby zostawiać szkice.",
    "Engelli Kişiler":
        "Zablokowane kontakty",
    "Engelle":
        "Zablokuj",
    "Engeli Kaldır":
        "Odblokuj",
    "Yeni Engelle":
        "Nowa blokada",
    "Profil — {}":
        "Profil — {}",
    "vCard bilgileri yükleniyor…":
        "Wczytywanie informacji vCard…",
    "vCard bulunamadı":
        "Nie znaleziono vCard",
    "Ad":
        "Imię i nazwisko",
    "Takma Ad":
        "Pseudonim",
    "E-posta":
        "E-mail",
    "Doğum":
        "Urodziny",
    "vCard boş":
        "vCard jest pusta",
    "Mesaj Gönder":
        "Wyślij wiadomość",
    "OMEMO Parmak İzleri — {}":
        "Odciski OMEMO — {}",
    "OMEMO Parmak İzleri":
        "Odciski OMEMO",
    "Bilgi alınamadı":
        "Nie udało się pobrać informacji",
    "Hata: {}":
        "Błąd: {}",
    "Cihaz bulunamadı":
        "Nie znaleziono urządzenia",
    "Cihaz: {}  ({})":
        "Urządzenie: {}  ({})",
    "Dışa Aktar":
        "Eksportuj",
    "Sohbet geçmişi boş.":
        "Historia rozmowy jest pusta.",
    "Sohbet Dışa Aktar":
        "Eksportuj rozmowę",
    "Tümü":
        "Wszystkie",
    "Okunmamış":
        "Nieprzeczytane",
    "Sabitlenmiş":
        "Przypięte",
    "Metin":
        "Tekst",
    "Sohbet: {}\n":
        "Rozmowa: {}\n",
    "Dışa aktarma: {}\n":
        "Eksport: {}\n",
    "Sohbet başarıyla dışa aktarıldı:\n{}":
        "Rozmowę wyeksportowano:\n{}",
    "Hata":
        "Błąd",
    "Dışa aktarma hatası: {}":
        "Błąd eksportu: {}",
    "Ses Mesajı":
        "Wiadomość głosowa",
    "PyAudio yüklü değil.\npip install pyaudio":
        "PyAudio nie jest zainstalowane.\npip install pyaudio",
    "✕ İptal":
        "✕ Anuluj",
    "✍ Yazıya dök":
        "✍ Transkrybuj",
    "▶ Gönder":
        "▶ Wyślij",
    "Ses kaydı hatası: {}":
        "Błąd nagrywania: {}",
    "Ses mesajı gönderilemedi: {}":
        "Nie udało się wysłać wiadomości głosowej: {}",
    "{} atılsın mı?\nSebep (opsiyonel):":
        "Wyrzucić {}?\nPowód (opcjonalnie):",
    "{} yasaklansın mı?\nSebep (opsiyonel):":
        "Zbanować {}?\nPowód (opcjonalnie):",
    "{} için JID girin:":
        "Wpisz JID dla {}:",
    "Yetki Değiştir":
        "Zmień przynależność",
    "Kişiyi Kaldır":
        "Usuń kontakt",
    "{} kaldırılsın mı?":
        "Usunąć {}?",
    "Oda Konusu":
        "Temat pokoju",
    "Yeni konu:":
        "Nowy temat:",
    "Davet":
        "Zaproś",
    "Odayı Sil":
        "Usuń pokój",
    "{} kalıcı olarak silinecek.\nEmin misiniz?":
        "{} zostanie trwale usunięty.\nNa pewno?",
    "Sebep (opsiyonel):":
        "Powód (opcjonalnie):",
    "{}🔓  Şifreleme Kapalı":
        "{}🔓  Szyfrowanie wyłączone",
    "  (kütüphane yüklü değil)":
        "  (biblioteka niezainstalowana)",
    "  (başlatılıyor…)":
        "  (uruchamianie…)",
    "  (GPG anahtarı yok)":
        "  (brak klucza GPG)",
    "🔒 OMEMO şifreleme açıldı":
        "🔒 Włączono szyfrowanie OMEMO",
    "🔑 OpenPGP şifreleme açıldı":
        "🔑 Włączono szyfrowanie OpenPGP",
    "🔓 Şifreleme kapatıldı":
        "🔓 Wyłączono szyfrowanie",
    "Tepki seç":
        "Wybierz reakcję",
    "☁  Sunucuya Yükle (HTTP)":
        "☁  Prześlij na serwer (HTTP)",
    "⚡  P2P Gönder (Jingle)":
        "⚡  Wyślij przez P2P (Jingle)",
    "Dosya Seç":
        "Wybierz plik",
    "Dosya Transferi":
        "Przesyłanie plików",
    "Bu sohbet OpenPGP ile şifreli, ama OpenPGP dosya şifreleyemez: dosya sunucuya şifresiz yüklenir, bağlantıyı gören herkes açabilir. Yine de gönderilsin mi?":
        "Ta rozmowa używa OpenPGP, ale OpenPGP nie szyfruje plików: plik zostanie przesłany bez szyfrowania i każdy z linkiem może go otworzyć. Mimo to wysłać?",
    "{} Yükleniyor: {}…":
        "{} Przesyłanie: {}…",
    "Bu sohbet şifreli, ama P2P aktarım (Jingle/IBB) uçtan uca şifreli değil: dosya sunucu üzerinden şifresiz geçer. Yine de P2P ile gönderilsin mi?":
        "Ta rozmowa jest szyfrowana, ale przesyłanie P2P (Jingle/IBB) nie jest szyfrowane end-to-end: plik przejdzie przez serwer bez szyfrowania. Mimo to wysłać przez P2P?",
    "Şifreli göndermek için 📎 → Sunucuya Yükle'yi kullanın (OMEMO'lu sohbette dosya şifrelenir).":
        "Aby wysłać zaszyfrowany plik, użyj 📎 → Prześlij na serwer (w rozmowach OMEMO pliki są szyfrowane).",
    "{mb} MB üzeri dosyalarda P2P yavaş olabilir. Devam edilsin mi?":
        "P2P może być wolne dla plików powyżej {mb} MB. Kontynuować?",
    "Kişi çevrimdışı görünüyor; P2P başarısız olabilir.":
        "Kontakt wygląda na niedostępny; P2P może się nie udać.",
    "otomatik kabul edildi":
        "zaakceptowano automatycznie",
    "Gelen Dosya Teklifi":
        "Przychodząca oferta pliku",
    "P2P — uçtan uca şifreli değil":
        "P2P — bez szyfrowania end-to-end",
    "Kabul Et ve Kaydet":
        "Akceptuj i zapisz",
    "Dosya teklifi yanıtsız kaldı":
        "Oferta pliku bez odpowiedzi",
    "Reddet":
        "Odrzuć",
    "bilinmeyen hata":
        "nieznany błąd",
    "❌ Dosya transferi: {}":
        "❌ Przesyłanie pliku: {}",
    "P2P başarısız oldu. Dosya sunucuya yüklenerek gönderilsin mi?":
        "P2P nie powiodło się. Wysłać plik przez serwer?",
    "Dosya gönderildi":
        "Plik wysłany",
    "Dosya alındı":
        "Plik odebrany",
    "İptal":
        "Anuluj",
    "Mesaj Arama":
        "Wyszukiwanie wiadomości",
    "🔍  Mesajlarda Ara":
        "🔍  Szukaj w wiadomościach",
    "Aranacak metin...":
        "Szukany tekst...",
    "Tema":
        "Motyw",
    "Tema uygulandı. Bazı öğeler yeniden başlatmada yenilenir.":
        "Zastosowano motyw. Niektóre elementy odświeżą się po ponownym uruchomieniu.",
    "En az {} harfli bir kelime girin":
        "Wpisz słowo o długości co najmniej {} liter",
    "Oda Oluştur":
        "Utwórz pokój",
    "{} adresinde zaten bir oda var.\n\nLütfen başka bir ad seçin. Oda sizinse odalar bölümündeki + (Odaya Katıl) düğmesiyle girebilirsiniz.":
        "Pod adresem {} istnieje już pokój.\n\nWybierz inną nazwę. Jeśli to Twój pokój, wejdź przyciskiem + (Dołącz do pokoju) w sekcji pokoi.",
    "⚠ Sunucu şifreli oda ayarlarını (yalnız üyeler / gerçek JID'ler) desteklemiyor; OMEMO bu odada çalışmaz. Oda normal ayarlarla açıldı.":
        "⚠ Serwer nie obsługuje ustawień pokoju szyfrowanego (tylko członkowie / prawdziwe JID-y); OMEMO nie zadziała w tym pokoju. Pokój otwarto ze zwykłymi ustawieniami.",
    "🌐 Oda hazır: adresi bilen herkes katılabilir.":
        "🌐 Pokój gotowy: każdy, kto zna adres, może dołączyć.",
    "🔒 Şifreli oda hazır: mesajlar OMEMO ile şifrelenir; yalnız davet ettikleriniz katılabilir (odaya sağ tık → 📨 Davet Gönder).":
        "🔒 Pokój szyfrowany gotowy: wiadomości są szyfrowane OMEMO; dołączyć mogą tylko zaproszone osoby (prawy klik na pokoju → 📨 Wyślij zaproszenie).",
    "Hesap":
        "Konto",
    "Sunucu":
        "Serwer",
    "🟢 Aktif":
        "🟢 Aktywne",
    "🔴 Pasif":
        "🔴 Nieaktywne",
    "⚫ Pasif":
        "⚫ Nieaktywne",
    "🟢 Yüklü":
        "🟢 Zainstalowane",
    "⚫ Yok":
        "⚫ Brak",
    "Kişi Sayısı":
        "Liczba kontaktów",
    "Aktif Odalar":
        "Aktywne pokoje",
    "Ayar Dosyası":
        "Plik ustawień",
    "OMEMO Veri":
        "Dane OMEMO",
    "Fotoğraf yayınlanamadı; eski fotoğraf korundu.":
        "Nie udało się opublikować zdjęcia; zachowano poprzednie.",
    "🌐 Dil":
        "🌐 Język",
    "Yeni dil uygulama yeniden başlatılınca geçerli olur.":
        "Nowy język zacznie obowiązywać po ponownym uruchomieniu aplikacji.",
    "● Uzakta (oto)":
        "● Zaraz wracam (auto)",
    "Göster":
        "Pokaż",
    "Çıkış":
        "Zakończ",
    "XMPP İstemci":
        "Klient XMPP",
    "{} sonuç":
        "Wyniki: {}",
    "🎭 GIF Ara":
        "🎭 Szukaj GIF-ów",
    "💡 Üstteki kutuya yazıp Enter'a basın (ilk aramada Tenor API anahtarı sorulur)":
        "💡 Wpisz w pole powyżej i naciśnij Enter (przy pierwszym wyszukiwaniu pojawi się prośba o klucz API Tenor)",
    "GIF Araması":
        "Wyszukiwanie GIF-ów",
    "Tenor API anahtarı (Google Cloud Console → Tenor API):":
        "Klucz API Tenor (Google Cloud Console → Tenor API):",
    "⚠ GIF araması için Tenor API anahtarı gerekli":
        "⚠ Wyszukiwanie GIF-ów wymaga klucza API Tenor",
    "Sonuç bulunamadı":
        "Brak wyników",
    "{} GIF — tıklayınca gönderilir":
        "GIF-y: {} — kliknij, aby wysłać",
    "Yedekleme / Geri Yükleme":
        "Kopia zapasowa / Przywracanie",
    "💾 Sohbet Yedekleme":
        "💾 Kopia zapasowa rozmów",
    "Yedek Kaydet":
        "Zapisz kopię",
    "Yedek":
        "Kopia zapasowa",
    "Yedeklendi: {}":
        "Zapisano kopię: {}",
    "Yedek Yükle":
        "Wczytaj kopię",
    "Geri yüklendi: {} sohbet":
        "Przywrócono rozmowy: {}",
    "📤 Yedekle (JSON)":
        "📤 Utwórz kopię (JSON)",
    "📥 Geri Yükle":
        "📥 Przywróć",
    "OMEMO QR Doğrulama":
        "Weryfikacja QR OMEMO",
    "🔐 OMEMO Parmak İzi":
        "🔐 Odcisk OMEMO",
    "Yükleniyor…":
        "Ładowanie…",
    "(OMEMO hazır değil)":
        "(OMEMO niegotowe)",
    "QR için: pip install qrcode":
        "Dla QR: pip install qrcode",
    "Kopyalandı":
        "Skopiowano",
    "Parmak izi panoya kopyalandı":
        "Odcisk skopiowano do schowka",
    "📋 Kopyala":
        "📋 Kopiuj",
    "Sohbet Arka Planı":
        "Tło rozmowy",
    "🖼 Sohbet Arka Planı":
        "🖼 Tło rozmowy",
    "Resim":
        "Obraz",
    "Arka Plan Seç":
        "Wybierz tło",
    "Arka Plan Rengi":
        "Kolor tła",
    "🖼 Resim Seç":
        "🖼 Wybierz obraz",
    "🎨 Renk Seç":
        "🎨 Wybierz kolor",
    "↩ Varsayılana Dön":
        "↩ Przywróć domyślne",
    "↩ Yanıtlanacak mesaj yok":
        "↩ Brak wiadomości, na którą można odpowiedzieć",
    "✏ Düzenlenecek mesajım yok":
        "✏ Brak mojej wiadomości do edycji",
    "🗑 Silinecek mesajım yok":
        "🗑 Brak mojej wiadomości do usunięcia",
    "Mesaj Zamanla":
        "Zaplanuj wiadomość",
    "Mesaj:":
        "Wiadomość:",
    "Kaç dakika sonra gönderilsin:":
        "Wyślij za ile minut:",
    "30 dk":
        "30 min",
    "1 saat":
        "1 godzina",
    "Özel (dk):":
        "Własne (min):",
    "⏰ Zamanla":
        "⏰ Zaplanuj",
    "⏰ Zamanlanmış mesaj ({} dk sonra): {}":
        "⏰ Zaplanowana wiadomość (za {} min): {}",
    "Toplu Mesaj":
        "Wiadomość zbiorcza",
    "📢 Toplu Mesaj Gönder":
        "📢 Wyślij wiadomość zbiorczą",
    "Alıcıları seçin:":
        "Wybierz odbiorców:",
    "0 kişi seçildi":
        "Wybrano 0 kontaktów",
    "{} kişi seçildi":
        "Wybrane kontakty: {}",
    "{} kişiye gönderildi":
        "Wysłano do kontaktów: {}",
    "📨 Gönder":
        "📨 Wyślij",
    "Otomatik Tema Geçişi":
        "Automatyczna zmiana motywu",
    "🌓 Otomatik Tema Geçişi":
        "🌓 Automatyczna zmiana motywu",
    "Otomatik tema geçişini etkinleştir":
        "Włącz automatyczną zmianę motywu",
    "Gündüz teması:":
        "Motyw dzienny:",
    "Gece teması:":
        "Motyw nocny:",
    "Gündüz başlangıç saati:":
        "Dzień zaczyna się o:",
    "Gece başlangıç saati:":
        "Noc zaczyna się o:",
    "Kaydet":
        "Zapisz",
    "Uygulama Kilidi":
        "Blokada aplikacji",
    "Mevcut PIN ayarlanmış ✓":
        "PIN jest ustawiony ✓",
    "PIN Doğrula":
        "Sprawdź PIN",
    "Mevcut PIN:":
        "Obecny PIN:",
    "PIN kaldırıldı":
        "PIN usunięty",
    "🗑 PIN'i Kaldır":
        "🗑 Usuń PIN",
    "Yeni PIN belirleyin:":
        "Ustaw nowy PIN:",
    "Tekrar girin:":
        "Wpisz ponownie:",
    "PIN en az 4 karakter olmalı":
        "PIN musi mieć co najmniej 4 znaki",
    "PIN'ler eşleşmiyor":
        "PIN-y się nie zgadzają",
    "PIN ayarlandı ✓":
        "PIN ustawiony ✓",
    "🔒 PIN Ayarla":
        "🔒 Ustaw PIN",
    "Proxy Ayarları":
        "Ustawienia proxy",
    "🔒 Proxy / SOCKS Ayarları":
        "🔒 Ustawienia proxy / SOCKS",
    "Proxy türü:":
        "Typ proxy:",
    "Yok":
        "Brak",
    "Adres:":
        "Adres:",
    "💡 Tor için: SOCKS5, 127.0.0.1:9050":
        "💡 Dla Tor: SOCKS5, 127.0.0.1:9050",
    "Yalnız XMPP bağlantısı proxy'den geçer; dosya yükleme/indirme, bağlantı önizlemesi, GIF ve AI istekleri geçmez. Kimlik doğrulamalı proxy desteklenmez.":
        "Przez proxy przechodzi tylko połączenie XMPP; przesyłanie/pobieranie plików, podglądy linków, GIF-y i żądania AI nie. Proxy z uwierzytelnianiem nie są obsługiwane.",
    "Ayarlar kaydedildi.\nBir sonraki bağlantıda uygulanır (ör. uygulamayı yeniden başlatınca).":
        "Zapisano ustawienia.\nZostaną zastosowane przy następnym połączeniu (np. po ponownym uruchomieniu aplikacji).",
    "Kullanılabilir komutlar:\n/help — Bu yardım\n/clear — Sohbet geçmişini temizle\n/nick <isim> — Oda takma adını değiştir\n/topic <konu> — Oda konusunu değiştir\n/invite <jid> — Odaya davet et\n/kick <nick> — Odadan at\n/ban <jid> — Yasakla\n/join <oda> — Odaya katıl\n/leave — Odadan ayrıl\n/status <mesaj> — Durum mesajı değiştir\n/ping — Sunucu ping\n/time — Şu anki saat\n/broadcast — Toplu mesaj\n/schedule — Mesaj zamanla\n/reply <metin> — Son gelen mesaja yanıt ver\n/react <emoji> — Son gelen mesaja tepki ekle\n/edit <metin> — Son mesajımı düzenle\n/del — Son mesajımı sil":
        "Dostępne polecenia:\n/help — Ta pomoc\n/clear — Wyczyść historię rozmowy\n/nick <nazwa> — Zmień pseudonim w pokoju\n/topic <temat> — Zmień temat pokoju\n/invite <jid> — Zaproś do pokoju\n/kick <nick> — Wyrzuć z pokoju\n/ban <jid> — Zbanuj\n/join <pokój> — Dołącz do pokoju\n/leave — Opuść pokój\n/status <wiadomość> — Zmień opis statusu\n/ping — Pinguj serwer\n/time — Bieżąca godzina\n/broadcast — Wiadomość zbiorcza\n/schedule — Zaplanuj wiadomość\n/reply <tekst> — Odpowiedz na ostatnią przychodzącą wiadomość\n/react <emoji> — Zareaguj na ostatnią przychodzącą wiadomość\n/edit <tekst> — Edytuj moją ostatnią wiadomość\n/del — Usuń moją ostatnią wiadomość",
    "📶 Son ping: {}ms":
        "📶 Ostatni ping: {}ms",
    "Takma ad değiştirildi: {}":
        "Zmieniono pseudonim: {}",
    "Konu değiştirildi: {}":
        "Zmieniono temat: {}",
    "Davet gönderildi: {}":
        "Wysłano zaproszenie: {}",
    "Kullanıcı atıldı: {}":
        "Wyrzucono użytkownika: {}",
    "Yasakla":
        "Zbanuj",
    "Kullanıcı yasaklanıyor: {}":
        "Banowanie użytkownika: {}",
    "Odaya katılınıyor: {}":
        "Dołączanie do pokoju: {}",
    "Odadan ayrılınıyor: {}":
        "Opuszczanie pokoju: {}",
    "Durum güncellendi: {}":
        "Zaktualizowano status: {}",
    "😊 Tepki verilecek mesaj yok":
        "😊 Brak wiadomości, na którą można zareagować",
    "Bilinmeyen komut: {}\n/help yazarak yardım alabilirsiniz":
        "Nieznane polecenie: {}\nWpisz /help, aby uzyskać pomoc",
    "Sohbet — {}":
        "Rozmowa — {}",
    "Bölünmüş Ekran":
        "Podzielony ekran",
    "En az 2 sohbet gerekli":
        "Potrzebne są co najmniej 2 rozmowy",
    "Bölünmüş Ekran — İkinci sohbet seçin":
        "Podzielony ekran — wybierz drugą rozmowę",
    "✓ Bağlandı":
        "✓ Połączono",
    "✓ Bağlantı Kuruldu":
        "✓ Nawiązano połączenie",
    "Sunucuya bağlanıldı":
        "Połączono z serwerem",
    "Mesaj — {}":
        "Wiadomość — {}",
    "Yeni mesaj":
        "Nowa wiadomość",
    "  Arama hatası: {}":
        "  Błąd wyszukiwania: {}",
    "  Sonuç bulunamadı":
        "  Brak wyników",
    "✓ {} odasına katıldı":
        "✓ Dołączono do {}",
    "ℹ {} zaten vardı: mevcut odaya katıldınız, ayarları değiştirilmedi.":
        "ℹ {} już istniał: dołączono do istniejącego pokoju; jego ustawień nie zmieniono.",
    "Bir kişi veya oda seçin":
        "Wybierz kontakt lub pokój",
    "📌 Konu: {}":
        "📌 Temat: {}",
    "MUC Daveti":
        "Zaproszenie MUC",
    "{} odasına davet edildiniz.\nSebep: {}\n\nKabul et?":
        "Zaproszono Cię do {}.\nPowód: {}\n\nAkceptować?",
    "Arkadaşlık İsteği":
        "Prośba o kontakt",
    "{} sizi takip etmek istiyor.\nKabul et?":
        "{} chce Cię obserwować.\nAkceptować?",
    "Oda Keşfi":
        "Odkrywanie pokoi",
    "Giriş Hatası":
        "Błąd logowania",
    "⚠ Bağlantı kesildi":
        "⚠ Rozłączono",
    "⚠ Bağlanılamadı":
        "⚠ Nie udało się połączyć",
    "⚠ Bağlantı başarısız{}: {}":
        "⚠ Połączenie nieudane{}: {}",
    "Bağlantı kesildi":
        "Rozłączono",
    "📊 Anket Oluştur":
        "📊 Utwórz ankietę",
    "Soru:":
        "Pytanie:",
    "Seçenekler (her satır bir seçenek):":
        "Opcje (jedna w wierszu):",
    "Evet\nHayır\nKararsızım":
        "Tak\nNie\nNie wiem",
    "Anket":
        "Ankieta",
    "Soru ve en az 2 seçenek gerekli":
        "Potrzebne są pytanie i co najmniej 2 opcje",
    "\n💡 Oy vermek için ilgili emoji ile tepki ekleyin":
        "\n💡 Aby zagłosować, zareaguj odpowiednim emoji",
    "📊 Anketi Gönder":
        "📊 Wyślij ankietę",
    "Hikaye":
        "Relacja",
    "Fotoğraf okunamadı: {}":
        "Nie udało się odczytać zdjęcia: {}",
    "📖 Hikaye":
        "📖 Relacja",
    "Durum yayınlandı":
        "Opublikowano status",
    "📋 XMPP Log Görüntüleyici":
        "📋 Podgląd dziennika XMPP",
    "📋 XMPP XML Trafik Logu":
        "📋 Dziennik ruchu XML XMPP",
    "Hesap: {}\n":
        "Konto: {}\n",
    "Bağlı: {}\n\n":
        "Połączono: {}\n\n",
    "⚠ Filter eklenemedi\n":
        "⚠ Nie udało się dodać filtra\n",
    "🗑 Temizle":
        "🗑 Wyczyść",
    "📤 Dışa Aktar":
        "📤 Eksportuj",
    "Sunucu başlatılamadı (port {}):\n{}":
        "Nie udało się uruchomić serwera (port {}):\n{}",
    "🔴 Hata: {}":
        "🔴 Błąd: {}",
    "🟢 Çalışıyor":
        "🟢 Działa",
    "⚫ Durduruldu":
        "⚫ Zatrzymany",
    "⏳ Başlatılıyor…":
        "⏳ Uruchamianie…",
    "⏳ Durduruluyor…":
        "⏳ Zatrzymywanie…",
    "▶ Başlat":
        "▶ Uruchom",
    "⏹ Durdur":
        "⏹ Zatrzymaj",
    "Bağlantı durumu":
        "Stan połączenia",
    "Kişi listesi":
        "Lista kontaktów",
    "Oda listesi":
        "Lista pokoi",
    "Mesaj geçmişi":
        "Historia wiadomości",
    "Mesaj gönder {to, message}":
        "Wyślij wiadomość {to, message}",
    "Bağlantı Kurulamadı":
        "Nie udało się połączyć",
    "20 saniye içinde sunucuya bağlanılamadı.\n\nSunucu: {}:{}{}\nSon hata: {}\n\nArka planda yeniden bağlanma denemeleri sürüyor.\nDenemeye devam edilsin mi?\n(\"Hayır\" → giriş ekranına dönülür)":
        "Nie udało się połączyć z serwerem w ciągu 20 sekund.\n\nSerwer: {}:{}{}\nOstatni błąd: {}\n\nPróby ponownego połączenia trwają w tle.\nPróbować dalej?\n(\"Nie\" → powrót do ekranu logowania)",
    "Kapat":
        "Zamknij",
    "Ne yapmak istiyorsun?":
        "Co chcesz zrobić?",
    "  Gizle (Tepsiye)  ":
        "  Ukryj (do zasobnika)  ",
    "  Uygulamadan Cik  ":
        "  Zamknij aplikację  ",
    "  Iptal  ":
        "  Anuluj  ",
    "🔁 Hesap Değişimi":
        "🔁 Zmień konto",
    "{} hesabına geçiliyor…":
        "Przełączanie na {}…",
    "Hesap değiştirilemedi: {}":
        "Nie udało się zmienić konta: {}",
    "XMPP bağlantı thread'i durdu: {}":
        "Wątek połączenia XMPP zatrzymał się: {}",
    "Bağlanıyor… {}":
        "Łączenie… {}",
    "🔑 Uygulama Kilidi":
        "🔑 Blokada aplikacji",
    "🔑 PIN Girin":
        "🔑 Wpisz PIN",
    "Yanlış PIN":
        "Błędny PIN",
    "Giriş":
        "Zaloguj",
    "aesgcm bağlantısı yalnız https yüklemeden kurulur":
        "Link aesgcm powstaje tylko z przesyłania przez https",
    "Çevrimiçi":
        "Dostępny",
    "Uzakta":
        "Zaraz wracam",
    "Meşgul":
        "Zajęty",
    "Uzun süre uzakta":
        "Dłużej nieobecny",
    "Model beklenen biçimde yanıt vermedi; tekrar deneyin.":
        "Model nie odpowiedział w oczekiwanym formacie; spróbuj ponownie.",
    "Hangi kişi ya da oda için? Adını yazın ya da önce sohbeti açın.":
        "Dla którego kontaktu lub pokoju? Wpisz nazwę albo najpierw otwórz rozmowę.",
    "Hangi odaya katılmak istiyorsunuz?":
        "Do którego pokoju chcesz dołączyć?",
    "Ne sormak istiyorsunuz?":
        "O co chcesz zapytać?",
    "Mesaj ya da hatırlatıcı metni eksik.":
        "Brakuje tekstu wiadomości lub przypomnienia.",
    "Hangi durum? (çevrimiçi, uzakta, meşgul)":
        "Jaki status? (dostępny, zaraz wracam, zajęty)",
    "Hatırlatıcı için tarih ve saat gerekli (ör. yarın 10:00).":
        "Przypomnienie wymaga daty i godziny (np. jutro 10:00).",
    "Hatırlatıcı zamanı geçmişte kalıyor.":
        "Czas przypomnienia już minął.",
    "📨 Mesaj gönderilsin mi?":
        "📨 Wysłać wiadomość?",
    "Alıcı: {}\n“{}”":
        "Do: {}\n„{}”",
    "⏰ Hatırlatıcı kurulsun mu?":
        "⏰ Ustawić przypomnienie?",
    "🚪 Odaya katılınsın mı?":
        "🚪 Dołączyć do pokoju?",
    "● Durum değiştirilsin mi?":
        "● Zmienić status?",
    "Geçmişe sor: ":
        "Zapytaj historię: ",
    "📬 Okunmamışları özetle":
        "📬 Podsumuj nieprzeczytane",
    "📅 Görevleri çıkar":
        "📅 Wyodrębnij zadania",
    "❓ Bekleyen sorular":
        "❓ Pytania bez odpowiedzi",
    "✍ Taslaklar":
        "✍ Szkice",
    "🚫 Bu mesaj silindi":
        "🚫 Ta wiadomość została usunięta",
    "🎤 Ses mesajı":
        "🎤 Wiadomość głosowa",
    "(Konuşma algılanmadı)":
        "(Nie wykryto mowy)",
    "[…yanıt uzunluk sınırına takıldı ve kesildi]":
        "[…odpowiedź osiągnęła limit długości i została ucięta]",
    "AI asistanı kapalı. ⚙ AI Ayarları'ndan bir sağlayıcı seçin.":
        "Asystent AI jest wyłączony. Wybierz dostawcę w ⚙ Ustawienia AI.",
    "Bu sohbet şifreli. Şifreli içerik izniniz olmadan buluta (Claude) gönderilmez.":
        "Ta rozmowa jest szyfrowana. Zaszyfrowana treść nie jest wysyłana do chmury (Claude) bez Twojej zgody.",
    "☁ Claude (bulut) · {}":
        "☁ Claude (chmura) · {}",
    "🖥 Yerel (Ollama) · {}":
        "🖥 Lokalnie (Ollama) · {}",
    "AI kapalı":
        "AI wyłączone",
    "Yanıt boyut sınırını aştı.":
        "Odpowiedź przekroczyła limit rozmiaru.",
    "Geçersiz adres: {!r} (http/https olmalı)":
        "Nieprawidłowy adres: {!r} (musi być http/https)",
    "Ollama'da '{}' modeli yok. Terminalde kurun:\n  ollama pull {}":
        "Ollama nie ma modelu '{}'. Zainstaluj go w terminalu:\n  ollama pull {}",
    "Ollama hatası ({}): {}":
        "Błąd Ollama ({}): {}",
    "Ollama'ya ulaşılamadı ({}).\nOllama çalışıyor mu? Terminalde: ollama serve":
        "Nie można połączyć się z Ollama ({}).\nCzy Ollama działa? W terminalu: ollama serve",
    "Yerel model zamanında yanıt vermedi.":
        "Model lokalny nie odpowiedział na czas.",
    "Ollama'dan geçersiz yanıt alındı.":
        "Nieprawidłowa odpowiedź z Ollama.",
    "Ollama yanıtı yarıda kesildi.":
        "Odpowiedź Ollama została przerwana.",
    "Ollama hatası: {}":
        "Błąd Ollama: {}",
    "Model yanıtı uzunluk sınırına takıldı; daha kısa bir sohbet aralığıyla tekrar deneyin.":
        "Odpowiedź modelu osiągnęła limit długości; spróbuj z krótszym fragmentem rozmowy.",
    "Yerel model boş yanıt döndürdü.":
        "Model lokalny zwrócił pustą odpowiedź.",
    "Gömme modeli beklenmeyen yanıt döndürdü.":
        "Model embeddingów zwrócił nieoczekiwaną odpowiedź.",
    "Claude için 'anthropic' paketi kurulu değil:\n  .venv-xmpp/bin/python -m pip install anthropic":
        "Pakiet 'anthropic' dla Claude nie jest zainstalowany:\n  .venv-xmpp/bin/python -m pip install anthropic",
    "Claude API anahtarı geçersiz ya da eksik (⚙ AI Ayarları).":
        "Klucz API Claude jest nieprawidłowy lub go brak (⚙ Ustawienia AI).",
    "Bu API anahtarının bu modele erişim izni yok.":
        "Ten klucz API nie ma dostępu do tego modelu.",
    "Claude modeli bulunamadı: {}":
        "Nie znaleziono modelu Claude: {}",
    "Claude hız sınırına takıldı; biraz sonra tekrar deneyin.":
        "Osiągnięto limit żądań Claude; spróbuj trochę później.",
    "Claude isteği kabul etmedi: {}":
        "Claude nie przyjął żądania: {}",
    "Claude sunucu hatası ({}); daha sonra tekrar deneyin.":
        "Błąd serwera Claude ({}); spróbuj później.",
    "Claude'a bağlanılamadı (internet bağlantısı?).":
        "Nie można połączyć się z Claude (połączenie z internetem?).",
    "Claude hatası: {}":
        "Błąd Claude: {}",
    "Claude bu isteği güvenlik nedeniyle yanıtlamadı.":
        "Claude nie odpowiedział na to żądanie ze względów bezpieczeństwa.",
    "Claude boş yanıt döndürdü.":
        "Claude zwrócił pustą odpowiedź.",
    "✍ Yazımı düzelt":
        "✍ Popraw pisownię",
    "🎩 Resmîleştir":
        "🎩 Bardziej oficjalnie",
    "😊 Samimileştir":
        "😊 Bardziej przyjaźnie",
    "✂ Kısalt":
        "✂ Skróć",
    "🌐 İngilizceye çevir":
        "🌐 Przetłumacz na angielski",
    "Bilinmeyen düzenleme modu: {}":
        "Nieznany tryb edycji: {}",
    "Model geçerli JSON döndürmedi; tekrar deneyin.":
        "Model nie zwrócił prawidłowego JSON; spróbuj ponownie.",
    "Başlığı boş bir öğe var.":
        "Jeden z elementów ma pusty tytuł.",
    "“{}”: tarih YYYY-AA-GG biçiminde olmalı.":
        "„{}”: data musi mieć format RRRR-MM-DD.",
    "“{}”: saat SS:DD biçiminde olmalı.":
        "„{}”: godzina musi mieć format GG:MM.",
    "“{}”: bitiş saati SS:DD biçiminde olmalı.":
        "„{}”: godzina zakończenia musi mieć format GG:MM.",
    "“{}”: saat verildiyse tarih de gerekli.":
        "„{}”: przy godzinie potrzebna jest też data.",
    "Sohbetten: “{}”":
        "Z rozmowy: „{}”",
    "Görsel biçimi tanınmadı.":
        "Nie rozpoznano formatu obrazu.",
    "Görsel açılamadı.":
        "Nie udało się otworzyć obrazu.",
    "Medya indirilemedi.":
        "Nie udało się pobrać multimediów.",
    "Ses→metin için faster-whisper gerekli (yerel çalışır):\n  .venv-xmpp/bin/python -m pip install faster-whisper \"av<19\"":
        "Zamiana mowy na tekst wymaga faster-whisper (działa lokalnie):\n  .venv-xmpp/bin/python -m pip install faster-whisper \"av<19\"",
    "Whisper modeli yüklenemedi ({}): {}":
        "Nie udało się wczytać modelu Whisper ({}): {}",
    "Ses çözücü (PyAV) faster-whisper ile uyumsuz. Düzeltmek için:\n  .venv-xmpp/bin/python -m pip install \"av<19\"":
        "Dekoder dźwięku (PyAV) jest niezgodny z faster-whisper. Aby naprawić:\n  .venv-xmpp/bin/python -m pip install \"av<19\"",
    "Ses yazıya dökülemedi: {}":
        "Nie udało się transkrybować nagrania: {}",
    "🔒 Şifreli mesaj (arşivde çözülemedi)":
        "🔒 Zaszyfrowana wiadomość (nie udało się odszyfrować w archiwum)",
    "[İletildi — {}]\n{}":
        "[Przekazane — {}]\n{}",
    "Oda adresi boş":
        "Adres pokoju jest pusty",
    "Geçersiz oda adresi: {!r} — oda adında {}":
        "Nieprawidłowy adres pokoju: {!r} — w nazwie pokoju: {}",
    " (ör. {})":
        " (np. {})",
    "Oda adresinde sunucu yok: {!r}":
        "Adres pokoju nie zawiera serwera: {!r}",
    "Geçersiz oda adresi: {!r}":
        "Nieprawidłowy adres pokoju: {!r}",
    "boşluk kullanılamaz":
        "spacje są niedozwolone",
    "şu karakterler kullanılamaz: ":
        "te znaki są niedozwolone: ",
    "Oda adı girin.":
        "Wpisz nazwę pokoju.",
    "Oda adından adres üretilemedi; harf ya da rakam kullanın (ör. proje-ekibi).":
        "Nie udało się utworzyć adresu z nazwy pokoju; użyj liter lub cyfr (np. zespol-projektu).",
    "Lütfen bir JID girin.":
        "Wpisz JID.",
    "Geçersiz JID — @ işareti olmalı (ör: ali@sunucu.tld)":
        "Nieprawidłowy JID — musi zawierać @ (np. ali@serwer.tld)",
    "Geçersiz JID — {}: {!r}":
        "Nieprawidłowy JID — {}: {!r}",
    "Geçersiz JID: {!r}":
        "Nieprawidłowy JID: {!r}",
    "Mesaj yazın...":
        "Napisz wiadomość...",
    "Tepki Ekle":
        "Dodaj reakcję",
    "Bir sohbet seçin":
        "Wybierz rozmowę",
    "Bir kişi veya oda seçerek konuşmaya başlayın":
        "Wybierz kontakt lub pokój, aby zacząć rozmowę",
    "Sohbete Başlayın":
        "Zacznij rozmowę",
    "yazıyor":
        "pisze",
    "⚠ OMEMO mesajı alındı ancak OMEMO hazır değil — çözülemedi":
        "⚠ Nadeszła wiadomość OMEMO, ale OMEMO nie jest gotowe — nie udało się jej odszyfrować",
    "OMEMO kütüphanesi yüklü değil (slixmpp-omemo).":
        "Biblioteka OMEMO nie jest zainstalowana (slixmpp-omemo).",
    "OMEMO henüz hazır değil — lütfen birkaç saniye bekleyin.":
        "OMEMO nie jest jeszcze gotowe — poczekaj kilka sekund.",
    "Mesaj gönderilemedi: {}":
        "Nie udało się wysłać wiadomości: {}",
    "Düzenleme hatası: {}":
        "Błąd edycji: {}",
    "Silme hatası: {}":
        "Błąd usuwania: {}",
    "Tepki hatası: {}":
        "Błąd reakcji: {}",
    "Yanıt hatası: {}":
        "Błąd odpowiedzi: {}",
    "İletme hatası: {}":
        "Błąd przekazywania: {}",
    "Bu takma ad odada kullanılıyor; başka bir takma ad deneyin.":
        "Ten pseudonim jest już zajęty w pokoju; wybierz inny.",
    "Oda parola istiyor.":
        "Pokój wymaga hasła.",
    "Bu odaya girişiniz yasaklanmış.":
        "Masz zakaz wstępu do tego pokoju.",
    "Oda yalnız üyelere açık.":
        "Pokój jest tylko dla członków.",
    "Oda bulunamadı (adres yanlış ya da oda kilitli olabilir).":
        "Nie znaleziono pokoju (adres może być błędny albo pokój zablokowany).",
    "Oda sunucusu bulunamadı (adresi kontrol edin).":
        "Nie znaleziono serwera pokoju (sprawdź adres).",
    "Oda dolu ya da şu an kullanılamıyor.":
        "Pokój jest pełny lub chwilowo niedostępny.",
    "Bu sunucuda yeni oda oluşturma izniniz yok.":
        "Nie możesz tworzyć pokoi na tym serwerze.",
    "Geçersiz oda adresi ya da takma ad.":
        "Nieprawidłowy adres pokoju lub pseudonim.",
    "Oda sunucusuna ulaşılamadı (zaman aşımı).":
        "Nie można połączyć się z serwerem pokoju (przekroczono czas).",
    "Oda taşınmış ya da kaldırılmış.":
        "Pokój został przeniesiony lub usunięty.",
    "Oda mesajı gönderilemedi: {}":
        "Nie udało się wysłać wiadomości do pokoju: {}",
    "'{}' sunucusunda oda bulunamadi.":
        "Na serwerze '{}' nie znaleziono pokoi.",
    "Sunucu bulunamadi (DNS hatasi)":
        "Nie znaleziono serwera (błąd DNS)",
    "Sunucu kesfetme desteklemiyor":
        "Serwer nie obsługuje odkrywania",
    "Sunucu yanit vermedi (zaman asimi)":
        "Serwer nie odpowiedział (przekroczono czas)",
    "Erisim reddedildi":
        "Odmowa dostępu",
    "⚠ '{}': {}. Genel Ara sekmesini deneyin.":
        "⚠ '{}': {}. Spróbuj karty Wyszukiwanie publiczne.",
    "Oda katılım hatası: {} {} sn içinde yanıt vermedi; oda sunucusu kapalı ya da adres yanlış olabilir.":
        "Błąd dołączania do pokoju: {} nie odpowiedział w ciągu {} s; serwer pokoju może nie działać albo adres jest błędny.",
    "{} odasına katılınamadı: {}":
        "Nie udało się dołączyć do {}: {}",
    "Oda katılım hatası: {}":
        "Błąd dołączania do pokoju: {}",
    "Oda ayrılma hatası: {}":
        "Błąd opuszczania pokoju: {}",
    "Konu değiştirme hatası: {}":
        "Błąd zmiany tematu: {}",
    "✓ {} odadan atıldı.":
        "✓ {} został wyrzucony z pokoju.",
    "Kick hatası: {}":
        "Błąd wyrzucania: {}",
    "✓ {} yasaklandı.":
        "✓ {} został zbanowany.",
    "Ban hatası: {}":
        "Błąd banowania: {}",
    "Rol değiştirme hatası: {}":
        "Błąd zmiany roli: {}",
    "Yetki değiştirme hatası: {}":
        "Błąd zmiany przynależności: {}",
    "✓ Takma adın değişti: {}":
        "✓ Zmieniono Twój pseudonim: {}",
    "Takma ad değiştirilemedi: {}":
        "Nie udało się zmienić pseudonimu: {}",
    "✓ {} davet edildi → {}":
        "✓ Zaproszono {} → {}",
    "Davet hatası: {}":
        "Błąd zaproszenia: {}",
    "Oda ayarları alınamadı: {}":
        "Nie udało się pobrać ustawień pokoju: {}",
    "✓ {} ayarları güncellendi.":
        "✓ Zaktualizowano ustawienia {}.",
    "Oda ayar kaydetme hatası: {}":
        "Błąd zapisu ustawień pokoju: {}",
    "✓ {} odası silindi.":
        "✓ Usunięto pokój {}.",
    "Oda silme hatası: {}":
        "Błąd usuwania pokoju: {}",
    "ℹ {} adresinde oda yoktu; sunucunun varsayılan ayarlarıyla yeni bir oda oluşturuldu.":
        "ℹ Pod adresem {} nie było pokoju; utworzono nowy z domyślnymi ustawieniami serwera.",
    "Yeni oda kullanıma açılamadı: {}":
        "Nie udało się udostępnić nowego pokoju: {}",
    "Oda yapılandırılamadı (sahibi olarak ⋮ → Oda Yönetimi'ni kullanın): {}":
        "Nie udało się skonfigurować pokoju (jako właściciel użyj ⋮ → Zarządzanie pokojem): {}",
    "✓ Yer imleri kaydedildi":
        "✓ Zapisano zakładki",
    "Yer imi kaydetme hatası: {}":
        "Błąd zapisu zakładki: {}",
    "✓ {} isteği kabul etti":
        "✓ {} zaakceptował prośbę",
    "✗ {} sizi kaldırdı":
        "✗ {} usunął Cię",
    "genel sunucu hatası":
        "ogólny błąd serwera",
    "kural seti izin vermedi":
        "niedozwolone przez reguły",
    "ağa ulaşılamıyor":
        "sieć nieosiągalna",
    "sunucuya ulaşılamıyor":
        "host nieosiągalny",
    "bağlantı reddedildi":
        "połączenie odrzucone",
    "zaman aşımı (TTL)":
        "przekroczono czas (TTL)",
    "komut desteklenmiyor":
        "nieobsługiwane polecenie",
    "adres türü desteklenmiyor":
        "nieobsługiwany typ adresu",
    "Proxy adresi girin (Tor için 127.0.0.1).":
        "Wpisz adres proxy (127.0.0.1 dla Tor).",
    "Geçerli bir port girin (1–65535).":
        "Wpisz prawidłowy port (1–65535).",
    "Proxy bağlantıyı beklenmedik şekilde kapattı":
        "Proxy nieoczekiwanie zamknęło połączenie",
    "Geçersiz hedef adı: {!r}":
        "Nieprawidłowa nazwa celu: {!r}",
    "SOCKS5 değil: proxy türünü kontrol edin":
        "To nie SOCKS5: sprawdź typ proxy",
    "SOCKS5 proxy kimlik doğrulama istiyor (desteklenmiyor)":
        "Proxy SOCKS5 wymaga uwierzytelnienia (nieobsługiwane)",
    "hata kodu {}":
        "kod błędu {}",
    "SOCKS5: geçersiz proxy yanıtı":
        "SOCKS5: nieprawidłowa odpowiedź proxy",
    "SOCKS4: istek reddedildi (kod {})":
        "SOCKS4: żądanie odrzucone (kod {})",
    "HTTP proxy yanıtı çok uzun":
        "Odpowiedź proxy HTTP jest za długa",
    "HTTP proxy reddetti: {}":
        "Proxy HTTP odmówiło: {}",
    "Proxy'ye bağlanılamadı ({}:{}): {}":
        "Nie udało się połączyć z proxy ({}:{}): {}",
    "Proxy zaman aşımı":
        "Przekroczono czas proxy",
    "az önce":
        "przed chwilą",
    "{} dakika önce":
        "minuty temu: {}",
    "{} saat önce":
        "godziny temu: {}",
    "dün":
        "wczoraj",
    "{} gün önce":
        "dni temu: {}",
    "Yanıtla: {} — {}":
        "Odpowiedz: {} — {}",
    "Anthropic API anahtarı":
        "Klucz API Anthropic",
    "OpenAI API anahtarı":
        "Klucz API OpenAI",
    "GitHub belirteci":
        "Token GitHub",
    "AWS erişim anahtarı":
        "Klucz dostępu AWS",
    "Google API anahtarı":
        "Klucz API Google",
    "Slack belirteci":
        "Token Slack",
    "Stripe gizli anahtarı":
        "Tajny klucz Stripe",
    "Oturum belirteci (JWT)":
        "Token sesji (JWT)",
    "Özel anahtar (private key)":
        "Klucz prywatny",
    "Parola / PIN":
        "Hasło / PIN",
    "Kart numarası":
        "Numer karty",
    "T.C. kimlik no":
        "Turecki numer identyfikacyjny",
    "Bu grup sohbetine şifresiz gönderilecek mesaj":
        "Wiadomość, która zostanie wysłana bez szyfrowania do tej rozmowy grupowej,",
    "Bu mesaj şifresiz gönderilecek ve":
        "Ta wiadomość zostanie wysłana bez szyfrowania i",
    "{} şu hassas bilgileri içeriyor gibi görünüyor:\n\n":
        "{} wygląda na to, że zawiera te dane wrażliwe:\n\n",
    "\n\nŞifresiz mesajları sunucu yöneticileri görebilir ve sunucu arşivinde (MAM) saklanabilir. Göndermeden önce 🔒 ile şifrelemeyi açabilirsiniz.\n\nYine de gönderilsin mi?":
        "\n\nAdministratorzy serwera widzą wiadomości nieszyfrowane, które mogą być przechowywane w archiwum serwera (MAM). Przed wysłaniem możesz włączyć szyfrowanie przyciskiem 🔒.\n\nMimo to wysłać?",
    "Dosya yükleme hatası: {}":
        "Błąd przesyłania pliku: {}",
    "🔒 Dosya şifreli yüklendi: {}":
        "🔒 Plik przesłano zaszyfrowany: {}",
    "✓ Dosya gönderildi: {}":
        "✓ Wysłano plik: {}",
    "Dosya gönderme hatası: {}":
        "Błąd wysyłania pliku: {}",
    "OMEMO kütüphanesi yüklü değil (slixmpp-omemo) — dosya gönderilmedi.":
        "Biblioteka OMEMO nie jest zainstalowana (slixmpp-omemo) — plik nie został wysłany.",
    "OMEMO henüz hazır değil — dosya gönderilmedi; birkaç saniye sonra tekrar deneyin.":
        "OMEMO nie jest jeszcze gotowe — plik nie został wysłany; spróbuj ponownie za kilka sekund.",
    "Sesli okuma için yerel bir ses motoru gerekli. Örneğin:\n  sudo pacman -S espeak-ng\nDaha doğal ses için Piper: piper-tts kurun ve ✨ → AI Ayarları'nda Türkçe bir ses modelinin (.onnx) yolunu girin.":
        "Czytanie na głos wymaga lokalnego silnika mowy. Na przykład:\n  sudo pacman -S espeak-ng\nDla bardziej naturalnego głosu zainstaluj piper-tts i podaj ścieżkę modelu głosu (.onnx) w ✨ → Ustawienia AI.",
    "Piper için `piper` komutu, bir ses modeli (.onnx) ve bir ses çalar (pw-play/paplay/aplay) gerekli.\n\n":
        "Piper wymaga polecenia `piper`, modelu głosu (.onnx) i odtwarzacza dźwięku (pw-play/paplay/aplay).\n\n",
    "Seçili ses motoru bulunamadı: {}\n\n":
        "Nie znaleziono wybranego silnika mowy: {}\n\n",
    "Okunacak metin yok.":
        "Nie ma tekstu do przeczytania.",
    "ℹ Sesli okuma motoru yok (isteğe bağlı): sudo pacman -S espeak-ng":
        "ℹ Brak silnika czytania (opcjonalny): sudo pacman -S espeak-ng",
    "✓ Sesli okuma: {}":
        "✓ Czytanie na głos: {}",
    "1 dk":
        "1 min",
    "10 dk":
        "10 min",
    "15 dk":
        "15 min",
    "kullanici@sunucu.tld":
        "uzytkownik@serwer.tld",
    "oda@conference.sunucu.tld":
        "pokoj@conference.serwer.tld",
    "yeni-oda":
        "nowy-pokoj",
    "muc.sunucu.tld":
        "muc.serwer.tld",
    "Koyu":
        "Ciemny",
    "Açık":
        "Jasny",
    "Gece mavisi":
        "Granat nocy",
}
