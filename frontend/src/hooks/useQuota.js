import { useEffect, useState } from 'react'
import { api } from '../lib/api'

/**
 * 剩余额度 Hook
 * - 加载 /api/auth/quota 获取当日额度信息
 * - 监听 quota-exhausted 全局事件自动刷新（额度耗尽时由 api 拦截器派发）
 */
export default function useQuota() {
  const [quota, setQuota] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const res = await api.get('/api/auth/quota')
      setQuota(res.data)
    } catch {
      // 静默失败（未登录等场景不阻塞 UI）
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    const refreshHandler = () => refresh()
    window.addEventListener('quota-exhausted', refreshHandler)
    window.addEventListener('quota-changed', refreshHandler)
    return () => {
      window.removeEventListener('quota-exhausted', refreshHandler)
      window.removeEventListener('quota-changed', refreshHandler)
    }
  }, [])

  return { quota, loading, refresh }
}
