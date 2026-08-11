import React, { useState, useEffect } from 'react'
import {
  BarChart3,
  TrendingUp,
  PieChart,
  Zap,
  Clock,
  Activity,
  DollarSign,
  Layers,
  Target,
  Download,
} from 'lucide-react'
import { Card, PageHeader, ErrorState, SkeletonGrid } from '../components/ui'
import api, { API_BASE } from '../lib/api'
import { useToast } from '../lib/toast'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart as RePieChart,
  Pie,
  Cell,
} from 'recharts'

const COLORS = [
  '#6366f1',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
  '#ec4899',
  '#f97316',
]

// 模块代码 → 中文名映射（用量分析按用户可见文案展示，未知模块回退原代码）
const MODULE_LABELS = {
  agent_run: '智能体执行',
  agent_run_stream: '智能体流式对话',
  assistant_chat: '助手对话',
  batch_process: '批量处理',
  batch_translate: '批量翻译',
  code_review: '代码审查',
  competitor_analysis: '竞品分析',
  contract_review: '合同审查',
  conversation_stream: '对话流式生成',
  data_analyzer: '数据分析',
  data_forecast: '数据预测',
  digital_human: '数字人',
  digital_human_script: '数字人脚本',
  doc_qa: '文档问答',
  game_generate: '小游戏生成',
  growth_batch: '批量增长内容',
  mindmap_generate: '思维导图',
  miniapp_generate: '小程序生成',
  openai_gateway: '开放API调用',
  openai_gateway_stream: '开放API流式',
  prd_code: '代码生成',
  prd_generate: '方案文档生成',
  prd_review: '方案评审',
  prd_td: '技术设计',
  prd_test: '测试用例生成',
  publish_guide: '发布指南',
  resume_optimize: '简历优化',
  seo_analyze: 'SEO分析',
  video_analyze: '视频解析',
  voice_chat: '语音对话',
  voice_generate: '语音合成',
  voice_respond: '语音回复',
  voice_tts: '配音合成',
  web_search: '联网搜索',
  web_search_noresults: '搜索无结果',
  wf_agent_node: '工作流节点',
}

const moduleLabel = (key) => MODULE_LABELS[key] || key

