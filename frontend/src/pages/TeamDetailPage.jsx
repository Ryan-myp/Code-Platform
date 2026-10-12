import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Users,
  Plus,
  Trash2,
  Play,
  Loader2,
  Crown,
  Bot,
  User,
  X,
  Gauge,
  CalendarDays,
  CreditCard,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDate, formatRelativeTime } from '../lib/format'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { Button, Empty, PageLoading, ErrorState, ConfirmDialog } from '../components/ui'

const MODE_META = {
  coordinate: { label: '协调模式', color: 'bg-purple-100 text-purple-700' },
  sequential: { label: '顺序模式', color: 'bg-sky-100 text-sky-700' },
  parallel: { label: '并行模式', color: 'bg-emerald-100 text-emerald-700' },
}

function StatCard({ icon: Icon, label, value, sub }) {
  return (
    <div className="flex items-center gap-3 p-4 rounded-xl border border-gray-200 bg-white">
      <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center flex-shrink-0">
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-lg font-semibold text-gray-900 tabular-nums truncate">{value}</p>
        {sub && <p className="text-[11px] text-gray-400 truncate">{sub}</p>}
      </div>
    </div>
  )
}

export default function TeamDetailPage() {
  const { id: teamId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()

  const [team, setTeam] = useState(null)
  const [members, setMembers] = useState([])
  const [usage, setUsage] = useState(null)
  const [dashboard, setDashboard] = useState(null) // admin-only; null = 无权限或加载中
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 成员管理
  const [addingMember, setAddingMember] = useState(false)
  const [newMemberId, setNewMemberId] = useState('')
  const [agents, setAgents] = useState([])

  // 内嵌执行台
  const [runInput, setRunInput] = useState('')
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [runError, setRunError] = useState(null)

  const [removeTarget, setRemoveTarget] = useState(null)
  const [deleteTeam, setDeleteTeam] = useState(false)

  const load = useCallback(async () => {
    if (!teamId) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(`/api/teams/${teamId}`)
      setTeam(res.data.team)
      setMembers(res.data.members || [])
      setUsage(res.data.usage_stats)
      // dashboard 仅团队管理员可看；403 时降级为只读视图
      try {
        const dRes = await api.get(`/api/teams/${teamId}/dashboard`)
        setDashboard(dRes.data)
      } catch {
        setDashboard(null)
      }
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [teamId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    api.get('/api/agents').then((res) => setAgents(Array.isArray(res.data) ? res.data : [])).catch(() => {})
  }, [])

  const agentNames = useMemo(() => {
    const map = {}
    for (const a of agents) map[a.id] = a.name
    return map
  }, [agents])
  const agentMembers = Array.isArray(team?.members) ? team.members : []

  const patchMembers = async (next) => {
    try {
      await api.patch(`/api/teams/${teamId}`, { members: next })
      load()
      return true
    } catch (e) {
      toast.error(e.response?.data?.detail || '操作失败')
      return false
    }
  }

  const addAgentMember = async (agentId) => {
    if (!agentId || agentMembers.includes(agentId)) return
    if (await patchMembers([...agentMembers, agentId])) {
      toast.success(`Agent 已加入：${agentNames[agentId] || agentId}`)
      setAddingMember(false)
      setNewMemberId('')
    }
  }

  const removeAgentMember = async (agentId) => {
    if (await patchMembers(agentMembers.filter((id) => id !== agentId))) {
      toast.success('Agent 已移出团队')
    }
  }

  const runTeam = async () => {
    if (!runInput.trim()) {
      toast.error('请输入执行内容')
      return
    }
    setRunning(true)
    setRunError(null)
    setRunResult(null)
    try {
      const res = await api.post(`/api/teams/${teamId}/run`, { message: runInput.trim() })
      setRunResult(res.data)
      setRunInput('')
      toast.success('执行完成')
    } catch (e) {
      setRunError(e.response?.data?.detail || e.message || '执行失败')
    } finally {
      setRunning(false)
    }
  }

  const removeMember = async () => {
    if (!removeTarget) return
    try {
      await api.delete(`/api/teams/${teamId}/members/${removeTarget}`)
      toast.success('成员已移除')
      setRemoveTarget(null)
      load()
    } catch (e) {
      toast.error(e.response?.data?.detail || '移除失败')
    }
  }

  const handleDelete = async () => {
    try {
      await api.delete(`/api/teams/${teamId}`)
      toast.success('团队已删除')
      navigate('/teams')
    } catch (e) {
      toast.error(e.response?.data?.detail || '删除失败')
    }
  }

  if (loading) return <PageLoading label="加载团队详情…" />
  if (error) return <ErrorState message="加载团队失败" onRetry={load} />
  if (!team) return null

  const modeMeta = MODE_META[team.mode] || MODE_META.coordinate
  const isAdmin = !!dashboard

  return (
    <div className="h-full flex flex-col">
      {/* 顶栏 */}
      <div className="h-14 bg-white border-b border-gray-200 flex items-center px-4 gap-3 flex-shrink-0">
        <button
          onClick={() => navigate('/teams')}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600"
          title="返回团队列表"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white flex-shrink-0">
          <Users className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="font-semibold text-gray-900 truncate">{team.name}</h1>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${modeMeta.color}`}>
              {modeMeta.label}
            </span>
            {dashboard?.subscription_status === 'expired' && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-600 whitespace-nowrap">
                订阅已过期
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 truncate">
            {team.description || '暂无描述'} · 创建于 {formatRelativeTime(team.created_at)}
          </p>
        </div>
        <Button variant="danger" icon={Trash2} size="sm" onClick={() => setDeleteTeam(true)}>
          <span className="hidden sm:inline">删除</span>
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {/* 统计卡片 */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard icon={Gauge} label="今日用量" value={usage?.today_used ?? 0} sub="tokens" />
          <StatCard icon={CalendarDays} label="本月用量" value={usage?.month_used ?? 0} sub={`日均 ${usage?.avg_daily ?? 0}`} />
          <StatCard
            icon={Users}
            label="席位"
            value={isAdmin ? `${dashboard.seats.used} / ${dashboard.seats.total}` : `${members.length} 人`}
            sub={isAdmin ? `可用 ${Math.max(0, dashboard.seats.total - dashboard.seats.used)}` : null}
          />
          <StatCard icon={CreditCard} label="订阅状态" value={isAdmin ? (dashboard.subscription_status === 'active' ? '生效中' : '已过期') : '—'} sub={dashboard?.team?.subscription_ends_at ? `至 ${formatDate(dashboard.team.subscription_ends_at)}` : '未设置'} />
        </div>

        {/* 协作 Agent */}
        <section className="bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">协作 Agent（{agentMembers.length}）</h2>
            <Button variant="secondary" size="sm" icon={Plus} onClick={() => setAddingMember((v) => !v)}>
              添加 Agent
            </Button>
          </div>
          {addingMember && (
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/60 flex items-center gap-2">
              <select
                value={newMemberId}
                onChange={(e) => setNewMemberId(e.target.value)}
                className="flex-1 min-w-40 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white outline-none"
              >
                <option value="">选择协作 Agent…</option>
                {agents.filter((a) => !agentMembers.includes(a.id)).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
              <Button variant="primary" size="sm" icon={Plus} onClick={() => addAgentMember(newMemberId)} disabled={!newMemberId}>
                加入团队
              </Button>
            </div>
          )}
          {agentMembers.length === 0 ? (
            <div className="p-6">
              <Empty
                icon={Users}
                title="还没有协作 Agent"
                description="添加 Agent 后即可在下方下达协作任务"
                actionLabel="添加 Agent"
                onAction={() => setAddingMember(true)}
              />
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {agentMembers.map((id) => (
                <li key={id} className="flex items-center gap-3 px-4 py-2.5">
                  <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600 flex-shrink-0">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{agentNames[id] || id}</p>
                    <p className="text-xs text-gray-400 truncate">{id}</p>
                  </div>
                  <button
                    onClick={() => removeAgentMember(id)}
                    className="p-1.5 hover:bg-red-50 rounded-lg text-gray-400 hover:text-red-500 transition-colors"
                    title="移出团队"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 用户席位 */}
        <section className="bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">用户席位（{members.length}）</h2>
            {dashboard?.seats?.total != null && (
              <span className="text-xs text-gray-400 tabular-nums">已用 {dashboard.seats.used} / 共 {dashboard.seats.total}</span>
            )}
          </div>
          {members.length === 0 ? (
            <div className="p-6">
              <p className="text-sm text-gray-400">暂无用户席位记录</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {members.map((m) => (
                <li key={m.id} className="flex items-center gap-3 px-4 py-2.5">
                  <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center text-gray-500 flex-shrink-0">
                    {m.avatar ? (
                      <img src={m.avatar} alt="" className="w-8 h-8 rounded-lg object-cover" />
                    ) : m.role === 'admin' ? (
                      <Crown className="w-4 h-4" />
                    ) : (
                      <User className="w-4 h-4" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {m.nickname || m.username}
                    </p>
                    <p className="text-xs text-gray-400">
                      {m.username} · 加入于 {m.joined_at ? formatDate(m.joined_at) : '—'}
                    </p>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs whitespace-nowrap ${m.role === 'admin' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'}`}
                  >
                    {m.role === 'admin' ? '管理员' : '成员'}
                  </span>
                  {m.role !== 'admin' && (
                    <button
                      onClick={() => setRemoveTarget(m.id)}
                      className="p-1.5 hover:bg-red-50 rounded-lg text-gray-400 hover:text-red-500 transition-colors"
                      title="移除席位"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 内嵌执行台 */}
        <section className="bg-white rounded-xl border border-gray-200">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
            <Play className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-semibold text-gray-900">协作执行</h2>
            {running && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-600">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> 执行中…
              </span>
            )}
          </div>
          <div className="p-4 space-y-3">
            <div className="flex gap-2 items-start">
              <textarea
                value={runInput}
                onChange={(e) => setRunInput(e.target.value)}
                placeholder={`给「${team.name}」下达协作任务，如：分析用户登录失败率上升的原因…（Ctrl+Enter 执行）`}
                rows={2}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 resize-none"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault()
                    runTeam()
                  }
                }}
              />
              <Button variant="success" icon={Play} loading={running} onClick={runTeam} className="flex-shrink-0">
                执行
              </Button>
            </div>
            {runError && <p className="text-xs text-red-500">{runError}</p>}
            {runResult && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full whitespace-nowrap">
                    完成
                  </span>
                  <span className="tabular-nums">耗时 {runResult.elapsed}s</span>
                  <span>{MODE_META[runResult.mode]?.label || runResult.mode}</span>
                </div>
                {runResult.members?.map((m, i) => (
                  <div key={i} className="px-3 py-2 rounded-lg border border-gray-100 bg-gray-50 text-xs">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`font-medium ${m.error ? 'text-red-600' : 'text-gray-700'}`}>{m.name}</span>
                      {Array.isArray(m.tools_used) && m.tools_used.length > 0 && (
                        <span className="inline-flex items-center gap-1 flex-wrap" title="本成员执行中真实调用的工具">
                          {m.tools_used.map((t, j) => (
                            <span key={j} className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 whitespace-nowrap">🛠 {t}</span>
                          ))}
                          {Array.isArray(m.mcp_calls) && m.mcp_calls.length > 0 && m.mcp_calls.map((c, j) => (
                            <span key={`m${j}`} className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 whitespace-nowrap">🔌 {c}</span>
                          ))}
                        </span>
                      )}
                    </div>
                    <span className="mt-1 block text-gray-600 break-all">{m.result}</span>
                  </div>
                ))}
                <div className="border border-gray-100 rounded-lg p-3 bg-gray-50 max-h-64 overflow-y-auto">
                  <MarkdownRenderer content={runResult.result || '(无汇总结果)'} />
                </div>
              </div>
            )}
          </div>
        </section>

        {/* 近期账单（仅管理员） */}
        {isAdmin && dashboard.recent_bills?.length > 0 && (
          <section className="bg-white rounded-xl border border-gray-200">
            <div className="px-4 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900">近期账单</h2>
            </div>
            <ul className="divide-y divide-gray-100">
              {dashboard.recent_bills.map((b) => (
                <li key={b.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <span className="font-medium text-gray-900 whitespace-nowrap">{b.plan_name || b.product || '订阅'}</span>
                  <span className="text-gray-400 flex-1 truncate">{b.metadata}</span>
                  <span className="tabular-nums text-gray-600 whitespace-nowrap">¥{b.amount}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs whitespace-nowrap ${b.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'}`}>
                    {b.status === 'paid' ? '已支付' : b.status}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <ConfirmDialog
        open={!!removeTarget}
        onClose={() => setRemoveTarget(null)}
        onConfirm={removeMember}
        title="移除成员"
        message="确定将该成员从团队中移除吗？"
        confirmLabel="移除"
      />
      <ConfirmDialog
        open={deleteTeam}
        onClose={() => setDeleteTeam(false)}
        onConfirm={handleDelete}
        title="删除团队"
        message={`确定删除团队「${team.name}」吗？此操作不可恢复。`}
        confirmLabel="删除"
      />
    </div>
  )
}
