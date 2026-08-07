import React, { useMemo, useState, useCallback } from 'react'
import {
  Copy,
  CheckCircle2,
  Folder,
  FolderOpen,
  FileCode2,
  ChevronRight,
  ChevronDown,
  FileJson,
  FileText,
  Braces,
  FileType,
  File,
} from 'lucide-react'
import { copyToClipboard } from '../lib/format'

// 与后端 _CODE_FILE_HEADER_RE 对齐：块头首行是合法文件路径
const FILE_PATH_RE =
  /^(?:#|\/\/|\/\*|--)?\s*([\w./-]+\.(?:py|js|ts|jsx|tsx|go|java|json|html|css|sh|yml|yaml|sql|md|txt))\s*\*?\/?$/
const CODE_BLOCK_RE = /```[a-zA-Z0-9]*[^\S\n]*([^\n]*)\n([\s\S]*?)```/g

/** 解析产物中的多文件代码块（```lang path ... ```）→ {文件路径: 内容} */
export function parseCodeFiles(content) {
  const files = {}
  const text = content || ''
  CODE_BLOCK_RE.lastIndex = 0
  let m
  while ((m = CODE_BLOCK_RE.exec(text))) {
    const header = (m[1] || '').trim()
    if (header && FILE_PATH_RE.test(header)) {
      files[header] = m[2].replace(/\n$/, '')
    }
  }
  return files
}

const EXT_META = {
  py: { color: 'text-blue-600', bg: 'bg-blue-50', icon: FileCode2 },
  js: { color: 'text-yellow-600', bg: 'bg-yellow-50', icon: FileCode2 },
  jsx: { color: 'text-cyan-600', bg: 'bg-cyan-50', icon: FileCode2 },
  ts: { color: 'text-sky-600', bg: 'bg-sky-50', icon: FileCode2 },
  tsx: { color: 'text-cyan-600', bg: 'bg-cyan-50', icon: FileCode2 },
  go: { color: 'text-cyan-600', bg: 'bg-cyan-50', icon: FileCode2 },
  java: { color: 'text-red-600', bg: 'bg-red-50', icon: FileCode2 },
  json: { color: 'text-emerald-600', bg: 'bg-emerald-50', icon: FileJson },
  html: { color: 'text-orange-600', bg: 'bg-orange-50', icon: FileType },
  css: { color: 'text-pink-600', bg: 'bg-pink-50', icon: FileType },
  md: { color: 'text-gray-600', bg: 'bg-gray-100', icon: FileText },
  sql: { color: 'text-violet-600', bg: 'bg-violet-50', icon: Braces },
  sh: { color: 'text-lime-600', bg: 'bg-lime-50', icon: File },
  yml: { color: 'text-teal-600', bg: 'bg-teal-50', icon: File },
  yaml: { color: 'text-teal-600', bg: 'bg-teal-50', icon: File },
  txt: { color: 'text-gray-500', bg: 'bg-gray-100', icon: FileText },
}

function extOf(name) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i + 1).toLowerCase() : ''
}

function buildTree(files) {
  const root = { name: '', type: 'dir', children: {} }
  for (const path of Object.keys(files).sort()) {
    const parts = path.split('/')
    let node = root
    for (let i = 0; i < parts.length - 1; i += 1) {
      if (!node.children[parts[i]])
        node.children[parts[i]] = { name: parts[i], type: 'dir', children: {} }
      node = node.children[parts[i]]
    }
    const name = parts[parts.length - 1]
    node.children[name] = { name, type: 'file', path, content: files[path] }
  }
  return root
}

function firstFile(node) {
  if (node.type === 'file') return node
  for (const child of Object.values(node.children || {})) {
    const f = firstFile(child)
    if (f) return f
  }
  return null
}

