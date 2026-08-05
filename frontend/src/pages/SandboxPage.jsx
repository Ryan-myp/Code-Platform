import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Plus, Play, Square, Trash2, RefreshCw,
  FolderOpen, Server, Container, Search, Terminal,
  LayoutGrid, List as ListIcon, Activity, Zap, Clock, Loader2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import MarkdownRenderer from '../components/MarkdownRenderer'
import {
  Modal, Button, Empty, SkeletonGrid, ErrorState, Badge, PageHeader, ConfirmDialog,
} from '../components/ui'

// 预置服务模板（前端展示用，与后端 SERVICE_TEMPLATES 互补）
const PRESET_SERVICES = [
  { id: 'python', name: 'Python 环境', image: 'python:3.11', ports: '8000:8000', desc: 'Python 3.11 开发环境' },
  { id: 'node', name: 'Node.js 环境', image: 'node:20', ports: '3000:3000', desc: 'Node.js 20 LTS 环境' },
  { id: 'go', name: 'Go 环境', image: 'golang:1.21', ports: '8080:8080', desc: 'Go 1.21 开发环境' },
  { id: 'postgres', name: 'PostgreSQL', image: 'postgres:16', ports: '5432:5432', desc: 'PostgreSQL 16 数据库' },
  { id: 'redis', name: 'Redis', image: 'redis:7', ports: '6379:6379', desc: 'Redis 7 缓存' },
  { id: 'mysql', name: 'MySQL', image: 'mysql:8', ports: '3306:3306', desc: 'MySQL 8 数据库' },
]

// 沙箱状态自定义映射
const SANDBOX_STATUS_MAP = {
  created: { text: '已创建', cls: 'bg-blue-100 text-blue-700' },
  exited: { text: '已退出', cls: 'bg-gray-100 text-gray-600' },
}

// 解析端口字段（后端存储为 JSON 字符串或数组）
function formatPorts(ports) {
  if (!ports) return '-'
  if (Array.isArray(ports)) return ports.length ? ports.join(', ') : '-'
  try {
    const parsed = JSON.parse(ports)
    return Array.isArray(parsed) ? (parsed.length ? parsed.join(', ') : '-') : String(ports)
  } catch {
    return String(ports)
  }
}

