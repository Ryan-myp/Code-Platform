import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { 
  Database, Plus, Trash2, Edit2, Search, 
  FileText, FolderOpen, Globe, Upload, Download,
  RefreshCw, ChevronDown, ChevronRight, AlertCircle
} from 'lucide-react'

const API = 'http://localhost:8888'

export default function KnowledgeBasesPage() {
  const [items, setItems] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [formData, setFormData] = useState({ name: '', description: '', source_type: 'local', source_path: '' })
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedKB, setExpandedKB] = useState(null)
  const [kbFiles, setKbFiles] = useState([])
  const [error, setError] = useState(null)

  const loadData = async () => {
    try {
      const token = localStorage.getItem('token')
      const res = await axios.get(`${API}/api/knowledge-bases`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setItems(res.data)
      setError(null)
    } catch (err) {
      console.error('加载知识库失败', err)
      setError('加载失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const filteredItems = items.filter(item =>
    item.name?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleSubmit = async () => {
    if (!formData.name.trim()) return
    const token = localStorage.getItem('token')
    try {
      if (editingItem) {
        await axios.put(`${API}/api/knowledge-bases/${editingItem.id}`, formData, {
          headers: { Authorization: `Bearer ${token}` }
        })
      } else {
        await axios.post(`${API}/api/knowledge-bases`, formData, {
          headers: { Authorization: `Bearer ${token}` }
        })
      }
      setShowForm(false)
      setEditingItem(null)
      setFormData({ name: '', description: '', source_type: 'local', source_path: '' })
      loadData()
    } catch (err) {
      alert('保存失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除此知识库？')) return
    const token = localStorage.getItem('token')
    try {
      await axios.delete(`${API}/api/knowledge-bases/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      loadData()
    } catch (err) {
      alert('删除失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const toggleExpand = async (id) => {
    if (expandedKB === id) {
      setExpandedKB(null)
      setKbFiles([])
    } else {
      setExpandedKB(id)
      // Load mock files
      setKbFiles([
        { name: 'document1.pdf', type: 'pdf', size: '2.3 MB' },
        { name: 'document2.docx', type: 'doc', size: '1.5 MB' },
        { name: 'specification.md', type: 'md', size: '15 KB' },
      ])
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin w-8 h-8 text-purple-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">知识库管理</h1>
          <p className="text-gray-500 mt-1">管理文档知识库，为 Agent 提供知识检索能力</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
        >
          <Plus className="w-4 h-4" />
          <span>新建知识库</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总知识库', value: items.length, icon: Database, color: 'from-violet-500 to-purple-600' },
          { label: '文档总数', value: items.reduce((acc, item) => acc + (item.file_count || 0), 0), icon: FileText, color: 'from-emerald-500 to-green-600' },
          { label: '总大小', value: `${(items.reduce((acc, item) => acc + (item.size_mb || 0), 0)).toFixed(1)} MB`, icon: FolderOpen, color: 'from-blue-500 to-cyan-600' },
          { label: '索引状态', value: items.filter(i => i.status === 'indexed').length, icon: Globe, color: 'from-orange-500 to-amber-600' },
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

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Search */}
      <div className="bg-white rounded-2xl border border-gray-200 p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索知识库..."
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500"
          />
        </div>
      </div>

      {/* Knowledge Bases List */}
      {filteredItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
          <Database className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无知识库</h3>
          <p className="text-gray-500 mb-6">创建一个知识库来存储和管理文档</p>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
          >
            <Plus className="w-4 h-4" />
            新建知识库
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredItems.map(item => (
            <div key={item.id} className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="p-5 flex items-center gap-4">
                <button
                  onClick={() => toggleExpand(item.id)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  {expandedKB === item.id ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                </button>
                
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                  <Database className="w-6 h-6 text-white" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-gray-900">{item.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      item.status === 'indexed' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-700'
                    }`}>
                      {item.status === 'indexed' ? '已索引' : '索引中'}
                    </span>
                  </div>
                  {item.description && (
                    <p className="text-sm text-gray-500 mt-1">{item.description}</p>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                    <span className="flex items-center gap-1"><FolderOpen className="w-3 h-3" />{item.file_count || 0} 文件</span>
                    <span className="flex items-center gap-1"><Globe className="w-3 h-3" />{item.source_type || 'local'}</span>
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <button className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg">
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={() => handleDelete(item.id)}
                    className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              
              {/* Expanded Files */}
              {expandedKB === item.id && (
                <div className="border-t border-gray-100 p-5 bg-gray-50">
                  <h4 className="font-medium text-gray-900 mb-3">文档列表</h4>
                  <div className="space-y-2">
                    {kbFiles.map((file, idx) => (
                      <div key={idx} className="flex items-center gap-3 p-3 bg-white rounded-xl">
                        <FileText className="w-5 h-5 text-gray-400" />
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">{file.name}</p>
                          <p className="text-xs text-gray-500">{file.size}</p>
                        </div>
                        <button className="p-2 hover:bg-gray-100 rounded-lg">
                          <Download className="w-4 h-4 text-gray-400" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">{editingItem ? '编辑知识库' : '新建知识库'}</h2>
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
                  placeholder="例如：技术文档库"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">来源类型</label>
                <select
                  value={formData.source_type}
                  onChange={(e) => setFormData({...formData, source_type: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500"
                >
                  <option value="local">本地文件</option>
                  <option value="url">URL</option>
                  <option value="api">API</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">来源路径</label>
                <input
                  type="text"
                  value={formData.source_path}
                  onChange={(e) => setFormData({...formData, source_path: e.target.value})}
                  placeholder="/path/to/documents"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  rows={3}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl">
                取消
              </button>
              <button onClick={handleSubmit} className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700">
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
