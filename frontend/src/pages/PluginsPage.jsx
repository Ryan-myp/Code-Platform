import React, { useState, useEffect } from 'react'
import { 
  Puzzle, RefreshCw, Loader2, AlertCircle, Play, 
  CheckCircle, XCircle, Star, Search, Filter,
  ChevronDown
} from 'lucide-react'
import axios from 'axios'

const API = 'http://localhost:8888'

// 插件卡片组件
function PluginCard({ plugin, onExecute, isExecuting }) {
  const categoryColors = {
    'prd': 'from-blue-500 to-cyan-600',
    'code': 'from-emerald-500 to-green-600',
    'test': 'from-orange-500 to-amber-600',
    'design': 'from-purple-500 to-pink-600',
    'default': 'from-gray-500 to-gray-600'
  }
  
  const color = categoryColors[plugin.category] || categoryColors.default
  
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center`}>
            <Puzzle className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{plugin.name}</h3>
            <span className="text-xs text-gray-500">{plugin.category || '通用'}</span>
          </div>
        </div>
        {plugin.rating > 0 && (
          <div className="flex items-center gap-1">
            <Star className="w-4 h-4 text-yellow-400 fill-current" />
            <span className="text-sm font-medium">{plugin.rating}</span>
          </div>
        )}
      </div>
      
      {plugin.description && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-4">{plugin.description}</p>
      )}
      
      <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
        <button
          onClick={() => onExecute(plugin.name)}
          disabled={isExecuting}
          className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
            isExecuting 
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
              : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
          }`}
        >
          {isExecuting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {isExecuting ? '执行中...' : '测试'}
        </button>
      </div>
    </div>
  )
}

export default function PluginsPage() {
  const [plugins, setPlugins] = useState([])
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [executing, setExecuting] = useState(null)
  const [testResult, setTestResult] = useState(null)
  const [showResult, setShowResult] = useState(null)

  const fetchPlugins = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`${API}/api/plugins`)
      setPlugins(res.data.plugins || [])
      setCategories(res.data.categories || [])
      setError(null)
    } catch (err) {
      setError('获取插件列表失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPlugins()
  }, [])

  const handleExecute = async (pluginName) => {
    setExecuting(pluginName)
    setTestResult(null)
    setShowResult(null)
    
    try {
      const res = await axios.post(`${API}/api/plugins/${pluginName}/execute`, {
        input_data: { prd_text: "这是一个测试PRD，用于验证插件功能是否正常" }
      })
      setTestResult(res.data)
      setShowResult(pluginName)
    } catch (err) {
      setTestResult({ 
        status: 'failed', 
        error: err.response?.data?.detail || err.message 
      })
      setShowResult(pluginName)
    } finally {
      setExecuting(null)
    }
  }

  const filteredPlugins = selectedCategory === 'all' 
    ? plugins 
    : plugins.filter(p => p.category === selectedCategory)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">插件市场</h1>
          <p className="text-gray-500 mt-1">查看和管理所有已注册的引擎插件</p>
        </div>
        <button
          onClick={fetchPlugins}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-xl hover:bg-gray-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Category Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setSelectedCategory('all')}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            selectedCategory === 'all' 
              ? 'bg-blue-600 text-white' 
              : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
          }`}
        >
          全部 ({plugins.length})
        </button>
        {categories.map(cat => {
          const count = plugins.filter(p => p.category === cat).length
          return (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                selectedCategory === cat 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {cat} ({count})
            </button>
          )
        })}
      </div>

      {/* Loading State */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      ) : filteredPlugins.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
          <Puzzle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无插件</h3>
          <p className="text-gray-500">当前没有已注册的插件</p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {filteredPlugins.map(plugin => (
            <PluginCard
              key={plugin.name}
              plugin={plugin}
              onExecute={handleExecute}
              isExecuting={executing === plugin.name}
            />
          ))}
        </div>
      )}

      {/* Test Result Modal */}
      {showResult && testResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">测试结果: {showResult}</h2>
              <button 
                onClick={() => setShowResult(null)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6">
              {testResult.status === 'success' ? (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-4">
                  <div className="flex items-center gap-2 text-emerald-700 font-medium mb-2">
                    <CheckCircle className="w-5 h-5" />
                    执行成功
                  </div>
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono bg-white p-4 rounded-lg">
                    {JSON.stringify(testResult.output, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                  <div className="flex items-center gap-2 text-red-700 font-medium mb-2">
                    <XCircle className="w-5 h-5" />
                    执行失败
                  </div>
                  <p className="text-sm text-gray-700">{testResult.error}</p>
                </div>
              )}
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => setShowResult(null)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
