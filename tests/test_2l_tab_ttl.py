"""RESOURCE HARDENING 2L: detaylı sekme TTL paritesi.

Kanıt: sekme yolu TTL durumunu yok sayıyordu — ana pencerede 2K mezar
taşıyla kalıcı gizlenen mesaj, açık sekmede sonsuza kadar görünür kalıyor,
kapat/aç döngüsünde ise yeniden çiziliyordu (paralel diriliş). [2L] ile
sekme satırı ekleme yolu AYNI yetkili haritayı okur:

- TTL metadata yok → mevcut TTL'siz davranış;
- deadline > now → satır çizilir, yalnız KALAN ömür kadar tab-lokal kaldırma
  zamanlanır (_remove_tab_row: FIFO + widget, başka hiçbir şeye dokunmaz);
- deadline ≤ now → satır ÇİZİLMEZ, zamanlayıcı kurulmaz, mezar taşı
  KALDIRILMAZ (2K yetkili).

Kimlik 2J/2K ile aynıdır: (jid, örnek-uid); eski girişler mid fallback'i.
TTL asla sekme açılışında yeniden başlamaz; harita sekme mantığından
salt-okunurdur.

Zamanlayıcı sıralama notu: aktif-sohbet tesliminde sekme timer'ı (tab
feed) ana pencere schedule'ından ÖNCE kurulur → afters[0] tab, afters[1]
main'dir (testler bu deterministik sıraya dayanır).
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2h_detached_tab_live import _SV, _W, _Entry, _row_body  # noqa: E402
from test_2i_ttl_expiry import _patch_clock, _Row  # noqa: E402
from test_history_window_bounds import _Cap, _mk_hist, _win  # noqa: E402

import xmpp  # noqa: E402

CAP = xmpp.MainWindow._DETACHED_TAB_MAX_ROWS
TAB = "t@x"
TTL = 10.0


def _win2l(ttl=TTL):
    """[2L] Gerçek _store (uid'li) + sekme canlı yolları için pencere çifti.

    _db_store_msg monkeypatch gerektirir; _append Tk'sız _Row üretir.
    """
    w = _win([], jid="main@x")
    w.active = "main@x"
    w._msg_ids = {}
    w._notify_enabled = False
    w._sound_enabled = False
    w._show_toast = lambda *a, **k: None
    w._send_read_receipts = False
    w._send_typing_notif = False
    w._typing_send_id = None
    w._disappearing_ttl = {TAB: ttl}
    w._ttl_deadlines = {}
    w._reply_map = {}
    w._bubble_widgets = []
    w._encryption_mode = types.SimpleNamespace(get=lambda: "none",
                                               set=lambda v: None)
    w._composer = types.SimpleNamespace(
        get_text=lambda: "own-ttl", clear_text=lambda: None,
        consume_reply=lambda: None, cancel_reply=lambda: None)

    def _fake_append(body, tag, sender="", is_me=False, time_str=None,
                     oob="", encrypted=False, mid="", reply_to=None,
                     local_path=""):
        r = _Row(mid, body)
        w._bubble_widgets.append(r)
        return r

    w._append = _fake_append

    def _fake_clear():
        w._bubble_widgets.clear()

    w._clear_chat = _fake_clear
    w.bot = types.SimpleNamespace(
        send_chat=_Cap(), send_gc=_Cap(),
        send_marker=lambda *a, **k: None, fetch_mam=lambda *a, **k: None)
    return w


def _open_tab(monkeypatch, w, target=TAB):
    """Gerçek _open_chat_tab'i sahte tk ile sürücüye alır."""
    fake_tk = types.SimpleNamespace(
        Toplevel=_W, Canvas=_W, Frame=_W, Label=_W, StringVar=_SV)
    monkeypatch.setattr(xmpp, "tk", fake_tk)
    monkeypatch.setattr(xmpp, "ttk", types.SimpleNamespace(Entry=_Entry))
    xmpp.MainWindow._open_chat_tab(w, target)
    return w._chat_tabs[target]


def _deliver2l(w, mid, body, jid=TAB):
    """Aktif-sohbet teslimi: gerçek _store (uid'li) + TTL kaydı + tab feed."""
    w.active = jid
    xmpp.MainWindow._handle(w, "msg", {"from": jid, "nick": "Ali",
                                       "body": body, "mid": mid})


def _tab_ms_timers(w):
    return [ms for ms, _fn in w._afters]


def _close_tab(w, tab):
    tab["win"].protocols["WM_DELETE_WINDOW"]()


# ── 1) Sekme satırı MUTLAK vadede söner; mezar taşı yerinde kalır ────────────
def test_tab_row_expires_at_absolute_deadline(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    tab = _open_tab(monkeypatch, w)
    _deliver2l(w, "m-1", "gelen-1")          # t=1000 → vade 1010 (aktif dal)
    uid = w.chats[TAB][-1][9]
    assert ("t@x", uid) in w._ttl_deadlines  # kayıt sekmeden önce (task C)
    assert len(tab["rows"]) == 1             # sekme görünür
    assert len(w._bubble_widgets) == 1       # ana pencere canlı satırı
    assert abs(_tab_ms_timers(w)[0] - 10_000) <= 1   # [tab, main] → ilk tab
    clock["now"] += 10                       # vade doldu (sınır: == now)
    w._afters[0][1]()                        # tab-lokal kaldırma
    assert tab["rows"] == []
    assert tab["frame"].children == []       # widget ağacı da temiz
    # 2K mezar taşı: haritada, dolmuş ve ASLA sıfırlanmamış
    assert ("t@x", uid) in w._ttl_deadlines
    assert w._ttl_deadlines[("t@x", uid)] == 1010.0 <= clock["now"]


# ── 2) Süre dolduktan sonra sekme aç/kapa: diriliş YOK ───────────────────────
def test_tab_reopen_after_expiry_no_resurrection(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    _deliver2l(w, "m-exp", "gelen-exp")      # t=1000 → vade 1010
    uid = w.chats[TAB][-1][9]
    n_afters = len(w._afters)
    clock["now"] += 11                        # dolmuş (mezar taşı)
    for _round in range(3):                   # tekrarlı reopen
        tab = _open_tab(monkeypatch, w)
        assert tab["rows"] == []              # dolmuş giriş ÇİZİLMEZ
        assert len(w._afters) == n_afters     # taze zamanlayıcı YOK
        _close_tab(w, tab)
    assert w._ttl_deadlines[("t@x", uid)] <= clock["now"]   # taş dokunulmadı


# ── 3) Vade dolmadan açılış: YALNIZ kalan ömür ───────────────────────────────
def test_tab_reopen_before_expiry_uses_remaining_time(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    _deliver2l(w, "m-rem", "gelen-rem")      # t=1000 → vade 1010
    clock["now"] += 7                         # t=1007: kalan 3 s
    for _round in range(2):
        tab = _open_tab(monkeypatch, w)
        assert len(tab["rows"]) == 1
        ms = _tab_ms_timers(w)[-1]            # en son açılan sekmenin timer'ı
        assert abs(ms - 3_000) <= 1           # kalan ömür
        assert abs(ms - 10_000) > 1           # tam TTL YENİDEN BAŞLAMADI
        _close_tab(w, tab)


# ── 4) Canlı gelen teslim: kayıt sekmeden önce, süre doğru ───────────────────
def test_tab_live_incoming_ttl(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    tab = _open_tab(monkeypatch, w)
    n_afters = len(w._afters)
    _deliver2l(w, "m-live", "gelen-live")    # aktif dal: kayıt → tab feed
    uid = w.chats[TAB][-1][9]
    assert ("t@x", uid) in w._ttl_deadlines  # harita tab add'dan önce dolu
    assert len(tab["rows"]) == 1
    assert abs(_tab_ms_timers(w)[0] - 10_000) <= 1
    clock["now"] += 11
    w._afters[0][1]()                         # yalnız tab zamanlayıcısı
    assert tab["rows"] == []
    # deliver 1 tab + 1 ana zamanlayıcı kurdu (sıra: [tab, main])
    assert len(w._afters) == n_afters + 2


# ── 5) Ana composer kendi gönderimi: sekme kimlik + süre alır ────────────────
def test_tab_main_composer_own_send_ttl(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    tab = _open_tab(monkeypatch, w)
    w.active = TAB                             # composer aktif sohbete yazar
    xmpp.MainWindow._send_message(w)          # mid'li own-send (TTL aktif)
    uid = w.chats[TAB][-1][9]
    assert ("t@x", uid) in w._ttl_deadlines
    assert len(tab["rows"]) == 1
    assert _row_body(tab["rows"][-1]) == "own-ttl"
    assert abs(_tab_ms_timers(w)[0] - 10_000) <= 1   # [tab, main]
    clock["now"] += 10
    w._afters[0][1]()                         # sekme zamanlayıcısı
    assert tab["rows"] == []                  # sekmede de süresi doldu
    assert ("t@x", uid) in w._ttl_deadlines   # mezar taşı yerinde


# ── 6) [2L-B1] Sekmenin kendi gönderimi TTL PARİTELİ (kimlik = uid) ──────────
def test_tab_inline_send_ttl(monkeypatch):
    """Inline _send: store → giriş/uid → mutlak vade kaydı → _add.

    B1 regresyonu: mid ŞART DEĞİLDİR — TTL kimliği (jid, örnek-uid)'dir;
    inline send mid ÜRETMEZ (mid="") ama TTL yine de çalışır: ana
    pencerede dolan mesaj sekmede de aynı mutlak vadede söner; reopen
    dirilmez. (Pre-fix: mid-kapısı kaydı engelliyordu — harita boş,
    zamanlayıcı yok, satır sonsuza dek görünür kalıyordu.)
    """
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l(ttl=5)
    tab = _open_tab(monkeypatch, w)
    w.active = TAB
    # ana render TTL'i çözsün (gerçek _render_history_entry)
    w._render_history_entry = lambda e: xmpp.MainWindow._render_history_entry(w, e)
    _SV.last.set("own-inline")
    _Entry.last.binds["<Return>"](None)
    # giriş: uid VAR, mid boş kalabilir (mid üretimi yok — wire dokunulmaz)
    entry = w.chats[TAB][-1]
    assert len(entry) == 10 and entry[9]     # uid'li tam tuple
    assert entry[7] == ""                    # mid yok — TTL yine de çalışır
    uid = entry[9]
    # mutlak vade: (target, uid) = 1005 (t=1000, TTL 5)
    assert w._ttl_deadlines[(TAB, uid)] == 1005.0
    # ana + sekme görünürlüğü ve tab zamanlayıcısı (kalan 5 s)
    assert len(tab["rows"]) == 1
    assert _row_body(tab["rows"][-1]) == "own-inline"
    assert abs(_tab_ms_timers(w)[0] - 5_000) <= 1   # kalan ömür
    # ana pencere (render yolu) canlı: vadede görünür
    xmpp.MainWindow._load_chat(w, TAB)
    assert len(w._bubble_widgets) == 1
    # t=1005: tab satırı gider; ana render gizler; mezar taşı kalır
    clock["now"] += 5
    w._afters[0][1]()                        # tab-lokal kaldırma
    assert tab["rows"] == []
    xmpp.MainWindow._load_chat(w, TAB)
    assert w._bubble_widgets == []           # ana pencere mezar taşına uyar
    assert w._ttl_deadlines[(TAB, uid)] == 1005.0
    # reopen: satır YOK; taze zamanlayıcı YOK (afters: tab + pre-render main)
    _close_tab(w, tab)
    tab2 = _open_tab(monkeypatch, w)
    assert tab2["rows"] == []
    assert len(w._afters) == 2               # TTL restart yok


# ── 7) 2H cap ↔ TTL zamanlayıcı etkileşimi (iki yön) ─────────────────────────
def test_tab_cap_and_ttl_timer_interaction(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    tab = _open_tab(monkeypatch, w)
    # Yön A (TTL önce): karışık akış — 75 TTL'li + 75 TTL'siz
    for k in range(75):
        _deliver2l(w, f"m-t{k}", f"gelen-t{k}")
        w._disappearing_ttl[TAB] = 0
        _deliver2l(w, f"m-n{k}", f"gelen-n{k}")
        w._disappearing_ttl[TAB] = TTL
    assert len(tab["rows"]) == 150
    clock["now"] += 11                        # TTL'liler doldu
    for _ms, fn in list(w._afters):           # tab-lokal kaldırmalar
        fn()
    assert len(tab["rows"]) == 75             # yalnız TTL'sizler kaldı
    assert all(not r.destroyed for r in tab["rows"])
    assert len(tab["frame"].children) == len(tab["rows"])   # FIFO == widget
    assert _row_body(tab["rows"][-1]) == "gelen-n74"
    # Yön B (cap önce): 200 TTL'li doldur → 10 TTL'siz ekle (ilk 10 TTL'li
    # evict edilir) → süre dolduğunda evict'lilerin timer'ı ZARARSIZdır
    w._disappearing_ttl[TAB] = TTL
    for k in range(200):
        _deliver2l(w, f"m-l{k}", f"gelen-l{k}")
    assert len(tab["rows"]) == CAP
    w._disappearing_ttl[TAB] = 0
    for k in range(10):
        _deliver2l(w, f"m-q{k}", f"gelen-q{k}")
    assert len(tab["rows"]) == CAP            # evict-before-append (2H)
    clock["now"] += 11                        # TTL'liler doldu
    for _ms, fn in list(w._afters):
        fn()                                  # evict'liler dahil zararsız
    assert [_row_body(r) for r in tab["rows"]] == \
        [f"gelen-q{k}" for k in range(10)]    # canlı TTL'liler gitti
    assert all(not r.destroyed for r in tab["rows"])
    assert len(tab["frame"].children) == len(tab["rows"])


# ── 8) Kapatılmış eski sekmenin zamanlayıcısı yeni sekmeye dokunamaz ─────────
def test_closed_old_tab_timer_cannot_mutate_reopened_tab(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    tab_old = _open_tab(monkeypatch, w)
    _deliver2l(w, "m-old", "gelen-old")       # eski sekmede TTL satırı+timer
    clock["now"] += 11
    _close_tab(w, tab_old)                    # eski sekme kapandı
    tab_new = _open_tab(monkeypatch, w)       # AYNI JID için yeni sekme
    w._disappearing_ttl[TAB] = 0
    for k in range(5):                        # yeni sekmeye TTL'siz canlı
        _deliver2l(w, f"m-new{k}", f"gelen-new{k}")
    new_rows = list(tab_new["rows"])
    assert len(new_rows) == 5
    for _ms, fn in list(w._afters):           # ESKİ zamanlayıcılar ateşlenir
        fn()
    assert list(tab_new["rows"]) == new_rows  # yeni FIFO değişmedi
    assert all(not r.destroyed for r in tab_new["rows"])


# ── 9) Eski (UID'siz) girişler: mid fallback ile mezar taşı saygılı ──────────
def test_tab_legacy_uid_fallback_safe(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    w._disappearing_ttl = {}
    # 9'luk canlı + 9'luk dolmuş + 8'lik eski-MAM şekli
    w.chats[TAB] = [
        ("Ali", "gövde 0", False, "10:00", "them", "", False, "m-9a", ""),
        ("Ali", "gövde 1", False, "10:01", "them", "", False, "m-9b", ""),
        ("Ali", "gövde 2", False, "10:02", "them", "", False, "m-8"),
    ]
    w._ttl_deadlines = {
        (TAB, "m-9a"): clock["now"] + 30.0,   # canlı legacy (kalan ömür)
        (TAB, "m-9b"): clock["now"] - 1.0,    # dolmuş mezar taşı (legacy)
    }
    tab = _open_tab(monkeypatch, w)
    bodies = [_row_body(r) for r in tab["rows"]]
    assert "gövde 0" in bodies                # canlı legacy çizilir
    assert "gövde 1" not in bodies            # dolmuş legacy atlanır (çökmez)
    assert "gövde 2" in bodies                # 8'lik normal çizilir
    assert abs(_tab_ms_timers(w)[-1] - 30_000) <= 1   # kalan ömür zamanlandı
    # haritadaki mezar taşı dokunulmadı
    assert w._ttl_deadlines[(TAB, "m-9b")] <= clock["now"]


# ── 10) TTL'siz akış değişmez (2H cap + sıralama + TTL'siz zamanlayıcı) ──────
def test_tab_non_ttl_unchanged(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    _patch_clock(monkeypatch)
    w = _win2l()
    w._disappearing_ttl = {}
    tab = _open_tab(monkeypatch, w)
    n_afters = len(w._afters)
    for k in range(300):
        _deliver2l(w, f"m-{k}", f"gelen-{k}")
    assert len(tab["rows"]) == CAP            # 2H cap aynı
    assert len(w.chats[TAB]) == 300           # domain tamamı
    assert _row_body(tab["rows"][-1]) == "gelen-299"
    assert _row_body(tab["rows"][0]) == "gelen-100"   # son CAP dili
    assert len(w._afters) == n_afters         # TTL katmanından sıfır zamanlayıcı


# ── 11) İlk açılış sınırı hâlâ min(N, 200) ───────────────────────────────────
def test_tab_initial_bound_still_200(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    _patch_clock(monkeypatch)
    for n in (0, 1, 50, 199, 200, 201, 1000, 5000):
        w = _win2l()
        w._disappearing_ttl = {}
        w.chats[TAB] = _mk_hist(n, prefix="g")
        tab = _open_tab(monkeypatch, w)
        assert len(tab["rows"]) == min(n, 200)
        if n > 0:
            assert _row_body(tab["rows"][-1]) == f"gövde {n - 1}"
            assert _row_body(tab["rows"][0]) == f"gövde {max(0, n - 200)}"
        _close_tab(w, tab)


# ── ADVERSARIAL: aynı-mid ayrık-uid + çapraz-sohbet (sekme tarafı) ───────────
def test_tab_same_mid_distinct_uid_and_cross_chat(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    tab = _open_tab(monkeypatch, w)
    w._disappearing_ttl[TAB] = 5
    _deliver2l(w, "X", "gelen-kisa")          # M1: TTL 5 → vade 1005
    uid1 = w.chats[TAB][-1][9]
    w._disappearing_ttl[TAB] = 60
    _deliver2l(w, "X", "gelen-uzun")          # M2: TTL 60 → vade 1060
    uid2 = w.chats[TAB][-1][9]
    assert uid1 != uid2 and len(tab["rows"]) == 2
    # afters: [M1tab, M1main, M2tab, M2main] (tab feed deliver'dan önce)
    m1_row = tab["rows"][0]
    clock["now"] += 6                         # t=1006: M1 dolmuş, M2 canlı
    w._afters[0][1]()                         # yalnız M1'in tab zamanlayıcısı
    assert m1_row.destroyed
    assert len(tab["rows"]) == 1              # M2 kaldı — bağımsız
    assert _row_body(tab["rows"][-1]) == "gelen-uzun"
    # çapraz sohbet: iki ayrı tab, aynı wire mid, bağımsız vade
    w._disappearing_ttl["a@x"] = 5
    w._disappearing_ttl["z@x"] = 60
    tab_a = _open_tab(monkeypatch, w, "a@x")
    _deliver2l(w, "X", "gelen-a", jid="a@x")  # t=1006 → vade 1011
    tab_z = _open_tab(monkeypatch, w, "z@x")
    _deliver2l(w, "X", "gelen-z", jid="z@x")  # t=1006 → vade 1066
    assert len(tab_a["rows"]) == 1 and len(tab_z["rows"]) == 1
    # afters şimdi: [M1tab, M1main, M2tab, M2main, aTab, aMain, zTab, zMain]
    clock["now"] += 6                         # t=1012: a@x dolmuş, z@x canlı
    w._afters[4][1]()                         # yalnız a@x'in tab zamanlayıcısı
    assert tab_a["rows"] == []                # a@x söndü
    assert len(tab_z["rows"]) == 1            # z@x bağımsız canlı
    # mezar taşları: her JID kendi taşını tutuyor
    assert w._ttl_deadlines[("a@x", w.chats["a@x"][-1][9])] <= clock["now"]
    assert w._ttl_deadlines[("z@x", w.chats["z@x"][-1][9])] > clock["now"]


# ══ [2L-B1] UID-without-mid kimlik sözleşmesi (6 ekleme testi) ════════════════


def _inline_send(w, body):
    _SV.last.set(body)
    _Entry.last.binds["<Return>"](None)


# ── G1) mid="" iken TTL kimliği uid'dir (mid fallback'e düşmez) ──────────────
def test_inline_send_ttl_without_mid_uses_uid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l(ttl=7)
    _open_tab(monkeypatch, w)                 # inline composer için sekme gerekli
    w.active = TAB
    _inline_send(w, "own-uid")
    entry = w.chats[TAB][-1]
    assert entry[7] == "" and entry[9]        # mid="" + uid VAR
    uid = xmpp.MainWindow._entry_instance_uid(w, entry)
    assert uid == entry[9]                    # kimlik uid — mid'e düşmedi
    assert w._ttl_deadlines[(TAB, uid)] == clock["now"] + 7.0
    assert 0 < xmpp.MainWindow._ttl_remaining(w, TAB, uid, 99) < 99


# ── G2) Ana render: mid="" + uid'li giriş — canlı/sınır/mezar taşı ───────────
def test_main_render_uid_ttl_without_mid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    w.active = TAB
    w._render_history_entry = lambda e: xmpp.MainWindow._render_history_entry(w, e)
    # güncel 10'luk giriş: mid="" (index 7) + uid=77 (index 9)
    w.chats[TAB] = [("Ali", "gövde 0", False, "10:00", "them", "", False,
                     "", "", 77)]
    w._ttl_deadlines = {(TAB, 77): clock["now"] + 10.0}
    xmpp.MainWindow._load_chat(w, TAB)
    assert len(w._bubble_widgets) == 1        # mid="" olmasına RAĞMEN canlı çizildi
    assert abs(_tab_ms_timers(w)[-1] - 10_000) <= 1   # kalan ömür
    clock["now"] += 10                        # tam sınır: deadline == now
    xmpp.MainWindow._load_chat(w, TAB)
    assert w._bubble_widgets == []            # mezar taşı: gizli
    assert w._ttl_deadlines[(TAB, 77)] <= clock["now"]
    xmpp.MainWindow._load_chat(w, TAB)
    assert w._bubble_widgets == []            # tekrar: diriliş yok


# ── G3) Sekme _add: mid="" + uid'li giriş — aynı sözleşme ────────────────────
def test_tab_add_uid_ttl_without_mid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    w.chats[TAB] = [("Ali", "gövde 0", False, "10:00", "them", "", False,
                     "", "", 88)]     # mid="" (7), local_path="" (8), uid=88 (9)
    w._ttl_deadlines = {(TAB, 88): clock["now"] + 8.0}
    tab = _open_tab(monkeypatch, w)
    assert len(tab["rows"]) == 1              # mid="" olmasına rağmen çizildi
    assert abs(_tab_ms_timers(w)[0] - 8_000) <= 1
    clock["now"] += 8
    _close_tab(w, tab)
    tab2 = _open_tab(monkeypatch, w)          # reopen: mezar taşı → gizli
    assert tab2["rows"] == []
    assert w._ttl_deadlines[(TAB, 88)] <= clock["now"]   # taş korundu


# ── G4) Eski (UID'siz + mid'li) girişler: mid fallback yerinde ───────────────
def test_legacy_mid_fallback_still_works(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l()
    w.active = TAB
    w._render_history_entry = lambda e: xmpp.MainWindow._render_history_entry(w, e)
    w.chats[TAB] = [
        ("Ali", "gövde 0", False, "10:00", "them", "", False, "m-leg-a", ""),
        ("Ali", "gövde 1", False, "10:01", "them", "", False, "m-leg-b", ""),
    ]
    w._ttl_deadlines = {
        (TAB, "m-leg-a"): clock["now"] + 20.0,   # canlı (mid fallback anahtarı)
        (TAB, "m-leg-b"): clock["now"] - 1.0,    # dolmuş mezar taşı
    }
    # ana render: canlı çizilir, dolmuş atlanır
    xmpp.MainWindow._load_chat(w, TAB)
    bodies = [getattr(r, "_body", "") for r in w._bubble_widgets]
    assert "gövde 0" in bodies and "gövde 1" not in bodies
    assert abs(_tab_ms_timers(w)[-1] - 20_000) <= 1
    # sekme: aynı fallback davranışı
    tab = _open_tab(monkeypatch, w)
    tab_bodies = [_row_body(r) for r in tab["rows"]]
    assert "gövde 0" in tab_bodies and "gövde 1" not in tab_bodies
    assert w._ttl_deadlines[(TAB, "m-leg-b")] <= clock["now"]   # taş korundu


# ── G5) TTL=0 inline send: kayıt/zamanlayıcı yok, davranış normal ────────────
def test_inline_non_ttl_unchanged(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    _patch_clock(monkeypatch)
    w = _win2l(ttl=0)
    tab = _open_tab(monkeypatch, w)
    w.active = TAB
    n_afters = len(w._afters)
    _inline_send(w, "own-normal")
    assert len(tab["rows"]) == 1              # satır normal çizilir
    assert _row_body(tab["rows"][-1]) == "own-normal"
    assert w._ttl_deadlines == {}             # TTL=0 → kayıt yok
    assert len(w._afters) == n_afters         # sıfır TTL zamanlayıcısı
    assert len(w.chats[TAB]) == 1             # domain normal


# ── G6) Cap baskısı altında inline TTL gönderimleri ──────────────────────────
def test_inline_ttl_cap_interaction(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2l(ttl=10)
    tab = _open_tab(monkeypatch, w)
    w.active = TAB
    peak = 0
    for k in range(250):                      # hepsi TTL'li inline send
        _inline_send(w, f"own-{k}")
        peak = max(peak, len(tab["rows"]))
        assert len(tab["rows"]) <= CAP, f"transyan taşma: {len(tab['rows'])}"
    assert peak <= CAP
    assert len(w.chats[TAB]) == 250           # domain tamamı
    clock["now"] += 10                        # hepsinin vadesi doldu
    for _ms, fn in list(w._afters):           # evict'liler dahil zararsız
        fn()
    assert tab["rows"] == []                  # hepsi söndü
    assert tab["frame"].children == []        # FIFO == widget ağacı
    assert len(w._ttl_deadlines) == 250       # mezar taşları korunur
    _close_tab(w, tab)
    tab2 = _open_tab(monkeypatch, w)          # reopen: diriliş yok
    assert tab2["rows"] == []
