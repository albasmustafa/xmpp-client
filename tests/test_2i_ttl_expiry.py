"""RESOURCE HARDENING 2I: TTL/kaybolan mesaj görsel vade doğruluğu.

Kanıtlar:
- Tek etkili vade (mid → expires_at): re-render TTL'i asla sıfırlamaz.
- History modunda defer edilen mesajın vadesi teslim anında alınır; süre
  dolmuşsa latest'e dönüşte GÖRÜNMEZ, dolmadıysa yalnız KALAN süre yaşar.
- Vadesi dolmuş mesaj _load_chat ile diriltilmez.
- Bayat zamanlayıcı yalnız kendi satırını söndürür; yeni widget'a dokunmaz.
- Farklı TTL'ler bağımsız voter; normal mesajlar etkilenmez.
- Clear yolları vade üstverisini temizler; MAM generation semantiği aynıdır.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _Cap, _mk_hist, _win  # noqa: E402

import xmpp  # noqa: E402

TTL = 10.0


class _Row:
    def __init__(self, mid, body):
        self._mid = mid
        self._body = body
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


def _patch_clock(monkeypatch, start=1000.0):
    clock = {"now": start}
    monkeypatch.setattr(
        xmpp, "time",
        types.SimpleNamespace(monotonic=lambda: clock["now"]))
    return clock


def _win2i(hist=(), ttl=TTL):
    """Gerçek render/schedule yollarını süren Tk'sız pencere çifti."""
    w = _win(hist, jid="a@b")
    w.active = "a@b"
    w._bubble_widgets = []
    w._msg_ids = {}
    w._notify_enabled = False
    w._sound_enabled = False
    w._show_toast = lambda *a, **k: None
    w._send_read_receipts = False
    w._disappearing_ttl = {"a@b": ttl}
    w._ttl_deadlines = {}
    w._store = lambda t, body, **k: w.chats.setdefault(t, []).append(
        ("Ali", body, False, "11:00", "them", "", False, k.get("mid", ""), ""))
    w.bot = types.SimpleNamespace(
        send_marker=lambda *a, **k: None, fetch_mam=lambda *a, **k: None)

    def _fake_clear():
        w._bubble_widgets.clear()

    w._clear_chat = _fake_clear

    def _fake_append(body, tag, sender="", is_me=False, time_str=None,
                     oob="", encrypted=False, mid="", reply_to=None,
                     local_path=""):
        r = _Row(mid, body)
        w._bubble_widgets.append(r)
        return r

    w._append = _fake_append
    w._render_history_entry = lambda e: xmpp.MainWindow._render_history_entry(w, e)
    return w


def _deliver(w, mid, body="selam"):
    xmpp.MainWindow._handle(w, "msg", {"from": "a@b", "nick": "Ali",
                                       "body": body, "mid": mid})


def _rows_with_mid(w, mid):
    return [r for r in w._bubble_widgets
            if getattr(r, "_mid", "") == mid]


