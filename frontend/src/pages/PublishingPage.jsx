import React, { useState, useEffect } from 'react'
import {
  Send,
  Copy,
  Check,
  Sparkles,
  Clock,
  Settings2,
  Plus,
  Trash2,
  TestTube2,
  Upload,
  FileText,
  Image as ImageIcon,
  Film,
  Tag,
  Link2,
  Download,
  ExternalLink,
  MessageSquare,
  Music2,
  Clapperboard,
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  Calendar,
  CalendarPlus,
  BarChart3,
  Play,
  TrendingUp,
  ChevronLeft,
  ChevronRight,
  PieChart,
  Search,
  CheckSquare,
  Square,
  X,
  ShieldCheck,
  Clock3,
  ArrowRight,
  ClipboardCheck,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
} from 'lucide-react'
import { Card, Button, Badge, Empty, PageHeader, Modal } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api, { API_BASE } from '../lib/api'

const PLATFORMS = [
  {
    value: 'wechat',
    label: '微信公众号',
    icon: MessageSquare,
    color: 'from-emerald-500 to-green-600',
    border: 'border-emerald-200 bg-emerald-50',
    text: 'text-emerald-600',
    desc: '图文 / 图片 / 视频',
    auto: '图文支持自动发布（AppID/Secret）',
  },
  {
    value: 'douyin',
    label: '抖音',
    icon: Clapperboard,
    color: 'from-gray-700 to-gray-900',
    border: 'border-gray-200 bg-gray-50',
    text: 'text-gray-700',
    desc: '图片 / 视频',
    auto: '图片视频支持自动发布（开放平台审核后）',
  },
  {
    value: 'kuaishou',
    label: '快手',
    icon: Music2,
    color: 'from-orange-500 to-amber-600',
    border: 'border-orange-200 bg-orange-50',
    text: 'text-orange-600',
    desc: '图片 / 视频',
    auto: '图片视频支持自动发布（开放平台审核后）',
  },
]

const CONTENT_TYPES = [
  { value: 'article', label: '图文', icon: FileText },
  { value: 'image', label: '图片', icon: ImageIcon },
  { value: 'video', label: '视频', icon: Film },
]

const MODE_BADGE = {
  guide: { label: '引导式', color: 'blue' },
  auto: { label: '自动发布', color: 'green' },
  guide_fallback: { label: '自动失败·已回退', color: 'amber' },
}

const STATUS_BADGE = {
  pending: { label: '待发布', color: 'amber' },
  success: { label: '已发布', color: 'green' },
  failed: { label: '失败', color: 'red' },
}

function assetFull(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return API_BASE + url
}

const TABS = [
  { key: 'workbench', label: '发布工作台', icon: Send },
  { key: 'calendar', label: '排期日历', icon: Calendar },
  { key: 'stats', label: '数据看板', icon: BarChart3 },
  { key: 'records', label: '发布记录', icon: Clock },
  { key: 'review', label: '审核队列', icon: ClipboardCheck },
  { key: 'accounts', label: '账号配置', icon: Settings2 },
]

const SCHEDULE_STATUS_BADGE = {
  pending: { label: '待发布', color: 'amber', dot: 'bg-amber-400' },
  published: { label: '已发布', color: 'green', dot: 'bg-emerald-400' },
  cancelled: { label: '已取消', color: 'gray', dot: 'bg-gray-300' },
}

// ── 排期日历工具 ──────────────────────────────────────────────
function buildCalendar(year, month) {
  // month 0-based
  const startDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < startDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}

function fmtDay(iso) {
  return iso ? iso.slice(0, 10) : ''
}

