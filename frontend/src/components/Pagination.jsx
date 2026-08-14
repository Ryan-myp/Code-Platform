import React, { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

/**
 * 通用分页组件（前端切片分页）
 *
 * 解决生成内容（图片/视频/音乐/游戏等）列表无分页、内容多时
 * 一次性渲染全部导致卡顿的问题。
 *
 * 用法：
 *   <Pagination items={allItems} pageSize={12} renderItem={(item, idx) => <.../>}
 *              emptyComponent={<Empty .../>} />
 *
 * @param {Array} items             全部数据（可传入已过滤后的列表）
 * @param {number} pageSize         每页条数（默认 12）
 * @param {Function} renderItem     渲染单项（接收 item, index）
 * @param {ReactNode} emptyComponent 空状态（可选，默认简单提示）
 * @param {string} [label]          统计标签（如 "共 56 个视频"）
 */
export default function Pagination({
  items = [],
  pageSize = 12,
  renderItem,
  emptyComponent,
  label,
  className = '',
  gridClass = '',
  onPageChange,
}) {
  const [page, setPage] = useState(1)
  const total = items.length
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // 数据变化时修正页码（如过滤后页数变少）
  useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  // 页码变化回调（用于"当前页全选"等场景）
  useEffect(() => {
    onPageChange?.(page)
  }, [page, onPageChange])

  const currentPageItems = items.slice((page - 1) * pageSize, page * pageSize)

  if (total === 0) {
    return emptyComponent || (
      <div className="py-12 text-center text-sm text-gray-400">暂无数据</div>
    )
  }

  const start = (page - 1) * pageSize
  // 默认网格 1 列（每项自带宽度），无 gridClass 时用基础网格
  const grid = gridClass || 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'

  return (
    <div className={className}>
      {/* 数据网格 */}
      <div className={grid}>
        {currentPageItems.map((item, idx) => (
          <div key={idx}>{renderItem(item, start + idx)}</div>
        ))}
      </div>

      {/* 分页导航 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 px-1">
          <span className="text-xs text-gray-400">
            {label || `共 ${total} 条`} · 第 {page}/{totalPages} 页
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="上一页"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            {/* 页码（最多显示 7 个，带省略） */}
            {buildPages(page, totalPages).map((p, i) =>
              p === '...' ? (
                <span key={`e${i}`} className="px-1 text-gray-400 text-xs">…</span>
              ) : (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`min-w-8 h-8 px-2 rounded-lg text-xs font-medium transition-colors ${
                    p === page
                      ? 'bg-brand-500 text-white'
                      : 'border border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {p}
                </button>
              )
            )}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="下一页"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/** 生成页码列表（带省略号） */
function buildPages(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = new Set([1, total, current - 1, current, current + 1])
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b)
  const result = []
  let prev = 0
  for (const p of sorted) {
    if (p - prev > 1) result.push('...')
    result.push(p)
    prev = p
  }
  return result
}
