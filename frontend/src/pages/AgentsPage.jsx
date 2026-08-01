import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { 
  Bot, Plus, Edit2, Trash2, Settings, Search, 
  Eye, Play, Pause, RefreshCw, Cpu, MemoryStick, 
  Layers, Zap, CheckCircle, XCircle, AlertCircle,
  ChevronRight, Filter, Grid, List as ListIcon,
  Star, MessageSquare, Clock, TrendingUp
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

// 默认 Expert Prompt
const DEFAULT_PROMPTS = {
  'Senior Dev Expert': `你是一个资深全栈开发工程师（Senior Full-Stack Developer），专注于高质量系统构建。

## 核心能力
1. **系统设计**: 能独立完成从需求到部署的完整开发流程
2. **代码质量**: 编写整洁、可扩展、可维护的代码
3. **技术选型**: 根据场景选择最合适的技术栈
4. **问题排查**: 快速定位并解决复杂技术问题

## 开发标准
### 后端开发
- 使用 FastAPI/Node.js/Go 等现代框架
- RESTful API 设计，遵循 OpenAPI 规范
- 数据库抽象层设计，支持多引擎切换
- 错误处理与日志追踪完整

### 前端开发
- 现代 CSS 框架（TailwindCSS）
- 响应式设计，支持移动端优先
- 深色/浅色主题系统
- 流畅动画与交互反馈
- 无障碍访问支持

### 质量保障
- 代码注释覆盖率 > 30%
- 关键路径有单元测试
- API 接口有完整的 Swagger 文档
- 提供清晰的 README 和使用说明

## 工作流程
1. 需求分析 → 拆解功能点和技术难点
2. 架构设计 → 确定技术栈、目录结构、数据模型
3. 编码实现 → 按模块逐步完成，每个模块独立可运行
4. 测试验证 → 基本功能自检，确保核心流程通
5. 文档交付 → README + API 文档 + 部署指南

## 输出要求
- 每个项目必须包含: README.md, requirements.txt/package.json, 启动脚本
- 代码注释使用中文或英文（与项目一致）
- 配置文件使用 .env 模板，敏感信息用占位符
- 提供一键启动脚本，降低部署门槛`,
  
  'QA Expert': `你是一个资深测试工程师（QA Expert），专注于软件质量保障。

## 核心能力
1. **测试策略**: 制定完整的测试计划和策略
2. **自动化测试**: 编写高质量的自动化测试脚本
3. **性能测试**: 识别系统性能瓶颈
4. **安全测试**: 发现潜在安全风险

## 测试标准
### 功能测试
- 用例设计覆盖核心业务流程
- 边界条件和异常场景充分
- 测试数据准备充分

### 自动化测试
- 单元测试覆盖率 > 80%
- 接口测试覆盖所有 API
- UI 测试覆盖关键用户流程

### 性能测试
- 响应时间 < 200ms（P95）
- 并发支持 > 1000
- 资源使用率 < 70%

## 输出要求
- 测试报告包含: 测试范围、通过率、缺陷统计
- 性能测试报告包含: 压测数据、瓶颈分析、优化建议
- 安全测试报告包含: 风险等级、修复建议、复测结果`,
  
  'PM Expert': `你是一个资深产品经理（Product Manager），专注于产品规划和需求分析。

## 核心能力
1. **需求分析**: 深入理解用户需求和业务目标
2. **PRD 编写**: 输出清晰完整的产品需求文档
3. **原型设计**: 快速输出产品原型
4. **数据分析**: 基于数据驱动产品决策

## 工作标准
### 需求分析
- 用户故事清晰完整（AC 标准）
- 需求优先级明确（MoSCoW 法则）
- 风险评估到位

### PRD 文档
- 背景和目标明确
- 功能描述详细
- 非功能需求完整
- 验收标准可量化

## 输出要求
- PRD 文档包含: 背景、目标、用户故事、功能描述、非功能需求、验收标准
- 原型图使用专业工具输出
- 数据指标可量化、可追踪`,
}

// Agent 卡片组件
function AgentCard({ agent, onView, onEdit, onDelete, onExecute, viewMode }) {
  const statusColor = {
    active: 'bg-emerald-100 text-emerald-700',
    inactive: 'bg-gray-100 text-gray-700',
    error: 'bg-red-100 text-red-700',
  }
  
  const statusText = {
    active: '运行中',
    inactive: '已停用',
    error: '异常',
  }
  
  const modelColors = {
    'agnes-2.5-flash': 'from-violet-500 to-purple-600',
    'gpt-4o': 'from-green-500 to-emerald-600',
    'claude-3': 'from-orange-500 to-amber-600',
  }
  
  const modelColor = modelColors[agent.model] || 'from-gray-500 to-gray-600'
  const status = agent.status || 'active'
  
  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex items-center gap-4">
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${modelColor} flex items-center justify-center text-white font-bold`}>
          {agent.name?.[0]?.toUpperCase() || 'A'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{agent.name}</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor[status]}`}>
              {statusText[status]}
            </span>
          </div>
          <p className="text-sm text-gray-500 truncate">{agent.description || '暂无描述'}</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className="flex items-center gap-1"><Bot className="w-4 h-4" />{agent.model}</span>
          <span className="flex items-center gap-1"><MessageSquare className="w-4 h-4" />{agent.tool_count || 0}</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => onExecute(agent)} className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors" title="执行">
            <Play className="w-4 h-4" />
          </button>
          <button onClick={() => onView(agent)} className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors" title="查看">
            <Eye className="w-4 h-4" />
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
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 group">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${modelColor} flex items-center justify-center text-white font-bold text-lg shadow-lg`}>
            {agent.name?.[0]?.toUpperCase() || 'A'}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{agent.name}</h3>
            <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
              <Bot className="w-3 h-3" />
              {agent.model}
            </p>
          </div>
        </div>
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${statusColor[status]}`}>
          {statusText[status]}
        </span>
      </div>
      
      {/* Description */}
      {agent.description && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-4">{agent.description}</p>
      )}
      
      {/* Stats */}
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
          {agent.last_run ? new Date(agent.last_run).toLocaleDateString() : '从未'}
        </span>
      </div>
      
      {/* Actions */}
      <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
        <button 
          onClick={() => onExecute(agent)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Play className="w-4 h-4" />
          执行
        </button>
        <button 
          onClick={() => onView(agent)}
          className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
          title="查看详情"
        >
          <Eye className="w-4 h-4" />
        </button>
        <button 
          onClick={() => onEdit(agent)}
          className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
          title="编辑"
        >
          <Edit2 className="w-4 h-4" />
        </button>
        <button 
          onClick={() => onDelete(agent)}
          className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
          title="删除"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

// 主页面组件
export default function AgentsPage({ initialTab = 'agents' }) {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('grid')
  const [showCreate, setShowCreate] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [editingAgent, setEditingAgent] = useState(null)
  const [filter, setFilter] = useState('all')
  
  // 表单状态
  const [form, setForm] = useState({
    name: '',
    description: '',
    model: 'agnes-2.5-flash',
    instructions: '',
    tools: [],
    knowledge_bases: []
  })
  
  const fetchAgents = async () => {
    const token = localStorage.getItem('token')
    if (!token) return
    try {
      const res = await axios.get(`${API_BASE}/api/agents`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setAgents(res.data)
    } catch (e) {
      console.error('加载 Agent 失败', e)
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchAgents()
  }, [])
  
  const filteredAgents = agents.filter(agent => {
    const matchSearch = agent.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                       agent.description?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchFilter = filter === 'all' || 
                       (filter === 'active' && agent.status === 'active') ||
                       (filter === 'inactive' && agent.status === 'inactive')
    return matchSearch && matchFilter
  })
  
  const openCreate = () => {
    setEditingAgent(null)
    setForm({
      name: '',
      description: '',
      model: 'agnes-2.5-flash',
      instructions: DEFAULT_PROMPTS['Senior Dev Expert'] || '',
      tools: [],
      knowledge_bases: []
    })
    setShowCreate(true)
    setShowEdit(false)
  }
  
  const openEdit = (agent) => {
    setEditingAgent(agent)
    setForm({
      name: agent.name,
      description: agent.description || '',
      model: agent.model,
      instructions: agent.instructions || '',
      tools: agent.tools || [],
      knowledge_bases: agent.knowledge_bases || []
    })
    setShowEdit(true)
    setShowCreate(false)
  }
  
  const handleSave = async () => {
    if (!form.name.trim()) return
    const token = localStorage.getItem('token')
    try {
      if (editingAgent) {
        await axios.put(`${API_BASE}/api/agents/${editingAgent.id}`, form, {
          headers: { Authorization: `Bearer ${token}` }
        })
      } else {
        await axios.post(`${API_BASE}/api/agents`, form, {
          headers: { Authorization: `Bearer ${token}` }
        })
      }
      setShowCreate(false)
      setShowEdit(false)
      fetchAgents()
    } catch (e) {
      console.error('保存失败', e)
      alert('保存失败: ' + (e.response?.data?.detail || e.message))
    }
  }
  
  const handleDelete = async (agent) => {
    if (!confirm(`确定删除 Agent "${agent.name}"？`)) return
    const token = localStorage.getItem('token')
    try {
      await axios.delete(`${API_BASE}/api/agents/${agent.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      fetchAgents()
    } catch (e) {
      console.error('删除失败', e)
      alert('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
  
  const handleExecute = async (agent) => {
    window.open(`/agents/${agent.id}`, '_blank')
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin w-8 h-8 text-purple-600" />
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agent 管理</h1>
          <p className="text-gray-500 mt-1">创建和管理 AI Agent，绑定工具、Skills 和知识库</p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 text-white rounded-xl hover:bg-purple-700 transition-colors font-medium shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>新建 Agent</span>
        </button>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总 Agent 数', value: agents.length, icon: Bot, color: 'from-violet-500 to-purple-600' },
          { label: '运行中', value: agents.filter(a => a.status === 'active').length, icon: Zap, color: 'from-emerald-500 to-green-600' },
          { label: '停用', value: agents.filter(a => a.status === 'inactive').length, icon: Pause, color: 'from-gray-400 to-gray-500' },
          { label: '平均工具数', value: (agents.reduce((acc, a) => acc + (a.tool_count || 0), 0) / (agents.length || 1)).toFixed(1), icon: Cpu, color: 'from-blue-500 to-cyan-600' },
        ].map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center`}>
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Toolbar */}
      <div className="bg-white rounded-2xl border border-gray-200 p-4 flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索 Agent..."
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        >
          <option value="all">全部状态</option>
          <option value="active">运行中</option>
          <option value="inactive">已停用</option>
        </select>
        <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
          >
            <Grid className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
          >
            <ListIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      {/* Agent Grid/List */}
      {filteredAgents.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
          <Bot className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无 Agent</h3>
          <p className="text-gray-500 mb-6">点击「新建 Agent」创建你的第一个 AI 助手</p>
          <button
            onClick={openCreate}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
          >
            <Plus className="w-4 h-4" />
            新建 Agent
          </button>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAgents.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onView={(a) => window.open(`/agents/${a.id}`, '_blank')}
              onEdit={openEdit}
              onDelete={handleDelete}
              onExecute={handleExecute}
              viewMode="grid"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredAgents.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onView={(a) => window.open(`/agents/${a.id}`, '_blank')}
              onEdit={openEdit}
              onDelete={handleDelete}
              onExecute={handleExecute}
              viewMode="list"
            />
          ))}
        </div>
      )}
      
      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-auto">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">新建 Agent</h2>
              <button onClick={() => setShowCreate(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({...form, name: e.target.value})}
                  placeholder="例如：代码审查专家"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({...form, description: e.target.value})}
                  placeholder="简要说明用途"
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">模型</label>
                <select
                  value={form.model}
                  onChange={(e) => setForm({...form, model: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                >
                  <option value="agnes-2.5-flash">agnes-2.5-flash</option>
                  <option value="gpt-4o">gpt-4o</option>
                  <option value="claude-3">claude-3</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">指令 (Instructions)</label>
                <textarea
                  value={form.instructions}
                  onChange={(e) => setForm({...form, instructions: e.target.value})}
                  rows={12}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Edit Modal */}
      {showEdit && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-auto">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold">编辑 Agent</h2>
              <button onClick={() => setShowEdit(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({...form, name: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({...form, description: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">模型</label>
                <select
                  value={form.model}
                  onChange={(e) => setForm({...form, model: e.target.value})}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                >
                  <option value="agnes-2.5-flash">agnes-2.5-flash</option>
                  <option value="gpt-4o">gpt-4o</option>
                  <option value="claude-3">claude-3</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">指令 (Instructions)</label>
                <textarea
                  value={form.instructions}
                  onChange={(e) => setForm({...form, instructions: e.target.value})}
                  rows={12}
                  className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowEdit(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-xl"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
