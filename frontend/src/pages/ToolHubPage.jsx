import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Empty, Badge, SkeletonGrid, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import {
  FileText,
  ClipboardList,
  Mail,
  Target,
  Users,
  Sparkles,
  Heart,
  Video,
  Calendar,
  GraduationCap,
  BookOpen,
  GitBranch,
  Layers,
  Search,
  UserCircle,
  Megaphone,
  TrendingUp,
  BarChart,
  Presentation,
  Table,
  Code,
  Briefcase,
  Mic,
  DollarSign,
  Zap,
  Star,
  Clock,
  ArrowRight,
  Filter,
  Grid3X3,
  List,
  Flame,
  Rocket,
  Award,
  Briefcase as BriefcaseIcon,
  Building2,
  FlaskConical,
  Tag,
  Palette,
  PenTool,
  MessageSquare,
  Layout,
  Lock,
} from 'lucide-react'

const ICON_MAP = {
  FileText,
  ClipboardList,
  Mail,
  Target,
  Users,
  Sparkles,
  Heart,
  Video,
  Calendar,
  GraduationCap,
  BookOpen,
  GitBranch,
  Layers,
  Search,
  UserCircle,
  Megaphone,
  TrendingUp,
  BarChart,
  Presentation,
  Table,
  Code,
  Briefcase,
  Mic,
  DollarSign,
  FlaskConical,
  Tag,
  Palette,
  PenTool,
  MessageSquare,
  Layout,
}

const CATEGORY_COLORS = {
  职场办公: {
    bg: 'from-blue-500 to-indigo-600',
    light: 'bg-blue-50',
    text: 'text-blue-600',
    border: 'border-blue-200',
  },
  自媒体创作: {
    bg: 'from-pink-500 to-rose-600',
    light: 'bg-pink-50',
    text: 'text-pink-600',
    border: 'border-pink-200',
  },
  学习研究: {
    bg: 'from-cyan-500 to-teal-600',
    light: 'bg-cyan-50',
    text: 'text-cyan-600',
    border: 'border-cyan-200',
  },
  '产品/营销': {
    bg: 'from-purple-500 to-violet-600',
    light: 'bg-purple-50',
    text: 'text-purple-600',
    border: 'border-purple-200',
  },
  互联网行业: {
    bg: 'from-blue-500 to-cyan-600',
    light: 'bg-sky-50',
    text: 'text-sky-600',
    border: 'border-sky-200',
  },
  传统行业: {
    bg: 'from-amber-500 to-orange-600',
    light: 'bg-amber-50',
    text: 'text-amber-600',
    border: 'border-amber-200',
  },
  通用办公: {
    bg: 'from-gray-500 to-slate-600',
    light: 'bg-gray-50',
    text: 'text-gray-600',
    border: 'border-gray-200',
  },
  运营分析: {
    bg: 'from-teal-500 to-emerald-600',
    light: 'bg-teal-50',
    text: 'text-teal-600',
    border: 'border-teal-200',
  },
  金融财务: {
    bg: 'from-blue-600 to-indigo-700',
    light: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
  },
  人力资源: {
    bg: 'from-violet-500 to-purple-600',
    light: 'bg-violet-50',
    text: 'text-violet-600',
    border: 'border-violet-200',
  },
  法律合规: {
    bg: 'from-red-500 to-rose-600',
    light: 'bg-red-50',
    text: 'text-red-600',
    border: 'border-red-200',
  },
  电商运营: {
    bg: 'from-orange-500 to-amber-600',
    light: 'bg-orange-50',
    text: 'text-orange-600',
    border: 'border-orange-200',
  },
  设计创意: {
    bg: 'from-pink-500 to-fuchsia-600',
    light: 'bg-pink-50',
    text: 'text-pink-600',
    border: 'border-pink-200',
  },
  专业工具: {
    bg: 'from-orange-500 to-red-600',
    light: 'bg-orange-50',
    text: 'text-orange-600',
    border: 'border-orange-200',
  },
}

const CATEGORY_ICONS = {
  职场办公: Briefcase,
  自媒体创作: Video,
  学习研究: GraduationCap,
  '产品/营销': Target,
  互联网行业: Code,
  传统行业: Building2,
  通用办公: FileText,
  运营分析: BarChart,
  金融财务: DollarSign,
  人力资源: Users,
  法律合规: FileText,
  电商运营: Tag,
  设计创意: Palette,
  专业工具: Zap,
}

