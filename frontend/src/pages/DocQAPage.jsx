import React, { useState, useRef, useEffect } from 'react'
import {
  Upload,
  MessageSquare,
  Send,
  Trash2,
  Clock,
  FileText,
  Eye,
  Bot,
  User,
  Sparkles,
  Search,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'

export default function DocQAPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  const fileRef = useRef(null)
  const chatRef = useRef(null)

  const [uploading, setUploading] = useState(false)
  const [docInfo, setDocInfo] = useState(null)
  const [question, setQuestion] = useState('')
  const [task, setTask] = useState(null)
  const [messages, setMessages] = useState([])
  const [records, setRecords] = useState([])

  useEffect(() => {
    loadRecords()
  }, [])

  const loadRecords = async () => {
    try {
      const res = await api.get('/api/doc-qa/records')
      setRecords(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setMessages([])
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/doc-qa/upload', form)
      setDocInfo(res.data)
      loadRecords()
      toast.success(res.data.message || '上传成功')
      // AI 欢迎语
      setMessages([
        {
          role: 'assistant',
          content: `📄 已加载文档《${res.data.filename}》，共 ${res.data.text_length} 字符。\n\n${res.data.summary?.summary || '你有什么想了解的？请随时提问。'}`,
          time: new Date().toISOString(),
        },
      ])
    } catch (err) {
      toast.error(`上传失败：${err.response?.data?.detail || err.message}`)
    }
    setUploading(false)
  }

  const handleAsk = async (presetQuestion) => {
    const q = (presetQuestion || question).trim()
    if (!q || !docInfo?.doc_id || task) return
    const userMsg = { role: 'user', content: q, time: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setQuestion('')

    const history = messages.slice(-10).map((m) => ({ role: m.role, content: m.content }))
    await submitTask(
      '/api/doc-qa/ask',
      { doc_id: docInfo.doc_id, question: q, history },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: data.answer,
              time: new Date().toISOString(),
              source: data.source,
            },
          ])
          setTask(null)
        },
        onError: (e) => {
          setTask(null)
          toast.error(`问答失败：${e.message}`)
        },
      }
    )

    // 滚动到底部
    setTimeout(
      () => chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' }),
      100
    )
  }

  const deleteRecord = async (id) => {
    try {
      await api.delete(`/api/doc-qa/records/${id}`)
      loadRecords()
      toast.success('已删除')
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI文档问答"
        description="上传任意文档 → AI理解内容 → 自由提问，像聊天一样探索文档"
        icon={Search}
        iconColor="from-indigo-500 to-blue-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Upload className="w-4 h-4 text-indigo-500" /> 上传文档
            </h3>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md,.csv"
              onChange={handleUpload}
              className="hidden"
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full py-12 border-2 border-dashed border-gray-300 rounded-xl hover:border-indigo-400 hover:bg-indigo-50/30 transition-all flex flex-col items-center gap-3"
            >
              <FileText className="w-10 h-10 text-gray-400" />
              <div className="text-sm text-gray-500">
                {uploading ? '解析中...' : '点击上传文档'}
              </div>
              <div className="text-xs text-gray-400">支持 PDF / Word / TXT / MD</div>
            </button>

            {docInfo && (
              <div className="mt-4 space-y-2">
                <div className="p-3 bg-indigo-50 rounded-lg">
                  <div className="font-medium text-indigo-800 text-sm">{docInfo.filename}</div>
                  <div className="text-xs text-indigo-600 mt-1">
                    {(docInfo.file_size / 1024).toFixed(1)} KB · {docInfo.text_length} 字符
                  </div>
                </div>
                {docInfo.summary?.title && (
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-gray-500">{docInfo.summary.type} · 文档摘要</div>
                    <div className="text-sm text-gray-700 mt-1">{docInfo.summary.summary}</div>
                  </div>
                )}
                {docInfo.summary?.suggested_questions?.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-500 mb-1.5">推荐问题：</div>
                    <div className="space-y-1">
                      {docInfo.summary.suggested_questions.slice(0, 4).map((q, i) => (
                        <button
                          key={i}
                          onClick={() => {
                            setQuestion(q)
                            handleAsk(q)
                          }}
                          className="w-full text-left px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 rounded-lg text-xs text-indigo-700 transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 已上传文档（{records.length}）
            </h3>
            {records.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无文档</div>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {records.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between p-2 rounded-lg bg-gray-50 text-xs"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-700 truncate">{r.filename}</div>
                      <div className="text-gray-400">
                        {r.text_length}字符 · {r.created_at?.slice(0, 10)}
                      </div>
                    </div>
                    <button
                      onClick={() => deleteRecord(r.id)}
                      className="p-1 text-gray-300 hover:text-red-500"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：对话区 */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="flex flex-col" style={{ minHeight: '520px' }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-indigo-500" /> 文档问答
                {docInfo && (
                  <span className="text-xs text-gray-400 font-normal">| {docInfo.filename}</span>
                )}
              </h3>
              <span className="text-xs text-gray-400">{messages.length} 条消息</span>
            </div>

            {/* 消息列表 */}
            <div ref={chatRef} className="flex-1 overflow-y-auto space-y-3 mb-4 max-h-[420px] pr-2">
              {messages.length === 0 ? (
                <Empty
                  icon={Search}
                  title="开始探索文档"
                  description="上传文档后，你可以像聊天一样自由提问"
                />
              ) : (
                messages.map((m, i) => (
                  <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
                    {m.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center flex-shrink-0">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                    )}
                    <div
                      className={`max-w-[78%] p-3 rounded-2xl ${
                        m.role === 'user'
                          ? 'bg-indigo-500 text-white rounded-br-md'
                          : 'bg-gray-100 text-gray-800 rounded-bl-md'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                      <div className="flex items-center justify-between mt-1">
                        <span
                          className={`text-[10px] ${m.role === 'user' ? 'text-white/60' : 'text-gray-400'}`}
                        >
                          {new Date(m.time).toLocaleTimeString('zh-CN', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                        {m.source && (
                          <span className="text-[10px] text-gray-400">📄 {m.source}</span>
                        )}
                      </div>
                    </div>
                    {m.role === 'user' && (
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                        <User className="w-4 h-4 text-white" />
                      </div>
                    )}
                  </div>
                ))
              )}
              {task && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                  <div className="p-3 rounded-2xl bg-gray-100 flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    <div
                      className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: '150ms' }}
                    />
                    <div
                      className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: '300ms' }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* 输入区 */}
            <div className="border-t pt-3 space-y-2">
              {task && (
                <div>
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>{task.stage || 'AI 思考中…'}</span>
                    <span>{task.progress || 0}%</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-blue-500 rounded-full transition-all duration-300"
                      style={{ width: `${task.progress || 0}%` }}
                    />
                  </div>
                </div>
              )}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                  placeholder={
                    docInfo ? '对文档提问，如：核心观点是什么？有哪些风险？...' : '请先上传文档'
                  }
                  disabled={!docInfo || !!task}
                  className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none disabled:bg-gray-50"
                />
                <button
                  onClick={() => handleAsk()}
                  disabled={!question.trim() || !!task || !docInfo}
                  className="p-3 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-50 transition-colors"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
