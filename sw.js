// service worker بسيط - مطلوب وجوده فقط عشان المتصفح يفعّل خاصية "تثبيت التطبيق"
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // بدون أي كاش خاص، بس بيمرر الطلبات عادي للسيرفر
  event.respondWith(fetch(event.request));
});
