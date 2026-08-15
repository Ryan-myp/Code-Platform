import React, { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Card, Button, Badge, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import MarkdownRenderer from '../components/MarkdownRenderer'
import useQuota from '../hooks/useQuota'
import ShareButton from '../components/ShareButton'
import ExportButton from '../components/ExportButton'
import { TOOL_EXAMPLES } from '../lib/toolExamples'
import {
  ArrowLeft,
  Play,
  Copy,
  Check,
  Clock,
  History,
  Sparkles,
  FileText,
  ClipboardList,
  Mail,
  Target,
  Users,
  Heart,
  Video,
  Calendar,
  GraduationCap,
  BookOpen,
  GitBranch,
  Layers,
  Search,
  UserCircle,
  Megaphone,
  TrendingUp,
  BarChart,
  Settings,
  ChevronDown,
  Upload,
  X,
  Download,
  Zap,
  Lock,
  Crown,
} from 'lucide-react'

const ICON_MAP = {
  FileText,
  ClipboardList,
  Mail,
  Target,
  Users,
  Sparkles,
  Heart,
  Video,
  Calendar,
  GraduationCap,
  BookOpen,
  GitBranch,
  Layers,
  Search,
  UserCircle,
  Megaphone,
  TrendingUp,
  BarChart,
}

const CATEGORY_COLORS = {
  职场办公: 'from-blue-500 to-indigo-600',
  自媒体创作: 'from-pink-500 to-rose-600',
  学习研究: 'from-cyan-500 to-teal-600',
  '产品/营销': 'from-purple-500 to-violet-600',
  互联网行业: 'from-blue-500 to-cyan-600',
  传统行业: 'from-amber-500 to-orange-600',
  通用办公: 'from-gray-500 to-slate-600',
  专业工具: 'from-orange-500 to-red-600',
}

export default function ToolRunPage() {
  const { toolId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { quota } = useQuota()

  const [tool, setTool] = useState(null)
  const [input, setInput] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [copied, setCopied] = useState(false)
  const [params, setParams] = useState({})
  const [showParams, setShowParams] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [showExamples, setShowExamples] = useState(false)
  const fileInputRef = React.useRef(null)
  // 异步任务进度（后端 task 的 progress/stage 字段，轮询期间实时渲染）
  const [taskId, setTaskId] = useState(null)
  const [taskProgress, setTaskProgress] = useState(null)
  // 卸载后停止轮询，避免对已卸载组件 setState
  const mountedRef = React.useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const examples = TOOL_EXAMPLES[toolId] || []

  const applyExample = (example) => {
    setInput(example.input)
    setParams((prev) => ({ ...prev, ...(example.params || {}) }))
    setShowExamples(false)
    toast.success(`已填入示例「${example.label}」，直接点开始生成即可体验`)
  }

  useEffect(() => {
    loadTool()
    loadHistory()
  }, [toolId])

  useEffect(() => {
    if (tool?.params) {
      const defaults = {}
      Object.entries(tool.params).forEach(([key, config]) => {
        defaults[key] = config.default
      })
      setParams(defaults)
    }
  }, [tool])

  const loadTool = async () => {
    try {
      const res = await api.get(`/api/tools/${toolId}`)
      setTool(res.data)
    } catch {
      toast.error('工具不存在')
      navigate('/tool-hub')
    }
  }

  const loadHistory = async () => {
    try {
      const res = await api.get(`/api/tools/${toolId}/history`)
      setHistory(res.data)
    } catch {
      // ignore
    }
  }

  const handleRun = async () => {
    const finalInput = fileContent ? `${fileContent}\n\n${input}`.trim() : input.trim()
    if (!finalInput) {
      toast.warning('请输入内容或上传文件')
      return
    }
    setLoading(true)
    setResult('')
    setTaskId(null)
    setTaskProgress(null)
    try {
      const res = await api.post('/api/tools/run', {
        tool_id: toolId,
        input: finalInput,
        params,
      })
      if (res.data.task_id) {
        // 异步任务模式：慢 LLM（可达 5 分钟）不阻塞请求，轮询任务进度
        const id = res.data.task_id
        setTaskId(id)
        setTaskProgress({ pct: 0, stage: '任务已提交，等待执行' })
        for (let i = 0; i < 120; i += 1) {
          if (!mountedRef.current) return
          const t = await api.get(`/api/tasks/${id}`)
          if (!mountedRef.current) return
          setTaskProgress({ pct: t.data.progress || 0, stage: t.data.stage || '处理中...' })
          if (t.data.status === 'success') {
            setResult(t.data.result?.result || '')
            loadHistory()
            toast.success('生成完成')
            return
          }
          if (t.data.status === 'failed') {
            toast.error(t.data.error || '生成失败')
            return
          }
          await new Promise((r) => setTimeout(r, 3000))
        }
        toast.error('生成超时，请稍后在任务中心查看')
      } else if (res.data.result) {
        setResult(res.data.result)
        loadHistory()
        toast.success('生成完成')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || '生成失败')
    } finally {
      if (mountedRef.current) {
        setLoading(false)
        setTaskId(null)
        setTaskProgress(null)
      }
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(result)
    setCopied(true)
    toast.success('已复制')
    setTimeout(() => setCopied(false), 2000)
  }

  const handleUseHistory = (item) => {
    setInput(item.input_text || item.input)
    if (item.params) {
      setParams((prev) => ({ ...prev, ...item.params }))
    }
    setResult(item.result)
    setShowHistory(false)
  }

  const handleUseTemplate = (template) => {
    setSelectedTemplate(template.id)
    setInput(template.content)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const maxSize = 10 * 1024 * 1024 // 10MB
    if (file.size > maxSize) {
      toast.error('文件大小不能超过 10MB')
      return
    }

    setUploadedFile(file)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await api.post('/api/tools/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setFileContent(res.data.content)
      toast.success(`已上传: ${file.name}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || '上传失败')
      setUploadedFile(null)
    }
  }

  const handleRemoveFile = () => {
    setUploadedFile(null)
    setFileContent('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleParamChange = (key, value) => {
    setParams((prev) => ({ ...prev, [key]: value }))
  }

  if (!tool) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  // 锁定工具（需要会员等级）：展示会员引导页
  if (tool.locked) {
    const label = tool.requires === 'vip' ? '至尊会员' : '专业会员'
    return (
      <div className="flex-1 overflow-auto bg-gray-50">
        <div className="max-w-md mx-auto py-20 text-center">
          <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-glow">
            <Lock className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-ink-900 mb-2">
            「{tool.name}」为{label}专属
          </h2>
          <p className="text-sm text-ink-500 mb-8 leading-relaxed">
            开通会员即可使用该工具，同时解锁全部会员权益与更高额度。
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button variant="secondary" onClick={() => navigate('/tool-hub')}>
              <ArrowLeft className="w-4 h-4 mr-1.5" />
              返回工具库
            </Button>
            <Button onClick={() => navigate('/membership')}>
              <Crown className="w-4 h-4 mr-1.5" />
              立即开通
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const Icon = ICON_MAP[tool.icon] || Sparkles
  const categoryColor = CATEGORY_COLORS[tool.category] || 'from-gray-500 to-gray-600'
  const templates = tool.templates || []
  const toolParams = tool.params || {}

  return (
    <div className="flex-1 overflow-auto bg-gray-50 pb-16 md:pb-0">
      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* 头部 */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => navigate('/tool-hub')}
            className="w-10 h-10 rounded-lg border border-gray-200 flex items-center justify-center hover:bg-gray-50 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div
            className={`w-12 h-12 rounded-xl bg-gradient-to-br ${categoryColor} flex items-center justify-center`}
          >
            <Icon className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-bold text-gray-900">{tool.name}</h1>
            <p className="text-sm text-gray-500">{tool.description}</p>
          </div>
          <Badge variant="info">{tool.category}</Badge>
          {quota && (
            <Link
              to="/profile"
              title="查看额度详情"
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                quota.remaining_today >= 9999
                  ? 'text-amber-600 border-amber-200 bg-amber-50'
                  : quota.remaining_today <= 5
                    ? 'text-red-500 border-red-200 bg-red-50'
                    : 'text-brand-600 border-brand-200 bg-brand-50'
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              {quota.remaining_today >= 9999 ? '无限额度' : `剩余 ${quota.remaining_today} 次`}
            </Link>
          )}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
              showHistory ? 'bg-brand-50 text-brand-600' : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <History className="w-4 h-4" />
            历史
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：配置区 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 模板选择 */}
            {templates.length > 0 && (
              <Card>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <Layers className="w-4 h-4" />
                  快速模板
                </h3>
                <div className="flex flex-wrap gap-2">
                  {templates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => handleUseTemplate(t)}
                      className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                        selectedTemplate === t.id
                          ? 'bg-brand-500 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </Card>
            )}

            {/* 参数配置 */}
            {Object.keys(toolParams).length > 0 && (
              <Card>
                <button
                  onClick={() => setShowParams(!showParams)}
                  className="w-full flex items-center justify-between text-sm font-medium text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Settings className="w-4 h-4" />
                    高级选项
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 transition-transform ${showParams ? 'rotate-180' : ''}`}
                  />
                </button>
                {showParams && (
                  <div className="mt-4 space-y-3">
                    {Object.entries(toolParams).map(([key, config]) => (
                      <div key={key}>
                        <label className="block text-xs text-gray-500 mb-1">{config.label}</label>
                        {config.type === 'text' ? (
                          <input
                            type="text"
                            value={params[key] || config.default || ''}
                            placeholder={config.placeholder || ''}
                            onChange={(e) => handleParamChange(key, e.target.value)}
                            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                          />
                        ) : config.type === 'number' ? (
                          <input
                            type="number"
                            value={params[key] ?? config.default ?? ''}
                            min={config.min}
                            max={config.max}
                            onChange={(e) => handleParamChange(key, e.target.value)}
                            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                          />
                        ) : config.type === 'bool' ? (
                          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={Boolean(params[key] ?? config.default)}
                              onChange={(e) => handleParamChange(key, e.target.checked)}
                              className="w-4 h-4 accent-brand-500"
                            />
                            启用
                          </label>
                        ) : (
                          <select
                            value={params[key] || config.default}
                            onChange={(e) => handleParamChange(key, e.target.value)}
                            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                          >
                            {(config.options || []).map((opt) => (
                              <option key={opt} value={opt}>
                                {opt}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}

            {/* 历史记录 */}
            {showHistory && history.length > 0 && (
              <Card>
                <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  使用历史
                </h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {history.slice(0, 10).map((item) => (
                    <div
                      key={item.id}
                      onClick={() => handleUseHistory(item)}
                      className="p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors"
                    >
                      <div className="text-xs text-gray-400 mb-1">
                        {new Date(item.created_at).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-700 truncate">
                        {item.input_text || item.input}
                      </div>
                      {item.params && Object.keys(item.params).length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {Object.entries(item.params)
                            .slice(0, 3)
                            .map(([k, v]) => (
                              <span
                                key={k}
                                className="px-1.5 py-0.5 text-[10px] bg-gray-200 text-gray-600 rounded"
                              >
                                {v}
                              </span>
                            ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* 输入区（h-full 仅桌面多列时生效，窄屏单列下自适应内容高度，防止拉伸溢出遮挡按钮） */}
            <Card className="!p-0 overflow-hidden flex flex-col lg:h-full">
              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-700">输入内容</span>
                  {examples.length > 0 && (
                    <div className="relative">
                      <button
                        onClick={() => setShowExamples(!showExamples)}
                        className="flex items-center gap-1 px-2 py-0.5 text-xs text-brand-600 bg-brand-50 hover:bg-brand-100 rounded-full transition-colors"
                      >
                        <Sparkles className="w-3 h-3" />
                        试试示例
                        <ChevronDown
                          className={`w-3 h-3 transition-transform ${showExamples ? 'rotate-180' : ''}`}
                        />
                      </button>
                      {showExamples && (
                        <div className="absolute top-full left-0 mt-1 w-56 bg-white rounded-lg shadow-lg border border-gray-100 py-1 z-20">
                          {examples.map((example, i) => (
                            <button
                              key={i}
                              onClick={() => applyExample(example)}
                              className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 flex items-center gap-2 transition-colors"
                            >
                              <Sparkles className="w-3 h-3 text-brand-500 shrink-0" />
                              {example.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <span className="text-xs text-gray-400">{input.length} 字</span>
              </div>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={tool.placeholder || '请输入内容...'}
                className="flex-1 w-full px-4 py-3 text-sm text-gray-900 placeholder-gray-400 outline-none resize-none min-h-[200px]"
              />
              {/* 文件上传区域 */}
              <div className="px-4 py-3 border-t border-gray-100 bg-gray-50 space-y-2">
                {uploadedFile ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-brand-50 rounded-lg">
                    <FileText className="w-4 h-4 text-brand-600" />
                    <span className="flex-1 text-sm text-gray-700 truncate">
                      {uploadedFile.name}
                    </span>
                    <button onClick={handleRemoveFile} className="text-gray-400 hover:text-red-500">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <label className="flex items-center justify-center gap-2 px-3 py-2 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-brand-500 hover:bg-brand-50/50 transition-colors">
                    <Upload className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-500">上传文件（可选）</span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      onChange={handleFileUpload}
                      accept=".xlsx,.xls,.csv,.pdf,.txt,.doc,.docx,.md"
                      className="hidden"
                    />
                  </label>
                )}
                <Button onClick={handleRun} loading={loading} className="w-full" size="lg">
                  <Play className="w-4 h-4 mr-2" />
                  {loading ? '执行中...' : tool.type === 'compute' ? '执行计算' : '开始生成'}
                </Button>
              </div>
            </Card>
          </div>

          {/* 右侧：结果区 */}
          <div className="lg:col-span-2">
            <Card className="!p-0 overflow-hidden h-full flex flex-col min-h-[500px]">
              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">生成结果</span>
                {result && (
                  <div className="flex items-center gap-2">
                    <ShareButton content={result} title={`${tool.name} 生成结果`} />
                    <ExportButton
                      content={result}
                      title={`${tool.name}-${new Date().toISOString().slice(0, 10)}`}
                    />
                    <button
                      onClick={handleCopy}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-brand-600 hover:bg-gray-100 rounded transition-colors"
                    >
                      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      {copied ? '已复制' : '复制'}
                    </button>
                  </div>
                )}
              </div>
              <div className="flex-1 p-4 overflow-y-auto">
                {loading ? (
                  <div className="flex flex-col items-center justify-center h-full px-6">
                    {taskId ? (
                      <div className="w-full max-w-sm">
                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-brand-500 to-violet-500 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${Math.max(2, taskProgress?.pct || 0)}%` }}
                          />
                        </div>
                        <p className="mt-3 text-sm text-gray-600 text-center">
                          {taskProgress?.stage || '处理中...'}
                        </p>
                        <p className="mt-1 text-[11px] text-gray-400 text-center break-all">
                          任务 ID：{taskId}
                        </p>
                      </div>
                    ) : (
                      <>
                        <div className="animate-spin w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full mb-3" />
                        <p className="text-sm text-gray-500">AI 正在生成中...</p>
                      </>
                    )}
                  </div>
                ) : result ? (
                  <MarkdownRenderer content={result} />
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-gray-400">
                    <Sparkles className="w-12 h-12 mb-3 opacity-50" />
                    <p className="text-sm">点击「开始生成」查看结果</p>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
