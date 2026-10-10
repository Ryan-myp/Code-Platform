import React, { useState, useMemo } from 'react'
import {
  Code2,
  Bot,
  Layers,
  Sparkles,
  Settings,
  Database,
  Wrench,
  Server,
  ListTodo,
  FileText,
  FolderKanban,
  Puzzle,
  MessageSquare,
  Brain,
  ChevronDown,
  ChevronRight,
  Menu,
  X,
  Play,
  Image as ImageIcon,
  Film,
  Music,
  Wand2,
  LogOut,
  Users,
  Zap,
  Home,
  CheckCircle2,
  Bell,
  Share2,
  Shield,
  GitBranch,
  PenTool,
  Languages,
  BarChart3,
  FlaskConical,
  Presentation,
  Table2,
  TrendingUp,
  HelpCircle,
  History as HistoryIcon,
  Crown,
  Lock,
  Search,
  Send,
  Smartphone,
  Gamepad2,
  Mic2,
  Sticker,
  Moon,
  Sun,
  UserCircle,
  GalleryVerticalEnd,
  Store,
  Clapperboard,
  Globe,
  Key,
  Keyboard,
  Clock,
  Download,
  Volume2,
  Monitor,
  Landmark,
  Target,
  FileSearch,
  Files,
  Activity,
  BookOpen,
  Terminal,
  Radar,
  Star,
  Lightbulb,
  ArrowRightLeft,
} from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { ConfirmDialog } from './ui'
import { useToast } from '../lib/toast'
import useQuota from '../hooks/useQuota'
import useAccess from '../hooks/useAccess'
import useTheme from '../hooks/useTheme'
import ModelSwitcher from './ModelSwitcher'

// icon 名称 → lucide-react 组件映射
const ICONS = {
  Home, Code2, Bot, Layers, Sparkles, Settings, Database, Wrench, Server,
  ChevronRight, Menu, X, Play, ImageIcon, Film, Music, Wand2, LogOut, Users,
  Zap, CheckCircle2, Bell, Share2, Shield, GitBranch, PenTool, Languages,
  BarChart3, FlaskConical, Presentation, Table2, TrendingUp, HelpCircle,
  HistoryIcon, Crown, Lock, Search, Send, Smartphone, Gamepad2, Mic2, Sticker, Keyboard,
  Moon, Sun, UserCircle, GalleryVerticalEnd, Store, Clapperboard, Globe,
  Key, Clock, Volume2, Monitor, Landmark, Target, FileSearch, Files, Activity,
  BookOpen, Terminal, Radar, Star, Lightbulb, ArrowRightLeft,
}

