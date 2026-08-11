import React, { useState, useEffect, useRef } from 'react'
import {
  Languages,
  Play,
  Copy,
  Check,
  ArrowRightLeft,
  Clock,
  Upload,
  X,
  FileText,
  Globe,
  Scale,
  Stethoscope,
  BookOpen,
  Briefcase,
  Code2,
  Trash2,
  Sparkles,
  FileUp,
  Star,
  ListOrdered,
  BookMarked,
  Plus,
  Download,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ShareButton from '../components/ShareButton'
import ExportButton from '../components/ExportButton'
import { Card, Button, Empty, PageHeader, SkeletonList, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

const LANGS = [
  '中文',
  'English',
  '日本語',
  '한국어',
  'Français',
  'Deutsch',
  'Español',
  'Русский',
  'العربية',
  'Português',
]

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
  {
    name: '技术文档',
    icon: '💻',
    text: '请将以下技术文档翻译为目标语言，保持专业术语准确性，保留代码示例和格式：',
  },
  {
    name: '商务邮件',
    icon: '📧',
    text: '请将以下商务邮件翻译为目标语言，保持正式商务语气，注意礼仪用语：',
  },
  {
    name: '产品说明',
    icon: '📦',
    text: '请将以下产品说明翻译为目标语言，突出产品特性，用词简洁明了：',
  },
  {
    name: '合同条款',
    icon: '⚖️',
    text: '请将以下合同条款翻译为目标语言，确保法律术语准确，条款含义不变：',
  },
  {
    name: '营销内容',
    icon: '📢',
    text: '请将以下营销内容翻译为目标语言，保持吸引力，适应当地文化表达：',
  },
  {
    name: '学术论文',
    icon: '🎓',
    text: '请将以下学术内容翻译为目标语言，保持学术规范，引用格式不变：',
  },
]

export default function TranslationPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿）
  const [inputs, setInputs] = usePersistentToolState('translation_inputs', {
    text: '',
    sourceLang: '中文',
    targetLang: 'English',
    domain: 'general',
    style: 'free',
    useGlossary: true,
  })
  const { text, sourceLang, targetLang, domain, style, useGlossary } = inputs
  const setText = (v) => setInputs((p) => ({ ...p, text: v ?? '' }))
  const setSourceLang = (v) => setInputs((p) => ({ ...p, sourceLang: v }))
  const setTargetLang = (v) => setInputs((p) => ({ ...p, targetLang: v }))
  const setDomain = (v) => setInputs((p) => ({ ...p, domain: v }))
  const setStyle = (v) => setInputs((p) => ({ ...p, style: v }))
  const setUseGlossary = (v) => setInputs((p) => ({ ...p, useGlossary: v }))
  const [result, setResult] = useState('')
  const [task, setTask] = useState(null)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [batchMode, setBatchMode] = useState(false)
  const [batchTexts, setBatchTexts] = useState([''])
  const [batchResults, setBatchResults] = useState([])
  const [favorites, setFavorites] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('translation_favorites') || '[]')
    } catch {
      return []
    }
  })
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState(null)
  const [glossary, setGlossary] = useState([])
  const [glossarySource, setGlossarySource] = useState('')
  const [glossaryTarget, setGlossaryTarget] = useState('')
  const [exporting, setExporting] = useState('')
  const fileInputRef = useRef(null)

  useEffect(() => {
    loadHistory()
    loadGlossary()
  }, [])
  const loadGlossary = async () => {
    try {
      const res = await api.get('/api/translation/glossary')
      setGlossary(res.data || [])
    } catch {
      /* 未登录或异常时静默 */
    }
  }
  const addGlossary = async () => {
    const source = glossarySource.trim()
    const target = glossaryTarget.trim()
    if (!source || !target) {
      toast.error('请输入术语原文与指定译文')
      return
    }
    try {
      await api.post('/api/translation/glossary', { source_term: source, target_term: target })
      setGlossarySource('')
      setGlossaryTarget('')
      loadGlossary()
      toast.success('已添加术语')
    } catch (e) {
      toast.error(e.message)
    }
  }
  const deleteGlossary = async (id, e) => {
    e.stopPropagation()
    try {
      await api.delete(`/api/translation/glossary/${id}`)
      setGlossary((g) => g.filter((x) => x.id !== id))
      toast.success('已删除术语')
    } catch {
      /* 静默失败 */
    }
  }
  const exportBilingual = async (fmt) => {
    const source = batchMode
      ? batchResults.map((r) => r.original).join('\n')
      : fileContent || text
    const translation = batchMode
      ? batchResults.map((r) => r.translated).join('\n')
      : result
    if (!source.trim() || !translation.trim()) {
      toast.error('没有可导出的翻译结果')
      return
    }
    setExporting(fmt)
    try {
      const res = await api.post(
        '/api/translation/export',
        { source, translation, format: fmt },
        { responseType: 'blob' }
      )
      const blobUrl = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = `双语对照_${new Date().toISOString().slice(0, 10)}.${fmt}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(blobUrl), 3000)
      toast.success(`已导出双语对照 ${fmt.toUpperCase()}`)
    } catch (e) {
      toast.error(e.message || '导出失败')
    } finally {
      setExporting('')
    }
  }
  const loadHistory = async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const res = await api.get('/api/translation/history')
      setHistory(res.data)
    } catch (e) {
      setHistoryError(e.message)
    } finally {
      setHistoryLoading(false)
    }
  }

  const buildSystemPrompt = () => {
    const domainMeta = DOMAINS.find((d) => d.value === domain)
    const styleMeta = STYLES.find((s) => s.value === style)
    return `你是专业翻译，将以下内容从${sourceLang}翻译为${targetLang}。\n领域：${domainMeta.label}（${domainMeta.desc}）\n翻译风格：${styleMeta.label}（${styleMeta.desc}）\n要求：保持原文格式，术语准确，表达自然流畅。只返回翻译结果。`
  }

  const translate = async () => {
    const finalText = fileContent || text
    if (!finalText.trim()) {
      toast.error('请输入翻译内容')
      return
    }
    setResult('')
    await submitTask(
      '/api/translation/translate',
      {
        source_lang: sourceLang,
        target_lang: targetLang,
        text: `${buildSystemPrompt()}\n\n${finalText}`,
        use_glossary: useGlossary,
      },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setResult(data.result)
          setTask(null)
          loadHistory()
          toast.success('翻译完成')
        },
        onError: (e) => {
          setTask(null)
          toast.error(`翻译失败：${e.message}`)
        },
      }
    )
  }

  const swapLangs = () => {
    setSourceLang(targetLang)
    setTargetLang(sourceLang)
    if (result) {
      setText(result)
      setResult('')
    }
  }

  const copyResult = () => {
    const content = result || batchResults.map((r) => r.translated).join('\n\n---\n\n')
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const applyTemplate = (tpl) => {
    setText(tpl.text + '\n\n')
    toast.success(`已应用模板：${tpl.name}`)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) {
      toast.error('文件不能超过 10MB')
      return
    }
    setUploadedFile(file)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await api.post('/api/tools/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setFileContent(res.data.content || '')
      toast.success(`已上传: ${file.name}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || '上传失败')
      setUploadedFile(null)
    }
  }

  const removeFile = () => {
    setUploadedFile(null)
    setFileContent('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const reuseHistory = (item) => {
    setText(item.source_text)
    setSourceLang(item.source_lang)
    setTargetLang(item.target_lang)
    setResult(item.result)
  }

  const toggleFavorite = (item, e) => {
    e.stopPropagation()
    const isFav = favorites.some((f) => f.id === item.id)
    const next = isFav
      ? favorites.filter((f) => f.id !== item.id)
      : [
          ...favorites,
          {
            id: item.id,
            source_text: item.source_text,
            source_lang: item.source_lang,
            target_lang: item.target_lang,
            result: item.result,
            created_at: item.created_at,
          },
        ]
    setFavorites(next)
    localStorage.setItem('translation_favorites', JSON.stringify(next))
    toast.success(isFav ? '已取消收藏' : '已收藏')
  }

  const addBatchLine = () => setBatchTexts([...batchTexts, ''])
  const updateBatchLine = (idx, val) => {
    const next = [...batchTexts]
    next[idx] = val
    setBatchTexts(next)
  }
  const removeBatchLine = (idx) => setBatchTexts(batchTexts.filter((_, i) => i !== idx))

  const batchTranslate = async () => {
    const validTexts = batchTexts.filter((t) => t.trim())
    if (validTexts.length === 0) {
      toast.error('请输入至少一段翻译内容')
      return
    }
    setBatchResults([])
    const outputs = []
    for (let i = 0; i < validTexts.length; i++) {
      // 异步任务模式：每段独立任务，串行等待（受后端用户并发限制保护）
      await new Promise((resolve) => {
        submitTask(
          '/api/translation/translate',
          {
            source_lang: sourceLang,
            target_lang: targetLang,
            text: `${buildSystemPrompt()}\n\n${validTexts[i]}`,
            use_glossary: useGlossary,
          },
          {
            onUpdate: (t) => setTask({ ...t, batchIndex: i + 1, batchTotal: validTexts.length }),
            onSuccess: (data) => {
              outputs.push({ original: validTexts[i], translated: data.result })
              resolve()
            },
            onError: () => {
              outputs.push({ original: validTexts[i], translated: '' })
              resolve()
            },
          }
        )
      })
    }
    setTask(null)
    setBatchResults(outputs)
    loadHistory()
    const failed = outputs.filter((o) => !o.translated).length
    toast.success(
      failed
        ? `批量翻译完成（${outputs.length - failed}成功/${failed}失败）`
        : `批量翻译完成（${outputs.length}段）`
    )
  }

  const deleteHistory = async (id, e) => {
    e.stopPropagation()
    try {
      await api.delete(`/api/translation/${id}`)
      loadHistory()
      toast.success('已删除')
    } catch {
      /* 静默失败，不阻塞 UI */
    }
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
          {
            label: '总翻译数',
            value: history.length,
            icon: FileText,
            color: 'from-blue-500 to-indigo-600',
          },
          {
            label: '语言对',
            value: `${new Set(history.map((h) => `${h.source_lang}→${h.target_lang}`)).size}`,
            icon: Globe,
            color: 'from-purple-500 to-violet-600',
          },
          {
            label: '当前方向',
            value: `${sourceLang} → ${targetLang}`,
            icon: ArrowRightLeft,
            color: 'from-emerald-500 to-green-600',
          },
          {
            label: '支持语言',
            value: `${LANGS.length}种`,
            icon: Languages,
            color: 'from-amber-500 to-orange-600',
          },
        ].map((s, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center`}
              >
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：输入区 */}
        <div className="space-y-4">
          {/* 语言选择 + 领域 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Globe className="w-4 h-4 text-blue-500" /> 翻译设置
            </h3>
            {/* 语言方向 */}
            <div className="flex items-center gap-2 mb-4">
              <select
                value={sourceLang}
                onChange={(e) => setSourceLang(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              >
                {LANGS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
              <button
                onClick={swapLangs}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                title="交换语言"
              >
                <ArrowRightLeft className="w-4 h-4 text-gray-500" />
              </button>
              <select
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              >
                {LANGS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            {/* 领域模式 */}
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-500 mb-1.5">翻译领域</label>
              <div className="grid grid-cols-2 gap-2">
                {DOMAINS.map((d) => {
                  const Icon = d.icon
                  return (
                    <button
                      key={d.value}
                      onClick={() => setDomain(d.value)}
                      className={`flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs border transition-all ${
                        domain === d.value
                          ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium'
                          : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                      }`}
                    >
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
              <div className="grid grid-cols-2 gap-2">
                {STYLES.map((s) => (
                  <button
                    key={s.value}
                    onClick={() => setStyle(s.value)}
                    className={`px-3 py-2 rounded-lg text-xs border transition-all text-center ${
                      style === s.value
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-medium'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-medium">{s.label}</div>
                    <div className="text-[10px] text-gray-400 mt-0.5">{s.desc}</div>
                  </button>
                ))}
              </div>
            </div>
            {/* 术语表开关 */}
            <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useGlossary}
                  onChange={(e) => setUseGlossary(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-xs font-medium text-gray-600">应用我的术语表</span>
              </label>
              <span className="text-[10px] text-gray-400">最多50条 · 最高优先级</span>
            </div>
          </Card>

          {/* 场景模板 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" /> 快捷模板
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {TEMPLATES.map((tpl, i) => (
                <button
                  key={i}
                  onClick={() => applyTemplate(tpl)}
                  className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left"
                >
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
                    <span className="flex-1 text-sm text-gray-700 truncate">
                      {uploadedFile.name}
                    </span>
                    <button onClick={removeFile} className="text-gray-400 hover:text-red-500">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label className="flex items-center justify-center gap-2 px-3 py-2 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-colors">
                    <Upload className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-500">上传文档翻译（.txt/.md/.docx）</span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      onChange={handleFileUpload}
                      accept=".txt,.md,.docx"
                      className="hidden"
                    />
                  </label>
                )}
              </div>
              {/* 批量模式开关 */}
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={batchMode}
                    onChange={(e) => setBatchMode(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-xs font-medium text-gray-600 flex items-center gap-1">
                    <ListOrdered className="w-3 h-3" /> 批量翻译模式
                  </span>
                </label>
                <span className="text-xs text-gray-400">
                  {batchMode ? `${batchTexts.filter((t) => t.trim()).length} 段待翻译` : '单段翻译'}
                </span>
              </div>

              {batchMode ? (
                <div className="space-y-2">
                  {batchTexts.map((t, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="text-xs text-gray-400 mt-2 flex-shrink-0 w-5 text-right">
                        {i + 1}.
                      </span>
                      <textarea
                        value={t}
                        onChange={(e) => updateBatchLine(i, e.target.value)}
                        placeholder={`第${i + 1}段文本...`}
                        rows={2}
                        className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                      />
                      {batchTexts.length > 1 && (
                        <button
                          onClick={() => removeBatchLine(i)}
                          className="p-1 text-gray-400 hover:text-red-500 mt-1"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                  <button
                    onClick={addBatchLine}
                    className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 ml-7"
                  >
                    <Plus className="w-3 h-3" /> 添加一段
                  </button>
                  <Button
                    variant="primary"
                    icon={Languages}
                    loading={!!task}
                    onClick={batchTranslate}
                    className="w-full"
                  >
                    批量翻译（{batchTexts.filter((t) => t.trim()).length}段）
                  </Button>
                  {task?.batchTotal > 1 && (
                    <div className="w-full">
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                        <span>
                          第 {task.batchIndex}/{task.batchTotal} 段 · {task.stage || '处理中…'}
                        </span>
                        <span>{task.progress || 0}%</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-300"
                          style={{ width: `${task.progress || 0}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="输入需要翻译的文本..."
                    rows={8}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                  />
                  <Button
                    variant="primary"
                    icon={Languages}
                    loading={!!task}
                    onClick={translate}
                    className="w-full"
                  >
                    翻译
                  </Button>
                  {task && !task.batchTotal && (
                    <div className="w-full">
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                        <span>{task.stage || '处理中…'}</span>
                        <span>{task.progress || 0}%</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-300"
                          style={{ width: `${task.progress || 0}%` }}
                        />
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </Card>
        </div>

        {/* 右侧：结果区 */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="min-h-[400px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Languages className="w-4 h-4 text-blue-500" />{' '}
                {batchMode ? '批量翻译结果' : '翻译结果'}
              </h3>
              {(result || batchResults.length > 0) && (
                <div className="flex items-center gap-2 flex-wrap">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Download}
                    loading={exporting === 'md'}
                    onClick={() => exportBilingual('md')}
                    title="双语对照导出 Markdown"
                  >
                    对照MD
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={FileText}
                    loading={exporting === 'docx'}
                    onClick={() => exportBilingual('docx')}
                    title="双语对照导出 Word"
                  >
                    对照Word
                  </Button>
                  <ExportButton
                    content={
                      result ||
                      batchResults.map((r) => `**${r.original}**\n\n${r.translated}`).join('\n\n---\n\n')
                    }
                    title="翻译结果"
                  />
                  <ShareButton
                    content={
                      result ||
                      batchResults
                        .map((r) => `**${r.original}**\n\n${r.translated}`)
                        .join('\n\n---\n\n')
                    }
                    title="翻译结果"
                    contentType="translation"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={copied ? Check : Copy}
                    onClick={copyResult}
                  >
                    {copied ? '已复制' : '复制'}
                  </Button>
                </div>
              )}
            </div>
            {batchMode && batchResults.length > 0 ? (
              <div className="space-y-3">
                {batchResults.map((r, i) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-blue-600 font-medium mb-1">第{i + 1}段</div>
                    <MarkdownRenderer content={r} />
                  </div>
                ))}
              </div>
            ) : result ? (
              <MarkdownRenderer content={result} />
            ) : (
              <Empty icon={Languages} title="等待翻译" description="输入文本后点击翻译" />
            )}
          </Card>

          {/* 我的术语表（v15：用户自定义，翻译时强制应用） */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <BookMarked className="w-4 h-4 text-blue-500" /> 我的术语表
              <span className="text-[10px] font-normal text-gray-400 ml-auto">
                {glossary.length}/50 条 · 强制应用
              </span>
            </h3>
            {/* 添加表单 */}
            <div className="flex gap-2 mb-3">
              <input
                value={glossarySource}
                onChange={(e) => setGlossarySource(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addGlossary()}
                placeholder="术语原文，如：大模型"
                className="flex-1 min-w-0 px-2.5 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <input
                value={glossaryTarget}
                onChange={(e) => setGlossaryTarget(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addGlossary()}
                placeholder="指定译文，如：LLM"
                className="flex-1 min-w-0 px-2.5 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <Button variant="primary" size="sm" icon={Plus} onClick={addGlossary}>
                添加
              </Button>
            </div>
            {glossary.length > 0 ? (
              <div className="max-h-44 overflow-y-auto space-y-1 pr-1">
                {glossary.map((g) => (
                  <div
                    key={g.id}
                    className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <span className="text-xs text-gray-700 font-medium">{g.source_term}</span>
                    <span className="text-gray-400 text-xs">→</span>
                    <span className="text-xs text-blue-600 flex-1 truncate">{g.target_term}</span>
                    <button
                      onClick={(e) => deleteGlossary(g.id, e)}
                      className="p-0.5 text-gray-400 hover:text-red-500 rounded transition-colors"
                      title="删除术语"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                icon={BookMarked}
                title="还没有自定义术语"
                description="添加专属术语，翻译时将自动强制应用"
                className="py-6"
              />
            )}
            {/* 内置常用术语参考 */}
            <details className="mt-3 pt-3 border-t border-gray-100">
              <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 select-none">
                内置常用术语参考（8条）
              </summary>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs mt-2">
                {[
                  { zh: '人工智能', en: 'Artificial Intelligence (AI)' },
                  { zh: '机器学习', en: 'Machine Learning' },
                  { zh: '深度学习', en: 'Deep Learning' },
                  { zh: '自然语言处理', en: 'Natural Language Processing (NLP)' },
                  { zh: '大数据', en: 'Big Data' },
                  { zh: '云计算', en: 'Cloud Computing' },
                  { zh: '区块链', en: 'Blockchain' },
                  { zh: '物联网', en: 'Internet of Things (IoT)' },
                ].map((term, i) => (
                  <div key={i} className="flex items-center gap-1 py-1 border-b border-gray-100">
                    <span className="text-gray-700 font-medium">{term.zh}</span>
                    <span className="text-gray-400">→</span>
                    <span className="text-blue-600">{term.en}</span>
                  </div>
                ))}
              </div>
            </details>
          </Card>
        </div>
      </div>

      {/* 历史记录 */}
      {historyLoading ? (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" /> 翻译历史
          </h3>
          <SkeletonList count={3} />
        </Card>
      ) : historyError ? (
        <Card>
          <ErrorState message={`历史加载失败：${historyError}`} onRetry={loadHistory} />
        </Card>
      ) : (
        history.length > 0 && (
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" /> 翻译历史
            </h3>
            <div className="space-y-2">
              {history.slice(0, 10).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                  onClick={() => reuseHistory(item)}
                >
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded flex-shrink-0">
                    {item.source_lang} → {item.target_lang}
                  </span>
                  <span className="text-sm text-gray-700 truncate flex-1">
                    {item.source_text?.slice(0, 60)}
                  </span>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {item.created_at?.slice(0, 16).replace('T', ' ')}
                  </span>
                  <button
                    onClick={(e) => toggleFavorite(item, e)}
                    className={`p-1 rounded transition-colors flex-shrink-0 ${favorites.some((f) => f.id === item.id) ? 'text-amber-500' : 'text-gray-300 hover:text-amber-400'}`}
                    title="收藏"
                  >
                    <Star
                      className="w-3.5 h-3.5"
                      fill={favorites.some((f) => f.id === item.id) ? 'currentColor' : 'none'}
                    />
                  </button>
                  <button
                    onClick={(e) => deleteHistory(item.id, e)}
                    className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors flex-shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </Card>
        )
      )}
    </div>
  )
}
