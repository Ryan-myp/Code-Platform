import React, { useState, useEffect, useCallback } from 'react'
import {
  Bot, Plus, Edit2, Trash2, Search,
  Play, RefreshCw, Cpu, MemoryStick,
  Layers, Zap,
  LayoutGrid, List as ListIcon,
  MessageSquare, Clock, X, Sparkles
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import { Modal, Button, Empty, PageLoading, SkeletonGrid, ErrorState, Badge, PageHeader } from '../components/ui'

// 默认 Expert Prompt
const DEFAULT_PROMPTS = {
  'Senior Dev Expert': `你是一个资深全栈开发工程师（Senior Full-Stack Developer），专注于高质量系统构建。

## 核心能力
1. **系统设计**: 能独立完成从需求到部署的完整开发流程
2. **代码质量**: 编写整洁、可扩展、可维护的代码
3. **技术选型**: 根据场景选择最合适的技术栈
4. **问题排查**: 快速定位并解决复杂技术问题

## 输出要求
- 提供完整可运行的代码
- 关键路径有单元测试
- 配置文件使用 .env 模板，敏感信息用占位符`,
  'QA Expert': `你是一个资深测试工程师（QA Expert），专注于软件质量保障。

## 核心能力
1. **测试策略**: 制定完整的测试计划和策略
2. **自动化测试**: 编写高质量的自动化测试脚本
3. **性能测试**: 识别系统性能瓶颈

## 输出要求
- 测试报告包含: 测试范围、通过率、缺陷统计
- 性能测试报告包含: 压测数据、瓶颈分析、优化建议`,
  'PM Expert': `你是一个资深产品经理（Product Manager），专注于产品规划和需求分析。

## 核心能力
1. **需求分析**: 深入理解用户需求和业务目标
2. **PRD 编写**: 输出清晰完整的产品需求文档

## 输出要求
- PRD 文档包含: 背景、目标、用户故事、功能描述、非功能需求、验收标准`,
}

const MODELS = ['agnes-2.5-flash', 'gpt-4o', 'claude-3', 'glm-4', 'qwen-max']

const MODEL_COLORS = {
  'agnes-2.5-flash': 'from-violet-500 to-purple-600',
  'gpt-4o': 'from-green-500 to-emerald-600',
  'claude-3': 'from-orange-500 to-amber-600',
  'glm-4': 'from-blue-500 to-cyan-600',
  'qwen-max': 'from-pink-500 to-rose-600',
}

// Agent 卡片组件
function AgentCard({ agent, onView, onEdit, onDelete, onExecute, viewMode }) {
  const modelColor = MODEL_COLORS[agent.model] || 'from-gray-500 to-gray-600'

  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex items-center gap-4">
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${modelColor} flex items-center justify-center text-white font-bold flex-shrink-0`}>
          {agent.name?.[0]?.toUpperCase() || 'A'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{agent.name}</h3>
            <Badge status={agent.status || 'active'} dot />
          </div>
          <p className="text-sm text-gray-500 truncate">{agent.description || '暂无描述'}</p>
        </div>
        <div className="hidden sm:flex items-center gap-3 text-sm text-gray-500 flex-shrink-0">
          <span className="flex items-center gap-1"><Bot className="w-4 h-4" />{agent.model}</span>
          <span className="flex items-center gap-1"><MessageSquare className="w-4 h-4" />{agent.tool_count || 0}</span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button onClick={() => onExecute(agent)} className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors" title="执行">
            <Play className="w-4 h-4" />
          </button>
          <button onClick={() => onView(agent)} className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors" title="查看">
            <Layers className="w-4 h-4" />
          </button>
          <button onClick={() => onEdit(agent)} className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors" title="编辑">
            <Edit2 className="w-4 h-4" />
          </button>
          <button onClick={() => onDelete(agent)} className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors" title="删除">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 group flex flex-col">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${modelColor} flex items-center justify-center text-white font-bold text-lg shadow-lg flex-shrink-0`}>
            {agent.name?.[0]?.toUpperCase() || 'A'}
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{agent.name}</h3>
            <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
              <Bot className="w-3 h-3 flex-shrink-0" />
              <span className="truncate">{agent.model}</span>
            </p>
          </div>
        </div>
        <Badge status={agent.status || 'active'} dot />
      </div>

      {agent.description && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-4 flex-1">{agent.description}</p>
      )}

      <div className="flex items-center gap-4 mb-4 text-xs text-gray-500">
        <span className="flex items-center gap-1" title="工具数量">
          <Cpu className="w-3.5 h-3.5" />
          {agent.tool_count || 0} 工具
        </span>
        <span className="flex items-center gap-1" title="知识库数量">
          <Layers className="w-3.5 h-3.5" />
          {agent.kb_count || 0} 知识库
        </span>
        <span className="flex items-center gap-1" title="最后运行时间">
          <Clock className="w-3.5 h-3.5" />
          {agent.last_run ? formatRelativeTime(agent.last_run) : '从未'}
        </span>
      </div>

      <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
        <Button variant="success" size="sm" icon={Play} onClick={() => onExecute(agent)} className="flex-1">
          执行
        </Button>
        <button onClick={() => onView(agent)} className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors" title="查看详情">
          <Layers className="w-4 h-4" />
        </button>
        <button onClick={() => onEdit(agent)} className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors" title="编辑">
          <Edit2 className="w-4 h-4" />
        </button>
        <button onClick={() => onDelete(agent)} className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors" title="删除">
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

