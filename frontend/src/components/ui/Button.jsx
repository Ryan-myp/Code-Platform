import React from 'react'
import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary:
    'bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-700 hover:to-brand-600 text-white shadow-soft hover:shadow-md-soft active:scale-[0.98]',
  secondary:
    'bg-white hover:bg-ink-50 text-ink-700 border border-ink-200 shadow-soft hover:shadow-md-soft active:scale-[0.98]',
  success:
    'bg-emerald-500 hover:bg-emerald-600 text-white shadow-soft hover:shadow-md-soft active:scale-[0.98]',
  danger:
    'bg-red-500 hover:bg-red-600 text-white shadow-soft hover:shadow-md-soft active:scale-[0.98]',
  ghost: 'hover:bg-ink-100 text-ink-700 active:scale-[0.98]',
  gradient:
    'bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-700 hover:to-brand-600 text-white shadow-soft hover:shadow-md-soft active:scale-[0.98]',
}

const SIZES = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
}

/**
 * 统一按钮组件
 * - loading 状态自动禁用并显示 spinner
 * - 支持图标
 */
export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon: Icon,
  iconPosition = 'left',
  className = '',
  ...props
}) {
  const isDisabled = disabled || loading
  const content = (
    <>
      {Icon && iconPosition === 'left' && (
        <Icon className={`w-4 h-4 ${children ? 'mr-1.5' : ''}`} />
      )}
      {children}
      {Icon && iconPosition === 'right' && (
        <Icon className={`w-4 h-4 ${children ? 'ml-1.5' : ''}`} />
      )}
    </>
  )

  if (loading) {
    return (
      <button
        disabled
        className={`inline-flex items-center justify-center rounded-xl font-medium transition-all cursor-not-allowed opacity-60 ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
        {...props}
      >
        <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
        {children || '处理中'}
      </button>
    )
  }

  return (
    <button
      disabled={isDisabled}
      className={`inline-flex items-center justify-center rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {content}
    </button>
  )
}
