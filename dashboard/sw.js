const CACHE_NAME = 'disha-field-ops-v1';
const URLS_TO_CACHE = [
  '/',
  '/field_ops.html',
  '/css/style.css',
  '/js/field_ops.js',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(URLS_TO_CACHE);
      })
  );
});

self.addEventListener('fetch', event => {
  // Try network first, then fallback to cache
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request);
    })
  );
});

// Cache dynamic API responses to keep app functional offline
self.addEventListener('fetch', event => {
  if (event.request.url.includes('127.0.0.1:8001') && event.request.method === 'GET') {
    event.respondWith(
      caches.open('disha-api-cache').then(cache => {
        return fetch(event.request).then(response => {
          cache.put(event.request, response.clone());
          return response;
        }).catch(() => {
          return cache.match(event.request);
        });
      })
    );
  }
});
