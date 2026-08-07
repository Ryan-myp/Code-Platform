/* eslint-disable react-refresh/only-export-components -- toast 工具库：导出 Hook 与组件 */
import React, { createContext, useContext, useState, useCallback, useRef } from 'react'
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

const ICONS = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
}

const STYLES = {
  success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
}

const ICON_COLORS = {
  success: 'text-emerald-500',
  error: 'text-red-500',
  warning: 'text-amber-500',
  info: 'text-blue-500',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const remove = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback((type, message, duration = 3500) => {
    const id = ++idRef.current
    setToasts((prev) => [...prev, { id, type, message }])
    if (duration > 0) {
      setTimeout(() => remove(id), duration)
    }
    return id
  }, [remove])

  const toast = {
    success: (msg, d) => push('success', msg, d),
    error: (msg, d) => push('error', msg, d ?? 5000),
    warning: (msg, d) => push('warning', msg, d),
    info: (msg, d) => push('info', msg, d),
    remove,
  }

  const toastValue = React.useMemo(() => toast, [push, remove])

  return (
    <ToastContext.Provider value={toastValue}>
      {children}
      {/* Toast 容器 */}
      <div className="fixed top-4 right-4 z-[9999] space-y-2 pointer-events-none">
        {toasts.map((t) => {
          const Icon = ICONS[t.type] || Info
          return (
            <div
              key={t.id}
              className={`flex items-start gap-3 min-w-[280px] max-w-md px-4 py-3 rounded-xl border shadow-lg pointer-events-auto animate-[slideIn_0.2s_ease-out] ${STYLES[t.type]}`}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${ICON_COLORS[t.type]}`} />
              <p className="flex-1 text-sm leading-relaxed">{t.message}</p>
              <button
                onClick={() => remove(t.id)}
                className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )
        })}
      </div>
      <style>{`@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}`}</style>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    // 降级：无 Provider 时返回 noop，避免崩溃
    return { success: () => {}, error: () => {}, warning: () => {}, info: () => {}, remove: () => {} }
  }
  return ctx
}

export default ToastProvider
