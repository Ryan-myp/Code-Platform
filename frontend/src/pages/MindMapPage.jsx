import React, { useState, useRef, useEffect } from 'react'
import {
  Sparkles,
  Download,
  Trash2,
  Clock,
  RefreshCw,
  Share2,
  Maximize2,
  Minimize2,
  PenLine,
  Check,
  FileText,
  X,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, SkeletonList, ErrorState } from '../components/ui'
import ShareButton from '../components/ShareButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import RandomPromptButton from '../components/RandomPromptButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'

const RANDOM_TOPICS = [
  '新能源汽车市场分析',
  'Python 后端工程师学习路线',
  '如何打造个人知识管理系统',
  '跨境电商运营全流程',
  '2026 年 AI 应用发展趋势',
  '家庭健康管理计划',
  '门店私域流量增长策略',
  '敏捷开发团队 Scrum 实践',
  '大学生职业规划路线图',
  '个人理财资产配置方案',
  '短视频账号冷启动计划',
  '智能家居产品需求分析',
]

// 配色主题：前端渲染覆色（不依赖后端节点自带色，一键全局换肤）
const COLOR_THEMES = [
  {
    id: 'classic',
    name: '经典多彩',
    colors: ['#667eea', '#4A90D9', '#6B8E23', '#E91E63', '#FF9800', '#9C27B0', '#00BCD4', '#FF5722'],
  },
  {
    id: 'fresh',
    name: '清新薄荷',
    colors: ['#10B981', '#34D399', '#22C55E', '#84CC16', '#0EA5E9', '#14B8A6', '#A3E635', '#16A34A'],
  },
  {
    id: 'warm',
    name: '暖阳橙红',
    colors: ['#F59E0B', '#F97316', '#EF4444', '#EAB308', '#FB923C', '#F43F5E', '#FBBF24', '#DC2626'],
  },
  {
    id: 'tech',
    name: '科技蓝紫',
    colors: ['#3B82F6', '#6366F1', '#06B6D4', '#8B5CF6', '#0EA5E9', '#4F46E5', '#22D3EE', '#7C3AED'],
  },
  {
    id: 'dark',
    name: '暗夜深邃',
    colors: ['#94A3B8', '#64748B', '#CBD5E1', '#475569', '#A78BFA', '#818CF8', '#93C5FD', '#C4B5FD'],
  },
]

const DEFAULT_PALETTE = COLOR_THEMES[0].colors

function MindMapCanvas({ data, width = 800, height = 600, palette = DEFAULT_PALETTE }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !data?.root) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, width, height)

    const cx = width / 2
    const cy = height / 2

    // 根节点
    drawNode(ctx, cx, cy, data.root.name, palette[0], 80)

    // 一级分支
    const branchCount = (data.root.children || []).length
    if (branchCount > 0) {
      const angleStep = (Math.PI * 2) / branchCount
      const radius = 160

      data.root.children.forEach((child, i) => {
        const angle = -Math.PI / 2 + i * angleStep
        const nx = cx + Math.cos(angle) * radius
        const ny = cy + Math.sin(angle) * radius
        const branchColor = palette[(i + 1) % palette.length]

        // 连线
        ctx.strokeStyle = branchColor
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(cx, cy + 30)
        ctx.quadraticCurveTo(cx, cy + 30 + radius * 0.4, nx, ny - 18)
        ctx.stroke()

        // 一级节点
        drawNode(ctx, nx, ny, child.name, branchColor, 60)

        // 二级节点
        const subChildren = child.children || []
        if (subChildren.length > 0) {
          const subRadius = 80
          const subAngleStep = Math.PI / Math.max(subChildren.length, 1)
          const baseAngle = angle - (subAngleStep * (subChildren.length - 1)) / 2

          subChildren.forEach((sub, j) => {
            const sa = baseAngle + j * subAngleStep
            const sx = nx + Math.cos(sa) * subRadius
            const sy = ny + Math.sin(sa) * subRadius

            ctx.strokeStyle = branchColor + '99'
            ctx.lineWidth = 1.5
            ctx.beginPath()
            ctx.moveTo(nx, ny + 18)
            ctx.quadraticCurveTo(nx, ny + 18 + subRadius * 0.5, sx, sy - 12)
            ctx.stroke()

            drawNode(ctx, sx, sy, sub.name, branchColor + '88', 44)

            // 三级节点
            const subSub = sub.children || []
            if (subSub.length > 0) {
              subSub.forEach((ss, k) => {
                const tRadius = 55
                const tAngle = sa + (k - (subSub.length - 1) / 2) * 0.3
                const tx = sx + Math.cos(tAngle) * tRadius
                const ty = sy + Math.sin(tAngle) * tRadius

                ctx.strokeStyle = branchColor + '44'
                ctx.lineWidth = 1
                ctx.beginPath()
                ctx.moveTo(sx, sy + 12)
                ctx.lineTo(tx, ty)
                ctx.stroke()

                drawNode(ctx, tx, ty, ss.name, branchColor + '33', 32, '#666')
              })
            }
          })
        }
      })
    }
  }, [data, width, height, palette])

  return <canvas ref={canvasRef} style={{ width, height }} className="rounded-xl" />
}

