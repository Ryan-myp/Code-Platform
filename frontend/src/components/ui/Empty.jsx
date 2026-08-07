import React from 'react'

/**
 * 空状态组件
 * - 统一的图标 + 标题 + 描述 + 操作按钮
 */
export default function Empty({
  icon: Icon,
  title = '暂无数据',
  description,
  action,
  actionLabel,
  onAction,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-16 px-4 text-center ${className}`}
    >
      {Icon && (
        <div className="w-20 h-20 rounded-2xl bg-ink-50 flex items-center justify-center mb-4">
          <Icon className="w-10 h-10 text-gray-300" />
        </div>
      )}
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      {description && <p className="text-sm text-gray-500 max-w-sm mb-6">{description}</p>}
      {(action || (actionLabel && onAction)) && (
        <div>
          {action ||
            (actionLabel && onAction && (
              <button
                onClick={onAction}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-600 to-brand-500 text-white rounded-xl hover:from-brand-700 hover:to-brand-600 shadow-soft hover:shadow-md-soft active:scale-[0.98] transition-all"
              >
                {actionLabel}
              </button>
            ))}
        </div>
      )}
    </div>
  )
}
