import React, { useState, useEffect, useCallback } from 'react'
import useToolHistory from '../hooks/useToolHistory'
import HistoryPanel from '../components/HistoryPanel'
import {
  Flame,
  Lightbulb,
  ShieldCheck,
  Clock,
  FolderOpen,
  Plus,
  Trash2,
  Pencil,
  Target,
  BarChart3,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  Copy,
  CalendarDays,
  BookMarked,
  ChevronLeft,
  ChevronRight,
  Search,
  Archive,
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

const SOURCE_LABELS = { weibo: '微博热搜', zhihu: '知乎热榜', '36kr': '36氪' }
const PLATFORMS = [
  { key: 'wechat', label: '微信公众号' },
  { key: 'douyin', label: '抖音' },
  { key: 'kuaishou', label: '快手' },
]

export default function ContentStrategyPage() {
  const [tab, setTab] = useState('hotspots')

  return (
    <div className="space-y-6">
      <PageHeader
        title="内容策略"
        description="热点追踪 · AI 选题 · 合规预检 · 最佳时间 · 内容日历 · 主题库 · 内容系列"
      />
      <div className="flex gap-2 flex-wrap">
        {[
          { key: 'hotspots', label: '热点追踪', icon: Flame },
          { key: 'compliance', label: '合规预检', icon: ShieldCheck },
          { key: 'besttime', label: '最佳时间', icon: Clock },
          { key: 'calendar', label: '内容日历', icon: CalendarDays },
          { key: 'topics', label: '主题库', icon: BookMarked },
          { key: 'series', label: '内容系列', icon: FolderOpen },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-1.5 transition-all ${
              tab === t.key
                ? 'bg-brand-500 text-white shadow-soft'
                : 'bg-white border border-ink-200 text-ink-600 hover:border-brand-300 hover:text-brand-600'
            }`}
          >
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>
      {tab === 'hotspots' && <HotspotsTab />}
      {tab === 'compliance' && <ComplianceTab />}
      {tab === 'besttime' && <BestTimeTab />}
      {tab === 'calendar' && <CalendarTab />}
      {tab === 'topics' && <TopicsTab />}
      {tab === 'series' && <SeriesTab />}
    </div>
  )
}

/* ── 热点追踪 + AI 选题 ── */
function HotspotsTab() {
  const toast = useToast()
  const [source, setSource] = useState('')
  const [hotspots, setHotspots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [suggesting, setSuggesting] = useState(null) // 正在选题的热点标题
  const [suggestions, setSuggestions] = useState(null)
  const { history: topicHistory, add: addTopicHistory, remove: removeTopicHistory, clear: clearTopicHistory } =
    useToolHistory('content_strategy_topics_v1', 20)
  const [platform, setPlatform] = useState('wechat')

  const fetchHotspots = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/strategy/hotspots', { params: source ? { source } : {} })
      setHotspots(res.data?.items || [])
      setError(null)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [source])

  useEffect(() => {
    fetchHotspots()
  }, [fetchHotspots])

  const handleSuggest = async (hotspot) => {
    setSuggesting(hotspot.title)
    setSuggestions(null)
    try {
      const res = await api.post('/api/strategy/topic-suggest', {
        hotspot: hotspot.title,
        platform,
        source: hotspot.source,
      })
      setSuggestions(res.data)
      addTopicHistory({ type: '选题', hotspot: res.data?.hotspot, platform: res.data?.platform, content: `${res.data?.hotspot} → ${res.data?.platform}` })
      toast.success('AI 选题完成')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSuggesting(null)
    }
  }

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <Flame className="w-4 h-4 text-rose-500" /> 实时热点
            <Badge color="rose">{hotspots.length}</Badge>
          </h3>
          <div className="flex gap-1.5">
            {[
              { key: '', label: '全部' },
              ...Object.entries(SOURCE_LABELS).map(([k, v]) => ({ key: k, label: v })),
            ].map((s) => (
              <button
                key={s.key || 'all'}
                onClick={() => setSource(s.key)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                  source === s.key
                    ? 'bg-brand-500 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
        {loading ? (
          <PageLoading />
        ) : error ? (
          <ErrorState message={error} onRetry={fetchHotspots} />
        ) : hotspots.length === 0 ? (
          <Empty icon={Flame} title="暂无热点" />
        ) : (
          <div className="space-y-1.5 max-h-[520px] overflow-y-auto pr-1">
            {hotspots.map((h) => (
              <div
                key={`${h.source}-${h.rank}`}
                className="group flex items-center gap-3 p-2.5 rounded-xl hover:bg-brand-50/40 border border-transparent hover:border-brand-100 transition-all"
              >
                <span
                  className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                    h.rank <= 3
                      ? 'bg-gradient-to-br from-rose-500 to-orange-400 text-white'
                      : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {h.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-ink-800 truncate">{h.title}</p>
                  <p className="text-[11px] text-ink-400">
                    {SOURCE_LABELS[h.source] || h.source} · 热度 {(h.heat / 10000).toFixed(1)}万
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Lightbulb}
                  loading={suggesting === h.title}
                  onClick={() => handleSuggest(h)}
                >
                  选题
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="space-y-4">
        <Card>
          <h3 className="font-semibold text-ink-900 mb-3 flex items-center gap-2">
            <Target className="w-4 h-4 text-brand-500" /> AI 选题建议
          </h3>
          <div className="mb-3">
            <p className="text-xs text-ink-400 mb-1.5">目标平台</p>
            <div className="flex gap-1.5">
              {PLATFORMS.map((p) => (
                <button
                  key={p.key}
                  onClick={() => setPlatform(p.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    platform === p.key
                      ? 'bg-brand-500 text-white shadow-soft'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          {!suggestions ? (
            <Empty
              icon={Lightbulb}
              title="选择左侧热点，生成选题角度"
              description="AI 将基于热点 × 平台 × 受众生成 3-5 个差异化选题"
            />
          ) : (
            <div className="space-y-2.5">
              <p className="text-xs text-ink-500">
                热点：<span className="text-ink-800 font-medium">{suggestions.hotspot}</span>
                <span className="ml-2 text-ink-300">
                  → {PLATFORMS.find((p) => p.key === suggestions.platform)?.label}
                </span>
              </p>
              {(suggestions.suggestions || []).map((s, i) => (
                <div key={i} className="p-3.5 rounded-xl border border-brand-100 bg-brand-50/40">
                  <p className="text-sm font-medium text-brand-800 flex items-start gap-2">
                    <span className="w-5 h-5 rounded-full bg-brand-500 text-white text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    {s.title_direction || s.title}
                  </p>
                  {s.angle && <p className="text-xs text-ink-600 mt-1.5 ml-7">{s.angle}</p>}
                  {s.audience && (
                    <p className="text-[11px] text-ink-400 mt-1 ml-7">目标受众：{s.audience}</p>
                  )}
                </div>
              ))}
            </div>
          )}
          {topicHistory.length > 0 && (
            <div className="mt-3">
              <HistoryPanel
                history={topicHistory}
                onReuse={(item) => {
                  toast.success('已选择该选题热点')
                }}
                onRemove={removeTopicHistory}
                onClear={clearTopicHistory}
                title="选题历史"
              />
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

/* ── 合规预检 ── */
function ComplianceTab() {
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState(null)

  const handleCheck = async () => {
    if (!title.trim() && !content.trim()) {
      toast.error('请输入标题或正文')
      return
    }
    setChecking(true)
    try {
      const res = await api.post('/api/strategy/compliance-check', { title, content })
      setResult(res.data)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setChecking(false)
    }
  }

  // 扫描结果 → Markdown（复制/分享复用）
  const buildResultMd = (r) => {
    if (!r) return ''
    const lines = [
      '# 内容合规扫描结果',
      '',
      `- 风险等级：${r.risk_label || r.risk || '-'}`,
      `- 命中总数：${r.total_hits ?? 0} 处`,
      '',
      r.message || '',
      '',
    ]
    if (r.hits?.length) {
      lines.push('## 命中明细', '')
      r.hits.forEach((h) => {
        lines.push(`- [${h.level === 'high' ? '高' : '中'}] ${h.word}${h.context ? `（上下文：${h.context}）` : ''}`)
      })
      lines.push('')
    }
    if (r.suggestions?.length) {
      lines.push('## 修改建议', '')
      r.suggestions.forEach((s) => lines.push(`- ${s}`))
      lines.push('')
    }
    lines.push('---', `由小团智能平台 AI 内容策略生成 · ${new Date().toLocaleString()}`)
    return lines.join('\n')
  }

  const riskStyle = {
    safe: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    low: 'border-amber-200 bg-amber-50 text-amber-800',
    medium: 'border-orange-200 bg-orange-50 text-orange-800',
    high: 'border-red-200 bg-red-50 text-red-800',
  }

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <Card>
        <h3 className="font-semibold text-ink-900 mb-3 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-500" /> 内容合规扫描
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">标题</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="输入文章/视频标题"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">正文</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={10}
              placeholder="粘贴正文内容，扫描敏感词 / 违禁词 / 广告法禁用词…"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !checking) {
                  e.preventDefault()
                  handleCheck()
                }
              }}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm resize-none"
            />
          </div>
          <Button
            variant="primary"
            icon={ShieldCheck}
            loading={checking}
            onClick={handleCheck}
            className="w-full justify-center"
          >
            开始扫描
          </Button>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand-500" /> 扫描结果
          </h3>
          {result && (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                icon={Copy}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(buildResultMd(result))
                    toast.success('扫描结果已复制')
                  } catch {
                    toast.error('复制失败，请手动选择复制')
                  }
                }}
              >
                复制
              </Button>
              <ShareButton
                content={buildResultMd(result)}
                title="内容安全扫描结果"
                contentType="content_strategy"
              />
            </div>
          )}
        </div>
        {!result ? (
          <Empty icon={ShieldCheck} title="等待扫描" description="输入内容后点击「开始扫描」" />
        ) : (
          <div className="space-y-4">
            <div className={`p-4 rounded-xl border ${riskStyle[result.risk] || riskStyle.low}`}>
              <div className="flex items-center gap-2">
                {result.risk === 'high' ? (
                  <AlertTriangle className="w-5 h-5" />
                ) : (
                  <CheckCircle2 className="w-5 h-5" />
                )}
                <span className="font-semibold">{result.risk_label}</span>
                {result.total_hits > 0 && <Badge color="rose">{result.total_hits} 处</Badge>}
              </div>
              <p className="text-xs mt-1.5 opacity-80">{result.message}</p>
            </div>

            {(result.hits || []).length > 0 && (
              <div>
                <p className="text-xs font-medium text-ink-500 mb-2">命中明细</p>
                <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                  {result.hits.map((h, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-sm"
                    >
                      <Badge color={h.level === 'high' ? 'red' : 'amber'}>
                        {h.level === 'high' ? '高' : '中'}
                      </Badge>
                      <span className="font-mono text-rose-600">{h.word}</span>
                      <span className="text-[11px] text-ink-400 truncate flex-1">
                        {h.context || ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(result.suggestions || []).length > 0 && (
              <div>
                <p className="text-xs font-medium text-ink-500 mb-2">替换建议</p>
                <div className="space-y-1.5">
                  {result.suggestions.map((s, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 text-sm p-2.5 rounded-lg bg-brand-50 border border-brand-100"
                    >
                      <span className="text-rose-500 line-through font-mono">{s.original}</span>
                      <span className="text-ink-300">→</span>
                      <span className="text-emerald-600 font-mono">{s.suggest}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

/* ── 最佳发布时间 ── */
function BestTimeTab() {
  const [platform, setPlatform] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchBestTime = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/strategy/best-time', { params: platform ? { platform } : {} })
      setData(res.data)
      setError(null)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [platform])

  useEffect(() => {
    fetchBestTime()
  }, [fetchBestTime])

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-ink-900 flex items-center gap-2">
          <Clock className="w-4 h-4 text-sky-500" /> 最佳发布时间
        </h3>
        <div className="flex gap-1.5">
          {[
            { key: '', label: '全平台' },
            { key: 'wechat', label: '公众号' },
            { key: 'douyin', label: '抖音' },
            { key: 'xhs', label: '小红书' },
          ].map((p) => (
            <button
              key={p.key}
              onClick={() => setPlatform(p.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                platform === p.key
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      {loading ? (
        <PageLoading />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchBestTime} />
      ) : (
        <div>
          <p className="text-xs text-ink-400 mb-4">{data?.note}</p>
          <div className="grid sm:grid-cols-3 gap-3">
            {(data?.top_slots || []).map((s, i) => (
              <div
                key={i}
                className={`p-4 rounded-2xl border text-center ${i === 0 ? 'border-amber-200 bg-gradient-to-b from-amber-50 to-orange-50' : 'border-ink-100 bg-white'}`}
              >
                <p className="text-[11px] text-ink-400 mb-1">
                  {i === 0 ? '🏆 最佳时段' : `TOP${i + 1}`}
                </p>
                <p className="text-lg font-bold text-ink-900">{s.label || s.weekday}</p>
                <p className="text-xs text-ink-500 mt-1">{s.reason || `平均阅读 ${s.avg_views}`}</p>
                {s.avg_views > 0 && (
                  <p className="text-[11px] text-ink-400 mt-1">
                    平均 {s.avg_views} 阅读 · {s.sample_count} 条样本
                  </p>
                )}
              </div>
            ))}
          </div>
          {data?.data_points === 0 && (
            <p className="text-xs text-amber-600 mt-4 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" />{' '}
              发布更多内容并录入效果数据后，将基于真实数据推荐
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

/* ── 内容系列管理 ── */
function SeriesTab() {
  const toast = useToast()
  const [series, setSeries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', platform: '' })
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [stats, setStats] = useState(null) // 当前查看的系列统计
  const [statsOpen, setStatsOpen] = useState(false)

  const fetchSeries = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/strategy/series')
      setSeries(res.data || [])
      setError(null)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSeries()
  }, [fetchSeries])

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('请填写系列名称')
      return
    }
    setSaving(true)
    try {
      if (editing) {
        await api.put(`/api/strategy/series/${editing}`, form)
        toast.success('系列已更新')
      } else {
        await api.post('/api/strategy/series', form)
        toast.success('系列已创建')
      }
      setCreateOpen(false)
      setEditing(null)
      setForm({ name: '', description: '', platform: '' })
      fetchSeries()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      await api.delete(`/api/strategy/series/${deleting}`)
      toast.success('系列已删除')
      setDeleting(null)
      fetchSeries()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const openStats = async (sid) => {
    try {
      const res = await api.get(`/api/strategy/series/${sid}/stats`)
      setStats(res.data)
      setStatsOpen(true)
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-ink-900 flex items-center gap-2">
          <FolderOpen className="w-4 h-4 text-brand-500" /> 内容系列 / 专栏
          <Badge color="brand">{series.length}</Badge>
        </h3>
        <Button
          variant="primary"
          size="sm"
          icon={Plus}
          onClick={() => {
            setEditing(null)
            setForm({ name: '', description: '', platform: '' })
            setCreateOpen(true)
          }}
        >
          新建系列
        </Button>
      </div>
      {loading ? (
        <PageLoading />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchSeries} />
      ) : series.length === 0 ? (
        <Empty
          icon={FolderOpen}
          title="还没有内容系列"
          description="将同主题的发布记录归入系列，沉淀栏目 IP"
        />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {series.map((s) => (
            <div
              key={s.id}
              className="group bg-white rounded-2xl border border-ink-100 p-4 hover:shadow-soft hover:border-brand-200 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center text-white font-bold">
                  {s.name?.[0] || '系'}
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => {
                      setEditing(s.id)
                      setForm({
                        name: s.name,
                        description: s.description || '',
                        platform: s.platform || '',
                      })
                      setCreateOpen(true)
                    }}
                    className="p-1.5 rounded-lg text-ink-300 hover:text-brand-500 hover:bg-brand-50 transition-colors"
                    title="编辑"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setDeleting(s.id)}
                    className="p-1.5 rounded-lg text-ink-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <p className="font-medium text-ink-900 mt-3 truncate">{s.name}</p>
              <p className="text-xs text-ink-400 mt-1 line-clamp-2 min-h-[32px]">
                {s.description || '暂无描述'}
              </p>
              <div className="flex items-center justify-between mt-3">
                <span className="text-[11px] text-ink-400">
                  {s.platform || '全平台'} · {s.item_count || 0} 篇
                </span>
                <Button size="sm" variant="ghost" icon={BarChart3} onClick={() => openStats(s.id)}>
                  效果
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 新建/编辑系列 */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title={editing ? '编辑系列' : '新建系列'}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">系列名称 *</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：AI 实战专栏"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              placeholder="系列定位、更新计划…"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm resize-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">平台</label>
            <div className="flex flex-wrap gap-1.5">
              {['', 'wechat', 'douyin', 'kuaishou'].map((p) => (
                <button
                  key={p || 'all'}
                  onClick={() => setForm({ ...form, platform: p })}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    form.platform === p
                      ? 'bg-brand-500 text-white shadow-soft'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p === '' ? '全平台' : PLATFORMS.find((x) => x.key === p)?.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={() => setCreateOpen(false)}>
            取消
          </Button>
          <Button
            variant="primary"
            icon={editing ? Pencil : Plus}
            loading={saving}
            onClick={handleSave}
          >
            {editing ? '保存修改' : '创建'}
          </Button>
        </div>
      </Modal>

      {/* 系列效果 */}
      <Modal open={statsOpen} onClose={() => setStatsOpen(false)} title="系列效果汇总" size="lg">
        {stats ? (
          <div className="space-y-5">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { label: '总篇数', value: stats.item_count || 0 },
                { label: '总阅读', value: stats.total_views || 0 },
                { label: '总互动', value: (stats.total_likes || 0) + (stats.total_comments || 0) },
              ].map((s, i) => (
                <div
                  key={i}
                  className="p-4 rounded-2xl bg-gradient-to-br from-brand-50 to-indigo-50 border border-brand-100 text-center"
                >
                  <p className="text-2xl font-bold text-brand-700">{s.value}</p>
                  <p className="text-xs text-ink-500 mt-1">{s.label}</p>
                </div>
              ))}
            </div>
            {(stats.items || []).length === 0 ? (
              <Empty
                icon={BarChart3}
                title="系列暂无内容"
                description="在发布中心将记录加入系列即可统计"
              />
            ) : (
              <div className="space-y-2">
                {(stats.items || []).map((it, i) => (
                  <div
                    key={it.id || i}
                    className="flex items-center gap-3 p-3 rounded-xl border border-ink-100 text-sm"
                  >
                    <span className="w-6 h-6 rounded-lg bg-gray-100 text-gray-500 text-xs flex items-center justify-center flex-shrink-0">
                      {it.seq || i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-ink-800">{it.title || it.record_id}</p>
                      <p className="text-[11px] text-ink-400">
                        {it.platform || '—'} · {it.pub_at ? formatDateTime(it.pub_at) : ''}
                      </p>
                    </div>
                    <div className="text-xs text-ink-400 flex gap-3 flex-shrink-0">
                      <span>👁 {it.views || 0}</span>
                      <span>👍 {it.likes || 0}</span>
                      <span>💬 {it.comments || 0}</span>
                    </div>
                  </div>
                ))}
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
        title="删除系列？"
        message="删除后系列内的条目将一并移除，发布记录本身不受影响。"
        confirmLabel="删除"
        icon={Trash2}
      />
    </Card>
  )
}

/* ── 内容日历（排期 + 已发布聚合月历） ── */
const CAL_WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']
const CAL_CONTENT_LABELS = { article: '文章', image: '图片', video: '视频', audio: '音频' }
const CAL_STATUS_LABELS = { pending: '待发布', published: '已发布', cancelled: '已取消', failed: '失败' }

function CalendarTab() {
  const nowDate = new Date()
  const [month, setMonth] = useState(
    `${nowDate.getFullYear()}-${String(nowDate.getMonth() + 1).padStart(2, '0')}`
  )
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null) // 选中的日期明细

  const fetchCalendar = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/strategy/calendar', { params: { month } })
      setData(res.data)
      setError(null)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [month])

  useEffect(() => {
    fetchCalendar()
  }, [fetchCalendar])

  const shiftMonth = (delta) => {
    const [y, m] = month.split('-').map(Number)
    const d = new Date(y, m - 1 + delta, 1)
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }

  const todayStr = `${nowDate.getFullYear()}-${String(nowDate.getMonth() + 1).padStart(2, '0')}-${String(
    nowDate.getDate()
  ).padStart(2, '0')}`
  const days = data?.days || {}
  const cells = []
  if (data) {
    for (let i = 0; i < (data.first_weekday || 0); i += 1) cells.push('blank')
    for (let d = 1; d <= (data.day_count || 0); d += 1) {
      cells.push(`${data.month}-${String(d).padStart(2, '0')}`)
    }
  }
  const selectedDay = selected ? days[selected] : null

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-ink-900 flex items-center gap-2">
          <CalendarDays className="w-4 h-4 text-brand-500" /> 内容日历
          <Badge color="amber">{data?.summary?.scheduled || 0} 排期</Badge>
          <Badge color="green">{data?.summary?.published || 0} 已发布</Badge>
        </h3>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => shiftMonth(-1)}
            className="p-2 rounded-lg border border-ink-200 text-ink-500 hover:border-brand-300 hover:text-brand-600 transition-all"
            title="上一月"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm font-semibold text-ink-800 w-24 text-center">
            {data ? `${Number(data.month.slice(0, 4))}年${Number(data.month.slice(5))}月` : month}
          </span>
          <button
            onClick={() => shiftMonth(1)}
            className="p-2 rounded-lg border border-ink-200 text-ink-500 hover:border-brand-300 hover:text-brand-600 transition-all"
            title="下一月"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
      {loading ? (
        <PageLoading />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchCalendar} />
      ) : (
        <div>
          <div className="grid grid-cols-7 gap-1.5 mb-1.5">
            {CAL_WEEKDAYS.map((w, i) => (
              <div
                key={w}
                className={`text-center text-[11px] font-medium py-1 ${i >= 5 ? 'text-rose-400' : 'text-ink-400'}`}
              >
                周{w}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {cells.map((c, i) =>
              c === 'blank' ? (
                <div key={`blank-${i}`} />
              ) : (
                <button
                  key={c}
                  onClick={() => setSelected(c)}
                  className={`min-h-[78px] rounded-xl border p-1.5 text-left transition-all ${
                    days[c]?.total > 0
                      ? 'border-brand-200 bg-brand-50/40 hover:border-brand-400 hover:shadow-soft'
                      : 'border-ink-100 bg-white hover:border-brand-300'
                  } ${c === todayStr ? 'ring-2 ring-brand-400/60' : ''}`}
                >
                  <span className={`text-xs font-semibold ${c === todayStr ? 'text-brand-600' : 'text-ink-600'}`}>
                    {Number(c.slice(8))}
                  </span>
                  {days[c]?.total > 0 && (
                    <div className="mt-1 space-y-0.5">
                      {days[c].schedules.length > 0 && (
                        <span className="flex items-center gap-1 text-[10px] text-amber-600 bg-amber-50 rounded-md px-1 py-0.5">
                          <Clock className="w-3 h-3" /> 排期 {days[c].schedules.length}
                        </span>
                      )}
                      {days[c].records.length > 0 && (
                        <span className="flex items-center gap-1 text-[10px] text-emerald-600 bg-emerald-50 rounded-md px-1 py-0.5">
                          <CheckCircle2 className="w-3 h-3" /> 发布 {days[c].records.length}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              )
            )}
          </div>
          {data && cells.filter((c) => c !== 'blank').length > 0 && Object.keys(days).length === 0 && (
            <p className="text-xs text-ink-400 mt-4 text-center">
              本月暂无排期与发布，可在发布中心创建排期后回到这里查看
            </p>
          )}
        </div>
      )}

      {/* 当日明细 */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `${selected} 内容明细` : ''}
        size="lg"
      >
        {selectedDay ? (
          <div className="space-y-4">
            {selectedDay.schedules.length === 0 && selectedDay.records.length === 0 && (
              <Empty icon={CalendarDays} title="当日无内容" description="可在发布中心创建排期或发布内容" />
            )}
            {selectedDay.schedules.length > 0 && (
              <div>
                <p className="text-xs font-medium text-ink-500 mb-2 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-amber-500" /> 排期计划
                </p>
                <div className="space-y-1.5">
                  {selectedDay.schedules.map((s) => (
                    <div key={s.id} className="flex items-center gap-3 p-2.5 rounded-xl border border-ink-100 text-sm">
                      <Badge color={s.status === 'published' ? 'green' : s.status === 'cancelled' ? 'gray' : 'amber'}>
                        {CAL_STATUS_LABELS[s.status] || s.status}
                      </Badge>
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-ink-800">{s.title}</p>
                        <p className="text-[11px] text-ink-400">
                          {s.time} · {s.platform || '—'} · {CAL_CONTENT_LABELS[s.content_type] || s.content_type || '—'}
                        </p>
                      </div>
                      {(s.topics || []).length > 0 && (
                        <div className="flex gap-1 flex-shrink-0">
                          {s.topics.slice(0, 3).map((t) => (
                            <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-brand-50 text-brand-600">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {selectedDay.records.length > 0 && (
              <div>
                <p className="text-xs font-medium text-ink-500 mb-2 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> 已发布内容
                </p>
                <div className="space-y-1.5">
                  {selectedDay.records.map((r) => (
                    <div key={r.id} className="flex items-center gap-3 p-2.5 rounded-xl border border-ink-100 text-sm">
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-ink-800">{r.title}</p>
                        <p className="text-[11px] text-ink-400">
                          {r.time} · {r.platform || '—'} · {CAL_CONTENT_LABELS[r.content_type] || r.content_type || '—'}
                        </p>
                      </div>
                      <div className="text-xs text-ink-400 flex gap-3 flex-shrink-0">
                        <span>👁 {r.views || 0}</span>
                        <span>👍 {r.likes || 0}</span>
                        <span>💬 {r.comments || 0}</span>
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
    </Card>
  )
}

/* ── 主题库（选题方向沉淀 + 标签筛选） ── */
const PRIORITY_META = [
  { value: 0, label: 'P0', desc: '本周必做', cls: 'bg-red-500 text-white' },
  { value: 1, label: 'P1', desc: '近期重点', cls: 'bg-orange-500 text-white' },
  { value: 2, label: 'P2', desc: '常规规划', cls: 'bg-sky-500 text-white' },
  { value: 3, label: 'P3', desc: '灵感备选', cls: 'bg-gray-400 text-white' },
]
const TOPIC_CATEGORIES_FALLBACK = ['干货', '热点', '案例拆解', '教程', '观点', '清单', '其他']
const EMPTY_TOPIC_FORM = { name: '', description: '', category: '', tags: '', goal: '', priority: 2 }

function TopicsTab() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tag, setTag] = useState('')
  const [category, setCategory] = useState('')
  const [keyword, setKeyword] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [form, setForm] = useState(EMPTY_TOPIC_FORM)

  const fetchTopics = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (tag) params.tag = tag
      if (category) params.category = category
      if (keyword.trim()) params.keyword = keyword.trim()
      const res = await api.get('/api/strategy/topics', { params })
      setData(res.data)
      setError(null)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [tag, category, keyword])

  useEffect(() => {
    fetchTopics()
  }, [fetchTopics])

  const parseTags = (s) =>
    (s || '')
      .split(/[,，]/)
      .map((x) => x.trim())
      .filter(Boolean)

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('请填写主题名称')
      return
    }
    setSaving(true)
    const payload = { ...form, tags: parseTags(form.tags) }
    try {
      if (editing) {
        await api.put(`/api/strategy/topics/${editing}`, payload)
        toast.success('主题已更新')
      } else {
        await api.post('/api/strategy/topics', payload)
        toast.success('主题已创建')
      }
      setOpen(false)
      setEditing(null)
      setForm(EMPTY_TOPIC_FORM)
      fetchTopics()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      await api.delete(`/api/strategy/topics/${deleting}`)
      toast.success('主题已删除')
      setDeleting(null)
      fetchTopics()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const categories = data?.categories || TOPIC_CATEGORIES_FALLBACK
  const items = data?.items || []

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-300" />
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索主题名称 / 描述…"
              className="w-full pl-9 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <Button
            variant="primary"
            icon={Plus}
            onClick={() => {
              setEditing(null)
              setForm(EMPTY_TOPIC_FORM)
              setOpen(true)
            }}
          >
            新建主题
          </Button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          <button
            onClick={() => setCategory('')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              !category ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            全部分类
          </button>
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(category === c ? '' : c)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                category === c ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        {(data?.tags || []).length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2 items-center">
            <button
              onClick={() => setTag('')}
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                !tag ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <Archive className="w-3.5 h-3.5" /> 全部标签
            </button>
            {data.tags.map((t) => (
              <button
                key={t.tag}
                onClick={() => setTag(tag === t.tag ? '' : t.tag)}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  tag === t.tag ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                #{t.tag}
                <span className={tag === t.tag ? 'opacity-80' : 'text-ink-400'}>{t.count}</span>
              </button>
            ))}
          </div>
        )}
      </Card>

      {loading ? (
        <PageLoading />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchTopics} />
      ) : items.length === 0 ? (
        <Empty
          icon={BookMarked}
          title={data?.total ? '没有匹配的主题' : '主题库还是空的'}
          description={
            data?.total ? '调整筛选条件，或清除标签 / 分类筛选' : '沉淀选题方向与内容素材，用标签高效筛选复用'
          }
        />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {items.map((t) => {
            const pm = PRIORITY_META.find((p) => p.value === t.priority) || PRIORITY_META[3]
            return (
              <div
                key={t.id}
                className="group bg-white rounded-2xl border border-ink-100 p-4 hover:shadow-soft hover:border-brand-200 transition-all"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-bold flex-shrink-0 ${pm.cls}`} title={pm.desc}>
                      {pm.label}
                    </span>
                    <p className="font-medium text-ink-900 truncate">{t.name}</p>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                    <button
                      onClick={() => {
                        setEditing(t.id)
                        setForm({
                          name: t.name,
                          description: t.description || '',
                          category: t.category || '',
                          tags: (t.tags || []).join(', '),
                          goal: t.goal || '',
                          priority: t.priority ?? 2,
                        })
                        setOpen(true)
                      }}
                      className="p-1.5 rounded-lg text-ink-300 hover:text-brand-500 hover:bg-brand-50 transition-colors"
                      title="编辑"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setDeleting(t.id)}
                      className="p-1.5 rounded-lg text-ink-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="删除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                {t.category && (
                  <div className="mt-2">
                    <Badge color="brand">{t.category}</Badge>
                  </div>
                )}
                <p className="text-xs text-ink-400 mt-2 line-clamp-2 min-h-[32px]">{t.description || '暂无描述'}</p>
                {(t.tags || []).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2.5">
                    {t.tags.map((tg) => (
                      <span
                        key={tg}
                        className="text-[10px] px-2 py-0.5 rounded-full bg-brand-50 text-brand-600 border border-brand-100"
                      >
                        #{tg}
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between mt-3 pt-2 border-t border-ink-50">
                  <span className="text-[11px] text-ink-500 truncate">{t.goal || '—'}</span>
                  <span className="text-[11px] text-ink-300 flex-shrink-0">
                    {t.created_at ? formatDateTime(t.created_at).slice(0, 10) : ''}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 新建 / 编辑主题 */}
      <Modal open={open} onClose={() => setOpen(false)} title={editing ? '编辑主题' : '新建主题'} size="lg">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">主题名称 *</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：AI 工具提效实操"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">分类</label>
            <div className="flex flex-wrap gap-1.5">
              <button
                onClick={() => setForm({ ...form, category: '' })}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  !form.category ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                未分类
              </button>
              {categories.map((c) => (
                <button
                  key={c}
                  onClick={() => setForm({ ...form, category: c })}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    form.category === c ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">标签（逗号分隔）</label>
            <input
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
              placeholder="AI, 效率, 涨粉"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">优先级</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {PRIORITY_META.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setForm({ ...form, priority: p.value })}
                  className={`px-2 py-2 rounded-xl text-xs font-medium transition-all border ${
                    form.priority === p.value
                      ? 'border-brand-400 bg-brand-50 text-brand-700 shadow-soft'
                      : 'border-ink-100 bg-white text-ink-500 hover:border-brand-300'
                  }`}
                >
                  <span className={`inline-block px-1.5 py-0.5 rounded-md font-bold ${p.cls}`}>{p.label}</span>
                  <span className="block mt-1 text-[10px] text-ink-400">{p.desc}</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">内容目标</label>
            <input
              value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })}
              placeholder="受众与转化目的，如：面向新媒体运营涨粉"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              placeholder="选题思路、素材方向…"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm resize-none"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button variant="primary" icon={editing ? Pencil : Plus} loading={saving} onClick={handleSave}>
            {editing ? '保存修改' : '创建'}
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={handleDelete}
        title="删除主题？"
        message="删除后该选题方向将不可恢复，请谨慎操作。"
        confirmLabel="删除"
        icon={Trash2}
      />
    </div>
  )
}
