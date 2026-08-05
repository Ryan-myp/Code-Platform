import React, { useState, useEffect, useCallback } from 'react'
import {
  Flame, Lightbulb, ShieldCheck, Clock, FolderOpen, Plus, Trash2, Pencil,
  Target, BarChart3, ExternalLink, Loader2, TrendingUp, CheckCircle2, AlertTriangle,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDateTime } from '../lib/format'
import { Button, PageHeader, Card, Empty, PageLoading, ErrorState, Badge, ConfirmDialog, Modal } from '../components/ui'

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
      <PageHeader title="内容策略" description="热点追踪 · AI 选题 · 合规预检 · 最佳发布时间 · 内容系列" />
      <div className="flex gap-2 flex-wrap">
        {[
          { key: 'hotspots', label: '热点追踪', icon: Flame },
          { key: 'compliance', label: '合规预检', icon: ShieldCheck },
          { key: 'besttime', label: '最佳时间', icon: Clock },
          { key: 'series', label: '内容系列', icon: FolderOpen },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-1.5 transition-all ${
              tab === t.key ? 'bg-brand-500 text-white shadow-soft' : 'bg-white border border-ink-200 text-ink-600 hover:border-brand-300 hover:text-brand-600'
            }`}
          >
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>
      {tab === 'hotspots' && <HotspotsTab />}
      {tab === 'compliance' && <ComplianceTab />}
      {tab === 'besttime' && <BestTimeTab />}
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

  useEffect(() => { fetchHotspots() }, [fetchHotspots])

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
            {[{ key: '', label: '全部' }, ...Object.entries(SOURCE_LABELS).map(([k, v]) => ({ key: k, label: v }))].map((s) => (
              <button
                key={s.key || 'all'}
                onClick={() => setSource(s.key)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                  source === s.key ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
        {loading ? <PageLoading /> : error ? <ErrorState message={error} onRetry={fetchHotspots} /> : hotspots.length === 0 ? (
          <Empty icon={Flame} title="暂无热点" />
        ) : (
          <div className="space-y-1.5 max-h-[520px] overflow-y-auto pr-1">
            {hotspots.map((h) => (
              <div key={`${h.source}-${h.rank}`} className="group flex items-center gap-3 p-2.5 rounded-xl hover:bg-brand-50/40 border border-transparent hover:border-brand-100 transition-all">
                <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                  h.rank <= 3 ? 'bg-gradient-to-br from-rose-500 to-orange-400 text-white' : 'bg-gray-100 text-gray-500'
                }`}>{h.rank}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-ink-800 truncate">{h.title}</p>
                  <p className="text-[11px] text-ink-400">{SOURCE_LABELS[h.source] || h.source} · 热度 {(h.heat / 10000).toFixed(1)}万</p>
                </div>
                <Button size="sm" variant="ghost" icon={Lightbulb} loading={suggesting === h.title} onClick={() => handleSuggest(h)}>
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
                    platform === p.key ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          {!suggestions ? (
            <Empty icon={Lightbulb} title="选择左侧热点，生成选题角度" description="AI 将基于热点 × 平台 × 受众生成 3-5 个差异化选题" />
          ) : (
            <div className="space-y-2.5">
              <p className="text-xs text-ink-500">
                热点：<span className="text-ink-800 font-medium">{suggestions.hotspot}</span>
                <span className="ml-2 text-ink-300">→ {PLATFORMS.find((p) => p.key === suggestions.platform)?.label}</span>
              </p>
              {(suggestions.suggestions || []).map((s, i) => (
                <div key={i} className="p-3.5 rounded-xl border border-brand-100 bg-brand-50/40">
                  <p className="text-sm font-medium text-brand-800 flex items-start gap-2">
                    <span className="w-5 h-5 rounded-full bg-brand-500 text-white text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">{i + 1}</span>
                    {s.title_direction || s.title}
                  </p>
                  {s.angle && <p className="text-xs text-ink-600 mt-1.5 ml-7">{s.angle}</p>}
                  {s.audience && <p className="text-[11px] text-ink-400 mt-1 ml-7">目标受众：{s.audience}</p>}
                </div>
              ))}
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
    if (!title.trim() && !content.trim()) { toast.error('请输入标题或正文'); return }
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
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm resize-none"
            />
          </div>
          <Button variant="primary" icon={ShieldCheck} loading={checking} onClick={handleCheck} className="w-full justify-center">
            开始扫描
          </Button>
        </div>
      </Card>

      <Card>
        <h3 className="font-semibold text-ink-900 mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-brand-500" /> 扫描结果
        </h3>
        {!result ? (
          <Empty icon={ShieldCheck} title="等待扫描" description="输入内容后点击「开始扫描」" />
        ) : (
          <div className="space-y-4">
            <div className={`p-4 rounded-xl border ${riskStyle[result.risk] || riskStyle.low}`}>
              <div className="flex items-center gap-2">
                {result.risk === 'high' ? <AlertTriangle className="w-5 h-5" /> : <CheckCircle2 className="w-5 h-5" />}
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
                    <div key={i} className="flex items-center gap-2 p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-sm">
                      <Badge color={h.level === 'high' ? 'red' : 'amber'}>{h.level === 'high' ? '高' : '中'}</Badge>
                      <span className="font-mono text-rose-600">{h.word}</span>
                      <span className="text-[11px] text-ink-400 truncate flex-1">{h.context || ''}</span>
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
                    <div key={i} className="flex items-center gap-2 text-sm p-2.5 rounded-lg bg-brand-50 border border-brand-100">
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

  useEffect(() => { fetchBestTime() }, [fetchBestTime])

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-ink-900 flex items-center gap-2">
          <Clock className="w-4 h-4 text-sky-500" /> 最佳发布时间
        </h3>
        <div className="flex gap-1.5">
          {[{ key: '', label: '全平台' }, { key: 'wechat', label: '公众号' }, { key: 'douyin', label: '抖音' }, { key: 'xhs', label: '小红书' }].map((p) => (
            <button
              key={p.key}
              onClick={() => setPlatform(p.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                platform === p.key ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      {loading ? <PageLoading /> : error ? <ErrorState message={error} onRetry={fetchBestTime} /> : (
        <div>
          <p className="text-xs text-ink-400 mb-4">{data?.note}</p>
          <div className="grid sm:grid-cols-3 gap-3">
            {(data?.top_slots || []).map((s, i) => (
              <div key={i} className={`p-4 rounded-2xl border text-center ${i === 0 ? 'border-amber-200 bg-gradient-to-b from-amber-50 to-orange-50' : 'border-ink-100 bg-white'}`}>
                <p className="text-[11px] text-ink-400 mb-1">{i === 0 ? '🏆 最佳时段' : `TOP${i + 1}`}</p>
                <p className="text-lg font-bold text-ink-900">{s.label || s.weekday}</p>
                <p className="text-xs text-ink-500 mt-1">{s.reason || `平均阅读 ${s.avg_views}`}</p>
                {s.avg_views > 0 && <p className="text-[11px] text-ink-400 mt-1">平均 {s.avg_views} 阅读 · {s.sample_count} 条样本</p>}
              </div>
            ))}
          </div>
          {data?.data_points === 0 && (
            <p className="text-xs text-amber-600 mt-4 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" /> 发布更多内容并录入效果数据后，将基于真实数据推荐
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

  useEffect(() => { fetchSeries() }, [fetchSeries])

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('请填写系列名称'); return }
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
        <Button variant="primary" size="sm" icon={Plus} onClick={() => { setEditing(null); setForm({ name: '', description: '', platform: '' }); setCreateOpen(true) }}>
          新建系列
        </Button>
      </div>
      {loading ? <PageLoading /> : error ? <ErrorState message={error} onRetry={fetchSeries} /> : series.length === 0 ? (
        <Empty icon={FolderOpen} title="还没有内容系列" description="将同主题的发布记录归入系列，沉淀栏目 IP" />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {series.map((s) => (
            <div key={s.id} className="group bg-white rounded-2xl border border-ink-100 p-4 hover:shadow-soft hover:border-brand-200 transition-all">
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center text-white font-bold">
                  {s.name?.[0] || '系'}
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => { setEditing(s.id); setForm({ name: s.name, description: s.description || '', platform: s.platform || '' }); setCreateOpen(true) }}
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
              <p className="text-xs text-ink-400 mt-1 line-clamp-2 min-h-[32px]">{s.description || '暂无描述'}</p>
              <div className="flex items-center justify-between mt-3">
                <span className="text-[11px] text-ink-400">{s.platform || '全平台'} · {s.item_count || 0} 篇</span>
                <Button size="sm" variant="ghost" icon={BarChart3} onClick={() => openStats(s.id)}>效果</Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 新建/编辑系列 */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title={editing ? '编辑系列' : '新建系列'}>
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
                    form.platform === p ? 'bg-brand-500 text-white shadow-soft' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p === '' ? '全平台' : PLATFORMS.find((x) => x.key === p)?.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button>
          <Button variant="primary" icon={editing ? Pencil : Plus} loading={saving} onClick={handleSave}>
            {editing ? '保存修改' : '创建'}
          </Button>
        </div>
      </Modal>

      {/* 系列效果 */}
      <Modal open={statsOpen} onClose={() => setStatsOpen(false)} title="系列效果汇总" size="lg">
        {stats ? (
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: '总篇数', value: stats.item_count || 0 },
                { label: '总阅读', value: stats.total_views || 0 },
                { label: '总互动', value: (stats.total_likes || 0) + (stats.total_comments || 0) },
              ].map((s, i) => (
                <div key={i} className="p-4 rounded-2xl bg-gradient-to-br from-brand-50 to-indigo-50 border border-brand-100 text-center">
                  <p className="text-2xl font-bold text-brand-700">{s.value}</p>
                  <p className="text-xs text-ink-500 mt-1">{s.label}</p>
                </div>
              ))}
            </div>
            {(stats.items || []).length === 0 ? (
              <Empty icon={BarChart3} title="系列暂无内容" description="在发布中心将记录加入系列即可统计" />
            ) : (
              <div className="space-y-2">
                {(stats.items || []).map((it, i) => (
                  <div key={it.id || i} className="flex items-center gap-3 p-3 rounded-xl border border-ink-100 text-sm">
                    <span className="w-6 h-6 rounded-lg bg-gray-100 text-gray-500 text-xs flex items-center justify-center flex-shrink-0">{it.seq || i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-ink-800">{it.title || it.record_id}</p>
                      <p className="text-[11px] text-ink-400">{it.platform || '—'} · {it.pub_at ? formatDateTime(it.pub_at) : ''}</p>
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
        ) : <PageLoading />}
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
