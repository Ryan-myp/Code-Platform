import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { 
  Plus, Play, Square, Trash2, RefreshCw, Terminal, 
  FolderOpen, Server, Clock, AlertCircle, CheckCircle, 
  Copy, ExternalLink, Container, Database, Search,
  Grid, List as ListIcon, Activity, Cpu, HardDrive,
  Wifi, Zap, Shield, Settings, Power, Loader
} from 'lucide-react'

const API = 'http://localhost:8888'

// 预置服务模板
const PRESET_SERVICES = [
  { id: 'python', name: 'Python 环境', image: 'python:3.11', ports: '8000:8000', desc: 'Python 3.11 开发环境' },
  { id: 'node', name: 'Node.js 环境', image: 'node:20', ports: '3000:3000', desc: 'Node.js 20 LTS 环境' },
  { id: 'go', name: 'Go 环境', image: 'golang:1.21', ports: '8080:8080', desc: 'Go 1.21 开发环境' },
  { id: 'postgres', name: 'PostgreSQL', image: 'postgres:16', ports: '5432:5432', desc: 'PostgreSQL 16 数据库' },
  { id: 'redis', name: 'Redis', image: 'redis:7', ports: '6379:6379', desc: 'Redis 7 缓存' },
  { id: 'mysql', name: 'MySQL', image: 'mysql:8', ports: '3306:3306', desc: 'MySQL 8 数据库' },
]

