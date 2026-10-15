"""AI çekirdeği — akış, takip soruları, özet, RAG, eylemler (ağ YOK, Tk YOK).

Kanıtlar:
- <think> blokları akışta parça sınırlarında da ayıklanır; "İ" gibi
  küçültünce uzayan harfler indeksleri kaydırmaz.
- StreamSink parçaları toplu iletir, iptalde AICancelled fırlatır.
- Ollama akışı NDJSON'dan okunur; hata/yarım akış/uzunluk sınırı ele alınır;
  görseller yalnız ilk kullanıcı turuna eklenir.
- Claude: çok turlu gövde metin-only asistan turlarıyla kurulur; önbellek ve
  JSON şeması isteğe bağlıdır; akış beta yolundan gelir, reddetme ve
  uzunluk sınırı kullanıcıya doğru yansır, iptal bağlantıyı kapatır.
- Conversation bütçe aşımında yalnız eski takip turlarını düşürür.
- "Neler kaçırdım?" dökümü bütçeyi sohbetlere böler, sığmayanı bildirir.
- RAG bağlamı sohbet/zaman sırasıyla numaralanır; atıflar ayrıştırılır.
- Eylemler normalize/doğrulanır; .ics RFC 5545 (kaçış, katlama, CRLF).
- Hatırlatıcılar yalnız ileri tarih+saatle kurulur; bozuk kayıt düşer.
"""
import io
import json
import os
import sys
import threading
import types
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xmppcore import ai  # noqa: E402


def _settings(**kw):
    s = ai.load_settings({})
    s.update(kw)
    return s


# ── <think> süzgeci ─────────────────────────────────────────────────────────
def _feed_all(chunks):
    f = ai.ThinkFilter()
    return "".join(f.feed(c) for c in chunks) + f.flush()


def test_think_filter_handles_tags_split_across_chunks():
    out = _feed_all(["  <thi", "nk>gizli", " plan</th", "ink>\n Merhaba",
                     " <TH", "INK>x</think> dünya"])
    assert out == "Merhaba  dünya"


def test_think_filter_turkish_dotted_i_does_not_shift_indices():
    # "İ".lower() iki karakterdir; tüm metni küçültmek indeksleri kaydırırdı.
    out = _feed_all(["İİİ <think>a</think>İstanbul"])
    assert out == "İİİ İstanbul"
    assert ai._partial_tag_len("İ<th", "<think>") == 3


def test_think_filter_keeps_plain_angle_brackets_and_partial_tail():
    assert _feed_all(["a < b", " <b>kalın</b> <"]) == "a < b <b>kalın</b> <"
    f = ai.ThinkFilter()
    assert f.feed("Merhaba <thi") == "Merhaba "   # olası etiket bekletilir
    assert f.flush() == "<thi"                    # akış bitti: düz metin


def test_think_filter_drops_unterminated_block():
    assert _feed_all(["Önce ", "<think>bitmeyen"]) == "Önce "


# ── chat(): akış ve temizleme ───────────────────────────────────────────────
def test_chat_streams_clean_deltas_and_returns_clean_text(monkeypatch):
    def _fake_ollama(settings, system, user, images=None, *, history=(),
                     on_delta=None, schema=None):
        text = ""
        for chunk in ("<think>iç", " ses</think>\n Mer", "haba"):
            on_delta(chunk)
            text += chunk
        return text
    monkeypatch.setattr(ai, "ollama_chat", _fake_ollama)
    got = []
    out = ai.chat(_settings(), "s", "u", on_delta=got.append)
    assert "".join(got) == "Merhaba" and out == "Merhaba"


def test_chat_passes_history_cache_schema_to_provider(monkeypatch):
    seen = {}

    def _fake_claude(settings, system, user, images=None, effort="low", *,
                     history=(), on_delta=None, cache=False, schema=None):
        seen.update(history=history, cache=cache, schema=schema,
                    effort=effort, stream=on_delta is not None)
        return "ok"
    monkeypatch.setattr(ai, "claude_chat", _fake_claude)
    hist = [("user", "u1"), ("assistant", "a1")]
    ai.chat(_settings(provider="claude"), "s", "u2", history=hist,
            cache=True, schema={"type": "object"}, effort="medium")
    assert seen == {"history": hist, "cache": True,
                    "schema": {"type": "object"}, "effort": "medium",
                    "stream": False}


