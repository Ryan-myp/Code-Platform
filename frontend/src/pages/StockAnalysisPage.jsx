import React, { useState, useEffect, useRef } from 'react'
import { Card, Button, Badge, Empty } from '../components/ui'
import Modal from '../components/ui/Modal'
import ShareButton from '../components/ShareButton'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import MarkdownRenderer from '../components/MarkdownRenderer'
import KLineChart from '../components/KLineChart'
import usePersistentToolState from '../hooks/usePersistentToolState'
import {
  Search,
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  Activity,
  PieChart,
  Play,
  Pause,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Copy,
  Download,
  ShieldAlert,
  AlertTriangle,
  CalendarClock,
  FileText,
  Trash2,
  Clock,
  Webhook,
  Loader2,
} from 'lucide-react'

// v22：热门股票快捷入口（一键直达查询）
const HOT_STOCKS = [
  { symbol: 'AAPL', label: '苹果' },
  { symbol: 'NVDA', label: '英伟达' },
  { symbol: 'MSFT', label: '微软' },
  { symbol: 'TSLA', label: '特斯拉' },
  { symbol: '0700.HK', label: '腾讯' },
  { symbol: '9988.HK', label: '阿里' },
  { symbol: '3690.HK', label: '美团' },
  { symbol: '600519.SS', label: '茅台' },
  { symbol: '300750.SZ', label: '宁德时代' },
  { symbol: '601318.SS', label: '中国平安' },
]

// v22：股票代码智能补全（关键词搜索 → 候选列表 → 自由选择）
export function SymbolAutocomplete({
  value,
  onChange,
  onSelect,
  onEnter,
  placeholder = '搜索股票名称/代码，如 AAPL、苹果、腾讯…',
  compact = false,
}) {
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [searching, setSearching] = useState(false)
  const timerRef = useRef(null)
  const reqIdRef = useRef(0)

  // 300ms 防抖自动补全：≥2 字符触发关键词搜索
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    const q = value.trim()
    if (q.length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      setSearching(false)
      return
    }
    setSearching(true)
    timerRef.current = setTimeout(async () => {
      const reqId = ++reqIdRef.current
      try {
        const res = await api.get(`/api/stock/search?q=${encodeURIComponent(q)}&limit=8`)
        if (reqId !== reqIdRef.current) return
        setSuggestions(res.data?.items || [])
        setShowSuggestions(true)
      } catch {
        if (reqId !== reqIdRef.current) return
        setSuggestions([])
        setShowSuggestions(false)
      } finally {
        if (reqId === reqIdRef.current) setSearching(false)
      }
    }, 300)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [value])

  const pick = (item) => {
    setSuggestions([])
    setShowSuggestions(false)
    onChange(item.symbol.toUpperCase())
    onSelect?.(item.symbol)
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search
          className={`absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 ${compact ? 'w-4 h-4' : ''}`}
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              if (suggestions.length > 0) {
                pick(suggestions[0])
              } else {
                onEnter?.()
              }
            }
          }}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          placeholder={placeholder}
          className={
            compact
              ? 'w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500'
              : 'w-full pl-10 pr-4 py-3 text-lg border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500'
          }
        />
        {searching && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 animate-spin" />
        )}
      </div>
      {showSuggestions && suggestions.length > 0 && (
        <ul
          className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-72 overflow-y-auto"
          data-testid="symbol-suggestions"
        >
          {suggestions.map((item) => (
            <li key={item.symbol}>
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault()
                  pick(item)
                }}
                className="w-full text-left px-3 py-2 hover:bg-brand-50 flex items-center gap-2"
              >
                <span className="font-semibold text-sm">{item.symbol}</span>
                <span className="flex-1 truncate text-sm text-gray-600">{item.name}</span>
                <Badge variant="info">{item.exchange}</Badge>
              </button>
            </li>
          ))}
        </ul>
      )}
      {showSuggestions && suggestions.length === 0 && !searching && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm text-gray-500">
          未找到匹配，请尝试完整代码（如 0700.HK）
        </div>
      )}
    </div>
  )
}

