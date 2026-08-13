import React, { useState, useEffect, useRef } from 'react'
import { useI18n } from '../i18n/index.jsx'
import { Search, Clock, FileText, Folder, MessageCircle, Zap, Tag, Wrench } from 'lucide-react'
import { api } from '../lib/api'

const TYPE_ICONS = (t) => ({
  tool: { icon: Wrench, color: 'text-blue-500', label: t('search.tools') },
  template: { icon: FileText, color: 'text-purple-500', label: t('search.templates') },
  project: { icon: Folder, color: 'text-amber-500', label: t('search.projects') },
  task: { icon: Tag, color: 'text-green-500', label: t('search.tasks') },
  conversation: { icon: MessageCircle, color: 'text-cyan-500', label: '对话' },
  recent: { icon: Clock, color: 'text-gray-400', label: '最近' },
})

const TYPE_PATHS = {
  tool: (id) => {
    const map = {
      'image-factory': '/image-factory',
      'video-factory': '/video-factory',
      'music-factory': '/music-factory',
      'code-sandbox': '/code-sandbox',
      'prd-engine': '/prd-engine',
      'template-market': '/templates',
      'agents': '/agents',
      'chat': '/chat',
      'seo-analyzer': '/seo-analyzer',
      'competitor-monitor': '/competitor-monitor',
      'meme-factory': '/meme-factory',
      'pdf-tools': '/pdf-tools',
      'voice-chat': '/voice-chat',
      'data-forecast': '/data-forecast',
      'mindmap': '/mindmap',
      'short-drama': '/short-drama',
      'copywriting': '/copywriting',
      'translation': '/translation',
      'ppt-factory': '/ppt-factory',
      'excel-tools': '/excel',
    }
    return map[id] || '/'
  },
}

export default function SearchPage() {
  const { t } = useI18n()
  const icons = TYPE_ICONS(t)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(false)
  const [filter, setFilter] = useState('all')
  const inputRef = useRef(null)

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus()
  }, [])

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (!query.trim()) {
        setResults([])
        setSuggestions([])
        return
      }
      setLoading(true)
      try {
        const [searchRes, suggestRes] = await Promise.all([
          api.get('/api/search/quick', { params: { q: query, limit: 20 } }),
          api.get('/api/search/suggest', { params: { q: query, limit: 10 } }),
        ])
        let allResults = searchRes.data?.results || []
        if (filter !== 'all') {
          allResults = allResults.filter(r => r.type === filter)
        }
        setResults(allResults)
        setSuggestions(suggestRes.data?.suggestions || [])
      } catch (e) {
        console.error('Search error:', e)
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query, filter])

  const handleNavigate = (result) => {
    if (result.path) {
      window.location.href = result.path
    } else {
      const path = TYPE_PATHS[result.type]?.(result.id) || '/'
      window.location.href = path
    }
  }

  const categoryCounts = results.reduce((acc, r) => {
    acc[r.type] = (acc[r.type] || 0) + 1
    return acc
  }, {})

  return (
    <div className="max-w-3xl mx-auto space-y-4 animate-page-in">
      {/* 搜索框 */}
      <div className="relative">
        <div className="flex items-center bg-white border-2 border-purple-300 rounded-2xl px-4 py-3 shadow-lg focus-within:border-purple-500 transition-colors">
          <Search className="w-5 h-5 text-gray-400 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActive(true) }}
            onFocus={() => setActive(true)}
            placeholder="搜索工具、模板、项目、任务..."
            className="flex-1 ml-3 bg-transparent outline-none text-lg"
          />
          {loading && (
            <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          )}
        </div>

        {/* 分类筛选 */}
        {active && (
          <div className="mt-3 flex flex-wrap gap-2">
            {[
              { key: 'all', label: t('common.all'), count: results.length },
              { key: 'tool', label: t('search.tools'), icon: Tool },
              { key: 'template', label: t('search.templates'), icon: FileText },
              { key: 'project', label: t('search.projects'), icon: Folder },
              { key: 'task', label: t('search.tasks'), icon: Tag },
              { key: 'conversation', label: '对话', icon: MessageCircle },
            ].map(cat => (
              <button
                key={cat.key}
                onClick={() => setFilter(cat.key)}
                className={`px-3 py-1.5 rounded-full text-sm flex items-center gap-1.5 transition-all ${
                  filter === cat.key
                    ? 'bg-purple-600 text-white shadow-md'
                    : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                {cat.icon && <cat.icon className="w-3.5 h-3.5" />}
                {cat.label}
                {categoryCounts[cat.key] > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                    filter === cat.key ? 'bg-white/20' : 'bg-gray-100'
                  }`}>{categoryCounts[cat.key]}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 搜索结果 */}
      {active && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          {results.length === 0 ? (
            <div className="p-8 text-center">
              <Search className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">没有找到匹配的结果</p>
              <p className="text-sm text-gray-400 mt-1">试试其他关键词或浏览工具列表</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {results.map((result, i) => {
                const typeInfo = icons[result.type] || icons.recent
                const Icon = typeInfo.icon
                return (
                  <button
                    key={i}
                    onClick={() => handleNavigate(result)}
                    className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-purple-50 transition-colors text-left"
                  >
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${typeInfo.color.replace('text-', 'bg-').replace('500', '100')}`}>
                      <Icon className={`w-5 h-5 ${typeInfo.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">{result.name}</p>
                      {result.description && (
                        <p className="text-sm text-gray-500 truncate">{result.description}</p>
                      )}
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${typeInfo.color.replace('text-', 'bg-').replace('500', '50')}`}>
                          {typeInfo.label}
                        </span>
                        {result.created_at && (
                          <span className="text-xs text-gray-400">
                            {new Date(result.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <Zap className="w-4 h-4 text-gray-300 flex-shrink-0" />
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* 热门搜索建议 */}
      {suggestions.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <p className="text-sm text-gray-500 mb-2">💡 热门搜索</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => { setQuery(s) }}
                className="px-3 py-1 bg-gray-100 hover:bg-purple-100 text-gray-600 hover:text-purple-700 rounded-full text-sm transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 快捷入口 */}
      {!query && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { name: '图片工厂', path: '/image-factory', icon: '🎨', color: 'from-pink-500 to-rose-500' },
            { name: '视频工厂', path: '/video-factory', icon: '🎬', color: 'from-blue-500 to-cyan-500' },
            { name: '模板市场', path: '/templates', icon: '📋', color: 'from-purple-500 to-violet-500' },
            { name: '智能体', path: '/agents', icon: '🤖', color: 'from-emerald-500 to-teal-500' },
          ].map(item => (
            <a
              key={item.name}
              href={item.path}
              className={`bg-gradient-to-br ${item.color} rounded-2xl p-4 text-white hover:shadow-lg transition-all hover:-translate-y-0.5`}
            >
              <span className="text-2xl">{item.icon}</span>
              <p className="font-medium mt-2">{item.name}</p>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
