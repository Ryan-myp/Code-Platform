import React, { useState, useEffect } from 'react'
import { FlaskConical, Plus, Trash2, Clock, Play, CheckCircle2, Trophy, Loader2, ChevronDown, ChevronUp, TrendingUp, AlertTriangle } from 'lucide-react'
import { Card, Button, Badge, Modal, Empty, PageHeader, ColorBadge } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

// AB 实验目标维度（营销口径，与后端评分维度对应）
const OBJECTIVES = ['整体效果', '标题吸引力', '点击转化率', '用户偏好', '记忆度', '信任感']
const DIMENSIONS = ['吸引力', '清晰度', '转化力', '专业度', '记忆点']

const STATUS_META = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-600' },
  pending: { label: '未运行', color: 'bg-gray-100 text-gray-600' },
  running: { label: '运行中', color: 'bg-amber-100 text-amber-700' },
  completed: { label: '已完成', color: 'bg-emerald-100 text-emerald-700' },
}

function ScoreBar({ label, a, b }) {
  const max = Math.max(a, b, 1)
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-gray-600 font-medium">{label}</span>
        <span className="text-gray-400">
          <span className="text-blue-600 font-semibold">{a}</span> vs{' '}
          <span className="text-emerald-600 font-semibold">{b}</span>
        </span>
      </div>
      <div className="flex gap-1.5">
        <div className="flex-1 h-2 rounded-full bg-ink-100 overflow-hidden">
          <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${(a / max) * 100}%` }} />
        </div>
        <div className="flex-1 h-2 rounded-full bg-ink-100 overflow-hidden">
          <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${(b / max) * 100}%` }} />
        </div>
      </div>
    </div>
  )
}

