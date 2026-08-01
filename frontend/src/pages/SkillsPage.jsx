import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { 
  Wrench, Plus, Trash2, Save, X, Search, Edit2, Eye,
  FolderOpen, FileText, FileCode, Image, Code, RefreshCw,
  ChevronDown, ChevronRight, Upload, Download, Terminal
} from 'lucide-react'

const API = 'http://localhost:8888'

// 技能卡片组件
function SkillCard({ skill, onClick, onEdit, onDelete }) {
  const categoryColors = {
    'coding': 'from-blue-500 to-cyan-600',
    'search': 'from-emerald-500 to-green-600',
    'file': 'from-orange-500 to-amber-600',
    'social': 'from-purple-500 to-pink-600',
    'default': 'from-gray-500 to-gray-600'
  }
  
  const color = categoryColors[skill.category] || categoryColors.default
  
  return (
    <div 
      className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all cursor-pointer group"
      onClick={() => onClick(skill)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center`}>
            <Wrench className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{skill.name}</h3>
            <p className="text-xs text-gray-500">{skill.category || '未分类'}</p>
          </div>
        </div>
        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg text-xs">
          {skill.file_count || 0} 文件
        </span>
      </div>
      
      {skill.description && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-4">{skill.description}</p>
      )}
      
      <div className="flex items-center gap-2 pt-4 border-t border-gray-100 opacity-0 group-hover:opacity-100 transition-opacity">
        <button 
          onClick={(e) => { e.stopPropagation(); onEdit(skill) }}
          className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg"
        >
          <Edit2 className="w-4 h-4" />
        </button>
        <button 
          onClick={(e) => { e.stopPropagation(); onDelete(skill) }}
          className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

export default function SkillsPage() {
  const [skills, setSkills] = useState([])
  const [selectedSkill, setSelectedSkill] = useState(null)
  const [files, setFiles] = useState([])
  const [editingFile, setEditingFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({ name: '', description: '', category: '' })
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState('grid')

  const loadSkills = async () => {
    const token = localStorage.getItem('token')
    try {
      const res = await axios.get(`${API}/api/skills`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setSkills(res.data)
    } catch (err) {
      console.error('加载技能失败', err)
    } finally {
      setLoading(false)
    }
  }

  const loadFiles = async (skillId) => {
    const token = localStorage.getItem('token')
    try {
      const res = await axios.get(`${API}/api/skills/${skillId}/files`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setFiles(res.data)
    } catch (err) {
      console.error('加载文件失败', err)
    }
  }

  useEffect(() => {
    loadSkills()
  }, [])

  const filteredSkills = skills.filter(s => 
    s.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.description?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleCreate = async () => {
    if (!formData.name.trim()) return
    const token = localStorage.getItem('token')
    try {
      await axios.post(`${API}/api/skills`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setShowForm(false)
      setFormData({ name: '', description: '', category: '' })
      loadSkills()
    } catch (err) {
      alert('创建失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDelete = async (skill) => {
    if (!confirm(`确定删除技能 "${skill.name}"？`)) return
    const token = localStorage.getItem('token')
    try {
      await axios.delete(`${API}/api/skills/${skill.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (selectedSkill?.id === skill.id) {
        setSelectedSkill(null)
        setFiles([])
      }
      loadSkills()
    } catch (err) {
      alert('删除失败: ' + (err.response?.data?.detail || err.message))
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
          <h1 className="text-2xl font-bold text-gray-900">Skills 管理</h1>
          <p className="text-gray-500 mt-1">创建和管理 AI 技能，定义 Agent 的行为和能力</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
        >
          <Plus className="w-4 h-4" />
          <span>新建 Skill</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总技能数', value: skills.length, icon: Wrench, color: 'from-violet-500 to-purple-600' },
          { label: '已绑定 Agent', value: skills.reduce((acc, s) => acc + (s.agent_count || 0), 0), icon: Bot, color: 'from-emerald-500 to-green-600' },
          { label: '文件总数', value: skills.reduce((acc, s) => acc + (s.file_count || 0), 0), icon: FileCode, color: 'from-blue-500 to-cyan-600' },
          { label: '分类数', value: [...new Set(skills.map(s => s.category).filter(Boolean))].length, icon: FolderOpen, color: 'from-orange-500 to-amber-600' },
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
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索技能..."
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500'}`}
          >
            <Grid className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500'}`}
          >
            <ListIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Skills List */}
        <div className="space-y-3">
          {filteredSkills.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
              <Wrench className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <h3 className="font-medium text-gray-900 mb-2">暂无技能</h3>
              <p className="text-sm text-gray-500">创建一个 Skill 来定义 Agent 的能力</p>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-2 gap-3">
              {filteredSkills.map(skill => (
                <SkillCard
                  key={skill.id}
                  skill={skill}
                  onClick={setSelectedSkill}
                  onEdit={() => {}}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredSkills.map(skill => (
                <div
                  key={skill.id}
                  className={`bg-white rounded-xl border p-4 flex items-center gap-3 cursor-pointer ${
                    selectedSkill?.id === skill.id ? 'border-purple-500 bg-purple-50' : 'border-gray-200'
                  }`}
                  onClick={() => setSelectedSkill(skill)}
                >
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                    <Wrench className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-gray-900 truncate">{skill.name}</h3>
                    <p className="text-xs text-gray-500">{skill.category || '未分类'}</p>
                  </div>
                  <span className="text-xs text-gray-500">{skill.file_count || 0} 文件</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Skill Detail */}
        <div className="col-span-2">
          {selectedSkill ? (
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                    <Wrench className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">{selectedSkill.name}</h2>
                    <p className="text-sm text-gray-500">{selectedSkill.category || '未分类'}</p>
                  </div>
                </div>
                {selectedSkill.description && (
                  <p className="mt-4 text-gray-600">{selectedSkill.description}</p>
                )}
              </div>
              
              <div className="p-6">
                <h3 className="font-medium text-gray-900 mb-4">文件列表</h3>
                {files.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无文件</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {files.map(file => (
                      <div key={file.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                        <FileCode className="w-5 h-5 text-gray-400" />
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">{file.name}</p>
                          <p className="text-xs text-gray-500">{file.size || 'N/A'} · {new Date(file.created_at).toLocaleDateString()}</p>
                        </div>
                        <button className="p-2 hover:bg-white rounded-lg">
                          <Edit2 className="w-4 h-4 text-gray-400" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
              <Wrench className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">选择一个技能</h3>
              <p className="text-gray-500">从左侧选择一个 Skill 查看详情</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">新建 Skill</h2>
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
                  placeholder="例如：代码审查专家"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({...formData, category: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">未分类</option>
                  <option value="coding">编码</option>
                  <option value="search">搜索</option>
                  <option value="file">文件</option>
                  <option value="social">社交</option>
                </select>
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
              <button onClick={handleCreate} className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700">
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
