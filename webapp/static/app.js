/* xmpp.py web arayüzü — vanilla JS, derleme adımı yok.
 *
 * Masaüstü istemcinin davranışını izler: olaylar WS ile gelir, komutlar
 * WS ile gider; geçmiş/AI/ayarlar REST uçlarındandır. Sunucu tarafı
 * köprüsü (webapp/bridge.py) MainWindow'nun Tk'siz karşılığıdır.
 */
"use strict";

/* ── yardımcılar ─────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
           "'": "&#39;"}[c]));
const LINK_RE = /\bhttps?:\/\/[^\s<>"']+/g;

/* ── arayüz dili ─────────────────────────────────────────────────────────
 * Masaüstüyle aynı gettext düzeni: Türkçe metin anahtardır, katalog
 * sunucudan gelir (/api/i18n; xmppcore/locale_*.py). Metin `_t(…)` ile,
 * şablon `fmt(…, n)` ile çevrilir; `{0}`/`{1}` sırası çeviride değişebilir.
 * Yeni metin bu iki çağrıya düz çift tırnaklı sabitle yazılır: sunucu ve
 * testler anahtarları bu kalıptan okur. */
const I18N = {lang: "tr", languages: {}, catalog: {}};
const _t = (text) => I18N.catalog[text] ?? text;

function fmt(text, ...args) {
  let auto = 0;
  return _t(text).replace(/\{(\d*)\}/g, (_, n) =>
    String(args[n === "" ? auto++ : Number(n)] ?? ""));
}

async function loadI18n() {
  try {
    const res = await fetch("/api/i18n",
                            {headers: {"X-Requested-With": "xmpp-web"}});
    if (res.ok) Object.assign(I18N, await res.json());
  } catch (_) { /* Türkçe kalır */ }
  document.documentElement.lang = I18N.lang;
}

/* index.html'deki sabit metinler: metin düğümleri + placeholder/title */
function translateDom(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const key = n.nodeValue.trim();
    const val = key && I18N.catalog[key];
    if (val) n.nodeValue = n.nodeValue.replace(key, val);
  }
  root.querySelectorAll("[placeholder], [title]").forEach((el) => {
    for (const attr of ["placeholder", "title"]) {
      const val = I18N.catalog[el.getAttribute(attr) || ""];
      if (val) el.setAttribute(attr, val);
    }
  });
}

// Kendi mesajlarımın göndericisi veride "Ben" kalır (DB/tepki eşleşmesi)
const who = (name) => (name === "Ben" ? _t("Ben") : name);

function linkify(body) {
  let html = esc(body);
  html = html.replace(LINK_RE, (u) =>
    `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>`);
  return html;
}

