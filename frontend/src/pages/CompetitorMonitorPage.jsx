import React, { useState, useEffect, useCallback } from 'react'
import {
  Plus,
  Trash2,
  Loader2,
  Radar,
  TrendingUp,
  Target,
  Clock,
  Search,
  Activity,
  ThumbsUp,
  MessageSquare,
  Share2,
  AlertTriangle,
  CheckCircle2,
  Copy,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDateTime } from '../lib/format'
import ShareButton from '../components/ShareButton'
import {
  Button,
  PageHeader,
  Card,
  Empty,
  PageLoading,
  ErrorState,
  Badge,
  ConfirmDialog,
  Modal,
} from '../components/ui'

const PLATFORMS = ['抖音', '小红书', 'B站', '微信公众号', '快手', '微博', '知乎', '视频号', '其他']

// 监控频率设置
const FREQUENCY_OPTIONS = [
  { value: 'daily', label: '每日' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
  { value: 'manual', label: '手动' },
]

const FREQUENCY_META = {
  daily: { label: '每日监控', color: 'blue' },
  weekly: { label: '每周监控', color: 'green' },
  monthly: { label: '每月监控', color: 'amber' },
  manual: { label: '手动监控', color: 'gray' },
}

const PLATFORM_COLORS = {
  抖音: 'bg-black text-white',
  小红书: 'bg-red-500 text-white',
  B站: 'bg-sky-500 text-white',
  微信公众号: 'bg-emerald-600 text-white',
  快手: 'bg-orange-500 text-white',
  微博: 'bg-rose-500 text-white',
  知乎: 'bg-blue-600 text-white',
  视频号: 'bg-teal-600 text-white',
  其他: 'bg-gray-500 text-white',
}

export default function CompetitorMonitorPage() {
  const toast = useToast()
  const [competitors, setCompetitors] = useState([])
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 添加竞品
  const [addOpen, setAddOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: '',
    platform: '抖音',
    account_id: '',
    description: '',
    profile_url: '',
    monitor_frequency: 'weekly',
  })

  // 分析
  const [analyzing, setAnalyzing] = useState(false)
  const [selectedIds, setSelectedIds] = useState([])
  const [focus, setFocus] = useState('')
  const [report, setReport] = useState(null) // 当前查看的报告
  const [reportOpen, setReportOpen] = useState(false)
  const [deleting, setDeleting] = useState(null)

  const fetchAll = useCallback(async () => {
    try {
      const [compRes, repRes] = await Promise.all([
        api.get('/api/monitor/competitors'),
        api.get('/api/monitor/reports'),
      ])
      setCompetitors(compRes.data || [])
      setReports(repRes.data || [])
      setError(null)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  const handleAdd = async () => {
    if (!form.name.trim()) {
      toast.error('请填写竞品名称')
      return
    }
    setSaving(true)
    try {
      await api.post('/api/monitor/competitors', {
        name: form.name.trim(),
        platform: form.platform,
        account_id: form.account_id.trim(),
        description: form.description.trim(),
        profile_url: form.profile_url.trim(),
        monitor_frequency: form.monitor_frequency,
      })
      toast.success('竞品已添加')
      setAddOpen(false)
      setForm({ name: '', platform: '抖音', account_id: '', description: '', profile_url: '', monitor_frequency: 'weekly' })
      fetchAll()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      await api.delete(`/api/monitor/competitors/${deleting}`)
      toast.success('已删除竞品')
      setDeleting(null)
      fetchAll()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const handleAnalyze = async () => {
    if (selectedIds.length === 0) {
      toast.error('请至少选择一个竞品')
      return
    }
    setAnalyzing(true)
    try {
      const res = await api.post('/api/monitor/analyze', {
        competitor_ids: selectedIds,
        query: focus.trim(),
      })
      setReport(res.data)
      setReportOpen(true)
      toast.success('分析完成')
      fetchAll()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  const openReport = async (r) => {
    try {
      const res = await api.get(`/api/monitor/report/${r.id}`)
      setReport({
        report_id: res.data.id,
        analysis: res.data.analysis_data || {},
        radar: res.data.radar_data || {},
        created_at: res.data.created_at,
      })
      setReportOpen(true)
    } catch (e) {
      toast.error(e.message)
    }
  }

  const toggleSelect = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  // 报告 → Markdown（复制/分享复用）
  const buildReportMd = (r) => {
    if (!r?.analysis) return ''
    const a = r.analysis
    const lines = ['# 竞品分析报告', '', `生成于 ${formatDateTime(r.created_at)}`, '']
    if (r.changes?.summary) {
      lines.push('## 变化摘要（与上次对比）', '', `> ${r.changes.summary}`)
      ;(r.changes.changed || []).forEach((c) => {
        if (c.modified?.length) {
          lines.push('', `- **${c.label}**：${c.modified[0].prev} → ${c.modified[0].curr}`)
        }
        ;(c.added || []).forEach((x) => lines.push(`- ➕ ${c.label}新增：${x}`))
        ;(c.removed || []).forEach((x) => lines.push(`- ➖ ${c.label}移除：${x}`))
      })
      lines.push('')
    }
    if (a.overview) lines.push('## 整体概览', '', a.overview, '')
    if (a.content_categories?.length) {
      lines.push('## 内容分类', '')
      a.content_categories.forEach((c) => lines.push(`- ${c.name}：${c.desc || c.count || ''}`))
      lines.push('')
    }
    if (a.hot_patterns?.length) {
      lines.push('## 热门模式', '')
      a.hot_patterns.forEach((p) => lines.push(`- ${typeof p === 'string' ? p : p.pattern || ''}`))
      lines.push('')
    }
    if (a.publishing_habits) {
      lines.push(
        '## 发布习惯',
        '',
        `- 频率：${a.publishing_habits.frequency || '—'}`,
        `- 主平台：${a.publishing_habits.platform_focus || '—'}`,
        `- 最佳时段：${(a.publishing_habits.best_times || []).join('、') || '—'}`,
        `- 分发策略：${a.publishing_habits.multi_platform_strategy || '—'}`,
        ''
      )
    }
    if (a.engagement_analysis) {
      lines.push(
        '## 互动分析',
        '',
        `- 均赞：${a.engagement_analysis.avg_likes ?? '—'}`,
        `- 均评：${a.engagement_analysis.avg_comments ?? '—'}`,
        `- 均转：${a.engagement_analysis.avg_shares ?? '—'}`,
        `- 互动率：${a.engagement_analysis.engagement_rate || '—'} · 趋势：${a.engagement_analysis.trend || '—'}`,
        ''
      )
    }
    if (a.competitive_advantages?.length) {
      lines.push('## 竞争优势', '')
      a.competitive_advantages.forEach((x) => lines.push(`- ${x}`))
      lines.push('')
    }
    if (a.competitive_weaknesses?.length) {
      lines.push('## 竞争劣势', '')
      a.competitive_weaknesses.forEach((x) => lines.push(`- ${x}`))
      lines.push('')
    }
    if (a.recommendations?.length) {
      lines.push('## 策略建议', '')
      a.recommendations.forEach((x) => lines.push(`- ${x}`))
      lines.push('')
    }
    lines.push('---', `由小团智能平台 AI 竞品监控生成 · ${new Date().toLocaleString()}`)
    return lines.join('\n')
  }

  const copyReport = async () => {
    const md = buildReportMd(report)
    if (!md) return
    try {
      await navigator.clipboard.writeText(md)
      toast.success('报告已复制')
    } catch {
      toast.error('复制失败，请手动选择复制')
    }
  }

  // 雷达图维度（从 radar.option.radar.indicator 解析）
  const radarIndicators = report?.radar?.option?.radar?.indicator || []
  const radarSeries = report?.radar?.option?.series || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="竞品监控"
        description="竞品追踪 · AI 策略分析 · 多维对比雷达"
        actions={
          <Button variant="primary" icon={Plus} onClick={() => setAddOpen(true)}>
            添加竞品
          </Button>
        }
      />

      {loading ? (
        <PageLoading />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchAll} />
      ) : (
        <>
          {/* 竞品列表 */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-ink-900 flex items-center gap-2">
                <Target className="w-4 h-4 text-brand-500" />
                竞品列表
                <Badge color="brand">{competitors.length}</Badge>
              </h3>
            </div>
            {competitors.length === 0 ? (
              <Empty
                icon={Target}
                title="还没有竞品"
                description="添加竞品账号后，可一键 AI 分析其内容策略"
                action={
                  <Button icon={Plus} onClick={() => setAddOpen(true)}>
                    添加第一个竞品
                  </Button>
                }
              />
            ) : (
              <div className="space-y-2">
                {competitors.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center gap-3 p-3 rounded-xl border border-ink-100 hover:border-brand-200 hover:bg-brand-50/30 transition-all"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(c.id)}
                      onChange={() => toggleSelect(c.id)}
                      className="w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                    />
                    <div
                      className={`w-9 h-9 rounded-lg flex items-center justify-center text-xs font-semibold flex-shrink-0 ${PLATFORM_COLORS[c.platform] || 'bg-gray-500 text-white'}`}
                    >
                      {c.platform?.[0] || '竞'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-ink-900 truncate">{c.name}</p>
                      <p className="text-xs text-ink-400 truncate">
                        {c.platform} ·{' '}
                        {c.account_id || c.profile_url || c.description || '未填写账号'}
                      </p>
                    </div>
                    <Badge color={(FREQUENCY_META[c.monitor_frequency] || FREQUENCY_META.weekly).color}>
                      {FREQUENCY_META[c.monitor_frequency]?.label || '每周监控'}
                    </Badge>
                    <span className="text-[11px] text-ink-300 hidden sm:block">
                      更新于 {formatDateTime(c.updated_at)}
                    </span>
                    <button
                      onClick={() => setDeleting(c.id)}
                      className="p-1.5 rounded-lg text-ink-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="删除竞品"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {competitors.length > 0 && (
              <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-brand-50 to-indigo-50 border border-brand-100">
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="flex-1">
                    <p className="text-xs font-medium text-brand-700 mb-1.5">分析重点（可选）</p>
                    <input
                      value={focus}
                      onChange={(e) => setFocus(e.target.value)}
                      placeholder="如：聚焦选题策略 / 互动运营手法"
                      className="w-full px-3.5 py-2.5 rounded-xl border border-brand-200 bg-white focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none text-sm"
                    />
                  </div>
                  <div className="flex items-end">
                    <Button
                      variant="primary"
                      icon={Radar}
                      loading={analyzing}
                      disabled={selectedIds.length === 0}
                      onClick={handleAnalyze}
                    >
                      分析已选（{selectedIds.length}）
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* 分析报告列表 */}
          <Card>
            <h3 className="font-semibold text-ink-900 mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-brand-500" />
              分析报告
              <Badge color="brand">{reports.length}</Badge>
            </h3>
            {reports.length === 0 ? (
              <Empty
                icon={Radar}
                title="暂无分析报告"
                description="选择竞品并点击分析，生成策略洞察与对比雷达图"
              />
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                {reports.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => openReport(r)}
                    className="text-left p-4 rounded-xl border border-ink-100 hover:border-brand-300 hover:shadow-soft transition-all group"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <Badge color="brand">{formatDateTime(r.created_at)}</Badge>
                      <Radar className="w-4 h-4 text-ink-300 group-hover:text-brand-500 transition-colors" />
                    </div>
                    <p className="text-sm text-ink-600 line-clamp-2">
                      竞品数{' '}
                      {(() => {
                        try {
                          return JSON.parse(r.competitor_ids || '[]').length
                        } catch {
                          return 0
                        }
                      })()}{' '}
                      · 点击查看详情
                    </p>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </>
      )}

      {/* 添加竞品弹窗 */}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="添加竞品">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">竞品名称 *</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：某某科技官方号"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">平台</label>
            <div className="flex flex-wrap gap-1.5">
              {PLATFORMS.map((p) => (
                <button
                  key={p}
                  onClick={() => setForm({ ...form, platform: p })}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    form.platform === p
                      ? 'bg-brand-500 text-white shadow-soft'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              账号 ID / 主页链接
            </label>
            <input
              value={form.account_id}
              onChange={(e) => setForm({ ...form, account_id: e.target.value })}
              placeholder="如：@xxx 或 https://…"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">主页 URL</label>
            <input
              value={form.profile_url}
              onChange={(e) => setForm({ ...form, profile_url: e.target.value })}
              placeholder="https://…"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">监控频率</label>
            <div className="flex flex-wrap gap-1.5">
              {FREQUENCY_OPTIONS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setForm({ ...form, monitor_frequency: f.value })}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    form.monitor_frequency === f.value
                      ? 'bg-brand-500 text-white shadow-soft'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-1">设置监控节奏，便于定期对比竞品变化</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">竞品描述</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              placeholder="内容定位、更新频率、目标受众等（用于 AI 分析）"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !analyzing) {
                  e.preventDefault()
                  handleAnalyze()
                }
              }}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm resize-none"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={() => setAddOpen(false)}>
            取消
          </Button>
          <Button variant="primary" icon={Plus} loading={saving} onClick={handleAdd}>
            添加
          </Button>
        </div>
      </Modal>

      {/* 报告详情弹窗 */}
      <Modal open={reportOpen} onClose={() => setReportOpen(false)} title="竞品分析报告" size="lg">
        {report ? (
          <div className="space-y-5 max-h-[70vh] overflow-y-auto pr-1">
            <div className="flex items-center gap-2 text-xs text-ink-400">
              <Clock className="w-3.5 h-3.5" />
              生成于 {formatDateTime(report.created_at)}
              <span className="ml-auto flex items-center gap-2">
                <button
                  onClick={copyReport}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-100 hover:bg-brand-50 text-ink-600 hover:text-brand-600 transition-colors"
                  title="复制报告全文"
                >
                  <Copy className="w-3 h-3" /> 复制
                </button>
                <ShareButton content={buildReportMd(report)} title="竞品分析报告" contentType="competitor_report" />
                <span className="flex items-center gap-1 text-emerald-600">
                  <CheckCircle2 className="w-3.5 h-3.5" /> AI 完成
                </span>
              </span>
            </div>

            {/* 变化摘要（diff 高亮） */}
            {report.changes && (
              <div className="p-4 rounded-xl border border-indigo-100 bg-indigo-50/40">
                <h4 className="text-sm font-semibold text-ink-900 mb-2 flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4 text-indigo-500" /> 变化摘要（与上次对比）
                </h4>
                <p className="text-xs text-ink-600 mb-2">{report.changes.summary}</p>
                {(report.changes.changed || []).length > 0 && (
                  <div className="space-y-2">
                    {report.changes.changed.map((c, i) => (
                      <div key={i} className="text-xs space-y-1">
                        <p className="font-medium text-ink-700">{c.label}</p>
                        {(c.modified || []).map((m, mi) => (
                          <p key={mi} className="flex items-center gap-1.5">
                            <span className="text-amber-600 font-medium">↻</span>
                            <span className="text-ink-400 line-through">{m.prev}</span>
                            <span className="text-ink-300">→</span>
                            <span className="text-amber-700">{m.curr}</span>
                          </p>
                        ))}
                        {(c.added || []).map((x, xi) => (
                          <p key={`a${xi}`} className="flex items-center gap-1.5 text-emerald-700">
                            <span className="font-bold">+</span> {x}
                          </p>
                        ))}
                        {(c.removed || []).map((x, xi) => (
                          <p key={`r${xi}`} className="flex items-center gap-1.5 text-red-500">
                            <span className="font-bold">−</span> <span className="line-through">{x}</span>
                          </p>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {report.analysis?.overview && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-brand-50 to-indigo-50 border border-brand-100">
                <p className="text-sm text-ink-800 leading-relaxed">{report.analysis.overview}</p>
              </div>
            )}

            {/* 内容分类 */}
            {report.analysis?.content_categories?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-ink-900 mb-2 flex items-center gap-1.5">
                  <Target className="w-4 h-4 text-brand-500" /> 内容矩阵
                </h4>
                <div className="space-y-2">
                  {report.analysis.content_categories.map((c, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <span className="w-28 flex-shrink-0 text-ink-700">{c.name}</span>
                      <div className="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-brand-500 to-indigo-500 rounded-full"
                          style={{ width: `${Math.min(c.percentage || 0, 100)}%` }}
                        />
                      </div>
                      <span className="w-12 text-right text-xs text-ink-400">{c.percentage}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 爆款规律 */}
            {report.analysis?.hot_patterns?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-ink-900 mb-2 flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4 text-rose-500" /> 爆款规律
                </h4>
                <ul className="space-y-1.5">
                  {report.analysis.hot_patterns.map((p, i) => (
                    <li key={i} className="text-sm text-ink-600 flex gap-2">
                      <span className="text-rose-400 flex-shrink-0">◆</span>
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 发布习惯 + 互动 */}
            {report.analysis?.publishing_habits && (
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="p-4 rounded-xl border border-ink-100">
                  <h4 className="text-sm font-semibold text-ink-900 mb-2 flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-sky-500" /> 发布策略
                  </h4>
                  <p className="text-xs text-ink-500 leading-relaxed">
                    频率：{report.analysis.publishing_habits.frequency || '—'}
                    <br />
                    主平台：{report.analysis.publishing_habits.platform_focus || '—'}
                    <br />
                    最佳时段：
                    {(report.analysis.publishing_habits.best_times || []).join('、') || '—'}
                    <br />
                    分发策略：{report.analysis.publishing_habits.multi_platform_strategy || '—'}
                  </p>
                </div>
                <div className="p-4 rounded-xl border border-ink-100">
                  <h4 className="text-sm font-semibold text-ink-900 mb-2 flex items-center gap-1.5">
                    <Activity className="w-4 h-4 text-emerald-500" /> 互动分析
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-center">
                    <div>
                      <ThumbsUp className="w-4 h-4 text-brand-500 mx-auto mb-1" />
                      <p className="text-sm font-semibold">
                        {report.analysis.engagement_analysis?.avg_likes ?? '—'}
                      </p>
                      <p className="text-[10px] text-ink-400">均赞</p>
                    </div>
                    <div>
                      <MessageSquare className="w-4 h-4 text-emerald-500 mx-auto mb-1" />
                      <p className="text-sm font-semibold">
                        {report.analysis.engagement_analysis?.avg_comments ?? '—'}
                      </p>
                      <p className="text-[10px] text-ink-400">均评</p>
                    </div>
                    <div>
                      <Share2 className="w-4 h-4 text-amber-500 mx-auto mb-1" />
                      <p className="text-sm font-semibold">
                        {report.analysis.engagement_analysis?.avg_shares ?? '—'}
                      </p>
                      <p className="text-[10px] text-ink-400">均转</p>
                    </div>
                  </div>
                  <p className="text-xs text-ink-500 mt-2">
                    互动率：{report.analysis.engagement_analysis?.engagement_rate || '—'} · 趋势：
                    {report.analysis.engagement_analysis?.trend || '—'}
                  </p>
                </div>
              </div>
            )}

            {/* 优势/劣势 */}
            <div className="grid sm:grid-cols-2 gap-3">
              {(report.analysis?.competitive_advantages || []).length > 0 && (
                <div className="p-4 rounded-xl border border-emerald-100 bg-emerald-50/50">
                  <h4 className="text-sm font-semibold text-emerald-800 mb-2 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" /> 竞品优势
                  </h4>
                  <ul className="space-y-1">
                    {report.analysis.competitive_advantages.map((a, i) => (
                      <li key={i} className="text-xs text-emerald-700 flex gap-1.5">
                        <span>•</span>
                        {a}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(report.analysis?.competitive_weaknesses || []).length > 0 && (
                <div className="p-4 rounded-xl border border-amber-100 bg-amber-50/50">
                  <h4 className="text-sm font-semibold text-amber-800 mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4" /> 可攻击弱点
                  </h4>
                  <ul className="space-y-1">
                    {report.analysis.competitive_weaknesses.map((a, i) => (
                      <li key={i} className="text-xs text-amber-700 flex gap-1.5">
                        <span>•</span>
                        {a}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* 建议 */}
            {(report.analysis?.recommendations || []).length > 0 && (
              <div className="p-4 rounded-xl border border-brand-100 bg-brand-50/50">
                <h4 className="text-sm font-semibold text-brand-800 mb-2 flex items-center gap-1.5">
                  <Target className="w-4 h-4" /> 差异化切入建议
                </h4>
                <ol className="space-y-1.5">
                  {report.analysis.recommendations.map((r, i) => (
                    <li key={i} className="text-xs text-brand-700 flex gap-2">
                      <span className="w-4 h-4 rounded-full bg-brand-500 text-white text-[10px] flex items-center justify-center flex-shrink-0">
                        {i + 1}
                      </span>
                      {r}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* 雷达图数据 */}
            {radarIndicators.length > 0 && (
              <div className="p-4 rounded-xl border border-ink-100">
                <h4 className="text-sm font-semibold text-ink-900 mb-1 flex items-center gap-1.5">
                  <Radar className="w-4 h-4 text-indigo-500" />{' '}
                  {report.radar?.title || '竞品对比雷达'}
                </h4>
                {report.radar?.insight && (
                  <p className="text-xs text-ink-500 mb-3">{report.radar.insight}</p>
                )}
                <div className="space-y-2">
                  {radarIndicators.map((ind, i) => (
                    <div key={i}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-ink-600">{ind.name}</span>
                        <span className="text-ink-400 font-mono">max {ind.max}</span>
                      </div>
                      <div className="flex gap-1.5 flex-wrap">
                        {radarSeries.map((s, si) => {
                          const val = s.data?.[0]?.value?.[i] ?? 0
                          const pct = Math.min((val / (ind.max || 100)) * 100, 100)
                          return (
                            <div key={si} className="flex-1 min-w-[80px]">
                              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${si === 0 ? 'bg-gradient-to-r from-brand-500 to-indigo-500' : 'bg-gradient-to-r from-rose-400 to-orange-400'}`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <p className="text-[10px] text-ink-400 mt-0.5 truncate">
                                {s.name}: {val}
                              </p>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <PageLoading />
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={handleDelete}
        title="删除竞品？"
        message="删除后该竞品将不再出现在分析列表中，历史报告保留。"
        confirmLabel="删除"
        icon={Trash2}
      />
    </div>
  )
}
