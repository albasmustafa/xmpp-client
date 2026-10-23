"""AI asistanı MainWindow entegrasyonu — Tk'sız pencere çiftleriyle.

Kanıtlar:
- Mesaj yetenekleri satır içeriğinden türetilir (metin/ses/görsel/SVG).
- Sağ tık menüsü ✨ AI alt menüsünü yalnız yetenek varsa kurar.
- Gizlilik: şifreli sohbet + bulut → kullanıcı reddederse hiçbir model
  çağrısı yapılmaz; onaylarsa yalnız o istek için allow_cloud=True.
- Özet okunmamış sayısını (sohbet açılış anı) kullanır.
- Taslak düzenleme: metin değişmediyse yerine yazar ve geri alınabilir;
  değiştiyse üzerine yazmaz.
- Anlamsal arama uçtan uca (tmp SQLite + sahte gömme).
- Ses→metin ve görsel açıklama önbelleğe alınır; geçici dosya kalmaz.
- Giriş kutusu ✨ butonu yalnız on_ai verilince oluşur.
"""
import io
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _win  # noqa: E402

import ui.chat.actions as actions_mod  # noqa: E402
import ui.chat.shell as shell_mod  # noqa: E402
import xmpp  # noqa: E402


class _Cap:
    def __init__(self, ret=None):
        self.calls = []
        self.ret = ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret


def _row(body="merhaba", oob="", local_path="", encrypted=False,
         retracted=False, mid="m1"):
    return types.SimpleNamespace(_body=body, _oob=oob, _local_path=local_path,
                                 _encrypted=encrypted, _retracted=retracted,
                                 _mid=mid, _is_me=False, _sender="Ali",
                                 _reply_to=None)


class _FakeWin:
    """ui/dialogs/ai.ResultWindow / SemanticSearchWindow çifti."""
    instances = []

    def __init__(self, parent, title, subtitle="", actions=(), **kw):
        self.title = title
        self.subtitle = subtitle
        self.kw = kw
        self.text = None
        self.error = None
        self.busy = None
        self.choices = None
        self.statuses = []
        self.results = None
        _FakeWin.instances.append(self)

    def set_text(self, text, status=""):
        self.text = text

    def set_error(self, msg):
        self.error = msg

    def set_busy(self, msg):
        self.busy = msg

    def set_choices(self, items, on_pick, hint=""):
        self.choices = (items, on_pick)

    def set_status(self, msg, error=False):
        self.statuses.append((msg, error))

    def set_results(self, results):
        self.results = results


class _Entry:
    def __init__(self, text="", placeholder=False):
        self.text = text
        self._showing_ph = placeholder
        self.focused = False

    def get_value(self):
        return "" if self._showing_ph else self.text

    def configure(self, **k):
        pass

    def focus_set(self):
        self.focused = True

    def icursor(self, _):
        pass


class _Var:
    def __init__(self, entry):
        self.entry = entry

    def get(self):
        return self.entry.text

    def set(self, v):
        self.entry.text = v


def _mw(monkeypatch, settings=None, chats=None, enc=None):
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@b"
    w.jid = "ben@example.com"
    w.rooms = []
    w.root = object()
    w.chats = chats if chats is not None else {"a@b": [
        ("Ali", "Yarın 14:00'te buluşalım mı?", False, "10:00", "them", "",
         False, "m1", "", 1),
        ("Ben", "Olur", True, "10:01", "me", "", False, "m2", "", 2)]}
    w._chat_enc_modes = dict(enc or {})
    w._bubble_widgets = []
    w._temp_files = []
    s = xmpp._ai.load_settings({})
    s.update(settings or {})
    w._ai_settings = lambda: dict(s)
    # Senkron worker: iş hemen çalışır, sonuç doğrudan GUI tarafına gider.
    def _submit(job, done, err):
        try:
            done(job())
        except xmpp._ai.AIError as e:
            err(e)
    w._ai_submit = _submit
    w._safe_after = lambda ms, fn, *a: fn(*a)
    _FakeWin.instances = []
    monkeypatch.setattr(xmpp._ui_ai, "ResultWindow", _FakeWin)
    monkeypatch.setattr(xmpp._ui_ai, "SemanticSearchWindow",
                        lambda parent, subtitle, on_search, on_open:
                        _FakeWin(parent, "Anlamsal", subtitle,
                                 on_search=on_search, on_open=on_open))
    return w


