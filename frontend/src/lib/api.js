import axios from 'axios'
import { friendlyError } from './errors'

/**
 * 统一 API 实例
 * - baseURL 从环境变量读取，默认指向本地后端
 * - 请求拦截器自动注入 JWT
 * - 响应拦截器统一错误处理与 401 登出
 */
/**
 * API 基地址（部署感知）：
 * - VITE_API_URL 显式配置优先
 * - 否则 npx 部署模式（同源：前端端口非 8888）→ 使用相对路径 ''（走同源 /api）
 * - 本地开发默认 → http://localhost:8888
 */
function resolveApiBase() {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL
  const port = window.location.port
  // 前端端口非 8888 时视为同源部署（npx code-platform web --port 3000），API 走相对路径
  if (port && port !== '8888' && port !== '5173') return ''
  return 'http://localhost:8888'
}

const API_BASE = resolveApiBase()

export { API_BASE }

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：注入 token + FormData 自动适配
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // FormData 时移除 Content-Type，让浏览器自动设置 multipart/form-data 及 boundary
  if (config.data instanceof FormData) {
    config.headers['Content-Type'] = undefined
  }
  return config
})

// 响应拦截器：统一错误处理
// 计费端点关键词：成功调用后派发 quota-changed 事件刷新额度展示
const QUOTA_KEYWORDS = ['/run', '/generate', '/translate', '/review', '/execute', '/render', '/sing']

api.interceptors.response.use(
  (response) => {
    const url = response.config?.url || ''
    const method = (response.config?.method || '').toLowerCase()
    if (method === 'post' && QUOTA_KEYWORDS.some((k) => url.includes(k))) {
      window.dispatchEvent(new CustomEvent('quota-changed'))
    }
    return response
  },
  (error) => {
    const status = error.response?.status
    // 后端明确文案（detail/message）优先；无则对 axios 层错误做友好翻译
    const detail =
      error.response?.data?.detail || error.response?.data?.message || friendlyError(error.message)

    // 401 未授权：清除凭证并跳转登录
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      delete axios.defaults.headers.common['Authorization']
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    // 402 额度不足：派发全局事件（携带后端分层文案，供 Notifier 统一引导）
    if (status === 402) {
      window.dispatchEvent(new CustomEvent('quota-exhausted', { detail: { message: detail } }))
    }
    // 归一化错误对象
    const normalized = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    normalized.status = status
    normalized.original = error
    return Promise.reject(normalized)
  }
)

/**
 * 提取响应数据，兼容裸返回 / {data} 包装 / {items} 包装
 */
export function pickData(res) {
  if (!res || !res.data) return res
  const body = res.data
  if (body && typeof body === 'object' && 'data' in body && Object.keys(body).length <= 3) {
    return body.data
  }
  return body
}

export default api