# ── 1) Latest modda vade: görünürlük + süre sonunda söndürme ────────────────
def test_ttl_message_expires_in_latest(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i()
    _deliver(w, "m-ttl")                      # TTL mesaj
    normal = w._append("normal", "them", mid="m-normal")  # TTL'siz
    assert len(_rows_with_mid(w, "m-ttl")) == 1
    # zamanlanmış süre TTL'dir (10 s → 10000 ms)
    assert w._afters[-1][0] == 10_000
    # süre dolmadan görünür
    clock["now"] += 5
    assert len(_rows_with_mid(w, "m-ttl")) == 1
    # süre doldu → zamanlayıcı satırı söndürür; normal satır dokunulmaz
    clock["now"] += 5
    ms, fn = w._afters[-1]
    assert ms == 10_000
    fn()
    assert _rows_with_mid(w, "m-ttl") == []
    assert normal.destroyed is False
    assert normal in w._bubble_widgets


# ── 2) ÇEKİRDEK: history defer + süre dolumu + latest'e dönüş ────────────────
def test_ttl_deferred_in_history_expires_before_return(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._on_history_older(w)      # history modu (start 100)
    afters_before = len(w._afters)
    _deliver(w, "m-defer")                    # defer: render YOK
    assert _rows_with_mid(w, "m-defer") == []          # pencereye dokunulmadı
    assert w._history_pending["a@b"] == 1
    assert ("a@b", "m-defer") in w._ttl_deadlines   # vade teslim anında
    # vade dolana kadar bekle
    clock["now"] += TTL + 1
    # latest'e dönüş: dolmuş mesaj GÖRÜNMEZ, taze TTL de BAŞLAMAZ
    xmpp.MainWindow._on_history_latest(w)
    assert _rows_with_mid(w, "m-defer") == []
    # dolmuş mesaj için taze TTL BAŞLAMADI: zamanlayıcı sayısı değişmedi
    assert len(w._afters) == afters_before


# ── 3) Vade dolmadan dönüş: yalnız KALAN süre ────────────────────────────────
def test_ttl_deferred_return_before_deadline_uses_remaining_time(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._on_history_older(w)
    _deliver(w, "m-part")                     # defer; vade = t0+10
    clock["now"] += 7                          # 7 s geçti
    xmpp.MainWindow._on_history_latest(w)
    rows = _rows_with_mid(w, "m-part")
    assert len(rows) == 1                      # görünür
    # kalan süre ~3 s (10 s değil): en son zamanlama ≈ 3000 ms
    scheduled = [ms for ms, _fn in w._afters if ms <= 3_500]
    assert scheduled and abs(scheduled[-1] - 3_000) <= 50
    # kalan süre sonunda söner
    clock["now"] += 3
    ms, fn = w._afters[-1]
    fn()
    assert rows[0].destroyed


# ── 4) Re-render vadeyi sıfırlamaz ───────────────────────────────────────────
def test_ttl_rerender_does_not_reset_deadline(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver(w, "m-live")                      # latest canlı teslim
    deadline = w._ttl_deadlines[("a@b", "m-live")]
    clock["now"] += 4                          # TTL'in %40'ı geçti
    start = max(0, len(w.chats["a@b"]) - 200)  # en yeni K penceresi
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    rows = _rows_with_mid(w, "m-live")
    assert len(rows) == 1                      # tek satır, dirilmedi
    assert abs(w._ttl_deadlines[("a@b", "m-live")] - deadline) < 1e-9  # vade aynı
    # yeni zamanlama KALAN süre (~6 s), tam TTL değil
    assert w._afters[-1][0] == 6_000
    # toplam görünür ömür orijinal vadeyi aşamaz
    clock["now"] += 6
    w._afters[-1][1]()
    assert rows[0].destroyed


# ── 5) Süresi dolmuş mesaj _load_chat ile diriltilmez ────────────────────────
def test_expired_ttl_not_resurrected_by_load_chat(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver(w, "m-gone")
    clock["now"] += TTL + 1                    # vade doldu
    assert len(w.chats["a@b"]) == 501          # domain korunur
    xmpp.MainWindow._load_chat(w, "a@b")       # tam yeniden yükleme
    assert _rows_with_mid(w, "m-gone") == []   # görsel diriliş YOK


# ── 6) Bayat zamanlayıcı yeni widget'ı söndüremez ────────────────────────────
def test_stale_timer_does_not_destroy_new_widget(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver(w, "m-stale")
    old_row = _rows_with_mid(w, "m-stale")[0]
    old_cb = w._afters[-1][1]
    # re-render: aynı mid için YENİ satır + YENİ zamanlayıcı
    clock["now"] += 2
    start = max(0, len(w.chats["a@b"]) - 200)  # en yeni K penceresi
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    new_row = _rows_with_mid(w, "m-stale")[-1]
    assert new_row is not old_row
    old_cb()                                    # BAYAT callback ateşlenir
    assert old_row.destroyed                    # yalnız KENDİ satırı söner
    assert new_row.destroyed is False           # geçerli widget sağ
    assert new_row in w._bubble_widgets


# ── 7) Farklı TTL'ler bağımsız voter ─────────────────────────────────────────
def test_multiple_ttl_deadlines_independent(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver(w, "m-short")                      # TTL 10
    w._disappearing_ttl["a@b"] = 3
    _deliver(w, "m-fast")                       # TTL 3
    assert (w._ttl_deadlines[("a@b", "m-short")]
            - w._ttl_deadlines[("a@b", "m-fast")] == 7)
    clock["now"] += 3                           # kısa olanın vadesi doldu
    start = max(0, len(w.chats["a@b"]) - 200)
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    assert _rows_with_mid(w, "m-fast") == []    # fast söndü
    assert len(_rows_with_mid(w, "m-short")) == 1  # short yaşıyor
    short_scheduled = [ms for ms, _ in w._afters if ms == 7_000]
    assert short_scheduled                      # kalan ~7 s zamanlandı
    clock["now"] += 7
    short_row = _rows_with_mid(w, "m-short")[0]
    for _ms, fn in list(w._afters):
        fn()
    assert short_row.destroyed
    assert short_row not in w._bubble_widgets


# ── 8) Clear yaşam döngüsü: vade üstverisi temizlenir ────────────────────────
def test_clear_removes_ttl_presentation_metadata(monkeypatch):
    w = _win2i(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver(w, "m-clear")
    assert ("a@b", "m-clear") in w._ttl_deadlines
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_clear_all", _Cap())
    gen_before = dict(w._mam_gen)
    # clear active
    w._load_chat = _Cap()
    xmpp.MainWindow._clear_active_history(w)
    assert ("a@b", "m-clear") not in w._ttl_deadlines
    assert w._mam_gen == {"a@b": gen_before.get("a@b", 0) + 1}  # MAM aynı
    # /clear yolu da aynı yardımcıyla temizler
    w2 = _win2i(_mk_hist(10))
    xmpp.MainWindow._load_chat(w2, "a@b")
    _deliver(w2, "m2")
    assert ("a@b", "m2") in w2._ttl_deadlines
    xmpp.MainWindow._forget_ttl_deadlines(w2, "a@b")
    assert ("a@b", "m2") not in w2._ttl_deadlines
    # clear all
    w3 = _win2i(_mk_hist(10))
    xmpp.MainWindow._load_chat(w3, "a@b")
    _deliver(w3, "m-all")
    w3._load_chat = _Cap()
    xmpp.MainWindow._clear_all_history(w3)
    assert w3._ttl_deadlines == {}


# ── 8b) B1: çapraz-sohbet aynı-mid vade bulaşması YOK (composite anahtar) ────
def test_b1_cross_chat_same_mid_independent_deadlines(monkeypatch):
    """B1 regresyonu: aynı mid iki sohbette bağımsız vade taşır.

    mid gönderici-kontrollüdür (origin-id → stanza-id → stanza["id"]) ve
    sohbetler arası benzersiz değildir; iki sohbet de aynı "X" kimliğini
    üretebilir. A TTL=5, Z TTL=60: +6 sn'de A gizli ama Z GÖRÜNÜR kalmalı;
    +61 sn'de Z de gizlenmelidir. (mid-only anahtar Z'nin mesajını 1006'da
    gizlerdi — vade bulaşması.)
    """
    clock = _patch_clock(monkeypatch)
    w = _win2i()
    w.active = "a@b"
    w._disappearing_ttl = {"a@b": 5, "z@z": 60}
    xmpp.MainWindow._handle(w, "msg", {"from": "a@b", "nick": "Ali",
                                       "body": "selam A", "mid": "X"})
    w.active = "z@z"
    xmpp.MainWindow._handle(w, "msg", {"from": "z@z", "nick": "Zeynep",
                                       "body": "selam Z", "mid": "X"})
    # bağımsız vadeler: fark tam 55 s (teslim anında; A'nın vadeleri ileride
    # dolmuş render'da pop edilir — o yüzden burada doğrulanır)
    assert abs(w._ttl_deadlines[("a@b", "X")]
               - w._ttl_deadlines[("z@z", "X")] + 55) < 1e-9
    clock["now"] += 6
    # A: vade (1005) doldu → yeniden yüklemede gizli
    w.active = "a@b"
    xmpp.MainWindow._load_chat(w, "a@b")
    assert _rows_with_mid(w, "X") == []
    # Z: vade (1060) canlı → görünür; zamanlama kalan ~54 s
    w.active = "z@z"
    xmpp.MainWindow._load_chat(w, "z@z")
    rows_z = _rows_with_mid(w, "X")
    assert len(rows_z) == 1
    assert w._afters[-1][0] == 54_000
    # +61 s: Z vadesi de dolar → gizli; [2K] dolmuş vade MEZAR TAŞI olarak
    # haritada kalır (diriliş yok — clear yolları dışında temizlenmez)
    clock["now"] += 55
    xmpp.MainWindow._render_bounded(w, "z@z", 0)
    assert _rows_with_mid(w, "X") == []
    assert ("z@z", "X") in w._ttl_deadlines
    assert w._ttl_deadlines[("z@z", "X")] <= clock["now"]


# ── 9) Normal mesajlar etkilenmez ────────────────────────────────────────────
def test_non_ttl_messages_unchanged(monkeypatch):
    clock = _patch_clock(monkeypatch)
    w = _win2i(_mk_hist(300))
    xmpp.MainWindow._load_chat(w, "a@b")
    # Faz 1: TTL KAPALI iken 200 normal mesaj → vade KAYDEDİLMEZ
    w._disappearing_ttl = {}
    for k in range(200):
        _deliver(w, f"n-{k}", f"normal {k}")
    assert w._ttl_deadlines == {}               # normal mesaj vadesiz
    # Faz 2: TTL açıkken 20 geçici mesaj
    w._disappearing_ttl = {"a@b": TTL}
    for k in range(20):
        _deliver(w, f"t-{k}", f"geçici {k}")
    assert len(w._ttl_deadlines) == 20
    clock["now"] += TTL + 1                     # yalnız TTL vadeleri dolar
    start = max(0, len(w.chats["a@b"]) - 200)
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    # yalnız dolmuş TTL satırları kayboldu; normal akış sağlam; domain tam
    assert all(not _rows_with_mid(w, f"t-{k}") for k in range(20))
    assert len(w.chats["a@b"]) == 300 + 220
    rendered_mids = {getattr(r, "_mid", "") for r in w._bubble_widgets}
    assert sum(1 for m in rendered_mids if m.startswith("n-")) >= 180
    assert not any(m.startswith("t-") for m in rendered_mids)