def _chat_spy(monkeypatch, reply="Özet metni"):
    spy = _Cap(ret=reply)
    monkeypatch.setattr(xmpp._ai, "chat", spy)
    return spy


# ── 1) Yetenekler ───────────────────────────────────────────────────────────
def test_message_items_from_row_content(monkeypatch):
    w = _mw(monkeypatch)
    items = xmpp.MainWindow._ai_message_items
    assert items(w, _row("selam")) == {"ai_translate", "ai_speak"}
    assert items(w, _row("", oob="https://x.org/v.ogg")) == {"ai_transcribe"}
    assert items(w, _row("bak https://x.org/p.jpg")) == {
        "ai_translate", "ai_describe", "ai_ask_image", "ai_speak"}
    assert items(w, _row("https://x.org/logo.svg")) == set()
    assert items(w, _row("selam", retracted=True)) == set()


def test_context_menu_adds_ai_caps_and_callbacks(monkeypatch):
    w = _mw(monkeypatch)
    w.bot = object()
    w._reactions = {}
    w._my_reactions = {}
    w._ai_translate_row = _Cap()
    w._ai_describe_row = _Cap()
    captured = {}
    monkeypatch.setattr(xmpp._actions_ui, "show_context_menu",
                        lambda parent, x, y, **kw: captured.update(kw))
    row = _row("bak https://x.org/p.png")
    xmpp.MainWindow._message_context_menu(
        w, types.SimpleNamespace(x_root=1, y_root=2), row)
    caps = captured["caps"]
    assert caps["ai_translate"] and caps["ai_describe"]
    assert caps["ai_ask_image"] and not caps["ai_transcribe"]
    captured["callbacks"]["on_ai_translate"]()
    captured["callbacks"]["on_ai_ask_image"]()
    assert w._ai_translate_row.calls == [((row,), {})]
    assert w._ai_describe_row.calls == [((row,), {"ask": True})]


class _FakeMenu:
    def __init__(self, parent=None, **kw):
        self.items = []
        _FakeMenu.all.append(self)

    def add_command(self, label=None, command=None, **k):
        self.items.append(("cmd", label, command))

    def add_separator(self):
        self.items.append(("sep", None, None))

    def add_cascade(self, label=None, menu=None, **k):
        self.items.append(("cascade", label, menu))

    def tk_popup(self, x, y):
        pass

    def grab_release(self):
        pass


def _theme():
    return {k: "#000" for k in ("BG_CARD", "FG", "SEL_BG", "SEL_FG")} | {
        "FONT": "Sans"}


def test_actions_ai_cascade_only_with_caps(monkeypatch):
    _FakeMenu.all = []
    monkeypatch.setattr(actions_mod, "tk",
                        types.SimpleNamespace(Menu=_FakeMenu))
    cb = {"on_copy": _Cap(), "on_ai_translate": _Cap(),
          "on_ai_transcribe": _Cap()}
    actions_mod.show_context_menu(
        "ROOT", 0, 0, theme=_theme(), t=str.upper,
        caps={"copy": True, "ai_translate": True, "ai_transcribe": True},
        mine=set(), has_reactions=False, callbacks=cb)
    root_menu = _FakeMenu.all[0]
    kinds = [it[0] for it in root_menu.items]
    assert kinds == ["cmd", "sep", "cascade"]
    assert root_menu.items[-1][1] == "✨ AI"
    sub = root_menu.items[-1][2]
    assert [it[1] for it in sub.items] == ["🌐 Çevir", "🎙 Sesi yazıya dök"]
    sub.items[1][2]()
    assert len(cb["on_ai_transcribe"].calls) == 1


# ── 2) Gizlilik kapısı ──────────────────────────────────────────────────────
def test_sensitive_detection(monkeypatch):
    w = _mw(monkeypatch, enc={"a@b": "omemo"})
    f = xmpp.MainWindow._ai_is_sensitive
    assert f(w, "a@b") is True
    assert f(w, "x@y") is False
    assert f(w, "x@y", row=_row(encrypted=True)) is True
    assert f(w, "x@y", entries=[("A", "b", False, "t", "them", "", True)])


