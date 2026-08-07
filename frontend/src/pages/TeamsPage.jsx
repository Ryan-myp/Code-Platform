import React, { useState, useEffect, useCallback } from 'react'
import {
  Users,
  Plus,
  Edit2,
  Trash2,
  Search,
  Eye,
  MessageSquare,
  RefreshCw,
  LayoutGrid,
  List as ListIcon,
  Bot,
  Settings,
  UserPlus,
  Code2,
  PenTool,
  HeadphonesIcon,
  Activity,
  Shield,
  UserCog,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import MarkdownRenderer from '../components/MarkdownRenderer'
import {
  Modal,
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  PageHeader,
  ConfirmDialog,
} from '../components/ui'

const MODE_META = {
  coordinate: { label: '协调模式', color: 'bg-blue-50 text-blue-600', dot: 'bg-blue-500' },
  parallel: { label: '并行模式', color: 'bg-emerald-50 text-emerald-600', dot: 'bg-emerald-500' },
  sequential: { label: '顺序模式', color: 'bg-amber-50 text-amber-600', dot: 'bg-amber-500' },
}

// 团队快速模板
const TEAM_TEMPLATES = [
  {
    name: '产品研发组',
    description: '产品经理 + 开发 + 测试的敏捷研发团队',
    icon: Code2,
    color: 'from-blue-500 to-indigo-600',
    defaults: {
      name: '产品研发组',
      description: '负责产品需求分析、开发实现、测试验证的敏捷研发团队',
      mode: 'coordinate',
      instructions:
        '## 协作规则\n1. 产品经理负责需求拆解和优先级排序\n2. 开发人员负责技术实现和代码质量\n3. 测试人员负责质量保障和Bug追踪\n4. 每日同步进度，遇到阻塞及时上报',
    },
  },
  {
    name: '内容创作组',
    description: '策划 + 写作 + 审核的内容生产团队',
    icon: PenTool,
    color: 'from-amber-500 to-orange-600',
    defaults: {
      name: '内容创作组',
      description: '负责内容策划、文案撰写、审核发布的内容生产团队',
      mode: 'sequential',
      instructions:
        '## 协作规则\n1. 策划人员负责选题规划和内容方向\n2. 写作人员负责文案创作和内容生产\n3. 审核人员负责质量把关和合规审查\n4. 按流程顺序执行，每环节完成后流转下一步',
    },
  },
  {
    name: '客户服务组',
    description: '售前咨询 + 技术支持 + 售后跟进',
    icon: HeadphonesIcon,
    color: 'from-emerald-500 to-teal-600',
    defaults: {
      name: '客户服务组',
      description: '负责售前咨询、技术支持、售后跟进的全流程客户服务团队',
      mode: 'parallel',
      instructions:
        '## 协作规则\n1. 售前顾问负责产品咨询和方案推荐\n2. 技术支持负责问题诊断和解决方案\n3. 售后专员负责跟进和客户满意度\n4. 各角色可并行处理不同客户请求',
    },
  },
]

// 成员角色定义
const MEMBER_ROLES = [
  { value: 'coordinator', label: '协调者', icon: UserCog, color: 'bg-blue-50 text-blue-700' },
  { value: 'executor', label: '执行者', icon: Bot, color: 'bg-emerald-50 text-emerald-700' },
  { value: 'reviewer', label: '审核者', icon: Shield, color: 'bg-amber-50 text-amber-700' },
]

// 模拟活动日志（基于团队创建时间等生成）
function generateActivityLog(team) {
  const activities = []
  const base = team.created_at
  if (!base) return activities
  activities.push({ text: `团队「${team.name}」创建`, time: base, type: 'create' })
  if (team.last_run) {
    activities.push({ text: '最近一次协作执行', time: team.last_run, type: 'run' })
  }
  return activities
}

function TeamCard({ team, onView, onEdit, onDelete, onRun, viewMode }) {
  const modeMeta = MODE_META[team.mode] || MODE_META.coordinate
  const memberIds = Array.isArray(team.members)
    ? team.members
    : team.members
      ? JSON.parse(team.members)
      : []
  const memberCount = memberIds.length

  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white font-bold flex-shrink-0">
          <Users className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{team.name}</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${modeMeta.color}`}>
              {modeMeta.label}
            </span>
          </div>
          <p className="text-sm text-gray-500 truncate">{team.description || '暂无描述'}</p>
        </div>
        <div className="hidden sm:flex items-center gap-3 text-xs text-gray-500 flex-shrink-0">
          <span className="flex items-center gap-1">
            <Bot className="w-3.5 h-3.5" />
            {memberCount} 成员
          </span>
          <span className="flex items-center gap-1">
            <Activity className="w-3.5 h-3.5" />
            {team.execution_count || 0} 次执行
          </span>
          <span>{formatRelativeTime(team.created_at)}</span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onRun(team)}
            className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors"
            title="运行"
          >
            <Play className="w-4 h-4" />
          </button>
          <button
            onClick={() => onView(team)}
            className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
            title="查看"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(team)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(team)}
            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white shadow-lg flex-shrink-0">
            <Users className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{team.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${modeMeta.color}`}>
                {modeMeta.label}
              </span>
              <span className="text-xs text-gray-400">{formatRelativeTime(team.created_at)}</span>
            </div>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-600 line-clamp-2 mb-3 flex-1">
        {team.description || '暂无描述'}
      </p>

      {/* 成员头像 + 执行统计 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="flex -space-x-2">
            {memberIds.slice(0, 4).map((id, i) => (
              <div
                key={i}
                className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 border-2 border-white flex items-center justify-center text-white text-xs font-bold"
              >
                {String.fromCharCode(65 + (i % 26))}
              </div>
            ))}
            {memberCount > 4 && (
              <div className="w-7 h-7 rounded-full bg-gray-200 border-2 border-white flex items-center justify-center text-gray-500 text-xs font-medium">
                +{memberCount - 4}
              </div>
            )}
            {memberCount === 0 && (
              <div className="w-7 h-7 rounded-full bg-gray-100 border-2 border-white flex items-center justify-center text-gray-400 text-xs">
                <MessageSquare className="w-3 h-3" />
              </div>
            )}
          </div>
          <span className="text-xs text-gray-400">{memberCount} 成员</span>
        </div>
        <span className="text-xs text-gray-400 flex items-center gap-1">
          <Activity className="w-3 h-3" />
          {team.execution_count || 0} 次
        </span>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">{formatRelativeTime(team.created_at)}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onRun(team)}
            className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors"
            title="运行"
          >
            <Play className="w-4 h-4" />
          </button>
          <button
            onClick={() => onView(team)}
            className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
            title="查看"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(team)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(team)}
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

function TeamFormModal({ open, onClose, onSubmit, editing, defaults, agents, loading }) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    mode: 'coordinate',
    members: [],
    instructions: '',
    respond_directly: false,
  })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (!open) return
    if (editing) {
      const members = Array.isArray(editing.members)
        ? editing.members
        : editing.members
          ? JSON.parse(editing.members)
          : []
      setForm({
        name: editing.name || '',
        description: editing.description || '',
        mode: editing.mode || 'coordinate',
        members,
        instructions: editing.instructions || '',
        respond_directly: !!editing.respond_directly,
      })
    } else if (defaults) {
      setForm({
        name: defaults.name || '',
        description: defaults.description || '',
        mode: defaults.mode || 'coordinate',
        members: [],
        instructions: defaults.instructions || '',
        respond_directly: false,
      })
    } else {
      setForm({
        name: '',
        description: '',
        mode: 'coordinate',
        members: [],
        instructions: '',
        respond_directly: false,
      })
    }
    setErrors({})
  }, [open, editing, defaults])

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  const toggleMember = (agentId) => {
    setForm((p) => ({
      ...p,
      members: p.members.includes(agentId)
        ? p.members.filter((id) => id !== agentId)
        : [...p.members, agentId],
    }))
  }

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入 Team 名称'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({
      ...form,
      name: form.name.trim(),
      members: form.members,
    })
  }

  const inputCls = (err) =>
    `w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${
      err
        ? 'border-red-300 focus:ring-red-500/20'
        : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'
    }`

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑 Team' : '新建 Team'}
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
            Team 名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：前端开发小队"
            className={inputCls(errors.name)}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            placeholder="简要说明 Team 的职责和目标"
            className={inputCls(false)}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">协作模式</label>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(MODE_META).map(([key, meta]) => (
              <button
                key={key}
                type="button"
                onClick={() => setField('mode', key)}
                className={`px-3 py-2 rounded-xl text-sm font-medium border transition-all ${
                  form.mode === key
                    ? 'border-purple-500 bg-purple-50 text-purple-700 shadow-sm'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                {meta.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            成员 Agent（{form.members.length} 个已选）
          </label>
          <div className="border border-gray-200 rounded-xl p-2 max-h-48 overflow-y-auto space-y-1">
            {agents.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">暂无 Agent，请先创建</p>
            ) : (
              agents.map((agent) => {
                const checked = form.members.includes(agent.id)
                return (
                  <label
                    key={agent.id}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${checked ? 'bg-purple-50' : 'hover:bg-gray-50'}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMember(agent.id)}
                      className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-bold">
                      {agent.name?.[0]?.toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{agent.name}</p>
                      <p className="text-xs text-gray-400 truncate">{agent.model || ''}</p>
                    </div>
                  </label>
                )
              })
            )}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Team 指令</label>
          <textarea
            value={form.instructions}
            onChange={(e) => setField('instructions', e.target.value)}
            rows={4}
            placeholder="Team 的系统指令，定义协作规则…"
            className={`${inputCls(false)} font-mono text-sm`}
          />
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.respond_directly}
            onChange={(e) => setField('respond_directly', e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
          />
          <span className="text-sm text-gray-700">允许成员直接响应（不经协调）</span>
        </label>
      </div>
    </Modal>
  )
}

function TeamDetailModal({ open, onClose, team, members, onEdit, onDelete }) {
  if (!team) return null
  const modeMeta = MODE_META[team.mode] || MODE_META.coordinate
  const memberIds = Array.isArray(team.members)
    ? team.members
    : team.members
      ? JSON.parse(team.members)
      : []
  const activityLog = generateActivityLog(team)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={team.name}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            关闭
          </Button>
          <Button
            icon={Edit2}
            onClick={() => {
              onEdit(team)
              onClose()
            }}
          >
            编辑
          </Button>
          <Button
            variant="danger"
            icon={Trash2}
            onClick={() => {
              onDelete(team)
              onClose()
            }}
          >
            删除
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex items-center gap-3 pb-4 border-b border-gray-100">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white shadow-lg">
            <Users className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{team.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${modeMeta.color}`}>
                {modeMeta.label}
              </span>
              <span className="text-xs text-gray-500">
                创建于 {formatRelativeTime(team.created_at)}
              </span>
            </div>
          </div>
        </div>

        {team.description && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">描述</p>
            <p className="text-sm text-gray-700">{team.description}</p>
          </div>
        )}

        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            成员（{memberIds.length}）
          </p>
          <div className="space-y-1.5">
            {memberIds.length === 0 ? (
              <p className="text-sm text-gray-400 italic">暂无成员</p>
            ) : members.length > 0 ? (
              memberIds.map((id, idx) => {
                const agent = members.find((m) => m.id === id)
                // 根据索引分配角色标签（第一个为协调者，后面交替分配）
                const roleIdx = idx === 0 ? 0 : idx % 2 === 1 ? 1 : 2
                const role = MEMBER_ROLES[roleIdx]
                return (
                  <div key={id} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-bold">
                      {agent?.name?.[0]?.toUpperCase() || '?'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">
                        {agent?.name || id}
                      </p>
                      {agent && <p className="text-xs text-gray-400 truncate">{agent.model}</p>}
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${role.color}`}>
                      {role.label}
                    </span>
                  </div>
                )
              })
            ) : (
              <p className="text-sm text-gray-400 italic">加载成员信息中…</p>
            )}
          </div>
        </div>

        {/* 团队活动日志 */}
        {activityLog.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
              <Activity className="w-3 h-3" /> 活动日志
            </p>
            <div className="space-y-2">
              {activityLog.map((log, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <div
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${log.type === 'create' ? 'bg-blue-500' : 'bg-emerald-500'}`}
                  />
                  <span className="text-gray-700 flex-1">{log.text}</span>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {formatRelativeTime(log.time)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {team.instructions && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Team 指令
            </p>
            <pre className="bg-gray-50 rounded-xl p-4 text-sm text-gray-700 whitespace-pre-wrap font-mono max-h-48 overflow-y-auto">
              {team.instructions}
            </pre>
          </div>
        )}
      </div>
    </Modal>
  )
}

// Team 运行弹窗：输入任务 → 按模式协作 → 展示成员产出与最终结果
function TeamRunModal({ team, onClose }) {
  const toast = useToast()
  const [message, setMessage] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const modeMeta = MODE_META[team?.mode] || MODE_META.coordinate

  const run = async () => {
    if (!message.trim()) {
      toast.error('请输入任务描述')
      return
    }
    setRunning(true)
    setResult(null)
    setError(null)
    try {
      const res = await api.post(`/api/teams/${team.id}/run`, { message: message.trim() })
      setResult(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || '运行失败')
    } finally {
      setRunning(false)
    }
  }

  return (
    <Modal
      open={!!team}
      onClose={onClose}
      title={`运行 Team — ${team?.name || ''}`}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            关闭
          </Button>
          <Button variant="success" icon={Play} onClick={run} loading={running} disabled={running}>
            开始协作
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {team && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${modeMeta.color}`}>
              {modeMeta.label}
            </span>
            <span>{team.description || ''}</span>
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            任务描述 <span className="text-red-500">*</span>
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            placeholder="例如：帮我们设计一个用户积分系统的技术方案，并输出测试计划…"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all text-sm"
          />
          <p className="text-xs text-gray-400 mt-1">
            任务将按团队协作模式分发给成员 Agent，最终汇总为统一答案
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600">
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
            {/* 成员产出 */}
            {Array.isArray(result.members) && result.members.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  成员产出（{result.members.length}）
                </p>
                {result.members.map((m, i) => (
                  <div key={i} className="rounded-xl border border-gray-200 overflow-hidden">
                    <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-100">
                      <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold">
                        {m.name?.[0]?.toUpperCase() || '?'}
                      </div>
                      <span className="text-sm font-medium text-gray-700 flex-1">{m.name}</span>
                      {m.error ? (
                        <XCircle className="w-4 h-4 text-red-500" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      )}
                    </div>
                    <div className="p-3 text-sm text-gray-700">
                      <MarkdownRenderer content={m.result} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 最终结果 */}
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-2 bg-emerald-100/60 border-b border-emerald-200">
                <Users className="w-4 h-4 text-emerald-600" />
                <span className="text-sm font-medium text-emerald-800">最终结果</span>
                {result.elapsed != null && (
                  <span className="text-xs text-emerald-600 ml-auto">耗时 {result.elapsed}s</span>
                )}
              </div>
              <div className="p-3 text-sm text-gray-800">
                <MarkdownRenderer content={result.result} />
              </div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

export default function TeamsPage() {
  const toast = useToast()
  const [teams, setTeams] = useState([])
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState('grid')
  const [showForm, setShowForm] = useState(false)
  const [editingTeam, setEditingTeam] = useState(null)
  const [saving, setSaving] = useState(false)
  const [viewTarget, setViewTarget] = useState(null)
  const [runTarget, setRunTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [formDefaults, setFormDefaults] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [teamsRes, agentsRes] = await Promise.all([
        api.get('/api/teams'),
        api.get('/api/agents'),
      ])
      setTeams(Array.isArray(teamsRes.data) ? teamsRes.data : [])
      setAgents(Array.isArray(agentsRes.data) ? agentsRes.data : [])
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const filteredTeams = teams.filter((t) => {
    const q = searchTerm.toLowerCase()
    if (!q) return true
    return (
      (t.name || '').toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q)
    )
  })

  const openCreate = () => {
    setEditingTeam(null)
    setFormDefaults(null)
    setShowForm(true)
  }
  const openEdit = (team) => {
    setEditingTeam(team)
    setShowForm(true)
  }

  const handleSubmit = async (payload) => {
    setSaving(true)
    try {
      if (editingTeam) {
        await api.put(`/api/teams/${editingTeam.id}`, payload)
        toast.success(`Team「${payload.name}」已更新`)
      } else {
        await api.post('/api/teams', payload)
        toast.success(`Team「${payload.name}」已创建`)
      }
      setShowForm(false)
      setEditingTeam(null)
      loadData()
    } catch (e) {
      toast.error(`操作失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return false
    try {
      await api.delete(`/api/teams/${deleteTarget.id}`)
      toast.success(`Team「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      loadData()
      return true
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
      return false
    }
  }

  const totalMembers = teams.reduce((acc, t) => {
    const ids = Array.isArray(t.members) ? t.members : t.members ? JSON.parse(t.members) : []
    return acc + ids.length
  }, 0)
  const totalExecutions = teams.reduce((sum, t) => sum + (t.execution_count || 0), 0)

  const stats = [
    {
      label: '总 Team 数',
      value: teams.length,
      icon: Users,
      color: 'from-emerald-500 to-teal-600',
    },
    {
      label: '协调模式',
      value: teams.filter((t) => t.mode === 'coordinate').length,
      icon: Settings,
      color: 'from-blue-500 to-cyan-600',
    },
    {
      label: '总成员数',
      value: totalMembers,
      icon: UserPlus,
      color: 'from-violet-500 to-purple-600',
    },
    {
      label: '总执行次数',
      value: totalExecutions,
      icon: Activity,
      color: 'from-amber-500 to-orange-600',
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Team 管理"
        description="创建和管理 AI Team，协调多个 Agent 协作完成复杂任务"
        icon={Users}
        iconColor="from-emerald-500 to-teal-600"
        actions={
          <Button variant="primary" icon={Plus} onClick={openCreate}>
            新建 Team
          </Button>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div
                className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center flex-shrink-0`}
              >
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 快速模板（仅在团队为空时显示） */}
      {teams.length === 0 && !loading && !error && (
        <div className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-2xl border border-emerald-200/50 p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <Users className="w-4 h-4 text-emerald-500" />
            从模板快速创建
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {TEAM_TEMPLATES.map((tpl) => (
              <button
                key={tpl.name}
                onClick={() => {
                  setFormDefaults(tpl.defaults)
                  setShowForm(true)
                }}
                className="bg-white rounded-xl p-4 border border-gray-200 hover:border-emerald-300 hover:shadow-md transition-all text-left group"
              >
                <div
                  className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tpl.color} flex items-center justify-center text-white mb-3`}
                >
                  <tpl.icon className="w-4.5 h-4.5" />
                </div>
                <h4 className="text-sm font-semibold text-gray-800 mb-1">{tpl.name}</h4>
                <p className="text-xs text-gray-500 line-clamp-2">{tpl.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索 Team 名称或描述…"
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="md" icon={RefreshCw} onClick={loadData}>
            刷新
          </Button>
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

      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={loadData} />
      ) : filteredTeams.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Users}
            title={searchTerm ? '未找到匹配的 Team' : '暂无 Team'}
            description={
              searchTerm ? '尝试调整搜索条件' : '点击「新建 Team」创建你的第一个 AI 团队'
            }
            actionLabel={searchTerm ? undefined : '新建 Team'}
            onAction={searchTerm ? undefined : openCreate}
          />
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTeams.map((team) => (
            <TeamCard
              key={team.id}
              team={team}
              members={agents}
              onView={setViewTarget}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onRun={setRunTarget}
              viewMode="grid"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredTeams.map((team) => (
            <TeamCard
              key={team.id}
              team={team}
              members={agents}
              onView={setViewTarget}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onRun={setRunTarget}
              viewMode="list"
            />
          ))}
        </div>
      )}

      <TeamFormModal
        open={showForm}
        onClose={() => {
          setShowForm(false)
          setEditingTeam(null)
          setFormDefaults(null)
        }}
        onSubmit={handleSubmit}
        editing={editingTeam}
        defaults={formDefaults}
        agents={agents}
        loading={saving}
      />

      <TeamDetailModal
        open={!!viewTarget}
        onClose={() => setViewTarget(null)}
        team={viewTarget}
        members={agents}
        onEdit={openEdit}
        onDelete={setDeleteTarget}
      />

      <TeamRunModal team={runTarget} onClose={() => setRunTarget(null)} />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除 Team"
        message={
          <>
            确定要删除 Team「<span className="font-medium text-gray-700">{deleteTarget?.name}</span>
            」吗？此操作不可撤销。
          </>
        }
        confirmLabel="确认删除"
      />
    </div>
  )
}
