"""🙈 XEP-0382 spoiler (gizli içerik): çekirdek, bot alma/gönderme,
masaüstü gönderim ve örtü, web köprüsü.

Sözleşme: yalnız şifresiz mesajda gönderilir; OMEMO/PGP yollarına
dokunulmaz (CLAUDE.md kural 1). Olay yüküne "spoiler" anahtarı yalnız mesaj
spoiler'sa eklenir. Gövde tıklanana kadar örtülüdür; bildirim de örtülüdür.
"""
import asyncio
import os
import sys
import types
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2p_consecutive_send import _o_w  # noqa: E402
from test_contract_events_dispatch import _bot_stub, _FakeMsg  # noqa: E402
from test_webapp import session  # noqa: E402,F401  (fixture)

import xmpp  # noqa: E402
from xmppcore import messages as messages_mod  # noqa: E402
from xmppcore import muc as muc_mod  # noqa: E402
from xmppcore import spoiler as sp  # noqa: E402
from xmppcore import storage as st  # noqa: E402

JID = "a@b"


def _xml(hint=None):
    el = ET.Element("message")
    if hint is not None:
        s = ET.SubElement(el, sp.TAG)
        if hint:
            s.text = hint
    return el


@pytest.fixture()
def db(monkeypatch, tmp_path):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "s.db"))
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    xmpp._db_conn = None
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    xmpp._db_conn = None


# ── Çekirdek ────────────────────────────────────────────────────────────────


def test_hint_of_absent_empty_and_text():
    assert sp.hint_of(_xml()) is None and sp.hint_of(None) is None
    assert sp.hint_of(_xml("")) == ""
    assert sp.hint_of(_xml("  film\n sonu  ")) == "film sonu"
    assert len(sp.hint_of(_xml("x" * 500))) == sp.HINT_MAX


def test_mark_adds_key_only_for_spoilers():
    assert sp.mark({"a": 1}, _xml()) == {"a": 1}
    assert sp.mark({"a": 1}, _xml("uyarı")) == {"a": 1, "spoiler": "uyarı"}
    assert sp.mark({"a": 1}, _xml("")) == {"a": 1, "spoiler": ""}


def test_add_builds_xep0382_element():
    msg = types.SimpleNamespace(xml=ET.Element("message"))
    sp.add(msg, None)
    assert msg.xml.find(sp.TAG) is None
    sp.add(msg, " film  sonu ")
    assert msg.xml.find(sp.TAG).text == "film sonu"
    bare = types.SimpleNamespace(xml=ET.Element("message"))
    sp.add(bare, "")
    el = bare.xml.find(sp.TAG)
    assert el is not None and not el.text


def test_label_and_cover():
    assert sp.label("") == "🙈 Gizli içerik"
    assert sp.label("son") == "🙈 Gizli içerik: son"
    assert sp.cover("son") == "🙈 Gizli içerik: son — göstermek için tıklayın"


# ── Bot: alma ───────────────────────────────────────────────────────────────


def test_incoming_plain_message_carries_spoiler():
    bot = _bot_stub()
    xmpp.XMPPBot._on_message(bot, _FakeMsg(body="katil uşak", mid="m1",
                                           xml=_xml("film")))
    kind, data = bot.gui_q.items[0]
    assert kind == "msg" and data["spoiler"] == "film"
    assert data["body"] == "katil uşak"


def test_incoming_without_spoiler_payload_unchanged():
    bot = _bot_stub()
    xmpp.XMPPBot._on_message(bot, _FakeMsg(body="selam", mid="m1"))
    assert "spoiler" not in bot.gui_q.items[0][1]


# ── Bot: gönderme ───────────────────────────────────────────────────────────


def _sender(monkeypatch, mod):
    monkeypatch.setattr(mod, "_add_origin_id", lambda msg, mid: mid)
    bot = _bot_stub()
    sent = []
    msg = types.SimpleNamespace(xml=ET.Element("message"),
                                send=lambda: sent.append(True))
    bot.make_message = lambda **kw: msg
    return bot, msg, sent


