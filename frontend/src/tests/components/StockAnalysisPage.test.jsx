/**
 * v21 股票分析页单测：定时分析报告面板 / 历史报告列表 / K 线主图挂载。
 * api 整体 mock，不触发真实后端；KLineChart 依赖 canvas，此页断言其标题与挂载点。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

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

describe('StockAnalysisPage v21', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    klInitMock.mockImplementation(() => klChartMock)
    apiMock.get.mockImplementation((url) => {
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
    fireEvent.change(screen.getByPlaceholderText('如 AAPL, 0700.HK'), { target: { value: 'AAPL' } })
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
      if (String(url).includes('/api/stock/')) {
        return Promise.resolve({
          data: {
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
          },
        })
      }
      return Promise.resolve({ data: PORTFOLIO })
    })
    render(<StockAnalysisPage />)
    fireEvent.change(screen.getByPlaceholderText(/输入股票代码/), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('查询'))
    await waitFor(() => expect(screen.getByText('价格走势（K 线）')).toBeInTheDocument())
    // MA5 图例（技术指标卡也有 MA5 文本，用数量断言）
    expect(screen.getAllByText('MA5').length).toBeGreaterThan(0)
    expect(screen.getByText(/红涨绿跌/)).toBeInTheDocument()
  })
})
