import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'

// 首帧主题同步：渲染前恢复深色模式，避免闪烁
;(function initTheme() {
  try {
    const saved = localStorage.getItem('theme')
    const dark =
      saved === 'dark' || (!saved && window.matchMedia?.('(prefers-color-scheme: dark)').matches)
    document.documentElement.classList.toggle('dark', dark)
  } catch {
    /* ignore */
  }
})()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

// PWA：仅生产构建注册 Service Worker（开发模式避免缓存干扰 HMR）
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('Service Worker 注册失败（不影响使用）:', err)
    })
  })
}
