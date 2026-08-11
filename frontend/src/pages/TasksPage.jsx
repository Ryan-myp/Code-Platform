import { useState, useEffect, useRef, useCallback } from 'react'
import {
  CheckCircle2,
  Circle,
  Clock,
  AlertCircle,
  XCircle,
  RotateCcw,
  Ban,
  Filter,
  RefreshCw,
  Zap,
  FileText,
  Music,
  Image,
  Video,
  Mic,
  Gamepad2,
  Smartphone,
  PauseCircle,
  Eye,
  BarChart3,
  Trash2,
  Clapperboard,
  PenLine,
  Languages,
  Presentation,
  Globe,
  TrendingUp,
} from 'lucide-react'
import { Card, Button, Badge, Empty, Modal, ErrorState } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import { connectWs } from '../lib/ws'

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
  drama_generate: { label: '短剧生成', icon: Clapperboard, color: 'purple' },
  meme_generate_set: { label: '表情包批量', icon: Image, color: 'amber' },
  music_compose: { label: '音乐作曲', icon: Music, color: 'rose' },
  dh_voice_clone: { label: '声音克隆', icon: Mic, color: 'emerald' },
  copywriting_generate: { label: '文案生成', icon: PenLine, color: 'blue' },
  translation_translate: { label: '翻译', icon: Languages, color: 'indigo' },
  ppt_generate: { label: 'PPT 生成', icon: Presentation, color: 'orange' },
  web_search_query: { label: '网页搜索', icon: Globe, color: 'sky' },
  video_analyze: { label: '视频分析', icon: Video, color: 'red' },
  forecast_analyze: { label: '预测分析', icon: TrendingUp, color: 'green' },
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
const PAGE_SIZE = 20

const getUsername = () => {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')?.username || ''
  } catch {
    return ''
  }
}

// ── 统计卡 ──────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, color }) {
  return (
    <Card className="!p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2.5 rounded-xl ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xl font-bold text-gray-900 leading-tight">{value ?? '—'}</div>
          <div className="text-xs text-gray-500">{label}</div>
        </div>
      </div>
    </Card>
  )
}

// ── 详情弹窗小组件 ──────────────────────────────────────
function InfoItem({ label, value }) {
  return (
    <div>
      <div className="text-xs text-gray-400">{label}</div>
      <div className="font-mono text-xs text-gray-700 truncate">{value || '—'}</div>
    </div>
  )
}

function JsonBlock({ title, json }) {
  const text = json ? JSON.stringify(json, null, 2) : ''
  return (
    <div>
      <div className="text-xs font-medium text-gray-500 mb-1">{title}</div>
      <pre className="text-xs bg-gray-50 border border-gray-100 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap break-all">
        {text || '（空）'}
      </pre>
    </div>
  )
}

