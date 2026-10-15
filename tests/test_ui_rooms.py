"""ui/rooms.py ve ui/dialogs/rooms.py sözleşmeleri (Faz 4B-3)."""

import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from ui import rooms as ui_rooms  # noqa: E402


class _List:
    def __init__(self, idx):
        self.idx = idx
        self.sel = None

    def nearest(self, y):
        return self.idx

    def selection_set(self, i):
        self.sel = i


def _ev():
    return types.SimpleNamespace(y=1, x_root=5, y_root=6)


def test_room_context_menu_delegates_and_routes(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_room_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@x"
    win._room_jids = ["r@conf"]
    win.my_nick = {"r@conf": "ben"}
    win.room_members = {"r@conf": {"ben": {"affil": "owner"}}}
    win._room_subjects = {"r@conf": "konu"}
    win.room_list = _List(0)
    calls = []
    for name, tag in (("_change_room_subject", "subject"),
                      ("_invite_to_room_dialog", "invite"),
                      ("_room_config_dialog", "config"),
                      ("_leave_room", "leave"),
                      ("_destroy_room_confirm", "destroy")):
        setattr(win, name, (lambda t: lambda *a: calls.append((t,) + a))(tag))

    xmpp.MainWindow._room_context_menu(win, _ev())

    parent, room, subject, can_admin, is_owner = captured[0][:5]
    assert (parent, room, subject) == ("ROOT", "r@conf", "konu")
    assert can_admin is True and is_owner is True
    for cb in captured[0][5:10]:
        cb()
    assert calls == [("subject", "r@conf"), ("invite", "r@conf"),
                     ("config", "r@conf"), ("leave", "r@conf"),
                     ("destroy", "r@conf")]
    assert win.room_list.sel == 0


def test_room_context_menu_member_flags(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_room_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@x"
    win._room_jids = ["r@conf"]
    win.my_nick = {}
    win.room_members = {"r@conf": {"ben": {"affil": "member"}}}
    win._room_subjects = {}
    win.room_list = _List(0)

    xmpp.MainWindow._room_context_menu(win, _ev())
    assert captured[0][3] is False and captured[0][4] is False


def test_room_context_menu_out_of_range_noop(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_room_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win._room_jids = []
    win.room_list = _List(0)
    xmpp.MainWindow._room_context_menu(win, _ev())
    assert captured == []


def test_member_context_menu_delegates_and_routes(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_member_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@x"
    win.active = "r@conf"
    win.rooms = ["r@conf"]
    win.my_nick = {"r@conf": "ben"}
    win.room_members = {"r@conf": {
        "ben": {"affil": "admin", "role": "moderator"},
        "ali": {"affil": "member", "role": "participant"}}}
    win.members_list = _List(7)
    win._member_index_map = {7: "ali"}
    calls = []
    win._start_private_muc_chat = lambda room, nick: calls.append(
        ("priv", room, nick))
    win._kick_member = lambda room, nick: calls.append(("kick", room, nick))
    win._ban_member = lambda room, nick: calls.append(("ban", room, nick))
    win._set_member_affiliation = lambda room, nick, a: calls.append(
        ("affil", room, nick, a))
    win.bot = types.SimpleNamespace(
        set_user_role=lambda r, n, role: calls.append(("role", r, n, role)))

    xmpp.MainWindow._member_context_menu(win, _ev())

    args = captured[0]
    assert args[0] == "ROOT" and args[1] == "ali"
    assert args[2] == "member" and args[3] == "participant"
    assert args[4] is True and args[5] is True
    priv, kick, role, ban, affil = args[6:11]
    priv()
    kick()
    role("visitor")
    ban()
    affil("admin")
    assert calls == [("priv", "r@conf", "ali"), ("kick", "r@conf", "ali"),
                     ("role", "r@conf", "ali", "visitor"),
                     ("ban", "r@conf", "ali"),
                     ("affil", "r@conf", "ali", "admin")]


def test_member_context_menu_rank_flags(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_member_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@x"
    win.active = "r@conf"
    win.rooms = ["r@conf"]
    win.my_nick = {}
    win.room_members = {"r@conf": {
        "ben": {"affil": "member", "role": "participant"},
        "ali": {"affil": "member", "role": "participant"}}}
    win.members_list = _List(7)
    win._member_index_map = {7: "ali"}

    xmpp.MainWindow._member_context_menu(win, _ev())
    assert captured[0][4] is False and captured[0][5] is False


def test_member_context_menu_self_noop(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_member_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.jid = "ben@x"
    win.active = "r@conf"
    win.rooms = ["r@conf"]
    win.my_nick = {"r@conf": "ben"}
    win.members_list = _List(0)
    win._member_index_map = {0: "ben"}
    xmpp.MainWindow._member_context_menu(win, _ev())
    assert captured == []


def test_member_context_menu_not_in_room_noop(monkeypatch):
    captured = []
    monkeypatch.setattr(ui_rooms, "show_member_menu",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.active = None
    win.rooms = []
    xmpp.MainWindow._member_context_menu(win, _ev())
    assert captured == []


def test_room_menu_icerikleri_ui_modulunde():
    assert "Konu Değiştir" in inspect.getsource(ui_rooms.show_room_menu)
    assert "Konu Değiştir" not in inspect.getsource(
        xmpp.MainWindow._room_context_menu)
    assert "Moderatör Yap" in inspect.getsource(ui_rooms.show_member_menu)
    assert "Moderatör Yap" not in inspect.getsource(
        xmpp.MainWindow._member_context_menu)


def test_rooms_modulu_protocol_cagrisi_yapmaz():
    src = inspect.getsource(ui_rooms)
    for token in ("self.bot", ".set_user_role(", ".set_affiliation(",
                  ".leave_muc(", "_db_", "run_coroutine_threadsafe"):
        assert token not in src, f"domain sızıntısı: {token}"


# ── 4B-3B: join / create ────────────────────────────────────────────────────

def test_join_room_dialog_delegates(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_join_room",
        lambda parent, conf, nick, on_discover, on_join:
            captured.append((parent, conf, nick, on_discover, on_join)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@example.com"
    win.my_nick = {}
    win.bot = types.SimpleNamespace(
        discover_rooms=lambda s: captured.append(("discover", s)),
        join_room=lambda r, n: captured.append(("join", r, n)))

    xmpp.MainWindow._join_room_dialog(win)

    parent, conf, nick, on_discover, on_join = captured[0]
    assert (parent, conf, nick) == ("ROOT", "conference.example.com", "ben")
    on_discover("conference.example.com")
    on_join("oda@conf", "ahmet")
    assert captured[1:] == [("discover", "conference.example.com"),
                            ("join", "oda@conf", "ahmet")]
    assert win.my_nick == {"oda@conf": "ahmet"}


def test_create_room_dialog_delegates_to_bot_create(monkeypatch):
    """Yapılandırma artık sabit gecikmeyle değil, sunucunun 201 yanıtıyla
    bot tarafında yapılır (test_room_kind.py)."""
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_create_room",
        lambda parent, conf, nick, on_create:
            captured.append((parent, conf, nick, on_create)))
    win = object.__new__(xmpp.MainWindow)
    win.root = types.SimpleNamespace(
        after=lambda ms, cb: captured.append(("after", ms, cb)))
    win.jid = "ben@example.com"
    win.my_nick = {}
    creates = []
    win.bot = types.SimpleNamespace(
        create_room=lambda r, n, k, name="": creates.append((r, n, k)))

    xmpp.MainWindow._create_room_dialog(win)

    parent, conf, nick, on_create = captured[0]
    assert parent is win.root
    assert (conf, nick) == ("conference.example.com", "ben")
    on_create("yeni@conference.example.com", "ahmet", "normal")
    assert creates == [("yeni@conference.example.com", "ahmet", "normal")]
    assert win.my_nick == {"yeni@conference.example.com": "ahmet"}
    assert len(captured) == 1  # root.after zamanlayıcısı yok


def test_room_dialog_icerikleri_ui_modulunde():
    from ui.dialogs import rooms as ui_dialogs_rooms

    assert "oda@conference.sunucu.tld" in inspect.getsource(
        ui_dialogs_rooms.show_join_room)
    assert "oda@conference.sunucu.tld" not in inspect.getsource(
        xmpp.MainWindow._join_room_dialog)
    assert "yeni-oda" in inspect.getsource(ui_dialogs_rooms.show_create_room)
    assert "yeni-oda" not in inspect.getsource(
        xmpp.MainWindow._create_room_dialog)


def test_room_dialog_modulu_protocol_cagrisi_yapmaz():
    from ui.dialogs import rooms as ui_dialogs_rooms

    src = inspect.getsource(ui_dialogs_rooms)
    for token in ("self.bot", "join_muc", "discover_rooms", "_db_",
                  "run_coroutine_threadsafe"):
        assert token not in src, f"domain sızıntısı: {token}"


# ── 4B-3D: bookmarks ────────────────────────────────────────────────────────

def test_show_bookmarks_delegates_and_routes(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_bookmarks",
        lambda parent, jid, active, rooms, my_nick, bms, on_join, on_save:
            captured.append((parent, jid, active, rooms, my_nick, bms,
                             on_join, on_save)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@example.com"
    win.active = "r@conf"
    win.rooms = ["r@conf"]
    win.my_nick = {"r@conf": "ben"}
    bms = [{"jid": "r@conf", "name": "R", "nick": "", "autojoin": True}]
    joins, saves = [], []
    win.bot = types.SimpleNamespace(
        join_room=lambda r, n: joins.append((r, n)),
        save_bookmarks=lambda b: saves.append(list(b)))

    xmpp.MainWindow._show_bookmarks(win, bms)

    parent, jid, active, rooms, my_nick, passed, on_join, on_save = captured[0]
    assert parent == "ROOT" and jid == "ben@example.com"
    assert (active, rooms, my_nick) == ("r@conf", ["r@conf"], {"r@conf": "ben"})
    assert passed is bms
    assert len(captured) == 1  # tek delegasyon / duplicate yok

    on_join("r@conf", "ahmet")
    assert joins == [("r@conf", "ahmet")]
    assert win.my_nick["r@conf"] == "ahmet"

    on_save(bms)
    assert saves == [bms]


def test_bookmarks_icerikleri_ui_modulunde():
    from ui.dialogs import rooms as ui_dialogs_rooms

    assert "Yer İmleri" in inspect.getsource(ui_dialogs_rooms.show_bookmarks)
    assert "Yer İmleri" not in inspect.getsource(
        xmpp.MainWindow._show_bookmarks)
    assert "Mevcut Odayı Ekle" in inspect.getsource(
        ui_dialogs_rooms.show_bookmarks)
    assert "Mevcut Odayı Ekle" not in inspect.getsource(
        xmpp.MainWindow._show_bookmarks)


# ── 4B-3E: room config ──────────────────────────────────────────────────────

def test_room_config_delegates_and_submits_once(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_room_config",
        lambda parent, room, form, on_submit:
            captured.append((parent, room, form, on_submit)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    calls = []
    win.bot = types.SimpleNamespace(
        set_room_config=lambda r, f: calls.append((r, f)))
    form = {"type": "form"}

    xmpp.MainWindow._show_room_config_form(win, "r@conf", form)

    parent, room, passed, on_submit = captured[0]
    assert (parent, room, passed) == ("ROOT", "r@conf", form)
    on_submit(form)
    assert form["type"] == "submit"
    assert calls == [("r@conf", form)]  # submit exactly once


def test_room_config_icerikleri_ui_modulunde_ve_wrapper_ince():
    from ui.dialogs import rooms as ui_dialogs_rooms

    src = inspect.getsource(ui_dialogs_rooms.show_room_config)
    for token in ("Oda Ayarları", "Kaydet", "İptal", "get_options",
                  "text-private", "list-multi", "text-multi", "boolean"):
        assert token in src, f"eksik UI semantiği: {token}"
    wrapper = inspect.getsource(xmpp.MainWindow._show_room_config_form)
    assert "get_options" not in wrapper
    assert "Kaydet" not in wrapper
    assert len(wrapper.splitlines()) < 12


# ── 4B-3C: room admin ───────────────────────────────────────────────────────

def test_room_admin_delegates_and_capabilities(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_room_admin",
        lambda parent, room, members, subject, contacts, on_subj, on_inv:
            captured.append((parent, room, members, subject, contacts,
                             on_subj, on_inv)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.active = "r@conf"
    win.rooms = ["r@conf"]
    win.room_members = {"r@conf": {
        "ali": {"role": "participant", "affil": "member"}}}
    win._room_subjects = {"r@conf": "eski"}
    win._contacts = {"a@b.c": "Ali"}
    calls = []
    win.bot = types.SimpleNamespace(
        set_room_subject=lambda r, s: calls.append(("subj", r, s)),
        invite_to_room=lambda r, j: calls.append(("inv", r, j)))

    xmpp.MainWindow._room_admin_dialog(win)

    parent, room, members, subject, contacts, on_subj, on_inv = captured[0]
    assert (parent, room, subject) == ("ROOT", "r@conf", "eski")
    assert members == {"ali": {"role": "participant", "affil": "member"}}
    assert contacts == {"a@b.c": "Ali"}

    assert on_subj("yeni") is True
    assert calls == [("subj", "r@conf", "yeni")]
    assert win._room_subjects["r@conf"] == "yeni"

    assert on_inv("a@b.c") is True
    assert calls[-1] == ("inv", "r@conf", "a@b.c")


def test_room_admin_bot_none_returns_false(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_room_admin",
        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.active = "r@conf"
    win.rooms = ["r@conf"]
    win.room_members = {}
    win._room_subjects = {"r@conf": "eski"}
    win._contacts = {}
    win.bot = None

    xmpp.MainWindow._room_admin_dialog(win)
    on_subj, on_inv = captured[0][-2], captured[0][-1]
    assert on_subj("yeni") is False
    assert win._room_subjects["r@conf"] == "eski"  # mutasyon yok
    assert on_inv("a@b.c") is False


def test_room_admin_not_in_room_noop(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(ui_dialogs_rooms, "show_room_admin",
                        lambda *a: captured.append(a))
    win = object.__new__(xmpp.MainWindow)
    win.active = None
    win.rooms = []
    xmpp.MainWindow._room_admin_dialog(win)
    assert captured == []


def test_room_admin_icerikleri_ui_modulunde_ve_wrapper_ince():
    from ui.dialogs import rooms as ui_dialogs_rooms

    src = inspect.getsource(ui_dialogs_rooms.show_room_admin)
    for token in ("Oda Yönetimi", "Konuyu Güncelle", "Davet Gönder",
                  "affil}/{role"):
        assert token in src, f"eksik UI semantiği: {token}"
    wrapper = inspect.getsource(xmpp.MainWindow._room_admin_dialog)
    assert "Konuyu Güncelle" not in wrapper
    assert len(wrapper.splitlines()) < 30


# ── 4B-3F: rooms browser ────────────────────────────────────────────────────

def test_rooms_browser_delegates_and_joins(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_rooms_browser",
        lambda parent, nick, rooms, on_join:
            captured.append((parent, nick, rooms, on_join)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@example.com"
    win.my_nick = {}
    joins = []
    win.bot = types.SimpleNamespace(
        join_room=lambda r, n: joins.append((r, n)))
    rooms = [("a@conf", "Alfa"), ("b@conf", "")]

    xmpp.MainWindow._show_rooms_browser(win, rooms)

    parent, nick, passed, on_join = captured[0]
    assert (parent, nick) == ("ROOT", "ben")
    assert passed is rooms
    on_join("a@conf", "ahmet")
    assert joins == [("a@conf", "ahmet")]
    assert win.my_nick == {"a@conf": "ahmet"}


def test_filter_and_sort_rooms_semantics():
    from ui.dialogs import rooms as ui_dialogs_rooms

    rooms = [("b@conf", "Beta"), ("a@conf", "alfa"), ("c@conf", "")]
    f = ui_dialogs_rooms.filter_and_sort_rooms
    assert [j for j, _ in f(rooms, "", "name_asc")] == ["a@conf", "b@conf", "c@conf"]
    assert [j for j, _ in f(rooms, "", "name_desc")] == ["c@conf", "b@conf", "a@conf"]
    assert [j for j, _ in f(rooms, "", "jid_asc")] == ["a@conf", "b@conf", "c@conf"]
    assert [j for j, _ in f(rooms, "", "jid_desc")] == ["c@conf", "b@conf", "a@conf"]
    assert [j for j, _ in f(rooms, "alf", "name_asc")] == ["a@conf"]
    assert [j for j, _ in f(rooms, "b@", "name_asc")] == ["b@conf"]
    assert f(rooms, "yok", "name_asc") == []


def test_rooms_browser_icerikleri_ui_modulunde_ve_wrapper_ince():
    from ui.dialogs import rooms as ui_dialogs_rooms

    src = inspect.getsource(ui_dialogs_rooms.show_rooms_browser)
    for token in ("Keşfedilen Odalar", "Seçilen Odaya Katıl",
                  "(Eşleşen oda bulunamadı)"):
        assert token in src, f"eksik UI semantiği: {token}"
    wrapper = inspect.getsource(xmpp.MainWindow._show_rooms_browser)
    assert "Keşfedilen Odalar" not in wrapper
    assert len(wrapper.splitlines()) < 12


# ── 4B-5: room search worker/UI sınırı ─────────────────────────────────────

def test_room_search_delegates(monkeypatch):
    from ui.dialogs import rooms as ui_dialogs_rooms

    captured = []
    monkeypatch.setattr(
        ui_dialogs_rooms, "show_room_search",
        lambda parent, nick, domain, servers, on_search, on_join, on_bm, on_disc,
               **kw:
            captured.append((parent, nick, domain, servers, on_search,
                             on_join, on_bm, on_disc, kw)))
    win = object.__new__(xmpp.MainWindow)
    win.root = "ROOT"
    win.jid = "ben@example.com"

    xmpp.MainWindow._search_rooms_dialog(win)

    parent, nick, domain, servers, *cbs, kw = captured[0]
    assert (parent, nick, domain) == ("ROOT", "ben", "example.com")
    # oda servisi keşfedilmediyse eski tahmin (bkz. test_room_join_search B1)
    assert kw == {"own_conf": "conference.example.com"}
    assert servers is xmpp._KNOWN_MUC_SERVERS
    assert all(callable(c) for c in cbs)


def test_room_search_worker_uses_safe_after(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    done, errors, safe = [], [], []
    win._safe_after = lambda ms, fn, *a: safe.append((fn, a))

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return b'{"items": [{"address": "a@conf", "name": "Alfa", "nusers": 5}]}'

    monkeypatch.setattr(xmpp.urllib.request, "urlopen",
                        lambda *a, **k: _Resp())
    started = []

    class _T:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            started.append(self.target)

    monkeypatch.setattr(xmpp.threading, "Thread", _T)

    xmpp.MainWindow._search_rooms_requested(win, "oda", done.append, errors.append)

    assert len(started) == 1 and done == []  # worker'da doğrudan çağrı yok
    started[0]()
    assert done == [] and len(safe) == 1     # yalnız _safe_after'a bırakıldı
    fn, args = safe[0]
    fn(*args)
    assert args[0][0]["address"] == "a@conf"


def test_room_search_worker_error_via_safe_after(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    safe, errors = [], []
    win._safe_after = lambda ms, fn, *a: safe.append((fn, a))

    def _boom(*a, **k):
        raise RuntimeError("net yok")

    monkeypatch.setattr(xmpp.urllib.request, "urlopen", _boom)
    started = []

    class _T:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            started.append(self.target)

    monkeypatch.setattr(xmpp.threading, "Thread", _T)

    xmpp.MainWindow._search_rooms_requested(win, "oda", lambda *a: None,
                                            errors.append)
    started[0]()
    assert errors == [] and len(safe) == 1
    fn, args = safe[0]
    fn(*args)
    assert errors and "net yok" in errors[0]


def test_join_searched_room_and_add_bookmark(monkeypatch):
    win = object.__new__(xmpp.MainWindow)
    win.my_nick = {}
    joins = []
    win.bot = types.SimpleNamespace(join_room=lambda r, n: joins.append((r, n)))

    xmpp.MainWindow._join_searched_room(win, "a@conf", "ahmet")
    assert joins == [("a@conf", "ahmet")]
    assert win.my_nick == {"a@conf": "ahmet"}

    saved, saved_flags = [], []
    win.bot = types.SimpleNamespace(
        get_bookmarks=lambda cb: cb([
            {"jid": "x@conf", "name": "X", "nick": "b", "autojoin": False}]),
        save_bookmarks=lambda b: saved.append(list(b)))

    xmpp.MainWindow._add_room_bookmark(
        win, "a@conf", "Alfa", "ahmet", lambda: saved_flags.append(1))
    assert saved_flags == [1] and len(saved) == 1
    assert any(b["jid"] == "a@conf" for b in saved[0])


def test_room_search_ui_worker_sizintisi_yok_ve_wrapper_ince():
    from ui.dialogs import rooms as ui_dialogs_rooms

    src = inspect.getsource(ui_dialogs_rooms.show_room_search)
    for token in ("urllib", "threading", "self.bot", "urlopen",
                  "run_coroutine_threadsafe"):
        assert token not in src, f"worker/domain sızıntısı: {token}"
    wrapper = inspect.getsource(xmpp.MainWindow._search_rooms_dialog)
    assert len(wrapper.splitlines()) < 12
