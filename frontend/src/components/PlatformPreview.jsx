import React, { useMemo } from 'react'
import {
  Heart,
  MessageCircle,
  Star,
  Share2,
  MoreHorizontal,
  Eye,
  ThumbsUp,
} from 'lucide-react'
import MarkdownRenderer from './MarkdownRenderer'

/* ══════════════════════════════════════════════════════════════
 * v18-D 平台排版预览
 * 把 LLM 生成的 Markdown 文案渲染为「仿真平台卡片」：
 * - xiaohongshu：小红书笔记卡片（用户条/封面/话题标签/互动栏）
 * - wechat：公众号文章排版（蓝V头部/居中标题/正文行高/阅读数据）
 * - 其他：通用阅读排版（标题居中 + 段落优雅行距）
 * 解析逻辑为纯函数（extractTitle/extractTags/splitBody/analyzeContent），
 * 便于单元测试。
 * ══════════════════════════════════════════════════════════════ */

/** 提取首个 Markdown 标题行（# / ## 开头） */
export function extractTitle(content) {
  if (!content) return ''
  const m = content.match(/^#{1,6}\s+(.+)$/m)
  return m ? m[1].trim() : ''
}

/** 提取话题标签 #xxx（排除 ## 标题标记、markdown 链接锚点、行内符号） */
export function extractTags(content) {
  if (!content) return []
  const tags = []
  // 前导仅限行首/空白/全角括号：半角 ( 用于 markdown 链接锚点（#url），不视为标签
  const re = /(^|[\s（])#([^\s#，。,.!！?？;；:：)）]+)/g
  let m
  while ((m = re.exec(content))) {
    const tag = m[2].trim()
    if (tag && !tags.includes(tag)) tags.push(tag)
  }
  return tags.slice(0, 8)
}

/** 行是否仅由话题标签组成（小红书结尾标签行） */
function isTagOnlyLine(line, tags) {
  const t = line.trim()
  if (!t || !t.startsWith('#')) return false
  const tokens = t.split(/\s+/).filter(Boolean)
  if (!tokens.length) return false
  return tokens.every((tok) => tags.includes(tok.replace(/^#/, '')))
}

/** 剥离首行标题与纯标签行，按空行分组为段落数组 */
export function splitBody(content) {
  const lines = (content || '').split('\n')
  const tags = extractTags(content)
  const cleaned = []
  lines.forEach((line, i) => {
    if (i === 0 && /^#{1,6}\s+/.test(line)) return // 首行标题
    if (isTagOnlyLine(line, tags)) return // 纯标签行
    cleaned.push(line)
  })
  const paragraphs = []
  let cur = []
  for (const line of cleaned) {
    if (!line.trim()) {
      if (cur.length) {
        paragraphs.push(cur.join('\n'))
        cur = []
      }
    } else {
      cur.push(line)
    }
  }
  if (cur.length) paragraphs.push(cur.join('\n'))
  return paragraphs
}

/** 内容结构统计（v18-D 结构化深度：字数/段落/小标题/标签） */
export function analyzeContent(content) {
  const text = (content || '').trim()
  if (!text) return { chars: 0, paragraphs: 0, headings: 0, tags: 0 }
  return {
    chars: text.replace(/\s/g, '').length,
    // 段落数以剥离标题/标签后的正文为准，与预览渲染保持一致
    paragraphs: splitBody(text).length,
    headings: (text.match(/^#{1,6}\s+/gm) || []).length,
    tags: extractTags(text).length,
  }
}

/* ── 迷你渲染工具 ─────────────────────────────────────────── */

/** **加粗** 行内渲染 */
function Inline({ text, strongClass = 'font-bold text-gray-900' }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong key={i} className={strongClass}>
        {p.slice(2, -2)}
      </strong>
    ) : (
      <React.Fragment key={i}>{p}</React.Fragment>
    )
  )
}

/** 稳定伪随机互动数：同一文案数字固定，切换视角才变化 */
function seedNum(content, salt, max) {
  let h = 0
  for (let i = 0; i < content.length; i++) h = (h * 31 + content.charCodeAt(i)) % 100000
  return (h + salt) % max
}

function fmtCount(n) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

/** 提取首个 emoji（封面装饰） */
function firstEmoji(text) {
  const m = text.match(/([\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]\u{FE0F}?)/u)
  return m ? m[0] : ''
}

/** 按行渲染正文（小标题/列表/普通段），wechat 小标题带蓝色竖条 */
function renderBodyLines(paragraphs, variant) {
  return paragraphs.map((para, pi) => (
    <div key={pi} className="space-y-1">
      {para.split('\n').map((line, li) => {
        const t = line.trim()
        if (!t) return null
        if (/^#{1,6}\s+/.test(t)) {
          const text = t.replace(/^#{1,6}\s+/, '')
          if (variant === 'wechat') {
            return (
              <h5 key={li} className="flex items-center gap-2 text-[15px] font-bold text-gray-900 my-2.5">
                <span className="w-1 h-4 bg-[#4F7CFD] rounded-full" />
                <Inline text={text} />
              </h5>
            )
          }
          return (
            <p key={li} className="text-[14px] font-bold text-gray-900 my-2">
              <Inline text={text} />
            </p>
          )
        }
        if (/^[-*]\s+/.test(t)) {
          return (
            <p key={li} className="flex gap-1.5 text-[14px] leading-7 text-gray-700">
              <span className="text-gray-300">•</span>
              <span>
                <Inline text={t.replace(/^[-*]\s+/, '')} />
              </span>
            </p>
          )
        }
        return (
          <p key={li} className="text-[14px] leading-7 text-gray-700">
            <Inline text={t} />
          </p>
        )
      })}
    </div>
  ))
}

/* ── 小红书笔记卡片 ───────────────────────────────────────── */

function XiaohongshuPreview({ content, title, tags, paragraphs }) {
  const emoji = firstEmoji(content)
  return (
    <div className="max-w-sm mx-auto bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* 顶部用户条 */}
      <div className="flex items-center gap-2 px-4 pt-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-pink-400 to-rose-500 flex items-center justify-center text-white text-xs font-bold">
          灵
        </div>
        <span className="text-[13px] font-medium text-gray-800">灵感笔记</span>
        <span className="ml-auto text-[11px] text-[#FF2442] border border-[#FF2442]/40 rounded-full px-2.5 py-0.5">
          关注
        </span>
        <MoreHorizontal className="w-4 h-4 text-gray-400" />
      </div>
      {/* 封面：渐变底 + emoji（无则标题字） */}
      <div className="mx-4 mt-3 h-28 rounded-xl bg-gradient-to-br from-pink-100 via-rose-50 to-amber-50 flex items-center justify-center overflow-hidden relative">
        {emoji ? (
          <span className="text-5xl">{emoji}</span>
        ) : (
          <span className="text-xl font-bold text-gray-300 tracking-widest">
            {title.slice(0, 6) || '✨'}
          </span>
        )}
        {tags.length > 0 && (
          <span className="absolute bottom-1.5 left-3 text-[10px] text-gray-400">
            #{tags.slice(0, 3).join(' #')}
          </span>
        )}
      </div>
      {/* 标题 */}
      {title && (
        <h4 className="px-4 mt-3 text-[15px] font-bold text-gray-900 leading-snug">{title}</h4>
      )}
      {/* 正文 */}
      <div className="px-4 mt-2 space-y-2">{renderBodyLines(paragraphs, 'xiaohongshu')}</div>
      {/* 话题标签 */}
      {tags.length > 0 && (
        <div className="px-4 pt-2.5 pb-3 flex flex-wrap gap-x-2.5 gap-y-1">
          {tags.map((t) => (
            <span key={t} className="text-[13px] text-[#FF2442]">
              #{t}
            </span>
          ))}
        </div>
      )}
      {/* 互动栏 */}
      <div className="flex items-center justify-between px-4 py-2.5 border-t border-gray-100">
        <div className="flex items-center gap-4 text-[11px] text-gray-500">
          <span className="flex items-center gap-1">
            <Heart className="w-3.5 h-3.5" />
            {fmtCount(seedNum(content, 7, 9000) + 8000)}
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle className="w-3.5 h-3.5" />
            {fmtCount(seedNum(content, 31, 700) + 100)}
          </span>
          <span className="flex items-center gap-1">
            <Star className="w-3.5 h-3.5" />
            {fmtCount(seedNum(content, 53, 6000) + 2000)}
          </span>
        </div>
        <Share2 className="w-4 h-4 text-gray-400" />
      </div>
    </div>
  )
}

/* ── 公众号文章排版 ───────────────────────────────────────── */

function WechatPreview({ content, title, paragraphs }) {
  const emoji = firstEmoji(content)
  const today = new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
  return (
    <div className="max-w-xl mx-auto bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* 公众号头部 */}
      <div className="flex items-center gap-2.5 px-5 pt-4">
        <div className="w-9 h-9 rounded-lg bg-[#07C160] flex items-center justify-center text-white text-[11px] font-bold">
          创
        </div>
        <div>
          <div className="text-[13px] font-semibold text-gray-900 flex items-center gap-1">
            灵感创作
            <span className="w-3.5 h-3.5 rounded-sm bg-[#4F7CFD] text-white text-[8px] flex items-center justify-center font-bold">
              V
            </span>
          </div>
          <div className="text-[10px] text-gray-400">AI 创作灵感</div>
        </div>
        <span className="ml-auto text-[11px] px-3 py-1 rounded-full border border-gray-200 text-gray-600">
          关注
        </span>
      </div>
      {/* 封面 */}
      <div className="mx-5 mt-3 h-36 rounded-xl bg-gradient-to-br from-indigo-50 via-blue-50 to-cyan-50 flex items-center justify-center overflow-hidden relative">
        {emoji ? (
          <span className="text-5xl">{emoji}</span>
        ) : (
          <span className="text-2xl font-bold text-gray-300">{title.slice(0, 8) || '✍️'}</span>
        )}
      </div>
      {/* 居中大标题 */}
      {title && (
        <h2 className="px-6 mt-4 text-xl font-bold text-gray-900 text-center leading-snug">
          {title}
        </h2>
      )}
      <div className="flex items-center justify-center gap-2 mt-2 text-[11px] text-gray-400">
        <span>AI 创作助手</span>
        <span>·</span>
        <span>{today}</span>
      </div>
      {/* 正文 */}
      <div className="px-6 mt-3 pb-6">{renderBodyLines(paragraphs, 'wechat')}</div>
      {/* 底部数据 */}
      <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-center gap-5 text-[11px] text-gray-400">
        <span className="flex items-center gap-1">
          <Eye className="w-3.5 h-3.5" />
          {fmtCount(seedNum(content, 11, 90000) + 10000)}
        </span>
        <span className="flex items-center gap-1">
          <ThumbsUp className="w-3.5 h-3.5" />
          {fmtCount(seedNum(content, 17, 9000) + 1000)}
        </span>
        <span>在看 {fmtCount(seedNum(content, 23, 3000) + 200)}</span>
      </div>
      <div className="px-6 pb-5">
        <div className="rounded-full bg-[#F7F7F7] text-center text-[11px] text-gray-500 py-1.5">
          长按识别二维码关注公众号
        </div>
      </div>
    </div>
  )
}

/* ── 通用阅读排版（无平台限定） ───────────────────────────── */

function GenericPreview({ title, paragraphs }) {
  return (
    <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-gray-200 shadow-sm px-6 py-6">
      {title && (
        <h2 className="text-xl font-bold text-gray-900 text-center leading-snug mb-1">{title}</h2>
      )}
      <div className="mt-4 space-y-2">{renderBodyLines(paragraphs, 'generic')}</div>
    </div>
  )
}

/* ── 入口 ─────────────────────────────────────────────────── */

function parseContent(content, fallbackTitle) {
  return {
    content, // 供预览卡片的 emoji 封面与稳定互动数字使用
    title: extractTitle(content) || fallbackTitle || '',
    tags: extractTags(content),
    paragraphs: splitBody(content),
  }
}

export default function PlatformPreview({ content, platform = '', title = '' }) {
  const parsed = useMemo(() => parseContent(content, title), [content, title])

  if (!content) return null
  if (platform === 'xiaohongshu') return <XiaohongshuPreview {...parsed} />
  if (platform === 'wechat') return <WechatPreview {...parsed} />
  return <GenericPreview {...parsed} />
}

/** 原文模式：直接 Markdown 渲染（供页面切换） */
export function RawContent({ content }) {
  return <MarkdownRenderer content={content} />
}
