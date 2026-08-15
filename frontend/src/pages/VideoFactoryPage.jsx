import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Video,
  Film,
  Clapperboard,
  Play,
  Download,
  Sparkles,
  Loader2,
  RefreshCw,
  Wand2,
  Trash2,
  Scissors,
  Music,
  Subtitles,
  Package,
  BookOpen,
  Layers,
  ChevronDown,
  Sliders,
  Upload,
  X,
  ScanLine,
  ScanSearch,
  Palette,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatBytes } from '../lib/format'
import { friendlyError } from '../lib/errors'
import {
  Modal,
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  Badge,
  PageHeader,
  ConfirmDialog,
  Pagination,
} from '../components/ui'
import ShareButton from '../components/ShareButton'
import FavoriteButton from '../components/FavoriteButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'
import useToolHistory from '../hooks/useToolHistory'
import HistoryPanel from '../components/HistoryPanel'

const MEDIA_BASE = api.defaults.baseURL
const absUrl = (u) => (u ? (u.startsWith('http') ? u : `${MEDIA_BASE}${u}`) : '')

// 发布包平台规格预设（商业化 v14）：ffmpeg cover 模式转码不变形
const PUBLISH_PLATFORMS = [
  { id: 'douyin', name: '抖音', spec: '1080×1920 竖屏' },
  { id: 'bilibili', name: 'B站', spec: '1920×1080 横屏' },
  { id: 'weixin', name: '视频号', spec: '1080×1230 竖屏' },
]

const PRESET_CATEGORIES = [
  {
    name: '自然风光',
    icon: '🌄',
    presets: [
      'A beautiful sunset over the ocean with gentle waves, cinematic quality, golden hour',
      'Aerial view of a misty mountain range at sunrise, drone footage, epic landscape',
      'Time-lapse of clouds moving over mountains at sunrise, golden light, 4K',
      'A peaceful lake reflecting snow-capped mountains, calm water, nature documentary',
    ],
  },
  {
    name: '城市人文',
    icon: '🏙️',
    presets: [
      'City street at night with neon lights and rain reflections, cyberpunk mood',
      'A cozy coffee shop on a rainy day, warm lighting, cinematic, lo-fi aesthetic',
      'Busy Tokyo intersection at night, time-lapse, people flowing, urban energy',
      'Vintage European old town street, cobblestone, warm afternoon light, travel film',
    ],
  },
  {
    name: '产品展示',
    icon: '📦',
    presets: [
      'Product showcase of a sleek smartphone rotating on a marble surface, studio lighting',
      'Perfume bottle on a silk fabric with soft bokeh lights, luxury commercial',
      'Sneakers floating in mid-air with dynamic lighting, sports commercial style',
      'Coffee being poured into a cup, slow motion, warm tones, food commercial',
    ],
  },
  {
    name: '抽象艺术',
    icon: '🎨',
    presets: [
      'Abstract colorful ink dropping into water, slow motion, macro, vibrant colors',
      'Geometric shapes morphing and transforming, neon glow, digital art',
      'Liquid metal flowing and forming patterns, chrome reflection, futuristic',
      'Particle effects forming a human silhouette, sci-fi, blue and purple glow',
    ],
  },
  {
    name: '自然微观',
    icon: '🔬',
    presets: [
      'Time-lapse of a flower blooming in fast motion, macro photography, vivid colors',
      'Slow motion water droplets falling into a pond, high speed photography',
      'Underwater scene with colorful coral and fish, crystal clear water, nature doc',
      'A cute cat walking on the beach at sunset, warm golden light, heartwarming',
    ],
  },
  {
    name: '影视剧情',
    icon: '🎬',
    presets: [
      'A lone traveler walking through a desert at dusk, long shadow, epic western film mood',
      'Two people meeting on a rainy street, slow motion, dramatic lighting, romance film',
      'A detective walking into a dimly lit office, noir atmosphere, film grain, mystery',
      'A robot waking up in a forest, curious gaze, sci-fi drama, soft morning light',
    ],
  },
  {
    name: '科幻未来',
    icon: '🚀',
    presets: [
      'Futuristic city skyline with flying vehicles at sunset, sci-fi concept art, cinematic',
      'A spaceship flying through a nebula with colorful gas clouds, epic space odyssey',
      "Holographic interface floating above a person's hand, futuristic tech, blue glow",
      'Dystopian megacity interior with neon signs and rain, blade runner style',
    ],
  },
]

const CAMERA_MOTIONS = [
  { value: '', label: '固定镜头', kw: '' },
  { value: 'slow push in', label: '推近', kw: 'slow push in, dolly zoom' },
  { value: 'pull back', label: '拉远', kw: 'gradual pull back' },
  { value: 'pan left to right', label: '横移', kw: 'smooth pan left to right' },
  { value: 'orbit around', label: '环绕', kw: 'orbit around the subject, 360 rotation' },
  { value: 'handheld', label: '手持', kw: 'handheld camera, natural shake, documentary feel' },
  { value: 'crane up', label: '升降', kw: 'crane shot rising upward' },
]

const MOODS = [
  { value: '', label: '默认', kw: '' },
  { value: 'warm', label: '温暖治愈', kw: 'warm cozy atmosphere, soft golden light, heartwarming' },
  { value: 'epic', label: '史诗宏大', kw: 'epic scale, dramatic lighting, grandiose atmosphere' },
  { value: 'dreamy', label: '梦幻唯美', kw: 'dreamy ethereal mood, soft pastel tones, magical atmosphere' },
  { value: 'cyber', label: '赛博冷峻', kw: 'cold cyberpunk mood, neon blue and purple, high contrast' },
  { value: 'dark', label: '暗黑悬疑', kw: 'dark mysterious mood, low key lighting, suspenseful' },
  { value: 'joyful', label: '欢乐活泼', kw: 'joyful vibrant mood, bright colors, energetic' },
]

const ASPECTS = [
  { label: '16:9 横屏', value: '1920x1080' },
  { label: '9:16 竖屏', value: '1080x1920' },
  { label: '1:1 方形', value: '1080x1080' },
  { label: '4:3 经典', value: '1280x960' },
]

const VIDEO_STYLES = [
  { value: '', label: '默认', desc: '无特殊风格' },
  { value: 'cinematic', label: '电影感', desc: '宽色域/景深' },
  { value: 'documentary', label: '纪录片', desc: '真实/自然' },
  { value: 'animation', label: '动画风', desc: '卡通/流畅' },
  { value: 'vlog', label: 'Vlog', desc: '手持/亲切' },
  { value: 'commercial', label: '广告', desc: '精致/吸引' },
]

const CAMERA_ANGLES = [
  { value: '', label: '默认' },
  { value: 'wide shot', label: '远景' },
  { value: 'medium shot', label: '中景' },
  { value: 'close-up', label: '近景' },
  { value: 'extreme close-up', label: '特写' },
  { value: 'aerial/drone', label: '航拍' },
  { value: 'low angle', label: '仰拍' },
]

const RESOLUTIONS = [
  { label: '480p', value: '854x480' },
  { label: '720p', value: '1280x720' },
  { label: '1080p', value: '1920x1080' },
]

const MODES = [
  { value: 'ti2vid', label: '文生视频' },
  { value: 'i2vid', label: '图生视频' },
  { value: 'keyframes', label: '关键帧动画' },
]

const FRAME_RATES = [24, 30, 60]

