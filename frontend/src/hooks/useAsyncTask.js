import { useRef, useCallback } from 'react'
import api from '../lib/api'

/**
 * 通用异步任务 hook：提交生成任务 → 立即返回 task_id → 轮询 GET /api/tasks/{task_id}
 * 兼容旧后端同步响应（无 task_id 时直接回调 onSuccess）
 *
 * 用法：
 *   const { submitTask, stopPolling, isPolling } = useAsyncTask()
 *   await submitTask('/api/xxx/generate', formData, {
 *     onUpdate: (task) => setCurrentTask(task),   // 每次轮询进度（pending/running/success/failed）
 *     onSuccess: (result) => handleDone(result),  // 任务成功，result 为 worker 返回体
 *     onError: (err) => toast.error(err.message), // 任务失败 / 提交失败
 *   })
 */
export default function useAsyncTask() {
  const timerRef = useRef(null)
  const activeRef = useRef(false)

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    activeRef.current = false
  }, [])

  const startPolling = useCallback((taskId, { onUpdate, onSuccess, onError, interval = 2000 }) => {
    stopPolling()
    activeRef.current = true
    const poll = async () => {
      if (!activeRef.current) return
      try {
        const res = await api.get(`/api/tasks/${taskId}`)
        if (!activeRef.current) return
        const t = res.data
        if (onUpdate) onUpdate(t)
        if (t.status === 'success') {
          stopPolling()
          if (onSuccess) onSuccess(t.result || {})
        } else if (['failed', 'interrupted', 'canceled'].includes(t.status)) {
          stopPolling()
          if (onError) onError({ message: t.error || (t.status === 'canceled' ? '任务已取消' : '任务执行失败'), task: t })
        }
      } catch {
        // 网络抖动：保留轮询，下次继续
      }
    }
    poll()
    timerRef.current = setInterval(poll, interval)
  }, [stopPolling])

  /**
   * 提交任务并自动轮询
   * @param {string} url 提交接口（POST）
   * @param {FormData|object} body 请求体
   * @param {object} opts { onUpdate, onSuccess, onError, timeout }
   * @returns {Promise<{task_id: string|null, sync: boolean}>}
   */
  const submitTask = useCallback(async (url, body, opts = {}) => {
    const { onUpdate, onSuccess, onError, timeout = 30000 } = opts
    try {
      const res = await api.post(url, body, { timeout })
      const data = res.data
      if (data?.task_id) {
        // 异步任务模式：后台 worker 执行，轮询进度
        if (onUpdate) onUpdate({ id: data.task_id, status: 'pending', progress: 0, stage: '任务排队中…' })
        startPolling(data.task_id, { onUpdate, onSuccess, onError })
        return { task_id: data.task_id, sync: false }
      }
      // 兼容同步响应（sync=1 或旧后端）：直接回调
      if (onSuccess) onSuccess(data)
      return { task_id: null, sync: true }
    } catch (e) {
      if (onError) onError(e)
      return { task_id: null, sync: false, error: e }
    }
  }, [startPolling])

  return { submitTask, startPolling, stopPolling }
}
