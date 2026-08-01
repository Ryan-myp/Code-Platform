import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileText, Code2, TestTube2, Send, Loader2, AlertCircle, BookOpen, MessageSquare, Copy, Sparkles, Bot, User, Edit2, Save, X, FolderGit2, Settings, ListChecks, Download, Layers, ArrowRight, CheckCircle2, ListTodo } from 'lucide-react'
import RichTextEditor from '../components/RichTextEditor'

const PIPELINE = ['prd', 'review', 'td', 'test', 'code']

const TABS = {
  prd: { label: 'PRD 编写', icon: FileText, color: 'blue', next: 'review', nextLabel: '下一步: 审查' },
  review: { label: 'PRD 审查', icon: BookOpen, color: 'emerald', next: 'td', nextLabel: '下一步: 技术方案' },
  td: { label: '技术方案', icon: Code2, color: 'indigo', next: 'test', nextLabel: '下一步: 测试用例' },
  test: { label: '测试用例', icon: TestTube2, color: 'green', next: 'code', nextLabel: '下一步: 代码生成' },
  code: { label: '代码生成', icon: Layers, color: 'purple' },
}

function initState() {
  return { messages: [], userInput: '', repoPath: '/Users/yanping.ma/GolandProjects/sponge', prdText: '', techDesign: '', language: 'go', loading: false, error: null, editingMsgIdx: null, editContent: '', requirementId: null }
}

