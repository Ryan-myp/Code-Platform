import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Plus,
  Play,
  Square,
  Trash2,
  RefreshCw,
  FolderOpen,
  Server,
  Container,
  Search,
  Terminal,
  LayoutGrid,
  List as ListIcon,
  Activity,
  Zap,
  Clock,
  Loader2,
  ExternalLink,
  Database,
  KeyRound,
  Table2,
  PlayCircle,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import MarkdownRenderer from '../components/MarkdownRenderer'
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

// 沙箱状态自定义映射
const SANDBOX_STATUS_MAP = {
  created: { text: '已创建', cls: 'bg-blue-100 text-blue-700' },
  exited: { text: '已退出', cls: 'bg-gray-100 text-gray-600' },
}

// 解析端口字段（后端存储为 JSON 字符串或数组）
function formatPorts(ports) {
  if (!ports) return '-'
  if (Array.isArray(ports)) return ports.length ? ports.join(', ') : '-'
  try {
    const parsed = JSON.parse(ports)
    return Array.isArray(parsed) ? (parsed.length ? parsed.join(', ') : '-') : String(ports)
  } catch {
    return String(ports)
  }
}

// 取第一个可访问端口（运行中的服务可直接打开）
function firstPort(ports) {
  if (!ports) return null
  let arr = ports
  if (!Array.isArray(arr)) {
    try {
      arr = JSON.parse(ports)
    } catch {
      return null
    }
  }
  if (!Array.isArray(arr) || !arr.length) return null
  const p = String(arr[0]).split(':').pop()
  return /^\d+$/.test(p) ? Number(p) : null
}

// 运行中的服务访问链接按钮
function AccessLink({ project }) {
  const port = project.status === 'running' ? firstPort(project.ports) : null
  if (!port) return null
  return (
    <a
      href={`http://localhost:${port}`}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg text-xs font-medium transition-colors border border-emerald-200"
      title={`打开 http://localhost:${port}`}
    >
      <ExternalLink className="w-3.5 h-3.5" />
      访问
    </a>
  )
}

