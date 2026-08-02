import React, { useState, useEffect, useRef } from 'react'
import { 
  Music, FileText, Mic, Play, Pause, Download, 
  Loader, Sparkles, RefreshCw, Clock, Type, Palette,
  Headphones, Music2, Disc, Radio, Volume2, Wand2,
  DownloadCloud, Trash2
} from 'lucide-react'

const API_BASE = 'http://localhost:8888'

// 预设歌词主题
const PRESET_THEMES = [
  { text: '夏日海滩旅行', style: 'pop' },
  { text: '星空下的告白', style: 'ballad' },
  { text: '城市霓虹灯', style: 'rap' },
  { text: '春天的约定', style: 'pop' },
  { text: '深夜食堂', style: 'jazz' },
  { text: '青春奋斗', style: 'rock' },
]

export default function MusicFactoryPage() {
  const [activeTab, setActiveTab] = useState('lyrics')
  const [stats, setStats] = useState({ total_tracks: 0, api_configured: false })
  const [audios, setAudios] = useState([])
  
  // 歌词生成状态
  const [theme, setTheme] = useState('')
  const [style, setStyle] = useState('pop')
  const [language, setLanguage] = useState('zh')
  const [length, setLength] = useState('medium')
  const [lyrics, setLyrics] = useState('')
  const [isGeneratingLyrics, setIsGeneratingLyrics] = useState(false)
  const [lyricsError, setLyricsError] = useState('')
  
  // 音乐生成状态
  const [selectedLyrics, setSelectedLyrics] = useState('')
  const [mood, setMood] = useState('happy')
  const [musicDuration, setMusicDuration] = useState(30)
  const [isGeneratingMusic, setIsGeneratingMusic] = useState(false)
  const [musicResult, setMusicResult] = useState(null)
  
  // TTS状态
  const [ttsText, setTtsText] = useState('')
  const [ttsVoice, setTtsVoice] = useState('female')
  const [isGeneratingTts, setIsGeneratingTts] = useState(false)
  const [ttsResult, setTtsResult] = useState(null)
  
  // 音频播放器
  const [playingAudio, setPlayingAudio] = useState(null)
  const audioRef = useRef(null)

  useEffect(() => {
    loadStats()
    loadAudios()
  }, [])

  const loadStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/music-factory/stats`)
      const data = await res.json()
      setStats(data)
    } catch (e) {
      console.error('加载统计失败:', e)
    }
  }

  const loadAudios = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/music-factory/list`)
      const data = await res.json()
      setAudios(data.audios || [])
    } catch (e) {
      console.error('加载音频列表失败:', e)
    }
  }

  const generateLyrics = async () => {
    if (!theme.trim()) {
      setLyricsError('请输入歌曲主题')
      return
    }
    setLyricsError('')
    setIsGeneratingLyrics(true)
    setLyrics('')
    
    try {
      const formData = new FormData()
      formData.append('theme', theme)
      formData.append('style', style)
      formData.append('language', language)
      formData.append('length', length)

      const res = await fetch(`${API_BASE}/api/music-factory/lyrics/generate`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      
      if (data.lyrics) {
        setLyrics(data.lyrics)
        setSelectedLyrics(data.lyrics)
      } else {
        setLyricsError(data.detail?.[0]?.msg || '生成失败')
      }
    } catch (e) {
      setLyricsError('生成失败: ' + e.message)
    } finally {
      setIsGeneratingLyrics(false)
    }
  }

  const generateMusic = async () => {
    const lyricsText = selectedLyrics || lyrics
    if (!lyricsText.trim()) {
      alert('请先输入或生成歌词')
      return
    }
    setIsGeneratingMusic(true)
    setMusicResult(null)
    
    try {
      const formData = new FormData()
      formData.append('lyrics', lyricsText)
      formData.append('style', style)
      formData.append('mood', mood)
      formData.append('duration', musicDuration)

      const res = await fetch(`${API_BASE}/api/music-factory/music/generate`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      setMusicResult(data)
    } catch (e) {
      console.error('生成音乐失败:', e)
    } finally {
      setIsGeneratingMusic(false)
    }
  }

  const generateTts = async () => {
    if (!ttsText.trim()) {
      alert('请输入文本')
      return
    }
    setIsGeneratingTts(true)
    setTtsResult(null)
    
    try {
      const formData = new FormData()
      formData.append('lyrics', ttsText)
      formData.append('voice', ttsVoice)
      formData.append('style', style)

      const res = await fetch(`${API_BASE}/api/music-factory/tts/sing`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      setTtsResult(data)
      
      if (data.url) {
        loadAudios()
      }
    } catch (e) {
      console.error('生成人声失败:', e)
    } finally {
      setIsGeneratingTts(false)
    }
  }

  const handlePlayAudio = (audio) => {
    if (playingAudio === audio.filename) {
      audioRef.current?.pause()
      setPlayingAudio(null)
    } else {
      setPlayingAudio(audio.filename)
      setTimeout(() => {
        audioRef.current?.play()
      }, 100)
    }
  }

  const deleteAudio = async (filename) => {
    if (!confirm('确定删除该音频？')) return
    await fetch(`${API_BASE}/api/music-factory/delete/${filename}`, { method: 'DELETE' })
    if (playingAudio === filename) {
      setPlayingAudio(null)
    }
    loadAudios()
  }

  return (
    <div className="p-6 space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Music className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">音乐工厂</h1>
            <p className="text-gray-500">生成歌词、创作音乐、合成虚拟人声</p>
          </div>
        </div>
        <button onClick={loadAudios} className="p-2 hover:bg-gray-100 rounded-lg">
          <RefreshCw className="w-5 h-5 text-gray-600" />
        </button>
      </div>

      {/* 统计 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-2xl font-bold text-purple-600">{stats.total_tracks}</div>
          <div className="text-sm text-gray-500">音乐作品</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className={`text-2xl font-bold ${stats.api_configured ? 'text-green-600' : 'text-red-600'}`}>
            {stats.api_configured ? '已配置' : '未配置'}
          </div>
          <div className="text-sm text-gray-500">API状态</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-2xl font-bold text-blue-600">3</div>
          <div className="text-sm text-gray-500">功能模块</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-2xl font-bold text-orange-600">
            {lyrics ? '✅' : '-'}
          </div>
          <div className="text-sm text-gray-500">歌词生成</div>
        </div>
      </div>

      {/* 标签页 */}
      <div className="flex gap-2 border-b border-gray-200">
        {[
          { key: 'lyrics', label: '歌词生成', icon: FileText },
          { key: 'music', label: '音乐生成', icon: Music2 },
          { key: 'tts', label: '虚拟人声', icon: Mic },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-purple-100 text-purple-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* 歌词生成 */}
      {activeTab === 'lyrics' && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold flex items-center gap-2">
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
          
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">歌曲主题</label>
              <input
                type="text"
                value={theme}
                onChange={e => { setTheme(e.target.value); setLyricsError('') }}
                placeholder="例如：夏日海滩旅行、星空下的告白..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
              {lyricsError && <p className="mt-1 text-sm text-red-500">{lyricsError}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select
                value={style}
                onChange={e => setStyle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="pop">流行</option>
                <option value="rock">摇滚</option>
                <option value="rap">说唱</option>
                <option value="ballad">抒情</option>
                <option value="jazz">爵士</option>
                <option value="classical">古典</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">语言</label>
              <select
                value={language}
                onChange={e => setLanguage(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="zh">中文</option>
                <option value="en">英文</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">长度</label>
              <select
                value={length}
                onChange={e => setLength(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="short">短歌 (30-60秒)</option>
                <option value="medium">中歌 (2-3分钟)</option>
                <option value="long">长歌 (3-5分钟)</option>
              </select>
            </div>
          </div>

          {/* 快捷主题 */}
          <div className="flex flex-wrap gap-2">
            <span className="text-sm text-gray-500 self-center">快捷主题:</span>
            {PRESET_THEMES.map((preset, i) => (
              <button
                key={i}
                onClick={() => { setTheme(preset.text); setStyle(preset.style) }}
                className="text-xs px-3 py-1 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-full transition-colors"
              >
                {preset.text}
              </button>
            ))}
          </div>

          <button
            onClick={generateLyrics}
            disabled={isGeneratingLyrics}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isGeneratingLyrics ? <Loader className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
            {isGeneratingLyrics ? '正在创作歌词...' : '生成歌词'}
          </button>

          {lyrics && (
            <div className="mt-4 p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border border-purple-100">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-purple-500" />
                  生成结果
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(lyrics)
                      alert('已复制到剪贴板')
                    }}
                    className="text-xs px-3 py-1 bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg transition-colors"
                  >
                    复制歌词
                  </button>
                  <button
                    onClick={() => setSelectedLyrics(lyrics)}
                    className="text-xs px-3 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg transition-colors"
                  >
                    用于音乐生成
                  </button>
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
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Disc className="w-5 h-5 text-purple-500" />
            AI 音乐创作
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">歌词内容</label>
            <textarea
              value={selectedLyrics}
              onChange={e => setSelectedLyrics(e.target.value)}
              placeholder="粘贴歌词或使用歌词生成器创作的歌词..."
              rows={8}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
            />
            {lyrics && (
              <button
                onClick={() => setSelectedLyrics(lyrics)}
                className="mt-2 text-sm text-purple-600 hover:text-purple-700 flex items-center gap-1"
              >
                <Wand2 className="w-4 h-4" />
                使用刚才生成的歌词
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select
                value={style}
                onChange={e => setStyle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="pop">流行</option>
                <option value="rock">摇滚</option>
                <option value="rap">说唱</option>
                <option value="ballad">抒情</option>
                <option value="jazz">爵士</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">情感基调</label>
              <select
                value={mood}
                onChange={e => setMood(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="happy">欢快</option>
                <option value="sad">悲伤</option>
                <option value="energetic">激昂</option>
                <option value="calm">平静</option>
                <option value="romantic">浪漫</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">时长（秒）: {musicDuration}s</label>
            <input
              type="range"
              min="15"
              max="120"
              value={musicDuration}
              onChange={e => setMusicDuration(Number(e.target.value))}
              className="w-full accent-purple-500"
            />
            <div className="flex justify-between text-xs text-gray-400">
              <span>15s</span>
              <span>120s</span>
            </div>
          </div>

          <button
            onClick={generateMusic}
            disabled={isGeneratingMusic}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isGeneratingMusic ? <Loader className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
            {isGeneratingMusic ? '正在创作音乐...' : '生成音乐'}
          </button>

          {musicResult && (
            <div className={`p-4 rounded-lg ${
              musicResult.status === 'pending' ? 'bg-blue-50 border border-blue-200' :
              musicResult.status === 'error' ? 'bg-red-50 border border-red-200' :
              'bg-purple-50 border border-purple-200'
            }`}>
              <div className="flex items-center gap-2">
                {musicResult.status === 'pending' && <Loader className="w-5 h-5 animate-spin text-blue-600" />}
                {musicResult.status === 'error' && <span>❌</span>}
                {musicResult.status !== 'pending' && musicResult.status !== 'error' && <span>🎵</span>}
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
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-purple-500" />
            AI 虚拟人声
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">文本内容</label>
            <textarea
              value={ttsText}
              onChange={e => setTtsText(e.target.value)}
              placeholder="输入要合成的文本，支持歌词、诗歌、对话..."
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
            />
            {lyrics && (
              <button
                onClick={() => setTtsText(lyrics)}
                className="mt-2 text-sm text-purple-600 hover:text-purple-700 flex items-center gap-1"
              >
                <Wand2 className="w-4 h-4" />
                使用歌词内容
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">声音类型</label>
              <select
                value={ttsVoice}
                onChange={e => setTtsVoice(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="female">女声</option>
                <option value="male">男声</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select
                value={style}
                onChange={e => setStyle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="pop">流行</option>
                <option value="rock">摇滚</option>
                <option value="rap">说唱</option>
                <option value="ballad">抒情</option>
              </select>
            </div>
          </div>

          <button
            onClick={generateTts}
            disabled={isGeneratingTts}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isGeneratingTts ? <Loader className="w-5 h-5 animate-spin" /> : <Mic className="w-5 h-5" />}
            {isGeneratingTts ? '正在合成...' : '生成人声'}
          </button>

          {ttsResult?.url && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span>✅</span>
                <span className="text-sm font-medium text-gray-700">人声合成完成</span>
              </div>
              <audio 
                ref={audioRef}
                controls 
                src={`${API_BASE}${ttsResult.url}`} 
                className="w-full"
                onEnded={() => setPlayingAudio(null)}
              />
            </div>
          )}
          
          {ttsResult?.status === 'not_supported' && (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-center gap-2">
                <span>⚠️</span>
                <span className="text-sm text-yellow-700">{ttsResult.message}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 音乐库 */}
      {audios.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Headphones className="w-5 h-5 text-purple-500" />
            我的音乐库 ({audios.length})
          </h2>
          <div className="space-y-2">
            {audios.map(audio => (
              <div key={audio.filename} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="flex items-center gap-3">
                  <button 
                    onClick={() => handlePlayAudio(audio)}
                    className="w-10 h-10 rounded-full bg-purple-100 hover:bg-purple-200 flex items-center justify-center transition-colors"
                  >
                    {playingAudio === audio.filename ? (
                      <Pause className="w-5 h-5 text-purple-600" />
                    ) : (
                      <Play className="w-5 h-5 text-purple-600 ml-0.5" />
                    )}
                  </button>
                  <div>
                    <div className="font-medium text-gray-900">{audio.filename.replace('.mp3', '').replace('music_', '')}</div>
                    <div className="text-sm text-gray-500">{(audio.size / 1024).toFixed(1)} KB</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <a 
                    href={`${API_BASE}${audio.url}`} 
                    download
                    className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                    title="下载"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                  <button 
                    onClick={() => deleteAudio(audio.filename)}
                    className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 使用指南 */}
      <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-4 border border-purple-100">
        <h3 className="font-medium text-purple-900 mb-3 flex items-center gap-2">
          <Music2 className="w-5 h-5" />
          使用指南
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">📝 歌词生成</div>
            <div className="text-sm text-gray-600 mt-1">AI 根据你的主题和风格创作完整歌词</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">🎵 音乐生成</div>
            <div className="text-sm text-gray-600 mt-1">基于歌词生成完整音乐作品（开发中）</div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">🎤 虚拟人声</div>
            <div className="text-sm text-gray-600 mt-1">TTS 合成人声（需要 TTS API 支持）</div>
          </div>
        </div>
        <div className="mt-3 text-sm text-purple-700">
          💡 当前歌词生成功能已可用，音乐生成和虚拟人声正在对接更多 API
        </div>
      </div>
      
      {/* 隐藏音频播放器 */}
      <audio ref={audioRef} onEnded={() => setPlayingAudio(null)} />
    </div>
  )
}
