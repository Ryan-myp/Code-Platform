import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { BookOpen, FileText, Cpu, Settings, Plus, Edit2, Trash2, X, FolderOpen, Globe, Zap } from 'lucide-react'

const API = 'http://localhost:8888'

export default function ResourcesPage() {
  const [activeTab, setActiveTab] = useState('knowledge')
  const [knowledgeBases, setKnowledgeBases] = useState([])
  const [skills, setSkills] = useState([])
  const [mcpServers, setMcpServers] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [formData, setFormData] = useState({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadData()
  }, [activeTab])

  const loadData = async () => {
    try {
      if (activeTab === 'knowledge') {
        const res = await axios.get(`${API}/api/knowledge-bases`)
        setKnowledgeBases(res.data)
      } else if (activeTab === 'skills') {
        const res = await axios.get(`${API}/api/skills`)
        setSkills(res.data)
      } else {
        const res = await axios.get(`${API}/api/mcp-servers`)
        setMcpServers(res.data)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      if (activeTab === 'knowledge') {
        if (editingItem) {
          await axios.put(`${API}/api/knowledge-bases/${editingItem.id}`, formData)
        } else {
          await axios.post(`${API}/api/knowledge-bases`, formData)
        }
      } else if (activeTab === 'skills') {
        if (editingItem) {
          await axios.put(`${API}/api/skills/${editingItem.id}`, formData)
        } else {
          await axios.post(`${API}/api/skills`, formData)
        }
      } else {
        if (editingItem) {
          await axios.put(`${API}/api/mcp-servers/${editingItem.id}`, formData)
        } else {
          await axios.post(`${API}/api/mcp-servers`, formData)
        }
      }
      setShowForm(false)
      setEditingItem(null)
      setFormData({})
      loadData()
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      if (activeTab === 'knowledge') {
        await axios.delete(`${API}/api/knowledge-bases/${id}`)
      } else if (activeTab === 'skills') {
        await axios.delete(`${API}/api/skills/${id}`)
      } else {
        await axios.delete(`${API}/api/mcp-servers/${id}`)
      }
      loadData()
    } catch (err) {
      console.error(err)
    }
  }

  const tabs = [
    { key: 'knowledge', label: '知识库', icon: BookOpen },
    { key: 'skills', label: 'Skills', icon: FileText },
    { key: 'mcp', label: 'MCP Server', icon: Cpu },
  ]

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-purple-600 to-indigo-700 rounded-2xl shadow-lg mb-6">
            <Settings className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight mb-3">资源管理</h1>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">管理知识库、Skills 和 MCP Server — 为 Agent 提供外部能力扩展</p>
        </div>

        {/* Tabs */}
        <div className="flex space-x-2 mb-8 justify-center">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center px-6 py-3 rounded-xl font-medium transition-all duration-200 ${
                activeTab === tab.key
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              <tab.icon className="w-5 h-5 mr-2" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Action Bar */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            {activeTab === 'knowledge' ? '知识库列表' : activeTab === 'skills' ? 'Skills 列表' : 'MCP Server 列表'}
          </h2>
          <button
            onClick={() => { setShowForm(true); setEditingItem(null); setFormData({}); }}
            className="flex items-center px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 font-bold transition-all shadow-lg hover:shadow-xl"
          >
            <Plus className="w-5 h-5 mr-2" />
            新建{activeTab === 'knowledge' ? '知识库' : activeTab === 'skills' ? 'Skill' : 'MCP Server'}
          </button>
        </div>

        {/* Form Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10">
                <h3 className="text-xl font-bold">
                  {editingItem ? '编辑' : '新建'}{activeTab === 'knowledge' ? '知识库' : activeTab === 'skills' ? 'Skill' : 'MCP Server'}
                </h3>
                <button onClick={() => setShowForm(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6 space-y-4">
                {activeTab === 'knowledge' && (
                  <>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">名称 *</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：产品文档库" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">类型</label>
                      <select className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.type || 'file'} onChange={e => setFormData({...formData, type: e.target.value})}>
                        <option value="file">文件目录</option>
                        <option value="web">网页 URL</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">路径 / URL</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.path || ''} onChange={e => setFormData({...formData, path: e.target.value})} placeholder="/path/to/documents" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">过滤条件</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.filter || ''} onChange={e => setFormData({...formData, filter: e.target.value})} placeholder="*.md, *.pdf" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">Top K</label>
                      <input type="number" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.top_k || 5} onChange={e => setFormData({...formData, top_k: parseInt(e.target.value)})} />
                    </div>
                  </>
                )}
                {activeTab === 'skills' && (
                  <>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">名称 *</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：代码审查员" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">描述</label>
                      <textarea className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 h-24 resize-none"
                        value={formData.description || ''} onChange={e => setFormData({...formData, description: e.target.value})} placeholder="Skill 的描述..." />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">内容 / Prompt *</label>
                      <textarea className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 h-48 resize-none font-mono text-sm"
                        value={formData.content || ''} onChange={e => setFormData({...formData, content: e.target.value})} placeholder="输入 Skill 的指令内容..." />
                    </div>
                  </>
                )}
                {activeTab === 'mcp' && (
                  <>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">名称 *</label>
                      <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：GitHub MCP" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">传输类型</label>
                      <select className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                        value={formData.transport_type || 'stdio'} onChange={e => setFormData({...formData, transport_type: e.target.value})}>
                        <option value="stdio">stdio (本地命令)</option>
                        <option value="sse">SSE (HTTP 流式)</option>
                      </select>
                    </div>
                    {formData.transport_type === 'stdio' && (
                      <>
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">命令</label>
                          <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                            value={formData.command || ''} onChange={e => setFormData({...formData, command: e.target.value})} placeholder="npx @modelcontextprotocol/server-github" />
                        </div>
                        <div>
                          <label className="block text-sm font-semibold text-gray-700 mb-2">参数 (JSON 数组)</label>
                          <textarea className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 font-mono text-sm"
                            value={formData.args ? JSON.stringify(formData.args, null, 2) : '[]'} 
                            onChange={e => { try { setFormData({...formData, args: JSON.parse(e.target.value)}) } catch {}}}
                            rows={3} />
                        </div>
                      </>
                    )}
                    {formData.transport_type === 'sse' && (
                      <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">URL</label>
                        <input type="text" className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                          value={formData.url || ''} onChange={e => setFormData({...formData, url: e.target.value})} placeholder="http://localhost:3001/sse" />
                      </div>
                    )}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">环境变量 (JSON 对象)</label>
                      <textarea className="w-full p-3 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10 font-mono text-sm"
                        value={formData.env ? JSON.stringify(formData.env, null, 2) : '{}'} 
                        onChange={e => { try { setFormData({...formData, env: JSON.parse(e.target.value)}) } catch {}}}
                        rows={3} />
                    </div>
                  </>
                )}

                <div className="flex space-x-3 pt-4">
                  <button onClick={() => setShowForm(false)} className="flex-1 px-6 py-3 border border-gray-300 rounded-xl hover:bg-gray-50 font-medium">取消</button>
                  <button onClick={handleSubmit} disabled={loading} className="flex-1 px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 font-bold flex items-center justify-center">
                    {loading ? '保存中...' : '保存'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* List */}
        <div className="space-y-4">
          {(activeTab === 'knowledge' ? knowledgeBases : activeTab === 'skills' ? skills : mcpServers).length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-gray-100">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                {activeTab === 'knowledge' ? <FolderOpen className="w-8 h-8 text-gray-400" /> : activeTab === 'skills' ? <FileText className="w-8 h-8 text-gray-400" /> : <Cpu className="w-8 h-8 text-gray-400" />}
              </div>
              <p className="text-gray-500 text-lg">暂无数据，点击"新建"开始创建</p>
            </div>
          ) : (
            (activeTab === 'knowledge' ? knowledgeBases : activeTab === 'skills' ? skills : mcpServers).map(item => (
              <div key={item.id} className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-lg text-sm font-bold">
                        {activeTab === 'knowledge' ? 'KB' : activeTab === 'skills' ? 'SKILL' : 'MCP'}
                      </span>
                      <h3 className="text-xl font-bold text-gray-900">{item.name}</h3>
                    </div>
                    {item.description && <p className="text-gray-600 mb-2">{item.description}</p>}
                    {activeTab === 'knowledge' && (
                      <div className="flex flex-wrap gap-2 text-sm text-gray-500">
                        <span className="flex items-center"><FolderOpen className="w-4 h-4 mr-1" />{item.type === 'web' ? item.url : item.path}</span>
                        <span>Top K: {item.top_k}</span>
                      </div>
                    )}
                    {activeTab === 'skills' && (
                      <div className="flex flex-wrap gap-2 text-sm text-gray-500">
                        <span className="line-clamp-2">{item.content}</span>
                      </div>
                    )}
                    {activeTab === 'mcp' && (
                      <div className="flex flex-wrap gap-2 text-sm text-gray-500">
                        <span className="flex items-center"><Zap className="w-4 h-4 mr-1" />{item.transport_type}</span>
                        {item.command && <span>命令: {item.command}</span>}
                        {item.url && <span>URL: {item.url}</span>}
                      </div>
                    )}
                  </div>
                  <div className="flex space-x-2">
                    <button onClick={() => { setEditingItem(item); setFormData(item); setShowForm(true); }}
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                      <Edit2 className="w-4 h-4 text-gray-600" />
                    </button>
                    <button onClick={() => handleDelete(item.id)}
                      className="p-2 hover:bg-red-50 rounded-lg transition-colors">
                      <Trash2 className="w-4 h-4 text-red-600" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
