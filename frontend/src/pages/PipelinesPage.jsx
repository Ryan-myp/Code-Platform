import React, { useState, useEffect, useCallback } from 'react'
import {
  GitBranch, Plus, Play, Trash2, Clock, Edit2, Terminal, RefreshCw,
  CheckCircle2, XCircle, CircleDashed, Rocket, FlaskConical, Package, Workflow,
  Server, ExternalLink, Wrench, Loader2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import {
  Modal, Button, Empty, SkeletonGrid, ErrorState, ColorBadge, PageHeader, ConfirmDialog,
} from '../components/ui'

const PIPELINE_TYPES = [
  { value: 'ci', label: 'CI 持续集成', icon: Workflow, color: 'blue', badge: 'blue' },
  { value: 'cd', label: 'CD 持续部署', icon: Rocket, color: 'green', badge: 'green' },
  { value: 'test', label: '自动化测试', icon: FlaskConical, color: 'purple', badge: 'purple' },
  { value: 'build', label: '构建打包', icon: Package, color: 'amber', badge: 'amber' },
  // deploy 类型由 AI 工作台「一键部署」自动创建（代码落盘 → 构建镜像 → 沙箱容器运行）
  { value: 'deploy', label: '沙箱部署', icon: Server, color: 'orange', badge: 'amber' },
]

const typeMeta = (type) => PIPELINE_TYPES.find((t) => t.value === type) || PIPELINE_TYPES[0]

const RUN_STATUS = {
  success: { label: '运行成功', icon: CheckCircle2, cls: 'bg-emerald-50 text-emerald-600 border-emerald-200' },
  failed: { label: '运行失败', icon: XCircle, cls: 'bg-red-50 text-red-600 border-red-200' },
  running: { label: '运行中', icon: CircleDashed, cls: 'bg-blue-50 text-blue-600 border-blue-200' },
}

// 运行状态徽章
function RunStatusBadge({ run }) {
  if (!run) {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-50 text-gray-400 border border-gray-200">未运行</span>
  }
  const meta = RUN_STATUS[run.status] || RUN_STATUS.running
  const Icon = meta.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${meta.cls}`}>
      <Icon className="w-3 h-3" />
      {meta.label}
    </span>
  )
}

// 新建/编辑弹窗
function PipelineFormModal({ open, onClose, onSubmit, editing, loading }) {
  const [form, setForm] = useState({ name: '', description: '', type: 'ci', repo: '', test_path: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (!open) return
    const cfg = editing?.config || {}
    setForm({
      name: editing?.name || '',
      description: editing?.description || '',
      type: editing?.type || 'ci',
      repo: cfg.repo || '',
      test_path: cfg.test_path || '',
    })
    setErrors({})
  }, [open, editing])

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  const handleSubmit = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入流水线名称'
    if (form.name.length > 60) e.name = '名称不能超过 60 个字符'
    setErrors(e)
    if (Object.keys(e).length > 0) return
    const config = {}
    if (form.repo.trim()) config.repo = form.repo.trim()
    if (form.test_path.trim()) config.test_path = form.test_path.trim()
    onSubmit({
      name: form.name.trim(),
      description: form.description.trim(),
      type: form.type,
      config,
    })
  }

  const inputCls = (err) =>
    `w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${
      err ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-blue-500/20 focus:border-blue-500'
    }`

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑流水线' : '新建流水线'}
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
            placeholder="例如：主分支 CI 流水线"
            className={inputCls(errors.name)}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <textarea
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            rows={2}
            placeholder="简要说明流水线的用途"
            className={inputCls(false)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">类型</label>
          <div className="grid grid-cols-2 gap-2">
            {PIPELINE_TYPES.filter((t) => t.value !== 'deploy').map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setField('type', t.value)}
                className={`px-3 py-2 rounded-xl text-sm font-medium border transition-all flex items-center justify-center gap-1.5 ${
                  form.type === t.value
                    ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <t.icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-4 space-y-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">执行配置（可选）</p>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">代码仓库地址</label>
            <input
              type="text"
              value={form.repo}
              onChange={(e) => setField('repo', e.target.value)}
              placeholder="https://github.com/org/repo.git"
              className={inputCls(false)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">测试路径</label>
            <input
              type="text"
              value={form.test_path}
              onChange={(e) => setField('test_path', e.target.value)}
              placeholder="tests/（默认）"
              className={inputCls(false)}
            />
          </div>
        </div>
      </div>
    </Modal>
  )
}

// 运行日志弹窗
function RunLogModal({ pipeline, onClose }) {
  const toast = useToast()
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!pipeline) return
    let alive = true
    let timer = null
    const fetchRuns = async () => {
      try {
        const res = await api.get(`/api/pipelines/${pipeline.id}/runs`)
        if (!alive) return
        setRuns(res.data)
        setSelected((prev) => prev || res.data[0] || null)
        // 所有运行均已结束则停止轮询（运行中时每 3s 刷新，实时展示部署进度）
        if (res.data.length > 0 && res.data.every((r) => r.status !== 'running')) clearInterval(timer)
      } catch (e) {
        if (alive) toast.error(`加载运行历史失败：${e.message}`)
      } finally {
        if (alive) setLoading(false)
      }
    }
    fetchRuns()
    timer = setInterval(fetchRuns, 3000)
    return () => { alive = false; clearInterval(timer) }
  }, [pipeline]) // eslint-disable-line react-hooks/exhaustive-deps

  const hasSuccess = runs.some((r) => r.status === 'success')

  return (
    <Modal open={!!pipeline} onClose={onClose} title={`运行日志 - ${pipeline?.name || ''}`} size="lg">
      {/* deploy 流水线：展示沙箱服务访问地址 */}
      {pipeline?.type === 'deploy' && pipeline?.config?.port && (
        <div className={`mb-4 px-4 py-3 rounded-xl border flex items-center justify-between gap-3 ${hasSuccess ? 'bg-emerald-50 border-emerald-200' : 'bg-gray-50 border-gray-200'}`}>
          <span className="text-sm text-gray-600">沙箱服务访问地址</span>
          {hasSuccess ? (
            <a href={`http://localhost:${pipeline.config.port}`} target="_blank" rel="noreferrer" className="text-sm font-medium text-emerald-600 hover:underline flex items-center gap-1">
              <ExternalLink className="w-3.5 h-3.5" /> http://localhost:{pipeline.config.port}
            </a>
          ) : (
            <span className="text-sm text-gray-400">部署成功后可访问</span>
          )}
        </div>
      )}
      {loading ? (
        <div className="py-12 text-center text-gray-400 text-sm">加载中…</div>
      ) : runs.length === 0 ? (
        <div className="py-12 text-center text-gray-400 text-sm">暂无运行记录，点击卡片上的「运行」按钮开始</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1 space-y-2 max-h-[50vh] overflow-y-auto pr-1">
            {runs.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className={`w-full text-left p-3 rounded-xl border transition-all ${
                  selected?.id === r.id ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <RunStatusBadge run={r} />
                  <span className="text-[10px] text-gray-400 font-mono">{r.id.slice(-8)}</span>
                </div>
                <p className="text-xs text-gray-500">{formatRelativeTime(r.started_at)}</p>
              </button>
            ))}
          </div>
          <div className="lg:col-span-2">
            {selected && (
              <pre className="bg-gray-900 text-green-400 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[50vh] whitespace-pre-wrap">
                {selected.log || '（无日志输出）'}
              </pre>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}

export default function PipelinesPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [saving, setSaving] = useState(false)
  const [runningId, setRunningId] = useState(null)
  const [fixingId, setFixingId] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [logTarget, setLogTarget] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/pipelines')
      setItems(res.data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async (payload) => {
    setSaving(true)
    try {
      if (editingItem) {
        await api.put(`/api/pipelines/${editingItem.id}`, payload)
        toast.success(`流水线「${payload.name}」已更新`)
      } else {
        await api.post('/api/pipelines', payload)
        toast.success(`流水线「${payload.name}」已创建`)
      }
      setShowForm(false)
      setEditingItem(null)
      load()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleRun = async (p) => {
    setRunningId(p.id)
    try {
      await api.post(`/api/pipelines/${p.id}/run`)
      toast.success(`「${p.name}」执行成功`)
      load()
    } catch (e) {
      toast.error(`执行失败：${e.message}`)
    } finally {
      setRunningId(null)
    }
  }

  // AI 诊断修复：拉取容器日志 → LLM 修改代码 → 重建 → 重启 → 健康检查
  const handleAutoFix = async (p) => {
    setFixingId(p.id)
    try {
      await api.post(`/api/pipelines/${p.id}/auto-fix`)
      toast.success('AI 诊断修复已启动，正在分析日志并修复代码…')
      setLogTarget(p)
      load()
    } catch (e) {
      toast.error(`AI 修复启动失败：${e.message}`)
    } finally {
      setFixingId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return false
    try {
      await api.delete(`/api/pipelines/${deleteTarget.id}`)
      toast.success(`流水线「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      load()
      return true
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
      return false
    }
  }

  const openCreate = () => { setEditingItem(null); setShowForm(true) }
  const openEdit = (p) => { setEditingItem(p); setShowForm(true) }

  const stats = [
    { label: '流水线总数', value: items.length, icon: GitBranch, color: 'from-blue-500 to-indigo-600' },
    { label: 'CI 集成', value: items.filter((i) => i.type === 'ci').length, icon: Workflow, color: 'from-cyan-500 to-blue-600' },
    { label: 'CD 部署', value: items.filter((i) => i.type === 'cd').length, icon: Rocket, color: 'from-emerald-500 to-green-600' },
    { label: '测试/构建', value: items.filter((i) => i.type === 'test' || i.type === 'build').length, icon: FlaskConical, color: 'from-amber-500 to-orange-600' },
    { label: '运行成功', value: items.filter((i) => i.last_run?.status === 'success').length, icon: CheckCircle2, color: 'from-rose-500 to-pink-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="CI/CD 流水线"
        description="管理持续集成、部署、测试与构建流水线，支持一键运行并查看执行日志"
        icon={GitBranch}
        iconColor="from-blue-500 to-indigo-600"
        actions={
          <Button variant="primary" icon={Plus} onClick={openCreate}>新建流水线</Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
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

      {/* Content */}
      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={load} />
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={GitBranch}
            title="暂无流水线"
            description="点击「新建流水线」创建你的第一条流水线"
            actionLabel="新建流水线"
            onAction={openCreate}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((p) => {
            const meta = typeMeta(p.type)
            return (
              <div key={p.id} className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 flex flex-col">
                <div className="flex items-start justify-between mb-3">
                  <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${meta.color === 'blue' ? 'from-blue-500 to-indigo-600' : meta.color === 'green' ? 'from-emerald-500 to-green-600' : meta.color === 'purple' ? 'from-purple-500 to-violet-600' : 'from-amber-500 to-orange-600'} flex items-center justify-center text-white shadow-lg`}>
                    <meta.icon className="w-5 h-5" />
                  </div>
                  <ColorBadge color={meta.badge}>{meta.label}</ColorBadge>
                </div>
                <h3 className="font-semibold text-gray-900 mb-1">{p.name}</h3>
                {p.description && <p className="text-sm text-gray-500 line-clamp-2 mb-2">{p.description}</p>}
                <div className="flex items-center gap-2 mb-3">
                  <RunStatusBadge run={p.last_run} />
                  {p.last_run && (
                    <span className="text-xs text-gray-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatRelativeTime(p.last_run.started_at)}
                    </span>
                  )}
                </div>
                {p.type === 'deploy' && p.last_run?.status === 'success' && p.config?.port && (
                  <a href={`http://localhost:${p.config.port}`} target="_blank" rel="noreferrer" className="text-xs text-emerald-600 hover:underline flex items-center gap-1 mb-3">
                    <ExternalLink className="w-3 h-3" /> http://localhost:{p.config.port}
                  </a>
                )}
                {p.type === 'deploy' && p.config?.service_name && (
                  <div className="rounded-xl bg-amber-50/60 border border-amber-100 p-3 mb-3 space-y-1 text-xs">
                    <p className="font-medium text-amber-700 flex items-center gap-1.5">
                      <Package className="w-3.5 h-3.5" /> 部署项目: {p.config.service_name}
                    </p>
                    <p className="text-gray-500 flex items-center gap-1.5 truncate" title={p.config.project_dir}>
                      <GitBranch className="w-3 h-3 flex-shrink-0" /> 代码目录: {p.config.project_dir?.split('/').slice(-2).join('/')}
                    </p>
                    <p className="text-gray-500 flex items-center gap-1.5">
                      <Server className="w-3 h-3 flex-shrink-0" /> 服务端口: {p.config.port}
                      {p.config.requirement_name && <> · 需求: {p.config.requirement_name}</>}
                    </p>
                  </div>
                )}
                <div className="mt-auto flex items-center justify-between pt-4 border-t border-gray-100">
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatRelativeTime(p.created_at)}
                  </span>
                  <div className="flex items-center gap-1">
                    {p.type === 'deploy' && p.last_run?.status === 'failed' && (
                      <button
                        onClick={() => handleAutoFix(p)}
                        disabled={fixingId === p.id}
                        className="px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-orange-600 text-white text-xs font-medium hover:opacity-90 transition-colors flex items-center gap-1 disabled:opacity-60"
                        title="AI 诊断修复：分析日志、修改代码并重新部署"
                      >
                        {fixingId === p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wrench className="w-3.5 h-3.5" />}
                        AI 修复
                      </button>
                    )}
                    <button
                      onClick={() => handleRun(p)}
                      disabled={runningId === p.id}
                      className="px-2.5 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors flex items-center gap-1 disabled:opacity-60"
                      title="运行流水线"
                    >
                      {runningId === p.id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                      运行
                    </button>
                    <button
                      onClick={() => setLogTarget(p)}
                      className="p-2 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded-lg transition-colors"
                      title="运行日志"
                    >
                      <Terminal className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => openEdit(p)}
                      className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
                      title="编辑"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setDeleteTarget(p)}
                      className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <PipelineFormModal
        open={showForm}
        onClose={() => { setShowForm(false); setEditingItem(null) }}
        onSubmit={handleSave}
        editing={editingItem}
        loading={saving}
      />

      <RunLogModal pipeline={logTarget} onClose={() => setLogTarget(null)} />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除流水线"
        message={<>确定要删除流水线「<span className="font-medium text-gray-700">{deleteTarget?.name}</span>」吗？运行历史将一并清除。</>}
        confirmLabel="确认删除"
      />
    </div>
  )
}
