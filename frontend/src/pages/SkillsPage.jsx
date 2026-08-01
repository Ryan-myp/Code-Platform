import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Wrench, Plus, Trash2, Save, X, ChevronDown, ChevronRight, FileText, FolderOpen, Code, Image, FileCode, Search, Edit2, Eye, FolderPlus, Upload, Download, FileJson, FileImage, File, Terminal, RefreshCw } from 'lucide-react'

const API = 'http://localhost:8888'

export default function SkillsPage() {
  const [skills, setSkills] = useState([])
  const [selectedSkill, setSelectedSkill] = useState(null)
  const [files, setFiles] = useState([])
  const [editingFile, setEditingFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [templates, setTemplates] = useState([])
  const [formData, setFormData] = useState({})
  const [loading, setLoading] = useState(false)
  const [expandedFolders, setExpandedFolders] = useState({})
  const [searchTerm, setSearchTerm] = useState('')
  const [newFileModal, setNewFileModal] = useState({ show: false, folder: '' })
  const [newFileName, setNewFileName] = useState('')
  const [activeTab, setActiveTab] = useState('files')

  useEffect(() => {
    loadSkills()
    loadTemplates()
  }, [])

  const loadSkills = async () => {
    try {
      const token = localStorage.getItem('token')
      const res = await axios.get(`${API}/api/skills`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setSkills(res.data)
    } catch (err) { console.error(err) }
  }

  const loadTemplates = async () => {
    try {
      const token = localStorage.getItem('token')
      const res = await axios.get(`${API}/api/skills/templates`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setTemplates(res.data)
    } catch (err) { console.error(err) }
  }

  const loadFiles = async (skillId) => {
    try {
      const token = localStorage.getItem('token')
      const res = await axios.get(`${API}/api/skills/${skillId}/files`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setFiles(res.data)
      const folders = {}
      res.data.forEach(f => { folders[f.folder] = true })
      setExpandedFolders(prev => ({ ...prev, ...folders }))
    } catch (err) { console.error(err) }
  }

  const handleSkillSelect = (skill) => {
    setSelectedSkill(skill)
    loadFiles(skill.id)
    setEditingFile(null)
    setActiveTab('files')
  }

  const toggleFolder = (folder) => {
    setExpandedFolders(prev => ({ ...prev, [folder]: !prev[folder] }))
  }

  const handleCreateSkill = async () => {
    if (!formData.name?.trim()) return alert('名称不能为空')
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      await axios.post(`${API}/api/skills`, { ...formData, content: formData.content || '' }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setShowForm(false)
      setShowTemplateModal(false)
      setFormData({})
      loadSkills()
    } catch (err) { console.error(err); alert('创建失败') }
    finally { setLoading(false) }
  }

  const handleCreateFromTemplate = async (template) => {
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const res = await axios.post(`${API}/api/skills/from-template`, {
        template_id: template.id,
        name: template.name + ' (副本)'
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setShowTemplateModal(false)
      loadSkills()
      const newSkill = res.data
      setSelectedSkill({ id: newSkill.id, name: newSkill.name })
      loadFiles(newSkill.id)
    } catch (err) { console.error(err); alert('创建失败') }
    finally { setLoading(false) }
  }

  const handleDeleteSkill = async (id) => {
    if (!confirm('确定删除这个 Skill？所有文件也会被删除。')) return
    try {
      const token = localStorage.getItem('token')
      await axios.delete(`${API}/api/skills/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (selectedSkill?.id === id) {
        setSelectedSkill(null)
        setFiles([])
        setEditingFile(null)
      }
      loadSkills()
    } catch (err) { console.error(err) }
  }

  const handleEditFile = (file) => {
    setEditingFile(file)
    setFileContent(file.content || '')
  }

  const handleSaveFile = async () => {
    if (!selectedSkill || !editingFile) return
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      await axios.put(
        `${API}/api/skills/${selectedSkill.id}/files/${encodeURIComponent(editingFile.folder)}/${encodeURIComponent(editingFile.filename)}`,
        { content: fileContent },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      await loadFiles(selectedSkill.id)
      setEditingFile(null)
    } catch (err) { console.error(err); alert('保存失败') }
    finally { setLoading(false) }
  }

  const handleAddFile = async (folder) => {
    setNewFileModal({ show: true, folder })
    setNewFileName('')
  }

  const handleCreateFile = async () => {
    if (!newFileName?.trim()) return alert('文件名不能为空')
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      await axios.post(
        `${API}/api/skills/${selectedSkill.id}/files`,
        { folder: newFileModal.folder, filename: newFileName.trim(), content: '' },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setNewFileModal({ show: false, folder: '' })
      setNewFileName('')
      await loadFiles(selectedSkill.id)
    } catch (err) { console.error(err); alert('创建失败') }
    finally { setLoading(false) }
  }

  const handleDeleteFile = async (file) => {
    if (!confirm(`确定删除 ${file.folder}/${file.filename}？`)) return
    try {
      const token = localStorage.getItem('token')
      await axios.delete(
        `${API}/api/skills/${selectedSkill.id}/files/${encodeURIComponent(file.folder)}/${encodeURIComponent(file.filename)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
      await loadFiles(selectedSkill.id)
      if (editingFile?.filename === file.filename) {
        setEditingFile(null)
      }
    } catch (err) { console.error(err) }
  }

  const handleExportSkill = async (skillId) => {
    try {
      const token = localStorage.getItem('token')
      const res = await axios.get(`${API}/api/skills/${skillId}/export`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const link = document.createElement('a')
      link.href = `data:application/zip;base64,${res.data.content}`
      link.download = `${skillId}.zip`
      link.click()
    } catch (err) { console.error(err); alert('导出失败') }
  }

  const handleImportSkill = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const buffer = await file.arrayBuffer()
      const base64 = btoa(new Uint8Array(buffer).reduce((data, byte) => data + String.fromCharCode(byte), ''))
      await axios.post(`${API}/api/skills/import`, { content: base64 }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      loadSkills()
      alert('导入成功')
    } catch (err) { console.error(err); alert('导入失败') }
    finally { setLoading(false) }
  }

  const handleSync = async () => {
    try {
      const token = localStorage.getItem('token')
      const res = await axios.post(`${API}/api/skills/sync`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      alert(res.data.message)
      loadSkills()
    } catch (err) { console.error(err); alert('同步失败') }
  }

  const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase()
    switch(ext) {
      case 'md': return FileText
      case 'json': return FileJson
      case 'py': return Terminal
      case 'yaml': case 'yml': return Code
      case 'png': case 'jpg': case 'svg': return FileImage
      default: return File
    }
  }

  const groupedFiles = files.reduce((acc, file) => {
    if (!acc[file.folder]) acc[file.folder] = []
    acc[file.folder].push(file)
    return acc
  }, {})

  const filteredFiles = searchTerm 
    ? files.filter(f => f.filename.toLowerCase().includes(searchTerm.toLowerCase()) || f.folder.toLowerCase().includes(searchTerm.toLowerCase()))
    : files
  const filteredGrouped = filteredFiles.reduce((acc, file) => {
    if (!acc[file.folder]) acc[file.folder] = []
    acc[file.folder].push(file)
    return acc
  }, {})
  const filteredFolders = Object.keys(filteredGrouped).sort()

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Wrench className="w-6 h-6 text-purple-600" />
              Skills 管理
            </h1>
            <p className="text-gray-500 mt-1">管理 Agent 技能包，每个 Skill 是一个文件夹项目</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowTemplateModal(true)} className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2">
              <Plus className="w-4 h-4" />从模板创建
            </button>
            <button onClick={() => { setShowForm(true); setFormData({}); }} className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2">
              <Plus className="w-4 h-4" />新建 Skill
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          {/* Toolbar */}
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button onClick={handleSync} className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1">
                <RefreshCw className="w-4 h-4" />同步
              </button>
              <label className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer flex items-center gap-1">
                <Upload className="w-4 h-4" />导入
                <input type="file" accept=".zip" className="hidden" onChange={handleImportSkill} />
              </label>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="搜索文件..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-1.5 border border-gray-200 rounded-lg text-sm focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
              />
            </div>
          </div>

          <div className="flex">
            {/* Skill List */}
            <div className="w-64 border-r border-gray-200 p-4">
              <h3 className="font-medium text-gray-700 mb-3">Skill 列表</h3>
              <div className="space-y-1">
                {skills.map(skill => (
                  <div
                    key={skill.id}
                    onClick={() => handleSkillSelect(skill)}
                    className={`p-2 rounded-lg cursor-pointer flex items-center justify-between group ${
                      selectedSkill?.id === skill.id 
                        ? 'bg-purple-50 text-purple-700' 
                        : 'hover:bg-gray-50 text-gray-700'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Wrench className="w-4 h-4 flex-shrink-0" />
                      <span className="text-sm truncate">{skill.name}</span>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteSkill(skill.id) }}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded"
                    >
                      <Trash2 className="w-3 h-3 text-red-500" />
                    </button>
                  </div>
                ))}
                {skills.length === 0 && (
                  <p className="text-sm text-gray-400 text-center py-4">暂无 Skill</p>
                )}
              </div>
            </div>

            {/* File Tree / Editor */}
            <div className="flex-1">
              {selectedSkill ? (
                <>
                  {/* File List */}
                  {activeTab === 'files' && (
                    <div>
                      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                        <div>
                          <h2 className="font-medium text-gray-900">{selectedSkill.name}</h2>
                          {selectedSkill.description && <p className="text-sm text-gray-500 mt-0.5">{selectedSkill.description}</p>}
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleExportSkill(selectedSkill.id)}
                            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1"
                          >
                            <Download className="w-4 h-4" />导出
                          </button>
                          <button
                            onClick={() => setActiveTab('settings')}
                            className={`px-3 py-1.5 text-sm rounded-lg ${activeTab === 'settings' ? 'bg-purple-50 text-purple-700' : 'border border-gray-200 hover:bg-gray-50'}`}
                          >
                            设置
                          </button>
                        </div>
                      </div>
                      
                      <div className="p-4">
                        {filteredFolders.length === 0 ? (
                          <div className="text-center py-12 text-gray-400">
                            <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-50" />
                            <p>暂无文件</p>
                            <button
                              onClick={() => handleAddFile('')}
                              className="mt-3 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm"
                            >
                              + 添加文件
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {filteredFolders.map(folder => {
                              const isExpanded = expandedFolders[folder]
                              const folderFiles = filteredGrouped[folder]
                              return (
                                <div key={folder}>
                                  <div className="flex items-center justify-between mb-2">
                                    <button
                                      onClick={() => toggleFolder(folder)}
                                      className="flex items-center gap-2 text-gray-700 hover:text-purple-600"
                                    >
                                      {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                      <FolderOpen className="w-4 h-4 text-purple-500" />
                                      <span className="font-medium text-sm">{folder || '根目录'}</span>
                                      <span className="text-xs text-gray-400">({folderFiles.length})</span>
                                    </button>
                                    <button
                                      onClick={() => handleAddFile(folder)}
                                      className="px-2 py-1 text-xs bg-purple-50 text-purple-600 rounded hover:bg-purple-100"
                                    >
                                      + 添加
                                    </button>
                                  </div>
                                  
                                  {isExpanded && (
                                    <div className="ml-6 space-y-1">
                                      {folderFiles.map((file, idx) => (
                                        <div key={idx} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded-lg group">
                                          <div className="flex items-center gap-2">
                                            {(() => { const Icon = getFileIcon(file.filename); return <Icon className="w-4 h-4 text-gray-400" />; })()}
                                            <span className="text-sm text-gray-700">{file.filename}</span>
                                          </div>
                                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button
                                              onClick={() => handleEditFile(file)}
                                              className="p-1.5 hover:bg-blue-50 rounded text-gray-500 hover:text-blue-600"
                                              title="编辑"
                                            >
                                              <Edit2 className="w-3 h-3" />
                                            </button>
                                            <button
                                              onClick={() => handleDeleteFile(file)}
                                              className="p-1.5 hover:bg-red-50 rounded text-gray-500 hover:text-red-600"
                                              title="删除"
                                            >
                                              <Trash2 className="w-3 h-3" />
                                            </button>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Settings Tab */}
                  {activeTab === 'settings' && (
                    <div className="p-6">
                      <h3 className="font-medium text-gray-900 mb-4">Skill 设置</h3>
                      <div className="space-y-4 max-w-lg">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
                          <input
                            type="text"
                            value={selectedSkill.name || ''}
                            onChange={(e) => setSelectedSkill({ ...selectedSkill, name: e.target.value })}
                            className="w-full p-2 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                          <textarea
                            value={selectedSkill.description || ''}
                            onChange={(e) => setSelectedSkill({ ...selectedSkill, description: e.target.value })}
                            className="w-full p-2 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500 h-24 resize-none"
                          />
                        </div>
                        <button
                          onClick={() => {
                            axios.put(`${API}/api/skills/${selectedSkill.id}`, selectedSkill, {
                              headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
                            }).then(() => loadSkills())
                          }}
                          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                        >
                          保存设置
                        </button>
                      </div>
                    </div>
                  )}

                  {/* File Editor */}
                  {editingFile && (
                    <div className="border-t border-gray-200">
                      <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
                        <div>
                          <h3 className="font-medium text-gray-900">{editingFile.folder}/{editingFile.filename}</h3>
                          <p className="text-sm text-gray-500">编辑中...</p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => setEditingFile(null)}
                            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
                          >
                            取消
                          </button>
                          <button
                            onClick={handleSaveFile}
                            disabled={loading}
                            className="px-4 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1"
                          >
                            <Save className="w-4 h-4" />
                            {loading ? '保存中...' : '保存'}
                          </button>
                        </div>
                      </div>
                      <div className="p-4">
                        <textarea
                          value={fileContent}
                          onChange={(e) => setFileContent(e.target.value)}
                          className="w-full h-96 p-4 border border-gray-200 rounded-lg font-mono text-sm focus:border-purple-500 focus:ring-1 focus:ring-purple-500 resize-none"
                          placeholder="输入文件内容..."
                          spellCheck={false}
                        />
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="flex items-center justify-center h-96 text-gray-400">
                  <div className="text-center">
                    <Wrench className="w-16 h-16 mx-auto mb-4 opacity-30" />
                    <p className="text-lg font-medium text-gray-600">选择或创建一个 Skill</p>
                    <p className="text-sm mt-1">从左侧列表选择一个 Skill，或创建新的</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Create Skill Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10">
              <h3 className="text-lg font-semibold">新建 Skill</h3>
              <button onClick={() => setShowForm(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                  value={formData.name || ''}
                  onChange={e => setFormData({...formData, name: e.target.value})}
                  placeholder="例如：代码规范、测试策略"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <input
                  type="text"
                  className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                  value={formData.description || ''}
                  onChange={e => setFormData({...formData, description: e.target.value})}
                  placeholder="简要说明这个 Skill 的用途"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">SKILL.md 内容 *</label>
                <textarea
                  className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500 h-48 resize-none font-mono text-sm"
                  value={formData.content || ''}
                  onChange={e => setFormData({...formData, content: e.target.value})}
                  placeholder={`# ${formData.name || 'Skill Name'}\n\n## Description\n简要描述这个 Skill 的作用\n\n## Instructions\n详细的执行指令...\n\n## Examples\n示例...`}
                />
              </div>
            </div>
            <div className="p-5 border-t border-gray-100 flex space-x-3 sticky bottom-0 bg-white">
              <button
                onClick={() => setShowForm(false)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
              >
                取消
              </button>
              <button
                onClick={handleCreateSkill}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 font-medium flex items-center justify-center"
              >
                {loading ? '创建中...' : <><Plus className="w-4 h-4 mr-2" />创建</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Template Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10">
              <h3 className="text-lg font-semibold">从模板创建</h3>
              <button onClick={() => setShowTemplateModal(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5">
              <div className="grid grid-cols-1 gap-4">
                {templates.map(template => (
                  <div
                    key={template.id}
                    className="p-4 border border-gray-200 rounded-lg hover:border-purple-500 hover:bg-purple-50 cursor-pointer transition-all"
                    onClick={() => handleCreateFromTemplate(template)}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-semibold text-gray-900">{template.name}</h4>
                        <p className="text-sm text-gray-500 mt-1">{template.description}</p>
                      </div>
                      <button className="px-3 py-1 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700">
                        使用
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* New File Modal */}
      {newFileModal.show && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
            <div className="p-5 border-b border-gray-100 flex justify-between items-center">
              <h3 className="text-lg font-semibold">新建文件</h3>
              <button onClick={() => setNewFileModal({ show: false, folder: '' })} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">文件夹</label>
                <input
                  type="text"
                  className="w-full p-2.5 border border-gray-200 rounded-lg bg-gray-50"
                  value={newFileModal.folder || '根目录'}
                  readOnly
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">文件名 *</label>
                <input
                  type="text"
                  className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                  value={newFileName}
                  onChange={e => setNewFileName(e.target.value)}
                  placeholder="例如：SKILL.md, ref1.md, validate.py"
                  autoFocus
                  onKeyDown={(e) => { if (e.key === 'Enter') handleCreateFile() }}
                />
              </div>
            </div>
            <div className="p-5 border-t border-gray-100 flex space-x-3">
              <button
                onClick={() => setNewFileModal({ show: false, folder: '' })}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
              >
                取消
              </button>
              <button
                onClick={handleCreateFile}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 font-medium flex items-center justify-center"
              >
                {loading ? '创建中...' : <><Plus className="w-4 h-4 mr-2" />创建</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
