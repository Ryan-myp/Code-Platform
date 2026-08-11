import React, { useState, useEffect } from 'react'
import {
  Sparkles,
  TrendingUp,
  Wand2,
  FileText,
  CheckSquare,
  Square,
  Trash2,
  Edit3,
  CalendarPlus,
  Play,
  Clock,
  BarChart3,
  MessageSquare,
  Eye,
  ThumbsUp,
  MessageCircle,
  Share2,
  UserPlus,
  Save,
  RefreshCw,
  X,
  Plus,
  Send,
  Flame,
  ArrowRight,
  ShieldCheck,
  Layers,
  Search,
  Target,
  TrendingUp as TrendingIcon,
  Radar,
  UserPlus as Competitor,
  Zap,
  Crosshair,
} from 'lucide-react'
import { Card, Button, Badge, Empty, PageHeader, Modal, SkeletonList } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PLATFORMS = [
  {
    value: 'wechat',
    label: '微信公众号',
    color: 'from-emerald-500 to-green-600',
    border: 'border-emerald-200 bg-emerald-50',
  },
  {
    value: 'douyin',
    label: '抖音',
    color: 'from-gray-700 to-gray-900',
    border: 'border-gray-200 bg-gray-50',
  },
  {
    value: 'kuaishou',
    label: '快手',
    color: 'from-orange-500 to-amber-600',
    border: 'border-orange-200 bg-orange-50',
  },
]

