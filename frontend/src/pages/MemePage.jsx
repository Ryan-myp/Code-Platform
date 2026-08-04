import React, { useState, useEffect } from 'react'
import {
  Sticker, Sparkles, Loader2, Download, Trash2, ImageIcon, SmilePlus, Type, FileEdit,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader } from '../components/ui'
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
  const [draftRestored, setDraftRestored] = useState(false)

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
    try { const res = await api.get('/api/meme/list'); setItems(res.data || []) } catch (e) {}
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

  const applySuggest = (s) => { setTopText(s.top); setBottomText(s.bottom) }

  return (
    <div className="space-y-6">
      <PageHeader
        title="表情包工坊"
        description="文字一键生成表情包：经典模板秒出 + AI 场景生成，微信/微博斗图利器"
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
              {generating && style === 'ai' && (
                <div className="flex items-center gap-2 text-xs text-amber-600 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  正在生成场景图并叠加文字，请稍候…
                </div>
              )}
            </div>
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

        {/* ── 右列：我的表情包 ── */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Sticker className="w-4 h-4 text-gray-400" /> 我的表情包（{items.length}）
            </h3>
            {items.length === 0 ? (
              <Empty icon={Sticker} title="还没有表情包" description="输入文字、选风格，点击生成即可" />
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {items.map((item) => (
                  <div key={item.id} className="group relative rounded-xl border border-gray-100 overflow-hidden hover:shadow-lg transition-all">
                    <img src={item.url} alt="表情包" className="w-full aspect-square object-cover" />
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="text-[11px] text-white truncate flex-1">{item.created_at?.slice(5, 16).replace('T', ' ')}</span>
                      <button onClick={() => download(item)} className="p-1 text-white hover:text-blue-300"><Download className="w-4 h-4" /></button>
                      <button onClick={() => remove(item)} className="p-1 text-white hover:text-red-300"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