function dayLabel(storedAt) {
  if (!storedAt) return null;
  const d = new Date(storedAt);
  if (isNaN(d)) return null;
  const now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const diff = Math.round((day(now) - day(d)) / 86400000);
  if (diff === 0) return _t("Bugün");
  if (diff === 1) return _t("Dün");
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`;
}

function beep() {
  try {
    const ctx = beep.ctx || (beep.ctx = new AudioContext());
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.value = 660; gain.gain.value = 0.06;
    osc.connect(gain).connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + 0.12);
  } catch (_) { /* ses önemli değil */ }
}

function toast(text, isErr = false) {
  const t = document.createElement("div");
  t.className = "toast" + (isErr ? " err" : "");
  t.innerHTML = esc(text);
  $("toasts").appendChild(t);
  setTimeout(() => t.remove(), isErr ? 6000 : 3500);
}

function toastActions(text, actions) {
  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = esc(text);
  const bar = document.createElement("div");
  bar.className = "t-actions";
  for (const [label, fn] of actions) {
    const b = document.createElement("button");
    b.textContent = label;
    b.onclick = () => { fn(); t.remove(); };
    bar.appendChild(b);
  }
  t.appendChild(bar);
  $("toasts").appendChild(t);
}

/* Bildirim: Android'de sayfa içinden `new Notification` yasaktır; service
 * worker kayıtlıysa onun showNotification'ı kullanılır. */
function showNotification(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    const opts = {body: (body || "").slice(0, 120), icon: "/static/icon-192.png"};
    if (navigator.serviceWorker?.controller) {
      navigator.serviceWorker.ready
        .then((reg) => reg.showNotification(title, opts)).catch(() => {});
    } else {
      try { new Notification(title, opts); } catch (_) { /* desteklenmiyor */ }
    }
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission();
  }
}

/* ── medya ────────────────────────────────────────────────────────────
 * Şifreli dosya (aesgcm://, OMEMO) tarayıcıda çözülemez: /api/media sunucuda
 * çözer, yanıt blob URL'si olarak gösterilir. aesgcm bağlantısı anahtarı
 * taşıdığından metin olarak hiç gösterilmez. */
const AESGCM_RE = /^aesgcm:\/\/\S+$/i;
const IMG_RE = /\.(png|jpe?g|gif|webp|avif|bmp)$/i;
const AUDIO_RE = /\.(wav|ogg|opus|mp3|m4a|flac|aac|webm)$/i;
const VIDEO_RE = /\.(mp4|mov|mkv)$/i;

function mediaOf(m) {
  const body = (m.body || "").trim();
  if (AESGCM_RE.test(m.oob || "")) return {url: m.oob, enc: true};
  if (AESGCM_RE.test(body)) return {url: body, enc: true};
  if (/^https?:\/\//i.test(m.oob || "")) return {url: m.oob, enc: false};
  return null;
}

function urlPath(url) { return url.split("#")[0].split("?")[0]; }

function mediaKind(url) {
  const path = urlPath(url);
  if (IMG_RE.test(path)) return "image";
  if (AUDIO_RE.test(path)) return "audio";
  if (VIDEO_RE.test(path)) return "video";
  return "file";
}

function mediaName(url) {
  try { return decodeURIComponent(urlPath(url).split("/").pop()) || "file"; }
  catch (_) { return "file"; }
}

/* Satırın sunucudaki kimliği: canlı mesajda DB kimliği yoktur, mid vardır */
function refAttrs(m) {
  return (m.mid ? ` data-mid="${esc(m.mid)}"` : "") +
         (m.id ? ` data-id="${esc(m.id)}"` : "");
}

function refQuery(el) {
  const q = new URLSearchParams({jid: S.active || ""});
  if (el.dataset.mid) q.set("mid", el.dataset.mid);
  else if (el.dataset.id) q.set("id", el.dataset.id);
  return q;
}

function refKey(el) {
  return `${S.active}|${el.dataset.mid || ""}|${el.dataset.id || ""}`;
}

async function fetchMedia(el) {
  const key = refKey(el);
  if (S.blobs.has(key)) return S.blobs.get(key);
  const res = await fetch(`/api/media?${refQuery(el)}`, {headers: {
    "X-Requested-With": "xmpp-web", "X-Auth-Token": S.token || ""}});
  if (!res.ok) throw new Error(String(res.status));
  const url = URL.createObjectURL(await res.blob());
  S.blobs.set(key, url);
  return url;
}

function placeMedia(slot, url) {
  const kind = slot.dataset.kind, name = slot.dataset.name || "";
  if (kind === "image") {
    slot.innerHTML = `<a href="${esc(url)}" target="_blank" rel="noopener">` +
      `<img class="preview" src="${esc(url)}" alt="${esc(name)}"></a>`;
  } else if (kind === "audio") {
    slot.innerHTML = `<audio controls src="${esc(url)}"></audio>`;
  } else if (kind === "video") {
    slot.innerHTML = `<video class="preview" controls src="${esc(url)}"></video>`;
  }
}

async function downloadMedia(btn) {
  try {
    const url = await fetchMedia(btn);
    const a = document.createElement("a");
    a.href = url; a.download = btn.dataset.name || "file";
    document.body.appendChild(a); a.click(); a.remove();
  } catch (_) { toast(_t("🔒 Dosya açılamadı."), true); }
}

/* Görsel/ses/video hemen açılır; diğer dosyalar tıklanınca indirilir */
function hydrateMedia(box) {
  box.querySelectorAll(".media-slot:not([data-done])").forEach(async (slot) => {
    slot.dataset.done = "1";
    try { placeMedia(slot, await fetchMedia(slot)); }
    catch (_) { slot.textContent = _t("🔒 Dosya açılamadı."); }
  });
  box.querySelectorAll("[data-download]").forEach((b) => {
    b.onclick = () => downloadMedia(b);
  });
}

/* ── ses → metin ──────────────────────────────────────────────────────── */
async function transcribe(btn) {
  const key = refKey(btn);
  if (S.sttBusy.has(key)) return;
  S.sttBusy.add(key);
  btn.disabled = true;
  btn.textContent = _t("⏳ Yazıya dökülüyor…");
  const body = {jid: S.active};
  if (btn.dataset.mid) body.mid = btn.dataset.mid; else body.id = btn.dataset.id;
  try {
    const {data} = await apiPost("/api/ai/transcribe", body);
    if (typeof data.text === "string") {
      S.stt.set(key, data.text);
      const line = document.createElement("div");
      line.className = "stt-line";
      line.textContent = `📝 ${data.text}`;
      btn.replaceWith(line);
      return;
    }
    toast(data.error || _t("Yanıt alınamadı."), true);
  } finally {
    S.sttBusy.delete(key);
  }
  btn.disabled = false;
  btn.textContent = _t("📝 Yazıya dök");
}

function sttHtml(m) {
  const key = `${S.active}|${m.mid || ""}|${m.id || ""}`;
  const done = S.stt.get(key);
  if (done !== undefined) return `<div class="stt-line">📝 ${esc(done)}</div>`;
  return `<button class="stt-btn" data-stt${refAttrs(m)}>` +
    `${esc(_t("📝 Yazıya dök"))}</button>`;
}

/* ── otomatik çeviri satırı ───────────────────────────────────────────
 * Dil algılama ve çeviri sunucudadır (yalnız yerel model, önbellek
 * masaüstüyle ortak); burada tek tek, en yeniden başlayarak istenir. */
function autoTranslateOn() {
  const ai = S.settings?.ai || {};
  return !!ai.auto_translate && ai.provider === "ollama";
}

function textKey(text) {
  let h = 5381;
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

function trHtml(m) {
  const key = textKey(m.body || "");
  const done = S.tr.get(key);
  if (done === undefined) S.trWant.set(key, m.body);
  return `<div class="tr-line${done ? "" : " hidden"}" data-trk="${key}">` +
    `${done ? "🌐 " + esc(done) : ""}</div>`;
}

async function translateQueue() {
  if (S.trRunning) return;
  S.trRunning = true;
  try {
    while (S.trWant.size) {
      const [key, text] = [...S.trWant.entries()].pop();   // en yeni önce
      S.trWant.delete(key);
      if (S.tr.has(key)) continue;
      let out = "";
      try {
        const {data} = await apiPost("/api/ai/autotranslate", {text});
        out = data.text || "";
      } catch (_) { /* oturum düştü */ }
      S.tr.set(key, out);
      if (!out) continue;
      document.querySelectorAll(`[data-trk="${key}"]`).forEach((el) => {
        el.textContent = `🌐 ${out}`;
        el.classList.remove("hidden");
      });
    }
  } finally {
    S.trRunning = false;
  }
}

/* ── dosya ve sesli mesaj gönderimi ───────────────────────────────────── */
const UPLOAD_MAX = 25 * 1024 * 1024;
const REC = {rec: null, chunks: [], start: 0, timer: null, to: null, cancel: false};

async function uploadBlob(to, blob, name) {
  if (!to) return;
  if (blob.size > UPLOAD_MAX) { toast(_t("Dosya çok büyük (en çok 25 MB)."), true); return; }
  toast(fmt("📤 Gönderiliyor: {}", name));
  const q = new URLSearchParams({to, name});
  const res = await fetch(`/api/upload?${q}`, {method: "POST", body: blob, headers: {
    "X-Requested-With": "xmpp-web", "X-Auth-Token": S.token || "",
    "Content-Type": blob.type || "application/octet-stream"}});
  let data = {};
  try { data = await res.json(); } catch (_) { /* boş gövde */ }
  if (res.status === 401) { showLogin(_t("Oturum sona erdi.")); return; }
  if (!res.ok || !data.ok) toast(data.error || _t("Dosya gönderilemedi."), true);
}

function recMime() {
  if (!window.MediaRecorder) return "";
  return ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/mp4"]
    .find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

function voiceName(type) {
  const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : "webm";
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  return `voice-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-` +
    `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}.${ext}`;
}

async function recStart() {
  if (!S.active || REC.rec) return;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    toast(_t("Bu tarayıcı ses kaydı yapamıyor (HTTPS ya da localhost gerekir)."), true);
    return;
  }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({audio: true}); }
  catch (_) { toast(_t("Mikrofon izni verilmedi."), true); return; }
  const mime = recMime();
  const rec = new MediaRecorder(stream, mime ? {mimeType: mime} : {});
  Object.assign(REC, {rec, chunks: [], start: Date.now(), to: S.active, cancel: false});
  rec.ondataavailable = (e) => { if (e.data.size) REC.chunks.push(e.data); };
  rec.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    clearInterval(REC.timer);
    $("rec-bar").classList.add("hidden");
    $("btn-mic").textContent = "🎤";
    const type = rec.mimeType || mime || "audio/webm";
    const blob = new Blob(REC.chunks, {type});
    const long = Date.now() - REC.start >= 500;
    REC.rec = null;
    if (!REC.cancel && long && blob.size) uploadBlob(REC.to, blob, voiceName(type));
  };
  rec.start();
  $("btn-mic").textContent = "⏹";
  $("rec-bar").classList.remove("hidden");
  $("rec-time").textContent = "0:00";
  REC.timer = setInterval(() => {
    const sec = Math.floor((Date.now() - REC.start) / 1000);
    $("rec-time").textContent = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
  }, 500);
}

function recStop(cancel = false) {
  if (!REC.rec) return;
  REC.cancel = cancel;
  REC.rec.stop();
}

/* ── durum ───────────────────────────────────────────────────────────── */
const S = {
  token: sessionStorage.getItem("xmpp_web_token") || null,
  ws: null, wsReq: 0, wsWait: new Map(),
  jid: "",
  contacts: new Map(),       // jid → {name, presence, unread, room, members, subject, enc, typing}
  active: null,
  history: new Map(),        // jid → {msgs: [], has_more}
  displayed: new Map(),      // jid → Set(okundu mid'leri)
  reply: null, editing: null,
  typingTimer: null, composing: false,
  settings: null,
  aiMode: null,
  blobs: new Map(),          // medya anahtarı → blob URL
  stt: new Map(), sttBusy: new Set(),
  tr: new Map(), trWant: new Map(), trRunning: false,
  tasks: [],
  joining: new Set(),        // kullanıcının istediği oda katılımları (küçük harf)
  notifyPrefs: {muted: {}, room_all: []},   // sunucudan (notify_policy.snapshot)
  starred: new Set(),        // ⭐ "jid\nmid" (sunucudan: snapshot.starred)
  revealed: new Set(),       // 🙈 açılmış spoiler'lar "jid\nmid" (oturumluk)
};
const RETRACTED = "🚫 Bu mesaj silindi";
const QUICK_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🎉"];

/* ── REST ────────────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const url = new URL(path, location.origin);
  // Token yalnız başlıkta: URL'de taşınmaz (günlük/vekil sızıntısı yok).
  // X-Requested-With: tarayıcı "basit istek" CSRF'ini preflight'a zorlar.
  opts.headers = {
    "X-Requested-With": "xmpp-web",
    ...(S.token ? {"X-Auth-Token": S.token} : {}),
    ...(opts.headers || {}),
  };
  const res = await fetch(url, opts);
  let data = {};
  try { data = await res.json(); } catch (_) { /* boş gövde */ }
  if (res.status === 401) { showLogin(_t("Oturum sona erdi.")); throw new Error("401"); }
  return { status: res.status, ok: res.ok, data };
}

async function apiPost(path, body) {
  return api(path, { method: "POST",
                     headers: {"Content-Type": "application/json"},
                     body: JSON.stringify(body || {}) });
}

/* ── WebSocket ───────────────────────────────────────────────────────── */
async function wsConnect() {
  if (!S.token) return;
  // WS'de başlık gönderilemez: tek kullanımlık kısa ömürlü bilet al.
  let ticket = "";
  try {
    const {data} = await apiPost("/api/ws-ticket", {});
    ticket = data.ticket || "";
  } catch (_) { return; }
  if (!ticket) return;
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws?ticket=${ticket}`);
  S.ws = ws;
  ws.onmessage = (m) => {
    let ev;
    try { ev = JSON.parse(m.data); } catch (_) { return; }
    if (ev.ev === "ack") {
      const resolve = S.wsWait.get(ev.data.req);
      if (resolve) { S.wsWait.delete(ev.data.req); resolve(ev.data); }
      return;
    }
    handleEvent(ev.ev, ev.data || {});
  };
  ws.onclose = () => {
    S.ws = null;
    if (S.token) setTimeout(wsConnect, 2500);
  };
}

function wsSend(cmd, args = {}) {
  if (!S.ws || S.ws.readyState !== 1) return Promise.resolve({ok: false});
  const req = ++S.wsReq;
  return new Promise((resolve) => {
    S.wsWait.set(req, resolve);
    S.ws.send(JSON.stringify({cmd, args, req}));
    setTimeout(() => {
      if (S.wsWait.has(req)) {
        S.wsWait.delete(req);
        resolve({ok: false, error: _t("Zaman aşımı")});
      }
    }, 10000);
  });
}

