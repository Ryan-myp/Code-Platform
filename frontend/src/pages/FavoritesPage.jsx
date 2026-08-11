import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Star,
  Trash2,
  Wrench,
  History,
  Store,
  GalleryVerticalEnd,
  Link2,
  Calendar,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDateTime } from '../lib/format'
import {
  Button,
  PageHeader,
  Card,
  Empty,
  PageLoading,
  ErrorState,
  Badge,
  ConfirmDialog,
} from '../components/ui'
import { useNavigate } from 'react-router-dom'

const TYPE_META = {
  tool: { label: '工具', icon: Wrench, color: 'bg-brand-50 text-brand-600', path: '/tool-hub' },
  record: {
    label: '记录',
    icon: History,
    color: 'bg-emerald-50 text-emerald-600',
    path: '/records',
  },
  template: { label: '模板', icon: Store, color: 'bg-amber-50 text-amber-600', path: '/templates' },
  gallery: {
    label: '作品',
    icon: GalleryVerticalEnd,
    color: 'bg-rose-50 text-rose-600',
    path: '/gallery',
  },
}

// v17 分页：每页条数（与后端 limit/offset 对齐）
const PAGE_SIZE = 20

export default function FavoritesPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [favType, setFavType] = useState('')
  const [favorites, setFavorites] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const offsetRef = useRef(0)

  // v17 分页加载：reset=true 清空重载（切换筛选时），append=false 为首页
  const fetchFavorites = useCallback(
    async (append = false) => {
      if (append) {
        setLoadingMore(true)
      } else {
        setLoading(true)
      }
      try {
        const res = await api.get('/api/favorites', {
          params: {
            fav_type: favType || undefined,
            limit: PAGE_SIZE,
            offset: offsetRef.current,
          },
        })
        const items = res.data || []
        setFavorites((prev) => (append ? [...prev, ...items] : items))
        offsetRef.current += items.length
        setHasMore(items.length === PAGE_SIZE)
        setError(null)
      } catch (e) {
        setError(e.message || '加载失败')
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [favType]
  )

  useEffect(() => {
    offsetRef.current = 0
    setHasMore(false)
    setFavorites([])
    fetchFavorites()
  }, [fetchFavorites])

  const handleDelete = async () => {
    try {
      await api.delete(`/api/favorites/${deleting}`)
      toast.success('已取消收藏')
      setDeleting(null)
      fetchFavorites(false)
    } catch (e) {
      toast.error(e.message)
    }
  }

  const tabs = [
    { key: '', label: '全部' },
    { key: 'tool', label: '工具' },
    { key: 'record', label: '记录' },
    { key: 'template', label: '模板' },
    { key: 'gallery', label: '作品' },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="收藏中心"
        description="一键收藏常用工具 / 记录 / 模板 / 作品，随时直达"
        actions={
          <Button variant="outline" icon={Star} onClick={() => fetchFavorites(false)}>
            刷新
          </Button>
        }
      />

      {/* 类型筛选 */}
      <div className="flex gap-2 flex-wrap">
        {tabs.map((t) => {
          const count = t.key === '' ? null : favorites.filter((f) => f.fav_type === t.key).length
          return (
            <button
              key={t.key}
              onClick={() => setFavType(t.key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                favType === t.key
                  ? 'bg-brand-500 text-white shadow-soft'
                  : 'bg-white border border-ink-200 text-ink-600 hover:border-brand-300 hover:text-brand-600'
              }`}
            >
              {t.label}
              {count !== null && <span className="ml-1.5 text-xs opacity-70">({count})</span>}
            </button>
          )
        })}
      </div>

      {loading ? (
        <PageLoading />
      ) : error ? (
        <ErrorState message={error} onRetry={() => fetchFavorites(false)} />
      ) : favorites.length === 0 ? (
        <Card>
          <Empty
            icon={Star}
            title="还没有收藏"
            description="在工具、记录、模板、作品页面点击 ☆ 收藏，即可在这里快速访问"
          />
        </Card>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {favorites.map((f) => {
            const meta = TYPE_META[f.fav_type] || {
              label: f.fav_type,
              icon: Link2,
              color: 'bg-gray-50 text-gray-600',
              path: null,
            }
            const Icon = meta.icon
            return (
              <div
                key={f.id}
                className="group bg-white rounded-2xl border border-ink-100 p-4 hover:shadow-soft hover:border-brand-200 transition-all"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${meta.color}`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge
                        color={
                          f.fav_type === 'tool'
                            ? 'brand'
                            : f.fav_type === 'record'
                              ? 'green'
                              : f.fav_type === 'template'
                                ? 'amber'
                                : 'rose'
                        }
                      >
                        {meta.label}
                      </Badge>
                      <span className="text-[11px] text-ink-300 flex items-center gap-1">
                        <Calendar className="w-3 h-3" /> {formatDateTime(f.created_at)}
                      </span>
                    </div>
                    <p
                      className="font-medium text-ink-900 mt-1.5 truncate"
                      title={f.label || f.target_id}
                    >
                      {f.label || f.target_id}
                    </p>
                    <p className="text-[11px] text-ink-400 font-mono truncate mt-0.5">
                      {f.target_id}
                    </p>
                  </div>
                  <button
                    onClick={() => setDeleting(f.id)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-ink-300 hover:text-red-500 hover:bg-red-50 transition-all"
                    title="取消收藏"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {meta.path && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 w-full justify-center"
                    onClick={() => navigate(meta.path)}
                  >
                    前往{meta.label}
                  </Button>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* v17 分页：已加载 offset 条，更多则显示加载按钮 */}
      {!loading && !error && hasMore && (
        <div className="flex justify-center pt-2">
          <Button
            variant="ghost"
            loading={loadingMore}
            icon={Star}
            onClick={() => fetchFavorites(true)}
          >
            加载更多（已显示 {offsetRef.current} 条）
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={handleDelete}
        title="取消收藏？"
        message="取消后该条目将从收藏中心移除。"
        confirmLabel="取消收藏"
        icon={Star}
      />
    </div>
  )
}
