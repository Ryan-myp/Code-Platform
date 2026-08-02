import React, { useState, useEffect, useRef } from 'react'
import {
  Languages, Play, Copy, Check, ArrowRightLeft, Clock, Upload, X,
  FileText, Globe, Scale, Stethoscope, BookOpen, Briefcase, Code2,
  Trash2, Sparkles, FileUp,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, Button, Empty, PageHeader } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const LANGS = ['中文', 'English', '日本語', '한국어', 'Français', 'Deutsch', 'Español', 'Русский', 'العربية', 'Português']

const DOMAINS = [
  { value: 'general', label: '通用', icon: Globe, desc: '日常文本翻译' },
  { value: 'tech', label: '技术文档', icon: Code2, desc: '技术术语精准' },
  { value: 'business', label: '商务', icon: Briefcase, desc: '商务沟通语境' },
  { value: 'legal', label: '法律', icon: Scale, desc: '法律术语严谨' },
  { value: 'medical', label: '医学', icon: Stethoscope, desc: '医学术语专业' },
  { value: 'literary', label: '文学', icon: BookOpen, desc: '文学风格优美' },
]

const STYLES = [
  { value: 'literal', label: '直译', desc: '忠实原文结构' },
  { value: 'free', label: '意译', desc: '自然流畅表达' },
  { value: 'localized', label: '本地化', desc: '适应目标文化' },
]

const TEMPLATES = [
  { name: '技术文档', icon: '💻', text: '请将以下技术文档翻译为目标语言，保持专业术语准确性，保留代码示例和格式：' },
  { name: '商务邮件', icon: '📧', text: '请将以下商务邮件翻译为目标语言，保持正式商务语气，注意礼仪用语：' },
  { name: '产品说明', icon: '📦', text: '请将以下产品说明翻译为目标语言，突出产品特性，用词简洁明了：' },
  { name: '合同条款', icon: '⚖️', text: '请将以下合同条款翻译为目标语言，确保法律术语准确，条款含义不变：' },
  { name: '营销内容', icon: '📢', text: '请将以下营销内容翻译为目标语言，保持吸引力，适应当地文化表达：' },
  { name: '学术论文', icon: '🎓', text: '请将以下学术内容翻译为目标语言，保持学术规范，引用格式不变：' },
]

