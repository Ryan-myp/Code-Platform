import React from 'react'
import { Wand2 } from 'lucide-react'

/**
 * 通用「随机提示词」按钮：从预设数组中随机取一条填入输入框。
 * 新手灵感入口，与智能补充（EnhancePromptButton）搭配使用。
 *
 * props:
 * - prompts: 预设数组（字符串或对象，onPick 收到整个元素）
 * - onPick(item): 把随机取到的元素填入输入框
 * - className: 按钮样式（默认幽灵小字链接样式）
 */
export default function RandomPromptButton({ prompts, onPick, className = '' }) {
  const handleRandom = () => {
    if (!prompts || prompts.length === 0) return
    onPick(prompts[Math.floor(Math.random() * prompts.length)])
  }

  return (
    <button onClick={handleRandom} className={`inline-flex items-center gap-1 ${className}`}>
      <Wand2 className="w-3 h-3" />
      随机提示词
    </button>
  )
}
