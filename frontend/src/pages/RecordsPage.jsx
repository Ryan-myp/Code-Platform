import React, { useEffect, useState } from 'react'
import {
  Calendar,
  ChevronDown,
  Clock,
  Copy,
  Eye,
  FileText,
  History,
  Link2,
  Loader2,
  Share2,
  Sparkles,
  Wrench,
} from 'lucide-react'
import api from '../lib/api'
import { useToast } from '../lib/toast'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ShareButton from '../components/ShareButton'
import ExportButton from '../components/ExportButton'

/**
 * 统一记录中心：工具使用记录 + 分享记录。
 */
export default function RecordsPage() {
  const toast = useToast()
  const [tab, setTab] = useState('tools') // tools | shares
  const [records, setRecords] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/records')
      setRecords(res.data)
    } catch (err) {
      toast.error(err.message || '加载记录失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const copyShareLink = async (code) => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/share/${code}`)
      toast.success('分享链接已复制')
    } catch {
      toast.error('复制失败')
    }
  }

  if (loading && !records) {
    return (
      <div className="flex items-center justify-center h-64 text-ink-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        加载记录…
      </div>
    )
  }

  const tools = records?.tools || []
  const shares = records?.shares || []

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-page-in">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink-900 flex items-center gap-2">
            <History className="w-5 h-5 text-brand-600" />
            记录中心
          </h1>
          <p className="text-sm text-ink-500">你的工具使用记录与分享内容，统一管理</p>
        </div>
        <div className="flex items-center gap-1 p-1 bg-ink-100/70 rounded-xl">
          <button
            onClick={() => setTab('tools')}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg transition-all ${
              tab === 'tools'
                ? 'bg-white shadow-soft text-brand-600 font-medium'
                : 'text-ink-500 hover:text-ink-700'
            }`}
          >
            <Wrench className="w-4 h-4" />
            工具记录
            <span className="text-xs text-ink-400">({tools.length})</span>
          </button>
          <button
            onClick={() => setTab('shares')}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg transition-all ${
              tab === 'shares'
                ? 'bg-white shadow-soft text-brand-600 font-medium'
                : 'text-ink-500 hover:text-ink-700'
            }`}
          >
            <Share2 className="w-4 h-4" />
            分享记录
            <span className="text-xs text-ink-400">({shares.length})</span>
          </button>
        </div>
      </div>

      {/* 工具记录 */}
      {tab === 'tools' && (
        <>
          {tools.length === 0 ? (
            <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-12 text-center text-ink-400">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">还没有工具使用记录，去「效率工具箱」试试吧</p>
            </div>
          ) : (
            <div className="space-y-3">
              {tools.map((r) => (
                <div
                  key={r.id}
                  className="bg-white rounded-2xl border border-ink-200/60 shadow-soft overflow-hidden"
                >
                  <button
                    onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                    className="w-full flex items-center gap-3 px-5 py-4 hover:bg-ink-50/50 transition-colors text-left"
                  >
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-ink-800 truncate">{r.tool_name}</p>
                      <p className="text-xs text-ink-400 truncate mt-0.5">
                        {r.input_text || '（无输入内容）'}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      {r.model && (
                        <span className="hidden md:inline px-2 py-0.5 text-[10px] rounded-full bg-ink-100 text-ink-500 font-mono">
                          {r.model}
                        </span>
                      )}
                      <span className="text-xs text-ink-400 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {r.created_at?.slice(5, 16)}
                      </span>
                      <ChevronDown
                        className={`w-4 h-4 text-ink-400 transition-transform ${expanded === r.id ? 'rotate-180' : ''}`}
                      />
                    </div>
                  </button>
                  {expanded === r.id && (
                    <div className="px-5 pb-5 border-t border-ink-100">
                      <div className="flex items-center justify-between pt-4 pb-2">
                        <span className="text-xs text-ink-400">生成结果</span>
                        <div className="flex items-center gap-1">
                          <ShareButton content={r.result} title={`${r.tool_name} 生成结果`} />
                          <ExportButton
                            content={r.result}
                            title={`${r.tool_name}-${r.created_at?.slice(0, 10)}`}
                          />
                        </div>
                      </div>
                      <div className="max-h-96 overflow-y-auto rounded-xl bg-ink-50/50 p-4">
                        <MarkdownRenderer content={r.result} />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* 分享记录 */}
      {tab === 'shares' && (
        <>
          {shares.length === 0 ? (
            <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-12 text-center text-ink-400">
              <Link2 className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">还没有分享内容，在工具结果区点击「分享」即可生成链接</p>
            </div>
          ) : (
            <div className="space-y-3">
              {shares.map((s) => (
                <div
                  key={s.id}
                  className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink-800 truncate">
                        {s.title || '分享内容'}
                      </p>
                      <div className="flex items-center gap-4 mt-1.5 text-xs text-ink-400">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {s.created_at?.slice(0, 10)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Eye className="w-3 h-3" />
                          {s.views} 次浏览
                        </span>
                        <span className="px-2 py-0.5 bg-ink-100 text-ink-500 rounded-full">
                          {s.content_type}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => copyShareLink(s.share_code)}
                        className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg text-ink-500 hover:text-brand-600 hover:bg-gray-100 transition-colors"
                        title="复制分享链接"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        复制链接
                      </button>
                      <a
                        href={`/share/${s.share_code}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg text-ink-500 hover:text-brand-600 hover:bg-gray-100 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        查看
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
