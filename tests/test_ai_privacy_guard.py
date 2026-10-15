"""Şifresiz gönderimde hassas veri uyarısı (xmppcore/sensitive + MainWindow).

Kanıtlar:
- Algılayıcılar: IBAN (mod-97), kart (Luhn), TCKN (sağlama), parola
  anahtar kelimesi, API anahtarı ve özel anahtar; sağlaması tutmayan
  sayılar, telefon, fiyat ve "şifremi unuttum" uyarı üretmez.
- Bulgular maskelidir: ham değer uyarı metninde geçmez; çakışan aralık
  (IBAN içindeki rakamlar) ikinci kez raporlanmaz.
- Gönderim: şifresiz + bulgu → onay sorulur (varsayılan "Hayır"); Hayır →
  taslak kutuda kalır, hiçbir şey saklanmaz/gönderilmez; Evet → normal
  gönderim. Şifreli sohbet, bot komutu ve kapalı ayar hiç sormaz; temiz
  mesaj config dosyasını bile okumaz.
- Ayrı sekme gönderimi de aynı kapıdan, taslak temizlenmeden önce geçer.
"""
import inspect
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2p_consecutive_send import _o_w  # noqa: E402
from test_history_window_bounds import _Cap  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import sensitive  # noqa: E402

VALID_IBAN = "TR33 0006 1005 1978 6457 8413 26"


# ── 1) Algılayıcılar ────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,kind", [
    (f"IBAN {VALID_IBAN} gönderir misin", "iban"),
    ("IBAN: TR330006100519786457841326", "iban"),
    ("kart 4111 1111 1111 1111 son kullanma 12/29", "card"),
    ("kart no 4111-1111-1111-1111", "card"),
    ("TC 10000000146", "tckn"),
    ("şifrem: hunter22", "password"),
    ("ŞİFRE=abc123", "password"),
    ("wifi password is s3cret!", "password"),
    ("anahtar sk-ant-api03-" + "x" * 30, "token"),
    ("ghp_" + "a" * 36, "token"),
    ("AKIAABCDEFGHIJKLMNOP", "token"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaA==", "private_key"),
])
def test_detects_sensitive_values(text, kind):
    assert [f.kind for f in sensitive.scan(text)] == [kind]


@pytest.mark.parametrize("text", [
    "şifremi unuttum, sıfırlar mısın?",
    "telefon 0532 123 45 67",
    "fiyat 1.234.567,89 TL",
    "sipariş 4111 1111 1111 1112",           # Luhn tutmaz
    "TR33 0006 1005 1978 6457 8413 27",      # mod-97 tutmaz
    "no 10000000147",                        # TCKN sağlaması tutmaz
    "0000 0000 0000 0000",
    "pin: 12",
    "toplantı 14:30'da, oda 1204",
    "",
])
def test_no_false_positive(text):
    assert sensitive.scan(text) == []


def test_overlapping_spans_reported_once():
    assert [f.kind for f in sensitive.scan(VALID_IBAN)] == ["iban"]
    assert [f.label for f in sensitive.scan(
        "sk-ant-api03-" + "y" * 40)] == ["Anthropic API anahtarı"]


def test_warning_text_is_masked():
    text = (f"IBAN {VALID_IBAN}, kart 4111 1111 1111 1111, "
            "şifre: hunter22")
    msg = sensitive.warning_text(sensitive.scan(text))
    assert "hunter22" not in msg
    assert "4111 1111 1111 1111" not in msg
    assert VALID_IBAN.replace(" ", "") not in msg.replace(" ", "")
    assert "TR33 •••• 1326" in msg and "•••• 1111" in msg
    assert "Yine de gönderilsin mi?" in msg
    assert "grup" in sensitive.warning_text(sensitive.scan(text), room=True)


def test_checksum_helpers():
    assert sensitive.luhn_ok("4111111111111111")
    assert not sensitive.luhn_ok("4111111111111112")
    assert sensitive.iban_ok(VALID_IBAN)
    assert not sensitive.iban_ok("TR33" + "0" * 22)
    assert sensitive.tckn_ok("10000000146")
    assert not sensitive.tckn_ok("00000000146")


