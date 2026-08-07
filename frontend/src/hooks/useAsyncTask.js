import { useRef, useCallback } from 'react'
import api from '../lib/api'
import { connectWs } from '../lib/ws'

/**
 * 通用异步任务 hook：提交生成任务 → 立即返回 task_id → WS 订阅 task:{task_id} 实时进度
 * （断线自动降级为轮询 GET /api/tasks/{task_id}）
 * 兼容旧后端同步响应（无 task_id 时直接回调 onSuccess）
 *
 * 用法：
 *   const { submitTask, stopPolling, isPolling } = useAsyncTask()
 *   await submitTask('/api/xxx/generate', formData, {
 *     onUpdate: (task) => setCurrentTask(task),   // 进度更新（pending/running/success/failed）
 *     onSuccess: (result) => handleDone(result),  // 任务成功，result 为 worker 返回体
 *     onError: (err) => toast.error(err.message), // 任务失败 / 提交失败
 *   })
 */
export default function useAsyncTask() {
  const timerRef = useRef(null)
  const activeRef = useRef(false)
  const wsUnsubRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (wsUnsubRef.current) {
      wsUnsubRef.current()
      wsUnsubRef.current = null
    }
    activeRef.current = false
  }, [])

  const startPolling = useCallback(
    (taskId, { onUpdate, onSuccess, onError, interval = 3000 }) => {
      stopPolling()
      activeRef.current = true
      const wsOk = { current: false }

      // 终态收尾：停止跟踪并回调（终态事件只带轻量字段，主动拉详情拿完整 result）
      const finish = (fn, arg) => {
        if (!activeRef.current) return
        stopPolling()
        if (fn) fn(arg)
      }

      // WS 事件驱动（主通道）：task_update 实时进度；终态事件拉详情后回调
      wsUnsubRef.current = connectWs(`task:${taskId}`, {
        onOpen: () => {
          wsOk.current = true
        },
        onClose: () => {
          wsOk.current = false
        },
        onMessage: (msg) => {
          if (!activeRef.current) return
          const { event, data } = msg
          if (!data) return
          if (event === 'task_update') {
            if (onUpdate) onUpdate(data)
          } else if (event === 'task_success') {
            api.get(`/api/tasks/${taskId}`).then(
              (res) => finish(onSuccess, res.data?.result || {}),
              () => finish(onSuccess, {})
            )
          } else if (event === 'task_failed' || event === 'task_canceled') {
            api.get(`/api/tasks/${taskId}`).then(
              (res) =>
                finish(onError, {
                  message:
                    res.data?.error || (event === 'task_canceled' ? '任务已取消' : '任务执行失败'),
                  task: res.data,
                }),
              () =>
                finish(onError, {
                  message: event === 'task_canceled' ? '任务已取消' : '任务执行失败',
                })
            )
          }
        },
      })

      // 轮询兜底：仅 WS 未连通时执行（网络抖动/服务端未开启 WS 的场景）
      const poll = async () => {
        if (!activeRef.current || wsOk.current) return
        try {
          const res = await api.get(`/api/tasks/${taskId}`)
          if (!activeRef.current) return
          const t = res.data
          if (onUpdate) onUpdate(t)
          if (t.status === 'success') {
            finish(onSuccess, t.result || {})
          } else if (['failed', 'interrupted', 'canceled'].includes(t.status)) {
            finish(onError, {
              message: t.error || (t.status === 'canceled' ? '任务已取消' : '任务执行失败'),
              task: t,
            })
          }
        } catch {
          // 网络抖动：保留轮询，下次继续
        }
      }
      poll()
      timerRef.current = setInterval(poll, interval)
    },
    [stopPolling]
  )

  /**
   * 提交任务并自动跟踪进度
   * @param {string} url 提交接口（POST）
   * @param {FormData|object} body 请求体
   * @param {object} opts { onUpdate, onSuccess, onError, timeout }
   * @returns {Promise<{task_id: string|null, sync: boolean}>}
   */
  const submitTask = useCallback(
    async (url, body, opts = {}) => {
      const { onUpdate, onSuccess, onError, timeout = 30000 } = opts
      try {
        const res = await api.post(url, body, { timeout })
        const data = res.data
        if (data?.task_id) {
          // 异步任务模式：后台 worker 执行，WS 订阅 + 轮询兜底
          if (onUpdate)
            onUpdate({ id: data.task_id, status: 'pending', progress: 0, stage: '任务排队中…' })
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
    },
    [startPolling]
  )

  return { submitTask, startPolling, stopPolling }
}
