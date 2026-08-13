import React, { useState, useEffect } from 'react'
import { useI18n } from '../i18n/index.jsx'
import { Send, ThumbsUp, ThumbsDown, AlertCircle, CheckCircle, Lightbulb, Bug, Star } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'

export default function FeedbackPage() {
  const { t } = useI18n()
  const toast = useToast()
  const FEEDBACK_TYPES = [
    { id: 'feedback', label: '使用反馈', icon: MessageCircle, color: 'text-blue-500' },
    { id: 'bug', label: t('feedback.type_bug'), icon: Bug, color: 'text-red-500' },
    { id: 'suggestion', label: t('feedback.type_suggestion'), icon: Lightbulb, color: 'text-amber-500' },
    { id: 'praise', label: t('feedback.type_praise'), icon: Star, color: 'text-emerald-500' },
  ]
  const [type, setType] = useState('feedback')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('tool')
  const [contact, setContact] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [myFeedbacks, setMyFeedbacks] = useState([])

  useEffect(() => {
    loadMyFeedbacks()
  }, [])

  const loadMyFeedbacks = async () => {
    try {
      const res = await api.get('/api/feedback')
      setMyFeedbacks(res.data?.feedbacks || [])
    } catch (e) {
      console.error('Load feedbacks error:', e)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim() || !content.trim()) {
      toast.error('请填写标题和内容')
      return
    }
    setSubmitting(true)
    try {
      await api.post('/api/feedback', {
        type,
        title: title.trim(),
        content: content.trim(),
        category,
        contact: contact.trim(),
      })
      setSubmitted(true)
      toast.success('反馈提交成功，感谢您的建议！')
      setTitle('')
      setContent('')
      setTimeout(() => setSubmitted(false), 3000)
      loadMyFeedbacks()
    } catch (err) {
      toast.error(err.response?.data?.detail || '提交失败，请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  const getTypeIcon = (t) => {
    const icons = { feedback: MessageCircle, bug: Bug, suggestion: Lightbulb, praise: Star }
    return icons[t] || MessageCircle
  }

  const getTypeColor = (t) => {
    const colors = { feedback: 'bg-blue-100 text-blue-700', bug: 'bg-red-100 text-red-700', suggestion: 'bg-amber-100 text-amber-700', praise: 'bg-emerald-100 text-emerald-700' }
    return colors[t] || 'bg-gray-100 text-gray-700'
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-page-in">
      {/* 标题 */}
      <div>
        <h1 className="text-2xl font-bold text-ink-900">用户反馈</h1>
        <p className="text-gray-500 mt-1">您的每一条建议都是我们进步的动力</p>
      </div>

      {/* 反馈类型选择 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <p className="font-medium text-gray-700 mb-3">反馈类型</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {FEEDBACK_TYPES.map(ft => (
            <button
              key={ft.id}
              onClick={() => setType(ft.id)}
              className={`p-3 rounded-xl border-2 transition-all text-center ${
                type === ft.id
                  ? 'border-purple-500 bg-purple-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <ft.icon className={`w-6 h-6 mx-auto mb-1 ${ft.color}`} />
              <p className="text-sm font-medium text-gray-700">{ft.label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* 反馈表单 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">标题 *</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="简短描述您的问题或建议"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 outline-none"
              maxLength={100}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">详细描述 *</label>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="请详细描述您的反馈，包括操作步骤、预期结果等"
              rows={5}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 outline-none resize-none"
              maxLength={2000}
            />
            <p className="text-xs text-gray-400 mt-1">{content.length}/2000</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 outline-none"
              >
                <option value="tool">工具问题</option>
                <option value="ui">界面体验</option>
                <option value="performance">性能问题</option>
                <option value="other">其他</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">联系方式（可选）</label>
              <input
                type="text"
                value={contact}
                onChange={e => setContact(e.target.value)}
                placeholder="邮箱或微信号"
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 bg-gradient-to-r from-purple-600 to-violet-600 text-white rounded-xl font-medium hover:from-purple-700 hover:to-violet-700 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                提交中...
              </>
            ) : submitted ? (
              <>
                <CheckCircle className="w-5 h-5" />
                已提交！
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                提交反馈
              </>
            )}
          </button>
        </form>
      </div>

      {/* 我的反馈历史 */}
      {myFeedbacks.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <p className="font-medium text-gray-700 mb-3">我的反馈</p>
          <div className="space-y-3">
            {myFeedbacks.slice(0, 5).map(fb => {
              const Icon = getTypeIcon(fb.type)
              return (
                <div key={fb.id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${getTypeColor(fb.type)}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-gray-900 text-sm truncate">{fb.title}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${getTypeColor(fb.type)}`}>
                        {fb.status}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{fb.content.slice(0, 80)}...</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(fb.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function MessageCircle(props) {
  return <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>
}
