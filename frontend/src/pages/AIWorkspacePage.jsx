import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import MarkdownRenderer from '../components/MarkdownRenderer'
import CodeTreeView from '../components/CodeTreeView'
import {
  FileText, Code2, TestTube2, Send, Loader2, BookOpen, MessageSquare,
  Copy, Sparkles, Bot, User, Edit2, Save, X, FolderGit2, ListTodo,
  Download, Layers, ArrowRight, RefreshCw, ShieldCheck, Rocket, ExternalLink,
  CheckCircle2, XCircle, GitBranch, Wrench, Undo2, SkipForward,
} from 'lucide-react'
import RichTextEditor from '../components/RichTextEditor'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime, copyToClipboard } from '../lib/format'
import { Button, Empty, PageHeader, Modal } from '../components/ui'

const PIPELINE = ['prd', 'review', 'td', 'test', 'code', 'review_code']

// 流水线阶段顺序与产物字段映射（状态条可视化 + 需求变更传播）
const PIPELINE_STAGES = [
  { key: 'prd', label: 'PRD', field: 'prd_text' },
  { key: 'review', label: 'PRD 审查', field: 'review_report' },
  { key: 'td', label: '技术方案', field: 'tech_design' },
  { key: 'test', label: '测试用例', field: 'test_cases' },
  { key: 'code', label: '代码生成', field: 'code' },
  { key: 'review_code', label: '代码审查', field: 'code_review' },
]

const TABS = {
  prd: { label: 'PRD 编写', icon: FileText, color: 'blue', next: 'review', nextLabel: '下一步: 审查' },
  review: { label: 'PRD 审查', icon: BookOpen, color: 'emerald', next: 'td', nextLabel: '下一步: 技术方案' },
  td: { label: '技术方案', icon: Code2, color: 'indigo', next: 'test', nextLabel: '下一步: 测试用例' },
  test: { label: '测试用例', icon: TestTube2, color: 'green', next: 'code', nextLabel: '下一步: 代码生成' },
  code: { label: '代码生成', icon: Layers, color: 'purple', next: 'review_code', nextLabel: '下一步: 代码审查' },
  review_code: { label: '代码审查', icon: ShieldCheck, color: 'amber', next: 'code', nextLabel: '回到代码生成' },
}

// 全静态 class 名，避免 Tailwind purge 丢失动态颜色
const COLOR_MAP = {
  blue: { from: 'from-blue-600', to: 'to-indigo-600', light: 'bg-blue-50', border: 'border-blue-100', text: 'text-blue-700', icon: 'text-blue-600', active: 'border-blue-600 text-blue-600', ring: 'focus:border-blue-500 focus:ring-blue-500/10' },
  emerald: { from: 'from-emerald-600', to: 'to-emerald-600', light: 'bg-emerald-50', border: 'border-emerald-100', text: 'text-emerald-700', icon: 'text-emerald-600', active: 'border-emerald-600 text-emerald-600', ring: 'focus:border-emerald-500 focus:ring-emerald-500/10' },
  indigo: { from: 'from-indigo-600', to: 'to-purple-600', light: 'bg-indigo-50', border: 'border-indigo-100', text: 'text-indigo-700', icon: 'text-indigo-600', active: 'border-indigo-600 text-indigo-600', ring: 'focus:border-indigo-500 focus:ring-indigo-500/10' },
  green: { from: 'from-green-600', to: 'to-emerald-600', light: 'bg-green-50', border: 'border-green-100', text: 'text-green-700', icon: 'text-green-600', active: 'border-green-600 text-green-600', ring: 'focus:border-green-500 focus:ring-green-500/10' },
  purple: { from: 'from-purple-600', to: 'to-indigo-600', light: 'bg-purple-50', border: 'border-purple-100', text: 'text-purple-700', icon: 'text-purple-600', active: 'border-purple-600 text-purple-600', ring: 'focus:border-purple-500 focus:ring-purple-500/10' },
  amber: { from: 'from-amber-500', to: 'to-orange-600', light: 'bg-amber-50', border: 'border-amber-100', text: 'text-amber-700', icon: 'text-amber-600', active: 'border-amber-500 text-amber-600', ring: 'focus:border-amber-500 focus:ring-amber-500/10' },
}

function initState() {
  return {
    messages: [],
    chatInput: '',
    repoPath: '/Users/yanping.ma/GolandProjects/sponge',
    prdText: '',
    userInput: '',
    techDesign: '',
    codeText: '',
    language: 'go',
    loading: false,
    editingMsgIdx: null,
    editContent: '',
  }
}

