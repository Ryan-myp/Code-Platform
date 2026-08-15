import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic2,
  Sparkles,
  Play,
  Download,
  Trash2,
  UserCircle,
  Music2,
  Film,
  Eye,
  Clock,
  FileText,
  RefreshCw,
  Wand2,
  Check,
  Send,
  Image as ImageIcon,
  Palette,
  Radio,
  Volume2,
  Pause,
  StopCircle,
  Smile,
  Shirt,
  Monitor,
  Glasses,
  HardHat,
  Video,
  Circle,
  Camera,
  Upload,
  Rocket,
  X,
  ShieldCheck,
  Layers,
  ListChecks,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  LayoutGrid,
  Shuffle,
  AudioWaveform,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Modal, Badge } from '../components/ui'
import ShareButton from '../components/ShareButton'
import HistoryPanel from '../components/HistoryPanel'
import FavoriteButton from '../components/FavoriteButton'
import useToolHistory from '../hooks/useToolHistory'
import { useToast } from '../lib/toast'
import api, { API_BASE } from '../lib/api'
import { friendlyError } from '../lib/errors'
import AnimatedAvatar, {
  EXPRESSION_NAMES,
  OUTFIT_NAMES,
  SCENE_NAMES,
} from '../components/AnimatedAvatar'

const SCENES = [
  {
    id: 'product',
    name: '产品介绍',
    desc: '突出卖点，节奏明快',
    icon: Sparkles,
    color: 'from-amber-500 to-orange-600',
  },
  {
    id: 'course',
    name: '课程讲解',
    desc: '结构化讲解',
    icon: FileText,
    color: 'from-blue-500 to-indigo-600',
  },
  {
    id: 'news',
    name: '新闻播报',
    desc: '字正腔圆',
    icon: Radio,
    color: 'from-gray-700 to-gray-900',
  },
  {
    id: 'livestream',
    name: '直播带货',
    desc: '感染力强',
    icon: Wand2,
    color: 'from-pink-500 to-rose-600',
  },
  {
    id: 'story',
    name: '故事讲述',
    desc: '情感丰富',
    icon: Volume2,
    color: 'from-violet-500 to-purple-600',
  },
]

// 场景台词模板：点击场景卡片时自动填入示例口播（文案为空时），也可随机抽取
const SCENE_SCRIPTS = {
  product: [
    '大家好，今天给大家介绍一款全新的AI效率工具。它能在30秒内自动完成PPT大纲、数据分析、视频生成，让繁琐的工作变得像聊天一样简单。现在下单，立享限时五折优惠，错过再等一年！',
    '家人们，这款智能办公软件真的太方便了！一键生成周报、自动整理会议纪要、还能智能推荐最优方案。我已经用了三个月，工作效率直接翻倍，强烈推荐给每一位职场人！',
  ],
  course: [
    '同学们好，今天我们学习AI绘画的核心概念——提示词工程。首先，明确主题是创作的基础；其次，描述风格决定画面气质；最后，细节参数控制最终效果。我们通过三个实战案例来理解。',
    '这节课我们来讲数据分析的四大步骤：第一，明确分析目标；第二，数据清洗与预处理；第三，建模与计算；第四，可视化呈现结论。每一步都有对应的工具和方法，大家做好笔记。',
  ],
  news: [
    '各位观众朋友，大家好！今天是8月9日，欢迎收看今日科技快讯。首条消息：国内AI大模型应用市场规模持续扩大，预计年底突破千亿。接下来请看详细报道。',
    '本台消息：随着人工智能技术的快速发展，智慧医疗、智能制造等领域迎来新一轮变革。专家预计，未来五年相关产业将带动新增就业岗位超百万个。',
  ],
  livestream: [
    '欢迎来到直播间！今天这款产品我们直接给大家上福利价，原价399，今天直播间只要99！三、二、一，上链接！还没点关注的家人们先点亮红心，我们马上抽奖！',
    '来咯来咯！今天给大家炸一波福利——最新款智能手环，心率监测、睡眠分析、运动记录全都有，今天只要半价！库存不多，拍完即止，赶紧去抢！',
  ],
  story: [
    '从前有座山，山里有个小村庄。村里住着一位老工匠，他每天打磨一件器物，从不在乎时间。多年后，那些器物成了远近闻名的珍宝——原来，真正的价值，都藏在日复一日的坚持里。',
    '那是一个深秋的傍晚，我收到了一封迟到了十年的信。信上只有一句话：人生没有白走的路。多年后我才明白，当年那些看似无用的选择，恰恰铺成了通向梦想的唯一道路。',
  ],
}

// v13.24 数字人情绪选项（auto=LLM 自动判断文案情绪，声音+表情联动）
const EMOTION_OPTIONS = [
  { id: 'auto', label: '自动', icon: '✨' },
  { id: 'neutral', label: '自然', icon: '🙂' },
  { id: 'happy', label: '欢快', icon: '😄' },
  { id: 'sad', label: '悲伤', icon: '😢' },
  { id: 'angry', label: '激昂', icon: '🔥' },
  { id: 'gentle', label: '温柔', icon: '😊' },
  { id: 'serious', label: '严肃', icon: '🧐' },
]
const emotionLabel = (id) => EMOTION_OPTIONS.find((e) => e.id === id)?.label || id || '自动'

