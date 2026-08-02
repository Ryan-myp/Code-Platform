import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bot, Layers, FolderKanban, CheckCircle2, Clock, Bell, Zap,
  Plus, ArrowRight, TrendingUp, AlertCircle, FileText, Image, Film, Music,
  Play, Users, Target, Sparkles, ChevronRight, BarChart3, Activity
} from 'lucide-react'
import { Card, Button, Badge, Modal } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PRIORITY_COLORS = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'gray' }
const STATUS_CONFIG = {
  todo: { label: '待办', color: 'gray' },
  in_progress: { label: '进行中', color: 'blue' },
  done: { label: '已完成', color: 'green' },
  cancelled: { label: '已取消', color: 'red' },
}

export default function HomePage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState(null)
  const [tasks, setTasks] = useState([])
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [newTask, setNewTask] = useState({ title: '', description: '', priority: 'P2' })

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [statsRes, recentRes, tasksRes, notifsRes] = await Promise.all([
        api.get('/api/home/stats'),
        api.get('/api/home/recent'),
        api.get('/api/tasks?status=todo'),
        api.get('/api/notifications?unread_only=true&limit=10'),
      ])
      setStats(statsRes.data)
      setRecent(recentRes.data)
      setTasks(tasksRes.data)
      setNotifications(notifsRes.data)
    } catch (e) {
      toast.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  const createTask = async () => {
    if (!newTask.title.trim()) { toast.error('请输入任务标题'); return }
    try {
      await api.post('/api/tasks', newTask)
      toast.success('任务已创建')
      setShowTaskModal(false)
      setNewTask({ title: '', description: '', priority: 'P2' })
      loadData()
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    }
  }

  const updateTaskStatus = async (taskId, status) => {
    try {
      await api.put(`/api/tasks/${taskId}`, { status })
      toast.success('状态已更新')
      loadData()
    } catch (e) {
      toast.error(`更新失败：${e.message}`)
    }
  }

  const markNotifRead = async (notifId) => {
    try {
      await api.put(`/api/notifications/${notifId}/read`)
      loadData()
    } catch (e) { /* ignore */ }
  }

  const statCards = [
    { label: 'Agent', value: stats?.agents || 0, icon: Bot, color: 'from-emerald-500 to-teal-600', path: '/agents' },
    { label: 'Workflow', value: stats?.workflows || 0, icon: Layers, color: 'from-blue-500 to-indigo-600', path: '/workflows' },
    { label: '项目', value: stats?.projects || 0, icon: FolderKanban, color: 'from-violet-500 to-purple-600', path: '/projects' },
    { label: '待办任务', value: stats?.tasks_todo || 0, icon: CheckCircle2, color: 'from-amber-500 to-orange-600', path: '/tasks' },
    { label: '未读通知', value: stats?.notifications_unread || 0, icon: Bell, color: 'from-pink-500 to-rose-600', path: '/notifications' },
    { label: '成果', value: stats?.artifacts || 0, icon: FileText, color: 'from-cyan-500 to-blue-600', path: '/artifacts' },
  ]

  const quickActions = [
    { label: '新建 Agent', icon: Bot, path: '/agents', color: 'bg-emerald-500' },
    { label: '新建 Workflow', icon: Layers, path: '/workflows', color: 'bg-blue-500' },
    { label: '图片生成', icon: Image, path: '/image-factory', color: 'bg-purple-500' },
    { label: '视频生成', icon: Film, path: '/video-factory', color: 'bg-pink-500' },
    { label: '音乐生成', icon: Music, path: '/music-factory', color: 'bg-indigo-500' },
    { label: '知识库', icon: Sparkles, path: '/knowledge-bases', color: 'bg-amber-500' },
  ]

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">工作台</h1>
          <p className="text-sm text-gray-500 mt-1">欢迎回来，这是你的工作概览</p>
        </div>
        <div className="flex gap-2">
          <Button variant="primary" icon={Plus} onClick={() => setShowTaskModal(true)}>
            新建任务
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            onClick={() => navigate(card.path)}
            className="bg-white rounded-xl border border-gray-200 p-4 cursor-pointer hover:shadow-md transition-all group"
          >
            <div className="flex items-center justify-between mb-2">
              <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${card.color} flex items-center justify-center`}>
                <card.icon className="w-4 h-4 text-white" />
              </div>
              <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-gray-500 transition-colors" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{card.value}</div>
            <div className="text-xs text-gray-500">{card.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 待办任务 */}
        <div className="lg:col-span-2">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-amber-500" />
                <h2 className="font-semibold text-gray-900">待办任务</h2>
                <Badge color="gray">{tasks.length}</Badge>
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate('/tasks')}>
                查看全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
            {tasks.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <CheckCircle2 className="w-10 h-10 mx-auto mb-2 opacity-50" />
                <p>暂无待办任务</p>
              </div>
            ) : (
              <div className="space-y-2">
                {tasks.slice(0, 5).map((task) => (
                  <div key={task.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
                    <input
                      type="checkbox"
                      className="w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                      onChange={() => updateTaskStatus(task.id, 'done')}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">{task.title}</div>
                      {task.description && (
                        <div className="text-xs text-gray-500 truncate">{task.description}</div>
                      )}
                    </div>
                    <Badge color={PRIORITY_COLORS[task.priority]}>{task.priority}</Badge>
                    {task.due_date && (
                      <div className="flex items-center gap-1 text-xs text-gray-400">
                        <Clock className="w-3 h-3" />
                        {task.due_date}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧面板 */}
        <div className="space-y-6">
          {/* 快捷操作 */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-5 h-5 text-blue-500" />
              <h2 className="font-semibold text-gray-900">快捷操作</h2>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  onClick={() => navigate(action.path)}
                  className="flex items-center gap-2 p-2.5 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-left"
                >
                  <div className={`w-7 h-7 rounded-lg ${action.color} flex items-center justify-center`}>
                    <action.icon className="w-3.5 h-3.5 text-white" />
                  </div>
                  <span className="text-xs font-medium text-gray-700">{action.label}</span>
                </button>
              ))}
            </div>
          </Card>

          {/* 最新通知 */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Bell className="w-5 h-5 text-pink-500" />
                <h2 className="font-semibold text-gray-900">最新通知</h2>
                {notifications.length > 0 && (
                  <Badge color="red">{notifications.length}</Badge>
                )}
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate('/notifications')}>
                全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
            {notifications.length === 0 ? (
              <div className="text-center py-6 text-gray-400">
                <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-xs">暂无新通知</p>
              </div>
            ) : (
              <div className="space-y-2">
                {notifications.slice(0, 4).map((notif) => (
                  <div
                    key={notif.id}
                    onClick={() => markNotifRead(notif.id)}
                    className="p-2.5 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                  >
                    <div className="flex items-start gap-2">
                      <AlertCircle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                        notif.type === 'error' ? 'text-red-500' :
                        notif.type === 'warning' ? 'text-amber-500' :
                        notif.type === 'success' ? 'text-green-500' : 'text-blue-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-gray-900 truncate">{notif.title}</div>
                        <div className="text-xs text-gray-500 truncate">{notif.content}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* 最近项目 */}
      {recent?.projects?.length > 0 && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FolderKanban className="w-5 h-5 text-violet-500" />
              <h2 className="font-semibold text-gray-900">最近项目</h2>
            </div>
            <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
              查看全部 <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {recent.projects.map((project) => (
              <div
                key={project.id}
                onClick={() => navigate(`/projects/${project.id}`)}
                className="p-3 rounded-lg border border-gray-200 hover:border-violet-300 hover:shadow-sm cursor-pointer transition-all"
              >
                <div className="font-medium text-sm text-gray-900 truncate">{project.name}</div>
                <div className="flex items-center gap-2 mt-2">
                  <Badge color={project.status === 'active' ? 'green' : 'gray'}>
                    {project.status}
                  </Badge>
                  <span className="text-xs text-gray-400">{project.updated_at?.split('T')[0]}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 新建任务弹窗 */}
      <Modal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        title="新建任务"
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowTaskModal(false)}>取消</Button>
            <Button variant="primary" onClick={createTask}>创建</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">任务标题 *</label>
            <input
              type="text"
              value={newTask.title}
              onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
              placeholder="输入任务标题"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">任务描述</label>
            <textarea
              value={newTask.description}
              onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
              placeholder="输入任务描述"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">优先级</label>
            <select
              value={newTask.priority}
              onChange={(e) => setNewTask({ ...newTask, priority: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            >
              <option value="P0">P0 - 紧急</option>
              <option value="P1">P1 - 高</option>
              <option value="P2">P2 - 中</option>
              <option value="P3">P3 - 低</option>
            </select>
          </div>
        </div>
      </Modal>
    </div>
  )
}
