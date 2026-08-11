import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  FileText,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  Plus,
  Upload,
  Download,
  Trash2,
  RefreshCw,
  Pencil,
  X,
  Check,
  FileCode2,
  Image as ImageIcon,
  Loader2,
  Sparkles,
  Save,
  FolderPlus,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { Modal, Button, ConfirmDialog, Empty } from './ui'
import MarkdownRenderer from './MarkdownRenderer'

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp', 'avif'])

const formatSize = (bytes) => {
  if (bytes == null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

/** 解析 SKILL.md frontmatter，返回 { meta, body } */
function parseFrontmatter(text) {
  const m = /^---\s*\n([\s\S]*?)\n---\s*\n?/.exec(text || '')
  if (!m) return null
  const meta = {}
  for (const line of m[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx > 0)
      meta[line.slice(0, idx).trim()] = line
        .slice(idx + 1)
        .trim()
        .replace(/^['"]|['"]$/g, '')
  }
  return { meta, body: text.slice(m[0].length) }
}

// ─── 目录树节点 ──────────────────────────────────────────────
function TreeNode({ node, depth = 0, expanded, onToggle, selectedPath, onSelect, rootName }) {
  const isDir = node.type === 'dir'
  const isExpanded = isDir && expanded.has(node.path)
  const isSelected = selectedPath === node.path
  const displayName = node.path === '' ? rootName : node.name

  if (isDir) {
    return (
      <div>
        <button
          onClick={() => {
            onToggle(node.path)
            onSelect(node)
          }}
          className={`w-full flex items-center gap-1.5 py-1.5 pr-2 rounded-lg text-left text-sm transition-colors ${
            isSelected ? 'bg-violet-50 text-violet-700' : 'text-gray-700 hover:bg-gray-100'
          }`}
          style={{ paddingLeft: 8 + depth * 14 }}
        >
          {isExpanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
          )}
          {isExpanded ? (
            <FolderOpen className="w-4 h-4 text-amber-500 flex-shrink-0" />
          ) : (
            <Folder className="w-4 h-4 text-amber-500 flex-shrink-0" />
          )}
          <span className="truncate flex-1 font-medium">{displayName}</span>
          {node.file_count > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 flex-shrink-0">
              {node.file_count}
            </span>
          )}
        </button>
        {isExpanded &&
          (node.children || []).map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              selectedPath={selectedPath}
              onSelect={onSelect}
              rootName={rootName}
            />
          ))}
      </div>
    )
  }

  return (
    <button
      onClick={() => onSelect(node)}
      className={`w-full flex items-center gap-1.5 py-1.5 pr-2 rounded-lg text-left text-sm transition-colors ${
        isSelected ? 'bg-violet-50 text-violet-700' : 'text-gray-600 hover:bg-gray-100'
      }`}
      style={{ paddingLeft: 8 + depth * 14 }}
    >
      {node.name === 'SKILL.md' ? (
        <FileText className="w-4 h-4 text-violet-500 flex-shrink-0" />
      ) : IMAGE_EXTS.has(node.ext) ? (
        <ImageIcon className="w-4 h-4 text-emerald-500 flex-shrink-0" />
      ) : (
        <FileCode2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
      )}
      <span className="truncate flex-1 font-mono text-xs">{node.name}</span>
    </button>
  )
}

