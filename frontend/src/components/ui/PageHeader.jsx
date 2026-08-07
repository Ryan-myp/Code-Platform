import React from 'react'

/**
 * 统一页面头部
 * - 标题 + 描述 + 右侧操作区
 */
export default function PageHeader({
  title,
  description,
  actions,
  icon: Icon,
  iconColor = 'from-brand-500 to-brand-700',
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
      <div className="flex items-start gap-3">
        {Icon && (
          <div
            className={`w-11 h-11 rounded-xl bg-gradient-to-br ${iconColor} flex items-center justify-center shadow-glow flex-shrink-0`}
          >
            <Icon className="w-6 h-6 text-white" />
          </div>
        )}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900">{title}</h1>
          {description && <p className="text-sm text-ink-500 mt-1">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  )
}
