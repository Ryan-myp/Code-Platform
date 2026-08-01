import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Database, Plus, Trash2, Edit2, Save, X, FolderOpen, Link, Search, FileText, Globe, File, Upload, Download, FileCode, Image, FileJson, Terminal, BookOpen, ChevronDown, ChevronRight } from 'lucide-react'

const API = 'http://localhost:8888'

export default function KnowledgeBasesPage() {
  const [items, setItems] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [formData, setFormData] = useState({})
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedKB, setExpandedKB] = useState(null)
  const [kbFiles, setKbFiles] = useState([])
  const [uploading, setUploading] = useState(false)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const res = await axios.get(`${API}/api/knowledge-bases`)
      setItems(res.data)
    } catch (err) { console.error(err) }
  }

  const loadKBFiles = async (item) => {
    // Mock files for demonstration - in real app would fetch from backend
    const mockFiles = [
      { name: 'document1.pdf', type: 'pdf', size: '2.3 MB' },
      { name: 'document2.docx', type: 'doc', size: '1.5 MB' },
      { name: 'specification.md', type: 'md', size: '15 KB' },
    ]
    setKbFiles(mockFiles)
    setExpandedKB(item.id)
  }

  const handleSubmit = async () => {
    if (!formData.name?.trim()) return alert('名称不能为空')
    setLoading(true)
    try {
      if (editingItem) {
        await axios.put(`${API}/api/knowledge-bases/${editingItem.id}`, formData)
      } else {
        await axios.post(`${API}/api/knowledge-bases`, formData)
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
      await axios.delete(`${API}/api/knowledge-bases/${id}`)
      loadData()
    } catch (err) { console.error(err) }
  }

  const toggleExpand = (id) => {
    if (expandedKB === id) {
      setExpandedKB(null)
      setKbFiles([])
    } else {
      const item = items.find(i => i.id === id)
      if (item) loadKBFiles(item)
    }
  }

  const handleFileUpload = async (e, kbId) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    
    setUploading(true)
    try {
      // In real implementation, upload files to backend
      // For now, just show a success message
      alert(`成功上传 ${files.length} 个文件`)
      loadData()
    } catch (err) {
      console.error(err)
      alert('上传失败')
    } finally {
      setUploading(false)
    }
  }

  const filteredItems = items.filter(item => 
    item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.description?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const getTypeIcon = (type) => {
    switch(type) {
      case 'web': return <Globe className="w-4 h-4" />
      case 'pdf': return <FileText className="w-4 h-4" />
      default: return <FolderOpen className="w-4 h-4" />
    }
  }

  const getTypeLabel = (type) => {
    switch(type) {
      case 'web': return '网页'
      case 'pdf': return 'PDF'
      default: return '文件'
    }
  }

  const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase()
    switch(ext) {
      case 'pdf': return FileText
      case 'doc': case 'docx': return FileCode
      case 'md': return BookOpen
      case 'json': return FileJson
      case 'py': return Terminal
      case 'png': case 'jpg': case 'svg': return Image
      default: return File
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
              <Database className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">知识库管理</h1>
          </div>
          <p className="text-gray-500 ml-13">为 Agent 配置知识来源，支持本地文件、网页和 PDF，可直接上传文件</p>
        </div>

        {/* Toolbar */}
        <div className="flex justify-between items-center mb-6">
          <div className="relative flex-1 max-w-md mr-4">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索知识库..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
            />
          </div>
          <button
            onClick={() => { setShowForm(true); setEditingItem(null); setFormData({ type: 'file', top_k: 5 }); }}
            className="flex items-center px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:from-blue-700 hover:to-indigo-700 font-medium transition-all shadow-sm"
          >
            <Plus className="w-4 h-4 mr-2" />
            新建知识库
          </button>
        </div>

        {/* List */}
        <div className="space-y-3">
          {filteredItems.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-xl border border-gray-100 shadow-sm">
              <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">暂无知识库</p>
              <p className="text-gray-400 text-sm mt-1">点击"新建知识库"开始添加</p>
            </div>
          ) : (
            filteredItems.map(item => (
              <div key={item.id} className="bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow overflow-hidden">
                <div className="p-5">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <button onClick={() => toggleExpand(item.id)} className="hover:bg-gray-100 rounded p-1">
                          {expandedKB === item.id ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                        </button>
                        <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
                          {getTypeIcon(item.type)}
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">{item.name}</h3>
                          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">{getTypeLabel(item.type)}</span>
                        </div>
                      </div>
                      {item.description && <p className="text-sm text-gray-600 mb-1 ml-11">{item.description}</p>}
                      <div className="flex items-center space-x-4 text-xs text-gray-400 ml-11">
                        {item.path && <span className="flex items-center"><FolderOpen className="w-3 h-3 mr-1" />{item.path}</span>}
                        {item.url && <span className="flex items-center"><Link className="w-3 h-3 mr-1" />{item.url}</span>}
                        {item.top_k !== undefined && <span>Top K: {item.top_k}</span>}
                        {item.created_at && <span>{new Date(item.created_at).toLocaleDateString()}</span>}
                      </div>
                    </div>
                    <div className="flex space-x-1">
                      <button onClick={() => { setEditingItem(item); setFormData(item); setShowForm(true); }}
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors" title="编辑">
                        <Edit2 className="w-4 h-4 text-gray-600" />
                      </button>
                      <button onClick={() => handleDelete(item.id)}
                        className="p-2 hover:bg-red-50 rounded-lg transition-colors" title="删除">
                        <Trash2 className="w-4 h-4 text-red-600" />
                      </button>
                    </div>
                  </div>

                  {/* Expanded file list */}
                  {expandedKB === item.id && (
                    <div className="mt-4 ml-11 pt-4 border-t border-gray-100">
                      <div className="flex justify-between items-center mb-3">
                        <h4 className="font-medium text-gray-900">文件列表</h4>
                        <label className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-sm cursor-pointer hover:bg-blue-100 transition-colors">
                          <Upload className="w-4 h-4 inline mr-1" />
                          上传文件
                          <input type="file" multiple className="hidden" onChange={(e) => handleFileUpload(e, item.id)} disabled={uploading} />
                        </label>
                      </div>
                      
                      {kbFiles.length === 0 ? (
                        <div className="text-center py-8 bg-gray-50 rounded-lg">
                          <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                          <p className="text-gray-500 text-sm">暂无文件</p>
                          <p className="text-gray-400 text-xs mt-1">点击"上传文件"添加知识文档</p>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {kbFiles.map((file, idx) => (
                            <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                              <div className="flex items-center space-x-3">
                                {getFileIcon(file.name)}
                                <div>
                                  <p className="text-sm font-medium text-gray-900">{file.name}</p>
                                  <p className="text-xs text-gray-500">{file.size}</p>
                                </div>
                              </div>
                              <div className="flex space-x-1">
                                <button className="p-1.5 hover:bg-blue-50 rounded text-gray-500 hover:text-blue-600" title="下载">
                                  <Download className="w-3 h-3" />
                                </button>
                                <button className="p-1.5 hover:bg-red-50 rounded text-gray-500 hover:text-red-600" title="删除">
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
            <div className="p-5 border-b border-gray-100 flex justify-between items-center">
              <h3 className="text-lg font-semibold">{editingItem ? '编辑知识库' : '新建知识库'}</h3>
              <button onClick={() => setShowForm(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                  value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="例如：产品文档库" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                  value={formData.description || ''} onChange={e => setFormData({...formData, description: e.target.value})} placeholder="简要说明用途" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">类型</label>
                <select className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                  value={formData.type || 'file'} onChange={e => setFormData({...formData, type: e.target.value})}>
                  <option value="file">文件目录</option>
                  <option value="web">网页 URL</option>
                  <option value="pdf">PDF 文件</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">路径 / URL</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                  value={formData.path || formData.url || ''} 
                  onChange={e => setFormData({...formData, ...(formData.type === 'web' ? {url: e.target.value} : {path: e.target.value})})} 
                  placeholder={formData.type === 'web' ? 'https://...' : '/path/to/docs'} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Top K（检索条数）</label>
                <input type="number" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                  value={formData.top_k || 5} onChange={e => setFormData({...formData, top_k: parseInt(e.target.value)})} />
              </div>
            </div>
            <div className="p-5 border-t border-gray-100 flex space-x-3">
              <button onClick={() => setShowForm(false)} className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium">取消</button>
              <button onClick={handleSubmit} disabled={loading} className="flex-1 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 font-medium flex items-center justify-center">
                {loading ? '保存中...' : <><Save className="w-4 h-4 mr-2" />保存</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
