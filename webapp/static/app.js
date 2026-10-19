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
  if (diff === 0) return "Bugün";
  if (diff === 1) return "Dün";
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
  if (res.status === 401) { showLogin("Oturum sona erdi."); throw new Error("401"); }
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
        resolve({ok: false, error: "Zaman aşımı"});
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
    toast("✓ Bağlandı");
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
    });
    if (jid !== S.active || document.hidden) {
      const c = S.contacts.get(jid) || mkUnknown(jid);
      S.contacts.set(jid, c);
      if (jid !== S.active) {
        c.unread = (c.unread || 0) + 1;
        notify(data.nick || jid, data.body);
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
      stored_at: new Date().toISOString(),
    });
  },
  own_sent(data) {
    appendMessage(data.to, {
      sender: "Ben", body: data.body, is_me: true, ts: data.ts,
      mid: data.mid, encrypted: data.enc !== "none",
      reply: data.reply, reactions: {},
      stored_at: new Date().toISOString(),
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
    openChat(room);
    toast(`✓ ${room} odasına katıldın`);
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
      list.innerHTML = '<li class="dim">Oda bulunamadı.</li>';
      return;
    }
    for (const room of data) {
      const li = document.createElement("li");
      const name = typeof room === "string" ? room : (room.jid || "?");
      li.innerHTML = `<span>${esc(name)}</span>`;
      const b = document.createElement("button");
      b.textContent = "Katıl";
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
    toastActions(`🍵 Davet: ${data.room}` +
                 (data.reason ? ` — ${data.reason}` : ""),
                 [["Katıl", () => {
                   $("j-room").value = data.room;
                   $("dlg-join").showModal();
                 }], ["Yok say", () => {}]]);
  },
  subscribe_req(data) {
    toastActions(`👥 ${data} abonelik istiyor`,
      [["Kabul", () => wsSend("approve_subscribe",
                             {jid: data, approve: true})],
       ["Reddet", () => wsSend("approve_subscribe",
                               {jid: data, approve: false})]]);
  },
  bookmarks_update(data) { toast(`🔖 Yer imi güncellendi: ${data.kind || ""}`); },
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
  sys_msg(data) { toast(data); },
  error(data) { toast(data, true); },
  disconnected() { toast("Bağlantı koptu — yeniden bağlanıyor…", true);
                   $("me-dot").className = "dot"; },
  conn_failed(data) { toast(`Bağlantı hatası: ${data}`, true); },
  auth_failed() {
    showLogin("Kimlik doğrulama başarısız — parolayı kontrol edin.");
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
  if (Notification.permission === "granted") {
    new Notification(`Mesaj — ${title}`, {body: (body || "").slice(0, 100)});
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission();
  }
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
    const label = c.room ? `# ${c.name}` : c.name;
    li.innerHTML =
      `<span class="dot ${esc(cls)}"></span>` +
      `<div class="name"><b>${esc(label)}</b>` +
      `<div class="sub">${esc(c.typing ? "yazıyor…" :
        c.room ? (c.subject || c.jid) : c.jid)}</div></div>` +
      (c.unread ? `<span class="badge">${c.unread}</span>` : "");
    li.onclick = () => openChat(c.jid);
    list.appendChild(li);
  }
  let total = 0;
  for (const c of S.contacts.values()) total += c.unread || 0;
  document.title = (total ? `[${total}] ` : "") + "XMPP — Web";
}

/* ── sohbet ──────────────────────────────────────────────────────────── */
async function openChat(jid) {
  S.active = jid;
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
  wsSend("open_chat", {jid});   // sunucu okunmamışı düşürür + boşsa MAM
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
  const enc = m.encrypted ? '<span title="şifreli">🔒</span>' : "";
  const reply = m.reply
    ? `<div class="reply-q">↩ <b>${esc(m.reply.sender || "")}</b> ` +
      `${esc((m.reply.body || "").slice(0, 90))}</div>` : "";
  let bodyHtml;
  if (m.body === RETRACTED) {
    bodyHtml = `<span class="enc-chip">${esc(m.body)}</span>`;
  } else if (m.oob && /^https?:\/\//.test(m.oob)) {
    const isImg = /\.(png|jpe?g|gif|webp|avif)(\?|$)/i.test(m.oob) &&
      S.settings?.general?.remote_previews !== false;
    bodyHtml = linkify(m.body) +
      `<a href="${esc(m.oob)}" target="_blank" rel="noopener noreferrer">` +
      (isImg ? `<img class="preview" loading="lazy" src="${esc(m.oob)}">`
             : `<div class="enc-chip">📎 ${esc(m.oob)}</div>`) +
      `</a>`;
  } else if (/^aesgcm:\/\//.test(m.oob || "")) {
    bodyHtml = linkify(m.body) +
      `<div class="enc-chip">🔒 şifreli dosya (masaüstü istemcide açılır)</div>`;
  } else {
    bodyHtml = linkify(m.body);
  }
  const reacts = Object.entries(m.reactions || {})
    .filter(([, senders]) => senders.length)
    .map(([emoji, senders]) =>
      `<span class="${senders.includes("Ben") ? "mine" : ""}" ` +
      `title="${esc(senders.join(", "))}" data-react="${esc(emoji)}">` +
      `${esc(emoji)} ${senders.length}</span>`).join("");
  const canAct = m.mid && m.body !== RETRACTED;
  const tools = canAct
    ? `<div class="row-tools">` +
      `<button data-act="reply" title="Yanıtla">↩</button>` +
      `<button data-act="react" title="Tepki">😊</button>` +
      (m.is_me ? `<button data-act="edit" title="Düzenle">✎</button>` +
                 `<button data-act="retract" title="Geri çek">🗑</button>`
               : "") +
      `</div>` : "";
  const midAttr = m.mid ? ` data-mid="${esc(m.mid)}"` : "";
  return `<div class="row ${m.is_me ? "me" : "them"}"${midAttr}>${tools}` +
    `<div class="bubble">` +
    (showSender ? `<div class="sender">${esc(m.sender)}</div>` : "") +
    reply + bodyHtml +
    `<div class="meta"><span>${esc(m.ts || "")}</span>${enc}${ticks}</div>` +
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
    box.innerHTML = `<div class="empty-hint">Soldan bir sohbet seçin</div>`;
    return;
  }
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  let html = "";
  if (h.has_more && h.msgs.length) {
    html += `<div class="sysline"><button id="btn-older">↑ daha eski</button></div>`;
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
  box.innerHTML = html || `<div class="empty-hint">Henüz mesaj yok</div>`;
  box.querySelectorAll("[data-act]").forEach((b) => {
    b.onclick = () => rowAction(b.dataset.act, b.closest(".row"));
  });
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

function renderChatHeader() {
  const c = S.active ? S.contacts.get(S.active) : null;
  const encBtn = $("btn-enc"), memBtn = $("btn-members"),
        leaveBtn = $("btn-leave-room"), dot = $("chat-dot");
  if (!c) {
    $("chat-name").textContent = "Bir sohbet seçin";
    $("chat-sub").textContent = "";
    dot.classList.add("hidden");
    encBtn.classList.add("hidden");
    memBtn.classList.add("hidden");
    leaveBtn.classList.add("hidden");
    return;
  }
  $("chat-name").textContent = c.room ? `# ${c.name}` : c.name;
  const p = c.presence || {};
  const awayTxt = {away: "uzakta", xa: "çok uzakta", dnd: "rahatsız etmeyin",
                   chat: "sohbet için müsait"};
  const sub = c.room
    ? (c.subject || `${Object.keys(c.members).length} üye`)
    : (p.ptype === "unavailable" ? "çevrimdışı"
       : awayTxt[p.pshow] || (p.ptype === "available" ? "çevrimiçi" : "—"));
  $("chat-sub").textContent = c.typing ? "✍ yazıyor…" : sub;
  if (!c.room) {
    dot.classList.remove("hidden");
    dot.className = "dot " + presenceClass(c);
  } else {
    dot.classList.add("hidden");
  }
  encBtn.classList.remove("hidden");
  memBtn.classList.toggle("hidden", !c.room);
  leaveBtn.classList.toggle("hidden", !c.room);
  encBtn.textContent = c.enc === "omemo" ? "🔒 OMEMO" : "🔓 Düz";
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
  }).join("") || `<li class="dim">Kimse yok</li>`;
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
      `↩ <b>${esc(S.reply.sender)}</b> ${esc(S.reply.body)}`;
    $("reply-bar").classList.remove("hidden");
    $("composer").focus();
  } else if (act === "edit") {
    S.editing = {mid, to: S.active};
    $("composer").value = row.body;
    $("edit-bar").classList.remove("hidden");
    $("composer").focus();
  } else if (act === "retract") {
    wsSend("retract", {to: S.active, mid});
  } else if (act === "react") {
    const pick = prompt("Emoji: " + QUICK_EMOJIS.join(" "), "👍");
    if (pick) toggleReaction(mid, pick.trim());
  }
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