export default function UsageAnalyticsPage() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [dailyUsage, setDailyUsage] = useState([])
  const [moduleDist, setModuleDist] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  // v15：趋势区间 + 按模块/按用户筛选
  const [days, setDays] = useState(7)
  const [moduleFilter, setModuleFilter] = useState('')
  const [userFilter, setUserFilter] = useState('')
  const [userOptions, setUserOptions] = useState([])

  // 导出使用统计 CSV（带 token 的 fetch，触发浏览器下载）
  const exportCsv = async () => {
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`${API_BASE}/api/usage-stats/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `usage_stats_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('统计已导出')
    } catch (e) {
      toast.error(`导出失败：${e.message}`)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  // 筛选变化时重新加载（mount 时也会触发一次）
  useEffect(() => {
    loadStats()
  }, [days, moduleFilter, userFilter])

  const loadUsers = async () => {
    try {
      const res = await api.get('/api/usage-stats/users')
      setUserOptions(res.data || [])
    } catch {
      // 用户列表失败不阻塞页面，但需提示降级原因（避免用户误以为筛选功能缺失）
      toast.warning('用户列表暂不可用，当前仅能查看全部用户数据')
    }
  }

  const loadStats = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const res = await api.get('/api/usage-stats', {
        params: {
          days,
          module: moduleFilter || undefined,
          user: userFilter || undefined,
        },
      })
      const data = res.data || {}
      setStats(data)

      // 构建每日使用趋势（days 天区间）
      if (data.daily_breakdown) {
        setDailyUsage(
          data.daily_breakdown.map((d) => ({
            date: d.date,
            调用次数: d.count,
            消耗Token: d.tokens,
          }))
        )
      }

      // 构建模块分布（不受 module 筛选影响，展示全量占比）
      if (data.module_breakdown) {
        setModuleDist(
          data.module_breakdown.map((m) => ({ key: m.module, name: moduleLabel(m.module), value: m.count }))
        )
      }
    } catch (e) {
      // 后端不可用时展示错误而非编造数据（真实统计才能支撑商业决策）
      setLoadError(e?.message || '用量统计加载失败')
      toast.error(`加载用量统计失败：${e.message || '网络错误'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="用量分析"
        description="全面了解你的AI使用情况：调用次数、Token消耗、模块分布、使用趋势"
        icon={BarChart3}
        iconColor="from-blue-500 to-indigo-600"
        actions={
          <button
            onClick={exportCsv}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-sm text-gray-700 rounded-xl hover:bg-gray-50 hover:border-blue-300 transition-colors shadow-sm"
          >
            <Download className="w-4 h-4 text-blue-500" /> 导出CSV
          </button>
        }
      />

      {/* 筛选工具栏：区间 + 模块 + 用户 */}
      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 font-medium">趋势区间</span>
            <div className="flex rounded-lg border border-gray-200 overflow-hidden">
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`px-3 py-1.5 text-sm transition-colors ${
                    days === d
                      ? 'bg-blue-500 text-white'
                      : 'bg-white text-gray-600 hover:bg-blue-50'
                  }`}
                >
                  {d}天
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 font-medium">模块</span>
            <select
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="">全部模块</option>
              {moduleDist.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.name}（{m.value} 次）
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 font-medium">用户</span>
            <select
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="">全部用户</option>
              {userOptions.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </select>
          </div>
          {(moduleFilter || userFilter) && (
            <button
              onClick={() => {
                setModuleFilter('')
                setUserFilter('')
              }}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              清除筛选
            </button>
          )}
        </div>
      </Card>

      {loading ? (
        <SkeletonGrid count={8} />
      ) : loadError ? (
        <ErrorState message={loadError} onRetry={loadStats} />
      ) : (
        <>
          {/* 总览卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: '累计调用',
            value: stats?.total_calls?.toLocaleString() ?? '-',
            icon: Zap,
            color: 'from-blue-500 to-indigo-600',
            bg: 'bg-blue-50',
            text: 'text-blue-600',
          },
          {
            label: '累计Token',
            value: stats?.total_tokens?.toLocaleString() ?? '-',
            icon: Layers,
            color: 'from-emerald-500 to-teal-600',
            bg: 'bg-emerald-50',
            text: 'text-emerald-600',
          },
          {
            label: '今日调用',
            value: stats?.today_calls ?? '-',
            icon: Activity,
            color: 'from-amber-500 to-orange-600',
            bg: 'bg-amber-50',
            text: 'text-amber-600',
          },
          {
            label: '今日Token',
            value: stats?.today_tokens?.toLocaleString() ?? '-',
            icon: Target,
            color: 'from-purple-500 to-violet-600',
            bg: 'bg-purple-50',
            text: 'text-purple-600',
          },
        ].map((item, i) => (
          <Card key={i} className="text-center">
            <div
              className={`w-10 h-10 mx-auto rounded-xl bg-gradient-to-br ${item.color} flex items-center justify-center mb-2`}
            >
              <item.icon className="w-5 h-5 text-white" />
            </div>
            <div className={`text-2xl font-bold ${item.text}`}>{item.value}</div>
            <div className="text-xs text-gray-500 mt-1">{item.label}</div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 趋势图 */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-blue-500" /> {days}天使用趋势
          </h3>
          {dailyUsage.length > 0 && (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={dailyUsage} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="调用次数"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="消耗Token"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
          {dailyUsage.length > 0 && dailyUsage.length < days && (
            <p className="mt-3 text-xs text-gray-400">
              当前仅有 {dailyUsage.length} 天使用记录，{days} 天区间内其余日期暂无数据
            </p>
          )}
          {dailyUsage.length === 0 && (
            <p className="py-10 text-sm text-gray-400 text-center">所选区间暂无使用记录</p>
          )}
        </Card>

        {/* 模块分布 */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <PieChart className="w-4 h-4 text-purple-500" /> 模块用量分布
          </h3>
          {moduleDist.length > 0 && (
            <ResponsiveContainer width="100%" height={280}>
              <RePieChart>
                <Pie
                  data={moduleDist}
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  innerRadius={50}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {moduleDist.map((entry, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </RePieChart>
            </ResponsiveContainer>
          )}
          {moduleDist.length === 0 && (
            <p className="py-10 text-sm text-gray-400 text-center">暂无模块用量数据</p>
          )}
        </Card>
      </div>

      {/* 附加信息 */}
      <Card>
        <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-amber-500" /> 账户概览
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-xs text-gray-500">会员等级</div>
            <div className="font-semibold text-gray-800 capitalize">
              {stats?.member_level || '-'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">今日剩余</div>
            <div className="font-semibold text-gray-800">{stats?.remaining_today || '-'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">最常用模块</div>
            <div className="font-semibold text-gray-800">{stats?.most_used || '-'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">日均调用</div>
            <div className="font-semibold text-gray-800">
              {stats?.total_calls
                ? Math.round(stats.total_calls / Math.max(1, dailyUsage.length || 7))
                : '-'}
            </div>
          </div>
        </div>
      </Card>
        </>
      )}
    </div>
  )
}
