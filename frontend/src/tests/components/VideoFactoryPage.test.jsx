/**
 * v20 视频工厂单测：AI 增强按钮渲染 / 点击调用 enhance-prompt（ti2vid/i2vid mode 传参）/ 结果填入描述框。
 * api 整体 mock，不触发真实后端。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
  defaults: { baseURL: '' },
}))

vi.mock('../../lib/api', () => ({
  default: apiMock,
  api: apiMock,
}))

import VideoFactoryPage from '../../pages/VideoFactoryPage'

describe('VideoFactoryPage v20 AI 增强', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/video-factory/list')) return Promise.resolve({ data: { videos: [] } })
      if (String(url).includes('/api/video-factory/stats')) {
        return Promise.resolve({ data: { total_videos: 0, api_configured: true } })
      }
      return Promise.resolve({ data: {} })
    })
    apiMock.post.mockResolvedValue({ data: {} })
  })

  it('渲染 ✨ AI 增强 按钮', () => {
    render(<VideoFactoryPage />)
    expect(screen.getByText('✨ AI 增强')).toBeInTheDocument()
  })

  it('点击增强：文生视频模式传 ti2vid，结果填入描述框', async () => {
    apiMock.post.mockImplementation((url) => {
      if (String(url).includes('/api/video-factory/enhance-prompt')) {
        return Promise.resolve({
          data: { ok: true, enhanced: '黄昏海面，金色阳光在浪尖跳动，镜头缓慢推进，电影感画质', mode: 'ti2vid' },
        })
      }
      return Promise.resolve({ data: {} })
    })
    render(<VideoFactoryPage />)
    const textarea = screen.getByPlaceholderText(/sunset over the ocean/)
    fireEvent.change(textarea, { target: { value: '海边黄昏' } })
    fireEvent.click(screen.getByText('✨ AI 增强'))
    await waitFor(() => {
      const call = apiMock.post.mock.calls.find(([url]) => String(url).includes('/api/video-factory/enhance-prompt'))
      expect(call).toBeTruthy()
      expect(call[1].get('mode')).toBe('ti2vid')
      expect(call[1].get('prompt')).toBe('海边黄昏')
    })
    await waitFor(() => {
      expect(textarea.value).toContain('镜头缓慢推进')
    })
  })

  it('图生视频模式传 i2vid', async () => {
    apiMock.post.mockImplementation((url) => {
      if (String(url).includes('/api/video-factory/enhance-prompt')) {
        return Promise.resolve({ data: { ok: true, enhanced: '增强后的画面描述文本内容足够长', mode: 'i2vid' } })
      }
      return Promise.resolve({ data: {} })
    })
    render(<VideoFactoryPage />)
    // 切换模式：通过选择框 value 直接改 inputs
    const modeSelect = screen.getAllByRole('combobox').find((el) => el.value === 'ti2vid')
    fireEvent.change(modeSelect, { target: { value: 'i2vid' } })
    const textarea = screen.getByPlaceholderText(/sunset over the ocean/)
    fireEvent.change(textarea, { target: { value: '一只猫在雪地里奔跑' } })
    fireEvent.click(screen.getByText('✨ AI 增强'))
    await waitFor(() => {
      const call = apiMock.post.mock.calls.find(([url]) => String(url).includes('/api/video-factory/enhance-prompt'))
      expect(call[1].get('mode')).toBe('i2vid')
    })
  })
})