def test_summary_encrypted_cloud_declined_sends_nothing(monkeypatch):
    w = _mw(monkeypatch, settings={"provider": "claude"},
            enc={"a@b": "omemo"})
    spy = _chat_spy(monkeypatch)
    asked = _Cap(ret=False)
    monkeypatch.setattr(xmpp.messagebox, "askyesno", asked)
    xmpp.MainWindow._ai_summarize(w, "a@b")
    assert len(asked.calls) == 1
    assert spy.calls == [] and _FakeWin.instances == []


def test_summary_encrypted_cloud_consent_is_per_request(monkeypatch):
    w = _mw(monkeypatch, settings={"provider": "claude"},
            enc={"a@b": "omemo"})
    spy = _chat_spy(monkeypatch)
    monkeypatch.setattr(xmpp.messagebox, "askyesno", _Cap(ret=True))
    xmpp.MainWindow._ai_summarize(w, "a@b")
    (args, kw), = spy.calls
    assert kw["sensitive"] is True and kw["allow_cloud"] is True
    assert kw["effort"] == "medium"
    assert "Yarın 14:00" in args[2] and "Ben: Olur" in args[2]
    assert _FakeWin.instances[0].text == "Özet metni"


def test_ai_off_offers_settings_and_sends_nothing(monkeypatch):
    w = _mw(monkeypatch, settings={"provider": "off"})
    spy = _chat_spy(monkeypatch)
    monkeypatch.setattr(xmpp.messagebox, "askyesno", _Cap(ret=True))
    w._ai_settings_dialog = _Cap()
    xmpp.MainWindow._ai_suggest_replies(w)
    assert spy.calls == [] and len(w._ai_settings_dialog.calls) == 1


def test_local_provider_encrypted_needs_no_prompt(monkeypatch):
    w = _mw(monkeypatch, enc={"a@b": "omemo"})
    spy = _chat_spy(monkeypatch, reply="Hello")
    asked = _Cap(ret=False)
    monkeypatch.setattr(xmpp.messagebox, "askyesno", asked)
    xmpp.MainWindow._ai_translate_row(w, _row("Merhaba"))
    assert asked.calls == []
    assert spy.calls[0][1]["sensitive"] is True
    assert _FakeWin.instances[0].text == "Hello"


# ── 3) Okunmamış özeti ──────────────────────────────────────────────────────
def test_load_chat_remembers_unread_at_open():
    w = _win([], jid="a@b")
    w._unread_counts = {"a@b": 4}
    xmpp.MainWindow._load_chat(w, "a@b")
    assert w._ai_unread_at_open == {"a@b": 4}
    assert w._unread_counts["a@b"] == 0
    xmpp.MainWindow._load_chat(w, "a@b")      # yeniden açılış: okunmamış yok
    assert w._ai_unread_at_open == {"a@b": 0}


def test_unread_summary_focuses_on_unread(monkeypatch):
    chats = {"a@b": [("Ali", f"mesaj {i}", False, "10:00", "them", "",
                      False, f"m{i}", "", i) for i in range(40)]}
    w = _mw(monkeypatch, chats=chats)
    w._ai_unread_at_open = {"a@b": 5}
    spy = _chat_spy(monkeypatch)
    xmpp.MainWindow._ai_summarize(w, "a@b", unread_only=True)
    user = spy.calls[0][0][2]
    assert "last 5 messages" in user
    # 5 okunmamış + 15 bağlam = son 20 mesaj (20..39)
    assert "mesaj 20" in user and "mesaj 39" in user
    assert "mesaj 19" not in user
    assert "okunmamış 5" in _FakeWin.instances[0].title


# ── 4) Taslak düzenleme ve yanıt önerisi ────────────────────────────────────
def _composer(w, text, placeholder=False):
    w._msg_entry = _Entry(text, placeholder)
    w.msg_var = _Var(w._msg_entry)
    w._chat_shell = types.SimpleNamespace(_ai_btn=None)


