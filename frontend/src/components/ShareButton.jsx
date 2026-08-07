import React, { useState } from 'react'
import { Check, Copy, ExternalLink, Loader2, QrCode, Share2, X } from 'lucide-react'
import api from '../lib/api'
import { useToast } from '../lib/toast'

/**
 * 分享按钮：将内容发布为公开分享链接，弹窗展示链接 + 二维码。
 */
export default function ShareButton({
  content,
  title = '',
  contentType = 'text',
  className = '',
  disabled = false,
}) {
  const toast = useToast()
  const [sharing, setSharing] = useState(false)
  const [shared, setShared] = useState(false)
  const [shareUrl, setShareUrl] = useState('')

  const handleShare = async () => {
    if (!content?.trim()) {
      toast.warning('暂无可分享的内容')
      return
    }
    setSharing(true)
    try {
      const res = await api.post('/api/shares', {
        content_type: contentType,
        title: title || '小团智能平台生成结果',
        content,
      })
      const shareCode = res.data.share_code
      const url = `${window.location.origin}/share/${shareCode}`
      setShareUrl(url)
      toast.success('分享链接已生成')
    } catch (err) {
      toast.error(err.message || '分享失败')
    } finally {
      setSharing(false)
    }
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      setShared(true)
      toast.success('分享链接已复制，快去发给朋友吧！')
      setTimeout(() => setShared(false), 3000)
    } catch {
      toast.error('复制失败，请手动复制')
    }
  }

  const qrSrc = shareUrl
    ? `https://api.qrserver.com/v1/create-qr-code/?size=240x240&margin=8&data=${encodeURIComponent(shareUrl)}`
    : ''

  return (
    <>
      <button
        onClick={handleShare}
        disabled={sharing || disabled}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg transition-colors disabled:opacity-50 ${
          shared
            ? 'bg-emerald-50 text-emerald-600'
            : 'text-gray-500 hover:text-brand-600 hover:bg-gray-100'
        } ${className}`}
        title="生成分享链接"
      >
        {sharing ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Share2 className="w-3.5 h-3.5" />
        )}
        分享
      </button>

      {shareUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setShareUrl('')}
          />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 text-center">
            <button
              onClick={() => setShareUrl('')}
              className="absolute top-3 right-3 p-1.5 text-ink-400 hover:text-ink-600 hover:bg-ink-50 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="w-12 h-12 mx-auto rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-soft mb-3">
              <QrCode className="w-6 h-6 text-white" />
            </div>
            <h3 className="font-semibold text-ink-900">分享已生成</h3>
            <p className="text-xs text-ink-400 mt-1">扫码或复制链接，发给好友即可查看</p>

            <div className="mt-4 mx-auto w-52 h-52 bg-white border border-ink-100 rounded-2xl p-3 shadow-soft">
              <img
                src={qrSrc}
                alt="分享二维码"
                className="w-full h-full object-contain"
                onError={(e) => {
                  e.target.style.display = 'none'
                  e.target.nextElementSibling?.classList.remove('hidden')
                }}
              />
              <p className="hidden text-xs text-ink-300 pt-10">二维码加载失败，请使用链接分享</p>
            </div>

            <div className="mt-4 flex items-center gap-2 bg-ink-50 rounded-xl px-3 py-2.5">
              <span className="text-xs text-ink-500 truncate flex-1 text-left">{shareUrl}</span>
              <button
                onClick={copyLink}
                className="flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 transition-colors flex-shrink-0"
              >
                {shared ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                {shared ? '已复制' : '复制'}
              </button>
            </div>

            <a
              href={shareUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-800 font-medium"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              打开分享页预览
            </a>
          </div>
        </div>
      )}
    </>
  )
}
