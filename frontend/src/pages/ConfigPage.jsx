import React, { useState, useEffect } from 'react'
import { 
  Settings, Save, Loader2, CheckCircle2, AlertCircle, 
  Key, Globe, Cpu, RefreshCw, Eye, EyeOff
} from 'lucide-react'

export default function ConfigPage() {
  const [apiKey, setApiKey] = useState('')
  const [apiUrl, setApiUrl] = useState('')
  const [modelName, setModelName] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const [config, setConfig] = useState(null)

  // 加载配置
  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config')
      const data = await res.json()
      setConfig(data)
      if (data.has_api_key) setApiKey('••••••••••••')
      setApiUrl(data.api_url || 'https://api.agnes-ai.cn/v1')
      setModelName(data.model_name || 'agnes-2.5-flash')
    } catch (err) {
      setError('加载配置失败')
    }
  }

  const handleSave = async () => {
    if (!apiUrl.trim()) {
      setError('API URL 不能为空')
      return
    }

    setSaving(true)
    setError('')
    setSuccess(false)

    try {
      const response = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey === '••••••••••••' ? '' : apiKey,
          api_url: apiUrl,
          model_name: modelName || 'agnes-2.5-flash'
        })
      })

      if (response.ok) {
        setSuccess(true)
        setTimeout(() => setSuccess(false), 3000)
        fetchConfig()
      } else {
        setError('保存失败，请检查后端服务')
      }
    } catch (err) {
      setError('连接失败：' + err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">系统配置</h1>
          <p className="text-gray-500 mt-1">配置 AI 模型接入信息和系统参数</p>
        </div>
        <button
          onClick={fetchConfig}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-xl hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4" />
          刷新
        </button>
      </div>

      {/* Success/Error Messages */}
      {success && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-xl flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          配置保存成功！
        </div>
      )}
      
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Configuration Card */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-blue-50 to-indigo-50">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-blue-600" />
            AI 模型配置
          </h2>
          <p className="text-sm text-gray-500 mt-1">配置 Agnes AI API 接入信息</p>
        </div>
        
        <div className="p-6 space-y-6">
          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Key className="w-4 h-4 inline mr-1" />
              API Key
            </label>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-xxxxxxxxxxxx"
                className="w-full px-4 py-2.5 pr-12 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
              />
              <button
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-100 rounded-lg"
              >
                {showKey ? <EyeOff className="w-4 h-4 text-gray-400" /> : <Eye className="w-4 h-4 text-gray-400" />}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {apiKey === '••••••••••••' ? 'API Key 已配置' : '留空则不修改'}
            </p>
          </div>

          {/* API URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Globe className="w-4 h-4 inline mr-1" />
              API URL
            </label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="https://api.agnes-ai.cn/v1"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
            />
            <p className="text-xs text-gray-500 mt-1">Agnes AI API 基础地址</p>
          </div>

          {/* Model Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Settings className="w-4 h-4 inline mr-1" />
              默认模型
            </label>
            <select
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="agnes-2.5-flash">agnes-2.5-flash (推荐)</option>
              <option value="agnes-2.5-pro">agnes-2.5-pro</option>
              <option value="gpt-4o">gpt-4o</option>
              <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">Agent 默认使用的模型</p>
          </div>

          {/* Status */}
          {config && (
            <div className="bg-gray-50 rounded-xl p-4">
              <h4 className="text-sm font-medium text-gray-700 mb-2">当前状态</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">API Key:</span>
                  <span className={`ml-2 ${config.has_api_key ? 'text-emerald-600' : 'text-red-600'}`}>
                    {config.has_api_key ? '已配置' : '未配置'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">API URL:</span>
                  <span className="ml-2 font-mono text-xs">{config.api_url || '未配置'}</span>
                </div>
                <div>
                  <span className="text-gray-500">默认模型:</span>
                  <span className="ml-2">{config.model_name || '未配置'}</span>
                </div>
                <div>
                  <span className="text-gray-500">版本:</span>
                  <span className="ml-2">v7.0</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            <span>保存配置</span>
          </button>
        </div>
      </div>

      {/* Tips */}
      <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
        <h4 className="text-sm font-medium text-amber-800 mb-2">💡 获取 API Key</h4>
        <p className="text-sm text-amber-700">
          访问{' '}
          <a href="https://api.agnes-ai.cn" target="_blank" rel="noopener noreferrer" className="underline hover:text-amber-900">
            api.agnes-ai.cn
          </a>
          {' '}注册账号并创建 API Key。免费额度足够个人使用。
        </p>
      </div>
    </div>
  )
}