export default function StockAnalysisPage() {
  // 输入态持久化：刷新/关闭不丢股票代码与周期
  const [state, setState] = usePersistentToolState(
    'stock_analysis_input',
    { symbol: '', period: '3mo' },
    { version: 1 }
  )
  const symbol = state.symbol
  const period = state.period
  const setSymbol = (v) => setState((s) => ({ ...s, symbol: v }))
  const setPeriod = (v) => setState((s) => ({ ...s, period: v }))
  const [stockData, setStockData] = useState(null)
  const [analysis, setAnalysis] = useState('')
  const [loading, setLoading] = useState(false)
  const [analysisType] = useState('comprehensive')
  const [portfolio, setPortfolio] = useState(null)
  const [tradeAction, setTradeAction] = useState('buy')
  const [tradeQty, setTradeQty] = useState('')
  const [showTrade, setShowTrade] = useState(false)
  // v21：定时报告 + 历史报告
  const [reports, setReports] = useState(null)
  const [viewReport, setViewReport] = useState(null)
  const [schedSymbol, setSchedSymbol] = useState('')
  const [schedPeriod, setSchedPeriod] = useState('3mo')
  const [schedFreq, setSchedFreq] = useState('0 9 * * *')
  const [creatingSchedule, setCreatingSchedule] = useState(false)
  const toast = useToast()

  useEffect(() => {
    loadPortfolio()
    loadReports()
  }, [])

  // v21：历史报告加载
  const loadReports = async () => {
    try {
      const res = await api.get('/api/stock/reports?limit=20')
      setReports(res.data?.items || [])
    } catch {
      setReports([])
    }
  }

  // v21：创建定时股票分析任务
  const handleCreateSchedule = async () => {
    const sym = (schedSymbol || stockData?.symbol || '').trim().toUpperCase()
    if (!sym) {
      toast.warning('请输入股票代码')
      return
    }
    setCreatingSchedule(true)
    try {
      await api.post('/api/scheduler', {
        name: `每日股票分析：${sym}`,
        description: '定时抓取行情并生成专业分析报告，通过 Webhook 推送',
        job_type: 'stock_report',
        cron_expression: schedFreq,
        config: { symbol: sym, period: schedPeriod, analysis_type: 'comprehensive' },
      })
      toast.success(`已创建定时任务：${sym}（${FREQ_OPTIONS.find((f) => f.cron === schedFreq)?.label}）`)
    } catch (err) {
      toast.error(err.response?.data?.detail || '创建定时任务失败')
    } finally {
      setCreatingSchedule(false)
    }
  }

  // v21：删除历史报告
  const handleDeleteReport = async (r) => {
    if (!confirm(`确定删除 ${r.symbol} 的报告吗？`)) return
    try {
      await api.delete(`/api/stock/reports/${r.id}`)
      toast.success('报告已删除')
      loadReports()
    } catch (err) {
      toast.error(err.response?.data?.detail || '删除失败')
    }
  }

  // v21：定时任务频率预设
  const FREQ_OPTIONS = [
    { label: '每天 9:00 盘前', cron: '0 9 * * *' },
    { label: '每天 17:00 盘后', cron: '0 17 * * *' },
    { label: '每周一 9:00', cron: '0 9 * * 1' },
  ]
  const PERIOD_OPTIONS = [
    { value: '1mo', label: '1个月' },
    { value: '3mo', label: '3个月' },
    { value: '6mo', label: '6个月' },
    { value: '1y', label: '1年' },
    { value: '2y', label: '2年' },
  ]

  const loadPortfolio = async () => {
    try {
      const res = await api.get('/api/trading/portfolio')
      setPortfolio(res.data)
    } catch {
      // ignore
    }
  }

  const handleSearch = async () => {
    if (!symbol.trim()) {
      toast.warning('请输入股票代码')
      return
    }
    await handleSearchFor(symbol)
  }

  // v22：指定代码查询（热门快捷 / 补全候选选择复用）
  const handleSearchFor = async (sym) => {
    const s = String(sym || '').trim().toUpperCase()
    if (!s) return
    setSymbol(s)
    setLoading(true)
    try {
      const res = await api.get(`/api/stock/${s}?period=${period}`)
      setStockData(res.data)
      setAnalysis('')
    } catch (err) {
      toast.error(err.response?.data?.detail || '获取股票数据失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAnalyze = async () => {
    if (!stockData) return
    setLoading(true)
    try {
      const res = await api.post('/api/stock/analyze', {
        symbol: stockData.symbol,
        analysis_type: analysisType,
        period: period,
      })
      setAnalysis(res.data.result)
    } catch (err) {
      toast.error(err.response?.data?.detail || '分析失败')
    } finally {
      setLoading(false)
    }
  }

  const handleTrade = async () => {
    if (!stockData || !tradeQty) {
      toast.warning('请输入交易数量')
      return
    }
    try {
      await api.post('/api/trading/trade', {
        symbol: stockData.symbol,
        action: tradeAction,
        quantity: parseInt(tradeQty),
      })
      toast.success(`${tradeAction === 'buy' ? '买入' : '卖出'}成功`)
      loadPortfolio()
      setShowTrade(false)
      setTradeQty('')
    } catch (err) {
      toast.error(err.response?.data?.detail || '交易失败')
    }
  }

  const handleReset = async () => {
    if (!confirm('确定要重置账户吗？所有持仓和交易记录将被清除。')) return
    try {
      await api.post('/api/trading/reset')
      toast.success('账户已重置')
      loadPortfolio()
    } catch {
      toast.error('重置失败')
    }
  }

  // 结构化报告：行情概览 + 技术指标 + 风险提示 + AI 分析（导出/复制/分享复用）
  const buildReportMd = () => {
    if (!stockData) return ''
    const rm = stockData.risk_metrics || {}
    const lines = [
      '# 股票分析报告',
      '',
      `> 代码：${stockData.symbol} · ${stockData.name || ''} · 周期：${period}`,
      `> 当前价格：$${stockData.current_price?.toFixed(2)} · 生成时间：${new Date().toLocaleString()}`,
      '',
      '## 行情概览',
      '',
      '| 指标 | 数值 |',
      '|---|---|',
      `| 开盘 | $${stockData.open?.toFixed(2)} |`,
      `| 最高 | $${stockData.day_high?.toFixed(2)} |`,
      `| 最低 | $${stockData.day_low?.toFixed(2)} |`,
      `| 成交量 | ${formatNumber(stockData.volume)} |`,
      `| 市值 | ${formatNumber(stockData.market_cap)} |`,
      `| 市盈率 | ${stockData.pe_ratio?.toFixed(2) || 'N/A'} |`,
      `| 52周最高 | $${stockData['52w_high']?.toFixed(2)} |`,
      `| 52周最低 | $${stockData['52w_low']?.toFixed(2)} |`,
      '',
      '## 技术指标',
      '',
      `- RSI(14)：${stockData.indicators?.rsi?.toFixed(2) || 'N/A'}`,
      `- MACD：${stockData.indicators?.macd?.toFixed(4) || 'N/A'}`,
      `- 均线：MA5=${stockData.indicators?.ma5?.toFixed(2) || 'N/A'}，MA20=${stockData.indicators?.ma20?.toFixed(2) || 'N/A'}，MA60=${stockData.indicators?.ma60?.toFixed(2) || 'N/A'}`,
      '',
      '## 风险提示',
      '',
      `- 综合风险等级：${rm.risk_level || '-'}`,
      `- 年化波动率：${rm.volatility_pct ?? '-'}%（${rm.volatility_level || '-'}）`,
      `- 最大回撤：${rm.max_drawdown_pct ?? '-'}%（${rm.drawdown_peak_date || '-'} → ${rm.drawdown_trough_date || '-'}）`,
      `- 日均成交量：${rm.avg_volume ? formatNumber(rm.avg_volume) : '-'}（流动性${rm.liquidity_level || '-'}）`,
      '',
    ]
    ;(rm.warnings || []).forEach((w) => lines.push(`- ⚠️ ${w}`))
    lines.push('')
    if (analysis) {
      lines.push('## AI 分析', '', analysis, '')
    }
    lines.push('---', '⚠️ 免责声明：本报告仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。')
    return lines.join('\n')
  }

  // AI 分析报告 → 导出 / 复制 / 分享
  const exportAnalysis = () => {
    const md = buildReportMd()
    if (!md) return
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${symbol}_分析报告_${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('分析报告已导出')
  }

  const copyAnalysis = async () => {
    const md = buildReportMd()
    if (!md) return
    try {
      await navigator.clipboard.writeText(md)
      toast.success('报告已复制，可直接粘贴到文档/微信')
    } catch {
      toast.error('复制失败，请手动选择复制')
    }
  }

  const formatNumber = (num) => {
    if (!num) return '0'
    if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T'
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(2)
  }

  const chartData =
    stockData?.data_points?.map((d) => ({
      date: d.date,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.volume,
    })) || []

  return (
    <div className="flex-1 overflow-auto bg-gray-50 pb-16 md:pb-0">
      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* 头部 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">股票分析</h1>
            <p className="text-sm text-gray-500 mt-1">行情分析 · 趋势预测 · 模拟交易</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="px-3 py-2 text-sm border border-gray-200 rounded-lg"
            >
              <option value="1mo">1个月</option>
              <option value="3mo">3个月</option>
              <option value="6mo">6个月</option>
              <option value="1y">1年</option>
              <option value="2y">2年</option>
            </select>
          </div>
        </div>

        {/* 搜索栏 */}
        <Card className="mb-6">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <SymbolAutocomplete
                value={symbol}
                onChange={setSymbol}
                onSelect={handleSearchFor}
                onEnter={handleSearch}
              />
            </div>
            <Button onClick={handleSearch} loading={loading}>
              查询
            </Button>
          </div>
          {/* v22：热门股票一键直达（未查询时展示） */}
          {!stockData && (
            <div className="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-gray-100">
              <span className="text-xs text-gray-400">热门：</span>
              {HOT_STOCKS.map((h) => (
                <button
                  key={h.symbol}
                  onClick={() => handleSearchFor(h.symbol)}
                  className="px-2.5 py-1 text-xs rounded-full border border-gray-200 text-gray-600 hover:border-brand-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                >
                  {h.label} <span className="text-gray-400">{h.symbol}</span>
                </button>
              ))}
            </div>
          )}
        </Card>

        {stockData && (
          <>
            {/* 股票信息卡片 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
              {/* 基本信息 */}
              <Card className="lg:col-span-2">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-2xl font-bold text-gray-900">{stockData.symbol}</h2>
                      <Badge variant="info">{stockData.exchange}</Badge>
                    </div>
                    <p className="text-gray-500 mt-1">{stockData.name}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-gray-900">
                      ${stockData.current_price?.toFixed(2)}
                    </div>
                    <div
                      className={`flex items-center gap-1 justify-end text-sm ${
                        stockData.current_price - stockData.previous_close >= 0
                          ? 'text-green-600'
                          : 'text-red-600'
                      }`}
                    >
                      {stockData.current_price - stockData.previous_close >= 0 ? (
                        <ArrowUpRight className="w-4 h-4" />
                      ) : (
                        <ArrowDownRight className="w-4 h-4" />
                      )}
                      {(
                        ((stockData.current_price - stockData.previous_close) /
                          stockData.previous_close) *
                        100
                      )?.toFixed(2)}
                      %
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-gray-100">
                  <div>
                    <div className="text-xs text-gray-500">开盘</div>
                    <div className="font-medium">${stockData.open?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">最高</div>
                    <div className="font-medium">${stockData.day_high?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">最低</div>
                    <div className="font-medium">${stockData.day_low?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">成交量</div>
                    <div className="font-medium">{formatNumber(stockData.volume)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">市值</div>
                    <div className="font-medium">{formatNumber(stockData.market_cap)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">市盈率</div>
                    <div className="font-medium">{stockData.pe_ratio?.toFixed(2) || 'N/A'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">52周最高</div>
                    <div className="font-medium">${stockData['52w_high']?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">52周最低</div>
                    <div className="font-medium">${stockData['52w_low']?.toFixed(2)}</div>
                  </div>
                </div>

                {/* 交易按钮 */}
                <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-100">
                  <Button onClick={() => setShowTrade(!showTrade)} size="sm">
                    <Play className="w-4 h-4 mr-1" />
                    模拟交易
                  </Button>
                  <Button onClick={handleAnalyze} loading={loading} variant="secondary" size="sm">
                    <BarChart3 className="w-4 h-4 mr-1" />
                    AI 分析
                  </Button>
                </div>

                {/* 交易面板 */}
                {showTrade && (
                  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-4">
                      <select
                        value={tradeAction}
                        onChange={(e) => setTradeAction(e.target.value)}
                        className="px-3 py-2 border border-gray-200 rounded-lg"
                      >
                        <option value="buy">买入</option>
                        <option value="sell">卖出</option>
                      </select>
                      <input
                        type="number"
                        value={tradeQty}
                        onChange={(e) => setTradeQty(e.target.value)}
                        placeholder="数量"
                        className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                      />
                      <Button onClick={handleTrade} size="sm">
                        确认{tradeAction === 'buy' ? '买入' : '卖出'}
                      </Button>
                    </div>
                    <div className="mt-2 text-xs text-gray-500">
                      预计金额: ${((tradeQty || 0) * stockData.current_price).toFixed(2)}
                    </div>
                  </div>
                )}
              </Card>

              {/* 技术指标 */}
              <Card>
                <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
                  <Activity className="w-4 h-4" />
                  技术指标
                </h3>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500">RSI (14)</span>
                      <span
                        className={`font-medium ${
                          stockData.indicators?.rsi > 70
                            ? 'text-red-600'
                            : stockData.indicators?.rsi < 30
                              ? 'text-green-600'
                              : 'text-gray-900'
                        }`}
                      >
                        {stockData.indicators?.rsi?.toFixed(2) || 'N/A'}
                      </span>
                    </div>
                    <div className="mt-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${
                          stockData.indicators?.rsi > 70
                            ? 'bg-red-500'
                            : stockData.indicators?.rsi < 30
                              ? 'bg-green-500'
                              : 'bg-blue-500'
                        }`}
                        style={{ width: `${Math.min(100, stockData.indicators?.rsi || 0)}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500">MACD</span>
                      <span
                        className={`font-medium ${
                          stockData.indicators?.macd > 0 ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {stockData.indicators?.macd?.toFixed(4) || 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div className="pt-4 border-t border-gray-100">
                    <div className="text-sm text-gray-500 mb-2">均线系统</div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-blue-600">MA5</span>
                        <span className="text-sm font-medium">
                          ${stockData.indicators?.ma5?.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-purple-600">MA20</span>
                        <span className="text-sm font-medium">
                          ${stockData.indicators?.ma20?.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-orange-600">MA60</span>
                        <span className="text-sm font-medium">
                          ${stockData.indicators?.ma60?.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* 风险提示卡片 */}
            {stockData.risk_metrics && (
              <Card className="mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium text-gray-900 flex items-center gap-2">
                    <ShieldAlert
                      className={`w-4 h-4 ${
                        stockData.risk_metrics.risk_level === '高'
                          ? 'text-red-500'
                          : stockData.risk_metrics.risk_level === '中'
                            ? 'text-amber-500'
                            : 'text-emerald-500'
                      }`}
                    />
                    风险提示
                  </h3>
                  <Badge
                    color={
                      stockData.risk_metrics.risk_level === '高'
                        ? 'red'
                        : stockData.risk_metrics.risk_level === '中'
                          ? 'amber'
                          : 'green'
                    }
                  >
                    综合风险：{stockData.risk_metrics.risk_level}
                  </Badge>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div className="p-3 rounded-lg bg-gray-50">
                    <div className="text-xs text-gray-500 mb-1">年化波动率</div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold text-gray-900">
                        {stockData.risk_metrics.volatility_pct ?? '-'}%
                      </span>
                      <span
                        className={`text-xs font-medium ${
                          stockData.risk_metrics.volatility_level === '高'
                            ? 'text-red-500'
                            : stockData.risk_metrics.volatility_level === '中'
                              ? 'text-amber-500'
                              : 'text-emerald-500'
                        }`}
                      >
                        {stockData.risk_metrics.volatility_level}波动
                      </span>
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-gray-50">
                    <div className="text-xs text-gray-500 mb-1">最大回撤</div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold text-gray-900">
                        {stockData.risk_metrics.max_drawdown_pct ?? '-'}%
                      </span>
                      <span
                        className={`text-xs font-medium ${
                          stockData.risk_metrics.max_drawdown_pct >= 20
                            ? 'text-red-500'
                            : stockData.risk_metrics.max_drawdown_pct >= 10
                              ? 'text-amber-500'
                              : 'text-emerald-500'
                        }`}
                      >
                        {stockData.risk_metrics.drawdown_peak_date || ''} →{' '}
                        {stockData.risk_metrics.drawdown_trough_date || ''}
                      </span>
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-gray-50">
                    <div className="text-xs text-gray-500 mb-1">日均成交量（流动性）</div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold text-gray-900">
                        {stockData.risk_metrics.avg_volume
                          ? formatNumber(stockData.risk_metrics.avg_volume)
                          : '-'}
                      </span>
                      <span className="text-xs font-medium text-gray-500">
                        {stockData.risk_metrics.liquidity_level}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {(stockData.risk_metrics.warnings || []).map((w, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-amber-800">
                      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                      {w}
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* 图表：专业 K 线（蜡烛图 + 成交量 + MA5/20/60） */}
            <Card className="mb-6">
              <h3 className="font-medium text-gray-900 mb-4">价格走势（K 线）</h3>
              <KLineChart data={chartData} height={420} />
            </Card>

            {/* AI 分析结果 */}
            {analysis && (
              <Card className="mb-6">
                <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
                  <h3 className="font-medium text-gray-900 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4" />
                    AI 分析报告
                  </h3>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => handleAnalyze()}>
                      重新分析
                    </Button>
                    <Button variant="ghost" size="sm" icon={Copy} onClick={copyAnalysis}>
                      复制
                    </Button>
                    <Button variant="ghost" size="sm" icon={Download} onClick={exportAnalysis}>
                      导出
                    </Button>
                    <ShareButton content={buildReportMd()} title={`${symbol} AI 股票分析报告`} contentType="stock_analysis" />
                  </div>
                </div>
                <MarkdownRenderer content={analysis} />
              </Card>
            )}
          </>
        )}

        {/* 投资组合 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-gray-900 flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                模拟账户
              </h3>
              <button
                onClick={handleReset}
                className="text-xs text-gray-500 hover:text-red-600 flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" />
                重置
              </button>
            </div>
            {portfolio ? (
              <div>
                <div className="text-3xl font-bold text-gray-900 mb-1">
                  ${formatNumber(portfolio.total_value)}
                </div>
                <div className="text-sm text-gray-500 mb-4">总资产</div>
                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
                  <div>
                    <div className="text-xs text-gray-500">可用现金</div>
                    <div className="font-medium text-lg">${formatNumber(portfolio.cash)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">持仓市值</div>
                    <div className="font-medium text-lg">
                      ${formatNumber(portfolio.total_value - portfolio.cash)}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <Empty description="暂无账户信息" />
            )}
          </Card>

          <Card>
            <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
              <PieChart className="w-4 h-4" />
              当前持仓
            </h3>
            {portfolio?.positions?.length > 0 ? (
              <div className="space-y-3">
                {portfolio.positions.map((pos, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <div className="font-medium">{pos.symbol}</div>
                      <div className="text-xs text-gray-500">
                        {pos.quantity} 股 @ ${pos.avg_cost?.toFixed(2)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium">${pos.market_value?.toFixed(2)}</div>
                      <div
                        className={`text-xs ${pos.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}
                      >
                        {pos.profit_loss >= 0 ? '+' : ''}
                        {pos.profit_loss?.toFixed(2)} ({pos.profit_loss_pct?.toFixed(2)}%)
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty description="暂无持仓" />
            )}
          </Card>
        </div>

       {/* v21：定时分析报告 + 历史报告 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          {/* 定时分析报告 */}
          <Card>
            <h3 className="font-medium text-gray-900 mb-1 flex items-center gap-2">
              <CalendarClock className="w-4 h-4 text-brand-500" />
              定时分析报告
            </h3>
            <p className="text-xs text-gray-500 mb-4">
              每天定时抓取行情并生成专业分析报告，配置 Webhook 后自动推送（飞书 / 企业微信 / 自建服务）
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">股票代码</label>
                <SymbolAutocomplete
                  value={schedSymbol}
                  onChange={setSchedSymbol}
                  compact
                  placeholder={stockData?.symbol || '搜索或输入代码，如 AAPL、0700.HK'}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">分析周期</label>
                  <select
                    value={schedPeriod}
                    onChange={(e) => setSchedPeriod(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                  >
                    {PERIOD_OPTIONS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">推送频率</label>
                  <select
                    value={schedFreq}
                    onChange={(e) => setSchedFreq(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                  >
                    {FREQ_OPTIONS.map((f) => (
                      <option key={f.cron} value={f.cron}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <Button onClick={handleCreateSchedule} loading={creatingSchedule} className="w-full">
                <Clock className="w-4 h-4 mr-1" />
                创建定时任务
              </Button>
              <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg text-xs text-blue-800">
                <Webhook className="w-4 h-4 mt-0.5 shrink-0" />
                <span>
                  报告生成后将通过 Webhook 自动推送。前往
                  <a href="/#/settings" className="underline font-medium">设置 - 通知</a>
                  配置飞书 / 企业微信机器人即可在手机上接收每日报告。
                </span>
              </div>
            </div>
          </Card>

          {/* 历史报告 */}
          <Card>
            <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-4 h-4 text-brand-500" />
              历史报告
            </h3>
            {reports === null ? (
              <Empty description="加载中..." />
            ) : reports.length === 0 ? (
              <Empty description="暂无定时报告，左侧创建定时任务后自动生成" />
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {reports.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{r.symbol}</span>
                        <Badge variant="info">{PERIOD_OPTIONS.find((p) => p.value === r.period)?.label || r.period}</Badge>
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : ''}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="ghost" size="sm" icon={FileText} onClick={() => setViewReport(r)}>
                        查看
                      </Button>
                      <Button variant="ghost" size="sm" icon={Trash2} onClick={() => handleDeleteReport(r)}>
                        删除
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 免责声明 */}
        <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-xs text-yellow-800">
            ⚠️ <strong>免责声明：</strong>本工具提供的数据和分析仅供参考，不构成任何投资建议。
            模拟交易使用虚拟资金，不涉及真实交易。投资有风险，入市需谨慎。
          </p>
        </div>
      </div>

      {/* v21：历史报告查看弹窗 */}
      <Modal open={!!viewReport} onClose={() => setViewReport(null)} title={viewReport ? `报告：${viewReport.symbol}` : ''} size="lg">
        {viewReport && (
          <div>
            <div className="flex items-center gap-3 mb-4 pb-3 border-b border-gray-100">
              <Badge variant="info">
                {PERIOD_OPTIONS.find((p) => p.value === viewReport.period)?.label || viewReport.period}
              </Badge>
              <span className="text-xs text-gray-500">
                {viewReport.created_at ? new Date(viewReport.created_at).toLocaleString() : ''}
              </span>
            </div>
            <MarkdownRenderer content={viewReport.report || ''} />
          </div>
        )}
      </Modal>
    </div>
  )
}
