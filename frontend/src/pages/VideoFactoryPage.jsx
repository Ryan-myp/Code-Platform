import React, { useState, useEffect } from 'react'
import { 
  Video, Film, Play, Pause, Download, Loader, Sparkles,
  Clock, Maximize2, Trash2, RefreshCw, Image as ImageIcon,
  Camera
} from 'lucide-react'

const API_BASE = 'http://localhost:8888'

export default function VideoFactoryPage() {
  const [stats, setStats] = useState({ total_videos: 0, api_configured: false })
  const [videos, setVideos] = useState([])
  const [pendingTasks, setPendingTasks] = useState([])
  
  // 生成状态
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState('agnes-video-v2.0')
  const [width, setWidth] = useState(1152)
  const [height, setHeight] = useState(768)
  const [duration, setDuration] = useState(5)
  const [mode, setMode] = useState('ti2vid') // ti2vid, i2vid, keyframes
  const [image, setImage] = useState('')
  const [frameRate, setFrameRate] = useState(24)
  const [isGenerating, setIsGenerating] = useState(false)
  const [lastResult, setLastResult] = useState(null)

  // 分辨率选项
  const resolutions = [
    { label: '480p', w: 854, h: 480 },
    { label: '720p', w: 1280, h: 720 },
    { label: '1080p', w: 1920, h: 1080 },
  ]

  useEffect(() => {
    loadStats()
    loadVideos()
    loadPendingTasks()
  }, [])

  const loadStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/video-factory/stats`)
      const data = await res.json()
      setStats(data)
    } catch (e) {
      console.error('加载统计失败:', e)
    }
  }

  const loadVideos = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/video-factory/list`)
      const data = await res.json()
      setVideos(data.videos || [])
    } catch (e) {
      console.error('加载视频列表失败:', e)
    }
  }

  const loadPendingTasks = async () => {
    // 这里可以轮询待处理任务
  }

  const createVideoTask = async () => {
    if (!prompt) {
      alert('请输入视频描述')
      return
    }
    setIsGenerating(true)
    try {
      const formData = new FormData()
      formData.append('prompt', prompt)
      formData.append('model', model)
      formData.append('width', width)
      formData.append('height', height)
      formData.append('duration', duration)
      formData.append('mode', mode)
      if (mode === 'i2vid') formData.append('image', image)
      formData.append('frame_rate', frameRate)

      const res = await fetch(`${API_BASE}/api/video-factory/generate`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      setLastResult(data)
      if (data.video_id) {
        setTimeout(() => checkVideoStatus(data.video_id), 5000)
      }
    } catch (e) {
      console.error('创建视频任务失败:', e)
    } finally {
      setIsGenerating(false)
    }
  }

  const checkVideoStatus = async (videoId) => {
    try {
      const res = await fetch(`${API_BASE}/api/video-factory/result/${videoId}`)
      const data = await res.json()
      
      if (data.status === 'completed') {
        setLastResult({ ...data, status: 'completed' })
        loadVideos()
        alert('视频生成完成！')
      } else if (data.status === 'failed') {
        alert('视频生成失败: ' + (data.error || '未知错误'))
      } else {
        // 继续轮询
        setTimeout(() => checkVideoStatus(videoId), 5000)
      }
    } catch (e) {
      console.error('检查状态失败:', e)
    }
  }

  const deleteVideo = async (filename) => {
    if (!confirm('确定删除该视频？')) return
    await fetch(`${API_BASE}/api/video-factory/delete/${filename}`, { method: 'DELETE' })
    loadVideos()
  }

  return (
    <div className="p-6 space-y-6">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
          <Video className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">视频工厂</h1>
          <p className="text-gray-500">文生视频、图生视频、关键帧动画</p>
        </div>
      </div>

      {/* 统计 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-2xl font-bold text-blue-600">{stats.total_videos}</div>
          <div className="text-sm text-gray-500">视频总数</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className={`text-2xl font-bold ${stats.api_configured ? 'text-green-600' : 'text-red-600'}`}>
            {stats.api_configured ? '已配置' : '未配置'}
          </div>
          <div className="text-sm text-gray-500">API状态</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-2xl font-bold text-purple-600">免费</div>
          <div className="text-sm text-gray-500">当前价格</div>
        </div>
      </div>

      {/* 生成表单 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-blue-500" />
          创建视频任务
        </h2>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">视频描述</label>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="描述你想要的视频内容，例如：A beautiful sunset over the ocean, waves gently crashing on the shore..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
          />
        </div>

        <div className="grid grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">分辨率</label>
            <select
              value={`${width}x${height}`}
              onChange={e => {
                const [w, h] = e.target.value.split('x').map(Number)
                setWidth(w)
                setHeight(h)
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="854x480">480p (854x480)</option>
              <option value="1280x720">720p (1280x720)</option>
              <option value="1920x1080">1080p (1920x1080)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">时长（秒）</label>
            <input
              type="number"
              min="1"
              max="15"
              value={duration}
              onChange={e => setDuration(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">生成模式</label>
            <select
              value={mode}
              onChange={e => setMode(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="ti2vid">文生视频</option>
              <option value="i2vid">图生视频</option>
              <option value="keyframes">关键帧动画</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">帧率</label>
            <select
              value={frameRate}
              onChange={e => setFrameRate(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="24">24 fps</option>
              <option value="30">30 fps</option>
              <option value="60">60 fps</option>
            </select>
          </div>
        </div>

        {mode === 'i2vid' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">参考图片 URL</label>
            <input
              type="text"
              value={image}
              onChange={e => setImage(e.target.value)}
              placeholder="https://example.com/image.jpg"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
        )}

        <button
          onClick={createVideoTask}
          disabled={isGenerating}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {isGenerating ? <Loader className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
          {isGenerating ? '创建任务中...' : '创建视频任务'}
        </button>

        {lastResult && (
          <div className={`p-4 rounded-lg ${
            lastResult.status === 'completed' ? 'bg-green-50' : 'bg-blue-50'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-gray-900">
                  {lastResult.status === 'completed' ? '✅ 视频生成完成' : '⏳ 视频生成中...'}
                </div>
                <div className="text-sm text-gray-500">
                  ID: {lastResult.video_id}
                </div>
              </div>
              {lastResult.status === 'completed' && lastResult.url && (
                <a
                  href={`${API_BASE}${lastResult.url}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  <Play className="w-4 h-4" />
                  查看视频
                </a>
              )}
              {lastResult.status !== 'completed' && (
                <button
                  onClick={() => checkVideoStatus(lastResult.video_id)}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  <RefreshCw className="w-4 h-4" />
                  刷新状态
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 视频库 */}
      {videos.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Film className="w-5 h-5 text-blue-500" />
            我的视频库 ({videos.length})
          </h2>
          <div className="grid grid-cols-4 gap-4">
            {videos.map(video => (
              <div key={video.filename} className="relative group">
                <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center">
                  <Video className="w-8 h-8 text-gray-400" />
                </div>
                <div className="absolute inset-0 bg-black bg-opacity-50 opacity-0 group-hover:opacity-100 rounded-lg flex items-center justify-center gap-2 transition-opacity">
                  <a href={`${API_BASE}${video.url}`} target="_blank" rel="noreferrer">
                    <Play className="w-5 h-5 text-white" />
                  </a>
                  <a href={`${API_BASE}${video.url}`} download>
                    <Download className="w-5 h-5 text-white" />
                  </a>
                  <button onClick={() => deleteVideo(video.filename)}>
                    <Trash2 className="w-5 h-5 text-red-400 hover:text-red-600" />
                  </button>
                </div>
                <div className="mt-1 text-xs text-gray-500 truncate">{video.filename}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 使用指南 */}
      <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
        <h3 className="font-medium text-blue-900 mb-2">使用指南</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• 文生视频：输入描述，AI 自动生成视频</li>
          <li>• 图生视频：上传参考图，让图片动起来</li>
          <li>• 关键帧动画：设置多个关键帧，生成过渡动画</li>
          <li>• 当前价格：免费（$0/秒）</li>
        </ul>
      </div>
    </div>
  )
}