/* ── olay dağıtıcı (bridge izdüşümü) ─────────────────────────────────── */
const EVENTS = {
  hello(data) {
    S.jid = data.jid;
    $("me-jid").textContent = data.jid;
    S.contacts.clear();
    for (const c of data.contacts) S.contacts.set(c.jid, c);
    S.notifyPrefs = data.notify_prefs || {muted: {}, room_all: []};
    S.starred = new Set((data.starred || []).map(([j, m]) => starKey(j, m)));
    renderContacts();
    const last = localStorage.getItem("xmpp_web_last_chat");
    if (last && S.contacts.has(last)) openChat(last);
  },
  connected(data) {
    S.jid = data.jid;
    $("me-jid").textContent = data.jid;
    // Roster'ı tazele: bilinen odaları koru
    const known = new Map(S.contacts);
    S.contacts.clear();
    for (const [jid, name] of Object.entries(data.roster || {})) {
      const old = known.get(jid) || {};
      S.contacts.set(jid, {
        jid, name, presence: old.presence || {}, unread: old.unread || 0,
        room: old.room || false, members: old.members || {},
        subject: old.subject || "", enc: old.enc || "none",
        typing: false,
      });
    }
    for (const [jid, c] of known) if (c.room) S.contacts.set(jid, c);
    renderContacts();
    toast(_t("✓ Bağlandı"));
  },
  presence(data) {
    const c = S.contacts.get(data.jid);
    if (c) { c.presence = {ptype: data.ptype, pshow: data.pshow};
             renderContacts(); renderChatHeader(); }
  },
  msg(data) {
    const jid = data.from;
    appendMessage(jid, {
      sender: data.nick || jid, body: data.body, is_me: false,
      ts: nowHHMM(), mid: data.mid, encrypted: !!data.encrypted,
      oob: data.oob || "", reply: data.reply || null,
      reactions: {}, stored_at: new Date().toISOString(),
      spoiler: data.spoiler,
    });
    if (jid !== S.active || document.hidden) {
      const c = S.contacts.get(jid) || mkUnknown(jid);
      S.contacts.set(jid, c);
      if (jid !== S.active) {
        c.unread = (c.unread || 0) + 1;
      }
      // Sekme arka plandaysa açık sohbetin mesajı da bildirilir; okundu
      // bildirimi sekme görünür olunca gider (visibilitychange). Sessize
      // alınmış sohbet, adın geçmediği oda mesajı ve Meşgul durumu susar
      // (karar sunucuda: notify_policy).
      if (data.notify !== false) {
        notify(data.nick || jid,
               data.spoiler != null ? spoilerLabel(data.spoiler) : data.body);
      }
      renderContacts();
    } else {
      wsSend("mark_displayed", {to: jid, mid: data.mid});
    }
    if (!S.contacts.has(jid)) renderContacts();
  },
  own_msg(data) {
    appendMessage(data.to, {
      sender: "Ben", body: data.body, is_me: true,
      ts: nowHHMM(), mid: data.mid, encrypted: !!data.encrypted,
      oob: data.oob || "", reply: data.reply || null, reactions: {},
      stored_at: new Date().toISOString(), spoiler: data.spoiler,
    });
  },
  own_sent(data) {
    appendMessage(data.to, {
      sender: "Ben", body: data.body, is_me: true, ts: data.ts,
      mid: data.mid, encrypted: data.enc !== "none", oob: data.oob || "",
      reply: data.reply, reactions: {},
      stored_at: new Date().toISOString(), spoiler: data.spoiler,
    });
  },
  typing(data) {
    const c = S.contacts.get(data.jid);
    if (c) { c.typing = !!data.active; renderContacts(); renderTyping(); }
    setTimeout(() => {
      const cc = S.contacts.get(data.jid);
      if (cc && cc.typing) { cc.typing = false; renderContacts(); renderTyping(); }
    }, 6000);
  },
  marker_displayed(data) {
    const set = S.displayed.get(data.from) || new Set();
    set.add(data.mid);
    S.displayed.set(data.from, set);
    if (S.active === data.from) renderMessages();
  },
  msg_correction(data) {
    applyMutation(data.from, data.orig_id, data.body);
  },
  corrected(data) { applyMutation(data.jid, data.mid, data.body); },
  msg_retract(data) {
    applyMutation(data.from, data.retracted_id, RETRACTED);
  },
  msg_reactions(data) {
    const jid = data.from || data.jid;
    const msgs = S.history.get(jid)?.msgs || [];
    const row = msgs.find((m) => m.mid === data.target_id);
    if (row) row.reactions = data.reactions || {};
    if (S.active === jid) renderMessages();
  },
  muc_presence(data) {
    const c = S.contacts.get(data.room) || mkUnknown(data.room, true);
    c.room = true;
    if (data.online) c.members[data.nick] = {
      role: data.role, affil: data.affil, show: data.show};
    else delete c.members[data.nick];
    S.contacts.set(data.room, c);
    renderContacts();
    if (S.active === data.room) { renderMembers(); }
  },
  muc_subject(data) {
    const c = S.contacts.get(data.room);
    if (c) { c.subject = data.subject; renderChatHeader(); }
  },
  room_joined(data) {
    const room = data.room;
    const c = S.contacts.get(room) || mkUnknown(room, true);
    c.room = true;
    S.contacts.set(room, c);
    renderContacts();
    // Bağlanışta kayıtlı odalara otomatik katılım da bu olayı üretir: açık
    // sohbeti yalnız kullanıcının istediği katılımda o odaya çevir.
    if (S.joining.delete(room.toLowerCase())) {
      openChat(room);
      toast(fmt("✓ {} odasına katıldın", room));
    }
  },
  room_left(data) {
    S.contacts.delete(data.room);
    if (S.active === data.room) { S.active = null; renderMessages(); }
    renderContacts();
  },
  rooms_discovered(data) {
    const list = $("rooms-list");
    list.innerHTML = "";
    if (!Array.isArray(data) || !data.length) {
      list.innerHTML = `<li class="dim">${esc(_t("Oda bulunamadı."))}</li>`;
      return;
    }
    for (const room of data) {
      const li = document.createElement("li");
      const name = typeof room === "string" ? room : (room.jid || "?");
      li.innerHTML = `<span>${esc(name)}</span>`;
      const b = document.createElement("button");
      b.textContent = _t("Katıl");
      b.onclick = () => {
        $("dlg-rooms").close();
        $("j-room").value = name;
        $("dlg-join").showModal();
      };
      li.appendChild(b);
      list.appendChild(li);
    }
  },
  muc_invite(data) {
    toastActions(fmt("🍵 Davet: {}", data.room) +
                 (data.reason ? ` — ${data.reason}` : ""),
                 [[_t("Katıl"), () => {
                   $("j-room").value = data.room;
                   $("dlg-join").showModal();
                 }], [_t("Yok say"), () => {}]]);
  },
  subscribe_req(data) {
    toastActions(fmt("👥 {} abonelik istiyor", data),
      [[_t("Kabul"), () => wsSend("approve_subscribe",
                                 {jid: data, approve: true})],
       [_t("Reddet"), () => wsSend("approve_subscribe",
                               {jid: data, approve: false})]]);
  },
  bookmarks_update(data) { toast(fmt("🔖 Yer imi güncellendi: {}", data.kind || "")); },
  read_elsewhere(data) {
    const c = S.contacts.get(data.jid);
    if (c) { c.unread = 0; renderContacts(); }
  },
  mam_results(data) {
    // Arşiv sayfası DB'ye yazıldı: geçmişi yeniden yükle.
    if (data.count) reloadHistory(data.jid);
  },
  unread_update(data) {
    for (const [jid, n] of Object.entries(data.counts || {})) {
      const c = S.contacts.get(jid);
      if (c) c.unread = n;
    }
    renderContacts();
  },
  reminder(data) {
    const text = data.title + (data.location ? ` — ${data.location}` : "");
    toast(`⏰ ${text}`);
    showNotification(_t("⏰ Hatırlatıcı"), text);
  },
  morning_digest(data) {
    $("ai-panel").classList.remove("hidden");
    $("ai-provider").textContent = aiProviderLabel();
    $("ai-output").innerHTML = `<b>${esc(_t("☀ Günaydın"))}</b>\n${esc(data.text || "")}`;
    showNotification(_t("☀ Günaydın"), data.text || "");
  },
  notify_prefs(data) {
    S.notifyPrefs = data || {muted: {}, room_all: []};
    renderContacts();
    renderChatHeader();
  },
  star(data) {                 // başka sekme ya da bu sekme yıldızladı
    const k = starKey(data.jid, data.mid);
    if (data.on) S.starred.add(k); else S.starred.delete(k);
    if (data.jid === S.active) renderMessages();
  },
  sys_msg(data) { toast(data); },
  error(data) { toast(data, true); },
  disconnected() { toast(_t("Bağlantı koptu — yeniden bağlanıyor…"), true);
                   $("me-dot").className = "dot"; },
  conn_failed(data) { toast(fmt("Bağlantı hatası: {}", data), true); },
  auth_failed() {
    showLogin(_t("Kimlik doğrulama başarısız — parolayı kontrol edin."));
  },
};

function handleEvent(ev, data) {
  (EVENTS[ev] || (() => {}))(data);
}

function mkUnknown(jid, room = false) {
  return {jid, name: jid.split("@")[0], presence: {}, unread: 0, room,
          members: {}, subject: "", enc: "none", typing: false};
}

