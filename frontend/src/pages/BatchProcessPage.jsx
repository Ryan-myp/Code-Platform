import React, { useState, useRef } from 'react'
import {
  Upload,
  FileText,
  Languages,
  Zap,
  Clock,
  Download,
  Trash2,
  Loader2,
  FileSpreadsheet,
  Sparkles,
  ChevronDown,
  Copy,
  RefreshCw,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'

const TASK_TYPES = [
  { key: 'summarize', label: '批量摘要', icon: FileText, desc: '多个文档一键生成摘要' },
  {
    key: 'doc_summary',
    label: '文档摘要（独立通道）',
    icon: FileText,
    desc: '走专用接口，返回标题/摘要/要点',
  },
  { key: 'keywords', label: '提取关键词', icon: Zap, desc: '提取每个文档的核心关键词' },
  { key: 'translate_en', label: '批量翻译', icon: Languages, desc: '多文档翻译为英文' },
  { key: 'sentiment', label: '情感分析', icon: Sparkles, desc: '分析每个文档的情感倾向' },
  {
    key: 'rewrite',
    label: '批量改写',
    icon: Sparkles,
    desc: '保留原意，重写为更清晰有表现力的版本',
  },
]

export default function BatchProcessPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  const fileRef = useRef(null)

  const [files, setFiles] = useState([])
  const [task, setTask] = useState('summarize')
  const [currentTask, setCurrentTask] = useState(null)
  const [results, setResults] = useState(null)
  const [jobs, setJobs] = useState([])

  const loadJobs = async () => {
    try {
      const res = await api.get('/api/batch/jobs')
      setJobs(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files || [])
    // 边界校验：后端单文件上限 20MB，前端提前拦截避免上传中断
    const oversized = selected.find((f) => f.size > 20 * 1024 * 1024)
    if (oversized) {
      toast.error(`「${oversized.name}」超过 20MB 上限，已忽略`)
      const ok = selected.filter((f) => f.size <= 20 * 1024 * 1024)
      setFiles(ok)
      setResults(null)
      toast.success(ok.length ? `已选择 ${ok.length} 个文件` : '请重新选择文件')
      e.target.value = ''
      return
    }
    setFiles(selected)
    setResults(null)
    toast.success(`已选择 ${selected.length} 个文件`)
  }

  const handleProcess = async () => {
    if (files.length === 0) {
      toast.error('请先选择文件')
      return
    }
    setResults(null)
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    const endpoint = task === 'doc_summary' ? '/api/batch/doc-summary' : '/api/batch/process'
    if (task !== 'doc_summary') form.append('task', task)
    await submitTask(endpoint, form, {
      onUpdate: (t) => setCurrentTask(t),
      onSuccess: (data) => {
        setCurrentTask(null)
        setResults(data)
        loadJobs()
        toast.success(`批量处理完成：${data.file_count ?? data.count ?? 0} 个文件`)
      },
      onError: (e) => {
        setCurrentTask(null)
        toast.error(`处理失败：${e.message}`)
      },
    })
  }

  const handleBatchTranslate = async () => {
    const text = prompt('请输入要翻译的文本（每行一条）：')
    if (!text) return
    const texts = text.split('\n').filter(Boolean)
    if (texts.length === 0) return

    setResults(null)
    await submitTask(
      '/api/batch/translate',
      { texts, target_lang: 'en' },
      {
        onUpdate: (t) => setCurrentTask(t),
        onSuccess: (data) => {
          setCurrentTask(null)
          setResults({ ...data, source: 'text' })
          loadJobs()
          toast.success(`翻译完成：${data.count ?? 0} 条`)
        },
        onError: (e) => {
          setCurrentTask(null)
          toast.error(`翻译失败：${e.message}`)
        },
      }
    )
  }

  // v15：失败项单独重试（translate 场景：按原索引原位替换）
  const retryItems = async (items) => {
    if (!items?.length) return
    const pending = items.filter((it) => it.error && it.original)
    if (pending.length === 0) {
      toast.error('失败项缺少原文，无法重试（文件类任务请重新上传失败文件）')
      return
    }
    await submitTask(
      '/api/batch/retry',
      {
        task_type: 'translate',
        items: pending.map((it) => ({
          index: it.index,
          original: it.original,
          target_lang: 'en',
          source_lang: 'auto',
        })),
      },
      {
        onUpdate: (t) => setCurrentTask(t),
        onSuccess: (data) => {
          setCurrentTask(null)
          const byIndex = new Map((data.results || []).map((r) => [r.index, r]))
          setResults((prev) => ({
            ...prev,
            results: (prev?.results || []).map((r) => byIndex.get(r.index) || r),
          }))
          loadJobs()
          toast.success(`重试完成：成功 ${data.success}/${data.count} 条`)
        },
        onError: (e) => {
          setCurrentTask(null)
          toast.error(`重试失败：${e.message}`)
        },
      }
    )
  }

  const retryAllFailed = () => {
    const failed = (results?.results || []).filter((r) => r.error)
    if (!failed.length) return
    retryItems(failed)
  }

  // 结果 → 文本（导出/复制/分享复用）
  const buildResultsText = (res) => {
    if (!res?.results?.length) return ''
    const lines = [`# 批量处理结果（${res.task || 'batch'}）`, '']
    res.results.forEach((r, i) => {
      const name = r.filename || `项目${i + 1}`
      lines.push(`## ${name}`)
      if (r.error) lines.push(`> 失败：${r.error}`)
      if (r.original) lines.push(`原文：${r.original}`)
      if (r.translated) lines.push(`翻译：${r.translated}`)
      if (r.title) lines.push(`标题：${r.title}`)
      if (r.summary) lines.push(`摘要：${r.summary}`)
      if (r.result) lines.push(`${r.result}`)
      if (r.key_points?.length) lines.push(`要点：${r.key_points.join('；')}`)
      lines.push('')
    })
    return lines.join('\n')
  }

  const exportResults = () => {
    const text = buildResultsText(results)
    if (!text) return
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `批量处理结果_${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('结果已导出')
  }

  const copyResults = async () => {
    const text = buildResultsText(results)
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      toast.success('全部结果已复制')
    } catch {
      toast.error('复制失败，请手动选择复制')
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="批量处理"
        description="一次上传多个文件，AI自动批量处理：摘要/翻译/关键词/情感分析"
        icon={FileSpreadsheet}
        iconColor="from-teal-500 to-emerald-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：上传 + 配置 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Upload className="w-4 h-4 text-teal-500" /> 选择文件
            </h3>
            <input
              ref={fileRef}
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => fileRef.current?.click()}
              className="w-full py-10 border-2 border-dashed border-gray-300 rounded-xl hover:border-teal-400 hover:bg-teal-50/30 transition-all flex flex-col items-center gap-3"
            >
              <Upload className="w-8 h-8 text-gray-400" />
              <div className="text-sm text-gray-500">点击选择多个文件</div>
              <div className="text-xs text-gray-400">支持 PDF / DOCX / TXT / MD / CSV</div>
            </button>

            {files.length > 0 && (
              <div className="mt-3 p-3 bg-teal-50 rounded-lg">
                <div className="font-medium text-teal-800 text-sm">{files.length} 个文件已选择</div>
                <div className="max-h-32 overflow-y-auto mt-1 space-y-0.5">
                  {files.map((f, i) => (
                    <div key={i} className="text-xs text-teal-600 flex items-center gap-1">
                      <FileText className="w-3 h-3" /> {f.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" /> 处理类型
            </h3>
            <div className="space-y-2">
              {TASK_TYPES.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTask(t.key)}
                  className={`w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
                    task === t.key
                      ? 'bg-teal-50 border border-teal-200'
                      : 'bg-gray-50 border border-gray-100 hover:bg-gray-100'
                  }`}
                >
                  <t.icon
                    className={`w-4 h-4 ${task === t.key ? 'text-teal-600' : 'text-gray-400'}`}
                  />
                  <div>
                    <div
                      className={`text-sm font-medium ${task === t.key ? 'text-teal-800' : 'text-gray-700'}`}
                    >
                      {t.label}
                    </div>
                    <div className="text-xs text-gray-500">{t.desc}</div>
                  </div>
                </button>
              ))}
            </div>
            <Button
              variant="primary"
              icon={Sparkles}
              loading={!!currentTask}
              onClick={handleProcess}
              className="w-full mt-4"
            >
              开始批量处理
            </Button>
            {currentTask && (
              <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                  <span>{currentTask.stage || '任务处理中…'}</span>
                  <span>{currentTask.progress || 0}%</span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-teal-500 to-emerald-500 rounded-full transition-all duration-300"
                    style={{ width: `${currentTask.progress || 0}%` }}
                  />
                </div>
              </div>
            )}
            <div className="mt-2 pt-2 border-t border-gray-100">
              <button
                onClick={handleBatchTranslate}
                className="w-full text-center py-2 text-xs text-gray-500 hover:text-teal-600 transition-colors flex items-center justify-center gap-1"
              >
                <Languages className="w-3 h-3" /> 或输入多行文本快速翻译
              </button>
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 处理记录
              {jobs.length === 0 && (
                <button
                  onClick={loadJobs}
                  className="text-xs text-teal-500 hover:underline ml-auto"
                >
                  加载
                </button>
              )}
            </h3>
            {jobs.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无记录</div>
            ) : (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {jobs.map((j) => (
                  <div
                    key={j.id}
                    className="p-2 rounded-lg bg-gray-50 text-xs flex items-center justify-between"
                  >
                    <div>
                      <div className="font-medium text-gray-700">
                        {j.task_type} · {j.file_count}个文件
                      </div>
                      <div className="text-gray-400">{j.created_at?.slice(0, 10)}</div>
                    </div>
                    <Badge color={j.status === 'done' ? 'green' : 'gray'}>{j.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：结果 */}
        <div className="lg:col-span-2 space-y-4">
          {!results ? (
            <Empty
              icon={FileSpreadsheet}
              title="等待处理"
              description="选择多个文件，选择处理类型，点击开始批量处理"
            />
          ) : (
            <Card>
              <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
                <h3 className="font-semibold text-gray-900">
                  处理结果（{results.results?.length || 0} 项）
                </h3>
                <div className="flex items-center gap-2">
                  <Badge color="green">{results.task}</Badge>
                  {results.results?.some((r) => r.error && r.original) && (
                    <Button variant="secondary" size="sm" icon={RefreshCw} onClick={retryAllFailed}>
                      重试失败项
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" icon={Download} onClick={exportResults}>
                    导出全部
                  </Button>
                  <Button variant="ghost" size="sm" icon={Copy} onClick={copyResults}>
                    复制全部
                  </Button>
                  <ShareButton
                    content={buildResultsText(results)}
                    title="批量处理结果"
                    contentType="batch_process"
                  />
                </div>
              </div>
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {results.results?.map((r, i) => (
                  <div
                    key={i}
                    className={`p-4 rounded-xl ${r.error ? 'bg-red-50 border border-red-100' : 'bg-gray-50'}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-800 flex items-center gap-2">
                        <FileText className="w-3.5 h-3.5 text-gray-400" />
                        {r.filename
                          ? r.filename
                          : r.index !== undefined
                            ? `#${r.index + 1}`
                            : `项目${i + 1}`}
                      </span>
                      {r.error ? (
                        <Badge color="red">失败</Badge>
                      ) : (
                        <Badge color="green">成功</Badge>
                      )}
                    </div>
                    {r.original && (
                      <div className="mb-2 p-2 bg-white rounded-lg text-xs text-gray-500">
                        <span className="text-gray-400">原文：</span>
                        {r.original}
                      </div>
                    )}
                    {r.translated && (
                      <div className="p-2 bg-teal-50 rounded-lg text-sm text-teal-800">
                        {r.translated}
                      </div>
                    )}
                    {r.result && (
                      <div className="p-2 bg-white rounded-lg text-sm text-gray-700 whitespace-pre-wrap">
                        {r.result}
                      </div>
                    )}
                    {r.summary && (
                      <div className="p-2 bg-white rounded-lg text-sm text-gray-700">
                        <strong>{r.title}</strong>
                        <p className="mt-1 text-gray-600">{r.summary}</p>
                        {r.key_points?.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {r.key_points.map((kp, j) => (
                              <span
                                key={j}
                                className="px-2 py-0.5 bg-teal-100 text-teal-700 rounded text-xs"
                              >
                                {kp}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                    {r.error && (
                      <div className="p-2 bg-red-50 rounded-lg text-xs text-red-600 mb-2">{r.error}</div>
                    )}
                    {r.error && r.original && (
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={RefreshCw}
                        onClick={() => retryItems([r])}
                      >
                        重试此项
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
