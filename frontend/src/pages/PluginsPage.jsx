import React, { useState, useEffect, useCallback } from 'react'
import {
  Puzzle, RefreshCw, Play, Star, Search,
  CheckCircle, XCircle, Power,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import MarkdownRenderer from '../components/MarkdownRenderer'
import {
  Modal, Button, Empty, SkeletonGrid, ErrorState,
  Badge, PageHeader,
} from '../components/ui'

const CATEGORY_COLORS = {
  prd: 'from-blue-500 to-cyan-600',
  code: 'from-emerald-500 to-green-600',
  test: 'from-orange-500 to-amber-600',
  design: 'from-purple-500 to-pink-600',
  default: 'from-gray-500 to-gray-600',
}

function PluginCard({ plugin, enabled, onExecute, onToggle, isExecuting }) {
  const color = CATEGORY_COLORS[plugin.category] || CATEGORY_COLORS.default
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center flex-shrink-0`}>
            <Puzzle className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{plugin.name}</h3>
            <span className="text-xs text-gray-500">{plugin.category || '通用'}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {plugin.rating > 0 && (
            <span className="flex items-center gap-1">
              <Star className="w-4 h-4 text-yellow-400 fill-current" />
              <span className="text-sm font-medium">{plugin.rating}</span>
            </span>
          )}
          <Badge status={enabled ? 'enabled' : 'disabled'} dot />
        </div>
      </div>

      {plugin.description && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-4 flex-1">{plugin.description}</p>
      )}

      <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
        <Button
          variant={enabled ? 'success' : 'secondary'}
          size="sm"
          icon={Play}
          loading={isExecuting}
          disabled={!enabled}
          onClick={() => onExecute(plugin.name)}
          className="flex-1"
        >
          {isExecuting ? '执行中' : '测试执行'}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          icon={Power}
          onClick={() => onToggle(plugin.name)}
          title={enabled ? '禁用' : '启用'}
        >
          {enabled ? '禁用' : '启用'}
        </Button>
      </div>
    </div>
  )
}

export default function PluginsPage() {
  const toast = useToast()
  const [plugins, setPlugins] = useState([])
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [executing, setExecuting] = useState(null)
  const [testResult, setTestResult] = useState(null)
  const [showResult, setShowResult] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [enabledMap, setEnabledMap] = useState({})

  const fetchPlugins = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/plugins')
      const list = res.data.plugins || []
      setPlugins(list)
      setCategories(res.data.categories || [])
      // 默认全部启用
      setEnabledMap((prev) => {
        const next = { ...prev }
        list.forEach((p) => {
          if (next[p.name] === undefined) next[p.name] = true
        })
        return next
      })
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchPlugins() }, [fetchPlugins])

  const handleExecute = async (pluginName) => {
    setExecuting(pluginName)
    setTestResult(null)
    setShowResult(null)
    try {
      const res = await api.post(`/api/plugins/${pluginName}/execute`, {
        input_data: { prd_text: '这是一个测试 PRD，用于验证插件功能是否正常' },
      })
      // 后端返回 {status, result}
      setTestResult({ status: 'success', output: res.data.result, raw: res.data })
      setShowResult(pluginName)
      toast.success(`插件「${pluginName}」执行成功`)
    } catch (e) {
      setTestResult({ status: 'failed', error: e.message })
      setShowResult(pluginName)
      toast.error(`插件「${pluginName}」执行失败：${e.message}`)
    } finally {
      setExecuting(null)
    }
  }

  const handleToggle = (pluginName) => {
    setEnabledMap((prev) => {
      const next = !prev[pluginName]
      toast[next ? 'success' : 'info'](`插件「${pluginName}」已${next ? '启用' : '禁用'}`)
      return { ...prev, [pluginName]: next }
    })
  }

  const filteredPlugins = plugins.filter((p) => {
    const matchCat = selectedCategory === 'all' || p.category === selectedCategory
    const q = searchTerm.toLowerCase()
    const matchSearch = !q || p.name?.toLowerCase().includes(q) || p.description?.toLowerCase().includes(q)
    return matchCat && matchSearch
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="插件市场"
        description="查看和管理所有已注册的引擎插件，支持测试执行与启停"
        icon={Puzzle}
        iconColor="from-blue-500 to-indigo-600"
        actions={
          <Button variant="secondary" icon={RefreshCw} onClick={fetchPlugins}>刷新</Button>
        }
      />

      {/* 搜索 + 分类筛选 */}
      <div className="flex flex-col lg:flex-row gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="搜索插件名称或描述…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-sm"
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${selectedCategory === 'all' ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'}`}
          >
            全部 ({plugins.length})
          </button>
          {categories.map((cat) => {
            const count = plugins.filter((p) => p.category === cat).length
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${selectedCategory === cat ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'}`}
              >
                {cat} ({count})
              </button>
            )
          })}
        </div>
      </div>

      {/* 内容 */}
      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`获取插件列表失败：${error.message}`} onRetry={fetchPlugins} />
      ) : filteredPlugins.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Puzzle}
            title={searchTerm || selectedCategory !== 'all' ? '未找到匹配的插件' : '暂无插件'}
            description={searchTerm || selectedCategory !== 'all' ? '尝试调整搜索或筛选条件' : '当前没有已注册的插件'}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPlugins.map((plugin) => (
            <PluginCard
              key={plugin.name}
              plugin={plugin}
              enabled={enabledMap[plugin.name] !== false}
              onExecute={handleExecute}
              onToggle={handleToggle}
              isExecuting={executing === plugin.name}
            />
          ))}
        </div>
      )}

      {/* 测试结果 Modal */}
      <Modal
        open={!!showResult}
        onClose={() => setShowResult(null)}
        title={showResult ? `测试结果：${showResult}` : ''}
        size="lg"
        footer={<Button variant="primary" onClick={() => setShowResult(null)}>关闭</Button>}
      >
        {testResult && (
          testResult.status === 'success' ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
              <div className="flex items-center gap-2 text-emerald-700 font-medium mb-3">
                <CheckCircle className="w-5 h-5" />
                执行成功
              </div>
              <div className="bg-white p-4 rounded-lg border max-h-[55vh] overflow-auto">
                <MarkdownRenderer
                  content={(() => {
                    const out = testResult.output
                    return typeof out === 'string' ? out : JSON.stringify(out, null, 2)
                  })()}
                />
              </div>
            </div>
          ) : (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="flex items-center gap-2 text-red-700 font-medium mb-2">
                <XCircle className="w-5 h-5" />
                执行失败
              </div>
              <p className="text-sm text-gray-700 break-all">{testResult.error}</p>
            </div>
          )
        )}
      </Modal>
    </div>
  )
}
