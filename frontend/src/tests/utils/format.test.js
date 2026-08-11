/**
 * v17 通用格式化工具单测：日期/时间/字节/状态映射/截断/防抖/剪贴板。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  formatDateTime,
  formatDate,
  formatRelativeTime,
  formatBytes,
  getStatusMeta,
  truncate,
  debounce,
  copyToClipboard,
} from '../../lib/format'

describe('formatDateTime', () => {
  it('格式化标准时间戳', () => {
    expect(formatDateTime('2026-08-02T14:30:00')).toBe('2026-08-02 14:30')
  })

  it('空值返回 fallback', () => {
    expect(formatDateTime(null)).toBe('-')
    expect(formatDateTime('')).toBe('-')
    expect(formatDateTime(undefined, 'N/A')).toBe('N/A')
  })

  it('非法日期返回 fallback', () => {
    expect(formatDateTime('not-a-date')).toBe('-')
  })
})

describe('formatDate', () => {
  it('格式化日期（无时间部分）', () => {
    expect(formatDate('2026-08-02T14:30:00')).toBe('2026-08-02')
  })

  it('空值返回 fallback', () => {
    expect(formatDate('')).toBe('-')
  })
})

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-02T12:00:00'))
  })

  afterEach(() => vi.useRealTimers())

  it('秒级返回刚刚', () => {
    expect(formatRelativeTime('2026-08-02T11:59:50')).toBe('刚刚')
  })

  it('分钟级', () => {
    expect(formatRelativeTime('2026-08-02T11:55:00')).toBe('5 分钟前')
  })

  it('小时级', () => {
    expect(formatRelativeTime('2026-08-02T10:00:00')).toBe('2 小时前')
  })

  it('天级（30 天内）', () => {
    expect(formatRelativeTime('2026-07-30T12:00:00')).toBe('3 天前')
  })

  it('超过 30 天回落为日期', () => {
    expect(formatRelativeTime('2026-06-01T12:00:00')).toBe('2026-06-01')
  })

  it('空值返回 fallback', () => {
    expect(formatRelativeTime(null)).toBe('-')
  })
})

describe('formatBytes', () => {
  it('各量级格式化', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
  })

  it('非法输入返回 fallback', () => {
    expect(formatBytes(null)).toBe('-')
    expect(formatBytes('abc')).toBe('-')
  })
})

describe('getStatusMeta', () => {
  it('已知状态返回中文文案与样式', () => {
    expect(getStatusMeta('success').text).toBe('成功')
    expect(getStatusMeta('running').cls).toContain('blue')
    expect(getStatusMeta('DONE').text).toBe('已完成') // 大小写不敏感
  })

  it('未知状态回退为原值', () => {
    expect(getStatusMeta('weird-status').text).toBe('weird-status')
  })

  it('自定义映射优先', () => {
    const custom = { special: { text: '自定义', cls: '' } }
    expect(getStatusMeta('special', custom).text).toBe('自定义')
  })
})

describe('truncate', () => {
  it('超长截断加省略号', () => {
    expect(truncate('a'.repeat(60), 50)).toBe('a'.repeat(50) + '…')
  })

  it('短文本原样返回', () => {
    expect(truncate('你好')).toBe('你好')
  })

  it('空值返回空串', () => {
    expect(truncate(null)).toBe('')
  })
})

describe('debounce', () => {
  it('连续调用只执行最后一次', () => {
    vi.useFakeTimers()
    const fn = vi.fn()
    const debounced = debounce(fn, 300)
    debounced('a')
    debounced('b')
    debounced('c')
    expect(fn).not.toHaveBeenCalled()
    vi.advanceTimersByTime(300)
    expect(fn).toHaveBeenCalledTimes(1)
    expect(fn).toHaveBeenCalledWith('c')
    vi.useRealTimers()
  })
})

describe('copyToClipboard', () => {
  it('成功复制返回 true', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
    expect(await copyToClipboard('hello')).toBe(true)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('hello')
  })

  it('复制失败返回 false', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })
    expect(await copyToClipboard('hello')).toBe(false)
  })
})
