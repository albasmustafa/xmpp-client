"""RESOURCE HARDENING 2F — BLOCKER FIX regresyon testleri.

Blocker 1: MAM niyet sahipliği — niyet isteğin kendi token'ına bağlıdır;
aynı JID'de outstanding UI isteği varken ikinci istek gönderilmez; bayat
(token uyuşmazlığı olan) sonuç yeni isteğin sahipliğini ASLA tüketemez.
Blocker 2: _open_chat_tab sınırlı render — en yeni K; O(toplam) render yok.
MAM dizilimleri PRODUCTION yollarıyla kurulur (_load_chat, _on_history_older,
_handle("mam_results"), clear yolları).
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _Cap, _mam_msgs, _mk_hist, _win  # noqa: E402

import xmpp  # noqa: E402

K = xmpp.MainWindow._HISTORY_WINDOW_SIZE


def _fetch_recorder():
    calls = []
    return calls, types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: calls.append((j, n, kw)))


# ══ Blocker 1 — MAM niyet sahipliği ══════════════════════════════════════════
def test_duplicate_older_click_refused_then_real_result_renders():
    """Gereklilik 1+3: outstanding Older varken ikinci tık İSTEK GÖNDERMEZ;
    sahiplik bozulmaz; tek gerçek sonuç explicit-older davranışını yürütür."""
    w = _win(_mk_hist(200))                    # 200 → start 0
    xmpp.MainWindow._load_chat(w, "a@b")
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    w._mam_oldest["a@b"] = "m0"
    w._mam_has_more["a@b"] = True
    xmpp.MainWindow._on_history_older(w)       # 1. tık → istek
    assert len(fetches) == 1
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "older"}
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._on_history_older(w)       # 2. tık → REDDEDİLİR
    assert len(fetches) == 1                   # ikinci istek YOK (E kuralı)
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "older"}
    assert len(w._render_history_entry.calls) == renders
    # Tek outstanding isteğin gerçek sonuçları explicit-older yürütür (I6)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "f"),
                             "token": 0})
    assert "a@b" not in w._history_mam_intent
    assert w._history_view_mode["a@b"] == "history"
    got = [c[0][0][7] for c in w._render_history_entry.calls[-200:]]
    assert len(got) == 200
    assert got[:50] == [f"f{i}" for i in range(50)]   # yeni sayfa anında görünür


def test_stale_result_cannot_consume_newer_older_intent(monkeypatch):
    """Gereklilik 1: eski (bayat token'lı) Older sonucu; clear + yeniden
    initial + YENİ Older isteğinden SONRA gelse bile yeni niyete dokunamaz;
    gerçek sonuç explicit-older'ı yürütür."""
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    w = _win([])                               # boş sohbet
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    xmpp.MainWindow._load_chat(w, "a@b")       # initial req (token 0)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(100, "m"),
                             "token": 0})
    assert w._mam_has_more["a@b"] is True      # 100 >= 50 → devam var
    # Kullanıcı Older ister (token 0) — sonucu yolda kalır (yavaş sunucu)
    xmpp.MainWindow._on_history_older(w)
    assert fetches[-1] == ("a@b", 50, {"before": "m0", "token": 0})
    # Temizlik: generation yükselir, üstveri + niyet silinir; boş geçmişle
    # clear, kendisi yeni initial isteği açar (token 1)
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert w._mam_gen["a@b"] == 1
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "initial"}
    assert len(fetches) == 3
    assert fetches[2] == ("a@b", 50, {"token": 1})
    # Yeni initial tamamlanır; kullanıcı yeniden Older ister (token 1)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(250, "y"),
                             "token": 1})
    assert w._history_start["a@b"] == 50
    assert len(w.chats["a@b"]) == 250
    xmpp.MainWindow._on_history_older(w)       # start 50 → yerel kaydırma
    xmpp.MainWindow._on_history_older(w)       # start 0 → MAM Older (token 1)
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "older"}
    renders = len(w._render_history_entry.calls)
    # BAYAT Older sonucu (token 0, clear öncesi istek) ŞİMDİ gelse:
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "eski"),
                             "token": 0})
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "older"}
    assert len(w._render_history_entry.calls) == renders     # render YOK
    assert len(w.chats["a@b"]) == 250                        # merge YOK
    # Gerçek sonuç (token 1) → explicit older: yeni sayfa görünür, <=K
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "g"),
                             "token": 1})
    assert "a@b" not in w._history_mam_intent
    assert w._history_view_mode["a@b"] == "history"
    got = [c[0][0][7] for c in w._render_history_entry.calls[-200:]]
    assert got[:50] == [f"g{i}" for i in range(50)]
    assert len(got) == 200


