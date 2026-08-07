import React, { useState, useEffect, useCallback } from 'react'
import {
  Settings,
  Save,
  RefreshCw,
  Eye,
  EyeOff,
  Key,
  Globe,
  Cpu,
  CheckCircle2,
  Wifi,
  Plus,
  Trash2,
  Loader2,
  Bell,
  Mail,
  Webhook,
  Send,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatDateTime } from '../lib/format'
import { Button, PageHeader, Badge, PageLoading, ErrorState } from '../components/ui'

// 掩码占位符（与后端脱敏返回一致）
const MASKED_PREFIX = '••••'
const DEFAULT_API_URL = 'https://api.agnes-ai.cn/v1'
const DEFAULT_MODEL = 'agnes-2.5-flash'

export default function ConfigPage() {
  const toast = useToast()
  const [apiKey, setApiKey] = useState('')
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL)
  const [modelName, setModelName] = useState(DEFAULT_MODEL)
  const [showKey, setShowKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [config, setConfig] = useState(null)
  const [errors, setErrors] = useState({})
  // 模型列表管理（每个模型可独立配置 base_url / api_key 多供应商接入）
  const [models, setModels] = useState([])
  const [newModelName, setNewModelName] = useState('')
  const [newModelBaseUrl, setNewModelBaseUrl] = useState('')
  const [newModelKey, setNewModelKey] = useState('')
  const [addingModel, setAddingModel] = useState(false)
  const [deletingModel, setDeletingModel] = useState('')
  const [editingModel, setEditingModel] = useState(null) // 编辑弹窗
  const [savingModel, setSavingModel] = useState(false)

  // ── 通知渠道配置 ──
  const [notifyCfg, setNotifyCfg] = useState(null)
  const [savingNotify, setSavingNotify] = useState(false)
  const [testingEmail, setTestingEmail] = useState(false)
  const [testingWebhook, setTestingWebhook] = useState(false)

  const fetchNotifyConfig = useCallback(async () => {
    try {
      const res = await api.get('/api/notify/config')
      setNotifyCfg(res.data || {})
    } catch {
      setNotifyCfg(null)
    }
  }, [])

  useEffect(() => {
    fetchNotifyConfig()
  }, [fetchNotifyConfig])

  const handleSaveNotify = async () => {
    if (!notifyCfg) return
    setSavingNotify(true)
    try {
      await api.put('/api/notify/config', notifyCfg)
      toast.success('通知配置已保存')
      fetchNotifyConfig()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSavingNotify(false)
    }
  }

  const handleTestEmail = async () => {
    setTestingEmail(true)
    try {
      const res = await api.post('/api/notify/test-email')
      toast.success(res.data?.message || '测试邮件已发送')
    } catch (e) {
      toast.error(e.message || '测试邮件失败')
    } finally {
      setTestingEmail(false)
    }
  }

  const handleTestWebhook = async () => {
    setTestingWebhook(true)
    try {
      const res = await api.post('/api/notify/test-webhook')
      toast.success(res.data?.message || 'Webhook 测试成功')
    } catch (e) {
      toast.error(e.message || 'Webhook 测试失败')
    } finally {
      setTestingWebhook(false)
    }
  }

  const setNotifyField = (key, val) => setNotifyCfg((p) => ({ ...(p || {}), [key]: val }))

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/config')
      const data = res.data
      setConfig(data)
      setApiUrl(data.api_url || data.agnes_api_base || DEFAULT_API_URL)
      setModelName(data.model_name || DEFAULT_MODEL)
      setModels(Array.isArray(data.models) ? data.models : [])
      // 已配置则展示掩码占位，留空表示不修改
      setApiKey(data.api_key || data.agnes_api_key || '')
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  const isKeyMasked = apiKey.startsWith(MASKED_PREFIX)

  const validate = () => {
    const e = {}
    if (!apiUrl.trim()) e.apiUrl = 'API URL 不能为空'
    else if (!/^https?:\/\//i.test(apiUrl.trim()))
      e.apiUrl = 'API URL 需以 http:// 或 https:// 开头'
    if (!modelName.trim()) e.modelName = '请选择默认模型'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSave = async () => {
    if (!validate()) {
      toast.error('请修正表单中的错误')
      return
    }
    setSaving(true)
    try {
      // 掩码占位表示不修改 API Key
      const payload = {
        api_url: apiUrl.trim(),
        model_name: modelName.trim(),
        api_key: isKeyMasked ? '' : apiKey.trim(),
      }
      await api.post('/api/config/save', payload)
      toast.success('配置保存成功')
      fetchConfig()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!apiUrl.trim() || !/^https?:\/\//i.test(apiUrl.trim())) {
      toast.error('请先填写合法的 API URL')
      return
    }
    if (!isKeyMasked && !apiKey.trim()) {
      toast.error('请先填写 API Key')
      return
    }
    setTesting(true)
    try {
      // 先保存最新输入，再探测后端连通性
      await api.post('/api/config/save', {
        api_url: apiUrl.trim(),
        model_name: modelName.trim(),
        api_key: isKeyMasked ? '' : apiKey.trim(),
      })
      await api.get('/api/config')
      toast.success('连接测试通过：后端服务正常，配置已生效')
      fetchConfig()
    } catch (e) {
      toast.error(`连接测试失败：${e.message}`)
    } finally {
      setTesting(false)
    }
  }

  const handleAddModel = async () => {
    const name = newModelName.trim()
    if (!name) {
      toast.error('请输入模型名称')
      return
    }
    setAddingModel(true)
    try {
      const res = await api.post('/api/config/models', {
        name,
        note: '',
        base_url: newModelBaseUrl.trim(),
        api_key: newModelKey.trim(),
      })
      setModels(res.data.models)
      setNewModelName('')
      setNewModelBaseUrl('')
      setNewModelKey('')
      toast.success(`模型 ${name} 已添加`)
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '添加模型失败')
    } finally {
      setAddingModel(false)
    }
  }

  const handleUpdateModel = async () => {
    if (!editingModel) return
    setSavingModel(true)
    try {
      const res = await api.put(`/api/config/models/${encodeURIComponent(editingModel.name)}`, {
        note: editingModel.note || '',
        base_url: (editingModel.base_url || '').trim(),
        api_key: editingModel.new_key || '', // 留空 = 保持不变
      })
      setModels(res.data.models)
      toast.success(`模型 ${editingModel.name} 已更新`)
      setEditingModel(null)
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '更新失败')
    } finally {
      setSavingModel(false)
    }
  }

  const handleDeleteModel = async (name) => {
    setDeletingModel(name)
    try {
      await api.delete(`/api/config/models/${encodeURIComponent(name)}`)
      toast.success(`模型 ${name} 已移除`)
      fetchConfig() // 刷新列表与默认模型（可能被自动回退）
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '移除模型失败')
    } finally {
      setDeletingModel('')
    }
  }

  if (loading) return <PageLoading />
  if (error) return <ErrorState message={`加载配置失败：${error.message}`} onRetry={fetchConfig} />

  const keyConfigured = isKeyMasked || (config?.api_key && config.api_key.startsWith(MASKED_PREFIX))

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <PageHeader
        title="系统配置"
        description="配置 AI 模型接入信息和系统参数"
        icon={Settings}
        iconColor="from-blue-500 to-indigo-600"
        actions={
          <Button variant="secondary" icon={RefreshCw} onClick={fetchConfig}>
            刷新
          </Button>
        }
      />

      {/* 配置卡 */}
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
                className={`w-full px-4 py-2.5 pr-12 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all font-mono ${errors.apiKey ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-blue-500/20 focus:border-blue-500'}`}
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-100 rounded-lg"
                title={showKey ? '隐藏' : '显示'}
              >
                {showKey ? (
                  <EyeOff className="w-4 h-4 text-gray-400" />
                ) : (
                  <Eye className="w-4 h-4 text-gray-400" />
                )}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {isKeyMasked ? 'API Key 已配置（留空或保留掩码则不修改）' : '留空则不修改'}
            </p>
          </div>

          {/* API URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Globe className="w-4 h-4 inline mr-1" />
              API URL <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="https://api.agnes-ai.cn/v1"
              className={`w-full px-4 py-2.5 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all font-mono ${errors.apiUrl ? 'border-red-300 focus:ring-red-500/20' : 'border-gray-200 focus:ring-blue-500/20 focus:border-blue-500'}`}
            />
            {errors.apiUrl ? (
              <p className="text-xs text-red-500 mt-1">{errors.apiUrl}</p>
            ) : (
              <p className="text-xs text-gray-500 mt-1">Agnes AI API 基础地址</p>
            )}
          </div>

          {/* 模型列表（每个模型独立配置 base_url / api_key，多供应商接入） */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Cpu className="w-4 h-4 inline mr-1" />
              模型列表
            </label>
            <div className="border border-gray-200 rounded-xl divide-y divide-gray-100 overflow-hidden">
              {models.length === 0 ? (
                <p className="px-4 py-3 text-xs text-gray-400">加载中…</p>
              ) : (
                models.map((m) => (
                  <div key={m.name} className="flex items-center gap-3 px-4 py-2.5">
                    <Cpu className="w-4 h-4 text-blue-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center flex-wrap gap-x-2 gap-y-0.5">
                        <span className="text-sm font-medium text-gray-800">{m.name}</span>
                        {m.note && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-500">
                            {m.note}
                          </span>
                        )}
                        {m.name === modelName && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600">
                            默认
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-[11px] text-gray-400 font-mono">
                        <span className="truncate max-w-[220px]">
                          {m.base_url ? m.base_url : 'API 地址：继承全局'}
                        </span>
                        <span className="flex-shrink-0">
                          {m.api_key ? `Key：${m.api_key}` : 'Key：继承全局'}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => setEditingModel({ ...m, new_key: '' })}
                      className="p-1.5 rounded-lg text-gray-300 hover:text-blue-500 hover:bg-blue-50 transition-colors"
                      title={`编辑 ${m.name}`}
                    >
                      <Settings className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteModel(m.name)}
                      disabled={deletingModel === m.name}
                      className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
                      title={`移除 ${m.name}`}
                    >
                      {deletingModel === m.name ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                ))
              )}
            </div>
            <div className="space-y-2 mt-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newModelName}
                  onChange={(e) => setNewModelName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddModel()}
                  placeholder="模型名称，如 gpt-4o / deepseek-v3"
                  className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:border-transparent outline-none transition-all font-mono text-sm focus:ring-blue-500/20 focus:border-blue-500"
                />
                <input
                  type="text"
                  value={newModelBaseUrl}
                  onChange={(e) => setNewModelBaseUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddModel()}
                  placeholder="API 地址（留空=继承全局）"
                  className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:border-transparent outline-none transition-all font-mono text-sm focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={newModelKey}
                  onChange={(e) => setNewModelKey(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddModel()}
                  placeholder="该模型的 API Key（留空=继承全局）"
                  className="flex-1 px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:border-transparent outline-none transition-all font-mono text-sm focus:ring-blue-500/20 focus:border-blue-500"
                />
                <button
                  onClick={handleAddModel}
                  disabled={addingModel}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 transition-colors disabled:opacity-60 flex-shrink-0"
                >
                  {addingModel ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                  添加模型
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-1.5">
              每个模型可配置独立的 API 地址与密钥（如智谱 / DeepSeek /
              豆包均为不同服务商）；留空则使用上方全局 API Key /
              URL。切换模型时自动使用对应供应商的地址与密钥
            </p>
          </div>

          {/* 默认模型（从模型列表中选择） */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Settings className="w-4 h-4 inline mr-1" />
              默认模型 <span className="text-red-500">*</span>
            </label>
            <select
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className={`w-full px-4 py-2.5 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${errors.modelName ? 'border-red-300' : 'border-gray-200 focus:ring-blue-500/20 focus:border-blue-500'}`}
            >
              {models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                  {m.note ? `（${m.note}）` : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Agent 默认使用的模型，保存后所有 AI 功能立即生效
            </p>
          </div>

          {/* 当前状态 */}
          <div className="bg-gray-50 rounded-xl p-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">当前状态</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-gray-500">API Key:</span>
                {keyConfigured ? (
                  <Badge status="active" dot label="已配置" />
                ) : (
                  <Badge status="inactive" dot label="未配置" />
                )}
              </div>
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-gray-500 flex-shrink-0">API URL:</span>
                <span className="font-mono text-xs text-gray-700 truncate">
                  {config?.api_url || config?.agnes_api_base || '未配置'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">默认模型:</span>
                <span className="text-gray-700">{config?.model_name || '未配置'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">版本:</span>
                <span className="text-gray-700">v7.0</span>
              </div>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-3">
          <Button variant="secondary" icon={Wifi} loading={testing} onClick={handleTest}>
            测试连接
          </Button>
          <Button variant="primary" icon={Save} loading={saving} onClick={handleSave}>
            保存配置
          </Button>
        </div>
      </div>

      {/* 提示 */}
      <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
        <h4 className="text-sm font-medium text-amber-800 mb-2 flex items-center gap-1.5">
          <CheckCircle2 className="w-4 h-4" />
          获取 API Key
        </h4>
        <p className="text-sm text-amber-700">
          访问{' '}
          <a
            href="https://api.agnes-ai.cn"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-amber-900"
          >
            api.agnes-ai.cn
          </a>{' '}
          注册账号并创建 API Key。免费额度足够个人使用。
        </p>
      </div>

      {/* 编辑模型弹窗 */}
      {editingModel && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
          onClick={() => setEditingModel(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-page-in"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-semibold text-gray-900 mb-1">编辑模型配置</h3>
            <p className="text-xs text-gray-400 mb-5 font-mono">{editingModel.name}</p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">备注</label>
                <input
                  type="text"
                  value={editingModel.note || ''}
                  onChange={(e) => setEditingModel({ ...editingModel, note: e.target.value })}
                  placeholder="如：DeepSeek / 智谱 GLM / 豆包"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:border-transparent outline-none transition-all text-sm focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  API 地址（留空=继承全局）
                </label>
                <input
                  type="text"
                  value={editingModel.base_url || ''}
                  onChange={(e) => setEditingModel({ ...editingModel, base_url: e.target.value })}
                  placeholder="如 https://api.deepseek.com/v1"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:border-transparent outline-none transition-all font-mono text-sm focus:ring-blue-500/20 focus:border-blue-500"
                />
                <p className="text-[11px] text-gray-400 mt-1">
                  当前：
                  {editingModel.base_url
                    ? editingModel.base_url
                    : '继承全局（' + (config?.api_url || config?.agnes_api_base || '未配置') + '）'}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  API Key（留空=保持不变）
                </label>
                <input
                  type="password"
                  value={editingModel.new_key || ''}
                  onChange={(e) => setEditingModel({ ...editingModel, new_key: e.target.value })}
                  placeholder={
                    editingModel.api_key
                      ? `已配置（${editingModel.api_key}），留空则不变`
                      : '未配置，留空则继承全局 Key'
                  }
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:border-transparent outline-none transition-all font-mono text-sm focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setEditingModel(null)}
                disabled={savingModel}
                className="px-4 py-2 text-sm rounded-xl text-gray-500 hover:bg-gray-100 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleUpdateModel}
                disabled={savingModel}
                className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-xl bg-blue-500 text-white font-medium hover:bg-blue-600 disabled:opacity-60 transition-colors"
              >
                {savingModel && <Loader2 className="w-4 h-4 animate-spin" />}
                保存修改
              </button>
            </div>
          </div>
        </div>
      )}

      {config?.updated_at && (
        <p className="text-xs text-gray-400 text-center">
          上次更新：{formatDateTime(config.updated_at)}
        </p>
      )}

      {/* ── 通知渠道配置 ── */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-soft">
            <Bell className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-gray-900">通知渠道配置</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              配置 SMTP 邮件 / Webhook 通知渠道，用于发布、任务等场景的消息推送
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            icon={Save}
            loading={savingNotify}
            onClick={handleSaveNotify}
          >
            保存通知配置
          </Button>
        </div>

        {!notifyCfg ? (
          <p className="text-sm text-gray-400 py-4">通知配置加载失败或暂无数据</p>
        ) : (
          <div className="space-y-5">
            {/* 邮件 */}
            <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium text-gray-800">SMTP 邮件</span>
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <span className="text-xs text-gray-500">启用</span>
                  <input
                    type="checkbox"
                    checked={!!notifyCfg.email_enabled}
                    onChange={(e) => setNotifyField('email_enabled', e.target.checked ? 1 : 0)}
                    className="w-4 h-4 rounded accent-blue-500"
                  />
                </label>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">SMTP 服务器</label>
                  <input
                    value={notifyCfg.email_smtp_host || ''}
                    onChange={(e) => setNotifyField('email_smtp_host', e.target.value)}
                    placeholder="smtp.qq.com"
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">端口</label>
                  <input
                    type="number"
                    value={notifyCfg.email_smtp_port ?? 587}
                    onChange={(e) =>
                      setNotifyField('email_smtp_port', Number(e.target.value) || 587)
                    }
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">账号</label>
                  <input
                    value={notifyCfg.email_smtp_user || ''}
                    onChange={(e) => setNotifyField('email_smtp_user', e.target.value)}
                    placeholder="xxx@qq.com"
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">密码（授权码）</label>
                  <input
                    type="password"
                    value={notifyCfg.email_smtp_password || ''}
                    onChange={(e) => setNotifyField('email_smtp_password', e.target.value)}
                    placeholder={
                      notifyCfg.email_smtp_password === '••••••••'
                        ? '已配置，留空保持不变'
                        : 'SMTP 授权码'
                    }
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">发件人</label>
                  <input
                    value={notifyCfg.email_from || ''}
                    onChange={(e) => setNotifyField('email_from', e.target.value)}
                    placeholder="小团智能平台 <xxx@qq.com>"
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">收件人</label>
                  <input
                    value={notifyCfg.email_to || ''}
                    onChange={(e) => setNotifyField('email_to', e.target.value)}
                    placeholder="接收通知的邮箱"
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none"
                  />
                </div>
              </div>
              <button
                onClick={handleTestEmail}
                disabled={testingEmail}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-blue-200 text-blue-600 text-xs font-medium hover:bg-blue-50 disabled:opacity-50 transition-all"
              >
                {testingEmail ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                发送测试邮件
              </button>
            </div>

            {/* Webhook */}
            <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Webhook className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm font-medium text-gray-800">Webhook</span>
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <span className="text-xs text-gray-500">启用</span>
                  <input
                    type="checkbox"
                    checked={!!notifyCfg.webhook_enabled}
                    onChange={(e) => setNotifyField('webhook_enabled', e.target.checked ? 1 : 0)}
                    className="w-4 h-4 rounded accent-indigo-500"
                  />
                </label>
              </div>
              <div className="grid grid-cols-1 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Webhook URL</label>
                  <input
                    value={notifyCfg.webhook_url || ''}
                    onChange={(e) => setNotifyField('webhook_url', e.target.value)}
                    placeholder="https://hooks.example.com/xxx"
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    密钥（X-Webhook-Secret）
                  </label>
                  <input
                    type="password"
                    value={notifyCfg.webhook_secret || ''}
                    onChange={(e) => setNotifyField('webhook_secret', e.target.value)}
                    placeholder={
                      notifyCfg.webhook_secret === '••••••••' ? '已配置，留空保持不变' : '可选'
                    }
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none font-mono"
                  />
                </div>
              </div>
              <button
                onClick={handleTestWebhook}
                disabled={testingWebhook}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-200 text-indigo-600 text-xs font-medium hover:bg-indigo-50 disabled:opacity-50 transition-all"
              >
                {testingWebhook ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                发送测试 Webhook
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
