"""RESOURCE HARDENING 2N: MAM kimlik/imleç dedupe (imza temelli).

Kanıt: eski `seen = {mid}` dedupe (1) live/mid ile sunucu-ekli stanza-id
çakışmasını kapatamıyordu (live raw R ↔ MAM logical S — kopya sürüyordu)
ve (2) aynı mid + FARKLI gövde girişlerini sessizce siliyordu. [2N] ile
dedupe imzası (kimlik-alias, body, yön) temellidir: alias kümesi
{logical_mid, raw_id} − {""}; alias + aynı gövde + aynı yön → duplicate;
aynı alias + farklı gövde/yön → KORUNUR; kimliksiz → asla dedupe edilmez.
İmleç archive_id'dir (logical_mid yalnız fallback); archive_id/raw_id
self.chats biçimine girmez.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _win  # noqa: E402

import xmpp  # noqa: E402


def _mam_msg(body, mid="", raw_id="", archive_id="", is_me=False,
             frm="a@b", ts="2026-09-14T10:00:00Z"):
    d = {"from": frm, "body": body, "is_me": is_me, "ts": ts, "mid": mid}
    if raw_id:
        d["raw_id"] = raw_id
    if archive_id:
        d["archive_id"] = archive_id
    return d


def _mam_w(hist=None, jid="a@b"):
    w = _win(hist, jid=jid)
    return w


def _entries(w, jid="a@b"):
    return w.chats.get(jid, [])


def _summary(w, jid="a@b"):
    """(mid, body, is_me) imza listesi — sıra korunur (yeni → eski)."""
    return [(e[7], e[1], bool(e[2])) for e in _entries(w, jid)]


def _page(w, msgs, jid="a@b", token=0):
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": jid, "messages": msgs, "token": token})


# ── A) origin-id paritesi: live O ↔ MAM logical O → tek giriş ────────────────
def test_origin_id_parity_one_entry():
    w = _mam_w(hist=[("Ali", "hello", False, "09:00", "them", "", False,
                      "O", "", 1)])
    _page(w, [_mam_msg("hello", mid="O", raw_id="R")])
    assert _summary(w) == [("O", "hello", False)]      # kopya gitti
    assert len(_entries(w)) == 1


# ── B) raw alias: live mid R ↔ MAM logical S + raw R → tek giriş ─────────────
def test_raw_alias_closes_server_stanza_id_mismatch():
    w = _mam_w(hist=[("Ali", "hello", False, "09:00", "them", "", False,
                      "R", "", 1)])            # live: raw id R depolandı
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")])   # MAM: logical S
    assert _summary(w) == [("R", "hello", False)]      # kopya gitti
    assert len(_entries(w)) == 1


# ── C) ZORUNLU: alias kesişimi tek başına silme gerekçesi değildir ───────────
def test_alias_intersection_must_not_over_dedupe():
    w = _mam_w(hist=[("Ali", "hello", False, "09:00", "them", "", False,
                      "R", "", 1)])
    _page(w, [_mam_msg("DIFFERENT", mid="S", raw_id="R")])  # aynı alias,
    # FARKLI gövde → korunur (unsafe `aliases & mids: continue` bunu silerdi)
    assert _summary(w) == [("S", "DIFFERENT", False), ("R", "hello", False)]
    assert len(_entries(w)) == 2


# ── D) aynı logical mid + farklı gövde → ikisi de kalır ──────────────────────
def test_same_mid_different_body_both_survive():
    w = _mam_w(hist=[("Ali", "A", False, "09:00", "them", "", False,
                      "M", "", 1)])
    _page(w, [_mam_msg("B", mid="M")])
    assert _summary(w) == [("M", "B", False), ("M", "A", False)]
    assert len(_entries(w)) == 2


# ── E) aynı mid + aynı gövde + TERS yön → ikisi de kalır ─────────────────────
def test_same_mid_body_opposite_direction_both_survive():
    w = _mam_w(hist=[("Ali", "A", False, "09:00", "them", "", False,
                      "M", "", 1)])
    _page(w, [_mam_msg("A", mid="M", is_me=True)])     # ters yön
    assert _summary(w) == [("M", "A", True), ("M", "A", False)]
    assert len(_entries(w)) == 2


# ── F) gerçek duplicate: mid + gövde + yön aynı → tek giriş ──────────────────
def test_true_duplicate_collapses():
    w = _mam_w(hist=[("Ali", "hello", False, "09:00", "them", "", False,
                      "M", "", 1)])
    _page(w, [_mam_msg("hello", mid="M")])
    assert _summary(w) == [("M", "hello", False)]
    assert len(_entries(w)) == 1


# ── G) sayfa-içi duplicate: aynı sayfada iki kez → tek kabul ─────────────────
def test_intra_page_duplicate_accepted_once():
    w = _mam_w()
    _page(w, [_mam_msg("hello", mid="P"), _mam_msg("hello", mid="P")])
    assert _summary(w) == [("P", "hello", False)]
    assert len(_entries(w)) == 1


# ── H) çakışan sayfalar: kesin kardinalite ───────────────────────────────────
def test_overlapping_pages_exact_cardinality():
    w = _mam_w()
    _page(w, [_mam_msg("A", mid="X")])                 # 1. sayfa
    _page(w, [_mam_msg("A", mid="X"), _mam_msg("B", mid="Y")])  # çakışan
    assert _summary(w) == [("Y", "B", False), ("X", "A", False)]
    assert len(_entries(w)) == 2


# ── I) mid'siz iki mesaj → ikisi de korunur ──────────────────────────────────
def test_midless_messages_never_deduped():
    w = _mam_w()
    _page(w, [_mam_msg("bir"), _mam_msg("iki")])       # mid="" — kimliksiz
    assert _summary(w) == [("", "bir", False), ("", "iki", False)]
    assert len(_entries(w)) == 2


# ── J) çapraz-JID aynı kimlikler: izole ──────────────────────────────────────
def test_cross_jid_same_identities_isolated():
    wa = _mam_w(hist=[("Ali", "A'ya ait", False, "09:00", "them", "", False,
                       "X", "", 1)], jid="a@b")
    wb = _mam_w(hist=[("Ayşe", "B'ye ait", False, "09:00", "them", "", False,
                       "X", "", 1)], jid="b@b")
    _page(wa, [_mam_msg("A'dan yankı", mid="X")], jid="a@b")
    _page(wb, [_mam_msg("B'den yankı", mid="X")], jid="b@b")
    assert _summary(wa, "a@b") == [("X", "A'dan yankı", False),
                                   ("X", "A'ya ait", False)]
    assert _summary(wb, "b@b") == [("X", "B'den yankı", False),
                                   ("X", "B'ye ait", False)]


# ── K) imleç: archive_id ≠ logical_mid → _mam_oldest archive_id'dir ──────────
def test_cursor_uses_archive_id_not_logical_mid():
    w = _mam_w()
    _page(w, [_mam_msg("hello", mid="O", archive_id="arch-1")])
    assert w._mam_oldest["a@b"] == "arch-1"   # logical_mid "O" KULLANILMAZ


# ── L) _load_older_mam: archive_id before= ile uçar ──────────────────────────
def test_load_older_mam_sends_archive_id_as_before():
    w = _mam_w()
    fetches = []
    w.bot = types.SimpleNamespace(
        fetch_mam=lambda j, n, **kw: fetches.append((j, n, kw)))
    w._mam_oldest["a@b"] = "arch-1"
    w._mam_has_more["a@b"] = True
    xmpp.MainWindow._on_history_older(w)      # start=0 → Older isteği
    assert fetches == [("a@b", 50, {"before": "arch-1", "token": 0})]


# ── M) archive_id yoksa mid fallback çalışır ─────────────────────────────────
def test_cursor_falls_back_to_mid_without_archive_id():
    w = _mam_w()
    _page(w, [_mam_msg("hello", mid="M")])    # archive_id YOK
    assert w._mam_oldest["a@b"] == "M"


# ── N) bayat token: geçmiş/imleç mutasyona uğramaz ───────────────────────────
def test_stale_token_does_not_mutate_history_or_cursor():
    w = _mam_w(hist=[("Ali", "eski", False, "09:00", "them", "", False,
                      "M", "", 1)])
    w._mam_gen = {"a@b": 1}                   # güncel generation 1
    w._mam_oldest["a@b"] = "eski-imleç"
    before_summary = _summary(w)
    _page(w, [_mam_msg("yeni", mid="M2")], token=0)   # bayat token
    assert _summary(w) == before_summary      # geçmiş değişmedi
    assert w._mam_oldest["a@b"] == "eski-imleç"        # imleç değişmedi


# ── O) _msg_inst_seq monotonik kalır ─────────────────────────────────────────
def test_msg_inst_seq_remains_monotonic():
    w = _mam_w()
    _page(w, [_mam_msg("bir", mid="m1"), _mam_msg("iki", mid="m2")])
    uids_1 = sorted(e[9] for e in _entries(w))
    assert len(uids_1) == 2 and uids_1 == [1, 2]
    assert w._msg_inst_seq == 2
    _page(w, [_mam_msg("üç", mid="m3")])
    uids_new = [e[9] for e in _entries(w) if e[9] not in uids_1]
    assert uids_new == [3]                     # yeni uid öncekilerin ÜSTÜNDE
    assert w._msg_inst_seq == 3                # sayaç monotonik: 3 kabul


# ── P) self.chats tuple tam 10 eleman ────────────────────────────────────────
def test_chat_tuple_exactly_ten_elements():
    w = _mam_w()
    _page(w, [_mam_msg("hello", mid="M", raw_id="R", archive_id="arch-1")])
    entries = _entries(w)
    assert len(entries) == 1
    assert all(len(e) == 10 for e in entries)


# ── Q) raw_id/archive_id tuple alanlarına girmez ─────────────────────────────
def test_raw_and_archive_ids_never_stored_in_tuple():
    w = _mam_w()
    _page(w, [_mam_msg("hello", mid="M", raw_id="RAW-XYZ",
                       archive_id="ARCH-XYZ")])
    entry = _entries(w)[0]
    assert entry[7] == "M"                    # depolanan kimlik logical_mid
    assert "RAW-XYZ" not in entry             # ham id asla depolanmaz
    assert "ARCH-XYZ" not in entry            # archive_id asla depolanmaz
    assert all(not isinstance(v, tuple) for v in entry)
