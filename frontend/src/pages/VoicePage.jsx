import React, { useState, useEffect } from 'react'
import {
  Mic2, Sparkles, Loader2, Download, Trash2, Volume2, Clapperboard,
  Film, AudioLines, Gauge, FileEdit,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const SCENES = [
  { id: 'shortvideo', name: '短视频旁白', desc: '节奏明快，口播/知识解说', icon: Clapperboard, color: 'from-pink-500 to-rose-600' },
  { id: 'ad', name: '广告口播', desc: '有感染力，产品宣传/带货', icon: Sparkles, color: 'from-amber-500 to-orange-600' },
  { id: 'audiobook', name: '有声书', desc: '娓娓道来，故事/小说朗读', icon: AudioLines, color: 'from-violet-500 to-purple-600' },
  { id: 'news', name: '新闻播报', desc: '字正腔圆，资讯/播报类', icon: Mic2, color: 'from-blue-500 to-indigo-600' },
  { id: 'story', name: '儿童故事', desc: '活泼童趣，亲子/教育内容', icon: Volume2, color: 'from-emerald-500 to-green-600' },
  { id: 'custom', name: '自定义', desc: '自由选择音色与语速', icon: Gauge, color: 'from-gray-500 to-gray-700' },
]

const VOICES = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓', gender: '女', style: '温柔亲切', emoji: '👩' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊', gender: '女', style: '活泼俏皮', emoji: '👧' },
  { id: 'zh-CN-YunxiNeural', name: '云希', gender: '男', style: '阳光少年感', emoji: '👦' },
  { id: 'zh-CN-YunjianNeural', name: '云健', gender: '男', style: '成熟浑厚', emoji: '🧔' },
  { id: 'zh-CN-YunyangNeural', name: '云扬', gender: '男', style: '新闻播报感', emoji: '🎙️' },
  { id: 'zh-CN-XiaomoNeural', name: '晓墨', gender: '童', style: '童声可爱', emoji: '🧒' },
  { id: 'en-US-AriaNeural', name: 'Aria', gender: '女', style: '英文女声', emoji: '🇺🇸' },
  { id: 'en-US-ChristopherNeural', name: 'Christopher', gender: '男', style: '英文男声', emoji: '🇬🇧' },
]

