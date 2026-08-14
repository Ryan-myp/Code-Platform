import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useRecentTools, { formatRecentTime } from '../hooks/useRecentTools'
import {
  Bot,
  Layers,
  FolderKanban,
  CheckCircle2,
  Clock,
  Bell,
  Zap,
  Plus,
  ArrowRight,
  AlertCircle,
  FileText,
  Image,
  Film,
  Music,
  Play,
  ChevronRight,
  Sparkles,
  GitBranch,
  ListTodo,
  Wrench,
  Rocket,
  ExternalLink,
  RefreshCcw,
  CircleDot,
  Code2,
  Wand2,
  PenTool,
  Languages,
  Presentation,
  Table2,
  TrendingUp,
  BarChart3,
  Database,
  Brain,
  Puzzle,
  MessageSquare,
  Settings,
  Crown,
  HelpCircle,
  History as HistoryIcon,
  Search,
  Shield,
  Users,
  Server,
  X,
  FlaskConical,
  Send,
  Smartphone,
  Gamepad2,
  Mic2,
  Sticker,
  Star,
  FileEdit,
  Trash2,
  GalleryVerticalEnd,
  Store,
  Video,
  UserCircle,
  Share2,
  Globe,
  Terminal,
  Key,
  Activity,
  Target,
  Volume2,
  Monitor,
  Landmark,
  FileSearch,
  Files,
  BookOpen,
  ChevronUp,
  ChevronDown,
  Save,
  RefreshCw,
} from 'lucide-react'
import { Card, Button, Badge, Modal } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const MEDIA_BASE = api.defaults.baseURL
// 相对 URL → 绝对 URL（首页直显图片/视频封面用）
const absUrl = (u) => (u ? (u.startsWith('http') ? u : `${MEDIA_BASE}${u}`) : '')