def test_rewrite_replaces_and_undo_restores(monkeypatch):
    w = _mw(monkeypatch)
    _composer(w, "yarin gelirmisin")
    spy = _chat_spy(monkeypatch, reply="Yarın gelir misin?")
    xmpp.MainWindow._ai_rewrite(w, "fix")
    assert w.msg_var.get() == "Yarın gelir misin?"
    assert "<draft>\nyarin gelirmisin\n</draft>" in spy.calls[0][0][2]
    xmpp.MainWindow._ai_undo_rewrite(w)
    assert w.msg_var.get() == "yarin gelirmisin"


def test_rewrite_does_not_clobber_changed_draft(monkeypatch):
    w = _mw(monkeypatch)
    _composer(w, "ilk taslak")

    def _chat(*a, **k):
        w._msg_entry.text = "kullanıcı yazmaya devam etti"
        return "Düzeltilmiş"
    monkeypatch.setattr(xmpp._ai, "chat", _chat)
    xmpp.MainWindow._ai_rewrite(w, "formal")
    assert w.msg_var.get() == "kullanıcı yazmaya devam etti"
    assert _FakeWin.instances[-1].text == "Düzeltilmiş"


def test_rewrite_empty_or_placeholder_is_noop(monkeypatch):
    w = _mw(monkeypatch)
    _composer(w, "Mesaj yazın...", placeholder=True)
    spy = _chat_spy(monkeypatch)
    info = _Cap()
    monkeypatch.setattr(xmpp.messagebox, "showinfo", info)
    xmpp.MainWindow._ai_rewrite(w, "fix")
    assert spy.calls == [] and len(info.calls) == 1


def test_suggestions_pick_fills_composer_from_placeholder(monkeypatch):
    w = _mw(monkeypatch)
    _composer(w, "Mesaj yazın...", placeholder=True)
    _chat_spy(monkeypatch, reply="1. Olur\n2. Saat kaçta?\n3. Yarın olmaz")
    xmpp.MainWindow._ai_suggest_replies(w)
    items, on_pick = _FakeWin.instances[0].choices
    assert items == ["Olur", "Saat kaçta?", "Yarın olmaz"]
    on_pick("Saat kaçta?")
    assert w.msg_var.get() == "Saat kaçta?"
    assert w._msg_entry._showing_ph is False and w._msg_entry.focused


# ── 5) Anlamsal arama (uçtan uca, tmp SQLite) ───────────────────────────────
@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(xmpp, "_DB_PATH", str(tmp_path / "ai_mw.db"))
    monkeypatch.setattr(xmpp, "_db_conn", None)
    yield
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    monkeypatch.setattr(xmpp, "_db_conn", None)


def _fake_embed(settings, texts):
    out = []
    for t in texts:
        t = t.lower()
        if "fatura" in t or "ödeme" in t:
            out.append([1.0, 0.0, 0.0])
        elif "buluş" in t:
            out.append([0.0, 1.0, 0.0])
        else:
            out.append([0.0, 0.0, 1.0])
    return out


def test_semantic_index_and_search_end_to_end(tmp_db, monkeypatch):
    xmpp._db_store_msg("a@b", "Ali", "Cuma buluşma yeri kafe", False,
                       "10:00", "them", mid="m1")
    xmpp._db_store_msg("c@d", "Can", "Elektrik faturası 120 TL geldi", False,
                       "11:00", "them", mid="m2")
    xmpp._db_store_msg("c@d", "Can", "https://x.org/a.jpg", False, "11:01",
                       "them", mid="m3")
    monkeypatch.setattr(xmpp._ai, "ollama_embed", _fake_embed)
    w = _mw(monkeypatch)
    xmpp.MainWindow._ai_semantic_search_dialog(w)
    win = _FakeWin.instances[0]
    assert win.statuses[-1] == ("✓ 3 yeni mesaj indekslendi.", False)
    assert w._ai_indexing is False
    win.kw["on_search"]("ödeme ne kadardı")
    label, payload = win.results[0]
    assert payload == ("c@d", "m2") and "faturası" in label
    assert all(p[1] != "m3" for _l, p in win.results)   # yalnız medya elenir
    # ikinci açılış: indeks güncel
    xmpp.MainWindow._ai_semantic_search_dialog(w)
    assert _FakeWin.instances[-1].statuses[-1] == ("✓ İndeks güncel.", False)


