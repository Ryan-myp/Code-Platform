import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

describe('App', () => {
  beforeEach(() => {
    // 模拟已登录状态
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('user', JSON.stringify({ username: 'admin' }))
  })

  it('renders without crashing', () => {
    render(<App />)
    // Sidebar 中有多个“小团智能平台”文字（桌面版 + 移动版）
    expect(screen.getAllByText(/小团智能平台/i).length).toBeGreaterThan(0)
  })

  it('shows navigation menu items', async () => {
    render(<App />)
    // 懒加载路由就绪前整棵子树处于 Suspense fallback，需等待 chunk 加载后 Sidebar 才出现
    expect(await screen.findByText(/创作工坊/i)).toBeInTheDocument()
  })
})