// 全场景能力地图：平台所有能力按场景分组，搜索直达（与侧边栏统一分类）
const SCENE_GROUPS = [
  {
    key: 'rd',
    label: '智能研发',
    desc: 'AI 全流程开发与交付',
    icon: Code2,
    color: 'from-brand-500 to-indigo-600',
    items: [
      {
        label: '一句话全自动',
        desc: '说出功能 → 自动研发部署',
        path: '/workspace',
        icon: Sparkles,
        hot: true,
        keywords: '自动,生成,开发,部署',
      },
      {
        label: 'AI 工作台',
        desc: 'PRD→审查→方案→代码',
        path: '/workspace',
        icon: Bot,
        keywords: '工作台,研发,代码',
      },
      { label: '需求看板', desc: '需求与任务管理', path: '/board', icon: ListTodo },
      { label: '项目空间', desc: '项目全生命周期', path: '/projects', icon: FolderKanban },
      { label: '成果仓库', desc: '所有成果集中存储', path: '/artifacts', icon: FileText },
      { label: '沙箱运行', desc: '安全运行 AI 生成应用', path: '/sandbox', icon: Play },
      { label: 'CI/CD 流水线', desc: '构建·部署·自动修复', path: '/pipelines', icon: GitBranch },
      { label: 'Agent 智能体', desc: '专业角色智能体', path: '/agents', icon: Bot },
      { label: '工作流编排', desc: '可视化流程自动化', path: '/workflows', icon: Layers },
      { label: '知识库', desc: '团队知识沉淀', path: '/knowledge-bases', icon: Database },
      { label: 'Skills', desc: 'Agent 技能扩展', path: '/skills', icon: BookOpen },
      { label: 'MCP Servers', desc: '外部能力接入', path: '/mcp-servers', icon: Server },
      { label: '智能协作', desc: '任务驱动团队对话', path: '/chat', icon: MessageSquare },
      { label: '自进化中心', desc: '平台持续自我进化', path: '/evolution', icon: Brain },
    ],
  },
  {
    key: 'create',
    label: '内容创作',
    desc: 'AI 生成图·视频·文案',
    icon: Wand2,
    color: 'from-accent-500 to-blue-600',
    items: [
      {
        label: '图片工厂',
        desc: '文生图·图生图',
        path: '/image-factory',
        icon: Image,
        keywords: '图片,绘画,设计',
      },
      {
        label: '视频工厂',
        desc: 'AI 视频生成',
        path: '/video-factory',
        icon: Film,
        keywords: '视频,动画',
      },
      {
        label: '音乐工厂',
        desc: 'AI 音乐创作',
        path: '/music-factory',
        icon: Music,
        keywords: '音乐,音频,作曲',
      },
      {
        label: '文案工厂',
        desc: '营销文案·自媒体',
        path: '/copywriting',
        icon: PenTool,
        keywords: '文案,写作,营销',
      },
      {
        label: '翻译中心',
        desc: '多语种翻译',
        path: '/translation',
        icon: Languages,
        keywords: '翻译,多语言',
      },
      {
        label: 'PPT 工厂',
        desc: 'AI 一键生成 PPT',
        path: '/ppt-factory',
        icon: Presentation,
        keywords: 'PPT,演示,幻灯片',
      },
      {
        label: '表情包工坊',
        desc: '文字一键生成表情包',
        path: '/meme',
        icon: Sticker,
        keywords: '表情包,图片,搞笑',
      },
    ],
  },
  {
    key: 'ai-tools',
    label: 'AI 工坊',
    desc: 'AI智能分析与交互',
    icon: Brain,
    color: 'from-teal-500 to-cyan-600',
    items: [
      {
        label: 'AI数字人',
        desc: '虚拟形象·口播视频',
        path: '/digital-human',
        icon: UserCircle,
        keywords: '数字人,虚拟,直播,口播',
      },
      {
        label: '语音对话',
        desc: '实时语音AI助手',
        path: '/voice-chat',
        icon: Mic2,
        keywords: '语音,对话,聊天,说话',
      },
      {
        label: '视频理解',
        desc: 'AI分析视频内容',
        path: '/video-analyzer',
        icon: Monitor,
        keywords: '视频,分析,理解,字幕',
      },
      {
        label: '思维导图',
        desc: 'AI生成结构化导图',
        path: '/mindmap',
        icon: Share2,
        keywords: '思维导图,脑图,结构',
      },
      {
        label: '数据预测',
        desc: 'CSV趋势分析预测',
        path: '/forecast',
        icon: TrendingUp,
        keywords: '数据,预测,分析,趋势',
      },
      {
        label: '文档问答',
        desc: '上传文档AI问答',
        path: '/doc-qa',
        icon: Search,
        keywords: '文档,问答,PDF,合同',
      },
      {
        label: '联网搜索',
        desc: 'AI联网搜索+摘要',
        path: '/web-search',
        icon: Globe,
        keywords: '搜索,联网,网页,信息',
      },
      {
        label: '代码解释器',
        desc: '在线Python运行分析',
        path: '/code-interpreter',
        icon: Terminal,
        keywords: '代码,Python,编程,解释器',
      },
    ],
  },
  {
    key: 'apps',
    label: '应用与社区',
    desc: 'AI生成应用·发布·变现',
    icon: Gamepad2,
    color: 'from-rose-500 to-pink-600',
    items: [
      {
        label: '小游戏工坊',
        desc: 'AI 生成网页 + 微信小游戏',
        path: '/games',
        icon: Gamepad2,
        keywords: '游戏,微信,娱乐',
      },
      {
        label: '小程序工坊',
        desc: 'AI 生成微信小程序',
        path: '/miniapp',
        icon: Smartphone,
        keywords: '微信,程序,应用',
      },
      {
        label: '配音工坊',
        desc: '文字转语音，短视频配音',
        path: '/voice-dubbing',
        icon: Volume2,
        keywords: '配音,语音,tts,音频',
      },
      {
        label: '发布中心',
        desc: '一键发布公众号·抖音·快手',
        path: '/publish',
        icon: Send,
        hot: true,
        keywords: '发布,公众号,抖音,快手',
      },
      {
        label: '增长工坊',
        desc: '用户增长与数据分析',
        path: '/growth',
        icon: Target,
        keywords: '增长,运营,数据',
      },
      {
        label: '作品广场',
        desc: '全平台作品聚合·点赞评论',
        path: '/gallery',
        icon: GalleryVerticalEnd,
        hot: true,
        keywords: '作品,点赞,评论,社区,广场',
      },
      {
        label: '模板市场',
        desc: '四大工坊模板聚合',
        path: '/templates',
        icon: Store,
        keywords: '模板,工坊,游戏,小程序',
      },
    ],
  },
  {
    key: 'eff',
    label: '效率与运营',
    desc: '日常办公 · 数据驱动',
    icon: BarChart3,
    color: 'from-emerald-500 to-teal-600',
    items: [
      {
        label: '效率工具箱',
        desc: '50+ 实用 AI 小工具',
        path: '/tool-hub',
        icon: Wrench,
        keywords: '工具,效率,实用',
      },
      {
        label: 'Excel 助手',
        desc: '上传分析·公式生成',
        path: '/excel',
        icon: Table2,
        keywords: 'Excel,表格,公式',
      },
      {
        label: '股票分析',
        desc: 'AI 行情研判',
        path: '/stock',
        icon: Landmark,
        keywords: '股票,金融,行情,分析',
      },
      {
        label: 'PDF工具集',
        desc: '合并拆分·合同审查',
        path: '/pdf-tools',
        icon: FileSearch,
        keywords: 'PDF,合同,合并,文档',
      },
      {
        label: '批量处理',
        desc: '批量翻译·摘要·分析',
        path: '/batch-process',
        icon: Files,
        keywords: '批量,翻译,文档,处理',
      },
      {
        label: '数据看板',
        desc: '经营数据可视化',
        path: '/dashboard',
        icon: BarChart3,
        keywords: '看板,数据,图表',
      },
      {
        label: 'AB 测试',
        desc: '实验设计与分析',
        path: '/ab-testing',
        icon: FlaskConical,
        keywords: 'AB测试,实验',
      },
      {
        label: '用量分析',
        desc: '个人AI使用统计',
        path: '/usage-analytics',
        icon: Activity,
        keywords: '用量,统计,分析,Token',
      },
    ],
  },
  {
    key: 'me',
    label: '个人中心',
    desc: '我的资产与权益',
    icon: Crown,
    color: 'from-amber-500 to-orange-600',
    items: [
      {
        label: '任务中心',
        desc: 'AI 生成任务实时进度',
        path: '/tasks',
        icon: CheckCircle2,
        keywords: '任务,进度,生成',
      },
      {
        label: '记录中心',
        desc: '全部使用记录',
        path: '/records',
        icon: HistoryIcon,
        keywords: '记录,历史',
      },
      {
        label: '通知中心',
        desc: '消息与提醒',
        path: '/notifications',
        icon: Bell,
        keywords: '通知,消息',
      },
      {
        label: '会员中心',
        desc: '额度与权益',
        path: '/membership',
        icon: Crown,
        keywords: '会员,权益,额度',
      },
      {
        label: '个人资料',
        desc: '账号与设置',
        path: '/profile',
        icon: Settings,
        keywords: '资料,账号,设置',
      },
      {
        label: '使用帮助',
        desc: '教程与常见问题',
        path: '/help',
        icon: HelpCircle,
        keywords: '帮助,教程,FAQ',
      },
    ],
  },
  {
    key: 'sys',
    label: '平台管理',
    desc: '系统配置与运维',
    icon: Settings,
    color: 'from-slate-500 to-gray-700',
    items: [
      {
        label: '模型配置',
        desc: '多供应商模型路由',
        path: '/config',
        icon: Settings,
        keywords: '模型,配置,API',
      },
      {
        label: 'API开放平台',
        desc: '创建Key接入能力',
        path: '/api-platform',
        icon: Key,
        keywords: 'API,Key,接口,开放',
      },
      {
        label: '定时任务',
        desc: '自动化报告与同步',
        path: '/scheduler',
        icon: Clock,
        keywords: '定时,任务,自动化,报告',
      },
      {
        label: '插件市场',
        desc: '扩展平台能力',
        path: '/plugins',
        icon: Puzzle,
        keywords: '插件,扩展,市场',
      },
      {
        label: '管理后台',
        desc: '用户·权限·数据',
        path: '/admin',
        icon: Shield,
        keywords: '管理,后台,用户',
      },
      {
        label: 'Team 管理',
        desc: '团队与成员',
        path: '/teams',
        icon: Users,
        keywords: '团队,成员,协作',
      },
    ],
  },
]

// 全部能力扁平化，供搜索匹配
const ALL_CAPABILITIES = SCENE_GROUPS.flatMap((g) =>
  g.items.map((it) => ({ ...it, group: g.label, groupKey: g.key }))
)

