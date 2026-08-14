import React, { useState, useEffect } from 'react'
import {
  Gamepad2,
  Sparkles,
  FolderTree,
  FileCode2,
  Braces,
  Paintbrush,
  Copy,
  Check,
  Download,
  Trash2,
  Eye,
  Rocket,
  Loader2,
  Play,
  Globe,
  Smartphone,
  Maximize2,
  MonitorPlay,
  Star,
  Pencil,
  Wand2,
  BarChart3,
  GitCommitHorizontal,
  Search,
  RefreshCw,
  BadgeCheck,
  X,
  Camera,
  Package,
  History,
  RotateCcw,
  GitCompare,
  ArrowRight,
} from 'lucide-react'
import { Card, Button, Badge, Empty, PageHeader, Modal, SkeletonList, Pagination,
} from '../components/ui'
import ShareButton from '../components/ShareButton'
import FavoriteButton from '../components/FavoriteButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import RandomPromptButton from '../components/RandomPromptButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'
import useToolHistory from '../hooks/useToolHistory'
import HistoryPanel from '../components/HistoryPanel'

const RANDOM_REQUIREMENTS = [
  '加入道具系统，吃金色苹果可以加速，每 50 分关卡加速一次',
  '吃到红色果实后身体变短但得分翻倍，效果限时 10 秒',
  '双人同屏对战模式，双方各控制一条蛇，先撞墙或咬到自己者输',
  '加入金币收集与商店系统，可用金币购买不同皮肤',
  '每过 5 关增加新的障碍物类型，如移动墙、传送门',
  '支持键盘 WASD 与方向键双操作方式',
  '策略塔防：3 种炮塔（箭/炮/冰），5 波敌人，波间可升级炮塔',
  '回合制战斗：勇士 vs 史莱姆，3 个技能（重击/治疗/防御），3 连战出首领',
  '卡牌对战：10 张卡牌库，能量上限 3，击败 AI 对手',
  '五子棋：AI 分简单/困难两档，支持悔棋',
  '放置经营：4 种设施可升级，离线收益 50%，累计收入成就',
  '答题闯关：15 题常识题库，3 条命，每题限时 15 秒',
  '合并玩法：合成 3 个同等级水果升级，2048 式操作手感',
  '跑酷跳跃：自动奔跑 + 二段跳 + 障碍物 + 金币收集，吃满100分变身',
  '消除三消：5 种宝石，连击奖励，限时 60 秒闯关',
  '射击防御：左右移动 + 子弹发射，防守 3 波外星入侵',
  '音乐节奏：跟着节拍点击，判定 GOOD/PERFECT，谱面 3 档难度',
  '物理弹球：击碎方块 + 道具（加宽/多球/激光），20 关',
  '拼图闯关：3×3 至 5×5 难度递进，步数计数 + 计时挑战',
  '迷宫寻宝：随机迷宫 + 小地图 + 宝箱 3 个，出口通关',
  '种田养成：种菜/浇水/收获循环，天气系统，金币扩地',
  '贪吃蛇进化：吃同色方块进化形态，碰撞判定随体积变化',
  '记忆翻牌：4×4 卡牌，限时 + 步数双挑战，连击加分',
]

const TEMPLATES = [
  {
    id: 'snake',
    name: '贪吃蛇',
    icon: '🐍',
    color: 'from-emerald-500 to-green-600',
    category: '休闲',
    description: '吃食物变长，撞墙/撞自己结束',
  },
  {
    id: '2048',
    name: '2048',
    icon: '🔢',
    color: 'from-amber-500 to-orange-600',
    category: '休闲',
    description: '滑动合并数字，合成 2048',
  },
  {
    id: 'plane',
    name: '飞机大战',
    icon: '✈️',
    color: 'from-blue-500 to-indigo-600',
    category: '休闲',
    description: '躲避敌机，射击得分升级',
  },
  {
    id: 'brick',
    name: '打砖块',
    icon: '🧱',
    color: 'from-red-500 to-rose-600',
    category: '休闲',
    description: '挡板反弹小球，清空砖块',
  },
  {
    id: 'memory',
    name: '记忆翻牌',
    icon: '🃏',
    color: 'from-violet-500 to-purple-600',
    category: '休闲',
    description: '翻牌配对，步数越少越好',
  },
  {
    id: 'tetris',
    name: '俄罗斯方块',
    icon: '🧩',
    color: 'from-cyan-500 to-teal-600',
    category: '休闲',
    description: '旋转堆叠，满行消除',
  },
  {
    id: 'match3',
    name: '三消消乐',
    icon: '🍬',
    color: 'from-pink-500 to-rose-600',
    category: '休闲',
    description: '交换消除，连锁加分',
  },
  {
    id: 'minesweeper',
    name: '扫雷',
    icon: '💣',
    color: 'from-lime-500 to-green-600',
    category: '益智',
    description: '推理翻格，零失误过关',
  },
  {
    id: 'quiz',
    name: '答题闯关',
    icon: '🧠',
    color: 'from-yellow-500 to-amber-600',
    category: '益智',
    description: '多类型题库限时闯关',
  },
  {
    id: 'tower-defense',
    name: '策略塔防',
    icon: '🏰',
    color: 'from-orange-500 to-amber-600',
    category: '策略',
    description: '布塔防守升级，抵御波次进攻',
  },
  {
    id: 'turn-rpg',
    name: '回合制RPG',
    icon: '🧙',
    color: 'from-purple-500 to-indigo-600',
    category: '回合制',
    description: '技能抉择，击败首领闯关',
  },
  {
    id: 'card-battle',
    name: '回合制卡牌',
    icon: '🎴',
    color: 'from-rose-500 to-pink-600',
    category: '回合制',
    description: '抽卡出牌，能量管理对战',
  },
  {
    id: 'gomoku',
    name: '五子棋',
    icon: '⚫',
    color: 'from-slate-500 to-gray-700',
    category: '回合制',
    description: '与 AI 对弈，三档难度',
  },
  {
    id: 'idle-manager',
    name: '放置经营',
    icon: '🏪',
    color: 'from-teal-500 to-emerald-600',
    category: '模拟',
    description: '开店自动赚钱，离线收益',
  },
  {
    id: 'custom',
    name: '自定义',
    icon: '✨',
    color: 'from-gray-500 to-gray-700',
    category: '自定义',
    description: '自由描述玩法，AI 设计实现',
  },
]

