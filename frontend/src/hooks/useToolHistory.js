import { useCallback, useEffect, useState } from 'react'

/**
 * 工具历史管理（localStorage 持久化）
 *
 * 专业基线：每个工具都应支持"历史记录 → 一键复用 / 删除 / 清空"，
 * 让生成结果可回溯、可对比、可复用（资产化闭环）。
 *
 * @param {string} storageKey 唯一存储键（如 'data_analyzer_history_v1'）
 * @param {number} maxItems   保留上限（默认 20）
 * @returns {{ history, add, remove, clear, update }}
 */
export default function useToolHistory(storageKey, maxItems = 20) {
  const [history, setHistory] = useState(() => {
    try {
      const raw = localStorage.getItem(storageKey)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(history.slice(0, maxItems)))
    } catch {
      /* localStorage 不可用时静默降级 */
    }
  }, [history, storageKey, maxItems])

  /** 新增一条记录（放最前，自动裁剪上限） */
  const add = useCallback(
    (item) => {
      setHistory((prev) => [{ ts: new Date().toISOString(), ...item }, ...prev].slice(0, maxItems))
    },
    [maxItems]
  )

  /** 删除单条 */
  const remove = useCallback((index) => {
    setHistory((prev) => prev.filter((_, i) => i !== index))
  }, [])

  /** 清空全部 */
  const clear = useCallback(() => {
    setHistory([])
  }, [])

  /** 更新指定条目（如补写执行结果） */
  const update = useCallback((index, patch) => {
    setHistory((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)))
  }, [])

  return { history, add, remove, clear, update }
}