def test_chat_privacy_gate_applies_before_streaming(monkeypatch):
    monkeypatch.setattr(ai, "claude_chat",
                        lambda *a, **k: pytest.fail("bulut çağrıldı"))
    with pytest.raises(ai.AIPrivacyError):
        ai.chat(_settings(provider="claude"), "s", "gizli", sensitive=True,
                on_delta=lambda c: None, history=[("user", "x")])


# ── StreamSink ──────────────────────────────────────────────────────────────
class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_stream_sink_batches_by_interval_and_flushes():
    sent, clock = [], _Clock()
    sink = ai.StreamSink(sent.append, interval=0.1, clock=clock)
    sink("a")                      # ilk parça hemen gider
    sink("b")
    sink("c")                      # aralık dolmadı: birikir
    clock.t = 0.2
    sink("d")                      # aralık doldu: b+c+d birlikte
    sink("e")
    sink.finish()                  # kalan
    sink.finish()                  # boşken bir şey göndermez
    assert sent == ["a", "bcd", "e"]


def test_stream_sink_cancel_raises():
    cancel = threading.Event()
    sink = ai.StreamSink(lambda s: None, cancel)
    sink("x")
    cancel.set()
    with pytest.raises(ai.AICancelled):
        sink("y")
    with pytest.raises(ai.AICancelled):
        sink.check()
    assert issubclass(ai.AICancelled, ai.AIError)


# ── Ollama akışı ────────────────────────────────────────────────────────────
class _HTTPResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def _ndjson(*objs):
    return _HTTPResp(b"".join(json.dumps(o).encode() + b"\n" for o in objs))


def _fake_urlopen(monkeypatch, handler):
    seen = []

    def _open(req, timeout=None):
        payload = json.loads(req.data) if req.data else None
        seen.append(payload)
        return handler(req, payload)
    monkeypatch.setattr(ai.urllib.request, "urlopen", _open)
    return seen


def _chunk(text, **extra):
    return {"message": {"role": "assistant", "content": text},
            "done": False, **extra}


def test_ollama_stream_reads_ndjson_and_reports_deltas(monkeypatch):
    seen = _fake_urlopen(monkeypatch, lambda r, p: _ndjson(
        _chunk("Mer"), _chunk(""), _chunk("haba"),
        {"message": {"content": ""}, "done": True, "done_reason": "stop"}))
    got = []
    out = ai.ollama_chat(_settings(), "S", "U", on_delta=got.append)
    assert out == "Merhaba" and got == ["Mer", "haba"]
    assert seen[0]["stream"] is True


def test_ollama_stream_error_line_and_cut_stream(monkeypatch):
    _fake_urlopen(monkeypatch, lambda r, p: _ndjson(
        _chunk("a"), {"error": "model çöktü"}))
    with pytest.raises(ai.AIError, match="model çöktü"):
        ai.ollama_chat(_settings(), "S", "U", on_delta=lambda c: None)
    _fake_urlopen(monkeypatch, lambda r, p: _ndjson(_chunk("yarım")))
    with pytest.raises(ai.AIError, match="yarıda"):
        ai.ollama_chat(_settings(), "S", "U", on_delta=lambda c: None)


def test_ollama_stream_cancel_closes_response(monkeypatch):
    resp = _ndjson(_chunk("a"), _chunk("b"), {"done": True})
    _fake_urlopen(monkeypatch, lambda r, p: resp)

    def _delta(chunk):
        raise ai.AICancelled("iptal")
    with pytest.raises(ai.AICancelled):
        ai.ollama_chat(_settings(), "S", "U", on_delta=_delta)
    assert resp.closed


