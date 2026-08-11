/**
 * v21/v22 股票分析页单测：定时分析报告面板 / 历史报告列表 / K 线主图挂载 /
 * 关键词智能补全（候选列表自由选择）/ 热门股票一键直达。
 * api 整体 mock，不触发真实后端；KLineChart 依赖 canvas，此页断言其标题与挂载点。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('../../lib/api', () => ({
  default: apiMock,
}))

// KLineChart 依赖真实 canvas，jsdom 下整体 mock 防渲染崩溃
const { klInitMock, klDisposeMock, klChartMock } = vi.hoisted(() => ({
  klInitMock: vi.fn(),
  klDisposeMock: vi.fn(),
  klChartMock: { createIndicator: vi.fn(), applyNewData: vi.fn() },
}))
vi.mock('klinecharts', () => ({
  init: (...args) => klInitMock(...args),
  dispose: (...args) => klDisposeMock(...args),
}))

import StockAnalysisPage from '../../pages/StockAnalysisPage'

const PORTFOLIO = { total_value: 1000000, cash: 500000, positions: [] }

const STOCK = {
  symbol: 'AAPL',
  name: 'Apple',
  current_price: 150,
  previous_close: 148,
  exchange: 'NASDAQ',
  open: 149,
  day_high: 152,
  day_low: 148.5,
  volume: 3000000,
  market_cap: 2500000000000,
  pe_ratio: 28.5,
  '52w_high': 200,
  '52w_low': 120,
  indicators: { rsi: 55, macd: 1.2, ma5: 148, ma20: 145, ma60: 140 },
  risk_metrics: { risk_level: '低', volatility_pct: 20, warnings: [] },
  data_points: [
    { date: '2026-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 },
    { date: '2026-01-02', open: 105, high: 112, low: 102, close: 108, volume: 1500 },
  ],
}

describe('StockAnalysisPage v21', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    klInitMock.mockImplementation(() => klChartMock)
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/stock/search')) {
        return Promise.resolve({ data: { items: [] } })
      }
      if (String(url).includes('/api/stock/reports')) {
        return Promise.resolve({ data: { items: [] } })
      }
      if (String(url).includes('/api/trading/portfolio')) {
        return Promise.resolve({ data: PORTFOLIO })
      }
      return Promise.resolve({ data: {} })
    })
    apiMock.post.mockResolvedValue({ data: {} })
    apiMock.delete.mockResolvedValue({ data: { ok: true } })
  })

  it('渲染定时分析报告面板与历史报告区', async () => {
    render(<StockAnalysisPage />)
    expect(screen.getByText('定时分析报告')).toBeInTheDocument()
    expect(screen.getByText('历史报告')).toBeInTheDocument()
    expect(screen.getByText('创建定时任务')).toBeInTheDocument()
    // Webhook 推送提示
    expect(screen.getByText(/Webhook 后自动推送/)).toBeInTheDocument()
    // 默认频率与周期预设
    expect(screen.getByRole('option', { name: '每天 9:00 盘前' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '每周一 9:00' })).toBeInTheDocument()
    // 顶部周期切换与定时面板各有一个 1年 选项
    expect(screen.getAllByRole('option', { name: '1年' }).length).toBeGreaterThan(0)
    await waitFor(() => expect(apiMock.get).toHaveBeenCalled())
  })

  it('创建定时任务：提交 stock_report 配置', async () => {
    render(<StockAnalysisPage />)
    fireEvent.change(screen.getByPlaceholderText('搜索或输入代码，如 AAPL、0700.HK'), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('创建定时任务'))
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledTimes(1))
    const [url, payload] = apiMock.post.mock.calls[0]
    expect(url).toBe('/api/scheduler')
    expect(payload.job_type).toBe('stock_report')
    expect(payload.config).toEqual({
      symbol: 'AAPL',
      period: '3mo',
      analysis_type: 'comprehensive',
    })
    expect(payload.name).toBe('每日股票分析：AAPL')
  })

  it('历史报告列表：查看与删除', async () => {
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/stock/reports')) {
        return Promise.resolve({
          data: {
            items: [
              { id: 1, symbol: 'AAPL', period: '3mo', report: '# 报告\n\n内容', created_at: '2026-01-01T09:00:00' },
            ],
          },
        })
      }
      return Promise.resolve({ data: PORTFOLIO })
    })
    render(<StockAnalysisPage />)
    // 历史报告条目
    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())
    // 周期 Badge（顶部周期切换与定时面板各有同名 option，用数量断言）
    expect(screen.getAllByText('3个月').length).toBeGreaterThan(0)

    // 查看弹窗：MarkdownRenderer 渲染报告内容
    fireEvent.click(screen.getByText('查看'))
    expect(await screen.findByText(/报告：AAPL/)).toBeInTheDocument()
    expect(screen.getByText(/内容/)).toBeInTheDocument()

    // 删除（Modal 为 overlay，不遮挡底层 DOM）
    const delBtn = screen.getByText('删除')
    const spy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(delBtn)
    await waitFor(() => expect(apiMock.delete).toHaveBeenCalledWith('/api/stock/reports/1'))
    spy.mockRestore()
  })

  it('查询股票后渲染 K 线图卡片', async () => {
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/stock/search')) {
        return Promise.resolve({ data: { items: [] } })
      }
      if (String(url).includes('/api/stock/')) {
        return Promise.resolve({ data: STOCK })
      }
      return Promise.resolve({ data: PORTFOLIO })
    })
    render(<StockAnalysisPage />)
    fireEvent.change(screen.getByPlaceholderText(/搜索股票名称\/代码/), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('查询'))
    await waitFor(() => expect(screen.getByText('价格走势（K 线）')).toBeInTheDocument())
    // MA5 图例（技术指标卡也有 MA5 文本，用数量断言）
    expect(screen.getAllByText('MA5').length).toBeGreaterThan(0)
    expect(screen.getByText(/红涨绿跌/)).toBeInTheDocument()
  })

  // ── v22：关键词智能补全 + 多结果自由选择 ──
  it('关键词输入 → 防抖搜索 → 展示候选列表（多结果可自由选择）', async () => {
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/stock/search')) {
        return Promise.resolve({
          data: {
            items: [
              { symbol: '0700.HK', name: 'Tencent Holdings', exchange: 'HKEX', type: 'Equity' },
              { symbol: 'TCEHY', name: 'Tencent ADR', exchange: 'PNK', type: 'Equity' },
            ],
          },
        })
      }
      return Promise.resolve({ data: PORTFOLIO })
    })
    render(<StockAnalysisPage />)
    fireEvent.change(screen.getByPlaceholderText(/搜索股票名称\/代码/), { target: { value: 'ten' } })
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/api/stock/search?q=ten&limit=8'))
    expect(await screen.findByText('Tencent Holdings')).toBeInTheDocument()
    const list = within(screen.getByTestId('symbol-suggestions'))
    expect(list.getByText('0700.HK')).toBeInTheDocument()
    expect(list.getByText('HKEX')).toBeInTheDocument()
  })

  it('点击候选 → 选中并立即查询该股票', async () => {
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/stock/search')) {
        return Promise.resolve({
          data: { items: [{ symbol: '0700.HK', name: 'Tencent Holdings', exchange: 'HKEX', type: 'Equity' }] },
        })
      }
      if (String(url).includes('/api/stock/')) {
        return Promise.resolve({ data: STOCK })
      }
      return Promise.resolve({ data: PORTFOLIO })
    })
    render(<StockAnalysisPage />)
    fireEvent.change(screen.getByPlaceholderText(/搜索股票名称\/代码/), { target: { value: 'tencent' } })
    fireEvent.mouseDown(await screen.findByText('Tencent Holdings'))
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/api/stock/0700.HK?period=3mo'))
    await waitFor(() => expect(screen.getByText('价格走势（K 线）')).toBeInTheDocument())
  })

  it('无候选时提示尝试完整代码', async () => {
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/stock/search')) {
        return Promise.resolve({ data: { items: [] } })
      }
      return Promise.resolve({ data: PORTFOLIO })
    })
    render(<StockAnalysisPage />)
    fireEvent.change(screen.getByPlaceholderText(/搜索股票名称\/代码/), { target: { value: 'xyzabc' } })
    expect(await screen.findByText('未找到匹配，请尝试完整代码（如 0700.HK）')).toBeInTheDocument()
  })

  it('热门股票一键直达查询', async () => {
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/stock/search')) {
        return Promise.resolve({ data: { items: [] } })
      }
      if (String(url).includes('/api/stock/')) {
        return Promise.resolve({ data: STOCK })
      }
      return Promise.resolve({ data: PORTFOLIO })
    })
    render(<StockAnalysisPage />)
    expect(screen.getByText('热门：')).toBeInTheDocument()
    fireEvent.click(screen.getByText('苹果'))
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/api/stock/AAPL?period=3mo'))
    await waitFor(() => expect(screen.getByText('价格走势（K 线）')).toBeInTheDocument())
  })
})
