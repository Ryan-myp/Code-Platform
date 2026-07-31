import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Bot, Plus, Edit2, Trash2, Settings, Database, Wrench, Search, FolderOpen, FileText, FileCode, FileJson, Terminal, Image, X, Layers, Users, ChevronRight, ChevronDown, Check, Eye, Code2 } from 'lucide-react'
import RichTextEditor from '../components/RichTextEditor'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

// ─── Agno 内置工具列表（按分类组织）─────────────────────────────
const AGNO_TOOLS = [
  { category: '搜索', items: [
    { id: 'web_search', label: 'WebSearch', desc: '通用网页搜索' },
    { id: 'duckduckgo', label: 'DuckDuckGo', desc: '隐私搜索引擎' },
    { id: 'tavily', label: 'Tavily Search', desc: 'AI 优化搜索' },
    { id: 'serper', label: 'Serper', desc: 'Google Search API' },
    { id: 'bravesearch', label: 'Brave Search', desc: 'Brave 搜索引擎' },
    { id: 'wikipedia', label: 'Wikipedia', desc: '维基百科搜索' },
    { id: 'arxiv', label: 'ArXiv', desc: '学术论文搜索' },
    { id: 'pubmed', label: 'PubMed', desc: '生物医学文献' },
    { id: 'hackernews', label: 'Hacker News', desc: 'HN 搜索' },
    { id: 'reddit', label: 'Reddit', desc: 'Reddit 搜索' },
  ]},
  { category: '编码', items: [
    { id: 'python', label: 'Python 执行', desc: '在沙箱中运行 Python' },
    { id: 'coding', label: 'Coding', desc: '通用代码生成与执行' },
    { id: 'shell', label: 'Shell', desc: '终端命令执行' },
    { id: 'pandas', label: 'Pandas', desc: '数据分析处理' },
  ]},
  { category: '文件', items: [
    { id: 'file', label: 'File Read/Write', desc: '文件读写操作' },
    { id: 'local_file_system', label: 'Local FS', desc: '本地文件系统访问' },
  ]},
  { category: '代码仓库', items: [
    { id: 'github', label: 'GitHub', desc: 'GitHub API 操作' },
    { id: 'gitlab', label: 'GitLab', desc: 'GitLab API 操作' },
  ]},
  { category: '容器与运维', items: [
    { id: 'docker', label: 'Docker', desc: 'Docker 容器管理' },
    { id: 'sql', label: 'SQL', desc: '数据库查询' },
    { id: 'postgres', label: 'PostgreSQL', desc: 'PostgreSQL 连接' },
  ]},
  { category: '爬虫与抓取', items: [
    { id: 'firecrawl', label: 'Firecrawl', desc: '网页内容抓取' },
    { id: 'crawl4ai', label: 'Crawl4AI', desc: 'AI 驱动爬取' },
    { id: 'spider', label: 'Spider', desc: '通用爬虫' },
    { id: 'browserbase', label: 'Browserbase', desc: '浏览器自动化' },
    { id: 'jina', label: 'Jina Reader', desc: '文章阅读优化' },
  ]},
  { category: '通讯', items: [
    { id: 'gmail', label: 'Gmail', desc: '邮件收发' },
    { id: 'slack', label: 'Slack', desc: 'Slack 消息' },
    { id: 'discord', label: 'Discord', desc: 'Discord 消息' },
    { id: 'telegram', label: 'Telegram', desc: 'Telegram 消息' },
    { id: 'notion', label: 'Notion', desc: 'Notion 集成' },
  ]},
  { category: '项目管理', items: [
    { id: 'jira', label: 'Jira', desc: 'Jira 项目管理' },
    { id: 'linear', label: 'Linear', desc: 'Linear 任务管理' },
    { id: 'trello', label: 'Trello', desc: 'Trello 看板' },
  ]},
  { category: '其他', items: [
    { id: 'dalle', label: 'DALL-E', desc: '图片生成' },
    { id: 'youtube', label: 'YouTube', desc: '视频搜索与转录' },
    { id: 'spotify', label: 'Spotify', desc: '音乐播放' },
    { id: 'openweather', label: 'OpenWeather', desc: '天气查询' },
    { id: 'apify', label: 'Apify', desc: '自动化平台' },
  ]},
]

