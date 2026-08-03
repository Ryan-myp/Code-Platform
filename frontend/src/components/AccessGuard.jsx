import React from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Lock, Crown, ArrowLeft } from 'lucide-react'
import { Button } from './ui'
import useAccess from '../hooks/useAccess'

const REQUIRE_LABEL = {
  pro: '专业版会员',
  vip: '至尊会员',
}

/**
 * 页面访问守卫（v9.3）
 * - 不可见页面：重定向到首页（与后端 404 语义一致）
 * - 锁定页面：展示会员引导页（后端已过滤，这里兜底直达 URL 的场景）
 * 用法：<AccessGuard path="/ppt-factory"><PPTFactoryPage /></AccessGuard>
 */
export default function AccessGuard({ path, children }) {
  const navigate = useNavigate()
  const { getPageStatus } = useAccess()
  const status = getPageStatus(path)

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
    return (
      <div className="max-w-md mx-auto py-20 text-center">
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-glow">
          <Lock className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-xl font-semibold text-ink-900 mb-2">该功能为{label}专属</h2>
        <p className="text-sm text-ink-500 mb-8 leading-relaxed">
          开通会员即可解锁此功能，同时畅享更高额度、全部专业工具与优先服务。
        </p>
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