// 模板分类展示顺序
const TEMPLATE_CATEGORIES = ['休闲', '益智', '策略', '回合制', '模拟', '自定义']

const VERSION_META = {
  web: { label: '网页版', icon: Globe, color: 'green', desc: '浏览器直接玩，可在线试玩' },
  wx: { label: '微信小游戏版', icon: Smartphone, color: 'blue', desc: '开发者工具导入运行' },
}

// v15：两版本逐文件变更行数对比（前后缀对齐近似 diff，仅展示用）
function lineDiffStats(a, b) {
  const A = String(a || '').split('\n')
  const B = String(b || '').split('\n')
  let i = 0
  while (i < A.length && i < B.length && A[i] === B[i]) i++
  let j = 0
  while (j < A.length - i && j < B.length - i && A[A.length - 1 - j] === B[B.length - 1 - j]) j++
  return { added: B.length - i - j, removed: A.length - i - j }
}

/* eslint-disable react/prop-types -- 页内纯展示组件，与全站 props 校验风格一致 */
function VersionDiffTable({ fromFiles, toFiles }) {
  const flat = (files) => {
    const out = {}
    Object.entries(files || {}).forEach(([ver, paths]) => {
      Object.entries(paths || {}).forEach(([p, content]) => {
        out[`${ver}/${p}`] = String(content)
      })
    })
    return out
  }
  const from = flat(fromFiles)
  const to = flat(toFiles)
  const paths = [...new Set([...Object.keys(from), ...Object.keys(to)])].sort()
  const rows = paths
    .map((p) => ({ p, ...lineDiffStats(from[p], to[p]) }))
    .filter((r) => r.added > 0 || r.removed > 0 || !from[r.p] || !to[r.p])
  if (rows.length === 0) {
    return <div className="text-xs text-gray-400 py-2">两个版本内容完全一致，无变更</div>
  }
  return (
    <div className="rounded-lg border border-gray-100 overflow-hidden">
      <div className="grid grid-cols-[1fr_auto_auto] gap-2 px-3 py-1.5 bg-gray-50 text-[10px] font-medium text-gray-400 border-b border-gray-100">
        <span>文件</span>
        <span className="w-9 text-right">新增</span>
        <span className="w-9 text-right">删除</span>
      </div>
      {rows.map((r) => (
        <div
          key={r.p}
          className="grid grid-cols-[1fr_auto_auto] gap-2 px-3 py-1.5 text-[11px] font-mono border-b border-gray-50 last:border-0"
        >
          <span className="text-gray-600 truncate">
            {r.p}
            {!from[r.p] && <span className="ml-1.5 text-[9px] px-1 py-0.5 rounded bg-emerald-50 text-emerald-600">新增文件</span>}
            {!to[r.p] && <span className="ml-1.5 text-[9px] px-1 py-0.5 rounded bg-red-50 text-red-500">已删除</span>}
          </span>
          <span className={`w-9 text-right ${r.added > 0 ? 'text-emerald-600' : 'text-gray-300'}`}>+{r.added}</span>
          <span className={`w-9 text-right ${r.removed > 0 ? 'text-red-500' : 'text-gray-300'}`}>-{r.removed}</span>
        </div>
      ))}
    </div>
  )
}

function fileIcon(path) {
  if (path.endsWith('.json')) return { Icon: Braces, color: 'text-amber-500' }
  if (path.endsWith('.html')) return { Icon: Paintbrush, color: 'text-pink-500' }
  if (path.endsWith('.css')) return { Icon: Paintbrush, color: 'text-sky-500' }
  return { Icon: FileCode2, color: 'text-blue-500' }
}

