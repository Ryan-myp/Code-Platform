import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Plus, Trash2, Play, Save, Download,
  GitBranch, GitMerge, Code2, Globe,
  Zap, FileText, Clock,
  ZoomIn, ZoomOut, RefreshCw, ChevronLeft,
  Undo2, Redo2, X, Workflow,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDateTime } from '../lib/format'
import { Modal, Button, Empty, PageLoading, ErrorState, ConfirmDialog } from '../components/ui'

// 节点类型定义
const NODE_TYPES = {
  agent: { label: 'Agent', icon: GitBranch, color: 'purple', config: { agent_id: '' } },
  http: { label: 'HTTP 请求', icon: Globe, color: 'blue', config: { url: '', method: 'GET', headers: '{}' } },
  condition: { label: '条件判断', icon: GitMerge, color: 'orange', config: { expression: '' } },
  parallel: { label: '并行执行', icon: Zap, color: 'green', config: {} },
  code: { label: '代码执行', icon: Code2, color: 'gray', config: { code: '', language: 'python' } },
  delay: { label: '延迟等待', icon: Clock, color: 'yellow', config: { seconds: 1 } },
  output: { label: '输出节点', icon: FileText, color: 'pink', config: {} },
}

// 静态颜色映射（避免 Tailwing 动态类名被 purge）
const COLOR_STYLES = {
  purple: { header: 'bg-purple-500', ring: 'ring-purple-500', text: 'text-purple-600', light: 'bg-purple-50', border: 'border-purple-500' },
  blue: { header: 'bg-blue-500', ring: 'ring-blue-500', text: 'text-blue-600', light: 'bg-blue-50', border: 'border-blue-500' },
  orange: { header: 'bg-orange-500', ring: 'ring-orange-500', text: 'text-orange-600', light: 'bg-orange-50', border: 'border-orange-500' },
  green: { header: 'bg-green-500', ring: 'ring-green-500', text: 'text-green-600', light: 'bg-green-50', border: 'border-green-500' },
  gray: { header: 'bg-gray-500', ring: 'ring-gray-500', text: 'text-gray-600', light: 'bg-gray-50', border: 'border-gray-500' },
  yellow: { header: 'bg-yellow-500', ring: 'ring-yellow-500', text: 'text-yellow-600', light: 'bg-yellow-50', border: 'border-yellow-500' },
  pink: { header: 'bg-pink-500', ring: 'ring-pink-500', text: 'text-pink-600', light: 'bg-pink-50', border: 'border-pink-500' },
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
  const [deleteNodeTarget, setDeleteNodeTarget] = useState(null)

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
    if (pendingConnection && pendingConnection !== nodeId) {
      addEdge(pendingConnection, nodeId)
      setPendingConnection(null)
    } else {
      setSelectedNodeId(nodeId)
    }
  }

  const handleOutputHandleClick = (nodeId, e) => {
    e.stopPropagation()
    setPendingConnection(pendingConnection === nodeId ? null : nodeId)
    setSelectedNodeId(nodeId)
  }

  // 运行工作流
  const runWorkflow = async () => {
    if (!workflow) return
    setRunning(true)
    try {
      const res = await api.post(`/api/workflows/${workflow.id}/run`, { message: '执行工作流' })
      setRunResult(res.data)
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
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable
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
          onClick={() => { setZoom(1); setPosition({ x: 0, y: 0 }) }}
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
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={() => doSave({ manual: true })}>
            <span className="hidden sm:inline">保存</span>
          </Button>
          <Button variant="success" size="sm" icon={Play} loading={running} onClick={runWorkflow}>
            <span className="hidden sm:inline">执行</span>
          </Button>
        </div>

        {/* 画布 */}
        <div
          ref={canvasRef}
          className="flex-1 relative overflow-hidden bg-gray-50"
          style={{ cursor: pendingConnection ? 'crosshair' : isPanning ? 'grabbing' : dragging ? 'grabbing' : 'default' }}
          onMouseDown={(e) => {
            if (e.target === canvasRef.current || e.target.tagName === 'svg' || e.target.tagName === 'rect') {
              setIsPanning(true)
              setPanStart({ x: e.clientX, y: e.clientY })
              setSelectedNodeId(null)
              setPendingConnection(null)
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
            <svg className="absolute top-0 left-0" width="4000" height="4000" style={{ pointerEvents: 'none' }}>
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
                    <path
                      d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
                      fill="none"
                      stroke="#9ca3af"
                      strokeWidth="2"
                      className="hover:stroke-red-500"
                    />
                    <circle cx={(x1 + x2) / 2} cy={(y1 + y2) / 2} r="5" fill="white" stroke="#9ca3af" />
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
              return (
                <div
                  key={node.id}
                  className={`absolute select-none ${isSelected ? `z-20` : 'z-10'}`}
                  style={{ left: node.x, top: node.y, width: NODE_W }}
                  onMouseDown={(e) => handleMouseDown(node.id, e)}
                  onClick={(e) => handleNodeClick(node.id, e)}
                >
                  <div
                    className={`relative w-full bg-white rounded-xl shadow-md border-2 cursor-move transition-shadow ${
                      isSelected ? `${styles.border} ring-2 ${styles.ring}/30` : 'border-gray-200'
                    } ${isPendingFrom ? 'ring-2 ring-offset-1 ' + styles.ring : ''}`}
                    style={{ width: NODE_W }}
                  >
                    <div className={`px-2 py-1.5 rounded-t-lg flex items-center gap-1.5 ${styles.header}`}>
                      <NodeType className="w-3.5 h-3.5 text-white flex-shrink-0" />
                      <span className="text-[10px] text-white font-medium truncate">{cfg?.label}</span>
                    </div>
                    <div className="px-2 py-2 text-xs text-gray-800 text-center truncate">
                      {node.label}
                    </div>

                    {/* 输出连接点 */}
                    <button
                      onClick={(e) => handleOutputHandleClick(node.id, e)}
                      className={`absolute top-1/2 -right-2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-white transition-all hover:scale-125 ${
                        isPendingFrom ? styles.header + ' scale-125' : 'bg-gray-400'
                      }`}
                      title="点击后选择目标节点以连线"
                    />

                    {/* 删除按钮 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleteNodeTarget(node.id)
                      }}
                      className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
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
                description="从左侧节点栏点击添加节点，开始编排你的工作流"
              />
            </div>
          )}

          {/* 连线提示 */}
          {pendingConnection && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-purple-600 text-white text-xs rounded-full shadow-lg z-30">
              已选择起点，点击目标节点完成连线（Esc 取消）
            </div>
          )}

          {/* 快捷键提示 */}
          <div className="absolute bottom-3 right-3 px-2.5 py-1.5 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg text-[10px] text-gray-400 hidden md:block">
            拖拽节点移动 · 点击右侧圆点连线 · Del 删除 · Ctrl+Z 撤销
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
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Agent ID</label>
                <input
                  type="text"
                  value={selectedNodeData.config.agent_id || ''}
                  onChange={(e) => updateNodeConfig(selectedNodeData.id, 'agent_id', e.target.value)}
                  placeholder="输入 Agent ID"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                />
              </div>
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
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'method', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Headers (JSON)</label>
                  <textarea
                    value={selectedNodeData.config.headers || '{}'}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'headers', e.target.value)}
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
                  onChange={(e) => updateNodeConfig(selectedNodeData.id, 'expression', e.target.value)}
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
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'language', e.target.value)}
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
                  onChange={(e) => updateNodeConfig(selectedNodeData.id, 'seconds', parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                />
              </div>
            )}

            {selectedNodeData.type === 'parallel' && (
              <p className="text-xs text-gray-400">并行执行节点无需额外配置，所有下游分支将同时触发。</p>
            )}

            {selectedNodeData.type === 'output' && (
              <p className="text-xs text-gray-400">输出节点将上游结果作为工作流的最终输出。</p>
            )}
          </div>

          <div className="p-4 border-t border-gray-200">
            <Button variant="danger" icon={Trash2} className="w-full" onClick={() => setDeleteNodeTarget(selectedNodeData.id)}>
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
                {runResult.run.started_at && <div>开始: {formatDateTime(runResult.run.started_at)}</div>}
              </div>
            )}
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 max-h-[50vh] overflow-y-auto">
              <div className="prose-sm max-w-none [&_pre]:my-2 [&_pre]:p-3 [&_pre]:bg-gray-900 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre_code]:text-gray-100 [&_code]:px-1 [&_code]:rounded [&_code]:bg-gray-200">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {typeof runResult.result === 'string'
                    ? runResult.result
                    : '```json\n' + JSON.stringify(runResult.result, null, 2) + '\n```'}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