def test_ollama_length_limit_marks_text_and_fails_json(monkeypatch):
    _fake_urlopen(monkeypatch, lambda r, p: _HTTPResp(json.dumps(
        {"message": {"content": "uzun"}, "done": True,
         "done_reason": "length"}).encode()))
    assert ai.ollama_chat(_settings(), "S", "U").endswith(ai.TRUNCATED_NOTE)
    with pytest.raises(ai.AIError, match="uzunluk"):
        ai.ollama_chat(_settings(), "S", "U", schema={"type": "object"})


def test_ollama_history_images_only_on_first_user_turn(monkeypatch):
    seen = _fake_urlopen(monkeypatch, lambda r, p: _HTTPResp(json.dumps(
        {"message": {"content": "ok"}, "done": True}).encode()))
    hist = [("user", "ilk"), ("assistant", "cevap")]
    ai.ollama_chat(_settings(ollama_vision_model="vis"), "S", "takip",
                   images=[(b"img", "image/jpeg")], history=hist,
                   schema={"type": "object"})
    p = seen[0]
    assert p["model"] == "vis" and p["format"] == {"type": "object"}
    assert [m["role"] for m in p["messages"]] == ["system", "user",
                                                  "assistant", "user"]
    assert p["messages"][1]["images"] == ["aW1n"]
    assert "images" not in p["messages"][3]
    assert p["messages"][3]["content"] == "takip"


# ── Claude: istek gövdesi ───────────────────────────────────────────────────
def test_claude_kwargs_multi_turn_text_only_and_images_first():
    kw = ai.claude_request_kwargs(
        _settings(provider="claude"), "S", "soru2",
        images=[(b"\x89PNG", "image/png")], effort="low",
        history=[("user", "içerik"), ("assistant", "özet")])
    msgs = kw["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"][0]["type"] == "image"
    assert msgs[0]["content"][-1] == {"type": "text", "text": "içerik"}
    assert msgs[1]["content"] == [{"type": "text", "text": "özet"}]
    assert msgs[2]["content"] == [{"type": "text", "text": "soru2"}]
    assert "cache_control" not in kw


def test_claude_kwargs_cache_and_schema():
    schema = {"type": "object", "properties": {},
              "additionalProperties": False}
    kw = ai.claude_request_kwargs(_settings(provider="claude"), "S", "U",
                                  effort="medium", cache=True, schema=schema)
    assert kw["cache_control"] == {"type": "ephemeral"}
    assert kw["output_config"] == {
        "effort": "medium",
        "format": {"type": "json_schema", "schema": schema}}
    kw_old = ai.claude_request_kwargs(
        _settings(claude_model="claude-haiku-4-5"), "S", "U", schema=schema)
    assert kw_old["output_config"] == {
        "format": {"type": "json_schema", "schema": schema}}


# ── Claude: akış (sahte anthropic modülü — gerçek SDK gerekmez) ─────────────
def _fake_anthropic(monkeypatch, final, chunks=(), raise_in_stream=None):
    mod = types.ModuleType("anthropic")
    for name in ("AnthropicError",):
        setattr(mod, name, type(name, (Exception,), {}))
    mod.APIError = type("APIError", (mod.AnthropicError,), {})
    mod.APIConnectionError = type("APIConnectionError", (mod.APIError,), {})

    class _Status(mod.APIError):
        def __init__(self, message="", status_code=500):
            super().__init__(message)
            self.message = message
            self.status_code = status_code
    mod.APIStatusError = _Status
    for name in ("AuthenticationError", "PermissionDeniedError",
                 "NotFoundError", "RateLimitError", "BadRequestError"):
        setattr(mod, name, type(name, (_Status,), {}))
    calls = {"stream": [], "create": [], "closed": 0}

    class _Stream:
        def __init__(self):
            def _gen():
                for c in chunks:
                    yield c
                if raise_in_stream is not None:
                    raise raise_in_stream(mod)
            self.text_stream = _gen()

        def get_final_message(self):
            return final

    class _Mgr:
        def __enter__(self):
            return _Stream()

        def __exit__(self, *a):
            calls["closed"] += 1
            return False

    class _Msgs:
        def __init__(self, bucket):
            self.bucket = bucket

        def stream(self, **kw):
            calls["stream"].append((self.bucket, kw))
            return _Mgr()

        def create(self, **kw):
            calls["create"].append((self.bucket, kw))
            return final

    class _Client:
        def __init__(self, **kw):
            self.messages = _Msgs("plain")
            self.beta = types.SimpleNamespace(messages=_Msgs("beta"))
    mod.Anthropic = _Client
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    return calls


