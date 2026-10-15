"""Phase B1 — MAM cursor-livelock regression testleri.

mam_results: tam sayfa (>=50 mesaj) geldiği hâlde msgs[0]dan güvenilir
cursor (archive_id/mid) türetilemiyorsa eski kod `_mam_has_more` True
bırakıyordu → `_load_older_mam` aynı sayfayı tekrar ister → livelock.

Beklenen (düzeltme sonrası) davranış: imleç türetilemeyen sayfada
`_mam_has_more` False olur (fail-stop) — sistem aynı sayfayı cursor'suz
sonsuz yeniden istemez. İmleçli normal sayfalarda continuation True olarak
korunur.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


def _win():
    """mam_results akışını sürebilen minimal pencere çifti."""
    w = object.__new__(xmpp.MainWindow)
    w.active = "other@x"          # render yolu tetiklenmesin
    w.chats = {}
    w._msg_ids = {}
    w._mam_aliases = {}
    w._mam_gen = {}
    w._history_mam_intent = {}
    w._mam_oldest = {"a@b": "OLD-CURSOR"}
    w._mam_has_more = {"a@b": True}
    w._history_start = {}
    w._history_view_mode = {}
    w._history_pending = {}
    w._msg_inst_seq = 0
    w.bot = types.SimpleNamespace(fetch_mam=lambda *a, **k: None)
    w.root = types.SimpleNamespace(after=lambda *a: None)
    return w


def _dispatch(w, msgs):
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@b", "token": None, "messages": msgs})


def _cursorless_batch(n=50):
    """archive_id/mid İÇERMEYEN n mesaj — cursor türetilemez."""
    return [{"body": f"m{i}", "is_me": False, "from": "a@x"}
            for i in range(n)]


# 1. B1 regression — pre-fix FAIL etmeli --------------------------------------------


def test_cursorless_full_page_disables_has_more():
    """İmleç türetilemeyen tam sayfa → has_more False (fail-stop, livelock yok).

    PRE-FIX: `_mam_has_more` True kalır → bu test FAIL eder (livelock kanıtı).
    """
    w = _win()
    _dispatch(w, _cursorless_batch(50))
    assert w._mam_has_more["a@b"] is False


def test_cursorless_page_does_not_advance_oldest():
    """İmleç türetilemeyen sayfa `_mam_oldest`i DEĞİŞTİRMEMELİ (state kanıtı)."""
    w = _win()
    _dispatch(w, _cursorless_batch(50))
    assert w._mam_oldest["a@b"] == "OLD-CURSOR"  # eski imleç korunur


def test_cursorless_refetch_growth_evidence():
    """Aynı sayfanın yeniden gelmesi mesajları İKİYE katlar — livelock
    büyüme kanıtı (imleç ilerlemediği için)."""
    w = _win()
    _dispatch(w, _cursorless_batch(50))
    assert len(w.chats["a@b"]) == 50
    _dispatch(w, _cursorless_batch(50))
    assert len(w.chats["a@b"]) == 100  # aynı 50 mesaj tekrar materialize
    # düzeltme sonrası imleçsiz sayfa continuation'ı KAPATIR:
    assert w._mam_has_more["a@b"] is False


# 2. İmleçli normal sayfalar etkilenmez ----------------------------------------------


def test_cursor_page_advances_and_continues():
    w = _win()
    msgs = [{"body": f"m{i}", "is_me": False, "from": "a@x",
             "mid": f"cur-{i}"} for i in range(50)]
    _dispatch(w, msgs)
    assert w._mam_has_more["a@b"] is True
    assert w._mam_oldest["a@b"] == "cur-0"  # imleç msgs[0]'dan ilerledi


# 3. Kısa sayfa ------------------------------------------------------------------------


def test_short_page_disables_has_more():
    w = _win()
    msgs = [{"body": f"m{i}", "is_me": False, "from": "a@x",
             "mid": f"c-{i}"} for i in range(30)]
    _dispatch(w, msgs)
    assert w._mam_has_more["a@b"] is False  # <50 → devam yok (değişmedi)
