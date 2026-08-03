import React, { useState, useEffect, useRef } from 'react'
import {
  PenTool, Play, Copy, Check, Clock, Sparkles, Upload, X,
  FileText, TrendingUp, Share2, Mail, Megaphone, Package, Newspaper, BookOpen,
  Trash2, Star, Tag,
} from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ShareButton from '../components/ShareButton'
import { Card, Button, Badge, Empty, PageHeader } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const TYPES = [
  { value: 'marketing', label: '营销文案', icon: Megaphone, color: 'pink' },
  { value: 'social', label: '社交媒体', icon: Share2, color: 'blue' },
  { value: 'seo', label: 'SEO文章', icon: TrendingUp, color: 'green' },
  { value: 'email', label: '邮件营销', icon: Mail, color: 'amber' },
  { value: 'ad', label: '广告创意', icon: Sparkles, color: 'purple' },
  { value: 'product', label: '产品描述', icon: Package, color: 'teal' },
  { value: 'press', label: '新闻稿', icon: Newspaper, color: 'red' },
  { value: 'brand', label: '品牌故事', icon: BookOpen, color: 'indigo' },
]

const TONES = [
  { value: 'professional', label: '专业' },
  { value: 'lively', label: '活泼' },
  { value: 'formal', label: '正式' },
  { value: 'humorous', label: '幽默' },
  { value: 'emotional', label: '感性' },
  { value: 'persuasive', label: '说服力' },
]

const LENGTHS = [
  { value: 'short', label: '短文案', desc: '100-200字' },
  { value: 'medium', label: '标准', desc: '300-500字' },
  { value: 'long', label: '长文', desc: '800-1500字' },
]

const TEMPLATES = [
  { name: '新品上市', icon: '🚀', prompt: '为一款全新的[产品名称]撰写上市营销文案，核心卖点包括[卖点1]、[卖点2]，目标受众是[人群]，希望突出[差异化优势]' },
  { name: '节日促销', icon: '🎉', prompt: '为[节日名称]促销活动撰写文案，折扣力度[XX折]，活动时间[日期]，主推产品[产品名]，营造紧迫感和购买欲' },
  { name: '小红书种草', icon: '📕', prompt: '写一篇小红书种草笔记，产品是[产品名]，使用体验[感受]，适合[场景]，语气要真实自然，带emoji' },
  { name: '朋友圈文案', icon: '💬', prompt: '写一条朋友圈营销文案，产品/服务是[名称]，要简短有力，引发互动，不超过100字' },
  { name: '邮件营销', icon: '📧', prompt: '写一封营销邮件，目的是[目的]，收件人是[人群]，核心信息是[内容]，需要包含CTA行动号召' },
  { name: '品牌故事', icon: '📖', prompt: '为品牌[品牌名]撰写品牌故事，品牌创立于[时间]，核心理念是[理念]，要打动人心，传递品牌价值' },
  { name: 'SEO长文', icon: '🔍', prompt: '围绕关键词[关键词]撰写一篇SEO优化文章，目标读者是[人群]，需要覆盖[子话题1]和[子话题2]，字数1000字以上' },
  { name: '产品详情', icon: '📦', prompt: '为产品[产品名]撰写详情页文案，包含：产品亮点、规格参数、使用场景、用户评价摘要、购买理由' },
]

