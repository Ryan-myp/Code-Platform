import React, { useState, useEffect } from 'react'
import {
  Image as ImageIcon,
  Film,
  Music,
  Heart,
  MessageCircle,
  Users,
  TrendingUp,
  X,
  Send,
  Sparkles,
  ThumbsUp,
  Search,
  Flame,
  Clock3,
  Copy,
  Play,
} from 'lucide-react'
import { PageHeader, Button, Empty, Badge, Modal, SkeletonGrid, Pagination,
} from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api, { API_BASE } from '../lib/api'

const TYPE_TABS = [
  { key: 'all', label: '全部作品', icon: Sparkles },
  { key: 'image', label: '图片', icon: ImageIcon },
  { key: 'video', label: '视频', icon: Film },
  { key: 'audio', label: '音频', icon: Music },
]

// 作品来源工厂（与后端 SOURCE_LABEL 一致，筛选传原始模块名）
const AUTHOR_OPTIONS = [
  { value: '', label: '全部来源' },
  { value: 'image_factory', label: '图片工厂' },
  { value: 'video_factory', label: '视频工厂' },
  { value: 'music_factory', label: '音乐工厂' },
  { value: 'voice_factory', label: '配音工坊' },
  { value: 'meme_factory', label: '表情包工坊' },
  { value: 'game_factory', label: '小游戏工坊' },
  { value: 'miniapp', label: '小程序工坊' },
  { value: 'short_drama', label: '短剧工厂' },
]

function mediaFull(url) {
  if (!url) return ''
  return url.startsWith('http') ? url : `${API_BASE}${url}`
}

function fmtTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