export default function TranslationPage() {
  const toast = useToast()
  const [text, setText] = useState('')
  const [sourceLang, setSourceLang] = useState('中文')
  const [targetLang, setTargetLang] = useState('English')
  const [domain, setDomain] = useState('general')
  const [style, setStyle] = useState('free')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const fileInputRef = useRef(null)

  useEffect(() => { loadHistory() }, [])
  const loadHistory = async () => {
    try { const res = await api.get('/api/translation/history'); setHistory(res.data) } catch (e) {}
  }

  const translate = async () => {
    const finalText = fileContent || text
    if (!finalText.trim()) { toast.error('请输入翻译内容'); return }
    setLoading(true); setResult('')
    const domainMeta = DOMAINS.find(d => d.value === domain)
    const styleMeta = STYLES.find(s => s.value === style)
    try {
      const systemPrompt = `你是专业翻译，将以下内容从${sourceLang}翻译为${targetLang}。
领域：${domainMeta.label}（${domainMeta.desc}）
翻译风格：${styleMeta.label}（${styleMeta.desc}）
要求：保持原文格式，术语准确，表达自然流畅。只返回翻译结果。`
      const res = await api.post('/api/translation/translate', {
        source_lang: sourceLang, target_lang: targetLang, text: `${systemPrompt}\n\n${finalText}`
      })
      setResult(res.data.result); loadHistory(); toast.success('翻译完成')
    } catch (e) { toast.error(`翻译失败：${e.message}`) }
    finally { setLoading(false) }
  }

  const swapLangs = () => {
    setSourceLang(targetLang); setTargetLang(sourceLang)
    if (result) { setText(result); setResult('') }
  }

  const copyResult = () => {
    navigator.clipboard.writeText(result); setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const applyTemplate = (tpl) => {
    setText(tpl.text + '\n\n')
    toast.success(`已应用模板：${tpl.name}`)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) { toast.error('文件不能超过 10MB'); return }
    setUploadedFile(file)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await api.post('/api/tools/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setFileContent(res.data.content || '')
      toast.success(`已上传: ${file.name}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || '上传失败')
      setUploadedFile(null)
    }
  }

  const removeFile = () => {
    setUploadedFile(null); setFileContent('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const reuseHistory = (item) => {
    setText(item.source_text); setSourceLang(item.source_lang); setTargetLang(item.target_lang); setResult(item.result)
  }

  const deleteHistory = async (id, e) => {
    e.stopPropagation()
    try { await api.delete(`/api/translation/${id}`); loadHistory(); toast.success('已删除') } catch (e) {}
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 翻译中心"
        description="支持10种语言互译，6大领域专业翻译，直译/意译/本地化多风格"
        icon={Languages}
        iconColor="from-blue-500 to-indigo-600"
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '总翻译数', value: history.length, icon: FileText, color: 'from-blue-500 to-indigo-600' },
          { label: '语言对', value: `${new Set(history.map(h => `${h.source_lang}→${h.target_lang}`)).size}`, icon: Globe, color: 'from-purple-500 to-violet-600' },
          { label: '当前方向', value: `${sourceLang} → ${targetLang}`, icon: ArrowRightLeft, color: 'from-emerald-500 to-green-600' },
          { label: '支持语言', value: `${LANGS.length}种`, icon: Languages, color: 'from-amber-500 to-orange-600' },
        ].map((s, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center`}>
                <s.icon className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="text-xl font-bold text-gray-900">{s.value}</div>
                <div className="text-xs text-gray-500">{s.label}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：输入区 */}
        <div className="space-y-4">
          {/* 语言选择 + 领域 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Globe className="w-4 h-4 text-blue-500" /> 翻译设置
            </h3>
            {/* 语言方向 */}
            <div className="flex items-center gap-2 mb-4">
              <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none">
                {LANGS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
              <button onClick={swapLangs} className="p-2 hover:bg-gray-100 rounded-lg transition-colors" title="交换语言">
                <ArrowRightLeft className="w-4 h-4 text-gray-500" />
              </button>
              <select value={targetLang} onChange={(e) => setTargetLang(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none">
                {LANGS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            {/* 领域模式 */}
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-500 mb-1.5">翻译领域</label>
              <div className="grid grid-cols-3 gap-2">
                {DOMAINS.map(d => {
                  const Icon = d.icon
                  return (
                    <button key={d.value} onClick={() => setDomain(d.value)}
                      className={`flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs border transition-all ${
                        domain === d.value
                          ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium'
                          : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                      }`}>
                      <Icon className="w-3.5 h-3.5" />
                      {d.label}
                    </button>
                  )
                })}
              </div>
            </div>
            {/* 翻译风格 */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">翻译风格</label>
              <div className="grid grid-cols-3 gap-2">
                {STYLES.map(s => (
                  <button key={s.value} onClick={() => setStyle(s.value)}
                    className={`px-3 py-2 rounded-lg text-xs border transition-all text-center ${
                      style === s.value
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-medium'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}>
                    <div className="font-medium">{s.label}</div>
                    <div className="text-[10px] text-gray-400 mt-0.5">{s.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </Card>

          {/* 场景模板 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" /> 快捷模板
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {TEMPLATES.map((tpl, i) => (
                <button key={i} onClick={() => applyTemplate(tpl)}
                  className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left">
                  <span className="text-base">{tpl.icon}</span>
                  <span className="text-xs text-gray-700">{tpl.name}</span>
                </button>
              ))}
            </div>
          </Card>

          {/* 输入区 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-500" /> 原文
            </h3>
            <div className="space-y-3">
              {/* 文件上传 */}
              <div>
                {uploadedFile ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg">
                    <FileUp className="w-4 h-4 text-blue-600" />
                    <span className="flex-1 text-sm text-gray-700 truncate">{uploadedFile.name}</span>
                    <button onClick={removeFile} className="text-gray-400 hover:text-red-500"><X className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <label className="flex items-center justify-center gap-2 px-3 py-2 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-colors">
                    <Upload className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-500">上传文档翻译（.txt/.md/.docx）</span>
                    <input ref={fileInputRef} type="file" onChange={handleFileUpload}
                      accept=".txt,.md,.docx" className="hidden" />
                  </label>
                )}
              </div>
              <textarea value={text} onChange={(e) => setText(e.target.value)}
                placeholder="输入需要翻译的文本..."
                rows={8} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none" />
              <Button variant="primary" icon={Languages} loading={loading} onClick={translate} className="w-full">翻译</Button>
            </div>
          </Card>
        </div>

        {/* 右侧：结果区 */}
        <div className="space-y-4">
          <Card className="min-h-[400px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Languages className="w-4 h-4 text-blue-500" /> 翻译结果
              </h3>
              {result && (
                <Button variant="ghost" size="sm" icon={copied ? Check : Copy} onClick={copyResult}>
                  {copied ? '已复制' : '复制'}
                </Button>
              )}
            </div>
            {result ? (
              <div className="prose prose-sm max-w-none text-gray-700">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown>
              </div>
            ) : (
              <Empty icon={Languages} title="等待翻译" description="输入文本后点击翻译" />
            )}
          </Card>
        </div>
      </div>

      {/* 历史记录 */}
      {history.length > 0 && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" /> 翻译历史
          </h3>
          <div className="space-y-2">
            {history.slice(0, 10).map(item => (
              <div key={item.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                onClick={() => reuseHistory(item)}>
                <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded flex-shrink-0">
                  {item.source_lang} → {item.target_lang}
                </span>
                <span className="text-sm text-gray-700 truncate flex-1">{item.source_text?.slice(0, 60)}</span>
                <span className="text-xs text-gray-400 flex-shrink-0">{item.created_at?.slice(0, 16).replace('T', ' ')}</span>
                <button onClick={(e) => deleteHistory(item.id, e)}
                  className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors flex-shrink-0">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
