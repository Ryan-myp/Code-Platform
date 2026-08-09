import React, { useState, useEffect, useCallback } from 'react'
import {
  Package,
  RefreshCw,
  Eye,
  FolderKanban,
  ListTodo,
  Search,
  ChevronDown,
  ChevronRight,
  Download,
  Trash2,
  FileText,
  LayoutGrid,
  List as ListIcon,
  Clock,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { formatDateTime, formatRelativeTime } from '../lib/format'
import {
  Modal,
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  Badge,
  PageHeader,
  ConfirmDialog,
} from '../components/ui'
import ShareButton from '../components/ShareButton'

const TYPE_META = {
  prd: { label: 'PRD', icon: '📋', color: 'blue' },
  review: { label: '审查报告', icon: '🔍', color: 'orange' },
  td: { label: '技术方案', icon: '📐', color: 'cyan' },
  test: { label: '测试用例', icon: '🧪', color: 'amber' },
  code: { label: '代码', icon: '💻', color: 'gray' },
  doc: { label: '文档', icon: '📄', color: 'slate' },
}

const getTypeMeta = (t) => TYPE_META[t] || { label: t || '其他', icon: '📄', color: 'gray' }

const VIEW_MODES = [
  { key: 'tree', label: '树形', icon: LayoutGrid },
  { key: 'list', label: '列表', icon: ListIcon },
  { key: 'timeline', label: '时间线', icon: Clock },
]

export default function ArtifactsPage() {
  const toast = useToast()
  const [artifacts, setArtifacts] = useState([])
  const [projects, setProjects] = useState([])
  const [requirements, setRequirements] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [viewMode, setViewMode] = useState('tree')
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedProjects, setExpandedProjects] = useState({})
  const [expandedReqs, setExpandedReqs] = useState({})
  const [filterType, setFilterType] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [artRes, projRes, reqRes] = await Promise.all([
        api.get('/api/artifacts'),
        api.get('/api/projects'),
        api.get('/api/requirements'),
      ])
      setArtifacts(artRes.data || [])
      setProjects(projRes.data || [])
      setRequirements(reqRes.data || [])
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const toggleProject = (pid) => setExpandedProjects((p) => ({ ...p, [pid]: !p[pid] }))
  const toggleReq = (rid) => setExpandedReqs((p) => ({ ...p, [rid]: !p[rid] }))

  const filtered = artifacts.filter((a) => {
    const q = searchTerm.toLowerCase()
    const matchSearch =
      !q ||
      a.type?.toLowerCase().includes(q) ||
      a.requirement_id?.toLowerCase().includes(q) ||
      a.project_id?.toLowerCase().includes(q)
    const matchType = !filterType || a.type === filterType
    return matchSearch && matchType
  })

  // 按项目 -> 需求 -> 成果分组
  const groupedByProject = {}
  filtered.forEach((art) => {
    const pid = art.project_id || ''
    if (!groupedByProject[pid]) groupedByProject[pid] = {}
    const key = art.requirement_id || '__unassigned__'
    if (!groupedByProject[pid][key]) groupedByProject[pid][key] = []
    groupedByProject[pid][key].push(art)
  })

  const getProjectName = (pid) => {
    if (pid === '__unassigned__' || !pid) return '未关联项目'
    const p = projects.find((p) => p.id === pid)
    return p ? p.name : pid
  }
  const getReqName = (rid) => {
    if (rid === '__unassigned__' || !rid) return '未关联需求'
    const r = requirements.find((r) => r.id === rid)
    return r ? r.name : rid
  }

  const handleDownload = async (art) => {
    try {
      const meta = getTypeMeta(art.type)
      const content = art.content || art.content_preview || ''
      const blob = new Blob(
        [typeof content === 'string' ? content : JSON.stringify(content, null, 2)],
        {
          type: 'text/markdown;charset=utf-8',
        }
      )
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${meta.label}_${art.id}.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('已开始下载')
    } catch (e) {
      toast.error(`下载失败：${e.message}`)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/artifacts/${deleteTarget.id}`)
      toast.success(`成果「${getTypeMeta(deleteTarget.type).label}」已删除`)
      setDeleteTarget(null)
      setSelected(null)
      fetchData()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="成果仓库"
        description="按项目和需求维度查看生成的 PRD、审查报告、技术方案等"
        icon={Package}
        iconColor="from-emerald-500 to-teal-600"
        actions={
          <Button variant="secondary" icon={RefreshCw} onClick={fetchData}>
            刷新
          </Button>
        }
      />

      {/* 工具栏 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="搜索成果类型 / 需求ID / 项目ID…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all text-sm"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all text-sm bg-white"
        >
          <option value="">全部类型</option>
          {Object.entries(TYPE_META).map(([k, v]) => (
            <option key={k} value={k}>
              {v.label}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
          {VIEW_MODES.map((mode) => {
            const Icon = mode.icon
            return (
              <button
                key={mode.key}
                onClick={() => setViewMode(mode.key)}
                className={`flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg transition-all ${viewMode === mode.key ? 'bg-white shadow-sm text-emerald-700 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
              >
                <Icon className="w-3.5 h-3.5" />
                {mode.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* 内容 */}
      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={fetchData} />
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Package}
            title={searchTerm || filterType ? '未找到匹配的成果' : '暂无成果'}
            description={
              searchTerm || filterType
                ? '尝试调整搜索或筛选条件'
                : '创建需求并生成 PRD/审查报告后，成果将在此显示'
            }
          />
        </div>
      ) : viewMode === 'tree' ? (
        <div className="space-y-2">
          {Object.entries(groupedByProject).map(([projectId, reqMap]) => {
            const projectName = getProjectName(projectId)
            const isExpanded = expandedProjects[projectId]
            const totalCount = Object.values(reqMap).reduce((s, arr) => s + arr.length, 0)
            return (
              <div
                key={projectId}
                className="bg-white border border-gray-200 rounded-xl overflow-hidden"
              >
                <button
                  onClick={() => toggleProject(projectId)}
                  className="w-full flex items-center gap-3 p-4 hover:bg-gray-50 transition-colors"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  )}
                  <FolderKanban className="w-5 h-5 text-amber-500" />
                  <span className="font-medium text-gray-900 truncate">{projectName}</span>
                  <Badge status="inactive" label={`${totalCount} 个成果`} className="ml-auto" />
                </button>
                {isExpanded &&
                  Object.entries(reqMap).map(([reqId, arts]) => {
                    const reqName = getReqName(reqId)
                    const reqExpanded = expandedReqs[reqId]
                    return (
                      <div key={reqId} className="ml-6 border-l-2 border-gray-100 pl-4 py-2">
                        <button
                          onClick={() => toggleReq(reqId)}
                          className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 py-1"
                        >
                          {reqExpanded ? (
                            <ChevronDown className="w-3 h-3" />
                          ) : (
                            <ChevronRight className="w-3 h-3" />
                          )}
                          <ListTodo className="w-4 h-4 text-gray-400" />
                          <span>{reqName}</span>
                          <span className="text-xs text-gray-400">({arts.length})</span>
                        </button>
                        {reqExpanded && (
                          <div className="ml-6 mt-2 space-y-1">
                            {arts.map((art) => {
                              const meta = getTypeMeta(art.type)
                              return (
                                <div
                                  key={art.id}
                                  className="flex items-center gap-3 p-2.5 hover:bg-gray-50 rounded-lg cursor-pointer group"
                                  onClick={() => setSelected(art)}
                                >
                                  <span className="text-lg">{meta.icon}</span>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className="text-sm font-medium text-gray-800">
                                        {meta.label}
                                      </span>
                                      <span className="text-xs text-gray-400">
                                        v{art.version || 1}
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-3 text-xs text-gray-400">
                                      <span className="font-mono">{art.id?.slice(0, 12)}…</span>
                                      <span>{formatRelativeTime(art.created_at)}</span>
                                      {art.author && <span>作者: {art.author}</span>}
                                    </div>
                                  </div>
                                  <Eye className="w-4 h-4 text-gray-300 group-hover:text-emerald-600" />
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })}
              </div>
            )
          })}
        </div>
      ) : viewMode === 'list' ? (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">类型</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">关联需求</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">版本</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">作者</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">创建时间</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map((art) => {
                const meta = getTypeMeta(art.type)
                const req = requirements.find((r) => r.id === art.requirement_id)
                const proj = projects.find((p) => p.id === art.project_id)
                return (
                  <tr key={art.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <span className="text-lg mr-1">{meta.icon}</span>
                      {meta.label}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {art.id?.slice(0, 16)}…
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-gray-700">{req?.name || '—'}</div>
                      {proj && <div className="text-xs text-gray-400">{proj.name}</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-500">v{art.version || 1}</td>
                    <td className="px-4 py-3 text-gray-500">{art.author || '—'}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {formatDateTime(art.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setSelected(art)}
                        className="text-emerald-600 hover:text-emerald-700 text-sm font-medium"
                      >
                        查看
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="space-y-0">
          {filtered.map((art, idx) => {
            const meta = getTypeMeta(art.type)
            const req = requirements.find((r) => r.id === art.requirement_id)
            const proj = projects.find((p) => p.id === art.project_id)
            return (
              <div key={art.id} className="flex gap-4 group">
                <div className="flex flex-col items-center">
                  <div className="w-3 h-3 rounded-full bg-emerald-400 ring-4 ring-white group-hover:ring-emerald-50 transition-all" />
                  {idx < filtered.length - 1 && <div className="w-px flex-1 bg-gray-200 my-1" />}
                </div>
                <div className="flex-1 pb-6">
                  <div
                    className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => setSelected(art)}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-xl">{meta.icon}</span>
                      <div>
                        <span className="text-sm font-semibold text-gray-800">{meta.label}</span>
                        <span className="text-xs text-gray-400 ml-2">v{art.version || 1}</span>
                      </div>
                      <span className="ml-auto text-xs text-gray-400">
                        {formatDateTime(art.created_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-400 flex-wrap">
                      {proj && (
                        <span className="flex items-center gap-1">
                          <FolderKanban className="w-3 h-3" />
                          {proj.name}
                        </span>
                      )}
                      {req && (
                        <span className="flex items-center gap-1">
                          <ListTodo className="w-3 h-3" />
                          {req.name}
                        </span>
                      )}
                      <span className="font-mono">{art.id?.slice(0, 12)}…</span>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 成果详情 Modal */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={
          selected
            ? `${getTypeMeta(selected.type).icon} ${getTypeMeta(selected.type).label} · v${selected.version || 1}`
            : ''
        }
        size="lg"
        footer={
          <>
            <ShareButton
              content={`# 成果：${getTypeMeta(selected?.type).label} v${selected?.version || 1}\n\n${selected?.content || selected?.content_preview || ''}\n\n> 由小团智能平台研发流水线产出 · ${selected?.created_at || ''}`}
              title={`成果：${getTypeMeta(selected?.type).label}`}
              contentType="artifact"
            />
            <Button variant="secondary" icon={Download} onClick={() => handleDownload(selected)}>
              下载
            </Button>
            <Button variant="danger" icon={Trash2} onClick={() => setDeleteTarget(selected)}>
              删除
            </Button>
            <Button variant="primary" onClick={() => setSelected(null)}>
              关闭
            </Button>
          </>
        }
      >
        {selected && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-gray-500">ID</p>
                <p className="font-mono text-xs text-gray-700 break-all">{selected.id}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">创建时间</p>
                <p className="text-gray-700">{formatDateTime(selected.created_at)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">作者</p>
                <p className="text-gray-700">{selected.author || '—'}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">关联项目</p>
                <p className="text-gray-700">{getProjectName(selected.project_id)}</p>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
                <FileText className="w-3.5 h-3.5" />
                内容
              </p>
              <div className="bg-gray-50 p-4 rounded-xl border max-h-[55vh] overflow-auto">
                <MarkdownRenderer
                  content={selected.content || selected.content_preview || '无内容'}
                />
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* 删除确认 */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除成果"
        message={
          deleteTarget
            ? `确定要删除成果「${getTypeMeta(deleteTarget.type).label} · v${deleteTarget.version || 1}」吗？此操作不可撤销。`
            : ''
        }
        confirmLabel="确认删除"
      />
    </div>
  )
}
