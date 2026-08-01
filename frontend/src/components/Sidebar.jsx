import React from 'react'
import {
  BookOpen, FileText, Code2, TestTube2, TerminalSquare, Settings, Bot, Users, Layers,
  ChevronDown, ChevronRight, Menu, X, Brain, Database, Wrench, Server, ListTodo,
  Puzzle, MessageSquare, Sparkles, Play
} from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Sidebar({ activePath, setActivePath, sidebarOpen, setSidebarOpen, user, onLogout }) {
  const navItems = [
    { key: 'rdm', label: '研发管理', icon: Code2,
      items: [
        { path: '/board', label: '需求看板', icon: ListTodo },
        { path: '/workspace', label: 'AI 工作台', icon: Sparkles },
        { path: '/artifacts', label: '成果仓库', icon: FileText },
      ] },
    { key: 'agent', label: '智能体管理', icon: Bot,
      items: [
        { path: '/agents', label: 'Agent 列表', icon: Bot },
        { path: '/teams', label: 'Team 管理', icon: Users },
        { path: '/workflows', label: 'Workflow 管理', icon: Layers },
        { path: '/sandbox', label: '沙箱运行', icon: Play },
      ] },
    { key: 'system', label: '系统配置', icon: Settings,
      items: [
        { path: '/config', label: '模型配置', icon: Settings },
        { path: '/knowledge-bases', label: '知识库', icon: Database },
        { path: '/skills', label: 'Skills', icon: Wrench },
        { path: '/mcp-servers', label: 'MCP Servers', icon: Server },
      ] },
    { key: 'plugins', label: '插件市场', icon: Puzzle,
      items: [{ path: '/plugins', label: '插件列表', icon: Puzzle }] },
    { key: 'chat', label: '智能协作', icon: MessageSquare,
      items: [{ path: '/chat', label: '任务对话', icon: MessageSquare }] },
    { key: 'evolution', label: '平台自进化', icon: Brain,
      items: [{ path: '/evolution', label: '自进化中心', icon: Brain }] },
  ]

  const initExpanded = {}
  navItems.forEach(m => { initExpanded[m.key] = m.items.some(i => i.path === window.location.pathname) })
  const [expandedMenus, setExpandedMenus] = React.useState(initExpanded)

  const toggleMenu = (key) => {
    setExpandedMenus(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <>
      {/* Desktop Sidebar */}
      <div className={`${sidebarOpen ? '' : 'hidden'} md:block fixed left-0 top-0 bottom-0 z-30 w-64 bg-white border-r border-gray-200`}>
        <div className="h-full flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-sm">AI</span>
              </div>
              <div>
                <h1 className="font-bold text-gray-900">智能研发平台</h1>
                <p className="text-xs text-gray-500">Agno Agent Powered</p>
              </div>
            </div>
          </div>
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {navItems.map(menu => (
              <div key={menu.key}>
                <button onClick={() => toggleMenu(menu.key)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors">
                  <div className="flex items-center space-x-2">
                    <menu.icon className="w-4 h-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-700">{menu.label}</span>
                  </div>
                  {expandedMenus[menu.key] ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                </button>
                {expandedMenus[menu.key] && (
                  <div className="ml-4 mt-1 space-y-0.5">
                    {menu.items.map(item => (
                      <Link key={item.path} to={item.path}
                        onClick={() => { setActivePath(item.path); if (window.innerWidth < 768) setSidebarOpen(false); }}
                        className={`flex items-center px-3 py-2 rounded-lg text-sm transition-all duration-200 ${activePath === item.path ? 'bg-purple-100 text-purple-700 font-medium' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'}`}>
                        <item.icon className={`w-4 h-4 mr-2 ${activePath === item.path ? 'text-purple-600' : 'text-gray-400'}`} />
                        {item.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </nav>
          <div className="p-4 border-t border-gray-200 bg-gray-50">
            {user && (
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                    <span className="text-purple-600 text-xs font-bold">{user.username?.[0]?.toUpperCase()}</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{user.username}</p>
                    <p className="text-xs text-gray-500 capitalize">{user.role}</p>
                  </div>
                </div>
                <button onClick={onLogout} className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors" title="退出登录">
                  <span className="text-gray-500 text-xs">退出</span>
                </button>
              </div>
            )}
            <div className="text-xs text-gray-500 text-center">
              <p>Powered by Agno</p>
              <p>v7.0</p>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Header */}
      <div className="md:hidden bg-white border-b border-gray-200 p-4 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-xs">AI</span>
          </div>
          <span className="font-bold text-gray-900">智能研发平台</span>
        </div>
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 hover:bg-gray-100 rounded-lg">
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
          <div className="relative w-64 h-full">
            <div className="h-full flex flex-col">
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                    <span className="text-white font-bold text-sm">AI</span>
                  </div>
                  <div><h1 className="font-bold text-gray-900">智能研发平台</h1></div>
                </div>
              </div>
              <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                {navItems.map(menu => (
                  <div key={menu.key}>
                    <button onClick={() => toggleMenu(menu.key)} className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-100">
                      <div className="flex items-center space-x-2"><menu.icon className="w-4 h-4 text-gray-600" /><span className="text-sm font-medium text-gray-700">{menu.label}</span></div>
                      {expandedMenus[menu.key] ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                    </button>
                    {expandedMenus[menu.key] && (
                      <div className="ml-4 mt-1 space-y-0.5">
                        {menu.items.map(item => (
                          <Link key={item.path} to={item.path} onClick={() => { setActivePath(item.path); setSidebarOpen(false); }}
                            className={`flex items-center px-3 py-2 rounded-lg text-sm ${activePath === item.path ? 'bg-purple-100 text-purple-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}`}>
                            <item.icon className="w-4 h-4 mr-2" />{item.label}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </nav>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
