/*
 * Service worker: offline fallback only.
 *
 * Scope is deliberately narrow. Everything this app does that matters --
 * generating a question, scoring an answer, building a report -- is a live
 * call to the API, so there is no useful "offline mode" to fake. Caching
 * app shells aggressively would only risk serving a stale build after a
 * deploy, which is a much more common failure than being offline.
 *
 * So this does one job: when a NAVIGATION fails because the network is gone,
 * show a real page explaining that instead of the browser's dinosaur. That
 * is also what an installed app (and a Play TWA) needs in order not to look
 * broken when the user is on the tube.
 */

const CACHE = "reflectinterview-offline-v1";
const OFFLINE_URL = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll([OFFLINE_URL, "/icon-192.png"]))
      // Take over without waiting for every existing tab to close, so a
      // fixed worker ships on the next load rather than the next browser
      // restart.
      .then(() => self.skipWaiting()),
  );
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
  const { request } = event;

  // Only navigations. API calls, static chunks and everything else go
  // straight to the network untouched -- intercepting them would mean this
  // worker could serve a stale chunk from a previous deploy.
  if (request.mode !== "navigate") return;

  event.respondWith(
    fetch(request).catch(async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(OFFLINE_URL);
      return (
        cached ||
        new Response("You are offline.", {
          status: 503,
          headers: { "Content-Type": "text/plain" },
        })
      );
    }),
  );
});
