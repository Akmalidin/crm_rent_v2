const CACHE_NAME = 'crm-rental-v3';
const PRECACHE = [
  '/',
  '/offline/',
  '/static/css/base.css',
  '/static/css/responsive.css',
];

// Install: precache shell
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: network first, fallback to cache, then offline page
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  // Skip admin and API
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/api/')) return;

  e.respondWith(
    fetch(e.request)
      .then(resp => {
        if (resp.ok && url.origin === location.origin) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        }
        return resp;
      })
      .catch(() =>
        caches.match(e.request).then(cached => {
          if (cached) return cached;
          // For navigation requests show offline page
          if (e.request.mode === 'navigate') {
            return caches.match('/offline/');
          }
        })
      )
  );
});
