"""OMEMO'lu sohbette giden dosyalar şifrelenir (aesgcm://, XEP-0454).

Kanıt: `xmppcore/transfers.py` dosyayı her zaman düz HTTP Upload ile
yüklüyordu; sunucu (ve bağlantıyı gören herkes) dosyayı okuyabiliyordu.
📎 menüsü OMEMO modundaki sohbette bile bağlantıyı şifresiz mesajla
gönderiyordu. Telefondaki istemciler (Conversations, Monocles, Monal)
OMEMO açıkken dosyayı AES-256-GCM ile şifreleyip `aesgcm://…#<iv><anahtar>`
bağlantısını OMEMO'lu gövdede gönderir; artık masaüstü de böyle gönderir.
"""
import asyncio
import os
import types

import pytest
from test_chatview_contracts import _upload_window

import xmpp
from xmppcore import aesgcm
from xmppcore.transfers import TransferMixin

PLAIN = b"\x89PNG gizli tatil fotografi" * 50


# ── Çekirdek: şifreleme ve bağlantı ──────────────────────────────────────────

def test_encrypt_roundtrip_through_aesgcm_url():
    blob, key, iv = aesgcm.encrypt(PLAIN)
    assert len(key) == 32 and len(iv) == 12
    assert blob != PLAIN and len(blob) == len(PLAIN) + 16     # GCM etiketi
    url = aesgcm.to_url("https://up.example.org/slot/ab12.png", key, iv)
    assert url.startswith("aesgcm://up.example.org/slot/ab12.png#")
    https, k2, iv2 = aesgcm.parse(url)
    assert https == "https://up.example.org/slot/ab12.png"
    assert aesgcm.decrypt(blob, k2, iv2) == PLAIN
    # Görsel/ses algılaması gelen bağlantılarla aynı deseni kullanır
    assert aesgcm.URL_RE.findall(f"bak {url} tamam") == [url]


def test_each_file_gets_a_fresh_key_and_iv():
    (_b1, k1, iv1), (_b2, k2, iv2) = aesgcm.encrypt(b"x"), aesgcm.encrypt(b"x")
    assert k1 != k2 and iv1 != iv2


@pytest.mark.parametrize("url", ["http://up.example.org/a.png", "ftp://h/a",
                                 "https:///a.png"])
def test_to_url_requires_https_upload(url):
    with pytest.raises(ValueError):
        aesgcm.to_url(url, bytes(32), bytes(12))


def test_upload_name_hides_original_name_but_keeps_extension():
    name = aesgcm.upload_name("/home/u/Gizli Sözleşme.PDF")
    assert name.endswith(".pdf") and "Gizli" not in name
    assert aesgcm.upload_name("/tmp/x.png") != aesgcm.upload_name("/tmp/x.png")
    assert "." not in aesgcm.upload_name("/tmp/uzantisiz")
    assert "/" not in aesgcm.upload_name("/tmp/a.ex/ploit")


# ── Bot: yükleme ve gönderim ─────────────────────────────────────────────────

class _Q:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


class _FakeUpload:
    def __init__(self):
        self.calls = []

    async def upload_file(self, filename, size=None, content_type=None, *,
                          input_file=None, timeout=None):
        data = input_file.read() if input_file is not None else None
        self.calls.append({"filename": str(filename), "size": size,
                           "content_type": content_type, "data": data})
        return f"https://up.example.org/slot/{os.path.basename(filename)}"


class _Bot(TransferMixin):
    def __init__(self, ready=True, enabled=True):
        self.gui_q = _Q()
        self.omemo_ready = ready
        self._enabled = enabled
        self.upload = _FakeUpload()
        self.plugin = {"xep_0363": self.upload}
        self.omemo_sent = []
        self.plain_sent = []

    def _omemo_enabled(self):
        return self._enabled

    async def _send_omemo(self, to, body, mtype, **kw):
        self.omemo_sent.append((to, body, mtype))

    def make_message(self, mto, mbody, mtype):
        sent = self.plain_sent
        msg = {"to": mto, "body": mbody, "type": mtype, "oob": {}}

        class _M(dict):
            def send(self):
                sent.append(dict(self))
        return _M(msg)


