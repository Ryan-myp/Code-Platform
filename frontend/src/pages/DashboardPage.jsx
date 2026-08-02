import React, { useState, useEffect } from 'react'
import { BarChart3, Bot, Layers, FolderKanban, CheckCircle2, GitBranch, Code2, Languages, FileText, TrendingUp } from 'lucide-react'
import { Card } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

export default function DashboardPage() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadStats() }, [])
  const loadStats = async () => {
    try {
      const [statsRes, overviewRes] = await Promise.all([
        api.get('/api/dashboard/stats'),
        api.get('/api/analytics/overview'),
      ])
      setStats({ ...statsRes.data, ...overviewRes.data })
    } catch (e) { toast.error('加载数据失败') }
    finally { setLoading(false) }
  }

  const cards = [
    { label: 'Agent 总数', value: stats?.agents || 0, icon: Bot, color: 'from-emerald-500 to-teal-600' },
    { label: 'Workflow 总数', value: stats?.workflows || 0, icon: Layers, color: 'from-blue-500 to-indigo-600' },
    { label: '项目总数', value: stats?.projects || 0, icon: FolderKanban, color: 'from-violet-500 to-purple-600' },
    { label: '任务总数', value: stats?.tasks || 0, icon: CheckCircle2, color: 'from-amber-500 to-orange-600' },
    { label: '已完成任务', value: stats?.tasks_completed || stats?.completed_tasks || 0, icon: TrendingUp, color: 'from-green-500 to-emerald-600' },
    { label: '流水线', value: stats?.pipelines || 0, icon: GitBranch, color: 'from-cyan-500 to-blue-600' },
    { label: '代码生成次数', value: stats?.code_generations || stats?.total_code_gens || 0, icon: Code2, color: 'from-pink-500 to-rose-600' },
    { label: '翻译次数', value: stats?.translations || stats?.total_translations || 0, icon: Languages, color: 'from-indigo-500 to-violet-600' },
    { label: '成果总数', value: stats?.artifacts || stats?.total_artifacts || 0, icon: FileText, color: 'from-teal-500 to-cyan-600' },
  ]

  if (loading) return <div className="flex justify-center py-12"><div className="animate-spin h-6 w-6 border-b-2 border-brand-500 rounded-full" /></div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">数据仪表盘</h1>
        <p className="text-sm text-gray-500 mt-1">平台整体数据概览</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-4">
        {cards.map(card => (
          <Card key={card.label}>
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${card.color} flex items-center justify-center shadow-sm`}>
                <card.icon className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{card.value}</div>
                <div className="text-sm text-gray-500">{card.label}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <Card>
        <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-500" /> 平台使用趋势
        </h2>
        <div className="text-center py-12 text-gray-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>趋势图表功能开发中...</p>
        </div>
      </Card>
    </div>
  )
}
