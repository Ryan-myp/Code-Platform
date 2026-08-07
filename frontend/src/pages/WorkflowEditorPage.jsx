import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Plus,
  Trash2,
  Play,
  Save,
  Download,
  GitBranch,
  GitMerge,
  Code2,
  Globe,
  Zap,
  FileText,
  Clock,
  Image as ImageIcon,
  Video,
  Music,
  CheckCircle2,
  XCircle,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  ChevronLeft,
  Undo2,
  Redo2,
  X,
  Workflow,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDateTime } from '../lib/format'
import { Modal, Button, Empty, PageLoading, ErrorState, ConfirmDialog } from '../components/ui'

// 节点类型定义（与后端 workflows/executor.py 支持的节点一一对应）
const NODE_TYPES = {
  agent: {
    label: 'Agent',
    icon: GitBranch,
    color: 'purple',
    config: { agent_id: '', message: '' },
  },
  http: {
    label: 'HTTP 请求',
    icon: Globe,
    color: 'blue',
    config: { url: '', method: 'GET', headers: '{}' },
  },
  condition: { label: '条件判断', icon: GitMerge, color: 'orange', config: { expression: '' } },
  parallel: { label: '并行执行', icon: Zap, color: 'green', config: {} },
  code: { label: '代码执行', icon: Code2, color: 'gray', config: { code: '', language: 'python' } },
  delay: { label: '延迟等待', icon: Clock, color: 'yellow', config: { seconds: 1 } },
  image: {
    label: '图片生成',
    icon: ImageIcon,
    color: 'pink',
    config: { prompt: '', size: '1024x1024', model: 'agnes-image-2.1-flash' },
  },
  video: {
    label: '视频生成',
    icon: Video,
    color: 'blue',
    config: { prompt: '', duration: 5, width: 1152, height: 768 },
  },
  music: {
    label: '音乐歌词',
    icon: Music,
    color: 'yellow',
    config: { theme: '', style: 'pop', language: 'zh', mood: 'happy' },
  },
  prd: {
    label: 'PRD 流程',
    icon: FileText,
    color: 'orange',
    config: { stage: 'generate', prd_text: '', tech_design: '', language: 'python' },
  },
  output: { label: '输出节点', icon: FileText, color: 'pink', config: {} },
}

// 静态颜色映射（避免 Tailwing 动态类名被 purge）
const COLOR_STYLES = {
  purple: {
    header: 'bg-purple-500',
    ring: 'ring-purple-500',
    text: 'text-purple-600',
    light: 'bg-purple-50',
    border: 'border-purple-500',
  },
  blue: {
    header: 'bg-blue-500',
    ring: 'ring-blue-500',
    text: 'text-blue-600',
    light: 'bg-blue-50',
    border: 'border-blue-500',
  },
  orange: {
    header: 'bg-orange-500',
    ring: 'ring-orange-500',
    text: 'text-orange-600',
    light: 'bg-orange-50',
    border: 'border-orange-500',
  },
  green: {
    header: 'bg-green-500',
    ring: 'ring-green-500',
    text: 'text-green-600',
    light: 'bg-green-50',
    border: 'border-green-500',
  },
  gray: {
    header: 'bg-gray-500',
    ring: 'ring-gray-500',
    text: 'text-gray-600',
    light: 'bg-gray-50',
    border: 'border-gray-500',
  },
  yellow: {
    header: 'bg-yellow-500',
    ring: 'ring-yellow-500',
    text: 'text-yellow-600',
    light: 'bg-yellow-50',
    border: 'border-yellow-500',
  },
  pink: {
    header: 'bg-pink-500',
    ring: 'ring-pink-500',
    text: 'text-pink-600',
    light: 'bg-pink-50',
    border: 'border-pink-500',
  },
}

const NODE_W = 120
const NODE_H = 60