export default function SandboxPage() {
  const [projects, setProjects] = useState([])
  const [services, setServices] = useState([])
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showCreateService, setShowCreateService] = useState(false)
  const [creating, setCreating] = useState(false)
  const [creatingService, setCreatingService] = useState(false)
  const [newProject, setNewProject] = useState({ 
    name: '', 
    description: '', 
    service_id: '',
    image: '',
    ports: '',
    env: ''
  })
  const [newService, setNewService] = useState({
    name: '',
    image: '',
    ports: '',
    env: ''
  })
  const [logs, setLogs] = useState({})
  const [activeTab, setActiveTab] = useState('projects')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('grid')
  const [pullImage, setPullImage] = useState('')
  const [pulling, setPulling] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({ running: 0, stopped: 0, total: 0 })

  const getToken = () => localStorage.getItem('token')

  const fetchProjects = async () => {
    const token = getToken()
    if (!token) return
    try {
      const res = await axios.get(`${API}/api/sandbox/projects`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setProjects(res.data)
      setError(null)
      const running = res.data.filter(p => p.status === 'running').length
      setStats({ running, stopped: res.data.length - running, total: res.data.length })
    } catch (err) {
      console.error('获取项目失败', err)
      setError('获取项目失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchServices = async () => {
    const token = getToken()
    if (!token) return
    try {
      const res = await axios.get(`${API}/api/sandbox/services`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setServices(res.data)
    } catch (err) {
      console.error('获取服务失败', err)
    }
  }

  const fetchImages = async () => {
    const token = getToken()
    if (!token) return
    try {
      const res = await axios.get(`${API}/api/sandbox/images`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setImages(res.data)
    } catch (err) {
      console.error('获取镜像失败', err)
    }
  }

  useEffect(() => {
    fetchProjects()
    fetchServices()
    fetchImages()
    const interval = setInterval(fetchProjects, 5000)
    return () => clearInterval(interval)
  }, [])

  const createProject = async () => {
    if (!newProject.name.trim()) return
    setCreating(true)
    const token = getToken()
    if (!token) return
    try {
      await axios.post(`${API}/api/sandbox/projects`, newProject, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setNewProject({ name: '', description: '', service_id: '', image: '', ports: '', env: '' })
      setShowCreate(false)
      fetchProjects()
    } catch (err) {
      console.error('创建项目失败', err)
      alert('创建失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setCreating(false)
    }
  }

  const createService = async () => {
    if (!newService.name.trim() || !newService.image.trim()) return
    setCreatingService(true)
    const token = getToken()
    if (!token) return
    try {
      await axios.post(`${API}/api/sandbox/services`, newService, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setNewService({ name: '', image: '', ports: '', env: '' })
      setShowCreateService(false)
      fetchServices()
    } catch (err) {
      console.error('创建服务失败', err)
      alert('创建失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setCreatingService(false)
    }
  }

  const startProject = async (id) => {
    const token = getToken()
    try {
      await axios.post(`${API}/api/sandbox/projects/${id}/start`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchProjects()
    } catch (err) {
      alert('启动失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const stopProject = async (id) => {
    const token = getToken()
    try {
      await axios.post(`${API}/api/sandbox/projects/${id}/stop`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchProjects()
    } catch (err) {
      alert('停止失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const deleteProject = async (id) => {
    if (!confirm('确定删除此项目？这将同时删除容器和数据。')) return
    const token = getToken()
    try {
      await axios.delete(`${API}/api/sandbox/projects/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchProjects()
    } catch (err) {
      alert('删除失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const pullImageFn = async () => {
    if (!pullImage.trim()) return
    setPulling(true)
    const token = getToken()
    try {
      await axios.post(`${API}/api/sandbox/images/pull`, { image: pullImage }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setPullImage('')
      fetchImages()
    } catch (err) {
      alert('拉取失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setPulling(false)
    }
  }

  const filteredProjects = projects.filter(p => 
    p.name?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="animate-spin w-8 h-8 text-purple-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">沙箱运行环境</h1>
          <p className="text-gray-500 mt-1">管理容器化服务和项目代码</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { fetchProjects(); fetchServices(); fetchImages() }}
            className="flex items-center gap-2 px-4 py-2 border border-gray-200 text-gray-700 rounded-xl hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            <span>刷新</span>
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
          >
            <Plus className="w-4 h-4" />
            <span>新建项目</span>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '运行中', value: stats.running, icon: Activity, color: 'from-emerald-500 to-green-600' },
          { label: '已停止', value: stats.stopped, icon: Square, color: 'from-gray-400 to-gray-500' },
          { label: '总项目', value: stats.total, icon: FolderOpen, color: 'from-violet-500 to-purple-600' },
          { label: '镜像数', value: images.length, icon: Container, color: 'from-blue-500 to-cyan-600' },
        ].map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center`}>
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
        ].map(tab => (
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

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Projects Tab */}
      {activeTab === 'projects' && (
        <div className="space-y-4">
          {/* Toolbar */}
          <div className="bg-white rounded-2xl border border-gray-200 p-4 flex items-center gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索项目..."
                className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
            <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
              >
                <ListIcon className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Projects Grid/List */}
          {filteredProjects.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
              <FolderOpen className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">暂无项目</h3>
              <p className="text-gray-500 mb-6">点击「新建项目」开始你的第一个沙箱项目</p>
              <button
                onClick={() => setShowCreate(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
              >
                <Plus className="w-4 h-4" />
                新建项目
              </button>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProjects.map(project => (
                <div key={project.id} className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                        project.status === 'running' 
                          ? 'bg-emerald-100 text-emerald-600' 
                          : 'bg-gray-100 text-gray-500'
                      }`}>
                        <FolderOpen className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900">{project.name}</h3>
                        <p className="text-xs text-gray-500">{project.image}</p>
                      </div>
                    </div>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                      project.status === 'running' 
                        ? 'bg-emerald-100 text-emerald-700' 
                        : 'bg-gray-100 text-gray-700'
                    }`}>
                      {project.status === 'running' ? '运行中' : '已停止'}
                    </span>
                  </div>
                  {project.description && (
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">{project.description}</p>
                  )}
                  <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
                    <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{project.ports || '-'}</span>
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{new Date(project.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
                    {project.status === 'running' ? (
                      <button
                        onClick={() => stopProject(project.id)}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 text-sm font-medium"
                      >
                        <Square className="w-4 h-4" />
                        停止
                      </button>
                    ) : (
                      <button
                        onClick={() => startProject(project.id)}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-emerald-50 text-emerald-600 rounded-lg hover:bg-emerald-100 text-sm font-medium"
                      >
                        <Play className="w-4 h-4" />
                        启动
                      </button>
                    )}
                    <button
                      onClick={() => deleteProject(project.id)}
                      className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredProjects.map(project => (
                <div key={project.id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    project.status === 'running' ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-100 text-gray-500'
                  }`}>
                    <FolderOpen className="w-5 h-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{project.name}</h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        project.status === 'running' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-700'
                      }`}>
                        {project.status === 'running' ? '运行中' : '已停止'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500">{project.image} · {project.ports}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {project.status === 'running' ? (
                      <button onClick={() => stopProject(project.id)} className="px-3 py-1.5 bg-red-50 text-red-600 rounded-lg text-sm hover:bg-red-100">停止</button>
                    ) : (
                      <button onClick={() => startProject(project.id)} className="px-3 py-1.5 bg-emerald-50 text-emerald-600 rounded-lg text-sm hover:bg-emerald-100">启动</button>
                    )}
                    <button onClick={() => deleteProject(project.id)} className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
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
            <button
              onClick={() => setShowCreateService(true)}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700 text-sm"
            >
              <Plus className="w-4 h-4" />
              添加服务
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {PRESET_SERVICES.map(service => (
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
            {services.map(service => (
              <div key={service.id} className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                    <Server className("w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{service.name}</h3>
                    <p className="text-xs text-gray-500">{service.image}</p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mb-4">{service.description || '自定义服务'}</p>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{service.ports}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Images Tab */}
      {activeTab === 'images' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={pullImage}
                onChange={(e) => setPullImage(e.target.value)}
                placeholder="输入镜像名称，例如: python:3.11"
                className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                onKeyDown={(e) => e.key === 'Enter' && pullImageFn()}
              />
              <button
                onClick={pullImageFn}
                disabled={pulling || !pullImage.trim()}
                className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50"
              >
                {pulling ? <Loader className="w-4 h-4 animate-spin" /> : '拉取'}
              </button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {images.map(img => (
              <div key={img.id} className="bg-white rounded-2xl border border-gray-200 p-5">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center">
                    <Container className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{img.repository}:{img.tag}</h3>
                    <p className="text-xs text-gray-500">{img.id}</p>
                  </div>
                </div>
                <div className="text-sm text-gray-600">
                  <p>大小: {img.size || 'N/A'}</p>
                  <p>创建: {new Date(img.created_at).toLocaleDateString()}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Project Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-auto">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">新建项目</h2>
              <button onClick={() => setShowCreate(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  value={newProject.name}
                  onChange={(e) => setNewProject({...newProject, name: e.target.value})}
                  placeholder="例如：我的项目"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={newProject.description}
                  onChange={(e) => setNewProject({...newProject, description: e.target.value})}
                  rows={2}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">镜像</label>
                <input
                  type="text"
                  value={newProject.image}
                  onChange={(e) => setNewProject({...newProject, image: e.target.value})}
                  placeholder="例如: python:3.11"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">端口映射</label>
                <input
                  type="text"
                  value={newProject.ports}
                  onChange={(e) => setNewProject({...newProject, ports: e.target.value})}
                  placeholder="例如: 8000:8000"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">环境变量</label>
                <textarea
                  value={newProject.env}
                  onChange={(e) => setNewProject({...newProject, env: e.target.value})}
                  rows={3}
                  placeholder="KEY=VALUE 格式，每行一个"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl"
                disabled={creating}
              >
                取消
              </button>
              <button
                onClick={createProject}
                className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50"
                disabled={creating || !newProject.name.trim()}
              >
                {creating ? <Loader className="w-4 h-4 animate-spin inline" /> : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Service Modal */}
      {showCreateService && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">添加服务</h2>
              <button onClick={() => setShowCreateService(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  value={newService.name}
                  onChange={(e) => setNewService({...newService, name: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">镜像 *</label>
                <input
                  type="text"
                  value={newService.image}
                  onChange={(e) => setNewService({...newService, image: e.target.value})}
                  placeholder="例如: python:3.11"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">端口映射</label>
                <input
                  type="text"
                  value={newService.ports}
                  onChange={(e) => setNewService({...newService, ports: e.target.value})}
                  placeholder="例如: 8000:8000"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">环境变量</label>
                <textarea
                  value={newService.env}
                  onChange={(e) => setNewService({...newService, env: e.target.value})}
                  rows={3}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowCreateService(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl"
              >
                取消
              </button>
              <button
                onClick={createService}
                className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
              >
                添加
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
