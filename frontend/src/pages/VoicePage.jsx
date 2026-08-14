import React, { useState, useEffect, useMemo } from 'react'
import {
  Mic2,
  Sparkles,
  Loader2,
  Download,
  Trash2,
  Volume2,
  Clapperboard,
  Film,
  AudioLines,
  Gauge,
  FileEdit,
  Search,
  Pencil,
  CheckSquare,
  Square,
  DownloadCloud,
  RotateCcw,
  Clock,
  BarChart3,
  Play,
  FileText,
  SlidersHorizontal,
  Wand2,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Modal, Badge, SkeletonList } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

const SCENES = [
  {
    id: 'shortvideo',
    name: '短视频旁白',
    desc: '节奏明快，口播/知识解说',
    icon: Clapperboard,
    color: 'from-pink-500 to-rose-600',
  },
  {
    id: 'ad',
    name: '广告口播',
    desc: '有感染力，产品宣传/带货',
    icon: Sparkles,
    color: 'from-amber-500 to-orange-600',
  },
  {
    id: 'audiobook',
    name: '有声书',
    desc: '娓娓道来，故事/小说朗读',
    icon: AudioLines,
    color: 'from-violet-500 to-purple-600',
  },
  {
    id: 'news',
    name: '新闻播报',
    desc: '字正腔圆，资讯/播报类',
    icon: Mic2,
    color: 'from-blue-500 to-indigo-600',
  },
  {
    id: 'story',
    name: '儿童故事',
    desc: '活泼童趣，亲子/教育内容',
    icon: Volume2,
    color: 'from-emerald-500 to-green-600',
  },
  {
    id: 'custom',
    name: '自定义',
    desc: '自由选择音色与语速',
    icon: Gauge,
    color: 'from-gray-500 to-gray-700',
  },
]

const VOICES = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓', gender: '女', style: '温柔亲切', emoji: '👩' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊', gender: '女', style: '活泼俏皮', emoji: '👧' },
  { id: 'zh-CN-YunxiNeural', name: '云希', gender: '男', style: '阳光少年感', emoji: '👦' },
  { id: 'zh-CN-YunjianNeural', name: '云健', gender: '男', style: '成熟浑厚', emoji: '🧔' },
  { id: 'zh-CN-YunyangNeural', name: '云扬', gender: '男', style: '新闻播报感', emoji: '🎙️' },
  { id: 'zh-CN-XiaomoNeural', name: '晓墨', gender: '童', style: '童声可爱', emoji: '🧒' },
  { id: 'en-US-AriaNeural', name: 'Aria', gender: '女', style: '英文女声', emoji: '🇺🇸' },
  {
    id: 'en-US-ChristopherNeural',
    name: 'Christopher',
    gender: '男',
    style: '英文男声',
    emoji: '🇬🇧',
  },
  // ── AI 克隆音色（CosyVoice 本地引擎，需 voice_engine 服务运行） ──
  { id: '中文女', name: '中文女声', gender: '女', style: 'AI 克隆音色 · 自然拟真', emoji: '🤖' },
  { id: '中文男', name: '中文男声', gender: '男', style: 'AI 克隆音色 · 自然拟真', emoji: '🤖' },
  { id: '中文童声', name: '中文童声', gender: '童', style: 'AI 克隆音色 · 活泼童真', emoji: '🤖' },
  { id: '粤语女', name: '粤语女声', gender: '女', style: 'AI 克隆音色 · 粤语流利', emoji: '🤖' },
]

