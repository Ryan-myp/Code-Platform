import React, { useState, useEffect } from 'react'
import {
  Smartphone,
  Sparkles,
  FolderOpen,
  FileCode2,
  Braces,
  FileText,
  Paintbrush,
  Copy,
  Check,
  Download,
  Trash2,
  Eye,
  Rocket,
  FolderTree,
  Loader2,
  Plus,
  MonitorPlay,
  Maximize2,
  Code2,
  Smartphone as PhoneIcon,
  ClipboardCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Globe,
} from 'lucide-react'
import { Card, Button, Badge, Empty, PageHeader, Modal, Pagination,
} from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import { wxmlToHtml } from '../lib/wxml-preview'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'
import useToolHistory from '../hooks/useToolHistory'
import HistoryPanel from '../components/HistoryPanel'
import FavoriteButton from '../components/FavoriteButton'

const TEMPLATES = [
  {
    id: 'shop',
    name: '电商购物',
    icon: '🛍️',
    color: 'from-pink-500 to-rose-600',
    description: '商品列表 / 详情 / 购物车 / 结算',
  },
  {
    id: 'booking',
    name: '预约服务',
    icon: '📅',
    color: 'from-blue-500 to-cyan-600',
    description: '服务列表 / 预约表单 / 我的预约',
  },
  {
    id: 'showcase',
    name: '作品展示',
    icon: '🎨',
    color: 'from-violet-500 to-purple-600',
    description: '首页 / 作品集 / 关于我们',
  },
  {
    id: 'tool',
    name: '效率工具',
    icon: '🧰',
    color: 'from-amber-500 to-orange-600',
    description: '记事本 / 计算器 / 打卡',
  },
  {
    id: 'news',
    name: '资讯阅读',
    icon: '📰',
    color: 'from-emerald-500 to-green-600',
    description: '文章列表 / 详情 / 分类',
  },
  {
    id: 'survey',
    name: '问卷投票',
    icon: '📊',
    color: 'from-cyan-500 to-blue-600',
    description: '问卷列表 / 填写表单 / 结果统计',
  },
  {
    id: 'event',
    name: '活动报名',
    icon: '🎪',
    color: 'from-orange-500 to-red-600',
    description: '活动列表 / 详情报名 / 我的票券',
  },
  {
    id: 'market',
    name: '二手闲置',
    icon: '🔄',
    color: 'from-yellow-500 to-amber-600',
    description: '闲置列表 / 发布求购 / 宝贝详情',
  },
  {
    id: 'custom',
    name: '自定义',
    icon: '✨',
    color: 'from-gray-500 to-gray-700',
    description: '自由发挥，AI 自行设计页面结构',
  },
]

function fileIcon(path) {
  if (path.endsWith('.json')) return { Icon: Braces, color: 'text-amber-500' }
  if (path.endsWith('.wxml')) return { Icon: FileText, color: 'text-emerald-500' }
  if (path.endsWith('.wxss')) return { Icon: Paintbrush, color: 'text-pink-500' }
  return { Icon: FileCode2, color: 'text-blue-500' }
}

function fileTree(paths) {
  // 按目录层级生成树：{ name, type: 'dir'|'file', children?, path }
  const root = { name: '', type: 'dir', children: [], path: '' }
  paths.forEach((p) => {
    const parts = p.split('/')
    let node = root
    let acc = ''
    parts.forEach((part, i) => {
      acc = acc ? `${acc}/${part}` : part
      const isFile = i === parts.length - 1
      let child = node.children.find((c) => c.name === part)
      if (!child) {
        child = {
          name: part,
          type: isFile ? 'file' : 'dir',
          path: acc,
          children: isFile ? null : [],
        }
        node.children.push(child)
      }
      node = child
    })
  })
  return root.children
}