const TABS = [
  { key: 'variants', label: '变体工坊', icon: Wand2 },
  { key: 'hotspots', label: '热点选题', icon: Flame },
  { key: 'series', label: '内容系列', icon: Layers },
  { key: 'metrics', label: '效果追踪', icon: BarChart3 },
  { key: 'review', label: 'AI 复盘', icon: Sparkles },
  { key: 'competitor', label: '竞品监控', icon: Target },
  { key: 'seo', label: 'SEO评分', icon: Search },
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
  const [editForm, setEditForm] = useState({
    title: '',
    content: '',
    topics: [],
    cover_style: '',
    topicInput: '',
  })

  // 批量排期
  const [schedModal, setSchedModal] = useState(false)
  const [schedInterval, setSchedInterval] = useState(60)
  const [schedStart, setSchedStart] = useState('')
  const [schedLoading, setSchedLoading] = useState(false)

  // ── 效果追踪状态 ──
  const [dashboard, setDashboard] = useState(null)
  const [metPlatform, setMetPlatform] = useState('')
  const [entryRecordId, setEntryRecordId] = useState('')
  const [entryForm, setEntryForm] = useState({
    views: 0,
    likes: 0,
    comments: 0,
    shares: 0,
    followers_gained: 0,
  })
  const [entrySaving, setEntrySaving] = useState(false)

  // ── AI 复盘状态 ──
  const [reviewPlatform, setReviewPlatform] = useState('')
  const [reviewDays, setReviewDays] = useState(30)
  const [reviewing, setReviewing] = useState(false)
  const [report, setReport] = useState(null)

  // ── 热点选题状态 ──
  const [hotspots, setHotspots] = useState([])
  const [hotSource, setHotSource] = useState('')
  const [hotLoading, setHotLoading] = useState(false)
  const [suggestId, setSuggestId] = useState('')
  const [suggestions, setSuggestions] = useState(null)
  const [suggestLoading, setSuggestLoading] = useState(false)

  // ── 内容系列状态 ──
  const [series, setSeries] = useState([])
  const [seriesForm, setSeriesForm] = useState({ name: '', description: '', platform: '' })
  const [seriesDetail, setSeriesDetail] = useState(null)
  const [seriesStats, setSeriesStats] = useState(null)
  const [seriesItemInput, setSeriesItemInput] = useState('')
  const [addingItem, setAddingItem] = useState(false)

  // ── 评论聚合状态 ──
  const [comments, setComments] = useState([])
  const [commentRecordId, setCommentRecordId] = useState('')
  const [commentForm, setCommentForm] = useState({ author: '', content: '' })
  const [replyLoading, setReplyLoading] = useState('')
  const [commentSaving, setCommentSaving] = useState(false)

  // ── 竞品监控状态 ──
  const [competitors, setCompetitors] = useState([])
  const [compForm, setCompForm] = useState({
    name: '',
    platform: '',
    account_id: '',
    description: '',
  })
  const [compSaving, setCompSaving] = useState(false)
  const [analyzeIds, setAnalyzeIds] = useState([])
  const [analyzing, setAnalyzing] = useState(false)
  const [compReport, setCompReport] = useState(null)

  // ── SEO评分状态 ──
  const [seoTitle, setSeoTitle] = useState('')
  const [seoContent, setSeoContent] = useState('')
  const [seoKeyword, setSeoKeyword] = useState('')
  const [seoLoading, setSeoLoading] = useState(false)
  const [seoResult, setSeoResult] = useState(null)
  const [kwSeed, setKwSeed] = useState('')
  const [kwIndustry, setKwIndustry] = useState('')
  const [kwLoading, setKwLoading] = useState(false)
  const [kwResult, setKwResult] = useState(null)

  useEffect(() => {
    if (tab === 'variants') loadVariants()
  }, [tab, varFilter])
  useEffect(() => {
    if (tab === 'metrics') loadDashboard()
  }, [tab, metPlatform])
  useEffect(() => {
    if (tab === 'hotspots') loadHotspots()
  }, [tab, hotSource])
  useEffect(() => {
    if (tab === 'series') loadSeries()
  }, [tab])
  useEffect(() => {
    if (tab === 'metrics' && commentRecordId) loadComments()
  }, [tab, commentRecordId])
  useEffect(() => {
    if (tab === 'competitor') loadCompetitors()
  }, [tab])
  useEffect(() => {
    if (tab === 'seo') {
      setSeoResult(null)
      setKwResult(null)
    }
  }, [tab])

  const loadVariants = async () => {
    try {
      const params = new URLSearchParams()
      if (varFilter) params.set('platform', varFilter)
      const res = await api.get(`/api/growth/variants?${params}`)
      setVariants(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const loadDashboard = async () => {
    try {
      const params = new URLSearchParams()
      if (metPlatform) params.set('platform', metPlatform)
      const res = await api.get(`/api/growth/metrics-dashboard?${params}`)
      setDashboard(res.data)
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const generate = async () => {
    if (!theme.trim()) {
      toast.error('请输入核心主题')
      return
    }
    setGenerating(true)
    try {
      const res = await api.post('/api/growth/batch', { theme: theme.trim(), platform, count })
      toast.success(`成功生成 ${res.data.generated} 组变体`)
      loadVariants()
    } catch (e) {
      toast.error(`生成失败：${e.message}`)
    } finally {
      setGenerating(false)
    }
  }

  const toggleSelect = async (id) => {
    const v = variants.find((x) => x.id === id)
    if (!v) return
    try {
      await api.put(`/api/growth/variants/${id}`, {
        title: v.title,
        content: v.content,
        topics: v.topics,
        cover_style: v.cover_style,
        selected: !v.selected,
      })
      setVariants((prev) => prev.map((x) => (x.id === id ? { ...x, selected: !x.selected } : x)))
    } catch (e) {
      toast.error(e.message)
    }
  }

  const startEdit = (v) => {
    setEditId(v.id)
    setEditForm({
      title: v.title,
      content: v.content,
      topics: v.topics || [],
      cover_style: v.cover_style || '',
      topicInput: '',
    })
  }

  const saveEdit = async () => {
    try {
      await api.put(`/api/growth/variants/${editId}`, {
        title: editForm.title,
        content: editForm.content,
        topics: editForm.topics,
        cover_style: editForm.cover_style,
        selected: true,
      })
      toast.success('已保存')
      setEditId('')
      loadVariants()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const addEditTopic = () => {
    const t = editForm.topicInput.trim().replace(/^#/, '')
    if (!t) return
    if (editForm.topics.includes(t)) return
    setEditForm({ ...editForm, topics: [...editForm.topics, t], topicInput: '' })
  }

  const deleteVariant = async (id) => {
    try {
      await api.delete(`/api/growth/variants/${id}`)
      toast.success('已删除')
      loadVariants()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const batchSchedule = async () => {
    const ids = variants.filter((v) => v.selected).map((v) => v.id)
    if (ids.length === 0) {
      toast.error('请先勾选要排期的变体')
      return
    }
    setSchedLoading(true)
    try {
      const res = await api.post('/api/growth/batch-schedule', {
        variant_ids: ids,
        interval_minutes: schedInterval,
        start_at: schedStart || '',
      })
      toast.success(res.data.message)
      setSchedModal(false)
      loadVariants()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSchedLoading(false)
    }
  }

  const saveMetrics = async () => {
    if (!entryRecordId.trim()) {
      toast.error('请输入发布记录 ID')
      return
    }
    setEntrySaving(true)
    try {
      await api.post(`/api/growth/metrics/${entryRecordId.trim()}`, entryForm)
      toast.success('效果数据已录入')
      setEntryForm({ views: 0, likes: 0, comments: 0, shares: 0, followers_gained: 0 })
      loadDashboard()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setEntrySaving(false)
    }
  }

  const runReview = async () => {
    setReviewing(true)
    setReport(null)
    try {
      const params = new URLSearchParams({ days: String(reviewDays) })
      if (reviewPlatform) params.set('platform', reviewPlatform)
      const res = await api.post(`/api/growth/review?${params}`)
      setReport(res.data)
    } catch (e) {
      toast.error(`复盘失败：${e.message}`)
    } finally {
      setReviewing(false)
    }
  }

  // ── 热点选题 ──
  const loadHotspots = async () => {
    setHotLoading(true)
    try {
      const params = new URLSearchParams()
      if (hotSource) params.set('source', hotSource)
      const res = await api.get(`/api/strategy/hotspots?${params}`)
      setHotspots(res.data?.items || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    } finally {
      setHotLoading(false)
    }
  }

  const getSuggestions = async (hotspot) => {
    setSuggestId(hotspot.title)
    setSuggestLoading(true)
    setSuggestions(null)
    try {
      const res = await api.post('/api/strategy/topic-suggest', {
        hotspot: hotspot.title,
        platform,
        source: hotspot.source,
      })
      setSuggestions(res.data)
    } catch (e) {
      toast.error(`选题建议生成失败：${e.message}`)
    } finally {
      setSuggestLoading(false)
    }
  }

  const importToVariants = (suggestion) => {
    setTheme(suggestion.title_direction)
    setTab('variants')
    toast.success('已导入变体工坊，可修改后批量生成')
  }

  // ── 内容系列 ──
  const loadSeries = async () => {
    try {
      const res = await api.get('/api/strategy/series')
      setSeries(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const createSeries = async () => {
    if (!seriesForm.name.trim()) {
      toast.error('请输入系列名称')
      return
    }
    try {
      await api.post('/api/strategy/series', seriesForm)
      toast.success('系列已创建')
      setSeriesForm({ name: '', description: '', platform: '' })
      loadSeries()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const loadSeriesStats = async (id) => {
    try {
      const res = await api.get(`/api/strategy/series/${id}/stats`)
      setSeriesDetail(id)
      setSeriesStats(res.data)
    } catch (e) {
      toast.error(e.message)
    }
  }

  const deleteSeries = async (id) => {
    try {
      await api.delete(`/api/strategy/series/${id}`)
      toast.success('已删除')
      loadSeries()
      setSeriesDetail(null)
      setSeriesStats(null)
    } catch (e) {
      toast.error(e.message)
    }
  }

  const addSeriesItem = async () => {
    if (!seriesDetail) {
      toast.error('请先选择一个系列')
      return
    }
    if (!seriesItemInput.trim()) {
      toast.error('请输入发布记录 ID')
      return
    }
    setAddingItem(true)
    try {
      await api.post(`/api/strategy/series/${seriesDetail}/items`, {
        record_id: seriesItemInput.trim(),
      })
      toast.success('已加入系列')
      setSeriesItemInput('')
      loadSeries()
      loadSeriesStats(seriesDetail)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setAddingItem(false)
    }
  }

  const removeSeriesItem = async (itemId) => {
    if (!seriesDetail) return
    try {
      await api.delete(`/api/strategy/series/${seriesDetail}/items/${itemId}`)
      toast.success('已从系列移除')
      loadSeries()
      loadSeriesStats(seriesDetail)
    } catch (e) {
      toast.error(e.message)
    }
  }

  // ── 评论聚合 + AI 回复 ──
  const loadComments = async () => {
    try {
      const res = await api.get(`/api/growth/comments?record_id=${commentRecordId}`)
      setComments(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const addComment = async () => {
    if (!commentRecordId.trim()) {
      toast.error('请先输入发布记录 ID')
      return
    }
    if (!commentForm.content.trim()) {
      toast.error('请输入评论内容')
      return
    }
    setCommentSaving(true)
    try {
      await api.post('/api/growth/comments', {
        record_id: commentRecordId.trim(),
        author: commentForm.author.trim() || '匿名用户',
        content: commentForm.content.trim(),
      })
      toast.success('评论已录入')
      setCommentForm({ author: '', content: '' })
      loadComments()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setCommentSaving(false)
    }
  }

  const generateReply = async (commentId) => {
    setReplyLoading(commentId)
    try {
      await api.post(`/api/growth/comments/${commentId}/reply`)
      toast.success('AI 回复已生成')
      loadComments()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setReplyLoading('')
    }
  }

  const deleteComment = async (id) => {
    try {
      await api.delete(`/api/growth/comments/${id}`)
      toast.success('已删除')
      loadComments()
    } catch (e) {
      toast.error(e.message)
    }
  }

  // ── 竞品监控 ──
  const loadCompetitors = async () => {
    try {
      const res = await api.get('/api/monitor/competitors')
      setCompetitors(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const addCompetitor = async () => {
    if (!compForm.name.trim()) {
      toast.error('请输入竞品名称')
      return
    }
    setCompSaving(true)
    try {
      await api.post('/api/monitor/competitors', compForm)
      toast.success('竞品已添加')
      setCompForm({ name: '', platform: '', account_id: '', description: '' })
      loadCompetitors()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setCompSaving(false)
    }
  }

  const deleteCompetitor = async (id) => {
    try {
      await api.delete(`/api/monitor/competitors/${id}`)
      toast.success('已删除')
      loadCompetitors()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const toggleAnalyzeId = (id) => {
    setAnalyzeIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const runAnalysis = async () => {
    if (analyzeIds.length === 0) {
      toast.error('请先勾选要分析的竞品')
      return
    }
    setAnalyzing(true)
    setCompReport(null)
    try {
      const res = await api.post('/api/monitor/analyze', { competitor_ids: analyzeIds })
      setCompReport(res.data)
      toast.success('竞品分析完成')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  // ── SEO 评分 ──
  const runSeoAnalyze = async () => {
    if (!seoTitle.trim()) {
      toast.error('请输入文章标题')
      return
    }
    if (!seoContent.trim() || seoContent.length < 50) {
      toast.error('文章内容至少50字')
      return
    }
    setSeoLoading(true)
    setSeoResult(null)
    try {
      const res = await api.post('/api/seo/analyze', {
        title: seoTitle.trim(),
        content: seoContent.trim(),
        target_keyword: seoKeyword.trim(),
      })
      setSeoResult(res.data)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSeoLoading(false)
    }
  }

  const runKeywordResearch = async () => {
    if (!kwSeed.trim()) {
      toast.error('请输入种子关键词')
      return
    }
    setKwLoading(true)
    setKwResult(null)
    try {
      const res = await api.post('/api/seo/keywords', {
        seed_keyword: kwSeed.trim(),
        industry: kwIndustry.trim(),
      })
      setKwResult(res.data)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setKwLoading(false)
    }
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
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === t.key
                ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white shadow-soft'
                : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
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
                <textarea
                  value={theme}
                  onChange={(e) => setTheme(e.target.value)}
                  placeholder="如：AI 时代职场人必备的 5 个效率工具"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">目标平台</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {PLATFORMS.map((p) => (
                    <button
                      key={p.value}
                      onClick={() => setPlatform(p.value)}
                      className={`px-2 py-2 rounded-lg text-xs border transition-all ${
                        platform === p.value
                          ? `${p.border} font-medium ring-2 ring-violet-500/20`
                          : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  生成数量：{count} 组
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={count}
                  onChange={(e) => setCount(Number(e.target.value))}
                  className="w-full accent-violet-600"
                />
                <div className="flex justify-between text-[10px] text-gray-400">
                  <span>1</span>
                  <span>10</span>
                </div>
              </div>
              <Button
                variant="primary"
                size="lg"
                icon={Wand2}
                loading={generating}
                onClick={generate}
                className="w-full"
              >
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
                  <select
                    value={varFilter}
                    onChange={(e) => setVarFilter(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                  >
                    <option value="">全部平台</option>
                    {PLATFORMS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                  {variants.length > 0 && (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={CalendarPlus}
                      onClick={() => setSchedModal(true)}
                      disabled={selectedCount === 0}
                    >
                      批量排期（{selectedCount}）
                    </Button>
                  )}
                </div>
              </div>

              {variants.length === 0 ? (
                varFilter ? (
                  <Empty
                    icon={Wand2}
                    title="当前平台暂无变体"
                    description={
                      <>
                        试试其他平台，或
                        <button
                          onClick={() => setVarFilter('')}
                          className="text-violet-600 hover:text-violet-800 font-medium mx-1"
                        >
                          清除筛选
                        </button>
                        查看全部内容
                      </>
                    }
                  />
                ) : (
                  <Empty
                    icon={Wand2}
                    title="暂无变体"
                    description="在左侧输入主题，AI 将为你生成多组内容变体"
                  />
                )
              ) : (
                <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                  {variants.map((v) => (
                    <div
                      key={v.id}
                      className={`p-3 rounded-xl border transition-all ${
                        v.selected
                          ? 'border-violet-200 bg-violet-50/20'
                          : 'border-gray-100 hover:border-gray-200'
                      }`}
                    >
                      {editId === v.id ? (
                        <div className="space-y-2">
                          <input
                            type="text"
                            value={editForm.title}
                            onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                            className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-medium focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                          />
                          <textarea
                            value={editForm.content}
                            onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
                            rows={4}
                            className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                          />
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={editForm.topicInput}
                              onChange={(e) =>
                                setEditForm({ ...editForm, topicInput: e.target.value })
                              }
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault()
                                  addEditTopic()
                                }
                              }}
                              placeholder="添加话题标签…"
                              className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                            />
                            <Button
                              variant="secondary"
                              size="sm"
                              icon={Plus}
                              onClick={addEditTopic}
                            >
                              添加
                            </Button>
                          </div>
                          {editForm.topics.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {editForm.topics.map((t, i) => (
                                <span
                                  key={i}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-50 border border-violet-200 text-xs text-violet-700"
                                >
                                  #{t}
                                  <button
                                    onClick={() =>
                                      setEditForm({
                                        ...editForm,
                                        topics: editForm.topics.filter((_, j) => j !== i),
                                      })
                                    }
                                    className="text-violet-300 hover:text-red-500"
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </button>
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="flex gap-2">
                            <Button variant="primary" size="sm" icon={Save} onClick={saveEdit}>
                              保存
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setEditId('')}>
                              取消
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="flex items-start gap-2">
                            <button
                              onClick={() => toggleSelect(v.id)}
                              className="mt-1 p-0.5 rounded text-violet-400 hover:text-violet-600"
                            >
                              {v.selected ? (
                                <CheckSquare className="w-4 h-4" />
                              ) : (
                                <Square className="w-4 h-4" />
                              )}
                            </button>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap mb-1">
                                <span className="text-sm font-semibold text-gray-800">
                                  {v.title}
                                </span>
                                <Badge color="purple">
                                  {v.platform === 'wechat'
                                    ? '公众号'
                                    : v.platform === 'douyin'
                                      ? '抖音'
                                      : '快手'}
                                </Badge>
                                {v.cover_style && (
                                  <span className="text-[10px] text-gray-400">
                                    封面：{v.cover_style}
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap line-clamp-3">
                                {v.content}
                              </p>
                              {v.topics?.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1.5">
                                  {v.topics.map((t, i) => (
                                    <span
                                      key={i}
                                      className="px-1.5 py-0.5 rounded-full bg-gray-100 text-[10px] text-gray-500"
                                    >
                                      #{t}
                                    </span>
                                  ))}
                                </div>
                              )}
                              <div className="flex items-center gap-2 mt-2">
                                {v.scheduled_at && (
                                  <span className="text-[10px] text-emerald-600">
                                    已排期：{v.scheduled_at?.slice(0, 16).replace('T', ' ')}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <button
                                onClick={() => startEdit(v)}
                                className="p-1.5 text-gray-300 hover:text-violet-500 rounded-lg hover:bg-violet-50"
                              >
                                <Edit3 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => deleteVariant(v.id)}
                                className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
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
              {
                label: '总阅读',
                value: dashboard?.total_views ?? 0,
                icon: Eye,
                color: 'from-blue-500 to-indigo-600',
              },
              {
                label: '总点赞',
                value: dashboard?.total_likes ?? 0,
                icon: ThumbsUp,
                color: 'from-pink-500 to-rose-600',
              },
              {
                label: '总评论',
                value: dashboard?.total_comments ?? 0,
                icon: MessageCircle,
                color: 'from-amber-500 to-orange-600',
              },
              {
                label: '总分享',
                value: dashboard?.total_shares ?? 0,
                icon: Share2,
                color: 'from-emerald-500 to-teal-600',
              },
              {
                label: '总涨粉',
                value: dashboard?.total_followers ?? 0,
                icon: UserPlus,
                color: 'from-violet-500 to-purple-600',
              },
            ].map((s, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center`}
                  >
                    <s.icon className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <div className="text-xl font-bold text-gray-900">
                      {s.value.toLocaleString()}
                    </div>
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
                <select
                  value={metPlatform}
                  onChange={(e) => {
                    setMetPlatform(e.target.value)
                    loadDashboard()
                  }}
                  className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none"
                >
                  <option value="">全部平台</option>
                  {PLATFORMS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              {!dashboard?.top_items?.length ? (
                <Empty
                  icon={BarChart3}
                  title="暂无效果数据"
                  description="发布内容并录入数据后这里会展示排行"
                />
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                  {dashboard.top_items.map((item, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 p-2.5 rounded-lg border border-gray-100 hover:border-blue-200 transition-all"
                    >
                      <span className="w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-bold flex items-center justify-center flex-shrink-0">
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">
                          {item.title || '(无标题)'}
                        </div>
                        <div className="flex items-center gap-3 text-[11px] text-gray-400 mt-0.5">
                          <span className="flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            {item.views}
                          </span>
                          <span className="flex items-center gap-1">
                            <ThumbsUp className="w-3 h-3" />
                            {item.likes}
                          </span>
                          <span className="flex items-center gap-1">
                            <MessageCircle className="w-3 h-3" />
                            {item.comments}
                          </span>
                        </div>
                      </div>
                      <Badge color="blue">
                        {item.platform === 'wechat'
                          ? '公众号'
                          : item.platform === 'douyin'
                            ? '抖音'
                            : item.platform === 'kuaishou'
                              ? '快手'
                              : item.platform}
                      </Badge>
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
              <p className="text-xs text-gray-400 mb-3">
                发布记录 ID 可在「发布中心 → 发布记录」中找到
              </p>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    发布记录 ID
                  </label>
                  <input
                    type="text"
                    value={entryRecordId}
                    onChange={(e) => setEntryRecordId(e.target.value)}
                    placeholder="如：pub_abc123def4"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: 'views', label: '阅读量', icon: Eye },
                    { key: 'likes', label: '点赞', icon: ThumbsUp },
                    { key: 'comments', label: '评论', icon: MessageCircle },
                    { key: 'shares', label: '分享', icon: Share2 },
                  ].map((f) => (
                    <div key={f.key}>
                      <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1">
                        <f.icon className="w-3 h-3" />
                        {f.label}
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={entryForm[f.key]}
                        onChange={(e) =>
                          setEntryForm({ ...entryForm, [f.key]: Number(e.target.value) || 0 })
                        }
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                      />
                    </div>
                  ))}
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <UserPlus className="w-3 h-3" />
                    涨粉数
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={entryForm.followers_gained}
                    onChange={(e) =>
                      setEntryForm({ ...entryForm, followers_gained: Number(e.target.value) || 0 })
                    }
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>
                <Button
                  variant="primary"
                  icon={Save}
                  loading={entrySaving}
                  onClick={saveMetrics}
                  className="w-full"
                >
                  保存效果数据
                </Button>
              </div>
            </Card>
          </div>

          {/* 评论互动聚合 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <MessageCircle className="w-4 h-4 text-amber-500" /> 评论管理
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    发布记录 ID
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={commentRecordId}
                      onChange={(e) => setCommentRecordId(e.target.value)}
                      placeholder="如：pub_abc123def4"
                      className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                    />
                    <Button variant="secondary" size="sm" icon={RefreshCw} onClick={loadComments}>
                      刷新
                    </Button>
                  </div>
                </div>
                {/* 手动添加评论 */}
                <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
                  <p className="text-xs font-medium text-gray-500 mb-2">手动录入评论</p>
                  <input
                    type="text"
                    value={commentForm.author}
                    onChange={(e) => setCommentForm({ ...commentForm, author: e.target.value })}
                    placeholder="评论者昵称（可选）"
                    className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-xs mb-2 focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                  <textarea
                    value={commentForm.content}
                    onChange={(e) => setCommentForm({ ...commentForm, content: e.target.value })}
                    placeholder="评论内容…"
                    rows={2}
                    className="w-full px-3 py-1.5 border border-gray-200 rounded-lg text-xs mb-2 focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                  <Button
                    variant="primary"
                    size="sm"
                    icon={Plus}
                    loading={commentSaving}
                    onClick={addComment}
                    className="w-full"
                  >
                    添加评论
                  </Button>
                </div>
              </div>
            </Card>

            <Card className="lg:col-span-2">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-purple-500" /> 评论列表（{comments.length}）
              </h3>
              {!commentRecordId ? (
                <Empty
                  icon={MessageCircle}
                  title="输入发布记录 ID"
                  description="在左侧输入发布记录 ID 查看对应评论"
                />
              ) : comments.length === 0 ? (
                <Empty
                  icon={MessageCircle}
                  title="暂无评论"
                  description="可手动录入评论或等待平台 API 自动拉取"
                />
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                  {comments.map((c) => (
                    <div
                      key={c.id}
                      className={`p-3 rounded-xl border transition-all ${
                        c.replied
                          ? 'border-emerald-200 bg-emerald-50/30'
                          : 'border-gray-100 hover:border-purple-200'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-gray-700">
                            {c.author || '匿名用户'}
                          </span>
                          {c.likes > 0 && (
                            <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
                              <ThumbsUp className="w-2.5 h-2.5" />
                              {c.likes}
                            </span>
                          )}
                          {c.replied && <Badge color="green">已回复</Badge>}
                        </div>
                        <button
                          onClick={() => deleteComment(c.id)}
                          className="p-1 text-gray-300 hover:text-red-500 rounded"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <p className="text-sm text-gray-700 mb-2">{c.content}</p>
                      {c.reply_content ? (
                        <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-100 text-xs text-emerald-700">
                          <span className="font-medium">AI 回复：</span>
                          {c.reply_content}
                        </div>
                      ) : (
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={Sparkles}
                          loading={replyLoading === c.id}
                          onClick={() => generateReply(c.id)}
                        >
                          生成 AI 回复
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}

      {/* ═══════════════════ 热点选题 ═══════════════════ */}
      {tab === 'hotspots' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 热点列表 */}
          <div className="lg:col-span-2">
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <Flame className="w-4 h-4 text-orange-500" /> 热点榜单
                </h3>
                <div className="flex items-center gap-2">
                  <select
                    value={hotSource}
                    onChange={(e) => setHotSource(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none"
                  >
                    <option value="">全部来源</option>
                    <option value="weibo">微博热搜</option>
                    <option value="zhihu">知乎热榜</option>
                    <option value="36kr">36氪</option>
                  </select>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={RefreshCw}
                    loading={hotLoading}
                    onClick={loadHotspots}
                  >
                    刷新
                  </Button>
                </div>
              </div>
              {hotLoading ? (
                <SkeletonList count={5} />
              ) : hotspots.length === 0 ? (
                <Empty
                  icon={Flame}
                  title="暂无热点"
                  description="点击刷新获取最新热点榜单"
                  actionLabel="刷新"
                  onAction={loadHotspots}
                />
              ) : (
                <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                  {hotspots.map((h) => (
                    <div
                      key={h.global_rank}
                      className={`p-3 rounded-xl border transition-all cursor-pointer ${
                        suggestId === h.title
                          ? 'border-orange-300 bg-orange-50/30'
                          : 'border-gray-100 hover:border-orange-200 hover:bg-orange-50/20'
                      }`}
                      onClick={() => getSuggestions(h)}
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 ${
                            h.global_rank <= 3
                              ? 'bg-orange-500 text-white'
                              : h.global_rank <= 10
                                ? 'bg-orange-100 text-orange-600'
                                : 'bg-gray-100 text-gray-500'
                          }`}
                        >
                          {h.global_rank}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800">{h.title}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge
                              color={
                                h.source === 'weibo'
                                  ? 'red'
                                  : h.source === 'zhihu'
                                    ? 'blue'
                                    : 'green'
                              }
                            >
                              {h.source_label}
                            </Badge>
                            <span className="text-[10px] text-gray-400">
                              热度 {(h.heat / 10000).toFixed(0)}万
                            </span>
                          </div>
                        </div>
                        {suggestId === h.title && suggestLoading && (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-orange-500 flex-shrink-0 mt-1" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* 选题建议 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-500" /> AI 选题建议
            </h3>
            {suggestLoading ? (
              <div className="flex flex-col items-center gap-3 py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-500" />
                <span className="text-sm text-gray-400">AI 正在分析热点…</span>
              </div>
            ) : suggestions ? (
              <div className="space-y-3">
                <div className="p-2 rounded-lg bg-purple-50 border border-purple-100 text-xs text-purple-700">
                  热点：{suggestions.hotspot}
                </div>
                {suggestions.suggestions?.map((s, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-lg border border-gray-100 hover:border-purple-200 transition-all"
                  >
                    <div className="text-sm font-semibold text-gray-800 mb-1">
                      {s.title_direction}
                    </div>
                    <div className="text-xs text-gray-500 mb-1">{s.angle}</div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-400">{s.audience}</span>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={ArrowRight}
                        onClick={() => importToVariants(s)}
                      >
                        导入变体
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                icon={Flame}
                title="点击左侧热点"
                description="AI 将为你生成选题角度和标题方向"
              />
            )}
          </Card>
        </div>
      )}

      {/* ═══════════════════ 内容系列 ═══════════════════ */}
      {tab === 'series' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Plus className="w-4 h-4 text-blue-500" /> 新建系列
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                value={seriesForm.name}
                onChange={(e) => setSeriesForm({ ...seriesForm, name: e.target.value })}
                placeholder="系列名称，如：AI工具测评"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <textarea
                value={seriesForm.description}
                onChange={(e) => setSeriesForm({ ...seriesForm, description: e.target.value })}
                placeholder="系列简介（可选）"
                rows={2}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <select
                value={seriesForm.platform}
                onChange={(e) => setSeriesForm({ ...seriesForm, platform: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 bg-white focus:outline-none"
              >
                <option value="">不限平台</option>
                {PLATFORMS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
              <Button variant="primary" icon={Plus} onClick={createSeries} className="w-full">
                创建系列
              </Button>
            </div>
          </Card>

          <div className="lg:col-span-2 space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-500" /> 我的系列（{series.length}）
              </h3>
              {series.length === 0 ? (
                <Empty
                  icon={Layers}
                  title="暂无内容系列"
                  description="创建系列来组织你的发布内容，便于统一管理和效果对比"
                />
              ) : (
                <div className="space-y-2">
                  {series.map((s) => (
                    <div
                      key={s.id}
                      className={`p-3 rounded-xl border transition-all cursor-pointer ${
                        seriesDetail === s.id
                          ? 'border-indigo-300 bg-indigo-50/20'
                          : 'border-gray-100 hover:border-indigo-200'
                      }`}
                      onClick={() => loadSeriesStats(s.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-gray-800">{s.name}</div>
                          <div className="text-xs text-gray-400">
                            {s.item_count || 0} 篇 ·{' '}
                            {s.platform
                              ? PLATFORMS.find((p) => p.value === s.platform)?.label || s.platform
                              : '全平台'}
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteSeries(s.id)
                          }}
                          className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {seriesStats && (
              <Card>
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-emerald-500" /> 系列效果
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
                  {[
                    { label: '总阅读', value: seriesStats.total_views, icon: Eye },
                    { label: '总点赞', value: seriesStats.total_likes, icon: ThumbsUp },
                    { label: '总评论', value: seriesStats.total_comments, icon: MessageCircle },
                  ].map((m, i) => (
                    <div key={i} className="text-center p-2 rounded-lg bg-gray-50">
                      <div className="text-lg font-bold text-gray-800">
                        {m.value.toLocaleString()}
                      </div>
                      <div className="text-[10px] text-gray-400">{m.label}</div>
                    </div>
                  ))}
                </div>
                {seriesStats.items?.length > 0 && (
                  <div className="space-y-1.5">
                    {seriesStats.items.map((item, i) => (
                      <div key={item.id || i} className="flex items-center gap-2 text-xs">
                        <span className="text-gray-400 w-5">#{i + 1}</span>
                        <span className="flex-1 text-gray-700 truncate">
                          {item.title || '(无标题)'}
                        </span>
                        <span className="text-gray-400">{item.views?.toLocaleString()} 阅读</span>
                        <button
                          onClick={() => removeSeriesItem(item.id)}
                          className="p-1 text-gray-300 hover:text-red-500 rounded hover:bg-red-50"
                          title="从系列移除"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex gap-2 mt-3">
                  <input
                    type="text"
                    value={seriesItemInput}
                    onChange={(e) => setSeriesItemInput(e.target.value)}
                    placeholder="发布记录 ID，如 pub_xxxx"
                    className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                  />
                  <Button
                    variant="primary"
                    size="sm"
                    icon={Plus}
                    loading={addingItem}
                    onClick={addSeriesItem}
                  >
                    加入
                  </Button>
                </div>
              </Card>
            )}
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
                <select
                  value={reviewPlatform}
                  onChange={(e) => setReviewPlatform(e.target.value)}
                  className="px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                >
                  <option value="">全部平台</option>
                  {PLATFORMS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">复盘天数</label>
                <select
                  value={reviewDays}
                  onChange={(e) => setReviewDays(Number(e.target.value))}
                  className="px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                >
                  {[7, 14, 30, 60, 90].map((d) => (
                    <option key={d} value={d}>
                      最近 {d} 天
                    </option>
                  ))}
                </select>
              </div>
              <Button variant="primary" icon={Sparkles} loading={reviewing} onClick={runReview}>
                生成复盘报告
              </Button>
            </div>

            {report ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 rounded-xl bg-violet-50 border border-violet-200">
                  <Eye className="w-4 h-4 text-violet-500" />
                  <span className="text-sm text-violet-700">
                    基于 {report.data_points} 条数据 · 总阅读 {report.total_views?.toLocaleString()}{' '}
                    · 总涨粉 {report.total_followers?.toLocaleString()}
                  </span>
                </div>
                <div className="p-4 rounded-xl bg-white border border-gray-200 whitespace-pre-wrap text-sm text-gray-700 leading-relaxed">
                  {report.report}
                </div>
              </div>
            ) : (
              <Empty
                icon={Sparkles}
                title="点击生成复盘报告"
                description="AI 将基于你的发布效果数据，分析爆款规律、诊断问题、给出下期选题建议"
              />
            )}
          </Card>
        </div>
      )}

      {/* ═══════════════════ 竞品监控 ═══════════════════ */}
      {tab === 'competitor' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Plus className="w-4 h-4 text-blue-500" /> 添加竞品
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                value={compForm.name}
                onChange={(e) => setCompForm({ ...compForm, name: e.target.value })}
                placeholder="竞品名称，如：XX科技"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <select
                value={compForm.platform}
                onChange={(e) => setCompForm({ ...compForm, platform: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 bg-white focus:outline-none"
              >
                <option value="">选择平台</option>
                <option value="douyin">抖音</option>
                <option value="kuaishou">快手</option>
                <option value="xiaohongshu">小红书</option>
                <option value="bilibili">B站</option>
                <option value="wechat">公众号</option>
                <option value="weibo">微博</option>
                <option value="zhihu">知乎</option>
              </select>
              <input
                type="text"
                value={compForm.account_id}
                onChange={(e) => setCompForm({ ...compForm, account_id: e.target.value })}
                placeholder="账号ID / 主页链接"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <textarea
                value={compForm.description}
                onChange={(e) => setCompForm({ ...compForm, description: e.target.value })}
                placeholder="竞品简介（可选）"
                rows={2}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <Button
                variant="primary"
                icon={Plus}
                loading={compSaving}
                onClick={addCompetitor}
                className="w-full"
              >
                添加竞品
              </Button>
            </div>
          </Card>

          <div className="lg:col-span-2 space-y-4">
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <Target className="w-4 h-4 text-red-500" /> 竞品列表（{competitors.length}）
                </h3>
                <Button
                  variant="primary"
                  size="sm"
                  icon={Sparkles}
                  loading={analyzing}
                  onClick={runAnalysis}
                  disabled={analyzeIds.length === 0}
                >
                  AI分析选中竞品（{analyzeIds.length}）
                </Button>
              </div>
              {competitors.length === 0 ? (
                <Empty
                  icon={Target}
                  title="暂无竞品"
                  description="添加需要关注的竞品账号，AI 将分析其内容策略"
                />
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {competitors.map((c) => (
                    <div
                      key={c.id}
                      className={`p-3 rounded-xl border transition-all cursor-pointer ${
                        analyzeIds.includes(c.id)
                          ? 'border-red-300 bg-red-50/20'
                          : 'border-gray-100 hover:border-red-200'
                      }`}
                      onClick={() => toggleAnalyzeId(c.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <button className="p-0.5 rounded text-red-400 hover:text-red-600">
                            {analyzeIds.includes(c.id) ? (
                              <CheckSquare className="w-4 h-4" />
                            ) : (
                              <Square className="w-4 h-4" />
                            )}
                          </button>
                          <div>
                            <div className="text-sm font-medium text-gray-800">{c.name}</div>
                            <div className="text-xs text-gray-400">
                              {c.platform}
                              {c.description ? ` · ${c.description.slice(0, 30)}` : ''}
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteCompetitor(c.id)
                          }}
                          className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {compReport && (
              <Card>
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-500" /> 分析结果
                </h3>
                <div className="space-y-3">
                  <p className="text-sm text-gray-600">{compReport.analysis?.overview}</p>

                  {compReport.analysis?.hot_patterns?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">爆款规律</p>
                      {compReport.analysis.hot_patterns.map((p, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-1.5 text-xs text-amber-700 py-0.5"
                        >
                          <Flame className="w-3 h-3 text-amber-500" /> {p}
                        </div>
                      ))}
                    </div>
                  )}

                  {compReport.analysis?.content_categories?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">内容分布</p>
                      <div className="space-y-1">
                        {compReport.analysis.content_categories.map((cat, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="w-20 text-gray-600">{cat.name}</span>
                            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-violet-500 rounded-full"
                                style={{ width: `${cat.percentage}%` }}
                              />
                            </div>
                            <span className="w-8 text-right text-gray-400">{cat.percentage}%</span>
                            <Badge
                              color={
                                cat.effectiveness === 'high'
                                  ? 'green'
                                  : cat.effectiveness === 'medium'
                                    ? 'amber'
                                    : 'red'
                              }
                            >
                              {cat.effectiveness}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {compReport.analysis?.recommendations?.length > 0 && (
                    <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                      <p className="text-xs font-medium text-emerald-700 mb-1">差异化建议</p>
                      {compReport.analysis.recommendations.map((r, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-1.5 text-xs text-emerald-800 py-0.5"
                        >
                          <Zap className="w-3 h-3 text-emerald-500" /> {r}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════ SEO评分 ═══════════════════ */}
      {tab === 'seo' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* SEO 评分 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Search className="w-4 h-4 text-blue-500" /> 内容SEO分析
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                value={seoTitle}
                onChange={(e) => setSeoTitle(e.target.value)}
                placeholder="文章标题"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <input
                type="text"
                value={seoKeyword}
                onChange={(e) => setSeoKeyword(e.target.value)}
                placeholder="目标关键词（可选）"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <textarea
                value={seoContent}
                onChange={(e) => setSeoContent(e.target.value)}
                placeholder="文章正文（至少50字）…"
                rows={8}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none resize-none"
              />
              <Button
                variant="primary"
                icon={Search}
                loading={seoLoading}
                onClick={runSeoAnalyze}
                className="w-full"
              >
                SEO 评分分析
              </Button>
            </div>
          </Card>

          <div className="space-y-4">
            {seoResult && (
              <Card>
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-14 h-14 rounded-full flex items-center justify-center text-white text-xl font-bold ${
                      (seoResult.overall_score || 0) >= 90
                        ? 'bg-emerald-500'
                        : (seoResult.overall_score || 0) >= 80
                          ? 'bg-blue-500'
                          : (seoResult.overall_score || 0) >= 70
                            ? 'bg-amber-500'
                            : (seoResult.overall_score || 0) >= 60
                              ? 'bg-orange-500'
                              : 'bg-red-500'
                    }`}
                  >
                    {seoResult.overall_score || '-'}
                  </div>
                  <div>
                    <div className="text-lg font-bold text-gray-900">SEO综合评分</div>
                    <div className="text-xs text-gray-500">{seoResult.summary}</div>
                  </div>
                  <Badge
                    className="ml-auto"
                    color={
                      seoResult.grade === 'A+' || seoResult.grade === 'A'
                        ? 'green'
                        : seoResult.grade === 'B'
                          ? 'amber'
                          : 'red'
                    }
                  >
                    {seoResult.grade}
                  </Badge>
                </div>

                {seoResult.dimensions?.map((d, i) => (
                  <div key={i} className="flex items-center gap-2 py-1.5 text-xs">
                    <span className="w-20 text-gray-600">{d.name}</span>
                    <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          d.score >= 90
                            ? 'bg-emerald-500'
                            : d.score >= 80
                              ? 'bg-blue-500'
                              : d.score >= 70
                                ? 'bg-amber-500'
                                : 'bg-red-500'
                        }`}
                        style={{ width: `${d.score}%` }}
                      />
                    </div>
                    <span className="w-8 text-right font-bold text-gray-700">{d.score}</span>
                    <span className="text-gray-400 hidden lg:inline">
                      {d.comment?.slice(0, 20)}
                    </span>
                  </div>
                ))}

                {seoResult.improvements?.length > 0 && (
                  <div className="mt-3 space-y-1.5">
                    <p className="text-xs font-medium text-gray-500">改进项</p>
                    {seoResult.improvements.map((imp, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-xs p-2 rounded-lg bg-gray-50"
                      >
                        <Badge
                          color={
                            imp.priority === 'high'
                              ? 'red'
                              : imp.priority === 'medium'
                                ? 'amber'
                                : 'green'
                          }
                        >
                          {imp.priority}
                        </Badge>
                        <div>
                          <span className="text-gray-700">{imp.issue}</span>
                          <span className="text-gray-400 ml-1">→ {imp.suggestion}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {seoResult.optimized_title_suggestions?.length > 0 && (
                  <div className="mt-3 p-2 rounded-lg bg-blue-50 border border-blue-200">
                    <p className="text-xs font-medium text-blue-700 mb-1">优化标题建议</p>
                    {seoResult.optimized_title_suggestions.map((t, i) => (
                      <div key={i} className="text-xs text-blue-800 py-0.5">
                        {i + 1}. {t}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}

            {/* 关键词研究 */}
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Crosshair className="w-4 h-4 text-emerald-500" /> 关键词研究
              </h3>
              <div className="space-y-2">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={kwSeed}
                    onChange={(e) => setKwSeed(e.target.value)}
                    placeholder="种子词，如：AI工具"
                    className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                  />
                  <input
                    type="text"
                    value={kwIndustry}
                    onChange={(e) => setKwIndustry(e.target.value)}
                    placeholder="行业（可选）"
                    className="w-32 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                  />
                </div>
                <Button
                  variant="primary"
                  icon={Search}
                  loading={kwLoading}
                  onClick={runKeywordResearch}
                  className="w-full"
                >
                  关键词研究
                </Button>
              </div>

              {kwResult && (
                <div className="mt-3 space-y-3">
                  {kwResult.related_keywords?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">相关词</p>
                      <div className="flex flex-wrap gap-1.5">
                        {kwResult.related_keywords.map((k, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded-full bg-gray-100 text-xs text-gray-700"
                          >
                            {k.keyword}{' '}
                            <span className="text-gray-400">
                              {k.search_volume}/{k.competition}
                            </span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {kwResult.long_tail_keywords?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">长尾词</p>
                      <div className="space-y-1">
                        {kwResult.long_tail_keywords.map((k, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="text-gray-700">{k.keyword}</span>
                            <Badge color="blue">{k.intent}</Badge>
                            <span className="text-gray-400">难度：{k.difficulty}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {kwResult.question_keywords?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">问题型关键词</p>
                      {kwResult.question_keywords.slice(0, 4).map((q, i) => (
                        <div key={i} className="text-xs text-gray-700 py-0.5">
                          Q: {q.question}
                        </div>
                      ))}
                    </div>
                  )}
                  {kwResult.content_suggestions && (
                    <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-700">
                      {kwResult.content_suggestions}
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
      <Modal open={schedModal} onClose={() => setSchedModal(false)} title="批量创建排期" size="sm">
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            将为已勾选的 <span className="font-semibold text-violet-600">{selectedCount}</span>{' '}
            条变体创建发布排期。
          </p>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">排期间隔（分钟）</label>
            <input
              type="number"
              min={10}
              max={1440}
              value={schedInterval}
              onChange={(e) => setSchedInterval(Number(e.target.value) || 60)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
            />
            <p className="text-[10px] text-gray-400 mt-0.5">
              如间隔 60 分钟，3 条变体将在 3 小时内依次自动发布
            </p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              首条发布时间（可选）
            </label>
            <input
              type="datetime-local"
              value={schedStart}
              min={new Date().toISOString().slice(0, 16)}
              onChange={(e) => setSchedStart(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
            />
            <p className="text-[10px] text-gray-400 mt-0.5">不填则从现在 + 5 分钟后开始</p>
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" onClick={() => setSchedModal(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              icon={CalendarPlus}
              loading={schedLoading}
              onClick={batchSchedule}
            >
              确认排期
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
