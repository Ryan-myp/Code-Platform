import React, { useState, useEffect, useCallback } from 'react'
import {
  Plus, Edit2, Trash2, Play, Clock,
  Search, LayoutGrid, List as ListIcon,
  Workflow, Calendar, Folder,
  BarChart3, CheckCircle2,
  GitBranch, Shield, FileCheck, UserCheck,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime, formatDate } from '../lib/format'
import {
  Modal, Button, Empty, SkeletonGrid, ErrorState, Badge, PageHeader, ConfirmDialog,
} from '../components/ui'

// 工作流快速模板（带完整节点编排，创建后即可运行）
const WORKFLOW_TEMPLATES = [
  { name: '需求评审流程', description: '需求文档生成→评审→输出的标准化流程', icon: FileCheck, color: 'from-blue-500 to-indigo-600',
    defaults: { name: '需求评审流程', description: '产品需求收集、技术评审、排期确认的标准化工作流' },
    definition: {
      nodes: [
        { id: 'tpl_prd1', type: 'prd', label: '需求文档生成', x: 60, y: 160, config: { stage: 'generate', prd_text: '${input.message}', tech_design: '', language: 'python' } },
        { id: 'tpl_prd2', type: 'prd', label: '需求评审', x: 300, y: 160, config: { stage: 'review', prd_text: '${tpl_prd1.result}', tech_design: '', language: 'python' } },
        { id: 'tpl_out1', type: 'output', label: '评审结果输出', x: 540, y: 160, config: {} },
      ],
      edges: [
        { id: 'e_prd1', from: 'tpl_prd1', to: 'tpl_prd2' },
        { id: 'e_prd2', from: 'tpl_prd2', to: 'tpl_out1' },
      ],
    } },
  { name: '代码发布流程', description: '发布计划→代码审查→质量判定→决策输出的 CI/CD 流程', icon: GitBranch, color: 'from-emerald-500 to-green-600',
    defaults: { name: '代码发布流程', description: '代码审查、自动化测试、灰度发布、全量上线的CI/CD工作流' },
    definition: {
      nodes: [
        { id: 'tpl_plan', type: 'agent', label: '发布计划制定', x: 60, y: 160, config: { agent_id: '', message: '${input.message}' } },
        { id: 'tpl_review', type: 'agent', label: '代码审查', x: 300, y: 160, config: { agent_id: '', message: '请对以下发布计划进行代码审查并输出审查报告：\n${tpl_plan.result}' } },
        { id: 'tpl_check', type: 'condition', label: '质量判定', x: 540, y: 160, config: { expression: "results['tpl_review'].status == 'success'" } },
        { id: 'tpl_out2', type: 'output', label: '发布决策输出', x: 780, y: 160, config: {} },
      ],
      edges: [
        { id: 'e_plan', from: 'tpl_plan', to: 'tpl_review' },
        { id: 'e_review', from: 'tpl_review', to: 'tpl_check' },
        { id: 'e_check', from: 'tpl_check', to: 'tpl_out2' },
      ],
    } },
  { name: '内容审核流程', description: '内容创作→合规审核→发布的管控流程', icon: Shield, color: 'from-amber-500 to-orange-600',
    defaults: { name: '内容审核流程', description: '内容创建、多级审核、合规检查、定时发布的管控工作流' },
    definition: {
      nodes: [
        { id: 'tpl_create', type: 'agent', label: '内容创作', x: 60, y: 160, config: { agent_id: '', message: '请创作以下主题的内容：\n${input.message}' } },
        { id: 'tpl_audit', type: 'agent', label: '合规审核', x: 300, y: 160, config: { agent_id: '', message: '请审核以下内容是否合规并输出审核结论：\n${tpl_create.result}' } },
        { id: 'tpl_out3', type: 'output', label: '审核结果输出', x: 540, y: 160, config: {} },
      ],
      edges: [
        { id: 'e_create', from: 'tpl_create', to: 'tpl_audit' },
        { id: 'e_audit', from: 'tpl_audit', to: 'tpl_out3' },
      ],
    } },
  { name: '客户 Onboarding', description: '需求分析→方案配置→上线计划输出', icon: UserCheck, color: 'from-violet-500 to-purple-600',
    defaults: { name: '客户 Onboarding', description: '新客户注册、需求对接、系统配置、培训上线的标准流程' },
    definition: {
      nodes: [
        { id: 'tpl_analyze', type: 'agent', label: '需求分析', x: 60, y: 160, config: { agent_id: '', message: '请分析以下客户需求并输出需求清单：\n${input.message}' } },
        { id: 'tpl_plan2', type: 'agent', label: '方案配置', x: 300, y: 160, config: { agent_id: '', message: '根据以下需求清单输出系统配置与上线计划：\n${tpl_analyze.result}' } },
        { id: 'tpl_out4', type: 'output', label: '上线计划输出', x: 540, y: 160, config: {} },
      ],
      edges: [
        { id: 'e_analyze', from: 'tpl_analyze', to: 'tpl_plan2' },
        { id: 'e_plan2', from: 'tpl_plan2', to: 'tpl_out4' },
      ],
    } },
]