// 默认导航（通用版兜底）— 5 层精简 IA：高频入口直达，长尾收敛到「更多→⌘K 命令面板 / 首页能力地图」
// 设计原则：单一主焦点(AI 工作台) + 渐进披露，消除 67 项平铺导致的「看不出重点」
const DEFAULT_NAV_ITEMS = [
  {
    key: 'home',
    label: '工作台',
    icon: Home,
    color: 'from-blue-500 to-indigo-600',
    items: [
      { path: '/home', label: '首页', icon: Home },
      { path: '/workspace', label: 'AI 工作台', icon: Sparkles, flagship: true },
      { path: '/tasks', label: '任务中心', icon: CheckCircle2 },
      { path: '/records', label: '记录中心', icon: HistoryIcon },
      { path: '/notifications', label: '通知中心', icon: Bell },
    ],
  },
  {
    key: 'create',
    label: '创作工坊',
    icon: Wand2,
    color: 'from-accent-500 to-blue-600',
    more: true, // 组内已精简，长尾(短剧/音乐/翻译/配音/发布/SEO/竞品/增长/作品/模板)走「更多」
    items: [
      { path: '/image-factory', label: '图片工厂', icon: ImageIcon, pageId: 'image-factory' },
      { path: '/video-factory', label: '视频工厂', icon: Film, pageId: 'video-factory' },
      { path: '/ppt-factory', label: 'PPT 工厂', icon: Presentation, pageId: 'ppt-factory' },
      { path: '/copywriting', label: '文案工厂', icon: PenTool, pageId: 'copywriting' },
      { path: '/games', label: '小游戏工坊', icon: Gamepad2, pageId: 'games' },
      { path: '/meme', label: '表情包工坊', icon: Sticker, pageId: 'meme' },
    ],
  },
  {
    key: 'tools',
    label: 'AI 与工具',
    icon: Brain,
    color: 'from-teal-500 to-cyan-600',
    more: true, // 长尾(数字人/语音/视频理解/导图/预测/联网/代码解释器/PDF/批量/看板/AB…)走「更多」
    items: [
      { path: '/tool-hub', label: '全部工具', icon: Wrench, flagship: true },
      { path: '/data-analyzer', label: '数据分析', icon: BarChart3, pageId: 'data-analyzer' },
      { path: '/doc-qa', label: '文档问答', icon: Search, pageId: 'doc-qa' },
      { path: '/excel', label: 'Excel 助手', icon: Table2, pageId: 'excel' },
      { path: '/stock', label: '股票分析', icon: Landmark, pageId: 'stock' },
    ],
  },
  {
    key: 'manage',
    label: '协作与管理',
    icon: Settings,
    color: 'from-violet-500 to-purple-600',
    more: true, // 长尾(Team/Skills/MCP/API开放/定时任务/插件/审计…)走「更多」
    items: [
      { path: '/chat', label: '智能协作', icon: MessageSquare, pageId: 'chat' },
      { path: '/knowledge-bases', label: '知识库', icon: Database },
      { path: '/agents', label: 'Agent 智能体', icon: Bot, pageId: 'agents' },
      { path: '/workflows', label: '工作流编排', icon: Layers, pageId: 'workflows' },
      { path: '/config', label: '模型配置', icon: Settings },
    ],
  },
  {
    key: 'member',
    label: '会员与帮助',
    icon: Crown,
    color: 'from-amber-500 to-orange-600',
    items: [
      { path: '/membership', label: '会员中心', icon: Crown },
      { path: '/help', label: '使用帮助', icon: HelpCircle },
    ],
  },
]

