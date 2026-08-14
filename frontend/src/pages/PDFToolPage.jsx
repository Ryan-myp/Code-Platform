import React, { useState, useEffect, useMemo } from 'react'
import {
  FileText,
  Merge,
  Scissors,
  Table,
  Shield,
  UserCheck,
  Upload,
  Download,
  Sparkles,
  Loader2,
  AlertTriangle,
  Check,
  FileWarning,
  History,
  FileArchive,
  Wand2,
} from 'lucide-react'
import { Card, Button, PageHeader, Badge, Empty, ErrorState, Modal } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import usePersistentToolState from '../hooks/usePersistentToolState'

const TABS = [
  { id: 'merge', label: 'PDF合并', icon: Merge, desc: '多个PDF文件合并为一个' },
  { id: 'split', label: 'PDF拆分', icon: Scissors, desc: '按页码范围拆分PDF' },
  { id: 'extract', label: '表格提取', icon: Table, desc: '从PDF提取表格为CSV' },
  { id: 'compress', label: 'PDF压缩', icon: FileArchive, desc: '去冗余+图片重编码减小体积' },
  { id: 'contract', label: '合同审查', icon: Shield, desc: 'AI逐条审查+修改建议' },
  { id: 'resume', label: '简历优化', icon: UserCheck, desc: 'AI简历评分+优化建议' },
]

const QUALITY_PRESETS = [
  { value: 3, label: '高压缩', desc: '体积最小' },
  { value: 5, label: '均衡', desc: '推荐' },
  { value: 8, label: '高质量', desc: '画质优先' },
]

const RISK_LABELS = { high: '高风险', medium: '中风险', low: '低风险' }

