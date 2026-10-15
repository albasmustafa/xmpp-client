"""SQLite mesaj ve tepki deposu (Faz 1 yaprak modülü).

Bağlantı tekil durumu (_db_conn) ve yol sabiti (_DB_PATH) facade
uzayında yaşar; erişim çağrı sırasında yapılır. Bağlantı
check_same_thread=False ile açılır; tüm işlemler _db_lock altında
serileştirilir (GUI + REST/webhook worker thread'leri ortak kullanır).
"""
import sqlite3
import threading
from datetime import datetime

from .constants import _log

# ── SQLite mesaj veritabanı ───────────────────────────────────────────────

_db_lock = threading.Lock()
STORED_AT_FMT = "%Y-%m-%dT%H:%M:%S"     # messages.stored_at biçimi


def _init_db():
    import xmpp as _app
    conn = sqlite3.connect(_app._DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jid TEXT NOT NULL,
        sender TEXT,
        body TEXT,
        is_me INTEGER,
        timestamp TEXT,
        tag TEXT,
        oob TEXT DEFAULT '',
        encrypted INTEGER DEFAULT 0,
        mid TEXT DEFAULT '',
        local_path TEXT DEFAULT '',
        reply_id TEXT DEFAULT '',
        reply_sender TEXT DEFAULT '',
        reply_body TEXT DEFAULT ''
    )""")
    # stored_at: kayıt anının tam tarihi (timestamp yalnız "SS:DD" tutar);
    # eski satırlarda boştur. Yanıt bekleyen soruların yaşı buradan gelir.
    for col in ("reply_id", "reply_sender", "reply_body", "stored_at"):
        if col not in {r[1] for r in conn.execute("PRAGMA table_info(messages)")}:
            conn.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT DEFAULT ''")
    conn.execute("""CREATE TABLE IF NOT EXISTS reactions (
        jid TEXT NOT NULL,
        mid TEXT NOT NULL,
        emoji TEXT NOT NULL,
        sender TEXT NOT NULL,
        PRIMARY KEY (jid, mid, emoji, sender)
    )""")
    cols = {row[1] for row in
            conn.execute("PRAGMA table_info(messages)").fetchall()}
    if "local_path" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN local_path TEXT DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_jid ON messages(jid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_ts ON messages(timestamp)")
    conn.execute("""CREATE TABLE IF NOT EXISTS plugins (
        name TEXT PRIMARY KEY,
        path TEXT NOT NULL,
        enabled INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS webhooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        events TEXT DEFAULT 'message',
        enabled INTEGER DEFAULT 1
    )""")
    # AI türetilmiş verisi: mesaj gömmeleri (anlamsal arama) ve pahalı
    # sonuç önbelleği (ses→metin, görsel açıklama). Kaynak mesaj silinir ya
    # da değişirse türetilmiş satır da silinir (aşağıdaki mutasyonlar).
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_embeddings (
        msg_id INTEGER PRIMARY KEY,
        jid TEXT NOT NULL,
        model TEXT NOT NULL,
        vec BLOB NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_emb_jid ON ai_embeddings(jid)")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_cache (
        key TEXT PRIMARY KEY,
        jid TEXT NOT NULL DEFAULT '',
        value TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def _get_db():
    import xmpp as _app
    with _db_lock:
        if _app._db_conn is None:
            _app._db_conn = _init_db()
        return _app._db_conn

def _db_store_msg(jid, sender, body, is_me, timestamp, tag, oob="", encrypted=False,
                  mid="", local_path="", reply_id="", reply_sender="", reply_body=""):
    try:
        db = _get_db()
        with _db_lock:
            db.execute(
                "INSERT INTO messages (jid, sender, body, is_me, timestamp, tag, oob, "
                "encrypted, mid, local_path, reply_id, reply_sender, reply_body, "
                "stored_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (jid, sender, body, int(is_me), timestamp, tag, oob, int(encrypted),
                 mid, local_path, reply_id, reply_sender, reply_body,
                 datetime.now().strftime(STORED_AT_FMT)))
            db.commit()
    except Exception:
        _log.error("Mesaj DB'ye yazılamadı (jid=%s)", jid, exc_info=True)


def _db_update_msg_body(jid, mid, new_body):
    """Sohbet kapsamlı gövde güncellemesi (düzeltme/silme) — [2J.a].

    mid gönderici-kontrollü ve sohbetler arası benzersiz DEĞİLDİR; kalıcı
    mutasyon (jid, mid) ile kapsamlanır ki başka bir sohbetin aynı-mid
    satırı değişmesin. Bellek mutasyonu zaten JID-kapsamlıdır.
    """
    if not (jid and mid):
        return
    try:
        db = _get_db()
        with _db_lock:
            db.execute("UPDATE messages SET body=? WHERE jid=? AND mid=?",
                       (new_body, jid, mid))
            # Eski gövdenin gömmesi bayatladı (düzeltme) ya da artık yok
            # sayılmalı (geri çekme): yeniden indekslenene kadar düşür.
            db.execute("DELETE FROM ai_embeddings WHERE msg_id IN "
                       "(SELECT id FROM messages WHERE jid=? AND mid=?)",
                       (jid, mid))
            db.commit()
    except Exception:
        _log.error("Mesaj gövdesi güncellenemedi (jid=%s, mid=%s)", jid, mid,
                   exc_info=True)

def _db_update_msg_reply(jid, mid, reply_id, reply_sender, reply_body):
    """Giden mesajın yanıt (alıntı) alanlarını sohbet kapsamlı güncelle — [2J.a]."""
    if not (jid and mid):
        return
    try:
        db = _get_db()
        with _db_lock:
            db.execute("UPDATE messages SET reply_id=?, reply_sender=?, reply_body=? "
                       "WHERE jid=? AND mid=?",
                       (reply_id, reply_sender, reply_body, jid, mid))
            db.commit()
    except Exception:
        _log.error("Yanıt bilgisi güncellenemedi (jid=%s, mid=%s)", jid, mid,
                   exc_info=True)


def _db_save_reaction(jid, mid, emoji, sender, add=True):
    """Bir tepkiyi kalıcı hale getir (add=False → kaldır)."""
    if not (jid and mid and emoji and sender):
        return
    try:
        db = _get_db()
        with _db_lock:
            if add:
                db.execute("INSERT OR IGNORE INTO reactions (jid, mid, emoji, sender) "
                           "VALUES (?, ?, ?, ?)", (jid, mid, emoji, sender))
            else:
                db.execute("DELETE FROM reactions WHERE jid=? AND mid=? AND emoji=? "
                           "AND sender=?", (jid, mid, emoji, sender))
            db.commit()
    except Exception:
        _log.error("Tepki kaydedilemedi (mid=%s)", mid, exc_info=True)


def _db_clear_my_reactions(jid, mid, sender="Ben"):
    """Kendi tepkilerimi bu mesaj için sil (yeniden yazılacak)."""
    try:
        db = _get_db()
        with _db_lock:
            db.execute("DELETE FROM reactions WHERE jid=? AND mid=? AND sender=?",
                       (jid, mid, sender))
            db.commit()
    except Exception:
        pass


def _db_clear_reactions_mid(jid, mid):
    """Bir mesaj silindiğinde tepkilerini de temizle."""
    try:
        db = _get_db()
        with _db_lock:
            db.execute("DELETE FROM reactions WHERE jid=? AND mid=?", (jid, mid))
            db.commit()
    except Exception:
        pass


def _db_load_reactions(jid):
    """{mid: {emoji: [sender, ...]}} olarak kayıtlı tepkileri yükle."""
    result: dict = {}
    try:
        db = _get_db()
        with _db_lock:
            rows = db.execute("SELECT mid, emoji, sender FROM reactions WHERE jid=?",
                              (jid,)).fetchall()
        for mid, emoji, sender in rows:
            result.setdefault(mid, {}).setdefault(emoji, []).append(sender)
    except Exception:
        _log.error("Tepkiler yüklenemedi (jid=%s)", jid, exc_info=True)
    return result


def _db_load_msgs(jid, limit=200):
    try:
        db = _get_db()
        with _db_lock:
            rows = db.execute(
                "SELECT sender, body, is_me, timestamp, tag, oob, encrypted, "
                "local_path, mid, reply_id, reply_sender, reply_body "
                "FROM messages WHERE jid=? ORDER BY id DESC LIMIT ?", (jid, limit)).fetchall()
        rows.reverse()
        return [(r[0], r[1], bool(r[2]), r[3], r[4], r[5], bool(r[6]), r[7] or "",
                 r[8] or "", r[9] or "", r[10] or "", r[11] or "")
                for r in rows]
    except Exception:
        _log.error("Mesajlar yüklenemedi (jid=%s)", jid, exc_info=True)
        return []

def _db_search_msgs(query, limit=100):
    try:
        db = _get_db()
        with _db_lock:
            rows = db.execute(
                "SELECT jid, sender, body, timestamp FROM messages "
                "WHERE body LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit)).fetchall()
        return rows
    except Exception:
        _log.error("Mesaj araması başarısız (query=%s)", query, exc_info=True)
        return []

# Her sohbette benim son mesajımdan sonra gelen (sistem olmayan) satırlar;
# parametre: tarama penceresi (son N satır). MCP sunucusu da kullanır.
UNANSWERED_SQL = (
    "WITH last_me AS (SELECT jid, MAX(id) AS mx FROM messages "
    "WHERE is_me = 1 GROUP BY jid) "
    "SELECT m.id, m.jid, m.sender, m.body, "
    "COALESCE(m.stored_at, ''), m.mid, m.encrypted "
    "FROM messages m LEFT JOIN last_me l ON l.jid = m.jid "
    "WHERE m.id > (SELECT COALESCE(MAX(id), 0) FROM messages) - ? "
    "AND m.is_me = 0 AND COALESCE(m.tag, '') != 'sys' "
    "AND m.id > COALESCE(l.mx, 0) ORDER BY m.id")


def _db_unanswered(scan_limit=5000):
    """Her sohbette son giden mesajımdan SONRA gelen mesajlar.

    Yanıt bekleyen soruların girdisi (xmppcore/questions). Yalnız son
    `scan_limit` satıra bakılır; sistem satırları hariç.
    Dönüş: [(id, jid, sender, body, stored_at, mid, encrypted)] — id artan.
    """
    try:
        db = _get_db()
        with _db_lock:
            return db.execute(UNANSWERED_SQL, (int(scan_limit),)).fetchall()
    except Exception:
        _log.error("Yanıt bekleyen mesajlar okunamadı", exc_info=True)
        return []

def _db_clear_chat(jid):
    try:
        db = _get_db()
        with _db_lock:
            db.execute("DELETE FROM messages WHERE jid=?", (jid,))
            db.execute("DELETE FROM reactions WHERE jid=?", (jid,))
            db.execute("DELETE FROM ai_embeddings WHERE jid=?", (jid,))
            db.execute("DELETE FROM ai_cache WHERE jid=?", (jid,))
            db.commit()
    except Exception:
        _log.error("Sohbet temizlenemedi (jid=%s)", jid, exc_info=True)

def _db_clear_all():
    try:
        db = _get_db()
        with _db_lock:
            db.execute("DELETE FROM messages")
            db.execute("DELETE FROM reactions")
            db.execute("DELETE FROM ai_embeddings")
            db.execute("DELETE FROM ai_cache")
            db.commit()
    except Exception:
        _log.error("Tüm mesajlar temizlenemedi", exc_info=True)


# ── AI türetilmiş verisi ──────────────────────────────────────────────────

def _db_ai_pending(model, limit=64, skip_bodies=()):
    """Bu modelle gömmesi olmayan mesajlar: [(id, jid, sender, body)].

    `skip_bodies` (ör. geri çekilmiş yer tutucusu) SQL'de elenir; böylece
    indekslenemeyen satırlar aynı partide sonsuza dek geri gelmez.
    """
    try:
        db = _get_db()
        skip = tuple(skip_bodies)
        marks = ",".join("?" * len(skip))
        skip_sql = f"AND m.body NOT IN ({marks}) " if skip else ""
        with _db_lock:
            return db.execute(
                "SELECT m.id, m.jid, m.sender, m.body FROM messages m "
                "LEFT JOIN ai_embeddings e ON e.msg_id = m.id AND e.model = ? "
                "WHERE e.msg_id IS NULL AND COALESCE(m.tag, '') != 'sys' "
                "AND length(trim(COALESCE(m.body, ''))) >= 2 "
                f"{skip_sql}"
                "ORDER BY m.id DESC LIMIT ?",
                (model, *skip, limit)).fetchall()
    except Exception:
        _log.error("İndekslenecek mesajlar okunamadı", exc_info=True)
        return []


def _db_ai_pending_count(model, skip_bodies=()):
    try:
        db = _get_db()
        skip = tuple(skip_bodies)
        marks = ",".join("?" * len(skip))
        skip_sql = f"AND m.body NOT IN ({marks}) " if skip else ""
        with _db_lock:
            return db.execute(
                "SELECT COUNT(*) FROM messages m "
                "LEFT JOIN ai_embeddings e ON e.msg_id = m.id AND e.model = ? "
                "WHERE e.msg_id IS NULL AND COALESCE(m.tag, '') != 'sys' "
                "AND length(trim(COALESCE(m.body, ''))) >= 2 "
                f"{skip_sql}", (model, *skip)).fetchone()[0]
    except Exception:
        _log.error("İndeks sayımı başarısız", exc_info=True)
        return 0


def _db_ai_store_embeddings(items):
    """items: [(msg_id, jid, model, vec_blob)] — mesaj hâlâ varsa yazılır."""
    if not items:
        return
    try:
        db = _get_db()
        with _db_lock:
            # İndeksleme sırasında silinen mesajın gömmesi yetim kalmasın.
            db.executemany(
                "INSERT OR REPLACE INTO ai_embeddings (msg_id, jid, model, vec) "
                "SELECT ?, ?, ?, ? WHERE EXISTS "
                "(SELECT 1 FROM messages WHERE id = ?)",
                [(mid, jid, model, vec, mid) for mid, jid, model, vec in items])
            db.commit()
    except Exception:
        _log.error("Gömmeler kaydedilemedi", exc_info=True)


def _db_ai_embedding_chunk(model, after_id=0, limit=500):
    """Kilidi uzun tutmamak için parça parça okuma (msg_id artan).

    Dönüş: [(msg_id, jid, sender, body, timestamp, mid, vec_blob)].
    """
    try:
        db = _get_db()
        with _db_lock:
            return db.execute(
                "SELECT e.msg_id, m.jid, m.sender, m.body, m.timestamp, "
                "m.mid, e.vec FROM ai_embeddings e "
                "JOIN messages m ON m.id = e.msg_id "
                "WHERE e.model = ? AND e.msg_id > ? "
                "ORDER BY e.msg_id LIMIT ?",
                (model, after_id, limit)).fetchall()
    except Exception:
        _log.error("Gömmeler okunamadı", exc_info=True)
        return []


def _db_ai_context(msg_ids, before=2, after=1):
    """Eşleşen mesajlar + aynı sohbetteki komşuları (geçmişe sor / RAG).

    Dönüş: [(id, jid, sender, body, timestamp, tag, mid, encrypted, is_me)]
    — tekil, (jid, id) sıralı. Silinmiş mesaj kimliği sessizce atlanır.
    """
    cols = "id, jid, sender, body, timestamp, tag, mid, encrypted, is_me"
    out = {}
    try:
        db = _get_db()
        with _db_lock:
            for msg_id in msg_ids:
                row = db.execute("SELECT jid FROM messages WHERE id=?",
                                 (msg_id,)).fetchone()
                if row is None:
                    continue
                jid = row[0]
                rows = db.execute(
                    f"SELECT {cols} FROM messages WHERE jid=? AND id<=? "
                    "ORDER BY id DESC LIMIT ?",
                    (jid, msg_id, int(before) + 1)).fetchall()
                if after > 0:
                    rows += db.execute(
                        f"SELECT {cols} FROM messages WHERE jid=? AND id>? "
                        "ORDER BY id ASC LIMIT ?",
                        (jid, msg_id, int(after))).fetchall()
                for r in rows:
                    out[r[0]] = r
    except Exception:
        _log.error("AI bağlam mesajları okunamadı", exc_info=True)
        return []
    return sorted(out.values(), key=lambda r: (r[1], r[0]))


def _db_ai_cache_get(key):
    try:
        db = _get_db()
        with _db_lock:
            row = db.execute("SELECT value FROM ai_cache WHERE key=?",
                             (key,)).fetchone()
        return row[0] if row else None
    except Exception:
        _log.error("AI önbelleği okunamadı", exc_info=True)
        return None


def _db_ai_cache_set(key, jid, value):
    try:
        db = _get_db()
        with _db_lock:
            db.execute("INSERT OR REPLACE INTO ai_cache (key, jid, value) "
                       "VALUES (?, ?, ?)", (key, jid or "", value))
            db.commit()
    except Exception:
        _log.error("AI önbelleği yazılamadı", exc_info=True)
