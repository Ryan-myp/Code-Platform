import React from 'react'
import './index.css'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import { BookOpen, FileText, Code2, TestTube2, TerminalSquare } from 'lucide-react'
import PRDPage from './pages/PRDPage'
import ReviewPage from './pages/ReviewPage'
import TDPage from './pages/TDPage'
import TestPage from './pages/TestPage'
import CodePage from './pages/CodePage'

function Navbar() {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'PRD 编写', icon: BookOpen },
    { path: '/review', label: 'PRD 审查', icon: FileText },
    { path: '/td', label: '技术方案', icon: Code2 },
    { path: '/test', label: '测试用例', icon: TestTube2 },
    { path: '/code', label: '代码生成', icon: TerminalSquare },
  ]
  
  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50 backdrop-blur-lg bg-white/90">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              智能研发平台
            </span>
          </div>
          <div className="hidden md:flex space-x-1">
            {navItems.map(item => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 shadow-sm'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<PRDPage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/td" element={<TDPage />} />
            <Route path="/test" element={<TestPage />} />
            <Route path="/code" element={<CodePage />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}
