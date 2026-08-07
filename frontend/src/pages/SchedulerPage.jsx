import React, { useState, useEffect } from 'react'
import { Clock, Plus, Trash2, Play, Pause, Settings, Calendar, RefreshCw, Zap } from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge, ConfirmDialog } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const JOB_TYPES = [
  { value: 'report', label: '定时报告', icon: Calendar },
  { value: 'sync', label: '数据同步', icon: RefreshCw },
  { value: 'reminder', label: '提醒通知', icon: Clock },
]

const CRON_PRESETS = [
  { label: '每天 9:00', value: '0 9 * * *' },
  { label: '每天 18:00', value: '0 18 * * *' },
  { label: '每周一 9:00', value: '0 9 * * 1' },
  { label: '每月1日 9:00', value: '0 9 1 * *' },
  { label: '每小时', value: '0 * * * *' },
]

export default function SchedulerPage() {
  const toast = useToast()
  const [jobs, setJobs] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [deleteId, setDeleteId] = useState(null)
  const [loading, setLoading] = useState(false)

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
    try {
      const res = await api.get('/api/scheduler')
      setJobs(res.data || [])
    } catch (e) {
      toast.error(`加载失败：${e.message}`)
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
      await api.post(`/api/scheduler/${job.id}/trigger`)
      toast.success(`已手动触发「${job.name}」`)
      loadJobs()
    } catch (e) {
      toast.error(e.message)
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
        description="创建定时报告、数据同步、提醒通知，自动化重复工作"
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
                格式：分 时 日 月 周，例如 0 9 * * * 表示每天9:00
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
      {jobs.length === 0 ? (
        <Empty
          icon={Clock}
          title="暂无定时任务"
          description="创建第一个定时任务，让AI自动完成重复工作"
        />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const typeInfo = JOB_TYPES.find((t) => t.value === job.job_type) || JOB_TYPES[0]
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
                  </div>
                  {job.description && (
                    <p className="text-xs text-gray-500 mt-0.5">{job.description}</p>
                  )}
                  <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
                    <span className="font-mono">{job.cron_expression}</span>
                    {job.last_run && (
                      <span>上次运行：{new Date(job.last_run).toLocaleString()}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
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
