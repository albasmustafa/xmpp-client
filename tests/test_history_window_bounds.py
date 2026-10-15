"""RESOURCE HARDENING 2F: sabit geçmiş penceresi (bounded history window).

Görev Q listesindeki kanıtlar:
- I1: her tam render <= K (_HISTORY_WINDOW_SIZE = 200)
- I2: canlı latest modu aktif birim sayısı HER AN <= HARD_CAP (250);
      işlem sırasında enstrümante edilir, transyan 251 yoktur
- I3: history modunda canlı mesaj: 0 _append, pending++
- I4/I5: pasif MAM prepend otomatik render yapmaz; saved viewport indeksleri
      M kadar kaydırılarak birebir korunur
- I6: explicit older MAM sonucu ikinci tık olmadan görünür
- I7: len(self.chats[jid]) aktif widget sayısını belirlemez
- I8: pencereleme domain verisini yazmaz
- Mod türetmesi YOK: latest/history açık durum haritasından gelir
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402
from ui.chat import history as hist_ui  # noqa: E402

K = xmpp.MainWindow._HISTORY_WINDOW_SIZE
CAP = xmpp.MainWindow._HISTORY_LIVE_HARD_CAP


class _Cap:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _W:
    """Minimum widget çifti (config/pack/canvas primitive)."""

    def config(self, **k):
        self.kw = getattr(self, "kw", {})
        self.kw.update(k)

    def pack(self, *a, **k):
        pass

    def pack_forget(self):
        pass

    def delete(self, *a):
        pass

    def create_oval(self, *a, **k):
        pass

    def create_text(self, *a, **k):
        pass

    def create_image(self, *a, **k):
        pass


class _Canvas:
    def __init__(self):
        self.moves = []
        self.idle = 0

    def update_idletasks(self):
        self.idle += 1

    def yview_moveto(self, v):
        self.moves.append(v)

    def yview_scroll(self, u, w):
        pass


class _FakeNav:
    def __init__(self):
        self.text = "↓ En yeni"
        self.packed = True

    def config(self, **k):
        if "text" in k:
            self.text = k["text"]

    def pack(self, **k):
        self.packed = True

    def pack_forget(self):
        self.packed = False


class _FakeBar:
    def __init__(self):
        self.grids = 0
        self.removed = 0
        self.nav_older = _FakeNav()
        self.nav_latest = _FakeNav()

    def grid(self, *a, **k):
        self.grids += 1

    def grid_remove(self):
        self.removed += 1


def _mk_hist(n, prefix="m"):
    return [(f"S{i % 5}", f"gövde {i}", i % 2 == 0, f"10:{i % 60:02d}",
             "them", "", False, f"{prefix}{i}", "") for i in range(n)]


def _mam_msgs(n, prefix):
    return [{"from": "a@b", "body": f"mam {prefix} {i}", "is_me": False,
             "ts": f"2026-09-30T09:{i % 60:02d}:00Z", "mid": f"{prefix}{i}"}
            for i in range(n)]


def _win(history=None, jid="a@b", active=None):
    """_load_chat'ın dokunduğu her noktayı taşıyan Tk'sız pencere çifti."""
    w = object.__new__(xmpp.MainWindow)
    w.active = active if active is not None else jid
    w.jid = "ben@example.com"
    w.rooms = []
    w.bot = types.SimpleNamespace(fetch_mam=lambda *a, **k: None)
    w._unread_counts = {}
    w._refresh_contacts = lambda: None
    w._refresh_typing_indicator = lambda: None
    w._afters = []
    w.root = types.SimpleNamespace(
        title=lambda *a: None,
        after=lambda ms, fn=None: w._afters.append((ms, fn)))
    w.chat_title = _W()
    w._chat_subject = _W()
    w._room_subjects = {}
    w._hdr_avatar = _W()
    w._avatars = {}
    w._photo_refs = []
    w._chat_shell = types.SimpleNamespace(show_chat=lambda: None)
    w.chats = {jid: list(history or [])}
    w._reply_map = {}
    w._render_history_entry = _Cap()
    w._chat_tabs = {}
    w._chat_enc_modes = {}
    w._encryption_mode = types.SimpleNamespace(set=lambda v: None)
    w._update_enc_btn = lambda silent=False: None
    w._composer = types.SimpleNamespace(cancel_reply=lambda: None)
    w._update_pin_bar = lambda: None
    w._last_date_label = "DOLU"
    w._chat_wallpaper = None
    w._clear_chat = _Cap()
    w._scroll_bottom = _Cap()
    w._mam_has_more = {}
    w._mam_oldest = {}
    w._mam_gen = {}
    w._nav_bar = _FakeBar()
    return w


def _store_live(w, jid, i):
    """_store'un bellek tarafını taklit et (SQLite dokunmadan)."""
    w.chats[jid].append((f"S{i}", f"canlı {i}", False, "11:00", "them",
                         "", False, f"canlı{i}", ""))


