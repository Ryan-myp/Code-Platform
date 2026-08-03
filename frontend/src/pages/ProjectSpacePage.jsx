import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  FolderKanban, Plus, RefreshCw, ArrowLeft,
  Image as ImageIcon, Film, Music, FileText, ListTodo, Package,
  Calendar, Eye, Play, Trash2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { formatDateTime, formatDate } from '../lib/format'
import {
  Modal, Button, Empty, SkeletonGrid, ErrorState,
  Badge, PageHeader, ConfirmDialog,
} from '../components/ui'

// 媒体资源前缀（与 api 实例 baseURL 保持一致，避免硬编码 localhost）
const MEDIA_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

// 项目状态自定义映射
const PROJECT_STATUS_MAP = {
  planning:  { text: '规划中', cls: 'bg-blue-100 text-blue-700' },
  active:    { text: '进行中', cls: 'bg-emerald-100 text-emerald-700' },
  completed: { text: '已完成', cls: 'bg-gray-100 text-gray-600' },
  archived:  { text: '已归档', cls: 'bg-gray-100 text-gray-600' },
  draft:     { text: '草稿', cls: 'bg-gray-100 text-gray-600' },
}

// 按类型分组的元数据
const TYPE_META = {
  image:   { label: '图片',   icon: ImageIcon, color: 'pink',   bg: 'bg-pink-50',   text: 'text-pink-700',   border: 'border-pink-200' },
  video:   { label: '视频',   icon: Film,      color: 'purple', bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  audio:   { label: '音频',   icon: Music,     color: 'amber',  bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-200' },
  lyrics:  { label: '歌词',   icon: FileText,  color: 'indigo', bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  prd:     { label: 'PRD',    icon: FileText,  color: 'emerald',bg: 'bg-emerald-50',text: 'text-emerald-700',border: 'border-emerald-200' },
  review:  { label: '审查报告', icon: FileText, color: 'orange', bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  td:      { label: '技术方案', icon: FileText, color: 'blue',   bg: 'bg-blue-50',   text: 'text-blue-700',   border: 'border-blue-200' },
  test:    { label: '测试用例', icon: FileText, color: 'cyan',   bg: 'bg-cyan-50',   text: 'text-cyan-700',   border: 'border-cyan-200' },
  code:    { label: '代码',    icon: FileText,  color: 'gray',   bg: 'bg-gray-50',   text: 'text-gray-700',   border: 'border-gray-200' },
  doc:     { label: '文档',    icon: FileText,  color: 'slate',  bg: 'bg-slate-50',  text: 'text-slate-700',  border: 'border-slate-200' },
}

const getTypeMeta = (t) => TYPE_META[t] || { label: t || '其他', icon: FileText, color: 'gray', bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' }

export default function ProjectSpacePage() {
  const { id: projectId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [projects, setProjects] = useState([])
  const [current, setCurrent] = useState(null)
  const [artifacts, setArtifacts] = useState([])
  const [requirements, setRequirements] = useState([])
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ name: '', description: '' })
  const [formErrors, setFormErrors] = useState({})
  const [selectedArtifact, setSelectedArtifact] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchProjects = useCallback(async () => {
    try {
      const res = await api.get('/api/projects')
      setProjects(res.data || [])
      return res.data || []
    } catch (e) {
      setError(e)
      return []
    }
  }, [])

  const fetchProjectSpace = useCallback(async (pid) => {
    setLoading(true)
    setError(null)
    try {
      const [projRes, artRes, reqRes] = await Promise.all([
        api.get('/api/projects'),
        api.get(`/api/projects/${pid}/artifacts`),
        api.get('/api/requirements'),
      ])
      const projList = projRes.data || []
      const proj = projList.find((p) => p.id === pid)
      setCurrent(proj || { id: pid, name: '未知项目' })
      setArtifacts(artRes.data || [])
      setRequirements((reqRes.data || []).filter((r) => r.project_id === pid))
      // tasks 接口可能不存在，按 project_id 过滤兜底
      try {
        const taskRes = await api.get('/api/tasks')
        setTasks((taskRes.data || []).filter((t) => t.project_id === pid))
      } catch {
        setTasks([])
      }
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (projectId) {
      fetchProjectSpace(projectId)
    } else {
      setLoading(true)
      Promise.all([fetchProjects(), api.get('/api/requirements')])
        .then(([_, reqRes]) => setRequirements(reqRes.data || []))
        .catch(() => setError(new Error('加载数据失败')))
        .finally(() => setLoading(false))
    }
  }, [projectId, fetchProjects, fetchProjectSpace])

  const openCreate = () => {
    setForm({ name: '', description: '' })
    setFormErrors({})
    setShowCreate(true)
  }

  const handleCreate = async () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入项目名称'
    else if (form.name.length > 60) e.name = '名称不能超过 60 个字符'
    setFormErrors(e)
    if (Object.keys(e).length > 0) return

    setSaving(true)
    try {
      const res = await api.post('/api/projects', { name: form.name.trim(), description: form.description.trim() })
      toast.success(`项目「${form.name.trim()}」已创建`)
      setShowCreate(false)
      navigate(`/projects/${res.data.id}`)
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/projects/${deleteTarget.id}`)
      toast.success(`项目「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      navigate('/projects')
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  // ── 项目列表视图 ───────────────────────────────────────────
  if (!projectId) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="项目空间"
          description="按项目聚合需求、任务和创作产物（图片/视频/音频/文档）"
          icon={FolderKanban}
          iconColor="from-indigo-500 to-blue-600"
          actions={
            <>
              <Button variant="secondary" icon={RefreshCw} onClick={fetchProjects}>刷新</Button>
              <Button variant="primary" icon={Plus} onClick={openCreate}>新建项目</Button>
            </>
          }
        />

        {loading ? (
          <SkeletonGrid count={6} />
        ) : error ? (
          <ErrorState message={`加载失败：${error.message}`} onRetry={fetchProjects} />
        ) : projects.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-200">
            <Empty
              icon={FolderKanban}
              title="暂无项目"
              description="点击「新建项目」开始组织你的需求和创作产物"
              actionLabel="新建项目"
              onAction={openCreate}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((proj) => {
              const reqCount = requirements.filter((r) => r.project_id === proj.id).length
              return (
                <div
                  key={proj.id}
                  onClick={() => navigate(`/projects/${proj.id}`)}
                  className="p-5 bg-white border border-gray-200 rounded-2xl hover:shadow-lg hover:border-indigo-300 transition-all cursor-pointer group flex flex-col"
                >
                  <div className="flex items-center justify-between mb-3">
                    <FolderKanban className="w-6 h-6 text-indigo-600 group-hover:scale-110 transition-transform" />
                    <Badge status={proj.status || 'planning'} customMap={PROJECT_STATUS_MAP} dot />
                  </div>
                  <h3 className="font-semibold text-gray-900 group-hover:text-indigo-700">{proj.name}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2 flex-1">{proj.description || '暂无描述'}</p>
                  <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
                    <span className="flex items-center gap-1"><ListTodo className="w-3 h-3" />{reqCount} 需求</span>
                    <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{proj.created_at ? formatDate(proj.created_at) : '—'}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* 新建项目 Modal */}
        <Modal
          open={showCreate}
          onClose={() => setShowCreate(false)}
          title="新建项目"
          size="md"
          footer={
            <>
              <Button variant="secondary" onClick={() => setShowCreate(false)}>取消</Button>
              <Button variant="primary" loading={saving} onClick={handleCreate}>创建</Button>
            </>
          }
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">项目名称 <span className="text-red-500">*</span></label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="例如：电商平台项目"
                className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${formErrors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-indigo-500/20 focus:border-indigo-500'}`}
              />
              {formErrors.name && <p className="text-xs text-red-500 mt-1">{formErrors.name}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
                placeholder="描述这个项目…"
                className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
              />
            </div>
          </div>
        </Modal>
      </div>
    )
  }

  // ── 项目空间详情视图 ─────────────────────────────────────
  const grouped = {}
  artifacts.forEach((a) => {
    const t = a.type || 'doc'
    if (!grouped[t]) grouped[t] = []
    grouped[t].push(a)
  })
  const typeOrder = ['image', 'video', 'audio', 'lyrics', 'prd', 'review', 'td', 'test', 'code', 'doc']
  const orderedTypes = Object.keys(grouped).sort((a, b) => {
    const ia = typeOrder.indexOf(a), ib = typeOrder.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title={current?.name || '加载中…'}
        description={
          <>
            {current?.description || '暂无描述'}
            {current?.id && <span className="ml-2 font-mono text-xs text-gray-400">ID: {current.id}</span>}
          </>
        }
        icon={FolderKanban}
        iconColor="from-indigo-500 to-blue-600"
        actions={
          <>
            <Button variant="secondary" icon={ArrowLeft} onClick={() => navigate('/projects')}>返回</Button>
            <Button variant="secondary" icon={RefreshCw} onClick={() => fetchProjectSpace(projectId)}>刷新</Button>
            <Button variant="danger" icon={Trash2} onClick={() => setDeleteTarget(current)}>删除项目</Button>
          </>
        }
      />

      {loading ? (
        <SkeletonGrid count={4} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={() => fetchProjectSpace(projectId)} />
      ) : (
        <>
          {/* 概览统计 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="总产物" value={artifacts.length} icon={Package} color="indigo" />
            <StatCard label="需求数" value={requirements.length} icon={ListTodo} color="emerald" />
            <StatCard label="任务数" value={tasks.length} icon={ListTodo} color="amber" />
            <StatCard label="创作产物" value={['image', 'video', 'audio', 'lyrics'].reduce((s, t) => s + (grouped[t]?.length || 0), 0)} icon={ImageIcon} color="pink" />
          </div>

          {/* 需求列表 */}
          {requirements.length > 0 && (
            <Section title={`需求 (${requirements.length})`} icon={ListTodo} color="emerald">
              <div className="space-y-2">
                {requirements.map((req) => (
                  <div key={req.id} className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg hover:bg-gray-50">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-gray-800">{req.name}</span>
                        <Badge status={req.status || 'draft'} dot />
                        <Badge status="inactive" label={req.priority || 'P2'} />
                      </div>
                      {req.description && <p className="text-xs text-gray-500 mt-1 line-clamp-1">{req.description}</p>}
                    </div>
                    <span className="text-xs text-gray-400 ml-2 flex-shrink-0">{req.created_at ? formatDate(req.created_at) : ''}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* 任务列表 */}
          {tasks.length > 0 && (
            <Section title={`任务 (${tasks.length})`} icon={ListTodo} color="amber">
              <div className="space-y-2">
                {tasks.map((task) => (
                  <div key={task.id} className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg">
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-gray-800">{task.title}</span>
                      {task.description && <p className="text-xs text-gray-500 mt-0.5">{task.description}</p>}
                    </div>
                    <Badge status={task.status || 'todo'} dot />
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* 按类型分组的产物 */}
          {orderedTypes.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty
                icon={Package}
                title="该项目暂无产物"
                description="在创作工厂生成图片/视频/音频时填入该项目 ID，产物会自动聚合到这里"
              />
            </div>
          ) : (
            orderedTypes.map((type) => {
              const meta = getTypeMeta(type)
              const arts = grouped[type]
              const Icon = meta.icon
              return (
                <Section key={type} title={`${meta.label} (${arts.length})`} icon={Icon} color={meta.color}>
                  <div className={`grid gap-3 ${
                    type === 'image' ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6' :
                    type === 'video' ? 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3' :
                    'grid-cols-1'
                  }`}>
                    {arts.map((art) => (
                      <ArtifactCard key={art.id} art={art} type={type} meta={meta} onView={() => setSelectedArtifact(art)} />
                    ))}
                  </div>
                </Section>
              )
            })
          )}
        </>
      )}

      {/* 产物详情 Modal */}
      <Modal
        open={!!selectedArtifact}
        onClose={() => setSelectedArtifact(null)}
        title={selectedArtifact ? `${getTypeMeta(selectedArtifact.type).label} · v${selectedArtifact.version || 1}` : ''}
        size="lg"
        footer={<Button variant="primary" onClick={() => setSelectedArtifact(null)}>关闭</Button>}
      >
        {selectedArtifact && (
          <div className="space-y-4">
            {selectedArtifact.media_url && ['image', 'video', 'audio'].includes(selectedArtifact.type) && (
              <div className="mb-2">
                {selectedArtifact.type === 'image' && (
                  <img src={`${MEDIA_BASE}${selectedArtifact.media_url}`} alt={selectedArtifact.id} className="max-w-full rounded-lg mx-auto" />
                )}
                {selectedArtifact.type === 'video' && (
                  <video src={`${MEDIA_BASE}${selectedArtifact.media_url}`} controls className="max-w-full rounded-lg mx-auto" />
                )}
                {selectedArtifact.type === 'audio' && (
                  <audio src={`${MEDIA_BASE}${selectedArtifact.media_url}`} controls className="w-full" />
                )}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <Field label="作者" value={selectedArtifact.author || '—'} />
              <Field label="创建时间" value={selectedArtifact.created_at ? formatDateTime(selectedArtifact.created_at) : '—'} />
              {selectedArtifact.duration > 0 && <Field label="时长" value={`${selectedArtifact.duration.toFixed(2)}s`} />}
              {selectedArtifact.media_url && <Field label="媒体路径" value={selectedArtifact.media_url} mono />}
            </div>
            {selectedArtifact.content && (
              <div>
                <p className="text-xs text-gray-500 mb-1">内容</p>
                <MarkdownRenderer content={selectedArtifact.content} className="max-h-80 overflow-auto" />
              </div>
            )}
            {selectedArtifact.metadata && (
              <div>
                <p className="text-xs text-gray-500 mb-1">元数据</p>
                <pre className="whitespace-pre-wrap text-xs font-mono text-gray-600 bg-gray-50 p-3 rounded-lg border">{selectedArtifact.metadata}</pre>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 删除项目确认 */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除项目"
        message={deleteTarget ? `确定要删除项目「${deleteTarget.name}」吗？项目下的需求和产物关联将失效，此操作不可撤销。` : ''}
        confirmLabel="确认删除"
      />
    </div>
  )
}

// ── 子组件 ───────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, color }) {
  const colorMap = {
    indigo: 'text-indigo-600 bg-indigo-50',
    emerald: 'text-emerald-600 bg-emerald-50',
    amber: 'text-amber-600 bg-amber-50',
    pink: 'text-pink-600 bg-pink-50',
  }
  return (
    <div className="p-4 bg-white border border-gray-200 rounded-2xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorMap[color] || colorMap.indigo}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  )
}

function Section({ title, icon: Icon, color, children }) {
  const colorMap = {
    indigo: 'text-indigo-600', emerald: 'text-emerald-600', amber: 'text-amber-600',
    pink: 'text-pink-600', purple: 'text-purple-600', blue: 'text-blue-600',
    cyan: 'text-cyan-600', orange: 'text-orange-600', gray: 'text-gray-600', slate: 'text-slate-600',
  }
  return (
    <div>
      <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-3">
        <Icon className={`w-4 h-4 ${colorMap[color] || colorMap.indigo}`} />
        {title}
      </h2>
      {children}
    </div>
  )
}

function ArtifactCard({ art, type, meta, onView }) {
  if (type === 'image' && art.media_url) {
    return (
      <div onClick={onView} className="group relative aspect-square bg-gray-100 rounded-lg overflow-hidden cursor-pointer hover:shadow-md transition-all border border-gray-200">
        <img src={`${MEDIA_BASE}${art.media_url}`} alt={art.id} className="w-full h-full object-cover group-hover:scale-105 transition-transform" loading="lazy" />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
          <Eye className="w-5 h-5 text-white opacity-0 group-hover:opacity-100" />
        </div>
      </div>
    )
  }
  if (type === 'video' && art.media_url) {
    return (
      <div onClick={onView} className="group bg-gray-900 rounded-lg overflow-hidden cursor-pointer hover:shadow-md transition-all border border-gray-200">
        <div className="aspect-video flex items-center justify-center relative">
          <video src={`${MEDIA_BASE}${art.media_url}`} className="w-full h-full object-cover" preload="metadata" muted />
          <div className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:bg-black/40">
            <Play className="w-10 h-10 text-white fill-white" />
          </div>
        </div>
        <div className="p-2 bg-white">
          <p className="text-xs text-gray-500 truncate font-mono">{art.id?.slice(0, 16)}</p>
          {art.duration > 0 && <p className="text-xs text-gray-400">{art.duration.toFixed(1)}s</p>}
        </div>
      </div>
    )
  }
  if (type === 'audio' && art.media_url) {
    return (
      <div onClick={onView} className="p-3 bg-white border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 flex items-center gap-3">
        <div className={`w-10 h-10 ${meta.bg} ${meta.text} rounded-lg flex items-center justify-center flex-shrink-0`}>
          <Music className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate font-mono">{art.id?.slice(0, 20)}</p>
          <p className="text-xs text-gray-400">{art.duration ? art.duration.toFixed(1) + 's' : ''}</p>
        </div>
        <Play className="w-4 h-4 text-gray-400" />
      </div>
    )
  }
  return (
    <div onClick={onView} className="p-3 bg-white border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 flex items-start gap-3">
      <div className={`w-10 h-10 ${meta.bg} ${meta.text} rounded-lg flex items-center justify-center flex-shrink-0`}>
        <FileText className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-800">{meta.label}</span>
          <span className="text-xs text-gray-400">v{art.version || 1}</span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{art.content || '(无内容预览)'}</p>
        <p className="text-xs text-gray-400 mt-1">{art.created_at ? formatDateTime(art.created_at) : ''}</p>
      </div>
    </div>
  )
}

function Field({ label, value, mono }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-sm text-gray-800 break-all ${mono ? 'font-mono text-xs' : ''}`}>{value}</p>
    </div>
  )
}