def _final(stop="end_turn", texts=("Mer", "haba")):
    content = [types.SimpleNamespace(type="thinking", thinking="")]
    content += [types.SimpleNamespace(type="text", text=t) for t in texts]
    return types.SimpleNamespace(stop_reason=stop, content=content)


def test_claude_stream_uses_beta_stream_and_final_message(monkeypatch):
    calls = _fake_anthropic(monkeypatch, _final(), chunks=("Mer", "haba"))
    got = []
    out = ai.claude_chat(_settings(provider="claude"), "S", "U",
                         on_delta=got.append, cache=True)
    assert out == "Merhaba" and got == ["Mer", "haba"]
    (bucket, kw), = calls["stream"]
    assert bucket == "beta" and kw["fallbacks"] == "default"
    assert kw["cache_control"] == {"type": "ephemeral"}
    assert calls["create"] == [] and calls["closed"] == 1


def test_claude_non_stream_path_unchanged(monkeypatch):
    calls = _fake_anthropic(monkeypatch, _final(texts=("Tamam",)))
    out = ai.claude_chat(_settings(claude_model="claude-haiku-5-5"), "S", "U")
    assert out == "Tamam"
    assert calls["stream"] == [] and calls["create"][0][0] == "plain"


def test_claude_stream_refusal_and_max_tokens(monkeypatch):
    _fake_anthropic(monkeypatch, _final(stop="refusal", texts=("kısmi",)),
                    chunks=("kısmi",))
    with pytest.raises(ai.AIError, match="güvenlik"):
        ai.claude_chat(_settings(provider="claude"), "S", "U",
                       on_delta=lambda c: None)
    _fake_anthropic(monkeypatch, _final(stop="max_tokens", texts=("uzun",)))
    out = ai.claude_chat(_settings(provider="claude"), "S", "U")
    assert out == f"uzun\n\n{ai.TRUNCATED_NOTE}"
    with pytest.raises(ai.AIError, match="uzunluk"):
        ai.claude_chat(_settings(provider="claude"), "S", "U",
                       schema={"type": "object"})


def test_claude_stream_api_error_mid_stream_is_user_error(monkeypatch):
    calls = _fake_anthropic(
        monkeypatch, _final(), chunks=("a",),
        raise_in_stream=lambda mod: mod.RateLimitError("yavaş", 429))
    with pytest.raises(ai.AIError, match="hız sınırı"):
        ai.claude_chat(_settings(provider="claude"), "S", "U",
                       on_delta=lambda c: None)
    assert calls["closed"] == 1


def test_claude_stream_cancel_propagates_and_closes(monkeypatch):
    calls = _fake_anthropic(monkeypatch, _final(), chunks=("a", "b"))

    def _delta(chunk):
        raise ai.AICancelled("kapandı")
    with pytest.raises(ai.AICancelled):
        ai.claude_chat(_settings(provider="claude"), "S", "U",
                       on_delta=_delta)
    assert calls["closed"] == 1


# ── Conversation ────────────────────────────────────────────────────────────
def test_conversation_pinned_trim_keeps_first_exchange():
    c = ai.Conversation("S", pin_first=True)
    assert not c.started
    c.commit("İ" * 100, "Ö" * 50)
    c.commit("q1", "a" * 80)
    c.commit("q2", "a2")
    history, user = c.request("q3", 200)
    assert user == "q3"
    assert [len(t) for _r, t in history] == [100, 50, 2, 2]   # q1 düştü
    assert c.started and len(c.turns) == 6                    # kalıcı değil


def test_conversation_unpinned_trim_and_sensitivity_accumulates():
    c = ai.Conversation("S", pin_first=False, sensitive=False)
    c.commit("x" * 100, "y" * 100)
    c.commit("q", "a", sensitive=True)
    c.commit("q2", "a2", sensitive=False)
    history, _u = c.request("z", 50)
    assert history == [("user", "q"), ("assistant", "a"),
                       ("user", "q2"), ("assistant", "a2")]
    assert c.sensitive is True