def _install_units(w, initial=0):
    """Widget birim sayacı: append +1, tam render +girdi, clear → 0.

    I2 enstrümantasyonu: birim sayısı işlem SIRASINDA izlenir.
    """
    st = {"units": initial, "max": initial}

    def _bump(n):
        st["units"] += n
        st["max"] = max(st["max"], st["units"])

    def _append(*a, **k):
        _bump(1)

    def _entry(_e):
        _bump(1)

    def _clear():
        st["units"] = 0

    w._append = _append
    w._render_history_entry = _entry
    w._clear_chat = _clear
    return st


# ── A) Sabitler ──────────────────────────────────────────────────────────────
def test_2f_constants():
    assert xmpp.MainWindow._HISTORY_WINDOW_SIZE == 200
    assert xmpp.MainWindow._HISTORY_LIVE_HARD_CAP == 250


# ── Q1/Q2) Büyük ilk açılış: tam render <= K ────────────────────────────────
def test_initial_chat_1000_renders_at_most_K():
    w = _win(_mk_hist(1000))
    xmpp.MainWindow._load_chat(w, "a@b")
    assert len(w._render_history_entry.calls) == 200
    assert w._history_start["a@b"] == 800
    assert w._history_view_mode["a@b"] == "latest"


def test_initial_chat_5000_renders_at_most_K():
    w = _win(_mk_hist(5000))
    xmpp.MainWindow._load_chat(w, "a@b")
    assert len(w._render_history_entry.calls) == 200
    assert w._history_start["a@b"] == 4800


# ── Q3) A/B geçişleri: her tam render <= K ──────────────────────────────────
def test_repeated_ab_switching_bounded():
    w = _win(_mk_hist(500), jid="a@b")
    w.chats["b@c"] = _mk_hist(300, "b")
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._on_history_older(w)          # a: history modu, start 100
    counts = []
    for _ in range(3):
        before = len(w._render_history_entry.calls)
        xmpp.MainWindow._load_chat(w, "b@c")
        counts.append(len(w._render_history_entry.calls) - before)
        before = len(w._render_history_entry.calls)
        xmpp.MainWindow._load_chat(w, "a@b")
        counts.append(len(w._render_history_entry.calls) - before)
    assert counts and all(0 < c <= 200 for c in counts)
    # A'nın history modu ve viewport'u geçişlerden sızmadan korunur
    assert w._history_view_mode["a@b"] == "history"
    assert w._history_start["a@b"] == 100
    assert w._history_view_mode["b@c"] == "latest"


