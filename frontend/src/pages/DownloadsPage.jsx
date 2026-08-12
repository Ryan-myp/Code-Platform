import React, { useState, useEffect } from 'react'
import { useI18n } from '../i18n/index.jsx'
import { Download, FileText, Image, Film, Music, Archive, Trash2, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
const { t } = useI18n()

const FILE_ICONS = {
  image: Image,
  video: Film,
  audio: Music,
  document: FileText,
  archive: Archive,
  default: FileText,
}

const FILE_TYPES = {
  'image/png': 'image', 'image/jpeg': 'image', 'image/gif': 'image',
  'video/mp4': 'video', 'video/webm': 'video',
  'audio/mpeg': 'audio', 'audio/wav': 'audio',
  'application/pdf': 'document', 'text/plain': 'document',
  'application/zip': 'archive',
}

export default function DownloadsPage() {
  const toast = useToast()
  const [downloads, setDownloads] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    loadDownloads()
  }, [])

  const loadDownloads = async () => {
    setLoading(true)
    try {
      // 从drafts表获取下载记录
      const res = await api.get('/api/drafts')
      const items = res.data?.drafts || []
      setDownloads(items)
    } catch (e) {
      console.error('Load downloads error:', e)
      setDownloads([])
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定要删除这条记录吗？')) return
    try {
      await api.delete(`/api/drafts/${id}`)
      toast.success('删除成功')
      loadDownloads()
    } catch (e) {
      toast.error('删除失败')
    }
  }

  const getFileIcon = (type) => {
    const fileType = FILE_TYPES[type] || 'default'
    const Icon = FILE_ICONS[fileType] || FILE_ICONS.default
    return <Icon className="w-5 h-5" />
  }

  const filtered = filter === 'all' ? downloads : downloads.filter(d => d.type === filter)
  const types = ['all', ...new Set(downloads.map(d => d.type))]

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-gray-500 mt-3">加载中…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-page-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">下载管理</h1>
          <p className="text-gray-500 text-sm mt-1">管理您下载的文件和创作记录</p>
        </div>
        <button onClick={loadDownloads} className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors">
          <RefreshCw className="w-4 h-4" />
          <span className="text-sm">刷新</span>
        </button>
      </div>

      {/* 筛选 */}
      <div className="flex flex-wrap gap-2">
        {types.map(t => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
              filter === t ? 'bg-purple-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
            }`}
          >
            {t === 'all' ? '全部' : t} ({t === 'all' ? downloads.length : downloads.filter(d => d.type === t).length})
          </button>
        ))}
      </div>

      {/* 列表 */}
      {filtered.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
          <Download className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 font-medium text-lg">暂无下载记录</p>
          <p className="text-gray-400 text-sm mt-1">在工具中生成内容后，文件将自动记录在此处</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="divide-y divide-gray-100">
            {filtered.map((item, i) => {
              const Icon = FILE_ICONS[item.type] || FILE_ICONS.default
              return (
                <div key={i} className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors">
                  <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center text-purple-600">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{item.title || item.name || '未命名文件'}</p>
                    <p className="text-sm text-gray-500">
                      {item.type || 'file'} · {new Date(item.created_at || item.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors" title="下载">
                      <Download className="w-4 h-4 text-gray-500" />
                    </button>
                    <button onClick={() => handleDelete(item.id)} className="p-2 hover:bg-red-50 rounded-lg transition-colors" title="删除">
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