@pytest.fixture()
def photo(tmp_path):
    p = tmp_path / "tatil.png"
    p.write_bytes(PLAIN)
    return str(p)


def test_send_file_omemo_uploads_only_ciphertext(photo):
    bot = _Bot()
    asyncio.run(bot._send_file_impl("ayse@example.org", photo, "chat",
                                    encryption="omemo"))
    (up,) = bot.upload.calls
    assert PLAIN not in up["data"]                         # sunucu düz veri görmez
    assert up["content_type"] == "application/octet-stream"
    assert up["size"] == len(up["data"])
    assert "tatil" not in up["filename"] and up["filename"].endswith(".png")
    # Bağlantı yalnız OMEMO'lu gövdede gider; düz mesaj/OOB yok
    ((to, body, mtype),) = bot.omemo_sent
    assert (to, mtype) == ("ayse@example.org", "chat")
    https, key, iv = aesgcm.parse(body)
    assert https.endswith(up["filename"])
    assert aesgcm.decrypt(up["data"], key, iv) == PLAIN
    assert bot.plain_sent == []


def test_send_file_omemo_room_uses_groupchat(photo):
    bot = _Bot()
    asyncio.run(bot._send_file_impl("oda@conf.example.org", photo,
                                    "groupchat", encryption="omemo"))
    assert bot.omemo_sent[0][2] == "groupchat"


@pytest.mark.parametrize("ready, enabled", [(False, True), (True, False)])
def test_send_file_omemo_not_ready_uploads_nothing(photo, ready, enabled):
    """OMEMO hazır değilse dosya şifresiz yüklenmeye DÜŞMEZ."""
    bot = _Bot(ready=ready, enabled=enabled)
    asyncio.run(bot._send_file_impl("ayse@example.org", photo, "chat",
                                    encryption="omemo"))
    assert bot.upload.calls == [] and bot.omemo_sent == []
    assert bot.plain_sent == []
    assert [k for k, _ in bot.gui_q.items] == ["error"]


def test_send_file_plain_is_unchanged(photo):
    bot = _Bot()
    asyncio.run(bot._send_file_impl("ayse@example.org", photo, "chat"))
    (up,) = bot.upload.calls
    assert up["filename"] == photo and up["data"] is None  # dosyayı slixmpp açar
    (msg,) = bot.plain_sent
    assert msg["body"] == "https://up.example.org/slot/tatil.png"
    assert msg["oob"]["url"] == msg["body"]
    assert bot.omemo_sent == []


def test_upload_file_encrypted_reports_aesgcm_link(photo):
    bot = _Bot()
    asyncio.run(bot._upload_file(photo, "ayse@example.org", encrypt=True))
    ((kind, data),) = bot.gui_q.items
    assert kind == "file_uploaded"
    assert data["encrypted"] is True and data["cb"] == "ayse@example.org"
    https, key, iv = aesgcm.parse(data["url"])
    assert aesgcm.decrypt(bot.upload.calls[0]["data"], key, iv) == PLAIN


def test_upload_file_encrypted_not_ready_reports_error(photo):
    bot = _Bot(ready=False)
    asyncio.run(bot._upload_file(photo, "ayse@example.org", encrypt=True))
    assert [k for k, _ in bot.gui_q.items] == ["error"]
    assert bot.upload.calls == []


def test_upload_file_plain_payload(photo):
    bot = _Bot()
    asyncio.run(bot._upload_file(photo, "ayse@example.org"))
    ((kind, data),) = bot.gui_q.items
    assert (kind, data["encrypted"]) == ("file_uploaded", False)
    assert data["url"] == "https://up.example.org/slot/tatil.png"


# ── GUI: şifreleme sohbetin modunu izler ─────────────────────────────────────

AES_URL = ("aesgcm://up.example.org/slot/ab12.png#"
           + (bytes(range(12)) + bytes(range(32))).hex())


@pytest.mark.parametrize("target, rooms, send", [
    ("a@b", [], "send_chat"), ("oda@conf", ["oda@conf"], "send_gc")])
