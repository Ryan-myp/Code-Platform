import React, { useState } from 'react'
import { useI18n } from '../i18n/index.jsx'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Loader2, Lock, User as UserIcon, UserPlus, AtSign, Sparkles, Wand2, Zap, Puzzle, Mail } from 'lucide-react'
import { api } from '../lib/api'

export default function LoginPage({ onLogin }) {
  const { t } = useI18n()
  const [mode, setMode] = useState('login') // login | register
  const [username, setUsername] = useState('')
  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [inviteCode, setInviteCode] = useState(
    () => new URLSearchParams(window.location.search).get('invite') || ''
  )
  // 分享来源（?share=code，注册时上报用于渠道转化统计）
  const [shareRef] = useState(() => new URLSearchParams(window.location.search).get('share') || '')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    // 前端校验
    if (!username.trim()) {
      setError(t('auth.username'))
      return
    }
    if (!password) {
      setError(t('auth.password'))
      return
    }
    if (mode === 'register') {
      if (password.length < 6) {
        setError('密码至少 6 位')
        return
      }
      if (password !== confirmPassword) {
        setError('两次输入的密码不一致')
        return
      }
    }
    setLoading(true)
    setError('')
    try {
      const url = mode === 'register' ? '/api/auth/register' : '/api/auth/login'
      const payload =
        mode === 'register'
          ? {
              username: username.trim(),
              nickname: nickname.trim() || undefined,
              email: email.trim() || undefined,
              password,
              invite_code: inviteCode.trim() || undefined,
              share_ref: shareRef || undefined,
            }
          : { username: username.trim(), password }
      const res = await api.post(url, payload)
      const { access_token, user } = res.data
      localStorage.setItem('token', access_token)
      localStorage.setItem('user', JSON.stringify(user))
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
      onLogin(user)
      navigate('/home')
    } catch (err) {
      setError(
        err.message || (mode === 'register' ? '注册失败，请重试' : '登录失败，请检查用户名和密码')
      )
    } finally {
      setLoading(false)
    }
  }

  const switchMode = (m) => {
    setMode(m)
    setError('')
  }

  // 演示账号一键填充（降低小白用户上手门槛）
  const fillDemoAccount = () => {
    setUsername('admin')
    setPassword('admin123')
    setError('')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-indigo-50 to-blue-50 flex items-center justify-center p-4">
      {/* 装饰背景 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-200/30 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-200/30 rounded-full blur-3xl" />
      </div>

      <div className="relative bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 w-full max-w-md border border-white/60">
        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-purple-500/30">
            <span className="text-white text-2xl font-bold">AI</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">小团智能平台</h1>
          <p className="text-gray-500 mt-2 text-sm">AI 赋能各行各业，智能解决工作难题</p>
        </div>

        {/* 登录 / 注册切换 */}
        <div className="grid grid-cols-2 gap-1 p-1 bg-gray-100/80 rounded-xl mb-6">
          <button
            type="button"
            onClick={() => switchMode('login')}
            className={`py-2 rounded-lg text-sm font-medium transition-all ${mode === 'login' ? 'bg-white shadow-soft text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
          >
            登录
          </button>
          <button
            type="button"
            onClick={() => switchMode('register')}
            className={`py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1 ${mode === 'register' ? 'bg-white shadow-soft text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
          >
            <UserPlus className="w-3.5 h-3.5" />
            注册
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">用户名</label>
            <div className="relative">
              <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                placeholder={t('auth.username')}
                autoComplete="username"
              />
            </div>
          </div>
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">昵称（可选）</label>
              <div className="relative">
                <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                  placeholder="给自己起个好记的名字"
                  maxLength={30}
                />
              </div>
            </div>
          )}
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱（选填）</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                  placeholder="用于密码重置与试用提醒（如 xx@163.com）"
                  maxLength={120}
                />
              </div>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-10 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                placeholder={mode === 'register' ? '请设置密码（至少 6 位）' : t('auth.password')}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                邀请码（选填）
              </label>
              <div className="relative">
                <UserPlus className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70 uppercase"
                  placeholder="填写好友邀请码，双方各得 5 次额度"
                  maxLength={12}
                />
              </div>
            </div>
          )}
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">确认密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                  placeholder="请再次输入密码"
                  autoComplete="new-password"
                />
              </div>
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 text-red-500 text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              <span>{error}</span>
            </div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-2.5 rounded-xl font-medium hover:from-purple-700 hover:to-indigo-700 disabled:opacity-60 transition-all shadow-lg shadow-purple-500/30 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {mode === 'register' ? '注册中…' : '登录中…'}
              </>
            ) : mode === 'register' ? (
              '注册并登录'
            ) : (
              t('auth.login_btn')
            )}
          </button>
        </form>

        {mode === 'login' && (
          <div className="mt-6 p-3 bg-purple-50/50 border border-purple-100 rounded-xl text-center">
            <p className="text-xs text-gray-500">
              默认账号：<span className="font-mono text-purple-600">admin</span> /{' '}
              <span className="font-mono text-purple-600">admin123</span>
            </p>
            <button
              type="button"
              onClick={fillDemoAccount}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-purple-600 hover:text-purple-700 bg-purple-100 hover:bg-purple-200/70 rounded-lg px-3 py-1.5 transition-colors"
            >
              <Zap className="w-3.5 h-3.5" />
              一键填入演示账号
            </button>
            <div className="mt-3">
              <button
                type="button"
                onClick={() => navigate('/forgot-password')}
                className="text-xs text-purple-500 hover:text-purple-700 underline underline-offset-2"
              >
                忘记密码？
              </button>
            </div>
          </div>
        )}
        {mode === 'register' && (
          <div className="mt-6 p-3 bg-indigo-50/50 border border-indigo-100 rounded-xl text-center">
            <p className="text-xs text-gray-500">
              注册即得 <span className="font-semibold text-purple-600">30 次/日</span>{' '}
              免费额度，填邀请码双方各得 <span className="font-semibold text-rose-500">5 次</span>{' '}
              奖励额度！
            </p>
          </div>
        )}

        {/* 平台能力亮点：让访客 3 秒感知平台价值 */}
        <div className="mt-5 pt-5 border-t border-gray-200/70">
          <div className="flex flex-wrap items-center justify-center gap-2">
            {[
              { icon: <Wand2 className="w-3.5 h-3.5" />, text: '54+ 效率工具' },
              { icon: <Puzzle className="w-3.5 h-3.5" />, text: 'AI 工坊全覆盖' },
              { icon: <Sparkles className="w-3.5 h-3.5" />, text: '多模型智能路由' },
            ].map((it) => (
              <span
                key={it.text}
                className="inline-flex items-center gap-1.5 text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-full px-3 py-1"
              >
                <span className="text-purple-500">{it.icon}</span>
                {it.text}
              </span>
            ))}
          </div>
          <p className="text-center text-[11px] text-gray-400 mt-2">
            从内容创作到代码研发，从数据分析到智能办公——一个平台解决你的全部工作
          </p>
        </div>
      </div>
    </div>
  )
}
