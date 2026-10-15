"""FAZ 4C-0: ChatView/mesaj alanı davranış dondurma sözleşmeleri.

4C extraction öncesi MEVCUT davranışı (bug'lar dahil) sabitler.
Bu testler "doğru olması gerekeni" değil, bugünkü davranışı belgelendirir.
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


def _root():
    titles = []

    class _R:
        def title(self, t):
            titles.append(t)

    return _R(), titles


def _msg_window(active="oda@conf"):
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w.jid = "ben@example.com"
    w._msg_ids = {}
    w.bot = None
    w._store = _Capture()
    w._append = _Capture()
    w._chat_tabs = {}
    w._send_read_receipts = False
    w._disappearing_ttl = {}
    w._chat_enc_modes = {}
    w._unread_counts = {}
    w._refresh_contacts = lambda: None
    w._notify_enabled = False
    w._sound_enabled = False
    w._show_toast = lambda *a, **k: None
    w.root, w._titles = _root()
    return w


# ── 1. Aktif sohbet render'ı vs okunmamış (MUC kimliği dahil) ───────────────
def test_msg_render_active_vs_unread_freeze():
    w = _msg_window(active="oda@conf")
    payload = {"from": "oda@conf", "nick": "Ali", "body": "merhaba", "mid": "m1"}

    xmpp.MainWindow._handle(w, "msg", payload)

    # Aktif: tek render, sender=nick, mid korunur
    assert len(w._append.calls) == 1
    assert w._append.calls[0][0][:2] == ("merhaba", "them")
    assert w._append.calls[0][1]["sender"] == "Ali"
    assert w._append.calls[0][1]["mid"] == "m1"
    # Depolama: hedef = bare oda JID, sender = kaynak nick
    assert w._store.calls[0][0][0] == "oda@conf"
    assert w._store.calls[0][1]["sender"] == "Ali"

    # Pasif: render yok, sayaç + başlık rozeti
    w.active = "baska@x"
    xmpp.MainWindow._handle(w, "msg", payload)
    assert len(w._append.calls) == 1
    assert w._unread_counts["oda@conf"] == 1
    assert " [1]" in w._titles[-1]


# ── 2. Correction: yalnız eşleşen mid; DB koşulsuz ──────────────────────────
def test_msg_correction_targets_mid_only_and_db_unconditional(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    r1 = types.SimpleNamespace(_mid="m1", _body="old")
    r2 = types.SimpleNamespace(_mid="m2", _body="keep")
    w._bubble_widgets = [r1, r2]
    ubt = _Capture()
    monkeypatch.setattr(xmpp._identity, "update_bubble_text", ubt)
    w.chats = {"a@b": [
        ("Ali", "old", False, "10:00", "them", "", False, "m1", ""),
        ("Bob", "keep", False, "10:01", "them", "", False, "m2", ""),
    ]}
    db = _Capture()
    monkeypatch.setattr(xmpp, "_db_update_msg_body", db)

    xmpp.MainWindow._handle(w, "msg_correction",
                            {"from": "a@b", "orig_id": "m1", "body": "yeni"})

    assert (r1._body, r1._edited, r2._body) == ("yeni", True, "keep")
    assert ubt.calls[0][0][0] is r1 and ubt.calls[0][0][1] == "yeni"
    assert ubt.calls[0][1]["edited"] is True
    # Geçmiş tuple: body index 1, sender index 0 korunur
    assert w.chats["a@b"][0][1] == "yeni"
    assert w.chats["a@b"][0][0] == "Ali"
    assert w.chats["a@b"][1][1] == "keep"
    assert db.calls[0][0] == ("a@b", "m1", "yeni")  # [2J.a] (jid, mid) kapsamlı

    # Pasif sohbette widget güncellenmez; DB yine de yazılır (mevcut davranış)
    r1._body = "old"
    w.active = "x@y"
    xmpp.MainWindow._handle(w, "msg_correction",
                            {"from": "a@b", "orig_id": "m1", "body": "yeni2"})
    assert r1._body == "old"
    assert len(ubt.calls) == 1  # pasifte UI helper çağrılmadı
    assert db.calls[-1][0] == ("a@b", "m1", "yeni2")  # [2J.a] jid kapsamlı


# ── 3. sent_mid: yalnız hedef sohbet aktifse yamalanır ──────────────────────
def test_sent_mid_patches_only_matching_active_chat():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    old = types.SimpleNamespace(_is_me=True, _mid="local")
    blank = types.SimpleNamespace(_is_me=True, _mid="")
    other = types.SimpleNamespace(_is_me=True, _mid="zzz")
    w._bubble_widgets = [old, blank, other]
    w._msg_ids = {}
    w._reactions = {}

    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@b", "mid": "wire"})

    # reversed tarama: other(mid'li) atlanır, blank yamalanır
    assert blank._mid == "wire"
    assert old._mid == "local"
    assert other._mid == "zzz"
    assert w._msg_ids["a@b"] == ["wire"]

    # Farklı sohbet için gelen sent_mid aktif balona dokunmaz
    blank2 = types.SimpleNamespace(_is_me=True, _mid="")
    w._bubble_widgets = [blank2]
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "baska@x", "mid": "wire2"})
    assert blank2._mid == ""
    assert w._msg_ids["baska@x"] == ["wire2"]  # domain state korunur


# ── 3b. V-2: file_uploaded → kendi row'una deterministik mid ────────────────
def _upload_window():
    w = _msg_window(active="a@b")
    rows = []
    w._bubble_widgets = []
    w.rooms = []

    def _append(body, tag, sender="", is_me=False, time_str=None, oob="",
                encrypted=False, mid="", reply_to=None, local_path=""):
        row = types.SimpleNamespace(_body=body, _is_me=is_me, _mid=mid,
                                    _reply_to=reply_to)
        rows.append(row)
        w._bubble_widgets.append(row)
        return row

    w._append = _append
    w._reactions = {}
    w.bot = types.SimpleNamespace(send_chat=_Capture(), send_gc=_Capture())
    return w, rows


def test_file_uploaded_rows_carry_their_own_mid_out_of_order():
    w, rows = _upload_window()
    xmpp.MainWindow._handle(w, "file_uploaded", {"url": "uX", "cb": "a@b"})
    xmpp.MainWindow._handle(w, "file_uploaded", {"url": "uY", "cb": "a@b"})

    mX = w.bot.send_chat.calls[0][1]["mid"]
    mY = w.bot.send_chat.calls[1][1]["mid"]
    assert mX and mY and mX != mY
    assert [(r._body, r._mid) for r in rows] == [("uX", mX), ("uY", mY)]

    # sent_mid ters sırada gelse bile row'lar karışmaz
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@b", "mid": mY})
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@b", "mid": mX})
    assert [(r._body, r._mid) for r in rows] == [("uX", mX), ("uY", mY)]
    assert w._msg_ids["a@b"] == [mY, mX]


def test_file_uploaded_muc_passes_same_mid_to_store_and_send():
    w, rows = _upload_window()
    w.rooms = ["oda@conf"]
    w.active = "oda@conf"
    xmpp.MainWindow._handle(w, "file_uploaded",
                            {"url": "uX", "cb": "oda@conf"})
    mX = w.bot.send_gc.calls[0][1]["mid"]
    assert w._store.calls[0][1]["mid"] == mX
    assert rows[0]._mid == mX


def test_sent_mid_multiple_unresolved_rows_left_unresolved():
    """Fail-safe: iki mid'siz outgoing varken yanlış eşleme yapılmaz."""
    w = _msg_window(active="a@b")
    x = types.SimpleNamespace(_is_me=True, _mid="")
    y = types.SimpleNamespace(_is_me=True, _mid="")
    w._bubble_widgets = [x, y]
    w._reactions = {}

    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@b", "mid": "midX"})
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@b", "mid": "midY"})

    assert x._mid == "" and y._mid == ""      # X↔midY / Y↔midX swap yok
    assert w._msg_ids["a@b"] == ["midX", "midY"]


