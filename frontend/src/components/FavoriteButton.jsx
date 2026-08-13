import React, { useState } from 'react'
import { Star, StarOff, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'

/**
 * 收藏按钮（专业基线：生成结果可收藏到素材库，跨会话留存）
 *
 * @param {string} favType  收藏类型：record/template/gallery/tool
 * @param {string} targetId 收藏目标 ID（如生成记录 id / 图片文件名）
 * @param {string} label    展示标签（如提示词/标题，可空）
 * @param {string} [className] 额外样式
 */
export default function FavoriteButton({ favType = 'record', targetId, label = '', className = '' }) {
  const toast = useToast()
  const [saving, setSaving] = useState(false)
  const [faved, setFaved] = useState(false)

  const toggle = async (e) => {
    e.stopPropagation()
    if (!targetId) {
      toast.info('该内容暂不支持收藏')
      return
    }
    setSaving(true)
    try {
      if (faved) {
        // 先查 id 再删（轻量：直接调列表接口匹配）
        const res = await api.get('/api/favorites', { params: { fav_type: favType, limit: 200 } })
        const found = (res.data || []).find((f) => f.target_id === targetId)
        if (found) await api.delete(`/api/favorites/${found.id}`)
        setFaved(false)
        toast.success('已取消收藏')
      } else {
        await api.post('/api/favorites', { fav_type: favType, target_id: targetId, label: label || undefined })
        setFaved(true)
        toast.success('已收藏到素材库')
      }
    } catch (err) {
      // 已收藏/网络错误：静默降级（不影响主流程）
      if (!faved) toast.error(err.response?.data?.detail || '收藏失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <button
      onClick={toggle}
      disabled={saving}
      className={`inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs transition-colors ${
        faved
          ? 'text-amber-500 bg-amber-50 hover:bg-amber-100'
          : 'text-gray-400 hover:text-amber-500 hover:bg-amber-50'
      } ${className}`}
      title={faved ? '取消收藏' : '收藏到素材库'}
    >
      {saving ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : faved ? (
        <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
      ) : (
        <Star className="w-3.5 h-3.5" />
      )}
    </button>
  )
}