export default function DigitalHumanPage() {
  const toast = useRef(useToast()).current
  const { history: genHistory, add: addGenHistory, remove: removeGenHistory, clear: clearGenHistory } =
    useToolHistory('dh_factory_history_v1', 30)

  // 生成表单
  const [text, setText] = useState('')
  const [avatarId, setAvatarId] = useState('business-female')
  const [voiceId, setVoiceId] = useState('zh-CN-XiaoxiaoNeural')
  const [bgId, setBgId] = useState('tech')
  const [sceneId, setSceneId] = useState('product')
  const [templateId, setTemplateId] = useState('') // 行业模板（选模板自动填充场景/背景/音色/字幕样式）
  const [templates, setTemplates] = useState([]) // 行业模板库
  const [speed, setSpeed] = useState(1.0)
  const [emotion, setEmotion] = useState('auto') // v13.24 情绪：auto=LLM 自动判断
  const [generating, setGenerating] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  // 商业参数：分辨率 / 帧率 / 水印
  const [resolution, setResolution] = useState('720p')
  const [fps, setFps] = useState(24) // 默认 24fps 流畅档（画质优先，异步任务可等）
  const [watermark, setWatermark] = useState(false) // 会员可开关；免费用户由后端强制加水印
  const [engine, setEngine] = useState('2d') // 引擎：2d=基础渲染，live_portrait=照片数字人
  const [genPhase, setGenPhase] = useState('') // 生成阶段提示文案
  const [quota, setQuota] = useState(null) // 今日剩余额度
  const [storage, setStorage] = useState(null) // 我的存储用量（记录数/占用/保留期）

  // 异步生成任务：提交后后台执行，页面可关闭（进度/状态/重试）
  const [currentTask, setCurrentTask] = useState(null) // 当前生成任务（含进度/阶段）
  const [taskList, setTaskList] = useState([]) // 我的生成任务列表
  const taskTimerRef = useRef(null) // 任务轮询定时器
  const recordWhenDoneRef = useRef(false) // 生成完成后自动开始录制（「生成+录制」按钮）

  // 批量生产：多条文案后台逐条生成
  const [batchTexts, setBatchTexts] = useState('') // 批量文案（每行一条）
  const [batchTask, setBatchTask] = useState(null) // 批量任务进度
  const batchTimerRef = useRef(null) // 批量轮询定时器

  // AI 文案助手 + 合规预检
  const [showScriptModal, setShowScriptModal] = useState(false)
  const [scriptForm, setScriptForm] = useState({ topic: '', platform: 'douyin', tone: '专业' })
  const [scriptList, setScriptList] = useState([])
  const [scriptLoading, setScriptLoading] = useState(false)
  const [checkResult, setCheckResult] = useState(null) // 合规预检结果
  const [qualityResult, setQualityResult] = useState(null) // v15 文案体检结果
  const [qualityLoading, setQualityLoading] = useState(false) // v15 文案体检请求中

  // 数据
  const [avatars, setAvatars] = useState([])
  const [voices, setVoices] = useState([])
  const [backgrounds, setBackgrounds] = useState([])
  const [records, setRecords] = useState([])
  const [recordTotal, setRecordTotal] = useState(0)
  const [recordPage, setRecordPage] = useState(1)
  const [recordStatus, setRecordStatus] = useState('') // 状态筛选：''|done|audio_only|failed
  const [recordQuery, setRecordQuery] = useState('') // 关键词搜索
  const [selectedRecords, setSelectedRecords] = useState([]) // 批量删除选中
  const [result, setResult] = useState(null)

  // 自定义形象 / 声音（用户上传）
  const [customAvatars, setCustomAvatars] = useState([])
  const [customVoices, setCustomVoices] = useState([])
  const [showAvatarModal, setShowAvatarModal] = useState(false)
  const [showVoiceModal, setShowVoiceModal] = useState(false)
  const [showPhotoModal, setShowPhotoModal] = useState(false) // 照片数字人 （口型同步）上传
  const [showAiVideoModal, setShowAiVideoModal] = useState(false) // AI 视频（可灵大模型生成）
  const [showAiAvatarModal, setShowAiAvatarModal] = useState(false) // AI 形象（文生图→口型同步）
  const [aiVideoForm, setAiVideoForm] = useState({
    mode: 'text2video',
    prompt: '',
    imageUrl: '',
    audioUrl: '',
    duration: 5,
    resolution: '720p',
  }) // AI 视频表单
  const [aiAvatarForm, setAiAvatarForm] = useState({ prompt: '', name: 'AI 形象' }) // AI 形象表单
  const [aiSubmitting, setAiSubmitting] = useState(false) // AI 任务提交中
  const [aiGatewayCfg, setAiGatewayCfg] = useState(null) // AI 网关配置状态（价格/可用性）
  const [showCloneModal, setShowCloneModal] = useState(false) // 声音克隆（参数近似）上传
  const [avatarForm, setAvatarForm] = useState({ name: '', desc: '', file: null, preview: '' })
  const [photoForm, setPhotoForm] = useState({ name: '', file: null, preview: '' })
  const [voiceForm, setVoiceForm] = useState({ name: '', desc: '', file: null })
  const [cloneForm, setCloneForm] = useState({ name: '', file: null, authorized: false })
  const [cloning, setCloning] = useState(false) // 声音克隆任务中
  const [uploading, setUploading] = useState(false)

  // 云端素材：场景预设 + 写真画廊
  const [cloudScenes, setCloudScenes] = useState([])
  const [portraitList, setPortraitList] = useState([])

  // 文案素材库
  const [articles, setArticles] = useState([])
  const [showArticles, setShowArticles] = useState(false)

  // 角色外观
  const [outfit, setOutfit] = useState('formal')
  const [avatarScene, setAvatarScene] = useState('studio')
  const [glasses, setGlasses] = useState(false)
  const [hat, setHat] = useState(false)
  const [currentExpression, setCurrentExpression] = useState('neutral')

  // 音频播放 + 口型同步
  const audioRef = useRef(null)
  const avatarRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [talking, setTalking] = useState(false)
  const [audioUrl, setAudioUrl] = useState('')
  const [previewingVoice, setPreviewingVoice] = useState(false)

  // 录制
  const [recording, setRecording] = useState(false)
  const [videoBlob, setVideoBlob] = useState(null)

  // 视频预览
  const videoRef = useRef(null)
  const [previewVideoUrl, setPreviewVideoUrl] = useState('')
  const [playingVideo, setPlayingVideo] = useState(false)

  // ★ AI 写真肖像
  const [portraitMap, setPortraitMap] = useState({}) // avatarId → portraitUrl
  const [generatingPortrait, setGeneratingPortrait] = useState(new Set()) // 正在生成的 avatarId
  const [generatingAll, setGeneratingAll] = useState(false) // 是否在批量生成

  useEffect(() => {
    loadData()
    loadRecords(true)
    loadQuota()
    loadStorage()
  }, [])
  // 挂载时加载历史生成任务；卸载时停止轮询
  useEffect(() => {
    loadTasks()
    // AI 视频网关状态（价格/是否已配置）
    api
      .get('/api/ai-video/config')
      .then((r) => setAiGatewayCfg(r.data))
      .catch(() => setAiGatewayCfg({ configured: false }))
  }, [])
  useEffect(() => () => clearInterval(taskTimerRef.current), [])

  // 额度变化时刷新（其他页面的计费操作也会派发该事件）
  useEffect(() => {
    const refresh = () => loadQuota()
    window.addEventListener('quota-changed', refresh)
    return () => window.removeEventListener('quota-changed', refresh)
  }, [])

  // 今日剩余额度（/api/auth/quota → get_quota_info 结构）
  const loadQuota = async () => {
    try {
      const res = await api.get('/api/auth/quota')
      setQuota(res.data)
    } catch {
      /* 静默失败 */
    }
  }

  // 会员或管理员（管理员后端豁免水印/1080p/额度限制，前端同步放行）
  const isMember = () =>
    quota?.membership === 'vip' || quota?.membership === 'pro' || quota?.role === 'admin'

  // 我的存储用量（/api/digital-human/storage → 记录数/文件数/磁盘占用/保留期）
  const loadStorage = async () => {
    try {
      const res = await api.get('/api/digital-human/storage')
      setStorage(res.data)
    } catch {
      /* 静默失败 */
    }
  }

  const loadData = async () => {
    try {
      const [aRes, vRes, bRes] = await Promise.all([
        api.get('/api/digital-human/avatars'),
        api.get('/api/digital-human/voices'),
        api.get('/api/digital-human/backgrounds'),
      ])
      api
        .get('/api/digital-human/scenes')
        .then((res) => setCloudScenes(res.data?.scenes || []))
        .catch(() => {})
      api
        .get('/api/digital-human/templates')
        .then((res) => setTemplates(res.data?.templates || []))
        .catch(() => {})
      api
        .get('/api/digital-human/portraits')
        .then((res) => setPortraitList(res.data?.portraits || []))
        .catch(() => {})
      // 自定义形象/声音（需登录，失败静默）
      api
        .get('/api/digital-human/custom-avatars')
        .then((res) => {
          const list = res.data?.avatars || []
          setCustomAvatars(list)
          // 自定义形象直接展示上传图片（无需 AI 写真）
          const pm = {}
          list.forEach((a) => {
            if (a.image_url) pm[a.id] = a.image_url
          })
          setPortraitMap((prev) => ({ ...prev, ...pm }))
        })
        .catch(() => {})
      api
        .get('/api/digital-human/custom-voices')
        .then((res) => setCustomVoices(res.data?.voices || []))
        .catch(() => {})
      const avatarList = aRes.data?.avatars || []
      setAvatars(avatarList)
      setVoices(vRes.data?.voices || [])
      setBackgrounds(bRes.data?.backgrounds || [])
      // 构建写真映射（相对路径走 vite/nginx 代理，同源加载避免 CORS 缓存问题）
      const pm = {}
      avatarList.forEach((a) => {
        if (a.has_portrait && a.portrait_url) {
          pm[a.id] = a.portrait_url.startsWith('http') ? a.portrait_url : a.portrait_url
        }
      })
      setPortraitMap(pm)
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  // 历史记录分页查询：状态筛选 + 关键词搜索
  const loadRecords = async (reset = false, status = recordStatus, q = recordQuery) => {
    try {
      const page = reset ? 1 : recordPage
      const res = await api.get('/api/digital-human/records', {
        params: { page, page_size: 20, status, q },
      })
      const items = res.data?.items || []
      setRecords((prev) => (reset ? items : [...prev, ...items]))
      setRecordTotal(res.data?.total || 0)
      setRecordPage(res.data?.page || 1)
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  // ★ 上传自定义形象（自己的头像/照片 → 数字人形象）
  const uploadCustomAvatar = async () => {
    if (!avatarForm.file) {
      toast.error('请先选择一张图片（jpg/png/webp）')
      return
    }
    if (!avatarForm.name.trim()) {
      toast.error('请输入形象名称')
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', avatarForm.file)
      fd.append('name', avatarForm.name.trim())
      fd.append('desc', avatarForm.desc.trim())
      const res = await api.post('/api/digital-human/custom-avatars', fd)
      const av = res.data?.avatar
      setAvatarForm({ name: '', desc: '', file: null, preview: '' })
      setShowAvatarModal(false)
      setCustomAvatars((prev) => [...prev, av])
      if (av?.image_url) setPortraitMap((prev) => ({ ...prev, [av.id]: av.image_url }))
      setAvatarId(av.id) // 上传后直接选中，便于立即试用
      toast.success(`自定义形象「${av.name}」已创建，可直接生成视频`)
    } catch (e) {
      toast.error(`上传失败：${e.message}`)
    } finally {
      setUploading(false)
    }
  }

  // ★ 提交 AI 视频生成任务（可灵大模型/AGNES：文生视频/图生视频/口型同步/照片活化）
  const submitAiVideo = async () => {
    if (!aiVideoForm.prompt.trim()) {
      toast.error('请输入视频内容描述')
      return
    }
    if (!aiGatewayCfg?.configured) {
      // AGNES key 已配置时也可用（照片活化+自动配音混合方案）
      if (aiVideoForm.mode === 'lipsync' && !aiVideoForm.imageUrl) {
        toast.error('混合数字人需上传参考照片（选择图生视频/口型同步并填照片路径）')
        return
      }
    }
    // 口型同步：无音频时后端自动用文案 TTS 配音（混合方案）
    setAiSubmitting(true)
    try {
      const res = await api.post('/api/ai-video/generate', aiVideoForm)
      toast.success(res.data?.message || 'AI 视频任务已提交')
      setShowAiVideoModal(false)
      loadTasks()
    } catch (e) {
      toast.error(friendlyError(e) || '提交失败')
    } finally {
      setAiSubmitting(false)
    }
  }

  // ★ 提交 AI 形象生成任务（万相文生图 → 自动创建照片数字人形象）
  const submitAiAvatar = async () => {
    if (aiAvatarForm.prompt.trim().length < 8) {
      toast.error('请至少输入 8 个字描述形象（如：一位 30 岁中国女性职场精英，正脸证件照风格）')
      return
    }
    if (!aiGatewayCfg?.configured) {
      toast.error('AI 形象网关未配置（需 DASHSCOPE_API_KEY），请联系平台管理员')
      return
    }
    setAiSubmitting(true)
    try {
      const res = await api.post('/api/ai-video/avatar-image', aiAvatarForm)
      toast.success(res.data?.message || 'AI 形象任务已提交（约 30-60 秒）')
      setShowAiAvatarModal(false)
      loadTasks()
    } catch (e) {
      toast.error(friendlyError(e) || '提交失败')
    } finally {
      setAiSubmitting(false)
    }
  }

  // ★ 从生成记录复制音频链接（供 AI 视频口型同步模式使用）
  const copyAudioUrl = () => {
    if (!audioUrl) {
      toast.error('暂无配音音频链接（先生成一次数字人视频）')
      return
    }
    navigator.clipboard?.writeText(audioUrl.replace(API_BASE, '').replace(/^\/+/, '/'))
    toast.success('音频链接已复制（可在 AI 视频口型同步模式粘贴）')
  }

  // ★ 上传照片数字人形象（正脸照片 → 口型同步引擎）
  const uploadPhotoAvatar = async () => {
    if (!photoForm.file) {
      toast.error('请选择照片')
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', photoForm.file)
      fd.append('name', photoForm.name.trim() || '我的照片形象')
      const res = await api.post('/api/digital-human/photo-avatar', fd)
      const av = res.data?.avatar
      setShowPhotoModal(false)
      setPhotoForm({ name: '', file: null, preview: '' })
      // 刷新自定义形象列表（含照片形象）
      try {
        const cRes = await api.get('/api/digital-human/custom-avatars')
        const list = cRes.data?.avatars || []
        setCustomAvatars(list)
        const pm = {}
        list.forEach((a) => {
          if (a.image_url) pm[a.id] = a.image_url
        })
        setPortraitMap((prev) => ({ ...prev, ...pm }))
      } catch {
        /* 静默失败，不阻塞上传流程 */
      }
      if (av?.id) {
        setAvatarId(av.id) // 上传后直接选中
        setEngine('live_portrait') // 照片形象自动切换照片引擎
      }
      toast.success(`照片数字人「${av?.name || '我的照片形象'}」已创建，可生成口型同步视频`)
    } catch (e) {
      toast.error(`上传失败：${e.message}`)
    } finally {
      setUploading(false)
    }
  }

  // ★ 上传自定义声音（自己的录音/音频 → 数字人配音）
  const uploadCustomVoice = async () => {
    if (!voiceForm.file) {
      toast.error('请先选择一个音频文件（mp3/wav/m4a）')
      return
    }
    if (!voiceForm.name.trim()) {
      toast.error('请输入声音名称')
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', voiceForm.file)
      fd.append('name', voiceForm.name.trim())
      fd.append('desc', voiceForm.desc.trim())
      const res = await api.post('/api/digital-human/custom-voices', fd)
      const v = res.data?.voice
      setVoiceForm({ name: '', desc: '', file: null })
      setShowVoiceModal(false)
      setCustomVoices((prev) => [...prev, v])
      setVoiceId(v.id) // 上传后直接选中
      toast.success(`自定义声音「${v.name}」已创建，生成时直接使用该音频作为配音`)
    } catch (e) {
      toast.error(`上传失败：${e.message}`)
    } finally {
      setUploading(false)
    }
  }

  const deleteCustomAvatar = async (id) => {
    try {
      await api.delete(`/api/digital-human/custom-avatars/${id}`)
      setCustomAvatars((prev) => prev.filter((a) => a.id !== id))
      if (avatarId === id) setAvatarId('business-female')
      toast.success('已删除自定义形象')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const deleteCustomVoice = async (id) => {
    try {
      await api.delete(`/api/digital-human/custom-voices/${id}`)
      setCustomVoices((prev) => prev.filter((v) => v.id !== id))
      if (voiceId === id) setVoiceId('zh-CN-XiaoxiaoNeural')
      toast.success('已删除自定义声音')
    } catch (e) {
      toast.error(e.message)
    }
  }

  // ★ 声音克隆（上传 10-60s 人声样本 → AI 分析基频 → 匹配音色+音调补偿；合规必选声明）
  const submitVoiceClone = async () => {
    if (!cloneForm.file) {
      toast.error('请先选择人声样本（mp3/wav/m4a，10-60 秒）')
      return
    }
    if (!cloneForm.name.trim()) {
      toast.error('请输入克隆声音名称')
      return
    }
    if (!cloneForm.authorized) {
      toast.error('请先勾选「本人声音或已获授权」声明（合规必选）')
      return
    }
    setCloning(true)
    try {
      const fd = new FormData()
      fd.append('file', cloneForm.file)
      fd.append('voice_name', cloneForm.name.trim())
      fd.append('declare_authorized', 'true')
      const res = await api.post('/api/digital-human/voice-clone', fd)
      const taskId = res.data?.task_id
      toast.success('声音克隆任务已提交，正在分析人声特征…')
      // 轮询异步任务（分析 10-60s 样本约 1-3s，最多等 60s；任务终态为 success/failed）
      for (let i = 0; i < 60; i += 1) {
        await new Promise((r) => setTimeout(r, 1000))
        const tRes = await api.get(`/api/tasks/${taskId}`)
        const t = tRes.data
        if (t?.status === 'success') {
          setShowCloneModal(false)
          setCloneForm({ name: '', file: null, authorized: false })
          // 刷新声音列表（克隆声音自动并入 custom-voices）
          const cRes = await api.get('/api/digital-human/custom-voices')
          setCustomVoices(cRes.data?.voices || [])
          if (t?.result?.voice_id) setVoiceId(t.result.voice_id) // 完成后直接选中
          toast.success(`克隆声音「${cloneForm.name.trim()}」已创建，可直接用于数字人配音`)
          return
        }
        if (['failed', 'canceled', 'interrupted'].includes(t?.status)) {
          throw new Error(t?.error || '声音克隆任务失败，请重试')
        }
      }
      throw new Error('声音克隆分析超时，请稍后在声音列表查看')
    } catch (e) {
      toast.error(`克隆失败：${e.message}`)
    } finally {
      setCloning(false)
    }
  }

  // 会员剩余时长人性化展示：超长有效期不显示天数为（避免“剩余 26806 天”的观感问题）
const fmtDaysLeft = (days) => {
  if (days >= 3650) return '长期有效'
  if (days >= 365) return `剩余 ${Math.floor(days / 365)} 年 ${days % 365 > 0 ? `${days % 365} 天` : ''}`
  return `剩余 ${days} 天`
}

// ★ 删除克隆音色（合规风控：授权撤销/滥用后立即停用并删除样本）
  const revokeVoiceClone = async (id) => {
    if (!window.confirm('删除后该克隆音色立即停用且样本文件被删除，确认删除？')) return
    try {
      await api.post(`/api/digital-human/voice-clones/${id}/revoke`)
      setCustomVoices((prev) => prev.filter((v) => v.id !== id))
      if (voiceId === id) setVoiceId('zh-CN-XiaoxiaoNeural')
      toast.success('克隆音色已删除，不可再用于生成')
    } catch (e) {
      toast.error(e.message)
    }
  }

  // ★ 发布视频到内容平台（复用发布中心的账号矩阵与素材包能力）
  const publishVideo = async (videoUrl, contentText, recordName) => {
    const platform = window.prompt(
      '选择发布平台：请输入 douyin（抖音）/ kuaishou（快手）/ wechat（公众号）'
    )
    if (!platform || !['douyin', 'kuaishou', 'wechat'].includes(platform)) return
    try {
      const res = await api.post('/api/publish/submit', {
        platform,
        content_type: 'video',
        title: `数字人视频 - ${recordName || '口播'}`,
        content: (contentText || '').slice(0, 2000),
        topics: ['数字人', 'AI'],
        asset_urls: [videoUrl],
      })
      const mode = res.data?.mode
      if (mode === 'auto') {
        toast.success(
          `已自动发布到${res.data?.platform_label || platform}！${res.data?.message || ''}`
        )
      } else {
        toast.info('已生成发布素材包：请到发布中心查看引导步骤完成发布')
        window.open(`/publish`, '_blank')
      }
    } catch (e) {
      toast.error(`发布失败：${e.message}`)
    }
  }

  // ★ 生成单个数字人写真
  const generatePortrait = async (avatarId) => {
    const av = avatars.find((a) => a.id === avatarId)
    if (!av) return
    // 避免重复生成
    if (generatingPortrait.has(avatarId)) return
    const newSet = new Set(generatingPortrait)
    newSet.add(avatarId)
    setGeneratingPortrait(newSet)
    toast.info(`正在为 ${av.name} 生成AI写真...`)
    try {
      const res = await api.post(`/api/digital-human/generate-portrait/${avatarId}`)
      // 相对路径走代理，同源加载（避免绝对地址跨域 CORS 缓存问题）
      const portraitUrl = res.data.url
      setPortraitMap((prev) => ({ ...prev, [avatarId]: portraitUrl }))
      toast.success(`${av.name} 写真生成成功！`)
      // 刷新 avatar 列表以更新 has_portrait 状态
      loadData()
    } catch (e) {
      toast.error(`${av.name} 写真生成失败：${e.message || '请稍后重试'}`)
    } finally {
      const finalSet = new Set(generatingPortrait)
      finalSet.delete(avatarId)
      setGeneratingPortrait(finalSet)
    }
  }

  // ★ 一键生成全部写真
  const generateAllPortraits = async () => {
    setGeneratingAll(true)
    toast.info('正在批量生成所有数字人写真，可能需要几分钟...')
    try {
      const res = await api.post('/api/digital-human/generate-all-portraits')
      const { generated, cached, failed } = res.data
      if (generated > 0 || cached > 0) {
        toast.success(
          `写真生成完成！新增 ${generated} 个，已有 ${cached} 个${failed > 0 ? `，失败 ${failed} 个` : ''}`
        )
        loadData() // 刷新
      } else {
        toast.error('所有写真生成失败，请检查API配置')
      }
    } catch (e) {
      toast.error(`批量生成失败：${e.message}`)
    } finally {
      setGeneratingAll(false)
    }
  }

  const loadArticles = async () => {
    try {
      const res = await api.get('/api/publish/assets')
      setArticles(res.data?.articles || [])
      setShowArticles(true)
    } catch {
      toast.error('加载文案失败')
    }
  }

  // ── 异步生成任务：提交 → 后台执行 → 轮询进度/结果（页面可关闭）──
  const formatTaskTime = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    const p = (n) => String(n).padStart(2, '0')
    return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  }

  const loadTasks = async () => {
    try {
      const res = await api.get('/api/tasks', {
        params: { type: 'dh_generate,ai_video,ai_avatar_image', limit: 8 },
      })
      setTaskList(res.data?.tasks || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  // 任务完成后：展示结果 + 预览音视频 + 刷新记录/额度
  const handleTaskDone = (result) => {
    setResult(result || {})
    if (result?.status === 'done' || result?.video_url || result?.audio_url) {
      addGenHistory({ type: '数字人', content: (text.trim() || '口播视频').slice(0, 50) })
    }
    loadRecords(true)
    loadQuota()
    loadStorage()
    if (result?.video_url) playPreviewVideo(result.video_url)
    if (result?.audio_url) {
      const fullUrl = result.audio_url.startsWith('http')
        ? result.audio_url
        : `${API_BASE}${result.audio_url}`
      setAudioUrl(fullUrl)
      // 延迟确保 audio 元素挂载后再播放
      setTimeout(() => {
        if (audioRef.current) {
          audioRef.current
            .play()
            .then(() => {
              setPlaying(true)
              setTalking(true)
            })
            .catch(() => {})
        }
      }, 300)
    }
  }

  // 轮询任务列表：一次请求同时刷新当前任务进度与历史列表
  const pollTasks = (taskId) => {
    clearInterval(taskTimerRef.current)
    taskTimerRef.current = setInterval(async () => {
      try {
        const res = await api.get('/api/tasks', { params: { type: 'dh_generate', limit: 10 } })
        const list = res.data?.tasks || []
        setTaskList(list)
        const t = list.find((x) => x.id === taskId)
        if (!t) return
        setCurrentTask(t)
        if (t.status === 'success') {
          clearInterval(taskTimerRef.current)
          setGenerating(false)
          handleTaskDone(t.result || {})
          toast.success(t.result?.message || '数字人视频生成成功')
          // 「生成+录制」模式：音频就绪后自动开始录制
          if (recordWhenDoneRef.current) {
            recordWhenDoneRef.current = false
            setTimeout(() => {
              if (audioRef.current && avatarRef.current) {
                avatarRef.current.startRecording()
                setRecording(true)
                audioRef.current
                  .play()
                  .then(() => {
                    setPlaying(true)
                    setTalking(true)
                  })
                  .catch(() => {})
              }
            }, 300)
          }
        } else if (['failed', 'interrupted', 'canceled'].includes(t.status)) {
          clearInterval(taskTimerRef.current)
          setGenerating(false)
          setGenPhase('')
          if (t.status === 'canceled') {
            toast.info('任务已取消')
          } else if (t.error_code === 402) {
            // 402 额度耗尽：全局已提示并引导升级（QuotaExhaustedNotifier），此处仅打开会员页
            window.open('/membership', '_blank')
          } else {
            toast.error(`生成失败：${friendlyError(t.error)}`)
          }
        }
      } catch {
        // 网络抖动：保留轮询，下次继续
      }
    }, 2000)
  }

  // 行业模板：一键套用场景/背景/音色/字幕样式（字幕样式与片头片尾由后端按模板渲染）
  const applyTemplate = (t) => {
    setTemplateId(t.id)
    setSceneId(t.scene_id)
    setBgId(t.background_id)
    if (t.voice_hint) setVoiceId(t.voice_hint)
    if (t.speed_hint) setSpeed(t.speed_hint)
    // v15：模板附带可直接填充的示例文案，文案为空时自动填入（{占位符} 需用户替换）
    if (t.script_sample && !text.trim()) {
      setText(t.script_sample)
      toast.success(`已套用「${t.name}」模板：示例文案已填入，请替换{占位符}内容`)
    } else {
      toast.success(`已套用「${t.name}」模板：场景/背景/音色/字幕样式已按模板填充`)
    }
  }
  const clearTemplate = () => {
    setTemplateId('')
    toast.info('已退出模板模式，恢复手动配置')
  }

  // 提交生成任务（普通生成 / 生成+录制共用）
  const submitTask = async (recordAfterDone) => {
    if (!text.trim()) {
      toast.error('请输入口播文案')
      return
    }
    setGenerating(true)
    setResult(null)
    stopAudio()
    setGenPhase('')
    if (recordAfterDone) setVideoBlob(null)
    recordWhenDoneRef.current = !!recordAfterDone
    try {
      const res = await api.post('/api/digital-human/generate', {
        text: text.trim(),
        avatar_id: avatarId,
        voice_id: voiceId,
        background_id: bgId,
        scene_id: sceneId,
        template_id: templateId,
        speed,
        resolution,
        fps,
        watermark,
        emotion,
        engine,
      })
      if (res.data?.task_id) {
        // 异步任务模式：立即返回 task_id，后台 worker 执行
        setCurrentTask({
          id: res.data.task_id,
          status: 'pending',
          progress: 0,
          stage: '任务排队中…',
        })
        toast.info('生成任务已提交，后台执行中，可关闭页面稍后查看')
        pollTasks(res.data.task_id)
      } else {
        // 兼容同步模式响应（sync=1 或旧后端）
        handleTaskDone(res.data)
        setGenerating(false)
        toast.success(res.data.message || '生成成功')
      }
    } catch (e) {
      setGenerating(false)
      if (e.status === 402) {
        // 402 额度耗尽：全局已提示并引导升级，此处仅打开会员页
        window.open('/membership', '_blank')
      } else {
        toast.error(`生成失败：${e.message}`)
      }
    }
  }

  const generate = () => submitTask(false)
  const recordAndPlay = () => submitTask(true)

  // 重试失败/中断的任务：重新排队执行
  const retryTask = async (t) => {
    try {
      await api.post(`/api/tasks/${t.id}/retry`)
      setGenerating(true)
      setCurrentTask({ id: t.id, status: 'pending', progress: 0, stage: '任务已重新提交…' })
      toast.info('任务已重新提交，后台重新执行中')
      pollTasks(t.id)
    } catch (e) {
      toast.error(`重试失败：${e.message}`)
    }
  }

  const playAudio = useCallback(() => {
    if (!audioRef.current) return
    audioRef.current
      .play()
      .then(() => {
        setPlaying(true)
        setTalking(true)
      })
      .catch(() => {})
  }, [])

  const pauseAudio = useCallback(() => {
    if (!audioRef.current) return
    audioRef.current.pause()
    setPlaying(false)
    setTalking(false)
  }, [])

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    setPlaying(false)
    setTalking(false)
  }, [])

  // v22：口型同步质量评估（音频能量 × 文字读音匹配度）
  const [lipCheck, setLipCheck] = useState(null)
  const [lipChecking, setLipChecking] = useState(false)
  const checkLipSync = async () => {
    if (!result?.audio_url) return
    setLipChecking(true)
    setLipCheck(null)
    try {
      const fd = new FormData()
      fd.append('audio_path', result.audio_url)
      fd.append('script_text', result?.text_length ? '' : '')
      const res = await api.post('/api/digital-human/lip-sync/quality', fd, { timeout: 60000 })
      setLipCheck(res.data)
    } catch (e) {
      toast.error(`口型检测失败：${e.message}`)
    } finally {
      setLipChecking(false)
    }
  }

  // 口播试听：TTS 短句预览（复用 voice_factory 全降级链，生成前先验证音频效果）
  const previewVoice = useCallback(async () => {
    const sample = text.trim()
    if (!sample) {
      toast.error('请先输入口播文案')
      return
    }
    if (customVoices.some((v) => v.id === voiceId)) {
      toast.error('自定义/克隆声音不支持试听，请选择系统音色')
      return
    }
    setPreviewingVoice(true)
    try {
      stopAudio()
      const form = new FormData()
      form.append('voice', voiceId)
      form.append('text', sample.slice(0, 80))
      const res = await api.post('/api/voice/preview', form, {
        responseType: 'blob',
        timeout: 60000,
      })
      const url = URL.createObjectURL(res.data)
      setAudioUrl((prev) => {
        if (prev && prev.startsWith('blob:')) URL.revokeObjectURL(prev)
        return url
      })
      // 等待 audio 元素挂载后自动播放
      setTimeout(() => {
        if (audioRef.current) {
          audioRef.current
            .play()
            .then(() => {
              setPlaying(true)
              setTalking(true)
            })
            .catch(() => {})
        }
      }, 100)
      toast.success('试听已就绪，正在播放')
    } catch (e) {
      const msg =
        e.status === 400 || e.status === 404
          ? `当前音色暂不支持试听：${e.message}`
          : `试听失败：${e.message}`
      toast.error(msg)
    } finally {
      setPreviewingVoice(false)
    }
  }, [text, voiceId, customVoices, stopAudio, toast])

  // ── 录制控制 ──
  const startRecording = useCallback(() => {
    if (!avatarRef.current) {
      toast.error('角色未就绪')
      return
    }
    avatarRef.current.startRecording()
    setRecording(true)
    setVideoBlob(null)
    toast.success('开始录制')
  }, [toast])

  const stopRecording = useCallback(async () => {
    if (!avatarRef.current) return
    const blob = await avatarRef.current.stopRecording()
    setRecording(false)
    if (blob) {
      setVideoBlob(blob)
      toast.success('录制完成')
    } else toast.error('录制失败')
  }, [toast])

  const downloadVideo = useCallback(() => {
    if (!videoBlob) return
    const url = URL.createObjectURL(videoBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = `digital-human-${Date.now()}.webm`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('下载中')
  }, [videoBlob, toast])

  // 通用文件下载（通过 axios blob 获取，支持认证 + 跨域）
  const downloadFile = useCallback(
    async (urlPath, filename) => {
      try {
        const res = await api.get(urlPath, { responseType: 'blob' })
        const blobUrl = URL.createObjectURL(res.data)
        const a = document.createElement('a')
        a.href = blobUrl
        a.download = filename
        a.click()
        setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
      } catch {
        toast.error('下载失败')
      }
    },
    [toast]
  )

  // 播放服务器生成的视频
  const playPreviewVideo = useCallback((url) => {
    const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`
    setPreviewVideoUrl(fullUrl)
    setPlayingVideo(false)
    // 等 video 元素挂载后播放
    setTimeout(() => {
      if (videoRef.current) {
        videoRef.current
          .play()
          .then(() => setPlayingVideo(true))
          .catch(() => {})
      }
    }, 200)
  }, [])

  // 音频结束时停止录制
  useEffect(() => {
    if (!playing && recording && avatarRef.current) {
      avatarRef.current.stopRecording().then((blob) => {
        setRecording(false)
        if (blob) setVideoBlob(blob)
      })
    }
  }, [playing, recording])

  // 卸载时停止批量轮询
  useEffect(() => () => clearInterval(batchTimerRef.current), [])

  const deleteRecord = async (id) => {
    try {
      await api.delete(`/api/digital-human/records/${id}`)
      loadRecords(true)
      toast.success('已删除')
    } catch (e) {
      toast.error(e.message)
    }
  }

  // ── 批量删除 ──
  const toggleRecordSelect = (id) => {
    setSelectedRecords((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }
  const toggleSelectAll = () => {
    const ids = records.map((r) => r.id)
    setSelectedRecords((prev) => (prev.length === records.length && records.length > 0 ? [] : ids))
  }
  const batchDelete = async () => {
    if (selectedRecords.length === 0) return
    try {
      const res = await api.post('/api/digital-human/records/batch-delete', {
        ids: selectedRecords,
      })
      setSelectedRecords([])
      loadRecords(true)
      toast.success(`已批量删除 ${res.data?.deleted || selectedRecords.length} 条记录`)
    } catch (e) {
      toast.error(`批量删除失败：${e.message}`)
    }
  }

  // ── 重新生成：回填该记录的全部参数后立即生成 ──
  const reuseRecord = async (r) => {
    setText(r.text || '')
    if (r.avatar_id) setAvatarId(r.avatar_id)
    if (r.voice_id) setVoiceId(r.voice_id)
    if (r.emotion) setEmotion(r.emotion) // v13.24 回填情绪（旧记录无情绪则保持当前选择）
    if (r.background_id) setBgId(r.background_id)
    if (r.scene_id) setSceneId(r.scene_id)
    if (r.resolution) setResolution(r.resolution)
    if (r.fps) setFps(r.fps)
    toast.info('已回填该记录的参数，正在重新生成…')
    // 等待 state 更新后再生成
    setTimeout(() => {
      generate()
    }, 100)
  }

  // ── 复制文案到剪贴板 ──
  const copyText = async (r) => {
    try {
      await navigator.clipboard.writeText(r.text || '')
      toast.success('文案已复制到剪贴板')
    } catch {
      toast.error('复制失败，请手动复制')
    }
  }

  // ── 批量生产：多条文案后台逐条生成 ──
  const runBatch = async () => {
    const texts = batchTexts
      .split('\n')
      .map((t) => t.trim())
      .filter(Boolean)
    if (texts.length === 0) {
      toast.error('请输入至少一条文案（每行一条）')
      return
    }
    if (texts.length > 50) {
      toast.error('单次最多 50 条文案')
      return
    }
    try {
      const res = await api.post('/api/digital-human/batch', {
        texts,
        avatar_id: avatarId,
        voice_id: voiceId,
        background_id: bgId,
        scene_id: sceneId,
        speed,
        resolution,
        fps,
        watermark,
        emotion,
      })
      setBatchTask(res.data)
      setCheckResult(null)
      toast.info(`批量任务已启动：${res.data.total} 条文案，后台逐条生成中…`)
      pollBatch(res.data.batch_id)
    } catch (e) {
      if (e.status === 402) {
        // 402 额度耗尽：全局已提示并引导升级，此处仅打开会员页
        window.open('/membership', '_blank')
      } else {
        toast.error(`批量生成失败：${e.message}`)
      }
    }
  }

  const pollBatch = (batchId) => {
    clearInterval(batchTimerRef.current)
    batchTimerRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/api/digital-human/batch/${batchId}`)
        setBatchTask(res.data)
        if (res.data.status === 'done' || res.data.status === 'interrupted') {
          clearInterval(batchTimerRef.current)
          loadRecords(true)
          loadQuota()
          loadStorage()
          if (res.data.status === 'done') {
            toast.success(
              `批量生成完成：成功 ${res.data.success} / 失败 ${res.data.failed}${res.data.skipped > 0 ? ` / 跳过 ${res.data.skipped}` : ''}`
            )
          } else {
            toast.error('批量任务已中断（服务重启导致），可点击「重试失败项」继续')
          }
        }
      } catch {
        clearInterval(batchTimerRef.current)
      }
    }, 2500)
  }

  const downloadBatch = () => {
    if (!batchTask?.batch_id) return
    downloadFile(`/api/digital-human/batch/${batchTask.batch_id}/download`, '数字人批量视频.zip')
  }

  // ── 重试批量任务失败项（服务中断/偶发失败恢复后使用）──
  const retryBatchFailed = async () => {
    if (!batchTask?.batch_id || !batchTask.failed) return
    try {
      const res = await api.post(`/api/digital-human/batch/${batchTask.batch_id}/retry-failed`)
      setBatchTask((prev) => (prev ? { ...prev, status: 'running', finished_at: '' } : res.data))
      toast.info(`已重新提交 ${res.data.retrying} 条失败项，正在重试…`)
      pollBatch(res.data.batch_id)
    } catch (e) {
      toast.error(`重试失败：${e.message}`)
    }
  }

  // ── AI 口播文案助手 ──
  const generateScripts = async () => {
    if (!scriptForm.topic.trim()) {
      toast.error('请输入口播主题')
      return
    }
    setScriptLoading(true)
    try {
      const res = await api.post('/api/digital-human/script-assist', {
        ...scriptForm,
        scene_id: sceneId,
        template_id: templateId,
      })
      setScriptList(res.data?.scripts || [])
      if (!res.data?.scripts?.length) toast.error('生成失败，请重试')
    } catch (e) {
      toast.error(`生成失败：${e.message}`)
    } finally {
      setScriptLoading(false)
    }
  }

  const applyScript = (s) => {
    setText(s)
    setShowScriptModal(false)
    toast.success('已填入文案框，可继续编辑')
  }

  // 场景联动：切换场景；文案为空时自动填该场景示例口播
  const selectScene = (id) => {
    setSceneId(id)
    if (!text.trim()) {
      const pool = SCENE_SCRIPTS[id]
      if (pool?.length) {
        setText(pool[0])
        toast.success(`已填「${SCENES.find((s) => s.id === id)?.name || ''}」示例口播`)
      }
    }
  }

  // 随机台词：优先当前场景池，否则全场景池抽取
  const pickRandomScript = () => {
    const pool = SCENE_SCRIPTS[sceneId]
    const all = Object.values(SCENE_SCRIPTS).flat()
    const list = pool?.length ? pool : all
    setText(list[Math.floor(Math.random() * list.length)])
    toast.success('已随机填入口播文案')
  }

  // ── 合规预检：生成前检查违禁词/风险词 ──
  const checkCompliance = async () => {
    if (!text.trim()) {
      toast.error('请先输入文案')
      return
    }
    try {
      const res = await api.post('/api/digital-human/compliance-check', { text })
      setCheckResult(res.data)
      if (res.data.allowed) {
        toast.success(
          res.data.risk_hits.length
            ? '检查通过（含风险词提示，建议修改）'
            : '文案合规，可以放心生成'
        )
      } else {
        toast.error(`含违规词：${res.data.hard_hits.join('、')}，无法生成`)
      }
    } catch (e) {
      toast.error(`检查失败：${e.message}`)
    }
  }

  // ── v15 文案体检：长句无停顿/emoji/长数字/长英文等口型友好性检查 ──
  const checkScriptQuality = async () => {
    if (!text.trim()) {
      toast.error('请先输入文案')
      return
    }
    setQualityLoading(true)
    try {
      const res = await api.post('/api/digital-human/script-check', { text })
      setQualityResult(res.data)
      if (res.data?.ok) {
        toast.success(`朗读友好 ✓ 约 ${res.data.estimate_sec} 秒（${res.data.char_count} 字）`)
      }
    } catch (e) {
      toast.error(`体检失败：${e.message}`)
    } finally {
      setQualityLoading(false)
    }
  }

  // 应用体检自动修复：去 emoji/特殊符号 + 数字转中文 + 空行折叠
  const applyQualityFix = () => {
    if (!qualityResult?.fixed_text) return
    setText(qualityResult.fixed_text)
    setQualityResult(null)
    toast.success('已应用修复版文案（可继续编辑）')
  }

  const loadArticle = (a) => {
    setText(a.result || a.prompt || '')
    setShowArticles(false)
    toast.success('已加载文案')
  }

  const selectedAvatar = avatars.find((a) => a.id === avatarId)
  const selectedVoice = voices.find((v) => v.id === voiceId)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI数字人"
        description="文案→配音→口播视频，12款虚拟形象（含性感女神/甜美女神）+ AI写真肖像 + 8种音色，一键生成专业数字人口播视频"
        icon={UserCircle}
        iconColor="from-violet-500 to-purple-600"
      />

      {/* 商业配额条：今日剩余生成次数 + 会员状态 */}
      {quota && (
        <div
          className={`flex flex-wrap items-center gap-3 px-4 py-2.5 rounded-xl border text-xs ${
            quota.remaining_today > 5
              ? 'bg-white border-gray-200 text-gray-600'
              : 'bg-amber-50 border-amber-200 text-amber-700'
          }`}
        >
          <span className="font-medium">
            今日剩余生成次数：
            <span
              className={
                quota.remaining_today > 5 ? 'text-violet-600 font-bold' : 'text-red-500 font-bold'
              }
            >
              {quota.remaining_today}
            </span>
            {quota.daily_quota ? ` / ${quota.daily_quota} 次` : ''}
          </span>
          {isMember() ? (
            <span className="flex items-center gap-1 text-emerald-600">
              <Sparkles className="w-3 h-3" />{' '}
              {quota.membership === 'vip' ? '至尊版 · 不限量' : '专业版'}会员
              {quota.membership_days_left != null && `（${fmtDaysLeft(quota.membership_days_left)}）`}
            </span>
          ) : (
            <a
              href="/membership"
              className="text-violet-600 hover:text-violet-800 font-medium underline underline-offset-2"
            >
              免费版每日 {quota.daily_quota || 30} 次 · 升级解锁 1080P 无水印
            </a>
          )}
          <span className="ml-auto text-[10px] text-gray-400">
            每次生成消耗 1 次额度
            {storage &&
              ` · 我的存储 ${storage.size_mb}MB / ${storage.records} 条（保留 ${storage.retention_days} 天）`}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左列：配置面板 */}
        <div className="space-y-4">
          {/* 行业模板库：一键套用场景/背景/音色/字幕样式 + 片头片尾 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <LayoutGrid className="w-4 h-4 text-amber-500" /> 行业模板库
              <span className="text-[10px] text-gray-400 font-normal">选模板自动填充全部配置</span>
            </h3>
            <div className="space-y-1.5">
              {(templates.length > 0 ? templates : []).map((t) => (
                <button
                  key={t.id}
                  onClick={() => applyTemplate(t)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs transition-all ${
                    templateId === t.id
                      ? 'bg-amber-50 border border-amber-300 text-amber-800 font-medium'
                      : 'border border-gray-100 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-base">{t.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium">{t.name}</div>
                    <div className="text-[10px] text-gray-400 truncate">{t.desc}</div>
                  </div>
                  <span className="text-[10px] text-gray-400 flex-shrink-0">
                    {t.subtitle?.position === 'center' ? '底部大字' : '右侧字幕'} · 片头片尾
                  </span>
                </button>
              ))}
              {templateId && (
                <button
                  onClick={clearTemplate}
                  className="w-full text-[10px] text-gray-400 hover:text-red-500 text-center py-1"
                >
                  退出模板（恢复手动配置）
                </button>
              )}
            </div>
          </Card>

          {/* 场景模板 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Radio className="w-4 h-4 text-amber-500" /> 场景模板
            </h3>
            <div className="space-y-1.5">
              {(cloudScenes.length > 0 ? cloudScenes : SCENES).map((s) => {
                const SceneIcon = s.icon || Sparkles
                return (
                  <button
                    key={s.id}
                    onClick={() => {
                      selectScene(s.id)
                    }}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs transition-all ${
                      sceneId === s.id
                        ? 'bg-violet-50 border border-violet-200 text-violet-700 font-medium'
                        : 'border border-gray-100 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <SceneIcon className="w-3.5 h-3.5 flex-shrink-0" />
                    <div>
                      <div className="font-medium">{s.name}</div>
                      <div className="text-[10px] text-gray-400">{s.desc}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </Card>

          {/* 背景模板 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-emerald-500" /> 背景模板
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {(backgrounds.length > 0
                ? backgrounds
                : [
                    {
                      id: 'tech',
                      name: '科技蓝幕',
                      color: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    },
                    { id: 'office', name: '现代办公室', color: '#1a1a2e' },
                    { id: 'studio', name: '简约演播室', color: '#16213e' },
                  ]
              ).map((b) => (
                <button
                  key={b.id}
                  onClick={() => setBgId(b.id)}
                  className={`h-12 rounded-lg text-[10px] font-medium overflow-hidden transition-all ${
                    bgId === b.id ? 'ring-2 ring-emerald-500' : 'opacity-75 hover:opacity-100'
                  }`}
                  style={{ background: b.color }}
                  title={b.name}
                >
                  <span className="flex items-center justify-center h-full w-full bg-black/35 text-white">
                    {b.name}
                  </span>
                </button>
              ))}
            </div>
          </Card>

          {/* 数字人形象 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <UserCircle className="w-4 h-4 text-blue-500" /> 数字人形象
              </h3>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => {
                    setAiVideoForm({ mode: 'text2video', prompt: '', imageUrl: '', audioUrl: '', duration: 5, resolution: '720p' })
                    setShowAiVideoModal(true)
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 transition-all"
                  title="可灵大模型生成视频（文生视频/图生视频/口型同步），按条付费"
                >
                  <Sparkles className="w-3 h-3" /> AI 视频
                </button>
                <button
                  onClick={() => {
                    setAiAvatarForm({ prompt: '', name: 'AI 形象' })
                    setShowAiAvatarModal(true)
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-cyan-200 bg-cyan-50 text-cyan-600 hover:bg-cyan-100 transition-all"
                  title="AI 生成高清形象图，自动创建照片数字人（可口型同步）"
                >
                  <Sparkles className="w-3 h-3" /> AI 形象
                </button>
                <button
                  onClick={() => {
                    setPhotoForm({ name: '', file: null, preview: '' })
                    setShowPhotoModal(true)
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100 transition-all"
                  title="上传真实照片，生成口型同步数字人视频"
                >
                  <Camera className="w-3 h-3" /> 照片数字人
                </button>
                <button
                  onClick={() => {
                    setAvatarForm({ name: '', desc: '', file: null, preview: '' })
                    setShowAvatarModal(true)
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100 transition-all"
                >
                  <Upload className="w-3 h-3" /> 上传我的形象
                </button>
                <button
                  onClick={generateAllPortraits}
                  disabled={generatingAll}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  <Camera className="w-3 h-3" />
                  {generatingAll ? '生成中...' : '一键生成全部写真'}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {/* 自定义形象（用户上传，带删除）；照片数字人形象带引擎标记 */}
              {customAvatars.map((a) => (
                <div key={a.id} className="relative group">
                  <button
                    onClick={() => {
                      setAvatarId(a.id)
                      // 照片数字人形象自动切换引擎，普通自定义形象回退 2D
                      setEngine(a.style === '照片数字人' ? 'live_portrait' : '2d')
                    }}
                    className={`relative w-full flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition-all ${
                      avatarId === a.id
                        ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-500/20'
                        : 'border-blue-100 hover:border-blue-200 hover:bg-blue-50/30'
                    }`}
                  >
                    <div className="w-12 h-12 rounded-full overflow-hidden ring-2 ring-blue-200 shadow-sm">
                      <img src={a.image_url} alt={a.name} className="w-full h-full object-cover" />
                    </div>
                    <div className="text-xs font-medium text-gray-800">{a.name}</div>
                    <div className="text-[10px] text-blue-500">
                      {a.style === '照片数字人' ? '照片数字人 · 口型同步' : '我的形象'}
                    </div>
                  </button>
                  <button
                    onClick={() => deleteCustomAvatar(a.id)}
                    className="absolute -top-1.5 -right-1.5 p-1 rounded-full bg-red-500 text-white shadow opacity-0 group-hover:opacity-100 transition-opacity"
                    title="删除该形象"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {avatars.map((a) => {
                const hasPortrait = !!portraitMap[a.id]
                const isGenerating = generatingPortrait.has(a.id)
                return (
                  <button
                    key={a.id}
                    onClick={() => {
                      setAvatarId(a.id)
                      setEngine('2d') // 内置形象仅支持 2D 基础引擎
                    }}
                    className={`relative flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition-all ${
                      avatarId === a.id
                        ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-500/20'
                        : 'border-gray-100 hover:border-violet-200 hover:bg-violet-50/30'
                    }`}
                  >
                    {/* 写真状态角标 */}
                    {hasPortrait ? (
                      <span
                        className="absolute top-1 right-1 w-2.5 h-2.5 bg-emerald-400 rounded-full ring-2 ring-white"
                        title="AI写真已就绪"
                      />
                    ) : isGenerating ? (
                      <span
                        className="absolute top-1 right-1 w-2.5 h-2.5 bg-amber-400 rounded-full ring-2 ring-white animate-pulse"
                        title="写真生成中..."
                      />
                    ) : null}
                    {/* 头像预览 — 有写真则显示写真缩略图 */}
                    {hasPortrait ? (
                      <div className="w-12 h-12 rounded-full overflow-hidden ring-2 ring-violet-200 shadow-sm">
                        <img
                          src={portraitMap[a.id]}
                          alt={a.name}
                          className="w-full h-full object-cover"
                        />
                      </div>
                    ) : (
                      <div
                        className={`w-10 h-10 rounded-full bg-gradient-to-br ${a.bg_color} flex items-center justify-center text-lg`}
                      >
                        {a.emoji}
                      </div>
                    )}
                    <div className="text-xs font-medium text-gray-800">{a.name}</div>
                    <div className="text-[10px] text-gray-400">{a.style}</div>
                    {/* 写真生成按钮（仅在选中且无写真时显示） */}
                    {avatarId === a.id && !hasPortrait && !isGenerating && (
                      <span
                        onClick={(e) => {
                          e.stopPropagation()
                          generatePortrait(a.id)
                        }}
                        className="text-[10px] text-violet-500 hover:text-violet-700 cursor-pointer underline mt-0.5"
                      >
                        生成AI写真
                      </span>
                    )}
                    {avatarId === a.id && isGenerating && (
                      <span className="text-[10px] text-amber-500 animate-pulse mt-0.5">
                        AI写真生成中...
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
            {/* 引擎状态条：照片形象自动切换 live_portrait，也可手动选择 */}
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <span className="text-[10px] text-gray-400">引擎：</span>
              {[
                { id: '2d', label: '2D 基础（卡通渲染·免费）' },
                { id: 'live_portrait', label: '照片数字人（口型同步）' },
                { id: 'sadtalker', label: '数字人高级版（3D 口型·头部运动）' },
              ].map((e) => (
                <button
                  key={e.id}
                  onClick={() => {
                    setEngine(e.id)
                    if (e.id !== '2d' && !customAvatars.some((a) => a.style === '照片数字人')) {
                      toast.info('请先上传正脸照片创建照片数字人形象')
                    }
                  }}
                  className={`px-2 py-1 text-[10px] font-medium rounded-lg border transition-all ${
                    engine === e.id
                      ? 'border-rose-400 bg-rose-50 text-rose-600'
                      : 'border-gray-200 text-gray-500 hover:border-rose-200'
                  }`}
                >
                  {e.label}
                </button>
              ))}
              {engine === 'live_portrait' && (
                <span className="text-[10px] text-rose-500">
                  照片数字人需搭配照片形象使用，失败自动降级 2D 保证出片
                </span>
              )}
              {engine === 'sadtalker' && (
                <span className="text-[10px] text-rose-500">
                  高级引擎推理约 20-50 分钟（CPU），需搭配照片形象，失败自动降级照片/2D 引擎
                </span>
              )}
            </div>
          </Card>

          {/* 声音选择 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Mic2 className="w-4 h-4 text-pink-500" /> 声音选择
              </h3>
              <button
                onClick={() => {
                  setVoiceForm({ name: '', desc: '', file: null })
                  setShowVoiceModal(true)
                }}
                className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-pink-200 bg-pink-50 text-pink-600 hover:bg-pink-100 transition-all"
              >
                <Upload className="w-3 h-3" /> 上传我的声音
              </button>
              <button
                onClick={() => {
                  setCloneForm({ name: '', file: null, authorized: false })
                  setShowCloneModal(true)
                }}
                className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 transition-all"
              >
                <Mic2 className="w-3 h-3" /> 克隆我的声音
              </button>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {/* 自定义声音：上传录音（直接用样本配音）/ 克隆声音（AI 匹配音色合成） */}
              {customVoices.map((v) => (
                <div key={v.id} className="relative group">
                  <button
                    onClick={() => setVoiceId(v.id)}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all ${
                      voiceId === v.id
                        ? 'bg-pink-50 border border-pink-200 text-pink-700 font-medium'
                        : 'border border-pink-100 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <span className="text-base">{v.is_clone ? '🔊' : '🎙️'}</span>
                    <div className="flex-1 text-left">
                      <div className="font-medium">
                        {v.name} · {v.is_clone ? '克隆声音' : '我的声音'}
                      </div>
                      <div className="text-[10px] text-gray-400">
                        {v.is_clone
                          ? v.desc || `基频 ${Math.round(v.f0_mean || 0)}Hz，AI 匹配音色合成配音`
                          : v.desc || `时长 ${Math.round(v.duration || 0)}s 的录音，直接作为配音`}
                      </div>
                    </div>
                    {voiceId === v.id && (
                      <Check className="w-3.5 h-3.5 text-pink-500 flex-shrink-0" />
                    )}
                  </button>
                  <button
                    onClick={() => (v.is_clone ? revokeVoiceClone(v.id) : deleteCustomVoice(v.id))}
                    className="absolute top-1 right-7 p-1 rounded-full bg-red-500 text-white shadow opacity-0 group-hover:opacity-100 transition-opacity"
                    title={v.is_clone ? '删除该克隆音色' : '删除该声音'}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {voices.map((v) => (
                <button
                  key={v.id}
                  onClick={() => setVoiceId(v.id)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all ${
                    voiceId === v.id
                      ? 'bg-pink-50 border border-pink-200 text-pink-700 font-medium'
                      : 'border border-gray-100 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-base">{v.emoji}</span>
                  <div className="flex-1 text-left">
                    <div className="font-medium">
                      {v.name} · {v.gender}
                    </div>
                    <div className="text-[10px] text-gray-400">{v.style}</div>
                  </div>
                  {voiceId === v.id && (
                    <Check className="w-3.5 h-3.5 text-pink-500 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
            <div className="mt-2">
              <label className="text-xs text-gray-500">语速：{speed.toFixed(1)}x</label>
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.05}
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                className="w-full mt-1 accent-violet-500"
              />
            </div>
            <div className="mt-3">
              <label className="text-xs text-gray-500 mb-1 block">
                情绪：{emotionLabel(emotion)}
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {EMOTION_OPTIONS.map((e) => (
                  <button
                    key={e.id}
                    onClick={() => setEmotion(e.id)}
                    className={`px-1 py-1.5 rounded-lg text-[11px] transition-all flex flex-col items-center gap-0.5 ${
                      emotion === e.id
                        ? 'bg-violet-100 text-violet-700 ring-1 ring-violet-400'
                        : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                    }`}
                  >
                    <span className="text-sm leading-none">{e.icon}</span>
                    {e.label}
                  </button>
                ))}
              </div>
              {emotion === 'auto' && (
                <p className="text-[10px] text-gray-400 mt-1">
                  AI 自动分析文案情绪（声音 + 表情联动）
                </p>
              )}
            </div>
          </Card>

          {/* 虚拟场景 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Monitor className="w-4 h-4 text-emerald-500" /> 虚拟场景
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(SCENE_NAMES).map(([key, name]) => (
                <button
                  key={key}
                  onClick={() => setAvatarScene(key)}
                  className={`p-2 rounded-lg text-xs font-medium transition-all ${
                    avatarScene === key
                      ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                      : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          </Card>

          {/* 表情切换 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Smile className="w-4 h-4 text-yellow-500" /> 表情控制
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {Object.entries(EXPRESSION_NAMES).map(([key, name]) => (
                <button
                  key={key}
                  onClick={() => setCurrentExpression(key)}
                  className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                    currentExpression === key
                      ? 'bg-yellow-100 text-yellow-700 border border-yellow-300'
                      : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          </Card>

          {/* 服装 + 配饰 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Shirt className="w-4 h-4 text-orange-500" /> 服装配饰
            </h3>
            <div className="space-y-2">
              {/* 服装 */}
              <div>
                <label className="text-xs text-gray-500 mb-1 block">服装</label>
                <div className="grid grid-cols-2 gap-1.5">
                  {Object.entries(OUTFIT_NAMES).map(([key, name]) => (
                    <button
                      key={key}
                      onClick={() => setOutfit(key)}
                      className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                        outfit === key
                          ? 'bg-orange-100 text-orange-700 border border-orange-300'
                          : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                      }`}
                    >
                      {name}
                    </button>
                  ))}
                </div>
              </div>
              {/* 配饰 */}
              <div className="flex gap-2">
                <button
                  onClick={() => setGlasses(!glasses)}
                  className={`flex-1 flex items-center justify-center gap-1.5 p-1.5 rounded-lg text-xs font-medium transition-all ${
                    glasses
                      ? 'bg-blue-100 text-blue-700 border border-blue-300'
                      : 'bg-gray-50 text-gray-500 border border-gray-100 hover:bg-gray-100'
                  }`}
                >
                  <Glasses className="w-3 h-3" /> 眼镜
                </button>
                <button
                  onClick={() => setHat(!hat)}
                  className={`flex-1 flex items-center justify-center gap-1.5 p-1.5 rounded-lg text-xs font-medium transition-all ${
                    hat
                      ? 'bg-purple-100 text-purple-700 border border-purple-300'
                      : 'bg-gray-50 text-gray-500 border border-gray-100 hover:bg-gray-100'
                  }`}
                >
                  <HardHat className="w-3 h-3" /> 帽子
                </button>
              </div>
            </div>
          </Card>
        </div>

        {/* 中列：文案编辑 + 生成 */}
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-violet-500" /> 口播文案
                <span className="text-xs font-normal text-gray-400">（{text.length} 字）</span>
              </h3>
              <div className="flex items-center gap-1.5 flex-wrap justify-end">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Wand2}
                  onClick={() => {
                    setScriptForm({ topic: '', platform: 'douyin', tone: '专业' })
                    setScriptList([])
                    setShowScriptModal(true)
                  }}
                >
                  AI 写文案
                </Button>
                <Button variant="secondary" size="sm" icon={ShieldCheck} onClick={checkCompliance}>
                  检查文案
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={ListChecks}
                  loading={qualityLoading}
                  onClick={checkScriptQuality}
                >
                  文案体检
                </Button>
                <Button variant="secondary" size="sm" icon={FileText} onClick={loadArticles}>
                  素材库
                </Button>
                <Button variant="secondary" size="sm" icon={Shuffle} onClick={pickRandomScript}>
                  随机台词
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Volume2}
                  loading={previewingVoice}
                  onClick={previewVoice}
                >
                  试听语音
                </Button>
              </div>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="输入口播文案，AI 会自动优化为更流畅自然的口播脚本…&#10;&#10;如：大家好，今天给大家介绍一款全新的AI效率工具，它可以在30秒内帮你完成…"
              rows={12}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none"
            />
            {/* 合规预检结果：红色=违规词拦截 / 橙色=风险词提示 */}
            {checkResult && (
              <div
                className={`mt-2 px-3 py-2 rounded-lg text-[11px] leading-relaxed border ${
                  checkResult.allowed
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-red-200 bg-red-50 text-red-700'
                }`}
              >
                {!checkResult.allowed && (
                  <div className="font-medium mb-0.5">
                    🚫 含违规词：{checkResult.hard_hits.join('、')}（无法生成，请修改）
                  </div>
                )}
                {checkResult.risk_hits.length > 0 && (
                  <div className="text-orange-600">
                    ⚠️ 风险词提示：{checkResult.risk_hits.slice(0, 10).join('、')}
                    {checkResult.risk_hits.length > 10
                      ? ` 等${checkResult.risk_hits.length}个`
                      : ''}
                    （发布到平台可能限流）
                  </div>
                )}
                {checkResult.allowed && checkResult.risk_hits.length === 0 && (
                  <div>✓ 文案合规，可以放心生成</div>
                )}
              </div>
            )}
          </Card>

          {/* 核心操作：生成按钮（紧跟口播文案，主路径最短） */}
          <div className="rounded-xl bg-gradient-to-r from-violet-50 to-fuchsia-50 border border-violet-100 p-3">
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-violet-900">
                  {text.trim() ? '文案已就绪，可以生成' : '输入文案后即可生成'}
                </div>
                <div className="text-[11px] text-violet-600/70 mt-0.5">
                  {selectedAvatar?.name || '数字人形象'} · {selectedVoice?.name || '音色'} · 视频质量等高级参数可展开调整
                </div>
              </div>
              <Button
                variant="primary"
                size="lg"
                icon={Sparkles}
                loading={generating}
                onClick={generate}
                className="!px-6 whitespace-nowrap"
              >
                {generating
                  ? (currentTask &&
                      !['success', 'failed'].includes(currentTask.status) &&
                      currentTask.stage) ||
                    genPhase ||
                    'AI数字人正在生成…'
                  : '生成视频'}
              </Button>
            </div>
          </div>

          {/* 高级参数（默认收起） */}
          <div className="rounded-xl border border-gray-200 overflow-hidden">
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors"
            >
              <span className="flex items-center gap-1.5 text-xs font-medium text-gray-600">
                <Sliders className="w-3.5 h-3.5 text-gray-400" />
                高级参数
                <span className="text-gray-400 font-normal">（视频质量/帧率/水印等）</span>
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 text-gray-400 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
              />
            </button>
            {showAdvanced && (
              <div className="p-4 space-y-3">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Film className="w-4 h-4 text-sky-500" /> 视频质量
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">分辨率</label>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { id: '720p', name: '高清 720P' },
                    { id: '1080p', name: '全高清 1080P', pro: true },
                  ].map((r) => (
                    <button
                      key={r.id}
                      onClick={() => setResolution(r.id)}
                      disabled={r.pro && !isMember()}
                      className={`p-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                        resolution === r.id
                          ? 'bg-sky-100 text-sky-700 border border-sky-300'
                          : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                      }`}
                    >
                      {r.name}
                      {r.pro && !isMember() && ' 🔒'}
                    </button>
                  ))}
                </div>
                {resolution === '1080p' && (
                  <div className="text-[10px] text-sky-500 mt-1">
                    1080P 渲染更精细，生成耗时约为 720P 的 2 倍
                  </div>
                )}
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">帧率</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                  {[12, 15, 24, 30].map((f) => (
                    <button
                      key={f}
                      onClick={() => setFps(f)}
                      className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                        fps === f
                          ? 'bg-sky-100 text-sky-700 border border-sky-300'
                          : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                      }`}
                    >
                      {f} fps
                      {f === 24 && <span className="text-[9px] text-sky-400 ml-0.5">流畅</span>}
                      {f === 30 && <span className="text-[9px] text-purple-400 ml-0.5">极致</span>}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50 border border-gray-100">
                <div>
                  <div className="text-xs font-medium text-gray-700">平台水印</div>
                  <div className="text-[10px] text-gray-400">
                    {isMember() ? '会员可自由开关' : '免费版视频右下角含平台水印'}
                  </div>
                </div>
                {isMember() ? (
                  <button
                    onClick={() => setWatermark(!watermark)}
                    className={`w-9 h-5 rounded-full transition-colors relative ${watermark ? 'bg-sky-500' : 'bg-gray-300'}`}
                  >
                    <span
                      className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${watermark ? 'left-4.5' : 'left-0.5'}`}
                    />
                  </button>
                ) : (
                  <span className="text-[10px] text-amber-500 font-medium">🔒 升级会员去除</span>
                )}
              </div>
            </div>
          </Card>

          {/* 批量生产：多文案后台流水线（口播矩阵产能） */}
          <Card className="border-dashed border-violet-300">
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <Layers className="w-4 h-4 text-violet-500" /> 批量生产
              <span className="text-[10px] font-normal text-gray-400">
                按当前形象/声音/质量设置逐条生成
              </span>
            </h3>
            <textarea
              value={batchTexts}
              onChange={(e) => setBatchTexts(e.target.value)}
              placeholder={
                '每行一条文案，最多 50 条，后台自动逐条生成…\n如：\n大家好，今天介绍一款AI效率工具\n你知道AI数字人吗？\n创业公司如何做内容营销'
              }
              rows={4}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none mb-2"
            />
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                icon={Layers}
                loading={batchTask?.status === 'running'}
                onClick={runBatch}
                className="flex-1"
              >
                {batchTask?.status === 'running'
                  ? `批量生成中（${batchTask.done}/${batchTask.total}）…`
                  : `批量生成 ${batchTexts.split('\n').filter((t) => t.trim()).length} 条视频`}
              </Button>
              {batchTask?.status === 'done' && batchTask.success > 0 && (
                <>
                  <Button variant="secondary" size="sm" icon={Download} onClick={downloadBatch}>
                    打包下载 ZIP
                  </Button>
                  <ShareButton
                    content={`# 数字人批量生产任务

文案 ${batchTask.total} 条 · 成功 ${batchTask.success} 条 · 失败 ${batchTask.failed} 条

${batchTexts
                      .split('\n')
                      .map((t) => t.trim())
                      .filter(Boolean)
                      .map((t, i) => `${i + 1}. ${t}`)
                      .join('\n')}

> 由小团智能平台数字人工厂批量生成 · ${new Date().toLocaleString()}`}
                    title="数字人批量生产任务"
                    contentType="digital-human"
                  />
                </>
              )}
              {(batchTask?.status === 'done' || batchTask?.status === 'interrupted') &&
                batchTask.failed > 0 && (
                  <Button variant="secondary" size="sm" icon={RefreshCw} onClick={retryBatchFailed}>
                    重试失败项 ({batchTask.failed})
                  </Button>
                )}
            </div>
            {/* 批量进度：总进度条 + 逐条状态 */}
            {batchTask && (
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between text-[11px] text-gray-500">
                  <span className="flex items-center gap-1.5">
                    {batchTask.status === 'running' ? (
                      <>
                        <span className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                        任务进行中 {batchTask.done}/{batchTask.total}
                      </>
                    ) : batchTask.status === 'interrupted' ? (
                      <>
                        <span className="w-2 h-2 bg-amber-400 rounded-full" />
                        任务中断（服务重启）· 可重试失败项
                      </>
                    ) : (
                      '任务已完成'
                    )}
                  </span>
                  <span>
                    成功 <span className="text-emerald-600 font-medium">{batchTask.success}</span> ·
                    失败 <span className="text-red-500 font-medium">{batchTask.failed}</span>
                    {batchTask.skipped > 0 && (
                      <>
                        {' '}
                        · 跳过{' '}
                        <span className="text-amber-500 font-medium">{batchTask.skipped}</span>
                      </>
                    )}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all duration-500"
                    style={{
                      width: `${batchTask.total ? (batchTask.done / batchTask.total) * 100 : 0}%`,
                    }}
                  />
                </div>
                <div className="max-h-44 overflow-y-auto pr-1 space-y-1">
                  {batchTask.items?.map((it) => (
                    <div key={it.index} className="flex items-center gap-2 text-[11px] py-0.5">
                      <span
                        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                          it.status === 'success'
                            ? 'bg-emerald-400'
                            : it.status === 'failed'
                              ? 'bg-red-400'
                              : it.status === 'skipped'
                                ? 'bg-amber-400'
                                : 'bg-gray-300 animate-pulse'
                        }`}
                      />
                      <span className="text-gray-400 flex-shrink-0 w-4">{it.index + 1}</span>
                      <span className="text-gray-600 truncate flex-1">{it.text_preview}</span>
                      {it.status === 'success' && it.video_url && (
                        <button
                          onClick={() => playPreviewVideo(it.video_url)}
                          className="text-blue-500 hover:text-blue-700 flex-shrink-0"
                        >
                          预览
                        </button>
                      )}
                      <span
                        className={`flex-shrink-0 max-w-40 truncate ${
                          it.status === 'success'
                            ? 'text-emerald-500'
                            : it.status === 'failed' || it.status === 'skipped'
                              ? 'text-red-400'
                              : 'text-gray-300'
                        }`}
                      >
                        {it.status === 'success'
                          ? '✓ 成功'
                          : it.status === 'failed'
                            ? `✗ ${it.error || '失败'}`
                            : it.status === 'skipped'
                              ? '额度不足跳过'
                              : it.status === 'running'
                                ? '生成中…'
                                : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

              <div className="flex gap-2 pt-1">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Video}
                  loading={generating}
                  onClick={recordAndPlay}
                >
                  生成并录制（含口播录制）
                </Button>
              </div>
            </div>
          )}
          </div>

          {genHistory.length > 0 && (
            <div className="mt-3">
              <HistoryPanel
                history={genHistory}
                onReuse={(item) => {
                  setText(item.content || '')
                  toast.info('已恢复口播文案，可重新生成')
                }}
                onRemove={removeGenHistory}
                onClear={clearGenHistory}
                title="生成历史"
              />
            </div>
          )}
          {generating && (
            <div className="text-[11px] text-gray-400 flex items-center gap-1.5">
              <span className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
              {currentTask?.stage || '任务执行中'} · 后台执行，可关闭页面，完成进度{' '}
              {Math.round(currentTask?.progress || 0)}%
            </div>
          )}

          {/* 生成任务面板：异步任务进度/状态/重试，页面无需停留等待 */}
          {(currentTask || taskList.length > 0) && (
            <Card className="mt-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <ListChecks className="w-4 h-4 text-violet-500" /> 我的生成任务
                </h3>
                <span className="text-[10px] text-gray-400">
                  后台执行 · 可离开页面 · 失败可重试
                </span>
              </div>
              {/* 当前活跃任务：进度条 + 阶段文案 */}
              {currentTask &&
                !['success', 'failed', 'interrupted', 'canceled'].includes(currentTask.status) && (
                  <div className="mb-3 p-3 bg-violet-50/70 rounded-lg">
                    <div className="flex items-center justify-between text-xs text-gray-600 mb-1.5">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                        {currentTask.stage || '任务执行中…'}
                      </span>
                      <span className="font-medium text-violet-600">
                        {Math.round(currentTask.progress || 0)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-violet-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-violet-500 rounded-full transition-all duration-500"
                        style={{ width: `${currentTask.progress || 0}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-gray-400 mt-1.5">
                      {currentTask.status === 'pending'
                        ? '任务排队中，即将开始执行…'
                        : '任务在后台执行，可关闭页面稍后回来查看，无需停留等待'}
                    </p>
                  </div>
                )}
              {/* 任务列表：状态 + 结果 + 重试 */}
              {taskList.length > 0 && (
                <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                  {taskList.map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center gap-2 text-xs p-2 rounded-lg bg-gray-50"
                    >
                      {t.status === 'success' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                      ) : t.status === 'failed' ? (
                        <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                      ) : t.status === 'interrupted' ? (
                        <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                      ) : (
                        <Loader2 className="w-4 h-4 text-violet-500 shrink-0 animate-spin" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-gray-700 truncate">
                            {t.status === 'success'
                              ? '视频生成成功'
                              : t.status === 'failed'
                                ? '生成失败'
                                : t.status === 'interrupted'
                                  ? '任务中断（可重试）'
                                  : t.status === 'canceled'
                                    ? '已取消'
                                    : t.stage || '任务执行中…'}
                          </span>
                          <span className="text-gray-400 shrink-0">
                            {t.status === 'pending' && '排队中'}
                            {t.status === 'running' && `${Math.round(t.progress || 0)}%`}
                            {['success', 'failed', 'interrupted', 'canceled'].includes(t.status) &&
                              formatTaskTime(t.created_at)}
                          </span>
                        </div>
                        <div className="text-[10px] text-gray-400 truncate mt-0.5">
                          {t.status === 'failed'
                            ? t.error || '未知错误'
                            : t.status === 'success'
                              ? '已完成 ✓'
                              : t.status === 'canceled'
                                ? '已取消'
                                : '任务执行中'}
                        </div>
                      </div>
                      {(t.status === 'failed' || t.status === 'interrupted') && (
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={RefreshCw}
                          onClick={() => retryTask(t)}
                          className="shrink-0"
                        >
                          重试
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* 预览区 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Eye className="w-4 h-4 text-violet-500" /> 实时预览
                {talking && (
                  <span className="text-[10px] text-emerald-500 font-normal animate-pulse">
                    ● 口型同步中
                  </span>
                )}
                {recording && (
                  <span className="text-[10px] text-red-500 font-normal animate-pulse">
                    ● 录制中
                  </span>
                )}
              </h3>
              <div className="flex items-center gap-1">
                {/* 录制按钮 */}
                {!recording ? (
                  <Button variant="secondary" size="sm" icon={Circle} onClick={startRecording}>
                    <span className="text-red-500">录制</span>
                  </Button>
                ) : (
                  <Button variant="secondary" size="sm" icon={StopCircle} onClick={stopRecording}>
                    停止
                  </Button>
                )}
                {videoBlob && (
                  <Button variant="secondary" size="sm" icon={Download} onClick={downloadVideo}>
                    下载
                  </Button>
                )}
                {/* 音频控制 */}
                {audioUrl && (
                  <>
                    {playing ? (
                      <Button variant="secondary" size="sm" icon={Pause} onClick={pauseAudio}>
                        暂停
                      </Button>
                    ) : (
                      <Button variant="secondary" size="sm" icon={Play} onClick={playAudio}>
                        播放
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" icon={StopCircle} onClick={stopAudio} />
                  </>
                )}
              </div>
            </div>
            <div
              className="relative rounded-xl overflow-hidden border border-gray-200 flex items-center justify-center"
              style={{ minHeight: 350 }}
            >
              <AnimatedAvatar
                ref={avatarRef}
                avatarId={avatarId}
                width={480}
                height={360}
                talking={talking}
                audioElement={audioRef.current}
                expression={currentExpression}
                outfit={outfit}
                scene={avatarScene}
                glasses={glasses}
                hat={hat}
                portraitUrl={portraitMap[avatarId] || null}
              />
              {/* 底部信息条 */}
              <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/50 to-transparent">
                <div className="flex items-center justify-center gap-3 text-white/80 text-xs">
                  <span className="flex items-center gap-1">
                    {portraitMap[avatarId] ? (
                      <img
                        src={portraitMap[avatarId]}
                        alt=""
                        className="w-4 h-4 rounded-full object-cover ring-1 ring-white/50"
                      />
                    ) : (
                      <UserCircle className="w-3 h-3" />
                    )}
                    {selectedAvatar?.name || '选择形象'}
                  </span>
                  <span className="flex items-center gap-1">
                    <Volume2 className="w-3 h-3" /> {selectedVoice?.name || ''}
                  </span>
                  <span className="flex items-center gap-1">
                    <Smile className="w-3 h-3" /> {EXPRESSION_NAMES[currentExpression]}
                  </span>
                  {portraitMap[avatarId] && (
                    <span className="text-[10px] text-emerald-300">● AI写真</span>
                  )}
                </div>
              </div>
            </div>
            {/* 音频播放条 */}
            {audioUrl && (
              <div className="mt-3 border border-gray-200 rounded-lg overflow-hidden bg-gray-50 px-3 py-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-700 flex items-center gap-1.5">
                    <Volume2 className="w-3.5 h-3.5 text-violet-500" /> 配音音频
                    {playing && (
                      <span className="text-[10px] text-emerald-500 animate-pulse">● 播放中</span>
                    )}
                  </span>
                  <span className="text-[10px] text-gray-400">{selectedVoice?.name || ''}</span>
                </div>
                <audio
                  ref={audioRef}
                  src={audioUrl}
                  controls
                  onPlay={() => {
                    setPlaying(true)
                    setTalking(true)
                  }}
                  onPause={() => {
                    setPlaying(false)
                    setTalking(false)
                  }}
                  onEnded={() => {
                    setPlaying(false)
                    setTalking(false)
                  }}
                  className="w-full h-8"
                  crossOrigin="anonymous"
                />
              </div>
            )}
            {/* 视频播放器 */}
            {previewVideoUrl && (
              <div className="mt-3 border border-violet-200 rounded-xl overflow-hidden bg-black">
                <div className="flex items-center justify-between px-3 py-1.5 bg-violet-50 border-b border-violet-200">
                  <span className="text-xs font-medium text-violet-700 flex items-center gap-1.5">
                    <Video className="w-3.5 h-3.5" /> 生成的视频
                    {playingVideo && (
                      <span className="text-[10px] text-emerald-500 animate-pulse">● 播放中</span>
                    )}
                  </span>
                  <button
                    onClick={() => {
                      setPreviewVideoUrl('')
                      setPlayingVideo(false)
                    }}
                    className="text-xs text-gray-400 hover:text-gray-600"
                  >
                    关闭
                  </button>
                </div>
                <video
                  ref={videoRef}
                  src={previewVideoUrl}
                  controls
                  onPlay={() => setPlayingVideo(true)}
                  onPause={() => setPlayingVideo(false)}
                  onEnded={() => setPlayingVideo(false)}
                  className="w-full"
                  style={{ maxHeight: 360 }}
                />
              </div>
            )}
          </Card>
        </div>

        {/* 右列：生成结果 + 历史 */}
        <div className="space-y-4">
          {/* 生成结果 */}
          {result && (
            <Card className="border-violet-200">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-500" /> 生成结果
              </h3>
              <div
                className={`p-3 rounded-xl border text-sm mb-3 ${
                  result.status === 'done'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : result.status === 'failed'
                      ? 'bg-red-50 border-red-200 text-red-800'
                      : 'bg-amber-50 border-amber-200 text-amber-800'
                }`}
              >
                {result.message}
              </div>
              {result.sensitive_warning && (
                <div className="p-2.5 rounded-lg border border-orange-200 bg-orange-50 text-orange-700 text-[11px] mb-3">
                  ⚠️ {result.sensitive_warning}
                </div>
              )}
              <div className="space-y-2 text-xs text-gray-600">
                <div className="flex justify-between">
                  <span>数字人：</span>
                  <span className="font-medium">
                    {result.avatar?.name} {result.avatar?.emoji}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>声音：</span>
                  <span className="font-medium">{result.voice?.name}</span>
                </div>
                <div className="flex justify-between">
                  <span>文案长度：</span>
                  <span className="font-medium">{result.text_length} 字</span>
                </div>
                {result.emotion && result.emotion !== 'auto' && (
                  <div className="flex justify-between">
                    <span>情绪：</span>
                    <span className="font-medium">{emotionLabel(result.emotion)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>视频参数：</span>
                  <span className="font-medium">
                    {result.resolution} · {result.fps}fps
                    {result.watermark ? ' · 含水印' : ' · 无水印'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>状态：</span>
                  <Badge
                    color={
                      result.status === 'done'
                        ? 'green'
                        : result.status === 'failed'
                          ? 'red'
                          : 'amber'
                    }
                  >
                    {result.status === 'done'
                      ? '已完成'
                      : result.status === 'failed'
                        ? '生成失败'
                        : '仅音频'}
                  </Badge>
                </div>
                {result.quota_remaining != null && (
                  <div className="flex justify-between">
                    <span>今日剩余：</span>
                    <span className="font-medium text-violet-600">{result.quota_remaining} 次</span>
                  </div>
                )}
              </div>
              {/* 下载/播放按钮 */}
              <div className="flex gap-2 mt-3">
                {result.audio_url && (
                  <button
                    onClick={() => {
                      const fullUrl = result.audio_url.startsWith('http')
                        ? result.audio_url
                        : `${API_BASE}${result.audio_url}`
                      setAudioUrl(fullUrl)
                      setTimeout(() => {
                        if (audioRef.current) {
                          audioRef.current
                            .play()
                            .then(() => {
                              setPlaying(true)
                              setTalking(true)
                            })
                            .catch(() => {})
                        }
                      }, 200)
                    }}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-colors"
                  >
                    <Play className="w-3.5 h-3.5" /> 播放音频
                  </button>
                )}
                {result.audio_url && (
                  <button
                    onClick={() => downloadFile(result.audio_url, 'digital-human-audio.mp3')}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-violet-50 border border-violet-200 text-violet-700 text-xs font-medium hover:bg-violet-100 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" /> 下载 MP3
                  </button>
                )}
                {result.audio_url && (
                  <button
                    onClick={checkLipSync}
                    disabled={lipChecking}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs font-medium hover:bg-amber-100 transition-colors disabled:opacity-50"
                  >
                    {lipChecking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AudioWaveform className="w-3.5 h-3.5" />}
                    {lipChecking ? '检测中…' : '口型检测'}
                  </button>
                )}
                {result.video_url && (
                  <button
                    onClick={() => playPreviewVideo(result.video_url)}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-colors"
                  >
                    <Play className="w-3.5 h-3.5" /> 播放视频
                  </button>
                )}
                {result.video_url && (
                  <button
                    onClick={() => downloadFile(result.video_url, 'digital-human-video.mp4')}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" /> 下载 MP4
                  </button>
                )}
                {(result.video_url || result.audio_url) && (
                  <div className="flex items-center justify-center">
                    <FavoriteButton
                      favType="record"
                      targetId={result.record_id}
                      label={text.slice(0, 40) || '数字人口播'}
                      className="!bg-gray-50 !border !border-gray-200 !rounded-lg !px-3 !py-2"
                    />
                  </div>
                )}
                {result.video_url && (
                  <button
                    onClick={() => publishVideo(result.video_url, text, result.avatar?.name)}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium hover:bg-rose-100 transition-colors"
                  >
                    <Rocket className="w-3.5 h-3.5" /> 发布
                  </button>
                )}
              </div>
              {/* v22 口型同步质量评估结果 */}
              {lipCheck && (
                <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-amber-800 flex items-center gap-1">
                      <AudioWaveform className="w-3.5 h-3.5" /> 口型同步质量
                    </span>
                    <Badge color={lipCheck.score >= 75 ? 'green' : lipCheck.score >= 50 ? 'amber' : 'red'}>
                      {lipCheck.score ?? '-'} 分
                    </Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 bg-white rounded-lg">
                      <div className="text-lg font-bold text-amber-700">{lipCheck.open_range ?? '-'}</div>
                      <div className="text-[10px] text-gray-500">开合范围</div>
                    </div>
                    <div className="p-2 bg-white rounded-lg">
                      <div className="text-lg font-bold text-amber-700">{lipCheck.silence_gaps ?? '-'}</div>
                      <div className="text-[10px] text-gray-500">停顿段数</div>
                    </div>
                    <div className="p-2 bg-white rounded-lg">
                      <div className="text-lg font-bold text-amber-700">
                        {lipCheck.peak_ratio ? Math.round(lipCheck.peak_ratio * 100) + '%' : '-'}
                      </div>
                      <div className="text-[10px] text-gray-500">重音占比</div>
                    </div>
                  </div>
                  <p className="text-[11px] text-gray-500 mt-2">
                    {lipCheck.score >= 75
                      ? '口型与配音匹配良好，可正常发布'
                      : lipCheck.score >= 50
                        ? '口型匹配一般，建议检查文案长度与语速'
                        : '口型匹配较弱，建议缩短文案或调整语速后重试'}
                  </p>
                </div>
              )}
              {result.record_id && (
                <div className="text-[10px] text-gray-400 mt-2">记录 ID：{result.record_id}</div>
              )}
            </Card>
          )}

          {/* 写真画廊（云端素材 /api/digital-human/portraits） */}
          {portraitList.some((p) => p.exists) && (
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <Camera className="w-4 h-4 text-violet-500" /> AI写真画廊
                  <Badge color="purple">
                    {portraitList.filter((p) => p.exists).length} 张已生成
                  </Badge>
                </h3>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  onClick={() =>
                    api
                      .get('/api/digital-human/portraits')
                      .then((res) => setPortraitList(res.data?.portraits || []))
                      .catch(() => {})
                  }
                >
                  刷新
                </Button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
                {portraitList
                  .filter((p) => p.exists)
                  .map((p) => (
                    <div key={p.avatar_id} className="group relative">
                      <img
                        src={p.url}
                        alt={p.avatar_name}
                        onClick={() => {
                          setAvatarId(p.avatar_id)
                          toast.info(`已选中 ${p.avatar_name}`)
                        }}
                        className="w-full aspect-square object-cover rounded-xl border border-gray-200 cursor-pointer group-hover:ring-2 group-hover:ring-violet-400 transition-all"
                      />
                      <div className="mt-1 text-[10px] text-gray-500 truncate text-center">
                        {p.avatar_name}
                      </div>
                    </div>
                  ))}
              </div>
            </Card>
          )}

          {/* 历史记录 */}
          <Card>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-500" /> 历史记录（{recordTotal}）
              </h3>
              <div className="flex items-center gap-1.5">
                {selectedRecords.length > 0 && (
                  <button
                    onClick={batchDelete}
                    className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
                  >
                    <Trash2 className="w-3 h-3" /> 批量删除（{selectedRecords.length}）
                  </button>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  onClick={() => loadRecords(true)}
                >
                  刷新
                </Button>
              </div>
            </div>
            {/* 筛选 + 搜索 */}
            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              {[
                { v: '', n: '全部' },
                { v: 'done', n: '成功' },
                { v: 'audio_only', n: '仅音频' },
                { v: 'failed', n: '失败' },
              ].map((s) => (
                <button
                  key={s.v}
                  onClick={() => {
                    setRecordStatus(s.v)
                    loadRecords(true, s.v, recordQuery)
                  }}
                  className={`px-2 py-1 text-[10px] font-medium rounded-lg transition-all ${
                    recordStatus === s.v
                      ? 'bg-violet-100 text-violet-700 border border-violet-300'
                      : 'bg-gray-50 text-gray-500 border border-gray-100 hover:bg-gray-100'
                  }`}
                >
                  {s.n}
                </button>
              ))}
              <input
                value={recordQuery}
                placeholder="搜索文案/形象/声音…"
                onChange={(e) => setRecordQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') loadRecords(true, recordStatus, recordQuery)
                }}
                className="flex-1 min-w-24 px-2 py-1 text-[10px] border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
              />
              <button
                onClick={() => loadRecords(true, recordStatus, recordQuery)}
                className="px-2 py-1 text-[10px] rounded-lg bg-violet-50 border border-violet-200 text-violet-600 hover:bg-violet-100"
              >
                搜索
              </button>
            </div>
            {records.length === 0 ? (
              <Empty icon={Film} title="暂无记录" description="生成第一个数字人视频后这里会显示" />
            ) : (
              <>
                <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                  {records.map((r) => {
                    const av = avatars.find((a) => a.id === r.avatar_id)
                    const checked = selectedRecords.includes(r.id)
                    return (
                      <div
                        key={r.id}
                        className={`p-3 rounded-xl border transition-all ${
                          r.status === 'done'
                            ? 'border-emerald-200 bg-emerald-50/30'
                            : r.status === 'failed'
                              ? 'border-red-200 bg-red-50/30'
                              : 'border-amber-200 bg-amber-50/30'
                        } ${checked ? 'ring-2 ring-violet-400' : ''}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleRecordSelect(r.id)}
                              className="accent-violet-600 w-3.5 h-3.5"
                            />
                            <span className="text-lg">{av?.emoji || '👤'}</span>
                            <div>
                              <div className="text-xs font-medium text-gray-800">
                                {av?.name || r.avatar_name}
                              </div>
                              <div className="text-[10px] text-gray-400">
                                {r.voice_name} · {r.text_length}字 · {r.resolution || '720p'}/
                                {r.fps || 15}fps
                                {r.emotion && r.emotion !== 'auto'
                                  ? ` · ${emotionLabel(r.emotion)}`
                                  : ''}
                                {r.watermark ? ' · 水印' : ''}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <Badge
                              color={
                                r.status === 'done'
                                  ? 'green'
                                  : r.status === 'failed'
                                    ? 'red'
                                    : 'amber'
                              }
                            >
                              {r.status === 'done'
                                ? '完成'
                                : r.status === 'failed'
                                  ? '失败'
                                  : '仅音频'}
                            </Badge>
                            <button
                              onClick={() => deleteRecord(r.id)}
                              className="p-1 text-gray-300 hover:text-red-500 rounded"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500 truncate mt-1">
                          {r.text?.slice(0, 60)}
                        </p>
                        <div className="flex items-center justify-between mt-1.5">
                          <div className="text-[10px] text-gray-400">
                            {r.created_at?.slice(0, 16)?.replace('T', ' ')}
                          </div>
                          <div className="flex items-center gap-1 flex-wrap justify-end">
                            {r.video_url && (
                              <button
                                onClick={() => playPreviewVideo(r.video_url)}
                                className="text-[10px] text-blue-500 hover:text-blue-700 px-1.5 py-0.5 rounded hover:bg-blue-50"
                              >
                                预览
                              </button>
                            )}
                            {r.audio_url && (
                              <button
                                onClick={() => {
                                  const fullUrl = r.audio_url.startsWith('http')
                                    ? r.audio_url
                                    : `${API_BASE}${r.audio_url}`
                                  setAudioUrl(fullUrl)
                                  setTimeout(() => {
                                    if (audioRef.current) {
                                      audioRef.current
                                        .play()
                                        .then(() => {
                                          setPlaying(true)
                                          setTalking(true)
                                        })
                                        .catch(() => {})
                                    }
                                  }, 200)
                                }}
                                className="text-[10px] text-blue-500 hover:text-blue-700 px-1.5 py-0.5 rounded hover:bg-blue-50"
                              >
                                播放
                              </button>
                            )}
                            {r.audio_url && (
                              <button
                                onClick={() =>
                                  downloadFile(r.audio_url, `${r.avatar_name || 'audio'}.mp3`)
                                }
                                className="text-[10px] text-violet-500 hover:text-violet-700 px-1.5 py-0.5 rounded hover:bg-violet-50"
                              >
                                MP3
                              </button>
                            )}
                            {r.video_url && (
                              <button
                                onClick={() =>
                                  downloadFile(r.video_url, `${r.avatar_name || 'video'}.mp4`)
                                }
                                className="text-[10px] text-emerald-500 hover:text-emerald-700 px-1.5 py-0.5 rounded hover:bg-emerald-50"
                              >
                                MP4
                              </button>
                            )}
                            {r.text && (
                              <button
                                onClick={() => copyText(r)}
                                className="text-[10px] text-gray-500 hover:text-gray-700 px-1.5 py-0.5 rounded hover:bg-gray-50"
                              >
                                复制文案
                              </button>
                            )}
                            <button
                              onClick={() => reuseRecord(r)}
                              className="text-[10px] text-sky-500 hover:text-sky-700 px-1.5 py-0.5 rounded hover:bg-sky-50"
                            >
                              <RefreshCw className="w-3 h-3 inline mr-0.5" />
                              重新生成
                            </button>
                            {r.video_url && (
                              <button
                                onClick={() => publishVideo(r.video_url, r.text, r.avatar_name)}
                                className="text-[10px] text-rose-500 hover:text-rose-700 px-1.5 py-0.5 rounded hover:bg-rose-50"
                              >
                                🚀 发布
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
                {/* 全选 + 加载更多 */}
                <div className="flex items-center justify-between mt-2">
                  <label className="flex items-center gap-1.5 text-[10px] text-gray-500 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={records.length > 0 && selectedRecords.length === records.length}
                      onChange={toggleSelectAll}
                      className="accent-violet-600 w-3.5 h-3.5"
                    />
                    全选本页
                  </label>
                  {records.length < recordTotal && (
                    <button
                      onClick={() => loadRecords(false)}
                      className="px-3 py-1 text-[10px] font-medium rounded-lg bg-violet-50 border border-violet-200 text-violet-600 hover:bg-violet-100"
                    >
                      加载更多（{records.length}/{recordTotal}）
                    </button>
                  )}
                </div>
              </>
            )}
          </Card>
        </div>
      </div>

      {/* 上传自定义形象 Modal */}
      <Modal
        open={showAvatarModal}
        onClose={() => setShowAvatarModal(false)}
        title="上传我的形象"
        size="sm"
      >
        <p className="text-xs text-gray-400 mb-3">
          上传你自己的头像/照片，生成视频时以该形象出镜（自动居中裁切，建议竖版人像图效果最佳）
        </p>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <label className="w-16 h-16 rounded-xl border-2 border-dashed border-gray-300 hover:border-blue-400 cursor-pointer overflow-hidden flex items-center justify-center bg-gray-50 flex-shrink-0">
              {avatarForm.preview ? (
                <img src={avatarForm.preview} alt="预览" className="w-full h-full object-cover" />
              ) : (
                <Upload className="w-5 h-5 text-gray-400" />
              )}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  setAvatarForm((prev) => ({ ...prev, file: f, preview: URL.createObjectURL(f) }))
                }}
              />
            </label>
            <div className="flex-1 space-y-2">
              <input
                value={avatarForm.name}
                placeholder="形象名称（如：我的真人形象）"
                maxLength={20}
                onChange={(e) => setAvatarForm((prev) => ({ ...prev, name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <input
                value={avatarForm.desc}
                placeholder="描述（选填，如：休闲装、办公室背景）"
                maxLength={100}
                onChange={(e) => setAvatarForm((prev) => ({ ...prev, desc: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowAvatarModal(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Upload}
              loading={uploading}
              onClick={uploadCustomAvatar}
            >
              上传并创建
            </Button>
          </div>
        </div>
      </Modal>

      {/* 上传照片数字人 Modal（正脸照片 → 口型同步引擎） */}
      <Modal
        open={showPhotoModal}
        onClose={() => setShowPhotoModal(false)}
        title="上传照片数字人"
        size="sm"
      >
        <p className="text-xs text-gray-400 mb-3">
          上传一张<b className="text-gray-600">正面免冠、光线充足</b>的真实人像照片（≥512px），
          即可生成口型同步的数字人口播视频——照片自动检测正脸，漫画/截图/无正脸将被拒绝
        </p>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <label className="w-16 h-16 rounded-xl border-2 border-dashed border-gray-300 hover:border-rose-400 cursor-pointer overflow-hidden flex items-center justify-center bg-gray-50 flex-shrink-0">
              {photoForm.preview ? (
                <img src={photoForm.preview} alt="预览" className="w-full h-full object-cover" />
              ) : (
                <Camera className="w-5 h-5 text-gray-400" />
              )}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  setPhotoForm((prev) => ({ ...prev, file: f, preview: URL.createObjectURL(f) }))
                }}
              />
            </label>
            <div className="flex-1 space-y-2">
              <input
                value={photoForm.name}
                placeholder="形象名称（如：我的真人形象）"
                maxLength={20}
                onChange={(e) => setPhotoForm((prev) => ({ ...prev, name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 outline-none"
              />
              <div className="text-[10px] text-gray-400 leading-relaxed">
                提示：使用照片即代表你拥有该肖像的使用权；生成失败将自动降级 2D 引擎，不会白等
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowPhotoModal(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Camera}
              loading={uploading}
              onClick={uploadPhotoAvatar}
            >
              检测正脸并创建
            </Button>
          </div>
        </div>
      </Modal>

      {/* AI 视频 Modal（可灵大模型/AGNES：文生视频/图生视频/照片活化+配音） */}
      <Modal
        open={showAiVideoModal}
        onClose={() => setShowAiVideoModal(false)}
        title="AI 数字人视频（大模型）"
        size="md"
      >
        <p className="text-xs text-gray-400 mb-3">
          大模型直接生成视频：镜头/光影/场景效果顶级。
          <b className="text-gray-600">混合数字人</b>：照片活化 + 文案自动配音，无需额外音频。
          口型同步精确模式需配音音频链接（下方生成记录点「复制音频」）。
          {aiGatewayCfg?.pricing && (
            <span className="text-violet-500 font-medium">
              价格：{aiGatewayCfg.pricing.text2video_720p} 元/条（720p）·{' '}
              {aiGatewayCfg.pricing.text2video_1080p} 元/条（1080p）
            </span>
          )}
        </p>
        <div className="space-y-3">
          <div className="flex gap-2">
            {[
              { id: 'text2video', label: '文生视频' },
              { id: 'image2video', label: '图生视频' },
              { id: 'lipsync', label: '照片数字人' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setAiVideoForm((p) => ({ ...p, mode: m.id }))}
                className={`flex-1 px-2 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                  aiVideoForm.mode === m.id
                    ? 'border-violet-500 bg-violet-50 text-violet-600'
                    : 'border-gray-200 text-gray-500 hover:border-violet-300'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <textarea
            value={aiVideoForm.prompt}
            onChange={(e) => setAiVideoForm((p) => ({ ...p, prompt: e.target.value }))}
            placeholder={
              aiVideoForm.mode === 'lipsync'
                ? '数字人口播文案，如：大家好，欢迎来到小团智能平台…（将自动合成配音）'
                : '视频内容描述，如：一只小猫在月光下奔跑，电影感，特写镜头'
            }
            rows={3}
            maxLength={1000}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none"
          />
          {aiVideoForm.mode !== 'text2video' && (
            <input
              value={aiVideoForm.imageUrl}
              onChange={(e) => setAiVideoForm((p) => ({ ...p, imageUrl: e.target.value }))}
              placeholder="参考照片地址（平台 /uploads 路径或 http(s) URL）"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
            />
          )}
          {aiVideoForm.mode === 'lipsync' && (
            <div className="space-y-2">
              <input
                value={aiVideoForm.audioUrl}
                onChange={(e) => setAiVideoForm((p) => ({ ...p, audioUrl: e.target.value }))}
                placeholder="配音音频地址（可选，留空=用上方文案自动TTS配音）"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
              />
              <button
                onClick={copyAudioUrl}
                className="text-[10px] text-violet-500 hover:text-violet-700 underline"
              >
                复制当前配音音频链接（精确口型模式用）
              </button>
            </div>
          )}
          <div className="flex gap-2">
            <select
              value={aiVideoForm.duration}
              onChange={(e) => setAiVideoForm((p) => ({ ...p, duration: Number(e.target.value) }))}
              className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none bg-white"
            >
              <option value={5}>5 秒</option>
              <option value={10}>10 秒</option>
            </select>
            <select
              value={aiVideoForm.resolution}
              onChange={(e) => setAiVideoForm((p) => ({ ...p, resolution: e.target.value }))}
              className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none bg-white"
            >
              <option value="720p">720p</option>
              <option value="1080p">1080p</option>
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowAiVideoModal(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Sparkles}
              loading={aiSubmitting}
              onClick={submitAiVideo}
            >
              {aiGatewayCfg?.configured ? '提交生成' : '未配置网关'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* AI 形象 Modal（万相文生图 → 照片数字人） */}
      <Modal
        open={showAiAvatarModal}
        onClose={() => setShowAiAvatarModal(false)}
        title="AI 形象生成"
        size="sm"
      >
        <p className="text-xs text-gray-400 mb-3">
          AI 生成高清人像图并自动创建<b className="text-gray-600">照片数字人形象</b>
          （支持口型同步）。建议描述：年龄/性别/职业/着装/正脸证件照风格。
          {aiGatewayCfg?.pricing && (
            <span className="text-cyan-500 font-medium">价格：{aiGatewayCfg.pricing.avatar_image} 元/张</span>
          )}
        </p>
        <div className="space-y-3">
          <textarea
            value={aiAvatarForm.prompt}
            onChange={(e) => setAiAvatarForm((p) => ({ ...p, prompt: e.target.value }))}
            placeholder="如：一位 30 岁中国女性职场精英，深色西装，正脸证件照风格，棚拍灯光，高清"
            rows={3}
            maxLength={500}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none resize-none"
          />
          <input
            value={aiAvatarForm.name}
            onChange={(e) => setAiAvatarForm((p) => ({ ...p, name: e.target.value }))}
            placeholder="形象名称（如：AI 职场女性）"
            maxLength={20}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowAiAvatarModal(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Sparkles}
              loading={aiSubmitting}
              onClick={submitAiAvatar}
            >
              {aiGatewayCfg?.configured ? '生成形象' : '未配置网关'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* 上传自定义声音 Modal */}
      <Modal
        open={showVoiceModal}
        onClose={() => setShowVoiceModal(false)}
        title="上传我的声音"
        size="sm"
      >
        <p className="text-xs text-gray-400 mb-3">
          上传你自己的录音/音频（mp3/wav/m4a，最长 10 分钟），生成视频时直接用这段声音作为配音——
          记得把文案填成和录音内容一致，字幕才能对上
        </p>
        <div className="space-y-3">
          <label className="flex items-center justify-center gap-2 px-3 py-4 rounded-xl border-2 border-dashed border-gray-300 hover:border-pink-400 cursor-pointer bg-gray-50">
            <Upload className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-500">
              {voiceForm.file ? voiceForm.file.name : '点击选择音频文件'}
            </span>
            <input
              type="file"
              accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (!f) return
                setVoiceForm((prev) => ({ ...prev, file: f }))
              }}
            />
          </label>
          <input
            value={voiceForm.name}
            placeholder="声音名称（如：我的声音）"
            maxLength={20}
            onChange={(e) => setVoiceForm((prev) => ({ ...prev, name: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
          />
          <input
            value={voiceForm.desc}
            placeholder="描述（选填，如：普通话男声、居家录音）"
            maxLength={100}
            onChange={(e) => setVoiceForm((prev) => ({ ...prev, desc: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowVoiceModal(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Upload}
              loading={uploading}
              onClick={uploadCustomVoice}
            >
              上传并创建
            </Button>
          </div>
        </div>
      </Modal>

      {/* 声音克隆 Modal（上传 10-60s 人声样本 → AI 分析匹配音色 + 音调补偿） */}
      <Modal
        open={showCloneModal}
        onClose={() => setShowCloneModal(false)}
        title="克隆我的声音"
        size="sm"
      >
        <p className="text-xs text-gray-400 mb-3">
          上传 10-60 秒干净人声样本（无背景音乐/噪音），AI 分析声音特征后自动匹配最接近的合成音色并做音调补偿——
          之后的数字人配音将带上你的声音气质（样本仅用于分析，不直接作为配音）
        </p>
        <div className="space-y-3">
          <label className="flex items-center justify-center gap-2 px-3 py-4 rounded-xl border-2 border-dashed border-gray-300 hover:border-violet-400 cursor-pointer bg-gray-50">
            <Mic2 className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-500">
              {cloneForm.file
                ? `${cloneForm.file.name}（${(cloneForm.file.size / 1024 / 1024).toFixed(1)}MB）`
                : '点击选择人声样本（10-60 秒）'}
            </span>
            <input
              type="file"
              accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (!f) return
                setCloneForm((prev) => ({ ...prev, file: f }))
              }}
            />
          </label>
          <input
            value={cloneForm.name}
            placeholder="克隆声音名称（如：我的播客音色）"
            maxLength={20}
            onChange={(e) => setCloneForm((prev) => ({ ...prev, name: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
          />
          <label className="flex items-start gap-2 p-3 rounded-lg bg-violet-50 border border-violet-100 cursor-pointer">
            <input
              type="checkbox"
              checked={cloneForm.authorized}
              onChange={(e) => setCloneForm((prev) => ({ ...prev, authorized: e.target.checked }))}
              className="mt-0.5 w-4 h-4 accent-violet-500"
            />
            <span className="text-xs text-violet-700 leading-relaxed">
              我声明：样本为<strong>本人声音</strong>或<strong>已获得授权</strong>使用，同意用于声音克隆合成
              （合规必选，平台保留撤销权利）
            </span>
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowCloneModal(false)}>
              取消
            </Button>
            <Button variant="primary" size="sm" icon={Upload} loading={cloning} onClick={submitVoiceClone}>
              开始克隆
            </Button>
          </div>
        </div>
      </Modal>

      {/* 文案素材库 Modal */}
      <Modal
        open={showArticles}
        onClose={() => setShowArticles(false)}
        title="从素材库加载文案"
        size="md"
      >
        {articles.length === 0 ? (
          <Empty icon={FileText} title="暂无素材" description="请先在发布中心或文案工厂生成文章" />
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {articles.map((a) => (
              <div
                key={a.id}
                className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-violet-200 hover:bg-violet-50/30 transition-all cursor-pointer"
                onClick={() => loadArticle(a)}
              >
                <FileText className="w-4 h-4 text-violet-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {a.title || a.prompt?.slice(0, 40) || '未命名'}
                  </div>
                  <div className="text-xs text-gray-400 truncate">
                    {(a.result || a.prompt || '').slice(0, 80)}
                  </div>
                </div>
                <span className="text-xs text-gray-400 flex-shrink-0">
                  {a.created_at?.slice(0, 10)}
                </span>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* v15 文案体检 Modal：口型友好问题清单 + 一键应用修复版 */}
      <Modal
        open={!!qualityResult}
        onClose={() => setQualityResult(null)}
        title="口播文案体检"
        size="md"
      >
        {qualityResult && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Badge color={qualityResult.ok ? 'green' : 'orange'}>
                {qualityResult.ok ? '朗读友好' : `发现 ${qualityResult.issues.length} 个问题`}
              </Badge>
              <span>
                汉字 {qualityResult.char_count} 字 · 预估朗读 {qualityResult.estimate_sec} 秒
              </span>
            </div>
            {qualityResult.ok ? (
              <div className="px-3 py-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" /> 文案朗读友好，口型同步无隐患，可以放心生成
              </div>
            ) : (
              <div className="space-y-2">
                {qualityResult.issues.map((it, idx) => (
                  <div
                    key={idx}
                    className={`px-3 py-2 rounded-lg border text-xs leading-relaxed ${
                      it.level === 'error'
                        ? 'border-red-200 bg-red-50 text-red-700'
                        : 'border-amber-200 bg-amber-50 text-amber-700'
                    }`}
                  >
                    <div className="font-medium flex items-center gap-1.5">
                      {it.level === 'error' ? (
                        <XCircle className="w-3.5 h-3.5" />
                      ) : (
                        <AlertTriangle className="w-3.5 h-3.5" />
                      )}
                      {it.item}
                    </div>
                    <div className="mt-0.5">{it.detail}</div>
                    <div className="mt-0.5 text-gray-600">💡 {it.suggest}</div>
                  </div>
                ))}
              </div>
            )}
            {qualityResult.fixed_changed && qualityResult.fixed_text && (
              <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-violet-50 border border-violet-200">
                <div className="text-xs text-violet-700 flex-1 min-w-0">
                  已生成修复版：去 emoji/特殊符号 + 数字转中文 + 空行折叠
                </div>
                <Button variant="primary" size="sm" icon={CheckCircle2} onClick={applyQualityFix}>
                  应用修复
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* AI 口播文案助手 Modal：主题 → 3 版口播文案 */}
      <Modal
        open={showScriptModal}
        onClose={() => setShowScriptModal(false)}
        title="AI 口播文案助手"
        size="md"
      >
        <p className="text-xs text-gray-400 mb-3">
          输入主题，AI 按当前场景（{SCENES.find((s) => s.id === sceneId)?.name || ''}）生成 3
          版不同切入角度的口播文案（自动规避违禁词）
        </p>
        <div className="grid grid-cols-2 gap-2 mb-3">
          <input
            value={scriptForm.topic}
            onChange={(e) => setScriptForm((prev) => ({ ...prev, topic: e.target.value }))}
            placeholder="口播主题，如：AI效率工具推荐"
            maxLength={100}
            onKeyDown={(e) => {
              if (e.key === 'Enter') generateScripts()
            }}
            className="col-span-2 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
          />
          <select
            value={scriptForm.platform}
            onChange={(e) => setScriptForm((prev) => ({ ...prev, platform: e.target.value }))}
            className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs outline-none focus:border-violet-500 bg-white"
          >
            <option value="douyin">抖音</option>
            <option value="kuaishou">快手</option>
            <option value="wechat">公众号</option>
            <option value="bilibili">B站</option>
          </select>
          <select
            value={scriptForm.tone}
            onChange={(e) => setScriptForm((prev) => ({ ...prev, tone: e.target.value }))}
            className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs outline-none focus:border-violet-500 bg-white"
          >
            <option value="专业">专业</option>
            <option value="亲切">亲切</option>
            <option value="活泼">活泼</option>
            <option value="煽情">煽情</option>
          </select>
        </div>
        <Button
          variant="primary"
          size="sm"
          icon={Wand2}
          loading={scriptLoading}
          onClick={generateScripts}
          className="w-full mb-3"
        >
          生成 3 版口播文案
        </Button>
        {scriptList.length > 0 && (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {scriptList.map((s, i) => (
              <div
                key={i}
                className="p-3 rounded-lg border border-gray-100 hover:border-violet-200 hover:bg-violet-50/30 transition-all"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-medium text-violet-500">版本 {i + 1}</span>
                  <button
                    onClick={() => applyScript(s)}
                    className="text-[10px] text-violet-600 hover:text-violet-800 font-medium underline"
                  >
                    使用此版
                  </button>
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">{s}</p>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  )
}