// 热门工具（首页推荐）
const HOT_TOOLS = [
  'meeting-notes',
  'xiaohongshu',
  'viral-title',
  'competitive-analysis',
  'ppt-factory',
  'excel-assistant',
]

export default function ToolHubPage() {
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('全部')
  const [viewMode, setViewMode] = useState('grid')
  const [favorites, setFavorites] = useState([])
  const [stats, setStats] = useState([])
  const [activeTab, setActiveTab] = useState('all') // all, favorites, stats
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    loadTools()
    loadFavorites()
    loadStats()
  }, [])

  const loadTools = async () => {
    try {
      setError(null)
      const res = await api.get('/api/tools')
      setTools(res.data)
    } catch (err) {
      setError(err.message || '加载工具列表失败')
      toast.error('加载工具列表失败')
    } finally {
      setLoading(false)
    }
  }

  const loadFavorites = async () => {
    try {
      const res = await api.get('/api/tools/favorites/list')
      setFavorites(res.data)
    } catch {
      // ignore
    }
  }

  const loadStats = async () => {
    try {
      const res = await api.get('/api/tools/stats')
      setStats(res.data)
    } catch {
      // ignore
    }
  }

  const toggleFavorite = async (toolId, e) => {
    e.stopPropagation()
    try {
      const res = await api.post(`/api/tools/favorites/${toolId}`)
      if (res.data.favorited) {
        toast.success('已收藏')
      } else {
        toast.info('已取消收藏')
      }
      loadFavorites()
    } catch {
      toast.error('操作失败')
    }
  }

  // 过滤工具
  const filteredTools = tools.filter((tool) => {
    const matchSearch =
      !searchQuery ||
      tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchCategory = selectedCategory === '全部' || tool.category === selectedCategory
    return matchSearch && matchCategory
  })

  // 按类别分组
  const grouped = filteredTools.reduce((acc, tool) => {
    if (!acc[tool.category]) acc[tool.category] = []
    acc[tool.category].push(tool)
    return acc
  }, {})

  // 热门工具
  const hotTools = tools.filter((t) => HOT_TOOLS.includes(t.id))

  // 获取分类颜色
  const getCategoryStyle = (category) =>
    CATEGORY_COLORS[category] || {
      bg: 'from-gray-500 to-gray-600',
      light: 'bg-gray-50',
      text: 'text-gray-600',
      border: 'border-gray-200',
    }

  if (loading) {
    return (
      <div className="flex-1 overflow-auto bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="mb-10 rounded-2xl bg-gradient-to-r from-gray-200 to-gray-300 p-8 animate-pulse">
            <div className="h-8 bg-white/30 rounded w-2/3 mb-2" />
            <div className="h-4 bg-white/30 rounded w-1/2" />
          </div>
          <SkeletonGrid count={8} />
        </div>
      </div>
    )
  }

  if (error && tools.length === 0) {
    return (
      <div className="flex-1 overflow-auto bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <ErrorState
            message={`工具列表加载失败：${error}`}
            onRetry={() => {
              setLoading(true)
              setError(null)
              loadTools()
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-b from-gray-50 to-white pb-16 md:pb-0">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Hero Section */}
        <div className="relative mb-10 overflow-hidden rounded-2xl bg-gradient-to-r from-brand-500 via-purple-500 to-pink-500 p-8 text-white">
          <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20viewBox%3D%220%200%2060%2060%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cg%20fill%3D%22none%22%20fill-rule%3D%22evenodd%22%3E%3Cg%20fill%3D%22%23ffffff%22%20fill-opacity%3D%220.05%22%3E%3Cpath%20d%3D%22M36%2034v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6%2034v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6%204V0H4v4H0v2h4v4h2V6h4V4H6z%22%2F%3E%3C%2Fg%3E%3C%2Fg%3E%3C%2Fsvg%3E')] opacity-20" />
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-white/20 rounded-xl backdrop-blur-sm">
                <Rocket className="w-8 h-8" />
              </div>
              <div>
                <h1 className="text-3xl font-bold">AI 效率工具箱</h1>
                <p className="text-white/80 text-sm mt-1">
                  {tools.length} 款专业工具 · 覆盖 {Object.keys(CATEGORY_COLORS).length} 大场景 ·
                  让工作效率提升 10 倍
                </p>
              </div>
            </div>

            {/* 搜索框 */}
            <div className="mt-6 max-w-xl">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索工具名称或功能..."
                  className="w-full pl-12 pr-4 py-3 bg-white rounded-xl text-gray-900 placeholder-gray-400 outline-none focus:ring-2 focus:ring-white/50 shadow-lg"
                />
              </div>
            </div>
          </div>
        </div>

        {/* 热门工具 */}
        {hotTools.length > 0 && !searchQuery && selectedCategory === '全部' && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <Flame className="w-5 h-5 text-orange-500" />
              <h2 className="text-lg font-semibold text-gray-900">热门推荐</h2>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {hotTools.map((tool) => {
                const Icon = ICON_MAP[tool.icon] || Sparkles
                const colors = getCategoryStyle(tool.category)
                return (
                  <div
                    key={tool.id}
                    onClick={() =>
                      navigate(
                        tool.locked
                          ? '/membership'
                          : tool.type === 'app'
                            ? tool.path
                            : `/tool/${tool.id}`
                      )
                    }
                    className={`group relative bg-white rounded-xl border border-gray-200 p-4 transition-all cursor-pointer ${
                      tool.locked
                        ? 'hover:border-amber-300 hover:shadow-lg'
                        : 'hover:shadow-lg hover:border-brand-300'
                    }`}
                  >
                    <div className="absolute -top-1 -right-1">
                      <Star className="w-5 h-5 text-yellow-400 fill-yellow-400" />
                    </div>
                    {tool.locked && (
                      <div className="absolute top-2 right-8 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 bg-amber-50 rounded flex items-center gap-0.5">
                        <Lock className="w-3 h-3" />
                        {tool.requires === 'vip' ? '至尊会员' : '专业会员'}
                      </div>
                    )}
                    <div
                      className={`w-10 h-10 rounded-lg bg-gradient-to-br ${colors.bg} flex items-center justify-center mb-2 group-hover:scale-110 transition-transform ${tool.locked ? 'opacity-60' : ''}`}
                    >
                      <Icon className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div className="font-medium text-sm text-gray-900">{tool.name}</div>
                      {tool.type === 'compute' && (
                        <span className="px-1 py-0.5 text-[9px] font-bold text-emerald-600 bg-emerald-50 rounded">
                          ⚡实算
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 truncate mt-0.5">{tool.category}</div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* 标签页切换 */}
        <div className="flex items-center gap-4 mb-6 border-b border-gray-200">
          <button
            onClick={() => {
              setActiveTab('all')
              setSelectedCategory('全部')
            }}
            className={`pb-3 px-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'all'
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Grid3X3 className="w-4 h-4 inline mr-1.5" />
            全部工具
          </button>
          <button
            onClick={() => setActiveTab('favorites')}
            className={`pb-3 px-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'favorites'
                ? 'border-yellow-500 text-yellow-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Star className="w-4 h-4 inline mr-1.5" />
            我的收藏 ({favorites.length})
          </button>
          <button
            onClick={() => setActiveTab('stats')}
            className={`pb-3 px-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'stats'
                ? 'border-teal-500 text-teal-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <BarChart className="w-4 h-4 inline mr-1.5" />
            使用统计
          </button>
        </div>

        {/* 收藏页 */}
        {activeTab === 'favorites' && (
          <div className="mb-8">
            {favorites.length > 0 ? (
              <div
                className={`grid gap-3 ${viewMode === 'grid' ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1'}`}
              >
                {favorites.map((tool) => {
                  const colors = getCategoryStyle(tool.category)
                  return (
                    <ToolCard
                      key={tool.id}
                      tool={tool}
                      colors={colors}
                      viewMode={viewMode}
                      isFavorite={true}
                      onToggleFavorite={(e) => toggleFavorite(tool.id, e)}
                      onClick={() => navigate(tool.type === 'app' ? tool.path : `/tool/${tool.id}`)}
                    />
                  )
                })}
              </div>
            ) : (
              <Empty icon={Star} title="暂无收藏" description="点击工具卡片上的星标即可收藏" />
            )}
          </div>
        )}

        {/* 使用统计页 */}
        {activeTab === 'stats' && (
          <div className="mb-8">
            {stats.length > 0 ? (
              <div className="space-y-3">
                {stats.map((stat, index) => {
                  const colors = getCategoryStyle(stat.category)
                  const Icon = ICON_MAP[stat.icon] || Sparkles
                  return (
                    <div
                      key={stat.tool_id}
                      onClick={() => navigate(`/tool/${stat.tool_id}`)}
                      className="flex items-center gap-4 bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md hover:border-brand-300 transition-all cursor-pointer"
                    >
                      <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center text-sm font-bold text-gray-500">
                        {index + 1}
                      </div>
                      <div
                        className={`w-10 h-10 rounded-lg bg-gradient-to-br ${colors.bg} flex items-center justify-center`}
                      >
                        <Icon className="w-5 h-5 text-white" />
                      </div>
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{stat.name}</div>
                        <div className="text-xs text-gray-500">{stat.category}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-gray-900">{stat.use_count}</div>
                        <div className="text-xs text-gray-500">次使用</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <Empty
                icon={BarChart}
                title="暂无使用记录"
                description="使用工具后会自动统计使用次数"
              />
            )}
          </div>
        )}

        {/* 分类导航 - 仅在全部工具页显示 */}
        {activeTab === 'all' && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex flex-wrap items-center gap-2 pb-2">
                <button
                  onClick={() => setSelectedCategory('全部')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                    selectedCategory === '全部'
                      ? 'bg-brand-500 text-white'
                      : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                  }`}
                >
                  全部 ({tools.length})
                </button>
                {Object.keys(CATEGORY_COLORS).map((cat) => {
                  const count = tools.filter((t) => t.category === cat).length
                  if (count === 0) return null
                  const colors = getCategoryStyle(cat)
                  return (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                        selectedCategory === cat
                          ? `bg-gradient-to-r ${colors.bg} text-white`
                          : `bg-white ${colors.text} hover:${colors.light} border ${colors.border}`
                      }`}
                    >
                      {cat} ({count})
                    </button>
                  )
                })}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-2 rounded-lg ${viewMode === 'grid' ? 'bg-brand-50 text-brand-600' : 'text-gray-400 hover:bg-gray-100'}`}
                >
                  <Grid3X3 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`p-2 rounded-lg ${viewMode === 'list' ? 'bg-brand-50 text-brand-600' : 'text-gray-400 hover:bg-gray-100'}`}
                >
                  <List className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 工具展示 - 仅在全部工具页显示 */}
        {activeTab === 'all' && (
          <>
            {/* 工具展示 */}
            {selectedCategory === '全部' ? (
              // 全部 - 按分类展示
              Object.entries(grouped).map(([category, items]) => {
                const colors = getCategoryStyle(category)
                const CatIcon = CATEGORY_ICONS[category] || Sparkles
                return (
                  <div key={category} className="mb-8">
                    <div className="flex items-center gap-3 mb-4">
                      <div
                        className={`w-8 h-8 rounded-lg bg-gradient-to-br ${colors.bg} flex items-center justify-center`}
                      >
                        <CatIcon className="w-4 h-4 text-white" />
                      </div>
                      <h2 className="text-lg font-semibold text-gray-900">{category}</h2>
                      <Badge variant="info">{items.length}</Badge>
                    </div>
                    <div
                      className={`grid gap-3 ${viewMode === 'grid' ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1'}`}
                    >
                      {items.map((tool) => (
                        <ToolCard
                          key={tool.id}
                          tool={tool}
                          colors={colors}
                          viewMode={viewMode}
                          isFavorite={favorites.some((f) => f.id === tool.id)}
                          onToggleFavorite={(e) => toggleFavorite(tool.id, e)}
                          onClick={() =>
                            navigate(tool.type === 'app' ? tool.path : `/tool/${tool.id}`)
                          }
                        />
                      ))}
                    </div>
                  </div>
                )
              })
            ) : (
              // 单分类 - 平铺展示
              <div
                className={`grid gap-3 ${viewMode === 'grid' ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1'}`}
              >
                {filteredTools.map((tool) => {
                  const colors = getCategoryStyle(tool.category)
                  return (
                    <ToolCard
                      key={tool.id}
                      tool={tool}
                      colors={colors}
                      viewMode={viewMode}
                      isFavorite={favorites.some((f) => f.id === tool.id)}
                      onToggleFavorite={(e) => toggleFavorite(tool.id, e)}
                      onClick={() => navigate(tool.type === 'app' ? tool.path : `/tool/${tool.id}`)}
                    />
                  )
                })}
              </div>
            )}

            {/* 空状态 */}
            {filteredTools.length === 0 && (
              <Empty
                icon={Search}
                title="没有找到匹配的工具"
                description="试试其他关键词或切换分类"
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}

// 工具卡片组件
function ToolCard({ tool, colors, viewMode, isFavorite, onToggleFavorite, onClick }) {
  const Icon = ICON_MAP[tool.icon] || Sparkles
  const navigate = useNavigate()
  const locked = tool.locked
  const handleClick = () => {
    if (locked) {
      navigate('/membership')
      return
    }
    onClick()
  }

  if (viewMode === 'list') {
    return (
      <div
        onClick={handleClick}
        className={`flex items-center gap-4 bg-white rounded-xl border border-gray-200 p-4 transition-all group ${
          locked
            ? 'cursor-pointer hover:border-amber-300 hover:shadow-md'
            : 'hover:shadow-md hover:border-brand-300 cursor-pointer'
        }`}
      >
        <div
          className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colors.bg} flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform ${locked ? 'opacity-60' : ''}`}
        >
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-900">{tool.name}</span>
            {tool.type === 'app' && (
              <Badge variant="info" size="sm">
                专业版
              </Badge>
            )}
            {locked && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 bg-amber-50 border border-amber-200 rounded-full">
                <Lock className="w-3 h-3" />
                {tool.requires === 'vip' ? '至尊会员' : '专业会员'}
              </span>
            )}
          </div>
          <div className="text-sm text-gray-500 truncate">{tool.description}</div>
        </div>
        <div className="flex items-center gap-2">
          {!locked && (
            <button
              onClick={onToggleFavorite}
              className={`p-1.5 rounded-lg transition-colors ${isFavorite ? 'text-yellow-500 bg-yellow-50' : 'text-gray-300 hover:text-yellow-500 hover:bg-yellow-50'}`}
            >
              <Star className={`w-4 h-4 ${isFavorite ? 'fill-yellow-500' : ''}`} />
            </button>
          )}
          <Badge variant="outline" className={colors.text}>
            {tool.category}
          </Badge>
          <ArrowRight
            className={`w-4 h-4 ${locked ? 'text-amber-400' : 'text-gray-400 group-hover:text-brand-500 group-hover:translate-x-1'} transition-all`}
          />
        </div>
      </div>
    )
  }

  return (
    <div
      onClick={handleClick}
      className={`bg-white rounded-xl border border-gray-200 p-4 transition-all group relative ${
        locked
          ? 'cursor-pointer hover:border-amber-300 hover:shadow-lg'
          : 'hover:shadow-lg hover:border-brand-300 cursor-pointer'
      }`}
    >
      {/* 收藏按钮 */}
      {!locked && (
        <button
          onClick={onToggleFavorite}
          className={`absolute top-2 right-2 p-1.5 rounded-lg transition-colors z-10 ${
            isFavorite
              ? 'text-yellow-500 bg-yellow-50'
              : 'text-gray-300 opacity-0 group-hover:opacity-100 hover:text-yellow-500 hover:bg-yellow-50'
          }`}
        >
          <Star className={`w-4 h-4 ${isFavorite ? 'fill-yellow-500' : ''}`} />
        </button>
      )}
      {locked && (
        <div className="absolute top-2 right-2 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 bg-amber-50 rounded flex items-center gap-0.5 z-10">
          <Lock className="w-3 h-3" />
          {tool.requires === 'vip' ? '至尊会员' : '专业会员'}
        </div>
      )}
      {tool.type === 'app' && !isFavorite && !locked && (
        <div className="absolute top-2 right-2 px-1.5 py-0.5 text-[10px] font-medium text-brand-600 bg-brand-50 rounded">
          专业版
        </div>
      )}
      <div
        className={`w-10 h-10 rounded-lg bg-gradient-to-br ${colors.bg} flex items-center justify-center mb-3 group-hover:scale-110 transition-transform ${locked ? 'opacity-60' : ''}`}
      >
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div className="font-medium text-gray-900 mb-1">{tool.name}</div>
      <div className="text-xs text-gray-500 line-clamp-2 mb-2">{tool.description}</div>
      <div className="flex items-center justify-between">
        <span className={`text-xs ${colors.text}`}>{tool.category}</span>
        <ArrowRight
          className={`w-4 h-4 ${locked ? 'text-amber-400' : 'text-gray-300 group-hover:text-brand-500 group-hover:translate-x-1'} transition-all`}
        />
      </div>
    </div>
  )
}
