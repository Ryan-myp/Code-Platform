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
    // 新 IA：5 层精简分组（工作台/创作工坊/AI与工具/协作与管理/会员与帮助）
    expect(screen.getAllByText(/创作工坊/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/协作与管理/i).length).toBeGreaterThan(0)
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