export default function GameFactoryPage() {
  const toast = useToast()
  const { history: genHistory, add: addGenHistory, remove: removeGenHistory, clear: clearGenHistory } =
    useToolHistory('game_factory_history_v1', 30)
  const [templates, setTemplates] = useState(TEMPLATES)
  // 输入态持久化：刷新/误关不丢草稿
  const [draft, setDraft] = usePersistentToolState('game_factory_draft_v1', {
    template: 'snake',
    name: '',
    requirement: '',
  })
  const [template, setTemplate] = useState(draft.template || 'snake')
  const [name, setName] = useState(draft.name || '')
  const [requirement, setRequirement] = useState(draft.requirement || '')
  const [generating, setGenerating] = useState(false)
  const [projects, setProjects] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [viewing, setViewing] = useState(null) // {id,name,files,versions}
  const [version, setVersion] = useState('web')
  const [selectedFile, setSelectedFile] = useState('')
  const [copied, setCopied] = useState(false)
  const [playing, setPlaying] = useState(null) // {id,name,html}
  const [showGuide, setShowGuide] = useState(false)
  const [guide, setGuide] = useState({ steps: [], note: '' })
  // 资产化管理：搜索/收藏筛选/重命名/迭代
  const [q, setQ] = useState('')
  const [onlyFav, setOnlyFav] = useState(false)
  const [renaming, setRenaming] = useState(null) // {id, name}
  const [renameName, setRenameName] = useState('')
  const [evolveReq, setEvolveReq] = useState('')
  const [evolving, setEvolving] = useState(false)
  // 异步任务进度（task_id + 轮询进度）
  const [genTask, setGenTask] = useState(null)
  const { submitTask } = useAsyncTask()

  useEffect(() => {
    loadProjects()
  }, [])
  useEffect(() => {
    api
      .get('/api/games/templates')
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
    setLoading(true)
    try {
      const res = await api.get('/api/games/projects')
      setProjects(res.data || [])
      api
        .get('/api/games/stats')
        .then((r) => setStats(r.data))
        .catch(() => {})
    } catch (e) {
      toast.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  const filteredProjects = projects.filter((p) => {
    if (onlyFav && !p.favorite) return false
    if (
      q &&
      !(
        p.name.toLowerCase().includes(q.toLowerCase()) ||
        (p.requirement || '').toLowerCase().includes(q.toLowerCase())
      )
    )
      return false
    return true
  })

  // 自动保存草稿
  useEffect(() => {
    setDraft({ template, name, requirement })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template, name, requirement])

  const generate = async () => {
    if (!name.trim()) {
      toast.error('请输入游戏名称')
      return
    }
    if (requirement.trim().length < 2) {
      toast.error('请描述你的玩法需求')
      return
    }
    setGenerating(true)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    await submitTask(
      '/api/games/generate',
      { name: name.trim(), template, requirement },
      {
        onUpdate: (t) => setGenTask(t),
        onSuccess: (data) => {
          setViewing({
            id: data.id,
            name: data.name,
            files: data.files,
            versions: data.versions || Object.keys(data.files || {}),
            qc: data.qc,
          })
          const firstVer = (data.versions || Object.keys(data.files || {}))[0] || 'web'
          setVersion(firstVer)
          const firstFile = Object.keys((data.files || {})[firstVer] || {})[0] || ''
          setSelectedFile(firstFile)
          loadProjects()
          addGenHistory({ type: '小游戏', name: name.trim(), template, requirement, content: requirement.trim() })
          setGenerating(false)
          toast.success(
            `生成成功：${data.versions?.length || 1} 个版本，${data.file_count} 个文件${data.qc?.ok ? ' · 商用 QC 全通过' : ''}`
          )
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
      const res = await api.get(`/api/games/${p.id}`)
      const files = res.data.files || {}
      const versions = Object.keys(files)
      setViewing({ id: p.id, name: p.name, files, versions, qc: res.data.qc })
      const firstVer = versions[0] || 'web'
      setVersion(firstVer)
      setSelectedFile(Object.keys(files[firstVer] || {})[0] || '')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const switchVersion = (v) => {
    setVersion(v)
    setSelectedFile(Object.keys((viewing?.files || {})[v] || {})[0] || '')
  }

  const playGame = async (p) => {
    try {
      const res = await api.get(`/api/games/${p.id}`)
      const files = res.data.files || {}
      const html = files.web?.['index.html']
      if (!html) {
        toast.error('网页版文件缺失，无法试玩')
        return
      }
      setPlaying({ id: p.id, name: p.name, html })
    } catch (e) {
      toast.error(e.message)
    }
  }

  const removeProject = async (p, e) => {
    e.stopPropagation()
    try {
      await api.delete(`/api/games/${p.id}`)
      loadProjects()
      toast.success('游戏已删除')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const toggleFav = async (p, e) => {
    e.stopPropagation()
    try {
      const res = await api.post(`/api/games/${p.id}/favorite`)
      loadProjects()
      toast.success(res.data.favorite ? '已收藏' : '已取消收藏')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const openRename = (p, e) => {
    e.stopPropagation()
    setRenaming({ id: p.id, name: p.name })
    setRenameName(p.name)
  }

  const submitRename = async () => {
    if (!renameName.trim()) {
      toast.error('请输入新名称')
      return
    }
    try {
      await api.put(`/api/games/${renaming.id}`, { name: renameName.trim(), tags: [] })
      toast.success('已重命名')
      setRenaming(null)
      loadProjects()
    } catch (err) {
      toast.error(err.message)
    }
  }

  // v15：迭代历史对比（版本时间线 + 逐版变更统计 + 回滚）
  const [showHistory, setShowHistory] = useState(false)
  const [historyData, setHistoryData] = useState(null) // {name, history: [{version, created_at, requirement, stats}]}
  const [historyLoading, setHistoryLoading] = useState(false)
  const [compareFrom, setCompareFrom] = useState(null)
  const [compareTo, setCompareTo] = useState(null)
  const [historyFiles, setHistoryFiles] = useState({}) // version -> {files}
  const [historyViewVer, setHistoryViewVer] = useState(null) // 正在查看的历史版本
  const [historyViewFiles, setHistoryViewFiles] = useState(null)
  const [historyViewLoading, setHistoryViewLoading] = useState(false)
  const [restoring, setRestoring] = useState(false)

  // 加载迭代历史时间线
  const openHistory = async () => {
    if (!viewing) return
    setShowHistory(true)
    setHistoryLoading(true)
    setHistoryData(null)
    try {
      const res = await api.get(`/api/games/${viewing.id}/history`)
      setHistoryData(res.data)
      const h = res.data?.history || []
      if (h.length >= 2) {
        setCompareFrom(h[h.length - 2].version)
        setCompareTo(h[h.length - 1].version)
      } else {
        setCompareFrom(null)
        setCompareTo(null)
      }
    } catch (e) {
      toast.error(`加载迭代历史失败：${e.message}`)
    } finally {
      setHistoryLoading(false)
    }
  }

  // 加载某历史版本的完整文件（查看/对比用，带缓存）
  const viewHistoryVersion = async (version) => {
    if (!viewing) return
    setHistoryViewVer(version)
    setHistoryViewLoading(true)
    if (historyFiles[version]) {
      setHistoryViewFiles(historyFiles[version])
      setHistoryViewLoading(false)
      return
    }
    try {
      const res = await api.get(`/api/games/${viewing.id}/history/${version}`)
      setHistoryFiles((prev) => ({ ...prev, [version]: res.data.files }))
      setHistoryViewFiles(res.data.files)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setHistoryViewLoading(false)
    }
  }

  // 回滚到历史版本（当前版本自动快照）
  const restoreVersion = async (version) => {
    if (!window.confirm(`确定回滚到 v${version} 吗？当前版本会自动保存为快照，可再次回滚。`)) return
    setRestoring(true)
    try {
      const res = await api.post(`/api/games/${viewing.id}/restore`, { version })
      setViewing({
        id: viewing.id,
        name: viewing.name,
        files: res.data.files,
        versions: res.data.versions,
      })
      const firstVer = res.data.versions[0] || 'web'
      setVersion(firstVer)
      setSelectedFile(Object.keys(res.data.files[firstVer] || {})[0] || '')
      setShowHistory(false)
      loadProjects()
      toast.success(res.data.message)
    } catch (e) {
      toast.error(`回滚失败：${e.message}`)
    } finally {
      setRestoring(false)
    }
  }

  const evolveGame = async () => {
    if (!viewing || !evolveReq.trim()) {
      toast.error('请输入迭代需求')
      return
    }
    setEvolving(true)
    setGenTask({ progress: 0, stage: '迭代任务排队中…', status: 'pending' })
    await submitTask(
      `/api/games/${viewing.id}/evolve`,
      { requirement: evolveReq.trim() },
      {
        onUpdate: (t) => setGenTask(t),
        onSuccess: (data) => {
          // 刷新查看内容为最新版本
          setViewing({ id: data.id, name: data.name, files: data.files, versions: data.versions })
          const firstVer = data.versions[0] || 'web'
          setVersion(firstVer)
          setSelectedFile(Object.keys(data.files[firstVer] || {})[0] || '')
          setEvolveReq('')
          loadProjects()
          setEvolving(false)
          toast.success(`迭代完成！新版本 ${data.versions.length} 个，共 ${data.file_count} 个文件`)
        },
        onError: (err) => {
          setEvolving(false)
          toast.error(`迭代失败：${err.message}`)
        },
      }
    )
  }

  const downloadZip = async () => {
    if (!viewing) return
    try {
      const res = await api.get(`/api/games/${viewing.id}/export-zip`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${viewing.name}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('ZIP 包已下载（含 web/ 网页版 + wx/ 微信小游戏版）')
    } catch (e) {
      toast.error(`下载失败：${e.message}`)
    }
  }

  // 发布包：网页成品 + 微信小游戏包 + 封面 + 上线清单 + 质量报告（商业化 v14）
  const downloadPublishPack = async () => {
    if (!viewing) return
    try {
      const res = await api.get(`/api/games/${viewing.id}/publish-pack`, {
        responseType: 'blob',
        timeout: 120000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${viewing.name}_发布包.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('发布包已下载（成品 + 封面 + README + 上线清单 + 质量报告）')
    } catch (e) {
      toast.error(`发布包下载失败：${e.message}`)
    }
  }

  const copyFile = async () => {
    try {
      await navigator.clipboard.writeText(viewing.files[version][selectedFile] || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('复制失败')
    }
  }

  const loadGuide = async () => {
    try {
      const res = await api.get('/api/games/deploy-guide')
      setGuide(res.data)
      setShowGuide(true)
    } catch (e) {
      toast.error(e.message)
    }
  }

  // 保存封面：截取试玩画面中游戏 canvas 当前帧，作为项目商用封面
  const saveCover = async () => {
    if (!playing) return
    try {
      const frame = document.getElementById('game-play-frame')
      const canvas = frame?.contentDocument?.querySelector('canvas')
      if (!canvas) {
        toast.error('未找到游戏画面（canvas），请确认游戏已渲染后再试')
        return
      }
      const dataUrl = canvas.toDataURL('image/png')
      await api.post(`/api/games/${playing.id}/cover`, { cover: dataUrl }, { timeout: 30000 })
      loadProjects()
      toast.success('封面已保存，将展示在项目列表')
    } catch (e) {
      toast.error(`封面保存失败：${e.message}`)
    }
  }

  const currentFiles = viewing?.files?.[version] || {}
  const current = currentFiles[selectedFile] || ''
  const tpl = templates.find((t) => t.id === template)
  const vm = VERSION_META[version]

  return (
    <div className="space-y-6">
      <PageHeader
        title="小游戏工坊"
        description="选玩法模板 + 描述需求 → AI 生成双版本小游戏：网页版在线试玩 + 微信小游戏版开发上线"
        icon={Gamepad2}
        iconColor="from-fuchsia-500 to-purple-600"
      />

      {/* ── 统计卡片 ── */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-fuchsia-50 text-fuchsia-600 flex items-center justify-center">
              <Gamepad2 className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.total}</div>
              <div className="text-xs text-gray-400">游戏项目</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Star className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.favorites}</div>
              <div className="text-xs text-gray-400">已收藏</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center">
              <GitCommitHorizontal className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.total_iterations}</div>
              <div className="text-xs text-gray-400">累计迭代</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <BarChart3 className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {Object.keys(stats.template_dist || {}).length}
              </div>
              <div className="text-xs text-gray-400">玩法模板</div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── 左列：模板 + 生成 ── */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FolderTree className="w-4 h-4 text-fuchsia-500" /> 选择玩法模板
            </h3>
            <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
              {TEMPLATE_CATEGORIES.map((cat) => {
                const catTpls = templates.filter((t) => (t.category || '其他') === cat)
                if (catTpls.length === 0) return null
                return (
                  <div key={cat}>
                    <p className="text-[11px] font-medium text-gray-400 mb-1.5 flex items-center gap-1">
                      {cat === '休闲' && '🎮'}
                      {cat === '益智' && '🧩'}
                      {cat === '策略' && '♟️'}
                      {cat === '回合制' && '🔄'}
                      {cat === '模拟' && '🏪'}
                      {cat === '自定义' && '✨'}
                      {cat}
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                      {catTpls.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => setTemplate(t.id)}
                          className={`flex flex-col items-center gap-1 px-1 py-2 rounded-xl border transition-all ${
                            template === t.id
                              ? 'bg-fuchsia-50 border-fuchsia-300 ring-2 ring-fuchsia-500/20'
                              : 'border-gray-200 hover:bg-gray-50'
                          }`}
                        >
                          <span
                            className={`w-8 h-8 rounded-lg bg-gradient-to-br ${t.color} flex items-center justify-center text-base`}
                          >
                            {t.icon}
                          </span>
                          <span className="text-[10px] font-medium text-gray-700 leading-tight text-center">
                            {t.name}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
            {tpl && <p className="mt-2 text-xs text-gray-400">{tpl.description}</p>}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" /> 生成配置
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">游戏名称 *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="如：星际贪吃蛇"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-fuchsia-500/20 focus:border-fuchsia-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center justify-between">
                  <span>玩法需求 *</span>
                  <div className="flex items-center gap-3">
                    <RandomPromptButton
                      prompts={RANDOM_REQUIREMENTS}
                      onPick={(t) => setRequirement(t)}
                      className="text-fuchsia-500 hover:text-fuchsia-700"
                    />
                    <EnhancePromptButton
                      text={requirement}
                      onEnhance={(t) => setRequirement(t)}
                      style="game"
                      className="text-fuchsia-600 hover:text-fuchsia-700"
                    />
                  </div>
                </label>
                <textarea
                  value={requirement}
                  onChange={(e) => setRequirement(e.target.value)}
                  placeholder="描述你的玩法需求，如：加入道具系统，吃金色苹果可以加速，每 50 分关卡加速一次…"
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-fuchsia-500/20 focus:border-fuchsia-500 outline-none"
                />
              </div>
              <Button
                variant="primary"
                size="lg"
                icon={Gamepad2}
                loading={generating}
                onClick={generate}
                className="w-full bg-gradient-to-r from-fuchsia-600 to-purple-600 hover:from-fuchsia-700 hover:to-purple-700"
              >
                {generating ? '生成任务执行中（后台）…' : '生成小游戏（网页 + 微信版）'}
              </Button>
              {genHistory.length > 0 && (
                <div className="mt-3">
                  <HistoryPanel
                    history={genHistory}
                    onReuse={(item) => {
                      if (item.name) setName(item.name)
                      if (item.requirement) setRequirement(item.requirement)
                      if (item.template) setTemplate(item.template)
                      toast.info('已恢复游戏需求，可重新生成')
                    }}
                    onRemove={removeGenHistory}
                    onClear={clearGenHistory}
                    title="生成历史"
                    renderSummary={(item) => (
                      <span className="text-gray-700">
                        {item.name} · {item.requirement?.slice(0, 40)}
                      </span>
                    )}
                  />
                </div>
              )}
              {generating && genTask && (
                <div className="rounded-lg bg-fuchsia-50 border border-fuchsia-100 px-3 py-2">
                  <div className="flex items-center gap-2 text-xs text-fuchsia-600">
                    <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                    <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                    <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-fuchsia-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-fuchsia-500 to-purple-600 rounded-full transition-all"
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
              <Rocket className="w-4 h-4 text-emerald-500" /> 双版本一步到位
            </h3>
            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex gap-2">
                <Globe className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                <span>网页版：平台内直接在线试玩，也可下载部署到任意网站</span>
              </div>
              <div className="flex gap-2">
                <Smartphone className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                <span>微信小游戏版：开发者工具导入即可运行，个人主体可注册上线</span>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              icon={Rocket}
              onClick={loadGuide}
              className="mt-2 w-full justify-center"
            >
              查看部署指引
            </Button>
          </Card>
        </div>

        {/* ── 右列：我的游戏 ── */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2 flex-shrink-0">
                <FolderTree className="w-4 h-4 text-gray-400" /> 我的游戏（{filteredProjects.length}
                ）
              </h3>
              <div className="flex-1 flex flex-wrap items-center gap-2">
                <div className="relative flex-1 min-w-[160px]">
                  <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="搜索游戏名称或需求…"
                    className="w-full pl-8 pr-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-fuchsia-500/20 focus:border-fuchsia-500 outline-none"
                  />
                </div>
                <button
                  onClick={() => setOnlyFav(!onlyFav)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all ${
                    onlyFav
                      ? 'bg-amber-50 border-amber-300 text-amber-700'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <Star
                    className={`w-3.5 h-3.5 ${onlyFav ? 'fill-amber-400 text-amber-400' : ''}`}
                  />
                  {onlyFav ? '全部' : '只看收藏'}
                </button>
                <Button variant="ghost" size="sm" icon={RefreshCw} onClick={loadProjects}>
                  刷新
                </Button>
              </div>
            </div>
            {loading ? (
              <SkeletonList count={3} />
            ) : filteredProjects.length === 0 ? (
              <Empty
                icon={Gamepad2}
                title={q || onlyFav ? '没有匹配的游戏' : '还没有小游戏'}
                description={
                  q || onlyFav
                    ? '换个关键词或筛选条件试试'
                    : '选择模板、填写需求后点击「生成小游戏」'
                }
              />
            ) : (
              <Pagination
                items={filteredProjects}
                pageSize={8}
                label={`共 ${filteredProjects.length} 个小游戏`}
                renderItem={(p) => {
                  const t = templates.find((x) => x.id === p.template)
                  return (
                    <div
                      onClick={() => openProject(p)}
                      className="flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-fuchsia-200 hover:bg-fuchsia-50/30 transition-all cursor-pointer"
                    >
                      <button
                        onClick={(e) => toggleFav(p, e)}
                        title={p.favorite ? '取消收藏' : '收藏'}
                        className={`flex-shrink-0 ${p.favorite ? 'text-amber-400' : 'text-gray-300 hover:text-amber-400'}`}
                      >
                        <Star className={`w-4 h-4 ${p.favorite ? 'fill-amber-400' : ''}`} />
                      </button>
                      <div
                        className={`w-10 h-10 rounded-lg bg-gradient-to-br ${t?.color || 'from-gray-500 to-gray-700'} flex items-center justify-center text-lg flex-shrink-0 overflow-hidden`}
                      >
                        {p.cover ? (
                          <img src={p.cover} alt="封面" className="w-full h-full object-cover" />
                        ) : (
                          t?.icon || '🎮'
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-800 truncate">
                            {p.name}
                          </span>
                          {p.iterations > 0 && (
                            <Badge color="violet">
                              <GitCommitHorizontal className="w-3 h-3 mr-0.5 inline" />
                              迭代 {p.iterations} 次
                            </Badge>
                          )}
                        </div>
                        <div className="text-xs text-gray-400 truncate">
                          {t?.name || '自定义'} · 双版本 · {p.requirement?.slice(0, 50)}
                        </div>
                      </div>
                      <span className="text-xs text-gray-400 flex-shrink-0">
                        {(p.updated_at || p.created_at)?.slice(0, 16).replace('T', ' ')}
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={Play}
                        onClick={(e) => {
                          e.stopPropagation()
                          playGame(p)
                        }}
                      >
                        试玩
                      </Button>
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
                          content={`# 小游戏：${p.name}\n\n需求：${p.requirement || ''}\n\n> 由小团智能平台小游戏工坊生成 · ${new Date().toLocaleString()}`}
                          title={`小游戏：${p.name}`}
                          contentType="game"
                          className="!p-1.5"
                        />
                      </span>
                      <button
                        onClick={(e) => openRename(p, e)}
                        title="重命名"
                        className="p-1.5 text-gray-300 hover:text-violet-500 rounded-lg hover:bg-violet-50"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
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
                <Rocket className="w-4 h-4 text-emerald-500" /> 快速上手
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm text-gray-600">
                <div className="p-3 rounded-lg bg-green-50 border border-green-100">
                  <p className="font-medium text-green-700 mb-1">① 在线试玩</p>
                  <p className="text-xs">点「试玩」直接在平台内运行网页版，验证玩法手感</p>
                </div>
                <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                  <p className="font-medium text-blue-700 mb-1">② 导入开发者工具</p>
                  <p className="text-xs">下载 ZIP → 微信开发者工具（小游戏类型）导入 wx/ 目录</p>
                </div>
                <div className="p-3 rounded-lg bg-violet-50 border border-violet-100">
                  <p className="font-medium text-violet-700 mb-1">③ 发布上线</p>
                  <p className="text-xs">网页版部署到任意网站；微信版上传代码 → 审核 → 发布</p>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ── 项目查看 Modal ── */}
      <Modal
        open={!!viewing}
        onClose={() => setViewing(null)}
        title={viewing ? `游戏：${viewing.name}` : ''}
        size="2xl"
        footer={
          <>
            <Button variant="secondary" icon={Rocket} onClick={loadGuide}>
              部署指引
            </Button>
            <Button variant="secondary" icon={Download} onClick={downloadZip}>
              下载 ZIP
            </Button>
            {viewing && (
              <FavoriteButton
                favType="record"
                targetId={viewing.id}
                label={viewing.name}
                className="!border !border-gray-200 !rounded-lg !px-3 !py-2"
              />
            )}
            <Button
              variant="primary"
              icon={Package}
              onClick={downloadPublishPack}
              title="成品 + 封面 + 上线清单 + 质量报告，一键可交付"
            >
              发布包
            </Button>
            <Button variant="primary" icon={Gamepad2} onClick={() => setViewing(null)}>
              完成
            </Button>
          </>
        }
      >
        {/* ── 商用 QC 报告（生成时门禁结果） ── */}
        {viewing?.qc && (
          <div
            className={`mb-4 rounded-xl border p-3 ${viewing.qc.ok ? 'border-emerald-200 bg-emerald-50/50' : 'border-red-200 bg-red-50/50'}`}
          >
            <div
              className={`flex items-center gap-1.5 text-xs font-medium mb-2 ${viewing.qc.ok ? 'text-emerald-700' : 'text-red-700'}`}
            >
              <BadgeCheck className="w-4 h-4" /> 商用质量门禁（QC）：
              {viewing.qc.ok ? '全部通过，可交付商用' : '部分未通过，建议迭代修复'}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {viewing.qc.checks.map((c) => (
                <span
                  key={c.item}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] ${c.ok ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}
                >
                  {c.ok ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />} {c.item}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 版本切换 */}
        <div className="flex gap-2 mb-4">
          {viewing?.versions?.map((v) => {
            const meta = VERSION_META[v]
            return (
              <button
                key={v}
                onClick={() => switchVersion(v)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  version === v
                    ? 'bg-fuchsia-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {meta?.icon && <meta.icon className="w-3.5 h-3.5" />}
                {meta?.label || v}（{Object.keys(viewing.files[v] || {}).length} 文件）
              </button>
            )
          })}
        </div>

        <div className="flex flex-col md:flex-row gap-4">
          {/* 文件列表 */}
          <div className="md:w-56 flex-shrink-0 border border-gray-200 rounded-xl overflow-hidden max-h-[55vh] overflow-y-auto bg-gray-50/50">
            <div className="px-3 py-2 bg-gray-100/80 border-b border-gray-200 text-xs font-medium text-gray-500 flex items-center gap-1.5">
              {vm?.icon && <vm.icon className="w-3.5 h-3.5" />} {vm?.label} ·{' '}
              {Object.keys(currentFiles).length} 个文件
            </div>
            <div className="p-2 space-y-0.5">
              {Object.keys(currentFiles).map((path) => {
                const { Icon, color } = fileIcon(path)
                return (
                  <button
                    key={path}
                    onClick={() => setSelectedFile(path)}
                    className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs transition-colors text-left ${
                      selectedFile === path
                        ? 'bg-fuchsia-100 text-fuchsia-700 font-medium'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${color} flex-shrink-0`} /> {path}
                  </button>
                )
              })}
            </div>
            {version === 'web' && currentFiles['index.html'] && (
              <div className="px-3 py-2 border-t border-gray-200 bg-green-50/60">
                <Button
                  variant="success"
                  size="sm"
                  icon={Play}
                  className="w-full justify-center"
                  onClick={() =>
                    setPlaying({
                      id: viewing.id,
                      name: viewing.name,
                      html: currentFiles['index.html'],
                    })
                  }
                >
                  在线试玩
                </Button>
              </div>
            )}
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
                <span className="text-xs text-gray-400 font-normal">（{current.length} 字符）</span>
              </span>
              <Button variant="ghost" size="sm" icon={copied ? Check : Copy} onClick={copyFile}>
                {copied ? '已复制' : '复制'}
              </Button>
            </div>
            <pre className="bg-gray-900 text-gray-100 text-xs leading-relaxed p-4 rounded-xl overflow-auto max-h-[48vh] font-mono whitespace-pre">
              {current}
            </pre>
          </div>
        </div>

        {/* ── AI 迭代区 ── */}
        <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50/40 p-4">
          <h4 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-1.5">
            <Wand2 className="w-4 h-4 text-violet-600" /> AI 迭代优化
          </h4>
          <p className="text-xs text-gray-500 mb-2">
            基于当前代码继续改：加功能、调难度、换风格、修 Bug，双版本同步更新；每次迭代自动保存版本快照，可随时对比回滚
          </p>
          <div className="flex gap-2">
            <input
              value={evolveReq}
              onChange={(e) => setEvolveReq(e.target.value)}
              placeholder="如：加一个暂停功能；每 100 分出一个道具；把配色改成赛博朋克风…"
              className="flex-1 px-3 py-2 border border-violet-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none bg-white"
            />
            <Button
              variant="primary"
              icon={Wand2}
              loading={evolving}
              onClick={evolveGame}
              className="bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 flex-shrink-0"
            >
              {evolving ? '迭代任务执行中（后台）…' : '开始迭代'}
            </Button>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <button
              onClick={openHistory}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-violet-600 hover:text-violet-700"
            >
              <History className="w-3.5 h-3.5" />
              迭代历史与版本对比（v15）
            </button>
          </div>
          {evolving && genTask && (
            <div className="mt-2 rounded-lg bg-violet-50 border border-violet-100 px-3 py-2">
              <div className="flex items-center gap-2 text-xs text-violet-600">
                <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                <span className="flex-1 truncate">{genTask.stage || '迭代执行中…'}</span>
                <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
              </div>
              <div className="mt-1.5 h-1.5 bg-violet-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-600 rounded-full transition-all"
                  style={{ width: `${genTask.progress || 0}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* ── 在线试玩 Modal ── */}
      <Modal
        open={!!playing}
        onClose={() => setPlaying(null)}
        title={playing ? `试玩：${playing.name}` : ''}
        size="xl"
        footer={
          <>
            <Button variant="secondary" icon={Camera} onClick={saveCover}>
              保存当前画面为封面
            </Button>
            <Button
              variant="primary"
              icon={Maximize2}
              onClick={() => {
                const url = URL.createObjectURL(new Blob([playing.html], { type: 'text/html' }))
                window.open(url, '_blank')
              }}
            >
              新窗口打开
            </Button>
          </>
        }
      >
        <div className="flex items-center gap-2 mb-3 text-xs text-gray-500 bg-green-50 border border-green-100 rounded-lg px-3 py-2">
          <MonitorPlay className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
          正在运行网页版（键盘操作 + 触屏滑动均可）。微信小游戏版请下载 ZIP 用开发者工具导入。
        </div>
        <div className="rounded-xl border border-gray-200 overflow-hidden bg-gray-900">
          <iframe
            id="game-play-frame"
            title="game-play"
            srcDoc={playing?.html || ''}
            className="w-full h-[60vh] bg-white"
          />
        </div>
      </Modal>

      {/* ── 迭代历史对比 Modal（v15） ── */}
      <Modal
        open={showHistory}
        onClose={() => setShowHistory(false)}
        title={historyData ? `迭代历史：${historyData.name}` : '迭代历史'}
        size="2xl"
      >
        {historyLoading ? (
          <div className="py-10 flex flex-col items-center gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-violet-500" />
            <span className="text-sm text-gray-500">正在加载版本历史…</span>
          </div>
        ) : !historyData || historyData.history.length === 0 ? (
          <Empty
            icon={History}
            title="暂无版本快照"
            description="每次执行 AI 迭代时会自动保存当前版本，之后即可在此对比与回滚"
          />
        ) : (
          <div className="flex flex-col lg:flex-row gap-4">
            {/* 版本时间线 */}
            <div className="lg:w-72 flex-shrink-0 space-y-2 max-h-[55vh] overflow-y-auto pr-1">
              {historyData.history.map((h) => {
                const isLatest = h.version === historyData.history[historyData.history.length - 1].version
                return (
                  <div
                    key={h.version}
                    className={`p-3 rounded-xl border transition-all ${
                      historyViewVer === h.version
                        ? 'border-violet-400 bg-violet-50'
                        : 'border-gray-200 bg-white hover:border-violet-300'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <button
                        onClick={() => viewHistoryVersion(h.version)}
                        className="flex items-center gap-1.5 text-sm font-semibold text-gray-800"
                      >
                        <GitCompare className="w-4 h-4 text-violet-500" />
                        v{h.version}
                        {isLatest && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-600">
                            最新
                          </span>
                        )}
                      </button>
                      <button
                        onClick={() => restoreVersion(h.version)}
                        disabled={restoring || isLatest}
                        title={isLatest ? '当前版本' : '回滚到此版本'}
                        className={`p-1.5 rounded-lg transition-colors ${
                          isLatest
                            ? 'text-gray-300 cursor-not-allowed'
                            : 'text-gray-400 hover:text-amber-600 hover:bg-amber-50'
                        }`}
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="text-[11px] text-gray-400 mt-0.5">
                      {(h.created_at || '').replace('T', ' ').slice(0, 19)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1 truncate" title={h.requirement}>
                      {h.requirement || '初始版本'}
                    </div>
                    {Object.keys(h.stats || {}).length > 0 && (
                      <div className="mt-1.5 space-y-0.5">
                        {Object.entries(h.stats).map(([p, s]) => (
                          <div key={p} className="flex items-center gap-1.5 text-[10px] font-mono">
                            <span className="text-gray-500 truncate flex-1">{p}</span>
                            {s.added > 0 && <span className="text-emerald-600">+{s.added}</span>}
                            {s.removed > 0 && <span className="text-red-500">-{s.removed}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* 版本对比与文件查看 */}
            <div className="flex-1 min-w-0 space-y-4">
              {/* 两版对比 */}
              <div className="rounded-xl border border-gray-200 p-3">
                <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1.5">
                  <GitCompare className="w-4 h-4 text-violet-500" />
                  版本对比（变更行数）
                </div>
                <div className="flex items-center gap-2 mb-3">
                  <select
                    value={compareFrom ?? ''}
                    onChange={(e) => setCompareFrom(Number(e.target.value))}
                    className="flex-1 px-2 py-1.5 rounded-lg border border-gray-200 text-xs focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none bg-white"
                  >
                    <option value="">选择起始版本</option>
                    {historyData.history.map((h) => (
                      <option key={h.version} value={h.version}>
                        v{h.version}
                      </option>
                    ))}
                  </select>
                  <ArrowRight className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                  <select
                    value={compareTo ?? ''}
                    onChange={(e) => setCompareTo(Number(e.target.value))}
                    className="flex-1 px-2 py-1.5 rounded-lg border border-gray-200 text-xs focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none bg-white"
                  >
                    <option value="">选择目标版本</option>
                    {historyData.history.map((h) => (
                      <option key={h.version} value={h.version}>
                        v{h.version}
                      </option>
                    ))}
                  </select>
                </div>
                {compareFrom && compareTo && compareFrom !== compareTo && historyFiles[compareFrom] && historyFiles[compareTo] ? (
                  <VersionDiffTable fromFiles={historyFiles[compareFrom]} toFiles={historyFiles[compareTo]} />
                ) : compareFrom && compareTo && compareFrom !== compareTo ? (
                  <div className="flex items-center gap-2 text-xs text-gray-500 py-3">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    请先点击左侧版本加载文件…
                  </div>
                ) : (
                  <div className="text-xs text-gray-400 py-3">
                    选择两个不同版本后展示逐文件变更行数；对比前先点击左侧版本卡片加载文件
                  </div>
                )}
              </div>

              {/* 历史版本文件查看 */}
              <div className="rounded-xl border border-gray-200 p-3">
                <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1.5">
                  <FileCode2 className="w-4 h-4 text-violet-500" />
                  {historyViewVer ? `v${historyViewVer} 文件内容` : '历史版本文件'}
                  <span className="text-xs text-gray-400 font-normal">（点击左侧版本查看）</span>
                </div>
                {historyViewLoading ? (
                  <div className="flex items-center gap-2 text-xs text-gray-500 py-3">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    加载中…
                  </div>
                ) : historyViewFiles ? (
                  <div className="space-y-2">
                    {Object.entries(historyViewFiles).map(([ver, paths]) => (
                      <div key={ver}>
                        <div className="text-[11px] font-medium text-gray-400 mb-1">{ver}/</div>
                        {Object.entries(paths).map(([p, content]) => (
                          <div
                            key={p}
                            className="mb-1.5 rounded-lg bg-gray-900 text-gray-100 text-[11px] p-2.5 max-h-40 overflow-auto font-mono whitespace-pre"
                          >
                            <div className="text-gray-400 mb-1">{p}</div>
                            {String(content).slice(0, 800)}
                            {String(content).length > 800 ? '…' : ''}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-gray-400 py-3">选择左侧版本查看该版本的完整代码</div>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* ── 部署指引 Modal ── */}
      <Modal open={showGuide} onClose={() => setShowGuide(false)} title="小游戏部署指引" size="lg">
        <div className="space-y-3">
          <ol className="space-y-2.5">
            {guide.steps.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-gray-700">
                <span className="w-6 h-6 rounded-full bg-fuchsia-100 text-fuchsia-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
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

      {/* ── 重命名 Modal ── */}
      <Modal
        open={!!renaming}
        onClose={() => setRenaming(null)}
        title="重命名游戏"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRenaming(null)}>
              取消
            </Button>
            <Button variant="primary" onClick={submitRename}>
              保存
            </Button>
          </>
        }
      >
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">游戏名称</label>
          <input
            value={renameName}
            onChange={(e) => setRenameName(e.target.value)}
            autoFocus
            placeholder="如：星际贪吃蛇 Pro"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-fuchsia-500/20 focus:border-fuchsia-500 outline-none"
          />
        </div>
      </Modal>
    </div>
  )
}