# ── Q4/Q5) Canlı latest: işlem sırasında enstrümantasyon, transyan 251 yok ──
def test_live_latest_thousands_never_exceeds_cap():
    w = _win(_mk_hist(200))                      # start 0, 200 birim
    xmpp.MainWindow._load_chat(w, "a@b")
    st = _install_units(w, initial=200)
    jid = "a@b"
    peak_logical = len(w.chats[jid]) - w._history_start[jid]
    rebases = 0
    append_calls = 0
    for i in range(1000):
        _store_live(w, jid, i)
        done = []

        def _append_fn():
            done.append(1)
            st["units"] += 1
            st["max"] = max(st["max"], st["units"])

        action = xmpp.MainWindow._deliver_live(w, jid, _append_fn)
        if action == "append":
            append_calls += 1
            assert len(done) == 1
        else:
            assert len(done) == 0                # rebase: ayrı append YOK
            if action == "rebase":
                rebases += 1
        # İşlem sırasında ölçüm (yalnız son durum değil):
        assert st["units"] <= CAP, f"transyan widget taşması: {st['units']}"
        logical = len(w.chats[jid]) - w._history_start[jid]
        peak_logical = max(peak_logical, logical)
        assert logical <= CAP, f"transyan mantıksal taşma: {logical}"
    assert rebases > 0
    assert append_calls + rebases == 1000
    assert st["max"] <= CAP
    assert peak_logical <= CAP
    # Rebase sonrası pencere K ile K+50 arası daralır; asla CAP'ı aşmaz
    assert 200 <= st["units"] <= CAP


# ── Q6) Mod türetmesi YOK: latest açıkça latest kalır ───────────────────────
def test_latest_mode_remains_explicit():
    w = _win(_mk_hist(200))                      # start 0
    xmpp.MainWindow._load_chat(w, "a@b")
    assert w._history_view_mode["a@b"] == "latest"

    def live():
        i = len([e for e in w.chats["a@b"] if e[7].startswith("canlı")])
        _store_live(w, "a@b", i)
        return xmpp.MainWindow._deliver_live(w, "a@b", lambda: None)

    live()                                       # 1 canlı
    assert w._history_view_mode["a@b"] == "latest"
    for _ in range(48):
        live()
    assert w._history_view_mode["a@b"] == "latest"   # 49 canlı
    for _ in range(11):                          # 251'inci birimde rebase
        live()
    assert w._history_view_mode["a@b"] == "latest"   # rebase sonrası da açıkça
    assert w._history_start["a@b"] == 51   # rebase noktası (251 → 260-209)
    assert len(w.chats["a@b"]) == 260            # 200 + 60 canlı (I8)


