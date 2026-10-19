"""RESOURCE HARDENING 2M: tepki/yanıt sunum kimliği kapsamlandırma.

Kanıt: `_reactions[mid]`, `_my_reactions[mid]`, `_reply_map[mid]` sohbetler
ARASI globaldi — A sohbetinin tepkisi/önizlemesi B sohbetinin aynı-mid
mesajında görünüyordu; DB zaten (jid, mid) kapsamlıydı (bellek/kalıcı
ayrışması). [2M] ile:

- tepkiler (jid, mid) kapsamlıdır; Policy C: (jid, mid) durumu o JID'in
  aktif satırlarının TAMAMINA uygulanır (canlı ve reload her zaman aynı;
  wire belirsizliği tutarlı sergilenir, hiçbir olay düşmez);
- yanıt önizleme sahipliği (jid, örnek-kimlik)'tir: güncel girişlerde uid,
  eski girişlerde mid; global mid-only fallback yoktur;
- peer hedef çözümü per-JID ters tarama kalır (son eşleşen kazanır —
  belgelenmiş deterministik wire belirsizlik politikası).
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_2i_ttl_expiry import _Row  # noqa: E402
from test_history_window_bounds import _Cap, _mam_msgs, _win  # noqa: E402

import xmpp  # noqa: E402


def _entry(mid="", uid=0, body="gövde", is_me=False):
    return ("Ali" if not is_me else "Ben", body, is_me, "10:00",
            "me" if is_me else "them", "", False, mid, "", uid)


def _reaction_mw(active="a@x", rows=None):
    """[2M] msg_reactions/_toggle_reaction üretim yolları için çift."""
    w = object.__new__(xmpp.MainWindow)
    w.active = active
    w.jid = "ben@example.com"
    w.rooms = []
    w.my_nick = {}
    w.chats = {}
    w._reactions = {}
    w._my_reactions = {}
    w._bubble_widgets = rows or []
    w._render_reactions = _Cap()
    w._scroll_bottom = lambda: None
    w.bot = types.SimpleNamespace(send_reaction=_Cap())
    return w


def _render_mw(hist=None, jid="a@x"):
    """[2M] render + tepki haritası yollarını süren Tk'sız çift (2I deseni)."""
    w = _win(hist, jid=jid)
    w._reactions = {}
    w._my_reactions = {}
    w._reply_map = {}
    w._ttl_deadlines = {}
    w._bubble_widgets = []
    w._disappearing_ttl = {jid: 0}
    w.bot = types.SimpleNamespace(
        send_marker=lambda *a, **k: None, fetch_mam=lambda *a, **k: None,
        send_reaction=_Cap())

    def _fake_clear():
        w._bubble_widgets.clear()

    w._clear_chat = _fake_clear

    def _fake_append(body, tag, sender="", is_me=False, time_str=None,
                     oob="", encrypted=False, mid="", reply_to=None,
                     local_path=""):
        r = _Row(mid, body)
        r._reply = reply_to
        w._bubble_widgets.append(r)
        if mid:
            # üretim _append'in [2M] davranışı: her yeni satır mevcut
            # (jid, mid) durumunu taşır (Policy C reload tutarlılığı)
            w._render_reactions(
                r, w._reactions.get((w.active, mid), {}))
        return r

    w._append = _fake_append
    w._render_reactions = _Cap()
    w._render_history_entry = lambda e: xmpp.MainWindow._render_history_entry(w, e)
    return w


def _react_event(frm, target_id, emojis, nick="Ali"):
    return {"from": frm, "target_id": target_id, "nick": nick,
            "emojis": emojis}


# ══ REACTIONS ═════════════════════════════════════════════════════════════════

# ── M1) Çapraz-sohbet gelen tepki: bulaşma YOK ───────────────────────────────
def test_cross_chat_incoming_reaction_isolated(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw(active="a@x", rows=[_Row("X", "A gövdesi")])
    w.chats = {"a@x": [_entry("X", 1)], "b@x": [_entry("X", 2, "B gövdesi")]}
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))
    # yalnız (a@x, X) oluşur; global mid anahtarı YOK
    assert w._reactions == {("a@x", "X"): {"👍": ["Ali"]}}
    assert ("b@x", "X") not in w._reactions
    assert "X" not in dict(w._reactions)   # mid-only eski anahtar yok
    # B'yi aç/reload et: tepki sızmaz (b@x haritası boş)
    w2 = _render_mw(hist=[_entry("X", 2, "B gövdesi")], jid="b@x")
    w2._reactions = w._reactions            # aynı harita (üretim tek harita)
    xmpp.MainWindow._load_chat(w2, "b@x")
    calls = [c[0][1] for c in w2._render_reactions.calls]
    assert all(r == {} for r in calls)      # B satırlarında sıfır çip


