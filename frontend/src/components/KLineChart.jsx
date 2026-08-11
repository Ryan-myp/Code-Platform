import { useEffect, useRef } from 'react'
import { init, dispose } from 'klinecharts'

/**
 * v21 专业 K 线图组件（klinecharts 封装）
 *
 * 蜡烛图 + 成交量副图 + MA5/20/60 均线 + 十字光标；红涨绿跌（中文习惯）。
 * props:
 * - data: [{ date, open, high, low, close, volume }]
 * - height: 容器高度（px，默认 420）
 */
export default function KLineChart({ data = [], height = 420 }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el || !data || data.length === 0) return undefined

    const chart = init(el, {
      locale: 'zh-CN',
      styles: {
        grid: {
          horizontal: { color: '#eef0f3', size: 1, style: 'dashed' },
          vertical: { color: 'transparent', size: 1, style: 'dashed' },
        },
        candle: {
          bar: {
            upColor: '#e11d48',
            upBorderColor: '#e11d48',
            upWickColor: '#e11d48',
            downColor: '#10b981',
            downBorderColor: '#10b981',
            downWickColor: '#10b981',
            noChangeColor: '#9ca3af',
            noChangeBorderColor: '#9ca3af',
            noChangeWickColor: '#9ca3af',
          },
        },
        indicator: {
          lines: [
            { color: '#3b82f6', size: 1 }, // MA5 蓝
            { color: '#a855f7', size: 1 }, // MA20 紫
            { color: '#f59e0b', size: 1 }, // MA60 橙
          ],
        },
        xAxis: { axisLine: { color: '#e5e7eb' }, tickText: { color: '#9ca3af' } },
        yAxis: { axisLine: { color: '#e5e7eb' }, tickText: { color: '#9ca3af' } },
        crosshair: {
          horizontal: { line: { color: '#9ca3af', style: 'dashed' } },
          vertical: { line: { color: '#9ca3af', style: 'dashed' } },
        },
      },
    })
    chartRef.current = chart

    chart.createIndicator({ name: 'MA', calcParams: [5, 20, 60] }, true, { id: 'candle_pane' })
    chart.createIndicator('VOL', false)
    chart.applyNewData(
      data
        .filter((d) => d.date)
        .map((d) => ({
          timestamp: new Date(`${d.date}T00:00:00`).getTime(),
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
          volume: d.volume,
        }))
    )

    return () => {
      dispose(chart)
      chartRef.current = null
    }
  }, [data])

  if (!data || data.length === 0) return null

  return (
    <div>
      <div ref={containerRef} className="w-full" style={{ height }} />
      <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-400">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 rounded bg-blue-500" /> MA5
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 rounded bg-purple-500" /> MA20
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 rounded bg-amber-500" /> MA60
        </span>
        <span className="ml-auto">红涨绿跌 · 十字光标可查看历史价格</span>
      </div>
    </div>
  )
}
