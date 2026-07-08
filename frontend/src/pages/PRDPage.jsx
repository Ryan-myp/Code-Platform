import React, { useState } from 'react'
import axios from 'axios'

export default function PRDPage() {
  const [prdText, setPrdText] = useState('')
  const [repoPath, setRepoPath] = useState('/Users/yanping.ma/GolandProjects/sponge')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleSubmit = async () => {
    if (!prdText.trim()) return
    setLoading(true)
    try {
      const res = await axios.post('/api/prd/review', {
        prd_text: prdText,
        repo_path: repoPath,
      })
      setResult(res.data.report)
    } catch (err) {
      alert('审查失败: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">智能研发平台</h1>
        <p className="mt-2 text-sm text-gray-600">基于 biz-delivery 的代码理解 + PRD 审查 + 技术方案生成</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">PRD 内容</h2>
          <textarea
            className="w-full h-64 p-3 border rounded-md font-mono text-sm"
            placeholder="请输入 PRD 内容..."
            value={prdText}
            onChange={(e) => setPrdText(e.target.value)}
          />
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">仓库路径</label>
            <input
              type="text"
              className="w-full p-2 border rounded-md text-sm"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading || !prdText.trim()}
            className="mt-4 w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '审查中...' : '开始审查'}
          </button>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">审查报告</h2>
          {result ? (
            <div className="prose prose-sm max-w-none">
              <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded">{result}</pre>
            </div>
          ) : (
            <div className="text-gray-400 text-center py-20">暂无审查结果</div>
          )}
        </div>
      </div>
    </div>
  )
}