# ── M2) Ters çapraz-sohbet: B'nin tepkisi A'ya sızmaz ────────────────────────
def test_reverse_cross_chat_reaction_isolated(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw(active="b@x")
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("b@x", "X", ["❤"]))
    assert w._reactions == {("b@x", "X"): {"❤": ["Ali"]}}
    assert ("a@x", "X") not in w._reactions


# ── M3) Kendi tepkim çapraz-sohbet: yalnız hedef JID ─────────────────────────
def test_own_reaction_cross_chat_scoped(monkeypatch):
    db_clear, db_save = _Cap(), _Cap()
    monkeypatch.setattr(xmpp, "_db_clear_my_reactions", db_clear)
    monkeypatch.setattr(xmpp, "_db_save_reaction", db_save)
    w = _reaction_mw(active="a@x")
    xmpp.MainWindow._toggle_reaction(w, "X", "👍")
    assert w._my_reactions == {("a@x", "X"): {"👍"}}
    assert ("b@x", "X") not in w._my_reactions
    assert w._reactions[("a@x", "X")] == {"👍": ["Ben"]}
    # DB çağrısı A-kapsamlı kalır (2J.a ile uyum)
    assert db_clear.calls[0][0] == ("a@x", "X")
    assert db_save.calls[0][0] == ("a@x", "X", "👍", "Ben", True)


# ── M4) Aynı-sohbet duplicate-mid: Policy C — TÜM satırlar aynı sunum ────────
def test_same_chat_duplicate_mid_reaction_policy_c(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    rows = [_Row("X", "ilk"), _Row("X", "ikinci")]
    w = _reaction_mw(active="a@x", rows=rows)
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))
    # canlı: iki satıra da aynı durum render edildi (ilk-satır-only YOK)
    assert [c[0][0] for c in w._render_reactions.calls] == rows
    assert all(c[0][1] == {"👍": ["Ali"]}
               for c in w._render_reactions.calls)


# ── M5) Aynı-sohbet kendi toggle'ı + reload yakınsaması ──────────────────────
def test_same_chat_own_toggle_and_reload_converge(monkeypatch):
    db_clear, db_save = _Cap(), _Cap()
    monkeypatch.setattr(xmpp, "_db_clear_my_reactions", db_clear)
    monkeypatch.setattr(xmpp, "_db_save_reaction", db_save)
    w = _render_mw(hist=[_entry("X", 1, "ilk"), _entry("X", 2, "ikinci")],
                   jid="a@x")
    w.active = "a@x"
    xmpp.MainWindow._toggle_reaction(w, "X", "👍")
    assert w._my_reactions == {("a@x", "X"): {"👍"}}
    # toggle Policy C: canlı satırlar — henüz render yok; reload:
    xmpp.MainWindow._load_chat(w, "a@x")
    calls = w._render_reactions.calls
    assert len(calls) == 2                             # her satır için bir
    assert all(c[0][1] == {"👍": ["Ben"]} for c in calls)  # AYNI durum
    # reload canlı durumu birebir taşır (ilk-satır-only tutarsızlığı yok)


# ── M6) Tepki cap'i: 500 (jid, mid) kapsamlı anahtar ─────────────────────────
def test_reaction_cap_scoped_keys(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw(active="a@x")
    for i in range(501):
        frm = f"j{i % 3}@x"                       # birden çok sohbet
        xmpp.MainWindow._handle(w, "msg_reactions",
                                _react_event(frm, f"m{i}", ["👍"]))
    assert len(w._reactions) <= 500               # cap korunur
    assert all(isinstance(k, tuple) and len(k) == 2 for k in w._reactions)


# ══ REPLIES ═══════════════════════════════════════════════════════════════════

# ── M7) Çapraz-sohbet önizleme: A quote A, B quote B ─────────────────────────
def test_reply_cross_chat_independent(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1, "A gövdesi")],
               "b@x": [_entry("X", 2, "B gövdesi")]}
    xmpp.MainWindow._remember_reply(
        w, "a@x", 1, {"id": "rA", "sender": "SA", "body": "alıntı A"})
    xmpp.MainWindow._remember_reply(
        w, "b@x", 2, {"id": "rB", "sender": "SB", "body": "alıntı B"})
    w.active = "a@x"
    xmpp.MainWindow._load_chat(w, "a@x")
    assert w._bubble_widgets[0]._reply["body"] == "alıntı A"
    w.active = "b@x"
    xmpp.MainWindow._load_chat(w, "b@x")
    assert w._bubble_widgets[0]._reply["body"] == "alıntı B"


