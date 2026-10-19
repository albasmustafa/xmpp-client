"""Tk'siz AI uçları: xmpp.py'deki `_ai_*` akışlarının web karşılıkları.

Gizlilik sözleşmesi aynen korunur: `ensure_allowed` izin vermezse
(AIPrivacyError) şifreli içerik buluta gitmez; REST katmanı bunu 403 olarak
döndürür. Gömme ve arama her zaman yereldir. Onay diyaloğu tarayıcıdadır;
burada "izin verildi" bilgisi isteğin kendisiyle gelir (allow_cloud).
"""
from datetime import datetime

from xmppcore import storage as _storage
from xmppcore.ai import (
    RAG_AFTER,
    RAG_BEFORE,
    RAG_MIN_SCORE,
    RAG_TOP_K,
    RETRACTED_BODY,
    VOICE_PLACEHOLDER,
    AIPrivacyError,
    build_digest,
    build_rag_context,
    build_transcript,
    chat,
    cited_numbers,
    digest_request,
    embed_document_text,
    embed_query_text,
    ensure_allowed,
    message_text,
    ollama_embed,
    pack_vec,
    rag_query_text,
    rag_system,
    rag_user,
    summary_request,
    top_k,
    transcript_budget,
    translate_request,
)
from xmppcore.config import _load_config

__all__ = ["AIPrivacyError", "settings", "summary", "translate", "digest",
           "ask_history", "assistant", "index_pending"]


def settings() -> dict:
    from xmppcore.ai import load_settings
    return load_settings(_load_config())


def _entries(jid: str, limit: int = 200):
    """DB satırlarını build_transcript'in beklediği
    (sender, body, is_me, ts, tag, ...) biçimine çevir."""
    return [(r[1], r[2], r[3], r[4], r[5]) for r in
            _storage._db_load_msgs(jid, limit=limit)]


def _label(jid: str, contacts: dict) -> str:
    return contacts.get(jid) or (jid.split("@")[0] if "@" in jid else jid)


def _gate(s: dict, sensitive: bool, allow_cloud: bool) -> str:
    """Sağlayıcıyı döndür; izin yoksa AIPrivacyError fırlar (web: 403)."""
    return ensure_allowed(s, sensitive=sensitive, allow_cloud=allow_cloud)


def summary(jid: str, unread: int = 0, allow_cloud: bool = False,
            contacts: dict | None = None) -> dict:
    s = settings()
    provider = _gate(s, sensitive=True, allow_cloud=allow_cloud)
    transcript, count = build_transcript(
        _entries(jid), max_chars=transcript_budget(s))
    if not count:
        return {"text": "Bu sohbette özetlenecek mesaj yok.",
                "provider": provider}
    system, user = summary_request(transcript, s["target_language"], unread)
    return {"text": chat(s, system, user, max_tokens=1200),
            "provider": provider, "label": _label(jid, contacts or {}),
            "messages": count}


def translate(text: str, allow_cloud: bool = False) -> dict:
    s = settings()
    provider = _gate(s, sensitive=False, allow_cloud=allow_cloud)
    system, user = translate_request(text, s["target_language"])
    return {"text": chat(s, system, user, max_tokens=2000),
            "provider": provider}


def digest(unread_map: dict, allow_cloud: bool = False,
           contacts: dict | None = None) -> dict:
    """Neler kaçırdım: okunmamış sayacı > 0 olan sohbetlerin dökümü.

    `unread_map`: {jid: okunmamış} — köprünün canlı sayaçları.
    """
    s = settings()
    provider = _gate(s, sensitive=True, allow_cloud=allow_cloud)
    contacts = contacts or {}
    chats = []
    for jid, unread in unread_map.items():
        if unread <= 0:
            continue
        entries = _entries(jid, limit=120)
        if entries:
            chats.append((_label(jid, contacts), entries, unread))
    if not chats:
        return {"text": "Okunmamış mesaj yok — her şeyi gördün.",
                "provider": provider}
    digest_text, _inc, omitted_idx = build_digest(
        chats, budget=transcript_budget(s))
    if not digest_text:
        return {"text": "Okunmamış mesaj yok — her şeyi gördün.",
                "provider": provider}
    system, user = digest_request(
        digest_text, s["target_language"],
        [chats[i][0] for i in omitted_idx])
    return {"text": chat(s, system, user, max_tokens=2000),
            "provider": provider}


