import React, { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * 统一 Markdown 渲染器
 * 所有工具输出、AI 回复、文档内容统一使用此组件渲染
 * 样式由 index.css 中的 .md-content 统一控制
 */
export default function MarkdownRenderer({ content, className = '', emptyText = '暂无内容' }) {
  const plugins = useMemo(() => [remarkGfm], [])

  if (!content) {
    return <p className="text-sm text-ink-400 italic">{emptyText}</p>
  }

  return (
    <div className={`md-content ${className}`}>
      <ReactMarkdown remarkPlugins={plugins}>{content}</ReactMarkdown>
    </div>
  )
}