// 容器日志弹窗：轮询沙箱日志接口（运行中每 3s 刷新）；支持 AI 分析定位问题
function LogModal({ project, onClose }) {
  const toast = useToast()
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const logsEndRef = useRef(null)

  useEffect(() => {
    if (!project) return
    setAnalysis(null)
    let alive = true
    let timer = null
    const fetchLogs = async () => {
      try {
        const res = await api.get(`/api/sandbox/projects/${project.id}/logs?tail=300`)
        if (!alive) return
        setLogs(res.data.logs || [])
        setMessage(res.data.message || '')
        // 非运行中停止轮询
        if (project.status !== 'running') clearInterval(timer)
      } catch (e) {
        if (alive) {
          setMessage(`日志加载失败：${e.message}`)
          clearInterval(timer)
        }
      } finally {
        if (alive) setLoading(false)
      }
    }
    fetchLogs()
    timer = setInterval(fetchLogs, 3000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [project])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs, loading])

  // AI 分析日志定位问题根因
  const handleAnalyze = async () => {
    setAnalyzing(true)
    setAnalysis(null)
    try {
      const res = await api.post(`/api/sandbox/projects/${project.id}/logs/analyze`)
      setAnalysis(res.data.analysis || '（无分析结果）')
    } catch (e) {
      toast.error(`分析失败：${e.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <Modal open={!!project} onClose={onClose} title={`容器日志 - ${project?.name || ''}`} size="lg">
      {message && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-700">
          {message}
        </div>
      )}
      <div className="mb-3 flex items-center gap-2">
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white text-xs font-medium rounded-lg hover:opacity-90 transition-all disabled:opacity-60"
        >
          {analyzing ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Search className="w-3.5 h-3.5" />
          )}
          {analyzing ? 'AI 分析中（约 10-60 秒）…' : 'AI 分析日志定位问题'}
        </button>
        {analysis && (
          <span className="text-xs text-gray-400">分析基于最近 {logs.length} 行日志</span>
        )}
      </div>
      {analysis && (
        <div className="mb-3 p-4 rounded-xl bg-indigo-50 border border-indigo-200 text-sm text-gray-800 max-h-[30vh] overflow-y-auto">
          <p className="text-xs font-semibold text-indigo-700 mb-2 flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5" /> AI 诊断报告
          </p>
          <MarkdownRenderer content={analysis} />
        </div>
      )}
      {loading ? (
        <div className="py-12 text-center text-gray-400 text-sm">加载中…</div>
      ) : (
        <pre className="bg-gray-900 text-green-400 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[55vh] whitespace-pre-wrap">
          {logs.length ? logs.join('\n') : '（暂无日志输出）'}
        </pre>
      )}
      <div ref={logsEndRef} />
    </Modal>
  )
}

// 项目卡片
function ProjectCard({ project, onStart, onStop, onDelete, onLogs, onConsole, viewMode }) {
  const isRunning = project.status === 'running'
  const ports = formatPorts(project.ports)
  const consoleType = isRunning ? serviceTypeOf(project.image) : null

  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4 hover:shadow-md transition-shadow">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
            isRunning ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-100 text-gray-500'
          }`}
        >
          <FolderOpen className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{project.name}</h3>
            <Badge status={project.status} customMap={SANDBOX_STATUS_MAP} />
          </div>
          <p className="text-sm text-gray-500 truncate">
            {project.image} · {ports}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <AccessLink project={project} />
          {consoleType && (
            <button
              onClick={() => onConsole(project)}
              className="p-2 hover:bg-indigo-50 text-gray-400 hover:text-indigo-600 rounded-lg transition-colors"
              title={`打开 ${SERVICE_TYPE_LABEL[consoleType]} 控制台`}
            >
              <Database className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => onLogs(project)}
            className="p-2 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded-lg transition-colors"
            title="查看日志"
          >
            <Terminal className="w-4 h-4" />
          </button>
          {isRunning ? (
            <Button variant="danger" size="sm" icon={Square} onClick={() => onStop(project)}>
              停止
            </Button>
          ) : (
            <Button variant="success" size="sm" icon={Play} onClick={() => onStart(project)}>
              启动
            </Button>
          )}
          <button
            onClick={() => onDelete(project)}
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
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
              isRunning ? 'bg-emerald-100 text-emerald-600' : 'bg-gray-100 text-gray-500'
            }`}
          >
            <FolderOpen className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{project.name}</h3>
            <p className="text-xs text-gray-500 truncate">
              {project.image}
              {project.project_dir
                ? ` · ${project.project_dir.split('/').slice(-2).join('/')}`
                : ''}
            </p>
          </div>
        </div>
        <Badge status={project.status} customMap={SANDBOX_STATUS_MAP} />
      </div>

      {project.description && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-3">{project.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
        <span className="flex items-center gap-1" title="端口映射">
          <Zap className="w-3 h-3" />
          {ports}
        </span>
        <span className="flex items-center gap-1" title="创建时间">
          <Clock className="w-3 h-3" />
          {formatRelativeTime(project.created_at)}
        </span>
      </div>

      <div className="flex items-center gap-2 pt-4 border-t border-gray-100 mt-auto">
        <AccessLink project={project} />
        {consoleType && (
          <button
            onClick={() => onConsole(project)}
            className="p-2 hover:bg-indigo-50 text-gray-400 hover:text-indigo-600 rounded-lg transition-colors"
            title={`打开 ${SERVICE_TYPE_LABEL[consoleType]} 控制台`}
          >
            <Database className="w-4 h-4" />
          </button>
        )}
        <button
          onClick={() => onLogs(project)}
          className="p-2 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded-lg transition-colors"
          title="查看日志"
        >
          <Terminal className="w-4 h-4" />
        </button>
        {isRunning ? (
          <Button
            variant="danger"
            size="sm"
            icon={Square}
            onClick={() => onStop(project)}
            className="flex-1"
          >
            停止
          </Button>
        ) : (
          <Button
            variant="success"
            size="sm"
            icon={Play}
            onClick={() => onStart(project)}
            className="flex-1"
          >
            启动
          </Button>
        )}
        <button
          onClick={() => onDelete(project)}
          className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
          title="删除"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

// 服务类型识别：根据镜像判断项目是否支持控制台及类型（6 种预制中间件全覆盖）
function serviceTypeOf(image = '') {
  const img = String(image || '').toLowerCase()
  if (img.includes('redis')) return 'redis'
  if (img.includes('mysql')) return 'mysql'
  if (img.includes('postgres')) return 'postgres'
  if (img.includes('mongo')) return 'mongo'
  if (img.includes('rabbit')) return 'rabbitmq'
  if (img.includes('nginx')) return 'nginx'
  return null
}

const SERVICE_TYPE_LABEL = {
  redis: 'Redis',
  mysql: 'MySQL',
  postgres: 'PostgreSQL',
  mongo: 'MongoDB',
  rabbitmq: 'RabbitMQ',
  nginx: 'Nginx',
}

// 各服务控制台元信息：端点 / 输入占位 / 说明 / 快捷命令 / 渲染模式 / 徽标样式
const CONSOLE_META = {
  redis: {
    endpoint: 'redis/command',
    mode: 'redis',
    badge: 'bg-red-50 text-red-600',
    hint: '在容器内执行 redis-cli 安全命令（查看 / 修改 / 删除 Key）',
    placeholder: '输入 redis-cli 命令，如 KEYS user:*',
    quick: ['KEYS *', 'DBSIZE', 'PING'],
    defaultInput: 'KEYS *',
  },
  mysql: {
    endpoint: 'sql/query',
    mode: 'sql',
    badge: 'bg-blue-50 text-blue-600',
    hint: '在容器内执行只读 SQL（SELECT / SHOW / DESC / EXPLAIN）',
    placeholder: '输入只读 SQL，如 SELECT * FROM users LIMIT 10',
    quick: ['SHOW TABLES;', 'SELECT 1;'],
    defaultInput: 'SHOW TABLES;',
  },
  postgres: {
    endpoint: 'sql/query',
    mode: 'sql',
    badge: 'bg-indigo-50 text-indigo-600',
    hint: '在容器内执行只读 SQL（SELECT / SHOW / DESC / EXPLAIN）',
    placeholder: '输入只读 SQL，如 SELECT * FROM users LIMIT 10',
    quick: ['SELECT version();', 'SELECT 1;'],
    defaultInput: 'SELECT version();',
  },
  mongo: {
    endpoint: 'mongo/command',
    mode: 'raw',
    badge: 'bg-green-50 text-green-600',
    hint: '在容器内执行 mongosh 只读命令（show dbs / use db / db.集合.find()）',
    placeholder: '输入 mongosh 命令，如 show dbs / db.users.find().limit(5)',
    quick: ['show dbs', 'show databases', 'db.stats()'],
    defaultInput: 'show dbs',
  },
  rabbitmq: {
    endpoint: 'rabbitmq/command',
    mode: 'raw',
    badge: 'bg-orange-50 text-orange-600',
    hint: '在容器内执行 rabbitmqctl 只读命令（status / list_* 列表类）',
    placeholder: '输入 rabbitmqctl 命令，如 list_queues name messages',
    quick: ['status', 'list_queues', 'list_exchanges', 'list_users', 'list_connections'],
    defaultInput: 'status',
  },
  nginx: {
    endpoint: 'nginx/command',
    mode: 'raw',
    badge: 'bg-cyan-50 text-cyan-600',
    hint: '在容器内执行 nginx 只读命令（版本 / 配置测试 / 配置转储）',
    placeholder: '输入 nginx 命令，如 nginx -t',
    quick: ['nginx -v', 'nginx -t', 'nginx -T'],
    defaultInput: 'nginx -t',
  },
}

// 服务控制台弹窗：全部预制中间件通用（Redis 命令 / SQL 只读查询 / Mongo & RabbitMQ & Nginx 只读命令）
// 通过容器内客户端执行，无需开放额外端口；所有命令均经后端安全白名单
function ServiceConsoleModal({ project, onClose }) {
  const toast = useToast()
  const type = project ? serviceTypeOf(project.image) : null
  const meta = CONSOLE_META[type] || null
  const [input, setInput] = useState('')
  const [result, setResult] = useState(null) // { ok, output|columns|rows, error }
  const [running, setRunning] = useState(false)
  const [copiedKey, setCopiedKey] = useState('')

  useEffect(() => {
    if (project && meta) {
      setResult(null)
      setInput(meta.defaultInput || '')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project])

  const handleRun = async (rawCmd) => {
    const c = (rawCmd ?? input).trim()
    if (!c) return
    setRunning(true)
    setResult(null)
    try {
      const body = meta.mode === 'sql' ? { sql: c } : { command: c }
      const res = await api.post(`/api/sandbox/projects/${project.id}/${meta.endpoint}`, body)
      setResult(res.data)
    } catch (e) {
      toast.error(e.message)
      setResult({ ok: false, error: e.message })
    } finally {
      setRunning(false)
    }
  }

  // Redis 输出按命令类型智能渲染：KEYS/DBSIZE → key 列表；GET/TTL/TYPE → 单值；其余 → 原始输出
  const renderRedisOutput = () => {
    if (!result) return null
    if (!result.ok) {
      return (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          执行失败：{result.error}
        </div>
      )
    }
    const verb = (result.command || '').split(' ')[0].toUpperCase()
    const lines = (result.output || '').split('\n').filter((l) => l.trim())
    if (verb === 'KEYS' || verb === 'DBSIZE') {
      return lines.length ? (
        <div className="space-y-1.5">
          {verb === 'KEYS' && (
            <p className="text-xs text-gray-400">共 {lines.length} 个 Key，点击可查看值</p>
          )}
          {lines.map((k) => (
            <div
              key={k}
              className="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm"
            >
              <span className="font-mono text-gray-800 truncate">{k}</span>
              <span className="flex items-center gap-1.5 flex-shrink-0">
                {copiedKey === k && <span className="text-[11px] text-emerald-600">已复制</span>}
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(k)
                    setCopiedKey(k)
                    setTimeout(() => setCopiedKey(''), 1500)
                  }}
                  className="px-2 py-1 bg-white border border-gray-200 rounded-md text-xs text-gray-500 hover:text-gray-800 hover:border-gray-300 transition-colors"
                >
                  复制
                </button>
                <button
                  onClick={() => handleRun(`GET ${k}`)}
                  className="px-2.5 py-1 bg-indigo-50 border border-indigo-200 rounded-md text-xs text-indigo-600 hover:bg-indigo-100 transition-colors"
                >
                  GET 查看
                </button>
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400 py-4 text-center">（空，暂无 Key）</p>
      )
    }
    if (verb === 'GET' || verb === 'TTL' || verb === 'TYPE' || verb === 'STRLEN') {
      return (
        <div className="p-4 rounded-xl bg-gray-900 text-emerald-400 font-mono text-sm break-all whitespace-pre-wrap">
          {result.output || '（空值）'}
        </div>
      )
    }
    return (
      <pre className="bg-gray-900 text-green-400 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[40vh] whitespace-pre-wrap">
        {result.output || 'OK'}
      </pre>
    )
  }

  // SQL 结果表格渲染
  const renderSqlResult = () => {
    if (!result) return null
    if (!result.ok) {
      return (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          查询失败：{result.error}
        </div>
      )
    }
    if (!result.columns || !result.columns.length) {
      return (
        <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-sm text-gray-500 text-center">
          （查询完成，无结果集）
        </div>
      )
    }
    return (
      <div className="overflow-auto max-h-[42vh] rounded-xl border border-gray-200">
        <table className="w-full text-xs">
          <thead className="bg-gray-100 sticky top-0">
            <tr>
              {result.columns.map((c) => (
                <th key={c} className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {result.rows.length ? (
              result.rows.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  {r.map((cell, j) => (
                    <td key={j} className="px-3 py-1.5 font-mono text-gray-600 whitespace-nowrap max-w-[320px] truncate" title={cell}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={result.columns.length} className="px-3 py-4 text-center text-gray-400">
                  （0 行）
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    )
  }

  // 原始文本输出（mongo / rabbitmq / nginx）
  const renderRawOutput = () => {
    if (!result) return null
    if (!result.ok) {
      return (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          执行失败：{result.error}
        </div>
      )
    }
    return (
      <pre className="bg-gray-900 text-green-400 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[45vh] whitespace-pre-wrap">
        {result.output || '（无输出）'}
      </pre>
    )
  }

  if (!meta) return null
  const isSql = meta.mode === 'sql'
  const isRedis = meta.mode === 'redis'

  return (
    <Modal open={!!project} onClose={onClose} size="lg" title={`服务控制台 - ${project?.name || ''}`}>
      <div className="mb-4 flex items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${meta.badge}`}
        >
          {isRedis ? <KeyRound className="w-3.5 h-3.5" /> : isSql ? <Table2 className="w-3.5 h-3.5" /> : <Database className="w-3.5 h-3.5" />}
          {SERVICE_TYPE_LABEL[type]}
        </span>
        <span className="text-xs text-gray-400">{meta.hint}</span>
      </div>

      <div className="flex gap-2 mb-3">
        {isSql ? (
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={2}
            placeholder={meta.placeholder}
            className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none font-mono text-sm transition-all resize-none"
          />
        ) : (
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRun()}
            placeholder={meta.placeholder}
            className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none font-mono text-sm transition-all"
          />
        )}
        <Button icon={running ? Loader2 : isSql ? Table2 : Play} loading={running} onClick={() => handleRun()}>
          {isSql ? '查询' : '执行'}
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5 mb-4">
        {meta.quick.map((q) => (
          <button
            key={q}
            onClick={() => handleRun(q.trim())}
            className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg text-xs font-mono text-gray-600 transition-colors"
          >
            {q.trim()}
          </button>
        ))}
      </div>
      {running ? (
        <div className="py-10 text-center text-gray-400 text-sm">{isSql ? '查询中…' : '执行中…'}</div>
      ) : isRedis ? (
        renderRedisOutput()
      ) : isSql ? (
        renderSqlResult()
      ) : (
        renderRawOutput()
      )}
    </Modal>
  )
}

