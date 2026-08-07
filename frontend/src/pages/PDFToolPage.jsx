import React, { useState, useEffect } from 'react'
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
} from 'lucide-react'
import { Card, Button, PageHeader, Badge, Empty, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const TABS = [
  { id: 'merge', label: 'PDF合并', icon: Merge, desc: '多个PDF文件合并为一个' },
  { id: 'split', label: 'PDF拆分', icon: Scissors, desc: '按页码范围拆分PDF' },
  { id: 'extract', label: '表格提取', icon: Table, desc: '从PDF提取表格为CSV' },
  { id: 'contract', label: '合同审查', icon: Shield, desc: 'AI逐条审查+修改建议' },
  { id: 'resume', label: '简历优化', icon: UserCheck, desc: 'AI简历评分+优化建议' },
]

export default function PDFToolPage() {
  const toast = useToast()
  const [tab, setTab] = useState('merge')

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
      })
      setContractResult(res.data)
      toast.success(`审查完成 — 风险等级：${res.data.risk_level}`)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setReviewing(false)
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="PDF 工具集"
        description="PDF合并/拆分/表格提取 + AI合同审查 + AI简历优化 — 文档处理全家桶"
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

      {/* 合同审查 */}
      {tab === 'contract' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Shield className="w-4 h-4 text-red-500" /> AI合同审查
          </h3>
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
              <div className="flex items-center gap-2">
                <Badge color={riskColor(contractResult.risk_level)}>
                  风险等级：{contractResult.risk_level}
                </Badge>
                <span className="text-sm text-gray-600">{contractResult.summary}</span>
              </div>
              {contractResult.risks?.map((r, i) => (
                <div key={i} className="p-3 rounded-lg border text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge color={riskColor(r.risk)}>{r.risk}</Badge>
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
          </h3>
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
              （合同审查 / 简历优化会在这里留痕）
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
            description="使用合同审查 / 简历优化后这里会显示历史记录"
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
    </div>
  )
}