# ── M8) Aynı-sohbet duplicate-mid önizleme: uid1 ≠ uid2 ──────────────────────
def test_reply_same_chat_duplicates_independent(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1, "birinci"), _entry("X", 2, "ikinci")]}
    xmpp.MainWindow._remember_reply(
        w, "a@x", 1, {"id": "r1", "sender": "S", "body": "alıntı ONE"})
    xmpp.MainWindow._remember_reply(
        w, "a@x", 2, {"id": "r2", "sender": "S", "body": "alıntı TWO"})
    xmpp.MainWindow._load_chat(w, "a@x")
    assert [r._reply["body"] for r in w._bubble_widgets] == \
        ["alıntı ONE", "alıntı TWO"]
    # reload ayrılığı korur
    xmpp.MainWindow._load_chat(w, "a@x")
    assert [r._reply["body"] for r in w._bubble_widgets] == \
        ["alıntı ONE", "alıntı TWO"]


# ── M9) Peer hedef: per-JID ters tarama — SON eşleşen kazanır ────────────────
def test_peer_reply_target_last_match_policy(monkeypatch):
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1, "eski gövde"),
                       _entry("X", 2, "yeni gövde")]}
    info = xmpp.MainWindow._resolve_reply(w, {"id": "X", "sender": "",
                                              "body": ""}, "a@x")
    assert info["body"] == "yeni gövde"       # belgelenmiş son-eşleşen
    assert info["sender"] == "Ali"


# ── M10) Peer hedef çapraz-sohbet güvenliği ──────────────────────────────────
def test_peer_reply_cross_chat_never_reads_other_cache(monkeypatch):
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("Y", 1, "Y gövdesi")]}   # a@x'te X YOK
    xmpp.MainWindow._remember_reply(
        w, "b@x", "X", {"id": "X", "sender": "SB", "body": "B'nin alıntısı"})
    info = xmpp.MainWindow._resolve_reply(w, {"id": "X", "sender": "",
                                              "body": ""}, "a@x")
    assert info["body"] in (None, "")         # b@x önizlemesine düşülmedi
    assert info["sender"] == ""


# ── M11) Eski (UID'siz) giriş: (jid, mid) fallback çalışır ───────────────────
def test_legacy_reply_mid_fallback(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    # 9'luk eski giriş (uid yok, mid "m-9")
    w.chats = {"a@x": [("Ali", "eski", False, "10:00", "them", "", False,
                        "m-9", "")]}
    xmpp.MainWindow._remember_reply(
        w, "a@x", "m-9", {"id": "r9", "sender": "S", "body": "eski alıntı"})
    xmpp.MainWindow._load_chat(w, "a@x")
    assert w._bubble_widgets[0]._reply["body"] == "eski alıntı"


# ── M12) Taze MAM girişleri: uid'li güvenli; DB'ye uid gitmez ────────────────
def test_mam_uid_safety(monkeypatch):
    db_store = _Cap()
    monkeypatch.setattr(xmpp, "_db_store_msg", db_store)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("eski", 0, "eski")]}
    xmpp.MainWindow._load_chat(w, "a@x")
    xmpp.MainWindow._handle(w, "mam_results",
                            {"jid": "a@x", "messages": _mam_msgs(50, "f")})
    fresh = w.chats["a@x"][:50]
    assert all(len(e) == 10 and e[9] for e in fresh)   # uid'li, çökmez
    xmpp.MainWindow._load_chat(w, "a@x")               # çökmez, normal çizilir
    assert len(w._bubble_widgets) == 51   # 1 eski + 50 mam (< K)
    # DB'ye uid YAZILMAZ: bu turda mam merge + render yolları DB yazmaz
    assert db_store.calls == []
    # tepki peer durumu (jid, mid) tabanlıdır — taze MAM için rastgele yok
    assert ("a@x", "f0") not in w._reactions