def test_encrypted_upload_is_sent_with_omemo_and_without_oob(target, rooms,
                                                             send):
    w, rows = _upload_window()
    w.rooms, w.active = rooms, target
    xmpp.MainWindow._handle(w, "file_uploaded",
                            {"url": AES_URL, "cb": target, "encrypted": True})
    ((args, kw),) = getattr(w.bot, send).calls
    assert args == (target, AES_URL) and kw["encryption"] == "omemo"
    (_sargs, skw), = w._store.calls
    assert skw["oob"] == "" and skw["encrypted"] is True    # anahtar OOB'ye yazılmaz
    assert skw["mid"] == kw["mid"] == rows[0]._mid


def test_plain_upload_is_sent_without_encryption():
    w, _rows = _upload_window()
    xmpp.MainWindow._handle(w, "file_uploaded",
                            {"url": "https://x/y.png", "cb": "a@b"})
    ((_a, kw),) = w.bot.send_chat.calls
    assert kw["encryption"] == "none"
    assert w._store.calls[0][1]["oob"] == "https://x/y.png"


def _file_win(modes, rooms=(), encrypted_rooms=()):
    win = object.__new__(xmpp.MainWindow)
    win.active = "a@b"
    win.rooms = list(rooms)
    win._chat_enc_modes = dict(modes)
    win._encrypted_rooms = set(encrypted_rooms)
    win._default_encryption = "none"
    win._append = lambda *a, **k: None
    calls = []
    win.bot = types.SimpleNamespace(
        upload_file=lambda path, target, encrypt=False: calls.append(
            ("upload", path, target, encrypt)),
        send_file=lambda to, path, mtype, encryption="none": calls.append(
            ("send", to, path, mtype, encryption)))
    return win, calls


@pytest.mark.parametrize("mode, expected", [("omemo", True), ("none", False)])
def test_attach_menu_encrypts_when_chat_is_omemo(mode, expected):
    # PGP: önce onay sorulur → test_pgp_attach_asks_before_plain_upload
    win, calls = _file_win({"a@b": mode})
    xmpp.MainWindow._upload_file_path(win, "/tmp/f.pdf", "a@b")
    assert calls == [("upload", "/tmp/f.pdf", "a@b", expected)]


def test_encrypted_room_files_are_encrypted():
    win, calls = _file_win({}, rooms=["oda@c"], encrypted_rooms=["oda@c"])
    xmpp.MainWindow._upload_file_path(win, "/tmp/f.pdf", "oda@c")
    assert calls[-1][-1] is True


def test_voice_message_follows_target_chat_encryption():
    win, calls = _file_win({"hedef@b": "omemo", "a@b": "none"})
    win._show_sent_voice = lambda path, target=None: None
    xmpp.MainWindow._on_recording_ready(win, "/tmp/v.wav", "hedef@b")
    assert calls == [("send", "hedef@b", "/tmp/v.wav", "chat", "omemo")]


def test_dropped_files_follow_chat_encryption(tmp_path):
    f = tmp_path / "belge.txt"
    f.write_text("x")
    win, calls = _file_win({"a@b": "omemo"})
    win.root = types.SimpleNamespace(
        tk=types.SimpleNamespace(splitlist=lambda data: [str(f)]))
    xmpp.MainWindow._on_dnd_drop(win, types.SimpleNamespace(data=str(f)))
    assert calls == [("send", "a@b", str(f), "chat", "omemo")]


# ── OMEMO başarısızsa anahtarlı bağlantı düz metne DÜŞMEZ ────────────────────
# Kanıt: _send_omemo_locked şifreleme olmayınca (anonim oda: üye JID'leri
# yok; encrypt_message None) gövdeyi düz metin gönderir. Gövde aesgcm://
# bağlantısıysa çözme anahtarı da açık gider: dosya sunucuya açılır.

def _omemo_bot(result=None):
    from test_omemo import _FakeBot, _FakeOmemoXep
    return _FakeBot(_FakeOmemoXep(result=result))


@pytest.mark.parametrize("to, mtype", [
    ("ali@example.com", "chat"),              # encrypt_message → None
    ("oda@conf.example.com", "groupchat"),    # anonim oda: alıcı yok
])
@pytest.mark.parametrize("body", [AES_URL, f"şuna bak {AES_URL} tamam"])
def test_omemo_failure_never_sends_file_key_in_clear(to, mtype, body):
    bot = _omemo_bot()
    asyncio.run(xmpp.XMPPBot._send_omemo(bot, to, body, mtype))
    assert bot.sent_plain == []
    assert not any(m.sent for m in bot.made_messages)
    errors = [d for k, d in bot.gui_q.items if k == "error"]
    assert errors and "GÖNDERİLMEDİ" in errors[-1]


