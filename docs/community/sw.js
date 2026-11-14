// Wire Now Community: shows silent pop-ups (no sound, no vibration).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (_) { d = { body: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(d.title || "Wire Now", {
    body: d.body || "Something new for you",
    icon: "icon-192.png",
    badge: "icon-192.png",
    silent: true,            // no sound
    vibrate: [],             // no vibration
    tag: d.link || "wirenow", // one pop-up per chat or post, not a pile
    renotify: false,
    data: { link: d.link || "" }
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL("./" + (event.notification.data.link || ""), self.registration.scope).href;
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const w of wins) {
      if (w.url.startsWith(self.registration.scope)) { await w.focus(); return w.navigate(url); }
    }
    return self.clients.openWindow(url);
  })());
});
