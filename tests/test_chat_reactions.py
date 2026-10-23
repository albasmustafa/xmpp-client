"""FAZ 4C-3B: ui/chat/reactions.py contract + MainWindow orchestration parity."""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui.chat.reactions as react_mod  # noqa: E402
import xmpp  # noqa: E402


class _Capture:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _W:
    def __init__(self, master=None, **kw):
        self.master = master
        self.kw = dict(kw)
        self.binds = {}
        self.children = []
        self.destroyed = False
        if master is not None and isinstance(master, _W):
            master.children.append(self)

    def pack(self, *a, **k):
        self.kw.setdefault("_pack", (a, k))

    def grid(self, *a, **k):
        pass

    def bind(self, seq, fn=None, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def bindtags(self, tags=None):              # _add_tooltip: "Tooltip" etiketi
        if tags is None:
            return getattr(self, "_tags", ("_W",))
        self._tags = tuple(tags)

    def bind_class(self, tag, seq=None, fn=None, add=None):
        return ""

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        self.destroyed = True
        if self.master is not None and self in self.master.children:
            self.master.children.remove(self)

    def config(self, **k):
        self.kw.update(k)

    def cget(self, key):
        return self.kw.get(key, "")


def _patch_tk(monkeypatch):
    monkeypatch.setattr(react_mod, "tk",
                        types.SimpleNamespace(Frame=_W, Label=_W))


def _row(mid="m1", is_me=False, retracted=False):
    r = _W()
    r._mid = mid
    r._is_me = is_me
    r._retracted = retracted
    r._body = "gövde"
    r._sender = "Ali"
    return r


def _render(row, reactions, mine=None, **over):
    a = dict(theme=xmpp._chat_theme(), on_toggle=_Capture(),
             on_details=_Capture(), on_reply=_Capture(), on_add=_Capture(),
             tooltip_fn=lambda s: "T:" + ",".join(s), add_tooltip=_Capture())
    a.update(over)
    rf = react_mod.render_reactions(row, reactions, mine or set(), **a)
    return rf, a


def _chips(rf):
    return [c for c in rf.children]


# ── 1-3) construction + counts ──────────────────────────────────────────────
def test_empty_reactions_with_and_without_mid(monkeypatch):
    _patch_tk(monkeypatch)
    row = _row(mid="m1")
    rf, _ = _render(row, {})
    texts = [c.kw.get("text") for c in _chips(rf)]
    assert texts == ["↩", "＋"]  # yalnız reply + add
    row2 = _row(mid="")
    assert _render(row2, {})[0] is None


def test_single_and_multi_sender_count_text(monkeypatch):
    _patch_tk(monkeypatch)
    rf, _ = _render(_row(), {"👍": ["Ali"]})
    assert _chips(rf)[0].kw["text"] == "👍"
    rf2, _ = _render(_row(), {"👍": ["Ali", "Veli"]})
    assert _chips(rf2)[0].kw["text"] == "👍 2"


def test_multiple_emoji_order_unchanged(monkeypatch):
    _patch_tk(monkeypatch)
    reactions = {"😂": ["Ali"], "👍": ["Ali", "Veli"], "❤": ["Ali", "Veli"]}
    rf, _ = _render(_row(mid=""), reactions)
    got = [c.kw["text"] for c in _chips(rf)]
    expected = [(f"{em} {len(s)}" if len(s) > 1 else em) for em, s in
                sorted(reactions.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    assert got == expected


# ── 4-5) mine/non-mine styling ──────────────────────────────────────────────
def test_mine_and_non_mine_styling(monkeypatch):
    _patch_tk(monkeypatch)
    rf, _ = _render(_row(), {"👍": ["Ben"], "❤": ["Ali"]}, mine={"👍"})
    by_text = {c.kw.get("text"): c for c in _chips(rf)}
    assert by_text["👍"].kw["fg"] == xmpp.FG_ME
    assert by_text["👍"].kw["bg"] == xmpp.ACCENT2
    assert by_text["❤"].kw["fg"] == xmpp.FG
    assert by_text["❤"].kw["bg"] == xmpp.BG_HOVER


# ── 6-7) callbacks exactly once ─────────────────────────────────────────────
def test_toggle_details_reply_add_callbacks(monkeypatch):
    _patch_tk(monkeypatch)
    rf, cb = _render(_row(), {"👍": ["Ali"]})
    chips = _chips(rf)
    chips[0].binds["<Button-1>"][0](None)
    chips[0].binds["<Button-3>"][0](None)
    chips[1].binds["<Button-1>"][0](None)  # ↩
    chips[2].binds["<Button-1>"][0](None)  # ＋
    assert cb["on_toggle"].calls == [(("👍",), {})]
    assert cb["on_details"].calls == [(("👍",), {})]
    assert len(cb["on_reply"].calls) == 1
    assert len(cb["on_add"].calls) == 1
    # mid yoksa chip bind'i olmaz
    rf2, _ = _render(_row(mid=""), {"👍": ["Ali"]})
    assert "<Button-1>" not in _chips(rf2)[0].binds


# ── 8-9) rerender/retracted temizliği ───────────────────────────────────────
def test_rerender_clears_old_frame_and_retracted_returns_none(monkeypatch):
    _patch_tk(monkeypatch)
    row = _row()
    rf1, _ = _render(row, {"👍": ["Ali"]})
    rf2, _ = _render(row, {"👍": ["Ali", "Veli"]})
    assert rf1.destroyed is True
    frames = [c for c in row.winfo_children()
              if getattr(c, "_tag", "") == react_mod.FRAME_TAG]
    assert frames == [rf2]

    ret_row = _row(retracted=False)
    old, _ = _render(ret_row, {"👍": ["Ali"]})
    ret_row._retracted = True
    out, _ = _render(ret_row, {"👍": ["Ali"]})
    assert out is None and old.destroyed is True
    assert [c for c in ret_row.winfo_children()
            if getattr(c, "_tag", "") == react_mod.FRAME_TAG] == []


# ── 10) incoming orchestration: state + DB + presentation ───────────────────
def _mw(reactions=None, mine=None, rows=None, active="a@b"):
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w.jid = "ben@example.com"
    w.rooms = []
    w.my_nick = {}
    w.chats = {}
    w._reactions = reactions or {}
    w._my_reactions = mine or {}
    w._bubble_widgets = rows or []
    w._render_reactions = lambda row, r: xmpp.MainWindow._render_reactions(w, row, r)
    w._scroll_bottom = lambda: None
    w._set_reply = lambda *a: None
    w._show_emoji_picker = lambda *a: None
    w._reaction_details_dialog = lambda *a: None
    w._toggle_reaction = lambda *a: None
    return w


def test_incoming_reaction_orchestration(monkeypatch):
    _patch_tk(monkeypatch)
    calls = []
    real = react_mod.render_reactions

    def spy(row, reactions, mine, **kw):
        calls.append((row, dict(reactions), set(mine)))
        return real(row, reactions, mine, **kw)

    monkeypatch.setattr(xmpp._reactions_ui, "render_reactions", spy)
    db = _Capture()
    monkeypatch.setattr(xmpp, "_db_save_reaction", db)
    row = _row(mid="m1")
    w = _mw(rows=[row])

    xmpp.MainWindow._handle(w, "msg_reactions", {
        "from": "a@b", "target_id": "m1", "nick": "Ali", "emojis": ["👍"]})

    assert w._reactions[("a@b", "m1")]["👍"] == ["Ali"]  # [2M] (jid, mid)
    assert db.calls[0][0] == ("a@b", "m1", "👍", "Ali", True)
    assert len(calls) == 1 and calls[0][0] is row
    assert calls[0][1] == {"👍": ["Ali"]}

    # kendi nick'imiz → _my_reactions güncellenir
    xmpp.MainWindow._handle(w, "msg_reactions", {
        "from": "a@b", "target_id": "m1", "nick": "Ben", "emojis": ["👍"]})
    assert w._my_reactions[("a@b", "m1")] == {"👍"}


def test_incoming_reaction_inactive_and_unknown_mid(monkeypatch):
    _patch_tk(monkeypatch)
    calls = []
    monkeypatch.setattr(xmpp._reactions_ui, "render_reactions",
                        lambda *a, **k: calls.append(a) or None)
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    row = _row(mid="m1")

    w = _mw(rows=[row], active="x@y")
    xmpp.MainWindow._handle(w, "msg_reactions", {
        "from": "a@b", "target_id": "m1", "nick": "Ali", "emojis": ["👍"]})
    assert calls == [] and w._reactions[("a@b", "m1")]["👍"] == ["Ali"]

    w2 = _mw(rows=[row], active="a@b")
    xmpp.MainWindow._handle(w2, "msg_reactions", {
        "from": "a@b", "target_id": "yok", "nick": "Ali", "emojis": ["👍"]})
    assert calls == [] and w2._reactions[("a@b", "yok")]["👍"] == ["Ali"]


# ── 11) local toggle orchestration parity ───────────────────────────────────
def test_local_toggle_orchestration(monkeypatch):
    _patch_tk(monkeypatch)
    calls = []
    monkeypatch.setattr(xmpp._reactions_ui, "render_reactions",
                        lambda *a, **k: calls.append(a) or None)
    db_save, db_clear = _Capture(), _Capture()
    monkeypatch.setattr(xmpp, "_db_save_reaction", db_save)
    monkeypatch.setattr(xmpp, "_db_clear_my_reactions", db_clear)
    sent = []
    row = _row(mid="m1")
    w = _mw(rows=[row])
    w.bot = types.SimpleNamespace(
        send_reaction=lambda to, mid, emojis, mtype:
            sent.append((to, mid, list(emojis), mtype)))

    xmpp.MainWindow._toggle_reaction(w, "m1", "👍")

    assert sent == [("a@b", "m1", ["👍"], "chat")]
    assert w._my_reactions[("a@b", "m1")] == {"👍"}   # [2M] (jid, mid)
    assert w._reactions[("a@b", "m1")]["👍"] == ["Ben"]
    assert db_clear.calls[0][0] == ("a@b", "m1")
    assert db_save.calls[0][0] == ("a@b", "m1", "👍", "Ben", True)
    assert len(calls) == 1 and calls[0][0] is row

    # aynı tepkiyi kaldır → tam küme + map temizliği
    xmpp.MainWindow._toggle_reaction(w, "m1", "👍")
    assert sent[-1] == ("a@b", "m1", [], "chat")
    assert ("a@b", "m1") not in w._my_reactions
    assert w._reactions.get(("a@b", "m1")) is None


# ── 12) retraction presentation clear ───────────────────────────────────────
def test_retraction_clears_reaction_chips(monkeypatch):
    _patch_tk(monkeypatch)
    monkeypatch.setattr(xmpp, "_db_update_msg_body", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_clear_reactions_mid", lambda *a: None)
    lbl = types.SimpleNamespace(text="x", winfo_exists=lambda: True,
                                config=lambda **k: None)
    row = _row(retracted=False)
    row._body_label = lbl
    rf, _ = _render(row, {"👍": ["Ben"]})  # mevcut çipler
    w = _mw(reactions={("a@b", "m1"): {"👍": ["Ben"]}},  # [2M] composite
            mine={("a@b", "m1"): {"👍"}}, rows=[row])

    xmpp.MainWindow._apply_local_retraction(w, "a@b", "m1")

    assert row._retracted is True and rf.destroyed is True
    assert [c for c in row.winfo_children()
            if getattr(c, "_tag", "") == react_mod.FRAME_TAG] == []
    assert ("a@b", "m1") not in w._reactions  # [2M] composite kapsam
    assert ("a@b", "m1") not in w._my_reactions


# ── 13) no domain leak ──────────────────────────────────────────────────────
def test_reactions_has_no_domain_dependencies():
    src = inspect.getsource(react_mod)
    for token in ("slixmpp", "ClientXMPP", "XMPPBot",
                  "run_coroutine_threadsafe", "sqlite", "_db_", "urlopen(",
                  "threading.", "gui_q", "subprocess", "_safe_after",
                  "import xmpp", "asyncio"):
        assert token not in src, token
