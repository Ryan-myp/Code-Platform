import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Database,
  Plus,
  Edit2,
  Trash2,
  Search,
  FolderOpen,
  Link2,
  Hash,
  RefreshCw,
  FileText,
  Globe,
  File,
  Clock,
  BarChart3,
  BookOpen,
  Shield,
  HelpCircle,
  TrendingUp,
  Cable,
  Loader2,
  Server,
  CheckCircle2,
  XCircle,
  UploadCloud,
  FolderSearch,
  FileX2,
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

const KB_TYPES = [
  { value: 'file', label: '本地文件', icon: FolderOpen, color: 'from-violet-500 to-purple-600' },
  { value: 'url', label: 'URL', icon: Link2, color: 'from-blue-500 to-cyan-600' },
  { value: 'db', label: '数据库', icon: Server, color: 'from-amber-500 to-orange-600' },
]

const typeMeta = (type) => KB_TYPES.find((t) => t.value === type) || KB_TYPES[0]

// 文档子类型
const DOC_SUBTYPES = [
  { value: 'general', label: '通用', icon: File, color: 'bg-gray-100 text-gray-600' },
  { value: 'pdf', label: 'PDF', icon: FileText, color: 'bg-red-50 text-red-600' },
  { value: 'word', label: 'Word', icon: FileText, color: 'bg-blue-50 text-blue-600' },
  { value: 'txt', label: 'TXT', icon: File, color: 'bg-gray-50 text-gray-600' },
  { value: 'web', label: '网页', icon: Globe, color: 'bg-emerald-50 text-emerald-600' },
  { value: 'db', label: '数据库', icon: Database, color: 'bg-amber-50 text-amber-600' },
]

const getSubtypeMeta = (subtype) => DOC_SUBTYPES.find((d) => d.value === subtype) || DOC_SUBTYPES[0]

// 知识库快速模板
const KB_TEMPLATES = [
  {
    name: '产品文档库',
    description: '产品需求文档、PRD、用户手册等产品相关资料',
    icon: BookOpen,
    color: 'from-blue-500 to-indigo-600',
    defaults: {
      name: '产品文档库',
      type: 'file',
      path: '',
      description: '产品需求文档、PRD、用户手册等产品相关资料',
      subtype: 'general',
    },
  },
  {
    name: '技术规范库',
    description: 'API文档、架构设计、编码规范等技术文档',
    icon: Shield,
    color: 'from-emerald-500 to-green-600',
    defaults: {
      name: '技术规范库',
      type: 'file',
      path: '',
      description: 'API文档、架构设计、编码规范等技术文档',
      subtype: 'general',
    },
  },
  {
    name: 'FAQ 知识库',
    description: '常见问题解答、客户FAQ、技术支持问答',
    icon: HelpCircle,
    color: 'from-amber-500 to-orange-600',
    defaults: {
      name: 'FAQ 知识库',
      type: 'file',
      path: '',
      description: '常见问题解答、客户FAQ、技术支持问答集合',
      subtype: 'general',
    },
  },
  {
    name: '行业报告库',
    description: '行业分析报告、市场研究、竞品分析等',
    icon: TrendingUp,
    color: 'from-violet-500 to-purple-600',
    defaults: {
      name: '行业报告库',
      type: 'file',
      path: '',
      description: '行业分析报告、市场研究、竞品分析等研究资料',
      subtype: 'pdf',
    },
  },
]

// 根据路径/URL推测文档子类型
function guessSubtype(kb) {
  if (kb.type === 'url') return 'web'
  const path = (kb.path || '').toLowerCase()
  if (path.endsWith('.pdf')) return 'pdf'
  if (path.endsWith('.doc') || path.endsWith('.docx')) return 'word'
  if (path.endsWith('.txt') || path.endsWith('.md')) return 'txt'
  if (path.includes('database') || path.includes('db')) return 'db'
  return 'general'
}

