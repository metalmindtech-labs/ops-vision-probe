// LearnForge Opportunity Radar — Service Worker
// Strategy: network-first for /api (always fresh data), stale-while-revalidate
// for app shell + static assets so the app installs and launches offline.

const CACHE = "radar-shell-v2";
const SHELL = ["/", "/index.html", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (e) => {
    e.waitUntil(
        caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => undefined)
    );
    self.skipWaiting();
});

self.addEventListener("activate", (e) => {
    e.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") return;

    const url = new URL(req.url);

    // Never cache API or SSE — always live data
    if (url.pathname.startsWith("/api/")) return;

    // Stale-while-revalidate for same-origin GETs
    if (url.origin === self.location.origin) {
        event.respondWith(
            caches.open(CACHE).then(async (cache) => {
                const cached = await cache.match(req);
                const networkPromise = fetch(req)
                    .then((res) => {
                        if (res && res.status === 200 && res.type === "basic") {
                            cache.put(req, res.clone());
                        }
                        return res;
                    })
                    .catch(() => cached);
                return cached || networkPromise;
            })
        );
    }
});