// 项目表单模态框（创建用，预留 editing 以支持后续编辑）
function ProjectFormModal({ open, onClose, onSubmit, editing, loading }) {
  const [form, setForm] = useState({ name: '', description: '', image: '', ports: '', env: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      setForm(
        editing
          ? {
              name: editing.name || '',
              description: editing.description || '',
              image: editing.image || '',
              ports: editing.ports || '',
              env: editing.env || '',
            }
          : { name: '', description: '', image: '', ports: '', env: '' }
      )
      setErrors({})
    }
  }, [open, editing])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入项目名称'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim() })
  }

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑项目' : '新建项目'}
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
            placeholder="例如：我的项目"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <textarea
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            rows={2}
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">镜像</label>
          <input
            type="text"
            value={form.image}
            onChange={(e) => setField('image', e.target.value)}
            placeholder="例如: python:3.11"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">端口映射</label>
          <input
            type="text"
            value={form.ports}
            onChange={(e) => setField('ports', e.target.value)}
            placeholder="例如: 8000:8000"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">环境变量</label>
          <textarea
            value={form.env}
            onChange={(e) => setField('env', e.target.value)}
            rows={3}
            placeholder="KEY=VALUE 格式，每行一个"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all font-mono text-sm"
          />
        </div>
      </div>
    </Modal>
  )
}

