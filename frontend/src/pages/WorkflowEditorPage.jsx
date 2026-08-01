import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { 
  Plus, Trash2, Play, Save, Download, Upload, 
  GitBranch, GitMerge, Code2, Database, Globe, 
  Settings, X, CheckCircle, AlertCircle, Loader,
  Move, Zap, FileText, Terminal, Clock, ChevronRight,
  Minus, ZoomIn, ZoomOut, RefreshCw
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

// 节点类型定义
const NODE_TYPES = {
  agent: { label: 'Agent', icon: GitBranch, color: 'purple', config: { agent_id: '' } },
  http: { label: 'HTTP 请求', icon: Globe, color: 'blue', config: { url: '', method: 'GET', headers: '{}' } },
  condition: { label: '条件判断', icon: GitMerge, color: 'orange', config: { expression: '' } },
  parallel: { label: '并行执行', icon: Zap, color: 'green', config: {} },
  code: { label: '代码执行', icon: Code2, color: 'gray', config: { code: '', language: 'python' } },
  delay: { label: '延迟等待', icon: Clock, color: 'yellow', config: { seconds: 1 } },
  output: { label: '输出节点', icon: FileText, color: 'pink', config: {} }
}

export default function WorkflowEditorPage({ workflowId, onBack }) {
  const [workflow, setWorkflow] = useState(null)
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [dragging, setDragging] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const canvasRef = useRef(null)

  // 加载工作流
  useEffect(() => {
    if (!workflowId) return
    const token = localStorage.getItem('token')
    axios.get(`${API_BASE}/api/workflows/${workflowId}`, {
      headers: { Authorization: `Bearer ${token}` }
    }).then(res => {
      setWorkflow(res.data)
      const data = typeof res.data.definition === 'string' 
        ? JSON.parse(res.data.definition) 
        : res.data.definition
      setNodes(data.nodes || [])
      setEdges(data.edges || [])
    })
  }, [workflowId])

  // 创建新节点
  const addNode = (type) => {
    const newNode = {
      id: `node_${Date.now()}`,
      type,
      label: `${NODE_TYPES[type].label} ${nodes.length + 1}`,
      x: 100 + Math.random() * 300,
      y: 100 + Math.random() * 200,
      config: { ...NODE_TYPES[type].config }
    }
    setNodes([...nodes, newNode])
    setSelectedNode(newNode.id)
  }

  // 删除节点
  const deleteNode = (nodeId) => {
    setNodes(nodes.filter(n => n.id !== nodeId))
    setEdges(edges.filter(e => e.from !== nodeId && e.to !== nodeId))
    if (selectedNode === nodeId) setSelectedNode(null)
  }

  // 更新节点位置
  const updateNodePosition = (nodeId, x, y) => {
    setNodes(nodes.map(n => n.id === nodeId ? { ...n, x, y } : n))
  }

  // 更新节点配置
  const updateNodeConfig = (nodeId, key, value) => {
    setNodes(nodes.map(n => 
      n.id === nodeId ? { ...n, config: { ...n.config, [key]: value } } : n
    ))
    if (selectedNode === nodeId) {
      setSelectedNode({ ...selectedNode, config: { ...selectedNode.config, [key]: value } })
    }
  }

  // 添加边
  const addEdge = (from, to) => {
    const exists = edges.some(e => e.from === from && e.to === to)
    if (!exists) {
      setEdges([...edges, { id: `edge_${from}_${to}`, from, to }])
    }
  }

  // 删除边
  const deleteEdge = (edgeId) => {
    setEdges(edges.filter(e => e.id !== edgeId))
  }

  // 保存工作流
  const saveWorkflow = async () => {
    if (!workflow) return
    const token = localStorage.getItem('token')
    const definition = { nodes, edges }
    await axios.put(`${API_BASE}/api/workflows/${workflow.id}`, {
      name: workflow.name,
      description: workflow.description,
      definition: JSON.stringify(definition)
    }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    alert('保存成功！')
  }

  // 执行工作流
  const runWorkflow = async () => {
    if (!workflow) return
    const token = localStorage.getItem('token')
    try {
      const res = await axios.post(`${API_BASE}/api/workflows/${workflow.id}/run`, {
        input: {}
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      alert(`执行完成！运行 ID: ${res.data.run_id}`)
    } catch (e) {
      alert('执行失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  // 导出工作流
  const exportWorkflow = () => {
    const data = { nodes, edges, version: '1.0' }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${workflow?.name || 'workflow'}.json`
    a.click()
  }

  // 节点选择
  const selectNode = (nodeId) => {
    setSelectedNode(nodes.find(n => n.id === nodeId) || null)
  }

  // 拖动节点
  const handleMouseDown = (nodeId, e) => {
    e.stopPropagation()
    setDragging(nodeId)
    setSelectedNode(nodeId)
  }

  const handleMouseMove = (e) => {
    if (dragging) {
      const canvas = canvasRef.current
      if (canvas) {
        const rect = canvas.getBoundingClientRect()
        const x = (e.clientX - rect.left - position.x) / zoom
        const y = (e.clientY - rect.top - position.y) / zoom
        updateNodePosition(dragging, x - 60, y - 30)
      }
    }
    if (isPanning) {
      const dx = e.clientX - panStart.x
      const dy = e.clientY - panStart.y
      setPosition({ x: position.x + dx, y: position.y + dy })
      setPanStart({ x: e.clientX, y: e.clientY })
    }
  }

  const handleMouseUp = () => {
    setDragging(null)
    setIsPanning(false)
  }

  if (!workflow) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="animate-spin w-8 h-8 text-purple-600" />
      </div>
    )
  }

  const selectedNodeData = nodes.find(n => n.id === selectedNode)

  return (
    <div className="flex h-full bg-gray-100">
      {/* 左侧工具栏 */}
      <div className="w-16 bg-white border-r border-gray-200 flex flex-col items-center py-4 gap-2">
        {Object.entries(NODE_TYPES).map(([type, config]) => {
          const Icon = config.icon
          return (
            <button
              key={type}
              onClick={() => addNode(type)}
              className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-600"
              title={`添加 ${config.label}`}
            >
              <Icon className="w-5 h-5" />
            </button>
          )
        })}
        
        <div className="flex-1" />
        
        <button
          onClick={() => setZoom(z => Math.max(0.5, z - 0.1))}
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-600"
        >
          <ZoomOut className="w-5 h-5" />
        </button>
        <button
          onClick={() => setZoom(z => Math.min(2, z + 0.1))}
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-600"
        >
          <ZoomIn className="w-5 h-5" />
        </button>
        <button
          onClick={() => { setZoom(1); setPosition({ x: 0, y: 0 }); }}
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-600"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* 中间画布 */}
      <div className="flex-1 flex flex-col">
        {/* 顶部工具栏 */}
        <div className="h-12 bg-white border-b border-gray-200 flex items-center px-4 gap-2">
          <button onClick={onBack} className="p-2 hover:bg-gray-100 rounded-lg">
            <ChevronRight className="w-5 h-5 rotate-180" />
          </button>
          
          <div className="flex-1">
            <input
              type="text"
              value={workflow.name}
              onChange={(e) => setWorkflow({ ...workflow, name: e.target.value })}
              className="font-semibold text-gray-900 bg-transparent border-none focus:outline-none"
            />
          </div>
          
          <button
            onClick={saveWorkflow}
            className="flex items-center gap-2 px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
          >
            <Save className="w-4 h-4" />
            <span>保存</span>
          </button>
          
          <button
            onClick={runWorkflow}
            className="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <Play className="w-4 h-4" />
            <span>执行</span>
          </button>
          
          <button
            onClick={exportWorkflow}
            className="flex items-center gap-2 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            <Download className="w-4 h-4" />
            <span>导出</span>
          </button>
        </div>

        {/* 画布 */}
        <div
          ref={canvasRef}
          className="flex-1 relative overflow-hidden"
          style={{ cursor: dragging ? 'grabbing' : 'grab' }}
          onMouseDown={(e) => {
            if (e.target === canvasRef.current) {
              setIsPanning(true)
              setPanStart({ x: e.clientX, y: e.clientY })
            }
          }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <div
            className="absolute"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${zoom})`,
              transformOrigin: '0 0'
            }}
          >
            {/* 网格背景 */}
            <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: 'none' }}>
              <defs>
                <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                  <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />
            </svg>

            {/* 边 */}
            {edges.map(edge => {
              const fromNode = nodes.find(n => n.id === edge.from)
              const toNode = nodes.find(n => n.id === edge.to)
              if (!fromNode || !toNode) return null
              
              const x1 = fromNode.x + 120
              const y1 = fromNode.y + 30
              const x2 = toNode.x
              const y2 = toNode.y + 30
              
              return (
                <g key={edge.id} onClick={() => deleteEdge(edge.id)}>
                  <line
                    x1={x1} y1={y1}
                    x2={x2} y2={y2}
                    stroke="#9ca3af"
                    strokeWidth="2"
                    strokeDasharray="5,5"
                    className="cursor-pointer hover:stroke-red-500"
                  />
                  <circle cx={(x1+x2)/2} cy={(y1+y2)/2} r="4" fill="white" stroke="#9ca3af" />
                </g>
              )
            })}

            {/* 节点 */}
            {nodes.map(node => {
              const NodeType = NODE_TYPES[node.type]?.icon || Code2
              const isSelected = selectedNode === node.id
              const config = NODE_TYPES[node.type]
              
              return (
                <div
                  key={node.id}
                  className={`absolute w-24 bg-white rounded-lg shadow-md border-2 cursor-move ${
                    isSelected ? 'border-purple-600' : 'border-gray-200'
                  }`}
                  style={{ left: node.x, top: node.y }}
                  onMouseDown={(e) => handleMouseDown(node.id, e)}
                  onClick={(e) => {
                    e.stopPropagation()
                    selectNode(node.id)
                  }}
                >
                  <div className={`p-2 rounded-t-lg bg-${config?.color || 'gray'}-500`}>
                    <NodeType className="w-4 h-4 text-white" />
                  </div>
                  <div className="p-2 text-xs text-gray-900 text-center truncate">
                    {node.label}
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteNode(node.id) }}
                    className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* 右侧属性面板 */}
      {selectedNodeData && (
        <div className="w-64 bg-white border-l border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">节点配置</h3>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">节点名称</label>
              <input
                type="text"
                value={selectedNodeData.label}
                onChange={(e) => {
                  setNodes(nodes.map(n => n.id === selectedNode ? { ...n, label: e.target.value } : n))
                  setSelectedNode({ ...selectedNodeData, label: e.target.value })
                }}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
              />
            </div>
            
            {selectedNodeData.type === 'agent' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Agent ID</label>
                <select
                  value={selectedNodeData.config.agent_id || ''}
                  onChange={(e) => updateNodeConfig(selectedNode.id, 'agent_id', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                >
                  <option value="">选择 Agent...</option>
                </select>
              </div>
            )}
            
            {selectedNodeData.type === 'http' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
                  <input
                    type="text"
                    value={selectedNodeData.config.url || ''}
                    onChange={(e) => updateNodeConfig(selectedNode.id, 'url', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">方法</label>
                  <select
                    value={selectedNodeData.config.method || 'GET'}
                    onChange={(e) => updateNodeConfig(selectedNode.id, 'method', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                </div>
              </>
            )}
            
            {selectedNodeData.type === 'condition' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">表达式</label>
                <textarea
                  value={selectedNodeData.config.expression || ''}
                  onChange={(e) => updateNodeConfig(selectedNode.id, 'expression', e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono"
                  placeholder="例如: ${input.status} == 'success'"
                />
              </div>
            )}
            
            {selectedNodeData.type === 'code' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">代码</label>
                <textarea
                  value={selectedNodeData.config.code || ''}
                  onChange={(e) => updateNodeConfig(selectedNode.id, 'code', e.target.value)}
                  rows={5}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono"
                />
              </div>
            )}
            
            {selectedNodeData.type === 'delay' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">延迟秒数</label>
                <input
                  type="number"
                  value={selectedNodeData.config.seconds || 1}
                  onChange={(e) => updateNodeConfig(selectedNode.id, 'seconds', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                />
              </div>
            )}
          </div>
          
          <div className="p-4 border-t border-gray-200">
            <button
              onClick={() => deleteNode(selectedNode)}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100"
            >
              <Trash2 className="w-4 h-4" />
              <span>删除节点</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
