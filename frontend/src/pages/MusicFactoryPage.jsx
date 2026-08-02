import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Music, FileText, Mic, Play, Pause, Download, Sparkles,
  RefreshCw, Wand2, Trash2, Headphones, Music2, Disc, Volume2, Copy,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatBytes, copyToClipboard } from '../lib/format'
import {
  Button, Empty, SkeletonList, ErrorState,
  PageHeader, ConfirmDialog,
} from '../components/ui'

const MEDIA_BASE = api.defaults.baseURL
const absUrl = (u) => (u ? (u.startsWith('http') ? u : `${MEDIA_BASE}${u}`) : '')

const PRESET_THEMES = [
  { text: '夏日海滩旅行', style: 'pop' },
  { text: '星空下的告白', style: 'ballad' },
  { text: '城市霓虹灯', style: 'rap' },
  { text: '春天的约定', style: 'pop' },
  { text: '深夜食堂', style: 'jazz' },
  { text: '青春奋斗', style: 'rock' },
]

const STYLES = [
  { value: 'pop', label: '流行' },
  { value: 'rock', label: '摇滚' },
  { value: 'rap', label: '说唱' },
  { value: 'ballad', label: '抒情' },
  { value: 'jazz', label: '爵士' },
  { value: 'classical', label: '古典' },
]

const MOODS = [
  { value: 'happy', label: '欢快' },
  { value: 'sad', label: '悲伤' },
  { value: 'energetic', label: '激昂' },
  { value: 'calm', label: '平静' },
  { value: 'romantic', label: '浪漫' },
]

const LENGTHS = [
  { value: 'short', label: '短歌 (30-60秒)' },
  { value: 'medium', label: '中歌 (2-3分钟)' },
  { value: 'long', label: '长歌 (3-5分钟)' },
]

const VOICES = [
  { value: 'female', label: '女声' },
  { value: 'male', label: '男声' },
]

const TABS = [
  { key: 'lyrics', label: '歌词生成', icon: FileText },
  { key: 'music', label: '音乐生成', icon: Music2 },
  { key: 'tts', label: '虚拟人声', icon: Mic },
]

