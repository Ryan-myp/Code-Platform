import React, { useState, useEffect, useCallback } from 'react'
import {
  ListTodo,
  FolderKanban,
  FileText,
  Code2,
  Plus,
  RefreshCw,
  Search,
  Eye,
  MessageSquare,
  CheckCircle2,
  Clock,
  ArrowRight,
  Edit2,
  Trash2,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { api } from '../lib/api'
import { sanitizeHtml } from '../lib/sanitize'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import {
  Modal,
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  Badge,
  ColorBadge,
  PageHeader,
  ConfirmDialog,
} from '../components/ui'
import RichTextEditor from '../components/RichTextEditor'

// 需求状态自定义映射（draft 在默认映射中已有）
const REQ_STATUS_MAP = {
  generated: { text: '已生成', cls: 'bg-emerald-100 text-emerald-700' },
  reviewed: { text: '已审查', cls: 'bg-purple-100 text-purple-700' },
}

// 项目状态自定义映射
const PROJECT_STATUS_MAP = {
  planning: { text: '规划中', cls: 'bg-blue-100 text-blue-700' },
  active: { text: '进行中', cls: 'bg-emerald-100 text-emerald-700' },
  completed: { text: '已完成', cls: 'bg-gray-100 text-gray-600' },
}

// 优先级 → 颜色
const PRIORITY_COLOR = { P0: 'red', P1: 'yellow', P2: 'blue' }

// 流水线阶段定义
const PIPELINE = [
  { key: 'prd', label: 'PRD', field: 'prd_text', tab: 'prd', icon: FileText },
  { key: 'review', label: '审查', field: 'review_report', tab: 'review', icon: MessageSquare },
  { key: 'td', label: '方案', field: 'tech_design', tab: 'td', icon: Code2 },
  { key: 'test', label: '测试', field: 'test_cases', tab: 'test', icon: ListTodo },
  { key: 'code', label: '代码', field: 'code', tab: 'code', icon: FileText },
]

// 优先级徽章
function PriorityBadge({ priority }) {
  return <ColorBadge color={PRIORITY_COLOR[priority] || 'gray'}>{priority || 'P2'}</ColorBadge>
}

// 需求卡片
function RequirementCard({ req, projects, onView, onEdit, onDelete, onPipeline }) {
  const projectName = projects.find((p) => p.id === req.project_id)?.name

  return (
    <div className="p-5 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow flex flex-col">
      <div className="flex items-start justify-between mb-2 gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <PriorityBadge priority={req.priority} />
          <Badge status={req.status || 'draft'} customMap={REQ_STATUS_MAP} />
          <h3 className="font-medium text-gray-900 truncate">{req.name}</h3>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onView(req)}
            className="p-1 text-gray-400 hover:text-indigo-600 rounded transition-colors"
            title="查看详情"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(req)}
            className="p-1 text-gray-400 hover:text-indigo-600 rounded transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(req)}
            className="p-1 text-gray-400 hover:text-red-600 rounded transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div
        className="text-sm text-gray-500 line-clamp-2 mb-3 prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{
          __html: sanitizeHtml(req.description) || '<span class="text-gray-400">暂无描述</span>',
        }}
      />

      {projectName && <div className="text-xs text-gray-400 mb-2">关联项目：{projectName}</div>}

      {/* Pipeline stages */}
      <div className="flex items-center gap-0.5 mt-auto pt-3 border-t border-gray-100 flex-wrap">
        {PIPELINE.map((p, i) => {
          const done = !!req[p.field]
          const Icon = done ? CheckCircle2 : Clock
          return (
            <React.Fragment key={p.key}>
              {i > 0 && <ArrowRight className="w-3 h-3 text-gray-300" />}
              <button
                onClick={() => onPipeline(req.id, p.tab)}
                className={`flex items-center gap-1 px-2 py-1 text-xs rounded-md transition-colors ${
                  done
                    ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                    : 'bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600'
                }`}
              >
                <Icon className="w-3 h-3" />
                {p.label}
              </button>
            </React.Fragment>
          )
        })}
      </div>
    </div>
  )
}

// 需求表单模态框（创建/编辑共用）
function RequirementFormModal({ open, onClose, onSubmit, editing, projects, loading }) {
  const [form, setForm] = useState({ name: '', description: '', priority: 'P1', project_id: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      setForm({
        name: editing?.name || '',
        description: editing?.description || '',
        priority: editing?.priority || 'P1',
        project_id: editing?.project_id || '',
      })
      setErrors({})
    }
  }, [open, editing])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入需求名称'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim() })
  }

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑需求' : '新建需求'}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={loading}>
            {editing ? '保存' : '创建'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            需求名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：电商下单功能"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-indigo-500/20 focus:border-indigo-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">详细描述</label>
          <div className="rounded-xl border border-gray-200 focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-500 overflow-hidden">
            <RichTextEditor
              value={form.description}
              onChange={(html) => setField('description', html)}
              placeholder="描述这个需求的目标、用户故事、验收标准..."
              minHeight={160}
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">优先级</label>
            <select
              value={form.priority}
              onChange={(e) => setField('priority', e.target.value)}
              className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
            >
              <option value="P0">P0 - 阻塞</option>
              <option value="P1">P1 - 重要</option>
              <option value="P2">P2 - 一般</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">关联项目</label>
            <select
              value={form.project_id}
              onChange={(e) => setField('project_id', e.target.value)}
              className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
            >
              <option value="">无</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </Modal>
  )
}