# ══ ADVERSARIAL ═══════════════════════════════════════════════════════════════

# ── A1) 10 farklı JID'de aynı mid ────────────────────────────────────────────
def test_same_mid_across_ten_jids(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw()
    for i in range(10):
        frm = f"j{i}@x"
        xmpp.MainWindow._handle(w, "msg_reactions",
                                _react_event(frm, "X", [f"e{i}"]))
    assert len(w._reactions) == 10
    for i in range(10):
        assert w._reactions[(f"j{i}@x", "X")] == {f"e{i}": ["Ali"]}


# ── A2) Tek JID'de 10× aynı mid — Policy C hepsine uygulanır ─────────────────
def test_same_mid_ten_times_in_one_jid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    rows = [_Row("X", f"s{i}") for i in range(10)]
    w = _reaction_mw(active="a@x", rows=rows)
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))
    assert [c[0][0] for c in w._render_reactions.calls] == rows


# ── A3) Sohbetler arasında sıralı tepki olayları bağımsız akar ───────────────
def test_alternating_reaction_events(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw()
    sets = {"a@x": [], "b@x": []}
    for i in range(6):
        frm = "a@x" if i % 2 == 0 else "b@x"
        # Her tepki olayı gönderenin TAM kümesidir (XEP-0444)
        sets[frm].append(f"e{i}")
        xmpp.MainWindow._handle(w, "msg_reactions",
                                _react_event(frm, "X", list(sets[frm])))
    assert w._reactions[("a@x", "X")] == {"e0": ["Ali"], "e2": ["Ali"],
                                          "e4": ["Ali"]}
    assert w._reactions[("b@x", "X")] == {"e1": ["Ali"], "e3": ["Ali"],
                                          "e5": ["Ali"]}


# ── A4) Kendi toggle + peer echo: aynı (jid, mid) altında birleşir ───────────
def test_own_toggle_then_peer_echo(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw(active="a@x")
    xmpp.MainWindow._toggle_reaction(w, "X", "👍")
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))  # peer echo
    store = w._reactions[("a@x", "X")]
    assert store["👍"] == ["Ben", "Ali"]      # iki gönderici aynı durumda
    assert w._my_reactions[("a@x", "X")] == {"👍"}   # kendi kümem korunur


# ── A5) render → canlı olay → tekrar render: tutarlı ─────────────────────────
def test_render_live_event_rerender_consistent(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1, "gövde")]}
    w.active = "a@x"
    xmpp.MainWindow._load_chat(w, "a@x")      # 1. render: çipsiz
    assert w._render_reactions.calls[-1][0][1] == {}
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))  # canlı
    assert len(w._render_reactions.calls) >= 2  # canlı refresh geldi
    xmpp.MainWindow._load_chat(w, "a@x")      # tekrar render
    assert w._render_reactions.calls[-1][0][1] == {"👍": ["Ali"]}


# ── A6) 800+ önizleme: cap evictionsıralı, çapraz-sohbet karışmaz ───────────
def test_reply_cache_eviction_under_load(monkeypatch):
    w = _render_mw(jid="a@x")
    for i in range(850):
        xmpp.MainWindow._remember_reply(
            w, f"j{i % 4}@x", f"m{i}",
            {"id": f"r{i}", "sender": "S", "body": f"b{i}"})
    assert len(w._reply_map) <= 800
    # en eski (jid, m0..) düşmüştür; en yeniler durur
    assert ("j1@x", "m849") in w._reply_map
    assert ("j0@x", "m0") not in w._reply_map


# ── A7) Anahtar-tip ayrımı: "1" (mid) ile 1 (uid) karışmaz ───────────────────
def test_key_type_separation_string_mid_vs_int_uid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    xmpp.MainWindow._remember_reply(
        w, "a@x", "1", {"id": "r", "sender": "S", "body": "mid-anahtarlı"})
    xmpp.MainWindow._remember_reply(
        w, "a@x", 1, {"id": "r", "sender": "S", "body": "uid-anahtarlı"})
    assert len(w._reply_map) == 2             # tip-duyarlı tuple anahtarlar
    assert w._reply_map[("a@x", "1")]["body"] == "mid-anahtarlı"
    assert w._reply_map[("a@x", 1)]["body"] == "uid-anahtarlı"


