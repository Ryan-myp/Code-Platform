import React, { useState } from 'react'
import useToolHistory from '../hooks/useToolHistory'
import HistoryPanel from '../components/HistoryPanel'
import {
  Search,
  Gauge,
  TrendingUp,
  FileText,
  Lightbulb,
  Loader2,
  Download,
  Copy,
  Target,
  Layers,
  HelpCircle,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PRIORITY_COLORS = {
  P1: 'bg-red-50 border-red-200 text-red-600',
  P2: 'bg-amber-50 border-amber-200 text-amber-600',
  P3: 'bg-gray-50 border-gray-200 text-gray-500',
}

const COMPETITION_COLORS = {
  高: 'bg-red-50 text-red-600',
  中: 'bg-amber-50 text-amber-600',
  低: 'bg-emerald-50 text-emerald-600',
}

const DIFFICULTY_COLORS = {
  高: 'bg-red-50 text-red-600',
  中: 'bg-amber-50 text-amber-600',
  低: 'bg-emerald-50 text-emerald-600',
}

export default function SEOAnalyzerPage() {
  const toast = useToast()
  const [tab, setTab] = useState('analyze')

  // SEO 评分表单
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [keyword, setKeyword] = useState('')
  const [analyzeLoading, setAnalyzeLoading] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState(null)
  const { history: seoHistory, add: addSeoHistory, remove: removeSeoHistory, clear: clearSeoHistory } =
    useToolHistory('seo_analyzer_history_v1', 20)

  // 关键词研究表单
  const [seedKeyword, setSeedKeyword] = useState('')
  const [industry, setIndustry] = useState('')
  const [kwLoading, setKwLoading] = useState(false)
  const [kwResult, setKwResult] = useState(null)

  const handleAnalyze = async () => {
    if (!title.trim()) {
      toast.error('请输入文章标题')
      return
    }
    if (!content.trim() || content.length < 50) {
      toast.error('文章内容至少 50 字')
      return
    }
    setAnalyzeLoading(true)
    setAnalyzeResult(null)
    try {
      const res = await api.post('/api/seo/analyze', {
        title: title.trim(),
        content: content.trim(),
        target_keyword: keyword.trim(),
      })
      setAnalyzeResult(res.data)
      addSeoHistory({ type: 'SEO', title, keyword, content: `${title} · ${keyword}` })
    } catch (e) {
      toast.error(e.message)
    } finally {
      setAnalyzeLoading(false)
    }
  }

  const handleKeywords = async () => {
    if (!seedKeyword.trim()) {
      toast.error('请输入种子词')
      return
    }
    setKwLoading(true)
    setKwResult(null)
    try {
      const res = await api.post('/api/seo/keywords', {
        seed_keyword: seedKeyword.trim(),
        industry: industry.trim(),
        language: 'zh',
      })
      setKwResult(res.data)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setKwLoading(false)
    }
  }

  const buildAnalyzeMd = (r) => {
    if (!r) return ''
    const lines = [
      `# SEO 内容诊断报告：${r.title}`,
      '',
      `- 综合评分：${r.overall_score}（${r.grade}）`,
      `- 内容长度：${r.content_length} 字`,
      `- 核心关键词：${r.keyword_analysis?.primary_keyword || keyword || '未指定'}`,
      '',
      `> ${r.summary || ''}`,
      '',
      '## 分维度评分',
      '',
      '| 维度 | 得分 | 权重 | 依据 |',
      '|------|------|------|------|',
    ]
    ;(r.dimensions || []).forEach((d) => lines.push(`| ${d.name} | ${d.score} | ${d.weight}% | ${(d.evidence || '').slice(0, 60)} |`))
    lines.push('', '## 优化建议')
    ;(r.improvements || []).forEach((imp, i) => {
      lines.push(`${i + 1}. **[${imp.priority.toUpperCase()}]** ${imp.issue}`)
      lines.push(`   - 影响：${imp.impact}`)
      lines.push(`   - 建议：${imp.suggestion}`)
    })
    if (r.optimized_title_suggestions?.length) {
      lines.push('', '## 优化标题建议')
      r.optimized_title_suggestions.forEach((t, i) => lines.push(`${i + 1}. ${t}`))
    }
    if (r.meta_description) {
      lines.push('', '## Meta 描述', '', r.meta_description)
    }
    return lines.join('\n')
  }

  const buildKeywordsMd = (r) => {
    if (!r) return ''
    const lines = [
      `# 关键词研究报告：${r.seed_keyword}`,
      '',
      `> ${r.content_suggestions || ''}`,
      '',
      '## 优先级矩阵',
      '',
      '| 关键词 | 相关度 | 竞争度 | 难度 | 优先级 | 建议 |',
      '|--------|--------|--------|------|--------|------|',
    ]
    ;(r.priority_matrix || []).forEach((m) =>
      lines.push(`| ${m.keyword} | ${m.relevance} | ${m.competition} | ${m.difficulty} | ${m.priority} | ${m.action} |`)
    )
    if (r.related_keywords?.length) {
      lines.push('', '## 相关关键词')
      r.related_keywords.forEach((k) =>
        lines.push(`- ${k.keyword}（搜索量:${k.search_volume} / 竞争:${k.competition} / 相关度:${k.relevance}）`)
      )
    }
    if (r.long_tail_keywords?.length) {
      lines.push('', '## 长尾关键词')
      r.long_tail_keywords.forEach((k) => lines.push(`- ${k.keyword}（意图:${k.intent} / 难度:${k.difficulty}）`))
    }
    if (r.question_keywords?.length) {
      lines.push('', '## 问题型关键词')
      r.question_keywords.forEach((k) => lines.push(`- ${k.question}（${k.question_type}）→ ${k.answer_brief}`))
    }
    if (r.topic_clusters?.length) {
      lines.push('', '## 主题簇')
      r.topic_clusters.forEach((c) => lines.push(`- **${c.cluster}**：${(c.keywords || []).join('、')}`))
    }
    return lines.join('\n')
  }

  const downloadMd = (text, filename) => {
    if (!text) return
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    toast.success('报告已导出')
  }

  const copyText = async (text) => {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      toast.success('已复制')
    } catch {
      toast.error('复制失败，请手动复制')
    }
  }

  const gradeColor = (score) => (score >= 80 ? 'text-emerald-600' : score >= 70 ? 'text-amber-600' : 'text-red-500')

  return (
    <div className="space-y-6">
      <PageHeader
        title="SEO 分析"
        description="内容 SEO 综合评分 + 关键词研究（分组/难度分级/优先级矩阵）"
        icon={Gauge}
        iconColor="from-emerald-500 to-teal-600"
      />

      <div className="flex gap-2">
        {[
          { key: 'analyze', label: '内容评分', icon: Gauge },
          { key: 'keywords', label: '关键词研究', icon: Search },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-xl text-sm flex items-center gap-2 transition-all ${
              tab === t.key
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium'
                : 'bg-gray-50 text-gray-500 border border-gray-100 hover:bg-gray-100'
            }`}
          >
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'analyze' ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <FileText className="w-4 h-4 text-emerald-500" /> 输入内容
              </h3>
              <div className="space-y-3">
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="文章标题"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                />
                <input
                  type="text"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="目标关键词（可选）"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                />
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="粘贴文章正文（至少 50 字）..."
                  rows={12}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none resize-y"
                />
                <Button
                  variant="primary"
                  icon={analyzeLoading ? Loader2 : Gauge}
                  loading={analyzeLoading}
                  onClick={handleAnalyze}
                  className="w-full"
                >
                  开始诊断
                </Button>
              </div>
            </Card>
          </div>

          <div className="lg:col-span-2 space-y-4">
            {analyzeLoading ? (
              <Card>
                <div className="flex items-center gap-3 text-sm text-gray-600">
                  <Loader2 className="w-5 h-5 text-emerald-500 animate-spin" />
                  <span>AI 正在多维度诊断内容 SEO…</span>
                </div>
              </Card>
            ) : !analyzeResult ? (
              <Empty
                icon={Gauge}
                title="输入内容开始诊断"
                description="从标题/关键词/结构/可读性等 8 个维度综合评分，并给出可执行优化建议"
              />
            ) : (
              <>
                <Card>
                  <div className="flex items-center gap-6 flex-wrap">
                    <div className="text-center">
                      <div className={`text-5xl font-bold ${gradeColor(analyzeResult.overall_score)}`}>
                        {analyzeResult.overall_score}
                      </div>
                      <Badge color={analyzeResult.overall_score >= 80 ? 'green' : analyzeResult.overall_score >= 70 ? 'yellow' : 'red'}>
                        {analyzeResult.grade}
                      </Badge>
                    </div>
                    <div className="flex-1 min-w-[200px]">
                      <div className="text-sm text-gray-700">{analyzeResult.summary}</div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        {analyzeResult.keyword_analysis && (
                          <>
                            <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg">
                              核心词：{analyzeResult.keyword_analysis.primary_keyword || keyword}
                            </span>
                            <span className="px-2 py-1 bg-gray-50 text-gray-600 rounded-lg">
                              密度：{analyzeResult.keyword_analysis.density}
                            </span>
                            {analyzeResult.keyword_analysis.appears_in_title === false && (
                              <span className="px-2 py-1 bg-red-50 text-red-600 rounded-lg">标题未含核心词</span>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col gap-2">
                      <Button variant="ghost" size="sm" icon={Download} onClick={() => downloadMd(buildAnalyzeMd(analyzeResult), `SEO诊断_${Date.now()}.md`)}>
                        导出报告
                      </Button>
                      <Button variant="ghost" size="sm" icon={Copy} onClick={() => copyText(buildAnalyzeMd(analyzeResult))}>
                        复制报告
                      </Button>
                    </div>
                  </div>
                </Card>

                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3">分维度评分</h3>
                  <div className="space-y-3">
                    {(analyzeResult.dimensions || []).map((d, i) => (
                      <div key={i}>
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span className="text-gray-700">
                            {d.name}
                            <span className="text-gray-400 text-xs ml-2">权重 {d.weight}%</span>
                          </span>
                          <span className={`font-semibold ${d.score >= 80 ? 'text-emerald-600' : d.score >= 70 ? 'text-amber-600' : 'text-red-500'}`}>
                            {d.score}
                          </span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${d.score >= 80 ? 'bg-emerald-500' : d.score >= 70 ? 'bg-amber-500' : 'bg-red-400'}`}
                            style={{ width: `${d.score}%` }}
                          />
                        </div>
                        {d.evidence && <div className="mt-1 text-xs text-gray-400">{d.evidence}</div>}
                      </div>
                    ))}
                  </div>
                </Card>

                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-amber-500" /> 优化建议
                  </h3>
                  <div className="space-y-2">
                    {(analyzeResult.improvements || []).map((imp, i) => (
                      <div key={i} className="p-3 rounded-xl bg-gray-50">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge color={imp.priority === 'high' ? 'red' : imp.priority === 'medium' ? 'yellow' : 'gray'}>
                            {imp.priority}
                          </Badge>
                          <span className="text-sm font-medium text-gray-800">{imp.issue}</span>
                        </div>
                        <div className="text-xs text-gray-500">影响：{imp.impact}</div>
                        <div className="text-xs text-gray-600 mt-1">建议：{imp.suggestion}</div>
                      </div>
                    ))}
                  </div>
                </Card>

                {analyzeResult.optimized_title_suggestions?.length > 0 && (
                  <Card>
                    <h3 className="font-semibold text-gray-900 mb-2">优化标题建议</h3>
                    <div className="space-y-1.5">
                      {analyzeResult.optimized_title_suggestions.map((t, i) => (
                        <div key={i} className="text-sm text-gray-700 bg-gray-50 p-2.5 rounded-lg">✓ {t}</div>
                      ))}
                    </div>
                  </Card>
                )}
              </>
            )}
            {seoHistory.length > 0 && (
              <HistoryPanel
                history={seoHistory}
                onReuse={(item) => {
                  if (item.title) setTitle(item.title)
                  if (item.keyword) setKeyword(item.keyword)
                  toast.success('已恢复SEO内容，可重新分析')
                }}
                onRemove={removeSeoHistory}
                onClear={clearSeoHistory}
                title="分析历史"
              />
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-4">
            <Card>
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Search className="w-4 h-4 text-emerald-500" /> 种子词研究
              </h3>
              <div className="space-y-3">
                <input
                  type="text"
                  value={seedKeyword}
                  onChange={(e) => setSeedKeyword(e.target.value)}
                  placeholder="种子词/主题，如：AI写作"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                />
                <input
                  type="text"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  placeholder="行业/领域（可选）"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                />
                <Button
                  variant="primary"
                  icon={kwLoading ? Loader2 : Search}
                  loading={kwLoading}
                  onClick={handleKeywords}
                  className="w-full"
                >
                  研究关键词
                </Button>
              </div>
            </Card>
            <Card>
              <h3 className="font-semibold text-gray-900 mb-2 text-sm">研究维度</h3>
              <div className="space-y-2 text-xs text-gray-500">
                <div className="flex items-center gap-2"><Target className="w-3.5 h-3.5 text-emerald-500" /> 相关关键词（搜索量/竞争度/相关度）</div>
                <div className="flex items-center gap-2"><TrendingUp className="w-3.5 h-3.5 text-emerald-500" /> 长尾关键词（意图/难度分级）</div>
                <div className="flex items-center gap-2"><HelpCircle className="w-3.5 h-3.5 text-emerald-500" /> 问题型关键词（5 类问句）</div>
                <div className="flex items-center gap-2"><Layers className="w-3.5 h-3.5 text-emerald-500" /> 主题簇（Pillar-Cluster 策略）</div>
                <div className="flex items-center gap-2"><Gauge className="w-3.5 h-3.5 text-emerald-500" /> 优先级矩阵（P1-P3 执行排序）</div>
              </div>
            </Card>
          </div>

          <div className="lg:col-span-2 space-y-4">
            {kwLoading ? (
              <Card>
                <div className="flex items-center gap-3 text-sm text-gray-600">
                  <Loader2 className="w-5 h-5 text-emerald-500 animate-spin" />
                  <span>AI 正在构建关键词矩阵…</span>
                </div>
              </Card>
            ) : !kwResult ? (
              <Empty
                icon={Search}
                title="输入种子词开始研究"
                description="输出关键词分组、难度分级与优先级矩阵，直接指导内容排期"
              />
            ) : (
              <>
                <Card>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                      <Gauge className="w-4 h-4 text-emerald-500" /> 优先级矩阵（执行排序）
                    </h3>
                    <div className="flex gap-2">
                      <Button variant="ghost" size="sm" icon={Download} onClick={() => downloadMd(buildKeywordsMd(kwResult), `关键词研究_${kwResult.seed_keyword}.md`)}>
                        导出报告
                      </Button>
                      <Button variant="ghost" size="sm" icon={Copy} onClick={() => copyText(buildKeywordsMd(kwResult))}>
                        复制
                      </Button>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                          <th className="py-2 pr-3 font-medium">关键词</th>
                          <th className="py-2 pr-3 font-medium">相关度</th>
                          <th className="py-2 pr-3 font-medium">竞争度</th>
                          <th className="py-2 pr-3 font-medium">难度</th>
                          <th className="py-2 pr-3 font-medium">优先级</th>
                          <th className="py-2 font-medium">建议</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(kwResult.priority_matrix || []).map((m, i) => (
                          <tr key={i} className="border-b border-gray-50">
                            <td className="py-2 pr-3 font-medium text-gray-800">{m.keyword}</td>
                            <td className="py-2 pr-3 text-gray-500">{m.relevance}</td>
                            <td className="py-2 pr-3">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] ${COMPETITION_COLORS[m.competition] || 'bg-gray-50 text-gray-500'}`}>
                                {m.competition}
                              </span>
                            </td>
                            <td className="py-2 pr-3">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] ${DIFFICULTY_COLORS[m.difficulty] || 'bg-gray-50 text-gray-500'}`}>
                                {m.difficulty}
                              </span>
                            </td>
                            <td className="py-2 pr-3">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${PRIORITY_COLORS[m.priority] || ''}`}>
                                {m.priority}
                              </span>
                            </td>
                            <td className="py-2 text-xs text-gray-500">{m.action}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card>
                    <h3 className="font-semibold text-gray-900 mb-3 text-sm">相关关键词</h3>
                    <div className="space-y-2">
                      {(kwResult.related_keywords || []).map((k, i) => (
                        <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
                          <span className="text-sm text-gray-700">{k.keyword}</span>
                          <div className="flex gap-1">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] ${COMPETITION_COLORS[k.competition] || 'bg-gray-50'}`}>
                              {k.competition}
                            </span>
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500">
                              量:{k.search_volume} · 相关度:{k.relevance}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>

                  <Card>
                    <h3 className="font-semibold text-gray-900 mb-3 text-sm">长尾关键词</h3>
                    <div className="space-y-2">
                      {(kwResult.long_tail_keywords || []).map((k, i) => (
                        <div key={i} className="p-2.5 bg-gray-50 rounded-lg">
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-700">{k.keyword}</span>
                            <span className={`px-1.5 py-0.5 rounded text-[10px] ${DIFFICULTY_COLORS[k.difficulty] || 'bg-gray-50'}`}>
                              {k.difficulty}
                            </span>
                          </div>
                          <div className="text-xs text-gray-400 mt-0.5">意图：{k.intent}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>

                {kwResult.question_keywords?.length > 0 && (
                  <Card>
                    <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                      <HelpCircle className="w-4 h-4 text-emerald-500" /> 问题型关键词
                    </h3>
                    <div className="space-y-2">
                      {kwResult.question_keywords.map((k, i) => (
                        <div key={i} className="p-2.5 bg-gray-50 rounded-lg">
                          <span className="text-sm text-gray-700">{k.question}</span>
                          <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-600">
                            {k.question_type}
                          </span>
                          <div className="text-xs text-gray-400 mt-0.5">{k.answer_brief}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {kwResult.topic_clusters?.length > 0 && (
                  <Card>
                    <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-emerald-500" /> 主题簇（Pillar-Cluster）
                    </h3>
                    <div className="space-y-2">
                      {kwResult.topic_clusters.map((c, i) => (
                        <div key={i} className="p-3 bg-gray-50 rounded-lg">
                          <span className="text-sm font-medium text-gray-800">🏷 {c.cluster}</span>
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {(c.keywords || []).map((k, j) => (
                              <span key={j} className="px-2 py-0.5 bg-white border border-gray-200 rounded text-xs text-gray-600">
                                {k}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