function ResultPanel({ result, onClose }) {
  const [openGen, setOpenGen] = useState(false)
  if (!result || result.status !== 'completed') {
    return (
      <Card className="p-8 text-center text-gray-400">
        <Loader2 className="w-6 h-6 text-purple-500 animate-spin inline-block mb-2" />
        <p>实验运行中，AI 正在评估方案…请稍候</p>
      </Card>
    )
  }
  const winner = result.winner === 'A'
  return (
    <Card className="space-y-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Trophy className="w-4 h-4 text-amber-500" />
            实验结果：方案 {result.winner} 胜出
            <ColorBadge color={winner ? 'blue' : 'green'}>{`置信度 ${result.confidence}%`}</ColorBadge>
          </h3>
          {result.objective && <p className="text-xs text-gray-400 mt-1">实验目标：{result.objective}</p>}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <Clock className="w-3 h-3" /> {result.ran_at}
          </span>
          <Button variant="ghost" size="sm" onClick={onClose}>收起</Button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-blue-50/60 rounded-xl p-4">
          <p className="text-sm font-semibold text-blue-700 mb-2">方案 A 终稿</p>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{result.generated_a || '（无内容）'}</p>
        </div>
        <div className="bg-emerald-50/60 rounded-xl p-4">
          <p className="text-sm font-semibold text-emerald-700 mb-2">方案 B 终稿</p>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{result.generated_b || '（无内容）'}</p>
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold text-gray-900 mb-3">五维评分对比</p>
        {(result.scores || []).map((s) => (
          <ScoreBar key={s.dimension} label={s.dimension || s.name} a={s.a ?? 0} b={s.b ?? 0} />
        ))}
      </div>

      {result.conclusion && (
        <div className="flex items-start gap-3 bg-brand-50 rounded-xl p-4">
          <CheckCircle2 className="w-5 h-5 text-brand-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-brand-700 mb-1">决策建议</p>
            <p className="text-sm text-gray-700">{result.conclusion}</p>
          </div>
        </div>
      )}

      {/* 分析输出升级：胜出原因 / 风险提示 / 下一步行动 */}
      {result.analysis && (
        <div className="grid md:grid-cols-3 gap-3">
          {result.analysis.winner_reason && (
            <div className="flex items-start gap-2.5 bg-blue-50/60 rounded-xl p-3.5">
              <TrendingUp className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs font-semibold text-blue-700 mb-1">胜出原因</p>
                <p className="text-xs text-gray-600 leading-relaxed">{result.analysis.winner_reason}</p>
              </div>
            </div>
          )}
          {(result.analysis.risks || []).length > 0 && (
            <div className="flex items-start gap-2.5 bg-rose-50/60 rounded-xl p-3.5">
              <AlertTriangle className="w-4 h-4 text-rose-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs font-semibold text-rose-700 mb-1">风险提示</p>
                <ul className="space-y-1">
                  {(result.analysis.risks || []).map((r, i) => (
                    <li key={i} className="text-xs text-gray-600 leading-relaxed">· {r}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          {(result.analysis.next_steps || []).length > 0 && (
            <div className="flex items-start gap-2.5 bg-emerald-50/60 rounded-xl p-3.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs font-semibold text-emerald-700 mb-1">下一步行动</p>
                <ul className="space-y-1">
                  {(result.analysis.next_steps || []).map((n, i) => (
                    <li key={i} className="text-xs text-gray-600 leading-relaxed">· {n}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => setOpenGen(!openGen)}
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
      >
        {openGen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        查看 AI 扩写过程说明
      </button>
      {openGen && (
        <p className="text-xs text-gray-400 leading-relaxed">
          运行方式：AI 以 20 年增长实验专家身份，将 A/B 方案各自扩写为完整终稿，并沿
          「吸引力 / 清晰度 / 转化力 / 专业度 / 记忆点」五个维度独立打分（0-100），
          按总分确定胜出方并给出置信度、胜出原因、风险提示与下一步行动。
          分数为模型评估意见，建议结合真实流量小范围验证。
        </p>
      )}
    </Card>
  )
}

export default function ABTestingPage() {
  const toast = useToast()
  const [tests, setTests] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [runningId, setRunningId] = useState('')
  const [resultMap, setResultMap] = useState({}) // id → result 对象（运行中/已完成）
  const [form, setForm] = useState({ name: '', description: '', objective: '整体效果', variant_a: '', variant_b: '' })

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/ab-tests')
      setTests(res.data || [])
      // 回填已有结果
      const map = {}
      for (const t of res.data || []) {
        if (t.result && t.result.status === 'completed') map[t.id] = t.result
      }
      setResultMap(map)
    } catch (e) {
      toast.error(`加载失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const create = async () => {
    if (!form.name.trim()) {
      toast.error('请输入实验名称')
      return
    }
    if (!form.variant_a.trim() || !form.variant_b.trim()) {
      toast.error('请填写 A/B 两个方案')
      return
    }
    try {
      await api.post('/api/ab-tests', form)
      toast.success('实验已创建')
      setShowModal(false)
      setForm({ name: '', description: '', objective: '整体效果', variant_a: '', variant_b: '' })
      load()
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('确定删除该实验？')) return
    try {
      await api.delete(`/api/ab-tests/${id}`)
      toast.success('已删除')
      load()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const run = async (t) => {
    setRunningId(t.id)
    setResultMap((m) => ({ ...m, [t.id]: { status: 'running' } }))
    try {
      const res = await api.post(`/api/ab-tests/${t.id}/run`, { objective: t.result?.objective || form.objective || '整体效果' })
      setResultMap((m) => ({ ...m, [t.id]: res.data }))
      toast.success(`实验完成：方案 ${res.data.winner} 胜出（置信度 ${res.data.confidence}%）`)
      load()
    } catch (e) {
      toast.error(`运行失败：${e.message}`)
      setResultMap((m) => {
        const next = { ...m }
        delete next[t.id]
        return next
      })
    } finally {
      setRunningId('')
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="A/B 测试"
        description="创建实验 → AI 扩写方案 → 五维评分对比 → 数据化决策"
        icon={FlaskConical}
        iconColor="from-purple-500 to-fuchsia-600"
        actions={
          <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>
            新建实验
          </Button>
        }
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin h-6 w-6 border-b-2 border-brand-500 rounded-full" />
        </div>
      ) : tests.length === 0 ? (
        <Card>
          <Empty icon={FlaskConical} title="暂无实验" description="创建第一个 A/B 测试，让 AI 帮你评估两个方案的优劣" />
        </Card>
      ) : (
        <div className="space-y-4">
          {tests.map((t) => {
            const result = resultMap[t.id]
            const meta = STATUS_META[result?.status === 'running' ? 'running' : result?.status === 'completed' ? 'completed' : 'draft']
            return (
              <div key={t.id} className="space-y-3">
                <Card>
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                        <FlaskConical className="w-5 h-5 text-purple-600" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-gray-900">{t.name}</h3>
                          <Badge className={meta.color}>{meta.label}</Badge>
                          {result?.status === 'completed' && (
                            <Badge className="bg-amber-100 text-amber-700">
                              <Trophy className="w-3 h-3 inline mr-1" />方案 {result.winner} · 置信度 {result.confidence}%
                            </Badge>
                          )}
                        </div>
                        {t.description && <p className="text-sm text-gray-500 mt-1">{t.description}</p>}
                        <div className="flex items-center gap-4 mt-3">
                          <div className="px-3 py-1.5 bg-blue-50 rounded-lg text-sm">
                            <span className="text-blue-600 font-medium">A:</span>{' '}
                            <span className="text-gray-700">{t.variant_a || '未设置'}</span>
                          </div>
                          <span className="text-gray-300">vs</span>
                          <div className="px-3 py-1.5 bg-green-50 rounded-lg text-sm">
                            <span className="text-green-600 font-medium">B:</span>{' '}
                            <span className="text-gray-700">{t.variant_b || '未设置'}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                          <Clock className="w-3 h-3" /> {t.created_at?.slice(0, 16)}
                          {result?.objective && <span>· 目标：{result.objective}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        icon={runningId === t.id ? Loader2 : Play}
                        disabled={runningId === t.id}
                        onClick={() => run(t)}
                      >
                        {runningId === t.id ? '评估中…' : result?.status === 'completed' ? '重新运行' : '运行'}
                      </Button>
                      <Button variant="ghost" size="sm" icon={Trash2} onClick={() => remove(t.id)} />
                    </div>
                  </div>
                </Card>
                {result && (
                  <ResultPanel
                    result={result}
                    onClose={() =>
                      setResultMap((m) => {
                        const next = { ...m }
                        delete next[t.id]
                        return next
                      })
                    }
                  />
                )}
              </div>
            )
          })}
        </div>
      )}

      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title="新建 A/B 测试"
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowModal(false)}>取消</Button>
            <Button variant="primary" onClick={create}>创建实验</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">实验名称 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：首页标题方案对比"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
              placeholder="实验背景与想验证的假设"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">实验目标维度</label>
            <select
              value={form.objective}
              onChange={(e) => setForm({ ...form, objective: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-white"
            >
              {OBJECTIVES.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">方案 A *</label>
            <input
              type="text"
              value={form.variant_a}
              onChange={(e) => setForm({ ...form, variant_a: e.target.value })}
              placeholder="对照组方案描述"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">方案 B *</label>
            <input
              type="text"
              value={form.variant_b}
              onChange={(e) => setForm({ ...form, variant_b: e.target.value })}
              placeholder="实验组方案描述"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <p className="text-xs text-gray-400">
            运行后 AI 将把两个方案扩写为完整终稿，并按{DIMENSIONS.join(' / ')}五个维度评分对比，给出胜出方与置信度。
          </p>
        </div>
      </Modal>
    </div>
  )
}
