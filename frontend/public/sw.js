const CACHE = 'cardscan-cache-v1';
const ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  // Don’t cache API POST/PUT, only GET same-origin navigations and assets
  const isGET = request.method === 'GET';
  const isSameOrigin = url.origin === self.location.origin;
  if (!isGET || !isSameOrigin) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/index.html'))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) =>
      cached || fetch(request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return resp;
      }).catch(() => cached)
    )
  );
});

self.addEventListener('push', (event) => {
  const data = event.data?.json() || { title: 'Nowe zamówienie!', body: 'Otrzymano nowe zamówienie w sklepie.' };
  const title = data.title;
  const options = {
    body: data.body,
    icon: '/logo.png',
    badge: '/logo.png'
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});
