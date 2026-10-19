"""İletme ve P2P: şifreli sohbetin içeriği şifresiz kanala sessizce gitmez.

Kanıtlar:
- `forward_message` (messages.py) hedefin şifreleme modunu hiç okumadan düz
  mesaj kuruyordu: şifreli sohbetten çözülmüş bir mesaj ya da anahtarlı
  `aesgcm://` bağlantısı OMEMO'lu bir sohbete bile açık metin gidiyordu.
  İletilen mesaj hedef sohbette görünmüyordu (yerel kayıt yoktu).
- 📎 → P2P (jingle_ft.py: yalnız IBB, veri XMPP akışında sunucudan geçer)
  OMEMO/PGP sohbetinde de sunuluyordu; uçtan uca şifreli değildir.
"""
import types

import pytest
from test_history_window_bounds import _Cap, _win

import xmpp

AES_URL = ("aesgcm://up.example.org/slot/ab12.png#"
           + (bytes(range(12)) + bytes(range(32))).hex())
FWD = "[İletildi — Ali]\ngizli plan"


class _Rec:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))


@pytest.fixture()
def ask(monkeypatch):
    asked = []
    answer = {"value": False}

    def _ask(title, message, **kw):
        asked.append(message)
        return answer["value"]
    monkeypatch.setattr(xmpp.messagebox, "askyesno", _ask)
    return asked, answer


def _fwd_win(modes=None, rooms=(), encrypted_rooms=(), active="a@x",
             leak_ok=True):
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w.rooms = list(rooms)
    w.root = None
    w._chat_enc_modes = dict(modes or {})
    w._encrypted_rooms = set(encrypted_rooms)
    w._default_encryption = "none"
    w._store = _Rec()
    w._append = _Rec()
    w._deliver_live = lambda target, fn: (fn(), "append")[1]
    w._leak_guard_ok = lambda target, body, enc, parent=None: leak_ok
    w.bot = types.SimpleNamespace(forward_message=_Rec())
    return w


# ── Biçim ve bot yolu ────────────────────────────────────────────────────────

def test_forward_body_format_is_shared():
    from xmppcore.format import _forward_body
    assert _forward_body("Ali", "gizli plan") == FWD


class _FakeStanza(dict):
    def __init__(self, sent, **kw):
        super().__init__(kw, origin_id={})
        self._sent = sent

    def send(self):
        self._sent.append(dict(self))


def _bot():
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None          # XMLStream.__del__ gürültüsü
    bot._dispatch_loop = lambda fn: fn()  # loop thread'i yerine doğrudan
    bot.errors = []
    bot.gui_q = types.SimpleNamespace(put=bot.errors.append)
    bot.sent = []
    bot.make_message = lambda mto, mbody, mtype: _FakeStanza(
        bot.sent, to=mto, body=mbody, type=mtype)
    bot.send_chat = _Rec()
    bot.send_gc = _Rec()
    return bot


@pytest.mark.parametrize("enc", ["omemo", "pgp"])
@pytest.mark.parametrize("mtype, via", [("chat", "send_chat"),
                                        ("groupchat", "send_gc")])
def test_bot_forward_uses_encrypted_send_path(enc, mtype, via):
    bot = _bot()
    xmpp.XMPPBot.forward_message(bot, "b@x", "Ali", "gizli plan", mtype,
                                 encryption=enc, mid="m-1")
    assert getattr(bot, via).calls == [(("b@x", FWD),
                                        {"encryption": enc, "mid": "m-1"})]
    assert bot.sent == []                          # düz stanza kurulmadı


def test_bot_forward_plain_carries_the_given_mid():
    bot = _bot()
    xmpp.XMPPBot.forward_message(bot, "b@x", "Ali", "gizli plan", "chat",
                                 mid="m-2")
    assert bot.errors == []
    (msg,) = bot.sent
    assert (msg["to"], msg["body"], msg["type"]) == ("b@x", FWD, "chat")
    assert msg["origin_id"]["id"] == "m-2"       # düzenle/sil için kimlik
    assert bot.send_chat.calls == []


# ── GUI: hedef sohbetin şifrelemesi ──────────────────────────────────────────

@pytest.mark.parametrize("enc", ["omemo", "pgp"])
def test_forward_to_encrypted_chat_is_encrypted_and_stored(ask, enc):
    asked, _ = ask
    w = _fwd_win({"b@x": enc})
    xmpp.MainWindow._forward_to(w, "b@x", "chat", "Ali", "gizli plan", True)
    ((a, k),) = w.bot.forward_message.calls
    assert a == ("b@x", "Ali", "gizli plan", "chat")
    assert k["encryption"] == enc and k["mid"]
    ((sa, sk),) = w._store.calls
    assert sa == ("b@x", FWD)
    assert sk["is_me"] is True and sk["encrypted"] is True
    assert sk["mid"] == k["mid"]                  # deterministik korelasyon
    assert asked == []                            # şifreli hedefte soru yok
    assert w._append.calls == []                  # hedef aktif değil


def test_forward_into_active_chat_is_shown_live(ask):
    w = _fwd_win({"a@x": "omemo"}, active="a@x")
    xmpp.MainWindow._forward_to(w, "a@x", "chat", "Ali", "gizli plan", False)
    ((a, k),) = w._append.calls
    assert a[0] == FWD and k["mid"] == w._store.calls[0][1]["mid"]
    assert k["encrypted"] is True


def test_forward_to_encrypted_room_uses_room_encryption(ask):
    w = _fwd_win(rooms=["oda@c"], encrypted_rooms=["oda@c"])
    xmpp.MainWindow._forward_to(w, "oda@c", "groupchat", "Ali", "x", True)
    ((a, k),) = w.bot.forward_message.calls
    assert a[3] == "groupchat" and k["encryption"] == "omemo"