// Workflow 卡片组件
function WorkflowCard({ workflow, onView, onEdit, onDelete, viewMode }) {
  const nodeCount = workflow.nodes?.length || 0
  const execCount = workflow.execution_count || 0
  const successRate = workflow.success_rate != null ? `${Math.round(workflow.success_rate * 100)}%` : null

  if (viewMode === 'list') {
    return (
      <div
        className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex items-center gap-4 cursor-pointer"
        onClick={() => onView(workflow)}
      >
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white flex-shrink-0">
          <Workflow className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{workflow.name}</h3>
            <Badge status={workflow.status || 'inactive'} dot />
          </div>
          <p className="text-sm text-gray-500 truncate">{workflow.description || '暂无描述'}</p>
        </div>
        <div className="hidden sm:flex items-center gap-4 text-sm text-gray-500 flex-shrink-0">
          <span className="flex items-center gap-1" title="执行次数">
            <BarChart3 className="w-4 h-4" />{execCount} 次
          </span>
          {successRate && (
            <span className="flex items-center gap-1" title="成功率">
              <CheckCircle2 className="w-4 h-4" />{successRate}
            </span>
          )}
          <span className="flex items-center gap-1"><Clock className="w-4 h-4" />{formatRelativeTime(workflow.created_at)}</span>
          <span className="flex items-center gap-1"><Folder className="w-4 h-4" />{nodeCount} 节点</span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => onView(workflow)} className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors" title="打开">
            <Play className="w-4 h-4" />
          </button>
          <button onClick={() => onEdit(workflow)} className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors" title="编辑">
            <Edit2 className="w-4 h-4" />
          </button>
          <button onClick={() => onDelete(workflow)} className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors" title="删除">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 cursor-pointer group flex flex-col"
      onClick={() => onView(workflow)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white font-bold flex-shrink-0">
            <Workflow className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{workflow.name}</h3>
            <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
              <Calendar className="w-3 h-3" />
              {formatDate(workflow.created_at)}
            </p>
          </div>
        </div>
        <Badge status={workflow.status || 'inactive'} dot />
      </div>

      <p className="text-sm text-gray-600 line-clamp-2 mb-4 flex-1">
        {workflow.description || '暂无描述'}
      </p>

      {/* 执行统计 */}
      <div className="flex items-center gap-3 mb-3 text-xs text-gray-500">
        <span className="flex items-center gap-1" title="节点数">
          <Folder className="w-3.5 h-3.5" />{nodeCount} 节点
        </span>
        <span className="flex items-center gap-1" title="执行次数">
          <BarChart3 className="w-3.5 h-3.5" />{execCount} 次
        </span>
        {successRate && (
          <span className="flex items-center gap-1" title="成功率">
            <CheckCircle2 className="w-3.5 h-3.5" />{successRate}
          </span>
        )}
      </div>

      {/* 最后执行时间 */}
      {workflow.last_run && (
        <p className="text-xs text-gray-400 mb-3 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          最后执行：{formatRelativeTime(workflow.last_run)}
        </p>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <span className="text-xs text-gray-500 flex items-center gap-1">
          <Calendar className="w-3.5 h-3.5" />
          {formatRelativeTime(workflow.created_at)}
        </span>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => onView(workflow)} className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors" title="打开">
            <Play className="w-4 h-4" />
          </button>
          <button onClick={() => onEdit(workflow)} className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors" title="编辑">
            <Edit2 className="w-4 h-4" />
          </button>
          <button onClick={() => onDelete(workflow)} className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors" title="删除">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// 表单模态框（创建/编辑共用）
function WorkflowFormModal({ open, onClose, onSubmit, editing, defaults, loading }) {
  const [form, setForm] = useState({ name: '', description: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      if (editing) {
        setForm({
          name: editing?.name || '',
          description: editing?.description || '',
        })
      } else if (defaults) {
        setForm({ name: defaults.name || '', description: defaults.description || '' })
      } else {
        setForm({ name: '', description: '' })
      }
      setErrors({})
    }
  }, [open, editing, defaults])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入工作流名称'
    if (form.name.length > 50) e.name = '名称不能超过 50 个字符'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim(), definition: defaults?.definition })
  }

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑工作流' : '新建工作流'}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={loading}>{editing ? '保存' : '创建'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        {defaults?.definition && !editing && (
          <div className="p-3 rounded-xl bg-violet-50 border border-violet-200 text-xs text-violet-700 flex items-center gap-2">
            <GitBranch className="w-4 h-4 flex-shrink-0" />
            该模板已预置完整节点编排，创建后可直接点击「执行」体验
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">名称 <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：代码审查工作流"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <textarea
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            rows={3}
            placeholder="简要描述工作流的用途"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
      </div>
    </Modal>
  )
}

