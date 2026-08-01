import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Plus, Edit2, Trash2, Play, Clock, CheckCircle, XCircle, Loader, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newWorkflow, setNewWorkflow] = useState({ name: '', description: '' })
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
    }
  }

  const deleteWorkflow = async (id, e) => {
    e.stopPropagation()
    if (!confirm('确定删除此工作流？')) return
    const token = localStorage.getItem('token')
    await axios.delete(`${API_BASE}/api/workflows/${id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    fetchWorkflows()
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="animate-spin w-8 h-8 text-purple-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflow 管理</h1>
          <p className="text-gray-500 mt-1">创建工作流，编排多 Agent 协作</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
        >
          <Plus className="w-4 h-4" />
          <span>新建工作流</span>
        </button>
      </div>

      {/* 创建表单 */}
      {showCreate && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h3 className="font-semibold text-gray-900">新建工作流</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
              <input
                type="text"
                value={newWorkflow.name}
                onChange={(e) => setNewWorkflow({ ...newWorkflow, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                placeholder="工作流名称"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <input
                type="text"
                value={newWorkflow.description}
                onChange={(e) => setNewWorkflow({ ...newWorkflow, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                placeholder="工作流描述"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={createWorkflow}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
            >
              创建
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 工作流列表 */}
      {workflows.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <div className="text-gray-400 text-5xl mb-4">🔄</div>
          <p className="text-lg font-medium text-gray-900">暂无工作流</p>
          <p className="text-gray-500 mt-1">创建你的第一个工作流，编排 Agent 协作</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {workflows.map(wf => (
            <div
              key={wf.id}
              className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => navigate(`/workflows/${wf.id}`)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900">{wf.name}</h3>
                  <p className="text-sm text-gray-500 mt-1">{wf.description || '暂无描述'}</p>
                </div>
                <ArrowRight className="w-5 h-5 text-gray-400" />
              </div>
              
              <div className="flex items-center gap-4 mt-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(wf.created_at).toLocaleDateString('zh-CN')}
                </span>
              </div>

              <div className="flex gap-2 mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={(e) => runWorkflow(wf.id, e)}
                  className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-green-50 text-green-600 rounded-lg hover:bg-green-100 text-sm"
                >
                  <Play className="w-3 h-3" />
                  执行
                </button>
                <button
                  onClick={(e) => navigate(`/workflows/${wf.id}/edit`)}
                  className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-purple-50 text-purple-600 rounded-lg hover:bg-purple-100 text-sm"
                >
                  <Edit2 className="w-3 h-3" />
                  编辑
                </button>
                <button
                  onClick={(e) => deleteWorkflow(wf.id, e)}
                  className="p-1.5 text-gray-400 hover:text-red-500"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
