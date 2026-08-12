import React, { useState, useEffect } from 'react'
import { FileText, TrendingUp, DollarSign, Award, Star, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'

export default function CreatorCenterPage() {
  const [stats, setStats] = useState(null)
  const [topCreators, setTopCreators] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('my') // my | top

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [statsRes, topRes] = await Promise.all([
        api.get('/api/templates/creator/stats'),
        api.get('/api/templates/creator/top?limit=10'),
      ])
      setStats(statsRes.data)
      setTopCreators(topRes.data?.creators || [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-gray-500 mt-3">加载中…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-2xl flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
        <div>
          <p className="font-medium text-red-700">加载失败</p>
          <p className="text-sm text-red-500 mt-1">{error}</p>
        </div>
      </div>
    )
  }

  const revenueYuan = (stats?.total_revenue || 0).toFixed(2)
  const avgPrice = stats?.templates?.length > 0
    ? (stats.templates.reduce((s, t) => s + (t.price || 0), 0) / stats.templates.length).toFixed(0)
    : '0'

  return (
    <div className="space-y-6">
      {/* 概览卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '上架模板', value: stats?.template_count || 0, icon: FileText, color: 'from-purple-500 to-indigo-500' },
          { label: '总销量', value: stats?.total_sales || 0, icon: TrendingUp, color: 'from-blue-500 to-cyan-500' },
          { label: '总收益', value: `¥${revenueYuan}`, icon: DollarSign, color: 'from-emerald-500 to-teal-500' },
          { label: '平均定价', value: `¥${avgPrice}`, icon: Star, color: 'from-amber-500 to-orange-500' },
        ].map((card, i) => (
          <div key={i} className={`bg-gradient-to-br ${card.color} rounded-2xl p-4 text-white`}>
            <div className="flex items-center justify-between">
              <card.icon className="w-6 h-6 opacity-80" />
              <p className="text-xs opacity-80">{card.label}</p>
            </div>
            <p className="text-2xl font-bold mt-2">{card.value}</p>
          </div>
        ))}
      </div>

      {/* Tab 切换 */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('my')}
          className={`px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${activeTab === 'my' ? 'bg-white border-b-2 border-purple-600 text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
        >
          我的模板 ({stats?.templates?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('top')}
          className={`px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${activeTab === 'top' ? 'bg-white border-b-2 border-amber-600 text-amber-600' : 'text-gray-500 hover:text-gray-700'}`}
        >
          热门创作者 ({topCreators.length})
        </button>
      </div>

      {/* 我的模板 */}
      {activeTab === 'my' && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {(!stats?.templates || stats.templates.length === 0) ? (
            <div className="p-8 text-center">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">暂无模板</p>
              <p className="text-sm text-gray-400 mt-1">上传第一个模板，开启创作者之路</p>
              <button className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-xl text-sm font-medium hover:bg-purple-700 transition-colors">
                去上传模板
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 font-medium">模板名称</th>
                    <th className="px-4 py-3 font-medium">分类</th>
                    <th className="px-4 py-3 font-medium">定价</th>
                    <th className="px-4 py-3 font-medium">销量</th>
                    <th className="px-4 py-3 font-medium">收益</th>
                    <th className="px-4 py-3 font-medium">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.templates.map((tpl, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium">{tpl.name}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">
                          {tpl.category || '未分类'}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-semibold">¥{tpl.price || 0}</td>
                      <td className="px-4 py-3">{tpl.sales || 0}</td>
                      <td className="px-4 py-3 text-emerald-600 font-medium">¥{((tpl.price || 0) * (tpl.sales || 0) * 0.7).toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${tpl.active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                          {tpl.active ? '上架中' : '已下架'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 热门创作者 */}
      {activeTab === 'top' && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {topCreators.length === 0 ? (
            <div className="p-8 text-center">
              <Award className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">暂无创作者数据</p>
              <p className="text-sm text-gray-400 mt-1">成为第一个上传模板的创作者</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {topCreators.map((creator, i) => (
                <div key={i} className="p-4 hover:bg-gray-50 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white ${
                      i === 0 ? 'bg-gradient-to-br from-amber-400 to-orange-500' :
                      i === 1 ? 'bg-gradient-to-br from-gray-300 to-gray-400' :
                      i === 2 ? 'bg-gradient-to-br from-amber-600 to-amber-700' :
                      'bg-gradient-to-br from-purple-400 to-indigo-500'
                    }`}>
                      {(creator.nickname || creator.username || 'U')[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{creator.nickname || creator.username}</p>
                      <p className="text-xs text-gray-500">{creator.template_count} 个模板 · {creator.total_sales} 次销售</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-emerald-600">¥{creator.total_revenue.toFixed(2)}</p>
                    <p className="text-xs text-gray-400">累计收益</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 收益说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
        <h4 className="font-medium text-blue-900 flex items-center gap-2">
          <DollarSign className="w-4 h-4" />
          收益说明
        </h4>
        <ul className="mt-2 text-sm text-blue-700 space-y-1">
          <li>• 模板售价的 70% 归创作者所有</li>
          <li>• 平台收取 30% 技术服务费</li>
          <li>• 收益可按月提现至支付宝或微信</li>
          <li>• 销量统计每日更新，收益实时可见</li>
        </ul>
      </div>
    </div>
  )
}
