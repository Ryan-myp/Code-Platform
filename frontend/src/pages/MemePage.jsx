import React, { useState, useEffect, useMemo } from 'react'
import {
  Sticker, Sparkles, Loader2, Download, Trash2, ImageIcon, SmilePlus, Type, FileEdit,
  Search, Pencil, CheckSquare, Square, DownloadCloud, RotateCcw, Layers, Wand2, Copy,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Modal, Badge, SkeletonGrid } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const STYLES = [
  { id: 'yellow', name: '经典黄底', desc: 'Doge 经典黄', swatch: 'bg-[#FFD84D]', text: '#000000' },
  { id: 'white', name: '熊猫白底', desc: '白底黑字极简', swatch: 'bg-white border border-gray-200', text: '#000000' },
  { id: 'red', name: '公告红底', desc: '红底白字通告', swatch: 'bg-[#E53935]', text: '#FFFFFF' },
  { id: 'black', name: '暗夜黑底', desc: '黑底白字高冷', swatch: 'bg-[#111111]', text: '#FFFFFF' },
  { id: 'gradient', name: '蓝紫渐变', desc: '渐变潮流吸睛', swatch: 'bg-gradient-to-b from-indigo-500 to-purple-500', text: '#FFFFFF' },
  { id: 'ai', name: 'AI 生成', desc: '文生图 + 叠字', swatch: 'bg-gradient-to-br from-pink-500 to-amber-400', text: '#FFFFFF' },
]

const SUGGESTS = [
  { top: '我太难了', bottom: '生活终于对我下手了' },
  { top: '好的呢', bottom: '微笑中透露着疲惫' },
  { top: '在？', bottom: '出来聊五毛钱的天' },
  { top: '格局打开', bottom: '这事就这么定了' },
  { top: '已阅', bottom: '散会' },
  { top: '干饭人', bottom: '干饭魂' },
]

