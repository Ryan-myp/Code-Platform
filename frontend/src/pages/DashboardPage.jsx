import React, { useState, useEffect } from 'react'
import {
  BarChart3, Bot, Layers, FolderKanban, CheckCircle2, GitBranch, Code2, Languages,
  FileText, TrendingUp, Search, Sparkles, Send, Brain, Upload, Eye, Clock,
  BarChart as BarChartIcon, PieChart, TrendingUp as TrendingUpIcon, Activity,
} from 'lucide-react'
import { BarChart, Bar, PieChart as RPieChart, Pie, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts'
import { Card, Button, PageHeader, Badge, SkeletonGrid, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#f97316', '#84cc16']

function ChartRenderer({ chartType, option, title, insight }) {
  if (!option) return null

  const series = option.series || []
  const xData = option.xAxis?.data || option.xAxis?.[0]?.data || []

  // Build data array from xAxis/yAxis/series
  const data = xData.map((label, i) => {
    const item = { name: label }
    series.forEach(s => {
      item[s.name || 'value'] = s.data?.[i] ?? 0
    })
    return item
  })

  const dataKeys = series.map(s => s.name || 'value')

  return (
    <div className="space-y-3">
      {title && <h3 className="text-base font-semibold text-gray-900">{title}</h3>}
      {insight && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800">
          <Brain className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{insight}</span>
        </div>
      )}

      {chartType === 'bar' && (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {dataKeys.map((k, i) => (
              <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}

      {chartType === 'line' && (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {dataKeys.map((k, i) => (
              <Line key={k} type="monotone" dataKey={k} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 4 }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}

      {chartType === 'pie' && (
        <ResponsiveContainer width="100%" height={320}>
          <RPieChart>
            <Pie data={data} dataKey={dataKeys[0]} nameKey="name" cx="50%" cy="50%" outerRadius={120}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </RPieChart>
        </ResponsiveContainer>
      )}

      {!['bar', 'line', 'pie'].includes(chartType) && (
        <div className="text-center py-8 text-gray-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-30" />
          <p>图表类型：{chartType} — 暂用JSON展示</p>
          <pre className="mt-3 text-left text-xs bg-gray-50 p-3 rounded overflow-auto max-h-60">
            {JSON.stringify({ chartType, title, insight, data }, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('overview')

  // 智能查询状态
  const [nlQuery, setNlQuery] = useState('')
  const [csvFile, setCsvFile] = useState(null)
  const [csvData, setCsvData] = useState('')
  const [csvPreview, setCsvPreview] = useState(null)
  const [querying, setQuerying] = useState(false)
  const [chartResult, setChartResult] = useState(null)
  const [queryHistory, setQueryHistory] = useState([])

  useEffect(() => { loadStats() }, [])

  const loadStats = async () => {
    try {
      const [statsRes, overviewRes] = await Promise.all([
        api.get('/api/dashboard/stats'),
        api.get('/api/analytics/overview'),
      ])
      setStats({ ...statsRes.data, ...overviewRes.data })
      setError(null)
    } catch (e) { setError(e) }
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

  const doNLQuery = async () => {
    if (!nlQuery.trim()) { toast.error('请输入查询内容'); return }
    setQuerying(true); setChartResult(null)
    try {
      const res = await api.post('/api/dashboard/nl-query', {
        query: nlQuery.trim(),
        csv_data: csvData,
        csv_filename: csvPreview?.filename || '',
      })
      setChartResult(res.data)
      setQueryHistory(prev => [{ query: nlQuery, time: new Date().toLocaleTimeString() }, ...prev.slice(0, 9)])
    } catch (e) { toast.error(`查询失败：${e.message}`) }
    finally { setQuerying(false) }
  }

  const uploadCsv = async (e) => {
    const f = e.target.files?.[0]; if (!f) return
    setCsvFile(f)
    const form = new FormData(); form.append('file', f)
    try {
      const res = await api.post('/api/dashboard/upload-csv', form)
      setCsvPreview(res.data)
      setCsvData(res.data.csv_data || '')
      toast.success(`CSV加载完成：${res.data.row_count} 行, ${res.data.columns?.length} 列`)
    } catch (err) { toast.error(`CSV上传失败：${err.message}`) }
  }

  if (loading) return (
    <div className="space-y-6">
      <PageHeader title="数据仪表盘" description="平台全局数据概览 + 自然语言智能图表查询" icon={BarChart3} iconColor="from-blue-500 to-indigo-600" />
      <SkeletonGrid count={6} />
    </div>
  )

  if (error && !stats) return (
    <div className="space-y-6">
      <PageHeader title="数据仪表盘" description="平台全局数据概览 + 自然语言智能图表查询" icon={BarChart3} iconColor="from-blue-500 to-indigo-600" />
      <ErrorState error={error} onRetry={() => { setLoading(true); setError(null); loadStats() }} />
    </div>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="数据仪表盘"
        description="平台全局数据概览 + 自然语言智能图表查询"
        icon={BarChart3}
        iconColor="from-blue-500 to-indigo-600"
      />

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {[
          { id: 'overview', label: '数据概览', icon: BarChartIcon },
          { id: 'smart', label: '智能查询', icon: Brain },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* 数据概览 */}
      {tab === 'overview' && (
        <>
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
              <Activity className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>切换到"智能查询"tab，用自然语言探索数据趋势</p>
            </div>
          </Card>
        </>
      )}

      {/* 智能查询 */}
      {tab === 'smart' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Search className="w-4 h-4 text-violet-500" /> 自然语言查询
              </h3>
              <textarea value={nlQuery} onChange={(e) => setNlQuery(e.target.value)}
                placeholder="用自然语言描述你想看的数据分析…&#10;&#10;示例：&#10;- 过去7天每天的内容发布量趋势&#10;- 各类型内容的占比&#10;- 本周互动量TOP5的文章&#10;- 各Agent的任务完成率对比"
                rows={5}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none" />
              <Button variant="primary" size="sm" icon={Send} loading={querying} onClick={doNLQuery} className="mt-2 w-full">
                {querying ? 'AI 分析中…' : '智能生成图表'}
              </Button>
            </Card>

            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <Upload className="w-4 h-4 text-emerald-500" /> 上传数据源
                </h3>
                {csvPreview && <Badge color="green">{csvPreview.row_count}行</Badge>}
              </div>
              <label className="flex flex-col items-center gap-2 p-6 border-2 border-dashed border-gray-200 rounded-xl hover:border-emerald-400 cursor-pointer transition-colors">
                <Upload className="w-6 h-6 text-gray-300" />
                <span className="text-sm text-gray-400">{csvFile ? csvFile.name : '点击上传CSV文件（可选）'}</span>
                <input type="file" accept=".csv" onChange={uploadCsv} className="hidden" />
              </label>
              {csvPreview && (
                <div className="mt-2 p-2 rounded-lg bg-gray-50 text-xs text-gray-500">
                  列：{csvPreview.columns?.map(c => `${c.name}(${c.type})`).join(', ')}
                </div>
              )}
            </Card>

            {/* 查询历史 */}
            {queryHistory.length > 0 && (
              <Card>
                <h3 className="font-semibold text-gray-900 mb-2 text-sm flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5 text-gray-400" /> 查询历史
                </h3>
                <div className="space-y-1">
                  {queryHistory.map((h, i) => (
                    <button key={i} onClick={() => setNlQuery(h.query)}
                      className="w-full text-left text-xs text-gray-600 hover:text-violet-600 px-2 py-1 rounded hover:bg-violet-50 transition-colors">
                      {h.query} <span className="text-gray-300 ml-1">{h.time}</span>
                    </button>
                  ))}
                </div>
              </Card>
            )}
          </div>

          <div className="lg:col-span-2">
            {chartResult ? (
              <Card>
                <ChartRenderer {...chartResult} />
              </Card>
            ) : (
              <Card>
                <div className="text-center py-16 text-gray-400">
                  <Brain className="w-16 h-16 mx-auto mb-4 opacity-20" />
                  <p className="font-medium text-gray-500">输入自然语言查询，AI 自动生成图表</p>
                  <p className="text-xs mt-2">支持柱状图、折线图、饼图、散点图、雷达图</p>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

