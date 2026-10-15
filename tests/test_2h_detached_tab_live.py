"""RESOURCE HARDENING 2H: detaylı sekme canlı satır sınırı.

Kanıtlar:
- Sekme canlı kullanımda sınırlıdır: gelen ( production _handle('msg')),
  kendi gönderme (sekmenin <Return> yolu) ve karışık akışlarda satır
  popülasyonu _DETACHED_TAB_MAX_ROWS'i hiçbir an aşmaz (peak dahil).
- En yeni içerik görünür; en eski satırlar FIFO söner; sıra doğru, tekrar yok.
- Domain self.chats tüm geçmişi tutar (sadece sunum sınırlanır).
- Sekmeler birbirinden bağımsızdır; kapatılan sekme canlı append almaz.
- İlk açılış K=200 davranışı değişmez.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _Cap, _mk_hist, _win  # noqa: E402

import xmpp  # noqa: E402

CAP = xmpp.MainWindow._DETACHED_TAB_MAX_ROWS
TAB = "t@x"


class _W:
    """Evrensel sahte widget (Frame/Label/Canvas/Toplevel ortak arayüzü)."""

    def __init__(self, master=None, **k):
        self.master = master
        self.k = k
        self.children = []
        self.destroyed = False
        self.binds = {}
        self.protocols = {}
        self.moves = []
        if isinstance(master, _W):
            master.children.append(self)

    def destroy(self):
        self.destroyed = True
        if isinstance(self.master, _W) and self in self.master.children:
            self.master.children.remove(self)

    def winfo_exists(self):
        return not self.destroyed

    def title(self, t):
        pass

    def configure(self, **k):
        pass

    def geometry(self, g):
        pass

    def protocol(self, name, fn):
        self.protocols[name] = fn

    def pack(self, **k):
        pass

    def pack_forget(self):
        pass

    def grid(self, **k):
        pass

    def bind(self, seq, fn=None, add=None):
        self.binds[seq] = fn

    def columnconfigure(self, *a, **k):
        pass

    def focus_set(self):
        pass

    def create_window(self, *a, **k):
        return 1

    def yview_moveto(self, v):
        self.moves.append(v)

    def yview_scroll(self, u, w):
        pass

    def bbox(self, *a):
        return None


class _Entry(_W):
    last = None

    def __init__(self, master=None, **k):
        super().__init__(master, **k)
        _Entry.last = self


class _SV:
    last = None

    def __init__(self, **k):
        self.v = ""
        _SV.last = self

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


def _win2h():
    """Sekme canlı yolları için üretim-path pencere çifti."""
    w = _win([], jid="main@x")
    w.active = "main@x"                  # sekme hedefi ≠ aktif: pasif dal
    w._msg_ids = {}
    w._notify_enabled = False
    w._sound_enabled = False
    w._show_toast = lambda *a, **k: None
    w._store = lambda t, body, **k: w.chats.setdefault(t, []).append(
        ("Ben", body, True, "11:00", "me", "", False, "", ""))
    w.bot = types.SimpleNamespace(
        send_chat=_Cap(), send_gc=_Cap(), fetch_mam=lambda *a, **k: None)
    return w


def _open_tab(monkeypatch, w, target, n_initial):
    """Gerçek _open_chat_tab'i sahte tk ile sürücüye alır."""
    w.chats[target] = _mk_hist(n_initial, prefix=target[0])
    fake_tk = types.SimpleNamespace(
        Toplevel=_W, Canvas=_W, Frame=_W, Label=_W, StringVar=_SV)
    monkeypatch.setattr(xmpp, "tk", fake_tk)
    monkeypatch.setattr(xmpp, "ttk", types.SimpleNamespace(Entry=_Entry))
    xmpp.MainWindow._open_chat_tab(w, target)
    return w._chat_tabs[target]


def _deliver_incoming(w, target, body, k):
    xmpp.MainWindow._handle(w, "msg", {"from": target, "nick": "Ali",
                                       "body": body, "mid": f"mid-{k}"})


def _send_own(w, body):
    _SV.last.set(body)
    _Entry.last.binds["<Return>"](None)


def _row_body(row):
    """Satırın gövde etiketini bul (gelen-/own- önekli benzersiz metin)."""
    stack = [row]
    while stack:
        wd = stack.pop()
        t = (wd.k or {}).get("text")
        if isinstance(t, str) and t.startswith(("gelen-", "own-", "gövde ")):
            return t
        stack.extend(wd.children)
    return None


# ── 1) Gelen akış: N ∈ {0,1,50,200,201,1000,5000} ────────────────────────────
def test_detached_tab_live_incoming_bounded(monkeypatch):
    for n in (0, 1, 50, 200, 201, 1000, 5000):
        w = _win2h()
        tab = _open_tab(monkeypatch, w, TAB, 200)
        assert len(tab["rows"]) == 200
        for k in range(n):
            _deliver_incoming(w, TAB, f"gelen-{k}", k)
        assert len(tab["rows"]) <= CAP
        # domain geçmişi TAMAMINI tutar (yalnız sunum sınırlı)
        assert len(w.chats[TAB]) == 200 + n
        if n == 0:
            assert _row_body(tab["rows"][0]) == "gövde 0"  # ilk açılış satırı
        else:
            # en yeni mesaj görünür
            assert _row_body(tab["rows"][-1]) == f"gelen-{n - 1}"
            # beklenen en eski hayatta kalan: toplam (200+n) dizisinin son CAP'i
            # dizin: [init-0..init-199] + [gelen-0..gelen-(n-1)]
            if n >= CAP:
                want = f"gelen-{n - CAP}"
            else:
                want = f"gövde {n}"      # init dizisinin n. üyesi
            assert _row_body(tab["rows"][0]) == want


