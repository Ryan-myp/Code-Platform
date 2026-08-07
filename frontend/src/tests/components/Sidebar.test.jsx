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
    expect(screen.getAllByText(/研发管理/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/系统配置/i).length).toBeGreaterThan(0)
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
    fireEvent.click(screen.getAllByText(/系统配置/i)[0])
    expect(screen.getAllByText(/插件市场/i).length).toBeGreaterThan(0)
  })
})
