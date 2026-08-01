import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Plus, Play, Square, Trash2, RefreshCw, Terminal, FolderOpen, Server, Clock, AlertCircle, CheckCircle, Copy, ExternalLink, Container, Database } from 'lucide-react'

const API = 'http://localhost:8888'

export default function SandboxPage() {
  const [projects, setProjects] = useState([])
  const [services, setServices] = useState([])
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newProject, setNewProject] = useState({ 
    name: '', 
    description: '', 
    service_id: '',
    image: '',
    ports: '',
    env: ''
  })
  const [logs, setLogs] = useState({})
  const [activeTab, setActiveTab] = useState('containers')
  const [pullImage, setPullImage] = useState('')
  const [pulling, setPulling] = useState(false)
  const [error, setError] = useState(null)

  // 获取 token
  const getToken = () => {
    const token = localStorage.getItem('token')
    if (!token) {
      window.location.href = '/login'
      return null
    }
    return token
  }

  const fetchProjects = async () => {
    const token = getToken()
    if (!token) return
    
    try {
      const res = await axios.get(`${API}/api/sandbox/projects`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setProjects(res.data)
      setError(null)
    } catch (err) {
      console.error('获取项目失败', err)
      if (err.response?.status === 401) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
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
      const res = await axios.post(`${API}/api/sandbox/container`, {
        name: newProject.name,
        description: newProject.description,
        service_id: newProject.service_id,
        image: newProject.image,
        ports: newProject.ports ? newProject.ports.split(',').map(p => p.trim()) : [],
        env: newProject.env ? newProject.env.split('\n').filter(e => e.trim()) : []
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setProjects([res.data, ...projects])
      setShowCreate(false)
      setNewProject({ 
        name: '', 
        description: '', 
        service_id: '',
        image: '',
        ports: '',
        env: ''
      })
    } catch (err) {
      alert(err.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const pullImageHandler = async () => {
    if (!pullImage.trim()) return
    const token = getToken()
    if (!token) return
    
    setPulling(true)
    try {
      const res = await axios.post(`${API}/api/sandbox/images/pull`, {
        image: pullImage.trim()
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.data.status === 'success') {
        alert('镜像拉取成功')
        setPullImage('')
        fetchImages()
      } else {
        alert('拉取失败: ' + res.data.message)
      }
    } catch (err) {
      alert(err.response?.data?.detail || '拉取失败')
    } finally {
      setPulling(false)
    }
  }

  const startProject = async (project) => {
    const token = getToken()
    if (!token) return
    
    try {
      const res = await axios.post(`${API}/api/sandbox/container/${project.id}/start`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchProjects()
    } catch (err) {
      alert(err.response?.data?.detail || '启动失败')
    }
  }

  const stopProject = async (project) => {
    const token = getToken()
    if (!token) return
    
    try {
      await axios.post(`${API}/api/sandbox/container/${project.id}/stop`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchProjects()
    } catch (err) {
      alert(err.response?.data?.detail || '停止失败')
    }
  }

  const deleteProject = async (project) => {
    if (!confirm(`确定删除 "${project.name}" 吗？`)) return
    const token = getToken()
    if (!token) return
    
    try {
      await axios.post(`${API}/api/sandbox/container/${project.id}/remove`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setProjects(projects.filter(p => p.id !== project.id))
    } catch (err) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  const refreshLogs = async (project) => {
    const token = getToken()
    if (!token) return
    
    try {
      const res = await axios.get(`${API}/api/sandbox/container/${project.id}/logs?tail=200`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setLogs({ ...logs, [project.id]: res.data.logs })
    } catch (err) {
      console.error('获取日志失败', err)
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running': return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'stopped': return <Square className="w-4 h-4 text-gray-400" />
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />
      default: return <Clock className="w-4 h-4 text-gray-400" />
    }
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">沙箱运行环境</h1>
          <p className="text-gray-500 mt-1">管理容器化服务和项目代码</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={fetchProjects}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition"
          >
            <RefreshCw className="w-4 h-4" />
            刷新
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg hover:opacity-90 transition"
          >
            <Plus className="w-4 h-4" />
            新建项目
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* 标签页 */}
      <div className="flex gap-2 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('containers')}
          className={`px-4 py-2 rounded-lg ${activeTab === 'containers' ? 'bg-purple-100 text-purple-700' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <Container className="w-4 h-4 inline mr-2" />
          容器列表
        </button>
        <button
          onClick={() => setActiveTab('services')}
          className={`px-4 py-2 rounded-lg ${activeTab === 'services' ? 'bg-purple-100 text-purple-700' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <Database className="w-4 h-4 inline mr-2" />
          预置服务
        </button>
        <button
          onClick={() => setActiveTab('images')}
          className={`px-4 py-2 rounded-lg ${activeTab === 'images' ? 'bg-purple-100 text-purple-700' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <FolderOpen className="w-4 h-4 inline mr-2" />
          镜像管理
        </button>
      </div>

      {/* 容器列表 */}
      {activeTab === 'containers' && (
        <>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
            </div>
          ) : projects.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Container className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>暂无项目，点击新建项目开始</p>
            </div>
          ) : (
            <div className="space-y-4">
              {projects.map(project => {
                const isRunning = project.status === 'running'
                return (
                  <div key={project.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-4">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isRunning ? 'bg-green-100' : 'bg-gray-100'}`}>
                          {getStatusIcon(project.status)}
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">{project.name}</h3>
                          <p className="text-sm text-gray-500 mt-1">{project.description || '暂无描述'}</p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                            <span className="flex items-center gap-1">
                              <Terminal className="w-3 h-3" />
                              {project.service_id ? `服务: ${project.service_id}` : project.command}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {new Date(project.created_at).toLocaleString('zh-CN')}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isRunning ? (
                          <>
                            <button
                              onClick={() => refreshLogs(project)}
                              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
                              title="刷新日志"
                            >
                              <Terminal className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => stopProject(project)}
                              className="p-2 text-red-500 hover:bg-red-50 rounded-lg"
                              title="停止"
                            >
                              <Square className="w-4 h-4" />
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => startProject(project)}
                            className="p-2 text-green-600 hover:bg-green-50 rounded-lg"
                            title="启动"
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => deleteProject(project)}
                          className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg"
                          title="删除"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {/* 日志面板 */}
                    {isRunning && logs[project.id] && (
                      <div className="mt-4 bg-gray-900 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs text-gray-400 flex items-center gap-1">
                            <Terminal className="w-3 h-3" />
                            运行日志
                          </span>
                          <button
                            onClick={() => refreshLogs(project)}
                            className="text-xs text-gray-400 hover:text-white"
                          >
                            刷新
                          </button>
                        </div>
                        <pre className="text-xs text-green-400 font-mono max-h-32 overflow-y-auto">
                          {logs[project.id].join('\n')}
                        </pre>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {/* 预置服务 */}
      {activeTab === 'services' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map(service => (
            <div key={service.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition cursor-pointer"
              onClick={() => {
                setNewProject({ ...newProject, service_id: service.id })
                setShowCreate(true)
              }}
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Database className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{service.name}</h3>
                  <p className="text-xs text-gray-500">{service.image}</p>
                </div>
              </div>
              <p className="text-sm text-gray-600 mb-3">{service.description}</p>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Terminal className="w-3 h-3" />
                <span>端口: {service.ports.join(', ')}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 镜像管理 */}
      {activeTab === 'images' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-900 mb-4">拉取新镜像</h3>
            <div className="flex gap-3">
              <input
                type="text"
                value={pullImage}
                onChange={e => setPullImage(e.target.value)}
                placeholder="输入镜像名称，如 redis:7-alpine"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                onKeyPress={e => e.key === 'Enter' && pullImageHandler()}
              />
              <button
                onClick={pullImageHandler}
                disabled={pulling}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {pulling ? '拉取中...' : '拉取'}
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">本地镜像</h3>
              <button onClick={fetchImages} className="text-sm text-purple-600 hover:text-purple-700">
                <RefreshCw className="w-4 h-4 inline" /> 刷新
              </button>
            </div>
            {images.length === 0 ? (
              <p className="text-gray-500 text-center py-8">暂无本地镜像</p>
            ) : (
              <div className="space-y-2">
                {images.map((img, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <span className="font-mono text-sm">{img.tag || img.id}</span>
                      <span className="text-xs text-gray-500 ml-2">{img.id}</span>
                    </div>
                    <span className="text-xs text-gray-500">{img.created}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 新建项目弹窗 */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">新建沙箱项目</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">项目名称 *</label>
                <input
                  type="text"
                  value={newProject.name}
                  onChange={e => setNewProject({ ...newProject, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                  placeholder="输入项目名称"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">服务模板</label>
                <select
                  value={newProject.service_id}
                  onChange={e => setNewProject({ ...newProject, service_id: e.target.value, image: '', ports: '' })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                >
                  <option value="">自定义镜像</option>
                  {services.map(s => (
                    <option key={s.id} value={s.id}>{s.name} ({s.image})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">镜像名称</label>
                <input
                  type="text"
                  value={newProject.image}
                  onChange={e => setNewProject({ ...newProject, image: e.target.value, service_id: '' })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none font-mono"
                  placeholder="如: redis:7-alpine"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">端口映射</label>
                <input
                  type="text"
                  value={newProject.ports}
                  onChange={e => setNewProject({ ...newProject, ports: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none font-mono"
                  placeholder="如: 6379:6379, 8080:80"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">环境变量</label>
                <textarea
                  value={newProject.env}
                  onChange={e => setNewProject({ ...newProject, env: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none font-mono"
                  rows="3"
                  placeholder="每行一个，如: POSTGRES_PASSWORD=password"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={newProject.description}
                  onChange={e => setNewProject({ ...newProject, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                  rows="2"
                  placeholder="项目描述"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                取消
              </button>
              <button
                onClick={createProject}
                disabled={creating}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {creating ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}