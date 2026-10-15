"""RESOURCE HARDENING 2J.b: TTL defteri için örnek kimliği (instance UID).

Kanıt: (jid, mid) anahtarı çapraz-sohbet bulaşmasını kapatır (2I-B1) ama
AYNI sohbetteki iki mantıksal mesaj aynı gönderici-kontrollü mid'i
taşıyabilir; mid defteri ikinci örneği ilk vadeye bağlardı. Artık her yeni
history girişi dahili bir örnek UID taşır (index 9; wire/DB'ye gitmez) ve
TTL anahtarı (jid, uid)'dir: örnekler bağımsız vade taşır, UID re-render'da
asla yenilenmez, eski/UID'siz girişler mid'e düşerek güvenle render edilir.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2i_ttl_expiry import _patch_clock, _Row, _rows_with_mid  # noqa: E402
from test_history_window_bounds import _Cap, _mam_msgs, _mk_hist, _win  # noqa: E402

import xmpp  # noqa: E402

TTL = 10.0


def _win2j(hist=(), ttl=TTL, jid="a@b"):
    """[2J.b] Üretim _store (UID atayan) + üretim TTL yollarını süren çift.

    _db_store_msg monkeypatch gerektirir; _append Tk'sız _Row üretir.
    """
    w = _win(hist, jid=jid)
    w._bubble_widgets = []
    w._msg_ids = {}
    w._notify_enabled = False
    w._sound_enabled = False
    w._show_toast = lambda *a, **k: None
    w._send_read_receipts = False
    w._disappearing_ttl = {jid: ttl}
    w._ttl_deadlines = {}
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


def _deliver2j(w, mid, body="selam", jid=None):
    """Üretim _handle("msg") yolu: gerçek _store (UID'li) + TTL kaydı."""
    jid = jid or w.active
    w.active = jid
    xmpp.MainWindow._handle(w, "msg", {"from": jid, "nick": "Ali",
                                       "body": body, "mid": mid})


# ── 1) ÇEKİRDEK: aynı sohbette aynı mid → bağımsız vadeler ──────────────────
def test_same_chat_duplicate_mid_independent_ttl(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    _deliver2j(w, "X", "bir")            # t=1000 → vade 1010
    clock["now"] += 2
    _deliver2j(w, "X", "iki")            # t=1002 → vade 1012
    entries = w.chats["a@b"]
    uids = [e[9] for e in entries]
    assert len(set(uids)) == 2           # ayrık örnek UİD'leri
    assert dict(w._ttl_deadlines) == {("a@b", uids[0]): 1010.0,
                                      ("a@b", uids[1]): 1012.0}
    # t=1011: birinci dolmuş-gizli, ikinci canlı-görünür
    clock["now"] += 9
    start = max(0, len(entries) - 200)
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    rows = _rows_with_mid(w, "X")
    assert len(rows) == 1 and rows[0]._body == "iki"
    # t=1012+: ikinci örnek de dolar — satırı yeniden çizilmez ve [2K] dolmuş
    # vade MEZAR TAŞI olarak haritada kalır (sonraki render'larda da gizli)
    clock["now"] += 1.5
    xmpp.MainWindow._render_bounded(w, "a@b", start)
    assert all(r._body != "iki" for r in _rows_with_mid(w, "X"))
    assert ("a@b", uids[1]) in w._ttl_deadlines
    assert w._ttl_deadlines[("a@b", uids[1])] <= clock["now"]


# ── 2) UID re-render/rebase'te yaşar; vade sıfırlanmaz ──────────────────────
def test_instance_uid_survives_rerender(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver2j(w, "X", "bir")            # t=1000 → 1010
    clock["now"] += 2
    _deliver2j(w, "X", "iki")            # t=1002 → 1012
    # yalnız taze (UID'li) girişlere bakılır; _mk_hist 9'luk (UID'siz) üretir
    uids_before = [e[9] for e in w.chats["a@b"][-2:]]
    clock["now"] += 3                    # t=1005
    n_before = len(w._afters)  # teslim anındaki meşru tam-TTL zamanlayıcıları dahil
    # 1) tam yeniden yükleme
    xmpp.MainWindow._load_chat(w, "a@b")
    assert [e[9] for e in w.chats["a@b"][-2:]] == uids_before
    # 2) history ↔ latest geçişi (rebase yolu dahil)
    xmpp.MainWindow._on_history_older(w)
    xmpp.MainWindow._on_history_latest(w)
    assert [e[9] for e in w.chats["a@b"][-2:]] == uids_before
    # re-render'ların EKLEDİĞİ zamanlamalar yalnız KALAN süre (5 s / 7 s) —
    # tam TTL yeniden başlatılmaz (vade sıfırlanmaz)
    new_sched = {ms for ms, _ in w._afters[n_before:]}
    assert new_sched == {5000, 7000}
    # 3) t=1011: dolan dirilmez; canlı olan kendi UID'siyle kalır
    clock["now"] += 6
    xmpp.MainWindow._load_chat(w, "a@b")
    rows = _rows_with_mid(w, "X")
    assert len(rows) == 1 and rows[0]._body == "iki"
    assert [e[9] for e in w.chats["a@b"][-2:]] == uids_before


# ── 3) Clear yaşam döngüsü: JID'in tüm UID anahtarları unutulur ──────────────
def test_clear_forgets_all_uid_keys_for_jid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    _patch_clock(monkeypatch)
    w = _win2j(_mk_hist(10))
    xmpp.MainWindow._load_chat(w, "a@b")
    _deliver2j(w, "a1")
    _deliver2j(w, "a2")
    w._disappearing_ttl["z@z"] = 30
    _deliver2j(w, "z1", jid="z@z")
    _deliver2j(w, "z2", jid="z@z")
    assert len(w._ttl_deadlines) == 4
    # clear A: yalnız A anahtarları; 2F generation bump korunur
    w.active = "a@b"
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    w._load_chat = _Cap()
    gen_before = dict(w._mam_gen)
    xmpp.MainWindow._clear_active_history(w)
    assert {k[0] for k in w._ttl_deadlines} == {"z@z"}
    assert len(w._ttl_deadlines) == 2
    assert w._mam_gen == {"a@b": gen_before.get("a@b", 0) + 1}
    # clear-all: harita boşalır
    monkeypatch.setattr(xmpp, "_db_clear_all", _Cap())
    xmpp.MainWindow._clear_all_history(w)
    assert w._ttl_deadlines == {}


# ── 4) Taze MAM girişleri UID'li; çökmez, rastgele TTL kurmaz ────────────────
def test_mam_fresh_entries_uid_safe(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    _patch_clock(monkeypatch)
    w = _win2j(_mk_hist(500))
    xmpp.MainWindow._load_chat(w, "a@b")
    n_afters = len(w._afters)
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "messages": _mam_msgs(50, "f")})
    fresh = w.chats["a@b"][:50]
    assert all(len(e) == 10 and e[9] for e in fresh)   # 10'luk + UID'li
    assert len({e[9] for e in fresh}) == 50            # benzersiz
    # pencereyi zorla çiz: çökmez, satırlar görünür, TTL zamanlayıcısı YOK
    xmpp.MainWindow._render_bounded(w, "a@b", 0)
    mids = {getattr(r, "_mid", "") for r in w._bubble_widgets}
    assert {f"f{i}" for i in range(50)} <= mids
    assert len(w._afters) == n_afters                  # rastgele TTL yok


# ── 5) Geriye uyum: eski giriş şekilleri güvenle render edilir ───────────────
def test_tuple_backward_compatibility(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    _patch_clock(monkeypatch)
    w = _win2j()
    w.active = "a@b"
    # 9'luk (2I-öncesi) ve 8'lik (eski MAM) girişler çökmez, TTL'siz render
    w.chats["a@b"] = [
        ("Ali", "eski dokuz", False, "10:00", "them", "", False, "m-9", ""),
        ("Ali", "eski sekiz", False, "10:01", "them", "", False, "m-8"),
    ]
    xmpp.MainWindow._load_chat(w, "a@b")
    assert len(w._bubble_widgets) == 2
    assert w._afters == []                  # TTL zamanlayıcısı yok
    assert w._ttl_deadlines == {}           # kayıt da yok
    # _entry_instance_uid sözleşmesi: 10'luk→UID, 9'luk/8'lik→mid, None→fallback
    uid_fn = xmpp.MainWindow._entry_instance_uid
    assert uid_fn(w, None, "fb") == "fb"
    assert uid_fn(w, ("A", "b", False, "t", "them", "", False, "m1", "")) == "m1"
    assert uid_fn(w, ("A", "b", False, "t", "them", "", False, "m2")) == "m2"
    assert uid_fn(w, ("A", "b", False, "t", "them", "", False, "m3", "", 7)) == 7
    # 10'luk girişte mevcut index erişimleri (export/REST deseni) değişmedi
    entry = ("Ali", "gövde", False, "10:02", "me", "OOB", True, "m4", "LP", 99)
    assert (entry[0], entry[1], entry[7], entry[8]) == ("Ali", "gövde", "m4", "LP")


# ── 6) 2I-B1 çapraz-sohbet regresyonu UID'li girişlerle de yeşil ─────────────
def test_cross_chat_regression_with_uid_entries(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    clock = _patch_clock(monkeypatch)
    w = _win2j()
    w._disappearing_ttl = {"a@b": 5, "z@z": 60}
    _deliver2j(w, "X", "A", jid="a@b")
    _deliver2j(w, "X", "Z", jid="z@z")
    uid_a = w.chats["a@b"][-1][9]
    uid_z = w.chats["z@z"][-1][9]
    assert uid_a != uid_z
    assert abs(w._ttl_deadlines[("a@b", uid_a)]
               - w._ttl_deadlines[("z@z", uid_z)] + 55) < 1e-9
    clock["now"] += 6
    w.active = "a@b"
    xmpp.MainWindow._load_chat(w, "a@b")
    assert _rows_with_mid(w, "X") == []      # A'nın 5 s'lik örneği söndü
    w.active = "z@z"
    xmpp.MainWindow._load_chat(w, "z@z")
    rows = _rows_with_mid(w, "X")
    assert len(rows) == 1 and rows[0]._body == "Z"   # Z 60 s canlı
