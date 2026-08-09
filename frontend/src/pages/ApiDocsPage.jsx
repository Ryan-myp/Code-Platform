import React, { useState, useEffect } from 'react'
import {
  Key,
  Copy,
  Trash2,
  ExternalLink,
  Code,
  Terminal,
  Shield,
  Clock,
  Plus,
  Eye,
  EyeOff,
  Zap,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge, ConfirmDialog, Modal } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

export default function ApiDocsPage() {
  const toast = useToast()
  const [keys, setKeys] = useState([])
  const [docs, setDocs] = useState(null)
  const [creating, setCreating] = useState(false)
  const [newKey, setNewKey] = useState(null)
  const [deleteId, setDeleteId] = useState(null)
  const [showFullKey, setShowFullKey] = useState({})
  const [loaded, setLoaded] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createLabel, setCreateLabel] = useState('')

  const loadData = async () => {
    try {
      const [keysRes, docsRes] = await Promise.all([
        api.get('/api/api-keys'),
        api.get('/api/open/docs'),
      ])
      setKeys(keysRes.data || [])
      setDocs(docsRes.data)
    } catch {
      /* 静默失败，不阻塞 UI */
    }
    setLoaded(true)
  }

  useEffect(() => {
    loadData()
  }, [])

  const createKey = async () => {
    setCreating(true)
    try {
      const res = await api.post('/api/api-keys', { label: createLabel.trim() })
      setNewKey(res.data)
      setCreateOpen(false)
      setCreateLabel('')
      loadData()
      toast.success('API Key 创建成功')
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    }
    setCreating(false)
  }

  const deleteKey = async () => {
    if (!deleteId) return
    try {
      await api.delete(`/api/api-keys/${deleteId}`)
      setKeys((prev) => prev.filter((k) => k.id !== deleteId))
      toast.success('已吊销')
    } catch (e) {
      toast.error(e.message)
    }
    setDeleteId(null)
  }

  const copyKey = (key) => {
    navigator.clipboard.writeText(key)
    toast.success('已复制到剪贴板')
  }

  const toggleShow = (id) => {
    setShowFullKey((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="API开放平台"
        description="创建个人API Key，将小团智能平台的AI能力集成到你的应用中"
        icon={Terminal}
        iconColor="from-violet-500 to-purple-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：Key管理 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Key className="w-4 h-4 text-violet-500" /> 我的API Keys
            </h3>
            {!loaded ? (
              <button onClick={loadData} className="text-sm text-violet-500 hover:underline">
                加载数据
              </button>
            ) : keys.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无API Key</div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {keys.map((k) => (
                  <div key={k.id} className="p-3 bg-gray-50 rounded-xl">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 flex items-center gap-1">
                          <span className="font-mono">{k.prefix}•••</span>
                          <button
                            onClick={() => toggleShow(k.id)}
                            className="text-gray-400 hover:text-violet-500"
                          >
                            {showFullKey[k.id] ? (
                              <EyeOff className="w-3 h-3" />
                            ) : (
                              <Eye className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                        {k.label && <div className="text-xs text-gray-500 mt-0.5">{k.label}</div>}
                      </div>
                      <button
                        onClick={() => setDeleteId(k.id)}
                        className="p-1 text-gray-300 hover:text-red-500"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      创建于 {k.created_at?.slice(0, 10)}
                      {k.last_used && ` · 最近使用 ${k.last_used.slice(0, 10)}`}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <Button
              variant="primary"
              icon={Plus}
              loading={creating}
              onClick={() => setCreateOpen(true)}
              className="w-full mt-3"
            >
              创建新 Key
            </Button>
          </Card>

          {/* 新创建的Key提示 */}
          {newKey && (
            <Card className="border-amber-300 bg-amber-50">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <h3 className="font-semibold text-amber-800 text-sm">新 Key 已生成</h3>
              </div>
              <div className="p-3 bg-white rounded-lg font-mono text-xs text-amber-700 break-all mb-2">
                {newKey.api_key}
              </div>
              <div className="flex gap-2">
                <Button size="sm" icon={Copy} onClick={() => copyKey(newKey.api_key)}>
                  复制
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setNewKey(null)}>
                  关闭
                </Button>
              </div>
              <p className="text-xs text-amber-600 mt-2">请立即保存，关闭后无法再次查看完整Key</p>
            </Card>
          )}

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-gray-500" /> 使用说明
            </h3>
            <div className="space-y-2 text-xs text-gray-600">
              <div>1. 创建API Key</div>
              <div>
                2. 在请求头中添加：
                <code className="px-1.5 py-0.5 bg-gray-100 rounded text-violet-600">
                  Authorization: Bearer YOUR_KEY
                </code>
              </div>
              <div>
                3. 发送请求到{' '}
                <code className="px-1.5 py-0.5 bg-gray-100 rounded text-violet-600">
                  https://platform.xiaotuan.ai/api/...
                </code>
              </div>
            </div>
          </Card>
        </div>

        {/* 右侧：API文档 */}
        <div className="lg:col-span-2 space-y-4">
          {!docs ? (
            <Empty icon={Code} title="加载API文档" description="点击左侧加载数据查看API文档" />
          ) : (
            <Card>
              <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
                <Code className="w-4 h-4 text-violet-500" /> {docs.title} {docs.version}
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                基础URL:{' '}
                <code className="px-2 py-0.5 bg-gray-100 rounded text-violet-600">
                  {docs.base_url}
                </code>
                <span className="mx-2">·</span>
                认证: <Badge color="violet">{docs.auth}</Badge>
                <span className="mx-2">·</span>
                频率限制: <span className="text-xs">{docs.rate_limit}</span>
              </p>
              <div className="space-y-3">
                {docs.endpoints?.map((ep, i) => (
                  <div key={i} className="p-4 rounded-xl bg-gray-50 border border-gray-100">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge color="blue">{ep.method}</Badge>
                      <code className="text-sm font-medium text-gray-800">{ep.path}</code>
                    </div>
                    <p className="text-xs text-gray-500 mb-2">{ep.description}</p>
                    {ep.body && (
                      <pre className="p-3 bg-gray-900 text-green-400 rounded-lg text-xs overflow-x-auto">
                        {JSON.stringify(ep.body, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={deleteKey}
        title="吊销API Key？"
        message="吊销后使用该Key的所有请求将立即失效，此操作不可撤销。"
        confirmLabel="确认吊销"
        icon={Trash2}
      />

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="创建 API Key"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button variant="primary" loading={creating} onClick={createKey}>
              创建
            </Button>
          </>
        }
      >
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">
            备注标签（可选，便于区分用途）
          </label>
          <input
            value={createLabel}
            onChange={(e) => setCreateLabel(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && createKey()}
            autoFocus
            placeholder="如：我的小程序 / 数据分析脚本"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
          />
          <p className="text-xs text-gray-400 mt-2">
            Key 创建后通过 Bearer 认证调用平台 AI 能力，配额随你的账号额度，也可用于 OpenAI 兼容接口（/v1/chat/completions）。
          </p>
        </div>
      </Modal>
    </div>
  )
}
