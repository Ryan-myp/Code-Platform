import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic2, Sparkles, Play, Download, Trash2, UserCircle, Music2,
  Film, Eye, Clock, FileText, RefreshCw, Wand2, Check, Send,
  Image as ImageIcon, Palette, Radio, Volume2, Pause, StopCircle,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Modal, Badge } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import AnimatedAvatar from '../components/AnimatedAvatar'

const SCENES = [
  { id: 'product', name: '产品介绍', desc: '突出卖点，节奏明快', icon: Sparkles, color: 'from-amber-500 to-orange-600' },
  { id: 'course', name: '课程讲解', desc: '结构化讲解', icon: FileText, color: 'from-blue-500 to-indigo-600' },
  { id: 'news', name: '新闻播报', desc: '字正腔圆', icon: Radio, color: 'from-gray-700 to-gray-900' },
  { id: 'livestream', name: '直播带货', desc: '感染力强', icon: Wand2, color: 'from-pink-500 to-rose-600' },
  { id: 'story', name: '故事讲述', desc: '情感丰富', icon: Volume2, color: 'from-violet-500 to-purple-600' },
]

export default function DigitalHumanPage() {
  const toast = useToast()

  // 生成表单
  const [text, setText] = useState('')
  const [avatarId, setAvatarId] = useState('business-female')
  const [voiceId, setVoiceId] = useState('zh-CN-XiaoxiaoNeural')
  const [bgId, setBgId] = useState('tech')
  const [sceneId, setSceneId] = useState('product')
  const [speed, setSpeed] = useState(1.0)
  const [generating, setGenerating] = useState(false)

  // 数据
  const [avatars, setAvatars] = useState([])
  const [voices, setVoices] = useState([])
  const [backgrounds, setBackgrounds] = useState([])
  const [records, setRecords] = useState([])
  const [result, setResult] = useState(null)

  // 文案素材库
  const [articles, setArticles] = useState([])
  const [showArticles, setShowArticles] = useState(false)

  // 音频播放 + 口型同步
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [talking, setTalking] = useState(false)
  const [audioUrl, setAudioUrl] = useState('')

  useEffect(() => { loadData(); loadRecords() }, [])

  const loadData = async () => {
    try {
      const [aRes, vRes, bRes] = await Promise.all([
        api.get('/api/digital-human/avatars'),
        api.get('/api/digital-human/voices'),
        api.get('/api/digital-human/backgrounds'),
      ])
      setAvatars(aRes.data?.avatars || [])
      setVoices(vRes.data?.voices || [])
      setBackgrounds(bRes.data?.backgrounds || [])
    } catch (e) {}
  }

  const loadRecords = async () => {
    try {
      const res = await api.get('/api/digital-human/records')
      setRecords(res.data || [])
    } catch (e) {}
  }

  const loadArticles = async () => {
    try {
      const res = await api.get('/api/publish/assets')
      setArticles(res.data?.articles || [])
      setShowArticles(true)
    } catch (e) { toast.error('加载文案失败') }
  }

  const generate = async () => {
    if (!text.trim()) { toast.error('请输入口播文案'); return }
    setGenerating(true); setResult(null); stopAudio()
    try {
      const res = await api.post('/api/digital-human/generate', {
        text: text.trim(), avatar_id: avatarId, voice_id: voiceId,
        background_id: bgId, scene_id: sceneId, speed,
      })
      setResult(res.data)
      loadRecords()
      // 如果有音频URL，自动播放
      if (res.data.audio_url) {
        const fullUrl = res.data.audio_url.startsWith('http')
          ? res.data.audio_url
          : `http://127.0.0.1:8000${res.data.audio_url}`
        setAudioUrl(fullUrl)
        // 延迟确保 audio 元素挂载后再播放
        setTimeout(() => {
          if (audioRef.current) {
            audioRef.current.play().then(() => {
              setPlaying(true)
              setTalking(true)
            }).catch(() => {})
          }
        }, 300)
      }
      toast.success(res.data.message || '生成成功')
    } catch (e) { toast.error(`生成失败：${e.message}`) }
    finally { setGenerating(false) }
  }

  const playAudio = useCallback(() => {
    if (!audioRef.current) return
    audioRef.current.play().then(() => { setPlaying(true); setTalking(true) }).catch(() => {})
  }, [])

  const pauseAudio = useCallback(() => {
    if (!audioRef.current) return
    audioRef.current.pause()
    setPlaying(false)
    setTalking(false)
  }, [])

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    setPlaying(false)
    setTalking(false)
  }, [])

  const deleteRecord = async (id) => {
    try { await api.delete(`/api/digital-human/records/${id}`); loadRecords(); toast.success('已删除') }
    catch (e) { toast.error(e.message) }
  }

  const useArticle = (a) => {
    setText(a.result || a.prompt || '')
    setShowArticles(false)
    toast.success('已加载文案')
  }

  const selectedAvatar = avatars.find(a => a.id === avatarId)
  const selectedVoice = voices.find(v => v.id === voiceId)
  const selectedBg = backgrounds.find(b => b.id === bgId)

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI数字人"
        description="文案→配音→口播视频，8大虚拟形象+8种音色+6款背景，一键生成数字人口播视频"
        icon={UserCircle}
        iconColor="from-violet-500 to-purple-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左列：配置面板 */}
        <div className="space-y-4">
          {/* 场景模板 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Radio className="w-4 h-4 text-amber-500" /> 场景模板
            </h3>
            <div className="space-y-1.5">
              {SCENES.map((s) => (
                <button key={s.id} onClick={() => { setSceneId(s.id) }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs transition-all ${
                    sceneId === s.id ? 'bg-violet-50 border border-violet-200 text-violet-700 font-medium' : 'border border-gray-100 text-gray-600 hover:bg-gray-50'
                  }`}>
                  <s.icon className="w-3.5 h-3.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">{s.name}</div>
                    <div className="text-[10px] text-gray-400">{s.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </Card>

          {/* 数字人形象 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <UserCircle className="w-4 h-4 text-blue-500" /> 数字人形象
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {avatars.map((a) => (
                <button key={a.id} onClick={() => setAvatarId(a.id)}
                  className={`flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition-all ${
                    avatarId === a.id ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-500/20' : 'border-gray-100 hover:border-violet-200 hover:bg-violet-50/30'
                  }`}>
                  <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${a.bg_color} flex items-center justify-center text-lg`}>
                    {a.emoji}
                  </div>
                  <div className="text-xs font-medium text-gray-800">{a.name}</div>
                  <div className="text-[10px] text-gray-400">{a.style}</div>
                </button>
              ))}
            </div>
          </Card>

          {/* 声音选择 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Mic2 className="w-4 h-4 text-pink-500" /> 声音选择
            </h3>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {voices.map((v) => (
                <button key={v.id} onClick={() => setVoiceId(v.id)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all ${
                    voiceId === v.id ? 'bg-pink-50 border border-pink-200 text-pink-700 font-medium' : 'border border-gray-100 text-gray-600 hover:bg-gray-50'
                  }`}>
                  <span className="text-base">{v.emoji}</span>
                  <div className="flex-1 text-left">
                    <div className="font-medium">{v.name} · {v.gender}</div>
                    <div className="text-[10px] text-gray-400">{v.style}</div>
                  </div>
                  {voiceId === v.id && <Check className="w-3.5 h-3.5 text-pink-500 flex-shrink-0" />}
                </button>
              ))}
            </div>
            <div className="mt-2">
              <label className="text-xs text-gray-500">语速：{speed.toFixed(1)}x</label>
              <input type="range" min={0.5} max={2.0} step={0.05} value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                className="w-full mt-1 accent-violet-500" />
            </div>
          </Card>

          {/* 背景选择 */}
          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Palette className="w-4 h-4 text-emerald-500" /> 虚拟背景
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {backgrounds.map((b) => (
                <button key={b.id} onClick={() => setBgId(b.id)}
                  className={`flex flex-col items-center gap-1 p-2 rounded-xl border transition-all ${
                    bgId === b.id ? 'border-emerald-400 bg-emerald-50 ring-2 ring-emerald-500/20' : 'border-gray-100 hover:border-emerald-200'
                  }`}>
                  <div className="w-8 h-8 rounded-lg" style={{ background: b.color }} />
                  <div className="text-[10px] font-medium text-gray-700">{b.name}</div>
                </button>
              ))}
            </div>
          </Card>
        </div>

        {/* 中列：文案编辑 + 生成 */}
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-violet-500" /> 口播文案
                <span className="text-xs font-normal text-gray-400">（{text.length} 字）</span>
              </h3>
              <Button variant="secondary" size="sm" icon={FileText} onClick={loadArticles}>
                从素材库加载
              </Button>
            </div>
            <textarea value={text} onChange={(e) => setText(e.target.value)}
              placeholder="输入口播文案，AI 会自动优化为更流畅自然的口播脚本…&#10;&#10;如：大家好，今天给大家介绍一款全新的AI效率工具，它可以在30秒内帮你完成…"
              rows={12}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none" />
          </Card>

          {/* 生成按钮 */}
          <div className="flex gap-2">
            <Button variant="primary" size="lg" icon={Sparkles} loading={generating} onClick={generate} className="flex-1">
              {generating ? 'AI数字人正在生成…' : '生成数字人视频'}
            </Button>
          </div>

          {/* 预览区 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Eye className="w-4 h-4 text-violet-500" /> 实时预览
                {talking && <span className="text-[10px] text-emerald-500 font-normal animate-pulse">● 口型同步中</span>}
              </h3>
              {/* 音频播放控制 */}
              {audioUrl && (
                <div className="flex items-center gap-1">
                  {playing ? (
                    <Button variant="secondary" size="sm" icon={Pause} onClick={pauseAudio}>暂停</Button>
                  ) : (
                    <Button variant="secondary" size="sm" icon={Play} onClick={playAudio}>播放</Button>
                  )}
                  <Button variant="ghost" size="sm" icon={StopCircle} onClick={stopAudio} />
                </div>
              )}
            </div>
            <div className="relative rounded-xl overflow-hidden border border-gray-200 bg-gray-900 flex items-center justify-center">
              <AnimatedAvatar
                avatarId={avatarId}
                width={400}
                height={350}
                talking={talking}
                audioElement={audioRef.current}
              />
              {/* 背景渐变叠加 */}
              <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ background: selectedBg?.color || '#667eea' }} />
              {/* 底部信息条 */}
              <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/60 to-transparent">
                <div className="flex items-center justify-center gap-3 text-white/80 text-xs">
                  <span className="flex items-center gap-1"><UserCircle className="w-3 h-3" /> {selectedAvatar?.name || '选择形象'}</span>
                  <span className="flex items-center gap-1"><Volume2 className="w-3 h-3" /> {selectedVoice?.name || ''}</span>
                </div>
              </div>
            </div>
            {/* 隐藏的 audio 元素 */}
            {audioUrl && (
              <audio
                ref={audioRef}
                src={audioUrl}
                onEnded={() => { setPlaying(false); setTalking(false) }}
                onPause={() => setPlaying(false)}
                className="hidden"
                crossOrigin="anonymous"
              />
            )}
          </Card>
        </div>

        {/* 右列：生成结果 + 历史 */}
        <div className="space-y-4">
          {/* 生成结果 */}
          {result && (
            <Card className="border-violet-200">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-500" /> 生成结果
              </h3>
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800 mb-3">
                {result.message}
              </div>
              <div className="space-y-2 text-xs text-gray-600">
                <div className="flex justify-between">
                  <span>数字人：</span>
                  <span className="font-medium">{result.avatar?.name} {result.avatar?.emoji}</span>
                </div>
                <div className="flex justify-between">
                  <span>声音：</span>
                  <span className="font-medium">{result.voice?.name}</span>
                </div>
                <div className="flex justify-between">
                  <span>文案长度：</span>
                  <span className="font-medium">{result.text_length} 字</span>
                </div>
                <div className="flex justify-between">
                  <span>状态：</span>
                  <Badge color={result.status === 'done' ? 'green' : 'amber'}>
                    {result.status === 'done' ? '已完成' : '仅音频'}
                  </Badge>
                </div>
                {result.record_id && (
                  <div className="text-[10px] text-gray-400 mt-2">记录 ID：{result.record_id}</div>
                )}
              </div>
            </Card>
          )}

          {/* 历史记录 */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-500" /> 历史记录（{records.length}）
              </h3>
              <Button variant="secondary" size="sm" icon={RefreshCw} onClick={loadRecords}>刷新</Button>
            </div>
            {records.length === 0 ? (
              <Empty icon={Film} title="暂无记录" description="生成第一个数字人视频后这里会显示" />
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {records.map((r) => {
                  const av = avatars.find(a => a.id === r.avatar_id)
                  return (
                    <div key={r.id} className={`p-3 rounded-xl border transition-all ${
                      r.status === 'done' ? 'border-emerald-200 bg-emerald-50/30' : 'border-amber-200 bg-amber-50/30'
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-lg">{av?.emoji || '👤'}</span>
                          <div>
                            <div className="text-xs font-medium text-gray-800">{av?.name || r.avatar_name}</div>
                            <div className="text-[10px] text-gray-400">{r.voice_name} · {r.text_length}字</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <Badge color={r.status === 'done' ? 'green' : 'amber'}>
                            {r.status === 'done' ? '完成' : '仅音频'}
                          </Badge>
                          <button onClick={() => deleteRecord(r.id)}
                            className="p-1 text-gray-300 hover:text-red-500 rounded">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 truncate mt-1">{r.text?.slice(0, 60)}</p>
                      <div className="text-[10px] text-gray-400 mt-1">{r.created_at?.slice(0, 16)?.replace('T', ' ')}</div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* 文案素材库 Modal */}
      <Modal open={showArticles} onClose={() => setShowArticles(false)} title="从素材库加载文案" size="md">
        {articles.length === 0 ? (
          <Empty icon={FileText} title="暂无素材" description="请先在发布中心或文案工厂生成文章" />
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {articles.map((a) => (
              <div key={a.id} className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-violet-200 hover:bg-violet-50/30 transition-all cursor-pointer"
                onClick={() => useArticle(a)}>
                <FileText className="w-4 h-4 text-violet-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">{a.title || a.prompt?.slice(0, 40) || '未命名'}</div>
                  <div className="text-xs text-gray-400 truncate">{(a.result || a.prompt || '').slice(0, 80)}</div>
                </div>
                <span className="text-xs text-gray-400 flex-shrink-0">{a.created_at?.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  )
}
