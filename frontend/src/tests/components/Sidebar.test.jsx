import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import Sidebar from '../../components/Sidebar'
import { ToastProvider } from '../../lib/toast'

// 包装组件，提供 Router 和 Toast 上下文
function renderWithProviders(ui) {
  return render(
    <BrowserRouter>
      <ToastProvider>{ui}</ToastProvider>
    </BrowserRouter>
  )
}

describe('Sidebar', () => {
  it('renders sidebar with logo', () => {
    renderWithProviders(
      <Sidebar
        sidebarOpen={true}
        setSidebarOpen={() => {}}
        user={{ username: 'admin' }}
        onLogout={() => {}}
      />
    )
    expect(screen.getAllByText(/小团智能平台/i).length).toBeGreaterThan(0)
  })

  it('renders all navigation sections', () => {
    renderWithProviders(
      <Sidebar
        sidebarOpen={true}
        setSidebarOpen={() => {}}
        user={{ username: 'admin' }}
        onLogout={() => {}}
      />
    )
    // 新 IA：统一语义 7 组（工作台/智能研发/Agent 与知识/创作工坊/效率工具/应用与社区/会员与帮助）
    expect(screen.getAllByText(/创作工坊/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/智能研发/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Agent 与知识/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/效率工具/i).length).toBeGreaterThan(0)
  })

  it('expands menu group to show items', () => {
    renderWithProviders(
      <Sidebar
        sidebarOpen={true}
        setSidebarOpen={() => {}}
        user={{ username: 'admin' }}
        onLogout={() => {}}
      />
    )
    fireEvent.click(screen.getAllByText(/创作工坊/i)[0])
    expect(screen.getAllByText(/图片工厂/i).length).toBeGreaterThan(0)
  })
})