// 需求详情模态框
function RequirementDetailModal({ req, onClose }) {
  if (!req) return null
  return (
    <Modal
      open={!!req}
      onClose={onClose}
      title={req.name}
      size="lg"
      footer={
        <Button variant="secondary" onClick={onClose}>
          关闭
        </Button>
      }
    >
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <PriorityBadge priority={req.priority} />
          <Badge status={req.status || 'draft'} customMap={REQ_STATUS_MAP} />
          {req.updated_at && (
            <span className="text-xs text-gray-400 ml-auto">
              {formatRelativeTime(req.updated_at)}
            </span>
          )}
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 mb-1 block">描述</label>
          <div
            className="prose prose-sm max-w-none p-3 bg-gray-50 rounded-lg border border-gray-200"
            dangerouslySetInnerHTML={{
              __html: sanitizeHtml(req.description) || '<span class="text-gray-400">暂无描述</span>',
            }}
          />
        </div>
        {req.prd_text && (
          <details>
            <summary className="cursor-pointer text-sm font-medium text-indigo-600 hover:text-indigo-700">
              查看 PRD
            </summary>
            <div className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
              <MarkdownRenderer content={req.prd_text} />
            </div>
          </details>
        )}
        {req.review_report && (
          <details>
            <summary className="cursor-pointer text-sm font-medium text-emerald-600 hover:text-emerald-700">
              查看审查报告
            </summary>
            <div className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
              <MarkdownRenderer content={req.review_report} />
            </div>
          </details>
        )}
      </div>
    </Modal>
  )
}

// 项目表单模态框
function ProjectFormModal({ open, onClose, onSubmit, loading }) {
  const [form, setForm] = useState({ name: '', description: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      setForm({ name: '', description: '' })
      setErrors({})
    }
  }, [open])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入项目名称'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim() })
  }

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建项目"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={loading}>
            创建
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            项目名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：电商平台项目"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-indigo-500/20 focus:border-indigo-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <textarea
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            rows={3}
            placeholder="描述这个项目..."
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
          />
        </div>
      </div>
    </Modal>
  )
}

