import React, { useState, useRef } from 'react'
import {
  BarChart3,
  Upload,
  X,
  Play,
  Sparkles,
  ChevronDown,
  Image as ImageIcon,
  Loader2,
  Database,
  FileText,
  Download,
  RefreshCw,
  Settings2,
  AlertTriangle,
  Lightbulb,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader } from '../components/ui'
import ShareButton from '../components/ShareButton'
import HistoryPanel from '../components/HistoryPanel'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import MarkdownRenderer from '../components/MarkdownRenderer'
import useToolHistory from '../hooks/useToolHistory'

// 示例数据：一键体验（电商销售明细）
const SAMPLE_CSV = `日期,区域,产品类别,销售金额,销售数量,销售员
2026-01-05,华东,数码,12800,12,王芳
2026-01-08,华南,家电,22600,8,李强
2026-01-12,华北,服饰,8600,45,张伟
2026-01-15,华东,家电,31200,11,陈静
2026-01-18,华南,服饰,5400,28,王芳
2026-01-22,华北,数码,9800,9,李强
2026-01-25,华东,服饰,11200,52,张伟
2026-01-28,华南,家电,19800,7,陈静
2026-02-03,华东,数码,14500,14,王芳
2026-02-06,华南,服饰,6200,30,李强
2026-02-10,华北,家电,16800,6,张伟
2026-02-14,华东,服饰,9800,44,陈静
2026-02-18,华南,数码,7600,8,王芳
2026-02-22,华北,家电,25400,9,李强
2026-02-26,华东,数码,17300,16,张伟
2026-03-02,华南,服饰,8900,41,陈静
2026-03-06,华北,数码,11200,11,王芳
2026-03-10,华东,家电,28700,10,李强
2026-03-14,华南,家电,20900,7,张伟
2026-03-18,华北,服饰,7400,36,陈静
2026-03-22,华东,数码,15800,15,王芳
2026-03-26,华南,服饰,10300,47,李强
2026-03-30,华北,家电,18200,6,张伟`

const QUICK_QUESTIONS = [
  '汇总各列统计信息（总和/均值/最值），找出最重要的发现',
  '分析整体销售趋势并按区域对比，用图表展示',
  '找出销量与销售额 Top 5 排名，用图表展示',
  '分析各产品类别的表现差异并给出优化建议',
]

const DEPTH_OPTIONS = [
  { value: 'quick', label: '快速', desc: '核心指标 + 关键发现' },
  { value: 'standard', label: '标准', desc: '概览/趋势/对比多维度' },
  { value: 'deep', label: '深度', desc: '交叉分析 + 统计 + 建议' },
]

const STYLE_OPTIONS = [
  { value: 'default', label: '默认' },
  { value: 'business', label: '商务简约' },
  { value: 'dark', label: '深色' },
]

function parsePreview(csv, maxRows = 6, maxCols = 8) {
  const lines = csv.split('\n').filter((l) => l.trim())
  if (lines.length === 0) return []
  return lines.slice(0, maxRows).map((line) => {
    const cells = line.split(',').map((c) => c.replace(/^"|"$/g, '').trim())
    return cells.slice(0, maxCols)
  })
}

