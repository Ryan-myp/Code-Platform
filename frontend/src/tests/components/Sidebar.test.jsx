import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import Sidebar from '../../components/Sidebar'
import { ToastProvider } from '../../lib/toast'

// 包装组件，提供 Router 和 Toast 上下文
function renderWithProviders(ui) {
  return render(
    <BrowserRouter>
      <ToastProvider>
        {ui}
      </ToastProvider>
    </BrowserRouter>
  )
}

describe('Sidebar', () => {
  it('renders sidebar with logo', () => {
    renderWithProviders(<Sidebar sidebarOpen={false} setSidebarOpen={() => {}} user={{ username: 'admin' }} onLogout={() => {}} />)
    expect(screen.getAllByText(/小团智能平台/i).length).toBeGreaterThan(0)
  })

  it('renders all navigation sections', () => {
    renderWithProviders(<Sidebar sidebarOpen={false} setSidebarOpen={() => {}} user={{ username: 'admin' }} onLogout={() => {}} />)
    expect(screen.getByText(/研发管理/i)).toBeInTheDocument()
    expect(screen.getByText(/插件市场/i)).toBeInTheDocument()
  })
})
