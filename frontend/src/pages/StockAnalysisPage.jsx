import React, { useState, useEffect } from 'react'
import { Card, Button, Badge, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'
import MarkdownRenderer from '../components/MarkdownRenderer'
import {
  Search, TrendingUp, TrendingDown, DollarSign, BarChart3,
  LineChart, Activity, PieChart, Play, Pause, RefreshCw,
  ArrowUpRight, ArrowDownRight, Minus
} from 'lucide-react'
import {
  LineChart as RechartsLine,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  BarChart,
  Bar
} from 'recharts'

export default function StockAnalysisPage() {
  const [symbol, setSymbol] = useState('')
  const [stockData, setStockData] = useState(null)
  const [analysis, setAnalysis] = useState('')
  const [loading, setLoading] = useState(false)
  const [analysisType, setAnalysisType] = useState('comprehensive')
  const [period, setPeriod] = useState('3mo')
  const [portfolio, setPortfolio] = useState(null)
  const [tradeAction, setTradeAction] = useState('buy')
  const [tradeQty, setTradeQty] = useState('')
  const [showTrade, setShowTrade] = useState(false)
  const toast = useToast()

  useEffect(() => {
    loadPortfolio()
  }, [])

  const loadPortfolio = async () => {
    try {
      const res = await api.get('/api/trading/portfolio')
      setPortfolio(res.data)
    } catch (err) {
      // ignore
    }
  }

  const handleSearch = async () => {
    if (!symbol.trim()) {
      toast.warning('请输入股票代码')
      return
    }
    setLoading(true)
    try {
      const res = await api.get(`/api/stock/${symbol.toUpperCase()}?period=${period}`)
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
      const res = await api.post('/api/trading/trade', {
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
    } catch (err) {
      toast.error('重置失败')
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

  const chartData = stockData?.data_points?.map(d => ({
    date: d.date,
    price: d.close,
    volume: d.volume,
    ma5: d.ma5,
    ma20: d.ma20,
  })) || []

  return (
    <div className="flex-1 overflow-auto bg-gray-50">
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
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="输入股票代码，如 AAPL, MSFT, TSLA..."
                className="w-full pl-10 pr-4 py-3 text-lg border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <Button onClick={handleSearch} loading={loading}>
              查询
            </Button>
          </div>
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
                    <div className={`flex items-center gap-1 justify-end text-sm ${
                      (stockData.current_price - stockData.previous_close) >= 0 
                        ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(stockData.current_price - stockData.previous_close) >= 0 
                        ? <ArrowUpRight className="w-4 h-4" />
                        : <ArrowDownRight className="w-4 h-4" />
                      }
                      {((stockData.current_price - stockData.previous_close) / stockData.previous_close * 100)?.toFixed(2)}%
                    </div>
                  </div>
                </div>
                
                <div className="grid grid-cols-4 gap-4 pt-4 border-t border-gray-100">
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
                      <span className={`font-medium ${
                        stockData.indicators?.rsi > 70 ? 'text-red-600' :
                        stockData.indicators?.rsi < 30 ? 'text-green-600' : 'text-gray-900'
                      }`}>
                        {stockData.indicators?.rsi?.toFixed(2) || 'N/A'}
                      </span>
                    </div>
                    <div className="mt-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${
                          stockData.indicators?.rsi > 70 ? 'bg-red-500' :
                          stockData.indicators?.rsi < 30 ? 'bg-green-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${Math.min(100, stockData.indicators?.rsi || 0)}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500">MACD</span>
                      <span className={`font-medium ${
                        stockData.indicators?.macd > 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {stockData.indicators?.macd?.toFixed(4) || 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div className="pt-4 border-t border-gray-100">
                    <div className="text-sm text-gray-500 mb-2">均线系统</div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-blue-600">MA5</span>
                        <span className="text-sm font-medium">${stockData.indicators?.ma5?.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-purple-600">MA20</span>
                        <span className="text-sm font-medium">${stockData.indicators?.ma20?.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-orange-600">MA60</span>
                        <span className="text-sm font-medium">${stockData.indicators?.ma60?.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* 图表 */}
            <Card className="mb-6">
              <h3 className="font-medium text-gray-900 mb-4">价格走势</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="price"
                      stroke="#3b82f6"
                      fillOpacity={1}
                      fill="url(#colorPrice)"
                      name="价格"
                    />
                    <Line type="monotone" dataKey="ma5" stroke="#3b82f6" strokeWidth={1} dot={false} name="MA5" />
                    <Line type="monotone" dataKey="ma20" stroke="#a855f7" strokeWidth={1} dot={false} name="MA20" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* AI 分析结果 */}
            {analysis && (
              <Card className="mb-6">
                <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  AI 分析报告
                </h3>
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
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <div className="font-medium">{pos.symbol}</div>
                      <div className="text-xs text-gray-500">
                        {pos.quantity} 股 @ ${pos.avg_cost?.toFixed(2)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium">${pos.market_value?.toFixed(2)}</div>
                      <div className={`text-xs ${pos.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {pos.profit_loss >= 0 ? '+' : ''}{pos.profit_loss?.toFixed(2)} ({pos.profit_loss_pct?.toFixed(2)}%)
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

        {/* 免责声明 */}
        <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-xs text-yellow-800">
            ⚠️ <strong>免责声明：</strong>本工具提供的数据和分析仅供参考，不构成任何投资建议。
            模拟交易使用虚拟资金，不涉及真实交易。投资有风险，入市需谨慎。
          </p>
        </div>
      </div>
    </div>
  )
}
