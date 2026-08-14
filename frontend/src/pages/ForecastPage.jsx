import React, { useState, useRef, useEffect } from 'react'
import {
  Upload,
  BarChart3,
  TrendingUp,
  Download,
  Trash2,
  Clock,
  Sparkles,
  FileText,
  Eye,
  Copy,
  RefreshCw,
  Settings2,
} from 'lucide-react'
import { Card, Button, Empty, PageHeader, Badge, Pagination } from '../components/ui'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import useAsyncTask from '../hooks/useAsyncTask'
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

export default function ForecastPage() {
  const toast = useToast()
  const { submitTask } = useAsyncTask()
  const fileRef = useRef(null)

  const [uploading, setUploading] = useState(false)
  const [task, setTask] = useState(null)
  const [dataInfo, setDataInfo] = useState(null)
  const [result, setResult] = useState(null)
  const [records, setRecords] = useState([])
  const [targetColumn, setTargetColumn] = useState('')
  const [periods, setPeriods] = useState(3)

  useEffect(() => {
    loadRecords()
  }, [])

  const loadRecords = async () => {
    try {
      const res = await api.get('/api/forecast/records')
      setRecords(res.data || [])
    } catch {
      /* 静默失败，不阻塞 UI */
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/forecast/upload', form)
      setDataInfo(res.data)
      toast.success(`解析成功，${res.data.row_count} 行数据`)
    } catch (err) {
      toast.error(`上传失败：${err.response?.data?.detail || err.message}`)
    }
    setUploading(false)
  }

  const handleAnalyze = async () => {
    if (!dataInfo?.data_id || task) return
    await submitTask(
      '/api/forecast/analyze',
      {
        data_id: dataInfo.data_id,
        target_column: targetColumn,
        forecast_periods: periods,
      },
      {
        onUpdate: (t) => setTask(t),
        onSuccess: (data) => {
          setResult(data)
          setTask(null)
          loadRecords()
          toast.success('预测分析完成')
        },
        onError: (err) => {
          setTask(null)
          toast.error(`分析失败：${err.message}`)
        },
      }
    )
  }

  const deleteRecord = async (id) => {
    try {
      await api.delete(`/api/forecast/records/${id}`)
      loadRecords()
      toast.success('已删除')
    } catch (err) {
      toast.error(err.message)
    }
  }

  // 结果 → Markdown 报告（导出/复制/分享复用同一份内容）
  const buildReportMd = (res) => {
    if (!res) return ''
    const lines = [
      '# AI 数据预测报告',
      '',
      `> 数据：${res.overview?.record_count || '-'} 条记录 · ${res.overview?.columns?.length || '-'} 列 · 预测方法：${res.predictions?.method || '-'}`,
      '',
      '## 数据概览',
      '',
      res.overview?.summary || '-',
      '',
    ]
    if (res.trend_analysis) {
      lines.push('## 趋势分析', '')
      lines.push(`- 整体趋势：${res.trend_analysis.overall_trend || '-'}`)
      if (res.trend_analysis.seasonal_patterns) {
        lines.push(`- 季节性：${res.trend_analysis.seasonal_patterns}`)
      }
      ;(res.trend_analysis.key_findings || []).forEach((f) => lines.push(`- 发现：${f}`))
      lines.push('')
    }
    if (res.predictions?.forecast_values?.length) {
      lines.push('## 预测结果', '')
      lines.push('| 周期 | 预测值 | 区间 |')
      lines.push('|---|---|---|')
      res.predictions.forecast_values.forEach((fv) => {
        lines.push(`| ${fv.period} | ${fv.value?.toLocaleString?.() || fv.value} | ${fv.low} ~ ${fv.high} |`)
      })
      lines.push('')
    }
    if (res.method_explanation) {
      lines.push('## 模型选择说明', '')
      lines.push(`- 当前模型：${res.method_explanation.current}`)
      Object.entries(res.method_explanation.info || {}).forEach(([k, v]) => lines.push(`- ${k}：${v}`))
      if (res.method_explanation.alternatives?.length) {
        lines.push('- 备选模型：')
        res.method_explanation.alternatives.forEach((alt) => lines.push(`  - ${alt.name}：${alt['适用场景']}`))
      }
      lines.push('')
    }
    if (res.predictions?.risks?.length) {
      lines.push('### 预测风险', '')
      res.predictions.risks.forEach((r) => lines.push(`- ${r}`))
      lines.push('')
    }
    if (res.recommendations?.length) {
      lines.push('## 行动建议', '')
      res.recommendations.forEach((r) => {
        lines.push(`- **[${r.level || r.priority}]** ${r.action}${r.expected_impact ? `（预期：${r.expected_impact}）` : ''}`)
      })
      lines.push('')
    }
    lines.push('---', '由小团智能平台 AI 数据预测生成', new Date().toLocaleString())
    return lines.join('\n')
  }

  const downloadReport = () => {
    const md = buildReportMd(result)
    if (!md) return
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `预测报告_${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('报告已导出')
  }

  const copyReport = async () => {
    const md = buildReportMd(result)
    if (!md) return
    try {
      await navigator.clipboard.writeText(md)
      toast.success('报告已复制，可直接粘贴到文档/微信')
    } catch {
      toast.error('复制失败，请手动选择复制')
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI数据预测"
        description="上传CSV数据 → 统计分析 + AI趋势预测 + 智能建议，驱动数据决策"
        icon={TrendingUp}
        iconColor="from-emerald-500 to-teal-600"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左：上传 */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Upload className="w-4 h-4 text-emerald-500" /> 上传数据
            </h3>
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              onChange={handleUpload}
              className="hidden"
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full py-12 border-2 border-dashed border-gray-300 rounded-xl hover:border-emerald-400 hover:bg-emerald-50/30 transition-all flex flex-col items-center gap-3"
            >
              <BarChart3 className="w-10 h-10 text-gray-400" />
              <div className="text-sm text-gray-500">
                {uploading ? '解析中...' : '点击上传 CSV 文件'}
              </div>
              <div className="text-xs text-gray-400">支持 .csv 格式</div>
            </button>

            {dataInfo && (
              <div className="mt-4 p-3 bg-emerald-50 rounded-lg space-y-2 text-sm">
                <div className="font-medium text-emerald-800">{dataInfo.filename}</div>
                <div className="text-xs text-emerald-600">
                  {dataInfo.row_count} 行 · {dataInfo.columns?.length} 列
                </div>
                {dataInfo.numeric_columns?.length > 0 && (
                  <div>
                    <label className="text-xs text-gray-500">预测目标列：</label>
                    <select
                      value={targetColumn}
                      onChange={(e) => setTargetColumn(e.target.value)}
                      className="w-full mt-1 px-2 py-1.5 border border-emerald-200 rounded-lg text-xs"
                    >
                      <option value="">自动选择</option>
                      {dataInfo.numeric_columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className="text-xs text-gray-500">预测期数：{periods} 期</label>
                  <input
                    type="range"
                    min={1}
                    max={12}
                    value={periods}
                    onChange={(e) => setPeriods(Number(e.target.value))}
                    className="w-full mt-1 accent-emerald-500"
                  />
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  icon={Sparkles}
                  loading={!!task}
                  onClick={() => handleAnalyze()}
                  className="w-full mt-2"
                >
                  开始预测分析
                </Button>
                {task && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>{task.stage || 'AI 分析中…'}</span>
                      <span>{task.progress || 0}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-300"
                        style={{ width: `${task.progress || 0}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>

          {dataInfo?.sample && (
            <Card>
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <Eye className="w-4 h-4 text-gray-500" /> 数据预览
              </h3>
              <div className="overflow-x-auto max-h-60">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {dataInfo.columns?.slice(0, 5).map((c) => (
                        <th
                          key={c}
                          className="px-2 py-1 text-left bg-gray-50 font-medium text-gray-600 border-b"
                        >
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dataInfo.sample.slice(0, 5).map((row, i) => (
                      <tr key={i}>
                        {dataInfo.columns?.slice(0, 5).map((c) => (
                          <td key={c} className="px-2 py-1 border-b border-gray-50 text-gray-500">
                            {row[c]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <Card>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-500" /> 历史记录（{records.length}）
            </h3>
            <Pagination
              items={records}
              pageSize={6}
              gridClass="grid grid-cols-1 gap-1.5"
              emptyComponent={
                <div className="text-xs text-gray-400 text-center py-4">暂无记录</div>
              }
              renderItem={(r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between p-2 rounded-lg bg-gray-50 text-xs"
                >
                  <div>
                    <div className="font-medium text-gray-700">{r.filename}</div>
                    <div className="text-gray-400">
                      {r.row_count}行 · {r.created_at?.slice(0, 10)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge color={r.status === 'done' ? 'green' : 'gray'}>
                      {r.status === 'done' ? '已分析' : '已上传'}
                    </Badge>
                    <button
                      onClick={() => deleteRecord(r.id)}
                      className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                      title="删除记录"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            />
          </Card>
        </div>

        {/* 右侧：结果 */}
        <div className="lg:col-span-2 space-y-4">
          {task ? (
            <Card className="border-emerald-200">
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <Sparkles className="w-5 h-5 text-emerald-500 animate-pulse" />
                <span>{task.stage || 'AI 正在分析数据…'}</span>
                <span className="text-gray-400 ml-auto">{task.progress || 0}%</span>
              </div>
            </Card>
          ) : !result ? (
            <Empty
              icon={TrendingUp}
              title="等待分析"
              description="上传CSV数据后点击「开始预测分析」"
            />
          ) : (
            <>
              <Card className="border-emerald-200">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-500" /> 数据概览
                  </h3>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => handleAnalyze()}>
                      重新分析
                    </Button>
                    <Button variant="ghost" size="sm" icon={Download} onClick={downloadReport}>
                      导出报告
                    </Button>
                    <Button variant="ghost" size="sm" icon={Copy} onClick={copyReport}>
                      复制
                    </Button>
                    <ShareButton
                      content={buildReportMd(result)}
                      title="AI 数据预测报告"
                      contentType="data_forecast"
                    />
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div className="p-3 bg-emerald-50 rounded-lg text-center">
                    <div className="text-2xl font-bold text-emerald-600">
                      {result.overview?.record_count}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">记录数</div>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-lg text-center">
                    <div className="text-lg font-bold text-blue-600">
                      {result.overview?.columns?.length || '-'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">列数</div>
                  </div>
                  <div className="p-3 bg-amber-50 rounded-lg text-center">
                    <div className="text-lg font-bold text-amber-600">
                      {result.predictions?.method || '-'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">预测方法</div>
                  </div>
                  <div className="p-3 bg-purple-50 rounded-lg text-center">
                    <div className="text-lg font-bold text-purple-600">
                      {result.overview?.data_quality || '-'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">数据质量</div>
                  </div>
                </div>
                <p className="mt-3 text-sm text-gray-600">{result.overview?.summary}</p>
              </Card>

              {/* 趋势图表 */}
              {result.charts?.labels?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-emerald-500" /> 趋势可视化
                  </h3>
                  <ResponsiveContainer width="100%" height={320}>
                    <ComposedChart
                      data={result.charts.labels.map((label, i) => ({
                        name: label,
                        实际值: result.charts.actual?.[i] ?? null,
                        预测值: result.charts.forecast?.[i] ?? null,
                        趋势线: result.charts.trend_line?.[i] ?? null,
                        预测区间: [
                          result.charts.lower_bound?.[i] ?? null,
                          result.charts.upper_bound?.[i] ?? null,
                        ],
                      }))}
                      margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="预测区间"
                        stroke="none"
                        fill="rgba(245,158,11,0.14)"
                        connectNulls={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="实际值"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        connectNulls={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="预测值"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        strokeDasharray="6 3"
                        dot={{ r: 4 }}
                        connectNulls={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="趋势线"
                        stroke="#6366f1"
                        strokeWidth={1.5}
                        strokeDasharray="3 3"
                        dot={false}
                        connectNulls={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </Card>
              )}

              {/* 趋势分析 */}
              {result.trend_analysis && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-blue-500" /> 趋势分析
                  </h3>
                  <div className="space-y-3">
                    <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
                      <strong>整体趋势：</strong>
                      {result.trend_analysis.overall_trend}
                    </div>
                    {result.trend_analysis.seasonal_patterns && (
                      <div className="text-sm text-gray-600">
                        <strong>季节性：</strong>
                        {result.trend_analysis.seasonal_patterns}
                      </div>
                    )}
                    {result.trend_analysis.key_findings?.length > 0 && (
                      <div>
                        <div className="text-sm font-medium text-gray-700 mb-1">关键发现：</div>
                        {result.trend_analysis.key_findings.map((f, i) => (
                          <div key={i} className="text-sm text-gray-600 flex gap-2">
                            <span className="text-blue-500">●</span> {f}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </Card>
              )}

              {/* 模型选择说明 */}
              {result.method_explanation && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Settings2 className="w-4 h-4 text-indigo-500" /> 模型选择说明
                  </h3>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm text-gray-500">当前模型：</span>
                    <Badge color="purple">{result.method_explanation.current}</Badge>
                  </div>
                  <div className="space-y-1.5">
                    {Object.entries(result.method_explanation.info || {}).map(([k, v]) => (
                      <div key={k} className="text-sm text-gray-600">
                        <strong className="text-gray-700">{k}：</strong>
                        {v}
                      </div>
                    ))}
                  </div>
                  {result.method_explanation.alternatives?.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <div className="text-sm font-medium text-gray-700 mb-1.5">备选模型：</div>
                      {result.method_explanation.alternatives.map((alt) => (
                        <div key={alt.name} className="text-xs text-gray-500 mb-1">
                          <span className="font-medium text-gray-600">{alt.name}</span>
                          ：{alt['适用场景']}
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              )}

              {/* 预测值 */}
              {result.predictions?.forecast_values?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-amber-500" /> 预测结果
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {result.predictions.forecast_values.map((fv, i) => (
                      <div
                        key={i}
                        className="p-3 bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl text-center border border-amber-200"
                      >
                        <div className="text-xs text-gray-500 mb-1">{fv.period}</div>
                        <div className="text-xl font-bold text-amber-700">
                          {fv.value?.toLocaleString?.() || fv.value}
                        </div>
                        <div className="text-[10px] text-gray-400 mt-0.5">
                          {fv.low} ~ {fv.high}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 text-sm text-gray-600">
                    <strong>短期预测：</strong>
                    {typeof result.predictions.short_term === 'string'
                      ? result.predictions.short_term
                      : result.predictions.short_term?.description}
                    {result.predictions.short_term?.confidence &&
                      `（置信度：${result.predictions.short_term.confidence}）`}
                    <br />
                    <strong>中期预测：</strong>
                    {typeof result.predictions.medium_term === 'string'
                      ? result.predictions.medium_term
                      : result.predictions.medium_term?.description}
                    {result.predictions.medium_term?.confidence &&
                      `（置信度：${result.predictions.medium_term.confidence}）`}
                  </div>
                </Card>
              )}

              {/* 建议 */}
              {result.recommendations?.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Eye className="w-4 h-4 text-emerald-500" /> 行动建议
                  </h3>
                  <div className="space-y-2">
                    {result.recommendations.map((r, i) => (
                      <div
                        key={i}
                        className={`p-3 rounded-lg text-sm ${
                          r.level === '紧急' || r.priority === 1
                            ? 'bg-red-50 text-red-800'
                            : r.level === '重要' || r.priority === 2
                              ? 'bg-amber-50 text-amber-800'
                              : 'bg-gray-50 text-gray-700'
                        }`}
                      >
                        <strong>[{r.level || r.priority}]</strong> {r.action}
                        {r.expected_impact && (
                          <div className="text-xs mt-0.5 opacity-70">
                            预期效果：{r.expected_impact}
                          </div>
                        )}
                        {r.timeline && (
                          <div className="text-xs mt-0.5 opacity-50">建议时间：{r.timeline}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