# ── A8) Boş mid: production çökmez; çip/bulaşma üretmez ──────────────────────
def test_empty_mid_safe(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw(active="a@x")
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "", ["👍"]))
    assert ("a@x", "") in w._reactions        # kayıt davranışı değişmedi
    # render: boş mid için satıra tepki/önizleme işlenmez (mevcut guard)
    w2 = _render_mw(jid="a@x")
    w2.chats = {"a@x": [("Ali", "gövde", False, "10:00", "them", "", False,
                         "", "")]}
    xmpp.MainWindow._load_chat(w2, "a@x")     # çökmez
    assert all(c[0][0]._mid != "" for c in w2._render_reactions.calls)


# ── B1) clear-active: A'nın TÜM sunum durumu gider, B korunur ────────────────
def test_clear_active_removes_all_presentation_state_for_jid(monkeypatch):
    """[2M-B1] Sunum durumu tanımladığı geçmişten uzun yaşamaz.

    A: mid X — peer tepki + own tepki + önizleme; B: mid Y — aynı üçlü.
    _clear_active_history(A) → A'nın üç haritadaki anahtarları gider,
    B'ninkiler birebir durur. Sonra A'da ESKİ mid X ile YENİ mantıksal
    mesaj → render: sıfır bayat çip, sıfır own state, sıfır önizleme.
    (Pre-fix: A anahtarları haritada kalırdı → bayat çipler yapışırdı.)
    """
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_clear_my_reactions", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1)], "b@x": [_entry("Y", 2, "B gövdesi")]}
    w.active = "a@x"
    # A üçlüsü: peer tepki + own tepki + önizleme
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))
    xmpp.MainWindow._toggle_reaction(w, "X", "👍")
    xmpp.MainWindow._remember_reply(
        w, "a@x", 1, {"id": "rA", "sender": "S", "body": "A alıntısı"})
    # B üçlüsü
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("b@x", "Y", ["❤"]))
    xmpp.MainWindow._remember_reply(
        w, "b@x", 2, {"id": "rB", "sender": "S", "body": "B alıntısı"})
    w._my_reactions.setdefault(("b@x", "Y"), {"❤"})
    # ön koşul: A ve B anahtarlarının hepsi mevcut
    assert ("a@x", "X") in w._reactions and ("a@x", "X") in w._my_reactions
    assert ("a@x", 1) in w._reply_map
    assert ("b@x", "Y") in w._reactions and ("b@x", "Y") in w._my_reactions
    assert ("b@x", 2) in w._reply_map
    # clear A (üretim yolu)
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert not any(k[0] == "a@x" for k in w._reactions)
    assert not any(k[0] == "a@x" for k in w._my_reactions)
    assert not any(k[0] == "a@x" for k in w._reply_map)
    # B birebir korunur
    assert w._reactions[("b@x", "Y")] == {"❤": ["Ali"]}
    assert w._my_reactions[("b@x", "Y")] == {"❤"}
    assert w._reply_map[("b@x", 2)]["body"] == "B alıntısı"
    # A'da ESKİ mid X ile YENİ mantıksal mesaj: sıfır bayat sunum
    w.chats["a@x"] = [_entry("X", 3, "yeni gövde", is_me=True)]
    w.active = "a@x"
    xmpp.MainWindow._load_chat(w, "a@x")
    assert len(w._render_reactions.calls) == 1
    assert w._render_reactions.calls[-1][0][1] == {}   # sıfır bayat çip
    rows = w._bubble_widgets
    assert len(rows) == 1
    assert rows[0]._reply is None                      # sıfır bayat önizleme
    assert not any(k[0] == "a@x" for k in w._my_reactions)  # own state yok


# ══ [2M-B1] CLEAR-LIFECYCLE ek regresyonlar ═══════════════════════════════════

