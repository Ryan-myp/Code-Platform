import React, { useState } from 'react'
import './index.css'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import { BookOpen, FileText, Code2, TestTube2, TerminalSquare, Settings, Bot, Users, Layers, ChevronDown, ChevronRight, Menu, X, Brain } from 'lucide-react'
import PRDPage from './pages/PRDPage'
import ReviewPage from './pages/ReviewPage'
import TDPage from './pages/TDPage'
import TestPage from './pages/TestPage'
import CodePage from './pages/CodePage'
import ConfigPage from './pages/ConfigPage'
import AgentsPage from './pages/AgentsPage'
import PlatformEvolutionPage from './pages/PlatformEvolutionPage'
import ResourcesPage from './pages/ResourcesPage'

function AppContent({ setActivePath }) {
  const location = useLocation()
  
  React.useEffect(() => {
    setActivePath(location.pathname)
  }, [location.pathname])

  return (
    <Routes>
      <Route path="/" element={<PRDPage />} />
      <Route path="/review" element={<ReviewPage />} />
      <Route path="/td" element={<TDPage />} />
      <Route path="/test" element={<TestPage />} />
      <Route path="/code" element={<CodePage />} />
      <Route path="/agents" element={<AgentsPage />} />
      <Route path="/teams" element={<AgentsPage tab="teams" />} />
      <Route path="/workflows" element={<AgentsPage tab="workflows" />} />
      <Route path="/config" element={<ConfigPage />} />
      <Route path="/resources" element={<ResourcesPage />} />
      <Route path="/evolution" element={<PlatformEvolutionPage />} />
    </Routes>
  )
}

export default function App() {
  const [activePath, setActivePath] = useState('/')
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <Router>
      <div className="flex min-h-screen bg-gray-50">
        {/* Sidebar */}
        <div className={`${sidebarOpen ? 'block' : 'hidden'} md:block fixed left-0 top-0 bottom-0 z-30 w-64 bg-white border-r border-gray-200`}>
          <Sidebar activePath={activePath} setActivePath={setActivePath} />
        </div>

        {/* Main Content */}
        <div className={`flex-1 flex flex-col ${sidebarOpen ? 'md:ml-64' : ''}`}>
          {/* Top Bar (Mobile) */}
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

          {/* Mobile Sidebar Overlay */}
          {sidebarOpen && (
            <div className="md:hidden fixed inset-0 z-40">
              <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
              <div className="relative w-64 h-full">
                <Sidebar activePath={activePath} setActivePath={(path) => { setActivePath(path); setSidebarOpen(false) }} />
              </div>
            </div>
          )}

          {/* Content Area */}
          <main className="flex-1 overflow-y-auto p-6">
            <AppContent setActivePath={setActivePath} />
          </main>
        </div>
      </div>
    </Router>
  )
}

function Sidebar({ activePath, setActivePath }) {
  const [expandedMenus, setExpandedMenus] = useState({
    rdm: true,
    agent: false,
    system: false,
    evolution: false,
  })

  const toggleMenu = (menuKey) => {
    setExpandedMenus(prev => ({ ...prev, [menuKey]: !prev[menuKey] }))
  }

  const navItems = [
    {
      key: 'rdm',
      label: '研发管理',
      icon: Code2,
      items: [
        { path: '/', label: 'PRD 编写', icon: BookOpen },
        { path: '/review', label: 'PRD 审查', icon: FileText },
        { path: '/td', label: '技术方案', icon: Code2 },
        { path: '/test', label: '测试用例', icon: TestTube2 },
        { path: '/code', label: '代码生成', icon: TerminalSquare },
      ]
    },
    {
      key: 'agent',
      label: '智能体管理',
      icon: Bot,
      items: [
        { path: '/agents', label: 'Agent 列表', icon: Bot },
        { path: '/teams', label: 'Team 管理', icon: Users },
        { path: '/workflows', label: 'Workflow 管理', icon: Layers },
      ]
    },
    {
      key: 'system',
      label: '系统配置',
      icon: Settings,
      items: [
        { path: '/config', label: '模型配置', icon: Settings },
      ]
    },
    {
      key: 'evolution',
      label: '平台自进化',
      icon: Brain,
      items: [
        { path: '/evolution', label: '自进化中心', icon: Brain },
      ]
    }
  ]

  return (
    <div className="h-full flex flex-col">
      {/* Logo */}
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

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map(menu => (
          <div key={menu.key}>
            <button
              onClick={() => toggleMenu(menu.key)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center space-x-2">
                <menu.icon className="w-4 h-4 text-gray-600" />
                <span className="text-sm font-medium text-gray-700">{menu.label}</span>
              </div>
              {expandedMenus[menu.key] ? (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-400" />
              )}
            </button>

            {expandedMenus[menu.key] && (
              <div className="ml-4 mt-1 space-y-0.5">
                {menu.items.map(item => {
                  const isActive = activePath === item.path
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={() => setActivePath(item.path)}
                      className={`flex items-center px-3 py-2 rounded-lg text-sm transition-all duration-200 ${
                        isActive
                          ? 'bg-purple-100 text-purple-700 font-medium'
                          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                      }`}
                    >
                      <item.icon className={`w-4 h-4 mr-2 ${isActive ? 'text-purple-600' : 'text-gray-400'}`} />
                      {item.label}
                    </Link>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 bg-gray-50">
        <div className="text-xs text-gray-500 text-center">
          <p>Powered by Agno</p>
          <p>v4.0.0</p>
        </div>
      </div>
    </div>
  )
}
