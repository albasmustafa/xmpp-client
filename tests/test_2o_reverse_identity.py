"""RESOURCE HARDENING 2O: ters kimlik dedupe (LIVE replay bastırma).

Kanıt: 2N MAM tarafı logical S + raw R bilir ve canonical satır S olarak
materialize eder; ancak sonraki LIVE teslim mid=R + aynı gövde/yön ile
gelirse ters korelasyon yoktu → ikinci satır materialize oluyordu (aynı
mesajın iki görünümü). [2O] ile:

- MAM kabulünde bounded registry kaydı: `_mam_aliases[jid][raw_id] =
  (canonical_mid, body, is_me)` (yalnız raw_id ≠ canonical_mid; archive_id
  ASLA girmaz; 256 alias/JID + 64 JID FIFO sınırlı; kalıcı değil);
- LIVE teslim TEK yetkili sınırda (`kind == "msg"`, _store ÖNCESİ) iki
  muhafazakâr kapıdan geçer: (A) birebir exact match — aynı (mid, body,
  yön) chats[jid]'de VARSA bastır; (B) ters-alias — kayıt + gövde + yön +
  kanonik satırın hâlâ aynı içerikle mevcut olması. Şüpheli/bayat kanıt
  FAIL-OPEN'dır; mid'siz teslim asla bastırılmaz.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2i_ttl_expiry import _Row  # noqa: E402
from test_history_window_bounds import _Cap, _win  # noqa: E402

import xmpp  # noqa: E402


def _mam_msg(body, mid="", raw_id="", archive_id="", is_me=False,
             frm="a@b", ts="2026-09-14T10:00:00Z"):
    d = {"from": frm, "body": body, "is_me": is_me, "ts": ts, "mid": mid}
    if raw_id:
        d["raw_id"] = raw_id
    if archive_id:
        d["archive_id"] = archive_id
    return d


def _page(w, msgs, jid="a@b", token=0):
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": jid, "messages": msgs, "token": token})


def _live(w, body, mid, frm="a@b"):
    xmpp.MainWindow._handle(w, "msg", {"from": frm, "nick": "Ali",
                                       "body": body, "mid": mid})


def _o_w(hist=None, jid="a@b"):
    """[2O] LIVE teslim + MAM merge üretim yollarını süren Tk'sız çift.

    _db_store_msg monkeypatch gerektirir; _append Tk'sız _Row üretir.
    """
    w = _win(hist, jid=jid)
    w.active = jid
    w._msg_ids = {}
    w._notify_enabled = False
    w._sound_enabled = False
    w._show_toast = lambda *a, **k: None
    w._send_read_receipts = False
    w._send_typing_notif = False
    w._typing_send_id = None
    w._disappearing_ttl = {}
    w._ttl_deadlines = {}
    w._reactions = {}
    w._my_reactions = {}
    w._reply_map = {}
    w._mam_aliases = {}                # [2O] registry (üretim __init__ gibi)
    w._bubble_widgets = []

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
    w._render_history_entry = lambda e: xmpp.MainWindow._render_history_entry(w, e)
    w.bot = types.SimpleNamespace(
        send_marker=lambda *a, **k: None, send_reaction=_Cap(),
        fetch_mam=lambda *a, **k: None)
    return w


def _summary(w, jid="a@b"):
    return [(e[7], e[1], bool(e[2])) for e in w.chats.get(jid, [])]


# ── A) MAM S/raw-R → LIVE R: TEK satır, canonical S kalır ────────────────────
def test_mam_raw_alias_suppresses_live_replay(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w()
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")])
    assert _summary(w) == [("S", "hello", False)]      # 2N: canonical S
    _live(w, "hello", "R")                     # LIVE replay (raw id)
    assert _summary(w) == [("S", "hello", False)]      # TEK satır; S kalır
    assert not any(e[7] == "R" for e in w.chats["a@b"])


# ── C) GÜVENLİK TABANI: alias + FARKLI gövde → iki satır ─────────────────────
def test_alias_with_different_body_materializes(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w()
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")])
    _live(w, "DIFFERENT", "R")                 # LIVE _store: append (sona)
    assert _summary(w) == [("S", "hello", False), ("R", "DIFFERENT", False)]
    assert len(w.chats["a@b"]) == 2


# ── B) MAM S → LIVE S aynı gövde/yön: TEK satır ──────────────────────────────
def test_exact_live_match_suppressed(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w()
    _page(w, [_mam_msg("hello", mid="S")])
    _live(w, "hello", "S")
    assert _summary(w) == [("S", "hello", False)]
    assert len(w.chats["a@b"]) == 1


# ── D) aynı mid/gövde + TERS yön → iki satır ─────────────────────────────────
def test_opposite_direction_not_suppressed(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(hist=[("Ben", "hello", True, "09:00", "me", "", False,
                    "M", "", 1)])             # outgoing satır (is_me True)
    _live(w, "hello", "M")                    # gelen yön — yön farklı
    assert _summary(w) == [("M", "hello", True), ("M", "hello", False)]
    assert len(w.chats["a@b"]) == 2


# ── E) aynı alias iki JID'de: çapraz bulaşma yok ─────────────────────────────
def test_same_alias_two_jids_isolated(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    wa = _o_w(jid="a@x")
    wb = _o_w(jid="b@x")
    _page(wa, [_mam_msg("hello", mid="S", raw_id="R")], jid="a@x")
    assert wa._mam_aliases["a@x"]["R"] == ("S", "hello", False)
    assert "b@x" not in wb._mam_aliases       # diğer çiftte kova yok
    _live(wb, "hello", "R", frm="b@x")        # b@x'te alias YOK → materialize
    assert _summary(wb, "b@x") == [("R", "hello", False)]
    # ve a@x'in alias'ı b@x'i bastıramaz
    assert _summary(wa, "a@x") == [("S", "hello", False)]


# ── F) active clear: yalnız o JID'in alias kovası gider ──────────────────────
def test_clear_active_removes_only_that_jid_aliases(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(jid="a@x")
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")], jid="a@x")
    _page(w, [_mam_msg("hello", mid="T", raw_id="U")], jid="b@x")
    assert set(w._mam_aliases) == {"a@x", "b@x"}
    w.active = "a@x"
    w.chats = {"a@x": [], "b@x": w.chats["b@x"]}
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert "a@x" not in w._mam_aliases
    assert w._mam_aliases["b@x"]["U"] == ("T", "hello", False)


# ── G) /clear (gerçek komut) aktif JID alias'larını temizler ─────────────────
def test_slash_clear_removes_active_jid_aliases(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(jid="a@x")
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")], jid="a@x")
    _page(w, [_mam_msg("hello", mid="T", raw_id="U")], jid="b@x")
    w.active = "a@x"
    xmpp.MainWindow._handle_bot_command(w, "/clear")   # GERÇEK komut yolu
    assert "a@x" not in w._mam_aliases
    assert w._mam_aliases["b@x"]["U"] == ("T", "hello", False)


# ── H) clear-all: registry tamamen boşalır ───────────────────────────────────
def test_clear_all_clears_registry(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_all", _Cap())
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(jid="a@x")
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")], jid="a@x")
    _page(w, [_mam_msg("hello", mid="T", raw_id="U")], jid="b@x")
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_all_history(w) is True
    assert w._mam_aliases == {}


# ── I) TTL temizliği: kanonik mid'e işaret eden aliaslar unutulur ────────────
def test_ttl_expiry_forgets_aliases_of_expired_mid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(hist=[("Ali", "hello", False, "09:00", "them", "", False,
                    "S", "", 1)], jid="a@x")
    xmpp.MainWindow._mam_alias_register(w, "a@x", "R", "S", "hello", False)
    assert ("R", ("S", "hello", False)) in w._mam_aliases["a@x"].items()
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        xmpp, "time", types.SimpleNamespace(monotonic=lambda: clock["now"]))
    # TTL vadesi dolmuş: 2K mezar taşı render'ı alias'ları da unutur
    w._ttl_deadlines = {("a@x", 1): clock["now"] - 1.0}
    xmpp.MainWindow._load_chat(w, "a@x")
    assert "R" not in w._mam_aliases.get("a@x", {})


# ── J) bayat alias clear sonrası yeni mesajı bastıramaz ──────────────────────
def test_stale_alias_cannot_suppress_post_clear_message(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(jid="a@x")
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")], jid="a@x")
    w.active = "a@x"
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True   # registry gitti
    _live(w, "hello", "R", frm="a@x")          # post-clear LIVE R
    assert _summary(w, "a@x") == [("R", "hello", False)]      # materialize


# ── K) JID başına 256 alias sınırı: deterministik en-eski FIFO ───────────────
def test_per_jid_alias_cap_fifo(monkeypatch):
    cap = xmpp.MainWindow._MAM_ALIAS_CAP_PER_JID
    w = _o_w(jid="a@x")
    for i in range(cap + 5):                   # 261 kayıt
        xmpp.MainWindow._mam_alias_register(w, "a@x", f"r{i}", f"S{i}",
                                            "b", False)
    bucket = w._mam_aliases["a@x"]
    assert len(bucket) == cap                  # 256
    assert "r0" not in bucket and "r4" not in bucket   # en eski 5 düştü
    assert "r5" in bucket                      # hayatta kalan ilk
    assert "r260" in bucket                    # en yeni
    assert bucket["r260"] == ("S260", "b", False)


# ── L) 64 JID sınırı: 65. kova en eskiyi düşürür ─────────────────────────────
def test_jid_bucket_cap_fifo(monkeypatch):
    cap = xmpp.MainWindow._MAM_ALIAS_MAX_JIDS
    w = _o_w(jid="j0@x")
    for i in range(cap + 1):                   # 65 kova
        xmpp.MainWindow._mam_alias_register(w, f"j{i}@x", "R", "S", "b",
                                            False)
    assert len(w._mam_aliases) == cap          # 64
    assert "j0@x" not in w._mam_aliases        # en eski kova düştü
    assert "j1@x" in w._mam_aliases            # hayatta kalan ilk
    assert f"j{cap}@x" in w._mam_aliases       # en yeni (j65@x)


# ── M) 2N MAM dedupe regresyonu yeşil kalır (suite koşusu; burada hızlı
#      çekirdek iddia: MAM duplicate hâlâ düşüyor) ────────────────────────────
def test_2n_mam_dedupe_core_still_green(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(hist=[("Ali", "hello", False, "09:00", "them", "", False,
                    "M", "", 1)])
    _page(w, [_mam_msg("hello", mid="M")])     # 2N: aynı mid+body+yön
    assert _summary(w) == [("M", "hello", False)]


# ── N) archive_id yalnız imleç: registry'ye ASLA girmez ──────────────────────
def test_archive_id_never_enters_registry(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w()
    _page(w, [_mam_msg("hello", mid="S", raw_id="R", archive_id="ARCH")])
    assert w._mam_oldest["a@b"] == "ARCH"      # imleç
    assert set(w._mam_aliases["a@b"]) == {"R"}  # yalnız raw_id anahtarı
    assert "ARCH" not in w._mam_aliases["a@b"]
    assert not any("ARCH" in str(v) for v in w._mam_aliases["a@b"].values())


# ── O) bayat MAM token: alias yaratmaz, geçmiş değişmez ──────────────────────
def test_stale_token_creates_no_aliases(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w(hist=[("Ali", "eski", False, "09:00", "them", "", False,
                    "M", "", 1)])
    w._mam_gen = {"a@b": 1}
    _page(w, [_mam_msg("yeni", mid="S2", raw_id="R2")], token=0)  # bayat
    assert w._mam_aliases == {}                # kayıt YOK
    assert _summary(w) == [("M", "eski", False)]        # geçmiş değişmedi


# ── P) _msg_inst_seq monotonik kalır (bastırma sayaç harcamaz) ───────────────
def test_msg_inst_seq_monotonic_with_suppression(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w()
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")])   # 1 kabul → seq 1
    assert w._msg_inst_seq == 1
    _live(w, "hello", "R")                     # bastırıldı → sayaç harcanmaz
    assert w._msg_inst_seq == 1
    _live(w, "DIFFERENT", "R")                 # materialize → seq 2
    assert w._msg_inst_seq == 2
    assert _summary(w) == [("S", "hello", False), ("R", "DIFFERENT", False)]


# ── Q) self.chats tam 10 eleman kalır ────────────────────────────────────────
def test_chat_tuple_still_ten_elements(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _o_w()
    _page(w, [_mam_msg("hello", mid="S", raw_id="R")])
    _live(w, "DIFFERENT", "R")
    assert all(len(e) == 10 for e in w.chats["a@b"])
    assert _summary(w) == [("S", "hello", False), ("R", "DIFFERENT", False)]
