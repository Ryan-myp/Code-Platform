import React, { useState, useEffect, useRef } from 'react'
import {
  PenTool,
  Play,
  Copy,
  Check,
  Clock,
  Sparkles,
  Upload,
  X,
  FileText,
  TrendingUp,
  Share2,
  Mail,
  Megaphone,
  Package,
  Newspaper,
  BookOpen,
  Trash2,
  Star,
  Tag,
  RefreshCw,
  Globe,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ShareButton from '../components/ShareButton'
import ExportButton from '../components/ExportButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import RandomPromptButton from '../components/RandomPromptButton'
import { Card, Button, Badge, Empty, PageHeader, SkeletonList, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

const TYPES = [
  { value: 'marketing', label: '营销文案', icon: Megaphone, color: 'pink' },
  { value: 'social', label: '社交媒体', icon: Share2, color: 'blue' },
  { value: 'seo', label: 'SEO文章', icon: TrendingUp, color: 'green' },
  { value: 'email', label: '邮件营销', icon: Mail, color: 'amber' },
  { value: 'ad', label: '广告创意', icon: Sparkles, color: 'purple' },
  { value: 'product', label: '产品描述', icon: Package, color: 'teal' },
  { value: 'press', label: '新闻稿', icon: Newspaper, color: 'red' },
  { value: 'brand', label: '品牌故事', icon: BookOpen, color: 'indigo' },
]

const TONES = [
  { value: 'professional', label: '专业' },
  { value: 'lively', label: '活泼' },
  { value: 'formal', label: '正式' },
  { value: 'humorous', label: '幽默' },
  { value: 'emotional', label: '感性' },
  { value: 'persuasive', label: '说服力' },
]

const LENGTHS = [
  { value: 'short', label: '短文案', desc: '100-200字' },
  { value: 'medium', label: '标准', desc: '300-500字' },
  { value: 'long', label: '长文', desc: '800-1500字' },
]

// v15：平台适配参数（公众号/小红书/抖音/知乎/微博/头条标题风格差异）
const PLATFORMS = [
  { value: '', label: '通用发布', icon: Globe, desc: '不限定平台' },
  { value: 'wechat', label: '公众号', icon: BookOpen, desc: '标题钩子 · 小标题分段' },
  { value: 'xiaohongshu', label: '小红书', icon: Sparkles, desc: 'emoji · 话题标签' },
  { value: 'douyin', label: '抖音', icon: Play, desc: '3秒钩子 · 短句口播' },
  { value: 'zhihu', label: '知乎', icon: TrendingUp, desc: '结论先行 · 专业论证' },
  { value: 'weibo', label: '微博', icon: Megaphone, desc: '短平快 · 话题传播' },
  { value: 'toutiao', label: '头条', icon: Newspaper, desc: '数字标题 · 扫读排版' },
]

const RANDOM_PROMPTS = [
  '为一款主打安全性能的新能源汽车撰写朋友圈推广文案，目标人群是关注家庭出行的 30-45 岁人群',
  '为一家新开业的日式拉面店撰写小红书种草笔记，突出汤底浓郁、叉烧入口即化',
  '为程序员社区撰写公众号推文开篇，主题：如何高效准备系统设计面试',
  '为儿童智能手表撰写电商详情页文案，强调定位精准、家长可远程查看',
  '为本地瑜伽馆撰写推广文案，吸引上班族报名晚间课程',
  '为环保品牌的竹制餐具撰写品牌故事文案，突出可持续理念',
  '为一家 SaaS 公司撰写获客落地页主标题和副标题，突出“3 天部署、零代码”卖点',
  '为宠物寄养服务撰写朋友圈文案，目标人群是长假出行的宠物主，强调视频日报服务',
  '为高校食堂新窗口撰写校园墙宣传文案，突出性价比与招牌菜，语气幽默接地气',
  '为知识付费课程撰写公众号推文，主题：普通人如何靠 AI 提升 3 倍工作效率',
  '为本地书店撰写世界读书日主题活动文案，含打卡赠书环节，唤起纸质书情怀',
  '为健身房撰写新年开工营销文案，主打“年后瘦身计划”，设置早鸟价机制',
]

const TEMPLATES = [
  {
    name: '新品上市',
    icon: '🚀',
    prompt:
      '为一款全新的智能降噪耳机撰写上市营销文案，核心卖点包括主动降噪、40小时续航、轻量佩戴，目标受众是通勤上班族，希望突出性价比优势',
  },
  {
    name: '节日促销',
    icon: '🎉',
    prompt:
      '为国庆黄金周促销活动撰写文案，折扣力度全场8折，活动时间10月1日-7日，主推产品家电焕新系列，营造紧迫感和购买欲',
  },
  {
    name: '小红书种草',
    icon: '📕',
    prompt:
      '写一篇小红书种草笔记，产品是便携咖啡机，使用体验是3分钟出杯、口感接近咖啡馆，适合办公室与出差场景，语气要真实自然，带emoji',
  },
  {
    name: '朋友圈文案',
    icon: '💬',
    prompt: '写一条朋友圈营销文案，产品/服务是精品咖啡月卡，要简短有力，引发互动，不超过100字',
  },
  {
    name: '邮件营销',
    icon: '📧',
    prompt: '写一封营销邮件，目的是邀请参加新品体验会，收件人是老客户，核心信息是限时免费体验名额，需要包含CTA行动号召',
  },
  {
    name: '品牌故事',
    icon: '📖',
    prompt:
      '为品牌山野茶舍撰写品牌故事，品牌创立于2016年，核心理念是回归自然的慢生活方式，要打动人心，传递品牌价值',
  },
  {
    name: 'SEO长文',
    icon: '🔍',
    prompt:
      '围绕关键词家用净水器选购指南撰写一篇SEO优化文章，目标读者是新手家庭，需要覆盖滤芯类型对比和安装注意事项，字数1000字以上',
  },
  {
    name: '产品详情',
    icon: '📦',
    prompt:
      '为产品智能扫地机器人撰写详情页文案，包含：产品亮点、规格参数、使用场景、用户评价摘要、购买理由',
  },
  {
    name: '短视频口播',
    icon: '🎬',
    prompt:
      '写一段 60 秒短视频口播脚本，产品是 AI 学习平板，面向备考学生家长，开头 3 秒要有钩子，中间讲核心功能，结尾引导评论领取体验课',
  },
  {
    name: '招聘 JD',
    icon: '👔',
    prompt:
      '撰写一份招聘 JD，岗位是 AI 产品经理，要求突出平台型产品经验与数据驱动能力，包含岗位职责、任职要求、加分项、福利亮点，语气真诚有吸引力',
  },
  {
    name: '年会致辞',
    icon: '🥂',
    prompt:
      '撰写公司年会总经理致辞稿，回顾年度关键词“增长”，感谢团队付出，公布明年目标，结尾鼓舞士气，时长 5 分钟，语言正式中带温度',
  },
  {
    name: '直播话术',
    icon: '📺',
    prompt:
      '写一套直播间带货话术，产品是护肤精华液，包含开场暖场、痛点引入、产品卖点、价格锚点、逼单话术、告别话术，节奏紧凑',
  },
  {
    name: '抖音爆款脚本',
    icon: '🎵',
    prompt:
      '写一段 30 秒抖音带货脚本，产品是便携榨汁杯，要求：3秒钩子（反常识开场）、痛点引入、产品卖点、价格锚点、逼单、引导关注，短句为主',
  },
  {
    name: '知乎高赞回答',
    icon: '🧠',
    prompt:
      '写一篇知乎高赞回答，问题：普通人如何系统入门数据分析？要求结论先行、分点论证（含案例）、专业但易懂、结尾总结升华',
  },
  {
    name: '公众号深度推文',
    icon: '📰',
    prompt:
      '写一篇公众号深度推文，主题：2026 年内容创作者的生存法则，要求：标题3个备选（利益点+悬念）、小标题分段、数据支撑、金句结尾',
  },
  {
    name: '微博热点借势',
    icon: '🔥',
    prompt:
      '结合“暑期出游高峰”热点写一条微博借势文案，品牌是精品咖啡连锁，要求：带#话题#、短句快节奏、引发共鸣与转发、附互动问题',
  },
]

export default function CopywritingPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿）
  const [inputs, setInputs] = usePersistentToolState('copywriting_inputs', {
    prompt: '',
    type: 'marketing',
    title: '',
    tone: 'professional',
    length: 'medium',
    platform: '',
  })
  const { prompt, type, title, tone, length, platform } = inputs
  const setPrompt = (v) => setInputs((p) => ({ ...p, prompt: v ?? '' }))
  const setType = (v) => setInputs((p) => ({ ...p, type: v }))
  const setTitle = (v) => setInputs((p) => ({ ...p, title: v ?? '' }))
  const setTone = (v) => setInputs((p) => ({ ...p, tone: v }))
  const setLength = (v) => setInputs((p) => ({ ...p, length: v }))
  const setPlatform = (v) => setInputs((p) => ({ ...p, platform: v }))
  const [result, setResult] = useState('')
  const [task, setTask] = useState(null)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [showTemplates, setShowTemplates] = useState(true)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [favorites, setFavorites] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('copywriting_favorites') || '[]')
    } catch {
      return []
    }
  })
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
      const res = await api.get('/api/copywriting/history')
      setHistory(res.data)
    } catch (e) {
      setHistoryError(e.message)
    } finally {
      setHistoryLoading(false)
    }
  }

  const generate = async () => {
    const finalPrompt = fileContent
      ? `${prompt}\n\n---参考材料---\n${fileContent.slice(0, 2000)}`
      : prompt
    if (!finalPrompt.trim()) {
      toast.error('请输入文案需求')
      return
    }
    setResult('')
    const fullPrompt = `${finalPrompt}\n\n要求：语气风格为${TONES.find((t) => t.value === tone)?.label}，篇幅控制在${LENGTHS.find((l) => l.value === length)?.desc}。`
    await submitTask(
      '/api/copywriting/generate',
      { type, title, platform, prompt: fullPrompt },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setResult(data.result)
          setTask(null)
          loadHistory()
          toast.success('文案生成完成')
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

  const applyTemplate = (tpl) => {
    setPrompt(tpl.prompt)
    setShowTemplates(false)
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
    setPrompt(item.prompt)
    setType(item.type)
    setTitle(item.title || '')
    setResult(item.result)
  }

  const toggleFavorite = (item, e) => {
    e.stopPropagation()
    const isFav = favorites.some((f) => f.id === item.id)
    const next = isFav
      ? favorites.filter((f) => f.id !== item.id)
      : [
          ...favorites,
          {
            id: item.id,
            prompt: item.prompt,
            type: item.type,
            title: item.title,
            created_at: item.created_at,
          },
        ]
    setFavorites(next)
    localStorage.setItem('copywriting_favorites', JSON.stringify(next))
    toast.success(isFav ? '已取消收藏' : '已收藏')
  }

  const regenerateFromHistory = (item, e) => {
    e.stopPropagation()
    setPrompt(item.prompt)
    setType(item.type)
    setTitle(item.title || '')
    toast.success('已填充，可修改后重新生成')
  }

  const deleteHistory = async (id, e) => {
    e.stopPropagation()
    try {
      await api.delete(`/api/copywriting/${id}`)
      loadHistory()
      toast.success('已删除')
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const currentType = TYPES.find((t) => t.value === type)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 文案工厂"
        description="智能文案生成，覆盖营销、社媒、SEO、邮件等全场景"
        icon={PenTool}
        iconColor="from-pink-500 to-rose-600"
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: '总文案数',
            value: history.length,
            icon: FileText,
            color: 'from-pink-500 to-rose-600',
          },
          {
            label: '本周生成',
            value: history.filter((h) => {
              const d = new Date(h.created_at)
              const now = new Date()
              return now - d < 7 * 86400000
            }).length,
            icon: PenTool,
            color: 'from-purple-500 to-indigo-600',
          },
          {
            label: '常用类型',
            value: currentType?.label || '-',
            icon: Tag,
            color: 'from-blue-500 to-cyan-600',
          },
          {
            label: '模板数量',
            value: TEMPLATES.length,
            icon: Sparkles,
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
        {/* 左侧：输入区 */}
        <div className="space-y-4">
          {/* 文案类型 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <PenTool className="w-4 h-4 text-pink-500" /> 文案类型
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {TYPES.map((t) => {
                const Icon = t.icon
                return (
                  <button
                    key={t.value}
                    onClick={() => setType(t.value)}
                    className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg text-xs border transition-all ${
                      type === t.value
                        ? 'bg-pink-50 border-pink-300 text-pink-700 font-medium shadow-sm'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {t.label}
                  </button>
                )
              })}
            </div>
          </Card>

          {/* 提示词模板 */}
          <Card>
            <button
              onClick={() => setShowTemplates(!showTemplates)}
              className="flex items-center justify-between w-full"
            >
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" /> 场景模板
              </h3>
              <span className="text-xs text-gray-400">{showTemplates ? '收起' : '展开'}</span>
            </button>
            {showTemplates && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                {TEMPLATES.map((tpl, i) => (
                  <button
                    key={i}
                    onClick={() => applyTemplate(tpl)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 hover:border-pink-300 hover:bg-pink-50/50 transition-all text-left"
                  >
                    <span className="text-lg">{tpl.icon}</span>
                    <span className="text-sm text-gray-700">{tpl.name}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>

          {/* 输入区 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-pink-500" /> 文案需求
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">标题（可选）</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="文案标题"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center justify-between">
                  <span>需求描述 *</span>
                  <div className="flex items-center gap-3">
                    <RandomPromptButton
                      prompts={RANDOM_PROMPTS}
                      onPick={(t) => setPrompt(t)}
                      className="text-pink-500 hover:text-pink-700"
                    />
                    <EnhancePromptButton
                      text={prompt}
                      onEnhance={(t) => setPrompt(t)}
                      style="copywriting"
                      className="text-pink-600 hover:text-pink-700"
                    />
                  </div>
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="描述你的文案需求，如：为一款新的智能手表写营销文案，突出健康监测功能..."
                  rows={5}
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !task) {
                      e.preventDefault()
                      generate()
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
                />
              </div>

              {/* 语气和长度 */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">语气风格</label>
                  <select
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
                  >
                    {TONES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">内容长度</label>
                  <select
                    value={length}
                    onChange={(e) => setLength(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
                  >
                    {LENGTHS.map((l) => (
                      <option key={l.value} value={l.value}>
                        {l.label} ({l.desc})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 平台适配（v15） */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center gap-1">
                  <Globe className="w-3 h-3" /> 平台适配
                  {platform && (
                    <span className="text-pink-500 font-normal">
                      · {PLATFORMS.find((p) => p.value === platform)?.desc}
                    </span>
                  )}
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {PLATFORMS.map((p) => {
                    const Icon = p.icon
                    return (
                      <button
                        key={p.value}
                        onClick={() => setPlatform(p.value)}
                        title={p.desc}
                        className={`flex flex-col items-center gap-0.5 px-1 py-1.5 rounded-lg text-[10px] border transition-all ${
                          platform === p.value
                            ? 'bg-pink-50 border-pink-300 text-pink-700 font-medium'
                            : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        {p.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 文件上传 */}
              <div>
                {uploadedFile ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-pink-50 border border-pink-200 rounded-lg">
                    <FileText className="w-4 h-4 text-pink-600" />
                    <span className="flex-1 text-sm text-gray-700 truncate">
                      {uploadedFile.name}
                    </span>
                    <button onClick={removeFile} className="text-gray-400 hover:text-red-500">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label className="flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-pink-400 hover:bg-pink-50/50 transition-colors">
                    <Upload className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-500">上传参考材料（可选）</span>
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
                生成文案
              </Button>
              {task && (
                <div className="w-full">
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>{task.stage || '处理中…'}</span>
                    <span>{task.progress || 0}%</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-pink-500 to-rose-500 rounded-full transition-all duration-300"
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
                <Sparkles className="w-4 h-4 text-pink-500" /> 生成结果
              </h3>
              {result && (
                <div className="flex items-center gap-2">
                  <ExportButton content={result} title="文案生成结果" />
                  <ShareButton content={result} title="文案生成结果" contentType="copywriting" />
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
            {result ? (
              <MarkdownRenderer content={result} />
            ) : (
              <Empty icon={PenTool} title="等待生成" description="输入需求后点击生成" />
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
              {history.slice(0, 10).map((item) => {
                const tc = TYPES.find((t) => t.value === item.type) || TYPES[0]
                const isFav = favorites.some((f) => f.id === item.id)
                return (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                    onClick={() => reuseHistory(item)}
                  >
                    <Badge color={tc.color}>{tc.label}</Badge>
                    <span className="text-sm text-gray-700 truncate flex-1">
                      {item.prompt?.slice(0, 80)}
                    </span>
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {item.created_at?.slice(0, 16).replace('T', ' ')}
                    </span>
                    <button
                      onClick={(e) => toggleFavorite(item, e)}
                      className={`p-1 rounded transition-colors flex-shrink-0 ${isFav ? 'text-amber-500' : 'text-gray-300 hover:text-amber-400'}`}
                      title={isFav ? '取消收藏' : '收藏'}
                    >
                      <Star className="w-3.5 h-3.5" fill={isFav ? 'currentColor' : 'none'} />
                    </button>
                    <button
                      onClick={(e) => regenerateFromHistory(item, e)}
                      className="p-1 text-gray-400 hover:text-blue-500 rounded transition-colors flex-shrink-0"
                      title="以此重新生成"
                    >
                      <Play className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={(e) => deleteHistory(item.id, e)}
                      className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors flex-shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )
              })}
            </div>
          </Card>
        )
      )}
    </div>
  )
}
