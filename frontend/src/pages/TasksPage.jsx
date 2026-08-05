import React, { useState, useEffect } from 'react'
import {
  CheckCircle2, Circle, Clock, AlertCircle, Plus, Filter, Search,
  Calendar, Tag, User, MoreVertical, Edit2, Trash2, X, ChevronDown
} from 'lucide-react'
import { Card, Button, Badge, Modal, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PRIORITY_OPTIONS = [
  { value: 'P0', label: 'P0 - 紧急', color: 'red' },
  { value: 'P1', label: 'P1 - 高', color: 'orange' },
  { value: 'P2', label: 'P2 - 中', color: 'blue' },
  { value: 'P3', label: 'P3 - 低', color: 'gray' },
]

const STATUS_OPTIONS = [
  { value: 'todo', label: '待办', color: 'gray', icon: Circle },
  { value: 'in_progress', label: '进行中', color: 'blue', icon: Clock },
  { value: 'done', label: '已完成', color: 'green', icon: CheckCircle2 },
  { value: 'cancelled', label: '已取消', color: 'red', icon: X },
]

export default function TasksPage() {
  const toast = useToast()
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ status: '', priority: '' })
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTask, setEditingTask] = useState(null)
  const [formData, setFormData] = useState({
    title: '', description: '', priority: 'P2', due_date: '', tags: [], assigned_to: ''
  })

  useEffect(() => { loadTasks() }, [filter])

  const loadTasks = async () => {
    setLoading(true)
    try {
      let url = '/api/tasks?'
      if (filter.status) url += `status=${filter.status}&`
      if (filter.priority) url += `priority=${filter.priority}&`
      const res = await api.get(url)
      setTasks(res.data)
    } catch {
      toast.error('加载任务失败')
    } finally {
      setLoading(false)
    }
  }

  const openCreateModal = () => {
    setEditingTask(null)
    setFormData({ title: '', description: '', priority: 'P2', due_date: '', tags: [], assigned_to: '' })
    setShowCreateModal(true)
  }

  const openEditModal = (task) => {
    setEditingTask(task)
    setFormData({
      title: task.title,
      description: task.description || '',
      priority: task.priority,
      due_date: task.due_date || '',
      tags: task.tags || [],
      assigned_to: task.assigned_to || '',
    })
    setShowCreateModal(true)
  }

  const saveTask = async () => {
    if (!formData.title.trim()) { toast.error('请输入任务标题'); return }
    try {
      if (editingTask) {
        await api.put(`/api/tasks/${editingTask.id}`, formData)
        toast.success('任务已更新')
      } else {
        await api.post('/api/tasks', formData)
        toast.success('任务已创建')
      }
      setShowCreateModal(false)
      loadTasks()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    }
  }

  const updateStatus = async (taskId, status) => {
    try {
      await api.put(`/api/tasks/${taskId}`, { status })
      toast.success('状态已更新')
      loadTasks()
    } catch (e) {
      toast.error(`更新失败：${e.message}`)
    }
  }

  const deleteTask = async (taskId) => {
    if (!confirm('确定删除此任务？')) return
    try {
      await api.delete(`/api/tasks/${taskId}`)
      toast.success('任务已删除')
      loadTasks()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const groupedTasks = {
    todo: tasks.filter(t => t.status === 'todo'),
    in_progress: tasks.filter(t => t.status === 'in_progress'),
    done: tasks.filter(t => t.status === 'done'),
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">任务中心</h1>
          <p className="text-sm text-gray-500 mt-1">管理所有任务和待办事项</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={openCreateModal}>
          新建任务
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
            value={filter.status}
            onChange={(e) => setFilter({ ...filter, status: e.target.value })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <select
            value={filter.priority}
            onChange={(e) => setFilter({ ...filter, priority: e.target.value })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="">全部优先级</option>
            {PRIORITY_OPTIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          {(filter.status || filter.priority) && (
            <Button variant="ghost" size="sm" onClick={() => setFilter({ status: '', priority: '' })}>
              清除筛选
            </Button>
          )}
          <div className="ml-auto text-sm text-gray-500">
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
          <Empty icon={CheckCircle2} title="暂无任务" description="点击「新建任务」创建第一个任务" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {STATUS_OPTIONS.filter(s => s.value !== 'cancelled').map((statusConfig) => {
            const StatusIcon = statusConfig.icon
            const statusTasks = groupedTasks[statusConfig.value] || []
            return (
              <div key={statusConfig.value} className="space-y-3">
                <div className="flex items-center gap-2 px-1">
                  <StatusIcon className={`w-4 h-4 text-${statusConfig.color}-500`} />
                  <span className="font-medium text-sm text-gray-700">{statusConfig.label}</span>
                  <Badge color={statusConfig.color}>{statusTasks.length}</Badge>
                </div>
                <div className="space-y-2">
                  {statusTasks.map((task) => (
                    <Card key={task.id} className="!p-3">
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={task.status === 'done'}
                          onChange={() => updateStatus(task.id, task.status === 'done' ? 'todo' : 'done')}
                          className="w-4 h-4 mt-0.5 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                        />
                        <div className="flex-1 min-w-0">
                          <div className={`text-sm font-medium ${task.status === 'done' ? 'line-through text-gray-400' : 'text-gray-900'}`}>
                            {task.title}
                          </div>
                          {task.description && (
                            <div className="text-xs text-gray-500 mt-1 line-clamp-2">{task.description}</div>
                          )}
                          <div className="flex items-center gap-2 mt-2 flex-wrap">
                            <Badge color={PRIORITY_OPTIONS.find(p => p.value === task.priority)?.color}>
                              {task.priority}
                            </Badge>
                            {task.due_date && (
                              <span className="flex items-center gap-1 text-xs text-gray-400">
                                <Calendar className="w-3 h-3" />
                                {task.due_date}
                              </span>
                            )}
                            {task.assigned_to && (
                              <span className="flex items-center gap-1 text-xs text-gray-400">
                                <User className="w-3 h-3" />
                                {task.assigned_to}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => openEditModal(task)}
                            className="p-1 text-gray-400 hover:text-gray-600 rounded"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteTask(task.id)}
                            className="p-1 text-gray-400 hover:text-red-500 rounded"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 创建/编辑弹窗 */}
      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={editingTask ? '编辑任务' : '新建任务'}
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowCreateModal(false)}>取消</Button>
            <Button variant="primary" onClick={saveTask}>
              {editingTask ? '保存' : '创建'}
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">任务标题 *</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="输入任务标题"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">任务描述</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="输入任务描述"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">优先级</label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              >
                {PRIORITY_OPTIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">截止日期</label>
              <input
                type="date"
                value={formData.due_date}
                onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">负责人</label>
            <input
              type="text"
              value={formData.assigned_to}
              onChange={(e) => setFormData({ ...formData, assigned_to: e.target.value })}
              placeholder="输入负责人"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
