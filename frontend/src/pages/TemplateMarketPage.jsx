import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LayoutGrid,
  Gamepad2,
  Smartphone,
  Sticker,
  Mic2,
  ArrowRight,
  Layers,
  Sparkles,
  Search,
  Star,
  X,
  Upload,
  Package,
  ShoppingCart,
  Coins,
  Trash2,
  Plus,
  Loader2,
  Store,
  Image as ImageIcon,
  Flame,
  CheckCircle2,
  Clock,
  Zap,
  ExternalLink,
} from 'lucide-react'
import { PageHeader, Empty, SkeletonGrid, Modal, Button, Pagination } from '../components/ui'
import { useToast } from '../lib/toast'
import { api } from '../lib/api'

const CATEGORY_TABS = [
  { key: 'all', label: '全部模板', icon: LayoutGrid },
  { key: 'game', label: '小游戏玩法', icon: Gamepad2 },
  { key: 'miniapp', label: '小程序结构', icon: Smartphone },
  { key: 'meme', label: '表情包样式', icon: Sticker },
  { key: 'voice', label: '配音场景', icon: Mic2 },
]

const C2C_CATEGORIES = [
  { key: 'game', label: '小游戏' },
  { key: 'miniapp', label: '小程序' },
  { key: 'meme', label: '表情包' },
  { key: 'voice', label: '配音' },
  { key: 'other', label: '其他' },
]

// 分类 key → 中文名（用户可见文案，未知回退原值）
const c2cCategoryLabel = (key) => C2C_CATEGORIES.find((c) => c.key === key)?.label || key