export default function MiniAppPage() {
  const toast = useToast()
  const [templates, setTemplates] = useState(TEMPLATES)
  const [draft, setDraft] = usePersistentToolState('miniapp_factory_draft_v1', {
    template: 'shop',
    name: '',
    requirement: '',
  })
  const [template, setTemplate] = useState(draft.template || 'shop')
  const [name, setName] = useState(draft.name || '')
  const [requirement, setRequirement] = useState(draft.requirement || '')
  const [generating, setGenerating] = useState(false)
  const [projects, setProjects] = useState([])
  const [viewing, setViewing] = useState(null) // {id,name,files}
  const [selectedFile, setSelectedFile] = useState('')
  const [copied, setCopied] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [guide, setGuide] = useState({ steps: [], note: '' })
  // 提审材料（v15）：app.json 字段核对 + 权限扫描 + 提审清单 md
  const [showReview, setShowReview] = useState(false)
  const [reviewData, setReviewData] = useState(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [viewMode, setViewMode] = useState('preview') // 'preview' | 'code'
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewPage, setPreviewPage] = useState('')
  // 异步任务进度（task_id + 轮询进度）
  const [genTask, setGenTask] = useState(null)
  const { submitTask } = useAsyncTask()
  const { history: genHistory, add: addGenHistory, remove: removeGenHistory, clear: clearGenHistory } =
    useToolHistory('miniapp_factory_history_v1', 30)

  useEffect(() => {
    loadProjects()
  }, [])
  useEffect(() => {
    api
      .get('/api/miniapp/templates')
      .then((res) => {
        if (res.data?.length) {
          const merged = TEMPLATES.map((t) => res.data.find((r) => r.id === t.id) || t)
          const extra = res.data
            .filter((r) => !TEMPLATES.some((t) => t.id === r.id))
            .map((r) => ({ ...r, color: 'from-gray-500 to-gray-700' }))
          setTemplates([...merged, ...extra])
        }
      })
      .catch(() => {})
  }, [])

  const loadProjects = async () => {
    try {
      const res = await api.get('/api/miniapp/projects')
      setProjects(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const buildPreview = (files) => {
    const result = wxmlToHtml(files, previewPage || undefined)
    setPreviewHtml(result.html)
    setPreviewPage(result.title)
  }

  const switchPreviewPage = (pagePath) => {
    if (!viewing) return
    setPreviewPage(pagePath)
    const result = wxmlToHtml(viewing.files, pagePath)
    setPreviewHtml(result.html)
    setSelectedFile(pagePath)
  }

  useEffect(() => {
    setDraft({ template, name, requirement })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template, name, requirement])

  const generate = async () => {
    if (!name.trim()) {
      toast.error('请输入项目名称')
      return
    }
    if (requirement.trim().length < 2) {
      toast.error('请描述你的功能需求')
      return
    }
    setGenerating(true)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    await submitTask(
      '/api/miniapp/generate',
      { name: name.trim(), template, requirement },
      {
        onUpdate: (t) => setGenTask(t),
        onSuccess: (data) => {
          const files = data.files || {}
          addGenHistory({ type: '小程序', name: name.trim(), template, content: requirement.trim().slice(0, 50) })
          setViewing({ id: data.id, name: data.name, files })
          setViewMode('preview')
          buildPreview(files)
          const wxmlFiles = Object.keys(files).filter((k) => k.endsWith('.wxml'))
          setSelectedFile(wxmlFiles[0] || '')
          loadProjects()
          setGenerating(false)
          toast.success(`生成成功：${data.file_count} 个文件`)
        },
        onError: (e) => {
          setGenerating(false)
          toast.error(`生成失败：${e.message}`)
        },
      }
    )
  }

  const openProject = async (p) => {
    try {
      const res = await api.get(`/api/miniapp/${p.id}`)
      const files = res.data.files || {}
      setViewing({ id: p.id, name: p.name, files })
      setViewMode('preview')
      buildPreview(files)
      const wxmlFiles = Object.keys(files).filter((k) => k.endsWith('.wxml'))
      setSelectedFile(wxmlFiles[0] || '')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const removeProject = async (p, e) => {
    e.stopPropagation()
    try {
      await api.delete(`/api/miniapp/${p.id}`)
      loadProjects()
      toast.success('项目已删除')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const downloadZip = async () => {
    if (!viewing) return
    try {
      const res = await api.get(`/api/miniapp/${viewing.id}/export-zip`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${viewing.name}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('发布包已下载（项目代码 + 介绍 + 审核清单 + 质量报告）')
    } catch (e) {
      toast.error(`下载失败：${e.message}`)
    }
  }

  // v22：服务端在线预览（wxml→html + Mock 数据注入 + 页面 Tab 切换）
  const [serverPreviewBusy, setServerPreviewBusy] = useState(false)
  const serverPreview = async () => {
    if (!viewing) return
    setServerPreviewBusy(true)
    try {
      const res = await api.get(`/api/miniapp/preview-html/${viewing.id}`)
      const url = res.data.url
      const win = window.open(`/miniapp-preview${url.replace('/api/miniapp/preview', '')}`, '_blank')
      if (!win) {
        // 弹窗被拦截时降级：直接打开
        window.location.href = `/miniapp-preview${url.replace('/api/miniapp/preview', '')}`
      }
      toast.success('服务端预览已生成（含 Mock 数据）')
    } catch (e) {
      toast.error(`预览生成失败：${e.message}`)
    } finally {
      setServerPreviewBusy(false)
    }
  }

  const copyFile = async () => {
    try {
      await navigator.clipboard.writeText(viewing.files[selectedFile] || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('复制失败')
    }
  }

  const loadGuide = async () => {
    try {
      const res = await api.get('/api/miniapp/deploy-guide')
      setGuide(res.data)
      setShowGuide(true)
    } catch (e) {
      toast.error(e.message)
    }
  }

  const loadReviewMaterial = async () => {
    if (!viewing) return
    setReviewLoading(true)
    try {
      const res = await api.get(`/api/miniapp/${viewing.id}/review-material`)
      setReviewData(res.data)
      setShowReview(true)
    } catch (e) {
      toast.error(`提审材料生成失败：${e.message}`)
    } finally {
      setReviewLoading(false)
    }
  }

  const downloadReviewMd = () => {
    if (!reviewData?.material) return
    const blob = new Blob([reviewData.material], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${reviewData.name || viewing?.name || 'miniapp'}-提审材料.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const tree = viewing ? fileTree(Object.keys(viewing.files)) : []
  const current = viewing?.files[selectedFile] || ''
  const tpl = templates.find((t) => t.id === template)
  const wxmlPages = viewing ? Object.keys(viewing.files).filter((k) => k.endsWith('.wxml')) : []

  return (
    <div className="space-y-6">
      <PageHeader
        title="小程序工坊"
        description="选模板 + 描述需求 → AI 生成完整微信小程序项目，在线预览、ZIP 导出、部署上线"
        icon={Smartphone}
        iconColor="from-indigo-500 to-violet-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── 左列：模板 + 生成 ── */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FolderTree className="w-4 h-4 text-indigo-500" /> 选择模板
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {templates.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTemplate(t.id)}
                  className={`flex flex-col items-center gap-1.5 px-2 py-3 rounded-xl border transition-all ${
                    template === t.id
                      ? 'bg-indigo-50 border-indigo-300 ring-2 ring-indigo-500/20'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <span
                    className={`w-9 h-9 rounded-lg bg-gradient-to-br ${t.color} flex items-center justify-center text-lg`}
                  >
                    {t.icon}
                  </span>
                  <span className="text-xs font-medium text-gray-700">{t.name}</span>
                </button>
              ))}
            </div>
            {tpl && <p className="mt-2 text-xs text-gray-400">{tpl.description}</p>}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" /> 生成配置
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">项目名称 *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="如：我的咖啡店小程序"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">功能需求 *</label>
                <textarea
                  value={requirement}
                  onChange={(e) => setRequirement(e.target.value)}
                  placeholder="描述你要做的功能，如：一个咖啡店点单小程序，展示菜单、支持加购物车、提交订单，要有会员积分功能…"
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                />
              </div>
              <Button
                variant="gradient"
                size="lg"
                icon={Smartphone}
                loading={generating}
                onClick={generate}
                className="w-full"
              >
                {generating ? '生成任务执行中（后台）…' : '生成小程序项目'}
              </Button>
              {genHistory.length > 0 && (
                <div className="mt-3">
                  <HistoryPanel
                    history={genHistory}
                    onReuse={(item) => {
                      if (item.name) setName(item.name)
                      if (item.requirement) setRequirement(item.requirement)
                      if (item.template) setTemplate(item.template)
                      toast.info('已恢复需求，可重新生成')
                    }}
                    onRemove={removeGenHistory}
                    onClear={clearGenHistory}
                    title="生成历史"
                  />
                </div>
              )}
              {generating && genTask && (
                <div className="rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2">
                  <div className="flex items-center gap-2 text-xs text-indigo-600">
                    <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                    <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                    <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-indigo-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-violet-600 rounded-full transition-all"
                      style={{ width: `${genTask.progress || 0}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                  </p>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <Rocket className="w-4 h-4 text-emerald-500" /> 三步上线
            </h3>
            <ol className="space-y-2 text-sm text-gray-600">
              <li className="flex gap-2">
                <span className="text-emerald-500 font-bold">1.</span> 选择模板 + 描述需求，AI
                生成完整项目
              </li>
              <li className="flex gap-2">
                <span className="text-emerald-500 font-bold">2.</span> 下载 ZIP →
                微信开发者工具「导入项目」
              </li>
              <li className="flex gap-2">
                <span className="text-emerald-500 font-bold">3.</span> 上传代码 → 提交审核 →
                发布上线
              </li>
            </ol>
            <Button
              variant="ghost"
              size="sm"
              icon={Rocket}
              onClick={loadGuide}
              className="mt-2 w-full justify-center"
            >
              查看详细部署指引
            </Button>
          </Card>
        </div>

        {/* ── 右列：我的项目 ── */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FolderTree className="w-4 h-4 text-gray-400" /> 我的项目（{projects.length}）
            </h3>
            {projects.length === 0 ? (
              <Empty
                icon={Smartphone}
                title="还没有小程序项目"
                description="选择模板、填写需求后点击「生成小程序项目」"
              />
            ) : (
              <Pagination
                items={projects}
                pageSize={8}
                label={`共 ${projects.length} 个项目`}
                renderItem={(p) => {
                  const t = templates.find((x) => x.id === p.template)
                  return (
                    <div
                      onClick={() => openProject(p)}
                      className="flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-indigo-200 hover:bg-indigo-50/30 transition-all cursor-pointer"
                    >
                      <div
                        className={`w-10 h-10 rounded-lg bg-gradient-to-br ${t?.color || 'from-gray-500 to-gray-700'} flex items-center justify-center text-lg flex-shrink-0`}
                      >
                        {t?.icon || '📱'}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">{p.name}</div>
                        <div className="text-xs text-gray-400 truncate">
                          {t?.name || p.template || '自定义'} · {p.requirement?.slice(0, 60)}
                        </div>
                      </div>
                      <span className="text-xs text-gray-400 flex-shrink-0">
                        {p.created_at?.slice(0, 16).replace('T', ' ')}
                      </span>
                      <span onClick={(e) => e.stopPropagation()}>
                        <FavoriteButton
                          favType="record"
                          targetId={p.id}
                          label={p.name}
                          className="!p-1.5"
                        />
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={Eye}
                        onClick={(e) => {
                          e.stopPropagation()
                          openProject(p)
                        }}
                      >
                        查看
                      </Button>
                      <span onClick={(e) => e.stopPropagation()}>
                        <ShareButton
                          content={`# 小程序：${p.name}\n\n需求：${p.requirement || ''}\n\n> 由小团智能平台 AI 小程序工坊生成 · ${new Date().toLocaleString()}`}
                          title={`小程序：${p.name}`}
                          contentType="miniapp"
                          className="!p-1.5"
                        />
                      </span>
                      <button
                        onClick={(e) => removeProject(p, e)}
                        className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )
                }}
              />
            )}
          </Card>

          {projects.length > 0 && (
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Rocket className="w-4 h-4 text-emerald-500" /> 快速上手提示
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm text-gray-600">
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                  <p className="font-medium text-emerald-700 mb-1">① 下载项目</p>
                  <p className="text-xs">在项目详情中点击「下载 ZIP」，得到完整项目代码</p>
                </div>
                <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                  <p className="font-medium text-blue-700 mb-1">② 导入开发者工具</p>
                  <p className="text-xs">微信开发者工具 → 导入项目 → 选择解压目录 → 编译预览</p>
                </div>
                <div className="p-3 rounded-lg bg-violet-50 border border-violet-100">
                  <p className="font-medium text-violet-700 mb-1">③ 发布上线</p>
                  <p className="text-xs">上传代码 → 提交审核 → 发布，个人主体即可注册</p>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ── 项目查看 Modal ── */}
      <Modal
        open={!!viewing}
        onClose={() => {
          setViewing(null)
          setViewMode('preview')
        }}
        title={viewing ? `项目：${viewing.name}` : ''}
        size="2xl"
        footer={
          <>
            <Button variant="secondary" icon={ClipboardCheck} loading={reviewLoading} onClick={loadReviewMaterial}>
              提审材料
            </Button>
            <Button variant="secondary" icon={Rocket} onClick={loadGuide}>
              部署指引
            </Button>
            <Button variant="secondary" icon={Globe} loading={serverPreviewBusy} onClick={serverPreview}>
              在线预览（服务端）
            </Button>
            <Button variant="secondary" icon={Download} onClick={downloadZip}>
              下载发布包
            </Button>
            <Button
              variant="primary"
              icon={Smartphone}
              onClick={() => {
                setViewing(null)
                toast.success('在微信开发者工具中导入解压后的目录即可运行')
              }}
            >
              完成
            </Button>
          </>
        }
      >
        {/* ── 模式切换 Tab ── */}
        <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-xl mb-4 w-fit">
          <button
            onClick={() => {
              setViewMode('preview')
              if (viewing) buildPreview(viewing.files)
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              viewMode === 'preview'
                ? 'bg-white text-indigo-700 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <MonitorPlay className="w-3.5 h-3.5" /> 可视化预览
          </button>
          <button
            onClick={() => setViewMode('code')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              viewMode === 'code'
                ? 'bg-white text-gray-700 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" /> 代码查看
          </button>
        </div>

        {/* ── 可视化预览模式 ── */}
        {viewMode === 'preview' && (
          <div className="flex flex-col gap-3">
            {/* 页面选择器 */}
            {wxmlPages.length > 1 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <PhoneIcon className="w-3 h-3" /> 页面切换：
                </span>
                {wxmlPages.map((p) => {
                  const label = p
                    .replace('pages/', '')
                    .replace('/index.wxml', '')
                    .replace('.wxml', '')
                  const isActive = previewPage === p
                  return (
                    <button
                      key={p}
                      onClick={() => switchPreviewPage(p)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                        isActive
                          ? 'bg-indigo-100 text-indigo-700'
                          : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }`}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>
            )}
            {/* 手机模拟框 */}
            <div className="flex justify-center bg-gray-100 rounded-2xl p-4">
              <div className="w-[375px] rounded-[36px] border-[6px] border-gray-800 bg-white shadow-2xl overflow-hidden">
                {/* 状态栏 */}
                <div className="h-7 bg-gray-800 flex items-center justify-between px-5 text-[10px] text-white">
                  <span>9:41</span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 border border-white rounded-sm" />
                    <span>▮▮▮▮</span>
                  </span>
                </div>
                <iframe
                  title="小程序预览"
                  srcDoc={previewHtml}
                  className="w-full bg-white"
                  style={{ height: '60vh', maxHeight: '600px', border: 'none' }}
                  sandbox="allow-scripts allow-same-origin"
                />
              </div>
            </div>
            <div className="flex items-center justify-center gap-2 text-xs text-gray-400">
              <MonitorPlay className="w-3 h-3" />
              以上为浏览器内自动转换的预览效果，实际效果以微信开发者工具为准
            </div>
          </div>
        )}

        {/* ── 代码查看模式 ── */}
        {viewMode === 'code' && (
          <div className="flex flex-col md:flex-row gap-4">
            {/* 文件树 */}
            <div className="md:w-64 flex-shrink-0 border border-gray-200 rounded-xl overflow-hidden max-h-[60vh] overflow-y-auto bg-gray-50/50">
              <div className="px-3 py-2 bg-gray-100/80 border-b border-gray-200 text-xs font-medium text-gray-500 flex items-center gap-1.5">
                <FolderTree className="w-3.5 h-3.5" /> {Object.keys(viewing?.files || {}).length}{' '}
                个文件
              </div>
              <div className="p-2 space-y-0.5">
                {tree.map((node) => (
                  <TreeNode
                    key={node.path}
                    node={node}
                    depth={0}
                    selected={selectedFile}
                    onSelect={setSelectedFile}
                  />
                ))}
              </div>
            </div>
            {/* 代码预览 */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700 truncate flex items-center gap-1.5">
                  {(() => {
                    const { Icon, color } = fileIcon(selectedFile)
                    return <Icon className={`w-4 h-4 ${color} flex-shrink-0`} />
                  })()}
                  {selectedFile}
                </span>
                <Button variant="ghost" size="sm" icon={copied ? Check : Copy} onClick={copyFile}>
                  {copied ? '已复制' : '复制'}
                </Button>
              </div>
              <pre className="bg-gray-900 text-gray-100 text-xs leading-relaxed p-4 rounded-xl overflow-auto max-h-[52vh] font-mono whitespace-pre">
                {current}
              </pre>
            </div>
          </div>
        )}
      </Modal>

      {/* ── 提审材料 Modal（v15）── */}
      <Modal
        open={showReview}
        onClose={() => setShowReview(false)}
        title={`提审材料：${reviewData?.name || viewing?.name || ''}`}
        size="lg"
        footer={
          <>
            <Button variant="secondary" icon={Download} onClick={downloadReviewMd}>
              下载提审材料.md
            </Button>
            <Button variant="primary" onClick={() => setShowReview(false)}>
              知道了
            </Button>
          </>
        }
      >
        {reviewData && (
          <div className="space-y-4">
            {/* 自检结论横幅 */}
            <div
              className={`flex items-start gap-2.5 px-3.5 py-3 rounded-xl border text-sm ${
                reviewData.ok
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : 'bg-red-50 border-red-200 text-red-800'
              }`}
            >
              {reviewData.ok ? (
                <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
              ) : (
                <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              )}
              <div>
                <p className="font-medium">
                  {reviewData.ok
                    ? '全部核对通过，可提交审核'
                    : `有 ${reviewData.checks.filter((c) => c.level === 'error').length} 项不通过，请先修复`}
                </p>
                <p className="text-xs opacity-80">基于 app.json 字段核对 + 代码权限扫描自动生成，最终以微信审核要求为准</p>
              </div>
            </div>

            {/* 核对项列表 */}
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-gray-500">核对清单（{reviewData.checks.length} 项）</p>
              {reviewData.checks.map((c, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 px-3 py-2 rounded-lg border border-gray-100 bg-gray-50/50 text-xs"
                >
                  {c.level === 'error' ? (
                    <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  ) : c.level === 'warn' ? (
                    <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                  )}
                  <div className="min-w-0">
                    <span className="font-medium text-gray-700">{c.item}</span>
                    <span className="text-gray-400">：{c.detail}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* 提审材料 Markdown 预览 */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1.5">提审材料 Markdown（可下载后补充完善）</p>
              <pre className="bg-gray-900 text-gray-100 text-xs leading-relaxed p-4 rounded-xl overflow-auto max-h-[36vh] font-mono whitespace-pre-wrap">
                {reviewData.material}
              </pre>
            </div>
          </div>
        )}
      </Modal>

      {/* ── 部署指引 Modal ── */}
      <Modal open={showGuide} onClose={() => setShowGuide(false)} title="小程序部署指引" size="lg">
        <div className="space-y-3">
          <ol className="space-y-2.5">
            {guide.steps.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-gray-700">
                <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
                  {i + 1}
                </span>
                <span className="pt-0.5">{s}</span>
              </li>
            ))}
          </ol>
          {guide.note && (
            <div className="px-3 py-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-start gap-2">
              <Rocket className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              {guide.note}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}

// 文件树节点（递归渲染）
/* eslint-disable react/prop-types -- 页内纯展示组件，与全站 props 校验风格一致 */
function TreeNode({ node, depth, selected, onSelect }) {
  if (node.type === 'dir') {
    return (
      <div>
        <div
          className="flex items-center gap-1.5 px-2 py-1 text-xs text-gray-500 font-medium"
          style={{ paddingLeft: 8 + depth * 14 }}
        >
          <FolderOpen className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" /> {node.name}
        </div>
        {node.children.map((c) => (
          <TreeNode
            key={c.path}
            node={c}
            depth={depth + 1}
            selected={selected}
            onSelect={onSelect}
          />
        ))}
      </div>
    )
  }
  const { Icon, color } = fileIcon(node.path)
  return (
    <button
      onClick={() => onSelect(node.path)}
      className={`w-full flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs transition-colors text-left ${
        selected === node.path
          ? 'bg-indigo-100 text-indigo-700 font-medium'
          : 'text-gray-600 hover:bg-gray-100'
      }`}
      style={{ paddingLeft: 8 + depth * 14 }}
    >
      <Icon className={`w-3.5 h-3.5 ${color} flex-shrink-0`} /> {node.name}
    </button>
  )
}
