import React, { useState, useEffect } from 'react'
import {
  Clock,
  Plus,
  Trash2,
  Play,
  Pause,
  Calendar,
  RefreshCw,
  Zap,
  History,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react'
import {
  Card,
  Button,
  Empty,
  PageHeader,
  Badge,
  ConfirmDialog,
  ErrorState,
  SkeletonList,
  Modal,
} from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const JOB_TYPES = [
  { value: 'report', label: '定时报告', icon: Calendar },
  { value: 'notify', label: '提醒通知', icon: Clock },
  { value: 'backup', label: '数据备份', icon: RefreshCw },
]

const CRON_PRESETS = [
  { label: '每天 9:00', value: '0 9 * * *' },
  { label: '每天 18:00', value: '0 18 * * *' },
  { label: '每周一 9:00', value: '0 9 * * 1' },
  { label: '每月1日 9:00', value: '0 9 1 * *' },
  { label: '每小时', value: '0 * * * *' },
]

// 最近执行状态徽标
const STATUS_META = {
  success: { label: '执行成功', color: 'green', icon: CheckCircle2 },
  failed: { label: '执行失败', color: 'red', icon: XCircle },
  running: { label: '执行中', color: 'amber', icon: Loader2 },
  '': { label: '未运行', color: 'gray', icon: History },
}

export default function SchedulerPage() {
  const toast = useToast()
  const [jobs, setJobs] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [deleteId, setDeleteId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  // 执行历史抽屉
  const [historyJob, setHistoryJob] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [runs, setRuns] = useState([])

  const [form, setForm] = useState({
    name: '',
    description: '',
    job_type: 'report',
    cron_expression: '0 9 * * *',
    config: '{}',
  })

  useEffect(() => {
    loadJobs()
  }, [])

  const loadJobs = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const res = await api.get('/api/scheduler')
      setJobs(res.data || [])
    } catch (e) {
      setLoadError(e?.message || '定时任务加载失败')
      toast.error(`加载失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const createJob = async () => {
    if (!form.name.trim()) {
      toast.error('请输入任务名称')
      return
    }
    setLoading(true)
    try {
      await api.post('/api/scheduler', {
        name: form.name.trim(),
        description: form.description.trim(),
        job_type: form.job_type,
        cron_expression: form.cron_expression,
      })
      toast.success('任务创建成功')
      setShowCreate(false)
      resetForm()
      loadJobs()
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    }
    setLoading(false)
  }

  const toggleJob = async (job) => {
    try {
      await api.put(`/api/scheduler/${job.id}`, { enabled: job.enabled ? 0 : 1 })
      loadJobs()
      toast.success(job.enabled ? '已暂停' : '已启用')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const triggerJob = async (job) => {
    try {
      const res = await api.post(`/api/scheduler/${job.id}/trigger`)
      const ok = res.data?.status === 'success'
      const detail = ok ? res.data?.output : res.data?.error
      const msg = `${res.data?.message || ''}${detail ? `：${detail}` : ''}`
      if (ok) {
        toast.success(msg, 6000)
      } else {
        toast.error(msg, 8000)
      }
      loadJobs()
    } catch (e) {
      toast.error(`触发失败：${e.message}`)
    }
  }

  const openHistory = async (job) => {
    setHistoryJob(job)
    setHistoryLoading(true)
    setHistoryError('')
    setRuns([])
    try {
      const res = await api.get(`/api/scheduler/${job.id}/runs`)
      setRuns(res.data || [])
    } catch (e) {
      setHistoryError(`历史加载失败：${e.message}`)
    } finally {
      setHistoryLoading(false)
    }
  }

  const deleteJob = async () => {
    if (!deleteId) return
    try {
      await api.delete(`/api/scheduler/${deleteId}`)
      setJobs((prev) => prev.filter((j) => j.id !== deleteId))
      toast.success('已删除')
    } catch (e) {
      toast.error(e.message)
    }
    setDeleteId(null)
  }

  const resetForm = () => {
    setForm({
      name: '',
      description: '',
      job_type: 'report',
      cron_expression: '0 9 * * *',
      config: '{}',
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="定时任务"
        description="创建定时报告、提醒通知、数据备份，自动化重复工作"
        icon={Clock}
        iconColor="from-teal-500 to-cyan-600"
        actions={
          <Button
            variant="primary"
            icon={Plus}
            onClick={() => {
              resetForm()
              setShowCreate(true)
            }}
          >
            创建任务
          </Button>
        }
      />

      {/* 创建表单 */}
      {showCreate && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Plus className="w-4 h-4 text-teal-500" /> 新建定时任务
          </h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">任务名称 *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="例如：每日销售报告"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">任务类型</label>
                <select
                  value={form.job_type}
                  onChange={(e) => setForm({ ...form, job_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 outline-none"
                >
                  {JOB_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="描述任务用途..."
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Cron 表达式</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {CRON_PRESETS.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => setForm({ ...form, cron_expression: p.value })}
                    className={`px-2 py-1 text-xs rounded-lg border transition-colors ${
                      form.cron_expression === p.value
                        ? 'border-teal-500 bg-teal-50 text-teal-700'
                        : 'border-gray-200 hover:border-teal-300 text-gray-600'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <input
                value={form.cron_expression}
                onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
                placeholder="分 时 日 月 周"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-teal-500 outline-none"
              />
              <p className="text-xs text-gray-400 mt-1">
                格式：分 时 日 月 周，例如 0 9 * * * 表示每天9:00（周：0/7=周日，1-6=周一至周六）
              </p>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                取消
              </Button>
              <Button variant="primary" loading={loading} onClick={createJob}>
                创建
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 任务列表 */}
      {loading ? (
        <SkeletonList count={3} />
      ) : loadError ? (
        <ErrorState message={loadError} onRetry={loadJobs} />
      ) : jobs.length === 0 ? (
        <Empty
          icon={Clock}
          title="暂无定时任务"
          description="创建第一个定时任务，让AI自动完成重复工作"
        />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const typeInfo = JOB_TYPES.find((t) => t.value === job.job_type) || JOB_TYPES[0]
            const status = STATUS_META[job.last_status] || STATUS_META['']
            const StatusIcon = status.icon
            return (
              <Card key={job.id} className="flex items-center gap-4">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    job.enabled ? 'bg-teal-50 text-teal-600' : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  <typeInfo.icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-gray-900 truncate">{job.name}</h3>
                    <Badge color={job.enabled ? 'green' : 'gray'}>
                      {job.enabled ? '运行中' : '已暂停'}
                    </Badge>
                    <Badge color="blue">{typeInfo.label}</Badge>
                    {/* v15：最近执行状态徽标 */}
                    <Badge color={status.color}>
                      <span className="flex items-center gap-1">
                        <StatusIcon className="w-3 h-3" />
                        {status.label}
                      </span>
                    </Badge>
                  </div>
                  {job.description && (
                    <p className="text-xs text-gray-500 mt-0.5">{job.description}</p>
                  )}
                  <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
                    <span className="font-mono">{job.cron_expression}</span>
                    {job.last_run && (
                      <span>上次运行：{new Date(job.last_run).toLocaleString()}</span>
                    )}
                    {job.next_run && (
                      <span className="text-teal-600">
                        下次运行：{new Date(job.next_run).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={History}
                    title="执行历史"
                    onClick={() => openHistory(job)}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Zap}
                    title="手动触发"
                    onClick={() => triggerJob(job)}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={job.enabled ? Pause : Play}
                    title={job.enabled ? '暂停' : '启用'}
                    onClick={() => toggleJob(job)}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Trash2}
                    className="text-gray-400 hover:text-red-500"
                    onClick={() => setDeleteId(job.id)}
                  />
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* 执行历史抽屉 */}
      <Modal
        open={!!historyJob}
        onClose={() => setHistoryJob(null)}
        title={historyJob ? `执行历史 · ${historyJob.name}` : ''}
        size="lg"
      >
        {historyLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-teal-500" />
          </div>
        ) : historyError ? (
          <ErrorState message={historyError} onRetry={() => openHistory(historyJob)} />
        ) : runs.length === 0 ? (
          <Empty
            icon={History}
            title="暂无执行记录"
            description="手动触发或等待调度执行后，这里会展示每次运行的完整日志"
          />
        ) : (
          <div className="space-y-0">
            {runs.map((run, idx) => {
              const ok = run.status === 'success'
              const isLast = idx === runs.length - 1
              return (
                <div key={run.id} className="flex gap-3 relative pb-5">
                  {/* 时间线竖线 */}
                  {!isLast && (
                    <div className="absolute left-[9px] top-6 bottom-0 w-px bg-gray-200" />
                  )}
                  <div className="flex-shrink-0 mt-1">
                    <span
                      className={`w-[19px] h-[19px] rounded-full flex items-center justify-center ${
                        ok ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-500'
                      }`}
                    >
                      {ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge color={ok ? 'green' : 'red'}>{ok ? '成功' : '失败'}</Badge>
                      <span className="text-xs text-gray-400">
                        {run.started_at?.replace('T', ' ').slice(0, 19)} ~{' '}
                        {run.finished_at?.replace('T', ' ').slice(0, 19)}
                      </span>
                    </div>
                    {(run.output || run.error) && (
                      <div
                        className={`mt-2 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap break-all ${
                          ok
                            ? 'bg-gray-50 text-gray-600 border border-gray-100'
                            : 'bg-red-50 text-red-600 border border-red-100'
                        }`}
                      >
                        {ok ? run.output : run.error}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={deleteJob}
        title="删除定时任务？"
        message="删除后任务将不再执行，此操作不可撤销。"
        confirmLabel="确认删除"
        icon={Trash2}
      />
    </div>
  )
}