def index_pending(s: dict) -> int:
    """Gömmesi olmayan mesajları indeksle (_ai_index_pending karşılığı)."""
    model = s["embed_model"]
    skip = (RETRACTED_BODY, VOICE_PLACEHOLDER)
    done, seen = 0, set()
    while True:
        batch = _storage._db_ai_pending(model, 32, skip)
        if not batch:
            break
        ids = {r[0] for r in batch}
        if ids <= seen:
            break
        seen |= ids
        items, texts, targets = [], [], []
        for msg_id, jid, sender, body in batch:
            if message_text(body):
                texts.append(embed_document_text(model, sender or "", body))
                targets.append((msg_id, jid))
            else:
                items.append((msg_id, jid, model, b""))
        for (msg_id, jid), vec in zip(targets, ollama_embed(s, texts)):
            items.append((msg_id, jid, model, pack_vec(vec)))
        _storage._db_ai_store_embeddings(items)
        done += len(batch)
    return done


def _iter_embeddings(model):
    after = 0
    while True:
        chunk = _storage._db_ai_embedding_chunk(model, after, 500)
        if not chunk:
            return
        yield from chunk
        after = chunk[-1][0]


def ask_history(question: str, previous: str = "", allow_cloud: bool = False,
                contacts: dict | None = None) -> dict:
    """Geçmişe sor (RAG): yerel gömme + kaynaklı yanıt.

    Web'de etkileşimli üç yollu onay yoktur: bağlamda şifreli satır varsa
    izin yoksa isteği baştan reddeder (tam-gizli ya da tam-açık).
    """
    s = settings()
    contacts = contacts or {}
    index_pending(s)
    model = s["embed_model"]
    query = rag_query_text(question, previous)
    qvec = ollama_embed(s, [embed_query_text(model, query)])[0]
    rows = ((msg_id, vec) for msg_id, _j, _s, _b, _t, _m, vec
            in _iter_embeddings(model))
    hits = top_k(pack_vec(qvec), rows, k=RAG_TOP_K, min_score=RAG_MIN_SCORE)
    ids = [msg_id for _score, msg_id in hits]
    context = (_storage._db_ai_context(ids, RAG_BEFORE, RAG_AFTER)
               if ids else [])
    if not context:
        return {"text": "Bu soruyla ilgili bir mesaj bulunamadı. Farklı "
                        "kelimelerle sormayı deneyin.",
                "sources": [], "provider": s.get("provider")}
    # Bağlamda şifreli satır varsa buluta gitmeden önce izin şart.
    has_secret = any(r[7] for r in context)
    provider = _gate(s, sensitive=bool(has_secret), allow_cloud=allow_cloud)
    labels = {jid: _label(jid, contacts) for jid in {r[1] for r in context}}
    ctx, sources = build_rag_context(
        context, {msg_id: i for i, msg_id in enumerate(ids)}, labels,
        max_chars=transcript_budget(s))
    if not ctx:
        return {"text": "Eşleşen mesajlar gönderilebilecek metin içermiyor.",
                "sources": [], "provider": provider}
    system = rag_system(s["target_language"],
                        datetime.now().strftime("%Y-%m-%d"))
    answer = chat(s, system, rag_user(ctx, question), max_tokens=2000)
    cited = [n for n in cited_numbers(answer) if 1 <= n <= len(sources)]
    picked = ([sources[n - 1] for n in cited] if cited
              else [x for x in sources if x.get("hit")])
    return {"text": answer, "provider": provider, "sources": picked}


def assistant(history: list, allow_cloud: bool = False) -> dict:
    """✨ Sohbet paneli: araçsız, düz konuşma (asistan ajanı web v1 dışı)."""
    s = settings()
    provider = _gate(s, sensitive=False, allow_cloud=allow_cloud)
    system = ("Sen bir XMPP istemcisinin yerleşik asistanısın. Kullanıcıya "
              f"{s['target_language']} dilinde kısa ve net yanıt ver. "
              "Sohbet içeriği verilmedikçe kişisel bilgi bilmezsin.")
    hist = [(h.get("role", "user"), h.get("text", "")) for h in history
            if h.get("text")]
    if not hist:
        return {"text": "", "provider": provider}
    return {"text": chat(s, system, hist[-1][1], history=hist[:-1],
                         max_tokens=1200), "provider": provider}