// 场景化示例文案（点击场景卡片且文本为空时自动填充；随机文案从当前场景池抽取）
const SCENE_TEXT_TEMPLATES = {
  shortvideo: [
    '大家好，欢迎来到小团智能平台，今天用 3 分钟教你做出一个爆款短视频，从选题到剪辑，全程干货，先点赞收藏再观看。',
    '你有没有发现，短视频的黄金三秒决定了播放量，今天分享三个开头技巧，让你的视频完播率翻倍。',
    '揭秘！普通人也能学会的短视频涨粉方法，第一步就是找准自己的赛道，第二步持续输出垂直内容。',
  ],
  ad: [
    '还在为效率低下烦恼吗？小团智能平台一站式搞定文案、图片、视频，一次创作，全平台分发，现在注册还有免费额度，赶紧体验吧！',
    '限时福利！今天下单立减五十元，前一百名还送精美礼品，机会有限，错过再等一年，赶快点击下方链接抢购！',
    '这款产品凭什么销量十万加？三大核心优势：材质升级、工艺精良、售后无忧，用户口碑爆棚，你还在犹豫什么？',
  ],
  audiobook: [
    '夜深了，故事才刚刚开始。他推开那扇尘封已久的木门，眼前的一切让他愣在了原地……',
    '第一章 初遇。那是一个下着细雨的黄昏，她撑着一把红色的伞，站在巷口，仿佛等了很久。',
    '老屋的钟敲了十二下，男孩悄悄从床上爬起来，借着月光，翻开了那本泛黄的日记。',
  ],
  news: [
    '各位听众朋友，大家好，这里是午间新闻。首先关注国内要闻：人工智能产业迎来新一轮发展机遇，多地出台支持政策……',
    '今日要闻播报：受冷空气影响，本周全国大部分地区将迎来降温天气，请广大市民注意添衣保暖，出行注意安全。',
    '下面播报财经消息：本周股市整体震荡上行，科技板块表现亮眼，专家提醒投资者注意控制仓位风险。',
  ],
  story: [
    '小朋友们，晚上好呀！今天森林里的小兔子要去找它的好朋友小松鼠玩，路上会发生什么有趣的事情呢？让我们一起去看看吧！',
    '从前呀，有一只不爱刷牙的小狮子，它总是捂着嘴巴说牙疼，后来牙医大象伯伯来帮忙了，猜猜小狮子最后怎么样了？',
    '叮咚，魔法城堡的大门打开了，小公主和小伙伴们要出发去寻找会唱歌的星星啦，出发之前，先把小手洗干净哦！',
  ],
  custom: [
    '欢迎来到小团智能平台，在这里，你可以自由选择音色、语速和音调，打造专属于你的声音。',
    '这是一段自定义配音示例文本，你可以替换成自己的内容，选择喜欢的音色开始创作。',
  ],
}

