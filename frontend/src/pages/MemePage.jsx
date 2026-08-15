import React, { useState, useEffect, useMemo } from 'react'
import {
  Sticker,
  Sparkles,
  Loader2,
  Download,
  Trash2,
  ImageIcon,
  SmilePlus,
  Type,
  FileEdit,
  Search,
  Pencil,
  CheckSquare,
  Square,
  DownloadCloud,
  RotateCcw,
  Layers,
  Wand2,
  Copy,
  Package,
  Film,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Modal, Badge, SkeletonGrid,
  Pagination} from '../components/ui'
import ShareButton from '../components/ShareButton'
import FavoriteButton from '../components/FavoriteButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'
import useToolHistory from '../hooks/useToolHistory'
import HistoryPanel from '../components/HistoryPanel'

const STYLES = [
  { id: 'yellow', name: '经典黄底', desc: 'Doge 经典黄', swatch: 'bg-[#FFD84D]', text: '#000000' },
  {
    id: 'white',
    name: '熊猫白底',
    desc: '白底黑字极简',
    swatch: 'bg-white border border-gray-200',
    text: '#000000',
  },
  { id: 'red', name: '公告红底', desc: '红底白字通告', swatch: 'bg-[#E53935]', text: '#FFFFFF' },
  { id: 'black', name: '暗夜黑底', desc: '黑底白字高冷', swatch: 'bg-[#111111]', text: '#FFFFFF' },
  {
    id: 'gradient',
    name: '蓝紫渐变',
    desc: '渐变潮流吸睛',
    swatch: 'bg-gradient-to-b from-indigo-500 to-purple-500',
    text: '#FFFFFF',
  },
  {
    id: 'neon',
    name: '霓虹灯管',
    desc: '深底青光描边',
    swatch: 'bg-gradient-to-b from-[#110826] to-[#2D0C42]',
    text: '#22D3EE',
  },
  {
    id: 'paper',
    name: '报纸复古',
    desc: '米白老报纸风',
    swatch: 'bg-[#F7F3E8] border border-gray-200',
    text: '#111111',
  },
  {
    id: 'sticker',
    name: '贴纸白边',
    desc: '黑字白描边',
    swatch: 'bg-white border border-gray-200',
    text: '#000000',
  },
  {
    id: 'upload',
    name: '上传背景',
    desc: '自己的图片做底',
    swatch: 'bg-gradient-to-br from-gray-400 to-gray-600',
    text: '#FFFFFF',
  },
  {
    id: 'ai',
    name: 'AI 生成',
    desc: '文生图 + 叠字',
    swatch: 'bg-gradient-to-br from-pink-500 to-amber-400',
    text: '#FFFFFF',
  },
]

const AI_STYLES = [
  { id: 'flat', name: '扁平插画', desc: '简洁高饱和' },
  { id: '3d', name: '3D 软萌', desc: '立体卡通' },
  { id: 'pixel', name: '像素复古', desc: '8-bit 质感' },
  { id: 'ink', name: '水墨国风', desc: '笔墨晕染' },
  { id: 'neon', name: '霓虹赛博', desc: '灯管光效' },
  { id: 'oil', name: '油画质感', desc: '笔触厚重' },
  { id: 'anime', name: '赛璐璐动漫', desc: '日漫赛璐璐' },
  { id: 'film', name: '电影写实', desc: '胶片质感' },
  { id: 'watercolor', name: '水彩手绘', desc: '清新晕染' },
  { id: 'retro', name: '复古海报', desc: '美式复古' },
  { id: 'cute3d', name: '粘土手办', desc: '可爱立体' },
  { id: 'graffiti', name: '街头涂鸦', desc: '潮酷喷绘' },
  { id: 'chibi', name: 'Q版大头', desc: '呆萌比例' },
  { id: 'doodle', name: '手绘涂鸦', desc: '随意线稿' },
]

const SUGGESTS = [
  { top: '我太难了', bottom: '生活终于对我下手了' },
  { top: '好的呢', bottom: '微笑中透露着疲惫' },
  { top: '在？', bottom: '出来聊五毛钱的天' },
  { top: '格局打开', bottom: '这事就这么定了' },
  { top: '已阅', bottom: '散会' },
  { top: '干饭人', bottom: '干饭魂' },
  { top: '周五了', bottom: '灵魂已经放假' },
  { top: '甲方说', bottom: '需求很简单，就是改个颜色' },
  { top: '开工', bottom: '搬砖的尽头是摸鱼' },
  { top: '体检报告', bottom: '主打一个不敢看' },
  { top: '早起失败', bottom: '床绑架了我' },
  { top: '开会两小时', bottom: '结论下次再说' },
  { top: '打工人', bottom: '今天也是元气满满的一天呢' },
  { top: '老板画的饼', bottom: '够吃一辈子' },
  { top: '周一', bottom: '重开吧这周' },
  { top: '同事的锅', bottom: '我来背，我谢谢你' },
  { top: '下班', bottom: '以迅雷不及掩耳之势跑路' },
  { top: '咖啡续命', bottom: '三分糖谢谢' },
  { top: '减肥第一天', bottom: '从明天开始' },
  { top: 'AI 写代码', bottom: 'bug 与我无关' },
  { top: '需求评审', bottom: '场景丰富，建议砍掉一半' },
  { top: '周末计划', bottom: '躺平 + 外卖 + 追剧' },
  { top: '年度目标', bottom: '活着就好' },
]

