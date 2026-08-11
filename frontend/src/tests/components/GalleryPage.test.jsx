/**
 * 作品广场（Gallery）单测：统计卡片 / 作品瀑布流渲染 / 类型 Tab 切换 /
 * 搜索防抖 / 点赞更新 / 评论面板发布评论。
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
  API_BASE: '',
}))

import GalleryPage from '../../pages/GalleryPage'

const STATS = { works: 12, works_today: 3, likes: 45, comments: 6 }

const WORKS = [
  {
    id: 'w1',
    type: 'image',
    type_label: '图片',
    icon: '🖼️',
    prompt: '夕阳下的城市剪影',
    author: 'image_factory',
    media_url: '/api/x/w1.png',
    likes: 3,
    comments: 1,
    liked: false,
    created_at: '2026-01-01T09:00:00',
  },
  {
    id: 'w2',
    type: 'video',
    type_label: '视频',
    icon: '🎬',
    prompt: '无人机航拍海岸线',
    author: 'video_factory',
    media_url: '/api/x/w2.mp4',
    thumbnail: '/api/x/w2.jpg',
    duration: 5.2,
    likes: 0,
    comments: 0,
    liked: false,
    created_at: '2026-01-02T09:00:00',
  },
  {
    id: 'w3',
    type: 'audio',
    type_label: '歌曲',
    icon: '🎵',
    prompt: '轻快的电子节奏',
    author: 'music_factory',
    media_url: '/api/x/w3.mp3',
    likes: 7,
    comments: 2,
    liked: true,
    created_at: '2026-01-03T09:00:00',
  },
]

describe('GalleryPage 作品广场', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('user', JSON.stringify({ username: 'alice' }))
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/gallery/works?')) {
        return Promise.resolve({ data: WORKS })
      }
      if (String(url).includes('/api/gallery/works/')) {
        return Promise.resolve({ data: WORKS[0] })
      }
      if (String(url).includes('/api/gallery/stats')) {
        return Promise.resolve({ data: STATS })
      }
      if (String(url).includes('/api/comments/thread')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: {} })
    })
    apiMock.post.mockResolvedValue({ data: {} })
    apiMock.delete.mockResolvedValue({ data: { ok: true } })
  })

  it('渲染统计卡片与作品卡片', async () => {
    render(<GalleryPage />)
    await waitFor(() => expect(screen.getByText('12')).toBeInTheDocument())
    expect(screen.getByText('作品总数')).toBeInTheDocument()
    expect(screen.getByText('今日新增')).toBeInTheDocument()
    expect(screen.getByText('累计点赞')).toBeInTheDocument()
    // 作品描述渲染（列表经 setTimeout 宏任务加载，统一等 waitFor）
    await waitFor(() => expect(screen.getByText('夕阳下的城市剪影')).toBeInTheDocument())
    expect(screen.getByText('无人机航拍海岸线')).toBeInTheDocument()
    expect(screen.getByText('轻快的电子节奏')).toBeInTheDocument()
  })

  it('类型 Tab 切换：请求带 type 参数并重新加载', async () => {
    render(<GalleryPage />)
    await waitFor(() => expect(apiMock.get).toHaveBeenCalled())
    fireEvent.click(screen.getByText('视频'))
    await waitFor(() => {
      expect(apiMock.get.mock.calls.some(([url]) => String(url).includes('type=video'))).toBe(true)
    })
  })

  it('搜索防抖：输入关键词后请求带 q 参数', async () => {
    render(<GalleryPage />)
    await waitFor(() => expect(apiMock.get).toHaveBeenCalled())
    fireEvent.change(screen.getByPlaceholderText('搜索作品描述…'), { target: { value: '海岸' } })
    await waitFor(
      () => {
        expect(apiMock.get.mock.calls.some(([url]) => String(url).includes('q=%E6%B5%B7%E5%B2%B8'))).toBe(true)
      },
      { timeout: 1000 }
    )
  })

  it('点赞交互：调用 like 接口并更新计数', async () => {
    apiMock.post.mockImplementation((url) => {
      if (String(url).includes('/like')) {
        return Promise.resolve({ data: { liked: true, likes: 4 } })
      }
      return Promise.resolve({ data: {} })
    })
    render(<GalleryPage />)
    // 卡片上的点赞按钮（避免与统计卡「累计点赞」混淆，用 role=button 限定）
    const likeBtns = await screen.findAllByRole('button', { name: /3/ })
    expect(likeBtns.length).toBeGreaterThan(0)
    fireEvent.click(likeBtns[0])
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/api/gallery/w1/like'))
    expect(await screen.findByText('4')).toBeInTheDocument()
  })

  it('打开评论面板并发布评论', async () => {
    render(<GalleryPage />)
    // 点击 w1 的评论按钮（面板标题与统计卡同文案，用面板独有提示断言）
    const commentBtns = await screen.findAllByRole('button', { name: /1/ })
    fireEvent.click(commentBtns[0])
    // 评论面板出现（空评论时显示抢沙发提示）
    expect(await screen.findByText('还没有评论，来抢沙发~')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('说点什么吧…'), { target: { value: '太美了！' } })
    fireEvent.click(screen.getByText('发布'))
    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        '/api/comments',
        expect.objectContaining({ content: '太美了！', target_type: 'work', target_id: 'w1' })
      )
    })
  })

  it('点击作品卡片打开详情预览（Modal）', async () => {
    render(<GalleryPage />)
    const card = await screen.findByText('夕阳下的城市剪影')
    fireEvent.click(card)
    expect(await screen.findByText(/作品详情/)).toBeInTheDocument()
    expect(screen.getByText('复制提示词')).toBeInTheDocument()
  })
})