# ── Q7) History modu + canlı: 0 _append; pending++; viewport birebir ────────
def test_history_mode_live_zero_append_pending_exact_ids():
    w = _win(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._on_history_older(w)          # start 100, history modu
    ids_before = [e[7] for e in w.chats["a@b"][100:300]]
    appends = _Cap()
    w._append = appends
    for i in range(3):
        _store_live(w, "a@b", i)
        action = xmpp.MainWindow._deliver_live(
            w, "a@b", lambda: appends.calls.append(("X",)))
    assert action == "defer"
    assert len(appends.calls) == 0               # I3: 0 render
    assert w._history_pending["a@b"] == 3
    assert w._history_start["a@b"] == 100        # viewport kaymadı
    assert w._history_view_mode["a@b"] == "history"
    assert [e[7] for e in w.chats["a@b"][100:300]] == ids_before
    assert "(3)" in w._nav_bar.nav_latest.text   # gösterge güncellendi


# ── Q8) İnaktif history JID + canlı: pending++, render yok; dönüş eski pencere
def test_inactive_history_jid_live_pending_and_restore():
    w = _win(_mk_hist(500), jid="a@b")
    w.chats["b@c"] = _mk_hist(400, "b")
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._load_chat(w, "b@c")          # b@c: 400 → start 200
    xmpp.MainWindow._on_history_older(w)          # b: history, start 0
    b_ids = [e[7] for e in w.chats["b@c"][0:200]]
    xmpp.MainWindow._load_chat(w, "a@b")         # A'ya dön
    renders = len(w._render_history_entry.calls)
    for i in range(2):
        _store_live(w, "b@c", i)
        xmpp.MainWindow._note_inactive_live(w, "b@c")
    assert w._history_pending["b@c"] == 2
    assert len(w._render_history_entry.calls) == renders   # render YOK
    assert w._history_start["b@c"] == 0
    # Dönüş: eski pencere + yeni mesaj göstergesi
    before = len(w._render_history_entry.calls)
    xmpp.MainWindow._load_chat(w, "b@c")
    assert len(w._render_history_entry.calls) - before == 200
    assert [e[7] for e in w.chats["b@c"][0:200]] == b_ids
    assert w._history_pending["b@c"] == 2        # history modunda korunur
    assert "(2)" in w._nav_bar.nav_latest.text


# ── Q9) İnaktif latest JID: render yok; yeniden açılış en yeni K'ya snap ────
def test_inactive_latest_jid_no_render_reopen_snaps():
    w = _win(_mk_hist(500), jid="a@b")
    w.chats["c@d"] = _mk_hist(500, "c")
    xmpp.MainWindow._load_chat(w, "a@b")
    renders = len(w._render_history_entry.calls)
    _store_live(w, "c@d", 1)
    xmpp.MainWindow._note_inactive_live(w, "c@d")
    assert w._history_pending.get("c@d", 0) == 0   # latest: pending gerekmez
    assert len(w._render_history_entry.calls) == renders
    xmpp.MainWindow._load_chat(w, "c@d")
    assert len(w._render_history_entry.calls) - renders == 200
    assert w._history_start["c@d"] == 301           # 501-200: en yeni K
    assert w._history_view_mode["c@d"] == "latest"


# ── Q10/Q11) Pasif MAM prepend: mantıksal görünür kimlikler birebir korunur ─
def _passive_prepend_ids(mode):
    w = _win(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")          # latest, start 300
    if mode == "history":
        xmpp.MainWindow._on_history_older(w)        # start 100
    s = w._history_start["a@b"]
    ids_before = [e[7] for e in w.chats["a@b"][s:s + 200]]
    renders = len(w._render_history_entry.calls)
    mode_before = w._history_view_mode["a@b"]
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "f")})
    assert len(w._render_history_entry.calls) == renders   # I4: render YOK
    assert w._history_view_mode["a@b"] == mode_before     # mod değişmedi
    assert w._history_start["a@b"] == s + 50              # I5: M kadar kayma
    s2 = w._history_start["a@b"]
    assert [e[7] for e in w.chats["a@b"][s2:s2 + 200]] == ids_before
    return w


def test_passive_mam_prepend_latest_ids_preserved():
    _passive_prepend_ids("latest")


def test_passive_mam_prepend_history_ids_preserved():
    _passive_prepend_ids("history")


# ── Q12) İnaktif JID pasif MAM: durum ayarlanır, render yok ─────────────────
def test_passive_mam_inactive_no_render():
    w = _win(_mk_hist(500), jid="a@b")
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._on_history_older(w)
    w.active = "baska@x"
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "f")})
    assert len(w._render_history_entry.calls) == renders
    assert w._history_start["a@b"] == 150          # 100 + M


# ── Q13) Boş aktif sohbet: intent initial; sonuç <=K latest render ──────────
def test_initial_mam_empty_active_chat():
    w = _win([], jid="a@b")
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    xmpp.MainWindow._load_chat(w, "a@b")
    # D: istek gönderildi ve niyet İSTEĞİN token'ına bağlandı (A kuralı)
    assert fetches == [("a@b", 50, {"token": 0})]
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "initial"}
    assert w._history_view_mode["a@b"] == "latest"
    assert w._history_start["a@b"] == 0
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(250, "f"),
                             "token": 0})
    assert "a@b" not in w._history_mam_intent      # niyet tükendi
    assert w._history_view_mode["a@b"] == "latest"
    assert w._history_start["a@b"] == 50           # 250-200
    assert w._history_pending["a@b"] == 0
    assert len(w._render_history_entry.calls) == 200
    assert w._scroll_bottom.calls                  # en alta


