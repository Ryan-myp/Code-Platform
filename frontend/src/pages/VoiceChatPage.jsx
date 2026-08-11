import React, { useState, useRef, useCallback, useEffect } from 'react'
import { Mic, MicOff, Volume2, Send, Trash2, Bot, User, Zap, Clock } from 'lucide-react'
import { Card, Button, Empty, PageHeader } from '../components/ui'
import { useToast } from '../lib/toast'
import api, { API_BASE } from '../lib/api'
import MarkdownRenderer from '../components/MarkdownRenderer'

export default function VoiceChatPage() {
  const toast = useRef(useToast()).current
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const recognitionRef = useRef(null)
  const chatRef = useRef(null)

  // 新消息/回复中自动滚动到底部
  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  // ── 浏览器语音识别 ──
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return

    const rec = new SpeechRecognition()
    rec.lang = 'zh-CN'
    rec.interimResults = true
    rec.continuous = false

    rec.onresult = (e) => {
      let final = ''
      for (let i = 0; i < e.results.length; i++) {
        final += e.results[i][0].transcript
      }
      setTranscript(final)
      if (e.results[0]?.isFinal) {
        setTranscript(final)
        handleSendRef.current(final)
      }
    }
    rec.onerror = (e) => {
      if (e.error !== 'no-speech') {
        toast.error(`语音识别失败：${e.error}`)
      }
      setListening(false)
    }
    rec.onend = () => setListening(false)

    recognitionRef.current = rec
  }, [])

  const toggleListening = useCallback(() => {
    const rec = recognitionRef.current
    if (!rec) {
      toast.error('您的浏览器不支持语音识别（请使用Chrome）')
      return
    }
    if (listening) {
      rec.stop()
      setListening(false)
    } else {
      setTranscript('')
      try {
        rec.start()
        setListening(true)
        toast.success('正在聆听...')
      } catch {
        toast.error('语音识别启动失败')
      }
    }
  }, [listening, toast])

  // ── 发送消息 ──
  const handleSend = useCallback(
    async (text) => {
      const msg = text || input.trim()
      if (!msg && !text) return

      const userMsg = { role: 'user', content: msg, time: new Date().toISOString() }
      setMessages((prev) => [...prev, userMsg])
      setInput('')
      setTranscript('')
      setLoading(true)

      try {
        const history = messages.slice(-10).map((m) => ({ role: m.role, content: m.content }))
        const res = await api.post('/api/voice-chat/respond', { message: msg, history })
        const aiMsg = { role: 'assistant', content: res.data.reply, time: new Date().toISOString() }
        setMessages((prev) => [...prev, aiMsg])

        // TTS 语音合成（如果后端支持）
        try {
          const ttsRes = await api.post('/api/voice-chat/tts', {
            text: res.data.reply,
            voice_id: 'zh-CN-XiaoxiaoNeural',
          })
          if (ttsRes.data.audio_url) {
            const audio = new Audio(
              ttsRes.data.audio_url.startsWith('http')
                ? ttsRes.data.audio_url
                : `${API_BASE}${ttsRes.data.audio_url}`
            )
            audio.play().catch(() => {})
          }
        } catch {
          // TTS 可选，失败不影响
        }
      } catch (e) {
        toast.error(`对话失败：${e.message}`)
      }
      setLoading(false)
    },
    [input, messages, toast]
  )

  // 语音识别回调通过 ref 转发到最新的 handleSend（避免识别 effect 捕获旧闭包）
  const handleSendRef = useRef(null)
  useEffect(() => {
    handleSendRef.current = handleSend
  }, [handleSend])

  const clearChat = () => setMessages([])

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI语音对话"
        description="浏览器原生语音识别 + AI智能回复 + 语音朗读，像和朋友聊天一样自然"
        icon={Mic}
        iconColor="from-blue-500 to-indigo-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：功能说明 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" /> 使用说明
            </h3>
            <div className="space-y-3 text-sm text-gray-600">
              <div className="flex gap-2">
                <span className="text-blue-500 font-bold">1.</span>
                <span>点击麦克风按钮开始说话</span>
              </div>
              <div className="flex gap-2">
                <span className="text-blue-500 font-bold">2.</span>
                <span>AI 自动识别并回复（文字+语音）</span>
              </div>
              <div className="flex gap-2">
                <span className="text-blue-500 font-bold">3.</span>
                <span>也可以直接输入文字对话</span>
              </div>
            </div>
            <div className="mt-3 p-3 bg-amber-50 rounded-lg text-xs text-amber-700">
              <strong>提示：</strong>语音识别需要 Chrome 浏览器，首次使用需授权麦克风权限。
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 对话统计
            </h3>
            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="p-3 bg-blue-50 rounded-lg">
                <div className="text-2xl font-bold text-blue-600">{messages.length}</div>
                <div className="text-xs text-gray-500 mt-1">消息总数</div>
              </div>
              <div className="p-3 bg-emerald-50 rounded-lg">
                <div className="text-2xl font-bold text-emerald-600">
                  {messages.filter((m) => m.role === 'assistant').length}
                </div>
                <div className="text-xs text-gray-500 mt-1">AI回复</div>
              </div>
            </div>
          </Card>
        </div>

        {/* 中/右侧：对话区 */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="flex flex-col" style={{ minHeight: '500px' }}>
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto space-y-3 mb-4 max-h-[500px] pr-2" ref={chatRef}>
              {messages.length === 0 ? (
                <Empty
                  icon={Mic}
                  title="开始语音对话"
                  description="点击下方麦克风按钮开始说话，或输入文字后发送"
                />
              ) : (
                messages.map((m, i) => (
                  <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
                    {m.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                    )}
                    <div
                      className={`max-w-[75%] p-3 rounded-2xl ${
                        m.role === 'user'
                          ? 'bg-violet-500 text-white rounded-br-md'
                          : 'bg-gray-100 text-gray-800 rounded-bl-md'
                      }`}
                    >
                      {m.role === 'user' ? (
                        <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                      ) : (
                        <MarkdownRenderer content={m.content} className="text-sm" />
                      )}
                      <div className="flex items-center justify-between mt-1">
                        <p
                          className={`text-[10px] ${m.role === 'user' ? 'text-white/60' : 'text-gray-400'}`}
                        >
                          {new Date(m.time).toLocaleTimeString('zh-CN', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                        {m.role === 'assistant' && (
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(m.content)
                              toast.success('已复制回复')
                            }}
                            className="text-[10px] text-gray-400 hover:text-blue-600 transition-colors"
                          >
                            复制
                          </button>
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
              {loading && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                  <div className="p-3 rounded-2xl bg-gray-100">
                    <div className="flex gap-1">
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: '0ms' }}
                      />
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
                </div>
              )}
            </div>

            {/* 输入区 */}
            <div className="border-t pt-3">
              {listening && transcript && (
                <div className="mb-2 p-2 bg-blue-50 rounded-lg text-sm text-blue-700 animate-pulse">
                  🎤 {transcript || '正在聆听...'}
                </div>
              )}
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleListening}
                  className={`p-3 rounded-xl transition-all ${
                    listening
                      ? 'bg-red-500 text-white animate-pulse'
                      : 'bg-gray-100 text-gray-600 hover:bg-blue-50 hover:text-blue-600'
                  }`}
                >
                  {listening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </button>
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder={listening ? '正在聆听...' : '输入文字对话，或点击麦克风语音输入...'}
                  className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading}
                  className="p-3 rounded-xl bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50 transition-colors"
                >
                  <Send className="w-5 h-5" />
                </button>
                {messages.length > 0 && (
                  <button
                    onClick={clearChat}
                    className="p-3 rounded-xl bg-gray-100 text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                )}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
