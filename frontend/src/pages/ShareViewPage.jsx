import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Calendar, Eye, Loader2, Sparkles, Home } from 'lucide-react'
import api from '../lib/api'
import MarkdownRenderer from '../components/MarkdownRenderer'

/**
 * 公开分享查看页（无需登录）。
 * 路由：/share/:shareCode
 */
export default function ShareViewPage() {
  const { shareCode } = useParams()
  const [share, setShare] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get(`/api/shares/${shareCode}`)
        setShare(res.data)
      } catch (err) {
        setError(err.message || '分享不存在或已失效')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [shareCode])

  // 同步页面标题与 og meta（浏览器端兑底；爬虫直访由后端 /share/{code} SEO HTML 负责）
  useEffect(() => {
    const plainText = (content) =>
      (content || '')
        // eslint-disable-next-line no-useless-escape -- `[` 在 class 内去掉转义会导致 `]` 提前结束字符类
        .replace(/[#*`>\[\]()!|~-]/g, '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120)

    const setMeta = (attr, key, value) => {
      let el = document.head.querySelector(`meta[${attr}="${key}"]`)
      if (!el) {
        el = document.createElement('meta')
        el.setAttribute(attr, key)
        document.head.appendChild(el)
      }
      el.setAttribute('content', value)
    }

    if (share) {
      const desc = plainText(share.content) || share.title
      document.title = `${share.title} - 小团智能平台`
      setMeta('name', 'description', desc)
      setMeta('property', 'og:title', share.title)
      setMeta('property', 'og:description', desc)
      setMeta('property', 'og:type', 'article')
      setMeta('property', 'og:site_name', '小团智能平台')
    } else if (error) {
      document.title = '分享不存在 - 小团智能平台'
    }
  }, [share, error])

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-indigo-50 to-blue-50">
      {/* 顶部品牌栏 */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-white/60 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-glow">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <div>
              <h1 className="font-semibold text-gray-900 leading-tight">小团智能平台</h1>
              <p className="text-xs text-gray-400">AI 赋能各行各业 · 分享内容</p>
            </div>
          </div>
          <Link
            to="/"
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-purple-600 hover:bg-purple-50 rounded-xl transition-colors"
          >
            <Home className="w-4 h-4" />
            进入平台
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-24 text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin mr-2" />
            加载分享内容…
          </div>
        ) : error ? (
          <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-12 text-center border border-white/60">
            <div className="w-16 h-16 bg-red-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Sparkles className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">内容不存在或已失效</h2>
            <p className="text-sm text-gray-500 mb-6">{error}</p>
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl font-medium shadow-lg shadow-purple-500/30 hover:from-purple-700 hover:to-indigo-700 transition-all"
            >
              去小团智能平台看看
            </Link>
          </div>
        ) : (
          <div className="bg-white/90 backdrop-blur-xl rounded-3xl shadow-2xl overflow-hidden border border-white/60">
            {/* 内容头部 */}
            <div className="px-8 pt-8 pb-6 border-b border-gray-100">
              <h2 className="text-2xl font-bold text-gray-900 leading-snug">
                {share.title || '分享内容'}
              </h2>
              <div className="flex items-center gap-4 mt-3 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  {share.created_at?.slice(0, 10)}
                </span>
                <span className="flex items-center gap-1">
                  <Eye className="w-3.5 h-3.5" />
                  {share.views} 次浏览
                </span>
                <span className="px-2 py-0.5 bg-purple-50 text-purple-600 rounded-full">
                  {share.content_type}
                </span>
              </div>
            </div>

            {/* 内容主体 */}
            <div className="px-8 py-6">
              <MarkdownRenderer content={share.content} emptyText="（空内容）" />
            </div>

            {/* 底部 CTA */}
            <div className="px-8 py-6 bg-gradient-to-r from-purple-50 to-indigo-50 border-t border-purple-100/60">
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <p className="text-sm font-semibold text-gray-800">这份内容是用 AI 生成的？</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    小团智能平台 · 30+ 效率工具免费体验
                  </p>
                  <p className="text-xs text-gray-400 mt-1.5">
                    分享被 10 位好友访问，分享者可得 5 次生成额度；你注册还可领免费额度
                  </p>
                </div>
                <Link
                  to={`/login?share=${shareCode}`}
                  className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl font-medium shadow-lg shadow-purple-500/30 hover:from-purple-700 hover:to-indigo-700 transition-all"
                >
                  <Sparkles className="w-4 h-4" />
                  免费体验
                </Link>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
