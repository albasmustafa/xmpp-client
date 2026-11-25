"""Web arayüzü: gönderim/düzeltme başarısız olunca yazılan metin kaybolmaz.

Hata: `sendCurrent` yanıta bakmadan kutuyu temizliyordu. WebSocket koptuğunda
`wsSend` hata metni olmadan `{ok: false}` döndürdüğü için ne uyarı çıkıyor ne de
metin kalıyordu — mesaj sessizce yok oluyordu. app.js'teki gerçek fonksiyonlar
küçük bir DOM taklidiyle node'da çalıştırılır (node yoksa test atlanır).
"""
import json
import shutil
import subprocess

import pytest

from webapp import server as srv

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node bulunamadı")


def _function_source(js: str, name: str) -> str:
    """app.js'teki üst düzey fonksiyonun kaynağı (`async` dahil, `\\n}` ile biter)."""
    at = js.index(f"function {name}(")
    start = js.rfind("\n", 0, at) + 1
    end = js.index("\n}\n", at) + 3
    return js[start:end]


HARNESS = r"""
const box = {value: ""};
const $ = (id) => ({composer: box}[id]);
const _t = (s) => s;
const S = {active: "ali@x", contacts: new Map([["ali@x", {enc: "none"}]]),
           editing: null, reply: null};
let toasts = [], sent = [], cleared = 0, reply = null, duringSend = null;
function toast(msg, err) { toasts.push([msg, !!err]); }
function clearReplyEdit() { cleared++; S.reply = null; S.editing = null; }
function showLeakDialog() { toasts.push(["leak", true]); }
async function wsSend(cmd, args) {
  sent.push(cmd);
  if (duringSend) duringSend();
  return reply;
}
%FUNCS%
async function run(name, {text, res, editing = null, during = null}) {
  box.value = text; reply = res; duringSend = during;
  toasts = []; sent = []; cleared = 0;
  S.editing = editing; S.reply = editing ? null : {mid: "r1"};
  await sendCurrent();
  return {name, box: box.value, toasts, sent, cleared,
          reply_kept: S.reply !== null, editing_kept: S.editing !== null};
}
(async () => {
  const out = [];
  out.push(await run("disconnected", {text: "merhaba", res: {ok: false}}));
  out.push(await run("server_error", {text: "merhaba",
                                      res: {ok: false, error: "Bağlı değil"}}));
  out.push(await run("success", {text: "merhaba", res: {ok: true, mid: "m1"}}));
  out.push(await run("typed_while_sending", {text: "merhaba", res: {ok: true},
                     during: () => { box.value = "merhaba dünya"; }}));
  out.push(await run("correct_fails", {text: "düzeltme", res: {ok: false, error: "x"},
                     editing: {to: "ali@x", mid: "m0"}}));
  out.push(await run("correct_ok", {text: "düzeltme", res: {ok: true},
                     editing: {to: "ali@x", mid: "m0"}}));
  console.log(JSON.stringify(out));
})();
"""


def _run_scenarios():
    js = (srv.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    funcs = [_function_source(js, "sendCurrent")]
    if "function takeSentText(" in js:
        funcs.append(_function_source(js, "takeSentText"))
    script = HARNESS.replace("%FUNCS%", "\n".join(funcs))
    res = subprocess.run([NODE, "-e", script], capture_output=True, text=True,
                         timeout=30)
    assert res.returncode == 0, res.stderr
    return {r["name"]: r for r in json.loads(res.stdout)}


def test_failed_send_keeps_text_and_reply_context():
    r = _run_scenarios()
    d = r["disconnected"]
    assert d["box"] == "merhaba"                      # metin kutuda kalır
    assert d["reply_kept"] and d["cleared"] == 0      # yanıt bağlamı da
    assert d["toasts"] == [["Bağlantı koptu — yeniden bağlanıyor…", True]]
    e = r["server_error"]
    assert e["box"] == "merhaba" and e["reply_kept"]
    assert e["toasts"] == [["Bağlı değil", True]]


def test_successful_send_clears_only_the_sent_text():
    r = _run_scenarios()
    ok = r["success"]
    assert ok["box"] == "" and ok["cleared"] == 1 and not ok["toasts"]
    # Yanıt beklenirken yazılan devam metni silinmez
    assert r["typed_while_sending"]["box"] == "dünya"


def test_failed_correction_keeps_text_and_edit_mode():
    r = _run_scenarios()
    f = r["correct_fails"]
    assert f["sent"] == ["correct"]
    assert f["box"] == "düzeltme" and f["editing_kept"] and f["cleared"] == 0
    assert f["toasts"] == [["x", True]]
    ok = r["correct_ok"]
    assert ok["box"] == "" and ok["cleared"] == 1
