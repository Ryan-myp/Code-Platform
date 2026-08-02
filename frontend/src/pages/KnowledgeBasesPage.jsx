import React, { useState, useEffect, useCallback } from 'react'
import {
  Database, Plus, Edit2, Trash2, Search,
  FolderOpen, Link2, Hash, RefreshCw,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import {
  Modal, Button, Empty, SkeletonGrid, ErrorState, Badge, PageHeader, ConfirmDialog,
} from '../components/ui'

const KB_TYPES = [
  { value: 'file', label: '本地文件', icon: FolderOpen, color: 'from-violet-500 to-purple-600' },
  { value: 'url', label: 'URL', icon: Link2, color: 'from-blue-500 to-cyan-600' },
]

const typeMeta = (type) => KB_TYPES.find((t) => t.value === type) || KB_TYPES[0]

// 知识库卡片
function KBCard({ kb, onEdit, onDelete }) {
  const meta = typeMeta(kb.type)
  const Icon = meta.icon
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 flex flex-col">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${meta.color} flex items-center justify-center text-white flex-shrink-0 shadow-lg`}>
            <Icon className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{kb.name}</h3>
            <p className="text-xs text-gray-500 mt-0.5">{meta.label}</p>
          </div>
        </div>
        <Badge label={meta.label} className="bg-gray-100 text-gray-600" />
      </div>

      <div className="space-y-1.5 mb-4 flex-1">
        {kb.type === 'url' ? (
          <p className="text-sm text-gray-600 flex items-center gap-2 min-w-0">
            <Link2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="truncate font-mono text-xs">{kb.url || '-'}</span>
          </p>
        ) : (
          <p className="text-sm text-gray-600 flex items-center gap-2 min-w-0">
            <FolderOpen className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="truncate font-mono text-xs">{kb.path || '-'}</span>
          </p>
        )}
        <p className="text-xs text-gray-500 flex items-center gap-2">
          <Hash className="w-3.5 h-3.5" />
          top_k: <span className="font-medium text-gray-700">{kb.top_k ?? 5}</span>
        </p>
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <span className="text-xs text-gray-400">{formatRelativeTime(kb.created_at)}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onEdit(kb)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(kb)}
            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// 创建/编辑表单
function KBFormModal({ open, onClose, onSubmit, editing, loading }) {
  const [form, setForm] = useState({ name: '', type: 'file', path: '', url: '', top_k: 5 })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (!open) return
    if (editing) {
      setForm({
        name: editing.name || '',
        type: editing.type || 'file',
        path: editing.path || '',
        url: editing.url || '',
        top_k: editing.top_k ?? 5,
      })
    } else {
      setForm({ name: '', type: 'file', path: '', url: '', top_k: 5 })
    }
    setErrors({})
  }, [open, editing])

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入知识库名称'
    if (form.name.length > 80) e.name = '名称不能超过 80 个字符'
    if (form.type === 'file' && !form.path.trim()) e.path = '请输入文件路径'
    if (form.type === 'url') {
      if (!form.url.trim()) e.url = '请输入 URL'
      else if (!/^https?:\/\//i.test(form.url.trim())) e.url = 'URL 需以 http(s):// 开头'
    }
    if (form.top_k !== '' && form.top_k != null) {
      const n = Number(form.top_k)
      if (isNaN(n) || n < 1 || n > 100) e.top_k = 'top_k 需为 1-100 之间的整数'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const payload = {
      name: form.name.trim(),
      type: form.type,
      path: form.type === 'file' ? form.path.trim() : '',
      url: form.type === 'url' ? form.url.trim() : '',
      top_k: Number(form.top_k) || 5,
    }
    onSubmit(payload)
  }

  const inputCls = (err) =>
    `w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${
      err ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'
    }`

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑知识库' : '新建知识库'}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={loading}>{editing ? '保存' : '创建'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：技术文档库"
            className={inputCls(errors.name)}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">来源类型</label>
          <select
            value={form.type}
            onChange={(e) => setField('type', e.target.value)}
            className={inputCls(false)}
          >
            {KB_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        {form.type === 'file' ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              文件路径 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.path}
              onChange={(e) => setField('path', e.target.value)}
              placeholder="/path/to/documents"
              className={inputCls(errors.path)}
            />
            {errors.path && <p className="text-xs text-red-500 mt-1">{errors.path}</p>}
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              URL <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.url}
              onChange={(e) => setField('url', e.target.value)}
              placeholder="https://example.com/docs"
              className={inputCls(errors.url)}
            />
            {errors.url && <p className="text-xs text-red-500 mt-1">{errors.url}</p>}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            top_k（检索召回数量）
          </label>
          <input
            type="number"
            min={1}
            max={100}
            value={form.top_k}
            onChange={(e) => setField('top_k', e.target.value)}
            className={inputCls(errors.top_k)}
          />
          {errors.top_k && <p className="text-xs text-red-500 mt-1">{errors.top_k}</p>}
        </div>
      </div>
    </Modal>
  )
}

