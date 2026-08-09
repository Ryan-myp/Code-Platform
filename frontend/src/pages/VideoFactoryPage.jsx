import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Video,
  Film,
  Clapperboard,
  Play,
  Download,
  Sparkles,
  RefreshCw,
  Wand2,
  Trash2,
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
} from '../components/ui'
import ShareButton from '../components/ShareButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

const MEDIA_BASE = api.defaults.baseURL
const absUrl = (u) => (u ? (u.startsWith('http') ? u : `${MEDIA_BASE}${u}`) : '')

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
  const [creating, setCreating] = useState(false)
  const [lastResult, setLastResult] = useState(null)
  const { submitTask, startPolling, stopPolling } = useAsyncTask()

  // 播放器
  const [selectedVideo, setSelectedVideo] = useState(null)
  const videoRef = useRef(null)

  // 删除
  const [deleteTarget, setDeleteTarget] = useState(null)

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
      setVideos(res.data.videos || [])
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
    return () => {
      stopPolling()
    }
  }, [fetchStats, fetchVideos, stopPolling])

  const fetchCloudPrompts = async () => {
    try {
      const res = await api.get('/api/video-factory/prompts')
      setCloudPrompts(res.data?.prompts || [])
    } catch {
      /* 静默：后端无此接口时降级为本地模板 */
    }
  }

  // 异步任务进度回调（提交与手动刷新共用）
  const handleTaskUpdate = (t) => {
    setLastResult((prev) => ({ ...prev, progress: t.progress, stage: t.stage }))
  }
  const handleTaskSuccess = (data) => {
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

  const handleCreate = async () => {
    if (!prompt.trim()) {
      toast.error('请输入视频描述')
      return
    }
    setCreating(true)
    setLastResult(null)
    const form = new FormData()
    // 风格/镜头/运镜/情绪作为结构化控制项，拼入 prompt 参与生成（避免死控件）
    const parts = [prompt]
    if (videoStyle) parts.push(VIDEO_STYLES.find((s) => s.value === videoStyle)?.label)
    if (cameraAngle) parts.push(cameraAngle)
    if (cameraMotion) parts.push(CAMERA_MOTIONS.find((m) => m.value === cameraMotion)?.kw)
    if (mood) parts.push(MOODS.find((m) => m.value === mood)?.kw)
    form.append('prompt', parts.filter(Boolean).join(', '))
    form.append('width', width)
    form.append('height', height)
    form.append('duration', duration)
    form.append('mode', mode)
    if (mode === 'i2vid') form.append('image', image)
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
      a.download = video.filename
      a.click()
      URL.revokeObjectURL(url)
      toast.success('已开始下载')
    } catch (e) {
      toast.error(`下载失败：${e.message}`)
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
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="描述你想要的视频内容，例如：A beautiful sunset over the ocean, waves gently crashing on the shore..."
            rows={3}
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
          />
        </div>

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
                （来自 /api/video-factory/prompts）
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
            <label className="block text-sm font-medium text-gray-700 mb-1">参考图片 URL</label>
            <input
              type="text"
              value={image}
              onChange={(e) => setImage(e.target.value)}
              placeholder="https://example.com/image.jpg"
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
          </div>
        )}

        <Button
          variant="gradient"
          size="lg"
          icon={Sparkles}
          loading={creating}
          disabled={!prompt.trim()}
          onClick={handleCreate}
          className="w-full"
        >
          {creating ? '创建任务中...' : '创建视频任务'}
        </Button>

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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {videos.map((video) => (
              <div key={video.filename} className="group relative">
                <div
                  className="aspect-video bg-gray-100 rounded-xl flex items-center justify-center cursor-pointer hover:bg-gray-200 transition-colors"
                  onClick={() => handlePlay(video)}
                >
                  <Video className="w-8 h-8 text-gray-400 group-hover:text-blue-500 transition-colors" />
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
                  <span onClick={(e) => e.stopPropagation()}>
                    <ShareButton
                      content={`# 视频作品：${video.filename}\n\n- 文件：${video.filename}\n- 大小：${formatBytes(video.size)}\n\n> 由小团智能平台 AI 视频工坊生成 · ${new Date().toLocaleString()}`}
                      title={`视频作品：${video.filename}`}
                      contentType="video"
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
                <div className="mt-2 text-xs text-gray-600 truncate">{video.filename}</div>
                <div className="text-xs text-gray-400">{formatBytes(video.size)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

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
          <>
            <video
              ref={videoRef}
              src={selectedVideo.url}
              className="w-full rounded-lg"
              controls
              autoPlay
            />
            <div className="mt-3 text-sm text-gray-500">{selectedVideo.filename}</div>
          </>
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