/** 按内容特征推断单文件工程的语言/文件名（与后端退化推断对齐） */
export function inferFileName(content) {
  const text = content || ''
  if (/package main/.test(text) && /func main\(/.test(text)) return 'main.go'
  if (/module\.exports|require\s*\(|express\s*\(\)|app\.listen\s*\(/.test(text)) return 'server.js'
  return 'main.py'
}

/** 单文件退化视图：整个产物视为一个文件 */
function SingleFileView({ content, title }) {
  const [copyOk, setCopyOk] = useState(false)
  const fileName = inferFileName(content)
  const meta = EXT_META[extOf(fileName)] || {
    color: 'text-gray-600',
    bg: 'bg-gray-100',
    icon: FileCode2,
  }
  const Icon = meta.icon
  const copy = async () => {
    await copyToClipboard(content)
    setCopyOk(true)
    setTimeout(() => setCopyOk(false), 1500)
  }
  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-700">
          <span className={`p-1 rounded ${meta.bg} ${meta.color}`}>
            <Icon className="w-3.5 h-3.5" />
          </span>
          {fileName}
          <span className="text-gray-400 font-normal">· {content.length} 字符</span>
        </span>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
        >
          {copyOk ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
          ) : (
            <Copy className="w-3.5 h-3.5" />
          )}
          {copyOk ? '已复制' : '复制'}
        </button>
      </div>
      <pre className="bg-gray-900 text-gray-100 p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[55vh] whitespace-pre-wrap">
        {content}
      </pre>
    </div>
  )
}

function TreeNode({ node, depth, activePath, collapsed, onSelect, onToggle }) {
  const pad = { paddingLeft: `${depth * 14 + 8}px` }
  if (node.type === 'dir') {
    const isOpen = !collapsed.has(node.name)
    return (
      <>
        <button
          onClick={() => onToggle(node.name)}
          className="w-full flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors"
          style={pad}
        >
          {isOpen ? (
            <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
          )}
          {isOpen ? (
            <FolderOpen className="w-3.5 h-3.5 text-amber-500" />
          ) : (
            <Folder className="w-3.5 h-3.5 text-amber-500" />
          )}
          <span className="font-medium">{node.name}</span>
        </button>
        {isOpen && (
          <div>
            {Object.values(node.children).map((child) => (
              <TreeNode
                key={child.name}
                node={child}
                depth={depth + 1}
                activePath={activePath}
                collapsed={collapsed}
                onSelect={onSelect}
                onToggle={onToggle}
              />
            ))}
          </div>
        )}
      </>
    )
  }
  const meta = EXT_META[extOf(node.name)] || {
    color: 'text-gray-600',
    bg: 'bg-gray-100',
    icon: FileCode2,
  }
  const Icon = meta.icon
  const active = activePath === node.path
  return (
    <button
      onClick={() => onSelect(node)}
      className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs transition-colors ${pad} ${
        active ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-gray-600 hover:bg-gray-100'
      }`}
    >
      <span className={`p-0.5 rounded ${meta.bg} ${meta.color}`}>
        <Icon className="w-3 h-3" />
      </span>
      <span className="truncate flex-1 text-left">{node.name}</span>
      <span className="text-[10px] text-gray-400">{node.content.split('\n').length} 行</span>
    </button>
  )
}

/**
 * 代码产物树形展示：解析多文件代码块 → 目录树 + 文件内容查看。
 * 无法解析出多文件时退化为单文件视图（整个产物视为一个文件）。
 */
export default function CodeTreeView({ content, title = '工程代码' }) {
  const files = useMemo(() => parseCodeFiles(content), [content])
  const tree = useMemo(() => (Object.keys(files).length ? buildTree(files) : null), [files])
  const [selected, setSelected] = useState(null)
  const [collapsed, setCollapsed] = useState(() => new Set())
  const [copyOk, setCopyOk] = useState(false)

  const active = selected || (tree ? firstFile(tree) : null)
  const fileCount = Object.keys(files).length

  const onToggle = useCallback((name) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }, [])

  const onSelect = useCallback((node) => {
    setSelected(node)
    setCopyOk(false)
  }, [])

  if (!tree) {
    return <SingleFileView content={content} title={title} />
  }

  const copyActive = async () => {
    if (!active) return
    await copyToClipboard(active.content)
    setCopyOk(true)
    setTimeout(() => setCopyOk(false), 1500)
  }
  const meta = EXT_META[extOf(active.path)] || {
    color: 'text-gray-600',
    bg: 'bg-gray-100',
    icon: FileCode2,
  }
  const Icon = meta.icon

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200">
        <span className="text-xs font-medium text-gray-700">{title}</span>
        <span className="text-[11px] text-gray-400">{fileCount} 个文件</span>
      </div>
      <div className="flex max-h-[55vh]">
        {/* 目录树 */}
        <div className="w-60 shrink-0 border-r border-gray-200 overflow-y-auto py-1.5 bg-white">
          {Object.values(tree.children).map((child) => (
            <TreeNode
              key={child.name}
              node={child}
              depth={0}
              activePath={active.path}
              collapsed={collapsed}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))}
        </div>
        {/* 文件内容 */}
        <div className="flex-1 min-w-0 bg-gray-900">
          <div className="flex items-center justify-between px-3 py-2 bg-gray-800/80 border-b border-gray-700">
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-200">
              <span className={`p-0.5 rounded ${meta.bg} ${meta.color}`}>
                <Icon className="w-3.5 h-3.5" />
              </span>
              {active.path}
              <span className="text-gray-500 font-normal">
                · {active.content.split('\n').length} 行 · {active.content.length} 字符
              </span>
            </span>
            <button
              onClick={copyActive}
              className="inline-flex items-center gap-1 px-2 py-1 text-[11px] text-indigo-300 hover:bg-indigo-500/20 rounded-lg transition-colors"
            >
              {copyOk ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
              {copyOk ? '已复制' : '复制文件'}
            </button>
          </div>
          <pre className="p-4 text-xs font-mono leading-relaxed overflow-auto max-h-[48vh] whitespace-pre-wrap text-gray-100">
            {active.content}
          </pre>
        </div>
      </div>
    </div>
  )
}
