import React, { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import Modal from './Modal'
import Button from './Button'

/**
 * 确认对话框
 * - 替代原生 confirm()
 * - 支持 danger 风格
 * - 异步确认（onConfirm 可返回 Promise，自动 loading）
 */
export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = '确认操作',
  message,
  confirmLabel = '确认',
  cancelLabel = '取消',
  variant = 'danger',
  icon: Icon = AlertTriangle,
}) {
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    try {
      setLoading(true)
      const result = await onConfirm?.()
      if (result !== false) {
        onClose?.()
      }
    } catch {
      // 错误由调用方在 onConfirm 内处理 toast
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={loading ? undefined : onClose} size="sm" closeOnBackdrop={!loading}>
      <div className="text-center">
        <div
          className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-soft ${
            variant === 'danger' ? 'bg-red-100' : 'bg-brand-50'
          }`}
        >
          <Icon className={`w-7 h-7 ${variant === 'danger' ? 'text-red-500' : 'text-brand-500'}`} />
        </div>
        <h3 className="text-lg font-semibold tracking-tight text-gray-900 mb-2">{title}</h3>
        {message && <p className="text-sm text-ink-500 mb-6">{message}</p>}
        <div className="flex items-center justify-center gap-3">
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            onClick={handleConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