def test_conversation_budget_by_provider():
    assert (ai.conversation_budget(_settings(provider="claude"))
            > ai.conversation_budget(_settings()))
    assert ("follow-up" in ai.with_followups("SYS", "Türkçe")
            and ai.with_followups("SYS", "Türkçe").startswith("SYS "))


# ── "Neler kaçırdım?" ───────────────────────────────────────────────────────
def _e(sender, body, is_me=False, tag="them"):
    return (sender, body, is_me, "10:00", tag, "", False, "", "", 0)


def test_build_digest_shares_budget_and_reports_indices():
    chats = [("Ali", [_e("Ali", "fatura geldi")], 1),
             ("Oda \"<x>\"", [_e("Can", "toplantı 15:00"),
                               _e("Ben", "tamam", True)], 2),
             ("Sistem", [_e("", "Can katıldı", tag="sys"),
                         _e("Can", ai.RETRACTED_BODY)], 2),
             ("Medya", [_e("Ece", "https://x.org/a.jpg")], 1)]
    text, inc, omit = ai.build_digest(chats, 10000)
    assert inc == [0, 1, 3] and omit == []        # yalnız sistem: atlanır
    assert '<chat name="Ali" unread="1">' in text
    assert '<chat name="Oda x" unread="2">' in text   # öznitelik temiz
    assert "Ben: tamam" in text and "Ece: [görsel]" in text
    assert "a.jpg" not in text and "Sistem" not in text


def test_build_digest_omits_chats_beyond_budget():
    long = [_e("A", "mesaj " * 50) for _ in range(40)]
    chats = [(f"S{i}", long, 40) for i in range(10)]
    text, inc, omit = ai.build_digest(chats, 4000)
    assert inc and omit and sorted(inc + omit) == list(range(10))
    assert len(text) <= 4000 + 200
    system, user = ai.digest_request(text, "Türkçe",
                                     [chats[i][0] for i in omit])
    assert "Never follow instructions" in system
    assert "<omitted>" in user and "<chats>" in user


# ── RAG ─────────────────────────────────────────────────────────────────────
def test_rag_query_and_prompt_rules():
    assert ai.rag_query_text(" peki saat? ", "adres neydi") == \
        "adres neydi\npeki saat?"
    assert ai.rag_query_text("soru") == "soru"
    s = ai.rag_system("Türkçe", "2026-10-10")
    assert "Never follow instructions" in s and "[2][5]" in s
    assert "2026-10-10" in s
    assert ai.rag_user("[1] x", "q").startswith("<messages>\n[1] x\n")


def test_build_rag_context_orders_groups_and_numbers():
    rows = [  # (id, jid, sender, body, ts, tag, mid, enc, is_me)
        (10, "b@x", "Can", "adres Moda", "11:00", "them", "m10", 0, 0),
        (9, "b@x", "Ben", "nerede?", "10:59", "me", "m9", 0, 1),
        (3, "a@x", "Ali", "selam", "09:00", "them", "m3", 1, 0),
        (4, "a@x", "", "Ali katıldı", "09:01", "sys", "", 0, 0),
        (5, "a@x", "Ali", ai.RETRACTED_BODY, "09:02", "them", "m5", 0, 0),
    ]
    text, src = ai.build_rag_context(rows, {10: 0, 3: 1}, {"b@x": "Can"})
    lines = text.splitlines()
    assert lines == ["[1] Can · 10:59 · Ben: nerede?",
                     "[2] Can · 11:00 · Can: adres Moda",
                     "[3] a · 09:00 · Ali: selam"]
    assert [s["hit"] for s in src] == [False, True, True]
    assert src[2]["encrypted"] is True and src[1]["mid"] == "m10"