# ── Q14) Kullanıcı kaçmışsa initial MAM sonucu: inaktif render YOK ──────────
def test_initial_mam_result_inactive_no_render():
    w = _win([], jid="a@b")
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    xmpp.MainWindow._load_chat(w, "a@b")
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "initial"}
    w.chats["b@c"] = _mk_hist(50, "b")
    xmpp.MainWindow._load_chat(w, "b@c")           # kullanıcı ayrıldı
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(250, "f"),
                             "token": 0})
    assert len(w._render_history_entry.calls) == renders   # render YOK
    assert w._history_view_mode["a@b"] == "latest"
    assert w._history_start["a@b"] == 50           # yalnız durum güncellendi


# ── Q15) start=0 + has_more + Daha eski: tam bir MAM isteği; intent older ───
def test_older_at_start_zero_requests_mam_once():
    w = _win(_mk_hist(200))                        # 200 → start 0
    xmpp.MainWindow._load_chat(w, "a@b")
    assert w._history_start["a@b"] == 0
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    w._mam_oldest["a@b"] = "m0"
    w._mam_has_more["a@b"] = True
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._on_history_older(w)
    assert fetches == [("a@b", 50, {"before": "m0", "token": 0})]
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "older"}
    # Henüz render YOK: sayfa ancak sonuç gelince görünür
    assert len(w._render_history_entry.calls) == renders


# ── Q16 / I6) Explicit older sonucu: ikinci tık olmadan görünür ─────────────
def test_explicit_older_result_reveals_immediately():
    w = _win(_mk_hist(200))
    xmpp.MainWindow._load_chat(w, "a@b")
    w.chat_canvas = _Canvas()
    w.bot = types.SimpleNamespace(fetch_mam=lambda j, n, **kw: None)
    w._mam_oldest["a@b"] = "m0"
    w._mam_has_more["a@b"] = True
    xmpp.MainWindow._on_history_older(w)             # istek + intent
    fresh = _mam_msgs(50, "f")
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": fresh, "token": 0})
    assert w._history_view_mode["a@b"] == "history"
    assert w._history_start["a@b"] == max(0, 50 - 200)   # J formülü
    rendered = w._render_history_entry.calls[-200:]
    assert len(rendered) == 200                              # <=K
    # İlk 50 girdi = kullanıcının istediği yeni sayfa (anında görünür)
    assert [c[0][0][7] for c in rendered[:50]] == [f"f{i}" for i in range(50)]
    assert "a@b" not in w._history_mam_intent
    # Deterministik üst kaydırma
    assert w.chat_canvas.moves[-1] == 0.0
    assert any(ms == 60 for ms, _fn in w._afters)


# ── Q17) Sonuç gelene kadar sohbet değiştiyse: yönlendirme/render YOK ───────
def test_explicit_older_result_inactive_no_nav():
    w = _win(_mk_hist(200), jid="a@b")
    xmpp.MainWindow._load_chat(w, "a@b")
    w.chats["b@c"] = _mk_hist(50, "b")
    w.bot = types.SimpleNamespace(fetch_mam=lambda j, n, **kw: None)
    w._mam_oldest["a@b"] = "m0"
    w._mam_has_more["a@b"] = True
    xmpp.MainWindow._on_history_older(w)             # intent older + istek
    xmpp.MainWindow._load_chat(w, "b@c")            # kullanıcı ayrıldı
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "f"),
                             "token": 0})
    assert len(w._render_history_entry.calls) == renders   # render YOK
    assert "a@b" not in w._history_mam_intent              # niyet temiz
    assert w._history_start["a@b"] == 50                   # viewport korundu
    assert w._history_view_mode["a@b"] == "latest"         # mod değişmedi


