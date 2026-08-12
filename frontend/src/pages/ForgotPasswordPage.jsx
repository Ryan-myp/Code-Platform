import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Mail, CheckCircle, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'

export default function ForgotPasswordPage() {
  const [step, setStep] = useState('email') // email | token | reset
  const [username, setUsername] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSendToken = async (e) => {
    e.preventDefault()
    if (!username.trim()) { setError('请输入用户名'); return }
    setLoading(true); setError(''); setSuccess('')
    try {
      await api.post('/api/auth/forgot-password', { username: username.trim() })
      setSuccess('重置令牌已生成！开发模式下令牌已记录在服务器日志中。')
      setStep('token')
    } catch (err) {
      setError(err.response?.data?.detail || '发送失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async (e) => {
    e.preventDefault()
    if (newPassword.length < 6) { setError('密码至少 6 位'); return }
    if (newPassword !== confirmPassword) { setError('两次密码不一致'); return }
    setLoading(true); setError(''); setSuccess('')
    try {
      await api.post('/api/auth/reset-password', { token: token.trim(), new_password: newPassword })
      setSuccess('密码已重置！即将跳转到登录页...')
      setTimeout(() => navigate('/'), 2000)
    } catch (err) {
      setError(err.response?.data?.detail || '重置失败，请检查令牌是否有效')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-indigo-50 to-blue-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-200/30 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-200/30 rounded-full blur-3xl" />
      </div>
      <div className="relative bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 w-full max-w-md border border-white/60">
        <button onClick={() => navigate('/')} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" /> 返回登录
        </button>
        <div className="text-center mb-6">
          <div className="w-14 h-14 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-purple-500/30">
            <Mail className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-xl font-bold text-gray-900">重置密码</h1>
          <p className="text-gray-500 mt-1 text-sm">
            {step === 'email' && '输入用户名，我们将为你生成重置令牌'}
            {step === 'token' && '输入令牌后设置新密码'}
            {step === 'reset' && '设置你的新密码'}
          </p>
        </div>

        {step === 'email' && (
          <form onSubmit={handleSendToken} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">用户名</label>
              <input type="text" value={username} onChange={e => setUsername(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                placeholder="请输入你的用户名" autoComplete="username" />
            </div>
            {error && <p className="text-red-500 text-sm flex items-center gap-1"><AlertCircle className="w-4 h-4" />{error}</p>}
            {success && <p className="text-emerald-600 text-sm flex items-center gap-1"><CheckCircle className="w-4 h-4" />{success}</p>}
            <button type="submit" disabled={loading}
              className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-2.5 rounded-xl font-medium hover:from-purple-700 hover:to-indigo-700 disabled:opacity-60 transition-all shadow-lg shadow-purple-500/30 flex items-center justify-center gap-2">
              {loading ? <><Loader2 className="w-4 h-4 animate-spin" />生成令牌中…</> : '生成重置令牌'}
            </button>
          </form>
        )}

        {step === 'token' && (
          <form onSubmit={handleSendToken} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">查看令牌</label>
              <p className="text-xs text-gray-500 mb-2">令牌已发送至服务器日志。在开发环境中，你可以在终端查看：</p>
              <div className="p-3 bg-gray-100 rounded-xl text-sm font-mono text-gray-600 break-all">
                查看终端输出中的 &quot;password reset token&quot; 日志
              </div>
            </div>
            <button type="button" onClick={() => setStep('token')} disabled
              className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-2.5 rounded-xl font-medium disabled:opacity-60 shadow-lg shadow-purple-500/30">
              我已查看令牌，继续设置密码
            </button>
          </form>
        )}

        {step === 'reset' && (
          <form onSubmit={handleReset} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">重置令牌</label>
              <input type="text" value={token} onChange={e => setToken(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70 font-mono"
                placeholder="粘贴从日志中获取的令牌" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">新密码</label>
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                placeholder="至少 6 位" autoComplete="new-password" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">确认新密码</label>
              <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all bg-white/70"
                placeholder="再次输入新密码" autoComplete="new-password" />
            </div>
            {error && <p className="text-red-500 text-sm flex items-center gap-1"><AlertCircle className="w-4 h-4" />{error}</p>}
            {success && <p className="text-emerald-600 text-sm flex items-center gap-1"><CheckCircle className="w-4 h-4" />{success}</p>}
            <button type="submit" disabled={loading}
              className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-2.5 rounded-xl font-medium hover:from-purple-700 hover:to-indigo-700 disabled:opacity-60 transition-all shadow-lg shadow-purple-500/30 flex items-center justify-center gap-2">
              {loading ? <><Loader2 className="w-4 h-4 animate-spin" />重置中…</> : '重置密码'}
            </button>
          </form>
        )}

        {/* 步骤指示 */}
        <div className="mt-6 flex items-center justify-center gap-2">
          {['email', 'token', 'reset'].map((s, i) => (
            <div key={s} className={`w-2 h-2 rounded-full ${step === s ? 'bg-purple-600 w-6' : 'bg-gray-300'}`} />
          ))}
        </div>

        <div className="mt-4 text-center">
          <button onClick={() => navigate('/')} className="text-sm text-purple-600 hover:text-purple-700 font-medium">
            想起密码了？返回登录
          </button>
        </div>
      </div>
    </div>
  )
}
