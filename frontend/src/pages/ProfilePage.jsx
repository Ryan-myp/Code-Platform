import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  Camera,
  Copy,
  Crown,
  Flame,
  Gauge,
  Gift,
  Loader2,
  Lock,
  Mail,
  Save,
  Sparkles,
  TrendingUp,
  User as UserIcon,
  Zap,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { useI18n, LanguageSwitcher } from '../i18n/index.jsx'

// 会员等级元信息
const MEMBERSHIP_META = {
  free: {
    label: '免费版',
    desc: '每日 30 次调用',
    color: 'from-gray-500 to-gray-600',
    badge: 'bg-gray-100 text-gray-600',
    quota: 30,
  },
  pro: {
    label: '专业版',
    desc: '每日 200 次调用',
    color: 'from-blue-500 to-indigo-600',
    badge: 'bg-blue-50 text-blue-600',
    quota: 200,
  },
  vip: {
    label: '至尊版',
    desc: '无限调用',
    color: 'from-amber-500 to-orange-600',
    badge: 'bg-amber-50 text-amber-600',
    quota: 9999,
  },
}

export default function ProfilePage({ user, onUserUpdate }) {
  const toast = useToast()
  const { t } = useI18n()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  // 资料表单
  const [nickname, setNickname] = useState('')
  const [avatar, setAvatar] = useState('')
  const [email, setEmail] = useState('')
  const [saving, setSaving] = useState(false)

  // 密码表单
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [changingPwd, setChangingPwd] = useState(false)

  // 邀请有礼
  const [invite, setInvite] = useState(null)

  useEffect(() => {
    loadProfile()
    loadInvite()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadInvite = async () => {
    try {
      const res = await api.get('/api/invite')
      setInvite(res.data)
    } catch {
      /* 邀请信息加载失败不打扰用户 */
    }
  }

  const copyInvite = async () => {
    if (!invite?.invite_code) return
    const link = `${window.location.origin}/login?invite=${invite.invite_code}`
    try {
      await navigator.clipboard.writeText(link)
      toast.success('邀请链接已复制，好友注册双方各得 5 次额度')
    } catch {
      toast.error('复制失败，请手动复制邀请码')
    }
  }

  const loadProfile = async () => {
    try {
      const res = await api.get('/api/auth/me')
      const data = res.data
      setProfile(data)
      setNickname(data.nickname || '')
      setAvatar(data.avatar || '')
      setEmail(data.email || '')
    } catch (err) {
      toast.error(err.message || '加载个人资料失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveProfile = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await api.put('/api/auth/me', {
        nickname: nickname.trim(),
        avatar: avatar.trim(),
        email: email.trim(),
      })
      setProfile(res.data)
      // 同步全局用户信息
      if (onUserUpdate)
        onUserUpdate({ ...user, nickname: res.data.nickname, avatar: res.data.avatar })
      toast.success('个人资料已更新')
    } catch (err) {
      toast.error(err.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePwd = async (e) => {
    e.preventDefault()
    if (newPwd.length < 6) {
      toast.error('新密码至少 6 位')
      return
    }
    if (newPwd !== confirmPwd) {
      toast.error('两次输入的新密码不一致')
      return
    }
    setChangingPwd(true)
    try {
      await api.put('/api/auth/password', { old_password: oldPwd, new_password: newPwd })
      toast.success('密码已更新，下次登录请使用新密码')
      setOldPwd('')
      setNewPwd('')
      setConfirmPwd('')
    } catch (err) {
      toast.error(err.message || '修改密码失败')
    } finally {
      setChangingPwd(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-ink-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        加载中…
      </div>
    )
  }

  const meta = MEMBERSHIP_META[profile?.membership] || MEMBERSHIP_META.free
  const dailyQuota = profile?.daily_quota || meta.quota
  const usedToday = profile?.used_today || 0
  const remaining = profile?.remaining_today ?? Math.max(0, dailyQuota - usedToday)
  const usagePercent =
    dailyQuota >= 9999 ? 0 : Math.min(100, Math.round((usedToday / dailyQuota) * 100))
  const displayName = profile?.nickname || profile?.username || user?.username || '未命名用户'
  const avatarUrl = profile?.avatar || ''

  const inputCls =
    'w-full px-3.5 py-2.5 border border-ink-200 rounded-xl focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all text-sm bg-white'

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-page-in">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/home" className="p-2 hover:bg-ink-100 rounded-lg transition-colors text-ink-500">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-ink-900">个人中心</h1>
            <p className="text-sm text-ink-500">管理个人资料、账号安全与会员额度</p>
          </div>
        </div>
        <LanguageSwitcher />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左列：头像 + 额度 + 会员 */}
        <div className="space-y-6 lg:col-span-1">
          {/* 头像卡片 */}
          <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-6 text-center">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt="头像"
                className="w-20 h-20 rounded-2xl object-cover mx-auto shadow-soft border-2 border-brand-100"
              />
            ) : (
              <div className="w-20 h-20 bg-gradient-to-br from-brand-500 to-brand-700 rounded-2xl flex items-center justify-center mx-auto shadow-glow">
                <span className="text-white text-2xl font-bold">
                  {displayName[0]?.toUpperCase()}
                </span>
              </div>
            )}
            <h2 className="text-lg font-bold text-ink-900 mt-3">{displayName}</h2>
            <p className="text-sm text-ink-500">@{profile?.username}</p>
            <div className="flex items-center justify-center gap-2 mt-3">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${meta.badge}`}>
                {meta.label}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-ink-100 text-ink-600 capitalize">
                {profile?.role}
              </span>
            </div>
            {profile?.membership_expires && (
              <p className="text-xs text-ink-400 mt-2">
                <Crown className="w-3 h-3 inline mr-1 text-amber-500" />
                会员至 {profile.membership_expires?.slice(0, 10)}
              </p>
            )}
            {profile?.trial_expires && profile?.trial_expires > new Date().toISOString().slice(0, 10) && (
              <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                Pro 试用至 {profile.trial_expires.slice(0, 10)}（剩余 {Math.ceil((new Date(profile.trial_expires) - Date.now()) / 86400000)} 天）
              </p>
            )}
          </div>

          {/* 额度卡片 */}
          <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-ink-900 flex items-center gap-2">
                <Gauge className="w-4 h-4 text-brand-500" />
                今日额度
              </h3>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full bg-gradient-to-r ${meta.color} text-white`}
              >
                {meta.label}
              </span>
            </div>
            {meta.quota >= 9999 ? (
              <div className="text-center py-4">
                <Zap className="w-8 h-8 text-amber-500 mx-auto mb-2" />
                <p className="text-sm text-ink-600 font-medium">至尊会员 · 无限调用</p>
                <p className="text-xs text-ink-400 mt-1">畅享全部 AI 工具，不受次数限制</p>
              </div>
            ) : (
              <>
                <div className="flex items-end justify-between mb-2">
                  <div>
                    <span className="text-3xl font-bold text-ink-900">{remaining}</span>
                    <span className="text-sm text-ink-400 ml-1">次剩余</span>
                  </div>
                  <span className="text-xs text-ink-400">
                    已用 {usedToday} / {dailyQuota}
                  </span>
                </div>
                <div className="h-2.5 bg-ink-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${meta.color} transition-all duration-500`}
                    style={{ width: `${usagePercent}%` }}
                  />
                </div>
                <p className="text-xs text-ink-400 mt-2">每日 0 点自动重置</p>
              </>
            )}
            <div className="mt-4 pt-4 border-t border-ink-100 flex items-center justify-between text-sm">
              <span className="text-ink-500 flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4 text-brand-400" />
                累计使用
              </span>
              <span className="font-semibold text-ink-800">{profile?.total_usage || 0} 次</span>
            </div>
          </div>

          {/* 会员升级提示 */}
          <div className="bg-gradient-to-br from-brand-50 to-indigo-50 border border-brand-100 rounded-2xl p-5">
            <h3 className="font-semibold text-ink-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand-500" />
              会员权益
            </h3>
            <ul className="mt-3 space-y-2 text-sm text-ink-600">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-500 flex-shrink-0" />
                免费版：每日 {MEMBERSHIP_META.free.quota} 次
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" />
                专业版：每日 {MEMBERSHIP_META.pro.quota} 次
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                至尊版：无限使用
              </li>
            </ul>
            <div className="mt-4 pt-4 border-t border-brand-100 flex items-center justify-between gap-2">
              <span className="text-xs text-ink-500">
                当前：{meta.label}
                {profile?.membership_expires
                  ? ` · 至 ${profile.membership_expires.slice(0, 10)}`
                  : ''}
              </span>
              <Link
                to="/membership"
                className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-gradient-to-r from-brand-500 to-brand-700 text-white shadow-soft hover:from-brand-600 hover:to-brand-800 transition-all whitespace-nowrap"
              >
                升级会员 →
              </Link>
            </div>
          </div>

          {/* 邀请有礼 */}
          <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5">
            <h3 className="font-semibold text-ink-900 flex items-center gap-2">
              <Gift className="w-4 h-4 text-rose-500" />
              邀请有礼
            </h3>
            <p className="text-xs text-ink-500 mt-2">
              邀请好友注册，双方各得 <span className="font-semibold text-brand-600">5 次</span>{' '}
              一次性额度（不随每日重置）
            </p>
            {invite ? (
              <div className="mt-3 space-y-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-bold tracking-[0.3em] bg-ink-50 border border-ink-200 rounded-lg px-3 py-2 flex-1 text-center text-ink-800">
                    {invite.invite_code}
                  </span>
                  <button
                    onClick={copyInvite}
                    className="px-3 py-2 rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 text-sm font-medium flex items-center gap-1 transition-colors"
                  >
                    <Copy className="w-3.5 h-3.5" /> 复制链接
                  </button>
                </div>
                <p className="text-xs text-ink-400">
                  已邀请 {invite.invited_count} 人 · 每邀请 1 人奖励 5 次
                </p>
              </div>
            ) : (
              <p className="text-xs text-ink-400 mt-3">加载中…</p>
            )}
          </div>
        </div>

        {/* 右列：资料 + 密码 */}
        <div className="space-y-6 lg:col-span-2">
          {/* 基本资料 */}
          <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-6">
            <h3 className="font-semibold text-ink-900 flex items-center gap-2 mb-5">
              <UserIcon className="w-4 h-4 text-brand-500" />
              基本资料
            </h3>
            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-ink-700 mb-1.5">昵称</label>
                  <input
                    type="text"
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                    className={inputCls}
                    placeholder="设置一个昵称"
                    maxLength={30}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink-700 mb-1.5">
                    用户名（不可修改）
                  </label>
                  <input
                    type="text"
                    value={profile?.username || ''}
                    disabled
                    className={`${inputCls} bg-ink-50 text-ink-400`}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink-700 mb-1.5">邮箱</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={`${inputCls} pl-10`}
                    placeholder="用于密码重置与试用提醒（如 xx@163.com）"
                    maxLength={120}
                  />
                </div>
                <p className="text-xs text-ink-400 mt-1.5">填写后可接收密码重置、试用到期等邮件通知</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink-700 mb-1.5">头像 URL</label>
                <div className="relative">
                  <Camera className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400" />
                  <input
                    type="text"
                    value={avatar}
                    onChange={(e) => setAvatar(e.target.value)}
                    className={`${inputCls} pl-10`}
                    placeholder="https://example.com/avatar.png（留空使用默认头像）"
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2.5 bg-gradient-to-r from-brand-500 to-brand-600 text-white rounded-xl font-medium hover:from-brand-600 hover:to-brand-700 disabled:opacity-60 transition-all shadow-soft flex items-center gap-2"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  保存资料
                </button>
              </div>
            </form>
          </div>

          {/* 修改密码 */}
          <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-6">
            <h3 className="font-semibold text-ink-900 flex items-center gap-2 mb-5">
              <Lock className="w-4 h-4 text-brand-500" />
              修改密码
            </h3>
            <form onSubmit={handleChangePwd} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-ink-700 mb-1.5">原密码</label>
                <input
                  type="password"
                  value={oldPwd}
                  onChange={(e) => setOldPwd(e.target.value)}
                  className={inputCls}
                  placeholder="请输入当前密码"
                  autoComplete="current-password"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-ink-700 mb-1.5">新密码</label>
                  <input
                    type="password"
                    value={newPwd}
                    onChange={(e) => setNewPwd(e.target.value)}
                    className={inputCls}
                    placeholder="至少 6 位"
                    autoComplete="new-password"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink-700 mb-1.5">
                    确认新密码
                  </label>
                  <input
                    type="password"
                    value={confirmPwd}
                    onChange={(e) => setConfirmPwd(e.target.value)}
                    className={inputCls}
                    placeholder="再次输入新密码"
                    autoComplete="new-password"
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={changingPwd || !oldPwd || !newPwd}
                  className="px-5 py-2.5 bg-ink-800 text-white rounded-xl font-medium hover:bg-ink-900 disabled:opacity-50 transition-all flex items-center gap-2"
                >
                  {changingPwd ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Flame className="w-4 h-4" />
                  )}
                  修改密码
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
