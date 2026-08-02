import React from 'react'
import { Loader2, RefreshCw } from 'lucide-react'

/** 全屏 spinner */
export function PageLoading({ label = '加载中…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <Loader2 className="w-8 h-8 text-purple-600 animate-spin mb-3" />
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}

/** 卡片内 spinner */
export function CardLoading({ label = '加载中…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <RefreshCw className="w-6 h-6 text-purple-500 animate-spin mb-2" />
      <p className="text-sm text-gray-400">{label}</p>
    </div>
  )
}

/** 骨架屏 - 列表 */
export function SkeletonList({ count = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-2xl border border-ink-200 p-4 animate-pulse">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-ink-100" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-ink-100 rounded w-1/3" />
              <div className="h-3 bg-ink-100 rounded w-1/2" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

/** 骨架屏 - 卡片网格 */
export function SkeletonGrid({ count = 6 }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-2xl border border-ink-200 p-5 animate-pulse">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-ink-100" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-ink-100 rounded w-2/3" />
              <div className="h-3 bg-ink-100 rounded w-1/3" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="h-3 bg-ink-100 rounded" />
            <div className="h-3 bg-ink-100 rounded w-5/6" />
          </div>
        </div>
      ))}
    </div>
  )
}

/** 错误状态 */
export function ErrorState({ message = '加载失败', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center mb-4 shadow-soft">
        <RefreshCw className="w-7 h-7 text-red-400" />
      </div>
      <p className="text-gray-600 mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-600 to-brand-500 text-white rounded-xl hover:from-brand-700 hover:to-brand-600 shadow-soft hover:shadow-md-soft active:scale-[0.98] transition-all text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          重试
        </button>
      )}
    </div>
  )
}

export default PageLoading
