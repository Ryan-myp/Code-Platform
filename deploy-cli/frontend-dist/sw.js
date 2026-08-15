/**
 *  Service Worker — PWA 离线缓存
 *  策略：先缓存后网络（Cache First）用于静态资源；网络优先用于 API
 */
const CACHE_NAME = 'xiaotuan-v1'
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
]

// 安装：预缓存核心资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  )
  self.skipWaiting()
})

// 激活：清理旧缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

// 请求策略
self.addEventListener('fetch', (event) => {
  const { request } = event
  // API 请求：网络优先，失败回退缓存
  if (request.url.includes('/api/')) {
    event.respondWith(
      fetch(request).catch(() => caches.match(request))
    )
    return
  }
  // 静态资源：Cache First
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  )
})
