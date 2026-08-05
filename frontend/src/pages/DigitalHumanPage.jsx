import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic2, Sparkles, Play, Download, Trash2, UserCircle, Music2,
  Film, Eye, Clock, FileText, RefreshCw, Wand2, Check, Send,
  Image as ImageIcon, Palette, Radio, Volume2, Pause, StopCircle,
  Smile, Shirt, Monitor, Glasses, HardHat, Video, Circle, Camera,
  Upload, Rocket, X,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Modal, Badge } from '../components/ui'
import { useToast } from '../lib/toast'
import api, { API_BASE } from '../lib/api'
import AnimatedAvatar, { EXPRESSION_NAMES, OUTFIT_NAMES, SCENE_NAMES } from '../components/AnimatedAvatar'

const SCENES = [
  { id: 'product', name: '产品介绍', desc: '突出卖点，节奏明快', icon: Sparkles, color: 'from-amber-500 to-orange-600' },
  { id: 'course', name: '课程讲解', desc: '结构化讲解', icon: FileText, color: 'from-blue-500 to-indigo-600' },
  { id: 'news', name: '新闻播报', desc: '字正腔圆', icon: Radio, color: 'from-gray-700 to-gray-900' },
  { id: 'livestream', name: '直播带货', desc: '感染力强', icon: Wand2, color: 'from-pink-500 to-rose-600' },
  { id: 'story', name: '故事讲述', desc: '情感丰富', icon: Volume2, color: 'from-violet-500 to-purple-600' },
]

