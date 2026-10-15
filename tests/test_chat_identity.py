"""FAZ 4C-3A: ui/chat/identity.py contract + MainWindow orchestration."""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui.chat.identity as ident_mod  # noqa: E402
import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Lbl:
    def __init__(self, text=""):
        self._text = text
        self.configs = []
        self._exists = True

    def winfo_exists(self):
        return self._exists

    def config(self, **k):
        self.configs.append(k)
        if "text" in k:
            self._text = k["text"]

    def cget(self, key):
        return self._text if key == "text" else ""


def _theme():
    return xmpp._chat_theme()


def _row(mid="", body="x", is_me=False, retracted=False, label=None):
    r = types.SimpleNamespace(_mid=mid, _body=body, _is_me=is_me,
                              _retracted=retracted, _edited=False)
    if label is not None:
        r._body_label = label
    return r


# ── 1-3) lookup ─────────────────────────────────────────────────────────────
def test_find_row_by_mid_and_unknown_and_duplicate():
    a, b, c = _row(mid="m1"), _row(mid="m2"), _row(mid="m1")
    rows = [a, b, c]
    assert ident_mod.find_row_by_mid(rows, "m2") is b
    assert ident_mod.find_row_by_mid(rows, "m1") is a  # ilk eşleşme
    assert ident_mod.find_row_by_mid(rows, "yok") is None
    assert ident_mod.find_row_by_mid(rows, "") is None


# ── 4-5) correction ─────────────────────────────────────────────────────────
def test_apply_correction_only_target(monkeypatch):
    ubt = _Capture()
    monkeypatch.setattr(ident_mod, "update_bubble_text", ubt)
    r1, r2 = _row(mid="m1", body="old"), _row(mid="m2", body="keep")
    ident_mod.apply_correction_to_row(r1, "yeni", formatter=lambda t: [],
                                      theme=_theme())
    assert (r1._body, r1._edited) == ("yeni", True)
    assert (r2._body, r2._edited) == ("keep", False)
    assert ubt.calls[0][0] == (r1, "yeni")
    assert ubt.calls[0][1]["edited"] is True


# ── 6-7) retraction ─────────────────────────────────────────────────────────
def test_apply_retraction_only_target_and_visual_state(monkeypatch):
    ubt = _Capture()
    cleared = []
    monkeypatch.setattr(ident_mod, "update_bubble_text", ubt)
    r1, r2 = _row(mid="m1", body="x"), _row(mid="m2", body="keep")
    ident_mod.apply_retraction_to_row(
        r1, "🚫 Bu mesaj silindi", formatter=lambda t: [], theme=_theme(),
        clear_reactions=cleared.append)
    assert (r1._body, r1._retracted) == ("🚫 Bu mesaj silindi", True)
    assert (r2._body, r2._retracted) == ("keep", False)
    assert ubt.calls[0][1]["retracted"] is True
    assert cleared == [r1]


# ── 9) last row lookup ──────────────────────────────────────────────────────
def test_find_last_message_row():
    # last message row: mid'li, retracted olmayan, yön filtresi
    r1 = _row(mid="m1", is_me=False)
    r2 = _row(mid="m2", is_me=False, retracted=True)
    r3 = _row(mid="", is_me=False)
    assert ident_mod.find_last_message_row([r1, r2, r3], False) is r1
    assert ident_mod.find_last_message_row([r1, r2], True) is None


# ── 10-11) sent_mid MW integration (J.3) ────────────────────────────────────
def test_sent_mid_matching_and_non_matching_target():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    blank = _row(mid="", is_me=True)
    w._bubble_widgets = [blank]
    w._msg_ids = {}
    w._reactions = {}
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "a@b", "mid": "wire"})
    assert blank._mid == "wire"
    assert w._msg_ids["a@b"] == ["wire"]

    blank2 = _row(mid="", is_me=True)
    w._bubble_widgets = [blank2]
    xmpp.MainWindow._handle(w, "sent_mid", {"to": "baska@x", "mid": "wire2"})
    assert blank2._mid == ""
    assert w._msg_ids["baska@x"] == ["wire2"]  # domain semantics korunur


