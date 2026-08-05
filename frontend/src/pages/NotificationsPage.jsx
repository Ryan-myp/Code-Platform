import React, { useState, useEffect } from 'react'
import {
  Bell, Check, CheckCheck, Trash2, AlertCircle, Info, AlertTriangle,
  CheckCircle2, X, Filter, Search
} from 'lucide-react'
import { Card, Button, Badge, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const TYPE_CONFIG = {
  info: { icon: Info, color: 'blue', label: '信息' },
  success: { icon: CheckCircle2, color: 'green', label: '成功' },
  warning: { icon: AlertTriangle, color: 'amber', label: '警告' },
  error: { icon: AlertCircle, color: 'red', label: '错误' },
  task: { icon: CheckCircle2, color: 'blue', label: '任务' },
  system: { icon: Bell, color: 'gray', label: '系统' },
}

export default function NotificationsPage() {
  const toast = useToast()
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ type: '', unreadOnly: false })

  useEffect(() => { loadNotifications() }, [filter])

  const loadNotifications = async () => {
    setLoading(true)
    try {
      let url = '/api/notifications?'
      if (filter.unreadOnly) url += 'unread_only=true&'
      const res = await api.get(url)
      setNotifications(res.data)
    } catch {
      toast.error('加载通知失败')
    } finally {
      setLoading(false)
    }
  }

  const markRead = async (notifId) => {
    try {
      await api.put(`/api/notifications/${notifId}/read`)
      loadNotifications()
    } catch {
      toast.error('操作失败')
    }
  }

  const markAllRead = async () => {
    try {
      await api.put('/api/notifications/read-all')
      toast.success('已全部标记为已读')
      loadNotifications()
    } catch {
      toast.error('操作失败')
    }
  }

  const deleteNotif = async (notifId) => {
    try {
      await api.delete(`/api/notifications/${notifId}`)
      toast.success('已删除')
      loadNotifications()
    } catch {
      toast.error('删除失败')
    }
  }

  const unreadCount = notifications.filter(n => !n.read).length

  const filteredNotifications = notifications.filter(n => {
    if (filter.type && n.type !== filter.type) return false
    return true
  })

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">通知中心</h1>
          <p className="text-sm text-gray-500 mt-1">
            {unreadCount > 0 ? `${unreadCount} 条未读通知` : '所有通知已读'}
          </p>
        </div>
        <div className="flex gap-2">
          {unreadCount > 0 && (
            <Button variant="primary" icon={CheckCheck} onClick={markAllRead}>
              全部已读
            </Button>
          )}
        </div>
      </div>

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
              <option key={key} value={key}>{config.label}</option>
            ))}
          </select>
          {(filter.type || filter.unreadOnly) && (
            <Button variant="ghost" size="sm" onClick={() => setFilter({ type: '', unreadOnly: false })}>
              清除筛选
            </Button>
          )}
          <div className="ml-auto text-sm text-gray-500">
            共 {filteredNotifications.length} 条通知
          </div>
        </div>
      </Card>

      {/* 通知列表 */}
      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" />
        </div>
      ) : filteredNotifications.length === 0 ? (
        <Card>
          <Empty icon={Bell} title="暂无通知" description="当有新通知时会显示在这里" />
        </Card>
      ) : (
        <div className="space-y-2">
          {filteredNotifications.map((notif) => {
            const typeConfig = TYPE_CONFIG[notif.type] || TYPE_CONFIG.info
            const TypeIcon = typeConfig.icon
            const isUnread = !notif.read

            return (
              <Card
                key={notif.id}
                className={`!p-4 transition-all ${isUnread ? 'bg-blue-50/50 border-blue-200' : 'bg-white'}`}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-8 h-8 rounded-lg bg-${typeConfig.color}-100 flex items-center justify-center flex-shrink-0`}>
                    <TypeIcon className={`w-4 h-4 text-${typeConfig.color}-600`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${isUnread ? 'text-gray-900' : 'text-gray-600'}`}>
                        {notif.title}
                      </span>
                      {isUnread && (
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                      )}
                      <Badge color={typeConfig.color} size="sm">{typeConfig.label}</Badge>
                    </div>
                    {notif.content && (
                      <p className={`text-sm mt-1 ${isUnread ? 'text-gray-700' : 'text-gray-500'}`}>
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
      )}
    </div>
  )
}
