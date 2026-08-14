import React, { useState, useEffect } from 'react'
import { Shield, Clock, AlertCircle, CheckCircle, XCircle, User, Activity } from 'lucide-react'
import { api } from '../lib/api'
import Pagination from '../components/Pagination'

const ACTION_LABELS = {
  login: '登录',
  logout: '登出',
  register: '注册',
  password_change: '修改密码',
  password_reset: '重置密码',
  upgrade: '升级会员',
  downgrade: '降级会员',
  template_upload: '上传模板',
  template_delete: '删除模板',
  template_buy: '购买模板',
  invite: '邀请用户',
  share: '分享内容',
  api_key_create: '创建API Key',
  api_key_delete: '删除API Key',
  config_change: '修改配置',
  user_create: '创建用户',
  user_update: '更新用户',
  user_delete: '删除用户',
  role_change: '修改角色',
}

const ACTION_COLORS = {
  login: 'bg-blue-100 text-blue-700',
  logout: 'bg-gray-100 text-gray-700',
  register: 'bg-emerald-100 text-emerald-700',
  password_change: 'bg-purple-100 text-purple-700',
  upgrade: 'bg-amber-100 text-amber-700',
  template_upload: 'bg-indigo-100 text-indigo-700',
  template_buy: 'bg-green-100 text-green-700',
  user_create: 'bg-cyan-100 text-cyan-700',
  user_delete: 'bg-red-100 text-red-700',
}

export default function AuditLogPage() {
  const [logs, setLogs] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState({ user: '', action: '', days: 7 })

  useEffect(() => {
    loadAll()
  }, [filter])

  const loadAll = async () => {
    setLoading(true)
    try {
      const endDate = new Date().toISOString().slice(0, 10)
      const startDate = new Date(Date.now() - filter.days * 86400000).toISOString().slice(0, 10)
      const [logsRes, statsRes] = await Promise.all([
        api.get('/api/audit/logs', { params: { ...filter, start_date: startDate, end_date: endDate } }),
        api.get('/api/audit/stats'),
      ])
      setLogs(logsRes.data?.logs || [])
      setStats(statsRes.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-gray-500 mt-3">加载中…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-2xl flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
        <div>
          <p className="font-medium text-red-700">加载失败</p>
          <p className="text-sm text-red-500 mt-1">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: '今日操作', value: stats.today_count, icon: Activity, color: 'from-blue-500 to-indigo-500' },
            { label: '失败操作', value: stats.fail_count, icon: XCircle, color: 'from-red-500 to-rose-500' },
            { label: '总日志数', value: logs.length, icon: Shield, color: 'from-emerald-500 to-teal-500' },
            { label: '时间范围', value: `${filter.days}天`, icon: Clock, color: 'from-amber-500 to-orange-500' },
          ].map((card, i) => (
            <div key={i} className={`bg-gradient-to-br ${card.color} rounded-2xl p-4 text-white`}>
              <div className="flex items-center justify-between">
                <card.icon className="w-6 h-6 opacity-80" />
                <p className="text-xs opacity-80">{card.label}</p>
              </div>
              <p className="text-2xl font-bold mt-2">{card.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* 筛选器 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-4 flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="用户ID"
            value={filter.user}
            onChange={e => setFilter(f => ({ ...f, user: e.target.value }))}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:border-purple-500 outline-none"
          />
        </div>
        <select
          value={filter.action}
          onChange={e => setFilter(f => ({ ...f, action: e.target.value }))}
          className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:border-purple-500 outline-none"
        >
          <option value="">所有操作</option>
          {Object.entries(ACTION_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          value={filter.days}
          onChange={e => setFilter(f => ({ ...f, days: Number(e.target.value) }))}
          className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:border-purple-500 outline-none"
        >
          <option value={7}>最近7天</option>
          <option value={14}>最近14天</option>
          <option value={30}>最近30天</option>
          <option value={90}>最近90天</option>
        </select>
        <button
          onClick={loadAll}
          className="px-4 py-1.5 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 transition-colors"
        >
          刷新
        </button>
      </div>

      {/* 日志列表 */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        {logs.length === 0 ? (
          <div className="p-8 text-center">
            <Shield className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">暂无审计日志</p>
            <p className="text-sm text-gray-400 mt-1">用户操作将在此记录</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-100 bg-gray-50">
                  <th className="px-4 py-3 font-medium">时间</th>
                  <th className="px-4 py-3 font-medium">用户</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                  <th className="px-4 py-3 font-medium">目标</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">详情</th>
                </tr>
              </thead>
              <tbody>
                <Pagination
                  items={logs}
                  pageSize={10}
                  label={`共 ${logs.length} 条日志`}
                  renderItem={(log, idx) => (
                    <tr key={idx} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-600 text-xs">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 font-medium">{log.user_id}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-600'}`}>
                          {ACTION_LABELS[log.action] || log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{log.target_type || '-'}</td>
                      <td className="px-4 py-3">
                        {log.success ? (
                          <CheckCircle className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-500" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs max-w-[200px] truncate">
                        {log.error || log.details || '-'}
                      </td>
                    </tr>
                  )}
                />
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