# ── 12-14) orchestration: UI + chats + DB (+reaction cleanup) ───────────────
def _orch_window():
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    lbl1, lbl2 = _Lbl("old"), _Lbl("keep")
    r1 = _row(mid="m1", body="old", label=lbl1)
    r2 = _row(mid="m2", body="keep", label=lbl2)
    w._bubble_widgets = [r1, r2]
    w.chats = {"a@b": [
        ("Ali", "old", False, "10:00", "them", "", False, "m1", ""),
        ("Bob", "keep", False, "10:01", "them", "", False, "m2", ""),
    ]}
    w._reactions = {("a@b", "m1"): {"👍": ["Ali"]}}  # [2M] (jid, mid) kapsamlı
    w._my_reactions = {("a@b", "m1"): {"👍"}}
    w._render_reactions = _Capture()
    return w, r1, r2, lbl1, lbl2


def test_local_edit_orchestration_ui_chats_db(monkeypatch):
    w, r1, r2, lbl1, lbl2 = _orch_window()
    db = _Capture()
    monkeypatch.setattr(xmpp, "_db_update_msg_body", db)

    xmpp.MainWindow._apply_local_correction(w, "a@b", "m1", "yeni")

    assert lbl1._text == "yeni  ✏" and lbl2._text == "keep"
    assert (r1._edited, r2._edited) == (True, False)
    assert w.chats["a@b"][0][1] == "yeni" and w.chats["a@b"][0][0] == "Ali"
    assert db.calls[0][0] == ("a@b", "m1", "yeni")  # [2J.a] (jid, mid) kapsamlı


def test_local_retract_orchestration_ui_chats_maps_db(monkeypatch):
    w, r1, r2, lbl1, lbl2 = _orch_window()
    db, dbr = _Capture(), _Capture()
    monkeypatch.setattr(xmpp, "_db_update_msg_body", db)
    monkeypatch.setattr(xmpp, "_db_clear_reactions_mid", dbr)

    xmpp.MainWindow._apply_local_retraction(w, "a@b", "m1")

    assert lbl1._text == "🚫 Bu mesaj silindi" and lbl2._text == "keep"
    assert (r1._retracted, r2._retracted) == (True, False)
    assert w._render_reactions.calls[0][0] == (r1, {})
    assert ("a@b", "m1") not in w._reactions  # [2M] composite kapsam
    assert ("a@b", "m1") not in w._my_reactions
    assert w.chats["a@b"][0][1] == "🚫 Bu mesaj silindi"
    assert db.calls[0][0] == ("a@b", "m1", "🚫 Bu mesaj silindi")  # [2J.a] jid kapsamlı
    assert dbr.calls[0][0] == ("a@b", "m1")


def test_incoming_correction_and_retraction_orchestration(monkeypatch):
    w, r1, r2, lbl1, lbl2 = _orch_window()
    db = _Capture()
    monkeypatch.setattr(xmpp, "_db_update_msg_body", db)
    monkeypatch.setattr(xmpp, "_db_clear_reactions_mid", _Capture())

    xmpp.MainWindow._handle(w, "msg_correction",
                            {"from": "a@b", "orig_id": "m1", "body": "yeni"})
    assert lbl1._text == "yeni  ✏" and r1._edited is True

    xmpp.MainWindow._handle(w, "msg_retract",
                            {"from": "a@b", "retracted_id": "m2"})
    assert lbl2._text == "🚫 Bu mesaj silindi" and r2._retracted is True
    assert "m2" not in w._reactions and "m2" not in w._my_reactions


# ── 15) scroll helper (minimal) ─────────────────────────────────────────────
def test_scroll_to_row_minimal():
    class _Canvas:
        def __init__(self):
            self.moves = []

        def yview_moveto(self, v):
            self.moves.append(v)

    class _Frame:
        def update_idletasks(self):
            pass

        def winfo_height(self):
            return 100

    class _Row:
        def winfo_y(self):
            return 110

    c = _Canvas()
    ident_mod.scroll_to_row(c, _Frame(), _Row())
    assert c.moves == [0.5]  # max(0, min(1, (110-60)/100))


# ── 16) no domain leak ──────────────────────────────────────────────────────
def test_identity_has_no_domain_dependencies():
    src = inspect.getsource(ident_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot",
                  "run_coroutine_threadsafe", "sqlite", "_db_", "urlopen(",
                  "threading.", "gui_q", "subprocess", "_safe_after",
                  "import xmpp", ".after("):
        assert token not in src, token
