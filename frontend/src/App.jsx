import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import axios from 'axios'
import Sidebar from './components/Sidebar'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './lib/toast'
import ConfigPage from './pages/ConfigPage'
import AgentsPage from './pages/AgentsPage'
import PlatformEvolutionPage from './pages/PlatformEvolutionPage'
import KnowledgeBasesPage from './pages/KnowledgeBasesPage'
import SkillsPage from './pages/SkillsPage'
import TeamsPage from './pages/TeamsPage'
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
import ImageFactoryPage from './pages/ImageFactoryPage'
import MusicFactoryPage from './pages/MusicFactoryPage'
import VideoFactoryPage from './pages/VideoFactoryPage'
import ProjectSpacePage from './pages/ProjectSpacePage'

function ProtectedRoute({ children, isAuthenticated }) {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
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
      <ToastProvider>
      <Routes>
        <Route path="/login" element={!isAuthenticated ? <LoginPage onLogin={handleLogin} /> : <Navigate to="/agents" replace />} />
        <Route path="*" element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <div className="flex min-h-screen bg-ink-50">
              <Sidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} user={user} onLogout={handleLogout} />
              <div className="flex-1 flex flex-col md:ml-64 min-w-0">
                <main className="flex-1 overflow-y-auto p-4 md:p-6 animate-page-in">
                  <ErrorBoundary>
                  <Routes>
                    <Route path="/board" element={<ReqBoardPage />} />
                    <Route path="/workspace" element={<AIWorkspacePage />} />
                    <Route path="/projects" element={<ProjectSpacePage />} />
                    <Route path="/projects/:id" element={<ProjectSpacePage />} />
                    <Route path="/artifacts" element={<ArtifactsPage />} />
                    <Route path="/plugins" element={<PluginsPage />} />
                    <Route path="/chat" element={<ChatPage />} />
                    <Route path="/agents" element={<AgentsPage />} />
                    <Route path="/agents/:id" element={<AgentExecutePage />} />
                    <Route path="/teams" element={<TeamsPage />} />
                    <Route path="/workflows" element={<WorkflowsPage />} />
                    <Route path="/workflows/:id" element={<WorkflowEditorPage />} />
                    <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
                    <Route path="/config" element={<ConfigPage />} />
                    <Route path="/knowledge-bases" element={<KnowledgeBasesPage />} />
                    <Route path="/skills" element={<SkillsPage />} />
                    <Route path="/sandbox" element={<SandboxPage />} />
                    <Route path="/mcp-servers" element={<MCPServersPage />} />
                    <Route path="/evolution" element={<PlatformEvolutionPage />} />
                    <Route path="/image-factory" element={<ImageFactoryPage />} />
                    <Route path="/video-factory" element={<VideoFactoryPage />} />
                    <Route path="/music-factory" element={<MusicFactoryPage />} />
                    <Route path="/" element={<Navigate to="/agents" replace />} />
                  </Routes>
                  </ErrorBoundary>
                </main>
              </div>
            </div>
          </ProtectedRoute>
        } />
      </Routes>
      </ToastProvider>
    </Router>
  )
}
