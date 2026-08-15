import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Globe } from 'lucide-react'

/**
 * v22 小程序服务端预览页：展示后端生成的 HTML 预览（wxml→html + Mock 数据注入）。
 * 通过 /miniapp-preview/:filename 访问，iframe 内嵌后端生成的完整预览页。
 */
export default function MiniAppPreviewPage() {
  const { filename } = useParams()
  const navigate = useNavigate()
  const src = `/api/miniapp/preview/${filename}`

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <div className="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200">
        <button
          onClick={() => navigate(-1)}
          className="w-9 h-9 rounded-lg border border-gray-200 flex items-center justify-center hover:bg-gray-50 transition-colors"
        >
          <ArrowLeft className="w-4.5 h-4.5 text-gray-600" />
        </button>
        <Globe className="w-5 h-5 text-brand-500" />
        <div>
          <div className="font-medium text-sm text-gray-900">小程序在线预览</div>
          <div className="text-xs text-gray-400">服务端渲染 · 含 Mock 数据注入 · 页面 Tab 切换</div>
        </div>
      </div>
      <iframe
        src={src}
        title="小程序预览"
        className="flex-1 w-full border-0 bg-white"
        sandbox="allow-scripts allow-same-origin"
      />
    </div>
  )
}