export default function WorkflowEditorPage() {
  const { id: workflowId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()

  const [workflow, setWorkflow] = useState(null)
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])
  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [showRunDialog, setShowRunDialog] = useState(false)
  const [runInput, setRunInput] = useState('')
  const [deleteNodeTarget, setDeleteNodeTarget] = useState(null)
  const [agents, setAgents] = useState([])

  // 画布交互
  const [dragging, setDragging] = useState(null)
  const [dragMoved, setDragMoved] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const [pendingConnection, setPendingConnection] = useState(null)
  const canvasRef = useRef(null)

  // 自动保存状态
  const [autoSaveStatus, setAutoSaveStatus] = useState('idle') // idle | saving | saved | error
  const [lastSavedAt, setLastSavedAt] = useState(null)

  // 历史（撤销/重做）
  const pastRef = useRef([])
  const futureRef = useRef([])
  const prevSnapshotRef = useRef(null)
  const historyTimerRef = useRef(null)
  const [, setHistoryVersion] = useState(0)

  // 状态镜像，供异步读取最新值
  const stateRef = useRef({ nodes, edges, workflow })
  useEffect(() => {
    stateRef.current = { nodes, edges, workflow }
  }, [nodes, edges, workflow])

  const loadedRef = useRef(false)
  const autoSaveTimerRef = useRef(null)

  // 加载工作流
  const loadWorkflow = useCallback(async () => {
    if (!workflowId) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(`/api/workflows/${workflowId}`)
      const wf = res.data
      setWorkflow(wf)
      const def = wf.definition || { nodes: [], edges: [] }
      const parsedNodes = Array.isArray(def.nodes) ? def.nodes : []
      const parsedEdges = Array.isArray(def.edges) ? def.edges : []
      setNodes(parsedNodes)
      setEdges(parsedEdges)
      // 初始化历史基线
      prevSnapshotRef.current = JSON.stringify({ nodes: parsedNodes, edges: parsedEdges })
      pastRef.current = []
      futureRef.current = []
      loadedRef.current = true
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [workflowId])

  useEffect(() => {
    loadWorkflow()
  }, [loadWorkflow])

  // 加载 Agent 列表（供 agent 节点下拉选择）
  useEffect(() => {
    api
      .get('/api/agents')
      .then((res) => setAgents(Array.isArray(res.data) ? res.data : []))
      .catch(() => setAgents([]))
  }, [])

  // ── 历史记录：监听 nodes/edges 变化，防抖提交 ──
  useEffect(() => {
    const snapshot = JSON.stringify({ nodes, edges })
    if (!prevSnapshotRef.current) {
      prevSnapshotRef.current = snapshot
      return
    }
    if (snapshot === prevSnapshotRef.current) return
    // 拖拽进行中不提交历史，避免每帧一条记录
    clearTimeout(historyTimerRef.current)
    historyTimerRef.current = setTimeout(() => {
      // 若与最近一次一致则跳过
      if (prevSnapshotRef.current === snapshot) return
      pastRef.current.push(prevSnapshotRef.current)
      // 限制历史长度，避免内存膨胀
      if (pastRef.current.length > 50) pastRef.current.shift()
      futureRef.current = []
      prevSnapshotRef.current = snapshot
      setHistoryVersion((v) => v + 1)
    }, 400)
    return () => clearTimeout(historyTimerRef.current)
  }, [nodes, edges])

  const undo = useCallback(() => {
    clearTimeout(historyTimerRef.current)
    if (pastRef.current.length === 0) return
    const prev = pastRef.current.pop()
    futureRef.current.unshift(prevSnapshotRef.current)
    prevSnapshotRef.current = prev
    const state = JSON.parse(prev)
    setNodes(state.nodes)
    setEdges(state.edges)
    setSelectedNodeId(null)
    setHistoryVersion((v) => v + 1)
  }, [])

  const redo = useCallback(() => {
    clearTimeout(historyTimerRef.current)
    if (futureRef.current.length === 0) return
    const next = futureRef.current.shift()
    pastRef.current.push(prevSnapshotRef.current)
    prevSnapshotRef.current = next
    const state = JSON.parse(next)
    setNodes(state.nodes)
    setEdges(state.edges)
    setSelectedNodeId(null)
    setHistoryVersion((v) => v + 1)
  }, [])

  const canUndo = pastRef.current.length > 0
  const canRedo = futureRef.current.length > 0

  // ── 自动保存：debounce 2s ──
  const toastRef = useRef(toast)
  toastRef.current = toast

  const doSave = useCallback(async ({ manual = false } = {}) => {
    const { nodes: n, edges: e, workflow: wf } = stateRef.current
    if (!wf) return false
    if (manual) setSaving(true)
    setAutoSaveStatus('saving')
    try {
      await api.put(`/api/workflows/${wf.id}`, {
        name: wf.name,
        description: wf.description,
        definition: { nodes: n, edges: e },
      })
      setAutoSaveStatus('saved')
      setLastSavedAt(new Date())
      if (manual) {
        toastRef.current.success('保存成功')
      } else {
        toastRef.current.success('已自动保存', 1500)
      }
      return true
    } catch (err) {
      setAutoSaveStatus('error')
      toastRef.current.error(`保存失败：${err.message}`)
      return false
    } finally {
      if (manual) setSaving(false)
    }
  }, [])

  // 上次保存的快照，防止无变化时重复保存
  const lastSavedSnapshotRef = useRef('')

  useEffect(() => {
    if (!loadedRef.current || !workflow) return
    clearTimeout(autoSaveTimerRef.current)
    const snapshot = JSON.stringify({ nodes, edges })
    if (snapshot === lastSavedSnapshotRef.current) return
    autoSaveTimerRef.current = setTimeout(() => {
      lastSavedSnapshotRef.current = snapshot
      doSave({ manual: false })
    }, 2000)
    return () => clearTimeout(autoSaveTimerRef.current)
  }, [nodes, edges, workflow, doSave])

  // ── 节点操作 ──
  const addNode = (type) => {
    const cfg = NODE_TYPES[type]
    if (!cfg) return
    const newNode = {
      id: `node_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type,
      label: `${cfg.label} ${nodes.length + 1}`,
      x: 120 + Math.random() * 240 - position.x / zoom,
      y: 100 + Math.random() * 160 - position.y / zoom,
      config: { ...cfg.config },
    }
    setNodes((prev) => [...prev, newNode])
    setSelectedNodeId(newNode.id)
  }

  const deleteNode = (nodeId) => {
    setNodes((prev) => prev.filter((n) => n.id !== nodeId))
    setEdges((prev) => prev.filter((e) => e.from !== nodeId && e.to !== nodeId))
    if (selectedNodeId === nodeId) setSelectedNodeId(null)
  }

  const updateNodePosition = (nodeId, x, y) => {
    setNodes((prev) => prev.map((n) => (n.id === nodeId ? { ...n, x, y } : n)))
  }

  const updateNodeConfig = (nodeId, key, value) => {
    setNodes((prev) =>
      prev.map((n) => (n.id === nodeId ? { ...n, config: { ...n.config, [key]: value } } : n))
    )
  }

  const updateNodeLabel = (nodeId, label) => {
    setNodes((prev) => prev.map((n) => (n.id === nodeId ? { ...n, label } : n)))
  }

  // ── 边操作 ──
  const addEdge = (from, to) => {
    if (from === to) return
    setEdges((prev) => {
      if (prev.some((e) => e.from === from && e.to === to)) return prev
      return [...prev, { id: `edge_${from}_${to}_${Date.now()}`, from, to }]
    })
  }

  const deleteEdge = (edgeId) => {
    setEdges((prev) => prev.filter((e) => e.id !== edgeId))
  }

  // ── 画布交互 ──
  const handleMouseDown = (nodeId, e) => {
    e.stopPropagation()
    setDragging(nodeId)
    setDragMoved(false)
    setSelectedNodeId(nodeId)
  }

  const handleMouseMove = (e) => {
    if (dragging) {
      const canvas = canvasRef.current
      if (canvas) {
        const rect = canvas.getBoundingClientRect()
        const x = (e.clientX - rect.left - position.x) / zoom - NODE_W / 2
        const y = (e.clientY - rect.top - position.y) / zoom - NODE_H / 2
        updateNodePosition(dragging, Math.round(x), Math.round(y))
        setDragMoved(true)
      }
    }
    if (isPanning) {
      const dx = e.clientX - panStart.x
      const dy = e.clientY - panStart.y
      setPosition((p) => ({ x: p.x + dx, y: p.y + dy }))
      setPanStart({ x: e.clientX, y: e.clientY })
    }
  }

  const handleMouseUp = () => {
    setDragging(null)
    setIsPanning(false)
  }

  const handleNodeClick = (nodeId, e) => {
    e.stopPropagation()
    // 如果正在连线，点击任意节点完成连线（不清除 pendingConnection，支持连续分支）
    if (pendingConnection && pendingConnection !== nodeId) {
      addEdge(pendingConnection, nodeId)
      toast.success(`已连线 → ${nodes.find((n) => n.id === nodeId)?.label || nodeId}`)
      // 不清除 pendingConnection，允许继续连线实现分支
    } else if (!dragMoved) {
      // 没有连线时，正常选中节点
      setPendingConnection(null)
      setSelectedNodeId(nodeId)
    }
  }

  // 运行工作流
  const runWorkflow = async () => {
    if (!workflow) return
    if (nodes.length === 0) {
      toast.error('请先在画布中添加节点')
      return
    }
    if (!runInput.trim()) {
      toast.error('请输入执行内容')
      return
    }
    setShowRunDialog(false)
    setRunning(true)
    try {
      const res = await api.post(`/api/workflows/${workflow.id}/run`, { message: runInput.trim() })
      setRunResult(res.data)
      setRunInput('')
    } catch (e) {
      toast.error(`执行失败：${e.message}`)
    } finally {
      setRunning(false)
    }
  }

  // 导出工作流
  const exportWorkflow = () => {
    const data = { nodes, edges, version: '1.0', name: workflow?.name }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${workflow?.name || 'workflow'}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('已导出工作流')
  }

  // ── 键盘快捷键 ──
  useEffect(() => {
    const handler = (e) => {
      const tag = e.target?.tagName
      const isInput =
        tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable
      const mod = e.ctrlKey || e.metaKey

      if (mod && e.key.toLowerCase() === 'z') {
        if (isInput) return
        e.preventDefault()
        if (e.shiftKey) redo()
        else undo()
      } else if (mod && e.key.toLowerCase() === 'y') {
        if (isInput) return
        e.preventDefault()
        redo()
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && !isInput) {
        if (selectedNodeId) {
          e.preventDefault()
          setDeleteNodeTarget(selectedNodeId)
        }
      } else if (e.key === 'Escape') {
        setSelectedNodeId(null)
        setPendingConnection(null)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, selectedNodeId])

  if (loading) return <PageLoading label="加载工作流…" />
  if (error) return <ErrorState message={`加载失败：${error.message}`} onRetry={loadWorkflow} />
  if (!workflow) return <ErrorState message="工作流不存在" />

  const selectedNodeData = nodes.find((n) => n.id === selectedNodeId)

  return (
    <div className="relative flex h-[calc(100vh-2rem)] md:h-[calc(100vh-3rem)] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      {/* 左侧节点工具栏 */}
      <aside className="w-16 bg-white border-r border-gray-200 flex flex-col items-center py-3 gap-1.5 overflow-y-auto">
        <div className="text-[10px] text-gray-400 font-medium mb-1">节点</div>
        {Object.entries(NODE_TYPES).map(([type, cfg]) => {
          const Icon = cfg.icon
          const styles = COLOR_STYLES[cfg.color]
          return (
            <button
              key={type}
              onClick={() => addNode(type)}
              className={`w-11 h-11 flex flex-col items-center justify-center rounded-xl border border-gray-200 hover:${styles.light} hover:border-current transition-all group relative`}
              title={`添加 ${cfg.label}`}
            >
              <Icon className={`w-5 h-5 ${styles.text}`} />
            </button>
          )
        })}
        <div className="flex-1" />
        <button
          onClick={() => setZoom((z) => Math.max(0.4, +(z - 0.1).toFixed(2)))}
          className="w-11 h-11 flex items-center justify-center rounded-xl hover:bg-gray-100 text-gray-500 transition-colors"
          title="缩小"
        >
          <ZoomOut className="w-5 h-5" />
        </button>
        <span className="text-[10px] text-gray-400">{Math.round(zoom * 100)}%</span>
        <button
          onClick={() => setZoom((z) => Math.min(2, +(z + 0.1).toFixed(2)))}
          className="w-11 h-11 flex items-center justify-center rounded-xl hover:bg-gray-100 text-gray-500 transition-colors"
          title="放大"
        >
          <ZoomIn className="w-5 h-5" />
        </button>
        <button
          onClick={() => {
            setZoom(1)
            setPosition({ x: 0, y: 0 })
          }}
          className="w-11 h-11 flex items-center justify-center rounded-xl hover:bg-gray-100 text-gray-500 transition-colors"
          title="重置视图"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </aside>

      {/* 中间画布区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部工具栏 */}
        <div className="h-14 bg-white border-b border-gray-200 flex items-center px-3 gap-2 flex-shrink-0">
          <button
            onClick={() => navigate('/workflows')}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600"
            title="返回"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>

          <input
            type="text"
            value={workflow.name || ''}
            onChange={(e) => setWorkflow((w) => ({ ...w, name: e.target.value }))}
            className="font-semibold text-gray-900 bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-purple-300 rounded px-1 min-w-0 flex-1"
            placeholder="工作流名称"
          />

          {/* 自动保存状态指示 */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400 mr-1">
            {autoSaveStatus === 'saving' && (
              <>
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>保存中…</span>
              </>
            )}
            {autoSaveStatus === 'saved' && lastSavedAt && (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>已保存 {formatDateTime(lastSavedAt).slice(11)}</span>
              </>
            )}
            {autoSaveStatus === 'error' && (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                <span className="text-red-500">保存失败</span>
              </>
            )}
          </div>

          <div className="h-6 w-px bg-gray-200 mx-1" />

          <button
            onClick={undo}
            disabled={!canUndo}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
            title="撤销 (Ctrl+Z)"
          >
            <Undo2 className="w-4 h-4" />
          </button>
          <button
            onClick={redo}
            disabled={!canRedo}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
            title="重做 (Ctrl+Shift+Z)"
          >
            <Redo2 className="w-4 h-4" />
          </button>

          <div className="h-6 w-px bg-gray-200 mx-1" />

          <Button variant="secondary" size="sm" icon={Download} onClick={exportWorkflow}>
            <span className="hidden sm:inline">导出</span>
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={Save}
            loading={saving}
            onClick={() => doSave({ manual: true })}
          >
            <span className="hidden sm:inline">保存</span>
          </Button>
          <Button variant="success" size="sm" icon={Play} onClick={() => setShowRunDialog(true)}>
            <span className="hidden sm:inline">执行</span>
          </Button>
        </div>

        {/* 画布 */}
        <div
          ref={canvasRef}
          className="flex-1 relative overflow-hidden bg-gray-50"
          style={{
            cursor: pendingConnection
              ? 'crosshair'
              : isPanning
                ? 'grabbing'
                : dragging
                  ? 'grabbing'
                  : 'default',
          }}
          onMouseDown={(e) => {
            // 点击画布空白处退出连线模式或取消选中
            const isCanvas =
              e.target === canvasRef.current ||
              ['svg', 'rect', 'path'].includes(e.target.tagName?.toLowerCase())
            if (isCanvas) {
              if (pendingConnection) {
                setPendingConnection(null)
                toast.info('已退出连线模式')
              }
              setIsPanning(true)
              setPanStart({ x: e.clientX, y: e.clientY })
              setSelectedNodeId(null)
            }
          }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <div
            className="absolute top-0 left-0"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${zoom})`,
              transformOrigin: '0 0',
            }}
          >
            {/* 网格背景 */}
            <svg
              className="absolute top-0 left-0"
              width="4000"
              height="4000"
              style={{ pointerEvents: 'none' }}
            >
              <defs>
                <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                  <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="4000" height="4000" fill="url(#grid)" />
            </svg>

            {/* 边 */}
            <svg
              className="absolute top-0 left-0"
              width="4000"
              height="4000"
              style={{ pointerEvents: 'none' }}
            >
              {edges.map((edge) => {
                const fromNode = nodes.find((n) => n.id === edge.from)
                const toNode = nodes.find((n) => n.id === edge.to)
                if (!fromNode || !toNode) return null
                const x1 = fromNode.x + NODE_W
                const y1 = fromNode.y + NODE_H / 2
                const x2 = toNode.x
                const y2 = toNode.y + NODE_H / 2
                const mx = (x1 + x2) / 2
                return (
                  <g
                    key={edge.id}
                    style={{ pointerEvents: 'auto', cursor: 'pointer' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteEdge(edge.id)
                      toast.info('已删除连线')
                    }}
                  >
                    {/* 隐形加粗点击区域 */}
                    <path
                      d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
                      fill="none"
                      stroke="transparent"
                      strokeWidth="14"
                    />
                    {/* 可见连线 */}
                    <path
                      d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
                      fill="none"
                      stroke="#9ca3af"
                      strokeWidth="2"
                      className="hover:stroke-red-400 hover:stroke-[3px]"
                      style={{ pointerEvents: 'none' }}
                    />
                    {/* 中点删除按钮 */}
                    <circle
                      cx={(x1 + x2) / 2}
                      cy={(y1 + y2) / 2}
                      r="6"
                      fill="white"
                      stroke="#d1d5db"
                      strokeWidth="1.5"
                      className="hover:fill-red-100 hover:stroke-red-400"
                    />
                    <text
                      x={(x1 + x2) / 2}
                      y={(y1 + y2) / 2 + 3.5}
                      textAnchor="middle"
                      fontSize="9"
                      fill="#9ca3af"
                      style={{ pointerEvents: 'none' }}
                    >
                      ×
                    </text>
                  </g>
                )
              })}
            </svg>

            {/* 节点 */}
            {nodes.map((node) => {
              const NodeType = NODE_TYPES[node.type]?.icon || Code2
              const isSelected = selectedNodeId === node.id
              const isPendingFrom = pendingConnection === node.id
              const cfg = NODE_TYPES[node.type]
              const styles = COLOR_STYLES[cfg?.color] || COLOR_STYLES.gray
              const isPendingTo = pendingConnection && pendingConnection !== node.id
              return (
                <div
                  key={node.id}
                  className={`absolute select-none group ${isSelected ? `z-20` : 'z-10'}`}
                  style={{ left: node.x, top: node.y, width: NODE_W }}
                  onMouseDown={(e) => handleMouseDown(node.id, e)}
                  onClick={(e) => handleNodeClick(node.id, e)}
                >
                  <div
                    className={`relative w-full bg-white rounded-xl shadow-md border-2 cursor-move transition-shadow ${
                      isSelected ? `${styles.border} ring-2 ${styles.ring}/30` : 'border-gray-200'
                    } ${isPendingFrom ? 'ring-2 ring-offset-1 ' + styles.ring : ''} ${isPendingTo ? 'ring-2 ring-offset-1 ring-purple-400' : ''}`}
                    style={{ width: NODE_W }}
                  >
                    <div
                      className={`px-2 py-1.5 rounded-t-lg flex items-center gap-1.5 ${styles.header}`}
                    >
                      <NodeType className="w-3.5 h-3.5 text-white flex-shrink-0" />
                      <span className="text-[10px] text-white font-medium truncate">
                        {cfg?.label}
                      </span>
                    </div>
                    <div className="px-2 py-2 text-xs text-gray-800 text-center truncate">
                      {node.label}
                    </div>

                    {/* 输入连接点（左侧） */}
                    <div
                      onMouseDown={(e) => {
                        e.stopPropagation()
                        e.preventDefault()
                      }}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (pendingConnection && pendingConnection !== node.id) {
                          addEdge(pendingConnection, node.id)
                          const label = nodes.find((n) => n.id === node.id)?.label || node.id
                          toast.success(`已连线 → ${label}`)
                        }
                      }}
                      className="absolute top-1/2 -left-4 -translate-y-1/2 w-6 h-6 rounded-full border-2 border-white cursor-pointer transition-all z-30 flex items-center justify-center shadow-md hover:scale-110"
                      style={{ background: isPendingTo ? '#a855f7' : '#d1d5db' }}
                      title={pendingConnection ? '✅ 点击完成连线' : '输入端'}
                    >
                      <svg width="10" height="10" viewBox="0 0 10 10">
                        <polygon points="3,1 8,5 3,9" fill="white" />
                      </svg>
                    </div>

                    {/* 输出连接点（右侧） */}
                    <div
                      onMouseDown={(e) => {
                        e.stopPropagation()
                        e.preventDefault()
                      }}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (pendingConnection === node.id) {
                          setPendingConnection(null)
                          toast.info('已退出连线模式')
                        } else {
                          setPendingConnection(node.id)
                          const label = nodes.find((n) => n.id === node.id)?.label || node.id
                          toast.success(`从「${label}」开始连线，可连续创建分支`)
                        }
                      }}
                      className="absolute top-1/2 -right-4 -translate-y-1/2 w-6 h-6 rounded-full border-2 border-white cursor-pointer transition-all z-30 flex items-center justify-center shadow-md hover:scale-110"
                      style={{ background: isPendingFrom ? '#3b82f6' : '#9ca3af' }}
                      title="点击开始连线"
                    >
                      <svg width="10" height="10" viewBox="0 0 10 10">
                        <polygon points="2,1 7,5 2,9" fill="white" />
                      </svg>
                    </div>

                    {/* 删除按钮 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleteNodeTarget(node.id)
                      }}
                      className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600 opacity-0 group-hover:opacity-100 transition-opacity z-30"
                      style={{ opacity: isSelected ? 1 : 0 }}
                      title="删除节点"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          {/* 空状态 */}
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <Empty
                icon={Workflow}
                title="画布为空"
                description="从左侧节点栏点击添加节点，支持 Agent / 图片 / 视频 / 音乐 / PRD 等节点编排"
              />
            </div>
          )}

          {/* 连线模式提示 */}
          {pendingConnection && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 px-4 py-2 bg-purple-600 text-white text-xs rounded-full shadow-lg z-30 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
              <span>
                连线模式：点击目标节点创建连线（支持分支）
                <span className="ml-2 text-purple-200">| 点击空白处或按 Esc 退出</span>
              </span>
            </div>
          )}

          {/* 快捷键提示 */}
          <div className="absolute bottom-3 right-3 px-2.5 py-1.5 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg text-[10px] text-gray-400 hidden md:block">
            拖拽移动 · 右侧圆点连线（支持分支） · 点击连线删除 · Del 删除 · Ctrl+Z 撤销 · $
            {'{input}'} 引用输入
          </div>
        </div>
      </div>

      {/* 右侧节点配置面板 */}
      {selectedNodeData && (
        <aside className="w-64 bg-white border-l border-gray-200 flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">节点配置</h3>
            <button
              onClick={() => setSelectedNodeId(null)}
              className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">节点名称</label>
              <input
                type="text"
                value={selectedNodeData.label || ''}
                onChange={(e) => updateNodeLabel(selectedNodeData.id, e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">节点类型</label>
              <div className="px-3 py-2 bg-gray-50 rounded-lg text-sm text-gray-600">
                {NODE_TYPES[selectedNodeData.type]?.label || selectedNodeData.type}
              </div>
            </div>

            {selectedNodeData.type === 'agent' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">选择 Agent</label>
                  {agents.length > 0 ? (
                    <select
                      value={selectedNodeData.config.agent_id || ''}
                      onChange={(e) =>
                        updateNodeConfig(selectedNodeData.id, 'agent_id', e.target.value)
                      }
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    >
                      <option value="">通用智能助手（不指定）</option>
                      {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={selectedNodeData.config.agent_id || ''}
                      onChange={(e) =>
                        updateNodeConfig(selectedNodeData.id, 'agent_id', e.target.value)
                      }
                      placeholder="输入 Agent ID"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    />
                  )}
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">执行指令</label>
                  <textarea
                    value={selectedNodeData.config.message ?? ''}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'message', e.target.value)
                    }
                    rows={3}
                    placeholder="留空则使用工作流输入；可引用上游结果 ${'{node_x.result}'}"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                  <p className="text-xs text-gray-400 mt-1">留空默认使用工作流的输入内容</p>
                </div>
              </>
            )}

            {selectedNodeData.type === 'http' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">URL</label>
                  <input
                    type="text"
                    value={selectedNodeData.config.url || ''}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'url', e.target.value)}
                    placeholder="https://api.example.com"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">请求方法</label>
                  <select
                    value={selectedNodeData.config.method || 'GET'}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'method', e.target.value)
                    }
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Headers (JSON)
                  </label>
                  <textarea
                    value={selectedNodeData.config.headers || '{}'}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'headers', e.target.value)
                    }
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
              </>
            )}

            {selectedNodeData.type === 'condition' && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">表达式</label>
                <textarea
                  value={selectedNodeData.config.expression || ''}
                  onChange={(e) =>
                    updateNodeConfig(selectedNodeData.id, 'expression', e.target.value)
                  }
                  rows={3}
                  placeholder="例如: ${input.status} == 'success'"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                />
              </div>
            )}

            {selectedNodeData.type === 'code' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">语言</label>
                  <select
                    value={selectedNodeData.config.language || 'python'}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'language', e.target.value)
                    }
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  >
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript</option>
                    <option value="bash">Bash</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">代码</label>
                  <textarea
                    value={selectedNodeData.config.code || ''}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'code', e.target.value)}
                    rows={6}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
              </>
            )}

            {selectedNodeData.type === 'delay' && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">延迟秒数</label>
                <input
                  type="number"
                  min="0"
                  value={selectedNodeData.config.seconds ?? 1}
                  onChange={(e) =>
                    updateNodeConfig(
                      selectedNodeData.id,
                      'seconds',
                      parseFloat(e.target.value) || 0
                    )
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                />
              </div>
            )}

            {selectedNodeData.type === 'image' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">画面描述</label>
                  <textarea
                    value={selectedNodeData.config.prompt || ''}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'prompt', e.target.value)
                    }
                    rows={3}
                    placeholder="描述要生成的图片，如：${'{input.message}'}"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    可引用上游节点结果，如 ${'{node_1.result}'}
                  </p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">图片尺寸</label>
                  <select
                    value={selectedNodeData.config.size || '1024x1024'}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'size', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  >
                    <option value="1024x1024">1024×1024（方形）</option>
                    <option value="768x1024">768×1024（竖版）</option>
                    <option value="1024x768">1024×768（横版）</option>
                  </select>
                </div>
              </>
            )}

            {selectedNodeData.type === 'video' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">视频描述</label>
                  <textarea
                    value={selectedNodeData.config.prompt || ''}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'prompt', e.target.value)
                    }
                    rows={3}
                    placeholder="描述视频内容，如：${'{input.message}'}"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">时长（秒）</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={selectedNodeData.config.duration ?? 5}
                    onChange={(e) =>
                      updateNodeConfig(
                        selectedNodeData.id,
                        'duration',
                        parseInt(e.target.value) || 5
                      )
                    }
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">宽度</label>
                    <input
                      type="number"
                      value={selectedNodeData.config.width ?? 1152}
                      onChange={(e) =>
                        updateNodeConfig(
                          selectedNodeData.id,
                          'width',
                          parseInt(e.target.value) || 1152
                        )
                      }
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">高度</label>
                    <input
                      type="number"
                      value={selectedNodeData.config.height ?? 768}
                      onChange={(e) =>
                        updateNodeConfig(
                          selectedNodeData.id,
                          'height',
                          parseInt(e.target.value) || 768
                        )
                      }
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    />
                  </div>
                </div>
              </>
            )}

            {selectedNodeData.type === 'music' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">歌词主题</label>
                  <input
                    type="text"
                    value={selectedNodeData.config.theme || ''}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'theme', e.target.value)}
                    placeholder="如：${'{input.message}'}"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">曲风</label>
                    <select
                      value={selectedNodeData.config.style || 'pop'}
                      onChange={(e) =>
                        updateNodeConfig(selectedNodeData.id, 'style', e.target.value)
                      }
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    >
                      {[
                        'pop',
                        'rock',
                        'folk',
                        'electronic',
                        'country',
                        'rap',
                        'jazz',
                        'classical',
                      ].map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">语言</label>
                    <select
                      value={selectedNodeData.config.language || 'zh'}
                      onChange={(e) =>
                        updateNodeConfig(selectedNodeData.id, 'language', e.target.value)
                      }
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    >
                      <option value="zh">中文</option>
                      <option value="en">English</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">情感基调</label>
                  <select
                    value={selectedNodeData.config.mood || 'happy'}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'mood', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  >
                    {['happy', 'sad', 'energetic', 'calm', 'romantic'].map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {selectedNodeData.type === 'prd' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">流程阶段</label>
                  <select
                    value={selectedNodeData.config.stage || 'generate'}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'stage', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  >
                    <option value="generate">生成 PRD</option>
                    <option value="review">评审 PRD</option>
                    <option value="td">技术设计</option>
                    <option value="test">生成测试用例</option>
                    <option value="code">生成代码</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">PRD 文本</label>
                  <textarea
                    value={selectedNodeData.config.prd_text || ''}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'prd_text', e.target.value)
                    }
                    rows={4}
                    placeholder="需求描述，可引用 ${'{input.message}'}"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                {(selectedNodeData.config.stage === 'test' ||
                  selectedNodeData.config.stage === 'code') && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">技术设计</label>
                    <textarea
                      value={selectedNodeData.config.tech_design || ''}
                      onChange={(e) =>
                        updateNodeConfig(selectedNodeData.id, 'tech_design', e.target.value)
                      }
                      rows={3}
                      placeholder="技术方案描述"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    />
                  </div>
                )}
                {selectedNodeData.config.stage === 'code' && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">代码语言</label>
                    <select
                      value={selectedNodeData.config.language || 'python'}
                      onChange={(e) =>
                        updateNodeConfig(selectedNodeData.id, 'language', e.target.value)
                      }
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    >
                      {['python', 'javascript', 'java', 'go', 'typescript'].map((l) => (
                        <option key={l} value={l}>
                          {l}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </>
            )}

            {selectedNodeData.type === 'parallel' && (
              <p className="text-xs text-gray-400">
                并行执行节点无需额外配置，所有下游分支将同时触发。
              </p>
            )}

            {selectedNodeData.type === 'output' && (
              <p className="text-xs text-gray-400">输出节点将上游结果作为工作流的最终输出。</p>
            )}
          </div>

          <div className="p-4 border-t border-gray-200">
            <Button
              variant="danger"
              icon={Trash2}
              className="w-full"
              onClick={() => setDeleteNodeTarget(selectedNodeData.id)}
            >
              删除节点
            </Button>
          </div>
        </aside>
      )}

      {/* 删除节点确认 */}
      <ConfirmDialog
        open={!!deleteNodeTarget}
        onClose={() => setDeleteNodeTarget(null)}
        onConfirm={() => {
          if (deleteNodeTarget) {
            deleteNode(deleteNodeTarget)
            toast.success('节点已删除')
          }
        }}
        title="确认删除节点"
        message={
          <>
            确定要删除节点「
            <span className="font-medium text-gray-700">
              {nodes.find((n) => n.id === deleteNodeTarget)?.label}
            </span>
            」吗？关联的连线也会一并删除，此操作可通过撤销恢复。
          </>
        }
        confirmLabel="删除"
      />

      {/* 运行输入对话框 */}
      <Modal
        open={showRunDialog}
        onClose={() => {
          setShowRunDialog(false)
          setRunInput('')
        }}
        title={`执行工作流：${workflow?.name || ''}`}
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                setShowRunDialog(false)
                setRunInput('')
              }}
            >
              取消
            </Button>
            <Button variant="success" icon={Play} loading={running} onClick={runWorkflow}>
              执行
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-700">请输入执行内容或指令</label>
          <textarea
            value={runInput}
            onChange={(e) => setRunInput(e.target.value)}
            placeholder="例如：帮我分析用户登录功能的需求..."
            className="w-full h-32 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 resize-none"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                runWorkflow()
              }
            }}
          />
          <p className="text-xs text-gray-400">提示：按 Ctrl+Enter 快速执行</p>
        </div>
      </Modal>

      {/* 执行结果 */}
      <Modal
        open={!!runResult}
        onClose={() => setRunResult(null)}
        title="工作流执行结果"
        size="lg"
        footer={<Button onClick={() => setRunResult(null)}>关闭</Button>}
      >
        {runResult ? (
          <div className="space-y-3">
            {runResult.engine && (
              <div className="flex items-center gap-2 text-sm">
                <span className="px-2 py-0.5 bg-gray-100 rounded text-gray-600">
                  引擎: {runResult.engine}
                </span>
                {runResult.elapsed != null && (
                  <span className="px-2 py-0.5 bg-gray-100 rounded text-gray-600">
                    耗时: {runResult.elapsed}s
                  </span>
                )}
                {runResult.run?.status && (
                  <span className="px-2 py-0.5 bg-emerald-100 rounded text-emerald-700">
                    {runResult.run.status}
                  </span>
                )}
              </div>
            )}
            {runResult.run && (
              <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-600 space-y-1">
                {runResult.run.id && <div>运行 ID: {runResult.run.id}</div>}
                {runResult.run.started_at && (
                  <div>开始: {formatDateTime(runResult.run.started_at)}</div>
                )}
              </div>
            )}
            {runResult.nodes?.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">节点执行情况</p>
                {runResult.nodes.map((n, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-xl border ${n.status === 'error' ? 'border-red-200 bg-red-50/60' : 'border-gray-200 bg-white'}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-gray-700">
                        {n.label || n.node_id}
                      </span>
                      {n.status === 'error' ? (
                        <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      )}
                    </div>
                    <p
                      className={`text-xs leading-relaxed ${n.status === 'error' ? 'text-red-600' : 'text-gray-600'}`}
                    >
                      {n.summary}
                    </p>
                  </div>
                ))}
              </div>
            )}
            {/* 图片生成结果直接预览 */}
            {(() => {
              const m =
                typeof runResult.result === 'string'
                  ? runResult.result.match(/\/api\/image-factory\/images\/[\w.-]+/)
                  : null
              return m ? (
                <img
                  src={m[0]}
                  alt="生成的图片"
                  className="rounded-lg border border-gray-200 w-full"
                />
              ) : null
            })()}
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 max-h-[50vh] overflow-y-auto">
              <MarkdownRenderer
                content={
                  typeof runResult.result === 'string'
                    ? runResult.result
                    : '```json\n' + JSON.stringify(runResult.result, null, 2) + '\n```'
                }
              />
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