export default function ReqBoardPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [activeTab, setActiveTab] = useState('requirements')
  const [requirements, setRequirements] = useState([])
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  const [showReqForm, setShowReqForm] = useState(false)
  const [editingReq, setEditingReq] = useState(null)
  const [savingReq, setSavingReq] = useState(false)
  const [viewingReq, setViewingReq] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const [showProjForm, setShowProjForm] = useState(false)
  const [savingProj, setSavingProj] = useState(false)

  const fetchAll = useCallback(
    async (initial = false) => {
      if (initial) {
        setLoading(true)
        setError(null)
      }
      try {
        const [reqRes, projRes] = await Promise.all([
          api.get('/api/requirements'),
          api.get('/api/projects'),
        ])
        setRequirements(reqRes.data)
        setProjects(projRes.data)
        if (initial) setError(null)
      } catch (e) {
        if (initial) setError(e)
        else toast.error(`刷新失败：${e.message}`)
      } finally {
        if (initial) setLoading(false)
      }
    },
    [toast]
  )

  useEffect(() => {
    fetchAll(true)
  }, [fetchAll])

  const handleRefresh = async () => {
    setRefreshing(true)
    await fetchAll(false)
    setRefreshing(false)
  }

  const openCreateReq = () => {
    setEditingReq(null)
    setShowReqForm(true)
  }
  const openEditReq = (req) => {
    setEditingReq(req)
    setShowReqForm(true)
  }

  const handleSaveReq = async (formData) => {
    setSavingReq(true)
    try {
      if (editingReq) {
        await api.put(`/api/requirements/${editingReq.id}`, formData)
        toast.success(`需求「${formData.name}」已更新`)
      } else {
        await api.post('/api/requirements', formData)
        toast.success(`需求「${formData.name}」已创建`)
      }
      setShowReqForm(false)
      setEditingReq(null)
      fetchAll(false)
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSavingReq(false)
    }
  }

  const handleDeleteReq = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/requirements/${deleteTarget.id}`)
      toast.success(`需求「${deleteTarget.name}」已删除`)
      if (viewingReq?.id === deleteTarget.id) setViewingReq(null)
      setDeleteTarget(null)
      fetchAll(false)
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const handleSaveProj = async (formData) => {
    setSavingProj(true)
    try {
      await api.post('/api/projects', formData)
      toast.success(`项目「${formData.name}」已创建`)
      setShowProjForm(false)
      fetchAll(false)
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    } finally {
      setSavingProj(false)
    }
  }

  const goToPipeline = (reqId, tab) => {
    navigate(`/workspace?requirement_id=${reqId}&tab=${tab}`)
  }

  const filtered = requirements.filter((r) => {
    const matchSearch =
      !searchTerm ||
      r.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.description || '').toLowerCase().includes(searchTerm.toLowerCase())
    const matchStatus = !filterStatus || r.status === filterStatus
    return matchSearch && matchStatus
  })

  const tabs = [
    { key: 'requirements', label: '需求列表', icon: ListTodo },
    { key: 'projects', label: '项目看板', icon: FolderKanban },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="需求看板"
        description="管理需求和项目，自动生成 PRD 和审查报告"
        icon={ListTodo}
        iconColor="from-indigo-500 to-purple-600"
        actions={
          <>
            <Button
              variant="secondary"
              icon={RefreshCw}
              onClick={handleRefresh}
              loading={refreshing}
            >
              刷新
            </Button>
            {activeTab === 'requirements' ? (
              <Button variant="primary" icon={Plus} onClick={openCreateReq}>
                新建需求
              </Button>
            ) : (
              <Button variant="primary" icon={Plus} onClick={() => setShowProjForm(true)}>
                新建项目
              </Button>
            )}
          </>
        }
      />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <tab.icon className="w-4 h-4" /> {tab.label}
          </button>
        ))}
      </div>

      {/* === TAB: Requirements === */}
      {activeTab === 'requirements' && (
        <>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="搜索需求名称或描述..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all text-sm"
              />
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all text-sm bg-white"
            >
              <option value="">全部状态</option>
              <option value="draft">草稿</option>
              <option value="generated">已生成</option>
              <option value="reviewed">已审查</option>
            </select>
          </div>

          {loading ? (
            <SkeletonGrid count={4} />
          ) : error ? (
            <ErrorState message={`加载失败：${error.message}`} onRetry={() => fetchAll(true)} />
          ) : filtered.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty
                icon={ListTodo}
                title={searchTerm || filterStatus ? '没有匹配的需求' : '暂无需求'}
                description={
                  searchTerm || filterStatus
                    ? '尝试调整搜索或筛选条件'
                    : '点击「新建需求」开始你的第一个需求'
                }
                actionLabel={searchTerm || filterStatus ? undefined : '新建需求'}
                onAction={searchTerm || filterStatus ? undefined : openCreateReq}
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((req) => (
                <RequirementCard
                  key={req.id}
                  req={req}
                  projects={projects}
                  onView={setViewingReq}
                  onEdit={openEditReq}
                  onDelete={setDeleteTarget}
                  onPipeline={goToPipeline}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* === TAB: Projects === */}
      {activeTab === 'projects' && (
        <>
          {loading ? (
            <SkeletonGrid count={6} />
          ) : error ? (
            <ErrorState message={`加载失败：${error.message}`} onRetry={() => fetchAll(true)} />
          ) : projects.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty
                icon={FolderKanban}
                title="暂无项目"
                description="点击「新建项目」开始你的第一个项目"
                actionLabel="新建项目"
                onAction={() => setShowProjForm(true)}
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((proj) => (
                <div
                  key={proj.id}
                  className="p-5 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                      <FolderKanban className="w-5 h-5 text-white" />
                    </div>
                    <Badge status={proj.status || 'planning'} customMap={PROJECT_STATUS_MAP} />
                  </div>
                  <h3 className="font-semibold text-gray-900">{proj.name}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                    {proj.description || '暂无描述'}
                  </p>
                  <div className="mt-3 flex items-center gap-4 text-sm text-gray-400">
                    <span>任务: {proj.task_count || 0}</span>
                    <span>完成: {proj.done_count || 0}</span>
                    <span>进度: {proj.progress || 0}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-1.5 mt-2">
                    <div
                      className="bg-indigo-600 h-1.5 rounded-full transition-all"
                      style={{ width: `${proj.progress || 0}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <RequirementFormModal
        open={showReqForm}
        onClose={() => {
          setShowReqForm(false)
          setEditingReq(null)
        }}
        onSubmit={handleSaveReq}
        editing={editingReq}
        projects={projects}
        loading={savingReq}
      />

      <RequirementDetailModal req={viewingReq} onClose={() => setViewingReq(null)} />

      <ProjectFormModal
        open={showProjForm}
        onClose={() => setShowProjForm(false)}
        onSubmit={handleSaveProj}
        loading={savingProj}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDeleteReq}
        title="确认删除需求"
        message={`确定要删除需求「${deleteTarget?.name}」吗？此操作不可撤销。`}
        confirmLabel="确认删除"
      />
    </div>
  )
}