def test_room_text_fallback_is_unchanged():
    """Metin mesajında eski davranış: anonim odada düz metne düşer."""
    bot = _omemo_bot()
    asyncio.run(xmpp.XMPPBot._send_omemo(bot, "oda@conf.example.com",
                                         "merhaba", "groupchat"))
    assert bot.sent_plain == [("oda@conf.example.com", "merhaba",
                               "groupchat")]


# ── PGP sohbetinde dosya: şifresiz gideceği onaylanmadan gönderilmez ────────
# Kanıt: OpenPGP (XEP-0027) dosya şifrelemez; PGP sohbetindeki dosya düz
# yüklenip bağlantısı düz gidiyordu ve kullanıcıya bir şey söylenmiyordu.

@pytest.fixture()
def ask(monkeypatch):
    asked = []
    answer = {"value": False}

    def _ask(title, message, **kw):
        asked.append(message)
        return answer["value"]
    monkeypatch.setattr(xmpp.messagebox, "askyesno", _ask)
    return asked, answer


@pytest.mark.parametrize("yes", [False, True])
def test_pgp_attach_asks_before_plain_upload(ask, yes):
    asked, answer = ask
    answer["value"] = yes
    win, calls = _file_win({"a@b": "pgp"})
    win.root = None
    xmpp.MainWindow._upload_file_path(win, "/tmp/f.pdf", "a@b")
    assert len(asked) == 1 and "şifresiz" in asked[0]
    assert calls == ([("upload", "/tmp/f.pdf", "a@b", False)] if yes else [])


@pytest.mark.parametrize("yes", [False, True])
def test_pgp_voice_message_asks_first(ask, yes):
    asked, answer = ask
    answer["value"] = yes
    win, calls = _file_win({"hedef@b": "pgp"})
    win.root = None
    shown = []
    win._show_sent_voice = lambda path, target=None: shown.append(target)
    xmpp.MainWindow._on_recording_ready(win, "/tmp/v.wav", "hedef@b")
    assert len(asked) == 1
    assert calls == ([("send", "hedef@b", "/tmp/v.wav", "chat", "none")]
                     if yes else [])
    assert shown == (["hedef@b"] if yes else [])


def test_pgp_drop_asks_once_for_all_files(ask, tmp_path):
    asked, answer = ask
    answer["value"] = False
    files = [tmp_path / "a.txt", tmp_path / "b.txt"]
    for f in files:
        f.write_text("x")
    win, calls = _file_win({"a@b": "pgp"})
    win.root = types.SimpleNamespace(
        tk=types.SimpleNamespace(splitlist=lambda data: [str(f) for f in files]))
    xmpp.MainWindow._on_dnd_drop(win, types.SimpleNamespace(data="x"))
    assert len(asked) == 1 and calls == []


def test_pgp_paste_declined_sends_nothing(ask, monkeypatch):
    pytest.importorskip("PIL")
    from PIL import ImageGrab
    asked, answer = ask
    answer["value"] = False

    class _Img:
        def save(self, f, format):
            f.write(b"png")
    monkeypatch.setattr(ImageGrab, "grabclipboard", lambda: _Img())
    monkeypatch.setattr(xmpp, "HAS_PIL", True)
    win, calls = _file_win({"a@b": "pgp"})
    win.root = None
    win._remember_temp = lambda path: True
    assert xmpp.MainWindow._on_paste(win) == "break"   # metin yapıştırılmaz
    assert len(asked) == 1 and calls == []


@pytest.mark.parametrize("mode", ["omemo", "none"])
def test_no_prompt_outside_pgp(ask, mode):
    asked, _answer = ask
    win, calls = _file_win({"a@b": mode})
    xmpp.MainWindow._upload_file_path(win, "/tmp/f.pdf", "a@b")
    assert asked == [] and len(calls) == 1
