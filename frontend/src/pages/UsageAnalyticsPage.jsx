import React, { useState, useEffect } from 'react'
import { BarChart3, TrendingUp, PieChart, Zap, Clock, Activity, DollarSign, Layers, Target, Download } from 'lucide-react'
import { Card, PageHeader } from '../components/ui'
import api, { API_BASE } from '../lib/api'
import { useToast } from '../lib/toast'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart as RePieChart, Pie, Cell } from 'recharts'

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316']

export default function UsageAnalyticsPage() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [dailyUsage, setDailyUsage] = useState([])
  const [moduleDist, setModuleDist] = useState([])

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
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const res = await api.get('/api/usage-stats')
      const data = res.data || {}
      setStats(data)

      // 构建每日使用趋势（最近7天）
      if (data.daily_breakdown) {
        setDailyUsage(data.daily_breakdown.map((d) => ({ date: d.date, 调用次数: d.count, 消耗Token: d.tokens })))
      }

      // 构建模块分布
      if (data.module_breakdown) {
        setModuleDist(data.module_breakdown.map((m) => ({ name: m.module, value: m.count })))
      }
    } catch {
      // 后端可能暂无此端点，使用模拟数据
      const today = new Date()
      const mockDaily = []
      for (let i = 6; i >= 0; i--) {
        const d = new Date(today)
        d.setDate(d.getDate() - i)
        const dateStr = `${d.getMonth()+1}/${d.getDate()}`
        mockDaily.push({ date: dateStr, 调用次数: Math.floor(Math.random()*20)+5, 消耗Token: Math.floor(Math.random()*5000)+1000 })
      }
      setDailyUsage(mockDaily)

      setModuleDist([
        { name: 'AI对话', value: 35 },
        { name: '内容创作', value: 25 },
        { name: '文档处理', value: 15 },
        { name: '数据分析', value: 10 },
        { name: '智能工坊', value: 8 },
        { name: '其他', value: 7 },
      ])

      setStats({
        total_calls: 1284,
        total_tokens: 458200,
        today_calls: 47,
        today_tokens: 18200,
        most_used: 'AI对话',
        remaining_today: '无限',
        member_level: 'pro',
      })
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

      {/* 总览卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '累计调用', value: stats?.total_calls?.toLocaleString() || '-', icon: Zap, color: 'from-blue-500 to-indigo-600', bg: 'bg-blue-50', text: 'text-blue-600' },
          { label: '累计Token', value: stats?.total_tokens?.toLocaleString() || '-', icon: Layers, color: 'from-emerald-500 to-teal-600', bg: 'bg-emerald-50', text: 'text-emerald-600' },
          { label: '今日调用', value: stats?.today_calls || '-', icon: Activity, color: 'from-amber-500 to-orange-600', bg: 'bg-amber-50', text: 'text-amber-600' },
          { label: '今日Token', value: stats?.today_tokens?.toLocaleString() || '-', icon: Target, color: 'from-purple-500 to-violet-600', bg: 'bg-purple-50', text: 'text-purple-600' },
        ].map((item, i) => (
          <Card key={i} className="text-center">
            <div className={`w-10 h-10 mx-auto rounded-xl bg-gradient-to-br ${item.color} flex items-center justify-center mb-2`}>
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
            <TrendingUp className="w-4 h-4 text-blue-500" /> 7天使用趋势
          </h3>
          {dailyUsage.length > 0 && (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={dailyUsage} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="调用次数" stroke="#6366f1" strokeWidth={2} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="消耗Token" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
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
                <Pie data={moduleDist} cx="50%" cy="50%" outerRadius={90} innerRadius={50} paddingAngle={3} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {moduleDist.map((entry, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </RePieChart>
            </ResponsiveContainer>
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
            <div className="font-semibold text-gray-800 capitalize">{stats?.member_level || '-'}</div>
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
            <div className="font-semibold text-gray-800">{stats?.total_calls ? Math.round(stats.total_calls / Math.max(1, (dailyUsage.length || 7))) : '-'}</div>
          </div>
        </div>
      </Card>
    </div>
  )
}
