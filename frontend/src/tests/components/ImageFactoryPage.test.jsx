/**
 * v20 图片工厂单测：AI 润色按钮渲染 / 点击调用 enhance-prompt / 结果填入描述框 + 负面词建议展示。
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

import ImageFactoryPage from '../../pages/ImageFactoryPage'

describe('ImageFactoryPage v20 AI 润色', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/image-factory/images')) return Promise.resolve({ data: [] })
      if (String(url).includes('/api/image-factory/templates')) return Promise.resolve({ data: [] })
      if (String(url).includes('/api/image-factory/stats')) {
        return Promise.resolve({ data: { total_images: 0, total_templates: 0, api_configured: true } })
      }
      return Promise.resolve({ data: {} })
    })
    apiMock.post.mockResolvedValue({ data: {} })
  })

  it('渲染 ✨ AI 润色 按钮', () => {
    render(<ImageFactoryPage />)
    expect(screen.getByText('✨ AI 润色')).toBeInTheDocument()
  })

  it('空描述点击给出提示且不请求', async () => {
    render(<ImageFactoryPage />)
    fireEvent.click(screen.getByText('✨ AI 润色'))
    await waitFor(() => {
      expect(apiMock.post.mock.calls.some(([url]) => String(url).includes('/enhance-prompt'))).toBe(false)
    })
  })

  it('点击润色：调用专用接口并将增强结果填入描述框 + 负面词建议展示', async () => {
    apiMock.post.mockImplementation((url) => {
      if (String(url).includes('/api/image-factory/enhance-prompt')) {
        return Promise.resolve({
          data: {
            ok: true,
            enhanced: '一位少女站在金色麦田里，仰头望向天空，电影感构图，柔和逆光，4k 高清',
            negative_auto: 'low quality, blurry, watermark',
          },
        })
      }
      return Promise.resolve({ data: {} })
    })
    render(<ImageFactoryPage />)
    const textarea = screen.getByPlaceholderText(/Professional product photography/)
    fireEvent.change(textarea, { target: { value: '少女在麦田' } })
    fireEvent.click(screen.getByText('✨ AI 润色'))
    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/image-factory/enhance-prompt'),
        expect.any(FormData),
      )
    })
    await waitFor(() => {
      expect(textarea.value).toContain('金色麦田')
    })
    // 负面词建议展示 + 一键填入
    expect(screen.getByText(/建议负面词/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('一键填入'))
    await waitFor(() => {
      expect(screen.getByText(/已启用负面提示词：low quality/)).toBeInTheDocument()
    })
  })
})