// 一键部署进度弹窗：轮询流水线运行日志，展示构建/启动/健康检查进度；失败后支持 AI 诊断修复
function DeployModal({ info, onClose }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(true)
  const [trackingRunId, setTrackingRunId] = useState(null)
  const [fixing, setFixing] = useState(false)

  useEffect(() => {
    if (!info) return
    setTrackingRunId(info.runId)
    setRun(null)
    setLoading(true)
  }, [info])

  useEffect(() => {
    if (!info || !trackingRunId) return
    let alive = true
    let timer = null
    const fetchRun = async () => {
      try {
        const res = await api.get(`/api/pipelines/${info.pipelineId}/runs`)
        if (!alive) return
        const found = (res.data || []).find((r) => r.id === trackingRunId) || null
        setRun(found)
        if (found && found.status !== 'running') clearInterval(timer)
      } catch {
        // 轮询失败静默，下次重试
      } finally {
        if (alive) setLoading(false)
      }
    }
    fetchRun()
    timer = setInterval(fetchRun, 3000)
    return () => { alive = false; clearInterval(timer) }
  }, [info, trackingRunId])

  const status = run?.status || 'running'
  const done = status === 'success'
  const failed = status === 'failed'
  const logText = run?.log || ''
  // 部署失败后自动修复（config.auto_fix 开启）：同一运行内进入 AI 诊断修复循环
  const autoFixing = status === 'running' && logText.includes('AI 诊断修复')
  const fixRound = (logText.match(/第 (\d+)\/3 轮 AI 诊断修复/) || [])[1] || ''

  const handleManualFix = async () => {
    setFixing(true)
    try {
      const res = await api.post(`/api/pipelines/${info.pipelineId}/auto-fix`)
      setTrackingRunId(res.data.id)
      setRun(null)
      setLoading(true)
      toast.success('AI 诊断修复已启动，正在分析日志并修复…')
    } catch (e) {
      toast.error(`修复启动失败：${e.message}`)
    } finally {
      setFixing(false)
    }
  }

  return (
    <Modal open={!!info} onClose={onClose} title={`沙箱部署 - ${info?.name || ''}`} size="lg">
      <div className="space-y-4">
        <div className="flex items-center gap-2 flex-wrap">
          {done ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-600 border border-emerald-200">
              <CheckCircle2 className="w-3.5 h-3.5" /> 部署成功
            </span>
          ) : failed ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-600 border border-red-200">
              <XCircle className="w-3.5 h-3.5" /> 部署失败
            </span>
          ) : autoFixing ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-600 border border-amber-200">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> AI 自动修复中{fixRound ? `（第 ${fixRound}/3 轮）` : ''}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-600 border border-blue-200">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> 部署中（首次构建镜像约 1-3 分钟）
            </span>
          )}
          {autoFixing && (
            <span className="text-xs text-amber-600">AI 正在分析日志、修改代码并重新部署，全程可关闭弹窗后在流水线页跟踪</span>
          )}
        </div>

        {done && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-emerald-800">服务已在沙箱容器中运行</p>
              <p className="text-xs text-emerald-600 mt-0.5">可通过下方地址访问，也可在「CI/CD 流水线」「沙箱运行」中停止或管理</p>
            </div>
            <a
              href={`http://localhost:${info.port}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white text-xs font-medium rounded-lg hover:bg-emerald-700 transition-colors flex-shrink-0"
            >
              <ExternalLink className="w-3.5 h-3.5" /> 访问服务
            </a>
          </div>
        )}

        {failed && (
          <div className="space-y-2">
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 leading-relaxed">
              部署未成功。可点击「AI 诊断修复」自动分析日志、修改代码并重新部署（最多 3 轮），也可查看下方日志手动定位问题。
            </div>
            <button
              onClick={handleManualFix}
              disabled={fixing}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-gradient-to-r from-amber-500 to-orange-600 text-white text-xs font-medium rounded-lg hover:opacity-90 transition-all shadow-sm disabled:opacity-60"
            >
              {fixing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wrench className="w-3.5 h-3.5" />}
              {fixing ? '修复启动中…' : 'AI 诊断修复'}
            </button>
          </div>
        )}

        <pre className="bg-gray-900 text-green-400 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[45vh] whitespace-pre-wrap">
          {loading ? '加载中…' : (run?.log || '（等待日志输出…）')}
        </pre>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>关闭</Button>
          <Button variant="gradient" icon={GitBranch} onClick={() => { onClose(); navigate('/pipelines') }}>去 CI/CD 流水线</Button>
        </div>
      </div>
    </Modal>
  )
}

// 一句话全自动：输入功能描述 → 后台串行执行 6 阶段 + 自动部署，实时展示进度与日志
const AUTO_RUN_STEPS = [
  { key: 'prd', label: 'PRD 生成' },
  { key: 'review', label: 'PRD 审查' },
  { key: 'td', label: '技术方案' },
  { key: 'test', label: '测试用例' },
  { key: 'code', label: '代码生成' },
  { key: 'review_code', label: '代码审查' },
  { key: 'deploy', label: '沙箱部署' },
]

function AutoRunModal({ open, onClose }) {
  const toast = useToast()
  const [desc, setDesc] = useState('')
  const [name, setName] = useState('')
  const [language, setLanguage] = useState('python')
  const [deploy, setDeploy] = useState(true)
  const [starting, setStarting] = useState(false)
  const [runId, setRunId] = useState(null)
  const [run, setRun] = useState(null)

  const isBusy = run && ['running', 'stopping'].includes(run.status)
  const progress = run?.stage_progress || {}

  // 阶段状态：done 完成 / running 进行中 / failed 失败 / skipped 跳过 / wait 等待
  const stageState = (key) => {
    if (progress[key] === 'done') return 'done'
    if (progress[key] === 'running') return 'running'
    if (progress[key] === 'failed') return 'failed'
    if (progress[key] === 'skipped') return 'skipped'
    if (run?.status === 'running' && run?.current_stage === key) return 'running'
    if (run?.status === 'failed' && run?.current_stage === key) return 'failed'
    return 'wait'
  }

  const startRun = async () => {
    if (!desc.trim()) { toast.error('请先描述你想要做的功能'); return }
    setStarting(true)
    try {
      const res = await api.post('/api/auto-run', {
        name: name.trim() || undefined,
        description: desc.trim(),
        language,
        deploy,
        target_stage: 'deploy',
      })
      setRunId(res.data.run_id)
      setRun({ status: 'running', current_stage: 'prd', stage_progress: {}, log: '流水线已启动…' })
      toast.success('🚀 全自动流水线已启动，正在生成 PRD…')
    } catch (e) {
      toast.error(`启动失败：${e.message}`)
    } finally {
      setStarting(false)
    }
  }

  const stopRun = async () => {
    try {
      await api.post(`/api/auto-runs/${runId}/stop`)
      toast.success('正在停止，将在当前阶段结束后生效')
    } catch (e) {
      toast.error(`停止失败：${e.message}`)
    }
  }

  // 轮询运行进度
  useEffect(() => {
    if (!open || !runId) return
    let alive = true
    let timer = null
    const fetchRun = async () => {
      try {
        const res = await api.get(`/api/auto-runs/${runId}`)
        if (!alive) return
        setRun(res.data)
        if (['success', 'failed', 'stopped'].includes(res.data.status)) clearInterval(timer)
      } catch { /* 轮询失败静默，下次重试 */ }
    }
    fetchRun()
    timer = setInterval(fetchRun, 3000)
    return () => { alive = false; clearInterval(timer) }
  }, [open, runId])

  // 每次打开时重置（关闭后重新开始新流程）
  useEffect(() => {
    if (open) { setRunId(null); setRun(null) }
  }, [open])

  const close = () => { setRunId(null); setRun(null); onClose() }

  return (
    <Modal open={open} onClose={close}>
      <div className="p-5 space-y-4 w-full max-w-2xl">
        <div className="flex items-center gap-2.5">
          <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-600 to-fuchsia-600 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </span>
          <div>
            <h2 className="text-lg font-bold text-gray-900">一句话全自动</h2>
            <p className="text-xs text-gray-500">说出你想要做的功能，AI 自动完成全部研发流程</p>
          </div>
        </div>

        {!runId ? (
          <>
            <div className="flex flex-wrap gap-1.5">
              {['做一个待办事项网页应用，支持增删改查', '做一个天气查询小工具', '做一个记账本 API 服务'].map((ex) => (
                <button
                  key={ex}
                  onClick={() => setDesc(ex)}
                  className="px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-600 text-xs border border-indigo-100 hover:bg-indigo-100 transition-colors"
                >
                  {ex}
                </button>
              ))}
            </div>
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={4}
              placeholder="例如：做一个待办事项管理网页应用，支持添加、编辑、删除和标记完成，数据保存在本地文件"
              className="w-full p-3 text-sm border border-gray-200 rounded-xl focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/10 outline-none resize-none"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="应用名（可选，默认取描述）"
                className="px-3 py-2 text-sm border border-gray-200 rounded-xl focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/10 outline-none"
              />
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="px-3 py-2 text-sm border border-gray-200 rounded-xl bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/10 outline-none"
              >
                <option value="python">Python</option>
                <option value="go">Go</option>
                <option value="java">Java</option>
                <option value="typescript">TypeScript</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" checked={deploy} onChange={(e) => setDeploy(e.target.checked)} className="w-4 h-4 accent-indigo-600" />
              自动部署到沙箱（生成可访问的服务地址）
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="secondary" onClick={close}>取消</Button>
              <Button variant="gradient" icon={Sparkles} onClick={startRun} disabled={starting}>
                {starting ? '启动中…' : '开始全自动实现'}
              </Button>
            </div>
          </>
        ) : (
          <>
            {/* 7 步进度条 */}
            <div className="grid grid-cols-7 gap-1.5">
              {AUTO_RUN_STEPS.map((st) => {
                const stt = stageState(st.key)
                return (
                  <div key={st.key} className="flex flex-col items-center gap-1.5">
                    <span className={`w-9 h-9 rounded-full flex items-center justify-center border-2 transition-all ${
                      stt === 'done' ? 'bg-emerald-500 border-emerald-500 text-white'
                        : stt === 'running' ? 'bg-indigo-50 border-indigo-500 text-indigo-600'
                        : stt === 'failed' ? 'bg-red-500 border-red-500 text-white'
                        : stt === 'skipped' ? 'bg-gray-100 border-gray-300 text-gray-400'
                        : 'bg-white border-gray-200 text-gray-300'
                    }`}>
                      {stt === 'done' ? <CheckCircle2 className="w-4 h-4" />
                        : stt === 'running' ? <Loader2 className="w-4 h-4 animate-spin" />
                        : stt === 'failed' ? <XCircle className="w-4 h-4" />
                        : <span className="text-[10px] font-medium">{stt === 'skipped' ? '—' : '·'}</span>}
                    </span>
                    <span className={`text-[10px] text-center leading-tight ${
                      stt === 'done' ? 'text-emerald-700 font-medium' : stt === 'running' ? 'text-indigo-700 font-medium' : stt === 'failed' ? 'text-red-600 font-medium' : 'text-gray-400'
                    }`}>{st.label}</span>
                  </div>
                )
              })}
            </div>

            {/* 状态汇总 */}
            <div className="p-3.5 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
              {run?.status === 'success' ? (
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <span className="text-sm font-medium text-emerald-700 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" /> 全流程完成！所有产物已保存到需求
                  </span>
                  {run.port > 0 && (
                    <a href={`http://localhost:${run.port}`} target="_blank" rel="noreferrer"
                       className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white text-xs font-medium rounded-lg hover:bg-emerald-700 transition-colors">
                      <ExternalLink className="w-3.5 h-3.5" /> 访问服务
                    </a>
                  )}
                </div>
              ) : run?.status === 'failed' ? (
                <div className="text-sm text-red-700 flex items-start gap-1.5">
                  <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>流程失败：{run.error || '未知错误'}（已完成阶段产物已保存，可在 AI 工作台中手动继续）</span>
                </div>
              ) : run?.status === 'stopped' ? (
                <span className="text-sm font-medium text-amber-700 flex items-center gap-1.5">
                  <XCircle className="w-4 h-4" /> 已手动停止（已完成阶段产物已保存）
                </span>
              ) : (
                <span className="text-sm font-medium text-indigo-700 flex items-center gap-1.5">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {run?.status === 'stopping' ? '正在停止…' : 'AI 正在全流程自动实现中，请稍候（约 2-5 分钟）…'}
                </span>
              )}
            </div>

            {/* 日志 */}
            <pre className="bg-gray-900 text-green-400 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[40vh] whitespace-pre-wrap">
              {run?.log || '加载中…'}
            </pre>

            <div className="flex justify-end gap-2">
              {isBusy && <Button variant="secondary" onClick={stopRun}>停止</Button>}
              <Button variant="gradient" onClick={close}>关闭</Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}

