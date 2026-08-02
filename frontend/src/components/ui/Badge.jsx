import React from 'react'
import { getStatusMeta } from '../../lib/format'

/**
 * 状态徽章组件
 * - 传入 status 自动匹配颜色与文案
 * - 支持自定义映射 customMap
 * - 支持自定义文本 dot
 */
export default function Badge({ status, customMap, label, dot = false, className = '' }) {
  const meta = getStatusMeta(status, customMap)
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${meta.cls} ${className}`}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />}
      {label || meta.text}
    </span>
  )
}

/** 静态颜色徽章 */
export function ColorBadge({ color = 'gray', children, className = '' }) {
  const colors = {
    gray: 'bg-gray-100 text-gray-600',
    blue: 'bg-blue-100 text-blue-700',
    green: 'bg-emerald-100 text-emerald-700',
    red: 'bg-red-100 text-red-700',
    yellow: 'bg-amber-100 text-amber-700',
    purple: 'bg-purple-100 text-purple-700',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[color] || colors.gray} ${className}`}>
      {children}
    </span>
  )
}
