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
