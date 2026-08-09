import React, { useMemo, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// mermaid 按需加载：仅在渲染 mermaid 代码块时拉取（-500KB+ 主 bundle），
// 避免全局同步导入把 mermaid 打进所有引用 MarkdownRenderer 的页面 chunk。
let _mermaidPromise = null
function loadMermaid() {
  if (!_mermaidPromise) {
    _mermaidPromise = import('mermaid').then((mod) => {
      const mermaid = mod.default
      mermaid.initialize({
        startOnLoad: false,
        theme: 'neutral',
        securityLevel: 'strict', // strict：禁止图表内嵌 HTML，防止 LLM 生成内容 XSS
        fontFamily: 'inherit',
        flowchart: { useMaxWidth: true, htmlLabels: true },
        sequence: { useMaxWidth: true },
      })
      return mermaid
    })
  }
  return _mermaidPromise
}

/** 渲染 mermaid 图：源码 → SVG。渲染失败时回退显示源码。 */
function MermaidBlock({ code }) {
  const ref = useRef(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setError('')
    const render = async () => {
      try {
        const mermaid = await loadMermaid()
        const id = `mmd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        const { svg } = await mermaid.render(id, code)
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg
        }
      } catch (e) {
        if (!cancelled) setError(e?.message || String(e))
      }
    }
    render()
    return () => {
      cancelled = true
    }
  }, [code])

  if (error) {
    return (
      <div className="my-3 rounded-xl border border-amber-300 bg-amber-50 p-3">
        <p className="text-[11px] text-amber-700 mb-1">⚠ mermaid 渲染失败，已展示源码</p>
        <pre className="text-xs text-gray-700 whitespace-pre-wrap break-all">{code}</pre>
      </div>
    )
  }
  return (
    <div
      ref={ref}
      className="my-3 overflow-x-auto rounded-xl border border-gray-200 bg-white p-4 flex justify-center"
    />
  )
}

/**
 * 统一 Markdown 渲染器
 * 所有工具输出、AI 回复、文档内容统一使用此组件渲染
 * - mermaid 代码块（```mermaid）自动渲染为图表
 * - 样式由 index.css 中的 .md-content 统一控制
 */
export default function MarkdownRenderer({ content, className = '', emptyText = '暂无内容' }) {
  const plugins = useMemo(() => [remarkGfm], [])

  const components = useMemo(
    () => ({
      // mermaid 块：渲染为图表（跳过 pre 包裹）
      code({ node, inline, className, children, ...props }) {
        const match = /language-([\w-]+)/.exec(className || '')
        if (!inline && match && match[1] === 'mermaid') {
          return <MermaidBlock code={String(children).replace(/\n$/, '')} />
        }
        return (
          <code className={className} {...props}>
            {children}
          </code>
        )
      },
      pre({ node, children }) {
        // mermaid 块自带容器样式，跳过默认 pre 包裹
        if (React.isValidElement(children) && children.type === MermaidBlock) {
          return children
        }
        return <pre>{children}</pre>
      },
    }),
    []
  )

  if (!content) {
    return <p className="text-sm text-ink-400 italic">{emptyText}</p>
  }

  return (
    <div className={`md-content ${className}`}>
      <ReactMarkdown remarkPlugins={plugins} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
