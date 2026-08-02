import React, { useState, useEffect, useRef } from 'react'
import { 
  Video, Film, Play, Pause, Download, Loader, Sparkles,
  Clock, Maximize2, Trash2, RefreshCw, Image as ImageIcon,
  Camera, Wand2, DownloadCloud
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
  const [mode, setMode] = useState('ti2vid')
  const [image, setImage] = useState('')
  const [frameRate, setFrameRate] = useState(24)
  const [isGenerating, setIsGenerating] = useState(false)
  const [lastResult, setLastResult] = useState(null)
  const [pollingId, setPollingId] = useState(null)
  
  // 视频播放器
  const [selectedVideo, setSelectedVideo] = useState(null)
  const videoRef = useRef(null)

  // 预设提示词
  const presets = [
    'A beautiful sunset over the ocean with gentle waves, cinematic quality',
    'A cute cat walking on the beach at sunset, warm golden light',
    'Time-lapse of a flower blooming in fast motion, macro photography',
    'Aerial view of a misty mountain range at sunrise, drone footage',
    'Slow motion water droplets falling into a pond, high speed photography',
    'A cozy coffee shop on a rainy day, warm lighting, cinematic',
  ]

  useEffect(() => {
    loadStats()
    loadVideos()
    return () => {
      if (pollingId) clearInterval(pollingId)
    }
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

  const createVideoTask = async () => {
    if (!prompt.trim()) {
      alert('请输入视频描述')
      return
    }
    setIsGenerating(true)
    setLastResult(null)
    
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
      
      if (data.video_id) {
        setLastResult({ 
          video_id: data.video_id, 
          status: 'pending', 
          prompt: prompt,
          created_at: new Date().toLocaleString()
        })
        startPolling(data.video_id)
      }
    } catch (e) {
      console.error('创建视频任务失败:', e)
      alert('创建任务失败，请重试')
    } finally {
      setIsGenerating(false)
    }
  }

  const startPolling = (videoId) => {
    if (pollingId) clearInterval(pollingId)
    
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/video-factory/result/${videoId}`)
        const data = await res.json()
        
        setLastResult(prev => ({ ...prev, ...data }))
        
        if (data.status === 'completed') {
          clearInterval(pollingId)
          loadVideos()
          alert('🎉 视频生成完成！')
        } else if (data.status === 'failed') {
          clearInterval(pollingId)
          alert('❌ 视频生成失败: ' + (data.error || '未知错误'))
        }
      } catch (e) {
        console.error('检查状态失败:', e)
      }
    }
    
    poll()
    const id = setInterval(poll, 5000)
    setPollingId(id)
  }

  const deleteVideo = async (filename) => {
    if (!confirm('确定删除该视频？')) return
    await fetch(`${API_BASE}/api/video-factory/delete/${filename}`, { method: 'DELETE' })
    loadVideos()
    if (selectedVideo?.filename === filename) {
      setSelectedVideo(null)
    }
  }

  const handlePlayVideo = (video) => {
    setSelectedVideo(video)
    setTimeout(() => videoRef.current?.play(), 100)
  }

  const handlePauseVideo = () => {
    videoRef.current?.pause()
  }

  return (
    <div className="p-6 space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
            <Video className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">视频工厂</h1>
            <p className="text-gray-500">文生视频、图生视频、关键帧动画</p>
          </div>
        </div>
        <button onClick={loadVideos} className="p-2 hover:bg-gray-100 rounded-lg">
          <RefreshCw className="w-5 h-5 text-gray-600" />
        </button>
      </div>

      {/* 统计 */}
      <div className="grid grid-cols-4 gap-4">
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
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-2xl font-bold text-orange-600">V2.0</div>
          <div className="text-sm text-gray-500">模型版本</div>
        </div>
      </div>

      {/* 生成表单 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-blue-500" />
            创建视频任务
          </h2>
          <button 
            onClick={() => setPrompt(presets[Math.floor(Math.random() * presets.length)])}
            className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <Wand2 className="w-4 h-4" />
            随机提示词
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">视频描述</label>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="描述你想要的视频内容，例如：A beautiful sunset over the ocean, waves gently crashing on the shore..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          {presets.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="text-xs text-gray-500">快捷预设:</span>
              {presets.slice(0, 3).map((p, i) => (
                <button
                  key={i}
                  onClick={() => setPrompt(p)}
                  className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-600 truncate max-w-xs"
                >
                  {p.slice(0, 30)}...
                </button>
              ))}
            </div>
          )}
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
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {isGenerating ? <Loader className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
          {isGenerating ? '创建任务中...' : '创建视频任务'}
        </button>

        {lastResult && (
          <div className={`p-4 rounded-lg ${
            lastResult.status === 'completed' ? 'bg-green-50 border border-green-200' : 
            lastResult.status === 'failed' ? 'bg-red-50 border border-red-200' : 
            'bg-blue-50 border border-blue-200'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-gray-900 flex items-center gap-2">
                  {lastResult.status === 'completed' && <span>✅</span>}
                  {lastResult.status === 'pending' && <span>⏳</span>}
                  {lastResult.status === 'failed' && <span>❌</span>}
                  {lastResult.status === 'completed' ? '视频生成完成' : 
                   lastResult.status === 'pending' ? '视频生成中...' : '视频生成失败'}
                </div>
                <div className="text-sm text-gray-500 mt-1">
                  ID: {lastResult.video_id?.slice(0, 50)}...
                </div>
                {lastResult.created_at && (
                  <div className="text-xs text-gray-400 mt-1">
                    创建时间: {lastResult.created_at}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {lastResult.status === 'completed' && lastResult.url && (
                  <a
                    href={`${API_BASE}${lastResult.url}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                    onClick={() => handlePlayVideo(lastResult)}
                  >
                    <Play className="w-4 h-4" />
                    查看视频
                  </a>
                )}
                {lastResult.status === 'pending' && (
                  <button
                    onClick={() => startPolling(lastResult.video_id)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    <RefreshCw className="w-4 h-4" />
                    刷新状态
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 视频播放器模态框 */}
      {selectedVideo && (
        <div className="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4" onClick={() => setSelectedVideo(null)}>
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">视频预览</h3>
              <button onClick={() => setSelectedVideo(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                <Maximize2 className="w-5 h-5 text-gray-600" />
              </button>
            </div>
            <div className="p-4">
              <video
                ref={videoRef}
                src={`${API_BASE}${selectedVideo.url}`}
                className="w-full rounded-lg"
                controls
                autoPlay
              />
            </div>
            <div className="p-4 border-t border-gray-200 flex items-center justify-between">
              <div className="text-sm text-gray-500">{selectedVideo.filename}</div>
              <div className="flex items-center gap-2">
                <a 
                  href={`${API_BASE}${selectedVideo.url}`} 
                  download={selectedVideo.filename}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  <Download className="w-4 h-4" />
                  下载视频
                </a>
                <button 
                  onClick={() => deleteVideo(selectedVideo.filename)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 视频库 */}
      {videos.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Film className="w-5 h-5 text-blue-500" />
            我的视频库 ({videos.length})
          </h2>
          <div className="grid grid-cols-3 gap-4">
            {videos.map(video => (
              <div key={video.filename} className="group relative">
                <div 
                  className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center cursor-pointer hover:bg-gray-200 transition-colors"
                  onClick={() => handlePlayVideo(video)}
                >
                  <Video className="w-8 h-8 text-gray-400 group-hover:text-blue-500 transition-colors" />
                </div>
                <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 rounded-lg flex items-center justify-center gap-2 transition-all opacity-0 group-hover:opacity-100">
                  <button 
                    onClick={(e) => { e.stopPropagation(); handlePlayVideo(video); }}
                    className="p-2 bg-white rounded-full hover:bg-blue-50"
                  >
                    <Play className="w-4 h-4 text-blue-600" />
                  </button>
                  <a 
                    href={`${API_BASE}${video.url}`} 
                    download
                    onClick={e => e.stopPropagation()}
                    className="p-2 bg-white rounded-full hover:bg-green-50"
                  >
                    <Download className="w-4 h-4 text-green-600" />
                  </a>
                  <button 
                    onClick={(e) => { e.stopPropagation(); deleteVideo(video.filename); }}
                    className="p-2 bg-white rounded-full hover:bg-red-50"
                  >
                    <Trash2 className="w-4 h-4 text-red-600" />
                  </button>
                </div>
                <div className="mt-2 text-xs text-gray-500 truncate">{video.filename}</div>
                <div className="text-xs text-gray-400">{(video.size / 1024 / 1024).toFixed(2)} MB</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 使用指南 */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 rounded-xl p-4 border border-blue-100">
        <h3 className="font-medium text-blue-900 mb-3 flex items-center gap-2">
          <FilmStrip className="w-5 h-5" />
          使用指南
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">🎬 文生视频</div>
            <div className="text-sm text-gray-600 mt-1">输入文字描述，AI 自动生成视频</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">🖼️ 图生视频</div>
            <div className="text-sm text-gray-600 mt-1">上传参考图，让图片中的元素动起来</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">✨ 关键帧动画</div>
            <div className="text-sm text-gray-600 mt-1">设置多个关键帧，生成流畅过渡动画</div>
          </div>
        </div>
        <div className="mt-3 text-sm text-blue-700">
          💡 当前 Agnes Video V2.0 免费使用，支持 480p/720p/1080p，最长 15 秒
        </div>
      </div>
    </div>
  )
}
