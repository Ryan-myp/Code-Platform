import React, { useState, useEffect, useRef } from 'react'
import {
  Table2,
  Play,
  Clock,
  Copy,
  Check,
  FileSpreadsheet,
  Upload,
  X,
  FileText,
  BarChart3,
  TrendingUp,
  PieChart,
  Calculator,
  Eraser,
  Sparkles,
  Trash2,
  Lightbulb,
  Download,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ShareButton from '../components/ShareButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import RandomPromptButton from '../components/RandomPromptButton'
import { Card, Button, Empty, PageHeader, SkeletonList, ErrorState, Badge } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const RANDOM_FORMULAS = [
  '根据 A 列销售额计算提成：10 万以下 5%，10-50 万 8%，50 万以上 12%',
  '统计 B 列中重复出现的值并标记出现次数',
  '根据入职日期计算工龄，满一年显示“满X年”',
  '把 C 列混合格式的日期统一为 YYYY-MM-DD 并计算与今天的差值天数',
  '按部门汇总 D 列金额，生成部门-金额对照表',
  '从 E 列身份证号中提取出生日期和性别',
  '计算 A 列库存量与 B 列安全库存的差值，低于安全线标红预警',
  '按季度统计销售额环比增长率，并用条件格式标出增长超过 20% 的季度',
  '将 A 列手机号脱敏为 138****1234 格式',
  '计算员工 A 列的加班时长，按 1.5 倍折算调休天数',
]

const OPERATIONS = [
  { value: 'analyze', label: '数据分析', icon: BarChart3, desc: 'AI 分析数据，给出洞察和建议' },
  { value: 'formula', label: '公式生成', icon: Calculator, desc: '根据需求生成 Excel 公式（附参数表）' },
  { value: 'create', label: '数据创建', icon: FileSpreadsheet, desc: '创建结构化数据表格' },
  { value: 'clean', label: '数据清洗', icon: Eraser, desc: '去重、格式化、异常值处理' },
  {
    value: 'outliers',
    label: '异常检测',
    icon: AlertTriangle,
    desc: 'IQR 法检测数值列异常值（无需 AI，秒级返回）',
  },
]

const QUICK_TEMPLATES = [
  {
    name: '销售数据分析',
    icon: '📊',
    op: 'analyze',
    prompt: '请分析以下销售数据，找出销售趋势、TOP产品、区域差异，并给出提升建议',
  },
  {
    name: '用户行为分析',
    icon: '👥',
    op: 'analyze',
    prompt: '请分析用户行为数据，包括活跃度、留存率、转化漏斗，并给出优化建议',
  },
  {
    name: '财务报表分析',
    icon: '💰',
    op: 'analyze',
    prompt: '请分析以下财务数据，计算关键财务指标，评估经营状况并给出建议',
  },
  {
    name: 'VLOOKUP匹配',
    icon: '🔍',
    op: 'formula',
    prompt: '需要根据A列的产品编码，从另一个表中匹配对应的产品名称和价格',
  },
  {
    name: '条件汇总',
    icon: '📋',
    op: 'formula',
    prompt: '需要按月份和部门汇总销售额，计算平均值、最大值、最小值',
  },
  {
    name: '数据去重清洗',
    icon: '🧹',
    op: 'clean',
    prompt: '请检查数据中的重复行、空值、异常值，并给出清洗方案',
  },
  {
    name: '人事考勤统计',
    icon: '⏰',
    op: 'analyze',
    prompt: '请分析考勤数据，统计出勤率、迟到早退频次、加班时长，并识别考勤异常员工',
  },
  {
    name: '库存周转分析',
    icon: '📦',
    op: 'analyze',
    prompt: '请分析库存数据，计算周转率、滞销占比、缺货风险，并给出补货建议',
  },
  {
    name: '成绩统计',
    icon: '📝',
    op: 'create',
    prompt: '根据各科成绩生成统计表：总分、排名、平均分、优秀率、及格率、分数段分布',
  },
  {
    name: '销售提成计算',
    icon: '💸',
    op: 'formula',
    prompt: '需要按阶梯比例计算提成：销售额 10 万以下 5%，10-50 万 8%，50 万以上 12%',
  },
  {
    name: '多表合并',
    icon: '🔗',
    op: 'formula',
    prompt: '需要把多个分部门的销售表按产品编码合并成一张总表，并汇总金额',
  },
]

export default function ExcelPage() {
  const toast = useToast()
  const [operation, setOperation] = useState('analyze')
  const [prompt, setPrompt] = useState('')
  const [dataInput, setDataInput] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [previewData, setPreviewData] = useState(null)
  const [formulaData, setFormulaData] = useState(null)
  const [outlierData, setOutlierData] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    loadHistory()
  }, [])
  const loadHistory = async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const res = await api.get('/api/excel/history')
      setHistory(res.data)
    } catch (e) {
      setHistoryError(e.message)
    } finally {
      setHistoryLoading(false)
    }
  }

  const execute = async () => {
    const finalInput = fileContent || dataInput || prompt
    if (!prompt.trim() && !finalInput.trim()) {
      toast.error('请输入内容或上传文件')
      return
    }
    setLoading(true)
    setResult('')
    try {
      let data = {}
      if (operation === 'analyze') {
        data = { raw: finalInput, prompt }
      } else if (operation === 'formula') {
        data = { prompt: prompt || finalInput }
      } else if (operation === 'outliers') {
        data = { raw: finalInput }
      } else {
        data = { content: finalInput, prompt }
      }
      const res = await api.post('/api/excel/operate', {
        operation,
        title: (prompt || dataInput || '').slice(0, 50) || uploadedFile?.name || '未命名',
        data,
      })
      setResult(res.data.result)
      // 结构化结果解析：formula（参数表）/ outliers（异常可视化），失败回退 markdown
      if (operation === 'formula') {
        try {
          setFormulaData(JSON.parse(res.data.result))
        } catch {
          setFormulaData(null)
        }
      } else {
        setFormulaData(null)
      }
      if (operation === 'outliers') {
        try {
          setOutlierData(JSON.parse(res.data.result))
        } catch {
          setOutlierData(null)
        }
      } else {
        setOutlierData(null)
      }
      loadHistory()
      toast.success('操作完成')
    } catch (e) {
      toast.error(`操作失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const copyResult = () => {
    navigator.clipboard.writeText(result)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const parsePreview = (content) => {
    if (!content) return null
    const lines = content.split('\n').filter((l) => l.trim())
    if (lines.length === 0) return null
    const delimiter = lines[0].includes('\t') ? '\t' : lines[0].includes(',') ? ',' : /\s{2,}/
    const headers = lines[0].split(delimiter).map((h) => h.trim())
    const rows = lines.slice(1, 11).map((l) => l.split(delimiter).map((c) => c.trim()))
    return { headers, rows }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const maxSize = 10 * 1024 * 1024
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
      const content = res.data.content || ''
      setFileContent(content)
      setDataInput(content)
      setPreviewData(parsePreview(content))
      toast.success(`已上传: ${file.name}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || '上传失败')
      setUploadedFile(null)
    }
  }

  const handleRemoveFile = () => {
    setUploadedFile(null)
    setFileContent('')
    setDataInput('')
    setPreviewData(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const applyQuickTemplate = (tpl) => {
    setOperation(tpl.op)
    setPrompt(tpl.prompt)
    toast.success(`已应用模板：${tpl.name}`)
  }

  const reuseHistory = (item) => {
    setOperation(item.operation)
    setResult(item.result)
    if (item.prompt) setPrompt(item.prompt)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Excel 智能助手"
        description="AI 数据分析、公式生成、数据清洗、表格创建"
        icon={Table2}
        iconColor="from-green-500 to-emerald-600"
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: '总操作数',
            value: history.length,
            icon: Table2,
            color: 'from-green-500 to-emerald-600',
          },
          {
            label: '本周使用',
            value: history.filter((h) => new Date() - new Date(h.created_at) < 7 * 86400000).length,
            icon: Sparkles,
            color: 'from-purple-500 to-indigo-600',
          },
          {
            label: '操作类型',
            value: `${OPERATIONS.length}种`,
            icon: Calculator,
            color: 'from-blue-500 to-cyan-600',
          },
          {
            label: '快速模板',
            value: QUICK_TEMPLATES.length,
            icon: FileText,
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

      {/* 快速模板 */}
      <Card>
        <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-500" /> 快速模板
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
          {QUICK_TEMPLATES.map((tpl, i) => (
            <button
              key={i}
              onClick={() => applyQuickTemplate(tpl)}
              className="flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg border border-gray-200 hover:border-green-300 hover:bg-green-50/50 transition-all"
            >
              <span className="text-lg">{tpl.icon}</span>
              <span className="text-xs text-gray-700 text-center">{tpl.name}</span>
            </button>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：操作区 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Table2 className="w-4 h-4 text-green-600" /> 操作面板
            </h3>
            <div className="space-y-4">
              {/* 操作类型 */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">操作类型</label>
                <div className="grid grid-cols-2 gap-2">
                  {OPERATIONS.map((op) => {
                    const Icon = op.icon
                    return (
                      <button
                        key={op.value}
                        onClick={() => setOperation(op.value)}
                        className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg text-xs border transition-all ${
                          operation === op.value
                            ? 'bg-green-50 border-green-300 text-green-700 font-medium'
                            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        {op.label}
                      </button>
                    )
                  })}
                </div>
                <p className="text-xs text-gray-400 mt-1.5">
                  {OPERATIONS.find((o) => o.value === operation)?.desc}
                </p>
              </div>

              {/* 输入 */}
              {operation === 'formula' ? (
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center justify-between">
                    <span>公式需求</span>
                    <div className="flex items-center gap-3">
                      <RandomPromptButton
                        prompts={RANDOM_FORMULAS}
                        onPick={(t) => setPrompt(t)}
                        className="text-green-500 hover:text-green-700"
                      />
                      <EnhancePromptButton
                        text={prompt}
                        onEnhance={(t) => setPrompt(t)}
                        style="excel"
                        className="text-green-600 hover:text-green-700"
                      />
                    </div>
                  </label>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="例如：根据A列的销售额计算提成，阶梯比例：10万以下5%，10-50万8%，50万以上12%"
                    rows={5}
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !loading) {
                        e.preventDefault()
                        execute()
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-green-500/20 focus:border-green-500 outline-none"
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">数据/内容</label>
                  {/* 文件上传 */}
                  <div className="mb-3">
                    {uploadedFile ? (
                      <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
                        <FileText className="w-4 h-4 text-green-600" />
                        <span className="flex-1 text-sm text-gray-700 truncate">
                          {uploadedFile.name}
                        </span>
                        <button
                          onClick={handleRemoveFile}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <label className="flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-green-500 hover:bg-green-50/50 transition-colors">
                        <Upload className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-500">上传 Excel / CSV 文件</span>
                        <input
                          ref={fileInputRef}
                          type="file"
                          onChange={handleFileUpload}
                          accept=".xlsx,.xls,.csv"
                          className="hidden"
                        />
                      </label>
                    )}
                  </div>
                  <textarea
                    value={dataInput || prompt}
                    onChange={(e) => setDataInput(e.target.value)}
                    placeholder={
                      operation === 'analyze'
                        ? '粘贴 Excel 数据（可用 Tab 或逗号分隔）或上传文件...'
                        : '输入需要创建的数据...'
                    }
                    rows={5}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-green-500/20 focus:border-green-500 outline-none font-mono"
                  />
                </div>
              )}

              {/* 补充说明 */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  补充说明（可选）
                </label>
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="对分析/操作的额外要求..."
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-green-500/20 focus:border-green-500 outline-none"
                />
              </div>

              <Button
                variant="success"
                icon={Play}
                loading={loading}
                onClick={execute}
                className="w-full"
              >
                执行
              </Button>
            </div>
          </Card>
        </div>

        {/* 右侧：结果区 */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="min-h-[300px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-green-600" /> 结果
              </h3>
              {result && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Download}
                    onClick={() => {
                      const blob = new Blob([result], { type: 'text/markdown;charset=utf-8' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `Excel处理结果_${new Date().toISOString().slice(0, 10)}.md`
                      a.click()
                      URL.revokeObjectURL(url)
                      toast.success('结果已导出')
                    }}
                  >
                    导出
                  </Button>
                  <ShareButton content={result} title="Excel 处理结果" contentType="excel" />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={copied ? Check : Copy}
                    onClick={copyResult}
                  >
                    {copied ? '已复制' : '复制'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={RefreshCw}
                    loading={loading}
                    onClick={execute}
                  >
                    重新执行
                  </Button>
                </div>
              )}
            </div>
            {result ? (
              operation === 'formula' && formulaData ? (
                <div className="space-y-3">
                  {/* 推荐公式 */}
                  <div className="p-3 rounded-lg bg-green-50 border border-green-200">
                    <div className="text-xs text-green-700 font-medium mb-1">推荐公式</div>
                    <code className="block font-mono text-sm text-green-900 break-all">
                      {formulaData.formula}
                    </code>
                  </div>
                  {formulaData.description && (
                    <p className="text-sm text-gray-600">{formulaData.description}</p>
                  )}
                  {/* 参数说明表 */}
                  {formulaData.params?.length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-500 mb-1.5">参数说明表</div>
                      <div className="overflow-x-auto rounded-lg border">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-gray-50">
                              <th className="px-2 py-1.5 text-left font-medium text-gray-600 border-b">
                                参数
                              </th>
                              <th className="px-2 py-1.5 text-left font-medium text-gray-600 border-b">
                                含义
                              </th>
                              <th className="px-2 py-1.5 text-left font-medium text-gray-600 border-b">
                                示例
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {formulaData.params.map((p, i) => (
                              <tr key={i} className="hover:bg-gray-50">
                                <td className="px-2 py-1.5 font-mono text-green-700 border-b border-gray-100">
                                  {p.name}
                                </td>
                                <td className="px-2 py-1.5 text-gray-700 border-b border-gray-100">
                                  {p.meaning}
                                </td>
                                <td className="px-2 py-1.5 text-gray-500 border-b border-gray-100">
                                  {p.example}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  {/* 计算逻辑 */}
                  {formulaData.logic?.length > 0 && (
                    <div className="p-3 rounded-lg bg-gray-50 text-sm">
                      <div className="text-xs font-medium text-gray-500 mb-1">计算逻辑</div>
                      <ol className="list-decimal list-inside space-y-0.5 text-gray-600 text-xs">
                        {formulaData.logic.map((l, i) => (
                          <li key={i}>{l}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                  {/* 使用场景 */}
                  {formulaData.scenarios && (
                    <div className="text-xs text-gray-600 bg-blue-50 border border-blue-100 rounded-lg p-3">
                      {formulaData.scenarios}
                    </div>
                  )}
                  {/* 替代方案 */}
                  {formulaData.alternatives?.length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-500 mb-1.5">替代方案</div>
                      {formulaData.alternatives.map((a, i) => (
                        <div
                          key={i}
                          className="p-2 rounded-lg border text-xs mb-1.5 flex flex-wrap items-baseline gap-2"
                        >
                          <code className="font-mono text-green-700">{a.formula}</code>
                          <span className="text-gray-500">{a.scenario}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* 常见陷阱 */}
                  {formulaData.pitfalls && (
                    <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg p-3">
                      <AlertTriangle className="w-3.5 h-3.5 inline mr-1" />
                      {formulaData.pitfalls}
                    </div>
                  )}
                </div>
              ) : operation === 'outliers' && outlierData ? (
                <div className="space-y-3">
                  {!outlierData.success ? (
                    <div className="text-amber-700 text-sm">{outlierData.message}</div>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge color={outlierData.columns?.length > 0 ? 'red' : 'green'}>
                          {outlierData.summary}
                        </Badge>
                        <span className="text-xs text-gray-400">{outlierData.method}</span>
                      </div>
                      {outlierData.columns?.length === 0 ? (
                        <Empty
                          icon={CheckCircle2}
                          title="未发现异常值"
                          description="所有数值列均落在正常范围内"
                        />
                      ) : (
                        outlierData.columns?.map((col, i) => (
                          <div key={i} className="p-3 rounded-lg border">
                            <div className="flex flex-wrap items-center gap-2 mb-2">
                              <span className="font-medium text-sm">{col.name}</span>
                              <Badge color="red">{col.count} 个异常</Badge>
                              <span className="text-xs text-gray-400">
                                正常区间 [{col.lower_bound}, {col.upper_bound}]
                              </span>
                            </div>
                            <div className="overflow-x-auto rounded-lg border">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="bg-gray-50">
                                    <th className="px-2 py-1.5 text-left font-medium text-gray-600 border-b">
                                      行号
                                    </th>
                                    <th className="px-2 py-1.5 text-left font-medium text-gray-600 border-b">
                                      数值
                                    </th>
                                    <th className="px-2 py-1.5 text-left font-medium text-gray-600 border-b">
                                      方向
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {col.outliers?.map((o, j) => (
                                    <tr key={j} className="hover:bg-gray-50">
                                      <td className="px-2 py-1 text-gray-700 border-b border-gray-100">
                                        {o.row}
                                      </td>
                                      <td className="px-2 py-1 font-mono text-red-600 border-b border-gray-100">
                                        {o.value}
                                      </td>
                                      <td className="px-2 py-1 border-b border-gray-100">
                                        <Badge color={o.direction === '偏高' ? 'red' : 'blue'}>
                                          {o.direction}
                                        </Badge>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        ))
                      )}
                    </>
                  )}
                </div>
              ) : (
                <MarkdownRenderer content={result} />
              )
            ) : (
              <Empty icon={FileSpreadsheet} title="等待操作" description="输入数据后点击执行" />
            )}
          </Card>

          {/* 公式解释 */}
          {operation === 'formula' && result && (
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-500" /> 公式解释
              </h3>
              <div className="bg-amber-50 rounded-xl p-4 text-sm text-gray-700 space-y-2">
                <p className="font-medium text-amber-800">公式说明：</p>
                <p>上述公式已根据你的需求生成。如果你需要了解公式的具体用法，可以参考以下说明：</p>
                <ul className="list-disc list-inside space-y-1 text-gray-600">
                  <li>公式中的单元格引用（如 A1, B2）需要根据实际数据位置调整</li>
                  <li>数组公式需要按 Ctrl+Shift+Enter 确认（旧版 Excel）</li>
                  <li>如果公式报错，请检查引用的单元格范围是否正确</li>
                </ul>
                <p className="text-xs text-gray-500 mt-2">
                  提示：可以将公式直接粘贴到 Excel 单元格中使用
                </p>
              </div>
            </Card>
          )}

          {/* 数据预览 */}
          {previewData && (
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Table2 className="w-4 h-4 text-green-600" /> 数据预览（前10行）
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50">
                      {previewData.headers.map((h, i) => (
                        <th
                          key={i}
                          className="px-2 py-1.5 text-left font-medium text-gray-600 border-b"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.rows.map((row, ri) => (
                      <tr key={ri} className="hover:bg-gray-50">
                        {row.map((cell, ci) => (
                          <td key={ci} className="px-2 py-1 text-gray-700 border-b border-gray-100">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* 历史记录 */}
      {historyLoading ? (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" /> 操作历史
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
              <Clock className="w-4 h-4 text-gray-400" /> 操作历史
            </h3>
            <div className="space-y-2">
              {history.slice(0, 10).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                  onClick={() => reuseHistory(item)}
                >
                  <Table2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                  <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded flex-shrink-0">
                    {OPERATIONS.find((o) => o.value === item.operation)?.label || item.operation}
                  </span>
                  <span className="text-sm text-gray-700 truncate flex-1">
                    {item.title || '未命名'}
                  </span>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {item.created_at?.slice(0, 16).replace('T', ' ')}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )
      )}
    </div>
  )
}
