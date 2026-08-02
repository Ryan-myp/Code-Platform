import React, { useEffect } from 'react'
import { X } from 'lucide-react'

/**
 * 统一 Modal 组件
 * - 自动滚动 (max-h-[90vh] overflow-y-auto)
 * - ESC 关闭
 * - 点击遮罩关闭
 * - 标题/页脚可选
 */
export default function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  closeOnBackdrop = true,
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-xl',
    lg: 'max-w-3xl',
    xl: 'max-w-5xl',
    '2xl': 'max-w-6xl',
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={closeOnBackdrop ? onClose : undefined}
      />
      <div
        className={`relative bg-white rounded-2xl shadow-lg-soft w-full ${sizes[size]} max-h-[90vh] flex flex-col animate-[modalIn_0.15s_ease-out]`}
      >
        {title && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-ink-200 flex-shrink-0">
            <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-ink-100 rounded-lg transition-colors text-ink-400 hover:text-ink-600"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}
        <div className="overflow-y-auto p-6 flex-1">{children}</div>
        {footer && (
          <div className="px-6 py-4 border-t border-ink-200 flex justify-end gap-3 flex-shrink-0">
            {footer}
          </div>
        )}
      </div>
      <style>{`@keyframes modalIn{from{transform:scale(0.96);opacity:0}to{transform:scale(1);opacity:1}}`}</style>
    </div>
  )
}
