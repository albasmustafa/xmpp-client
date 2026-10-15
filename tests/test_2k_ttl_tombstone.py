"""RESOURCE HARDENING 2K: TTL süre-dolma mezar taşı / diriliş-yok.

Kanıt: 2J öncesi davranışta süresi dolmuş vade render'da POP ediliyordu;
alan girişi yaşamaya devam ettiğinden SONRAKİ render aynı mesajı normal
mesaj gibi yeniden çiziyordu (deterministik diriliş). [2K] ile dolmuş vade
pop EDİLMEZ — kalan süresi-dolmuş vadenin kendisi mezar taşıdır:
TTL metadata yok → asla TTL'siz / eski girişler normal çizilir;
metadata + deadline > now → canlı TTL mesajı (kalan süre);
metadata + deadline <= now → alan girişi var oldukça kalıcı gizli.
Mezar taşını yalnız clear yolları temizler; zamanlayıcı satırı söndürse
bile işaret kalır.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2i_ttl_expiry import _patch_clock, _rows_with_mid  # noqa: E402
from test_2j_ttl_instance_uid import _deliver2j, _win2j  # noqa: E402
from test_history_window_bounds import _Cap, _mk_hist  # noqa: E402

import xmpp  # noqa: E402

TTL = 10.0


def _expired_marker(w, jid, uid, clock):
    """Anahtarın mezar taşı olduğunu doğrula: haritada + vadesi geçmiş."""
    assert (jid, uid) in w._ttl_deadlines
    assert w._ttl_deadlines[(jid, uid)] <= clock["now"]


# ── 1) ÇEKİRDEK: ikinci/üçüncü render'da diriliş YOK ─────────────────────────
def test_expired_ttl_never_resurrects_on_second_render(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    _deliver2j(w, "m-2k", "kaybol")          # t=1000 → vade 1010
    uid = w.chats["a@b"][-1][9]
    n_afters = len(w._afters)
    # SINIR: tam vade anında (deadline == now) → dolmuş sayılır
    clock["now"] += 10
    xmpp.MainWindow._load_chat(w, "a@b")
    assert _rows_with_mid(w, "m-2k") == []
    # ikinci ve üçüncü render: hâlâ gizli
    clock["now"] += 0.01
    xmpp.MainWindow._load_chat(w, "a@b")
    clock["now"] += 1
    xmpp.MainWindow._load_chat(w, "a@b")
    assert _rows_with_mid(w, "m-2k") == []
    # sıfır yeni zamanlayıcı; işaret hâlâ "dolmuş" olarak duruyor
    assert len(w._afters) == n_afters
    _expired_marker(w, "a@b", uid, clock)


# ── 2) Zamanlayıcı satırı söndürse bile işaret kalır ─────────────────────────
def test_timer_expired_message_does_not_resurrect(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    _deliver2j(w, "m-timer", "kaybol")       # t=1000 → vade 1010
    uid = w.chats["a@b"][-1][9]
    n_afters = len(w._afters)
    clock["now"] += 10                        # t=1010: vade doldu
    _ms, fn = w._afters[-1]
    fn()                                      # canlı zamanlayıcı satırı söndürür
    assert _rows_with_mid(w, "m-timer") == []
    # tam render: mesaj gizli kalır; yeni TTL yaşam döngüsü BAŞLAMAZ
    xmpp.MainWindow._load_chat(w, "a@b")
    assert _rows_with_mid(w, "m-timer") == []
    assert len(w._afters) == n_afters
    _expired_marker(w, "a@b", uid, clock)


# ── 3) latest/history/rebase/avatar döngülerinde diriliş YOK ─────────────────
def test_expired_message_survives_history_latest_cycles_as_expired(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver2j(w, "m-cycle", "kaybol")       # t=1000 → vade 1010
    uid = w.chats["a@b"][-1][9]
    n_afters = len(w._afters)
    clock["now"] += 11                        # vade doldu
    for _step in range(2):
        xmpp.MainWindow._on_history_latest(w)
        assert _rows_with_mid(w, "m-cycle") == []
        xmpp.MainWindow._on_history_older(w)
        assert _rows_with_mid(w, "m-cycle") == []
    xmpp.MainWindow._on_history_latest(w)
    xmpp.MainWindow._load_chat(w, "a@b")
    xmpp.MainWindow._rebase_latest_window(w, "a@b")
    xmpp.MainWindow._on_avatar_update(w, "a@b")   # avatar reload → aktifse render
    assert _rows_with_mid(w, "m-cycle") == []
    assert len(w._afters) == n_afters
    _expired_marker(w, "a@b", uid, clock)


# ── 4) Aynı mid, ayrık UID: süre-dolmalar bağımsız ───────────────────────────
def test_same_mid_distinct_uid_expiry_independent(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    w._disappearing_ttl["a@b"] = 5
    _deliver2j(w, "X", "bes-sn")             # M1: t=1000, TTL 5 → vade 1005
    uid1 = w.chats["a@b"][-1][9]
    w._disappearing_ttl["a@b"] = 20
    _deliver2j(w, "X", "yirmi-sn")           # M2: t=1000, TTL 20 → vade 1020
    uid2 = w.chats["a@b"][-1][9]
    assert uid1 != uid2
    start = max(0, len(w.chats["a@b"]) - 200)

    clock["now"] += 6                        # t=1006: M1 dolmuş, M2 canlı
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    rows = _rows_with_mid(w, "X")
    assert len(rows) == 1 and rows[0]._body == "yirmi-sn"
    _expired_marker(w, "a@b", uid1, clock)
    assert w._ttl_deadlines[("a@b", uid2)] > clock["now"]

    clock["now"] += 9                        # t=1015: M2 hâlâ canlı
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    rows = _rows_with_mid(w, "X")
    assert len(rows) == 1 and rows[0]._body == "yirmi-sn"   # M1 geri DÖNMEDİ

    clock["now"] += 6                        # t=1021: M2 de doldu
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    assert _rows_with_mid(w, "X") == []
    _expired_marker(w, "a@b", uid1, clock)
    _expired_marker(w, "a@b", uid2, clock)


# ── 5) Çapraz-sohbet süre-dolma bağımsızlığı ─────────────────────────────────
def test_cross_chat_expired_state_independent(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    w._disappearing_ttl = {"a@b": 5, "z@z": 60}
    _deliver2j(w, "X", "A", jid="a@b")       # t=1000 → vade 1005
    uid_a = w.chats["a@b"][-1][9]
    _deliver2j(w, "X", "Z", jid="z@z")       # t=1000 → vade 1060
    uid_z = w.chats["z@z"][-1][9]
    clock["now"] += 6                        # A dolmuş, Z canlı
    w.active = "a@b"
    xmpp.MainWindow._load_chat(w, "a@b")
    assert _rows_with_mid(w, "X") == []
    _expired_marker(w, "a@b", uid_a, clock)
    w.active = "z@z"
    xmpp.MainWindow._load_chat(w, "z@z")
    rows = _rows_with_mid(w, "X")
    assert len(rows) == 1 and rows[0]._body == "Z"
    assert w._ttl_deadlines[("z@z", uid_z)] > clock["now"]   # A'nın durumu
    clock["now"] += 55                        # t=1061: Z de doldu
    xmpp.MainWindow._load_chat(w, "z@z")
    assert _rows_with_mid(w, "X") == []
    _expired_marker(w, "z@z", uid_z, clock)
    _expired_marker(w, "a@b", uid_a, clock)   # A'nın taşı hâlâ yerinde


# ── 6) Clear yaşam döngüsü: mezar taşları da temizlenir ──────────────────────
def test_clear_removes_expired_tombstones_for_jid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    w._disappearing_ttl["z@z"] = TTL          # z1 dolacak
    _deliver2j(w, "a1", jid="a@b")            # t=1000 → vade 1010
    _deliver2j(w, "a2", jid="a@b")
    _deliver2j(w, "z1", jid="z@z")            # t=1000 → vade 1010
    w._disappearing_ttl["z@z"] = 60
    _deliver2j(w, "z2", jid="z@z")            # t=1000 → vade 1060 (canlı)
    assert len(w._ttl_deadlines) == 4
    clock["now"] += 11                        # t=1011: a1/a2/z1 dolmuş; z2 canlı
    w.active = "a@b"
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    w._load_chat = _Cap()
    gen_before = dict(w._mam_gen)
    xmpp.MainWindow._clear_active_history(w)
    assert {k[0] for k in w._ttl_deadlines} == {"z@z"}   # A'nın taşları gitti
    assert len(w._ttl_deadlines) == 2                     # Z'nin ikisi de duruyor
    assert w._mam_gen == {"a@b": gen_before.get("a@b", 0) + 1}
    monkeypatch.setattr(xmpp, "_db_clear_all", _Cap())
    xmpp.MainWindow._clear_all_history(w)
    assert w._ttl_deadlines == {}                         # clear-all: boş


# ── 7) Re-render vadeyi asla sıfırlamaz (dolma sonrası da) ───────────────────
def test_rerender_never_resets_deadline(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver2j(w, "m-live", "gövde")          # t=1000 → vade 1010
    uid = w.chats["a@b"][-1][9]
    deadline = w._ttl_deadlines[("a@b", uid)]
    start = max(0, len(w.chats["a@b"]) - 200)
    clock["now"] += 3                         # canlı: kalan 7 s
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    assert w._ttl_deadlines[("a@b", uid)] == deadline
    clock["now"] += 8                         # t=1011: dolmuş
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    assert w._ttl_deadlines[("a@b", uid)] == deadline        # taşı DEĞİŞMEDİ
    xmpp.MainWindow._load_chat(w, "a@b")
    assert w._ttl_deadlines[("a@b", uid)] == deadline


# ── 8) TTL'siz mesajlar etkilenmez ───────────────────────────────────────────
def test_non_ttl_unaffected(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    _patch_clock(monkeypatch)
    w = _win2j()
    w._disappearing_ttl = {}
    for k in range(20):
        _deliver2j(w, f"n-{k}", f"normal {k}")
    assert w._ttl_deadlines == {}
    for _ in range(3):
        xmpp.MainWindow._load_chat(w, "a@b")
    rendered = {getattr(r, "_mid", "") for r in w._bubble_widgets}
    assert {f"n-{k}" for k in range(20)} <= rendered
    assert w._ttl_deadlines == {}


# ── 9) Eski (UID'siz) girişler güvenli; mezar taşıyla yan yana çökmez ────────
def test_legacy_entry_safe(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    _deliver2j(w, "m-exp", "dolacak")         # t=1000 → vade 1010
    uid = w.chats["a@b"][-1][9]
    clock["now"] += 11                        # dolmuş
    # eski şekiller: 9'luk ve 8'lik girişler yan yana eklenir
    w.chats["a@b"].append(
        ("Ali", "eski dokuz", False, "10:05", "them", "", False, "m-9", ""))
    w.chats["a@b"].append(
        ("Ali", "eski sekiz", False, "10:06", "them", "", False, "m-8"))
    xmpp.MainWindow._load_chat(w, "a@b")
    bodies = {getattr(r, "_body", "") for r in w._bubble_widgets}
    assert {"eski dokuz", "eski sekiz"} <= bodies          # legacy normal
    assert all(r._body != "dolacak" for r in w._bubble_widgets)
    _expired_marker(w, "a@b", uid, clock)


# ── STRES 1: süre dolduktan sonra 100 render — sıfır diriliş/kararsızlık ─────
def test_hundred_renders_after_expiry_stable(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    _deliver2j(w, "m-stress", "kaybol")
    uid = w.chats["a@b"][-1][9]
    n_afters = len(w._afters)
    deadline = dict(w._ttl_deadlines)
    clock["now"] += 11
    for _ in range(100):
        xmpp.MainWindow._render_bounded(w, "a@b", 0)
    assert _rows_with_mid(w, "m-stress") == []
    assert len(w._afters) == n_afters
    assert w._ttl_deadlines == deadline       # bit-aynı kararsızlık
    _expired_marker(w, "a@b", uid, clock)


# ── STRES 2: 1000 TTL girişi — davranış + metadata büyümesi nicemi ───────────
def test_thousand_ttl_entries_metadata_quantified(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j(_mk_hist(10))
    xmpp.MainWindow._load_chat(w, "a@b")
    for k in range(1000):                     # hepsi t=1000'de, TTL 10
        _deliver2j(w, f"t-{k}", f"geçici {k}")
    assert len(w._ttl_deadlines) == 1000      # teslim anında 1000 vade
    n_afters = len(w._afters)
    clock["now"] += 11                        # t=1011: hepsi dolmuş (vade 1010)
    start = max(0, len(w.chats["a@b"]) - 200)
    xmpp.MainWindow._render_bounded(w, "a@b", start)   # pencere yalnız 200 gezer
    assert w._bubble_widgets == []            # 0 görünür TTL satırı
    assert len(w._afters) == n_afters         # sıfır yeni zamanlayıcı
    snapshot = dict(w._ttl_deadlines)
    assert len(snapshot) == 1000              # [2K] mezar taşları KORUNUR
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    assert w._ttl_deadlines == snapshot       # temizlik döngüsü YOK
    assert w._bubble_widgets == []
