"""FAZ 4C-PRE: J.1-J.4 verified pre-existing bug fix regression testleri."""

import asyncio
import os
import queue
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
import xmppcore.archive as archive_mod  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


# ── J.1 — stale MAM response after clear ────────────────────────────────────

def test_mam_stale_result_after_clear_is_benign():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.chats = {}
    w._mam_oldest = {}
    w._mam_has_more = {}
    w._mam_gen = {"a@b": 0}
    w._load_chat = _Capture()

    # İstek uçuşta (token=0); kullanıcı temizledi → generation bump
    w._mam_gen["a@b"] = 1
    xmpp.MainWindow._handle(w, "mam_results", {
        "jid": "a@b", "token": 0,
        "messages": [{"mid": "m1", "body": "eski", "ts": "2026-09-26T09:00:00Z",
                      "is_me": False, "from": "ali@example.com"}]})

    assert w.chats.get("a@b") is None
    assert len(w._load_chat.calls) == 0


def test_mam_current_result_still_merges_and_is_per_jid():
    w = object.__new__(xmpp.MainWindow)
    w.active = "x@y"                      # başka sohbet açık
    w.chats = {}
    w._mam_oldest = {}
    w._mam_has_more = {}
    w._mam_gen = {"a@b": 5, "c@d": 1}
    w._load_chat = _Capture()

    # a@b için eski generation sonucu düşer; c@d'nin güncel sonucu merge olur
    xmpp.MainWindow._handle(w, "mam_results", {
        "jid": "a@b", "token": 1,
        "messages": [{"mid": "m1", "body": "bayat", "ts": "2026-09-26T09:00:00Z",
                      "is_me": False, "from": "ali@example.com"}]})
    xmpp.MainWindow._handle(w, "mam_results", {
        "jid": "c@d", "token": 1,
        "messages": [{"mid": "m2", "body": "guncel", "ts": "2026-09-26T09:05:00Z",
                      "is_me": False, "from": "veli@example.com"}]})

    assert w.chats.get("a@b") is None
    assert len(w.chats["c@d"]) == 1
    # Aktif olmayan fakat geçerli JID sonucu render tetiklemez
    assert len(w._load_chat.calls) == 0


def test_load_mam_history_passes_generation_token():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.rooms = {}
    w.chats = {}
    w._mam_gen = {"a@b": 3}
    calls = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda jid, n, **kw: calls.append((jid, n, kw)))

    xmpp.MainWindow._load_mam_history(w)

    assert calls == [("a@b", 50, {"token": 3})]


def test_load_older_mam_passes_generation_token_and_ignores_stale():
    """V-1: older-MAM isteği generation token'ı taşımalı; temizlik sonrası
    dönen bayat sayfa temizlenen sohbeti geri doldurmamalı."""
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.rooms = {}
    w.chats = {}
    w._mam_oldest = {"a@b": "m1"}
    w._mam_has_more = {}
    w._mam_gen = {"a@b": 3}
    w._load_chat = _Capture()
    calls = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda jid, n, **kw: calls.append((jid, n, kw)))

    xmpp.MainWindow._load_older_mam(w)
    assert calls == [("a@b", 50, {"before": "m1", "token": 3})]

    # Clear → generation bump; uçuştaki eski sayfa yok sayılmalı
    w._mam_gen["a@b"] = 4
    xmpp.MainWindow._handle(w, "mam_results", {
        "jid": "a@b", "token": 3,
        "messages": [{"mid": "m0", "body": "silinmis",
                      "ts": "2026-09-20T09:00:00Z",
                      "is_me": False, "from": "ali@example.com"}]})
    assert w.chats.get("a@b") is None
    assert len(w._load_chat.calls) == 0


def test_load_older_mam_target_captured_at_request_time():
    """V-1: before/token aynı hedef JID için istek anında belirlenmeli."""
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.rooms = {}
    w.chats = {}
    w._mam_oldest = {"a@b": "m1", "c@d": "m9"}
    w._mam_has_more = {}
    w._mam_gen = {"a@b": 3, "c@d": 7}
    calls = []

    def _fetch(jid, n, **kw):
        calls.append((jid, n, kw))
        w.active = "c@d"          # istek uçarken hedef değişti
        w._mam_oldest["a@b"] = "degismis"

    w.bot = types.SimpleNamespace(fetch_mam=_fetch)

    xmpp.MainWindow._load_older_mam(w)
    assert calls == [("a@b", 50, {"before": "m1", "token": 3})]


