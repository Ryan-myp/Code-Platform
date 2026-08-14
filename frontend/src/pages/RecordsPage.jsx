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
import { ErrorState, Pagination } from '../components/ui'

/**
 * 统一记录中心：工具使用记录 + 分享记录。
 */
export default function RecordsPage() {
  const toast = useToast()
  const [tab, setTab] = useState('tools') // tools | shares
  const [records, setRecords] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [shareStats, setShareStats] = useState(null)
  const [shareStatsLoaded, setShareStatsLoaded] = useState(false)

  const load = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const res = await api.get('/api/records')
      setRecords(res.data)
    } catch (err) {
      setLoadError(err.message || '加载记录失败')
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

  // 分享工作台：访问 / 注册转化 / 裂变奖励（独立于 records，含去重访问与奖励状态）
  const loadShareStats = async () => {
    try {
      const res = await api.get('/api/shares/my')
      setShareStats(res.data)
    } catch {
      // 旧后端兼容：静默失败，继续用 records 里的基础分享数据
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

  if (loadError && !records) {
    return (
      <div className="max-w-4xl mx-auto">
        <ErrorState message={loadError} onRetry={load} />
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
            onClick={() => {
              setTab('shares')
              if (!shareStatsLoaded) {
                setShareStatsLoaded(true)
                loadShareStats()
              }
            }}
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
            <Pagination
              items={tools}
              pageSize={5}
              gridClass="grid grid-cols-1 gap-3"
              label={`共 ${tools.length} 条记录`}
              renderItem={(r) => (
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
              )}
            />
          )}
        </>
      )}

      {/* 分享记录 */}
      {tab === 'shares' && (
        <>
          {/* 裂变收益规则卡：访问达标得额度 + 邀请注册双方得额度 */}
          <div className="bg-gradient-to-r from-brand-50 to-purple-50 border border-brand-100/60 rounded-2xl p-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-soft flex-shrink-0">
                  <Share2 className="w-5 h-5 text-brand-600" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink-900">分享得额度 · 裂变赚奖励</p>
                  <p className="text-xs text-ink-500 mt-1 leading-relaxed">
                    分享链接被{' '}
                    <span className="font-semibold text-brand-600">
                      {shareStats?.totals?.threshold ?? 10}
                    </span>{' '}
                    位不同用户访问，可得{' '}
                    <span className="font-semibold text-brand-600">
                      {shareStats?.totals?.reward_per_share ?? 5}
                    </span>{' '}
                    次生成额度（每分享限一次）；好友用你的邀请码注册，双方各得{' '}
                    <span className="font-semibold text-brand-600">
                      {shareStats?.totals?.reward_per_invite ?? 5}
                    </span>{' '}
                    次
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4 text-center flex-shrink-0">
                <div>
                  <p className="text-lg font-bold text-ink-900">
                    {shareStats?.totals?.visits ?? 0}
                  </p>
                  <p className="text-[10px] text-ink-400">累计访问</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-ink-900">
                    {shareStats?.totals?.conversions ?? 0}
                  </p>
                  <p className="text-[10px] text-ink-400">注册转化</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-emerald-600">
                    +{shareStats?.totals?.reward_earned ?? 0}
                  </p>
                  <p className="text-[10px] text-ink-400">已得额度</p>
                </div>
              </div>
            </div>
          </div>

          {shares.length === 0 ? (
            <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-12 text-center text-ink-400">
              <Link2 className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">还没有分享内容，在工具结果区点击「分享」即可生成链接</p>
              <p className="text-xs text-ink-300 mt-2">分享得越多，访问达标后赚的额度越多</p>
            </div>
          ) : (
            <div className="space-y-3">
              {(shareStats?.shares ?? shares).map((s) => {
                const threshold = shareStats?.totals?.threshold ?? 10
                const visits = s.visits ?? 0
                return (
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
                    {/* 裂变进度：去重访问 / 阈值 → 达标发奖状态 */}
                    <div className="mt-3 pt-3 border-t border-ink-50">
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="text-ink-400">
                          去重访问 {visits} / {threshold}
                        </span>
                        {s.rewarded ? (
                          <span className="flex items-center gap-1 text-emerald-600 font-medium">
                            <Sparkles className="w-3 h-3" />
                            已获得 +{s.reward_quota || 5} 次额度
                          </span>
                        ) : (
                          <span className="text-ink-400">
                            {visits >= threshold ? '已达标，下次访问自动发奖' : '继续分享攒访问'}
                          </span>
                        )}
                      </div>
                      <div className="h-1.5 bg-ink-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            s.rewarded ? 'bg-emerald-500' : 'bg-brand-500'
                          }`}
                          style={{ width: `${Math.min(100, (visits / threshold) * 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
