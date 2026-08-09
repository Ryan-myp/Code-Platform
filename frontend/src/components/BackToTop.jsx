import React, { useEffect, useState } from 'react'
import { ArrowUp } from 'lucide-react'

/**
 * 全局「回到顶部」浮动按钮。
 * 滚动超过阈值后出现，点击平滑回到顶部；路由切换时自动回到顶部（页面级）。
 */
export default function BackToTop({ threshold = 400 }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > threshold)
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])

  // 路由切换时回到顶部，避免新页面停留在旧滚动位置
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [])

  if (!visible) return null

  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      title="回到顶部"
      aria-label="回到顶部"
      className="fixed left-4 bottom-20 md:left-6 md:bottom-6 z-40 w-10 h-10 rounded-full bg-white/90 backdrop-blur border border-gray-200 shadow-lg text-gray-500 hover:text-purple-600 hover:border-purple-200 hover:shadow-purple-100 transition-all flex items-center justify-center"
    >
      <ArrowUp className="w-4 h-4" />
    </button>
  )
}
