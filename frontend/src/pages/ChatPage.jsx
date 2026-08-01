import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { Bot, MessageSquare, Send, Loader2, Users, Layers, ChevronDown, ChevronRight, Menu, X, Brain, Database, Wrench, Server, ListTodo, FolderKanban, Puzzle, ArrowRight, Sparkles, Hash, User, Plus, Edit2, Trash2, Save, Search, BookOpen, FolderOpen, Image as ImageIcon, Play, MessageCirclePlus, MessageCircleMore, Clock, Bot as BotIcon, UserCircle } from 'lucide-react'

const API = 'http://localhost:8888'

export default function ChatPage() {
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [agents, setAgents] = useState([])
  const [teams, setTeams] = useState([])
  const [workflows, setWorkflows] = useState([])
  const [showTargetPicker, setShowTargetPicker] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)
  const messagesEndRef = useRef(null)

  // Load all targets on mount
  useEffect(() => {
    Promise.all([
      axios.get(`${API}/api/agents`).catch(() => ({ data: [] })),
      axios.get(`${API}/api/teams`).catch(() => ({ data: [] })),
      axios.get(`${API}/api/workflows`).catch(() => ({ data: [] })),
    ]).then(([agentsRes, teamsRes, workflowsRes]) => {
      setAgents(agentsRes.data || [])
      setTeams(teamsRes.data || [])
      setWorkflows(workflowsRes.data || [])
    })
  }, [])

  // Load conversations list
  const loadConversations = async () => {
    try {
      const res = await axios.get(`${API}/api/agents`)
      if (res.data.length > 0) {
        // Get conversations for the first agent (or create a new one)
        const agentId = res.data[0].id
        const convRes = await axios.get(`${API}/api/agents/${agentId}/conversations`)
        setConversations(convRes.data || [])
      }
    } catch (err) {
      console.error('Failed to load conversations:', err)
    }
  }

  useEffect(() => { loadConversations() }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Parse @mentions from input text
  const parseMentions = (text) => {
    const mentions = text.match(/@(\S+)/g) || []
    return mentions.map(m => m.substring(1))
  }

  // Match mentioned names to actual agents/teams/workflows
  const resolveTargets = (mentionNames) => {
    const resolved = []
    mentionNames.forEach(name => {
      const agent = agents.find(a => a.name.toLowerCase().includes(name.toLowerCase()))
      if (agent) { resolved.push({ type: 'agent', ...agent }); return }
      const team = teams.find(t => t.name.toLowerCase().includes(name.toLowerCase()))
      if (team) { resolved.push({ type: 'team', ...team }); return }
      const workflow = workflows.find(w => w.name.toLowerCase().includes(name.toLowerCase()))
      if (workflow) { resolved.push({ type: 'workflow', ...workflow }); return }
    })
    return resolved
  }

  // Create a new conversation and send message
  const handleSend = async () => {
    if (!inputText.trim()) return
    
    const userMessageContent = inputText.trim()
    const mentionNames = parseMentions(userMessageContent)
    const targets = resolveTargets(mentionNames)
    
    // Add user message to chat display immediately
    const userMessage = {
      role: 'user',
      content: userMessageContent,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMessage])
    setInputText('') // Clear input field
    
    setLoading(true)
    setShowTargetPicker(false)

    try {
      let result
      
      // Find an agent to use for conversation
      const agentId = agents[0]?.id || null
      
      if (targets.length === 0) {
        // No mentions → send to default agent
        if (agentId) {
          // If no active conversation, create one
          let convId = activeConversationId
          if (!convId && agentId) {
            try {
              const convRes = await axios.post(`${API}/api/agents/${agentId}/conversations`, {})
              convId = convRes.data.id
              setActiveConversationId(convId)
              loadConversations()
            } catch (e) { console.error(e) }
          }
          
          // Save user message to backend
          if (convId) {
            await axios.post(`${API}/api/conversations/${convId}/messages`, {
              role: 'user',
              content: userMessageContent
            })
          }
          
          // Run agent with conversation history
          const res = await axios.post(`${API}/api/agents/${agentId}/run`, {
            message: userMessageContent,
            conversation_id: convId
          })
          result = res.data.result || res.data
        } else {
          result = { status: 'error', detail: 'No agents configured.' }
        }
      } else if (targets.length === 1) {
        const target = targets[0]
        if (target.type === 'agent') {
          let convId = activeConversationId
          if (!convId) {
            try {
              const convRes = await axios.post(`${API}/api/agents/${target.id}/conversations`, {})
              convId = convRes.data.id
              setActiveConversationId(convId)
              loadConversations()
            } catch (e) {}
          }
          if (convId) {
            await axios.post(`${API}/api/conversations/${convId}/messages`, {
              role: 'user',
              content: userMessageContent
            })
          }
          const res = await axios.post(`${API}/api/agents/${target.id}/run`, {
            message: userMessageContent,
            conversation_id: convId
          })
          result = res.data.result || res.data
        } else if (target.type === 'team') {
          const res = await axios.post(`${API}/api/teams/${target.id}/run`, {
            message: userMessageContent
          })
          result = res.data.result || res.data
        } else if (target.type === 'workflow') {
          const res = await axios.post(`${API}/api/workflows/${target.id}/run`, {
            message: userMessageContent
          })
          result = res.data.result || res.data
        }
      } else {
        // Multiple mentions → route each separately and aggregate results
        const results = []
        for (const target of targets) {
          try {
            let res
            if (target.type === 'agent') {
              res = await axios.post(`${API}/api/agents/${target.id}/run`, { message: userMessageContent })
            } else if (target.type === 'team') {
              res = await axios.post(`${API}/api/teams/${target.id}/run`, { message: userMessageContent })
            } else {
              res = await axios.post(`${API}/api/workflows/${target.id}/run`, { message: userMessageContent })
            }
            results.push({
              target_name: target.name,
              target_type: target.type,
              result: res.data.result || res.data
            })
          } catch (err) {
            results.push({
              target_name: target.name,
              target_type: target.type,
              error: err.response?.data?.detail || err.message
            })
          }
        }
        result = { aggregated: true, results }
      }

      const assistantMessage = {
        role: 'assistant',
        content: typeof result === 'string' ? result : JSON.stringify(result, null, 2),
        timestamp: new Date().toISOString(),
        targets: targets,
      }
      
      // Save assistant message to backend if we have a conversation
      if (activeConversationId) {
        try {
          await axios.post(`${API}/api/conversations/${activeConversationId}/messages`, {
            role: 'assistant',
            content: assistantMessage.content
          })
        } catch (e) { /* ignore */ }
      }
      
      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      const errorMessage = {
        role: 'error',
        content: `Error: ${err.response?.data?.detail || err.message}`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  // Load conversation messages
  const loadConversationMessages = async (convId) => {
    try {
      const res = await axios.get(`${API}/api/conversations/${convId}`)
      const msgs = res.data.messages || []
      const formatted = msgs.map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
        timestamp: m.timestamp || new Date().toISOString(),
      }))
      setMessages(formatted)
      setActiveConversationId(convId)
    } catch (err) {
      console.error('Failed to load conversation:', err)
    }
  }

  // Create new conversation
  const handleNewConversation = async () => {
    const agentId = agents[0]?.id
    if (!agentId) return
    try {
      const res = await axios.post(`${API}/api/agents/${agentId}/conversations`, {})
      setActiveConversationId(res.data.id)
      setMessages([])
      loadConversations()
    } catch (err) {
      console.error('Failed to create conversation:', err)
    }
  }

  // Delete conversation
  const handleDeleteConversation = async (convId, e) => {
    e.stopPropagation()
    try {
      await axios.delete(`${API}/api/conversations/${convId}`)
      if (activeConversationId === convId) {
        setActiveConversationId(null)
        setMessages([])
      }
      loadConversations()
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const showSuggestions = inputText.endsWith('@') || /@\w*$/.test(inputText)

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar - Conversations List */}
      <div className={`${showSidebar ? 'w-72' : 'w-0'} transition-all duration-300 bg-white border-r border-gray-200 flex flex-col overflow-hidden`}>
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold text-gray-900 flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-purple-600" />
              对话列表
            </h2>
            <button onClick={handleNewConversation} className="p-1.5 hover:bg-gray-100 rounded-lg" title="新建对话">
              <Plus className="w-4 h-4 text-purple-600" />
            </button>
          </div>
          <div className="relative">
            <Search className="absolute left-2 top-2 w-4 h-4 text-gray-400" />
            <input type="text" placeholder="搜索对话..." className="w-full pl-8 pr-2 py-1.5 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent" />
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              <MessageCirclePlus className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>暂无对话</p>
              <p className="text-xs mt-1">点击 + 创建新对话</p>
            </div>
          ) : (
            conversations.map(conv => (
              <div 
                key={conv.id}
                onClick={() => loadConversationMessages(conv.id)}
                className={`p-3 rounded-lg cursor-pointer group relative ${
                  activeConversationId === conv.id 
                    ? 'bg-purple-50 border border-purple-200' 
                    : 'hover:bg-gray-50 border border-transparent'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{conv.title || '未命名对话'}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Clock className="w-3 h-3 text-gray-400" />
                      <span className="text-xs text-gray-400">
                        {conv.updated_at ? new Date(conv.updated_at).toLocaleDateString() : ''}
                      </span>
                      <span className="text-xs text-gray-400">·</span>
                      <span className="text-xs text-gray-400">{conv.message_count || 0} 条</span>
                    </div>
                  </div>
                  <button 
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded"
                  >
                    <Trash2 className="w-3 h-3 text-red-500" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
        
        <div className="p-3 border-t border-gray-200 text-xs text-gray-400 text-center">
          {conversations.length} 个对话
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => setShowSidebar(!showSidebar)} className="p-2 hover:bg-gray-100 rounded-lg">
              {showSidebar ? <ChevronRight className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
            <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-gray-900">智能协作</h1>
              <p className="text-xs text-gray-500">@Agent/@Team 触发任务，自动路由执行</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full">{agents.length} Agents</span>
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full">{teams.length} Teams</span>
            <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full">{workflows.length} Workflows</span>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-16">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-purple-600 to-indigo-700 rounded-2xl shadow-xl mb-6">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">欢迎使用智能协作</h2>
              <p className="text-gray-500 max-w-md mx-auto mb-8">输入需求并用 @ 提及 Agent、Team 或 Workflow，系统将自动路由并执行任务。</p>
              
              {/* Quick examples */}
              <div className="max-w-2xl mx-auto space-y-3">
                <div className="p-4 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow cursor-pointer" onClick={() => setInputText('@产品经理Agent 帮我写一个电商下单功能的PRD')}>
                  <p className="text-sm text-gray-700"><span className="font-medium text-purple-600">@产品经理Agent</span> 帮我写一个电商下单功能的PRD</p>
                </div>
                <div className="p-4 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow cursor-pointer" onClick={() => setInputText('@代码审查团队 审查这个PRD的质量 @架构师Agent 生成技术方案')}>
                  <p className="text-sm text-gray-700"><span className="font-medium text-green-600">@代码审查团队</span> 审查这个PRD的质量 <span className="font-medium text-purple-600">@架构师Agent</span> 生成技术方案</p>
                </div>
                <div className="p-4 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow cursor-pointer" onClick={() => setInputText('@项目管理员 创建一个新的电商平台项目')}>
                  <p className="text-sm text-gray-700"><span className="font-medium text-blue-600">@项目管理员</span> 创建一个新的电商平台项目</p>
                </div>
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex items-start gap-2 max-w-2xl ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                    {/* Avatar */}
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      msg.role === 'user' ? 'bg-purple-600' : msg.role === 'error' ? 'bg-red-500' : 'bg-indigo-600'
                    }`}>
                      {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <BotIcon className="w-4 h-4 text-white" />}
                    </div>
                    
                    <div className={`rounded-2xl px-4 py-3 ${
                      msg.role === 'user' 
                        ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white' 
                        : msg.role === 'error'
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : 'bg-white border border-gray-200 text-gray-900'
                    }`}>
                      {msg.targets && msg.targets.length > 0 && (
                        <div className="flex items-center gap-1 mb-2 text-xs opacity-75">
                          <ArrowRight className="w-3 h-3" />
                          {msg.targets.map((t, i) => (
                            <span key={i} className={`px-2 py-0.5 rounded-full ${
                              t.type === 'agent' ? 'bg-purple-200 text-purple-700' :
                              t.type === 'team' ? 'bg-green-200 text-green-700' :
                              'bg-blue-200 text-blue-700'
                            }`}>{t.name}</span>
                          ))}
                        </div>
                      )}
                      <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                      <p className="text-xs mt-1 opacity-50">{new Date(msg.timestamp).toLocaleTimeString()}</p>
                    </div>
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="flex items-center gap-2 text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">处理中...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white p-4">
          <div className="max-w-4xl mx-auto relative">
            <div className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入需求，用 @ 提及 Agent/Team/Workflow... (如: @产品经理Agent 写PRD)"
                  className="w-full p-3 pr-12 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none min-h-[48px] max-h-[120px]"
                  rows={1}
                />
                {/* Mention suggestions */}
                {showSuggestions && (
                  <div className="absolute bottom-full left-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10 w-64">
                    <div className="p-2 border-b border-gray-100">
                      <span className="text-xs font-medium text-gray-500">Agents</span>
                    </div>
                    {agents.map(a => (
                      <button key={a.id} className="w-full text-left px-3 py-1.5 hover:bg-gray-50 text-sm" onClick={() => setInputText(prev => prev.replace(/@\w*$/, `@${a.name} `))}>
                        <BotIcon className="w-3 h-3 inline mr-1 text-purple-500" />{a.name}
                      </button>
                    ))}
                    {teams.length > 0 && (
                      <>
                        <div className="p-2 border-t border-b border-gray-100">
                          <span className="text-xs font-medium text-gray-500">Teams</span>
                        </div>
                        {teams.map(t => (
                          <button key={t.id} className="w-full text-left px-3 py-1.5 hover:bg-gray-50 text-sm" onClick={() => setInputText(prev => prev.replace(/@\w*$/, `@${t.name} `))}>
                            <Users className="w-3 h-3 inline mr-1 text-green-500" />{t.name}
                          </button>
                        ))}
                      </>
                    )}
                    {workflows.length > 0 && (
                      <>
                        <div className="p-2 border-t border-b border-gray-100">
                          <span className="text-xs font-medium text-gray-500">Workflows</span>
                        </div>
                        {workflows.map(w => (
                          <button key={w.id} className="w-full text-left px-3 py-1.5 hover:bg-gray-50 text-sm" onClick={() => setInputText(prev => prev.replace(/@\w*$/, `@${w.name} `))}>
                            <Layers className="w-3 h-3 inline mr-1 text-blue-500" />{w.name}
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                )}
              </div>
              <button
                onClick={handleSend}
                disabled={loading || !inputText.trim()}
                className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
              >
                <Send className="w-4 h-4" />
                <span className="hidden sm:inline">发送</span>
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2">提示：输入 @ 可快速选择 Agent、Team 或 Workflow。支持同时 @ 多个目标进行并行执行。对话会自动保存，下次打开可查看历史。</p>
          </div>
        </div>
      </div>
    </div>
  )
}
