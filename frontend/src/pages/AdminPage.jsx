import React, { useEffect, useMemo, useState } from 'react'
import {
  Activity, Crown, Loader2, RefreshCw, Search, Shield, Sparkles,
  TrendingUp, UserPlus, Users as UsersIcon, Wrench, Eye, BarChart3,
  Check, X, Zap, Banknote, ImageIcon, Layers, UserCog, QrCode, Trash2,
  Ticket, Plus, Video,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { ConfirmDialog } from '../components/ui'

const STATUS_LABELS = {
  pending: '待支付',
  paid: '待审核',
  approved: '已开通',
  rejected: '已拒绝',
  expired: '已过期',
}

const MEMBERSHIP_META = {
  free: { label: '免费版', badge: 'bg-gray-100 text-gray-600' },
  pro: { label: '专业版', badge: 'bg-blue-50 text-blue-600' },
  vip: { label: '至尊版', badge: 'bg-amber-50 text-amber-600' },
}

const ROLE_META = {
  admin: { label: '管理员', cls: 'bg-purple-50 text-purple-600' },
  user: { label: '普通用户', cls: 'bg-blue-50 text-blue-600' },
  viewer: { label: '访客', cls: 'bg-gray-100 text-gray-600' },
}

// 内容可见范围（与后端 permissions.VISIBLE_TO_VALUES 对齐）
const VISIBLE_TO_OPTIONS = [
  { value: 'all', label: '所有人可见', desc: '所有登录用户可见' },
  { value: 'pro', label: '专业版及以上', desc: '免费用户可见但锁定（引导开通）' },
  { value: 'vip', label: '仅至尊版', desc: '其余用户可见但锁定' },
  { value: 'admin', label: '仅管理员', desc: '其他用户完全不可见' },
  { value: 'hidden', label: '全站下线', desc: '所有人（含管理员）列表隐藏' },
]

export default function AdminPage() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [users, setUsers] = useState([])
  const [topTools, setTopTools] = useState([])
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [editingUser, setEditingUser] = useState(null)
  const [savingUser, setSavingUser] = useState(false)

  // 订单审核
  const [orders, setOrders] = useState([])
  const [orderFilter, setOrderFilter] = useState('paid')
  const [reviewTarget, setReviewTarget] = useState(null) // {order, approve}
  const [reviewing, setReviewing] = useState(false)

  // 页面区块：overview 运营总览 / content 内容管理
  const [activeSection, setActiveSection] = useState('overview')
  const [me] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('user') || '{}')
    } catch {
      return {}
    }
  })

  // 收款码配置
  const [paymentQr, setPaymentQr] = useState('')
  const [uploadingQr, setUploadingQr] = useState(false)
  const qrFileRef = React.useRef(null)

  // v9.4 营销中心：优惠券
  const [coupons, setCoupons] = useState([])
  const [couponForm, setCouponForm] = useState({ code: '', discount_type: 'fixed', value: 10, max_uses: 100, expires_days: 0 })
  const [creatingCoupon, setCreatingCoupon] = useState(false)
  const [deleteCoupon, setDeleteCoupon] = useState(null)

  // v9.4 分享渠道分析 + 订单统计
  const [shareStats, setShareStats] = useState(null)
  const [orderStats, setOrderStats] = useState(null)

  const loadOrders = async () => {
    try {
      const res = await api.get('/api/admin/orders', { params: { status: orderFilter === 'all' ? '' : orderFilter } })
      setOrders(res.data)
    } catch (err) {
      toast.error(err.message || '加载订单失败')
    }
  }

  const handleReview = async () => {
    if (!reviewTarget) return
    setReviewing(true)
    try {
      await api.post(`/api/admin/orders/${reviewTarget.order.id}/review`, { approve: reviewTarget.approve })
      toast.success(reviewTarget.approve ? '已开通会员（30 天）' : '已拒绝该订单')
      setReviewTarget(null)
      loadOrders()
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '审核失败')
    } finally {
      setReviewing(false)
    }
  }

  const loadAll = async () => {
    setLoading(true)
    try {
      const [statsRes, usersRes, toolsRes, activityRes, qrRes] = await Promise.all([
        api.get('/api/admin/stats'),
        api.get('/api/admin/users', { params: { search, limit: 100 } }),
        api.get('/api/admin/top-tools', { params: { days: 30, limit: 8 } }),
        api.get('/api/admin/activity', { params: { days: 7 } }),
        api.get('/api/admin/payment-qr'),
      ])
      setStats(statsRes.data)
      setUsers(usersRes.data)
      setTopTools(toolsRes.data)
      setActivity(activityRes.data)
      setPaymentQr(qrRes.data?.url || '')
    } catch (err) {
      toast.error(err.message || '加载管理数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    loadOrders()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderFilter])

  useEffect(() => {
    loadMarketing()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    loadAll()
  }

  const handleSaveUser = async () => {
    setSavingUser(true)
    try {
      await api.put(`/api/admin/users/${editingUser.id}`, {
        membership: editingUser.membership,
        daily_quota: editingUser.daily_quota,
        active: editingUser.active,
        role: editingUser.role,
      })
      toast.success('用户状态已更新')
      setEditingUser(null)
      loadAll()
    } catch (err) {
      toast.error(err.message || '更新失败')
    } finally {
      setSavingUser(false)
    }
  }

  const handleUploadQr = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingQr(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post('/api/admin/payment-qr', fd)
      setPaymentQr(res.data.url)
      toast.success('收款码已更新，会员中心将展示扫码支付')
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '上传失败')
    } finally {
      setUploadingQr(false)
      if (qrFileRef.current) qrFileRef.current.value = ''
    }
  }

  const handleRemoveQr = async () => {
    try {
      await api.delete('/api/admin/payment-qr')
      setPaymentQr('')
      toast.success('收款码已移除')
    } catch (err) {
      toast.error(err.message || '移除失败')
    }
  }

  // ── v9.4 营销 / 分析数据加载与操作 ──────────────────────────
  const loadMarketing = async () => {
    try {
      const [couponsRes, shareRes, orderRes] = await Promise.all([
        api.get('/api/admin/coupons'),
        api.get('/api/admin/share-stats'),
        api.get('/api/admin/order-stats'),
      ])
      setCoupons(couponsRes.data)
      setShareStats(shareRes.data)
      setOrderStats(orderRes.data)
    } catch (err) {
      toast.error(err.message || '加载营销数据失败')
    }
  }

  const handleCreateCoupon = async () => {
    if (!couponForm.value || couponForm.value <= 0) {
      toast.error('请填写有效的抵扣面值')
      return
    }
    if (!couponForm.max_uses || couponForm.max_uses <= 0) {
      toast.error('请填写有效的可用次数')
      return
    }
    setCreatingCoupon(true)
    try {
      await api.post('/api/admin/coupons', couponForm)
      toast.success('优惠券已生成')
      setCouponForm({ code: '', discount_type: 'fixed', value: 10, max_uses: 100, expires_days: 0 })
      loadMarketing()
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '生成失败')
    } finally {
      setCreatingCoupon(false)
    }
  }

  const handleToggleCoupon = async (c) => {
    try {
      await api.post(`/api/admin/coupons/${c.id}/toggle`)
      toast.success(c.active ? '已停用' : '已启用')
      loadMarketing()
    } catch (err) {
      toast.error(err.message || '操作失败')
    }
  }

  const handleDeleteCoupon = async () => {
    if (!deleteCoupon) return
    try {
      await api.delete(`/api/admin/coupons/${deleteCoupon.id}`)
      toast.success('优惠券已删除')
      setDeleteCoupon(null)
      loadMarketing()
    } catch (err) {
      toast.error(err.message || '删除失败')
    }
  }

  const statCards = useMemo(() => {
    if (!stats) return []
    return [
      { label: '总用户数', value: stats.total_users, icon: UsersIcon, color: 'from-brand-500 to-indigo-600', sub: `今日新增 ${stats.today_users}` },
      { label: '今日调用', value: stats.today_calls, icon: Zap, color: 'from-emerald-500 to-teal-600', sub: `累计 ${stats.total_calls}` },
      { label: '今日活跃', value: stats.today_active, icon: Activity, color: 'from-cyan-500 to-blue-600', sub: '有过工具调用的用户' },
      { label: '工具总数', value: stats.total_tools, icon: Wrench, color: 'from-orange-500 to-amber-600', sub: '效率工具箱' },
      { label: '分享总数', value: stats.total_shares, icon: Eye, color: 'from-pink-500 to-rose-600', sub: `累计浏览 ${stats.total_views}` },
    ]
  }, [stats])

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64 text-ink-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        加载管理数据…
      </div>
    )
  }

  const maxActivity = Math.max(1, ...activity.map((a) => a.calls))
  const maxTool = Math.max(1, ...topTools.map((t) => t.count))

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-page-in">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink-900 flex items-center gap-2">
            <Shield className="w-5 h-5 text-brand-600" />
            管理后台
          </h1>
          <p className="text-sm text-ink-500">用户、内容可见性与平台运营管理</p>
        </div>
        <button
          onClick={loadAll}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-xl border border-ink-200 hover:bg-ink-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {/* 区块切换 */}
      <div className="flex items-center gap-1.5 border-b border-ink-100">
        <button
          onClick={() => setActiveSection('overview')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeSection === 'overview'
              ? 'border-brand-500 text-brand-600'
              : 'border-transparent text-ink-500 hover:text-ink-800'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          运营总览
        </button>
        <button
          onClick={() => setActiveSection('content')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeSection === 'content'
              ? 'border-brand-500 text-brand-600'
              : 'border-transparent text-ink-500 hover:text-ink-800'
          }`}
        >
          <Eye className="w-4 h-4" />
          内容可见性
        </button>
        <button
          onClick={() => setActiveSection('dh')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeSection === 'dh'
              ? 'border-brand-500 text-brand-600'
              : 'border-transparent text-ink-500 hover:text-ink-800'
          }`}
        >
          <Video className="w-4 h-4" />
          数字人运营
        </button>
      </div>

      {activeSection === 'overview' && (
      <>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {statCards.map((card) => (
          <div key={card.label} className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-ink-500">{card.label}</span>
              <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${card.color} flex items-center justify-center`}>
                <card.icon className="w-4 h-4 text-white" />
              </div>
            </div>
            <p className="text-2xl font-bold text-ink-900">{card.value}</p>
            <p className="text-xs text-ink-400 mt-1">{card.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 活跃度 */}
        <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5 lg:col-span-2">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-brand-500" />
            近 7 天调用趋势
          </h3>
          <div className="flex items-end justify-between gap-2 h-40">
            {activity.map((a) => (
              <div key={a.day} className="flex-1 flex flex-col items-center gap-1.5 group">
                <span className="text-[10px] text-ink-400 opacity-0 group-hover:opacity-100 transition-opacity">
                  {a.calls}
                </span>
                <div
                  className="w-full max-w-10 rounded-t-lg bg-gradient-to-t from-brand-500 to-indigo-400 transition-all duration-500"
                  style={{ height: `${Math.max(4, (a.calls / maxActivity) * 100)}%` }}
                />
                <span className="text-[10px] text-ink-400">{a.day.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* TOP 工具 */}
        <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-brand-500" />
            TOP 工具（近 30 天）
          </h3>
          {topTools.length === 0 ? (
            <p className="text-sm text-ink-400 text-center py-8">暂无工具使用数据</p>
          ) : (
            <div className="space-y-3">
              {topTools.map((t, i) => (
                <div key={t.tool_id}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="flex items-center gap-2 text-ink-700 min-w-0">
                      <span className={`w-5 h-5 rounded-md text-[10px] font-bold flex items-center justify-center flex-shrink-0 ${
                        i === 0 ? 'bg-amber-100 text-amber-600' : i === 1 ? 'bg-gray-100 text-gray-500' : i === 2 ? 'bg-orange-100 text-orange-600' : 'bg-ink-50 text-ink-400'
                      }`}>
                        {i + 1}
                      </span>
                      <span className="truncate">{t.name}</span>
                    </span>
                    <span className="text-xs text-ink-500 flex-shrink-0">{t.count} 次</span>
                  </div>
                  <div className="h-1.5 bg-ink-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        i === 0 ? 'bg-gradient-to-r from-amber-400 to-orange-500' : 'bg-gradient-to-r from-brand-500 to-indigo-500'
                      }`}
                      style={{ width: `${(t.count / maxTool) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 用户列表 */}
      <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <UsersIcon className="w-4 h-4 text-brand-500" />
            用户管理
            <span className="text-xs font-normal text-ink-400">（{users.length} 人）</span>
          </h3>
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 pr-3 py-2 text-sm border border-ink-200 rounded-xl focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all"
                placeholder="搜索用户名 / 昵称"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-2 text-sm rounded-xl bg-ink-800 text-white hover:bg-ink-900 transition-colors"
            >
              搜索
            </button>
          </form>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-ink-400 border-b border-ink-100">
                <th className="pb-2.5 pr-4 font-medium">用户</th>
                <th className="pb-2.5 pr-4 font-medium">角色</th>
                <th className="pb-2.5 pr-4 font-medium">会员</th>
                <th className="pb-2.5 pr-4 font-medium">今日使用</th>
                <th className="pb-2.5 pr-4 font-medium">累计使用</th>
                <th className="pb-2.5 pr-4 font-medium">注册时间</th>
                <th className="pb-2.5 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const meta = MEMBERSHIP_META[u.membership] || MEMBERSHIP_META.free
                return (
                  <tr key={u.id} className="border-b border-ink-50 hover:bg-ink-50/50 transition-colors">
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-700 rounded-lg flex items-center justify-center flex-shrink-0">
                          <span className="text-white text-xs font-semibold">
                            {(u.nickname || u.username || '?')[0]?.toUpperCase()}
                          </span>
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-ink-800 truncate">{u.nickname || u.username}</p>
                          <p className="text-xs text-ink-400">@{u.username}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${ROLE_META[u.role]?.cls || 'bg-ink-100 text-ink-600'}`}>
                        {ROLE_META[u.role]?.label || u.role}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${meta.badge}`}>
                        {u.membership === 'vip' && <Crown className="w-3 h-3 inline mr-0.5 text-amber-500" />}
                        {meta.label}
                      </span>
                      {u.active === 0 && (
                        <span className="ml-1.5 px-2 py-0.5 rounded-full text-xs bg-red-50 text-red-500">已禁用</span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-ink-600">
                      {u.used_today || 0} / {u.daily_quota || 30}
                    </td>
                    <td className="py-3 pr-4 text-ink-600">{u.total_usage || 0} 次</td>
                    <td className="py-3 pr-4 text-xs text-ink-400">{u.created_at?.slice(0, 10)}</td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() =>
                          setEditingUser({
                            id: u.id,
                            username: u.username,
                            nickname: u.nickname,
                            membership: u.membership || 'free',
                            daily_quota: u.daily_quota || 30,
                            active: u.active !== 0,
                            role: u.role || 'user',
                          })
                        }
                        className="px-2.5 py-1.5 text-xs rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 transition-colors"
                      >
                        管理
                      </button>
                    </td>
                  </tr>
                )
              })}
              {users.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-ink-400">
                    <UserPlus className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    暂无用户
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 订单审核 */}
      <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5 mt-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <Banknote className="w-4 h-4 text-brand-500" />
            会员订单审核
            <span className="text-xs font-normal text-ink-400">（{orders.length} 单）</span>
          </h3>
          <div className="flex items-center gap-1.5">
            {[
              { key: 'paid', label: '待审核' },
              { key: 'pending', label: '待支付' },
              { key: 'approved', label: '已开通' },
              { key: 'rejected', label: '已拒绝' },
              { key: 'all', label: '全部' },
            ].map((f) => (
              <button
                key={f.key}
                onClick={() => setOrderFilter(f.key)}
                className={`px-3 py-1.5 text-xs rounded-full font-medium transition-colors ${
                  orderFilter === f.key
                    ? 'bg-brand-500 text-white shadow-soft'
                    : 'bg-ink-50 text-ink-500 hover:bg-ink-100'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {orders.length === 0 ? (
          <p className="text-sm text-ink-400 text-center py-8">暂无{orderFilter === 'paid' ? '待审核' : ''}订单</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-ink-400 border-b border-ink-100">
                  <th className="pb-2.5 pr-4 font-medium">用户</th>
                  <th className="pb-2.5 pr-4 font-medium">套餐</th>
                  <th className="pb-2.5 pr-4 font-medium">金额</th>
                  <th className="pb-2.5 pr-4 font-medium">凭证</th>
                  <th className="pb-2.5 pr-4 font-medium">下单时间</th>
                  <th className="pb-2.5 pr-4 font-medium">状态</th>
                  <th className="pb-2.5 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const st = {
                    pending: { label: '待支付', cls: 'bg-amber-50 text-amber-600' },
                    paid: { label: '待审核', cls: 'bg-blue-50 text-blue-600' },
                    approved: { label: '已开通', cls: 'bg-emerald-50 text-emerald-600' },
                    rejected: { label: '已拒绝', cls: 'bg-red-50 text-red-500' },
                  }[o.status] || { label: o.status, cls: 'bg-ink-100 text-ink-500' }
                  return (
                    <tr key={o.id} className="border-b border-ink-50 hover:bg-ink-50/50 transition-colors">
                      <td className="py-3 pr-4">
                        <p className="font-medium text-ink-800">{o.username || '未知用户'}</p>
                        <p className="text-xs text-ink-400">{o.id.slice(-10)}</p>
                      </td>
                      <td className="py-3 pr-4">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-indigo-50 text-indigo-600">
                          {o.plan === 'vip' ? '至尊版' : o.plan === 'pro' ? '专业版' : o.plan}
                        </span>
                      </td>
                      <td className="py-3 pr-4 font-semibold text-ink-800">¥{o.amount}</td>
                      <td className="py-3 pr-4 max-w-[200px]">
                        {o.voucher?.startsWith('/uploads/') ? (
                          <a
                            href={o.voucher}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-brand-600 hover:text-brand-800 flex items-center gap-1"
                          >
                            <ImageIcon className="w-3.5 h-3.5" /> 查看截图
                          </a>
                        ) : o.remark ? (
                          <span className="text-xs text-ink-500 line-clamp-1">{o.remark}</span>
                        ) : (
                          <span className="text-xs text-ink-300">—</span>
                        )}
                      </td>
                      <td className="py-3 pr-4 text-xs text-ink-400">{o.created_at?.slice(0, 16).replace('T', ' ')}</td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${st.cls}`}>{st.label}</span>
                      </td>
                      <td className="py-3 text-right whitespace-nowrap">
                        {o.status === 'paid' ? (
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => setReviewTarget({ order: o, approve: true })}
                              className="px-2.5 py-1.5 text-xs rounded-lg bg-emerald-50 text-emerald-600 hover:bg-emerald-100 transition-colors flex items-center gap-1"
                            >
                              <Check className="w-3 h-3" /> 通过
                            </button>
                            <button
                              onClick={() => setReviewTarget({ order: o, approve: false })}
                              className="px-2.5 py-1.5 text-xs rounded-lg bg-red-50 text-red-500 hover:bg-red-100 transition-colors flex items-center gap-1"
                            >
                              <X className="w-3 h-3" /> 拒绝
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-ink-300">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 收款码配置 */}
      <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold text-ink-900 flex items-center gap-2">
              <QrCode className="w-4 h-4 text-brand-500" />
              收款码配置
            </h3>
            <p className="text-xs text-ink-400 mt-1">上传微信 / 支付宝收款码，会员中心下单时展示扫码支付</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              ref={qrFileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={handleUploadQr}
              className="hidden"
            />
            <button
              onClick={() => qrFileRef.current?.click()}
              disabled={uploadingQr}
              className="flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-60 transition-colors"
            >
              {uploadingQr ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <QrCode className="w-3.5 h-3.5" />}
              {paymentQr ? '更换收款码' : '上传收款码'}
            </button>
            {paymentQr && (
              <button
                onClick={handleRemoveQr}
                className="flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg bg-red-50 text-red-500 hover:bg-red-100 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                移除
              </button>
            )}
          </div>
        </div>
        {paymentQr ? (
          <div className="flex items-center gap-6">
            <img
              src={paymentQr}
              alt="收款码"
              className="w-36 h-36 object-contain rounded-xl border border-ink-200 bg-white p-2"
            />
            <div className="text-sm text-ink-500 space-y-2">
              <p className="flex items-center gap-1.5">
                <Check className="w-4 h-4 text-emerald-500" />
                已生效：会员中心下单弹窗将展示此收款码
              </p>
              <p className="text-xs text-ink-400">图片路径：{paymentQr}</p>
            </div>
          </div>
        ) : (
          <div className="border-2 border-dashed border-ink-200 rounded-xl p-8 text-center text-sm text-ink-400">
            尚未配置收款码，上传后用户即可在会员中心扫码支付
          </div>
        )}
      </div>

      {/* 营销中心：优惠券 / 折扣码 */}
      <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold text-ink-900 flex items-center gap-2">
              <Ticket className="w-4 h-4 text-brand-500" />
              营销中心 · 优惠券
            </h3>
            <p className="text-xs text-ink-400 mt-1">生成折扣码，会员中心下单时可抵扣金额</p>
          </div>
        </div>
        {/* 创建表单 */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4">
          <input
            value={couponForm.code}
            onChange={(e) => setCouponForm({ ...couponForm, code: e.target.value.toUpperCase() })}
            placeholder="优惠码（留空自动生成）"
            className="col-span-2 px-3 py-2 text-sm border border-ink-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <select
            value={couponForm.discount_type}
            onChange={(e) => setCouponForm({ ...couponForm, discount_type: e.target.value })}
            className="px-3 py-2 text-sm border border-ink-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
          >
            <option value="fixed">固定金额</option>
            <option value="percent">百分比折扣</option>
          </select>
          <input
            type="number"
            value={couponForm.value}
            onChange={(e) => setCouponForm({ ...couponForm, value: Number(e.target.value) })}
            placeholder={couponForm.discount_type === 'fixed' ? '抵扣金额（元）' : '折扣百分比'}
            className="px-3 py-2 text-sm border border-ink-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <input
            type="number"
            value={couponForm.max_uses}
            onChange={(e) => setCouponForm({ ...couponForm, max_uses: Number(e.target.value) })}
            placeholder="可用次数"
            className="px-3 py-2 text-sm border border-ink-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <input
            type="number"
            value={couponForm.expires_days}
            onChange={(e) => setCouponForm({ ...couponForm, expires_days: Number(e.target.value) })}
            placeholder="有效天数（0=永久）"
            className="px-3 py-2 text-sm border border-ink-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <button
            onClick={handleCreateCoupon}
            disabled={creatingCoupon}
            className="col-span-2 md:col-span-6 flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-lg bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-60 transition-colors"
          >
            {creatingCoupon ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            生成优惠券
          </button>
        </div>
        {/* 列表 */}
        {coupons.length === 0 ? (
          <div className="border-2 border-dashed border-ink-200 rounded-xl p-8 text-center text-sm text-ink-400">
            暂无优惠券，填写上方表单生成第一张
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-ink-400 border-b border-ink-100">
                  <th className="py-2 pr-3 font-medium">优惠码</th>
                  <th className="py-2 pr-3 font-medium">类型</th>
                  <th className="py-2 pr-3 font-medium">使用情况</th>
                  <th className="py-2 pr-3 font-medium">有效期</th>
                  <th className="py-2 pr-3 font-medium">状态</th>
                  <th className="py-2 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {coupons.map((c) => (
                  <tr key={c.id} className="border-b border-ink-50 hover:bg-ink-50/40">
                    <td className="py-2.5 pr-3 font-mono font-semibold text-brand-600">{c.code}</td>
                    <td className="py-2.5 pr-3 text-ink-600">
                      {c.discount_type === 'fixed' ? `¥${c.value}` : `${c.value}% 折扣`}
                    </td>
                    <td className="py-2.5 pr-3 text-ink-600">
                      {c.used_count} / {c.max_uses}
                    </td>
                    <td className="py-2.5 pr-3 text-xs text-ink-400">
                      {c.expires_at ? c.expires_at.slice(0, 10) : '永久'}
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${c.active ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}`}>
                        {c.active ? '启用' : '停用'}
                      </span>
                    </td>
                    <td className="py-2.5 text-right whitespace-nowrap">
                      <button
                        onClick={() => handleToggleCoupon(c)}
                        className="px-2 py-1 text-xs rounded-lg text-ink-500 hover:bg-ink-100 transition-colors"
                      >
                        {c.active ? '停用' : '启用'}
                      </button>
                      <button
                        onClick={() => setDeleteCoupon(c)}
                        className="px-2 py-1 text-xs rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 分享渠道分析（埋点） */}
      <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold text-ink-900 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-brand-500" />
              分享渠道分析
            </h3>
            <p className="text-xs text-ink-400 mt-1">记录分享页打开来源与注册转化，评估分享获客效果</p>
          </div>
          <button
            onClick={loadMarketing}
            className="flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg bg-ink-50 text-ink-600 hover:bg-ink-100 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            刷新
          </button>
        </div>
        {shareStats && (
          <>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-ink-50 rounded-xl px-4 py-3">
                <p className="text-xs text-ink-400">总访问</p>
                <p className="text-xl font-bold text-ink-900 mt-0.5">{shareStats.totals.visits}</p>
              </div>
              <div className="bg-ink-50 rounded-xl px-4 py-3">
                <p className="text-xs text-ink-400">注册转化</p>
                <p className="text-xl font-bold text-ink-900 mt-0.5">{shareStats.totals.conversions}</p>
              </div>
              <div className="bg-ink-50 rounded-xl px-4 py-3">
                <p className="text-xs text-ink-400">转化率</p>
                <p className="text-xl font-bold text-emerald-600 mt-0.5">{shareStats.totals.conversion_rate}%</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink-400 border-b border-ink-100">
                    <th className="py-2 pr-3 font-medium">分享内容</th>
                    <th className="py-2 pr-3 font-medium">打开</th>
                    <th className="py-2 pr-3 font-medium">埋点访问</th>
                    <th className="py-2 pr-3 font-medium">来源渠道</th>
                    <th className="py-2 pr-3 font-medium">注册转化</th>
                    <th className="py-2 font-medium">转化率</th>
                  </tr>
                </thead>
                <tbody>
                  {shareStats.shares.map((s) => (
                    <tr key={s.id} className="border-b border-ink-50 hover:bg-ink-50/40">
                      <td className="py-2.5 pr-3 text-ink-700 max-w-[200px] truncate">{s.title}</td>
                      <td className="py-2.5 pr-3 text-ink-600">{s.views}</td>
                      <td className="py-2.5 pr-3 text-ink-600">{s.visits}</td>
                      <td className="py-2.5 pr-3">
                        <div className="flex flex-wrap gap-1">
                          {s.sources.length === 0 ? (
                            <span className="text-xs text-ink-300">-</span>
                          ) : (
                            s.sources.slice(0, 3).map((src) => (
                              <span key={src.source} className="px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 text-[11px]">
                                {src.source} × {src.count}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 pr-3 text-ink-600">{s.conversions}</td>
                      <td className="py-2.5 text-emerald-600 font-medium">{s.conversion_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* 订单统计报表 */}
      <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold text-ink-900 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-brand-500" />
              订单统计报表
            </h3>
            <p className="text-xs text-ink-400 mt-1">营收 / 转化率 / 客单价 / 近 30 天趋势</p>
          </div>
        </div>
        {orderStats && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
              {[
                { label: '总营收', value: `¥${orderStats.revenue}`, color: 'text-ink-900' },
                { label: '总订单', value: orderStats.total_orders, color: 'text-ink-900' },
                { label: '开通转化率', value: `${orderStats.conversion_rate}%`, color: 'text-emerald-600' },
                { label: '客单价', value: `¥${orderStats.avg_order}`, color: 'text-brand-600' },
                { label: '优惠券抵扣', value: `¥${orderStats.discount_total}`, color: 'text-amber-600' },
              ].map((kpi) => (
                <div key={kpi.label} className="bg-ink-50 rounded-xl px-4 py-3">
                  <p className="text-xs text-ink-400">{kpi.label}</p>
                  <p className={`text-lg font-bold mt-0.5 ${kpi.color}`}>{kpi.value}</p>
                </div>
              ))}
            </div>
            <div className="grid md:grid-cols-2 gap-5">
              {/* 近 30 天营收柱状图 */}
              <div>
                <p className="text-sm font-medium text-ink-700 mb-3">近 30 天营收趋势</p>
                <div className="flex items-end gap-[3px] h-28">
                  {orderStats.trend.map((t) => {
                    const maxRev = Math.max(1, ...orderStats.trend.map((x) => x.revenue))
                    return (
                      <div key={t.day} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                        <div className="absolute -top-6 hidden group-hover:block bg-ink-900 text-white text-[10px] rounded px-1.5 py-0.5 whitespace-nowrap z-10">
                          {t.day.slice(5)} · ¥{t.revenue}
                        </div>
                        <div
                          className={`w-full rounded-t ${t.revenue > 0 ? 'bg-gradient-to-t from-brand-600 to-brand-400' : 'bg-ink-100'}`}
                          style={{ height: t.revenue > 0 ? `${Math.max(4, (t.revenue / maxRev) * 100)}%` : '2px' }}
                        />
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between text-[10px] text-ink-300 mt-1">
                  <span>{orderStats.trend[0]?.day.slice(5)}</span>
                  <span>{orderStats.trend[orderStats.trend.length - 1]?.day.slice(5)}</span>
                </div>
              </div>
              {/* 套餐分布 + 状态 */}
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-ink-700 mb-2">套餐营收分布</p>
                  {orderStats.plan_dist.length === 0 ? (
                    <p className="text-xs text-ink-300">暂无已开通订单</p>
                  ) : (
                    <div className="space-y-2">
                      {orderStats.plan_dist.map((p) => {
                        const max = Math.max(1, ...orderStats.plan_dist.map((x) => x.revenue))
                        return (
                          <div key={p.plan} className="flex items-center gap-2">
                            <span className="w-14 text-xs text-ink-500">
                              {p.plan === 'vip' ? '至尊版' : '专业版'}
                            </span>
                            <div className="flex-1 h-2.5 bg-ink-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${p.plan === 'vip' ? 'bg-amber-500' : 'bg-brand-500'}`}
                                style={{ width: `${(p.revenue / max) * 100}%` }}
                              />
                            </div>
                            <span className="w-20 text-right text-xs text-ink-500">
                              ¥{p.revenue} · {p.orders}单
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-ink-700 mb-2">订单状态分布</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(STATUS_LABELS).map(([k, label]) => (
                      <span key={k} className="px-2.5 py-1 rounded-lg bg-ink-50 text-xs text-ink-600">
                        {label} {orderStats.status_counts[k] || 0}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* 审核确认弹窗 */}
      {reviewTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 animate-page-in">
            <h3 className="font-semibold text-ink-900 mb-2">
              {reviewTarget.approve ? '确认开通会员？' : '确认拒绝该订单？'}
            </h3>
            <p className="text-sm text-ink-500">
              {reviewTarget.approve
                ? `将自动为 ${reviewTarget.order.username} 开通${reviewTarget.order.plan === 'vip' ? '至尊版' : '专业版'}会员，有效期 30 天。`
                : `订单 ${reviewTarget.order.id.slice(-10)} 将被关闭，用户不会获得会员权益。`}
            </p>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setReviewTarget(null)}
                disabled={reviewing}
                className="px-4 py-2 text-sm rounded-xl text-ink-500 hover:bg-ink-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleReview}
                disabled={reviewing}
                className={`px-4 py-2 text-sm rounded-xl text-white disabled:opacity-60 transition-colors flex items-center gap-1.5 ${
                  reviewTarget.approve
                    ? 'bg-emerald-500 hover:bg-emerald-600'
                    : 'bg-red-500 hover:bg-red-600'
                }`}
              >
                {reviewing ? <Loader2 className="w-4 h-4 animate-spin" /> : reviewTarget.approve ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
                {reviewTarget.approve ? '确认开通' : '确认拒绝'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除优惠券确认弹窗 */}
      {deleteCoupon && (
        <ConfirmDialog
          title="删除优惠券"
          message={`确定删除优惠码 ${deleteCoupon.code} 吗？删除后不可恢复。`}
          confirmText="删除"
          danger
          onConfirm={handleDeleteCoupon}
          onCancel={() => setDeleteCoupon(null)}
        />
      )}

      {/* 编辑用户弹窗 */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-page-in">
            <h3 className="font-semibold text-ink-900 mb-1">
              管理用户 {editingUser.nickname || editingUser.username}
            </h3>
            <p className="text-xs text-ink-400 mb-5">@{editingUser.username} · 调整角色、会员等级与每日额度</p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-ink-700 mb-1.5 flex items-center gap-1.5">
                  <UserCog className="w-4 h-4 text-ink-400" />
                  用户角色
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(ROLE_META).map(([key, m]) => {
                    const isMe = String(editingUser.id) === String(me.id)
                    return (
                      <button
                        key={key}
                        type="button"
                        disabled={isMe && editingUser.role !== key}
                        onClick={() => setEditingUser({ ...editingUser, role: key })}
                        className={`py-2 rounded-xl text-sm font-medium border transition-all ${
                          editingUser.role === key
                            ? 'border-brand-500 bg-brand-50 text-brand-600'
                            : 'border-ink-200 text-ink-500 hover:border-ink-300 disabled:opacity-40 disabled:cursor-not-allowed'
                        }`}
                        title={isMe && editingUser.role !== key ? '不能修改自己的角色' : ''}
                      >
                        {m.label}
                      </button>
                    )
                  })}
                </div>
                {String(editingUser.id) === String(me.id) && (
                  <p className="text-xs text-amber-500 mt-1">⚠ 不能修改自己的角色（防止误操作锁死系统）</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-700 mb-1.5">会员等级</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(MEMBERSHIP_META).map(([key, m]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setEditingUser({ ...editingUser, membership: key })}
                      className={`py-2 rounded-xl text-sm font-medium border transition-all ${
                        editingUser.membership === key
                          ? 'border-brand-500 bg-brand-50 text-brand-600'
                          : 'border-ink-200 text-ink-500 hover:border-ink-300'
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-700 mb-1.5">每日额度（次）</label>
                <input
                  type="number"
                  value={editingUser.daily_quota}
                  onChange={(e) => setEditingUser({ ...editingUser, daily_quota: parseInt(e.target.value) || 0 })}
                  min={0}
                  max={100000}
                  className="w-full px-3.5 py-2.5 border border-ink-200 rounded-xl focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all text-sm"
                />
                <p className="text-xs text-ink-400 mt-1">9999 表示至尊版无限额度</p>
              </div>

              <div className="flex items-center justify-between p-3 bg-ink-50 rounded-xl">
                <span className="text-sm text-ink-600">启用账号</span>
                <button
                  type="button"
                  onClick={() => setEditingUser({ ...editingUser, active: !editingUser.active })}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    editingUser.active ? 'bg-brand-500' : 'bg-ink-300'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${
                      editingUser.active ? 'left-5.5' : 'left-0.5'
                    }`}
                  />
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setEditingUser(null)}
                className="px-4 py-2 text-sm rounded-xl text-ink-500 hover:bg-ink-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSaveUser}
                disabled={savingUser}
                className="px-4 py-2 text-sm rounded-xl bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-60 transition-colors flex items-center gap-1.5"
              >
                {savingUser ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                保存
              </button>
            </div>
          </div>
        </div>
      )}
      </>
      )}

      {/* 内容可见性管理 */}
      {activeSection === 'content' && <ContentManager />}

      {/* 数字人运营报表 */}
      {activeSection === 'dh' && <DigitalHumanStats />}
    </div>
  )
}

/**
 * 内容可见性管理（v9.3 灰度发布 / 上下线）
 * - 工具 / 页面双列表，实时切换可见范围
 * - 用于上新工具灰度放量、会员专属权益配置、功能下线
 */
function ContentManager() {
  const toast = useToast()
  const [type, setType] = useState('tool')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [savingId, setSavingId] = useState(null)

  const load = async (t) => {
    setLoading(true)
    try {
      const res = await api.get('/api/admin/visibility', { params: { type: t } })
      setItems(res.data || [])
    } catch (err) {
      toast.error(err.message || '加载内容列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(type)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type])

  const changeVisibility = async (item, visibleTo) => {
    setSavingId(item.resource_id)
    try {
      await api.put('/api/admin/visibility', {
        resource_type: type,
        resource_id: item.resource_id,
        visible_to: visibleTo,
      })
      toast.success(`「${item.name}」已设为「${VISIBLE_TO_OPTIONS.find((o) => o.value === visibleTo)?.label || visibleTo}」`)
      setItems((prev) => prev.map((i) => (i.resource_id === item.resource_id ? { ...i, visible_to: visibleTo } : i)))
    } catch (err) {
      toast.error(err.message || '更新失败')
    } finally {
      setSavingId(null)
    }
  }

  const filtered = items.filter(
    (i) => !search || i.name.toLowerCase().includes(search.toLowerCase()) || i.resource_id.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <Layers className="w-4 h-4 text-brand-500" />
            内容可见性管理
          </h3>
          <span className="text-xs font-normal text-ink-400">
            控制用户能看到什么：上新工具灰度放量 / 会员专属权益 / 功能下线
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-2 text-sm border border-ink-200 rounded-xl focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all"
              placeholder="搜索名称 / ID"
            />
          </div>
          <div className="flex items-center gap-1.5">
            {[
              { key: 'tool', label: '效率工具' },
              { key: 'page', label: '独立页面' },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setType(t.key)}
                className={`px-3 py-1.5 text-xs rounded-full font-medium transition-colors ${
                  type === t.key
                    ? 'bg-brand-500 text-white shadow-soft'
                    : 'bg-ink-50 text-ink-500 hover:bg-ink-100'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 可见范围图例 */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {VISIBLE_TO_OPTIONS.map((o) => (
          <span
            key={o.value}
            className="px-2.5 py-1 rounded-lg text-xs bg-ink-50 text-ink-500"
            title={o.desc}
          >
            {o.label}：{o.desc}
          </span>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-ink-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          加载内容列表…
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-ink-400 text-center py-12">暂无匹配内容</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-ink-400 border-b border-ink-100">
                <th className="pb-2.5 pr-4 font-medium">名称</th>
                <th className="pb-2.5 pr-4 font-medium">{type === 'tool' ? '分类' : '路径'}</th>
                <th className="pb-2.5 font-medium">可见范围</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const current = VISIBLE_TO_OPTIONS.find((o) => o.value === item.visible_to)
                return (
                  <tr key={item.resource_id} className="border-b border-ink-50 hover:bg-ink-50/50 transition-colors">
                    <td className="py-3 pr-4">
                      <p className="font-medium text-ink-800">{item.name}</p>
                      <p className="text-xs text-ink-400">{item.resource_id}</p>
                    </td>
                    <td className="py-3 pr-4 text-xs text-ink-500">{item.category || '—'}</td>
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <select
                          value={item.visible_to || 'all'}
                          disabled={savingId === item.resource_id}
                          onChange={(e) => changeVisibility(item, e.target.value)}
                          className="px-3 py-2 text-sm border border-ink-200 rounded-xl bg-white focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-60"
                        >
                          {VISIBLE_TO_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                        {item.visible_to !== 'all' && (
                          <span className={`px-2 py-0.5 rounded-full text-xs whitespace-nowrap ${
                            item.visible_to === 'hidden'
                              ? 'bg-red-50 text-red-500'
                              : item.visible_to === 'admin'
                                ? 'bg-purple-50 text-purple-600'
                                : 'bg-amber-50 text-amber-600'
                          }`}>
                            {current?.desc}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/**
 * 数字人专项运营报表（v8.0 商业化 P0）
 * - 总量/成功率/平均耗时/存储占用 核心卡片
 * - 状态分布 + 分辨率分布 + 近 7 天趋势 + 用户 TOP5
 * - 批量任务健康度 + 最近失败原因（用于线上故障定位）
 */
function DigitalHumanStats() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/digital-human/admin/stats')
      setData(res.data || {})
    } catch (err) {
      toast.error(err.message || '加载数字人报表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-24 text-ink-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        加载数字人运营数据...
      </div>
    )
  }

  const d = data || {}
  const usage = d.usage || {}
  const storage = d.storage || {}
  const batches = d.batches || {}
  const totals = d.totals || {}
  const statusDist = d.status_dist || {}
  const resDist = d.res_dist || {}
  const trend = d.trend_7d || []
  const maxTrend = Math.max(1, ...trend.map((t) => t.count))
  const statusMeta = {
    done: { label: '成功', cls: 'bg-green-50 text-green-600' },
    audio_only: { label: '仅音频', cls: 'bg-amber-50 text-amber-600' },
    failed: { label: '失败', cls: 'bg-red-50 text-red-600' },
    pending: { label: '生成中', cls: 'bg-blue-50 text-blue-600' },
  }

  const cards = [
    { label: '累计生成', value: totals.records ?? 0, sub: `今日 +${totals.today ?? 0}`, color: 'from-brand-500 to-indigo-500' },
    { label: '生成成功率', value: `${Math.round((usage.success_rate || 0) * 100)}%`, sub: `${usage.success || 0} / ${usage.total || 0} 次成功`, color: 'from-green-500 to-emerald-500' },
    { label: '平均耗时', value: `${usage.avg_seconds ?? 0}s`, sub: '单条生成（含渲染）', color: 'from-amber-500 to-orange-500' },
    { label: '存储占用', value: `${storage.total_mb ?? 0}MB`, sub: `音频 ${storage.audio_count || 0} / 视频 ${storage.video_count || 0}`, color: 'from-purple-500 to-fuchsia-500' },
    { label: '批量任务', value: batches.total ?? 0, sub: `完成 ${batches.done ?? 0} / 中断 ${batches.interrupted ?? 0}`, color: 'from-sky-500 to-cyan-500' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-500">数字人内容工厂 · 生产运营实时指标（成功率/耗时来自 usage_logs）</p>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-xl border border-ink-200 hover:bg-ink-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {/* 核心指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-ink-500">{card.label}</span>
              <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${card.color} flex items-center justify-center`}>
                <Activity className="w-4 h-4 text-white" />
              </div>
            </div>
            <p className="text-2xl font-bold text-ink-900">{card.value}</p>
            <p className="text-xs text-ink-400 mt-1">{card.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 近 7 天趋势 */}
        <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-ink-900 mb-4">近 7 天生成趋势</h3>
          <div className="flex items-end gap-3 h-40">
            {trend.map((t) => (
              <div key={t.date} className="flex-1 flex flex-col items-center gap-1.5">
                <span className="text-xs text-ink-600 font-medium">{t.count}</span>
                <div
                  className="w-full rounded-t-lg bg-gradient-to-t from-brand-500/70 to-brand-400 transition-all"
                  style={{ height: `${Math.max(4, Math.round((t.count / maxTrend) * 100))}%` }}
                />
                <span className="text-[10px] text-ink-400">{t.date.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 状态 + 分辨率分布 */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
            <h3 className="text-sm font-semibold text-ink-900 mb-3">状态分布</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(statusDist).map(([k, v]) => (
                <span key={k} className={`px-3 py-1.5 rounded-full text-sm ${statusMeta[k]?.cls || 'bg-gray-100 text-gray-600'}`}>
                  {statusMeta[k]?.label || k} {v}
                </span>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
            <h3 className="text-sm font-semibold text-ink-900 mb-3">分辨率分布</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(resDist).map(([k, v]) => (
                <span key={k} className="px-3 py-1.5 rounded-full text-sm bg-indigo-50 text-indigo-600">
                  {k === '1080p' ? '1080p 高清' : '720p 标清'} × {v}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 用户 TOP5 */}
        <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
          <h3 className="text-sm font-semibold text-ink-900 mb-3">生成量 TOP5 用户</h3>
          {d.user_top?.length ? (
            <div className="space-y-2">
              {d.user_top.map((u, i) => (
                <div key={u.user_id} className="flex items-center justify-between py-1.5 border-b border-ink-100 last:border-0">
                  <div className="flex items-center gap-3">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      i === 0 ? 'bg-amber-100 text-amber-600' : 'bg-ink-100 text-ink-500'
                    }`}>{i + 1}</span>
                    <span className="text-sm text-ink-800 font-medium">{u.user_id || '未知用户'}</span>
                  </div>
                  <span className="text-sm text-ink-600">{u.c} 次</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-400 py-4">暂无生成记录</p>
          )}
        </div>

        {/* 最近失败原因（线上故障定位） */}
        <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
          <h3 className="text-sm font-semibold text-ink-900 mb-3">最近失败原因（TOP10）</h3>
          {d.recent_failures?.length ? (
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {d.recent_failures.map((f, i) => (
                <div key={i} className="py-1.5 border-b border-ink-100 last:border-0">
                  <p className="text-xs text-ink-400 truncate">{f.text?.slice(0, 40) || '（无文案）'} · {f.created_at?.slice(0, 16).replace('T', ' ')}</p>
                  <p className="text-sm text-red-500 truncate">{f.error}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-400 py-4">近期待观察，无失败记录</p>
          )}
        </div>
      </div>
    </div>
  )
}
