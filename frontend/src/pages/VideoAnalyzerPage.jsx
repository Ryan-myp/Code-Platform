import React, { useState, useRef, useEffect } from 'react'
import { Upload, Video, FileText, Download, Trash2, Clock, Play, Film, Eye, Sparkles } from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

export default function VideoAnalyzerPage() {
  const toast = useToast()
  const fileRef = useRef(null)

  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [videoInfo, setVideoInfo] = useState(null)
  const [result, setResult] = useState(null)
  const [records, setRecords] = useState([])

  useEffect(() => { loadRecords() }, [])

  const loadRecords = async () => {
    try {
      const res = await api.get('/api/video/records')
      setRecords(res.data || [])
    } catch {}
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

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
    if (!videoInfo?.video_id) return
    setAnalyzing(true)
    try {
      const res = await api.post('/api/video/analyze', { video_id: videoInfo.video_id, description: '' })
      setResult(res.data)
      loadRecords()
      toast.success('视频分析完成')
    } catch (err) {
      toast.error(`分析失败：${err.response?.data?.detail || err.message}`)
    }
    setAnalyzing(false)
  }

  const deleteRecord = async (id) => {
    try { await api.delete(`/api/video/records/${id}`); loadRecords(); toast.success('已删除') }
    catch (err) { toast.error(err.message) }
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
            <input ref={fileRef} type="file" accept="video/*" onChange={handleUpload} className="hidden" />
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
                <Button variant="primary" size="sm" icon={Sparkles} loading={analyzing} onClick={handleAnalyze} className="w-full mt-2">
                  开始智能分析
                </Button>
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
                  <div key={r.id} className="flex items-center justify-between p-2 rounded-lg bg-gray-50 text-xs">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-700 truncate">{r.filename}</div>
                      <div className="text-gray-400">{(r.file_size/1024/1024).toFixed(1)}MB · {r.created_at?.slice(0,10)}</div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Badge color={r.status === 'done' ? 'green' : 'gray'}>{r.status === 'done' ? '已分析' : '已上传'}</Badge>
                      <button onClick={() => deleteRecord(r.id)} className="p-1 text-gray-300 hover:text-red-500">
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
          {!result ? (
            <Empty icon={Eye} title="等待分析" description="上传视频后点击「开始智能分析」，AI将自动生成详细报告" />
          ) : (
            <>
              <Card className="border-red-200">
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <Film className="w-4 h-4 text-red-500" /> 视频概览
                </h3>
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
                        <span key={i} className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs">{t}</span>
                      ))}
                    </div>
                  </div>
                </div>
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

              {/* 关键场景 */}
              {result.key_scenes?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Play className="w-4 h-4 text-amber-500" /> 关键场景（{result.key_scenes.length}）
                  </h3>
                  <div className="space-y-2">
                    {result.key_scenes.map((s, i) => (
                      <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-gray-50">
                        <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-mono">{s.timestamp}</span>
                        <span className="text-sm text-gray-700 flex-1">{s.description}</span>
                        <Badge color={s.importance === '高' ? 'red' : s.importance === '中' ? 'amber' : 'gray'}>{s.importance}</Badge>
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
                        <li key={i} className="flex gap-2"><span className="text-yellow-500">✦</span> {h}</li>
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
                        <li key={i} className="flex gap-2"><span className="text-emerald-500">▸</span> {r}</li>
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
                    <Button variant="secondary" size="sm" icon={Download}
                      onClick={() => {
                        const blob = new Blob([result.subtitles_text], { type: 'text/plain' })
                        const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
                        a.download = 'subtitles.txt'; a.click()
                      }}>
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