def test_send_chat_plain_adds_spoiler(monkeypatch):
    bot, msg, sent = _sender(monkeypatch, messages_mod)
    ok = asyncio.run(messages_mod.MessagesMixin._send_chat(
        bot, "ali@x", "gizli", "none", "m1", "film"))
    assert ok and sent == [True]
    assert msg.xml.find(sp.TAG).text == "film"


def test_send_chat_without_spoiler_adds_nothing(monkeypatch):
    bot, msg, _sent = _sender(monkeypatch, messages_mod)
    asyncio.run(messages_mod.MessagesMixin._send_chat(
        bot, "ali@x", "selam", "none", "m1"))
    assert msg.xml.find(sp.TAG) is None


def test_send_gc_plain_adds_spoiler(monkeypatch):
    bot, msg, sent = _sender(monkeypatch, muc_mod)
    ok = asyncio.run(muc_mod.MucMixin._send_gc(
        bot, "oda@c", "gizli", "none", "m1", ""))
    assert ok and sent == [True] and msg.xml.find(sp.TAG) is not None


def test_omemo_send_path_untouched(monkeypatch):
    """Kural 1: OMEMO gönderimi spoiler'ı hiç görmez."""
    bot = _bot_stub()
    bot._omemo_enabled = lambda: True
    bot.omemo_ready = True
    calls = []

    async def _fake(*a, **k):
        calls.append((a, k))
    bot._send_omemo = _fake
    asyncio.run(messages_mod.MessagesMixin._send_chat(
        bot, "ali@x", "gizli", "omemo", "m1", "film"))
    assert calls == [(("ali@x", "gizli", "chat"), {"mid": "m1"})]


# ── Masaüstü ────────────────────────────────────────────────────────────────


def test_send_message_spoiler_plain_chat(db):
    w = _o_w(["katil uşak"])
    xmpp.MainWindow._send_message(w, spoiler="film")
    (args, kw), = w.bot.send_chat.calls
    assert args[1] == "katil uşak" and kw["spoiler"] == "film"
    assert w._spoilers[(JID, kw["mid"])] == "film"
    assert st._db_load_spoilers(JID) == {kw["mid"]: "film"}


def test_send_message_without_spoiler_passes_no_kwarg(db):
    w = _o_w(["selam"])
    xmpp.MainWindow._send_message(w)
    assert "spoiler" not in w.bot.send_chat.calls[0][1]


def test_send_message_spoiler_refused_in_encrypted_chat(db):
    w = _o_w(["gizli"])
    w._encryption_mode = types.SimpleNamespace(get=lambda: "omemo",
                                               set=lambda v: None)
    cleared, toasts = [], []
    w._composer.clear_text = lambda: cleared.append(True)
    w._show_toast = lambda *a: toasts.append(a)
    xmpp.MainWindow._send_message(w, spoiler="film")
    assert w.bot.send_chat.calls == [] and cleared == []      # metin kalır
    assert "gönderilemez" in toasts[0][1]


def test_slash_text_sent_as_spoiler_not_command(db):
    w = _o_w(["/clear bunu"])
    handled = []
    w._handle_bot_command = handled.append
    xmpp.MainWindow._send_message(w, spoiler="")
    assert handled == []
    assert w.bot.send_chat.calls[0][0][1] == "/clear bunu"


def test_note_spoiler_records_map_and_db(db):
    st._db_store_msg(JID, "ali", "gizli", False, "10:00", "them", mid="m1")
    w = object.__new__(xmpp.MainWindow)
    assert xmpp.MainWindow._note_spoiler(w, JID, "m1", " film ") == "film"
    assert w._spoilers == {(JID, "m1"): "film"}
    assert st._db_load_spoilers(JID) == {"m1": "film"}
    assert xmpp.MainWindow._note_spoiler(w, JID, "m2", None) is None


class _Text:
    """selectable_text'in iç Text'i: tıklamayı bu alır (çerçeve değil)."""

    def __init__(self):
        self.binds = []

    def cget(self, opt):
        return "#eee" if opt == "fg" else None

    def bind(self, seq, fn, add=None):
        self.binds.append((seq, fn))


