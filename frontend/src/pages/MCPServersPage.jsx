import React, { useState, useEffect, useCallback } from 'react'
import {
  Server,
  Plus,
  Trash2,
  Edit2,
  Search,
  Terminal,
  Globe,
  RefreshCw,
  Play,
  Square,
  Wifi,
  WifiOff,
  LayoutGrid,
  List as ListIcon,
  KeyRound,
  User,
  Cable,
  Loader2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import {
  Modal,
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  Badge,
  PageHeader,
  ConfirmDialog,
} from '../components/ui'

const TRANSPORTS = [
  { value: 'stdio', label: 'stdio (标准输入输出)', icon: Terminal },
  { value: 'sse', label: 'SSE (Server-Sent Events)', icon: Globe },
  { value: 'http', label: 'HTTP (Streamable)', icon: Globe },
]

// 认证方式
const AUTH_TYPES = [
  { value: 'none', label: '无认证', icon: Wifi },
  { value: 'bearer', label: 'Bearer Token', icon: KeyRound },
  { value: 'basic', label: 'Basic 认证', icon: User },
  { value: 'api_key', label: 'API Key 请求头', icon: KeyRound },
]

// 将后端返回的 args（可能是 JSON 字符串或数组）转为空格分隔的可读字符串
function argsToString(args) {
  if (!args) return ''
  if (Array.isArray(args)) return args.join(' ')
  if (typeof args === 'string') {
    // 后端存储为 JSON 字符串，尝试解析
    try {
      const parsed = JSON.parse(args)
      return Array.isArray(parsed) ? parsed.join(' ') : parsed
    } catch {
      return args
    }
  }
  return ''
}

// 将空格分隔的参数字符串转为数组
function parseArgs(str) {
  const s = (str || '').trim()
  if (!s) return []
  return s.split(/\s+/)
}

// 认证方式标签
const AUTH_LABELS = { bearer: 'Bearer', basic: 'Basic', api_key: 'API Key' }

// MCP 服务器卡片
function MCPServerCard({
  server,
  onEdit,
  onDelete,
  onToggle,
  onTest,
  testing,
  toggling,
  viewMode,
}) {
  const isActive = server.status === 'active'
  const transport = server.transport || server.transport_type || 'stdio'
  const authType = server.auth_type || 'none'

  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex items-center gap-4">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center text-white flex-shrink-0 bg-gradient-to-br ${
            isActive ? 'from-emerald-500 to-green-600' : 'from-gray-400 to-gray-500'
          }`}
        >
          <Server className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{server.name}</h3>
            <Badge status={isActive ? 'active' : 'inactive'} dot />
          </div>
          <p className="text-sm text-gray-500 truncate font-mono text-xs">
            {transport === 'stdio' ? server.command || '-' : server.url || '-'}
          </p>
        </div>
        <div className="hidden sm:flex items-center gap-2 text-xs text-gray-500 flex-shrink-0">
          <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg font-mono">
            {transport}
          </span>
          {authType !== 'none' && (
            <span
              className="px-2 py-1 bg-orange-50 text-orange-600 rounded-lg flex items-center gap-1"
              title="已配置授权验证"
            >
              <KeyRound className="w-3 h-3" />
              {AUTH_LABELS[authType] || authType}
            </span>
          )}
          <span className="flex items-center gap-1">
            {isActive ? (
              <Wifi className="w-3.5 h-3.5 text-emerald-500" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-gray-400" />
            )}
          </span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onTest?.(server)}
            disabled={testing === server.id}
            className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
            title="测试连接"
          >
            {testing === server.id ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Cable className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={() => onToggle(server)}
            disabled={toggling === server.id}
            className={`p-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              isActive
                ? 'hover:bg-red-50 text-gray-400 hover:text-red-600'
                : 'hover:bg-emerald-50 text-gray-400 hover:text-emerald-600'
            }`}
            title={isActive ? '停止' : '启动'}
          >
            {toggling === server.id ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : isActive ? (
              <Square className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={() => onEdit(server)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(server)}
            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`bg-white rounded-2xl border p-5 transition-all duration-200 hover:shadow-lg flex flex-col ${
        isActive ? 'border-emerald-200 bg-emerald-50/30' : 'border-gray-200'
      }`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center text-white flex-shrink-0 shadow-lg bg-gradient-to-br ${
              isActive ? 'from-emerald-500 to-green-600' : 'from-gray-400 to-gray-500'
            }`}
          >
            <Server className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{server.name}</h3>
            <span
              className={`inline-flex items-center gap-1 text-xs ${isActive ? 'text-emerald-600' : 'text-gray-500'}`}
            >
              {isActive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {isActive ? '已连接' : '未连接'}
            </span>
          </div>
        </div>
        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg text-xs font-mono flex-shrink-0">
          {transport}
        </span>
        {authType !== 'none' && (
          <span
            className="px-2 py-1 bg-orange-50 text-orange-600 rounded-lg text-xs font-mono flex-shrink-0 flex items-center gap-1"
            title="已配置授权验证"
          >
            <KeyRound className="w-3 h-3" />
            {AUTH_LABELS[authType] || authType}
          </span>
        )}
      </div>

      <div className="space-y-2 text-sm text-gray-600 mb-4 flex-1">
        {transport === 'sse' ? (
          <p className="flex items-center gap-2 min-w-0">
            <Globe className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="text-xs truncate font-mono">{server.url || '-'}</span>
          </p>
        ) : (
          <>
            <p className="flex items-center gap-2 min-w-0">
              <Terminal className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-xs truncate font-mono">{server.command || '-'}</span>
            </p>
            {argsToString(server.args) && (
              <p className="flex items-center gap-2 min-w-0 pl-6">
                <span className="text-xs truncate font-mono text-gray-400">
                  {argsToString(server.args)}
                </span>
              </p>
            )}
          </>
        )}
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <span className="text-xs text-gray-400">{formatRelativeTime(server.created_at)}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onTest?.(server)}
            disabled={testing === server.id}
            className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
            title="测试连接"
          >
            {testing === server.id ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Cable className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={() => onToggle(server)}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              isActive
                ? 'bg-red-50 text-red-600 hover:bg-red-100'
                : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
            }`}
          >
            {isActive ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {isActive ? '停止' : '启动'}
          </button>
          <button
            onClick={() => onEdit(server)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(server)}
            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// 创建/编辑表单
function MCPFormModal({ open, onClose, onSubmit, editing, loading }) {
  const [form, setForm] = useState({
    name: '',
    transport_type: 'stdio',
    command: '',
    args: '',
    url: '',
    auth_type: 'none',
    auth_token: '',
    auth_username: '',
    auth_password: '',
    auth_header: 'X-API-Key',
    auth_key: '',
    env: '',
  })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (!open) return
    if (editing) {
      // auth_config 为后端脱敏值：凭证留空 = 保持不变
      const ac = editing.auth_config || {}
      const envStr =
        editing.env && typeof editing.env === 'object'
          ? Object.entries(editing.env)
              .map(([k, v]) => `${k}=${v}`)
              .join('\n')
          : ''
      setForm({
        name: editing.name || '',
        transport_type: editing.transport_type || editing.transport || 'stdio',
        command: editing.command || '',
        args: argsToString(editing.args),
        url: editing.url || '',
        auth_type: editing.auth_type || 'none',
        auth_token: '',
        auth_username: ac.username || '',
        auth_password: '',
        auth_header: ac.header_name || 'X-API-Key',
        auth_key: '',
        env: envStr,
      })
    } else {
      setForm({
        name: '',
        transport_type: 'stdio',
        command: '',
        args: '',
        url: '',
        auth_type: 'none',
        auth_token: '',
        auth_username: '',
        auth_password: '',
        auth_header: 'X-API-Key',
        auth_key: '',
        env: '',
      })
    }
    setErrors({})
  }, [open, editing])

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入 MCP 服务器名称'
    if (form.name.length > 80) e.name = '名称不能超过 80 个字符'
    if (form.transport_type === 'stdio') {
      if (!form.command.trim()) e.command = '请输入启动命令'
    } else {
      if (!form.url.trim()) e.url = '请输入 URL'
      else if (!/^https?:\/\//i.test(form.url.trim())) e.url = 'URL 需以 http(s):// 开头'
    }
    if (form.auth_type === 'bearer' && !form.auth_token.trim()) e.auth_token = '请输入 Token'
    if (form.auth_type === 'basic' && !form.auth_username.trim()) e.auth_username = '请输入用户名'
    if (form.auth_type === 'api_key' && !form.auth_key.trim()) e.auth_key = '请输入 API Key'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    // 认证配置：编辑时凭证留空 = 保持不变；auth_type 为 none = 清空
    let authConfig
    if (form.auth_type === 'none') {
      authConfig = {}
    } else if (form.auth_type === 'bearer') {
      authConfig = { token: form.auth_token.trim() }
    } else if (form.auth_type === 'basic') {
      authConfig = { username: form.auth_username.trim(), password: form.auth_password }
    } else {
      authConfig = {
        header_name: form.auth_header.trim() || 'X-API-Key',
        key: form.auth_key.trim(),
      }
    }
    // env 多行 key=value 解析
    const env = {}
    ;(form.env || '').split('\n').forEach((line) => {
      const i = line.indexOf('=')
      if (i > 0) env[line.slice(0, i).trim()] = line.slice(i + 1).trim()
    })
    const payload = {
      name: form.name.trim(),
      transport_type: form.transport_type,
      command: form.transport_type === 'stdio' ? form.command.trim() : '',
      args: form.transport_type === 'stdio' ? parseArgs(form.args) : [],
      url: form.transport_type === 'stdio' ? '' : form.url.trim(),
      auth_type: form.auth_type,
      auth_config: authConfig,
      env,
    }
    onSubmit(payload)
  }

  const inputCls = (err) =>
    `w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${
      err
        ? 'border-red-300 focus:ring-red-500/20'
        : 'border-gray-200 focus:ring-orange-500/20 focus:border-orange-500'
    }`

  const maskedPlaceholder = (val) => (editing && val ? `${val}（留空不修改）` : '')

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑 MCP 服务器' : '新建 MCP 服务器'}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" onClick={handleSubmit} loading={loading}>
            {editing ? '保存' : '创建'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：文件系统 MCP"
            className={inputCls(errors.name)}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">传输类型</label>
          <select
            value={form.transport_type}
            onChange={(e) => setField('transport_type', e.target.value)}
            className={inputCls(false)}
          >
            {TRANSPORTS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {form.transport_type === 'stdio' ? (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                启动命令 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.command}
                onChange={(e) => setField('command', e.target.value)}
                placeholder="例如：npx"
                className={inputCls(errors.command)}
              />
              {errors.command && <p className="text-xs text-red-500 mt-1">{errors.command}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                参数（空格分隔）
              </label>
              <input
                type="text"
                value={form.args}
                onChange={(e) => setField('args', e.target.value)}
                placeholder="例如：-y @modelcontextprotocol/server-filesystem /path/to/files"
                className={inputCls(false)}
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              URL <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.url}
              onChange={(e) => setField('url', e.target.value)}
              placeholder="例如：http://localhost:3001/mcp"
              className={inputCls(errors.url)}
            />
            {errors.url && <p className="text-xs text-red-500 mt-1">{errors.url}</p>}
          </div>
        )}

        {/* 认证设置（authorized 验证） */}
        <div className="border border-gray-200 rounded-xl p-4 space-y-3 bg-orange-50/30">
          <p className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
            <KeyRound className="w-4 h-4 text-orange-500" />
            认证设置
          </p>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">认证方式</label>
            <select
              value={form.auth_type}
              onChange={(e) => setField('auth_type', e.target.value)}
              className={inputCls(false)}
            >
              {AUTH_TYPES.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>

          {form.auth_type === 'bearer' && (
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Bearer Token</label>
              <input
                type="password"
                value={form.auth_token}
                onChange={(e) => setField('auth_token', e.target.value)}
                placeholder={maskedPlaceholder(editing?.auth_config?.token) || 'sk-xxx'}
                className={inputCls(errors.auth_token)}
              />
              {errors.auth_token && (
                <p className="text-xs text-red-500 mt-1">{errors.auth_token}</p>
              )}
            </div>
          )}

          {form.auth_type === 'basic' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">用户名</label>
                <input
                  type="text"
                  value={form.auth_username}
                  onChange={(e) => setField('auth_username', e.target.value)}
                  placeholder="admin"
                  className={inputCls(errors.auth_username)}
                />
                {errors.auth_username && (
                  <p className="text-xs text-red-500 mt-1">{errors.auth_username}</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">密码</label>
                <input
                  type="password"
                  value={form.auth_password}
                  onChange={(e) => setField('auth_password', e.target.value)}
                  placeholder={maskedPlaceholder(editing?.auth_config?.password) || '••••••'}
                  className={inputCls(false)}
                />
              </div>
            </div>
          )}

          {form.auth_type === 'api_key' && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">请求头名称</label>
                <input
                  type="text"
                  value={form.auth_header}
                  onChange={(e) => setField('auth_header', e.target.value)}
                  placeholder="X-API-Key"
                  className={inputCls(false)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">API Key</label>
                <input
                  type="password"
                  value={form.auth_key}
                  onChange={(e) => setField('auth_key', e.target.value)}
                  placeholder={maskedPlaceholder(editing?.auth_config?.key) || 'sk-xxx'}
                  className={inputCls(errors.auth_key)}
                />
                {errors.auth_key && <p className="text-xs text-red-500 mt-1">{errors.auth_key}</p>}
              </div>
            </>
          )}

          <p className="text-xs text-gray-400">
            {form.auth_type === 'none'
              ? '连接时不会携带任何认证信息'
              : '调用 / 测试该 MCP 服务时会自动注入对应认证头'}
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            环境变量（每行 KEY=value）
          </label>
          <textarea
            value={form.env}
            onChange={(e) => setField('env', e.target.value)}
            rows={3}
            placeholder="API_KEY=sk-xxx&#10;REGION=cn"
            className={`${inputCls(false)} font-mono text-xs`}
          />
        </div>
      </div>
    </Modal>
  )
}

export default function MCPServersPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [transportFilter, setTransportFilter] = useState('all')
  const [viewMode, setViewMode] = useState('grid')
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [testingId, setTestingId] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/mcp-servers')
      setItems(res.data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const filteredItems = items.filter((item) => {
    const q = searchTerm.toLowerCase()
    const matchSearch =
      !q ||
      item.name?.toLowerCase().includes(q) ||
      item.command?.toLowerCase().includes(q) ||
      item.url?.toLowerCase().includes(q)
    const t = item.transport || item.transport_type || 'stdio'
    const matchFilter = transportFilter === 'all' || t === transportFilter
    return matchSearch && matchFilter
  })

  const openCreate = () => {
    setEditingItem(null)
    setShowForm(true)
  }
  const openEdit = (item) => {
    setEditingItem(item)
    setShowForm(true)
  }

  const handleSave = async (payload) => {
    setSaving(true)
    try {
      if (editingItem) {
        await api.put(`/api/mcp-servers/${editingItem.id}`, payload)
        toast.success(`MCP 服务器「${payload.name}」已更新`)
      } else {
        await api.post('/api/mcp-servers', payload)
        toast.success(`MCP 服务器「${payload.name}」已创建`)
      }
      setShowForm(false)
      setEditingItem(null)
      loadData()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (server) => {
    setTestingId(server.id)
    try {
      const res = await api.post(`/api/mcp-servers/${server.id}/test`)
      const d = res.data
      if (d.ok) {
        toast.success(
          d.tools?.length
            ? `${d.detail}，工具：${d.tools.slice(0, 5).join('、')}`
            : d.detail || '连接正常'
        )
      } else {
        toast.error(d.error || '连接失败')
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '测试失败')
    } finally {
      setTestingId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return false
    try {
      await api.delete(`/api/mcp-servers/${deleteTarget.id}`)
      toast.success(`MCP 服务器「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      loadData()
      return true
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
      return false
    }
  }

  const [togglingId, setTogglingId] = useState(null)

  const handleToggle = async (server) => {
    setTogglingId(server.id)
    try {
      const res = await api.post(`/api/mcp-servers/${server.id}/toggle`)
      const enabled = res.data?.enabled
      toast.success(`「${server.name}」已${enabled ? '启动' : '停止'}`)
      loadData()
    } catch (e) {
      toast.error(`操作失败：${e.message}`)
    } finally {
      setTogglingId(null)
    }
  }

  const stats = [
    { label: '总服务器', value: items.length, icon: Server, color: 'from-orange-500 to-red-600' },
    {
      label: '已连接',
      value: items.filter((s) => s.status === 'active').length,
      icon: Wifi,
      color: 'from-emerald-500 to-green-600',
    },
    {
      label: 'stdio 类型',
      value: items.filter((s) => (s.transport || s.transport_type) === 'stdio').length,
      icon: Terminal,
      color: 'from-blue-500 to-cyan-600',
    },
    {
      label: 'SSE 类型',
      value: items.filter((s) => (s.transport || s.transport_type) === 'sse').length,
      icon: Globe,
      color: 'from-purple-500 to-pink-600',
    },
    {
      label: '已启用认证',
      value: items.filter((s) => (s.auth_type || 'none') !== 'none').length,
      icon: KeyRound,
      color: 'from-orange-500 to-amber-600',
    },
    {
      label: 'HTTP 类型',
      value: items.filter((s) => (s.transport || s.transport_type) === 'http').length,
      icon: Globe,
      color: 'from-rose-500 to-red-600',
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="MCP Servers"
        description="管理 Model Context Protocol 服务器，为 Agent 提供外部工具接入能力"
        icon={Server}
        iconColor="from-orange-500 to-red-600"
        actions={
          <Button variant="primary" icon={Plus} onClick={openCreate}>
            新建 MCP
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div
                className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center flex-shrink-0`}
              >
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索 MCP 名称、命令或 URL…"
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition-all"
          />
        </div>
        <div className="flex items-center gap-2">
          <select
            value={transportFilter}
            onChange={(e) => setTransportFilter(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition-all text-sm"
          >
            <option value="all">全部类型</option>
            <option value="stdio">stdio</option>
            <option value="sse">SSE</option>
            <option value="http">HTTP</option>
          </select>
          <Button variant="ghost" size="md" icon={RefreshCw} onClick={loadData} title="刷新">
            刷新
          </Button>
          <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-orange-600' : 'text-gray-500 hover:text-gray-700'}`}
              title="网格视图"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-orange-600' : 'text-gray-500 hover:text-gray-700'}`}
              title="列表视图"
            >
              <ListIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={loadData} />
      ) : filteredItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Server}
            title={
              searchTerm || transportFilter !== 'all'
                ? '未找到匹配的 MCP 服务器'
                : '暂无 MCP 服务器'
            }
            description={
              searchTerm || transportFilter !== 'all'
                ? '尝试调整搜索或筛选条件'
                : '点击「新建 MCP」创建你的第一个 MCP 服务器'
            }
            actionLabel={searchTerm || transportFilter !== 'all' ? undefined : '新建 MCP'}
            onAction={searchTerm || transportFilter !== 'all' ? undefined : openCreate}
          />
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((item) => (
            <MCPServerCard
              key={item.id}
              server={item}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onToggle={handleToggle}
              onTest={handleTest}
              testing={testingId}
              toggling={togglingId}
              viewMode="grid"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredItems.map((item) => (
            <MCPServerCard
              key={item.id}
              server={item}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onToggle={handleToggle}
              onTest={handleTest}
              testing={testingId}
              toggling={togglingId}
              viewMode="list"
            />
          ))}
        </div>
      )}

      <MCPFormModal
        open={showForm}
        onClose={() => {
          setShowForm(false)
          setEditingItem(null)
        }}
        onSubmit={handleSave}
        editing={editingItem}
        loading={saving}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除 MCP 服务器"
        message={
          <>
            确定要删除 MCP 服务器「
            <span className="font-medium text-gray-700">{deleteTarget?.name}</span>
            」吗？此操作不可撤销。
          </>
        }
        confirmLabel="确认删除"
      />
    </div>
  )
}
