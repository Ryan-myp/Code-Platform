import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { FileText, FolderGit2, Play, Loader2, CheckCircle2, AlertCircle, BookOpen, MessageSquare, Send, Copy, Sparkles, Bot, User, Edit2, Save, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import RichTextEditor from '../components/RichTextEditor'

export default function PRDPage() {
  const [userInput, setUserInput] = useState('')
  const [repoPath, setRepoPath] = useState('/Users/yanping.ma/GolandProjects/sponge')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Chat messages
  const [messages, setMessages] = useState([])
  const messagesEndRef = useRef(null)
  const chatInputRef = useRef(null)
  const [editingMsgIdx, setEditingMsgIdx] = useState(null)
  const [editContent, setEditContent] = useState('')

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // ─── Strip images from HTML for LLM ──────────────────────
  const stripImages = (html) => {
    if (!html) return html
    // Remove all <img> tags and their attributes
    return html.replace(/<img[^>]*>/gi, '[图片已移除]').replace(/src="data:image\/[a-zA-Z]+;base64,[^"]*"/g, '')
  }

  // ─── Generate PRD ────────────────────────────────────────
  const handleGeneratePRD = async () => {
    if (!userInput.trim()) { setError('请输入需求描述'); return }
    setLoading(true); setError(null)
    try {
      const res = await axios.post('/api/prd/generate', { prd_text: stripImages(userInput) })
      const aiReply = res.data.result || '生成失败'
      setMessages(prev => [...prev,
        { role: 'user', content: userInput, timestamp: new Date().toISOString() },
        { role: 'assistant', content: aiReply, timestamp: new Date().toISOString() }
      ])
    } catch (err) {
      setError('生成失败: ' + (err.response?.data?.detail || err.message))
    } finally { setLoading(false) }
  }

  // ─── Review ──────────────────────────────────────────────
  const handleReview = async () => {
    if (messages.length < 1) { setError('先生成 PRD'); return }
    const lastPrd = messages[messages.length - 1].role === 'assistant' ? messages[messages.length - 1].content : ''
    if (!lastPrd) { setError('没有可审查的 PRD'); return }
    setLoading(true); setError(null)
    try {
      const res = await axios.post('/api/prd/review', { prd_text: lastPrd, repo_path: repoPath })
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.result || res.data.report || '审查失败', timestamp: new Date().toISOString() }])
    } catch (err) {
      setError('审查失败: ' + (err.response?.data?.detail || err.message))
    } finally { setLoading(false) }
  }

  // ─── Chat in PRD mode ───────────────────────────────────
  const handleChatSend = async () => {
    const text = chatInputRef.current?.value?.trim()
    if (!text) return
    chatInputRef.current.value = ''
    setMessages(prev => [...prev, { role: 'user', content: text, timestamp: new Date().toISOString() }])
    setLoading(true)
    try {
      const historyText = messages.map(m => `${m.role === 'user' ? '用户' : 'AI'}: ${stripImages(m.content)}`).join('\n\n')
      const fullContext = historyText + '\n\n用户最新指令: ' + text
      const res = await axios.post('/api/prd/generate', { prd_text: fullContext })
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.result || '处理失败', timestamp: new Date().toISOString() }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ 处理失败: ' + (err.response?.data?.detail || err.message), timestamp: new Date().toISOString(), error: true }])
    } finally { setLoading(false) }
  }

  // ─── Edit message inline ────────────────────────────────
  const startEdit = (idx) => { setEditingMsgIdx(idx); setEditContent(messages[idx].content) }
  const saveEdit = (idx) => { const u = [...messages]; u[idx] = { ...u[idx], content: editContent }; setMessages(u); setEditingMsgIdx(null) }
  const cancelEdit = () => setEditingMsgIdx(null)

  const copyToClipboard = (text) => { navigator.clipboard.writeText(text); alert('已复制') }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-4 py-6">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center justify-center gap-2"><FileText className="w-8 h-8 text-blue-600" /> PRD 编写</h1>
        <p className="text-lg text-gray-600">输入需求描述，AI 自动生成产品需求文档，支持对话式迭代修改</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3 max-w-6xl mx-auto">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" /><p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* ─── Left: Input + Right: Chat ────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-[1600px] mx-auto" style={{ height: 'calc(100vh - 280px)' }}>
        
        {/* LEFT: Input Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col">
          <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2"><BookOpen className="w-4 h-4 text-blue-600" /> 需求输入</h2>
            <span className="text-xs text-gray-400">左侧：输入需求，生成 PRD</span>
          </div>
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            <RichTextEditor value={userInput} onChange={setUserInput}
              placeholder={"请输入需求描述...\n\n例如：\n1. 新增素材分享功能\n2. 支持将创意素材分享给其他广告账户\n3. 分享时需要校验素材状态"}
              minHeight={180} />
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1"><FolderGit2 className="w-4 h-4 inline mr-1" />仓库路径（可选）</label>
              <input type="text" className="w-full p-2.5 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-sm font-mono"
                value={repoPath} onChange={(e) => setRepoPath(e.target.value)} placeholder="/path/to/repo" />
            </div>

            <div className="flex gap-2">
              <button onClick={handleGeneratePRD} disabled={loading || !userInput.trim()}
                className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-2.5 px-4 rounded-lg hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all flex items-center justify-center gap-2">
                {loading ? <><Loader2 className="w-4 h-4 animate-spin" />生成中...</> : <><Sparkles className="w-4 h-4" />生成 PRD</>}
              </button>
              {messages.length > 0 && (
                <button onClick={handleReview} disabled={loading}
                  className="px-3 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium transition-all flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />审查
                </button>
              )}
            </div>

            {/* Quick actions hint */}
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
              <p className="text-xs font-medium text-blue-700 mb-1">💡 使用提示</p>
              <ul className="text-xs text-blue-600 space-y-0.5">
                <li>• 在左侧输入需求，点击"生成 PRD"</li>
                <li>• PRD 会出现在右侧聊天框中</li>
                <li>• 在右侧聊天框中对 PRD 提出修改意见</li>
                <li>• 点击"审查"对当前 PRD 进行审查</li>
              </ul>
            </div>
          </div>
        </div>

        {/* RIGHT: Chat Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col">
          <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-purple-600" />
              <h2 className="text-base font-semibold text-gray-900">PRD 智能协作</h2>
              {messages.length > 0 && <span className="text-xs text-gray-400 ml-1">{messages.length} 条消息</span>}
            </div>
            {messages.length > 0 && (
              <button onClick={() => setMessages([])} className="text-xs text-gray-400 hover:text-red-500">清空对话</button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 py-16">
                <MessageSquare className="w-12 h-12 mb-3 opacity-40" />
                <p className="text-sm font-medium">暂无对话记录</p>
                <p className="text-xs mt-1">在左侧输入需求后点击"生成 PRD"</p>
              </div>
            ) : messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex items-start gap-2 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
                    msg.role === 'user' ? 'bg-purple-600' : 'bg-blue-600'
                  }`}>
                    {msg.role === 'user' ? <User className="w-3.5 h-3.5 text-white" /> : <Bot className="w-3.5 h-3.5 text-white" />}
                  </div>
                  <div className={`rounded-2xl px-3 py-2.5 ${
                    msg.role === 'user' ? 'bg-purple-600 text-white' : msg.error ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-gray-100 text-gray-900'
                  }`}>
                    {/* Actions bar */}
                    <div className={`flex items-center gap-1 mb-1.5 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-400'}`}>
                      <button onClick={() => startEdit(idx)} title="编辑" className="p-0.5 hover:bg-black/10 rounded"><Edit2 className="w-3 h-3" /></button>
                      <button onClick={() => copyToClipboard(msg.content)} title="复制" className="p-0.5 hover:bg-black/10 rounded"><Copy className="w-3 h-3" /></button>
                    </div>
                    {/* Content */}
                    {editingMsgIdx === idx ? (
                      <div className="space-y-1.5">
                        <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)}
                          className={`w-full p-2 rounded-lg text-sm resize-none font-mono ${msg.role === 'user' ? 'bg-white/20 text-white placeholder-white/60' : 'bg-white text-gray-900'}`} rows={6} />
                        <div className="flex gap-1.5">
                          <button onClick={() => saveEdit(idx)} className="px-2 py-0.5 bg-green-500 text-white text-xs rounded hover:bg-green-600 flex items-center gap-0.5">
                            <Save className="w-2.5 h-2.5 inline" />保存
                          </button>
                          <button onClick={cancelEdit} className="px-2 py-0.5 bg-gray-500 text-white text-xs rounded hover:bg-gray-600 flex items-center gap-0.5">
                            <X className="w-2.5 h-2.5 inline" />取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap text-sm leading-relaxed">
                        {msg.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown> : msg.content}
                      </div>
                    )}
                    <div className={`text-xs mt-1.5 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-400'}`}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {loading && <div className="flex items-center gap-2 text-gray-500"><Loader2 className="w-4 h-4 animate-spin" /><span className="text-sm">AI 正在思考...</span></div>}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input */}
          <div className="border-t border-gray-200 bg-gray-50 p-4">
            <div className="flex items-end gap-2">
              <textarea ref={chatInputRef} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend() } }}
                placeholder="对 PRD 提出修改意见，例如：增加用户权限管理章节、补充异常流程..."
                className="flex-1 p-2.5 border border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 resize-none text-sm bg-white" rows={2} />
              <button onClick={handleChatSend} disabled={loading || !chatInputRef.current?.value?.trim()}
                className="px-3 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 self-end">
                <Send className="w-4 h-4" /><span className="hidden sm:inline">发送</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