export default function CopywritingPage() {
  const toast = useToast()
  const [prompt, setPrompt] = useState('')
  const [type, setType] = useState('marketing')
  const [title, setTitle] = useState('')
  const [tone, setTone] = useState('professional')
  const [length, setLength] = useState('medium')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [showTemplates, setShowTemplates] = useState(true)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [favorites, setFavorites] = useState(() => {
    try { return JSON.parse(localStorage.getItem('copywriting_favorites') || '[]') } catch { return [] }
  })
  const fileInputRef = useRef(null)

  useEffect(() => { loadHistory() }, [])
  const loadHistory = async () => {
    try { const res = await api.get('/api/copywriting/history'); setHistory(res.data) } catch (e) {}
  }

  const generate = async () => {
    const finalPrompt = fileContent
      ? `${prompt}\n\n---参考材料---\n${fileContent.slice(0, 2000)}`
      : prompt
    if (!finalPrompt.trim()) { toast.error('请输入文案需求'); return }
    setLoading(true); setResult('')
    try {
      const fullPrompt = `${finalPrompt}\n\n要求：语气风格为${TONES.find(t => t.value === tone)?.label}，篇幅控制在${LENGTHS.find(l => l.value === length)?.desc}。`
      const res = await api.post('/api/copywriting/generate', { type, title, prompt: fullPrompt })
      setResult(res.data.result); loadHistory(); toast.success('文案生成完成')
    } catch (e) { toast.error(`生成失败：${e.message}`) }
    finally { setLoading(false) }
  }

  const copyResult = () => {
    navigator.clipboard.writeText(result); setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const applyTemplate = (tpl) => {
    setPrompt(tpl.prompt)
    setShowTemplates(false)
    toast.success(`已应用模板：${tpl.name}`)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) { toast.error('文件不能超过 10MB'); return }
    setUploadedFile(file)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await api.post('/api/tools/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setFileContent(res.data.content || '')
      toast.success(`已上传: ${file.name}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || '上传失败')
      setUploadedFile(null)
    }
  }

  const removeFile = () => {
    setUploadedFile(null); setFileContent('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const reuseHistory = (item) => {
    setPrompt(item.prompt); setType(item.type); setTitle(item.title || ''); setResult(item.result)
  }

  const toggleFavorite = (item, e) => {
    e.stopPropagation()
    const isFav = favorites.some(f => f.id === item.id)
    const next = isFav ? favorites.filter(f => f.id !== item.id) : [...favorites, { id: item.id, prompt: item.prompt, type: item.type, title: item.title, created_at: item.created_at }]
    setFavorites(next)
    localStorage.setItem('copywriting_favorites', JSON.stringify(next))
    toast.success(isFav ? '已取消收藏' : '已收藏')
  }

  const regenerateFromHistory = (item, e) => {
    e.stopPropagation()
    setPrompt(item.prompt); setType(item.type); setTitle(item.title || '')
    toast.success('已填充，可修改后重新生成')
  }

  const deleteHistory = async (id, e) => {
    e.stopPropagation()
    try { await api.delete(`/api/copywriting/${id}`); loadHistory(); toast.success('已删除') } catch (e) {}
  }

  const currentType = TYPES.find(t => t.value === type)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 文案工厂"
        description="智能文案生成，覆盖营销、社媒、SEO、邮件等全场景"
        icon={PenTool}
        iconColor="from-pink-500 to-rose-600"
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '总文案数', value: history.length, icon: FileText, color: 'from-pink-500 to-rose-600' },
          { label: '本周生成', value: history.filter(h => { const d = new Date(h.created_at); const now = new Date(); return (now - d) < 7 * 86400000 }).length, icon: PenTool, color: 'from-purple-500 to-indigo-600' },
          { label: '常用类型', value: currentType?.label || '-', icon: Tag, color: 'from-blue-500 to-cyan-600' },
          { label: '模板数量', value: TEMPLATES.length, icon: Sparkles, color: 'from-amber-500 to-orange-600' },
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：输入区 */}
        <div className="space-y-4">
          {/* 文案类型 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <PenTool className="w-4 h-4 text-pink-500" /> 文案类型
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {TYPES.map(t => {
                const Icon = t.icon
                return (
                  <button key={t.value} onClick={() => setType(t.value)}
                    className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg text-xs border transition-all ${
                      type === t.value
                        ? 'bg-pink-50 border-pink-300 text-pink-700 font-medium shadow-sm'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}>
                    <Icon className="w-4 h-4" />
                    {t.label}
                  </button>
                )
              })}
            </div>
          </Card>

          {/* 提示词模板 */}
          <Card>
            <button onClick={() => setShowTemplates(!showTemplates)}
              className="flex items-center justify-between w-full">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" /> 场景模板
              </h3>
              <span className="text-xs text-gray-400">{showTemplates ? '收起' : '展开'}</span>
            </button>
            {showTemplates && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                {TEMPLATES.map((tpl, i) => (
                  <button key={i} onClick={() => applyTemplate(tpl)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 hover:border-pink-300 hover:bg-pink-50/50 transition-all text-left">
                    <span className="text-lg">{tpl.icon}</span>
                    <span className="text-sm text-gray-700">{tpl.name}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>

          {/* 输入区 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-pink-500" /> 文案需求
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">标题（可选）</label>
                <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="文案标题"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">需求描述 *</label>
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)}
                  placeholder="描述你的文案需求，如：为一款新的智能手表写营销文案，突出健康监测功能..."
                  rows={5} className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none" />
              </div>

              {/* 语气和长度 */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">语气风格</label>
                  <select value={tone} onChange={(e) => setTone(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none">
                    {TONES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">内容长度</label>
                  <select value={length} onChange={(e) => setLength(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none">
                    {LENGTHS.map(l => <option key={l.value} value={l.value}>{l.label} ({l.desc})</option>)}
                  </select>
                </div>
              </div>

              {/* 文件上传 */}
              <div>
                {uploadedFile ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-pink-50 border border-pink-200 rounded-lg">
                    <FileText className="w-4 h-4 text-pink-600" />
                    <span className="flex-1 text-sm text-gray-700 truncate">{uploadedFile.name}</span>
                    <button onClick={removeFile} className="text-gray-400 hover:text-red-500"><X className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <label className="flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-pink-400 hover:bg-pink-50/50 transition-colors">
                    <Upload className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-500">上传参考材料（可选）</span>
                    <input ref={fileInputRef} type="file" onChange={handleFileUpload}
                      accept=".txt,.md,.docx,.pdf" className="hidden" />
                  </label>
                )}
              </div>

              <Button variant="primary" icon={Play} loading={loading} onClick={generate} className="w-full">生成文案</Button>
            </div>
          </Card>
        </div>

        {/* 右侧：结果区 */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="min-h-[400px]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-pink-500" /> 生成结果
              </h3>
              {result && (
                <div className="flex items-center gap-2">
                  <ShareButton content={result} title="文案生成结果" contentType="copywriting" />
                  <Button variant="ghost" size="sm" icon={copied ? Check : Copy} onClick={copyResult}>
                    {copied ? '已复制' : '复制'}
                  </Button>
                </div>
              )}
            </div>
            {result ? (
              <MarkdownRenderer content={result} />
            ) : (
              <Empty icon={PenTool} title="等待生成" description="输入需求后点击生成" />
            )}
          </Card>
        </div>
      </div>

      {/* 历史记录 */}
      {history.length > 0 && (
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" /> 历史记录
          </h3>
          <div className="space-y-2">
            {history.slice(0, 10).map(item => {
              const tc = TYPES.find(t => t.value === item.type) || TYPES[0]
              const isFav = favorites.some(f => f.id === item.id)
              return (
                <div key={item.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors"
                  onClick={() => reuseHistory(item)}>
                  <Badge color={tc.color}>{tc.label}</Badge>
                  <span className="text-sm text-gray-700 truncate flex-1">{item.prompt?.slice(0, 80)}</span>
                  <span className="text-xs text-gray-400 flex-shrink-0">{item.created_at?.slice(0, 16).replace('T', ' ')}</span>
                  <button onClick={(e) => toggleFavorite(item, e)}
                    className={`p-1 rounded transition-colors flex-shrink-0 ${isFav ? 'text-amber-500' : 'text-gray-300 hover:text-amber-400'}`}
                    title={isFav ? '取消收藏' : '收藏'}>
                    <Star className="w-3.5 h-3.5" fill={isFav ? 'currentColor' : 'none'} />
                  </button>
                  <button onClick={(e) => regenerateFromHistory(item, e)}
                    className="p-1 text-gray-400 hover:text-blue-500 rounded transition-colors flex-shrink-0"
                    title="以此重新生成">
                    <Play className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={(e) => deleteHistory(item.id, e)}
                    className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors flex-shrink-0">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}
