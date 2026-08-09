import React, { useState } from 'react'
import { Wand2, Loader2 } from 'lucide-react'
import api from '../lib/api'
import { useToast } from '../lib/toast'

/**
 * 通用「AI 智能补充」按钮：调用 /api/tools/enhance-prompt 润色提示词并填入输入框。
 * 免费辅助能力（不扣减生成额度），各生成页复用。
 *
 * props:
 * - text: 当前输入框内容
 * - onEnhance(text): 把润色结果填入输入框
 * - style: 润色场景（image/copywriting/music/video/meme/mindmap/ppt/general）
 * - className: 按钮样式（默认幽灵小字链接样式）
 */
export default function EnhancePromptButton({ text, onEnhance, style = 'general', className = '' }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)

  const handleEnhance = async () => {
    const trimmed = (text || '').trim()
    if (!trimmed) {
      toast.error('请先输入内容，再使用智能补充')
      return
    }
    if (busy) return
    setBusy(true)
    try {
      const res = await api.post('/api/tools/enhance-prompt', { text: trimmed, style })
      const enhanced = res.data?.enhanced
      if (enhanced) {
        onEnhance(enhanced)
        toast.success('已智能补充，可直接生成')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || '智能补充失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      onClick={handleEnhance}
      disabled={busy}
      className={`inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
      {busy ? '补充中…' : '智能补充'}
    </button>
  )
}
