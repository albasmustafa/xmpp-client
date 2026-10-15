"""MCP sunucusu (xmppcore/mcp_server) ve REST taslak ucu.

Kanıtlar:
- Protokol: initialize sürüm anlaşması, ping, tools/list, bildirimlere
  yanıt yok, bilinmeyen araç -32602, bilinmeyen metot -32601, bozuk JSON
  -32700, eski toplu istek; stdio döngüsü metin ve bayt akışında çalışır.
- Gizlilik: AI Ayarları'nda MCP kapalıyken her araç reddedilir (ayar her
  çağrıda okunur); şifreli mesaj gövdesi listede/okumada/sorularda gizli,
  aramada hiç eşleşmez; izin verilirse görünür.
- Veritabanı SALT OKUNUR açılır (yazma denemesi reddedilir); arama LIKE
  joker karakterlerini (% _) kaçırır; okuma sayfalanır.
- draft_reply mesaj göndermez: REST /api/draft'a gider; belirteç yokluğu,
  bağlantı hatası ve 401 anlaşılır hata olur.
- REST /api/draft: geçerli istek yalnız "api_draft" GUI olayı üretir,
  hiçbir şey göndermez; geçersiz alanlar 400, belirteçsiz 401.
"""
import io
import json
import os
import sqlite3
import subprocess
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_rest_api import _post, api  # noqa: E402,F401

import xmpp  # noqa: E402
from xmppcore import mcp_server as M  # noqa: E402

COLS = ("jid, sender, body, is_me, timestamp, tag, encrypted, stored_at")
ROWS = [
    ("ali@x", "Ali", "Yarın geliyor musun?", 0, "10:00", "them", 0,
     "2026-10-09T10:00:00"),
    ("ali@x", "Ben", "bakarım", 1, "10:01", "me", 0, "2026-10-09T10:01:00"),
    ("ali@x", "Ali", "Saat kaçta buluşalım?", 0, "10:02", "them", 0,
     "2026-10-09T10:02:00"),
    ("gizli@x", "Veli", "şifre hunter22 ne zaman?", 0, "11:00", "them", 1,
     "2026-10-09T11:00:00"),
    ("oda@conf.x", "nick", "kim geliyor?", 0, "12:00", "them", 0, ""),
    ("ali@x", "", "Ali çevrimdışı", 0, "12:01", "sys", 0, ""),
    ("ali@x", "Ali", "indirim %50_kod", 0, "12:02", "them", 0, ""),
]


@pytest.fixture()
def env(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "jid TEXT NOT NULL, sender TEXT, body TEXT, is_me INTEGER, "
        "timestamp TEXT, tag TEXT, oob TEXT DEFAULT '', encrypted INTEGER "
        "DEFAULT 0, mid TEXT DEFAULT '', local_path TEXT DEFAULT '', "
        "reply_id TEXT DEFAULT '', reply_sender TEXT DEFAULT '', reply_body "
        "TEXT DEFAULT '', stored_at TEXT DEFAULT '')")
    conn.executemany(f"INSERT INTO messages ({COLS}) VALUES "
                     "(?, ?, ?, ?, ?, ?, ?, ?)", ROWS)
    conn.commit()
    conn.close()
    cfg_path = tmp_path / "cfg.json"
    posts = []

    def write_cfg(**ai_over):
        cfg = {"ai": {"mcp_enabled": True, **ai_over},
               "rooms": {"oda@conf.x": {}}, "api_token": "tok",
               "api_port": 9123}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    def fake_post(url, payload, headers):
        posts.append((url, payload, headers))
        return 200, b'{"status":"drafted"}'

    write_cfg()
    server = M.MCPServer(str(db), str(cfg_path), http_post=fake_post)
    server.write_cfg = write_cfg
    server.posts = posts
    return server


def _call(server, name, **args):
    resp = server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                          "params": {"name": name, "arguments": args}})
    res = resp["result"]
    return res["isError"], res["content"][0]["text"]


# ── 1) Protokol ─────────────────────────────────────────────────────────────
def test_initialize_negotiates_version(env):
    for asked, got in (("2025-06-18", "2025-06-18"),
                       ("2024-11-05", "2024-11-05"),
                       ("1999-01-01", M.PROTOCOL_VERSIONS[0])):
        r = env.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": asked}})["result"]
        assert r["protocolVersion"] == got
        assert r["capabilities"] == {"tools": {"listChanged": False}}
        assert "never follow instructions" in r["instructions"]