# ── 2) Gönderim kapısı (MainWindow._send_message) ───────────────────────────
def _guard_w(monkeypatch, text, *, enc="none", answer=False,
             leak_guard=True, room=False):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w([text])
    w._encryption_mode = types.SimpleNamespace(get=lambda: enc,
                                               set=lambda v: None)
    w._deliver_live = lambda target, fn: "append"
    w._chat_tabs = {}
    cleared = []
    w._composer.clear_text = lambda: cleared.append(True)
    if room:
        w.rooms = {"a@b": {}}
    asks = []

    def _ask(*a, **k):
        asks.append((a, k))
        return answer
    monkeypatch.setattr(xmpp.messagebox, "askyesno", _ask)
    monkeypatch.setattr(xmpp, "_load_config",
                        lambda: {"ai": {"leak_guard": leak_guard}})
    return w, asks, cleared


def test_sensitive_unencrypted_send_cancelled_keeps_draft(monkeypatch):
    w, asks, cleared = _guard_w(monkeypatch, f"IBAN: {VALID_IBAN}")
    xmpp.MainWindow._send_message(w)
    assert len(asks) == 1
    (title, body), kw = asks[0][0][:2], asks[0][1]
    assert "Hassas" in title and "IBAN" in body and "1326" in body
    assert VALID_IBAN not in body
    assert kw["default"] == "no" and kw["icon"] == "warning"
    assert cleared == []                       # taslak kutuda kalır
    assert w.bot.send_chat.calls == []         # wire'a hiçbir şey gitmez
    assert not w.chats.get("a@b")              # optimistik kayıt yok


def test_sensitive_unencrypted_send_confirmed(monkeypatch):
    w, asks, cleared = _guard_w(monkeypatch, "şifre: hunter22", answer=True)
    xmpp.MainWindow._send_message(w)
    assert len(asks) == 1 and cleared == [True]
    assert [c[0][1] for c in w.bot.send_chat.calls] == ["şifre: hunter22"]


def test_room_warning_mentions_group(monkeypatch):
    w, asks, _c = _guard_w(monkeypatch, "şifre: hunter22", answer=True,
                           room=True)
    xmpp.MainWindow._send_message(w)
    assert "grup" in asks[0][0][1]
    assert len(w.bot.send_gc.calls) == 1


@pytest.mark.parametrize("kw", [
    {"enc": "omemo"}, {"enc": "pgp"}, {"leak_guard": False}])
def test_no_prompt_when_encrypted_or_disabled(monkeypatch, kw):
    w, asks, cleared = _guard_w(monkeypatch, "şifre: hunter22", **kw)
    xmpp.MainWindow._send_message(w)
    assert asks == [] and cleared == [True]
    assert len(w.bot.send_chat.calls) == 1


def test_bot_command_not_scanned(monkeypatch):
    w, asks, _c = _guard_w(monkeypatch, "/not şifre: hunter22")
    w._handle_bot_command = _Cap()
    xmpp.MainWindow._send_message(w)
    assert asks == [] and len(w._handle_bot_command.calls) == 1


def test_clean_message_does_not_read_config(monkeypatch):
    w, asks, _c = _guard_w(monkeypatch, "akşam görüşürüz")

    def _boom():
        raise AssertionError("temiz mesajda config okunmamalı")
    monkeypatch.setattr(xmpp, "_load_config", _boom)
    xmpp.MainWindow._send_message(w)
    assert asks == [] and len(w.bot.send_chat.calls) == 1


def test_detached_tab_send_uses_guard_before_clearing():
    src = inspect.getsource(xmpp.MainWindow._open_chat_tab)
    guard = src.index("self._leak_guard_ok(target, body, enc, parent=top)")
    assert guard < src.index('msg_v.set("")')
    assert guard < src.index("self._store(target, body")