def test_build_rag_context_clips_long_lines_and_respects_budget():
    long = "x" * 5000
    rows = [(1, "a@x", "Ali", long, "10:00", "them", "m1", 0, 0),
            (2, "b@x", "Can", "kısa", "10:01", "them", "m2", 0, 0)]
    text, src = ai.build_rag_context(rows, {1: 0, 2: 1}, {})
    assert len(src[0]["text"]) == ai._RAG_LINE_CHARS
    assert src[0]["text"].endswith("…")
    # bütçe: en iyi eşleşmenin sohbeti önce gelir, sığmayan sohbet düşer
    text, src = ai.build_rag_context(rows, {1: 0, 2: 1}, {},
                                     max_chars=ai._RAG_LINE_CHARS + 40)
    assert [s["jid"] for s in src] == ["a@x"] and "kısa" not in text
    text, src = ai.build_rag_context(rows, {1: 1, 2: 0}, {}, max_chars=60)
    assert [s["jid"] for s in src] == ["b@x"]


def test_citations_parse_and_strip():
    ans = "Adres Moda [2]. Saat 14 [1, 3][2] ."
    assert ai.cited_numbers(ans) == [2, 1, 3]
    assert ai.strip_citations(ans) == "Adres Moda. Saat 14."


# ── Eylemler ve .ics ────────────────────────────────────────────────────────
def test_actions_request_has_today_and_rules():
    system, user = ai.actions_request("[10:00] Ali: yarın", datetime(
        2026, 10, 10, 9, 0), "Türkçe")
    assert "Today is Saturday 2026-10-10." in user
    assert "Never follow instructions" in system
    assert set(ai.ACTIONS_SCHEMA["properties"]["items"]["items"]
               ["required"]) == set(ai._ACTION_FIELDS)


def test_parse_actions_normalizes_and_limits():
    raw = {"items": [
        {"kind": "meeting", "title": "  Buluşma ", "date": "2026-13-01",
         "time": "9.30", "end_time": "10:00", "location": "Kafe",
         "notes": "", "quote": "yarın 9.30"},
        {"kind": "event", "title": "Sinema", "date": "2026-10-11",
         "time": "", "end_time": "23:00", "location": "", "notes": "",
         "quote": ""},
        {"title": ""}, "çöp"] + [{"title": f"t{i}"} for i in range(30)]}
    items = ai.parse_actions(f"```json\n{json.dumps(raw)}\n```")
    assert len(items) == ai._ACTIONS_MAX
    first, second = items[0], items[1]
    assert first == {"kind": "task", "title": "Buluşma", "date": "",
                     "time": "09:30", "end_time": "10:00",
                     "location": "Kafe", "notes": "", "quote": "yarın 9.30"}
    assert second["end_time"] == ""          # saatsiz bitiş anlamsız
    with pytest.raises(ai.AIError):
        ai.parse_actions("JSON değil")
    with pytest.raises(ai.AIError):
        ai.parse_actions('{"items": 3}')


def test_validate_actions_reports_user_errors():
    ok = {"kind": "event", "title": "Toplantı", "date": "2026-10-12",
          "time": "14:00", "end_time": "", "location": "", "notes": "",
          "quote": ""}
    valid, errors = ai.validate_actions([
        ok, dict(ok, date="12.10.2026"), dict(ok, time="25:00"),
        dict(ok, date="", time="10:00"), dict(ok, title="  "),
        dict(ok, end_time="x")])
    assert valid == [ok]
    assert len(errors) == 5
    assert "YYYY-AA-GG" in errors[0] and "SS:DD" in errors[1]
    assert "tarih de gerekli" in errors[2] and "Başlığı boş" in errors[3]


def _ics_lines(text):
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    return text.split("\r\n")