export default function TemplateMarketPage() {
  const navigate = useNavigate()
  // toast 固定引用：useToast 无 Provider 时每次 render 返回新对象，
  // 直接放进依赖数组会导致 effect 无限重跑（挂起）；用 ref 锁住首帧引用
  const toast = useRef(useToast()).current
  const [data, setData] = useState(null)
  const [cat] = useState('all')
  const [loading, setLoading] = useState(true)
  const [marketTab, setMarketTab] = useState('image') // image | builtin | c2c | mine | purchases

  // ── 图片海报商城（商业化核心：分类/排序/热度/定价/购买） ──
  const [imgStore, setImgStore] = useState(null)
  const [imgCat, setImgCat] = useState('全部')
  const [imgSort, setImgSort] = useState('hot') // hot | new | price
  const [imgLoading, setImgLoading] = useState(false)
  const [buyTarget, setBuyTarget] = useState(null) // 购买弹窗目标模板
  const [buyType, setBuyType] = useState('once')
  const [buying, setBuying] = useState(false)

  // ── 搜索 / 收藏（localStorage 持久化） ──
  const [q, setQ] = useState('')
  const [favs, setFavs] = useState([])
  const [onlyFav, setOnlyFav] = useState(false)

  // ── C2C 用户市场 ──
  const [c2c, setC2c] = useState([])
  const [mine, setMine] = useState([])
  const [purchases, setPurchases] = useState([])
  const [c2cLoading, setC2cLoading] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [buyingId, setBuyingId] = useState('')

  const [uploadForm, setUploadForm] = useState({
    name: '',
    description: '',
    category: 'game',
    price: 0,
    content_json: '{}',
  })

  useEffect(() => {
    try {
      setFavs(JSON.parse(localStorage.getItem('tm_favs') || '[]'))
    } catch {
      setFavs([])
    }
  }, [])

  useEffect(() => {
    const t = setTimeout(
      () => {
        setLoading(true)
        api
          .get('/api/templates/market', { params: { q: q.trim() } })
          .then((res) => {
            setData(res.data)
          })
          .catch(() => toast.error('模板加载失败'))
          .finally(() => setLoading(false))
      },
      q ? 300 : 0
    )
    return () => clearTimeout(t)
  }, [q, toast])

  // 图片模板商城：分类/搜索/排序变化时拉取
  useEffect(() => {
    setImgLoading(true)
    api
      .get('/api/image-store/list', {
        params: { category: imgCat === '全部' ? '' : imgCat, q: q.trim(), sort: imgSort },
      })
      .then((res) => setImgStore(res.data))
      .catch((e) => toast.error(`图片模板加载失败：${e.message}`))
      .finally(() => setImgLoading(false))
  }, [imgCat, imgSort, q, toast])

  const loadC2C = useCallback(async () => {
    setC2cLoading(true)
    try {
      const res = await api.get('/api/templates/c2c', { params: { q: q.trim() } })
      setC2c(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      toast.error(`C2C 市场加载失败：${e.message}`)
    } finally {
      setC2cLoading(false)
    }
  }, [q, toast])

  const loadMine = useCallback(async () => {
    try {
      const res = await api.get('/api/templates/user')
      setMine(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      toast.error(`我的模板加载失败：${e.message}`)
    }
  }, [toast])

  const loadPurchases = useCallback(async () => {
    try {
      const res = await api.get('/api/templates/purchases')
      setPurchases(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      toast.error(`购买记录加载失败：${e.message}`)
    }
  }, [toast])

  useEffect(() => {
    if (marketTab === 'c2c') loadC2C()
    if (marketTab === 'mine') loadMine()
    if (marketTab === 'purchases') loadPurchases()
  }, [marketTab, loadC2C, loadMine, loadPurchases])

  const toggleFav = (id) => {
    setFavs((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
      localStorage.setItem('tm_favs', JSON.stringify(next))
      return next
    })
  }

  const handleUpload = async () => {
    if (!uploadForm.name.trim()) {
      toast.error('请输入模板名称')
      return
    }
    setUploading(true)
    try {
      const res = await api.post('/api/templates/upload', {
        name: uploadForm.name.trim(),
        description: uploadForm.description.trim(),
        category: uploadForm.category,
        price: Number(uploadForm.price) || 0,
        content_json: uploadForm.content_json || '{}',
      })
      toast.success(res.data?.message || '模板已上架')
      setUploadOpen(false)
      setUploadForm({ name: '', description: '', category: 'game', price: 0, content_json: '{}' })
      loadMine()
      loadC2C()
    } catch (e) {
      toast.error(`上架失败：${e.message}`)
    } finally {
      setUploading(false)
    }
  }

  const handleBuy = async (tpl) => {
    setBuyingId(tpl.id)
    try {
      const res = await api.post(`/api/templates/${tpl.id}/buy`)
      toast.success(res.data?.message || '购买成功')
      loadPurchases()
    } catch (e) {
      toast.error(e.message?.includes('积分不足') ? e.message : `购买失败：${e.message}`)
    } finally {
      setBuyingId('')
    }
  }

  const handleDeleteMine = async (tpl) => {
    try {
      await api.delete(`/api/templates/${tpl.id}`)
      toast.success(`「${tpl.name}」已下架`)
      loadMine()
      loadC2C()
    } catch (e) {
      toast.error(`下架失败：${e.message}`)
    }
  }

  // ── 图片海报商城操作 ──
  const priceText = (p) => {
    if (!p || p.mode === 'free') return '免费'
    if (p.mode === 'once') return `${p.once} 积分·永久`
    if (p.mode === 'day') return `${p.day} 积分/天`
    return `${p.month} 积分/月`
  }

  const refreshImgStore = async () => {
    const r = await api.get('/api/image-store/list', {
      params: { category: imgCat === '全部' ? '' : imgCat, q: q.trim(), sort: imgSort },
    })
    setImgStore(r.data)
  }

  const handleBuyImage = async () => {
    if (!buyTarget) return
    setBuying(true)
    try {
      const res = await api.post(`/api/image-store/templates/${buyTarget.id}/purchase`, {
        access_type: buyType,
      })
      toast.success(res.data?.message || '购买成功')
      setBuyTarget(null)
      refreshImgStore()
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '购买失败')
    } finally {
      setBuying(false)
    }
  }

  const handleUseImage = (t) => {
    navigate(`/image-factory?template=${t.id}`)
  }

  const groups = data?.groups || {}
  const all = Object.values(groups).flatMap((g) => g.items || [])
  const items = useMemo(() => {
    let list = cat === 'all' ? all : groups[cat]?.items || []
    if (onlyFav) list = list.filter((i) => favs.includes(i.id))
    return [...list].sort((a, b) => (favs.includes(b.id) ? 1 : 0) - (favs.includes(a.id) ? 1 : 0))
  }, [cat, all, groups, onlyFav, favs])

  const renderC2cCard = (t) => (
    <div
      key={t.id}
      className="group bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg hover:-translate-y-0.5 hover:border-amber-200 transition-all flex flex-col"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center text-xl shadow-soft">
          <Store className="w-5 h-5 text-white" />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="px-2 py-0.5 rounded-full bg-orange-50 text-orange-600 text-[10px] font-medium border border-orange-100">
            {c2cCategoryLabel(t.category)}
          </span>
          <span
            className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${t.price > 0 ? 'bg-amber-50 text-amber-600 border border-amber-100' : 'bg-green-50 text-green-600 border border-green-100'}`}
          >
            <Coins className="w-3 h-3" /> {t.price > 0 ? `${t.price} 积分` : '免费'}
          </span>
        </div>
      </div>
      <h3 className="text-sm font-semibold text-gray-900">{t.name}</h3>
      <p className="text-xs text-gray-500 mt-1.5 flex-1 leading-relaxed line-clamp-2">
        {t.description || '暂无描述'}
      </p>
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
        <span className="text-[10px] text-gray-400">已售 {t.sales || 0} 次</span>
        <button
          onClick={() => handleBuy(t)}
          disabled={buyingId === t.id}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-orange-600 text-white text-xs font-medium hover:opacity-90 disabled:opacity-50 transition-all"
        >
          {buyingId === t.id ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <ShoppingCart className="w-3.5 h-3.5" />
          )}
          购买
        </button>
      </div>
    </div>
  )

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <PageHeader
        icon={Layers}
        iconColor="from-amber-500 to-orange-600"
        title="模板市场"
        description="内置模板聚合 + C2C 用户模板交易：选中即用，AI 自动补齐细节"
        actions={
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setMarketTab('image')}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium transition-all ${marketTab === 'image' ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-sm' : 'bg-white border border-gray-200 text-gray-600 hover:border-amber-300 hover:text-amber-600'}`}
            >
              <ImageIcon className="w-3.5 h-3.5" /> 图片海报
            </button>
            <button
              onClick={() => setMarketTab('builtin')}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium transition-all ${marketTab === 'builtin' ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-sm' : 'bg-white border border-gray-200 text-gray-600 hover:border-amber-300 hover:text-amber-600'}`}
            >
              <LayoutGrid className="w-3.5 h-3.5" /> 内置模板
            </button>
            <button
              onClick={() => setMarketTab('c2c')}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium transition-all ${marketTab === 'c2c' ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-sm' : 'bg-white border border-gray-200 text-gray-600 hover:border-amber-300 hover:text-amber-600'}`}
            >
              <Store className="w-3.5 h-3.5" /> 用户市场
            </button>
            <button
              onClick={() => setMarketTab('mine')}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium transition-all ${marketTab === 'mine' ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-sm' : 'bg-white border border-gray-200 text-gray-600 hover:border-amber-300 hover:text-amber-600'}`}
            >
              <Package className="w-3.5 h-3.5" /> 我的上传
            </button>
            <button
              onClick={() => setMarketTab('purchases')}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium transition-all ${marketTab === 'purchases' ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-sm' : 'bg-white border border-gray-200 text-gray-600 hover:border-amber-300 hover:text-amber-600'}`}
            >
              <ShoppingCart className="w-3.5 h-3.5" /> 我的购买
            </button>
            <button
              onClick={() => setUploadOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white border border-amber-300 text-amber-600 text-xs font-medium hover:bg-amber-500 hover:text-white transition-all"
            >
              <Upload className="w-3.5 h-3.5" /> 上传模板
            </button>
          </div>
        }
      />

      {marketTab === 'image' ? (
        <>
          {/* 分类 + 排序 */}
          <div className="flex flex-col lg:flex-row gap-3 mb-4 items-start lg:items-center">
            <div className="flex gap-1.5 flex-wrap flex-1">
              <button
                onClick={() => setImgCat('全部')}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium border transition-all ${imgCat === '全部' ? 'bg-amber-500 text-white border-amber-500' : 'bg-white border-gray-200 text-gray-500 hover:border-amber-300 hover:text-amber-600'}`}
              >
                全部
              </button>
              {(imgStore?.categories || []).map((c) => (
                <button
                  key={c.label}
                  onClick={() => setImgCat(c.label)}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-medium border transition-all ${imgCat === c.label ? 'bg-amber-500 text-white border-amber-500' : 'bg-white border-gray-200 text-gray-500 hover:border-amber-300 hover:text-amber-600'}`}
                >
                  {c.label}（{c.count}）
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              {[
                ['hot', '🔥 最热'],
                ['new', '🆕 最新'],
                ['price', '💰 价格'],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setImgSort(key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${imgSort === key ? 'bg-violet-500 text-white border-violet-500' : 'bg-white border-gray-200 text-gray-500 hover:border-violet-300'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {imgLoading ? (
            <SkeletonGrid count={8} />
          ) : !imgStore || imgStore.items.length === 0 ? (
            <Empty
              icon={ImageIcon}
              title="暂无图片模板"
              description="在图片工厂中创建模板后，可设置定价上架到市场"
            />
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
              {imgStore.items.map((t) => (
                <div
                  key={t.id}
                  className="group bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-xl hover:-translate-y-0.5 hover:border-amber-300 transition-all flex flex-col"
                >
                  {/* 预览图 */}
                  <div
                    className="relative h-44 bg-gray-100 cursor-pointer overflow-hidden"
                    onClick={() => handleUseImage(t)}
                  >
                    <img
                      src={t.preview}
                      alt={t.name}
                      className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                      loading="lazy"
                    />
                    <span
                      className={`absolute top-2 left-2 flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${t.pricing?.mode === 'free' ? 'bg-green-500/90 text-white' : 'bg-amber-500/95 text-white'}`}
                    >
                      <Coins className="w-3 h-3" /> {priceText(t.pricing)}
                    </span>
                    {t.access && (
                      <span className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/95 text-white text-[10px] font-medium">
                        <CheckCircle2 className="w-3 h-3" />
                        {t.access === 'once' ? '已购' : '订阅中'}
                      </span>
                    )}
                    <span className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded-md bg-black/50 text-white text-[10px]">
                      {t.width}×{t.height}
                    </span>
                  </div>
                  <div className="p-3 flex-1 flex flex-col">
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <h3 className="text-sm font-semibold text-gray-900 truncate">{t.name}</h3>
                      <span className="px-1.5 py-0.5 rounded-md bg-amber-50 text-amber-600 text-[10px] font-medium flex-shrink-0">
                        {t.category}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-auto pt-2">
                      <span className="flex items-center gap-1 text-[11px] text-gray-400">
                        <Flame className="w-3.5 h-3.5 text-orange-400" />
                        使用 {t.usage || 0} 次
                      </span>
                      {t.pricing?.mode === 'free' ? (
                        <button
                          onClick={() => handleUseImage(t)}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gradient-to-r from-emerald-500 to-green-600 text-white text-xs font-medium hover:opacity-90 transition-all"
                        >
                          <Zap className="w-3.5 h-3.5" /> 免费使用
                        </button>
                      ) : t.access ? (
                        <button
                          onClick={() => handleUseImage(t)}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gradient-to-r from-violet-500 to-purple-600 text-white text-xs font-medium hover:opacity-90 transition-all"
                        >
                          <Zap className="w-3.5 h-3.5" /> 去使用
                        </button>
                      ) : (
                        <button
                          onClick={() => {
                            setBuyTarget(t)
                            setBuyType('once')
                          }}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-orange-600 text-white text-xs font-medium hover:opacity-90 transition-all"
                        >
                          <ShoppingCart className="w-3.5 h-3.5" /> 购买
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : marketTab === 'builtin' ? (
        <>
          {/* 搜索 / 只看收藏 */}
          <div className="flex flex-col sm:flex-row gap-3 mb-5">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="搜索模板名称 / 描述 / 标签…"
                className="w-full pl-9 pr-8 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-400"
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
            <button
              onClick={() => setOnlyFav(!onlyFav)}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium border transition-all ${onlyFav ? 'bg-amber-50 border-amber-300 text-amber-700' : 'bg-white border-gray-200 text-gray-500 hover:border-amber-300 hover:text-amber-600'}`}
            >
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
                    <div
                      className={`w-12 h-12 rounded-xl bg-gradient-to-br ${t.color} flex items-center justify-center text-2xl shadow-soft`}
                    >
                      {t.icon}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 text-[10px] font-medium border border-amber-100">
                        {t.tool}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          toggleFav(t.id)
                        }}
                        className={`p-1.5 rounded-lg transition-all ${favs.includes(t.id) ? 'text-amber-500 bg-amber-50' : 'text-gray-300 hover:text-amber-500 hover:bg-amber-50'}`}
                        title={favs.includes(t.id) ? '取消收藏' : '收藏模板'}
                      >
                        <Star
                          className={`w-4 h-4 ${favs.includes(t.id) ? 'fill-amber-500' : ''}`}
                        />
                      </button>
                    </div>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900">{t.name}</h3>
                  <p className="text-xs text-gray-500 mt-1.5 flex-1 leading-relaxed">
                    {t.description}
                  </p>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
                    <div className="flex gap-1.5">
                      {(t.tags || []).map((tag) => (
                        <span
                          key={tag}
                          className="px-1.5 py-0.5 rounded-md bg-gray-50 text-gray-400 text-[10px]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="flex items-center gap-2.5 flex-shrink-0">
                      <span
                        className={`flex items-center gap-1 text-[10px] font-medium ${t.used > 0 ? 'text-gray-500' : 'text-gray-300'}`}
                      >
                        <Sparkles className="w-3 h-3" />{' '}
                        {t.used > 0 ? `已使用 ${t.used} 次` : '未使用'}
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
        </>
      ) : marketTab === 'c2c' ? (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="搜索用户市场模板…"
                className="w-full pl-9 pr-8 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-400"
              />
            </div>
            <div className="flex gap-1.5 flex-wrap">
              {C2C_CATEGORIES.map((c) => (
                <button
                  key={c.key}
                  onClick={() => setUploadForm((p) => ({ ...p, category: c.key }))}
                  className={`px-3 py-2 rounded-xl text-xs font-medium border transition-all ${uploadForm.category === c.key ? 'bg-amber-500 text-white border-amber-500' : 'bg-white border-gray-200 text-gray-500'}`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
          {c2cLoading ? (
            <SkeletonGrid count={6} />
          ) : c2c.length === 0 ? (
            <Empty
              icon={Store}
              title="暂无用户模板"
              description="点击右上角「上传模板」分享你的模板"
            />
          ) : (
            <Pagination
              items={c2c.filter((t) => !uploadForm.category || t.category === uploadForm.category)}
              pageSize={8}
              label={`共 ${c2c.filter((t) => !uploadForm.category || t.category === uploadForm.category).length} 个模板`}
              renderItem={(t) => renderC2cCard(t)}
            />
          )}
          {c2c.length > 0 &&
            c2c.filter((t) => !uploadForm.category || t.category === uploadForm.category)
              .length === 0 && (
              <Empty
                icon={Store}
                title="该分类暂无模板"
                description="试试其他分类，或点击右上角「上传模板」分享你的模板"
              />
            )}
        </div>
      ) : marketTab === 'mine' ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-700">我上传的模板（{mine.length}）</h3>
            <Button variant="secondary" size="sm" icon={Plus} onClick={() => setUploadOpen(true)}>
              上传新模板
            </Button>
          </div>
          {mine.length === 0 ? (
            <Empty
              icon={Package}
              title="还没有上传模板"
              description="上传模板到市场，赚取积分收益"
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {mine.map((t) => (
                <div
                  key={t.id}
                  className="bg-white rounded-2xl border border-gray-200 p-5 flex flex-col"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-xl shadow-soft">
                      <Package className="w-5 h-5 text-white" />
                    </div>
                    <span
                      className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${t.price > 0 ? 'bg-amber-50 text-amber-600' : 'bg-green-50 text-green-600'}`}
                    >
                      <Coins className="w-3 h-3" /> {t.price > 0 ? `${t.price} 积分` : '免费'}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900">{t.name}</h3>
                  <p className="text-xs text-gray-500 mt-1.5 flex-1 line-clamp-2">
                    {t.description || '暂无描述'}
                  </p>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
                    <span className="text-[10px] text-gray-400">已售 {t.sales || 0} 次</span>
                    <button
                      onClick={() => handleDeleteMine(t)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-200 text-red-500 text-xs font-medium hover:bg-red-50 transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" /> 下架
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-gray-700">我的购买记录（{purchases.length}）</h3>
          {purchases.length === 0 ? (
            <Empty
              icon={ShoppingCart}
              title="还没有购买记录"
              description="去用户市场逛逛，发现好模板"
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {purchases.map((p) => (
                <div
                  key={p.id}
                  className="bg-white rounded-2xl border border-gray-200 p-5 flex flex-col"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center text-xl shadow-soft">
                      <ShoppingCart className="w-5 h-5 text-white" />
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-green-50 text-green-600 text-[10px] font-medium border border-green-100">
                      {p.price > 0 ? `${p.price} 积分` : '免费'}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900">
                    {p.template_name || '模板'}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1.5 flex-1 line-clamp-2">
                    {p.template_desc || '已购买，可直接使用'}
                  </p>
                  <div className="text-[10px] text-gray-400 mt-3 pt-3 border-t border-gray-100">
                    购买时间：{p.created_at ? new Date(p.created_at).toLocaleString() : '-'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 底部：一键前往工坊 */}
      {marketTab === 'builtin' && (
        <div className="mt-8 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100 rounded-2xl p-5 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-soft">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-800">
                模板只是起点，AI 帮你完成全部实现
              </p>
              <p className="text-xs text-gray-500">
                描述你的想法，其余交给平台：小游戏双端生成、小程序项目、表情包绘制、配音合成
              </p>
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
      )}

      {/* 上传模板弹窗 */}
      <Modal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="上传模板到市场"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setUploadOpen(false)}>
              取消
            </Button>
            <Button onClick={handleUpload} loading={uploading} icon={Upload}>
              上架
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              模板名称 <span className="text-red-500">*</span>
            </label>
            <input
              value={uploadForm.name}
              onChange={(e) => setUploadForm({ ...uploadForm, name: e.target.value })}
              placeholder="例如：抖音爆款口播脚本模板"
              className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
            <textarea
              value={uploadForm.description}
              onChange={(e) => setUploadForm({ ...uploadForm, description: e.target.value })}
              rows={3}
              placeholder="模板的用途、特点、适用场景…"
              className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">分类</label>
              <select
                value={uploadForm.category}
                onChange={(e) => setUploadForm({ ...uploadForm, category: e.target.value })}
                className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500/20 outline-none text-sm bg-white"
              >
                {C2C_CATEGORIES.map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">定价（积分）</label>
              <input
                type="number"
                min={0}
                value={uploadForm.price}
                onChange={(e) => setUploadForm({ ...uploadForm, price: e.target.value })}
                placeholder="0 = 免费"
                className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              模板内容（JSON）
            </label>
            <textarea
              value={uploadForm.content_json}
              onChange={(e) => setUploadForm({ ...uploadForm, content_json: e.target.value })}
              rows={4}
              placeholder='{"style": "搞笑", "duration": "60s", ...}'
              className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none text-sm font-mono"
            />
          </div>
        </div>
      </Modal>

      {/* 图片模板购买弹窗（按次/按天/按月） */}
      <Modal
        open={!!buyTarget}
        onClose={() => setBuyTarget(null)}
        title={`购买模板「${buyTarget?.name || ''}」`}
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setBuyTarget(null)}>
              取消
            </Button>
            <Button
              variant="gradient"
              icon={Coins}
              loading={buying}
              onClick={handleBuyImage}
              disabled={!buyTarget || buying}
            >
              确认购买（{buyTarget?.pricing?.[buyType] || 0} 积分）
            </Button>
          </>
        }
      >
        {buyTarget && (
          <div className="space-y-4">
            <div className="flex gap-4">
              <img
                src={buyTarget.preview}
                alt={buyTarget.name}
                className="w-32 h-32 rounded-xl object-cover border border-gray-200 flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900">{buyTarget.name}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {buyTarget.category} · {buyTarget.width}×{buyTarget.height}
                </p>
                <p className="flex items-center gap-1 text-xs text-gray-400 mt-1.5">
                  <Flame className="w-3.5 h-3.5 text-orange-400" />
                  已被使用 {buyTarget.usage || 0} 次
                </p>
                <p className="mt-2 text-xs text-amber-600 bg-amber-50 border border-amber-100 rounded-lg px-2.5 py-1.5">
                  当前积分余额：<b>{imgStore?.credits ?? 0}</b>
                </p>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                选择购买方式
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {[
                  ['once', '按次', '永久可用', 'once'],
                  ['day', '按天', '24 小时有效', 'day'],
                  ['month', '按月', '30 天有效', 'month'],
                ].map(([key, label, desc, field]) => (
                  <button
                    key={key}
                    onClick={() => setBuyType(key)}
                    className={`rounded-xl border p-3 text-center transition-all ${buyType === key ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-500/20' : 'border-gray-200 hover:border-amber-300'}`}
                  >
                    <p className="text-sm font-semibold text-gray-800">{label}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
                    <p className={`text-sm font-bold mt-1.5 ${buyTarget.pricing?.[field] > 0 ? 'text-amber-600' : 'text-gray-300'}`}>
                      {buyTarget.pricing?.[field] > 0 ? `${buyTarget.pricing[field]} 积分` : '—'}
                    </p>
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-gray-400 mt-2">
                购买后可在图片工厂直接渲染使用；按天/按月到期后可续费，订阅期间不限次数。
              </p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
