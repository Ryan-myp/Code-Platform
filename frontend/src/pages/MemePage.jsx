import React, { useState, useEffect, useMemo } from 'react'
import {
  Sticker,
  Sparkles,
  Loader2,
  Download,
  Trash2,
  ImageIcon,
  SmilePlus,
  Type,
  FileEdit,
  Search,
  Pencil,
  CheckSquare,
  Square,
  DownloadCloud,
  RotateCcw,
  Layers,
  Wand2,
  Copy,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Modal, Badge, SkeletonGrid } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

const STYLES = [
  { id: 'yellow', name: '经典黄底', desc: 'Doge 经典黄', swatch: 'bg-[#FFD84D]', text: '#000000' },
  {
    id: 'white',
    name: '熊猫白底',
    desc: '白底黑字极简',
    swatch: 'bg-white border border-gray-200',
    text: '#000000',
  },
  { id: 'red', name: '公告红底', desc: '红底白字通告', swatch: 'bg-[#E53935]', text: '#FFFFFF' },
  { id: 'black', name: '暗夜黑底', desc: '黑底白字高冷', swatch: 'bg-[#111111]', text: '#FFFFFF' },
  {
    id: 'gradient',
    name: '蓝紫渐变',
    desc: '渐变潮流吸睛',
    swatch: 'bg-gradient-to-b from-indigo-500 to-purple-500',
    text: '#FFFFFF',
  },
  {
    id: 'neon',
    name: '霓虹灯管',
    desc: '深底青光描边',
    swatch: 'bg-gradient-to-b from-[#110826] to-[#2D0C42]',
    text: '#22D3EE',
  },
  {
    id: 'paper',
    name: '报纸复古',
    desc: '米白老报纸风',
    swatch: 'bg-[#F7F3E8] border border-gray-200',
    text: '#111111',
  },
  {
    id: 'sticker',
    name: '贴纸白边',
    desc: '黑字白描边',
    swatch: 'bg-white border border-gray-200',
    text: '#000000',
  },
  {
    id: 'upload',
    name: '上传背景',
    desc: '自己的图片做底',
    swatch: 'bg-gradient-to-br from-gray-400 to-gray-600',
    text: '#FFFFFF',
  },
  {
    id: 'ai',
    name: 'AI 生成',
    desc: '文生图 + 叠字',
    swatch: 'bg-gradient-to-br from-pink-500 to-amber-400',
    text: '#FFFFFF',
  },
]

