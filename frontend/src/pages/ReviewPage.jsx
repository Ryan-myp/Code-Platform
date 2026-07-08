import React, { useState } from 'react'
import axios from 'axios'
import { FileText, Loader2, CheckCircle2, AlertCircle, ClipboardList, Code2, TestTube2, TerminalSquare } from 'lucide-react'

export default function ReviewPage() {
  const [prdText, setPrdText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleReview = async () => {
    if (!prdText.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await axios.post('/api/prd/review', {
        prd_text: prdText,
      })
      setResult(res.data.report)
    } catch (err) {
      setError('审查失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
          <FileText className="w-8 h-8 text-blue-600" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">PRD 审查</h1>
        <p className="text-lg text-gray-600">自动识别 P0/P1/P2 问题，给出修改建议</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <ClipboardList className="w-5 h-5 text-blue-600 mr-2" />
              PRD 内容
            </h2>
          </div>
          <div className="p-6 space-y-4">
            <textarea
              className="w-full h-80 p-4 border border-gray-300 rounded-lg font-mono text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all resize-none"
              placeholder={"请输入 PRD 内容...\n\n例如：\n1. 新增素材分享功能\n2. 支持将创意素材分享给其他广告账户\n3. 分享时需要校验素材状态"}
              value={prdText}
              onChange={(e) => setPrdText(e.target.value)}
            />
            <button
              onClick={handleReview}
              disabled={loading || !prdText.trim()}
              className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all duration-200 flex items-center justify-center"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  审查中...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5 mr-2" />
                  开始审查
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
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <CheckCircle2 className="w-5 h-5 text-green-600 mr-2" />
              审查报告
            </h2>
          </div>
          <div className="p-6 min-h-[500px]">
            {result ? (
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-6 rounded-lg border border-gray-200 font-mono leading-relaxed">{result}</pre>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 py-20">
                <FileText className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg font-medium">暂无审查结果</p>
                <p className="text-sm mt-2">输入 PRD 后点击"开始审查"</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
