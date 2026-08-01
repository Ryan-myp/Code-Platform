import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Server, Plus, Trash2, Edit2, Save, X, Search, Terminal, Globe, Activity, Calendar, CheckCircle, XCircle } from 'lucide-react'

const API = 'http://localhost:8888'

export default function MCPServersPage() {
  const [items, setItems] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [formData, setFormData] = useState({})
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const res = await axios.get(`${API}/api/mcp-servers`)
      setItems(res.data)
    } catch (err) { console.error(err) }
  }

  const handleSubmit = async () => {
    if (!formData.name?.trim()) return alert('名称不能为空')
    setLoading(true)
    try {
      if (editingItem) {
        await axios.put(`${API}/api/mcp-servers/${editingItem.id}`, formData)
      } else {
        await axios.post(`${API}/api/mcp-servers`, formData)
      }
      setShowForm(false)
      setEditingItem(null)
      setFormData({})
      loadData()
    } catch (err) { console.error(err); alert('保存失败') }
    finally { setLoading(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除？')) return
    try {
      await axios.delete(`${API}/api/mcp-servers/${id}`)
      loadData()
    } catch (err) { console.error(err) }
  }

  const filteredItems = items.filter(item => 
    item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.command?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const getTransportBadge = (type) => {
    switch(type) {
      case 'sse': return <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-medium">SSE</span>
      default: return <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">stdio</span>
    }
  }

  const getStatusIcon = (server) => {
    // Mock status - in real app would check actual connection
    return <CheckCircle className="w-4 h-4 text-green-500" />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50/30">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-10 h-10 bg-gradient-to-br from-orange-600 to-red-600 rounded-xl flex items-center justify-center shadow-lg">
              <Server className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">MCP Servers 管理</h1>
          </div>
          <p className="text-gray-500 ml-13">管理 Model Context Protocol 服务器，为 Agent 提供外部工具接入能力</p>
        </div>

        {/* Toolbar */}
        <div className="flex justify-between items-center mb-6">
          <div className="relative flex-1 max-w-md mr-4">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索 MCP Servers..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10"
            />
          </div>
          <button
            onClick={() => { setShowForm(true); setEditingItem(null); setFormData({ transport_type: 'stdio', args: [], env: {} }); }}
            className="flex items-center px-4 py-2 bg-gradient-to-r from-orange-600 to-red-600 text-white rounded-lg hover:from-orange-700 hover:to-red-700 font-medium transition-all shadow-sm"
          >
            <Plus className="w-4 h-4 mr-2" />
            新建 MCP Server
          </button>
        </div>

        {/* List */}
        <div className="space-y-4">
          {filteredItems.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-xl border border-gray-100 shadow-sm">
              <Server className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">暂无 MCP Servers</p>
              <p className="text-gray-400 text-sm mt-1">点击"新建 MCP Server"开始添加</p>
            </div>
          ) : (
            filteredItems.map(server => (
              <div key={server.id} className="bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow overflow-hidden">
                <div className="p-5">
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-orange-50 rounded-lg flex items-center justify-center">
                        <Server className="w-5 h-5 text-orange-600" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="font-semibold text-gray-900">{server.name}</h3>
                          {getTransportBadge(server.transport_type)}
                          {getStatusIcon(server)}
                        </div>
                        <div className="flex items-center space-x-2 mt-1">
                          {server.command && (
                            <span className="text-xs text-gray-500 flex items-center font-mono">
                              <Terminal className="w-3 h-3 mr-1" />
                              {server.command}
                            </span>
                          )}
                          {server.url && (
                            <span className="text-xs text-gray-500 flex items-center">
                              <Globe className="w-3 h-3 mr-1" />
                              {server.url}
                            </span>
                          )}
                          {server.created_at && (
                            <span className="text-xs text-gray-400 flex items-center">
                              <Calendar className="w-3 h-3 mr-1" />
                              {new Date(server.created_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex space-x-1">
                      <button onClick={() => { setEditingItem(server); setFormData({...server, args: server.args || [], env: server.env || {}}); setShowForm(true); }}
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors" title="编辑">
                        <Edit2 className="w-4 h-4 text-gray-600" />
                      </button>
                      <button onClick={() => handleDelete(server.id)}
                        className="p-2 hover:bg-red-50 rounded-lg transition-colors" title="删除">
                        <Trash2 className="w-4 h-4 text-red-600" />
                      </button>
                    </div>
                  </div>
                  
                  {/* Config Details */}
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    {server.args && server.args.length > 0 && (
                      <div>
                        <span className="text-gray-500">参数：</span>
                        <code className="bg-gray-50 px-2 py-1 rounded text-xs font-mono">{JSON.stringify(server.args)}</code>
                      </div>
                    )}
                    {server.env && Object.keys(server.env).length > 0 && (
                      <div>
                        <span className="text-gray-500">环境变量：</span>
                        <code className="bg-gray-50 px-2 py-1 rounded text-xs font-mono">{JSON.stringify(server.env)}</code>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10">
              <h3 className="text-lg font-semibold">{editingItem ? '编辑 MCP Server' : '新建 MCP Server'}</h3>
              <button onClick={() => setShowForm(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10"
                  value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：文件系统、GitHub" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">传输类型</label>
                <select className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10"
                  value={formData.transport_type || 'stdio'} onChange={e => setFormData({...formData, transport_type: e.target.value})}>
                  <option value="stdio">stdio（本地命令）</option>
                  <option value="sse">SSE（HTTP 端点）</option>
                </select>
              </div>
              
              {formData.transport_type === 'stdio' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">命令</label>
                    <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 font-mono text-sm"
                      value={formData.command || ''} onChange={e => setFormData({...formData, command: e.target.value})} placeholder="python3" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">参数（JSON 数组）</label>
                    <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 font-mono text-sm"
                      value={JSON.stringify(formData.args || [])} onChange={e => {try {setFormData({...formData, args: JSON.parse(e.target.value)})} catch(err) {}}} placeholder='["server.py"]' />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">环境变量（JSON 对象）</label>
                    <textarea className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10 font-mono text-sm h-20 resize-none"
                      value={JSON.stringify(formData.env || {}, null, 2)} onChange={e => {try {setFormData({...formData, env: JSON.parse(e.target.value)})} catch(err) {}}} placeholder='{"KEY": "value"}' />
                  </div>
                </>
              )}
              
              {formData.transport_type === 'sse' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
                  <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-orange-500 focus:ring-2 focus:ring-orange-500/10"
                    value={formData.url || ''} onChange={e => setFormData({...formData, url: e.target.value})} placeholder="https://mcp-server.example.com/sse" />
                </div>
              )}
            </div>
            <div className="p-5 border-t border-gray-100 flex space-x-3 sticky bottom-0 bg-white">
              <button onClick={() => setShowForm(false)} className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium">取消</button>
              <button onClick={handleSubmit} disabled={loading} className="flex-1 px-4 py-2 bg-gradient-to-r from-orange-600 to-red-600 text-white rounded-lg hover:from-orange-700 hover:to-red-700 disabled:opacity-50 font-medium flex items-center justify-center">
                {loading ? '保存中...' : <><Save className="w-4 h-4 mr-2" />保存</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