def test_sent_mid_pre_tagged_row_does_not_steal_mid_from_pending_row():
    """Zaten kendi mid'iyle doğan row, sent_mid ile başka satıra yazmaz."""
    w = _msg_window(active="a@b")
    tagged = types.SimpleNamespace(_is_me=True, _mid="midX")
    pending = types.SimpleNamespace(_is_me=True, _mid="")
    w._bubble_widgets = [tagged, pending]
    w._reactions = {}

    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@b", "mid": "midX"})

    assert tagged._mid == "midX"
    assert pending._mid == ""


# ── 4. MAM: sıra/dedupe + bayat generation guard ────────────────────────────
def test_mam_merge_order_dedupe_and_stale_result_ignored():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.chats = {}
    w._mam_oldest = {}
    w._mam_has_more = {}
    w._mam_gen = {"a@b": 0}
    w._load_chat = _Capture()
    msgs = [
        {"mid": "m2", "body": "yeni", "ts": "2026-09-26T10:00:00Z",
         "is_me": False, "from": "ali@example.com"},
        {"mid": "m1", "body": "eski", "ts": "2026-09-26T09:00:00Z",
         "is_me": False, "from": "ali@example.com"},
    ]

    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": msgs, "token": 0})

    hist = w.chats["a@b"]
    assert [e[1] for e in hist] == ["yeni", "eski"]  # giriş sırası korunur
    assert [e[0] for e in hist] == ["ali", "ali"]
    assert w._load_chat.calls[0][0] == ("a@b",)
    assert w._mam_oldest["a@b"] == "m2"

    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": [msgs[1]], "token": 0})
    assert len(w.chats["a@b"]) == 2  # mid dedupe

    # Clear simülasyonu: generation bump → eski token'lı sonuç yok sayılır
    w.chats = {}
    calls_before = len(w._load_chat.calls)
    w._mam_gen["a@b"] = 1
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": msgs, "token": 0})
    assert w.chats.get("a@b") is None
    assert len(w._load_chat.calls) == calls_before

    # Güncel token'lı sonuç normal şekilde merge olur
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": msgs, "token": 1})
    assert len(w.chats["a@b"]) == 2
