"""Sesli mesaj dökümünün balonda gösterimi ve otomatik yerel kuyruk.

Kanıtlar:
- Ayarlar: `auto_transcribe` varsayılan kapalı, `leak_guard` açık; ikisi de
  kalıcı ve bool'a zorlanır. AI kapalıyken otomatik döküm çalışmaz.
- _append: satır meta çerçevesini (`_meta_frame`) ve ses kaynağını
  (`_stt_ref`) taşır; bilinen döküm hemen balona girer; otomatik modda
  yalnız GELEN ses kuyruğa eklenir.
- Balon: döküm meta satırından ÖNCE paketlenir, ikinci sonuç aynı etiketi
  günceller; yok edilmiş satıra dokunulmaz; uzun metin kırpılır.
- Kuyruk: kaynak başına tek iş, tek worker, en yeni önce; tavan aşılınca
  en eski düşer ve yeniden eklenebilir. Tek bir kaynağın hatası kuyruğu
  durdurmaz; yerel bileşen eksikse (AISetupError) kuyruk boşalır ve
  otomatik mod oturum için kapanır. Worker Tk'ya dokunmaz.
- Elle "Metne dök" sonucu da balona yazılır.
"""
import inspect
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fake_selectable  # noqa: E402
from test_chat_media import _MW, _append_window  # noqa: E402
from test_history_window_bounds import _Cap  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import ai  # noqa: E402

URL = "https://up.example/v/ses.ogg"


# ── 1) Ayarlar ──────────────────────────────────────────────────────────────
def test_settings_defaults_and_persistence():
    s = ai.load_settings({})
    assert s["auto_transcribe"] is False and s["leak_guard"] is True
    cfg = ai.merge_settings({}, {"auto_transcribe": True,
                                 "leak_guard": False}, None)
    s = ai.load_settings(cfg)
    assert s["auto_transcribe"] is True and s["leak_guard"] is False
    assert ai.load_settings({"ai": {"auto_transcribe": 1}})[
        "auto_transcribe"] is True


def test_refresh_flags_respects_provider_off(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"ai": {
        "auto_transcribe": True, "provider": "off", "whisper_model": "base"}})
    xmpp.MainWindow._ai_refresh_flags(w)
    assert w._ai_auto_stt is False and w._ai_stt_model == "base"
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"ai": {
        "auto_transcribe": True}})
    xmpp.MainWindow._ai_refresh_flags(w)
    assert w._ai_auto_stt is True


# ── 2) _append kancası ──────────────────────────────────────────────────────
def _audio_w(monkeypatch):
    w = _append_window(monkeypatch)
    monkeypatch.setattr(xmpp._audio_ui, "audio_placeholder",
                        lambda parent, theme, bg: _MW())
    w._request_audio = lambda url, holder, bg: None
    w._request_url_preview = lambda url, container: None
    return w


def test_append_records_meta_frame_and_audio_ref(monkeypatch):
    w = _audio_w(monkeypatch)
    row = xmpp.MainWindow._append(w, f"dinle {URL}", "them", sender="Ali")
    assert row._meta_frame is not None
    assert row._meta_frame in row._bubble.children
    assert row._stt_ref == URL
    plain = xmpp.MainWindow._append(w, "merhaba", "them", sender="Ali")
    assert not hasattr(plain, "_stt_ref")


def test_append_shows_known_transcript(monkeypatch):
    w = _audio_w(monkeypatch)
    w._ai_stt_texts = {URL: "yarın geliyorum"}
    w._ai_show_transcript = _Cap()
    row = xmpp.MainWindow._append(w, URL, "them", sender="Ali")
    assert w._ai_show_transcript.calls == [((row, "yarın geliyorum"), {})]


def test_auto_mode_enqueues_only_incoming(monkeypatch):
    w = _audio_w(monkeypatch)
    w._ai_auto_stt = True
    w._ai_stt_enqueue = _Cap()
    xmpp.MainWindow._append(w, URL, "them", sender="Ali")
    xmpp.MainWindow._append(w, URL, "me", sender="Ben", is_me=True)
    assert w._ai_stt_enqueue.calls == [((("url", URL),), {})]