# ── I) GERÇEK /clear üretim komutu aynı garantiyi verir ──────────────────────
def test_slash_clear_removes_presentation_state(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_clear_my_reactions", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1)], "b@x": [_entry("Y", 2, "B gövdesi")]}
    w.active = "a@x"
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("b@x", "Y", ["❤"]))
    xmpp.MainWindow._remember_reply(
        w, "a@x", 1, {"id": "rA", "sender": "S", "body": "A alıntısı"})
    xmpp.MainWindow._remember_reply(
        w, "b@x", 2, {"id": "rB", "sender": "S", "body": "B alıntısı"})
    xmpp.MainWindow._handle_bot_command(w, "/clear")   # GERÇEK komut yolu
    assert not any(k[0] == "a@x" for k in w._reactions)
    assert not any(k[0] == "a@x" for k in w._my_reactions)
    assert not any(k[0] == "a@x" for k in w._reply_map)
    # B korunur; A'da eski mid X ile yeni mesaj bayat sunum almaz
    assert w._reactions[("b@x", "Y")] == {"❤": ["Ali"]}
    assert w._reply_map[("b@x", 2)]["body"] == "B alıntısı"
    w.chats["a@x"] = [_entry("X", 3, "yeni gövde", is_me=True)]
    xmpp.MainWindow._load_chat(w, "a@x")
    assert w._render_reactions.calls[-1][0][1] == {}
    assert w._bubble_widgets[0]._reply is None


# ── J) clear-all: üç harita da boşalır; yeni mesaj bayat almaz ───────────────
def test_clear_all_empties_all_presentation_maps(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_all", _Cap())
    monkeypatch.setattr(xmpp, "_db_clear_my_reactions", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1)], "b@x": [_entry("Y", 2)],
               "c@x": [_entry("Z", 3)]}
    w.active = "a@x"
    for frm, mid in (("a@x", "X"), ("b@x", "Y"), ("c@x", "Z")):
        xmpp.MainWindow._handle(w, "msg_reactions",
                                _react_event(frm, mid, ["👍"]))
    xmpp.MainWindow._remember_reply(
        w, "a@x", 1, {"id": "r1", "sender": "S", "body": "alıntı 1"})
    xmpp.MainWindow._remember_reply(
        w, "b@x", 2, {"id": "r2", "sender": "S", "body": "alıntı 2"})
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_all_history(w) is True
    assert w._reactions == {}
    assert w._my_reactions == {}
    assert w._reply_map == {}
    # eski mid'lerle yeni mesajlar: bayat sunum YOK
    w.chats = {"a@x": [_entry("X", 9, "yeni", is_me=True)]}
    xmpp.MainWindow._load_chat(w, "a@x")
    assert w._render_reactions.calls[-1][0][1] == {}
    assert w._bubble_widgets[0]._reply is None


# ── K) Eski (UID'siz) giriş: (jid, mid) bayat önizleme yapışamaz ─────────────
def test_legacy_reply_stale_state_cannot_reattach(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [("Ali", "eski", False, "10:00", "them", "", False,
                        "X", "")]}                      # 9'luk legacy, mid X
    xmpp.MainWindow._remember_reply(
        w, "a@x", "X", {"id": "r", "sender": "S", "body": "ESKİ alıntı"})
    assert ("a@x", "X") in w._reply_map
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert ("a@x", "X") not in w._reply_map             # legacy anahtar gitti
    # yeni legacy-benzeri giriş AYNI mid X ile: ESKİ önizleme yapışamaz
    w.chats["a@x"] = [("Ali", "yeni", False, "11:00", "them", "", False,
                       "X", "")]
    w.active = "a@x"
    xmpp.MainWindow._load_chat(w, "a@x")
    assert w._bubble_widgets[0]._reply is None


