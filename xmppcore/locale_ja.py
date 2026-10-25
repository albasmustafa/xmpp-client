"""日本語 arayüz kataloğu: Türkçe metin (anahtar) → 日本語.

Eksik metin İngilizceye düşer (`xmppcore/i18n.py`); `{}` yer tutucuları
şablonla aynı kalmalı (`tests/test_i18n_catalog.py`).
"""

CATALOG = {
    "Veri zaman aşımı":
        "データの待機がタイムアウトしました",
    "Beyan edilen boyut aşıldı":
        "申告されたサイズを超えました",
    "Dosya 2 GiB sınırını aşıyor":
        "ファイルが 2 GiB の上限を超えています",
    "Kabul zaman aşımı":
        "受け入れの待機がタイムアウトしました",
    "Teklif gönderilemedi: {}":
        "ファイル送信の申し出を送れませんでした: {}",
    "Hash uyuşmadı":
        "ハッシュが一致しません",
    "Hash uyuşmazlığı":
        "ハッシュの不一致",
    "Reddedildi":
        "拒否されました",
    "İptal edildi":
        "キャンセルされました",
    "Yeni teklif":
        "新しい申し出",
    "Yeni teklif geldi":
        "新しい申し出が届きました",
    "Karşı taraf kapattı: {}":
        "相手が終了しました: {}",
    "sebep yok":
        "理由なし",
    "↪ Alıntılanan mesaja git":
        "↪ 引用元のメッセージへ移動",
    "👥 Tepkileri gör…":
        "👥 リアクションを見る…",
    "🌐 Çevir":
        "🌐 翻訳",
    "🎙 Sesi yazıya dök":
        "🎙 音声を文字起こし",
    "🖼 Görseli açıkla":
        "🖼 画像を説明",
    "❓ Görsele soru sor…":
        "❓ 画像について質問…",
    "🔊 Sesli oku":
        "🔊 読み上げ",
    "😀 Daha fazla emoji…":
        "😀 その他の絵文字…",
    "🎤 Yükleniyor…":
        "🎤 読み込み中…",
    "🎤 Ses Mesajı":
        "🎤 音声メッセージ",
    "🎤 Ses: {}…":
        "🎤 音声: {}…",
    "⬆ Daha eski":
        "⬆ 古い順",
    "↓ En yeni":
        "↓ 最新",
    "↓ Yeni mesajlar ({})":
        "↓ 新着メッセージ（{}）",
    "📷 Yükleniyor…":
        "📷 読み込み中…",
    "⚠ Resim yüklenemedi":
        "⚠ 画像を読み込めませんでした",
    "ESC ile kapat":
        "ESC で閉じる",
    "Tab ↹ kabul · Esc kapat":
        "Tab ↹ 確定 · Esc 閉じる",
    "Takip sorusu sorun…":
        "続けて質問する…",
    "⏳ Hazırlanıyor…":
        "⏳ 準備中…",
    "Sor ↵":
        "質問 ↵",
    "✓ Hazır":
        "✓ 準備完了",
    "✍ Yazılıyor…":
        "✍ 入力中…",
    "⏳ Yanıt hazırlanıyor…":
        "⏳ 回答を準備中…",
    "Seçince giriş kutusuna yerleştirilir:":
        "選ぶと入力欄に入ります:",
    "Anlamsal Arama":
        "意味検索",
    "🧠  Anlamla Ara":
        "🧠  意味で検索",
    "Örn: \"geçen ay konuşulan fiyat\", \"buluşma yeri\"":
        "例: \"先月話した価格\"、\"待ち合わせ場所\"",
    "Ne arıyorsunuz?":
        "何を探していますか？",
    "📅 Etkinlik":
        "📅 予定",
    "✅ Görev":
        "✅ タスク",
    "Tarih ve saatler sohbetten tahmin edildi; kaydetmeden önce kontrol edin (YYYY-AA-GG, SS:DD).":
        "日時は会話から推測したものです。保存前に確認してください（YYYY-MM-DD、HH:MM）。",
    "📅 .ics olarak kaydet":
        "📅 .ics として保存",
    "⏰ Hatırlatıcı kur":
        "⏰ リマインダーを設定",
    "✓ {} öğe bulundu — seçip kaydedin ya da hatırlatıcı kurun.":
        "✓ {} 件見つかりました — 選んで保存するか、リマインダーを設定してください。",
    "Bu sohbette görev ya da etkinlik bulunamadı.":
        "この会話にはタスクや予定が見つかりませんでした。",
    "Tarih":
        "日付",
    "Saat":
        "時刻",
    "Bitiş":
        "終了",
    "Yer":
        "場所",
    "Önce en az bir öğe seçin.":
        "先に 1 件以上選択してください。",
    "📋 Panoya kopyalandı":
        "📋 クリップボードにコピーしました",
    "💬 Sohbete git":
        "💬 会話へ移動",
    "⏰ Yarın 09:00 hatırlat":
        "⏰ 明日 09:00 に通知",
    "✓ Yok say":
        "✓ 無視",
    "{} sohbette yanıt bekleyen soru var.":
        "{} 件の会話に未回答の質問があります。",
    "Yanıt bekleyen soru yok. 🎉":
        "未回答の質問はありません。🎉",
    "Yanıt Bekleyen Sorular":
        "未回答の質問",
    "❓  Yanıt Bekleyen Sorular":
        "❓  未回答の質問",
    "Son mesajınızdan sonra size sorulan ve henüz yanıtlamadığınız sorular. Tespit bilgisayarınızda yapılır; hiçbir içerik dışarı gönderilmez.":
        "あなたの最後のメッセージ以降に聞かれ、まだ答えていない質問です。検出はこのコンピューター上で行われ、内容はどこにも送信されません。",
    "⏳ Taranıyor…":
        "⏳ スキャン中…",
    "↩ Takip sorusu":
        "↩ 追加の質問",
    "✓ Giriş kutusuna kondu — kontrol edip siz gönderin.":
        "✓ 入力欄に入れました — 確認してからご自身で送信してください。",
    "✓ Bir öneri seçin":
        "✓ 候補を選んでください",
    "Asistan":
        "アシスタント",
    "✨  Asistan":
        "✨  アシスタント",
    "Bir komut yazın ya da soru sorun…":
        "コマンドを入力するか質問してください…",
    "↩ Takip sorusu: {} — {}  (Esc: komut)":
        "↩ 追加の質問: {} — {}  （Esc: コマンド）",
    "{}  ·  sırada: {}":
        "{}  ·  待機中: {}",
    "sırada: {}":
        "待機中: {}",
    "Örnekler — tıklayın ya da kendiniz yazın:":
        "例 — クリックするか自分で入力:",
    "✗ Vazgeç":
        "✗ キャンセル",
    "Vazgeçildi.":
        "キャンセルしました。",
    "Yanıt Taslakları":
        "返信の下書き",
    "📝  Yanıt Taslakları":
        "📝  返信の下書き",
    "Taslaklar asla kendiliğinden gönderilmez: “Kullan” metni sohbetin giriş kutusuna koyar, düzenleyip siz gönderirsiniz.":
        "下書きが勝手に送信されることはありません。「使う」で会話の入力欄にテキストが入り、編集してご自身で送信します。",
    "{} sohbet için taslak var.":
        "{} 件の会話の下書きが用意できています。",
    "Bekleyen taslak yok.":
        "保留中の下書きはありません。",
    "{} yeni mesaj":
        "新着 {} 件",
    "⏳ Taslak hazırlanıyor…":
        "⏳ 下書きを準備中…",
    "🔒 Şifreli sohbet: taslak için içerik buluta (Claude) gönderilmeli.":
        "🔒 暗号化された会話: 下書きを作るには内容をクラウド（Claude）に送る必要があります。",
    "➡ Kullan":
        "➡ 使う",
    "☁ Onayla ve hazırla":
        "☁ 許可して準備",
    "🔄 Yeniden üret":
        "🔄 作り直す",
    "✓ Kaldır":
        "✓ 削除",
    "Kapalı":
        "オフ",
    "🖥 Yerel — Ollama (önerilen; veri bilgisayarda kalır)":
        "🖥 ローカル — Ollama（推奨。データはこのコンピューターに残ります）",
    "☁ Claude — bulut (Anthropic API)":
        "☁ Claude — クラウド（Anthropic API）",
    "AI Ayarları":
        "AI 設定",
    "✨ AI Asistanı":
        "✨ AI アシスタント",
    "Şifreli sohbetler varsayılan olarak yalnız yerel modelle işlenir. Ses→metin ve anlamsal arama her zaman yereldir.":
        "暗号化された会話は、既定ではローカルモデルだけで処理されます。音声の文字起こしと意味検索は常にローカルです。",
    "SAĞLAYICI":
        "プロバイダー",
    "YEREL MODEL (OLLAMA)":
        "ローカルモデル（OLLAMA）",
    "Adres":
        "アドレス",
    "Sohbet modeli":
        "チャットモデル",
    "Görsel modeli":
        "画像モデル",
    "Gömme modeli":
        "埋め込みモデル",
    "Model sıcak":
        "モデルの保持時間",
    "Ekran kartı":
        "グラフィックカード",
    "Kurulum: ollama pull {}  ·  ollama pull {}\nModel, bu süre boyunca bellekte tutulur; boşta geçen isteklerde yeniden yükleme beklemesi olmaz (5 dk = Ollama varsayılanı). Ekran kartı \"off\": sohbet modeli yalnız CPU'da (zayıf ekran kartında daha hızlı).":
        "導入: ollama pull {}  ·  ollama pull {}\nモデルはこの時間メモリに保持されるため、しばらく空いた後の要求でも再読み込みを待ちません（5 分 = Ollama の既定値）。グラフィックカード \"off\": チャットモデルは CPU だけで動きます（非力なグラフィックカードでは速くなります）。",
    "CLAUDE (BULUT)":
        "CLAUDE（クラウド）",
    "API anahtarı":
        "API キー",
    "Kayıtlı anahtar var — değiştirmek için yazın.":
        "キーは保存済みです — 変更するには新しいキーを入力してください。",
    "Boş bırakılırsa ANTHROPIC_API_KEY ortam değişkeni kullanılır.":
        "空欄の場合は環境変数 ANTHROPIC_API_KEY を使います。",
    "Kayıtlı anahtarı sil":
        "保存したキーを削除",
    "Şifreli sohbetlerde de her seferinde sormadan Claude'u kullan (önerilmez)":
        "暗号化された会話でも毎回確認せずに Claude を使う（非推奨）",
    "✨ Özellikler":
        "✨ 機能",
    "GENEL":
        "全般",
    "Çeviri/yanıt dili":
        "翻訳・返信の言語",
    "Şifresiz gönderimde parola/IBAN/kart gibi hassas bilgi uyarısı (yerel)":
        "暗号化せずに送るとき、パスワード/IBAN/カードなどの機密情報を警告する（ローカル）",
    "ASİSTAN":
        "アシスタント",
    "Yazarken satır içi öneri — Tab ile kabul et (yalnız yerel Ollama modeliyle çalışır)":
        "入力中のインライン候補 — Tab で確定（ローカルの Ollama モデルのみ）",
    "Uzaktayken gelen mesajlara yanıt taslağı hazırla (asla gönderilmez; dönüşte gözden geçirirsiniz)":
        "不在中に届いたメッセージへの返信の下書きを用意する（送信はされず、戻ったときに確認します）",
    "🎙 Ses":
        "🎙 音声",
    "SES → METİN":
        "音声 → テキスト",
    "Whisper modeli":
        "Whisper モデル",
    "Gelen sesli mesajları otomatik yazıya dök (yerel, faster-whisper)":
        "受信した音声メッセージを自動で文字起こしする（ローカル、faster-whisper）",
    "SESLİ OKUMA":
        "読み上げ",
    "Motor":
        "エンジン",
    "Piper ses modeli":
        "Piper の音声モデル",
    "Okuma dili":
        "読み上げ言語",
    "Motor yoksa: sudo pacman -S espeak-ng · Piper için .onnx ses modelinin tam yolunu girin (ör. tr_TR-dfki-medium.onnx).":
        "エンジンがない場合: sudo pacman -S espeak-ng · Piper では .onnx 音声モデルのフルパスを入力してください（例: tr_TR-dfki-medium.onnx）。",
    "MCP erişimi: harici AI araçları sohbet geçmişini okuyabilir ve taslak bırakabilir (mesaj gönderemez)":
        "MCP アクセス: 外部の AI ツールが会話履歴を読み、下書きを残せます（メッセージは送信できません）",
    "MCP'ye şifreli mesajların içeriğini de göster (önerilmez)":
        "暗号化メッセージの内容も MCP に見せる（非推奨）",
    "Kayıt komutu (taslak için REST API de açık olmalı):":
        "登録コマンド（下書きには REST API も有効にする必要があります）:",
    "📋 MCP komutu panoya kopyalandı.":
        "📋 MCP コマンドをクリップボードにコピーしました。",
    "⏳ Test ediliyor…":
        "⏳ テスト中…",
    "🔌 Bağlantıyı Test Et":
        "🔌 接続をテスト",
    "Mesajı İlet":
        "メッセージを転送",
    "İletilecek kişi/oda seçin:":
        "宛先を選択:",
    "Kaybolan Mesajlar":
        "消えるメッセージ",
    "Mesajlar belirli süre sonra\notomatik silinir.":
        "メッセージは設定した時間が過ぎると\n自動で削除されます。",
    "30sn":
        "30秒",
    "5dk":
        "5分",
    "1sa":
        "1時間",
    "1gün":
        "1日",
    "Uygula":
        "適用",
    "Geçmişi Sil":
        "履歴を削除",
    "🗑 Mesaj Geçmişini Sil":
        "🗑 メッセージ履歴を削除",
    "Toplam: {} mesaj, {} sohbet":
        "合計: {} 件のメッセージ、{} 件の会話",
    "Silindi":
        "削除しました",
    "Bu sohbetin geçmişi silindi":
        "この会話の履歴を削除しました",
    "Tüm Geçmişi Sil":
        "すべての履歴を削除",
    "Tüm sohbet geçmişi silinecek. Emin misiniz?":
        "すべての会話履歴が削除されます。よろしいですか？",
    "🗑 Bu Sohbeti Sil":
        "🗑 この会話を削除",
    "⚠ Tüm Geçmişi Sil":
        "⚠ すべての履歴を削除",
    "Kişi Grupları":
        "連絡先グループ",
    "🏷 Kişi Grupları":
        "🏷 連絡先グループ",
    "Henüz grup yok":
        "まだグループがありません",
    "Grup Ekle":
        "グループを追加",
    "Grup adı:":
        "グループ名:",
    "Bilgi":
        "情報",
    "Önce bir grup oluşturun":
        "先にグループを作成してください",
    "Gruba Ekle":
        "グループに追加",
    "Grup:":
        "グループ:",
    "Ekle":
        "追加",
    "+ Yeni Grup":
        "+ 新しいグループ",
    "+ Kişi Ekle":
        "+ 連絡先を追加",
    "Yeni Sohbet":
        "新しい会話",
    "  JID Gir  ":
        "  JID を入力  ",
    "Bir XMPP adresi girerek doğrudan sohbet\nbaşlatabilir veya abonelik isteği gönderebilirsiniz.":
        "XMPP アドレスを入力すると、すぐに会話を始めたり\n購読リクエストを送ったりできます。",
    "JID (XMPP Adresi)":
        "JID（XMPP アドレス）",
    "  Sohbet Başlat  ":
        "  会話を始める  ",
    "  Kişi Olarak Ekle  ":
        "  連絡先に追加  ",
    "  Kişiler  ":
        "  連絡先  ",
    "Mevcut kişilerinizden birini seçerek\nsohbet başlatabilirsiniz.":
        "既存の連絡先から選んで\n会話を始められます。",
    "Filtrele...":
        "絞り込み...",
    "  Kullanıcı Ara  ":
        "  ユーザーを検索  ",
    "Sunucuda kullanıcı arayın (XEP-0055).\nTüm sunucular bu özelliği desteklemeyebilir.":
        "サーバー上のユーザーを検索します（XEP-0055）。\nすべてのサーバーが対応しているわけではありません。",
    "Sunucu:":
        "サーバー:",
    "Arama:":
        "検索:",
    "İsim veya JID...":
        "名前または JID...",
    "  Aranıyor…":
        "  検索中…",
    "  Ara  ":
        "  検索  ",
    "🔍  Kullanıcı Ara":
        "🔍  ユーザーを検索",
    "Sunucuda kullanıcı arayın (XEP-0055)":
        "サーバー上のユーザーを検索（XEP-0055）",
    "Ara":
        "検索",
    "Sohbet Başlat":
        "会話を始める",
    "Durum Mesajı":
        "ステータスメッセージ",
    "Durum yazın...":
        "ステータスを入力...",
    "Konum Paylaş":
        "位置情報を共有",
    "Açıklama:":
        "説明:",
    "İstanbul":
        "イスタンブール",
    "Geçersiz koordinatlar":
        "座標が正しくありません",
    "Paylaş":
        "共有",
    "Durdur":
        "停止",
    "Davet Gönder":
        "招待を送る",
    "{} odasına davet edilecek JID:":
        "{} に招待する JID:",
    "Ortak Gruplar":
        "共通のグループ",
    "🏠 {} ile Ortak Gruplar":
        "🏠 {} との共通グループ",
    "  Ortak grup bulunamadı":
        "  共通のグループはありません",
    "Bir konferans sunucusu keşfedin veya doğrudan katılın":
        "会議サーバーを探すか、直接参加します",
    "🌐  KONFERANS SUNUCUSU":
        "🌐  会議サーバー",
    "Odaları Keşfet":
        "ルームを探す",
    "🚪  ODA JID (doğrudan katıl)":
        "🚪  ルームの JID（直接参加）",
    "👤  TAKMA AD":
        "👤  ニックネーム",
    "Katıl":
        "参加",
    "Yeni bir sohbet odası oluşturun":
        "新しいチャットルームを作成",
    "🏠  ODA ADI":
        "🏠  ルーム名",
    "Adres: …@{}":
        "アドレス: …@{}",
    "Adres: {}":
        "アドレス: {}",
    "🛡  ODA TÜRÜ":
        "🛡  ルームの種類",
    "🌐  Normal oda":
        "🌐  通常のルーム",
    "Adresi bilen herkes katılabilir, mesajlar şifresizdir.":
        "アドレスを知っている人は誰でも参加できます。メッセージは暗号化されません。",
    "🔒  Şifreli oda (OMEMO)":
        "🔒  暗号化ルーム（OMEMO）",
    "Yalnız davet ettikleriniz katılır, mesajlar uçtan uca şifrelenir.":
        "招待した人だけが参加できます。メッセージはエンドツーエンドで暗号化されます。",
    "OMEMO kütüphanesi (slixmpp-omemo) yüklü değil.":
        "OMEMO ライブラリ（slixmpp-omemo）がインストールされていません。",
    "Oluştur ve Katıl":
        "作成して参加",
    "📑  Yer İmleri":
        "📑  ブックマーク",
    "Mevcut Odayı Ekle":
        "現在のルームを追加",
    "🗑 Sil":
        "🗑 削除",
    "Oda Ayarları — {}":
        "ルーム設定 — {}",
    "Oda Yönetimi — {}":
        "ルーム管理 — {}",
    "  Üyeler  ":
        "  メンバー  ",
    "  Ayarlar  ":
        "  設定  ",
    "Oda Konusu:":
        "ルームの話題:",
    "Konuyu Güncelle":
        "話題を更新",
    "  Davet  ":
        "  招待  ",
    "Davet edilecek JID:":
        "招待する JID:",
    "{} davet edildi":
        "{} を招待しました",
    "📨 Davet Gönder":
        "📨 招待を送る",
    "İsim A→Z":
        "名前 A→Z",
    "İsim Z→A":
        "名前 Z→A",
    "Adres A→Z":
        "アドレス A→Z",
    "Adres Z→A":
        "アドレス Z→A",
    "Keşfedilen Odalar":
        "見つかったルーム",
    "Oda ara (isim veya adres)...":
        "ルームを検索（名前またはアドレス）...",
    "  (Eşleşen oda bulunamadı)":
        "  （一致するルームはありません）",
    "{}/{} oda":
        "{}/{} ルーム",
    "Seçilen Odaya Katıl":
        "選択したルームに参加",
    "  Genel Ara  ":
        "  公開検索  ",
    "Oda adı veya konu ara...":
        "ルーム名や話題で検索...",
    "Aranıyor…":
        "検索中…",
    "  (Sonuç bulunamadı)":
        "  （結果なし）",
    "Yer imine eklendi":
        "ブックマークに追加しました",
    "Yer İmine Ekle":
        "ブックマークを追加",
    "  Popüler Sunucular  ":
        "  人気のサーバー  ",
    "Bir sunucu seçip 'Keşfet' ile odaları listeleyin.":
        "サーバーを選び「探す」でルームを一覧表示します。",
    "Seçili Sunucudan Keşfet":
        "選択したサーバーから探す",
    "Sunucu adresi":
        "サーバーアドレス",
    "  Keşfet  ":
        "  探す  ",
    "  Hesap  ":
        "  アカウント  ",
    "PROFİL":
        "プロフィール",
    "Sunucu: {}":
        "サーバー: {}",
    "Profil Fotoğrafı Seç":
        "プロフィール写真を選択",
    "Tüm":
        "すべて",
    "Fotoğraf yüklenemedi: {}":
        "写真を読み込めませんでした: {}",
    "Fotoğraf Değiştir":
        "写真を変更",
    "Kaldır":
        "削除",
    "DURUM MESAJI":
        "ステータスメッセージ",
    "GİRİŞ":
        "ログイン",
    "Açılışta otomatik giriş (formu atla)":
        "起動時に自動ログイン（フォームを省略）",
    "ÇOKLU HESAP":
        "複数アカウント",
    "⇄ Geçiş":
        "⇄ 切り替え",
    "Ek hesap yok":
        "ほかのアカウントはありません",
    "Hesap Ekle":
        "アカウントを追加",
    "Şifre:":
        "パスワード:",
    "+ Hesap Ekle":
        "+ アカウントを追加",
    "  Görünüm  ":
        "  外観  ",
    "TEMA":
        "テーマ",
    "YAZI TİPİ":
        "フォント",
    "Yazı tipi:":
        "フォント:",
    "Boyut:":
        "サイズ:",
    "ÖNİZLEME":
        "プレビュー",
    "Merhaba! Bu bir önizleme mesajıdır. 🎉":
        "こんにちは！これはプレビュー用のメッセージです。🎉",
    "DİL":
        "言語",
    "DÜZEN":
        "レイアウト",
    "📐 Kompakt mod (mesaj balonları daha sıkışık)":
        "📐 コンパクトモード（吹き出しを詰めて表示）",
    "SOHBET ARKA PLANI":
        "会話の背景",
    "(varsayılan)":
        "（既定）",
    "Mevcut: {}":
        "現在: {}",
    "🖼 Arka Plan Değiştir…":
        "🖼 背景を変更…",
    "  Bildirimler  ":
        "  通知  ",
    "BİLDİRİMLER":
        "通知",
    "Masaüstü bildirimleri göster":
        "デスクトップ通知を表示",
    "Bildirim sesleri çal":
        "通知音を鳴らす",
    "🔊 Sesi Test Et":
        "🔊 音をテスト",
    "SİSTEM TEPSİSİ":
        "システムトレイ",
    "⚫ pystray yüklü değil":
        "⚫ pystray がインストールされていません",
    "Tepsi ikonu: {}":
        "トレイアイコン: {}",
    "Yüklemek için: pip install pystray":
        "インストール: pip install pystray",
    "GİZLİLİK":
        "プライバシー",
    "Okundu bilgisi gönder (XEP-0333)":
        "既読通知を送る（XEP-0333）",
    "Yazıyor bildirimi gönder (XEP-0085)":
        "入力中の通知を送る（XEP-0085）",
    "KAYBOLAN MESAJLAR":
        "消えるメッセージ",
    "Varsayılan süre (tüm yeni sohbetler için):":
        "既定の時間（新しい会話すべて）:",
    "30 sn":
        "30秒",
    "5 dk":
        "5分",
    "1 gün":
        "1日",
    "ENGELLİ KİŞİLER":
        "ブロック中の連絡先",
    "🚫 Engelli kişileri yönet...":
        "🚫 ブロック中の連絡先を管理...",
    "İndirme klasörü":
        "ダウンロードフォルダー",
    "Gelen dosyaları otomatik kabul et":
        "受信ファイルを自動で受け入れる",
    "IBB blok boyutu":
        "IBB ブロックサイズ",
    "Büyük dosya uyarı eşiği (MB)":
        "大きなファイルの警告しきい値（MB）",
    "  Şifreleme  ":
        "  暗号化  ",
    "Hazır":
        "準備完了",
    "Yüklü değil":
        "未インストール",
    "Başlatılmadı":
        "未起動",
    "Cihaz bilgileri yükleniyor…":
        "デバイス情報を読み込み中…",
    "Bu Cihaz  (ID: {})":
        "このデバイス  （ID: {}）",
    "Diğer Cihazlar ({})":
        "ほかのデバイス（{}）",
    "Başka cihaz bulunamadı":
        "ほかのデバイスは見つかりませんでした",
    "GPG bulunamadı":
        "GPG が見つかりません",
    "Anahtar: {} adet":
        "キー: {}",
    "PGP ANAHTAR EŞLEŞTİRME":
        "PGP キーの対応付け",
    "JID → GPG Key ID eşleştirmesi":
        "JID → GPG キー ID の対応付け",
    "+ Eşleştirme Ekle":
        "+ 対応付けを追加",
    "OMEMO QR DOĞRULAMA":
        "OMEMO QR 検証",
    "🔐 QR Kod ile Parmak İzi Doğrula…":
        "🔐 QR コードでフィンガープリントを検証…",
    "🟢 qrcode kütüphanesi yüklü":
        "🟢 qrcode ライブラリはインストール済み",
    "⚫ QR için: pip install qrcode[pil]":
        "⚫ QR には: pip install qrcode[pil]",
    "VARSAYILAN ŞİFRELEME":
        "既定の暗号化",
    "🔓 Kapalı":
        "🔓 オフ",
    "  Bağlantı  ":
        "  接続  ",
    "BAĞLANTI AYARLARI":
        "接続設定",
    "Odalara otomatik yeniden katıl":
        "ルームに自動で再参加",
    "OTOMATİK UZAKTA":
        "自動離席",
    "İşlem yapılmadığında otomatik uzakta durumuna geç:":
        "操作がないとき自動で離席にする:",
    "3 dk":
        "3分",
    "BAĞLANTI KALİTESİ":
        "接続品質",
    "📶 Bağlantı yok":
        "📶 接続なし",
    "📶 Henüz ölçülmedi":
        "📶 未計測",
    "KAYITLI ODALAR":
        "保存したルーム",
    "Kayıtlı oda yok":
        "保存したルームはありません",
    "BAĞLANTI DURUMU":
        "接続状態",
    "Bağlı":
        "接続済み",
    "Bağlı değil":
        "未接続",
    "Hesap: {}":
        "アカウント: {}",
    "Kişiler: {}  •  Aktif Odalar: {}":
        "連絡先: {}  •  参加中のルーム: {}",
    "PROXY / ANONİM BAĞLANTI":
        "プロキシ / 匿名接続",
    "Yapılandırılmamış":
        "未設定",
    "Tür: {}":
        "種類: {}",
    "🔧 Proxy Ayarları…":
        "🔧 プロキシ設定…",
    "OTOMATİK TEMA GEÇİŞİ":
        "テーマの自動切り替え",
    "⚫ Kapalı":
        "⚫ オフ",
    "🌓 Otomatik Tema Ayarları…":
        "🌓 テーマ自動切り替えの設定…",
    "GÜVENLİK":
        "セキュリティ",
    "🔑 Uygulama Kilidi (PIN)…":
        "🔑 アプリのロック（PIN）…",
    "🗑 Mesaj Geçmişini Sil…":
        "🗑 メッセージ履歴を削除…",
    "  Hakkında  ":
        "  このアプリについて  ",
    "deneme.py — Modern Tkinter XMPP İstemcisi":
        "deneme.py — Tkinter 製のモダンな XMPP クライアント",
    "KÜTÜPHANELER":
        "ライブラリ",
    "VERİ":
        "データ",
    "📤 Sohbetleri Dışa Aktar":
        "📤 会話をエクスポート",
    "📋 Ayarları Kopyala":
        "📋 設定をコピー",
    "✓ Kopyalandı":
        "✓ コピーしました",
    "💾 Yedekleme / Geri Yükleme…":
        "💾 バックアップ / 復元…",
    "KLAVYE KISAYOLLARI":
        "キーボードショートカット",
    "⌨ Kısayolları Göster…":
        "⌨ ショートカットを表示…",
    "Hızlı Geçiş":
        "クイック切り替え",
    "Sohbette Ara":
        "会話内を検索",
    "Yedekleme":
        "バックアップ",
    "  Kaydet ve Kapat  ":
        "  保存して閉じる  ",
    "Klavye Kısayolları":
        "キーボードショートカット",
    "Hızlı Geçiş (kişi/oda)":
        "クイック切り替え（連絡先/ルーム）",
    "Son mesaja yanıtla":
        "最後のメッセージに返信",
    "Son mesajımı düzenle":
        "自分の最後のメッセージを編集",
    "Son mesajımı sil":
        "自分の最後のメッセージを削除",
    "✨ Neler kaçırdım? (AI özeti)":
        "✨ 見逃したことは？（AI 要約）",
    "✨ Geçmişe sor (AI)":
        "✨ 履歴に質問（AI）",
    "✨ Sesle yaz (dikte)":
        "✨ 音声入力（ディクテーション）",
    "Üzerine gel":
        "マウスオーバー",
    "Eylem butonları (yanıtla/tepki/… )":
        "操作ボタン（返信/リアクション/… ）",
    "Çift tık":
        "ダブルクリック",
    "Mesajı yanıtla (alıntı)":
        "メッセージに返信（引用）",
    "Tepkiye tıkla":
        "リアクションをクリック",
    "Tepkini ekle / kaldır":
        "自分のリアクションを追加 / 削除",
    "Bu menü":
        "このメニュー",
    "Aramayı kapat":
        "検索を閉じる",
    "Mesaj gönder":
        "メッセージを送信",
    "Yapıştır (resim/metin)":
        "貼り付け（画像/テキスト）",
    "Tepkiler":
        "リアクション",
    "😊 Tepkiler":
        "😊 リアクション",
    "(tepki yok)":
        "（リアクションなし）",
    "📖 Hikaye / Durum Paylaş":
        "📖 ストーリー / ステータスを共有",
    "METİN DURUMU":
        "テキストステータス",
    "RUHSAL DURUM":
        "気分",
    "😊 Mutlu":
        "😊 うれしい",
    "😔 Üzgün":
        "😔 悲しい",
    "😡 Kızgın":
        "😡 怒っている",
    "😴 Uykulu":
        "😴 眠い",
    "🤔 Düşünceli":
        "🤔 考え中",
    "🎉 Heyecanlı":
        "🎉 わくわく",
    "FOTOĞRAF":
        "写真",
    "Seçilmedi":
        "選択されていません",
    "📷 Fotoğraf Seç":
        "📷 写真を選択",
    "📤 Yayınla":
        "📤 公開",
    "Profil Fotoğrafı":
        "プロフィール写真",
    "Fotoğrafınızı değiştirin veya kaldırın":
        "写真を変更または削除します",
    "✓ Güncellendi":
        "✓ 更新しました",
    "⚠ Yayınlanamadı — eski fotoğraf korundu":
        "⚠ 公開できませんでした — 以前の写真のままです",
    "Pillow Gerekli":
        "Pillow が必要です",
    "Fotoğraf desteği için Pillow gerekli:\npip install Pillow":
        "写真機能には Pillow が必要です:\npip install Pillow",
    "Fotoğraf Seç":
        "写真を選択",
    "Resim Dosyaları":
        "画像ファイル",
    "Tüm Dosyalar":
        "すべてのファイル",
    "✓ Kaldırıldı":
        "✓ 削除しました",
    "📷  Fotoğraf Seç":
        "📷  写真を選択",
    "  📝 Konu Değiştir":
        "  📝 話題を変更",
    "  📨 Davet Gönder":
        "  📨 招待を送る",
    "  ⚙ Oda Ayarları":
        "  ⚙ ルーム設定",
    "  🚪 Odayı Terk Et":
        "  🚪 ルームから退出",
    "  💣 Odayı Sil":
        "  💣 ルームを削除",
    "  Yetki: {}":
        "  所属: {}",
    "  Rol: {}":
        "  役割: {}",
    "  💬 Özel Mesaj":
        "  💬 個別メッセージ",
    "  👢 At (Kick)":
        "  👢 キック",
    "  🔇 Sustur":
        "  🔇 発言を禁止",
    "  🔊 Konuşmaya İzin Ver":
        "  🔊 発言を許可",
    "  ⚔ Moderatör Yap":
        "  ⚔ モデレーターにする",
    "  ⚔ Moderatörlüğü Al":
        "  ⚔ モデレーターを外す",
    "  🚫 Yasakla (Ban)":
        "  🚫 追放（BAN）",
    "  🛡 Yönetici Yap":
        "  🛡 管理者にする",
    "  👤 Üye Yap":
        "  👤 メンバーにする",
    "  ↓ Yetkiyi Kaldır":
        "  ↓ 所属を外す",
    "↑/↓ seç · Enter aç · Esc kapat":
        "↑/↓ 選択 · Enter 開く · Esc 閉じる",
    "Eşleşen sohbet bulunamadı":
        "一致する会話はありません",
    "  Sohbet Başlat":
        "  会話を始める",
    "📌 Sabitlemeyi Kaldır":
        "📌 固定を解除",
    "📌 Sohbeti Sabitle":
        "📌 会話を固定",
    "🏠 Ortak Gruplar":
        "🏠 共通のグループ",
    "  Kişiyi Kaldır":
        "  連絡先を削除",
    "KATILIMCILAR — {}":
        "参加者 — {}",
    "Çevrimdışı":
        "オフライン",
    "Ortak grup: {}":
        "共通のグループ: {}",
    "özel":
        "非公開",
    "⚠ Değişiklikler kaybolacak — kapatmak için yine dışarı tıkla":
        "⚠ 変更は失われます — 閉じるにはもう一度外側をクリックしてください",
    "KİŞİLER":
        "連絡先",
    "Kullanıcı Ara":
        "ユーザーを検索",
    "ODALAR":
        "ルーム",
    "GELİŞMİŞ":
        "詳細",
    "Mesaj Ara":
        "メッセージを検索",
    "Yeniden Bağlan":
        "再接続",
    "Ayarlar":
        "設定",
    "⏱ Kaybolan Mesajlar":
        "⏱ 消えるメッセージ",
    "📜 Daha Eski Mesajları Yükle (MAM)":
        "📜 古いメッセージを読み込む（MAM）",
    "⏰ Mesaj Zamanla":
        "⏰ メッセージを予約",
    "📤 Sohbeti Dışa Aktar":
        "📤 会話をエクスポート",
    "🗑 Geçmişi Sil":
        "🗑 履歴を削除",
    "🔧 Oda Yönetimi":
        "🔧 ルーム管理",
    "👤 Profil":
        "👤 プロフィール",
    "🔎 Mesaj Ara":
        "🔎 メッセージを検索",
    "📌 Sabitlenmiş Mesajlar":
        "📌 固定したメッセージ",
    "💬 Sohbet":
        "💬 会話",
    "📤 Paylaşım":
        "📤 共有",
    "📍 Konum Paylaş":
        "📍 位置情報を共有",
    "📖 Hikaye Paylaş":
        "📖 ストーリーを共有",
    "📢 Toplu Mesaj":
        "📢 一斉送信",
    "🔒 Güvenlik":
        "🔒 セキュリティ",
    "🔒 OMEMO Parmak İzleri":
        "🔒 OMEMO フィンガープリント",
    "🔐 OMEMO QR Doğrulama":
        "🔐 OMEMO QR 検証",
    "🚫 Engelli Kişiler":
        "🚫 ブロック中の連絡先",
    "🪟 Görünüm":
        "🪟 表示",
    "📺 Yeni Sekmede Aç":
        "📺 新しいタブで開く",
    "📺 Bölünmüş Ekran":
        "📺 画面分割",
    "🖼 Arka Plan Değiştir":
        "🖼 背景を変更",
    "📐 Rahat Moda Geç":
        "📐 ゆったりモードに切り替え",
    "📐 Kompakt Moda Geç":
        "📐 コンパクトモードに切り替え",
    "⚙ Diğer":
        "⚙ その他",
    "💬 Durum Mesajı":
        "💬 ステータスメッセージ",
    "💾 Yedekleme / Geri Yükleme":
        "💾 バックアップ / 復元",
    "⌨ Klavye Kısayolları":
        "⌨ キーボードショートカット",
    "Yüzler":
        "顔",
    "El":
        "手",
    "Kalp":
        "ハート",
    "Nesne":
        "もの",
    "Yiyecek":
        "食べ物",
    "Doğa":
        "自然",
    "Bugün":
        "今日",
    "⚠ OMEMO plugin kaydı başarısız: {}":
        "⚠ OMEMO プラグインの登録に失敗しました: {}",
    "⚠ OMEMO başlatma zaman aşımına uğradı. Sunucu PEP/PubSub desteklemeyebilir.":
        "⚠ OMEMO の起動がタイムアウトしました。サーバーが PEP/PubSub に対応していない可能性があります。",
    "⚠ OMEMO başlatma hatası: {}":
        "⚠ OMEMO の起動エラー: {}",
    "🔐 OMEMO şifreleme hazır":
        "🔐 OMEMO 暗号化の準備ができました",
    "⚠ OMEMO çözme hatası: {}":
        "⚠ OMEMO の復号エラー: {}",
    "⚠ PGP mesajı çözülemedi (anahtar eksik?)":
        "⚠ PGP メッセージを復号できませんでした（キーがない？）",
    "⚠ PGP çözme hatası: {}":
        "⚠ PGP の復号エラー: {}",
    "🔑 PGP anahtar ayarlandı (config)":
        "🔑 PGP キーを設定しました（設定ファイル）",
    "🔑 PGP anahtar otomatik eşleştirildi: {}":
        "🔑 PGP キーを自動で対応付けました: {}",
    "🔑 PGP: tek secret key kullanılıyor: {}":
        "🔑 PGP: 唯一の秘密鍵を使用します: {}",
    "Sunucuya bağlandı, oturum açılıyor…":
        "サーバーに接続しました。ログイン中…",
    "Giriş başarısız: JID veya şifre yanlış.":
        "ログインに失敗しました: JID またはパスワードが違います。",
    "⟳ {}s sonra yeniden bağlanılıyor…":
        "⟳ {} 秒後に再接続します…",
    "PGP: {} için GPG anahtarı bulunamadı. Ayarlar → Şifreleme'den anahtar eşleştirin.":
        "PGP: {} の GPG キーが見つかりません。設定 → 暗号化 でキーを対応付けてください。",
    "PGP şifreleme başarısız: {}":
        "PGP 暗号化に失敗しました: {}",
    "PGP: Şifreli veri çıkarılamadı":
        "PGP: 暗号化データを取り出せませんでした",
    "PGP gönderme hatası: {}":
        "PGP 送信エラー: {}",
    "OMEMO: Oda üyelerinin JID'leri alınamadı (oda anonim olabilir). Şifreli dosya bağlantısı şifresiz GÖNDERİLMEDİ.":
        "OMEMO: ルームメンバーの JID を取得できませんでした（匿名ルームの可能性があります）。暗号化ファイルのリンクは平文では送信していません。",
    "OMEMO: Oda üyelerinin JID'leri alınamadı (oda anonim olabilir). Düz metin gönderiliyor.":
        "OMEMO: ルームメンバーの JID を取得できませんでした（匿名ルームの可能性があります）。平文で送信します。",
    "OMEMO: Alıcının cihaz bilgileri alınamadı.\nKarşı tarafın OMEMO destekli bir istemci kullanması gerekiyor.\nDetay: {}":
        "OMEMO: 相手のデバイス情報を取得できませんでした。\n相手は OMEMO 対応のクライアントを使う必要があります。\n詳細: {}",
    "OMEMO şifreleme hatası: {}":
        "OMEMO 暗号化エラー: {}",
    "⚠ OMEMO uyarı: {}":
        "⚠ OMEMO の警告: {}",
    "OMEMO şifreleme başarısız — şifreli dosya bağlantısı şifresiz GÖNDERİLMEDİ.":
        "OMEMO 暗号化に失敗しました — 暗号化ファイルのリンクは平文では送信していません。",
    "OMEMO şifreleme başarısız — düz metin gönderiliyor":
        "OMEMO 暗号化に失敗しました — 平文で送信します",
    "✓ Profil fotoğrafı güncellendi":
        "✓ プロフィール写真を更新しました",
    "⚠ Avatar yayınlanamadı: {}":
        "⚠ アバターを公開できませんでした: {}",
    "İstek gönderildi → {}":
        "リクエストを送信しました → {}",
    "Kişi eklenemedi: {}":
        "連絡先を追加できませんでした: {}",
    "✓ Kişi kaldırıldı: {}":
        "✓ 連絡先を削除しました: {}",
    "Kişi kaldırılamadı: {}":
        "連絡先を削除できませんでした: {}",
    "Engelleme hatası: {}":
        "ブロックのエラー: {}",
    "✓ {} engeli kaldırıldı":
        "✓ {} のブロックを解除しました",
    "Engel kaldırma hatası: {}":
        "ブロック解除のエラー: {}",
    "Engel listesi hatası: {}":
        "ブロックリストのエラー: {}",
    "📍 Konum paylaşıldı":
        "📍 位置情報を共有しました",
    "Konum paylaşma hatası: {}":
        "位置情報共有のエラー: {}",
    "Ruh hâli paylaşılamadı: {}":
        "気分を共有できませんでした: {}",
    "📍 Konum paylaşımı durduruldu":
        "📍 位置情報の共有を停止しました",
    "Konum durdurma hatası: {}":
        "位置情報停止のエラー: {}",
    "XMPP Giriş":
        "XMPP ログイン",
    "Hesabınıza giriş yapın":
        "アカウントにログイン",
    "Şifre":
        "パスワード",
    "Gelişmiş":
        "詳細設定",
    "Otomatik giriş":
        "自動ログイン",
    "Şifremi hatırla":
        "パスワードを記憶する",
    "Sunucu (boş = SRV)":
        "サーバー（空欄 = SRV）",
    "SRV otomatik  •  OMEMO & PGP destekli":
        "SRV 自動  •  OMEMO と PGP に対応",
    "Bağlan":
        "接続",
    "Eksik Bilgi":
        "入力不足",
    "JID ve şifre gerekli.":
        "JID とパスワードが必要です。",
    "Geçersiz JID":
        "JID が正しくありません",
    "JID formatı: kullanıcı@sunucu.tld":
        "JID の形式: user@server.tld",
    "Kişi veya oda ara...":
        "連絡先やルームを検索...",
    "Kişi Ekle":
        "連絡先を追加",
    "Gruplar":
        "グループ",
    "Komut ver ya da soru sor · Ctrl+Shift+K":
        "指示や質問をどうぞ · Ctrl+Shift+K",
    "Oda Keşfet":
        "ルームを探す",
    "Yer İmleri":
        "ブックマーク",
    "Odaya Katıl":
        "ルームに参加",
    "Ana Menü":
        "メインメニュー",
    "＋  Yeni Sohbet":
        "＋  新しい会話",
    "✓ Bağlantı":
        "✓ 接続",
    "Zaten bağlısınız":
        "すでに接続しています",
    "Bağlantı":
        "接続",
    "Deneme başlatılamadı: {}":
        "接続を試せませんでした: {}",
    "⟳ Yeniden bağlanılıyor…":
        "⟳ 再接続中…",
    "Bağlanıyor…":
        "接続中…",
    "KATILIMCILAR":
        "参加者",
    "🔒 Şifreli dosya (OMEMO)":
        "🔒 暗号化ファイル（OMEMO）",
    "⬇ İndir ve aç":
        "⬇ ダウンロードして開く",
    "📂 Klasörde göster":
        "📂 フォルダーで表示",
    "Alıntılanan mesaja git":
        "引用元のメッセージへ移動",
    "Yanıtla":
        "返信",
    "Tepki ekle":
        "リアクションを追加",
    "Tepkileri gör":
        "リアクションを見る",
    "AI: çevir / yazıya dök / açıkla":
        "AI: 翻訳 / 文字起こし / 説明",
    "Kopyala":
        "コピー",
    "İlet":
        "転送",
    "Sabitle":
        "固定",
    "Düzenle":
        "編集",
    "Sil":
        "削除",
    "⚠ Şifreli dosya açılamadı":
        "⚠ 暗号化ファイルを開けませんでした",
    "📥 Şifreli dosya":
        "📥 暗号化ファイル",
    "Aç":
        "開く",
    "Klasörü Aç":
        "フォルダーを開く",
    "🔗 {n} görsel bağlantısı daha":
        "🔗 ほかに {n} 件の画像リンク",
    "🎤 {n} ses bağlantısı daha":
        "🎤 ほかに {n} 件の音声リンク",
    "Görsel bağlantıları":
        "画像リンク",
    "Ses bağlantıları":
        "音声リンク",
    "{} — {} bağlantı":
        "{} — リンク {} 件",
    "Sayfa {}/{}":
        "{}/{} ページ",
    "◀ Önceki":
        "◀ 前へ",
    "Sonraki ▶":
        "次へ ▶",
    "🔗 Tarayıcıda Aç":
        "🔗 ブラウザーで開く",
    "↪ Alıntılanan mesaj uygulamada bulunamadı":
        "↪ 引用元のメッセージがアプリ内に見つかりません",
    "Mesajı Düzenle":
        "メッセージを編集",
    "Yeni metin:":
        "新しいテキスト:",
    "Mesajı Sil":
        "メッセージを削除",
    "Bu mesajı silmek istediğinizden emin misiniz?":
        "このメッセージを削除してもよろしいですか？",
    "↩ Bu mesaj yanıtlanamıyor (kimlik yok)":
        "↩ このメッセージには返信できません（ID なし）",
    "Bu mesaj şifreli içerik taşıyor ama seçtiğiniz sohbet şifresiz: içerik (şifreli dosyanın anahtarı dahil) sunucuya açık metin gider. Yine de iletilsin mi?":
        "このメッセージには暗号化された内容が含まれていますが、選んだ会話は暗号化されていません。内容（暗号化ファイルのキーを含む）がサーバーに平文で届きます。それでも転送しますか？",
    "Sabitlenmiş Mesajlar":
        "固定したメッセージ",
    "Şifreli Sohbet":
        "暗号化された会話",
    "{}\n\nYalnız bu istek için içerik Claude'a (bulut) gönderilsin mi?\nHayır derseniz hiçbir şey gönderilmez.":
        "{}\n\nこの要求に限り、内容を Claude（クラウド）に送りますか？\n「いいえ」を選ぶと何も送信されません。",
    "{}\n\nAI Ayarları açılsın mı?":
        "{}\n\nAI 設定を開きますか？",
    "Beklenmeyen hata: {}":
        "予期しないエラー: {}",
    "{}\n\n{} kaynağın {} tanesi şifreli.\n\nEvet: şifreli içerik de yalnız bu istek için Claude'a (bulut) gönderilsin.\nHayır: şifreli içerik çıkarılsın, yalnız kalanı gönderilsin.\nİptal: hiçbir şey gönderilmesin.":
        "{}\n\n{} 件のソースのうち {} 件が暗号化されています。\n\nはい: この要求に限り、暗号化された内容も Claude（クラウド）に送ります。\nいいえ: 暗号化された内容を除き、残りだけ送ります。\nキャンセル: 何も送りません。",
    "✨ Asistan…":
        "✨ アシスタント…",
    "📬 Okunmamışları özetle ({})":
        "📬 未読を要約（{}）",
    "📝 Sohbeti özetle":
        "📝 会話を要約",
    "📅 Görev ve etkinlikleri çıkar":
        "📅 タスクと予定を抽出",
    "💬 Bu sohbet":
        "💬 この会話",
    "❓ Yanıt bekleyen sorular":
        "❓ 未回答の質問",
    "✍ Yanıt taslakları":
        "✍ 返信の下書き",
    "🔎 Geçmişe sor…":
        "🔎 履歴に質問…",
    "🧠 Anlamsal arama…":
        "🧠 意味検索…",
    "🗂 Tüm sohbetler":
        "🗂 すべての会話",
    "⚙ AI Ayarları…":
        "⚙ AI 設定…",
    "💡 Yanıt öner":
        "💡 返信を提案",
    "✨ Asistan (bu sohbet)…":
        "✨ アシスタント（この会話）…",
    "⏹ Dikteyi bitir":
        "⏹ 音声入力を終了",
    "🎙 Sesle yaz (dikte)":
        "🎙 音声入力（ディクテーション）",
    "⏹ Sesli okumayı durdur":
        "⏹ 読み上げを停止",
    "✍ Taslağı düzenle":
        "✍ 下書きを編集",
    "↶ AI değişikliğini geri al":
        "↶ AI の変更を元に戻す",
    "🌐 Çeviri":
        "🌐 翻訳",
    "Örn: Bu ifade ne anlama geliyor?":
        "例: この表現はどういう意味？",
    "🎙 Ses kaydının metni":
        "🎙 録音の文字起こし",
    "🖥 Yerel (faster-whisper) · {}":
        "🖥 ローカル（faster-whisper）· {}",
    "Yazıya dökülüyor… (ilk kullanımda model indirilir)":
        "文字起こし中…（初回はモデルをダウンロードします）",
    "🎙 Otomatik ses→metin durdu":
        "🎙 自動文字起こしを停止しました",
    "faster-whisper/model yok — AI Ayarları → Test Et":
        "faster-whisper/モデルがありません — AI 設定 → テスト",
    "Görsel çok büyük.":
        "画像が大きすぎます。",
    "Görsele Soru Sor":
        "画像について質問",
    "Görsel hakkında ne sormak istiyorsunuz?":
        "画像について何を聞きたいですか？",
    "🖼 Görsel açıklaması":
        "🖼 画像の説明",
    "Örn: Arka planda ne yazıyor?":
        "例: 背景に何と書いてある？",
    "Özet":
        "要約",
    "Özetlenecek mesaj yok.":
        "要約するメッセージがありません。",
    "📝 {} — okunmamış {} mesajın özeti":
        "📝 {} — 未読 {} 件の要約",
    "📝 {} — sohbet özeti":
        "📝 {} — 会話の要約",
    "{} · son {} mesaj":
        "{} · 最新 {} 件のメッセージ",
    "Örn: Benden ne isteniyor? Saat kaçta buluşuyoruz?":
        "例: 何を頼まれている？何時に会う？",
    "Neler kaçırdım?":
        "見逃したことは？",
    "Okunmamış mesaj yok — her şey okunmuş. 🎉":
        "未読メッセージはありません — すべて既読です。🎉",
    "Okunmamışlar arasında özetlenecek metin mesajı yok.":
        "未読の中に要約できるテキストメッセージがありません。",
    "📥 Neler kaçırdım?":
        "📥 見逃したことは？",
    "{} · {} sohbet, {} okunmamış mesaj":
        "{} · {} 件の会話、未読 {} 件",
    "Örn: Bana kim soru sordu?":
        "例: 誰が私に質問した？",
    "Sohbete git":
        "会話へ移動",
    "Ali'ye yarın 10'da toplantı olduğunu yaz":
        "Ali に明日 10 時に会議があると伝えて",
    "Yarın 09:00'da faturayı ödemeyi hatırlat":
        "明日 09:00 に請求書の支払いをリマインドして",
    "Geçmişe sor: Ali'nin verdiği adres neydi?":
        "履歴に質問: Ali が教えてくれた住所は？",
    "Ayşe ile sohbeti özetle":
        "Ayşe との会話を要約して",
    "Durumumu meşgul yap":
        "ステータスを取り込み中にして",
    "💬 Bağlam: {} — \"bu sohbet\" ya da ad yazmadan verilen komutlar bu sohbete":
        "💬 コンテキスト: {} — 「この会話」と言ったり名前のないコマンドはこの会話に適用されます",
    "Açık sohbet yok — komutlarda kişi ya da oda adını yazın":
        "開いている会話がありません — コマンドには連絡先やルームの名前を書いてください",
    "{} · kişi listeniz modele gönderilmez; gönderme ve değişiklikler onayınızla yapılır":
        "{} · 連絡先リストはモデルに送られません。送信や変更にはあなたの承認が必要です",
    "Düşünüyor…":
        "考え中…",
    "“{}” adında bir kişi ya da oda bulunamadı.":
        "「{}」という連絡先やルームは見つかりませんでした。",
    "“{}” birden çok kişiyle eşleşti":
        "「{}」は複数の連絡先に一致します",
    "✓ Onayla":
        "✓ 承認",
    "✗ İptal":
        "✗ キャンセル",
    "✓ Seçildi":
        "✓ 選択しました",
    "✓ {} sohbeti açıldı.":
        "✓ {} との会話を開きました。",
    "✓ Taslak giriş kutusuna kondu — kontrol edip siz gönderin.":
        "✓ 下書きを入力欄に入れました — 確認してからご自身で送信してください。",
    "⚠ Oda adresi geçersiz.":
        "⚠ ルームのアドレスが正しくありません。",
    "✓ {} odasına katılma isteği gönderildi.":
        "✓ {} への参加リクエストを送りました。",
    "✓ Durum: {}":
        "✓ ステータス: {}",
    "✓ İlgili pencere açıldı.":
        "✓ 該当するウィンドウを開きました。",
    "⚠ Bu eylem desteklenmiyor.":
        "⚠ この操作には対応していません。",
    "⚠ Sunucuya bağlı değilsiniz.":
        "⚠ サーバーに接続していません。",
    "⚠ “/” ile başlayan metin komut sayılır; gönderilmedi.":
        "⚠ 「/」で始まるテキストはコマンドとして扱われるため、送信しませんでした。",
    "✓ {} kişisine gönderildi.":
        "✓ {} に送信しました。",
    "Gönderilmedi (uyarıda vazgeçildi).":
        "送信しませんでした（警告でキャンセル）。",
    "Sohbette metin mesajı yok.":
        "会話にテキストメッセージがありません。",
    "Model öneri üretemedi.":
        "モデルが候補を作れませんでした。",
    "📝 Taslak alınamadı":
        "📝 下書きを作れませんでした",
    "Taslak kutusu dolu — önce birkaçını kaldırın":
        "下書きボックスがいっぱいです — 先にいくつか削除してください",
    "📝 Yeni yanıt taslağı":
        "📝 新しい返信の下書き",
    "📝 Uzaktayken gelenler":
        "📝 不在中に届いたもの",
    "{} sohbet için yanıt taslağı — Ctrl+Shift+R":
        "{} 件の会話に返信の下書き — Ctrl+Shift+R",
    "🌙 Uzaktayken":
        "🌙 不在中",
    "🔊 Sesli okuma":
        "🔊 読み上げ",
    "🔊 Sesli okuma başarısız":
        "🔊 読み上げに失敗しました",
    "{} çalışmadı":
        "{} は動作しませんでした",
    "⚠ Hassas bilgi":
        "⚠ 機密情報",
    "Tespit bu bilgisayarda yapılır; hiçbir içerik dışarı gönderilmez.":
        "検出はこのコンピューター上で行われ、内容はどこにも送信されません。",
    "Taranıyor…":
        "スキャン中…",
    "{} sohbette soru yanıt bekliyor — Ctrl+Shift+Q":
        "{} 件の会話で質問が返信を待っています — Ctrl+Shift+Q",
    "Görevler ve Etkinlikler":
        "タスクと予定",
    "Bu sohbette henüz mesaj yok.":
        "この会話にはまだメッセージがありません。",
    "📅 {} — görevler ve etkinlikler":
        "📅 {} — タスクと予定",
    "Sohbet inceleniyor…":
        "会話を確認中…",
    "Kaydedilecek öğe yok.":
        "保存するものがありません。",
    "Takvim dosyasını kaydet":
        "カレンダーファイルを保存",
    "Tüm dosyalar":
        "すべてのファイル",
    "⚠ Dosya yazılamadı: {}":
        "⚠ ファイルを書き込めませんでした: {}",
    "✓ {} öğe kaydedildi: {} — takvim uygulamanızla açabilirsiniz.":
        "✓ {} 件を保存しました: {} — カレンダーアプリで開けます。",
    "Hatırlatıcı için seçili öğelerde ileri bir tarih ve saat olmalı.":
        "リマインダーには、選んだ項目に未来の日時が必要です。",
    "⏰ {} hatırlatıcı kuruldu.":
        "⏰ リマインダーを {} 件設定しました。",
    " {} öğede ileri tarih/saat olmadığı için kurulmadı.":
        " 未来の日時がない {} 件は設定しませんでした。",
    "  — zamanı geçti":
        "  — 時刻を過ぎています",
    "⏰ Hatırlatıcı":
        "⏰ リマインダー",
    "Yanıt Öner":
        "返信を提案",
    "💡 Yanıt önerileri":
        "💡 返信の候補",
    "AI Asistanı":
        "AI アシスタント",
    "Önce giriş kutusuna bir mesaj yazın.":
        "先に入力欄にメッセージを書いてください。",
    "Sesle Yaz":
        "音声入力",
    "Mikrofon için PyAudio gerekli:\n  .venv-xmpp/bin/python -m pip install pyaudio":
        "マイクには PyAudio が必要です:\n  .venv-xmpp/bin/python -m pip install pyaudio",
    "Ses→metin için faster-whisper gerekli (yerel çalışır):\n  .venv-xmpp/bin/python -m pip install faster-whisper":
        "文字起こしには faster-whisper が必要です（ローカルで動作）:\n  .venv-xmpp/bin/python -m pip install faster-whisper",
    "Uygulama kapanıyor.":
        "アプリを終了しています。",
    "Konuşma algılanmadı.":
        "音声が検出されませんでした。",
    "🎙 Dikte":
        "🎙 ディクテーション",
    "✍ Taslağa koy":
        "✍ 下書きに入れる",
    "✓ Sohbet değiştiği için burada gösteriliyor":
        "✓ 会話が切り替わったためここに表示しています",
    "🖥 Yerel gömme · {} — mesajlar bilgisayardan çıkmaz":
        "🖥 ローカル埋め込み · {} — メッセージがこのコンピューターから出ることはありません",
    "⏳ İndeksleme zaten sürüyor…":
        "⏳ すでにインデックス作成中です…",
    "⏳ Mesajlar indeksleniyor: {}/{} (arama şimdiden çalışır)":
        "⏳ メッセージのインデックス作成中: {}/{}（検索はもう使えます）",
    "✓ {} yeni mesaj indekslendi.":
        "✓ 新しいメッセージ {} 件をインデックスしました。",
    "✓ İndeks güncel.":
        "✓ インデックスは最新です。",
    "⏳ İndeks kontrol ediliyor…":
        "⏳ インデックスを確認中…",
    "İptal edildi.":
        "キャンセルしました。",
    "Gömmeler veritabanına yazılamadı.":
        "埋め込みをデータベースに書き込めませんでした。",
    "⏳ Aranıyor…":
        "⏳ 検索中…",
    "{} sonuç — açmak için çift tıklayın":
        "{} 件の結果 — ダブルクリックで開く",
    "Eşleşen mesaj bulunamadı.":
        "一致するメッセージは見つかりませんでした。",
    "🔎 Geçmişe sor":
        "🔎 履歴に質問",
    "{} · arama yerel ({})":
        "{} · ローカル検索（{}）",
    "Örn: Ali'nin verdiği adres neydi?":
        "例: Ali が教えてくれた住所は？",
    "Sorunuzu aşağıya yazın: ilgili mesajlar bu bilgisayarda bulunur, yanıt kaynaklarıyla gelir.":
        "下に質問を書いてください。関連するメッセージをこのコンピューター上で探し、出典つきで回答します。",
    "İlgili mesajlar aranıyor…":
        "関連するメッセージを探しています…",
    "Mesajlar indeksleniyor: {}/{}…":
        "メッセージのインデックス作成中: {}/{}…",
    "Bu soruyla ilgili bir mesaj bulunamadı. Farklı kelimelerle sormayı deneyin.":
        "この質問に関係するメッセージは見つかりませんでした。別の言葉で聞いてみてください。",
    "Eşleşme yok":
        "一致なし",
    "Gönderilmedi.":
        "送信しませんでした。",
    "İptal edildi — hiçbir şey gönderilmedi.":
        "キャンセルしました — 何も送信していません。",
    "Eşleşen mesajlar gönderilebilecek metin içermiyor (yalnız medya ya da şifreli içerik).":
        "一致したメッセージに送信できるテキストがありません（メディアか暗号化された内容のみ）。",
    "Kaynaklar":
        "出典",
    "İlgili mesajlar":
        "関連するメッセージ",
    "Yanıt hazırlanıyor…":
        "回答を準備中…",
    "AI kapalı — test edilecek sağlayıcı yok.":
        "AI はオフです — テストするプロバイダーがありません。",
    "✓ Ollama çalışıyor; modeller hazır.":
        "✓ Ollama は動作中で、モデルの準備もできています。",
    "✗ Ollama çalışıyor ama eksik model var: ":
        "✗ Ollama は動作中ですが、モデルが不足しています: ",
    "✓ Claude erişilebilir ({}).":
        "✓ Claude に接続できます（{}）。",
    "✓ faster-whisper kurulu (ses→metin).":
        "✓ faster-whisper はインストール済みです（音声 → テキスト）。",
    "✗ Ses→metin için: .venv-xmpp/bin/python -m pip install faster-whisper":
        "✗ 音声 → テキストには: .venv-xmpp/bin/python -m pip install faster-whisper",
    "✓ MCP erişimi açık; REST API çalışıyor (taslak bırakılabilir).":
        "✓ MCP アクセスはオンで、REST API が動作中です（下書きを残せます）。",
    "ℹ MCP erişimi açık; taslak bırakmak için REST API'yi de açın.":
        "ℹ MCP アクセスはオンです。下書きを残すには REST API もオンにしてください。",
    "Engelli Kişiler":
        "ブロック中の連絡先",
    "Engelle":
        "ブロック",
    "Engeli Kaldır":
        "ブロック解除",
    "Yeni Engelle":
        "新しくブロック",
    "Profil — {}":
        "プロフィール — {}",
    "vCard bilgileri yükleniyor…":
        "vCard 情報を読み込み中…",
    "vCard bulunamadı":
        "vCard が見つかりません",
    "Ad":
        "名前",
    "Takma Ad":
        "ニックネーム",
    "E-posta":
        "メール",
    "Doğum":
        "誕生日",
    "vCard boş":
        "vCard は空です",
    "Mesaj Gönder":
        "メッセージを送る",
    "OMEMO Parmak İzleri — {}":
        "OMEMO フィンガープリント — {}",
    "OMEMO Parmak İzleri":
        "OMEMO フィンガープリント",
    "Bilgi alınamadı":
        "情報を取得できませんでした",
    "Hata: {}":
        "エラー: {}",
    "Cihaz bulunamadı":
        "デバイスが見つかりません",
    "Cihaz: {}  ({})":
        "デバイス: {}  （{}）",
    "Dışa Aktar":
        "エクスポート",
    "Sohbet geçmişi boş.":
        "会話の履歴は空です。",
    "Sohbet Dışa Aktar":
        "会話をエクスポート",
    "Tümü":
        "すべて",
    "Okunmamış":
        "未読",
    "Sabitlenmiş":
        "固定",
    "Metin":
        "テキスト",
    "Sohbet: {}\n":
        "会話: {}\n",
    "Dışa aktarma: {}\n":
        "エクスポート: {}\n",
    "Sohbet başarıyla dışa aktarıldı:\n{}":
        "会話をエクスポートしました:\n{}",
    "Hata":
        "エラー",
    "Dışa aktarma hatası: {}":
        "エクスポートのエラー: {}",
    "Ses Mesajı":
        "音声メッセージ",
    "PyAudio yüklü değil.\npip install pyaudio":
        "PyAudio がインストールされていません。\npip install pyaudio",
    "✕ İptal":
        "✕ キャンセル",
    "✍ Yazıya dök":
        "✍ 文字起こし",
    "▶ Gönder":
        "▶ 送信",
    "Ses kaydı hatası: {}":
        "録音エラー: {}",
    "Ses mesajı gönderilemedi: {}":
        "音声メッセージを送信できませんでした: {}",
    "{} atılsın mı?\nSebep (opsiyonel):":
        "{} をキックしますか？\n理由（任意）:",
    "{} yasaklansın mı?\nSebep (opsiyonel):":
        "{} を追放しますか？\n理由（任意）:",
    "{} için JID girin:":
        "{} の JID を入力:",
    "Yetki Değiştir":
        "所属を変更",
    "Kişiyi Kaldır":
        "連絡先を削除",
    "{} kaldırılsın mı?":
        "{} を削除しますか？",
    "Oda Konusu":
        "ルームの話題",
    "Yeni konu:":
        "新しい話題:",
    "Davet":
        "招待",
    "Odayı Sil":
        "ルームを削除",
    "{} kalıcı olarak silinecek.\nEmin misiniz?":
        "{} は完全に削除されます。\nよろしいですか？",
    "Sebep (opsiyonel):":
        "理由（任意）:",
    "{}🔓  Şifreleme Kapalı":
        "{}🔓  暗号化オフ",
    "  (kütüphane yüklü değil)":
        "  （ライブラリ未インストール）",
    "  (başlatılıyor…)":
        "  （起動中…）",
    "  (GPG anahtarı yok)":
        "  （GPG キーなし）",
    "🔒 OMEMO şifreleme açıldı":
        "🔒 OMEMO 暗号化をオンにしました",
    "🔑 OpenPGP şifreleme açıldı":
        "🔑 OpenPGP 暗号化をオンにしました",
    "🔓 Şifreleme kapatıldı":
        "🔓 暗号化をオフにしました",
    "Tepki seç":
        "リアクションを選択",
    "☁  Sunucuya Yükle (HTTP)":
        "☁  サーバーにアップロード（HTTP）",
    "⚡  P2P Gönder (Jingle)":
        "⚡  P2P で送信（Jingle）",
    "Dosya Seç":
        "ファイルを選択",
    "Dosya Transferi":
        "ファイル転送",
    "Bu sohbet OpenPGP ile şifreli, ama OpenPGP dosya şifreleyemez: dosya sunucuya şifresiz yüklenir, bağlantıyı gören herkes açabilir. Yine de gönderilsin mi?":
        "この会話は OpenPGP を使っていますが、OpenPGP ではファイルを暗号化できません。ファイルは暗号化されずにアップロードされ、リンクを知っている人は誰でも開けます。それでも送信しますか？",
    "{} Yükleniyor: {}…":
        "{} アップロード中: {}…",
    "Bu sohbet şifreli, ama P2P aktarım (Jingle/IBB) uçtan uca şifreli değil: dosya sunucu üzerinden şifresiz geçer. Yine de P2P ile gönderilsin mi?":
        "この会話は暗号化されていますが、P2P 転送（Jingle/IBB）はエンドツーエンド暗号化ではありません。ファイルは暗号化されずにサーバーを通ります。それでも P2P で送信しますか？",
    "Şifreli göndermek için 📎 → Sunucuya Yükle'yi kullanın (OMEMO'lu sohbette dosya şifrelenir).":
        "暗号化して送るには 📎 → サーバーにアップロード を使ってください（OMEMO の会話ではファイルが暗号化されます）。",
    "{mb} MB üzeri dosyalarda P2P yavaş olabilir. Devam edilsin mi?":
        "{mb} MB を超えるファイルは P2P だと遅くなることがあります。続けますか？",
    "Kişi çevrimdışı görünüyor; P2P başarısız olabilir.":
        "相手はオフラインのようです。P2P は失敗するかもしれません。",
    "otomatik kabul edildi":
        "自動で受け入れました",
    "Gelen Dosya Teklifi":
        "ファイルの受信申し出",
    "P2P — uçtan uca şifreli değil":
        "P2P — エンドツーエンド暗号化ではありません",
    "Kabul Et ve Kaydet":
        "受け入れて保存",
    "Dosya teklifi yanıtsız kaldı":
        "ファイルの申し出に応答がありませんでした",
    "Reddet":
        "拒否",
    "bilinmeyen hata":
        "不明なエラー",
    "❌ Dosya transferi: {}":
        "❌ ファイル転送: {}",
    "P2P başarısız oldu. Dosya sunucuya yüklenerek gönderilsin mi?":
        "P2P に失敗しました。サーバーへのアップロードで送信しますか？",
    "Dosya gönderildi":
        "ファイルを送信しました",
    "Dosya alındı":
        "ファイルを受信しました",
    "İptal":
        "キャンセル",
    "Mesaj Arama":
        "メッセージ検索",
    "🔍  Mesajlarda Ara":
        "🔍  メッセージ内を検索",
    "Aranacak metin...":
        "検索するテキスト...",
    "Tema":
        "テーマ",
    "Tema uygulandı. Bazı öğeler yeniden başlatmada yenilenir.":
        "テーマを適用しました。一部の要素は再起動後に更新されます。",
    "En az {} harfli bir kelime girin":
        "{} 文字以上の単語を入力してください",
    "Oda Oluştur":
        "ルームを作成",
    "{} adresinde zaten bir oda var.\n\nLütfen başka bir ad seçin. Oda sizinse odalar bölümündeki + (Odaya Katıl) düğmesiyle girebilirsiniz.":
        "{} にはすでにルームがあります。\n\n別の名前を選んでください。自分のルームなら、ルーム欄の +（ルームに参加）ボタンから入れます。",
    "⚠ Sunucu şifreli oda ayarlarını (yalnız üyeler / gerçek JID'ler) desteklemiyor; OMEMO bu odada çalışmaz. Oda normal ayarlarla açıldı.":
        "⚠ サーバーが暗号化ルームの設定（メンバー限定 / 実 JID）に対応していないため、このルームでは OMEMO が使えません。ルームは通常の設定で開きました。",
    "🌐 Oda hazır: adresi bilen herkes katılabilir.":
        "🌐 ルームの準備ができました: アドレスを知っている人は誰でも参加できます。",
    "🔒 Şifreli oda hazır: mesajlar OMEMO ile şifrelenir; yalnız davet ettikleriniz katılabilir (odaya sağ tık → 📨 Davet Gönder).":
        "🔒 暗号化ルームの準備ができました: メッセージは OMEMO で暗号化され、招待した人だけが参加できます（ルームを右クリック → 📨 招待を送る）。",
    "Hesap":
        "アカウント",
    "Sunucu":
        "サーバー",
    "🟢 Aktif":
        "🟢 有効",
    "🔴 Pasif":
        "🔴 無効",
    "⚫ Pasif":
        "⚫ 無効",
    "🟢 Yüklü":
        "🟢 インストール済み",
    "⚫ Yok":
        "⚫ なし",
    "Kişi Sayısı":
        "連絡先の数",
    "Aktif Odalar":
        "参加中のルーム",
    "Ayar Dosyası":
        "設定ファイル",
    "OMEMO Veri":
        "OMEMO データ",
    "Fotoğraf yayınlanamadı; eski fotoğraf korundu.":
        "写真を公開できませんでした。以前の写真のままです。",
    "🌐 Dil":
        "🌐 言語",
    "Yeni dil uygulama yeniden başlatılınca geçerli olur.":
        "新しい言語はアプリの再起動後に反映されます。",
    "● Uzakta (oto)":
        "● 離席中（自動）",
    "Göster":
        "表示",
    "Çıkış":
        "終了",
    "XMPP İstemci":
        "XMPP クライアント",
    "{} sonuç":
        "{} 件の結果",
    "🎭 GIF Ara":
        "🎭 GIF を検索",
    "💡 Üstteki kutuya yazıp Enter'a basın (ilk aramada Tenor API anahtarı sorulur)":
        "💡 上の欄に入力して Enter を押してください（初回の検索で Tenor の API キーを尋ねます）",
    "GIF Araması":
        "GIF 検索",
    "Tenor API anahtarı (Google Cloud Console → Tenor API):":
        "Tenor の API キー（Google Cloud Console → Tenor API）:",
    "⚠ GIF araması için Tenor API anahtarı gerekli":
        "⚠ GIF 検索には Tenor の API キーが必要です",
    "Sonuç bulunamadı":
        "結果なし",
    "{} GIF — tıklayınca gönderilir":
        "{} 件の GIF — クリックで送信",
    "Yedekleme / Geri Yükleme":
        "バックアップ / 復元",
    "💾 Sohbet Yedekleme":
        "💾 会話のバックアップ",
    "Yedek Kaydet":
        "バックアップを保存",
    "Yedek":
        "バックアップ",
    "Yedeklendi: {}":
        "バックアップしました: {}",
    "Yedek Yükle":
        "バックアップを読み込む",
    "Geri yüklendi: {} sohbet":
        "{} 件の会話を復元しました",
    "📤 Yedekle (JSON)":
        "📤 バックアップ（JSON）",
    "📥 Geri Yükle":
        "📥 復元",
    "OMEMO QR Doğrulama":
        "OMEMO QR 検証",
    "🔐 OMEMO Parmak İzi":
        "🔐 OMEMO フィンガープリント",
    "Yükleniyor…":
        "読み込み中…",
    "(OMEMO hazır değil)":
        "（OMEMO の準備ができていません）",
    "QR için: pip install qrcode":
        "QR には: pip install qrcode",
    "Kopyalandı":
        "コピーしました",
    "Parmak izi panoya kopyalandı":
        "フィンガープリントをクリップボードにコピーしました",
    "📋 Kopyala":
        "📋 コピー",
    "Sohbet Arka Planı":
        "会話の背景",
    "🖼 Sohbet Arka Planı":
        "🖼 会話の背景",
    "Resim":
        "画像",
    "Arka Plan Seç":
        "背景を選択",
    "Arka Plan Rengi":
        "背景色",
    "🖼 Resim Seç":
        "🖼 画像を選択",
    "🎨 Renk Seç":
        "🎨 色を選択",
    "↩ Varsayılana Dön":
        "↩ 既定に戻す",
    "↩ Yanıtlanacak mesaj yok":
        "↩ 返信するメッセージがありません",
    "✏ Düzenlenecek mesajım yok":
        "✏ 編集できる自分のメッセージがありません",
    "🗑 Silinecek mesajım yok":
        "🗑 削除できる自分のメッセージがありません",
    "Mesaj Zamanla":
        "メッセージを予約",
    "Mesaj:":
        "メッセージ:",
    "Kaç dakika sonra gönderilsin:":
        "何分後に送信するか:",
    "30 dk":
        "30分",
    "1 saat":
        "1時間",
    "Özel (dk):":
        "カスタム（分）:",
    "⏰ Zamanla":
        "⏰ 予約",
    "⏰ Zamanlanmış mesaj ({} dk sonra): {}":
        "⏰ 予約メッセージ（{} 分後）: {}",
    "Toplu Mesaj":
        "一斉送信",
    "📢 Toplu Mesaj Gönder":
        "📢 一斉送信する",
    "Alıcıları seçin:":
        "宛先を選択:",
    "0 kişi seçildi":
        "0 件の連絡先を選択中",
    "{} kişi seçildi":
        "{} 件の連絡先を選択中",
    "{} kişiye gönderildi":
        "{} 件の連絡先に送信しました",
    "📨 Gönder":
        "📨 送信",
    "Otomatik Tema Geçişi":
        "テーマの自動切り替え",
    "🌓 Otomatik Tema Geçişi":
        "🌓 テーマの自動切り替え",
    "Otomatik tema geçişini etkinleştir":
        "テーマの自動切り替えを有効にする",
    "Gündüz teması:":
        "昼のテーマ:",
    "Gece teması:":
        "夜のテーマ:",
    "Gündüz başlangıç saati:":
        "昼の開始時刻:",
    "Gece başlangıç saati:":
        "夜の開始時刻:",
    "Kaydet":
        "保存",
    "Uygulama Kilidi":
        "アプリのロック",
    "Mevcut PIN ayarlanmış ✓":
        "PIN は設定済みです ✓",
    "PIN Doğrula":
        "PIN を確認",
    "Mevcut PIN:":
        "現在の PIN:",
    "PIN kaldırıldı":
        "PIN を削除しました",
    "🗑 PIN'i Kaldır":
        "🗑 PIN を削除",
    "Yeni PIN belirleyin:":
        "新しい PIN を設定:",
    "Tekrar girin:":
        "もう一度入力:",
    "PIN en az 4 karakter olmalı":
        "PIN は 4 文字以上にしてください",
    "PIN'ler eşleşmiyor":
        "PIN が一致しません",
    "PIN ayarlandı ✓":
        "PIN を設定しました ✓",
    "🔒 PIN Ayarla":
        "🔒 PIN を設定",
    "Proxy Ayarları":
        "プロキシ設定",
    "🔒 Proxy / SOCKS Ayarları":
        "🔒 プロキシ / SOCKS 設定",
    "Proxy türü:":
        "プロキシの種類:",
    "Yok":
        "なし",
    "Adres:":
        "アドレス:",
    "💡 Tor için: SOCKS5, 127.0.0.1:9050":
        "💡 Tor の場合: SOCKS5、127.0.0.1:9050",
    "Yalnız XMPP bağlantısı proxy'den geçer; dosya yükleme/indirme, bağlantı önizlemesi, GIF ve AI istekleri geçmez. Kimlik doğrulamalı proxy desteklenmez.":
        "プロキシを通るのは XMPP 接続だけです。ファイルのアップロード/ダウンロード、リンクのプレビュー、GIF、AI の要求は通りません。認証付きのプロキシには対応していません。",
    "Ayarlar kaydedildi.\nBir sonraki bağlantıda uygulanır (ör. uygulamayı yeniden başlatınca).":
        "設定を保存しました。\n次回の接続時に反映されます（アプリの再起動後など）。",
    "Kullanılabilir komutlar:\n/help — Bu yardım\n/clear — Sohbet geçmişini temizle\n/nick <isim> — Oda takma adını değiştir\n/topic <konu> — Oda konusunu değiştir\n/invite <jid> — Odaya davet et\n/kick <nick> — Odadan at\n/ban <jid> — Yasakla\n/join <oda> — Odaya katıl\n/leave — Odadan ayrıl\n/status <mesaj> — Durum mesajı değiştir\n/ping — Sunucu ping\n/time — Şu anki saat\n/broadcast — Toplu mesaj\n/schedule — Mesaj zamanla\n/reply <metin> — Son gelen mesaja yanıt ver\n/react <emoji> — Son gelen mesaja tepki ekle\n/edit <metin> — Son mesajımı düzenle\n/del — Son mesajımı sil":
        "使えるコマンド:\n/help — このヘルプ\n/clear — 会話履歴を消去\n/nick <名前> — ルームでのニックネームを変更\n/topic <話題> — ルームの話題を変更\n/invite <jid> — ルームに招待\n/kick <ニックネーム> — ルームからキック\n/ban <jid> — 追放\n/join <ルーム> — ルームに参加\n/leave — ルームから退出\n/status <メッセージ> — ステータスメッセージを変更\n/ping — サーバーに ping\n/time — 現在時刻\n/broadcast — 一斉送信\n/schedule — メッセージを予約\n/reply <テキスト> — 最後に受信したメッセージに返信\n/react <絵文字> — 最後に受信したメッセージにリアクション\n/edit <テキスト> — 自分の最後のメッセージを編集\n/del — 自分の最後のメッセージを削除",
    "📶 Son ping: {}ms":
        "📶 直近の ping: {}ms",
    "Takma ad değiştirildi: {}":
        "ニックネームを変更しました: {}",
    "Konu değiştirildi: {}":
        "話題を変更しました: {}",
    "Davet gönderildi: {}":
        "招待を送りました: {}",
    "Kullanıcı atıldı: {}":
        "ユーザーをキックしました: {}",
    "Yasakla":
        "追放",
    "Kullanıcı yasaklanıyor: {}":
        "ユーザーを追放中: {}",
    "Odaya katılınıyor: {}":
        "ルームに参加中: {}",
    "Odadan ayrılınıyor: {}":
        "ルームから退出中: {}",
    "Durum güncellendi: {}":
        "ステータスを更新しました: {}",
    "😊 Tepki verilecek mesaj yok":
        "😊 リアクションするメッセージがありません",
    "Bilinmeyen komut: {}\n/help yazarak yardım alabilirsiniz":
        "不明なコマンド: {}\n/help でヘルプを表示できます",
    "Sohbet — {}":
        "会話 — {}",
    "Bölünmüş Ekran":
        "画面分割",
    "En az 2 sohbet gerekli":
        "会話が 2 つ以上必要です",
    "Bölünmüş Ekran — İkinci sohbet seçin":
        "画面分割 — 2 つ目の会話を選択",
    "✓ Bağlandı":
        "✓ 接続しました",
    "✓ Bağlantı Kuruldu":
        "✓ 接続が確立しました",
    "Sunucuya bağlanıldı":
        "サーバーに接続しました",
    "Mesaj — {}":
        "メッセージ — {}",
    "Yeni mesaj":
        "新しいメッセージ",
    "  Arama hatası: {}":
        "  検索エラー: {}",
    "  Sonuç bulunamadı":
        "  結果なし",
    "✓ {} odasına katıldı":
        "✓ {} に参加しました",
    "ℹ {} zaten vardı: mevcut odaya katıldınız, ayarları değiştirilmedi.":
        "ℹ {} はすでに存在していました: 既存のルームに参加し、設定は変更していません。",
    "Bir kişi veya oda seçin":
        "連絡先かルームを選択してください",
    "📌 Konu: {}":
        "📌 話題: {}",
    "MUC Daveti":
        "MUC への招待",
    "{} odasına davet edildiniz.\nSebep: {}\n\nKabul et?":
        "{} に招待されました。\n理由: {}\n\n承諾しますか？",
    "Arkadaşlık İsteği":
        "連絡先リクエスト",
    "{} sizi takip etmek istiyor.\nKabul et?":
        "{} があなたをフォローしたいと言っています。\n承諾しますか？",
    "Oda Keşfi":
        "ルームの検索",
    "Giriş Hatası":
        "ログインエラー",
    "⚠ Bağlantı kesildi":
        "⚠ 切断されました",
    "⚠ Bağlanılamadı":
        "⚠ 接続できませんでした",
    "⚠ Bağlantı başarısız{}: {}":
        "⚠ 接続に失敗しました{}: {}",
    "Bağlantı kesildi":
        "切断されました",
    "📊 Anket Oluştur":
        "📊 アンケートを作成",
    "Soru:":
        "質問:",
    "Seçenekler (her satır bir seçenek):":
        "選択肢（1 行に 1 つ）:",
    "Evet\nHayır\nKararsızım":
        "はい\nいいえ\n未定",
    "Anket":
        "アンケート",
    "Soru ve en az 2 seçenek gerekli":
        "質問と 2 つ以上の選択肢が必要です",
    "\n💡 Oy vermek için ilgili emoji ile tepki ekleyin":
        "\n💡 投票するには対応する絵文字でリアクションしてください",
    "📊 Anketi Gönder":
        "📊 アンケートを送信",
    "Hikaye":
        "ストーリー",
    "Fotoğraf okunamadı: {}":
        "写真を読み込めませんでした: {}",
    "📖 Hikaye":
        "📖 ストーリー",
    "Durum yayınlandı":
        "ステータスを公開しました",
    "📋 XMPP Log Görüntüleyici":
        "📋 XMPP ログビューアー",
    "📋 XMPP XML Trafik Logu":
        "📋 XMPP XML 通信ログ",
    "Hesap: {}\n":
        "アカウント: {}\n",
    "Bağlı: {}\n\n":
        "接続: {}\n\n",
    "⚠ Filter eklenemedi\n":
        "⚠ フィルターを追加できませんでした\n",
    "🗑 Temizle":
        "🗑 クリア",
    "📤 Dışa Aktar":
        "📤 エクスポート",
    "Sunucu başlatılamadı (port {}):\n{}":
        "サーバーを起動できませんでした（ポート {}）:\n{}",
    "🔴 Hata: {}":
        "🔴 エラー: {}",
    "🟢 Çalışıyor":
        "🟢 実行中",
    "⚫ Durduruldu":
        "⚫ 停止中",
    "⏳ Başlatılıyor…":
        "⏳ 起動中…",
    "⏳ Durduruluyor…":
        "⏳ 停止中…",
    "▶ Başlat":
        "▶ 開始",
    "⏹ Durdur":
        "⏹ 停止",
    "Bağlantı durumu":
        "接続状態",
    "Kişi listesi":
        "連絡先リスト",
    "Oda listesi":
        "ルーム一覧",
    "Mesaj geçmişi":
        "メッセージ履歴",
    "Mesaj gönder {to, message}":
        "メッセージを送信 {to, message}",
    "Bağlantı Kurulamadı":
        "接続できませんでした",
    "20 saniye içinde sunucuya bağlanılamadı.\n\nSunucu: {}:{}{}\nSon hata: {}\n\nArka planda yeniden bağlanma denemeleri sürüyor.\nDenemeye devam edilsin mi?\n(\"Hayır\" → giriş ekranına dönülür)":
        "20 秒以内にサーバーに接続できませんでした。\n\nサーバー: {}:{}{}\n最後のエラー: {}\n\nバックグラウンドで再接続を続けています。\n試行を続けますか？\n（\"いいえ\" → ログイン画面に戻る）",
    "Kapat":
        "閉じる",
    "Ne yapmak istiyorsun?":
        "どうしますか？",
    "  Gizle (Tepsiye)  ":
        "  隠す（トレイへ）  ",
    "  Uygulamadan Cik  ":
        "  アプリを終了  ",
    "  Iptal  ":
        "  キャンセル  ",
    "🔁 Hesap Değişimi":
        "🔁 アカウントを切り替え",
    "{} hesabına geçiliyor…":
        "{} に切り替えています…",
    "Hesap değiştirilemedi: {}":
        "アカウントを切り替えられませんでした: {}",
    "XMPP bağlantı thread'i durdu: {}":
        "XMPP 接続スレッドが停止しました: {}",
    "Bağlanıyor… {}":
        "接続中… {}",
    "🔑 Uygulama Kilidi":
        "🔑 アプリのロック",
    "🔑 PIN Girin":
        "🔑 PIN を入力",
    "Yanlış PIN":
        "PIN が違います",
    "Giriş":
        "ログイン",
    "aesgcm bağlantısı yalnız https yüklemeden kurulur":
        "aesgcm リンクは https のアップロードからしか作れません",
    "Çevrimiçi":
        "オンライン",
    "Uzakta":
        "離席中",
    "Meşgul":
        "取り込み中",
    "Uzun süre uzakta":
        "長時間離席",
    "Model beklenen biçimde yanıt vermedi; tekrar deneyin.":
        "モデルが想定した形式で答えませんでした。もう一度お試しください。",
    "Hangi kişi ya da oda için? Adını yazın ya da önce sohbeti açın.":
        "どの連絡先またはルームですか？名前を書くか、先に会話を開いてください。",
    "Hangi odaya katılmak istiyorsunuz?":
        "どのルームに参加しますか？",
    "Ne sormak istiyorsunuz?":
        "何を聞きたいですか？",
    "Mesaj ya da hatırlatıcı metni eksik.":
        "メッセージまたはリマインダーの本文がありません。",
    "Hangi durum? (çevrimiçi, uzakta, meşgul)":
        "どのステータスにしますか？（オンライン、離席中、取り込み中）",
    "Hatırlatıcı için tarih ve saat gerekli (ör. yarın 10:00).":
        "リマインダーには日時が必要です（例: 明日 10:00）。",
    "Hatırlatıcı zamanı geçmişte kalıyor.":
        "リマインダーの時刻はすでに過ぎています。",
    "📨 Mesaj gönderilsin mi?":
        "📨 メッセージを送信しますか？",
    "Alıcı: {}\n“{}”":
        "宛先: {}\n「{}」",
    "⏰ Hatırlatıcı kurulsun mu?":
        "⏰ リマインダーを設定しますか？",
    "🚪 Odaya katılınsın mı?":
        "🚪 ルームに参加しますか？",
    "● Durum değiştirilsin mi?":
        "● ステータスを変更しますか？",
    "Geçmişe sor: ":
        "履歴に質問: ",
    "📬 Okunmamışları özetle":
        "📬 未読を要約",
    "📅 Görevleri çıkar":
        "📅 タスクを抽出",
    "❓ Bekleyen sorular":
        "❓ 未回答の質問",
    "✍ Taslaklar":
        "✍ 下書き",
    "🚫 Bu mesaj silindi":
        "🚫 このメッセージは削除されました",
    "🎤 Ses mesajı":
        "🎤 音声メッセージ",
    "(Konuşma algılanmadı)":
        "（音声が検出されませんでした）",
    "[…yanıt uzunluk sınırına takıldı ve kesildi]":
        "[…回答が長さの上限に達したため途中で切れました]",
    "AI asistanı kapalı. ⚙ AI Ayarları'ndan bir sağlayıcı seçin.":
        "AI アシスタントはオフです。⚙ AI 設定でプロバイダーを選んでください。",
    "Bu sohbet şifreli. Şifreli içerik izniniz olmadan buluta (Claude) gönderilmez.":
        "この会話は暗号化されています。暗号化された内容は、あなたの許可なくクラウド（Claude）に送られません。",
    "☁ Claude (bulut) · {}":
        "☁ Claude（クラウド）· {}",
    "🖥 Yerel (Ollama) · {}":
        "🖥 ローカル（Ollama）· {}",
    "AI kapalı":
        "AI オフ",
    "Yanıt boyut sınırını aştı.":
        "回答がサイズの上限を超えました。",
    "Geçersiz adres: {!r} (http/https olmalı)":
        "アドレスが正しくありません: {!r}（http/https である必要があります）",
    "Ollama'da '{}' modeli yok. Terminalde kurun:\n  ollama pull {}":
        "Ollama に '{}' モデルがありません。ターミナルでインストールしてください:\n  ollama pull {}",
    "Ollama hatası ({}): {}":
        "Ollama のエラー（{}）: {}",
    "Ollama'ya ulaşılamadı ({}).\nOllama çalışıyor mu? Terminalde: ollama serve":
        "Ollama に接続できませんでした（{}）。\nOllama は起動していますか？ターミナルで: ollama serve",
    "Yerel model zamanında yanıt vermedi.":
        "ローカルモデルが時間内に応答しませんでした。",
    "Ollama'dan geçersiz yanıt alındı.":
        "Ollama から無効な応答が返りました。",
    "Ollama yanıtı yarıda kesildi.":
        "Ollama の応答が途中で切れました。",
    "Ollama hatası: {}":
        "Ollama のエラー: {}",
    "Model yanıtı uzunluk sınırına takıldı; daha kısa bir sohbet aralığıyla tekrar deneyin.":
        "モデルの回答が長さの上限に達しました。会話の範囲を短くしてもう一度お試しください。",
    "Yerel model boş yanıt döndürdü.":
        "ローカルモデルが空の回答を返しました。",
    "Gömme modeli beklenmeyen yanıt döndürdü.":
        "埋め込みモデルが想定外の応答を返しました。",
    "Claude için 'anthropic' paketi kurulu değil:\n  .venv-xmpp/bin/python -m pip install anthropic":
        "Claude 用の 'anthropic' パッケージがインストールされていません:\n  .venv-xmpp/bin/python -m pip install anthropic",
    "Claude API anahtarı geçersiz ya da eksik (⚙ AI Ayarları).":
        "Claude の API キーが正しくないか、ありません（⚙ AI 設定）。",
    "Bu API anahtarının bu modele erişim izni yok.":
        "この API キーではこのモデルを使えません。",
    "Claude modeli bulunamadı: {}":
        "Claude のモデルが見つかりません: {}",
    "Claude hız sınırına takıldı; biraz sonra tekrar deneyin.":
        "Claude のレート制限に達しました。少し待ってからお試しください。",
    "Claude isteği kabul etmedi: {}":
        "Claude がリクエストを受け付けませんでした: {}",
    "Claude sunucu hatası ({}); daha sonra tekrar deneyin.":
        "Claude のサーバーエラー（{}）です。しばらくしてからお試しください。",
    "Claude'a bağlanılamadı (internet bağlantısı?).":
        "Claude に接続できませんでした（インターネット接続は？）。",
    "Claude hatası: {}":
        "Claude のエラー: {}",
    "Claude bu isteği güvenlik nedeniyle yanıtlamadı.":
        "Claude は安全上の理由でこのリクエストに答えませんでした。",
    "Claude boş yanıt döndürdü.":
        "Claude が空の回答を返しました。",
    "✍ Yazımı düzelt":
        "✍ つづりを直す",
    "🎩 Resmîleştir":
        "🎩 丁寧にする",
    "😊 Samimileştir":
        "😊 親しみやすくする",
    "✂ Kısalt":
        "✂ 短くする",
    "🌐 İngilizceye çevir":
        "🌐 英語に翻訳",
    "Bilinmeyen düzenleme modu: {}":
        "不明な編集モード: {}",
    "Model geçerli JSON döndürmedi; tekrar deneyin.":
        "モデルが有効な JSON を返しませんでした。もう一度お試しください。",
    "Başlığı boş bir öğe var.":
        "タイトルが空の項目があります。",
    "“{}”: tarih YYYY-AA-GG biçiminde olmalı.":
        "「{}」: 日付は YYYY-MM-DD の形式にしてください。",
    "“{}”: saat SS:DD biçiminde olmalı.":
        "「{}」: 時刻は HH:MM の形式にしてください。",
    "“{}”: bitiş saati SS:DD biçiminde olmalı.":
        "「{}」: 終了時刻は HH:MM の形式にしてください。",
    "“{}”: saat verildiyse tarih de gerekli.":
        "「{}」: 時刻を指定する場合は日付も必要です。",
    "Sohbetten: “{}”":
        "会話から: 「{}」",
    "Görsel biçimi tanınmadı.":
        "画像の形式を認識できませんでした。",
    "Görsel açılamadı.":
        "画像を開けませんでした。",
    "Medya indirilemedi.":
        "メディアをダウンロードできませんでした。",
    "Ses→metin için faster-whisper gerekli (yerel çalışır):\n  .venv-xmpp/bin/python -m pip install faster-whisper \"av<19\"":
        "文字起こしには faster-whisper が必要です（ローカルで動作）:\n  .venv-xmpp/bin/python -m pip install faster-whisper \"av<19\"",
    "Whisper modeli yüklenemedi ({}): {}":
        "Whisper モデルを読み込めませんでした（{}）: {}",
    "Ses çözücü (PyAV) faster-whisper ile uyumsuz. Düzeltmek için:\n  .venv-xmpp/bin/python -m pip install \"av<19\"":
        "音声デコーダー（PyAV）が faster-whisper と互換性がありません。修正するには:\n  .venv-xmpp/bin/python -m pip install \"av<19\"",
    "Ses yazıya dökülemedi: {}":
        "音声を文字起こしできませんでした: {}",
    "🔒 Şifreli mesaj (arşivde çözülemedi)":
        "🔒 暗号化されたメッセージ（アーカイブでは復号できませんでした）",
    "[İletildi — {}]\n{}":
        "[転送 — {}]\n{}",
    "Oda adresi boş":
        "ルームのアドレスが空です",
    "Geçersiz oda adresi: {!r} — oda adında {}":
        "ルームのアドレスが正しくありません: {!r} — ルーム名に {}",
    " (ör. {})":
        " （例: {}）",
    "Oda adresinde sunucu yok: {!r}":
        "ルームのアドレスにサーバーがありません: {!r}",
    "Geçersiz oda adresi: {!r}":
        "ルームのアドレスが正しくありません: {!r}",
    "boşluk kullanılamaz":
        "空白は使えません",
    "şu karakterler kullanılamaz: ":
        "次の文字は使えません: ",
    "Oda adı girin.":
        "ルーム名を入力してください。",
    "Oda adından adres üretilemedi; harf ya da rakam kullanın (ör. proje-ekibi).":
        "ルーム名からアドレスを作れませんでした。英字か数字を使ってください（例: project-team）。",
    "Lütfen bir JID girin.":
        "JID を入力してください。",
    "Geçersiz JID — @ işareti olmalı (ör: ali@sunucu.tld)":
        "JID が正しくありません — @ が必要です（例: ali@server.tld）",
    "Geçersiz JID — {}: {!r}":
        "JID が正しくありません — {}: {!r}",
    "Geçersiz JID: {!r}":
        "JID が正しくありません: {!r}",
    "Mesaj yazın...":
        "メッセージを入力...",
    "Tepki Ekle":
        "リアクションを追加",
    "Bir sohbet seçin":
        "会話を選択",
    "Bir kişi veya oda seçerek konuşmaya başlayın":
        "連絡先かルームを選んで会話を始めましょう",
    "Sohbete Başlayın":
        "会話を始めましょう",
    "yazıyor":
        "入力中",
    "⚠ OMEMO mesajı alındı ancak OMEMO hazır değil — çözülemedi":
        "⚠ OMEMO メッセージを受信しましたが、OMEMO の準備ができていないため復号できませんでした",
    "OMEMO kütüphanesi yüklü değil (slixmpp-omemo).":
        "OMEMO ライブラリがインストールされていません（slixmpp-omemo）。",
    "OMEMO henüz hazır değil — lütfen birkaç saniye bekleyin.":
        "OMEMO の準備がまだできていません — 数秒お待ちください。",
    "Mesaj gönderilemedi: {}":
        "メッセージを送信できませんでした: {}",
    "Düzenleme hatası: {}":
        "編集のエラー: {}",
    "Silme hatası: {}":
        "削除のエラー: {}",
    "Tepki hatası: {}":
        "リアクションのエラー: {}",
    "Yanıt hatası: {}":
        "返信のエラー: {}",
    "İletme hatası: {}":
        "転送のエラー: {}",
    "Bu takma ad odada kullanılıyor; başka bir takma ad deneyin.":
        "このニックネームはルームで使われています。別のニックネームにしてください。",
    "Oda parola istiyor.":
        "このルームにはパスワードが必要です。",
    "Bu odaya girişiniz yasaklanmış.":
        "このルームへの参加は禁止されています。",
    "Oda yalnız üyelere açık.":
        "このルームはメンバー限定です。",
    "Oda bulunamadı (adres yanlış ya da oda kilitli olabilir).":
        "ルームが見つかりません（アドレスの誤りか、ルームがロックされている可能性があります）。",
    "Oda sunucusu bulunamadı (adresi kontrol edin).":
        "ルームのサーバーが見つかりません（アドレスを確認してください）。",
    "Oda dolu ya da şu an kullanılamıyor.":
        "ルームが満員か、現在利用できません。",
    "Bu sunucuda yeni oda oluşturma izniniz yok.":
        "このサーバーでルームを作成する権限がありません。",
    "Geçersiz oda adresi ya da takma ad.":
        "ルームのアドレスまたはニックネームが正しくありません。",
    "Oda sunucusuna ulaşılamadı (zaman aşımı).":
        "ルームのサーバーに接続できませんでした（タイムアウト）。",
    "Oda taşınmış ya da kaldırılmış.":
        "ルームは移動または削除されました。",
    "Oda mesajı gönderilemedi: {}":
        "ルームにメッセージを送信できませんでした: {}",
    "'{}' sunucusunda oda bulunamadi.":
        "'{}' サーバーにルームは見つかりませんでした。",
    "Sunucu bulunamadi (DNS hatasi)":
        "サーバーが見つかりません（DNS エラー）",
    "Sunucu kesfetme desteklemiyor":
        "サーバーがルーム検索に対応していません",
    "Sunucu yanit vermedi (zaman asimi)":
        "サーバーが応答しませんでした（タイムアウト）",
    "Erisim reddedildi":
        "アクセスが拒否されました",
    "⚠ '{}': {}. Genel Ara sekmesini deneyin.":
        "⚠ '{}': {}。「公開検索」タブをお試しください。",
    "Oda katılım hatası: {} {} sn içinde yanıt vermedi; oda sunucusu kapalı ya da adres yanlış olabilir.":
        "ルーム参加のエラー: {} が {} 秒以内に応答しませんでした。ルームのサーバーが停止しているか、アドレスが誤っている可能性があります。",
    "{} odasına katılınamadı: {}":
        "{} に参加できませんでした: {}",
    "Oda katılım hatası: {}":
        "ルーム参加のエラー: {}",
    "Oda ayrılma hatası: {}":
        "ルーム退出のエラー: {}",
    "Konu değiştirme hatası: {}":
        "話題変更のエラー: {}",
    "✓ {} odadan atıldı.":
        "✓ {} をルームからキックしました。",
    "Kick hatası: {}":
        "キックのエラー: {}",
    "✓ {} yasaklandı.":
        "✓ {} を追放しました。",
    "Ban hatası: {}":
        "追放のエラー: {}",
    "Rol değiştirme hatası: {}":
        "役割変更のエラー: {}",
    "Yetki değiştirme hatası: {}":
        "所属変更のエラー: {}",
    "✓ Takma adın değişti: {}":
        "✓ ニックネームを変更しました: {}",
    "Takma ad değiştirilemedi: {}":
        "ニックネームを変更できませんでした: {}",
    "✓ {} davet edildi → {}":
        "✓ {} を招待しました → {}",
    "Davet hatası: {}":
        "招待のエラー: {}",
    "Oda ayarları alınamadı: {}":
        "ルーム設定を取得できませんでした: {}",
    "✓ {} ayarları güncellendi.":
        "✓ {} の設定を更新しました。",
    "Oda ayar kaydetme hatası: {}":
        "ルーム設定の保存エラー: {}",
    "✓ {} odası silindi.":
        "✓ ルーム {} を削除しました。",
    "Oda silme hatası: {}":
        "ルーム削除のエラー: {}",
    "ℹ {} adresinde oda yoktu; sunucunun varsayılan ayarlarıyla yeni bir oda oluşturuldu.":
        "ℹ {} にはルームがなかったため、サーバーの既定設定で新しいルームを作成しました。",
    "Yeni oda kullanıma açılamadı: {}":
        "新しいルームを使える状態にできませんでした: {}",
    "Oda yapılandırılamadı (sahibi olarak ⋮ → Oda Yönetimi'ni kullanın): {}":
        "ルームを設定できませんでした（オーナーとして ⋮ → ルーム管理 を使ってください）: {}",
    "✓ Yer imleri kaydedildi":
        "✓ ブックマークを保存しました",
    "Yer imi kaydetme hatası: {}":
        "ブックマーク保存のエラー: {}",
    "✓ {} isteği kabul etti":
        "✓ {} がリクエストを承諾しました",
    "✗ {} sizi kaldırdı":
        "✗ {} があなたを削除しました",
    "genel sunucu hatası":
        "サーバーの一般的なエラー",
    "kural seti izin vermedi":
        "ルールにより許可されていません",
    "ağa ulaşılamıyor":
        "ネットワークに到達できません",
    "sunucuya ulaşılamıyor":
        "ホストに到達できません",
    "bağlantı reddedildi":
        "接続が拒否されました",
    "zaman aşımı (TTL)":
        "タイムアウト（TTL）",
    "komut desteklenmiyor":
        "コマンドに対応していません",
    "adres türü desteklenmiyor":
        "アドレスの種類に対応していません",
    "Proxy adresi girin (Tor için 127.0.0.1).":
        "プロキシのアドレスを入力してください（Tor なら 127.0.0.1）。",
    "Geçerli bir port girin (1–65535).":
        "正しいポートを入力してください（1–65535）。",
    "Proxy bağlantıyı beklenmedik şekilde kapattı":
        "プロキシが接続を予期せず閉じました",
    "Geçersiz hedef adı: {!r}":
        "接続先の名前が正しくありません: {!r}",
    "SOCKS5 değil: proxy türünü kontrol edin":
        "SOCKS5 ではありません: プロキシの種類を確認してください",
    "SOCKS5 proxy kimlik doğrulama istiyor (desteklenmiyor)":
        "SOCKS5 プロキシが認証を求めています（未対応）",
    "hata kodu {}":
        "エラーコード {}",
    "SOCKS5: geçersiz proxy yanıtı":
        "SOCKS5: プロキシの応答が正しくありません",
    "SOCKS4: istek reddedildi (kod {})":
        "SOCKS4: リクエストが拒否されました（コード {}）",
    "HTTP proxy yanıtı çok uzun":
        "HTTP プロキシの応答が長すぎます",
    "HTTP proxy reddetti: {}":
        "HTTP プロキシが拒否しました: {}",
    "Proxy'ye bağlanılamadı ({}:{}): {}":
        "プロキシに接続できませんでした（{}:{}）: {}",
    "Proxy zaman aşımı":
        "プロキシのタイムアウト",
    "az önce":
        "たった今",
    "{} dakika önce":
        "{} 分前",
    "{} saat önce":
        "{} 時間前",
    "dün":
        "昨日",
    "{} gün önce":
        "{} 日前",
    "Yanıtla: {} — {}":
        "返信: {} — {}",
    "Anthropic API anahtarı":
        "Anthropic の API キー",
    "OpenAI API anahtarı":
        "OpenAI の API キー",
    "GitHub belirteci":
        "GitHub のトークン",
    "AWS erişim anahtarı":
        "AWS のアクセスキー",
    "Google API anahtarı":
        "Google の API キー",
    "Slack belirteci":
        "Slack のトークン",
    "Stripe gizli anahtarı":
        "Stripe のシークレットキー",
    "Oturum belirteci (JWT)":
        "セッショントークン（JWT）",
    "Özel anahtar (private key)":
        "秘密鍵",
    "Parola / PIN":
        "パスワード / PIN",
    "Kart numarası":
        "カード番号",
    "T.C. kimlik no":
        "トルコの身分証番号",
    "Bu grup sohbetine şifresiz gönderilecek mesaj":
        "このグループチャットに暗号化せずに送るメッセージには",
    "Bu mesaj şifresiz gönderilecek ve":
        "このメッセージは暗号化せずに送信されます。また",
    "{} şu hassas bilgileri içeriyor gibi görünüyor:\n\n":
        "{}、次の機密情報が含まれているようです:\n\n",
    "\n\nŞifresiz mesajları sunucu yöneticileri görebilir ve sunucu arşivinde (MAM) saklanabilir. Göndermeden önce 🔒 ile şifrelemeyi açabilirsiniz.\n\nYine de gönderilsin mi?":
        "\n\nサーバー管理者は暗号化されていないメッセージを見ることができ、サーバーのアーカイブ（MAM）に保存されることもあります。送信前に 🔒 で暗号化をオンにできます。\n\nそれでも送信しますか？",
    "Dosya yükleme hatası: {}":
        "ファイルのアップロードエラー: {}",
    "🔒 Dosya şifreli yüklendi: {}":
        "🔒 ファイルを暗号化してアップロードしました: {}",
    "✓ Dosya gönderildi: {}":
        "✓ ファイルを送信しました: {}",
    "Dosya gönderme hatası: {}":
        "ファイル送信のエラー: {}",
    "OMEMO kütüphanesi yüklü değil (slixmpp-omemo) — dosya gönderilmedi.":
        "OMEMO ライブラリがインストールされていません（slixmpp-omemo）— ファイルは送信していません。",
    "OMEMO henüz hazır değil — dosya gönderilmedi; birkaç saniye sonra tekrar deneyin.":
        "OMEMO の準備がまだできていません — ファイルは送信していません。数秒後にもう一度お試しください。",
    "Sesli okuma için yerel bir ses motoru gerekli. Örneğin:\n  sudo pacman -S espeak-ng\nDaha doğal ses için Piper: piper-tts kurun ve ✨ → AI Ayarları'nda Türkçe bir ses modelinin (.onnx) yolunu girin.":
        "読み上げにはローカルの音声エンジンが必要です。例:\n  sudo pacman -S espeak-ng\nより自然な声にするには piper-tts をインストールし、✨ → AI 設定 で音声モデル（.onnx）のパスを入力してください。",
    "Piper için `piper` komutu, bir ses modeli (.onnx) ve bir ses çalar (pw-play/paplay/aplay) gerekli.\n\n":
        "Piper には `piper` コマンド、音声モデル（.onnx）、音声プレーヤー（pw-play/paplay/aplay）が必要です。\n\n",
    "Seçili ses motoru bulunamadı: {}\n\n":
        "選んだ音声エンジンが見つかりません: {}\n\n",
    "Okunacak metin yok.":
        "読み上げるテキストがありません。",
    "ℹ Sesli okuma motoru yok (isteğe bağlı): sudo pacman -S espeak-ng":
        "ℹ 読み上げエンジンがありません（任意）: sudo pacman -S espeak-ng",
    "✓ Sesli okuma: {}":
        "✓ 読み上げ: {}",
    "1 dk":
        "1分",
    "10 dk":
        "10分",
    "15 dk":
        "15分",
    "kullanici@sunucu.tld":
        "user@server.tld",
    "oda@conference.sunucu.tld":
        "room@conference.server.tld",
    "yeni-oda":
        "new-room",
    "muc.sunucu.tld":
        "muc.server.tld",
    "Koyu":
        "ダーク",
    "Açık":
        "ライト",
    "Gece mavisi":
        "ナイトブルー",
}
