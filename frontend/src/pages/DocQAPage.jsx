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
  Download,
  RefreshCw,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge } from '../components/ui'
import ShareButton from '../components/ShareButton'
import HistoryPanel from '../components/HistoryPanel'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import MarkdownRenderer from '../components/MarkdownRenderer'
import useToolHistory from '../hooks/useToolHistory'

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
  // v15：多文档联合问答（勾选≥2篇时跨文档检索）
  const [selectedDocIds, setSelectedDocIds] = useState([])
  const { history, add, remove, clear } = useToolHistory('doc_qa_history_v1', 20)

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
    // 边界校验：后端单文件上限 20MB，前端提前拦截避免上传中断
    if (file.size > 20 * 1024 * 1024) {
      toast.error('文件过大：单次上传请控制在 20MB 以内')
      e.target.value = ''
      return
    }
    setUploading(true)
    setMessages([])
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/doc-qa/upload', form)
      setDocInfo(res.data)
      setSelectedDocIds((prev) =>
        prev.includes(res.data.doc_id) ? prev : [...prev, res.data.doc_id]
      )
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

  // v15：勾选/取消文档（≥2 篇进入联合问答）
  const toggleSelectDoc = (id) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const handleAsk = async (presetQuestion) => {
    const q = (presetQuestion || question).trim()
    // v15：≥2 篇勾选 → 联合问答；否则用当前激活文档
    const docIds =
      selectedDocIds.length >= 2 ? selectedDocIds : docInfo?.doc_id ? [docInfo.doc_id] : []
    if (!q || docIds.length === 0 || task) return
    const userMsg = { role: 'user', content: q, time: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setQuestion('')

    const history = messages.slice(-10).map((m) => ({ role: m.role, content: m.content }))
    await submitTask(
      '/api/doc-qa/ask',
      { doc_id: docIds[0], doc_ids: docIds, question: q, history },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setMessages((prev) => {
            const next = [
              ...prev,
              {
                role: 'assistant',
                content: data.answer,
                time: new Date().toISOString(),
                source: data.source,
                citations: data.citations || [],
                docIds: data.doc_ids || docIds,
              },
            ]
            // 专业基线：每轮问答落一次会话快照（可回溯可复用）
            add({
              title: q.slice(0, 24),
              docName: docInfo?.filename || '文档',
              docId: docIds[0],
              question: q,
              messages: next.map((m) => ({
                role: m.role,
                content: m.content,
                source: m.source,
                citations: m.citations,
              })),
            })
            return next
          })
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

  // 专业基线：会话历史复用 / 导出 / 重试
  const handleReuse = (item) => {
    if (!item.docId) {
      toast.error('该会话缺少文档信息，无法恢复')
      return
    }
    if (!records.some((r) => r.id === item.docId)) {
      toast.error('原文档已被删除，请重新上传后再恢复会话')
      return
    }
    setSelectedDocIds([item.docId])
    setMessages(
      item.messages?.map((m) => ({ ...m, time: new Date().toISOString() })) || []
    )
    toast.success(`已恢复会话《${item.title || item.docName}》`)
  }

  const handleRetry = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (!lastUser || !docInfo || task) return
    // 回滚到最后一条用户消息（去掉其后的 assistant 回复）
    const idx = messages.findIndex((m) => m === lastUser)
    setMessages(messages.slice(0, idx + 1))
    handleAsk(lastUser.content)
  }

  const buildChatMd = () => {
    if (messages.length === 0) return ''
    const title = docInfo?.filename || '文档问答'
    return `# 文档问答记录：${title}\n\n`
      + messages
          .map((m) => {
            const citeBlock = m.citations?.length
              ? `\n\n> 引用溯源：\n${m.citations.map((c, i) => `> [${i + 1}] ${c.doc_name}：${c.text}`).join('\n')}`
              : ''
            return `### ${m.role === 'user' ? '🙋 提问' : '🤖 回答'}（${new Date(m.time).toLocaleString('zh-CN')}）\n\n${m.content}${m.source ? `\n\n> 来源：${m.source}` : ''}${citeBlock}\n`
          })
          .join('\n---\n\n')
  }

  const exportChat = () => {
    if (messages.length === 0) return
    const title = docInfo?.filename || '文档问答'
    const blob = new Blob([buildChatMd()], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title.replace(/[\\/:*?"<>|]/g, '_')}-问答记录.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 3000)
    toast.success('对话记录已导出')
  }

  const clearChat = () => {
    if (!window.confirm('确定清空当前对话吗？')) return
    setMessages([])
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
              {selectedDocIds.length >= 2 && (
                <span className="ml-auto text-[10px] text-indigo-600 font-normal">
                  {selectedDocIds.length} 篇已选 · 联合问答
                </span>
              )}
            </h3>
            {records.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无文档</div>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {records.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => toggleSelectDoc(r.id)}
                    className={`flex items-center gap-2 p-2 rounded-lg text-xs cursor-pointer transition-colors ${
                      selectedDocIds.includes(r.id)
                        ? 'bg-indigo-50 ring-1 ring-indigo-200'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(r.id)}
                      onChange={(e) => e.stopPropagation()}
                      onClick={(e) => e.stopPropagation()}
                      className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 flex-shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-700 truncate">{r.filename}</div>
                      <div className="text-gray-400">
                        {r.text_length}字符 · {r.created_at?.slice(0, 10)}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteRecord(r.id)
                      }}
                      className="p-1 text-gray-300 hover:text-red-500 flex-shrink-0"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* 会话历史（专业基线：可回溯可恢复） */}
          <HistoryPanel
            history={history}
            onReuse={handleReuse}
            onRemove={remove}
            onClear={clear}
            title="会话历史"
            renderSummary={(item) =>
              `${item.docName || '文档'} · ${item.question?.slice(0, 40) || ''}`
            }
          />
        </div>

        {/* 右侧：对话区 */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="flex flex-col" style={{ minHeight: '520px' }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-indigo-500" /> 文档问答
                <span className="text-xs text-gray-400 font-normal">
                  |{' '}
                  {selectedDocIds.length >= 2
                    ? `${selectedDocIds.length} 篇文档联合问答`
                    : docInfo?.filename}
                </span>
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">{messages.length} 条消息</span>
                {messages.length > 0 && (
                  <>
                    <button
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(buildChatMd())
                          toast.success('对话记录已复制')
                        } catch {
                          toast.error('复制失败')
                        }
                      }}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-indigo-600 rounded-lg transition-colors"
                      title="复制对话记录"
                    >
                      📋 复制
                    </button>
                    <button
                      onClick={exportChat}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-indigo-600 rounded-lg transition-colors"
                      title="导出对话记录"
                    >
                      <Download className="w-3 h-3" /> 导出
                    </button>
                    <ShareButton content={buildChatMd()} title="文档问答记录" contentType="doc_qa" />
                    <button
                      onClick={handleRetry}
                      disabled={!docInfo || !!task}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-indigo-600 rounded-lg transition-colors disabled:opacity-40"
                      title="重新回答最后一个问题"
                    >
                      <RefreshCw className="w-3 h-3" /> 重试
                    </button>
                    <button
                      onClick={clearChat}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-3 h-3" /> 清空对话
                    </button>
                  </>
                )}
              </div>
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
                      {m.role === 'user' ? (
                        <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                      ) : (
                        <MarkdownRenderer content={m.content} className="text-sm" />
                      )}
                      {/* v15：引用溯源（回答附原文片段定位） */}
                      {m.citations?.length > 0 && (
                        <details className="mt-2 bg-white/80 rounded-lg px-3 py-2">
                          <summary className="text-[11px] text-indigo-600 cursor-pointer font-medium select-none">
                            引用溯源（{m.citations.length} 处）
                          </summary>
                          <div className="space-y-1.5 mt-2">
                            {m.citations.map((c, ci) => (
                              <div
                                key={ci}
                                className="text-[11px] border-l-2 border-indigo-200 pl-2"
                              >
                                <span className="text-indigo-500 font-medium">
                                  [{ci + 1}] {c.doc_name}
                                </span>
                                <p className="mt-0.5 text-gray-500 leading-relaxed line-clamp-3">
                                  {c.text}
                                </p>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
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
