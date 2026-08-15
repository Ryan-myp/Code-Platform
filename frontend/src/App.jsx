import React, { useState, useEffect, useLayoutEffect, lazy, Suspense } from 'react'
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import axios from 'axios'
import Sidebar from './components/Sidebar'
import ErrorBoundary from './components/ErrorBoundary'
import CommandPalette from './components/CommandPalette'
import OnboardingTour from './components/OnboardingTour'
import FloatingAssistant from './components/FloatingAssistant'
import MobileBottomNav from './components/MobileBottomNav'
import BackToTop from './components/BackToTop'
import AccessGuard from './components/AccessGuard'
import { trackVisit } from './hooks/useRecentTools'
import { pageTitleFor } from './lib/pageTitle'
import { ToastProvider, useToast } from './lib/toast'
import { useI18n, LanguageSwitcher } from './i18n/index.jsx'

// 页面级懒加载：首屏仅加载当前页面，其余按需分块（首包从 ~1.8MB 降至 ~300KB）
const ConfigPage = lazy(() => import('./pages/ConfigPage'))
const AgentsPage = lazy(() => import('./pages/AgentsPage'))
const PlatformEvolutionPage = lazy(() => import('./pages/PlatformEvolutionPage'))
const KnowledgeBasesPage = lazy(() => import('./pages/KnowledgeBasesPage'))
const SkillsPage = lazy(() => import('./pages/SkillsPage'))
const TeamsPage = lazy(() => import('./pages/TeamsPage'))
const SandboxPage = lazy(() => import('./pages/SandboxPage'))
const MCPServersPage = lazy(() => import('./pages/MCPServersPage'))
const ArtifactsPage = lazy(() => import('./pages/ArtifactsPage'))
const PluginsPage = lazy(() => import('./pages/PluginsPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const WorkflowsPage = lazy(() => import('./pages/WorkflowsPage'))
const WorkflowEditorPage = lazy(() => import('./pages/WorkflowEditorPage'))
const ReqBoardPage = lazy(() => import('./pages/ReqBoardPage'))
const AIWorkspacePage = lazy(() => import('./pages/AIWorkspacePage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'))
const AgentExecutePage = lazy(() => import('./pages/AgentExecutePage'))
const ImageFactoryPage = lazy(() => import('./pages/ImageFactoryPage'))
const MusicFactoryPage = lazy(() => import('./pages/MusicFactoryPage'))
const VideoFactoryPage = lazy(() => import('./pages/VideoFactoryPage'))
const ProjectSpacePage = lazy(() => import('./pages/ProjectSpacePage'))
// v9.0 新页面
const HomePage = lazy(() => import('./pages/HomePage'))
const TasksPage = lazy(() => import('./pages/TasksPage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const PipelinesPage = lazy(() => import('./pages/PipelinesPage'))
const CopywritingPage = lazy(() => import('./pages/CopywritingPage'))
const TranslationPage = lazy(() => import('./pages/TranslationPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ABTestingPage = lazy(() => import('./pages/ABTestingPage'))
const PPTFactoryPage = lazy(() => import('./pages/PPTFactoryPage'))
const ExcelPage = lazy(() => import('./pages/ExcelPage'))
const ToolHubPage = lazy(() => import('./pages/ToolHubPage'))
const ToolRunPage = lazy(() => import('./pages/ToolRunPage'))
const StockAnalysisPage = lazy(() => import('./pages/StockAnalysisPage'))
// v9.1 商业版
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const ShareViewPage = lazy(() => import('./pages/ShareViewPage'))
const HelpPage = lazy(() => import('./pages/HelpPage'))
const RecordsPage = lazy(() => import('./pages/RecordsPage'))
// v9.2 商业版
const MembershipPage = lazy(() => import('./pages/MembershipPage'))
// v9.3 内容发布 + 小程序开发
const PublishingPage = lazy(() => import('./pages/PublishingPage'))
const GrowthPage = lazy(() => import('./pages/GrowthPage'))
const SEOAnalyzerPage = lazy(() => import('./pages/SEOAnalyzerPage'))
const MiniAppPage = lazy(() => import('./pages/MiniAppPage'))
const MiniAppPreviewPage = lazy(() => import('./pages/MiniAppPreviewPage'))
const GameFactoryPage = lazy(() => import('./pages/GameFactoryPage'))
const ShortDramaPage = lazy(() => import('./pages/ShortDramaPage'))
const VoicePage = lazy(() => import('./pages/VoicePage'))
const MemePage = lazy(() => import('./pages/MemePage'))
const DigitalHumanPage = lazy(() => import('./pages/DigitalHumanPage'))
const VoiceChatPage = lazy(() => import('./pages/VoiceChatPage'))
const VideoAnalyzerPage = lazy(() => import('./pages/VideoAnalyzerPage'))
const MindMapPage = lazy(() => import('./pages/MindMapPage'))
const ForecastPage = lazy(() => import('./pages/ForecastPage'))
const DocQAPage = lazy(() => import('./pages/DocQAPage'))
const PDFToolPage = lazy(() => import('./pages/PDFToolPage'))
// v10.0 社区与变现
const GalleryPage = lazy(() => import('./pages/GalleryPage'))
const TemplateMarketPage = lazy(() => import('./pages/TemplateMarketPage'))
// v10.1 新功能页面
const WebSearchPage = lazy(() => import('./pages/WebSearchPage'))
const BatchProcessPage = lazy(() => import('./pages/BatchProcessPage'))
const ApiDocsPage = lazy(() => import('./pages/ApiDocsPage'))
const CodeSandboxPage = lazy(() => import('./pages/CodeSandboxPage'))
const DataAnalyzerPage = lazy(() => import('./pages/DataAnalyzerPage'))
const UsageAnalyticsPage = lazy(() => import('./pages/UsageAnalyticsPage'))
const UsageDetailPage = lazy(() => import('./pages/UsageDetailPage'))
const InviteHistoryPage = lazy(() => import('./pages/InviteHistoryPage'))
const CreatorCenterPage = lazy(() => import('./pages/CreatorCenterPage'))
const AuditLogPage = lazy(() => import('./pages/AuditLogPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const FeedbackPage = lazy(() => import('./pages/FeedbackPage'))
const ShortcutsPage = lazy(() => import('./pages/ShortcutsPage'))
const DownloadsPage = lazy(() => import('./pages/DownloadsPage'))
const SchedulerPage = lazy(() => import('./pages/SchedulerPage'))
// 全量修复 v1：内容策略 / 竞品监控 / 收藏中心
const ContentStrategyPage = lazy(() => import('./pages/ContentStrategyPage'))
const CompetitorMonitorPage = lazy(() => import('./pages/CompetitorMonitorPage'))
const FavoritesPage = lazy(() => import('./pages/FavoritesPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

// 页面级加载骨架（懒加载期间展示）
function PageFallback() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
        <span className="text-sm text-gray-400">页面加载中…</span>
      </div>
    </div>
  )
}

function ProtectedRoute({ children, isAuthenticated }) {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

// v17-F：路由级页面标题映射见 lib/pageTitle.js（TOOL_META + 通用页 + 动态前缀）

// v16 路由访问追踪：记录「最近使用」工具（供首页快捷区一键直达）
// v17-F：同时跟随路由更新浏览器标签页标题（67 个页面切换时标签名始终正确）
function RouteTracker() {
  const location = useLocation()
  useEffect(() => {
    trackVisit(location.pathname)
    document.title = pageTitleFor(location.pathname)
  }, [location.pathname])
  return null
}

// 分享页 SEO 落地：后端 /share/{code} 返回的 HTML 通过 meta refresh + JS 跳转到 /?share={code}，
// 此处解析 query 并跳转到 SPA 分享页（useLayoutEffect 避免闪现登录/主页）
function ShareRedirect() {
  const location = useLocation()
  const navigate = useNavigate()
  useLayoutEffect(() => {
    const code = new URLSearchParams(location.search).get('share')
    if (code) {
      navigate(`/share/${code}`, { replace: true })
    }
  }, [location.search, navigate])
  return null
}

// 全局 402 额度耗尽引导：api 拦截器派发 quota-exhausted 事件（携带后端分层文案：
// free 促升级 / pro 提示明日恢复）后统一提示，避免各页重复处理；页面级 toast 由各页自理
function QuotaExhaustedNotifier() {
  const toast = useToast()
  useEffect(() => {
    const notify = (e) => {
      toast.error(e?.detail?.message || '今日生成额度已用完，可在会员中心查看套餐升级', 6000)
    }
    window.addEventListener('quota-exhausted', notify)
    return () => window.removeEventListener('quota-exhausted', notify)
  }, [toast])
  return null
}

export default function App() {
  const { t, lang } = useI18n()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  // 同步初始化认证态（避免首帧未登录被 ProtectedRoute 踢到 /login 再跳回 /home）
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('user') || 'null')
    } catch {
      return null
    }
  })
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem('token') && !!user
  )
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)
  // 门户配置（登录后从后端加载，决定侧边栏导航结构）
  const [portal, setPortal] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('portal') || 'null')
    } catch { return null }
  })

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token && user) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      // 加载门户配置
      axios.get('/api/portal/current').then(res => {
        const p = res.data
        setPortal(p)
        localStorage.setItem('portal', JSON.stringify(p))
      }).catch(() => {})
    }
  }, [user])

  // 监听命令面板打开事件
  useEffect(() => {
    const handleOpen = () => setCommandPaletteOpen(true)
    window.addEventListener('open-command-palette', handleOpen)
    return () => window.removeEventListener('open-command-palette', handleOpen)
  }, [])

  const handleLogin = (userData) => {
    setUser(userData)
    setIsAuthenticated(true)
  }

  const handleUserUpdate = (userData) => {
    setUser(userData)
    localStorage.setItem('user', JSON.stringify(userData))
    // 用户资料更新时重新加载门户配置
    axios.get('/api/portal/current').then(res => {
      const p = res.data
      setPortal(p)
      localStorage.setItem('portal', JSON.stringify(p))
    }).catch(() => {})
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    delete axios.defaults.headers.common['Authorization']
    setUser(null)
    setIsAuthenticated(false)
  }

  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ShareRedirect />
      <RouteTracker />
      <ToastProvider>
        <QuotaExhaustedNotifier />
        <CommandPalette isOpen={commandPaletteOpen} onClose={() => setCommandPaletteOpen(false)} />
        <OnboardingTour isAuthenticated={isAuthenticated} />
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route
              path="/login"
              element={
                !isAuthenticated ? (
                  <LoginPage onLogin={handleLogin} />
                ) : (
                  <Navigate to="/home" replace />
                )
              }
            />
            <Route
              path="/forgot-password"
              element={
                !isAuthenticated ? (
                  <ForgotPasswordPage />
                ) : (
                  <Navigate to="/home" replace />
                )
              }
            />
            {/* 公开分享查看页（无需登录） */}
            <Route path="/share/:shareCode" element={<ShareViewPage />} />
            <Route
              path="*"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <div className="flex min-h-screen bg-ink-50">
                    <Sidebar
                      sidebarOpen={sidebarOpen}
                      setSidebarOpen={setSidebarOpen}
                      user={user}
                      portal={portal}
                      onLogout={handleLogout}
                      onPortalSwitch={(p) => { setPortal(p); localStorage.setItem('portal', JSON.stringify(p)); }}
                    />
                    <div className="flex-1 flex flex-col md:ml-64 min-w-0">
                      <main className="flex-1 overflow-y-auto p-4 md:p-6 pb-20 md:pb-6 animate-page-in">
                        <ErrorBoundary>
                          <Routes>
                            <Route path="/home" element={<HomePage />} />
                            <Route path="/tasks" element={<TasksPage />} />
                            <Route path="/notifications" element={<NotificationsPage />} />
                            <Route path="/board" element={<ReqBoardPage />} />
                            <Route path="/workspace" element={<AIWorkspacePage />} />
                            {/* 演示别名：/workbench → 工作台 */}
                            <Route path="/workbench" element={<Navigate to="/workspace" replace />} />
                            <Route path="/projects" element={<ProjectSpacePage />} />
                            <Route path="/projects/:id" element={<ProjectSpacePage />} />
                            <Route path="/artifacts" element={<ArtifactsPage />} />
                            <Route
                              path="/plugins"
                              element={
                                <AccessGuard path="/plugins">
                                  <PluginsPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/chat"
                              element={
                                <AccessGuard path="/chat">
                                  <ChatPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/agents"
                              element={
                                <AccessGuard path="/agents">
                                  <AgentsPage />
                                </AccessGuard>
                              }
                            />
                            <Route path="/agents/:id" element={<AgentExecutePage />} />
                            <Route path="/teams" element={<TeamsPage />} />
                            <Route
                              path="/workflows"
                              element={
                                <AccessGuard path="/workflows">
                                  <WorkflowsPage />
                                </AccessGuard>
                              }
                            />
                            <Route path="/workflows/:id" element={<WorkflowEditorPage />} />
                            <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
                            <Route path="/config" element={<ConfigPage />} />
                            <Route path="/knowledge-bases" element={<KnowledgeBasesPage />} />
                            <Route path="/skills" element={<SkillsPage />} />
                            <Route
                              path="/sandbox"
                              element={
                                <AccessGuard path="/sandbox">
                                  <SandboxPage />
                                </AccessGuard>
                              }
                            />
                            <Route path="/mcp-servers" element={<MCPServersPage />} />
                            <Route path="/evolution" element={<PlatformEvolutionPage />} />
                            <Route
                              path="/image-factory"
                              element={
                                <AccessGuard path="/image-factory">
                                  <ImageFactoryPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/video-factory"
                              element={
                                <AccessGuard path="/video-factory">
                                  <VideoFactoryPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/music-factory"
                              element={
                                <AccessGuard path="/music-factory">
                                  <MusicFactoryPage />
                                </AccessGuard>
                              }
                            />
                            {/* v9.0 Phase 2: 研发增强（代码生成/代码审查已并入 AI 工作台） */}
                            <Route
                              path="/code-gen"
                              element={<Navigate to="/workspace?tab=code" replace />}
                            />
                            <Route
                              path="/code-review"
                              element={<Navigate to="/workspace?tab=review_code" replace />}
                            />
                            <Route path="/pipelines" element={<PipelinesPage />} />
                            {/* v9.0 Phase 3: 内容创作 */}
                            <Route
                              path="/copywriting"
                              element={
                                <AccessGuard path="/copywriting">
                                  <CopywritingPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/translation"
                              element={
                                <AccessGuard path="/translation">
                                  <TranslationPage />
                                </AccessGuard>
                              }
                            />
                            {/* v9.3 内容发布 + 小程序开发 */}
                            <Route
                              path="/publish"
                              element={
                                <AccessGuard path="/publish">
                                  <PublishingPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/growth"
                              element={
                                <AccessGuard path="/growth">
                                  <GrowthPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/seo"
                              element={
                                <AccessGuard path="/seo">
                                  <SEOAnalyzerPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/miniapp"
                              element={
                                <AccessGuard path="/miniapp">
                                  <MiniAppPage />
                                </AccessGuard>
                              }
                            />
                            {/* v22 小程序服务端预览（无鉴权包装：iframe 直连后端生成页） */}
                            <Route path="/miniapp-preview/:filename" element={<MiniAppPreviewPage />} />
                            {/* v9.4 小游戏工坊（网页 + 微信双版本） */}
                            <Route
                              path="/games"
                              element={
                                <AccessGuard path="/games">
                                  <GameFactoryPage />
                                </AccessGuard>
                              }
                            />
                            {/* v13.23 短剧工厂（AI 编剧 + 配音 + 数字人播报） */}
                            <Route
                              path="/drama"
                              element={
                                <AccessGuard path="/drama">
                                  <ShortDramaPage />
                                </AccessGuard>
                              }
                            />
                            {/* v9.5 AI 配音 + 表情包 */}
                            <Route
                              path="/voice-dubbing"
                              element={
                                <AccessGuard path="/voice-dubbing">
                                  <VoicePage />
                                </AccessGuard>
                              }
                            />
                            {/* 演示别名：/voice-factory → AI 配音 */}
                            <Route
                              path="/voice-factory"
                              element={
                                <AccessGuard path="/voice-dubbing">
                                  <VoicePage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/meme"
                              element={
                                <AccessGuard path="/meme">
                                  <MemePage />
                                </AccessGuard>
                              }
                            />
                            {/* 演示别名：/meme-factory → 表情包工坊 */}
                            <Route
                              path="/meme-factory"
                              element={
                                <AccessGuard path="/meme">
                                  <MemePage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/digital-human"
                              element={
                                <AccessGuard path="/digital-human">
                                  <DigitalHumanPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/voice-chat"
                              element={
                                <AccessGuard path="/voice-chat">
                                  <VoiceChatPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/video-analyzer"
                              element={
                                <AccessGuard path="/video-analyzer">
                                  <VideoAnalyzerPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/mindmap"
                              element={
                                <AccessGuard path="/mindmap">
                                  <MindMapPage />
                                </AccessGuard>
                              }
                            />
                            {/* 演示别名：/mind-map → 思维导图 */}
                            <Route
                              path="/mind-map"
                              element={
                                <AccessGuard path="/mindmap">
                                  <MindMapPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/forecast"
                              element={
                                <AccessGuard path="/forecast">
                                  <ForecastPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/doc-qa"
                              element={
                                <AccessGuard path="/doc-qa">
                                  <DocQAPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/pdf-tools"
                              element={
                                <AccessGuard path="/pdf-tools">
                                  <PDFToolPage />
                                </AccessGuard>
                              }
                            />
                            {/* v10.1 新功能 */}
                            <Route
                              path="/web-search"
                              element={
                                <AccessGuard path="/web-search">
                                  <WebSearchPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/batch-process"
                              element={
                                <AccessGuard path="/batch-process">
                                  <BatchProcessPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/code-interpreter"
                              element={
                                <AccessGuard path="/code-interpreter">
                                  <CodeSandboxPage />
                                </AccessGuard>
                              }
                            />
                            {/* 演示别名：/code-sandbox → 代码解释器 */}
                            <Route
                              path="/code-sandbox"
                              element={
                                <AccessGuard path="/code-interpreter">
                                  <CodeSandboxPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/data-analyzer"
                              element={
                                <AccessGuard path="/data-analyzer">
                                  <DataAnalyzerPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/api-platform"
                              element={
                                <AccessGuard path="/api-platform">
                                  <ApiDocsPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/api-docs"
                              element={
                                <AccessGuard path="/api-platform">
                                  <ApiDocsPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/usage-analytics"
                              element={
                                <AccessGuard path="/usage-analytics">
                                  <UsageAnalyticsPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/usage-detail"
                              element={
                                <AccessGuard path="/usage-detail">
                                  <UsageDetailPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/invite-history"
                              element={
                                <AccessGuard path="/invite-history">
                                  <InviteHistoryPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/creator-center"
                              element={
                                <AccessGuard path="/creator-center">
                                  <CreatorCenterPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/audit-log"
                              element={
                                <AccessGuard path="/audit-log">
                                  <AuditLogPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/search"
                              element={<SearchPage />}
                            />
                            <Route
                              path="/feedback"
                              element={<FeedbackPage />}
                            />
                            <Route
                              path="/shortcuts"
                              element={<ShortcutsPage />}
                            />
                            <Route
                              path="/downloads"
                              element={<DownloadsPage />}
                            />
                            <Route
                              path="/scheduler"
                              element={
                                <AccessGuard path="/scheduler">
                                  <SchedulerPage />
                                </AccessGuard>
                              }
                            />
                            {/* v10.0 社区与变现 */}
                            <Route
                              path="/gallery"
                              element={
                                <AccessGuard path="/gallery">
                                  <GalleryPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/templates"
                              element={
                                <AccessGuard path="/templates">
                                  <TemplateMarketPage />
                                </AccessGuard>
                              }
                            />
                            {/* v11 全量修复：内容策略 / 竞品监控 / 收藏中心 */}
                            <Route
                              path="/strategy"
                              element={
                                <AccessGuard path="/strategy">
                                  <ContentStrategyPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/monitor"
                              element={
                                <AccessGuard path="/monitor">
                                  <CompetitorMonitorPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/favorites"
                              element={
                                <AccessGuard path="/favorites">
                                  <FavoritesPage />
                                </AccessGuard>
                              }
                            />
                            {/* v9.0 Phase 4: 运营分析 */}
                            <Route path="/dashboard" element={<DashboardPage />} />
                            <Route path="/ab-testing" element={<ABTestingPage />} />
                            {/* v9.0 办公效率 */}
                            <Route
                              path="/ppt-factory"
                              element={
                                <AccessGuard path="/ppt-factory">
                                  <PPTFactoryPage />
                                </AccessGuard>
                              }
                            />
                            <Route
                              path="/excel"
                              element={
                                <AccessGuard path="/excel">
                                  <ExcelPage />
                                </AccessGuard>
                              }
                            />
                            {/* v9.0 效率工具箱 */}
                            <Route path="/tool-hub" element={<ToolHubPage />} />
                            <Route path="/tools" element={<ToolHubPage />} />
                            <Route path="/tool/:toolId" element={<ToolRunPage />} />
                            <Route
                              path="/stock"
                              element={
                                <AccessGuard path="/stock">
                                  <StockAnalysisPage />
                                </AccessGuard>
                              }
                            />
                            {/* v9.1 商业版 */}
                            <Route
                              path="/profile"
                              element={<ProfilePage user={user} onUserUpdate={handleUserUpdate} />}
                            />
                            <Route path="/membership" element={<MembershipPage />} />
                            <Route path="/admin" element={<AdminPage />} />
                            <Route path="/help" element={<HelpPage />} />
                            <Route path="/records" element={<RecordsPage />} />
                            <Route path="/" element={<Navigate to="/home" replace />} />
                            {/* 404 兜底：未匹配路由展示 NotFound，避免空白空壳 */}
                            <Route path="*" element={<NotFoundPage />} />
                          </Routes>
                        </ErrorBoundary>
                      </main>
                      {/* 全局浮动机器人：登录后所有页面可用 */}
                      <FloatingAssistant />
                      {/* 全局回到顶部（登录态内页） */}
                      <BackToTop />
                      {/* 移动端底部导航 */}
                      <MobileBottomNav />
                    </div>
                  </div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </ToastProvider>
    </Router>
  )
}