const AI_STYLES = [
  { id: 'flat', name: '扁平插画', desc: '简洁高饱和' },
  { id: '3d', name: '3D 软萌', desc: '立体卡通' },
  { id: 'pixel', name: '像素复古', desc: '8-bit 质感' },
  { id: 'ink', name: '水墨国风', desc: '笔墨晕染' },
  { id: 'neon', name: '霓虹赛博', desc: '灯管光效' },
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
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿；bgUpload 图片数据不持久化）
  const [inputs, setInputs] = usePersistentToolState('meme_inputs', {
    style: 'yellow',
    topText: '',
    bottomText: '',
    aiPrompt: '',
    aiStyle: 'flat',
  })
  const { style, topText, bottomText, aiPrompt, aiStyle } = inputs
  const setStyle = (v) => setInputs((p) => ({ ...p, style: v }))
  const setTopText = (v) => setInputs((p) => ({ ...p, topText: v ?? '' }))
  const setBottomText = (v) => setInputs((p) => ({ ...p, bottomText: v ?? '' }))
  const setAiPrompt = (v) => setInputs((p) => ({ ...p, aiPrompt: v ?? '' }))
  const setAiStyle = (v) => setInputs((p) => ({ ...p, aiStyle: v }))
  const [bgUpload, setBgUpload] = useState('')
  const [decoration, setDecoration] = useState('')
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
  // 异步任务进度（task_id + 轮询进度）
  const [genTask, setGenTask] = useState(null)
  const { submitTask } = useAsyncTask()

  useEffect(() => {
    loadList()
  }, [])

  // 进入页面恢复草稿（仅挂载时执行一次，setter 均为函数式更新）
  useEffect(() => {
    api
      .get('/api/drafts/meme')
      .then((res) => {
        const d = res.data
        if (d?.content?.top_text || d?.content?.bottom_text) {
          setTopText(d.content.top_text || '')
          setBottomText(d.content.bottom_text || '')
          if (d.content.style) setStyle(d.content.style)
          if (d.content.ai_prompt) setAiPrompt(d.content.ai_prompt)
          if (d.content.ai_style) setAiStyle(d.content.ai_style)
          if (d.content.decoration) setDecoration(d.content.decoration)
          setDraftRestored(true)
        }
      })
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 输入防抖自动保存草稿
  useEffect(() => {
    if (!topText.trim() && !bottomText.trim()) return
    const t = setTimeout(() => {
      api
        .post('/api/drafts/save', {
          tool_id: 'meme',
          title: `${topText.slice(0, 15)} / ${bottomText.slice(0, 15)}`,
          content: {
            top_text: topText,
            bottom_text: bottomText,
            style,
            ai_prompt: aiPrompt,
            ai_style: aiStyle,
            decoration,
          },
        })
        .catch(() => {})
    }, 1500)
    return () => clearTimeout(t)
  }, [topText, bottomText, style, aiPrompt, aiStyle, decoration])

  // 生成成功后清除草稿
  const clearDraft = async () => {
    try {
      const res = await api.get('/api/drafts/meme')
      if (res.data?.id) await api.delete(`/api/drafts/${res.data.id}`)
    } catch {
      /* ignore */
    }
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
      api
        .get('/api/meme/stats')
        .then((r) => setStats(r.data))
        .catch(() => {})
    } catch (e) {
      toast.error(`加载失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const generate = async () => {
    if (!topText.trim() && !bottomText.trim()) {
      toast.error('请输入至少一行文字')
      return
    }
    setGenerating(true)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const fd = new FormData()
    fd.append('top_text', topText.trim())
    fd.append('bottom_text', bottomText.trim())
    fd.append('style', style)
    fd.append('ai_prompt', aiPrompt.trim())
    fd.append('ai_style', aiStyle)
    fd.append('bg_upload', bgUpload)
    fd.append('decoration', decoration.trim())
    await submitTask('/api/meme/generate', fd, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: async () => {
        toast.success(style === 'ai' ? 'AI 表情包生成完成' : '表情包已生成')
        setGenerating(false)
        setBgUpload('')
        await clearDraft()
        loadList()
      },
      onError: (e) => {
        setGenerating(false)
        toast.error(`生成失败：${e.message}`)
      },
    })
  }

  // ── 批量生成：每行一组「顶部 / 底部」，一次生成多张 ──
  const generateBatch = async () => {
    const lines = batchText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    if (lines.length === 0) {
      toast.error('请输入至少一行文案')
      return
    }
    setGenerating(true)
    let ok = 0
    let done = 0
    // 全部任务（提交/完成）后收尾
    const finish = () => {
      done++
      if (done < lines.length) return
      setGenerating(false)
      setBatchMode(false)
      setBatchText('')
      if (ok > 0) {
        toast.success(`批量生成完成：${ok}/${lines.length} 张`)
        loadList()
      }
    }
    for (const line of lines) {
      const parts = line.split('/')
      const top = (parts[0] || '').trim()
      const bottom = (parts.slice(1).join('/') || '').trim()
      const fd = new FormData()
      fd.append('top_text', top)
      fd.append('bottom_text', bottom)
      fd.append('style', style)
      fd.append('ai_prompt', '')
      await submitTask('/api/meme/generate', fd, {
        onSuccess: () => {
          ok++
          finish()
        },
        onError: (e) => {
          toast.error(`「${line}」生成失败：${e.message}`)
          finish()
        },
      })
    }
  }

  const download = (item) => {
    const a = document.createElement('a')
    a.href = item.url
    a.download = item.id
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // 商用尺寸导出：240（微信表情单图）/ 750（聊天大图）/ 1080（原图）/ 2160（高清印刷）
  const downloadSize = (item, size) => {
    const a = document.createElement('a')
    a.href = `${item.url}?size=${size}`
    a.download = item.id.replace(/\.png$/, `_${size}.png`)
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const remove = async (item) => {
    try {
      await api.delete(`/api/meme/${item.id}`)
      loadList()
      toast.success('已删除')
    } catch (e) {
      toast.error(e.message)
    }
  }

  const removeSelected = async () => {
    if (selected.size === 0) return
    try {
      await Promise.all([...selected].map((id) => api.delete(`/api/meme/${id}`)))
      toast.success(`已删除 ${selected.size} 个表情包`)
      setSelected(new Set())
      loadList()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const downloadSelected = async () => {
    if (selected.size === 0) return
    try {
      const fd = new FormData()
      ;[...selected].forEach((id) => fd.append('ids', id))
      const res = await api.post('/api/meme/batch-download', fd, {
        responseType: 'blob',
        timeout: 60000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `memes_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已打包下载 ${selected.size} 个表情包`)
    } catch (e) {
      toast.error(`批量下载失败：${e.message}`)
    }
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelected((prev) =>
      prev.size === filtered.length ? new Set() : new Set(filtered.map((i) => i.id))
    )
  }

  const openRename = (item) => {
    setRenaming(item)
    setRenameTitle(item.title || '')
  }

  const submitRename = async () => {
    if (!renameTitle.trim()) {
      toast.error('请输入新标题')
      return
    }
    try {
      await api.put(`/api/meme/${renaming.id}/rename`, { title: renameTitle.trim() })
      toast.success('已重命名')
      setRenaming(null)
      loadList()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const filtered = useMemo(() => {
    let list = [...items]
    if (q) {
      const kw = q.toLowerCase()
      list = list.filter(
        (i) =>
          i.id.toLowerCase().includes(kw) ||
          (i.top_text || '').toLowerCase().includes(kw) ||
          (i.bottom_text || '').toLowerCase().includes(kw) ||
          (i.title || '').toLowerCase().includes(kw)
      )
    }
    if (filterStyle) list = list.filter((i) => i.style === filterStyle)
    return list
  }, [items, q, filterStyle])

  const applySuggest = (s) => {
    setTopText(s.top)
    setBottomText(s.bottom)
  }

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
          <button
            onClick={() => {
              setTopText('')
              setBottomText('')
              setAiPrompt('')
              setDraftRestored(false)
              api
                .get('/api/drafts/meme')
                .then((r) => r.data?.id && api.delete(`/api/drafts/${r.data.id}`))
                .catch(() => {})
            }}
            className="text-sky-600 hover:text-sky-800 font-medium"
          >
            清空草稿
          </button>
        </div>
      )}

      {/* ── 统计卡片 ── */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Layers className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.total}</div>
              <div className="text-xs text-gray-400">表情包总数</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Wand2 className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">{stats.ai_count}</div>
              <div className="text-xs text-gray-400">AI 生成</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Type className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {Object.keys(stats.style_dist || {}).length}
              </div>
              <div className="text-xs text-gray-400">使用风格</div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-100 bg-white p-4 flex items-center gap-3">
            <span className="w-9 h-9 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
              <Copy className="w-4.5 h-4.5" />
            </span>
            <div>
              <div className="text-lg font-bold text-gray-900">
                {Object.entries(stats.style_dist || {}).reduce((a, [, n]) => Math.max(a, n), 0)}
              </div>
              <div className="text-xs text-gray-400">单风格最多</div>
            </div>
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
                <button
                  key={s.id}
                  onClick={() => setStyle(s.id)}
                  className={`flex flex-col items-center gap-1.5 px-2 py-2.5 rounded-xl border transition-all ${
                    style === s.id
                      ? 'bg-amber-50 border-amber-300 ring-2 ring-amber-500/20'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <span
                    className={`w-10 h-8 rounded-lg ${s.swatch} flex items-center justify-center`}
                  >
                    <Type className="w-3.5 h-3.5" style={{ color: s.text }} />
                  </span>
                  <span className="text-xs font-medium text-gray-700">{s.name}</span>
                  <span className="text-[11px] text-gray-400">{s.desc}</span>
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <Type className="w-4 h-4 text-pink-500" /> 表情文字
              </span>
              <button
                onClick={() => applySuggest(SUGGESTS[Math.floor(Math.random() * SUGGESTS.length)])}
                className="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-1"
              >
                <Wand2 className="w-3 h-3" />
                随机梗文案
              </button>
            </h3>
            {!batchMode ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    顶部文字（冲击力强）
                  </label>
                  <input
                    type="text"
                    value={topText}
                    onChange={(e) => setTopText(e.target.value)}
                    placeholder="如：我太难了"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    底部文字（神转折）
                  </label>
                  <input
                    type="text"
                    value={bottomText}
                    onChange={(e) => setBottomText(e.target.value)}
                    placeholder="如：生活终于对我下手了"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">
                    灵感模板（点击填入）
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {SUGGESTS.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => applySuggest(s)}
                        className="px-2 py-1 rounded-full bg-gray-100 hover:bg-amber-100 text-[11px] text-gray-600 hover:text-amber-700 transition-colors"
                      >
                        {s.top} / {s.bottom}
                      </button>
                    ))}
                  </div>
                </div>

                {style === 'ai' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">
                        AI 场景描述（可选）
                      </label>
                      <input
                        type="text"
                        value={aiPrompt}
                        onChange={(e) => setAiPrompt(e.target.value)}
                        placeholder="如：一只加班到崩溃的柴犬，办公室场景"
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                      />
                      <p className="text-[11px] text-gray-400 mt-1">留空则根据文字自动设计场景</p>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1.5">
                        画面风格
                      </label>
                      <div className="flex flex-wrap gap-1.5">
                        {AI_STYLES.map((s) => (
                          <button
                            key={s.id}
                            onClick={() => setAiStyle(s.id)}
                            className={`px-2.5 py-1 rounded-full text-[11px] border transition-colors ${
                              aiStyle === s.id
                                ? 'bg-pink-50 border-pink-300 text-pink-700'
                                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-pink-50'
                            }`}
                          >
                            {s.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {style === 'upload' && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      背景图片（≤8MB）
                    </label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        if (!f) return
                        const reader = new FileReader()
                        reader.onload = () => setBgUpload(reader.result)
                        reader.readAsDataURL(f)
                      }}
                      className="w-full text-sm text-gray-500 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-amber-50 file:text-amber-700 file:text-xs file:font-medium hover:file:bg-amber-100"
                    />
                    {bgUpload && (
                      <img
                        src={bgUpload}
                        alt="背景预览"
                        className="mt-2 h-24 rounded-lg object-cover border border-gray-200"
                      />
                    )}
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    emoji 装饰（可选，右下角）
                  </label>
                  <input
                    type="text"
                    value={decoration}
                    onChange={(e) => setDecoration(e.target.value)}
                    placeholder="如：😂,🔥,💯（最多 4 个）"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>

                <Button
                  variant="primary"
                  size="lg"
                  icon={Sticker}
                  loading={generating}
                  onClick={generate}
                  className="w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
                >
                  {generating ? '生成任务执行中（后台）…' : '生成表情包'}
                </Button>
                {generating && genTask && (
                  <div className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2">
                    <div className="flex items-center gap-2 text-xs text-amber-700">
                      <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                      <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                      <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                    </div>
                    <div className="mt-1.5 h-1.5 bg-amber-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-amber-500 to-orange-600 rounded-full transition-all"
                        style={{ width: `${genTask.progress || 0}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[11px] text-gray-400">
                      任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                    </p>
                  </div>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Copy}
                  onClick={() => {
                    setBatchMode(true)
                    setBatchText('')
                  }}
                  className="w-full justify-center"
                >
                  批量生成模式（一次多张）
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center justify-between">
                    <span>批量文案（每行一组，用 / 分隔顶部与底部）</span>
                    <button
                      onClick={() => {
                        const count = 3 + Math.floor(Math.random() * 2)
                        const pool = [...SUGGESTS]
                        const picked = []
                        while (picked.length < count && pool.length > 0) {
                          const i = Math.floor(Math.random() * pool.length)
                          picked.push(pool.splice(i, 1)[0])
                        }
                        setBatchText(picked.map((s) => `${s.top} / ${s.bottom}`).join('\n'))
                      }}
                      className="text-amber-600 hover:text-amber-700 flex items-center gap-1"
                    >
                      <Wand2 className="w-3 h-3" />
                      随机批量
                    </button>
                  </label>
                  <textarea
                    value={batchText}
                    onChange={(e) => setBatchText(e.target.value)}
                    rows={8}
                    placeholder={
                      '举例：\n我太难了 / 生活终于对我下手了\n好的呢 / 微笑中透露着疲惫\n在？ / 出来聊五毛钱的天'
                    }
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !generating) {
                        e.preventDefault()
                        generateBatch()
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                  <p className="text-[11px] text-gray-400 mt-1">
                    当前风格：{STYLES.find((s) => s.id === style)?.name} · 每行生成一张
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    size="md"
                    icon={Copy}
                    loading={generating}
                    onClick={generateBatch}
                    className="flex-1 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
                  >
                    {generating ? '批量生成中…' : '批量生成'}
                  </Button>
                  <Button variant="secondary" size="md" onClick={() => setBatchMode(false)}>
                    返回单张
                  </Button>
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
              <p>② 智能换行优先在标点断行，白字黑描边 + 投影更立体</p>
              <p>③ 支持 240/750/1080/2160 多尺寸导出（微信表情/聊天图/高清印刷）</p>
              <p>④ AI 模式生成专属搞笑场景，上下文字底条保证可读性</p>
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
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="搜索文字或文件名…"
                    className="w-full pl-8 pr-3 py-1.5 border border-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                  />
                </div>
                <select
                  value={filterStyle}
                  onChange={(e) => setFilterStyle(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-amber-500 bg-white"
                >
                  <option value="">全部风格</option>
                  {STYLES.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="px-2 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 outline-none focus:border-amber-500 bg-white"
                >
                  <option value="newest">最新优先</option>
                  <option value="oldest">最早优先</option>
                </select>
                <Button variant="ghost" size="sm" icon={RotateCcw} onClick={loadList}>
                  刷新
                </Button>
              </div>
            </div>

            {filtered.length > 0 && (
              <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs">
                <button
                  onClick={toggleAll}
                  className="flex items-center gap-1.5 text-gray-600 hover:text-amber-600"
                >
                  {selected.size === filtered.length ? (
                    <CheckSquare className="w-4 h-4" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                  全选
                </button>
                <span className="text-gray-400">已选 {selected.size} 项</span>
                {selected.size > 0 && (
                  <div className="ml-auto flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={DownloadCloud}
                      onClick={downloadSelected}
                    >
                      批量下载 ZIP
                    </Button>
                    <Button variant="danger" size="sm" icon={Trash2} onClick={removeSelected}>
                      批量删除
                    </Button>
                  </div>
                )}
              </div>
            )}

            {loading ? (
              <SkeletonGrid count={4} />
            ) : filtered.length === 0 ? (
              <Empty
                icon={Sticker}
                title={q || filterStyle ? '没有匹配的表情包' : '还没有表情包'}
                description={
                  q || filterStyle ? '换个关键词或筛选条件试试' : '输入文字、选风格，点击生成即可'
                }
              />
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {filtered.map((item) => (
                  <div
                    key={item.id}
                    className="group relative rounded-xl border border-gray-100 overflow-hidden hover:shadow-lg transition-all"
                  >
                    <img
                      src={item.url}
                      alt="表情包"
                      loading="lazy"
                      className="w-full aspect-square object-cover"
                    />
                    {/* 标题条（非 hover 也可见） */}
                    <div className="absolute top-0 inset-x-0 bg-gradient-to-b from-black/60 to-transparent p-1.5 pb-4 flex items-center justify-between">
                      <span className="text-[11px] text-white truncate flex-1">{item.title}</span>
                      <button
                        onClick={() => toggleSelect(item.id)}
                        className={`p-0.5 flex-shrink-0 ${selected.has(item.id) ? 'text-amber-400' : 'text-white/70 hover:text-white'}`}
                      >
                        {selected.has(item.id) ? (
                          <CheckSquare className="w-3.5 h-3.5" />
                        ) : (
                          <Square className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 pt-6 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="text-[11px] text-white truncate flex-1">
                        {item.style_label || '未标记'} ·{' '}
                        {item.created_at?.slice(5, 16).replace('T', ' ')}
                      </span>
                      <button
                        onClick={() => openRename(item)}
                        title="重命名"
                        className="p-1 text-white hover:text-violet-300"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => download(item)}
                        title="下载原图 1080"
                        className="p-1 text-white hover:text-blue-300"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <span onClick={(e) => e.stopPropagation()}>
                        <ShareButton
                          content={`# 表情包：${item.title}\n\n风格：${item.style_label || '未标记'}\n\n> 由小团智能平台表情包工坊生成 · ${new Date().toLocaleString()}`}
                          title={`表情包：${item.title}`}
                          contentType="meme"
                          className="!p-1 !text-white !bg-transparent"
                        />
                      </span>
                      <select
                        onChange={(e) => {
                          if (e.target.value) downloadSize(item, e.target.value)
                        }}
                        defaultValue=""
                        title="导出尺寸"
                        className="text-[10px] bg-black/40 text-white border border-white/20 rounded-md px-1 py-0.5 outline-none cursor-pointer"
                      >
                        <option value="" disabled>
                          尺寸
                        </option>
                        {[240, 750, 1080, 2160].map((s) => (
                          <option key={s} value={s} className="text-gray-800">
                            {s}×{s}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => remove(item)}
                        title="删除"
                        className="p-1 text-white hover:text-red-300"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* ── 重命名 Modal ── */}
      <Modal
        open={!!renaming}
        onClose={() => setRenaming(null)}
        title="重命名表情包"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRenaming(null)}>
              取消
            </Button>
            <Button variant="primary" onClick={submitRename}>
              保存
            </Button>
          </>
        }
      >
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">
            标题（便于在资产库中识别）
          </label>
          <input
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            autoFocus
            placeholder="如：打工人专用-01"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
          />
        </div>
      </Modal>
    </div>
  )
}
