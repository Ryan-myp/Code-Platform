import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  MessageSquare, Send, Users, Layers, Menu, X,
  Sparkles, User, Plus, Trash2, Search, Clock,
  Bot as BotIcon, ArrowRight, RefreshCw, Brain, ChevronDown,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import { Button, Empty, SkeletonList, ErrorState, ConfirmDialog } from '../components/ui'

const TARGET_TYPES = {
  agent: { icon: BotIcon, color: 'text-purple-600', chip: 'bg-purple-100 text-purple-700' },
  team: { icon: Users, color: 'text-emerald-600', chip: 'bg-emerald-100 text-emerald-700' },
  workflow: { icon: Layers, color: 'text-blue-600', chip: 'bg-blue-100 text-blue-700' },
}

const targetMeta = (type) => TARGET_TYPES[type] || TARGET_TYPES.agent

const EXAMPLES = [
  { text: '@产品经理Agent 帮我写一个电商下单功能的 PRD', color: 'text-purple-600' },
  { text: '@代码审查团队 审查这个 PRD 的质量', color: 'text-emerald-600' },
  { text: '@项目管理员 创建一个新的电商平台项目', color: 'text-blue-600' },
]

export default function ChatPage() {
  const navigate = useNavigate()
  const toast = useToast()

  const [conversations, setConversations] = useState([])
  const [convLoading, setConvLoading] = useState(true)
  const [convError, setConvError] = useState(null)
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [inputText, setInputText] = useState('')
  const [sending, setSending] = useState(false)

  const [agents, setAgents] = useState([])
  const [teams, setTeams] = useState([])
  const [workflows, setWorkflows] = useState([])
  const [targetsLoading, setTargetsLoading] = useState(true)

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // 会话记忆（GET/POST /api/conversations/{id}/memories）
  const [memories, setMemories] = useState([])
  const [memInput, setMemInput] = useState('')
  const [memOpen, setMemOpen] = useState(false)
  const [memBusy, setMemBusy] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // 加载可用目标（agents / teams / workflows）
  const fetchTargets = useCallback(async () => {
    setTargetsLoading(true)
    try {
      const [agentsRes, teamsRes, workflowsRes] = await Promise.all([
        api.get('/api/agents').catch(() => ({ data: [] })),
        api.get('/api/teams').catch(() => ({ data: [] })),
        api.get('/api/workflows').catch(() => ({ data: [] })),
      ])
      setAgents(agentsRes.data || [])
      setTeams(teamsRes.data || [])
      setWorkflows(workflowsRes.data || [])
    } finally {
      setTargetsLoading(false)
    }
  }, [])

  // 加载会话列表（基于第一个 agent，作为默认会话容器）
  const fetchConversations = useCallback(async () => {
    if (agents.length === 0) {
      setConversations([])
      setConvLoading(false)
      return
    }
    setConvLoading(true)
    setConvError(null)
    try {
      const res = await api.get(`/api/agents/${agents[0].id}/conversations`)
      setConversations(res.data || [])
    } catch (e) {
      setConvError(e)
    } finally {
      setConvLoading(false)
    }
  }, [agents])

  useEffect(() => { fetchTargets() }, [fetchTargets])
  useEffect(() => { fetchConversations() }, [fetchConversations])

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  // 解析 @mentions
  const parseMentions = (text) => {
    const matches = text.match(/@(\S+)/g) || []
    return matches.map((m) => m.substring(1))
  }

  // 将 @name 解析为实际 agent / team / workflow
  const resolveTargets = (names) => {
    const resolved = []
    const seen = new Set()
    names.forEach((name) => {
      const lower = name.toLowerCase()
      const agent = agents.find((a) => a.name?.toLowerCase().includes(lower))
      if (agent) {
        if (!seen.has('agent:' + agent.id)) { resolved.push({ type: 'agent', ...agent }); seen.add('agent:' + agent.id) }
        return
      }
      const team = teams.find((t) => t.name?.toLowerCase().includes(lower))
      if (team) {
        if (!seen.has('team:' + team.id)) { resolved.push({ type: 'team', ...team }); seen.add('team:' + team.id) }
        return
      }
      const wf = workflows.find((w) => w.name?.toLowerCase().includes(lower))
      if (wf) {
        if (!seen.has('workflow:' + wf.id)) { resolved.push({ type: 'workflow', ...wf }); seen.add('workflow:' + wf.id) }
      }
    })
    return resolved
  }

  // 加载会话记忆
  const loadMemories = async (convId) => {
    if (!convId) { setMemories([]); return }
    try {
      const res = await api.get(`/api/conversations/${convId}/memories`)
      setMemories(res.data || [])
    } catch { setMemories([]) }
  }

  // 添加记忆
  const addMemory = async () => {
    if (!memInput.trim() || !activeConversationId) return
    setMemBusy(true)
    try {
      await api.post(`/api/conversations/${activeConversationId}/memories`, { content: memInput.trim() })
      setMemInput('')
      toast.success('记忆已保存，后续对话可引用')
      loadMemories(activeConversationId)
    } catch (e) { toast.error(`保存失败：${e.message}`) }
    finally { setMemBusy(false) }
  }

  // 删除记忆
  const deleteMemory = async (memId) => {
    try {
      await api.delete(`/api/conversations/memories/${memId}`)
      setMemories((prev) => prev.filter((m) => m.id !== memId))
      toast.success('记忆已删除')
    } catch (e) { toast.error(`删除失败：${e.message}`) }
  }

  // 加载某个会话的消息
  const loadConversation = async (convId) => {
    setMessagesLoading(true)
    try {
      const res = await api.get(`/api/conversations/${convId}`)
      const msgs = (res.data.messages || []).map((m) => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content || '',
        timestamp: m.timestamp || new Date().toISOString(),
      }))
      setMessages(msgs)
      setActiveConversationId(convId)
      setSidebarOpen(false)
      loadMemories(convId)
    } catch (e) {
      toast.error(`加载会话失败：${e.message}`)
    } finally {
      setMessagesLoading(false)
    }
  }

  // 新建会话
  const handleNewConversation = async () => {
    if (agents.length === 0) {
      toast.error('请先创建 Agent 后再开始对话')
      return
    }
    const agentId = agents[0].id
    const title = `对话 ${new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`
    try {
      const res = await api.post(`/api/agents/${agentId}/conversations`, { title })
      setActiveConversationId(res.data.id)
      setMessages([])
      setMemories([])
      setSidebarOpen(false)
      fetchConversations()
      inputRef.current?.focus()
    } catch (e) {
      toast.error(`创建会话失败：${e.message}`)
    }
  }

  // 删除会话（由 ConfirmDialog 触发）
  const handleDeleteConversation = async () => {
    if (!deleteTarget) return false
    setDeleting(true)
    try {
      await api.delete(`/api/conversations/${deleteTarget.id}`)
      toast.success('会话已删除')
      if (activeConversationId === deleteTarget.id) {
        setActiveConversationId(null)
        setMessages([])
        setMemories([])
      }
      setDeleteTarget(null)
      fetchConversations()
      return true
    } catch (e) {
      toast.error(`删除会话失败：${e.message}`)
      return false
    } finally {
      setDeleting(false)
    }
  }

  // 发送消息
  const handleSend = async () => {
    const content = inputText.trim()
    if (!content || sending) return

    const targets = resolveTargets(parseMentions(content))

    if (targets.length === 0 && agents.length === 0) {
      toast.error('请先创建 Agent，或在消息中 @mention 一个 Agent/Team/Workflow')
      return
    }

    const userMessage = { role: 'user', content, timestamp: new Date().toISOString(), targets }
    setMessages((prev) => [...prev, userMessage])
    setInputText('')
    setSending(true)

    // 关键修复：使用局部 convId 贯穿整个流程，避免依赖闭包中陈旧的 activeConversationId
    let convId = activeConversationId

    try {
      // 确保会话存在（无活动会话时基于首要 agent 创建）
      if (!convId && agents.length > 0) {
        const primaryAgentId = targets.find((t) => t.type === 'agent')?.id || agents[0].id
        const title = content.length > 30 ? content.slice(0, 30) + '…' : content
        const convRes = await api.post(`/api/agents/${primaryAgentId}/conversations`, { title })
        convId = convRes.data.id
        setActiveConversationId(convId)
        fetchConversations()
      }

      // 持久化用户消息
      if (convId) {
        try {
          await api.post(`/api/conversations/${convId}/messages`, { role: 'user', content })
        } catch {
          /* 持久化失败不阻塞展示 */
        }
      }

      let assistantContent = ''

      if (targets.length === 0) {
        // 无 @mention → 默认 agent
        const res = await api.post(`/api/agents/${agents[0].id}/run`, { message: content })
        assistantContent = res.data.result || '（无返回结果）'
      } else if (targets.length === 1) {
        const t = targets[0]
        const url = t.type === 'agent'
          ? `/api/agents/${t.id}/run`
          : t.type === 'team' ? `/api/teams/${t.id}/run` : `/api/workflows/${t.id}/run`
        const res = await api.post(url, { message: content })
        assistantContent = res.data.result || '（无返回结果）'
      } else {
        // 多目标并行 → 聚合
        const results = await Promise.allSettled(
          targets.map((t) => {
            const url = t.type === 'agent'
              ? `/api/agents/${t.id}/run`
              : t.type === 'team' ? `/api/teams/${t.id}/run` : `/api/workflows/${t.id}/run`
            return api.post(url, { message: content }).then((res) => res.data.result || '（无返回结果）')
          })
        )
        assistantContent = results
          .map((r, i) => {
            const t = targets[i]
            if (r.status === 'fulfilled') return `### ${t.name}\n\n${r.value}`
            return `### ${t.name}\n\n❌ 执行失败：${r.reason?.message || '未知错误'}`
          })
          .join('\n\n---\n\n')
      }

      // 持久化 assistant 消息（使用局部 convId，修复原代码依赖 null conversationId 的 bug）
      if (convId) {
        try {
          await api.post(`/api/conversations/${convId}/messages`, { role: 'assistant', content: assistantContent })
        } catch {
          /* 持久化失败不阻塞展示 */
        }
      }

      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: assistantContent,
        timestamp: new Date().toISOString(),
        targets,
      }])
    } catch (e) {
      setMessages((prev) => [...prev, {
        role: 'error',
        content: `执行失败：${e.message}`,
        timestamp: new Date().toISOString(),
      }])
      toast.error(`执行失败：${e.message}`)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // @mention 建议器
  const mentionMatch = inputText.match(/@(\w*)$/)
  const showSuggestions = !!mentionMatch
  const mentionQuery = mentionMatch ? mentionMatch[1].toLowerCase() : ''

  const insertMention = (name) => {
    setInputText((prev) => prev.replace(/@\w*$/, `@${name} `))
    inputRef.current?.focus()
  }

  const filteredAgents = agents.filter((a) => a.name?.toLowerCase().includes(mentionQuery))
  const filteredTeams = teams.filter((t) => t.name?.toLowerCase().includes(mentionQuery))
  const filteredWorkflows = workflows.filter((w) => w.name?.toLowerCase().includes(mentionQuery))
  const hasSuggestions = filteredAgents.length + filteredTeams.length + filteredWorkflows.length > 0

  const filteredConversations = conversations.filter((c) =>
    (c.title || '未命名对话').toLowerCase().includes(searchQuery.toLowerCase())
  )

  const sidebarLoading = targetsLoading || convLoading
  const noResources = !targetsLoading && agents.length === 0 && teams.length === 0 && workflows.length === 0
  const activeConversation = conversations.find((c) => c.id === activeConversationId)

  const renderSidebar = () => (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-gray-900 flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-purple-600" />
            对话列表
          </h2>
          <Button size="sm" variant="ghost" icon={Plus} onClick={handleNewConversation} title="新建对话">
            新建
          </Button>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索对话…"
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sidebarLoading ? (
          <div className="p-2"><SkeletonList count={4} /></div>
        ) : convError ? (
          <div className="p-2">
            <ErrorState message={`加载会话失败：${convError.message}`} onRetry={fetchConversations} />
          </div>
        ) : filteredConversations.length === 0 ? (
          <Empty
            icon={MessageSquare}
            title={searchQuery ? '未找到匹配的对话' : '暂无对话'}
            description={searchQuery ? '尝试调整搜索关键词' : '点击「新建」开始第一轮对话'}
            actionLabel={searchQuery ? undefined : '新建对话'}
            onAction={searchQuery ? undefined : handleNewConversation}
            className="py-10"
          />
        ) : (
          filteredConversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => loadConversation(conv.id)}
              className={`p-3 rounded-lg cursor-pointer group relative transition-colors ${
                activeConversationId === conv.id
                  ? 'bg-purple-50 border border-purple-200'
                  : 'hover:bg-gray-50 border border-transparent'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{conv.title || '未命名对话'}</p>
                  <div className="flex items-center gap-1.5 mt-1 text-xs text-gray-400">
                    <Clock className="w-3 h-3" />
                    <span>{formatRelativeTime(conv.updated_at || conv.created_at)}</span>
                    {conv.message_count != null && (
                      <>
                        <span>·</span>
                        <span>{conv.message_count} 条</span>
                      </>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(conv) }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded transition-opacity"
                  title="删除对话"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-500" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="p-3 border-t border-gray-200 text-xs text-gray-400 text-center">
        共 {conversations.length} 个对话
      </div>
    </div>
  )

  return (
    <div className="flex h-[calc(100vh-2rem)] md:h-[calc(100vh-3rem)] gap-0 md:gap-4">
      {/* 桌面侧边栏 */}
      <aside className="hidden md:flex w-72 bg-white rounded-2xl border border-gray-200 overflow-hidden flex-shrink-0">
        {renderSidebar()}
      </aside>

      {/* 移动端抽屉 */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[80vw] bg-white shadow-xl flex flex-col">
            <div className="flex justify-end p-2">
              <button onClick={() => setSidebarOpen(false)} className="p-1.5 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">{renderSidebar()}</div>
          </aside>
        </div>
      )}

      {/* 主区域 */}
      <section className="flex-1 flex flex-col min-w-0 bg-white rounded-2xl border border-gray-200 overflow-hidden">
        {/* 顶栏 */}
        <header className="px-4 py-3 border-b border-gray-200 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-2 hover:bg-gray-100 rounded-lg"
              title="打开对话列表"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-xl flex items-center justify-center shadow flex-shrink-0">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="font-bold text-gray-900 truncate">
                {activeConversation?.title || '智能协作中心'}
              </h1>
              <p className="text-xs text-gray-500 truncate">@Agent / @Team / @Workflow 自动路由执行</p>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-2 text-xs flex-shrink-0">
            <span className="px-2.5 py-1 bg-purple-100 text-purple-700 rounded-full">{agents.length} Agents</span>
            <span className="px-2.5 py-1 bg-emerald-100 text-emerald-700 rounded-full">{teams.length} Teams</span>
            <span className="px-2.5 py-1 bg-blue-100 text-blue-700 rounded-full">{workflows.length} Workflows</span>
          </div>
        </header>

        {/* 消息区 */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
          {noResources ? (
            <Empty
              icon={Sparkles}
              title="暂无可用资源"
              description="请先创建 Agent、Team 或 Workflow 后再开始对话"
              actionLabel="前往创建 Agent"
              onAction={() => navigate('/agents')}
            />
          ) : messages.length === 0 && !messagesLoading ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-purple-600 to-indigo-700 rounded-2xl shadow-xl mb-5">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">欢迎使用智能协作</h2>
              <p className="text-gray-500 max-w-md mx-auto mb-7">
                输入需求并用 @ 提及 Agent、Team 或 Workflow，系统将自动路由并执行任务。
              </p>
              <div className="w-full max-w-2xl space-y-2.5">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => { setInputText(ex.text); inputRef.current?.focus() }}
                    className="w-full p-3.5 bg-white border border-gray-200 rounded-xl hover:shadow-md hover:border-purple-200 transition-all text-left"
                  >
                    <p className="text-sm text-gray-700">
                      <span className={`font-medium ${ex.color}`}>{ex.text.split(' ')[0]}</span>
                      {ex.text.substring(ex.text.indexOf(' '))}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messagesLoading && (
                <div className="flex items-center justify-center py-8 text-gray-400 text-sm">
                  <RefreshCw className="w-4 h-4 animate-spin mr-2" /> 加载消息中…
                </div>
              )}
              {messages.map((msg, idx) => (
                <MessageBubble key={idx} msg={msg} />
              ))}
              {sending && (
                <div className="flex items-center gap-2 text-gray-500 pl-2">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span className="text-sm">处理中…</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* 会话记忆面板 */}
        {activeConversationId && (
          <div className="border-t border-gray-100 bg-amber-50/40 px-3 py-2">
            <button
              onClick={() => setMemOpen(!memOpen)}
              className="flex items-center gap-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Brain className="w-3.5 h-3.5 text-amber-500" />
              会话记忆
              <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-semibold">{memories.length}</span>
              <ChevronDown className={`w-3 h-3 transition-transform ${memOpen ? 'rotate-180' : ''}`} />
            </button>
            {memOpen && (
              <div className="mt-2 space-y-2">
                {memories.length === 0 ? (
                  <p className="text-xs text-gray-400">暂无记忆。记录用户偏好、关键决定，后续对话可直接引用。</p>
                ) : (
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {memories.map((m) => (
                      <div key={m.id} className="flex items-start gap-2 text-xs bg-white rounded-lg border border-amber-100 px-2.5 py-1.5">
                        <span className="text-gray-600 flex-1">{m.content}</span>
                        <button onClick={() => deleteMemory(m.id)} className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0" title="删除记忆">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <input
                    value={memInput}
                    onChange={(e) => setMemInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addMemory()}
                    placeholder="记一条要点，如：用户偏好简洁风格的回答…"
                    className="flex-1 px-3 py-1.5 rounded-lg border border-amber-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                  />
                  <Button size="sm" onClick={addMemory} disabled={memBusy || !memInput.trim()}>
                    保存记忆
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 输入区 */}
        <div className="border-t border-gray-200 bg-white p-3 md:p-4">
          <div className="relative">
            {showSuggestions && hasSuggestions && (
              <div className="absolute bottom-full left-0 mb-2 bg-white border border-gray-200 rounded-xl shadow-lg max-h-64 overflow-y-auto z-10 w-72">
                <MentionGroup label="Agents" icon={BotIcon} color="text-purple-500" items={filteredAgents} onPick={insertMention} />
                <MentionGroup label="Teams" icon={Users} color="text-emerald-500" items={filteredTeams} onPick={insertMention} />
                <MentionGroup label="Workflows" icon={Layers} color="text-blue-500" items={filteredWorkflows} onPick={insertMention} />
              </div>
            )}
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入需求，用 @ 提及 Agent/Team/Workflow…（回车发送，Shift+回车换行）"
                className="flex-1 p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none resize-none min-h-[48px] max-h-[140px] text-sm"
                rows={1}
              />
              <Button
                variant="gradient"
                icon={Send}
                onClick={handleSend}
                loading={sending}
                disabled={!inputText.trim()}
                className="flex-shrink-0"
              >
                <span className="hidden sm:inline">发送</span>
              </Button>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            提示：输入 @ 可快速选择目标，支持同时 @ 多个目标并行执行。对话自动保存。
          </p>
        </div>
      </section>

      {/* 删除会话确认 */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConversation}
        title="确认删除对话"
        message={
          <>
            确定要删除对话「<span className="font-medium text-gray-700">{deleteTarget?.title || '未命名对话'}</span>」吗？此操作不可撤销。
          </>
        }
        confirmLabel="确认删除"
        loading={deleting}
      />
    </div>
  )
}

// @mention 分组
function MentionGroup({ label, icon: Icon, color, items, onPick }) {
  if (!items || items.length === 0) return null
  return (
    <>
      <div className="px-3 py-1.5 border-b border-gray-100 bg-gray-50">
        <span className="text-xs font-medium text-gray-500 flex items-center gap-1">
          <Icon className={`w-3 h-3 ${color}`} />
          {label}
        </span>
      </div>
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => onPick(item.name)}
          className="w-full text-left px-3 py-1.5 hover:bg-purple-50 text-sm text-gray-700 flex items-center gap-2"
        >
          <Icon className={`w-3.5 h-3.5 ${color} flex-shrink-0`} />
          <span className="truncate">{item.name}</span>
        </button>
      ))}
    </>
  )
}

// 消息气泡
function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  const isError = msg.role === 'error'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex items-start gap-2 max-w-[85%] md:max-w-2xl ${isUser ? 'flex-row-reverse' : ''}`}>
        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isUser
            ? 'bg-gradient-to-br from-purple-600 to-indigo-600'
            : isError
              ? 'bg-red-500'
              : 'bg-gradient-to-br from-indigo-500 to-purple-500'
        }`}>
          {isUser ? <User className="w-4 h-4 text-white" /> : <BotIcon className="w-4 h-4 text-white" />}
        </div>
        <div className={`rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white'
            : isError
              ? 'bg-red-50 text-red-700 border border-red-200'
              : 'bg-white border border-gray-200 text-gray-900'
        }`}>
          {msg.targets && msg.targets.length > 0 && (
            <div className={`flex items-center flex-wrap gap-1 mb-2 text-xs ${isUser ? 'text-white/80' : 'text-gray-500'}`}>
              <ArrowRight className="w-3 h-3" />
              {msg.targets.map((t, i) => {
                const meta = targetMeta(t.type)
                return (
                  <span key={i} className={`px-2 py-0.5 rounded-full ${isUser ? 'bg-white/20 text-white' : meta.chip}`}>
                    {t.name}
                  </span>
                )
              })}
            </div>
          )}
          <div className={`text-sm leading-relaxed ${isUser || isError ? 'whitespace-pre-wrap' : ''}`}>
            {isUser || isError ? msg.content : <MarkdownRenderer content={msg.content} />}
          </div>
          <p className={`text-xs mt-1.5 ${isUser ? 'text-white/60' : 'text-gray-400'}`}>
            {formatRelativeTime(msg.timestamp)}
          </p>
        </div>
      </div>
    </div>
  )
}
