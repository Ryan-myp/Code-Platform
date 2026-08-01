import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { 
  Server, Plus, Trash2, Edit2, Save, X, Search, 
  Terminal, Globe, Activity, CheckCircle, XCircle,
  RefreshCw, Play, Square, Wifi, WifiOff
} from 'lucide-react'

const API = 'http://localhost:8888'

// MCP 服务器卡片组件
function MCPServerCard({ server, onEdit, onDelete, onToggle }) {
  const isActive = server.status === 'active'
  
  return (
    <div className={`bg-white rounded-2xl border p-5 transition-all hover:shadow-md ${
      isActive ? 'border-emerald-200 bg-emerald-50/30' : 'border-gray-200'
    }`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isActive ? 'bg-gradient-to-br from-emerald-500 to-green-600' : 'bg-gradient-to-br from-gray-400 to-gray-500'
          }`}>
            <Server className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{server.name}</h3>
            <span className={`inline-flex items-center gap-1 text-xs ${
              isActive ? 'text-emerald-600' : 'text-gray-500'
            }`}>
              {isActive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {isActive ? '已连接' : '未连接'}
            </span>
          </div>
        </div>
        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg text-xs font-mono">
          {server.transport || 'stdio'}
        </span>
      </div>
      
      <div className="space-y-2 text-sm text-gray-600 mb-4">
        <p className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-gray-400" />
          <span className="font-mono text-xs truncate">{server.command}</span>
        </p>
        {server.url && (
          <p className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-gray-400" />
            <span className="text-xs truncate">{server.url}</span>
          </p>
        )}
      </div>
      
      <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
        <button
          onClick={() => onToggle(server.id)}
          className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
            isActive 
              ? 'bg-red-50 text-red-600 hover:bg-red-100' 
              : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
          }`}
        >
          {isActive ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          {isActive ? '停止' : '启动'}
        </button>
        <button 
          onClick={() => onEdit(server)}
          className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-xl"
        >
          <Edit2 className="w-4 h-4" />
        </button>
        <button 
          onClick={() => onDelete(server.id)}
          className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-xl"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

export default function MCPServersPage() {
  const [items, setItems] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [formData, setFormData] = useState({ 
    name: '', command: '', args: '', url: '', transport: 'stdio' 
  })
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')

  const loadData = async () => {
    try {
      const token = localStorage.getItem('token')
      const res = await axios.get(`${API}/api/mcp-servers`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setItems(res.data)
    } catch (err) {
      console.error('加载 MCP 服务器失败', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const filteredItems = items.filter(item =>
    item.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.command?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleSubmit = async () => {
    if (!formData.name?.trim()) return
    const token = localStorage.getItem('token')
    try {
      const payload = {
        name: formData.name,
        command: formData.command,
        args: formData.args,
        url: formData.url,
        transport: formData.transport
      }
      if (editingItem) {
        await axios.put(`${API}/api/mcp-servers/${editingItem.id}`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        })
      } else {
        await axios.post(`${API}/api/mcp-servers`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        })
      }
      setShowForm(false)
      setEditingItem(null)
      setFormData({ name: '', command: '', args: '', url: '', transport: 'stdio' })
      loadData()
    } catch (err) {
      alert('保存失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除此 MCP 服务器？')) return
    const token = localStorage.getItem('token')
    try {
      await axios.delete(`${API}/api/mcp-servers/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      loadData()
    } catch (err) {
      alert('删除失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleToggle = async (id) => {
    const token = localStorage.getItem('token')
    try {
      await axios.post(`${API}/api/mcp-servers/${id}/toggle`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      loadData()
    } catch (err) {
      alert('操作失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin w-8 h-8 text-orange-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">MCP Servers</h1>
          <p className="text-gray-500 mt-1">管理 Model Context Protocol 服务器，为 Agent 提供外部工具接入能力</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-orange-600 text-white rounded-xl hover:bg-orange-700"
        >
          <Plus className="w-4 h-4" />
          <span>新建 MCP</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总服务器', value: items.length, icon: Server, color: 'from-orange-500 to-red-600' },
          { label: '已连接', value: items.filter(s => s.status === 'active').length, icon: CheckCircle, color: 'from-emerald-500 to-green-600' },
          { label: 'stdio 类型', value: items.filter(s => s.transport === 'stdio').length, icon: Terminal, color: 'from-blue-500 to-cyan-600' },
          { label: 'SSE 类型', value: items.filter(s => s.transport === 'sse').length, icon: Globe, color: 'from-purple-500 to-pink-600' },
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

      {/* Search */}
      <div className="bg-white rounded-2xl border border-gray-200 p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索 MCP 服务器..."
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500"
          />
        </div>
      </div>

      {/* MCP Servers Grid */}
      {filteredItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
          <Server className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无 MCP 服务器</h3>
          <p className="text-gray-500 mb-6">创建一个 MCP 服务器来为 Agent 提供工具接入</p>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-xl hover:bg-orange-700"
          >
            <Plus className="w-4 h-4" />
            新建 MCP 服务器
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {filteredItems.map(item => (
            <MCPServerCard
              key={item.id}
              server={item}
              onEdit={() => {
                setEditingItem(item)
                setFormData({
                  name: item.name,
                  command: item.command,
                  args: item.args || '',
                  url: item.url || '',
                  transport: item.transport || 'stdio'
                })
                setShowForm(true)
              }}
              onDelete={handleDelete}
              onToggle={handleToggle}
            />
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">{editingItem ? '编辑 MCP 服务器' : '新建 MCP 服务器'}</h2>
              <button onClick={() => setShowForm(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  placeholder="例如：文件系统 MCP"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">传输类型</label>
                <select
                  value={formData.transport}
                  onChange={(e) => setFormData({...formData, transport: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500"
                >
                  <option value="stdio">stdio (标准输入输出)</option>
                  <option value="sse">SSE (Server-Sent Events)</option>
                </select>
              </div>
              {formData.transport === 'stdio' ? (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">命令 *</label>
                    <input
                      type="text"
                      value={formData.command}
                      onChange={(e) => setFormData({...formData, command: e.target.value})}
                      placeholder="例如：npx"
                      className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">参数</label>
                    <input
                      type="text"
                      value={formData.args}
                      onChange={(e) => setFormData({...formData, args: e.target.value})}
                      placeholder="例如：-y @modelcontextprotocol/server-filesystem /path/to/files"
                      className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500"
                    />
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">URL *</label>
                  <input
                    type="text"
                    value={formData.url}
                    onChange={(e) => setFormData({...formData, url: e.target.value})}
                    placeholder="例如：http://localhost:3001/sse"
                    className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500"
                  />
                </div>
              )}
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl">
                取消
              </button>
              <button onClick={handleSubmit} className="px-4 py-2 bg-orange-600 text-white rounded-xl hover:bg-orange-700">
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
