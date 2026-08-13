import React, { useEffect, useState } from 'react'
import { Star, Sparkles } from 'lucide-react'
import { api } from '../lib/api'

/**
 * 图片质量徽章（商用专业基线）
 *
 * 懒加载调用 /api/image-factory/images/{filename}/quality，
 * 展示 0-100 评分 + 等级（A/B/C），hover 显示优化建议。
 * 结果缓存（模块级 Map），避免重复请求。
 */
const _cache = new Map()

export default function ImageQualityBadge({ filename, className = '' }) {
  const [quality, setQuality] = useState(_cache.get(filename) || null)

  useEffect(() => {
    if (!filename || _cache.has(filename)) return
    api
      .get(`/api/image-factory/images/${filename}/quality`, { timeout: 10000 })
      .then((res) => {
        const q = res.data || {}
        _cache.set(filename, q)
        setQuality(q)
      })
      .catch(() => {}) // 静默失败，不阻塞列表
  }, [filename])

  if (!quality || quality.score == null) return null

  const { score, grade, suggestions = [] } = quality
  const color =
    score >= 85
      ? 'bg-emerald-500/90'
      : score >= 65
        ? 'bg-amber-500/90'
        : 'bg-red-500/90'

  return (
    <div className={`relative group ${className}`}>
      <span
        className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[10px] font-medium text-white ${color}`}
        title={`美观度 ${score}/100（${grade} 级）`}
      >
        <Star className="w-2.5 h-2.5 fill-white" />
        {score}
        {grade && <span className="opacity-80">{grade}</span>}
      </span>
      {suggestions.length > 0 && (
        <div className="absolute z-20 bottom-full left-0 mb-1 hidden group-hover:block w-48 bg-gray-900 text-white text-[10px] rounded-lg p-2 shadow-lg">
          {suggestions.slice(0, 3).map((s, i) => (
            <p key={i} className="leading-relaxed">• {s}</p>
          ))}
        </div>
      )}
    </div>
  )
}