// 需求产物查看弹窗：PRD/审查/技术方案/测试用例/代码/代码审查 + 自动化测试记录，去黑盒
const ARTIFACT_FIELDS = [
  { key: 'prd', label: 'PRD', field: 'prd_text', mono: false },
  { key: 'review', label: 'PRD 审查', field: 'review_report', mono: false },
  { key: 'td', label: '技术方案', field: 'tech_design', mono: false },
  { key: 'test', label: '测试用例', field: 'test_cases', mono: false },
  { key: 'code', label: '代码', field: 'code', mono: true },
  { key: 'review_code', label: '代码审查', field: 'code_review', mono: false },
]

function ArtifactsModal({ open, onClose, requirement, testRuns, testLoading, onRefreshTests }) {
  const [atab, setAtab] = useState('prd')
  const [copyOk, setCopyOk] = useState(false)
  useEffect(() => { if (open) { setAtab('prd'); setCopyOk(false) } }, [open])

  const stage = ARTIFACT_FIELDS.find((s) => s.key === atab)
  const content = requirement?.[stage?.field] || ''
  const stageStatus = requirement?.pipeline_status
    ? (typeof requirement.pipeline_status === 'string'
      ? (() => { try { return JSON.parse(requirement.pipeline_status) } catch { return {} } })()
      : requirement.pipeline_status)
    : {}

  const copyContent = async () => {
    if (!content) return
    await copyToClipboard(content)
    setCopyOk(true)
    setTimeout(() => setCopyOk(false), 1500)
  }

  return (
    <Modal open={open} onClose={onClose} title={`需求产物 - ${requirement?.name || ''}`} size="lg">
      <div className="flex items-center gap-1.5 border-b border-gray-200 pb-3 mb-4 overflow-x-auto">
        {ARTIFACT_FIELDS.map((s) => {
          const has = !!requirement?.[s.field]
          const st = stageStatus[s.key]?.status
          return (
            <button
              key={s.key}
              onClick={() => setAtab(s.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                atab === s.key ? 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200' : 'hover:bg-gray-50 text-gray-600'
              }`}
              title={st === 'stale' ? '上游已变更，建议重新生成' : has ? '已生成' : '未生成'}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${st === 'stale' ? 'bg-amber-500' : has ? 'bg-emerald-500' : 'bg-gray-300'}`} />
              {s.label}
            </button>
          )
        })}
        <button
          onClick={() => setAtab('tests')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
            atab === 'tests' ? 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200' : 'hover:bg-gray-50 text-gray-600'
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
          测试记录
          {testRuns?.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-semibold">{testRuns.length}</span>
          )}
        </button>
      </div>

      {atab === 'tests' ? (
        <div className="space-y-3 max-h-[55vh] overflow-y-auto">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500">自动化测试执行记录（部署流水线中的测试门禁与 AI 修复循环）</p>
            <button
              onClick={onRefreshTests}
              disabled={testLoading}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${testLoading ? 'animate-spin' : ''}`} /> 刷新
            </button>
          </div>
          {testLoading ? (
            <div className="py-10 text-center text-gray-400 text-sm">加载中…</div>
          ) : testRuns?.length ? (
            testRuns.map((r) => {
              const cases = Array.isArray(r.cases) ? r.cases : []
              const passed = cases.filter((c) => c.status === 'passed').length
              const failed = cases.filter((c) => c.status === 'failed' || c.status === 'error').length
              const skipped = cases.filter((c) => c.status === 'skipped').length
              return (
                <div key={r.id} className="rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-3 py-2 bg-gray-50 flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-gray-700 flex items-center gap-1.5">
                      {r.status === 'passed'
                        ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                        : <XCircle className="w-3.5 h-3.5 text-red-500" />}
                      {r.status === 'passed' ? '通过' : '失败'}
                      <span className="text-gray-400 font-normal">· {r.summary || '—'}</span>
                      {cases.length > 0 && (
                        <span className="flex items-center gap-1">
                          <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[10px] font-semibold">✓ {passed}</span>
                          {failed > 0 && (
                            <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 text-[10px] font-semibold">✗ {failed}</span>
                          )}
                          {skipped > 0 && (
                            <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 text-[10px] font-semibold">⊘ {skipped}</span>
                          )}
                        </span>
                      )}
                    </span>
                    <span className="text-[10px] text-gray-400">{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</span>
                  </div>
                  {cases.length > 0 && (
                    <div className="border-t border-gray-100 divide-y divide-gray-50 max-h-[30vh] overflow-y-auto">
                      {cases.map((c, i) => {
                        const isFail = c.status === 'failed' || c.status === 'error'
                        return (
                          <div key={`${c.path || c.name}-${i}`} className="px-3 py-1.5 flex items-start gap-2 hover:bg-gray-50">
                            {c.status === 'passed' ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                            ) : c.status === 'skipped' ? (
                              <SkipForward className="w-3.5 h-3.5 text-gray-400 mt-0.5 flex-shrink-0" />
                            ) : (
                              <XCircle className="w-3.5 h-3.5 text-red-500 mt-0.5 flex-shrink-0" />
                            )}
                            <div className="min-w-0 flex-1">
                              <div className="text-xs text-gray-700 font-mono break-all">{c.name || c.path}</div>
                              {isFail && c.message && (
                                <div className="text-[11px] text-red-600 mt-0.5 break-all leading-snug">{c.message}</div>
                              )}
                            </div>
                            <span className={`text-[10px] flex-shrink-0 mt-0.5 ${
                              c.status === 'passed' ? 'text-emerald-600' : c.status === 'skipped' ? 'text-gray-400' : 'text-red-500'
                            }`}>
                              {c.status === 'passed' ? '通过' : c.status === 'skipped' ? '跳过' : '失败'}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                  {r.log && (
                    <details className="border-t border-gray-100">
                      <summary className="px-3 py-1.5 text-[11px] text-gray-500 cursor-pointer hover:bg-gray-50 select-none">
                        查看完整执行日志
                      </summary>
                      <pre className="bg-gray-900 text-green-400 p-3 text-[11px] font-mono overflow-auto max-h-[28vh] whitespace-pre-wrap">
                        {r.log}
                      </pre>
                    </details>
                  )}
                </div>
              )
            })
          ) : (
            <div className="py-10 text-center text-gray-400 text-sm">
              暂无自动化测试记录。部署流水线开启「自动化测试」后，测试门禁与修复结果会记录在这里。
            </div>
          )}
        </div>
      ) : !content ? (
        <div className="py-14 text-center">
          <Empty
            icon={stage?.mono ? <Code2 className="w-8 h-8" /> : <FileText className="w-8 h-8" />}
            title={`${stage?.label || ''}尚未生成`}
            desc="切换到对应阶段页签生成后，产物会自动保存到需求，这里即可查看"
          />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-400">{content.length} 字符 · 与需求关联保存的产物一致</span>
            <button
              onClick={copyContent}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            >
              {copyOk ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              {copyOk ? '已复制' : '复制全文'}
            </button>
          </div>
          {stage?.mono ? (
            <CodeTreeView content={content} title={`${stage?.label}（按工程结构展示）`} />
          ) : (
            <div className="max-h-[55vh] overflow-y-auto rounded-xl border border-gray-200 p-4">
              <MarkdownRenderer content={content} />
            </div>
          )}
        </>
      )}
    </Modal>
  )
}

export default function AIWorkspacePage() {
  const toast = useToast()
  const [tab, setTab] = useState('prd')
  const [state, setState] = useState(() => ({ prd: initState(), review: initState(), td: initState(), test: initState(), code: initState(), review_code: initState() }))
  const [requirements, setRequirements] = useState([])
  const [reqLoading, setReqLoading] = useState(true)
  const [reqError, setReqError] = useState(null)
  const [selectedReqId, setSelectedReqId] = useState(null)
  const [deployInfo, setDeployInfo] = useState(null)
  const [autoRunOpen, setAutoRunOpen] = useState(false)
  const [artifactsOpen, setArtifactsOpen] = useState(false)
  const [testRuns, setTestRuns] = useState([])
  const [testLoading, setTestLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const s = state[tab]
  const update = (patch) => setState((prev) => ({ ...prev, [tab]: { ...prev[tab], ...patch } }))
  const tabInfo = TABS[tab]
  const c = COLOR_MAP[tabInfo.color]

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [s.messages, s.loading])

  const fetchRequirements = useCallback(async () => {
    setReqLoading(true)
    setReqError(null)
    try {
      const res = await api.get('/api/requirements')
      setRequirements(res.data || [])
    } catch (e) {
      setReqError(e)
    } finally {
      setReqLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRequirements()
    const params = new URLSearchParams(window.location.search)
    const reqFromUrl = params.get('requirement_id')
    if (reqFromUrl) setSelectedReqId(reqFromUrl)
    const t = params.get('tab')
    if (t && PIPELINE.includes(t)) setTab(t)
  }, [fetchRequirements])

  const selectedReq = requirements.find((r) => r.id === selectedReqId) || null

  // 加载需求的自动化测试执行记录
  const fetchTestRuns = useCallback(async () => {
    if (!selectedReqId) { setTestRuns([]); return }
    setTestLoading(true)
    try {
      const res = await api.get(`/api/requirements/${selectedReqId}/test-runs`)
      setTestRuns(res.data || [])
    } catch {
      setTestRuns([])
    } finally {
      setTestLoading(false)
    }
  }, [selectedReqId])

  const openArtifacts = () => {
    setArtifactsOpen(true)
    fetchTestRuns()
  }

  // 阶段状态：stale=上游变更需重新生成 / done=已有产物 / idle=未开始
  const stageStatus = (key) => {
    if (!selectedReq) return 'idle'
    let ps = selectedReq.pipeline_status || {}
    if (typeof ps === 'string') { try { ps = JSON.parse(ps) } catch { ps = {} } }
    if (ps[key]?.status === 'stale') return 'stale'
    const stage = PIPELINE_STAGES.find((s) => s.key === key)
    return selectedReq[stage.field] ? 'done' : 'idle'
  }

  // 从需求产物预填目标标签的输入区（仅当输入区为空时，避免覆盖用户正在编辑的内容）
  const prefillFromRequirement = (key, req) => {
    if (!req) return
    const patch = {}
    if (key === 'prd' && !state.prd.userInput) patch.userInput = req.description || ''
    else if (key === 'review' && !state.review.prdText) patch.prdText = req.prd_text || ''
    else if (key === 'td' && !state.td.prdText) patch.prdText = req.review_report || req.prd_text || ''
    else if (key === 'test') {
      if (!state.test.prdText) patch.prdText = req.prd_text || ''
      if (!state.test.techDesign) patch.techDesign = req.tech_design || ''
    } else if (key === 'code' && !state.code.techDesign) patch.techDesign = req.tech_design || ''
    else if (key === 'review_code' && !state.review_code.codeText) patch.codeText = req.code || ''
    if (Object.keys(patch).length > 0) {
      setState((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }))
    }
  }

  const handleTabChange = (key) => {
    setTab(key)
    const req = requirements.find((r) => r.id === selectedReqId)
    prefillFromRequirement(key, req)
  }

  const handleSelectRequirement = (reqId) => {
    setSelectedReqId(reqId)
    const req = requirements.find((r) => r.id === reqId)
    prefillFromRequirement(tab, req)
  }

  const saveToRequirement = async (stage, content) => {
    if (!selectedReqId) return null
    try {
      const res = await api.post(`/api/requirements/${selectedReqId}/pipeline-output`, { stage, content })
      toast.success(`已保存到需求「${selectedReq?.name || selectedReqId}」`)
      return res.data
    } catch (e) {
      toast.error(`保存到需求失败：${e.message}`)
      return null
    }
  }

  const stripImages = (html) => html
    ? html.replace(/<img[^>]*>/gi, '[图片已移除]').replace(/src="data:image\/[a-zA-Z]+;base64,[^"]*"/g, '')
    : html

  const callApi = async (url, body) => {
    const res = await api.post(url, body)
    return res.data.result || '处理失败'
  }

  // 使用函数式更新，修复原代码连续 addMessage 时丢失前一条消息的 bug
  const addMessage = (role, content, meta = {}) => {
    setState((prev) => ({
      ...prev,
      [tab]: {
        ...prev[tab],
        messages: [...prev[tab].messages, { role, content, timestamp: new Date().toISOString(), ...meta }],
      },
    }))
  }

  const handleGenerate = async () => {
    if (s.loading) return
    update({ loading: true })
    try {
      if (tab === 'prd') {
        if (!s.userInput.trim()) { toast.error('请输入需求描述'); update({ loading: false }); return }
        const result = await callApi('/api/prd/generate', { prd_text: stripImages(s.userInput) })
        addMessage('user', s.userInput)
        addMessage('assistant', result)
        update({ userInput: '' })
        await saveToRequirement('prd', result)
      } else if (tab === 'review') {
        if (!s.prdText.trim()) { toast.error('请输入 PRD 内容'); update({ loading: false }); return }
        const result = await callApi('/api/prd/review', { prd_text: stripImages(s.prdText), repo_path: s.repoPath })
        addMessage('user', s.prdText)
        addMessage('assistant', result)
        await saveToRequirement('review', result)
      } else if (tab === 'td') {
        if (!s.prdText.trim()) { toast.error('请输入 PRD 内容'); update({ loading: false }); return }
        const result = await callApi('/api/prd/technical-design', { prd_text: stripImages(s.prdText), repo_path: s.repoPath })
        addMessage('user', s.prdText)
        addMessage('assistant', result)
        await saveToRequirement('td', result)
      } else if (tab === 'test') {
        if (!s.prdText.trim()) { toast.error('请输入 PRD 内容'); update({ loading: false }); return }
        const result = await callApi('/api/prd/test-cases', { prd_text: stripImages(s.prdText), tech_design: stripImages(s.techDesign) })
        addMessage('user', s.prdText + (s.techDesign ? '\n\n技术方案: ' + s.techDesign : ''))
        addMessage('assistant', result)
        await saveToRequirement('test', result)
      } else if (tab === 'code') {
        if (!s.techDesign.trim()) { toast.error('请输入技术方案'); update({ loading: false }); return }
        const result = await callApi('/api/prd/generate-code', { task_type: 'code', tech_design: stripImages(s.techDesign), language: s.language })
        addMessage('user', `语言: ${s.language}\n技术方案: ${s.techDesign}`)
        addMessage('assistant', result)
        await saveToRequirement('code', result)
      } else if (tab === 'review_code') {
        if (!s.codeText.trim()) { toast.error('请输入要审查的代码'); update({ loading: false }); return }
        const result = await callApi('/api/code/review', { language: s.language, code: stripImages(s.codeText) })
        addMessage('user', `语言: ${s.language}\n代码:\n${s.codeText}`)
        addMessage('assistant', result)
        update({ codeText: '' })
        // 审查结果留存到需求，可回到代码生成或下次直接查看
        await saveToRequirement('code_review', result)
      }
    } catch (e) {
      toast.error(`生成失败：${e.message}`)
    } finally {
      update({ loading: false })
    }
  }

  const handleChatSend = async () => {
    const text = (s.chatInput || '').trim()
    if (!text || s.loading) return
    update({ chatInput: '', loading: true })
    addMessage('user', text)
    try {
      const historyText = s.messages.map((m) => `${m.role === 'user' ? '用户' : 'AI'}: ${stripImages(m.content)}`).join('\n\n') + '\n\n用户最新指令: ' + text
      let url, body
      if (tab === 'prd') { url = '/api/prd/generate'; body = { prd_text: historyText } }
      else if (tab === 'review') { url = '/api/prd/review'; body = { prd_text: historyText, repo_path: s.repoPath } }
      else if (tab === 'td') { url = '/api/prd/technical-design'; body = { prd_text: historyText, repo_path: s.repoPath } }
      else if (tab === 'test') { url = '/api/prd/test-cases'; body = { prd_text: historyText, tech_design: s.techDesign } }
      else if (tab === 'review_code') { url = '/api/code/review'; body = { language: s.language, code: historyText } }
      else { url = '/api/prd/code-chat'; body = { message: historyText, language: s.language } }
      const result = await callApi(url, body)
      addMessage('assistant', result)
    } catch (e) {
      addMessage('assistant', '❌ 处理失败：' + e.message)
      toast.error(`处理失败：${e.message}`)
    } finally {
      update({ loading: false })
    }
  }

  const goNext = () => {
    const next = TABS[tab]?.next
    if (!next) return
    setTab(next)
    const req = requirements.find((r) => r.id === selectedReqId)
    prefillFromRequirement(next, req)
  }

  // 从对话中提取待审查的代码（输入框优先，否则取最近一次用户提交的代码）
  const extractReviewCode = () => {
    if (s.codeText.trim()) return s.codeText.trim()
    const userMsgs = s.messages.filter((m) => m.role === 'user')
    const marker = '代码:\n'
    for (let i = userMsgs.length - 1; i >= 0; i--) {
      const idx = userMsgs[i].content.indexOf(marker)
      if (idx >= 0) return userMsgs[i].content.slice(idx + marker.length).trim()
    }
    return userMsgs[0]?.content || ''
  }

  // 根据审查意见修改代码：审查结果 → LLM 返回修改后的完整代码
  const handleImprove = async (reviewMsg) => {
    if (s.loading) return
    const code = extractReviewCode()
    if (!code) { toast.error('未找到待修改的代码，请先在左侧粘贴代码'); return }
    update({ loading: true })
    try {
      addMessage('user', '请根据上面的审查意见修改代码')
      const result = await callApi('/api/code/improve', { language: s.language, code, review: stripImages(reviewMsg.content) })
      addMessage('assistant', result, { kind: 'improved' })
    } catch (e) {
      toast.error(`代码修改失败：${e.message}`)
    } finally {
      update({ loading: false })
    }
  }

  // 把审查后的改进代码带回「代码生成」，可继续追问优化或重新部署
  const handleBringToCode = async (improvedMsg) => {
    const code = (improvedMsg.content || '').replace(/^```[a-zA-Z]*\s*\n?/, '').replace(/\n?```\s*$/, '').trim()
    if (!code) { toast.error('未解析到修改后的代码'); return }
    setState((prev) => ({
      ...prev,
      code: {
        ...prev.code,
        messages: [
          ...prev.code.messages,
          {
            role: 'user',
            content: `（代码审查后修改的代码，可直接继续追问优化）\n\`\`\`${s.language}\n${code}\n\`\`\``,
            timestamp: new Date().toISOString(),
            meta: { from: 'review' },
          },
        ],
      },
    }))
    await saveToRequirement('code', code)
    setTab('code')
    toast.success('已带回代码生成，可继续追问优化或重新部署')
  }

  const startEdit = (idx) => update({ editingMsgIdx: idx, editContent: s.messages[idx].content })
  const saveEdit = (idx) => {
    const u = [...s.messages]
    u[idx] = { ...u[idx], content: s.editContent }
    update({ messages: u, editingMsgIdx: null })
  }
  const cancelEdit = () => update({ editingMsgIdx: null })

  const handleCopy = async (text) => {
    const ok = await copyToClipboard(text)
    toast.success(ok ? '已复制到剪贴板' : '复制失败')
  }

  const downloadCode = (text) => {
    const ext = s.language === 'python' ? 'py' : s.language === 'java' ? 'java' : s.language === 'typescript' ? 'ts' : 'go'
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `code_${Date.now()}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  }

  // 一键部署到沙箱：代码落盘 → podman 构建镜像 → 启动容器 → 健康检查
  const handleDeploy = async (codeText) => {
    if (s.language !== 'python') {
      toast.error('当前沙箱部署仅支持 Python 服务（后续支持更多语言）')
      return
    }
    const clean = (codeText || '').replace(/^```[a-zA-Z]*\s*\n?/, '').replace(/\n?```\s*$/, '').trim()
    if (!clean) {
      toast.error('无可部署代码，请先完成代码生成')
      return
    }
    const base = (selectedReq?.name || 'ai-service').replace(/[^\w-]+/g, '-').slice(0, 20) || 'ai-service'
    const name = `${base}-${Math.random().toString(36).slice(2, 6)}`
    try {
      const res = await api.post('/api/deployments', {
        name,
        language: 'python',
        code: clean,
        requirement_id: selectedReqId || '',
      })
      setDeployInfo({ open: true, pipelineId: res.data.pipeline_id, runId: res.data.run_id, port: res.data.port, name: res.data.name })
      toast.success('部署已启动，正在构建镜像…')
    } catch (e) {
      toast.error(`部署启动失败：${e.message}`)
    }
  }

  const canGenerate = tab === 'prd' ? s.userInput.trim() : tab === 'code' ? s.techDesign.trim() : tab === 'review_code' ? s.codeText.trim() : s.prdText.trim()
  const generateBtnText = getGenerateBtnText()
  const chatPlaceholder = getChatPlaceholder()

  return (
    <div className="space-y-5">
      <PageHeader
        title="AI 工作台"
        description="统一 AI 研发流水线：PRD 编写 → 审查 → 技术方案 → 测试用例 → 代码生成"
        icon={Sparkles}
      />

      {/* 一句话全自动入口：小白用户只需说出功能，AI 全流程自动实现 */}
      <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-fuchsia-600 rounded-2xl p-5 text-white shadow-lg flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1">
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Rocket className="w-5 h-5" /> 一句话全自动
          </h3>
          <p className="text-sm text-white/80 mt-1">
            说出你想要的功能，AI 自动完成 PRD → 审查 → 技术方案 → 测试用例 → 代码 → 审查 → 部署 全流程，全程可视化跟踪
          </p>
        </div>
        <button
          onClick={() => setAutoRunOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-white text-indigo-700 rounded-xl font-semibold text-sm hover:bg-indigo-50 transition-all shadow-md hover:shadow-lg flex-shrink-0"
        >
          <Sparkles className="w-4 h-4" /> 开始全自动实现
        </button>
      </div>

      {/* 流水线状态条：6 阶段可视化，点击任意阶段跳转（关联需求时显示） */}
      {selectedReq && (
        <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium flex-shrink-0">
            <GitBranch className="w-3.5 h-3.5" /> 流水线进度
          </div>
          <div className="flex-1 flex items-center gap-1 overflow-x-auto">
            {PIPELINE_STAGES.map((stage, idx) => {
              const st = stageStatus(stage.key)
              const active = tab === stage.key
              return (
                <React.Fragment key={stage.key}>
                  {idx > 0 && (
                    <div className={`flex-1 h-0.5 rounded min-w-[8px] ${st === 'idle' ? 'bg-gray-200' : 'bg-emerald-400'}`} />
                  )}
                  <button
                    onClick={() => handleTabChange(stage.key)}
                    title={st === 'stale' ? '上游已变更，此阶段产物建议重新生成' : st === 'done' ? '已有产物，可查看或重新生成' : '尚未生成'}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                      active ? 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200' : 'hover:bg-gray-50 text-gray-600'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${
                      st === 'stale' ? 'bg-amber-500' : st === 'done' ? 'bg-emerald-500' : 'bg-gray-300'
                    }`} />
                    {stage.label}
                    {st === 'stale' && <span className="text-[10px] text-amber-600 font-semibold">需更新</span>}
                  </button>
                </React.Fragment>
              )
            })}
          </div>
          <button
            onClick={openArtifacts}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg text-xs font-medium transition-colors border border-indigo-100 flex-shrink-0"
            title="查看该需求已保存的全部产物与测试记录"
          >
            <FolderGit2 className="w-3.5 h-3.5" /> 查看全部产物
            {ARTIFACT_FIELDS.filter((s) => selectedReq[s.field]).length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-semibold">
                {ARTIFACT_FIELDS.filter((s) => selectedReq[s.field]).length}
              </span>
            )}
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto">
        {PIPELINE.map((key) => {
          const t = TABS[key]
          const TColor = COLOR_MAP[t.color]
          return (
            <button
              key={key}
              onClick={() => handleTabChange(key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === key ? TColor.active : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <t.icon className="w-4 h-4" /> {t.label}
              {stageStatus(key) === 'stale' && (
                <span className="ml-0.5 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-semibold">需更新</span>
              )}
            </button>
          )
        })}
      </div>

      {/* 需求加载失败提示 */}
      {reqError && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-center justify-between gap-3">
          <span className="text-sm text-red-700">需求列表加载失败：{reqError.message}</span>
          <button onClick={fetchRequirements} className="text-sm text-red-600 hover:underline flex items-center gap-1 flex-shrink-0">
            <RefreshCw className="w-3.5 h-3.5" /> 重试
          </button>
        </div>
      )}

      <DeployModal info={deployInfo} onClose={() => setDeployInfo(null)} />
      <AutoRunModal open={autoRunOpen} onClose={() => setAutoRunOpen(false)} />
      <ArtifactsModal
        open={artifactsOpen}
        onClose={() => setArtifactsOpen(false)}
        requirement={selectedReq}
        testRuns={testRuns}
        testLoading={testLoading}
        onRefreshTests={fetchTestRuns}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
        {/* 左：输入面板 */}
        <div className="lg:col-span-1 bg-white rounded-2xl border border-gray-200 overflow-hidden flex flex-col h-[60vh] lg:h-[calc(100vh-13rem)] min-h-[400px]">
          <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <tabInfo.icon className={`w-4 h-4 ${c.icon}`} /> {tabInfo.label}
              </h2>
              <span className="text-xs text-gray-400 hidden sm:inline">左侧输入，点击生成</span>
            </div>
            {/* 需求选择器 */}
            <div className="flex items-center gap-2">
              <ListTodo className="w-4 h-4 text-gray-400 flex-shrink-0" />
              {reqLoading ? (
                <span className="text-xs text-gray-400">加载需求…</span>
              ) : reqError ? (
                <span className="text-xs text-red-500">需求加载失败</span>
              ) : (
                <select
                  value={selectedReqId || ''}
                  onChange={(e) => handleSelectRequirement(e.target.value)}
                  className="flex-1 p-1.5 text-xs border border-gray-200 rounded-md bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/10 outline-none"
                >
                  <option value="">-- 选择关联需求（可选） --</option>
                  {requirements.map((r) => (
                    <option key={r.id} value={r.id}>[{r.status}] {r.name}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {selectedReq && (
              <div className="p-2 bg-indigo-50 rounded-lg border border-indigo-100 text-xs text-indigo-700">
                已关联: <strong>{selectedReq.name}</strong>（状态: {selectedReq.status}）
              </div>
            )}
            {renderLeftPanel()}
            <div className="flex gap-2">
              <button
                onClick={handleGenerate}
                disabled={s.loading || !canGenerate}
                className={`flex-1 bg-gradient-to-r ${c.from} ${c.to} text-white py-2.5 px-4 rounded-xl hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all flex items-center justify-center gap-2 text-sm`}
              >
                {s.loading
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> 生成中…</>
                  : <><Sparkles className="w-4 h-4" /> {generateBtnText}</>}
              </button>
              {tabInfo.next && s.messages.length > 0 && (
                <button
                  onClick={goNext}
                  className="px-4 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 font-medium transition-all flex items-center gap-1.5 text-sm whitespace-nowrap"
                >
                  {tabInfo.nextLabel} <ArrowRight className="w-4 h-4" />
                </button>
              )}
            </div>
            <div className={`p-3 ${c.light} rounded-xl border ${c.border}`}>
              <p className={`text-xs font-medium ${c.text} mb-1`}>💡 使用提示</p>
              <ul className={`text-xs ${c.text} space-y-0.5`}>
                <li>• 在左侧输入内容，点击「{generateBtnText}」</li>
                <li>• 结果出现在右侧对话区，可继续追问</li>
                {selectedReqId && <li>• 生成结果将自动保存到关联需求</li>}
              </ul>
            </div>
          </div>
        </div>

        {/* 右：对话面板 */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 overflow-hidden flex flex-col h-[60vh] lg:h-[calc(100vh-13rem)] min-h-[400px]">
          <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-purple-600" />
              <h2 className="text-base font-semibold text-gray-900">AI 对话</h2>
              {s.messages.length > 0 && <span className="text-xs text-gray-400 ml-1">{s.messages.length} 条</span>}
            </div>
            {s.messages.length > 0 && (
              <button onClick={() => update({ messages: [] })} className="text-xs text-gray-400 hover:text-red-500">清空</button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {s.messages.length === 0 ? (
              <Empty
                icon={MessageSquare}
                title="暂无对话记录"
                description={`在左侧输入内容后点击「${generateBtnText}」开始对话`}
                className="h-full justify-center"
              />
            ) : (
              s.messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex items-start gap-2 max-w-[88%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-purple-600' : 'bg-blue-600'}`}>
                      {msg.role === 'user' ? <User className="w-3.5 h-3.5 text-white" /> : <Bot className="w-3.5 h-3.5 text-white" />}
                    </div>
                    <div className={`rounded-2xl px-3 py-2.5 ${msg.role === 'user' ? 'bg-purple-600 text-white' : msg.error ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-gray-100 text-gray-900'}`}>
                      <div className={`flex items-center gap-1 mb-1.5 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-400'}`}>
                        <button onClick={() => startEdit(idx)} title="编辑" className="p-0.5 hover:bg-black/10 rounded"><Edit2 className="w-3 h-3" /></button>
                        <button onClick={() => handleCopy(msg.content)} title="复制" className="p-0.5 hover:bg-black/10 rounded"><Copy className="w-3 h-3" /></button>
                        {tab === 'code' && msg.role === 'assistant' && (
                          <button onClick={() => downloadCode(msg.content)} title="下载代码" className="p-0.5 hover:bg-black/10 rounded"><Download className="w-3 h-3" /></button>
                        )}
                        {tab === 'code' && msg.role === 'assistant' && s.language === 'python' && (
                          <button onClick={() => handleDeploy(msg.content)} title="部署到沙箱" className="p-0.5 hover:bg-black/10 rounded text-purple-500"><Rocket className="w-3 h-3" /></button>
                        )}
                        {tab === 'review_code' && msg.role === 'assistant' && msg.kind !== 'improved' && (
                          <button onClick={() => handleImprove(msg)} title="按此审查意见修改代码" className="p-0.5 hover:bg-black/10 rounded text-amber-600"><Wrench className="w-3 h-3" /></button>
                        )}
                        {tab === 'review_code' && msg.role === 'assistant' && msg.kind === 'improved' && (
                          <>
                            <button onClick={() => downloadCode(msg.content)} title="下载代码" className="p-0.5 hover:bg-black/10 rounded"><Download className="w-3 h-3" /></button>
                            {s.language === 'python' && (
                              <button onClick={() => handleDeploy(msg.content)} title="部署到沙箱" className="p-0.5 hover:bg-black/10 rounded text-purple-500"><Rocket className="w-3 h-3" /></button>
                            )}
                            <button onClick={() => handleBringToCode(msg)} title="带回代码生成" className="p-0.5 hover:bg-black/10 rounded text-purple-500"><Undo2 className="w-3 h-3" /></button>
                          </>
                        )}
                      </div>
                      {s.editingMsgIdx === idx ? (
                        <div className="space-y-1.5">
                          <textarea
                            value={s.editContent}
                            onChange={(e) => update({ editContent: e.target.value })}
                            className={`w-full p-2 rounded-lg text-sm resize-none font-mono ${msg.role === 'user' ? 'bg-white/20 text-white placeholder-white/60' : 'bg-white text-gray-900'}`}
                            rows={6}
                          />
                          <div className="flex gap-1.5">
                            <button onClick={() => saveEdit(idx)} className="px-2 py-0.5 bg-green-500 text-white text-xs rounded hover:bg-green-600 flex items-center gap-0.5"><Save className="w-2.5 h-2.5 inline" />保存</button>
                            <button onClick={cancelEdit} className="px-2 py-0.5 bg-gray-500 text-white text-xs rounded hover:bg-gray-600 flex items-center gap-0.5"><X className="w-2.5 h-2.5 inline" />取消</button>
                          </div>
                        </div>
                      ) : (
                        <div className={`text-sm leading-relaxed ${msg.role === 'user' ? 'whitespace-pre-wrap' : ''}`}>
                          {msg.role === 'assistant'
                            ? <MarkdownRenderer content={msg.content} />
                            : msg.content}
                        </div>
                      )}
                      <div className={`text-xs mt-1.5 ${msg.role === 'user' ? 'text-purple-200' : 'text-gray-400'}`}>
                        {formatRelativeTime(msg.timestamp)}
                      </div>
                      {tab === 'code' && msg.role === 'assistant' && s.language === 'python' && (
                        <div className="mt-2.5">
                          <button
                            onClick={() => handleDeploy(msg.content)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-medium rounded-lg hover:opacity-90 transition-all shadow-sm"
                          >
                            <Rocket className="w-3.5 h-3.5" /> 一键部署到沙箱
                          </button>
                        </div>
                      )}
                      {tab === 'review_code' && msg.role === 'assistant' && msg.kind === 'improved' && (
                        <div className="mt-2.5 flex flex-wrap gap-2">
                          {s.language === 'python' && (
                            <button
                              onClick={() => handleDeploy(msg.content)}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-medium rounded-lg hover:opacity-90 transition-all shadow-sm"
                            >
                              <Rocket className="w-3.5 h-3.5" /> 部署改进后的代码
                            </button>
                          )}
                          <button
                            onClick={() => handleBringToCode(msg)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-amber-500 to-orange-600 text-white text-xs font-medium rounded-lg hover:opacity-90 transition-all shadow-sm"
                          >
                            <Undo2 className="w-3.5 h-3.5" /> 带回代码生成
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            {s.loading && (
              <div className="flex items-center gap-2 text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">AI 正在思考…</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-gray-200 bg-gray-50 p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={s.chatInput}
                onChange={(e) => update({ chatInput: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend() } }}
                placeholder={chatPlaceholder}
                className="flex-1 p-2.5 border border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 resize-none text-sm bg-white outline-none"
                rows={2}
              />
              <Button variant="gradient" icon={Send} loading={s.loading} disabled={!s.chatInput.trim()} onClick={handleChatSend} className="self-end">
                <span className="hidden sm:inline">发送</span>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )

  function renderLeftPanel() {
    if (tab === 'prd') {
      return (
        <>
          <RichTextEditor
            value={s.userInput}
            onChange={(v) => update({ userInput: v })}
            placeholder={'请输入需求描述…\n\n例如：\n1. 新增素材分享功能\n2. 支持将创意素材分享给其他广告账户\n3. 分享时需要校验素材状态'}
            minHeight={180}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1"><FolderGit2 className="w-4 h-4 inline mr-1" />仓库路径（可选）</label>
            <input type="text" className={`w-full p-2.5 border border-gray-300 rounded-lg ${c.ring} text-sm font-mono outline-none`} value={s.repoPath} onChange={(e) => update({ repoPath: e.target.value })} placeholder="/path/to/repo" />
          </div>
        </>
      )
    }
    if (tab === 'review') {
      return (
        <>
          <RichTextEditor value={s.prdText} onChange={(v) => update({ prdText: v })} placeholder="请输入 PRD 内容…" minHeight={200} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">仓库路径（可选）</label>
            <input type="text" className={`w-full p-2.5 border border-gray-300 rounded-lg ${c.ring} text-sm font-mono outline-none`} value={s.repoPath} onChange={(e) => update({ repoPath: e.target.value })} placeholder="/path/to/repo" />
          </div>
        </>
      )
    }
    if (tab === 'td') {
      return (
        <>
          <RichTextEditor value={s.prdText} onChange={(v) => update({ prdText: v })} placeholder="请输入 PRD 内容…" minHeight={180} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">仓库路径（可选）</label>
            <input type="text" className={`w-full p-2.5 border border-gray-300 rounded-lg ${c.ring} text-sm font-mono outline-none`} value={s.repoPath} onChange={(e) => update({ repoPath: e.target.value })} placeholder="/path/to/repo" />
          </div>
        </>
      )
    }
    if (tab === 'test') {
      return (
        <>
          <RichTextEditor value={s.prdText} onChange={(v) => update({ prdText: v })} placeholder="请输入 PRD 内容…" minHeight={150} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">技术方案（可选）</label>
            <RichTextEditor value={s.techDesign} onChange={(v) => update({ techDesign: v })} placeholder="粘贴技术方案内容，增强测试覆盖度…" minHeight={100} />
          </div>
        </>
      )
    }
    if (tab === 'code') {
      return (
        <>
          <RichTextEditor value={s.techDesign} onChange={(v) => update({ techDesign: v })} placeholder="粘贴或输入技术方案内容…" minHeight={180} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">编程语言</label>
            <select className={`w-full p-2.5 border border-gray-200 rounded-lg ${c.ring} outline-none`} value={s.language} onChange={(e) => update({ language: e.target.value })}>
              <option value="go">Go</option>
              <option value="python">Python</option>
              <option value="java">Java</option>
              <option value="typescript">TypeScript</option>
            </select>
            <p className="text-xs text-gray-400 mt-1.5">生成代码后，Python 服务可点击对话区「一键部署到沙箱」立即运行</p>
          </div>
        </>
      )
    }
    // review_code：代码审查
    return (
      <>
        <RichTextEditor value={s.codeText} onChange={(v) => update({ codeText: v })} placeholder="粘贴要审查的代码…" minHeight={200} />
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">编程语言</label>
          <select className={`w-full p-2.5 border border-gray-200 rounded-lg ${c.ring} outline-none`} value={s.language} onChange={(e) => update({ language: e.target.value })}>
            <option value="go">Go</option>
            <option value="python">Python</option>
            <option value="java">Java</option>
            <option value="typescript">TypeScript</option>
          </select>
        </div>
      </>
    )
  }

  function getGenerateBtnText() {
    if (tab === 'prd') return '生成 PRD'
    if (tab === 'review') return '开始审查'
    if (tab === 'td') return '生成技术方案'
    if (tab === 'test') return '生成测试用例'
    if (tab === 'review_code') return '开始审查'
    return '生成代码'
  }

  function getChatPlaceholder() {
    if (tab === 'prd') return '对 PRD 提出修改意见，例如：增加用户权限管理章节…'
    if (tab === 'review') return '对审查结果提出意见或追问…'
    if (tab === 'td') return '对技术方案提出修改意见…'
    if (tab === 'test') return '对测试用例提出修改意见，例如：补充边界条件…'
    if (tab === 'review_code') return '对审查结果提出意见或追问…'
    return '对生成的代码提出修改意见，例如：增加错误处理…'
  }
}