function fmtDuration(sec) {
  if (!sec) return '--:--'
  const m = Math.floor(sec / 60),
    s = Math.round(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function fmtSize(bytes) {
  if (!bytes) return '0 KB'
  return `${(bytes / 1024).toFixed(1)} KB`
}

export default function VoicePage() {
  const toast = useToast()
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿）
  const [inputs, setInputs] = usePersistentToolState('voice_inputs', {
    scene: 'shortvideo',
    text: '',
    voice: 'zh-CN-XiaoxiaoNeural',
    speed: 1.0,
    pitch: 0,
    emotion: '',
    format: 'mp3',
  })
  const { scene, text, voice, speed, pitch, emotion, format } = inputs
  const setScene = (v) => setInputs((p) => ({ ...p, scene: v }))
  const setText = (v) => setInputs((p) => ({ ...p, text: v ?? '' }))
  const setVoice = (v) => setInputs((p) => ({ ...p, voice: v }))
  const setSpeed = (v) => setInputs((p) => ({ ...p, speed: v }))
  const setPitch = (v) => setInputs((p) => ({ ...p, pitch: v }))
  const setEmotion = (v) => setInputs((p) => ({ ...p, emotion: v }))
  const setFormat = (v) => setInputs((p) => ({ ...p, format: v }))
  // 配音场景模板库：一键填充配方（音色/语速/音调/情绪/文案）+ 热度/商业化
  const [voiceTpls, setVoiceTpls] = useState([])
  const [voiceTplId, setVoiceTplId] = useState('')
  const [voiceTplInfo, setVoiceTplInfo] = useState(null)
  const [voiceTplCat, setVoiceTplCat] = useState('全部')
  useEffect(() => {
    api
      .get('/api/voice-templates/list')
      .then((res) => setVoiceTpls(res.data?.items || []))
      .catch(() => {})
  }, [])
  const voiceTplCats = useMemo(
    () => ['全部', ...new Set(voiceTpls.map((t) => t.category))],
    [voiceTpls]
  )
  const applyVoiceTpl = (t) => {
    setVoiceTplId(t.id)
    setScene('custom') // 模板走自由音色通道，精准应用配方
    setVoice(t.voice)
    setSpeed(t.speed)
    setPitch(t.pitch)
    setEmotion(t.emotion || '')
    if (t.texts?.length) setText(t.texts[0])
  }
  const openVoiceTpl = async (tid) => {
    try {
      const res = await api.get(`/api/voice-templates/${tid}`)
      setVoiceTplInfo(res.data)
    } catch (e) {
      toast.error(`模板详情加载失败：${e.message}`)
    }
  }
  // 随机文案：从当前场景模板池抽取（custom/无匹配时从全部场景池抽取）
  const pickRandomText = () => {
    const pool = SCENE_TEXT_TEMPLATES[scene] || []
    const all = Object.values(SCENE_TEXT_TEMPLATES).flat()
    const src = pool.length > 0 ? pool : all
    setText(src[Math.floor(Math.random() * src.length)])
  }
  const selectScene = (id) => {
    setScene(id)
    // 场景联动：文本为空时自动填充该场景首条示例文案
    if (!text.trim()) {
      const tmpl = (SCENE_TEXT_TEMPLATES[id] || [])[0]
      if (tmpl) setText(tmpl)
    }
  }
  const [previewing, setPreviewing] = useState('')
  const [generating, setGenerating] = useState(false)
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [draftRestored, setDraftRestored] = useState(false)

  // ── 资产化管理状态 ──
  const [q, setQ] = useState('')
  const [filterScene, setFilterScene] = useState('')
  const [filterVoice, setFilterVoice] = useState('')
  const [sort, setSort] = useState('newest')
  const [selected, setSelected] = useState(new Set())
  const [renaming, setRenaming] = useState(null) // { id, title }
  const [renameTitle, setRenameTitle] = useState('')
  // 异步任务进度（task_id + 轮询进度）
  const [genTask, setGenTask] = useState(null)
  const { submitTask } = useAsyncTask()

  useEffect(() => {
    loadList()
  }, [])

  // 进入页面恢复草稿（仅挂载时执行一次，setter 均为函数式更新）
  useEffect(() => {
    api
      .get('/api/drafts/voice')
      .then((res) => {
        const d = res.data
        if (d?.content?.text) {
          setText(d.content.text)
          if (d.content.scene) setScene(d.content.scene)
          if (d.content.voice) setVoice(d.content.voice)
          if (d.content.speed) setSpeed(d.content.speed)
          setDraftRestored(true)
        }
      })
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 输入防抖自动保存草稿
  useEffect(() => {
    if (!text.trim()) return
    const t = setTimeout(() => {
      api
        .post('/api/drafts/save', {
          tool_id: 'voice',
          title: text.slice(0, 30),
          content: { text, scene, voice, speed, pitch, emotion, format },
        })
        .catch(() => {})
    }, 1500)
    return () => clearTimeout(t)
  }, [text, scene, voice, speed])

  // 生成成功后清除草稿
  const clearDraft = async () => {
    try {
      const res = await api.get('/api/drafts/voice')
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
      if (filterScene) params.set('scene', filterScene)
      if (filterVoice) params.set('voice', filterVoice)
      if (sort) params.set('sort', sort)
      const res = await api.get(`/api/voice/list?${params.toString()}`)
      setItems(res.data || [])
      api
        .get('/api/voice/stats')
        .then((r) => setStats(r.data))
        .catch(() => {})
    } catch (e) {
      toast.error(`加载失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const generate = async () => {
    if (!text.trim()) {
      toast.error('请输入要配音的文本')
      return
    }
    setGenerating(true)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const fd = new FormData()
    fd.append('text', text.trim())
    fd.append('scene', scene)
    fd.append('voice', scene === 'custom' ? voice : '')
    fd.append('speed', String(speed))
    fd.append('pitch', String(pitch))
    fd.append('emotion', emotion)
    fd.append('format', format)
    if (voiceTplId) fd.append('template_id', voiceTplId)
    await submitTask('/api/voice/generate', fd, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: async (data) => {
        toast.success(
          `配音完成：${fmtDuration(data.duration)}${data.has_srt ? ' · 已生成 SRT 字幕' : ''}${data.segments > 1 ? `（${data.segments} 段自动拼接）` : ''}`
        )
        setGenerating(false)
        await clearDraft()
        loadList()
      },
      onError: (e) => {
        setGenerating(false)
        toast.error(`生成失败：${e.message}`)
      },
    })
  }

  const download = (item) => {
    const a = document.createElement('a')
    a.href = item.url
    a.download = item.id
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // 音色试听：合成短示例并播放（不占生成额度）
  const previewVoice = async (vid) => {
    if (previewing) return
    setPreviewing(vid)
    try {
      const fd = new FormData()
      fd.append('voice', vid)
      const res = await api.post('/api/voice/preview', fd, { responseType: 'blob', timeout: 60000 })
      const url = URL.createObjectURL(res.data)
      const audio = new Audio(url)
      audio.onended = () => {
        URL.revokeObjectURL(url)
        setPreviewing('')
      }
      audio.onerror = () => {
        URL.revokeObjectURL(url)
        setPreviewing('')
      }
      audio.play().catch(() => setPreviewing(''))
    } catch (e) {
      setPreviewing('')
      toast.error(`试听失败：${e.message}`)
    }
  }

  const remove = async (item) => {
    try {
      await api.delete(`/api/voice/${item.id}`)
      loadList()
      toast.success('已删除')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const removeSelected = async () => {
    if (selected.size === 0) return
    try {
      await Promise.all([...selected].map((id) => api.delete(`/api/voice/${id}`)))
      toast.success(`已删除 ${selected.size} 个配音`)
      setSelected(new Set())
      loadList()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const downloadSelected = async () => {
    if (selected.size === 0) return
    try {
      const res = await api.post('/api/voice/batch-download', toForm([...selected]), {
        responseType: 'blob',
        timeout: 60000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `voices_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已打包下载 ${selected.size} 个配音`)
    } catch (e) {
      toast.error(`批量下载失败：${e.message}`)
    }
  }

  const toForm = (ids) => {
    const fd = new FormData()
    ids.forEach((id) => fd.append('ids', id))
    return fd
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
    setSelected((prev) =>
      prev.size === filtered.length ? new Set() : new Set(filtered.map((i) => i.id))
    )
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
      await api.put(`/api/voice/${renaming.id}/rename`, { title: renameTitle.trim() })
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
          (i.text || '').toLowerCase().includes(kw) ||
          (i.title || '').toLowerCase().includes(kw)
      )
    }
    if (filterScene) list = list.filter((i) => i.scene === filterScene)
    if (filterVoice) list = list.filter((i) => i.voice === filterVoice)
    return list
  }, [items, q, filterScene, filterVoice])

  const sceneCfg = SCENES.find((s) => s.id === scene)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 配音工坊"
        description="文字转语音：选场景预设或自由音色，长文本自动分段拼接，资产化管理配音库"
        icon={Mic2}
        iconColor="from-pink-500 to-rose-600"
      />

      {draftRestored && (
        <div className="flex items-center gap-2 text-xs text-sky-700 bg-sky-50 border border-sky-200 rounded-xl px-4 py-2.5">
          <FileEdit className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="flex-1">已恢复上次未完成的草稿，可直接继续生成或清空重写</span>
          <button
            onClick={() => {
              setText('')
              setDraftRestored(false)
              api
                .get('/api/drafts/voice')
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
            <span className="w-9 h-9 rounded-lg bg-pink-50 text-pink-600 flex items-center justify-center">
              <AudioLines className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.total}</div>
              <div className="text-xs text-gray-400">配音总数</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center">
              <Clock className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {fmtDuration(stats.total_duration)}
              </div>
              <div className="text-xs text-gray-400">总时长</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <BarChart3 className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {Object.keys(stats.scene_dist || {}).length}
              </div>
              <div className="text-xs text-gray-400">使用场景</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
              <Volume2 className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {Object.keys(stats.voice_dist || {}).length}
              </div>
              <div className="text-xs text-gray-400">音色种类</div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── 左列：生成配置 ── */}
        <div className="space-y-4">
          {/* 配音场景模板库：一键应用专业配音配方 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Wand2 className="w-4 h-4 text-purple-500" /> 配音场景模板
              <span className="ml-auto text-[11px] font-normal text-gray-400">
                {voiceTpls.length} 个专业配方
              </span>
            </h3>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {voiceTplCats.map((c) => (
                <button
                  key={c}
                  onClick={() => setVoiceTplCat(c)}
                  className={`px-2.5 py-1 rounded-full text-xs transition-all ${
                    voiceTplCat === c
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5 max-h-44 overflow-y-auto pr-1">
              {voiceTpls
                .filter((t) => voiceTplCat === '全部' || t.category === voiceTplCat)
                .map((t) => (
                  <button
                    key={t.id}
                    onClick={() => applyVoiceTpl(t)}
                    title={t.desc}
                    className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full border text-xs transition-all ${
                      voiceTplId === t.id
                        ? 'bg-purple-50 border-purple-400 ring-2 ring-purple-500/20 text-purple-700 font-medium'
                        : 'border-gray-200 text-gray-600 hover:border-purple-300 hover:bg-purple-50/50'
                    }`}
                  >
                    <span>{t.icon}</span>
                    {t.name}
                    {t.pricing?.mode !== 'free' && (
                      <span className="px-1 rounded bg-amber-100 text-amber-700 text-[10px]">
                        {t.pricing_label}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400">🔥{t.usage || 0}</span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation()
                        openVoiceTpl(t.id)
                      }}
                      className="ml-0.5 text-purple-400 hover:text-purple-600"
                    >
                      📖
                    </span>
                  </button>
                ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-pink-500" /> 选择场景
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {SCENES.map((s) => (
                <button
                  key={s.id}
                  onClick={() => selectScene(s.id)}
                  className={`flex flex-col items-start gap-1 px-3 py-2.5 rounded-xl border transition-all ${
                    scene === s.id
                      ? 'bg-pink-50 border-pink-300 ring-2 ring-pink-500/20'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <span
                    className={`w-7 h-7 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center text-white`}
                  >
                    <s.icon className="w-4 h-4" />
                  </span>
                  <span className="text-xs font-medium text-gray-700">{s.name}</span>
                  <span className="text-[11px] text-gray-400 leading-tight">{s.desc}</span>
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <AudioLines className="w-4 h-4 text-violet-500" /> 配音文本
              <button
                onClick={pickRandomText}
                title="从当前场景示例文案中随机抽取一条"
                className="ml-auto text-xs text-violet-500 hover:text-violet-700 flex items-center gap-1 font-normal"
              >
                <Wand2 className="w-3.5 h-3.5" />
                随机文案
              </button>
            </h3>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="输入要配音的文字，如：大家好，欢迎来到小团智能平台，今天教你 3 分钟做出一个爆款短视频…"
              rows={6}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
            />
            <div className="flex items-center justify-between mt-1">
              <span className="text-xs text-gray-400">
                {text.length} / 10000 字{text.length > 900 ? '（将自动分段拼接）' : ''}
              </span>
              <span className="text-[11px] text-gray-400">支持长文本自动分段</span>
            </div>

            {scene === 'custom' && (
              <div className="mt-3 space-y-3 border-t border-gray-100 pt-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">
                    音色（点击 ▶ 可试听）
                  </label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {VOICES.map((v) => (
                      <div
                        key={v.id}
                        className={`flex items-center gap-1 px-2 py-1.5 rounded-lg border text-xs transition-all ${
                          voice === v.id
                            ? 'bg-pink-50 border-pink-300 text-pink-700 font-medium'
                            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <button
                          onClick={() => setVoice(v.id)}
                          className="flex items-center gap-1 flex-1 min-w-0"
                        >
                          <span>{v.emoji}</span>
                          <span className="truncate">
                            {v.name} · {v.gender}
                          </span>
                        </button>
                        <button
                          onClick={() => previewVoice(v.id)}
                          title="试听音色"
                          className="p-1 rounded-md text-gray-400 hover:text-pink-600 hover:bg-pink-50 flex-shrink-0"
                        >
                          {previewing === v.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Play className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    语速：{speed.toFixed(2)}x
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="2"
                    step="0.05"
                    value={speed}
                    onChange={(e) => setSpeed(parseFloat(e.target.value))}
                    className="w-full accent-pink-500"
                  />
                  <div className="flex justify-between text-[11px] text-gray-400">
                    <span>慢</span>
                    <span>正常</span>
                    <span>快</span>
                  </div>
                </div>
              </div>
            )}

            {/* ── 商用参数：音调 + 格式（全局生效） ── */}
            <div className="mt-3 space-y-3 border-t border-gray-100 pt-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500">
                <SlidersHorizontal className="w-3.5 h-3.5" /> 商用参数（响度已标准化 -14 LUFS +
                淡入淡出）
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  音调：{pitch > 0 ? '+' : ''}
                  {pitch}%（{pitch === 0 ? '原声' : pitch > 0 ? '更明亮' : '更低沉'}）
                </label>
                <input
                  type="range"
                  min="-20"
                  max="20"
                  step="1"
                  value={pitch}
                  onChange={(e) => setPitch(parseInt(e.target.value, 10))}
                  className="w-full accent-violet-500"
                />
                <div className="flex justify-between text-[11px] text-gray-400">
                  <span>低沉 -20</span>
                  <span>原声 0</span>
                  <span>明亮 +20</span>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">输出格式</label>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { id: 'mp3', name: 'MP3 高音质', desc: '256kbps · 体积小' },
                    { id: 'wav', name: 'WAV 无损', desc: 'PCM 16bit · 专业后期' },
                  ].map((f) => (
                    <button
                      key={f.id}
                      onClick={() => setFormat(f.id)}
                      className={`px-2 py-1.5 rounded-lg border text-left transition-all ${
                        format === f.id
                          ? 'bg-violet-50 border-violet-300'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div
                        className={`text-xs font-medium ${format === f.id ? 'text-violet-700' : 'text-gray-700'}`}
                      >
                        {f.name}
                      </div>
                      <div className="text-[10px] text-gray-400">{f.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <Button
              variant="primary"
              size="lg"
              icon={Mic2}
              loading={generating}
              onClick={generate}
              className="w-full mt-3 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700"
            >
              {generating
                ? '生成任务执行中（后台）…'
                : `生成配音${sceneCfg ? `（${sceneCfg.name}）` : ''}`}
            </Button>
            {generating && genTask && (
              <div className="rounded-lg bg-pink-50 border border-pink-100 px-3 py-2 mt-2">
                <div className="flex items-center gap-2 text-xs text-pink-600">
                  <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                  <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                  <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                </div>
                <div className="mt-1.5 h-1.5 bg-pink-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-pink-500 to-rose-600 rounded-full transition-all"
                    style={{ width: `${genTask.progress || 0}%` }}
                  />
                </div>
                <p className="mt-1 text-[11px] text-gray-400">
                  任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                </p>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <Film className="w-4 h-4 text-blue-500" /> 配音怎么用？
            </h3>
            <div className="space-y-2 text-sm text-gray-600">
              <p>① 生成后点 ▶ 试听，满意再下载 mp3</p>
              <p>② 去「视频工厂」生成视频素材，用剪映/PR 等工具把配音合入</p>
              <p>③ 也可以配合「发布中心」直接把成片发布到公众号/抖音/快手</p>
            </div>
          </Card>
        </div>

        {/* ── 右列：配音资产库 ── */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2 flex-shrink-0">
                <AudioLines className="w-4 h-4 text-gray-400" /> 配音资产库（{filtered.length}）
              </h3>
              <div className="flex-1 flex flex-wrap items-center gap-2">
                <div className="relative flex-1 min-w-[160px]">
                  <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="搜索文本或文件名…"
                    className="w-full pl-8 pr-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
                  />
                </div>
                <select
                  value={filterScene}
                  onChange={(e) => setFilterScene(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-pink-500 bg-white"
                >
                  <option value="">全部场景</option>
                  {SCENES.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <select
                  value={filterVoice}
                  onChange={(e) => setFilterVoice(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-pink-500 bg-white"
                >
                  <option value="">全部音色</option>
                  {VOICES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-pink-500 bg-white"
                >
                  <option value="newest">最新优先</option>
                  <option value="oldest">最早优先</option>
                  <option value="duration">时长最长</option>
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
                  className="flex items-center gap-1.5 text-gray-600 hover:text-pink-600"
                >
                  {selected.size === filtered.length ? (
                    <CheckSquare className="w-4 h-4" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                  全选
                </button>
                <span className="text-gray-400">已选 {selected.size} 项</span>
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
                    <Button variant="danger" size="sm" icon={Trash2} onClick={removeSelected}>
                      批量删除
                    </Button>
                  </div>
                )}
              </div>
            )}

            {loading ? (
              <SkeletonList count={3} />
            ) : filtered.length === 0 ? (
              <Empty
                icon={Mic2}
                title={q || filterScene ? '没有匹配的配音' : '还没有配音'}
                description={
                  q || filterScene ? '换个关键词或筛选条件试试' : '选场景、输入文本，点击生成即可'
                }
              />
            ) : (
              <div className="space-y-3">
                {filtered.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 rounded-xl border border-gray-100 hover:border-pink-200 hover:bg-pink-50/30 transition-all"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <button
                        onClick={() => toggleSelect(item.id)}
                        className={`flex-shrink-0 ${selected.has(item.id) ? 'text-pink-600' : 'text-gray-300 hover:text-gray-400'}`}
                      >
                        {selected.has(item.id) ? (
                          <CheckSquare className="w-4 h-4" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                      <span className="w-9 h-9 rounded-lg bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center text-white flex-shrink-0">
                        <Volume2 className="w-4 h-4" />
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-gray-800 truncate">
                            {item.title}
                          </span>
                          {item.scene_label && <Badge color="pink">{item.scene_label}</Badge>}
                          {item.voice_name && <Badge color="blue">{item.voice_name}</Badge>}
                          {item.has_srt && (
                            <Badge color="violet">
                              <FileText className="w-3 h-3" /> SRT
                            </Badge>
                          )}
                          {item.format === 'wav' && <Badge color="amber">WAV</Badge>}
                          {item.pitch !== 0 && (
                            <span className="text-[11px] text-gray-400">
                              音调 {item.pitch > 0 ? '+' : ''}
                              {item.pitch}%
                            </span>
                          )}
                          {item.speed !== 1 && (
                            <span className="text-[11px] text-gray-400">
                              语速 {item.speed.toFixed(2)}x
                            </span>
                          )}
                        </div>
                        {item.text && (
                          <div className="text-xs text-gray-400 truncate">{item.text}</div>
                        )}
                        <div className="text-[11px] text-gray-400 mt-0.5">
                          {fmtDuration(item.duration)} · {fmtSize(item.size)} ·{' '}
                          {item.created_at?.slice(0, 16).replace('T', ' ')}
                          {item.segments > 1 ? ` · ${item.segments} 段拼接` : ''}
                        </div>
                      </div>
                      <button
                        onClick={() => openRename(item)}
                        title="重命名"
                        className="p-1.5 text-gray-300 hover:text-violet-500 rounded-lg hover:bg-violet-50"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => download(item)}
                        title="下载音频"
                        className="p-1.5 text-gray-300 hover:text-blue-500 rounded-lg hover:bg-blue-50"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(item.text || '')
                            toast.success('配音文本已复制')
                          } catch { toast.error('复制失败') }
                        }}
                        title="复制文本"
                        className="p-1.5 text-gray-300 hover:text-emerald-500 rounded-lg hover:bg-emerald-50"
                      >
                        📋
                      </button>
                      <span onClick={(e) => e.stopPropagation()}>
                        <ShareButton
                          content={`# 配音作品：${item.title}\n\n文本：${item.text || ''}\n音色：${item.voice_name || ''} · 场景：${item.scene_label || ''}\n\n> 由小团智能平台 AI 配音工坊生成 · ${new Date().toLocaleString()}`}
                          title={`配音：${item.title}`}
                          contentType="voice"
                          className="!p-1.5"
                        />
                      </span>
                      <button
                        onClick={() => remove(item)}
                        title="删除"
                        className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <audio controls src={item.url} preload="none" className="w-full h-9" />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* ── 配音场景模板详情 Modal ── */}
      <Modal
        open={!!voiceTplInfo}
        onClose={() => setVoiceTplInfo(null)}
        title={`${voiceTplInfo?.icon || '🎙️'} ${voiceTplInfo?.name || '配音场景模板'}`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setVoiceTplInfo(null)}>
              知道了
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                applyVoiceTpl(voiceTplInfo)
                setVoiceTplInfo(null)
              }}
            >
              应用此配方
            </Button>
          </>
        }
      >
        {voiceTplInfo && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge color="purple">{voiceTplInfo.category}</Badge>
              <Badge color={voiceTplInfo.pricing?.mode !== 'free' ? 'amber' : 'green'}>
                {voiceTplInfo.pricing_label}
              </Badge>
              <Badge color="gray">🔥 使用 {voiceTplInfo.usage || 0} 次</Badge>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">{voiceTplInfo.desc}</p>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 rounded-lg bg-gray-50">
                <div className="text-[11px] text-gray-400">推荐音色</div>
                <div className="text-sm font-medium text-gray-800 mt-0.5">
                  {VOICES.find((v) => v.id === voiceTplInfo.voice)?.name || voiceTplInfo.voice}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-gray-50">
                <div className="text-[11px] text-gray-400">语速 / 音调</div>
                <div className="text-sm font-medium text-gray-800 mt-0.5">
                  {voiceTplInfo.speed}x / {voiceTplInfo.pitch > 0 ? '+' : ''}
                  {voiceTplInfo.pitch}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-gray-50">
                <div className="text-[11px] text-gray-400">情绪风格</div>
                <div className="text-sm font-medium text-gray-800 mt-0.5">
                  {voiceTplInfo.emotion
                    ? {
                        happy: '😊 欢快',
                        sad: '😢 悲伤',
                        angry: '🔥 激昂',
                        gentle: '🍃 柔和',
                        serious: '🎯 严肃',
                      }[voiceTplInfo.emotion] || voiceTplInfo.emotion
                    : '无（自然语态）'}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-gray-50">
                <div className="text-[11px] text-gray-400">建议时长</div>
                <div className="text-sm font-medium text-gray-800 mt-0.5">
                  {voiceTplInfo.duration}s
                </div>
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-gray-500 mb-1.5">💬 即用文案（点击应用）</div>
              <div className="space-y-1.5">
                {(voiceTplInfo.texts || []).map((tx, i) => (
                  <button
                    key={i}
                    onClick={() => setText(tx)}
                    className="w-full text-left px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-600 hover:border-purple-300 hover:bg-purple-50/50 transition-all"
                  >
                    {tx}
                  </button>
                ))}
              </div>
            </div>
            {voiceTplInfo.pro_tips && (
              <div className="p-3 rounded-lg bg-purple-50 border border-purple-100">
                <div className="text-xs font-medium text-purple-700 mb-1">🎬 配音技巧</div>
                <div className="text-xs text-purple-700/80 leading-relaxed">
                  {voiceTplInfo.pro_tips}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* ── 重命名 Modal ── */}
      <Modal
        open={!!renaming}
        onClose={() => setRenaming(null)}
        title="重命名配音"
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
            placeholder="如：产品介绍口播 01"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
          />
        </div>
      </Modal>
    </div>
  )
}
