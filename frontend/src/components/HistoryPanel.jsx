import React, { useState } from 'react'
import { History, Trash2, RotateCcw, ChevronDown, Clock } from 'lucide-react'

/**
 * 工具历史面板（专业基线通用组件）
 *
 * 展示历史记录列表，支持一键复用 / 删除 / 清空。配合 useToolHistory 使用：
 *   const { history, add, remove, clear } = useToolHistory('key_v1')
 *   <HistoryPanel history={history} onReuse={...} onRemove={remove} onClear={clear} renderSummary={...} />
 *
 * @param {Array} history        记录数组（每项含 ts 时间戳）
 * @param {Function} onReuse     点击复用回调（参数：记录对象, 索引）
 * @param {Function} onRemove    删除单条（参数：索引）
 * @param {Function} onClear     清空全部
 * @param {Function} [renderSummary] 自定义摘要渲染（默认截取 content 前 60 字）
 * @param {string} [title]       面板标题（默认"历史记录"）
 */
export default function HistoryPanel({
  history = [],
  onReuse,
  onRemove,
  onClear,
  renderSummary,
  title = '历史记录',
}) {
  const [open, setOpen] = useState(history.length > 0)

  const fmt = (iso) => {
    try {
      return new Date(iso).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return ''
    }
  }

  return (
    <div className="rounded-xl border border-gray-100 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-2.5 bg-gray-50 flex items-center justify-between text-xs text-gray-500 hover:text-gray-700 transition-colors"
      >
        <span className="flex items-center gap-1.5 font-medium">
          <History className="w-3.5 h-3.5" />
          {title}（{history.length}）
        </span>
        <span className="flex items-center gap-2">
          {history.length > 0 && (
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation()
                if (window.confirm(`确定清空全部 ${history.length} 条${title}吗？`)) onClear?.()
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation()
                  if (window.confirm(`确定清空全部 ${history.length} 条${title}吗？`)) onClear?.()
                }
              }}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded text-red-500 hover:bg-red-50 transition-colors"
              title="清空全部"
            >
              <Trash2 className="w-3 h-3" />
              清空
            </span>
          )}
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>

      {open && (
        <div className="divide-y divide-gray-50 max-h-64 overflow-y-auto bg-white">
          {history.length === 0 ? (
            <p className="px-4 py-6 text-center text-xs text-gray-400">
              暂无记录，完成一次生成后会自动保存
            </p>
          ) : (
            history.map((item, i) => (
              <div
                key={i}
                className="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50/60 transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  {item.title ? (
                    <p className="text-xs font-medium text-gray-700 truncate">{item.title}</p>
                  ) : null}
                  <p className="text-[11px] text-gray-400 truncate">
                    {renderSummary
                      ? renderSummary(item)
                      : (item.content || item.question || item.query || '').slice(0, 60) || '—'}
                  </p>
                  <p className="text-[10px] text-gray-300 flex items-center gap-1 mt-0.5">
                    <Clock className="w-2.5 h-2.5" /> {fmt(item.ts)}
                  </p>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {onReuse && (
                    <button
                      onClick={() => onReuse(item, i)}
                      className="p-1.5 rounded-lg text-brand-600 hover:bg-brand-50 transition-colors"
                      title="复用此记录"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {onRemove && (
                    <button
                      onClick={() => onRemove(i)}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="删除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
