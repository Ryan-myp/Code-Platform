import React, { useState, useEffect } from 'react'
import {
  Send, Copy, Check, Sparkles, Clock, Settings2, Plus, Trash2, TestTube2,
  FileText, Image as ImageIcon, Film, Tag, Link2, Download, ExternalLink,
  MessageSquare, Music2, Clapperboard, AlertCircle, CheckCircle2, CircleDashed,
} from 'lucide-react'
import { Card, Button, Badge, Empty, PageHeader, Modal } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PLATFORMS = [
  {
    value: 'wechat', label: '微信公众号', icon: MessageSquare, color: 'from-emerald-500 to-green-600',
    border: 'border-emerald-200 bg-emerald-50', text: 'text-emerald-600',
    desc: '图文 / 图片 / 视频',
    auto: '图文支持自动发布（AppID/Secret）',
  },
  {
    value: 'douyin', label: '抖音', icon: Clapperboard, color: 'from-gray-700 to-gray-900',
    border: 'border-gray-200 bg-gray-50', text: 'text-gray-700',
    desc: '图片 / 视频',
    auto: '图片视频支持自动发布（开放平台审核后）',
  },
  {
    value: 'kuaishou', label: '快手', icon: Music2, color: 'from-orange-500 to-amber-600',
    border: 'border-orange-200 bg-orange-50', text: 'text-orange-600',
    desc: '图片 / 视频',
    auto: '图片视频支持自动发布（开放平台审核后）',
  },
]

const CONTENT_TYPES = [
  { value: 'article', label: '图文', icon: FileText },
  { value: 'image', label: '图片', icon: ImageIcon },
  { value: 'video', label: '视频', icon: Film },
]

const MODE_BADGE = {
  guide: { label: '引导式', color: 'blue' },
  auto: { label: '自动发布', color: 'green' },
  guide_fallback: { label: '自动失败·已回退', color: 'amber' },
}

const STATUS_BADGE = {
  pending: { label: '待发布', color: 'amber' },
  success: { label: '已发布', color: 'green' },
  failed: { label: '失败', color: 'red' },
}

function assetFull(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return (api.defaults.baseURL || 'http://localhost:8888') + url
}

const TABS = [
  { key: 'workbench', label: '发布工作台', icon: Send },
  { key: 'records', label: '发布记录', icon: Clock },
  { key: 'accounts', label: '账号配置', icon: Settings2 },
]