export default function MemePage() {
  const toast = useToast()
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿；bgUpload 图片数据不持久化）
  const [inputs, setInputs] = usePersistentToolState('meme_inputs', {
    style: 'yellow',
    topText: '',
    bottomText: '',
    aiPrompt: '',
    aiStyle: 'flat',
  })
  const { style, topText, bottomText, aiPrompt, aiStyle } = inputs
  const setStyle = (v) => setInputs((p) => ({ ...p, style: v }))
  const setTopText = (v) => setInputs((p) => ({ ...p, topText: v ?? '' }))
  const setBottomText = (v) => setInputs((p) => ({ ...p, bottomText: v ?? '' }))
  const setAiPrompt = (v) => setInputs((p) => ({ ...p, aiPrompt: v ?? '' }))
  const setAiStyle = (v) => setInputs((p) => ({ ...p, aiStyle: v }))
  const [bgUpload, setBgUpload] = useState('')
  const [decoration, setDecoration] = useState('')
  // v22 表情包模板库：热门梗/场景配方（底图风格 + AI 画面 + 文案 + 装饰）
  const [memeTpls, setMemeTpls] = useState([])
  const [memeTplId, setMemeTplId] = useState('')
  const [memeTplInfo, setMemeTplInfo] = useState(null)
  const [memeTplCat, setMemeTplCat] = useState('全部')
  const [generating, setGenerating] = useState(false)
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [draftRestored, setDraftRestored] = useState(false)

  // ── 资产化管理状态 ──
  const [q, setQ] = useState('')
  const [filterStyle, setFilterStyle] = useState('')
  const [sort, setSort] = useState('newest')
  const [selected, setSelected] = useState(new Set())
  const [currentPage, setCurrentPage] = useState(1)
  const [renaming, setRenaming] = useState(null)
  const [renameTitle, setRenameTitle] = useState('')
  const [batchMode, setBatchMode] = useState(false)
  const [batchText, setBatchText] = useState('')
  // 异步任务进度（task_id + 轮询进度）
  const [genTask, setGenTask] = useState(null)
  const { submitTask } = useAsyncTask()
  const { history: genHistory, add: addGenHistory, remove: removeGenHistory, clear: clearGenHistory } =
    useToolHistory('meme_gen_history_v1', 30)
  // ── 商业化发布 v14：微信发布包（勾选成套打包）+ 成套生成（16 张统一风格/角色）──
  const [packOpen, setPackOpen] = useState(false)
  const [packTitle, setPackTitle] = useState('')
  const [packDesc, setPackDesc] = useState('')
  const [packing, setPacking] = useState(false)
  const [setOpen, setSetOpen] = useState(false)
  const [setText, setSetText] = useState('')
  const [setCharacter, setSetCharacter] = useState('')
  const [setBusy, setSetBusy] = useState(false)
  // 风格预览图（v15：模板风格真实底图 + AI 风格示意卡，生成前预览画面质感方向）
  const [previews, setPreviews] = useState([])

  useEffect(() => {
    loadList()
  }, [])

  // 加载风格预览图（失败静默，不阻塞主功能）
  useEffect(() => {
    api
      .get('/api/meme/style-previews')
      .then((res) => setPreviews(res.data || []))
      .catch(() => {})
    // v22 表情包模板
    api
      .get('/api/meme-templates/list')
      .then((res) => setMemeTpls(res.data?.items || []))
      .catch(() => {})
  }, [])

  // 进入页面恢复草稿（仅挂载时执行一次，setter 均为函数式更新）
  useEffect(() => {
    api
      .get('/api/drafts/meme')
      .then((res) => {
        const d = res.data
        if (d?.content?.top_text || d?.content?.bottom_text) {
          setTopText(d.content.top_text || '')
          setBottomText(d.content.bottom_text || '')
          if (d.content.style) setStyle(d.content.style)
          if (d.content.ai_prompt) setAiPrompt(d.content.ai_prompt)
          if (d.content.ai_style) setAiStyle(d.content.ai_style)
          if (d.content.decoration) setDecoration(d.content.decoration)
          setDraftRestored(true)
        }
      })
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 输入防抖自动保存草稿
  useEffect(() => {
    if (!topText.trim() && !bottomText.trim()) return
    const t = setTimeout(() => {
      api
        .post('/api/drafts/save', {
          tool_id: 'meme',
          title: `${topText.slice(0, 15)} / ${bottomText.slice(0, 15)}`,
          content: {
            top_text: topText,
            bottom_text: bottomText,
            style,
            ai_prompt: aiPrompt,
            ai_style: aiStyle,
            decoration,
          },
        })
        .catch(() => {})
    }, 1500)
    return () => clearTimeout(t)
  }, [topText, bottomText, style, aiPrompt, aiStyle, decoration])

  // 生成成功后清除草稿
  const clearDraft = async () => {
    try {
      const res = await api.get('/api/drafts/meme')
      if (res.data?.id) await api.delete(`/api/drafts/${res.data.id}`)
    } catch {
      /* ignore */
    }
  }

  const loadList = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (q) params.set('q', q)
      if (filterStyle) params.set('style', filterStyle)
      if (sort) params.set('sort', sort)
      const res = await api.get(`/api/meme/list?${params.toString()}`)
      setItems(res.data || [])
      api
        .get('/api/meme/stats')
        .then((r) => setStats(r.data))
        .catch(() => {})
    } catch (e) {
      toast.error(`加载失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  // v22：生成 GIF 动图版表情包（文字脉冲 + 震动动画，4-16 帧可调）
  const [gifBusy, setGifBusy] = useState(false)
  const generateGif = async () => {
    if (!topText.trim() && !bottomText.trim()) {
      toast.error('请输入至少一行文字')
      return
    }
    setGifBusy(true)
    try {
      const fd = new FormData()
      fd.append('top_text', topText.trim())
      fd.append('bottom_text', bottomText.trim())
      fd.append('style', style === 'ai' ? 'yellow' : style) // AI 背景在 GIF 链路先回退经典底色
      fd.append('frame_count', '10')
      fd.append('fps', '12')
      const res = await api.post('/api/meme/generate/gif', fd, { timeout: 300000 })
      toast.success('GIF 动图生成完成')
      addGenHistory({
        type: 'GIF动图',
        top: topText.trim(),
        bottom: bottomText.trim(),
        content: `${topText.trim()} / ${bottomText.trim()}（GIF）`,
      })
      await loadList()
    } catch (e) {
      toast.error(`GIF 生成失败：${e.message}`)
    } finally {
      setGifBusy(false)
    }
  }

  const generate = async () => {
    if (!topText.trim() && !bottomText.trim()) {
      toast.error('请输入至少一行文字')
      return
    }
    setGenerating(true)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const fd = new FormData()
    fd.append('top_text', topText.trim())
    fd.append('bottom_text', bottomText.trim())
    fd.append('style', style)
    fd.append('ai_prompt', aiPrompt.trim())
    fd.append('ai_style', aiStyle)
    fd.append('bg_upload', bgUpload)
    fd.append('decoration', decoration.trim())
    if (memeTplId) fd.append('template_id', memeTplId)
    await submitTask('/api/meme/generate', fd, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: async () => {
        addGenHistory({
          type: '表情包',
          top: topText.trim(),
          bottom: bottomText.trim(),
          style,
          content: `${topText.trim()} / ${bottomText.trim()}`,
        })
        toast.success(style === 'ai' ? 'AI 表情包生成完成' : '表情包已生成')
        setGenerating(false)
        setBgUpload('')
        await clearDraft()
        loadList()
      },
      onError: (e) => {
        setGenerating(false)
        toast.error(`生成失败：${e.message}`)
      },
    })
  }

  // ── 批量生成：每行一组「顶部 / 底部」，一次生成多张 ──
  const generateBatch = async () => {
    const lines = batchText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    if (lines.length === 0) {
      toast.error('请输入至少一行文案')
      return
    }
    setGenerating(true)
    let ok = 0
    let done = 0
    // 全部任务（提交/完成）后收尾
    const finish = () => {
      done++
      if (done < lines.length) return
      setGenerating(false)
      setBatchMode(false)
      setBatchText('')
      if (ok > 0) {
        toast.success(`批量生成完成：${ok}/${lines.length} 张`)
        loadList()
      }
    }
    for (const line of lines) {
      const parts = line.split('/')
      const top = (parts[0] || '').trim()
      const bottom = (parts.slice(1).join('/') || '').trim()
      const fd = new FormData()
      fd.append('top_text', top)
      fd.append('bottom_text', bottom)
      fd.append('style', style)
      fd.append('ai_prompt', '')
      await submitTask('/api/meme/generate', fd, {
        onSuccess: () => {
          ok++
          finish()
        },
        onError: (e) => {
          toast.error(`「${line}」生成失败：${e.message}`)
          finish()
        },
      })
    }
  }

  const download = (item) => {
    const a = document.createElement('a')
    a.href = item.url
    a.download = item.id
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // 商用尺寸导出：240（微信表情单图）/ 750（聊天大图）/ 1080（原图）/ 2160（高清印刷）
  const downloadSize = (item, size) => {
    const a = document.createElement('a')
    a.href = `${item.url}?size=${size}`
    a.download = item.id.replace(/\.png$/, `_${size}.png`)
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const remove = async (item) => {
    try {
      await api.delete(`/api/meme/${item.id}`)
      loadList()
      toast.success('已删除')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const removeSelected = async () => {
    if (selected.size === 0) return
    try {
      await Promise.all([...selected].map((id) => api.delete(`/api/meme/${id}`)))
      toast.success(`已删除 ${selected.size} 个表情包`)
      setSelected(new Set())
      loadList()
    } catch (e) {
      toast.error(e.message)
    }
  }

  // 微信发布包：勾选表情 → 主图 240 / 缩略图 120 / 图标 50 / 横幅 750x400 + 指南 + 质量报告
  const downloadPublishPack = async () => {
    if (selected.size === 0) {
      toast.error('请先勾选要打包的表情包')
      return
    }
    setPacking(true)
    try {
      const fd = new FormData()
      ;[...selected].forEach((id) => fd.append('ids', id))
      fd.append('pack_title', packTitle.trim() || '我的表情包')
      fd.append('pack_desc', packDesc.trim() || 'AI 生成趣味表情包')
      const res = await api.post('/api/meme/publish-pack', fd, {
        responseType: 'blob',
        timeout: 120000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `wechat_meme_pack_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setPackOpen(false)
      const setCount = Math.ceil(selected.size / 16)
      toast.success(
        `微信发布包已生成：${selected.size} 张${setCount > 1 ? `（自动拆分为 ${setCount} 套）` : ''}（含规格成品/上传指南/质量报告）`,
      )
    } catch (e) {
      toast.error(`发布包生成失败：${e.message}`)
    } finally {
      setPacking(false)
    }
  }

  // 成套生成：一次输入最多 16 条文案，同风格 + 同角色设定统一生成（可提交微信开放平台审核）
  const generateSet = async () => {
    const lines = setText
      .split(/\n/)
      .map((l) => l.trim())
      .filter(Boolean)
    if (lines.length === 0) {
      toast.error('请输入至少一条文案（每行：顶部文字|底部文字）')
      return
    }
    if (lines.length > 16) {
      toast.error('微信成套表情包最多 16 张')
      return
    }
    setSetBusy(true)
    const fd = new FormData()
    lines.forEach((l) => fd.append('items', l))
    fd.append('style', style)
    fd.append('ai_style', aiStyle)
    fd.append('character', setCharacter.trim())
    fd.append('sync', 'false')
    await submitTask('/api/meme/generate-set', fd, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: () => {
        toast.success(`成套生成完成：${lines.length} 张（风格/角色统一）`)
        setSetBusy(false)
        setSetOpen(false)
        setSetText('')
        setSetCharacter('')
        loadList()
      },
      onError: (e) => {
        setSetBusy(false)
        toast.error(`成套生成失败：${e.message}`)
      },
    })
  }

  const downloadSelected = async () => {
    if (selected.size === 0) return
    try {
      const fd = new FormData()
      ;[...selected].forEach((id) => fd.append('ids', id))
      const res = await api.post('/api/meme/batch-download', fd, {
        responseType: 'blob',
        timeout: 60000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `memes_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已打包下载 ${selected.size} 个表情包`)
    } catch (e) {
      toast.error(`批量下载失败：${e.message}`)
    }
  }

  // 我的文案收藏（localStorage 持久化）
  const [myTexts, setMyTexts] = useState(() => {
    try { return JSON.parse(localStorage.getItem('meme_my_texts') || '[]') } catch { return [] }
  })
  const saveMyText = () => {
    const pair = `${topText.trim()} / ${bottomText.trim()}`
    if (!topText.trim() && !bottomText.trim()) { toast.error('请先输入文案'); return }
    setMyTexts((prev) => {
      if (prev.includes(pair)) { toast.info('该文案已在收藏中'); return prev }
      const next = [pair, ...prev].slice(0, 20)
      localStorage.setItem('meme_my_texts', JSON.stringify(next))
      toast.success('已收藏该文案')
      return next
    })
  }
  const removeMyText = (p) => {
    setMyTexts((prev) => {
      const next = prev.filter((x) => x !== p)
      localStorage.setItem('meme_my_texts', JSON.stringify(next))
      return next
    })
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    // 当前页全选（跨页保留已选，避免误操作）
    const pageSize = 12
    const pageItems = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)
    const pageIds = new Set(pageItems.map((i) => i.id))
    const allOnPage = pageIds.size > 0 && pageIds.size === pageItems.filter((i) => selected.has(i.id)).length
    setSelected((prev) => {
      const next = new Set(prev)
      if (allOnPage) {
        pageIds.forEach((id) => next.delete(id))
      } else {
        pageIds.forEach((id) => next.add(id))
      }
      return next
    })
  }

  const openRename = (item) => {
    setRenaming(item)
    setRenameTitle(item.title || '')
  }

  const submitRename = async () => {
    if (!renameTitle.trim()) {
      toast.error('请输入新标题')
      return
    }
    try {
      await api.put(`/api/meme/${renaming.id}/rename`, { title: renameTitle.trim() })
      toast.success('已重命名')
      setRenaming(null)
      loadList()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const filtered = useMemo(() => {
    let list = [...items]
    if (q) {
      const kw = q.toLowerCase()
      list = list.filter(
        (i) =>
          i.id.toLowerCase().includes(kw) ||
          (i.top_text || '').toLowerCase().includes(kw) ||
          (i.bottom_text || '').toLowerCase().includes(kw) ||
          (i.title || '').toLowerCase().includes(kw)
      )
    }
    if (filterStyle) list = list.filter((i) => i.style === filterStyle)
    return list
  }, [items, q, filterStyle])

  const applySuggest = (s) => {
    setTopText(s.top)
    setBottomText(s.bottom)
  }

  // v22 表情包模板：一键应用配方（文案/风格/AI 画面/装饰）
  const applyMemeTpl = (t) => {
    const parts = (t.texts?.[0] || '').split('|')
    setTopText((parts[0] || '').trim())
    setBottomText((parts[1] || '').trim())
    setStyle(t.style)
    setAiStyle(t.ai_style)
    setDecoration(t.decoration || '')
    if (t.prompt_hint) setAiPrompt(t.prompt_hint)
    setMemeTplId(t.id)
    toast.success(`已应用「${t.name}」模板，可直接生成`)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="表情包工坊"
        description="文字一键生成表情包：经典模板秒出 + AI 场景生成，批量制作、资产化管理"
        icon={Sticker}
        iconColor="from-amber-500 to-orange-600"
      />

      {draftRestored && (
        <div className="flex items-center gap-2 text-xs text-sky-700 bg-sky-50 border border-sky-200 rounded-xl px-4 py-2.5">
          <FileEdit className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="flex-1">已恢复上次未完成的草稿，可直接继续生成或清空重写</span>
          <button
            onClick={() => {
              setTopText('')
              setBottomText('')
              setAiPrompt('')
              setDraftRestored(false)
              api
                .get('/api/drafts/meme')
                .then((r) => r.data?.id && api.delete(`/api/drafts/${r.data.id}`))
                .catch(() => {})
            }}
            className="text-sky-600 hover:text-sky-800 font-medium"
          >
            清空草稿
          </button>
        </div>
      )}

      {/* ── 统计卡片 ── */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Layers className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.total}</div>
              <div className="text-xs text-gray-400">表情包总数</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Wand2 className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.ai_count}</div>
              <div className="text-xs text-gray-400">AI 生成</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Type className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {Object.keys(stats.style_dist || {}).length}
              </div>
              <div className="text-xs text-gray-400">使用风格</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
              <Copy className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {Object.entries(stats.style_dist || {}).reduce((a, [, n]) => Math.max(a, n), 0)}
              </div>
              <div className="text-xs text-gray-400">单风格最多</div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── 左列：生成配置 ── */}
        <div className="space-y-4">
          {/* v22 表情包模板库：热门梗/场景配方，选模板一键填充（文案/风格/装饰） */}
          {memeTpls.length > 0 && (
            <Card>
              <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
                <Sticker className="w-4 h-4 text-amber-500" /> 表情包模板
                <span className="text-xs font-normal text-gray-400">
                  选热门梗模板，文案/风格/装饰一键填充，可直接生成
                </span>
              </h3>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {['全部', ...new Set(memeTpls.map((t) => t.category))].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setMemeTplCat(cat)}
                    className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                      memeTplCat === cat
                        ? 'bg-amber-500 text-white border-amber-500'
                        : 'bg-white text-gray-500 border-gray-200 hover:border-amber-300'
                    }`}
                  >
                    {cat}
                    {cat !== '全部' && (
                      <span className="ml-1 opacity-70">
                        {memeTpls.filter((t) => t.category === cat).length}
                      </span>
                    )}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                {memeTpls
                  .filter((t) => memeTplCat === '全部' || t.category === memeTplCat)
                  .map((t) => (
                    <button
                      key={t.id}
                      onClick={() => applyMemeTpl(t)}
                      title={t.desc}
                      className={`px-3 py-1.5 rounded-lg text-xs border transition-colors flex items-center gap-1 ${
                        memeTplId === t.id
                          ? 'bg-amber-500 text-white border-amber-500'
                          : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'
                      }`}
                    >
                      <span>{t.icon}</span>
                      {t.name}
                      {t.pricing?.mode !== 'free' && (
                        <span
                          className={`text-[10px] px-1 rounded ${
                            memeTplId === t.id ? 'bg-white/20' : 'bg-amber-100 text-amber-700'
                          }`}
                        >
                          {t.pricing_label}
                        </span>
                      )}
                    </button>
                  ))}
              </div>
              {memeTpls.some((t) => t.id === memeTplId) && (
                <div className="mt-3 flex items-center justify-between">
                  <p className="text-[11px] text-amber-600">
                    ✓ 已应用「{memeTpls.find((t) => t.id === memeTplId)?.name}」——文案/风格/装饰已填充，可继续微调后生成
                  </p>
                  <button
                    onClick={async () => {
                      try {
                        const res = await api.get(`/api/meme-templates/${memeTplId}`)
                        setMemeTplInfo(res.data)
                      } catch {
                        toast.error('模板详情加载失败')
                      }
                    }}
                    className="text-xs px-2.5 py-1 rounded-lg border border-amber-200 text-amber-600 hover:bg-amber-50 transition-colors"
                  >
                    📖 查看模板
                  </button>
                </div>
              )}
            </Card>
          )}

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <SmilePlus className="w-4 h-4 text-amber-500" /> 选择风格
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {STYLES.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setStyle(s.id)}
                  className={`flex flex-col items-center gap-1.5 px-2 py-2.5 rounded-xl border transition-all ${
                    style === s.id
                      ? 'bg-amber-50 border-amber-300 ring-2 ring-amber-500/20'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <span
                    className={`w-10 h-8 rounded-lg ${s.swatch} flex items-center justify-center`}
                  >
                    <Type className="w-3.5 h-3.5" style={{ color: s.text }} />
                  </span>
                  <span className="text-xs font-medium text-gray-700">{s.name}</span>
                  <span className="text-[11px] text-gray-400">{s.desc}</span>
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <Type className="w-4 h-4 text-pink-500" /> 表情文字
              </span>
              <button
                onClick={() => applySuggest(SUGGESTS[Math.floor(Math.random() * SUGGESTS.length)])}
                className="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-1"
              >
                <Wand2 className="w-3 h-3" />
                随机梗文案
              </button>
            </h3>
            {!batchMode ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    顶部文字（冲击力强）
                  </label>
                  <input
                    type="text"
                    value={topText}
                    onChange={(e) => setTopText(e.target.value)}
                    placeholder="如：我太难了"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    底部文字（神转折）
                  </label>
                  <input
                    type="text"
                    value={bottomText}
                    onChange={(e) => setBottomText(e.target.value)}
                    placeholder="如：生活终于对我下手了"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">
                    灵感模板（点击填入）
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {SUGGESTS.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => applySuggest(s)}
                        className="px-2 py-1 rounded-full bg-gray-100 hover:bg-amber-100 text-[11px] text-gray-600 hover:text-amber-700 transition-colors"
                      >
                        {s.top} / {s.bottom}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-medium text-gray-400">我的文案收藏</label>
                    <button onClick={saveMyText} className="text-[11px] text-amber-500 hover:text-amber-700">
                      ★ 收藏当前文案
                    </button>
                  </div>
                  {myTexts.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {myTexts.map((p, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-amber-50 border border-amber-100 text-[11px] text-amber-700">
                          <button onClick={() => {
                            const [top, bottom] = p.split(' / ')
                            setTopText(top || '')
                            setBottomText(bottom || '')
                          }} className="truncate max-w-32" title={p}>
                            {p}
                          </button>
                          <button onClick={() => removeMyText(p)} className="text-amber-300 hover:text-red-500">×</button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-gray-400">收藏常用文案，下次一键复用</p>
                  )}
                </div>

                {style === 'ai' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">
                        AI 场景描述（可选）
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={aiPrompt}
                          onChange={(e) => setAiPrompt(e.target.value)}
                          placeholder="如：一只加班到崩溃的柴犬，办公室场景"
                          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                        />
                        <EnhancePromptButton
                          text={aiPrompt}
                          onEnhance={(t) => setAiPrompt(t)}
                          className="text-amber-600 hover:text-amber-700"
                        />
                      </div>
                      <p className="text-[11px] text-gray-400 mt-1">留空则根据文字自动设计场景</p>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1.5">
                        画面风格（点击预览图切换，示意卡为 AI 效果方向）
                      </label>
                      <div className="grid grid-cols-2 sm:grid-cols-4 sm:grid-cols-8 gap-1.5">
                        {AI_STYLES.map((s) => {
                          const pv = previews.find((p) => p.id === `ai:${s.id}`)?.url
                          return (
                            <button
                              key={s.id}
                              onClick={() => setAiStyle(s.id)}
                              title={`${s.name}：${s.desc}`}
                              className={`group relative rounded-xl overflow-hidden border-2 transition-all ${
                                aiStyle === s.id
                                  ? 'border-pink-500 ring-2 ring-pink-500/30'
                                  : 'border-transparent hover:border-pink-300'
                              }`}
                            >
                              <div className="aspect-square w-full bg-gradient-to-br from-gray-100 to-gray-200">
                                {pv ? (
                                  <img
                                    src={pv}
                                    alt={s.name}
                                    loading="lazy"
                                    className="w-full h-full object-cover"
                                  />
                                ) : (
                                  <div className="w-full h-full flex items-center justify-center text-[10px] text-gray-400">
                                    {s.name}
                                  </div>
                                )}
                              </div>
                              <span
                                className={`absolute bottom-0 inset-x-0 text-center text-[10px] py-0.5 ${
                                  aiStyle === s.id ? 'bg-pink-600 text-white' : 'bg-black/50 text-white'
                                }`}
                              >
                                {s.name}
                              </span>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {style === 'upload' && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      背景图片（≤8MB）
                    </label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        if (!f) return
                        const reader = new FileReader()
                        reader.onload = () => setBgUpload(reader.result)
                        reader.readAsDataURL(f)
                      }}
                      className="w-full text-sm text-gray-500 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-amber-50 file:text-amber-700 file:text-xs file:font-medium hover:file:bg-amber-100"
                    />
                    {bgUpload && (
                      <img
                        src={bgUpload}
                        alt="背景预览"
                        className="mt-2 h-24 rounded-lg object-cover border border-gray-200"
                      />
                    )}
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    emoji 装饰（可选，右下角）
                  </label>
                  <input
                    type="text"
                    value={decoration}
                    onChange={(e) => setDecoration(e.target.value)}
                    placeholder="如：😂,🔥,💯（最多 4 个）"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>

                <Button
                  variant="primary"
                  size="lg"
                  icon={Sticker}
                  loading={generating}
                  onClick={generate}
                  className="w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
                >
                  {generating ? '生成任务执行中（后台）…' : '生成表情包'}
                </Button>
                <button
                  onClick={generateGif}
                  disabled={generating || (!topText.trim() && !bottomText.trim())}
                  className="w-full mt-2 p-3 rounded-xl border-2 border-dashed border-purple-300 hover:border-purple-500 hover:bg-purple-50/50 transition-all text-center disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Film className="w-5 h-5 mx-auto text-purple-500 mb-1" />
                  <div className="text-sm font-medium text-purple-600">生成 GIF 动图版</div>
                  <div className="text-xs text-gray-400 mt-0.5">文字脉冲缩放 + 震动动画，微信聊天更吸睛</div>
                </button>
                {genHistory.length > 0 && (
                  <div className="mt-3">
                    <HistoryPanel
                      history={genHistory}
                      onReuse={(item) => {
                        if (item.top) {
                          setTopText(item.top)
                          setBottomText(item.bottom || '')
                          setStyle(item.style || 'yellow')
                        }
                        toast.info('已恢复文案，可重新生成')
                      }}
                      onRemove={removeGenHistory}
                      onClear={clearGenHistory}
                      title="生成历史"
                    />
                  </div>
                )}
                {generating && genTask && (
                  <div className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2">
                    <div className="flex items-center gap-2 text-xs text-amber-700">
                      <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                      <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                      <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                    </div>
                    <div className="mt-1.5 h-1.5 bg-amber-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-amber-500 to-orange-600 rounded-full transition-all"
                        style={{ width: `${genTask.progress || 0}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[11px] text-gray-400">
                      任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                    </p>
                  </div>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Copy}
                  onClick={() => {
                    setBatchMode(true)
                    setBatchText('')
                  }}
                  className="w-full justify-center"
                >
                  批量生成模式（一次多张）
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={Layers}
                  loading={setBusy}
                  onClick={() => {
                    setSetText('')
                    setSetCharacter('')
                    setSetOpen(true)
                  }}
                  className="w-full justify-center"
                  title="一次输入最多 16 条文案，同风格+同角色统一生成，可直接提交微信表情开放平台"
                >
                  成套生成（16 张统一风格/角色）
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center justify-between">
                    <span>批量文案（每行一组，用 / 分隔顶部与底部）</span>
                    <button
                      onClick={() => {
                        const count = 3 + Math.floor(Math.random() * 2)
                        const pool = [...SUGGESTS]
                        const picked = []
                        while (picked.length < count && pool.length > 0) {
                          const i = Math.floor(Math.random() * pool.length)
                          picked.push(pool.splice(i, 1)[0])
                        }
                        setBatchText(picked.map((s) => `${s.top} / ${s.bottom}`).join('\n'))
                      }}
                      className="text-amber-600 hover:text-amber-700 flex items-center gap-1"
                    >
                      <Wand2 className="w-3 h-3" />
                      随机批量
                    </button>
                  </label>
                  <textarea
                    value={batchText}
                    onChange={(e) => setBatchText(e.target.value)}
                    rows={8}
                    placeholder={
                      '举例：\n我太难了 / 生活终于对我下手了\n好的呢 / 微笑中透露着疲惫\n在？ / 出来聊五毛钱的天'
                    }
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !generating) {
                        e.preventDefault()
                        generateBatch()
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                  <p className="text-[11px] text-gray-400 mt-1">
                    当前风格：{STYLES.find((s) => s.id === style)?.name} · 每行生成一张
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    size="md"
                    icon={Copy}
                    loading={generating}
                    onClick={generateBatch}
                    className="flex-1 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
                  >
                    {generating ? '批量生成中…' : '批量生成'}
                  </Button>
                  <Button variant="secondary" size="md" onClick={() => setBatchMode(false)}>
                    返回单张
                  </Button>
                </div>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-emerald-500" /> 使用提示
            </h3>
            <div className="space-y-2 text-sm text-gray-600">
              <p>① 经典模板模式秒出，微信/QQ 直接发送</p>
              <p>② 智能换行优先在标点断行，白字黑描边 + 投影更立体</p>
              <p>③ 支持 240/750/1080/2160 多尺寸导出（微信表情/聊天图/高清印刷）</p>
              <p>④ AI 模式生成专属搞笑场景，上下文字底条保证可读性</p>
            </div>
          </Card>
        </div>

        {/* ── 右列：表情包资产库 ── */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2 flex-shrink-0">
                <Sticker className="w-4 h-4 text-gray-400" /> 表情包资产库（{filtered.length}）
              </h3>
              <div className="flex-1 flex flex-wrap items-center gap-2">
                <div className="relative flex-1 min-w-[160px]">
                  <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="搜索文字或文件名…"
                    className="w-full pl-8 pr-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>
                <select
                  value={filterStyle}
                  onChange={(e) => setFilterStyle(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-amber-500 bg-white"
                >
                  <option value="">全部风格</option>
                  {STYLES.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-amber-500 bg-white"
                >
                  <option value="newest">最新优先</option>
                  <option value="oldest">最早优先</option>
                </select>
                <Button variant="ghost" size="sm" icon={RotateCcw} onClick={loadList}>
                  刷新
                </Button>
              </div>
            </div>

            {filtered.length > 0 && (
              <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs">
                <button
                  onClick={toggleAll}
                  className="flex items-center gap-1.5 text-gray-600 hover:text-amber-600"
                >
                  {(() => {
                    const pageSize = 12
                    const pageItems = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)
                    const allOnPage = pageItems.length > 0 && pageItems.every((i) => selected.has(i.id))
                    return allOnPage ? (
                      <CheckSquare className="w-4 h-4" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )
                  })()}
                  全选本页
                </button>
                <span className="text-gray-400">已选 {selected.size} 项（跨页累计）</span>
                {selected.size > 0 && (
                  <div className="ml-auto flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={DownloadCloud}
                      onClick={downloadSelected}
                    >
                      批量下载 ZIP
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      icon={Package}
                      onClick={() => {
                        setPackTitle('')
                        setPackDesc('')
                        setPackOpen(true)
                      }}
                      title="一键打包为微信表情开放平台可提交的成套物料"
                    >
                      微信发布包
                    </Button>
                    <Button variant="danger" size="sm" icon={Trash2} onClick={removeSelected}>
                      批量删除
                    </Button>
                  </div>
                )}
              </div>
            )}

            {loading ? (
              <SkeletonGrid count={4} />
            ) : filtered.length === 0 ? (
              <Empty
                icon={Sticker}
                title={q || filterStyle ? '没有匹配的表情包' : '还没有表情包'}
                description={
                  q || filterStyle ? '换个关键词或筛选条件试试' : '输入文字、选风格，点击生成即可'
                }
              />
            ) : (
              <Pagination
                items={filtered}
                pageSize={12}
                onPageChange={setCurrentPage}
                label={q || filterStyle ? `找到 ${filtered.length} 个表情包` : `共 ${filtered.length} 个表情包`}
                renderItem={(item) => (
                  <div
                    key={item.id}
                    className="group relative rounded-xl border border-gray-100 overflow-hidden hover:shadow-lg transition-all"
                  >
                    <img
                      src={item.url}
                      alt="表情包"
                      loading="lazy"
                      className="w-full aspect-square object-contain bg-gray-50"
                    />
                    {/* 标题条（非 hover 也可见） */}
                    <div className="absolute top-0 inset-x-0 bg-gradient-to-b from-black/60 to-transparent p-1.5 pb-4 flex items-center justify-between">
                      <span className="text-[11px] text-white truncate flex-1">{item.title}</span>
                      <button
                        onClick={() => toggleSelect(item.id)}
                        className={`p-0.5 flex-shrink-0 ${selected.has(item.id) ? 'text-amber-400' : 'text-white/70 hover:text-white'}`}
                      >
                        {selected.has(item.id) ? (
                          <CheckSquare className="w-3.5 h-3.5" />
                        ) : (
                          <Square className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="text-[11px] text-white truncate flex-1">
                        {item.style_label || '未标记'} ·{' '}
                        {item.created_at?.slice(5, 16).replace('T', ' ')}
                      </span>
                      <button
                        onClick={() => openRename(item)}
                        title="重命名"
                        className="p-1 text-white hover:text-violet-300"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => download(item)}
                        title="下载原图 1080"
                        className="p-1 text-white hover:text-blue-300"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <span onClick={(e) => e.stopPropagation()}>
                        <ShareButton
                          content={`# 表情包：${item.title}\n\n风格：${item.style_label || '未标记'}\n\n> 由小团智能平台表情包工坊生成 · ${new Date().toLocaleString()}`}
                          title={`表情包：${item.title}`}
                          contentType="meme"
                          className="!p-1 !text-white !bg-transparent"
                        />
                      </span>
                      <span onClick={(e) => e.stopPropagation()}>
                        <FavoriteButton
                          favType="gallery"
                          targetId={item.id || item.filename}
                          label={item.title?.slice(0, 40) || '表情包'}
                          className="!p-1 !text-white !bg-transparent"
                        />
                      </span>
                      <select
                        onChange={(e) => {
                          if (e.target.value) downloadSize(item, e.target.value)
                        }}
                        defaultValue=""
                        title="导出尺寸"
                        className="text-[10px] bg-black/40 text-white border border-white/20 rounded-md px-1 py-0.5 outline-none cursor-pointer"
                      >
                        <option value="" disabled>
                          尺寸
                        </option>
                        {[240, 750, 1080, 2160].map((s) => (
                          <option key={s} value={s} className="text-gray-800">
                            {s}×{s}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => remove(item)}
                        title="删除"
                        className="p-1 text-white hover:text-red-300"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              />
            )}
          </Card>
        </div>
      </div>

      {/* ── 成套生成 Modal（商业化 v14：16 张成套，同风格+同角色）── */}
      <Modal
        open={setOpen}
        onClose={() => setOpen(false)}
        title="成套生成（微信表情开放平台成套）"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)} disabled={setBusy}>
              取消
            </Button>
            <Button
              variant="primary"
              icon={Layers}
              loading={setBusy}
              onClick={generateSet}
              className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
            >
              开始成套生成
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-700">
            每行一条文案（格式：顶部文字|底部文字，可只填顶部），最多 16 张。全套自动保持同一风格
            + 同一角色设定，可直接提交微信表情开放平台审核。生成前自动安全审核，违规文案会拦截并提示修改。
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              成套文案（{setText.split(/\n/).filter((l) => l.trim()).length}/16 条）
            </label>
            <textarea
              value={setText}
              onChange={(e) => setSetText(e.target.value)}
              rows={8}
              placeholder={
                '举例：\n我太难了|生活终于对我下手了\n好的呢|微笑中透露着疲惫\n在？|出来聊五毛钱的天\n格局打开|这事就这么定了'
              }
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">
                角色设定（AI 模式，全套保持一致）
              </label>
              <input
                type="text"
                value={setCharacter}
                onChange={(e) => setSetCharacter(e.target.value)}
                placeholder="如：一只圆滚滚的橘猫，穿黄色卫衣"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">
                风格（预览与成图一致）
              </label>
              <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200">
                {(() => {
                  const pvId = style === 'ai' ? `ai:${aiStyle}` : style
                  const pv = previews.find((p) => p.id === pvId)?.url
                  return pv ? (
                    <img
                      src={pv}
                      alt="风格预览"
                      className="w-14 h-14 rounded-lg object-cover border border-gray-200 shrink-0"
                    />
                  ) : null
                })()}
                <div className="text-sm text-gray-700">
                  {STYLES.find((s) => s.id === style)?.name}
                  {style === 'ai' && ` · ${AI_STYLES.find((s) => s.id === aiStyle)?.name}`}
                  <div className="text-[11px] text-gray-400 mt-0.5">
                    {style === 'ai' ? 'AI 效果示意，生成后为真实画面' : '与成图一致的底图预览'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Modal>

      {/* ── 微信发布包 Modal ── */}
      <Modal
        open={packOpen}
        onClose={() => setPackOpen(false)}
        title="微信表情发布包"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPackOpen(false)} disabled={packing}>
              取消
            </Button>
            <Button
              variant="primary"
              icon={Package}
              loading={packing}
              onClick={downloadPublishPack}
              className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
            >
              生成发布包（{selected.size} 张
              {Math.ceil(selected.size / 16) > 1 ? ` / ${Math.ceil(selected.size / 16)} 套` : ''}）
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-sky-50 border border-sky-100 px-3 py-2 text-xs text-sky-700">
            将自动生成：主图 240×240 / 缩略图 120×120 / 聊天页图标 50×50 / 详情页横幅 750×400，
            并附《表情说明》《上传指南》《平台规格说明》《商用授权》《质量自检报告》。微信审核需 16 张成套。
          </div>
          {selected.size > 16 && (
            <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2 text-xs text-violet-700">
              已选 {selected.size} 张，将自动按 16 张/套拆分为{' '}
              {Math.ceil(selected.size / 16)} 套打包，每套独立成目录，需分别提交微信审核。
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              表情包名称（投稿标题，≤30 字）
            </label>
            <input
              type="text"
              value={packTitle}
              onChange={(e) => setPackTitle(e.target.value)}
              placeholder="如：打工人日常"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              表情介绍（投稿说明，≤200 字）
            </label>
            <textarea
              value={packDesc}
              onChange={(e) => setPackDesc(e.target.value)}
              rows={3}
              placeholder="如：打工人专属表情，包含摸鱼、加班、周五等高频场景"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
            />
          </div>
        </div>
      </Modal>

      {/* ── 重命名 Modal ── */}
      <Modal
        open={!!renaming}
        onClose={() => setRenaming(null)}
        title="重命名表情包"
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
          <label className="block text-xs font-medium text-gray-500 mb-1.5">
            标题（便于在资产库中识别）
          </label>
          <input
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            autoFocus
            placeholder="如：打工人专用-01"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
          />
        </div>
      </Modal>

      {/* v22 表情包模板详情弹窗 */}
      <Modal
        open={!!memeTplInfo}
        onClose={() => setMemeTplInfo(null)}
        title="表情包模板"
      >
        {memeTplInfo && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{memeTplInfo.icon}</span>
              <h3 className="text-lg font-semibold text-gray-800">{memeTplInfo.name}</h3>
              <Badge color="amber">{memeTplInfo.category_label || memeTplInfo.category}</Badge>
              {memeTplInfo.pricing?.mode !== 'free' && (
                <Badge color="red">{memeTplInfo.pricing_label}</Badge>
              )}
            </div>
            <p className="text-sm text-gray-500 leading-relaxed">{memeTplInfo.desc}</p>
            <div className="text-xs text-gray-400">
              热度 {memeTplInfo.usage || 0} 次使用{memeTplInfo.pricing?.mode === 'free' ? ' · 免费' : ''}
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                ['🎨 底图风格', memeTplInfo.style],
                ['🖼️ AI 画面风格', memeTplInfo.ai_style],
                ['✨ 推荐装饰', memeTplInfo.decoration || '无'],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-gray-50 border border-gray-100 p-2.5">
                  <div className="text-[11px] text-gray-400">{k}</div>
                  <div className="text-xs font-medium text-gray-700 mt-0.5">{v}</div>
                </div>
              ))}
              <div className="rounded-xl bg-gray-50 border border-gray-100 p-2.5">
                <div className="text-[11px] text-gray-400">📝 文案建议</div>
                <div className="text-xs font-medium text-gray-700 mt-0.5">
                  {memeTplInfo.top_hint}… / {memeTplInfo.bottom_hint}…
                </div>
              </div>
            </div>
            {memeTplInfo.prompt_hint && (
              <div className="rounded-xl bg-gray-50 border border-gray-100 p-3.5">
                <div className="text-xs font-semibold text-amber-600 mb-1">🎬 AI 场景建议</div>
                <p className="text-[13px] text-gray-600 leading-relaxed">{memeTplInfo.prompt_hint}</p>
              </div>
            )}
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-3.5">
              <div className="text-xs font-semibold text-amber-600 mb-1.5">💬 即用文案（点击一键填充）</div>
              <div className="space-y-1.5">
                {memeTplInfo.texts?.map((tx, i) => {
                  const parts = String(tx).split('|')
                  return (
                    <button
                      key={i}
                      onClick={() => {
                        setTopText((parts[0] || '').trim())
                        setBottomText((parts[1] || '').trim())
                        setMemeTplInfo(null)
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg bg-white border border-gray-200 hover:border-amber-300 hover:bg-amber-50 text-xs text-gray-600 transition-colors"
                    >
                      <span className="font-medium">{parts[0]}</span>
                      <span className="text-gray-400"> / </span>
                      {parts[1]}
                    </button>
                  )
                })}
              </div>
            </div>
            <div className="flex items-center justify-end pt-1">
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setMemeTplInfo(null)}>
                  关闭
                </Button>
                <Button onClick={() => applyMemeTpl(memeTplInfo)}>应用此模板</Button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