export default function TasksPage() {
  const toast = useToast()
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [filter, setFilter] = useState({ type: '', status: '' })
  const [actionId, setActionId] = useState('')
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [stats, setStats] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loadError, setLoadError] = useState('')
  const timerRef = useRef(null)
  const offsetRef = useRef(0)

  useEffect(() => {
    offsetRef.current = offset
  }, [offset])

  const buildParams = useCallback(
    (off) => {
      const params = { limit: PAGE_SIZE, offset: off }
      if (filter.type) params.type = filter.type
      if (filter.status) params.status = filter.status
      return params
    },
    [filter]
  )

  const applyPage = (data, append) => {
    const list = data.tasks || []
    setTasks((prev) => (append ? [...prev, ...list] : list))
    setTotal(data.total || 0)
    const off = data.offset || 0
    setOffset(off)
    setHasMore(off + list.length < (data.total || 0))
  }

  // 拉第一页（silent=true 时不触发 loading 态，供 WS 事件/兜底轮询静默刷新）
  const loadFirst = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true)
      try {
        const res = await api.get('/api/tasks', { params: buildParams(0) })
        applyPage(res.data, false)
        setLoadError('')
      } catch {
        // 静默失败，避免弹窗轰炸（首次/手动加载时展示错误态）
        if (!silent) setLoadError('任务列表加载失败，请检查网络后重试')
      } finally {
        setLoading(false)
      }
    },
    [buildParams]
  )

  // 静默刷新：已翻页时不打断当前浏览
  const refreshQuiet = useCallback(() => {
    if (offsetRef.current > 0) return
    loadFirst(true)
  }, [loadFirst])

  // 加载更多（分页）
  const loadMore = useCallback(async () => {
    if (loadingMore) return
    setLoadingMore(true)
    try {
      const res = await api.get('/api/tasks', {
        params: buildParams(offsetRef.current + PAGE_SIZE),
      })
      applyPage(res.data, true)
    } catch {
      // 静默失败
    } finally {
      setLoadingMore(false)
    }
  }, [buildParams, loadingMore])

  useEffect(() => {
    loadFirst()
  }, [loadFirst])

  // 任务统计卡（后端 30s 缓存，无需高频刷新）
  useEffect(() => {
    api
      .get('/api/tasks/stats')
      .then((res) => setStats(res.data))
      .catch(() => {})
  }, [])

  // WS 实时推送：任务列表事件驱动刷新；断线降级为 10s 兜底轮询
  useEffect(() => {
    const username = getUsername()
    if (!username) return
    const wsOk = { current: false }
    const unsub = connectWs(`task:user:${username}`, {
      onOpen: () => {
        wsOk.current = true
      },
      onClose: () => {
        wsOk.current = false
      },
      onMessage: () => {
        refreshQuiet()
      },
    })
    timerRef.current = setInterval(() => {
      if (!wsOk.current) refreshQuiet()
    }, 10000)
    return () => {
      unsub()
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [refreshQuiet])

  const refresh = async () => {
    setLoading(true)
    try {
      await loadFirst(true)
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
      loadFirst(true)
    } catch (e) {
      toast.error(`重试失败：${e.message}`)
    } finally {
      setActionId('')
    }
  }

  const cancelTask = async (task) => {
    const msg =
      task.status === 'running'
        ? '确定取消该任务？执行中任务将在下次进度检查时中止（已产生的部分外部消耗无法退回）'
        : '确定取消该任务？（仅排队中的任务可取消）'
    if (!confirm(msg)) return
    setActionId(task.id)
    try {
      await api.post(`/api/tasks/${task.id}/cancel`)
      toast.success('任务已取消')
      loadFirst(true)
    } catch (e) {
      toast.error(`取消失败：${e.message}`)
    } finally {
      setActionId('')
    }
  }

  const openDetail = async (task) => {
    setDetail(task)
    try {
      const res = await api.get(`/api/tasks/${task.id}`)
      setDetail(res.data)
    } catch {
      // 请求失败时保留列表摘要展示
    }
  }

  // 删除任务记录（仅终态展示按钮；不影响已保存的生成产物）
  const deleteTask = async (task) => {
    if (!confirm('确定删除该任务记录？删除后不可恢复（不影响已保存的生成产物）')) return
    setActionId(task.id)
    try {
      await api.delete(`/api/tasks/${task.id}`)
      toast.success('任务已删除')
      loadFirst(true)
      api
        .get('/api/tasks/stats')
        .then((res) => setStats(res.data))
        .catch(() => {})
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    } finally {
      setActionId('')
    }
  }

  // 清空终态任务记录（执行中的任务不受影响）
  const cleanupTasks = async () => {
    if (
      !confirm(
        '确定清空所有已完成的终态任务记录（成功/失败/已中断/已取消）？执行中的任务不受影响，删除后不可恢复'
      )
    )
      return
    try {
      const res = await api.post('/api/tasks/cleanup')
      toast.success(res.data?.message || '已清理历史任务')
      loadFirst(true)
      api
        .get('/api/tasks/stats')
        .then((r) => setStats(r.data))
        .catch(() => {})
    } catch (e) {
      toast.error(`清理失败：${e.message}`)
    }
  }

  const typeMeta = (type) =>
    TYPE_META[type] || { label: type || '未知任务', icon: FileText, color: 'gray' }
  const statusMeta = (status) =>
    STATUS_META[status] || { label: status || '未知', color: 'gray', icon: Circle }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">任务中心</h1>
          <p className="text-sm text-gray-500 mt-1">
            AI 生成任务实时进度 · 关闭页面也不中断，完成后自动保存产物
          </p>
        </div>
        <Button variant="ghost" icon={RefreshCw} onClick={refresh}>
          刷新
        </Button>
      </div>

      {/* 统计卡 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard
            icon={FileText}
            label="累计任务"
            value={stats.total}
            color="bg-brand-50 text-brand-600"
          />
          <StatCard
            icon={Zap}
            label="排队 / 执行中"
            value={stats.active}
            color="bg-blue-50 text-blue-600"
          />
          <StatCard
            icon={CheckCircle2}
            label="今日完成"
            value={stats.today_finished}
            color="bg-green-50 text-green-600"
          />
          <StatCard
            icon={BarChart3}
            label="成功率"
            value={`${stats.success_rate ?? 0}%`}
            color="bg-amber-50 text-amber-600"
          />
        </div>
      )}

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
              <option key={value} value={value}>
                {m.label}
              </option>
            ))}
          </select>
          <select
            value={filter.status}
            onChange={(e) => setFilter({ ...filter, status: e.target.value })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          {(filter.type || filter.status) && (
            <Button variant="ghost" size="sm" onClick={() => setFilter({ type: '', status: '' })}>
              清除筛选
            </Button>
          )}
          <div className="ml-auto flex items-center gap-2 text-sm text-gray-500">
            <Zap className="w-4 h-4 text-amber-500" />共 {total} 个任务
            {total > 0 && (
              <Button variant="ghost" size="sm" onClick={cleanupTasks}>
                清空已完成
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* 任务列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" />
        </div>
      ) : loadError ? (
        <Card>
          <ErrorState message={loadError} onRetry={() => loadFirst(false)} />
        </Card>
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
                  <div
                    className={`p-2.5 rounded-xl bg-${tm.color}-50 text-${tm.color}-600 shrink-0`}
                  >
                    <TypeIcon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-gray-900 text-sm">{tm.label}</span>
                      <Badge color={st.color}>{st.label}</Badge>
                      {task.priority > 0 && <Badge color="amber">P{task.priority}</Badge>}
                      <span className="text-xs text-gray-400 font-mono">{task.id}</span>
                    </div>
                    {/* 进度条 */}
                    <div className="mt-2.5 flex items-center gap-3">
                      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            task.status === 'success'
                              ? 'bg-green-500'
                              : task.status === 'failed'
                                ? 'bg-red-400'
                                : 'bg-brand-500'
                          }`}
                          style={{ width: `${task.progress || 0}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-10 text-right">
                        {active
                          ? `${Math.round(task.progress || 0)}%`
                          : task.status === 'success'
                            ? '100%'
                            : '—'}
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
                      {task.created_by && (
                        <span className="text-xs text-gray-400">by {task.created_by}</span>
                      )}
                      {task.retry_count > 0 && (
                        <span className="text-xs text-gray-400">重试 {task.retry_count} 次</span>
                      )}
                      <div className="ml-auto flex items-center gap-1.5">
                        <button
                          onClick={() => openDetail(task)}
                          title="查看详情"
                          className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-gray-50 text-gray-500 hover:bg-gray-100"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          详情
                        </button>
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
                        {(task.status === 'pending' || task.status === 'running') && (
                          <button
                            onClick={() => cancelTask(task)}
                            disabled={actionId === task.id}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:opacity-50"
                          >
                            <PauseCircle className="w-3.5 h-3.5" />
                            {actionId === task.id ? '取消中…' : '取消'}
                          </button>
                        )}
                        {!active && (
                          <button
                            onClick={() => deleteTask(task)}
                            disabled={actionId === task.id}
                            title="删除任务记录（不影响已保存产物）"
                            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-gray-50 text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            删除
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

      {/* 加载更多 */}
      {hasMore && (
        <div className="flex justify-center pt-1">
          <Button variant="ghost" onClick={loadMore} disabled={loadingMore}>
            {loadingMore ? '加载中…' : '加载更多'}
          </Button>
        </div>
      )}

      {/* 任务详情 */}
      <Modal open={!!detail} onClose={() => setDetail(null)} title="任务详情" size="lg">
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <InfoItem label="任务 ID" value={detail.id} />
              <InfoItem label="类型" value={typeMeta(detail.type).label} />
              <InfoItem label="状态" value={statusMeta(detail.status).label} />
              <InfoItem label="进度" value={`${Math.round(detail.progress || 0)}%`} />
              <InfoItem label="创建时间" value={detail.created_at} />
              <InfoItem label="开始时间" value={detail.started_at} />
              <InfoItem label="完成时间" value={detail.finished_at} />
              <InfoItem label="创建者" value={detail.created_by} />
              <InfoItem label="重试次数" value={String(detail.retry_count ?? 0)} />
              <InfoItem
                label="优先级"
                value={detail.priority > 0 ? `P${detail.priority}` : '普通'}
              />
              <InfoItem
                label="自动重试"
                value={
                  detail.max_attempts > 0
                    ? `最多 ${detail.max_attempts} 次（失败自动重试）`
                    : '关闭'
                }
              />
              <InfoItem label="阶段" value={detail.stage} />
            </div>
            {detail.error && (
              <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg p-2.5 break-all">
                {detail.error}
              </div>
            )}
            <JsonBlock title="参数 payload" json={detail.payload} />
            <JsonBlock title="结果 result" json={detail.result} />
          </div>
        )}
      </Modal>
    </div>
  )
}