@pytest.mark.parametrize("yes", [False, True])
@pytest.mark.parametrize("body, src_encrypted", [
    ("gizli plan", True),          # şifreli sohbetten çözülmüş mesaj
    (AES_URL, False),              # bayrak yoksa da anahtar taşıyan bağlantı
])
def test_encrypted_content_to_plain_chat_needs_consent(ask, yes, body,
                                                       src_encrypted):
    asked, answer = ask
    answer["value"] = yes
    w = _fwd_win({"b@x": "none"})
    xmpp.MainWindow._forward_to(w, "b@x", "chat", "Ali", body, src_encrypted)
    assert len(asked) == 1 and "şifresiz" in asked[0]
    if yes:
        ((_a, k),) = w.bot.forward_message.calls
        assert k["encryption"] == "none"
        assert w._store.calls[0][1]["encrypted"] is False
    else:
        assert w.bot.forward_message.calls == [] and w._store.calls == []


def test_plain_message_to_plain_chat_needs_no_consent(ask):
    asked, _ = ask
    w = _fwd_win({"b@x": "none"})
    xmpp.MainWindow._forward_to(w, "b@x", "chat", "Ali", "selam", False)
    assert asked == [] and len(w.bot.forward_message.calls) == 1


def test_leak_guard_applies_to_plain_forward(ask):
    w = _fwd_win({"b@x": "none"}, leak_ok=False)
    xmpp.MainWindow._forward_to(w, "b@x", "chat", "Ali", "TR33 0006…", False)
    assert w.bot.forward_message.calls == [] and w._store.calls == []


def test_forward_without_connection_does_nothing(ask):
    w = _fwd_win({"b@x": "omemo"})
    w.bot = None
    xmpp.MainWindow._forward_to(w, "b@x", "chat", "Ali", "x", True)
    assert w._store.calls == []


# ── GUI bağlantısı: diyalog ve satırın şifreli bayrağı ───────────────────────

def test_forward_dialog_passes_target_and_source_flag(monkeypatch):
    captured = []
    monkeypatch.setattr(
        xmpp._ui_chat_actions, "show_forward",
        lambda parent, contacts, rooms, body, sender, on_forward:
            captured.append(on_forward))
    w = _fwd_win()
    w._contacts = {}
    w._forward_to = _Rec()
    xmpp.MainWindow._forward_dialog(w, "gövde", "Ali", encrypted=True)
    captured[0]("b@x", "chat")
    assert w._forward_to.calls == [(("b@x", "chat", "Ali", "gövde", True),
                                    {})]


def test_hover_bar_forward_passes_row_encryption(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.active, w.rooms, w.bot = "a@x", [], object()
    w._reactions = {}
    w._ai_message_items = lambda row: set()
    w._forward_dialog = _Rec()
    specs = []
    monkeypatch.setattr(xmpp._actions_ui, "populate_action_bar",
                        lambda bar, theme, s, **k: specs.extend(s))
    row = types.SimpleNamespace(_body="gövde", _is_me=False, _mid="m1",
                                _sender="Ali", _retracted=False,
                                _reply_to=None, _encrypted="omemo")
    xmpp.MainWindow._populate_action_bar(w, object(), row)
    (fwd,) = [s for s in specs if s[1] == "İlet"]
    fwd[2]()
    assert w._forward_dialog.calls == [(("gövde", "Ali"),
                                        {"encrypted": True})]


# ── P2P: şifreli sohbette önce uyarı ─────────────────────────────────────────

def _p2p_win(mode, tmp_path):
    path = tmp_path / "deneme.bin"
    path.write_bytes(b"icerik")
    w = _win(jid="a@x")
    w.active = "a@x"
    w.root = None
    w._chat_enc_modes = {"a@x": mode}
    w._ft_warn_mb = 100
    w._ft_block_size = 4096
    w._ft_pending_out = {}
    w.presence = {"a@x": "online"}
    w._append = _Cap()
    picked = []
    w._ask_send_path = lambda: picked.append(1) or str(path)
    w.bot = types.SimpleNamespace(jingle_send=_Cap())
    return w, picked


@pytest.mark.parametrize("mode", ["omemo", "pgp"])
def test_p2p_in_encrypted_chat_warns_before_file_choice(ask, tmp_path, mode):
    asked, answer = ask
    answer["value"] = False
    w, picked = _p2p_win(mode, tmp_path)
    xmpp.MainWindow._send_file_p2p(w)
    assert len(asked) == 1 and "şifreli değil" in asked[0]
    assert picked == [] and w.bot.jingle_send.calls == []


def test_p2p_warning_points_omemo_users_to_encrypted_upload(ask, tmp_path):
    asked, _ = ask
    w, _picked = _p2p_win("omemo", tmp_path)
    xmpp.MainWindow._send_file_p2p(w)
    assert "Sunucuya Yükle" in asked[0]


def test_p2p_in_encrypted_chat_proceeds_after_consent(ask, tmp_path):
    _asked, answer = ask
    answer["value"] = True
    w, picked = _p2p_win("omemo", tmp_path)
    xmpp.MainWindow._send_file_p2p(w)
    assert picked == [1] and len(w.bot.jingle_send.calls) == 1


def test_p2p_in_plain_chat_has_no_extra_prompt(ask, tmp_path):
    asked, _ = ask
    w, _picked = _p2p_win("none", tmp_path)
    xmpp.MainWindow._send_file_p2p(w)
    assert asked == [] and len(w.bot.jingle_send.calls) == 1