function drawNode(ctx, x, y, text, color, size, textColor = '#fff') {
  // 圆角矩形
  const w = Math.max(size, text.length * 14 + 20)
  const h = size * 0.55
  const r = h / 2

  ctx.fillStyle = color
  ctx.beginPath()
  ctx.moveTo(x - w / 2 + r, y - h / 2)
  ctx.lineTo(x + w / 2 - r, y - h / 2)
  ctx.arcTo(x + w / 2, y - h / 2, x + w / 2, y + h / 2, r)
  ctx.arcTo(x + w / 2, y + h / 2, x - w / 2, y + h / 2, r)
  ctx.arcTo(x - w / 2, y + h / 2, x - w / 2, y - h / 2, r)
  ctx.arcTo(x - w / 2, y - h / 2, x + w / 2, y - h / 2, r)
  ctx.closePath()
  ctx.fill()

  // 文字
  ctx.fillStyle = textColor
  ctx.font = `${Math.max(10, size * 0.18)}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, x, y)
}

export default function MindMapPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  const [topic, setTopic] = useState('')
  const [depth, setDepth] = useState(3)
  const [paletteKey, setPaletteKey] = useState('classic')
  const [task, setTask] = useState(null)
  const [result, setResult] = useState(null)
  const [records, setRecords] = useState([])
  const [recordsLoading, setRecordsLoading] = useState(true)
  const [recordsError, setRecordsError] = useState(null)
  const [fullscreen, setFullscreen] = useState(false)
  const [editingOutline, setEditingOutline] = useState(false)
  const [outlineDraft, setOutlineDraft] = useState('')
  const [applyingEdit, setApplyingEdit] = useState(false)

  useEffect(() => {
    loadRecords()
  }, [])

  const loadRecords = async () => {
    setRecordsLoading(true)
    setRecordsError(null)
    try {
      const res = await api.get('/api/mindmap/records')
      setRecords(res.data || [])
    } catch (e) {
      setRecordsError(e.message)
    } finally {
      setRecordsLoading(false)
    }
  }

  const generate = async () => {
    if (!topic.trim()) {
      toast.error('请输入主题')
      return
    }
    await submitTask(
      '/api/mindmap/generate',
      { topic: topic.trim(), depth, style: 'professional' },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setResult(data)
          setTask(null)
          loadRecords()
          toast.success('思维导图生成成功')
        },
        onError: (e) => {
          setTask(null)
          toast.error(`生成失败：${e.message}`)
        },
      }
    )
  }

  const exportPNG = () => {
    const canvas = document.querySelector('.mindmap-canvas canvas')
    if (!canvas) return
    const a = document.createElement('a')
    a.href = canvas.toDataURL('image/png')
    a.download = `mindmap-${Date.now()}.png`
    a.click()
    toast.success('已导出PNG')
  }

  // v15：节点批量编辑（树 ↔ Tab 缩进大纲，与后端 tree_to_outline 规则一致）
  const treeToOutline = (root) => {
    const lines = []
    const walk = (node, level) => {
      if (!node?.name) return
      lines.push('\t'.repeat(level) + node.name)
      ;(node.children || []).forEach((c) => walk(c, level + 1))
    }
    walk(root, 0)
    return lines.join('\n')
  }

  const startEditOutline = () => {
    if (!result?.root) return
    setOutlineDraft(treeToOutline(result.root))
    setEditingOutline(true)
  }

  const applyOutlineEdit = async () => {
    if (!outlineDraft.trim()) {
      toast.error('大纲不能为空')
      return
    }
    setApplyingEdit(true)
    try {
      const res = await api.post('/api/mindmap/apply-edit', { outline: outlineDraft })
      const tree = res.data.tree
      setResult((prev) => ({ ...prev, root: tree, title: tree.name }))
      setEditingOutline(false)
      toast.success('已应用大纲修改')
    } catch (e) {
      toast.error(e.message || '应用失败')
    } finally {
      setApplyingEdit(false)
    }
  }

  // v15：导出大纲 Markdown（本地生成，无需后端）
  const exportOutlineMD = () => {
    const root = result?.root
    if (!root) return
    const lines = [`# ${result.title || root.name || '思维导图'}`, '']
    const walk = (node, level) => {
      if (!node?.name || level === 0) return
      lines.push('  '.repeat(level - 1) + '- ' + node.name)
      ;(node.children || []).forEach((c) => walk(c, level + 1))
    }
    walk(root, 0)
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${result.title || root.name || 'mindmap'}-大纲.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 3000)
    toast.success('已导出大纲 MD')
  }

  const deleteRecord = async (id) => {
    try {
      await api.delete(`/api/mindmap/records/${id}`)
      loadRecords()
      toast.success('已删除')
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI思维导图"
        description="输入主题 → AI自动生成结构化思维导图，支持导出PNG图片"
        icon={Share2}
        iconColor="from-purple-500 to-violet-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：输入 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-500" /> 生成导图
              </span>
              <span className="flex items-center gap-3">
                <RandomPromptButton
                  prompts={RANDOM_TOPICS}
                  onPick={(t) => setTopic(t)}
                  className="text-purple-500 hover:text-purple-700 text-xs"
                />
                <EnhancePromptButton
                  text={topic}
                  onEnhance={(t) => setTopic(t)}
                  style="mindmap"
                  className="text-purple-600 hover:text-purple-700 text-xs"
                />
              </span>
            </h3>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="输入思维导图主题，如：新能源汽车市场分析、Python学习路线..."
              rows={3}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !task) {
                  e.preventDefault()
                  generate()
                }
              }}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none resize-none mb-3"
            />
            <div className="flex items-center gap-2 mb-3">
              <label className="text-xs text-gray-500">展开深度：</label>
              {[2, 3, 4].map((d) => (
                <button
                  key={d}
                  onClick={() => setDepth(d)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    depth === d
                      ? 'bg-purple-100 text-purple-700 border border-purple-300'
                      : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                  }`}
                >
                  {d}层
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5 mb-3 flex-wrap">
              <label className="text-xs text-gray-500 mr-1">配色：</label>
              {COLOR_THEMES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setPaletteKey(t.id)}
                  title={t.name}
                  className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] border transition-all ${
                    paletteKey === t.id
                      ? 'bg-purple-100 border-purple-300 text-purple-700 font-medium'
                      : 'bg-gray-50 border-gray-100 text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  <span className="flex gap-0.5">
                    {t.colors.slice(0, 3).map((c) => (
                      <span key={c} className="w-2 h-2 rounded-full" style={{ background: c }} />
                    ))}
                  </span>
                  {t.name}
                </button>
              ))}
            </div>
            <Button
              variant="primary"
              icon={Sparkles}
              loading={!!task}
              onClick={generate}
              className="w-full"
            >
              {task ? 'AI正在生成思维导图...' : '生成思维导图'}
            </Button>
            {task && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                  <span>{task.stage || 'AI 生成结构中…'}</span>
                  <span>{task.progress || 0}%</span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-violet-500 rounded-full transition-all duration-300"
                    style={{ width: `${task.progress || 0}%` }}
                  />
                </div>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 历史记录（{records.length}）
            </h3>
            {recordsLoading ? (
              <SkeletonList count={3} />
            ) : recordsError ? (
              <ErrorState message={`加载失败：${recordsError}`} onRetry={loadRecords} />
            ) : records.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无记录</div>
            ) : (
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {records.slice(0, 10).map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between p-2 rounded-lg bg-gray-50 text-xs"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-700 truncate">{r.topic}</div>
                      <div className="text-gray-400">
                        {r.depth}层 · {r.created_at?.slice(0, 10)}
                      </div>
                    </div>
                    <button
                      onClick={() => deleteRecord(r.id)}
                      className="p-1 text-gray-300 hover:text-red-500"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：导图展示 */}
        <div className={`${fullscreen ? 'lg:col-span-3' : 'lg:col-span-2'} space-y-4`}>
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900">
                {result ? result.title || result.topic : '预览'}
              </h3>
              {result && (
                <div className="flex items-center gap-1 flex-wrap">
                  <Button variant="secondary" size="sm" icon={Download} onClick={exportPNG}>
                    导出PNG
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={FileText}
                    onClick={exportOutlineMD}
                  >
                    大纲MD
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={PenLine}
                    onClick={startEditOutline}
                  >
                    编辑大纲
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={RefreshCw}
                    disabled={!!task}
                    onClick={generate}
                  >
                    重新生成
                  </Button>
                  <ShareButton
                    content={`# ${result.title || result.topic || '思维导图'}\n\n${result.description || ''}\n\n> 由小团智能平台 AI 思维导图生成 · ${new Date().toLocaleString()}`}
                    title={`思维导图：${result.title || result.topic}`}
                    contentType="mindmap"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={fullscreen ? Minimize2 : Maximize2}
                    onClick={() => setFullscreen(!fullscreen)}
                  />
                </div>
              )}
            </div>
            {!result ? (
              <Empty
                icon={Share2}
                title="等待生成"
                description="输入主题后点击生成，AI将创建思维导图"
              />
            ) : editingOutline ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>
                    批量编辑节点：Tab 缩进控制层级（首行为根节点），可直接增删改节点名
                  </span>
                  <span className="text-gray-400">缩进 → 层级；上一级 ← Shift+Tab</span>
                </div>
                <textarea
                  value={outlineDraft}
                  onChange={(e) => setOutlineDraft(e.target.value)}
                  rows={18}
                  spellCheck={false}
                  className="w-full px-3 py-2 font-mono text-xs border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
                />
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    icon={Check}
                    loading={applyingEdit}
                    onClick={applyOutlineEdit}
                  >
                    应用修改
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={X}
                    onClick={() => setEditingOutline(false)}
                  >
                    取消
                  </Button>
                </div>
              </div>
            ) : (
              <div
                className="mindmap-canvas flex items-center justify-center overflow-auto rounded-xl bg-gradient-to-br from-gray-50 to-purple-50/30 border border-gray-100"
                style={{ minHeight: 500 }}
              >
                <MindMapCanvas
                  data={{ root: result.root, title: result.title }}
                  width={fullscreen ? 1000 : 700}
                  height={fullscreen ? 650 : 500}
                  palette={COLOR_THEMES.find((t) => t.id === paletteKey)?.colors || DEFAULT_PALETTE}
                />
              </div>
            )}
            {result?.description && (
              <p className="mt-3 text-sm text-gray-500 text-center">{result.description}</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
