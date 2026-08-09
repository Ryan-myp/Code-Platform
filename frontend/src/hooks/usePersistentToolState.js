import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 工具输入态自动持久化（localStorage 版本化）
 *
 * 专业基线：创作类工具在输入过程中刷新 / 误关页面不丢工作内容（耐用性）。
 * - 输入内容（标题 / 提示词 / 参数）自动保存，页面重开自动恢复
 * - key 携带版本号，数据结构变更时 bump version 即可自动失效旧缓存
 * - 仅持久化 JSON 可序列化的小体积字段；超大内容（如 base64 图片）用 exclude 显式排除
 * - 容量防护：超过 maxBytes 时放弃保存（避免撑爆 localStorage）
 *
 * @param {string} key 存储键（自动追加 _v{version} 后缀）
 * @param {object} initialState 初始状态
 * @param {object} [options]
 * @param {number} [options.version=1] 结构版本号，变更结构时 +1 使旧缓存失效
 * @param {string[]} [options.exclude=[]] 不持久化的字段名（大体积 / 运行时字段）
 * @param {number} [options.maxBytes=512*1024] 单次保存体积上限
 * @returns {[object, Function, { clear: Function }]} [state, setState, { clear }]
 */
export default function usePersistentToolState(key, initialState, options = {}) {
  const { version = 1, exclude = [], maxBytes = 512 * 1024 } = options
  const storageKey = `${key}_v${version}`
  const excludeRef = useRef(exclude)
  excludeRef.current = exclude

  const [state, setState] = useState(() => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return initialState
      const saved = JSON.parse(raw)
      if (!saved || typeof saved !== 'object') return initialState
      // 合并恢复：旧缓存缺字段时回落到 initialState 默认值
      return { ...initialState, ...saved }
    } catch {
      return initialState
    }
  })

  // 防抖持久化：连续输入只写一次
  const timer = useRef(null)
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      try {
        const payload = {}
        for (const [k, v] of Object.entries(state)) {
          if (!excludeRef.current.includes(k) && v !== undefined) payload[k] = v
        }
        const json = JSON.stringify(payload)
        if (json.length <= maxBytes) {
          localStorage.setItem(storageKey, json)
        }
      } catch {
        /* localStorage 不可用或已满：静默降级，不影响页面 */
      }
    }, 300)
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [state, storageKey, maxBytes])

  /** 清空已保存的输入态并复位初始值 */
  const clear = useCallback(() => {
    try {
      localStorage.removeItem(storageKey)
    } catch {
      /* ignore */
    }
    setState(initialState)
  }, [storageKey, initialState])

  return [state, setState, { clear }]
}
