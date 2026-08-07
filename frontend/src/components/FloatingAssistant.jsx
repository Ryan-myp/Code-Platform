import React, { useState, useEffect, useRef } from 'react'
import { Bot, X, Send, Trash2, Sparkles } from 'lucide-react'
import MarkdownRenderer from './MarkdownRenderer'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'

const STORAGE_KEY = 'assistant_messages_v1'

// 快捷问题：小白用户点一下即可提问
const QUICK_QUESTIONS = [
  '平台有哪些功能？',
  '如何发布内容到公众号/抖音？',
  '如何生成微信小程序？',
  '如何生成小游戏？',
  '部署失败怎么办？',
]

const WELCOME =
  '你好呀，我是**小团** 🤖 你的平台智能助手！\n\n我可以帮你解答平台使用问题：额度计算、功能入口、内容发布、小程序开发、Agent / 工作流 / 知识库怎么用……\n\n直接输入问题，或点下方快捷问题试试吧～'

export default function FloatingAssistant() {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const listRef = useRef(null)
  const inputRef = useRef(null)

  // 恢复本地会话记录
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
      if (Array.isArray(saved)) setMessages(saved.slice(-50))
    } catch {
      /* 忽略损坏的本地缓存 */
    }
  }, [])

  // 持久化消息
  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-50)))
      } catch {
        /* 存储满时静默忽略 */
      }
    }
  }, [messages])

  // 打开面板时聚焦输入框；新消息自动滚动到底部
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading, open])

  const send = async (text) => {
    const content = (text ?? input).trim()
    if (!content || loading) return
    setInput('')
    // 传给后端的上下文：发送前的最近 10 条（不含当前问题）
    const history = messages.slice(-10).map((m) => ({ role: m.role, content: m.content }))
    setMessages((prev) => [...prev, { role: 'user', content }])
    setLoading(true)
    try {
      const res = await api.post('/api/assistant/chat', { message: content, history })
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.result }])
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `😅 小团暂时走神了：${e.response?.data?.detail || e.message}`,
        },
      ])
      toast.error('助手请求失败')
    } finally {
      setLoading(false)
    }
  }

  const clearChat = () => {
    setMessages([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
    toast.success('对话已清空')
  }

  const hasMessages = messages.length > 0

  return (
    <>
      {/* 悬浮球 */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 text-white shadow-xl hover:shadow-2xl hover:scale-105 active:scale-95 transition-all flex items-center justify-center group"
        title={open ? '收起助手' : '打开智能助手'}
      >
        {/* 呼吸光环 */}
        <span
          className="absolute inset-0 rounded-full bg-purple-500/40 animate-ping group-hover:animate-none"
          style={{ animationDuration: '2.4s' }}
        />
        <span className="relative flex items-center justify-center">
          {open ? <X className="w-6 h-6" /> : <Bot className="w-7 h-7" />}
        </span>
      </button>

      {/* 聊天面板 */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[min(380px,calc(100vw-2rem))] h-[560px] max-h-[calc(100vh-8rem)] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden animate-page-in">
          {/* 头部 */}
          <div className="px-4 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 flex items-center gap-3 flex-shrink-0">
            <div className="w-9 h-9 rounded-full bg-white/20 border border-white/30 flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white font-semibold text-sm leading-tight">小团智能助手</p>
              <p className="text-white/70 text-[11px] flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse" />
                在线 · 平台问题随时问
              </p>
            </div>
            {hasMessages && (
              <button
                onClick={clearChat}
                className="p-1.5 rounded-lg hover:bg-white/15 text-white/80 transition-colors"
                title="清空对话"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setOpen(false)}
              className="p-1.5 rounded-lg hover:bg-white/15 text-white/80 transition-colors"
              title="收起"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* 消息区 */}
          <div ref={listRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
            {!hasMessages && (
              <div className="flex flex-col items-start gap-3">
                <div className="max-w-[90%] bg-white border border-gray-200 rounded-2xl rounded-bl-md px-3.5 py-2.5 text-sm text-gray-700 shadow-sm">
                  <MarkdownRenderer content={WELCOME} />
                </div>
                <div className="flex flex-wrap gap-2">
                  {QUICK_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      disabled={loading}
                      className="px-3 py-1.5 rounded-full bg-white border border-purple-200 text-purple-600 text-xs hover:bg-purple-50 hover:border-purple-300 transition-colors disabled:opacity-50"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.role === 'user' ? (
                  <div className="max-w-[85%] bg-gradient-to-br from-purple-500 to-indigo-600 text-white rounded-2xl rounded-br-md px-3.5 py-2.5 text-sm whitespace-pre-wrap shadow-sm">
                    {m.content}
                  </div>
                ) : (
                  <div className="max-w-[90%] bg-white border border-gray-200 rounded-2xl rounded-bl-md px-3.5 py-2.5 text-sm text-gray-700 shadow-sm">
                    <MarkdownRenderer content={m.content} />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm flex items-center gap-1.5">
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* 输入区 */}
          <div className="p-3 border-t border-gray-200 bg-white flex items-end gap-2 flex-shrink-0">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
              placeholder="问问小团，例如：额度怎么算？"
              className="flex-1 px-3.5 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              maxLength={2000}
            />
            <button
              onClick={() => send()}
              disabled={loading || !input.trim()}
              className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 text-white flex items-center justify-center hover:opacity-90 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
              title="发送 (Enter)"
            >
              {loading ? (
                <Sparkles className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
