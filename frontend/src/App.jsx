import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'
import Sidebar from './components/Sidebar'
import ConfigPage from './pages/ConfigPage'
import AgentsPage from './pages/AgentsPage'
import PlatformEvolutionPage from './pages/PlatformEvolutionPage'
import KnowledgeBasesPage from './pages/KnowledgeBasesPage'
import SkillsPage from './pages/SkillsPage'
import SandboxPage from './pages/SandboxPage'
import MCPServersPage from './pages/MCPServersPage'
import ArtifactsPage from './pages/ArtifactsPage'
import PluginsPage from './pages/PluginsPage'
import ChatPage from './pages/ChatPage'
import WorkflowsPage from './pages/WorkflowsPage'
import WorkflowEditorPage from './pages/WorkflowEditorPage'
import ReqBoardPage from './pages/ReqBoardPage'
import AIWorkspacePage from './pages/AIWorkspacePage'
import LoginPage from './pages/LoginPage'
import AgentExecutePage from './pages/AgentExecutePage'

const API = 'http://localhost:8888'

function ProtectedRoute({ children, isAuthenticated }) {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

export default function App() {
  const [activePath, setActivePath] = useState(window.location.pathname)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [user, setUser] = useState(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = localStorage.getItem('user')
    if (token && userData) {
      const parsedUser = JSON.parse(userData)
      setUser(parsedUser)
      setIsAuthenticated(true)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
    }
  }, [])

  const handleLogin = (userData) => {
    setUser(userData)
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    delete axios.defaults.headers.common['Authorization']
    setUser(null)
    setIsAuthenticated(false)
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={!isAuthenticated ? <LoginPage onLogin={handleLogin} /> : <Navigate to="/agents" replace />} />
        <Route path="*" element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <div className="flex min-h-screen bg-gray-50">
              <Sidebar activePath={activePath} setActivePath={setActivePath} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} user={user} onLogout={handleLogout} />
              <div className={`flex-1 flex flex-col ${sidebarOpen ? 'md:ml-64' : ''}`}>
                <main className="flex-1 overflow-y-auto p-6">
                  <Routes>
                    <Route path="/board" element={<ReqBoardPage />} />
                    <Route path="/workspace" element={<AIWorkspacePage />} />
                    <Route path="/artifacts" element={<ArtifactsPage />} />
                    <Route path="/plugins" element={<PluginsPage />} />
                    <Route path="/chat" element={<ChatPage />} />
                    <Route path="/agents" element={<AgentsPage />} />
                    <Route path="/agents/:id" element={<AgentExecutePage />} />
                    <Route path="/teams" element={<AgentsPage tab="teams" />} />
                    <Route path="/workflows" element={<WorkflowsPage />} />
                    <Route path="/workflows/:id" element={<WorkflowEditorPage />} />
                    <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
                    <Route path="/config" element={<ConfigPage />} />
                    <Route path="/knowledge-bases" element={<KnowledgeBasesPage />} />
                    <Route path="/skills" element={<SkillsPage />} />
                    <Route path="/sandbox" element={<SandboxPage />} />
                    <Route path="/mcp-servers" element={<MCPServersPage />} />
                    <Route path="/evolution" element={<PlatformEvolutionPage />} />
                    <Route path="/" element={<Navigate to="/agents" replace />} />
                  </Routes>
                </main>
              </div>
            </div>
          </ProtectedRoute>
        } />
      </Routes>
    </Router>
  )
}
