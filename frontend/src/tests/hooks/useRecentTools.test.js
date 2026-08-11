/**
 * v17 最近使用追踪单测：路由访问去重置顶 / 上限 / 排除页 / 未收录页 / 清空 / 相对时间。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import useRecentTools, {
  trackVisit,
  clearRecentTools,
  formatRecentTime,
} from '../../hooks/useRecentTools'

const STORAGE_KEY = 'recent_tools_v1'

describe('trackVisit', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('首次访问写入记录（含标签与图标）', () => {
    trackVisit('/workspace')
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY))
    expect(list).toHaveLength(1)
    expect(list[0].path).toBe('/workspace')
    expect(list[0].label).toBe('AI 工作台')
    expect(list[0].icon).toBe('⚡')
    expect(typeof list[0].ts).toBe('number')
  })

  it('同页面重复访问去重置顶', () => {
    trackVisit('/workspace')
    trackVisit('/chat')
    trackVisit('/workspace') // 再次访问 workspace → 置顶
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY))
    expect(list[0].path).toBe('/workspace')
    expect(list).toHaveLength(2)
  })

  it('超过上限 10 条时淘汰最旧', () => {
    for (let i = 0; i < 12; i++) {
      trackVisit(`/tool-${i}`) // 未收录路径不会写入，改用循环收录页
      trackVisit('/workspace')
    }
    // 上面 12 轮中 /workspace 始终置顶，且是唯一收录路径 → 只留 1 条
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY))
    expect(list).toHaveLength(1)
    expect(list[0].path).toBe('/workspace')
  })

  it('上限淘汰：模拟 12 个不同收录页', () => {
    const pages = [
      '/workspace', '/board', '/projects', '/artifacts', '/tasks', '/chat',
      '/agents', '/workflows', '/knowledge-bases', '/digital-human', '/meme',
      '/music-factory', '/image-factory', '/video-factory',
    ]
    pages.forEach((p) => trackVisit(p))
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY))
    expect(list).toHaveLength(10) // 只保留最新 10 条
    expect(list[list.length - 1].path).toBe('/tasks') // 最旧 4 条（workspace/board/projects/artifacts）被淘汰
  })

  it('排除页不记录', () => {
    trackVisit('/home')
    trackVisit('/login')
    trackVisit('/membership')
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('未收录页面不记录', () => {
    trackVisit('/unknown-page-xyz')
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('空 path 安全跳过', () => {
    trackVisit(null)
    trackVisit('')
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('localStorage 数据损坏时安全降级', () => {
    localStorage.setItem(STORAGE_KEY, '{broken json')
    trackVisit('/chat')
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY))
    expect(list).toHaveLength(1)
    expect(list[0].path).toBe('/chat')
  })
})

describe('clearRecentTools', () => {
  it('清空后记录消失', () => {
    trackVisit('/chat')
    clearRecentTools()
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})

describe('useRecentTools hook', () => {
  beforeEach(() => localStorage.clear())

  it('初始为空，访问后刷新可见', () => {
    const { result, rerender } = renderHook(() => useRecentTools())
    expect(result.current.recent).toEqual([])

    trackVisit('/chat')
    act(() => result.current.refresh())
    expect(result.current.recent).toHaveLength(1)
    expect(result.current.recent[0].path).toBe('/chat')
    rerender()
  })

  it('clear 清空列表', () => {
    trackVisit('/chat')
    const { result } = renderHook(() => useRecentTools())
    act(() => result.current.refresh())
    expect(result.current.recent).toHaveLength(1)
    act(() => result.current.clear())
    expect(result.current.recent).toEqual([])
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})

describe('formatRecentTime', () => {
  const now = Date.now()

  it('1 分钟内返回刚刚', () => {
    expect(formatRecentTime(now - 1000)).toBe('刚刚')
  })

  it('N 分钟前', () => {
    expect(formatRecentTime(now - 5 * 60000)).toBe('5 分钟前')
  })

  it('N 小时前', () => {
    expect(formatRecentTime(now - 3 * 3600000)).toBe('3 小时前')
  })

  it('昨天', () => {
    expect(formatRecentTime(now - 26 * 3600000)).toBe('昨天')
  })

  it('N 天前（7 天内）', () => {
    expect(formatRecentTime(now - 4 * 86400000)).toBe('4 天前')
  })

  it('超过 7 天显示月日', () => {
    const old = new Date(2026, 5, 15).getTime() // 6月15日
    expect(formatRecentTime(old)).toBe('6月15日')
  })

  it('空值返回空串', () => {
    expect(formatRecentTime(null)).toBe('')
    expect(formatRecentTime(undefined)).toBe('')
  })
})