// 容器日志弹窗：轮询沙箱日志接口（运行中每 3s 刷新）；支持 AI 分析定位问题
function LogModal({ project, onClose }) {
  const toast = useToast()
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const logsEndRef = useRef(null)

  useEffect(() => {
    if (!project) return
    setAnalysis(null)
    let alive = true
    let timer = null
    const fetchLogs = async () => {
      try {
        const res = await api.get(`/api/sandbox/projects/${project.id}/logs?tail=300`)
        if (!alive) return
        setLogs(res.data.logs || [])
        setMessage(res.data.message || '')
        // 非运行中停止轮询
        if (project.status !== 'running') clearInterval(timer)
      } catch (e) {
        if (alive) {
          setMessage(`日志加载失败：${e.message}`)
          clearInterval(timer)
        }
      } finally {
        if (alive) setLoading(false)
      }
    }
    fetchLogs()
    timer = setInterval(fetchLogs, 3000)
    return () => { alive = false; clearInterval(timer) }
  }, [project])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs, loading])

  // AI 分析日志定位问题根因
  const handleAnalyze = async () => {
    setAnalyzing(true)
    setAnalysis(null)
    try {
      const res = await api.post(`/api/sandbox/projects/${project.id}/logs/analyze`)
      setAnalysis(res.data.analysis || '（无分析结果）')
    } catch (e) {
      toast.error(`分析失败：${e.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <Modal open={!!project} onClose={onClose} title={`容器日志 - ${project?.name || ''}`} size="lg">
      {message && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-700">{message}</div>
      )}
      <div className="mb-3 flex items-center gap-2">
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white text-xs font-medium rounded-lg hover:opacity-90 transition-all disabled:opacity-60"
        >
          {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
          {analyzing ? 'AI 分析中（约 10-60 秒）…' : 'AI 分析日志定位问题'}
        </button>
        {analysis && (
          <span className="text-xs text-gray-400">分析基于最近 {logs.length} 行日志</span>
        )}
      </div>
      {analysis && (
        <div className="mb-3 p-4 rounded-xl bg-indigo-50 border border-indigo-200 text-sm text-gray-800 max-h-[30vh] overflow-y-auto">
          <p className="text-xs font-semibold text-indigo-700 mb-2 flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5" /> AI 诊断报告
          </p>
          <MarkdownRenderer content={analysis} />
        </div>
      )}
      {loading ? (
        <div className="py-12 text-center text-gray-400 text-sm">加载中…</div>
      ) : (
        <pre className="bg-gray-900 text-green-400 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[55vh] whitespace-pre-wrap">
          {logs.length ? logs.join('\n') : '（暂无日志输出）'}
        </pre>
      )}
      <div ref={logsEndRef} />
    </Modal>
  )
}

// 项目卡片
function ProjectCard({ project, onStart, onStop, onDelete, onLogs, viewMode }) {
  const isRunning = project.status === 'running'
  const ports = formatPorts(project.ports)

  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4 hover:shadow-md transition-shadow">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isRunning ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-100 text-gray-500'
        }`}>
          <FolderOpen className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{project.name}</h3>
            <Badge status={project.status} customMap={SANDBOX_STATUS_MAP} />
          </div>
          <p className="text-sm text-gray-500 truncate">{project.image} · {ports}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => onLogs(project)}
            className="p-2 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded-lg transition-colors"
            title="查看日志"
          >
            <Terminal className="w-4 h-4" />
          </button>
          {isRunning ? (
            <Button variant="danger" size="sm" icon={Square} onClick={() => onStop(project)}>停止</Button>
          ) : (
            <Button variant="success" size="sm" icon={Play} onClick={() => onStart(project)}>启动</Button>
          )}
          <button
            onClick={() => onDelete(project)}
            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
            isRunning ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-100 text-gray-500'
          }`}>
            <FolderOpen className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{project.name}</h3>
            <p className="text-xs text-gray-500 truncate">{project.image}{project.project_dir ? ` · ${project.project_dir.split('/').slice(-2).join('/')}` : ''}</p>
          </div>
        </div>
        <Badge status={project.status} customMap={SANDBOX_STATUS_MAP} />
      </div>

      {project.description && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-3">{project.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
        <span className="flex items-center gap-1" title="端口映射">
          <Zap className="w-3 h-3" />{ports}
        </span>
        <span className="flex items-center gap-1" title="创建时间">
          <Clock className="w-3 h-3" />{formatRelativeTime(project.created_at)}
        </span>
      </div>

      <div className="flex items-center gap-2 pt-4 border-t border-gray-100 mt-auto">
        <button
          onClick={() => onLogs(project)}
          className="p-2 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded-lg transition-colors"
          title="查看日志"
        >
          <Terminal className="w-4 h-4" />
        </button>
        {isRunning ? (
          <Button variant="danger" size="sm" icon={Square} onClick={() => onStop(project)} className="flex-1">停止</Button>
        ) : (
          <Button variant="success" size="sm" icon={Play} onClick={() => onStart(project)} className="flex-1">启动</Button>
        )}
        <button
          onClick={() => onDelete(project)}
          className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
          title="删除"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

// 项目表单模态框（创建用，预留 editing 以支持后续编辑）
function ProjectFormModal({ open, onClose, onSubmit, editing, loading }) {
  const [form, setForm] = useState({ name: '', description: '', image: '', ports: '', env: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      setForm(editing
        ? {
            name: editing.name || '',
            description: editing.description || '',
            image: editing.image || '',
            ports: editing.ports || '',
            env: editing.env || '',
          }
        : { name: '', description: '', image: '', ports: '', env: '' }
      )
      setErrors({})
    }
  }, [open, editing])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入项目名称'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim() })
  }

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑项目' : '新建项目'}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={loading}>{editing ? '保存' : '创建'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">名称 <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：我的项目"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <textarea
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            rows={2}
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">镜像</label>
          <input
            type="text"
            value={form.image}
            onChange={(e) => setField('image', e.target.value)}
            placeholder="例如: python:3.11"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">端口映射</label>
          <input
            type="text"
            value={form.ports}
            onChange={(e) => setField('ports', e.target.value)}
            placeholder="例如: 8000:8000"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">环境变量</label>
          <textarea
            value={form.env}
            onChange={(e) => setField('env', e.target.value)}
            rows={3}
            placeholder="KEY=VALUE 格式，每行一个"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all font-mono text-sm"
          />
        </div>
      </div>
    </Modal>
  )
}

// 服务表单模态框（添加自定义服务）
function ServiceFormModal({ open, onClose, onSubmit, loading }) {
  const [form, setForm] = useState({ name: '', image: '', ports: '', env: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      setForm({ name: '', image: '', ports: '', env: '' })
      setErrors({})
    }
  }, [open])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入服务名称'
    if (!form.image.trim()) e.image = '请输入镜像名称'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim(), image: form.image.trim() })
  }

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="添加服务"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={loading}>添加</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">名称 <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：自定义服务"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">镜像 <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={form.image}
            onChange={(e) => setField('image', e.target.value)}
            placeholder="例如: python:3.11"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.image ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.image && <p className="text-xs text-red-500 mt-1">{errors.image}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">端口映射</label>
          <input
            type="text"
            value={form.ports}
            onChange={(e) => setField('ports', e.target.value)}
            placeholder="例如: 8000:8000"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">环境变量</label>
          <textarea
            value={form.env}
            onChange={(e) => setField('env', e.target.value)}
            rows={3}
            placeholder="KEY=VALUE 格式，每行一个"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all font-mono text-sm"
          />
        </div>
      </div>
    </Modal>
  )
}

export default function SandboxPage() {
  const toast = useToast()
  const [projects, setProjects] = useState([])
  const [services, setServices] = useState([])
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('projects')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('grid')

  const [showProjectForm, setShowProjectForm] = useState(false)
  const [savingProject, setSavingProject] = useState(false)
  const [showServiceForm, setShowServiceForm] = useState(false)
  const [savingService, setSavingService] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [logTarget, setLogTarget] = useState(null)

  const [pullImage, setPullImage] = useState('')
  const [pulling, setPulling] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const fetchProjects = useCallback(async (initial = false) => {
    if (initial) {
      setLoading(true)
      setError(null)
    }
    try {
      const res = await api.get('/api/sandbox/projects')
      setProjects(res.data)
      if (initial) setError(null)
    } catch (e) {
      if (initial) setError(e)
    } finally {
      if (initial) setLoading(false)
    }
  }, [])

  const fetchServices = useCallback(async () => {
    try {
      const res = await api.get('/api/sandbox/services')
      const list = Array.isArray(res.data) ? res.data : (res.data.services || [])
      // 兼容后端返回 dict 的旧格式：{id: {name, image, ...}}
      setServices(Array.isArray(list)
        ? list
        : Object.entries(list).map(([id, s]) => ({ id, ...s })))
    } catch {
      setServices([])
    }
  }, [])

  const fetchImages = useCallback(async () => {
    try {
      const res = await api.get('/api/sandbox/images')
      setImages(Array.isArray(res.data) ? res.data : (res.data.images || []))
    } catch {
      setImages([])
    }
  }, [])

  useEffect(() => {
    fetchProjects(true)
    fetchServices()
    fetchImages()
    const interval = setInterval(() => fetchProjects(false), 5000)
    return () => clearInterval(interval)
  }, [fetchProjects, fetchServices, fetchImages])

  const handleRefresh = async () => {
    setRefreshing(true)
    await Promise.all([fetchProjects(false), fetchServices(), fetchImages()])
    setRefreshing(false)
  }

  const handleCreateProject = async (formData) => {
    setSavingProject(true)
    try {
      await api.post('/api/sandbox/projects', formData)
      toast.success(`项目「${formData.name}」已创建`)
      setShowProjectForm(false)
      fetchProjects(false)
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    } finally {
      setSavingProject(false)
    }
  }

  const handleCreateService = async (formData) => {
    setSavingService(true)
    try {
      // 自定义服务为本地展示模板（无后端持久化接口），合并入列表
      const custom = {
        id: `custom-${Date.now()}`,
        name: formData.name,
        image: formData.image,
        ports: formData.ports ? formData.ports.split(',').map((p) => p.trim()).filter(Boolean) : [],
        description: '自定义服务',
      }
      setServices((prev) => [...(Array.isArray(prev) ? prev : []), custom])
      toast.success(`服务「${formData.name}」已添加`)
      setShowServiceForm(false)
    } catch (e) {
      toast.error(`添加失败：${e.message}`)
    } finally {
      setSavingService(false)
    }
  }

  const handleAction = async (project, action) => {
    try {
      await api.post(`/api/sandbox/projects/${project.id}/${action}`, {})
      toast.success(action === 'start' ? `项目「${project.name}」已启动` : `项目「${project.name}」已停止`)
      fetchProjects(false)
    } catch (e) {
      toast.error(`${action === 'start' ? '启动' : '停止'}失败：${e.message}`)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/sandbox/projects/${deleteTarget.id}`)
      toast.success(`项目「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      fetchProjects(false)
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const handlePullImage = async () => {
    if (!pullImage.trim()) return
    setPulling(true)
    try {
      await api.post('/api/sandbox/images/pull', { image: pullImage.trim() })
      toast.success(`镜像「${pullImage.trim()}」拉取成功`)
      setPullImage('')
      fetchImages()
    } catch (e) {
      toast.error(`拉取失败：${e.message}`)
    } finally {
      setPulling(false)
    }
  }

  const filteredProjects = projects.filter((p) =>
    p.name?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const stats = [
    { label: '运行中', value: projects.filter((p) => p.status === 'running').length, icon: Activity, color: 'from-emerald-500 to-green-600' },
    { label: '已停止', value: projects.filter((p) => p.status !== 'running').length, icon: Square, color: 'from-gray-400 to-gray-500' },
    { label: '总项目', value: projects.length, icon: FolderOpen, color: 'from-violet-500 to-purple-600' },
    { label: '镜像数', value: images.length, icon: Container, color: 'from-blue-500 to-cyan-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="沙箱运行环境"
        description="管理容器化服务和项目代码"
        icon={Container}
        actions={
          <>
            <Button variant="secondary" icon={RefreshCw} onClick={handleRefresh} loading={refreshing}>刷新</Button>
            <Button variant="primary" icon={Plus} onClick={() => setShowProjectForm(true)}>新建项目</Button>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center flex-shrink-0`}>
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-2xl border border-gray-200 p-2 flex gap-2">
        {[
          { id: 'projects', label: '项目列表', icon: FolderOpen },
          { id: 'services', label: '预置服务', icon: Server },
          { id: 'images', label: '镜像管理', icon: Container },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-purple-600 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Projects Tab */}
      {activeTab === 'projects' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索项目名称…"
                className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              />
            </div>
            <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1 self-end sm:self-auto">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
                title="网格视图"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
                title="列表视图"
              >
                <ListIcon className="w-4 h-4" />
              </button>
            </div>
          </div>

          {loading ? (
            <SkeletonGrid count={6} />
          ) : error ? (
            <ErrorState message={`加载失败：${error.message}`} onRetry={() => fetchProjects(true)} />
          ) : filteredProjects.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty
                icon={FolderOpen}
                title={searchQuery ? '未找到匹配的项目' : '暂无项目'}
                description={searchQuery ? '尝试调整搜索条件' : '点击「新建项目」开始你的第一个沙箱项目'}
                actionLabel={searchQuery ? undefined : '新建项目'}
                onAction={searchQuery ? undefined : () => setShowProjectForm(true)}
              />
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onStart={(p) => handleAction(p, 'start')}
                  onStop={(p) => handleAction(p, 'stop')}
                  onDelete={setDeleteTarget}
                  onLogs={setLogTarget}
                  viewMode="grid"
                />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onStart={(p) => handleAction(p, 'start')}
                  onStop={(p) => handleAction(p, 'stop')}
                  onDelete={setDeleteTarget}
                  onLogs={setLogTarget}
                  viewMode="list"
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Services Tab */}
      {activeTab === 'services' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-gray-900">预置服务模板</h3>
            <Button variant="primary" size="sm" icon={Plus} onClick={() => setShowServiceForm(true)}>添加服务</Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {PRESET_SERVICES.map((service) => (
              <div key={service.id} className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center">
                    <Server className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{service.name}</h3>
                    <p className="text-xs text-gray-500">{service.image}</p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mb-4">{service.desc}</p>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{service.ports}</span>
                </div>
              </div>
            ))}
            {services.map((service) => (
              <div key={service.id} className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                    <Server className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{service.name}</h3>
                    <p className="text-xs text-gray-500">{service.image}</p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mb-4">{service.description || '自定义服务'}</p>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{formatPorts(service.ports)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Images Tab */}
      {activeTab === 'images' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-4 flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={pullImage}
              onChange={(e) => setPullImage(e.target.value)}
              placeholder="输入镜像名称，例如: python:3.11"
              className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              onKeyDown={(e) => e.key === 'Enter' && handlePullImage()}
            />
            <Button variant="primary" icon={Plus} loading={pulling} disabled={!pullImage.trim()} onClick={handlePullImage}>
              拉取
            </Button>
          </div>
          {images.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty
                icon={Container}
                title="暂无镜像"
                description="在上方输入镜像名称并拉取，例如 python:3.11"
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {images.map((img) => (
                <div key={img.id} className="bg-white rounded-2xl border border-gray-200 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center">
                      <Container className="w-5 h-5 text-white" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-semibold text-gray-900 truncate">{img.repository}:{img.tag}</h3>
                      <p className="text-xs text-gray-500 truncate">{img.id}</p>
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>大小: {img.size || 'N/A'}</p>
                    <p>创建: {formatRelativeTime(img.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <ProjectFormModal
        open={showProjectForm}
        onClose={() => setShowProjectForm(false)}
        onSubmit={handleCreateProject}
        editing={null}
        loading={savingProject}
      />

      <ServiceFormModal
        open={showServiceForm}
        onClose={() => setShowServiceForm(false)}
        onSubmit={handleCreateService}
        loading={savingService}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除项目"
        message={`确定要删除项目「${deleteTarget?.name}」吗？这将同时删除容器和数据，此操作不可撤销。`}
        confirmLabel="确认删除"
      />

      <LogModal project={logTarget} onClose={() => setLogTarget(null)} />
    </div>
  )
}
