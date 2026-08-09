/* 小团智能平台 Service Worker
 * 策略：
 *  - 预缓存应用外壳（首页/图标/manifest）
 *  - /assets/*（带 hash 内容寻址）→ 缓存优先（永久缓存，文件变化即新 URL）
 *  - 其它同源 GET（页面/API 之外的普通请求）→ 网络优先，失败回退缓存（离线可用）
 *  - 版本号变更即整体替换缓存，避免旧资源残留
 */
const SW_VERSION = 'v1.0.0'
const CACHE_NAME = `xiaotuan-${SW_VERSION}`
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/icons/icon-192.png',
  '/icons/icon-512.png'
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) {
    return // 非 GET / 跨域（API 走代理或后端直连）不拦截
  }
  // 带 hash 的构建资源：缓存优先
  if (request.url.includes('/assets/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((resp) => {
        const clone = resp.clone()
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone))
        return resp
      }))
    )
    return
  }
  // 其它同源 GET：网络优先，离线回退缓存
  event.respondWith(
    fetch(request)
      .then((resp) => {
        if (resp.ok) {
          const clone = resp.clone()
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone))
        }
        return resp
      })
      .catch(() => caches.match(request).then((cached) => cached || caches.match('/index.html')))
  )
})
