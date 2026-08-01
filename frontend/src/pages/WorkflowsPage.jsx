import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { 
  Plus, Edit2, Trash2, Play, Clock, CheckCircle, XCircle, 
  Loader, ArrowRight, Search, Filter, Grid, List as ListIcon,
  Folder, Workflow, Calendar, AlertCircle, Terminal
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [editingWorkflow, setEditingWorkflow] = useState(null)
  const [newWorkflow, setNewWorkflow] = useState({ name: '', description: '' })
  const [editForm, setEditForm] = useState({ name: '', description: '' })
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('grid')
  const [filter, setFilter] = useState('all')
  const navigate = useNavigate()

  const fetchWorkflows = async () => {
    const token = localStorage.getItem('token')
    if (!token) return
    try {
      const res = await axios.get(`${API_BASE}/api/workflows`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setWorkflows(res.data)
    } catch (e) {
      console.error('加载工作流失败', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWorkflows()
  }, [])

  const filteredWorkflows = workflows.filter(w => {
    const matchSearch = w.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                       w.description?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchFilter = filter === 'all' || 
                       (filter === 'active' && w.status === 'active') ||
                       (filter === 'inactive' && w.status === 'inactive')
    return matchSearch && matchFilter
  })

  const createWorkflow = async () => {
    if (!newWorkflow.name.trim()) return
    const token = localStorage.getItem('token')
    try {
      await axios.post(`${API_BASE}/api/workflows`, {
        name: newWorkflow.name,
        description: newWorkflow.description,
        definition: { nodes: [], edges: [] }
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setNewWorkflow({ name: '', description: '' })
      setShowCreate(false)
      fetchWorkflows()
    } catch (e) {
      console.error('创建失败', e)
      alert('创建失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const updateWorkflow = async () => {
    if (!editForm.name.trim() || !editingWorkflow) return
    const token = localStorage.getItem('token')
    try {
      await axios.put(`${API_BASE}/api/workflows/${editingWorkflow.id}`, editForm, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setShowEdit(false)
      setEditingWorkflow(null)
      fetchWorkflows()
    } catch (e) {
      console.error('更新失败', e)
      alert('更新失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const deleteWorkflow = async (id, e) => {
    e.stopPropagation()
    if (!confirm('确定删除此工作流？')) return
    const token = localStorage.getItem('token')
    try {
      await axios.delete(`${API_BASE}/api/workflows/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchWorkflows()
    } catch (e) {
      console.error('删除失败', e)
      alert('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const runWorkflow = async (id, e) => {
    e.stopPropagation()
    const token = localStorage.getItem('token')
    try {
      const res = await axios.post(`${API_BASE}/api/workflows/${id}/run`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      alert(`工作流已提交执行！运行 ID: ${res.data.run_id}`)
    } catch (e) {
      alert('执行失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const openEdit = (workflow) => {
    setEditingWorkflow(workflow)
    setEditForm({ name: workflow.name, description: workflow.description || '' })
    setShowEdit(true)
    setShowCreate(false)
  }

  const openCreate = () => {
    setNewWorkflow({ name: '', description: '' })
    setShowCreate(true)
    setShowEdit(false)
  }

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
          <h1 className="text-2xl font-bold text-gray-900">Workflow 管理</h1>
          <p className="text-gray-500 mt-1">创建工作流，编排多 Agent 协作</p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 text-white rounded-xl hover:bg-purple-700 transition-colors font-medium shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>新建工作流</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总工作流', value: workflows.length, icon: Workflow, color: 'from-violet-500 to-purple-600' },
          { label: '运行中', value: workflows.filter(w => w.status === 'active').length, icon: Play, color: 'from-emerald-500 to-green-600' },
          { label: '已停止', value: workflows.filter(w => w.status === 'inactive').length, icon: XCircle, color: 'from-gray-400 to-gray-500' },
          { label: '今日执行', value: workflows.filter(w => w.last_run?.startsWith(new Date().toISOString().split('T')[0])).length, icon: Clock, color: 'from-blue-500 to-cyan-600' },
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

      {/* Toolbar */}
      <div className="bg-white rounded-2xl border border-gray-200 p-4 flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索工作流..."
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        >
          <option value="all">全部状态</option>
          <option value="active">运行中</option>
          <option value="inactive">已停止</option>
        </select>
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

      {/* Workflow Grid/List */}
      {filteredWorkflows.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
          <Workflow className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无工作流</h3>
          <p className="text-gray-500 mb-6">创建一个工作流来编排多 Agent 协作</p>
          <button
            onClick={openCreate}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
          >
            <Plus className="w-4 h-4" />
            新建工作流
          </button>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredWorkflows.map(workflow => (
            <div
              key={workflow.id}
              className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 cursor-pointer group"
              onClick={() => navigate(`/workflows/${workflow.id}`)}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white font-bold">
                    <Workflow className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{workflow.name}</h3>
                    <p className="text-xs text-gray-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {new Date(workflow.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                  workflow.status === 'active' 
                    ? 'bg-emerald-100 text-emerald-700' 
                    : 'bg-gray-100 text-gray-700'
                }`}>
                  {workflow.status === 'active' ? '运行中' : '已停止'}
                </span>
              </div>
              
              {/* Description */}
              <p className="text-sm text-gray-600 line-clamp-2 mb-4">
                {workflow.description || '暂无描述'}
              </p>
              
              {/* Footer */}
              <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                <span className="text-xs text-gray-500">
                  {workflow.nodes?.length || 0} 个节点
                </span>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => runWorkflow(workflow.id, e)}
                    className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors"
                    title="执行"
                  >
                    <Play className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); openEdit(workflow) }}
                    className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
                    title="编辑"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => deleteWorkflow(workflow.id, e)}
                    className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredWorkflows.map(workflow => (
            <div
              key={workflow.id}
              className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex items-center gap-4 cursor-pointer"
              onClick={() => navigate(`/workflows/${workflow.id}`)}
            >
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white">
                <Workflow className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-gray-900 truncate">{workflow.name}</h3>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    workflow.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-700'
                  }`}>
                    {workflow.status === 'active' ? '运行中' : '已停止'}
                  </span>
                </div>
                <p className="text-sm text-gray-500 truncate">{workflow.description || '暂无描述'}</p>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span className="flex items-center gap-1"><Clock className="w-4 h-4" />{new Date(workflow.created_at).toLocaleDateString()}</span>
                <span className="flex items-center gap-1"><Folder className="w-4 h-4" />{workflow.nodes?.length || 0} 节点</span>
              </div>
              <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                <button
                  onClick={() => runWorkflow(workflow.id, new Event('click'))}
                  className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors"
                  title="执行"
                >
                  <Play className="w-4 h-4" />
                </button>
                <button
                  onClick={() => openEdit(workflow)}
                  className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
                  title="编辑"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteWorkflow(workflow.id, new Event('click'))}
                  className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
                  title="删除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">新建工作流</h2>
              <button onClick={() => setShowCreate(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  value={newWorkflow.name}
                  onChange={(e) => setNewWorkflow({...newWorkflow, name: e.target.value})}
                  placeholder="例如：代码审查工作流"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={newWorkflow.description}
                  onChange={(e) => setNewWorkflow({...newWorkflow, description: e.target.value})}
                  rows={3}
                  placeholder="简要描述工作流的用途"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl"
              >
                取消
              </button>
              <button
                onClick={createWorkflow}
                className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEdit && editingWorkflow && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">编辑工作流</h2>
              <button onClick={() => setShowEdit(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm({...editForm, description: e.target.value})}
                  rows={3}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowEdit(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl"
              >
                取消
              </button>
              <button
                onClick={updateWorkflow}
                className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
