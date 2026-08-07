import React from 'react'
import { getStatusMeta } from '../../lib/format'

/**
 * 状态徽章组件
 * - 用法一（状态自动映射）：<Badge status="running" /> / <Badge status="done" label="已完成" />
 * - 用法二（指定颜色 + 内容）：<Badge color="blue">文本</Badge> / <Badge color="green" dot>运行中</Badge>
 * - 支持自定义映射 customMap
 */
export default function Badge({
  status,
  color,
  customMap,
  label,
  dot = false,
  children,
  className = '',
}) {
  const meta = color
    ? { text: children ?? label ?? '', cls: COLOR_CLS[color] || COLOR_CLS.gray }
    : getStatusMeta(status, customMap)
  const content = children ?? label ?? meta.text
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${meta.cls} ${className}`}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />}
      {content}
    </span>
  )
}

/** 静态颜色徽章 */
export function ColorBadge({ color = 'gray', children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${COLOR_CLS[color] || COLOR_CLS.gray} ${className}`}
    >
      {children}
    </span>
  )
}

const COLOR_CLS = {
  gray: 'bg-gray-100 text-gray-600',
  blue: 'bg-blue-100 text-blue-700',
  green: 'bg-emerald-100 text-emerald-700',
  red: 'bg-red-100 text-red-700',
  yellow: 'bg-amber-100 text-amber-700',
  purple: 'bg-purple-100 text-purple-700',
  amber: 'bg-amber-100 text-amber-700',
  orange: 'bg-orange-100 text-orange-700',
  cyan: 'bg-cyan-100 text-cyan-700',
  pink: 'bg-pink-100 text-pink-700',
  brand: 'bg-brand-100 text-brand-700',
}
