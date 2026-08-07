import React, { useState, useEffect, useCallback } from 'react'
import {
  Brain,
  TrendingUp,
  Zap,
  AlertCircle,
  RefreshCw,
  Lightbulb,
  Code,
  FileText,
  Settings,
  Clock,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDateTime, formatRelativeTime } from '../lib/format'
import {
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  Badge,
  PageHeader,
  ConfirmDialog,
} from '../components/ui'

const TABS = [
  { key: 'stats', label: '使用统计', icon: TrendingUp },
  { key: 'optimizations', label: '优化建议', icon: Zap },
  { key: 'prompts', label: 'Prompt 历史', icon: Settings },
]

export default function PlatformEvolutionPage() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [optimizations, setOptimizations] = useState([])
  const [promptHistory, setPromptHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [optimizing, setOptimizing] = useState(false)
  const [activeTab, setActiveTab] = useState('stats')
  const [confirmOptimize, setConfirmOptimize] = useState(false)

  const loadStats = useCallback(async () => {
    const res = await api.get('/api/usage-stats')
    setStats(res.data)
  }, [])

  const loadOptimizations = useCallback(async () => {
    const res = await api.get('/api/evolution/prompt-history')
    setPromptHistory(res.data || [])
  }, [])

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await Promise.all([loadStats(), loadOptimizations()])
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [loadStats, loadOptimizations])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const triggerOptimization = async () => {
    setOptimizing(true)
    try {
      const res = await api.post('/api/evolution/optimize-prompts', { target: 'all' })
      // 后端返回 {result: string}
      const resultText = res.data.result || res.data.action || '优化完成'
      setOptimizations([
        {
          type: 'all',
          priority: 'medium',
          reason: '基于近期使用数据自动生成',
          suggestion: resultText,
        },
      ])
      toast.success('优化已完成，已生成新的 Prompt 版本')
      // 刷新数据
      await Promise.all([loadStats(), loadOptimizations()])
    } catch (e) {
      toast.error(`优化失败：${e.message}`)
    } finally {
      setOptimizing(false)
      setConfirmOptimize(false)
    }
  }

  const totalRequests = stats?.total_calls || 0
  const successRate = stats?.success_rate ?? 0
  const avgTime = stats?.avg_response_time ?? 0
  const errorRate = totalRequests ? 100 - successRate : 0
  const byType = stats?.by_type || []
  const recent = stats?.recent || []
  const maxTypeCount = Math.max(1, ...byType.map((t) => t.c || 0))

  const statsCards = [
    {
      label: '总请求数',
      value: totalRequests,
      icon: TrendingUp,
      color: 'from-purple-500 to-indigo-600',
    },
    {
      label: '平均响应时间',
      value: `${avgTime}s`,
      icon: Zap,
      color: 'from-amber-500 to-orange-600',
    },
    {
      label: '错误率',
      value: `${errorRate.toFixed(1)}%`,
      icon: AlertCircle,
      color: 'from-red-500 to-rose-600',
    },
    {
      label: 'Prompt 版本',
      value: promptHistory.length,
      icon: Lightbulb,
      color: 'from-blue-500 to-cyan-600',
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="平台自进化"
        description="基于使用数据自动优化 PRD、技术方案、代码生成的 Prompt 和模板"
        icon={Brain}
        iconColor="from-purple-600 to-indigo-700"
        actions={
          <Button
            variant="gradient"
            icon={Lightbulb}
            loading={optimizing}
            disabled={totalRequests < 5}
            onClick={() => setConfirmOptimize(true)}
          >
            触发全面优化
          </Button>
        }
      />

      {/* Tabs */}
      <div className="flex space-x-1 bg-gray-100 p-1 rounded-xl max-w-md">
        {TABS.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === tab.key ? 'bg-white text-purple-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
            >
              <Icon className="w-4 h-4 mr-2" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {totalRequests < 5 && (
        <p className="text-center text-sm text-gray-500">
          需要至少 5 次使用记录才能触发优化（当前：{totalRequests} 次）
        </p>
      )}

      {loading ? (
        <SkeletonGrid count={4} />
      ) : error ? (
        <ErrorState message={`加载数据失败：${error.message}`} onRetry={loadAll} />
      ) : (
        <>
          {/* Stats Tab */}
          {activeTab === 'stats' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {statsCards.map((card, idx) => {
                  const Icon = card.icon
                  return (
                    <div key={idx} className="bg-white rounded-2xl border border-gray-200 p-5">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-medium text-gray-500">{card.label}</h3>
                        <div
                          className={`w-9 h-9 rounded-xl bg-gradient-to-br ${card.color} flex items-center justify-center`}
                        >
                          <Icon className="w-4 h-4 text-white" />
                        </div>
                      </div>
                      <p className="text-3xl font-bold text-gray-900">{card.value}</p>
                    </div>
                  )
                })}
              </div>

              {/* 任务类型分布 */}
              <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                    <Code className="w-5 h-5 text-purple-600 mr-2" />
                    按任务类型分布
                  </h2>
                </div>
                <div className="p-6">
                  {byType.length === 0 ? (
                    <Empty
                      icon={Code}
                      title="暂无任务类型数据"
                      description="使用平台功能后，将在此展示分布情况"
                    />
                  ) : (
                    byType.map((t) => (
                      <div key={t.task_type} className="mb-4 last:mb-0">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-700 capitalize">
                            {t.task_type || '未知'}
                          </span>
                          <span className="text-sm text-gray-500">
                            {t.c} 次 · 均 {Number(t.a || 0).toFixed(2)}s
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-purple-600 h-2 rounded-full transition-all duration-500"
                            style={{ width: `${((t.c || 0) / maxTypeCount) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* 最近调用 */}
              <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                    <FileText className="w-5 h-5 text-emerald-600 mr-2" />
                    最近调用
                  </h2>
                </div>
                <div className="p-6">
                  {recent.length === 0 ? (
                    <Empty icon={Clock} title="暂无调用记录" />
                  ) : (
                    <div className="space-y-2">
                      {recent.map((r, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <Badge status={r.success ? 'success' : 'failed'} dot />
                            <span className="text-sm text-gray-700 capitalize">
                              {r.task_type || '未知'}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-400">
                            <span>{Number(r.response_time || 0).toFixed(2)}s</span>
                            <span>{formatRelativeTime(r.timestamp)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Optimizations Tab */}
          {activeTab === 'optimizations' && (
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                  <Zap className="w-5 h-5 text-amber-500 mr-2" />
                  最新优化建议
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={RefreshCw}
                  loading={optimizing}
                  onClick={() => setConfirmOptimize(true)}
                >
                  重新优化
                </Button>
              </div>
              <div className="p-6">
                {optimizations.length === 0 ? (
                  <Empty
                    icon={Lightbulb}
                    title="暂无优化建议"
                    description='点击"触发全面优化"生成建议'
                    actionLabel="触发优化"
                    onAction={() => setConfirmOptimize(true)}
                  />
                ) : (
                  <div className="space-y-4">
                    {optimizations.map((opt, idx) => (
                      <div key={idx} className="border border-gray-200 rounded-xl p-4">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center space-x-2">
                            <Badge
                              status={opt.priority === 'high' ? 'failed' : 'pending'}
                              label={opt.priority === 'high' ? '高优先级' : '中优先级'}
                            />
                            <span className="text-sm font-medium text-gray-900 capitalize">
                              {opt.type}
                            </span>
                          </div>
                        </div>
                        {opt.reason && <p className="text-sm text-gray-600 mb-2">{opt.reason}</p>}
                        <div className="bg-purple-50 rounded-lg p-3">
                          <p className="text-sm text-purple-700 whitespace-pre-wrap">
                            <strong>建议:</strong> {opt.suggestion}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Prompts Tab */}
          {activeTab === 'prompts' && (
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                  <Settings className="w-5 h-5 text-blue-600 mr-2" />
                  Prompt 历史记录
                </h2>
              </div>
              <div className="p-6">
                {promptHistory.length === 0 ? (
                  <Empty
                    icon={Settings}
                    title="暂无 Prompt 历史记录"
                    description="触发优化后，新版本将记录在此"
                  />
                ) : (
                  <div className="space-y-4">
                    {promptHistory.map((prompt, idx) => (
                      <div key={idx} className="border border-gray-200 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-900 capitalize">
                              {prompt.module || prompt.key || '未知模块'}
                            </span>
                            <Badge status="inactive" label={`v${prompt.version ?? '?'}`} />
                          </div>
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {prompt.optimized_at ? formatDateTime(prompt.optimized_at) : '从未'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mb-2 line-clamp-3 whitespace-pre-wrap">
                          {prompt.instructions || '（无内容）'}
                        </p>
                        {prompt.created_by && (
                          <div className="text-xs text-gray-400">来源：{prompt.created_by}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* 触发优化确认 */}
      <ConfirmDialog
        open={confirmOptimize}
        onClose={() => setConfirmOptimize(false)}
        onConfirm={triggerOptimization}
        title="触发全面优化"
        message="将基于近期使用数据调用 LLM 生成新的 Prompt 版本，可能消耗一定 Token，确认继续？"
        confirmLabel="开始优化"
        variant="primary"
        icon={Lightbulb}
      />
    </div>
  )
}
