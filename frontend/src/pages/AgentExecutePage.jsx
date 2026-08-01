import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { Bot, Send, Plus, Trash2, ArrowLeft, Loader, Sparkles, Database, Wrench, ChevronRight, FolderOpen, FileText, Code2, Terminal, Play, Pause, RotateCw } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

export default function AgentExecutePage({ agentId, onBack }) {
  const [agent, setAgent] = useState(null)
  const [sessions, setSessions] = useState([])
  const [currentSession, setCurrentSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [showToolLog, setShowToolLog] = useState(false)
  const [toolLog, setToolLog] = useState([])
  const messagesEndRef = useRef(null)

  // 加载 Agent 信息
  useEffect(() => {
    if (!agentId) return
    const token = localStorage.getItem('token')
    axios.get(`${API_BASE}/api/agents`, {
      headers: { Authorization: `Bearer ${token}` }
    }).then(res => {
      const found = res.data.find(a => a.id === agentId)
      setAgent(found)
      loadSessions(found?.id)
    })
  }, [agentId])

  // 加载会话列表
  const loadSessions = async (agentId) => {
    if (!agentId) return
    const token = localStorage.getItem('token')
    try {
      const res = await axios.get(`${API_BASE}/api/sessions?agent_id=${agentId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setSessions(res.data)
    } catch (e) {
      console.error('加载会话失败', e)
    }
  }

  // 创建新会话
  const createSession = async () => {
    const token = localStorage.getItem('token')
    try {
      const res = await axios.post(`${API_BASE}/api/sessions`, {
        agent_id: agentId,
        title: `新对话 ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const newSession = { id: res.data.session_id, title: res.data.title, created_at: new Date().toISOString() }
      setCurrentSession(newSession)
      setMessages([])
      loadSessions(agentId)
    } catch (e) {
      console.error('创建会话失败', e)
    }
  }

  // 选择会话
  const selectSession = async (session) => {
    setCurrentSession(session)
    setLoading(true)
    const token = localStorage.getItem('token')
    try {
      const res = await axios.get(`${API_BASE}/api/sessions/${session.id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setMessages(res.data)
    } catch (e) {
      console.error('加载消息失败', e)
    } finally {
      setLoading(false)
    }
  }

  // 发送消息
  const sendMessage = async () => {
    if (!input.trim() || !currentSession) return
    
    const userMessage = { role: 'user', content: input, created_at: new Date().toISOString() }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setSending(true)
    setToolLog([])

    const token = localStorage.getItem('token')
    
    try {
      // 保存用户消息
      await axios.post(`${API_BASE}/api/sessions/${currentSession.id}/messages`, {
        role: 'user',
        content: input
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })

      // 模拟工具调用日志
      setToolLog(prev => [...prev, { time: new Date().toLocaleTimeString(), tool: 'web_search', status: 'calling', result: '' }])
      
      await new Promise(r => setTimeout(r, 800))
      setToolLog(prev => [...prev.slice(0, -1), { time: new Date().toLocaleTimeString(), tool: 'web_search', status: 'success', result: '找到 3 条相关结果' }])
      
      setToolLog(prev => [...prev, { time: new Date().toLocaleTimeString(), tool: 'code_execution', status: 'calling', result: '' }])
      await new Promise(r => setTimeout(r, 1000))
      setToolLog(prev => [...prev.slice(0, -1), { time: new Date().toLocaleTimeString(), tool: 'code_execution', status: 'success', result: '输出：Hello World' }])

      // 模拟 Agent 回复
      await new Promise(r => setTimeout(r, 500))
      
      const assistantMessage = {
        role: 'assistant',
        content: `这是 ${agent?.name || 'Agent'} 的回复。\n\n我正在处理你的请求，已调用相关工具和知识库。`,
        created_at: new Date().toISOString()
      }
      
      setMessages(prev => [...prev, assistantMessage])
      
      await axios.post(`${API_BASE}/api/sessions/${currentSession.id}/messages`, {
        role: 'assistant',
        content: assistantMessage.content
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      
    } catch (e) {
      console.error('发送消息失败', e)
    } finally {
      setSending(false)
    }
  }

  // 删除会话
  const deleteSession = async (sessionId, e) => {
    e.stopPropagation()
    if (!confirm('确定删除此会话？')) return
    
    const token = localStorage.getItem('token')
    await axios.delete(`${API_BASE}/api/sessions/${sessionId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (currentSession?.id === sessionId) {
      setCurrentSession(null)
      setMessages([])
    }
    loadSessions(agentId)
  }

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, toolLog])

  if (!agent) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="animate-spin w-8 h-8 text-purple-600" />
      </div>
    )
  }

  const tools = typeof agent.tools === 'string' ? JSON.parse(agent.tools) : (agent.tools || [])
  const knowledgeBases = typeof agent.knowledge_base_ids === 'string' ? JSON.parse(agent.knowledge_base_ids) : (agent.knowledge_base_ids || [])
  const skills = typeof agent.skill_ids === 'string' ? JSON.parse(agent.skill_ids) : (agent.skill_ids || [])

  return (
    <div className="flex h-full bg-gray-50">
      {/* 左侧会话列表 */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <button onClick={onBack} className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-3">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">返回</span>
          </button>
          <div className="flex items-center gap-2 mb-2">
            <Bot className="w-5 h-5 text-purple-600" />
            <h2 className="font-semibold text-gray-900 truncate">{agent.name}</h2>
          </div>
          <p className="text-xs text-gray-500 line-clamp-2">{agent.description || '智能助手'}</p>
        </div>
        
        <div className="p-3 border-b border-gray-200">
          <button
            onClick={createSession}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span className="text-sm">新对话</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sessions.map(session => (
            <div
              key={session.id}
              onClick={() => selectSession(session)}
              className={`p-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 ${currentSession?.id === session.id ? 'bg-purple-50 border-l-2 border-l-purple-600' : ''}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{session.title}</p>
                  <p className="text-xs text-gray-500">{new Date(session.created_at).toLocaleString('zh-CN')}</p>
                </div>
                <button
                  onClick={(e) => deleteSession(session.id, e)}
                  className="p-1 text-gray-400 hover:text-red-500"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
          {sessions.length === 0 && (
            <div className="p-4 text-center text-gray-400 text-sm">
              暂无对话
            </div>
          )}
        </div>
      </div>

      {/* 中间对话区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {currentSession ? (
          <>
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto p-6">
              {loading ? (
                <div className="flex items-center justify-center h-32">
                  <Loader className="animate-spin w-6 h-6 text-purple-600" />
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                  <Bot className="w-16 h-16 mb-4 opacity-50" />
                  <p className="text-lg font-medium">开始对话</p>
                  <p className="text-sm mt-1">向 {agent.name} 提问吧</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-2xl px-4 py-3 rounded-2xl ${
                        msg.role === 'user'
                          ? 'bg-purple-600 text-white'
                          : 'bg-white border border-gray-200 text-gray-900'
                      }`}>
                        <div className="flex items-center gap-2 mb-1">
                          {msg.role === 'assistant' && <Bot className="w-4 h-4" />}
                          <span className="text-xs opacity-75">{msg.role === 'user' ? '你' : agent.name}</span>
                          <span className="text-xs opacity-50 ml-auto">{new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    </div>
                  ))}
                  {sending && (
                    <div className="flex justify-start">
                      <div className="bg-white border border-gray-200 px-4 py-3 rounded-2xl">
                        <div className="flex items-center gap-2">
                          <Loader className="animate-spin w-4 h-4 text-purple-600" />
                          <span className="text-sm text-gray-500">{agent.name} 正在思考...</span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* 输入区域 */}
            <div className="p-4 bg-white border-t border-gray-200">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder={`给 ${agent.name} 发消息...`}
                  className="flex-1 px-4 py-2 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <button
                  onClick={sendMessage}
                  disabled={sending || !input.trim()}
                  className="px-4 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <Bot className="w-20 h-20 mx-auto mb-4 opacity-30" />
              <p className="text-lg">选择或创建一个会话</p>
              <button
                onClick={createSession}
                className="mt-4 px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
              >
                开始新对话
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 右侧工具日志 */}
      <div className="w-72 bg-white border-l border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">执行详情</h3>
            <button
              onClick={() => setShowToolLog(!showToolLog)}
              className="text-xs text-purple-600 hover:text-purple-700"
            >
              {showToolLog ? '收起' : '展开'}
            </button>
          </div>
        </div>

        {/* Agent 信息 */}
        <div className="p-4 border-b border-gray-200">
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">模型:</span>
              <span className="text-gray-900">{agent.model || 'agnes-2.5-flash'}</span>
            </div>
            {tools.length > 0 && (
              <div className="flex items-center gap-2">
                <Wrench className="w-4 h-4 text-gray-400" />
                <span className="text-gray-600">工具:</span>
                <span className="text-gray-900">{tools.length} 个</span>
              </div>
            )}
            {knowledgeBases.length > 0 && (
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-gray-400" />
                <span className="text-gray-600">知识库:</span>
                <span className="text-gray-900">{knowledgeBases.length} 个</span>
              </div>
            )}
            {skills.length > 0 && (
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-gray-400" />
                <span className="text-gray-600">技能:</span>
                <span className="text-gray-900">{skills.length} 个</span>
              </div>
            )}
          </div>
        </div>

        {/* 工具调用日志 */}
        {showToolLog && (
          <div className="flex-1 overflow-y-auto p-4">
            {toolLog.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">暂无执行记录</p>
            ) : (
              <div className="space-y-2">
                {toolLog.map((log, idx) => (
                  <div key={idx} className="p-2 bg-gray-50 rounded-lg text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-gray-700">{log.tool}</span>
                      <span className="text-gray-400">{log.time}</span>
                    </div>
                    <div className={`flex items-center gap-1 ${
                      log.status === 'calling' ? 'text-blue-600' : 'text-green-600'
                    }`}>
                      {log.status === 'calling' ? (
                        <Loader className="w-3 h-3 animate-spin" />
                      ) : (
                        <span className="w-3 h-3">✓</span>
                      )}
                      <span>{log.status === 'calling' ? '调用中...' : log.result}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