def test_stale_result_cannot_consume_newer_initial_intent(monkeypatch):
    """Gereklilik 2+5: clear + yeniden açılış yeni initial niyeti açar;
    önceki isteğin bayat sonucu onu tüketemez; gerçek sonuç <=K render eder."""
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    w = _win([])
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    xmpp.MainWindow._load_chat(w, "a@b")       # initial req (token 0)
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "initial"}
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "initial"}
    # Bayat sonuç (token 0) guard'a takılır; yeni niyet sağ kalır
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(250, "eski"),
                             "token": 0})
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "initial"}
    assert len(w._render_history_entry.calls) == renders
    # Gerçek sonuç (token 1) → <=K latest render
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(250, "y"),
                             "token": 1})
    assert "a@b" not in w._history_mam_intent
    assert len(w._render_history_entry.calls) - renders == 200
    assert w._history_start["a@b"] == 50


def test_clear_while_older_outstanding_invalidates_navigation(monkeypatch):
    """Gereklilik 4: Older isteği uçarken temizlik yapılırsa bayat sonuç
    temizlenmiş/yeniden açılmış sohbeti yönlendiremez."""
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    w = _win(_mk_hist(200))
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    xmpp.MainWindow._load_chat(w, "a@b")
    w._mam_oldest["a@b"] = "m0"
    w._mam_has_more["a@b"] = True
    xmpp.MainWindow._on_history_older(w)       # Older req (token 0) uçuyor
    assert xmpp.MainWindow._clear_active_history(w) is True
    # Eski sahiplik geçersiz; clear'ın açtığı YENİ initial (token 1) sahibi
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "initial"}
    assert "a@b" not in w._mam_has_more and "a@b" not in w._mam_oldest
    renders = len(w._render_history_entry.calls)
    # Bayat Older sonucu gelir:
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "eski"),
                             "token": 0})
    assert len(w._render_history_entry.calls) == renders   # render YOK
    assert w.chats.get("a@b", []) == []                    # merge YOK
    assert w._history_view_mode["a@b"] == "latest"         # latest boş kalır
    assert w._history_start["a@b"] == 0
    assert w._history_pending["a@b"] == 0
    # Bayat sonuç temizlenen sohbeti yönlendiremedi; clear'ın kendi açtığı
    # YENİ initial niyeti (token 1) sağ ve onun sonucunu bekliyor:
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "initial"}
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(120, "y"),
                             "token": 1})
    assert "a@b" not in w._history_mam_intent
    assert len(w._render_history_entry.calls) - renders == 120


def test_zero_result_clears_matching_intent():
    """Gereklilik 6: boş sonuç — eşleşen niyet güvenle temizlenir,
    has_more doğru güncellenir."""
    w = _win([])
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    xmpp.MainWindow._load_chat(w, "a@b")       # initial (token 0)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": [], "token": 0})
    assert "a@b" not in w._history_mam_intent
    assert w._mam_has_more["a@b"] is False
    # Older varyantı:
    w._mam_has_more["a@b"] = True
    w._mam_oldest["a@b"] = "m0"
    xmpp.MainWindow._on_history_older(w)
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "older"}
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": [], "token": 0})
    assert "a@b" not in w._history_mam_intent
    assert w._mam_has_more["a@b"] is False
    assert len(w._render_history_entry.calls) == renders


def test_switch_away_while_request_outstanding_no_render():
    """Gereklilik 7: istek uçarken sohbet değişirse sonuç yalnız
    durum/günceller; inaktif UI render'ı olmaz (F kuralı)."""
    w = _win([], jid="a@b")
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    xmpp.MainWindow._load_chat(w, "a@b")       # initial (token 0) uçtu
    w.chats["b@c"] = _mk_hist(30, "b")
    xmpp.MainWindow._load_chat(w, "b@c")       # kullanıcı ayrıldı
    renders = len(w._render_history_entry.calls)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(120, "m"),
                             "token": 0})
    assert len(w._render_history_entry.calls) == renders   # render YOK
    assert w._history_view_mode["a@b"] == "latest"
    assert w._history_start["a@b"] == 0         # 120-120? → max(0, 120-200)
    assert "a@b" not in w._history_mam_intent
    # Geri dönüldüğünde sınırlı pencere görür
    xmpp.MainWindow._load_chat(w, "a@b")
    assert len(w._render_history_entry.calls) - renders == 120