export default function AIWorkspacePage() {
  const [tab, setTab] = useState('prd')
  const [state, setState] = useState(() => ({ prd: initState(), review: initState(), td: initState(), test: initState(), code: initState() }))
  const [requirements, setRequirements] = useState([])
  const messagesEndRef = useRef(null)
  const chatInputRef = useRef(null)
  const [selectedReqId, setSelectedReqId] = useState(null)

  const s = state[tab]
  const update = (patch) => setState(prev => ({ ...prev, [tab]: { ...prev[tab], ...patch } }))

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [s.messages])

  useEffect(() => {
    axios.get('/api/requirements').then(res => setRequirements(res.data)).catch(() => {})
    const params = new URLSearchParams(window.location.search)
    const reqFromUrl = params.get('requirement_id')
    if (reqFromUrl) {
      setSelectedReqId(reqFromUrl)
      const t = params.get('tab')
      if (t && PIPELINE.includes(t)) setTab(t)
    }
  }, [])

  const selectedReq = requirements.find(r => r.id === selectedReqId) || null

  const handleSelectRequirement = (reqId) => {
    setSelectedReqId(reqId)
    const req = requirements.find(r => r.id === reqId)
    if (!req) return
    if (tab === 'prd') update({ userInput: req.description || '' })
    else if (tab === 'review') update({ prdText: req.prd_text || '' })
    else if (tab === 'td') update({ prdText: req.review_report || req.prd_text || '' })
    else if (tab === 'test') { update({ prdText: req.prd_text || '', techDesign: req.tech_design || '' }) }
    else if (tab === 'code') update({ techDesign: req.tech_design || '' })
  }

  const saveToRequirement = async (stage, content) => {
    if (!selectedReqId) return
    try {
      const res = await axios.post(`/api/requirements/${selectedReqId}/pipeline-output`, { stage, content })
      return res.data
    } catch (e) {
      update({ error: '保存到需求失败: ' + (e.response?.data?.detail || e.message) })
      return null
    }
  }

  const stripImages = (html) => html ? html.replace(/<img[^>]*>/gi, '[图片已移除]').replace(/src="data:image\/[a-zA-Z]+;base64,[^"]*"/g, '') : html

  const callApi = async (url, body) => {
    update({ loading: true, error: null })
    const res = await axios.post(url, body)
    return res.data.result || '处理失败'
  }

  const addMessage = (role, content) => {
    update({ messages: [...s.messages, { role, content, timestamp: new Date().toISOString() }] })
  }

  const handleGenerate = async () => {
    try {
      if (tab === 'prd') {
        if (!s.userInput.trim()) { update({ error: '请输入需求描述' }); return }
        const result = await callApi('/api/prd/generate', { prd_text: stripImages(s.userInput) })
        addMessage('user', s.userInput)
        addMessage('assistant', result)
        update({ userInput: '' })
        await saveToRequirement('prd', result)
      } else if (tab === 'review') {
        if (!s.prdText.trim()) { update({ error: '请输入 PRD 内容' }); return }
        const result = await callApi('/api/prd/review', { prd_text: stripImages(s.prdText), repo_path: s.repoPath })
        addMessage('user', s.prdText)
        addMessage('assistant', result)
        await saveToRequirement('review', result)
      } else if (tab === 'td') {
        if (!s.prdText.trim()) { update({ error: '请输入 PRD 内容' }); return }
        const result = await callApi('/api/prd/technical-design', { prd_text: stripImages(s.prdText), repo_path: s.repoPath })
        addMessage('user', s.prdText)
        addMessage('assistant', result)
        await saveToRequirement('td', result)
      } else if (tab === 'test') {
        if (!s.prdText.trim()) { update({ error: '请输入 PRD 内容' }); return }
        const result = await callApi('/api/prd/test-cases', { prd_text: stripImages(s.prdText), tech_design: stripImages(s.techDesign) })
        addMessage('user', s.prdText + (s.techDesign ? '\n\n技术方案: ' + s.techDesign : ''))
        addMessage('assistant', result)
        await saveToRequirement('test', result)
      } else if (tab === 'code') {
        if (!s.techDesign.trim()) { update({ error: '请输入技术方案' }); return }
        const result = await callApi('/api/prd/generate-code', { task_type: 'code', tech_design: stripImages(s.techDesign), language: s.language })
        addMessage('user', `语言: ${s.language}\n技术方案: ${s.techDesign}`)
        addMessage('assistant', result)
        await saveToRequirement('code', result)
      }
    } catch (e) {
      update({ error: '生成失败: ' + e.message })
    } finally { update({ loading: false }) }
  }

  const handleChatSend = async () => {
    const text = chatInputRef.current?.value?.trim()
    if (!text) return
    chatInputRef.current.value = ''
    addMessage('user', text)
    update({ loading: true })
    try {
      const historyText = s.messages.map(m => `${m.role === 'user' ? '用户' : 'AI'}: ${stripImages(m.content)}`).join('\n\n') + '\n\n用户最新指令: ' + text
      let url, body
      if (tab === 'prd') { url = '/api/prd/generate'; body = { prd_text: historyText } }
      else if (tab === 'review') { url = '/api/prd/review'; body = { prd_text: historyText, repo_path: s.repoPath } }
      else if (tab === 'td') { url = '/api/prd/technical-design'; body = { prd_text: historyText, repo_path: s.repoPath } }
      else if (tab === 'test') { url = '/api/prd/test-cases'; body = { prd_text: historyText, tech_design: s.techDesign } }
      else { url = '/api/prd/code-chat'; body = { message: historyText, language: s.language } }
      const result = await callApi(url, body)
      addMessage('assistant', result)
    } catch (e) {
      addMessage('assistant', '❌ 处理失败: ' + e.message)
    } finally { update({ loading: false }) }
  }

  const goNext = () => {
    const next = TABS[tab]?.next
    if (!next) return
    const req = requirements.find(r => r.id === selectedReqId)
    setTab(next)
    if (req) {
      const nextS = state[next]
      const patch = {}
      if (next === 'review' && req.prd_text) patch.prdText = req.prd_text
      else if (next === 'td') patch.prdText = req.review_report || req.prd_text || ''
      else if (next === 'test') { patch.prdText = req.prd_text || ''; patch.techDesign = req.tech_design || '' }
      else if (next === 'code') patch.techDesign = req.tech_design || ''
      if (Object.keys(patch).length > 0) {
        setState(prev => ({ ...prev, [next]: { ...prev[next], ...patch } }))
      }
    }
  }

  const startEdit = (idx) => { update({ editingMsgIdx: idx, editContent: s.messages[idx].content }) }
  const saveEdit = (idx) => { const u = [...s.messages]; u[idx] = { ...u[idx], content: s.editContent }; update({ messages: u, editingMsgIdx: null }) }
  const cancelEdit = () => update({ editingMsgIdx: null })
  const copyToClipboard = (text) => { navigator.clipboard.writeText(text); alert('已复制') }
  const downloadCode = (text) => {
    const ext = s.language === 'python' ? 'py' : s.language === 'java' ? 'java' : s.language === 'typescript' ? 'ts' : 'go'
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `code_${Date.now()}.${ext}`; a.click(); URL.revokeObjectURL(url)
  }

  const tabInfo = TABS[tab]
  const colorMap = { blue: { from: 'from-blue-600', to: 'to-indigo-600', light: 'bg-blue-50', border: 'border-blue-100', text: 'text-blue-700' }, emerald: { from: 'from-emerald-600', to: 'to-emerald-600', light: 'bg-emerald-50', border: 'border-emerald-100', text: 'text-emerald-700' }, indigo: { from: 'from-indigo-600', to: 'to-purple-600', light: 'bg-indigo-50', border: 'border-indigo-100', text: 'text-indigo-700' }, green: { from: 'from-green-600', to: 'to-emerald-600', light: 'bg-green-50', border: 'border-green-100', text: 'text-green-700' }, purple: { from: 'from-purple-600', to: 'to-indigo-600', light: 'bg-purple-50', border: 'border-purple-100', text: 'text-purple-700' } }
  const c = colorMap[tabInfo.color]

  const canGenerate = tab === 'prd' ? s.userInput.trim() : tab === 'code' ? s.techDesign.trim() : s.prdText.trim()

  return (
    <div className="space-y-6">
      <div className="text-center space-y-4 py-6">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center justify-center gap-2">
          <tabInfo.icon className={`w-8 h-8 text-${tabInfo.color}-600`} /> AI 工作台
        </h1>
        <p className="text-lg text-gray-600">统一 AI 研发助手，支持 PRD 编写/审查、技术方案、测试用例和代码生成</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 max-w-[1600px] mx-auto">
        {PIPELINE.map((key) => {
          const t = TABS[key]
          return (
            <button key={key} onClick={() => setTab(key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? `border-${t.color}-600 text-${t.color}-600`
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              <t.icon className="w-4 h-4" /> {t.label}
            </button>
          )
        })}
      </div>

      {/* Error */}
      {s.error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3 max-w-[1600px] mx-auto">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" /><p className="text-red-700 text-sm">{s.error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-[1600px] mx-auto" style={{ height: 'calc(100vh - 340px)' }}>
        {/* LEFT: Input Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col">
          <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <tabInfo.icon className={`w-4 h-4 text-${tabInfo.color}-600`} /> {tabInfo.label}
              </h2>
              <span className="text-xs text-gray-400">左侧：输入内容，点击生成</span>
            </div>
            {/* Requirement selector */}
            <div className="flex items-center gap-2">
              <ListTodo className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <select value={selectedReqId || ''} onChange={e => handleSelectRequirement(e.target.value)}
                className="flex-1 p-1.5 text-xs border border-gray-200 rounded-md bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/10">
                <option value="">-- 选择关联需求（可选） --</option>
                {requirements.map(r => (
                  <option key={r.id} value={r.id}>
                    [{r.status}] {r.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {selectedReq && (
              <div className="p-2 bg-indigo-50 rounded-lg border border-indigo-100 text-xs text-indigo-700">
                已关联: <strong>{selectedReq.name}</strong> (状态: {selectedReq.status})
              </div>
            )}
            {renderLeftPanel()}
            <div className="flex gap-2">
              <button onClick={handleGenerate} disabled={s.loading || !canGenerate}
                className={`flex-1 bg-gradient-to-r ${c.from} ${c.to} text-white py-2.5 px-4 rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all flex items-center justify-center gap-2`}>
                {s.loading ? <><Loader2 className="w-4 h-4 animate-spin" />生成中...</> : <><Sparkles className="w-4 h-4" />{getGenerateBtnText()}</>}
              </button>
              {tabInfo.next && s.messages.length > 0 && (
                <button onClick={goNext}
                  className="px-4 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-all flex items-center gap-1.5 text-sm whitespace-nowrap">
                  {tabInfo.nextLabel} <ArrowRight className="w-4 h-4" />
                </button>
              )}
            </div>
            <div className={`p-3 ${c.light} rounded-lg border ${c.border}`}>
              <p className={`text-xs font-medium ${c.text} mb-1`}>💡 使用提示</p>
              <ul className={`text-xs ${c.text} space-y-0.5`}>
                <li>• 在左侧输入内容，点击"{getGenerateBtnText()}"</li>
                <li>• 结果出现在右侧聊天框中</li>
                <li>• 在右侧对话框中提出修改意见</li>
                {selectedReqId && <li>• 生成结果将自动保存到关联需求</li>}
              </ul>
            </div>
          </div>
        </div>

        {/* RIGHT: Chat Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col">
          <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-purple-600" />
              <h2 className="text-base font-semibold text-gray-900">AI 对话</h2>
              {s.messages.length > 0 && <span className="text-xs text-gray-400 ml-1">{s.messages.length} 条消息</span>}
            </div>
            {s.messages.length > 0 && (
              <button onClick={() => update({ messages: [] })} className="text-xs text-gray-400 hover:text-red-500">清空对话</button>
            )}
          </div>
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {s.messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 py-16">
                <MessageSquare className="w-12 h-12 mb-3 opacity-40" />
                <p className="text-sm font-medium">暂无对话记录</p>
                <p className="text-xs mt-1">在左侧输入内容后点击"{getGenerateBtnText()}"</p>
              </div>
            ) : s.messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex items-start gap-2 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-purple-600' : 'bg-blue-600'}`}>
                    {msg.role === 'user' ? <User className="w-3.5 h-3.5 text-white" /> : <Bot className="w-3.5 h-3.5 text-white" />}
                  </div>
                  <div className={`rounded-2xl px-3 py-2.5 ${msg.role === 'user' ? 'bg-purple-600 text-white' : msg.error ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-gray-100 text-gray-900'}`}>
                    <div className={`flex items-center gap-1 mb-1.5 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-400'}`}>
                      <button onClick={() => startEdit(idx)} title="编辑" className="p-0.5 hover:bg-black/10 rounded"><Edit2 className="w-3 h-3" /></button>
                      <button onClick={() => copyToClipboard(msg.content)} title="复制" className="p-0.5 hover:bg-black/10 rounded"><Copy className="w-3 h-3" /></button>
                      {tab === 'code' && msg.role === 'assistant' && (
                        <button onClick={() => downloadCode(msg.content)} title="下载代码" className="p-0.5 hover:bg-black/10 rounded"><Download className="w-3 h-3" /></button>
                      )}
                    </div>
                    {s.editingMsgIdx === idx ? (
                      <div className="space-y-1.5">
                        <textarea value={s.editContent} onChange={(e) => update({ editContent: e.target.value })}
                          className={`w-full p-2 rounded-lg text-sm resize-none font-mono ${msg.role === 'user' ? 'bg-white/20 text-white placeholder-white/60' : 'bg-white text-gray-900'}`} rows={6} />
                        <div className="flex gap-1.5">
                          <button onClick={() => saveEdit(idx)} className="px-2 py-0.5 bg-green-500 text-white text-xs rounded hover:bg-green-600 flex items-center gap-0.5"><Save className="w-2.5 h-2.5 inline" />保存</button>
                          <button onClick={cancelEdit} className="px-2 py-0.5 bg-gray-500 text-white text-xs rounded hover:bg-gray-600 flex items-center gap-0.5"><X className="w-2.5 h-2.5 inline" />取消</button>
                        </div>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap text-sm leading-relaxed">
                        {msg.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown> : msg.content}
                      </div>
                    )}
                    <div className={`text-xs mt-1.5 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-400'}`}>{new Date(msg.timestamp).toLocaleTimeString()}</div>
                  </div>
                </div>
              </div>
            ))}
            {s.loading && <div className="flex items-center gap-2 text-gray-500"><Loader2 className="w-4 h-4 animate-spin" /><span className="text-sm">AI 正在思考...</span></div>}
            <div ref={messagesEndRef} />
          </div>
          <div className="border-t border-gray-200 bg-gray-50 p-4">
            <div className="flex items-end gap-2">
              <textarea ref={chatInputRef} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend() } }}
                placeholder={getChatPlaceholder()}
                className="flex-1 p-2.5 border border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 resize-none text-sm bg-white" rows={2} />
              <button onClick={handleChatSend} disabled={s.loading || !chatInputRef.current?.value?.trim()}
                className="px-3 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 self-end">
                <Send className="w-4 h-4" /><span className="hidden sm:inline">发送</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )

  function renderLeftPanel() {
    if (tab === 'prd') {
      return (
        <>
          <RichTextEditor value={s.userInput} onChange={(v) => update({ userInput: v })}
            placeholder={"请输入需求描述...\n\n例如：\n1. 新增素材分享功能\n2. 支持将创意素材分享给其他广告账户\n3. 分享时需要校验素材状态"}
            minHeight={180} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1"><FolderGit2 className="w-4 h-4 inline mr-1" />仓库路径（可选）</label>
            <input type="text" className="w-full p-2.5 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-sm font-mono"
              value={s.repoPath} onChange={(e) => update({ repoPath: e.target.value })} placeholder="/path/to/repo" />
          </div>
        </>
      )
    }
    if (tab === 'review') {
      return (
        <>
          <RichTextEditor value={s.prdText} onChange={(v) => update({ prdText: v })} placeholder={"请输入 PRD 内容..."} minHeight={200} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">仓库路径（可选）</label>
            <input type="text" className="w-full p-2.5 border border-gray-300 rounded-lg focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 text-sm font-mono"
              value={s.repoPath} onChange={(e) => update({ repoPath: e.target.value })} placeholder="/path/to/repo" />
          </div>
        </>
      )
    }
    if (tab === 'td') {
      return (
        <>
          <RichTextEditor value={s.prdText} onChange={(v) => update({ prdText: v })} placeholder={"请输入 PRD 内容..."} minHeight={180} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">仓库路径（可选）</label>
            <input type="text" className="w-full p-2.5 border border-gray-300 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 text-sm font-mono"
              value={s.repoPath} onChange={(e) => update({ repoPath: e.target.value })} placeholder="/path/to/repo" />
          </div>
        </>
      )
    }
    if (tab === 'test') {
      return (
        <>
          <RichTextEditor value={s.prdText} onChange={(v) => update({ prdText: v })} placeholder={"请输入 PRD 内容..."} minHeight={150} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">技术方案（可选）</label>
            <RichTextEditor value={s.techDesign} onChange={(v) => update({ techDesign: v })} placeholder="粘贴技术方案内容，增强测试覆盖度..." minHeight={100} />
          </div>
        </>
      )
    }
    if (tab === 'code') {
      return (
        <>
          <RichTextEditor value={s.techDesign} onChange={(v) => update({ techDesign: v })} placeholder="粘贴或输入技术方案内容..." minHeight={180} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">编程语言</label>
            <select className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500" value={s.language} onChange={e => update({ language: e.target.value })}>
              <option value="go">Go</option>
              <option value="python">Python</option>
              <option value="java">Java</option>
              <option value="typescript">TypeScript</option>
            </select>
          </div>
        </>
      )
    }
  }

  function getGenerateBtnText() {
    if (tab === 'prd') return '生成 PRD'
    if (tab === 'review') return '开始审查'
    if (tab === 'td') return '生成技术方案'
    if (tab === 'test') return '生成测试用例'
    return '生成代码'
  }

  function getChatPlaceholder() {
    if (tab === 'prd') return '对 PRD 提出修改意见，例如：增加用户权限管理章节...'
    if (tab === 'review') return '对审查结果提出意见或追问...'
    if (tab === 'td') return '对技术方案提出修改意见...'
    if (tab === 'test') return '对测试用例提出修改意见，例如：补充边界条件...'
    return '对生成的代码提出修改意见，例如：增加错误处理...'
  }
}
