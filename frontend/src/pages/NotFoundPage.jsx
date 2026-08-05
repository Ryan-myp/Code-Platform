import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Compass, Home, ArrowLeft } from 'lucide-react'
import { Card, Empty, PageHeader } from '../components/ui'

/**
 * 404 兜底页：未匹配任何路由时展示，避免出现空白空壳。
 */
export default function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <div className="space-y-6">
      <PageHeader
        title="页面不存在"
        description="您访问的页面不存在或已被移动"
        icon={Compass}
        iconColor="from-amber-500 to-orange-600"
      />
      <Card>
        <Empty
          icon={Compass}
          title="404 · 找不到这个页面"
          description="可能是链接有误、页面已下线，或者您输入了一个不存在的地址。"
          action={
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate(-1)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" /> 返回上一页
              </button>
              <button
                onClick={() => navigate('/home')}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-600 to-brand-500 text-white rounded-xl hover:from-brand-700 hover:to-brand-600 shadow-soft transition-all"
              >
                <Home className="w-4 h-4" /> 回到首页
              </button>
            </div>
          }
        />
      </Card>
    </div>
  )
}