// 知识库卡片
function KBCard({ kb, onEdit, onDelete, onTest, onSearch, onDocs, testing }) {
  const meta = typeMeta(kb.type)
  const Icon = meta.icon
  const subtype = kb.subtype || guessSubtype(kb)
  const subMeta = getSubtypeMeta(subtype)
  const docCount = kb.doc_count || 0
  const totalSize = kb.total_size ? formatFileSize(kb.total_size) : null
  const cfg = kb.config || {}
  // db 类型连接信息摘要
  const dbInfo =
    kb.type !== 'db'
      ? null
      : cfg.engine === 'sqlite'
        ? cfg.database || '-'
        : `${cfg.host || 'localhost'}:${cfg.port || ''}/${cfg.database || ''}`

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 flex flex-col">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`w-12 h-12 rounded-xl bg-gradient-to-br ${meta.color} flex items-center justify-center text-white flex-shrink-0 shadow-lg`}
          >
            <Icon className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{kb.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${subMeta.color}`}>
                {subMeta.label}
              </span>
              <span className="text-xs text-gray-400">{meta.label}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-1.5 mb-4 flex-1">
        {kb.type === 'url' ? (
          <p className="text-sm text-gray-600 flex items-center gap-2 min-w-0">
            <Link2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="truncate font-mono text-xs">{kb.url || '-'}</span>
          </p>
        ) : kb.type === 'db' ? (
          <>
            <p className="text-sm text-gray-600 flex items-center gap-2 min-w-0">
              <Database className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="truncate font-mono text-xs">
                {cfg.engine || 'sqlite'} · {dbInfo}
              </span>
            </p>
            {cfg.table && (
              <p className="text-sm text-gray-600 flex items-center gap-2 min-w-0 pl-6">
                <Hash className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <span className="truncate font-mono text-xs">表：{cfg.table}</span>
              </p>
            )}
          </>
        ) : (
          <p className="text-sm text-gray-600 flex items-center gap-2 min-w-0">
            <FolderOpen className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="truncate font-mono text-xs">{kb.path || '-'}</span>
          </p>
        )}
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Hash className="w-3.5 h-3.5" />
            top_k: <span className="font-medium text-gray-700">{kb.top_k ?? 5}</span>
          </span>
          {docCount > 0 && (
            <span className="flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" />
              {docCount} 文档
            </span>
          )}
          {totalSize && (
            <span className="flex items-center gap-1">
              <BarChart3 className="w-3.5 h-3.5" />
              {totalSize}
            </span>
          )}
        </div>
      </div>

      {/* 描述 */}
      {kb.description && (
        <p className="text-xs text-gray-500 line-clamp-2 mb-3">{kb.description}</p>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <span className="text-xs text-gray-400 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {formatRelativeTime(kb.created_at)}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onTest?.(kb)}
            className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
            title="测试连接"
            disabled={testing}
          >
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Cable className="w-4 h-4" />}
          </button>
          <button
            onClick={() => onSearch?.(kb)}
            className="p-2 hover:bg-emerald-50 text-gray-400 hover:text-emerald-600 rounded-lg transition-colors"
            title="检索知识库"
          >
            <Search className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDocs?.(kb)}
            className="p-2 hover:bg-amber-50 text-gray-400 hover:text-amber-600 rounded-lg transition-colors"
            title="文档管理"
          >
            <FolderSearch className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(kb)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(kb)}
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

// 格式化文件大小
function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

// 创建/编辑表单
function KBFormModal({ open, onClose, onSubmit, editing, defaults, loading }) {
  const toast = useToast()
  const [form, setForm] = useState({
    name: '',
    type: 'file',
    path: '',
    url: '',
    top_k: 5,
    description: '',
    subtype: 'general',
    engine: 'sqlite',
    db_path: '',
    db_name: '',
    host: 'localhost',
    port: '3306',
    user: '',
    password: '',
    table: '',
  })
  const [errors, setErrors] = useState({})
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post('/api/knowledge-bases/upload', fd)
      const d = res.data
      setField('path', d.path)
      setField('subtype', 'general')
      toast.success(d.detail || '上传成功，路径已自动填充')
      // 上传后自动测试
      setTestResult(null)
      setTesting(true)
      try {
        const t = await api.post('/api/knowledge-bases/test-connection', {
          type: 'file',
          path: d.path,
          config: {},
        })
        setTestResult(t.data)
      } catch (err2) {
        setTestResult({
          ok: false,
          error: err2.response?.data?.detail || err2.message || '测试失败',
        })
      } finally {
        setTesting(false)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '上传失败')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  useEffect(() => {
    if (!open) return
    const cfg = editing?.config || {}
    const base = {
      name: editing?.name || defaults?.name || '',
      type: editing?.type || defaults?.type || 'file',
      path: editing?.path || defaults?.path || '',
      url: editing?.url || defaults?.url || '',
      top_k: editing?.top_k ?? 5,
      description: editing?.description || defaults?.description || '',
      subtype: editing?.subtype || defaults?.subtype || 'general',
      engine: cfg.engine || 'sqlite',
      db_path: cfg.database || '',
      db_name: cfg.database || '',
      host: cfg.host || 'localhost',
      port: cfg.port || (cfg.engine === 'postgres' ? '5432' : '3306'),
      user: cfg.user || '',
      password: '', // 脱敏值不回填，留空 = 不修改
      table: cfg.table || '',
    }
    setForm(base)
    setErrors({})
    setTestResult(null)
  }, [open, editing, defaults])

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  const buildConfig = () => {
    const config = { engine: form.engine }
    if (form.engine === 'sqlite') {
      config.database = form.db_path.trim()
    } else {
      config.host = form.host.trim() || 'localhost'
      config.port = form.port.trim()
      config.user = form.user.trim()
      if (form.password) config.password = form.password
      config.database = form.db_name?.trim() || ''
    }
    if (form.table.trim()) config.table = form.table.trim()
    return config
  }

  const handleTestConnection = async () => {
    if (form.type === 'file' && !form.path.trim()) {
      toast.error('请先填写文件路径')
      return
    }
    if (form.type === 'url' && !form.url.trim()) {
      toast.error('请先填写 URL')
      return
    }
    if (form.type === 'db' && form.engine === 'sqlite' && !form.db_path.trim()) {
      toast.error('请先填写数据库文件路径')
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.post('/api/knowledge-bases/test-connection', {
        type: form.type,
        path: form.path.trim(),
        url: form.url.trim(),
        config: form.type === 'db' ? buildConfig() : {},
      })
      setTestResult(res.data)
    } catch (e) {
      setTestResult({ ok: false, error: e.response?.data?.detail || e.message || '测试失败' })
    } finally {
      setTesting(false)
    }
  }

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入知识库名称'
    if (form.name.length > 80) e.name = '名称不能超过 80 个字符'
    if (form.type === 'file' && !form.path.trim()) e.path = '请输入文件路径'
    if (form.type === 'url') {
      if (!form.url.trim()) e.url = '请输入 URL'
      else if (!/^https?:\/\//i.test(form.url.trim())) e.url = 'URL 需以 http(s):// 开头'
    }
    if (form.type === 'db') {
      if (form.engine === 'sqlite') {
        if (!form.db_path.trim()) e.db_path = '请输入数据库文件路径'
      } else {
        if (!form.db_name?.trim()) e.db_name = '请输入数据库名'
      }
    }
    if (form.top_k !== '' && form.top_k != null) {
      const n = Number(form.top_k)
      if (isNaN(n) || n < 1 || n > 100) e.top_k = 'top_k 需为 1-100 之间的整数'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    const payload = {
      name: form.name.trim(),
      type: form.type,
      path: form.type === 'file' ? form.path.trim() : '',
      url: form.type === 'url' ? form.url.trim() : '',
      top_k: Number(form.top_k) || 5,
      description: form.description?.trim() || '',
      subtype: form.subtype || 'general',
      config: form.type === 'db' ? buildConfig() : {},
    }
    onSubmit(payload)
  }

  const inputCls = (err) =>
    `w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${
      err
        ? 'border-red-300 focus:ring-red-500/20'
        : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'
    }`

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑知识库' : '新建知识库'}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={loading}>
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
            placeholder="例如：技术文档库"
            className={inputCls(errors.name)}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            placeholder="简要说明知识库的内容和用途"
            className={inputCls(false)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">文档类型</label>
          <div className="grid grid-cols-3 gap-2">
            {DOC_SUBTYPES.map((st) => (
              <button
                key={st.value}
                type="button"
                onClick={() => setField('subtype', st.value)}
                className={`px-3 py-2 rounded-xl text-sm font-medium border transition-all flex items-center justify-center gap-1.5 ${
                  form.subtype === st.value
                    ? 'border-purple-500 bg-purple-50 text-purple-700 shadow-sm'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <st.icon className="w-3.5 h-3.5" />
                {st.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">来源类型</label>
          <select
            value={form.type}
            onChange={(e) => setField('type', e.target.value)}
            className={inputCls(false)}
          >
            {KB_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {form.type === 'file' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              文档来源 <span className="text-red-500">*</span>
            </label>
            {/* 上传入口：小白首选 */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="w-full p-4 rounded-xl border-2 border-dashed border-violet-200 bg-violet-50/40 hover:border-violet-400 hover:bg-violet-50 transition-all flex flex-col items-center gap-1.5 disabled:opacity-60"
            >
              {uploading ? (
                <Loader2 className="w-6 h-6 text-violet-500 animate-spin" />
              ) : (
                <UploadCloud className="w-6 h-6 text-violet-500" />
              )}
              <span className="text-sm font-medium text-violet-700">
                {uploading ? '上传中…' : '点击上传文档（txt / md / pdf / docx 等）'}
              </span>
              <span className="text-xs text-gray-400">单个文件不超过 20MB，上传后自动填充路径</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleUpload}
              accept=".txt,.md,.csv,.log,.json,.yaml,.yml,.html,.htm,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx"
            />
            <div className="flex items-center gap-2 my-2">
              <div className="flex-1 h-px bg-gray-200" />
              <span className="text-xs text-gray-400">或输入服务器本地路径</span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>
            <input
              type="text"
              value={form.path}
              onChange={(e) => setField('path', e.target.value)}
              placeholder="/path/to/documents"
              className={inputCls(errors.path)}
            />
            <p className="text-xs text-gray-400 mt-1">
              本地目录或文件的绝对路径，Agent 将扫描其中的文本文件
            </p>
            {errors.path && <p className="text-xs text-red-500 mt-1">{errors.path}</p>}
          </div>
        )}

        {form.type === 'url' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              URL <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.url}
              onChange={(e) => setField('url', e.target.value)}
              placeholder="https://example.com/docs"
              className={inputCls(errors.url)}
            />
            {errors.url && <p className="text-xs text-red-500 mt-1">{errors.url}</p>}
          </div>
        )}

        {form.type === 'db' && (
          <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50/40 p-4">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-amber-600" />
              <span className="text-sm font-medium text-gray-700">数据库连接设置</span>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">数据库引擎</label>
              <select
                value={form.engine}
                onChange={(e) => setField('engine', e.target.value)}
                className={inputCls(false)}
              >
                <option value="sqlite">SQLite（本地文件）</option>
                <option value="mysql">MySQL</option>
                <option value="postgres">PostgreSQL</option>
              </select>
              <p className="text-xs text-gray-400 mt-1">
                MySQL / PostgreSQL 需后端环境安装 pymysql / psycopg2，未安装时测试连接会给出提示
              </p>
            </div>

            {form.engine === 'sqlite' ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  数据库文件路径 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.db_path}
                  onChange={(e) => setField('db_path', e.target.value)}
                  placeholder="/path/to/data.db"
                  className={inputCls(errors.db_path)}
                />
                {errors.db_path && <p className="text-xs text-red-500 mt-1">{errors.db_path}</p>}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">主机</label>
                  <input
                    type="text"
                    value={form.host}
                    onChange={(e) => setField('host', e.target.value)}
                    placeholder="localhost"
                    className={inputCls(false)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">端口</label>
                  <input
                    type="text"
                    value={form.port}
                    onChange={(e) => setField('port', e.target.value)}
                    placeholder={form.engine === 'postgres' ? '5432' : '3306'}
                    className={inputCls(false)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">用户名</label>
                  <input
                    type="text"
                    value={form.user}
                    onChange={(e) => setField('user', e.target.value)}
                    placeholder="root"
                    className={inputCls(false)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={(e) => setField('password', e.target.value)}
                    placeholder={editing ? '留空不修改' : ''}
                    className={inputCls(false)}
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    数据库名 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.db_name}
                    onChange={(e) => setField('db_name', e.target.value)}
                    placeholder="my_database"
                    className={inputCls(errors.db_name)}
                  />
                  {errors.db_name && <p className="text-xs text-red-500 mt-1">{errors.db_name}</p>}
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                表名 <span className="text-gray-400 font-normal">（可选，默认检索第一张表）</span>
              </label>
              <input
                type="text"
                value={form.table}
                onChange={(e) => setField('table', e.target.value)}
                placeholder="users / products"
                className={inputCls(false)}
              />
              <p className="text-xs text-gray-400 mt-1">
                连接测试成功后会自动列出可用的表，可直接复制表名
              </p>
            </div>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            top_k（检索召回数量）
          </label>
          <input
            type="number"
            min={1}
            max={100}
            value={form.top_k}
            onChange={(e) => setField('top_k', e.target.value)}
            className={inputCls(errors.top_k)}
          />
          {errors.top_k && <p className="text-xs text-red-500 mt-1">{errors.top_k}</p>}
        </div>

        {/* 测试连接 */}
        <div className="pt-2 border-t border-gray-100">
          <Button variant="secondary" icon={Cable} onClick={handleTestConnection} loading={testing}>
            测试连接
          </Button>
          {testResult &&
            (testResult.ok ? (
              <div className="mt-3 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-700">
                <p className="flex items-center gap-1.5 font-medium">
                  <CheckCircle2 className="w-4 h-4" />
                  {testResult.detail || '连接成功'}
                </p>
                {testResult.doc_count != null && (
                  <p className="text-xs mt-1 text-emerald-600">文档数：{testResult.doc_count}</p>
                )}
                {testResult.tables?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {testResult.tables.map((t) => (
                      <span
                        key={t}
                        className="px-2 py-0.5 rounded bg-white border border-emerald-200 text-xs font-mono text-emerald-700"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-3 p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600">
                <p className="flex items-center gap-1.5 font-medium">
                  <XCircle className="w-4 h-4" />
                  {testResult.error || '连接失败'}
                </p>
              </div>
            ))}
        </div>
      </div>
    </Modal>
  )
}

// 知识库检索弹窗
function KBSearchModal({ kb, onClose }) {
  const toast = useToast()
  const [q, setQ] = useState('')
  const [limit, setLimit] = useState(5)
  const [hits, setHits] = useState(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(null)

  const doSearch = async () => {
    if (!q.trim()) {
      toast.error('请输入检索关键词')
      return
    }
    setSearching(true)
    setError(null)
    try {
      const res = await api.get(`/api/knowledge-bases/${kb.id}/search`, {
        params: { q: q.trim(), limit },
      })
      setHits(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || '检索失败')
    } finally {
      setSearching(false)
    }
  }

  return (
    <Modal open={!!kb} onClose={onClose} title={`检索「${kb?.name}」`} size="lg">
      <div className="space-y-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()}
            placeholder="输入关键词，回车检索…"
            className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none"
          >
            {[5, 10, 20].map((n) => (
              <option key={n} value={n}>
                前 {n} 条
              </option>
            ))}
          </select>
          <Button variant="primary" icon={Search} onClick={doSearch} loading={searching}>
            检索
          </Button>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600">
            {error}
          </div>
        )}

        {hits &&
          (hits.count === 0 ? (
            <div className="py-8 text-center text-gray-400 text-sm">
              未找到匹配内容，换个关键词试试
            </div>
          ) : (
            <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
              <p className="text-xs text-gray-500">
                共 {hits.count} 条结果{hits.table ? `（表：${hits.table}）` : ''}
              </p>
              {hits.hits.map((hit, idx) =>
                hit.file ? (
                  <div key={idx} className="p-3 rounded-xl border border-gray-200 bg-gray-50">
                    <p className="text-xs font-medium text-gray-700 mb-1.5">
                      <FileText className="w-3.5 h-3.5 inline mr-1 text-gray-400" />
                      <span className="font-mono">{hit.file}</span>
                      <span className="text-gray-400 ml-1">（{hit.match_count} 处匹配）</span>
                    </p>
                    {hit.matches.map((m, mi) => (
                      <p
                        key={mi}
                        className="text-xs text-gray-600 leading-relaxed border-t border-gray-100 py-1.5 first:border-t-0"
                      >
                        {m}
                      </p>
                    ))}
                  </div>
                ) : (
                  <div key={idx} className="p-3 rounded-xl border border-gray-200 bg-gray-50">
                    {Object.entries(hit).map(([k, v]) => (
                      <p
                        key={k}
                        className="text-xs text-gray-600 leading-relaxed flex gap-2 py-0.5"
                      >
                        <span className="font-mono text-purple-600 flex-shrink-0">{k}</span>
                        <span className="truncate">{v}</span>
                      </p>
                    ))}
                  </div>
                )
              )}
            </div>
          ))}
      </div>
    </Modal>
  )
}

// 知识库文档管理弹窗：查看 / 删除 / 检索
function KBDocsModal({ kb, onClose, onSearch }) {
  const toast = useToast()
  const [docs, setDocs] = useState(null)
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [error, setError] = useState(null)

  const loadDocs = useCallback(async () => {
    if (!kb) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(`/api/knowledge-bases/${kb.id}/documents`)
      setDocs(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [kb])

  useEffect(() => {
    setDocs(null)
    if (kb) loadDocs()
  }, [kb, loadDocs])

  const handleDelete = async (doc) => {
    if (doc.is_table) return
    setDeleting(doc.name)
    try {
      await api.delete(`/api/knowledge-bases/${kb.id}/documents`, {
        params: { filename: doc.name },
      })
      toast.success(`已删除 ${doc.name}`)
      loadDocs()
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '删除失败')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <Modal open={!!kb} onClose={onClose} title={`文档管理 — ${kb?.name || ''}`} size="md">
      <div className="space-y-3">
        {kb?.type === 'file' && (
          <button
            onClick={() => onSearch?.(kb)}
            className="w-full p-3 rounded-xl border-2 border-dashed border-emerald-200 bg-emerald-50/40 hover:border-emerald-400 hover:bg-emerald-50 transition-all flex items-center justify-center gap-2 text-sm text-emerald-700"
          >
            <Search className="w-4 h-4" /> 在知识库中检索内容
          </button>
        )}

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600">
            {error}
          </div>
        )}

        {loading && !docs && (
          <p className="text-sm text-gray-400 text-center py-6">加载文档列表…</p>
        )}

        {!loading && docs && docs.count === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">暂无文档，上传文件后即可在此查看</p>
        )}

        {docs && docs.count > 0 && (
          <>
            <p className="text-xs text-gray-500">
              共 {docs.count} 个文档（{docs.type === 'db' ? '数据库表' : '文件'}）
            </p>
            <div className="max-h-[45vh] overflow-y-auto space-y-1.5 pr-1">
              {docs.docs.map((doc) => (
                <div
                  key={doc.path || doc.name}
                  className="flex items-center gap-3 p-2.5 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
                    {doc.is_table ? (
                      <Database className="w-4 h-4 text-amber-600" />
                    ) : (
                      <FileText className="w-4 h-4 text-amber-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{doc.name}</p>
                    <p className="text-xs text-gray-400">
                      {doc.is_table
                        ? '数据库表'
                        : `${formatFileSize(doc.size)}${doc.mtime ? ' · ' + new Date(doc.mtime).toLocaleString('zh-CN') : ''}`}
                    </p>
                  </div>
                  {!doc.is_table && (
                    <button
                      onClick={() => handleDelete(doc)}
                      disabled={deleting === doc.name}
                      className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors flex-shrink-0 disabled:opacity-50"
                      title="删除文档"
                    >
                      {deleting === doc.name ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <FileX2 className="w-4 h-4" />
                      )}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}

export default function KnowledgeBasesPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [formDefaults, setFormDefaults] = useState(null)
  const [testingId, setTestingId] = useState(null)
  const [searchTarget, setSearchTarget] = useState(null)
  const [docsTarget, setDocsTarget] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/knowledge-bases')
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
      item.path?.toLowerCase().includes(q) ||
      item.url?.toLowerCase().includes(q) ||
      item.description?.toLowerCase().includes(q)
    const matchType = typeFilter === 'all' || item.type === typeFilter
    return matchSearch && matchType
  })

  const openCreate = () => {
    setEditingItem(null)
    setFormDefaults(null)
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
        await api.put(`/api/knowledge-bases/${editingItem.id}`, payload)
        toast.success(`知识库「${payload.name}」已更新`)
      } else {
        await api.post('/api/knowledge-bases', payload)
        toast.success(`知识库「${payload.name}」已创建`)
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

  const handleDelete = async () => {
    if (!deleteTarget) return false
    try {
      await api.delete(`/api/knowledge-bases/${deleteTarget.id}`)
      toast.success(`知识库「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      loadData()
      return true
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
      return false
    }
  }

  const handleTestKb = async (kb) => {
    setTestingId(kb.id)
    try {
      const res = await api.post(`/api/knowledge-bases/${kb.id}/test`)
      const d = res.data
      if (d.ok) toast.success(d.detail || '连接成功')
      else toast.error(d.error || '连接失败')
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '测试失败')
    } finally {
      setTestingId(null)
    }
  }

  const totalDocs = items.reduce((sum, i) => sum + (i.doc_count || 0), 0)

  const stats = [
    {
      label: '总知识库',
      value: items.length,
      icon: Database,
      color: 'from-violet-500 to-purple-600',
    },
    {
      label: '本地文件',
      value: items.filter((i) => (i.type || 'file') === 'file').length,
      icon: FolderOpen,
      color: 'from-emerald-500 to-green-600',
    },
    {
      label: 'URL 类型',
      value: items.filter((i) => i.type === 'url').length,
      icon: Globe,
      color: 'from-blue-500 to-cyan-600',
    },
    {
      label: '数据库',
      value: items.filter((i) => i.type === 'db').length,
      icon: Server,
      color: 'from-amber-500 to-orange-600',
    },
    { label: '总文档数', value: totalDocs, icon: FileText, color: 'from-rose-500 to-pink-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="知识库管理"
        description="管理文档知识库，为 Agent 提供知识检索能力"
        icon={Database}
        iconColor="from-violet-500 to-purple-600"
        actions={
          <Button variant="primary" icon={Plus} onClick={openCreate}>
            新建知识库
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

      {/* 快速模板（仅在知识库为空时显示） */}
      {items.length === 0 && !loading && !error && (
        <div className="bg-gradient-to-r from-violet-50 to-purple-50 rounded-2xl border border-violet-200/50 p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <Database className="w-4 h-4 text-violet-500" />
            从模板快速创建
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {KB_TEMPLATES.map((tpl) => (
              <button
                key={tpl.name}
                onClick={() => {
                  setFormDefaults(tpl.defaults)
                  setShowForm(true)
                }}
                className="bg-white rounded-xl p-4 border border-gray-200 hover:border-violet-300 hover:shadow-md transition-all text-left group"
              >
                <div
                  className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tpl.color} flex items-center justify-center text-white mb-3`}
                >
                  <tpl.icon className="w-4.5 h-4.5" />
                </div>
                <h4 className="text-sm font-semibold text-gray-800 mb-1">{tpl.name}</h4>
                <p className="text-xs text-gray-500 line-clamp-2">{tpl.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索知识库名称、路径或 URL…"
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div className="flex items-center gap-2">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all text-sm"
          >
            <option value="all">全部类型</option>
            {KB_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <Button variant="ghost" size="md" icon={RefreshCw} onClick={loadData} title="刷新">
            刷新
          </Button>
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
            icon={Database}
            title={searchTerm || typeFilter !== 'all' ? '未找到匹配的知识库' : '暂无知识库'}
            description={
              searchTerm || typeFilter !== 'all'
                ? '尝试调整搜索或筛选条件'
                : '点击「新建知识库」创建你的第一个知识库'
            }
            actionLabel={searchTerm || typeFilter !== 'all' ? undefined : '新建知识库'}
            onAction={searchTerm || typeFilter !== 'all' ? undefined : openCreate}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((kb) => (
            <KBCard
              key={kb.id}
              kb={kb}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onTest={handleTestKb}
              onSearch={setSearchTarget}
              onDocs={setDocsTarget}
              testing={testingId === kb.id}
            />
          ))}
        </div>
      )}

      <KBFormModal
        open={showForm}
        onClose={() => {
          setShowForm(false)
          setEditingItem(null)
          setFormDefaults(null)
        }}
        onSubmit={handleSave}
        editing={editingItem}
        defaults={formDefaults}
        loading={saving}
      />

      <KBSearchModal kb={searchTarget} onClose={() => setSearchTarget(null)} />

      <KBDocsModal kb={docsTarget} onClose={() => setDocsTarget(null)} onSearch={setSearchTarget} />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除知识库"
        message={
          <>
            确定要删除知识库「
            <span className="font-medium text-gray-700">{deleteTarget?.name}</span>
            」吗？此操作不可撤销。
          </>
        }
        confirmLabel="确认删除"
      />
    </div>
  )
}