// 表单模态框（创建/编辑共用）
function AgentFormModal({ open, onClose, onSubmit, editing, loading }) {
  const [form, setForm] = useState({
    name: '', description: '', model: 'agnes-2.5-flash', instructions: '', tools: [], knowledge_bases: []
  })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      if (editing) {
        setForm({
          name: editing.name || '',
          description: editing.description || '',
          model: editing.model || 'agnes-2.5-flash',
          instructions: editing.instructions || '',
          tools: editing.tools || [],
          knowledge_bases: editing.knowledge_bases || []
        })
      } else {
        setForm({
          name: '', description: '', model: 'agnes-2.5-flash',
          instructions: DEFAULT_PROMPTS['Senior Dev Expert'] || '', tools: [], knowledge_bases: []
        })
      }
      setErrors({})
    }
  }, [open, editing])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入 Agent 名称'
    if (form.name.length > 50) e.name = '名称不能超过 50 个字符'
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
      title={editing ? '编辑 Agent' : '新建 Agent'}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={loading}>{editing ? '保存' : '创建'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">名称 <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：代码审查专家"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            placeholder="简要说明 Agent 用途"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">模型</label>
          <select
            value={form.model}
            onChange={(e) => setField('model', e.target.value)}
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          >
            {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-sm font-medium text-gray-700">指令 (Instructions)</label>
            <div className="flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <select
                onChange={(e) => e.target.value && setField('instructions', DEFAULT_PROMPTS[e.target.value])}
                className="text-xs text-purple-600 bg-transparent border-none outline-none cursor-pointer"
                defaultValue=""
              >
                <option value="">选择模板…</option>
                {Object.keys(DEFAULT_PROMPTS).map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
          </div>
          <textarea
            value={form.instructions}
            onChange={(e) => setField('instructions', e.target.value)}
            rows={10}
            placeholder="输入 Agent 的系统指令…"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all font-mono text-sm"
          />
        </div>
      </div>
    </Modal>
  )
}

// 主页面组件
export default function AgentsPage({ tab }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('agent-view') || 'grid')
  const [filter, setFilter] = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [editingAgent, setEditingAgent] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const fetchAgents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/agents')
      setAgents(res.data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  const setView = (v) => {
    setViewMode(v)
    localStorage.setItem('agent-view', v)
  }

  const filteredAgents = agents.filter((agent) => {
    const matchSearch = agent.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchFilter = filter === 'all' ||
      (filter === 'active' && (agent.status || 'active') === 'active') ||
      (filter === 'inactive' && agent.status === 'inactive')
    return matchSearch && matchFilter
  })

  const openCreate = () => {
    setEditingAgent(null)
    setShowForm(true)
  }
  const openEdit = (agent) => {
    setEditingAgent(agent)
    setShowForm(true)
  }

  const handleSave = async (formData) => {
    setSaving(true)
    try {
      if (editingAgent) {
        await api.put(`/api/agents/${editingAgent.id}`, formData)
        toast.success(`Agent「${formData.name}」已更新`)
      } else {
        await api.post('/api/agents', formData)
        toast.success(`Agent「${formData.name}」已创建`)
      }
      setShowForm(false)
      fetchAgents()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.delete(`/api/agents/${deleteTarget.id}`)
      toast.success(`Agent「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      fetchAgents()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    } finally {
      setDeleting(false)
    }
  }

  const handleExecute = (agent) => {
    navigate(`/agents/${agent.id}`)
  }

  const stats = [
    { label: '总 Agent 数', value: agents.length, icon: Bot, color: 'from-violet-500 to-purple-600' },
    { label: '运行中', value: agents.filter((a) => (a.status || 'active') === 'active').length, icon: Zap, color: 'from-emerald-500 to-green-600' },
    { label: '停用', value: agents.filter((a) => a.status === 'inactive').length, icon: MemoryStick, color: 'from-gray-400 to-gray-500' },
    { label: '平均工具数', value: (agents.reduce((acc, a) => acc + (a.tool_count || 0), 0) / (agents.length || 1)).toFixed(1), icon: Cpu, color: 'from-blue-500 to-cyan-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent 管理"
        description="创建和管理 AI Agent，绑定工具、Skills 和知识库"
        icon={Bot}
        actions={
          <Button variant="primary" icon={Plus} onClick={openCreate}>新建 Agent</Button>
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
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索 Agent 名称或描述…"
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
            <option value="inactive">已停用</option>
          </select>
          <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => setView('grid')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
              title="网格视图"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setView('list')}
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
        <ErrorState message={`加载失败：${error.message}`} onRetry={fetchAgents} />
      ) : filteredAgents.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Bot}
            title={searchQuery || filter !== 'all' ? '未找到匹配的 Agent' : '暂无 Agent'}
            description={searchQuery || filter !== 'all' ? '尝试调整搜索或筛选条件' : '点击「新建 Agent」创建你的第一个 AI 助手'}
            actionLabel={searchQuery || filter !== 'all' ? undefined : '新建 Agent'}
            onAction={searchQuery || filter !== 'all' ? undefined : openCreate}
          />
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onView={(a) => navigate(`/agents/${a.id}`)}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onExecute={handleExecute}
              viewMode="grid"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onView={(a) => navigate(`/agents/${a.id}`)}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onExecute={handleExecute}
              viewMode="list"
            />
          ))}
        </div>
      )}

      <AgentFormModal
        open={showForm}
        onClose={() => setShowForm(false)}
        onSubmit={handleSave}
        editing={editingAgent}
        loading={saving}
      />

      {/* 删除确认 */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        size="sm"
      >
        <div className="text-center">
          <div className="w-14 h-14 rounded-2xl bg-red-100 flex items-center justify-center mx-auto mb-4">
            <Trash2 className="w-7 h-7 text-red-500" />
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">确认删除 Agent</h3>
          <p className="text-sm text-gray-500 mb-6">
            确定要删除 Agent「<span className="font-medium text-gray-700">{deleteTarget?.name}</span>」吗？此操作不可撤销。
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>取消</Button>
            <Button variant="danger" icon={Trash2} loading={deleting} onClick={handleDelete}>确认删除</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
