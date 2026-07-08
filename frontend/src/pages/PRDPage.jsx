import React, { useState } from 'react'
import axios from 'axios'
import { FileText, FolderGit2, Play, Loader2, CheckCircle2, AlertCircle, BookOpen } from 'lucide-react'

export default function PRDPage() {
  const [prdText, setPrdText] = useState('')
  const [repoPath, setRepoPath] = useState('/Users/yanping.ma/GolandProjects/sponge')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    if (!prdText.trim()) {
      setError('请输入 PRD 内容')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await axios.post('/api/prd/review', {
        prd_text: prdText,
        repo_path: repoPath,
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
      {/* Hero */}
      <div className="text-center space-y-4 py-8">
        <h1 className="text-4xl font-bold text-gray-900">智能研发平台</h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          基于 biz-delivery 的代码理解 + PRD 审查 + 技术方案生成 + 测试用例生成
        </p>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* PRD 编辑区 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center">
              <FileText className="w-5 h-5 text-blue-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">PRD 内容</h2>
            </div>
          </div>
          <div className="p-6 space-y-4">
            <textarea
              className="w-full h-80 p-4 border border-gray-300 rounded-lg font-mono text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all resize-none"
              placeholder={"请输入 PRD 内容...\n\n例如：\n1. 新增素材分享功能\n2. 支持将创意素材分享给其他广告账户\n3. 分享时需要校验素材状态"}
              value={prdText}
              onChange={(e) => setPrdText(e.target.value)}
            />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <FolderGit2 className="w-4 h-4 inline mr-1" />
                仓库路径
              </label>
              <input
                type="text"
                className="w-full p-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all text-sm font-mono"
                value={repoPath}
                onChange={(e) => setRepoPath(e.target.value)}
              />
            </div>
            <button
              onClick={handleSubmit}
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
                  <Play className="w-5 h-5 mr-2" />
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

        {/* 审查结果 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center">
              <CheckCircle2 className="w-5 h-5 text-green-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">审查报告</h2>
            </div>
          </div>
          <div className="p-6 min-h-[500px]">
            {result ? (
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-6 rounded-lg border border-gray-200 font-mono leading-relaxed">{result}</pre>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 py-20">
                <BookOpen className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg font-medium">暂无审查结果</p>
                <p className="text-sm mt-2">输入 PRD 后点击"开始审查"</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
        {[
          { icon: '🔍', title: 'PRD 审查', desc: '自动识别 P0/P1/P2 问题，给出修改建议', bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-200' },
          { icon: '📐', title: '技术方案', desc: '生成完整的技术设计方案，含架构图', bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-200' },
          { icon: '🧪', title: '测试用例', desc: '自动生成正向/异常/边界测试用例', bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-200' },
        ].map((feature, i) => (
          <div key={i} className={`rounded-xl p-6 border ${feature.bg} ${feature.text} ${feature.border} transition-all duration-200 hover:shadow-md`}>
            <span className="text-3xl block mb-3">{feature.icon}</span>
            <h3 className={`font-semibold ${feature.text} mb-2`}>{feature.title}</h3>
            <p className="text-sm text-gray-600">{feature.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
