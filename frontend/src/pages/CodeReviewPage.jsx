import React, { useState, useEffect } from 'react'
import { Shield, Play, Copy, Check, Clock } from 'lucide-react'
import MarkdownRenderer from '../components/MarkdownRenderer'
import ShareButton from '../components/ShareButton'
import { Card, Button, Badge, Empty, PageHeader } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const LANGUAGES = ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c++', 'sql']

export default function CodeReviewPage() {
  const toast = useToast()
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState('python')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)

  useEffect(() => { loadHistory() }, [])
  const loadHistory = async () => {
    try { const res = await api.get('/api/code/reviews'); setHistory(res.data) } catch (e) {}
  }

  const review = async () => {
    if (!code.trim()) { toast.error('请输入代码'); return }
    setLoading(true); setResult('')
    try {
      const res = await api.post('/api/code/review', { language, code })
      setResult(res.data.result); loadHistory(); toast.success('审查完成')
    } catch (e) { toast.error(`审查失败：${e.message}`) }
    finally { setLoading(false) }
  }

  const copyResult = () => {
    navigator.clipboard.writeText(result); setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 代码审查"
        description="粘贴代码，AI 分析代码质量、潜在 bug 和优化建议"
        icon={Shield}
        iconColor="from-amber-500 to-orange-600"
      />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-amber-500" /> 待审查代码
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
              <label className="block text-sm font-medium text-gray-700 mb-1">代码内容</label>
              <textarea value={code} onChange={(e) => setCode(e.target.value)}
                placeholder="粘贴需要审查的代码..."
                rows={12} className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-brand-500" />
            </div>
            <Button variant="primary" icon={Shield} loading={loading} onClick={review} className="w-full">
              开始审查
            </Button>
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">审查报告</h2>
            {result && (
              <div className="flex items-center gap-2">
                <ShareButton content={result} title="代码审查报告" contentType="code-review" />
                <Button variant="ghost" size="sm" icon={copied ? Check : Copy} onClick={copyResult}>{copied ? '已复制' : '复制'}</Button>
              </div>
            )}
          </div>
          {result ? (
            <MarkdownRenderer content={result} className="max-h-96 overflow-auto" />
          ) : (
            <Empty icon={Shield} title="等待审查" description="粘贴代码后点击审查按钮" />
          )}
        </Card>
      </div>
      {history.length > 0 && (
        <Card>
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2"><Clock className="w-5 h-5 text-gray-400" /> 审查历史</h2>
          <div className="space-y-2">
            {history.slice(0, 5).map((item) => (
              <div key={item.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer"
                onClick={() => { setCode(item.code); setLanguage(item.language); setResult(item.result) }}>
                <Badge color="amber">{item.language}</Badge>
                <span className="text-sm text-gray-700 truncate flex-1">{item.code?.slice(0, 80)}...</span>
                <span className="text-xs text-gray-400">{item.created_at?.slice(0, 16)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
