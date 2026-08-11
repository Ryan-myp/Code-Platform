import React, { useState } from 'react'
import { Search, Globe, ExternalLink, Clock, Sparkles, FileText, Loader2, Zap, Copy, Download, RefreshCw } from 'lucide-react'
import { Card, Button, Empty, PageHeader, SkeletonList, ErrorState } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

export default function WebSearchPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  // 输入态持久化：刷新不丢搜索词/筛选条件
  const [state, setState] = usePersistentToolState(
    'web_search_input',
    { query: '', timeRange: '', domainFilter: '' },
    { version: 2 }
  )
  const query = state.query
  const setQuery = (v) => setState((s) => ({ ...s, query: v }))
  const timeRange = state.timeRange || ''
  const setTimeRange = (v) => setState((s) => ({ ...s, timeRange: v }))
  const domainFilter = state.domainFilter || ''
  const setDomainFilter = (v) => setState((s) => ({ ...s, domainFilter: v }))
  const [task, setTask] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const [loadedHistory, setLoadedHistory] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)

  const loadHistory = async () => {
    setHistoryLoading(true)
    try {
      const res = await api.get('/api/search/history')
      setHistory(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    } finally {
      setLoadedHistory(true)
      setHistoryLoading(false)
    }
  }

  const handleSearch = async (queryOverride) => {
    // queryOverride：推荐词/相关搜索点击时显式传词，避免 setState 异步导致搜旧词
    const q = (queryOverride || query).trim()
    if (!q || task) return
    setResult(null)
    setError(null)
    await submitTask(
      '/api/search/web',
      { query: q, time_range: timeRange, domain_filter: domainFilter },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setResult(data)
          setTask(null)
          loadHistory()
        },
        onError: (e) => {
          setError(e.message)
          setTask(null)
          toast.error(`搜索失败：${e.message}`)
        },
      }
    )
  }

  // 结果 → Markdown（复制/导出/分享复用）
  const buildSummaryMd = (res) => {
    if (!res) return ''
    const lines = [`# AI 搜索摘要：${query}`, '', res.summary || '', '']
    const filters = []
    if (res.time_range) filters.push(res.time_range === '24h' ? '近24小时' : res.time_range === '7d' ? '近7天' : '近30天')
    if (res.domain_filter) filters.push(`来源域: ${res.domain_filter}`)
    if (filters.length) {
      lines.push(`> 筛选条件：${filters.join(' · ')}`, '')
    }
    if (res.sources?.length) {
      lines.push('## 信息来源', '')
      res.sources.forEach((s, i) => lines.push(`${i + 1}. [${s.title}](${s.url})`))
      lines.push('')
    }
    lines.push(`> 由小团智能平台 AI 联网搜索生成 · ${new Date().toLocaleString()}`)
    return lines.join('\n')
  }

  const copySummary = async () => {
    const md = buildSummaryMd(result)
    if (!md) return
    try {
      await navigator.clipboard.writeText(md)
      toast.success('摘要已复制，可直接粘贴到文档/微信')
    } catch {
      toast.error('复制失败，请手动选择复制')
    }
  }

  const exportSummary = () => {
    const md = buildSummaryMd(result)
    if (!md) return
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `AI搜索摘要_${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('摘要已导出')
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI联网搜索"
        description="实时搜索互联网 + AI智能整合摘要，获取最新、最准确的信息"
        icon={Globe}
        iconColor="from-cyan-500 to-blue-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：搜索 + 历史 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Search className="w-4 h-4 text-cyan-500" /> 搜索全网
            </h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="搜索任何问题，如：2024年AI发展趋势..."
                className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none"
              />
              <button
                onClick={() => handleSearch()}
                disabled={!!task || !query.trim()}
                className="px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl hover:from-cyan-600 hover:to-blue-700 disabled:opacity-50 transition-all flex items-center gap-1.5"
              >
                {task ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
              </button>
            </div>
            {task && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                  <span>{task.stage || 'AI 搜索整合中…'}</span>
                  <span>{task.progress || 0}%</span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-300"
                    style={{ width: `${task.progress || 0}%` }}
                  />
                </div>
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {['AI最新进展', '2024科技趋势', 'Python最佳实践', '最新经济数据'].map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setQuery(q)
                    setTimeout(() => handleSearch(q), 50)
                  }}
                  className="px-3 py-1.5 bg-gray-50 hover:bg-cyan-50 text-xs text-gray-600 hover:text-cyan-700 rounded-lg transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>

            {/* v15：时间筛选 + 来源域过滤 */}
            <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <div className="flex rounded-lg bg-gray-100 p-0.5 text-xs">
                  {[
                    { v: '', l: '不限' },
                    { v: '24h', l: '近24h' },
                    { v: '7d', l: '近7天' },
                    { v: '30d', l: '近30天' },
                  ].map((opt) => (
                    <button
                      key={opt.v || 'all'}
                      onClick={() => setTimeRange(opt.v)}
                      className={`px-2.5 py-1 rounded-md transition-colors ${
                        timeRange === opt.v
                          ? 'bg-white shadow-sm text-cyan-600 font-medium'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      {opt.l}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-gray-400" />
                <input
                  type="text"
                  value={domainFilter}
                  onChange={(e) => setDomainFilter(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="来源域过滤，如: wikipedia.org,github.com"
                  className="flex-1 px-2.5 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none"
                />
              </div>
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 搜索历史
              {!loadedHistory && !historyLoading && (
                <button
                  onClick={loadHistory}
                  className="text-xs text-cyan-500 hover:underline ml-auto"
                >
                  加载
                </button>
              )}
            </h3>
            {historyLoading ? (
              <SkeletonList count={3} />
            ) : history.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无搜索记录</div>
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {history.slice(0, 15).map((h) => (
                  <button
                    key={h.id}
                    onClick={() => setQuery(h.query)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-cyan-50 text-sm text-gray-600 hover:text-cyan-700 transition-colors flex items-center gap-2"
                  >
                    <Search className="w-3 h-3 text-gray-400 flex-shrink-0" />
                    <span className="truncate">{h.query}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：结果 */}
        <div className="lg:col-span-2 space-y-4">
          {task ? (
            <Card>
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <Loader2 className="w-5 h-5 text-cyan-500 animate-spin" />
                <span>{task.stage || 'AI 正在搜索整合…'}</span>
                <span className="text-gray-400 ml-auto">{task.progress || 0}%</span>
              </div>
            </Card>
          ) : error ? (
            <ErrorState message={`搜索失败：${error}`} onRetry={handleSearch} />
          ) : !result ? (
            <Empty
              icon={Globe}
              title="开始搜索"
              description="输入关键词搜索互联网，AI将为你整合多源信息并生成摘要"
            />
          ) : (
            <>
              {/* AI摘要 */}
              <Card className="border-cyan-200">
                <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
                  <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-cyan-500" /> AI智能摘要
                  </h3>
                  <div className="flex items-center gap-2">
                    {result.time_range && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-50 border border-cyan-100 text-cyan-600">
                        {result.time_range === '24h' ? '近24h' : result.time_range === '7d' ? '近7天' : '近30天'}
                      </span>
                    )}
                    {result.domain_filter && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 border border-blue-100 text-blue-600">
                        仅 {result.domain_filter}
                      </span>
                    )}
                    <span className="text-xs text-gray-400">
                      {result.mode === 'web_search' ? '联网搜索' : 'AI知识库'}
                    </span>
                    <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => handleSearch()}>
                      重新搜索
                    </Button>
                    <Button variant="ghost" size="sm" icon={Copy} onClick={copySummary}>
                      复制
                    </Button>
                    <Button variant="ghost" size="sm" icon={Download} onClick={exportSummary}>
                      导出
                    </Button>
                    <ShareButton
                      content={buildSummaryMd(result)}
                      title={`AI搜索摘要：${query}`}
                      contentType="web_search"
                    />
                  </div>
                </div>
                <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {result.summary}
                </div>
              </Card>

              {/* 来源列表 */}
              {result.sources?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Globe className="w-4 h-4 text-blue-500" /> 信息来源（{result.sources.length}）
                  </h3>
                  <div className="space-y-2">
                    {result.sources.map((s, i) => (
                      <a
                        key={i}
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block p-3 rounded-lg bg-gray-50 hover:bg-blue-50 transition-colors group"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-800 group-hover:text-blue-700">
                            {s.title}
                          </span>
                          <ExternalLink className="w-3 h-3 text-gray-400 group-hover:text-blue-500 flex-shrink-0" />
                        </div>
                        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{s.snippet}</p>
                      </a>
                    ))}
                  </div>
                </Card>
              )}

              {/* 相关搜索 */}
              {result.related?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-500" /> 相关搜索
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {result.related.map((r, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setQuery(r)
                          setTimeout(() => handleSearch(r), 50)
                        }}
                        className="px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-xs text-amber-700 rounded-lg transition-colors"
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