# ── L) UID'li reply anahtarları da JID sahipliğiyle temizlenir ───────────────
def test_uid_reply_cache_cleanup_by_jid(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    w.chats = {"a@x": [_entry("X", 1)], "b@x": [_entry("Y", 2)]}
    xmpp.MainWindow._remember_reply(
        w, "a@x", 1, {"id": "r1", "sender": "S", "body": "A-uid"})
    xmpp.MainWindow._remember_reply(
        w, "b@x", 2, {"id": "r2", "sender": "S", "body": "B-uid"})
    w._load_chat = _Cap()
    xmpp.MainWindow._clear_active_history(w)
    assert ("a@x", 1) not in w._reply_map     # uid yeniden kullanılamasa da
    assert w._reply_map[("b@x", 2)]["body"] == "B-uid"   # yaşam döngüsü eşit


# ── M) Reaction cap/order non-regression: clear sonrası cap devam eder ──────
def test_reaction_cap_continues_after_clear(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    w = _reaction_mw(active="a@x")
    for i in range(501):                       # cap dolduruldu
        xmpp.MainWindow._handle(w, "msg_reactions",
                                _react_event(f"j{i % 3}@x", f"m{i}", ["👍"]))
    assert len(w._reactions) <= 500
    survivors = list(w._reactions.keys())      # kalanlar (FIFO sırası)
    w.active = "j0@x"
    w.chats = {"j0@x": []}
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert not any(k[0] == "j0@x" for k in w._reactions)
    others = [k for k in survivors if k[0] != "j0@x"]
    assert all(k in w._reactions for k in others)   # kalanlar aynı sırada
    assert list(w._reactions.keys()) == [k for k in survivors
                                         if k[0] != "j0@x"]
    # sonraki eklemeler cap'i sürdürür
    for i in range(520, 540):
        xmpp.MainWindow._handle(w, "msg_reactions",
                                _react_event(f"n{i}@x", f"m{i}", ["👍"]))
    assert len(w._reactions) <= 500


# ── N) Reply cap non-regression: clear sonrası cap 800 devam eder ────────────
def test_reply_cap_continues_after_clear(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    w = _render_mw(jid="a@x")
    for i in range(820):
        xmpp.MainWindow._remember_reply(
            w, f"j{i % 4}@x", f"m{i}",
            {"id": f"r{i}", "sender": "S", "body": "b"})
    assert len(w._reply_map) <= 800
    w.active = "j0@x"
    w.chats = {"j0@x": []}
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert not any(k[0] == "j0@x" for k in w._reply_map)
    for i in range(830, 860):
        xmpp.MainWindow._remember_reply(
            w, f"n{i}@x", f"m{i}",
            {"id": f"r{i}", "sender": "S", "body": "b"})
    assert len(w._reply_map) <= 800            # cap sürdürülür


# ── O+P) Policy C + çapraz-sohbet non-regression (clear yaşam döngüsüyle) ────
def test_policy_c_and_cross_chat_after_clear_lifecycle(monkeypatch):
    monkeypatch.setattr(xmpp, "_db_clear_chat", _Cap())
    monkeypatch.setattr(xmpp, "_db_save_reaction", lambda *a: None)
    monkeypatch.setattr(xmpp, "_db_store_msg", lambda *a, **k: None)
    rows = [_Row("X", "satır-1"), _Row("X", "satır-2")]
    w = _reaction_mw(active="a@x", rows=rows)
    w.chats = {"a@x": [_entry("X", 1)], "b@x": [_entry("X", 2, "B")]}

    # B: mid X tepki — A'dan bağımsız
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("b@x", "X", ["❤"]))
    # A: mid X tepki — Policy C (iki satır)
    xmpp.MainWindow._handle(w, "msg_reactions",
                            _react_event("a@x", "X", ["👍"]))
    assert [c[0][0] for c in w._render_reactions.calls] == rows
    assert w._render_reactions.calls[-1][0][1] == {"👍": ["Ali"]}

    # clear A → B'nin tepki durumu durur (clear chats.pop'u kendi yapar)
    w._load_chat = _Cap()
    assert xmpp.MainWindow._clear_active_history(w) is True
    assert w._reactions[("b@x", "X")] == {"❤": ["Ali"]}
    # B'yi aç: mid X satırı hâlâ B'nin tepkisini gösterir
    wb = _render_mw(jid="b@x")
    wb.chats = {"b@x": [_entry("X", 2, "B")]}
    wb._reactions = w._reactions
    xmpp.MainWindow._load_chat(wb, "b@x")
    assert wb._render_reactions.calls[-1][0][1] == {"❤": ["Ali"]}

    # A'da ESKİ mid X yeniden: ne A'nın eski durumu ne B'ninki yapışır
    wa = _render_mw(jid="a@x")
    wa.chats = {"a@x": [_entry("X", 3, "yeni", is_me=True)]}
    wa._reactions = w._reactions
    wa._my_reactions = w._my_reactions
    wa._reply_map = getattr(w, "_reply_map", {})
    xmpp.MainWindow._load_chat(wa, "a@x")
    assert wa._render_reactions.calls[-1][0][1] == {}
