import { API_BASE } from './api'

/**
 * WebSocket 连接管理器：按频道共享连接（引用计数），断线自动重连 + 30s 心跳保活。
 *
 * 用法：
 *   const unsubscribe = connectWs('task:user:admin', {
 *     onMessage: (msg) => { const { event, data } = msg },
 *     onOpen: () => {},   // 连接建立（可停用轮询降级）
 *     onClose: () => {},  // 连接断开（可恢复轮询降级）
 *   })
 *   // 组件卸载时调用 unsubscribe()
 */
const conns = new Map() // channel -> { ws, listeners, openCbs, closeCbs, closed, timer }

const wsUrl = (channel) => {
  const base = API_BASE.replace(/^http/, 'ws')
  return `${base}/ws/${channel}?token=${encodeURIComponent(localStorage.getItem('token') || '')}`
}

export function connectWs(channel, handlers = {}) {
  const onMessage = typeof handlers === 'function' ? handlers : handlers.onMessage
  const onOpen = typeof handlers === 'function' ? undefined : handlers.onOpen
  const onClose = typeof handlers === 'function' ? undefined : handlers.onClose

  let entry = conns.get(channel)
  if (!entry) {
    entry = { ws: null, listeners: new Set(), openCbs: new Set(), closeCbs: new Set(), closed: false, timer: null }
    conns.set(channel, entry)
    open(entry, channel)
  }
  if (onMessage) entry.listeners.add(onMessage)
  if (onOpen) entry.openCbs.add(onOpen)
  if (onClose) entry.closeCbs.add(onClose)

  return () => {
    if (onMessage) entry.listeners.delete(onMessage)
    if (onOpen) entry.openCbs.delete(onOpen)
    if (onClose) entry.closeCbs.delete(onClose)
    // 无任何订阅者时关闭连接
    if (entry.listeners.size === 0 && entry.openCbs.size === 0 && entry.closeCbs.size === 0) {
      entry.closed = true
      if (entry.timer) clearInterval(entry.timer)
      if (entry.ws) {
        try {
          if (entry.ws.readyState === WebSocket.CONNECTING) {
            // 连接尚未建立时直接 close 会触发 "closed before established" 警告
            // （React StrictMode 双挂载场景）；挂 onopen 后立即关闭，避免泄漏
            entry.ws.onopen = () => { try { entry.ws.close() } catch { /* ignore */ } }
          } else if (entry.ws.readyState === WebSocket.OPEN || entry.ws.readyState === WebSocket.CLOSING) {
            entry.ws.close()
          }
        } catch { /* ignore */ }
      }
      conns.delete(channel)
    }
  }
}

function open(entry, channel) {
  if (entry.closed) return
  let ws
  try {
    ws = new WebSocket(wsUrl(channel))
  } catch {
    return
  }
  entry.ws = ws
  ws.onopen = () => {
    // 心跳保活：规避反向代理空闲断连
    if (entry.timer) clearInterval(entry.timer)
    entry.timer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 30000)
    entry.openCbs.forEach((fn) => { try { fn() } catch { /* ignore */ } })
  }
  ws.onmessage = (evt) => {
    let msg = null
    try {
      msg = JSON.parse(evt.data)
    } catch {
      return
    }
    entry.listeners.forEach((fn) => { try { fn(msg) } catch { /* ignore */ } })
  }
  ws.onclose = () => {
    if (entry.timer) { clearInterval(entry.timer); entry.timer = null }
    entry.closeCbs.forEach((fn) => { try { fn() } catch { /* ignore */ } })
    // 3s 后自动重连（除非已无订阅者）
    if (!entry.closed) setTimeout(() => open(entry, channel), 3000)
  }
  ws.onerror = () => { try { ws.close() } catch { /* ignore */ } }
}

export default connectWs
