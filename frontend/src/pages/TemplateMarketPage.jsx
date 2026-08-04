import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LayoutGrid, Gamepad2, Smartphone, Sticker, Mic2, ArrowRight,
  Layers, Sparkles, Search, Star, X,
} from 'lucide-react'
import { PageHeader, Empty, SkeletonGrid } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const CATEGORY_TABS = [
  { key: 'all', label: '全部模板', icon: LayoutGrid },
  { key: 'game', label: '小游戏玩法', icon: Gamepad2 },
  { key: 'miniapp', label: '小程序结构', icon: Smartphone },
  { key: 'meme', label: '表情包样式', icon: Sticker },
  { key: 'voice', label: '配音场景', icon: Mic2 },
]

export default function TemplateMarketPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [cat, setCat] = useState('all')
  const [loading, setLoading] = useState(true)

  // ── 搜索 / 收藏（localStorage 持久化） ──
  const [q, setQ] = useState('')
  const [favs, setFavs] = useState([])
  const [onlyFav, setOnlyFav] = useState(false)

  useEffect(() => {
    try { setFavs(JSON.parse(localStorage.getItem('tm_favs') || '[]')) } catch { setFavs([]) }
  }, [])

  useEffect(() => {
    const t = setTimeout(() => {
      setLoading(true)
      api.get('/api/templates/market', { params: { q: q.trim() } })
        .then((res) => { setData(res.data) })
        .catch((e) => toast.error('模板加载失败'))
        .finally(() => setLoading(false))
    }, q ? 300 : 0)
    return () => clearTimeout(t)
  }, [q])

  const toggleFav = (id) => {
    setFavs((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
      localStorage.setItem('tm_favs', JSON.stringify(next))
      return next
    })
  }

  const groups = data?.groups || {}
  const all = Object.values(groups).flatMap((g) => g.items || [])
  const items = useMemo(() => {
    let list = cat === 'all' ? all : (groups[cat]?.items || [])
    if (onlyFav) list = list.filter((i) => favs.includes(i.id))
    // 已收藏的模板优先展示
    return [...list].sort((a, b) => (favs.includes(b.id) ? 1 : 0) - (favs.includes(a.id) ? 1 : 0))
  }, [cat, all, groups, onlyFav, favs])

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <PageHeader
        icon={Layers}
        iconColor="from-amber-500 to-orange-600"
        title="模板市场"
        description="四大工坊内置模板聚合：选中即用，AI 自动补齐细节"
        actions={
          <div className="flex gap-2 flex-wrap">
            {CATEGORY_TABS.map((t) => {
              const count = t.key === 'all' ? data?.total : groups[t.key]?.count
              return (
                <button
                  key={t.key}
                  onClick={() => setCat(t.key)}
                  className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium transition-all ${
                    cat === t.key
                      ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-sm'
                      : 'bg-white border border-gray-200 text-gray-600 hover:border-amber-300 hover:text-amber-600'
                  }`}
                >
                  <t.icon className="w-3.5 h-3.5" /> {t.label}
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${cat === t.key ? 'bg-white/20' : 'bg-gray-100 text-gray-400'}`}>{count ?? 0}</span>
                </button>
              )
            })}
          </div>
        }
      />

      {/* 搜索 / 只看收藏 */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索模板名称 / 描述 / 标签…"
            className="w-full pl-9 pr-8 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-400" />
          {q && (
            <button onClick={() => setQ('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-gray-300 hover:text-gray-500 rounded-full">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <button onClick={() => setOnlyFav(!onlyFav)}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium border transition-all ${onlyFav ? 'bg-amber-50 border-amber-300 text-amber-700' : 'bg-white border-gray-200 text-gray-500 hover:border-amber-300 hover:text-amber-600'}`}>
          <Star className={`w-3.5 h-3.5 ${onlyFav ? 'fill-amber-500 text-amber-500' : ''}`} />
          只看收藏（{favs.length}）
        </button>
      </div>

      {loading ? (
        <SkeletonGrid count={8} />
      ) : items.length === 0 ? (
        <Empty icon={LayoutGrid} title="暂无模板" description="模板正在准备中，敬请期待" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {items.map((t) => (
            <div
              key={t.id}
              className="group bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg hover:-translate-y-0.5 hover:border-amber-200 transition-all flex flex-col cursor-pointer"
              onClick={() => navigate(t.path)}
            >
              <div className="flex items-start justify-between mb-3">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${t.color} flex items-center justify-center text-2xl shadow-soft`}>
                  {t.icon}
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 text-[10px] font-medium border border-amber-100">
                    {t.tool}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleFav(t.id) }}
                    className={`p-1.5 rounded-lg transition-all ${favs.includes(t.id) ? 'text-amber-500 bg-amber-50' : 'text-gray-300 hover:text-amber-500 hover:bg-amber-50'}`}
                    title={favs.includes(t.id) ? '取消收藏' : '收藏模板'}
                  >
                    <Star className={`w-4 h-4 ${favs.includes(t.id) ? 'fill-amber-500' : ''}`} />
                  </button>
                </div>
              </div>
              <h3 className="text-sm font-semibold text-gray-900">{t.name}</h3>
              <p className="text-xs text-gray-500 mt-1.5 flex-1 leading-relaxed">{t.description}</p>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
                <div className="flex gap-1.5">
                  {(t.tags || []).map((tag) => (
                    <span key={tag} className="px-1.5 py-0.5 rounded-md bg-gray-50 text-gray-400 text-[10px]">{tag}</span>
                  ))}
                </div>
                <div className="flex items-center gap-2.5 flex-shrink-0">
                  <span className={`flex items-center gap-1 text-[10px] font-medium ${t.used > 0 ? 'text-gray-500' : 'text-gray-300'}`}>
                    <Sparkles className="w-3 h-3" /> {t.used > 0 ? `已使用 ${t.used} 次` : '未使用'}
                  </span>
                  <span className="flex items-center gap-1 text-xs font-medium text-amber-600 opacity-0 group-hover:opacity-100 transition-opacity">
                    去使用 <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 底部：一键前往工坊 */}
      <div className="mt-8 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100 rounded-2xl p-5 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-soft">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">模板只是起点，AI 帮你完成全部实现</p>
            <p className="text-xs text-gray-500">描述你的想法，其余交给平台：小游戏双端生成、小程序项目、表情包绘制、配音合成</p>
          </div>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          {[
            { path: '/games', label: '小游戏工坊', icon: Gamepad2 },
            { path: '/miniapp', label: '小程序工坊', icon: Smartphone },
            { path: '/meme', label: '表情包工坊', icon: Sticker },
            { path: '/voice-dubbing', label: '配音工坊', icon: Mic2 },
          ].map((b) => (
            <button
              key={b.path}
              onClick={() => navigate(b.path)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white border border-amber-200 text-xs font-medium text-amber-700 hover:bg-amber-500 hover:text-white transition-all"
            >
              <b.icon className="w-3.5 h-3.5" /> {b.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