def test_semantic_index_stuck_store_reports_error(tmp_db, monkeypatch):
    xmpp._db_store_msg("a@b", "Ali", "Cuma buluşma", False, "10:00", "them")
    monkeypatch.setattr(xmpp._ai, "ollama_embed", _fake_embed)
    monkeypatch.setattr(xmpp, "_db_ai_store_embeddings", lambda items: None)
    w = _mw(monkeypatch)
    xmpp.MainWindow._ai_semantic_search_dialog(w)
    msg, is_err = _FakeWin.instances[0].statuses[-1]
    assert is_err and "yazılamadı" in msg
    assert w._ai_indexing is False


# ── 6) Ses→metin ve görsel açıklama önbelleği ───────────────────────────────
def test_transcribe_caches_and_removes_temp(tmp_db, monkeypatch):
    w = _mw(monkeypatch)
    monkeypatch.setattr(xmpp._ai, "fetch_url", lambda url, mx: b"OggS...")
    paths = []

    def _tr(path, model):
        paths.append(path)
        assert os.path.exists(path) and path.endswith(".ogg")
        return "merhaba dünya"
    monkeypatch.setattr(xmpp._ai, "transcribe_file", _tr)
    row = _row("", oob="https://x.org/voice.ogg")
    xmpp.MainWindow._ai_transcribe_row(w, row)
    xmpp.MainWindow._ai_transcribe_row(w, row)
    assert [i.text for i in _FakeWin.instances] == ["merhaba dünya"] * 2
    assert len(paths) == 1 and not os.path.exists(paths[0])
    assert w._temp_files == []


def test_describe_image_sends_prepared_image_and_caches(tmp_db, monkeypatch):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (20, 10), "red").save(buf, "PNG")
    w = _mw(monkeypatch)
    monkeypatch.setattr(xmpp._ai, "fetch_url",
                        lambda url, mx: buf.getvalue())
    spy = _chat_spy(monkeypatch, reply="Kırmızı bir dikdörtgen.")
    row = _row("https://x.org/p.png", encrypted=True)
    xmpp.MainWindow._ai_describe_row(w, row)
    xmpp.MainWindow._ai_describe_row(w, row)
    assert len(spy.calls) == 1
    kw = spy.calls[0][1]
    assert kw["images"][0][1] == "image/jpeg" and kw["sensitive"] is True
    assert _FakeWin.instances[1].text == "Kırmızı bir dikdörtgen."
    # soru sorma önbelleğe alınmaz
    monkeypatch.setattr(xmpp.simpledialog, "askstring",
                        lambda *a, **k: "Rengi ne?")
    xmpp.MainWindow._ai_describe_row(w, row, ask=True)
    assert len(spy.calls) == 2 and "Rengi ne?" in spy.calls[1][0][2]


# ── 7) Giriş kutusu ✨ butonu ───────────────────────────────────────────────
def test_shell_ai_button_optional(monkeypatch):
    import test_chat_shell as tcs
    tcs._W.instances = []
    monkeypatch.setattr(shell_mod, "tk", types.SimpleNamespace(
        Frame=tcs._W, Label=tcs._W, Canvas=tcs._W, StringVar=tcs._Var))
    monkeypatch.setattr(shell_mod, "ttk", types.SimpleNamespace(
        Scrollbar=tcs._W, Button=tcs._W))
    calls = {k: tcs._Capture() for k in tcs.CALLBACK_KEYS}
    calls["on_ai"] = tcs._Capture()
    tip = tcs._Capture()
    sh = shell_mod.ChatShell(tcs._W(), lambda s: "T:" + s, tcs._theme(),
                             calls, entry_cls=tcs._W, add_tooltip=tip)
    assert sh._ai_btn is not None and sh._ai_btn.kw["text"] == "✨"
    sh._ai_btn.binds["<Button-1>"][0]("EV")
    assert calls["on_ai"].calls == [(("EV",), {})]
    assert any(c[0][1] == "T:ai_assistant" for c in tip.calls)
    assert "_ai_btn" not in shell_mod.ChatShell.LEGACY_REFS
