import React, { useState, useEffect } from 'react'
import {
  Image as ImageIcon, Film, Music, Heart, MessageCircle, Users,
  TrendingUp, X, Send, Sparkles, ThumbsUp,
} from 'lucide-react'
import { PageHeader, Button, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

const TYPE_TABS = [
  { key: 'all', label: '全部作品', icon: Sparkles },
  { key: 'image', label: '图片', icon: ImageIcon },
  { key: 'video', label: '视频', icon: Film },
  { key: 'audio', label: '音频', icon: Music },
]

function fmtTime(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}

// 作品卡片：图片/视频/音频统一媒体渲染 + 点赞 + 评论入口
function WorkCard({ work, onLike, onComment, user }) {
  const [imgErr, setImgErr] = useState(false)
  const mediaUrl = work.media_url?.startsWith('http') ? work.media_url : `${API_BASE}${work.media_url || ''}`
  return (
    <div className="break-inside-avoid mb-4 bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-lg hover:-translate-y-0.5 transition-all">
      {/* 媒体区 */}
      <div className="relative bg-gray-100">
        {work.type === 'image' && (
          !imgErr ? (
            <img src={mediaUrl} alt={work.prompt?.slice(0, 50) || '作品'} loading="lazy"
              className="w-full max-h-80 object-cover" onError={() => setImgErr(true)} />
          ) : (
            <div className="w-full h-40 flex flex-col items-center justify-center text-gray-400">
              <ImageIcon className="w-8 h-8 mb-1" /><span className="text-xs">{work.prompt?.slice(0, 40) || '图片作品'}</span>
            </div>
          )
        )}
        {work.type === 'video' && (
          <video src={mediaUrl} controls className="w-full max-h-80 bg-black" preload="metadata" />
        )}
        {work.type === 'audio' && (
          <div className="w-full h-36 flex flex-col items-center justify-center gap-3 bg-gradient-to-br from-sky-50 to-indigo-100">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center shadow-glow">
              <Music className="w-5 h-5 text-white" />
            </div>
            <audio src={mediaUrl} controls preload="none" className="w-4/5 h-8" />
          </div>
        )}
        <span className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full bg-black/50 backdrop-blur text-white text-[10px] font-medium">
          {work.icon} {work.type_label}
        </span>
      </div>
      {/* 信息区 */}
      <div className="p-3.5">
        <p className="text-sm text-gray-800 line-clamp-2 min-h-[2.5rem]">{work.prompt || '（无描述）'}</p>
        <div className="flex items-center justify-between mt-2.5">
          <div className="min-w-0">
            <p className="text-xs font-medium text-gray-600 truncate">{work.author}</p>
            <p className="text-[10px] text-gray-400">{fmtTime(work.created_at)}</p>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              onClick={() => onLike(work)}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                work.liked
                  ? 'bg-rose-50 text-rose-500 border border-rose-200'
                  : 'bg-gray-50 text-gray-500 border border-gray-200 hover:border-rose-200 hover:text-rose-500'
              }`}
            >
              <Heart className={`w-3.5 h-3.5 ${work.liked ? 'fill-rose-500' : ''}`} />
              {work.likes}
            </button>
            <button
              onClick={() => onComment(work)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-medium bg-gray-50 text-gray-500 border border-gray-200 hover:border-brand-300 hover:text-brand-600 transition-all"
            >
              <MessageCircle className="w-3.5 h-3.5" />
              {work.comments}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// 评论面板（复用 /api/comments，target_type='work'）
function CommentsPanel({ work, onClose, user }) {
  const toast = useToast()
  const [comments, setComments] = useState([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)

  const load = async () => {
    try {
      const res = await api.get('/api/comments', { params: { target_type: 'work', target_id: work.id } })
      setComments(res.data || [])
    } catch { setComments([]) }
  }
  useEffect(() => { load() }, [work.id])

  const submit = async () => {
    if (!text.trim()) return
    setSending(true)
    try {
      await api.post('/api/comments', {
        content: text.trim(), target_type: 'work', target_id: work.id,
        author_id: user?.username || 'guest',
      })
      setText('')
      toast.success('评论已发布')
      load()
    } catch (e) { toast.error(e.message) } finally { setSending(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full sm:max-w-lg bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-brand-500" /> 作品评论
            </h3>
            <p className="text-xs text-gray-400 truncate mt-0.5">{work.prompt?.slice(0, 40) || work.author}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-[180px]">
          {comments.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">还没有评论，来抢沙发~</div>
          ) : (
            comments.map((c) => (
              <div key={c.id} className="flex gap-2.5">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                  {c.author_id?.[0]?.toUpperCase() || 'U'}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-800">{c.author_id || '匿名'}</span>
                    <span className="text-[10px] text-gray-400">{fmtTime(c.created_at)}</span>
                  </div>
                  <p className="text-sm text-gray-700 mt-1 bg-gray-50 rounded-xl px-3 py-2">{c.content}</p>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="px-5 py-3.5 border-t border-gray-100 flex items-center gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="说点什么吧…"
            className="flex-1 px-3.5 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-400"
          />
          <Button size="sm" onClick={submit} disabled={sending || !text.trim()}>
            <Send className="w-3.5 h-3.5 mr-1" /> 发布
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function GalleryPage() {
  const toast = useToast()
  const [works, setWorks] = useState([])
  const [stats, setStats] = useState(null)
  const [type, setType] = useState('all')
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState(null) // 评论面板目标作品
  const [user, setUser] = useState(null)

  useEffect(() => {
    try { setUser(JSON.parse(localStorage.getItem('user') || 'null')) } catch { setUser(null) }
  }, [])

  const loadWorks = async (t) => {
    setLoading(true)
    try {
      const params = t === 'all' ? {} : { type: t }
      const res = await api.get('/api/gallery/works', { params })
      setWorks(res.data || [])
    } catch (e) { toast.error('加载作品失败') } finally { setLoading(false) }
  }

  useEffect(() => { loadWorks(type) }, [type])

  useEffect(() => {
    api.get('/api/gallery/stats').then((res) => setStats(res.data)).catch(() => {})
  }, [])

  const toggleLike = async (work) => {
    try {
      const res = await api.post(`/api/gallery/${work.id}/like`)
      setWorks((prev) => prev.map((w) => (w.id === work.id ? { ...w, liked: res.data.liked, likes: res.data.likes } : w)))
    } catch (e) { toast.error(e.message) }
  }

  const openComments = (work) => setActive(work)

  const statsCards = [
    { label: '作品总数', value: stats?.works ?? '-', icon: Sparkles, color: 'from-brand-500 to-indigo-600' },
    { label: '今日新增', value: stats?.works_today ?? '-', icon: TrendingUp, color: 'from-emerald-500 to-teal-600' },
    { label: '累计点赞', value: stats?.likes ?? '-', icon: ThumbsUp, color: 'from-rose-500 to-pink-600' },
    { label: '作品评论', value: stats?.comments ?? '-', icon: MessageCircle, color: 'from-amber-500 to-orange-600' },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <PageHeader
        icon={Sparkles}
        iconColor="from-violet-500 to-purple-600"
        title="作品广场"
        description="全平台 AI 作品聚合：图片、视频、音频一键浏览，点赞评论互动"
        actions={
          <div className="flex gap-2">
            {TYPE_TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setType(t.key)}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium transition-all ${
                  type === t.key
                    ? 'bg-gradient-to-r from-violet-500 to-purple-600 text-white shadow-sm'
                    : 'bg-white border border-gray-200 text-gray-600 hover:border-violet-300 hover:text-violet-600'
                }`}
              >
                <t.icon className="w-3.5 h-3.5" /> {t.label}
              </button>
            ))}
          </div>
        }
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {statsCards.map((s) => (
          <div key={s.label} className="bg-white rounded-2xl border border-gray-200 p-4 flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${s.color} flex items-center justify-center shadow-soft flex-shrink-0`}>
              <s.icon className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-xl font-bold text-gray-900 leading-tight">{s.value}</p>
              <p className="text-xs text-gray-400">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 作品瀑布流 */}
      {loading ? (
        <div className="text-center py-20 text-gray-400">作品加载中…</div>
      ) : works.length === 0 ? (
        <Empty icon={ImageIcon} title="暂无作品" description="先去图片工厂 / 视频工厂 / 配音工坊创作，作品会自动出现在这里" />
      ) : (
        <div className="columns-1 sm:columns-2 lg:columns-3 xl:columns-4 gap-4">
          {works.map((w) => (
            <WorkCard key={w.id} work={w} onLike={toggleLike} onComment={openComments} user={user} />
          ))}
        </div>
      )}

      {active && <CommentsPanel work={active} onClose={() => setActive(null)} user={user} />}
    </div>
  )
}
