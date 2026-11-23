/* xmpp.py web — service worker.
 *
 * Görevleri: (1) Android'de bildirim (sayfa içinden `new Notification`
 * yasak; app.js reg.showNotification kullanır) ve bildirime dokununca
 * uygulamayı öne getirme, (2) PWA kurulabilirliği, (3) arayüz kabuğunun
 * çevrimdışı açılabilmesi. Yalnız statik kabuk önbelleğe girer: /api ve /ws
 * (mesajlar, medya, token) ASLA önbelleğe alınmaz ve ele geçirilmez.
 * Kabuk ağ-önce sunulur: güncelleme hemen görünür, önbellek yalnız yedektir.
 */
const CACHE = "xmpp-web-shell-v1";
const SHELL = ["/", "/static/app.js", "/static/app.css",
               "/static/icon-192.png", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE)
    .then((c) => c.addAll(SHELL)).catch(() => {})
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE)
                                    .map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (!SHELL.includes(url.pathname) && !url.pathname.startsWith("/static/")) {
    return;                       // /api, /ws, medya: tarayıcıya bırak
  }
  event.respondWith(fetch(req).then((res) => {
    if (res.ok && res.type === "basic") {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
    }
    return res;
  }).catch(() => caches.match(req).then((hit) => hit || Response.error())));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.matchAll({type: "window", includeUncontrolled: true})
    .then((list) => {
      for (const c of list) if ("focus" in c) return c.focus();
      return self.clients.openWindow("/");
    }));
});
