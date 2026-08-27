const CACHE = "aciega-static-v3";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return;
  if (event.request.method !== "GET") return;
  const networkFirst =
    event.request.destination === "document" || event.request.destination === "script";
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      if (networkFirst) {
        try {
          const res = await fetch(event.request);
          if (res.ok && url.origin === self.location.origin) cache.put(event.request, res.clone());
          return res;
        } catch {
          const hit = await cache.match(event.request);
          if (hit) return hit;
          throw new Error("offline");
        }
      }
      const hit = await cache.match(event.request);
      if (hit) return hit;
      const res = await fetch(event.request);
      if (res.ok && url.origin === self.location.origin) cache.put(event.request, res.clone());
      return res;
    }),
  );
});
