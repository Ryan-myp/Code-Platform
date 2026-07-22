import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Brain, TrendingUp, Zap, AlertCircle, RefreshCw, CheckCircle, Lightbulb, Code, FileText, Settings } from 'lucide-react'

export default function PlatformEvolutionPage() {
  const [stats, setStats] = useState(null)
  const [optimizations, setOptimizations] = useState([])
  const [promptHistory, setPromptHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const [activeTab, setActiveTab] = useState('stats') // stats, optimizations, prompts

  // 加载统计数据
  const loadStats = async () => {
    try {
      const res = await axios.get('/api/platform/usage-stats')
      setStats(res.data)
    } catch (err) {
      console.error('Failed to load stats:', err)
    }
  }

  // 加载优化建议
  const loadOptimizations = async () => {
    try {
      const res = await axios.get('/api/platform/prompt-history')
      setPromptHistory(res.data.prompts)
    } catch (err) {
      console.error('Failed to load optimizations:', err)
    }
  }

  // 触发平台优化
  const triggerOptimization = async (target = 'all') => {
    setOptimizing(true)
    try {
      const res = await axios.post('/api/platform/optimize', { target })
      setOptimizations(res.data.optimizations)
      alert(res.data.message)
      // 刷新数据
      loadStats()
      loadOptimizations()
    } catch (err) {
      console.error('Optimization failed:', err)
      alert('优化失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setOptimizing(false)
    }
  }

  useEffect(() => {
    loadStats()
    loadOptimizations()
  }, [])

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-purple-600 to-indigo-700 rounded-2xl shadow-lg mb-6">
            <Brain className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight mb-3">平台自进化</h1>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">
            基于使用数据自动优化 PRD、技术方案、代码生成的 Prompt 和模板
          </p>
        </div>

        {/* Tabs */}
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-xl mb-8 max-w-md mx-auto">
          {[
            { key: 'stats', label: '使用统计', icon: TrendingUp },
            { key: 'optimizations', label: '优化建议', icon: Zap },
            { key: 'prompts', label: 'Prompt 历史', icon: Settings },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? 'bg-white text-purple-700 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <tab.icon className="w-4 h-4 mr-2" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Stats Tab */}
        {activeTab === 'stats' && (
          <div className="space-y-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-500">总请求数</h3>
                  <TrendingUp className="w-5 h-5 text-purple-600" />
                </div>
                <p className="text-3xl font-bold text-gray-900">{stats?.total_requests || 0}</p>
              </div>

              <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-500">平均响应时间</h3>
                  <Zap className="w-5 h-5 text-yellow-600" />
                </div>
                <p className="text-3xl font-bold text-gray-900">{stats?.avg_response_time || 0}s</p>
              </div>

              <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-500">错误率</h3>
                  <AlertCircle className="w-5 h-5 text-red-600" />
                </div>
                <p className="text-3xl font-bold text-gray-900">{stats?.error_rate || 0}%</p>
              </div>

              <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-gray-500">Prompt 版本</h3>
                  <Lightbulb className="w-5 h-5 text-blue-600" />
                </div>
                <p className="text-3xl font-bold text-gray-900">{promptHistory.length}</p>
              </div>
            </div>

            {/* Task Type Distribution */}
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                  <Code className="w-5 h-5 text-purple-600 mr-2" />
                  按任务类型分布
                </h2>
              </div>
              <div className="p-6">
                {stats?.by_task_type && Object.entries(stats.by_task_type).map(([type, count]) => (
                  <div key={type} className="mb-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700 capitalize">{type}</span>
                      <span className="text-sm text-gray-500">{count} 次</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-purple-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${(count / stats.total_requests) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Daily Usage */}
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                  <FileText className="w-5 h-5 text-green-600 mr-2" />
                  每日使用情况
                </h2>
              </div>
              <div className="p-6">
                {stats?.by_date && Object.entries(stats.by_date).map(([date, count]) => (
                  <div key={date} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                    <span className="text-sm text-gray-700">{date}</span>
                    <span className="text-sm font-medium text-purple-600">{count} 次</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Trigger Optimization Button */}
            <div className="flex justify-center">
              <button
                onClick={() => triggerOptimization('all')}
                disabled={optimizing || stats?.total_requests < 5}
                className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-4 px-8 rounded-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-bold transition-all duration-200 flex items-center shadow-lg hover:shadow-xl"
              >
                {optimizing ? (
                  <>
                    <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                    优化中...
                  </>
                ) : (
                  <>
                    <Lightbulb className="w-5 h-5 mr-2" />
                    触发全面优化
                  </>
                )}
              </button>
            </div>
            {stats?.total_requests < 5 && (
              <p className="text-center text-sm text-gray-500">
                需要至少 5 次使用记录才能触发优化（当前：{stats?.total_requests || 0} 次）
              </p>
            )}
          </div>
        )}

        {/* Optimizations Tab */}
        {activeTab === 'optimizations' && (
          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                  <Zap className="w-5 h-5 text-yellow-600 mr-2" />
                  最新优化建议
                </h2>
                <button
                  onClick={() => triggerOptimization('all')}
                  disabled={optimizing}
                  className="text-sm text-purple-600 hover:text-purple-700 font-medium flex items-center"
                >
                  <RefreshCw className={`w-4 h-4 mr-1 ${optimizing ? 'animate-spin' : ''}`} />
                  刷新
                </button>
              </div>
              <div className="p-6">
                {optimizations.length === 0 ? (
                  <div className="text-center py-12">
                    <Lightbulb className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">暂无优化建议，点击"触发全面优化"生成建议</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {optimizations.map((opt, idx) => (
                      <div key={idx} className="border border-gray-200 rounded-xl p-4">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center space-x-2">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                              opt.priority === 'high' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
                            }`}>
                              {opt.priority === 'high' ? '高优先级' : '中优先级'}
                            </span>
                            <span className="text-sm font-medium text-gray-900 capitalize">{opt.type}</span>
                          </div>
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        </div>
                        <p className="text-sm text-gray-600 mb-2">{opt.reason}</p>
                        <div className="bg-purple-50 rounded-lg p-3">
                          <p className="text-sm text-purple-700">
                            <strong>建议:</strong> {opt.suggestion}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Prompts Tab */}
        {activeTab === 'prompts' && (
          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                  <Settings className="w-5 h-5 text-blue-600 mr-2" />
                  Prompt 历史记录
                </h2>
              </div>
              <div className="p-6">
                {promptHistory.length === 0 ? (
                  <div className="text-center py-12">
                    <Settings className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">暂无 Prompt 历史记录</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {promptHistory.map((prompt, idx) => (
                      <div key={idx} className="border border-gray-200 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-900 capitalize">{prompt.key}</span>
                          <span className="text-xs text-gray-500">v{prompt.version}</span>
                        </div>
                        <p className="text-sm text-gray-600 mb-2 line-clamp-3">{prompt.instructions}</p>
                        <div className="flex items-center space-x-4 text-xs text-gray-500">
                          <span>使用次数: {prompt.usage_count}</span>
                          <span>最后优化: {prompt.last_optimized ? new Date(prompt.last_optimized).toLocaleString() : '从未'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