export default function MemePage() {
  const toast = useToast()
  const [style, setStyle] = useState('yellow')
  const [topText, setTopText] = useState('')
  const [bottomText, setBottomText] = useState('')
  const [aiPrompt, setAiPrompt] = useState('')
  const [generating, setGenerating] = useState(false)
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [draftRestored, setDraftRestored] = useState(false)

  // ── 资产化管理状态 ──
  const [q, setQ] = useState('')
  const [filterStyle, setFilterStyle] = useState('')
  const [sort, setSort] = useState('newest')
  const [selected, setSelected] = useState(new Set())
  const [renaming, setRenaming] = useState(null)
  const [renameTitle, setRenameTitle] = useState('')
  const [batchMode, setBatchMode] = useState(false)
  const [batchText, setBatchText] = useState('')

  useEffect(() => { loadList() }, [])

  // 进入页面恢复草稿
  useEffect(() => {
    api.get('/api/drafts/meme').then((res) => {
      const d = res.data
      if (d?.content?.top_text || d?.content?.bottom_text) {
        setTopText(d.content.top_text || '')
        setBottomText(d.content.bottom_text || '')
        if (d.content.style) setStyle(d.content.style)
        if (d.content.ai_prompt) setAiPrompt(d.content.ai_prompt)
        setDraftRestored(true)
      }
    }).catch(() => {})
  }, [])

  // 输入防抖自动保存草稿
  useEffect(() => {
    if (!topText.trim() && !bottomText.trim()) return
    const t = setTimeout(() => {
      api.post('/api/drafts/save', {
        tool_id: 'meme', title: `${topText.slice(0, 15)} / ${bottomText.slice(0, 15)}`,
        content: { top_text: topText, bottom_text: bottomText, style, ai_prompt: aiPrompt },
      }).catch(() => {})
    }, 1500)
    return () => clearTimeout(t)
  }, [topText, bottomText, style, aiPrompt])

  // 生成成功后清除草稿
  const clearDraft = async () => {
    try {
      const res = await api.get('/api/drafts/meme')
      if (res.data?.id) await api.delete(`/api/drafts/${res.data.id}`)
    } catch { /* ignore */ }
  }

  const loadList = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (q) params.set('q', q)
      if (filterStyle) params.set('style', filterStyle)
      if (sort) params.set('sort', sort)
      const res = await api.get(`/api/meme/list?${params.toString()}`)
      setItems(res.data || [])
      api.get('/api/meme/stats').then((r) => setStats(r.data)).catch(() => {})
    } catch (e) {
      toast.error(`加载失败：${e.message}`)
    } finally { setLoading(false) }
  }

  const generate = async () => {
    if (!topText.trim() && !bottomText.trim()) { toast.error('请输入至少一行文字'); return }
    setGenerating(true)
    try {
      const fd = new FormData()
      fd.append('top_text', topText.trim())
      fd.append('bottom_text', bottomText.trim())
      fd.append('style', style)
      fd.append('ai_prompt', aiPrompt.trim())
      const res = await api.post('/api/meme/generate', fd, { timeout: 180000 })
      toast.success(style === 'ai' ? 'AI 表情包生成完成' : '表情包已生成')
      await clearDraft()
      loadList()
    } catch (e) {
      toast.error(`生成失败：${e.message}`)
    } finally { setGenerating(false) }
  }

  // ── 批量生成：每行一组「顶部 / 底部」，一次生成多张 ──
  const generateBatch = async () => {
    const lines = batchText.split('\n').map((l) => l.trim()).filter(Boolean)
    if (lines.length === 0) { toast.error('请输入至少一行文案'); return }
    setGenerating(true)
    let ok = 0
    for (const line of lines) {
      const parts = line.split('/')
      const top = (parts[0] || '').trim()
      const bottom = (parts.slice(1).join('/') || '').trim()
      try {
        const fd = new FormData()
        fd.append('top_text', top)
        fd.append('bottom_text', bottom)
        fd.append('style', style)
        fd.append('ai_prompt', '')
        await api.post('/api/meme/generate', fd, { timeout: 180000 })
        ok++
      } catch (e) {
        toast.error(`「${line}」生成失败：${e.message}`)
      }
    }
    setGenerating(false)
    setBatchMode(false)
    setBatchText('')
    if (ok > 0) { toast.success(`批量生成完成：${ok}/${lines.length} 张`); loadList() }
  }

  const download = (item) => {
    const a = document.createElement('a')
    a.href = item.url
    a.download = item.id
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const remove = async (item) => {
    try { await api.delete(`/api/meme/${item.id}`); loadList(); toast.success('已删除') }
    catch (e) { toast.error(e.message) }
  }

  const removeSelected = async () => {
    if (selected.size === 0) return
    try {
      await Promise.all([...selected].map((id) => api.delete(`/api/meme/${id}`)))
      toast.success(`已删除 ${selected.size} 个表情包`)
      setSelected(new Set())
      loadList()
    } catch (e) { toast.error(e.message) }
  }

  const downloadSelected = async () => {
    if (selected.size === 0) return
    try {
      const fd = new FormData()
      ;[...selected].forEach((id) => fd.append('ids', id))
      const res = await api.post('/api/meme/batch-download', fd, { responseType: 'blob', timeout: 60000 })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `memes_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已打包下载 ${selected.size} 个表情包`)
    } catch (e) { toast.error(`批量下载失败：${e.message}`) }
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelected((prev) => prev.size === filtered.length ? new Set() : new Set(filtered.map((i) => i.id)))
  }

  const openRename = (item) => { setRenaming(item); setRenameTitle(item.title || '') }

  const submitRename = async () => {
    if (!renameTitle.trim()) { toast.error('请输入新标题'); return }
    try {
      await api.put(`/api/meme/${renaming.id}/rename`, { title: renameTitle.trim() })
      toast.success('已重命名')
      setRenaming(null)
      loadList()
    } catch (e) { toast.error(e.message) }
  }

  const filtered = useMemo(() => {
    let list = [...items]
    if (q) {
      const kw = q.toLowerCase()
      list = list.filter((i) => i.id.toLowerCase().includes(kw)
        || (i.top_text || '').toLowerCase().includes(kw) || (i.bottom_text || '').toLowerCase().includes(kw)
        || (i.title || '').toLowerCase().includes(kw))
    }
    if (filterStyle) list = list.filter((i) => i.style === filterStyle)
    return list
  }, [items, q, filterStyle])

  const applySuggest = (s) => { setTopText(s.top); setBottomText(s.bottom) }

  return (
    <div className="space-y-6">
      <PageHeader
        title="表情包工坊"
        description="文字一键生成表情包：经典模板秒出 + AI 场景生成，批量制作、资产化管理"
        icon={Sticker}
        iconColor="from-amber-500 to-orange-600"
      />

      {draftRestored && (
        <div className="flex items-center gap-2 text-xs text-sky-700 bg-sky-50 border border-sky-200 rounded-xl px-4 py-2.5">
          <FileEdit className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="flex-1">已恢复上次未完成的草稿，可直接继续生成或清空重写</span>
          <button onClick={() => { setTopText(''); setBottomText(''); setAiPrompt(''); setDraftRestored(false); api.get('/api/drafts/meme').then((r) => r.data?.id && api.delete(`/api/drafts/${r.data.id}`)).catch(() => {}) }}
            className="text-sky-600 hover:text-sky-800 font-medium">清空草稿</button>
        </div>
      )}

      {/* ── 统计卡片 ── */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center"><Layers className="w-4.5 h-4.5" /></span>
            <div><div className="text-lg font-bold text-gray-900">{stats.total}</div><div className="text-xs text-gray-400">表情包总数</div></div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center"><Wand2 className="w-4.5 h-4.5" /></span>
            <div><div className="text-lg font-bold text-gray-900">{stats.ai_count}</div><div className="text-xs text-gray-400">AI 生成</div></div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center"><Type className="w-4.5 h-4.5" /></span>
            <div><div className="text-lg font-bold text-gray-900">{Object.keys(stats.style_dist || {}).length}</div><div className="text-xs text-gray-400">使用风格</div></div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center"><Copy className="w-4.5 h-4.5" /></span>
            <div><div className="text-lg font-bold text-gray-900">{Object.entries(stats.style_dist || {}).reduce((a, [, n]) => Math.max(a, n), 0)}</div><div className="text-xs text-gray-400">单风格最多</div></div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── 左列：生成配置 ── */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <SmilePlus className="w-4 h-4 text-amber-500" /> 选择风格
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {STYLES.map((s) => (
                <button key={s.id} onClick={() => setStyle(s.id)}
                  className={`flex flex-col items-center gap-1.5 px-2 py-2.5 rounded-xl border transition-all ${
                    style === s.id ? 'bg-amber-50 border-amber-300 ring-2 ring-amber-500/20' : 'border-gray-200 hover:bg-gray-50'
                  }`}>
                  <span className={`w-10 h-8 rounded-lg ${s.swatch} flex items-center justify-center`}>
                    <Type className="w-3.5 h-3.5" style={{ color: s.text }} />
                  </span>
                  <span className="text-xs font-medium text-gray-700">{s.name}</span>
                  <span className="text-[11px] text-gray-400">{s.desc}</span>
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Type className="w-4 h-4 text-pink-500" /> 表情文字
            </h3>
            {!batchMode ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">顶部文字（冲击力强）</label>
                  <input type="text" value={topText} onChange={(e) => setTopText(e.target.value)}
                    placeholder="如：我太难了"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">底部文字（神转折）</label>
                  <input type="text" value={bottomText} onChange={(e) => setBottomText(e.target.value)}
                    placeholder="如：生活终于对我下手了"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">灵感模板（点击填入）</label>
                  <div className="flex flex-wrap gap-1.5">
                    {SUGGESTS.map((s, i) => (
                      <button key={i} onClick={() => applySuggest(s)}
                        className="px-2 py-1 rounded-full bg-gray-100 hover:bg-amber-100 text-[11px] text-gray-600 hover:text-amber-700 transition-colors">
                        {s.top} / {s.bottom}
                      </button>
                    ))}
                  </div>
                </div>

                {style === 'ai' && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">AI 场景描述（可选）</label>
                    <input type="text" value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
                      placeholder="如：一只加班到崩溃的柴犬，办公室场景"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                    <p className="text-[11px] text-gray-400 mt-1">留空则根据文字自动设计场景</p>
                  </div>
                )}

                <Button variant="primary" size="lg" icon={Sticker} loading={generating} onClick={generate}
                  className="w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700">
                  {generating ? (style === 'ai' ? 'AI 生成中（约 1 分钟）…' : '生成中…') : '生成表情包'}
                </Button>
                <Button variant="secondary" size="sm" icon={Copy} onClick={() => { setBatchMode(true); setBatchText('') }} className="w-full justify-center">
                  批量生成模式（一次多张）
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">批量文案（每行一组，用 / 分隔顶部与底部）</label>
                  <textarea value={batchText} onChange={(e) => setBatchText(e.target.value)} rows={8}
                    placeholder={'举例：\n我太难了 / 生活终于对我下手了\n好的呢 / 微笑中透露着疲惫\n在？ / 出来聊五毛钱的天'}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                  <p className="text-[11px] text-gray-400 mt-1">当前风格：{STYLES.find((s) => s.id === style)?.name} · 每行生成一张</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="primary" size="md" icon={Copy} loading={generating} onClick={generateBatch} className="flex-1 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700">
                    {generating ? '批量生成中…' : '批量生成'}
                  </Button>
                  <Button variant="secondary" size="md" onClick={() => setBatchMode(false)}>返回单张</Button>
                </div>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-emerald-500" /> 使用提示
            </h3>
            <div className="space-y-2 text-sm text-gray-600">
              <p>① 经典模板模式秒出，微信/QQ 直接发送</p>
              <p>② 长文字自动换行缩放，最多 2 行</p>
              <p>③ AI 模式生成专属搞笑场景，配上下文字更有梗</p>
            </div>
          </Card>
        </div>

        {/* ── 右列：表情包资产库 ── */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2 flex-shrink-0">
                <Sticker className="w-4 h-4 text-gray-400" /> 表情包资产库（{filtered.length}）
              </h3>
              <div className="flex-1 flex flex-wrap items-center gap-2">
                <div className="relative flex-1 min-w-[160px]">
                  <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索文字或文件名…"
                    className="w-full pl-8 pr-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
                </div>
                <select value={filterStyle} onChange={(e) => setFilterStyle(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-amber-500 bg-white">
                  <option value="">全部风格</option>
                  {STYLES.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                <select value={sort} onChange={(e) => setSort(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-amber-500 bg-white">
                  <option value="newest">最新优先</option>
                  <option value="oldest">最早优先</option>
                </select>
                <Button variant="ghost" size="sm" icon={RotateCcw} onClick={loadList}>刷新</Button>
              </div>
            </div>

            {filtered.length > 0 && (
              <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs">
                <button onClick={toggleAll} className="flex items-center gap-1.5 text-gray-600 hover:text-amber-600">
                  {selected.size === filtered.length ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                  全选
                </button>
                <span className="text-gray-400">已选 {selected.size} 项</span>
                {selected.size > 0 && (
                  <div className="ml-auto flex gap-2">
                    <Button variant="secondary" size="sm" icon={DownloadCloud} onClick={downloadSelected}>批量下载 ZIP</Button>
                    <Button variant="danger" size="sm" icon={Trash2} onClick={removeSelected}>批量删除</Button>
                  </div>
                )}
              </div>
            )}

            {loading ? (
              <SkeletonGrid count={4} />
            ) : filtered.length === 0 ? (
              <Empty icon={Sticker} title={q || filterStyle ? '没有匹配的表情包' : '还没有表情包'} description={q || filterStyle ? '换个关键词或筛选条件试试' : '输入文字、选风格，点击生成即可'} />
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {filtered.map((item) => (
                  <div key={item.id} className="group relative rounded-xl border border-gray-100 overflow-hidden hover:shadow-lg transition-all">
                    <img src={item.url} alt="表情包" loading="lazy" className="w-full aspect-square object-cover" />
                    {/* 标题条（非 hover 也可见） */}
                    <div className="absolute top-0 inset-x-0 bg-gradient-to-b from-black/60 to-transparent p-1.5 pb-4 flex items-center justify-between">
                      <span className="text-[11px] text-white truncate flex-1">{item.title}</span>
                      <button onClick={() => toggleSelect(item.id)} className={`p-0.5 flex-shrink-0 ${selected.has(item.id) ? 'text-amber-400' : 'text-white/70 hover:text-white'}`}>
                        {selected.has(item.id) ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="text-[11px] text-white truncate flex-1">{item.style_label || '未标记'} · {item.created_at?.slice(5, 16).replace('T', ' ')}</span>
                      <button onClick={() => openRename(item)} title="重命名" className="p-1 text-white hover:text-violet-300"><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => download(item)} title="下载 PNG" className="p-1 text-white hover:text-blue-300"><Download className="w-4 h-4" /></button>
                      <button onClick={() => remove(item)} title="删除" className="p-1 text-white hover:text-red-300"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* ── 重命名 Modal ── */}
      <Modal open={!!renaming} onClose={() => setRenaming(null)} title="重命名表情包" size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRenaming(null)}>取消</Button>
            <Button variant="primary" onClick={submitRename}>保存</Button>
          </>
        }>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">标题（便于在资产库中识别）</label>
          <input value={renameTitle} onChange={(e) => setRenameTitle(e.target.value)} autoFocus
            placeholder="如：打工人专用-01"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none" />
        </div>
      </Modal>
    </div>
  )
}
