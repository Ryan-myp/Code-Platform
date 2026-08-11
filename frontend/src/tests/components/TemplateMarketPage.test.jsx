/**
 * 模板市场（TemplateMarket）单测：内置模板渲染 / 收藏 toggle + 只看收藏过滤 /
 * 用户市场（C2C）加载与购买 / 我的上传 / 上传模板弹窗校验。
 * api 整体 mock，不触发真实后端；页面使用 useNavigate，用 MemoryRouter 包裹。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../../lib/toast'

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

import TemplateMarketPage from '../../pages/TemplateMarketPage'

const MARKET_DATA = {
  groups: {
    game: {
      items: [
        { id: 't1', name: '贪吃蛇模板', tool: '游戏', color: 'from-emerald-500 to-teal-600', icon: '🐍', description: '经典贪吃蛇玩法', tags: ['经典', '双端'], used: 10, path: '/games' },
        { id: 't2', name: '飞机大战模板', tool: '游戏', color: 'from-blue-500 to-indigo-600', icon: '✈️', description: '弹幕射击玩法', tags: ['射击'], used: 0, path: '/games' },
      ],
    },
    miniapp: {
      items: [
        { id: 't3', name: '打卡助手模板', tool: '小程序', color: 'from-violet-500 to-purple-600', icon: '📅', description: '每日打卡提醒', tags: ['工具'], used: 3, path: '/miniapp' },
      ],
    },
  },
}

const C2C_ITEMS = [
  { id: 'c1', name: '抖音口播脚本', description: '爆款口播模板', category: 'game', price: 10, sales: 2, user_id: 'u1' },
  // 页面默认按 category='game' 过滤（C2C_CATEGORIES 首项），免费模板也归 game 以同时验证两种价格徽章
  { id: 'c2', name: '免费模板', description: '免费分享', category: 'game', price: 0, sales: 5, user_id: 'u2' },
]

const renderPage = () =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <TemplateMarketPage />
      </ToastProvider>
    </MemoryRouter>
  )

describe('TemplateMarketPage 模板市场', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    apiMock.get.mockImplementation((url) => {
      if (String(url).includes('/api/templates/market')) {
        return Promise.resolve({ data: MARKET_DATA })
      }
      if (String(url).includes('/api/templates/c2c')) {
        return Promise.resolve({ data: C2C_ITEMS })
      }
      if (String(url).includes('/api/templates/user')) {
        return Promise.resolve({ data: [] })
      }
      if (String(url).includes('/api/templates/purchases')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: {} })
    })
    apiMock.post.mockResolvedValue({ data: { message: 'ok' } })
    apiMock.delete.mockResolvedValue({ data: { ok: true } })
  })

  it('渲染内置模板列表（分组聚合）', async () => {
    renderPage()
    expect(screen.getByText('模板市场')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('贪吃蛇模板')).toBeInTheDocument())
    expect(screen.getByText('飞机大战模板')).toBeInTheDocument()
    expect(screen.getByText('打卡助手模板')).toBeInTheDocument()
    // 使用次数展示
    expect(screen.getByText('已使用 10 次')).toBeInTheDocument()
    expect(screen.getByText('未使用')).toBeInTheDocument()
  })

  it('收藏 toggle：点击星标收藏，只看收藏过滤生效', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('贪吃蛇模板')).toBeInTheDocument())
    // 收藏 t1
    const favBtns = screen.getAllByTitle('收藏模板')
    fireEvent.click(favBtns[0])
    expect(localStorage.getItem('tm_favs')).toContain('t1')
    // 只看收藏 → 只剩 t1
    fireEvent.click(screen.getByText(/只看收藏/))
    expect(screen.getByText('贪吃蛇模板')).toBeInTheDocument()
    expect(screen.queryByText('飞机大战模板')).not.toBeInTheDocument()
  })

  it('用户市场：切换 Tab 加载 C2C 并购买', async () => {
    renderPage()
    fireEvent.click(screen.getByText('用户市场'))
    expect(await screen.findByText('抖音口播脚本')).toBeInTheDocument()
    expect(screen.getByText('10 积分')).toBeInTheDocument()
    expect(screen.getByText('免费')).toBeInTheDocument()
    // 购买（两个模板各有一个购买按钮，取第一个）
    fireEvent.click(screen.getAllByText('购买')[0])
    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/api/templates/c1/buy'))
    // 购买成功后刷新购买记录
    await waitFor(() => expect(apiMock.get).toHaveBeenCalledWith('/api/templates/purchases'))
  })

  it('我的上传：空列表提示', async () => {
    renderPage()
    fireEvent.click(screen.getByText('我的上传'))
    expect(await screen.findByText('还没有上传模板')).toBeInTheDocument()
  })

  it('上传模板：空名称校验 + 上架调用', async () => {
    renderPage()
    fireEvent.click(screen.getByText('上传模板'))
    // 弹窗出现
    expect(await screen.findByText('上传模板到市场')).toBeInTheDocument()
    // 空名称提交 → 提示且不请求
    fireEvent.click(screen.getByText('上架'))
    expect(await screen.findByText('请输入模板名称')).toBeInTheDocument()
    expect(apiMock.post).not.toHaveBeenCalled()
    // 填写名称后上架
    fireEvent.change(screen.getByPlaceholderText('例如：抖音爆款口播脚本模板'), {
      target: { value: '我的新模板' },
    })
    fireEvent.click(screen.getByText('上架'))
    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        '/api/templates/upload',
        expect.objectContaining({ name: '我的新模板', category: 'game', price: 0 })
      )
    })
  })
})
