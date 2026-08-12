import React, { useState, useEffect } from 'react'
import { Users, Gift, Clock, TrendingUp, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'

const REWARD_TYPE_LABELS = {
  invite: '邀请奖励',
  share: '分享奖励',
  bonus: '额外奖励',
}

export default function InviteHistoryPage() {
  const [history, setHistory] = useState([])
  const [rewards, setRewards] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('history') // history | rewards

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [hRes, rRes] = await Promise.all([
        api.get('/api/invite/history'),
        api.get('/api/invite/rewards'),
      ])
      setHistory(hRes.data?.history || [])
      setRewards(rRes.data?.rewards || [])
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

  const totalInvited = history.length
  const totalRewardAmount = rewards.reduce((s, r) => s + r.amount, 0)

  return (
    <div className="space-y-6">
      {/* 概览卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '已邀请人数', value: totalInvited, icon: Users, color: 'from-purple-500 to-indigo-500' },
          { label: '总奖励额度', value: `${totalRewardAmount} 次`, icon: Gift, color: 'from-emerald-500 to-teal-500' },
          { label: '每邀请奖励', value: '5 次', icon: TrendingUp, color: 'from-blue-500 to-cyan-500' },
          { label: '历史记录', value: history.length + rewards.length, icon: Clock, color: 'from-amber-500 to-orange-500' },
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
          onClick={() => setTab('history')}
          className={`px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${tab === 'history' ? 'bg-white border-b-2 border-purple-600 text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
        >
          邀请历史 ({history.length})
        </button>
        <button
          onClick={() => setTab('rewards')}
          className={`px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${tab === 'rewards' ? 'bg-white border-b-2 border-emerald-600 text-emerald-600' : 'text-gray-500 hover:text-gray-700'}`}
        >
          奖励流水 ({rewards.length})
        </button>
      </div>

      {/* 邀请历史 */}
      {tab === 'history' && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {history.length === 0 ? (
            <div className="p-8 text-center">
              <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">暂无邀请记录</p>
              <p className="text-sm text-gray-400 mt-1">邀请好友注册，双方各得 5 次额度奖励</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 font-medium">被邀请人</th>
                    <th className="px-4 py-3 font-medium">注册时间</th>
                    <th className="px-4 py-3 font-medium">邀请码</th>
                    <th className="px-4 py-3 font-medium">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium">{item.invitee_name || item.invitee_id}</td>
                      <td className="px-4 py-3 text-gray-600">{item.joined_at ? new Date(item.joined_at).toLocaleDateString() : '-'}</td>
                      <td className="px-4 py-3 font-mono text-xs">{item.invite_code}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-100 text-emerald-700">
                          {item.status === 'completed' ? '已完成' : item.status}
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

      {/* 奖励流水 */}
      {tab === 'rewards' && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {rewards.length === 0 ? (
            <div className="p-8 text-center">
              <Gift className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">暂无奖励记录</p>
              <p className="text-sm text-gray-400 mt-1">完成邀请或分享后将获得额度奖励</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 font-medium">类型</th>
                    <th className="px-4 py-3 font-medium">额度</th>
                    <th className="px-4 py-3 font-medium">来源</th>
                    <th className="px-4 py-3 font-medium">说明</th>
                    <th className="px-4 py-3 font-medium">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {rewards.map((item, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-purple-100 text-purple-700">
                          {REWARD_TYPE_LABELS[item.reward_type] || item.reward_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-semibold text-emerald-600">+{item.amount} 次</td>
                      <td className="px-4 py-3 text-gray-600">{item.source}</td>
                      <td className="px-4 py-3 text-gray-600">{item.description}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{new Date(item.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
