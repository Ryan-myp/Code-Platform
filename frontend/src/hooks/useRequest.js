import { useState, useEffect, useCallback, useRef } from 'react'
import { pickData } from '../lib/api'

/**
 * 数据请求 Hook
 * - 自动管理 loading / data / error 三态
 * - 支持手动 refresh
 * - 支持立即执行 / 延迟执行 (manual)
 * - 错误自动归一化
 *
 * @param {Function} fetcher - 返回 Promise 的函数，接收 api 实例
 * @param {Object} options
 * @param {boolean} options.manual - 是否手动触发，默认 false（立即执行）
 * @param {Array} options.deps - 依赖项，变化时重新请求
 * @param {boolean} options.pick - 是否自动 pickData 解包，默认 true
 */
export function useRequest(fetcher, options = {}) {
  const { manual = false, deps = [], pick = true } = options
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(!manual)
  const [error, setError] = useState(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const run = useCallback(async (...args) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetcherRef.current(...args)
      const result = pick ? pickData(res) : res
      setData(result)
      return result
    } catch (e) {
      setError(e)
      throw e
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const refresh = useCallback(() => run(), [run])

  useEffect(() => {
    if (!manual) {
      run().catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, loading, error, run, refresh, setData, setError }
}

/**
 * Mutation Hook（用于增删改）
 * - 自动管理 loading
 * - 成功/失败交由调用方处理 toast
 */
export function useMutation(mutator) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const mutatorRef = useRef(mutator)
  mutatorRef.current = mutator

  const run = useCallback(async (...args) => {
    setLoading(true)
    setError(null)
    try {
      const res = await mutatorRef.current(...args)
      return res
    } catch (e) {
      setError(e)
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  return { run, loading, error }
}

export default useRequest
