import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  CheckCircle2, Circle, Clock, AlertCircle, XCircle, RotateCcw, Ban,
  Filter, RefreshCw, Zap, FileText, Music, Image, Video, Mic, Gamepad2,
  Smartphone, PauseCircle
} from 'lucide-react'
import { Card, Button, Badge, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

// 任务类型展示映射
const TYPE_META = {
  dh_generate: { label: '数字人', icon: Video, color: 'indigo' },
  game_generate: { label: '小游戏生成', icon: Gamepad2, color: 'fuchsia' },
  game_evolve: { label: '小游戏迭代', icon: Gamepad2, color: 'fuchsia' },
  miniapp_generate: { label: '小程序生成', icon: Smartphone, color: 'purple' },
  video_generate: { label: '视频生成', icon: Video, color: 'red' },
  music_lyrics: { label: '歌词生成', icon: Music, color: 'rose' },
  music_sing: { label: '人声合成', icon: Music, color: 'rose' },
  meme_generate: { label: '表情包', icon: Image, color: 'amber' },
  image_t2i: { label: '文生图', icon: Image, color: 'blue' },
  image_i2i: { label: '图生图', icon: Image, color: 'blue' },
  image_template: { label: '模板渲染', icon: Image, color: 'blue' },
  image_tryon: { label: '虚拟试衣', icon: Image, color: 'cyan' },
  voice_generate: { label: 'AI 配音', icon: Mic, color: 'emerald' },
}

const STATUS_META = {
  pending: { label: '排队中', color: 'gray', icon: Clock },
  running: { label: '执行中', color: 'blue', icon: Circle },
  success: { label: '已完成', color: 'green', icon: CheckCircle2 },
  failed: { label: '失败', color: 'red', icon: AlertCircle },
  interrupted: { label: '已中断', color: 'orange', icon: XCircle },
  canceled: { label: '已取消', color: 'gray', icon: Ban },
}

const STATUS_OPTIONS = Object.entries(STATUS_META).map(([value, m]) => ({ value, label: m.label }))

export default function TasksPage() {
  const toast = useToast()
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ type: '', status: '' })
  const [actionId, setActionId] = useState('')
  const timerRef = useRef(null)

  const loadTasks = useCallback(async () => {
    try {
      const params = {}
      if (filter.type) params.type = filter.type
      if (filter.status) params.status = filter.status
      const res = await api.get('/api/tasks', { params })
      setTasks(res.data.tasks || [])
    } catch {
      // 轮询静默失败，避免弹窗轰炸
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { loadTasks() }, [loadTasks])

  // 任务中心自动轮询（3s），进度实时刷新
  useEffect(() => {
    timerRef.current = setInterval(loadTasks, 3000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [loadTasks])

  const refresh = async () => {
    setLoading(true)
    try {
      await loadTasks()
      toast.success('已刷新')
    } catch (e) {
      toast.error(`加载失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const retryTask = async (task) => {
    setActionId(task.id)
    try {
      await api.post(`/api/tasks/${task.id}/retry`)
      toast.success('任务已重新提交')
      loadTasks()
    } catch (e) {
      toast.error(`重试失败：${e.message}`)
    } finally {
      setActionId('')
    }
  }

  const cancelTask = async (task) => {
    if (!confirm('确定取消该任务？（仅排队中的任务可取消）')) return
    setActionId(task.id)
    try {
      await api.post(`/api/tasks/${task.id}/cancel`)
      toast.success('任务已取消')
      loadTasks()
    } catch (e) {
      toast.error(`取消失败：${e.message}`)
    } finally {
      setActionId('')
    }
  }

  const typeMeta = (type) => TYPE_META[type] || { label: type || '未知任务', icon: FileText, color: 'gray' }
  const statusMeta = (status) => STATUS_META[status] || { label: status || '未知', color: 'gray', icon: Circle }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">任务中心</h1>
          <p className="text-sm text-gray-500 mt-1">AI 生成任务实时进度 · 关闭页面也不中断，完成后自动保存产物</p>
        </div>
        <Button variant="ghost" icon={RefreshCw} onClick={refresh}>
          刷新
        </Button>
      </div>

      {/* 过滤器 */}
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">筛选：</span>
          </div>
          <select
            value={filter.type}
            onChange={(e) => setFilter({ ...filter, type: e.target.value })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="">全部类型</option>
            {Object.entries(TYPE_META).map(([value, m]) => (
              <option key={value} value={value}>{m.label}</option>
            ))}
          </select>
          <select
            value={filter.status}
            onChange={(e) => setFilter({ ...filter, status: e.target.value })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          {(filter.type || filter.status) && (
            <Button variant="ghost" size="sm" onClick={() => setFilter({ type: '', status: '' })}>
              清除筛选
            </Button>
          )}
          <div className="ml-auto flex items-center gap-2 text-sm text-gray-500">
            <Zap className="w-4 h-4 text-amber-500" />
            共 {tasks.length} 个任务
          </div>
        </div>
      </Card>

      {/* 任务列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" />
        </div>
      ) : tasks.length === 0 ? (
        <Card>
          <Empty
            icon={CheckCircle2}
            title="暂无任务"
            description="在小游戏/小程序/视频/图片/配音等工厂提交生成任务后，会在这里实时展示进度"
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => {
            const TypeIcon = typeMeta(task.type).icon
            const StatusIcon = statusMeta(task.status).icon
            const st = statusMeta(task.status)
            const tm = typeMeta(task.type)
            const active = task.status === 'pending' || task.status === 'running'
            const failed = ['failed', 'interrupted'].includes(task.status)
            return (
              <Card key={task.id} className="!p-4">
                <div className="flex items-start gap-3">
                  <div className={`p-2.5 rounded-xl bg-${tm.color}-50 text-${tm.color}-600 shrink-0`}>
                    <TypeIcon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-gray-900 text-sm">{tm.label}</span>
                      <Badge color={st.color}>{st.label}</Badge>
                      <span className="text-xs text-gray-400 font-mono">{task.id}</span>
                    </div>
                    {/* 进度条 */}
                    <div className="mt-2.5 flex items-center gap-3">
                      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            task.status === 'success' ? 'bg-green-500'
                              : task.status === 'failed' ? 'bg-red-400'
                                : 'bg-brand-500'
                          }`}
                          style={{ width: `${task.progress || 0}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-10 text-right">
                        {active ? `${Math.round(task.progress || 0)}%` : task.status === 'success' ? '100%' : '—'}
                      </span>
                    </div>
                    {/* 阶段文案 / 错误 */}
                    <div className="mt-1.5 text-xs">
                      {active ? (
                        <span className="text-gray-500">{task.stage || '任务排队中…'}</span>
                      ) : failed ? (
                        <span className="text-red-500 flex items-start gap-1">
                          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                          <span className="break-all">{task.error || '执行失败'}</span>
                        </span>
                      ) : task.status === 'success' ? (
                        <span className="text-green-600">{task.stage || '生成完成'}</span>
                      ) : (
                        <span className="text-gray-400">{task.stage || ''}</span>
                      )}
                    </div>
                    {/* 元信息 + 操作 */}
                    <div className="mt-2 flex items-center gap-3 flex-wrap">
                      <span className="text-xs text-gray-400">
                        {task.created_at ? task.created_at.replace('T', ' ').slice(0, 19) : ''}
                      </span>
                      {task.created_by && <span className="text-xs text-gray-400">by {task.created_by}</span>}
                      {task.retry_count > 0 && (
                        <span className="text-xs text-gray-400">重试 {task.retry_count} 次</span>
                      )}
                      <div className="ml-auto flex items-center gap-1.5">
                        {failed && (
                          <button
                            onClick={() => retryTask(task)}
                            disabled={actionId === task.id}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 disabled:opacity-50"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                            {actionId === task.id ? '重试中…' : '重试'}
                          </button>
                        )}
                        {task.status === 'pending' && (
                          <button
                            onClick={() => cancelTask(task)}
                            disabled={actionId === task.id}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:opacity-50"
                          >
                            <PauseCircle className="w-3.5 h-3.5" />
                            取消
                          </button>
                        )}
                        {task.status === 'running' && (
                          <span className="flex items-center gap-1 text-xs text-blue-500">
                            <StatusIcon className="w-3.5 h-3.5 animate-pulse" />
                            执行中
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