// ─── 文件浏览器弹窗 ──────────────────────────────────────────
export default function SkillExplorer({ open, onClose, skill, onEdit, onDelete, onChanged }) {
  const toast = useRef(useToast()).current
  const [tree, setTree] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(new Set())
  const [selected, setSelected] = useState(null)
  const [content, setContent] = useState(null)
  const [contentLoading, setContentLoading] = useState(false)
  const [imageUrl, setImageUrl] = useState(null)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(null)
  const [createName, setCreateName] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  const loadTree = useCallback(async () => {
    if (!open || !skill?.id) return
    setLoading(true)
    try {
      const res = await api.get(`/api/skills/${skill.id}/files/tree`)
      const t = res.data
      setTree(t)
      const dirs = new Set()
      const collect = (node) => {
        if (node.type === 'dir') {
          dirs.add(node.path)
          ;(node.children || []).forEach(collect)
        }
      }
      collect(t)
      setExpanded(dirs)
      return t
    } catch (e) {
      toast.error(`加载文件树失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }, [open, skill, toast])

  useEffect(() => {
    if (open) {
      setSelected(null)
      setContent(null)
      setImageUrl(null)
      setEditing(false)
      setCreating(null)
      loadTree()
    }
  }, [open, loadTree])

  // 目标目录：当前选中目录，或选中文件所在目录，或根目录
  const targetDir = useMemo(() => {
    if (!selected) return ''
    if (selected.type === 'dir') return selected.path
    return selected.path.includes('/') ? selected.path.slice(0, selected.path.lastIndexOf('/')) : ''
  }, [selected])

  const selectNode = useCallback(
    async (node) => {
      setSelected(node)
      setEditing(false)
      setContent(null)
      setImageUrl(null)
      if (node.type !== 'file') return
      setContentLoading(true)
      try {
        if (IMAGE_EXTS.has(node.ext)) {
          const res = await api.get(
            `/api/skills/${skill.id}/file/raw?path=${encodeURIComponent(node.path)}`,
            { responseType: 'blob' }
          )
          setImageUrl(URL.createObjectURL(res.data))
        } else {
          const res = await api.get(
            `/api/skills/${skill.id}/file?path=${encodeURIComponent(node.path)}`
          )
          setContent(res.data)
        }
      } catch (e) {
        toast.error(`读取文件失败：${e.message}`)
      } finally {
        setContentLoading(false)
      }
    },
    [skill, toast]
  )

  const toggleDir = (path) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const startEdit = () => {
    if (!content?.is_text) return
    setEditText(content.content || '')
    setEditing(true)
  }

  const handleSave = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await api.put(`/api/skills/${skill.id}/file?path=${encodeURIComponent(selected.path)}`, {
        content: editText,
      })
      toast.success('文件已保存')
      setEditing(false)
      await selectNode(selected)
      if (selected.name === 'SKILL.md') onChanged?.()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleCreate = async () => {
    const name = (createName || '').trim().replace(/^\/+/, '')
    if (!name) {
      toast.error('请输入名称')
      return
    }
    if (name.includes('/') || name.includes('\\') || name === '.' || name === '..') {
      toast.error('名称不能包含路径分隔符')
      return
    }
    const rel = (targetDir ? `${targetDir}/` : '') + name
    // 同名文件已存在时拒绝（目录幂等创建，文件不可覆盖）
    if (creating === 'file' && tree) {
      const findDup = (node) => {
        if (node.type === 'file' && node.path === rel) return true
        return (node.children || []).some(findDup)
      }
      if (findDup(tree)) {
        toast.error(`「${name}」已存在`)
        return
      }
    }
    setSaving(true)
    try {
      if (creating === 'folder') {
        await api.post(`/api/skills/${skill.id}/folder?path=${encodeURIComponent(rel)}`)
        toast.success(`已创建目录「${name}」`)
      } else {
        const defaultContent =
          name === 'SKILL.md'
            ? `---\nname: ${skill.name || ''}\ndescription: ${skill.description || ''}\n---\n\n（在此编写技能指令）`
            : ''
        await api.put(`/api/skills/${skill.id}/file?path=${encodeURIComponent(rel)}`, {
          content: defaultContent,
        })
        toast.success(`已创建文件「${name}」`)
      }
      setCreating(null)
      setCreateName('')
      await loadTree()
      onChanged?.()
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return false
    try {
      await api.delete(`/api/skills/${skill.id}/file?path=${encodeURIComponent(deleteTarget.path)}`)
      toast.success(`已删除「${deleteTarget.name}」`)
      if (selected?.path === deleteTarget.path) {
        setSelected(null)
        setContent(null)
        setImageUrl(null)
      }
      await loadTree()
      onChanged?.()
      return true
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
      return false
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('folder', targetDir)
      await api.post(`/api/skills/${skill.id}/upload`, fd)
      toast.success(`已上传「${file.name}」`)
      await loadTree()
      onChanged?.()
    } catch (err) {
      toast.error(`上传失败：${err.message}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleExportZip = async () => {
    try {
      const res = await api.get(`/api/skills/${skill.id}/export-zip`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${skill.name || skill.id}.zip`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('已导出 Skill ZIP 包')
    } catch (e) {
      toast.error(`导出失败：${e.message}`)
    }
  }

  const fm = selected?.name === 'SKILL.md' && content ? parseFrontmatter(content.content) : null

  const renderPreview = () => {
    if (!selected) {
      return (
        <div className="h-full flex items-center justify-center">
          <Empty
            icon={FileCode2}
            title="选择一个文件查看内容"
            description="左侧为 Skill 的标准目录结构：SKILL.md、scripts/、references/、examples/、assets/ 等"
          />
        </div>
      )
    }
    if (selected.type === 'dir') {
      return (
        <div className="h-full flex items-center justify-center">
          <Empty
            icon={FolderOpen}
            title={selected.path ? `目录 ${selected.path}` : 'Skill 根目录'}
            description="可在此目录下新建文件、上传文件或创建子目录"
          />
        </div>
      )
    }
    if (contentLoading) {
      return (
        <div className="h-full flex items-center justify-center text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" /> 加载中…
        </div>
      )
    }
    if (imageUrl) {
      return (
        <div className="h-full flex items-center justify-center bg-[repeating-conic-gradient(#f3f4f6_0%_25%,#ffffff_0%_50%)] bg-[length:20px_20px] rounded-xl">
          <img
            src={imageUrl}
            alt={selected.name}
            className="max-w-full max-h-[56vh] object-contain rounded-lg shadow"
          />
        </div>
      )
    }
    if (!content) return null
    if (!content.is_text) {
      return (
        <div className="h-full flex items-center justify-center">
          <Empty
            icon={FileCode2}
            title="二进制文件不可预览"
            description={`${selected.name}（${formatSize(content.size)}）请下载后查看`}
          />
        </div>
      )
    }
    if (editing) {
      return (
        <div className="h-full flex flex-col">
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="flex-1 w-full p-4 font-mono text-sm text-gray-800 bg-gray-50 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none"
            spellCheck={false}
          />
          <div className="flex justify-end gap-2 mt-3">
            <Button variant="secondary" size="sm" icon={X} onClick={() => setEditing(false)}>
              取消
            </Button>
            <Button size="sm" icon={Save} loading={saving} onClick={handleSave}>
              保存
            </Button>
          </div>
        </div>
      )
    }
    if (selected.name === 'SKILL.md' && fm) {
      return (
        <div className="space-y-3">
          {fm.meta.name && (
            <div className="flex flex-wrap items-center gap-2 bg-violet-50 border border-violet-100 rounded-xl px-3 py-2">
              <Sparkles className="w-4 h-4 text-violet-500" />
              <span className="text-sm font-semibold text-violet-700">{fm.meta.name}</span>
              {fm.meta.description && (
                <span className="text-xs text-violet-500 truncate flex-1">
                  {fm.meta.description}
                </span>
              )}
            </div>
          )}
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <MarkdownRenderer content={fm.body || '(正文为空)'} />
          </div>
        </div>
      )
    }
    return (
      <pre className="h-full overflow-auto bg-gray-50 rounded-xl p-4 text-xs text-gray-800 font-mono whitespace-pre-wrap break-all">
        {content.content || '（空文件）'}
      </pre>
    )
  }

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={skill?.name}
        size="2xl"
        footer={
          <>
            <Button variant="secondary" icon={Download} onClick={handleExportZip}>
              导出 ZIP
            </Button>
            <Button variant="secondary" onClick={onClose}>
              关闭
            </Button>
            <Button
              variant="ghost"
              icon={Pencil}
              onClick={() => {
                onEdit(skill)
                onClose()
              }}
            >
              编辑信息
            </Button>
            <Button
              variant="danger"
              icon={Trash2}
              onClick={() => {
                onDelete(skill)
                onClose()
              }}
            >
              删除 Skill
            </Button>
          </>
        }
      >
        <div className="flex gap-4 h-[68vh] -m-2">
          {/* 左侧：目录树 */}
          <div className="w-64 flex-shrink-0 border-r border-gray-100 pr-2 flex flex-col">
            <div className="flex items-center gap-1 flex-wrap pb-2 border-b border-gray-100">
              <Button
                size="sm"
                variant="ghost"
                icon={Plus}
                onClick={() => {
                  setCreating('file')
                  setCreateName('')
                }}
                title="新建文件"
              >
                文件
              </Button>
              <Button
                size="sm"
                variant="ghost"
                icon={FolderPlus}
                onClick={() => {
                  setCreating('folder')
                  setCreateName('')
                }}
                title="新建文件夹"
              >
                目录
              </Button>
              <Button
                size="sm"
                variant="ghost"
                icon={Upload}
                loading={uploading}
                onClick={() => fileInputRef.current?.click()}
                title="上传文件"
              >
                上传
              </Button>
              <Button
                size="sm"
                variant="ghost"
                icon={Download}
                onClick={handleExportZip}
                title="导出 ZIP"
              />
              <Button size="sm" variant="ghost" icon={RefreshCw} onClick={loadTree} title="刷新" />
            </div>

            {creating && (
              <div className="flex items-center gap-1 py-2">
                <input
                  autoFocus
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreate()
                    if (e.key === 'Escape') setCreating(null)
                  }}
                  placeholder={`${creating === 'folder' ? '目录名' : '文件名'}（创建于 ${targetDir || '根目录'}/）`}
                  className="flex-1 min-w-0 px-2 py-1 rounded-lg border border-gray-200 text-xs focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                />
                <button
                  onClick={handleCreate}
                  className="p-1.5 rounded-lg text-violet-600 hover:bg-violet-50"
                  title="确认"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setCreating(null)}
                  className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100"
                  title="取消"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            <div className="flex-1 overflow-y-auto mt-2">
              {loading ? (
                <div className="p-4 text-gray-400 flex items-center gap-2 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  加载中…
                </div>
              ) : tree ? (
                <>
                  <TreeNode
                    node={tree}
                    depth={0}
                    expanded={expanded}
                    onToggle={toggleDir}
                    selectedPath={selected?.path}
                    onSelect={selectNode}
                    rootName={skill?.name}
                  />
                  {tree.file_count === 0 && (
                    <div className="mt-3 px-3 py-4 bg-gray-50 rounded-xl text-center">
                      <p className="text-xs text-gray-500 mb-2">
                        目录为空，点击「文件 / 目录 / 上传」开始构建标准结构
                      </p>
                    </div>
                  )}
                </>
              ) : null}
            </div>

            {/* 隐藏的文件选择 */}
            <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} />
          </div>

          {/* 右侧：内容区 */}
          <div className="flex-1 min-w-0 flex flex-col">
            {selected && (
              <div className="flex items-center justify-between gap-2 pb-2 border-b border-gray-100 flex-shrink-0">
                <div className="flex items-center gap-2 min-w-0">
                  {selected.type === 'file' ? (
                    <FileCode2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  ) : (
                    <Folder className="w-4 h-4 text-amber-500 flex-shrink-0" />
                  )}
                  <span className="font-mono text-xs text-gray-700 truncate">
                    {selected.path || skill.name}
                  </span>
                  {content && (
                    <span className="text-[10px] text-gray-400 flex-shrink-0">
                      {formatSize(content.size)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {selected.type === 'file' && content?.is_text && !editing && (
                    <Button size="sm" variant="ghost" icon={Pencil} onClick={startEdit}>
                      编辑
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={Trash2}
                    onClick={() => setDeleteTarget(selected)}
                  >
                    删除
                  </Button>
                </div>
              </div>
            )}
            <div className="flex-1 overflow-y-auto mt-3">{renderPreview()}</div>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title={deleteTarget?.type === 'dir' ? '确认删除目录' : '确认删除文件'}
        message={
          deleteTarget?.type === 'dir' ? (
            <>
              确定要删除目录「
              <span className="font-medium text-gray-700">{deleteTarget?.path}</span>
              」及其全部内容吗？此操作不可撤销。
            </>
          ) : (
            <>
              确定要删除文件「
              <span className="font-medium text-gray-700">{deleteTarget?.path}</span>
              」吗？此操作不可撤销。
            </>
          )
        }
        confirmLabel="确认删除"
      />
    </>
  )
}