// 服务表单模态框（添加自定义服务）
function ServiceFormModal({ open, onClose, onSubmit, loading }) {
  const [form, setForm] = useState({ name: '', image: '', ports: '', env: '' })
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (open) {
      setForm({ name: '', image: '', ports: '', env: '' })
      setErrors({})
    }
  }, [open])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入服务名称'
    if (!form.image.trim()) e.image = '请输入镜像名称'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim(), image: form.image.trim() })
  }

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="添加服务"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={loading}>
            添加
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
            placeholder="例如：自定义服务"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.name ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            镜像 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.image}
            onChange={(e) => setField('image', e.target.value)}
            placeholder="例如: python:3.11"
            className={`w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.image ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'}`}
          />
          {errors.image && <p className="text-xs text-red-500 mt-1">{errors.image}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">端口映射</label>
          <input
            type="text"
            value={form.ports}
            onChange={(e) => setField('ports', e.target.value)}
            placeholder="例如: 8000:8000"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">环境变量</label>
          <textarea
            value={form.env}
            onChange={(e) => setField('env', e.target.value)}
            rows={3}
            placeholder="KEY=VALUE 格式，每行一个"
            className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all font-mono text-sm"
          />
        </div>
      </div>
    </Modal>
  )
}

export default function SandboxPage() {
  const toast = useToast()
  const [projects, setProjects] = useState([])
  const [services, setServices] = useState([])
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('projects')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('grid')

  const [showProjectForm, setShowProjectForm] = useState(false)
  const [savingProject, setSavingProject] = useState(false)
  const [showServiceForm, setShowServiceForm] = useState(false)
  const [savingService, setSavingService] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [logTarget, setLogTarget] = useState(null)
  const [consoleTarget, setConsoleTarget] = useState(null)

  const [pullImage, setPullImage] = useState('')
  const [pulling, setPulling] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const fetchProjects = useCallback(async (initial = false) => {
    if (initial) {
      setLoading(true)
      setError(null)
    }
    try {
      const res = await api.get('/api/sandbox/projects')
      setProjects(res.data)
      if (initial) setError(null)
    } catch (e) {
      if (initial) setError(e)
    } finally {
      if (initial) setLoading(false)
    }
  }, [])

  const fetchServices = useCallback(async () => {
    try {
      const res = await api.get('/api/sandbox/services')
      const list = Array.isArray(res.data) ? res.data : res.data.services || []
      // 兼容后端返回 dict 的旧格式：{id: {name, image, ...}}
      setServices(
        Array.isArray(list) ? list : Object.entries(list).map(([id, s]) => ({ id, ...s }))
      )
    } catch {
      setServices([])
    }
  }, [])

  const fetchImages = useCallback(async () => {
    try {
      const res = await api.get('/api/sandbox/images')
      setImages(Array.isArray(res.data) ? res.data : res.data.images || [])
    } catch {
      setImages([])
    }
  }, [])

  useEffect(() => {
    fetchProjects(true)
    fetchServices()
    fetchImages()
    const interval = setInterval(() => fetchProjects(false), 5000)
    return () => clearInterval(interval)
  }, [fetchProjects, fetchServices, fetchImages])

  const handleRefresh = async () => {
    setRefreshing(true)
    await Promise.all([fetchProjects(false), fetchServices(), fetchImages()])
    setRefreshing(false)
  }

  const handleCreateProject = async (formData) => {
    setSavingProject(true)
    try {
      await api.post('/api/sandbox/projects', formData)
      toast.success(`项目「${formData.name}」已创建`)
      setShowProjectForm(false)
      fetchProjects(false)
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    } finally {
      setSavingProject(false)
    }
  }

  const handleCreateService = async (formData) => {
    setSavingService(true)
    try {
      // 自定义服务为本地展示模板（无后端持久化接口），合并入列表
      const custom = {
        id: `custom-${Date.now()}`,
        name: formData.name,
        image: formData.image,
        ports: formData.ports
          ? formData.ports
              .split(',')
              .map((p) => p.trim())
              .filter(Boolean)
          : [],
        description: '自定义服务',
      }
      setServices((prev) => [...(Array.isArray(prev) ? prev : []), custom])
      toast.success(`服务「${formData.name}」已添加`)
      setShowServiceForm(false)
    } catch (e) {
      toast.error(`添加失败：${e.message}`)
    } finally {
      setSavingService(false)
    }
  }

  // 用预置模板一键创建沙箱项目（端口/环境变量取自模板，创建后切回项目列表）
  const handleQuickCreate = async (service) => {
    try {
      const ports = Array.isArray(service.ports) ? service.ports : [String(service.ports || '')].filter(Boolean)
      await api.post('/api/sandbox/projects', {
        name: `${service.name} 实例`,
        image: service.image,
        ports,
        env: service.env || [],
        command: service.command || '',
      })
      toast.success(`「${service.name}」项目已创建`)
      setActiveTab('projects')
      fetchProjects(false)
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    }
  }

  const handleAction = async (project, action) => {
    try {
      await api.post(`/api/sandbox/projects/${project.id}/${action}`, {})
      toast.success(
        action === 'start' ? `项目「${project.name}」已启动` : `项目「${project.name}」已停止`
      )
      fetchProjects(false)
    } catch (e) {
      toast.error(`${action === 'start' ? '启动' : '停止'}失败：${e.message}`)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/sandbox/projects/${deleteTarget.id}`)
      toast.success(`项目「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      fetchProjects(false)
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const handlePullImage = async () => {
    if (!pullImage.trim()) return
    setPulling(true)
    try {
      await api.post('/api/sandbox/images/pull', { image: pullImage.trim() })
      toast.success(`镜像「${pullImage.trim()}」拉取成功`)
      setPullImage('')
      fetchImages()
    } catch (e) {
      toast.error(`拉取失败：${e.message}`)
    } finally {
      setPulling(false)
    }
  }

  const filteredProjects = projects.filter((p) =>
    p.name?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const stats = [
    {
      label: '运行中',
      value: projects.filter((p) => p.status === 'running').length,
      icon: Activity,
      color: 'from-emerald-500 to-green-600',
    },
    {
      label: '已停止',
      value: projects.filter((p) => p.status !== 'running').length,
      icon: Square,
      color: 'from-gray-400 to-gray-500',
    },
    {
      label: '总项目',
      value: projects.length,
      icon: FolderOpen,
      color: 'from-violet-500 to-purple-600',
    },
    { label: '镜像数', value: images.length, icon: Container, color: 'from-blue-500 to-cyan-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="沙箱运行环境"
        description="管理容器化服务和项目代码"
        icon={Container}
        actions={
          <>
            <Button
              variant="secondary"
              icon={RefreshCw}
              onClick={handleRefresh}
              loading={refreshing}
            >
              刷新
            </Button>
            <Button variant="primary" icon={Plus} onClick={() => setShowProjectForm(true)}>
              新建项目
            </Button>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
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

      {/* Tabs */}
      <div className="bg-white rounded-2xl border border-gray-200 p-2 flex gap-2">
        {[
          { id: 'projects', label: '项目列表', icon: FolderOpen },
          { id: 'services', label: '预置服务', icon: Server },
          { id: 'images', label: '镜像管理', icon: Container },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-purple-600 text-white shadow-sm'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Projects Tab */}
      {activeTab === 'projects' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索项目名称…"
                className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              />
            </div>
            <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1 self-end sm:self-auto">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
                title="网格视图"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
                title="列表视图"
              >
                <ListIcon className="w-4 h-4" />
              </button>
            </div>
          </div>

          {loading ? (
            <SkeletonGrid count={6} />
          ) : error ? (
            <ErrorState
              message={`加载失败：${error.message}`}
              onRetry={() => fetchProjects(true)}
            />
          ) : filteredProjects.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty
                icon={FolderOpen}
                title={searchQuery ? '未找到匹配的项目' : '暂无项目'}
                description={
                  searchQuery ? '尝试调整搜索条件' : '点击「新建项目」开始你的第一个沙箱项目'
                }
                actionLabel={searchQuery ? undefined : '新建项目'}
                onAction={searchQuery ? undefined : () => setShowProjectForm(true)}
              />
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onStart={(p) => handleAction(p, 'start')}
                  onStop={(p) => handleAction(p, 'stop')}
                  onDelete={setDeleteTarget}
                  onLogs={setLogTarget}
                  onConsole={setConsoleTarget}
                  viewMode="grid"
                />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onStart={(p) => handleAction(p, 'start')}
                  onStop={(p) => handleAction(p, 'stop')}
                  onDelete={setDeleteTarget}
                  onLogs={setLogTarget}
                  onConsole={setConsoleTarget}
                  viewMode="list"
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Services Tab：单一数据源（后端 SERVICE_TEMPLATES），避免双份定义重复展示 */}
      {activeTab === 'services' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-gray-900">预置服务模板</h3>
            <Button
              variant="primary"
              size="sm"
              icon={Plus}
              onClick={() => setShowServiceForm(true)}
            >
              添加服务
            </Button>
          </div>
          {services.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty icon={Server} title="暂无服务模板" description="点击「添加服务」自定义模板，或从项目列表直接创建" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {services.map((service) => {
                const consoleType = serviceTypeOf(service.image)
                return (
                  <div
                    key={service.id}
                    className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all flex flex-col"
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                        <Server className="w-5 h-5 text-white" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-gray-900 truncate">{service.name}</h3>
                        <p className="text-xs text-gray-500 truncate font-mono">{service.image}</p>
                      </div>
                    </div>
                    <p className="text-sm text-gray-600 mb-4 flex-1">{service.description || '自定义服务'}</p>
                    <div className="flex items-center gap-2 text-xs text-gray-500 mb-3">
                      <span className="flex items-center gap-1">
                        <Zap className="w-3 h-3" />
                        {formatPorts(service.ports)}
                      </span>
                      {consoleType && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600">
                          <Database className="w-3 h-3" />
                          支持控制台
                        </span>
                      )}
                    </div>
                    <div className="pt-3 border-t border-gray-100">
                      <Button
                        variant="outline"
                        size="sm"
                        icon={PlayCircle}
                        className="w-full"
                        onClick={() => handleQuickCreate(service)}
                      >
                        一键创建项目
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Images Tab */}
      {activeTab === 'images' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-4 flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={pullImage}
              onChange={(e) => setPullImage(e.target.value)}
              placeholder="输入镜像名称，例如: python:3.11"
              className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              onKeyDown={(e) => e.key === 'Enter' && handlePullImage()}
            />
            <Button
              variant="primary"
              icon={Plus}
              loading={pulling}
              disabled={!pullImage.trim()}
              onClick={handlePullImage}
            >
              拉取
            </Button>
          </div>
          {images.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200">
              <Empty
                icon={Container}
                title="暂无镜像"
                description="在上方输入镜像名称并拉取，例如 python:3.11"
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {images.map((img) => (
                <div key={img.id} className="bg-white rounded-2xl border border-gray-200 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center">
                      <Container className="w-5 h-5 text-white" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-semibold text-gray-900 truncate">
                        {img.repository}:{img.tag}
                      </h3>
                      <p className="text-xs text-gray-500 truncate">{img.id}</p>
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>大小: {img.size || 'N/A'}</p>
                    <p>创建: {formatRelativeTime(img.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <ProjectFormModal
        open={showProjectForm}
        onClose={() => setShowProjectForm(false)}
        onSubmit={handleCreateProject}
        editing={null}
        loading={savingProject}
      />

      <ServiceFormModal
        open={showServiceForm}
        onClose={() => setShowServiceForm(false)}
        onSubmit={handleCreateService}
        loading={savingService}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除项目"
        message={`确定要删除项目「${deleteTarget?.name}」吗？这将同时删除容器和数据，此操作不可撤销。`}
        confirmLabel="确认删除"
      />

      <LogModal project={logTarget} onClose={() => setLogTarget(null)} />
<ServiceConsoleModal project={consoleTarget} onClose={() => setConsoleTarget(null)} />
    </div>
  )
}