const ALL_TOOL_IDS = AGNO_TOOLS.flatMap(c => c.items.map(t => t.id))

// ─── Team 页面 ──────────────────────────────────────────────────
function TeamsPage() {
  const [teams, setTeams] = useState([])
  const [agents, setAgents] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingTeam, setEditingTeam] = useState(null)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', mode: 'coordinate', members: [], instructions: '', respond_directly: false })

  const loadTeams = async () => {
    try { const r = await axios.get(`${API_BASE}/api/teams`); setTeams(r.data) } catch (e) { console.error(e) }
  }
  const loadAgents = async () => {
    try { const r = await axios.get(`${API_BASE}/api/agents`); setAgents(r.data) } catch (e) { console.error(e) }
  }
  useEffect(() => { loadTeams(); loadAgents() }, [])

  const openCreate = () => { setEditingTeam(null); setForm({ name: '', description: '', mode: 'coordinate', members: [], instructions: '', respond_directly: false }); setShowModal(true) }
  const openEdit = (team) => {
    setEditingTeam(team)
    setForm({
      name: team.name, description: team.description || '', mode: team.mode || 'coordinate',
      members: team.members || [], instructions: team.instructions || '', respond_directly: !!team.respond_directly
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) return
    setLoading(true)
    try {
      if (editingTeam) {
        await axios.put(`${API_BASE}/api/teams/${editingTeam.id}`, form)
      } else {
        await axios.post(`${API_BASE}/api/teams`, form)
      }
      setShowModal(false)
      loadTeams()
    } catch (e) { console.error(e) } finally { setLoading(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除此 Team？')) return
    try { await axios.delete(`${API_BASE}/api/teams/${id}`); loadTeams() } catch (e) { console.error(e) }
  }

  const toggleMember = (agentId) => {
    const members = form.members.includes(agentId)
      ? form.members.filter(a => a !== agentId)
      : [...form.members, agentId]
    setForm({ ...form, members })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Users className="w-6 h-6 text-blue-600" /> Team 管理</h1>
          <p className="text-sm text-gray-500 mt-1">多 Agent 协作团队，支持协调模式与并行模式</p>
        </div>
        <button onClick={openCreate} className="px-4 py-2 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-lg hover:shadow-lg transition-all flex items-center gap-2">
          <Plus className="w-4 h-4" /> 新建 Team
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teams.map(team => (
          <div key={team.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow group">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center text-white font-bold">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{team.name}</h3>
                  <p className="text-xs text-gray-500 capitalize">{team.mode === 'coordinate' ? '协调模式' : '并行模式'}</p>
                </div>
              </div>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => openEdit(team)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-blue-600"><Edit2 className="w-3.5 h-3.5" /></button>
                <button onClick={() => handleDelete(team.id)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
            {team.description && <p className="text-sm text-gray-600 mb-3 line-clamp-2">{team.description}</p>}
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span className="flex items-center gap-1"><Bot className="w-3 h-3" />{Array.isArray(team.members) ? team.members.length : 0} 成员</span>
            </div>
            {team.instructions && (
              <details className="mt-3">
                <summary className="text-xs text-purple-600 cursor-pointer hover:text-purple-700">查看指令</summary>
                <p className="text-xs text-gray-600 mt-1 whitespace-pre-wrap max-h-32 overflow-y-auto">{team.instructions}</p>
              </details>
            )}
          </div>
        ))}
        {teams.length === 0 && (
          <div className="col-span-full text-center py-16 text-gray-400">
            <Users className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">暂无 Team</p>
            <p className="text-sm mt-1">点击"新建 Team"开始</p>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b flex justify-between items-center">
              <h2 className="text-xl font-bold">{editingTeam ? '编辑 Team' : '新建 Team'}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 text-2xl">&times;</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                  value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="例如：代码审查团队" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                  value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="简要说明" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">协作模式</label>
                  <select className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                    value={form.mode} onChange={e => setForm({...form, mode: e.target.value})}>
                    <option value="coordinate">协调模式 (Coordinate)</option>
                    <option value="parallel">并行模式 (Parallel)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">直接响应</label>
                  <select className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10"
                    value={form.respond_directly ? 'true' : 'false'} onChange={e => setForm({...form, respond_directly: e.target.value === 'true'})}>
                    <option value="false">否（聚合输出）</option>
                    <option value="true">是（直接回复）</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">团队指令</label>
                <RichTextEditor
                  value={form.instructions}
                  onChange={(html) => setForm({...form, instructions: html})}
                  placeholder="团队整体行为指导..."
                  minHeight={160}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">团队成员（选择 Agent）*</label>
                <div className="border border-gray-200 rounded-lg p-3 max-h-48 overflow-y-auto">
                  {agents.length === 0 ? (
                    <p className="text-xs text-gray-400">暂无 Agent。先去 <button onClick={() => window.location.href='/agents'} className="text-blue-600 hover:underline">Agent 管理</button> 创建</p>
                  ) : agents.filter(a => a.active !== 0).map(agent => (
                    <label key={agent.id} className="flex items-center gap-2 py-1.5 text-sm hover:bg-gray-50 rounded px-1">
                      <input type="checkbox" checked={form.members.includes(agent.id)}
                        onChange={() => toggleMember(agent.id)} className="rounded border-gray-300 text-blue-600" />
                      <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center text-white text-xs font-bold">
                        {agent.name?.[0]?.toUpperCase()}
                      </div>
                      <span>{agent.name}</span>
                      <span className="text-xs text-gray-400 ml-auto">{agent.model}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-6 border-t flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">取消</button>
              <button onClick={handleSave} disabled={loading || !form.name.trim() || form.members.length === 0} className="px-4 py-2 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-lg disabled:opacity-50">
                {editingTeam ? '保存' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Workflow 页面 ──────────────────────────────────────────────
function WorkflowsPage() {
  const [workflows, setWorkflows] = useState([])
  const [agents, setAgents] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editingWorkflow, setEditingWorkflow] = useState(null)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', steps: [] })

  const loadWorkflows = async () => {
    try { const r = await axios.get(`${API_BASE}/api/workflows`); setWorkflows(r.data) } catch (e) { console.error(e) }
  }
  const loadAgents = async () => {
    try { const r = await axios.get(`${API_BASE}/api/agents`); setAgents(r.data) } catch (e) { console.error(e) }
  }
  useEffect(() => { loadWorkflows(); loadAgents() }, [])

  const openCreate = () => { setEditingWorkflow(null); setForm({ name: '', description: '', steps: [] }); setShowModal(true) }
  const openEdit = (wf) => {
    setEditingWorkflow(wf)
    setForm({ name: wf.name, description: wf.description || '', steps: wf.steps || [] })
    setShowModal(true)
  }

  const addStep = () => {
    setForm({ ...form, steps: [...form.steps, { agent_id: '', description: '' }] })
  }

  const removeStep = (index) => {
    setForm({ ...form, steps: form.steps.filter((_, i) => i !== index) })
  }

  const updateStep = (index, field, value) => {
    const steps = [...form.steps]
    steps[index] = { ...steps[index], [field]: value }
    setForm({ ...form, steps })
  }

  const handleSave = async () => {
    if (!form.name.trim() || form.steps.length === 0) return
    setLoading(true)
    try {
      if (editingWorkflow) {
        await axios.put(`${API_BASE}/api/workflows/${editingWorkflow.id}`, form)
      } else {
        await axios.post(`${API_BASE}/api/workflows`, form)
      }
      setShowModal(false)
      loadWorkflows()
    } catch (e) { console.error(e) } finally { setLoading(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除此 Workflow？')) return
    try { await axios.delete(`${API_BASE}/api/workflows/${id}`); loadWorkflows() } catch (e) { console.error(e) }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Layers className="w-6 h-6 text-green-600" /> Workflow 管理</h1>
          <p className="text-sm text-gray-500 mt-1">顺序执行的 Agent 流水线，每个步骤由一个 Agent 完成</p>
        </div>
        <button onClick={openCreate} className="px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-lg hover:shadow-lg transition-all flex items-center gap-2">
          <Plus className="w-4 h-4" /> 新建 Workflow
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {workflows.map(wf => (
          <div key={wf.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow group">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-400 to-emerald-400 flex items-center justify-center text-white font-bold">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{wf.name}</h3>
                  <p className="text-xs text-gray-500">{Array.isArray(wf.steps) ? wf.steps.length : 0} 步</p>
                </div>
              </div>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => openEdit(wf)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-green-600"><Edit2 className="w-3.5 h-3.5" /></button>
                <button onClick={() => handleDelete(wf.id)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
            {wf.description && <p className="text-sm text-gray-600 mb-3 line-clamp-2">{wf.description}</p>}
            {Array.isArray(wf.steps) && wf.steps.length > 0 && (
              <div className="space-y-1">
                {wf.steps.slice(0, 3).map((step, i) => {
                  const agent = agents.find(a => a.id === step.agent_id)
                  return (
                    <div key={i} className="flex items-center gap-2 text-xs text-gray-500">
                      <ChevronRight className="w-3 h-3 text-green-400" />
                      <span>{agent ? agent.name : `步骤 ${i + 1}`}</span>
                    </div>
                  )
                })}
                {wf.steps.length > 3 && <p className="text-xs text-gray-400">+{wf.steps.length - 3} 更多步骤</p>}
              </div>
            )}
          </div>
        ))}
        {workflows.length === 0 && (
          <div className="col-span-full text-center py-16 text-gray-400">
            <Layers className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">暂无 Workflow</p>
            <p className="text-sm mt-1">点击"新建 Workflow"开始</p>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b flex justify-between items-center">
              <h2 className="text-xl font-bold">{editingWorkflow ? '编辑 Workflow' : '新建 Workflow'}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 text-2xl">&times;</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-green-500 focus:ring-2 focus:ring-green-500/10"
                  value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="例如：PRD → TD → 测试用例" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-green-500 focus:ring-2 focus:ring-green-500/10"
                  value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="简要说明" />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700">执行步骤 *</label>
                  <button onClick={addStep} className="text-xs text-green-600 hover:text-green-700 flex items-center gap-1">
                    <Plus className="w-3 h-3" /> 添加步骤
                  </button>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {form.steps.map((step, index) => (
                    <div key={index} className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-xs font-bold">{index + 1}</div>
                      <select className="flex-1 p-2 border border-gray-200 rounded text-sm focus:border-green-500"
                        value={step.agent_id || ''} onChange={e => updateStep(index, 'agent_id', e.target.value)}>
                        <option value="">选择 Agent...</option>
                        {agents.filter(a => a.active !== 0).map(a => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))}
                      </select>
                      <button onClick={() => removeStep(index)} className="p-1 text-gray-400 hover:text-red-500"><X className="w-4 h-4" /></button>
                    </div>
                  ))}
                  {form.steps.length === 0 && <p className="text-sm text-gray-400 text-center py-4">至少需要 1 个步骤</p>}
                </div>
              </div>
            </div>
            <div className="p-6 border-t flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">取消</button>
              <button onClick={handleSave} disabled={loading || !form.name.trim() || form.steps.length === 0} className="px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-lg disabled:opacity-50">
                {editingWorkflow ? '保存' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Agent 页面（增强版：Tool 选择 + 更新弹窗）───────────────────
function AgentsPageInner() {
  const [agents, setAgents] = useState([])
  const [skills, setSkills] = useState([])
  const [kbs, setKbs] = useState([])
  const [mcpServers, setMcpServers] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [showToolSelector, setShowToolSelector] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [loading, setLoading] = useState(false)
  const [editingAgent, setEditingAgent] = useState(null)
  const [activeToolCategory, setActiveToolCategory] = useState(AGNO_TOOLS[0].category)

  const [form, setForm] = useState({
    name: '', description: '', instructions: '', model: 'agnes-2.0-flash',
    enable_memory: false, enable_reasoning: false,
    tools: [], knowledge_base_ids: [], skill_ids: [], mcp_server_ids: []
  })

  const loadAll = async () => {
    try {
      const [agentsR, skillsR, kbsR, mcpR] = await Promise.all([
        axios.get(`${API_BASE}/api/agents`),
        axios.get(`${API_BASE}/api/skills`),
        axios.get(`${API_BASE}/api/knowledge-bases`),
        axios.get(`${API_BASE}/api/mcp-servers`),
      ])
      setAgents(agentsR.data)
      setSkills(skillsR.data)
      setKbs(kbsR.data)
      setMcpServers(mcpR.data)
    } catch (e) { console.error(e) }
  }

  useEffect(() => { loadAll() }, [])

  const openCreate = () => {
    setEditingAgent(null)
    setForm({ name: '', description: '', instructions: '', model: 'agnes-2.0-flash', enable_memory: false, enable_reasoning: false, tools: [], knowledge_base_ids: [], skill_ids: [], mcp_server_ids: [] })
    setShowModal(true)
  }

  const openEdit = (agent) => {
    setEditingAgent(agent)
    const tools = typeof agent.tools === 'string' ? (JSON.parse(agent.tools) || []) : (agent.tools || [])
    const kbIds = typeof agent.knowledge_base_ids === 'string' ? (JSON.parse(agent.knowledge_base_ids) || []) : (agent.knowledge_base_ids || [])
    const skillIds = typeof agent.skill_ids === 'string' ? (JSON.parse(agent.skill_ids) || []) : (agent.skill_ids || [])
    const mcpIds = typeof agent.mcp_server_ids === 'string' ? (JSON.parse(agent.mcp_server_ids) || []) : (agent.mcp_server_ids || [])
    setForm({
      name: agent.name, description: agent.description || '', instructions: agent.instructions || '',
      model: agent.model || 'agnes-2.0-flash', enable_memory: !!agent.enable_memory, enable_reasoning: !!agent.enable_reasoning,
      tools, knowledge_base_ids: kbIds, skill_ids: skillIds, mcp_server_ids: mcpIds
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) return
    setLoading(true)
    try {
      const payload = {
        name: form.name, description: form.description, instructions: form.instructions,
        model: form.model, enable_memory: form.enable_memory, enable_reasoning: form.enable_reasoning,
        tools: form.tools, knowledge_base_ids: form.knowledge_base_ids,
        skill_ids: form.skill_ids, mcp_server_ids: form.mcp_server_ids
      }
      if (editingAgent) {
        await axios.put(`${API_BASE}/api/agents/${editingAgent.id}`, payload)
      } else {
        await axios.post(`${API_BASE}/api/agents`, payload)
      }
      setShowModal(false)
      loadAll()
    } catch (e) { console.error(e) } finally { setLoading(false) }
  }

  const handleDelete = async (agentId) => {
    if (!confirm('确定删除此 Agent？')) return
    try { await axios.delete(`${API_BASE}/api/agents/${agentId}`); loadAll() } catch (e) { console.error(e) }
  }

  const toggleTool = (toolId) => {
    const tools = form.tools.includes(toolId)
      ? form.tools.filter(t => t !== toolId)
      : [...form.tools, toolId]
    setForm({ ...form, tools })
  }

  const toggleMcpServer = (serverId) => {
    const mcpIds = form.mcp_server_ids.includes(serverId)
      ? form.mcp_server_ids.filter(s => s !== serverId)
      : [...form.mcp_server_ids, serverId]
    setForm({ ...form, mcp_server_ids: mcpIds })
  }

  const getToolLabel = (id) => {
    for (const cat of AGNO_TOOLS) {
      const t = cat.items.find(i => i.id === id)
      if (t) return t.label
    }
    return id
  }

  const getToolDesc = (id) => {
    for (const cat of AGNO_TOOLS) {
      const t = cat.items.find(i => i.id === id)
      if (t) return t.desc
    }
    return ''
  }

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (a.description || '').toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Bot className="w-6 h-6 text-purple-600" /> Agent 管理</h1>
          <p className="text-sm text-gray-500 mt-1">创建和管理 AI Agent，绑定工具、Skills 和知识库</p>
        </div>
        <button onClick={openCreate} className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:shadow-lg transition-all flex items-center gap-2">
          <Plus className="w-4 h-4" /> 新建 Agent
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input type="text" placeholder="搜索 Agent..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10" />
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredAgents.map(agent => {
          const tools = typeof agent.tools === 'string' ? (JSON.parse(agent.tools) || []) : (agent.tools || [])
          const kbIds = typeof agent.knowledge_base_ids === 'string' ? (JSON.parse(agent.knowledge_base_ids) || []) : (agent.knowledge_base_ids || [])
          return (
            <div key={agent.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow group">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white font-bold text-lg">
                    {agent.name?.[0]?.toUpperCase() || 'A'}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{agent.name}</h3>
                    <p className="text-xs text-gray-500">{agent.model || 'agnes-2.0-flash'}</p>
                  </div>
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => openEdit(agent)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-blue-600" title="编辑"><Edit2 className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(agent.id)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-red-600" title="删除"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              {agent.description && <p className="text-sm text-gray-600 mb-3 line-clamp-2">{agent.description}</p>}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                {tools.length > 0 && (
                  <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 rounded-full">
                    <Code2 className="w-3 h-3" />{tools.length} 工具
                  </span>
                )}
                {kbIds.length > 0 && (
                  <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">
                    <Database className="w-3 h-3" />{kbIds.length} KB
                  </span>
                )}
                {agent.enable_memory && <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded-full">记忆</span>}
                {agent.enable_reasoning && <span className="px-2 py-0.5 bg-orange-50 text-orange-700 rounded-full">推理</span>}
              </div>
              {agent.instructions && (
                <details className="mt-3">
                  <summary className="text-xs text-purple-600 cursor-pointer hover:text-purple-700">查看指令</summary>
                  <p className="text-xs text-gray-600 mt-1 whitespace-pre-wrap max-h-32 overflow-y-auto">{agent.instructions}</p>
                </details>
              )}
            </div>
          )
        })}
        {filteredAgents.length === 0 && (
          <div className="col-span-full text-center py-16 text-gray-400">
            <Bot className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">暂无 Agent</p>
            <p className="text-sm mt-1">点击"新建 Agent"开始</p>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b flex justify-between items-center sticky top-0 bg-white z-10">
              <h2 className="text-xl font-bold">{editingAgent ? '编辑 Agent' : '新建 Agent'}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 text-2xl">&times;</button>
            </div>
            <div className="p-6 space-y-5">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
                  <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                    value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="例如：代码审查专家" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">模型</label>
                  <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                    value={form.model} onChange={e => setForm({...form, model: e.target.value})} placeholder="agnes-2.0-flash" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <input type="text" className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
                  value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="简要说明用途" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">指令 (Instructions)</label>
                <RichTextEditor
                  value={form.instructions}
                  onChange={(html) => setForm({...form, instructions: html})}
                  placeholder="# 角色\n你是一个资深..."
                  minHeight={200}
                />
              </div>

              {/* Toggles */}
              <div className="flex gap-6">
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="checkbox" checked={form.enable_memory} onChange={e => setForm({...form, enable_memory: e.target.checked})}
                    className="rounded border-gray-300 text-purple-600" />
                  <Settings className="w-4 h-4 text-purple-500" />启用记忆
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="checkbox" checked={form.enable_reasoning} onChange={e => setForm({...form, enable_reasoning: e.target.checked})}
                    className="rounded border-gray-300 text-purple-600" />
                  <Eye className="w-4 h-4 text-orange-500" />启用推理
                </label>
              </div>

              {/* Tools Selector */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700">工具 (Tools)</label>
                  <button onClick={() => setShowToolSelector(!showToolSelector)}
                    className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1">
                    {showToolSelector ? '收起' : '选择工具'} ({form.tools.length} 已选)
                  </button>
                </div>

                {/* Selected tools tags */}
                {form.tools.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {form.tools.map(t => (
                      <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 rounded-full text-xs">
                        {getToolLabel(t)}
                        <button onClick={() => toggleTool(t)} className="hover:text-red-500"><X className="w-3 h-3" /></button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Full tool selector */}
                {showToolSelector && (
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    {/* Category tabs */}
                    <div className="flex overflow-x-auto border-b bg-gray-50">
                      {AGNO_TOOLS.map(cat => (
                        <button key={cat.category} onClick={() => setActiveToolCategory(cat.category)}
                          className={`px-3 py-2 text-xs font-medium whitespace-nowrap ${activeToolCategory === cat.category ? 'bg-white text-purple-700 border-b-2 border-purple-500' : 'text-gray-600 hover:text-gray-900'}`}>
                          {cat.category}
                        </button>
                      ))}
                    </div>
                    {/* Tools list */}
                    <div className="max-h-48 overflow-y-auto p-2">
                      {AGNO_TOOLS.find(c => c.category === activeToolCategory)?.items.map(tool => (
                        <label key={tool.id} className="flex items-center gap-2 p-2 rounded hover:bg-gray-50 cursor-pointer">
                          <input type="checkbox" checked={form.tools.includes(tool.id)}
                            onChange={() => toggleTool(tool.id)}
                            className="rounded border-gray-300 text-purple-600" />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-800">{tool.label}</div>
                            <div className="text-xs text-gray-400 truncate">{tool.desc}</div>
                          </div>
                          {form.tools.includes(tool.id) && <Check className="w-4 h-4 text-purple-600 flex-shrink-0" />}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* MCP Servers */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">MCP Servers</label>
                <div className="border border-gray-200 rounded-lg p-3 max-h-32 overflow-y-auto">
                  {mcpServers.length === 0 ? (
                    <p className="text-xs text-gray-400">暂无 MCP Server。去 <button onClick={() => window.location.href='/mcp-servers'} className="text-purple-600 hover:underline">MCP 管理</button> 创建</p>
                  ) : mcpServers.map(server => (
                    <label key={server.id} className="flex items-center gap-2 py-1 text-sm">
                      <input type="checkbox" checked={form.mcp_server_ids.includes(server.id)}
                        onChange={() => toggleMcpServer(server.id)}
                        className="rounded border-gray-300 text-purple-600" />
                      {server.name}
                      <span className="text-xs text-gray-400 ml-auto">{server.transport_type}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Skills */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Skills</label>
                <div className="border border-gray-200 rounded-lg p-3 max-h-32 overflow-y-auto">
                  {skills.length === 0 ? (
                    <p className="text-xs text-gray-400">暂无 Skills。去 <button onClick={() => window.location.href='/skills'} className="text-purple-600 hover:underline">Skills 管理</button> 创建</p>
                  ) : skills.map(s => (
                    <label key={s.id} className="flex items-center gap-2 py-1 text-sm">
                      <input type="checkbox" checked={form.skill_ids.includes(s.id)}
                        onChange={e => {
                          const ids = e.target.checked ? [...form.skill_ids, s.id] : form.skill_ids.filter(x => x !== s.id)
                          setForm({...form, skill_ids: ids})
                        }}
                        className="rounded border-gray-300 text-purple-600" />
                      {s.name}
                    </label>
                  ))}
                </div>
              </div>

              {/* Knowledge Bases */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Knowledge Bases</label>
                <div className="border border-gray-200 rounded-lg p-3 max-h-32 overflow-y-auto">
                  {kbs.length === 0 ? (
                    <p className="text-xs text-gray-400">暂无知识库</p>
                  ) : kbs.map(kb => (
                    <label key={kb.id} className="flex items-center gap-2 py-1 text-sm">
                      <input type="checkbox" checked={form.knowledge_base_ids.includes(kb.id)}
                        onChange={e => {
                          const ids = e.target.checked ? [...form.knowledge_base_ids, kb.id] : form.knowledge_base_ids.filter(x => x !== kb.id)
                          setForm({...form, knowledge_base_ids: ids})
                        }}
                        className="rounded border-gray-300 text-purple-600" />
                      {kb.name}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-6 border-t flex justify-end gap-2 sticky bottom-0 bg-white">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">取消</button>
              <button onClick={handleSave} disabled={loading || !form.name.trim()} className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg disabled:opacity-50">
                {editingAgent ? '保存' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── 主入口：根据 tab 切换 ───────────────────────────────────────
export default function AgentsPage({ tab }) {
  if (tab === 'teams') return <TeamsPage />
  if (tab === 'workflows') return <WorkflowsPage />
  return <AgentsPageInner />
}
