import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { Code2, Loader2, AlertCircle, Send, Bot, Copy, Download, Sparkles, Image as ImageIcon, MessageSquare, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function CodePage() {
  const [techDesign, setTechDesign] = useState('')
  const [language, setLanguage] = useState('go')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [error, setError] = useState(null)
  const [uploadedImage, setUploadedImage] = useState(null)
  const [currentAgent, setCurrentAgent] = useState(null)
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    const saved = localStorage.getItem('tech_design')
    if (saved) setTechDesign(saved)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleImageUpload = (e) => {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => setUploadedImage(reader.result)
      reader.readAsDataURL(file)
    }
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() && !uploadedImage) return
    const userMessage = { role: 'user', content: inputMessage, image: uploadedImage, timestamp: new Date().toISOString() }
    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setUploadedImage(null)
    setLoading(true)
    try {
      const res = await axios.post('/api/prd/generate-code', { task_type: 'code', tech_design: techDesign || inputMessage, message: inputMessage, language })
      if (res.data.status === 'success') {
        setMessages(prev => [...prev, { role: 'assistant', content: res.data.result, timestamp: new Date().toISOString() }])
      } else {
        setError('生成失败: ' + (res.data.result || '未知错误'))
      }
    } catch (err) {
      const errMsg = err.response?.data?.result || err.response?.data?.detail || err.message
      setError('生成失败: ' + errMsg)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  const handleCopy = (text) => { navigator.clipboard.writeText(text); alert('已复制到剪贴板') }
  const handleDownload = (text, filename) => {
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url)
  }

  const selectAgent = (agentName) => {
    setCurrentAgent(agentName)
    setMessages([{ role: 'assistant', content: `你好！我是${agentName}，有什么可以帮你的吗？`, timestamp: new Date().toISOString() }])
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-[1400px] mx-auto p-6">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-purple-600 to-indigo-700 rounded-2xl shadow-lg mb-4">
            <Code2 className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold text-gray-900 mb-2">代码生成</h1>
          <p className="text-gray-500">基于技术方案自动生成 Go/Python/Java 代码</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Panel - Configuration */}
          <div className="lg:col-span-4 space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-200 bg-gray-50">
                <h2 className="text-base font-semibold text-gray-900 flex items-center">
                  <Code2 className="w-4 h-4 text-purple-600 mr-2" />
                  技术方案输入
                </h2>
              </div>
              <div className="p-5 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">技术方案内容</label>
                  <textarea className="w-full p-3 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500 resize-none h-40 text-sm" value={techDesign} onChange={e => setTechDesign(e.target.value)} placeholder="粘贴或输入技术方案内容..." />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">编程语言</label>
                  <select className="w-full p-2.5 border border-gray-200 rounded-lg focus:border-purple-500" value={language} onChange={e => setLanguage(e.target.value)}>
                    <option value="go">Go</option>
                    <option value="python">Python</option>
                    <option value="java">Java</option>
                  </select>
                </div>
                <div className="p-3 bg-purple-50 rounded-lg border border-purple-100">
                  <p className="text-xs font-medium text-purple-700 mb-1.5">生成内容包括：</p>
                  <ul className="text-xs text-purple-600 space-y-0.5">
                    <li>• Handler 层代码（路由处理）</li>
                    <li>• Service 层代码（业务逻辑）</li>
                    <li>• DAO 层代码（数据访问）</li>
                    <li>• Model 定义（结构体）</li>
                    <li>• 错误码定义</li>
                    <li>• 测试用例代码</li>
                  </ul>
                </div>
                <button onClick={sendMessage} disabled={loading || (!techDesign.trim() && !inputMessage.trim())} className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-2.5 px-4 rounded-lg hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all flex items-center justify-center">
                  {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />生成中...</> : <><Sparkles className="w-4 h-4 mr-2" />生成代码</>}
                </button>
                {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3"><AlertCircle className="w-4 h-4 text-red-600 inline mr-1.5" /><span className="text-red-700 text-sm">{error}</span></div>}
              </div>
            </div>
          </div>

          {/* Right Panel - Chat & Results */}
          <div className="lg:col-span-8 space-y-4">
            {/* Agent Selection Pills */}
            <div className="flex flex-wrap gap-2">
              {[{ name: '代码助手', icon: '🤖' }, { name: '架构师', icon: '🏗️' }, { name: '测试工程师', icon: '🧪' }].map(a => (
                <button key={a.name} onClick={() => selectAgent(a.name)} className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${currentAgent === a.name ? 'bg-purple-600 text-white shadow-md' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}>
                  {a.icon} {a.name}
                </button>
              ))}
            </div>

            {/* Chat Area */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col" style={{ height: 'calc(100vh - 280px)' }}>
              <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                <h2 className="text-base font-semibold text-gray-900 flex items-center">
                  <MessageSquare className="w-4 h-4 text-purple-600 mr-2" />
                  对话与结果
                </h2>
                <button onClick={() => messages.length > 0 && setMessages([])} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors" title="清空对话">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-400">
                    <Bot className="w-12 h-12 mb-3 opacity-40" />
                    <p className="text-sm font-medium">暂无对话记录</p>
                    <p className="text-xs mt-1">开始对话或点击"生成代码"</p>
                  </div>
                ) : messages.map((msg, idx) => (
                  <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-xl p-4 ${msg.role === 'user' ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-900'}`}>
                      {msg.image && <img src={msg.image} alt="Uploaded" className="max-w-full rounded-lg mb-2 max-h-24 object-contain" />}
                      <div className="prose prose-sm max-w-none">
                        {msg.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown> : <p className="whitespace-pre-wrap">{msg.content}</p>}
                      </div>
                      <div className={`text-xs mt-2 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-500'}`}>{new Date(msg.timestamp).toLocaleTimeString()}</div>
                      {msg.role === 'assistant' && (
                        <div className="flex space-x-2 mt-2 pt-2 border-t border-purple-200/30">
                          <button onClick={() => handleCopy(msg.content)} className="flex items-center px-2 py-1 bg-white/20 rounded text-xs hover:bg-white/30 transition-colors"><Copy className="w-3 h-3 mr-1" />复制</button>
                          <button onClick={() => handleDownload(msg.content, `code_${Date.now()}.go`)} className="flex items-center px-2 py-1 bg-white/20 rounded text-xs hover:bg-white/30 transition-colors"><Download className="w-3 h-3 mr-1" />下载</button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {loading && <div className="flex justify-start"><div className="bg-gray-100 rounded-xl p-3 flex items-center"><Loader2 className="w-4 h-4 animate-spin text-purple-600 mr-2" /><span className="text-sm text-gray-600">生成中...</span></div></div>}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Area */}
              <div className="border-t border-gray-200 bg-gray-50 p-4">
                {uploadedImage && <div className="mb-2 relative inline-block"><img src={uploadedImage} alt="Preview" className="h-12 rounded-lg border border-gray-200" /><button onClick={() => setUploadedImage(null)} className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white rounded-full flex items-center justify-center text-xs">×</button></div>}
                <div className="flex items-end space-x-2">
                  <button onClick={() => fileInputRef.current?.click()} className="p-2.5 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors" title="上传图片"><ImageIcon className="w-4 h-4" /></button>
                  <input ref={fileInputRef} type="file" accept="image/*" onChange={handleImageUpload} className="hidden" />
                  <textarea className="flex-1 p-2.5 border border-gray-200 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-500 resize-none text-sm bg-white" placeholder="输入消息... (Enter 发送，Shift+Enter 换行)" value={inputMessage} onChange={e => setInputMessage(e.target.value)} onKeyDown={handleKeyDown} rows={2} />
                  <button onClick={sendMessage} disabled={!inputMessage.trim() && !uploadedImage || loading} className="p-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"><Send className="w-4 h-4" /></button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
