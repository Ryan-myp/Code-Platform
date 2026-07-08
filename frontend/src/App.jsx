import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import PRDPage from './pages/PRDPage'
import ReviewPage from './pages/ReviewPage'
import TDPage from './pages/TDPage'
import TestPage from './pages/TestPage'
import CodePage from './pages/CodePage'

function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="text-xl font-bold text-blue-600">智能研发平台</Link>
            </div>
            <div className="flex space-x-4">
              <Link to="/" className="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600">PRD</Link>
              <Link to="/review" className="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600">审查</Link>
              <Link to="/td" className="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600">方案</Link>
              <Link to="/test" className="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600">测试</Link>
              <Link to="/code" className="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600">代码</Link>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<PRDPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/td" element={<TDPage />} />
          <Route path="/test" element={<TestPage />} />
          <Route path="/code" element={<CodePage />} />
        </Routes>
      </Layout>
    </Router>
  )
}
