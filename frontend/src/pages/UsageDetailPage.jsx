import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../lib/api'
import { Clock, Zap, AlertCircle } from 'lucide-react'

const MODULE_COLORS = {
  image_factory: '#8b5cf6',
  music_factory: '#ec4899',
  video_factory: '#f59e0b',
  meme_factory: '#10b981',
  writing_factory: '#3b82f6',
  seo_analyzer: '#06b6d4',
  competitor_monitor: '#8b5cf6',
  stock_tools: '#ef4444',
  prd_engine: '#6366f1',
  template_store: '#14b8a6',
  voice_chat: '#a855f7',
  tool_hub: '#f97316',
}

export default function UsageDetailPage() {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedHours, setSelectedHours] = useState(24)

  useEffect(() => {
    loadDetail()
  }, [])

  const loadDetail = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/auth/usage/detail')
      setDetail(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-gray-500 mt-3">加载中…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-2xl flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
        <div>
          <p className="font-medium text-red-700">加载失败</p>
          <p className="text-sm text-red-500 mt-1">{error}</p>
        </div>
      </div>
    )
  }

  if (!detail || detail.items.length === 0) {
    return (
      <div className="p-8 bg-white rounded-2xl border border-gray-200 text-center">
        <Zap className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 font-medium">暂无使用记录</p>
        <p className="text-sm text-gray-400 mt-1">开始使用 AI 工具后，这里会显示详细用量</p>
      </div>
    )
  }

  // 按小时聚合
  const byHour = {}
  for (const item of detail.items) {
    const d = new Date(item.created_at)
    const key = `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`
    if (!byHour[key]) byHour[key] = { hour: key, count: 0, tokens: 0 }
    byHour[key].count += 1
    byHour[key].tokens += item.tokens_used || 0
  }
  const hourData = Object.values(byHour).slice(-selectedHours)

  // 按模块聚合
  const byModule = {}
  for (const item of detail.items) {
    const mod = item.module || 'unknown'
    if (!byModule[mod]) byModule[mod] = { module: mod, count: 0, tokens: 0 }
    byModule[mod].count += 1
    byModule[mod].tokens += item.tokens_used || 0
  }
  const moduleData = Object.values(byModule).sort((a, b) => b.count - a.count)

  const totalCalls = detail.items.length
  const totalTokens = detail.items.reduce((s, i) => s + (i.tokens_used || 0), 0)
  const totalCost = (totalTokens / 1000000 * 0.03).toFixed(3)

  return (
    <div className="space-y-6">
      {/* 概览卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '总调用次数', value: totalCalls.toLocaleString(), color: 'from-purple-500 to-indigo-500' },
          { label: '消耗 Token 数', value: totalTokens.toLocaleString(), color: 'from-blue-500 to-cyan-500' },
          { label: '预估费用', value: `¥${totalCost}`, color: 'from-emerald-500 to-teal-500' },
          { label: '涉及模块', value: Object.keys(byModule).length.toString(), color: 'from-amber-500 to-orange-500' },
        ].map((card, i) => (
          <div key={i} className={`bg-gradient-to-br ${card.color} rounded-2xl p-4 text-white`}>
            <p className="text-xs opacity-80">{card.label}</p>
            <p className="text-2xl font-bold mt-1">{card.value}</p>
          </div>
        ))}
      </div>

      {/* 近 N 小时趋势 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-500" /> 近 {selectedHours} 小时调用趋势
          </h3>
          <div className="flex gap-1">
            {[12, 24, 48, 168].map(h => (
              <button key={h} onClick={() => setSelectedHours(h)}
                className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${selectedHours === h ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                {h >= 168 ? '7天' : `${h}h`}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={hourData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <XAxis dataKey="hour" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [`${v} 次`, '调用次数']} labelFormatter={l => l} />
            <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="调用次数" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 模块分布 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4 text-purple-500" /> 模块分布
        </h3>
        <div className="space-y-2.5">
          {moduleData.map((m, i) => {
            const pct = (m.count / totalCalls * 100).toFixed(1)
            return (
              <div key={i}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="font-medium text-gray-700">{m.module}</span>
                  <span className="text-gray-500">{m.count} 次 · {((m.tokens / 1000).toFixed(1))}K tokens</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{
                    width: `${pct}%`,
                    backgroundColor: MODULE_COLORS[m.module] || '#6b7280',
                  }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 最近记录 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-4">最近调用记录</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-100">
                <th className="pb-2 font-medium">时间</th>
                <th className="pb-2 font-medium">模块</th>
                <th className="pb-2 font-medium">Token 数</th>
                <th className="pb-2 font-medium">请求耗时</th>
                <th className="pb-2 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {detail.items.slice(0, 20).map((item, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 text-gray-600">{new Date(item.created_at).toLocaleString()}</td>
                  <td className="py-2 font-medium">{item.module}</td>
                  <td className="py-2 text-gray-600">{item.tokens_used?.toLocaleString() ?? '-'}</td>
                  <td className="py-2 text-gray-600">{item.duration_ms ? `${item.duration_ms}ms` : '-'}</td>
                  <td className="py-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${item.success ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                      {item.success ? '成功' : '失败'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {detail.total > 20 && (
          <p className="text-xs text-gray-400 text-center mt-3">仅展示最近 20 条，共 {detail.total} 条记录</p>
        )}
      </div>
    </div>
  )
}
