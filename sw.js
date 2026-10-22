const CACHE = 'yn-ai-v9';
const ASSETS = [
  './index.html',
  './manifest.json',
  './assets/brand.css',
  './construction/index.html',
  './construction/trend.html',
  './news/index.html',
  './news-data.js',
  './weather-data.js'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// 네트워크 우선: 온라인이면 항상 최신 파일을 받아오고, 오프라인일 때만 캐시로 대체합니다.
// 우리 사이트 파일은 브라우저 HTTP 캐시(최대 10분)도 건너뛰고 서버에 확인 — 날씨·뉴스가 옛 화면으로 남지 않게.
self.addEventListener('fetch', e => {
  if (e.request.url.includes('api.anthropic.com')) return;
  if (e.request.url.includes('cdn.jsdelivr.net')) return;

  const req = e.request;
  const own = req.method === 'GET' && new URL(req.url).origin === self.location.origin;
  const net = !own ? fetch(req)
    : req.mode === 'navigate' ? fetch(req.url, { cache: 'no-cache', credentials: 'same-origin', redirect: 'manual' })
    : fetch(req.url, { cache: 'no-cache', credentials: 'same-origin' });

  e.respondWith(
    net.then(res => {
      if (res && res.status === 200 && res.type !== 'opaque') {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(req, clone));
      }
      return res;
    }).catch(() =>
      caches.match(req).then(cached => cached || caches.match('./index.html'))
    )
  );
});