export default function KnowledgeBasesPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/knowledge-bases')
      setItems(res.data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const filteredItems = items.filter((item) => {
    const q = searchTerm.toLowerCase()
    const matchSearch = !q ||
      item.name?.toLowerCase().includes(q) ||
      item.path?.toLowerCase().includes(q) ||
      item.url?.toLowerCase().includes(q)
    const matchType = typeFilter === 'all' || item.type === typeFilter
    return matchSearch && matchType
  })

  const openCreate = () => {
    setEditingItem(null)
    setShowForm(true)
  }
  const openEdit = (item) => {
    setEditingItem(item)
    setShowForm(true)
  }

  const handleSave = async (payload) => {
    setSaving(true)
    try {
      if (editingItem) {
        await api.put(`/api/knowledge-bases/${editingItem.id}`, payload)
        toast.success(`知识库「${payload.name}」已更新`)
      } else {
        await api.post('/api/knowledge-bases', payload)
        toast.success(`知识库「${payload.name}」已创建`)
      }
      setShowForm(false)
      setEditingItem(null)
      loadData()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return false
    try {
      await api.delete(`/api/knowledge-bases/${deleteTarget.id}`)
      toast.success(`知识库「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      loadData()
      return true
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
      return false
    }
  }

  const stats = [
    { label: '总知识库', value: items.length, icon: Database, color: 'from-violet-500 to-purple-600' },
    { label: '本地文件', value: items.filter((i) => (i.type || 'file') === 'file').length, icon: FolderOpen, color: 'from-emerald-500 to-green-600' },
    { label: 'URL 类型', value: items.filter((i) => i.type === 'url').length, icon: Link2, color: 'from-blue-500 to-cyan-600' },
    { label: '平均 top_k', value: items.length ? (items.reduce((a, i) => a + (Number(i.top_k) || 0), 0) / items.length).toFixed(1) : '0.0', icon: Hash, color: 'from-orange-500 to-amber-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="知识库管理"
        description="管理文档知识库，为 Agent 提供知识检索能力"
        icon={Database}
        iconColor="from-violet-500 to-purple-600"
        actions={
          <Button variant="primary" icon={Plus} onClick={openCreate}>新建知识库</Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center flex-shrink-0`}>
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索知识库名称、路径或 URL…"
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div className="flex items-center gap-2">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all text-sm"
          >
            <option value="all">全部类型</option>
            {KB_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <Button variant="ghost" size="md" icon={RefreshCw} onClick={loadData} title="刷新">
            刷新
          </Button>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={loadData} />
      ) : filteredItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Database}
            title={searchTerm || typeFilter !== 'all' ? '未找到匹配的知识库' : '暂无知识库'}
            description={searchTerm || typeFilter !== 'all' ? '尝试调整搜索或筛选条件' : '点击「新建知识库」创建你的第一个知识库'}
            actionLabel={searchTerm || typeFilter !== 'all' ? undefined : '新建知识库'}
            onAction={searchTerm || typeFilter !== 'all' ? undefined : openCreate}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((kb) => (
            <KBCard key={kb.id} kb={kb} onEdit={openEdit} onDelete={setDeleteTarget} />
          ))}
        </div>
      )}

      <KBFormModal
        open={showForm}
        onClose={() => { setShowForm(false); setEditingItem(null) }}
        onSubmit={handleSave}
        editing={editingItem}
        loading={saving}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除知识库"
        message={<>确定要删除知识库「<span className="font-medium text-gray-700">{deleteTarget?.name}</span>」吗？此操作不可撤销。</>}
        confirmLabel="确认删除"
      />
    </div>
  )
}