def test_auto_mode_off_does_nothing(monkeypatch):
    w = _audio_w(monkeypatch)
    w._ai_stt_enqueue = _Cap()
    xmpp.MainWindow._append(w, URL, "them", sender="Ali")
    assert w._ai_stt_enqueue.calls == []


# ── 3) Balon içi gösterim ───────────────────────────────────────────────────
class _Row:
    def __init__(self, alive=True, is_me=False, ref=URL):
        self._alive = alive
        self._is_me = is_me
        self._stt_ref = ref
        self._meta_frame = object()
        self._bubble = types.SimpleNamespace(cget=lambda k: "#123")

    def winfo_exists(self):
        return self._alive


def test_show_transcript_packs_before_meta_then_updates(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w._bind_message_menu = _Cap()
    w._bind_scroll_widget = _Cap()
    notes, updates = [], []

    def _note(bubble, theme, bg, text, *, is_me, text_factory, before=None):
        assert text_factory is xmpp._selectable.selectable_text  # seçilebilir
        notes.append((bg, text, is_me, before))
        return "LBL"
    monkeypatch.setattr(xmpp._audio_ui, "transcript_note", _note)
    monkeypatch.setattr(xmpp._audio_ui, "set_transcript",
                        lambda lbl, text: updates.append((lbl, text)))
    row = _Row()
    xmpp.MainWindow._ai_show_transcript(w, row, "ilk")
    assert notes == [("#123", "ilk", False, row._meta_frame)]
    assert w._bind_message_menu.calls == [(("LBL", row), {})]
    xmpp.MainWindow._ai_show_transcript(w, row, "ikinci")
    assert len(notes) == 1 and updates == [("LBL", "ikinci")]
    xmpp.MainWindow._ai_show_transcript(w, _Row(alive=False), "x")
    assert len(notes) == 1


def test_stt_done_updates_matching_rows_and_caps_memo(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    a, b, other = _Row(), _Row(), _Row(ref="https://x/b.ogg")
    w._bubble_widgets = [a, object(), b, other]
    w._ai_show_transcript = _Cap()
    monkeypatch.setattr(xmpp.MainWindow, "_AI_STT_MEMO_CAP", 2)
    xmpp.MainWindow._ai_stt_done(w, URL, "metin")
    assert [c[0][0] for c in w._ai_show_transcript.calls] == [a, b]
    xmpp.MainWindow._ai_stt_done(w, "r2", "2")
    xmpp.MainWindow._ai_stt_done(w, "r3", "3")
    assert list(w._ai_stt_texts) == ["r2", "r3"]


def test_transcript_view_truncates_and_packs_before(monkeypatch):
    monkeypatch.setattr(xmpp._audio_ui, "tk", types.SimpleNamespace(
        Label=_MW))
    meta = _MW()
    lbl = xmpp._audio_ui.transcript_note(
        _MW(), xmpp._chat_theme(), "#000", "a  b\n" + "x" * 900,
        is_me=False, before=meta,
        text_factory=fake_selectable.make(_MW).selectable_text)
    assert lbl.kw["_pack"][1]["before"] is meta
    text = lbl.kw["text"]
    assert text.startswith("📝 a b x") and text.endswith("…")
    assert len(text) == len("📝 ") + xmpp._audio_ui.TRANSCRIPT_MAX_CHARS


# ── 4) Otomatik kuyruk ──────────────────────────────────────────────────────
def _qw(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.active = "a@x"
    w._ai_stt_model = "small"
    threads = []

    class _T:
        def __init__(self, target=None, daemon=None, name=None):
            threads.append(target)

        def start(self):
            pass
    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    return w, threads


def test_enqueue_dedupes_and_starts_single_worker(monkeypatch):
    w, threads = _qw(monkeypatch)
    xmpp.MainWindow._ai_stt_enqueue(w, ("url", URL))
    xmpp.MainWindow._ai_stt_enqueue(w, ("url", URL))
    xmpp.MainWindow._ai_stt_enqueue(w, ("url", "https://x/2.ogg"))
    st = w._ai_stt
    assert len(threads) == 1 and st["running"] is True
    assert [i[0][1] for i in st["queue"]] == [URL, "https://x/2.ogg"]
    assert st["queue"][0][1:] == ("small", "a@x")


def test_enqueue_cap_drops_oldest_and_allows_requeue(monkeypatch):
    w, _t = _qw(monkeypatch)
    monkeypatch.setattr(xmpp.MainWindow, "_AI_STT_QUEUE_CAP", 2)
    for i in range(3):
        xmpp.MainWindow._ai_stt_enqueue(w, ("url", f"r{i}"))
    assert [i[0][1] for i in w._ai_stt["queue"]] == ["r1", "r2"]
    assert "r0" not in w._ai_stt["seen"]
    xmpp.MainWindow._ai_stt_enqueue(w, ("url", "r0"))
    assert [i[0][1] for i in w._ai_stt["queue"]] == ["r2", "r0"]


def test_worker_newest_first_and_skips_failed_item(monkeypatch):
    w, _t = _qw(monkeypatch)
    for ref in ("eski", "bozuk", "yeni"):
        xmpp.MainWindow._ai_stt_enqueue(w, ("url", ref))

    def _job(src, model, jid):
        def run():
            if src[1] == "bozuk":
                raise ai.AIError("indirilemedi")
            return f"metin:{src[1]}"
        return run
    w._ai_stt_job = _job
    w._safe_after = _Cap()
    xmpp.MainWindow._ai_stt_worker(w)
    assert [c[0][2:] for c in w._safe_after.calls] == [
        ("yeni", "metin:yeni"), ("eski", "metin:eski")]
    assert w._ai_stt["running"] is False
    assert "bozuk" in w._ai_stt["seen"]          # oturumda tekrar denenmez


def test_worker_setup_error_disables_auto_mode(monkeypatch):
    w, _t = _qw(monkeypatch)
    for ref in ("a", "b"):
        xmpp.MainWindow._ai_stt_enqueue(w, ("url", ref))
    calls = []

    def _job(src, model, jid):
        def run():
            calls.append(src[1])
            raise ai.AISetupError("faster-whisper gerekli")
        return run
    w._ai_stt_job = _job
    w._safe_after = _Cap()
    xmpp.MainWindow._ai_stt_worker(w)
    assert calls == ["b"]                        # ilk hatada durur
    assert not w._ai_stt["queue"] and w._ai_stt["running"] is False
    (args, _k), = w._safe_after.calls
    assert args[1].__name__ == "_ai_stt_disable"

    w._ai_auto_stt = True
    w._show_toast = _Cap()
    xmpp.MainWindow._ai_stt_disable(w, "faster-whisper gerekli")
    assert w._ai_auto_stt is False
    (title, text), _k = w._show_toast.calls[0]
    assert len(text) <= 80


def test_missing_whisper_is_setup_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    try:
        ai.transcribe_file("/yok.ogg")
    except ai.AISetupError as e:
        assert "faster-whisper" in str(e)
    else:
        raise AssertionError("AISetupError bekleniyordu")


def test_worker_does_not_touch_tk():
    src = inspect.getsource(xmpp.MainWindow._ai_stt_worker)
    assert "self.root" not in src and "_audio_ui" not in src
    assert "_safe_after" in src


# ── 5) Elle "Metne dök" ─────────────────────────────────────────────────────
def test_manual_transcribe_also_fills_bubble(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = None
    w.active = "a@x"
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"ai": {}})
    texts = []

    class _Win:
        def __init__(self, *a, **k):
            pass

        def set_busy(self, m):
            pass

        def set_text(self, t):
            texts.append(t)

        def set_error(self, m):
            raise AssertionError(m)
    monkeypatch.setattr(xmpp._ui_ai, "ResultWindow", _Win)
    w._ai_stt_job = lambda src, model, jid: (lambda: "merhaba")
    w._ai_submit = lambda job, done, err: done(job())
    w._ai_stt_done = _Cap()
    row = types.SimpleNamespace(_oob=URL, _body=URL, _local_path="",
                                _retracted=False)
    xmpp.MainWindow._ai_transcribe_row(w, row)
    assert texts == ["merhaba"]
    assert w._ai_stt_done.calls == [((URL, "merhaba"), {})]
