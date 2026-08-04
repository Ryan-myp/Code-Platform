import React, { useState, useEffect } from 'react'
import {
  Sparkles, TrendingUp, Wand2, FileText, CheckSquare, Square, Trash2,
  Edit3, CalendarPlus, Play, Clock, BarChart3, MessageSquare, Eye,
  ThumbsUp, MessageCircle, Share2, UserPlus, Save, RefreshCw, X, Plus, Send,
} from 'lucide-react'
import { Card, Button, Badge, Empty, PageHeader, Modal } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PLATFORMS = [
  { value: 'wechat', label: '微信公众号', color: 'from-emerald-500 to-green-600', border: 'border-emerald-200 bg-emerald-50' },
  { value: 'douyin', label: '抖音', color: 'from-gray-700 to-gray-900', border: 'border-gray-200 bg-gray-50' },
  { value: 'kuaishou', label: '快手', color: 'from-orange-500 to-amber-600', border: 'border-orange-200 bg-orange-50' },
]

const TABS = [
  { key: 'variants', label: '变体工坊', icon: Wand2 },
  { key: 'metrics', label: '效果追踪', icon: BarChart3 },
  { key: 'review', label: 'AI 复盘', icon: Sparkles },
]

export default function GrowthPage() {
  const toast = useToast()
  const [tab, setTab] = useState('variants')

  // ── 变体工坊状态 ──
  const [theme, setTheme] = useState('')
  const [platform, setPlatform] = useState('wechat')
  const [count, setCount] = useState(5)
  const [generating, setGenerating] = useState(false)
  const [variants, setVariants] = useState([])
  const [varFilter, setVarFilter] = useState('')
  const [editId, setEditId] = useState('')
  const [editForm, setEditForm] = useState({ title: '', content: '', topics: [], cover_style: '', topicInput: '' })

  // 批量排期
  const [schedModal, setSchedModal] = useState(false)
  const [schedInterval, setSchedInterval] = useState(60)
  const [schedStart, setSchedStart] = useState('')
  const [schedLoading, setSchedLoading] = useState(false)

  // ── 效果追踪状态 ──
  const [dashboard, setDashboard] = useState(null)
  const [metPlatform, setMetPlatform] = useState('')
  const [entryRecordId, setEntryRecordId] = useState('')
  const [entryForm, setEntryForm] = useState({ views: 0, likes: 0, comments: 0, shares: 0, followers_gained: 0 })
  const [entrySaving, setEntrySaving] = useState(false)

  // ── AI 复盘状态 ──
  const [reviewPlatform, setReviewPlatform] = useState('')
  const [reviewDays, setReviewDays] = useState(30)
  const [reviewing, setReviewing] = useState(false)
  const [report, setReport] = useState(null)

  useEffect(() => { if (tab === 'variants') loadVariants() }, [tab, varFilter])
  useEffect(() => { if (tab === 'metrics') loadDashboard() }, [tab, metPlatform])

  const loadVariants = async () => {
    try {
      const params = new URLSearchParams()
      if (varFilter) params.set('platform', varFilter)
      const res = await api.get(`/api/growth/variants?${params}`)
      setVariants(res.data || [])
    } catch (e) {}
  }

  const loadDashboard = async () => {
    try {
      const params = new URLSearchParams()
      if (metPlatform) params.set('platform', metPlatform)
      const res = await api.get(`/api/growth/metrics-dashboard?${params}`)
      setDashboard(res.data)
    } catch (e) {}
  }

  const generate = async () => {
    if (!theme.trim()) { toast.error('请输入核心主题'); return }
    setGenerating(true)
    try {
      const res = await api.post('/api/growth/batch', { theme: theme.trim(), platform, count })
      toast.success(`成功生成 ${res.data.generated} 组变体`)
      loadVariants()
    } catch (e) { toast.error(`生成失败：${e.message}`) }
    finally { setGenerating(false) }
  }

  const toggleSelect = async (id) => {
    const v = variants.find((x) => x.id === id)
    if (!v) return
    try {
      await api.put(`/api/growth/variants/${id}`, {
        title: v.title, content: v.content, topics: v.topics,
        cover_style: v.cover_style, selected: !v.selected,
      })
      setVariants((prev) => prev.map((x) => x.id === id ? { ...x, selected: !x.selected } : x))
    } catch (e) { toast.error(e.message) }
  }

  const startEdit = (v) => {
    setEditId(v.id)
    setEditForm({ title: v.title, content: v.content, topics: v.topics || [], cover_style: v.cover_style || '', topicInput: '' })
  }

  const saveEdit = async () => {
    try {
      await api.put(`/api/growth/variants/${editId}`, {
        title: editForm.title, content: editForm.content,
        topics: editForm.topics, cover_style: editForm.cover_style,
        selected: true,
      })
      toast.success('已保存')
      setEditId('')
      loadVariants()
    } catch (e) { toast.error(e.message) }
  }

  const addEditTopic = () => {
    const t = editForm.topicInput.trim().replace(/^#/, '')
    if (!t) return
    if (editForm.topics.includes(t)) return
    setEditForm({ ...editForm, topics: [...editForm.topics, t], topicInput: '' })
  }

  const deleteVariant = async (id) => {
    try { await api.delete(`/api/growth/variants/${id}`); toast.success('已删除'); loadVariants() }
    catch (e) { toast.error(e.message) }
  }

  const batchSchedule = async () => {
    const ids = variants.filter((v) => v.selected).map((v) => v.id)
    if (ids.length === 0) { toast.error('请先勾选要排期的变体'); return }
    setSchedLoading(true)
    try {
      const res = await api.post('/api/growth/batch-schedule', {
        variant_ids: ids, interval_minutes: schedInterval,
        start_at: schedStart || '',
      })
      toast.success(res.data.message)
      setSchedModal(false)
      loadVariants()
    } catch (e) { toast.error(e.message) }
    finally { setSchedLoading(false) }
  }

  const saveMetrics = async () => {
    if (!entryRecordId.trim()) { toast.error('请输入发布记录 ID'); return }
    setEntrySaving(true)
    try {
      await api.post(`/api/growth/metrics/${entryRecordId.trim()}`, entryForm)
      toast.success('效果数据已录入')
      setEntryForm({ views: 0, likes: 0, comments: 0, shares: 0, followers_gained: 0 })
      loadDashboard()
    } catch (e) { toast.error(e.message) }
    finally { setEntrySaving(false) }
  }

  const runReview = async () => {
    setReviewing(true); setReport(null)
    try {
      const params = new URLSearchParams({ days: String(reviewDays) })
      if (reviewPlatform) params.set('platform', reviewPlatform)
      const res = await api.post(`/api/growth/review?${params}`)
      setReport(res.data)
    } catch (e) { toast.error(`复盘失败：${e.message}`) }
    finally { setReviewing(false) }
  }

  const selectedCount = variants.filter((v) => v.selected).length

  return (
    <div className="space-y-6">
      <PageHeader
        title="增长工坊"
        description="批量内容变体生产 + 发布效果追踪 + AI 运营复盘，打造增长飞轮"
        icon={TrendingUp}
        iconColor="from-violet-500 to-purple-600"
      />

      {/* Tab 切换 */}
      <div className="flex gap-2">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === t.key ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white shadow-soft' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* ═══════════════════ 变体工坊 ═══════════════════ */}
      {tab === 'variants' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 生成表单 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Wand2 className="w-4 h-4 text-purple-500" /> 批量变体生成
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">核心主题</label>
                <textarea value={theme} onChange={(e) => setTheme(e.target.value)}
                  placeholder="如：AI 时代职场人必备的 5 个效率工具"
                  rows={3} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">目标平台</label>
                <div className="grid grid-cols-3 gap-2">
                  {PLATFORMS.map((p) => (
                    <button key={p.value} onClick={() => setPlatform(p.value)}
                      className={`px-2 py-2 rounded-lg text-xs border transition-all ${
                        platform === p.value ? `${p.border} font-medium ring-2 ring-violet-500/20` : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                      }`}>
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">生成数量：{count} 组</label>
                <input type="range" min={1} max={10} value={count} onChange={(e) => setCount(Number(e.target.value))}
                  className="w-full accent-violet-600" />
                <div className="flex justify-between text-[10px] text-gray-400"><span>1</span><span>10</span></div>
              </div>
              <Button variant="primary" size="lg" icon={Wand2} loading={generating} onClick={generate} className="w-full">
                {generating ? 'AI 生成中…' : `生成 ${count} 组变体`}
              </Button>
            </div>
          </Card>

          {/* 变体列表 */}
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-gray-400" /> 变体列表（{variants.length}）
                </h3>
                <div className="flex items-center gap-2">
                  <select value={varFilter} onChange={(e) => setVarFilter(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20">
                    <option value="">全部平台</option>
                    {PLATFORMS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                  </select>
                  {variants.length > 0 && (
                    <Button variant="secondary" size="sm" icon={CalendarPlus}
                      onClick={() => setSchedModal(true)} disabled={selectedCount === 0}>
                      批量排期（{selectedCount}）
                    </Button>
                  )}
                </div>
              </div>

              {variants.length === 0 ? (
                <Empty icon={Wand2} title="暂无变体" description="在左侧输入主题，AI 将为你生成多组内容变体" />
              ) : (
                <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                  {variants.map((v) => (
                    <div key={v.id} className={`p-3 rounded-xl border transition-all ${
                      v.selected ? 'border-violet-200 bg-violet-50/20' : 'border-gray-100 hover:border-gray-200'
                    }`}>
                      {editId === v.id ? (
                        <div className="space-y-2">
                          <input type="text" value={editForm.title}
                            onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                            className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-medium focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none" />
                          <textarea value={editForm.content}
                            onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
                            rows={4} className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none" />
                          <div className="flex gap-2">
                            <input type="text" value={editForm.topicInput}
                              onChange={(e) => setEditForm({ ...editForm, topicInput: e.target.value })}
                              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addEditTopic() } }}
                              placeholder="添加话题标签…" className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none" />
                            <Button variant="secondary" size="sm" icon={Plus} onClick={addEditTopic}>添加</Button>
                          </div>
                          {editForm.topics.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {editForm.topics.map((t, i) => (
                                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-50 border border-violet-200 text-xs text-violet-700">
                                  #{t}
                                  <button onClick={() => setEditForm({ ...editForm, topics: editForm.topics.filter((_, j) => j !== i) })}
                                    className="text-violet-300 hover:text-red-500"><Trash2 className="w-3 h-3" /></button>
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="flex gap-2">
                            <Button variant="primary" size="sm" icon={Save} onClick={saveEdit}>保存</Button>
                            <Button variant="ghost" size="sm" onClick={() => setEditId('')}>取消</Button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="flex items-start gap-2">
                            <button onClick={() => toggleSelect(v.id)}
                              className="mt-1 p-0.5 rounded text-violet-400 hover:text-violet-600">
                              {v.selected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                            </button>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap mb-1">
                                <span className="text-sm font-semibold text-gray-800">{v.title}</span>
                                <Badge color="purple">{v.platform === 'wechat' ? '公众号' : v.platform === 'douyin' ? '抖音' : '快手'}</Badge>
                                {v.cover_style && <span className="text-[10px] text-gray-400">封面：{v.cover_style}</span>}
                              </div>
                              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap line-clamp-3">{v.content}</p>
                              {v.topics?.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1.5">
                                  {v.topics.map((t, i) => (
                                    <span key={i} className="px-1.5 py-0.5 rounded-full bg-gray-100 text-[10px] text-gray-500">#{t}</span>
                                  ))}
                                </div>
                              )}
                              <div className="flex items-center gap-2 mt-2">
                                {v.scheduled_at && <span className="text-[10px] text-emerald-600">已排期：{v.scheduled_at?.slice(0, 16).replace('T', ' ')}</span>}
                              </div>
                            </div>
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <button onClick={() => startEdit(v)} className="p-1.5 text-gray-300 hover:text-violet-500 rounded-lg hover:bg-violet-50"><Edit3 className="w-4 h-4" /></button>
                              <button onClick={() => deleteVariant(v.id)} className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"><Trash2 className="w-4 h-4" /></button>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}

      {/* ═══════════════════ 效果追踪 ═══════════════════ */}
      {tab === 'metrics' && (
        <div className="space-y-6">
          {/* 看板 */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: '总阅读', value: dashboard?.total_views ?? 0, icon: Eye, color: 'from-blue-500 to-indigo-600' },
              { label: '总点赞', value: dashboard?.total_likes ?? 0, icon: ThumbsUp, color: 'from-pink-500 to-rose-600' },
              { label: '总评论', value: dashboard?.total_comments ?? 0, icon: MessageCircle, color: 'from-amber-500 to-orange-600' },
              { label: '总分享', value: dashboard?.total_shares ?? 0, icon: Share2, color: 'from-emerald-500 to-teal-600' },
              { label: '总涨粉', value: dashboard?.total_followers ?? 0, icon: UserPlus, color: 'from-violet-500 to-purple-600' },
            ].map((s, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center`}>
                    <s.icon className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-gray-900">{s.value.toLocaleString()}</div>
                    <div className="text-xs text-gray-500">{s.label}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* 效果排行 + 手动录入 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-blue-500" /> 效果排行 TOP20
                </h3>
                <select value={metPlatform} onChange={(e) => { setMetPlatform(e.target.value); loadDashboard() }}
                  className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none">
                  <option value="">全部平台</option>
                  {PLATFORMS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
              {!dashboard?.top_items?.length ? (
                <Empty icon={BarChart3} title="暂无效果数据" description="发布内容并录入数据后这里会展示排行" />
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                  {dashboard.top_items.map((item, i) => (
                    <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg border border-gray-100 hover:border-blue-200 transition-all">
                      <span className="w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-bold flex items-center justify-center flex-shrink-0">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">{item.title || '(无标题)'}</div>
                        <div className="flex items-center gap-3 text-[11px] text-gray-400 mt-0.5">
                          <span className="flex items-center gap-1"><Eye className="w-3 h-3" />{item.views}</span>
                          <span className="flex items-center gap-1"><ThumbsUp className="w-3 h-3" />{item.likes}</span>
                          <span className="flex items-center gap-1"><MessageCircle className="w-3 h-3" />{item.comments}</span>
                        </div>
                      </div>
                      <Badge color="blue">{item.platform === 'wechat' ? '公众号' : item.platform === 'douyin' ? '抖音' : item.platform === 'kuaishou' ? '快手' : item.platform}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* 手动录入 */}
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-amber-500" /> 手动录入效果数据
              </h3>
              <p className="text-xs text-gray-400 mb-3">发布记录 ID 可在「发布中心 → 发布记录」中找到</p>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">发布记录 ID</label>
                  <input type="text" value={entryRecordId} onChange={(e) => setEntryRecordId(e.target.value)}
                    placeholder="如：pub_abc123def4"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: 'views', label: '阅读量', icon: Eye },
                    { key: 'likes', label: '点赞', icon: ThumbsUp },
                    { key: 'comments', label: '评论', icon: MessageCircle },
                    { key: 'shares', label: '分享', icon: Share2 },
                  ].map((f) => (
                    <div key={f.key}>
                      <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1"><f.icon className="w-3 h-3" />{f.label}</label>
                      <input type="number" min={0} value={entryForm[f.key]}
                        onChange={(e) => setEntryForm({ ...entryForm, [f.key]: Number(e.target.value) || 0 })}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                    </div>
                  ))}
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1"><UserPlus className="w-3 h-3" />涨粉数</label>
                  <input type="number" min={0} value={entryForm.followers_gained}
                    onChange={(e) => setEntryForm({ ...entryForm, followers_gained: Number(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                </div>
                <Button variant="primary" icon={Save} loading={entrySaving} onClick={saveMetrics} className="w-full">保存效果数据</Button>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* ═══════════════════ AI 复盘 ═══════════════════ */}
      {tab === 'review' && (
        <div className="space-y-6">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-500" /> AI 运营复盘
            </h3>
            <div className="flex flex-wrap items-end gap-3 mb-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">复盘平台</label>
                <select value={reviewPlatform} onChange={(e) => setReviewPlatform(e.target.value)}
                  className="px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20">
                  <option value="">全部平台</option>
                  {PLATFORMS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">复盘天数</label>
                <select value={reviewDays} onChange={(e) => setReviewDays(Number(e.target.value))}
                  className="px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20">
                  {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>最近 {d} 天</option>)}
                </select>
              </div>
              <Button variant="primary" icon={Sparkles} loading={reviewing} onClick={runReview}>生成复盘报告</Button>
            </div>

            {report ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 rounded-xl bg-violet-50 border border-violet-200">
                  <Eye className="w-4 h-4 text-violet-500" />
                  <span className="text-sm text-violet-700">基于 {report.data_points} 条数据 · 总阅读 {report.total_views?.toLocaleString()} · 总涨粉 {report.total_followers?.toLocaleString()}</span>
                </div>
                <div className="p-4 rounded-xl bg-white border border-gray-200 whitespace-pre-wrap text-sm text-gray-700 leading-relaxed">
                  {report.report}
                </div>
              </div>
            ) : (
              <Empty icon={Sparkles} title="点击生成复盘报告" description="AI 将基于你的发布效果数据，分析爆款规律、诊断问题、给出下期选题建议" />
            )}
          </Card>
        </div>
      )}

      {/* 批量排期 Modal */}
      <Modal open={schedModal} onClose={() => setSchedModal(false)} title="批量创建排期" size="sm">
        <div className="space-y-3">
          <p className="text-sm text-gray-600">将为已勾选的 <span className="font-semibold text-violet-600">{selectedCount}</span> 条变体创建发布排期。</p>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">排期间隔（分钟）</label>
            <input type="number" min={10} max={1440} value={schedInterval}
              onChange={(e) => setSchedInterval(Number(e.target.value) || 60)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none" />
            <p className="text-[10px] text-gray-400 mt-0.5">如间隔 60 分钟，3 条变体将在 3 小时内依次自动发布</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">首条发布时间（可选）</label>
            <input type="datetime-local" value={schedStart}
              onChange={(e) => setSchedStart(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none" />
            <p className="text-[10px] text-gray-400 mt-0.5">不填则从现在 + 5 分钟后开始</p>
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" onClick={() => setSchedModal(false)}>取消</Button>
            <Button variant="primary" icon={CalendarPlus} loading={schedLoading} onClick={batchSchedule}>确认排期</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