// 特色创作工厂：平台主打卖点（首页置顶专区，标签为真实能力；hot=true 为重点主推，加“主打”徽标）
const FEATURE_FACTORIES = [
  {
    label: '图片工厂',
    desc: '文生图 · 图生图 · 虚拟试衣',
    tags: ['10 种艺术风格', '负面词净化', '模板合成'],
    path: '/image-factory',
    icon: Image,
    gradient: 'from-violet-500 to-fuchsia-600',
    hot: true,
  },
  {
    label: '视频工厂',
    desc: '文生视频 · 图生视频',
    tags: ['导演四要素', '自动封面', '1080P'],
    path: '/video-factory',
    icon: Film,
    gradient: 'from-sky-500 to-blue-600',
    hot: true,
  },
  {
    label: '游戏工坊',
    desc: '一句话生成小游戏',
    tags: ['15 模板', '6 品类', '双版本'],
    path: '/games',
    icon: Gamepad2,
    gradient: 'from-orange-500 to-red-500',
  },
  {
    label: '语音工厂',
    desc: '文字转配音',
    tags: ['6 场景文案', '多音色'],
    path: '/voice-dubbing',
    icon: Mic2,
    gradient: 'from-rose-500 to-pink-600',
  },
  {
    label: '音乐工厂',
    desc: 'AI 作词作曲',
    tags: ['情绪联动', '6 大主题'],
    path: '/music-factory',
    icon: Music,
    gradient: 'from-indigo-500 to-violet-600',
  },
  {
    label: 'PPT 工厂',
    desc: '一键生成 PPT',
    tags: ['10 模板', '8 主题'],
    path: '/ppt-factory',
    icon: Presentation,
    gradient: 'from-amber-500 to-orange-600',
  },
  {
    label: 'Excel 助手',
    desc: '分析 · 公式 · 清洗',
    tags: ['6 大操作', '12 模板'],
    path: '/excel',
    icon: Table2,
    gradient: 'from-emerald-500 to-green-600',
  },
  {
    label: '表情包工坊',
    desc: '文字生成表情包',
    tags: ['AI 8 风格', '商用尺寸'],
    path: '/meme',
    icon: Sticker,
    gradient: 'from-yellow-400 to-amber-500',
  },
  {
    label: '思维导图',
    desc: 'AI 结构化脑图',
    tags: ['5 套配色', '深度可选'],
    path: '/mindmap',
    icon: Share2,
    gradient: 'from-purple-500 to-indigo-600',
  },
  {
    label: 'AI 数字人',
    desc: '虚拟形象口播',
    tags: ['场景联动', '多引擎'],
    path: '/digital-human',
    icon: UserCircle,
    gradient: 'from-cyan-500 to-teal-600',
  },
  {
    label: '文案工厂',
    desc: '营销 · 自媒体 · SEO',
    tags: ['8 类型', '12 模板'],
    path: '/copywriting',
    icon: PenTool,
    gradient: 'from-pink-500 to-rose-600',
  },
]

// 首页组件元数据（与后端 dashboard_widgets 的 widget_type 对应）
const WIDGET_META = [
  {
    type: 'stats',
    label: '数据概览',
    desc: '统计卡片：Agent/Workflow/项目/任务等',
    icon: BarChart3,
  },
  { type: 'recent', label: '智能流水线', desc: '最近需求进度与部署状态', icon: GitBranch },
  { type: 'tasks', label: '任务中心', desc: 'AI 生成任务进度预览', icon: CheckCircle2 },
  { type: 'quick_actions', label: '快捷操作', desc: '常用功能快捷入口', icon: Zap },
  { type: 'notifications', label: '最新通知', desc: '未读通知预览', icon: Bell },
]

const PRIORITY_COLORS = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'gray' }

// 任务类型 / 状态展示映射（与任务中心页一致）
const TASK_TYPE_LABEL = {
  dh_generate: '数字人',
  game_generate: '小游戏生成',
  game_evolve: '小游戏迭代',
  miniapp_generate: '小程序生成',
  video_generate: '视频生成',
  music_lyrics: '歌词生成',
  music_sing: '人声合成',
  meme_generate: '表情包',
  image_t2i: '文生图',
  image_i2i: '图生图',
  image_template: '模板渲染',
  image_tryon: '虚拟试衣',
  voice_generate: 'AI 配音',
}
const TASK_STATUS_LABEL = {
  pending: '排队中',
  running: '执行中',
  success: '已完成',
  failed: '失败',
  interrupted: '已中断',
  canceled: '已取消',
}

// AI 工作台流水线阶段（与 AIWorkspacePage 保持一致）
const STAGES = [
  { key: 'prd', label: 'PRD', field: 'prd_text' },
  { key: 'review', label: 'PRD 审查', field: 'review_report' },
  { key: 'td', label: '技术方案', field: 'tech_design' },
  { key: 'test', label: '测试用例', field: 'test_cases' },
  { key: 'code', label: '代码生成', field: 'code' },
  { key: 'review_code', label: '代码审查', field: 'code_review' },
]

// 阶段状态：stale=上游变更需重新生成 / done=已有产物 / idle=未开始
function stageStatus(req, key) {
  let ps = req?.pipeline_status || {}
  if (typeof ps === 'string') {
    try {
      ps = JSON.parse(ps)
    } catch {
      ps = {}
    }
  }
  if (ps[key]?.status === 'stale') return 'stale'
  const stage = STAGES.find((s) => s.key === key)
  return req?.[stage.field] ? 'done' : 'idle'
}

const RUN_STATUS = {
  running: { label: '部署中', dot: 'bg-blue-500 animate-pulse', badge: 'blue' },
  success: { label: '运行中', dot: 'bg-green-500', badge: 'green' },
  failed: { label: '失败', dot: 'bg-red-500', badge: 'red' },
}

// 能力入口卡片（搜索结果展示）：带热标的能力高亮主推
function CapCard({ item, groupColor, onNavigate }) {
  return (
    <button
      onClick={() => onNavigate(item.path)}
      className="relative flex items-center gap-2.5 p-3 rounded-xl border border-gray-200 bg-white hover:border-brand-300 hover:shadow-sm hover:-translate-y-0.5 transition-all text-left group"
    >
      <span
        className={`w-8 h-8 rounded-lg bg-gradient-to-br ${groupColor} flex items-center justify-center flex-shrink-0`}
      >
        <item.icon className="w-4 h-4 text-white" />
      </span>
      <span className="min-w-0">
        <span className="block text-xs font-semibold text-gray-800 truncate">{item.label}</span>
        <span className="block text-[10px] text-gray-400 truncate">{item.desc}</span>
      </span>
      {item.hot && (
        <span className="absolute -top-1.5 -right-1.5 px-1.5 py-0.5 rounded-full bg-gradient-to-r from-amber-400 to-orange-500 text-white text-[9px] font-bold shadow-sm">
          主推
        </span>
      )}
    </button>
  )
}

