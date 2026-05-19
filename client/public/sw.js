// Minimal service worker — exists so Chrome considers the app installable
// (which unlocks Web Share Target). No caching, just a passthrough fetch handler.

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
  // Passthrough: let the network handle every request.
});
