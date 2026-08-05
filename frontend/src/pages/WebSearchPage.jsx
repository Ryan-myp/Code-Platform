import React, { useState } from 'react'
import { Search, Globe, ExternalLink, Clock, Sparkles, FileText, Loader2, Zap } from 'lucide-react'
import { Card, Button, Empty, PageHeader, SkeletonList, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

export default function WebSearchPage() {
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const [loadedHistory, setLoadedHistory] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)

  const loadHistory = async () => {
    setHistoryLoading(true)
    try { const res = await api.get('/api/search/history'); setHistory(res.data || []) } catch {/* 静默失败，不阻塞 UI */}
    finally { setLoadedHistory(true); setHistoryLoading(false) }
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true); setResult(null); setError(null)
    try {
      const res = await api.post('/api/search/web', { query: query.trim() })
      setResult(res.data)
      loadHistory()
    } catch (e) { setError(e.message); toast.error(`搜索失败：${e.message}`) }
    setLoading(false)
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
                onClick={handleSearch}
                disabled={loading || !query.trim()}
                className="px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl hover:from-cyan-600 hover:to-blue-700 disabled:opacity-50 transition-all flex items-center gap-1.5"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {['AI最新进展', '2024科技趋势', 'Python最佳实践', '最新经济数据'].map((q) => (
                <button key={q} onClick={() => { setQuery(q); setTimeout(() => handleSearch, 50) }}
                  className="px-3 py-1.5 bg-gray-50 hover:bg-cyan-50 text-xs text-gray-600 hover:text-cyan-700 rounded-lg transition-colors">
                  {q}
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 搜索历史
              {!loadedHistory && !historyLoading && <button onClick={loadHistory} className="text-xs text-cyan-500 hover:underline ml-auto">加载</button>}
            </h3>
            {historyLoading ? (
              <SkeletonList count={3} />
            ) : history.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无搜索记录</div>
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {history.slice(0, 15).map((h) => (
                  <button key={h.id} onClick={() => setQuery(h.query)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-cyan-50 text-sm text-gray-600 hover:text-cyan-700 transition-colors flex items-center gap-2">
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
          {loading ? (
            <Card>
              <SkeletonList count={4} />
            </Card>
          ) : error ? (
            <ErrorState message={`搜索失败：${error}`} onRetry={handleSearch} />
          ) : !result ? (
            <Empty icon={Globe} title="开始搜索" description="输入关键词搜索互联网，AI将为你整合多源信息并生成摘要" />
          ) : (
            <>
              {/* AI摘要 */}
              <Card className="border-cyan-200">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-cyan-500" /> AI智能摘要
                  </h3>
                  <span className="text-xs text-gray-400">{result.mode === 'web_search' ? '联网搜索' : 'AI知识库'}</span>
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
                      <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                        className="block p-3 rounded-lg bg-gray-50 hover:bg-blue-50 transition-colors group">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-800 group-hover:text-blue-700">{s.title}</span>
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
                      <button key={i} onClick={() => { setQuery(r); setTimeout(() => handleSearch, 50) }}
                        className="px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-xs text-amber-700 rounded-lg transition-colors">
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