# ══ Blocker 1 — MAM üstveri temizliği ════════════════════════════════════════
def test_slash_clear_helper_cleans_mam_metadata():
    """/clear yolunun kullandığı yardımcı bayat MAM üstverisini de siler."""
    w = _win(_mk_hist(300))
    xmpp.MainWindow._load_chat(w, "a@b")
    w._history_mam_intent["a@b"] = {"token": 0, "intent": "older"}
    w._mam_has_more["a@b"] = True
    w._mam_oldest["a@b"] = "m0"
    xmpp.MainWindow._reset_history_ui_state(w, "a@b")
    for d in (w._history_start, w._history_view_mode,
              w._history_pending, w._history_mam_intent,
              w._mam_has_more, w._mam_oldest):
        assert "a@b" not in d


def test_clear_all_cleans_mam_metadata(monkeypatch):
    """Gereklilik (üstveri): clear-all tüm JID'lerde MAM gezinme üstverisini
    temizler."""
    monkeypatch.setattr(xmpp, "_db_clear_all", _Cap())
    w = _win(_mk_hist(10))
    w.chats["b@c"] = _mk_hist(5, "b")
    w._history_mam_intent = {"a@b": {"token": 0, "intent": "older"},
                             "b@c": {"token": 0, "intent": "initial"}}
    w._mam_has_more = {"a@b": True, "b@c": True}
    w._mam_oldest = {"a@b": "m0", "b@c": "b0"}
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_all_history(w) is True
    assert w._history_mam_intent == {}
    assert w._mam_has_more == {}
    assert w._mam_oldest == {}


# ══ Blocker 2 — _open_chat_tab sınırlı render ════════════════════════════════
class _TabToplevel:
    last = None

    def __init__(self, master=None, **k):
        self.protocols = {}
        type(self).last = self

    def title(self, t):
        pass

    def configure(self, **k):
        pass

    def geometry(self, g):
        pass

    def protocol(self, name, fn):
        self.protocols[name] = fn

    def destroy(self):
        pass


class _TabCanvas:
    def __init__(self, master=None, **k):
        self.moves = 0

    def pack(self, **k):
        pass

    def create_window(self, *a, **k):
        return 1

    def bind(self, *a, **k):
        pass

    def yview_scroll(self, *a):
        pass

    def yview_moveto(self, v):
        self.moves += 1

    def bbox(self, *a):
        return None

    def configure(self, **k):
        pass


class _TabFrame:
    def __init__(self, master=None, **k):
        self.master = master
        _TabFrame.made.append(self)

    def pack(self, **k):
        pass

    def bind(self, *a, **k):
        pass

    def columnconfigure(self, *a, **k):
        pass


class _TabLabel:
    def __init__(self, master=None, **k):
        self.k = k

    def pack(self, **k):
        pass

    def grid(self, **k):
        pass

    def bind(self, *a, **k):
        pass


class _TabEntry:
    def __init__(self, master=None, **k):
        pass

    def grid(self, **k):
        pass

    def bind(self, *a, **k):
        pass

    def focus_set(self):
        pass


class _TabStringVar:
    def __init__(self, **k):
        pass

    def get(self):
        return ""

    def set(self, v):
        pass


def _open_tab_and_count(w, target):
    """Üretim _open_chat_tab yolunu sahte tk ile sürücüye alır; mesaj
    satırlarını msg_f'nin doğrudan çocuklarından sayar."""
    _TabFrame.made = []
    fake_tk = types.SimpleNamespace(
        Toplevel=_TabToplevel, Canvas=_TabCanvas, Frame=_TabFrame,
        Label=_TabLabel, StringVar=_TabStringVar)
    old_tk, old_ttk = xmpp.tk, xmpp.ttk
    xmpp.tk = fake_tk
    xmpp.ttk = types.SimpleNamespace(Entry=_TabEntry)
    try:
        xmpp.MainWindow._open_chat_tab(w, target)
    finally:
        xmpp.tk, xmpp.ttk = old_tk, old_ttk
    top = _TabToplevel.last
    msg_f = _TabFrame.made[0]                  # canvas'a bağlı ilk frame
    rows = [f for f in _TabFrame.made[1:] if f.master is msg_f]
    return top, rows


def test_open_chat_tab_bounded_latest_K():
    """Gereklilik (sekme): N ∈ {50, 200, 201, 1000, 5000} → render <= K;
    domain + birincil pencere durumu değişmez; tekrar açılış sınırlı kalır."""
    for n in (50, 200, 201, 1000, 5000):
        w = _win(_mk_hist(n))
        xmpp.MainWindow._load_chat(w, "a@b")   # birincil görünüm kur
        primary_state = (dict(w._history_start), dict(w._history_view_mode),
                         dict(w._history_pending))
        snapshot = [tuple(e) for e in w.chats["a@b"]]
        top, rows = _open_tab_and_count(w, "a@b")
        expect = min(n, K)
        assert len(rows) == expect, f"N={n}: {len(rows)} != {expect}"
        assert top is not None and "a@b" in w._chat_tabs
        # Domain + birincil pencere durumu değişmedi (paylaşılan sahiplik yok)
        assert [tuple(e) for e in w.chats["a@b"]] == snapshot
        assert (dict(w._history_start), dict(w._history_view_mode),
                dict(w._history_pending)) == primary_state
    # Tekrarlı açılış sınırlı kalır
    w = _win(_mk_hist(5000))
    xmpp.MainWindow._load_chat(w, "a@b")
    for _ in range(3):
        _top, rows = _open_tab_and_count(w, "a@b")
        assert len(rows) == K


