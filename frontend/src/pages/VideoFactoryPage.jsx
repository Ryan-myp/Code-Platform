import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Video, Film, Clapperboard, Play, Download, Sparkles,
  RefreshCw, Wand2, Trash2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatBytes } from '../lib/format'
import {
  Modal, Button, Empty, SkeletonGrid, ErrorState,
  Badge, PageHeader, ConfirmDialog,
} from '../components/ui'

const MEDIA_BASE = api.defaults.baseURL
const absUrl = (u) => (u ? (u.startsWith('http') ? u : `${MEDIA_BASE}${u}`) : '')

const PRESETS = [
  'A beautiful sunset over the ocean with gentle waves, cinematic quality',
  'A cute cat walking on the beach at sunset, warm golden light',
  'Time-lapse of a flower blooming in fast motion, macro photography',
  'Aerial view of a misty mountain range at sunrise, drone footage',
  'Slow motion water droplets falling into a pond, high speed photography',
  'A cozy coffee shop on a rainy day, warm lighting, cinematic',
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

  // 生成
  const [prompt, setPrompt] = useState('')
  const [width, setWidth] = useState(1152)
  const [height, setHeight] = useState(768)
  const [duration, setDuration] = useState(5)
  const [mode, setMode] = useState('ti2vid')
  const [image, setImage] = useState('')
  const [frameRate, setFrameRate] = useState(24)
  const [creating, setCreating] = useState(false)
  const [lastResult, setLastResult] = useState(null)
  const pollingRef = useRef(null)

  // 播放器
  const [selectedVideo, setSelectedVideo] = useState(null)
  const videoRef = useRef(null)

  // 删除
  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/api/video-factory/stats')
      setStats(res.data)
    } catch { /* 静默 */ }
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
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [fetchStats, fetchVideos])

  const startPolling = (videoId) => {
    if (pollingRef.current) clearInterval(pollingRef.current)
    const poll = async () => {
      try {
        const res = await api.get(`/api/video-factory/result/${videoId}`)
        const data = res.data
        setLastResult((prev) => ({
          ...prev,
          ...data,
          url: data.url ? absUrl(data.url) : prev?.url,
        }))
        if (data.status === 'completed') {
          if (pollingRef.current) clearInterval(pollingRef.current)
          toast.success('视频生成完成！')
          fetchVideos()
        }
      } catch (e) {
        if (pollingRef.current) clearInterval(pollingRef.current)
        setLastResult((prev) => ({ ...prev, status: 'failed', error: e.message }))
        toast.error(`视频生成失败：${e.message}`)
      }
    }
    poll()
    pollingRef.current = setInterval(poll, 5000)
  }

  const handleCreate = async () => {
    if (!prompt.trim()) {
      toast.error('请输入视频描述')
      return
    }
    setCreating(true)
    setLastResult(null)
    try {
      const form = new FormData()
      form.append('prompt', prompt)
      form.append('width', width)
      form.append('height', height)
      form.append('duration', duration)
      form.append('mode', mode)
      if (mode === 'i2vid') form.append('image', image)
      form.append('frame_rate', frameRate)
      const res = await api.post('/api/video-factory/generate', form, { timeout: 120000 })
      const data = res.data
      if (data.video_id) {
        setLastResult({
          video_id: data.video_id,
          status: 'pending',
          prompt: prompt,
          created_at: new Date().toLocaleString(),
        })
        toast.success('视频任务已创建，正在生成...')
        startPolling(data.video_id)
      }
    } catch (e) {
      toast.error(`创建任务失败：${e.message}`)
    } finally {
      setCreating(false)
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
    { label: 'API 状态', value: stats.api_configured ? '已配置' : '未配置', color: stats.api_configured ? 'text-green-600' : 'text-red-600' },
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
          <Button variant="secondary" icon={RefreshCw} onClick={() => { fetchStats(); fetchVideos() }}>
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
            onClick={() => setPrompt(PRESETS[Math.floor(Math.random() * PRESETS.length)])}
            className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <Wand2 className="w-4 h-4" />
            随机提示词
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">视频描述 <span className="text-red-500">*</span></label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="描述你想要的视频内容，例如：A beautiful sunset over the ocean, waves gently crashing on the shore..."
            rows={3}
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
          />
          {PRESETS.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2 items-center">
              <span className="text-xs text-gray-500">快捷预设:</span>
              {PRESETS.slice(0, 3).map((p, i) => (
                <button
                  key={i}
                  onClick={() => setPrompt(p)}
                  className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-600 truncate max-w-xs transition-colors"
                >
                  {p.slice(0, 30)}...
                </button>
              ))}
            </div>
          )}
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
              {RESOLUTIONS.map((r) => <option key={r.value} value={r.value}>{r.label} ({r.value})</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">时长（秒）</label>
            <input
              type="number" min="1" max="15" value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">生成模式</label>
            <select
              value={mode} onChange={(e) => setMode(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            >
              {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">帧率</label>
            <select
              value={frameRate} onChange={(e) => setFrameRate(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            >
              {FRAME_RATES.map((f) => <option key={f} value={f}>{f} fps</option>)}
            </select>
          </div>
        </div>

        {mode === 'i2vid' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">参考图片 URL</label>
            <input
              type="text" value={image} onChange={(e) => setImage(e.target.value)}
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
          <div className={`p-4 rounded-xl ${
            lastResult.status === 'completed' ? 'bg-green-50 border border-green-200' :
            lastResult.status === 'failed' ? 'bg-red-50 border border-red-200' :
            'bg-blue-50 border border-blue-200'
          }`}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="font-medium text-gray-900 flex items-center gap-2">
                  <Badge status={lastResult.status === 'completed' ? 'completed' : lastResult.status === 'failed' ? 'failed' : 'processing'} dot />
                  {lastResult.status === 'completed' ? '视频生成完成' :
                   lastResult.status === 'failed' ? '视频生成失败' : '视频生成中...'}
                </div>
                <div className="text-sm text-gray-500 mt-1 truncate">ID: {lastResult.video_id}</div>
                {lastResult.created_at && (
                  <div className="text-xs text-gray-400 mt-1">创建时间: {lastResult.created_at}</div>
                )}
                {lastResult.status === 'failed' && lastResult.error && (
                  <div className="text-sm text-red-600 mt-1">失败原因：{lastResult.error}</div>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {lastResult.status === 'completed' && lastResult.url && (
                  <Button variant="success" size="sm" icon={Play} onClick={() => handlePlay({ ...lastResult, filename: `${lastResult.video_id}.mp4` })}>
                    查看视频
                  </Button>
                )}
                {lastResult.status !== 'completed' && lastResult.status !== 'failed' && (
                  <Button variant="secondary" size="sm" icon={RefreshCw} onClick={() => startPolling(lastResult.video_id)}>
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
                  <button onClick={() => handlePlay(video)} className="p-2 bg-white rounded-full hover:bg-blue-50 transition-colors" title="播放">
                    <Play className="w-4 h-4 text-blue-600" />
                  </button>
                  <button onClick={() => handleDownload(video)} className="p-2 bg-white rounded-full hover:bg-green-50 transition-colors" title="下载">
                    <Download className="w-4 h-4 text-green-600" />
                  </button>
                  <button onClick={() => setDeleteTarget(video)} className="p-2 bg-white rounded-full hover:bg-red-50 transition-colors" title="删除">
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
            <Button variant="secondary" onClick={() => setSelectedVideo(null)}>关闭</Button>
            <Button variant="success" icon={Download} onClick={() => handleDownload(selectedVideo)}>下载视频</Button>
            <Button variant="danger" icon={Trash2} onClick={() => setDeleteTarget(selectedVideo)}>删除</Button>
          </>
        }
      >
        {selectedVideo && (
          <>
            <video ref={videoRef} src={selectedVideo.url} className="w-full rounded-lg" controls autoPlay />
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
