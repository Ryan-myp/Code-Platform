import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Sidebar from '../components/Sidebar'

describe('Sidebar', () => {
  it('renders sidebar with logo', () => {
    render(<Sidebar activePath="/" setActivePath={() => {}} />)
    expect(screen.getByText(/智能研发平台/i)).toBeInTheDocument()
  })

  it('renders all navigation sections', () => {
    render(<Sidebar activePath="/" setActivePath={() => {}} />)
    expect(screen.getByText(/需求管理/i)).toBeInTheDocument()
    expect(screen.getByText(/研发管理/i)).toBeInTheDocument()
    expect(screen.getByText(/插件市场/i)).toBeInTheDocument()
  })
})
