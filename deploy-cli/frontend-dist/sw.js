/**
 * 一次性自毁 Service Worker（本地版不使用 SW）
 *
 * 背景：旧版注册的 SW 以 Cache First 缓存了旧 index.html 与静态资源，
 * 升级后仍从缓存喂旧页面 → 引用旧哈希 JS → 404/MIME 报错，且旧页面会反复注册旧 SW。
 * 本文件部署后：浏览器导航时检测到 sw.js 内容变化 → 安装本版本 →
 * 立即注销自身并清空所有缓存，之后请求全部直连服务器，彻底打破缓存循环。
 */
self.addEventListener('install', () => {
  self.skipWaiting()
  self.registration.unregister()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

// 不拦截任何请求：页面/静态资源全部直连服务器
self.addEventListener('fetch', () => {})