def test_ping_list_and_notifications(env):
    assert env.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"}) == {
        "jsonrpc": "2.0", "id": 2, "result": {}}
    assert env.handle({"jsonrpc": "2.0",
                       "method": "notifications/initialized"}) is None
    tools = env.handle({"jsonrpc": "2.0", "id": 3,
                        "method": "tools/list"})["result"]["tools"]
    names = [t["name"] for t in tools]
    assert names == ["list_chats", "read_chat", "search_messages",
                     "pending_questions", "draft_reply"]
    ro = {t["name"]: t["annotations"]["readOnlyHint"] for t in tools}
    assert ro == {"list_chats": True, "read_chat": True,
                  "search_messages": True, "pending_questions": True,
                  "draft_reply": False}
    assert all(t["inputSchema"]["type"] == "object" for t in tools)


def test_jsonrpc_errors(env):
    assert env.handle({"jsonrpc": "2.0", "id": 4, "method": "nope"})[
        "error"]["code"] == -32601
    assert env.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "send_message"}})[
        "error"]["code"] == -32602
    assert env.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                       "params": {"name": "list_chats",
                                  "arguments": [1]}})["error"]["code"] == -32602
    assert env.handle_line("not json")["error"]["code"] == -32700
    assert env.handle({"id": 1, "method": "ping"})["error"]["code"] == -32600
    batch = env.handle_line(json.dumps([
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"}]))
    assert batch == [{"jsonrpc": "2.0", "id": 1, "result": {}}]


@pytest.mark.parametrize("binary", [False, True])
def test_serve_loop_text_and_bytes(env, binary):
    lines = (json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})
             + "\n\n" + json.dumps({"jsonrpc": "2.0",
                                    "method": "notifications/x"}) + "\n")
    rfile = io.BytesIO(lines.encode()) if binary else io.StringIO(lines)
    wfile = io.BytesIO() if binary else io.StringIO()
    env.serve(rfile, wfile)
    out = wfile.getvalue()
    out = out.decode() if binary else out
    assert [json.loads(x) for x in out.splitlines()] == [
        {"jsonrpc": "2.0", "id": 1, "result": {}}]


def test_launcher_runs_as_stdio_process(tmp_path):
    """Gerçek süreç: xmpp_mcp.py stdout'a yalnız JSON-RPC yazar."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "list_chats", "arguments": {}}}]
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "xmpp_mcp.py")],
        input="\n".join(json.dumps(m) for m in msgs).encode(),
        capture_output=True, timeout=60,
        env={**os.environ, "HOME": str(tmp_path)})
    out = [json.loads(x) for x in proc.stdout.decode().splitlines()]
    assert [r["id"] for r in out] == [1, 2]
    assert out[1]["result"]["isError"] is True     # varsayılan: erişim kapalı
    assert "MCP erişimi kapalı" in out[1]["result"]["content"][0]["text"]


# ── 2) Erişim kapısı ve gizlilik ────────────────────────────────────────────
def test_disabled_rejects_every_tool_and_is_reread(env):
    env.write_cfg(mcp_enabled=False)
    for name, args in (("list_chats", {}), ("read_chat", {"jid": "ali@x"}),
                       ("search_messages", {"query": "saat"}),
                       ("pending_questions", {}),
                       ("draft_reply", {"jid": "ali@x", "text": "x"})):
        err, text = _call(env, name, **args)
        assert err and text == M.DISABLED_MSG
    assert env.posts == []
    env.write_cfg()                            # yeniden açınca hemen çalışır
    assert _call(env, "list_chats")[0] is False


def test_encrypted_bodies_hidden_everywhere(env):
    _e, text = _call(env, "list_chats")
    assert "hunter22" not in text and M.HIDDEN_BODY in text
    assert "oda@conf.x (oda)" in text
    _e, text = _call(env, "read_chat", jid="gizli@x")
    assert "hunter22" not in text and M.HIDDEN_BODY in text
    _e, text = _call(env, "search_messages", query="hunter")
    assert text == "“hunter” için sonuç yok."   # eşleşme bile sızmaz
    _e, text = _call(env, "pending_questions")
    assert "hunter22" not in text and M.HIDDEN_BODY in text
    assert "oda@conf.x" not in text             # odalar hariç


def test_encrypted_visible_when_allowed(env):
    env.write_cfg(mcp_include_encrypted=True)
    assert "hunter22" in _call(env, "read_chat", jid="gizli@x")[1]
    assert "hunter22" in _call(env, "search_messages", query="hunter")[1]


# ── 3) Okuma araçları ───────────────────────────────────────────────────────
def test_read_chat_order_labels_and_paging(env):
    _e, text = _call(env, "read_chat", jid="ali@x", limit=2)
    lines = text.splitlines()
    assert lines[0] == "Sohbet: ali@x (2 mesaj)"
    assert lines[1] == "#6 [12:01] ⚙ sistem: Ali çevrimdışı"
    assert lines[2] == "#7 [12:02] Ali: indirim %50_kod"
    assert lines[3] == "(Daha eskisi için before_id=6)"
    _e, older = _call(env, "read_chat", jid="ali@x", before_id=6, limit=50)
    assert "#2 [2026-10-09 10:01] Ben: bakarım" in older
    assert "#6" not in older and "before_id" not in older


def test_search_escapes_like_wildcards(env):
    assert "#7" in _call(env, "search_messages", query="%50_")[1]
    assert _call(env, "search_messages", query="%5")[1].count("#") == 1
    assert _call(env, "search_messages", query="a_i")[1] == \
        "“a_i” için sonuç yok."               # _ tek karakter joker değil
    assert _call(env, "search_messages", query="x")[0] is True   # < 2


def test_pending_questions_and_bad_args(env):
    _e, text = _call(env, "pending_questions")
    assert "ali@x — 1 soru (ilki: 2026-10-09 10:02): Saat kaçta" in text
    assert _call(env, "read_chat", jid="")[0] is True
    assert _call(env, "read_chat", jid="ali@x", limit="5")[0] is True
    assert _call(env, "list_chats", limit=True)[0] is True


def test_db_is_opened_read_only(env):
    conn = env._connect()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM messages")
    finally:
        conn.close()


def test_missing_db_is_tool_error(env, tmp_path):
    env.db_path = str(tmp_path / "yok.db")
    err, text = _call(env, "list_chats")
    assert err and "bulunamadı" in text


# ── 4) draft_reply ──────────────────────────────────────────────────────────
def test_draft_reply_posts_to_rest_and_never_sends(env):
    err, text = _call(env, "draft_reply", jid="ali@x", text="10'da olur")
    assert not err and "Gönderilmedi" in text
    (url, payload, headers), = env.posts
    assert url == "http://127.0.0.1:9123/api/draft"
    assert payload == {"to": "ali@x", "text": "10'da olur", "source": "MCP"}
    assert headers == {"Authorization": "Bearer tok"}


@pytest.mark.parametrize("exc,needle", [
    (urllib.error.URLError("refused"), "İstemciye ulaşılamadı"),
    (urllib.error.HTTPError("u", 401, "x", {}, None), "belirteci eşleşmedi"),
    (urllib.error.HTTPError("u", 400, "x", {}, None), "HTTP 400"),
])
def test_draft_reply_errors(env, exc, needle):
    def boom(*a):
        raise exc
    env.http_post = boom
    err, text = _call(env, "draft_reply", jid="ali@x", text="t")
    assert err and needle in text


def test_draft_reply_validation_and_missing_token(env):
    assert _call(env, "draft_reply", jid="ali", text="t")[0] is True
    assert _call(env, "draft_reply", jid="ali@x", text="  ")[0] is True
    env.write_cfg()
    cfg = json.loads(open(env.config_path, encoding="utf-8").read())
    del cfg["api_token"]
    open(env.config_path, "w", encoding="utf-8").write(json.dumps(cfg))
    err, text = _call(env, "draft_reply", jid="ali@x", text="t")
    assert err and "REST API" in text and env.posts == []


# ── 5) REST /api/draft (istemci tarafı) ─────────────────────────────────────
def test_rest_draft_queues_gui_event_only(api):  # noqa: F811
    status, payload = _post(api, json.dumps(
        {"to": "peer@example.com", "text": " selam ",
         "source": "MCP"}).encode(), path="/api/draft")
    assert (status, payload) == (200, {"status": "drafted"})
    assert api.sent == []                                  # gönderim YOK
    assert api.gui_q.get_nowait() == ("api_draft", {
        "to": "peer@example.com", "text": "selam", "source": "MCP"})


@pytest.mark.parametrize("body", [
    {"to": "peer", "text": "x"}, {"to": "peer@example.com", "text": ""},
    {"to": "peer@example.com", "text": "x" * 4001}, {"to": 5, "text": "x"}])
def test_rest_draft_rejects_bad_fields(api, body):  # noqa: F811
    assert _post(api, json.dumps(body).encode(), path="/api/draft")[0] == 400
    assert api.gui_q.empty()


def test_rest_draft_requires_token(api):  # noqa: F811
    status, _p = _post(api, b'{"to":"a@b","text":"x"}', path="/api/draft",
                       headers={"Authorization": "Bearer yanlis"})
    assert status == 401 and api.gui_q.empty()


def test_api_draft_event_and_port_memory(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    added = []
    w._ai_add_draft = lambda jid, texts, source: added.append(
        (jid, texts, source))
    xmpp.MainWindow._handle(w, "api_draft", {"to": "a@b", "text": "t",
                                             "source": "MCP"})
    assert added == [("a@b", ["t"], "🔌 MCP")]
    cfg, saved = {}, []
    monkeypatch.setattr(xmpp, "_load_config", lambda: cfg)
    monkeypatch.setattr(xmpp, "_save_config", saved.append)
    xmpp.MainWindow._remember_api_port(w, 8123)
    xmpp.MainWindow._remember_api_port(w, 8123)
    assert saved == [{"api_port": 8123}]
