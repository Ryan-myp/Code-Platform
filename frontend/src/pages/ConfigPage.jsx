import React, { useState, useEffect } from 'react'
import { Settings, Save, Loader2, CheckCircle2, AlertCircle, Key, Globe, Cpu } from 'lucide-react'

export default function ConfigPage() {
  const [apiKey, setApiKey] = useState('')
  const [apiUrl, setApiUrl] = useState('')
  const [modelName, setModelName] = useState('')
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  // 从后端获取当前配置（不经过 localStorage，确保安全）
  useEffect(() => {
    fetch('/api/config')
      .then(res => res.json())
      .then(data => {
        if (data.has_api_key) setApiKey('••••••••') // 隐藏真实密钥，仅显示已设置标识
        setApiUrl(data.api_url || '')
        setModelName(data.model_name || '')
      })
      .catch(() => {})
  }, [])

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setError('API Key 不能为空')
      return
    }
    if (!apiUrl.trim()) {
      setError('API URL 不能为空')
      return
    }

    setSaving(true)
    setError('')
    setSuccess(false)

    try {
      // ✅ 关键修复：绝不将 API Key 存入 localStorage！只向后端发送
      const response = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          api_url: apiUrl,
          model_name: modelName || 'agnes-2.0-flash'
        })
      })

      if (response.ok) {
        setSuccess(true)
        setTimeout(() => setSuccess(false), 3000)
      } else {
        setError(`保存失败：请检查后端服务` + (await response.text()))
      }
    } catch (err) {
      setError(`连接失败：` + err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl shadow-lg mb-6">
            <Settings className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight mb-3">系统配置</h1>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">配置 AI 模型接入信息</p>
        </div>

        {/* Configuration Form */}
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
            <h2 className="text-lg font-bold text-gray-900 flex items-center">
              <Cpu className="w-5 h-5 text-blue-600 mr-2" />
              模型配置
            </h2>
          </div>
          
          <div className="p-6 space-y-6">
            {/* API Key */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                <Key className="w-4 h-4 inline mr-1" />
                API Key
              </label>
              <input
                type="password"
                className="w-full p-3 border border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all text-sm font-mono"
                placeholder="sk-xxx...xxxx"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <p className="mt-1 text-xs text-red-600 font-medium">🔐 API Key 仅在后端数据库加密存储，绝不保存在浏览器中</p>
            </div>

            {/* API URL */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                <Globe className="w-4 h-4 inline mr-1" />
                API URL
              </label>
              <input
                type="text"
                className="w-full p-3 border border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all text-sm font-mono"
                placeholder="https://api.example.com/v1/chat/completions"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
              />
              <p className="mt-1 text-xs text-gray-500">OpenAI 兼容的 API 地址</p>
            </div>

            {/* Model Name */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                <Cpu className="w-4 h-4 inline mr-1" />
                模型名称
              </label>
              <input
                type="text"
                className="w-full p-3 border border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all text-sm font-mono"
                placeholder="agnes-2.0-flash"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
              />
              <p className="mt-1 text-xs text-gray-500">可选，留空则使用默认模型</p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="px-6 py-4 border-t border-gray-100 bg-gray-50">
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 px-6 rounded-xl hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-bold text-lg transition-all duration-200 shadow-lg hover:shadow-xl flex items-center justify-center"
            >
              {saving ? (
                <>
                  <Loader2 className="w-6 h-6 mr-3 animate-spin" />
                  保存中...
                </>
              ) : (
                <>
                  <Save className="w-6 h-6 mr-3" />
                  保存配置
                </>
              )}
            </button>

            {/* Success/Error Messages */}
            {success && (
              <div className="mt-4 bg-green-50 border border-green-200 rounded-xl p-4 flex items-start">
                <CheckCircle2 className="w-5 h-5 text-green-600 mr-2 flex-shrink-0 mt-0.5" />
                <p className="text-green-700 text-sm font-medium">配置保存成功！API Key 已在后端安全存储。</p>
              </div>
            )}
            {error && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-xl p-4 flex items-start">
                <AlertCircle className="w-5 h-5 text-red-600 mr-2 flex-shrink-0 mt-0.5" />
                <p className="text-red-700 text-sm font-medium">{error}</p>
              </div>
            )}
          </div>
        </div>

        {/* Tips */}
        <div className="mt-8 bg-blue-50 rounded-2xl border border-blue-100 p-6">
          <h3 className="text-lg font-bold text-blue-900 mb-3">💡 安全提示</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li>✓ API Key 不会存储在 localStorage 或浏览器缓存中</li>
            <li>✓ 所有配置均加密保存在后端 SQLite 数据库中</li>
            <li>✓ 配置接口需要认证 Token 才能访问（需先登录）</li>
            <li>✓ 建议启用 JWT 鉴权保护所有敏感端点</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
