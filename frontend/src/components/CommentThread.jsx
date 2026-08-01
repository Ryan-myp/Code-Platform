import { useState } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Underline from '@tiptap/extension-underline'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'

// ─── CommentThread.jsx ────────────────────────────────────────────────
export default function CommentThread({ target_type, target_id }) {
  const [comments, setComments] = useState([])
  const [replyingTo, setReplyingTo] = useState(null)
  const [newComment, setNewComment] = useState('')
  const [loading, setLoading] = useState(false)

  // TipTap editor for comment input
  const editor = useEditor({
    extensions: [StarterKit, Image, Underline],
    content: '',
    onUpdate: ({ editor }) => setNewComment(editor.getHTML()),
  })

  const loadComments = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/comments/thread?target_type=${target_type}&target_id=${target_id}`)
      if (res.ok) {
        const data = await res.json()
        setComments(data)
      }
    } catch (e) {
      console.error('Failed to load comments:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!editor || !newComment.trim()) return
    
    try {
      const res = await fetch(`${API_BASE}/api/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: newComment,
          target_type,
          target_id,
          parent_comment_id: replyingTo || '',
          author_id: 'user_001', // TODO: auth
        }),
      })
      
      if (res.ok) {
        editor.commands.setContent('')
        setNewComment('')
        setReplyingTo(null)
        loadComments()
      }
    } catch (e) {
      console.error('Failed to submit comment:', e)
    }
  }

  const handleReply = (commentId) => {
    setReplyingTo(replyingTo === commentId ? null : commentId)
  }

  // Render HTML content safely
  const renderCommentContent = (html) => {
    return { __html: html }
  }

  return (
    <div className="comment-thread mt-4">
      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
        💬 评论 ({comments.reduce((sum, c) => sum + 1 + c.replies.length, 0)})
      </h3>

      {/* Comment Input */}
      <div className="border rounded-lg p-3 mb-4 bg-gray-50">
        {editor && (
          <>
            {/* Toolbar */}
            <div className="flex gap-1 mb-2 border-b pb-2">
              <button onClick={() => editor.chain().focus().toggleBold().run()} className={`p-1 rounded ${editor.isActive('bold') ? 'bg-purple-100' : ''}`} title="加粗">
                <strong>B</strong>
              </button>
              <button onClick={() => editor.chain().focus().toggleItalic().run()} className={`p-1 rounded ${editor.isActive('italic') ? 'bg-purple-100' : ''}`} title="斜体">
                <em>I</em>
              </button>
              <button onClick={() => editor.chain().focus().toggleUnderline().run()} className={`p-1 rounded ${editor.isActive('underline') ? 'bg-purple-100' : ''}`} title="下划线">
                <u>U</u>
              </button>
              <button onClick={() => editor.chain().focus().toggleCodeBlock().run()} className={`p-1 rounded ${editor.isActive('codeBlock') ? 'bg-purple-100' : ''}`} title="代码块">
                {'{ }'}
              </button>
              <button onClick={() => {
                const url = prompt('图片 URL:')
                if (url) editor.chain().focus().setImage({ src: url }).run()
              }} className="p-1 rounded hover:bg-purple-100" title="插入图片">
                🖼️
              </button>
            </div>
            
            {/* Editor */}
            <EditorContent editor={editor} className="min-h-[80px] max-h-[200px] overflow-y-auto prose prose-sm max-w-none" />
          </>
        )}
        
        <div className="flex justify-end gap-2 mt-2">
          {replyingTo && (
            <span className="text-sm text-gray-500 self-center">回复评论</span>
          )}
          <button onClick={handleSubmit} disabled={!newComment.trim()} className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg disabled:opacity-50 hover:shadow-lg transition-all">
            提交评论
          </button>
        </div>
      </div>

      {/* Comments List */}
      {loading ? (
        <div className="text-center py-4 text-gray-400">加载中...</div>
      ) : comments.length === 0 ? (
        <div className="text-center py-4 text-gray-400">暂无评论，来抢沙发吧~</div>
      ) : (
        <div className="space-y-4">
          {comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              onReply={handleReply}
              isReplying={replyingTo === comment.id}
              depth={0}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── CommentItem.jsx ──────────────────────────────────────────────
function CommentItem({ comment, onReply, isReplying, depth = 0 }) {
  const [replyContent, setReplyContent] = useState('')
  const [replying, setReplying] = useState(isReplying)
  const [submitting, setSubmitting] = useState(false)

  const handleReplySubmit = async () => {
    if (!replyContent.trim()) return
    setSubmitting(true)
    
    try {
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8888'
      const res = await fetch(`${API_BASE}/api/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: replyContent,
          target_type: comment.target_type,
          target_id: comment.target_id,
          parent_comment_id: comment.id,
          author_id: 'user_001',
        }),
      })
      
      if (res.ok) {
        setReplyContent('')
        setReplying(false)
        window.location.reload() // Simple reload to refresh thread
      }
    } catch (e) {
      console.error('Failed to reply:', e)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={`${depth > 0 ? 'ml-8 border-l-2 border-purple-200 pl-4' : ''}`}>
      <div className="bg-white rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white text-sm font-bold">
              {comment.author_id?.[0]?.toUpperCase() || 'U'}
            </div>
            <span className="text-sm font-medium">{comment.author_id || '匿名用户'}</span>
            <span className="text-xs text-gray-400">{new Date(comment.created_at).toLocaleString('zh-CN')}</span>
          </div>
          <button 
            onClick={() => onReply(comment.id)}
            className="text-xs text-purple-500 hover:text-purple-700 px-2 py-1 rounded hover:bg-purple-50"
          >
            ↩ 回复
          </button>
        </div>
        
        <div 
          className="prose prose-sm max-w-none text-gray-700"
          dangerouslySetInnerHTML={{ __html: comment.content }}
        />
        
        <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
          <span>👍 {comment.like_count || 0}</span>
          <span>💬 {comment.reply_count || comment.replies?.length || 0} 回复</span>
        </div>
      </div>

      {/* Reply Input */}
      {replying && (
        <div className="mt-2 ml-4">
          <textarea
            value={replyContent}
            onChange={(e) => setReplyContent(e.target.value)}
            placeholder="写下你的回复..."
            className="w-full p-2 border rounded-lg text-sm resize-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/10"
            rows={2}
          />
          <div className="flex justify-end gap-2 mt-1">
            <button onClick={() => setReplying(false)} className="text-xs text-gray-500 px-3 py-1">取消</button>
            <button 
              onClick={handleReplySubmit} 
              disabled={submitting || !replyContent.trim()}
              className="text-xs px-3 py-1 bg-purple-500 text-white rounded hover:bg-purple-600 disabled:opacity-50"
            >
              {submitting ? '提交中...' : '回复'}
            </button>
          </div>
        </div>
      )}

      {/* Nested Replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="mt-2 space-y-2">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              onReply={onReply}
              isReplying={isReplying}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}
