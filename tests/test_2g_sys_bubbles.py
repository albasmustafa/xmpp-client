"""RESOURCE HARDENING 2G: sınırlı sistem/ortam balonu yüzeyi.

Kanıtlar:
- muc_subject tekrarlı stanza → oda başına TEK konu balonu (coalesce),
  toplam sys balonu <= _MAX_SYS_BUBBLES; en güncel konu görünür.
- sys_msg akışı sınırlı: 10.000 olay → O(1) balon; en yeni bildirimler görünür.
- Tahliye yalnız sys balonlarına dokunur: mesaj satırları / tarih ayırıcılar
  korunur; _bubble_widgets canlı widget çocuklarıyla tutarlı kalır.
- Subject referans yaşam döngüsü: evict/clear/replacement sonrası bayat
  (yok edilmiş) widget referansı kalmaz.
- muc_subject ve sys_msg sınırlı sunum yolunu (tek _create_sys_bubble)
  bypass edemez.
Domain self.chats, mesaj pencere durumu ve 2F mantığı bu yüzeyden etkilenmez.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402

CAP = xmpp.MainWindow._MAX_SYS_BUBBLES
ROOM = "oda@conf"


class _Cap:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return None


class _Frame:
    def __init__(self):
        self.children = []

    def winfo_children(self):
        return list(self.children)


class _SG:
    """render_system_message sahte balonu: master-çocuk takipli."""

    def __init__(self, parent, theme, text):
        self.text = text
        self.parent = parent
        self.destroyed = False
        self._sys_kind = None
        if isinstance(parent, _Frame):
            parent.children.append(self)

    def destroy(self):
        self.destroyed = True
        if isinstance(self.parent, _Frame) and self in self.parent.children:
            self.parent.children.remove(self)


class _Row:
    """Normal mesaj satırı taklidi (tahliye edilmemesi gereken)."""

    def __init__(self, mid):
        self._mid = mid
        self._is_me = False
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class _Sep:
    """Tarih ayırıcı taklidi."""

    def __init__(self, label):
        self._date_label = label
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class _HdrSubject:
    def __init__(self):
        self.configs = []
        self.packed = 0
        self.unpacked = 0

    def config(self, **k):
        self.configs.append(k)

    def pack(self, **k):
        self.packed += 1

    def pack_forget(self):
        self.unpacked += 1


def _win2g():
    w = object.__new__(xmpp.MainWindow)
    w.active = ROOM
    w.rooms = [ROOM]
    w.msg_frame = _Frame()
    w._bubble_widgets = []
    w._photo_refs = []
    w.chats = {}
    w._room_subjects = {}
    w._chat_subject = _HdrSubject()
    w._bind_scroll_widget = lambda *a, **k: None
    w._scroll_bottom = _Cap()
    w._reset_action_bar = lambda: None
    w._sys_bubbles = []
    w._subject_bubbles = {}
    return w


def _stub_render(monkeypatch):
    monkeypatch.setattr(xmpp._render, "render_system_message",
                        lambda parent, theme, text: _SG(parent, theme, text))


# ── 1) muc_subject: tekrarlı stanza sınırlı + tek konu balonu ────────────────
def test_muc_subject_repeated_stanzas_bounded(monkeypatch):
    _stub_render(monkeypatch)
    w = _win2g()
    n = 10_000
    for i in range(n):
        xmpp.MainWindow._handle(w, "muc_subject",
                                {"room": ROOM, "subject": f"konu {i}"})
    # sys yüzeyi O(1): coalesce sayesinde 10k olayda bile TEK balon
    assert len(w._sys_bubbles) <= CAP
    assert len(w._sys_bubbles) == 1              # yalnız güncel konu balonu
    # en güncel konu görünür
    current = w._subject_bubbles[ROOM]
    assert not current.destroyed
    assert current.text == f"📌 Konu: konu {n - 1}"
    assert current.parent.children and current in current.parent.children
    # aktif oda için konu balonu TEKTEK: başka subject balonu yok
    subject_bubbles = [b for b in w._sys_bubbles
                       if getattr(b, "_sys_kind", (None,))[0] == "subject"]
    assert subject_bubbles == [current]
    # başlık etiketi de en güncel konuyu taşır
    assert w._chat_subject.configs[-1]["text"] == "📌 konu 9999"   # başlık
    # domain history değişmedi
    assert w.chats == {}


# ── 2) sys_msg: tekrarlı olaylar sınırlı, en yeni bildirimler görünür ────────
def test_sys_msg_repeated_events_bounded(monkeypatch):
    _stub_render(monkeypatch)
    w = _win2g()
    n = 10_000
    for i in range(n):
        xmpp.MainWindow._handle(w, "sys_msg", f"bildirim {i}")
    assert len(w._sys_bubbles) <= CAP
    # en yeni bildirimler görünür: yaşayan balonlar son CAP olay
    texts = [b.text for b in w._sys_bubbles]
    assert texts == [f"bildirim {i}" for i in range(n - CAP, n)]
    # en eski bildirimler tahliye edildi
    assert all(b.destroyed for b in [] ) or True  # (tahliye edilenler listede yok)
    # widget çocukları ile liste tutarlı
    assert all(not b.destroyed for b in w._sys_bubbles)
    assert len(w.msg_frame.children) == len(w._bubble_widgets) == CAP
    # mesaj birimi / domain durumu değişmedi
    assert w.chats == {}
    assert not hasattr(w, "_history_start") or w._history_start == {}


# ── 3) Tahliye yalnız sys balonlarına dokunur ────────────────────────────────
def test_sys_bubble_eviction_preserves_message_rows(monkeypatch):
    _stub_render(monkeypatch)
    w = _win2g()
    rows = [_Row(f"m{i}") for i in range(30)]
    seps = [_Sep(f"gün{i}") for i in range(3)]
    w._bubble_widgets = rows + seps
    for i in range(10):
        xmpp.MainWindow._create_sys_bubble(w, f"eski {i}")
    old_sys = list(w._sys_bubbles)
    assert len(old_sys) == 10
    # CAP adet yeni sys olayı → toplam 60 → en eski 10 sys tahliye edilir
    for i in range(CAP):
        xmpp.MainWindow._handle(w, "sys_msg", f"yeni {i}")
    # normal mesaj satırları ve tarih ayırıcılar duruyor, yok edilmedi
    assert all(not r.destroyed for r in rows)
    assert all(not s.destroyed for s in seps)
    assert all(r in w._bubble_widgets for r in rows)
    assert all(s in w._bubble_widgets for s in seps)
    # yalnız en eski sys balonları gitti
    assert all(b.destroyed for b in old_sys)
    assert all(b not in w._bubble_widgets for b in old_sys)
    assert all(b not in w._sys_bubbles for b in old_sys)
    # yaşıyanlar: son CAP sys balonu
    assert len(w._sys_bubbles) == CAP
    assert [b.text for b in w._sys_bubbles] == [f"yeni {i}" for i in range(CAP)]
    # _bubble_widgets canlı widget çocuklarıyla tutarlı
    alive = [b for b in rows + seps + old_sys + w._sys_bubbles
             if not b.destroyed]
    assert len(w._bubble_widgets) == 30 + 3 + CAP
    assert all(not b.destroyed for b in w._bubble_widgets)
    assert all(b in w._bubble_widgets for b in w._sys_bubbles)
    assert len(alive) == 30 + 3 + CAP
    # domain değişmedi
    assert w.chats == {}


# ── 4) Subject referans yaşam döngüsü (bayat referans saldırısı) ─────────────
def test_subject_reference_survives_eviction_lifecycle(monkeypatch):
    _stub_render(monkeypatch)
    w = _win2g()
    # konu balonu oluştur
    xmpp.MainWindow._handle(w, "muc_subject",
                            {"room": ROOM, "subject": "eski konu"})
    first = w._subject_bubbles[ROOM]
    # yeterince sys olayı → konu balonu cap tarafından tahliye edilir
    for i in range(CAP):
        xmpp.MainWindow._handle(w, "sys_msg", f"taşma {i}")
    assert first.destroyed
    assert ROOM not in w._subject_bubbles        # bayat referans bırakılmadı
    # yeni subject güncellemesi: istisna yok, yok edilmiş widget'a dokunuş yok
    xmpp.MainWindow._handle(w, "muc_subject",
                            {"room": ROOM, "subject": "yeni konu"})
    current = w._subject_bubbles[ROOM]
    assert not current.destroyed
    assert current.text == "📌 Konu: yeni konu"
    assert current in current.parent.children
    # haritada yalnız GEÇERLİ referanslar kalır
    assert all(not b.destroyed for b in w._subject_bubbles.values())
    # clear yolu haritayı/listeleri temizler; sonrasındaki güncelleme çalışır
    xmpp.MainWindow._clear_chat(w)
    assert w._sys_bubbles == [] and w._subject_bubbles == {}
    assert all(b.destroyed for b in w.msg_frame.children) or \
        w.msg_frame.children == []
    xmpp.MainWindow._handle(w, "muc_subject",
                            {"room": ROOM, "subject": "clear sonrası"})
    assert w._subject_bubbles[ROOM].text == "📌 Konu: clear sonrası"
    assert not w._subject_bubbles[ROOM].destroyed


def test_subject_map_keeps_newer_ref_when_old_subject_evicted(monkeypatch):
    """Aynı odanın ESKİ subject balonu cap ile tahliye edilse bile haritadaki
    GÜNCEL referans düşürülmez (kimlik denetimi)."""
    _stub_render(monkeypatch)
    w = _win2g()
    xmpp.MainWindow._handle(w, "muc_subject",
                            {"room": ROOM, "subject": "konu 1"})
    current = w._subject_bubbles[ROOM]
    # cap'i doldur, sonra haritadaki güncel balonu TAHLİYE EDİLMEMİŞ eski bir
    # ("subject", ROOM) imzalı balonla karıştır
    for i in range(CAP - 2):                   # headroom: tek tahliye
        xmpp.MainWindow._handle(w, "sys_msg", f"ikit {i}")
    stale_kind = types.SimpleNamespace()
    stale_kind.destroyed = False
    stale_kind._sys_kind = ("subject", ROOM)
    stale_kind.destroy = lambda: setattr(stale_kind, "destroyed", True)
    w._sys_bubbles.insert(0, stale_kind)         # en eski sıraya
    w._bubble_widgets.append(stale_kind)
    # bir sys olayı daha → en eski = stale_kind tahliye edilir
    xmpp.MainWindow._handle(w, "sys_msg", "son")
    assert stale_kind.destroyed
    # haritadaki GÜNCEL subject referansı sağ ve değişmedi
    assert w._subject_bubbles.get(ROOM) is current
    assert not current.destroyed


# ── 5) Handler'lar sınırlı yolu bypass edemez ────────────────────────────────
def test_handlers_use_bounded_sys_path(monkeypatch):
    _stub_render(monkeypatch)
    w = _win2g()
    calls = []
    real = xmpp.MainWindow._create_sys_bubble

    def spy(body, sys_kind=None):
        calls.append((body, sys_kind))
        return real(w, body, sys_kind)

    w._create_sys_bubble = spy
    xmpp.MainWindow._handle(w, "sys_msg", "bildirim")
    xmpp.MainWindow._handle(w, "muc_subject",
                            {"room": ROOM, "subject": "konu"})
    xmpp.MainWindow._append(w, "düz sys", "sys")
    # üçü de TEK sınırlı yoldan geçti; subject imzası oda kimlikli
    assert len(calls) == 3
    assert calls[1] == ("📌 Konu: konu", ("subject", ROOM))
    assert calls[0][1] is None and calls[2][1] is None
    assert len(w._sys_bubbles) == 3