// 作品卡片：图片/视频/音频统一媒体渲染 + 点赞 + 评论入口
function WorkCard({ work, onLike, onComment, onPreview }) {
  const [imgErr, setImgErr] = useState(false)
  const mediaUrl = mediaFull(work.media_url)
  return (
    <div
      onClick={() => onPreview?.(work)}
      className="break-inside-avoid mb-4 bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-lg hover:-translate-y-0.5 transition-all cursor-pointer"
    >
      {/* 媒体区 */}
      <div className="relative bg-gray-100">
        {work.type === 'image' &&
          (!imgErr ? (
            <img
              src={mediaUrl}
              alt={work.prompt?.slice(0, 50) || '作品'}
              loading="lazy"
              className="w-full max-h-80 object-cover"
              onError={() => setImgErr(true)}
            />
          ) : (
            <div className="w-full h-40 flex flex-col items-center justify-center text-gray-400">
              <ImageIcon className="w-8 h-8 mb-1" />
              <span className="text-xs">{work.prompt?.slice(0, 40) || '图片作品'}</span>
            </div>
          ))}
        {work.type === 'video' && (
          <div className="relative w-full aspect-video bg-gradient-to-br from-gray-800 to-gray-900 group/video">
            {work.thumbnail ? (
              <img
                src={mediaFull(work.thumbnail)}
                alt={work.prompt?.slice(0, 50) || '视频作品'}
                loading="lazy"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
                <Film className="w-10 h-10 mb-2" />
                <span className="text-xs px-4 text-center">
                  {work.prompt?.slice(0, 30) || '视频作品'}
                </span>
              </div>
            )}
            {/* 播放按钮浮层：点击卡片播放，无需先进入详情 */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover/video:bg-black/40 transition-colors">
              <span className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center shadow-lg group-hover/video:scale-110 transition-transform">
                <Play className="w-5 h-5 text-gray-900 ml-0.5 fill-gray-900" />
              </span>
            </div>
            {work.duration > 0 && (
              <span className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/60 text-white text-[10px]">
                {work.duration.toFixed(1)}s
              </span>
            )}
          </div>
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
        <p className="text-sm text-gray-800 line-clamp-2 min-h-[2.5rem]">
          {work.prompt || '（无描述）'}
        </p>
        <div className="flex items-center justify-between mt-2.5">
          <div className="min-w-0">
            <p className="text-xs font-medium text-gray-600 truncate">{work.author}</p>
            <p className="text-[10px] text-gray-400">{fmtTime(work.created_at)}</p>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onLike(work)
              }}
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
              onClick={(e) => {
                e.stopPropagation()
                onComment(work)
              }}
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

// 评论面板（thread 视图：点赞 / 回复 / 删除）
function CommentItemView({ c, user, onLike, onReply, onDelete }) {
  const [replying, setReplying] = useState(false)
  const [replyText, setReplyText] = useState('')
  const mine = user && c.author_id === user.username

  const submitReply = () => {
    if (!replyText.trim()) return
    onReply(c.id, replyText.trim())
    setReplyText('')
    setReplying(false)
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2.5">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
          {c.author_id?.[0]?.toUpperCase() || 'U'}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-gray-800">{c.author_id || '匿名'}</span>
            <span className="text-[10px] text-gray-400">{fmtTime(c.created_at)}</span>
            {mine && (
              <span className="text-[10px] px-1 py-0.5 rounded bg-brand-50 text-brand-600 font-medium">
                我
              </span>
            )}
            <span className="ml-auto flex items-center gap-1">
              <button
                onClick={() => onLike(c)}
                className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-all ${
                  c.liked
                    ? 'bg-rose-50 text-rose-500'
                    : 'bg-gray-50 text-gray-400 hover:text-rose-500'
                }`}
              >
                <ThumbsUp className={`w-3 h-3 ${c.liked ? 'fill-rose-500' : ''}`} /> {c.likes || 0}
              </button>
              <button
                onClick={() => setReplying(!replying)}
                className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-all ${
                  replying
                    ? 'bg-brand-50 text-brand-600'
                    : 'bg-gray-50 text-gray-400 hover:text-brand-600 hover:bg-brand-50'
                }`}
              >
                回复
              </button>
              {mine && (
                <button
                  onClick={() => onDelete(c.id)}
                  className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-50 text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                >
                  删除
                </button>
              )}
            </span>
          </div>
          <p className="text-sm text-gray-700 mt-1 bg-gray-50 rounded-xl px-3 py-2">{c.content}</p>
        </div>
      </div>

      {replying && (
        <div className="flex items-center gap-2 pl-10">
          <input
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submitReply()}
            placeholder={`回复 ${c.author_id || 'TA'}…`}
            className="flex-1 px-3 py-1.5 rounded-xl border border-gray-200 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-400"
          />
          <Button size="sm" onClick={submitReply} disabled={!replyText.trim()}>
            回复
          </Button>
        </div>
      )}

      {c.replies?.length > 0 && (
        <div className="pl-10 space-y-2 border-l-2 border-gray-100 ml-4">
          {c.replies.map((r) => (
            <CommentItemView
              key={r.id}
              c={r}
              user={user}
              onLike={onLike}
              onReply={onReply}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function CommentsPanel({ work, onClose, user }) {
  const toast = useToast()
  const [comments, setComments] = useState([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)

  const load = async () => {
    try {
      const params = { target_type: 'work', target_id: work.id }
      if (user?.username) params.user_id = user.username
      const res = await api.get('/api/comments/thread', { params })
      setComments(res.data || [])
    } catch {
      setComments([])
    }
  }
  useEffect(() => {
    load()
  }, [work.id])

  const submit = async () => {
    if (!text.trim()) return
    setSending(true)
    try {
      await api.post('/api/comments', {
        content: text.trim(),
        target_type: 'work',
        target_id: work.id,
        author_id: user?.username || 'guest',
      })
      setText('')
      toast.success('评论已发布')
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSending(false)
    }
  }

  // 递归更新树中的点赞状态
  const patchComment = (node, id, data) => {
    if (node.id === id) return { ...node, liked: data.liked, likes: data.likes }
    if (node.replies?.length)
      return { ...node, replies: node.replies.map((r) => patchComment(r, id, data)) }
    return node
  }

  const toggleLike = async (c) => {
    try {
      const res = await api.post(`/api/comments/${c.id}/like`, {
        user_id: user?.username || 'guest',
      })
      setComments((prev) => prev.map((x) => patchComment(x, c.id, res.data)))
    } catch (e) {
      toast.error(e.message)
    }
  }

  const replyTo = async (parentId, content) => {
    try {
      await api.post('/api/comments', {
        content,
        target_type: 'work',
        target_id: work.id,
        author_id: user?.username || 'guest',
        parent_comment_id: parentId,
      })
      toast.success('回复已发布')
      load()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const remove = async (id) => {
    try {
      await api.delete(`/api/comments/${id}`)
      toast.success('评论已删除')
      load()
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full sm:max-w-lg bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-brand-500" /> 作品评论
              <span className="text-xs text-gray-400 font-normal">（可点赞 / 回复 / 删除）</span>
            </h3>
            <p className="text-xs text-gray-400 truncate mt-0.5">
              {work.prompt?.slice(0, 40) || work.author}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-[180px]">
          {comments.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">还没有评论，来抢沙发~</div>
          ) : (
            comments.map((c) => (
              <CommentItemView
                key={c.id}
                c={c}
                user={user}
                onLike={toggleLike}
                onReply={replyTo}
                onDelete={remove}
              />
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

  // ── 搜索 / 排序 / 来源筛选 / 详情预览 ──
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('newest')
  const [author, setAuthor] = useState('')
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    try {
      setUser(JSON.parse(localStorage.getItem('user') || 'null'))
    } catch {
      setUser(null)
    }
  }, [])

  const loadWorks = async (t = type) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (t !== 'all') params.set('type', t)
      if (q.trim()) params.set('q', q.trim())
      if (sort) params.set('sort', sort)
      if (author) params.set('author', author)
      const res = await api.get(`/api/gallery/works?${params.toString()}`)
      setWorks(res.data || [])
    } catch {
      toast.error('加载作品失败')
    } finally {
      setLoading(false)
    }
  }

  // 搜索防抖 + 条件变化自动刷新
  useEffect(() => {
    const t = setTimeout(() => loadWorks(type), q ? 300 : 0)
    return () => clearTimeout(t)
  }, [type, q, sort, author])

  useEffect(() => {
    api
      .get('/api/gallery/stats')
      .then((res) => setStats(res.data))
      .catch(() => {})
  }, [])

  const toggleLike = async (work) => {
    try {
      const res = await api.post(`/api/gallery/${work.id}/like`)
      const patch = { ...work, liked: res.data.liked, likes: res.data.likes }
      setWorks((prev) => prev.map((w) => (w.id === work.id ? patch : w)))
      if (preview?.id === work.id) setPreview(patch)
    } catch (e) {
      toast.error(e.message)
    }
  }

  const openComments = (work) => setActive(work)

  // 作品详情：先用列表数据秒开，再拉取详情接口（GET /api/gallery/works/{id}）补充点赞/评论统计
  const openPreview = (work) => {
    setPreview(work)
    api
      .get(`/api/gallery/works/${work.id}`)
      .then((res) => setPreview(res.data || work))
      .catch(() => {
        /* 列表数据已够用 */
      })
  }

  const statsCards = [
    {
      label: '作品总数',
      value: stats?.works ?? '-',
      icon: Sparkles,
      color: 'from-brand-500 to-indigo-600',
    },
    {
      label: '今日新增',
      value: stats?.works_today ?? '-',
      icon: TrendingUp,
      color: 'from-emerald-500 to-teal-600',
    },
    {
      label: '累计点赞',
      value: stats?.likes ?? '-',
      icon: ThumbsUp,
      color: 'from-rose-500 to-pink-600',
    },
    {
      label: '作品评论',
      value: stats?.comments ?? '-',
      icon: MessageCircle,
      color: 'from-amber-500 to-orange-600',
    },
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
          <div
            key={s.label}
            className="bg-white rounded-2xl border border-gray-200 p-4 flex items-center gap-3"
          >
            <div
              className={`w-10 h-10 rounded-xl bg-gradient-to-br ${s.color} flex items-center justify-center shadow-soft flex-shrink-0`}
            >
              <s.icon className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-xl font-bold text-gray-900 leading-tight">{s.value}</p>
              <p className="text-xs text-gray-400">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 搜索 / 排序 / 来源筛选 */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索作品描述…"
            className="w-full pl-9 pr-8 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-400"
          />
          {q && (
            <button
              onClick={() => setQ('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-gray-300 hover:text-gray-500 rounded-full"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-xl border border-gray-200 overflow-hidden bg-white">
            {[
              { key: 'newest', label: '最新', icon: Clock3 },
              { key: 'popular', label: '最热', icon: Flame },
            ].map((s) => (
              <button
                key={s.key}
                onClick={() => setSort(s.key)}
                className={`flex items-center gap-1 px-3 py-2 text-xs font-medium transition-all ${sort === s.key ? 'bg-violet-50 text-violet-700' : 'text-gray-500 hover:bg-gray-50'}`}
              >
                <s.icon className="w-3.5 h-3.5" /> {s.label}
              </button>
            ))}
          </div>
          <select
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 text-xs text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-400"
          >
            {AUTHOR_OPTIONS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 作品瀑布流 */}
      {loading ? (
        <SkeletonGrid count={8} />
      ) : works.length === 0 ? (
        <Empty
          icon={ImageIcon}
          title="暂无作品"
          description="先去图片工厂 / 视频工厂 / 配音工坊创作，作品会自动出现在这里"
        />
      ) : (
        <Pagination
          items={works}
          pageSize={8}
          label={`共 ${works.length} 个作品`}
          renderItem={(w) => (
            <div className="mb-4 break-inside-avoid">
              <WorkCard
                key={w.id}
                work={w}
                onLike={toggleLike}
                onComment={openComments}
                onPreview={openPreview}
                user={user}
              />
            </div>
          )}
        />
      )}

      {active && <CommentsPanel work={active} onClose={() => setActive(null)} user={user} />}

      {/* 作品详情预览 */}
      <Modal
        open={!!preview}
        onClose={() => setPreview(null)}
        title={preview ? `作品详情 · ${preview.type_label}` : ''}
        size="lg"
      >
        {preview && (
          <div className="space-y-4">
            <div className="rounded-2xl overflow-hidden bg-gray-100">
              {preview.type === 'image' && (
                <img
                  src={mediaFull(preview.media_url)}
                  alt={preview.prompt?.slice(0, 50) || '作品'}
                  className="w-full max-h-[480px] object-contain"
                />
              )}
              {preview.type === 'video' && (
                <video
                  src={mediaFull(preview.media_url)}
                  controls
                  autoPlay
                  className="w-full max-h-[480px] bg-black"
                />
              )}
              {preview.type === 'audio' && (
                <div className="w-full h-44 flex flex-col items-center justify-center gap-3 bg-gradient-to-br from-sky-50 to-indigo-100">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center shadow-glow">
                    <Music className="w-6 h-6 text-white" />
                  </div>
                  <audio
                    src={mediaFull(preview.media_url)}
                    controls
                    autoPlay
                    className="w-4/5 h-9"
                  />
                </div>
              )}
            </div>
            <p className="text-sm text-gray-800 leading-relaxed">
              {preview.prompt || '（无描述）'}
            </p>
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <Badge color="purple">{preview.author}</Badge>
              <span>{fmtTime(preview.created_at)}</span>
              <div className="ml-auto flex items-center gap-2">
                <button
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(preview.prompt || '')
                      toast.success('提示词已复制，可到创作工具中复用')
                    } catch {
                      toast.error('复制失败')
                    }
                  }}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-medium bg-gray-50 text-gray-500 border border-gray-200 hover:border-brand-300 hover:text-brand-600 transition-all"
                  title="复制提示词"
                >
                  <Copy className="w-3.5 h-3.5" /> 复制提示词
                </button>
                <ShareButton
                  content={preview.prompt || '（无描述）'}
                  title={`作品 · ${preview.author}`}
                  contentType="gallery_work"
                />
                <button
                  onClick={() => toggleLike(preview)}
                  className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-medium transition-all ${preview.liked ? 'bg-rose-50 text-rose-500 border border-rose-200' : 'bg-gray-50 text-gray-500 border border-gray-200 hover:border-rose-200 hover:text-rose-500'}`}
                >
                  <Heart className={`w-3.5 h-3.5 ${preview.liked ? 'fill-rose-500' : ''}`} />{' '}
                  {preview.likes}
                </button>
                <button
                  onClick={() => {
                    openComments(preview)
                    setPreview(null)
                  }}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-medium bg-gray-50 text-gray-500 border border-gray-200 hover:border-brand-300 hover:text-brand-600 transition-all"
                >
                  <MessageCircle className="w-3.5 h-3.5" /> {preview.comments}
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
