import React, { useState, useRef, useEffect } from 'react'
import {
  Upload,
  Video,
  FileText,
  Download,
  Trash2,
  Clock,
  Play,
  Film,
  Eye,
  Sparkles,
  Copy,
  RefreshCw,
  Volume2,
  Gauge,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'

export default function VideoAnalyzerPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  const fileRef = useRef(null)

  const [uploading, setUploading] = useState(false)
  const [task, setTask] = useState(null)
  const [videoInfo, setVideoInfo] = useState(null)
  const [result, setResult] = useState(null)
  const [records, setRecords] = useState([])

  useEffect(() => {
    loadRecords()
  }, [])

  const loadRecords = async () => {
    try {
      const res = await api.get('/api/video/records')
      setRecords(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    // 边界校验：拒绝超大文件（后端默认上限 200MB），提前提示避免上传中断
    if (file.size > 200 * 1024 * 1024) {
      toast.error('文件过大：单次上传请控制在 200MB 以内')
      e.target.value = ''
      return
    }
    if (!/video\//.test(file.type) && !/\.(mp4|mov|avi|webm|mkv)$/i.test(file.name)) {
      toast.error('不支持的视频格式，请上传 MP4 / MOV / AVI / WebM')
      e.target.value = ''
      return
    }

    setUploading(true)
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/video/upload', form)
      setVideoInfo(res.data)
      toast.success(res.data.message || '上传成功')
    } catch (err) {
      toast.error(`上传失败：${err.response?.data?.detail || err.message}`)
    }
    setUploading(false)
  }

  const handleAnalyze = async () => {
    if (!videoInfo?.video_id || task) return
    await submitTask(
      '/api/video/analyze',
      { video_id: videoInfo.video_id, description: '' },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setResult(data)
          setTask(null)
          loadRecords()
          toast.success('视频分析完成')
        },
        onError: (err) => {
          setTask(null)
          toast.error(`分析失败：${err.message}`)
        },
      }
    )
  }

  const deleteRecord = async (id) => {
    try {
      await api.delete(`/api/video/records/${id}`)
      loadRecords()
      toast.success('已删除')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const buildReportMd = (res) => {
    if (!res) return ''
    const lines = [
      '# 视频分析报告',
      '',
      `- 标题：${res.title || '-'}`,
      `- 基调：${res.tone || '-'}`,
      `- 目标受众：${res.target_audience || '-'}`,
      '',
      '## 内容摘要',
      '',
      res.summary || '-',
      '',
    ]
    if (res.key_scenes?.length) {
      lines.push('## 关键场景', '')
      res.key_scenes.forEach((s) => lines.push(`- [${s.timestamp}] ${s.description}（${s.importance}）`))
      lines.push('')
    }
    if (res.highlights?.length) {
      lines.push('## 内容亮点', '')
      res.highlights.forEach((h) => lines.push(`- ${h}`))
      lines.push('')
    }
    if (res.recommendations?.length) {
      lines.push('## 优化建议', '')
      res.recommendations.forEach((r) => lines.push(`- ${r}`))
      lines.push('')
    }
    if (res.segments) {
      lines.push('## 分段报告（画面 / 音频 / 文本）', '')
      ;[
        ['visual', '画面'],
        ['audio', '音频'],
        ['text', '文本'],
      ].forEach(([key, label]) => {
        const seg = res.segments[key]
        if (!seg) return
        lines.push(`### ${label}${seg.score != null ? `（${seg.score} 分）` : ''}`, '')
        lines.push(seg.analysis || '-', '')
        ;(seg.key_points || []).forEach((p) => lines.push(`- ${p}`))
        lines.push('')
      })
    }
    lines.push('---', `由小团智能平台 AI 视频分析生成 · ${new Date().toLocaleString()}`)
    return lines.join('\n')
  }

  const copyReport = async () => {
    const md = buildReportMd(result)
    if (!md) return
    try {
      await navigator.clipboard.writeText(md)
      toast.success('分析报告已复制')
    } catch {
      toast.error('复制失败，请手动选择复制')
    }
  }

  const downloadReport = async () => {
    if (!result?.video_id) {
      toast.error('暂无分析结果可导出')
      return
    }
    try {
      const res = await api.get(`/api/video/records/${result.video_id}/report`)
      const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = res.data.filename || '视频分析报告.md'
      a.click()
      URL.revokeObjectURL(a.href)
      toast.success('分析报告已下载')
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '下载失败')
    }
  }

  // 分段轨道渲染配置
  const SEGMENT_ITEMS = [
    { key: 'visual', label: '画面', icon: Film, color: 'text-amber-500', bar: 'from-amber-400 to-orange-500' },
    { key: 'audio', label: '音频', icon: Volume2, color: 'text-sky-500', bar: 'from-sky-400 to-indigo-500' },
    { key: 'text', label: '文本', icon: FileText, color: 'text-emerald-500', bar: 'from-emerald-400 to-teal-500' },
  ]

  const scoreColor = (s) => {
    if (s == null) return 'bg-gray-200'
    if (s >= 80) return 'bg-emerald-500'
    if (s >= 60) return 'bg-amber-500'
    return 'bg-red-500'
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI视频理解"
        description="上传视频 → AI自动分析：内容摘要、关键场景、字幕生成、优化建议"
        icon={Video}
        iconColor="from-red-500 to-pink-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：上传 + 控制 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Upload className="w-4 h-4 text-red-500" /> 上传视频
            </h3>
            <input
              ref={fileRef}
              type="file"
              accept="video/*"
              onChange={handleUpload}
              className="hidden"
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full py-12 border-2 border-dashed border-gray-300 rounded-xl hover:border-red-400 hover:bg-red-50/30 transition-all flex flex-col items-center gap-3"
            >
              <Upload className="w-10 h-10 text-gray-400" />
              <div className="text-sm text-gray-500">
                {uploading ? '上传中...' : '点击选择视频文件'}
              </div>
              <div className="text-xs text-gray-400">支持 MP4 / MOV / AVI / WebM</div>
            </button>

            {videoInfo && (
              <div className="mt-4 p-3 bg-emerald-50 rounded-lg space-y-1.5 text-sm">
                <div className="font-medium text-emerald-800">{videoInfo.filename}</div>
                <div className="text-xs text-emerald-600">
                  大小：{(videoInfo.file_size / 1024 / 1024).toFixed(1)} MB
                  {videoInfo.duration && ` · 时长：${videoInfo.duration}s`}
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  icon={Sparkles}
                  loading={!!task}
                  onClick={() => handleAnalyze()}
                  className="w-full mt-2"
                >
                  开始智能分析
                </Button>
                {task && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>{task.stage || 'AI 分析中…'}</span>
                      <span>{task.progress || 0}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-red-500 to-pink-500 rounded-full transition-all duration-300"
                        style={{ width: `${task.progress || 0}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 历史记录（{records.length}）
            </h3>
            {records.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4">暂无记录</div>
            ) : (
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {records.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between p-2 rounded-lg bg-gray-50 text-xs"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-700 truncate">{r.filename}</div>
                      <div className="text-gray-400">
                        {(r.file_size / 1024 / 1024).toFixed(1)}MB · {r.created_at?.slice(0, 10)}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Badge color={r.status === 'done' ? 'green' : 'gray'}>
                        {r.status === 'done' ? '已分析' : '已上传'}
                      </Badge>
                      <button
                        onClick={() => deleteRecord(r.id)}
                        className="p-1 text-gray-300 hover:text-red-500"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：结果展示 */}
        <div className="lg:col-span-2 space-y-4">
          {task ? (
            <Card className="border-red-200">
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <Sparkles className="w-5 h-5 text-red-500 animate-pulse" />
                <span>{task.stage || 'AI 正在分析视频…'}</span>
                <span className="text-gray-400 ml-auto">{task.progress || 0}%</span>
              </div>
            </Card>
          ) : !result ? (
            <Empty
              icon={Eye}
              title="等待分析"
              description="上传视频后点击「开始智能分析」，AI将自动生成详细报告"
            />
          ) : (
            <>
              <Card className="border-red-200">
                <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
                  <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    <Film className="w-4 h-4 text-red-500" /> 视频概览
                  </h3>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => handleAnalyze()}>
                      重新分析
                    </Button>
                    <Button variant="ghost" size="sm" icon={Copy} onClick={copyReport}>
                      复制报告
                    </Button>
                    <Button variant="ghost" size="sm" icon={Download} onClick={downloadReport}>
                      下载报告
                    </Button>
                    <ShareButton
                      content={buildReportMd(result)}
                      title={`视频分析：${result.title}`}
                      contentType="video_analysis"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-gray-500">标题</div>
                    <div className="font-medium text-gray-800">{result.title}</div>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-gray-500">基调</div>
                    <div className="font-medium text-gray-800">{result.tone}</div>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-gray-500">目标受众</div>
                    <div className="font-medium text-gray-800">{result.target_audience}</div>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-gray-500">话题</div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {result.topics?.map((t, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                {result.overall_score != null && (
                  <div className="mt-3 p-3 rounded-xl bg-gradient-to-r from-red-50 to-orange-50 border border-red-100">
                    <div className="flex items-center gap-3">
                      <Gauge className="w-5 h-5 text-red-500 flex-shrink-0" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                          <span>综合评分</span>
                          <span className="font-bold text-gray-800">{result.overall_score} / 100</span>
                        </div>
                        <div className="h-2 bg-white/70 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${scoreColor(result.overall_score)}`}
                            style={{ width: `${result.overall_score}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </Card>

              <Card>
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-500" /> 内容摘要
                </h3>
                <p className="text-sm text-gray-700 leading-relaxed">{result.summary}</p>
                {result.detailed_summary && (
                  <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
                    {result.detailed_summary}
                  </div>
                )}
              </Card>

              {/* 分段报告：画面 / 音频 / 文本 */}
              {result.segments && (
                <Card className="border-amber-200">
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-amber-500" /> 分段报告
                    <span className="text-xs font-normal text-gray-400">画面 / 音频 / 文本 三轨评估</span>
                  </h3>
                  <div className="grid md:grid-cols-3 gap-3">
                    {SEGMENT_ITEMS.map(({ key, label, icon: Icon, color, bar }) => {
                      const seg = result.segments[key]
                      if (!seg) return null
                      return (
                        <div key={key} className="p-3.5 rounded-xl border border-amber-100 bg-amber-50/40">
                          <div className="flex items-center justify-between mb-2">
                            <span className={`flex items-center gap-1.5 text-sm font-medium ${color}`}>
                              <Icon className="w-4 h-4" /> {label}
                            </span>
                            <span className="text-sm font-bold text-gray-800">
                              {seg.score != null ? `${seg.score} 分` : '—'}
                            </span>
                          </div>
                          {seg.score != null && (
                            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden mb-2.5">
                              <div
                                className={`h-full rounded-full bg-gradient-to-r ${bar}`}
                                style={{ width: `${seg.score}%` }}
                              />
                            </div>
                          )}
                          <p className="text-xs text-gray-600 leading-relaxed">{seg.analysis}</p>
                          {seg.key_points?.length > 0 && (
                            <ul className="mt-2 space-y-1">
                              {seg.key_points.map((p, i) => (
                                <li key={i} className="flex gap-1.5 text-xs text-gray-500">
                                  <span className="text-amber-500 flex-shrink-0">•</span>
                                  <span className="line-clamp-2">{p}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </Card>
              )}

              {/* 关键场景 */}
              {result.key_scenes?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Play className="w-4 h-4 text-amber-500" /> 关键场景（{result.key_scenes.length}
                    ）
                  </h3>
                  <div className="space-y-2">
                    {result.key_scenes.map((s, i) => (
                      <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-gray-50">
                        <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-mono">
                          {s.timestamp}
                        </span>
                        <span className="text-sm text-gray-700 flex-1">{s.description}</span>
                        <Badge
                          color={
                            s.importance === '高' ? 'red' : s.importance === '中' ? 'amber' : 'gray'
                          }
                        >
                          {s.importance}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* 亮点 + 建议 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {result.highlights?.length > 0 && (
                  <Card>
                    <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-yellow-500" /> 内容亮点
                    </h3>
                    <ul className="space-y-1.5 text-sm text-gray-600">
                      {result.highlights.map((h, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-yellow-500">✦</span> {h}
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}
                {result.recommendations?.length > 0 && (
                  <Card>
                    <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                      <Eye className="w-4 h-4 text-emerald-500" /> 优化建议
                    </h3>
                    <ul className="space-y-1.5 text-sm text-gray-600">
                      {result.recommendations.map((r, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-emerald-500">▸</span> {r}
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}
              </div>

              {/* 字幕 */}
              {result.subtitles_text && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-gray-500" /> 模拟字幕
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={Download}
                      onClick={() => {
                        const blob = new Blob([result.subtitles_text], { type: 'text/plain' })
                        const a = document.createElement('a')
                        a.href = URL.createObjectURL(blob)
                        a.download = 'subtitles.txt'
                        a.click()
                      }}
                    >
                      下载字幕
                    </Button>
                  </h3>
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 p-3 rounded-lg max-h-40 overflow-y-auto">
                    {result.subtitles_text}
                  </pre>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