function nowHHMM() {
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

function notify(title, body) {
  if (S.settings?.general?.sounds) beep();
  if (!S.settings?.general?.notifications) return;
  if (document.hasFocus()) return;
  showNotification(fmt("Mesaj — {}", title), body);
}

/* ── kenar çubuğu ────────────────────────────────────────────────────── */
function presenceClass(c) {
  if (c.room) return "online";
  const p = c.presence || {};
  if (p.ptype === "unavailable") return "";
  return p.pshow || (p.ptype === "available" ? "online" : "");
}

function renderContacts() {
  const filter = ($("filter").value || "").toLocaleLowerCase("tr");
  const list = $("contact-list");
  list.innerHTML = "";
  const items = [...S.contacts.values()].filter((c) => {
    if (!filter) return true;
    return (c.name + " " + c.jid).toLocaleLowerCase("tr").includes(filter);
  }).sort((a, b) => {
    if ((b.unread || 0) !== (a.unread || 0))
      return (b.unread || 0) - (a.unread || 0);
    return (a.name || a.jid).localeCompare(b.name || b.jid, "tr");
  });
  for (const c of items) {
    const li = document.createElement("li");
    li.className = "contact" + (c.jid === S.active ? " active" : "");
    const cls = presenceClass(c);
    const label = (c.room ? `# ${c.name}` : c.name) +
      (muteUntil(c.jid) !== null ? " 🔕" : "");
    li.innerHTML =
      `<span class="dot ${esc(cls)}"></span>` +
      `<div class="name"><b>${esc(label)}</b>` +
      `<div class="sub">${esc(c.typing ? _t("yazıyor…") :
        c.room ? (c.subject || c.jid) : c.jid)}</div></div>` +
      (c.unread ? `<span class="badge">${c.unread}</span>` : "");
    li.onclick = () => openChat(c.jid);
    // Sağ tık (telefonda uzun basma) → o sohbetin 🔔 Bildirimler menüsü
    li.oncontextmenu = (e) => {
      e.preventDefault();
      openCtxMenu(c, e.clientX, e.clientY);
    };
    bindLongPress(li, (x, y) => openCtxMenu(c, x, y));
    list.appendChild(li);
  }
  let total = 0;
  for (const c of S.contacts.values()) total += c.unread || 0;
  document.title = (total ? `[${total}] ` : "") + "XMPP — Web";
}

/* ── sohbet ──────────────────────────────────────────────────────────── */
async function openChat(jid) {
  if (S.active !== jid) closeNotifyMenu();
  S.active = jid;
  $("main-view").classList.add("chat-open");    // dar ekranda sohbete geç
  localStorage.setItem("xmpp_web_last_chat", jid);
  const c = S.contacts.get(jid) || mkUnknown(jid);
  S.contacts.set(jid, c);
  c.unread = 0;
  renderContacts();
  renderChatHeader();
  renderMembers();
  if (!S.history.has(jid)) S.history.set(jid, {msgs: [], has_more: true});
  await loadHistory(jid);
  renderMessages();
  // sunucu okunmamışı düşürür + boşsa MAM (gizli sekme açık sohbet sayılmaz)
  wsSend("open_chat", {jid: document.hidden ? "" : jid});
  $("composer").focus();
}

async function loadHistory(jid) {
  const h = S.history.get(jid);
  let cursor = "";
  if (h.msgs.length && h.msgs[0].id) {
    const r0 = h.msgs[0];
    // İmleç (stored_at, id): MAM geçmişi sonradan yazıldığından id
    // sırası zaman sırası değildir; sunucu stored_at ile sıralar.
    cursor = `&before_id=${encodeURIComponent(r0.id)}` +
      `&before_stored_at=${encodeURIComponent(r0.stored_at || "")}`;
  }
  const {data} = await api(`/api/history?jid=${encodeURIComponent(jid)}` +
    cursor);
  if (!data.messages) return;
  h.has_more = !!data.has_more;
  h.msgs = [...data.messages, ...h.msgs];
}

async function reloadHistory(jid) {
  S.history.set(jid, {msgs: [], has_more: true});
  await loadHistory(jid);
  if (S.active === jid) renderMessages();
}

function rowHtml(m, prev) {
  if (m.tag === "sys" || m.sender === "sys") {
    return `<div class="sysline">${esc(m.body)}</div>`;
  }
  const room = S.contacts.get(S.active)?.room;
  const showSender = room && !m.is_me && m.sender !== prev?.sender;
  const ticks = m.is_me
    ? `<span class="ticks">${tickFor(m)}</span>` : "";
  const enc = m.encrypted
    ? `<span title="${esc(_t("şifreli"))}">🔒</span>` : "";
  const reply = m.reply
    ? `<div class="reply-q">↩ <b>${esc(who(m.reply.sender || ""))}</b> ` +
      `${esc((m.reply.body || "").slice(0, 90))}</div>` : "";
  let bodyHtml;
  const media = m.body === RETRACTED ? null : mediaOf(m);
  if (m.body === RETRACTED) {
    bodyHtml = `<span class="enc-chip">${esc(_t(RETRACTED))}</span>`;
  } else if (media) {
    const kind = mediaKind(media.url), name = mediaName(media.url);
    // Gövde yalnız bağlantıysa tekrar yazılmaz; aesgcm gövdesi anahtar taşır
    const caption = media.enc || (m.body || "").trim() === media.url
      ? "" : linkify(m.body);
    if (media.enc && kind === "file") {
      bodyHtml = caption + `<button class="enc-chip" data-download` +
        `${refAttrs(m)} data-name="${esc(name)}">🔒 ${esc(name)} ⬇</button>`;
    } else if (media.enc) {
      bodyHtml = caption + `<div class="media-slot" data-kind="${kind}"` +
        `${refAttrs(m)} data-name="${esc(name)}">` +
        `${esc(fmt("🔒 {} açılıyor…", name))}</div>`;
    } else {
      const previews = S.settings?.general?.remote_previews !== false;
      const href = `href="${esc(media.url)}" target="_blank" rel="noopener noreferrer"`;
      bodyHtml = caption + (kind === "image" && previews
        ? `<a ${href}><img class="preview" loading="lazy" src="${esc(media.url)}"></a>`
        : kind === "audio" && previews
          ? `<audio controls preload="none" src="${esc(media.url)}"></audio>`
          : `<a ${href}><div class="enc-chip">📎 ${esc(name)}</div></a>`);
    }
    if (kind === "audio" && (m.mid || m.id)) bodyHtml += sttHtml(m);
  } else {
    bodyHtml = linkify(m.body);
    if (!m.is_me && autoTranslateOn() && m.body) bodyHtml += trHtml(m);
  }
  const reacts = Object.entries(m.reactions || {})
    .filter(([, senders]) => senders.length)
    .map(([emoji, senders]) =>
      `<span class="${senders.includes("Ben") ? "mine" : ""}" ` +
      `title="${esc(senders.map(who).join(", "))}" data-react="${esc(emoji)}">` +
      `${esc(emoji)} ${senders.length}</span>`).join("");
  // XEP-0382: spoiler gövdesi tıklanana kadar örtülü (medya önizlemesi dahil)
  const revealKey = `${S.active}\n${m.mid || m.id || ""}`;
  if (m.spoiler != null && m.body !== RETRACTED && !S.revealed.has(revealKey)) {
    bodyHtml = `<button class="spoiler" data-reveal="${esc(revealKey)}">` +
      `${esc(spoilerCover(m.spoiler))}</button>`;
  }
  const canAct = m.mid && m.body !== RETRACTED;
  const starred = canAct && S.starred.has(starKey(S.active, m.mid));
  const tools = canAct
    ? `<div class="row-tools">` +
      `<button data-act="reply" title="${esc(_t("Yanıtla"))}">↩</button>` +
      `<button data-act="react" title="${esc(_t("Tepki"))}">😊</button>` +
      `<button data-act="star" title="${esc(starred ? _t("☆ Yıldızı Kaldır")
                                                   : _t("⭐ Yıldızla"))}">` +
      `${starred ? "⭐" : "☆"}</button>` +
      (m.is_me ? `<button data-act="edit" title="${esc(_t("Düzenle"))}">✎</button>` +
                 `<button data-act="retract" title="${esc(_t("Geri çek"))}">🗑</button>`
               : "") +
      `</div>` : "";
  const midAttr = m.mid ? ` data-mid="${esc(m.mid)}"` : "";
  return `<div class="row ${m.is_me ? "me" : "them"}"${midAttr}>${tools}` +
    `<div class="bubble">` +
    (showSender ? `<div class="sender">${esc(m.sender)}</div>` : "") +
    reply + bodyHtml +
    `<div class="meta">${starred ? `<span class="star">⭐</span>` : ""}` +
    `<span>${esc(m.ts || "")}</span>${enc}${ticks}</div>` +
    (reacts ? `<div class="reactions">${reacts}</div>` : "") +
    `</div></div>`;
}

function tickFor(m) {
  if (!m.mid) return "✓";
  const set = S.displayed.get(S.active);
  return set && set.has(m.mid) ? "✓✓" : "✓";
}

function renderMessages() {
  const box = $("messages");
  const h = S.history.get(S.active);
  if (!h) {
    box.innerHTML = `<div class="empty-hint">${esc(_t("Soldan bir sohbet seçin"))}</div>`;
    return;
  }
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  let html = "";
  if (h.has_more && h.msgs.length) {
    html += `<div class="sysline"><button id="btn-older">${esc(_t("↑ daha eski"))}</button></div>`;
  }
  let prev = null, prevDay = null;
  for (const m of h.msgs) {
    const d = dayLabel(m.stored_at);
    if (d && d !== prevDay) {
      html += `<div class="day-sep">${esc(d)}</div>`;
      prevDay = d;
    }
    html += rowHtml(m, prev);
    prev = m;
  }
  box.innerHTML = html || `<div class="empty-hint">${esc(_t("Henüz mesaj yok"))}</div>`;
  box.querySelectorAll("[data-act]").forEach((b) => {
    b.onclick = () => rowAction(b.dataset.act, b.closest(".row"));
  });
  box.querySelectorAll("[data-reveal]").forEach((b) => {
    b.onclick = () => {
      S.revealed.add(b.dataset.reveal);
      renderMessages();
    };
  });
  hydrateMedia(box);
  const autoStt = !!S.settings?.ai?.auto_transcribe;
  box.querySelectorAll("[data-stt]").forEach((b) => {
    b.onclick = () => transcribe(b);
    if (autoStt && !b.closest(".row.me")) transcribe(b);
  });
  translateQueue();
  box.querySelectorAll("[data-react]").forEach((sp) => {
    sp.onclick = () => {
      const mid = sp.closest(".row").dataset.mid;
      toggleReaction(mid, sp.dataset.react);
    };
  });
  $("btn-older")?.addEventListener("click", async () => {
    const h = S.history.get(S.active);
    if (h && h.has_more) {
      await loadHistory(S.active);
      renderMessages();
    } else {
      // Yerel geçmiş tükendi: sunucu arşivinden (MAM) eski sayfa iste.
      wsSend("load_older_mam", {jid: S.active});
    }
  });
  if (atBottom) box.scrollTop = box.scrollHeight;
}

function appendMessage(jid, m) {
  const h = S.history.get(jid) || S.history.set(jid, {msgs: [], has_more: false}).get(jid);
  if (m.mid && h.msgs.some((x) => x.mid && x.mid === m.mid &&
                                x.is_me === m.is_me)) return;
  h.msgs.push(m);
  if (h.msgs.length > 600) h.msgs.splice(0, h.msgs.length - 600);
  if (jid === S.active) {
    renderMessages();
  } else {
    const c = S.contacts.get(jid);
    if (c) renderContacts();
  }
}

function applyMutation(jid, mid, body) {
  const h = S.history.get(jid);
  if (!h) return;
  const row = h.msgs.find((m) => m.mid === mid);
  if (row) {
    row.body = body;
    if (body === RETRACTED) row.reactions = {};
  }
  if (jid === S.active) renderMessages();
}

/* ── bildirim kontrolü (kurallar sunucuda: xmppcore/notify_policy) ───── */
function muteUntil(jid) {
  // null: sessiz değil · 0: süresiz · sayı: bitiş (epoch sn)
  const u = (S.notifyPrefs.muted || {})[jid];
  if (typeof u !== "number") return null;
  if (u === 0) return 0;
  return u * 1000 > Date.now() ? u : null;
}

function muteEndText(u) {
  const d = new Date(u * 1000), p = (n) => String(n).padStart(2, "0");
  const hm = `${p(d.getHours())}:${p(d.getMinutes())}`;
  return d.toDateString() === new Date().toDateString()
    ? hm : `${p(d.getDate())}.${p(d.getMonth() + 1)} ${hm}`;
}

function notifyMenuItems(c) {
  const items = [];
  const u = muteUntil(c.jid);
  if (u !== null) {
    items.push(["unmute", u === 0 ? _t("🔔 Sesi Aç (süresiz)")
                                   : fmt("🔔 Sesi Aç (bitiş {})", muteEndText(u))]);
    items.push(null);
  }
  items.push(["1h", _t("🔕 1 Saat Sessize Al")], ["8h", _t("🔕 8 Saat Sessize Al")],
             ["1d", _t("🔕 1 Gün Sessize Al")], ["forever", _t("🔕 Süresiz Sessize Al")]);
  if (c.room) {
    items.push(null);
    items.push((S.notifyPrefs.room_all || []).includes(c.jid)
      ? ["room_mention", _t("@ Yalnız Adım Geçince Bildir")]
      : ["room_all", _t("🔔 Her Mesajda Bildir")]);
  }
  return items;
}

function closeNotifyMenu() {
  $("notify-menu").classList.add("hidden");
  $("btn-notify").setAttribute("aria-expanded", "false");
}

function fillNotifyMenu(menu, c) {
  menu.innerHTML = "";
  for (const item of notifyMenuItems(c)) {
    if (!item) { menu.appendChild(document.createElement("hr")); continue; }
    const [choice, label] = item;
    const b = document.createElement("button");
    b.setAttribute("role", "menuitem");
    b.textContent = label;
    b.onclick = () => setNotify(c, choice);
    menu.appendChild(b);
  }
}

function openNotifyMenu() {
  const c = S.active ? S.contacts.get(S.active) : null;
  if (!c) return;
  closeCtxMenu();
  const menu = $("notify-menu");
  fillNotifyMenu(menu, c);
  menu.classList.remove("hidden");
  $("btn-notify").setAttribute("aria-expanded", "true");
  menu.querySelector("button")?.focus();
}

/* Kenar çubuğunda sağ tık / uzun basma: aynı menü, imlecin yanında */
function openCtxMenu(c, x, y) {
  closeNotifyMenu();
  const menu = $("ctx-menu");
  fillNotifyMenu(menu, c);
  const title = document.createElement("div");
  title.className = "pop-title";
  title.textContent = c.room ? `# ${c.name}` : c.name;
  menu.prepend(title);
  menu.classList.remove("hidden");
  const w = menu.offsetWidth, h = menu.offsetHeight;
  menu.style.left = Math.max(8, Math.min(x, innerWidth - w - 8)) + "px";
  menu.style.top = Math.max(8, Math.min(y, innerHeight - h - 8)) + "px";
  menu.querySelector("button")?.focus();
}

function closeCtxMenu() {
  $("ctx-menu").classList.add("hidden");
}

function bindLongPress(el, fn) {
  // iOS Safari uzun basmada contextmenu olayı vermez; Android ikisini de
  // verir (menü aynı yerde yeniden açılır). Uzun basmadan sonraki tıklama
  // sohbeti açmasın.
  let timer = null, fired = false;
  const cancel = () => { clearTimeout(timer); timer = null; };
  el.addEventListener("touchstart", (e) => {
    fired = false;
    const t = e.touches[0];
    timer = setTimeout(() => { fired = true; fn(t.clientX, t.clientY); }, 550);
  }, {passive: true});
  el.addEventListener("touchmove", cancel, {passive: true});
  el.addEventListener("touchcancel", cancel);
  el.addEventListener("touchend", (e) => {
    cancel();
    if (fired) e.preventDefault();
  });
}

/* ── hazır yanıtlar (kurallar sunucuda: xmppcore/canned) ─────────────── */
async function openCannedMenu() {
  const r = await wsSend("get_canned", {});
  if (!r.ok) {
    toast(r.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
    return;
  }
  const menu = $("canned-menu");
  menu.innerHTML = "";
  for (const text of r.items) {
    const b = document.createElement("button");
    b.setAttribute("role", "menuitem");
    b.textContent = text;
    b.title = text;
    b.onclick = () => { closeCannedMenu(); insertCanned(text); };
    menu.appendChild(b);
  }
  if (!r.items.length) {
    const empty = document.createElement("div");
    empty.className = "pop-title";
    empty.textContent = _t("Henüz hazır yanıt yok");
    menu.appendChild(empty);
  }
  menu.appendChild(document.createElement("hr"));
  const edit = document.createElement("button");
  edit.setAttribute("role", "menuitem");
  edit.textContent = _t("✏ Düzenle…");
  edit.onclick = () => { closeCannedMenu(); openCannedEditor(r.items); };
  menu.appendChild(edit);
  menu.classList.remove("hidden");
  $("btn-canned").setAttribute("aria-expanded", "true");
  menu.querySelector("button")?.focus();
}

function closeCannedMenu() {
  $("canned-menu").classList.add("hidden");
  $("btn-canned").setAttribute("aria-expanded", "false");
}

function insertCanned(text) {
  // İmlecin olduğu yere eklenir; gönderilmez (masaüstüyle aynı)
  const ta = $("composer");
  const start = ta.selectionStart ?? ta.value.length;
  const end = ta.selectionEnd ?? start;
  const before = ta.value.slice(0, start);
  const pad = before && !/\s$/.test(before) ? " " : "";
  ta.value = before + pad + text + ta.value.slice(end);
  const pos = (before + pad + text).length;
  ta.focus();
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event("input"));
}

function openCannedEditor(items) {
  $("canned-text").value = items.join("\n");
  $("dlg-canned").showModal();
  $("canned-text").focus();
}

async function saveCanned() {
  const r = await wsSend("set_canned", {text: $("canned-text").value});
  if (!r.ok) {
    toast(r.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
    return;
  }
  $("dlg-canned").close();
  toast(fmt("Kaydedilen yanıt: {}", r.items.length));
}

async function setNotify(c, choice) {
  closeNotifyMenu();
  closeCtxMenu();
  const r = await wsSend("set_notify", {jid: c.jid, choice});
  if (!r.ok) {
    toast(r.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
    return;
  }
  S.notifyPrefs = r.prefs;
  renderContacts();
  renderChatHeader();
  if (choice === "room_all") toast(_t("Her mesajda bildirilecek"));
  else if (choice === "room_mention") toast(_t("Yalnız adınız geçince bildirilecek"));
  else if (choice === "unmute") toast(`${_t("🔔 Bildirimler açıldı")} — ${c.name}`);
  else {
    const u = muteUntil(c.jid);
    toast(`${_t("🔕 Sessize alındı")} — ${c.name} · ` +
          (u ? fmt("bitiş {}", muteEndText(u)) : _t("süresiz")));
  }
}

function renderChatHeader() {
  const c = S.active ? S.contacts.get(S.active) : null;
  const encBtn = $("btn-enc"), memBtn = $("btn-members"),
        leaveBtn = $("btn-leave-room"), dot = $("chat-dot"),
        notifyBtn = $("btn-notify");
  if (!c) {
    closeNotifyMenu();
    $("chat-name").textContent = _t("Bir sohbet seçin");
    $("chat-sub").textContent = "";
    dot.classList.add("hidden");
    notifyBtn.classList.add("hidden");
    encBtn.classList.add("hidden");
    memBtn.classList.add("hidden");
    leaveBtn.classList.add("hidden");
    return;
  }
  $("chat-name").textContent = c.room ? `# ${c.name}` : c.name;
  const p = c.presence || {};
  // Durum adları masaüstü menüsüyle aynı (agent.STATUS_LABELS)
  const awayTxt = {away: _t("uzakta"), xa: _t("uzun süre uzakta"),
                   dnd: _t("meşgul"), chat: _t("çevrimiçi")};
  const sub = c.room
    ? (c.subject || fmt("{} üye", Object.keys(c.members).length))
    : (p.ptype === "unavailable" ? _t("çevrimdışı")
       : awayTxt[p.pshow] || (p.ptype === "available" ? _t("çevrimiçi") : "—"));
  $("chat-sub").textContent = c.typing ? _t("✍ yazıyor…") : sub;
  if (!c.room) {
    dot.classList.remove("hidden");
    dot.className = "dot " + presenceClass(c);
  } else {
    dot.classList.add("hidden");
  }
  notifyBtn.classList.remove("hidden");
  notifyBtn.textContent = muteUntil(c.jid) !== null ? "🔕" : "🔔";
  encBtn.classList.remove("hidden");
  memBtn.classList.toggle("hidden", !c.room);
  leaveBtn.classList.toggle("hidden", !c.room);
  encBtn.textContent = c.enc === "omemo" ? "🔒 OMEMO" : _t("🔓 Düz");
  renderTyping();
}

function renderTyping() {
  const c = S.active ? S.contacts.get(S.active) : null;
  $("typing-line").classList.toggle("hidden", !(c && c.typing));
}

function renderMembers() {
  const c = S.active ? S.contacts.get(S.active) : null;
  const panel = $("members-panel");
  if (!c || !c.room) { panel.classList.add("hidden"); return; }
  if (panel.classList.contains("hidden")) return;  // kullanıcı kapattıysa
  $("member-list").innerHTML = Object.entries(c.members).map(([nick, info]) => {
    const cls = info.show || "online";
    return `<li><span class="dot ${esc(cls)}"></span>` +
      `<span>${esc(nick)}</span>` +
      `<span class="affil">${esc(info.affil || info.role || "")}</span></li>`;
  }).join("") || `<li class="dim">${esc(_t("Kimse yok"))}</li>`;
}

/* ── satır eylemleri ─────────────────────────────────────────────────── */
function rowAction(act, rowEl) {
  const mid = rowEl.dataset.mid;
  const h = S.history.get(S.active);
  const row = h?.msgs.find((m) => m.mid === mid);
  if (!row) return;
  if (act === "reply") {
    S.reply = {id: mid, sender: row.is_me ? "Ben" : row.sender,
               body: (row.body || "").slice(0, 120),
               to: S.active};
    $("reply-preview").innerHTML =
      `↩ <b>${esc(who(S.reply.sender))}</b> ${esc(S.reply.body)}`;
    $("reply-bar").classList.remove("hidden");
    $("composer").focus();
  } else if (act === "edit") {
    S.editing = {mid, to: S.active};
    $("composer").value = row.body;
    $("edit-bar").classList.remove("hidden");
    $("composer").focus();
  } else if (act === "retract") {
    wsSend("retract", {to: S.active, mid}).then((res) => {
      if (!res.ok) toast(res.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
    });
  } else if (act === "star") {
    toggleStar(S.active, mid);
  } else if (act === "react") {
    const pick = prompt("Emoji: " + QUICK_EMOJIS.join(" "), "👍");
    if (pick) toggleReaction(mid, pick.trim());
  }
}

/* ── ⭐ yıldızlı mesajlar (masaüstüyle ortak DB: messages.starred) ───── */
function starKey(jid, mid) {
  return `${jid}\n${mid}`;
}

async function toggleStar(jid, mid) {
  const on = !S.starred.has(starKey(jid, mid));
  const r = await wsSend("star", {jid, mid, on});
  if (!r.ok) {
    toast(r.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
    return;
  }
  if (on) S.starred.add(starKey(jid, mid)); else S.starred.delete(starKey(jid, mid));
  if (jid === S.active) renderMessages();
}

async function openStarred() {
  const r = await wsSend("starred", {});
  if (!r.ok) {
    toast(r.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
    return;
  }
  S.starred = new Set(r.items.map((i) => starKey(i.jid, i.mid)));
  const list = $("starred-list");
  list.innerHTML = r.items.map((i, n) =>
    `<li data-n="${n}"><div class="starred-text">` +
    `<div class="dim small">${esc(i.chat)} · ` +
    `${esc([dayLabel(i.stored_at), i.ts].filter(Boolean).join(" "))}</div>` +
    `<div>${esc(i.is_me ? who("Ben") : i.sender)}: ${esc(i.body)}</div></div>` +
    `<button data-unstar="${n}" title="${esc(_t("☆ Yıldızı Kaldır"))}">⭐</button>` +
    `</li>`).join("") ||
    `<li class="dim">${esc(_t("Henüz yıldızlı mesaj yok"))}</li>`;
  list.querySelectorAll("li[data-n]").forEach((li) => {
    const it = r.items[+li.dataset.n];
    li.onclick = () => {
      $("dlg-starred").close();
      openStarredMessage(it.jid, it.mid);
    };
  });
  list.querySelectorAll("[data-unstar]").forEach((b) => {
    const it = r.items[+b.dataset.unstar];
    b.onclick = async (e) => {
      e.stopPropagation();
      const rr = await wsSend("star", {jid: it.jid, mid: it.mid, on: false});
      if (!rr.ok) {
        toast(rr.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
        return;
      }
      S.starred.delete(starKey(it.jid, it.mid));
      b.closest("li").remove();
      if (it.jid === S.active) renderMessages();
    };
  });
  $("dlg-starred").showModal();
}

async function openStarredMessage(jid, mid) {
  await openChat(jid);
  const el = [...$("messages").querySelectorAll(".row[data-mid]")]
    .find((x) => x.dataset.mid === mid);
  if (!el) {
    toast(_t("Mesaj yüklenen geçmişte bulunamadı"));
    return;
  }
  el.scrollIntoView({block: "center"});
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1600);
}

async function toggleReaction(mid, emoji) {
  const h = S.history.get(S.active);
  const row = h?.msgs.find((m) => m.mid === mid);
  if (!row) return;
  const mine = (row.reactions?.[emoji] || []).includes("Ben");
  const emojis = new Set(Object.entries(row.reactions || {})
    .filter(([, senders]) => senders.includes("Ben"))
    .map(([e]) => e));
  if (mine) emojis.delete(emoji); else emojis.add(emoji);
  await wsSend("react", {to: S.active, mid, emojis: [...emojis]});
}

/* ── gönderim ────────────────────────────────────────────────────────── */
function clearReplyEdit() {
  S.reply = null; S.editing = null;
  $("reply-bar").classList.add("hidden");
  $("edit-bar").classList.add("hidden");
}

function takeSentText(box, raw) {
  // Yalnız gönderilen metin kalkar: yanıt beklenirken yazılan devamı silinmez
  box.value = box.value.startsWith(raw) ? box.value.slice(raw.length).trimStart()
                                         : box.value;
}

async function sendCurrent(force = false, spoiler = null) {
  const box = $("composer");
  const raw = box.value;
  const body = raw.trim();
  if (!body || !S.active) return;
  const enc = S.contacts.get(S.active)?.enc || "none";
  // Başarısız gönderimde metin ve yanıt/düzeltme bağlamı kutuda kalır;
  // WebSocket kopukken wsSend hata metni olmadan {ok: false} döner.
  const failed = (res) => {
    if (res.ok) return false;
    toast(res.error || _t("Bağlantı koptu — yeniden bağlanıyor…"), true);
    return true;
  };
  if (S.editing) {
    const res = await wsSend("correct", {to: S.editing.to, mid: S.editing.mid, body});
    if (failed(res)) return;
    takeSentText(box, raw);
    clearReplyEdit();
    return;
  }
  if (spoiler !== null && enc !== "none") {
    toast(_t("Şifreli sohbette gizli içerik gönderilemez"), true);
    return;                             // metin kutuda kalır
  }
  const res = await wsSend("send",
    {to: S.active, body, enc, force, reply_to: S.reply,
     ...(spoiler !== null ? {spoiler} : {})});
  if (res.leak && !force) {
    showLeakDialog(res.findings, () => sendCurrent(true, spoiler));
    return;
  }
  if (failed(res)) return;
  takeSentText(box, raw);
  clearReplyEdit();
}

/* ── 🙈 spoiler (XEP-0382; yalnız şifresiz sohbet) ──────────────────── */
function spoilerLabel(hint) {
  return hint ? fmt("🙈 Gizli içerik: {}", hint) : _t("🙈 Gizli içerik");
}

function spoilerCover(hint) {
  return fmt("{} — göstermek için tıklayın", spoilerLabel(hint));
}

function openSendMenu() {
  // ➤ düğmesinde sağ tık / uzun basma
  const menu = $("send-menu");
  menu.innerHTML = "";
  const b = document.createElement("button");
  b.setAttribute("role", "menuitem");
  b.textContent = _t("🙈 Gizli içerik olarak gönder…");
  b.onclick = () => sendSpoiler();
  menu.appendChild(b);
  menu.classList.remove("hidden");
  b.focus();
}

function closeSendMenu() {
  $("send-menu").classList.add("hidden");
}

async function sendSpoiler() {
  closeSendMenu();
  if (!$("composer").value.trim() || !S.active) return;
  if ((S.contacts.get(S.active)?.enc || "none") !== "none") {
    toast(_t("Şifreli sohbette gizli içerik gönderilemez"), true);
    return;
  }
  const hint = prompt(_t("Uyarı metni (isteğe bağlı):"), "");
  if (hint === null) return;            // vazgeçildi
  await sendCurrent(false, hint.trim());
}

function showLeakDialog(findings, onConfirm) {
  $("leak-findings").innerHTML = (findings || []).map((f) =>
    `<div>• <b>${esc(f.label)}</b> — ${esc(f.sample)}</div>`).join("");
  const dlg = $("dlg-confirm");
  $("leak-yes").onclick = () => { dlg.close(); onConfirm(); };
  $("leak-no").onclick = () => dlg.close();
  dlg.showModal();
}

/* yazıyor bildirimi */
function composerInput() {
  const ta = $("composer");
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
  if (!S.active || S.editing) return;
  clearTimeout(S.typingTimer);
  if (!S.composing) {
    S.composing = true;
    wsSend("typing", {to: S.active, active: true});
  }
  S.typingTimer = setTimeout(() => {
    S.composing = false;
    wsSend("typing", {to: S.active, active: false});
  }, 3000);
}

/* ── AI paneli ───────────────────────────────────────────────────────── */
function aiProviderLabel() {
  const ai = S.settings?.ai || {};
  if (ai.provider === "claude") return `☁ Claude · ${ai.claude_model}`;
  if (ai.provider === "ollama")
    return fmt("🖥 Yerel · {}", ai.ollama_model);
  return _t("AI kapalı");
}

function aiPrivacyBlocked(out, status, data) {
  if (status !== 403) return false;
  $("ai-cloud-row").classList.remove("hidden");
  out.innerHTML = `🛡 ${esc(data.error || _t("İzin gerekli."))}` +
    `<div class="src">${esc(_t("Onay kutusunu işaretleyip yeniden dene — yalnız bu istek için geçerli olur."))}</div>`;
  return true;
}

async function aiTasks() {
  const out = $("ai-output");
  if (!S.active) { out.textContent = _t("Soldan bir sohbet seçin"); return; }
  $("ai-provider").textContent = aiProviderLabel();
  out.innerHTML = `<span class="ai-busy">${esc(_t("⏳ Çalışıyor…"))}</span>`;
  const jid = S.active;
  const {status, data} = await apiPost("/api/ai/tasks", {
    jid, allow_cloud: $("ai-allow-cloud").checked});
  if (aiPrivacyBlocked(out, status, data)) return;
  if (!Array.isArray(data.items)) {
    out.innerHTML = `✗ ${esc(data.error || _t("Yanıt alınamadı."))}`;
    return;
  }
  if (!data.items.length) {
    out.textContent = data.text || _t("Görev ya da etkinlik bulunamadı.");
    return;
  }
  S.tasks = data.items;
  out.innerHTML = data.items.map((it, i) =>
    `<label class="chk task"><input type="checkbox" data-task="${i}" checked>` +
    `<span><b>${it.kind === "event" ? "📅" : "✅"} ${esc(it.title)}</b><br>` +
    `<span class="dim small">${esc([it.date, it.time, it.location]
      .filter(Boolean).join(" · "))}</span></span></label>`).join("") +
    `<div class="task-actions"><button id="task-ics">` +
    `${esc(_t("📅 Takvime aktar (.ics)"))}</button><button id="task-remind">` +
    `${esc(_t("⏰ Hatırlat"))}</button></div>`;
  const picked = () => [...out.querySelectorAll("[data-task]:checked")]
    .map((c) => S.tasks[Number(c.dataset.task)]);
  $("task-ics").onclick = () => exportIcs(picked());
  $("task-remind").onclick = async () => {
    const {data: r} = await apiPost("/api/reminders", {items: picked(), jid});
    toast(r.message || r.error || "", !r.ok);
  };
}

async function exportIcs(items) {
  const res = await fetch("/api/ics", {method: "POST",
    headers: {"X-Requested-With": "xmpp-web", "X-Auth-Token": S.token || "",
              "Content-Type": "application/json"},
    body: JSON.stringify({items})});
  if (!res.ok) {
    let data = {};
    try { data = await res.json(); } catch (_) { /* boş */ }
    toast(data.error || _t("Yanıt alınamadı."), true);
    return;
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = "gorevler.ics";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

async function aiRun(mode, extra = {}) {
  const out = $("ai-output");
  const body = {allow_cloud: $("ai-allow-cloud").checked, ...extra};
  $("ai-provider").textContent = aiProviderLabel();
  out.innerHTML = `<span class="ai-busy">${esc(_t("⏳ Çalışıyor…"))}</span>`;
  const {status, data} = await apiPost(`/api/ai/${mode}`, body);
  if (aiPrivacyBlocked(out, status, data)) return;
  if (!data.text) {
    out.innerHTML = `✗ ${esc(data.error || _t("Yanıt alınamadı."))}`;
    return;
  }
  const srcs = (data.sources || []).map((s) =>
    `<div class="src">[${s.n}] ${esc(s.label || s.jid)} · ${esc(s.who)}: ` +
    `${esc((s.text || "").slice(0, 90))}</div>`).join("");
  out.innerHTML = `${esc(data.text)}${srcs}`;
}

function aiSelect(mode) {
  S.aiMode = mode;
  document.querySelectorAll("[data-ai]").forEach((b) =>
    b.classList.toggle("on", b.dataset.ai === mode));
  const needsInput = mode === "ask" || mode === "translate" ||
    mode === "assistant";   // özet, döküm ve görevler doğrudan çalışır
  $("ai-input-row").classList.toggle("hidden", !needsInput);
  $("ai-input").placeholder =
    mode === "ask" ? _t("Geçmişte ara…") :
    mode === "translate" ? _t("Çevrilecek metin…") : _t("Asistana yaz…");
}

async function aiSubmit() {
  const mode = S.aiMode || "summary";
  const text = $("ai-input").value.trim();
  if (mode === "ask") {
    await aiRun("ask", {question: text, previous: S.aiPrev || ""});
    S.aiPrev = text;
  } else if (mode === "translate") {
    if (text) await aiRun("translate", {text});
  } else if (mode === "assistant") {
    S.aiHist = S.aiHist || [];
    S.aiHist.push({role: "user", text});
    await aiRun("assistant", {history: S.aiHist});
    const outText = $("ai-output").textContent;
    if (outText) S.aiHist.push({role: "assistant", text: outText});
  } else {
    await aiRun(mode);
  }
}

/* ── ayarlar ─────────────────────────────────────────────────────────── */
function applyTheme(colors) {
  const root = document.documentElement.style;
  for (const [k, v] of Object.entries(colors || {})) root.setProperty(`--${k}`, v);
}

async function openSettings() {
  const {data} = await api("/api/settings");
  S.settings = data;
  const g = data.general, ai = data.ai;
  const themeLabels = data.theme_labels || {};
  $("s-theme").innerHTML = (data.themes || []).map((t) =>
    `<option value="${esc(t)}" ${t === g.theme ? "selected" : ""}>` +
    `${esc(themeLabels[t] || t)}</option>`).join("");
  $("s-language").innerHTML = Object.entries(I18N.languages).map(([code, name]) =>
    `<option value="${esc(code)}" ${code === I18N.lang ? "selected" : ""}>` +
    `${esc(name)}</option>`).join("");
  $("s-keep-alive").innerHTML = (data.choices.keep_alive || []).map((k) =>
    `<option value="${esc(k)}" ${k === ai.keep_alive ? "selected" : ""}>${esc(k)}</option>`).join("");
  $("s-notifications").checked = !!g.notifications;
  $("s-sounds").checked = !!g.sounds;
  $("s-receipts").checked = !!g.send_read_receipts;
  $("s-typing").checked = !!g.send_typing;
  $("s-rejoin").checked = !!g.auto_rejoin;
  $("s-previews").checked = g.remote_previews !== false;
  $("s-provider").value = ai.provider;
  $("s-ollama-url").value = ai.ollama_url;
  $("s-ollama-model").value = ai.ollama_model;
  $("s-ollama-vision").value = ai.ollama_vision_model;
  $("s-embed").value = ai.embed_model;
  $("s-claude-model").value = ai.claude_model;
  $("s-api-key").placeholder = ai.has_api_key
    ? _t("Kayıtlı anahtar var — değiştirmek için yazın") : _t("Anahtar yok");
  $("s-cloud-enc").checked = !!ai.cloud_for_encrypted;
  $("s-leak").checked = !!ai.leak_guard;
  $("s-auto-stt").checked = !!ai.auto_transcribe;
  $("s-inline").checked = !!ai.inline_complete;
  $("s-away").checked = !!ai.away_drafts;
  $("s-autotr").checked = !!ai.auto_translate;
  $("s-morning").checked = !!ai.morning_digest;
  $("s-morning-time").value = ai.morning_time || "08:30";
  $("dlg-settings").showModal();
  applyTheme((data.theme_colors || {})[g.theme]);
}

async function saveSettings() {
  const ai = {
    provider: $("s-provider").value,
    ollama_url: $("s-ollama-url").value.trim(),
    ollama_model: $("s-ollama-model").value.trim(),
    ollama_vision_model: $("s-ollama-vision").value.trim(),
    embed_model: $("s-embed").value.trim(),
    claude_model: $("s-claude-model").value.trim(),
    keep_alive: $("s-keep-alive").value,
    cloud_for_encrypted: $("s-cloud-enc").checked,
    leak_guard: $("s-leak").checked,
    auto_transcribe: $("s-auto-stt").checked,
    inline_complete: $("s-inline").checked,
    away_drafts: $("s-away").checked,
    auto_translate: $("s-autotr").checked,
    morning_digest: $("s-morning").checked,
    morning_time: $("s-morning-time").value || "08:30",
  };
  const language = $("s-language").value;
  const body = {
    language,
    general: {
      theme: $("s-theme").value,
      notifications: $("s-notifications").checked,
      sounds: $("s-sounds").checked,
      send_read_receipts: $("s-receipts").checked,
      send_typing: $("s-typing").checked,
      auto_rejoin: $("s-rejoin").checked,
      remote_previews: $("s-previews").checked,
    },
    ai,
  };
  if ($("s-del-key").checked) body.api_key = "";
  else if ($("s-api-key").value.trim()) body.api_key = $("s-api-key").value.trim();
  const {status, data} = await apiPost("/api/settings", body);
  if (status === 200) {
    S.settings = {...S.settings, ai: data.ai, general: body.general};
    const {data: fresh} = await api("/api/settings");
    S.settings = fresh;
    applyTheme((fresh.theme_colors || {})[body.general.theme]);
    toast(_t("✓ Ayarlar kaydedildi"));
    if (language !== I18N.lang) {
      // Yeni dil: sayfayı yeniden yükle (oturum sessionStorage'da sürer)
      $("dlg-settings").close();
      location.reload();
      return;
    }
  } else {
    toast(data.error || _t("Ayarlar kaydedilemedi"), true);
  }
  $("dlg-settings").close();
}

/* ── giriş / çıkış ───────────────────────────────────────────────────── */
function showLogin(message = "") {
  S.token = null;
  sessionStorage.removeItem("xmpp_web_token");
  try { S.ws?.close(); } catch (_) {}
  S.ws = null;
  $("main-view").classList.add("hidden");
  $("login-view").classList.remove("hidden");
  const err = $("l-error");
  err.textContent = message;
  err.classList.toggle("hidden", !message);
  api("/api/prefill").then(({data}) => {
    if (data.jid) {
      $("l-jid").value = data.jid;
      $("l-server").value = data.server || "";
      $("l-port").value = data.port || 5222;
      $("l-remember").checked = true;
    }
  }).catch(() => {});
}

async function showMain() {
  $("login-view").classList.add("hidden");
  $("main-view").classList.remove("hidden");
  wsConnect();
  const {data} = await api("/api/settings");
  S.settings = data;
  applyTheme((data.theme_colors || {})[data.general.theme]);
  $("ai-provider").textContent = aiProviderLabel();
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

/* ── olay bağlama ────────────────────────────────────────────────────── */
function bind() {
  $("login-form").onsubmit = async (e) => {
    e.preventDefault();
    const btn = $("l-submit");
    btn.disabled = true;
    btn.textContent = _t("Bağlanıyor…");
    try {
      const {status, data} = await apiPost("/api/login", {
        jid: $("l-jid").value.trim(),
        password: $("l-pw").value,
        server: $("l-server").value.trim(),
        port: parseInt($("l-port").value || "5222", 10),
        remember: $("l-remember").checked,
        force: false,
      });
      if (status === 200) {
        S.token = data.token;
        sessionStorage.setItem("xmpp_web_token", data.token);
        await showMain();
      } else if (data.conflict) {
        if (confirm(fmt("Zaten {} olarak bağlı bir oturum var. Kapatıp devam edilsin mi?",
                        data.connected_as))) {
          const r2 = await apiPost("/api/login", {
            jid: $("l-jid").value.trim(), password: $("l-pw").value,
            server: $("l-server").value.trim(),
            port: parseInt($("l-port").value || "5222", 10),
            remember: $("l-remember").checked, force: true});
          if (r2.status === 200) {
            S.token = r2.data.token;
            sessionStorage.setItem("xmpp_web_token", r2.data.token);
            await showMain();
          } else toast(r2.data.error || _t("Giriş başarısız."), true);
        }
      } else {
        $("l-error").textContent = data.error || _t("Giriş başarısız.");
        $("l-error").classList.remove("hidden");
      }
    } finally {
      btn.disabled = false;
      btn.textContent = _t("Bağlan");
    }
  };

  $("filter").oninput = renderContacts;
  // Gizli sekme "açık sohbet" sayılmaz: sunucu okundu bildirmesin, okunmamış
  // saysın; geri gelince sohbet yeniden açık ve son gelen mesaj okundu.
  document.addEventListener("visibilitychange", () => {
    if (!S.token) return;
    if (document.hidden) { wsSend("open_chat", {jid: ""}); return; }
    if (!S.active) return;
    wsSend("open_chat", {jid: S.active});
    const h = S.history.get(S.active);
    const last = h && [...h.msgs].reverse().find((m) => !m.is_me && m.mid);
    if (last) wsSend("mark_displayed", {to: S.active, mid: last.mid});
  });
  $("btn-join-room").onclick = () => {
    $("j-nick").value = S.jid.split("@")[0] || "";
    $("dlg-join").showModal();
  };
  $("j-go").onclick = (e) => {
    e.preventDefault();
    const room = $("j-room").value.trim();
    if (room) {
      S.joining.add(room.toLowerCase());
      wsSend("join_room", {room, nick: $("j-nick").value.trim()});
    }
    $("dlg-join").close();
  };
  $("rooms-close").onclick = () => $("dlg-rooms").close();
  $("btn-discover")?.addEventListener("click", async () => {
    $("dlg-rooms").showModal();
    await wsSend("discover_rooms", {});
  });
  $("btn-leave-room").onclick = () => {
    if (S.active && confirm(fmt("{} odasından ayrıl?", S.active)))
      wsSend("leave_room", {room: S.active});
  };
  $("btn-notify").onclick = (e) => {
    e.stopPropagation();
    if ($("notify-menu").classList.contains("hidden")) openNotifyMenu();
    else closeNotifyMenu();
  };
  // Dışarı tıklama ya da Esc menüyü kapatır (masaüstü açılır kartları gibi)
  $("btn-starred").onclick = () => openStarred();
  $("starred-close").onclick = () => $("dlg-starred").close();
  $("btn-canned").onclick = (e) => {
    e.stopPropagation();
    if ($("canned-menu").classList.contains("hidden")) openCannedMenu();
    else closeCannedMenu();
  };
  $("canned-save").onclick = (e) => {
    e.preventDefault();
    saveCanned();
  };
  document.addEventListener("click", (e) => {
    if (!$("notify-menu").contains(e.target)) closeNotifyMenu();
    if (!$("ctx-menu").contains(e.target)) closeCtxMenu();
    if (!$("canned-menu").contains(e.target)) closeCannedMenu();
    if (!$("send-menu").contains(e.target)) closeSendMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("ctx-menu").classList.contains("hidden")) {
      closeCtxMenu();
    }
    if (e.key === "Escape" && !$("send-menu").classList.contains("hidden")) {
      closeSendMenu();
    }
    if (e.key === "Escape" && !$("canned-menu").classList.contains("hidden")) {
      closeCannedMenu();
      $("composer").focus();
    }
    if (e.key === "Escape" && !$("notify-menu").classList.contains("hidden")) {
      closeNotifyMenu();
      $("btn-notify").focus();
    }
  });
  $("btn-enc").onclick = () => {
    const c = S.contacts.get(S.active);
    if (!c) return;
    c.enc = c.enc === "omemo" ? "none" : "omemo";
    wsSend("set_enc", {jid: S.active, mode: c.enc});
    renderChatHeader();
    toast(c.enc === "omemo"
      ? _t("🔒 OMEMO açık — karşı tarafın OMEMO desteklemesi gerekir")
      : _t("🔓 Şifreleme kapalı"));
  };
  $("btn-members").onclick = () => {
    const p = $("members-panel");
    p.classList.toggle("hidden");
    renderMembers();
  };
  $("presence-select").onchange = () =>
    wsSend("set_presence", {show: $("presence-select").value,
                            status: $("presence-status").value});
  $("presence-status").onchange = () =>
    wsSend("set_presence", {show: $("presence-select").value,
                            status: $("presence-status").value});
  $("btn-settings").onclick = openSettings;
  $("s-save").onclick = saveSettings;
  $("s-cancel").onclick = () => $("dlg-settings").close();
  $("btn-logout").onclick = async () => {
    await apiPost("/api/logout", {});
    showLogin(_t("Çıkış yapıldı."));
  };

  const composer = $("composer");
  composer.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendCurrent();
    } else if (e.key === "Escape") {
      clearReplyEdit();
    }
  });
  composer.addEventListener("input", composerInput);
  $("btn-send").onclick = () => sendCurrent();
  $("btn-send").oncontextmenu = (e) => {
    e.preventDefault();
    e.stopPropagation();
    openSendMenu();
  };
  bindLongPress($("btn-send"), () => openSendMenu());
  $("btn-attach").onclick = () => S.active && $("file-input").click();
  $("file-input").onchange = () => {
    for (const f of $("file-input").files) uploadBlob(S.active, f, f.name);
    $("file-input").value = "";
  };
  $("btn-mic").onclick = () => (REC.rec ? recStop() : recStart());
  $("rec-cancel").onclick = () => recStop(true);
  $("btn-back").onclick = () => $("main-view").classList.remove("chat-open");
  $("reply-cancel").onclick = () => {
    S.reply = null;
    $("reply-bar").classList.add("hidden");
  };
  $("edit-cancel").onclick = () => {
    S.editing = null;
    composer.value = "";
    $("edit-bar").classList.add("hidden");
  };

  document.querySelectorAll("[data-ai]").forEach((b) => {
    b.onclick = () => {
      aiSelect(b.dataset.ai);
      if (b.dataset.ai === "summary" && S.active) {
        const c = S.contacts.get(S.active);
        aiRun("summary", {jid: S.active, unread: c?.unread || 0});
      } else if (b.dataset.ai === "digest") {
        aiRun("digest");
      } else if (b.dataset.ai === "tasks") {
        aiTasks();
      }
    };
  });
  $("btn-ai").onclick = () => {
    $("ai-panel").classList.toggle("hidden");
    $("ai-provider").textContent = aiProviderLabel();
  };
  $("ai-close").onclick = () => $("ai-panel").classList.add("hidden");
  $("ai-submit").onclick = aiSubmit;
  $("ai-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); aiSubmit(); }
  });
}

/* ── açılış ──────────────────────────────────────────────────────────── */
async function init() {
  // PWA: kabuk önbelleği + Android bildirimleri (güvenli bağlam gerekir)
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  await loadI18n();
  translateDom(document.body);
  bind();
  if (S.token) {
    try {
      const {status} = await api("/api/settings");
      if (status === 200) {
        $("login-view").classList.add("hidden");
        await showMain();
        return;
      }
    } catch (_) { /* 401 → login */ }
  }
  showLogin();
}

init();