async function sendCurrent(force = false) {
  const box = $("composer");
  const body = box.value.trim();
  if (!body || !S.active) return;
  const enc = S.contacts.get(S.active)?.enc || "none";
  if (S.editing) {
    await wsSend("correct", {to: S.editing.to, mid: S.editing.mid, body});
    box.value = "";
    clearReplyEdit();
    return;
  }
  const res = await wsSend("send",
    {to: S.active, body, enc, force, reply_to: S.reply});
  if (res.leak && !force) {
    showLeakDialog(res.findings, () => sendCurrent(true));
    return;
  }
  if (!res.ok && res.error) toast(res.error, true);
  box.value = "";
  clearReplyEdit();
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
    return `🖥 Yerel · ${ai.ollama_model}`;
  return "AI kapalı";
}

async function aiRun(mode, extra = {}) {
  const out = $("ai-output");
  const body = {allow_cloud: $("ai-allow-cloud").checked, ...extra};
  $("ai-provider").textContent = aiProviderLabel();
  out.innerHTML = `<span class="ai-busy">⏳ Çalışıyor…</span>`;
  const {status, data} = await apiPost(`/api/ai/${mode}`, body);
  if (status === 403) {
    $("ai-cloud-row").classList.remove("hidden");
    out.innerHTML = `🛡 ${esc(data.error || "İzin gerekli.")}` +
      `<div class="src">Onay kutusunu işaretleyip yeniden dene — yalnız bu istek için geçerli olur.</div>`;
    return;
  }
  if (!data.text) {
    out.innerHTML = `✗ ${esc(data.error || "Yanıt alınamadı.")}`;
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
    mode === "assistant";
  $("ai-input-row").classList.toggle("hidden", !needsInput);
  $("ai-input").placeholder =
    mode === "ask" ? "Geçmişte ara…" :
    mode === "translate" ? "Çevrilecek metin…" : "Asistana yaz…";
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
  $("s-theme").innerHTML = (data.themes || []).map((t) =>
    `<option value="${esc(t)}" ${t === g.theme ? "selected" : ""}>${esc(t)}</option>`).join("");
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
    ? "Kayıtlı anahtar var — değiştirmek için yazın" : "Anahtar yok";
  $("s-cloud-enc").checked = !!ai.cloud_for_encrypted;
  $("s-leak").checked = !!ai.leak_guard;
  $("s-auto-stt").checked = !!ai.auto_transcribe;
  $("s-inline").checked = !!ai.inline_complete;
  $("s-away").checked = !!ai.away_drafts;
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
  };
  const body = {
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
    toast("✓ Ayarlar kaydedildi");
  } else {
    toast(data.error || "Ayarlar kaydedilemedi", true);
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
  if (Notification.permission === "default") Notification.requestPermission();
}

/* ── olay bağlama ────────────────────────────────────────────────────── */
function bind() {
  $("login-form").onsubmit = async (e) => {
    e.preventDefault();
    const btn = $("l-submit");
    btn.disabled = true;
    btn.textContent = "Bağlanıyor…";
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
        if (confirm(`Zaten ${data.connected_as} olarak bağlı bir oturum var. Kapatıp devam edilsin mi?`)) {
          const r2 = await apiPost("/api/login", {
            jid: $("l-jid").value.trim(), password: $("l-pw").value,
            server: $("l-server").value.trim(),
            port: parseInt($("l-port").value || "5222", 10),
            remember: $("l-remember").checked, force: true});
          if (r2.status === 200) {
            S.token = r2.data.token;
            sessionStorage.setItem("xmpp_web_token", r2.data.token);
            await showMain();
          } else toast(r2.data.error || "Giriş başarısız", true);
        }
      } else {
        $("l-error").textContent = data.error || "Giriş başarısız.";
        $("l-error").classList.remove("hidden");
      }
    } finally {
      btn.disabled = false;
      btn.textContent = "Bağlan";
    }
  };

  $("filter").oninput = renderContacts;
  $("btn-join-room").onclick = () => {
    $("j-nick").value = S.jid.split("@")[0] || "";
    $("dlg-join").showModal();
  };
  $("j-go").onclick = (e) => {
    e.preventDefault();
    const room = $("j-room").value.trim();
    if (room) wsSend("join_room", {room, nick: $("j-nick").value.trim()});
    $("dlg-join").close();
  };
  $("rooms-close").onclick = () => $("dlg-rooms").close();
  $("btn-discover")?.addEventListener("click", async () => {
    $("dlg-rooms").showModal();
    await wsSend("discover_rooms", {});
  });
  $("btn-leave-room").onclick = () => {
    if (S.active && confirm(`${S.active} odasından ayrıl?`))
      wsSend("leave_room", {room: S.active});
  };
  $("btn-enc").onclick = () => {
    const c = S.contacts.get(S.active);
    if (!c) return;
    c.enc = c.enc === "omemo" ? "none" : "omemo";
    wsSend("set_enc", {jid: S.active, mode: c.enc});
    renderChatHeader();
    toast(c.enc === "omemo"
      ? "🔒 OMEMO açık — karşı tarafın OMEMO desteklemesi gerekir"
      : "🔓 Şifreleme kapalı");
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
    showLogin("Çıkış yapıldı.");
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
      }
    };
  });
  $("ai-close").onclick = () => $("ai-panel").classList.add("hidden");
  $("ai-submit").onclick = aiSubmit;
  $("ai-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); aiSubmit(); }
  });
}

/* ── açılış ──────────────────────────────────────────────────────────── */
async function init() {
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
