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
  ZoomIn,
  ZoomOut,
  RefreshCw,
  ChevronLeft,
  Undo2,
  Redo2,
  X,
  Loader2,
  Workflow,
  Wrench,
  Database,
  Repeat,
  History,
  GitCommit,
  RotateCcw,
  PlayCircle,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import { api } from '../lib/api'
import { connectWs } from '../lib/ws'
import { useToast } from '../lib/toast'
import { formatDateTime } from '../lib/format'
import { Button, Empty, PageLoading, ErrorState, ConfirmDialog, Badge } from '../components/ui'
import ShareButton from '../components/ShareButton'

// 节点类型定义（与后端 workflows/executor.py 支持的节点一一对应）
const NODE_TYPES = {
  start: {
    label: '开始节点',
    icon: PlayCircle,
    color: 'green',
    desc: '工作流入口，定义输入参数（名称/默认值），下游可用 ${开始节点.result.字段} 引用',
    config: { fields: [] }, // fields: [{ name, label, default }]
  },
  agent: {
    label: 'Agent',
  desc: '调 LLM 处理一段指令，可引用上游节点结果',
    icon: GitBranch,
    color: 'purple',
    config: { agent_id: '', message: '' },
  },
  http: {
    label: 'HTTP 请求',
  desc: '请求 URL，抓取网页 / API 内容',
    icon: Globe,
    color: 'blue',
    config: { url: '', method: 'GET', headers: '{}' },
  },
  condition: { label: '条件判断', desc: '按表达式走 if_true / if_false 分支', icon: GitMerge, color: 'orange', config: { expression: '' } },
  parallel: { label: '并行执行', desc: '同时执行多个分支并汇合', icon: Zap, color: 'green', config: {} },
  code: { label: '代码执行', desc: '执行一段受限 Python 代码', icon: Code2, color: 'gray', config: { code: '', language: 'python' } },
  delay: { label: '延迟等待', desc: '等待 N 秒后继续', icon: Clock, color: 'yellow', config: { seconds: 1 } },
  image: {
    label: '图片生成',
  desc: '按提示词生成图片',
    icon: ImageIcon,
    color: 'pink',
    config: { prompt: '', size: '1024x1024', model: '' }, // model 留空 = 使用系统配置的图片模型
  },
  video: {
    label: '视频生成',
  desc: '按提示词生成视频',
    icon: Video,
    color: 'blue',
    config: { prompt: '', duration: 5, width: 1152, height: 768 },
  },
  music: {
    label: '音乐歌词',
  desc: '生成音乐 / 歌词',
    icon: Music,
    color: 'yellow',
    config: { theme: '', style: 'pop', language: 'zh', mood: 'happy' },
  },
  prd: {
    label: 'PRD 流程',
  desc: 'PRD → 技术方案 → 代码 三段式',
    icon: FileText,
    color: 'orange',
    config: { stage: 'generate', prd_text: '', tech_design: '', language: 'python' },
  },
  tool: {
    label: '平台工具',
  desc: '调用工具广场里的平台工具',
    icon: Wrench,
    color: 'teal',
    config: { tool_id: '', input: '' }, // tool_id：工具广场工具 id（如 code_interpreter）
  },
  loop: {
    label: '循环',
  desc: '对列表逐项执行内层节点，支持 until / 最大迭代',
    icon: Repeat,
    color: 'indigo',
    config: {
      items: '', // JSON 数组或 ${node_x.results} 引用；留空 = until 迭代模式
      body: 'agent', // 内层节点类型
      body_config: '{"message": "${loop_item}"}', // 内层节点配置（JSON，可引用 ${loop_item}/${loop_index}）
      until_key: '',
      until_value: '',
      max_iterations: 5,
    },
  },
  kb: {
    label: '知识库检索',
  desc: '从知识库检索相关内容',
    icon: Database,
    color: 'indigo',
    config: { kb_ids: [], query: '' },
  },
  output: { label: '结束节点', desc: '把上游结果作为最终输出', icon: FileText, color: 'pink', config: {} },
}