def test_open_chat_tab_latest_not_earliest(monkeypatch):
    """N>K: sekme EN YENİ K'yi çizer (en eski değil) — etiket metinleriyle."""
    made_labels = []

    class _L(_TabLabel):
        def __init__(self, master=None, **k):
            super().__init__(master, **k)
            made_labels.append(k.get("text"))

    fake_tk = types.SimpleNamespace(
        Toplevel=_TabToplevel, Canvas=_TabCanvas, Frame=_TabFrame,
        Label=_L, StringVar=_TabStringVar)
    monkeypatch.setattr(xmpp, "tk", fake_tk)
    monkeypatch.setattr(xmpp, "ttk", types.SimpleNamespace(Entry=_TabEntry))
    _TabFrame.made = []
    w = _win(_mk_hist(1000))
    xmpp.MainWindow._open_chat_tab(w, "a@b")
    texts = [t for t in made_labels if t]
    assert "gövde 999" in texts                # son mesaj
    assert "gövde 0" not in texts              # en eski DEĞİL
    assert "gövde 800" in texts                # K penceresinin ilk üyesi
    assert "gövde 799" not in texts

# ══ B1 — /clear generation bump ══════════════════════════════════════════════
def test_slash_clear_bumps_gen_while_older_outstanding(monkeypatch):
    """B1: /clear yeniden yükleme ÖNCESİ generation'ı yükseltir.

    Dizi (tamamı üretim yolları): Older isteği (token N) outstanding iken
    GERÇEK _handle_bot_command("/clear") çalıştırılır → yeni Initial token
    N+1 alır → bayat Older sonucu (token N) yeni Initial sahipliğini
    tüketemez → eşleşen Initial sonucu normal işlenir.
    """
    # 1) Aktif sohbet yüklü
    # [Phase6A-F1] /clear artık canonical _db_clear_chat'i de çağırır;
    # bu test üretim DB'sine dokunmamak için silgiyi kaydediciye bağlar.
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    w = _win(_mk_hist(200))                    # start 0, latest
    xmpp.MainWindow._load_chat(w, "a@b")
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    # 2) Pagination durumu + Older isteği
    w._mam_oldest["a@b"] = "m0"
    w._mam_has_more["a@b"] = True
    xmpp.MainWindow._on_history_older(w)
    # 3) Older isteği token N=0 ile uçtu ve outstanding
    assert fetches == [("a@b", 50, {"before": "m0", "token": 0})]
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "older"}
    # 4) GERÇEK /clear komutu
    xmpp.MainWindow._handle_bot_command(w, "/clear")
    # 5) Yeni Initial token N+1 ile açıldı; sahiplik {"token": N+1, "initial"}
    assert fetches[1] == ("a@b", 50, {"token": 1})
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "initial"}
    assert w._mam_gen["a@b"] == 1
    assert w.chats.get("a@b", []) == []        # /clear bellek-side temizliği
    renders = len(w._render_history_entry.calls)
    # 6) ESKİ Older sonucu (token N=0) gelir:
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "eski"),
                             "token": 0})
    # bayat: niyet tüketilmedi, merge/render yok, üstveri ve gen değişmedi
    assert w._history_mam_intent["a@b"] == {"token": 1, "intent": "initial"}
    assert w.chats.get("a@b", []) == []
    assert len(w._render_history_entry.calls) == renders
    assert "a@b" not in w._mam_has_more and "a@b" not in w._mam_oldest
    assert w._mam_gen["a@b"] == 1
    # 7) Eşleşen Initial sonucu (token N+1):
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(250, "yeni"),
                             "token": 1})
    assert "a@b" not in w._history_mam_intent   # niyet normal tüketildi
    assert len(w.chats["a@b"]) == 250           # doğru sonuç merge edildi
    got = [c[0][0][7] for c in w._render_history_entry.calls[-200:]]
    assert len(got) == 200                      # render <= K
    assert got == [f"yeni{i}" for i in range(50, 250)]   # en yeni K penceresi
    # clear öncesi sayfa geri gelmez
    assert all(not g.startswith(("m", "eski")) for g in got)
    assert w._history_start["a@b"] == 50
    assert w._history_view_mode["a@b"] == "latest"
