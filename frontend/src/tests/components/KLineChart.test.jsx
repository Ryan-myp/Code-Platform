/**
 * v21 K 线图组件单测：klinecharts 初始化 / 数据映射 / 指标注册 / 卸载销毁。
 * klinecharts 依赖真实 canvas，测试中整体 mock，只验证交互契约。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'

const { initMock, disposeMock, chartMock } = vi.hoisted(() => ({
  initMock: vi.fn(),
  disposeMock: vi.fn(),
  chartMock: {
    createIndicator: vi.fn(),
    applyNewData: vi.fn(),
  },
}))

vi.mock('klinecharts', () => ({
  init: (...args) => initMock(...args),
  dispose: (...args) => disposeMock(...args),
}))

import KLineChart from '../../components/KLineChart'

const OHLC = [
  { date: '2026-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 },
  { date: '2026-01-02', open: 105, high: 112, low: 102, close: 108, volume: 1500 },
]

describe('KLineChart', () => {
  beforeEach(() => {
    initMock.mockReset()
    disposeMock.mockReset()
    chartMock.createIndicator.mockReset()
    chartMock.applyNewData.mockReset()
    initMock.mockImplementation(() => chartMock)
  })

  it('空数据不初始化图表', () => {
    const { container } = render(<KLineChart data={[]} />)
    expect(container.innerHTML).toBe('')
    expect(initMock).not.toHaveBeenCalled()
  })

  it('初始化图表：容器 + 中文 + 红涨绿跌样式', () => {
    render(<KLineChart data={OHLC} />)
    expect(initMock).toHaveBeenCalledTimes(1)
    const [el, options] = initMock.mock.calls[0]
    expect(el).toBeInstanceOf(HTMLElement)
    expect(options.locale).toBe('zh-CN')
    // 红涨绿跌：蜡烛上涨色为红
    expect(options.styles.candle.bar.upColor).toBe('#e11d48')
    expect(options.styles.candle.bar.downColor).toBe('#10b981')
  })

  it('注册 MA 均线与成交量副图', () => {
    render(<KLineChart data={OHLC} />)
    expect(chartMock.createIndicator).toHaveBeenCalledWith({ name: 'MA', calcParams: [5, 20, 60] }, true, { id: 'candle_pane' })
    expect(chartMock.createIndicator).toHaveBeenCalledWith('VOL', false)
  })

  it('数据映射：日期转 timestamp + OHLCV 字段透传', () => {
    render(<KLineChart data={OHLC} />)
    expect(chartMock.applyNewData).toHaveBeenCalledTimes(1)
    const mapped = chartMock.applyNewData.mock.calls[0][0]
    expect(mapped).toHaveLength(2)
    expect(mapped[0]).toEqual({
      timestamp: new Date('2026-01-01T00:00:00').getTime(),
      open: 100,
      high: 110,
      low: 95,
      close: 105,
      volume: 1000,
    })
  })

  it('卸载时销毁图表实例', () => {
    const { unmount } = render(<KLineChart data={OHLC} />)
    unmount()
    expect(disposeMock).toHaveBeenCalledWith(chartMock)
  })

  it('渲染均线图例与操作提示', () => {
    const { container } = render(<KLineChart data={OHLC} />)
    expect(container.textContent).toContain('MA5')
    expect(container.textContent).toContain('MA20')
    expect(container.textContent).toContain('MA60')
    expect(container.textContent).toContain('红涨绿跌')
  })
})