# ── Q18) History'den Latest/New-messages: sınırlı K re-render; pending sıfır
def test_latest_click_from_history_bounded():
    w = _win(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._on_history_older(w)             # history, start 100
    for i in range(3):
        _store_live(w, "a@b", i)
        assert xmpp.MainWindow._deliver_live(w, "a@b", lambda: None) == "defer"
    assert w._history_pending["a@b"] == 3
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._on_history_latest(w)
    assert w._history_view_mode["a@b"] == "latest"
    assert w._history_pending["a@b"] == 0
    n = len(w._render_history_entry.calls) - renders
    assert n == 200                                 # bilinçli K re-render
    got = [c[0][0][7] for c in w._render_history_entry.calls[-200:]]
    assert got[:197] == [f"m{i}" for i in range(303, 500)]
    assert got[197:] == ["canlı0", "canlı1", "canlı2"]
    assert w._scroll_bottom.calls


# ── Q19) Her render dilimi <= K; clamp güvenli ───────────────────────────────
def test_every_render_slice_bounded():
    w = _win(_mk_hist(1000))
    for start in (0, 1, 199, 200, 500, 800, 999, 1000, 5000, -10):
        n = xmpp.MainWindow._render_bounded(w, "a@b", start)
        assert 0 <= n <= 200
    window, s, e = xmpp.MainWindow._history_window_slice(w, "a@b", 900)
    assert len(window) == 100 and (s, e) == (900, 1000)
    assert window == w.chats["a@b"][900:1000]


# ── Q20) Geçmiş temizliği: 2F durumu sıfırlanır ─────────────────────────────
def test_clear_history_resets_state(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_clear_all", _Cap())
    w = _win(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._on_history_older(w)
    _store_live(w, "a@b", 1)
    xmpp.MainWindow._deliver_live(w, "a@b", lambda: None)   # pending 1
    assert w._history_pending["a@b"] == 1
    # [2F-Blocker] Bayat MAM üstverisi de temizlenmeli
    w._mam_has_more["a@b"] = True
    w._mam_oldest["a@b"] = "m0"
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True
    for d in (w._history_start, w._history_view_mode,
              w._history_pending, w._history_mam_intent):
        assert "a@b" not in d
    assert "a@b" not in w._mam_has_more
    assert "a@b" not in w._mam_oldest

    w2 = _win(_mk_hist(500))
    xmpp.MainWindow._load_chat(w2, "a@b")
    w2.chats["b@c"] = _mk_hist(10, "b")
    xmpp.MainWindow._load_chat(w2, "b@c")
    w2._mam_has_more = {"a@b": True, "b@c": True}
    w2._mam_oldest = {"a@b": "m0", "b@c": "b0"}
    w2._load_chat = _Cap()   # temizlik sonrası yeniden yüklemeyi yalıt
    assert xmpp.MainWindow._clear_all_history(w2) is True
    assert w2.chats == {}
    for d in (w2._history_start, w2._history_view_mode,
              w2._history_pending, w2._history_mam_intent,
              w2._mam_has_more, w2._mam_oldest):
        assert d == {}


def test_reset_history_ui_state_direct():
    w = _win(_mk_hist(10))
    xmpp.MainWindow._load_chat(w, "a@b")
    w._history_mam_intent["a@b"] = {"token": 0, "intent": "older"}
    w._mam_has_more["a@b"] = True
    w._mam_oldest["a@b"] = "m0"
    xmpp.MainWindow._reset_history_ui_state(w, "a@b")
    for d in (w._history_start, w._history_view_mode,
              w._history_pending, w._history_mam_intent,
              w._mam_has_more, w._mam_oldest):
        assert "a@b" not in d


# ── Q21) Pencere sınırında tarih ayırıcı sıfırlaması ────────────────────────
def test_date_separator_reset_at_window_boundary():
    w = _win(_mk_hist(500))
    sep_labels = []
    w._maybe_add_date_separator = lambda ts=None: sep_labels.append(
        w._last_date_label)
    appends = []

    def _entry(e):
        w._maybe_add_date_separator(e[3])
        appends.append(e[3])

    w._render_history_entry = _entry
    w._last_date_label = "ESKİ-SOHBET"
    xmpp.MainWindow._render_bounded(w, "a@b", 100)
    assert len(sep_labels) == 200
    assert sep_labels[0] == ""            # sınırda önceki sohbet tarihi görülmedi
    assert appends[0] == "10:40"          # ilk pencere girdisinin gerçek zamanı


# ── Q22) Gezinme domain verisini yazmaz (I8) ─────────────────────────────────
def test_navigation_leaves_domain_unchanged():
    w = _win(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    snapshot = [tuple(e) for e in w.chats["a@b"]]
    xmpp.MainWindow._on_history_older(w)
    xmpp.MainWindow._on_history_latest(w)
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._note_inactive_live(w, "a@b")
    assert w.chats["a@b"] == snapshot
    assert len(w.chats["a@b"]) == 500     # I7: toplam uzunluk widget belirlemez


# ── Q23) 2F dışı canlı davranış değişmedi (append sözleşmesi aynen) ─────────
def test_live_behavior_backcompat_append():
    w = object.__new__(xmpp.MainWindow)   # 2F durumu hiç kurulmamış çift
    w.chats = {"a@b": [("A", "eski", False, "10:00", "them", "", False,
                        "m1", "")]}
    calls = []
    action = xmpp.MainWindow._deliver_live(
        w, "a@b", lambda: calls.append(("gövde", "them")))
    assert action == "append"
    assert calls == [("gövde", "them")]
    assert w._history_view_mode.get("a@b", "latest") == "latest"  # örtük latest


# ── Bayat MAM sonucu: YENİ isteğin niyetine asla dokunamaz (Blocker 1) ──────
def test_stale_result_cannot_consume_newer_intent():
    w = _win(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    w._mam_gen = {"a@b": 1}                        # clear sonrası dünya
    w._history_mam_intent["a@b"] = {"token": 1, "intent": "older"}
    renders = len(w._render_history_entry.calls)
    start_before = w._history_start["a@b"]
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "f"),
                             "token": 0})          # bayat token'lı sonuç
    # Sahiplik sag: bayat sonuç niyeti NE tüketti NE kaydırdı NE render etti
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "older"}
    assert w._history_start["a@b"] == start_before
    assert len(w._render_history_entry.calls) == renders


# ── O) Sabit gezinme kontrolleri: metin/görünürlük sözleşmesi ───────────────
def test_nav_presentation_pending_text():
    bar = _FakeBar()
    hist_ui.update_history_nav(bar, show_older=True, show_latest=True,
                               pending=3)
    assert bar.nav_latest.text == "↓ Yeni mesajlar (3)"
    assert bar.nav_latest.packed and bar.nav_older.packed

    hist_ui.update_history_nav(bar, show_older=True, show_latest=True,
                               pending=0)
    assert bar.nav_latest.text == "↓ En yeni"


def test_nav_presentation_visibility():
    bar = _FakeBar()
    # latest modu: yalnız Older (start>0)
    hist_ui.update_history_nav(bar, show_older=True, show_latest=False,
                               pending=0)
    assert bar.nav_older.packed and not bar.nav_latest.packed
    # hiçbir şey: çubuk gizli
    grids, removes = bar.grids, bar.removed
    hist_ui.update_history_nav(bar, show_older=False, show_latest=False,
                               pending=0)
    assert bar.removed == removes + 1 and bar.grids == grids
    # older ve latest paketlenmez
    assert not bar.nav_older.packed and not bar.nav_latest.packed


def test_nav_bar_widget_count_constant(monkeypatch):
    """Mesaj sayısından bağımsız: gezinme her zaman tek çubuk/iki kontrol."""
    w = _win(_mk_hist(1000))
    seen_bars = []

    def _build(parent, th, on_older, on_latest):
        bar = _FakeBar()
        seen_bars.append(bar)
        return bar

    monkeypatch.setattr(xmpp._history_ui, "build_history_nav", _build)
    w._nav_bar = None                       # kurulumu zorla
    w._chat_shell = types.SimpleNamespace(
        show_chat=lambda: None, _chat_area=object())
    for _ in range(3):
        xmpp.MainWindow._load_chat(w, "a@b")
        xmpp.MainWindow._on_history_older(w)
        _store_live(w, "a@b", 1)
        xmpp.MainWindow._deliver_live(w, "a@b", lambda: None)
        xmpp.MainWindow._on_history_latest(w)
    assert len(seen_bars) == 1              # tek örnek; mesaj başına widget yok
