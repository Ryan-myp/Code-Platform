import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Bot,
  Send,
  Square,
  Plus,
  Trash2,
  ArrowLeft,
  Sparkles,
  Database,
  Wrench,
  FileText,
  Menu,
  Cpu,
  MessageSquare,
  RefreshCw,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { api } from '../lib/api'
import { fetchSSE } from '../lib/sse'
import { useToast } from '../lib/toast'
import { formatRelativeTime, formatDateTime } from '../lib/format'
import { Button, Empty, PageLoading, ErrorState, ConfirmDialog } from '../components/ui'

/** 安全解析 JSON 字段 */
function safeParseArray(val) {
  if (Array.isArray(val)) return val
  if (typeof val === 'string') {
    try {
      const p = JSON.parse(val)
      return Array.isArray(p) ? p : []
    } catch {
      return []
    }
  }
  return []
}

export default function AgentExecutePage() {
  // 路由 /agents/:id 通过 useParams 获取，兼容旧 agentId 命名
  const { id } = useParams()
  const agentId = id
  const navigate = useNavigate()
  const toast = useToast()

  const [agent, setAgent] = useState(null)
  const [sessions, setSessions] = useState([])
  const [currentSession, setCurrentSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loadingAgent, setLoadingAgent] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [showSessionsMobile, setShowSessionsMobile] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const abortRef = useRef(null)

  // 加载 Agent 信息
  const loadAgent = useCallback(async () => {
    if (!agentId) return
    setLoadingAgent(true)
    setError(null)
    try {
      const res = await api.get('/api/agents')
      const found = res.data.find((a) => a.id === agentId)
      if (!found) {
        setError(new Error('Agent 不存在或已删除'))
        return
      }
      setAgent(found)
      const sres = await api.get('/api/sessions', { params: { agent_id: agentId } })
      setSessions(sres.data)
    } catch (e) {
      setError(e)
    } finally {
      setLoadingAgent(false)
    }
  }, [agentId])

  useEffect(() => {
    loadAgent()
  }, [loadAgent])

  // 刷新会话列表
  const loadSessions = useCallback(async () => {
    if (!agentId) return
    try {
      const res = await api.get('/api/sessions', { params: { agent_id: agentId } })
      setSessions(res.data)
    } catch {
      // 静默，列表刷新失败不打扰
    }
  }, [agentId])

  // 创建新会话
  const createSession = async () => {
    if (!agentId) return
    const title = `新对话 ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
    try {
      const res = await api.post('/api/sessions', { agent_id: agentId, title })
      const newSession = {
        id: res.data.session_id,
        agent_id: agentId,
        title: res.data.title || title,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      setCurrentSession(newSession)
      setMessages([])
      setShowSessionsMobile(false)
      loadSessions()
      inputRef.current?.focus()
    } catch (e) {
      toast.error(`创建会话失败：${e.message}`)
    }
  }

  // 选择会话并加载消息
  const selectSession = async (session) => {
    setCurrentSession(session)
    setShowSessionsMobile(false)
    setLoadingMessages(true)
    try {
      const res = await api.get(`/api/sessions/${session.id}/messages`)
      setMessages(res.data)
    } catch (e) {
      toast.error(`加载消息失败：${e.message}`)
      setMessages([])
    } finally {
      setLoadingMessages(false)
    }
  }

  // v12.0 单 Agent SSE 流式执行：打字机增量 + 可中断（assistant 由后端自动落库）
  const streamToAgent = (text, sessionId) => {
    // 更新最后一条流式消息（防并发覆盖：函数式更新）
    const patchStream = (updater) => {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (!last || !last.streaming) return prev
        next[next.length - 1] = { ...last, ...updater(last) }
        return next
      })
    }
    abortRef.current = fetchSSE(`/api/agents/${agentId}/run/stream`, {
      body: { message: text, session_id: sessionId },
      onEvent: (event, data) => {
        if (event === 'delta') {
          patchStream((last) => ({ content: last.content + data.text }))
        } else if (event === 'done') {
          patchStream((last) => ({ content: data.full || last.content, streaming: false }))
        } else if (event === 'error') {
          patchStream((last) => ({
            streaming: false,
            error: true,
            content: last.content || `> ⚠️ 回复失败：${data.detail || '未知错误'}`,
          }))
        }
      },
      onError: (err) => {
        // 已有部分内容则保留并追加提示，否则整条展示错误
        patchStream((last) => ({
          streaming: false,
          error: true,
          content: last.content
            ? `${last.content}\n\n> ⚠️ ${err.message}`
            : `> ⚠️ 回复失败：${err.message}`,
        }))
      },
      onClose: () => {
        abortRef.current = null
        setSending(false)
      },
    })
  }

  // 发送消息（回车触发）— v12.0 流式：SSE 打字机增量渲染 + 可中断
  const sendMessage = async () => {
    const text = input.trim()
    if (!text || !currentSession || sending) return

    const userMessage = {
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setSending(true)

    // 占位 assistant 气泡：流式增量写入该消息
    const assistantMsg = {
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      streaming: true,
    }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      // 持久化用户消息（失败不阻塞流式）
      try {
        await api.post(`/api/sessions/${currentSession.id}/messages`, {
          role: 'user',
          content: text,
        })
      } catch {
        /* 忽略持久化失败 */
      }
      streamToAgent(text, currentSession.id)
    } catch (e) {
      // 兜底：恢复可发送状态并展示错误
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last?.streaming) {
          next[next.length - 1] = {
            ...last,
            streaming: false,
            error: true,
            content: last.content || `> ⚠️ 回复失败：${e.message}`,
          }
        }
        return next
      })
      setSending(false)
    }
  }

  // 错误重试：恢复失败消息为流式占位，重新生成
  const handleRetry = (msgIdx) => {
    if (sending || !currentSession) return
    let userIdx = -1
    for (let i = msgIdx - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userIdx = i
        break
      }
    }
    if (userIdx < 0) return
    const userMsg = messages[userIdx]
    // 恢复为流式占位（不清空已生成的部分内容），重新发起
    setMessages((prev) => {
      const next = [...prev]
      next[msgIdx] = { ...next[msgIdx], content: '', error: false, streaming: true }
      return next
    })
    setSending(true)
    streamToAgent(userMsg.content, currentSession.id)
  }

  // 停止生成：中断 SSE 流，保留已生成内容
  const handleStop = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last?.streaming) next[next.length - 1] = { ...last, streaming: false }
      return next
    })
    setSending(false)
  }

  // 删除会话
  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.delete(`/api/sessions/${deleteTarget.id}`)
      toast.success('会话已删除')
      if (currentSession?.id === deleteTarget.id) {
        setCurrentSession(null)
        setMessages([])
      }
      setDeleteTarget(null)
      loadSessions()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    } finally {
      setDeleting(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // 新消息到达时滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  if (loadingAgent) return <PageLoading label="加载 Agent…" />
  if (error) return <ErrorState message={`加载失败：${error.message}`} onRetry={loadAgent} />
  if (!agent) return <ErrorState message="Agent 不存在" />

  const tools = safeParseArray(agent.tools)
  const knowledgeBases = safeParseArray(agent.knowledge_base_ids)
  const skills = safeParseArray(agent.skill_ids)

  return (
    <div className="relative flex h-[calc(100vh-2rem)] md:h-[calc(100vh-3rem)] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      {/* 移动端遮罩 */}
      {showSessionsMobile && (
        <div
          className="absolute inset-0 bg-black/30 z-20 md:hidden"
          onClick={() => setShowSessionsMobile(false)}
        />
      )}

      {/* 左侧会话列表 */}
      <aside
        className={`absolute md:relative z-30 w-72 md:w-64 h-full bg-white border-r border-gray-200 flex flex-col transform transition-transform duration-200 md:translate-x-0 ${
          showSessionsMobile ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-4 border-b border-gray-200">
          <button
            onClick={() => navigate('/agents')}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-3 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>返回 Agent 列表</span>
          </button>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white flex-shrink-0">
              <Bot className="w-5 h-5" />
            </div>
            <h2 className="font-semibold text-gray-900 truncate">{agent.name}</h2>
          </div>
          {agent.description && (
            <p className="text-xs text-gray-500 line-clamp-2">{agent.description}</p>
          )}
        </div>

        <div className="p-3 border-b border-gray-200">
          <Button variant="primary" icon={Plus} className="w-full" onClick={createSession}>
            新对话
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 ? (
            <div className="px-4 py-8">
              <Empty
                icon={MessageSquare}
                title="暂无对话"
                description="点击上方按钮开始第一次对话"
              />
            </div>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => selectSession(session)}
                className={`group w-full text-left p-3 border-b border-gray-100 transition-colors ${
                  currentSession?.id === session.id
                    ? 'bg-purple-50 border-l-2 border-l-purple-600'
                    : 'hover:bg-gray-50'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {session.title || '未命名会话'}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {formatRelativeTime(session.updated_at || session.created_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setDeleteTarget(session)
                    }}
                    className="p-1 text-gray-300 hover:text-red-500 rounded transition-colors flex-shrink-0"
                    title="删除会话"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* 中间对话区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 移动端顶栏 */}
        <div className="md:hidden flex items-center gap-2 p-3 border-b border-gray-200">
          <button
            onClick={() => setShowSessionsMobile(true)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="会话列表"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h2 className="font-semibold text-gray-900 truncate">{agent.name}</h2>
        </div>

        {currentSession ? (
          <>
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-gray-50">
              {loadingMessages ? (
                <div className="flex items-center justify-center h-32">
                  <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : messages.length === 0 ? (
                <Empty
                  icon={Bot}
                  title="开始对话"
                  description={`向 ${agent.name} 提问吧`}
                  className="py-20"
                />
              ) : (
                <div className="space-y-4 max-w-3xl mx-auto">
                  {messages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] md:max-w-[75%] px-4 py-3 rounded-2xl ${
                          msg.role === 'user'
                            ? 'bg-purple-600 text-white rounded-br-sm'
                            : msg.error
                              ? 'bg-red-50 border border-red-200 text-red-700 rounded-bl-sm'
                              : 'bg-white border border-gray-200 text-gray-900 rounded-bl-sm'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          {msg.role === 'assistant' && (
                            <Bot className="w-4 h-4 flex-shrink-0 text-purple-500" />
                          )}
                          <span className="text-xs opacity-70">
                            {msg.role === 'user' ? '你' : agent.name}
                          </span>
                          <span className="text-xs opacity-50 ml-auto">
                            {formatDateTime(msg.created_at).slice(11)}
                          </span>
                        </div>
                        {msg.role === 'assistant' ? (
                          <div>
                            {msg.content ? (
                              <MarkdownRenderer content={msg.content} />
                            ) : (
                              msg.streaming && (
                                <span className="text-sm text-gray-400">正在思考…</span>
                              )
                            )}
                            {msg.streaming && (
                              <span className="inline-block w-0.5 h-4 bg-purple-500/70 animate-pulse ml-0.5 align-middle" />
                            )}
                          </div>
                        ) : (
                          <p className="text-sm whitespace-pre-wrap break-words">{msg.content}</p>
                        )}
                        {msg.error && (
                          <button
                            onClick={() => handleRetry(idx)}
                            className="mt-2 inline-flex items-center gap-1 px-2.5 py-1 bg-red-50 border border-red-200 text-red-600 text-xs font-medium rounded-lg hover:bg-red-100 transition-colors"
                          >
                            <RefreshCw className="w-3 h-3" /> 重试
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* 输入区域 */}
            <div className="p-3 md:p-4 bg-white border-t border-gray-200">
              <div className="flex items-end gap-2 max-w-3xl mx-auto">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`给 ${agent.name} 发消息…（Enter 发送，Shift+Enter 换行）`}
                  rows={1}
                  className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all resize-none max-h-32 overflow-y-auto text-sm"
                />
                {sending ? (
                  <Button variant="danger" icon={Square} onClick={handleStop}>
                    <span className="hidden sm:inline">停止</span>
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    icon={Send}
                    onClick={sendMessage}
                    disabled={!input.trim() || !currentSession}
                  >
                    <span className="hidden sm:inline">发送</span>
                  </Button>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-gray-50">
            <Empty
              icon={MessageSquare}
              title="选择或创建一个会话"
              description="从左侧选择已有对话，或创建新对话开始交流"
              actionLabel="开始新对话"
              onAction={createSession}
            />
          </div>
        )}
      </div>

      {/* 右侧 Agent 详情面板 */}
      <aside className="hidden lg:flex w-72 bg-white border-l border-gray-200 flex-col">
        <div className="p-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-500" />
            Agent 详情
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-gray-500">模型</span>
              <span className="text-gray-900 ml-auto font-medium">
                {agent.model || 'agnes-2.5-flash'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Wrench className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-gray-500">工具</span>
              <span className="text-gray-900 ml-auto font-medium">{tools.length} 个</span>
            </div>
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-gray-500">知识库</span>
              <span className="text-gray-900 ml-auto font-medium">{knowledgeBases.length} 个</span>
            </div>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-gray-500">技能</span>
              <span className="text-gray-900 ml-auto font-medium">{skills.length} 个</span>
            </div>
          </div>

          {(tools.length > 0 || knowledgeBases.length > 0 || skills.length > 0) && (
            <div className="pt-4 border-t border-gray-100 space-y-3">
              {tools.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-1.5">已绑定工具</p>
                  <div className="flex flex-wrap gap-1.5">
                    {tools.slice(0, 8).map((t, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded"
                      >
                        {typeof t === 'string' ? t : t?.name || t?.id || '工具'}
                      </span>
                    ))}
                    {tools.length > 8 && (
                      <span className="px-2 py-0.5 text-xs text-gray-400">+{tools.length - 8}</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* 删除会话确认 */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除会话"
        message={
          <>
            确定要删除会话「
            <span className="font-medium text-gray-700">{deleteTarget?.title}</span>
            」吗？该会话的所有消息将一并删除，此操作不可撤销。
          </>
        }
        confirmLabel="删除"
        loading={deleting}
      />
    </div>
  )
}