class _Box:
    """selectable_text çerçevesi: `.text` + `_font` + `set_content`."""

    def __init__(self):
        self.content = None
        self.history = []
        self.binds = []                 # çerçeveye bağlanan (olmamalı)
        self.text = _Text()
        self._font = ("Sans", 10)

    def set_content(self, content, **kw):
        self.content = (content, kw)
        self.history.append((content, kw))

    def bind(self, seq, fn, add=None):
        self.binds.append((seq, fn))

    def winfo_exists(self):
        return True


def _row(mid="m1", **kw):
    base = dict(_mid=mid, _body="katil uşak", _body_text=_Box(),
                _retracted=False, _edited=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_apply_spoiler_hides_until_click():
    w = object.__new__(xmpp.MainWindow)
    w.active = JID
    w._spoilers = {(JID, "m1"): "film"}
    w._format_markdown = lambda t: [(t, None)]
    row = _row()
    box = row._body_text
    xmpp.MainWindow._apply_spoiler(w, row)
    assert box.content[0] == sp.cover("film")
    # Hata (2026-11-25): bağlama çerçevedeydi; tıklamayı iç Text alır
    assert box.binds == []
    seq, reveal = box.text.binds[0]
    assert seq == "<Button-1>"
    assert reveal() == "break"                     # ilk tık açar
    assert box.content[0] == [("katil uşak", None)]
    # Örtünün soluk italiği kalmasın: özgün renk ve yazı tipi geri gelir
    assert ("", {"fg": "#eee", "font": ("Sans", 10)}) in box.history
    assert reveal() is None                        # sonra tık seçim yapar


@pytest.mark.parametrize("row", [_row(mid="başka"), _row(_retracted=True),
                                 _row(_body_text=None)])
def test_apply_spoiler_leaves_other_rows(row):
    w = object.__new__(xmpp.MainWindow)
    w.active = JID
    w._spoilers = {(JID, "m1"): "film"}
    xmpp.MainWindow._apply_spoiler(w, row)
    box = row._body_text
    assert box is None or box.content is None


def test_incoming_spoiler_notification_is_covered():
    """Bildirim/toast gövdesi örtüyle değişir (kaynak taraması: dal tek)."""
    import inspect
    src = inspect.getsource(xmpp.MainWindow._handle)
    assert "spoiler = self._note_spoiler(frm, mid" in src
    assert "notify_body = _spoiler.label(spoiler)" in src


# ── Web ─────────────────────────────────────────────────────────────────────


def test_web_incoming_spoiler_stored_and_in_history(session):  # noqa: F811
    session._apply("msg", {"from": "ali@x", "nick": "ali", "body": "gizli",
                           "mid": "w1", "spoiler": "film"})
    ev = session.sink.get_nowait()
    assert ev["ev"] == "msg" and ev["data"]["spoiler"] == "film"
    rows = session.history("ali@x")["messages"]
    assert rows[-1]["mid"] == "w1" and rows[-1]["spoiler"] == "film"


def test_web_history_plain_rows_have_no_spoiler_key(session):  # noqa: F811
    session._apply("msg", {"from": "ali@x", "nick": "ali", "body": "selam",
                           "mid": "w2"})
    assert "spoiler" not in session.history("ali@x")["messages"][-1]


def test_web_send_spoiler(session):  # noqa: F811
    r = session.command("send", {"to": "ali@x", "body": "gizli",
                                 "spoiler": " film "})
    assert r["ok"]
    (_n, args, kw), = [c for c in session.bot.calls if c[0] == "send_chat"]
    assert kw["spoiler"] == "film"
    assert st._db_load_spoilers("ali@x") == {r["mid"]: "film"}


def test_web_send_spoiler_refused_in_encrypted_chat(session):  # noqa: F811
    session.enc_modes["ali@x"] = "omemo"
    r = session.command("send", {"to": "ali@x", "body": "gizli",
                                 "spoiler": "film"})
    assert r["ok"] is False and "gönderilemez" in r["error"]
    assert not [c for c in session.bot.calls if c[0] == "send_chat"]


def test_web_spoiler_ui_wiring():
    from webapp import server as srv
    js = (srv.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="send-menu"' in html
    assert "data-reveal" in js and "spoilerCover(" in js
    assert "bindLongPress($(\"btn-send\")" in js
    notify = js.split("  msg(data) {", 1)[1].split("\n  },", 1)[0]
    assert "spoilerLabel(data.spoiler)" in notify      # bildirim de örtülü


# ── Sunucu arşivi (MAM) geçmişi ve ayrı sohbet sekmesi ──────────────────────
def test_mam_archive_item_carries_spoiler(monkeypatch):
    """Arşivden gelen spoiler'lı mesaj da örtülü gelsin: öğe "spoiler" taşır;
    spoiler'sız öğenin yükü eskisi gibi kalır (exact-payload uyumu)."""
    from test_mam_rooms import _J, _bot_stub, _FakeMam, _Fwd, _Stanza

    from xmppcore import archive as arch

    class _XStanza(_Stanza):
        xml = None

    def _res(body, hint, mid):
        m = _XStanza({"from": _J("ali@x.im"), "body": body, "id": mid})
        m.xml = _xml(hint)
        return {"mam_result": {"forwarded": _Fwd(m, "2026-11-25T10:00:00Z"),
                               "id": "A-" + mid}}

    fake = _FakeMam([_res("katil uşak", "film", "m1"),
                     _res("sır", "", "m2"), _res("düz", None, "m3")])
    monkeypatch.setattr(arch, "_get_xep", lambda bot, name: fake)
    bot = _bot_stub(room=False)
    asyncio.run(arch.ArchiveMixin._fetch_mam(bot, "ali@x.im", 50))
    _kind, data = bot.gui_q.get_nowait()
    first, second, third = data["messages"]
    assert first["spoiler"] == "film"
    assert second["spoiler"] == ""                 # uyarısız spoiler
    assert "spoiler" not in third


def test_mam_encrypted_item_ignores_spoiler_mark(monkeypatch):
    """Canlı yolla aynı: şifreli mesajdaki spoiler işareti yok sayılır (kural 1)."""
    from test_mam_rooms import _J, _bot_stub, _FakeMam, _Fwd, _Stanza

    from xmppcore import archive as arch

    class _XStanza(_Stanza):
        xml = None

    m = _XStanza({"from": _J("ali@x.im"), "body": "", "id": "e1"})
    m.xml = _xml("film")
    ET.SubElement(m.xml, "{eu.siacs.conversations.axolotl}encrypted")
    fake = _FakeMam([{"mam_result": {"forwarded": _Fwd(m, "2026-11-25T10:00:00Z"),
                                     "id": "A-e1"}}])
    monkeypatch.setattr(arch, "_get_xep", lambda bot, name: fake)
    bot = _bot_stub(room=False)
    asyncio.run(arch.ArchiveMixin._fetch_mam(bot, "ali@x.im", 50))
    _kind, data = bot.gui_q.get_nowait()
    item, = data["messages"]
    assert item["body"].startswith("🔒") and "spoiler" not in item


def test_desktop_mam_results_note_spoiler(db):
    from test_history_window_bounds import _win

    w = _win([], jid="ali@x.im")
    xmpp.MainWindow._handle(w, "mam_results", {
        "jid": "ali@x.im", "token": 0, "messages": [
            {"from": "ali@x.im", "body": "katil uşak", "ts": "",
             "is_me": False, "mid": "M1", "spoiler": "film"},
            {"from": "ali@x.im", "body": "düz", "ts": "", "is_me": False,
             "mid": "M2"},
        ]})
    assert [e[1] for e in w.chats["ali@x.im"]] == ["katil uşak", "düz"]
    assert w._spoilers == {("ali@x.im", "M1"): "film"}


def test_web_mam_results_store_spoiler(session):  # noqa: F811
    session._apply("mam_results", {"jid": "ali@x", "messages": [
        {"from": "ali@x", "body": "katil uşak", "ts": "2026-11-25T10:00:00Z",
         "is_me": False, "mid": "M1", "spoiler": "film"},
        {"from": "ali@x", "body": "düz", "ts": "2026-11-25T10:01:00Z",
         "is_me": False, "mid": "M2"},
    ]})
    assert st._db_load_spoilers("ali@x") == {"M1": "film"}
    rows = {r["mid"]: r for r in session.history("ali@x")["messages"]}
    assert rows["M1"]["spoiler"] == "film" and "spoiler" not in rows["M2"]


class _Label:
    """Sohbet sekmesindeki gövde etiketi (tk.Label yüzeyi)."""

    def __init__(self):
        self.opts = {}
        self.binds = {}

    def configure(self, **kw):
        self.opts.update(kw)

    def bind(self, seq, fn):
        self.binds[seq] = fn

    def unbind(self, seq):
        self.binds.pop(seq, None)


def test_chat_tab_spoiler_cover_reveals_on_click():
    w = object.__new__(xmpp.MainWindow)
    lbl = _Label()
    xmpp.MainWindow._cover_tab_spoiler(w, lbl, "katil uşak", "film", "#eee")
    assert lbl.opts["text"] == sp.cover("film")      # gövde görünmez
    assert "katil uşak" not in lbl.opts["text"]
    lbl.binds["<Button-1>"](None)
    assert lbl.opts["text"] == "katil uşak" and lbl.opts["fg"] == "#eee"
    assert "<Button-1>" not in lbl.binds             # ikinci tık bir şey yapmaz


def test_chat_tab_add_uses_spoiler_cover():
    """`_open_chat_tab._add` gövdeyi düz etiketle çiziyordu; örtü uygulanmalı."""
    import inspect
    src = inspect.getsource(xmpp.MainWindow._open_chat_tab)
    assert "_cover_tab_spoiler(" in src and "_spoiler_map()" in src


# ── Masaüstü medya önizlemesi ───────────────────────────────────────────────
def _media_mw(monkeypatch):
    from test_chat_media import _MW
    from test_media_per_message_bounds import _bounds_mw

    mw, c = _bounds_mw(monkeypatch)
    monkeypatch.setattr(xmpp.tk, "Frame", _MW)          # bağlantı önizlemesi çerçevesi
    monkeypatch.setattr(xmpp.tk, "Label", _MW)
    monkeypatch.setattr(_MW, "cget", lambda self, k: self.kw.get(k),
                        raising=False)
    monkeypatch.setattr(_MW, "destroy", lambda self: c.setdefault(
        "destroyed", []).append(self), raising=False)
    mw._spoilers = {("a@b", "m1"): "film"}
    return mw, c


def test_spoiler_media_preview_deferred_until_reveal(monkeypatch):
    """Spoiler'lı mesajdaki resim ve bağlantı önizlemesi örtü açılana kadar
    çizilmez ve ağdan çekilmez (çekmek gönderenin sunucusuna da haber verir)."""
    mw, c = _media_mw(monkeypatch)
    row = mw._append("bak http://x/i0.png http://x/page", "them", sender="A",
                     mid="m1")
    assert c["rich_img"] == c["req_img"] == c["preview"] == []
    assert row._spoiler_hidden
    assert row._body_text.binds["<Button-1>"][-1](None) == "break"
    assert c["req_img"] == ["http://x/i0.png"]
    assert c["preview"] == ["http://x/page"]
    row._body_text.binds["<Button-1>"][-1](None)       # ikinci tık: yeniden çekmez
    assert c["req_img"] == ["http://x/i0.png"]


def test_spoiler_image_only_message_gets_own_cover(monkeypatch):
    """Metinsiz (yalnız resim) spoiler'da örtülecek gövde yok: ayrı örtü çıkar."""
    mw, c = _media_mw(monkeypatch)
    row = mw._append("http://x/i0.png", "them", sender="A", mid="m1")
    assert c["req_img"] == []
    covers = [w for w in row._bubble.children
              if w.kw.get("text") == sp.cover("film")]
    assert len(covers) == 1 and row._spoiler_hidden
    covers[0].binds["<Button-1>"][-1](None)
    assert c["req_img"] == ["http://x/i0.png"]
    assert covers[0] in c["destroyed"] and not row._spoiler_hidden


def test_plain_message_media_unchanged(monkeypatch):
    mw, c = _media_mw(monkeypatch)
    mw._append("bak http://x/i0.png http://x/page", "them", sender="A",
               mid="m9")                                # spoiler'sız
    assert c["req_img"] == ["http://x/i0.png"]
    assert c["preview"] == ["http://x/page"]