export default function VideoFactoryPage() {
  const toast = useToast()
  const [stats, setStats] = useState({ total_videos: 0, api_configured: false })
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 云端提示词库
  const [cloudPrompts, setCloudPrompts] = useState([])

  // 生成（专业基线：输入态持久化，刷新不丢草稿；参考图 image 体积大不持久化）
  const [inputs, setInputs] = usePersistentToolState('video_factory_inputs', {
    prompt: '',
    width: 1152,
    height: 768,
    duration: 5,
    mode: 'ti2vid',
    frameRate: 24,
    videoStyle: '',
    cameraAngle: '',
    cameraMotion: '',
    mood: '',
  })
  const { prompt, width, height, duration, mode, frameRate, videoStyle, cameraAngle, cameraMotion, mood } = inputs
  const setPrompt = (v) => setInputs((p) => ({ ...p, prompt: v ?? '' }))
  const setWidth = (v) => setInputs((p) => ({ ...p, width: v }))
  const setHeight = (v) => setInputs((p) => ({ ...p, height: v }))
  const setDuration = (v) => setInputs((p) => ({ ...p, duration: v }))
  const setMode = (v) => setInputs((p) => ({ ...p, mode: v }))
  const setFrameRate = (v) => setInputs((p) => ({ ...p, frameRate: v }))
  const setVideoStyle = (v) => setInputs((p) => ({ ...p, videoStyle: v ?? '' }))
  const setCameraAngle = (v) => setInputs((p) => ({ ...p, cameraAngle: v ?? '' }))
  const setCameraMotion = (v) => setInputs((p) => ({ ...p, cameraMotion: v ?? '' }))
  const setMood = (v) => setInputs((p) => ({ ...p, mood: v ?? '' }))
  const [image, setImage] = useState('')
  const [imageError, setImageError] = useState(false) // 参考图预览失败提示
  const [imageFile, setImageFile] = useState(null) // 图生视频：本地图片上传
  const [imagePreview, setImagePreview] = useState('') // 本地图片预览 URL
  const imageInputRef = useRef(null)
  const [creating, setCreating] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [enhancingPrompt, setEnhancingPrompt] = useState(false) // v20：AI 画质增强
  const [autoEnhance, setAutoEnhance] = useState(true) // 默认自动增强画面描述（提升视频质感）
  const [lastResult, setLastResult] = useState(null)
  const { submitTask, startPolling, stopPolling } = useAsyncTask()
  const { history: genHistory, add: addGenHistory, remove: removeGenHistory, clear: clearGenHistory } =
    useToolHistory('video_factory_history_v1', 30)

  // 播放器
  const [selectedVideo, setSelectedVideo] = useState(null)
  const videoRef = useRef(null)

  // 删除
  const [deleteTarget, setDeleteTarget] = useState(null)

  // 发布包（商业化 v14）：按平台规格转码成片 + 抽帧封面 + 发布文案 + 质量报告
  const [packVideo, setPackVideo] = useState(null)
  const [packPlatform, setPackPlatform] = useState('douyin')
  const [packTitle, setPackTitle] = useState('')
  const [packDesc, setPackDesc] = useState('')
  const [packing, setPacking] = useState(false)

  // 视频后期工具（拼接 / 配乐 / 字幕 / 批量转码）
  const [postMode, setPostMode] = useState(null) // 'concat' | 'music' | 'subtitle' | 'transcode' | null
  const [postBusy, setPostBusy] = useState(false)
  const [concatSel, setConcatSel] = useState([]) // 拼接/转码选中的文件名
  const [postVideo, setPostVideo] = useState('') // 配乐/字幕目标视频
  const [bgmUrl, setBgmUrl] = useState('')
  const [bgVolume, setBgVolume] = useState(0.3)
  const [srtContent, setSrtContent] = useState('')
  const [postResult, setPostResult] = useState(null) // { mode, url, filename }
  // v15：批量转码参数（宽高留空保持原分辨率）
  const [transcodeWidth, setTranscodeWidth] = useState('')
  const [transcodeHeight, setTranscodeHeight] = useState('')
  const [transcodeCrf, setTranscodeCrf] = useState(23)
  // v22：AI 后期增强（自动字幕 / 智能分析 / 视频滤镜）
  const [aiPostMode, setAiPostMode] = useState(null) // 'auto-subtitle' | 'analyze' | 'filter'
  const [aiPostBusy, setAiPostBusy] = useState(false)
  const [aiPostVideo, setAiPostVideo] = useState('')
  const [subtitleLang, setSubtitleLang] = useState('zh')
  const [filterType, setFilterType] = useState('sepia')
  const [filterIntensity, setFilterIntensity] = useState(0.5)
  const [aiPostResult, setAiPostResult] = useState(null) // { mode, url, filename, ... }
  // v15：脚本文案模板库（口播/剧情/科普）
  const [scriptTemplates, setScriptTemplates] = useState([])
  const [scriptCategory, setScriptCategory] = useState('全部')
  const [scriptTopic, setScriptTopic] = useState('')
  // v21：视频模板市场（TikTok/电商/社媒/节日/生活 → 广告短片，复用图片引擎渲染镜头帧 + ffmpeg 运镜/转场/BGM）
  const [vtplTemplates, setVtplTemplates] = useState([])
  const [vtplCategory, setVtplCategory] = useState('全部')
  // v24：模板市场默认收起（横幅形式），避免占用大片纵向空间挤压下方生成表单
  const [vtplOpen, setVtplOpen] = useState(false)
  const [vtplModal, setVtplModal] = useState(null) // 正在查看的模板
  const [vtplVars, setVtplVars] = useState([]) // 模板变量（文本替换 + 图片槽）
  const [vtplOverrides, setVtplOverrides] = useState({}) // 文本变量 {key: text}
  const [vtplImages, setVtplImages] = useState({}) // 图片槽 {key: url}
  const [vtplAccess, setVtplAccess] = useState('once')
  const [vtplBusy, setVtplBusy] = useState(false)
  const [vtplResult, setVtplResult] = useState(null) // {url, cover, duration, filename}

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/api/video-factory/stats')
      setStats(res.data)
    } catch {
      /* 静默 */
    }
  }, [])

  const fetchVideos = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/video-factory/list')
      const list = res.data.videos || []
      setVideos(list)
      // 旧视频封面由后端后台补抽帧：存在无封面项时稍后自动刷新一次
      if (list.some((v) => !v.cover_url)) {
        setTimeout(() => fetchVideos(), 12000)
      }
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()
    fetchVideos()
    fetchCloudPrompts()
    fetchScriptTemplates()
    fetchVtplTemplates()
    return () => {
      stopPolling()
    }
  }, [fetchStats, fetchVideos, stopPolling])

  const fetchScriptTemplates = async () => {
    try {
      const res = await api.get('/api/video-factory/prompts/scripts')
      setScriptTemplates(res.data?.templates || [])
    } catch {
      /* 静默：后端无此接口时降级为无模板 */
    }
  }

  const fetchCloudPrompts = async () => {
    try {
      const res = await api.get('/api/video-factory/prompts')
      setCloudPrompts(res.data?.prompts || [])
    } catch {
      /* 静默：后端无此接口时降级为本地模板 */
    }
  }

  // v21：视频模板市场数据
  const fetchVtplTemplates = async () => {
    try {
      const res = await api.get('/api/video-templates/list')
      setVtplTemplates(res.data?.items || [])
    } catch {
      /* 静默：后端无此接口时隐藏模板市场 */
    }
  }

  // v21：打开模板 → 拉取变量清单（文本替换 + 图片槽）
  const openVtplModal = async (item) => {
    setVtplModal(item)
    setVtplResult(null)
    setVtplOverrides({})
    setVtplImages({})
    setVtplVars([])
    try {
      const res = await api.get(`/api/video-templates/${item.id}`)
      const vars = res.data?.vars || []
      setVtplVars(vars)
      const ov = {}
      const im = {}
      vars.forEach((v) => {
        if (v.type === 'text') ov[v.key] = v.text ?? ''
        else if (v.type === 'image') im[v.key] = ''
      })
      setVtplOverrides(ov)
      setVtplImages(im)
    } catch {
      /* 静默 */
    }
  }

  // v21：购买授权（收费模板：按次 / 按天 / 按月，积分）
  const handleVtplPurchase = async (accessType) => {
    if (!vtplModal || vtplBusy) return
    setVtplBusy(true)
    try {
      const fd = new FormData()
      fd.append('template_id', vtplModal.id)
      fd.append('access_type', accessType)
      const res = await api.post('/api/video-templates/purchase', fd)
      toast.success(res.data?.message || '购买成功')
    } catch (e) {
      toast.error(`购买失败：${e.message}`)
    } finally {
      setVtplBusy(false)
    }
  }

  // v21：渲染成片（镜头帧 → Ken Burns 运镜 → xfade 转场 → 节拍 BGM，耗时 30-90s）
  const handleVtplRender = async () => {
    if (!vtplModal || vtplBusy) return
    setVtplBusy(true)
    setVtplResult(null)
    try {
      const fd = new FormData()
      fd.append('template_id', vtplModal.id)
      fd.append('overrides', JSON.stringify(vtplOverrides))
      fd.append('images', JSON.stringify(Object.fromEntries(Object.entries(vtplImages).filter(([, v]) => v))))
      const res = await api.post('/api/video-templates/render', fd, { timeout: 600000 })
      setVtplResult({ ...res.data, url: absUrl(res.data.url), cover: absUrl(res.data.cover) })
      toast.success('视频渲染完成！')
      fetchVtplTemplates() // 刷新使用热度
    } catch (e) {
      toast.error(`渲染失败：${e.message}`)
    } finally {
      setVtplBusy(false)
    }
  }

  // 异步任务进度回调（提交与手动刷新共用）
  const handleTaskUpdate = (t) => {
    setLastResult((prev) => ({ ...prev, progress: t.progress, stage: t.stage }))
  }
  const handleTaskSuccess = (data) => {
    if (data && data.url) {
      addGenHistory({ type: '视频', content: (inputs.prompt || 'AI 视频').slice(0, 50), url: data.url })
    }
    setLastResult({
      ...data,
      url: data.url ? absUrl(data.url) : null,
      status: 'completed',
      created_at: new Date().toLocaleString(),
    })
    setCreating(false)
    toast.success('视频生成完成！')
    fetchVideos()
  }
  const handleTaskError = (e) => {
    setLastResult((prev) => ({ ...prev, status: 'failed', error: e.message }))
    setCreating(false)
    toast.error(`视频生成失败：${e.message}`)
  }

  // v20：AI 画质增强（调用专用接口；失败静默回退原描述，不阻塞生成）
  const handleEnhancePrompt = async () => {
    if (!prompt.trim()) {
      toast.error('请先输入视频描述，再使用 AI 增强')
      return
    }
    if (enhancingPrompt) return
    setEnhancingPrompt(true)
    try {
      const fd = new FormData()
      fd.append('prompt', prompt)
      fd.append('mode', mode === 'ti2vid' ? 'ti2vid' : 'i2vid')
      const res = await api.post('/api/video-factory/enhance-prompt', fd)
      const d = res.data || {}
      if (d.enhanced) setPrompt(d.enhanced)
      toast.success('已 AI 增强画面描述，可直接生成')
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'AI 增强失败')
    } finally {
      setEnhancingPrompt(false)
    }
  }

  const handleCreate = async () => {
    if (!prompt.trim()) {
      toast.error('请输入视频描述')
      return
    }
    setCreating(true)
    setLastResult(null)
    // 自动增强画面描述（默认开）：简短描述 → 专业画面描述（运动/镜头/光影/氛围）
    let finalPrompt = prompt
    if (autoEnhance && prompt.trim().length < 120) {
      try {
        const enRes = await api.post('/api/video-factory/enhance-prompt', { prompt: prompt.trim() })
        if (enRes.data?.enhanced) finalPrompt = enRes.data.enhanced
      } catch { /* 增强失败用原描述 */ }
    }
    const form = new FormData()
    // 风格/镜头/运镜/情绪作为结构化控制项，拼入 prompt 参与生成（避免死控件）
    const parts = [finalPrompt]
    if (videoStyle) parts.push(VIDEO_STYLES.find((s) => s.value === videoStyle)?.label)
    if (cameraAngle) parts.push(cameraAngle)
    if (cameraMotion) parts.push(CAMERA_MOTIONS.find((m) => m.value === cameraMotion)?.kw)
    if (mood) parts.push(MOODS.find((m) => m.value === mood)?.kw)
    form.append('prompt', parts.filter(Boolean).join(', '))
    form.append('width', width)
    form.append('height', height)
    form.append('duration', duration)
    form.append('mode', mode)
    if (mode === 'i2vid') {
      // 图生视频：本地上传图片或 http/https 直链（二选一）
      if (imageFile) {
        form.append('image_upload', imageFile)
      } else {
        const imgUrl = image.trim()
        if (!imgUrl) {
          toast.error('图生视频模式需要参考图（可上传本地图片或填写 URL）')
          setCreating(false)
          return
        }
        if (!/^https?:\/\//.test(imgUrl)) {
          toast.error('参考图片 URL 必须以 http:// 或 https:// 开头')
          setCreating(false)
          return
        }
        form.append('image', imgUrl)
      }
    }
    form.append('frame_rate', frameRate)
    const r = await submitTask('/api/video-factory/generate', form, {
      onUpdate: handleTaskUpdate,
      onSuccess: handleTaskSuccess,
      onError: handleTaskError,
    })
    if (r.task_id) {
      setLastResult({
        video_id: r.task_id,
        status: 'processing',
        prompt,
        created_at: new Date().toLocaleString(),
      })
      toast.success('视频任务已提交，后台生成中（可在任务中心查看进度）')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/video-factory/delete/${deleteTarget.filename}`)
      toast.success('视频已删除')
      if (selectedVideo?.filename === deleteTarget.filename) setSelectedVideo(null)
      setDeleteTarget(null)
      fetchVideos()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const handlePlay = (video) => {
    setSelectedVideo({ ...video, url: absUrl(video.url) })
    setTimeout(() => videoRef.current?.play(), 100)
  }

  const handleDownload = async (video) => {
    try {
      const res = await fetch(absUrl(video.url))
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = (video.title ? `${video.title}.mp4` : video.filename)
      a.click()
      URL.revokeObjectURL(url)
      toast.success('已开始下载')
    } catch (e) {
      toast.error(`下载失败：${e.message}`)
    }
  }

  // 视频发布包：按平台规格 cover 转码成片 + 抽帧封面 + 发布文案 + 质量报告
  const downloadPublishPack = async () => {
    if (!packVideo) return
    setPacking(true)
    try {
      const fd = new FormData()
      fd.append('filename', packVideo.filename)
      fd.append('platform', packPlatform)
      fd.append('video_title', packTitle.trim() || packVideo.title || 'AI 视频作品')
      fd.append('video_desc', packDesc.trim())
      const res = await api.post('/api/video-factory/publish-pack', fd, {
        responseType: 'blob',
        timeout: 600000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `video_publish_pack_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setPackVideo(null)
      toast.success('视频发布包已生成：规格成片 + 封面 + 发布文案 + 质量报告')
    } catch (e) {
      toast.error(`发布包生成失败：${e.message}`)
    } finally {
      setPacking(false)
    }
  }

  // ── 视频后期工具 ──
  const toggleConcatSel = (filename) => {
    setConcatSel((prev) =>
      prev.includes(filename) ? prev.filter((f) => f !== filename) : [...prev, filename]
    )
  }

  const openPost = (mode) => {
    setPostMode(mode)
    setPostResult(null)
    if (mode === 'concat' || mode === 'transcode') {
      setConcatSel([])
    } else {
      setPostVideo('')
    }
  }

  // 拼接：多个视频按顺序合成一个（统一分辨率 + 自动补静音）
  const handlePostConcat = async () => {
    if (concatSel.length < 2) {
      toast.error('请至少选择两个视频')
      return
    }
    setPostBusy(true)
    setPostResult(null)
    try {
      const form = new FormData()
      form.append('filenames', concatSel.join(','))
      const res = await api.post('/api/video-factory/tools/concat', form, { timeout: 600000 })
      setPostResult({ mode: 'concat', ...res.data })
      toast.success('视频拼接完成')
      fetchVideos()
    } catch (e) {
      toast.error(`拼接失败：${e.message}`)
    } finally {
      setPostBusy(false)
    }
  }

  // 批量转码：统一 H.264 + 可选分辨率，逐项报告成功/失败
  const handlePostTranscode = async () => {
    if (concatSel.length === 0) {
      toast.error('请至少选择一个视频')
      return
    }
    setPostBusy(true)
    setPostResult(null)
    try {
      const form = new FormData()
      form.append('filenames', concatSel.join(','))
      if (transcodeWidth) form.append('width', transcodeWidth)
      if (transcodeHeight) form.append('height', transcodeHeight)
      form.append('crf', transcodeCrf || 23)
      const res = await api.post('/api/video-factory/tools/transcode', form, { timeout: 600000 })
      setPostResult({ mode: 'transcode', ...res.data })
      if (res.data.ok > 0) {
        toast.success(`转码完成：成功 ${res.data.ok} 个${res.data.failed ? `，失败 ${res.data.failed} 个` : ''}`)
        fetchVideos()
      } else {
        toast.error('转码失败，请检查视频文件')
      }
    } catch (e) {
      toast.error(`转码失败：${e.message}`)
    } finally {
      setPostBusy(false)
    }
  }

  // 配乐：原声 + BGM 混音（BGM 支持 URL 或服务器本地路径）
  const handlePostMusic = async () => {
    if (!postVideo) {
      toast.error('请选择目标视频')
      return
    }
    if (!bgmUrl.trim()) {
      toast.error('请输入 BGM 音乐地址')
      return
    }
    setPostBusy(true)
    setPostResult(null)
    try {
      const form = new FormData()
      form.append('video', postVideo)
      form.append('music', bgmUrl.trim())
      form.append('bg_volume', bgVolume)
      const res = await api.post('/api/video-factory/tools/music', form, { timeout: 600000 })
      setPostResult({ mode: 'music', ...res.data })
      toast.success('配乐完成')
      fetchVideos()
    } catch (e) {
      toast.error(`配乐失败：${e.message}`)
    } finally {
      setPostBusy(false)
    }
  }

  // 字幕：SRT 文本烧录进画面（需 libass，已自动优先 imageio-ffmpeg）
  const handlePostSubtitle = async () => {
    if (!postVideo) {
      toast.error('请选择目标视频')
      return
    }
    if (!srtContent.trim()) {
      toast.error('请输入字幕内容')
      return
    }
    setPostBusy(true)
    setPostResult(null)
    try {
      const form = new FormData()
      form.append('video', postVideo)
      form.append('srt_content', srtContent)
      const res = await api.post('/api/video-factory/tools/subtitle', form, { timeout: 600000 })
      setPostResult({ mode: 'subtitle', ...res.data })
      toast.success('字幕烧录完成')
      fetchVideos()
    } catch (e) {
      toast.error(`字幕烧录失败：${e.message}`)
    } finally {
      setPostBusy(false)
    }
  }

  // ── v22 AI 后期增强：自动字幕 / 智能分析 / 视频滤镜 ──
  const openAiPost = (mode) => {
    setAiPostMode(mode)
    setAiPostResult(null)
    setAiPostVideo(videos[0]?.filename || '')
  }

  const handleAiAutoSubtitle = async () => {
    if (!aiPostVideo) {
      toast.error('请选择目标视频')
      return
    }
    setAiPostBusy(true)
    setAiPostResult(null)
    try {
      const form = new FormData()
      form.append('video', aiPostVideo)
      form.append('language', subtitleLang)
      const res = await api.post('/api/video-factory/tools/auto-subtitle', form, { timeout: 600000 })
      setAiPostResult({ mode: 'auto-subtitle', ...res.data })
      toast.success('自动字幕生成完成')
      fetchVideos()
    } catch (e) {
      toast.error(`自动字幕失败：${friendlyError(e) || e.message}`)
    } finally {
      setAiPostBusy(false)
    }
  }

  const handleAiAnalyze = async () => {
    if (!aiPostVideo) {
      toast.error('请选择目标视频')
      return
    }
    setAiPostBusy(true)
    setAiPostResult(null)
    try {
      const form = new FormData()
      form.append('video', aiPostVideo)
      form.append('analysis_type', 'general')
      const res = await api.post('/api/video-factory/tools/analyze', form, { timeout: 300000 })
      setAiPostResult({ mode: 'analyze', ...res.data })
    } catch (e) {
      toast.error(`智能分析失败：${friendlyError(e) || e.message}`)
    } finally {
      setAiPostBusy(false)
    }
  }

  const handleAiFilter = async () => {
    if (!aiPostVideo) {
      toast.error('请选择目标视频')
      return
    }
    setAiPostBusy(true)
    setAiPostResult(null)
    try {
      const form = new FormData()
      form.append('video', aiPostVideo)
      form.append('filter_type', filterType)
      form.append('intensity', String(filterIntensity))
      const res = await api.post('/api/video-factory/tools/filters', form, { timeout: 600000 })
      setAiPostResult({ mode: 'filter', ...res.data })
      toast.success('滤镜应用完成')
      fetchVideos()
    } catch (e) {
      toast.error(`滤镜应用失败：${friendlyError(e) || e.message}`)
    } finally {
      setAiPostBusy(false)
    }
  }

  const statsCards = [
    { label: '视频总数', value: stats.total_videos, color: 'text-blue-600' },
    {
      label: 'API 状态',
      value: stats.api_configured ? '已配置' : '未配置',
      color: stats.api_configured ? 'text-green-600' : 'text-red-600',
    },
    { label: '当前价格', value: stats.price || '免费', color: 'text-purple-600' },
    { label: '模型版本', value: stats.model || 'V2.0', color: 'text-orange-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="视频工厂"
        description="文生视频、图生视频、关键帧动画"
        icon={Video}
        iconColor="from-blue-500 to-cyan-500"
        actions={
          <Button
            variant="secondary"
            icon={RefreshCw}
            onClick={() => {
              fetchStats()
              fetchVideos()
            }}
          >
            刷新
          </Button>
        }
      />

      {/* v24 视频模板市场：可折叠横幅（默认收起）+ 展开后横向滚动紧凑卡片，不再占满纵向空间 */}
      {vtplTemplates.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200">
          <button
            onClick={() => setVtplOpen(!vtplOpen)}
            className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left group"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Clapperboard className="w-5 h-5 text-blue-500 shrink-0" />
              <span className="font-semibold text-gray-900 whitespace-nowrap">视频模板市场</span>
              <span className="text-xs text-gray-400 font-normal hidden md:inline truncate">
                专业级广告短片模板 · 一键渲染成片（Ken Burns 运镜 + 转场 + 节拍 BGM）
              </span>
              <span className="text-xs text-gray-400 shrink-0">{vtplTemplates.length} 个模板</span>
            </div>
            <span className="flex items-center gap-1 text-sm text-blue-600 shrink-0">
              {vtplOpen ? '收起模板' : '展开模板'}
              <ChevronDown
                className={`w-4 h-4 transition-transform ${vtplOpen ? 'rotate-180' : ''}`}
              />
            </span>
          </button>
          {vtplOpen && (
            <div className="px-5 pb-5 space-y-3">
              {/* 分类筛选 */}
              <div className="flex flex-wrap gap-1.5">
                {['全部', ...new Set(vtplTemplates.map((t) => t.category))].map((c) => (
                  <button
                    key={c}
                    onClick={() => setVtplCategory(c)}
                    className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                      vtplCategory === c
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {c}
                    <span className="ml-1 opacity-70">
                      {c === '全部' ? vtplTemplates.length : vtplTemplates.filter((t) => t.category === c).length}
                    </span>
                  </button>
                ))}
              </div>
              {/* 模板卡片：横向滚动一行，不再 5 列网格占满纵向空间 */}
              <div className="flex gap-3 overflow-x-auto pb-2">
                {vtplTemplates
                  .filter((t) => vtplCategory === '全部' || t.category === vtplCategory)
                  .map((t) => (
                    <button
                      key={t.id}
                      onClick={() => openVtplModal(t)}
                      className="group text-left rounded-xl border border-gray-200 overflow-hidden hover:border-blue-300 hover:shadow-lg transition-all w-36 sm:w-40 shrink-0"
                    >
                      <div className="relative aspect-[3/4] bg-gray-100 overflow-hidden">
                        <img
                          src={absUrl(t.preview)}
                          alt={t.name}
                          loading="lazy"
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none'
                          }}
                        />
                        <span className="absolute top-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-white">
                          {t.platform}
                        </span>
                        {t.pricing?.mode !== 'free' && (
                          <span className="absolute top-1.5 right-1.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-500 text-white">
                            {t.pricing_label}
                          </span>
                        )}
                        <span className="absolute bottom-1.5 right-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-white">
                          {(t.duration || 0).toFixed(1)}s
                        </span>
                      </div>
                      <div className="p-2">
                        <div className="text-xs font-medium text-gray-800 truncate">{t.name}</div>
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{t.category}</span>
                          <span className="text-[10px] text-gray-400">{t.usage} 次使用</span>
                        </div>
                      </div>
                    </button>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 统计 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statsCards.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
            <div className="text-sm text-gray-500 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* 生成表单 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-blue-500" />
            创建视频任务
          </h2>
          <button
            onClick={() => {
              const localPresets = PRESET_CATEGORIES.flatMap((c) => c.presets)
              const allPresets =
                cloudPrompts.length > 0 ? [...cloudPrompts, ...localPresets] : localPresets
              setPrompt(allPresets[Math.floor(Math.random() * allPresets.length)])
            }}
            className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <Wand2 className="w-4 h-4" />
            随机提示词
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center justify-between">
            <span>
              视频描述 <span className="text-red-500">*</span>
            </span>
            <EnhancePromptButton
              text={prompt}
              onEnhance={(t) => setPrompt(t)}
              style="video"
              className="text-blue-600 hover:text-blue-700"
            />
            <button
              onClick={handleEnhancePrompt}
              disabled={enhancingPrompt}
              className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              title="AI 增强为专业画面描述（含运动/镜头语言/光影/氛围）"
            >
              {enhancingPrompt ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              {enhancingPrompt ? '增强中…' : '✨ AI 增强'}
            </button>
            <label className="inline-flex items-center gap-1 text-[11px] text-gray-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={autoEnhance}
                onChange={(e) => setAutoEnhance(e.target.checked)}
                className="accent-blue-600 w-3 h-3"
              />
              自动增强画面
            </label>
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="描述你想要的视频内容，例如：A beautiful sunset over the ocean, waves gently crashing on the shore..."
            rows={3}
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
          />
        </div>

        {/* 核心操作：生成按钮（主路径最优先） */}
        <div className="rounded-xl bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-100 p-3">
          <div className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-blue-900">
                {mode === 'ti2vid' ? '文生视频' : '图生视频'}
              </div>
              <div className="text-[11px] text-blue-600/70 mt-0.5">
                {mode === 'ti2vid'
                  ? '输入描述即可生成 · 支持风格/镜头/运镜等高级参数'
                  : '填写参考图 URL + 描述即可生成'}
              </div>
            </div>
            <Button
              variant="gradient"
              size="lg"
              icon={Sparkles}
              loading={creating}
              disabled={!prompt.trim()}
              onClick={handleCreate}
              className="!px-6 whitespace-nowrap"
            >
              {creating ? '创建任务中...' : '生成视频'}
            </Button>
          </div>
        </div>

        {/* 高级参数（默认收起，避免主路径被参数淹没） */}
        <div className="rounded-xl border border-gray-200 overflow-hidden">
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <span className="flex items-center gap-1.5 text-xs font-medium text-gray-600">
              <Sliders className="w-3.5 h-3.5 text-gray-400" />
              高级参数
              <span className="text-gray-400 font-normal">
                （模板/风格/镜头/分辨率/时长等）
              </span>
            </span>
            <ChevronDown
              className={`w-3.5 h-3.5 text-gray-400 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
            />
          </button>
          {showAdvanced && (
            <div className="p-4 space-y-4">
        {/* 分类提示词模板 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">提示词模板</label>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {PRESET_CATEGORIES.map((cat, ci) => (
              <div key={ci} className="relative group">
                <button className="w-full flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left">
                  <span className="text-base">{cat.icon}</span>
                  <span className="text-xs text-gray-700">{cat.name}</span>
                </button>
                <div className="absolute z-10 top-full left-0 mt-1 w-72 bg-white rounded-xl border border-gray-200 shadow-lg p-2 space-y-1 hidden group-hover:block">
                  {cat.presets.map((p, pi) => (
                    <button
                      key={pi}
                      onClick={() => setPrompt(p)}
                      className="w-full text-left text-xs px-2 py-1.5 rounded-lg hover:bg-blue-50 text-gray-600 truncate transition-colors"
                    >
                      {p.slice(0, 40)}...
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 云端提示词库 */}
        {cloudPrompts.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1.5">
              <RefreshCw className="w-3.5 h-3.5 text-blue-500" />
              云端提示词库
              <span className="text-xs text-gray-400 font-normal">
                在线精选提示词，点击即可填充
              </span>
            </label>
            <div className="flex flex-wrap gap-2">
              {cloudPrompts.map((p, pi) => (
                <button
                  key={pi}
                  onClick={() => setPrompt(p)}
                  title={p}
                  className="px-3 py-1.5 rounded-lg border border-blue-200 bg-blue-50/60 hover:bg-blue-100 text-xs text-blue-700 truncate max-w-xs transition-colors"
                >
                  {p.slice(0, 46)}...
                </button>
              ))}
            </div>
          </div>
        )}

        {/* v15 脚本文案模板库（口播/剧情/科普） */}
        {scriptTemplates.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-blue-500" />
              脚本文案模板
              <span className="text-xs text-gray-400 font-normal">
                点击填充到视频描述，支持 {'{主题}'} 替换
              </span>
            </label>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="text"
                value={scriptTopic}
                onChange={(e) => setScriptTopic(e.target.value)}
                placeholder="主题词（替换模板中的 {主题}，如：智能音箱）"
                className="flex-1 min-w-0 px-3 py-1.5 rounded-lg border border-gray-200 text-xs focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <div className="flex gap-1 shrink-0">
                {['全部', '口播', '剧情', '科普'].map((c) => (
                  <button
                    key={c}
                    onClick={() => setScriptCategory(c)}
                    className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${
                      scriptCategory === c ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {scriptTemplates
                .filter((t) => scriptCategory === '全部' || t.category === scriptCategory)
                .map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      const topic = scriptTopic.trim()
                      const fill = (s) => (topic ? s.replaceAll('{主题}', topic) : s)
                      setPrompt([fill(t.title), ...t.structure.map(fill)].join('\n'))
                    }}
                    className="text-left p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 shrink-0">
                        {t.category}
                      </span>
                      <span className="text-xs font-medium text-gray-800 truncate">{t.name}</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1 truncate">{t.title}</div>
                    <div className="text-[11px] text-gray-400 mt-1 truncate">{t.desc}</div>
                  </button>
                ))}
            </div>
          </div>
        )}

        {/* 视频风格 + 镜头语言 + 运镜 + 情绪氛围 */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">视频风格</label>
            <select
              value={videoStyle}
              onChange={(e) => setVideoStyle(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-sm"
            >
              {VIDEO_STYLES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                  {s.desc ? ` (${s.desc})` : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">镜头语言</label>
            <select
              value={cameraAngle}
              onChange={(e) => setCameraAngle(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-sm"
            >
              {CAMERA_ANGLES.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">运镜方式</label>
            <select
              value={cameraMotion}
              onChange={(e) => setCameraMotion(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-sm"
            >
              {CAMERA_MOTIONS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">情绪氛围</label>
            <select
              value={mood}
              onChange={(e) => setMood(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-sm"
            >
              {MOODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">画面比例快捷切换</label>
          <div className="flex flex-wrap gap-2 mb-3">
            {ASPECTS.map((a) => (
              <button
                key={a.value}
                onClick={() => {
                  const [w, h] = a.value.split('x').map(Number)
                  setWidth(w)
                  setHeight(h)
                }}
                className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                  width === Number(a.value.split('x')[0]) && height === Number(a.value.split('x')[1])
                    ? 'border-blue-500 bg-blue-50 text-blue-700 font-medium'
                    : 'border-gray-200 hover:bg-gray-50 text-gray-600'
                }`}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">分辨率</label>
            <select
              value={`${width}x${height}`}
              onChange={(e) => {
                const [w, h] = e.target.value.split('x').map(Number)
                setWidth(w)
                setHeight(h)
              }}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            >
              {RESOLUTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label} ({r.value})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">时长（秒）</label>
            <input
              type="number"
              min="1"
              max="15"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">生成模式</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">帧率</label>
            <select
              value={frameRate}
              onChange={(e) => setFrameRate(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            >
              {FRAME_RATES.map((f) => (
                <option key={f} value={f}>
                  {f} fps
                </option>
              ))}
            </select>
          </div>
        </div>

        {mode === 'i2vid' && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-sm font-medium text-gray-700">参考图</label>
              <span className="text-[11px] text-gray-400">可上传本地图片或填 URL 直链</span>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) {
                    setImageFile(file)
                    setImagePreview(URL.createObjectURL(file))
                    setImage('') // 清空 URL 输入
                  }
                }}
              />
              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border text-sm transition-all flex-shrink-0 ${imageFile ? 'border-blue-400 bg-blue-50 text-blue-600' : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 text-gray-600'}`}
              >
                <Upload className="w-4 h-4" />
                {imageFile ? '已选本地图片' : '上传本地图片'}
              </button>
              <input
                type="text"
                value={image}
                onChange={(e) => {
                  setImage(e.target.value)
                  if (e.target.value) {
                    setImageFile(null)
                    setImagePreview('')
                  }
                }}
                placeholder="或粘贴图片 URL https://..."
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
            </div>
            {(imageFile && imagePreview) ? (
              <div className="mt-2 relative">
                <img
                  src={imagePreview}
                  alt="本地参考图预览"
                  className="max-h-40 rounded-lg border border-gray-200 object-contain bg-gray-50"
                />
                <button
                  onClick={() => {
                    setImageFile(null)
                    setImagePreview('')
                  }}
                  className="absolute top-2 right-2 p-1 rounded-lg bg-black/60 text-white hover:bg-red-500 transition-colors"
                  title="移除本地图片"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : image.trim() ? (
              <div className="mt-2">
                <img
                  src={image.trim()}
                  alt="参考图预览"
                  onError={() => setImageError(true)}
                  onLoad={() => setImageError(false)}
                  className="max-h-40 rounded-lg border border-gray-200 object-contain bg-gray-50"
                />
                {imageError && (
                  <p className="mt-1 text-xs text-red-500">
                    图片加载失败，请检查 URL 是否可访问（需 http/https 直链）
                  </p>
                )}
              </div>
            ) : null}
          </div>
        )}

            </div>
          )}
        </div>

        {genHistory.length > 0 && (
          <div className="mt-3">
            <HistoryPanel
              history={genHistory}
              onReuse={(item) => {
                setPrompt(item.content)
                toast.info('已恢复提示词，可重新生成')
              }}
              onRemove={removeGenHistory}
              onClear={clearGenHistory}
              title="生成历史"
            />
          </div>
        )}
        {lastResult && (
          <div
            className={`p-4 rounded-xl ${
              lastResult.status === 'completed'
                ? 'bg-green-50 border border-green-200'
                : lastResult.status === 'failed'
                  ? 'bg-red-50 border border-red-200'
                  : 'bg-blue-50 border border-blue-200'
            }`}
          >
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="font-medium text-gray-900 flex items-center gap-2">
                  <Badge
                    status={
                      lastResult.status === 'completed'
                        ? 'completed'
                        : lastResult.status === 'failed'
                          ? 'failed'
                          : 'processing'
                    }
                    dot
                  />
                  {lastResult.status === 'completed'
                    ? '视频生成完成'
                    : lastResult.status === 'failed'
                      ? '视频生成失败'
                      : '视频生成中...'}
                </div>
                <div className="text-sm text-gray-500 mt-1 truncate">ID: {lastResult.video_id}</div>
                {lastResult.created_at && (
                  <div className="text-xs text-gray-400 mt-1">
                    创建时间: {lastResult.created_at}
                  </div>
                )}
                {lastResult.status === 'failed' && lastResult.error && (
                  <div className="text-sm text-red-600 mt-1">
                    失败原因：{friendlyError(lastResult.error)}
                  </div>
                )}
                {lastResult.status !== 'completed' &&
                  lastResult.status !== 'failed' &&
                  lastResult.progress !== undefined && (
                    <div className="mt-2">
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span className="truncate">{lastResult.stage || '视频生成中...'}</span>
                        <span className="ml-2">{Math.round(lastResult.progress || 0)}%</span>
                      </div>
                      <div className="mt-1 h-1.5 bg-blue-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full transition-all"
                          style={{ width: `${lastResult.progress || 0}%` }}
                        />
                      </div>
                    </div>
                  )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {lastResult.status === 'completed' && lastResult.url && (
                  <Button
                    variant="success"
                    size="sm"
                    icon={Play}
                    onClick={() =>
                      handlePlay({ ...lastResult, filename: `${lastResult.video_id}.mp4` })
                    }
                  >
                    查看视频
                  </Button>
                )}
                {(lastResult.status === 'completed' || lastResult.status === 'failed') && (
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={RefreshCw}
                    loading={creating}
                    onClick={handleCreate}
                  >
                    换一版
                  </Button>
                )}
                {lastResult.status !== 'completed' && lastResult.status !== 'failed' && (
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={RefreshCw}
                    onClick={() =>
                      startPolling(lastResult.video_id, {
                        onUpdate: handleTaskUpdate,
                        onSuccess: handleTaskSuccess,
                        onError: handleTaskError,
                      })
                    }
                  >
                    刷新状态
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 视频后期工具 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1 flex items-center gap-2">
          <Wand2 className="w-5 h-5 text-blue-500" />
          视频后期工具
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          基于 ffmpeg 的本地后期处理：多段拼接、背景音乐混音、字幕烧录、批量转码，处理结果自动存入视频库
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button
            onClick={() => openPost('concat')}
            className="p-4 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-center"
          >
            <Scissors className="w-6 h-6 mx-auto text-blue-500 mb-2" />
            <div className="font-medium text-sm text-gray-900">多视频拼接</div>
            <div className="text-xs text-gray-500 mt-1">统一分辨率按顺序合并，自动补静音</div>
          </button>
          <button
            onClick={() => openPost('music')}
            className="p-4 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-center"
          >
            <Music className="w-6 h-6 mx-auto text-blue-500 mb-2" />
            <div className="font-medium text-sm text-gray-900">背景音乐混音</div>
            <div className="text-xs text-gray-500 mt-1">原声 + BGM 混合，可调背景音量</div>
          </button>
          <button
            onClick={() => openPost('subtitle')}
            className="p-4 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-center"
          >
            <Subtitles className="w-6 h-6 mx-auto text-blue-500 mb-2" />
            <div className="font-medium text-sm text-gray-900">字幕烧录</div>
            <div className="text-xs text-gray-500 mt-1">SRT 字幕文本直接烧进画面</div>
          </button>
          <button
            onClick={() => openPost('transcode')}
            className="p-4 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-center"
          >
            <Layers className="w-6 h-6 mx-auto text-blue-500 mb-2" />
            <div className="font-medium text-sm text-gray-900">批量转码</div>
            <div className="text-xs text-gray-500 mt-1">统一 H.264 格式，可选分辨率</div>
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
          <button
            onClick={() => openAiPost('auto-subtitle')}
            className="p-4 rounded-xl border border-purple-200 hover:border-purple-400 hover:bg-purple-50/50 transition-all text-center"
          >
            <ScanLine className="w-6 h-6 mx-auto text-purple-500 mb-2" />
            <div className="font-medium text-sm text-gray-900">自动字幕</div>
            <div className="text-xs text-gray-500 mt-1">AI 语音识别自动生成 SRT 字幕并烧录</div>
          </button>
          <button
            onClick={() => openAiPost('analyze')}
            className="p-4 rounded-xl border border-purple-200 hover:border-purple-400 hover:bg-purple-50/50 transition-all text-center"
          >
            <ScanSearch className="w-6 h-6 mx-auto text-purple-500 mb-2" />
            <div className="font-medium text-sm text-gray-900">智能分析</div>
            <div className="text-xs text-gray-500 mt-1">多帧提取 + AI 解读内容/情感/标签</div>
          </button>
          <button
            onClick={() => openAiPost('filter')}
            className="p-4 rounded-xl border border-purple-200 hover:border-purple-400 hover:bg-purple-50/50 transition-all text-center"
          >
            <Palette className="w-6 h-6 mx-auto text-purple-500 mb-2" />
            <div className="font-medium text-sm text-gray-900">视频滤镜</div>
            <div className="text-xs text-gray-500 mt-1">复古/黑白/暖冷等 6 种风格一键套用</div>
          </button>
        </div>
        <p className="text-xs text-purple-500 mt-3">
          ✨ AI 后期增强（v22）：自动字幕走 Whisper 转录 + LLM 兜底，分析提取 6 关键帧，滤镜基于 ffmpeg 色彩链
        </p>
      </div>

      {/* 视频库 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Film className="w-5 h-5 text-blue-500" />
          我的视频库 ({videos.length})
        </h2>
        {loading ? (
          <SkeletonGrid count={3} />
        ) : error ? (
          <ErrorState message={`加载失败：${error.message}`} onRetry={fetchVideos} />
        ) : videos.length === 0 ? (
          <Empty icon={Film} title="暂无视频" description="创建你的第一个视频任务" />
        ) : (
          <Pagination
            items={videos}
            pageSize={9}
            label={`共 ${videos.length} 个视频`}
            renderItem={(video) => (
              <div className="group relative">
                <div
                  className="aspect-video bg-gray-100 rounded-xl flex items-center justify-center cursor-pointer hover:bg-gray-200 transition-colors overflow-hidden"
                  onClick={() => handlePlay(video)}
                >
                  {video.cover_url ? (
                    <img
                      src={video.cover_url}
                      alt={video.title || video.filename}
                      className="w-full h-full object-cover transition-transform group-hover:scale-105 duration-300"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-gray-100 to-blue-50">
                      <Video className="w-8 h-8 text-gray-400 group-hover:text-blue-500 transition-colors" />
                      <span className="mt-1.5 text-[10px] text-gray-400">封面生成中…</span>
                    </div>
                  )}
                </div>
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 rounded-xl flex items-center justify-center gap-2 transition-all opacity-0 group-hover:opacity-100">
                  <button
                    onClick={() => handlePlay(video)}
                    className="p-2 bg-white rounded-full hover:bg-blue-50 transition-colors"
                    title="播放"
                  >
                    <Play className="w-4 h-4 text-blue-600" />
                  </button>
                  <button
                    onClick={() => handleDownload(video)}
                    className="p-2 bg-white rounded-full hover:bg-green-50 transition-colors"
                    title="下载"
                  >
                    <Download className="w-4 h-4 text-green-600" />
                  </button>
                  <button
                    onClick={() => {
                      setPackVideo(video)
                      setPackPlatform('douyin')
                      setPackTitle(video.title || '')
                      setPackDesc('')
                    }}
                    className="p-2 bg-white rounded-full hover:bg-cyan-50 transition-colors"
                    title="发布包（平台规格成片 + 封面 + 文案）"
                  >
                    <Package className="w-4 h-4 text-cyan-600" />
                  </button>
                  <span onClick={(e) => e.stopPropagation()}>
                    <ShareButton
                      content={`# 视频作品：${video.title || video.filename}\n\n- 文件：${video.filename}\n- 大小：${formatBytes(video.size)}\n\n> 由小团智能平台 AI 视频工坊生成 · ${new Date().toLocaleString()}`}
                      title={`视频作品：${video.title || video.filename}`}
                      contentType="video"
                      className="!p-2 !bg-white !rounded-full"
                    />
                  </span>
                  <span onClick={(e) => e.stopPropagation()}>
                    <FavoriteButton
                      favType="record"
                      targetId={video.filename}
                      label={video.title || video.filename}
                      className="!p-2 !bg-white !rounded-full"
                    />
                  </span>
                  <button
                    onClick={() => setDeleteTarget(video)}
                    className="p-2 bg-white rounded-full hover:bg-red-50 transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4 text-red-600" />
                  </button>
                </div>
                <div className="mt-2 text-xs text-gray-600 truncate">{video.title || video.filename}</div>
                <div className="text-xs text-gray-400">{formatBytes(video.size)}</div>
              </div>
            )}
          />
        )}
      </div>

      {/* 视频发布包 Modal：平台规格成片 + 封面 + 发布文案 + 质量报告 */}
      <Modal
        open={!!packVideo}
        onClose={() => setPackVideo(null)}
        title="视频发布包（平台规格成片）"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPackVideo(null)} disabled={packing}>
              取消
            </Button>
            <Button
              variant="primary"
              icon={Package}
              loading={packing}
              onClick={downloadPublishPack}
              className="bg-gradient-to-r from-blue-500 to-cyan-600 hover:from-blue-600 hover:to-cyan-700"
            >
              生成发布包
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
            将自动转码为平台规格成片（cover 模式居中裁剪不变形，有音轨自动保留），抽帧生成封面，
            并附发布文案（标题/描述/标签）、平台规格说明、上传指南、商用授权与质量自检报告。
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">目标平台</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {PUBLISH_PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPackPlatform(p.id)}
                  className={`flex flex-col items-start gap-0.5 px-3 py-2.5 rounded-xl border text-left transition-all ${
                    packPlatform === p.id
                      ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500/20'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-sm font-medium text-gray-800">{p.name}</span>
                  <span className="text-[11px] text-gray-400">{p.spec}</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">视频标题</label>
            <input
              type="text"
              value={packTitle}
              onChange={(e) => setPackTitle(e.target.value)}
              placeholder="如：夏日海岸的治愈瞬间"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">视频描述</label>
            <textarea
              value={packDesc}
              onChange={(e) => setPackDesc(e.target.value)}
              rows={3}
              placeholder="如：AI 生成的治愈系风光短片，适合短视频平台发布"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
          </div>
        </div>
      </Modal>

      {/* 使用指南 */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 rounded-xl p-4 border border-blue-100">
        <h3 className="font-medium text-blue-900 mb-3 flex items-center gap-2">
          <Clapperboard className="w-5 h-5" />
          使用指南
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">文生视频</div>
            <div className="text-sm text-gray-600 mt-1">输入文字描述，AI 自动生成视频</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">图生视频</div>
            <div className="text-sm text-gray-600 mt-1">上传参考图，让图片中的元素动起来</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">关键帧动画</div>
            <div className="text-sm text-gray-600 mt-1">设置多个关键帧，生成流畅过渡动画</div>
          </div>
        </div>
        <div className="mt-3 text-sm text-blue-700">
          当前 Agnes Video V2.0 免费使用，支持 480p/720p/1080p，最长 15 秒
        </div>
      </div>

      {/* 视频后期工具 Modal */}
      <Modal
        open={!!postMode}
        onClose={() => setPostMode(null)}
        title={
          postMode === 'concat'
            ? '多视频拼接'
            : postMode === 'music'
              ? '背景音乐混音'
              : postMode === 'subtitle'
                ? '字幕烧录'
                : '批量转码'
        }
        size="lg"
      >
        {postMode === 'concat' && (
          <div>
            <p className="text-sm text-gray-500 mb-3">
              按勾选顺序拼接（已选 {concatSel.length} 个，至少 2 个）
            </p>
            {videos.length < 2 ? (
              <Empty icon={Film} title="视频不足" description="请先生成至少两个视频" />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-64 overflow-y-auto mb-4">
                {videos.map((v) => (
                  <label
                    key={v.filename}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${
                      concatSel.includes(v.filename)
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={concatSel.includes(v.filename)}
                      onChange={() => toggleConcatSel(v.filename)}
                      className="accent-blue-600"
                    />
                    <span className="text-xs text-gray-700 truncate flex-1">{v.title || v.filename}</span>
                  </label>
                ))}
              </div>
            )}
            <Button
              variant="gradient"
              icon={Scissors}
              loading={postBusy}
              disabled={concatSel.length < 2}
              onClick={handlePostConcat}
              className="w-full"
            >
              开始拼接
            </Button>
          </div>
        )}

        {postMode === 'music' && (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">目标视频</label>
              <select
                value={postVideo}
                onChange={(e) => setPostVideo(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              >
                <option value="">请选择视频</option>
                {videos.map((v) => (
                  <option key={v.filename} value={v.filename}>
                    {v.title || v.filename}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">BGM 地址</label>
              <input
                type="text"
                value={bgmUrl}
                onChange={(e) => setBgmUrl(e.target.value)}
                placeholder="https://… 音乐 URL（也可填服务器本地路径）"
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <p className="text-xs text-gray-400 mt-1">
                提示：可用音乐工厂生成的音乐地址（在音乐列表复制 URL）
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">
                背景音量: {Math.round(bgVolume * 100)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={bgVolume}
                onChange={(e) => setBgVolume(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>
            <Button
              variant="gradient"
              icon={Music}
              loading={postBusy}
              disabled={!postVideo || !bgmUrl.trim()}
              onClick={handlePostMusic}
              className="w-full"
            >
              开始配乐
            </Button>
          </div>
        )}

        {postMode === 'subtitle' && (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">目标视频</label>
              <select
                value={postVideo}
                onChange={(e) => setPostVideo(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              >
                <option value="">请选择视频</option>
                {videos.map((v) => (
                  <option key={v.filename} value={v.filename}>
                    {v.title || v.filename}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">SRT 字幕内容</label>
              <textarea
                rows={8}
                value={srtContent}
                onChange={(e) => setSrtContent(e.target.value)}
                placeholder={`1\n00:00:00,000 --> 00:00:03,000\n第一句字幕\n\n2\n00:00:03,000 --> 00:00:06,000\n第二句字幕`}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none font-mono text-xs"
              />
            </div>
            <Button
              variant="gradient"
              icon={Subtitles}
              loading={postBusy}
              disabled={!postVideo || !srtContent.trim()}
              onClick={handlePostSubtitle}
              className="w-full"
            >
              开始烧录
            </Button>
          </div>
        )}

        {postMode === 'transcode' && (
          <div className="space-y-4">
            <p className="text-sm text-gray-500">
              批量转码为 H.264 平台兼容格式（已选 {concatSel.length} 个，最多 10 个）
            </p>
            {videos.length === 0 ? (
              <Empty icon={Film} title="视频不足" description="请先生成视频" />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-52 overflow-y-auto">
                {videos.map((v) => (
                  <label
                    key={v.filename}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${
                      concatSel.includes(v.filename)
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={concatSel.includes(v.filename)}
                      onChange={() => toggleConcatSel(v.filename)}
                      className="accent-blue-600"
                    />
                    <span className="text-xs text-gray-700 truncate flex-1">{v.title || v.filename}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">输出宽度</label>
                <input
                  type="number"
                  min="16"
                  max="7680"
                  value={transcodeWidth}
                  onChange={(e) => setTranscodeWidth(e.target.value)}
                  placeholder="原尺寸"
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">输出高度</label>
                <input
                  type="number"
                  min="16"
                  max="7680"
                  value={transcodeHeight}
                  onChange={(e) => setTranscodeHeight(e.target.value)}
                  placeholder="原尺寸"
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">CRF 画质</label>
                <input
                  type="number"
                  min="18"
                  max="35"
                  value={transcodeCrf}
                  onChange={(e) => setTranscodeCrf(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-sm"
                />
              </div>
            </div>
            <p className="text-xs text-gray-400">
              宽高需成对填写（留空保持原分辨率）；CRF 18~35，数值越小画质越高、文件越大
            </p>
            <Button
              variant="gradient"
              icon={Layers}
              loading={postBusy}
              disabled={concatSel.length === 0}
              onClick={handlePostTranscode}
              className="w-full"
            >
              开始批量转码
            </Button>
          </div>
        )}

        {/* 批量转码逐项结果 */}
        {postResult?.mode === 'transcode' && (
          <div className="mt-4 p-4 rounded-xl bg-green-50 border border-green-200">
            <div className="font-medium text-gray-900 mb-2">
              转码完成：成功 {postResult.ok} 个{postResult.failed ? ` / 失败 ${postResult.failed} 个` : ''}
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {postResult.results.map((r) =>
                r.status === 'ok' ? (
                  <div key={r.filename} className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-gray-600 truncate">
                      {r.source} → {r.filename}
                      {r.width ? `（${r.width}×${r.height}）` : ''}
                    </span>
                    <Button
                      variant="success"
                      size="sm"
                      icon={Play}
                      onClick={() => handlePlay({ url: absUrl(r.url), filename: r.filename })}
                    >
                      预览
                    </Button>
                  </div>
                ) : (
                  <div key={r.source} className="text-xs text-red-500 truncate" title={r.error}>
                    {r.source}：{r.error}
                  </div>
                )
              )}
            </div>
          </div>
        )}

        {postResult && postResult.mode !== 'transcode' && (
          <div className="mt-4 p-4 rounded-xl bg-green-50 border border-green-200 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="font-medium text-gray-900">处理完成</div>
              <div className="text-xs text-gray-500 truncate mt-0.5">{postResult.filename}</div>
            </div>
            <Button
              variant="success"
              size="sm"
              icon={Play}
              onClick={() => handlePlay({ url: absUrl(postResult.url), filename: postResult.filename })}
            >
              预览
            </Button>
          </div>
        )}
      </Modal>

      {/* v22 AI 后期增强 Modal：自动字幕 / 智能分析 / 视频滤镜 */}
      <Modal
        open={!!aiPostMode}
        onClose={() => setAiPostMode(null)}
        title={
          aiPostMode === 'auto-subtitle'
            ? '自动字幕生成'
            : aiPostMode === 'analyze'
              ? '视频智能分析'
              : '视频滤镜'
        }
        size="lg"
      >
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">目标视频</label>
            <select
              value={aiPostVideo}
              onChange={(e) => setAiPostVideo(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
            >
              <option value="">请选择视频</option>
              {videos.map((v) => (
                <option key={v.filename} value={v.filename}>
                  {v.title || v.filename}
                </option>
              ))}
            </select>
          </div>

          {aiPostMode === 'auto-subtitle' && (
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">字幕语言</label>
              <select
                value={subtitleLang}
                onChange={(e) => setSubtitleLang(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 outline-none"
              >
                <option value="zh">中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="ko">한국어</option>
              </select>
              <p className="text-xs text-gray-400 mt-2">
                Whisper 语音识别生成字幕并烧录进画面；识别不可用时自动切换 LLM 生成结构化字幕
              </p>
            </div>
          )}

          {aiPostMode === 'filter' && (
            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">滤镜风格</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'sepia', label: '怀旧棕褐' },
                  { id: 'black_white', label: '经典黑白' },
                  { id: 'vintage', label: '复古胶片' },
                  { id: 'warm', label: '暖阳' },
                  { id: 'cool', label: '冷冽' },
                  { id: 'fade', label: '淡入淡出' },
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFilterType(f.id)}
                    className={`p-2.5 rounded-lg border text-sm transition-all ${
                      filterType === f.id
                        ? 'border-purple-500 bg-purple-50 text-purple-700 font-medium'
                        : 'border-gray-200 hover:border-purple-300 text-gray-600'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <Button
            variant="gradient"
            icon={aiPostMode === 'analyze' ? ScanSearch : aiPostMode === 'filter' ? Palette : ScanLine}
            loading={aiPostBusy}
            disabled={!aiPostVideo}
            onClick={
              aiPostMode === 'auto-subtitle'
                ? handleAiAutoSubtitle
                : aiPostMode === 'analyze'
                  ? handleAiAnalyze
                  : handleAiFilter
            }
            className="w-full"
          >
            {aiPostMode === 'analyze' ? '开始分析' : '开始处理'}
          </Button>

          {aiPostResult && (
            <div className="mt-2 p-3 rounded-xl bg-purple-50 border border-purple-100">
              {aiPostResult.mode === 'analyze' ? (
                <div className="text-sm space-y-2">
                  <p className="font-medium text-purple-700">
                    分析完成：{aiPostResult.analysis?.summary || '（摘要生成中）'}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {(aiPostResult.analysis?.keywords || []).slice(0, 6).map((kw, i) => (
                      <Badge key={i} variant="purple">{kw}</Badge>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500">
                    情感：{aiPostResult.analysis?.sentiment || 'neutral'} ｜ 规格：
                    {aiPostResult.spec?.width}×{aiPostResult.spec?.height} ｜ 时长{' '}
                    {aiPostResult.spec?.duration_sec}s
                  </p>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-purple-700">
                      {aiPostResult.mode === 'auto-subtitle' ? '字幕视频已生成' : '滤镜视频已生成'}
                    </p>
                    <p className="text-xs text-gray-500">
                      {aiPostResult.subtitle_source === 'whisper' ? 'Whisper 转录' : ''}
                      {aiPostResult.frames ? `｜ ${aiPostResult.frames} 帧动画` : ''}
                    </p>
                  </div>
                  {aiPostResult.url && (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={Play}
                      onClick={() => window.open(absUrl(aiPostResult.url), '_blank')}
                    >
                      预览
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      {/* v21 视频模板渲染 Modal：预览 + 变量编辑 + 购买授权 + 一键成片 */}
      <Modal
        open={!!vtplModal}
        onClose={() => setVtplModal(null)}
        title={vtplModal ? `视频模板 · ${vtplModal.name}` : ''}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setVtplModal(null)} disabled={vtplBusy}>
              取消
            </Button>
            {vtplModal?.pricing?.mode !== 'free' && (
              <div className="flex items-center gap-1.5">
                {['once', 'day', 'month'].map((a) => (
                  <button
                    key={a}
                    onClick={() => setVtplAccess(a)}
                    className={`px-2.5 py-1.5 rounded-lg text-xs border transition-colors ${
                      vtplAccess === a
                        ? 'border-amber-500 bg-amber-50 text-amber-700'
                        : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    {a === 'once'
                      ? `按次 ${vtplModal?.pricing?.once || 0}`
                      : a === 'day'
                        ? `按天 ${vtplModal?.pricing?.day || 0}`
                        : `按月 ${vtplModal?.pricing?.month || 0}`}
                    积分
                  </button>
                ))}
                <Button
                  variant="primary"
                  size="sm"
                  icon={Package}
                  disabled={vtplBusy}
                  onClick={() => handleVtplPurchase(vtplAccess)}
                  className="bg-amber-500 hover:bg-amber-600"
                >
                  购买授权
                </Button>
              </div>
            )}
            <Button
              variant="primary"
              icon={Clapperboard}
              loading={vtplBusy}
              onClick={handleVtplRender}
              className="bg-gradient-to-r from-blue-500 to-cyan-600 hover:from-blue-600 hover:to-cyan-700"
            >
              渲染视频
            </Button>
          </>
        }
      >
        {vtplModal && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* 左侧：首帧预览 + 模板信息 */}
            <div className="space-y-3">
              <div className="rounded-xl overflow-hidden border border-gray-200 bg-gray-900 flex items-center justify-center">
                <img src={absUrl(vtplModal.preview)} alt={vtplModal.name} className="max-h-[46vh] object-contain" />
              </div>
              <div className="rounded-xl bg-gray-50 border border-gray-100 px-3 py-2.5 text-xs space-y-1">
                <div className="text-gray-700">{vtplModal.desc}</div>
                <div className="text-gray-400">
                  规格：{vtplModal.width}×{vtplModal.height} · {vtplModal.fps}fps · 成片约 {vtplModal.duration}s
                  {vtplModal.pricing?.mode !== 'free'
                    ? ` · ${vtplModal.pricing_label}（按次 ${vtplModal.pricing.once} / 按天 ${vtplModal.pricing.day} / 按月 ${vtplModal.pricing.month} 积分）`
                    : ' · 免费'}
                </div>
              </div>
              {/* 渲染结果播放器 */}
              {vtplResult && (
                <div className="rounded-xl overflow-hidden border border-green-200 bg-black">
                  <video src={vtplResult.url} poster={vtplResult.cover} controls autoPlay playsInline className="w-full max-h-[42vh]" />
                </div>
              )}
            </div>
            {/* 右侧：变量编辑（文本替换 + 产品图槽） */}
            <div className="space-y-3">
              <div className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-blue-500" />
                内容变量
                <span className="text-xs text-gray-400 font-normal">修改后点击「渲染视频」生成专属成片</span>
              </div>
              {vtplVars.length === 0 && (
                <div className="text-xs text-gray-400 py-8 text-center">模板变量加载中…</div>
              )}
              <div className="space-y-2.5 max-h-[44vh] overflow-y-auto pr-1">
                {vtplVars.map((v, vi) =>
                  v.type === 'image' ? (
                    <div key={vi}>
                      <label className="block text-xs font-medium text-gray-500 mb-1">
                        产品图 URL（{v.key}）
                        <span className="text-gray-400 font-normal"> 留空则跳过该图层</span>
                      </label>
                      <input
                        type="text"
                        value={vtplImages[v.key] || ''}
                        onChange={(e) => setVtplImages((p) => ({ ...p, [v.key]: e.target.value }))}
                        placeholder="https://… 产品或场景图（建议 1:1 以上）"
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                      />
                    </div>
                  ) : (
                    <div key={vi}>
                      <label className="block text-xs font-medium text-gray-500 mb-1">{v.key}</label>
                      <input
                        type="text"
                        value={vtplOverrides[v.key] || ''}
                        onChange={(e) => setVtplOverrides((p) => ({ ...p, [v.key]: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                      />
                    </div>
                  ),
                )}
              </div>
              {vtplResult && (
                <div className="rounded-xl bg-green-50 border border-green-200 px-3 py-2.5 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-gray-800">成片已生成 · {vtplResult.duration}s</div>
                    <div className="text-[11px] text-gray-500 truncate mt-0.5">{vtplResult.filename}</div>
                  </div>
                  <a
                    href={vtplResult.url}
                    download={vtplResult.filename}
                    className="shrink-0 inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-green-500 hover:bg-green-600 text-white transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    下载 MP4
                  </a>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* 视频播放器 Modal */}
      <Modal
        open={!!selectedVideo}
        onClose={() => setSelectedVideo(null)}
        title="视频预览"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setSelectedVideo(null)}>
              关闭
            </Button>
            <Button variant="success" icon={Download} onClick={() => handleDownload(selectedVideo)}>
              下载视频
            </Button>
            <Button variant="danger" icon={Trash2} onClick={() => setDeleteTarget(selectedVideo)}>
              删除
            </Button>
          </>
        }
      >
        {selectedVideo && (
          <div className="space-y-3">
            {/* v18-C：影院容器 + 元信息面板（标题/格式/大小），成片展示专业感 */}
            <div className="bg-black rounded-xl overflow-hidden flex items-center justify-center">
              <video
                ref={videoRef}
                src={selectedVideo.url}
                className="max-w-full max-h-[52vh] w-auto"
                controls
                autoPlay
                playsInline
              />
            </div>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">
                  {selectedVideo.title || selectedVideo.filename}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {selectedVideo.filename} · {formatBytes(selectedVideo.size)}
                </div>
              </div>
              {selectedVideo.prompt && (
                <div className="text-xs text-gray-500 bg-gray-50 border border-gray-100 rounded-lg px-2.5 py-1.5 max-w-[55%] line-clamp-2 flex-shrink-0">
                  生成提示词：{selectedVideo.prompt}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* 删除确认 */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除视频"
        message={`确定要删除「${deleteTarget?.filename}」吗？此操作不可撤销。`}
        confirmLabel="确认删除"
      />
    </div>
  )
}