export default function MusicFactoryPage() {
  const toast = useToast()
  const [activeTab, setActiveTab] = useState('lyrics')
  const [stats, setStats] = useState({ total_tracks: 0, api_configured: false })
  const [audios, setAudios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 歌词
  const [theme, setTheme] = useState('')
  const [style, setStyle] = useState('pop')
  const [language, setLanguage] = useState('zh')
  const [length, setLength] = useState('medium')
  const [lyrics, setLyrics] = useState('')
  const [generatingLyrics, setGeneratingLyrics] = useState(false)
  const [lyricsError, setLyricsError] = useState('')

  // 音乐
  const [selectedLyrics, setSelectedLyrics] = useState('')
  const [mood, setMood] = useState('happy')
  const [musicDuration, setMusicDuration] = useState(30)
  const [generatingMusic, setGeneratingMusic] = useState(false)
  const [musicResult, setMusicResult] = useState(null)

  // TTS
  const [ttsText, setTtsText] = useState('')
  const [ttsVoice, setTtsVoice] = useState('female')
  const [generatingTts, setGeneratingTts] = useState(false)
  const [ttsResult, setTtsResult] = useState(null)

  // 播放
  const [playingAudio, setPlayingAudio] = useState(null)
  const audioRef = useRef(null)

  // 删除
  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/api/music-factory/stats')
      setStats(res.data)
    } catch { /* 静默 */ }
  }, [])

  const fetchAudios = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/music-factory/list')
      setAudios((res.data.items || []).filter((i) => i.type === 'audio'))
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()
    fetchAudios()
  }, [fetchStats, fetchAudios])

  const generateLyrics = async () => {
    if (!theme.trim()) {
      setLyricsError('请输入歌曲主题')
      return
    }
    setLyricsError('')
    setGeneratingLyrics(true)
    setLyrics('')
    try {
      const form = new FormData()
      form.append('theme', theme)
      form.append('style', style)
      form.append('language', language)
      form.append('length', length)
      const res = await api.post('/api/music-factory/lyrics/generate', form, { timeout: 120000 })
      const data = res.data
      if (data.lyrics) {
        setLyrics(data.lyrics)
        setSelectedLyrics(data.lyrics)
        toast.success('歌词生成完成')
      } else {
        setLyricsError('生成失败')
      }
    } catch (e) {
      setLyricsError(`生成失败：${e.message}`)
    } finally {
      setGeneratingLyrics(false)
    }
  }

  const generateMusic = async () => {
    const lyricsText = selectedLyrics || lyrics
    if (!lyricsText.trim()) {
      toast.error('请先输入或生成歌词')
      return
    }
    setGeneratingMusic(true)
    setMusicResult(null)
    try {
      const form = new FormData()
      form.append('lyrics', lyricsText)
      form.append('style', style)
      form.append('mood', mood)
      form.append('duration', musicDuration)
      const res = await api.post('/api/music-factory/music/generate', form, { timeout: 120000 })
      setMusicResult(res.data)
      toast.info(res.data.message || '音乐任务已提交')
    } catch (e) {
      toast.error(`生成音乐失败：${e.message}`)
    } finally {
      setGeneratingMusic(false)
    }
  }

  const generateTts = async () => {
    if (!ttsText.trim()) {
      toast.error('请输入文本')
      return
    }
    setGeneratingTts(true)
    setTtsResult(null)
    try {
      const form = new FormData()
      form.append('lyrics', ttsText)
      form.append('voice', ttsVoice)
      form.append('style', style)
      const res = await api.post('/api/music-factory/tts/sing', form, { timeout: 120000 })
      const data = res.data
      setTtsResult(data)
      if (data.url) {
        toast.success('人声合成完成')
        fetchAudios()
      }
    } catch (e) {
      toast.error(`生成人声失败：${e.message}`)
    } finally {
      setGeneratingTts(false)
    }
  }

  const handlePlayAudio = (audio) => {
    if (playingAudio === audio.filename) {
      audioRef.current?.pause()
      setPlayingAudio(null)
    } else {
      setPlayingAudio(audio.filename)
      setTimeout(() => audioRef.current?.play(), 100)
    }
  }

  const handleCopyLyrics = async () => {
    const ok = await copyToClipboard(lyrics)
    if (ok) toast.success('已复制到剪贴板')
    else toast.error('复制失败')
  }

  const handleDownload = async (audio) => {
    try {
      const res = await fetch(absUrl(audio.url))
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = audio.filename
      a.click()
      URL.revokeObjectURL(url)
      toast.success('已开始下载')
    } catch (e) {
      toast.error(`下载失败：${e.message}`)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/music-factory/delete/${deleteTarget.filename}`)
      toast.success('已删除')
      if (playingAudio === deleteTarget.filename) setPlayingAudio(null)
      setDeleteTarget(null)
      fetchAudios()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const statsCards = [
    { label: '音乐作品', value: stats.total_tracks, color: 'text-purple-600' },
    { label: 'API 状态', value: stats.api_configured ? '已配置' : '未配置', color: stats.api_configured ? 'text-green-600' : 'text-red-600' },
    { label: '功能模块', value: 3, color: 'text-blue-600' },
    { label: '歌词生成', value: lyrics ? '已生成' : '-', color: 'text-orange-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="音乐工厂"
        description="生成歌词、创作音乐、合成虚拟人声"
        icon={Music}
        iconColor="from-purple-500 to-pink-500"
        actions={
          <Button variant="secondary" icon={RefreshCw} onClick={() => { fetchStats(); fetchAudios() }}>
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

      {/* 标签页 */}
      <div className="flex gap-2 border-b border-gray-200">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              activeTab === tab.key ? 'bg-purple-100 text-purple-700' : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* 歌词生成 */}
      {activeTab === 'lyrics' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-500" />
              AI 歌词创作
            </h2>
            <button
              onClick={() => {
                const preset = PRESET_THEMES[Math.floor(Math.random() * PRESET_THEMES.length)]
                setTheme(preset.text)
                setStyle(preset.style)
              }}
              className="text-sm text-purple-600 hover:text-purple-700 flex items-center gap-1"
            >
              <Wand2 className="w-4 h-4" />
              随机主题
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">歌曲主题 <span className="text-red-500">*</span></label>
              <input
                type="text" value={theme}
                onChange={(e) => { setTheme(e.target.value); setLyricsError('') }}
                placeholder="例如：夏日海滩旅行、星空下的告白..."
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              />
              {lyricsError && <p className="mt-1 text-sm text-red-500">{lyricsError}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none">
                {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">语言</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none">
                <option value="zh">中文</option>
                <option value="en">英文</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">长度</label>
              <select value={length} onChange={(e) => setLength(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none">
                {LENGTHS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-sm text-gray-500">快捷主题:</span>
            {PRESET_THEMES.map((preset, i) => (
              <button key={i} onClick={() => { setTheme(preset.text); setStyle(preset.style) }}
                className="text-xs px-3 py-1 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-full transition-colors">
                {preset.text}
              </button>
            ))}
          </div>

          <Button variant="gradient" size="lg" icon={Sparkles} loading={generatingLyrics} disabled={!theme.trim()} onClick={generateLyrics} className="w-full">
            {generatingLyrics ? '正在创作歌词...' : '生成歌词'}
          </Button>

          {lyrics && (
            <div className="mt-4 p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl border border-purple-100">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-purple-500" />
                  生成结果
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" icon={Copy} onClick={handleCopyLyrics}>复制</Button>
                  <Button variant="success" size="sm" onClick={() => { setSelectedLyrics(lyrics); setActiveTab('music'); toast.success('已带入音乐生成') }}>
                    用于音乐生成
                  </Button>
                </div>
              </div>
              <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono leading-relaxed max-h-96 overflow-y-auto">
                {lyrics}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* 音乐生成 */}
      {activeTab === 'music' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Disc className="w-5 h-5 text-purple-500" />
            AI 音乐创作
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">歌词内容 <span className="text-red-500">*</span></label>
            <textarea
              value={selectedLyrics} onChange={(e) => setSelectedLyrics(e.target.value)}
              placeholder="粘贴歌词或使用歌词生成器创作的歌词..."
              rows={8}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
            />
            {lyrics && (
              <button onClick={() => setSelectedLyrics(lyrics)} className="mt-2 text-sm text-purple-600 hover:text-purple-700 flex items-center gap-1">
                <Wand2 className="w-4 h-4" />
                使用刚才生成的歌词
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none">
                {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">情感基调</label>
              <select value={mood} onChange={(e) => setMood(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none">
                {MOODS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">时长（秒）: {musicDuration}s</label>
            <input type="range" min="15" max="120" value={musicDuration}
              onChange={(e) => setMusicDuration(Number(e.target.value))} className="w-full accent-purple-500" />
            <div className="flex justify-between text-xs text-gray-400">
              <span>15s</span>
              <span>120s</span>
            </div>
          </div>

          <Button variant="gradient" size="lg" icon={Sparkles} loading={generatingMusic}
            disabled={!selectedLyrics.trim()} onClick={generateMusic} className="w-full">
            {generatingMusic ? '正在创作音乐...' : '生成音乐'}
          </Button>

          {musicResult && (
            <div className={`p-4 rounded-xl ${
              musicResult.status === 'pending' ? 'bg-blue-50 border border-blue-200' :
              musicResult.status === 'error' ? 'bg-red-50 border border-red-200' :
              'bg-purple-50 border border-purple-200'
            }`}>
              <div className="flex items-center gap-2">
                <Volume2 className="w-5 h-5 text-purple-600 flex-shrink-0" />
                <span className="text-sm text-gray-700">
                  {musicResult.message || '音乐正在生成中，请稍候...'}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 虚拟人声 */}
      {activeTab === 'tts' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-purple-500" />
            AI 虚拟人声
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">文本内容 <span className="text-red-500">*</span></label>
            <textarea
              value={ttsText} onChange={(e) => setTtsText(e.target.value)}
              placeholder="输入要合成的文本，支持歌词、诗歌、对话..."
              rows={4}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
            />
            {lyrics && (
              <button onClick={() => setTtsText(lyrics)} className="mt-2 text-sm text-purple-600 hover:text-purple-700 flex items-center gap-1">
                <Wand2 className="w-4 h-4" />
                使用歌词内容
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">声音类型</label>
              <select value={ttsVoice} onChange={(e) => setTtsVoice(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none">
                {VOICES.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select value={style} onChange={(e) => setStyle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none">
                {STYLES.slice(0, 4).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
          </div>

          <Button variant="gradient" size="lg" icon={Mic} loading={generatingTts}
            disabled={!ttsText.trim()} onClick={generateTts} className="w-full">
            {generatingTts ? '正在合成...' : '生成人声'}
          </Button>

          {ttsResult?.url && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-xl">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium text-gray-700">人声合成完成</span>
              </div>
              <audio controls src={absUrl(ttsResult.url)} className="w-full" />
            </div>
          )}

          {ttsResult?.status === 'not_supported' && (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
              <div className="flex items-center gap-2">
                <span className="text-sm text-yellow-700">{ttsResult.message}</span>
              </div>
            </div>
          )}
          {ttsResult?.status === 'error' && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
              <div className="flex items-center gap-2">
                <span className="text-sm text-red-700">{ttsResult.message}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 音乐库 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Headphones className="w-5 h-5 text-purple-500" />
          我的音乐库 ({audios.length})
        </h2>
        {loading ? (
          <SkeletonList count={4} />
        ) : error ? (
          <ErrorState message={`加载失败：${error.message}`} onRetry={fetchAudios} />
        ) : audios.length === 0 ? (
          <Empty icon={Headphones} title="暂无音乐" description="生成歌词或合成人声后，作品会出现在这里" />
        ) : (
          <div className="space-y-2">
            {audios.map((audio) => (
              <div key={audio.filename} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <button
                    onClick={() => handlePlayAudio(audio)}
                    className="w-10 h-10 rounded-full bg-purple-100 hover:bg-purple-200 flex items-center justify-center transition-colors flex-shrink-0"
                  >
                    {playingAudio === audio.filename ? (
                      <Pause className="w-5 h-5 text-purple-600" />
                    ) : (
                      <Play className="w-5 h-5 text-purple-600 ml-0.5" />
                    )}
                  </button>
                  <div className="min-w-0">
                    <div className="font-medium text-gray-900 truncate">{audio.filename.replace('.mp3', '').replace('music_', '')}</div>
                    <div className="text-sm text-gray-500">{formatBytes(audio.size)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button onClick={() => handleDownload(audio)} className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors" title="下载">
                    <Download className="w-4 h-4" />
                  </button>
                  <button onClick={() => setDeleteTarget(audio)} className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="删除">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        {/* 单例音频播放器 */}
        {playingAudio && (
          <audio
            ref={audioRef}
            src={absUrl(audios.find((a) => a.filename === playingAudio)?.url)}
            autoPlay
            onEnded={() => setPlayingAudio(null)}
            className="hidden"
          />
        )}
      </div>

      {/* 使用指南 */}
      <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-4 border border-purple-100">
        <h3 className="font-medium text-purple-900 mb-3 flex items-center gap-2">
          <Music2 className="w-5 h-5" />
          使用指南
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">歌词生成</div>
            <div className="text-sm text-gray-600 mt-1">AI 根据你的主题和风格创作完整歌词</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">音乐生成</div>
            <div className="text-sm text-gray-600 mt-1">基于歌词生成完整音乐作品（开发中）</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">虚拟人声</div>
            <div className="text-sm text-gray-600 mt-1">TTS 合成人声（需要 TTS API 支持）</div>
          </div>
        </div>
      </div>

      {/* 删除确认 */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除"
        message={`确定要删除「${deleteTarget?.filename}」吗？此操作不可撤销。`}
        confirmLabel="确认删除"
      />
    </div>
  )
}
