/**
 * v17 工具输入态持久化单测：版本化恢复 / 防抖保存 / 排除字段 / 容量上限 / 清空。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import usePersistentToolState from '../../hooks/usePersistentToolState'

describe('usePersistentToolState', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('初始返回 initialState，且 300ms 后自动持久化', async () => {
    const { result } = renderHook(() =>
      usePersistentToolState('key1', { query: '', page: 1 })
    )
    expect(result.current[0]).toEqual({ query: '', page: 1 })

    act(() => result.current[1]({ query: 'hello', page: 2 }))
    await waitFor(() => {
      const saved = JSON.parse(localStorage.getItem('key1_v1'))
      expect(saved).toEqual({ query: 'hello', page: 2 })
    })
  })

  it('重挂载时从 localStorage 恢复，缺失字段回落默认值', async () => {
    const { result, unmount } = renderHook(() =>
      usePersistentToolState('key2', { query: '', tags: [] })
    )
    act(() => result.current[1]({ query: '测试', tags: ['a'] }))
    await waitFor(() => expect(localStorage.getItem('key2_v1')).toBeTruthy())
    unmount()

    // 结构变更：新增字段 extra 用默认值补齐
    const { result: restored } = renderHook(() =>
      usePersistentToolState('key2', { query: '', tags: [], extra: 'default' })
    )
    expect(restored.current[0]).toEqual({ query: '测试', tags: ['a'], extra: 'default' })
  })

  it('版本号变化时旧缓存失效', async () => {
    const { result, unmount } = renderHook(() =>
      usePersistentToolState('key3', { a: 1 }, { version: 1 })
    )
    act(() => result.current[1]({ a: 99 }))
    await waitFor(() => expect(localStorage.getItem('key3_v1')).toBeTruthy())
    unmount()

    const { result: v2 } = renderHook(() =>
      usePersistentToolState('key3', { a: 1 }, { version: 2 })
    )
    expect(v2.current[0]).toEqual({ a: 1 }) // v2 缓存不存在 → 默认值
    expect(localStorage.getItem('key3_v2')).toBeNull()
  })

  it('exclude 字段不持久化', async () => {
    const { result } = renderHook(() =>
      usePersistentToolState('key4', { title: '', big: '' }, { exclude: ['big'] })
    )
    act(() => result.current[1]({ title: '标题', big: 'x'.repeat(1000) }))
    await waitFor(() => {
      const saved = JSON.parse(localStorage.getItem('key4_v1'))
      expect(saved.title).toBe('标题')
      expect(saved.big).toBeUndefined()
    })
  })

  it('超过 maxBytes 时放弃保存（保护 localStorage）', async () => {
    const { result } = renderHook(() =>
      usePersistentToolState('key5', { content: '' }, { maxBytes: 100 })
    )
    act(() => result.current[1]({ content: 'x'.repeat(200) }))
    await new Promise((r) => setTimeout(r, 400))
    expect(localStorage.getItem('key5_v1')).toBeNull()
  })

  it('localStorage 损坏时安全回落默认值', () => {
    localStorage.setItem('key6_v1', '{broken')
    const { result } = renderHook(() =>
      usePersistentToolState('key6', { ok: true })
    )
    expect(result.current[0]).toEqual({ ok: true })
  })

  it('clear 清空缓存并复位状态', async () => {
    const { result } = renderHook(() =>
      usePersistentToolState('key7', { q: '' })
    )
    act(() => result.current[1]({ q: 'abc' }))
    await waitFor(() => expect(localStorage.getItem('key7_v1')).toBeTruthy())

    act(() => result.current[2].clear())
    expect(result.current[0]).toEqual({ q: '' })
    expect(localStorage.getItem('key7_v1')).toBeNull()
  })
})