export default function PDFToolPage() {
  const toast = useToast()
  const [tab, setTab] = useState('merge')

  // 文档模板库：合同审查/简历优化场景模板（一键填充示例 + 注入专家要点）
  const [docTpls, setDocTpls] = useState([])
  const [docTplId, setDocTplId] = useState('')
  const [docTplInfo, setDocTplInfo] = useState(null)
  const [docTplCat, setDocTplCat] = useState('全部')
  useEffect(() => {
    api
      .get('/api/pdf-doc-templates/list')
      .then((res) => setDocTpls(res.data?.items || []))
      .catch(() => {})
  }, [])
  const docTplCats = useMemo(
    () => ['全部', ...new Set(docTpls.map((t) => t.category))],
    [docTpls]
  )
  const openDocTpl = async (tid) => {
    try {
      const res = await api.get(`/api/pdf-doc-templates/${tid}`)
      setDocTplInfo(res.data)
    } catch (e) {
      toast.error(`模板详情加载失败：${e.message}`)
    }
  }
  const applyDocTplTo = (t, kind) => {
    setDocTplId(t.id)
    if (kind === 'contract') {
      setContractText(t.sample || '')
      if (t.name) setContractTitle(t.name)
    } else {
      setResumeText(t.sample || '')
      if (t.position) setTargetPosition(t.position)
    }
  }
  // 输入态持久化（刷新/误关不丢草稿）
  const [persistInputs, setPersistInputs] = usePersistentToolState('pdf_ai_inputs', {
    contractText: '',
    contractTitle: '',
    resumeText: '',
    targetPosition: '',
  })

  // Merge
  const [mergeFiles, setMergeFiles] = useState([])
  const [merging, setMerging] = useState(false)
  const [mergeResult, setMergeResult] = useState(null)

  // Split
  const [splitFile, setSplitFile] = useState(null)
  const [pageRanges, setPageRanges] = useState('')
  const [splitting, setSplitting] = useState(false)
  const [splitResult, setSplitResult] = useState(null)

  // Extract
  const [extractFile, setExtractFile] = useState(null)
  const [extracting, setExtracting] = useState(false)
  const [extractResult, setExtractResult] = useState(null)

  // Contract
  const [contractText, setContractText] = useState('')
  const [contractTitle, setContractTitle] = useState('')
  const [reviewing, setReviewing] = useState(false)
  const [contractResult, setContractResult] = useState(null)

  // Resume
  const [resumeText, setResumeText] = useState('')
  const [targetPosition, setTargetPosition] = useState('')
  const [optimizing, setOptimizing] = useState(false)
  const [resumeResult, setResumeResult] = useState(null)

  // Compress
  const [compressFile, setCompressFile] = useState(null)
  const [quality, setQuality] = useState(5)
  const [compressing, setCompressing] = useState(false)
  const [compressResult, setCompressResult] = useState(null)

  // 输入态持久化生效（useEffect 须在 state 声明之后，避免 TDZ）
  useEffect(() => {
    if (persistInputs.contractText) setContractText(persistInputs.contractText)
    if (persistInputs.contractTitle) setContractTitle(persistInputs.contractTitle)
    if (persistInputs.resumeText) setResumeText(persistInputs.resumeText)
    if (persistInputs.targetPosition) setTargetPosition(persistInputs.targetPosition)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    const t = setTimeout(() => {
      setPersistInputs({ contractText, contractTitle, resumeText, targetPosition })
    }, 800)
    return () => clearTimeout(t)
  }, [contractText, contractTitle, resumeText, targetPosition, setPersistInputs])

  // 任务记录（GET /api/pdf/jobs）
  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(false)

  const loadJobs = async () => {
    setJobsLoading(true)
    try {
      const res = await api.get('/api/pdf/jobs?limit=20')
      setJobs(res.data || [])
    } catch {
      /* 未登录或异常时静默 */
    } finally {
      setJobsLoading(false)
    }
  }

  useEffect(() => {
    loadJobs()
  }, [])

  const JOB_LABELS = {
    merge: 'PDF合并',
    split: 'PDF拆分',
    extract_table: '表格提取',
    compress: 'PDF压缩',
    contract_review: '合同审查',
    resume_optimize: '简历优化',
  }
  const JOB_STATUS_COLOR = { done: 'green', failed: 'red', processing: 'blue' }

  // ── Merge ──
  const uploadMerge = (e) => {
    const files = Array.from(e.target.files || [])
    setMergeFiles(files)
    setMergeResult(null)
  }
  const doMerge = async () => {
    if (mergeFiles.length < 2) {
      toast.error('至少选择2个PDF文件')
      return
    }
    setMerging(true)
    setMergeResult(null)
    try {
      const form = new FormData()
      mergeFiles.forEach((f) => form.append('files', f))
      const res = await api.post('/api/pdf/merge', form)
      setMergeResult(res.data)
      toast.success(res.data.message || '合并完成')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setMerging(false)
    }
  }

  // ── Split ──
  const uploadSplit = (e) => {
    setSplitFile(e.target.files?.[0] || null)
    setSplitResult(null)
  }
  const doSplit = async () => {
    if (!splitFile) {
      toast.error('请选择PDF文件')
      return
    }
    setSplitting(true)
    setSplitResult(null)
    try {
      const form = new FormData()
      form.append('file', splitFile)
      form.append('ranges', pageRanges)
      const res = await api.post('/api/pdf/split', form)
      setSplitResult(res.data)
      toast.success(res.data.message || '拆分完成')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSplitting(false)
    }
  }

  // ── Extract ──
  const uploadExtract = (e) => {
    setExtractFile(e.target.files?.[0] || null)
    setExtractResult(null)
  }
  const doExtract = async () => {
    if (!extractFile) {
      toast.error('请选择PDF文件')
      return
    }
    setExtracting(true)
    setExtractResult(null)
    try {
      const form = new FormData()
      form.append('file', extractFile)
      const res = await api.post('/api/pdf/extract-table', form)
      setExtractResult(res.data)
      toast.success(`找到 ${res.data.tables_found} 个表格`)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setExtracting(false)
    }
  }

  // ── Contract ──
  const doReview = async () => {
    if (!contractText.trim() || contractText.length < 20) {
      toast.error('请输入20字以上的合同文本')
      return
    }
    setReviewing(true)
    setContractResult(null)
    try {
      const res = await api.post('/api/pdf/contract-review', {
        text: contractText.trim(),
        title: contractTitle || '合同审查',
        template_id: docTplId && docTplId.startsWith('pdt_') ? docTplId : '',
      })
      setContractResult(res.data)
      toast.success(`审查完成 — 风险等级：${res.data.risk_level}`)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setReviewing(false)
    }
  }

  // ── Compress ──
  const uploadCompress = (e) => {
    setCompressFile(e.target.files?.[0] || null)
    setCompressResult(null)
  }
  const doCompress = async () => {
    if (!compressFile) {
      toast.error('请选择PDF文件')
      return
    }
    setCompressing(true)
    setCompressResult(null)
    try {
      const form = new FormData()
      form.append('file', compressFile)
      form.append('quality', String(quality))
      const res = await api.post('/api/pdf/compress', form)
      setCompressResult(res.data)
      toast.success(res.data.message || '压缩完成')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setCompressing(false)
    }
  }

  // ── Resume ──
  const doOptimize = async () => {
    if (!resumeText.trim() || resumeText.length < 20) {
      toast.error('请输入20字以上的简历内容')
      return
    }
    setOptimizing(true)
    setResumeResult(null)
    try {
      const res = await api.post('/api/pdf/resume-optimize', {
        text: resumeText.trim(),
        target_position: targetPosition,
        template_id: docTplId && docTplId.startsWith('pdt_') ? docTplId : '',
      })
      setResumeResult(res.data)
      toast.success(`优化完成 — 综合评分: ${res.data.overall_score} 分`)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setOptimizing(false)
    }
  }

  // ── Risk Badge Helper ──
  const riskColor = (level) => {
    if (level === 'high') return 'red'
    if (level === 'medium') return 'amber'
    return 'green'
  }

  // 责任倾向徽标：甲方/乙方/双方/未标注
  const partyColor = (p) => {
    if (p === '甲方') return 'blue'
    if (p === '乙方') return 'violet'
    if (p === '双方') return 'emerald'
    return 'gray'
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="PDF 工具集"
        description="PDF合并/拆分/表格提取/压缩 + AI合同审查 + AI简历优化 — 文档处理全家桶"
        icon={FileText}
        iconColor="from-red-500 to-rose-600"
      />

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
              tab === t.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* PDF合并 */}
      {tab === 'merge' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Merge className="w-4 h-4 text-blue-500" /> PDF合并
          </h3>
          <p className="text-sm text-gray-500 mb-4">将多个PDF文件按上传顺序合并为一个文件</p>
          <label className="flex flex-col items-center gap-2 p-8 border-2 border-dashed border-gray-200 rounded-xl hover:border-blue-400 cursor-pointer transition-colors mb-4">
            <Upload className="w-8 h-8 text-gray-300" />
            <span className="text-sm text-gray-400">
              {mergeFiles.length > 0 ? `已选择 ${mergeFiles.length} 个文件` : '点击选择多个PDF文件'}
            </span>
            <input type="file" multiple accept=".pdf" onChange={uploadMerge} className="hidden" />
          </label>
          {mergeFiles.length > 0 && (
            <div className="space-y-2 mb-4">
              {mergeFiles.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-gray-600">
                  <FileText className="w-4 h-4 text-gray-400" />
                  {f.name} ({(f.size / 1024).toFixed(1)} KB)
                </div>
              ))}
            </div>
          )}
          <Button
            variant="primary"
            icon={Merge}
            loading={merging}
            onClick={doMerge}
            disabled={mergeFiles.length < 2}
          >
            合并PDF
          </Button>
          {mergeResult?.success && (
            <div className="mt-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
              {mergeResult.message}
              {mergeResult.download_url && (
                <a href={mergeResult.download_url} className="ml-2 font-medium underline" download>
                  下载
                </a>
              )}
            </div>
          )}
        </Card>
      )}

      {/* PDF拆分 */}
      {tab === 'split' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Scissors className="w-4 h-4 text-orange-500" /> PDF拆分
          </h3>
          <div className="space-y-4">
            <label className="flex flex-col items-center gap-2 p-8 border-2 border-dashed border-gray-200 rounded-xl hover:border-orange-400 cursor-pointer transition-colors">
              <Upload className="w-8 h-8 text-gray-300" />
              <span className="text-sm text-gray-400">
                {splitFile ? splitFile.name : '点击选择要拆分的PDF'}
              </span>
              <input type="file" accept=".pdf" onChange={uploadSplit} className="hidden" />
            </label>
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">
                页码范围（可选）
              </label>
              <input
                value={pageRanges}
                onChange={(e) => setPageRanges(e.target.value)}
                placeholder="如: 1-3,5,7-10（不填则整文档每5页拆分）"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-orange-500/20 outline-none"
              />
            </div>
            <Button
              variant="primary"
              icon={Scissors}
              loading={splitting}
              onClick={doSplit}
              disabled={!splitFile}
            >
              拆分PDF
            </Button>
          </div>
          {splitResult?.success && (
            <div className="mt-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
              共 {splitResult.total_pages} 页，提取 {splitResult.extracted_files?.length || 0}{' '}
              个文件
            </div>
          )}
        </Card>
      )}

      {/* 表格提取 */}
      {tab === 'extract' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Table className="w-4 h-4 text-emerald-500" /> 表格提取
          </h3>
          <label className="flex flex-col items-center gap-2 p-8 border-2 border-dashed border-gray-200 rounded-xl hover:border-emerald-400 cursor-pointer transition-colors mb-4">
            <Upload className="w-8 h-8 text-gray-300" />
            <span className="text-sm text-gray-400">
              {extractFile ? extractFile.name : '点击选择包含表格的PDF'}
            </span>
            <input type="file" accept=".pdf" onChange={uploadExtract} className="hidden" />
          </label>
          <Button
            variant="primary"
            icon={Table}
            loading={extracting}
            onClick={doExtract}
            disabled={!extractFile}
          >
            提取表格
          </Button>
          {extractResult && (
            <div className="mt-4 p-3 rounded-xl bg-gray-50 border text-sm">
              {extractResult.success ? (
                <div>
                  <Badge color="green">{extractResult.tables_found} 个表格</Badge>
                  {extractResult.tables?.map((t, i) => (
                    <details key={i} className="mt-2">
                      <summary className="text-blue-600 cursor-pointer">
                        表格{t.table_index}: {t.rows}行×{t.columns}列
                      </summary>
                      <pre className="mt-2 text-xs overflow-auto max-h-40 bg-white p-2 rounded">
                        {t.csv}
                      </pre>
                    </details>
                  ))}
                </div>
              ) : (
                <div className="text-amber-700">{extractResult.message}</div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* PDF压缩 */}
      {tab === 'compress' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <FileArchive className="w-4 h-4 text-sky-500" /> PDF压缩
          </h3>
          <p className="text-sm text-gray-500 mb-4">
            去除文档冗余对象；低强度档位还会对超大图片降采样重编码，显著减小体积
          </p>
          <label className="flex flex-col items-center gap-2 p-8 border-2 border-dashed border-gray-200 rounded-xl hover:border-sky-400 cursor-pointer transition-colors mb-4">
            <Upload className="w-8 h-8 text-gray-300" />
            <span className="text-sm text-gray-400">
              {compressFile
                ? `${compressFile.name} (${(compressFile.size / 1024).toFixed(1)} KB)`
                : '点击选择要压缩的PDF'}
            </span>
            <input type="file" accept=".pdf" onChange={uploadCompress} className="hidden" />
          </label>
          <div className="mb-4">
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              压缩强度：<span className="text-sky-600 font-bold">{quality}</span>
            </label>
            <div className="flex gap-2">
              {QUALITY_PRESETS.map((q) => (
                <button
                  key={q.value}
                  onClick={() => setQuality(q.value)}
                  className={`flex-1 px-3 py-2 rounded-lg border text-sm transition-colors ${
                    quality === q.value
                      ? 'border-sky-500 bg-sky-50 text-sky-700 font-medium'
                      : 'border-gray-200 text-gray-500 hover:border-sky-300'
                  }`}
                >
                  {q.label}
                  <span className="block text-xs text-gray-400">{q.desc}</span>
                </button>
              ))}
            </div>
          </div>
          <Button
            variant="primary"
            icon={FileArchive}
            loading={compressing}
            onClick={doCompress}
            disabled={!compressFile}
          >
            压缩PDF
          </Button>
          {compressResult && (
            <div className="mt-4 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-emerald-800 font-medium mb-1">{compressResult.message}</div>
                  <div className="flex gap-4 text-xs text-emerald-700">
                    <span>原始 {(compressResult.original_size / 1024).toFixed(1)} KB</span>
                    <span>→ 压缩后 {(compressResult.compressed_size / 1024).toFixed(1)} KB</span>
                    <span className="font-bold">减小 {compressResult.ratio}%</span>
                  </div>
                </div>
                <a
                  href={compressResult.download_url}
                  download
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 transition-colors flex-shrink-0"
                >
                  <Download className="w-3.5 h-3.5" /> 下载
                </a>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* 合同审查 */}
      {tab === 'contract' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Shield className="w-4 h-4 text-red-500" /> AI合同审查
            <span className="ml-auto text-[11px] font-normal text-gray-400 flex items-center gap-1">
              <Wand2 className="w-3.5 h-3.5" /> 模板一键填充示例合同
            </span>
          </h3>
          {/* 合同审查模板：一键填充示例 + 注入审查要点 */}
          <div className="mb-3">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {docTpls
                .filter((t) => t.category === '合同审查')
                .map((t) => (
                  <button
                    key={t.id}
                    onClick={() => applyDocTplTo(t, 'contract')}
                    title={t.desc}
                    className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full border text-xs transition-all ${
                      docTplId === t.id
                        ? 'bg-red-50 border-red-400 ring-2 ring-red-500/20 text-red-700 font-medium'
                        : 'border-gray-200 text-gray-600 hover:border-red-300 hover:bg-red-50/50'
                    }`}
                  >
                    <span>{t.icon}</span>
                    {t.name}
                    {t.pricing?.mode !== 'free' && (
                      <span className="px-1 rounded bg-amber-100 text-amber-700 text-[10px]">
                        {t.pricing_label}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400">🔥{t.usage || 0}</span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation()
                        openDocTpl(t.id)
                      }}
                      className="ml-0.5 text-red-400 hover:text-red-600"
                    >
                      📖
                    </span>
                  </button>
                ))}
            </div>
          </div>
          <div className="space-y-3">
            <input
              value={contractTitle}
              onChange={(e) => setContractTitle(e.target.value)}
              placeholder="合同名称（可选）"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-red-500/20"
            />
            <textarea
              value={contractText}
              onChange={(e) => setContractText(e.target.value)}
              placeholder="粘贴合同全文（至少20字）…"
              rows={10}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500/20 focus:border-red-500 outline-none resize-none"
            />
            <Button
              variant="primary"
              icon={Sparkles}
              loading={reviewing}
              onClick={doReview}
              disabled={contractText.length < 20}
            >
              AI智能审查
            </Button>
          </div>
          {contractResult && (
            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <ShareButton
                  content={`# 合同审查报告：${contractTitle || '合同审查'}\n\n整体风险：${RISK_LABELS[contractResult.risk_level] || contractResult.risk_level}\n${contractResult.summary || ''}\n\n${(contractResult.risks || [])
                    .map((r) => `- 【${RISK_LABELS[r.risk] || r.risk}】${r.clause}：${r.issue}\n  建议：${r.suggestion}`)
                    .join('\n')}\n\n> 由小团智能平台 AI 合同审查生成 · ${new Date().toLocaleString()}`}
                  title={`合同审查：${contractTitle || '合同审查'}`}
                  contentType="pdf"
                />
                <button
                  onClick={async () => {
                    const md = `# 合同审查报告：${contractTitle || '合同审查'}\n\n整体风险：${RISK_LABELS[contractResult.risk_level] || contractResult.risk_level}\n${contractResult.summary || ''}\n\n${(contractResult.risks || [])
                      .map((r) => `- 【${RISK_LABELS[r.risk] || r.risk}】${r.clause}：${r.issue}\n  建议：${r.suggestion}`)
                      .join('\n')}`
                    try {
                      await navigator.clipboard.writeText(md)
                      toast.success('审查报告已复制')
                    } catch { toast.error('复制失败') }
                  }}
                  className="text-xs text-gray-500 hover:text-red-600 px-2 py-1 rounded-lg hover:bg-red-50 border border-gray-200"
                >
                  📋 复制报告
                </button>
                <button
                  onClick={() => {
                    const md = `# 合同审查报告：${contractTitle || '合同审查'}\n\n整体风险：${RISK_LABELS[contractResult.risk_level] || contractResult.risk_level}\n${contractResult.summary || ''}\n\n${(contractResult.risks || [])
                      .map((r) => `- 【${RISK_LABELS[r.risk] || r.risk}】${r.clause}：${r.issue}\n  建议：${r.suggestion}`)
                      .join('\n')}`
                    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `合同审查-${contractTitle || Date.now()}.md`
                    document.body.appendChild(a)
                    a.click()
                    a.remove()
                    setTimeout(() => URL.revokeObjectURL(url), 3000)
                  }}
                  className="text-xs text-gray-500 hover:text-red-600 px-2 py-1 rounded-lg hover:bg-red-50 border border-gray-200"
                >
                  📄 导出报告
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge color={riskColor(contractResult.risk_level)}>
                  整体风险：{RISK_LABELS[contractResult.risk_level] || contractResult.risk_level}
                </Badge>
                {contractResult.level_count && (
                  <div className="flex items-center gap-1.5">
                    {contractResult.level_count.high > 0 && (
                      <Badge color="red">高危 {contractResult.level_count.high}</Badge>
                    )}
                    {contractResult.level_count.medium > 0 && (
                      <Badge color="amber">中危 {contractResult.level_count.medium}</Badge>
                    )}
                    {contractResult.level_count.low > 0 && (
                      <Badge color="green">低危 {contractResult.level_count.low}</Badge>
                    )}
                  </div>
                )}
                <span className="text-sm text-gray-600 flex-1 min-w-0">
                  {contractResult.summary}
                </span>
              </div>
              {contractResult.risks?.map((r, i) => (
                <div key={i} className="p-3 rounded-lg border text-sm">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <Badge color={riskColor(r.risk)}>{RISK_LABELS[r.risk] || r.risk}</Badge>
                    <Badge color={partyColor(r.party)} title="责任倾向">
                      {r.party || '未标注'}
                    </Badge>
                    <span className="font-medium">{r.clause}</span>
                  </div>
                  <p className="text-gray-600 text-xs mb-1">&ldquo;{r.content}&rdquo;</p>
                  <p className="text-red-600 text-xs mb-1">{r.issue}</p>
                  <p className="text-emerald-600 text-xs">建议：{r.suggestion}</p>
                </div>
              ))}
              {contractResult.signature_advice && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  {contractResult.signature_advice}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* 简历优化 */}
      {tab === 'resume' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-violet-500" /> AI简历优化
            <span className="ml-auto text-[11px] font-normal text-gray-400 flex items-center gap-1">
              <Wand2 className="w-3.5 h-3.5" /> 模板一键填充示例简历
            </span>
          </h3>
          {/* 简历优化模板：一键填充示例 + 注入岗位要点 */}
          <div className="mb-3">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {docTpls
                .filter((t) => t.category === '简历优化')
                .map((t) => (
                  <button
                    key={t.id}
                    onClick={() => applyDocTplTo(t, 'resume')}
                    title={t.desc}
                    className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full border text-xs transition-all ${
                      docTplId === t.id
                        ? 'bg-violet-50 border-violet-400 ring-2 ring-violet-500/20 text-violet-700 font-medium'
                        : 'border-gray-200 text-gray-600 hover:border-violet-300 hover:bg-violet-50/50'
                    }`}
                  >
                    <span>{t.icon}</span>
                    {t.name}
                    {t.pricing?.mode !== 'free' && (
                      <span className="px-1 rounded bg-amber-100 text-amber-700 text-[10px]">
                        {t.pricing_label}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400">🔥{t.usage || 0}</span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation()
                        openDocTpl(t.id)
                      }}
                      className="ml-0.5 text-violet-400 hover:text-violet-600"
                    >
                      📖
                    </span>
                  </button>
                ))}
            </div>
          </div>
          <div className="space-y-3">
            <input
              value={targetPosition}
              onChange={(e) => setTargetPosition(e.target.value)}
              placeholder="目标岗位（可选，如：前端工程师）"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-violet-500/20"
            />
            <textarea
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="粘贴简历全文（至少20字）…"
              rows={10}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none"
            />
            <Button
              variant="primary"
              icon={Sparkles}
              loading={optimizing}
              onClick={doOptimize}
              disabled={resumeText.length < 20}
            >
              AI优化简历
            </Button>
          </div>
          {resumeResult && (
            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <ShareButton
                  content={`# 简历优化报告：${targetPosition || '简历'}\n\n综合评分：${resumeResult.overall_score || '-'}\n${resumeResult.summary || ''}\n\n## 亮点\n${(resumeResult.highlights || []).map((h) => `- ${h}`).join('\n')}\n\n## 优化建议\n${(resumeResult.suggestions || [])
                    .map((s) => `- 原文：${s.original}\n  改写：${s.rewrite}\n  理由：${s.reason}`)
                    .join('\n')}\n\n> 由小团智能平台 AI 简历优化生成 · ${new Date().toLocaleString()}`}
                  title={`简历优化：${targetPosition || '简历'}`}
                  contentType="pdf"
                />
                <button
                  onClick={async () => {
                    const md = `# 简历优化报告：${targetPosition || '简历'}\n\n综合评分：${resumeResult.overall_score || '-'}\n${resumeResult.summary || ''}\n\n## 亮点\n${(resumeResult.highlights || []).map((h) => `- ${h}`).join('\n')}\n\n## 优化建议\n${(resumeResult.suggestions || [])
                      .map((s) => `- 原文：${s.original}\n  改写：${s.rewrite}\n  理由：${s.reason}`)
                      .join('\n')}`
                    try {
                      await navigator.clipboard.writeText(md)
                      toast.success('优化报告已复制')
                    } catch { toast.error('复制失败') }
                  }}
                  className="text-xs text-gray-500 hover:text-red-600 px-2 py-1 rounded-lg hover:bg-red-50 border border-gray-200"
                >
                  📋 复制报告
                </button>
                <button
                  onClick={() => {
                    const md = `# 简历优化报告：${targetPosition || '简历'}\n\n综合评分：${resumeResult.overall_score || '-'}\n${resumeResult.summary || ''}\n\n## 亮点\n${(resumeResult.highlights || []).map((h) => `- ${h}`).join('\n')}\n\n## 优化建议\n${(resumeResult.suggestions || [])
                      .map((s) => `- 原文：${s.original}\n  改写：${s.rewrite}\n  理由：${s.reason}`)
                      .join('\n')}`
                    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `简历优化-${targetPosition || Date.now()}.md`
                    document.body.appendChild(a)
                    a.click()
                    a.remove()
                    setTimeout(() => URL.revokeObjectURL(url), 3000)
                  }}
                  className="text-xs text-gray-500 hover:text-violet-600 px-2 py-1 rounded-lg hover:bg-violet-50 border border-gray-200"
                >
                  📄 导出报告
                </button>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200">
                <div className="text-3xl font-bold text-violet-600">
                  {resumeResult.overall_score || '-'}
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-800">综合评分</div>
                  <div className="text-xs text-gray-500">{resumeResult.summary}</div>
                </div>
              </div>

              {resumeResult.dimensions?.map((d, i) => (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-gray-50 text-sm">
                  <span className="w-20 text-gray-600 text-xs">{d.name}</span>
                  <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-violet-500 rounded-full transition-all"
                      style={{ width: `${d.score}%` }}
                    />
                  </div>
                  <span className="w-8 text-right font-bold text-xs text-violet-600">
                    {d.score}
                  </span>
                  <span className="text-xs text-gray-400 flex-1">{d.comment}</span>
                </div>
              ))}

              {resumeResult.optimized_summary && (
                <div className="p-3 rounded-lg bg-violet-50 border border-violet-200 text-sm">
                  <div className="font-medium text-violet-800 mb-1">优化版自我评价</div>
                  <p className="text-gray-700">{resumeResult.optimized_summary}</p>
                </div>
              )}

              {resumeResult.suggestions?.map((s, i) => (
                <div key={i} className="p-3 rounded-lg border text-sm">
                  <div className="flex items-start gap-2">
                    <FileWarning className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-xs text-gray-400 line-through mb-1">{s.original}</p>
                      <p className="text-xs text-emerald-600 font-medium">{s.rewrite}</p>
                      <p className="text-xs text-gray-400 mt-1">{s.reason}</p>
                    </div>
                  </div>
                </div>
              ))}

              {resumeResult.highlights?.length > 0 && (
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm">
                  <div className="font-medium text-emerald-800 mb-1">优化亮点</div>
                  {resumeResult.highlights.map((h, i) => (
                    <div key={i} className="flex items-center gap-1.5 text-xs text-emerald-700">
                      <Check className="w-3 h-3 flex-shrink-0" /> {h}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* 任务记录（历史） */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <History className="w-4 h-4 text-gray-500" /> 任务记录
            <span className="text-xs text-gray-400 font-normal">
              （压缩 / 合同审查 / 简历优化会在这里留痕）
            </span>
          </h3>
          <Button
            variant="secondary"
            size="sm"
            icon={Loader2}
            onClick={loadJobs}
            disabled={jobsLoading}
          >
            刷新
          </Button>
        </div>
        {jobsLoading ? (
          <div className="text-center py-6 text-gray-400 text-sm">加载中…</div>
        ) : jobs.length === 0 ? (
          <Empty
            icon={History}
            title="暂无任务记录"
            description="使用压缩 / 合同审查 / 简历优化后这里会显示历史记录"
          />
        ) : (
          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {jobs.map((j) => (
              <div
                key={j.id}
                className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-4 h-4 text-white" />
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {JOB_LABELS[j.job_type] || j.job_type}
                    <span className="text-xs text-gray-400 font-normal ml-2">
                      #{j.original_filename || j.id.slice(0, 8)}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400">
                    {j.created_at?.replace('T', ' ').slice(0, 16)}
                  </div>
                </div>
                <Badge color={JOB_STATUS_COLOR[j.status] || 'gray'}>{j.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ── 文档模板详情 Modal ── */}
      <Modal
        open={!!docTplInfo}
        onClose={() => setDocTplInfo(null)}
        title={`${docTplInfo?.icon || '📄'} ${docTplInfo?.name || '文档模板'}`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDocTplInfo(null)}>
              知道了
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                applyDocTplTo(
                  docTplInfo,
                  docTplInfo?.category === '简历优化' ? 'resume' : 'contract'
                )
                setDocTplInfo(null)
              }}
            >
              应用此模板
            </Button>
          </>
        }
      >
        {docTplInfo && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge color={docTplInfo.category === '简历优化' ? 'violet' : 'red'}>
                {docTplInfo.category_label}
              </Badge>
              <Badge color={docTplInfo.pricing?.mode !== 'free' ? 'amber' : 'green'}>
                {docTplInfo.pricing_label}
              </Badge>
              <Badge color="gray">🔥 使用 {docTplInfo.usage || 0} 次</Badge>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">{docTplInfo.desc}</p>
            {docTplInfo.position && (
              <div className="p-2.5 rounded-lg bg-gray-50">
                <span className="text-[11px] text-gray-400">目标岗位：</span>
                <span className="text-sm font-medium text-gray-800">{docTplInfo.position}</span>
              </div>
            )}
            {docTplInfo.sample && (
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1.5">📋 示例文档（点击应用）</div>
                <button
                  onClick={() => {
                    applyDocTplTo(docTplInfo, docTplInfo.category === '简历优化' ? 'resume' : 'contract')
                    setDocTplInfo(null)
                  }}
                  className="w-full text-left px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:border-purple-300 hover:bg-purple-50/50 transition-all max-h-40 overflow-y-auto whitespace-pre-wrap"
                >
                  {docTplInfo.sample.slice(0, 600)}
                  {docTplInfo.sample.length > 600 ? '…' : ''}
                </button>
              </div>
            )}
            {docTplInfo.pro_tips && (
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
                <div className="text-xs font-medium text-amber-700 mb-1">🎯 专家审查/优化要点</div>
                <div className="text-xs text-amber-700/80 leading-relaxed">
                  {docTplInfo.pro_tips}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
