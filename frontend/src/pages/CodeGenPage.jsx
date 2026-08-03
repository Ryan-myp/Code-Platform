import React, { useState, useEffect, useRef } from 'react'
import { Code2, Play, Copy, Check, RotateCcw, Clock, Trash2 } from 'lucide-react'
import { Card, Button, Badge, Empty, PageHeader } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import ShareButton from '../components/ShareButton'

const LANGUAGES = ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c++', 'sql', 'html/css', 'shell']

export default function CodeGenPage() {
  const toast = useToast()
  const [prompt, setPrompt] = useState('')
  const [language, setLanguage] = useState('python')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const resultRef = useRef(null)

  useEffect(() => { loadHistory() }, [])

  const loadHistory = async () => {
    try {
      const res = await api.get('/api/code/generations')
      setHistory(res.data)
    } catch (e) { /* ignore */ }
  }

  const generate = async () => {
    if (!prompt.trim()) { toast.error('请输入代码需求'); return }
    setLoading(true)
    setResult('')
    try {
      const res = await api.post('/api/code/generate', { language, prompt })
      setResult(res.data.result)
      loadHistory()
      toast.success('代码生成完成')
    } catch (e) {
      toast.error(`生成失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const copyResult = () => {
    navigator.clipboard.writeText(result)
    setCopied(true)
    toast.success('已复制到剪贴板')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 代码生成"
        description="描述你的需求，AI 自动生成高质量代码"
        icon={Code2}
        iconColor="from-blue-500 to-indigo-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 输入区 */}
        <Card className="lg:col-span-1">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Code2 className="w-5 h-5 text-blue-500" /> 代码需求
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">编程语言</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500">
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">需求描述</label>
              <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)}
                placeholder="例如：写一个 Python 函数，实现快速排序算法..."
                rows={6} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500" />
            </div>
            <Button variant="primary" icon={Play} loading={loading} onClick={generate} className="w-full">
              生成代码
            </Button>
          </div>
        </Card>

        {/* 结果区 */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">生成结果</h2>
            {result && (
              <div className="flex gap-1 items-center">
                <ShareButton content={result} title="代码生成结果" contentType="code" />
                <Button variant="ghost" size="sm" icon={copied ? Check : Copy} onClick={copyResult}>
                  {copied ? '已复制' : '复制'}
                </Button>
                <Button variant="ghost" size="sm" icon={RotateCcw} onClick={() => { setResult(''); setPrompt('') }}>
                  清空
                </Button>
              </div>
            )}
          </div>
          {result ? (
            <pre ref={resultRef} className="bg-gray-900 text-green-400 rounded-lg p-4 text-sm overflow-auto max-h-96 font-mono">
              {result}
            </pre>
          ) : (
            <Empty icon={Code2} title="等待生成" description="输入需求后点击生成按钮" />
          )}
        </Card>
      </div>

      {/* 历史记录 */}
      {history.length > 0 && (
        <Card>
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-gray-400" /> 生成历史
          </h2>
          <div className="space-y-2">
            {history.slice(0, 5).map((item) => (
              <div key={item.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer"
                onClick={() => { setPrompt(item.prompt); setLanguage(item.language); setResult(item.result) }}>
                <Badge color="blue">{item.language}</Badge>
                <span className="text-sm text-gray-700 truncate flex-1">{item.prompt}</span>
                <span className="text-xs text-gray-400">{item.created_at?.slice(0, 16)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
