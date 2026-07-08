import React, { useState } from 'react'
import axios from 'axios'
import { Code2, Loader2, CheckCircle2, AlertCircle, Database, GitBranch, Layers, Settings } from 'lucide-react'

export default function TDPage() {
  const [prdText, setPrdText] = useState('')
  const [repoPath, setRepoPath] = useState('/Users/yanping.ma/GolandProjects/sponge')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleGenerate = async () => {
    if (!prdText.trim()) {
      setError('请输入 PRD 内容')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await axios.post('/api/prd/technical-design', {
        prd_text: prdText,
        repo_path: repoPath,
      })
      setResult(res.data.document)
    } catch (err) {
      setError('生成失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-full mb-4">
          <Code2 className="w-8 h-8 text-indigo-600" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">技术方案</h1>
        <p className="text-lg text-gray-600">生成完整的技术设计方案，含架构图</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <Settings className="w-5 h-5 text-indigo-600 mr-2" />
              配置
            </h2>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">PRD 内容</label>
              <textarea
                className="w-full h-64 p-4 border border-gray-300 rounded-lg font-mono text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all resize-none"
                placeholder={"请输入 PRD 内容..."}
                value={prdText}
                onChange={(e) => setPrdText(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">仓库路径</label>
              <input
                type="text"
                className="w-full p-3 border border-gray-300 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm font-mono"
                value={repoPath}
                onChange={(e) => setRepoPath(e.target.value)}
              />
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading || !prdText.trim()}
              className="w-full bg-indigo-600 text-white py-3 px-6 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all duration-200 flex items-center justify-center"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5 mr-2" />
                  生成技术方案
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
              <Layers className="w-5 h-5 text-indigo-600 mr-2" />
              技术方案
            </h2>
          </div>
          <div className="p-6 min-h-[500px]">
            {result ? (
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-6 rounded-lg border border-gray-200 font-mono leading-relaxed">{result}</pre>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 py-20">
                <Database className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg font-medium">暂无技术方案</p>
                <p className="text-sm mt-2">输入 PRD 后点击"生成技术方案"</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 技术方案示例 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <GitBranch className="w-5 h-5 text-indigo-600 mr-2" />
          技术方案包含内容
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: '📐', title: '架构设计', desc: '模块划分、数据流向、依赖关系' },
            { icon: '🗄️', title: '数据库设计', desc: '表结构、字段定义、索引设计' },
            { icon: '🔌', title: '接口设计', desc: 'RESTful API、Request/Response' },
            { icon: '🔄', title: '流程图', desc: '核心业务流程图、时序图' },
            { icon: '⚡', title: '性能设计', desc: '缓存策略、限流、异步处理' },
            { icon: '🔒', title: '安全设计', desc: '鉴权、加密、防注入' },
          ].map((item, i) => (
            <div key={i} className="p-4 bg-gray-50 rounded-lg">
              <span className="text-2xl block mb-2">{item.icon}</span>
              <h3 className="font-semibold text-gray-900 mb-1">{item.title}</h3>
              <p className="text-sm text-gray-600">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