export default function PublishingPage() {
  const toast = useToast()
  const [tab, setTab] = useState('workbench')

  // ── 发布工作台状态 ──
  const [assets, setAssets] = useState({ articles: [], media: [] })
  const [assetTab, setAssetTab] = useState('articles')
  const [platforms, setPlatforms] = useState(['wechat'])
  const [contentType, setContentType] = useState('article')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [topicInput, setTopicInput] = useState('')
  const [topics, setTopics] = useState([])
  const [selectedAssets, setSelectedAssets] = useState([]) // [{url, name, type}]
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copiedKey, setCopiedKey] = useState('')

  // ── 记录筛选 ──
  const [recPlatform, setRecPlatform] = useState('')
  const [recStatus, setRecStatus] = useState('')
  const [recQ, setRecQ] = useState('')

  // ── 记录 / 账号 ──
  const [records, setRecords] = useState([])
  const [accounts, setAccounts] = useState([])
  const [accountsLoaded, setAccountsLoaded] = useState(false)
  const [accForm, setAccForm] = useState({
    platform: 'wechat',
    name: '',
    app_id: '',
    app_secret: '',
  })
  const [testingId, setTestingId] = useState('')
  const [detail, setDetail] = useState(null)
  const [batchModal, setBatchModal] = useState(false)
  const [batchText, setBatchText] = useState('')
  const [batchLoading, setBatchLoading] = useState(false)

  // ── 审核队列 ──
  const [reviewList, setReviewList] = useState([])
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewingId, setReviewingId] = useState('')
  const [reviewNote, setReviewNote] = useState('')
  const [reviewTarget, setReviewTarget] = useState(null) // {record, action}

  // ── 合规预检 + 最佳时间 ──
  const [complianceResult, setComplianceResult] = useState(null)
  const [complianceModal, setComplianceModal] = useState(false)
  const [pendingSubmit, setPendingSubmit] = useState(null)
  const [bestTimes, setBestTimes] = useState(null)
  const [, setBestTimeLoading] = useState(false)

  const checkCompliance = async () => {
    try {
      const res = await api.post('/api/strategy/compliance-check', { title, content })
      return res.data
    } catch {
      return null
    }
  }

  const loadBestTime = async (p = platforms[0]) => {
    setBestTimeLoading(true)
    try {
      const res = await api.get(`/api/strategy/best-time?platform=${p}`)
      setBestTimes(res.data?.top_slots?.slice(0, 3) || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    } finally {
      setBestTimeLoading(false)
    }
  }

  // 素材包 ZIP 一键下载（README 步骤 + 正文 + 全部素材文件）
  const downloadPackage = async () => {
    if (!detail) return
    try {
      const res = await api.get(`/api/publish/records/${detail.id}/package`, {
        responseType: 'blob',
        timeout: 60000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `publish_package_${detail.id.slice(-6)}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('素材包已下载（README 发布步骤 + 文案 + 素材文件）')
    } catch (e) {
      toast.error(`素材包下载失败：${e.message}`)
    }
  }

  // ── 排期日历 / 数据看板 ──
  const now = new Date()
  const [calMonth, setCalMonth] = useState(
    `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  )
  const [schedules, setSchedules] = useState([])
  const [stats, setStats] = useState(null)
  const [schedModal, setSchedModal] = useState(null) // { date }
  const [schedAssets, setSchedAssets] = useState([]) // 排期弹窗内选择的素材
  const [schedForm, setSchedForm] = useState({
    platform: 'wechat',
    content_type: 'article',
    title: '',
    content: '',
    scheduled_at: '',
    topics: [],
    topic_input: '',
  })
  const [executingId, setExecutingId] = useState('')

  // ── 排期批量操作 ──
  const [schedSelected, setSchedSelected] = useState(new Set())
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    if (tab !== 'records') return
    const t = setTimeout(() => loadRecords(), recQ ? 300 : 0)
    return () => clearTimeout(t)
  }, [tab, recPlatform, recStatus, recQ])
  useEffect(() => {
    if (tab === 'accounts') loadAccounts()
  }, [tab])
  useEffect(() => {
    if (tab === 'review') loadReviewQueue()
  }, [tab])
  useEffect(() => {
    if (tab === 'calendar') {
      loadSchedules()
    }
  }, [tab, calMonth])
  useEffect(() => {
    if (tab === 'stats') {
      loadStats()
      loadSchedules()
    }
  }, [tab])

  const loadSchedules = async () => {
    try {
      const res = await api.get(`/api/publish/schedules?month=${calMonth}`)
      setSchedules(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }
  const loadStats = async () => {
    try {
      const res = await api.get('/api/publish/stats')
      setStats(res.data || null)
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  useEffect(() => {
    loadAssets()
    loadStats()
    loadAccounts() // 顶部「已配置账号」统计依赖账号数据，mount 即加载（避免切 Tab 才刷新的时序差异）
  }, [])

  const loadAssets = async () => {
    try {
      const res = await api.get('/api/publish/assets')
      setAssets(res.data || { articles: [], media: [] })
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }
  const loadRecords = async () => {
    try {
      const params = new URLSearchParams()
      if (recPlatform) params.set('platform', recPlatform)
      if (recStatus) params.set('status', recStatus)
      if (recQ.trim()) params.set('q', recQ.trim())
      const res = await api.get(`/api/publish/records?${params.toString()}`)
      setRecords(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }
  const loadAccounts = async () => {
    try {
      const res = await api.get('/api/publish/accounts')
      setAccounts(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    } finally {
      // 无论成败都标记加载完成：顶部统计避免一直显示占位 "-"
      setAccountsLoaded(true)
    }
  }

  // 平台多选切换
  const togglePlatform = (p) => {
    setPlatforms((prev) => {
      if (prev.includes(p)) {
        if (prev.length <= 1) return prev // 至少保留一个平台
        return prev.filter((x) => x !== p)
      }
      return [...prev, p]
    })
  }

  // 使用素材库中的文章
  const loadArticle = (a) => {
    setTitle(a.title || '')
    setContent(a.result || a.prompt || '')
    setContentType('article')
    toast.success(`已加载文章：${(a.title || a.prompt || '').slice(0, 20)}`)
  }

  // 添加媒体素材
  const addMedia = (m) => {
    const url = m.url || m.media_url
    if (!url) return
    if (selectedAssets.some((s) => s.url === url)) {
      toast.error('该素材已在列表中')
      return
    }
    const type = m.type === 'video' ? 'video' : 'image'
    setSelectedAssets((prev) => [
      ...prev,
      {
        url,
        name: url.split('/').pop(),
        type,
        thumbnail: m.thumbnail || (type === 'image' ? url : ''),
      },
    ])
    setContentType(type)
    toast.success(`已加入素材：${url.split('/').pop()}`)
  }

  const removeAsset = (url) => setSelectedAssets((prev) => prev.filter((s) => s.url !== url))

  const addTopic = () => {
    const t = topicInput.trim().replace(/^#/, '')
    if (!t) return
    if (topics.includes(t)) {
      toast.error('话题已存在')
      return
    }
    setTopics((prev) => [...prev, t])
    setTopicInput('')
  }

  // ── 审核队列操作 ──
  const loadReviewQueue = async () => {
    setReviewLoading(true)
    try {
      const res = await api.get('/api/publish/review-queue')
      setReviewList(res.data || [])
    } catch (e) {
      toast.error(`审核队列加载失败：${e.message}`)
    } finally {
      setReviewLoading(false)
    }
  }

  const handleReview = async () => {
    if (!reviewTarget) return
    setReviewingId(reviewTarget.record.id)
    try {
      const res = await api.put(`/api/publish/records/${reviewTarget.record.id}/review`, {
        action: reviewTarget.action,
        note: reviewNote.trim(),
      })
      toast.success(res.data?.message || '审核完成')
      setReviewTarget(null)
      setReviewNote('')
      loadReviewQueue()
    } catch (e) {
      toast.error(`审核失败：${e.message}`)
    } finally {
      setReviewingId('')
    }
  }

  const submit = async () => {
    if (!title.trim() && contentType !== 'image') {
      toast.error('请填写标题')
      return
    }
    if (contentType === 'article' && !content.trim()) {
      toast.error('请填写正文内容（可直接从素材库加载文章）')
      return
    }
    if (selectedAssets.length === 0 && contentType !== 'article') {
      toast.error('请从素材库选择要发布的图片/视频')
      return
    }

    // 合规预检
    const comp = await checkCompliance()
    const payload = {
      content_type: contentType,
      title,
      content,
      topics,
      asset_urls: selectedAssets.map((s) => s.url),
    }
    if (comp && comp.risk === 'high') {
      setComplianceResult(comp)
      setComplianceModal(true)
      setPendingSubmit({ platforms, ...payload })
      return
    }
    if (comp && comp.risk !== 'safe') {
      setComplianceResult(comp)
    }

    if (platforms.length > 1) {
      await doCrossPost(payload)
    } else {
      await doSubmit({ platform: platforms[0], ...payload })
    }
  }

  const doSubmit = async (payload) => {
    setLoading(true)
    setResult(null)
    setComplianceResult(null)
    try {
      const res = await api.post('/api/publish/submit', payload)
      setResult(res.data)
      loadRecords()
      toast.success(res.data.mode === 'auto' ? '已自动发布成功' : '素材包已生成')
    } catch (e) {
      toast.error(`发布失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const doCrossPost = async (payload) => {
    setLoading(true)
    setResult(null)
    setComplianceResult(null)
    try {
      const res = await api.post('/api/publish/cross-post', { platforms, ...payload })
      setResult(res.data)
      loadRecords()
      toast.success(res.data.message || `已向 ${res.data.success}/${res.data.total} 个平台提交发布`)
    } catch (e) {
      toast.error(`跨平台发布失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const confirmRiskySubmit = () => {
    setComplianceModal(false)
    if (pendingSubmit) {
      const { platforms: pts, ...payload } = pendingSubmit
      if (pts && pts.length > 1) {
        doCrossPost(payload)
      } else {
        doSubmit({ platform: pts ? pts[0] : platforms[0], ...payload })
      }
      setPendingSubmit(null)
    }
  }

  const copy = async (text, key) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(key)
      setTimeout(() => setCopiedKey(''), 1500)
    } catch {
      toast.error('复制失败')
    }
  }

  // ── 账号操作 ──
  const saveAccount = async () => {
    if (!accForm.platform) {
      toast.error('请选择平台')
      return
    }
    try {
      const res = await api.post('/api/publish/accounts', accForm)
      toast.success(res.data.configured ? '账号已配置' : '账号已保存（未填完整凭据）')
      setAccForm({ platform: 'wechat', name: '', app_id: '', app_secret: '' })
      loadAccounts()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const testAccount = async (id) => {
    setTestingId(id)
    try {
      const res = await api.post(`/api/publish/accounts/${id}/test`)
      toast.success(res.data.message || '连接成功')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setTestingId('')
    }
  }

  const deleteAccount = async (id) => {
    try {
      await api.delete(`/api/publish/accounts/${id}`)
      loadAccounts()
      toast.success('账号已删除')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const batchImportAccounts = async () => {
    if (!batchText.trim()) {
      toast.error('请输入账号信息')
      return
    }
    setBatchLoading(true)
    try {
      const res = await api.post('/api/publish/accounts/batch', {
        platform: accForm.platform,
        lines: batchText.trim(),
      })
      toast.success(
        `批量导入完成：成功 ${res.data.count} 个${res.data.skipped?.length ? `，跳过 ${res.data.skipped.length} 个` : ''}`
      )
      setBatchModal(false)
      setBatchText('')
      loadAccounts()
    } catch (e) {
      toast.error(`批量导入失败：${e.message}`)
    } finally {
      setBatchLoading(false)
    }
  }

  // ── 排期操作 ──
  const openSchedModal = (date) => {
    setSchedForm({
      platform: 'wechat',
      content_type: 'article',
      title: '',
      content: '',
      scheduled_at: `${date}T09:00`,
      topics: [],
      topic_input: '',
    })
    setSchedAssets([])
    setSchedModal({ date })
  }

  const addSchedTopic = () => {
    const t = schedForm.topic_input.trim().replace(/^#/, '')
    if (!t) return
    if (schedForm.topics.includes(t)) {
      toast.error('话题已存在')
      return
    }
    setSchedForm({ ...schedForm, topics: [...schedForm.topics, t], topic_input: '' })
  }

  const createSchedule = async () => {
    if (!schedForm.title.trim() && schedForm.content_type !== 'image') {
      toast.error('请填写标题')
      return
    }
    if (!schedForm.scheduled_at) {
      toast.error('请选择计划发布时间')
      return
    }
    try {
      await api.post('/api/publish/schedules', {
        platform: schedForm.platform,
        content_type: schedForm.content_type,
        title: schedForm.title,
        content: schedForm.content,
        topics: schedForm.topics,
        asset_urls: schedAssets.map((s) => s.url),
        scheduled_at: schedForm.scheduled_at,
      })
      toast.success('排期已创建，到点后一键执行发布')
      setSchedModal(null)
      loadSchedules()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const executeSchedule = async (id) => {
    setExecutingId(id)
    try {
      const res = await api.post(`/api/publish/schedules/${id}/execute`)
      toast.success(res.data.mode === 'auto' ? '排期已自动发布成功' : '排期已执行，素材包已生成')
      loadSchedules()
      loadRecords()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setExecutingId('')
    }
  }

  const cancelSchedule = async (id) => {
    if (!window.confirm('确定取消这条排期吗？')) return
    try {
      await api.delete(`/api/publish/schedules/${id}`)
      toast.success('排期已取消')
      loadSchedules()
    } catch (e) {
      toast.error(e.message)
    }
  }

  // ── 排期批量取消 ──
  const toggleSchedSelect = (id) => {
    setSchedSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAllSched = () => {
    const pendings = schedules.filter((s) => s.status === 'pending')
    setSchedSelected((prev) =>
      prev.size === pendings.length ? new Set() : new Set(pendings.map((s) => s.id))
    )
  }

  const batchCancel = async () => {
    if (schedSelected.size === 0) return
    if (!window.confirm(`确定批量取消选中的 ${schedSelected.size} 条排期吗？`)) return
    setCancelling(true)
    try {
      const res = await api.post('/api/publish/schedules/batch-cancel', { ids: [...schedSelected] })
      toast.success(`已取消 ${res.data.cancelled} 条排期`)
      setSchedSelected(new Set())
      loadSchedules()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setCancelling(false)
    }
  }

  const ctypeMeta = CONTENT_TYPES.find((c) => c.value === contentType)

  return (
    <div className="space-y-6">
      <PageHeader
        title="发布中心"
        description="文章、图片、视频一键发布到公众号 / 抖音 / 快手，支持引导式与自动发布"
        icon={Send}
        iconColor="from-blue-500 to-indigo-600"
      />

      {/* 统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: '可发布文章',
            value: assets.articles?.length || 0,
            icon: FileText,
            color: 'from-blue-500 to-indigo-600',
          },
          {
            label: '图片视频素材',
            value: assets.media?.length || 0,
            icon: Film,
            color: 'from-pink-500 to-rose-600',
          },
          {
            label: '发布总次数',
            value: stats?.total ?? records.length,
            icon: Send,
            color: 'from-emerald-500 to-teal-600',
          },
          {
            label: '已配置账号',
            value: accountsLoaded ? accounts.filter((a) => a.configured).length : '-',
            icon: Settings2,
            color: 'from-amber-500 to-orange-600',
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
                <div className="text-xl font-bold text-gray-900">{s.value}</div>
                <div className="text-xs text-gray-500">{s.label}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tab 切换 */}
      <div className="flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === t.key
                ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-soft'
                : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'workbench' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── 左列：发布设置 ── */}
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Send className="w-4 h-4 text-blue-500" /> 发布设置
              </h3>
              {/* 内容类型 */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-3">
                {CONTENT_TYPES.map((c) => (
                  <button
                    key={c.value}
                    onClick={() => setContentType(c.value)}
                    className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg text-xs border transition-all ${
                      contentType === c.value
                        ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium shadow-sm'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <c.icon className="w-4 h-4" /> {c.label}
                  </button>
                ))}
              </div>
              {/* 标题 */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">标题</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={contentType === 'image' ? '图片描述（可选）' : '文章 / 视频标题'}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                />
              </div>
              {/* 正文 */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  正文 / 文案 <span className="text-gray-400">（{content.length} 字）</span>
                </label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder={
                    contentType === 'article'
                      ? '文章正文，可在右侧素材库一键加载历史文章…'
                      : '配文文案，可在文案工厂生成后粘贴…'
                  }
                  rows={7}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                />
              </div>
              {/* 话题 */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  话题标签（回车添加）
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={topicInput}
                    onChange={(e) => setTopicInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addTopic()
                      }
                    }}
                    placeholder="如：AI工具 效率办公"
                    className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                  />
                  <Button variant="secondary" size="sm" icon={Plus} onClick={addTopic}>
                    添加
                  </Button>
                </div>
                {topics.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {topics.map((t, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700"
                      >
                        #{t}
                        <button
                          onClick={() => setTopics(topics.filter((_, j) => j !== i))}
                          className="text-blue-300 hover:text-red-500"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {/* 已选素材 */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  发布素材（{selectedAssets.length}）
                </label>
                {selectedAssets.length === 0 ? (
                  <div className="px-3 py-3 rounded-lg border-2 border-dashed border-gray-200 text-center text-xs text-gray-400">
                    尚未选择素材，请从右侧素材库点击「加入素材」
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {selectedAssets.map((s) => (
                      <div
                        key={s.url}
                        className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-gray-50 border border-gray-100"
                      >
                        {s.thumbnail ? (
                          <img
                            src={assetFull(s.thumbnail)}
                            alt=""
                            className="w-8 h-8 rounded object-cover flex-shrink-0"
                          />
                        ) : s.type === 'video' ? (
                          <Film className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        ) : (
                          <ImageIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        )}
                        <span className="flex-1 text-xs text-gray-700 truncate">{s.name}</span>
                        <button
                          onClick={() => removeAsset(s.url)}
                          className="text-gray-300 hover:text-red-500"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>

            {/* 平台选择（多选） */}
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <ExternalLink className="w-4 h-4 text-indigo-500" /> 发布到（可多选）
              </h3>
              <div className="space-y-2">
                {PLATFORMS.map((p) => {
                  const selected = platforms.includes(p.value)
                  return (
                    <button
                      key={p.value}
                      onClick={() => togglePlatform(p.value)}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left ${
                        selected
                          ? `${p.border} ring-2 ring-blue-500/20`
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div
                        className={`w-9 h-9 rounded-lg bg-gradient-to-br ${p.color} flex items-center justify-center flex-shrink-0`}
                      >
                        <p.icon className="w-4.5 h-4.5 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">{p.label}</div>
                        <div className="text-xs text-gray-500">{p.desc}</div>
                      </div>
                      {selected ? (
                        <CheckSquare className={`w-4 h-4 ${p.text} flex-shrink-0`} />
                      ) : (
                        <Square className="w-4 h-4 text-gray-300 flex-shrink-0" />
                      )}
                    </button>
                  )
                })}
              </div>
              <div className="mt-3 px-3 py-2.5 rounded-lg bg-indigo-50 border border-indigo-100 text-xs text-indigo-600 flex items-start gap-2">
                <Sparkles className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <span>
                  已选 {platforms.length} 个平台：
                  {platforms.map((p) => PLATFORMS.find((x) => x.value === p)?.label).join('、')} ·
                  内容类型：{ctypeMeta.label}。多选时将调用跨平台一键分发。
                </span>
              </div>
            </Card>

            <Button
              variant="primary"
              size="lg"
              icon={Send}
              loading={loading}
              onClick={submit}
              className="w-full"
            >
              {loading
                ? '发布中…'
                : platforms.length > 1
                  ? `一键分发到 ${platforms.length} 个平台`
                  : '一键发布'}
            </Button>
          </div>

          {/* ── 右列：素材库 + 结果 ── */}
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" /> 素材库
                <span className="text-xs font-normal text-gray-400">
                  点击文章「加载正文」或图片视频「加入素材」
                </span>
              </h3>
              <div className="flex gap-2 mb-4">
                {[
                  {
                    key: 'articles',
                    label: `文章（${assets.articles?.length || 0}）`,
                    icon: FileText,
                  },
                  { key: 'media', label: `图片视频（${assets.media?.length || 0}）`, icon: Film },
                ].map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setAssetTab(t.key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      assetTab === t.key
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    <t.icon className="w-3.5 h-3.5" /> {t.label}
                  </button>
                ))}
              </div>

              {assetTab === 'articles' ? (
                assets.articles?.length ? (
                  <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                    {assets.articles.map((a) => (
                      <div
                        key={a.id}
                        className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50/40 transition-all"
                      >
                        <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                          <FileText className="w-4 h-4 text-blue-500" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">
                            {a.title || a.prompt?.slice(0, 40) || '未命名文章'}
                          </div>
                          <div className="text-xs text-gray-400 truncate">
                            {(a.result || a.prompt || '').slice(0, 80)}
                          </div>
                        </div>
                        <span className="text-xs text-gray-400 flex-shrink-0">
                          {a.created_at?.slice(0, 10)}
                        </span>
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={FileText}
                          onClick={() => loadArticle(a)}
                        >
                          加载正文
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty
                    icon={FileText}
                    title="暂无历史文章"
                    description="到「文案工厂」生成文章后会自动出现在这里"
                  />
                )
              ) : assets.media?.length ? (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 max-h-72 overflow-y-auto pr-1">
                  {assets.media.map((m) => (
                    <div
                      key={m.id}
                      className="group relative rounded-xl overflow-hidden border border-gray-200 bg-gray-50"
                    >
                      {m.type === 'image' ? (
                        <img src={assetFull(m.url)} alt="" className="w-full h-28 object-cover" />
                      ) : m.thumbnail ? (
                        <img
                          src={assetFull(m.thumbnail)}
                          alt=""
                          className="w-full h-28 object-cover"
                        />
                      ) : (
                        <div className="w-full h-28 flex items-center justify-center bg-gradient-to-br from-gray-800 to-gray-900">
                          <Film className="w-8 h-8 text-white/70" />
                        </div>
                      )}
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={Plus}
                          onClick={() => addMedia(m)}
                        >
                          加入素材
                        </Button>
                      </div>
                      <div className="px-2 py-1.5 text-[11px] text-gray-500 truncate bg-white">
                        {m.url?.split('/').pop()}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty
                  icon={Film}
                  title="暂无图片视频素材"
                  description="到「图片工厂」「视频工厂」生成素材后会自动出现在这里"
                />
              )}
            </Card>

            {/* 发布结果 */}
            {result && !result.results && (
              <Card
                className={
                  result.mode === 'auto'
                    ? 'border-emerald-200'
                    : result.mode === 'guide_fallback'
                      ? 'border-amber-200'
                      : 'border-blue-200'
                }
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    {result.mode === 'auto' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    ) : result.mode === 'guide_fallback' ? (
                      <AlertCircle className="w-4 h-4 text-amber-500" />
                    ) : (
                      <Sparkles className="w-4 h-4 text-blue-500" />
                    )}
                    发布结果
                  </h3>
                  <div className="flex items-center gap-2">
                    <ShareButton
                      content={`# 发布结果：${result.title || '未命名'}\n\n平台：${result.platform_label || '—'} · 内容类型：${result.content_type || '—'} · 模式：${MODE_BADGE[result.mode]?.label || result.mode}\n\n${result.content || ''}\n\n> 由小团智能平台发布中心生成 · ${new Date().toLocaleString()}`}
                      title="发布结果"
                      contentType="publishing"
                    />
                    <Badge color={MODE_BADGE[result.mode]?.color}>
                      {MODE_BADGE[result.mode]?.label}
                    </Badge>
                  </div>
                </div>

                {result.mode === 'auto' ? (
                  <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
                    <p className="font-medium flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" />
                      {result.message}
                    </p>
                    <p className="mt-1 text-xs text-emerald-600">
                      记录 ID：{result.record_id} · 平台帖子 ID：{result.platform_post_id}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div
                      className={`p-3 rounded-xl text-sm ${result.mode === 'guide_fallback' ? 'bg-amber-50 border border-amber-200 text-amber-800' : 'bg-blue-50 border border-blue-200 text-blue-800'}`}
                    >
                      <p className="font-medium">{result.message}</p>
                      <p className="mt-1 text-xs opacity-80">
                        发布目标：{result.platform_label} ·{' '}
                        {result.content_type === 'article' ? '图文' : result.content_type}
                      </p>
                    </div>

                    {/* 合规检测结果 */}
                    {complianceResult && complianceResult.risk !== 'safe' && (
                      <div
                        className={`p-3 rounded-xl text-sm ${
                          complianceResult.risk === 'high'
                            ? 'bg-red-50 border border-red-200'
                            : complianceResult.risk === 'medium'
                              ? 'bg-amber-50 border border-amber-200'
                              : 'bg-blue-50 border border-blue-100'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <ShieldCheck
                            className={`w-4 h-4 ${
                              complianceResult.risk === 'high'
                                ? 'text-red-500'
                                : complianceResult.risk === 'medium'
                                  ? 'text-amber-500'
                                  : 'text-blue-500'
                            }`}
                          />
                          <span
                            className={`font-medium ${
                              complianceResult.risk === 'high'
                                ? 'text-red-800'
                                : complianceResult.risk === 'medium'
                                  ? 'text-amber-800'
                                  : 'text-blue-700'
                            }`}
                          >
                            合规检测：{complianceResult.risk_label}（{complianceResult.total_hits}{' '}
                            处提示）
                          </span>
                        </div>
                        <p className="text-xs opacity-80">{complianceResult.message}</p>
                        {complianceResult.suggestions?.length > 0 && (
                          <div className="mt-2 space-y-0.5">
                            {complianceResult.suggestions.slice(0, 5).map((s, i) => (
                              <div key={i} className="text-xs flex items-center gap-1.5">
                                <span className="line-through text-red-400">{s.original}</span>
                                <ArrowRight className="w-3 h-3 text-gray-300" />
                                <span className="text-emerald-600">{s.suggest}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* 多平台适配说明 */}
                    {result.adapted?.note?.length > 0 && (
                      <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 text-sm">
                        <div className="flex items-center gap-2 mb-2">
                          <Sparkles className="w-4 h-4 text-purple-500" />
                          <span className="font-medium text-purple-800">智能适配</span>
                        </div>
                        <ul className="space-y-1">
                          {result.adapted.note.map((n, i) => (
                            <li key={i} className="flex items-start gap-2 text-xs text-purple-700">
                              <CheckCircle2 className="w-3 h-3 mt-0.5 flex-shrink-0 text-purple-400" />
                              <span>{n}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 标题 */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium text-gray-500">标题</label>
                        <button
                          onClick={() => copy(result.title, 'title')}
                          className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
                        >
                          {copiedKey === 'title' ? (
                            <Check className="w-3 h-3" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}{' '}
                          复制
                        </button>
                      </div>
                      <div className="px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-800">
                        {result.title || '（无）'}
                      </div>
                    </div>

                    {/* 正文 */}
                    {result.content && (
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="text-xs font-medium text-gray-500">
                            正文 / 文案（{result.content.length} 字）
                          </label>
                          <button
                            onClick={() => copy(result.content, 'content')}
                            className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
                          >
                            {copiedKey === 'content' ? (
                              <Check className="w-3 h-3" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}{' '}
                            复制全文
                          </button>
                        </div>
                        <div className="px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-800 whitespace-pre-wrap max-h-56 overflow-y-auto">
                          {result.content}
                        </div>
                      </div>
                    )}

                    {/* 话题 */}
                    {result.topics?.length > 0 && (
                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">话题</label>
                        <div className="flex flex-wrap gap-1.5">
                          {result.topics.map((t, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700"
                            >
                              #{t}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 素材下载 */}
                    {result.asset_urls?.length > 0 && (
                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">
                          素材文件（右键另存为下载）
                        </label>
                        <div className="space-y-1">
                          {result.asset_urls.map((u, i) => (
                            <a
                              key={i}
                              href={assetFull(u)}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-sm text-gray-700"
                            >
                              <Download className="w-3.5 h-3.5 text-gray-400" />
                              <span className="flex-1 truncate">{u.split('/').pop()}</span>
                              <Link2 className="w-3.5 h-3.5 text-gray-300" />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 发布步骤 */}
                    <div>
                      <label className="text-xs font-medium text-gray-500 block mb-2">
                        分步操作指引
                      </label>
                      <ol className="space-y-2">
                        {result.steps?.map((s, i) => (
                          <li key={i} className="flex gap-3 text-sm text-gray-700">
                            <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                              {i + 1}
                            </span>
                            <span>{s}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>
                )}
              </Card>
            )}

            {/* 跨平台分发结果 */}
            {result && result.results && (
              <Card className="border-indigo-200">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    <Send className="w-4 h-4 text-indigo-500" /> 跨平台分发结果
                  </h3>
                  <Badge color="indigo">
                    {result.success}/{result.total} 成功
                  </Badge>
                </div>
                <div className="p-3 rounded-xl bg-indigo-50 border border-indigo-200 text-sm text-indigo-800 mb-3">
                  {result.message}
                </div>
                <div className="space-y-2">
                  {result.results.map((r, i) => {
                    const pm = PLATFORMS.find((x) => x.value === r.platform)
                    return (
                      <div
                        key={i}
                        className={`p-3 rounded-xl border ${
                          r.status === 'success'
                            ? 'border-emerald-200 bg-emerald-50/50'
                            : r.status === 'pending'
                              ? 'border-blue-200 bg-blue-50/50'
                              : 'border-red-200 bg-red-50/50'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          {pm && (
                            <span
                              className={`w-6 h-6 rounded-md bg-gradient-to-br ${pm.color} flex items-center justify-center flex-shrink-0`}
                            >
                              <pm.icon className="w-3 h-3 text-white" />
                            </span>
                          )}
                          <span className="text-sm font-medium text-gray-800">
                            {pm?.label || r.platform}
                          </span>
                          <Badge
                            color={
                              r.status === 'success'
                                ? 'green'
                                : r.status === 'pending'
                                  ? 'blue'
                                  : 'red'
                            }
                          >
                            {r.status === 'success'
                              ? '已发布'
                              : r.status === 'pending'
                                ? '素材包'
                                : '失败'}
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-600">{r.message}</p>
                        {r.record_id && (
                          <p className="text-[10px] text-gray-400 mt-1">记录 ID：{r.record_id}</p>
                        )}
                      </div>
                    )
                  })}
                </div>
              </Card>
            )}
          </div>
        </div>
      )}

      {tab === 'calendar' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── 左列：日历 ── */}
          <div className="lg:col-span-2">
            <Card>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-indigo-500" /> 发布排期日历
                </h3>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => {
                      const [y, m] = calMonth.split('-').map(Number)
                      const d = new Date(y, m - 2, 1)
                      setCalMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
                    }}
                    className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="px-3 py-1 rounded-lg bg-indigo-50 text-indigo-700 text-sm font-medium">
                    {new Date(`${calMonth}-01`).toLocaleDateString('zh-CN', {
                      year: 'numeric',
                      month: 'long',
                    })}
                  </span>
                  <button
                    onClick={() => {
                      const [y, m] = calMonth.split('-').map(Number)
                      const d = new Date(y, m, 1)
                      setCalMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
                    }}
                    className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-7 gap-1 mb-1">
                {['日', '一', '二', '三', '四', '五', '六'].map((d, i) => (
                  <div
                    key={i}
                    className={`text-center text-xs font-medium py-1 ${i === 0 || i === 6 ? 'text-red-400' : 'text-gray-400'}`}
                  >
                    {d}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1">
                {buildCalendar(
                  Number(calMonth.split('-')[0]),
                  Number(calMonth.split('-')[1]) - 1
                ).map((day, i) => {
                  if (!day)
                    return (
                      <div
                        key={i}
                        className="h-20 rounded-xl border border-dashed border-gray-100"
                      />
                    )
                  const dayStr = `${calMonth}-${String(day).padStart(2, '0')}`
                  const dayScheds = schedules.filter((s) => fmtDay(s.scheduled_at) === dayStr)
                  const isToday = dayStr === new Date().toISOString().slice(0, 10)
                  return (
                    <button
                      key={i}
                      onClick={() => openSchedModal(dayStr)}
                      className={`h-20 rounded-xl border text-left p-1.5 transition-all hover:shadow-md group ${
                        isToday
                          ? 'border-indigo-300 bg-indigo-50/50'
                          : 'border-gray-100 hover:border-indigo-200 bg-white'
                      }`}
                    >
                      <div className={`flex items-center justify-between`}>
                        <span
                          className={`text-xs font-medium ${isToday ? 'text-indigo-600' : 'text-gray-500'}`}
                        >
                          {day}
                        </span>
                        <CalendarPlus className="w-3 h-3 text-gray-200 group-hover:text-indigo-400" />
                      </div>
                      <div className="mt-1 space-y-0.5">
                        {dayScheds.slice(0, 3).map((s) => (
                          <div key={s.id} className="flex items-center gap-1 min-w-0">
                            <span
                              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${SCHEDULE_STATUS_BADGE[s.status]?.dot || 'bg-gray-300'}`}
                            />
                            <span className="text-[10px] text-gray-500 truncate">
                              {s.scheduled_at?.slice(11, 16)}{' '}
                              {s.title || PLATFORMS.find((p) => p.value === s.platform)?.label}
                            </span>
                          </div>
                        ))}
                        {dayScheds.length > 3 && (
                          <span className="text-[10px] text-gray-400">
                            +{dayScheds.length - 3} 条
                          </span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
              <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-400" /> 待发布
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" /> 已发布
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-gray-300" /> 已取消
                </span>
                <span className="ml-auto text-gray-400">点击任意日期创建排期</span>
              </div>
            </Card>
          </div>

          {/* ── 右列：本月排期列表 ── */}
          <div>
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <CalendarPlus className="w-4 h-4 text-amber-500" /> 本月排期（{schedules.length}）
                </h3>
                <div className="flex items-center gap-2">
                  {schedules.some((s) => s.status === 'pending') && (
                    <button
                      onClick={toggleAllSched}
                      className="flex items-center gap-1 text-xs text-gray-500 hover:text-indigo-600 transition-all"
                    >
                      {schedSelected.size ===
                      schedules.filter((s) => s.status === 'pending').length ? (
                        <CheckSquare className="w-3.5 h-3.5" />
                      ) : (
                        <Square className="w-3.5 h-3.5" />
                      )}{' '}
                      全选
                    </button>
                  )}
                  {schedSelected.size > 0 && (
                    <Button
                      variant="danger"
                      size="sm"
                      icon={Trash2}
                      loading={cancelling}
                      onClick={batchCancel}
                    >
                      批量取消（{schedSelected.size}）
                    </Button>
                  )}
                </div>
              </div>
              {schedules.length === 0 ? (
                <Empty
                  icon={Calendar}
                  title="本月暂无排期"
                  description="点击日历上的日期创建发布排期"
                />
              ) : (
                <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
                  {schedules.map((s) => {
                    const p = PLATFORMS.find((x) => x.value === s.platform)
                    const isOverdue =
                      s.status === 'pending' && s.scheduled_at < new Date().toISOString()
                    return (
                      <div
                        key={s.id}
                        className={`p-3 rounded-xl border transition-all ${isOverdue ? 'border-red-200 bg-red-50/30' : 'border-gray-100 hover:border-indigo-200'} ${schedSelected.has(s.id) ? 'border-indigo-300 bg-indigo-50/40' : ''}`}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          {s.status === 'pending' && (
                            <button
                              onClick={() => toggleSchedSelect(s.id)}
                              className={`p-1 rounded-md transition-all ${schedSelected.has(s.id) ? 'bg-indigo-100 text-indigo-600' : 'text-gray-300 hover:text-indigo-500 hover:bg-gray-50'}`}
                              title={schedSelected.has(s.id) ? '取消选择' : '选择此排期'}
                            >
                              {schedSelected.has(s.id) ? (
                                <CheckSquare className="w-4 h-4" />
                              ) : (
                                <Square className="w-4 h-4" />
                              )}
                            </button>
                          )}
                          {p && (
                            <span
                              className={`w-6 h-6 rounded-md bg-gradient-to-br ${p.color} flex items-center justify-center flex-shrink-0`}
                            >
                              <p.icon className="w-3 h-3 text-white" />
                            </span>
                          )}
                          <Badge color={SCHEDULE_STATUS_BADGE[s.status]?.color || 'gray'}>
                            {SCHEDULE_STATUS_BADGE[s.status]?.label || s.status}
                          </Badge>
                          {isOverdue && (
                            <span className="text-[10px] text-red-500 font-medium">已到时间</span>
                          )}
                          <span className="text-xs text-gray-400 ml-auto">
                            {s.scheduled_at?.slice(5, 16).replace('T', ' ')}
                          </span>
                        </div>
                        <div className="text-sm font-medium text-gray-800 truncate mb-1">
                          {s.title || `（${s.content_label}发布）`}
                        </div>
                        {s.content && (
                          <div className="text-xs text-gray-400 truncate mb-2">
                            {s.content.slice(0, 60)}
                          </div>
                        )}
                        <div className="flex gap-1.5">
                          {s.status === 'pending' && (
                            <>
                              <Button
                                variant="primary"
                                size="sm"
                                icon={Play}
                                loading={executingId === s.id}
                                onClick={() => executeSchedule(s.id)}
                              >
                                执行发布
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                icon={Trash2}
                                onClick={() => cancelSchedule(s.id)}
                              >
                                取消
                              </Button>
                            </>
                          )}
                          {s.published_record_id && (
                            <span className="text-[11px] text-emerald-600 ml-auto">
                              记录 {s.published_record_id}
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}

      {tab === 'stats' && (
        <div className="space-y-6">
          {/* 核心指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              {
                label: '发布总次数',
                value: stats?.total ?? 0,
                sub: `成功率 ${stats?.success_rate ?? 0}%`,
                icon: Send,
                color: 'from-blue-500 to-indigo-600',
              },
              {
                label: '发布成功',
                value: stats?.success ?? 0,
                sub: '已发布到平台',
                icon: CheckCircle2,
                color: 'from-emerald-500 to-teal-600',
              },
              {
                label: '待发布',
                value: stats?.pending ?? 0,
                sub: '含失败待重试',
                icon: Clock,
                color: 'from-amber-500 to-orange-600',
              },
              {
                label: '未来排期',
                value: stats?.upcoming_schedules ?? 0,
                sub: stats?.overdue_schedules
                  ? `已到时间 ${stats.overdue_schedules} 条待执行`
                  : '已排定待执行',
                icon: Calendar,
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
                    <div className="text-xl font-bold text-gray-900">{s.value}</div>
                    <div className="text-xs text-gray-500">{s.label}</div>
                    <div
                      className={`text-[11px] ${stats?.overdue_schedules && i === 3 ? 'text-red-500' : 'text-gray-400'}`}
                    >
                      {s.sub}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* 发布状态分布 */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              {
                key: 'success',
                label: '发布成功',
                color: 'from-emerald-500 to-teal-600',
                bar: 'bg-emerald-500',
              },
              {
                key: 'failed',
                label: '发布失败',
                color: 'from-rose-500 to-pink-600',
                bar: 'bg-rose-500',
              },
              {
                key: 'pending',
                label: '待发布',
                color: 'from-amber-500 to-orange-600',
                bar: 'bg-amber-500',
              },
            ].map((s) => {
              const n = stats?.by_status?.[s.key] || 0
              const pct = stats?.total ? Math.round((n / stats.total) * 100) : 0
              return (
                <div key={s.key} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="flex items-center gap-2 text-sm text-gray-700">
                      <span className={`w-2.5 h-2.5 rounded-full bg-gradient-to-br ${s.color}`} />{' '}
                      {s.label}
                    </span>
                    <span className="text-sm font-bold text-gray-900">{n}</span>
                  </div>
                  <div className="h-2.5 rounded-full bg-gray-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${s.bar} transition-all duration-500`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-gray-400 mt-1.5">占比 {pct}%</p>
                </div>
              )
            })}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 平台分布 */}
            <Card>
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <PieChart className="w-4 h-4 text-blue-500" /> 平台分布
              </h3>
              {Object.keys(stats?.by_platform || {}).length === 0 ? (
                <Empty
                  icon={PieChart}
                  title="暂无发布数据"
                  description="发布内容后这里会展示各平台占比"
                />
              ) : (
                <div className="space-y-3">
                  {PLATFORMS.map((p) => {
                    const n = stats?.by_platform?.[p.value] || 0
                    const max = Math.max(...Object.values(stats?.by_platform || {}), 1)
                    return (
                      <div key={p.value}>
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span className="flex items-center gap-2 text-gray-700">
                            <span
                              className={`w-6 h-6 rounded-md bg-gradient-to-br ${p.color} flex items-center justify-center`}
                            >
                              <p.icon className="w-3 h-3 text-white" />
                            </span>
                            {p.label}
                          </span>
                          <span className="text-xs text-gray-400">{n} 次</span>
                        </div>
                        <div className="h-2.5 rounded-full bg-gray-100 overflow-hidden">
                          <div
                            className={`h-full rounded-full bg-gradient-to-r ${p.color} transition-all duration-500`}
                            style={{ width: `${(n / max) * 100}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Card>

            {/* 近 30 天趋势 */}
            <Card>
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-500" /> 近 30 天发布趋势
              </h3>
              {!stats?.trend_30d?.some((t) => t.count > 0) ? (
                <Empty
                  icon={TrendingUp}
                  title="近 30 天暂无发布"
                  description="持续发布后这里会显示趋势曲线"
                />
              ) : (
                <div className="flex items-end gap-[3px] h-36">
                  {stats.trend_30d.map((t, i) => {
                    const max = Math.max(...stats.trend_30d.map((x) => x.count), 1)
                    const h = Math.max((t.count / max) * 100, t.count > 0 ? 8 : 2)

                    return (
                      <div
                        key={i}
                        className="flex-1 flex flex-col items-center justify-end h-full group relative"
                      >
                        <div
                          className="w-full rounded-t bg-gradient-to-t from-indigo-500 to-blue-400 transition-all"
                          style={{ height: `${h}%`, opacity: t.count > 0 ? 1 : 0.15 }}
                        />
                        {t.count > 0 && (
                          <span className="absolute -top-5 text-[9px] text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity">
                            {t.count}
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
              <div className="flex justify-between text-[10px] text-gray-400 mt-2">
                <span>{stats?.trend_30d?.[0]?.date?.slice(5)}</span>
                <span>{stats?.trend_30d?.[29]?.date?.slice(5)}</span>
              </div>
            </Card>
          </div>
        </div>
      )}

      {tab === 'records' && (
        <Card>
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" /> 发布记录（{records.length}）
            </h3>
            <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
              <select
                value={recPlatform}
                onChange={(e) => setRecPlatform(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="">全部平台</option>
                {PLATFORMS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
              <select
                value={recStatus}
                onChange={(e) => setRecStatus(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="">全部状态</option>
                {Object.entries(STATUS_BADGE).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v.label}
                  </option>
                ))}
              </select>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                <input
                  value={recQ}
                  onChange={(e) => setRecQ(e.target.value)}
                  placeholder="搜索标题 / 内容…"
                  className="w-44 pl-8 pr-7 py-1.5 rounded-lg border border-gray-200 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                />
                {recQ && (
                  <button
                    onClick={() => setRecQ('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>
          {records.length === 0 ? (
            <Empty icon={Clock} title="暂无发布记录" description="发布内容后记录会展示在这里" />
          ) : (
            <div className="space-y-2">
              {records.map((r) => (
                <div
                  key={r.id}
                  className="p-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50/30 transition-all"
                >
                  <div className="flex items-center gap-3 flex-wrap">
                    <Badge color={PLATFORMS.find((p) => p.value === r.platform) ? 'green' : 'gray'}>
                      {PLATFORMS.find((p) => p.value === r.platform)?.label || r.platform_label}
                    </Badge>
                    <Badge color="blue">{r.content_label}</Badge>
                    <Badge color={MODE_BADGE[r.mode]?.color || 'gray'}>
                      {MODE_BADGE[r.mode]?.label || r.mode}
                    </Badge>
                    <Badge color={STATUS_BADGE[r.status]?.color || 'gray'}>
                      {STATUS_BADGE[r.status]?.label || r.status}
                    </Badge>
                    <span className="flex-1 text-sm text-gray-700 truncate min-w-0">
                      {r.title || '(无标题)'}
                    </span>
                    <span className="text-xs text-gray-400">
                      {r.created_at?.slice(0, 16).replace('T', ' ')}
                    </span>
                    <Button variant="ghost" size="sm" onClick={() => setDetail(r)}>
                      详情
                    </Button>
                  </div>
                  {r.error && <p className="mt-2 text-xs text-red-500 truncate">错误：{r.error}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {tab === 'review' && (
        <Card>
          <div className="flex items-center gap-3 mb-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <ClipboardCheck className="w-4 h-4 text-violet-500" /> 审核队列
              <Badge color="purple">{reviewList.length}</Badge>
            </h3>
            <Button variant="ghost" size="sm" onClick={loadReviewQueue} loading={reviewLoading}>
              刷新
            </Button>
          </div>
          {reviewList.length === 0 ? (
            <Empty
              icon={ClipboardCheck}
              title="队列已清空"
              description="待审核的发布内容会出现在这里，通过后进入发布流程"
            />
          ) : (
            <div className="space-y-2">
              {reviewList.map((r) => (
                <div
                  key={r.id}
                  className="p-4 rounded-xl border border-violet-100 bg-violet-50/30 hover:border-violet-300 transition-all"
                >
                  <div className="flex items-center gap-3 flex-wrap">
                    <Badge color={PLATFORMS.find((p) => p.value === r.platform) ? 'green' : 'gray'}>
                      {PLATFORMS.find((p) => p.value === r.platform)?.label || r.platform_label}
                    </Badge>
                    <Badge color="blue">{r.content_label}</Badge>
                    <Badge color="amber">待审核</Badge>
                    <span className="flex-1 text-sm text-gray-700 truncate min-w-0">
                      {r.title || '(无标题)'}
                    </span>
                    <span className="text-xs text-gray-400">
                      {r.created_at?.slice(0, 16).replace('T', ' ')}
                    </span>
                  </div>
                  {r.content && (
                    <p className="mt-2 text-xs text-gray-500 line-clamp-2">{r.content}</p>
                  )}
                  <div className="flex items-center gap-2 mt-3 pt-3 border-t border-violet-100">
                    <Button
                      size="sm"
                      variant="primary"
                      icon={ThumbsUp}
                      loading={reviewingId === r.id}
                      onClick={() => {
                        setReviewTarget({ record: r, action: 'approve' })
                        setReviewNote('')
                      }}
                    >
                      通过
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      icon={ThumbsDown}
                      loading={reviewingId === r.id}
                      onClick={() => {
                        setReviewTarget({ record: r, action: 'reject' })
                        setReviewNote('')
                      }}
                    >
                      驳回
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={RotateCcw}
                      onClick={() => {
                        setReviewTarget({ record: r, action: 'reset' })
                        setReviewNote('')
                      }}
                    >
                      重置为草稿
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* 审核操作弹窗 */}
      <Modal
        open={!!reviewTarget}
        onClose={() => setReviewTarget(null)}
        title={
          reviewTarget?.action === 'approve'
            ? '通过审核'
            : reviewTarget?.action === 'reject'
              ? '驳回内容'
              : '重置为草稿'
        }
      >
        <p className="text-sm text-gray-600 mb-4">
          {reviewTarget?.action === 'approve'
            ? `确认通过「${reviewTarget?.record?.title || '无标题'}」？通过后将进入发布流程。`
            : reviewTarget?.action === 'reject'
              ? `驳回「${reviewTarget?.record?.title || '无标题'}」？请填写驳回原因。`
              : `将「${reviewTarget?.record?.title || '无标题'}」重置为草稿？`}
        </p>
        <textarea
          value={reviewNote}
          onChange={(e) => setReviewNote(e.target.value)}
          rows={3}
          placeholder="审核备注（可选）"
          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm resize-none"
        />
        <div className="flex justify-end gap-2 mt-5">
          <Button variant="ghost" onClick={() => setReviewTarget(null)}>
            取消
          </Button>
          <Button
            variant="primary"
            loading={reviewingId === reviewTarget?.record?.id}
            onClick={handleReview}
          >
            确认
          </Button>
        </div>
      </Modal>

      {tab === 'accounts' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 已配置账号 */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-gray-400" /> 已配置账号（{accounts.length}）
              </h3>
              <Button
                variant="secondary"
                size="sm"
                icon={Upload}
                onClick={() => setBatchModal(true)}
              >
                批量导入
              </Button>
            </div>
            {accounts.length === 0 ? (
              <Empty
                icon={Settings2}
                title="暂无账号配置"
                description="添加平台账号后即可使用自动发布（未配置时自动使用引导式）"
              />
            ) : (
              <div className="space-y-2">
                {accounts.map((a) => {
                  const p = PLATFORMS.find((x) => x.value === a.platform)
                  return (
                    <div
                      key={a.id}
                      className="p-3 rounded-lg border border-gray-100 hover:border-blue-200 transition-all"
                    >
                      <div className="flex items-center gap-3">
                        {p && (
                          <div
                            className={`w-9 h-9 rounded-lg bg-gradient-to-br ${p.color} flex items-center justify-center flex-shrink-0`}
                          >
                            <p.icon className="w-4 h-4 text-white" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800">
                            {a.name || p?.label || a.platform}
                          </div>
                          <div className="text-xs text-gray-400">
                            AppID：{a.app_id || '未填写'} {a.configured ? '· 已配置' : '· 未配置'} ·
                            今日 {a.today_published ?? 0}/{a.daily_limit ?? 10}
                          </div>
                        </div>
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={TestTube2}
                          loading={testingId === a.id}
                          onClick={() => testAccount(a.id)}
                        >
                          测试连接
                        </Button>
                        <button
                          onClick={() => deleteAccount(a.id)}
                          className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          {/* 添加账号 */}
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Plus className="w-4 h-4 text-blue-500" /> 添加 / 更新账号
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">平台</label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {PLATFORMS.map((p) => (
                      <button
                        key={p.value}
                        onClick={() => setAccForm({ ...accForm, platform: p.value })}
                        className={`flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-xs border transition-all ${
                          accForm.platform === p.value
                            ? `${p.border} ${p.text} font-medium`
                            : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                        }`}
                      >
                        <p.icon className="w-3.5 h-3.5" /> {p.label.replace('微信', '')}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    账号名称（可选）
                  </label>
                  <input
                    type="text"
                    value={accForm.name}
                    onChange={(e) => setAccForm({ ...accForm, name: e.target.value })}
                    placeholder="如：我的公众号"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">AppID</label>
                  <input
                    type="text"
                    value={accForm.app_id}
                    onChange={(e) => setAccForm({ ...accForm, app_id: e.target.value })}
                    placeholder="平台应用 / 公众号 AppID"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">AppSecret</label>
                  <input
                    type="password"
                    value={accForm.app_secret}
                    onChange={(e) => setAccForm({ ...accForm, app_secret: e.target.value })}
                    placeholder="平台应用 / 公众号 AppSecret"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                  />
                </div>
                <Button variant="primary" icon={Plus} onClick={saveAccount} className="w-full">
                  保存账号
                </Button>
              </div>
            </Card>

            <Card>
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <CircleDashed className="w-4 h-4 text-amber-500" /> 凭据获取指引
              </h3>
              <div className="space-y-2 text-sm text-gray-600">
                <p>
                  <span className="font-medium text-emerald-600">微信公众号：</span>登录
                  mp.weixin.qq.com → 设置与开发 → 基本配置 → 复制 AppID 与 AppSecret（需开启 IP
                  白名单）。配置后图文可自动发布。
                </p>
                <p>
                  <span className="font-medium text-gray-700">抖音 / 快手：</span>
                  到开放平台创建「移动应用/网站应用」并完成审核，审核通过后才能获得可用凭据实现图片视频自动发布；审核前请使用「引导式」零配置发布。
                </p>
                <p className="text-xs text-gray-400">
                  凭据仅保存在本平台数据库（脱敏展示），不会明文回传前端。
                </p>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* 创建排期 Modal */}
      <Modal
        open={!!schedModal}
        onClose={() => setSchedModal(null)}
        title={`创建发布排期 · ${schedModal?.date || ''}`}
        size="lg"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">发布平台</label>
              <div className="space-y-1.5">
                {PLATFORMS.map((p) => (
                  <button
                    key={p.value}
                    onClick={() =>
                      setSchedForm({
                        ...schedForm,
                        platform: p.value,
                        content_type: p.value === 'wechat' ? 'article' : 'image',
                      })
                    }
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all ${
                      schedForm.platform === p.value
                        ? `${p.border} ${p.text} font-medium`
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <p.icon className="w-3.5 h-3.5" /> {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">内容类型</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {CONTENT_TYPES.map((c) => (
                  <button
                    key={c.value}
                    onClick={() => setSchedForm({ ...schedForm, content_type: c.value })}
                    className={`flex flex-col items-center gap-1 px-1 py-2 rounded-lg border text-[11px] transition-all ${
                      schedForm.content_type === c.value
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-medium'
                        : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    <c.icon className="w-3.5 h-3.5" /> {c.label}
                  </button>
                ))}
              </div>
              <div className="mt-3">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-500">计划发布时间</label>
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      loadBestTime(schedForm.platform)
                    }}
                    className="text-xs text-purple-500 hover:text-purple-700 flex items-center gap-1"
                  >
                    <Clock3 className="w-3 h-3" /> 最佳时间
                  </button>
                </div>
                <input
                  type="datetime-local"
                  value={schedForm.scheduled_at}
                  onChange={(e) => setSchedForm({ ...schedForm, scheduled_at: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                />
                {bestTimes && bestTimes.length > 0 && (
                  <div className="mt-2 space-y-1">
                    <p className="text-[10px] text-gray-400">推荐时段：</p>
                    {bestTimes.map((t, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          const now = new Date()
                          const target = new Date()
                          const dayDiff = (t.weekday_num - now.getDay() + 7) % 7
                          target.setDate(target.getDate() + (dayDiff === 0 ? 0 : dayDiff))
                          target.setHours(t.hour, 0, 0, 0)
                          const iso = target.toISOString().slice(0, 16)
                          setSchedForm({ ...schedForm, scheduled_at: iso })
                        }}
                        className="block w-full text-left px-2 py-1 rounded text-xs text-purple-600 hover:bg-purple-50 transition-colors"
                      >
                        <span className="font-medium">{t.label}</span>
                        {t.avg_views > 0 && (
                          <span className="text-gray-400 ml-2">
                            均阅 {t.avg_views.toLocaleString()}
                          </span>
                        )}
                        {t.sample_count > 0 && (
                          <span className="text-gray-300 ml-1">({t.sample_count}篇)</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">标题</label>
            <input
              type="text"
              value={schedForm.title}
              onChange={(e) => setSchedForm({ ...schedForm, title: e.target.value })}
              placeholder="如：周五产品周报 / 新品上架视频"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">正文 / 文案</label>
            <textarea
              value={schedForm.content}
              onChange={(e) => setSchedForm({ ...schedForm, content: e.target.value })}
              rows={3}
              placeholder="排期发布时使用的文案（可留空）"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              话题标签（回车添加）
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={schedForm.topic_input}
                onChange={(e) => setSchedForm({ ...schedForm, topic_input: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addSchedTopic()
                  }
                }}
                placeholder="如：AI工具 内容运营"
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
              />
              <Button variant="secondary" size="sm" icon={Plus} onClick={addSchedTopic}>
                添加
              </Button>
            </div>
            {schedForm.topics.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {schedForm.topics.map((t, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-xs text-indigo-700"
                  >
                    #{t}
                    <button
                      onClick={() =>
                        setSchedForm({
                          ...schedForm,
                          topics: schedForm.topics.filter((_, j) => j !== i),
                        })
                      }
                      className="text-indigo-300 hover:text-red-500"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              素材（{schedAssets.length}，点击图片/视频选择）
            </label>
            {assets.media?.length ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2 max-h-36 overflow-y-auto pr-1">
                {assets.media.map((m) => {
                  const url = m.url || m.media_url
                  const sel = schedAssets.some((s) => s.url === url)
                  return (
                    <button
                      key={m.id}
                      onClick={() => {
                        if (!url) return
                        setSchedAssets((prev) =>
                          sel
                            ? prev.filter((s) => s.url !== url)
                            : [
                                ...prev,
                                {
                                  url,
                                  name: url.split('/').pop(),
                                  type: m.type === 'video' ? 'video' : 'image',
                                },
                              ]
                        )
                      }}
                      className={`relative rounded-lg overflow-hidden border-2 transition-all ${sel ? 'border-indigo-500 ring-2 ring-indigo-500/30' : 'border-transparent hover:border-indigo-200'}`}
                    >
                      {m.type === 'image' ? (
                        <img src={assetFull(url)} alt="" className="w-full h-12 object-cover" />
                      ) : (
                        <div className="w-full h-12 flex items-center justify-center bg-gray-800">
                          <Film className="w-4 h-4 text-white/70" />
                        </div>
                      )}
                      {sel && (
                        <span className="absolute top-0.5 right-0.5 w-3.5 h-3.5 rounded-full bg-indigo-500 text-white text-[9px] flex items-center justify-center">
                          <Check className="w-2 h-2" />
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            ) : (
              <p className="text-xs text-gray-400">
                暂无素材，可先到图片/视频工厂生成（图文排期可不选素材）
              </p>
            )}
          </div>

          <Button
            variant="primary"
            size="lg"
            icon={CalendarPlus}
            onClick={createSchedule}
            className="w-full"
          >
            创建排期
          </Button>
        </div>
      </Modal>

      {/* 合规风险确认 Modal */}
      <Modal
        open={complianceModal}
        onClose={() => {
          setComplianceModal(false)
          setPendingSubmit(null)
        }}
        title="⚠️ 内容合规风险提示"
        size="md"
      >
        <div className="space-y-3">
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-800">
            <p className="font-medium">检测到高风险内容，可能违反平台规定导致限流或封号</p>
            <p className="text-xs mt-1 opacity-80">
              共 {complianceResult?.total_hits || 0} 处风险提示
            </p>
          </div>
          {complianceResult?.suggestions?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">修改建议：</p>
              <div className="space-y-1">
                {complianceResult.suggestions.slice(0, 8).map((s, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="line-through text-red-400 bg-red-50 px-1.5 py-0.5 rounded">
                      {s.original}
                    </span>
                    <span className="text-gray-300">→</span>
                    <span className="text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
                      {s.suggest}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-2 justify-end">
            <Button
              variant="secondary"
              onClick={() => {
                setComplianceModal(false)
                setPendingSubmit(null)
              }}
            >
              返回修改
            </Button>
            <Button variant="danger" onClick={confirmRiskySubmit}>
              仍要发布
            </Button>
          </div>
        </div>
      </Modal>

      {/* 批量导入账号 Modal */}
      <Modal open={batchModal} onClose={() => setBatchModal(false)} title="批量导入账号" size="md">
        <div className="space-y-3">
          <p className="text-xs text-gray-500">
            每行一个账号，格式：
            <code className="px-1.5 py-0.5 rounded bg-gray-100 text-blue-600">
              名称|AppID|AppSecret
            </code>
            （用竖线 <code className="px-1 py-0.5 rounded bg-gray-100">|</code> 分隔）
          </p>
          <textarea
            value={batchText}
            onChange={(e) => setBatchText(e.target.value)}
            rows={8}
            placeholder={'主号|wx1234567890|abc123def456\n备用号|wx0987654321|xyz789uvw012'}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
          />
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" onClick={() => setBatchModal(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              icon={Upload}
              loading={batchLoading}
              onClick={batchImportAccounts}
            >
              导入
            </Button>
          </div>
        </div>
      </Modal>

      {/* 记录详情 Modal */}
      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title="发布详情"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              icon={Download}
              onClick={downloadPackage}
              disabled={!detail}
            >
              下载素材包 ZIP
            </Button>
            <Button variant="primary" onClick={() => setDetail(null)}>
              关闭
            </Button>
          </>
        }
      >
        {detail && (
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge color="green">
                {PLATFORMS.find((p) => p.value === detail.platform)?.label || detail.platform_label}
              </Badge>
              <Badge color="blue">{detail.content_label}</Badge>
              <Badge color={MODE_BADGE[detail.mode]?.color}>{MODE_BADGE[detail.mode]?.label}</Badge>
              <Badge color={STATUS_BADGE[detail.status]?.color}>
                {STATUS_BADGE[detail.status]?.label}
              </Badge>
              <span className="text-xs text-gray-400 ml-auto">
                {detail.created_at?.slice(0, 19).replace('T', ' ')}
              </span>
            </div>
            {detail.title && <p className="font-medium text-gray-900">{detail.title}</p>}
            {detail.content && (
              <div className="px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 whitespace-pre-wrap max-h-64 overflow-y-auto text-gray-700">
                {detail.content}
              </div>
            )}
            {detail.topics?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {detail.topics.map((t, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700"
                  >
                    #{t}
                  </span>
                ))}
              </div>
            )}
            {detail.asset_urls?.length > 0 && (
              <div>
                <label className="text-xs font-medium text-gray-500">
                  素材文件（也可一键下载素材包 ZIP）
                </label>
                <div className="space-y-1 mt-1">
                  {detail.asset_urls.map((u, i) => (
                    <a
                      key={i}
                      href={assetFull(u)}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200 hover:border-blue-300 text-xs text-gray-600"
                    >
                      <Download className="w-3 h-3 text-gray-400" /> {u.split('/').pop()}
                    </a>
                  ))}
                </div>
              </div>
            )}
            {detail.platform_post_id && (
              <p className="text-xs text-emerald-600">平台帖子 ID：{detail.platform_post_id}</p>
            )}
            {detail.error && (
              <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg p-2">
                错误：{detail.error}
              </p>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
