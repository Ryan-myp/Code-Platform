import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell,
  Check,
  CheckCheck,
  Trash2,
  AlertCircle,
  Info,
  AlertTriangle,
  CheckCircle2,
  Filter,
  Settings,
  ChevronDown,
} from 'lucide-react'
import {
  Card,
  Button,
  Badge,
  Empty,
  ErrorState,
  SkeletonList,
  PageHeader,
} from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PAGE_SIZE = 20

const TYPE_CONFIG = {
  info: { icon: Info, color: 'blue', label: '信息' },
  success: { icon: CheckCircle2, color: 'green', label: '成功' },
  warning: { icon: AlertTriangle, color: 'amber', label: '警告' },
  error: { icon: AlertCircle, color: 'red', label: '错误' },
  task: { icon: CheckCircle2, color: 'blue', label: '任务' },
  system: { icon: Bell, color: 'gray', label: '系统' },
}

export default function NotificationsPage() {
  const toast = useRef(useToast()).current
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [filter, setFilter] = useState({ type: '', unreadOnly: false })
  const [total, setTotal] = useState(0)
  const [unreadCount, setUnreadCount] = useState(0)
  const [offset, setOffset] = useState(0)
  const offsetRef = useRef(0)

  const loadUnreadCount = useCallback(async () => {
    try {
      const res = await api.get('/api/notifications/unread-count')
      setUnreadCount(res.data?.count || 0)
    } catch {
      // 角标失败不阻塞页面
    }
  }, [])

  const loadNotifications = useCallback(
    async (append = false) => {
      const nextOffset = append ? offsetRef.current : 0
      if (!append) {
        setLoading(true)
      } else {
        setLoadingMore(true)
      }
      setLoadError('')
      try {
        const res = await api.get('/api/notifications', {
          params: {
            limit: PAGE_SIZE,
            offset: nextOffset,
            unread_only: filter.unreadOnly || undefined,
          },
        })
        const { items = [], total: t = 0 } = res.data || {}
        setNotifications((prev) => (append ? [...prev, ...items] : items))
        setTotal(t)
        offsetRef.current = nextOffset + items.length
        setOffset(offsetRef.current)
      } catch {
        setLoadError('通知加载失败，请检查网络后重试')
        toast.error('加载通知失败')
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [filter, toast]
  )

  useEffect(() => {
    offsetRef.current = 0
    setOffset(0)
    setNotifications([])
    setTotal(0)
    loadNotifications(false)
    loadUnreadCount()
  }, [filter, loadNotifications, loadUnreadCount])

  const markRead = async (notifId) => {
    try {
      await api.put(`/api/notifications/${notifId}/read`)
      setNotifications((prev) =>
        prev.map((n) => (n.id === notifId ? { ...n, read: 1 } : n))
      )
      setUnreadCount((c) => Math.max(0, c - 1))
    } catch {
      toast.error('操作失败')
    }
  }

  const markAllRead = async () => {
    try {
      await api.put('/api/notifications/read-all')
      setNotifications((prev) => prev.map((n) => ({ ...n, read: 1 })))
      setUnreadCount(0)
      toast.success('已全部标记为已读')
    } catch {
      toast.error('操作失败')
    }
  }

  const deleteNotif = async (notifId) => {
    try {
      await api.delete(`/api/notifications/${notifId}`)
      setNotifications((prev) => prev.filter((n) => n.id !== notifId))
      setTotal((t) => Math.max(0, t - 1))
      toast.success('已删除')
    } catch {
      toast.error('删除失败')
    }
  }

  const filteredNotifications = notifications.filter((n) => {
    if (filter.type && n.type !== filter.type) return false
    return true
  })

  const hasMore = offset < total

  return (
    <div className="space-y-6">
      <PageHeader
        title="通知中心"
        description={
          unreadCount > 0
            ? `有 ${unreadCount} 条未读通知待查看`
            : '所有通知均已读'
        }
        icon={Bell}
        iconColor="from-pink-500 to-rose-600"
        actions={
          <>
            <Button variant="ghost" icon={Settings} onClick={() => navigate('/config')}>
              通知设置
            </Button>
            {unreadCount > 0 && (
              <Button variant="primary" icon={CheckCheck} onClick={markAllRead}>
                全部已读
                <Badge color="red" size="sm" className="ml-1.5">
                  {unreadCount}
                </Badge>
              </Button>
            )}
          </>
        }
      />

      {/* 过滤器 */}
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">筛选：</span>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={filter.unreadOnly}
              onChange={(e) => setFilter({ ...filter, unreadOnly: e.target.checked })}
              className="w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
            />
            <span className="text-sm text-gray-600">仅显示未读</span>
          </label>
          <select
            value={filter.type}
            onChange={(e) => setFilter({ ...filter, type: e.target.value })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="">全部类型</option>
            {Object.entries(TYPE_CONFIG).map(([key, config]) => (
              <option key={key} value={key}>
                {config.label}
              </option>
            ))}
          </select>
          {(filter.type || filter.unreadOnly) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setFilter({ type: '', unreadOnly: false })}
            >
              清除筛选
            </Button>
          )}
          <div className="ml-auto text-sm text-gray-500">
            共 {total} 条通知
            {unreadCount > 0 && (
              <span className="ml-2 text-red-500 font-medium">{unreadCount} 条未读</span>
            )}
          </div>
        </div>
      </Card>

      {/* 通知列表 */}
      {loading ? (
        <SkeletonList count={5} />
      ) : loadError ? (
        <Card>
          <ErrorState message={loadError} onRetry={() => loadNotifications(false)} />
        </Card>
      ) : filteredNotifications.length === 0 ? (
        <Card>
          <Empty icon={Bell} title="暂无通知" description="当有新通知时会显示在这里" />
        </Card>
      ) : (
        <>
          <div className="space-y-2">
            {filteredNotifications.map((notif) => {
              const typeConfig = TYPE_CONFIG[notif.type] || TYPE_CONFIG.info
              const TypeIcon = typeConfig.icon
              const isUnread = !notif.read

              return (
                <Card
                  key={notif.id}
                  className={`!p-4 transition-all ${
                    isUnread ? 'bg-blue-50/50 border-blue-200' : 'bg-white'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                      <TypeIcon className="w-4 h-4 text-gray-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-sm font-medium ${
                            isUnread ? 'text-gray-900' : 'text-gray-600'
                          }`}
                        >
                          {notif.title}
                        </span>
                        {isUnread && <span className="w-2 h-2 rounded-full bg-blue-500" />}
                        <Badge color={typeConfig.color} size="sm">
                          {typeConfig.label}
                        </Badge>
                      </div>
                      {notif.content && (
                        <p
                          className={`text-sm mt-1 ${
                            isUnread ? 'text-gray-700' : 'text-gray-500'
                          }`}
                        >
                          {notif.content}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                        <span>{notif.created_at?.replace('T', ' ').slice(0, 16)}</span>
                        {notif.read_at && (
                          <span className="flex items-center gap-1">
                            <Check className="w-3 h-3" />
                            已读
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {isUnread && (
                        <button
                          onClick={() => markRead(notif.id)}
                          className="p-1.5 text-gray-400 hover:text-blue-500 rounded-lg hover:bg-blue-50 transition-colors"
                          title="标记为已读"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => deleteNotif(notif.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>

          {/* 分页加载更多 */}
          {hasMore && (
            <div className="flex justify-center pt-2">
              <Button
                variant="ghost"
                loading={loadingMore}
                icon={ChevronDown}
                onClick={() => loadNotifications(true)}
              >
                加载更多（已显示 {offset} / {total}）
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