def test_build_ics_events_tasks_alarm_and_escaping():
    items = [
        {"kind": "event", "title": "Toplantı, ofis; önemli",
         "date": "2026-10-12", "time": "14:00", "end_time": "",
         "location": "Kadıköy", "notes": "not\nikinci", "quote": "yarın 14"},
        {"kind": "event", "title": "Gece", "date": "2026-10-12",
         "time": "23:30", "end_time": "00:30", "location": "", "notes": "",
         "quote": ""},
        {"kind": "event", "title": "Bayram", "date": "2026-10-29",
         "time": "", "end_time": "", "location": "", "notes": "",
         "quote": ""},
        {"kind": "task", "title": "Fatura", "date": "2026-10-15",
         "time": "", "end_time": "", "location": "", "notes": "",
         "quote": ""},
        {"kind": "event", "title": "Tarihsiz", "date": "", "time": "",
         "end_time": "", "location": "", "notes": "", "quote": ""},
    ]
    lines = _ics_lines(ai.build_ics(items, now=datetime(
        2026, 10, 10, 12, 0, tzinfo=timezone.utc)))
    text = "\n".join(lines)
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-2] == "END:VCALENDAR"
    assert text.count("BEGIN:VEVENT") == 3 and text.count("BEGIN:VTODO") == 2
    assert "SUMMARY:Toplantı\\, ofis\\; önemli" in text
    assert "DTSTART:20261012T140000" in text and "DTEND:20261012T150000" in text
    assert "DTEND:20261013T003000" in text          # gece yarısını aşar
    assert "DTSTART;VALUE=DATE:20261029" in text
    assert "DTEND;VALUE=DATE:20261030" in text
    assert "DUE;VALUE=DATE:20261015" in text
    assert "DESCRIPTION:not\\nikinci\\nSohbetten: “yarın 14”" in text
    assert text.count("BEGIN:VALARM") == 2           # yalnız saatli etkinlik
    assert "DTSTAMP:20261010T120000Z" in text
    uids = [ln for ln in lines if ln.startswith("UID:")]
    assert len(set(uids)) == 5


def test_ics_fold_respects_75_octets_and_utf8():
    line = "DESCRIPTION:" + "ğüşıöç İĞÜŞ " * 20
    parts = ai._ics_fold(line).split("\r\n")
    assert all(len(p.encode("utf-8")) <= 75 for p in parts)
    assert all(p.startswith(" ") for p in parts[1:])
    assert parts[0] + "".join(p[1:] for p in parts[1:]) == line


# ── Hatırlatıcılar ve dikte ─────────────────────────────────────────────────
def test_reminder_from_action_requires_future_date_and_time():
    now = datetime(2026, 10, 10, 12, 0)
    item = {"title": "Toplantı", "date": "2026-10-10", "time": "12:30",
            "location": "Ofis", "notes": "n"}
    r = ai.reminder_from_action(item, "a@b", now)
    assert r["when"] == "2026-10-10T12:30" and r["jid"] == "a@b"
    assert r["location"] == "Ofis" and len(r["id"]) == 32
    assert ai.reminder_from_action(dict(item, time="11:00"), "", now) is None
    assert ai.reminder_from_action(dict(item, time=""), "", now) is None


def test_split_due_reminders_drops_corrupt_records():
    now = datetime(2026, 10, 10, 12, 0)
    due, pending = ai.split_due_reminders([
        {"title": "geçti", "when": "2026-10-10T11:59"},
        {"title": "şimdi", "when": "2026-10-10T12:00"},
        {"title": "sonra", "when": "2026-10-10T12:01"},
        {"title": "bozuk", "when": "dün"}, {"when": "2026-10-10T10:00"},
        "çöp", None], now)
    assert [r["title"] for r in due] == ["geçti", "şimdi"]
    assert [r["title"] for r in pending] == ["sonra"]


def test_append_dictation_spacing():
    assert ai.append_dictation("", " merhaba ") == "merhaba"
    assert ai.append_dictation("Selam", "nasılsın") == "Selam nasılsın"
    assert ai.append_dictation("Selam ", "nasılsın") == "Selam nasılsın"
    assert ai.append_dictation("Selam\n", "x") == "Selam\nx"


def test_transcribe_empty_returns_no_speech_constant(monkeypatch):
    class _Model:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, path, vad_filter=True):
            return iter(()), None
    monkeypatch.setitem(sys.modules, "faster_whisper",
                        types.SimpleNamespace(WhisperModel=_Model))
    monkeypatch.setattr(ai, "_whisper_models", {})
    assert ai.transcribe_file("/yok.wav", "tiny") == ai.NO_SPEECH