export default function Sidebar({ sidebarOpen, setSidebarOpen, user, portal, onLogout, onPortalSwitch }) {
  const location = useLocation()
  const activePath = location.pathname
  const toast = useToast()
  const { quota } = useQuota()
  const { getPageStatusById } = useAccess()
  const { theme, toggleTheme } = useTheme()
  const [confirmLogout, setConfirmLogout] = useState(false)
  const [showPortalSwitcher, setShowPortalSwitcher] = useState(false)

  // 门户自定义导航 或 默认导航
  const navItems = useMemo(() => {
    if (portal?.nav_groups && portal.nav_groups.length > 0) {
      return portal.nav_groups.map(g => ({
        key: g.key,
        label: g.label,
        icon: ICONS[g.icon_key] || Brain,
        color: g.color || 'from-gray-500 to-gray-600',
        items: (g.items || []).map(item => ({
          path: item.path,
          label: item.label,
          icon: item.pageId ? (ICONS[item.pageId] || Search) : (ICONS[item.icon] || Search),
          pageId: item.pageId,
        })),
      }))
    }
    // 无自定义导航时追加管理员入口（仅挂到「协作与管理」组，避免在每组重复出现）
    const isAdmin = user?.role === 'admin'
    return DEFAULT_NAV_ITEMS.map((m) => ({
      ...m,
      items: m.items.concat(
        isAdmin && m.key === 'manage' ? [
          { path: '/admin', label: '管理后台', icon: Shield },
          { path: '/audit-log', label: '审计日志', icon: Activity },
        ] : []
      ),
    }))
  }, [portal, user])

  const initExpanded = {}
  navItems.forEach((m) => {
    initExpanded[m.key] = m.items.some((i) => activePath.startsWith(i.path))
  })
  const [expandedMenus, setExpandedMenus] = React.useState(initExpanded)

  const toggleMenu = (key) => {
    setExpandedMenus((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleLogout = () => {
    setConfirmLogout(false)
    onLogout()
    toast.success('已安全退出登录')
  }

  // 门户切换
  const handlePortalSwitch = async (portalType) => {
    try {
      const res = await fetch('/api/portal/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portal_type: portalType }),
      })
      if (res.ok) {
        const newPortal = await res.json()
        onPortalSwitch(newPortal)
        setShowPortalSwitcher(false)
        toast.success(`已切换到${newPortal.portal_name}`)
        window.location.reload()
      }
    } catch (e) {
      toast.error('切换门户失败，请重试')
    }
  }

  const renderNav = (onNavigate) => (
    <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
      {navItems.map((menu) => {
        const visibleItems = menu.items.filter(
          (i) => !i.pageId || getPageStatusById(i.pageId).visible
        )
        if (visibleItems.length === 0) return null
        const isActiveMenu = visibleItems.some((i) => activePath.startsWith(i.path))
        return (
          <div key={menu.key} className="mb-1">
            <button
              onClick={() => toggleMenu(menu.key)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm transition-all duration-200 ${
                isActiveMenu
                  ? 'bg-brand-50 text-brand-800 font-semibold'
                  : 'text-ink-600 hover:bg-ink-50 hover:text-ink-800'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <div
                  className={`w-7 h-7 rounded-lg bg-gradient-to-br ${menu.color} flex items-center justify-center shadow-soft`}
                >
                  <menu.icon className="w-3.5 h-3.5 text-white" />
                </div>
                <span>{menu.label}</span>
              </div>
              {expandedMenus[menu.key] ? (
                <ChevronDown className="w-3.5 h-3.5 text-ink-400" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-ink-400" />
              )}
            </button>
            {expandedMenus[menu.key] && (
              <div className="ml-4 mt-0.5 space-y-0.5 border-l border-ink-200/60 pl-3 py-0.5">
                {visibleItems.map((item, idx) => {
                  const pageStatus = item.pageId ? getPageStatusById(item.pageId) : null
                  const locked = !!pageStatus?.locked
                  const active =
                    activePath === item.path ||
                    (item.path !== '/agents' && activePath.startsWith(item.path))
                  return (
                    <React.Fragment key={item.path}>
                      <Link
                        to={locked ? '/membership' : item.path}
                        onClick={onNavigate}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                          locked
                            ? 'text-ink-400 hover:bg-amber-50 hover:text-amber-600'
                            : active
                              ? 'bg-brand-100 text-brand-700 font-medium shadow-soft'
                              : 'text-ink-500 hover:bg-ink-50 hover:text-ink-800 hover:translate-x-0.5'
                        }`}
                      >
                        <item.icon
                          className={`w-3.5 h-3.5 ${locked ? 'text-amber-400' : active ? 'text-brand-600' : 'text-ink-400'}`}
                        />
                        <span>{item.label}</span>
                        {item.flagship && !locked && (
                          <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-gradient-to-r from-brand-500 to-indigo-600 text-white text-[9px] font-semibold">
                            <Sparkles className="w-2.5 h-2.5" /> 主打
                          </span>
                        )}
                        {locked ? (
                          <Lock className="w-3 h-3 text-amber-500 ml-auto" />
                        ) : (
                          active && (
                            <span className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-500" />
                          )
                        )}
                      </Link>
                    </React.Fragment>
                  )
                })}
                {/* 长尾「更多」：收敛到全局 ⌘K 命令面板 / 首页能力地图 */}
                {menu.more && (
                  <button
                    onClick={() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
                    className="mt-0.5 ml-3 flex items-center gap-1.5 pl-3 py-1.5 text-xs text-ink-400 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition-colors border-l border-ink-200/60"
                    title="还有更多功能，按 ⌘K 搜索全部"
                  >
                    <Search className="w-3 h-3" />
                    更多功能
                    <kbd className="px-1 py-0.5 text-[9px] bg-ink-50 border border-ink-200 rounded font-mono">⌘K</kbd>
                  </button>
                )}
              </div>
            )}
          </div>
        )
      })}
    </nav>
  )

  const renderUser = (onNavigate) => (
    <div className="px-3 py-3 border-t border-ink-100 bg-gradient-to-b from-ink-50/50 to-transparent">
      <ModelSwitcher />
      {user && (
        <div className="flex items-center justify-between mb-2 px-1">
          <Link
            to="/profile"
            onClick={onNavigate}
            className="flex items-center gap-2.5 min-w-0 group"
          >
            <div className="w-9 h-9 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl flex items-center justify-center shadow-soft flex-shrink-0">
              <span className="text-white text-sm font-semibold">
                {user.username?.[0]?.toUpperCase()}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink-800 truncate group-hover:text-brand-600 transition-colors">
                {user.nickname || user.username}
              </p>
              <p className="text-xs text-ink-500 capitalize">{user.role}</p>
            </div>
          </Link>
          <button
            onClick={() => setConfirmLogout(true)}
            className="p-2 hover:bg-red-50 rounded-lg transition-colors text-ink-400 hover:text-red-500"
            title="退出登录"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      )}
      {user && quota && (
        <Link
          to="/profile"
          onClick={onNavigate}
          className="flex items-center justify-between px-3 py-2 rounded-xl bg-brand-50/60 border border-brand-100/80 hover:bg-brand-50 transition-colors"
        >
          <span className="text-xs text-ink-600 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-brand-500" />
            今日额度
          </span>
          <span
            className={`text-xs font-semibold ${quota.remaining_today >= 9999 ? 'text-amber-600' : quota.remaining_today <= 5 ? 'text-red-500' : 'text-brand-600'}`}
          >
            {quota.remaining_today >= 9999 ? '无限' : `剩 ${quota.remaining_today} 次`}
          </span>
        </Link>
      )}
      {user && (
        <Link
          to="/membership"
          onClick={onNavigate}
          className="flex items-center justify-between px-3 py-2 rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200/80 hover:from-amber-100 hover:to-orange-100 transition-colors"
        >
          <span className="text-xs text-ink-700 flex items-center gap-1.5">
            <Crown className="w-3.5 h-3.5 text-amber-500" />
            升级会员
          </span>
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-500 text-white">
            ¥19.9 起
          </span>
        </Link>
      )}
      <div className="flex items-center justify-center gap-1 text-xs text-ink-400 pt-2">
        <Zap className="w-3 h-3 text-brand-400" />
        <span>Powered by Agno</span>
        <span className="text-ink-300">·</span>
        <span>v16.0</span>
        <span className="text-ink-300">·</span>
        <button
          onClick={toggleTheme}
          className="flex items-center gap-1 hover:text-brand-500 transition-colors"
          title="切换深色 / 浅色模式"
        >
          {theme === 'dark' ? <Sun className="w-3 h-3" /> : <Moon className="w-3 h-3" />}
          <span>{theme === 'dark' ? '深色' : '浅色'}</span>
        </button>
      </div>
    </div>
  )

  // 可用门户列表（排除当前门户）
  const otherPortals = [
    { id: 'rdm', name: '研发管理版', desc: '需求→开发→测试→部署' },
    { id: 'media', name: '自媒体创作版', desc: '内容生产→发布→运营' },
    { id: 'general', name: '通用版', desc: '全部功能' },
  ].filter(p => p.id !== (portal?.portal_type || 'general'))

  return (
    <>
      {/* Desktop Sidebar */}
      <div className="hidden md:block fixed left-0 top-0 bottom-0 z-30 w-64 bg-white/95 backdrop-blur-xl border-r border-ink-200/60 shadow-soft">
        <div className="h-full flex flex-col">
          <div className="px-4 py-4 border-b border-ink-100">
            <Link to="/home" className="flex items-center gap-3 group">
              <div className="w-11 h-11 bg-gradient-to-br from-brand-500 via-brand-600 to-brand-700 rounded-xl flex items-center justify-center shadow-glow transition-transform group-hover:scale-105">
                <span className="text-white font-bold text-sm tracking-tight">AI</span>
              </div>
              <div>
                <h1 className="font-semibold text-ink-900 tracking-tight">小团智能平台</h1>
                <p className="text-xs text-ink-400 mt-0.5">AI 赋能 · 智效未来</p>
              </div>
            </Link>
            {/* 门户切换按钮 */}
            {otherPortals.length > 0 && (
              <div className="mt-3 relative">
                <button
                  onClick={() => setShowPortalSwitcher(!showPortalSwitcher)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-gradient-to-r from-brand-50 to-indigo-50 border border-brand-200/60 hover:from-brand-100 hover:to-indigo-100 text-brand-700 transition-all text-xs"
                  title={`当前：${portal?.portal_name || '通用版'}，点击切换`}
                >
                  <ArrowRightLeft className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="flex-1 text-left truncate">
                    {portal?.portal_name || '通用版'}
                  </span>
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showPortalSwitcher ? 'rotate-180' : ''}`} />
                </button>
                {showPortalSwitcher && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowPortalSwitcher(false)} />
                    <div className="absolute z-50 left-0 top-full mt-1 w-52 bg-white rounded-xl border border-ink-200 shadow-lg py-1">
                      <div className="px-3 py-2 border-b border-ink-100">
                        <p className="text-[10px] font-semibold text-ink-400 uppercase tracking-wider">切换工作门户</p>
                      </div>
                      {otherPortals.map(p => (
                        <button
                          key={p.id}
                          onClick={() => handlePortalSwitch(p.id)}
                          className="w-full text-left px-3 py-2.5 hover:bg-brand-50 transition-colors"
                        >
                          <p className="text-sm font-medium text-ink-700">{p.name}</p>
                          <p className="text-[11px] text-ink-400 mt-0.5">{p.desc}</p>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
            className="mt-3 w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-ink-50 border border-ink-200/60 hover:bg-brand-50 hover:border-brand-200 text-ink-500 hover:text-brand-600 transition-all group"
            title="全局搜索（⌘K / Ctrl+K）"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="text-xs">搜索需求 / 命令 / 工具…</span>
            <kbd className="ml-auto px-1.5 py-0.5 text-[10px] bg-white border border-ink-200 rounded font-mono">
              ⌘K
            </kbd>
          </button>
          {renderNav()}
          {renderUser()}
        </div>
      </div>

      {/* Mobile Header */}
      <div className="md:hidden bg-white/95 backdrop-blur-xl border-b border-ink-200/60 p-3 flex items-center justify-between sticky top-0 z-20 shadow-soft">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-700 rounded-lg flex items-center justify-center shadow-soft">
            <span className="text-white font-bold text-xs">AI</span>
          </div>
          <span className="font-semibold text-ink-900">小团智能平台</span>
        </div>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 hover:bg-ink-50 rounded-lg transition-colors"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Drawer */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative w-64 h-full bg-white shadow-lg" style={{ animation: 'slideRight 0.2s ease-out' }}>
            <div className="h-full flex flex-col">
              <div className="px-4 py-4 border-b border-ink-100 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl flex items-center justify-center shadow-glow">
                    <span className="text-white font-bold text-sm">AI</span>
                  </div>
                  <div>
                    <h1 className="font-semibold text-ink-900">小团智能平台</h1>
                    <p className="text-xs text-ink-400">{portal?.portal_name || '通用版'}</p>
                  </div>
                </div>
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="p-1 hover:bg-ink-50 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              {renderNav(() => setSidebarOpen(false))}
              {renderUser(() => setSidebarOpen(false))}
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmLogout}
        onClose={() => setConfirmLogout(false)}
        onConfirm={handleLogout}
        title="确认退出登录？"
        message="退出后需要重新登录才能继续使用平台。"
        confirmLabel="退出"
        icon={LogOut}
      />
      <style dangerouslySetInnerHTML={{ __html: `@keyframes slideRight{from{transform:translateX(-100%)}to{transform:translateX(0)}}` }} />
    </>
  )
}
