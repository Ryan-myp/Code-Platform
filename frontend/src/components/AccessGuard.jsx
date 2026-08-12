import React, { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Lock, Crown, ArrowLeft, Check, Sparkles } from 'lucide-react'
import { Button } from './ui'
import useAccess from '../hooks/useAccess'
import { api } from '../lib/api'

const REQUIRE_LABEL = {
  pro: '专业版会员',
  vip: '至尊会员',
}

/**
 * 页面访问守卫（v9.3）
 * - 不可见页面：重定向到首页（与后端 404 语义一致）
 * - 锁定页面：展示会员引导页 + 价格对比（商业化转化）
 * 用法：<AccessGuard path="/ppt-factory"><PPTFactoryPage /></AccessGuard>
 */
export default function AccessGuard({ path, children }) {
  const navigate = useNavigate()
  const { getPageStatus } = useAccess()
  const status = getPageStatus(path)
  const [prices, setPrices] = useState(null)

  useEffect(() => {
    if (status.locked) {
      api
        .get('/api/stripe/prices')
        .then((res) => setPrices(res.data))
        .catch(() => setPrices(null))
    }
  }, [status.locked])

  if (status.loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!status.visible) {
    return <Navigate to="/home" replace />
  }

  if (status.locked) {
    const label = REQUIRE_LABEL[status.requires] || '会员专属'
    const pro = prices?.pro
    const vip = prices?.vip
    return (
      <div className="max-w-2xl mx-auto py-14 px-4 text-center">
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-glow">
          <Lock className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-xl font-semibold text-ink-900 mb-2">该功能为{label}专属</h2>
        <p className="text-sm text-ink-500 mb-8 leading-relaxed">
          开通会员即可解锁此功能，同时畅享更高额度、全部专业工具与优先服务。
        </p>

        {/* 价格对比 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8 text-left">
          <div className="rounded-2xl border border-ink-200 bg-white p-6 shadow-soft">
            <div className="flex items-center justify-between mb-3">
              <span className="font-semibold text-ink-900">专业版</span>
              <span className="text-xs px-2 py-1 rounded-full bg-indigo-50 text-indigo-600">推荐</span>
            </div>
            <p className="text-3xl font-bold text-ink-900 mb-1">
              {pro?.amount ? `¥${(pro.amount / 100).toFixed(0)}` : '¥19.9'}
              <span className="text-sm font-normal text-ink-400">/月</span>
            </p>
            <ul className="space-y-2 text-sm text-ink-600 mt-4">
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />每日 200 次 AI 调用（免费版 30 次）</li>
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />全部专业工具与高级模型</li>
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />解锁{label}专属功能</li>
            </ul>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-gradient-to-b from-amber-50 to-white p-6 shadow-soft">
            <div className="flex items-center justify-between mb-3">
              <span className="font-semibold text-ink-900">至尊版</span>
              <Sparkles className="w-4 h-4 text-amber-500" />
            </div>
            <p className="text-3xl font-bold text-ink-900 mb-1">
              {vip?.amount ? `¥${(vip.amount / 100).toFixed(0)}` : '¥99'}
              <span className="text-sm font-normal text-ink-400">/月</span>
            </p>
            <ul className="space-y-2 text-sm text-ink-600 mt-4">
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />AI 调用不限次</li>
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />优先生成通道，高峰免排队</li>
              <li className="flex items-start gap-2"><Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />全部模板与插件特权</li>
            </ul>
          </div>
        </div>

        <div className="flex items-center justify-center gap-3">
          <Button variant="secondary" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            返回
          </Button>
          <Button onClick={() => navigate('/membership')}>
            <Crown className="w-4 h-4 mr-1.5" />
            立即开通
          </Button>
        </div>
      </div>
    )
  }

  return children
}
