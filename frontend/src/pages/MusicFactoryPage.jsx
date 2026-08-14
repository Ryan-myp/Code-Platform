import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Music,
  FileText,
  Mic,
  Play,
  Pause,
  Download,
  Sparkles,
  RefreshCw,
  Wand2,
  Trash2,
  Headphones,
  Music2,
  Disc,
  Volume2,
  Copy,
  Package,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatBytes, copyToClipboard } from '../lib/format'
import {
  Button,
  Badge,
  Empty,
  SkeletonList,
  ErrorState,
  PageHeader,
  ConfirmDialog,
  Modal,
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

// v20：歌词段落解析（与后端 parse_lyrics_sections 同构，兼容中英文/全角标注）
// 注意：字符类开头 [ 必须转义（无转义时 V8 不把它当作内容字符，eslint no-useless-escape 此处为误报）
/* eslint-disable-next-line no-useless-escape -- 字符类中 [ 需显式转义才能作为内容 */
const SECTION_TAG_RE = /^\s*[\[［（(【]\s*([A-Za-z-]+(?:\s*\d*)?|副歌|主歌|桥段|桥|尾声|前奏|间奏|说唱|预副歌)\s*[\]［（(【］）)】]\s*$/
const SECTION_TITLES = {
  CHORUS: 'Chorus',
  VERSE: 'Verse',
  BRIDGE: 'Bridge',
  OUTRO: 'Outro',
  INTRO: 'Intro',
  'PRE-CHORUS': 'Pre-Chorus',
  RAP: 'Rap',
  副歌: 'Chorus',
  主歌: 'Verse',
  桥段: 'Bridge',
  桥: 'Bridge',
  尾声: 'Outro',
  前奏: 'Intro',
  间奏: 'Interlude',
  说唱: 'Rap',
  预副歌: 'Pre-Chorus',
}

export function parseLyricsSections(text) {
  if (!text || !String(text).trim()) return []
  const sections = []
  let current = null
  const normalizeTitle = (raw) => {
    const exact = SECTION_TITLES[raw]
    if (exact) return exact
    // "VERSE 1" / "CHORUS 2" 等带序号形式（保留序号）
    for (const k of ['PRE-CHORUS', 'VERSE', 'CHORUS', 'BRIDGE', 'OUTRO', 'INTRO']) {
      if (raw.startsWith(k)) return SECTION_TITLES[k] + raw.slice(k.length)
    }
    return raw.replace(/^\w/, (c) => c.toUpperCase())
  }
  for (const ln of String(text).split('\n')) {
    const m = ln.match(SECTION_TAG_RE)
    if (m) {
      if (current) sections.push(current)
      const raw = m[1].trim().toUpperCase()
      const title = normalizeTitle(raw)
      current = { title, lines: [], isHook: title.toUpperCase().includes('CHORUS') || title.toUpperCase().includes('HOOK') }
      continue
    }
    if (!current) current = { title: '歌词', lines: [], isHook: false }
    if (ln.trim()) current.lines.push(ln.trim())
  }
  if (current && current.lines.length) sections.push(current)
  return sections
}

// v20：歌词卡片（段落徽章 + Hook 行强调 + 行渲染）
const SECTION_BADGE_STYLES = {
  Chorus: 'bg-purple-100 text-purple-700 border-purple-200',
  Verse: 'bg-blue-50 text-blue-600 border-blue-100',
  Bridge: 'bg-amber-50 text-amber-600 border-amber-100',
  'Pre-Chorus': 'bg-fuchsia-50 text-fuchsia-600 border-fuchsia-100',
}

export function LyricsCard({ text, className = '' }) {
  const sections = parseLyricsSections(text)
  if (!sections.length) return null
  return (
    <div className={`space-y-3 ${className}`} data-testid="lyrics-card">
      {sections.map((sec, i) => (
        <div
          key={i}
          className="rounded-xl border border-gray-100 bg-white/70 shadow-sm overflow-hidden"
        >
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50/80 border-b border-gray-100">
            <span
              className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
                SECTION_BADGE_STYLES[sec.title] || 'bg-gray-100 text-gray-600 border-gray-200'
              }`}
            >
              {sec.title}
            </span>
            {sec.isHook && (
              <span className="text-[10px] text-purple-500 font-medium">🎵 记忆点 Hook</span>
            )}
          </div>
          <div className="px-4 py-2.5">
            {sec.lines.map((l, j) => (
              <div
                key={j}
                className={`py-0.5 text-sm leading-relaxed ${
                  sec.isHook && j === 0
                    ? 'text-purple-800 font-semibold bg-purple-50/80 rounded-md px-2 -mx-2 my-0.5'
                    : 'text-gray-700'
                }`}
              >
                {l}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

const PRESET_CATEGORIES = [
  {
    name: '爱情情感',
    icon: '💕',
    themes: [
      { text: '星空下的告白', style: 'ballad' },
      { text: '春天的约定', style: 'pop' },
      { text: '分手后的雨天', style: 'ballad' },
      { text: '第一次心动', style: 'pop' },
    ],
  },
  {
    name: '生活场景',
    icon: '🌴',
    themes: [
      { text: '夏日海滩旅行', style: 'pop' },
      { text: '深夜食堂', style: 'jazz' },
      { text: '周末的早晨', style: 'jazz' },
      { text: '城市漫步', style: 'pop' },
    ],
  },
  {
    name: '励志奋斗',
    icon: '🔥',
    themes: [
      { text: '青春奋斗', style: 'rock' },
      { text: '追梦不放弃', style: 'rock' },
      { text: '城市霓虹灯', style: 'rap' },
      { text: '逆风翻盘', style: 'rap' },
    ],
  },
  {
    name: '自然意境',
    icon: '🌿',
    themes: [
      { text: '山间清晨的雾气', style: 'classical' },
      { text: '月光下的湖泊', style: 'classical' },
      { text: '秋天的落叶', style: 'ballad' },
      { text: '雨后彩虹', style: 'pop' },
    ],
  },
  {
    name: '节日庆典',
    icon: '🎉',
    themes: [
      { text: '春节团圆夜', style: 'pop' },
      { text: '圣诞雪夜', style: 'classical' },
      { text: '毕业季不说再见', style: 'ballad' },
      { text: '生日派对狂欢', style: 'electronic' },
    ],
  },
  {
    name: '国风古韵',
    icon: '🏮',
    themes: [
      { text: '江南烟雨', style: 'classical' },
      { text: '长安月下', style: 'folk' },
      { text: '山河故人', style: 'folk' },
      { text: '琴瑟和鸣', style: 'classical' },
    ],
  },
]

const STYLES = [
  { value: 'pop', label: '流行' },
  { value: 'rock', label: '摇滚' },
  { value: 'rap', label: '说唱' },
  { value: 'ballad', label: '抒情' },
  { value: 'jazz', label: '爵士' },
  { value: 'classical', label: '古典' },
  { value: 'folk', label: '民谣' },
  { value: 'electronic', label: '电子' },
]

const INSTRUMENTS = [
  { value: '', label: '默认' },
  { value: 'piano', label: '钢琴' },
  { value: 'guitar', label: '吉他' },
  { value: 'violin', label: '小提琴' },
  { value: 'drums', label: '鼓' },
  { value: 'synth', label: '合成器' },
  { value: 'erhu', label: '二胡' },
  { value: 'pipa', label: '琵琶' },
  { value: 'guqin', label: '古琴' },
  { value: 'bamboo_flute', label: '竹笛' },
  { value: 'saxophone', label: '萨克斯' },
  { value: 'trumpet', label: '小号' },
  { value: 'cello', label: '大提琴' },
  { value: 'harp', label: '竖琴' },
  { value: 'accordion', label: '手风琴' },
  { value: 'ukulele', label: '尤克里里' },
]

const MOODS = [
  { value: 'happy', label: '欢快' },
  { value: 'sad', label: '悲伤' },
  { value: 'energetic', label: '激昂' },
  { value: 'calm', label: '平静' },
  { value: 'romantic', label: '浪漫' },
  { value: 'nostalgic', label: '怀旧' },
  { value: 'epic', label: '史诗' },
  { value: 'dreamy', label: '梦幻' },
  { value: 'mysterious', label: '神秘' },
  { value: 'warm', label: '温馨' },
  { value: 'hopeful', label: '希望' },
  { value: 'playful', label: '俏皮' },
]

const LENGTHS = [
  { value: 'short', label: '短歌 (30-60秒)' },
  { value: 'medium', label: '中歌 (2-3分钟)' },
  { value: 'long', label: '长歌 (3-5分钟)' },
]

// v15：歌词押韵/段落结构参数
const RHYMES = [
  { value: 'natural', label: '自然押韵（推荐）' },
  { value: 'strict', label: '严格押韵（说唱/快歌）' },
  { value: 'soft', label: '弱押韵（意境优先）' },
]

const STRUCTURES = [
  { value: 'verse_chorus', label: '主歌+副歌' },
  { value: 'verse_chorus_bridge', label: '主歌+副歌+桥段' },
  { value: 'free', label: '自由段落' },
  { value: 'rap_verse', label: '说唱+Hook' },
]

const VOICES = [
  { value: 'female', label: '女声' },
  { value: 'male', label: '男声' },
]

const TTS_SPEEDS = [
  { value: '0.8', label: '慢速' },
  { value: '1.0', label: '正常' },
  { value: '1.2', label: '快速' },
  { value: '1.5', label: '极速' },
]

const LYRICS_TEMPLATES = [
  {
    name: '标准结构',
    icon: '🎵',
    structure:
      '[Verse 1]\n[主歌第一段内容]\n\n[Chorus]\n[副歌内容，重复性强]\n\n[Verse 2]\n[主歌第二段内容]\n\n[Chorus]\n[副歌重复]\n\n[Bridge]\n[桥段，情感升华]\n\n[Chorus]\n[副歌最后重复]',
  },
  {
    name: '简单结构',
    icon: '🎶',
    structure:
      '[Verse 1]\n[主歌内容]\n\n[Chorus]\n[副歌内容]\n\n[Verse 2]\n[主歌内容]\n\n[Chorus]\n[副歌重复]',
  },
  {
    name: '说唱结构',
    icon: '🎤',
    structure:
      '[Intro]\n[开场白]\n\n[Verse 1]\n[说唱第一段]\n\n[Hook]\n[记忆点/副歌]\n\n[Verse 2]\n[说唱第二段]\n\n[Hook]\n[记忆点重复]\n\n[Outro]\n[结尾]',
  },
]

const TABS = [
  { key: 'lyrics', label: '歌词生成', icon: FileText },
  { key: 'music', label: '音乐生成', icon: Music2 },
  { key: 'tts', label: '人声合成', icon: Mic },
]

export default function MusicFactoryPage() {
  const toast = useToast()
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿）
  const [inputs, setInputs] = usePersistentToolState('music_factory_inputs', {
    activeTab: 'lyrics',
    theme: '',
    style: 'pop',
    language: 'zh',
    length: 'medium',
    mood: 'happy',
    rhyme: 'natural',
    structure: 'verse_chorus',
    musicDuration: 30,
    musicVoice: 'female',
  })
  const {
    activeTab,
    theme,
    style,
    language,
    length,
    mood,
    rhyme,
    structure,
    musicDuration,
    musicVoice,
  } = inputs
  const setActiveTab = (v) => setInputs((p) => ({ ...p, activeTab: v }))
  const setTheme = (v) => setInputs((p) => ({ ...p, theme: v ?? '' }))
  const setStyle = (v) => setInputs((p) => ({ ...p, style: v }))
  const setLanguage = (v) => setInputs((p) => ({ ...p, language: v }))
  const setLength = (v) => setInputs((p) => ({ ...p, length: v }))
  const setMood = (v) => setInputs((p) => ({ ...p, mood: v }))
  const setRhyme = (v) => setInputs((p) => ({ ...p, rhyme: v }))
  const setStructure = (v) => setInputs((p) => ({ ...p, structure: v }))
  const setMusicVoice = (v) => setInputs((p) => ({ ...p, musicVoice: v }))
  const setMusicDuration = (v) => setInputs((p) => ({ ...p, musicDuration: v }))
  const [stats, setStats] = useState({ total_tracks: 0, api_configured: false })
  const [audios, setAudios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 歌词示例（来自 /api/music-factory/lyrics/examples）
  const [lyricExamples, setLyricExamples] = useState({})

  // 歌词
  const [lyrics, setLyrics] = useState('')
  const [generatingLyrics, setGeneratingLyrics] = useState(false)
  const [lyricsError, setLyricsError] = useState('')

  // 音乐
  const [selectedLyrics, setSelectedLyrics] = useState('')
  const [generatingMusic, setGeneratingMusic] = useState(false)
  const [musicResult, setMusicResult] = useState(null)
  // v22 音乐场景模板库：场景化配方（风格/情绪/歌词示例/时长/BPM/乐器/结构）
  const [musicTpls, setMusicTpls] = useState([])
  const [musicTplId, setMusicTplId] = useState('')
  const [musicTplInfo, setMusicTplInfo] = useState(null) // 配方详情弹窗
  const [musicTplCat, setMusicTplCat] = useState('全部')

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

  // 发布包（商业化 v14）：单曲打包为可提交网易云/腾讯/抖音音乐人的成套物料
  const [packAudio, setPackAudio] = useState(null)
  const [packTitle, setPackTitle] = useState('')
  const [packArtist, setPackArtist] = useState('')
  const [packGenre, setPackGenre] = useState('')
  // v15：发布包封面自定义上传（File + dataURL 预览）
  const [packCoverFile, setPackCoverFile] = useState(null)
  const [packCoverPreview, setPackCoverPreview] = useState('')
  const [packing, setPacking] = useState(false)
  // 异步任务进度（task_id + 轮询进度）
  const [genTask, setGenTask] = useState(null)
  const { submitTask } = useAsyncTask()
  const { history: genHistory, add: addGenHistory, remove: removeGenHistory, clear: clearGenHistory } =
    useToolHistory('music_factory_history_v1', 30)

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/api/music-factory/stats')
      setStats(res.data)
    } catch {
      /* 静默 */
    }
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
    api
      .get('/api/music-factory/lyrics/examples')
      .then((res) => setLyricExamples(res.data?.examples || {}))
      .catch(() => {
        /* 静默 */
      })
    // v22 音乐场景模板
    api
      .get('/api/music-scene-templates/list')
      .then((res) => setMusicTpls(res.data?.items || []))
      .catch(() => {
        /* 静默 */
      })
  }, [fetchStats, fetchAudios])

  const generateLyrics = async () => {
    if (!theme.trim()) {
      setLyricsError('请输入歌曲主题')
      return
    }
    setLyricsError('')
    setGeneratingLyrics(true)
    setLyrics('')
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const form = new FormData()
    form.append('theme', theme)
    form.append('style', style)
    form.append('language', language)
    form.append('length', length)
    form.append('mood', mood)
    form.append('rhyme', rhyme)
    form.append('structure', structure)
    await submitTask('/api/music-factory/lyrics/generate', form, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: (data) => {
        if (data.lyrics) {
          setLyrics(data.lyrics)
          setSelectedLyrics(data.lyrics)
          toast.success('歌词生成完成')
        } else {
          setLyricsError('生成失败')
        }
        setGeneratingLyrics(false)
      },
      onError: (e) => {
        setGeneratingLyrics(false)
        setLyricsError(`生成失败：${e.message}`)
      },
    })
  }

  const generateMusic = async () => {
    const lyricsText = selectedLyrics || lyrics
    if (!lyricsText.trim()) {
      toast.error('请先输入或生成歌词')
      return
    }
    setGeneratingMusic(true)
    setMusicResult(null)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const form = new FormData()
    form.append('lyrics', lyricsText)
    form.append('style', style)
    form.append('mood', mood)
    form.append('voice', musicVoice)
    form.append('theme', theme || 'AI 音乐作品')
    form.append('duration', musicDuration)
    if (musicTplId) form.append('template_id', musicTplId)
    await submitTask('/api/music-factory/music/generate', form, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: (data) => {
        setMusicResult(data)
        if (data.url) {
          addGenHistory({
            type: '音乐',
            theme: theme || 'AI 音乐作品',
            style,
            mood,
            content: `${(theme || 'AI 音乐作品').slice(0, 40)} · ${style} · ${mood}`,
          })
          toast.success('歌曲生成完成，可以听了！')
          fetchAudios()
        }
        setGeneratingMusic(false)
      },
      onError: (e) => {
        setGeneratingMusic(false)
        toast.error(`生成音乐失败：${e.message}`)
      },
    })
  }

  const generateTts = async () => {
    if (!ttsText.trim()) {
      toast.error('请输入文本')
      return
    }
    setGeneratingTts(true)
    setTtsResult(null)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const form = new FormData()
    form.append('lyrics', ttsText)
    form.append('voice', ttsVoice)
    form.append('style', style)
    await submitTask('/api/music-factory/tts/sing', form, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: (data) => {
        setTtsResult(data)
        if (data.url) {
          toast.success('人声朗读合成完成')
          fetchAudios()
        }
        setGeneratingTts(false)
      },
      onError: (e) => {
        setGeneratingTts(false)
        toast.error(`生成人声失败：${e.message}`)
      },
    })
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

  // 音乐发布包：mp3 + wav 母带（44.1kHz/16bit）+ flac 无损 + 封面 + lrc/txt 歌词 + 质量报告
  const downloadPublishPack = async () => {
    if (!packAudio) return
    setPacking(true)
    try {
      const fd = new FormData()
      fd.append('audio_id', packAudio.filename)
      fd.append('song_title', packTitle.trim() || packAudio.title || 'AI 音乐作品')
      fd.append('artist', packArtist.trim())
      fd.append('genre', packGenre.trim())
      if (packCoverFile) fd.append('cover_image', packCoverFile)
      const res = await api.post('/api/music-factory/publish-pack', fd, {
        responseType: 'blob',
        timeout: 300000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `music_publish_pack_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setPackAudio(null)
      setPackCoverFile(null)
      setPackCoverPreview('')
      toast.success('音乐发布包已生成：mp3 + wav 母带 + flac 无损 + 封面 + 歌词 + 质量报告')
    } catch (e) {
      toast.error(`发布包生成失败：${e.message}`)
    } finally {
      setPacking(false)
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
    {
      label: 'API 状态',
      value: stats.api_configured ? '已配置' : '未配置',
      color: stats.api_configured ? 'text-green-600' : 'text-red-600',
    },
    {
      label: 'AI 引擎',
      value: stats.engine?.acestep_ok
        ? 'ACE-Step 大模型'
        : stats.engine?.cosyvoice_ok
          ? '本地真歌声'
          : '本地引擎',
      color: stats.engine?.acestep_ok ? 'text-green-600' : 'text-purple-600',
    },
    { label: '歌词生成', value: lyrics ? '已生成' : '-', color: 'text-orange-600' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="音乐工厂"
        description="生成歌词、创作歌曲、AI 歌手演唱"
        icon={Music}
        iconColor="from-purple-500 to-pink-500"
        actions={
          <Button
            variant="secondary"
            icon={RefreshCw}
            onClick={() => {
              fetchStats()
              fetchAudios()
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

      {/* 标签页 */}
      <div className="flex gap-2 border-b border-gray-200">
        {TABS.map((tab) => (
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
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-500" />
              AI 歌词创作
            </h2>
            <button
              onClick={() => {
                const allThemes = PRESET_CATEGORIES.flatMap((c) => c.themes)
                const preset = allThemes[Math.floor(Math.random() * allThemes.length)]
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                歌曲主题 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={theme}
                onChange={(e) => {
                  setTheme(e.target.value)
                  setLyricsError('')
                }}
                placeholder="例如：夏日海滩旅行、星空下的告白..."
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
              />
              {lyricsError && <p className="mt-1 text-sm text-red-500">{lyricsError}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {STYLES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">语言</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                <option value="zh">中文</option>
                <option value="en">英文</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">长度</label>
              <select
                value={length}
                onChange={(e) => setLength(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {LENGTHS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">押韵（v15）</label>
              <select
                value={rhyme}
                onChange={(e) => setRhyme(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {RHYMES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">段落结构（v15）</label>
              <select
                value={structure}
                onChange={(e) => setStructure(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {STRUCTURES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-sm text-gray-500">快捷主题:</span>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {PRESET_CATEGORIES.map((cat, ci) => (
                <div key={ci} className="relative group">
                  <button className="w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-gray-200 hover:border-purple-300 hover:bg-purple-50/50 transition-all text-left">
                    <span className="text-sm">{cat.icon}</span>
                    <span className="text-xs text-gray-700">{cat.name}</span>
                  </button>
                  <div className="absolute z-10 top-full left-0 mt-1 w-48 bg-white rounded-xl border border-gray-200 shadow-lg p-1.5 space-y-0.5 hidden group-hover:block">
                    {cat.themes.map((preset, pi) => (
                      <button
                        key={pi}
                        onClick={() => {
                          setTheme(preset.text)
                          setStyle(preset.style)
                        }}
                        className="w-full text-left text-xs px-2 py-1.5 rounded-lg hover:bg-purple-50 text-gray-600 transition-colors"
                      >
                        {preset.text}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 歌词结构模板 */}
          <div>
            <span className="text-sm text-gray-500">歌词结构模板:</span>
            <div className="flex flex-wrap gap-2 mt-1">
              {LYRICS_TEMPLATES.map((tpl, i) => (
                <button
                  key={i}
                  onClick={() => setLyrics(tpl.structure)}
                  className="text-xs px-3 py-1 bg-gray-100 hover:bg-purple-100 text-gray-700 rounded-full transition-colors flex items-center gap-1"
                >
                  <span>{tpl.icon}</span> {tpl.name}
                </button>
              ))}
            </div>
          </div>

          {/* 歌词示例（云端） */}
          {Object.keys(lyricExamples).length > 0 && (
            <div>
              <span className="text-sm text-gray-500">歌词示例:</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {Object.entries(lyricExamples).map(([key, text]) => (
                  <button
                    key={key}
                    onClick={() => {
                      setLyrics(text)
                      setSelectedLyrics(text)
                      toast.success('已载入示例歌词')
                    }}
                    className="text-xs px-3 py-1 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-full transition-colors border border-purple-100"
                  >
                    {key === 'love'
                      ? '❤️ 爱情'
                      : key === 'nature'
                        ? '🌿 自然'
                        : key === 'dream'
                          ? '✨ 梦想'
                          : key}
                  </button>
                ))}
              </div>
            </div>
          )}

          <Button
            variant="gradient"
            size="lg"
            icon={Sparkles}
            loading={generatingLyrics}
            disabled={!theme.trim()}
            onClick={generateLyrics}
            className="w-full"
          >
            {generatingLyrics ? '生成任务执行中（后台）…' : '生成歌词'}
          </Button>
          {generatingLyrics && genTask && (
            <div className="rounded-lg bg-purple-50 border border-purple-100 px-3 py-2 mt-2">
              <div className="flex items-center gap-2 text-xs text-purple-700">
                <Sparkles className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
              </div>
              <div className="mt-1.5 h-1.5 bg-purple-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all"
                  style={{ width: `${genTask.progress || 0}%` }}
                />
              </div>
              <p className="mt-1 text-[11px] text-gray-400">
                任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
              </p>
            </div>
          )}

          {lyrics && (
            <div className="mt-4 p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl border border-purple-100">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-purple-500" />
                  生成结果
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" icon={Copy} onClick={handleCopyLyrics}>
                    复制
                  </Button>
                  <Button
                    variant="success"
                    size="sm"
                    onClick={() => {
                      setSelectedLyrics(lyrics)
                      setActiveTab('music')
                      toast.success('已带入音乐生成')
                    }}
                  >
                    用于音乐生成
                  </Button>
                </div>
              </div>
              <LyricsCard text={lyrics} className="max-h-96 overflow-y-auto pr-1" />
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

          {/* v22 音乐场景模板库：选场景自动填充专业配方（风格/情绪/歌词/时长/BPM） */}
          {musicTpls.length > 0 && (
            <div className="rounded-2xl border border-purple-100 bg-gradient-to-br from-purple-50/70 to-pink-50/40 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  🎼 音乐场景模板
                  <span className="text-xs text-gray-400 font-normal ml-2">
                    按使用场景选配方：风格 / 情绪 / 歌词 / 时长 / BPM 自动填充，不懂乐理也能出专业级成品
                  </span>
                </label>
                {musicTpls.some((t) => t.id === musicTplId) && (
                  <button
                    onClick={async () => {
                      try {
                        const res = await api.get(`/api/music-scene-templates/${musicTplId}`)
                        setMusicTplInfo(res.data)
                      } catch {
                        toast.error('配方加载失败')
                      }
                    }}
                    className="text-xs px-2.5 py-1 rounded-lg border border-purple-200 text-purple-600 hover:bg-purple-50 transition-colors shrink-0"
                  >
                    🎛️ 查看配方
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {['全部', ...new Set(musicTpls.map((t) => t.category))].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setMusicTplCat(cat)}
                    className={`px-2.5 py-1 rounded-lg text-xs border transition-colors ${
                      musicTplCat === cat
                        ? 'bg-purple-600 text-white border-purple-600'
                        : 'bg-white text-gray-500 border-gray-200 hover:border-purple-300'
                    }`}
                  >
                    {cat}
                    {cat !== '全部' && (
                      <span className="ml-1 opacity-70">
                        {musicTpls.filter((t) => t.category === cat).length}
                      </span>
                    )}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                {musicTpls
                  .filter((t) => musicTplCat === '全部' || t.category === musicTplCat)
                  .map((t) => (
                    <button
                      key={t.id}
                      onClick={() => {
                        const next = musicTplId === t.id ? '' : t.id
                        setMusicTplId(next)
                        if (next) {
                          // 一键填充专业配方
                          setSelectedLyrics(t.lyrics_template || selectedLyrics)
                          setStyle(t.style)
                          setMood(t.mood)
                          setMusicVoice(t.voice)
                          setMusicDuration(t.duration)
                          setTheme(t.theme_suggestion || theme)
                          toast.success(`已应用「${t.name}」配方，可直接生成`)
                        }
                      }}
                      title={t.desc}
                      className={`px-3 py-1.5 rounded-lg text-xs border transition-colors flex items-center gap-1 ${
                        musicTplId === t.id
                          ? 'bg-purple-600 text-white border-purple-600'
                          : 'bg-white text-gray-600 border-gray-200 hover:border-purple-300'
                      }`}
                    >
                      <span>{t.icon}</span>
                      {t.name}
                      {t.pricing?.mode !== 'free' && (
                        <span
                          className={`text-[10px] px-1 rounded ${
                            musicTplId === t.id ? 'bg-white/20' : 'bg-amber-100 text-amber-700'
                          }`}
                        >
                          {t.pricing_label}
                        </span>
                      )}
                      <span className="text-[10px] opacity-60">{t.duration}s</span>
                    </button>
                  ))}
              </div>
              {musicTplId && (
                <p className="text-[11px] text-purple-500">
                  ✓ 已选：{musicTpls.find((t) => t.id === musicTplId)?.name}——歌词/风格/情绪/声音/时长已自动填充，可直接生成或继续微调
                </p>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center justify-between">
              <span>
                歌词内容 <span className="text-red-500">*</span>
              </span>
              <EnhancePromptButton
                text={selectedLyrics}
                onEnhance={(t) => setSelectedLyrics(t)}
                style="music"
                className="text-purple-600 hover:text-purple-700"
              />
            </label>
            <textarea
              value={selectedLyrics}
              onChange={(e) => setSelectedLyrics(e.target.value)}
              placeholder="粘贴歌词或使用歌词生成器创作的歌词..."
              rows={8}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
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

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {STYLES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">情感基调</label>
              <select
                value={mood}
                onChange={(e) => setMood(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {MOODS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">演唱声音</label>
              <select
                value={musicVoice}
                onChange={(e) => setMusicVoice(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {VOICES.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="rounded-lg bg-purple-50 border border-purple-100 px-3 py-2 text-xs text-gray-500">
            🎼 AI 歌声引擎：根据歌词智能谱曲，AI 歌手按旋律逐字演唱（音高/节奏/颤音对齐），自动伴奏混音与封面，约 1-2 分钟完成
          </div>

          <Button
            variant="gradient"
            size="lg"
            icon={Sparkles}
            loading={generatingMusic}
            disabled={!selectedLyrics.trim()}
            onClick={generateMusic}
            className="w-full"
          >
            {generatingMusic ? 'AI 歌手演唱合成中…' : '生成音乐'}
          </Button>
          {genHistory.length > 0 && (
            <div className="mt-3">
              <HistoryPanel
                history={genHistory}
                onReuse={(item) => {
                  if (item.theme) setTheme(item.theme)
                  if (item.style) setStyle(item.style)
                  if (item.mood) setMood(item.mood)
                  toast.info('已恢复音乐参数，可重新生成')
                }}
                onRemove={removeGenHistory}
                onClear={clearGenHistory}
                title="生成历史"
              />
            </div>
          )}
          {generatingMusic && genTask && (
            <div className="rounded-lg bg-purple-50 border border-purple-100 px-3 py-2">
              <div className="flex items-center gap-2 text-xs text-purple-700">
                <Sparkles className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
              </div>
              <div className="mt-1.5 h-1.5 bg-purple-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all"
                  style={{ width: `${genTask.progress || 0}%` }}
                />
              </div>
              <p className="mt-1 text-[11px] text-gray-400">
                任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
              </p>
            </div>
          )}

          {musicResult?.url && (
            <div className="overflow-hidden rounded-2xl border border-purple-100 bg-gradient-to-br from-purple-50 via-white to-pink-50 shadow-sm">
              {/* v20：作品卡渐变头部 */}
              <div className="bg-gradient-to-r from-purple-500 via-fuchsia-500 to-pink-500 px-4 py-3 flex items-center gap-3">
                {musicResult.cover_url ? (
                  <img
                    src={absUrl(musicResult.cover_url)}
                    alt=""
                    className="w-12 h-12 rounded-lg object-cover shadow-md ring-2 ring-white/40 flex-shrink-0"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center flex-shrink-0 ring-1 ring-white/40">
                    <Music2 className="w-6 h-6 text-white" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="font-bold text-white truncate drop-shadow-sm">
                    {musicResult.theme || 'AI 音乐作品'}
                  </div>
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    <span className="text-[10px] font-medium bg-white/25 text-white rounded-full px-2 py-0.5">
                      {STYLES.find((s) => s.value === musicResult.style)?.label || musicResult.style}
                    </span>
                    {musicResult.duration > 0 && (
                      <span className="text-[10px] font-medium bg-white/25 text-white rounded-full px-2 py-0.5">
                        {musicResult.duration.toFixed(1)}s
                      </span>
                    )}
                    <span className="text-[10px] font-medium bg-white/25 text-white rounded-full px-2 py-0.5">
                      AI 作品
                    </span>
                  </div>
                </div>
                <FavoriteButton
                  favType="record"
                  targetId={musicResult.audio_id}
                  label={musicResult.theme || 'AI 音乐'}
                  className="!bg-white/20 !text-white !hover:bg-white/30"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Download}
                  onClick={() => handleDownload({ filename: musicResult.audio_id, url: musicResult.url })}
                >
                  下载
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  loading={generatingMusic}
                  disabled={!selectedLyrics.trim()}
                  onClick={generateMusic}
                >
                  换一版
                </Button>
              </div>
              <div className="px-4 py-3 space-y-3">
                {/* v20：歌词预览（max-h 展开） */}
                {selectedLyrics && (
                  <details className="group rounded-xl border border-purple-100 bg-white/80">
                    <summary className="cursor-pointer select-none flex items-center justify-between px-3 py-2 text-xs font-medium text-purple-600 hover:text-purple-700">
                      <span className="flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5" />
                        歌词预览
                      </span>
                      <span className="text-gray-400 group-open:hidden">展开 ▾</span>
                      <span className="text-gray-400 hidden group-open:inline">收起 ▴</span>
                    </summary>
                    <LyricsCard text={selectedLyrics} className="max-h-72 overflow-y-auto px-3 pb-3" />
                  </details>
                )}
                {/* v20：美化播放器容器 */}
                <div className="rounded-xl bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-100/60 p-3">
                  <audio controls src={absUrl(musicResult.url)} className="w-full" />
                </div>
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
            AI 人声朗读
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              文本内容 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={ttsText}
              onChange={(e) => setTtsText(e.target.value)}
              placeholder="输入要合成的文本，支持歌词、诗歌、对话..."
              rows={4}
              className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">声音类型</label>
              <select
                value={ttsVoice}
                onChange={(e) => setTtsVoice(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {VOICES.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">音乐风格</label>
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              >
                {STYLES.slice(0, 4).map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <Button
            variant="gradient"
            size="lg"
            icon={Mic}
            loading={generatingTts}
            disabled={!ttsText.trim()}
            onClick={generateTts}
            className="w-full"
          >
            {generatingTts ? '生成任务执行中（后台）…' : '生成人声'}
          </Button>
          {generatingTts && genTask && (
            <div className="rounded-lg bg-purple-50 border border-purple-100 px-3 py-2 mt-2">
              <div className="flex items-center gap-2 text-xs text-purple-700">
                <Sparkles className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
              </div>
              <div className="mt-1.5 h-1.5 bg-purple-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all"
                  style={{ width: `${genTask.progress || 0}%` }}
                />
              </div>
              <p className="mt-1 text-[11px] text-gray-400">
                任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
              </p>
            </div>
          )}

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
          <Empty
            icon={Headphones}
            title="暂无音乐"
            description="生成歌词或合成人声后，作品会出现在这里"
          />
        ) : (
          <Pagination
            items={audios}
            pageSize={8}
            gridClass="grid grid-cols-1 gap-2.5"
            label={`共 ${audios.length} 首音乐`}
            renderItem={(audio) => (
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  {audio.cover_url ? (
                    <img
                      src={absUrl(audio.cover_url)}
                      alt=""
                      className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center flex-shrink-0">
                      <Music className="w-5 h-5 text-white" />
                    </div>
                  )}
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
                    <div className="font-medium text-gray-900 truncate">
                      {audio.title || audio.filename}
                    </div>
                    <div className="text-sm text-gray-500 flex items-center gap-1.5 mt-0.5">
                      {audio.duration > 0 && <span>{audio.duration.toFixed(1)}s</span>}
                      {audio.style && (
                        <span className="px-1.5 py-0.5 rounded-full bg-purple-50 text-purple-600 text-[10px] border border-purple-100">
                          {STYLES.find((s) => s.value === audio.style)?.label || audio.style}
                        </span>
                      )}
                      <span>{formatBytes(audio.size)}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => handleDownload(audio)}
                    className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                    title="下载"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => {
                      setPackAudio(audio)
                      setPackTitle(audio.title || '')
                      setPackArtist('')
                      setPackGenre('')
                      setPackCoverFile(null)
                      setPackCoverPreview('')
                    }}
                    className="p-2 text-gray-500 hover:text-pink-600 hover:bg-pink-50 rounded-lg transition-colors"
                    title="发布包（可提交网易云/腾讯/抖音音乐人）"
                  >
                    <Package className="w-4 h-4" />
                  </button>
                  <span onClick={(e) => e.stopPropagation()}>
                    <ShareButton
                      content={`# 音乐作品：${audio.filename}\n\n- 文件：${audio.filename}\n- 大小：${formatBytes(audio.size)}\n\n> 由小团智能平台 AI 音乐工坊生成 · ${new Date().toLocaleString()}`}
                      title={`音乐作品：${audio.filename}`}
                      contentType="music"
                      className="!p-2"
                    />
                  </span>
                  <button
                    onClick={() => setDeleteTarget(audio)}
                    className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          />
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

      {/* 音乐发布包 Modal：mp3 + wav 母带 + flac 无损 + 封面 + lrc 歌词 + 质量报告 */}
      <Modal
        open={!!packAudio}
        onClose={() => setPackAudio(null)}
        title="音乐发布包（音乐人平台成套物料）"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPackAudio(null)} disabled={packing}>
              取消
            </Button>
            <Button
              variant="primary"
              icon={Package}
              loading={packing}
              onClick={downloadPublishPack}
              className="bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700"
            >
              生成发布包
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-purple-50 border border-purple-100 px-3 py-2 text-xs text-purple-700">
            将自动生成：mp3 成品 + wav 母带（44.1kHz/16bit）+ flac 无损 + 封面 + lrc/txt 歌词
            + 各平台规格说明（网易云/腾讯/抖音音乐人）+ 上传指南 + 商用授权 + 质量自检报告。
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              歌曲标题
            </label>
            <input
              type="text"
              value={packTitle}
              onChange={(e) => setPackTitle(e.target.value)}
              placeholder="如：星空下的告白"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">歌手/作者</label>
              <input
                type="text"
                value={packArtist}
                onChange={(e) => setPackArtist(e.target.value)}
                placeholder="如：AI 音乐工坊"
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">流派</label>
              <select
                value={packGenre}
                onChange={(e) => setPackGenre(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 outline-none focus:border-purple-500 bg-white"
              >
                <option value="">默认</option>
                {STYLES.map((s) => (
                  <option key={s.value} value={s.label}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              自定义封面（可选，≤8MB，自动裁剪为 640×640；不传则用 AI 生成封面）
            </label>
            <div className="flex items-center gap-3">
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  setPackCoverFile(f)
                  const reader = new FileReader()
                  reader.onload = () => setPackCoverPreview(reader.result)
                  reader.readAsDataURL(f)
                }}
                className="w-full text-sm text-gray-500 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-purple-50 file:text-purple-700 file:text-xs file:font-medium hover:file:bg-purple-100"
              />
              {packCoverPreview && (
                <div className="relative shrink-0">
                  <img
                    src={packCoverPreview}
                    alt="封面预览"
                    className="w-14 h-14 rounded-lg object-cover border border-gray-200"
                  />
                  <button
                    onClick={() => {
                      setPackCoverFile(null)
                      setPackCoverPreview('')
                    }}
                    className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] leading-4 text-center"
                    title="移除封面"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </Modal>

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
            <div className="text-sm text-gray-600 mt-1">
              基于歌词合成完整歌曲：AI 谱曲伴奏 + AI 歌手按旋律演唱 + 自动混音封面
            </div>
          </div>
          <div className="bg-white rounded-lg p-3">
            <div className="font-medium text-gray-900">人声朗读</div>
            <div className="text-sm text-gray-600 mt-1">TTS 语音合成朗读（支持男声/女声）</div>
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

      {/* v22 音乐场景配方详情弹窗 */}
      <Modal open={!!musicTplInfo} onClose={() => setMusicTplInfo(null)} title="场景配方">
        {musicTplInfo && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{musicTplInfo.icon}</span>
              <h3 className="text-lg font-semibold text-gray-800">{musicTplInfo.name}</h3>
              <Badge color="purple">{musicTplInfo.category_label || musicTplInfo.category}</Badge>
              {musicTplInfo.pricing?.mode !== 'free' && (
                <Badge color="amber">{musicTplInfo.pricing_label}</Badge>
              )}
            </div>
            <p className="text-sm text-gray-500 leading-relaxed">{musicTplInfo.desc}</p>
            <div className="text-xs text-gray-400">
              热度 {musicTplInfo.usage || 0} 次使用{musicTplInfo.pricing?.mode === 'free' ? ' · 免费' : ''}
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                ['🎵 风格', musicTplInfo.style],
                ['🎭 情绪', musicTplInfo.mood],
                ['🎤 声音', musicTplInfo.voice === 'male' ? '男声' : '女声'],
                ['⏱️ 时长', `${musicTplInfo.duration}s`],
                ['🥁 BPM', musicTplInfo.bpm],
                ['🎸 乐器编配', musicTplInfo.instrument],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-gray-50 border border-gray-100 p-2.5">
                  <div className="text-[11px] text-gray-400">{k}</div>
                  <div className="text-xs font-medium text-gray-700 mt-0.5 leading-relaxed">{v}</div>
                </div>
              ))}
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-3.5">
              <div className="text-xs font-semibold text-purple-600 mb-1">📐 段落结构</div>
              <p className="text-[13px] text-gray-600 leading-relaxed">{musicTplInfo.structure}</p>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-3.5">
              <div className="text-xs font-semibold text-purple-600 mb-1">💡 专业提示</div>
              <p className="text-[13px] text-gray-600 leading-relaxed">{musicTplInfo.pro_tips}</p>
            </div>
            <div className="rounded-xl bg-gray-50 border border-gray-100 p-3.5">
              <div className="text-xs font-semibold text-purple-600 mb-1.5">📜 歌词示例（已随配方填充）</div>
              <pre className="text-[12px] text-gray-600 leading-relaxed whitespace-pre-wrap font-sans">
                {musicTplInfo.lyrics_template}
              </pre>
            </div>
            <div className="flex items-center justify-between pt-1">
              <p className="text-xs text-gray-400">
                选中该模板后点击生成，将按此配方创作音乐
              </p>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setMusicTplInfo(null)}>
                  关闭
                </Button>
                <Button
                  onClick={() => {
                    setSelectedLyrics(musicTplInfo.lyrics_template || selectedLyrics)
                    setStyle(musicTplInfo.style)
                    setMood(musicTplInfo.mood)
                    setMusicVoice(musicTplInfo.voice)
                    setMusicDuration(musicTplInfo.duration)
                    setTheme(musicTplInfo.theme_suggestion || theme)
                    setMusicTplId(musicTplInfo.id)
                    setMusicTplInfo(null)
                    toast.success(`已应用「${musicTplInfo.name}」配方`)
                  }}
                >
                  应用此配方
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
