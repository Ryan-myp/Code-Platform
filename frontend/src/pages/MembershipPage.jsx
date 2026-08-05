import React, { useEffect, useState } from 'react'
import {
  ArrowRight, Check, Crown, FileUp, Loader2, RefreshCw, ShieldCheck,
  Sparkles, Zap, Clock, XCircle, Banknote, QrCode, Trophy, AlertTriangle, Ticket,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import useQuota from '../hooks/useQuota'

const STATUS_META = {
  pending: { label: '待支付', cls: 'bg-amber-50 text-amber-600 border-amber-200' },
  paid: { label: '待审核', cls: 'bg-blue-50 text-blue-600 border-blue-200' },
  approved: { label: '已开通', cls: 'bg-emerald-50 text-emerald-600 border-emerald-200' },
  rejected: { label: '已拒绝', cls: 'bg-red-50 text-red-500 border-red-200' },
  expired: { label: '已过期', cls: 'bg-gray-50 text-gray-400 border-gray-200' },
}

const PLAN_META = {
  free: { icon: Zap, color: 'from-gray-500 to-gray-600', ring: 'ring-gray-200', btn: 'bg-gray-100 text-gray-500', tag: '入门' },
  pro: { icon: Sparkles, color: 'from-blue-500 to-indigo-600', ring: 'ring-blue-200', btn: 'bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700', tag: '推荐' },
  vip: { icon: Crown, color: 'from-amber-500 to-orange-600', ring: 'ring-amber-200', btn: 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700', tag: '至尊' },
}

export default function MembershipPage() {
  const toast = useToast()
  const { quota } = useQuota()
  const [plans, setPlans] = useState(null)
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [buyPlan, setBuyPlan] = useState(null) // 当前开通的套餐
  const [creating, setCreating] = useState(false)
  const [currentOrder, setCurrentOrder] = useState(null) // 已创建订单（待上传凭证）
  const [voucherFile, setVoucherFile] = useState(null)
  const [remark, setRemark] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // v9.4：扫码支付 + 邀请排行榜
  const [paymentQr, setPaymentQr] = useState('')
  const [leaderboard, setLeaderboard] = useState(null)
  // v9.4：优惠码抵扣
  const [couponCode, setCouponCode] = useState('')

  const membership = quota?.membership || 'free'
  const isVip = membership === 'vip'

  const loadAll = async () => {
    setLoading(true)
    try {
      const [plansRes, ordersRes, qrRes, boardRes] = await Promise.all([
        api.get('/api/membership/plans'),
        api.get('/api/orders'),
        api.get('/api/membership/payment-qr'),
        api.get('/api/invite/leaderboard'),
      ])
      setPlans(plansRes.data)
      setOrders(ordersRes.data)
      setPaymentQr(qrRes.data?.url || '')
      setLeaderboard(boardRes.data)
    } catch (err) {
      toast.error(err.message || '加载会员信息失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleBuy = async () => {
    if (!buyPlan) return
    setCreating(true)
    try {
      const res = await api.post('/api/orders', {
        plan: buyPlan,
        coupon_code: couponCode.trim(),
      })
      setCurrentOrder(res.data)
      toast.success('订单已创建，请完成转账并上传凭证')
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '创建订单失败')
    } finally {
      setCreating(false)
    }
  }

  const handleSubmitVoucher = async () => {
    if (!currentOrder) return
    if (!voucherFile && !remark.trim()) {
      toast.error('请上传支付凭证截图或填写转账说明')
      return
    }
    setSubmitting(true)
    try {
      const fd = new FormData()
      if (voucherFile) fd.append('file', voucherFile)
      if (remark.trim()) fd.append('remark', remark.trim())
      await api.post(`/api/orders/${currentOrder.id}/voucher`, fd)
      toast.success('凭证已提交，等待管理员审核（通常 1 个工作日内）')
      setCurrentOrder(null)
      setVoucherFile(null)
      setRemark('')
      loadAll()
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const closeModal = () => {
    if (submitting) return
    setCurrentOrder(null)
    setVoucherFile(null)
    setRemark('')
    setCouponCode('')
    setBuyPlan(null)
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900 flex items-center gap-2.5">
            <Crown className="w-6 h-6 text-amber-500" />
            会员中心
          </h1>
          <p className="text-sm text-ink-500 mt-1">开通会员，解锁更大额度，畅用全部 AI 工具</p>
        </div>
        <button onClick={loadAll} className="p-2 hover:bg-ink-50 rounded-lg transition-colors text-ink-400 hover:text-brand-600" title="刷新">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* 当前会员状态 */}
      <div className={`rounded-2xl p-6 mb-8 text-white bg-gradient-to-r ${membership === 'vip' ? 'from-amber-500 via-orange-500 to-rose-500' : membership === 'pro' ? 'from-blue-600 via-indigo-600 to-violet-600' : 'from-ink-700 to-ink-800'}`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm opacity-80">当前方案</p>
            <p className="text-2xl font-bold mt-1 flex items-center gap-2">
              {isVip ? '至尊版会员' : membership === 'pro' ? '专业版会员' : '免费版'}
              {membership !== 'free' && quota?.membership_expires && (
                <span className="text-xs font-normal opacity-80 bg-white/20 rounded-full px-3 py-1">
                  有效期至 {quota.membership_expires.slice(0, 10)}
                  {quota.membership_days_left != null && quota.membership_days_left <= 7 && (
                    <span className="ml-1.5 text-amber-200">· 剩 {quota.membership_days_left} 天</span>
                  )}
                </span>
              )}
            </p>
            {membership !== 'free' && quota?.membership_days_left != null && quota.membership_days_left <= 3 && (
              <div className="mt-3 inline-flex items-center gap-2 bg-white/15 border border-white/30 rounded-xl px-3 py-2 text-xs">
                <AlertTriangle className="w-4 h-4 text-amber-200" />
                会员即将到期（剩 {quota.membership_days_left} 天），建议尽快续费避免额度降级
              </div>
            )}
          </div>
          <div className="text-right">
            <p className="text-sm opacity-80">今日剩余额度</p>
            <p className="text-3xl font-bold mt-1">
              {isVip ? '∞ 无限' : `${quota?.remaining_today ?? '-'} 次`}
            </p>
            {!isVip && quota && (
              <p className="text-xs opacity-80 mt-1">
                每日 {quota.daily_quota} 次 + 邀请奖励 {quota.bonus_quota} 次
              </p>
            )}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-ink-400">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> 加载中…
        </div>
      ) : (
        <>
          {/* 套餐卡片 */}
          <h2 className="font-semibold text-ink-900 mb-4 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-brand-500" /> 选择方案
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-10">
            {plans &&
              Object.entries(plans).map(([key, plan]) => {
                const meta = PLAN_META[key] || PLAN_META.free
                const isCurrent = membership === key
                const Icon = meta.icon
                return (
                  <div
                    key={key}
                    className={`relative bg-white rounded-2xl border border-ink-200/60 shadow-soft p-6 flex flex-col ring-2 ring-transparent transition-all hover:-translate-y-1 hover:shadow-lg ${isCurrent ? meta.ring : ''}`}
                  >
                    {key !== 'free' && (
                      <span className={`absolute top-4 right-4 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gradient-to-r ${meta.color} text-white`}>
                        {meta.tag}
                      </span>
                    )}
                    <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${meta.color} flex items-center justify-center mb-4 shadow-soft`}>
                      <Icon className="w-5 h-5 text-white" />
                    </div>
                    <h3 className="font-semibold text-ink-900 text-lg">{plan.name}</h3>
                    <div className="flex items-baseline gap-1 mt-2 mb-4">
                      <span className="text-3xl font-bold text-ink-900">
                        {plan.price > 0 ? `¥${plan.price}` : '免费'}
                      </span>
                      {plan.price > 0 && <span className="text-xs text-ink-400">/ 30 天</span>}
                    </div>
                    <div className="text-sm text-brand-600 font-medium mb-3">
                      每日 {plan.daily_quota >= 9999 ? '无限' : `${plan.daily_quota} 次`}额度
                    </div>
                    <ul className="space-y-2 text-sm text-ink-600 mb-6 flex-1">
                      {(plan.features || []).map((f) => (
                        <li key={f} className="flex items-start gap-2">
                          <Check className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                          {f}
                        </li>
                      ))}
                    </ul>
                    {isCurrent ? (
                      <button disabled className={`w-full py-2.5 rounded-xl text-sm font-medium ${meta.btn} opacity-60 cursor-default`}>
                        当前方案
                      </button>
                    ) : key === 'free' ? (
                      <div className="w-full py-2.5 rounded-xl text-sm font-medium bg-ink-50 text-ink-400 text-center">默认方案</div>
                    ) : (
                      <button
                        onClick={() => setBuyPlan(key)}
                        className={`w-full py-2.5 rounded-xl text-sm font-medium text-white shadow-soft transition-all ${meta.btn}`}
                      >
                        立即开通 <ArrowRight className="w-3.5 h-3.5 inline ml-0.5" />
                      </button>
                    )}
                  </div>
                )
              })}
          </div>

          {/* 我的订单 */}
          <h2 className="font-semibold text-ink-900 mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-brand-500" /> 我的订单
          </h2>
          {orders.length === 0 ? (
            <div className="bg-white rounded-2xl border border-dashed border-ink-200 p-10 text-center text-ink-400 text-sm">
              暂无订单，选择上方方案立即开通会员
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft divide-y divide-ink-100">
              {orders.map((o) => {
                const st = STATUS_META[o.status] || STATUS_META.pending
                return (
                  <div key={o.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                    <div>
                      <p className="text-sm font-medium text-ink-800">
                        {plans?.[o.plan]?.name || o.plan} · <span className="text-ink-500">¥{o.amount}</span>
                      </p>
                      <p className="text-xs text-ink-400 mt-0.5">
                        订单号 {o.id.slice(-10)} · {o.created_at.slice(0, 16).replace('T', ' ')}
                      </p>
                      {o.remark && <p className="text-xs text-ink-400 mt-0.5">备注：{o.remark}</p>}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${st.cls}`}>{st.label}</span>
                      {o.status === 'pending' && (
                        <button
                          onClick={() => setCurrentOrder(o)}
                          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 transition-colors"
                        >
                          上传凭证
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* 邀请排行榜 */}
          <h2 className="font-semibold text-ink-900 mb-4 flex items-center gap-2 mt-10">
            <Trophy className="w-5 h-5 text-amber-500" /> 邀请排行榜
            <span className="text-xs font-normal text-ink-400">每邀请 1 位新用户，双方各得 +5 次额度</span>
          </h2>
          {leaderboard && leaderboard.board.length === 0 ? (
            <div className="bg-white rounded-2xl border border-dashed border-ink-200 p-10 text-center text-ink-400 text-sm">
              暂无邀请记录，分享你的邀请码成为第一名
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft overflow-hidden">
              <div className="divide-y divide-ink-50">
                {leaderboard?.board.map((u) => {
                  const isMe = u.username === quota?.username
                  return (
                    <div key={u.username} className={`flex items-center gap-4 px-5 py-3 ${isMe ? 'bg-brand-50/50' : ''}`}>
                      <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                        u.rank === 1 ? 'bg-amber-100 text-amber-600' : u.rank === 2 ? 'bg-gray-100 text-gray-500' : u.rank === 3 ? 'bg-orange-100 text-orange-600' : 'bg-ink-50 text-ink-400'
                      }`}>
                        {u.rank}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-ink-800 truncate">
                          {u.nickname}
                          {isMe && <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full bg-brand-100 text-brand-600">我</span>}
                        </p>
                        <p className="text-xs text-ink-400">@{u.username}</p>
                      </div>
                      <span className="text-sm font-semibold text-brand-600 flex-shrink-0">
                        邀请 {u.invites} 人
                      </span>
                    </div>
                  )
                })}
                {leaderboard?.my_rank != null && leaderboard.my_rank > (leaderboard.board.length || 0) && (
                  <div className="flex items-center gap-4 px-5 py-3 bg-ink-50/60">
                    <span className="w-7 h-7 rounded-lg bg-ink-100 text-ink-500 flex items-center justify-center text-sm font-bold flex-shrink-0">
                      {leaderboard.my_rank}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-ink-800 truncate">我的排名</p>
                      <p className="text-xs text-ink-400">继续邀请好友即可上榜</p>
                    </div>
                    <span className="text-sm font-semibold text-ink-600 flex-shrink-0">
                      邀请 {leaderboard.my_invites} 人
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* 开通确认 + 凭证上传弹窗 */}
      {(buyPlan || currentOrder) && plans && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeModal} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h3 className="font-semibold text-ink-900 text-lg flex items-center gap-2">
                <Banknote className="w-5 h-5 text-brand-500" />
                {currentOrder ? '提交支付凭证' : '确认开通'}
              </h3>
              {!currentOrder ? (
                <div className="mt-4 space-y-3">
                  <div className="flex justify-between items-center bg-ink-50 rounded-xl px-4 py-3 text-sm">
                    <span className="text-ink-600">方案</span>
                    <span className="font-semibold text-ink-900">{plans[buyPlan].name}</span>
                  </div>
                  <div className="flex justify-between items-center bg-ink-50 rounded-xl px-4 py-3 text-sm">
                    <span className="text-ink-600">金额</span>
                    <span className="font-semibold text-brand-600">¥{plans[buyPlan].price}</span>
                  </div>
                  <div className="rounded-xl border border-dashed border-ink-300 px-4 py-3">
                    <label className="flex items-center gap-2 text-sm">
                      <Ticket className="w-4 h-4 text-brand-500 flex-shrink-0" />
                      <input
                        type="text"
                        value={couponCode}
                        onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                        placeholder="优惠码（选填）"
                        className="flex-1 bg-transparent outline-none text-sm placeholder:text-ink-400"
                      />
                      {couponCode && (
                        <button
                          type="button"
                          onClick={() => setCouponCode('')}
                          className="text-xs text-ink-400 hover:text-ink-600"
                        >
                          清除
                        </button>
                      )}
                    </label>
                    <p className="text-[11px] text-ink-400 mt-1">
                      输入优惠码可抵扣订单金额，下单时自动校验
                    </p>
                  </div>
                  <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-700 leading-relaxed">
                    请通过微信 / 支付宝转账至管理员账户，付款后上传转账截图，管理员审核通过后自动开通会员（有效期 30 天）。
                  </div>
                  {paymentQr ? (
                    <div className="rounded-xl border border-ink-200 overflow-hidden">
                      <div className="flex items-center gap-2 bg-ink-50 px-4 py-2.5 text-xs font-medium text-ink-600">
                        <QrCode className="w-4 h-4 text-brand-500" />
                        扫码支付（保存图片后转账，付款备注可填订单号）
                      </div>
                      <div className="flex items-center justify-center p-4 bg-white">
                        <img
                          src={paymentQr}
                          alt="收款码"
                          className="w-44 h-44 object-contain rounded-lg border border-ink-100"
                        />
                      </div>
                      <p className="text-[11px] text-ink-400 text-center pb-3">
                        微信 / 支付宝扫码转账 ¥{plans[buyPlan].price}，然后上传支付凭证
                      </p>
                    </div>
                  ) : (
                    <div className="bg-ink-50 rounded-xl px-4 py-3 text-xs text-ink-500 text-center">
                      管理员暂未配置收款码，请转账后填写转账说明并上传凭证
                    </div>
                  )}
                  <button
                    onClick={handleBuy}
                    disabled={creating}
                    className="w-full py-2.5 rounded-xl bg-gradient-to-r from-brand-500 to-brand-700 text-white text-sm font-medium shadow-soft hover:from-brand-600 hover:to-brand-800 transition-all disabled:opacity-60"
                  >
                    {creating ? <Loader2 className="w-4 h-4 animate-spin inline mr-1" /> : null}
                    创建订单并继续
                  </button>
                </div>
              ) : (
                <div className="mt-4 space-y-4">
                  <div className="bg-ink-50 rounded-xl px-4 py-3 text-sm flex justify-between">
                    <span className="text-ink-600">待支付金额</span>
                    <span className="font-semibold text-ink-900">
                      {currentOrder.original_amount > currentOrder.amount && (
                        <span className="text-ink-400 line-through mr-2 font-normal">¥{currentOrder.original_amount}</span>
                      )}
                      ¥{currentOrder.amount}
                      {currentOrder.coupon_code && (
                        <span className="ml-2 text-xs font-medium text-brand-600 bg-brand-50 rounded-md px-1.5 py-0.5">
                          {currentOrder.coupon_code}
                        </span>
                      )}
                    </span>
                  </div>
                  <label className="block">
                    <span className="text-sm font-medium text-ink-700 mb-1.5 flex items-center gap-1.5">
                      <FileUp className="w-4 h-4 text-brand-500" /> 支付凭证截图（可选）
                    </span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setVoucherFile(e.target.files?.[0] || null)}
                      className="block w-full text-sm text-ink-500 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-600 hover:file:bg-brand-100"
                    />
                    {voucherFile && (
                      <p className="text-xs text-emerald-600 mt-1">已选择：{voucherFile.name}</p>
                    )}
                  </label>
                  <div>
                    <label className="block text-sm font-medium text-ink-700 mb-1.5">转账说明（可选）</label>
                    <textarea
                      value={remark}
                      onChange={(e) => setRemark(e.target.value)}
                      rows={2}
                      maxLength={200}
                      placeholder="例如：微信转账 20 元，付款人 张三"
                      className="w-full border border-ink-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-400"
                    />
                  </div>
                  <button
                    onClick={handleSubmitVoucher}
                    disabled={submitting}
                    className="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-sm font-medium shadow-soft hover:from-emerald-600 hover:to-teal-700 transition-all disabled:opacity-60"
                  >
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin inline mr-1" /> : null}
                    提交凭证
                  </button>
                  <p className="text-center text-xs text-ink-400 flex items-center justify-center gap-1">
                    <XCircle className="w-3 h-3" /> 审核结果将在订单列表中展示
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