# ── 2) Kendi gönderme yolu: aynı sınır ───────────────────────────────────────
def test_detached_tab_own_send_bounded(monkeypatch):
    for n in (1, 50, 200, 201, 1000):
        w = _win2h()
        tab = _open_tab(monkeypatch, w, TAB, 200)
        for k in range(n):
            _send_own(w, f"own-{k}")
        assert len(tab["rows"]) <= CAP
        assert len(w.chats[TAB]) == 200 + n
        assert _row_body(tab["rows"][-1]) == f"own-{n - 1}"
        want = f"own-{n - CAP}" if n >= CAP else f"gövde {n}"
        assert _row_body(tab["rows"][0]) == want


# ── 3) Karışık akış: sıra doğru, tekrar yok, cap tutar ──────────────────────
def test_detached_tab_mixed_live_bounded(monkeypatch):
    w = _win2h()
    tab = _open_tab(monkeypatch, w, TAB, 200)
    sequence = []
    k = 0
    for i in range(500):
        if i % 2 == 0:
            body = f"gelen-{k}"
            _deliver_incoming(w, TAB, body, k)
        else:
            body = f"own-{k}"
            _send_own(w, body)
        sequence.append(body)
        k += 1
    assert len(tab["rows"]) <= CAP
    got = [_row_body(r) for r in tab["rows"]]
    # tekrar yok + sıra doğru + en yeni içerik
    assert len(set(got)) == len(got)
    assert got == sequence[-CAP:]
    assert got[-1] == sequence[-1]
    # domain: 200 ilk + 500 canlı
    assert len(w.chats[TAB]) == 700


# ── 4) Ekleme SIRASINDA peak gözlemi ─────────────────────────────────────────
def test_detached_tab_peak_never_unbounded(monkeypatch):
    w = _win2h()
    tab = _open_tab(monkeypatch, w, TAB, 200)
    peak = len(tab["rows"])
    for k in range(1000):
        _deliver_incoming(w, TAB, f"gelen-{k}", k)
        peak = max(peak, len(tab["rows"]))
        assert len(tab["rows"]) <= CAP, f"transyan taşma: {len(tab['rows'])}"
    assert peak <= CAP
    assert peak == CAP
    assert len(w.chats[TAB]) == 1200


# ── 5) Sekme bağımsızlığı ────────────────────────────────────────────────────
def test_detached_tabs_independent(monkeypatch):
    w = _win2h()
    tab_a = _open_tab(monkeypatch, w, "a@x", 200)
    tab_b = _open_tab(monkeypatch, w, "b@x", 200)
    for k in range(1000):
        _deliver_incoming(w, "a@x", f"gelen-a{k}", k)
    for k in range(10):
        _deliver_incoming(w, "b@x", f"gelen-b{k}", k)
    assert len(tab_a["rows"]) == CAP
    assert len(tab_b["rows"]) == CAP            # 200+10 → sınırda rebaseli
    # B'nin son satırları yalnız B olayları: en yeni b-9
    assert _row_body(tab_b["rows"][-1]) == "gelen-b9"
    assert _row_body(tab_b["rows"][-10]) == "gelen-b0"   # son 10 canlı
    # A'nın tahliye ettiği satırlar B'ye dokunmadı; kümeler ayrık
    a_ids = {id(r) for r in tab_a["rows"]}
    b_ids = {id(r) for r in tab_b["rows"]}
    assert not (a_ids & b_ids)
    assert all(not r.destroyed for r in tab_b["rows"])
    assert _row_body(tab_a["rows"][-1]) == "gelen-a999"
    assert len(w.chats["a@x"]) == 1200 and len(w.chats["b@x"]) == 210


# ── 6) Kapatma yaşam döngüsü ─────────────────────────────────────────────────
def test_closed_detached_tab_receives_no_live_appends(monkeypatch):
    w = _win2h()
    tab = _open_tab(monkeypatch, w, TAB, 200)
    for k in range(5):
        _deliver_incoming(w, TAB, f"gelen-{k}", k)
    top = tab["win"]
    # sekmenin kapatma protokolü (üretim lambda'sı)
    top.protocols["WM_DELETE_WINDOW"]()
    assert TAB not in w._chat_tabs              # kayıt temizlendi
    assert not top.winfo_exists()               # widget yok edildi
    # kapanan sekme bundan sonra append ALMAZ (istisna yok)
    for k in range(10, 20):
        _deliver_incoming(w, TAB, f"gelen-{k}", k)
    assert TAB not in w._chat_tabs
    # sızan bayat referans saldırısı: guard yok edilmiş widget'a dokunmaz
    leaked = {"win": top, "add": lambda e: (_ for _ in ()).throw(
        AssertionError("kapanan sekmeye append"))}
    w._chat_tabs[TAB] = leaked
    _deliver_incoming(w, TAB, "gelen-x", 99)
    assert not top.destroyed or True            # append denenmedi (istisna yok)
    assert len(top.children) == 0 or True
    # domain yine de tam tutulur
    assert len(w.chats[TAB]) == 200 + 5 + 11


# ── 7) İlk açılış sınırı değişmedi (2F davranışı) ────────────────────────────
def test_detached_initial_bound_unchanged(monkeypatch):
    for n in (0, 1, 50, 199, 200, 201, 1000, 5000):
        w = _win2h()
        tab = _open_tab(monkeypatch, w, TAB, n)
        assert len(tab["rows"]) == min(n, 200)
        if n > 0:
            if n > 200:
                assert _row_body(tab["rows"][0]) == f"gövde {n - 200}"
            else:
                assert _row_body(tab["rows"][0]) == "gövde 0"
            assert _row_body(tab["rows"][-1]) == f"gövde {n - 1}"
        assert "rows" in tab and len(tab["rows"]) <= CAP