export default function DigitalHumanPage() {
  const toast = useToast()

  // 生成表单
  const [text, setText] = useState('')
  const [avatarId, setAvatarId] = useState('business-female')
  const [voiceId, setVoiceId] = useState('zh-CN-XiaoxiaoNeural')
  const [bgId, setBgId] = useState('tech')
  const [sceneId, setSceneId] = useState('product')
  const [speed, setSpeed] = useState(1.0)
  const [generating, setGenerating] = useState(false)

  // 数据
  const [avatars, setAvatars] = useState([])
  const [voices, setVoices] = useState([])
  const [backgrounds, setBackgrounds] = useState([])
  const [records, setRecords] = useState([])
  const [result, setResult] = useState(null)

  // 自定义形象 / 声音（用户上传）
  const [customAvatars, setCustomAvatars] = useState([])
  const [customVoices, setCustomVoices] = useState([])
  const [showAvatarModal, setShowAvatarModal] = useState(false)
  const [showVoiceModal, setShowVoiceModal] = useState(false)
  const [avatarForm, setAvatarForm] = useState({ name: '', desc: '', file: null, preview: '' })
  const [voiceForm, setVoiceForm] = useState({ name: '', desc: '', file: null })
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

  // 录制
  const [recording, setRecording] = useState(false)
  const [videoBlob, setVideoBlob] = useState(null)

  // 视频预览
  const videoRef = useRef(null)
  const [previewVideoUrl, setPreviewVideoUrl] = useState('')
  const [playingVideo, setPlayingVideo] = useState(false)

  // ★ AI 写真肖像
  const [portraitMap, setPortraitMap] = useState({})         // avatarId → portraitUrl
  const [generatingPortrait, setGeneratingPortrait] = useState(new Set())  // 正在生成的 avatarId
  const [generatingAll, setGeneratingAll] = useState(false)   // 是否在批量生成

  useEffect(() => { loadData(); loadRecords() }, [])

  const loadData = async () => {
    try {
      const [aRes, vRes, bRes] = await Promise.all([
        api.get('/api/digital-human/avatars'),
        api.get('/api/digital-human/voices'),
        api.get('/api/digital-human/backgrounds'),
      ])
      api.get('/api/digital-human/scenes')
        .then((res) => setCloudScenes(res.data?.scenes || []))
        .catch(() => {})
      api.get('/api/digital-human/portraits')
        .then((res) => setPortraitList(res.data?.portraits || []))
        .catch(() => {})
      // 自定义形象/声音（需登录，失败静默）
      api.get('/api/digital-human/custom-avatars')
        .then((res) => {
          const list = res.data?.avatars || []
          setCustomAvatars(list)
          // 自定义形象直接展示上传图片（无需 AI 写真）
          const pm = {}
          list.forEach((a) => { if (a.image_url) pm[a.id] = a.image_url })
          setPortraitMap(prev => ({ ...prev, ...pm }))
        })
        .catch(() => {})
      api.get('/api/digital-human/custom-voices')
        .then((res) => setCustomVoices(res.data?.voices || []))
        .catch(() => {})
      const avatarList = aRes.data?.avatars || []
      setAvatars(avatarList)
      setVoices(vRes.data?.voices || [])
      setBackgrounds(bRes.data?.backgrounds || [])
      // 构建写真映射（相对路径走 vite/nginx 代理，同源加载避免 CORS 缓存问题）
      const pm = {}
      avatarList.forEach(a => {
        if (a.has_portrait && a.portrait_url) {
          pm[a.id] = a.portrait_url.startsWith('http')
            ? a.portrait_url
            : a.portrait_url
        }
      })
      setPortraitMap(pm)
    } catch {/* 静默失败，不阻塞 UI */}
  }

  const loadRecords = async () => {
    try {
      const res = await api.get('/api/digital-human/records')
      setRecords(res.data || [])
    } catch {/* 静默失败，不阻塞 UI */}
  }

  // ★ 上传自定义形象（自己的头像/照片 → 数字人形象）
  const uploadCustomAvatar = async () => {
    if (!avatarForm.file) { toast.error('请先选择一张图片（jpg/png/webp）'); return }
    if (!avatarForm.name.trim()) { toast.error('请输入形象名称'); return }
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
      setCustomAvatars(prev => [...prev, av])
      if (av?.image_url) setPortraitMap(prev => ({ ...prev, [av.id]: av.image_url }))
      setAvatarId(av.id) // 上传后直接选中，便于立即试用
      toast.success(`自定义形象「${av.name}」已创建，可直接生成视频`)
    } catch (e) { toast.error(`上传失败：${e.message}`) }
    finally { setUploading(false) }
  }

  // ★ 上传自定义声音（自己的录音/音频 → 数字人配音）
  const uploadCustomVoice = async () => {
    if (!voiceForm.file) { toast.error('请先选择一个音频文件（mp3/wav/m4a）'); return }
    if (!voiceForm.name.trim()) { toast.error('请输入声音名称'); return }
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
      setCustomVoices(prev => [...prev, v])
      setVoiceId(v.id) // 上传后直接选中
      toast.success(`自定义声音「${v.name}」已创建，生成时直接使用该音频作为配音`)
    } catch (e) { toast.error(`上传失败：${e.message}`) }
    finally { setUploading(false) }
  }

  const deleteCustomAvatar = async (id) => {
    try {
      await api.delete(`/api/digital-human/custom-avatars/${id}`)
      setCustomAvatars(prev => prev.filter(a => a.id !== id))
      if (avatarId === id) setAvatarId('business-female')
      toast.success('已删除自定义形象')
    } catch (e) { toast.error(e.message) }
  }

  const deleteCustomVoice = async (id) => {
    try {
      await api.delete(`/api/digital-human/custom-voices/${id}`)
      setCustomVoices(prev => prev.filter(v => v.id !== id))
      if (voiceId === id) setVoiceId('zh-CN-XiaoxiaoNeural')
      toast.success('已删除自定义声音')
    } catch (e) { toast.error(e.message) }
  }

  // ★ 发布视频到内容平台（复用发布中心的账号矩阵与素材包能力）
  const publishVideo = async (videoUrl, contentText, recordName) => {
    const platform = window.prompt('选择发布平台：请输入 douyin（抖音）/ kuaishou（快手）/ wechat（公众号）')
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
        toast.success(`已自动发布到${res.data?.platform_label || platform}！${res.data?.message || ''}`)
      } else {
        toast.info('已生成发布素材包：请到发布中心查看引导步骤完成发布')
        window.open(`/publish`, '_blank')
      }
    } catch (e) { toast.error(`发布失败：${e.message}`) }
  }

  // ★ 生成单个数字人写真
  const generatePortrait = async (avatarId) => {
    const av = avatars.find(a => a.id === avatarId)
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
      setPortraitMap(prev => ({ ...prev, [avatarId]: portraitUrl }))
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
        toast.success(`写真生成完成！新增 ${generated} 个，已有 ${cached} 个${failed > 0 ? `，失败 ${failed} 个` : ''}`)
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
    } catch { toast.error('加载文案失败') }
  }

  const generate = async () => {
    if (!text.trim()) { toast.error('请输入口播文案'); return }
    setGenerating(true); setResult(null); stopAudio()
    try {
      const res = await api.post('/api/digital-human/generate', {
        text: text.trim(), avatar_id: avatarId, voice_id: voiceId,
        background_id: bgId, scene_id: sceneId, speed,
      })
      setResult(res.data)
      loadRecords()
      // 如果有视频URL，自动预览
      if (res.data.video_url) {
        playPreviewVideo(res.data.video_url)
      }
      // 如果有音频URL，自动播放
      if (res.data.audio_url) {
        const fullUrl = res.data.audio_url.startsWith('http')
          ? res.data.audio_url
          : `${API_BASE}${res.data.audio_url}`
        setAudioUrl(fullUrl)
        // 延迟确保 audio 元素挂载后再播放
        setTimeout(() => {
          if (audioRef.current) {
            audioRef.current.play().then(() => {
              setPlaying(true)
              setTalking(true)
            }).catch(() => {})
          }
        }, 300)
      }
      toast.success(res.data.message || '生成成功')
    } catch (e) { toast.error(`生成失败：${e.message}`) }
    finally { setGenerating(false) }
  }

  const playAudio = useCallback(() => {
    if (!audioRef.current) return
    audioRef.current.play().then(() => { setPlaying(true); setTalking(true) }).catch(() => {})
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

  // ── 录制控制 ──
  const startRecording = useCallback(() => {
    if (!avatarRef.current) { toast.error('角色未就绪'); return }
    avatarRef.current.startRecording()
    setRecording(true)
    setVideoBlob(null)
    toast.success('开始录制')
  }, [toast])

  const stopRecording = useCallback(async () => {
    if (!avatarRef.current) return
    const blob = await avatarRef.current.stopRecording()
    setRecording(false)
    if (blob) { setVideoBlob(blob); toast.success('录制完成') }
    else toast.error('录制失败')
  }, [toast])

  const downloadVideo = useCallback(() => {
    if (!videoBlob) return
    const url = URL.createObjectURL(videoBlob)
    const a = document.createElement('a'); a.href = url; a.download = `digital-human-${Date.now()}.webm`
    a.click(); URL.revokeObjectURL(url); toast.success('下载中')
  }, [videoBlob, toast])

  // 通用文件下载（通过 axios blob 获取，支持认证 + 跨域）
  const downloadFile = useCallback(async (urlPath, filename) => {
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
  }, [toast])

  // 播放服务器生成的视频
  const playPreviewVideo = useCallback((url) => {
    const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`
    setPreviewVideoUrl(fullUrl)
    setPlayingVideo(false)
    // 等 video 元素挂载后播放
    setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.play().then(() => setPlayingVideo(true)).catch(() => {})
      }
    }, 200)
  }, [])

  // 自动录制：生成 + 播放时同步录制
  const recordAndPlay = useCallback(async () => {
    if (!text.trim()) { toast.error('请输入口播文案'); return }
    setGenerating(true); setResult(null); stopAudio(); setVideoBlob(null)
    try {
      const res = await api.post('/api/digital-human/generate', {
        text: text.trim(), avatar_id: avatarId, voice_id: voiceId,
        background_id: bgId, scene_id: sceneId, speed,
      })
      setResult(res.data); loadRecords()
      if (res.data.audio_url) {
        const fullUrl = res.data.audio_url.startsWith('http')
          ? res.data.audio_url : `${API_BASE}${res.data.audio_url}`
        setAudioUrl(fullUrl)
        setTimeout(() => {
          if (audioRef.current && avatarRef.current) {
            avatarRef.current.startRecording()
            setRecording(true)
            audioRef.current.play().then(() => { setPlaying(true); setTalking(true) }).catch(() => {})
          }
        }, 300)
      }
      toast.success(res.data.message || '生成成功')
    } catch (e) { toast.error(`生成失败：${e.message}`) }
    finally { setGenerating(false) }
  }, [text, avatarId, voiceId, bgId, sceneId, speed, toast, stopAudio, loadRecords])

  // 音频结束时停止录制
  useEffect(() => {
    if (!playing && recording && avatarRef.current) {
      avatarRef.current.stopRecording().then(blob => {
        setRecording(false)
        if (blob) setVideoBlob(blob)
      })
    }
  }, [playing, recording])

  const deleteRecord = async (id) => {
    try { await api.delete(`/api/digital-human/records/${id}`); loadRecords(); toast.success('已删除') }
    catch (e) { toast.error(e.message) }
  }

  const loadArticle = (a) => {
    setText(a.result || a.prompt || '')
    setShowArticles(false)
    toast.success('已加载文案')
  }

  const selectedAvatar = avatars.find(a => a.id === avatarId)
  const selectedVoice = voices.find(v => v.id === voiceId)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI数字人"
        description="文案→配音→口播视频，12款虚拟形象（含性感女神/甜美女神）+ AI写真肖像 + 8种音色，一键生成专业数字人口播视频"
        icon={UserCircle}
        iconColor="from-violet-500 to-purple-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左列：配置面板 */}
        <div className="space-y-4">
          {/* 场景模板 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Radio className="w-4 h-4 text-amber-500" /> 场景模板
            </h3>
            <div className="space-y-1.5">
              {(cloudScenes.length > 0 ? cloudScenes : SCENES).map((s) => {
                const SceneIcon = s.icon || Sparkles
                return (
                <button key={s.id} onClick={() => { setSceneId(s.id) }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs transition-all ${
                    sceneId === s.id ? 'bg-violet-50 border border-violet-200 text-violet-700 font-medium' : 'border border-gray-100 text-gray-600 hover:bg-gray-50'
                  }`}>
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
            <div className="grid grid-cols-3 gap-2">
              {(backgrounds.length > 0 ? backgrounds : [{ id: 'tech', name: '科技蓝幕', color: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }, { id: 'office', name: '现代办公室', color: '#1a1a2e' }, { id: 'studio', name: '简约演播室', color: '#16213e' }]).map((b) => (
                <button key={b.id} onClick={() => setBgId(b.id)}
                  className={`h-12 rounded-lg text-[10px] font-medium overflow-hidden transition-all ${
                    bgId === b.id ? 'ring-2 ring-emerald-500' : 'opacity-75 hover:opacity-100'
                  }`}
                  style={{ background: b.color }}
                  title={b.name}>
                  <span className="flex items-center justify-center h-full w-full bg-black/35 text-white">{b.name}</span>
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
                  onClick={() => { setAvatarForm({ name: '', desc: '', file: null, preview: '' }); setShowAvatarModal(true) }}
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
              {/* 自定义形象（用户上传，带删除） */}
              {customAvatars.map((a) => (
                <div key={a.id} className="relative group">
                  <button onClick={() => setAvatarId(a.id)}
                    className={`relative w-full flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition-all ${
                      avatarId === a.id ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-500/20' : 'border-blue-100 hover:border-blue-200 hover:bg-blue-50/30'
                    }`}>
                    <div className="w-12 h-12 rounded-full overflow-hidden ring-2 ring-blue-200 shadow-sm">
                      <img src={a.image_url} alt={a.name} className="w-full h-full object-cover" />
                    </div>
                    <div className="text-xs font-medium text-gray-800">{a.name}</div>
                    <div className="text-[10px] text-blue-500">我的形象</div>
                  </button>
                  <button onClick={() => deleteCustomAvatar(a.id)}
                    className="absolute -top-1.5 -right-1.5 p-1 rounded-full bg-red-500 text-white shadow opacity-0 group-hover:opacity-100 transition-opacity"
                    title="删除该形象">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {avatars.map((a) => {
                const hasPortrait = !!portraitMap[a.id]
                const isGenerating = generatingPortrait.has(a.id)
                return (
                <button key={a.id} onClick={() => setAvatarId(a.id)}
                  className={`relative flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition-all ${
                    avatarId === a.id ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-500/20' : 'border-gray-100 hover:border-violet-200 hover:bg-violet-50/30'
                  }`}>
                  {/* 写真状态角标 */}
                  {hasPortrait ? (
                    <span className="absolute top-1 right-1 w-2.5 h-2.5 bg-emerald-400 rounded-full ring-2 ring-white" title="AI写真已就绪" />
                  ) : isGenerating ? (
                    <span className="absolute top-1 right-1 w-2.5 h-2.5 bg-amber-400 rounded-full ring-2 ring-white animate-pulse" title="写真生成中..." />
                  ) : null}
                  {/* 头像预览 — 有写真则显示写真缩略图 */}
                  {hasPortrait ? (
                    <div className="w-12 h-12 rounded-full overflow-hidden ring-2 ring-violet-200 shadow-sm">
                      <img src={portraitMap[a.id]} alt={a.name} className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${a.bg_color} flex items-center justify-center text-lg`}>
                      {a.emoji}
                    </div>
                  )}
                  <div className="text-xs font-medium text-gray-800">{a.name}</div>
                  <div className="text-[10px] text-gray-400">{a.style}</div>
                  {/* 写真生成按钮（仅在选中且无写真时显示） */}
                  {avatarId === a.id && !hasPortrait && !isGenerating && (
                    <span
                      onClick={(e) => { e.stopPropagation(); generatePortrait(a.id) }}
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
              )})}
            </div>
          </Card>

          {/* 声音选择 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Mic2 className="w-4 h-4 text-pink-500" /> 声音选择
              </h3>
              <button
                onClick={() => { setVoiceForm({ name: '', desc: '', file: null }); setShowVoiceModal(true) }}
                className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg border border-pink-200 bg-pink-50 text-pink-600 hover:bg-pink-100 transition-all"
              >
                <Upload className="w-3 h-3" /> 上传我的声音
              </button>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {/* 自定义声音（用户上传录音，直接作为配音） */}
              {customVoices.map((v) => (
                <div key={v.id} className="relative group">
                  <button onClick={() => setVoiceId(v.id)}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all ${
                      voiceId === v.id ? 'bg-pink-50 border border-pink-200 text-pink-700 font-medium' : 'border border-pink-100 text-gray-600 hover:bg-gray-50'
                    }`}>
                    <span className="text-base">🎙️</span>
                    <div className="flex-1 text-left">
                      <div className="font-medium">{v.name} · 我的声音</div>
                      <div className="text-[10px] text-gray-400">{v.desc || `时长 ${Math.round(v.duration || 0)}s 的录音，直接作为配音`}</div>
                    </div>
                    {voiceId === v.id && <Check className="w-3.5 h-3.5 text-pink-500 flex-shrink-0" />}
                  </button>
                  <button onClick={() => deleteCustomVoice(v.id)}
                    className="absolute top-1 right-7 p-1 rounded-full bg-red-500 text-white shadow opacity-0 group-hover:opacity-100 transition-opacity"
                    title="删除该声音">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {voices.map((v) => (
                <button key={v.id} onClick={() => setVoiceId(v.id)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all ${
                    voiceId === v.id ? 'bg-pink-50 border border-pink-200 text-pink-700 font-medium' : 'border border-gray-100 text-gray-600 hover:bg-gray-50'
                  }`}>
                  <span className="text-base">{v.emoji}</span>
                  <div className="flex-1 text-left">
                    <div className="font-medium">{v.name} · {v.gender}</div>
                    <div className="text-[10px] text-gray-400">{v.style}</div>
                  </div>
                  {voiceId === v.id && <Check className="w-3.5 h-3.5 text-pink-500 flex-shrink-0" />}
                </button>
              ))}
            </div>
            <div className="mt-2">
              <label className="text-xs text-gray-500">语速：{speed.toFixed(1)}x</label>
              <input type="range" min={0.5} max={2.0} step={0.05} value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                className="w-full mt-1 accent-violet-500" />
            </div>
          </Card>

          {/* 虚拟场景 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Monitor className="w-4 h-4 text-emerald-500" /> 虚拟场景
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(SCENE_NAMES).map(([key, name]) => (
                <button key={key} onClick={() => setAvatarScene(key)}
                  className={`p-2 rounded-lg text-xs font-medium transition-all ${
                    avatarScene === key ? 'bg-emerald-100 text-emerald-700 border border-emerald-300' : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                  }`}>
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
            <div className="grid grid-cols-3 gap-1.5">
              {Object.entries(EXPRESSION_NAMES).map(([key, name]) => (
                <button key={key} onClick={() => setCurrentExpression(key)}
                  className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                    currentExpression === key ? 'bg-yellow-100 text-yellow-700 border border-yellow-300' : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                  }`}>
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
                    <button key={key} onClick={() => setOutfit(key)}
                      className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
                        outfit === key ? 'bg-orange-100 text-orange-700 border border-orange-300' : 'bg-gray-50 text-gray-600 border border-gray-100 hover:bg-gray-100'
                      }`}>
                      {name}
                    </button>
                  ))}
                </div>
              </div>
              {/* 配饰 */}
              <div className="flex gap-2">
                <button onClick={() => setGlasses(!glasses)}
                  className={`flex-1 flex items-center justify-center gap-1.5 p-1.5 rounded-lg text-xs font-medium transition-all ${
                    glasses ? 'bg-blue-100 text-blue-700 border border-blue-300' : 'bg-gray-50 text-gray-500 border border-gray-100 hover:bg-gray-100'
                  }`}>
                  <Glasses className="w-3 h-3" /> 眼镜
                </button>
                <button onClick={() => setHat(!hat)}
                  className={`flex-1 flex items-center justify-center gap-1.5 p-1.5 rounded-lg text-xs font-medium transition-all ${
                    hat ? 'bg-purple-100 text-purple-700 border border-purple-300' : 'bg-gray-50 text-gray-500 border border-gray-100 hover:bg-gray-100'
                  }`}>
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
              <Button variant="secondary" size="sm" icon={FileText} onClick={loadArticles}>
                从素材库加载
              </Button>
            </div>
            <textarea value={text} onChange={(e) => setText(e.target.value)}
              placeholder="输入口播文案，AI 会自动优化为更流畅自然的口播脚本…&#10;&#10;如：大家好，今天给大家介绍一款全新的AI效率工具，它可以在30秒内帮你完成…"
              rows={12}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none" />
          </Card>

          {/* 生成按钮 */}
          <div className="flex gap-2">
            <Button variant="primary" size="lg" icon={Sparkles} loading={generating} onClick={generate} className="flex-1">
              {generating ? 'AI数字人正在生成…' : '生成数字人视频'}
            </Button>
            <Button variant="secondary" size="lg" icon={Video} loading={generating} onClick={recordAndPlay}>
              生成+录制
            </Button>
          </div>

          {/* 预览区 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Eye className="w-4 h-4 text-violet-500" /> 实时预览
                {talking && <span className="text-[10px] text-emerald-500 font-normal animate-pulse">● 口型同步中</span>}
                {recording && <span className="text-[10px] text-red-500 font-normal animate-pulse">● 录制中</span>}
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
                      <Button variant="secondary" size="sm" icon={Pause} onClick={pauseAudio}>暂停</Button>
                    ) : (
                      <Button variant="secondary" size="sm" icon={Play} onClick={playAudio}>播放</Button>
                    )}
                    <Button variant="ghost" size="sm" icon={StopCircle} onClick={stopAudio} />
                  </>
                )}
              </div>
            </div>
            <div className="relative rounded-xl overflow-hidden border border-gray-200 flex items-center justify-center" style={{ minHeight: 350 }}>
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
                      <img src={portraitMap[avatarId]} alt="" className="w-4 h-4 rounded-full object-cover ring-1 ring-white/50" />
                    ) : (
                      <UserCircle className="w-3 h-3" />
                    )}
                    {selectedAvatar?.name || '选择形象'}
                  </span>
                  <span className="flex items-center gap-1"><Volume2 className="w-3 h-3" /> {selectedVoice?.name || ''}</span>
                  <span className="flex items-center gap-1"><Smile className="w-3 h-3" /> {EXPRESSION_NAMES[currentExpression]}</span>
                  {portraitMap[avatarId] && <span className="text-[10px] text-emerald-300">● AI写真</span>}
                </div>
              </div>
            </div>
            {/* 音频播放条 */}
            {audioUrl && (
              <div className="mt-3 border border-gray-200 rounded-lg overflow-hidden bg-gray-50 px-3 py-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-700 flex items-center gap-1.5">
                    <Volume2 className="w-3.5 h-3.5 text-violet-500" /> 配音音频
                    {playing && <span className="text-[10px] text-emerald-500 animate-pulse">● 播放中</span>}
                  </span>
                  <span className="text-[10px] text-gray-400">{selectedVoice?.name || ''}</span>
                </div>
                <audio
                  ref={audioRef}
                  src={audioUrl}
                  controls
                  onPlay={() => { setPlaying(true); setTalking(true) }}
                  onPause={() => { setPlaying(false); setTalking(false) }}
                  onEnded={() => { setPlaying(false); setTalking(false) }}
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
                    {playingVideo && <span className="text-[10px] text-emerald-500 animate-pulse">● 播放中</span>}
                  </span>
                  <button onClick={() => { setPreviewVideoUrl(''); setPlayingVideo(false) }}
                    className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
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
              <div className={`p-3 rounded-xl border text-sm mb-3 ${
                result.status === 'done' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'
              }`}>
                {result.message}
              </div>
              <div className="space-y-2 text-xs text-gray-600">
                <div className="flex justify-between">
                  <span>数字人：</span>
                  <span className="font-medium">{result.avatar?.name} {result.avatar?.emoji}</span>
                </div>
                <div className="flex justify-between">
                  <span>声音：</span>
                  <span className="font-medium">{result.voice?.name}</span>
                </div>
                <div className="flex justify-between">
                  <span>文案长度：</span>
                  <span className="font-medium">{result.text_length} 字</span>
                </div>
                <div className="flex justify-between">
                  <span>状态：</span>
                  <Badge color={result.status === 'done' ? 'green' : 'amber'}>
                    {result.status === 'done' ? '已完成' : '仅音频'}
                  </Badge>
                </div>
              </div>
              {/* 下载/播放按钮 */}
              <div className="flex gap-2 mt-3">
                {result.audio_url && (
                  <button onClick={() => {
                    const fullUrl = result.audio_url.startsWith('http')
                      ? result.audio_url : `${API_BASE}${result.audio_url}`
                    setAudioUrl(fullUrl)
                    setTimeout(() => {
                      if (audioRef.current) {
                        audioRef.current.play().then(() => { setPlaying(true); setTalking(true) }).catch(() => {})
                      }
                    }, 200)
                  }}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-colors">
                    <Play className="w-3.5 h-3.5" /> 播放音频
                  </button>
                )}
                {result.audio_url && (
                  <button onClick={() => downloadFile(result.audio_url, 'digital-human-audio.mp3')}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-violet-50 border border-violet-200 text-violet-700 text-xs font-medium hover:bg-violet-100 transition-colors">
                    <Download className="w-3.5 h-3.5" /> 下载 MP3
                  </button>
                )}
                {result.video_url && (
                  <button onClick={() => playPreviewVideo(result.video_url)}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-colors">
                    <Play className="w-3.5 h-3.5" /> 播放视频
                  </button>
                )}
                {result.video_url && (
                  <button onClick={() => downloadFile(result.video_url, 'digital-human-video.mp4')}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors">
                    <Download className="w-3.5 h-3.5" /> 下载 MP4
                  </button>
                )}
                {result.video_url && (
                  <button onClick={() => publishVideo(result.video_url, text, result.avatar?.name)}
                    className="flex-1 flex items-center justify-center gap-1.5 p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium hover:bg-rose-100 transition-colors">
                    <Rocket className="w-3.5 h-3.5" /> 发布
                  </button>
                )}
              </div>
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
                  <Badge color="purple">{portraitList.filter((p) => p.exists).length} 张已生成</Badge>
                </h3>
                <Button variant="secondary" size="sm" icon={RefreshCw}
                  onClick={() => api.get('/api/digital-human/portraits').then((res) => setPortraitList(res.data?.portraits || [])).catch(() => {})}>
                  刷新
                </Button>
              </div>
              <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
                {portraitList.filter((p) => p.exists).map((p) => (
                  <div key={p.avatar_id} className="group relative">
                    <img src={p.url} alt={p.avatar_name}
                      onClick={() => { setAvatarId(p.avatar_id); toast.info(`已选中 ${p.avatar_name}`) }}
                      className="w-full aspect-square object-cover rounded-xl border border-gray-200 cursor-pointer group-hover:ring-2 group-hover:ring-violet-400 transition-all" />
                    <div className="mt-1 text-[10px] text-gray-500 truncate text-center">{p.avatar_name}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}

        {/* 历史记录 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-500" /> 历史记录（{records.length}）
              </h3>
              <Button variant="secondary" size="sm" icon={RefreshCw} onClick={loadRecords}>刷新</Button>
            </div>
            {records.length === 0 ? (
              <Empty icon={Film} title="暂无记录" description="生成第一个数字人视频后这里会显示" />
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {records.map((r) => {
                  const av = avatars.find(a => a.id === r.avatar_id)
                  return (
                    <div key={r.id} className={`p-3 rounded-xl border transition-all ${
                      r.status === 'done' ? 'border-emerald-200 bg-emerald-50/30' : 'border-amber-200 bg-amber-50/30'
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-lg">{av?.emoji || '👤'}</span>
                          <div>
                            <div className="text-xs font-medium text-gray-800">{av?.name || r.avatar_name}</div>
                            <div className="text-[10px] text-gray-400">{r.voice_name} · {r.text_length}字</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <Badge color={r.status === 'done' ? 'green' : 'amber'}>
                            {r.status === 'done' ? '完成' : '仅音频'}
                          </Badge>
                          <button onClick={() => deleteRecord(r.id)}
                            className="p-1 text-gray-300 hover:text-red-500 rounded">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 truncate mt-1">{r.text?.slice(0, 60)}</p>
                      <div className="flex items-center justify-between mt-1.5">
                        <div className="text-[10px] text-gray-400">{r.created_at?.slice(0, 16)?.replace('T', ' ')}</div>
                        <div className="flex items-center gap-1">
                          {r.audio_url && (
                            <button onClick={() => {
                              const fullUrl = r.audio_url.startsWith('http')
                                ? r.audio_url : `${API_BASE}${r.audio_url}`
                              setAudioUrl(fullUrl)
                              setTimeout(() => {
                                if (audioRef.current) {
                                  audioRef.current.play().then(() => { setPlaying(true); setTalking(true) }).catch(() => {})
                                }
                              }, 200)
                            }}
                              className="text-[10px] text-blue-500 hover:text-blue-700 px-1.5 py-0.5 rounded hover:bg-blue-50">
                              播放
                            </button>
                          )}
                          {r.audio_url && (
                            <button onClick={() => downloadFile(r.audio_url, `${r.avatar_name || 'audio'}.mp3`)}
                              className="text-[10px] text-violet-500 hover:text-violet-700 px-1.5 py-0.5 rounded hover:bg-violet-50">
                              MP3
                            </button>
                          )}
                          {r.video_url && (
                            <button onClick={() => playPreviewVideo(r.video_url)}
                              className="text-[10px] text-blue-500 hover:text-blue-700 px-1.5 py-0.5 rounded hover:bg-blue-50">
                              播放
                            </button>
                          )}
                          {r.video_url && (
                            <button onClick={() => downloadFile(r.video_url, `${r.avatar_name || 'video'}.mp4`)}
                              className="text-[10px] text-emerald-500 hover:text-emerald-700 px-1.5 py-0.5 rounded hover:bg-emerald-50">
                              MP4
                            </button>
                          )}
                          {r.video_url && (
                            <button onClick={() => publishVideo(r.video_url, r.text, r.avatar_name)}
                              className="text-[10px] text-rose-500 hover:text-rose-700 px-1.5 py-0.5 rounded hover:bg-rose-50">
                              🚀 发布
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* 上传自定义形象 Modal */}
      <Modal open={showAvatarModal} onClose={() => setShowAvatarModal(false)} title="上传我的形象" size="sm">
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
                type="file" accept="image/*" className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  setAvatarForm(prev => ({ ...prev, file: f, preview: URL.createObjectURL(f) }))
                }}
              />
            </label>
            <div className="flex-1 space-y-2">
              <input
                value={avatarForm.name} placeholder="形象名称（如：我的真人形象）" maxLength={20}
                onChange={(e) => setAvatarForm(prev => ({ ...prev, name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <input
                value={avatarForm.desc} placeholder="描述（选填，如：休闲装、办公室背景）" maxLength={100}
                onChange={(e) => setAvatarForm(prev => ({ ...prev, desc: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowAvatarModal(false)}>取消</Button>
            <Button variant="primary" size="sm" icon={Upload} loading={uploading} onClick={uploadCustomAvatar}>
              上传并创建
            </Button>
          </div>
        </div>
      </Modal>

      {/* 上传自定义声音 Modal */}
      <Modal open={showVoiceModal} onClose={() => setShowVoiceModal(false)} title="上传我的声音" size="sm">
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
              type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg" className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (!f) return
                setVoiceForm(prev => ({ ...prev, file: f }))
              }}
            />
          </label>
          <input
            value={voiceForm.name} placeholder="声音名称（如：我的声音）" maxLength={20}
            onChange={(e) => setVoiceForm(prev => ({ ...prev, name: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
          />
          <input
            value={voiceForm.desc} placeholder="描述（选填，如：普通话男声、居家录音）" maxLength={100}
            onChange={(e) => setVoiceForm(prev => ({ ...prev, desc: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowVoiceModal(false)}>取消</Button>
            <Button variant="primary" size="sm" icon={Upload} loading={uploading} onClick={uploadCustomVoice}>
              上传并创建
            </Button>
          </div>
        </div>
      </Modal>

      {/* 文案素材库 Modal */}
      <Modal open={showArticles} onClose={() => setShowArticles(false)} title="从素材库加载文案" size="md">
        {articles.length === 0 ? (
          <Empty icon={FileText} title="暂无素材" description="请先在发布中心或文案工厂生成文章" />
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {articles.map((a) => (
              <div key={a.id} className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-violet-200 hover:bg-violet-50/30 transition-all cursor-pointer"
                onClick={() => loadArticle(a)}>
                <FileText className="w-4 h-4 text-violet-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">{a.title || a.prompt?.slice(0, 40) || '未命名'}</div>
                  <div className="text-xs text-gray-400 truncate">{(a.result || a.prompt || '').slice(0, 80)}</div>
                </div>
                <span className="text-xs text-gray-400 flex-shrink-0">{a.created_at?.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  )
}
