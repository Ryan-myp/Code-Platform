import React, { useState } from 'react'
import { Check, Download, FileDown, FileText, Loader2 } from 'lucide-react'
import { useToast } from '../lib/toast'

/**
 * 结果导出按钮：支持 Markdown / Word(.doc) / PDF(打印)。
 * - md：纯文本下载
 * - docx：HTML 包装的 Word 文档（Word/WPS 可直接打开）
 * - pdf：调用浏览器打印（另存为 PDF）
 */
export default function ExportButton({ content, title = '导出内容', className = '' }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [exporting, setExporting] = useState('')

  const downloadFile = (text, filename, mime) => {
    const blob = new Blob(['\ufeff', text], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportMd = () => {
    if (!content?.trim()) {
      toast.warning('暂无可导出的内容')
      return
    }
    downloadFile(content, `${title}.md`, 'text/markdown;charset=utf-8')
    toast.success('已导出 Markdown 文件')
    setOpen(false)
  }

  const exportDocx = () => {
    if (!content?.trim()) {
      toast.warning('暂无可导出的内容')
      return
    }
    setExporting('docx')
    const html = content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(
        /```(\w*)\n([\s\S]*?)```/g,
        (_m, lang, code) =>
          `<pre style="background:#f5f5f5;padding:12px;border-radius:6px;font-family:Consolas,monospace;font-size:12px;">${code}</pre>`
      )
      .replace(/^### (.*)$/gm, '<h3>$1</h3>')
      .replace(/^## (.*)$/gm, '<h2>$1</h2>')
      .replace(/^# (.*)$/gm, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br/>')
    const doc = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title></head><body style="font-family:'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.7;max-width:800px;margin:40px auto;padding:0 20px;">${html}</body></html>`
    downloadFile(doc, `${title}.doc`, 'application/msword;charset=utf-8')
    toast.success('已导出 Word 文档')
    setOpen(false)
    setTimeout(() => setExporting(''), 500)
  }

  const exportPdf = () => {
    if (!content?.trim()) {
      toast.warning('暂无可导出的内容')
      return
    }
    setOpen(false)
    // 使用浏览器打印另存为 PDF
    toast.info('请在打印窗口中选择「另存为 PDF」')
    setTimeout(() => window.print(), 300)
  }

  return (
    <div className={`relative inline-block ${className}`}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg text-gray-500 hover:text-brand-600 hover:bg-gray-100 transition-colors"
        title="导出结果"
      >
        <Download className="w-3.5 h-3.5" />
        导出
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1.5 z-50 bg-white rounded-xl shadow-xl border border-ink-200/70 p-1.5 w-44 animate-page-in">
            <button
              onClick={exportMd}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-ink-600 hover:bg-ink-50 transition-colors text-left"
            >
              <FileText className="w-4 h-4 text-ink-400" />
              Markdown (.md)
            </button>
            <button
              onClick={exportDocx}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-ink-600 hover:bg-ink-50 transition-colors text-left"
            >
              {exporting === 'docx' ? (
                <Loader2 className="w-4 h-4 text-ink-400 animate-spin" />
              ) : (
                <FileDown className="w-4 h-4 text-ink-400" />
              )}
              Word 文档 (.doc)
            </button>
            <button
              onClick={exportPdf}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-ink-600 hover:bg-ink-50 transition-colors text-left"
            >
              <Download className="w-4 h-4 text-ink-400" />
              PDF（打印）
            </button>
          </div>
        </>
      )}
    </div>
  )
}
