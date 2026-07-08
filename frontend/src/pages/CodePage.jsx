import React, { useState } from 'react'
import axios from 'axios'
import { TerminalSquare, Loader2, CheckCircle2, AlertCircle, FileCode, Copy, Download } from 'lucide-react'

export default function CodePage() {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setCode('')
    try {
      const res = await axios.post('/api/prd/generate-code', {
        prd_text: '这是一个示例 PRD',
      })
      setCode(res.data.files[0]?.content || '// 代码生成中...')
    } catch (err) {
      setError('生成失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    alert('代码已复制到剪贴板')
  }

  const handleDownload = () => {
    const blob = new Blob([code], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'generated-code.go'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-8">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-purple-100 rounded-full mb-4">
          <TerminalSquare className="w-8 h-8 text-purple-600" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">代码生成</h1>
        <p className="text-lg text-gray-600">根据技术方案自动生成代码</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <FileCode className="w-5 h-5 text-purple-600 mr-2" />
              代码生成
            </h2>
          </div>
          <div className="p-6 space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <p className="text-sm text-gray-600">
                基于技术方案自动生成 Go/Python/Java 代码
              </p>
              <ul className="mt-2 text-sm text-gray-700 list-disc list-inside">
                <li>Handler 层代码</li>
                <li>Service 层代码</li>
                <li>DAO 层代码</li>
                <li>Model 定义</li>
                <li>错误码定义</li>
                <li>测试用例代码</li>
              </ul>
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="w-full bg-purple-600 text-white py-3 px-6 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all duration-200 flex items-center justify-center"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5 mr-2" />
                  生成代码
                </>
              )}
            </button>
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
                <AlertCircle className="w-5 h-5 text-red-600 mr-2 flex-shrink-0 mt-0.5" />
                <p className="text-red-700 text-sm">{error}</p>
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <FileCode className="w-5 h-5 text-purple-600 mr-2" />
              生成结果
            </h2>
            <div className="flex space-x-2">
              <button
                onClick={handleCopy}
                className="p-2 text-gray-600 hover:text-purple-600 transition-colors"
                title="复制代码"
              >
                <Copy className="w-4 h-4" />
              </button>
              <button
                onClick={handleDownload}
                className="p-2 text-gray-600 hover:text-purple-600 transition-colors"
                title="下载代码"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="p-6 min-h-[500px]">
            {code ? (
              <pre className="whitespace-pre-wrap text-sm bg-gray-900 text-gray-100 p-6 rounded-lg font-mono leading-relaxed overflow-auto max-h-[500px]">{code}</pre>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 py-20">
                <TerminalSquare className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg font-medium">暂无生成结果</p>
                <p className="text-sm mt-2">点击"生成代码"按钮</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