export default function PublishingPage() {
  const toast = useToast()
  const [tab, setTab] = useState('workbench')

  // ── 发布工作台状态 ──
  const [assets, setAssets] = useState({ articles: [], media: [] })
  const [assetTab, setAssetTab] = useState('articles')
  const [platform, setPlatform] = useState('wechat')
  const [contentType, setContentType] = useState('article')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [topicInput, setTopicInput] = useState('')
  const [topics, setTopics] = useState([])
  const [selectedAssets, setSelectedAssets] = useState([]) // [{url, name, type}]
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copiedKey, setCopiedKey] = useState('')

  // ── 记录 / 账号 ──
  const [records, setRecords] = useState([])
  const [accounts, setAccounts] = useState([])
  const [accForm, setAccForm] = useState({ platform: 'wechat', name: '', app_id: '', app_secret: '' })
  const [testingId, setTestingId] = useState('')
  const [detail, setDetail] = useState(null)

  useEffect(() => { loadAssets() }, [])
  useEffect(() => { if (tab === 'records') loadRecords() }, [tab])
  useEffect(() => { if (tab === 'accounts') loadAccounts() }, [tab])

  const loadAssets = async () => {
    try { const res = await api.get('/api/publish/assets'); setAssets(res.data || { articles: [], media: [] }) } catch (e) {}
  }
  const loadRecords = async () => {
    try { const res = await api.get('/api/publish/records'); setRecords(res.data || []) } catch (e) {}
  }
  const loadAccounts = async () => {
    try { const res = await api.get('/api/publish/accounts'); setAccounts(res.data || []) } catch (e) {}
  }

  // 平台切换时自动建议内容类型
  const switchPlatform = (p) => {
    setPlatform(p)
    setContentType(p === 'wechat' ? 'article' : 'image')
  }

  // 使用素材库中的文章
  const useArticle = (a) => {
    setTitle(a.title || '')
    setContent(a.result || a.prompt || '')
    setContentType('article')
    toast.success(`已加载文章：${(a.title || a.prompt || '').slice(0, 20)}`)
  }

  // 添加媒体素材
  const addMedia = (m) => {
    const url = m.url || m.media_url
    if (!url) return
    if (selectedAssets.some((s) => s.url === url)) { toast.error('该素材已在列表中'); return }
    const type = m.type === 'video' ? 'video' : 'image'
    setSelectedAssets((prev) => [...prev, { url, name: url.split('/').pop(), type, thumbnail: m.thumbnail || (type === 'image' ? url : '') }])
    setContentType(type)
    toast.success(`已加入素材：${url.split('/').pop()}`)
  }

  const removeAsset = (url) => setSelectedAssets((prev) => prev.filter((s) => s.url !== url))

  const addTopic = () => {
    const t = topicInput.trim().replace(/^#/, '')
    if (!t) return
    if (topics.includes(t)) { toast.error('话题已存在'); return }
    setTopics((prev) => [...prev, t]); setTopicInput('')
  }

  const submit = async () => {
    if (!title.trim() && contentType !== 'image') { toast.error('请填写标题'); return }
    if (contentType === 'article' && !content.trim()) { toast.error('请填写正文内容（可直接从素材库加载文章）'); return }
    if (selectedAssets.length === 0 && contentType !== 'article') { toast.error('请从素材库选择要发布的图片/视频'); return }
    setLoading(true); setResult(null)
    try {
      const res = await api.post('/api/publish/submit', {
        platform, content_type: contentType, title, content,
        topics, asset_urls: selectedAssets.map((s) => s.url),
      })
      setResult(res.data)
      loadRecords()
      toast.success(res.data.mode === 'auto' ? '已自动发布成功' : '素材包已生成')
    } catch (e) { toast.error(`发布失败：${e.message}`) }
    finally { setLoading(false) }
  }

  const copy = async (text, key) => {
    try { await navigator.clipboard.writeText(text); setCopiedKey(key); setTimeout(() => setCopiedKey(''), 1500) }
    catch { toast.error('复制失败') }
  }

  // ── 账号操作 ──
  const saveAccount = async () => {
    if (!accForm.platform) { toast.error('请选择平台'); return }
    try {
      const res = await api.post('/api/publish/accounts', accForm)
      toast.success(res.data.configured ? '账号已配置' : '账号已保存（未填完整凭据）')
      setAccForm({ platform: 'wechat', name: '', app_id: '', app_secret: '' })
      loadAccounts()
    } catch (e) { toast.error(e.message) }
  }

  const testAccount = async (id) => {
    setTestingId(id)
    try {
      const res = await api.post(`/api/publish/accounts/${id}/test`)
      toast.success(res.data.message || '连接成功')
    } catch (e) { toast.error(e.message) }
    finally { setTestingId('') }
  }

  const deleteAccount = async (id) => {
    try { await api.delete(`/api/publish/accounts/${id}`); loadAccounts(); toast.success('账号已删除') }
    catch (e) { toast.error(e.message) }
  }

  const platformMeta = PLATFORMS.find((p) => p.value === platform)
  const ctypeMeta = CONTENT_TYPES.find((c) => c.value === contentType)

  return (
    <div className="space-y-6">
      <PageHeader
        title="内容发布中心"
        description="文章、图片、视频一键发布到公众号 / 抖音 / 快手，支持引导式与自动发布"
        icon={Send}
        iconColor="from-blue-500 to-indigo-600"
      />

      {/* 统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '可发布文章', value: assets.articles?.length || 0, icon: FileText, color: 'from-blue-500 to-indigo-600' },
          { label: '图片视频素材', value: assets.media?.length || 0, icon: Film, color: 'from-pink-500 to-rose-600' },
          { label: '发布总次数', value: records.length, icon: Send, color: 'from-emerald-500 to-teal-600' },
          { label: '已配置账号', value: accounts.filter((a) => a.configured).length, icon: Settings2, color: 'from-amber-500 to-orange-600' },
        ].map((s, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center`}>
                <s.icon className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="text-xl font-bold text-gray-900">{s.value}</div>
                <div className="text-xs text-gray-500">{s.label}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tab 切换 */}
      <div className="flex gap-2">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === t.key ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-soft' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'workbench' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── 左列：发布设置 ── */}
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Send className="w-4 h-4 text-blue-500" /> 发布设置
              </h3>
              {/* 内容类型 */}
              <div className="grid grid-cols-3 gap-2 mb-3">
                {CONTENT_TYPES.map((c) => (
                  <button key={c.value} onClick={() => setContentType(c.value)}
                    className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg text-xs border transition-all ${
                      contentType === c.value ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium shadow-sm' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}>
                    <c.icon className="w-4 h-4" /> {c.label}
                  </button>
                ))}
              </div>
              {/* 标题 */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">标题</label>
                <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
                  placeholder={contentType === 'image' ? '图片描述（可选）' : '文章 / 视频标题'}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none" />
              </div>
              {/* 正文 */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">正文 / 文案 <span className="text-gray-400">（{content.length} 字）</span></label>
                <textarea value={content} onChange={(e) => setContent(e.target.value)}
                  placeholder={contentType === 'article' ? '文章正文，可在右侧素材库一键加载历史文章…' : '配文文案，可在文案工厂生成后粘贴…'}
                  rows={7} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none" />
              </div>
              {/* 话题 */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">话题标签（回车添加）</label>
                <div className="flex gap-2">
                  <input type="text" value={topicInput} onChange={(e) => setTopicInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTopic() } }}
                    placeholder="如：AI工具 效率办公" className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none" />
                  <Button variant="secondary" size="sm" icon={Plus} onClick={addTopic}>添加</Button>
                </div>
                {topics.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {topics.map((t, i) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700">
                        #{t}
                        <button onClick={() => setTopics(topics.filter((_, j) => j !== i))} className="text-blue-300 hover:text-red-500"><Trash2 className="w-3 h-3" /></button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {/* 已选素材 */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">发布素材（{selectedAssets.length}）</label>
                {selectedAssets.length === 0 ? (
                  <div className="px-3 py-3 rounded-lg border-2 border-dashed border-gray-200 text-center text-xs text-gray-400">
                    尚未选择素材，请从右侧素材库点击「加入素材」
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {selectedAssets.map((s) => (
                      <div key={s.url} className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-gray-50 border border-gray-100">
                        {s.thumbnail ? <img src={assetFull(s.thumbnail)} alt="" className="w-8 h-8 rounded object-cover flex-shrink-0" /> : (s.type === 'video' ? <Film className="w-4 h-4 text-gray-400 flex-shrink-0" /> : <ImageIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />)}
                        <span className="flex-1 text-xs text-gray-700 truncate">{s.name}</span>
                        <button onClick={() => removeAsset(s.url)} className="text-gray-300 hover:text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>

            {/* 平台选择 */}
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <ExternalLink className="w-4 h-4 text-indigo-500" /> 发布到
              </h3>
              <div className="space-y-2">
                {PLATFORMS.map((p) => (
                  <button key={p.value} onClick={() => switchPlatform(p.value)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left ${
                      platform === p.value ? `${p.border} ring-2 ring-blue-500/20` : 'border-gray-200 hover:bg-gray-50'
                    }`}>
                    <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${p.color} flex items-center justify-center flex-shrink-0`}>
                      <p.icon className="w-4.5 h-4.5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900">{p.label}</div>
                      <div className="text-xs text-gray-500">{p.desc}</div>
                    </div>
                    {platform === p.value && <CheckCircle2 className={`w-4 h-4 ${p.text} flex-shrink-0`} />}
                  </button>
                ))}
              </div>
              <div className="mt-3 px-3 py-2.5 rounded-lg bg-indigo-50 border border-indigo-100 text-xs text-indigo-600 flex items-start gap-2">
                <Sparkles className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <span>当前平台：{platformMeta.label} · 内容类型：{ctypeMeta.label}。{platformMeta.auto}；未配置或暂不支持时自动生成本引导式素材包。</span>
              </div>
            </Card>

            <Button variant="primary" size="lg" icon={Send} loading={loading} onClick={submit} className="w-full">
              {loading ? '发布中…' : '一键发布'}
            </Button>
          </div>

          {/* ── 右列：素材库 + 结果 ── */}
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" /> 素材库
                <span className="text-xs font-normal text-gray-400">点击文章「加载正文」或图片视频「加入素材」</span>
              </h3>
              <div className="flex gap-2 mb-4">
                {[
                  { key: 'articles', label: `文章（${assets.articles?.length || 0}）`, icon: FileText },
                  { key: 'media', label: `图片视频（${assets.media?.length || 0}）`, icon: Film },
                ].map((t) => (
                  <button key={t.key} onClick={() => setAssetTab(t.key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      assetTab === t.key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}>
                    <t.icon className="w-3.5 h-3.5" /> {t.label}
                  </button>
                ))}
              </div>

              {assetTab === 'articles' ? (
                assets.articles?.length ? (
                  <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                    {assets.articles.map((a) => (
                      <div key={a.id} className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50/40 transition-all">
                        <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                          <FileText className="w-4 h-4 text-blue-500" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">{a.title || a.prompt?.slice(0, 40) || '未命名文章'}</div>
                          <div className="text-xs text-gray-400 truncate">{(a.result || a.prompt || '').slice(0, 80)}</div>
                        </div>
                        <span className="text-xs text-gray-400 flex-shrink-0">{a.created_at?.slice(0, 10)}</span>
                        <Button variant="secondary" size="sm" icon={FileText} onClick={() => useArticle(a)}>加载正文</Button>
                      </div>
                    ))}
                  </div>
                ) : <Empty icon={FileText} title="暂无历史文章" description="到「文案工厂」生成文章后会自动出现在这里" />
              ) : (
                assets.media?.length ? (
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 max-h-72 overflow-y-auto pr-1">
                    {assets.media.map((m) => (
                      <div key={m.id} className="group relative rounded-xl overflow-hidden border border-gray-200 bg-gray-50">
                        {m.type === 'image' ? (
                          <img src={assetFull(m.url)} alt="" className="w-full h-28 object-cover" />
                        ) : (
                          <div className="w-full h-28 flex items-center justify-center bg-gradient-to-br from-gray-800 to-gray-900">
                            <Film className="w-8 h-8 text-white/70" />
                          </div>
                        )}
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
                          <Button variant="secondary" size="sm" icon={Plus} onClick={() => addMedia(m)}>加入素材</Button>
                        </div>
                        <div className="px-2 py-1.5 text-[11px] text-gray-500 truncate bg-white">{m.url?.split('/').pop()}</div>
                      </div>
                    ))}
                  </div>
                ) : <Empty icon={Film} title="暂无图片视频素材" description="到「图片工厂」「视频工厂」生成素材后会自动出现在这里" />
              )}
            </Card>

            {/* 发布结果 */}
            {result && (
              <Card className={result.mode === 'auto' ? 'border-emerald-200' : result.mode === 'guide_fallback' ? 'border-amber-200' : 'border-blue-200'}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    {result.mode === 'auto' ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : result.mode === 'guide_fallback' ? <AlertCircle className="w-4 h-4 text-amber-500" /> : <Sparkles className="w-4 h-4 text-blue-500" />}
                    发布结果
                  </h3>
                  <Badge color={MODE_BADGE[result.mode]?.color}>{MODE_BADGE[result.mode]?.label}</Badge>
                </div>

                {result.mode === 'auto' ? (
                  <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
                    <p className="font-medium flex items-center gap-2"><CheckCircle2 className="w-4 h-4" />{result.message}</p>
                    <p className="mt-1 text-xs text-emerald-600">记录 ID：{result.record_id} · 平台帖子 ID：{result.platform_post_id}</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className={`p-3 rounded-xl text-sm ${result.mode === 'guide_fallback' ? 'bg-amber-50 border border-amber-200 text-amber-800' : 'bg-blue-50 border border-blue-200 text-blue-800'}`}>
                      <p className="font-medium">{result.message}</p>
                      <p className="mt-1 text-xs opacity-80">发布目标：{result.platform_label} · {result.content_type === 'article' ? '图文' : result.content_type}</p>
                    </div>

                    {/* 标题 */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium text-gray-500">标题</label>
                        <button onClick={() => copy(result.title, 'title')} className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1">
                          {copiedKey === 'title' ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />} 复制
                        </button>
                      </div>
                      <div className="px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-800">{result.title || '（无）'}</div>
                    </div>

                    {/* 正文 */}
                    {result.content && (
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="text-xs font-medium text-gray-500">正文 / 文案（{result.content.length} 字）</label>
                          <button onClick={() => copy(result.content, 'content')} className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1">
                            {copiedKey === 'content' ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />} 复制全文
                          </button>
                        </div>
                        <div className="px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-800 whitespace-pre-wrap max-h-56 overflow-y-auto">{result.content}</div>
                      </div>
                    )}

                    {/* 话题 */}
                    {result.topics?.length > 0 && (
                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">话题</label>
                        <div className="flex flex-wrap gap-1.5">
                          {result.topics.map((t, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700">#{t}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 素材下载 */}
                    {result.asset_urls?.length > 0 && (
                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">素材文件（右键另存为下载）</label>
                        <div className="space-y-1">
                          {result.asset_urls.map((u, i) => (
                            <a key={i} href={assetFull(u)} target="_blank" rel="noreferrer"
                              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-sm text-gray-700">
                              <Download className="w-3.5 h-3.5 text-gray-400" />
                              <span className="flex-1 truncate">{u.split('/').pop()}</span>
                              <Link2 className="w-3.5 h-3.5 text-gray-300" />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 发布步骤 */}
                    <div>
                      <label className="text-xs font-medium text-gray-500 block mb-2">分步操作指引</label>
                      <ol className="space-y-2">
                        {result.steps?.map((s, i) => (
                          <li key={i} className="flex gap-3 text-sm text-gray-700">
                            <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{i + 1}</span>
                            <span>{s}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      )}

      {tab === 'records' && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" /> 发布记录
          </h3>
          {records.length === 0 ? (
            <Empty icon={Clock} title="暂无发布记录" description="发布内容后记录会展示在这里" />
          ) : (
            <div className="space-y-2">
              {records.map((r) => (
                <div key={r.id} className="p-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50/30 transition-all">
                  <div className="flex items-center gap-3 flex-wrap">
                    <Badge color={PLATFORMS.find((p) => p.value === r.platform) ? 'green' : 'gray'}>
                      {PLATFORMS.find((p) => p.value === r.platform)?.label || r.platform_label}
                    </Badge>
                    <Badge color="blue">{r.content_label}</Badge>
                    <Badge color={MODE_BADGE[r.mode]?.color || 'gray'}>{MODE_BADGE[r.mode]?.label || r.mode}</Badge>
                    <Badge color={STATUS_BADGE[r.status]?.color || 'gray'}>{STATUS_BADGE[r.status]?.label || r.status}</Badge>
                    <span className="flex-1 text-sm text-gray-700 truncate min-w-0">{r.title || '(无标题)'}</span>
                    <span className="text-xs text-gray-400">{r.created_at?.slice(0, 16).replace('T', ' ')}</span>
                    <Button variant="ghost" size="sm" onClick={() => setDetail(r)}>详情</Button>
                  </div>
                  {r.error && <p className="mt-2 text-xs text-red-500 truncate">错误：{r.error}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {tab === 'accounts' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 已配置账号 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-gray-400" /> 已配置账号（{accounts.length}）
            </h3>
            {accounts.length === 0 ? (
              <Empty icon={Settings2} title="暂无账号配置" description="添加平台账号后即可使用自动发布（未配置时自动使用引导式）" />
            ) : (
              <div className="space-y-2">
                {accounts.map((a) => {
                  const p = PLATFORMS.find((x) => x.value === a.platform)
                  return (
                    <div key={a.id} className="p-3 rounded-lg border border-gray-100 hover:border-blue-200 transition-all">
                      <div className="flex items-center gap-3">
                        {p && <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${p.color} flex items-center justify-center flex-shrink-0`}><p.icon className="w-4 h-4 text-white" /></div>}
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800">{a.name || p?.label || a.platform}</div>
                          <div className="text-xs text-gray-400">AppID：{a.app_id || '未填写'} {a.configured ? '· 已配置' : '· 未配置'}</div>
                        </div>
                        <Button variant="secondary" size="sm" icon={TestTube2} loading={testingId === a.id} onClick={() => testAccount(a.id)}>测试连接</Button>
                        <button onClick={() => deleteAccount(a.id)} className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"><Trash2 className="w-4 h-4" /></button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          {/* 添加账号 */}
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Plus className="w-4 h-4 text-blue-500" /> 添加 / 更新账号
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">平台</label>
                  <div className="grid grid-cols-3 gap-2">
                    {PLATFORMS.map((p) => (
                      <button key={p.value} onClick={() => setAccForm({ ...accForm, platform: p.value })}
                        className={`flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-xs border transition-all ${
                          accForm.platform === p.value ? `${p.border} ${p.text} font-medium` : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                        }`}>
                        <p.icon className="w-3.5 h-3.5" /> {p.label.replace('微信', '')}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">账号名称（可选）</label>
                  <input type="text" value={accForm.name} onChange={(e) => setAccForm({ ...accForm, name: e.target.value })}
                    placeholder="如：我的公众号" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">AppID</label>
                  <input type="text" value={accForm.app_id} onChange={(e) => setAccForm({ ...accForm, app_id: e.target.value })}
                    placeholder="平台应用 / 公众号 AppID" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">AppSecret</label>
                  <input type="password" value={accForm.app_secret} onChange={(e) => setAccForm({ ...accForm, app_secret: e.target.value })}
                    placeholder="平台应用 / 公众号 AppSecret" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none" />
                </div>
                <Button variant="primary" icon={Plus} onClick={saveAccount} className="w-full">保存账号</Button>
              </div>
            </Card>

            <Card>
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <CircleDashed className="w-4 h-4 text-amber-500" /> 凭据获取指引
              </h3>
              <div className="space-y-2 text-sm text-gray-600">
                <p><span className="font-medium text-emerald-600">微信公众号：</span>登录 mp.weixin.qq.com → 设置与开发 → 基本配置 → 复制 AppID 与 AppSecret（需开启 IP 白名单）。配置后图文可自动发布。</p>
                <p><span className="font-medium text-gray-700">抖音 / 快手：</span>到开放平台创建「移动应用/网站应用」并完成审核，审核通过后才能获得可用凭据实现图片视频自动发布；审核前请使用「引导式」零配置发布。</p>
                <p className="text-xs text-gray-400">凭据仅保存在本平台数据库（脱敏展示），不会明文回传前端。</p>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* 记录详情 Modal */}
      <Modal open={!!detail} onClose={() => setDetail(null)} title="发布详情" size="lg">
        {detail && (
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge color="green">{PLATFORMS.find((p) => p.value === detail.platform)?.label || detail.platform_label}</Badge>
              <Badge color="blue">{detail.content_label}</Badge>
              <Badge color={MODE_BADGE[detail.mode]?.color}>{MODE_BADGE[detail.mode]?.label}</Badge>
              <Badge color={STATUS_BADGE[detail.status]?.color}>{STATUS_BADGE[detail.status]?.label}</Badge>
              <span className="text-xs text-gray-400 ml-auto">{detail.created_at?.slice(0, 19).replace('T', ' ')}</span>
            </div>
            {detail.title && <p className="font-medium text-gray-900">{detail.title}</p>}
            {detail.content && (
              <div className="px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 whitespace-pre-wrap max-h-64 overflow-y-auto text-gray-700">{detail.content}</div>
            )}
            {detail.topics?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {detail.topics.map((t, i) => <span key={i} className="px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700">#{t}</span>)}
              </div>
            )}
            {detail.asset_urls?.length > 0 && (
              <div>
                <label className="text-xs font-medium text-gray-500">素材文件</label>
                <div className="space-y-1 mt-1">
                  {detail.asset_urls.map((u, i) => (
                    <a key={i} href={assetFull(u)} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200 hover:border-blue-300 text-xs text-gray-600">
                      <Download className="w-3 h-3 text-gray-400" /> {u.split('/').pop()}
                    </a>
                  ))}
                </div>
              </div>
            )}
            {detail.platform_post_id && <p className="text-xs text-emerald-600">平台帖子 ID：{detail.platform_post_id}</p>}
            {detail.error && <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg p-2">错误：{detail.error}</p>}
          </div>
        )}
      </Modal>
    </div>
  )
}