export default function WorkflowsPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [workflows, setWorkflows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('grid')
  const [filter, setFilter] = useState('all')
  const [formDefaults, setFormDefaults] = useState(null)

  const [showForm, setShowForm] = useState(false)
  const [editingWorkflow, setEditingWorkflow] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchWorkflows = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/workflows')
      setWorkflows(res.data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchWorkflows()
  }, [fetchWorkflows])

  const filteredWorkflows = workflows.filter((w) => {
    const matchSearch = w.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.description?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchFilter = filter === 'all' ||
      (filter === 'active' && (w.status || 'inactive') === 'active') ||
      (filter === 'inactive' && (w.status || 'inactive') === 'inactive') ||
      (filter === 'draft' && (w.status || 'inactive') === 'draft') ||
      (filter === 'paused' && (w.status || 'inactive') === 'paused') ||
      (filter === 'archived' && (w.status || 'inactive') === 'archived')
    return matchSearch && matchFilter
  })

  const openCreate = () => {
    setEditingWorkflow(null)
    setFormDefaults(null)
    setShowForm(true)
  }
  const openEdit = (workflow) => {
    setEditingWorkflow(workflow)
    setShowForm(true)
  }

  const handleSave = async (formData) => {
    setSaving(true)
    try {
      if (editingWorkflow) {
        await api.put(`/api/workflows/${editingWorkflow.id}`, formData)
        toast.success(`工作流「${formData.name}」已更新`)
      } else {
        const res = await api.post('/api/workflows', {
          name: formData.name,
          description: formData.description,
          definition: formData.definition || { nodes: [], edges: [] },
        })
        toast.success(`工作流「${formData.name}」已创建`)
        // 创建后直接进入编辑器编排 / 执行
        setShowForm(false)
        navigate(`/workflows/${res.data.id}`)
        return
      }
      setShowForm(false)
      fetchWorkflows()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/workflows/${deleteTarget.id}`)
      toast.success(`工作流「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      fetchWorkflows()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const handleView = (workflow) => {
    navigate(`/workflows/${workflow.id}`)
  }

  const totalExecutions = workflows.reduce((sum, w) => sum + (w.execution_count || 0), 0)
  const avgSuccess = workflows.filter(w => w.success_rate != null)
  const avgRate = avgSuccess.length > 0
    ? Math.round(avgSuccess.reduce((s, w) => s + w.success_rate, 0) / avgSuccess.length * 100)
    : null

  const stats = [
    { label: '总工作流', value: workflows.length, icon: Workflow, color: 'from-violet-500 to-purple-600' },
    { label: '运行中', value: workflows.filter((w) => (w.status || 'inactive') === 'active').length, icon: Play, color: 'from-emerald-500 to-green-600' },
    { label: '总执行次数', value: totalExecutions, icon: BarChart3, color: 'from-blue-500 to-cyan-600' },
    { label: '平均成功率', value: avgRate != null ? `${avgRate}%` : '-', icon: CheckCircle2, color: 'from-amber-500 to-orange-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Workflow 管理"
        description="创建工作流，编排多 Agent 协作"
        icon={Workflow}
        actions={
          <Button variant="primary" icon={Plus} onClick={openCreate}>新建工作流</Button>
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

      {/* 快速模板（仅在工作流为空时显示） */}
      {workflows.length === 0 && !loading && !error && (
        <div className="bg-gradient-to-r from-violet-50 to-purple-50 rounded-2xl border border-violet-200/50 p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <Workflow className="w-4 h-4 text-violet-500" />
            从模板快速创建
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {WORKFLOW_TEMPLATES.map((tpl) => (
              <button
                key={tpl.name}
                onClick={() => { setFormDefaults({ ...tpl.defaults, definition: tpl.definition }); setShowForm(true) }}
                className="bg-white rounded-xl p-4 border border-gray-200 hover:border-violet-300 hover:shadow-md transition-all text-left group"
              >
                <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tpl.color} flex items-center justify-center text-white mb-3`}>
                  <tpl.icon className="w-4.5 h-4.5" />
                </div>
                <h4 className="text-sm font-semibold text-gray-800 mb-1">{tpl.name}</h4>
                <p className="text-xs text-gray-500 line-clamp-2">{tpl.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索工作流名称或描述…"
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all text-sm"
          >
            <option value="all">全部状态</option>
            <option value="active">运行中</option>
            <option value="inactive">已停止</option>
            <option value="draft">草稿</option>
            <option value="paused">已暂停</option>
            <option value="archived">已归档</option>
          </select>
          <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
              title="网格视图"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
              title="列表视图"
            >
              <ListIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={fetchWorkflows} />
      ) : filteredWorkflows.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Workflow}
            title={searchQuery || filter !== 'all' ? '未找到匹配的工作流' : '暂无工作流'}
            description={searchQuery || filter !== 'all' ? '尝试调整搜索或筛选条件' : '创建一个工作流来编排多 Agent 协作'}
            actionLabel={searchQuery || filter !== 'all' ? undefined : '新建工作流'}
            onAction={searchQuery || filter !== 'all' ? undefined : openCreate}
          />
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredWorkflows.map((workflow) => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              onView={handleView}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              viewMode="grid"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredWorkflows.map((workflow) => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              onView={handleView}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              viewMode="list"
            />
          ))}
        </div>
      )}

      <WorkflowFormModal
        open={showForm}
        onClose={() => { setShowForm(false); setFormDefaults(null) }}
        onSubmit={handleSave}
        editing={editingWorkflow}
        defaults={formDefaults}
        loading={saving}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除工作流"
        message={`确定要删除工作流「${deleteTarget?.name}」吗？此操作不可撤销。`}
        confirmLabel="确认删除"
      />
    </div>
  )
}