def test_clear_active_history_bumps_mam_generation(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.chats = {"a@b": [("Ali", "x", False, "10:00", "them", "", False, "m1", "")]}
    w._mam_gen = {"a@b": 4}
    w._load_chat = _Capture()
    monkeypatch.setattr(xmpp, "_db_clear_chat", lambda jid: None)

    assert xmpp.MainWindow._clear_active_history(w) is True
    assert w._mam_gen["a@b"] == 5


def test_clear_all_history_bumps_all_generations(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.chats = {"a@b": [], "c@d": []}
    w._mam_gen = {"a@b": 1, "c@d": 7}
    w._load_chat = _Capture()
    monkeypatch.setattr(xmpp, "_db_clear_all", lambda: None)

    assert xmpp.MainWindow._clear_all_history(w) is True
    assert w._mam_gen == {"a@b": 2, "c@d": 8}


class _J:
    def __init__(self, s):
        self.s = s

    @property
    def bare(self):
        return self.s


class _Stanza:
    def __init__(self, body, frm, mid):
        self._body = body
        self._frm = frm
        self.id = mid
        self.xml = None

    def get(self, k, d=None):
        return self._body if k == "body" else d

    def __getitem__(self, k):
        if k == "from":
            return _J(self._frm)
        if k == "id":
            return self.id
        raise KeyError(k)


class _Mam:
    def __init__(self, error=None):
        self.error = error

    def retrieve(self, **kw):
        # son sayfa RSM yineleyicisiyle (iterator=True) istenir
        return types.SimpleNamespace(next=self._page) if kw.get("iterator") else self._page()

    async def _page(self):
        if self.error:
            raise self.error
        st = _Stanza("merhaba", "ali@example.com", "a1")
        return {"mam": {"results": [{"mam_result": {"forwarded": {
            "stanza": st, "delay": {"stamp": "2026-09-14T10:00:00Z"}}}}]}}


def _mam_bot():
    bot = object.__new__(xmpp.XMPPBot)
    bot._run_out_filters = None
    bot.gui_q = queue.Queue()
    bot.boundjid = types.SimpleNamespace(bare="ben@example.com")
    return bot


def test_fetch_mam_token_echoed_on_success_and_error(monkeypatch):
    bot = _mam_bot()
    monkeypatch.setattr(archive_mod, "_get_xep", lambda self, name: _Mam())
    asyncio.run(xmpp.XMPPBot._fetch_mam(bot, "ali@example.com", token=7))
    kind, data = bot.gui_q.get_nowait()
    assert kind == "mam_results"
    assert data["token"] == 7
    assert data["messages"][0]["mid"] == "a1"

    monkeypatch.setattr(archive_mod, "_get_xep",
                        lambda self, name: _Mam(error=RuntimeError("yok")))
    asyncio.run(xmpp.XMPPBot._fetch_mam(bot, "ali@example.com", token=8))
    kind, data = bot.gui_q.get_nowait()
    assert data["token"] == 8
    assert data["messages"] == [] and data["error"] == "yok"


# ── J.2 — local edit/retract outgoing state ─────────────────────────────────

def _edit_retract_window():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.root = types.SimpleNamespace()
    w._bubble_widgets = [
        types.SimpleNamespace(_mid="m1", _body="old", _edited=False),
        types.SimpleNamespace(_mid="m2", _body="keep", _edited=False),
    ]
    w.chats = {"a@b": [
        ("Ali", "old", False, "10:00", "them", "", False, "m1", ""),
        ("Bob", "keep", False, "10:01", "them", "", False, "m2", ""),
    ]}
    w._update_bubble_text = _Capture()
    w._render_reactions = _Capture()
    w._reactions = {("a@b", "m1"): {"👍": ["Ali"]}}  # [2M] (jid, mid) kapsamlı
    w._my_reactions = {("a@b", "m1"): {"👍"}}
    w.bot = types.SimpleNamespace(send_correction=_Capture(),
                                  retract_message=_Capture())
    return w


def test_local_edit_updates_correct_row_history_and_db(monkeypatch):
    w = _edit_retract_window()
    db = _Capture()
    ubt = _Capture()
    monkeypatch.setattr(xmpp, "_db_update_msg_body", db)
    monkeypatch.setattr(xmpp._identity, "update_bubble_text", ubt)
    monkeypatch.setattr(xmpp._ui_chat_actions, "ask_edit_message",
                        lambda *a, **k: "yeni")

    xmpp.MainWindow._edit_message_dialog(w, "m1", "old", "chat")

    assert w.bot.send_correction.calls[0][0] == ("a@b", "yeni", "m1", "chat")
    r1, r2 = w._bubble_widgets
    assert (r1._body, r1._edited) == ("yeni", True)
    assert (r2._body, r2._edited) == ("keep", False)
    assert ubt.calls[0][0][0] is r1 and ubt.calls[0][1]["edited"] is True
    assert w.chats["a@b"][0][1] == "yeni" and w.chats["a@b"][0][0] == "Ali"
    assert w.chats["a@b"][1][1] == "keep"
    assert db.calls[0][0] == ("a@b", "m1", "yeni")  # [2J.a] (jid, mid) kapsamlı


def test_local_retract_updates_correct_row_maps_and_db(monkeypatch):
    w = _edit_retract_window()
    db, db_react = _Capture(), _Capture()
    ubt = _Capture()
    monkeypatch.setattr(xmpp, "_db_update_msg_body", db)
    monkeypatch.setattr(xmpp, "_db_clear_reactions_mid", db_react)
    monkeypatch.setattr(xmpp._identity, "update_bubble_text", ubt)
    monkeypatch.setattr(xmpp.messagebox, "askyesno", lambda *a, **k: True)

    xmpp.MainWindow._retract_message(w, "m1", "chat")

    assert w.bot.retract_message.calls[0][0] == ("a@b", "m1", "chat")
    r1, r2 = w._bubble_widgets
    assert (r1._body, r1._retracted) == ("🚫 Bu mesaj silindi", True)
    assert not hasattr(r2, "_retracted") or r2._retracted is False
    assert ubt.calls[0][0][0] is r1 and ubt.calls[0][1]["retracted"] is True
    assert ("a@b", "m1") not in w._reactions  # [2M] composite kapsam
    assert ("a@b", "m1") not in w._my_reactions
    assert w.chats["a@b"][0][1] == "🚫 Bu mesaj silindi"
    assert w.chats["a@b"][1][1] == "keep"
    assert db.calls[0][0] == ("a@b", "m1", "🚫 Bu mesaj silindi")  # [2J.a]
    assert db_react.calls[0][0] == ("a@b", "m1")


# ── J.4 — date separator message date'ini dikkate alır ──────────────────────

def test_parse_msg_date_supported_and_invalid_formats():
    from datetime import date, datetime
    today = datetime.now().date()
    assert xmpp._parse_msg_date("10:30") == today
    assert xmpp._parse_msg_date("2026-09-25T10:00:00Z") == date(2026, 9, 25)
    assert xmpp._parse_msg_date("2026-09-25 10:00") == date(2026, 9, 25)
    assert xmpp._parse_msg_date("") is None
    assert xmpp._parse_msg_date(None) is None
    assert xmpp._parse_msg_date("abc") is None
    assert xmpp._parse_msg_date("99:99") is None


def _date_sep_window():
    created = []

    class _W:
        def __init__(self, *a, **k):
            created.append(k)

        def pack(self, *a, **k):
            pass

        def grid(self, *a, **k):
            pass

        def columnconfigure(self, *a, **k):
            pass

    w = object.__new__(xmpp.MainWindow)
    w.msg_frame = _W()
    w._bubble_widgets = []
    w._last_date_label = ""
    w._bind_scroll_widget = lambda *a: None
    return w, created, _W


def test_date_separator_uses_message_date_and_dedupes(monkeypatch):
    w, created, W = _date_sep_window()
    monkeypatch.setattr(xmpp._render, "tk",
                        types.SimpleNamespace(Frame=W, Label=W))

    # Geçmiş gün → intended format, "Bugün" değil
    xmpp.MainWindow._maybe_add_date_separator(w, "2026-09-25T10:00:00Z")
    texts = [k.get("text") for k in created if "text" in k]
    assert len(texts) == 1
    assert texts[0] != "Bugün" and "2026" in texts[0] and "25" in texts[0]

    # Aynı gün ikinci mesaj → duplicate separator yok
    n = len(created)
    xmpp.MainWindow._maybe_add_date_separator(w, "2026-09-25T11:00:00Z")
    assert len(created) == n

    # Bugün → "Bugün"
    xmpp.MainWindow._maybe_add_date_separator(w, None)
    new_texts = [k.get("text") for k in created[n:] if "text" in k]
    assert new_texts == ["Bugün"]

    # Bozuk timestamp → güvenli fallback (bugün zaten eklendi → yeni separator yok)
    n2 = len(created)
    xmpp.MainWindow._maybe_add_date_separator(w, "abc")
    assert len(created) == n2
