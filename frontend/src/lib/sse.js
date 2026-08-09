import { API_BASE } from './api'

/**
 * SSE 流式客户端 — fetch + ReadableStream 解析 Server-Sent Events
 *
 * 用法：
 *   const stream = fetchSSE('/api/agents/xx/run/stream', {
 *     body: { message: '你好' },
 *     onEvent: (event, data) => {   // event: delta / done / error / ...
 *       if (event === 'delta') { ... }
 *     },
 *     onError: (err) => {},
 *     onClose: () => {},            // 流结束（正常或异常）
 *   })
 *   stream.abort()                  // 主动停止（停止生成按钮）
 *
 * 说明：
 * - 自动携带 JWT（与 api.js 一致）
 * - 事件块按空行（\n\n）切分，兼容 \r\n
 * - 非 2xx 响应解析后端 detail / error.message 作为错误文案
 * - AbortError 静默处理（用户主动停止不算错误）
 */
export function fetchSSE(url, { method = 'POST', body, headers = {}, onEvent, onError, onClose } = {}) {
  const controller = new AbortController()
  const token = localStorage.getItem('token')

  async function run() {
    let response
    try {
      response = await fetch(`${API_BASE}${url}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })
    } catch {
      onError?.(new Error('网络连接失败，请检查服务是否已启动'))
      onClose?.()
      return
    }

    if (!response.ok) {
      let detail = `请求失败（${response.status}）`
      try {
        const j = await response.json()
        detail = j.detail || j.error?.message || detail
      } catch {
        /* 非 JSON 响应保持默认文案 */
      }
      onError?.(new Error(detail))
      onClose?.()
      return
    }
    if (!response.body) {
      onError?.(new Error('当前浏览器不支持流式响应'))
      onClose?.()
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const block = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const lines = block.split('\n').map((l) => l.replace(/\r$/, ''))
          let event = 'message'
          const dataLines = []
          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
          }
          if (dataLines.length === 0) continue
          const raw = dataLines.join('\n')
          let data
          try {
            data = JSON.parse(raw)
          } catch {
            data = raw
          }
          onEvent?.(event, data)
        }
      }
    } catch (e) {
      // 用户主动 abort 不算错误
      if (e?.name !== 'AbortError') {
        onError?.(new Error('流式连接中断，请重试'))
      }
    } finally {
      onClose?.()
    }
  }

  run()
  return { abort: () => controller.abort() }
}

export default fetchSSE