// 能力入口小标签（分组概览展示）
function CapChip({ item, onNavigate }) {
  return (
    <button
      onClick={() => onNavigate(item.path)}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs transition-all ${
        item.hot
          ? 'bg-gradient-to-r from-brand-500 to-indigo-600 text-white font-medium shadow-sm hover:opacity-90'
          : 'bg-white border border-gray-200 text-gray-600 hover:border-brand-300 hover:text-brand-600'
      }`}
    >
      <item.icon className="w-3 h-3" />
      {item.label}
      {item.hot && <Sparkles className="w-3 h-3" />}
    </button>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState(null)
  // v16 最近使用：用户访问过的工具一键直达（localStorage 追踪）
  const { recent: recentTools, clear: clearRecentTools } = useRecentTools()
  const [tasks, setTasks] = useState([])
  const [notifications, setNotifications] = useState([])
  const [favorites, setFavorites] = useState([])
  const [toolStats, setToolStats] = useState([])
  const [drafts, setDrafts] = useState([])
  const [showcase, setShowcase] = useState([]) // 真实用户成果案例墙
  const [factoryWorks, setFactoryWorks] = useState([]) // 最新创作墙（图片/视频工厂真实作品）
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [capKw, setCapKw] = useState('')

  // 首页组件配置（null=未加载，默认全显示）
  const [widgets, setWidgets] = useState(null)
  const [widgetModal, setWidgetModal] = useState(false)
  const [widgetSaving, setWidgetSaving] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [
        statsRes,
        recentRes,
        tasksRes,
        notifsRes,
        favRes,
        toolRes,
        draftRes,
        widgetsRes,
        showcaseRes,
        factoryRes,
      ] = await Promise.all([
        api.get('/api/home/stats'),
        api.get('/api/home/recent'),
        api.get('/api/tasks', { params: { limit: 8 } }),
        api.get('/api/notifications?unread_only=true&limit=10'),
        api.get('/api/tools/favorites/list').catch(() => ({ data: [] })),
        api.get('/api/tools/stats').catch(() => ({ data: [] })),
        api.get('/api/drafts').catch(() => ({ data: [] })),
        api.get('/api/home/widgets').catch(() => ({ data: null })),
        api.get('/api/showcase').catch(() => ({ data: { items: [] } })),
        api.get('/api/factory/latest').catch(() => ({ data: { items: [] } })),
      ])
      setStats(statsRes.data)
      setRecent(recentRes.data)
      setTasks(tasksRes.data?.tasks || [])
      setNotifications(notifsRes.data?.items || [])
      setFavorites(favRes.data || [])
      setToolStats(toolRes.data || [])
      setDrafts(draftRes.data || [])
      if (widgetsRes?.data) setWidgets(widgetsRes.data)
      setShowcase(showcaseRes?.data?.items || [])
      setFactoryWorks(factoryRes?.data?.items || [])
      setLoadError('')
    } catch (e) {
      setLoadError(e?.message || '首页数据加载失败')
      toast.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  const deleteDraft = async (id) => {
    try {
      await api.delete(`/api/drafts/${id}`)
      setDrafts((prev) => prev.filter((d) => d.id !== id))
      toast.success('草稿已删除')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const markNotifRead = async (notifId) => {
    try {
      await api.put(`/api/notifications/${notifId}/read`)
      loadData()
    } catch {
      /* ignore */
    }
  }

  // ── 首页组件配置 ──
  const widgetVisible = (type) => {
    if (!widgets) return true
    const w = widgets.find((x) => x.widget_type === type)
    if (!w) return true
    return w.visible === 1 || w.visible === true
  }

  const openWidgetConfig = async () => {
    setWidgetModal(true)
    if (!widgets) {
      try {
        const res = await api.get('/api/home/widgets')
        setWidgets(res.data || [])
      } catch {
        /* 静默 */
      }
    }
  }

  const toggleWidget = (type) => {
    setWidgets((prev) =>
      (prev || []).map((w) =>
        w.widget_type === type
          ? { ...w, visible: w.visible === 1 || w.visible === true ? 0 : 1 }
          : w
      )
    )
  }

  const moveWidget = (type, dir) => {
    setWidgets((prev) => {
      if (!prev) return prev
      const idx = prev.findIndex((w) => w.widget_type === type)
      const target = idx + dir
      if (idx < 0 || target < 0 || target >= prev.length) return prev
      const next = [...prev]
      const [w] = next.splice(idx, 1)
      next.splice(target, 0, w)
      return next
    })
  }

  const saveWidgets = async () => {
    if (!widgets) return
    setWidgetSaving(true)
    try {
      await Promise.all(
        widgets.map((w, i) =>
          api.put(`/api/home/widgets/${w.id || w.widget_type}`, {
            widget_type: w.widget_type,
            title: w.title || '',
            config: w.config || {},
            position: i,
            size: w.size || 'md',
            visible: w.visible === 1 || w.visible === true,
          })
        )
      )
      toast.success('首页布局已保存')
      setWidgetModal(false)
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setWidgetSaving(false)
    }
  }

  // 问候语（随时间段变化）
  const now = new Date()
  const hour = now.getHours()
  const greeting = hour < 6 ? '夜深了' : hour < 12 ? '早上好' : hour < 18 ? '下午好' : '晚上好'
  const dateStr = now.toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
  let user = null
  try {
    user = JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    /* ignore */
  }

  const statCards = [
    {
      label: 'Agent',
      value: stats?.agents || 0,
      icon: Bot,
      color: 'from-emerald-500 to-teal-600',
      path: '/agents',
    },
    {
      label: 'Workflow',
      value: stats?.workflows || 0,
      icon: Layers,
      color: 'from-blue-500 to-indigo-600',
      path: '/workflows',
    },
    {
      label: '项目',
      value: stats?.projects || 0,
      icon: FolderKanban,
      color: 'from-violet-500 to-purple-600',
      path: '/projects',
    },
    {
      label: '任务中心',
      value: tasks.length,
      icon: CheckCircle2,
      color: 'from-amber-500 to-orange-600',
      path: '/tasks',
    },
    {
      label: '未读通知',
      value: stats?.notifications_unread || 0,
      icon: Bell,
      color: 'from-pink-500 to-rose-600',
      path: '/notifications',
    },
    {
      label: '成果',
      value: stats?.artifacts || 0,
      icon: FileText,
      color: 'from-cyan-500 to-blue-600',
      path: '/artifacts',
    },
  ]

  const quickActions = [
    { label: 'AI 工作台', icon: Sparkles, path: '/workspace', color: 'bg-brand-500' },
    { label: '需求看板', icon: ListTodo, path: '/board', color: 'bg-violet-500' },
    { label: '沙箱运行', icon: Play, path: '/sandbox', color: 'bg-emerald-500' },
    { label: 'CI/CD 流水线', icon: GitBranch, path: '/pipelines', color: 'bg-blue-500' },
    { label: '图片生成', icon: Image, path: '/image-factory', color: 'bg-purple-500' },
    { label: '效率工具箱', icon: Wrench, path: '/tool-hub', color: 'bg-orange-500' },
  ]

  const requirements = recent?.requirements || []
  const pipelines = recent?.pipelines || []
  const totalStale = (req) => STAGES.filter((s) => stageStatus(req, s.key) === 'stale').length

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
      </div>
    )
  }

  // 核心数据加载失败：全页兜底错误态 + 一键重试（不再静默空白）
  if (loadError && !stats) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <div className="w-14 h-14 bg-red-50 rounded-2xl flex items-center justify-center mb-4">
          <svg className="w-7 h-7 text-red-500" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
        </div>
        <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">首页数据加载失败</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">{loadError}</p>
        <Button variant="primary" icon={RefreshCw} onClick={loadData}>
          重新加载
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 欢迎区 */}
      <div className="bg-gradient-to-r from-brand-600 via-brand-500 to-indigo-500 rounded-2xl px-6 py-5 text-white shadow-lg relative overflow-hidden">
        <div className="absolute -right-8 -top-8 w-40 h-40 bg-white/10 rounded-full" />
        <div className="absolute right-16 -bottom-12 w-32 h-32 bg-white/10 rounded-full" />
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative z-10">
          <div>
            <h1 className="text-xl md:text-2xl font-bold">
              {greeting}，{user?.nickname || user?.username || '朋友'} 👋
            </h1>
            <p className="text-white/80 text-sm mt-1">
              {dateStr} · 欢迎回来，这里汇聚了你的一切工作
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              icon={Rocket}
              onClick={() => navigate('/workspace')}
              className="!bg-white !text-brand-700 hover:!bg-gray-50 shadow-lg"
            >
              打开 AI 工作台
            </Button>
            <Button
              icon={Zap}
              onClick={() => navigate('/tasks')}
              className="!bg-white/15 !text-white border border-white/40 hover:!bg-white/25"
            >
              任务中心
            </Button>
            <Button
              icon={Settings}
              onClick={openWidgetConfig}
              className="!bg-white/15 !text-white border border-white/40 hover:!bg-white/25"
            >
              首页配置
            </Button>
          </div>
        </div>
        {/* 能力数据条：让新用户 3 秒感知平台规模 */}
        <div className="flex items-center gap-6 mt-4 pt-4 border-t border-white/20 relative z-10 flex-wrap">
          {[
            { num: '54+', label: '效率工具' },
            { num: '4', label: 'AI 工坊' },
            { num: String(showcase.length || 0), label: '精选成果' },
            { num: '5', label: '大模型路由' },
          ].map((it) => (
            <div key={it.label} className="flex items-baseline gap-1.5">
              <span className="text-lg font-bold text-white">{it.num}</span>
              <span className="text-xs text-white/70">{it.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* v16 最近使用快捷区：按用户真实使用轨迹一键直达（去重置顶、相对时间、可清空） */}
      {recentTools.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-soft px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <HistoryIcon className="w-4 h-4 text-brand-500" />
              <h2 className="font-semibold text-gray-900">最近使用</h2>
              <span className="text-xs text-gray-400">你的常用工具，一键直达</span>
            </div>
            <button
              onClick={clearRecentTools}
              className="text-xs text-gray-400 hover:text-red-500 flex items-center gap-1 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              清空记录
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {recentTools.map((it) => (
              <button
                key={it.path}
                onClick={() => navigate(it.path)}
                className="group flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 bg-gray-50 hover:bg-brand-50 hover:border-brand-200 hover:shadow-sm transition-all"
              >
                <span className="text-base">{it.icon}</span>
                <span className="text-sm font-medium text-gray-700 group-hover:text-brand-700">
                  {it.label}
                </span>
                <span className="text-xs text-gray-400">{formatRecentTime(it.ts)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 特色创作工厂：平台主打卖点置顶专区 */}
      <div className="bg-gradient-to-br from-brand-500/5 via-white to-fuchsia-500/5 rounded-2xl border border-brand-100 p-5 shadow-soft">
        <div className="flex items-center gap-2 mb-4">
          <span className="relative flex h-8 w-8 items-center justify-center">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-30" />
            <span className="relative inline-flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-fuchsia-600">
              <Sparkles className="w-4 h-4 text-white" />
            </span>
          </span>
          <div>
            <h2 className="font-bold text-gray-900 leading-tight">特色创作工厂</h2>
            <p className="text-[11px] text-gray-400">平台主打 · AI 创作全品类一站式生成</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {FEATURE_FACTORIES.map((f) => (
            <button
              key={f.label}
              onClick={() => navigate(f.path)}
              className={`group relative flex flex-col gap-1.5 p-3 rounded-xl bg-white border transition-all text-left overflow-hidden hover:shadow-md hover:-translate-y-0.5 ${
                f.hot ? 'border-brand-300 ring-1 ring-brand-100' : 'border-gray-200 hover:border-brand-300'
              }`}
            >
              {f.hot && (
                <span className="absolute top-2 right-2 px-1.5 py-0.5 rounded-full bg-gradient-to-r from-amber-400 to-orange-500 text-white text-[9px] font-bold shadow-sm">
                  主打
                </span>
              )}
              <span
                className={`absolute top-0 right-0 w-16 h-16 rounded-bl-full bg-gradient-to-br ${f.gradient} opacity-10 group-hover:opacity-20 transition-opacity`}
              />
              <span
                className={`w-8 h-8 rounded-lg bg-gradient-to-br ${f.gradient} flex items-center justify-center shadow-sm`}
              >
                <f.icon className="w-4 h-4 text-white" />
              </span>
              <span className="text-sm font-semibold text-gray-900">{f.label}</span>
              <span className="text-[11px] text-gray-400 leading-snug">{f.desc}</span>
              <span className="flex flex-wrap gap-1 mt-0.5">
                {f.tags.map((t) => (
                  <span
                    key={t}
                    className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-50 text-gray-500 border border-gray-100 group-hover:bg-brand-50 group-hover:text-brand-600 group-hover:border-brand-100 transition-colors"
                  >
                    {t}
                  </span>
                ))}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* 精选作品墙：平台最新创作直显（点击直达同款创作） */}
      {factoryWorks.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-soft overflow-hidden">
          <div className="flex items-center justify-between px-5 pt-4 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-brand-500" />
              <h2 className="font-semibold text-gray-900">精选作品</h2>
              <span className="text-xs text-gray-400">
                平台用户最新生成的作品 · 点击直达同款创作
              </span>
            </div>
            <button
              onClick={() => navigate('/gallery')}
              className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-medium"
            >
              全部作品
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex gap-3 px-5 pb-5 overflow-x-auto scrollbar-thin">
            {factoryWorks.map((w) => (
              <button
                key={w.id}
                onClick={() => navigate(w.route)}
                className="group w-56 flex-shrink-0 text-left rounded-xl overflow-hidden border border-gray-200 hover:border-brand-300 hover:shadow-md transition-all"
              >
                <div className="relative aspect-video bg-gray-100">
                  {w.type === 'image' ? (
                    <img
                      src={absUrl(w.media_url)}
                      alt={w.prompt || '图片作品'}
                      loading="lazy"
                      className="w-full h-full object-cover transition-transform group-hover:scale-105 duration-300"
                    />
                  ) : w.thumbnail ? (
                    <img
                      src={absUrl(w.thumbnail)}
                      alt={w.prompt || '视频作品'}
                      loading="lazy"
                      className="w-full h-full object-cover transition-transform group-hover:scale-105 duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-100 to-blue-50">
                      <Film className="w-8 h-8 text-gray-400" />
                    </div>
                  )}
                  {w.type === 'video' && (
                    <>
                      <span className="absolute inset-0 flex items-center justify-center">
                        <span className="w-9 h-9 rounded-full bg-white/90 flex items-center justify-center shadow-md group-hover:scale-110 transition-transform">
                          <Play className="w-4 h-4 text-gray-900 ml-0.5 fill-gray-900" />
                        </span>
                      </span>
                      {w.duration > 0 && (
                        <span className="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/60 text-white text-[10px]">
                          {w.duration.toFixed(1)}s
                        </span>
                      )}
                    </>
                  )}
                  <span className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded-md bg-black/50 backdrop-blur text-white text-[10px] font-medium">
                    {w.type === 'video' ? '🎬 视频' : '🖼️ 图片'}
                  </span>
                </div>
                <div className="px-3 py-2">
                  <p className="text-xs text-gray-700 truncate">{w.prompt || w.author}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5">{w.author}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 全场景能力地图：说出你想做的事，快速找到对应能力 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-soft">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-brand-500" />
            <h2 className="font-semibold text-gray-900">全场景能力地图</h2>
            <span className="text-xs text-gray-400">平台能帮你做的事，都在这里</span>
          </div>
          <div className="relative flex-1 max-w-xs">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={capKw}
              onChange={(e) => setCapKw(e.target.value)}
              placeholder="想做什么？搜一下直达，如：图片、PPT、代码…"
              className="w-full pl-9 pr-8 py-2 text-sm border border-gray-200 rounded-xl focus:border-brand-400 focus:ring-2 focus:ring-brand-400/10 outline-none transition-all"
            />
            {capKw && (
              <button
                onClick={() => setCapKw('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {capKw.trim() ? (
          /* 搜索结果：按组聚合展示匹配的能力 */
          <div className="space-y-4">
            {SCENE_GROUPS.map((g) => {
              const matched = g.items.filter((it) =>
                (it.label + it.desc + (it.keywords || '') + g.label)
                  .toLowerCase()
                  .includes(capKw.trim().toLowerCase())
              )
              if (matched.length === 0) return null
              return (
                <div key={g.key}>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`w-6 h-6 rounded-lg bg-gradient-to-br ${g.color} flex items-center justify-center`}
                    >
                      <g.icon className="w-3 h-3 text-white" />
                    </span>
                    <span className="text-sm font-semibold text-gray-700">{g.label}</span>
                    <span className="text-xs text-gray-400">找到 {matched.length} 项</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                    {matched.map((it) => (
                      <CapCard
                        key={it.label}
                        item={it}
                        groupColor={g.color}
                        onNavigate={navigate}
                      />
                    ))}
                  </div>
                </div>
              )
            })}
            {ALL_CAPABILITIES.filter((it) =>
              (it.label + it.desc + (it.keywords || '') + it.group)
                .toLowerCase()
                .includes(capKw.trim().toLowerCase())
            ).length === 0 && (
              <div className="text-center py-8 text-gray-400">
                <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">没有找到「{capKw}」相关能力，试试其他关键词</p>
                <button
                  onClick={() => navigate('/workspace')}
                  className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-brand-500 to-indigo-600 text-white text-xs font-medium rounded-xl hover:opacity-90 transition-opacity"
                >
                  <Sparkles className="w-3.5 h-3.5" /> 或者直接用「一句话全自动」告诉我
                </button>
              </div>
            )}
          </div>
        ) : (
          /* 全部分组展示 */
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {SCENE_GROUPS.map((g) => (
              <div
                key={g.key}
                className="rounded-xl border border-gray-100 bg-gray-50/60 p-4 hover:border-brand-200 hover:shadow-sm transition-all"
              >
                <div className="flex items-center gap-2 mb-3">
                  <span
                    className={`w-7 h-7 rounded-lg bg-gradient-to-br ${g.color} flex items-center justify-center`}
                  >
                    <g.icon className="w-3.5 h-3.5 text-white" />
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-gray-900">{g.label}</div>
                    <div className="text-[10px] text-gray-400">{g.desc}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {g.items.map((it, idx) => (
                    <React.Fragment key={it.label}>
                      {it.group && (idx === 0 || g.items[idx - 1].group !== it.group) && (
                        <div className="w-full flex items-center gap-2 mt-1 mb-0.5 first:mt-0">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                            {it.group}
                          </span>
                          <span className="flex-1 h-px bg-gray-200/70" />
                        </div>
                      )}
                      <CapChip item={it} onNavigate={navigate} />
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 统计卡片 */}
      {widgetVisible('stats') && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {statCards.map((card) => (
            <div
              key={card.label}
              onClick={() => navigate(card.path)}
              className="bg-white rounded-xl border border-gray-200 p-4 cursor-pointer hover:shadow-md transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className={`w-8 h-8 rounded-lg bg-gradient-to-br ${card.color} flex items-center justify-center`}
                >
                  <card.icon className="w-4 h-4 text-white" />
                </div>
                <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-gray-500 transition-colors" />
              </div>
              <div className="text-2xl font-bold text-gray-900">{card.value}</div>
              <div className="text-xs text-gray-500">{card.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* 智能研发工作流：最近需求 + 最近部署 */}
      {widgetVisible('recent') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 最近需求（AI 流水线进度） */}
          <div className="lg:col-span-2">
            <Card>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-brand-500" />
                  <h2 className="font-semibold text-gray-900">最近需求 · 智能流水线</h2>
                  {requirements.length > 0 && <Badge color="brand">{requirements.length}</Badge>}
                </div>
                <Button variant="ghost" size="sm" onClick={() => navigate('/workspace')}>
                  新建需求 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
              {requirements.length === 0 ? (
                <div className="text-center py-10 text-gray-400">
                  <Rocket className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">还没有需求流水线</p>
                  <Button
                    variant="primary"
                    size="sm"
                    className="mt-3"
                    icon={Plus}
                    onClick={() => navigate('/workspace')}
                  >
                    创建第一个需求
                  </Button>
                  <p className="text-xs mt-2 text-gray-400">
                    从需求 → 审查 → 设计 → 测试 → 代码 → 部署，全流程 AI 驱动
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {requirements.map((req) => {
                    const staleCount = totalStale(req)
                    const doneCount = STAGES.filter(
                      (s) => stageStatus(req, s.key) === 'done'
                    ).length
                    return (
                      <div
                        key={req.id}
                        onClick={() => navigate(`/workspace?requirement_id=${req.id}`)}
                        className="p-3 rounded-lg border border-gray-200 hover:border-brand-300 hover:shadow-sm cursor-pointer transition-all group"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <CircleDot
                              className={`w-4 h-4 flex-shrink-0 ${staleCount > 0 ? 'text-amber-500' : 'text-emerald-500'}`}
                            />
                            <span className="text-sm font-medium text-gray-900 truncate">
                              {req.name}
                            </span>
                            <Badge color={PRIORITY_COLORS[req.priority]}>{req.priority}</Badge>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-xs text-gray-400">
                              {req.updated_at?.split('T')[0]}
                            </span>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="!py-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              继续流程 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                            </Button>
                          </div>
                        </div>
                        {/* 6 阶段进度条 */}
                        <div className="mt-2.5 flex items-center gap-1">
                          {STAGES.map((s, i) => {
                            const st = stageStatus(req, s.key)
                            return (
                              <React.Fragment key={s.key}>
                                {i > 0 && (
                                  <div
                                    className={`h-0.5 rounded flex-1 min-w-[6px] ${st === 'idle' ? 'bg-gray-200' : 'bg-emerald-400'}`}
                                  />
                                )}
                                <div
                                  title={`${s.label}：${st === 'stale' ? '需更新' : st === 'done' ? '已完成' : '未开始'}`}
                                  className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                                    st === 'stale'
                                      ? 'bg-amber-400 ring-2 ring-amber-100'
                                      : st === 'done'
                                        ? 'bg-emerald-500'
                                        : 'bg-gray-200'
                                  }`}
                                />
                              </React.Fragment>
                            )
                          })}
                          <span className="ml-2 text-[10px] text-gray-400 flex-shrink-0">
                            {doneCount}/6 阶段完成
                          </span>
                        </div>
                        <div className="mt-1.5 flex items-center gap-1.5 pl-1">
                          {STAGES.map((s) => (
                            <span key={s.key} className="text-[10px] text-gray-400">
                              {s.label}
                            </span>
                          ))}
                          {staleCount > 0 && (
                            <span className="ml-auto flex items-center gap-1 text-[10px] font-semibold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full">
                              <RefreshCcw className="w-2.5 h-2.5" /> {staleCount} 个阶段需更新
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

          {/* 最近部署状态 */}
          <div>
            <Card className="h-full">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <GitBranch className="w-5 h-5 text-blue-500" />
                  <h2 className="font-semibold text-gray-900">最近部署</h2>
                </div>
                <Button variant="ghost" size="sm" onClick={() => navigate('/pipelines')}>
                  全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
              {pipelines.length === 0 ? (
                <div className="text-center py-10 text-gray-400">
                  <GitBranch className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">暂无部署记录</p>
                  <p className="text-xs mt-1">在 AI 工作台生成代码后一键部署到沙箱</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {pipelines.map((p) => {
                    const run = p.last_run
                    const st = RUN_STATUS[run?.status] || {
                      label: run?.status || '未知',
                      dot: 'bg-gray-300',
                      badge: 'gray',
                    }
                    const port = p.config?.port
                    return (
                      <div
                        key={p.id}
                        onClick={() => navigate('/pipelines')}
                        className="p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium text-gray-900 truncate">
                            {p.name}
                          </span>
                          <Badge color={st.badge}>
                            <span className="flex items-center gap-1">
                              <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
                              {st.label}
                            </span>
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500">
                          {port && (
                            <span className="flex items-center gap-1 text-emerald-600 font-medium">
                              <ExternalLink className="w-3 h-3" /> localhost:{port}
                            </span>
                          )}
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" /> {p.updated_at?.split('T')[0]}
                          </span>
                          {run?.status === 'failed' && (
                            <span className="ml-auto flex items-center gap-1 text-amber-600 font-medium">
                              <Wrench className="w-3 h-3" /> 可 AI 修复
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

      {widgetVisible('tasks') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* AI 任务中心预览 */}
          <div className="lg:col-span-2">
            <Card>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-amber-500" />
                  <h2 className="font-semibold text-gray-900">AI 任务中心</h2>
                  <Badge color="gray">{tasks.length}</Badge>
                </div>
                <Button variant="ghost" size="sm" onClick={() => navigate('/tasks')}>
                  查看全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
              {tasks.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <CheckCircle2 className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p>暂无生成任务，去小游戏/图片/配音等工厂提交一个吧</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {tasks.slice(0, 5).map((task) => {
                    const active = task.status === 'pending' || task.status === 'running'
                    const failed = ['failed', 'interrupted'].includes(task.status)
                    return (
                      <div
                        key={task.id}
                        className="p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900">
                            {TASK_TYPE_LABEL[task.type] || task.type || '未知任务'}
                          </span>
                          <Badge
                            color={
                              failed
                                ? 'red'
                                : active
                                  ? 'blue'
                                  : task.status === 'success'
                                    ? 'green'
                                    : 'gray'
                            }
                          >
                            {TASK_STATUS_LABEL[task.status] || task.status}
                          </Badge>
                          <span className="ml-auto text-xs text-gray-400">
                            {task.created_at?.replace('T', ' ').slice(5, 16)}
                          </span>
                        </div>
                        <div className="mt-2 flex items-center gap-3">
                          <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${failed ? 'bg-red-400' : task.status === 'success' ? 'bg-green-500' : 'bg-brand-500'}`}
                              style={{ width: `${task.progress || 0}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500">
                            {active ? `${Math.round(task.progress || 0)}%` : ''}
                          </span>
                        </div>
                        <div className="mt-1 text-xs">
                          {failed ? (
                            <span className="text-red-500 truncate block">
                              {task.error || '执行失败'}
                            </span>
                          ) : (
                            <span className="text-gray-500 truncate block">
                              {task.stage || '任务排队中…'}
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

          {/* 右侧面板 */}
          <div className="space-y-6">
            {/* 快捷操作 */}
            {widgetVisible('quick_actions') && (
              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Zap className="w-5 h-5 text-blue-500" />
                  <h2 className="font-semibold text-gray-900">快捷操作</h2>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {quickActions.map((action) => (
                    <button
                      key={action.label}
                      onClick={() => navigate(action.path)}
                      className="flex items-center gap-2 p-2.5 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left"
                    >
                      <div
                        className={`w-7 h-7 rounded-lg ${action.color} flex items-center justify-center`}
                      >
                        <action.icon className="w-3.5 h-3.5 text-white" />
                      </div>
                      <span className="text-xs font-medium text-gray-700">{action.label}</span>
                    </button>
                  ))}
                </div>
              </Card>
            )}

            {/* 最新通知 */}
            {widgetVisible('notifications') && (
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Bell className="w-5 h-5 text-pink-500" />
                    <h2 className="font-semibold text-gray-900">最新通知</h2>
                    {notifications.length > 0 && <Badge color="red">{notifications.length}</Badge>}
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => navigate('/notifications')}>
                    全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </div>
                {notifications.length === 0 ? (
                  <div className="text-center py-6 text-gray-400">
                    <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-xs">暂无新通知</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {notifications.slice(0, 4).map((notif) => (
                      <div
                        key={notif.id}
                        onClick={() => markNotifRead(notif.id)}
                        className="p-2.5 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                      >
                        <div className="flex items-start gap-2">
                          <AlertCircle
                            className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                              notif.type === 'error'
                                ? 'text-red-500'
                                : notif.type === 'warning'
                                  ? 'text-amber-500'
                                  : notif.type === 'success'
                                    ? 'text-green-500'
                                    : 'text-blue-500'
                            }`}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-gray-900 truncate">
                              {notif.title}
                            </div>
                            <div className="text-xs text-gray-500 truncate">{notif.content}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}

            {/* 常用工具（使用统计 TOP6） */}
            {toolStats.length > 0 && (
              <Card>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-emerald-500" />
                    <h2 className="font-semibold text-gray-900">常用工具</h2>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => navigate('/tool-hub')}>
                    全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </div>
                <div className="space-y-1.5">
                  {toolStats.slice(0, 6).map((t) => (
                    <button
                      key={t.tool_id}
                      onClick={() => navigate(t.path ? t.path : `/tool/${t.tool_id}`)}
                      className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-gray-50 transition-colors text-left group"
                    >
                      <span
                        className={`w-7 h-7 rounded-lg ${t.color || 'bg-brand-500'} flex items-center justify-center flex-shrink-0`}
                      >
                        <span className="text-white text-xs">{t.name?.[0] || '工'}</span>
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="block text-xs font-medium text-gray-700 truncate">
                          {t.name}
                        </span>
                        <span className="block text-[10px] text-gray-400">
                          {t.category} · 用 {t.use_count} 次
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              </Card>
            )}

            {/* 我的收藏 */}
            {favorites.length > 0 && (
              <Card>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Star className="w-5 h-5 text-amber-400" fill="currentColor" />
                    <h2 className="font-semibold text-gray-900">我的收藏</h2>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => navigate('/tool-hub')}>
                    全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {favorites.slice(0, 8).map((t) => (
                    <button
                      key={t.id}
                      onClick={() => navigate(t.path ? t.path : `/tool/${t.id}`)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-xs text-amber-700 hover:bg-amber-100 transition-colors"
                    >
                      <Star className="w-3 h-3" fill="currentColor" />
                      {t.name}
                    </button>
                  ))}
                </div>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* 草稿箱 */}
      {drafts.length > 0 && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileEdit className="w-5 h-5 text-sky-500" />
              <h2 className="font-semibold text-gray-900">草稿箱</h2>
              <Badge color="blue">{drafts.length}</Badge>
              <span className="text-xs text-gray-400">
                在配音/表情包/文案等页面输入时会自动保存
              </span>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {drafts.map((d) => (
              <div
                key={d.id}
                className="group p-3 rounded-lg border border-gray-200 hover:border-sky-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="px-1.5 py-0.5 rounded bg-sky-50 text-sky-600 text-[10px] font-medium">
                    {d.tool_label}
                  </span>
                  <span className="text-[10px] text-gray-400 ml-auto">
                    {d.updated_at?.slice(5, 16).replace('T', ' ')}
                  </span>
                </div>
                <div className="text-sm font-medium text-gray-800 truncate">
                  {d.title || '未命名草稿'}
                </div>
                {d.content?.text && (
                  <div className="text-xs text-gray-400 truncate mt-0.5">
                    {String(d.content.text).slice(0, 40)}
                  </div>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <Button
                    variant="primary"
                    size="sm"
                    className="!py-1 flex-1"
                    onClick={() => d.tool_path && navigate(d.tool_path)}
                  >
                    继续编辑
                  </Button>
                  <button
                    onClick={() => deleteDraft(d.id)}
                    className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 最近项目 */}
      {recent?.projects?.length > 0 && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FolderKanban className="w-5 h-5 text-violet-500" />
              <h2 className="font-semibold text-gray-900">最近项目</h2>
            </div>
            <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
              查看全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {recent.projects.map((project) => (
              <div
                key={project.id}
                onClick={() => navigate(`/projects/${project.id}`)}
                className="p-3 rounded-lg border border-gray-200 hover:border-violet-300 hover:shadow-sm cursor-pointer transition-all"
              >
                <div className="font-medium text-sm text-gray-900 truncate">{project.name}</div>
                <div className="flex items-center gap-2 mt-2">
                  <Badge color={project.status === 'active' ? 'green' : 'gray'}>
                    {project.status}
                  </Badge>
                  <span className="text-xs text-gray-400">{project.updated_at?.split('T')[0]}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 首页组件配置弹窗 */}
      <Modal
        open={widgetModal}
        onClose={() => setWidgetModal(false)}
        title="首页组件配置"
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setWidgetModal(false)}>
              取消
            </Button>
            <Button variant="primary" icon={Save} loading={widgetSaving} onClick={saveWidgets}>
              保存布局
            </Button>
          </div>
        }
      >
        <div className="space-y-2">
          {(
            widgets ||
            WIDGET_META.map((m, i) => ({
              id: m.type,
              widget_type: m.type,
              title: m.label,
              config: {},
              position: i,
              size: 'md',
              visible: 1,
            }))
          ).map((w, i) => {
            const meta = WIDGET_META.find((m) => m.type === w.widget_type)
            if (!meta) return null
            const visible = w.visible === 1 || w.visible === true
            return (
              <div
                key={meta.type}
                className={`flex items-center gap-3 p-3 rounded-xl border transition-colors ${visible ? 'border-gray-200 bg-white' : 'border-gray-100 bg-gray-50 opacity-60'}`}
              >
                <span className="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                  <meta.icon className="w-4 h-4 text-white" />
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 flex items-center gap-2">
                    {meta.label}
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
                      {meta.type}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 truncate">{meta.desc}</div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => moveWidget(meta.type, -1)}
                    disabled={i === 0}
                    className="p-1.5 text-gray-400 hover:text-brand-600 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg hover:bg-gray-100"
                    title="上移"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => moveWidget(meta.type, 1)}
                    disabled={i === (widgets || WIDGET_META).length - 1}
                    className="p-1.5 text-gray-400 hover:text-brand-600 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg hover:bg-gray-100"
                    title="下移"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => toggleWidget(meta.type)}
                    className={`relative w-9 h-5 rounded-full transition-colors ${visible ? 'bg-brand-500' : 'bg-gray-300'}`}
                    title={visible ? '点击隐藏' : '点击显示'}
                  >
                    <span
                      className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${visible ? 'left-4' : 'left-0.5'}`}
                    />
                  </button>
                </div>
              </div>
            )
          })}
          <p className="text-xs text-gray-400 pt-1">
            布局保存在云端（GET/PUT /api/home/widgets），隐藏/显示与排序即时生效
          </p>
        </div>
      </Modal>
    </div>
  )
}
