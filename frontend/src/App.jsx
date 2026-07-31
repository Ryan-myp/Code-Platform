import React, { useState } from 'react'
import './index.css'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import ConfigPage from './pages/ConfigPage'
import AgentsPage from './pages/AgentsPage'
import PlatformEvolutionPage from './pages/PlatformEvolutionPage'
import KnowledgeBasesPage from './pages/KnowledgeBasesPage'
import SkillsPage from './pages/SkillsPage'
import MCPServersPage from './pages/MCPServersPage'
import ArtifactsPage from './pages/ArtifactsPage'
import PluginsPage from './pages/PluginsPage'
import ChatPage from './pages/ChatPage'
import WorkflowsPage from './pages/WorkflowsPage'
import ReqBoardPage from './pages/ReqBoardPage'
import AIWorkspacePage from './pages/AIWorkspacePage'

export default function App() {
  const [activePath, setActivePath] = useState(window.location.pathname)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <Router>
      <div className="flex min-h-screen bg-gray-50">
        <Sidebar activePath={activePath} setActivePath={setActivePath} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <div className={`flex-1 flex flex-col ${sidebarOpen ? 'md:ml-64' : ''}`}>
          <main className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/board" element={<ReqBoardPage />} />
              <Route path="/workspace" element={<AIWorkspacePage />} />
              <Route path="/artifacts" element={<ArtifactsPage />} />
              <Route path="/plugins" element={<PluginsPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/agents" element={<AgentsPage />} />
              <Route path="/teams" element={<AgentsPage tab="teams" />} />
              <Route path="/workflows" element={<WorkflowsPage />} />
              <Route path="/config" element={<ConfigPage />} />
              <Route path="/knowledge-bases" element={<KnowledgeBasesPage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/mcp-servers" element={<MCPServersPage />} />
              <Route path="/evolution" element={<PlatformEvolutionPage />} />
              <Route path="/" element={<Navigate to="/board" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  )
}