function fmtDuration(sec) {
  if (!sec) return '--:--'
  const m = Math.floor(sec / 60), s = Math.round(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function VoicePage() {
  const toast = useToast()
  const [scene, setScene] = useState('shortvideo')
  const [text, setText] = useState('')
  const [voice, setVoice] = useState('zh-CN-XiaoxiaoNeural')
  const [speed, setSpeed] = useState(1.0)
  const [generating, setGenerating] = useState(false)
  const [items, setItems] = useState([])
  const [draftRestored, setDraftRestored] = useState(false)

  useEffect(() => { loadList() }, [])

  // 进入页面恢复草稿
  useEffect(() => {
    api.get('/api/drafts/voice').then((res) => {
      const d = res.data
      if (d?.content?.text) {
        setText(d.content.text)
        if (d.content.scene) setScene(d.content.scene)
        if (d.content.voice) setVoice(d.content.voice)
        if (d.content.speed) setSpeed(d.content.speed)
        setDraftRestored(true)
      }
    }).catch(() => {})
  }, [])

  // 输入防抖自动保存草稿
  useEffect(() => {
    if (!text.trim()) return
    const t = setTimeout(() => {
      api.post('/api/drafts/save', {
        tool_id: 'voice', title: text.slice(0, 30), content: { text, scene, voice, speed },
      }).catch(() => {})
    }, 1500)
    return () => clearTimeout(t)
  }, [text, scene, voice, speed])

  // 生成成功后清除草稿
  const clearDraft = async () => {
    try {
      const res = await api.get('/api/drafts/voice')
      if (res.data?.id) await api.delete(`/api/drafts/${res.data.id}`)
    } catch { /* ignore */ }
  }

  const loadList = async () => {
    try { const res = await api.get('/api/voice/list'); setItems(res.data || []) } catch (e) {}
  }

  const generate = async () => {
    if (!text.trim()) { toast.error('请输入要配音的文本'); return }
    setGenerating(true)
    try {
      const fd = new FormData()
      fd.append('text', text.trim())
      fd.append('scene', scene)
      fd.append('voice', scene === 'custom' ? voice : '')
      fd.append('speed', String(speed))
      const res = await api.post('/api/voice/generate', fd, { timeout: 180000 })
      toast.success(`配音完成：${fmtDuration(res.data.duration)}${res.data.segments > 1 ? `（${res.data.segments} 段自动拼接）` : ''}`)
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
    try { await api.delete(`/api/voice/${item.id}`); loadList(); toast.success('已删除') }
    catch (e) { toast.error(e.message) }
  }

  const sceneCfg = SCENES.find((s) => s.id === scene)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 配音工坊"
        description="文字转语音：选场景预设或自由音色，长文本自动分段拼接，短视频配音一步到位"
        icon={Mic2}
        iconColor="from-pink-500 to-rose-600"
      />

      {draftRestored && (
        <div className="flex items-center gap-2 text-xs text-sky-700 bg-sky-50 border border-sky-200 rounded-xl px-4 py-2.5">
          <FileEdit className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="flex-1">已恢复上次未完成的草稿，可直接继续生成或清空重写</span>
          <button onClick={() => { setText(''); setDraftRestored(false); api.get('/api/drafts/voice').then((r) => r.data?.id && api.delete(`/api/drafts/${r.data.id}`)).catch(() => {}) }}
            className="text-sky-600 hover:text-sky-800 font-medium">清空草稿</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── 左列：生成配置 ── */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-pink-500" /> 选择场景
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {SCENES.map((s) => (
                <button key={s.id} onClick={() => setScene(s.id)}
                  className={`flex flex-col items-start gap-1 px-3 py-2.5 rounded-xl border transition-all ${
                    scene === s.id ? 'bg-pink-50 border-pink-300 ring-2 ring-pink-500/20' : 'border-gray-200 hover:bg-gray-50'
                  }`}>
                  <span className={`w-7 h-7 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center text-white`}>
                    <s.icon className="w-4 h-4" />
                  </span>
                  <span className="text-xs font-medium text-gray-700">{s.name}</span>
                  <span className="text-[11px] text-gray-400 leading-tight">{s.desc}</span>
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <AudioLines className="w-4 h-4 text-violet-500" /> 配音文本
            </h3>
            <textarea value={text} onChange={(e) => setText(e.target.value)}
              placeholder="输入要配音的文字，如：大家好，欢迎来到小团智能平台，今天教你 3 分钟做出一个爆款短视频…"
              rows={6}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-pink-500/20 focus:border-pink-500 outline-none" />
            <div className="flex items-center justify-between mt-1">
              <span className="text-xs text-gray-400">{text.length} / 10000 字{text.length > 900 ? '（将自动分段拼接）' : ''}</span>
              <span className="text-[11px] text-gray-400">支持长文本自动分段</span>
            </div>

            {scene === 'custom' && (
              <div className="mt-3 space-y-3 border-t border-gray-100 pt-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">音色</label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {VOICES.map((v) => (
                      <button key={v.id} onClick={() => setVoice(v.id)}
                        className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-xs transition-all ${
                          voice === v.id ? 'bg-pink-50 border-pink-300 text-pink-700 font-medium' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                        }`}>
                        <span>{v.emoji}</span><span>{v.name} · {v.gender}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">语速：{speed.toFixed(2)}x</label>
                  <input type="range" min="0.5" max="2" step="0.05" value={speed}
                    onChange={(e) => setSpeed(parseFloat(e.target.value))} className="w-full accent-pink-500" />
                  <div className="flex justify-between text-[11px] text-gray-400"><span>慢</span><span>正常</span><span>快</span></div>
                </div>
              </div>
            )}

            <Button variant="primary" size="lg" icon={Mic2} loading={generating} onClick={generate}
              className="w-full mt-3 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700">
              {generating ? 'AI 配音中…' : `生成配音${sceneCfg ? `（${sceneCfg.name}）` : ''}`}
            </Button>
            {generating && (
              <div className="flex items-center gap-2 text-xs text-pink-600 bg-pink-50 border border-pink-100 rounded-lg px-3 py-2 mt-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                正在合成语音{text.length > 900 ? '（长文本分段合成中）' : ''}…
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <Film className="w-4 h-4 text-blue-500" /> 配音怎么用？
            </h3>
            <div className="space-y-2 text-sm text-gray-600">
              <p>① 生成后点 ▶ 试听，满意再下载 mp3</p>
              <p>② 去「视频工厂」生成视频素材，用剪映/PR 等工具把配音合入</p>
              <p>③ 也可以配合「发布中心」直接把成片发布到公众号/抖音/快手</p>
            </div>
          </Card>
        </div>

        {/* ── 右列：我的配音 ── */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <AudioLines className="w-4 h-4 text-gray-400" /> 我的配音（{items.length}）
            </h3>
            {items.length === 0 ? (
              <Empty icon={Mic2} title="还没有配音" description="选场景、输入文本，点击生成即可" />
            ) : (
              <div className="space-y-3">
                {items.map((item) => (
                  <div key={item.id} className="p-3 rounded-xl border border-gray-100 hover:border-pink-200 hover:bg-pink-50/30 transition-all">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="w-9 h-9 rounded-lg bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center text-white flex-shrink-0">
                        <Volume2 className="w-4 h-4" />
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">{item.id}</div>
                        <div className="text-xs text-gray-400">{fmtDuration(item.duration)} · {(item.size / 1024).toFixed(1)} KB · {item.created_at?.slice(0, 16).replace('T', ' ')}</div>
                      </div>
                      <button onClick={() => download(item)} className="p-1.5 text-gray-300 hover:text-blue-500 rounded-lg hover:bg-blue-50"><Download className="w-4 h-4" /></button>
                      <button onClick={() => remove(item)} className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50"><Trash2 className="w-4 h-4" /></button>
                    </div>
                    <audio controls src={item.url} className="w-full h-9" />
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
