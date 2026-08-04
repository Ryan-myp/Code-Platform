import React, { useState } from 'react'
import {
  Code2, Bot, Layers, Sparkles, Settings, Database, Wrench, Server,
  ListTodo, FileText, FolderKanban, Puzzle, MessageSquare, Brain,
  ChevronDown, ChevronRight, Menu, X, Play, Image as ImageIcon, Film, Music,
  Wand2, LogOut, Users, Zap, Home, CheckCircle2, Bell,
  Shield, GitBranch, PenTool, Languages, BarChart3, FlaskConical,
  Presentation, Table2, TrendingUp, HelpCircle, History as HistoryIcon, Crown, Lock, Search,
  Send, Smartphone, Gamepad2, Mic2, Sticker, Moon, Sun, UserCircle,
  GalleryVerticalEnd, Store
} from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { ConfirmDialog } from './ui'
import { useToast } from '../lib/toast'
import useQuota from '../hooks/useQuota'
import useAccess from '../hooks/useAccess'
import useTheme from '../hooks/useTheme'
import ModelSwitcher from './ModelSwitcher'

export default function Sidebar({ sidebarOpen, setSidebarOpen, user, onLogout }) {
  const location = useLocation()
  const activePath = location.pathname
  const toast = useToast()
  const { quota } = useQuota()
  const { getPageStatusById } = useAccess()
  const { theme, toggleTheme } = useTheme()
  const [confirmLogout, setConfirmLogout] = useState(false)

  const navItems = [
    { key: 'home', label: '工作台', icon: Home, color: 'from-blue-500 to-indigo-600',
      items: [
        { path: '/home', label: '首页', icon: Home },
        { path: '/tasks', label: '任务中心', icon: CheckCircle2 },
        { path: '/records', label: '记录中心', icon: HistoryIcon },
        { path: '/notifications', label: '通知中心', icon: Bell },
        { path: '/membership', label: '会员中心', icon: Crown },
      ] },
    { key: 'rdm', label: '研发管理', icon: Code2, color: 'from-brand-500 to-brand-600',
      items: [
        { path: '/board', label: '需求看板', icon: ListTodo, group: '需求与项目' },
        { path: '/workspace', label: 'AI 工作台', icon: Sparkles, group: '需求与项目' },
        { path: '/projects', label: '项目空间', icon: FolderKanban, group: '需求与项目' },
        { path: '/artifacts', label: '成果仓库', icon: FileText, group: '需求与项目' },
        { path: '/sandbox', label: '沙箱运行', icon: Play, pageId: 'sandbox', group: '代码研发' },
        { path: '/pipelines', label: 'CI/CD 流水线', icon: GitBranch, group: '部署运维' },
      ] },
    { key: 'agent', label: '智能体管理', icon: Bot, color: 'from-emerald-500 to-teal-600',
      items: [
        { path: '/agents', label: 'Agent 列表', icon: Bot, pageId: 'agents' },
        { path: '/teams', label: 'Team 管理', icon: Users },
        { path: '/workflows', label: 'Workflow 管理', icon: Layers, pageId: 'workflows' },
        { path: '/knowledge-bases', label: '知识库', icon: Database },
        { path: '/skills', label: 'Skills', icon: Wrench },
        { path: '/mcp-servers', label: 'MCP Servers', icon: Server },
      ] },
    { key: 'factory', label: '创作工厂', icon: Wand2, color: 'from-accent-500 to-blue-600',
      items: [
        { path: '/image-factory', label: '图片工厂', icon: ImageIcon, pageId: 'image-factory', group: '内容生成' },
        { path: '/video-factory', label: '视频工厂', icon: Film, pageId: 'video-factory', group: '内容生成' },
        { path: '/music-factory', label: '音乐工厂', icon: Music, pageId: 'music-factory', group: '内容生成' },
        { path: '/copywriting', label: '文案工厂', icon: PenTool, pageId: 'copywriting', group: '内容生成' },
        { path: '/translation', label: '翻译中心', icon: Languages, pageId: 'translation', group: '内容生成' },
        { path: '/ppt-factory', label: 'PPT 工厂', icon: Presentation, pageId: 'ppt-factory', group: '内容生成' },
        { path: '/meme', label: '表情包工坊', icon: Sticker, pageId: 'meme', group: '内容生成' },
        { path: '/digital-human', label: 'AI数字人', icon: UserCircle, pageId: 'digital-human', group: '智能工坊' },
        { path: '/pdf-tools', label: 'PDF工具集', icon: FileText, pageId: 'pdf-tools', group: '效率工具' },
        { path: '/games', label: '小游戏工坊', icon: Gamepad2, pageId: 'games', group: '智能工坊' },
        { path: '/miniapp', label: '小程序工坊', icon: Smartphone, pageId: 'miniapp', group: '智能工坊' },
        { path: '/voice', label: '配音工坊', icon: Mic2, pageId: 'voice', group: '智能工坊' },
        { path: '/publish', label: '发布中心', icon: Send, pageId: 'publish', group: '发布社区' },
        { path: '/growth', label: '增长工坊', icon: TrendingUp, pageId: 'growth', group: '发布社区' },
        { path: '/gallery', label: '作品广场', icon: GalleryVerticalEnd, pageId: 'gallery', group: '发布社区' },
        { path: '/templates', label: '模板市场', icon: Store, pageId: 'templates', group: '发布社区' },
      ] },
    { key: 'office', label: '效率工具', icon: Wrench, color: 'from-orange-500 to-red-600',
      items: [
        { path: '/tool-hub', label: '全部工具', icon: Wrench },
        { path: '/excel', label: 'Excel 助手', icon: Table2, pageId: 'excel' },
        { path: '/stock', label: '股票分析', icon: TrendingUp, pageId: 'stock' },
        { path: '/dashboard', label: '数据看板', icon: BarChart3 },
        { path: '/ab-testing', label: 'AB 测试', icon: FlaskConical },
      ] },
    { key: 'support', label: '协作与支持', icon: MessageSquare, color: 'from-violet-500 to-purple-600',
      items: [
        { path: '/chat', label: '智能协作', icon: MessageSquare, pageId: 'chat' },
        { path: '/help', label: '使用帮助', icon: HelpCircle },
        { path: '/plugins', label: '插件市场', icon: Puzzle, pageId: 'plugins' },
        { path: '/evolution', label: '平台自进化', icon: Brain },
      ] },
    { key: 'system', label: '系统配置', icon: Settings, color: 'from-amber-500 to-orange-600',
      items: [
        { path: '/config', label: '模型配置', icon: Settings },
        ...(user?.role === 'admin'
          ? [{ path: '/admin', label: '管理后台', icon: Shield }]
          : []),
      ] },
  ]

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

  const renderNav = (onNavigate) => (
    <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
      {navItems.map((menu) => {
        // 按可见性过滤入口（admin 设置 hidden / 仅限他人时不在侧边栏展示）
        const visibleItems = menu.items.filter((i) => !i.pageId || getPageStatusById(i.pageId).visible)
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
                <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${menu.color} flex items-center justify-center shadow-soft`}>
                  <menu.icon className="w-3.5 h-3.5 text-white" />
                </div>
                <span>{menu.label}</span>
              </div>
              {expandedMenus[menu.key] ? <ChevronDown className="w-3.5 h-3.5 text-ink-400" /> : <ChevronRight className="w-3.5 h-3.5 text-ink-400" />}
            </button>
            {expandedMenus[menu.key] && (
              <div className="ml-4 mt-0.5 space-y-0.5 border-l border-ink-200/60 pl-3 py-0.5">
                {visibleItems.map((item, idx) => {
                  const showGroup = item.group && item.group !== visibleItems[idx - 1]?.group
                  const pageStatus = item.pageId ? getPageStatusById(item.pageId) : null
                  const locked = !!pageStatus?.locked
                  const active = activePath === item.path || (item.path !== '/agents' && activePath.startsWith(item.path))
                  return (
                    <React.Fragment key={item.path}>
                      {showGroup && (
                        <div className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-400/70">
                          {item.group}
                        </div>
                      )}
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
                        <item.icon className={`w-3.5 h-3.5 ${locked ? 'text-amber-400' : active ? 'text-brand-600' : 'text-ink-400'}`} />
                        <span>{item.label}</span>
                        {locked ? (
                          <Lock className="w-3 h-3 text-amber-500 ml-auto" />
                        ) : (
                          active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-500" />
                        )}
                      </Link>
                    </React.Fragment>
                  )
                })}
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
          <Link to="/profile" onClick={onNavigate} className="flex items-center gap-2.5 min-w-0 group">
            <div className="w-9 h-9 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl flex items-center justify-center shadow-soft flex-shrink-0">
              <span className="text-white text-sm font-semibold">{user.username?.[0]?.toUpperCase()}</span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink-800 truncate group-hover:text-brand-600 transition-colors">{user.nickname || user.username}</p>
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
          <span className={`text-xs font-semibold ${quota.remaining_today >= 9999 ? 'text-amber-600' : quota.remaining_today <= 5 ? 'text-red-500' : 'text-brand-600'}`}>
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
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-500 text-white">¥19.9 起</span>
        </Link>
      )}
      <div className="flex items-center justify-center gap-1 text-xs text-ink-400 pt-2">
        <Zap className="w-3 h-3 text-brand-400" />
        <span>Powered by Agno</span>
        <span className="text-ink-300">·</span>
        <span>v9.0</span>
        <span className="text-ink-300">·</span>
        <button onClick={toggleTheme} className="flex items-center gap-1 hover:text-brand-500 transition-colors" title="切换深色 / 浅色模式">
          {theme === 'dark' ? <Sun className="w-3 h-3" /> : <Moon className="w-3 h-3" />}
          <span>{theme === 'dark' ? '深色' : '浅色'}</span>
        </button>
      </div>
    </div>
  )

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
          </div>
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
            className="mt-3 w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-ink-50 border border-ink-200/60 hover:bg-brand-50 hover:border-brand-200 text-ink-500 hover:text-brand-600 transition-all group"
            title="全局搜索（⌘K / Ctrl+K）"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="text-xs">搜索需求 / 命令 / 工具…</span>
            <kbd className="ml-auto px-1.5 py-0.5 text-[10px] bg-white border border-ink-200 rounded font-mono">⌘K</kbd>
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
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 hover:bg-ink-50 rounded-lg transition-colors">
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Drawer */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="relative w-64 h-full bg-white animate-[slideRight_0.2s_ease-out] shadow-lg">
            <div className="h-full flex flex-col">
              <div className="px-4 py-4 border-b border-ink-100 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl flex items-center justify-center shadow-glow">
                    <span className="text-white font-bold text-sm">AI</span>
                  </div>
                  <h1 className="font-semibold text-ink-900">小团智能平台</h1>
                </div>
                <button onClick={() => setSidebarOpen(false)} className="p-1 hover:bg-ink-50 rounded-lg">
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
      <style>{`@keyframes slideRight{from{transform:translateX(-100%)}to{transform:translateX(0)}}`}</style>
    </>
  )
}