// 静态颜色映射（避免 Tailwing 动态类名被 purge）
// 注意：hoverBg 必须是完整类名字面量，否则 Tailwind 扫描不到不生效
const COLOR_STYLES = {
  purple: {
    header: 'bg-purple-500',
    ring: 'ring-purple-500',
    text: 'text-purple-600',
    light: 'bg-purple-50',
    border: 'border-purple-500',
    hoverBg: 'hover:bg-purple-50',
  },
  blue: {
    header: 'bg-blue-500',
    ring: 'ring-blue-500',
    text: 'text-blue-600',
    light: 'bg-blue-50',
    border: 'border-blue-500',
    hoverBg: 'hover:bg-blue-50',
  },
  orange: {
    header: 'bg-orange-500',
    ring: 'ring-orange-500',
    text: 'text-orange-600',
    light: 'bg-orange-50',
    border: 'border-orange-500',
    hoverBg: 'hover:bg-orange-50',
  },
  green: {
    header: 'bg-green-500',
    ring: 'ring-green-500',
    text: 'text-green-600',
    light: 'bg-green-50',
    border: 'border-green-500',
    hoverBg: 'hover:bg-green-50',
  },
  gray: {
    header: 'bg-gray-500',
    ring: 'ring-gray-500',
    text: 'text-gray-600',
    light: 'bg-gray-50',
    border: 'border-gray-500',
    hoverBg: 'hover:bg-gray-50',
  },
  yellow: {
    header: 'bg-yellow-500',
    ring: 'ring-yellow-500',
    text: 'text-yellow-600',
    light: 'bg-yellow-50',
    border: 'border-yellow-500',
    hoverBg: 'hover:bg-yellow-50',
  },
  pink: {
    header: 'bg-pink-500',
    ring: 'ring-pink-500',
    text: 'text-pink-600',
    light: 'bg-pink-50',
    border: 'border-pink-500',
    hoverBg: 'hover:bg-pink-50',
  },
  teal: {
    header: 'bg-teal-500',
    ring: 'ring-teal-500',
    text: 'text-teal-600',
    light: 'bg-teal-50',
    border: 'border-teal-500',
    hoverBg: 'hover:bg-teal-50',
  },
  indigo: {
    header: 'bg-indigo-500',
    ring: 'ring-indigo-500',
    text: 'text-indigo-600',
    light: 'bg-indigo-50',
    border: 'border-indigo-500',
    hoverBg: 'hover:bg-indigo-50',
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
  const [runInput, setRunInput] = useState('')
  const [startValues, setStartValues] = useState({}) // 开始节点字段 -> 值
  const [deleteNodeTarget, setDeleteNodeTarget] = useState(null)
  const [agents, setAgents] = useState([])

  // v17.x 内嵌执行控制台：替代原「弹窗输入 + 弹窗结果」，WS 实时节点状态
  const [rightTab, setRightTab] = useState('run')
  const [runStatus, setRunStatus] = useState('idle') // idle | running | done | error
  const [liveNodes, setLiveNodes] = useState({}) // node_id -> { status, result }
  const [inspectNode, setInspectNode] = useState(null) // 正在查看输入/输出的节点 id
  const [liveRunId, setLiveRunId] = useState(null) // 当前执行 run_id（WS 带出，用于拉节点快照）

  // 查看某节点的输入/输出：输出取 WS 实时结果，输入拉该 run 的节点快照（节点完成即落库，执行中也可查）
  const fetchInspectSnapshot = useCallback(
    async (nid) => {
      if (!liveRunId) return
      try {
        const res = await api.get(`/api/workflows/runs/${liveRunId}/snapshots`)
        const snap = (res.data?.nodes || []).find((s) => s.node_id === nid)
        if (snap) setInspectSnap(nid, snap)
      } catch {
        /* 快照尚未写入或 run 不存在，忽略 */
      }
    },
    [liveRunId]
  )
  const [inspectSnap, setInspectSnap] = useState({}) // node_id -> { input_data, output_data }
  const [openNodeCard, setOpenNodeCard] = useState(null) // 「节点执行情况」卡片中展开完整输出的节点
  const [nodeTip, setNodeTip] = useState(null) // 左侧节点工具栏 hover 提示 { label, desc, y }
  const openInspect = useCallback(
    (nid) => {
      setInspectNode(nid === inspectNode ? null : nid)
      if (nid === inspectNode) return
      fetchInspectSnapshot(nid)
    },
    [inspectNode, fetchInspectSnapshot]
  )
  const [showHistory, setShowHistory] = useState(false)
  const [historyTab, setHistoryTab] = useState('runs') // runs | versions
  const [runs, setRuns] = useState([])
  const [runsLoading, setRunsLoading] = useState(false)
  const [expandedRun, setExpandedRun] = useState(null) // run_id -> 展开看快照
  const [snapshots, setSnapshots] = useState({}) // run_id -> nodes[]
  const [resetNodes, setResetNodes] = useState({}) // run_id -> [node_id]（单节点回滚勾选）
  const [resumeBusy, setResumeBusy] = useState(null) // 正在续跑/重放的 run_id
  const [versions, setVersions] = useState([])
  const [restoreTarget, setRestoreTarget] = useState(null) // 待恢复的版本号

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

  // ── 运行历史 / 版本管理：加载与操作（放在 toastRef 与 loadWorkflow 定义之后，避免 TDZ）──
  const [runsError, setRunsError] = useState('')

  const loadRuns = useCallback(async () => {
    setRunsLoading(true)
    setRunsError('')
    try {
      const res = await api.get(`/api/workflows/${workflowId}/runs`, { params: { limit: 20 } })
      setRuns(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      setRuns([])
      setRunsError(e.message || '网络异常')
    } finally {
      setRunsLoading(false)
    }
  }, [workflowId])

  const loadVersions = useCallback(async () => {
    try {
      const res = await api.get(`/api/workflows/${workflowId}/versions`)
      setVersions(Array.isArray(res.data) ? res.data : [])
    } catch {
      setVersions([])
    }
  }, [workflowId])

  const openHistory = useCallback(() => {
    setShowHistory(true)
    loadRuns()
    loadVersions()
  }, [loadRuns, loadVersions])

  const openRunSnapshots = useCallback(
    async (runId) => {
      setExpandedRun((cur) => (cur === runId ? null : runId))
      if (!snapshots[runId]) {
        try {
          const res = await api.get(`/api/workflows/runs/${runId}/snapshots`)
          setSnapshots((prev) => ({ ...prev, [runId]: res.data?.nodes || [] }))
        } catch (e) {
          toastRef.current.error(`加载节点快照失败：${e.message}`)
        }
      }
    },
    [snapshots]
  )

  // 断点续跑（可选 reset_node：勾选的节点清快照重跑）
  const resumeRun = useCallback(
    async (run, resetList) => {
      setResumeBusy(run.id)
      try {
        const cfg = resetList?.length ? { params: { reset_node: resetList } } : {}
        const res = await api.post(`/api/workflows/runs/${run.id}/resume`, null, cfg)
        toastRef.current.success(
          `续跑完成：${res.data?.status || 'completed'}（复用快照 ${res.data?.resumed_nodes?.length || 0} 个节点，新 run ${res.data?.new_run}）`
        )
        setResetNodes({})
        setExpandedRun(null)
        loadRuns()
      } catch (e) {
        toastRef.current.error(`续跑失败：${e.message}`)
      } finally {
        setResumeBusy(null)
      }
    },
    [loadRuns]
  )

  // 输入重放：用原 run 的 input_data 重新跑
  const replayRun = useCallback(
    async (run) => {
      setResumeBusy(run.id)
      try {
        const res = await api.post(`/api/workflows/runs/${run.id}/replay`)
        toastRef.current.success(`重放完成：${res.data?.status || 'completed'}（新 run ${res.data?.new_run}）`)
        loadRuns()
      } catch (e) {
        toastRef.current.error(`重放失败：${e.message}`)
      } finally {
        setResumeBusy(null)
      }
    },
    [loadRuns]
  )

  const restoreVersion = useCallback(
    async (version) => {
      try {
        const res = await api.post(`/api/workflows/${workflowId}/versions/${version}/restore`)
        toastRef.current.success(`已恢复到版本 ${version}（当前状态已存档为版本 ${res.data?.saved_version}）`)
        setRestoreTarget(null)
        await loadWorkflow()
        loadVersions()
      } catch (e) {
        toastRef.current.error(`恢复失败：${e.message}`)
      }
    },
    [workflowId, loadWorkflow, loadVersions]
  )

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
    setRightTab('config')
  }

  const deleteNode = (nodeId) => {
    setNodes((prev) => prev.filter((n) => n.id !== nodeId))
    setEdges((prev) => prev.filter((e) => e.from !== nodeId && e.to !== nodeId))
    if (selectedNodeId === nodeId) setSelectedNodeId(null)
  }

  // 选中节点时自动切到右侧「节点配置」Tab
  useEffect(() => {
    if (selectedNodeId) setRightTab('config')
  }, [selectedNodeId])

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

  // 开始节点（定义了输入字段的）：执行台渲染对应表单
  const startNode = nodes.find((n) => n.type === 'start' && (n.config?.fields || []).length) || null
  const startFields = startNode?.config?.fields || []

  // 运行工作流（v17.x：内嵌控制台，非弹窗；执行期间 WS 实时推送节点完成事件）
  const runWorkflow = async () => {
    if (!workflow) return
    if (nodes.length === 0) {
      toast.error('请先在画布中添加节点')
      return
    }
    const hasStartValues = startFields.length > 0
    if (hasStartValues && !runInput.trim() && !Object.values(startValues).some((v) => String(v || '').trim())) {
      toast.error('请填写执行内容或开始节点输入')
      return
    }
    setRunning(true)
    setRunStatus('running')
    setRunResult(null)
    setLiveNodes({})
    setLiveRunId(null)
    setInspectNode(null)
    setInspectSnap({})
    setOpenNodeCard(null)
    setRightTab('run')
    try {
      const payload = { message: runInput.trim(), ...(hasStartValues ? startValues : {}) }
      const res = await api.post(`/api/workflows/${workflow.id}/run`, payload)
      setRunResult(res.data)
      setRunStatus('done')
    } catch (e) {
      setRunStatus('error')
      toast.error(`执行失败：${e.message}`)
    } finally {
      setRunning(false)
    }
  }

  // WS 订阅稳定频道 workflow-live:{workflow_id}：执行期间实时看到节点逐个完成
  useEffect(() => {
    if (!workflow) return undefined
    const unsubscribe = connectWs(`workflow-live:${workflow.id}`, {
      onMessage: (msg) => {
        const { event, data } = msg || {}
        if (event === 'node_completed' && data?.node_id) {
          setLiveNodes((prev) => ({
            ...prev,
            [data.node_id]: { status: data.status, result: data.result },
          }))
          if (data.run_id) setLiveRunId(data.run_id)
        }
      },
    })
    return unsubscribe
  }, [workflow?.id])

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
          const styles = COLOR_STYLES[cfg.color] || COLOR_STYLES.gray
          return (
            <button
              key={type}
              onClick={() => addNode(type)}
              onMouseEnter={(e) => {
                const r = e.currentTarget.getBoundingClientRect()
                setNodeTip({ label: cfg.label, desc: cfg.desc || '', y: r.top + r.height / 2 })
              }}
              onMouseLeave={() => setNodeTip(null)}
              className={`w-11 h-11 flex flex-col items-center justify-center rounded-xl border border-gray-200 ${styles.hoverBg} hover:border-current transition-all group relative`}
              aria-label={`添加 ${cfg.label}`}
            >
              <Icon className={`w-5 h-5 ${styles.text}`} />
            </button>
          )
        })}
        {/* 节点提示气泡（fixed 定位，避免被侧栏 overflow 裁剪） */}
        {nodeTip && (
          <div
            className="fixed z-50 pointer-events-none"
            style={{ left: 72, top: nodeTip.y - 24 }}
          >
            <div className="rounded-lg bg-gray-900 text-white text-xs px-3 py-2 shadow-lg w-56">
              <p className="font-medium">+ {nodeTip.label}</p>
              {nodeTip.desc && <p className="mt-0.5 text-gray-300 leading-snug">{nodeTip.desc}</p>}
            </div>
          </div>
        )}
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
            <span className="hidden sm:inline whitespace-nowrap">导出</span>
          </Button>
          <ShareButton
            content={JSON.stringify({ nodes, edges, version: '1.0', name: workflow?.name }, null, 2)}
            title={`工作流：${workflow?.name || '未命名'}`}
            contentType="workflow"
          />
          <Button
            variant="primary"
            size="sm"
            icon={Save}
            loading={saving}
            onClick={() => doSave({ manual: true })}
          >
            <span className="hidden sm:inline whitespace-nowrap">保存</span>
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={History}
            onClick={openHistory}
          >
            <span className="hidden sm:inline whitespace-nowrap">历史</span>
          </Button>
          <Button
            variant="success"
            size="sm"
            icon={Play}
            onClick={() => {
              setRightTab('run')
              runWorkflow()
            }}
          >
            <span className="hidden sm:inline whitespace-nowrap">执行</span>
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
              <div className="pointer-events-auto flex flex-col items-center gap-3">
                <Empty
                  icon={Workflow}
                  title="画布为空"
                  description="建议从「开始节点」拖入，再连 Agent / HTTP / 图片等节点，最后接「结束节点」"
                />
                <Button variant="primary" size="sm" icon={PlayCircle} onClick={() => addNode('start')}>
                  快速添加开始节点
                </Button>
              </div>
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

      <aside className="w-[400px] bg-white border-l border-gray-200 flex flex-col flex-shrink-0">
        {/* Tab 头：执行 | 节点配置 */}
        <div className="flex items-center border-b border-gray-200 shrink-0">
          <button
            onClick={() => setRightTab('run')}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              rightTab === 'run' ? 'border-emerald-500 text-emerald-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            执行
          </button>
          <button
            onClick={() => setRightTab('config')}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              rightTab === 'config' ? 'border-purple-500 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            节点配置
          </button>
          <span className="ml-auto flex items-center gap-1.5 pr-3 text-xs">
            {runStatus === 'running' && (
              <span className="flex items-center gap-1 text-emerald-600">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />执行中…
              </span>
            )}
            {runStatus === 'done' && runResult?.run?.status && (
              <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 whitespace-nowrap">
                {runResult.run.status}
                {runResult.elapsed != null && <span className="tabular-nums ml-1">{runResult.elapsed}s</span>}
              </span>
            )}
            {runStatus === 'error' && <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-600">失败</span>}
          </span>
        </div>

        {rightTab === 'run' ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {/* 实时节点状态（WS workflow-live 频道） */}
                {(runStatus === 'running' || Object.keys(liveNodes).length > 0) && nodes.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {nodes.map((n) => {
                      const lv = liveNodes[n.id]
                      const st = runStatus === 'done' ? (runResult?.nodes?.find((r) => r.node_id === n.id)?.status || lv?.status) : lv?.status
                      const label = n.label || n.name || n.id
                      const cls =
                        st === 'success'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : st === 'error' || st === 'failed'
                            ? 'bg-red-50 text-red-600 border-red-200'
                            : runStatus === 'running'
                              ? 'bg-sky-50 text-sky-600 border-sky-200'
                              : 'bg-gray-50 text-gray-400 border-gray-200'
                      const mark =
                        st === 'success' ? '✓' : st === 'error' || st === 'failed' ? '✕' : runStatus === 'running' ? '…' : '·'
                      const resultText = lv?.result && typeof lv.result === 'object' ? JSON.stringify(lv.result).slice(0, 160) : null
                      const active = inspectNode === n.id
                      return (
                        <button
                          key={n.id}
                          onClick={() => openInspect(n.id)}
                          title={
                            (st === 'success' || st === 'error' || st === 'failed'
                              ? (resultText || runResult?.nodes?.find((r) => r.node_id === n.id)?.summary || '')
                              : '点击查看详情') + '（点击查看输入/输出）'
                          }
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg border text-xs cursor-pointer transition-all ${cls} ${active ? 'ring-2 ring-purple-500/40 shadow-sm' : ''}`}
                        >
                          <span className="font-medium">{label}</span>
                          <span>{mark}</span>
                        </button>
                      )
                    })}
                  </div>
                )}

                {/* 节点输入/输出详情（点击上方 chip 展开） */}
                {inspectNode && (() => {
                  const nd = nodes.find((x) => x.id === inspectNode)
                  const lv = liveNodes[inspectNode]
                  const snap = inspectSnap[inspectNode]
                  const out = snap?.output_data ?? lv?.result
                  const inp = snap?.input_data
                  const fmt = (v, max = 2000) => {
                    const s = typeof v === 'string' ? v : JSON.stringify(v, null, 2)
                    return s?.length > max ? s.slice(0, max) + '\n…（已截断，完整内容见历史面板快照）' : s || '（空）'
                  }
                  return (
                    <div className="border border-purple-200 bg-purple-50/40 rounded-lg p-3 space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <p className="font-medium text-purple-700">
                          {nd?.label || inspectNode}（{nd?.type}）输入 / 输出
                        </p>
                        <button onClick={() => setInspectNode(null)} className="text-gray-400 hover:text-gray-600">✕</button>
                      </div>
                      <div>
                        <p className="text-gray-400 mb-1">输入</p>
                        <pre className="whitespace-pre-wrap break-all bg-white border border-gray-200 rounded-md p-2 max-h-40 overflow-y-auto text-gray-700">
                          {fmt(inp)}
                        </pre>
                      </div>
                      <div>
                        <p className="text-gray-400 mb-1">输出</p>
                        <pre className="whitespace-pre-wrap break-all bg-white border border-gray-200 rounded-md p-2 max-h-40 overflow-y-auto text-gray-700">
                          {fmt(out)}
                        </pre>
                      </div>
                    </div>
                  )
                })()}

                {/* 开始节点输入字段（若定义了） */}
                {startFields.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <p className="sm:col-span-2 text-xs text-gray-400 -mt-1">
                      开始节点（{startNode.label || startNode.id}）输入：
                    </p>
                    {startFields.map((f) => (
                      <div key={f.name} className="flex items-center gap-2">
                        <label className="text-xs text-gray-500 w-24 flex-shrink-0 truncate" title={f.label || f.name}>
                          {f.label || f.name}
                        </label>
                        <input
                          type="text"
                          value={startValues[f.name] ?? f.default ?? ''}
                          onChange={(e) => setStartValues((p) => ({ ...p, [f.name]: e.target.value }))}
                          placeholder={f.default ? `默认：${f.default}` : ''}
                          className="flex-1 px-2.5 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 outline-none min-w-0"
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* 执行输入 + 按钮 */}
                <div className="flex gap-2 items-start">
                  <textarea
                    value={runInput}
                    onChange={(e) => setRunInput(e.target.value)}
                    placeholder={
                      startFields.length > 0
                        ? '补充说明（可选），或留空仅用上方开始节点字段'
                        : '输入执行内容，如：帮我分析用户登录功能的需求...（Ctrl+Enter 快速执行）'
                    }
                    rows={2}
                    className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 resize-none"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault()
                        runWorkflow()
                      }
                    }}
                  />
                  <div className="flex flex-col gap-1.5 flex-shrink-0">
                    <Button variant="success" icon={Play} loading={running} onClick={runWorkflow}>
                      执行
                    </Button>
                    <button
                      onClick={() => {
                        setRunStatus('idle')
                        setLiveNodes({})
                        setLiveRunId(null)
                        setInspectNode(null)
                        setInspectSnap({})
                      }}
                      className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      关闭
                    </button>
                  </div>
                </div>

                {/* 最终结果 */}
                {runResult && (
                  <div className="space-y-2">
                    {runResult.nodes?.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-gray-500">节点执行情况</p>
                        {runResult.nodes.map((n, idx) => {
                          const raw = n.summary || ''
                          const isOpen = openNodeCard === n.node_id
                          return (
                            <div
                              key={idx}
                              className={`px-3 py-2 rounded-lg border text-xs cursor-pointer select-none ${n.status === 'error' ? 'border-red-200 bg-red-50/60 text-red-600' : 'border-gray-100 bg-gray-50 text-gray-600'}`}
                              onClick={() => setOpenNodeCard(isOpen ? null : n.node_id)}
                              title="点击查看/收起完整输出"
                            >
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-gray-700">{n.label || n.node_id}</span>
                                <span className={`ml-1 ${n.status === 'error' ? 'text-red-500' : 'text-emerald-600'}`}>▸</span>
                                <span className="truncate flex-1">{raw.length > 120 ? raw.slice(0, 120) + '…' : raw}</span>
                              </div>
                              {isOpen && (
                                <pre className="mt-2 whitespace-pre-wrap break-all bg-white border border-gray-100 rounded-md p-2 max-h-52 overflow-y-auto text-gray-700">
                                  {typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2)}
                                </pre>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {(() => {
                      const m =
                        typeof runResult.result === 'string'
                          ? runResult.result.match(/\/api\/image-factory\/images\/[\w.-]+/)
                          : null
                      return m ? (
                        <img src={m[0]} alt="生成的图片" className="rounded-lg border border-gray-200 w-full" />
                      ) : null
                    })()}
                    <div className="border border-gray-100 rounded-lg p-3 bg-gray-50">
                      {typeof runResult.result === 'string' && runResult.result.length > 300 && (
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs text-gray-500 flex-1">最终结果{runResult.elapsed != null && `（耗时 ${runResult.elapsed}s）`}</span>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(runResult.result)
                              toast.success('已复制最终结果')
                            }}
                            className="text-xs px-2 py-1 border border-gray-200 rounded-md text-gray-600 hover:bg-white transition-colors"
                          >
                            复制
                          </button>
                          <button
                            onClick={() => {
                              const blob = new Blob([runResult.result], { type: 'text/markdown' })
                              const url = URL.createObjectURL(blob)
                              const a = document.createElement('a')
                              a.href = url
                              a.download = `${workflow?.name || 'workflow'}-result.md`
                              a.click()
                              URL.revokeObjectURL(url)
                              toast.success('已下载 Markdown')
                            }}
                            className="text-xs px-2 py-1 border border-gray-200 rounded-md text-gray-600 hover:bg-white transition-colors"
                          >
                            下载 .md
                          </button>
                        </div>
                      )}
                      <div className="max-h-96 overflow-y-auto">
                      <MarkdownRenderer
                        content={
                          typeof runResult.result === 'string'
                            ? runResult.result
                            : '```json\n' + JSON.stringify(runResult.result, null, 2) + '\n```'
                        }
                      />
                      </div>
                    </div>
                  </div>
                )}
                {runStatus === 'error' && <p className="text-xs text-red-500">执行失败，请检查节点配置后重试</p>}
              </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {selectedNodeData ? (
            <>
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

            {selectedNodeData.type === 'start' && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-gray-500">输入参数</label>
                  <button
                    onClick={() => {
                      const cur = Array.isArray(selectedNodeData.config.fields)
                        ? selectedNodeData.config.fields
                        : []
                      updateNodeConfig(selectedNodeData.id, 'fields', [
                        ...cur,
                        { name: '', label: '', default: '' },
                      ])
                    }}
                    className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-700 transition-colors"
                  >
                    <Plus className="w-3 h-3" />
                    添加
                  </button>
                </div>
                {(Array.isArray(selectedNodeData.config.fields) ? selectedNodeData.config.fields : [])
                  .length === 0 && (
                    <p className="text-xs text-gray-400 mb-2">
                      未定义字段时，执行台默认只显示一条文本输入（message）
                    </p>
                  )}
                <div className="space-y-2">
                  {(Array.isArray(selectedNodeData.config.fields)
                    ? selectedNodeData.config.fields
                    : []
                  ).map((f, i) => (
                    <div key={i} className="border border-gray-100 rounded-lg p-2 space-y-1.5 bg-gray-50/60">
                      <div className="flex gap-1.5 items-center">
                        <input
                          type="text"
                          value={f.name || ''}
                          onChange={(e) => {
                            const arr = [...selectedNodeData.config.fields]
                            arr[i] = { ...arr[i], name: e.target.value }
                            updateNodeConfig(selectedNodeData.id, 'fields', arr)
                          }}
                          placeholder="字段名（英文，如 title）"
                          className="flex-1 px-2 py-1.5 border border-gray-200 rounded-md text-xs focus:ring-1 focus:ring-emerald-500/40 outline-none min-w-0"
                        />
                        <button
                          onClick={() => {
                            const arr = selectedNodeData.config.fields.filter((_, j) => j !== i)
                            updateNodeConfig(selectedNodeData.id, 'fields', arr)
                          }}
                          className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                          title="删除字段"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <input
                        type="text"
                        value={f.label || ''}
                        onChange={(e) => {
                          const arr = [...selectedNodeData.config.fields]
                          arr[i] = { ...arr[i], label: e.target.value }
                          updateNodeConfig(selectedNodeData.id, 'fields', arr)
                        }}
                        placeholder="显示名（可留空）"
                        className="w-full px-2 py-1.5 border border-gray-200 rounded-md text-xs focus:ring-1 focus:ring-emerald-500/40 outline-none"
                      />
                      <input
                        type="text"
                        value={f.default || ''}
                        onChange={(e) => {
                          const arr = [...selectedNodeData.config.fields]
                          arr[i] = { ...arr[i], default: e.target.value }
                          updateNodeConfig(selectedNodeData.id, 'fields', arr)
                        }}
                        placeholder="默认值（可留空）"
                        className="w-full px-2 py-1.5 border border-gray-200 rounded-md text-xs focus:ring-1 focus:ring-emerald-500/40 outline-none"
                      />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-2 leading-relaxed">
                  下游节点可用 <code className="text-emerald-600">${'{开始节点id.result.字段名}'}</code> 引用输入，如{' '}
                  <code className="text-emerald-600">${'{n_start.result.title}'}</code>
                </p>
              </div>
            )}

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

            {selectedNodeData.type === 'tool' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">工具 ID</label>
                  <input
                    type="text"
                    value={selectedNodeData.config.tool_id || ''}
                    onChange={(e) =>
                      updateNodeConfig(selectedNodeData.id, 'tool_id', e.target.value)
                    }
                    placeholder="如 code_interpreter / meeting-notes / csv-analyzer"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                  <p className="text-xs text-gray-400 mt-1">工具广场任意工具；计算类本地实算，生成类走平台引擎</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">工具输入</label>
                  <textarea
                    value={selectedNodeData.config.input ?? ''}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'input', e.target.value)}
                    rows={3}
                    placeholder="代码或任务描述；可引用上游结果 ${'{node_x.result}'}"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
              </>
            )}

            {selectedNodeData.type === 'kb' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">知识库 ID</label>
                  <input
                    type="text"
                    value={Array.isArray(selectedNodeData.config.kb_ids) ? selectedNodeData.config.kb_ids.join(',') : (selectedNodeData.config.kb_id || '')}
                    onChange={(e) =>
                      updateNodeConfig(
                        selectedNodeData.id,
                        'kb_ids',
                        e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                      )
                    }
                    placeholder="多个用逗号分隔，如 kb_xxx,kb_yyy"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">检索问题</label>
                  <textarea
                    value={selectedNodeData.config.query ?? ''}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'query', e.target.value)}
                    rows={2}
                    placeholder="检索 query；可引用上游结果 ${'{node_x.result}'}"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                  <p className="text-xs text-gray-400 mt-1">输出 = 命中的参考知识段（v2 打分 Top3），供下游 Agent 节点引用</p>
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

            {selectedNodeData.type === 'loop' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">循环项列表</label>
                  <textarea
                    value={selectedNodeData.config.items || ''}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'items', e.target.value)}
                    rows={3}
                    placeholder='JSON 数组如 ["a","b"]，或引用上游结果 ${"{node_x.results}"}；留空 = until 迭代模式'
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">内层节点类型</label>
                  <select
                    value={selectedNodeData.config.body || 'agent'}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'body', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  >
                    {[['agent', 'Agent'], ['http', 'HTTP'], ['code', '代码'], ['condition', '条件'], ['delay', '延迟'], ['image', '图片'], ['kb', '知识库'], ['tool', '工具']].map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">内层节点配置 (JSON)</label>
                  <textarea
                    value={selectedNodeData.config.body_config || ''}
                    onChange={(e) => updateNodeConfig(selectedNodeData.id, 'body_config', e.target.value)}
                    rows={3}
                    placeholder='{"message": "${loop_item} 的处理"}（可引用 ${loop_item}/${loop_index}）'
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">until 键</label>
                    <input
                      type="text"
                      value={selectedNodeData.config.until_key || ''}
                      onChange={(e) => updateNodeConfig(selectedNodeData.id, 'until_key', e.target.value)}
                      placeholder="可选"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">until 值</label>
                    <input
                      type="text"
                      value={selectedNodeData.config.until_value ?? ''}
                      onChange={(e) => updateNodeConfig(selectedNodeData.id, 'until_value', e.target.value)}
                      placeholder="如 done"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">最大迭代次数（硬顶 20）</label>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={selectedNodeData.config.max_iterations ?? 5}
                    onChange={(e) =>
                      updateNodeConfig(
                        selectedNodeData.id,
                        'max_iterations',
                        Math.max(1, Math.min(20, parseInt(e.target.value) || 5))
                      )
                    }
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                  />
                  <p className="text-xs text-gray-400 mt-1">单项失败不中断循环（输出 status=partial）；until 命中提前终止</p>
                </div>
              </>
            )}

            {selectedNodeData.type === 'parallel' && (
              <p className="text-xs text-gray-400">
                并行执行节点无需额外配置，所有下游分支将同时触发。
              </p>
            )}

            {selectedNodeData.type === 'output' && (
              <p className="text-xs text-gray-400">结束节点将上游结果作为工作流的最终输出。</p>
            )}

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
            </>
            ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-500 flex items-center gap-2">
                <GitBranch className="w-4 h-4" />
                选中画布上的节点即可编辑其配置
              </p>
              <p className="text-xs text-gray-400 leading-relaxed">
                提示：开始节点定义工作流输入参数；Agent 节点可引用上游结果 {'${上游节点id.result}'}
              </p>
            </div>
            )}
          </div>
        )}
      </aside>
      
      {/* 运行历史 / 版本管理抽屉 */}
      {showHistory && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/20" onClick={() => setShowHistory(false)}>
          <div
            className="w-full max-w-lg h-full bg-white shadow-xl flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-gray-200 flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => setShowHistory(false)}
                className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
              <div className="flex-1" />
              {[['runs', '运行历史', History], ['versions', '版本', GitCommit]].map(([tab, label, Icon]) => (
                <button
                  key={tab}
                  onClick={() => setHistoryTab(tab)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    historyTab === tab ? 'bg-purple-50 text-purple-700 font-medium' : 'text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {historyTab === 'runs' && (
                runsLoading ? (
                  <div className="py-10 text-center text-sm text-gray-400">加载中…</div>
                ) : runsError && runs.length === 0 ? (
                  <div className="py-10 text-center space-y-3">
                    <p className="text-sm text-red-500">加载失败：{runsError}</p>
                    <button
                      onClick={() => loadRuns()}
                      className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                    >
                      重试
                    </button>
                  </div>
                ) : runs.length === 0 ? (
                  <div className="py-10 text-center text-sm text-gray-400">暂无运行记录</div>
                ) : (
                  runs.map((run) => {
                    const isExp = expandedRun === run.id
                    const busy = resumeBusy === run.id
                    const checked = resetNodes[run.id] || []
                    return (
                      <div key={run.id} className="border border-gray-200 rounded-xl overflow-hidden">
                        <button
                          onClick={() => openRunSnapshots(run.id)}
                          className="w-full px-3 py-2.5 flex items-center gap-2 text-left hover:bg-gray-50 transition-colors"
                        >
                          <span
                            className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              run.status === 'running'
                                ? 'bg-amber-400 animate-pulse'
                                : run.node_failed > 0
                                  ? 'bg-red-500'
                                  : 'bg-emerald-500'
                            }`}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-gray-700 truncate">{run.id}</p>
                            <p className="text-[11px] text-gray-400">
                              {formatDateTime(run.started_at)}
                              {run.elapsed_seconds != null && ` · ${run.elapsed_seconds}s`}
                            </p>
                          </div>
                          <span className="text-[11px] text-gray-500 flex-shrink-0">
                            节点 {run.node_ok}/{run.node_total}
                          </span>
                          <Badge color={run.status === 'running' ? 'amber' : run.node_failed > 0 ? 'red' : 'green'}>
                            {run.status === 'running' ? '运行中' : run.node_failed > 0 ? '有失败' : '成功'}
                          </Badge>
                        </button>
                        {isExp && (
                          <div className="px-3 py-2.5 bg-gray-50/60 border-t border-gray-100 space-y-2.5">
                            {(snapshots[run.id] || []).map((sn) => {
                              const ok = sn.status === 'success'
                              const canCheck = ok && run.node_failed > 0
                              return (
                                <div key={sn.node_id} className="flex items-center gap-2 text-xs">
                                  {canCheck ? (
                                    <input
                                      type="checkbox"
                                      checked={checked.includes(sn.node_id)}
                                      onChange={(e) =>
                                        setResetNodes((p) => ({
                                          ...p,
                                          [run.id]: e.target.checked
                                            ? [...(p[run.id] || []), sn.node_id]
                                            : (p[run.id] || []).filter((x) => x !== sn.node_id),
                                        }))
                                      }
                                      className="accent-purple-600"
                                    />
                                  ) : (
                                    <span className="w-3.5" />
                                  )}
                                  <span
                                    className={`font-mono ${
                                      sn.status === 'success' ? 'text-emerald-600' : sn.status === 'skipped' ? 'text-gray-400' : 'text-red-500'
                                    }`}
                                  >
                                    {sn.node_id}
                                  </span>
                                  <Badge color={sn.status === 'success' ? 'green' : sn.status === 'skipped' ? 'gray' : 'red'}>
                                    {sn.status}
                                  </Badge>
                                  <span className="text-gray-400 truncate flex-1">
                                    {JSON.stringify(sn.output_data || '').slice(0, 80)}
                                  </span>
                                </div>
                              )
                            })}
                            {(snapshots[run.id] || []).length === 0 && (
                              <p className="text-xs text-gray-400">无节点快照</p>
                            )}
                            {run.node_failed > 0 && (
                              <div className="flex flex-wrap gap-1.5 pt-1 border-t border-gray-100">
                                <Button
                                  variant="success"
                                  size="sm"
                                  icon={RotateCcw}
                                  loading={busy}
                                  onClick={() => resumeRun(run, checked)}
                                >
                                  断点续跑{checked.length > 0 ? `（重跑 ${checked.length} 个节点）` : ''}
                                </Button>
                                <Button variant="secondary" size="sm" icon={Play} loading={busy} onClick={() => replayRun(run)}>
                                  输入重放
                                </Button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })
                )
              )}

              {historyTab === 'versions' && (
                versions.length === 0 ? (
                  <div className="py-10 text-center text-sm text-gray-400">暂无版本（每次保存自动存档，保留最近 20 版）</div>
                ) : (
                  versions.map((v) => (
                    <div key={v.version} className="border border-gray-200 rounded-xl px-3 py-2.5 flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-gray-700">
                          v{v.version} · {v.name}
                        </p>
                        <p className="text-[11px] text-gray-400">{formatDateTime(v.created_at)}</p>
                      </div>
                      <Button variant="ghost" size="sm" icon={RotateCcw} onClick={() => setRestoreTarget(v.version)}>
                        恢复
                      </Button>
                    </div>
                  ))
                )
              )}
            </div>
          </div>
        </div>
      )}

      {/* 版本恢复确认 */}
      <ConfirmDialog
        open={restoreTarget != null}
        onClose={() => setRestoreTarget(null)}
        onConfirm={() => restoreVersion(restoreTarget)}
        title={`恢复到版本 ${restoreTarget ?? ''}`}
        message="恢复后画布将替换为该版本的节点/连线（当前未保存的修改会丢失，但会自动存档为新版本可找回）。确定恢复？"
        confirmLabel="恢复"
      />

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

    </div>
  )
}
