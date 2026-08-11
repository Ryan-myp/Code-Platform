import React, { useState, useEffect, useRef } from 'react'
import {
  Presentation,
  Play,
  Clock,
  FileText,
  Copy,
  Check,
  Upload,
  X,
  Download,
  Users,
  Layers,
  Palette,
  Sparkles,
  Trash2,
  Briefcase,
  GraduationCap,
  Rocket,
  BarChart3,
  Lightbulb,
  BookOpen,
  Megaphone,
  ClipboardList,
  RefreshCw,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import SlidePreviewer, { extractSlidesFromResult } from '../components/SlidePreviewer'
import ShareButton from '../components/ShareButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import RandomPromptButton from '../components/RandomPromptButton'
import { Card, Button, Empty, PageHeader, SkeletonList, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

const PPT_TYPES = [
  { value: 'business', label: '商业计划', icon: Briefcase, color: 'blue' },
  { value: 'report', label: '工作汇报', icon: BarChart3, color: 'green' },
  { value: 'product', label: '产品发布', icon: Rocket, color: 'purple' },
  { value: 'training', label: '培训课件', icon: GraduationCap, color: 'amber' },
  { value: 'proposal', label: '项目提案', icon: Lightbulb, color: 'orange' },
  { value: 'academic', label: '学术论文', icon: BookOpen, color: 'indigo' },
  { value: 'marketing', label: '营销策划', icon: Megaphone, color: 'pink' },
  { value: 'review', label: '个人述职', icon: ClipboardList, color: 'teal' },
]

const TEMPLATE_STYLES = [
  {
    value: 'business',
    label: '商务汇报',
    desc: '工作汇报/项目提案',
    color: 'bg-indigo-500',
  },
  {
    value: 'roadshow',
    label: '融资路演',
    desc: '投资人/产品发布',
    color: 'bg-rose-600',
  },
  {
    value: 'teaching',
    label: '教学课件',
    desc: '培训/课堂课件',
    color: 'bg-emerald-600',
  },
  {
    value: 'marketing',
    label: '营销方案',
    desc: '策划/活动方案',
    color: 'bg-pink-600',
  },
  {
    value: 'tech',
    label: '科技产品',
    desc: '技术方案/产品发布',
    color: 'bg-blue-500',
  },
  {
    value: 'consulting',
    label: '咨询分析',
    desc: '行业研究/战略咨询',
    color: 'bg-orange-600',
  },
  {
    value: 'finance',
    label: '金融投研',
    desc: '投资分析/行业研究',
    color: 'bg-teal-600',
  },
]

const AUDIENCES = [
  { value: 'executive', label: '高管/决策层' },
  { value: 'client', label: '客户/合作伙伴' },
  { value: 'team', label: '内部团队' },
  { value: 'public', label: '公众/媒体' },
]

const SCALES = [
  { value: 'short', label: '精简版', desc: '5-10页' },
  { value: 'standard', label: '标准版', desc: '15-20页' },
  { value: 'detailed', label: '详细版', desc: '25-30页' },
]

const THEMES = [
  { value: 'business_blue', label: '商务蓝', color: 'bg-blue-500' },
  { value: 'tech_purple', label: '科技紫', color: 'bg-purple-500' },
  { value: 'energy_orange', label: '活力橙', color: 'bg-orange-500' },
  { value: 'minimal_gray', label: '简约灰', color: 'bg-gray-500' },
  { value: 'china_red', label: '中国红', color: 'bg-red-600' },
  { value: 'mint_fresh', label: '清新薄荷', color: 'bg-emerald-400' },
  { value: 'vintage_gold', label: '复古金棕', color: 'bg-amber-700' },
  { value: 'dream_pink', label: '梦幻紫粉', color: 'bg-fuchsia-400' },
]

const RANDOM_TITLES = [
  '2026 年产品战略规划',
  '新员工入职培训',
  'Q3 销售业绩复盘',
  '人工智能技术趋势分享',
  '项目启动会汇报',
  '年度品牌营销方案',
  '数字化转型路线图',
  '校园招聘宣讲方案',
  '乡村振兴产业规划',
  '电商大促营销策略',
  'AIGC 行业白皮书',
  '安全生产月活动总结',
]

const TEMPLATES = [
  {
    name: '季度工作汇报',
    icon: '📊',
    title: '2026年Q3工作季度汇报',
    outline: '1. 工作概述\n2. 核心成果\n3. 数据分析\n4. 问题与挑战\n5. 下季度计划',
  },
  {
    name: '产品发布演示',
    icon: '🚀',
    title: '智能新品发布会',
    outline: '1. 产品背景\n2. 核心功能\n3. 技术亮点\n4. 使用场景\n5. 价格方案\n6. Q&A',
  },
  {
    name: '商业计划书',
    icon: '💼',
    title: 'AI 内容平台商业计划书',
    outline: '1. 市场分析\n2. 产品定位\n3. 商业模式\n4. 团队介绍\n5. 财务预测\n6. 融资需求',
  },
  {
    name: '技术培训',
    icon: '🎓',
    title: '大模型应用开发技术培训',
    outline: '1. 技术概述\n2. 核心概念\n3. 实践案例\n4. 动手实验\n5. 最佳实践',
  },
  {
    name: '项目提案',
    icon: '💡',
    title: '智能客服系统立项提案',
    outline: '1. 项目背景\n2. 目标与范围\n3. 技术方案\n4. 资源需求\n5. 时间规划\n6. 风险评估',
  },
  {
    name: '年度总结',
    icon: '📅',
    title: '2026年度工作总结',
    outline: '1. 年度回顾\n2. 重点成果\n3. 经验教训\n4. 团队建设\n5. 明年展望',
  },
  {
    name: '学术答辩',
    icon: '🎓',
    title: '硕士学位论文答辩',
    outline: '1. 研究背景与意义\n2. 文献综述\n3. 研究方法\n4. 实验设计与结果\n5. 结论与展望\n6. 创新点总结',
  },
  {
    name: '电商大促',
    icon: '🛒',
    title: '双十一电商大促营销方案',
    outline: '1. 市场分析\n2. 活动目标\n3. 玩法设计\n4. 渠道投放\n5. 预算分配\n6. 效果预估',
  },
  {
    name: '政府汇报',
    icon: '🏛️',
    title: '年度政务工作汇报',
    outline: '1. 指导思想\n2. 重点工作推进\n3. 民生实事成效\n4. 存在问题\n5. 下步计划',
  },
  {
    name: '文旅策划',
    icon: '🏞️',
    title: '城市文旅品牌策划方案',
    outline: '1. 资源禀赋分析\n2. 客群画像\n3. IP 打造\n4. 活动策划\n5. 传播推广\n6. 落地保障',
  },
]

export default function PPTFactoryPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  const [result, setResult] = useState('')
  const [slides, setSlides] = useState([])
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿）
  const [inputs, setInputs] = usePersistentToolState('ppt_factory_inputs', {
    title: '',
    outline: '',
    pptType: 'business',
    audience: 'executive',
    scale: 'standard',
    theme: 'business_blue',
    template: 'business',
  })
  const { title, outline, pptType, audience, scale, theme, template } = inputs
  const setTitle = (v) => setInputs((p) => ({ ...p, title: v ?? '' }))
  const setOutline = (v) => setInputs((p) => ({ ...p, outline: v ?? '' }))
  const setPptType = (v) => setInputs((p) => ({ ...p, pptType: v }))
  const setAudience = (v) => setInputs((p) => ({ ...p, audience: v }))
  const setScale = (v) => setInputs((p) => ({ ...p, scale: v }))
  const setTheme = (v) => setInputs((p) => ({ ...p, theme: v }))
  const setTemplate = (v) => setInputs((p) => ({ ...p, template: v }))
    const [pptxUrl, setPptxUrl] = useState('')
    const [downloading, setDownloading] = useState(false)
  const [task, setTask] = useState(null)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    loadHistory()
  }, [])
  const loadHistory = async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const res = await api.get('/api/ppt/history')
      setHistory(res.data)
    } catch (e) {
      setHistoryError(e.message)
    } finally {
      setHistoryLoading(false)
    }
  }

  const generate = async () => {
    if (!title.trim()) {
      toast.error('请输入 PPT 主题')
      return
    }
    // 占位符校验：模板残留的 [xxx] 占位符不允许直接生成（避免污染历史记录）
    if (/\[[^\]]+\]/.test(title)) {
      toast.error('主题中还有未填写的占位符（如 [产品名]），请先替换为实际内容')
      return
    }
    setResult('')
    setSlides([])
    setPptxUrl('')
    const typeLabel = PPT_TYPES.find((t) => t.value === pptType)?.label
    const audienceLabel = AUDIENCES.find((a) => a.value === audience)?.label
    const scaleDesc = SCALES.find((s) => s.value === scale)?.desc
    const themeLabel = THEMES.find((t) => t.value === theme)?.label
    const fullOutline = fileContent
      ? `${outline}\n\n参考材料:\n${fileContent.slice(0, 1500)}`
      : outline
    await submitTask(
      '/api/ppt/generate',
      {
        title: `${title}（类型:${typeLabel}, 受众:${audienceLabel}, 规模:${scaleDesc}, 风格:${themeLabel}）`,
        outline: fullOutline,
        template,
      },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setResult(data.result)
          setPptxUrl(data.pptx || '')
          setSlides(extractSlidesFromResult(data.result))
          setTask(null)
          loadHistory()
          toast.success('PPT 生成完成')
        },
        onError: (e) => {
          setTask(null)
          toast.error(`生成失败：${e.message}`)
        },
      }
    )
  }

  const copyResult = () => {
    navigator.clipboard.writeText(result)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // 下载 PPTX：走 axios 携带 Authorization 头（<a download> 原生导航不带 token，会 401）
  const downloadPptx = async () => {
    if (!pptxUrl) return
    setDownloading(true)
    try {
      const res = await api.get(pptxUrl, { responseType: 'blob' })
      const blobUrl = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = pptxUrl.split('/').pop() || 'presentation.pptx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(blobUrl), 3000)
      toast.success('PPTX 已开始下载')
    } catch (err) {
      toast.error(err.response?.data?.detail || '下载失败，请稍后重试')
    } finally {
      setDownloading(false)
    }
  }

  const downloadOutline = () => {
    const name = (title || 'PPT').replace(/[\\/:*?"<>|]/g, '_')
    const blob = new Blob([result], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name}-大纲.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('已下载大纲文件')
  }

  const applyTemplate = (tpl) => {
    setTitle(tpl.title)
    setOutline(tpl.outline)
    toast.success(`已应用模板：${tpl.name}`)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) {
      toast.error('文件不能超过 10MB')
      return
    }
    setUploadedFile(file)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await api.post('/api/tools/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setFileContent(res.data.content || '')
      toast.success(`已上传: ${file.name}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || '上传失败')
      setUploadedFile(null)
    }
  }

  const removeFile = () => {
    setUploadedFile(null)
    setFileContent('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const reuseHistory = (item) => {
    setTitle(item.title)
    setOutline(item.outline || '')
    setResult(item.result)
    setPptxUrl(item.file_path || '')
    // v18-A 兜底：旧历史 slides 列可能为空（'[]'），从 result 提取 JSON 解析
    let parsedSlides = []
    try {
      const parsed = typeof item.slides === 'string' ? JSON.parse(item.slides) : item.slides
      if (Array.isArray(parsed)) parsedSlides = parsed
    } catch {
      /* 空 slides 字段 */
    }
    if (parsedSlides.length === 0) parsedSlides = extractSlidesFromResult(item.result)
    setSlides(parsedSlides)
  }

  const themeColorMap = {
    business_blue: 'border-blue-200 bg-blue-50',
    tech_purple: 'border-purple-200 bg-purple-50',
    energy_orange: 'border-orange-200 bg-orange-50',
    minimal_gray: 'border-gray-200 bg-gray-50',
    china_red: 'border-red-200 bg-red-50',
    mint_fresh: 'border-emerald-200 bg-emerald-50',
    vintage_gold: 'border-amber-200 bg-amber-50',
    dream_pink: 'border-fuchsia-200 bg-fuchsia-50',
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI PPT 生成"
        description="智能生成PPT大纲与内容，支持多种演示场景和设计主题"
        icon={Presentation}
        iconColor="from-orange-500 to-red-600"
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: '总生成数',
            value: history.length,
            icon: Presentation,
            color: 'from-orange-500 to-red-600',
          },
          {
            label: '本周生成',
            value: history.filter((h) => new Date() - new Date(h.created_at) < 7 * 86400000).length,
            icon: Sparkles,
            color: 'from-purple-500 to-indigo-600',
          },
          {
            label: '场景模板',
            value: TEMPLATES.length,
            icon: Layers,
            color: 'from-blue-500 to-cyan-600',
          },
          {
            label: '设计主题',
            value: THEMES.length,
            icon: Palette,
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：配置区 */}
        <div className="space-y-4">
          {/* 场景模板 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" /> 快速模板
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {TEMPLATES.map((tpl, i) => (
                <button
                  key={i}
                  onClick={() => applyTemplate(tpl)}
                  className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50/50 transition-all text-left"
                >
                  <span className="text-base">{tpl.icon}</span>
                  <span className="text-xs text-gray-700">{tpl.name}</span>
                </button>
              ))}
            </div>
          </Card>

          {/* PPT 配置 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Presentation className="w-4 h-4 text-orange-500" /> PPT 配置
            </h3>
            <div className="space-y-3">
              {/* 类型 */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">演示类型</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {PPT_TYPES.map((t) => {
                    const Icon = t.icon
                    return (
                      <button
                        key={t.value}
                        onClick={() => setPptType(t.value)}
                        className={`flex flex-col items-center gap-1 px-2 py-2 rounded-lg text-xs border transition-all ${
                          pptType === t.value
                            ? 'bg-orange-50 border-orange-300 text-orange-700 font-medium'
                            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        {t.label}
                      </button>
                    )
                  })}
                </div>
              </div>
              {/* 受众 + 规模 */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">目标受众</label>
                  <select
                    value={audience}
                    onChange={(e) => setAudience(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
                  >
                    {AUDIENCES.map((a) => (
                      <option key={a.value} value={a.value}>
                        {a.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">页数规模</label>
                  <select
                    value={scale}
                    onChange={(e) => setScale(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
                  >
                    {SCALES.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label} ({s.desc})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {/* 模板风格（PPTX 主题色板 + 结构原则） */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">
                  模板风格（PPTX 主题色板 + 结构原则）
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {TEMPLATE_STYLES.map((t) => (
                    <button
                      key={t.value}
                      onClick={() => setTemplate(t.value)}
                      className={`flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs border transition-all text-left ${
                        template === t.value
                          ? 'border-orange-400 bg-orange-50'
                          : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      <span className={`w-2.5 h-2.5 rounded-full ${t.color} flex-shrink-0`} />
                      <span>
                        <span className="block font-medium text-gray-800">{t.label}</span>
                        <span className="block text-[10px] text-gray-400">{t.desc}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
              {/* 设计主题 */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">设计主题</label>
                <div className="grid grid-cols-2 gap-2">
                  {THEMES.map((t) => (
                    <button
                      key={t.value}
                      onClick={() => setTheme(t.value)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-all ${
                        theme === t.value
                          ? `${themeColorMap[t.value]} border-current font-medium`
                          : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      <span className={`w-3 h-3 rounded-full ${t.color}`} />
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          {/* 输入区 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-orange-500" /> 内容输入
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center justify-between">
                  <span>主题 *</span>
                  <RandomPromptButton
                    prompts={RANDOM_TITLES}
                    onPick={(t) => setTitle(t)}
                    className="text-orange-500 hover:text-orange-700"
                  />
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="例如：2026年产品战略规划"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center justify-between">
                  <span>大纲要点（可选）</span>
                  <EnhancePromptButton
                    text={outline}
                    onEnhance={(t) => setOutline(t)}
                    style="ppt"
                    className="text-orange-600 hover:text-orange-700"
                  />
                </label>
                <textarea
                  value={outline}
                  onChange={(e) => setOutline(e.target.value)}
                  placeholder="输入大纲要点，每行一个..."
                  rows={4}
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !task) {
                      e.preventDefault()
                      generate()
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
                />
              </div>
              {/* 文件上传 */}
              <div>
                {uploadedFile ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-orange-50 border border-orange-200 rounded-lg">
                    <FileText className="w-4 h-4 text-orange-600" />
                    <span className="flex-1 text-sm text-gray-700 truncate">
                      {uploadedFile.name}
                    </span>
                    <button onClick={removeFile} className="text-gray-400 hover:text-red-500">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label className="flex items-center justify-center gap-2 px-3 py-2 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-orange-400 hover:bg-orange-50/50 transition-colors">
                    <Upload className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-500">上传参考文档（可选）</span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      onChange={handleFileUpload}
                      accept=".txt,.md,.docx,.pdf"
                      className="hidden"
                    />
                  </label>
                )}
              </div>
              <Button
                variant="primary"
                icon={Play}
                loading={!!task}
                onClick={generate}
                className="w-full"
              >
                生成 PPT
              </Button>
              {task && (
                <div className="w-full">
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>{task.stage || '处理中…'}</span>
                    <span>{task.progress || 0}%</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-orange-500 to-amber-500 rounded-full transition-all duration-300"
                      style={{ width: `${task.progress || 0}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* 右侧：结果区 */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="min-h-[400px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Presentation className="w-4 h-4 text-orange-500" /> 生成结果
              </h3>
              {result && (
                <div className="flex items-center gap-2 flex-wrap">
                  {pptxUrl && (
                    <Button
                      size="sm"
                      icon={Download}
                      loading={downloading}
                      onClick={downloadPptx}
                      className="bg-orange-500 text-white hover:bg-orange-600 border-0"
                    >
                      下载 PPTX
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" icon={Download} onClick={downloadOutline}>
                    大纲
                  </Button>
                  <ShareButton content={result} title="PPT 大纲生成结果" contentType="ppt" />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={copied ? Check : Copy}
                    onClick={copyResult}
                  >
                    {copied ? '已复制' : '复制'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={RefreshCw}
                    loading={!!task}
                    onClick={generate}
                  >
                    重新生成
                  </Button>
                </div>
              )}
            </div>
            {slides.length > 0 ? (
              <SlidePreviewer slides={slides} template={template} title={title} />
            ) : result ? (
              <MarkdownRenderer content={result} />
            ) : (
              <Empty icon={Presentation} title="等待生成" description="输入主题后点击生成" />
            )}
          </Card>
        </div>
      </div>

      {/* 历史记录 */}
      {historyLoading ? (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" /> 历史记录
          </h3>
          <SkeletonList count={3} />
        </Card>
      ) : historyError ? (
        <Card>
          <ErrorState message={`历史加载失败：${historyError}`} onRetry={loadHistory} />
        </Card>
      ) : (
        history.length > 0 && (
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" /> 历史记录
            </h3>
            <div className="space-y-2">
              {history.slice(0, 10).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                  onClick={() => reuseHistory(item)}
                >
                  <Presentation className="w-4 h-4 text-orange-400 flex-shrink-0" />
                  <span className="text-sm text-gray-700 truncate flex-1">{item.title}</span>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {item.created_at?.slice(0, 16).replace('T', ' ')}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )
      )}
    </div>
  )
}