export default function DataAnalyzerPage() {
  const toast = useToast()
  const [csv, setCsv] = useState('')
  const [meta, setMeta] = useState({ columns: [], rows: 0, filename: '' })
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [showCode, setShowCode] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [depth, setDepth] = useState('standard')
  const [chartStyle, setChartStyle] = useState('default')
  const [lastParams, setLastParams] = useState(null) // 重试时复用
  const fileInputRef = useRef(null)
  const { history, add, remove, clear } = useToolHistory('data_analyzer_history_v1', 20)

  // 下载工具（通用）
  const downloadText = (content, filename, mime = 'text/markdown;charset=utf-8') => {
    const blob = new Blob([content], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 3000)
  }

  const buildConclusionMd = () => {
    if (!result?.conclusion) return ''
    const q = lastParams?.question || question
    const header = `# 数据分析报告\n\n> 分析问题：${q}\n> 数据：${meta.filename || 'data.csv'}（${meta.rows} 行）\n> 耗时：${result.duration}s\n\n---\n\n`
    return header + result.conclusion
  }

  const downloadConclusion = () => {
    if (!result?.conclusion) return
    const q = lastParams?.question || question
    downloadText(buildConclusionMd(), `数据分析-${(q || 'report').slice(0, 20).replace(/[\\/:*?"<>|]/g, '_')}.md`)
    toast.success('分析报告已下载')
  }

  const downloadChart = (name, b64) => {
    const a = document.createElement('a')
    a.href = `data:image/png;base64,${b64}`
    a.download = name.endsWith('.png') ? name : `${name}.png`
    document.body.appendChild(a)
    a.click()
    a.remove()
    toast.success(`图表 ${name} 已下载`)
  }

  const runAnalyze = async (q, data, filename, opts = {}) => {
    setLoading(true)
    setResult(null)
    try {
      const res = await api.post('/api/data-analyzer/analyze', {
        question: q,
        data,
        filename: filename || 'data.csv',
        depth: opts.depth || depth,
        chart_style: opts.chartStyle || chartStyle,
      })
      setResult(res.data)
      add({
        title: q.slice(0, 30),
        question: q,
        csv: data.slice(0, 300),
        filename: filename || 'data.csv',
        conclusion: res.data.conclusion,
        charts: (res.data.charts || []).map((c) => ({ name: c.name, data: c.data.slice(0, 40) })),
        depth: opts.depth || depth,
        chartStyle: opts.chartStyle || chartStyle,
      })
      if (res.data.error && !res.data.conclusion) {
        toast.error('分析执行出错，请尝试换一种问法')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '分析失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const handleRun = async () => {
    if (!csv.trim()) {
      toast.error('请先上传数据或使用示例数据')
      return
    }
    if (!question.trim()) {
      toast.error('请描述你想分析的问题')
      return
    }
    const params = { question: question.trim(), filename: meta.filename }
    setLastParams(params)
    await runAnalyze(params.question, csv, params.filename)
  }

  const handleRetry = () => {
    if (!lastParams || !csv.trim()) return
    setQuestion(lastParams.question)
    runAnalyze(lastParams.question, csv, lastParams.filename)
  }

  const handleReuse = (item) => {
    setQuestion(item.question)
    if (item.depth) setDepth(item.depth)
    if (item.chartStyle) setChartStyle(item.chartStyle)
    toast.success('已复用历史分析，可直接运行')
  }

  const onKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleRun()
    }
  }

  const applyCsv = (text, filename = '') => {
    const lines = text.split('\n').filter((l) => l.trim())
    const columns =
      lines.length > 0
        ? lines[0]
            .split(',')
            .map((c) => c.replace(/^"|"$/g, '').trim())
            .filter(Boolean)
        : []
    setCsv(text)
    setMeta({ columns, rows: Math.max(lines.length - 1, 0), filename })
    setResult(null)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await api.post('/api/data-analyzer/upload', form)
      applyCsv(res.data.csv, res.data.filename)
      toast.success(
        `已解析 ${res.data.filename}：${res.data.columns.length} 列 / ${res.data.rows} 行`
      )
    } catch (err) {
      toast.error(err.message || '文件解析失败')
    }
    e.target.value = ''
  }

  const preview = parsePreview(csv)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI数据分析沙箱"
        description="上传表格（CSV/Excel），用自然语言提问，AI 自动生成 Python 代码分析并出图表"
        icon={BarChart3}
        iconColor="from-emerald-500 to-teal-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* 左侧：数据 + 问题 */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Database className="w-4 h-4 text-emerald-600" /> 1. 数据源
              </h3>
              <button
                onClick={() => applyCsv(SAMPLE_CSV, 'sample_sales.csv')}
                className="flex items-center gap-1 px-2.5 py-1 text-xs text-brand-600 bg-brand-50 hover:bg-brand-100 rounded-full transition-colors"
              >
                <Sparkles className="w-3 h-3" />
                试试示例数据
              </button>
            </div>

            {/* 上传区 */}
            <div className="flex items-center gap-2 mb-3">
              <label className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-gray-200 rounded-xl cursor-pointer hover:border-emerald-500 hover:bg-emerald-50/40 transition-colors">
                <Upload className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-500">上传 CSV / Excel</span>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileUpload}
                  accept=".csv,.xlsx,.xls"
                  className="hidden"
                />
              </label>
              {csv && (
                <button
                  onClick={() => {
                    setCsv('')
                    setMeta({ columns: [], rows: 0, filename: '' })
                    setResult(null)
                  }}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  title="清除数据"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* CSV 编辑器 */}
            {!csv ? (
              <Empty
                icon={Database}
                title="等待数据"
                description="上传表格文件，或点击「试试示例数据」快速体验"
              />
            ) : (
              <>
                <div className="flex items-center gap-2 mb-2 text-xs">
                  {meta.columns.slice(0, 8).map((c) => (
                    <span
                      key={c}
                      className="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full font-medium"
                    >
                      {c}
                    </span>
                  ))}
                  {meta.columns.length > 8 && (
                    <span className="text-gray-400">+{meta.columns.length - 8} 列</span>
                  )}
                  <span className="ml-auto text-gray-400">{meta.rows} 行</span>
                </div>
                {/* 预览表格 */}
                <div className="overflow-x-auto rounded-lg border border-gray-100 mb-3">
                  <table className="w-full text-xs">
                    <tbody>
                      {preview.map((row, i) => (
                        <tr key={i} className={i === 0 ? 'bg-gray-50' : 'border-t border-gray-50'}>
                          {row.map((cell, j) => (
                            <td
                              key={j}
                              className={`px-2.5 py-1.5 whitespace-nowrap ${i === 0 ? 'font-semibold text-gray-700' : 'text-gray-500'}`}
                            >
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <textarea
                  value={csv}
                  onChange={(e) => applyCsv(e.target.value, meta.filename)}
                  rows={6}
                  spellCheck={false}
                  className="w-full px-3 py-2 bg-gray-50 text-gray-700 font-mono text-xs rounded-xl border border-gray-100 focus:ring-2 focus:ring-emerald-400 outline-none resize-y"
                />
              </>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-emerald-600" /> 2. 你想分析什么？
            </h3>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="例如：按区域汇总销售金额并分析趋势，找出增长最快的品类…（⌘/Ctrl + Enter 运行）"
              rows={3}
              className="w-full px-4 py-3 text-sm text-gray-900 placeholder-gray-400 border border-gray-100 rounded-xl outline-none focus:ring-2 focus:ring-emerald-400 resize-y"
            />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {QUICK_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => setQuestion(q)}
                  className="px-2.5 py-1 text-xs text-gray-500 bg-gray-50 hover:bg-emerald-50 hover:text-emerald-700 rounded-full transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>

            {/* 高级参数（专业基线：真实影响分析深度与图表风格） */}
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="mt-3 w-full flex items-center justify-between px-3 py-2 text-xs text-gray-500 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <span className="flex items-center gap-1.5 font-medium">
                <Settings2 className="w-3.5 h-3.5" /> 高级选项
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
              />
            </button>
            {showAdvanced && (
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-500 mb-1.5">分析深度</p>
                  <div className="flex rounded-lg overflow-hidden border border-gray-200">
                    {DEPTH_OPTIONS.map((d) => (
                      <button
                        key={d.value}
                        onClick={() => setDepth(d.value)}
                        title={d.desc}
                        className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                          depth === d.value
                            ? 'bg-emerald-600 text-white'
                            : 'bg-white text-gray-500 hover:bg-gray-50'
                        }`}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1.5">图表风格</p>
                  <div className="flex rounded-lg overflow-hidden border border-gray-200">
                    {STYLE_OPTIONS.map((s) => (
                      <button
                        key={s.value}
                        onClick={() => setChartStyle(s.value)}
                        className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                          chartStyle === s.value
                            ? 'bg-emerald-600 text-white'
                            : 'bg-white text-gray-500 hover:bg-gray-50'
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <Button
              onClick={handleRun}
              loading={loading}
              disabled={!csv.trim() || !question.trim()}
              className="w-full mt-4"
              size="lg"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              {loading ? 'AI 正在生成代码并分析…' : '开始分析'}
            </Button>
          </Card>

          {/* 历史记录（专业基线：结果可回溯可复用） */}
          <HistoryPanel
            history={history}
            onReuse={handleReuse}
            onRemove={remove}
            onClear={clear}
            renderSummary={(item) =>
              `${item.filename || ''} · ${item.depth || '标准'}深度 · ${(item.conclusion || '').slice(0, 40)}`
            }
          />
        </div>

        {/* 右侧：结果 */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="min-h-[500px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-emerald-600" /> 分析结果
              </h3>
              <div className="flex items-center gap-2">
                {result?.duration && (
                  <span className="text-xs text-gray-400">耗时 {result.duration}s</span>
                )}
                {result?.conclusion && (
                  <>
                    <Button size="sm" variant="ghost" icon={Download} onClick={downloadConclusion}>
                      导出报告
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(buildConclusionMd())
                          toast.success('分析报告已复制')
                        } catch {
                          toast.error('复制失败')
                        }
                      }}
                    >
                      📋 复制
                    </Button>
                    <ShareButton
                      content={buildConclusionMd()}
                      title="数据分析报告"
                      contentType="data_analysis"
                    />
                    <Button size="sm" variant="ghost" icon={RefreshCw} onClick={handleRetry}>
                      重新分析
                    </Button>
                  </>
                )}
              </div>
            </div>

            {!result ? (
              <Empty
                icon={BarChart3}
                title="等待分析"
                description="上传数据并描述问题后，AI 将自动生成分析代码、图表与结论"
              />
            ) : (
              <div className="space-y-5">
                {/* 图表 */}
                {result.charts?.length > 0 && (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {result.charts.map((chart) => (
                      <div
                        key={chart.name}
                        className="rounded-xl border border-gray-100 overflow-hidden"
                      >
                        <div className="px-3 py-2 bg-gray-50 flex items-center gap-2 text-xs text-gray-500">
                          <ImageIcon className="w-3.5 h-3.5" />
                          {chart.name}
                        </div>
                        <img
                          src={`data:image/png;base64,${chart.data}`}
                          alt={chart.name}
                          className="w-full bg-white"
                        />
                        <button
                          onClick={() => downloadChart(chart.name, chart.data)}
                          className="w-full py-1.5 text-xs text-gray-500 hover:text-emerald-600 hover:bg-emerald-50 flex items-center justify-center gap-1 transition-colors"
                        >
                          <Download className="w-3 h-3" /> 下载图片
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* 数据概览（v15：列/行/类型概览卡片） */}
                {result.overview && (
                  <div className="p-3 bg-gray-50 rounded-xl flex items-center gap-3 flex-wrap text-xs">
                    <Database className="w-4 h-4 text-emerald-500" />
                    <span className="text-gray-600 font-medium">
                      {meta.filename || 'data.csv'}
                    </span>
                    <span className="px-2 py-0.5 bg-white border border-gray-200 rounded text-gray-600">
                      {(result.overview.columns || []).length} 列
                    </span>
                    <span className="px-2 py-0.5 bg-white border border-gray-200 rounded text-gray-600">
                      {result.overview.rows} 行
                    </span>
                    <div className="flex gap-1 ml-auto">
                      {(result.overview.columns || []).slice(0, 10).map((c) => (
                        <span key={c} className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded-full">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 三段式结论（洞察/异常/建议） */}
                {result.conclusion_sections &&
                  (result.conclusion_sections.insights?.length ||
                    result.conclusion_sections.anomalies?.length ||
                    result.conclusion_sections.suggestions?.length) && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="p-4 rounded-xl bg-blue-50 border border-blue-100">
                        <div className="text-sm font-semibold text-blue-700 mb-2 flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5" /> 洞察
                        </div>
                        <ul className="space-y-1.5">
                          {(result.conclusion_sections.insights || []).map((item, i) => (
                            <li key={i} className="text-xs text-blue-900/80 leading-relaxed">
                              • {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div className="p-4 rounded-xl bg-red-50 border border-red-100">
                        <div className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5" /> 异常
                        </div>
                        <ul className="space-y-1.5">
                          {(result.conclusion_sections.anomalies || []).map((item, i) => (
                            <li key={i} className="text-xs text-red-900/80 leading-relaxed">
                              • {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div className="p-4 rounded-xl bg-amber-50 border border-amber-100">
                        <div className="text-sm font-semibold text-amber-700 mb-2 flex items-center gap-1.5">
                          <Lightbulb className="w-3.5 h-3.5" /> 建议
                        </div>
                        <ul className="space-y-1.5">
                          {(result.conclusion_sections.suggestions || []).map((item, i) => (
                            <li key={i} className="text-xs text-amber-900/80 leading-relaxed">
                              • {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                {/* 结论 */}
                {result.conclusion && (
                  <div className="prose prose-sm max-w-none">
                    <MarkdownRenderer content={result.conclusion} />
                  </div>
                )}

                {/* 执行错误 */}
                {result.error && !result.conclusion && (
                  <div className="p-4 bg-red-50 border border-red-100 rounded-xl">
                    <p className="text-sm text-red-600 font-medium mb-1">代码执行出错</p>
                    <pre className="text-xs text-red-500 whitespace-pre-wrap font-mono">
                      {result.error}
                    </pre>
                  </div>
                )}

                {/* 生成代码 */}
                {result.code && (
                  <div className="rounded-xl border border-gray-100 overflow-hidden">
                    <button
                      onClick={() => setShowCode(!showCode)}
                      className="w-full px-4 py-2.5 bg-gray-50 flex items-center justify-between text-xs text-gray-500 hover:text-gray-700 transition-colors"
                    >
                      <span className="flex items-center gap-1.5 font-medium">
                        <FileText className="w-3.5 h-3.5" />
                        AI 生成的 Python 代码（只读展示，沙箱已执行）
                      </span>
                      <ChevronDown
                        className={`w-3.5 h-3.5 transition-transform ${showCode ? 'rotate-180' : ''}`}
                      />
                    </button>
                    {showCode && (
                      <pre className="p-4 bg-gray-900 text-green-400 font-mono text-xs whitespace-pre-wrap overflow-x-auto max-h-72 overflow-y-auto">
                        {result.code}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
