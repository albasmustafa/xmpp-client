"""Phase B3 — MAM intent-leak regression testleri (networksüz).

`_load_older_mam` / `_load_mam_history` niyeti `bot.fetch_mam`'den ÖNCE
yazar. Fetch senkron raise ederse niyet stale kalır ve o JID için MAM
(ilk yükleme + Load Older) kilitlenir. Beklenen: başarısız isteğin niyeti
geri alınır; disconnect lifecycle'ı in-flight niyetleri temizler.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import xmpp  # noqa: E402


def _win(active="a@b"):
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w.rooms = []
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


class RaisingFetch:
    """fetch_mam her çağrıda deterministic raise eder; çağrı sayısını tutar."""

    def __init__(self, exc=None):
        self.exc = exc or RuntimeError("bağlantı yok")
        self.calls = 0

    def __call__(self, *a, **k):
        self.calls += 1
        raise self.exc


class CountingFetch:
    def __init__(self):
        self.calls = 0

    def __call__(self, *a, **k):
        self.calls += 1


# 1. TEST A — older path: sync fetch raise → stale intent -------------------------


def test_older_fetch_raise_rolls_back_intent():
    """fetch_mam senkron raise ederse niyet GERİ ALINMALI (stale kalmamalı).

    PRE-FIX: niyet sözlükte kalır + RuntimeError dışarı sızar → FAIL.
    """
    w = _win()
    raising = RaisingFetch()
    w.bot.fetch_mam = raising
    xmpp.MainWindow._load_older_mam(w)
    assert "a@b" not in w._history_mam_intent        # stale intent YOK
    assert raising.calls == 1                        # tek deneme; sessiz retry yok


def test_failed_older_fetch_does_not_block_retry():
    """Başarısız fetch sonrası ikinci Load Older isteği YENİDEN denenmeli.

    POST-FIX: exception içeride yakalanır (dışarı sızmadan), niyet geri
    alınır; pre-fix'te ise RuntimeError dışarı sızar + niyet stale kalırdı.
    """
    w = _win()
    raising = RaisingFetch()
    w.bot.fetch_mam = raising
    xmpp.MainWindow._load_older_mam(w)  # ilk deneme: raise → rollback, sızmaz
    assert "a@b" not in w._history_mam_intent
    # ikinci çağrı: fetch artık çalışıyor → istek gider, intent kurulur
    w.bot.fetch_mam = lambda *a, **k: None
    xmpp.MainWindow._load_older_mam(w)
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "older"}
    assert raising.calls == 1  # ilki başarısıztı, retry bu çağrıda


# 2. Initial path aynı sızıntı ------------------------------------------------------


def test_initial_fetch_raise_rolls_back_intent():
    """_load_mam_history fetch raise ederse niyet geri alınmalı."""
    w = _win(active="a@b")
    raising = RaisingFetch()
    w.bot.fetch_mam = raising
    xmpp.MainWindow._load_mam_history(w)
    assert "a@b" not in w._history_mam_intent
    assert raising.calls == 1


def test_failed_initial_fetch_does_not_block_retry():
    """Başarısız initial fetch sonrası sohbet açılışı yeniden dener."""
    w = _win(active="a@b")
    raising = RaisingFetch()
    w.bot.fetch_mam = raising
    xmpp.MainWindow._load_mam_history(w)  # raise → rollback, sızmaz
    assert "a@b" not in w._history_mam_intent
    w.bot.fetch_mam = lambda *a, **k: None
    xmpp.MainWindow._load_mam_history(w)
    assert w._history_mam_intent["a@b"] == {"token": 0, "intent": "initial"}


# 3. Mevcut E-kuralı guard'ı (davranış belgelenir) ----------------------------------


def test_stale_intent_guards_next_request():
    """Intent doluyken ikinci istek gönderilmez (E kuralı) — fetch çağrılmaz."""
    w = _win()
    counting = CountingFetch()
    w.bot.fetch_mam = counting
    w._history_mam_intent["a@b"] = {"token": 0, "intent": "older"}
    xmpp.MainWindow._load_older_mam(w)
    assert counting.calls == 0  # guard: mevcut niyet varken yeni istek yok


# 4. Disconnect lifecycle: in-flight niyetler temizlenmeli --------------------------


def test_disconnect_clears_in_flight_intents():
    """Bağlantı koptuğunda uçuştaki MAM niyetleri geçersizdir: sonuç bir
    daha gelmeyeceği için stale intent sonraki yüklemeleri kilitler.
    Disconnect lifecycle'ı (alias clear-all gibi) niyetleri de temizlemeli."""
    w = _win()
    w._history_mam_intent["a@x"] = {"token": 1, "intent": "older"}
    w._history_mam_intent["b@y"] = {"token": 2, "intent": "initial"}
    w._append = lambda *a, **k: None  # UI stub
    xmpp.MainWindow._handle(w, "disconnected", None)
    assert w._history_mam_intent == {}  # temiz; stale yok


def test_disconnect_clears_aliases_too_existing_behavior():
    """Mevcut lifecycle: disconnect alias registry'yi temizler (kilit)."""
    w = _win()
    w._mam_aliases["a@x"] = {"r1": ("m1", "gövde", False)}
    w._append = lambda *a, **k: None
    xmpp.MainWindow._handle(w, "disconnected", None)
    assert w._mam_aliases == {}
