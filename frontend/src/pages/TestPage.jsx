import React, { useState } from 'react'
import axios from 'axios'
import { TestTube2, Loader2, CheckCircle2, AlertCircle, ListChecks, Bug, Shield } from 'lucide-react'

export default function TestPage() {
  const [prdText, setPrdText] = useState('')
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
      const res = await axios.post('/api/prd/test-cases', {
        prd_text: prdText,
      })
      setResult(res.data.cases)
    } catch (err) {
      setError('生成失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
          <TestTube2 className="w-8 h-8 text-green-600" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">测试用例</h1>
        <p className="text-lg text-gray-600">自动生成正向/异常/边界测试用例</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <ListChecks className="w-5 h-5 text-green-600 mr-2" />
              PRD 内容
            </h2>
          </div>
          <div className="p-6 space-y-4">
            <textarea
              className="w-full h-64 p-4 border border-gray-300 rounded-lg font-mono text-sm focus:border-green-500 focus:ring-2 focus:ring-green-100 transition-all resize-none"
              placeholder={"请输入 PRD 内容..."}
              value={prdText}
              onChange={(e) => setPrdText(e.target.value)}
            />
            <button
              onClick={handleGenerate}
              disabled={loading || !prdText.trim()}
              className="w-full bg-green-600 text-white py-3 px-6 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all duration-200 flex items-center justify-center"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5 mr-2" />
                  生成测试用例
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
              <Bug className="w-5 h-5 text-green-600 mr-2" />
              测试用例
            </h2>
          </div>
          <div className="p-6 min-h-[500px]">
            {result ? (
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-6 rounded-lg border border-gray-200 font-mono leading-relaxed">{result}</pre>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 py-20">
                <TestTube2 className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg font-medium">暂无测试用例</p>
                <p className="text-sm mt-2">输入 PRD 后点击"生成测试用例"</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 测试用例类型 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Shield className="w-5 h-5 text-green-600 mr-2" />
          测试用例包含类型
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: '✅', title: '正向测试', desc: '正常流程测试，验证功能是否正确' },
            { icon: '⚠️', title: '异常测试', desc: '异常场景测试，验证错误处理' },
            { icon: '🔒', title: '安全测试', desc: 'SQL 注入/XSS/越权访问' },
            { icon: '🔄', title: '边界测试', desc: '空值/超限/并发等边界条件' },
            { icon: '📊', title: '性能测试', desc: 'QPS/响应时间/资源占用' },
            { icon: '🔗', title: '集成测试', desc: '多模块/多服务集成验证' },
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
